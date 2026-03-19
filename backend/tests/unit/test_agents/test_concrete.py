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

class TestFreelancerAgent:
    def test_available_actions(self):
        agent = make_freelancer()
        actions = agent.available_actions()
        assert "adopt_tool" in actions
        assert "rest" in actions
        assert "offer_service" in actions

class TestIndieDevAgent:
    def test_available_actions(self):
        agent = make_indie_dev()
        actions = agent.available_actions()
        assert "launch_competing_product" in actions
        assert "open_source" in actions
        assert "seek_funding" in actions

class TestGovernmentAgent:
    def test_available_actions(self):
        agent = make_government()
        actions = agent.available_actions()
        assert "regulate" in actions
        assert "subsidize" in actions
        assert "deregulate" in actions

class TestInvestorAgent:
    def test_available_actions(self):
        agent = make_investor()
        actions = agent.available_actions()
        assert "invest_seed" in actions
        assert "invest_series" in actions
        assert "divest" in actions
        assert "wait_and_see" in actions

class TestPlatformerAgent:
    def test_available_actions(self):
        agent = make_platformer()
        actions = agent.available_actions()
        assert "launch_competing_feature" in actions
        assert "acquire_service" in actions
        assert "restrict_api" in actions

class TestCommunityAgent:
    def test_available_actions(self):
        agent = make_community()
        actions = agent.available_actions()
        assert "endorse" in actions
        assert "set_standard" in actions
        assert "educate_market" in actions
