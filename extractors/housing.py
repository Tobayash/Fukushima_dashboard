from __future__ import annotations

from io import BytesIO
from html.parser import HTMLParser
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pandas as pd
import pdfplumber

from extractors.common import AREAS, EVACUATION_12, area_group, empty_records_df, normalize_area_id, now_iso


HOUSING_PROGRESS_PAGE_URL = "https://www.pref.fukushima.lg.jp/site/portal/ps-saigaikoueitou.html"
HOUSING_SOURCE_NAME = "福島県 帰還者のための災害公営住宅等の進捗状況"


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


def _housing_pdfs() -> list[tuple[str, str, str]]:
    html = _fetch_bytes(HOUSING_PROGRESS_PAGE_URL).decode("utf-8", errors="replace")
    parser = _LinkParser()
    parser.feed(html)
    candidates: list[tuple[str, str, str]] = []
    for text, href in parser.links:
        if "現在の進捗状況" not in text or not href.lower().endswith(".pdf"):
            continue
        period = _period_from_label(text)
        if period:
            candidates.append((period, text, urljoin(HOUSING_PROGRESS_PAGE_URL, href)))
    if not candidates:
        raise ValueError("帰還者向け住宅進捗PDFを見つけられませんでした。")
    return sorted(candidates, key=lambda row: row[0])


def _period_from_label(text: str) -> str:
    match = re.search(r"令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", text)
    if match:
        year = 2018 + int(match.group(1))
        return f"{year:04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.search(r"令和\s*(\d+)年(\d+)月(\d+)日", text)
    if match:
        year = 2018 + int(match.group(1))
        return f"{year:04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return ""


def _pdf_text(url: str) -> str:
    raw = _fetch_bytes(url)
    parts: list[str] = []
    with pdfplumber.open(BytesIO(raw)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                parts.append(text)
    return "\n".join(parts)


def _parse_area_totals(text: str) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = {}
    current_area: str | None = None

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if "小計③" in line or "合計①" in line:
            break
        if "小計①" in line or "小計②" in line:
            current_area = None
            continue

        for area_name in EVACUATION_12:
            if area_name in line:
                current_area = area_name

        if current_area is None:
            continue
        if "計 " not in line and not line.startswith("計 "):
            continue

        numbers = [int(value) for value in re.findall(r"(?<![A-Za-z])\d+", line)]
        if len(numbers) < 2:
            continue
        planned = float(numbers[-2])
        completed = float(numbers[-1])
        if planned <= 0:
            continue
        record = totals.setdefault(current_area, {"planned": 0.0, "completed": 0.0})
        record["planned"] += planned
        record["completed"] += completed

    return totals


def _housing_records_for_area(
    *,
    area_name: str,
    period: str,
    source_url: str,
    notes: str,
    retrieved_at: str,
    planned: float | None = None,
    completed: float | None = None,
) -> list[dict[str, object]]:
    completion_rate = completed / planned * 100 if planned else None
    return [
        _record(
            indicator_id="returnee_housing_planned",
            indicator_name="帰還者向け住宅計画戸数",
            area_name=area_name,
            period=period,
            value=planned,
            unit="戸",
            source_url=source_url,
            notes=notes,
            retrieved_at=retrieved_at,
        ),
        _record(
            indicator_id="returnee_housing_completed",
            indicator_name="帰還者向け住宅完成戸数",
            area_name=area_name,
            period=period,
            value=completed,
            unit="戸",
            source_url=source_url,
            notes=notes,
            retrieved_at=retrieved_at,
        ),
        _record(
            indicator_id="returnee_housing_completion_rate",
            indicator_name="帰還者向け住宅完成率",
            area_name=area_name,
            period=period,
            value=completion_rate,
            unit="%",
            source_url=source_url,
            notes=notes,
            retrieved_at=retrieved_at,
        ),
    ]


def _record(
    *,
    indicator_id: str,
    indicator_name: str,
    area_name: str,
    period: str,
    value: float | None,
    unit: str,
    source_url: str,
    notes: str,
    retrieved_at: str,
) -> dict[str, object]:
    return {
        "indicator_id": indicator_id,
        "indicator_name": indicator_name,
        "category": "生活再建・居住環境",
        "concept": "住宅整備",
        "area_id": normalize_area_id(area_name),
        "area_name": area_name,
        "area_group": area_group(area_name),
        "period": period if value is not None else "",
        "value": value,
        "unit": unit,
        "source_type": "行政資料",
        "source_name": HOUSING_SOURCE_NAME,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "collection_method": "B",
        "notes": notes,
    }


def fetch_returnee_housing_progress() -> pd.DataFrame:
    """帰還者向け住宅整備の進捗を福島県公式PDFから時系列で取得する。"""
    rows: list[dict[str, object]] = []
    retrieved_at = now_iso()

    try:
        pdfs = _housing_pdfs()
    except Exception as exc:  # noqa: BLE001 - keep the dashboard available with NO DATA rows.
        notes = f"NO DATA: 福島県公式ページまたはPDFから住宅整備データを取得できませんでした（{exc}）。"
        for area in AREAS:
            if area["area_id"] == "pref_fukushima":
                continue
            rows.extend(
                _housing_records_for_area(
                    area_name=area["area_name"],
                    period="",
                    source_url=HOUSING_PROGRESS_PAGE_URL,
                    notes=notes,
                    retrieved_at=retrieved_at,
                )
        )
        return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)

    seen_areas: set[str] = set()
    failed_labels: list[str] = []
    for period, label, pdf_url in pdfs:
        try:
            totals = _parse_area_totals(_pdf_text(pdf_url))
        except Exception:  # noqa: BLE001 - one old PDF should not hide the rest of the series.
            failed_labels.append(label)
            continue

        for area_name, values in totals.items():
            seen_areas.add(area_name)
            planned = values["planned"]
            completed = values["completed"]
            notes = f"{label}のPDFから、市町村内の帰還者向け災害公営住宅・再生賃貸住宅等の合計行を抽出。"
            rows.extend(
                _housing_records_for_area(
                    area_name=area_name,
                    period=period,
                    source_url=pdf_url,
                    notes=notes,
                    retrieved_at=retrieved_at,
                    planned=planned,
                    completed=completed,
                )
            )

    for area in AREAS:
        if area["area_id"] == "pref_fukushima":
            continue
        area_name = area["area_name"]
        if area_name in seen_areas:
            continue
        notes = "NO DATA: 確認できた住宅整備PDFに当該市町村の帰還者向け住宅整備合計行を確認できませんでした。"
        if failed_labels:
            notes += f" 一部PDFは抽出できませんでした: {', '.join(failed_labels)}。"
        rows.extend(
            _housing_records_for_area(
                area_name=area_name,
                period="",
                source_url=HOUSING_PROGRESS_PAGE_URL,
                notes=notes,
                retrieved_at=retrieved_at,
            )
        )

    return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)
