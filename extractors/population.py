from __future__ import annotations

from io import BytesIO
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pandas as pd

from extractors.common import (
    EVACUATION_12,
    area_group,
    empty_records_df,
    normalize_area_id,
    now_iso,
)


TIME_SERIES_URL = "https://www.pref.fukushima.lg.jp/sec/11045b/15847.html"
MONTHLY_URL = "https://www.pref.fukushima.lg.jp/sec/11045b/15846.html"
SOURCE_NAME = "福島県の推計人口（福島県現住人口調査）"


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attr_dict = dict(attrs)
            self._href = attr_dict.get("href")
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


def _page_links(url: str) -> list[tuple[str, str]]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    parser = _LinkParser()
    parser.feed(html)
    return [(text, urljoin(url, href)) for text, href in parser.links if href]


def _find_link(url: str, *keywords: str) -> str | None:
    for text, href in _page_links(url):
        if all(keyword in text for keyword in keywords):
            return href
    return None


def _read_csv_url(url: str) -> pd.DataFrame:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        content = BytesIO(response.read())
    encodings = ["cp932", "utf-8-sig", "utf-8"]
    last_error: Exception | None = None
    for encoding in encodings:
        content.seek(0)
        try:
            return pd.read_csv(content, encoding=encoding)
        except Exception as exc:  # noqa: BLE001 - try common public-data encodings.
            last_error = exc
    if last_error:
        raise last_error
    raise ValueError(f"CSVを読み込めませんでした: {url}")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(col).strip() for col in out.columns]
    return out


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        for col in df.columns:
            if candidate == col or candidate in col:
                return col
    return None


def _period_from_row(row: pd.Series, df: pd.DataFrame) -> str:
    date_col = _find_col(df, ["年月日", "調査年月日", "年月", "基準日"])
    if date_col is not None:
        value = row.get(date_col)
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m")
        if pd.notna(value):
            text = str(value).strip()
            if text:
                return text

    year_col = _find_col(df, ["年", "西暦年"])
    month_col = _find_col(df, ["月"])
    if year_col and month_col:
        year = pd.to_numeric(row.get(year_col), errors="coerce")
        month = pd.to_numeric(row.get(month_col), errors="coerce")
        if pd.notna(year) and pd.notna(month):
            return f"{int(year):04d}-{int(month):02d}"

    return ""


def _records_from_wide(
    df: pd.DataFrame,
    *,
    value_col_candidates: list[str],
    indicator_id: str,
    indicator_name: str,
    unit: str,
    concept: str,
    source_url: str,
) -> pd.DataFrame:
    df = _normalize_columns(df)
    area_col = _find_col(df, ["自治体名_現在", "市町村名", "自治体名", "地域", "市町村"])
    value_col = _find_col(df, value_col_candidates)
    if area_col is None or value_col is None:
        return empty_records_df()

    rows: list[dict[str, object]] = []
    retrieved_at = now_iso()
    for _, row in df.iterrows():
        area_name = str(row.get(area_col, "")).strip()
        if area_name not in EVACUATION_12:
            continue
        value = pd.to_numeric(row.get(value_col), errors="coerce")
        if pd.isna(value):
            continue
        period = _period_from_row(row, df)
        rows.append(
            {
                "indicator_id": indicator_id,
                "indicator_name": indicator_name,
                "category": "避難・帰還・人口移動",
                "concept": concept,
                "area_id": normalize_area_id(area_name),
                "area_name": area_name,
                "area_group": area_group(area_name),
                "period": period,
                "value": float(value),
                "unit": unit,
                "source_type": "行政統計",
                "source_name": SOURCE_NAME,
                "source_url": source_url,
                "retrieved_at": retrieved_at,
                "collection_method": "A",
                "notes": "福島県公開CSVから取得。",
            }
        )
    return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)


def _base_record(
    *,
    indicator_id: str,
    indicator_name: str,
    concept: str,
    area_name: str,
    period: str,
    value: float,
    unit: str,
    source_url: str,
    notes: str,
) -> dict[str, object]:
    return {
        "indicator_id": indicator_id,
        "indicator_name": indicator_name,
        "category": "避難・帰還・人口移動",
        "concept": concept,
        "area_id": normalize_area_id(area_name),
        "area_name": area_name,
        "area_group": area_group(area_name),
        "period": period,
        "value": value,
        "unit": unit,
        "source_type": "行政統計",
        "source_name": SOURCE_NAME,
        "source_url": source_url,
        "retrieved_at": now_iso(),
        "collection_method": "A",
        "notes": notes,
    }


def _records_from_population_long(df: pd.DataFrame, source_url: str) -> pd.DataFrame:
    df = _normalize_columns(df)
    required = {"調査基準日", "自治体名_現在", "性別", "異動種別", "値"}
    if not required.issubset(set(df.columns)):
        return empty_records_df()

    target = df[df["自治体名_現在"].isin(EVACUATION_12)].copy()
    target["period"] = pd.to_datetime(target["調査基準日"], errors="coerce").dt.strftime("%Y-%m")
    target["値"] = pd.to_numeric(target["値"], errors="coerce")

    rows: list[dict[str, object]] = []
    population = target[target["異動種別"] == "人口"]
    population_grouped = population.groupby(["period", "自治体名_現在"], as_index=False)["値"].sum()
    for _, row in population_grouped.dropna(subset=["値"]).iterrows():
        rows.append(
            _base_record(
                indicator_id="current_population",
                indicator_name="現住人口",
                concept="人口再構成・移住定住",
                area_name=row["自治体名_現在"],
                period=row["period"],
                value=float(row["値"]),
                unit="人",
                source_url=source_url,
                notes="福島県公開CSVから取得。男女別人口を合算。",
            )
        )

    households = target[target["異動種別"] == "世帯"]
    households_grouped = households.groupby(["period", "自治体名_現在"], as_index=False)["値"].sum()
    for _, row in households_grouped.dropna(subset=["値"]).iterrows():
        rows.append(
            _base_record(
                indicator_id="households",
                indicator_name="世帯数",
                concept="人口再構成・移住定住",
                area_name=row["自治体名_現在"],
                period=row["period"],
                value=float(row["値"]),
                unit="世帯",
                source_url=source_url,
                notes="福島県公開CSVから取得。",
            )
        )

    return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)


def _records_from_social_change_long(df: pd.DataFrame, source_url: str) -> pd.DataFrame:
    df = _normalize_columns(df)
    required = {"調査基準日", "自治体名_現在", "異動種別", "値"}
    if not required.issubset(set(df.columns)):
        return empty_records_df()

    target = df[df["自治体名_現在"].isin(EVACUATION_12)].copy()
    target["period"] = pd.to_datetime(target["調査基準日"], errors="coerce").dt.strftime("%Y-%m")
    target["値"] = pd.to_numeric(target["値"], errors="coerce")
    grouped = target.groupby(["period", "自治体名_現在", "異動種別"], as_index=False)["値"].sum()
    pivot = grouped.pivot_table(index=["period", "自治体名_現在"], columns="異動種別", values="値", aggfunc="sum").reset_index()
    pivot["転入数"] = pivot.get("転入", 0).fillna(0)
    pivot["転出数"] = pivot.get("転出", 0).fillna(0)
    pivot["社会増減"] = pivot["転入数"] - pivot["転出数"]

    indicators = [
        ("transfer_in", "転入数", "転入者数。県内外から当該市町村に移った人数。"),
        ("transfer_out", "転出数", "転出者数。当該市町村から県内外へ移った人数。"),
        ("social_change", "社会増減", "転入数から転出数を差し引いて算出。"),
    ]
    rows = []
    for _, row in pivot.iterrows():
        for indicator_id, indicator_name, notes in indicators:
            value = pd.to_numeric(row.get(indicator_name), errors="coerce")
            if pd.isna(value):
                continue
            rows.append(
                _base_record(
                    indicator_id=indicator_id,
                    indicator_name=indicator_name,
                    concept="人口動態",
                    area_name=row["自治体名_現在"],
                    period=row["period"],
                    value=float(value),
                    unit="人",
                    source_url=source_url,
                    notes=f"福島県公開CSVから取得。{notes}",
                )
            )
    return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)


def _records_from_natural_change_long(df: pd.DataFrame, source_url: str) -> pd.DataFrame:
    df = _normalize_columns(df)
    required = {"調査基準日", "自治体名_現在", "異動種別", "値"}
    if not required.issubset(set(df.columns)):
        return empty_records_df()

    target = df[df["自治体名_現在"].isin(EVACUATION_12)].copy()
    target["period"] = pd.to_datetime(target["調査基準日"], errors="coerce").dt.strftime("%Y-%m")
    target["値"] = pd.to_numeric(target["値"], errors="coerce")
    grouped = target.groupby(["period", "自治体名_現在", "異動種別"], as_index=False)["値"].sum()
    pivot = grouped.pivot_table(index=["period", "自治体名_現在"], columns="異動種別", values="値", aggfunc="sum").reset_index()
    pivot["出生数"] = pivot.get("出生", 0).fillna(0)
    pivot["死亡数"] = pivot.get("死亡", 0).fillna(0)
    pivot["自然増減"] = pivot["出生数"] - pivot["死亡数"]

    indicators = [
        ("births", "出生数", "出生数。男女別行を合算。"),
        ("deaths", "死亡数", "死亡数。男女別行を合算。"),
        ("natural_change", "自然増減", "出生数から死亡数を差し引いて算出。"),
    ]
    rows = []
    for _, row in pivot.iterrows():
        for indicator_id, indicator_name, notes in indicators:
            value = pd.to_numeric(row.get(indicator_name), errors="coerce")
            if pd.isna(value):
                continue
            rows.append(
                _base_record(
                    indicator_id=indicator_id,
                    indicator_name=indicator_name,
                    concept="人口動態",
                    area_name=row["自治体名_現在"],
                    period=row["period"],
                    value=float(value),
                    unit="人",
                    source_url=source_url,
                    notes=f"福島県公開CSVから取得。{notes}",
                )
            )
    return pd.concat([empty_records_df(), pd.DataFrame(rows)], ignore_index=True)


def _fallback_latest_population() -> pd.DataFrame:
    csv_url = _find_link(MONTHLY_URL, "統計表")
    if not csv_url:
        return empty_records_df()
    df = _read_csv_url(csv_url)
    frames = [
        _records_from_wide(
            df,
            value_col_candidates=["総人口", "人口総数", "人口"],
            indicator_id="current_population",
            indicator_name="現住人口",
            unit="人",
            concept="人口再構成・移住定住",
            source_url=csv_url,
        ),
        _records_from_wide(
            df,
            value_col_candidates=["世帯数", "世帯"],
            indicator_id="households",
            indicator_name="世帯数",
            unit="世帯",
            concept="人口再構成・移住定住",
            source_url=csv_url,
        ),
    ]
    return pd.concat(frames, ignore_index=True)


def fetch_population_households() -> pd.DataFrame:
    """福島県公開CSVから12市町村の人口・世帯を取得する。"""
    csv_url = _find_link(TIME_SERIES_URL, "人口・世帯")
    if not csv_url:
        return _fallback_latest_population()

    df = _read_csv_url(csv_url)
    long_records = _records_from_population_long(df, csv_url)
    if not long_records.empty:
        return long_records
    frames = [
        _records_from_wide(
            df,
            value_col_candidates=["総人口", "人口総数", "人口"],
            indicator_id="current_population",
            indicator_name="現住人口",
            unit="人",
            concept="人口再構成・移住定住",
            source_url=csv_url,
        ),
        _records_from_wide(
            df,
            value_col_candidates=["世帯数", "世帯"],
            indicator_id="households",
            indicator_name="世帯数",
            unit="世帯",
            concept="人口再構成・移住定住",
            source_url=csv_url,
        ),
    ]
    result = pd.concat(frames, ignore_index=True)
    if result.empty:
        return _fallback_latest_population()
    return result


def fetch_social_change() -> pd.DataFrame:
    """福島県公開CSVから12市町村の転入・転出・社会増減を取得する。"""
    csv_url = _find_link(TIME_SERIES_URL, "社会動態", "月次")
    if not csv_url:
        return empty_records_df()
    df = _read_csv_url(csv_url)
    long_records = _records_from_social_change_long(df, csv_url)
    if not long_records.empty:
        return long_records
    return _records_from_wide(
        df,
        value_col_candidates=["社会増減", "純移動", "転入超過"],
        indicator_id="social_change",
        indicator_name="社会増減",
        unit="人",
        concept="人口動態",
        source_url=csv_url,
    )


def fetch_natural_change() -> pd.DataFrame:
    """福島県公開CSVから12市町村の出生・死亡・自然増減を取得する。"""
    csv_url = _find_link(TIME_SERIES_URL, "自然動態", "月次")
    if not csv_url:
        return empty_records_df()
    df = _read_csv_url(csv_url)
    return _records_from_natural_change_long(df, csv_url)


def fetch_population_indicators() -> pd.DataFrame:
    frames = [fetch_population_households(), fetch_social_change(), fetch_natural_change()]
    return pd.concat(frames, ignore_index=True)
