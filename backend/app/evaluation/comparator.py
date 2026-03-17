"""比較器 — シミュレーション結果と期待トレンドの比較.

設計方針:
  - 評価はトレンド方向の一致のみ（UP/DOWN/STABLE）
  - 恣意的な重み・規模スコアは一切使わない
  - 全トレンドを均等に扱い、単純な正解率で評価する

純粋関数のみで構成され、インフラ依存なし。
"""

from __future__ import annotations

from app.evaluation.models import (
    BenchmarkScenario,
    EvaluationResult,
    ExpectedTrend,
    TrendDirection,
    TrendResult,
)
from app.prediction.trend import compute_trend
from app.simulation.models import RoundResult, MarketDimension

# 方向判定の閾値（変化率が±DIRECTION_THRESHOLD%以内ならSTABLE）
DIRECTION_THRESHOLD = 3.0

# getattr で安全にアクセス可能なServiceMarketStateのスカラー属性
_ALLOWED_SCALAR_METRICS = frozenset({
    "economic_sentiment",
    "tech_hype_level",
    "regulatory_pressure",
    "remote_work_adoption",
    "ai_disruption_level",
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
      - "dimensions.user_adoption" → ServiceMarketState.dimensions[MarketDimension.USER_ADOPTION]
      - "economic_sentiment" → ServiceMarketState.economic_sentiment
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
            if category == "dimensions" and len(parts) == 2:
                dim = MarketDimension(parts[1])
                values.append(ms.dimensions.get(dim, 0.0))
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
    """1つの期待トレンドを評価する（方向の一致のみ）."""
    values = extract_metric_values(
        rounds, expected.metric, expected.start_round, expected.end_round,
    )

    if not values or len(values) < 2:
        return TrendResult(
            metric=expected.metric,
            expected_direction=expected.direction,
            actual_direction=TrendDirection.STABLE,
            actual_change_rate=0.0,
            direction_correct=expected.direction == TrendDirection.STABLE,
        )

    trend = compute_trend(values)
    actual_dir = compute_actual_direction(values)

    direction_correct = actual_dir == expected.direction

    return TrendResult(
        metric=expected.metric,
        expected_direction=expected.direction,
        actual_direction=actual_dir,
        actual_change_rate=round(trend.change_rate, 2),
        direction_correct=direction_correct,
    )


# ─── ベンチマーク全体評価 ───


def evaluate_benchmark(
    benchmark: BenchmarkScenario,
    rounds: list[RoundResult],
) -> EvaluationResult:
    """1つのベンチマーク全体を評価する（方向正解率のみ）."""
    trend_results = [
        evaluate_trend(et, rounds) for et in benchmark.expected_trends
    ]

    if trend_results:
        direction_accuracy = sum(
            tr.direction_correct for tr in trend_results
        ) / len(trend_results)
    else:
        direction_accuracy = 0.0

    return EvaluationResult(
        benchmark_id=benchmark.id,
        benchmark_name=benchmark.name,
        trend_results=trend_results,
        direction_accuracy=round(direction_accuracy, 4),
        simulation_rounds=len(rounds),
    )
