"""イベント効果の適用ロジック — MarketState へのイベント影響を計算する."""

from __future__ import annotations

import logging

from app.simulation.events.models import MarketEvent
from app.simulation.models import MarketState, SkillCategory

logger = logging.getLogger(__name__)


def apply_event(event: MarketEvent, market: MarketState) -> list[str]:
    """イベントの影響を MarketState に適用する.

    Returns: 発生したイベントの説明リスト（ラウンド結果の events に追加用）
    """
    impact = event.impact
    messages: list[str] = []

    # スキル需要への影響
    for skill_key, delta in impact.skill_demand_delta.items():
        try:
            sc = SkillCategory(skill_key)
        except ValueError:
            continue
        old = market.skill_demand.get(sc, 0.5)
        market.skill_demand[sc] = max(0.0, min(1.0, old + delta))

    # 単価への影響
    if impact.price_multiplier != 1.0:
        for skill in SkillCategory:
            market.unit_prices[skill] *= impact.price_multiplier

    # マクロ指標
    if impact.unemployment_delta != 0:
        market.unemployment_rate = max(
            0.0, min(1.0, market.unemployment_rate + impact.unemployment_delta)
        )
    if impact.ai_automation_delta != 0:
        market.ai_automation_rate = max(
            0.0, min(1.0, market.ai_automation_rate + impact.ai_automation_delta)
        )
    if impact.remote_work_delta != 0:
        market.remote_work_rate = max(
            0.0, min(1.0, market.remote_work_rate + impact.remote_work_delta)
        )
    if impact.offshore_delta != 0:
        market.overseas_outsource_rate = max(
            0.0, min(1.0, market.overseas_outsource_rate + impact.offshore_delta)
        )

    messages.append(f"[イベント] {event.name}: {event.description}")
    logger.info("イベント適用: %s (ラウンド %d)", event.name, market.round_number)

    return messages


def apply_active_events(
    events: list[MarketEvent], round_number: int, market: MarketState
) -> list[str]:
    """指定ラウンドで有効な全イベントを適用する."""
    all_messages: list[str] = []
    for event in events:
        if event.is_active(round_number):
            msgs = apply_event(event, market)
            all_messages.extend(msgs)
    return all_messages
