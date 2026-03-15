"""トレンド分析 — 純粋Python実装の線形回帰・移動平均."""

from __future__ import annotations

from app.prediction.models import (
    PredictionResult,
    DimensionPrediction,
    TrendData,
)
from app.reports.extractor import (
    extract_macro_timeline,
    extract_dimension_timeline,
)
from app.simulation.models import RoundResult, MarketDimension


def linear_regression(values: list[float]) -> tuple[float, float]:
    """最小二乗法で傾きと切片を計算する.

    Returns: (slope, intercept)
    """
    n = len(values)
    if n < 2:
        return 0.0, values[0] if values else 0.0

    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0, y_mean

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    return slope, intercept


def moving_average(values: list[float], window: int = 3) -> list[float]:
    """単純移動平均を計算する."""
    if len(values) < window:
        return list(values)
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        subset = values[start:i + 1]
        result.append(sum(subset) / len(subset))
    return result


def compute_trend(values: list[float], window: int = 3) -> TrendData:
    """時系列データのトレンドを計算する."""
    if not values:
        return TrendData(values=[])

    slope, _ = linear_regression(values)
    start = values[0]
    end = values[-1]
    change_rate = ((end - start) / abs(start) * 100) if start != 0 else 0.0

    return TrendData(
        values=values,
        slope=round(slope, 6),
        start_value=round(start, 4),
        end_value=round(end, 4),
        change_rate=round(change_rate, 2),
        moving_avg=[round(v, 4) for v in moving_average(values, window)],
    )


def predict_from_results(
    rounds: list[RoundResult],
) -> PredictionResult:
    """シミュレーション結果から定量予測を生成する."""
    if not rounds:
        return PredictionResult(simulation_months=0)

    dim_timeline = extract_dimension_timeline(rounds)
    macro_timeline = extract_macro_timeline(rounds)

    # ディメンション別予測
    dim_predictions = []
    for dim in MarketDimension:
        d_values = dim_timeline.get(dim.value, [])
        d_trend = compute_trend(d_values)

        dim_predictions.append(DimensionPrediction(
            dimension=dim.value,
            current_value=round(d_values[-1], 4) if d_values else 0.0,
            predicted_value=round(d_values[-1] + d_trend.slope * 6, 4) if d_values else 0.0,
            trend=d_trend,
        ))

    # マクロ予測
    macro_predictions = {}
    for key, values in macro_timeline.items():
        macro_predictions[key] = compute_trend(values)

    # ハイライト生成
    highlights = _generate_highlights(dim_predictions, macro_predictions)

    return PredictionResult(
        simulation_months=len(rounds),
        dimension_predictions=dim_predictions,
        macro_predictions=macro_predictions,
        highlights=highlights,
    )


def _generate_highlights(
    dims: list[DimensionPrediction],
    macros: dict[str, TrendData],
) -> list[str]:
    """主要な予測ハイライトを自動生成する."""
    highlights = []

    if dims:
        # 最も成長したディメンション
        top_growth = max(dims, key=lambda d: d.trend.change_rate)
        if top_growth.trend.change_rate > 5:
            highlights.append(
                f"{top_growth.dimension} が最も成長（{top_growth.trend.change_rate:+.1f}%）"
            )

        # 最も低下したディメンション
        top_decline = min(dims, key=lambda d: d.trend.change_rate)
        if top_decline.trend.change_rate < -5:
            highlights.append(
                f"{top_decline.dimension} が最も低下（{top_decline.trend.change_rate:+.1f}%）"
            )

        # competitive_pressureが高い場合の警告
        cp = next((d for d in dims if d.dimension == "competitive_pressure"), None)
        if cp and cp.predicted_value > 0.7:
            highlights.append(
                f"競合圧力が高水準（予測値: {cp.predicted_value:.2f}）— 差別化戦略が重要"
            )

        # user_adoptionの評価
        ua = next((d for d in dims if d.dimension == "user_adoption"), None)
        if ua and ua.predicted_value > 0.6:
            highlights.append(
                f"ユーザー獲得率が良好（予測値: {ua.predicted_value:.2f}）— 市場浸透の可能性が高い"
            )
        elif ua and ua.predicted_value < 0.2:
            highlights.append(
                f"ユーザー獲得率が低水準（予測値: {ua.predicted_value:.2f}）— マーケティング戦略の見直しが必要"
            )

    # AI破壊度
    ai_trend = macros.get("ai_disruption_level")
    if ai_trend and ai_trend.change_rate > 10:
        highlights.append(
            f"AI破壊度が上昇中（{ai_trend.end_value:.2f}、{ai_trend.change_rate:+.1f}%）"
        )

    return highlights
