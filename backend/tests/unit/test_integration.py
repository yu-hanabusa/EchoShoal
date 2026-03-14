"""統合テスト — コンポーネント間の連携確認."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.simulation.agents.base import AgentAction, AgentPersonality, AgentProfile, AgentState, BaseAgent
from app.simulation.agents.ses_company import SESCompanyAgent
from app.simulation.engine import SimulationEngine
from app.simulation.events.effects import apply_active_events
from app.simulation.events.models import EventImpact, EventType, MarketEvent
from app.simulation.events.scheduler import EventScheduler
from app.simulation.models import Industry, MarketState, ScenarioInput, SkillCategory
from app.simulation.scenario_analyzer import ScenarioAnalyzer


# --- LLMフォールバックテスト ---

class StubAgent(BaseAgent):
    def available_actions(self) -> list[str]:
        return ["recruit", "upskill"]

    def _execute_action(self, action: AgentAction, market: MarketState) -> None:
        if action.action_type == "recruit":
            self.state.headcount += 1


def make_stub_agent(llm=None) -> StubAgent:
    profile = AgentProfile(name="Stub", agent_type="stub", industry=Industry.SES)
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

        actions = await agent.decide_actions(MarketState())

        assert len(actions) == 1
        assert actions[0].action_type == "recruit"  # 最初のavailable_action
        assert "フォールバック" in actions[0].description

    @pytest.mark.asyncio
    async def test_fallback_on_empty_actions(self):
        """LLMが空のアクションリストを返した場合もフォールバック."""
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={"actions": []})
        agent = make_stub_agent(llm=mock_llm)

        actions = await agent.decide_actions(MarketState())

        assert len(actions) == 1
        assert actions[0].action_type == "recruit"

    @pytest.mark.asyncio
    async def test_normal_llm_response_no_fallback(self):
        """LLMが正常に応答した場合はフォールバック不使用."""
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "actions": [{"action_type": "upskill", "description": "研修実施"}]
        })
        agent = make_stub_agent(llm=mock_llm)

        actions = await agent.decide_actions(MarketState())

        assert len(actions) == 1
        assert actions[0].action_type == "upskill"


# --- シナリオ解析 → イベント → エンジン統合テスト ---

class TestScenarioToEngine:
    def test_scenario_analyzer_detects_skills(self):
        scenario = ScenarioInput(
            description="生成AIとLLMの普及で Python エンジニアの需要が増加するシナリオ"
        )
        analyzer = ScenarioAnalyzer()
        enriched = analyzer.analyze(scenario)

        assert SkillCategory.AI_ML in enriched.detected_skills
        assert SkillCategory.WEB_BACKEND in enriched.detected_skills

    @pytest.mark.asyncio
    async def test_event_scheduler_generates_events(self):
        scenario = ScenarioInput(
            description="AI技術の急速な普及によるIT人材市場の変化を予測する",
            ai_acceleration=0.8,
        )
        scheduler = EventScheduler(llm=None)
        events = await scheduler.generate_from_scenario(scenario)

        assert len(events) >= 1
        assert any(e.event_type == EventType.TECH_DISRUPTION for e in events)

    @pytest.mark.asyncio
    async def test_engine_with_events(self):
        """エンジンがイベントスケジューラを統合して動作する."""
        scheduler = EventScheduler()
        scheduler.add_event(MarketEvent(
            name="テストイベント",
            event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            duration=2,
            impact=EventImpact(skill_demand_delta={"ai_ml": 0.1}),
        ))

        agent = make_stub_agent()
        agent.decide_actions = AsyncMock(return_value=[
            AgentAction(agent_id=agent.id, action_type="recruit", description="テスト")
        ])

        engine = SimulationEngine(
            agents=[agent], llm=MagicMock(),
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

        engine = SimulationEngine(
            agents=[agent], llm=MagicMock(), on_progress=on_progress
        )

        with patch.object(engine, "_select_active_agents", return_value=[]):
            await engine.run(num_rounds=3)

        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)


# --- SES shift_domain テスト ---

class TestShiftDomain:
    def test_shift_domain_improves_new_skill(self):
        profile = AgentProfile(name="SES", agent_type="SES企業", industry=Industry.SES)
        state = AgentState(
            headcount=10,
            skills={SkillCategory.LEGACY: 0.6},
        )
        agent = SESCompanyAgent(profile=profile, state=state, llm=MagicMock())

        action = AgentAction(
            agent_id=agent.id,
            action_type="shift_domain",
            description="ドメイン変更",
            parameters={"to_skill": "ai_ml", "from_skill": "legacy"},
        )
        agent._execute_action(action, MarketState())

        assert agent.state.skills.get(SkillCategory.AI_ML, 0) == pytest.approx(0.15)
        assert agent.state.skills[SkillCategory.LEGACY] == pytest.approx(0.55)

    def test_shift_domain_without_from_skill(self):
        profile = AgentProfile(name="SES", agent_type="SES企業", industry=Industry.SES)
        state = AgentState(headcount=10)
        agent = SESCompanyAgent(profile=profile, state=state, llm=MagicMock())

        action = AgentAction(
            agent_id=agent.id,
            action_type="shift_domain",
            description="新規ドメイン参入",
            parameters={"to_skill": "cloud_infra"},
        )
        agent._execute_action(action, MarketState())

        assert agent.state.skills.get(SkillCategory.CLOUD_INFRA, 0) == pytest.approx(0.15)


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
