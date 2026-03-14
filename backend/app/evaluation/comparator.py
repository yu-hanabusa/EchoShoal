"""比較器 — シミュレーション結果と期待トレンドの比較・精度算出.

純粋関数のみで構成され、インフラ依存なし。
"""

from __future__ import annotations

import math

from app.evaluation.models import (
    BenchmarkScenario,
    EvaluationResult,
    ExpectedTrend,
    TrendDirection,
    TrendResult,
)
from app.prediction.trend import compute_trend
from app.simulation.models import Industry, RoundResult, SkillCategory

# 方向判定の閾値（変化率が±DIRECTION_THRESHOLD%以内ならSTABLE）
DIRECTION_THRESHOLD = 3.0

# getattr で安全にアクセス可能なMarketStateのスカラー属性
_ALLOWED_SCALAR_METRICS = frozenset({
    "unemployment_rate",
    "ai_automation_rate",
    "remote_work_rate",
    "overseas_outsource_rate",
    "average_age",
    "total_engineers",
})


# ─── メトリクス抽出 ───


def extract_metric_values(
    rounds: list[RoundResult],
    metric: str,
    start_round: int | None = None,
    end_round: int | None = None,
) -> list[float]:
    """メトリクスパスから時系列値を抽出する.

    パス形式:
      - "skill_demand.ai_ml" → MarketState.skill_demand[SkillCategory.AI_ML]
      - "unit_prices.cloud_infra" → MarketState.unit_prices[SkillCategory.CLOUD_INFRA]
      - "industry_growth.sier" → MarketState.industry_growth[Industry.SIER]
      - "unemployment_rate" → MarketState.unemployment_rate
    """
    # ラウンド範囲の絞り込み
    filtered = rounds
    if start_round is not None:
        filtered = [r for r in filtered if r.round_number >= start_round]
    if end_round is not None:
        filtered = [r for r in filtered if r.round_number <= end_round]

    if not filtered:
        return []

    parts = metric.split(".", 1)
    category = parts[0]

    values: list[float] = []
    for r in filtered:
        ms = r.market_state
        try:
            if category == "skill_demand" and len(parts) == 2:
                skill = SkillCategory(parts[1])
                values.append(ms.skill_demand.get(skill, 0.0))
            elif category == "skill_supply" and len(parts) == 2:
                skill = SkillCategory(parts[1])
                values.append(ms.skill_supply.get(skill, 0.0))
            elif category == "unit_prices" and len(parts) == 2:
                skill = SkillCategory(parts[1])
                values.append(ms.unit_prices.get(skill, 0.0))
            elif category == "industry_growth" and len(parts) == 2:
                industry = Industry(parts[1])
                values.append(ms.industry_growth.get(industry, 0.0))
            elif metric in _ALLOWED_SCALAR_METRICS:
                values.append(float(getattr(ms, metric)))
            else:
                return []
        except (ValueError, KeyError):
            return []

    return values


# ─── 方向判定 ───


def compute_actual_direction(values: list[float]) -> TrendDirection:
    """時系列値から実際のトレンド方向を判定する."""
    if len(values) < 2:
        return TrendDirection.STABLE

    trend = compute_trend(values)
    if trend.change_rate > DIRECTION_THRESHOLD:
        return TrendDirection.UP
    elif trend.change_rate < -DIRECTION_THRESHOLD:
        return TrendDirection.DOWN
    else:
        return TrendDirection.STABLE


# ─── 単一トレンド評価 ───


def evaluate_trend(
    expected: ExpectedTrend,
    rounds: list[RoundResult],
) -> TrendResult:
    """1つの期待トレンドを評価する."""
    values = extract_metric_values(
        rounds, expected.metric, expected.start_round, expected.end_round,
    )

    if not values or len(values) < 2:
        return TrendResult(
            metric=expected.metric,
            expected_direction=expected.direction,
            actual_direction=TrendDirection.STABLE,
            expected_magnitude=expected.magnitude,
            actual_change_rate=0.0,
            direction_correct=expected.direction == TrendDirection.STABLE,
            magnitude_error=1.0,
            score=0.0,
        )

    trend = compute_trend(values)
    actual_dir = compute_actual_direction(values)

    # 方向正解判定
    if expected.direction == TrendDirection.STABLE:
        direction_correct = actual_dir == TrendDirection.STABLE
    else:
        direction_correct = actual_dir == expected.direction

    # 規模誤差の計算（正規化）
    if expected.magnitude != 0.0:
        magnitude_error = abs(expected.magnitude - trend.change_rate) / max(
            abs(expected.magnitude), 1.0,
        )
    else:
        # STABLEの場合: 変化率の絶対値が小さいほど良い
        magnitude_error = min(abs(trend.change_rate) / 10.0, 1.0)

    magnitude_error = min(magnitude_error, 2.0)  # 上限クランプ

    # スコア算出: 方向70% + 規模30%
    score = 0.7 * float(direction_correct) + 0.3 * max(0.0, 1.0 - magnitude_error)

    return TrendResult(
        metric=expected.metric,
        expected_direction=expected.direction,
        actual_direction=actual_dir,
        expected_magnitude=expected.magnitude,
        actual_change_rate=round(trend.change_rate, 2),
        direction_correct=direction_correct,
        magnitude_error=round(magnitude_error, 4),
        score=round(score, 4),
    )


# ─── ピアソン相関 ───


def pearson_r(xs: list[float], ys: list[float]) -> float | None:
    """純粋Python実装のピアソン相関係数.

    データが不十分または分散ゼロの場合はNoneを返す。
    """
    n = len(xs)
    if n < 3 or n != len(ys):
        return None

    x_mean = sum(xs) / n
    y_mean = sum(ys) / n

    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    var_x = sum((x - x_mean) ** 2 for x in xs)
    var_y = sum((y - y_mean) ** 2 for y in ys)

    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return None

    return cov / denom


# ─── ベンチマーク全体評価 ───


def evaluate_benchmark(
    benchmark: BenchmarkScenario,
    rounds: list[RoundResult],
) -> EvaluationResult:
    """1つのベンチマーク全体を評価する."""
    trend_results = [
        evaluate_trend(et, rounds) for et in benchmark.expected_trends
    ]

    # 重み付き方向正解率
    total_weight = sum(
        et.weight for et in benchmark.expected_trends
    )
    if total_weight > 0:
        direction_accuracy = sum(
            tr.direction_correct * et.weight
            for tr, et in zip(trend_results, benchmark.expected_trends)
        ) / total_weight
    else:
        direction_accuracy = 0.0

    # 重み付き平均規模誤差
    if total_weight > 0:
        mean_magnitude_error = sum(
            tr.magnitude_error * et.weight
            for tr, et in zip(trend_results, benchmark.expected_trends)
        ) / total_weight
    else:
        mean_magnitude_error = 1.0

    # ピアソン相関（期待magnitudeと実際のchange_rate）
    expected_mags = [et.magnitude for et in benchmark.expected_trends]
    actual_rates = [tr.actual_change_rate for tr in trend_results]
    correlation = pearson_r(expected_mags, actual_rates)

    # 総合スコア: 方向60% + 規模30% + 相関10%
    clamped_mae = min(mean_magnitude_error, 1.0)
    corr_component = max(0.0, correlation) if correlation is not None else 0.0
    overall_score = (
        0.6 * direction_accuracy
        + 0.3 * (1.0 - clamped_mae)
        + 0.1 * corr_component
    )

    return EvaluationResult(
        benchmark_id=benchmark.id,
        benchmark_name=benchmark.name,
        trend_results=trend_results,
        direction_accuracy=round(direction_accuracy, 4),
        mean_magnitude_error=round(mean_magnitude_error, 4),
        correlation=round(correlation, 4) if correlation is not None else None,
        overall_score=round(overall_score, 4),
        simulation_rounds=len(rounds),
    )
