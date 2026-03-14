"""トレンド分析 — 純粋Python実装の線形回帰・移動平均."""

from __future__ import annotations

from app.prediction.models import (
    PredictionResult,
    SkillPrediction,
    TrendData,
)
from app.reports.extractor import (
    extract_macro_timeline,
    extract_price_timeline,
    extract_skill_demand_timeline,
)
from app.simulation.models import MarketState, RoundResult, SkillCategory


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
    total_engineers: int = 1_090_000,
) -> PredictionResult:
    """シミュレーション結果から定量予測を生成する."""
    if not rounds:
        return PredictionResult(simulation_months=0)

    demand_timeline = extract_skill_demand_timeline(rounds)
    price_timeline = extract_price_timeline(rounds)
    macro_timeline = extract_macro_timeline(rounds)

    final_market = rounds[-1].market_state

    # スキル別予測
    skill_predictions = []
    for skill in SkillCategory:
        d_values = demand_timeline.get(skill.value, [])
        p_values = price_timeline.get(skill.value, [])

        d_trend = compute_trend(d_values)
        p_trend = compute_trend(p_values)

        # 不足人数の推定:
        # demand_supply_ratio > 1 なら需要超過
        ratio = final_market.demand_supply_ratio(skill)
        shortage = 0
        if ratio > 1.0:
            # 超過分 × 全エンジニア数 × スキル需要比率
            demand_share = final_market.skill_demand.get(skill, 0.0)
            shortage = int(total_engineers * demand_share * (ratio - 1.0) / ratio)

        skill_predictions.append(SkillPrediction(
            skill=skill.value,
            current_demand=round(d_values[-1], 4) if d_values else 0.0,
            predicted_demand=round(d_values[-1] + d_trend.slope * 6, 4) if d_values else 0.0,
            demand_trend=d_trend,
            current_price=round(p_values[-1], 1) if p_values else 0.0,
            predicted_price=round(p_values[-1] + p_trend.slope * 6, 1) if p_values else 0.0,
            price_trend=p_trend,
            shortage_estimate=shortage,
        ))

    # マクロ予測
    macro_predictions = {}
    for key, values in macro_timeline.items():
        macro_predictions[key] = compute_trend(values)

    # ハイライト生成
    highlights = _generate_highlights(skill_predictions, macro_predictions)

    return PredictionResult(
        simulation_months=len(rounds),
        total_engineers=total_engineers,
        skill_predictions=skill_predictions,
        macro_predictions=macro_predictions,
        highlights=highlights,
    )


def _generate_highlights(
    skills: list[SkillPrediction],
    macros: dict[str, TrendData],
) -> list[str]:
    """主要な予測ハイライトを自動生成する."""
    highlights = []

    # 需要増加が最も大きいスキル
    if skills:
        top_growth = max(skills, key=lambda s: s.demand_trend.change_rate)
        if top_growth.demand_trend.change_rate > 5:
            highlights.append(
                f"{top_growth.skill} の需要が最も増加（{top_growth.demand_trend.change_rate:+.1f}%）"
            )

        # 需要減少が最も大きいスキル
        top_decline = min(skills, key=lambda s: s.demand_trend.change_rate)
        if top_decline.demand_trend.change_rate < -5:
            highlights.append(
                f"{top_decline.skill} の需要が最も減少（{top_decline.demand_trend.change_rate:+.1f}%）"
            )

        # 人材不足が深刻なスキル
        shortage_skills = sorted(skills, key=lambda s: s.shortage_estimate, reverse=True)
        for sp in shortage_skills[:2]:
            if sp.shortage_estimate > 1000:
                highlights.append(
                    f"{sp.skill} で約{sp.shortage_estimate:,}人の人材不足が予測"
                )

        # 単価上昇が大きいスキル
        top_price = max(skills, key=lambda s: s.price_trend.change_rate)
        if top_price.price_trend.change_rate > 3:
            highlights.append(
                f"{top_price.skill} の単価が{top_price.predicted_price:.0f}万円/月に上昇見込み"
            )

    # AI自動化率
    ai_trend = macros.get("ai_automation_rate")
    if ai_trend and ai_trend.change_rate > 10:
        highlights.append(
            f"AI自動化率が{ai_trend.end_value:.1%}に上昇（{ai_trend.change_rate:+.1f}%）"
        )

    return highlights
