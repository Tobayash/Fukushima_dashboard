from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"


AREAS = [
    {"area_id": "pref_fukushima", "area_name": "福島県"},
    {"area_id": "tamura", "area_name": "田村市"},
    {"area_id": "minamisoma", "area_name": "南相馬市"},
    {"area_id": "kawamata", "area_name": "川俣町"},
    {"area_id": "hirono", "area_name": "広野町"},
    {"area_id": "naraha", "area_name": "楢葉町"},
    {"area_id": "tomioka", "area_name": "富岡町"},
    {"area_id": "kawauchi", "area_name": "川内村"},
    {"area_id": "okuma", "area_name": "大熊町"},
    {"area_id": "futaba", "area_name": "双葉町"},
    {"area_id": "namie", "area_name": "浪江町"},
    {"area_id": "katsurao", "area_name": "葛尾村"},
    {"area_id": "iitate", "area_name": "飯舘村"},
]

FUTABA_8 = {"広野町", "楢葉町", "富岡町", "川内村", "大熊町", "双葉町", "浪江町", "葛尾村"}
EVACUATION_12 = {area["area_name"] for area in AREAS if area["area_id"] != "pref_fukushima"}
AREA_NAME_TO_ID = {area["area_name"]: area["area_id"] for area in AREAS}


INDICATORS = [
    {"indicator_id": "resident_rate", "indicator_name": "居住率", "unit": "%"},
    {"indicator_id": "returnee_housing_planned", "indicator_name": "帰還者向け住宅計画戸数", "unit": "戸"},
    {"indicator_id": "returnee_housing_completed", "indicator_name": "帰還者向け住宅完成戸数", "unit": "戸"},
    {"indicator_id": "returnee_housing_completion_rate", "indicator_name": "帰還者向け住宅完成率", "unit": "%"},
    {"indicator_id": "infra_completion_mentions", "indicator_name": "公共インフラ工程表 完了記載数", "unit": "件"},
    {"indicator_id": "infra_future_mentions", "indicator_name": "公共インフラ工程表 予定・着手記載数", "unit": "件"},
    {"indicator_id": "life_medical_mentions", "indicator_name": "医療機能関連記載数", "unit": "件"},
    {"indicator_id": "life_school_mentions", "indicator_name": "学校機能関連記載数", "unit": "件"},
    {"indicator_id": "life_commerce_mentions", "indicator_name": "商業機能関連記載数", "unit": "件"},
    {"indicator_id": "industry_mentions", "indicator_name": "産業・農林水産関連記載数", "unit": "件"},
    {"indicator_id": "suicide_deaths_vital", "indicator_name": "自殺者数（人口動態統計）", "unit": "人"},
    {"indicator_id": "suicide_rate_vital", "indicator_name": "自殺死亡率（人口動態統計・人口10万対）", "unit": "人/10万人"},
    {"indicator_id": "current_population", "indicator_name": "現住人口", "unit": "人"},
    {"indicator_id": "households", "indicator_name": "世帯数", "unit": "世帯"},
    {"indicator_id": "transfer_in", "indicator_name": "転入数", "unit": "人"},
    {"indicator_id": "transfer_out", "indicator_name": "転出数", "unit": "人"},
    {"indicator_id": "social_change", "indicator_name": "社会増減", "unit": "人"},
    {"indicator_id": "births", "indicator_name": "出生数", "unit": "人"},
    {"indicator_id": "deaths", "indicator_name": "死亡数", "unit": "人"},
    {"indicator_id": "natural_change", "indicator_name": "自然増減", "unit": "人"},
    {"indicator_id": "evacuees", "indicator_name": "避難者数", "unit": "人"},
    {"indicator_id": "intention_returned", "indicator_name": "戻っている割合", "unit": "%"},
    {"indicator_id": "intention_want_return", "indicator_name": "戻りたい割合", "unit": "%"},
    {"indicator_id": "intention_undecided", "indicator_name": "まだ判断がつかない割合", "unit": "%"},
    {"indicator_id": "intention_no_return", "indicator_name": "戻らない割合", "unit": "%"},
    {"indicator_id": "intention_no_answer", "indicator_name": "無回答割合", "unit": "%"},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_records_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
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
    )


def area_group(area_name: str) -> str:
    if area_name == "福島県":
        return "福島県全体"
    if area_name in FUTABA_8:
        return "避難地域12市町村 / 双葉郡8町村"
    if area_name in EVACUATION_12:
        return "避難地域12市町村"
    return "その他"


def normalize_area_id(area_name: str) -> str:
    return AREA_NAME_TO_ID.get(area_name, area_name)


def save_processed(df: pd.DataFrame, filename: str) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / filename
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return out
