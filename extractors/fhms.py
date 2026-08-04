from __future__ import annotations

import pandas as pd
from extractors.common import empty_records_df, now_iso


FHMS_SOURCE_NAME = "県民健康調査・公開集計"
FHMS_SOURCE_URL = "https://fhms.jp/"


def fetch_wbc_counts() -> pd.DataFrame:
    """WBC受検者数取得の雛形。"""
    df = empty_records_df()
    sample = [
        {
            "indicator_id": "wbc_n",
            "indicator_name": "WBC受検者数",
            "area_id": "pref_fukushima",
            "area_name": "福島県",
            "period": "2025-12",
            "value": None,
            "unit": "人",
            "source_name": FHMS_SOURCE_NAME,
            "source_url": FHMS_SOURCE_URL,
            "retrieved_at": now_iso(),
            "notes": "公開集計表の所在確認後に実装。",
        }
    ]
    return pd.concat([df, pd.DataFrame(sample)], ignore_index=True)
