"""Tests for concrete agent implementations."""

from unittest.mock import MagicMock

import pytest

from app.simulation.agents.base import AgentAction, AgentProfile, AgentState
from app.simulation.agents.ses_company import SESCompanyAgent
from app.simulation.agents.sier_company import SIerCompanyAgent
from app.simulation.agents.freelancer import FreelancerAgent
from app.simulation.agents.enterprise import EnterpriseITAgent
from app.simulation.models import Industry, MarketState, SkillCategory


def make_ses(state_overrides=None):
    profile = AgentProfile(name="テストSES", agent_type="SES企業", industry=Industry.SES)
    state = AgentState(headcount=20, revenue=200, cost=100, **(state_overrides or {}))
    return SESCompanyAgent(profile=profile, state=state, llm=MagicMock())


def make_sier(state_overrides=None):
    profile = AgentProfile(name="テストSIer", agent_type="SIer企業", industry=Industry.SIER)
    state = AgentState(headcount=100, revenue=1000, cost=800, **(state_overrides or {}))
    return SIerCompanyAgent(profile=profile, state=state, llm=MagicMock())


def make_freelancer(state_overrides=None):
    profile = AgentProfile(name="テストFL", agent_type="フリーランス", industry=Industry.FREELANCE)
    state = AgentState(
        headcount=1, revenue=70, cost=5,
        skills={SkillCategory.WEB_BACKEND: 0.7},
        **(state_overrides or {})
    )
    return FreelancerAgent(profile=profile, state=state, llm=MagicMock())


def make_enterprise(state_overrides=None):
    profile = AgentProfile(name="テスト情シス", agent_type="事業会社IT", industry=Industry.ENTERPRISE_IT)
    state = AgentState(headcount=5, revenue=0, cost=200, **(state_overrides or {}))
    return EnterpriseITAgent(profile=profile, state=state, llm=MagicMock())


market = MarketState()


class TestSESCompanyAgent:
    def test_available_actions(self):
        agent = make_ses()
        assert "recruit" in agent.available_actions()
        assert "upskill" in agent.available_actions()

    def test_recruit_increases_headcount(self):
        agent = make_ses()
        action = AgentAction(
            agent_id=agent.id, action_type="recruit",
            description="採用", parameters={"count": 3},
        )
        agent._execute_action(action, market)
        assert agent.state.headcount == 23
        assert agent.state.cost == 100 + 3 * 35

    def test_release_bench_decreases_headcount(self):
        agent = make_ses()
        action = AgentAction(
            agent_id=agent.id, action_type="release_bench",
            description="整理", parameters={"count": 2},
        )
        agent._execute_action(action, market)
        assert agent.state.headcount == 18
        assert agent.state.satisfaction < 0.5

    def test_upskill(self):
        agent = make_ses()
        action = AgentAction(
            agent_id=agent.id, action_type="upskill",
            description="研修", parameters={"skill": "ai_ml"},
        )
        agent._execute_action(action, market)
        assert agent.state.skills.get(SkillCategory.AI_ML, 0) == pytest.approx(0.1)

    def test_reputation_clamped(self):
        agent = make_ses(state_overrides={"reputation": 0.01})
        action = AgentAction(
            agent_id=agent.id, action_type="adjust_margin",
            description="上げ", parameters={"direction": "up"},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation >= 0.0


class TestSIerCompanyAgent:
    def test_available_actions(self):
        agent = make_sier()
        assert "bid_project" in agent.available_actions()

    def test_bid_project(self):
        agent = make_sier()
        action = AgentAction(
            agent_id=agent.id, action_type="bid_project",
            description="入札", parameters={"scale": "large"},
        )
        agent._execute_action(action, market)
        assert agent.state.revenue == 1000 + 500
        assert agent.state.active_contracts == 1

    def test_outsource_reduces_reputation(self):
        agent = make_sier()
        original_rep = agent.state.reputation
        action = AgentAction(
            agent_id=agent.id, action_type="outsource",
            description="下請け",
        )
        agent._execute_action(action, market)
        assert agent.state.reputation < original_rep


class TestFreelancerAgent:
    def test_available_actions(self):
        agent = make_freelancer()
        assert "take_contract" in agent.available_actions()
        assert "rest" in agent.available_actions()

    def test_take_contract_uses_market_price(self):
        agent = make_freelancer()
        action = AgentAction(
            agent_id=agent.id, action_type="take_contract",
            description="受注", parameters={"skill": "web_backend"},
        )
        agent._execute_action(action, market)
        # base_price=70, proficiency=0.7 -> 70 * (0.7 + 0.42) = 78.4
        assert agent.state.revenue == pytest.approx(78.4)

    def test_learn_skill_increases_proficiency(self):
        agent = make_freelancer()
        action = AgentAction(
            agent_id=agent.id, action_type="learn_skill",
            description="学習", parameters={"skill": "ai_ml"},
        )
        agent._execute_action(action, market)
        assert agent.state.skills[SkillCategory.AI_ML] == pytest.approx(0.12)

    def test_rest_increases_satisfaction(self):
        agent = make_freelancer(state_overrides={"satisfaction": 0.3})
        action = AgentAction(
            agent_id=agent.id, action_type="rest",
            description="休養",
        )
        agent._execute_action(action, market)
        assert agent.state.satisfaction == pytest.approx(0.4)


class TestEnterpriseITAgent:
    def test_available_actions(self):
        agent = make_enterprise()
        assert "start_dx" in agent.available_actions()
        assert "maintain_legacy" in agent.available_actions()

    def test_hire_internal(self):
        agent = make_enterprise()
        action = AgentAction(
            agent_id=agent.id, action_type="hire_internal",
            description="採用", parameters={"count": 2},
        )
        agent._execute_action(action, market)
        assert agent.state.headcount == 7
        assert agent.state.cost == 200 + 100

    def test_start_dx_boosts_skill(self):
        agent = make_enterprise()
        action = AgentAction(
            agent_id=agent.id, action_type="start_dx",
            description="DX", parameters={"skill": "cloud_infra"},
        )
        agent._execute_action(action, market)
        assert agent.state.skills[SkillCategory.CLOUD_INFRA] == pytest.approx(0.2)
        assert agent.state.reputation > 0.5

    def test_maintain_legacy_decreases_satisfaction(self):
        agent = make_enterprise()
        action = AgentAction(
            agent_id=agent.id, action_type="maintain_legacy",
            description="保守",
        )
        agent._execute_action(action, market)
        assert agent.state.satisfaction < 0.5
