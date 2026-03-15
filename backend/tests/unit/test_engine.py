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

    async def decide_actions(self, market: ServiceMarketState, rag_context: str = "") -> list[AgentAction]:
        return [
            AgentAction(
                agent_id=self.id,
                action_type="adopt_service",
                description="Auto adopt",
                self_impact={"headcount_delta": 1},
            )
        ]


def make_stub_agent(name: str = "Stub") -> StubAgent:
    profile = AgentProfile(name=name, agent_type="stub", stakeholder_type=StakeholderType.ENTERPRISE)
    state = AgentState(headcount=5)
    return StubAgent(profile=profile, state=state, llm=MagicMock())


def _make_engine_with_mock_llm(agents=None, scenario=None, **kwargs):
    """Create engine with an LLM mock that handles _update_market calls."""
    mock_llm = MagicMock()
    mock_llm.generate_json = AsyncMock(return_value={
        "dimension_deltas": {},
        "macro_deltas": {},
    })
    mock_llm.generate = AsyncMock(return_value="")
    return SimulationEngine(
        agents=agents or [],
        llm=mock_llm,
        scenario=scenario,
        **kwargs,
    )


class TestSimulationEngine:
    @pytest.mark.asyncio
    async def test_run_produces_results(self):
        agents = [make_stub_agent("A"), make_stub_agent("B")]
        engine = _make_engine_with_mock_llm(agents=agents)

        # Force all agents active
        with patch.object(engine, "_select_active_agents", return_value=agents):
            results = await engine.run(num_rounds=3)

        assert len(results) == 3
        assert results[0].round_number == 1
        assert results[2].round_number == 3

    @pytest.mark.asyncio
    async def test_market_state_updates(self):
        agents = [make_stub_agent()]
        engine = _make_engine_with_mock_llm(agents=agents)

        with patch.object(engine, "_select_active_agents", return_value=agents):
            await engine.run(num_rounds=1)

        assert engine.market.round_number == 1

    @pytest.mark.asyncio
    async def test_llm_call_limit(self):
        agents = [make_stub_agent()]
        engine = _make_engine_with_mock_llm(agents=agents)
        engine._llm_call_count = 4999

        with patch.object(engine, "_select_active_agents", return_value=agents):
            results = await engine.run(num_rounds=5)

        # Should stop after 1 round (5000th call)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_agent_error_handled(self):
        agent = make_stub_agent()
        agent.decide_actions = AsyncMock(side_effect=RuntimeError("LLM down"))

        engine = _make_engine_with_mock_llm(agents=[agent])
        with patch.object(engine, "_select_active_agents", return_value=[agent]):
            results = await engine.run(num_rounds=1)

        assert len(results) == 1
        assert any("error" in e for e in results[0].events)

    @pytest.mark.asyncio
    async def test_scenario_tech_disruption(self):
        """_apply_scenario_effects still works for engines without event_scheduler."""
        scenario = ScenarioInput(
            description="AI技術の急速な普及テスト",
            tech_disruption=1.0,
            num_rounds=5,
        )
        engine = _make_engine_with_mock_llm(agents=[make_stub_agent()], scenario=scenario)

        with patch.object(engine, "_select_active_agents", return_value=[]):
            await engine.run()

        # _apply_scenario_effects applies delta of tech_disruption * 0.005 per round
        # 5 rounds * 1.0 * 0.005 = 0.025 increase from 0.0
        assert engine.market.ai_disruption_level > 0.0

    @pytest.mark.asyncio
    async def test_scenario_economic_climate(self):
        """_apply_scenario_effects adjusts economic_sentiment over rounds."""
        scenario = ScenarioInput(
            description="経済ショックのテストシナリオ",
            economic_climate=-0.5,
            num_rounds=3,
        )
        engine = _make_engine_with_mock_llm(scenario=scenario)

        original_sentiment = engine.market.economic_sentiment  # 0.0
        await engine.run()

        # economic_climate < 0 means negative delta, but sentiment starts at 0.0
        # so it will be clamped to 0.0
        assert engine.market.economic_sentiment >= 0.0
        assert engine.market.economic_sentiment == pytest.approx(0.0)

    def test_get_summary(self):
        agents = [make_stub_agent("A")]
        engine = _make_engine_with_mock_llm(agents=agents)
        summary = engine.get_summary()

        assert summary["total_rounds"] == 0
        assert len(summary["agents"]) == 1
        assert summary["agents"][0]["name"] == "A"

    @pytest.mark.asyncio
    async def test_update_market_adopt_increases_user_adoption(self):
        """_update_market is now async and LLM-based. Mock LLM to return expected deltas."""
        engine = _make_engine_with_mock_llm()
        engine.llm.generate_json = AsyncMock(return_value={
            "dimension_deltas": {"user_adoption": 0.05},
            "macro_deltas": {},
        })

        original = engine.market.dimensions[MarketDimension.USER_ADOPTION]
        actions = [{"type": "adopt_service", "agent": "A", "agent_id": "x", "description": "", "reputation": 0.5}]
        await engine._update_market(actions, 1)

        assert engine.market.dimensions[MarketDimension.USER_ADOPTION] > original

    @pytest.mark.asyncio
    async def test_update_market_build_competitor_increases_pressure(self):
        """_update_market with LLM returning competitive_pressure delta."""
        engine = _make_engine_with_mock_llm()
        engine.llm.generate_json = AsyncMock(return_value={
            "dimension_deltas": {"competitive_pressure": 0.08},
            "macro_deltas": {},
        })

        original = engine.market.dimensions[MarketDimension.COMPETITIVE_PRESSURE]
        actions = [{"type": "build_competitor", "agent": "A", "agent_id": "x", "description": "", "reputation": 0.5}]
        await engine._update_market(actions, 1)

        assert engine.market.dimensions[MarketDimension.COMPETITIVE_PRESSURE] > original
