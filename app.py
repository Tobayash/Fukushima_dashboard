from __future__ import annotations

import base64
from html import escape
from io import BytesIO
from pathlib import Path
import random
import re
from urllib.parse import quote, urljoin

import requests

from bs4 import BeautifulSoup
import pandas as pd
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from extractors.health import fetch_suicide_health_indicators


APP_DIR = Path(__file__).resolve().parent
SNAPSHOT_DATA_PATH = APP_DIR / "data" / "processed" / "share_master_indicators.csv"
LOCAL_CONTEXT_PATH = APP_DIR / "data" / "processed" / "municipal_context_events.csv"
MAP_IMAGE_PATH = APP_DIR / "data" / "raw" / "fukushima_map_export.png"
MAP_SVG_PATH = APP_DIR / "data" / "raw" / "fukushima-map-municipalities.svg"
DATA_VERSION = "2026-08-04-health-suicide-v5-display1990"
AREA_SELECTION_KEY = "area_select_v1"
INDICATOR_SELECTION_PREFIX = "indicator_select_by_category_v1"
HEALTH_INDICATOR_IDS = {"suicide_deaths_vital", "suicide_rate_vital"}
HEALTH_DUAL_AXIS_IDS = ["suicide_deaths_vital", "suicide_rate_vital"]
CHART_START_DATE = pd.Timestamp("2011-03-11")
DISPLAY_MIN_DATE = pd.Timestamp("1990-01-01")
OFFICIAL_NEWS_URLS = {
    "南相馬市": "https://www.city.minamisoma.lg.jp/news.html",
}

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
    "帰還意向": [
        "intention_returned",
        "intention_want_return",
        "intention_undecided",
        "intention_no_return",
        "intention_no_answer",
    ],
    "身体的・精神的健康": [
        "suicide_deaths_vital",
        "suicide_rate_vital",
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
    "行政・地域の取り組み": [
        "context_event_count",
        "context_report_count",
        "context_initiative_count",
        "context_survey_count",
        "context_topic_count",
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
    "context_event_count",
    "context_initiative_count",
    "context_report_count",
    "intention_returned",
    "intention_want_return",
    "intention_undecided",
    "intention_no_return",
    "intention_no_answer",
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
CHART_GROUPS = [
    ("帰還者向け住宅整備", ["returnee_housing_planned", "returnee_housing_completed"]),
    ("公共インフラ工程表", ["infra_completion_mentions", "infra_future_mentions"]),
    (
        "生活機能・産業関連記載数",
        ["life_medical_mentions", "life_school_mentions", "life_commerce_mentions", "industry_mentions"],
    ),
    (
        "行政・地域の取り組み",
        [
            "context_event_count",
            "context_report_count",
            "context_initiative_count",
            "context_survey_count",
            "context_topic_count",
        ],
    ),
]
CONTEXT_CHART_IDS = [
    "context_event_count",
    "context_report_count",
    "context_initiative_count",
    "context_survey_count",
    "context_topic_count",
]
POPULATION_ESTIMATE_IDS = {"current_population", "households"}
POPULATION_HOUSEHOLD_IDS = ["current_population", "households"]
SUMMARY_GROUP_ICONS = {
    "人口・世帯": "people",
    "人口動態（移動・自然）": "activity",
    "帰還意向": "home",
    "身体的・精神的健康": "heart",
    "居住再開・住宅整備": "home",
    "公共インフラ・生活機能・産業": "work",
    "行政・地域の取り組み": "community",
}


st.set_page_config(
    page_title="福島県復興指標ダッシュボード",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --app-bg: #f7fafb;
        --panel-bg: #ffffff;
        --sidebar-bg: #f0f3f6;
        --text-main: #25313b;
        --text-muted: #5c6670;
        --border: #d8dee4;
        --accent: #0f6b7d;
        --chip-bg: #f8fafb;
    }
    [data-testid="stAppViewContainer"] {
        background: var(--app-bg);
        color: var(--text-main);
    }
    .block-container {
        padding-top: 2.4rem;
        padding-bottom: 2rem;
    }
    [data-testid="stSidebar"] {
        min-width: 360px;
        background: var(--sidebar-bg);
    }
    .dashboard-title {
        font-size: 1.85rem;
        font-weight: 800;
        line-height: 1.4;
        margin: .1rem 0 .25rem;
        padding-top: .15rem;
        padding-bottom: .05rem;
        overflow: visible;
        color: var(--text-main);
    }
    .dashboard-subtitle {
        color: var(--text-muted);
        font-size: .95rem;
        margin-bottom: .35rem;
    }
    .data-updated {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        color: var(--text-muted);
        font-size: .86rem;
        margin: 0 0 1rem;
        padding: .18rem .55rem;
        border: 1px solid var(--border);
        border-radius: 999px;
        background: var(--chip-bg);
    }
    .section-note {
        color: var(--text-muted);
        font-size: .9rem;
        margin-bottom: .8rem;
    }
    .news-card {
        display: block;
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
        background: var(--panel-bg);
        color: inherit;
        text-decoration: none;
        margin: .7rem 0 1rem;
        box-shadow: 0 8px 24px rgba(15, 38, 51, .06);
    }
    .news-card:hover {
        border-color: var(--accent);
        text-decoration: none;
    }
    .news-card-body {
        padding: .9rem 1rem;
    }
    .news-card-title {
        font-weight: 800;
        line-height: 1.45;
        color: var(--text-main);
    }
    .news-card-source {
        color: var(--text-muted);
        font-size: .8rem;
        margin-top: .45rem;
    }
    .icon-heading {
        display: flex;
        align-items: center;
        gap: .55rem;
        margin: 1rem 0 .55rem;
        font-size: 1.06rem;
        font-weight: 800;
        color: var(--text-main);
    }
    .icon-heading svg {
        width: 19px;
        height: 19px;
        stroke: var(--accent);
        stroke-width: 2.2;
        fill: none;
        flex: 0 0 auto;
    }
    .source-card {
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: .8rem .9rem;
        margin-bottom: .6rem;
        background: var(--panel-bg);
    }
    [data-testid="stTabs"] [role="tablist"] {
        gap: .35rem;
    }
    [data-testid="stPlotlyChart"] {
        background: transparent;
        border: 0;
        padding: 0;
        margin: .35rem 0 1.05rem;
        overflow: visible !important;
    }
    [data-testid="stPlotlyChart"] > div {
        background: var(--panel-bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: .35rem;
        overflow: visible !important;
    }
    [data-testid="stPlotlyChart"] iframe {
        overflow: hidden !important;
    }
    [data-testid="stMarkdownContainer"] {
        color: var(--text-main);
    }
    [data-testid="stCaptionContainer"] {
        color: var(--text-muted);
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
    "community": '<svg viewBox="0 0 24 24"><path d="M12 21s7-4.35 7-11a7 7 0 1 0-14 0c0 6.65 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/><path d="M8 18h8"/></svg>',
    "heart": '<svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 1 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78z"/></svg>',
}


def icon_heading(icon: str, text: str) -> None:
    st.markdown(
        f'<div class="icon-heading">{ICONS.get(icon, "")}<span>{text}</span></div>',
        unsafe_allow_html=True,
    )


def apply_dashboard_theme(theme: str) -> None:
    if theme == "dark":
        variables = {
            "app-bg": "#111820",
            "panel-bg": "#18222d",
            "sidebar-bg": "#121a23",
            "text-main": "#eef4f6",
            "text-muted": "#aeb9c2",
            "border": "#324352",
            "accent": "#60c1d4",
            "chip-bg": "#18222d",
        }
    else:
        variables = {
            "app-bg": "#f7fafb",
            "panel-bg": "#ffffff",
            "sidebar-bg": "#f0f3f6",
            "text-main": "#25313b",
            "text-muted": "#5c6670",
            "border": "#d8dee4",
            "accent": "#0f6b7d",
            "chip-bg": "#f8fafb",
        }
    css_vars = "\n".join(f"--{key}: {value};" for key, value in variables.items())
    st.markdown(
        f"""
        <style>
        :root {{
            {css_vars}
        }}
        [data-testid="stHeader"] {{
            background: rgba(0, 0, 0, 0);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def current_theme() -> str:
    return st.session_state.get("dashboard_theme", "light")


def chart_theme_layout() -> dict:
    if current_theme() == "dark":
        return {
            "template": "plotly_dark",
            "paper_bgcolor": "#18222d",
            "plot_bgcolor": "#18222d",
            "font": {"color": "#eef4f6"},
            "legend": {"bgcolor": "rgba(0,0,0,0)"},
        }
    return {
        "template": "plotly_white",
        "paper_bgcolor": "#ffffff",
        "plot_bgcolor": "#ffffff",
        "font": {"color": "#25313b"},
        "legend": {"bgcolor": "rgba(255,255,255,0)"},
    }


def render_plotly_chart(fig: go.Figure) -> None:
    fig.update_layout(**chart_theme_layout())
    current_height = fig.layout.height
    if current_height is None or current_height < 500:
        fig.update_layout(height=500)
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
        ),
        legend_title_text="",
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "responsive": True})


@st.cache_data(show_spinner=False)
def load_indicator_data(version: str) -> pd.DataFrame:
    if not SNAPSHOT_DATA_PATH.exists():
        raise FileNotFoundError(f"処理済みデータが見つかりません: {SNAPSHOT_DATA_PATH}")

    snapshot = pd.read_csv(SNAPSHOT_DATA_PATH, encoding="utf-8-sig")
    snapshot = snapshot[~snapshot["indicator_id"].isin(HEALTH_INDICATOR_IDS)].copy()
    health = fetch_suicide_health_indicators()
    context_indicators = build_context_indicator_rows(load_local_context_events(version))
    df = pd.concat([snapshot, health, context_indicators], ignore_index=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["period_dt"] = pd.to_datetime(df["period"], errors="coerce", format="mixed")
    df["period_label"] = df["period_dt"].dt.strftime("%Y-%m-%d")
    df.loc[df["period_label"].isna(), "period_label"] = df["period"].fillna("")
    df = df[df["period_dt"].isna() | (df["period_dt"] >= DISPLAY_MIN_DATE)].copy()
    return df


def build_context_indicator_rows(events: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "indicator_id",
        "indicator_name",
        "category",
        "concept",
        "area_id",
        "area_name",
        "area_group",
        "period",
        "value",
        "unit",
        "source_type",
        "source_name",
        "source_url",
        "retrieved_at",
        "collection_method",
        "notes",
    ]
    if events.empty or "event_dt" not in events.columns:
        return pd.DataFrame(columns=columns)

    records: list[dict[str, object]] = []
    retrieved_at = pd.Timestamp(LOCAL_CONTEXT_PATH.stat().st_mtime, unit="s", tz="UTC").isoformat() if LOCAL_CONTEXT_PATH.exists() else ""
    indicator_defs = {
        "context_event_count": "確認済み取り組み・近況件数",
        "context_report_count": "報告書・計画更新件数",
        "context_initiative_count": "施策・事業・連携件数",
        "context_survey_count": "調査・検証・視察件数",
        "context_topic_count": "内容区分数",
    }
    for area_name, group in events.dropna(subset=["event_dt"]).sort_values("event_dt").groupby("area_name"):
        group = group.copy()
        text = (
            group["kind"].fillna("")
            + " "
            + group["category"].fillna("")
            + " "
            + group["title"].fillna("")
            + " "
            + group["summary"].fillna("")
        )
        group["_is_report"] = text.str.contains("報告|計画|公表|更新|公告", regex=True)
        group["_is_initiative"] = text.str.contains("施策|事業|連携|支援|活動|行事|再開|整備", regex=True)
        group["_is_survey"] = text.str.contains("調査|検証|視察|測定|アンケート", regex=True)
        for event_dt, date_group in group.groupby("event_dt"):
            upto = group[group["event_dt"] <= event_dt]
            values = {
                "context_event_count": float(len(upto)),
                "context_report_count": float(upto["_is_report"].sum()),
                "context_initiative_count": float(upto["_is_initiative"].sum()),
                "context_survey_count": float(upto["_is_survey"].sum()),
                "context_topic_count": float(upto["category"].dropna().nunique()),
            }
            source_urls = " / ".join(upto["source_url"].dropna().astype(str).unique()[:3])
            for indicator_id, value in values.items():
                records.append(
                    {
                        "indicator_id": indicator_id,
                        "indicator_name": indicator_defs[indicator_id],
                        "category": "行政・地域の取り組み",
                        "concept": "公開資料・ニュースから確認できる取り組みの蓄積",
                        "area_id": "",
                        "area_name": area_name,
                        "area_group": "避難地域12市町村",
                        "period": event_dt.strftime("%Y-%m-%d"),
                        "value": value,
                        "unit": "件",
                        "source_type": "自治体HP・公的資料・報道",
                        "source_name": "確認済み行政・地域取り組みデータ",
                        "source_url": source_urls,
                        "retrieved_at": retrieved_at,
                        "collection_method": "B",
                        "notes": "確認済み出来事データから累積件数として暫定作成。未確認情報は含めない。",
                    }
                )
    return pd.DataFrame(records, columns=columns)


def data_updated_label(df: pd.DataFrame) -> str:
    if "retrieved_at" in df.columns:
        retrieved = pd.to_datetime(df["retrieved_at"], errors="coerce", utc=True).dropna()
        if not retrieved.empty:
            latest = retrieved.max().tz_convert("Asia/Tokyo")
            return f"{latest.year}年{latest.month}月{latest.day}日"

    modified = pd.Timestamp(SNAPSHOT_DATA_PATH.stat().st_mtime, unit="s", tz="Asia/Tokyo")
    return f"{modified.year}年{modified.month}月{modified.day}日"


@st.cache_data(show_spinner=False)
def load_local_context_events(version: str) -> pd.DataFrame:
    columns = [
        "area_name",
        "event_date",
        "kind",
        "category",
        "title",
        "summary",
        "source_name",
        "source_url",
    ]
    if not LOCAL_CONTEXT_PATH.exists():
        return pd.DataFrame(columns=columns + ["event_dt", "event_label"])

    events = pd.read_csv(LOCAL_CONTEXT_PATH, encoding="utf-8-sig")
    for column in columns:
        if column not in events.columns:
            events[column] = ""
    events["event_dt"] = pd.to_datetime(events["event_date"], errors="coerce", format="mixed")
    events["event_label"] = events["event_dt"].dt.strftime("%Y-%m-%d")
    events.loc[events["event_label"].isna(), "event_label"] = events["event_date"].fillna("")
    return events[columns + ["event_dt", "event_label"]]


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


def svg_path_bounds(svg_text: str, area_options: list[str]) -> tuple[tuple[float, float, float, float], dict[str, tuple[float, float]]]:
    target_names = set(area_options)
    all_x: list[float] = []
    all_y: list[float] = []
    label_points: dict[str, tuple[float, float]] = {}
    path_pattern = re.compile(r'<path\b(?=[^>]*data-name="([^"]+)")(?=[^>]*\sd="([^"]+)")[^>]*>', re.S)
    number_pattern = re.compile(r"-?\d+(?:\.\d+)?")

    for match in path_pattern.finditer(svg_text):
        area_name, path_d = match.groups()
        if area_name not in target_names:
            continue
        numbers = [float(value) for value in number_pattern.findall(path_d)]
        xs = numbers[0::2]
        ys = numbers[1::2]
        if not xs or not ys:
            continue
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        all_x.extend([min_x, max_x])
        all_y.extend([min_y, max_y])
        label_points[area_name] = ((min_x + max_x) / 2, (min_y + max_y) / 2)

    if not all_x or not all_y:
        return (5028.6, -6157.9, 5017.1, 4010.5), label_points

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    pad_x = (max_x - min_x) * 0.16
    pad_y = (max_y - min_y) * 0.14
    return (min_x - pad_x, min_y - pad_y, (max_x - min_x) + 2 * pad_x, (max_y - min_y) + 2 * pad_y), label_points


def svg_area_labels(label_points: dict[str, tuple[float, float]], selected_area: str) -> str:
    label_offsets = {
        "南相馬市": (20, -35),
        "飯舘村": (-15, -35),
        "川俣町": (-20, -25),
        "田村市": (-50, 40),
        "葛尾村": (-10, 25),
        "浪江町": (15, -25),
        "双葉町": (45, 0),
        "大熊町": (35, 10),
        "富岡町": (40, 25),
        "楢葉町": (42, 12),
        "広野町": (35, 20),
        "川内村": (-35, 20),
    }
    labels: list[str] = ['<g class="target-labels">']
    for area_name in AREA_OPTIONS:
        if area_name not in label_points:
            continue
        x, y = label_points[area_name]
        dx, dy = label_offsets.get(area_name, (0, 0))
        selected_class = " selected-label" if area_name == selected_area else ""
        labels.append(
            f'<text class="target-label{selected_class}" x="{x + dx:.1f}" y="{y + dy:.1f}">'
            f"{escape(area_name)}</text>"
        )
    labels.append("</g>")
    return "".join(labels)


def mark_svg_target_paths(svg_text: str, area_options: list[str], selected_area: str) -> str:
    target_names = set(area_options)
    path_pattern = re.compile(r'<path\b[^>]*>', re.S)

    def replace_path(match: re.Match[str]) -> str:
        path_tag = match.group(0)
        name_match = re.search(r'data-name="([^"]+)"', path_tag)
        if not name_match:
            return path_tag
        area_name = name_match.group(1)
        if area_name not in target_names:
            return path_tag

        extra_classes = "target-area selected-area" if area_name == selected_area else "target-area"
        if 'class="' in path_tag:
            class_match = re.search(r'class="([^"]*)"', path_tag)
            current_class = class_match.group(1) if class_match else ""
            class_names = [name for name in current_class.split() if name not in {"target-area", "selected-area"}]
            class_names.extend(extra_classes.split())
            path_tag = re.sub(r'class="[^"]*"', f'class="{" ".join(class_names)}"', path_tag, count=1)
        else:
            path_tag = path_tag.replace("<path", f'<path class="{extra_classes}"', 1)

        if "tabindex=" not in path_tag:
            path_tag = path_tag.replace(">", ' tabindex="0">', 1)

        return path_tag

    return path_pattern.sub(replace_path, svg_text)


def style_svg_area_paths(svg_text: str, area_options: list[str], selected_area: str) -> str:
    target_names = set(area_options)
    path_pattern = re.compile(r'<path\b[^>]*>', re.S)

    def replace_attr(tag: str, attr: str, value: str) -> str:
        if re.search(rf'\b{attr}="[^"]*"', tag):
            return re.sub(rf'\b{attr}="[^"]*"', f'{attr}="{value}"', tag, count=1)
        if tag.endswith("/>"):
            return tag[:-2] + f' {attr}="{value}"/>'
        return tag.replace(">", f' {attr}="{value}">', 1)

    def replace_path(match: re.Match[str]) -> str:
        path_tag = match.group(0)
        name_match = re.search(r'data-name="([^"]+)"', path_tag)
        if not name_match:
            return path_tag
        area_name = name_match.group(1)
        if area_name == selected_area:
            path_tag = replace_attr(path_tag, "fill", "#d65f45")
            path_tag = replace_attr(path_tag, "stroke", "#1f2a30")
            path_tag = replace_attr(path_tag, "stroke-width", "20")
            path_tag = replace_attr(path_tag, "opacity", "1")
        elif area_name in target_names:
            path_tag = replace_attr(path_tag, "fill", "#8fc8b5")
            path_tag = replace_attr(path_tag, "stroke", "#ffffff")
            path_tag = replace_attr(path_tag, "stroke-width", "14")
            path_tag = replace_attr(path_tag, "opacity", "1")
        else:
            path_tag = replace_attr(path_tag, "fill", "#e8ece7")
            path_tag = replace_attr(path_tag, "stroke", "#ffffff")
            path_tag = replace_attr(path_tag, "stroke-width", "10")
            path_tag = replace_attr(path_tag, "opacity", ".62")
        return path_tag

    return path_pattern.sub(replace_path, svg_text)


def link_svg_area_paths(svg_text: str, area_options: list[str]) -> str:
    target_names = set(area_options)
    path_pattern = re.compile(r'<path\b[^>]*>', re.S)

    def replace_path(match: re.Match[str]) -> str:
        path_tag = match.group(0)
        name_match = re.search(r'data-name="([^"]+)"', path_tag)
        if not name_match:
            return path_tag
        area_name = name_match.group(1)
        if area_name not in target_names:
            return path_tag
        href = f"?area={quote(area_name)}"
        label = escape(f"{area_name}を表示")
        return (
            f'<a class="svg-area-link" href="{href}" xlink:href="{href}" target="_top" '
            f'aria-label="{label}" title="{escape(area_name)}">{path_tag}</a>'
        )

    return path_pattern.sub(replace_path, svg_text)


def html_area_label_links(
    label_points: dict[str, tuple[float, float]],
    view_box: tuple[float, float, float, float],
    selected_area: str,
) -> str:
    view_x, view_y, view_w, view_h = view_box
    label_offsets = {
        "南相馬市": (20, -35),
        "飯舘村": (-15, -35),
        "川俣町": (-20, -25),
        "田村市": (-50, 40),
        "葛尾村": (-10, 25),
        "浪江町": (15, -25),
        "双葉町": (45, 0),
        "大熊町": (35, 10),
        "富岡町": (40, 25),
        "楢葉町": (42, 12),
        "広野町": (35, 20),
        "川内村": (-35, 20),
    }
    links = ['<div class="map-label-layer">']
    for area_name in AREA_OPTIONS:
        if area_name not in label_points:
            continue
        x, y = label_points[area_name]
        dx, dy = label_offsets.get(area_name, (0, 0))
        left = ((x + dx - view_x) / view_w) * 100
        top = ((y + dy - view_y) / view_h) * 100
        selected_class = " selected-label-link" if area_name == selected_area else ""
        hit_width = 3.35 if len(area_name) <= 3 else len(area_name) * 1.18
        links.append(
            f'<a class="map-label-link{selected_class}" href="?area={quote(area_name)}" target="_self" '
            f'title="{escape(area_name)}" aria-label="{escape(area_name)}を表示" '
            f'style="left:{left:.3f}%; top:{top:.3f}%; width:{hit_width:.2f}em;"></a>'
        )
    links.append("</div>")
    return "".join(links)


def html_area_chips(area_options: list[str], selected_area: str) -> str:
    chips = ['<div class="map-chip-row">']
    for area_name in area_options:
        selected_class = " selected-map-chip" if area_name == selected_area else ""
        chips.append(
            f'<a class="map-chip{selected_class}" href="?area={quote(area_name)}" target="_self">'
            f"{escape(area_name)}</a>"
        )
    chips.append("</div>")
    return "".join(chips)


def svg_area_style_rules(area_options: list[str], selected_area: str) -> str:
    target_selectors = ",\n    ".join(
        f'.svg-map path[data-name="{area_name}"]' for area_name in area_options
    )
    selected_selector = f'.svg-map path[data-name="{selected_area}"]'
    return f"""
    {target_selectors} {{
      fill: #8fc8b5;
      stroke: #ffffff;
      stroke-width: 14;
      opacity: 1;
    }}
    {target_selectors}:hover {{
      fill: #48a084;
      stroke: #284b43;
    }}
    {selected_selector} {{
      fill: #d65f45;
      stroke: #1f2a30;
      stroke-width: 20;
      opacity: 1;
    }}
    """


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
    if MAP_SVG_PATH.exists():
        render_svg_area_map(area_options, selected_area)
        return

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


def render_svg_area_map(area_options: list[str], selected_area: str) -> None:
    svg_text = MAP_SVG_PATH.read_text(encoding="utf-8")
    svg_text = svg_text.replace('<?xml version="1.0" standalone="no"?>', "")
    if "xmlns:xlink" not in svg_text:
        svg_text = svg_text.replace("<svg ", '<svg xmlns:xlink="http://www.w3.org/1999/xlink" ', 1)
    view_box, label_points = svg_path_bounds(svg_text, area_options)
    view_x, view_y, view_w, view_h = view_box
    map_aspect_ratio = max(view_w / view_h, 0.1)
    svg_labels = svg_area_labels(label_points, selected_area)
    svg_text = re.sub(
        r'viewBox="[^"]+"',
        f'viewBox="{view_x:.1f} {view_y:.1f} {view_w:.1f} {view_h:.1f}"',
        svg_text,
        count=1,
    )
    svg_text = re.sub(r'\swidth="[^"]+"\sheight="[^"]+"', ' width="100%" height="auto"', svg_text, count=1)
    svg_text = style_svg_area_paths(svg_text, area_options, selected_area)
    svg_text = link_svg_area_paths(svg_text, area_options)
    svg_text = svg_text.replace("</svg>", f"{svg_labels}</svg>", 1)
    label_links = html_area_label_links(label_points, view_box, selected_area)
    map_html = f"""
    <div class="svg-map-shell">
      <div class="svg-map">
        {svg_text}
        {label_links}
      </div>
      <div class="svg-map-caption">
        <span class="selected-dot"></span>
        <strong>{selected_area}</strong>
        <span>対象12市町村を拡大表示しています。市町村の切り替えは左側の補助選択から行えます。</span>
      </div>
    </div>
    <style>
    html, body {{
      margin: 0;
      padding: 0;
      background: transparent;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .svg-map-shell {{
      border: 1px solid #d8dee4;
      border-radius: 8px;
      background: #f8fafb;
      padding: 12px;
    }}
    .svg-map {{
      position: relative;
      width: 100%;
      aspect-ratio: {map_aspect_ratio:.4f};
      max-height: min(68vh, 620px);
      overflow: visible;
      border-radius: 6px;
      background: linear-gradient(180deg, #fafdff 0%, #edf5f2 100%);
    }}
    .svg-map svg {{
      width: 100%;
      height: auto;
      max-height: min(68vh, 620px);
      display: block;
      margin: 0 auto;
    }}
    .svg-map path.pref-path {{
      transition: fill .15s ease, stroke .15s ease, opacity .15s ease;
    }}
    .map-label-layer {{
      position: absolute;
      left: 23.825%;
      top: 0;
      width: 52.381%;
      height: 100%;
      z-index: 3;
      pointer-events: none;
    }}
    .map-label-link {{
      position: absolute;
      transform: translate(-50%, -73%);
      display: block;
      height: 1.65em;
      border-radius: 999px;
      color: transparent;
      text-decoration: none;
      pointer-events: auto;
      overflow: hidden;
      background: transparent;
      outline: none;
    }}
    .map-label-link:hover,
    .map-label-link:focus {{
      background: transparent;
      outline: none;
    }}
    .svg-area-link {{
      cursor: pointer;
      outline: none;
    }}
    .svg-area-link:focus path.pref-path {{
      stroke: #284b43;
      stroke-width: 24;
    }}
    .target-label {{
      font-size: 78px;
      font-weight: 800;
      fill: #26343c;
      stroke: rgba(255, 255, 255, .95);
      stroke-width: 12px;
      paint-order: stroke;
      text-anchor: middle;
    }}
    .target-label.selected-label {{
      fill: #9f321f;
      font-size: 88px;
    }}
    .svg-map-caption {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 9px;
      color: #4f5f68;
      font-size: 13px;
    }}
    .svg-map-caption strong {{
      color: #26343c;
      white-space: nowrap;
    }}
    .selected-dot {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: #d65f45;
      border: 1px solid #1f2a30;
      display: inline-block;
    }}
    </style>
    """
    st.markdown(map_html, unsafe_allow_html=True)


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
        with st.sidebar.expander(group_name, expanded=group_name in {"人口・世帯", "人口動態（移動・自然）", "行政・地域の取り組み"}):
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


def value_axis_label(data: pd.DataFrame, title: str | None = None) -> str:
    names = [name for name in data["indicator_name"].dropna().astype(str).unique() if name]
    units = [unit for unit in data["unit"].dropna().astype(str).unique() if unit]
    measure = title or "値"
    if len(names) == 1:
        measure = names[0]
    if len(units) == 1:
        return f"{measure}（{units[0]}）"
    if len(units) > 1:
        return f"{measure}（単位混在）"
    return measure


def time_position_note(data: pd.DataFrame) -> str | None:
    periods = data["period"].dropna().astype(str)
    if periods.empty:
        return None

    notes: list[str] = []
    if periods.str.fullmatch(r"\d{4}-\d{2}").any():
        notes.append("年月のみのデータは、グラフ上では当該月の1日位置に配置しています。")
    if periods.str.fullmatch(r"\d{4}").any():
        notes.append("年のみのデータは、年単位の値として扱っています。")
    if periods.str.fullmatch(r"\d{4}-\d{2}-\d{2}").any():
        notes.append("年月日まであるデータは、その日付位置に配置しています。")
    return " ".join(notes) if notes else None


def population_estimate_note(data: pd.DataFrame) -> str | None:
    estimate_data = data[data["indicator_id"].isin(POPULATION_ESTIMATE_IDS)].copy()
    if estimate_data.empty:
        return None

    changes: list[str] = []
    for indicator_name, group in estimate_data.groupby("indicator_name"):
        group = group.dropna(subset=["value", "period_dt"]).sort_values("period_dt").copy()
        if len(group) < 2:
            continue
        group["previous_value"] = group["value"].shift(1)
        group["previous_period"] = group["period_label"].shift(1)
        denominator = group["previous_value"].abs().replace(0, pd.NA)
        group["change_rate"] = (group["value"] - group["previous_value"]).abs() / denominator
        flagged = group[(group["previous_value"].notna()) & (group["change_rate"] >= 0.05)].head(2)
        for _, row in flagged.iterrows():
            changes.append(f"{indicator_name}: {row['previous_period']}→{row['period_label']}")

    base_note = (
        "現住人口・世帯数は福島県現住人口調査の公開データに基づく推計値で、"
        "国勢調査を基準に補正されるため、国勢調査年や推計方法の切替付近で段差が見える場合があります。"
    )
    if changes:
        return base_note + " 表示範囲では " + "、".join(changes[:4]) + " に比較的大きな変化があります。"
    return base_note


def render_line_chart(data: pd.DataFrame, title: str) -> None:
    y_label = value_axis_label(data, title)
    fig = px.line(
        data,
        x="period_dt",
        y="value",
        color="indicator_name",
        markers=False,
        labels={"period_dt": "時点", "value": y_label, "indicator_name": "指標"},
        hover_data={"period_label": True, "unit": True, "period_dt": False},
        title=title,
    )
    fig.update_yaxes(title_text=y_label)
    valid_dates = data["period_dt"].dropna()
    if not valid_dates.empty:
        fig.update_xaxes(title_text="時点", range=[valid_dates.min(), valid_dates.max()])
    else:
        fig.update_xaxes(title_text="時点")
    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=54, b=95),
        legend_title_text="",
    )
    render_plotly_chart(fig)
    notes = [note for note in [population_estimate_note(data), time_position_note(data)] if note]
    if notes:
        st.caption(" ".join(notes))


FLOW_INDICATOR_IDS = set(DYNAMICS_IDS)


def annualize_indicator_data(data: pd.DataFrame, flow_ids: set[str] | None = None) -> pd.DataFrame:
    flow_ids = flow_ids or set()
    valid = data[data["value"].notna() & data["period_dt"].notna()].copy()
    if valid.empty:
        return data.copy()

    meta_columns = [
        "area_code",
        "area_name",
        "category",
        "indicator_id",
        "indicator_name",
        "unit",
        "source_type",
        "source_name",
        "source_url",
        "retrieved_at",
        "collection_method",
        "notes",
    ]
    meta_columns = [column for column in meta_columns if column in valid.columns]
    valid["_year"] = valid["period_dt"].dt.year

    yearly_rows: list[pd.Series] = []
    for (indicator_id, year), group in valid.sort_values("period_dt").groupby(["indicator_id", "_year"]):
        group = group.copy()
        if indicator_id in flow_ids:
            row = group.iloc[-1].copy()
            row["value"] = group["value"].sum()
            row["period"] = str(year)
            row["period_dt"] = pd.Timestamp(year=int(year), month=12, day=31)
            row["period_label"] = f"{int(year)}年"
        else:
            if indicator_id in POPULATION_HOUSEHOLD_IDS and int(year) % 5 == 0:
                census_group = group[group["period_dt"].dt.month.eq(10)]
                row = (census_group.iloc[-1] if not census_group.empty else group.iloc[-1]).copy()
            else:
                row = group.iloc[-1].copy()
            row["period"] = str(year)
            row["period_label"] = f"{int(year)}年"
        yearly_rows.append(row[meta_columns + ["period", "period_dt", "period_label", "value"]])

    return pd.DataFrame(yearly_rows).reset_index(drop=True)


def apply_time_grain(data: pd.DataFrame, grain: str, flow_ids: set[str] | None = None) -> pd.DataFrame:
    if grain == "year":
        return annualize_indicator_data(data, flow_ids=flow_ids)
    return data.copy()


def grain_label(grain: str) -> str:
    return "年単位" if grain == "year" else "月単位"


def get_time_grain(key: str) -> str:
    state_key = f"{key}_grain"
    if state_key not in st.session_state:
        st.session_state[state_key] = "year"
    return st.session_state[state_key]


def render_time_grain_buttons(key: str) -> None:
    state_key = f"{key}_grain"
    current = get_time_grain(key)
    col_year, col_month, _ = st.columns([1, 1, 4])
    with col_year:
        if st.button(
            "年単位",
            key=f"{key}_year_button",
            type="primary" if current == "year" else "secondary",
            width="stretch",
        ):
            st.session_state[state_key] = "year"
            st.rerun()
    with col_month:
        if st.button(
            "月単位",
            key=f"{key}_month_button",
            type="primary" if current == "month" else "secondary",
            width="stretch",
        ):
            st.session_state[state_key] = "month"
            st.rerun()


def census_jump_segments(group: pd.DataFrame, threshold: float = 0.05) -> set[int]:
    ordered = group.dropna(subset=["value", "period_dt"]).sort_values("period_dt").copy()
    if len(ordered) < 2:
        return set()
    ordered["previous_value"] = ordered["value"].shift(1)
    denominator = ordered["previous_value"].abs().replace(0, pd.NA)
    ordered["change_rate"] = (ordered["value"] - ordered["previous_value"]).abs() / denominator
    flagged = ordered[
        ordered["previous_value"].notna()
        & (ordered["change_rate"] >= threshold)
        & ordered["period_dt"].dt.month.eq(10)
        & ordered["period_dt"].dt.year.mod(5).eq(0)
    ]
    return set(flagged.index)


def render_population_household_chart(data: pd.DataFrame, mark_all_census_segments: bool = False) -> None:
    plot_data = data[
        data["indicator_id"].isin(POPULATION_HOUSEHOLD_IDS)
        & data["value"].notna()
        & data["period_dt"].notna()
    ].copy()
    if plot_data.empty:
        return

    fig = go.Figure()
    colors = {"current_population": "#0f6b7d", "households": "#d95f43"}
    axes = {"current_population": "y", "households": "y2"}
    names = {"current_population": "現住人口", "households": "世帯数"}
    jump_notes: list[str] = []

    for indicator_id in POPULATION_HOUSEHOLD_IDS:
        group = plot_data[plot_data["indicator_id"] == indicator_id].sort_values("period_dt").copy()
        if group.empty:
            continue
        jump_idx = census_jump_segments(group, threshold=0 if mark_all_census_segments else 0.05)
        if jump_idx:
            for idx in jump_idx:
                row_position = group.index.get_loc(idx)
                if row_position > 0:
                    previous = group.iloc[row_position - 1]
                    current = group.loc[idx]
                    jump_notes.append(f"{names[indicator_id]}: {previous['period_label']}→{current['period_label']}")

        solid_x: list[pd.Timestamp | None] = []
        solid_y: list[float | None] = []
        rows = list(group.itertuples())
        for i, row in enumerate(rows):
            if i > 0 and row.Index in jump_idx:
                solid_x.append(None)
                solid_y.append(None)
            solid_x.append(row.period_dt)
            solid_y.append(row.value)

        fig.add_trace(
            go.Scatter(
                x=solid_x,
                y=solid_y,
                mode="lines",
                name=names[indicator_id],
                line=dict(color=colors[indicator_id], width=2.4),
                yaxis=axes[indicator_id],
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f}<extra>" + names[indicator_id] + "</extra>",
            )
        )

        for idx in jump_idx:
            row_position = group.index.get_loc(idx)
            if row_position == 0:
                continue
            previous = group.iloc[row_position - 1]
            current = group.loc[idx]
            fig.add_trace(
                go.Scatter(
                    x=[previous["period_dt"], current["period_dt"]],
                    y=[previous["value"], current["value"]],
                    mode="lines",
                    name=f"{names[indicator_id]}（国勢調査年補正付近）",
                    line=dict(color=colors[indicator_id], width=2.4, dash="dot"),
                    yaxis=axes[indicator_id],
                    showlegend=False,
                    hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f}<extra>" + names[indicator_id] + "</extra>",
                )
            )

    valid_dates = plot_data["period_dt"].dropna()
    if not valid_dates.empty:
        fig.update_xaxes(title_text="時点", range=[valid_dates.min(), valid_dates.max()])
    fig.update_layout(
        title="現住人口・世帯数",
        height=430,
        margin=dict(l=10, r=10, t=54, b=95),
        legend_title_text="",
        yaxis=dict(title="現住人口（人）"),
        yaxis2=dict(title="世帯数（世帯）", overlaying="y", side="right", showgrid=False),
    )
    render_plotly_chart(fig)
    note = population_estimate_note(plot_data)
    if jump_notes:
        if mark_all_census_segments:
            note = (note or "") + " 年単位データでは、点線は国勢調査年付近の補正・基準更新区間を示します。"
        else:
            note = (note or "") + " 点線は国勢調査年付近の比較的大きな段差を示します。"
    if note:
        st.caption(note)


def render_suicide_health_chart(data: pd.DataFrame) -> None:
    plot_data = data[
        data["indicator_id"].isin(HEALTH_DUAL_AXIS_IDS)
        & data["value"].notna()
        & data["period_dt"].notna()
    ].copy()
    if plot_data.empty:
        return

    fig = go.Figure()
    config = {
        "suicide_deaths_vital": {
            "name": "自殺者数",
            "axis": "y",
            "color": "#6b7280",
            "title": "自殺者数（人）",
        },
        "suicide_rate_vital": {
            "name": "自殺死亡率",
            "axis": "y2",
            "color": "#b84a62",
            "title": "自殺死亡率（人口10万対）",
        },
    }
    for indicator_id, item in config.items():
        group = plot_data[plot_data["indicator_id"] == indicator_id].sort_values("period_dt").copy()
        if group.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=group["period_dt"],
                y=group["value"],
                mode="lines",
                name=item["name"],
                line=dict(color=item["color"], width=2.4),
                yaxis=item["axis"],
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.1f}<extra>" + item["name"] + "</extra>",
            )
        )

    valid_dates = plot_data["period_dt"].dropna()
    if not valid_dates.empty:
        fig.update_xaxes(title_text="時点", range=[valid_dates.min(), valid_dates.max()])
    fig.update_layout(
        title="自殺者数・自殺死亡率",
        height=430,
        margin=dict(l=10, r=10, t=54, b=95),
        legend_title_text="",
        yaxis=dict(title=config["suicide_deaths_vital"]["title"]),
        yaxis2=dict(title=config["suicide_rate_vital"]["title"], overlaying="y", side="right", showgrid=False),
    )
    render_plotly_chart(fig)
    st.caption("自殺死亡率は人口規模が小さい年ではNO DATAとして扱っています。単年度だけでなく、複数年の傾向として確認してください。")


def render_latest_bar_chart(data: pd.DataFrame, title: str) -> None:
    if data.empty:
        return
    y_label = value_axis_label(data, title)
    fig = px.bar(
        data,
        x="indicator_name",
        y="value",
        color="indicator_name",
        text="period_label",
        labels={"indicator_name": "指標", "value": y_label},
        title=title,
    )
    fig.update_yaxes(title_text=y_label)
    fig.update_xaxes(title_text="指標")
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=54, b=105),
        showlegend=False,
        xaxis_tickangle=-25,
    )
    render_plotly_chart(fig)


def indicator_order_map() -> dict[str, int]:
    order: dict[str, int] = {}
    for group_ids in INDICATOR_GROUPS.values():
        for indicator_id in group_ids:
            if indicator_id not in order:
                order[indicator_id] = len(order)
    return order


def sort_by_graph_order(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data.copy()
    ordered = data.copy()
    order = indicator_order_map()
    ordered["_indicator_order"] = ordered["indicator_id"].map(order).fillna(len(order)).astype(int)
    ordered["_period_sort"] = ordered["period_dt"].fillna(pd.Timestamp.max)
    return ordered.sort_values(["_indicator_order", "_period_sort", "period", "indicator_name"]).drop(
        columns=["_indicator_order", "_period_sort"], errors="ignore"
    )


def filter_data_table(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data.copy()

    filtered = data.copy()
    col_category, col_indicator, col_period = st.columns([1.1, 1.4, 1])
    with col_category:
        categories = list(dict.fromkeys(sort_by_graph_order(filtered)["category"].dropna().astype(str)))
        selected_categories = st.multiselect(
            "カテゴリーで絞り込み",
            options=categories,
            default=categories,
            key="data_filter_categories",
        )
    if not selected_categories:
        st.caption(f"表示中: 0件 / 全{len(data):,}件")
        return filtered.iloc[0:0].copy()
    filtered = filtered[filtered["category"].astype(str).isin(selected_categories)].copy()

    with col_indicator:
        indicator_labels = list(dict.fromkeys(sort_by_graph_order(filtered)["indicator_name"].dropna().astype(str)))
        selected_indicators = st.multiselect(
            "指標で絞り込み",
            options=indicator_labels,
            default=indicator_labels,
            key="data_filter_indicators",
        )
    if not selected_indicators:
        st.caption(f"表示中: 0件 / 全{len(data):,}件")
        return filtered.iloc[0:0].copy()
    filtered = filtered[filtered["indicator_name"].astype(str).isin(selected_indicators)].copy()

    with col_period:
        keyword = st.text_input(
            "時点・出典・備考を検索",
            value="",
            key="data_filter_keyword",
            placeholder="例: 2020 / 福島県",
        ).strip()
    if keyword:
        searchable = (
            filtered["period_label"].fillna("").astype(str)
            + " "
            + filtered["source_name"].fillna("").astype(str)
            + " "
            + filtered["notes"].fillna("").astype(str)
        )
        filtered = filtered[searchable.str.contains(re.escape(keyword), case=False, na=False)].copy()

    st.caption(f"表示中: {len(filtered):,}件 / 全{len(data):,}件")
    return filtered


def render_latest_table(area_df: pd.DataFrame) -> None:
    latest = sort_by_graph_order(latest_records(area_df))
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


def date_range_slider(area_df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    valid_dates = area_df["period_dt"].dropna()
    if valid_dates.empty:
        return CHART_START_DATE, pd.Timestamp.now()

    min_date = max(valid_dates.min(), DISPLAY_MIN_DATE)
    max_date = valid_dates.max()
    if max_date <= min_date:
        return min_date, max_date
    default_start = CHART_START_DATE if min_date <= CHART_START_DATE <= max_date else min_date

    st.sidebar.markdown("#### 表示期間")
    start, end = st.sidebar.slider(
        "表示期間",
        min_value=min_date.to_pydatetime(),
        max_value=max_date.to_pydatetime(),
        value=(default_start.to_pydatetime(), max_date.to_pydatetime()),
        format="YYYY/MM",
        help="1990年1月以降から選択できます。デフォルトの開始時点だけ2011年3月11日にしています。",
        label_visibility="collapsed",
    )
    return pd.Timestamp(start), pd.Timestamp(end)


def local_context_for_area(area_name: str) -> pd.DataFrame:
    events = load_local_context_events(DATA_VERSION)
    if events.empty:
        return events
    return events[events["area_name"] == area_name].sort_values("event_dt", ascending=False).copy()


def render_local_context_events(area_name: str) -> None:
    st.markdown(
        '<div class="section-note">'
        '公開資料・公的機関・報道等から確認できた取り組みや近況を、復興指標の背景情報として表示します。'
        '確認できない市町村・項目はDATAなしとして扱います。'
        '</div>',
        unsafe_allow_html=True,
    )
    events = local_context_for_area(area_name)
    if events.empty:
        st.info(f"{area_name}について、確認済みの行政・地域の取り組み・近況データはまだありません。DATAなしとして扱います。")
        return

    timeline = events[events["event_dt"].notna()].sort_values("event_dt").copy()
    if timeline["event_dt"].nunique() >= 2:
        fig = px.scatter(
            timeline,
            x="event_dt",
            y="category",
            color="kind",
            hover_name="title",
            hover_data={"summary": True, "event_label": True, "event_dt": False},
            labels={"event_dt": "時点", "category": "内容区分", "kind": "種別"},
            title="確認済みの取り組み・近況",
        )
        fig.update_xaxes(title_text="時点")
        fig.update_yaxes(title_text="内容区分")
        fig.update_layout(height=max(280, 58 * timeline["category"].nunique()), margin=dict(l=10, r=10, t=50, b=10))
        render_plotly_chart(fig)

    view = events[
        ["event_label", "kind", "category", "title", "summary", "source_name", "source_url"]
    ].rename(
        columns={
            "event_label": "時点",
            "kind": "種別",
            "category": "内容区分",
            "title": "項目",
            "summary": "概要",
            "source_name": "出典",
            "source_url": "URL",
        }
    )
    st.dataframe(view, width="stretch", hide_index=True)


def render_context_section(area_df: pd.DataFrame, selected_ids: list[str], date_range: tuple[pd.Timestamp, pd.Timestamp]) -> None:
    active_ids = [indicator_id for indicator_id in CONTEXT_CHART_IDS if indicator_id in selected_ids]
    if not active_ids:
        return
    icon_heading("community", "行政・地域の取り組み")
    start_date, end_date = date_range
    data = area_df[
        area_df["indicator_id"].isin(active_ids)
        & area_df["value"].notna()
        & area_df["period_dt"].notna()
        & (area_df["period_dt"] >= start_date)
        & (area_df["period_dt"] <= end_date)
    ].copy()
    if data["period_dt"].nunique() >= 2:
        render_line_chart(data, "行政・地域の取り組み")
    else:
        latest = latest_records(data)
        if not latest.empty:
            render_latest_bar_chart(latest, "行政・地域の取り組み")
    render_local_context_events(area_df["area_name"].iloc[0])


def format_summary_value(value: float, unit: str) -> str:
    if pd.isna(value):
        return "NO DATA"
    if unit in {"人", "世帯", "戸", "件"}:
        return f"{value:,.0f}{unit}"
    if unit == "%":
        return f"{value:,.1f}%"
    return f"{value:,.1f}{unit}"


def trend_word(diff: float, unit: str) -> str:
    threshold = 0.1 if unit == "%" else 1.0
    if abs(diff) < threshold:
        return "おおむね横ばい"
    return "増加" if diff > 0 else "減少"


def build_trend_summary(area_df: pd.DataFrame, selected_ids: list[str], limit: int = 5) -> list[str]:
    candidates = area_df[
        area_df["indicator_id"].isin(selected_ids)
        & area_df["value"].notna()
        & area_df["period_dt"].notna()
        & (area_df["period_dt"] >= CHART_START_DATE)
    ].copy()
    if candidates.empty:
        return []

    summaries: list[tuple[pd.Timestamp, str]] = []
    for _, group in candidates.sort_values(["indicator_name", "period_dt"]).groupby("indicator_id"):
        if group["period_dt"].nunique() < 2:
            continue
        first = group.iloc[0]
        latest = group.iloc[-1]
        unit = str(latest.get("unit", ""))
        diff = latest["value"] - first["value"]
        sentence = (
            f"{latest['indicator_name']}は、確認できる初期値（{first['period_label']}："
            f"{format_summary_value(first['value'], unit)}）から最新値（{latest['period_label']}："
            f"{format_summary_value(latest['value'], unit)}）にかけて{trend_word(diff, unit)}しています。"
        )
        summaries.append((latest["period_dt"], sentence))

    return [sentence for _, sentence in sorted(summaries, key=lambda item: item[0], reverse=True)[:limit]]


def trend_records(area_df: pd.DataFrame, selected_ids: list[str]) -> list[dict[str, object]]:
    candidates = area_df[
        area_df["indicator_id"].isin(selected_ids)
        & area_df["value"].notna()
        & area_df["period_dt"].notna()
        & (area_df["period_dt"] >= CHART_START_DATE)
    ].copy()
    if candidates.empty:
        return []

    records: list[dict[str, object]] = []
    for _, group in candidates.sort_values(["indicator_name", "period_dt"]).groupby("indicator_id"):
        if group["period_dt"].nunique() < 2:
            continue
        first = group.iloc[0]
        latest = group.iloc[-1]
        diff = latest["value"] - first["value"]
        denominator = abs(first["value"]) if first["value"] else pd.NA
        rel_change = abs(diff) / denominator if pd.notna(denominator) and denominator != 0 else abs(diff)

        step_group = group.copy()
        step_group["previous_value"] = step_group["value"].shift(1)
        step_group["previous_period_dt"] = step_group["period_dt"].shift(1)
        step_group["previous_period_label"] = step_group["period_label"].shift(1)
        step_group["step_diff"] = step_group["value"] - step_group["previous_value"]
        step_group["step_score"] = step_group["step_diff"].abs()
        if step_group["previous_value"].abs().max() > 0:
            step_group["step_score"] = step_group["step_score"] / step_group["previous_value"].abs().replace(0, pd.NA)
        step_group = step_group[step_group["previous_value"].notna() & step_group["step_score"].notna()]
        change_row = step_group.sort_values("step_score", ascending=False).head(1)
        if change_row.empty:
            change_dt = latest["period_dt"]
            change_label = latest["period_label"]
        else:
            change_dt = change_row.iloc[0]["period_dt"]
            change_label = change_row.iloc[0]["period_label"]

        records.append(
            {
                "indicator_name": latest["indicator_name"],
                "unit": str(latest.get("unit", "")),
                "first_label": first["period_label"],
                "first_value": first["value"],
                "latest_label": latest["period_label"],
                "latest_value": latest["value"],
                "direction": trend_word(diff, str(latest.get("unit", ""))),
                "score": float(rel_change) if pd.notna(rel_change) else 0.0,
                "change_dt": change_dt,
                "change_label": change_label,
            }
        )
    return sorted(records, key=lambda record: record["score"], reverse=True)


def event_near_change(context_events: pd.DataFrame, change_dt: object, days: int = 180) -> pd.Series | None:
    if context_events.empty or pd.isna(change_dt):
        return None
    events = context_events[context_events["event_dt"].notna()].copy()
    if events.empty:
        return None
    target = pd.Timestamp(change_dt)
    events["_distance"] = (events["event_dt"] - target).abs()
    nearby = events[events["_distance"] <= pd.Timedelta(days=days)].sort_values("_distance")
    if nearby.empty:
        return None
    return nearby.iloc[0]


def latest_category_sentence(group_latest: pd.DataFrame) -> str:
    parts = []
    for _, row in group_latest.sort_values("indicator_name").head(4).iterrows():
        parts.append(f"{row['indicator_name']}は{row['period_label']}時点で{format_summary_value(row['value'], str(row['unit']))}")
    if not parts:
        return ""
    return "最新値では、" + "、".join(parts) + "です。"


def natural_summary_paragraph(group_latest: pd.DataFrame, records: list[dict[str, object]]) -> str:
    latest_sentence = latest_category_sentence(group_latest)
    if not records:
        return latest_sentence or "このカテゴリーでは、現在選択されている指標について時系列の変化を確認できるデータが不足しています。"

    main = records[0]
    unit = str(main["unit"])
    trend_sentence = (
        f"時系列で見ると、{main['indicator_name']}は{main['first_label']}の"
        f"{format_summary_value(main['first_value'], unit)}から{main['latest_label']}の"
        f"{format_summary_value(main['latest_value'], unit)}へ{main['direction']}しています。"
    )
    if len(records) >= 2:
        second = records[1]
        second_unit = str(second["unit"])
        trend_sentence += (
            f"あわせて、{second['indicator_name']}も{second['first_label']}の"
            f"{format_summary_value(second['first_value'], second_unit)}から{second['latest_label']}の"
            f"{format_summary_value(second['latest_value'], second_unit)}へ{second['direction']}しています。"
        )
    return " ".join(sentence for sentence in [latest_sentence, trend_sentence] if sentence)


def overall_evaluation_paragraph(area_df: pd.DataFrame, selected_ids: list[str], context_events: pd.DataFrame) -> str:
    selected_df = area_df[area_df["indicator_id"].isin(selected_ids)].copy()
    selected_indicator_count = selected_df["indicator_id"].nunique()
    latest_count = latest_records(selected_df)["indicator_id"].nunique()
    records = trend_records(area_df, selected_ids)

    if not records:
        coverage_sentence = (
            f"現在選択されている{selected_indicator_count}指標のうち、最新値を確認できるものは"
            f"{latest_count}指標です。時系列変化を読むには、まだデータが不足している指標があります。"
        )
        context_sentence = (
            "行政・地域の取り組みについては、確認済み情報を背景情報として併記しています。"
            if not context_events.empty
            else "行政・地域の取り組みについては、確認済み情報がまだ限られています。"
        )
        return coverage_sentence + context_sentence

    direction_counts = {"増加": 0, "減少": 0, "おおむね横ばい": 0}
    for record in records:
        direction_counts[str(record["direction"])] = direction_counts.get(str(record["direction"]), 0) + 1
    top_records = records[:3]
    focus = "、".join(f"{record['indicator_name']}（{record['direction']}）" for record in top_records)
    coverage_sentence = (
        f"現在選択されている{selected_indicator_count}指標のうち、最新値を確認できるものは{latest_count}指標で、"
        f"時系列変化を確認できる指標は{len(records)}指標です。"
    )
    trend_sentence = (
        f"変化が比較的大きい指標として、{focus}が確認されています。"
        f"増加傾向は{direction_counts.get('増加', 0)}指標、減少傾向は{direction_counts.get('減少', 0)}指標、"
        f"おおむね横ばいは{direction_counts.get('おおむね横ばい', 0)}指標です。"
    )
    context_sentence = (
        "行政・地域の取り組み情報も確認できており、指標変化を解釈する際の背景として参照できます。"
        if not context_events.empty
        else "一方で、行政・地域の取り組み情報はまだ十分に確認できていないため、指標変化の背景解釈には留意が必要です。"
    )
    return coverage_sentence + trend_sentence + context_sentence


def render_context_summary(area_name: str) -> None:
    events = local_context_for_area(area_name)
    if events.empty:
        st.write("行政・地域の取り組みや近況については、確認済みの時点情報がまだありません。DATAなしとして扱います。")
        return

    st.write("同じ期間に確認された行政・地域の取り組み・近況として、以下の情報があります。これらは指標変化の背景として併記するもので、因果関係を示すものではありません。")
    for _, row in events.head(4).iterrows():
        source = row["source_name"]
        if isinstance(row.get("source_url"), str) and row["source_url"].startswith("http"):
            source = f"[{source}]({row['source_url']})"
        st.markdown(
            f"- {row['event_label']}：{row['title']}（{row['category']}）。{row['summary']} 出典：{source}"
        )


@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_recent_news_items(area_name: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    cutoff_year = pd.Timestamp.now(tz="Asia/Tokyo") - pd.DateOffset(years=1)

    official_url = OFFICIAL_NEWS_URLS.get(area_name)
    if official_url:
        try:
            response = requests.get(official_url, timeout=6)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a"):
                title = " ".join(link.get_text(" ", strip=True).split())
                href = link.get("href", "")
                if not title or not re.search(r"20\d{2}年|令和", title):
                    continue
                date_match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", title)
                pub_dt = None
                if date_match:
                    pub_dt = pd.Timestamp(
                        year=int(date_match.group(1)),
                        month=int(date_match.group(2)),
                        day=int(date_match.group(3)),
                        tz="Asia/Tokyo",
                    )
                if pub_dt is not None and pub_dt < cutoff_year:
                    continue
                href = urljoin(official_url, href)
                items.append(
                    {
                        "title": title,
                        "url": href or official_url,
                        "source": f"{area_name}公式ウェブサイト",
                        "published": pub_dt.strftime("%Y-%m-%d") if pub_dt is not None else "",
                    }
                )
        except Exception:
            pass

    items.extend(context_event_news_items(area_name))

    deduped: dict[str, dict[str, str]] = {}
    for item in items:
        if not item.get("title") or not item.get("url"):
            continue
        key = item["url"] or item["title"]
        if key and key not in deduped:
            deduped[key] = item
    return list(deduped.values())


def context_event_news_items(area_name: str) -> list[dict[str, str]]:
    events = local_context_for_area(area_name)
    if events.empty:
        return []
    items: list[dict[str, str]] = []
    for _, row in events.iterrows():
        url = str(row.get("source_url", ""))
        title = str(row.get("title", ""))
        if not url.startswith("http") or not title:
            continue
        items.append(
            {
                "title": title,
                "url": url,
                "source": str(row.get("source_name", "確認済み資料")),
                "published": str(row.get("event_label", "")),
            }
        )
    return items


def render_news_card(item: dict[str, str], label: str) -> None:
    title = escape(item.get("title", ""))
    url = escape(item.get("url", ""))
    source = escape(label)
    st.markdown(
        (
            f'<a class="news-card" href="{url}" target="_blank" rel="noreferrer">'
            '<div class="news-card-body">'
            f'<div class="news-card-title">{title}</div>'
            f'<div class="news-card-source">{source}</div>'
            '</div>'
            '</a>'
        ),
        unsafe_allow_html=True,
    )


def render_random_recent_news(area_name: str) -> None:
    icon_heading("source", "ランダム近況ニュース")
    st.markdown(
        '<div class="section-note">'
        '自治体HPや確認済み資料から、出典ページへのリンクを1件表示します。'
        '安全な公開運用のため、記事画像・本文要約・スクリーンショットの転載表示は行いません。'
        'ページを再表示するたびに候補内で変わることがあります。'
        '</div>',
        unsafe_allow_html=True,
    )
    items = fetch_recent_news_items(area_name)
    if not items:
        st.info(f"{area_name}について、表示可能な自治体HP・確認済み資料リンクを取得できませんでした。DATAなしとして扱います。")
        return

    candidate_items = items
    shuffled = candidate_items.copy()
    random.shuffle(shuffled)
    picked = shuffled[0]
    label = f"{picked['published']} / {picked['source']}" if picked.get("published") else picked["source"]
    render_news_card(picked, label)
    st.caption("外部ページへのリンクです。本文・画像は各出典ページで確認してください。")


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
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=54, b=95))
    render_plotly_chart(fig)


def render_chart_tab(area_df: pd.DataFrame, selected_ids: list[str], date_range: tuple[pd.Timestamp, pd.Timestamp]) -> None:
    render_random_recent_news(area_df["area_name"].iloc[0])
    icon_heading("chart", "復興指標グラフ")
    st.markdown(
        '<div class="section-note">'
        '時系列データがある指標は折れ線で、時点が限られる指標は同じ単位ごとの最新値として表示します。'
        '年月のみのデータはグラフ上では当該月の1日位置に、年月日まであるデータはその日付位置に配置しています。'
        'データがない項目はNO DATAとして扱います。'
        '</div>',
        unsafe_allow_html=True,
    )
    start_date, end_date = date_range
    chart_df = area_df[
        area_df["period_dt"].isna()
        | ((area_df["period_dt"] >= start_date) & (area_df["period_dt"] <= end_date))
    ].copy()

    chart_items = []

    def render_in_chart_grid(render_fn) -> None:
        chart_items.append(render_fn)

    def render_chart_grid() -> None:
        for i in range(0, len(chart_items), 2):
            row_columns = st.columns(2, gap="large")
            for column, render_fn in zip(row_columns, chart_items[i : i + 2]):
                with column:
                    render_fn()

    rendered_ids: set[str] = set()
    population_household_ids = [indicator_id for indicator_id in POPULATION_HOUSEHOLD_IDS if indicator_id in selected_ids]
    if population_household_ids:
        pop_data = chart_df[chart_df["indicator_id"].isin(population_household_ids)].copy()
        pop_grain = get_time_grain("population_household")
        pop_data = apply_time_grain(pop_data, pop_grain)
        if pop_data["period_dt"].nunique() >= 2:
            render_in_chart_grid(
                lambda: (
                    render_population_household_chart(pop_data, mark_all_census_segments=pop_grain == "year"),
                    render_time_grain_buttons("population_household"),
                    st.caption(f"表示粒度: {grain_label(pop_grain)}"),
                )
            )
            rendered_ids.update(population_household_ids)

    population_extra_ids = [
        indicator_id
        for indicator_id in INDICATOR_GROUPS["人口・世帯"]
        if indicator_id in selected_ids and indicator_id not in POPULATION_HOUSEHOLD_IDS
    ]
    if population_extra_ids:
        pop_extra_data = chart_df[
            chart_df["indicator_id"].isin(population_extra_ids)
            & chart_df["value"].notna()
            & chart_df["period_dt"].notna()
        ].copy()
        pop_extra_grain = get_time_grain("population_household")
        pop_extra_data = apply_time_grain(pop_extra_data, pop_extra_grain)
        if pop_extra_data["period_dt"].nunique() >= 2:
            for _, unit_df in pop_extra_data.groupby("unit", dropna=False):
                render_in_chart_grid(lambda unit_df=unit_df: render_line_chart(unit_df, "人口・世帯"))
            rendered_ids.update(pop_extra_data["indicator_id"].unique())

    active_dynamics_ids = [indicator_id for indicator_id in DYNAMICS_IDS if indicator_id in selected_ids]
    if active_dynamics_ids:
        dynamics_data = chart_df[
            chart_df["indicator_id"].isin(active_dynamics_ids)
            & chart_df["value"].notna()
            & chart_df["period_dt"].notna()
        ].copy()
        dynamics_grain = get_time_grain("population_dynamics")
        dynamics_data = apply_time_grain(dynamics_data, dynamics_grain, flow_ids=FLOW_INDICATOR_IDS)
        if dynamics_data["period_dt"].nunique() >= 2:
            render_in_chart_grid(
                lambda: (
                    render_line_chart(dynamics_data, "人口移動・自然動態"),
                    render_time_grain_buttons("population_dynamics"),
                    st.caption(f"表示粒度: {grain_label(dynamics_grain)}"),
                )
            )
            rendered_ids.update(dynamics_data["indicator_id"].unique())

    if any(indicator_id in selected_ids for indicator_id in INTENTION_IDS):
        render_in_chart_grid(lambda: render_intention_chart(chart_df, selected_ids))
    rendered_ids.update([indicator_id for indicator_id in INTENTION_IDS if indicator_id in selected_ids])

    health_ids = [indicator_id for indicator_id in HEALTH_DUAL_AXIS_IDS if indicator_id in selected_ids]
    if health_ids:
        health_data = chart_df[chart_df["indicator_id"].isin(health_ids)].copy()
        if health_data["period_dt"].nunique() >= 2:
            render_in_chart_grid(lambda: render_suicide_health_chart(health_data))
            rendered_ids.update(health_ids)

    for title, group_ids in CHART_GROUPS:
        if set(group_ids).issubset(set(CONTEXT_CHART_IDS)):
            continue
        active_group_ids = [indicator_id for indicator_id in group_ids if indicator_id in selected_ids]
        if not active_group_ids:
            continue
        group_data = chart_df[
            chart_df["indicator_id"].isin(active_group_ids)
            & chart_df["value"].notna()
            & chart_df["period_dt"].notna()
        ].copy()
        if group_data["period_dt"].nunique() >= 2 and group_data["indicator_id"].nunique() >= 1:
            for _, unit_df in group_data.groupby("unit", dropna=False):
                unit_title = title if group_data["unit"].nunique(dropna=False) <= 1 else f"{title}（{unit_df['unit'].iloc[0]}）"
                render_in_chart_grid(lambda unit_df=unit_df, unit_title=unit_title: render_line_chart(unit_df, unit_title))
            rendered_ids.update(group_data["indicator_id"].unique())

    handled = {indicator_id for _, ids in CHART_GROUPS for indicator_id in ids} | set(INTENTION_IDS) | set(HEALTH_DUAL_AXIS_IDS) | set(DYNAMICS_IDS)
    latest_candidates: list[pd.DataFrame] = []
    remaining_ids = [indicator_id for indicator_id in selected_ids if indicator_id not in handled and indicator_id not in rendered_ids]
    remaining_df = chart_df[
        chart_df["indicator_id"].isin(remaining_ids)
        & chart_df["value"].notna()
        & chart_df["period_dt"].notna()
    ].copy()
    for (category, unit), grouped_data in remaining_df.groupby(["category", "unit"], dropna=False):
        if grouped_data["period_dt"].nunique() >= 2 and grouped_data["indicator_id"].nunique() >= 2:
            render_in_chart_grid(
                lambda grouped_data=grouped_data, category=category, unit=unit: render_line_chart(
                    grouped_data, f"{category}（{unit}）"
                )
            )
            rendered_ids.update(grouped_data["indicator_id"].unique())

    for indicator_id in selected_ids:
        if indicator_id in handled or indicator_id in rendered_ids:
            continue
        data = chart_df[
            (chart_df["indicator_id"] == indicator_id)
            & chart_df["value"].notna()
            & chart_df["period_dt"].notna()
        ].copy()
        if data["period_dt"].nunique() >= 2:
            render_in_chart_grid(lambda data=data: render_line_chart(data, data["indicator_name"].iloc[0]))
            rendered_ids.add(indicator_id)
        else:
            latest = latest_records(chart_df[chart_df["indicator_id"] == indicator_id])
            if not latest.empty:
                latest_candidates.append(latest)

    if latest_candidates:
        latest_bars = pd.concat(latest_candidates, ignore_index=True)
        latest_bars = latest_bars[~latest_bars["indicator_id"].isin(rendered_ids)].copy()
        if not latest_bars.empty:
            for (category, unit), unit_df in latest_bars.groupby(["category", "unit"], dropna=False):
                title = f"{category}（{unit}）"
                render_in_chart_grid(lambda unit_df=unit_df, title=title: render_latest_bar_chart(unit_df.sort_values("indicator_name"), title))

    render_chart_grid()
    render_context_section(area_df, selected_ids, date_range)


def summarize_area(area_df: pd.DataFrame, selected_ids: list[str]) -> None:
    selected_df = area_df[area_df["indicator_id"].isin(selected_ids)].copy()
    latest = latest_records(selected_df)
    if latest.empty:
        st.info("要約できるデータがありません。")
        return

    area_name = area_df["area_name"].iloc[0]
    context_events = local_context_for_area(area_name)

    icon_heading("summary", "総合評価")
    st.write(overall_evaluation_paragraph(area_df, selected_ids, context_events))
    st.caption("この総合評価は、復興の達成率や最終ゴールへの進捗率ではなく、現在読み込まれている公開データから確認できる変化とデータ充足状況を要約した暫定コメントです。")

    for group_name, group_ids in INDICATOR_GROUPS.items():
        active_ids = [indicator_id for indicator_id in group_ids if indicator_id in selected_ids]
        if not active_ids:
            continue

        group_latest = latest[latest["indicator_id"].isin(active_ids)].copy()
        records = trend_records(area_df, active_ids)
        if group_latest.empty and not records:
            continue

        icon_heading(SUMMARY_GROUP_ICONS.get(group_name, "summary"), group_name)
        st.write(natural_summary_paragraph(group_latest, records))

        if group_name == "身体的・精神的健康":
            st.caption("自殺死亡率は人口規模が小さい年ではNO DATAとして扱っています。年次の変動が大きく見える場合があるため、単年度だけで解釈しないでください。")
        elif group_name == "行政・地域の取り組み":
            if context_events.empty:
                st.write("この市町村について確認済みの行政・地域の取り組みデータはまだありません。DATAなしとして扱います。")
            else:
                st.write(
                    "この項目は、確認できた報告書、施策・事業、調査・検証、地域活動などの情報を時点付きで整理したものです。"
                    "件数は取り組みの存在を把握するための暫定指標であり、取り組みの質や効果を直接評価するものではありません。"
                )
        elif records:
            event = event_near_change(context_events, records[0]["change_dt"])
            if event is not None:
                st.write(
                    f"特徴的な変化が見られた{records[0]['change_label']}の前後には、"
                    f"{event['event_label']}の「{event['title']}」が確認されています。"
                    "これは指標変化の背景として参照する情報であり、因果関係を示すものではありません。"
                )

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


def main() -> None:
    df = load_indicator_data(DATA_VERSION)
    area_options = [area for area in AREA_OPTIONS if area in set(df["area_name"])]
    if AREA_SELECTION_KEY not in st.session_state:
        st.session_state[AREA_SELECTION_KEY] = area_options[0]

    sync_query_area(area_options)
    theme_label = st.sidebar.radio(
        "表示テーマ",
        options=["ライト", "ダーク"],
        index=0 if current_theme() == "light" else 1,
        horizontal=True,
    )
    st.session_state["dashboard_theme"] = "dark" if theme_label == "ダーク" else "light"
    apply_dashboard_theme(st.session_state["dashboard_theme"])

    selected_area = st.sidebar.selectbox(
        "市町村（補助選択）",
        options=area_options,
        key=AREA_SELECTION_KEY,
    )
    area_df = df[df["area_name"] == selected_area].copy()
    date_range = date_range_slider(df)
    selected_ids = render_indicator_selector(df)
    if not selected_ids:
        st.warning("表示する指標を1つ以上選択してください。")
        return

    st.markdown('<div class="dashboard-title">福島県復興指標ダッシュボード</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="dashboard-subtitle">{selected_area}の復興関連指標を、公開データ・公的資料から確認できる範囲で表示します。データがない項目はNO DATAとして扱います。</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="data-updated">データ更新日: {data_updated_label(df)}</div>',
        unsafe_allow_html=True,
    )
    render_area_map(area_options, selected_area)

    graph_tab, summary_tab, data_tab, source_tab = st.tabs(["復興指標", "要約", "データ", "出典・取得状況"])
    with graph_tab:
        render_chart_tab(area_df, selected_ids, date_range)
    with summary_tab:
        summarize_area(area_df, selected_ids)
    with data_tab:
        icon_heading("table", "データ")
        data = area_df[area_df["indicator_id"].isin(selected_ids)].copy()
        latest = latest_records(data)
        if not latest.empty:
            st.markdown("#### 最新値一覧")
            render_latest_table(data)
        st.markdown("#### グラフに使用しているデータ")
        data = sort_by_graph_order(data)
        data = filter_data_table(data)
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
