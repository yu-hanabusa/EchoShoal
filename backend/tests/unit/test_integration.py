"""統合テスト — コンポーネント間の連携確認."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.simulation.agents.base import AgentAction, AgentPersonality, AgentProfile, AgentState, BaseAgent
from app.simulation.agents.enterprise_agent import EnterpriseAgent
from app.simulation.engine import SimulationEngine
from app.simulation.events.effects import apply_active_events
from app.simulation.events.models import EventImpact, EventType, MarketEvent
from app.simulation.events.scheduler import EventScheduler
from app.simulation.models import StakeholderType, ServiceMarketState, ScenarioInput, MarketDimension
from app.simulation.scenario_analyzer import ScenarioAnalyzer


# --- LLMフォールバックテスト ---

class StubAgent(BaseAgent):
    def available_actions(self) -> list[str]:
        return ["adopt_service", "upskill"]


def make_stub_agent(llm=None) -> StubAgent:
    profile = AgentProfile(name="Stub", agent_type="stub", stakeholder_type=StakeholderType.ENTERPRISE)
    state = AgentState(headcount=5)
    return StubAgent(
        profile=profile, state=state, llm=llm or MagicMock(),
        personality=AgentPersonality(noise=0.0),
    )


class TestLLMFallback:
    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        """LLMがエラーを投げた場合、フォールバックアクションが返される."""
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(side_effect=RuntimeError("LLM down"))
        agent = make_stub_agent(llm=mock_llm)

        actions = await agent.decide_actions(ServiceMarketState())

        assert len(actions) == 1
        assert actions[0].action_type == "adopt_service"  # 最初のavailable_action
        assert "フォールバック" in actions[0].description

    @pytest.mark.asyncio
    async def test_fallback_on_empty_actions(self):
        """LLMが空のアクションリストを返した場合もフォールバック."""
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={"actions": []})
        agent = make_stub_agent(llm=mock_llm)

        actions = await agent.decide_actions(ServiceMarketState())

        assert len(actions) == 1
        assert actions[0].action_type == "adopt_service"

    @pytest.mark.asyncio
    async def test_normal_llm_response_no_fallback(self):
        """LLMが正常に応答した場合はフォールバック不使用."""
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "actions": [{"action_type": "upskill", "description": "研修実施"}]
        })
        agent = make_stub_agent(llm=mock_llm)

        actions = await agent.decide_actions(ServiceMarketState())

        assert len(actions) == 1
        assert actions[0].action_type == "upskill"


# --- シナリオ解析 → イベント → エンジン統合テスト ---

class TestScenarioToEngine:
    def test_scenario_analyzer_detects_dimensions(self):
        scenario = ScenarioInput(
            description="生成AIとLLMの普及で Python エンジニアの需要が増加するシナリオ"
        )
        analyzer = ScenarioAnalyzer()
        enriched = analyzer.analyze(scenario)

        assert MarketDimension.TECH_MATURITY in enriched.detected_dimensions

    @pytest.mark.asyncio
    async def test_event_scheduler_generates_events(self):
        """LLMなしの場合、静的イベントは空リストを返す."""
        scenario = ScenarioInput(
            description="AI技術の急速な普及によるサービス市場の変化を予測する",
        )
        scheduler = EventScheduler(llm=None)
        events = await scheduler.generate_from_scenario(scenario)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_engine_with_events(self):
        """エンジンがイベントスケジューラを統合して動作する."""
        scheduler = EventScheduler()
        scheduler.add_event(MarketEvent(
            name="テストイベント",
            event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            duration=2,
            impact=EventImpact(dimension_delta={"tech_maturity": 0.1}),
        ))

        agent = make_stub_agent()
        agent.decide_actions = AsyncMock(return_value=[
            AgentAction(agent_id=agent.id, action_type="adopt_service", description="テスト")
        ])

        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={"dimension_deltas": {}, "macro_deltas": {}})
        mock_llm.generate = AsyncMock(return_value="")

        engine = SimulationEngine(
            agents=[agent], llm=mock_llm,
            event_scheduler=scheduler,
        )

        with patch.object(engine, "_select_active_agents", return_value=[agent]):
            results = await engine.run(num_rounds=2)

        assert len(results) == 2
        # ラウンド1でイベントが発生
        assert any("テストイベント" in e for e in results[0].events)
        # ラウンド2でもイベント有効（duration=2）
        assert any("テストイベント" in e for e in results[1].events)

    @pytest.mark.asyncio
    async def test_engine_progress_callback(self):
        """プログレスコールバックが各ラウンド後に呼ばれる."""
        progress_calls = []

        async def on_progress(current: int, total: int) -> None:
            progress_calls.append((current, total))

        agent = make_stub_agent()
        agent.decide_actions = AsyncMock(return_value=[])

        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={"dimension_deltas": {}, "macro_deltas": {}})
        mock_llm.generate = AsyncMock(return_value="")

        engine = SimulationEngine(
            agents=[agent], llm=mock_llm, on_progress=on_progress
        )

        with patch.object(engine, "_select_active_agents", return_value=[]):
            await engine.run(num_rounds=3)

        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)


# --- Enterprise adopt_service テスト ---

class TestEnterpriseAdoptService:
    def test_adopt_service_applies_self_impact(self):
        """adopt_service with self_impact updates agent state."""
        profile = AgentProfile(name="Enterprise", agent_type="大手企業", stakeholder_type=StakeholderType.ENTERPRISE)
        state = AgentState(headcount=50)
        agent = EnterpriseAgent(profile=profile, state=state, llm=MagicMock())

        action = AgentAction(
            agent_id=agent.id,
            action_type="adopt_service",
            description="サービス採用",
            self_impact={"cost_delta": 20, "satisfaction_delta": 0.05},
        )
        agent._execute_action(action, ServiceMarketState())

        assert agent.state.cost == 20
        assert agent.state.satisfaction == pytest.approx(0.55)

    def test_partner_applies_self_impact(self):
        """partner with self_impact updates agent state."""
        profile = AgentProfile(name="Enterprise", agent_type="大手企業", stakeholder_type=StakeholderType.ENTERPRISE)
        state = AgentState(headcount=50)
        agent = EnterpriseAgent(profile=profile, state=state, llm=MagicMock())

        action = AgentAction(
            agent_id=agent.id,
            action_type="partner",
            description="提携",
            self_impact={"reputation_delta": 0.08},
        )
        agent._execute_action(action, ServiceMarketState())

        assert agent.state.reputation == pytest.approx(0.58)


# --- レートリミットテスト ---

class TestRateLimit:
    def test_check_rate_limit_import(self):
        """レートリミット関数がインポート可能."""
        from app.api.routes.simulations import _check_rate_limit
        assert callable(_check_rate_limit)


# --- ヘルスチェック統合テスト ---

class TestHealthCheckIntegration:
    @pytest.mark.asyncio
    async def test_health_check_with_services(self):
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "redis" in data["services"]
        assert "neo4j" in data["services"]
        # 外部サービス未起動時は unavailable
        assert data["services"]["redis"] in ("connected", "unavailable")
        assert data["services"]["neo4j"] in ("connected", "unavailable")
