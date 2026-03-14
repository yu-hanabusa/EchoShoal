"""シナリオ比較分析 — 複数シミュレーション結果の差分を分析する."""

from __future__ import annotations

from typing import Any

from app.prediction.models import PredictionResult


def compare_predictions(
    base: PredictionResult,
    alternative: PredictionResult,
    base_label: str = "ベースシナリオ",
    alt_label: str = "代替シナリオ",
) -> dict[str, Any]:
    """2つの予測結果を比較して差分を返す."""
    skill_diffs = []

    base_skills = {sp.skill: sp for sp in base.skill_predictions}
    alt_skills = {sp.skill: sp for sp in alternative.skill_predictions}

    for skill_key in base_skills:
        b = base_skills[skill_key]
        a = alt_skills.get(skill_key)
        if a is None:
            continue

        skill_diffs.append({
            "skill": skill_key,
            "demand_diff": round(a.predicted_demand - b.predicted_demand, 4),
            "price_diff": round(a.predicted_price - b.predicted_price, 1),
            "shortage_diff": a.shortage_estimate - b.shortage_estimate,
            base_label: {
                "demand": b.predicted_demand,
                "price": b.predicted_price,
                "shortage": b.shortage_estimate,
            },
            alt_label: {
                "demand": a.predicted_demand,
                "price": a.predicted_price,
                "shortage": a.shortage_estimate,
            },
        })

    # マクロ比較
    macro_diffs = {}
    for key in base.macro_predictions:
        b_trend = base.macro_predictions[key]
        a_trend = alternative.macro_predictions.get(key)
        if a_trend is None:
            continue
        macro_diffs[key] = {
            "end_value_diff": round(a_trend.end_value - b_trend.end_value, 4),
            "change_rate_diff": round(a_trend.change_rate - b_trend.change_rate, 2),
            base_label: {"end_value": b_trend.end_value, "change_rate": b_trend.change_rate},
            alt_label: {"end_value": a_trend.end_value, "change_rate": a_trend.change_rate},
        }

    # 最も差が大きいスキルを特定
    most_impacted = sorted(
        skill_diffs, key=lambda x: abs(x["demand_diff"]), reverse=True
    )

    return {
        "base_label": base_label,
        "alternative_label": alt_label,
        "simulation_months": base.simulation_months,
        "skill_comparison": skill_diffs,
        "macro_comparison": macro_diffs,
        "most_impacted_skills": [s["skill"] for s in most_impacted[:3]],
    }
