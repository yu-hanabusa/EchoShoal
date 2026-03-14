"""外部イベントシステムのユニットテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.simulation.events.effects import apply_active_events, apply_event
from app.simulation.events.models import EventImpact, EventType, MarketEvent
from app.simulation.events.scheduler import EventScheduler
from app.simulation.models import MarketState, ScenarioInput, SkillCategory


# --- MarketEvent モデルテスト ---

class TestMarketEvent:
    def test_is_active_at_trigger_round(self):
        event = MarketEvent(
            name="テスト", event_type=EventType.POLICY_CHANGE,
            trigger_round=5, duration=3,
        )
        assert event.is_active(5)
        assert event.is_active(6)
        assert event.is_active(7)
        assert not event.is_active(4)
        assert not event.is_active(8)

    def test_is_active_single_round(self):
        event = MarketEvent(
            name="テスト", event_type=EventType.ECONOMIC_SHOCK,
            trigger_round=10, duration=1,
        )
        assert event.is_active(10)
        assert not event.is_active(9)
        assert not event.is_active(11)

    def test_default_impact(self):
        event = MarketEvent(
            name="テスト", event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
        )
        assert event.impact.price_multiplier == 1.0
        assert event.impact.unemployment_delta == 0.0


class TestEventType:
    def test_all_types(self):
        assert len(EventType) == 6


# --- イベント効果テスト ---

class TestApplyEvent:
    def test_skill_demand_delta(self):
        market = MarketState()
        original_ai = market.skill_demand[SkillCategory.AI_ML]
        event = MarketEvent(
            name="AI需要増", event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            impact=EventImpact(skill_demand_delta={"ai_ml": 0.2}),
        )
        apply_event(event, market)
        assert market.skill_demand[SkillCategory.AI_ML] == pytest.approx(original_ai + 0.2)

    def test_price_multiplier(self):
        market = MarketState()
        original_price = market.unit_prices[SkillCategory.WEB_BACKEND]
        event = MarketEvent(
            name="景気後退", event_type=EventType.ECONOMIC_SHOCK,
            trigger_round=1,
            impact=EventImpact(price_multiplier=0.9),
        )
        apply_event(event, market)
        assert market.unit_prices[SkillCategory.WEB_BACKEND] == pytest.approx(original_price * 0.9)

    def test_unemployment_delta(self):
        market = MarketState()
        event = MarketEvent(
            name="解雇増", event_type=EventType.ECONOMIC_SHOCK,
            trigger_round=1,
            impact=EventImpact(unemployment_delta=0.03),
        )
        apply_event(event, market)
        assert market.unemployment_rate == pytest.approx(0.05)  # 0.02 + 0.03

    def test_ai_automation_delta(self):
        market = MarketState()
        original = market.ai_automation_rate
        event = MarketEvent(
            name="AI加速", event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            impact=EventImpact(ai_automation_delta=0.1),
        )
        apply_event(event, market)
        assert market.ai_automation_rate == pytest.approx(original + 0.1)

    def test_clamps_to_bounds(self):
        market = MarketState(unemployment_rate=0.98)
        event = MarketEvent(
            name="テスト", event_type=EventType.ECONOMIC_SHOCK,
            trigger_round=1,
            impact=EventImpact(unemployment_delta=0.1),
        )
        apply_event(event, market)
        assert market.unemployment_rate == 1.0

    def test_returns_event_messages(self):
        market = MarketState()
        event = MarketEvent(
            name="DX推進法改正", event_type=EventType.POLICY_CHANGE,
            trigger_round=1, description="デジタル改革を推進",
        )
        msgs = apply_event(event, market)
        assert len(msgs) == 1
        assert "DX推進法改正" in msgs[0]

    def test_invalid_skill_key_ignored(self):
        market = MarketState()
        event = MarketEvent(
            name="テスト", event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            impact=EventImpact(skill_demand_delta={"invalid_skill": 0.5}),
        )
        # エラーにならないこと
        apply_event(event, market)


class TestApplyActiveEvents:
    def test_only_active_events_applied(self):
        events = [
            MarketEvent(
                name="早期", event_type=EventType.POLICY_CHANGE,
                trigger_round=1, duration=2,
                impact=EventImpact(unemployment_delta=0.01),
            ),
            MarketEvent(
                name="後期", event_type=EventType.ECONOMIC_SHOCK,
                trigger_round=5, duration=1,
                impact=EventImpact(unemployment_delta=0.02),
            ),
        ]
        market = MarketState(round_number=1)
        msgs = apply_active_events(events, 1, market)

        assert len(msgs) == 1
        assert "早期" in msgs[0]
        assert market.unemployment_rate == pytest.approx(0.03)

    def test_no_events_active(self):
        events = [
            MarketEvent(
                name="テスト", event_type=EventType.POLICY_CHANGE,
                trigger_round=10,
            ),
        ]
        market = MarketState(round_number=1)
        msgs = apply_active_events(events, 1, market)
        assert len(msgs) == 0


# --- EventScheduler テスト ---

class TestEventScheduler:
    def test_add_event(self):
        scheduler = EventScheduler()
        event = MarketEvent(
            name="手動イベント", event_type=EventType.POLICY_CHANGE,
            trigger_round=3,
        )
        scheduler.add_event(event)
        assert len(scheduler.events) == 1

    def test_get_active_events(self):
        scheduler = EventScheduler()
        scheduler.add_event(MarketEvent(
            name="A", event_type=EventType.POLICY_CHANGE,
            trigger_round=1, duration=3,
        ))
        scheduler.add_event(MarketEvent(
            name="B", event_type=EventType.ECONOMIC_SHOCK,
            trigger_round=5, duration=1,
        ))

        active_r2 = scheduler.get_active_events(2)
        assert len(active_r2) == 1
        assert active_r2[0].name == "A"

        active_r5 = scheduler.get_active_events(5)
        assert len(active_r5) == 1
        assert active_r5[0].name == "B"

    @pytest.mark.asyncio
    async def test_generate_static_fallback_without_llm(self):
        scheduler = EventScheduler(llm=None)
        scenario = ScenarioInput(
            description="AI技術の急速な普及によるIT人材市場の変化",
            ai_acceleration=0.5,
        )
        events = await scheduler.generate_from_scenario(scenario)
        assert len(events) >= 1
        assert any(e.event_type == EventType.TECH_DISRUPTION for e in events)

    @pytest.mark.asyncio
    async def test_generate_static_economic_shock(self):
        scheduler = EventScheduler(llm=None)
        scenario = ScenarioInput(
            description="深刻な景気後退によるIT市場への影響を予測する",
            economic_shock=-0.5,
        )
        events = await scheduler.generate_from_scenario(scenario)
        assert any(e.event_type == EventType.ECONOMIC_SHOCK for e in events)

    @pytest.mark.asyncio
    async def test_generate_static_policy_change(self):
        scheduler = EventScheduler(llm=None)
        scenario = ScenarioInput(
            description="新しい政策によるIT市場への影響予測シナリオ",
            policy_change="DX推進法改正",
        )
        events = await scheduler.generate_from_scenario(scenario)
        assert any(e.event_type == EventType.POLICY_CHANGE for e in events)

    @pytest.mark.asyncio
    async def test_generate_with_llm(self):
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "events": [
                {
                    "name": "LLM生成イベント",
                    "event_type": "tech_disruption",
                    "description": "AIの急速な進化",
                    "trigger_round": 3,
                    "duration": 2,
                    "impact": {
                        "skill_demand_delta": {"ai_ml": 0.15},
                        "price_multiplier": 1.05,
                    },
                }
            ]
        })
        scheduler = EventScheduler(llm=mock_llm)
        scenario = ScenarioInput(
            description="AI技術の急速な普及によるIT人材市場の変化を予測",
            num_rounds=12,
        )
        events = await scheduler.generate_from_scenario(scenario)

        assert len(events) == 1
        assert events[0].name == "LLM生成イベント"
        assert events[0].impact.skill_demand_delta["ai_ml"] == 0.15

    @pytest.mark.asyncio
    async def test_generate_with_llm_fallback_on_error(self):
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(side_effect=RuntimeError("LLMエラー"))
        scheduler = EventScheduler(llm=mock_llm)
        scenario = ScenarioInput(
            description="テスト用のシナリオ説明文です。AI加速テスト",
            ai_acceleration=0.8,
        )
        events = await scheduler.generate_from_scenario(scenario)

        # フォールバックで静的イベントが生成される
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_parse_skips_invalid_event_type(self):
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "events": [
                {"name": "無効", "event_type": "invalid_type", "trigger_round": 1},
                {"name": "有効", "event_type": "policy_change", "trigger_round": 2},
            ]
        })
        scheduler = EventScheduler(llm=mock_llm)
        scenario = ScenarioInput(
            description="テスト用のシナリオ説明文です。パースの検証。",
            num_rounds=12,
        )
        events = await scheduler.generate_from_scenario(scenario)
        assert len(events) == 1
        assert events[0].name == "有効"

    @pytest.mark.asyncio
    async def test_parse_skips_out_of_range_round(self):
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "events": [
                {"name": "範囲外", "event_type": "policy_change", "trigger_round": 100},
            ]
        })
        scheduler = EventScheduler(llm=mock_llm)
        scenario = ScenarioInput(
            description="テスト用のシナリオ説明文です。ラウンド範囲検証。",
            num_rounds=12,
        )
        events = await scheduler.generate_from_scenario(scenario)
        assert len(events) == 0
