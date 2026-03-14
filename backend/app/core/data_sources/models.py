"""統計データのモデル定義."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StatRecord(BaseModel):
    """統計データの1レコード."""

    name: str = Field(..., description="統計指標名（例: 情報通信業_従業者数）")
    source: str = Field(..., description="データソース（例: e-Stat, IPA白書）")
    year: int = Field(..., description="統計年")
    value: float = Field(..., description="数値")
    unit: str = Field(default="人", description="単位（人, 万円, %, 社）")
    category: str = Field(default="", description="カテゴリ（industry, skill, labor）")
    metadata: dict[str, str] = Field(default_factory=dict, description="追加メタデータ")


class StatMeta(BaseModel):
    """e-Stat 統計表のメタ情報."""

    stats_id: str = Field(..., description="統計表ID")
    title: str = Field(..., description="統計表名")
    survey_name: str = Field(default="", description="調査名")
    updated_at: str = Field(default="", description="最終更新日")


class CollectResult(BaseModel):
    """データ収集結果のサマリー."""

    total_records: int = 0
    stored_records: int = 0
    errors: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
