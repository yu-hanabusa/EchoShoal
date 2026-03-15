"""Tests for agent personality and biased decision-making."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.simulation.agents.base import (
    AgentAction,
    AgentPersonality,
    AgentProfile,
    AgentState,
    BaseAgent,
)
from app.simulation.models import StakeholderType, ServiceMarketState, MarketDimension


class PersonalityTestAgent(BaseAgent):
    """Test implementation for personality tests."""

    def available_actions(self) -> list[str]:
        return ["action_a", "action_b", "action_c"]

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        pass


def make_test_agent(personality: AgentPersonality | None = None, llm=None):
    profile = AgentProfile(name="テスト", agent_type="test", stakeholder_type=StakeholderType.ENTERPRISE)
    state = AgentState(headcount=10, revenue=100, cost=50)
    return PersonalityTestAgent(
        profile=profile, state=state,
        llm=llm or MagicMock(),
        personality=personality,
    )


class TestAgentPersonality:
    def test_default_values(self):
        p = AgentPersonality()
        assert p.conservatism == 0.5
        assert p.noise == 0.1

    def test_custom_values(self):
        p = AgentPersonality(conservatism=0.9, noise=0.02)
        assert p.conservatism == 0.9
        assert p.noise == 0.02


class TestPersonalityPrompt:
    def test_conservative_prompt(self):
        agent = make_test_agent(AgentPersonality(conservatism=0.9))
        prompt = agent._build_personality_prompt()
        assert "保守的" in prompt

    def test_innovative_prompt(self):
        agent = make_test_agent(AgentPersonality(conservatism=0.1))
        prompt = agent._build_personality_prompt()
        assert "革新的" in prompt

    def test_bandwagon_high(self):
        agent = make_test_agent(AgentPersonality(bandwagon=0.8))
        prompt = agent._build_personality_prompt()
        assert "真似" in prompt or "トレンド" in prompt

    def test_bandwagon_low(self):
        agent = make_test_agent(AgentPersonality(bandwagon=0.2))
        prompt = agent._build_personality_prompt()
        assert "独自" in prompt or "独立" in prompt

    def test_overconfidence_high(self):
        agent = make_test_agent(AgentPersonality(overconfidence=0.8))
        prompt = agent._build_personality_prompt()
        assert "過大評価" in prompt or "大胆" in prompt

    def test_sunk_cost_high(self):
        agent = make_test_agent(AgentPersonality(sunk_cost_bias=0.9))
        prompt = agent._build_personality_prompt()
        assert "過去" in prompt or "愛着" in prompt

    def test_info_sensitivity_low(self):
        agent = make_test_agent(AgentPersonality(info_sensitivity=0.2))
        prompt = agent._build_personality_prompt()
        assert "見落とし" in prompt or "苦手" in prompt

    def test_custom_description_included(self):
        agent = make_test_agent(AgentPersonality(description="カスタム性格"))
        prompt = agent._build_personality_prompt()
        assert "カスタム性格" in prompt

    def test_personality_in_system_prompt(self):
        agent = make_test_agent(AgentPersonality(conservatism=0.9))
        system_prompt = agent._build_system_prompt()
        assert "性格" in system_prompt
        assert "保守的" in system_prompt
        assert "Choose 1-2 actions" in system_prompt


class TestNoiseInjection:
    @pytest.mark.asyncio
    async def test_noise_zero_no_injection(self):
        """noise=0.0 → LLM判断がそのまま返る."""
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "actions": [{"action_type": "action_a", "description": "LLM判断"}]
        })
        agent = make_test_agent(
            personality=AgentPersonality(noise=0.0),
            llm=mock_llm,
        )

        actions = await agent.decide_actions(ServiceMarketState())
        assert len(actions) == 1
        assert actions[0].action_type == "action_a"
        assert actions[0].description == "LLM判断"

    @pytest.mark.asyncio
    async def test_noise_one_always_injects(self):
        """noise=1.0 → 必ずランダム行動に差し替え."""
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "actions": [{"action_type": "action_a", "description": "LLM判断"}]
        })
        agent = make_test_agent(
            personality=AgentPersonality(noise=1.0),
            llm=mock_llm,
        )

        actions = await agent.decide_actions(ServiceMarketState())
        assert len(actions) == 1
        assert actions[0].description == "直感的判断（合理的根拠なし）"
        assert actions[0].action_type in agent.available_actions()

    def test_inject_noise_returns_valid_action(self):
        agent = make_test_agent()
        original = [AgentAction(
            agent_id=agent.id, action_type="action_a", description="元の判断"
        )]
        noised = agent._inject_noise(original)
        assert len(noised) == 1
        assert noised[0].action_type in agent.available_actions()


class TestDefaultPersonality:
    def test_agent_without_personality_gets_default(self):
        agent = make_test_agent(personality=None)
        assert agent.personality.conservatism == 0.5
        assert agent.personality.noise == 0.1

    def test_balanced_prompt(self):
        agent = make_test_agent(personality=AgentPersonality())
        prompt = agent._build_personality_prompt()
        assert "バランス" in prompt
