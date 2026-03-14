"""指標抽出器 — シミュレーション結果から時系列データと主要指標を抽出する."""

from __future__ import annotations

from typing import Any

from app.simulation.models import RoundResult, SkillCategory


def extract_skill_demand_timeline(
    rounds: list[RoundResult],
) -> dict[str, list[float]]:
    """各ラウンドのスキル別需要推移を抽出する."""
    timeline: dict[str, list[float]] = {s.value: [] for s in SkillCategory}
    for r in rounds:
        for skill in SkillCategory:
            timeline[skill.value].append(
                r.market_state.skill_demand.get(skill, 0.0)
            )
    return timeline


def extract_price_timeline(
    rounds: list[RoundResult],
) -> dict[str, list[float]]:
    """各ラウンドのスキル別単価推移を抽出する."""
    timeline: dict[str, list[float]] = {s.value: [] for s in SkillCategory}
    for r in rounds:
        for skill in SkillCategory:
            timeline[skill.value].append(
                r.market_state.unit_prices.get(skill, 0.0)
            )
    return timeline


def extract_macro_timeline(
    rounds: list[RoundResult],
) -> dict[str, list[float]]:
    """マクロ指標の推移を抽出する."""
    keys = [
        "unemployment_rate", "ai_automation_rate",
        "remote_work_rate", "overseas_outsource_rate",
    ]
    timeline: dict[str, list[float]] = {k: [] for k in keys}
    for r in rounds:
        ms = r.market_state
        timeline["unemployment_rate"].append(ms.unemployment_rate)
        timeline["ai_automation_rate"].append(ms.ai_automation_rate)
        timeline["remote_work_rate"].append(ms.remote_work_rate)
        timeline["overseas_outsource_rate"].append(ms.overseas_outsource_rate)
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
        for skill in SkillCategory:
            d_prev = prev.skill_demand.get(skill, 0.5)
            d_curr = curr.skill_demand.get(skill, 0.5)
            total_change += abs(d_curr - d_prev)

            p_prev = prev.unit_prices.get(skill, 0.0)
            p_curr = curr.unit_prices.get(skill, 0.0)
            if p_prev > 0:
                total_change += abs((p_curr - p_prev) / p_prev)

        changes.append({
            "round": rounds[i].round_number,
            "change_magnitude": round(total_change, 4),
            "events": rounds[i].events,
            "action_count": len(rounds[i].actions_taken),
        })

    changes.sort(key=lambda x: x["change_magnitude"], reverse=True)
    return changes[:top_n]


def build_report_data(
    rounds: list[RoundResult],
    scenario_description: str = "",
    agents_summary: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """レポート生成に必要な全データをまとめる."""
    return {
        "scenario_description": scenario_description,
        "total_rounds": len(rounds),
        "skill_demand_timeline": extract_skill_demand_timeline(rounds),
        "price_timeline": extract_price_timeline(rounds),
        "macro_timeline": extract_macro_timeline(rounds),
        "action_summary": extract_action_summary(rounds),
        "significant_rounds": extract_significant_rounds(rounds),
        "agents": agents_summary or [],
        "final_market": rounds[-1].market_state.model_dump() if rounds else {},
    }
