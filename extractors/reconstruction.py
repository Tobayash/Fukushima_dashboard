from __future__ import annotations

from io import BytesIO
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pandas as pd
from bs4 import BeautifulSoup
import pdfplumber

from extractors.common import AREAS, EVACUATION_12, area_group, empty_records_df, normalize_area_id, now_iso


RESIDENT_RATE_SOURCE_NAME = "福島県「令和8年度 ふくしま復興・創生に向けて」（資料5-2）"
RESIDENT_RATE_SOURCE_URL = "https://www.reconstruction.go.jp/files/user/topics/250828_shiryou5-2.pdf"
EVACUEES_SOURCE_NAME = "福島県 避難者数の推移"
EVACUEES_SOURCE_URL = "https://www.pref.fukushima.lg.jp/site/portal/hinansya.html"
INTENTION_SOURCE_NAME = "復興庁 原子力被災自治体における住民意向調査"
INTENTION_SOURCE_URL = "https://www.reconstruction.go.jp/topics/cat-11/cat-41/cat-136/ikoucyousa/"


RESIDENT_RATES_2025_06 = {
    "広野町": 91.5,
    "田村市": 87.0,
    "川内村": 83.9,
    "楢葉町": 70.4,
    "南相馬市": 65.3,
    "川俣町": 52.6,
    "葛尾村": 38.5,
    "飯舘村": 34.0,
    "富岡町": 23.8,
    "浪江町": 16.3,
    "大熊町": 10.3,
    "双葉町": 3.6,
}


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        raw = response.read()
    for encoding in ("utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def _parse_reiwa_date(text: str) -> str:
    match = re.search(r"令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", text)
    if not match:
        return ""
    year = 2018 + int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_pref_evacuees(text: str) -> dict[str, object] | None:
    date_match = re.search(r"現在の避難者数（(?P<date>令和\s*\d+\s*年\s*\d+\s*月\s*\d+\s*日)時点）", text)
    total_match = re.search(
        r"(?P<total>[0-9,]+)\s*人.*?うち県外避難者(?P<outside>[0-9,]+)\s*人\s*"
        r"県内避難者(?P<inside>[0-9,]+)\s*人\s*避難先不明者(?P<unknown>[0-9,]+)\s*人",
        text,
        re.S,
    )
    if not total_match:
        return None

    def as_int(name: str) -> int:
        return int(total_match.group(name).replace(",", ""))

    return {
        "period": _parse_reiwa_date(date_match.group("date")) if date_match else "",
        "total": as_int("total"),
        "outside": as_int("outside"),
        "inside": as_int("inside"),
        "unknown": as_int("unknown"),
    }


def fetch_resident_rate() -> pd.DataFrame:
    """避難地域12市町村の居住率。

    PDF本文から確認できた2025年6月時点の値を、出典URL付きの構造化データとして
    保持する。今後、同形式の新PDFが継続公開される場合はPDF抽出に置き換える。
    """
    rows = []
    for area_name, value in RESIDENT_RATES_2025_06.items():
        rows.append(
            {
                "indicator_id": "resident_rate",
                "indicator_name": "居住率",
                "category": "避難・帰還・人口移動",
                "concept": "居住再開",
                "area_id": normalize_area_id(area_name),
                "area_name": area_name,
                "area_group": area_group(area_name),
                "period": "2025-06",
                "value": value,
                "unit": "%",
                "source_type": "行政資料",
                "source_name": RESIDENT_RATE_SOURCE_NAME,
                "source_url": RESIDENT_RATE_SOURCE_URL,
                "retrieved_at": now_iso(),
                "collection_method": "B",
                "notes": "PDF 2ページ目の掲載値。田村市は都路地区、南相馬市は小高区等、川俣町は山木屋地区。",
            }
        )
    return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)


def fetch_current_population() -> pd.DataFrame:
    """後方互換用。人口系は extractors.population を使用する。"""
    return empty_records_df()


def fetch_evacuees() -> pd.DataFrame:
    """避難者数データ。

    県全体の現在値は福島県ページから自動取得する。市町村別の値は取得元を
    追加確認中のため、初期版では未取得レコードとして残す。
    """
    rows = []
    retrieved_at = now_iso()
    try:
        parsed = _parse_pref_evacuees(_fetch_text(EVACUEES_SOURCE_URL))
    except Exception:  # noqa: BLE001 - UI should still show municipality placeholders.
        parsed = None

    if parsed is not None:
        rows.append(
            {
                "indicator_id": "evacuees",
                "indicator_name": "避難者数",
                "category": "避難・帰還・人口移動",
                "concept": "避難継続",
                "area_id": "pref_fukushima",
                "area_name": "福島県",
                "area_group": area_group("福島県"),
                "period": parsed["period"],
                "value": parsed["total"],
                "unit": "人",
                "source_type": "行政資料",
                "source_name": EVACUEES_SOURCE_NAME,
                "source_url": EVACUEES_SOURCE_URL,
                "retrieved_at": retrieved_at,
                "collection_method": "B",
                "notes": f"県全体値。内訳: 県外避難者{parsed['outside']:,}人、県内避難者{parsed['inside']:,}人、避難先不明者{parsed['unknown']:,}人。",
            }
        )

    for area in AREAS:
        if area["area_id"] == "pref_fukushima":
            continue
        rows.append(
            {
                "indicator_id": "evacuees",
                "indicator_name": "避難者数",
                "category": "避難・帰還・人口移動",
                "concept": "避難継続",
                "area_id": area["area_id"],
                "area_name": area["area_name"],
                "area_group": area_group(area["area_name"]),
                "period": "",
                "value": None,
                "unit": "人",
                "source_type": "行政資料",
                "source_name": "福島県 避難者数の推移 / 避難地域12市町村の状況",
                "source_url": EVACUEES_SOURCE_URL,
                "retrieved_at": retrieved_at,
                "collection_method": "B",
                "notes": "市町村別の粒度と基準日を追加確認中。県全体値は同ページから取得済み。",
            }
        )
    return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)


def _fiscal_year_start(label: str) -> int | None:
    reiwa = re.search(r"令和\s*(元|\d+)\s*年度", label)
    if reiwa:
        year = 1 if reiwa.group(1) == "元" else int(reiwa.group(1))
        return 2018 + year
    heisei = re.search(r"平成\s*(\d+)\s*年度", label)
    if heisei:
        return 1988 + int(heisei.group(1))
    return None


def _all_intention_reports() -> list[dict[str, str]]:
    html = _fetch_text(INTENTION_SOURCE_URL)
    soup = BeautifulSoup(html, "html.parser")
    reports: list[dict[str, str]] = []

    for heading in soup.find_all(["h2", "h3"]):
        fiscal_label = heading.get_text(" ", strip=True)
        fiscal_start = _fiscal_year_start(fiscal_label)
        if fiscal_start is None:
            continue
        table = heading.find_next("table")
        if table is None:
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 5:
                continue
            area_name = cells[0].get_text(" ", strip=True)
            if area_name not in EVACUATION_12:
                continue

            links = [(a.get_text(" ", strip=True), urljoin(INTENTION_SOURCE_URL, a.get("href", ""))) for a in tr.find_all("a")]
            pdf_url = next((href for text, href in links if text == "速報版"), None)
            if pdf_url is None:
                pdf_url = next((href for text, href in links if text == "報告書"), None)
            if pdf_url is None:
                continue

            reports.append(
                {
                    "area_name": area_name,
                    "fiscal_start": str(fiscal_start),
                    "fiscal_label": fiscal_label,
                    "period": str(fiscal_start),
                    "survey_period": cells[1].get_text(" ", strip=True),
                    "source_url": pdf_url,
                }
            )

    return sorted(reports, key=lambda row: (row["area_name"], row["fiscal_start"]))


def _latest_intention_reports() -> dict[str, dict[str, str]]:
    reports: dict[str, dict[str, str]] = {}
    for report in sorted(_all_intention_reports(), key=lambda row: row["fiscal_start"], reverse=True):
        if report["area_name"] not in reports:
            reports[report["area_name"]] = {
                "fiscal_label": report["fiscal_label"],
                "period": report["period"],
                "survey_period": report["survey_period"],
                "source_url": report["source_url"],
            }
    return reports


def _pdf_text(url: str) -> str:
    raw = _fetch_bytes(url)
    parts: list[str] = []
    with pdfplumber.open(BytesIO(raw)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                parts.append(text)
    return "\n".join(parts)


def _parse_intention_values(text: str) -> dict[str, float] | None:
    for line in text.splitlines():
        match = re.search(r"全\s*体\s+n\s*=\s*[\d,]+\s+(?P<values>.+)$", line)
        if not match:
            continue
        values = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", match.group("values"))]
        if len(values) < 5:
            continue
        return {
            "intention_returned": values[0],
            "intention_want_return": values[1],
            "intention_undecided": values[2],
            "intention_no_return": values[3],
            "intention_no_answer": values[4],
        }
    return None


INTENTION_INDICATORS = [
    ("intention_returned", "戻っている割合"),
    ("intention_want_return", "戻りたい割合"),
    ("intention_undecided", "まだ判断がつかない割合"),
    ("intention_no_return", "戻らない割合"),
    ("intention_no_answer", "無回答割合"),
]


def _return_intention_records(area: dict[str, str], report: dict[str, str] | None, values: dict[str, float] | None, retrieved_at: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    area_name = area["area_name"]
    for indicator_id, indicator_name in INTENTION_INDICATORS:
        rows.append(
            {
                "indicator_id": indicator_id,
                "indicator_name": indicator_name,
                "category": "避難・帰還・人口移動",
                "concept": "帰還意向",
                "area_id": area["area_id"],
                "area_name": area_name,
                "area_group": area_group(area_name),
                "period": report["period"] if report and values else "",
                "value": values.get(indicator_id) if values else None,
                "unit": "%",
                "source_type": "公的調査",
                "source_name": INTENTION_SOURCE_NAME,
                "source_url": report["source_url"] if report else INTENTION_SOURCE_URL,
                "retrieved_at": retrieved_at,
                "collection_method": "B",
                "notes": (
                    f"{report['fiscal_label']}PDFから抽出。調査時期: {report['survey_period']}。"
                    "5カテゴリ（戻っている、戻りたい、まだ判断がつかない、戻らない、無回答）を、PDFの全体行から抽出。"
                    if report and values
                    else "NO DATA: 復興庁の住民意向調査ページに該当データがない、またはPDF形式が抽出非対応。"
                ),
            }
        )
    return rows


def fetch_return_intentions_for_area(area_name: str) -> pd.DataFrame:
    """選択市町村だけ、住民意向調査の年度別PDFを抽出する。"""
    area = next((row for row in AREAS if row["area_name"] == area_name), None)
    if area is None or area["area_id"] == "pref_fukushima":
        return empty_records_df()

    retrieved_at = now_iso()
    try:
        reports = [report for report in _all_intention_reports() if report["area_name"] == area_name]
    except Exception:  # noqa: BLE001 - keep UI usable when the list page fails.
        reports = []

    rows: list[dict[str, object]] = []
    for report in reports:
        try:
            values = _parse_intention_values(_pdf_text(report["source_url"]))
        except Exception:  # noqa: BLE001 - PDF formats differ by year.
            values = None
        if values:
            rows.extend(_return_intention_records(area, report, values, retrieved_at))

    if not rows:
        rows.extend(_return_intention_records(area, None, None, retrieved_at))
    return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)


def fetch_return_intentions() -> pd.DataFrame:
    """住民意向調査由来の帰還意向データ。

    復興庁ページで各市町村の最新PDFを探し、帰還意向の「全体」行を抽出する。
    取得できない市町村は NO DATA レコードとして返す。
    """
    rows = []
    retrieved_at = now_iso()
    try:
        reports = _latest_intention_reports()
    except Exception:  # noqa: BLE001 - keep placeholders visible when network/PDF page fails.
        reports = {}

    for area in AREAS:
        if area["area_id"] == "pref_fukushima":
            continue
        area_name = area["area_name"]
        report = reports.get(area_name)
        values: dict[str, float] | None = None
        if report is not None:
            try:
                values = _parse_intention_values(_pdf_text(report["source_url"]))
            except Exception:  # noqa: BLE001 - report availability differs by year/PDF format.
                values = None
        rows.extend(_return_intention_records(area, report, values, retrieved_at))
    return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)
