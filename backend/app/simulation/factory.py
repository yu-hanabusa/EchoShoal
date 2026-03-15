"""Factory for creating default agent populations."""

from __future__ import annotations

from app.core.llm.router import LLMRouter
from app.simulation.agents.base import (
    AgentPersonality,
    AgentProfile,
    AgentState,
    BaseAgent,
)
from app.simulation.agents.community_agent import CommunityAgent
from app.simulation.agents.enterprise_agent import EnterpriseAgent
from app.simulation.agents.freelancer_agent import FreelancerAgent
from app.simulation.agents.government_agent import GovernmentAgent
from app.simulation.agents.indie_dev_agent import IndieDevAgent
from app.simulation.agents.investor_agent import InvestorAgent
from app.simulation.agents.platformer_agent import PlatformerAgent
from app.simulation.models import StakeholderType, MarketDimension


def create_default_agents(llm: LLMRouter) -> list[BaseAgent]:
    """Create a representative set of stakeholder agents for service impact simulation.

    各エージェントにはステークホルダー種別に応じた性格（ペルソナ）を設定する。
    """
    agents: list[BaseAgent] = []

    # --- 企業 (2社: 大手・スタートアップ) ---

    agents.append(EnterpriseAgent(
        profile=AgentProfile(
            name="大手テクノロジー企業A",
            agent_type="大手企業",
            stakeholder_type=StakeholderType.ENTERPRISE,
            description="国内大手IT企業。既存事業の防衛意識が強く、新サービスには慎重だが資金力は豊富。",
        ),
        state=AgentState(
            headcount=500, revenue=3000, cost=2500,
            capabilities={
                MarketDimension.TECH_MATURITY: 0.6,
                MarketDimension.MARKET_AWARENESS: 0.7,
            },
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.8,
            bandwagon=0.3,
            overconfidence=0.4,
            sunk_cost_bias=0.8,
            info_sensitivity=0.6,
            noise=0.03,
            description="大企業特有の意思決定の遅さ。既存事業を守る意識が強く、破壊的サービスには防衛的に反応する。",
        ),
    ))

    agents.append(EnterpriseAgent(
        profile=AgentProfile(
            name="スタートアップB",
            agent_type="スタートアップ",
            stakeholder_type=StakeholderType.ENTERPRISE,
            description="設立2年のスタートアップ。アグレッシブに市場を狙うが経験不足。",
        ),
        state=AgentState(
            headcount=15, revenue=30, cost=50,
            capabilities={
                MarketDimension.TECH_MATURITY: 0.4,
                MarketDimension.USER_ADOPTION: 0.3,
            },
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.2,
            bandwagon=0.5,
            overconfidence=0.8,
            sunk_cost_bias=0.2,
            info_sensitivity=0.6,
            noise=0.12,
            description="若い経営チームが率いる。市場機会に素早く反応するが、身の丈に合わない勝負をしがち。",
        ),
    ))

    # --- フリーランス (1人) ---

    agents.append(FreelancerAgent(
        profile=AgentProfile(
            name="フリーランスC",
            agent_type="フリーランス",
            stakeholder_type=StakeholderType.FREELANCER,
            description="フルスタックエンジニア。新しいツールやサービスの早期採用者。",
        ),
        state=AgentState(
            headcount=1, revenue=80, cost=5,
            capabilities={
                MarketDimension.TECH_MATURITY: 0.7,
                MarketDimension.USER_ADOPTION: 0.5,
            },
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.3,
            bandwagon=0.4,
            overconfidence=0.5,
            sunk_cost_bias=0.3,
            info_sensitivity=0.7,
            noise=0.1,
            description="技術的な好奇心が強く、新サービスを積極的に試す。実務での有用性を重視する堅実な判断。",
        ),
    ))

    # --- 個人開発者 (1人) ---

    agents.append(IndieDevAgent(
        profile=AgentProfile(
            name="個人開発者D",
            agent_type="個人開発者",
            stakeholder_type=StakeholderType.INDIE_DEVELOPER,
            description="副業で個人開発を行う。対象サービスと類似の領域で競合プロダクトを検討中。",
        ),
        state=AgentState(
            headcount=1, revenue=10, cost=2,
            capabilities={
                MarketDimension.TECH_MATURITY: 0.5,
                MarketDimension.COMPETITIVE_PRESSURE: 0.2,
            },
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.3,
            bandwagon=0.7,
            overconfidence=0.4,
            sunk_cost_bias=0.3,
            info_sensitivity=0.5,
            noise=0.15,
            description="SNSやコミュニティの意見に影響されやすい。「自分でも作れる」と考えがちだが、完成まで持っていく力はある。",
        ),
    ))

    # --- 行政 (1機関) ---

    agents.append(GovernmentAgent(
        profile=AgentProfile(
            name="デジタル庁",
            agent_type="行政",
            stakeholder_type=StakeholderType.GOVERNMENT,
            description="デジタル社会推進を担う政府機関。規制とイノベーション促進のバランスを取る。",
        ),
        state=AgentState(
            headcount=200, revenue=0, cost=500,
            capabilities={
                MarketDimension.REGULATORY_RISK: 0.7,
                MarketDimension.MARKET_AWARENESS: 0.4,
            },
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.7,
            bandwagon=0.3,
            overconfidence=0.2,
            sunk_cost_bias=0.6,
            info_sensitivity=0.5,
            noise=0.05,
            description="政策決定に時間がかかるが、一度方針を決めると大きな影響力を持つ。国際動向を見て判断する傾向。",
        ),
    ))

    # --- 投資家/VC (1社) ---

    agents.append(InvestorAgent(
        profile=AgentProfile(
            name="VCファンドE",
            agent_type="投資家/VC",
            stakeholder_type=StakeholderType.INVESTOR,
            description="国内有力VCファンド。SaaS・AI領域に注力。ポートフォリオとのシナジーを重視。",
        ),
        state=AgentState(
            headcount=20, revenue=500, cost=100,
            capabilities={
                MarketDimension.FUNDING_CLIMATE: 0.8,
                MarketDimension.MARKET_AWARENESS: 0.6,
            },
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.4,
            bandwagon=0.5,
            overconfidence=0.6,
            sunk_cost_bias=0.4,
            info_sensitivity=0.8,
            noise=0.08,
            description="データドリブンな投資判断。ハイプに敏感だが、最終的にはユニットエコノミクスを重視する。",
        ),
    ))

    # --- プラットフォーマー (1社) ---

    agents.append(PlatformerAgent(
        profile=AgentProfile(
            name="グローバルクラウドF",
            agent_type="プラットフォーマー",
            stakeholder_type=StakeholderType.PLATFORMER,
            description="グローバルクラウドプラットフォーム。あらゆる領域で類似サービスを展開可能。",
        ),
        state=AgentState(
            headcount=10000, revenue=50000, cost=40000,
            capabilities={
                MarketDimension.TECH_MATURITY: 0.9,
                MarketDimension.COMPETITIVE_PRESSURE: 0.8,
            },
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.3,
            bandwagon=0.2,
            overconfidence=0.7,
            sunk_cost_bias=0.3,
            info_sensitivity=0.8,
            noise=0.05,
            description="市場が十分に大きいと判断すれば競合機能を即座にリリースする。小さい市場は無視する合理的判断。",
        ),
    ))

    # --- 業界団体/コミュニティ (1団体) ---

    agents.append(CommunityAgent(
        profile=AgentProfile(
            name="業界コミュニティG",
            agent_type="業界団体",
            stakeholder_type=StakeholderType.COMMUNITY,
            description="関連技術のオープンソースコミュニティ。標準化と知識共有を推進。",
        ),
        state=AgentState(
            headcount=50, revenue=10, cost=15,
            capabilities={
                MarketDimension.ECOSYSTEM_HEALTH: 0.7,
                MarketDimension.MARKET_AWARENESS: 0.5,
            },
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.4,
            bandwagon=0.3,
            overconfidence=0.3,
            sunk_cost_bias=0.5,
            info_sensitivity=0.6,
            noise=0.08,
            description="技術的公正性を重視。オープン性を好み、ベンダーロックインには批判的。",
        ),
    ))

    return agents
