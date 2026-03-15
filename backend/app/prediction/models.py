"""予測モデル — シミュレーション結果の定量予測データ構造."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TrendData(BaseModel):
    """時系列トレンドデータ."""
    values: list[float]
    slope: float = 0.0            # 傾き（1ラウンドあたりの変化量）
    start_value: float = 0.0
    end_value: float = 0.0
    change_rate: float = 0.0      # 全期間の変化率（%）
    moving_avg: list[float] = Field(default_factory=list)


class DimensionPrediction(BaseModel):
    """ディメンション別の予測結果."""
    dimension: str
    current_value: float          # 現在のディメンション値
    predicted_value: float        # 予測値（6ヶ月後）
    trend: TrendData


class PredictionResult(BaseModel):
    """シミュレーション結果に基づく定量予測."""
    simulation_months: int
    dimension_predictions: list[DimensionPrediction] = Field(default_factory=list)
    macro_predictions: dict[str, TrendData] = Field(default_factory=dict)
    highlights: list[str] = Field(default_factory=list)
