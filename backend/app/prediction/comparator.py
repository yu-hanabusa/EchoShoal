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
    dim_diffs = []

    base_dims = {dp.dimension: dp for dp in base.dimension_predictions}
    alt_dims = {dp.dimension: dp for dp in alternative.dimension_predictions}

    for dim_key in base_dims:
        b = base_dims[dim_key]
        a = alt_dims.get(dim_key)
        if a is None:
            continue

        dim_diffs.append({
            "dimension": dim_key,
            "value_diff": round(a.predicted_value - b.predicted_value, 4),
            base_label: {
                "value": b.predicted_value,
            },
            alt_label: {
                "value": a.predicted_value,
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

    # 最も差が大きいディメンションを特定
    most_impacted = sorted(
        dim_diffs, key=lambda x: abs(x["value_diff"]), reverse=True
    )

    return {
        "base_label": base_label,
        "alternative_label": alt_label,
        "simulation_months": base.simulation_months,
        "dimension_comparison": dim_diffs,
        "macro_comparison": macro_diffs,
        "most_impacted_dimensions": [d["dimension"] for d in most_impacted[:3]],
    }
