"""外部イベントモデル — シミュレーション中に発生する市場イベント."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """イベント種別."""
    POLICY_CHANGE = "policy_change"          # 政策・制度変更
    ECONOMIC_SHOCK = "economic_shock"        # 景気変動
    TECH_DISRUPTION = "tech_disruption"      # 技術的変革
    COMPETITIVE_MOVE = "competitive_move"    # 競合の動き
    INDUSTRY_SHIFT = "industry_shift"        # 業界構造変化
    NATURAL_DISASTER = "natural_disaster"    # 自然災害


class EventImpact(BaseModel):
    """イベントが市場に与える影響."""
    # ディメンションへの影響（正: 増加、負: 減少）
    dimension_delta: dict[str, float] = Field(default_factory=dict)
    # マクロ指標への影響
    economic_sentiment_delta: float = 0.0
    tech_hype_delta: float = 0.0
    regulatory_pressure_delta: float = 0.0
    ai_disruption_delta: float = 0.0


class MarketEvent(BaseModel):
    """シミュレーション中に発生する市場イベント."""
    name: str
    event_type: EventType
    description: str = ""
    trigger_round: int = Field(ge=1)       # 発生ラウンド
    duration: int = Field(default=1, ge=1)  # 持続ラウンド数
    impact: EventImpact = Field(default_factory=EventImpact)

    def is_active(self, round_number: int) -> bool:
        """指定ラウンドでこのイベントが有効かどうか."""
        return self.trigger_round <= round_number < self.trigger_round + self.duration
