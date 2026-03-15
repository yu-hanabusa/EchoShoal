"""Core simulation data models for the Service Business Impact Simulator."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class StakeholderType(str, Enum):
    """ステークホルダーの種別."""
    ENTERPRISE = "enterprise"           # 企業（大手・中堅・スタートアップ）
    FREELANCER = "freelancer"           # フリーランス
    INDIE_DEVELOPER = "indie_developer" # 個人開発者
    GOVERNMENT = "government"           # 行政
    INVESTOR = "investor"               # 投資家/VC
    PLATFORMER = "platformer"           # プラットフォーマー
    COMMUNITY = "community"             # 業界団体/コミュニティ


class MarketDimension(str, Enum):
    """シミュレーションが追跡する市場ディメンション."""
    USER_ADOPTION = "user_adoption"                   # ユーザー獲得率
    REVENUE_POTENTIAL = "revenue_potential"            # 収益ポテンシャル
    TECH_MATURITY = "tech_maturity"                    # 技術成熟度
    COMPETITIVE_PRESSURE = "competitive_pressure"      # 競合圧力
    REGULATORY_RISK = "regulatory_risk"                # 規制リスク
    MARKET_AWARENESS = "market_awareness"              # 市場認知度
    ECOSYSTEM_HEALTH = "ecosystem_health"              # エコシステム健全性
    FUNDING_CLIMATE = "funding_climate"                # 資金調達環境


class ServiceMarketState(BaseModel):
    """Snapshot of the service market at a given simulation round.

    Represents aggregate market conditions that all agents can observe.
    Updated each round based on agent actions and external events.
    """
    round_number: int = 0

    # 対象サービス情報
    service_name: str = ""
    service_category: str = ""

    # 各ディメンションの値 (0.0〜1.0)
    dimensions: dict[MarketDimension, float] = Field(
        default_factory=lambda: {d: 0.3 for d in MarketDimension}
    )

    # マクロ環境指標 (0.0〜1.0)
    economic_sentiment: float = 0.5       # 経済センチメント
    tech_hype_level: float = 0.5          # 技術ハイプレベル
    regulatory_pressure: float = 0.3      # 規制圧力
    remote_work_adoption: float = 0.45    # リモートワーク普及率
    ai_disruption_level: float = 0.3      # AI破壊的変化の度合い

    def pressure_ratio(self, dim: MarketDimension) -> float:
        """Returns dimension pressure ratio. >0.5 means high pressure."""
        return self.dimensions.get(dim, 0.3)


class ScenarioInput(BaseModel):
    """User-provided scenario for simulation."""
    description: str = Field(..., min_length=10, max_length=2000)
    num_rounds: int = Field(default=24, ge=1, le=36)

    # サービス情報
    service_name: str = Field(default="", description="評価対象のサービス名")
    service_url: str | None = Field(default=None, description="GitHub/プロダクトURL")
    target_market: str | None = Field(default=None, description="ターゲット市場の説明")

    # 環境パラメータ
    economic_climate: float = Field(default=0.0, ge=-1.0, le=1.0)
    tech_disruption: float = Field(default=0.0, ge=-1.0, le=1.0)
    regulatory_change: str | None = None


class DocumentReference(BaseModel):
    """文書参照ログ — どの文書がどのエージェントに参照されたか."""
    document_id: str = ""
    document_name: str = ""
    agent_id: str = ""
    agent_name: str = ""
    round_number: int = 0
    context_snippet: str = ""


class SuccessScore(BaseModel):
    """サービス成功スコア — LLMが判定する総合評価."""
    score: int = Field(default=50, ge=0, le=100)
    verdict: str = ""
    key_factors: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)


class RoundResult(BaseModel):
    """Result of a single simulation round."""
    round_number: int
    market_state: ServiceMarketState
    actions_taken: list[dict] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    summary: str = ""
    document_references: list[DocumentReference] = Field(default_factory=list)
