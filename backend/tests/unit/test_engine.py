"""Tests for simulation engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.simulation.agents.base import AgentAction, AgentProfile, AgentState, BaseAgent
from app.simulation.engine import SimulationEngine
from app.simulation.models import StakeholderType, ServiceMarketState, ScenarioInput, MarketDimension


class StubAgent(BaseAgent):
    """Deterministic agent for engine tests."""

    def available_actions(self) -> list[str]:
        return ["adopt_service", "upskill"]

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        if action.action_type == "adopt_service":
            self.state.headcount += 1

    async def decide_actions(self, market: ServiceMarketState, rag_context: str = "") -> list[AgentAction]:
        return [
            AgentAction(
                agent_id=self.id,
                action_type="adopt_service",
                description="Auto adopt",
            )
        ]


def make_stub_agent(name: str = "Stub") -> StubAgent:
    profile = AgentProfile(name=name, agent_type="stub", stakeholder_type=StakeholderType.ENTERPRISE)
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
    async def test_scenario_tech_disruption(self):
        scenario = ScenarioInput(
            description="AI技術の急速な普及テスト",
            tech_disruption=1.0,
            num_rounds=5,
        )
        engine = SimulationEngine(
            agents=[make_stub_agent()],
            llm=MagicMock(),
            scenario=scenario,
        )

        with patch.object(engine, "_select_active_agents", return_value=[]):
            await engine.run()

        assert engine.market.ai_disruption_level > 0.3  # Increased from default

    @pytest.mark.asyncio
    async def test_scenario_economic_climate(self):
        scenario = ScenarioInput(
            description="経済ショックのテストシナリオ",
            economic_climate=-0.5,
            num_rounds=3,
        )
        engine = SimulationEngine(
            agents=[],
            llm=MagicMock(),
            scenario=scenario,
        )

        original_sentiment = engine.market.economic_sentiment
        await engine.run()

        assert engine.market.economic_sentiment < original_sentiment

    def test_get_summary(self):
        agents = [make_stub_agent("A")]
        engine = SimulationEngine(agents=agents, llm=MagicMock())
        summary = engine.get_summary()

        assert summary["total_rounds"] == 0
        assert len(summary["agents"]) == 1
        assert summary["agents"][0]["name"] == "A"

    def test_update_market_adopt_increases_user_adoption(self):
        engine = SimulationEngine(agents=[], llm=MagicMock())
        original = engine.market.dimensions[MarketDimension.USER_ADOPTION]

        engine._update_market([
            {"type": "adopt_service", "agent": "A", "description": ""},
        ])

        assert engine.market.dimensions[MarketDimension.USER_ADOPTION] > original

    def test_update_market_build_competitor_increases_pressure(self):
        engine = SimulationEngine(agents=[], llm=MagicMock())
        original = engine.market.dimensions[MarketDimension.COMPETITIVE_PRESSURE]

        engine._update_market([
            {"type": "build_competitor", "agent": "A", "description": ""},
        ])

        assert engine.market.dimensions[MarketDimension.COMPETITIVE_PRESSURE] > original
