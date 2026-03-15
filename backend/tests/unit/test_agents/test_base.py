"""Tests for base agent class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.simulation.agents.base import AgentAction, AgentPersonality, AgentProfile, AgentState, BaseAgent
from app.simulation.models import StakeholderType, ServiceMarketState, MarketDimension


class ConcreteAgent(BaseAgent):
    """Concrete test implementation of BaseAgent."""

    def available_actions(self) -> list[str]:
        return ["action_a", "action_b"]

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        if action.action_type == "action_a":
            self.state.revenue += 10


def make_agent(llm=None) -> ConcreteAgent:
    profile = AgentProfile(
        name="テスト企業",
        agent_type="test",
        stakeholder_type=StakeholderType.ENTERPRISE,
        description="テスト用エージェント",
    )
    state = AgentState(
        capabilities={MarketDimension.TECH_MATURITY: 0.6},
        revenue=100.0,
        cost=50.0,
        headcount=10,
    )
    return ConcreteAgent(
        profile=profile, state=state, llm=llm or MagicMock(),
        personality=AgentPersonality(noise=0.0),  # テストではノイズ無効化
    )


class TestAgentProfile:
    def test_auto_id(self):
        p = AgentProfile(name="Test", agent_type="test", stakeholder_type=StakeholderType.ENTERPRISE)
        assert len(p.id) > 0

    def test_unique_ids(self):
        p1 = AgentProfile(name="A", agent_type="test", stakeholder_type=StakeholderType.ENTERPRISE)
        p2 = AgentProfile(name="B", agent_type="test", stakeholder_type=StakeholderType.FREELANCER)
        assert p1.id != p2.id


class TestAgentState:
    def test_defaults(self):
        state = AgentState()
        assert state.satisfaction == 0.5
        assert state.reputation == 0.5
        assert state.risk_tolerance == 0.5
        assert state.capabilities == {}


class TestBaseAgent:
    def test_properties(self):
        agent = make_agent()
        assert agent.name == "テスト企業"
        assert len(agent.id) > 0

    def test_available_actions(self):
        agent = make_agent()
        assert agent.available_actions() == ["action_a", "action_b"]

    @pytest.mark.asyncio
    async def test_decide_actions_calls_llm(self):
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "actions": [
                {"action_type": "action_a", "description": "テスト"},
            ]
        })
        agent = make_agent(llm=mock_llm)
        market = ServiceMarketState()

        actions = await agent.decide_actions(market)

        assert len(actions) == 1
        assert actions[0].action_type == "action_a"
        mock_llm.generate_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_decide_actions_filters_invalid(self):
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "actions": [
                {"action_type": "invalid_action", "description": "無効"},
                {"action_type": "action_b", "description": "有効"},
            ]
        })
        agent = make_agent(llm=mock_llm)

        actions = await agent.decide_actions(ServiceMarketState())

        assert len(actions) == 1
        assert actions[0].action_type == "action_b"

    @pytest.mark.asyncio
    async def test_decide_actions_max_two(self):
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "actions": [
                {"action_type": "action_a", "description": "1"},
                {"action_type": "action_b", "description": "2"},
                {"action_type": "action_a", "description": "3"},
            ]
        })
        agent = make_agent(llm=mock_llm)

        actions = await agent.decide_actions(ServiceMarketState())
        assert len(actions) == 2

    @pytest.mark.asyncio
    async def test_apply_actions_updates_state(self):
        agent = make_agent()
        action = AgentAction(
            agent_id=agent.id,
            action_type="action_a",
            description="テスト",
        )
        original_revenue = agent.state.revenue
        await agent.apply_actions([action], ServiceMarketState())
        assert agent.state.revenue == original_revenue + 10

    def test_to_summary(self):
        agent = make_agent()
        summary = agent.to_summary()
        assert summary["name"] == "テスト企業"
        assert summary["type"] == "test"
        assert summary["headcount"] == 10
        assert summary["stakeholder_type"] == "enterprise"

    def test_build_decision_prompt_includes_market_data(self):
        agent = make_agent()
        market = ServiceMarketState(
            round_number=5,
            service_name="TestService",
        )
        prompt = agent._build_decision_prompt(market)
        assert "ラウンド 5" in prompt
        assert "TestService" in prompt

    def test_improve_capability(self):
        agent = make_agent()
        result = agent._improve_capability("user_adoption", 0.1)
        assert result is True
        assert agent.state.capabilities[MarketDimension.USER_ADOPTION] == pytest.approx(0.1)

    def test_improve_capability_invalid_dimension(self):
        agent = make_agent()
        result = agent._improve_capability("nonexistent", 0.1)
        assert result is False
