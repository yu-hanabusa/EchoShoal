"""イベント効果の適用ロジック — ServiceMarketState へのイベント影響を計算する."""

from __future__ import annotations

import logging

from app.simulation.events.models import MarketEvent
from app.simulation.models import ServiceMarketState, MarketDimension

logger = logging.getLogger(__name__)


def apply_event(event: MarketEvent, market: ServiceMarketState) -> list[str]:
    """イベントの影響を ServiceMarketState に適用する.

    Returns: 発生したイベントの説明リスト（ラウンド結果の events に追加用）
    """
    impact = event.impact
    messages: list[str] = []

    # ディメンションへの影響
    for dim_key, delta in impact.dimension_delta.items():
        try:
            dim = MarketDimension(dim_key)
        except ValueError:
            continue
        old = market.dimensions.get(dim, 0.0)
        market.dimensions[dim] = max(0.0, min(1.0, old + delta))

    # マクロ指標
    if impact.economic_sentiment_delta != 0:
        market.economic_sentiment = max(
            0.0, min(1.0, market.economic_sentiment + impact.economic_sentiment_delta)
        )
    if impact.tech_hype_delta != 0:
        market.tech_hype_level = max(
            0.0, min(1.0, market.tech_hype_level + impact.tech_hype_delta)
        )
    if impact.regulatory_pressure_delta != 0:
        market.regulatory_pressure = max(
            0.0, min(1.0, market.regulatory_pressure + impact.regulatory_pressure_delta)
        )
    if impact.ai_disruption_delta != 0:
        market.ai_disruption_level = max(
            0.0, min(1.0, market.ai_disruption_level + impact.ai_disruption_delta)
        )

    messages.append(f"[イベント] {event.name}: {event.description}")
    logger.info("イベント適用: %s (ラウンド %d)", event.name, market.round_number)

    return messages


def apply_active_events(
    events: list[MarketEvent], round_number: int, market: ServiceMarketState
) -> list[str]:
    """指定ラウンドで有効な全イベントを適用する."""
    all_messages: list[str] = []
    for event in events:
        if event.is_active(round_number):
            msgs = apply_event(event, market)
            all_messages.extend(msgs)
    return all_messages
