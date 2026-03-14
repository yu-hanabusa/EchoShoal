"""Factory for creating default agent populations."""

from __future__ import annotations

from app.core.llm.router import LLMRouter
from app.simulation.agents.base import (
    AgentPersonality,
    AgentProfile,
    AgentState,
    BaseAgent,
)
from app.simulation.agents.enterprise import EnterpriseITAgent
from app.simulation.agents.freelancer import FreelancerAgent
from app.simulation.agents.ses_company import SESCompanyAgent
from app.simulation.agents.sier_company import SIerCompanyAgent
from app.simulation.models import Industry, SkillCategory


def create_default_agents(llm: LLMRouter) -> list[BaseAgent]:
    """Create a representative set of agents for the Japanese IT market.

    各エージェントには業界・規模に応じた性格（ペルソナ）を設定する。
    """
    agents: list[BaseAgent] = []

    # --- SES企業 (3社: 大手・中堅・零細) ---

    agents.append(SESCompanyAgent(
        profile=AgentProfile(
            name="テックスタッフ",
            agent_type="SES企業",
            industry=Industry.SES,
            description="老舗SES大手。安定した顧客基盤を持つが組織が硬直化している。",
        ),
        state=AgentState(
            headcount=200, revenue=600, cost=400,
            skills={SkillCategory.WEB_BACKEND: 0.5, SkillCategory.CLOUD_INFRA: 0.4},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.8,
            bandwagon=0.4,
            overconfidence=0.3,
            sunk_cost_bias=0.7,
            info_sensitivity=0.5,
            noise=0.05,
            description="大企業特有の意思決定の遅さがあり、既存顧客を失う恐怖から新規事業に踏み切れない。",
        ),
    ))

    agents.append(SESCompanyAgent(
        profile=AgentProfile(
            name="ITサービス中部",
            agent_type="SES企業",
            industry=Industry.SES,
            description="名古屋拠点の中堅SES。製造業向けが主力だが情報が遅い。",
        ),
        state=AgentState(
            headcount=50, revenue=150, cost=100,
            skills={SkillCategory.WEB_BACKEND: 0.4, SkillCategory.LEGACY: 0.6},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.6,
            bandwagon=0.7,
            overconfidence=0.3,
            sunk_cost_bias=0.5,
            info_sensitivity=0.3,
            noise=0.15,
            description="地方企業で東京のトレンドに半年遅れで追随する。判断にムラがある。",
        ),
    ))

    agents.append(SESCompanyAgent(
        profile=AgentProfile(
            name="エスイーネクスト",
            agent_type="SES企業",
            industry=Industry.SES,
            description="設立3年の少数精鋭SES。成長意欲が強いが経験不足。",
        ),
        state=AgentState(
            headcount=15, revenue=40, cost=30,
            skills={SkillCategory.WEB_FRONTEND: 0.3, SkillCategory.MOBILE: 0.3},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.2,
            bandwagon=0.5,
            overconfidence=0.8,
            sunk_cost_bias=0.2,
            info_sensitivity=0.6,
            noise=0.1,
            description="若い経営者が率いており、身の丈に合わない案件にも挑戦しがち。失敗から学ぶタイプ。",
        ),
    ))

    # --- SIer企業 (2社: 大手・中堅) ---

    agents.append(SIerCompanyAgent(
        profile=AgentProfile(
            name="日本システム開発",
            agent_type="SIer企業",
            industry=Industry.SIER,
            description="官公庁・金融向け大手SIer。レガシー資産が膨大。",
        ),
        state=AgentState(
            headcount=500, revenue=3000, cost=2500,
            skills={SkillCategory.ERP: 0.6, SkillCategory.LEGACY: 0.7, SkillCategory.CLOUD_INFRA: 0.3},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.9,
            bandwagon=0.3,
            overconfidence=0.4,
            sunk_cost_bias=0.9,
            info_sensitivity=0.6,
            noise=0.03,
            description="巨大組織で変化が極端に遅い。COBOL・メインフレームの既存資産に強い愛着がある。稟議に3ヶ月かかる。",
        ),
    ))

    agents.append(SIerCompanyAgent(
        profile=AgentProfile(
            name="デジタルソリューションズ",
            agent_type="SIer企業",
            industry=Industry.SIER,
            description="DX支援に注力する中堅SIer。大手の動向を気にする。",
        ),
        state=AgentState(
            headcount=80, revenue=500, cost=400,
            skills={SkillCategory.WEB_BACKEND: 0.5, SkillCategory.AI_ML: 0.3},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.4,
            bandwagon=0.6,
            overconfidence=0.4,
            sunk_cost_bias=0.3,
            info_sensitivity=0.7,
            noise=0.08,
            description="中堅で柔軟だが、大手SIerの動向を見て追随することが多い。独自色を出そうとしつつ結局は横並び。",
        ),
    ))

    # --- フリーランス (3人: ベテラン・中堅・新人) ---

    agents.append(FreelancerAgent(
        profile=AgentProfile(
            name="田中太郎",
            agent_type="フリーランス",
            industry=Industry.FREELANCE,
            description="クラウドインフラに強いベテランフリーランス。15年のキャリア。",
        ),
        state=AgentState(
            headcount=1, revenue=90, cost=5,
            skills={SkillCategory.CLOUD_INFRA: 0.9, SkillCategory.WEB_BACKEND: 0.8},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.1,
            bandwagon=0.2,
            overconfidence=0.9,
            sunk_cost_bias=0.3,
            info_sensitivity=0.6,
            noise=0.12,
            description="経験豊富で自信過剰。「俺なら何でもできる」と思いがち。高単価案件を狙いすぎて空振りすることも。",
        ),
    ))

    agents.append(FreelancerAgent(
        profile=AgentProfile(
            name="佐藤花子",
            agent_type="フリーランス",
            industry=Industry.FREELANCE,
            description="フロントエンド中心の堅実なフリーランス。7年目。",
        ),
        state=AgentState(
            headcount=1, revenue=65, cost=3,
            skills={SkillCategory.WEB_FRONTEND: 0.7, SkillCategory.MOBILE: 0.5},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.5,
            bandwagon=0.3,
            overconfidence=0.3,
            sunk_cost_bias=0.4,
            info_sensitivity=0.7,
            noise=0.08,
            description="バランスの取れた判断ができる堅実派。データを見て意思決定するタイプ。",
        ),
    ))

    agents.append(FreelancerAgent(
        profile=AgentProfile(
            name="鈴木一郎",
            agent_type="フリーランス",
            industry=Industry.FREELANCE,
            description="独立1年目の駆け出しフリーランス。不安と期待が入り混じる。",
        ),
        state=AgentState(
            headcount=1, revenue=40, cost=2,
            skills={SkillCategory.WEB_BACKEND: 0.3, SkillCategory.AI_ML: 0.2},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.4,
            bandwagon=0.8,
            overconfidence=0.3,
            sunk_cost_bias=0.2,
            info_sensitivity=0.4,
            noise=0.2,
            description="新人で不安が大きく、SNSやコミュニティの意見に流されやすい。「みんながAIやってるから自分も」と考えがち。判断が大きくブレる。",
        ),
    ))

    # --- 事業会社IT部門 (2社) ---

    agents.append(EnterpriseITAgent(
        profile=AgentProfile(
            name="メガバンクIT部",
            agent_type="事業会社IT",
            industry=Industry.ENTERPRISE_IT,
            description="メガバンクの情報システム部。金融規制下で極めて保守的。",
        ),
        state=AgentState(
            headcount=30, revenue=0, cost=500,
            skills={SkillCategory.LEGACY: 0.8, SkillCategory.SECURITY: 0.6},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.95,
            bandwagon=0.2,
            overconfidence=0.1,
            sunk_cost_bias=0.9,
            info_sensitivity=0.5,
            noise=0.02,
            description="金融庁の規制と内部監査があり、新技術の導入は年単位の検討が必要。COBOLの基幹系を20年以上運用しており、刷新の議論は出るが毎回見送り。",
        ),
    ))

    agents.append(EnterpriseITAgent(
        profile=AgentProfile(
            name="製造業DX推進室",
            agent_type="事業会社IT",
            industry=Industry.ENTERPRISE_IT,
            description="製造業のDX推進専門チーム。経営の期待は大きいが経験不足。",
        ),
        state=AgentState(
            headcount=8, revenue=0, cost=150,
            skills={SkillCategory.ERP: 0.4, SkillCategory.CLOUD_INFRA: 0.2},
        ),
        llm=llm,
        personality=AgentPersonality(
            conservatism=0.3,
            bandwagon=0.6,
            overconfidence=0.5,
            sunk_cost_bias=0.3,
            info_sensitivity=0.5,
            noise=0.1,
            description="経営陣から「DXやれ」と言われて作られた部署。やる気はあるが何から手をつけていいか分からず、展示会で見たソリューションに飛びつきがち。",
        ),
    ))

    return agents
