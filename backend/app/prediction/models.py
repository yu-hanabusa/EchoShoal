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


class SkillPrediction(BaseModel):
    """スキル別の予測結果."""
    skill: str
    current_demand: float         # 現在の需要指数
    predicted_demand: float       # 予測需要指数（期間末）
    demand_trend: TrendData
    current_price: float          # 現在の単価（万円/月）
    predicted_price: float        # 予測単価（万円/月）
    price_trend: TrendData
    shortage_estimate: int = 0    # 不足人数の推定


class PredictionResult(BaseModel):
    """シミュレーション結果に基づく定量予測."""
    simulation_months: int
    total_engineers: int = 1_090_000
    skill_predictions: list[SkillPrediction] = Field(default_factory=list)
    macro_predictions: dict[str, TrendData] = Field(default_factory=dict)
    highlights: list[str] = Field(default_factory=list)  # 主要な予測ハイライト
