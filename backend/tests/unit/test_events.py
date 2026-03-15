"""外部イベントシステムのユニットテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.simulation.events.effects import apply_active_events, apply_event
from app.simulation.events.models import EventImpact, EventType, MarketEvent
from app.simulation.events.scheduler import EventScheduler
from app.simulation.models import ServiceMarketState, ScenarioInput, MarketDimension


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
        assert event.impact.economic_sentiment_delta == 0.0
        assert event.impact.tech_hype_delta == 0.0
        assert event.impact.dimension_delta == {}


class TestEventType:
    def test_all_types(self):
        assert len(EventType) == 6


# --- イベント効果テスト ---

class TestApplyEvent:
    def test_dimension_delta(self):
        market = ServiceMarketState()
        original_ua = market.dimensions[MarketDimension.USER_ADOPTION]
        event = MarketEvent(
            name="ユーザー急増", event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            impact=EventImpact(dimension_delta={"user_adoption": 0.2}),
        )
        apply_event(event, market)
        assert market.dimensions[MarketDimension.USER_ADOPTION] == pytest.approx(original_ua + 0.2)

    def test_economic_sentiment_delta(self):
        market = ServiceMarketState(economic_sentiment=0.5)
        original = market.economic_sentiment
        event = MarketEvent(
            name="景気後退", event_type=EventType.ECONOMIC_SHOCK,
            trigger_round=1,
            impact=EventImpact(economic_sentiment_delta=-0.1),
        )
        apply_event(event, market)
        assert market.economic_sentiment == pytest.approx(original - 0.1)

    def test_tech_hype_delta(self):
        market = ServiceMarketState()
        original = market.tech_hype_level
        event = MarketEvent(
            name="技術ハイプ", event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            impact=EventImpact(tech_hype_delta=0.1),
        )
        apply_event(event, market)
        assert market.tech_hype_level == pytest.approx(original + 0.1)

    def test_ai_disruption_delta(self):
        market = ServiceMarketState()
        original = market.ai_disruption_level
        event = MarketEvent(
            name="AI加速", event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            impact=EventImpact(ai_disruption_delta=0.1),
        )
        apply_event(event, market)
        assert market.ai_disruption_level == pytest.approx(original + 0.1)

    def test_regulatory_pressure_delta(self):
        market = ServiceMarketState()
        original = market.regulatory_pressure
        event = MarketEvent(
            name="規制強化", event_type=EventType.POLICY_CHANGE,
            trigger_round=1,
            impact=EventImpact(regulatory_pressure_delta=0.1),
        )
        apply_event(event, market)
        assert market.regulatory_pressure == pytest.approx(original + 0.1)

    def test_clamps_to_bounds(self):
        market = ServiceMarketState()
        market.dimensions[MarketDimension.USER_ADOPTION] = 0.95
        event = MarketEvent(
            name="テスト", event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            impact=EventImpact(dimension_delta={"user_adoption": 0.2}),
        )
        apply_event(event, market)
        assert market.dimensions[MarketDimension.USER_ADOPTION] == 1.0

    def test_returns_event_messages(self):
        market = ServiceMarketState()
        event = MarketEvent(
            name="DX推進法改正", event_type=EventType.POLICY_CHANGE,
            trigger_round=1, description="デジタル改革を推進",
        )
        msgs = apply_event(event, market)
        assert len(msgs) == 1
        assert "DX推進法改正" in msgs[0]

    def test_invalid_dimension_key_ignored(self):
        market = ServiceMarketState()
        event = MarketEvent(
            name="テスト", event_type=EventType.TECH_DISRUPTION,
            trigger_round=1,
            impact=EventImpact(dimension_delta={"invalid_dimension": 0.5}),
        )
        # エラーにならないこと
        apply_event(event, market)


class TestApplyActiveEvents:
    def test_only_active_events_applied(self):
        events = [
            MarketEvent(
                name="早期", event_type=EventType.POLICY_CHANGE,
                trigger_round=1, duration=2,
                impact=EventImpact(economic_sentiment_delta=-0.05),
            ),
            MarketEvent(
                name="後期", event_type=EventType.ECONOMIC_SHOCK,
                trigger_round=5, duration=1,
                impact=EventImpact(economic_sentiment_delta=-0.1),
            ),
        ]
        market = ServiceMarketState(round_number=1)
        msgs = apply_active_events(events, 1, market)

        assert len(msgs) == 1
        assert "早期" in msgs[0]
        assert market.economic_sentiment == pytest.approx(0.0)  # 0.0 - 0.05, clamped to 0.0

    def test_no_events_active(self):
        events = [
            MarketEvent(
                name="テスト", event_type=EventType.POLICY_CHANGE,
                trigger_round=10,
            ),
        ]
        market = ServiceMarketState(round_number=1)
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
        """LLMなしの場合、静的イベントは空リストを返す（固定係数を使わない方針）."""
        scheduler = EventScheduler(llm=None)
        scenario = ScenarioInput(
            description="AI技術の急速な普及によるサービス市場の変化",
            tech_disruption=0.5,
        )
        events = await scheduler.generate_from_scenario(scenario)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_generate_static_economic_shock(self):
        """LLMなしの場合、静的イベントは空リストを返す."""
        scheduler = EventScheduler(llm=None)
        scenario = ScenarioInput(
            description="深刻な景気後退によるサービス市場への影響を予測する",
            economic_climate=-0.5,
        )
        events = await scheduler.generate_from_scenario(scenario)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_generate_static_regulatory_change(self):
        """LLMなしの場合、静的イベントは空リストを返す."""
        scheduler = EventScheduler(llm=None)
        scenario = ScenarioInput(
            description="新しい規制によるサービス市場への影響予測シナリオ",
            regulatory_change="データ保護法改正",
        )
        events = await scheduler.generate_from_scenario(scenario)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_generate_with_llm(self):
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "events": [
                {
                    "name": "LLM生成イベント",
                    "event_type": "tech_disruption",
                    "description": "技術の急速な進化",
                    "trigger_round": 3,
                    "duration": 2,
                    "impact": {
                        "dimension_delta": {"tech_maturity": 0.15},
                        "tech_hype_delta": 0.05,
                    },
                }
            ]
        })
        scheduler = EventScheduler(llm=mock_llm)
        scenario = ScenarioInput(
            description="AI技術の急速な普及によるサービス市場の変化を予測",
            num_rounds=12,
        )
        events = await scheduler.generate_from_scenario(scenario)

        assert len(events) == 1
        assert events[0].name == "LLM生成イベント"
        assert events[0].impact.dimension_delta["tech_maturity"] == 0.15

    @pytest.mark.asyncio
    async def test_generate_with_llm_fallback_on_error(self):
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(side_effect=RuntimeError("LLMエラー"))
        scheduler = EventScheduler(llm=mock_llm)
        scenario = ScenarioInput(
            description="テスト用のシナリオ説明文です。技術破壊テスト",
            tech_disruption=0.8,
        )
        events = await scheduler.generate_from_scenario(scenario)

        # フォールバックで静的イベント（現在は空リスト）が返される
        assert len(events) == 0

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
