"""指標抽出器 — シミュレーション結果から時系列データと主要指標を抽出する."""

from __future__ import annotations

from typing import Any

from app.simulation.models import RoundResult, MarketDimension


def extract_dimension_timeline(
    rounds: list[RoundResult],
) -> dict[str, list[float]]:
    """各ラウンドのディメンション別推移を抽出する."""
    timeline: dict[str, list[float]] = {d.value: [] for d in MarketDimension}
    for r in rounds:
        for dim in MarketDimension:
            timeline[dim.value].append(
                r.market_state.dimensions.get(dim, 0.0)
            )
    return timeline


def extract_macro_timeline(
    rounds: list[RoundResult],
) -> dict[str, list[float]]:
    """マクロ指標の推移を抽出する."""
    keys = [
        "economic_sentiment", "tech_hype_level",
        "regulatory_pressure", "ai_disruption_level",
    ]
    timeline: dict[str, list[float]] = {k: [] for k in keys}
    for r in rounds:
        ms = r.market_state
        timeline["economic_sentiment"].append(ms.economic_sentiment)
        timeline["tech_hype_level"].append(ms.tech_hype_level)
        timeline["regulatory_pressure"].append(ms.regulatory_pressure)
        timeline["ai_disruption_level"].append(ms.ai_disruption_level)
    return timeline


def extract_action_summary(
    rounds: list[RoundResult],
) -> dict[str, int]:
    """全ラウンドのアクション種別ごとの実行回数を集計する."""
    counts: dict[str, int] = {}
    for r in rounds:
        for action in r.actions_taken:
            atype = action.get("type", "unknown")
            counts[atype] = counts.get(atype, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def extract_significant_rounds(
    rounds: list[RoundResult], top_n: int = 3
) -> list[dict[str, Any]]:
    """変化が大きかったラウンドを特定する."""
    if len(rounds) < 2:
        return []

    changes = []
    for i in range(1, len(rounds)):
        prev = rounds[i - 1].market_state
        curr = rounds[i].market_state

        total_change = 0.0
        for dim in MarketDimension:
            d_prev = prev.dimensions.get(dim, 0.3)
            d_curr = curr.dimensions.get(dim, 0.3)
            total_change += abs(d_curr - d_prev)

        changes.append({
            "round": rounds[i].round_number,
            "change_magnitude": round(total_change, 4),
            "events": rounds[i].events,
            "action_count": len(rounds[i].actions_taken),
        })

    changes.sort(key=lambda x: x["change_magnitude"], reverse=True)
    return changes[:top_n]


def extract_document_impact_data(
    rounds: list[RoundResult],
) -> list[dict[str, Any]]:
    """ラウンドごとの文書参照ログを集計する."""
    refs: list[dict[str, Any]] = []
    for r in rounds:
        for doc_ref in r.document_references:
            refs.append({
                "round": r.round_number,
                "document_name": doc_ref.document_name,
                "agent_name": doc_ref.agent_name,
                "context_snippet": doc_ref.context_snippet,
            })
    return refs


def build_report_data(
    rounds: list[RoundResult],
    scenario_description: str = "",
    agents_summary: list[dict[str, Any]] | None = None,
    confidence_notes: list[str] | None = None,
) -> dict[str, Any]:
    """レポート生成に必要な全データをまとめる."""
    data: dict[str, Any] = {
        "scenario_description": scenario_description,
        "total_rounds": len(rounds),
        "dimension_timeline": extract_dimension_timeline(rounds),
        "macro_timeline": extract_macro_timeline(rounds),
        "action_summary": extract_action_summary(rounds),
        "significant_rounds": extract_significant_rounds(rounds),
        "document_impact": extract_document_impact_data(rounds),
        "agents": agents_summary or [],
        "final_market": rounds[-1].market_state.model_dump() if rounds else {},
    }
    if confidence_notes:
        data["confidence_notes"] = confidence_notes
    return data
