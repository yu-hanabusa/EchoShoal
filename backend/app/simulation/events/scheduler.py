"""EventScheduler — シナリオからイベントスケジュールを生成する."""

from __future__ import annotations

import logging
from typing import Any

from app.core.llm.router import LLMRouter, TaskType
from app.simulation.events.models import EventImpact, EventType, MarketEvent
from app.simulation.models import ScenarioInput, MarketDimension

logger = logging.getLogger(__name__)

# LLM にイベント生成を依頼する際のシステムプロンプト
_SYSTEM_PROMPT = """あなたはサービスビジネスの市場アナリストです。
シナリオ説明に基づき、シミュレーション期間中に発生しうる市場イベントをJSON形式で生成してください。

回答形式:
{{"events": [
  {{
    "name": "イベント名",
    "event_type": "policy_change|economic_shock|tech_disruption|competitive_move|industry_shift|natural_disaster",
    "description": "イベントの説明",
    "trigger_round": 1-{max_rounds},
    "duration": 1-6,
    "impact": {{
      "dimension_delta": {{"ディメンション名": -0.1〜0.3}},
      "economic_sentiment_delta": -0.1〜0.1,
      "tech_hype_delta": -0.1〜0.1,
      "regulatory_pressure_delta": -0.1〜0.1,
      "ai_disruption_delta": 0.0〜0.1
    }}
  }}
]}}

制約:
- イベントは3〜5個程度
- trigger_round は期間内に分散させる
- 影響値は現実的な範囲で設定
- dimension_delta のキーは: user_adoption, revenue_potential, tech_maturity, competitive_pressure, regulatory_risk, market_awareness, ecosystem_health, funding_climate"""


class EventScheduler:
    """シナリオに基づいてイベントスケジュールを生成・管理する."""

    def __init__(self, llm: LLMRouter | None = None):
        self._llm = llm
        self._events: list[MarketEvent] = []

    @property
    def events(self) -> list[MarketEvent]:
        return self._events

    async def generate_from_scenario(self, scenario: ScenarioInput) -> list[MarketEvent]:
        """LLM を使ってシナリオからイベントを生成する."""
        if self._llm is None:
            logger.warning("LLM未設定のため静的イベントを使用します")
            self._events = self._generate_static_events(scenario)
            return self._events

        prompt = (
            f"対象サービス: {scenario.service_name or '未指定'}\n"
            f"シナリオ: {scenario.description}\n"
            f"シミュレーション期間: {scenario.num_rounds}ラウンド（1ラウンド = 1ヶ月）\n"
            f"経済環境: {scenario.economic_climate}\n"
            f"技術破壊度: {scenario.tech_disruption}\n"
        )
        if scenario.regulatory_change:
            prompt += f"規制変更: {scenario.regulatory_change}\n"

        system = _SYSTEM_PROMPT.replace("{max_rounds}", str(scenario.num_rounds))

        try:
            response = await self._llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=prompt,
                system_prompt=system,
            )
            self._events = self._parse_events(response, scenario.num_rounds)
        except Exception:
            logger.exception("イベント生成に失敗。静的イベントにフォールバック")
            self._events = self._generate_static_events(scenario)

        logger.info("イベントスケジュール生成: %d件", len(self._events))
        return self._events

    def get_active_events(self, round_number: int) -> list[MarketEvent]:
        """指定ラウンドで有効なイベントを返す."""
        return [e for e in self._events if e.is_active(round_number)]

    def add_event(self, event: MarketEvent) -> None:
        """手動でイベントを追加する."""
        self._events.append(event)

    def _parse_events(
        self, response: dict[str, Any], max_rounds: int
    ) -> list[MarketEvent]:
        """LLM 応答をパースして MarketEvent リストに変換する."""
        events = []
        raw_events = response.get("events", [])

        for raw in raw_events:
            try:
                event_type = raw.get("event_type", "")
                if event_type not in EventType.__members__.values():
                    try:
                        event_type = EventType(event_type)
                    except ValueError:
                        continue
                else:
                    event_type = EventType(event_type)

                trigger = raw.get("trigger_round", 1)
                if not 1 <= trigger <= max_rounds:
                    continue

                impact_raw = raw.get("impact", {})
                # dimension_delta のキーを MarketDimension 値に正規化
                dim_deltas = {}
                for k, v in impact_raw.get("dimension_delta", {}).items():
                    k_lower = k.lower()
                    valid_values = {d.value for d in MarketDimension}
                    if k_lower in valid_values:
                        dim_deltas[k_lower] = float(v)

                impact = EventImpact(
                    dimension_delta=dim_deltas,
                    economic_sentiment_delta=float(impact_raw.get("economic_sentiment_delta", 0.0)),
                    tech_hype_delta=float(impact_raw.get("tech_hype_delta", 0.0)),
                    regulatory_pressure_delta=float(impact_raw.get("regulatory_pressure_delta", 0.0)),
                    ai_disruption_delta=float(impact_raw.get("ai_disruption_delta", 0.0)),
                )

                events.append(MarketEvent(
                    name=raw.get("name", "不明なイベント"),
                    event_type=event_type,
                    description=raw.get("description", ""),
                    trigger_round=trigger,
                    duration=min(max(int(raw.get("duration", 1)), 1), 6),
                    impact=impact,
                ))
            except (TypeError, ValueError):
                logger.warning("イベントのパースに失敗: %s", raw)
                continue

        return events

    def _generate_static_events(self, scenario: ScenarioInput) -> list[MarketEvent]:
        """LLM なしで静的にイベントを生成する（フォールバック）."""
        events = []
        mid = scenario.num_rounds // 2

        # 技術破壊シナリオ
        if scenario.tech_disruption > 0.3:
            events.append(MarketEvent(
                name="競合技術の急速な進化",
                event_type=EventType.TECH_DISRUPTION,
                description="AIや新技術の急速な進化により市場環境が激変",
                trigger_round=max(1, mid - 2),
                duration=4,
                impact=EventImpact(
                    dimension_delta={
                        "tech_maturity": 0.15,
                        "competitive_pressure": 0.1,
                    },
                    tech_hype_delta=0.05,
                ),
            ))

        # 経済ショック
        if scenario.economic_climate < -0.3:
            events.append(MarketEvent(
                name="景気後退",
                event_type=EventType.ECONOMIC_SHOCK,
                description="景気後退によりIT投資が縮小",
                trigger_round=max(1, mid - 3),
                duration=6,
                impact=EventImpact(
                    dimension_delta={
                        "funding_climate": -0.1,
                        "revenue_potential": -0.08,
                    },
                    economic_sentiment_delta=-0.05,
                ),
            ))
        elif scenario.economic_climate > 0.3:
            events.append(MarketEvent(
                name="IT投資拡大",
                event_type=EventType.ECONOMIC_SHOCK,
                description="好景気によりデジタル投資が拡大",
                trigger_round=max(1, mid - 2),
                duration=4,
                impact=EventImpact(
                    dimension_delta={
                        "funding_climate": 0.1,
                        "user_adoption": 0.08,
                    },
                    economic_sentiment_delta=0.05,
                ),
            ))

        # 規制変更
        if scenario.regulatory_change:
            events.append(MarketEvent(
                name="規制変更",
                event_type=EventType.POLICY_CHANGE,
                description=scenario.regulatory_change,
                trigger_round=max(1, mid),
                duration=3,
                impact=EventImpact(
                    dimension_delta={"regulatory_risk": 0.1},
                    regulatory_pressure_delta=0.05,
                ),
            ))

        return events
