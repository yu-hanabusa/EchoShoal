"""Tests for base agent class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.simulation.agents.base import AgentAction, AgentProfile, AgentState, BaseAgent
from app.simulation.models import Industry, MarketState, SkillCategory


class ConcreteAgent(BaseAgent):
    """Concrete test implementation of BaseAgent."""

    def available_actions(self) -> list[str]:
        return ["action_a", "action_b"]

    def _execute_action(self, action: AgentAction, market: MarketState) -> None:
        if action.action_type == "action_a":
            self.state.revenue += 10


def make_agent(llm=None) -> ConcreteAgent:
    profile = AgentProfile(
        name="テスト企業",
        agent_type="test",
        industry=Industry.SES,
        description="テスト用エージェント",
    )
    state = AgentState(
        skills={SkillCategory.WEB_BACKEND: 0.6},
        revenue=100.0,
        cost=50.0,
        headcount=10,
    )
    return ConcreteAgent(profile=profile, state=state, llm=llm or MagicMock())


class TestAgentProfile:
    def test_auto_id(self):
        p = AgentProfile(name="Test", agent_type="test", industry=Industry.SES)
        assert len(p.id) > 0

    def test_unique_ids(self):
        p1 = AgentProfile(name="A", agent_type="test", industry=Industry.SES)
        p2 = AgentProfile(name="B", agent_type="test", industry=Industry.SES)
        assert p1.id != p2.id


class TestAgentState:
    def test_defaults(self):
        state = AgentState()
        assert state.satisfaction == 0.5
        assert state.reputation == 0.5
        assert state.risk_tolerance == 0.5


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
        market = MarketState()

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

        actions = await agent.decide_actions(MarketState())

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

        actions = await agent.decide_actions(MarketState())
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
        await agent.apply_actions([action], MarketState())
        assert agent.state.revenue == original_revenue + 10

    def test_to_summary(self):
        agent = make_agent()
        summary = agent.to_summary()
        assert summary["name"] == "テスト企業"
        assert summary["type"] == "test"
        assert summary["headcount"] == 10

    def test_build_decision_prompt_includes_market_data(self):
        agent = make_agent()
        market = MarketState(round_number=5, unemployment_rate=0.03)
        prompt = agent._build_decision_prompt(market)
        assert "ラウンド 5" in prompt
        assert "失業率" in prompt
