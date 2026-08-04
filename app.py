from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from extractors.health import fetch_suicide_health_indicators


APP_DIR = Path(__file__).resolve().parent
SNAPSHOT_DATA_PATH = APP_DIR / "data" / "processed" / "share_master_indicators.csv"
MAP_IMAGE_PATH = APP_DIR / "data" / "raw" / "fukushima_map_export.png"
DATA_VERSION = "2026-08-04-health-suicide-v4"
AREA_SELECTION_KEY = "area_select_v1"
INDICATOR_SELECTION_PREFIX = "indicator_select_by_category_v1"
HEALTH_INDICATOR_IDS = {"suicide_deaths_vital", "suicide_rate_vital"}
CHART_START_DATE = pd.Timestamp("2011-03-11")

AREA_OPTIONS = [
    "南相馬市",
    "田村市",
    "川俣町",
    "広野町",
    "楢葉町",
    "富岡町",
    "川内村",
    "大熊町",
    "双葉町",
    "浪江町",
    "葛尾村",
    "飯舘村",
]

MAP_POINTS = {
    "川俣町": (1370, 352),
    "飯舘村": (1518, 330),
    "南相馬市": (1668, 386),
    "田村市": (1422, 574),
    "葛尾村": (1568, 555),
    "浪江町": (1670, 520),
    "双葉町": (1710, 558),
    "大熊町": (1690, 598),
    "富岡町": (1688, 648),
    "川内村": (1540, 664),
    "楢葉町": (1680, 716),
    "広野町": (1680, 784),
}

INDICATOR_GROUPS = {
    "人口・世帯": [
        "current_population",
        "households",
        "evacuees",
    ],
    "人口動態（移動・自然）": [
        "transfer_in",
        "transfer_out",
        "social_change",
        "births",
        "deaths",
        "natural_change",
    ],
    "居住再開・住宅整備": [
        "resident_rate",
        "returnee_housing_planned",
        "returnee_housing_completed",
        "returnee_housing_completion_rate",
    ],
    "公共インフラ・生活機能・産業": [
        "infra_completion_mentions",
        "infra_future_mentions",
        "life_medical_mentions",
        "life_school_mentions",
        "life_commerce_mentions",
        "industry_mentions",
    ],
    "身体的・精神的健康": [
        "suicide_deaths_vital",
        "suicide_rate_vital",
    ],
    "帰還意向": [
        "intention_returned",
        "intention_want_return",
        "intention_undecided",
        "intention_no_return",
        "intention_no_answer",
    ],
}

DEFAULT_INDICATORS = [
    "current_population",
    "households",
    "transfer_in",
    "transfer_out",
    "births",
    "deaths",
    "resident_rate",
    "returnee_housing_completion_rate",
    "infra_completion_mentions",
    "life_medical_mentions",
    "life_school_mentions",
    "life_commerce_mentions",
    "industry_mentions",
    "suicide_deaths_vital",
    "suicide_rate_vital",
    "intention_returned",
    "intention_want_return",
    "intention_no_return",
]

INTENTION_IDS = [
    "intention_returned",
    "intention_want_return",
    "intention_undecided",
    "intention_no_return",
    "intention_no_answer",
]

DYNAMICS_IDS = [
    "transfer_in",
    "transfer_out",
    "births",
    "deaths",
    "social_change",
    "natural_change",
]


st.set_page_config(
    page_title="福島県復興指標ダッシュボード",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
    }
    [data-testid="stSidebar"] {
        min-width: 360px;
    }
    .dashboard-title {
        font-size: 1.85rem;
        font-weight: 800;
        line-height: 1.25;
        margin-bottom: .2rem;
    }
    .dashboard-subtitle {
        color: #52616f;
        font-size: .95rem;
        margin-bottom: 1rem;
    }
    .section-note {
        color: #5c6670;
        font-size: .9rem;
    }
    .icon-heading {
        display: flex;
        align-items: center;
        gap: .55rem;
        margin: 1rem 0 .55rem;
        font-size: 1.06rem;
        font-weight: 800;
        color: #25313b;
    }
    .icon-heading svg,
    .metric-chip svg {
        width: 19px;
        height: 19px;
        stroke: #0f6b7d;
        stroke-width: 2.2;
        fill: none;
        flex: 0 0 auto;
    }
    .metric-row {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .75rem;
        margin: .65rem 0 1rem;
    }
    .metric-chip {
        border: 1px solid #d8dee4;
        border-radius: 8px;
        padding: .72rem .78rem;
        background: #ffffff;
        min-height: 74px;
    }
    .metric-chip-title {
        display: flex;
        align-items: center;
        gap: .42rem;
        color: #52616f;
        font-size: .78rem;
        font-weight: 700;
        margin-bottom: .25rem;
    }
    .metric-chip-value {
        color: #202a33;
        font-size: 1.15rem;
        font-weight: 800;
        line-height: 1.2;
    }
    .metric-chip-sub {
        color: #697581;
        font-size: .74rem;
        margin-top: .2rem;
    }
    .source-card {
        border: 1px solid #d8dee4;
        border-radius: 8px;
        padding: .8rem .9rem;
        margin-bottom: .6rem;
        background: #fff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


ICONS = {
    "map": '<svg viewBox="0 0 24 24"><path d="M9 18l-6 3V6l6-3 6 3 6-3v15l-6 3-6-3z"/><path d="M9 3v15"/><path d="M15 6v15"/></svg>',
    "chart": '<svg viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-7"/></svg>',
    "summary": '<svg viewBox="0 0 24 24"><path d="M4 5h16"/><path d="M4 12h12"/><path d="M4 19h9"/></svg>',
    "table": '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18"/><path d="M9 4v16"/></svg>',
    "source": '<svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.07 0l2.12-2.12a5 5 0 0 0-7.07-7.07L11 4.93"/><path d="M14 11a5 5 0 0 0-7.07 0L4.81 13.12a5 5 0 1 0 7.07 7.07L13 19.07"/></svg>',
    "people": '<svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "home": '<svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8"/><path d="M5 10v11h14V10"/><path d="M9 21v-7h6v7"/></svg>',
    "activity": '<svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 8-6-16-3 8H2"/></svg>',
    "work": '<svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><path d="M2 13h20"/></svg>',
}


def icon_heading(icon: str, text: str) -> None:
    st.markdown(
        f'<div class="icon-heading">{ICONS.get(icon, "")}<span>{text}</span></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_indicator_data(version: str) -> pd.DataFrame:
    if not SNAPSHOT_DATA_PATH.exists():
        raise FileNotFoundError(f"処理済みデータが見つかりません: {SNAPSHOT_DATA_PATH}")

    snapshot = pd.read_csv(SNAPSHOT_DATA_PATH, encoding="utf-8-sig")
    snapshot = snapshot[~snapshot["indicator_id"].isin(HEALTH_INDICATOR_IDS)].copy()
    health = fetch_suicide_health_indicators()
    df = pd.concat([snapshot, health], ignore_index=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["period_dt"] = pd.to_datetime(df["period"], errors="coerce", format="mixed")
    df["period_label"] = df["period_dt"].dt.strftime("%Y-%m-%d")
    df.loc[df["period_label"].isna(), "period_label"] = df["period"].fillna("")
    return df


@st.cache_data(show_spinner=False)
def selected_map_crop(area_name: str) -> bytes | None:
    if area_name not in MAP_POINTS or not MAP_IMAGE_PATH.exists():
        return None
    image = Image.open(MAP_IMAGE_PATH).convert("RGB")
    width, height = image.size
    x, y = MAP_POINTS[area_name]
    crop_w, crop_h = 520, 360
    left = max(0, min(width - crop_w, int(x - crop_w / 2)))
    upper = max(0, min(height - crop_h, int(y - crop_h / 2)))
    crop = image.crop((left, upper, left + crop_w, upper + crop_h))
    output = BytesIO()
    crop.save(output, format="PNG")
    return output.getvalue()


def latest_records(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[df["value"].notna()].copy()
    if valid.empty:
        return valid
    valid["_sort_dt"] = valid["period_dt"].fillna(pd.Timestamp.min)
    idx = valid.sort_values(["indicator_id", "_sort_dt"]).groupby("indicator_id").tail(1).index
    return valid.loc[idx].drop(columns=["_sort_dt"]).sort_values("indicator_name")


def indicator_label_map(df: pd.DataFrame) -> dict[str, str]:
    labels = (
        df[["indicator_id", "indicator_name"]]
        .dropna()
        .drop_duplicates()
        .set_index("indicator_id")["indicator_name"]
        .to_dict()
    )
    return {key: labels.get(key, key) for key in sorted(df["indicator_id"].dropna().unique())}


def sync_query_area(area_options: list[str]) -> None:
    query_area = st.query_params.get("area")
    if isinstance(query_area, list):
        query_area = query_area[0] if query_area else None
    if query_area in area_options:
        st.session_state[AREA_SELECTION_KEY] = query_area


def render_area_map(area_options: list[str], selected_area: str) -> None:
    icon_heading("map", "地図から市町村を選択")
    if not MAP_IMAGE_PATH.exists():
        st.info("地図画像が見つからないため、一覧から選択してください。")
        return

    encoded = base64.b64encode(MAP_IMAGE_PATH.read_bytes()).decode("ascii")
    anchors = []
    for area_name, (x, y) in MAP_POINTS.items():
        if area_name not in area_options:
            continue
        selected_class = " selected" if area_name == selected_area else ""
        anchors.append(
            f'<a class="map-point{selected_class}" href="/?area={quote(area_name)}" '
            f'target="_top" style="left:{x / 18:.3f}%; top:{y / 12:.3f}%;">{area_name}</a>'
        )

    map_col, crop_col = st.columns([1.6, 1], gap="large")
    with map_col:
        components.html(
            f"""
            <div class="map-wrap">
              <img src="data:image/png;base64,{encoded}" alt="福島県市町村地図" />
              {''.join(anchors)}
            </div>
            <style>
            html, body {{
              margin: 0;
              padding: 0;
              background: transparent;
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }}
            .map-wrap {{
              position: relative;
              width: 100%;
              aspect-ratio: 3 / 2;
              overflow: hidden;
              border: 1px solid #d8dee4;
              border-radius: 8px;
              background: #f7f8fa;
            }}
            .map-wrap img {{
              width: 100%;
              height: 100%;
              object-fit: contain;
              display: block;
            }}
            .map-point {{
              position: absolute;
              transform: translate(-50%, -50%);
              padding: 3px 7px;
              border: 1px solid #ffffff;
              border-radius: 999px;
              background: rgba(19, 83, 115, .86);
              color: #fff;
              font-size: 11px;
              font-weight: 700;
              line-height: 1.2;
              text-decoration: none;
              box-shadow: 0 2px 7px rgba(0,0,0,.22);
              white-space: nowrap;
            }}
            .map-point:hover,
            .map-point.selected {{
              background: #d84b36;
            }}
            </style>
            """,
            height=390,
        )
    with crop_col:
        crop = selected_map_crop(selected_area)
        st.markdown(f"**選択中: {selected_area}**")
        if crop:
            st.image(crop, width="stretch")
        st.caption("右の拡大図は地図上の市町村周辺を切り出した暫定表示です。境界だけを正確に抽出する場合は、元PPTXの図形データを市町村単位で分離できるか確認します。")


def render_indicator_selector(df: pd.DataFrame) -> list[str]:
    labels = indicator_label_map(df)
    available = set(df["indicator_id"].dropna().unique())
    selected: list[str] = []
    st.sidebar.markdown("#### 指標カテゴリー")
    for group_name, ids in INDICATOR_GROUPS.items():
        group_ids = [indicator_id for indicator_id in ids if indicator_id in available]
        if not group_ids:
            continue
        default = [indicator_id for indicator_id in group_ids if indicator_id in DEFAULT_INDICATORS]
        with st.sidebar.expander(group_name, expanded=group_name in {"人口・世帯", "人口動態（移動・自然）"}):
            picked_labels = st.multiselect(
                "表示する指標",
                options=[labels[indicator_id] for indicator_id in group_ids],
                default=[labels[indicator_id] for indicator_id in default],
                key=f"{INDICATOR_SELECTION_PREFIX}_{group_name}",
                label_visibility="collapsed",
            )
        inverse = {labels[indicator_id]: indicator_id for indicator_id in group_ids}
        selected.extend(inverse[label] for label in picked_labels)
    return selected


def no_data_message(area_name: str, indicator_ids: list[str], df: pd.DataFrame) -> None:
    labels = indicator_label_map(df)
    missing = [labels.get(indicator_id, indicator_id) for indicator_id in indicator_ids]
    if missing:
        st.caption(f"{area_name}で表示可能なデータがない指標: " + "、".join(missing))


def render_line_chart(data: pd.DataFrame, title: str) -> None:
    fig = px.line(
        data,
        x="period_dt",
        y="value",
        color="indicator_name",
        markers=False,
        labels={"period_dt": "時点", "value": "値", "indicator_name": "指標"},
        title=title,
    )
    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=50, b=10),
        legend_title_text="",
    )
    st.plotly_chart(fig, width="stretch")


def render_latest_bar_chart(data: pd.DataFrame, title: str) -> None:
    if data.empty:
        return
    fig = px.bar(
        data,
        x="indicator_name",
        y="value",
        color="indicator_name",
        text="period_label",
        labels={"indicator_name": "指標", "value": f"値（{data['unit'].iloc[0]}）"},
        title=title,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        height=340,
        margin=dict(l=10, r=10, t=60, b=80),
        showlegend=False,
        xaxis_tickangle=-25,
    )
    st.plotly_chart(fig, width="stretch")


def render_latest_table(area_df: pd.DataFrame) -> None:
    latest = latest_records(area_df)
    if latest.empty:
        st.info("最新値として表示できるデータがありません。")
        return
    view = latest[
        ["category", "indicator_name", "value", "unit", "period_label", "source_name", "notes"]
    ].rename(
        columns={
            "category": "カテゴリー",
            "indicator_name": "指標",
            "value": "最新値",
            "unit": "単位",
            "period_label": "時点",
            "source_name": "出典",
            "notes": "備考",
        }
    )
    st.dataframe(view, width="stretch", hide_index=True)


def render_intention_chart(area_df: pd.DataFrame, selected_ids: list[str]) -> None:
    selected_intentions = [indicator_id for indicator_id in INTENTION_IDS if indicator_id in selected_ids]
    if not selected_intentions:
        return
    data = area_df[
        area_df["indicator_id"].isin(selected_intentions)
        & area_df["value"].notna()
        & area_df["period_dt"].notna()
    ].copy()
    if data.empty:
        no_data_message(area_df["area_name"].iloc[0], selected_intentions, area_df)
        return
    data["year"] = data["period_dt"].dt.year.astype(str)
    fig = px.bar(
        data,
        x="value",
        y="year",
        color="indicator_name",
        orientation="h",
        barmode="stack",
        labels={"value": "割合（%）", "year": "年", "indicator_name": "回答"},
        title="帰還意向の推移",
    )
    fig.update_xaxes(range=[0, 100], ticksuffix="%")
    fig.update_layout(height=max(320, 44 * data["year"].nunique()), margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")


def render_chart_tab(area_df: pd.DataFrame, selected_ids: list[str]) -> None:
    icon_heading("chart", "復興指標グラフ")
    st.markdown('<div class="section-note">時系列データがある指標は折れ線で、時点が限られる指標は同じ単位ごとの最新値として表示します。データがない項目はNO DATAとして扱います。</div>', unsafe_allow_html=True)
    chart_df = area_df[
        area_df["period_dt"].isna() | (area_df["period_dt"] >= CHART_START_DATE)
    ].copy()

    rendered_ids: set[str] = set()
    dynamics = chart_df[
        chart_df["indicator_id"].isin([x for x in DYNAMICS_IDS if x in selected_ids])
        & chart_df["value"].notna()
        & chart_df["period_dt"].notna()
    ].copy()
    if dynamics["period_dt"].nunique() >= 2 and dynamics["indicator_id"].nunique() >= 1:
        render_line_chart(dynamics, "人口移動・自然動態")
        rendered_ids.update(dynamics["indicator_id"].unique())

    render_intention_chart(chart_df, selected_ids)
    rendered_ids.update([indicator_id for indicator_id in INTENTION_IDS if indicator_id in selected_ids])

    handled = set(DYNAMICS_IDS) | set(INTENTION_IDS)
    latest_candidates: list[pd.DataFrame] = []
    for indicator_id in selected_ids:
        if indicator_id in handled:
            continue
        data = chart_df[
            (chart_df["indicator_id"] == indicator_id)
            & chart_df["value"].notna()
            & chart_df["period_dt"].notna()
        ].copy()
        if data["period_dt"].nunique() >= 2:
            render_line_chart(data, data["indicator_name"].iloc[0])
            rendered_ids.add(indicator_id)
        else:
            latest = latest_records(area_df[area_df["indicator_id"] == indicator_id])
            if not latest.empty:
                latest_candidates.append(latest)

    if latest_candidates:
        latest_bars = pd.concat(latest_candidates, ignore_index=True)
        latest_bars = latest_bars[~latest_bars["indicator_id"].isin(rendered_ids)].copy()
        if not latest_bars.empty:
            st.markdown("#### 最新値で確認する指標")
            for (category, unit), unit_df in latest_bars.groupby(["category", "unit"], dropna=False):
                title = f"{category}（{unit}）"
                render_latest_bar_chart(unit_df.sort_values("indicator_name"), title)

    latest_only = area_df[area_df["indicator_id"].isin(selected_ids)].copy()
    latest = latest_records(latest_only)
    if not latest.empty:
        st.markdown("#### 最新値一覧")
        render_latest_table(latest_only)


def summarize_area(area_df: pd.DataFrame, selected_ids: list[str]) -> None:
    icon_heading("summary", "要約")
    latest = latest_records(area_df[area_df["indicator_id"].isin(selected_ids)])
    if latest.empty:
        st.info("要約できるデータがありません。")
        return

    area_name = area_df["area_name"].iloc[0]
    st.markdown(f"### {area_name}の概況")

    by_id = latest.set_index("indicator_id")
    lines: list[str] = []
    for indicator_id in ["current_population", "households", "evacuees", "resident_rate"]:
        if indicator_id in by_id.index:
            row = by_id.loc[indicator_id]
            lines.append(f"{row['indicator_name']}は{row['period_label']}時点で{row['value']:,.1f}{row['unit']}です。")
    if lines:
        st.write(" ".join(lines))

    movement_ids = [x for x in ["transfer_in", "transfer_out", "births", "deaths"] if x in by_id.index]
    if movement_ids:
        text = []
        for indicator_id in movement_ids:
            row = by_id.loc[indicator_id]
            text.append(f"{row['indicator_name']} {row['value']:,.0f}{row['unit']}（{row['period_label']}）")
        st.write("人口動態の最新値は、" + "、".join(text) + "です。")

    health_ids = [x for x in ["suicide_deaths_vital", "suicide_rate_vital"] if x in by_id.index]
    if health_ids:
        text = []
        for indicator_id in health_ids:
            row = by_id.loc[indicator_id]
            text.append(f"{row['indicator_name']} {row['value']:,.1f}{row['unit']}（{row['period_label']}）")
        st.write("身体的・精神的健康に関する確認可能な指標として、" + "、".join(text) + "が表示されています。自殺死亡率は人口規模が小さい年ではNO DATAとして扱っています。")

    st.caption("この要約は現在読み込まれているデータから機械的に作成した暫定コメントです。解釈や因果関係は、出典・調査設計を確認したうえで別途検討してください。")


def render_sources(area_df: pd.DataFrame) -> None:
    icon_heading("source", "出典・取得状況")
    sources = (
        area_df[["category", "indicator_name", "source_type", "source_name", "source_url", "retrieved_at", "collection_method", "notes"]]
        .drop_duplicates()
        .sort_values(["category", "indicator_name"])
    )
    for _, row in sources.iterrows():
        url = row.get("source_url")
        source_line = (
            f'<a href="{url}" target="_blank" rel="noreferrer">{row["source_name"]}</a>'
            if isinstance(url, str) and url.startswith("http")
            else row["source_name"]
        )
        st.markdown(
            f"""
            <div class="source-card">
              <strong>{row['indicator_name']}</strong><br>
              <span>{row['category']} / {row['source_type']} / 取得方法 {row['collection_method']}</span><br>
              <span>出典: {source_line}</span><br>
              <span>取得日時: {row['retrieved_at']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if isinstance(row.get("notes"), str) and row["notes"].strip():
            st.caption(row["notes"])


def render_top_snapshot(area_df: pd.DataFrame) -> None:
    latest = latest_records(area_df)
    if latest.empty:
        return
    by_id = latest.set_index("indicator_id")
    cards = [
        ("people", "現住人口", "current_population"),
        ("home", "居住率", "resident_rate"),
        ("activity", "自殺者数", "suicide_deaths_vital"),
        ("work", "公共インフラ完了記載", "infra_completion_mentions"),
    ]
    parts = ['<div class="metric-row">']
    for icon, title, indicator_id in cards:
        if indicator_id in by_id.index and pd.notna(by_id.loc[indicator_id, "value"]):
            row = by_id.loc[indicator_id]
            value = f'{row["value"]:,.1f}'.rstrip("0").rstrip(".")
            sub = f'{row["period_label"]} / {row["unit"]}'
        else:
            value = "NO DATA"
            sub = ""
        parts.append(
            f"""
            <div class="metric-chip">
              <div class="metric-chip-title">{ICONS.get(icon, "")}<span>{title}</span></div>
              <div class="metric-chip-value">{value}</div>
              <div class="metric-chip-sub">{sub}</div>
            </div>
            """
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def main() -> None:
    df = load_indicator_data(DATA_VERSION)
    area_options = [area for area in AREA_OPTIONS if area in set(df["area_name"])]
    if AREA_SELECTION_KEY not in st.session_state:
        st.session_state[AREA_SELECTION_KEY] = area_options[0]

    sync_query_area(area_options)
    selected_area = st.sidebar.selectbox(
        "市町村（補助選択）",
        options=area_options,
        key=AREA_SELECTION_KEY,
    )
    selected_ids = render_indicator_selector(df)
    if not selected_ids:
        st.warning("表示する指標を1つ以上選択してください。")
        return

    area_df = df[df["area_name"] == selected_area].copy()

    st.markdown('<div class="dashboard-title">福島県復興指標ダッシュボード</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="dashboard-subtitle">{selected_area}の復興関連指標を、公開データ・公的資料から確認できる範囲で表示します。データがない項目はNO DATAとして扱います。</div>',
        unsafe_allow_html=True,
    )
    area_df = df[df["area_name"] == selected_area].copy()
    render_top_snapshot(area_df)
    render_area_map(area_options, selected_area)

    graph_tab, summary_tab, data_tab, source_tab = st.tabs(["復興指標グラフ", "要約", "データ", "出典・取得状況"])
    with graph_tab:
        render_chart_tab(area_df, selected_ids)
    with summary_tab:
        summarize_area(area_df, selected_ids)
    with data_tab:
        icon_heading("table", "データ")
        data = area_df[area_df["indicator_id"].isin(selected_ids)].copy()
        data = data.sort_values(["indicator_name", "period_dt", "period"])
        st.dataframe(
            data[
                [
                    "category",
                    "indicator_name",
                    "area_name",
                    "period_label",
                    "value",
                    "unit",
                    "source_name",
                    "notes",
                ]
            ].rename(
                columns={
                    "category": "カテゴリー",
                    "indicator_name": "指標",
                    "area_name": "市町村",
                    "period_label": "時点",
                    "value": "値",
                    "unit": "単位",
                    "source_name": "出典",
                    "notes": "備考",
                }
            ),
            width="stretch",
            hide_index=True,
        )
    with source_tab:
        render_sources(area_df[area_df["indicator_id"].isin(selected_ids)])


if __name__ == "__main__":
    main()
