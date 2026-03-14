"""Tests for simulation engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.simulation.agents.base import AgentAction, AgentProfile, AgentState, BaseAgent
from app.simulation.engine import SimulationEngine
from app.simulation.models import Industry, MarketState, ScenarioInput, SkillCategory


class StubAgent(BaseAgent):
    """Deterministic agent for engine tests."""

    def available_actions(self) -> list[str]:
        return ["recruit", "upskill"]

    def _execute_action(self, action: AgentAction, market: MarketState) -> None:
        if action.action_type == "recruit":
            self.state.headcount += 1

    async def decide_actions(self, market: MarketState) -> list[AgentAction]:
        return [
            AgentAction(
                agent_id=self.id,
                action_type="recruit",
                description="Auto recruit",
            )
        ]


def make_stub_agent(name: str = "Stub") -> StubAgent:
    profile = AgentProfile(name=name, agent_type="stub", industry=Industry.SES)
    state = AgentState(headcount=5)
    return StubAgent(profile=profile, state=state, llm=MagicMock())


class TestSimulationEngine:
    @pytest.mark.asyncio
    async def test_run_produces_results(self):
        agents = [make_stub_agent("A"), make_stub_agent("B")]
        engine = SimulationEngine(agents=agents, llm=MagicMock())

        # Force all agents active
        with patch.object(engine, "_select_active_agents", return_value=agents):
            results = await engine.run(num_rounds=3)

        assert len(results) == 3
        assert results[0].round_number == 1
        assert results[2].round_number == 3

    @pytest.mark.asyncio
    async def test_market_state_updates(self):
        agents = [make_stub_agent()]
        engine = SimulationEngine(agents=agents, llm=MagicMock())

        with patch.object(engine, "_select_active_agents", return_value=agents):
            await engine.run(num_rounds=1)

        assert engine.market.round_number == 1

    @pytest.mark.asyncio
    async def test_llm_call_limit(self):
        agents = [make_stub_agent()]
        engine = SimulationEngine(agents=agents, llm=MagicMock())
        engine._llm_call_count = 4999

        with patch.object(engine, "_select_active_agents", return_value=agents):
            results = await engine.run(num_rounds=5)

        # Should stop after 1 round (5000th call)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_agent_error_handled(self):
        agent = make_stub_agent()
        agent.decide_actions = AsyncMock(side_effect=RuntimeError("LLM down"))

        engine = SimulationEngine(agents=[agent], llm=MagicMock())
        with patch.object(engine, "_select_active_agents", return_value=[agent]):
            results = await engine.run(num_rounds=1)

        assert len(results) == 1
        assert any("error" in e for e in results[0].events)

    @pytest.mark.asyncio
    async def test_scenario_ai_acceleration(self):
        scenario = ScenarioInput(
            description="AI技術の急速な普及テスト",
            ai_acceleration=1.0,
            num_rounds=5,
        )
        engine = SimulationEngine(
            agents=[make_stub_agent()],
            llm=MagicMock(),
            scenario=scenario,
        )

        with patch.object(engine, "_select_active_agents", return_value=[]):
            await engine.run()

        assert engine.market.ai_automation_rate > 0.05  # Increased from default

    @pytest.mark.asyncio
    async def test_scenario_economic_shock(self):
        scenario = ScenarioInput(
            description="経済ショックのテストシナリオ",
            economic_shock=-0.5,
            num_rounds=3,
        )
        engine = SimulationEngine(
            agents=[],
            llm=MagicMock(),
            scenario=scenario,
        )

        original_price = engine.market.unit_prices[SkillCategory.AI_ML]
        await engine.run()

        assert engine.market.unit_prices[SkillCategory.AI_ML] < original_price

    def test_get_summary(self):
        agents = [make_stub_agent("A")]
        engine = SimulationEngine(agents=agents, llm=MagicMock())
        summary = engine.get_summary()

        assert summary["total_rounds"] == 0
        assert len(summary["agents"]) == 1
        assert summary["agents"][0]["name"] == "A"

    def test_update_market_hire_increases_demand(self):
        engine = SimulationEngine(agents=[], llm=MagicMock())
        original = engine.market.skill_demand[SkillCategory.WEB_BACKEND]

        engine._update_market([
            {"type": "recruit", "agent": "A", "description": ""},
            {"type": "hire_engineers", "agent": "B", "description": ""},
        ])

        assert engine.market.skill_demand[SkillCategory.WEB_BACKEND] > original

    def test_update_market_price_adjustment(self):
        engine = SimulationEngine(agents=[], llm=MagicMock())
        # Set high demand, low supply
        engine.market.skill_demand[SkillCategory.AI_ML] = 0.9
        engine.market.skill_supply[SkillCategory.AI_ML] = 0.3
        original_price = engine.market.unit_prices[SkillCategory.AI_ML]

        engine._update_market([])

        assert engine.market.unit_prices[SkillCategory.AI_ML] > original_price
