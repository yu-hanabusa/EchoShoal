"""Tests for concrete agent implementations.

Now that _execute_action is in BaseAgent and uses self_impact from LLM,
these tests verify that self_impact deltas are correctly applied to agent state.
"""

from unittest.mock import MagicMock

import pytest

from app.simulation.agents.base import AgentAction, AgentProfile, AgentState
from app.simulation.agents.enterprise_agent import EnterpriseAgent
from app.simulation.agents.freelancer_agent import FreelancerAgent
from app.simulation.agents.indie_dev_agent import IndieDevAgent
from app.simulation.agents.government_agent import GovernmentAgent
from app.simulation.agents.investor_agent import InvestorAgent
from app.simulation.agents.platformer_agent import PlatformerAgent
from app.simulation.agents.community_agent import CommunityAgent
from app.simulation.models import StakeholderType, ServiceMarketState, MarketDimension


def make_enterprise(state_overrides=None):
    profile = AgentProfile(
        name="テスト企業", agent_type="大手企業",
        stakeholder_type=StakeholderType.ENTERPRISE,
    )
    state = AgentState(headcount=50, revenue=1000, cost=800, **(state_overrides or {}))
    return EnterpriseAgent(profile=profile, state=state, llm=MagicMock())


def make_freelancer(state_overrides=None):
    profile = AgentProfile(
        name="テストFL", agent_type="フリーランス",
        stakeholder_type=StakeholderType.FREELANCER,
    )
    state = AgentState(
        headcount=1, revenue=70, cost=5,
        capabilities={MarketDimension.TECH_MATURITY: 0.7},
        **(state_overrides or {})
    )
    return FreelancerAgent(profile=profile, state=state, llm=MagicMock())


def make_indie_dev(state_overrides=None):
    profile = AgentProfile(
        name="テスト個人開発", agent_type="個人開発者",
        stakeholder_type=StakeholderType.INDIE_DEVELOPER,
    )
    state = AgentState(headcount=1, revenue=20, cost=5, **(state_overrides or {}))
    return IndieDevAgent(profile=profile, state=state, llm=MagicMock())


def make_government(state_overrides=None):
    profile = AgentProfile(
        name="テスト行政", agent_type="行政",
        stakeholder_type=StakeholderType.GOVERNMENT,
    )
    state = AgentState(headcount=10, revenue=0, cost=100, **(state_overrides or {}))
    return GovernmentAgent(profile=profile, state=state, llm=MagicMock())


def make_investor(state_overrides=None):
    profile = AgentProfile(
        name="テストVC", agent_type="投資家",
        stakeholder_type=StakeholderType.INVESTOR,
    )
    state = AgentState(headcount=5, revenue=500, cost=200, **(state_overrides or {}))
    return InvestorAgent(profile=profile, state=state, llm=MagicMock())


def make_platformer(state_overrides=None):
    profile = AgentProfile(
        name="テストPF", agent_type="プラットフォーマー",
        stakeholder_type=StakeholderType.PLATFORMER,
    )
    state = AgentState(headcount=1000, revenue=10000, cost=8000, **(state_overrides or {}))
    return PlatformerAgent(profile=profile, state=state, llm=MagicMock())


def make_community(state_overrides=None):
    profile = AgentProfile(
        name="テストコミュニティ", agent_type="業界団体",
        stakeholder_type=StakeholderType.COMMUNITY,
    )
    state = AgentState(headcount=3, revenue=0, cost=20, **(state_overrides or {}))
    return CommunityAgent(profile=profile, state=state, llm=MagicMock())


market = ServiceMarketState()


class TestEnterpriseAgent:
    def test_available_actions(self):
        agent = make_enterprise()
        actions = agent.available_actions()
        assert "adopt_service" in actions
        assert "build_competitor" in actions
        assert "wait_and_observe" in actions

    def test_adopt_service_applies_self_impact(self):
        agent = make_enterprise()
        action = AgentAction(
            agent_id=agent.id, action_type="adopt_service",
            description="採用",
            self_impact={"cost_delta": 20, "satisfaction_delta": 0.05},
        )
        original_cost = agent.state.cost
        agent._execute_action(action, market)
        assert agent.state.cost == original_cost + 20
        assert agent.state.satisfaction == pytest.approx(0.55)

    def test_build_competitor_applies_self_impact(self):
        agent = make_enterprise()
        action = AgentAction(
            agent_id=agent.id, action_type="build_competitor",
            description="競合開発",
            self_impact={"headcount_delta": 5, "cost_delta": 100},
        )
        agent._execute_action(action, market)
        assert agent.state.headcount == 55
        assert agent.state.cost == 800 + 100

    def test_acquire_startup_applies_self_impact(self):
        agent = make_enterprise()
        original_rep = agent.state.reputation
        action = AgentAction(
            agent_id=agent.id, action_type="acquire_startup",
            description="買収",
            self_impact={"cost_delta": 300, "reputation_delta": 0.05},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation > original_rep
        assert agent.state.cost == 800 + 300

    def test_lobby_regulation_applies_self_impact(self):
        agent = make_enterprise()
        original_rep = agent.state.reputation
        action = AgentAction(
            agent_id=agent.id, action_type="lobby_regulation",
            description="ロビー活動",
            self_impact={"reputation_delta": -0.05},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation < original_rep


class TestFreelancerAgent:
    def test_available_actions(self):
        agent = make_freelancer()
        actions = agent.available_actions()
        assert "adopt_tool" in actions
        assert "rest" in actions
        assert "offer_service" in actions

    def test_adopt_tool_applies_self_impact(self):
        agent = make_freelancer()
        action = AgentAction(
            agent_id=agent.id, action_type="adopt_tool",
            description="ツール採用",
            self_impact={"satisfaction_delta": 0.05},
        )
        agent._execute_action(action, market)
        assert agent.state.satisfaction == pytest.approx(0.55)

    def test_offer_service_applies_self_impact(self):
        agent = make_freelancer()
        action = AgentAction(
            agent_id=agent.id, action_type="offer_service",
            description="受託提供",
            self_impact={"revenue_delta": 15, "contracts_delta": 1},
        )
        agent._execute_action(action, market)
        assert agent.state.revenue == 70 + 15
        assert agent.state.active_contracts == 1

    def test_rest_applies_self_impact(self):
        agent = make_freelancer(state_overrides={"satisfaction": 0.3})
        action = AgentAction(
            agent_id=agent.id, action_type="rest",
            description="休養",
            self_impact={"satisfaction_delta": 0.1},
        )
        agent._execute_action(action, market)
        assert agent.state.satisfaction == pytest.approx(0.4)

    def test_raise_rate_applies_self_impact(self):
        agent = make_freelancer()
        action = AgentAction(
            agent_id=agent.id, action_type="raise_rate",
            description="単価交渉",
            self_impact={"revenue_delta": 7},
        )
        agent._execute_action(action, market)
        assert agent.state.revenue == pytest.approx(77)


class TestIndieDevAgent:
    def test_available_actions(self):
        agent = make_indie_dev()
        actions = agent.available_actions()
        assert "launch_competing_product" in actions
        assert "open_source" in actions
        assert "seek_funding" in actions

    def test_launch_competing_product_applies_self_impact(self):
        agent = make_indie_dev()
        action = AgentAction(
            agent_id=agent.id, action_type="launch_competing_product",
            description="競合リリース",
            self_impact={"cost_delta": 10, "reputation_delta": 0.05},
        )
        agent._execute_action(action, market)
        assert agent.state.cost == 5 + 10
        assert agent.state.reputation > 0.5

    def test_open_source_applies_self_impact(self):
        agent = make_indie_dev()
        action = AgentAction(
            agent_id=agent.id, action_type="open_source",
            description="OSS公開",
            self_impact={"reputation_delta": 0.1},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation > 0.5

    def test_abandon_project_applies_self_impact(self):
        agent = make_indie_dev()
        action = AgentAction(
            agent_id=agent.id, action_type="abandon_project",
            description="放棄",
            self_impact={"satisfaction_delta": -0.1, "contracts_delta": -1},
        )
        agent._execute_action(action, market)
        assert agent.state.satisfaction < 0.5


class TestGovernmentAgent:
    def test_available_actions(self):
        agent = make_government()
        actions = agent.available_actions()
        assert "regulate" in actions
        assert "subsidize" in actions
        assert "deregulate" in actions

    def test_regulate_applies_self_impact(self):
        agent = make_government()
        action = AgentAction(
            agent_id=agent.id, action_type="regulate",
            description="規制導入",
            self_impact={"cost_delta": 20},
        )
        agent._execute_action(action, market)
        assert agent.state.cost == 100 + 20

    def test_subsidize_applies_self_impact(self):
        agent = make_government()
        action = AgentAction(
            agent_id=agent.id, action_type="subsidize",
            description="補助金",
            self_impact={"cost_delta": 50, "reputation_delta": 0.05},
        )
        agent._execute_action(action, market)
        assert agent.state.cost == 150
        assert agent.state.reputation == pytest.approx(0.55)

    def test_deregulate_applies_self_impact(self):
        agent = make_government()
        action = AgentAction(
            agent_id=agent.id, action_type="deregulate",
            description="規制緩和",
            self_impact={"reputation_delta": 0.03},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation == pytest.approx(0.53)


class TestInvestorAgent:
    def test_available_actions(self):
        agent = make_investor()
        actions = agent.available_actions()
        assert "invest_seed" in actions
        assert "invest_series" in actions
        assert "divest" in actions
        assert "wait_and_see" in actions

    def test_invest_seed_applies_self_impact(self):
        agent = make_investor()
        action = AgentAction(
            agent_id=agent.id, action_type="invest_seed",
            description="シード投資",
            self_impact={"cost_delta": 100},
        )
        agent._execute_action(action, market)
        assert agent.state.cost == 200 + 100

    def test_divest_applies_self_impact(self):
        agent = make_investor()
        action = AgentAction(
            agent_id=agent.id, action_type="divest",
            description="投資引き上げ",
            self_impact={"revenue_delta": 50, "reputation_delta": -0.05},
        )
        agent._execute_action(action, market)
        assert agent.state.revenue == 500 + 50
        assert agent.state.reputation < 0.5

    def test_fund_competitor_applies_self_impact(self):
        agent = make_investor()
        action = AgentAction(
            agent_id=agent.id, action_type="fund_competitor",
            description="競合に投資",
            self_impact={"cost_delta": 200},
        )
        agent._execute_action(action, market)
        assert agent.state.cost == 200 + 200


class TestPlatformerAgent:
    def test_available_actions(self):
        agent = make_platformer()
        actions = agent.available_actions()
        assert "launch_competing_feature" in actions
        assert "acquire_service" in actions
        assert "restrict_api" in actions

    def test_launch_competing_feature_applies_self_impact(self):
        agent = make_platformer()
        action = AgentAction(
            agent_id=agent.id, action_type="launch_competing_feature",
            description="競合機能リリース",
            self_impact={"cost_delta": 50},
        )
        agent._execute_action(action, market)
        assert agent.state.cost == 8000 + 50

    def test_restrict_api_applies_self_impact(self):
        agent = make_platformer()
        original_rep = agent.state.reputation
        action = AgentAction(
            agent_id=agent.id, action_type="restrict_api",
            description="API制限",
            self_impact={"reputation_delta": -0.1},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation < original_rep

    def test_partner_integrate_applies_self_impact(self):
        agent = make_platformer()
        action = AgentAction(
            agent_id=agent.id, action_type="partner_integrate",
            description="API連携",
            self_impact={"reputation_delta": 0.05},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation == pytest.approx(0.55)


class TestCommunityAgent:
    def test_available_actions(self):
        agent = make_community()
        actions = agent.available_actions()
        assert "endorse" in actions
        assert "set_standard" in actions
        assert "educate_market" in actions

    def test_endorse_applies_self_impact(self):
        agent = make_community()
        action = AgentAction(
            agent_id=agent.id, action_type="endorse",
            description="推薦",
            self_impact={"reputation_delta": 0.05},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation > 0.5

    def test_set_standard_applies_self_impact(self):
        agent = make_community()
        action = AgentAction(
            agent_id=agent.id, action_type="set_standard",
            description="標準策定",
            self_impact={"reputation_delta": 0.03},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation == pytest.approx(0.53)

    def test_reject_standard_applies_self_impact(self):
        agent = make_community()
        original_rep = agent.state.reputation
        action = AgentAction(
            agent_id=agent.id, action_type="reject_standard",
            description="標準除外",
            self_impact={"reputation_delta": -0.05},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation < original_rep

    def test_reputation_clamped(self):
        agent = make_community(state_overrides={"reputation": 0.01})
        action = AgentAction(
            agent_id=agent.id, action_type="reject_standard",
            description="標準除外",
            self_impact={"reputation_delta": -0.1},
        )
        agent._execute_action(action, market)
        assert agent.state.reputation >= 0.0

    def test_empty_self_impact_no_change(self):
        """self_impact が空の場合、状態は変わらない."""
        agent = make_community()
        action = AgentAction(
            agent_id=agent.id, action_type="endorse",
            description="テスト",
        )
        old = agent.state.model_copy()
        agent._execute_action(action, market)
        assert agent.state.cost == old.cost
        assert agent.state.revenue == old.revenue
        assert agent.state.reputation == old.reputation
        assert agent.state.satisfaction == old.satisfaction
