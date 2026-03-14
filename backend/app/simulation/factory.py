"""Factory for creating default agent populations."""

from __future__ import annotations

from app.core.llm.router import LLMRouter
from app.simulation.agents.base import AgentProfile, AgentState, BaseAgent
from app.simulation.agents.enterprise import EnterpriseITAgent
from app.simulation.agents.freelancer import FreelancerAgent
from app.simulation.agents.ses_company import SESCompanyAgent
from app.simulation.agents.sier_company import SIerCompanyAgent
from app.simulation.models import Industry, SkillCategory


def create_default_agents(llm: LLMRouter) -> list[BaseAgent]:
    """Create a representative set of agents for the Japanese IT market."""
    agents: list[BaseAgent] = []

    # SES企業 (3社: 大手・中堅・零細)
    ses_configs = [
        ("テックスタッフ", 200, 600, 400, {SkillCategory.WEB_BACKEND: 0.5, SkillCategory.CLOUD_INFRA: 0.4}),
        ("ITサービス中部", 50, 150, 100, {SkillCategory.WEB_BACKEND: 0.4, SkillCategory.LEGACY: 0.6}),
        ("エスイーネクスト", 15, 40, 30, {SkillCategory.WEB_FRONTEND: 0.3, SkillCategory.MOBILE: 0.3}),
    ]
    for name, headcount, revenue, cost, skills in ses_configs:
        agents.append(SESCompanyAgent(
            profile=AgentProfile(name=name, agent_type="SES企業", industry=Industry.SES),
            state=AgentState(headcount=headcount, revenue=revenue, cost=cost, skills=skills),
            llm=llm,
        ))

    # SIer企業 (2社: 大手・中堅)
    sier_configs = [
        ("日本システム開発", 500, 3000, 2500, {SkillCategory.ERP: 0.6, SkillCategory.LEGACY: 0.7, SkillCategory.CLOUD_INFRA: 0.3}),
        ("デジタルソリューションズ", 80, 500, 400, {SkillCategory.WEB_BACKEND: 0.5, SkillCategory.AI_ML: 0.3}),
    ]
    for name, headcount, revenue, cost, skills in sier_configs:
        agents.append(SIerCompanyAgent(
            profile=AgentProfile(name=name, agent_type="SIer企業", industry=Industry.SIER),
            state=AgentState(headcount=headcount, revenue=revenue, cost=cost, skills=skills),
            llm=llm,
        ))

    # フリーランス (3人: 高単価・中堅・新人)
    fl_configs = [
        ("田中太郎", 90, 5, {SkillCategory.CLOUD_INFRA: 0.9, SkillCategory.WEB_BACKEND: 0.8}),
        ("佐藤花子", 65, 3, {SkillCategory.WEB_FRONTEND: 0.7, SkillCategory.MOBILE: 0.5}),
        ("鈴木一郎", 40, 2, {SkillCategory.WEB_BACKEND: 0.3, SkillCategory.AI_ML: 0.2}),
    ]
    for name, revenue, cost, skills in fl_configs:
        agents.append(FreelancerAgent(
            profile=AgentProfile(name=name, agent_type="フリーランス", industry=Industry.FREELANCE),
            state=AgentState(headcount=1, revenue=revenue, cost=cost, skills=skills),
            llm=llm,
        ))

    # 事業会社IT部門 (2社)
    ent_configs = [
        ("メガバンクIT部", 30, 0, 500, {SkillCategory.LEGACY: 0.8, SkillCategory.SECURITY: 0.6}),
        ("製造業DX推進室", 8, 0, 150, {SkillCategory.ERP: 0.4, SkillCategory.CLOUD_INFRA: 0.2}),
    ]
    for name, headcount, revenue, cost, skills in ent_configs:
        agents.append(EnterpriseITAgent(
            profile=AgentProfile(name=name, agent_type="事業会社IT", industry=Industry.ENTERPRISE_IT),
            state=AgentState(headcount=headcount, revenue=revenue, cost=cost, skills=skills),
            llm=llm,
        ))

    return agents
