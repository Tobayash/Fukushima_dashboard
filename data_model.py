from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class IndicatorRecord(BaseModel):
    indicator_id: str = Field(..., description="指標ID")
    indicator_name: str = Field(..., description="指標名")
    area_id: str = Field(..., description="地域ID")
    area_name: str = Field(..., description="地域名")
    period: str = Field(..., description="対象期間。例: 2025-06, 2025")
    value: Optional[float] = Field(None, description="指標値")
    unit: str = Field(..., description="単位")
    source_name: str = Field(..., description="出典名")
    source_url: str = Field(..., description="出典URL")
    retrieved_at: str = Field(..., description="取得日時 ISO 8601")
    notes: Optional[str] = Field(None, description="備考")
