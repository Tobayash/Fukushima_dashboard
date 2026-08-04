from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pandas as pd
import pdfplumber

from extractors.common import AREAS, EVACUATION_12, RAW_DIR, area_group, empty_records_df, normalize_area_id, now_iso


INFRA_SOURCE_PAGE_URL = "https://www.reconstruction.go.jp/topics/cat-11/cat-22/cat-23/202509301409578788/"
INFRA_SOURCE_NAME = "復興庁 福島12市町村における公共インフラ復旧の工程表"
INFRA_CACHE = RAW_DIR / "infrastructure_life_industry_indicators_v1.csv"


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = " ".join(part.strip() for part in self._text_parts if part.strip())
            self.links.append((text, self._href))
            self._href = None
            self._text_parts = []


def _fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def _latest_period_from_text(text: str) -> str:
    match = re.search(r"令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", text)
    if not match:
        return "2025-09-30"
    year = 2018 + int(match.group(1))
    return f"{year:04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def _parse_links(url: str) -> list[tuple[str, str]]:
    html = _fetch_bytes(url).decode("utf-8", errors="replace")
    parser = _LinkParser()
    parser.feed(html)
    return [(text, urljoin(url, href)) for text, href in parser.links]


def _source_pages() -> list[str]:
    pages = [INFRA_SOURCE_PAGE_URL]
    for text, href in _parse_links(INFRA_SOURCE_PAGE_URL):
        if "令和6年度公表分" in text or "令和5年度公表分" in text:
            pages.append(href)
    return pages


def _municipality_pdf_links(url: str) -> dict[str, tuple[str, str, str]]:
    links: dict[str, tuple[str, str, str]] = {}
    for text, href in _parse_links(url):
        if not href.lower().endswith(".pdf"):
            continue
        area_name = next((name for name in EVACUATION_12 if name in text), None)
        if area_name is None:
            continue
        period = _latest_period_from_text(text)
        links[area_name] = (period, text, href)
    return links


def _pdf_text(url: str) -> str:
    raw = _fetch_bytes(url)
    parts: list[str] = []
    with pdfplumber.open(BytesIO(raw)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                parts.append(text)
    return "\n".join(parts)


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text))


def _metrics_from_text(text: str) -> dict[str, int]:
    return {
        "infra_completion_mentions": _count(r"(?<!未)完了", text),
        "infra_future_mentions": _count(r"完了予定|実施予定|予定なし|工事中|整備中|着手|発注|検討", text),
        "life_medical_mentions": _count(r"医療施設|医療機関|病院|診療所|診療|救急", text),
        "life_school_mentions": _count(r"学校施設|学校|小学校|中学校|義務教育学校|幼稚園|こども園", text),
        "life_commerce_mentions": _count(r"商業|買物|買い物|スーパー|店舗|小売|商店", text),
        "industry_mentions": _count(r"農林業施設|農地|農業|営農|漁港|水産|産業|工業|事業所", text),
    }


METRIC_DEFINITIONS = {
    "infra_completion_mentions": ("公共インフラ工程表 完了記載数", "件", "公共インフラ・復旧工事進捗", "工程表内で「完了」と読める記載を数えた参考値。事業数そのものではありません。"),
    "infra_future_mentions": ("公共インフラ工程表 予定・着手記載数", "件", "公共インフラ・復旧工事進捗", "工程表内で予定・工事中・着手・発注等と読める記載を数えた参考値。事業数そのものではありません。"),
    "life_medical_mentions": ("医療機能関連記載数", "件", "学校・医療・商業施設など生活機能", "工程表内の医療施設・医療機関・診療等の関連語を数えた参考値。施設数そのものではありません。"),
    "life_school_mentions": ("学校機能関連記載数", "件", "学校・医療・商業施設など生活機能", "工程表内の学校施設・学校等の関連語を数えた参考値。学校数そのものではありません。"),
    "life_commerce_mentions": ("商業機能関連記載数", "件", "学校・医療・商業施設など生活機能", "工程表内の商業・買物・店舗等の関連語を数えた参考値。店舗数そのものではありません。"),
    "industry_mentions": ("産業・農林水産関連記載数", "件", "地域経済・産業", "工程表内の農地・農業・営農・漁港・産業等の関連語を数えた参考値。事業所数そのものではありません。"),
}


def _record(
    *,
    indicator_id: str,
    area_name: str,
    period: str,
    value: float | None,
    source_url: str,
    notes: str,
    retrieved_at: str,
) -> dict[str, object]:
    indicator_name, unit, concept, metric_note = METRIC_DEFINITIONS[indicator_id]
    return {
        "indicator_id": indicator_id,
        "indicator_name": indicator_name,
        "category": concept,
        "concept": concept,
        "area_id": normalize_area_id(area_name),
        "area_name": area_name,
        "area_group": area_group(area_name),
        "period": period if value is not None else "",
        "value": value,
        "unit": unit,
        "source_type": "行政資料",
        "source_name": INFRA_SOURCE_NAME,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "collection_method": "B",
        "notes": f"{notes} {metric_note}",
    }


def fetch_infrastructure_life_industry_indicators() -> pd.DataFrame:
    """公共インフラ・生活機能・産業関連の工程表テキスト指標を取得する。"""
    if INFRA_CACHE.exists():
        return pd.concat([empty_records_df(), pd.read_csv(INFRA_CACHE)], ignore_index=True)

    rows: list[dict[str, object]] = []
    retrieved_at = now_iso()

    try:
        source_pages = _source_pages()
    except Exception as exc:  # noqa: BLE001 - keep visible NO DATA rows.
        source_pages = []
        page_error = str(exc)
    else:
        page_error = ""

    seen_area_ids: set[str] = set()
    for source_page in source_pages:
        try:
            links = _municipality_pdf_links(source_page)
        except Exception:
            continue

        for area in AREAS:
            if area["area_id"] == "pref_fukushima":
                continue
            area_name = area["area_name"]
            link = links.get(area_name)
            if link is None:
                continue
            period, label, source_url = link
            try:
                metrics = _metrics_from_text(_pdf_text(source_url))
            except Exception:
                continue
            else:
                notes = f"{label}のPDF本文から関連語を機械抽出。"
                seen_area_ids.add(area["area_id"])
                for indicator_id in METRIC_DEFINITIONS:
                    rows.append(
                        _record(
                            indicator_id=indicator_id,
                            area_name=area_name,
                            period=period,
                            value=float(metrics[indicator_id]),
                            source_url=source_url,
                            notes=notes,
                            retrieved_at=retrieved_at,
                        )
                    )

    latest_source_url = source_pages[0] if source_pages else INFRA_SOURCE_PAGE_URL
    for area in AREAS:
        if area["area_id"] == "pref_fukushima" or area["area_id"] in seen_area_ids:
            continue
        notes = "NO DATA: 復興庁の工程表ページで当該市町村PDFを確認できませんでした。"
        if page_error:
            notes += f" ページ取得エラー: {page_error}。"
        for indicator_id in METRIC_DEFINITIONS:
            rows.append(
                _record(
                    indicator_id=indicator_id,
                    area_name=area["area_name"],
                    period="",
                    value=None,
                    source_url=latest_source_url,
                    notes=notes,
                    retrieved_at=retrieved_at,
                )
            )

    out = pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)
    if not out.empty:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        out.to_csv(INFRA_CACHE, index=False, encoding="utf-8-sig")
    return out
