"""Core simulation data models for the IT labor market."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Industry(str, Enum):
    """IT industry segments in Japan."""
    SIER = "sier"          # System Integrator
    SES = "ses"            # System Engineering Service
    FREELANCE = "freelance"
    WEB_STARTUP = "web_startup"
    ENTERPRISE_IT = "enterprise_it"  # In-house IT departments


class SkillCategory(str, Enum):
    """Skill categories tracked in the market."""
    LEGACY = "legacy"              # COBOL, VB, mainframe
    WEB_FRONTEND = "web_frontend"  # React, Vue, etc.
    WEB_BACKEND = "web_backend"    # Python, Go, Node.js
    CLOUD_INFRA = "cloud_infra"    # AWS, GCP, Azure, K8s
    AI_ML = "ai_ml"                # ML, LLM, data science
    SECURITY = "security"
    MOBILE = "mobile"
    ERP = "erp"                    # SAP, Oracle ERP


class ContractType(str, Enum):
    """Employment/contract types."""
    SEISHAIN = "seishain"          # 正社員 (full-time)
    KEIYAKU = "keiyaku"            # 契約社員 (contract)
    HAKEN = "haken"                # 派遣 (dispatch)
    SES_CONTRACT = "ses_contract"  # SES契約
    FREELANCE = "freelance"        # 業務委託
    GYOMU_ITAKU = "gyomu_itaku"    # 業務委託 (subcontract)


class MarketState(BaseModel):
    """Snapshot of the IT labor market at a given simulation round.

    Represents aggregate market conditions that all agents can observe.
    Updated each round based on agent actions and external events.
    """
    round_number: int = 0

    # Demand/supply per skill (0.0 = no demand, 1.0+ = severe shortage)
    skill_demand: dict[SkillCategory, float] = Field(
        default_factory=lambda: {s: 0.5 for s in SkillCategory}
    )
    skill_supply: dict[SkillCategory, float] = Field(
        default_factory=lambda: {s: 0.5 for s in SkillCategory}
    )

    # Average unit prices per skill (万円/月)
    unit_prices: dict[SkillCategory, float] = Field(
        default_factory=lambda: {
            SkillCategory.LEGACY: 55.0,
            SkillCategory.WEB_FRONTEND: 65.0,
            SkillCategory.WEB_BACKEND: 70.0,
            SkillCategory.CLOUD_INFRA: 75.0,
            SkillCategory.AI_ML: 85.0,
            SkillCategory.SECURITY: 80.0,
            SkillCategory.MOBILE: 68.0,
            SkillCategory.ERP: 72.0,
        }
    )

    # Industry-level metrics
    industry_growth: dict[Industry, float] = Field(
        default_factory=lambda: {i: 0.0 for i in Industry}
    )

    # Macro factors
    average_age: float = 38.5  # IT業界平均年齢
    total_engineers: int = 1_090_000  # 約109万人 (IPA統計ベース)
    unemployment_rate: float = 0.02
    overseas_outsource_rate: float = 0.15  # オフショア比率
    ai_automation_rate: float = 0.05  # AI自動化による代替率
    remote_work_rate: float = 0.45

    def demand_supply_ratio(self, skill: SkillCategory) -> float:
        """Returns demand/supply ratio. >1.0 means shortage."""
        supply = self.skill_supply.get(skill, 0.5)
        if supply <= 0:
            return float("inf")
        return self.skill_demand.get(skill, 0.5) / supply


class ScenarioInput(BaseModel):
    """User-provided scenario for simulation."""
    description: str = Field(..., min_length=10, max_length=2000)
    num_rounds: int = Field(default=24, ge=1, le=36)
    focus_industries: list[Industry] = Field(default_factory=list)
    focus_skills: list[SkillCategory] = Field(default_factory=list)

    # Optional macro shocks
    ai_acceleration: float = Field(default=0.0, ge=-1.0, le=1.0)
    economic_shock: float = Field(default=0.0, ge=-1.0, le=1.0)
    policy_change: str | None = None


class RoundResult(BaseModel):
    """Result of a single simulation round."""
    round_number: int
    market_state: MarketState
    actions_taken: list[dict] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    summary: str = ""
