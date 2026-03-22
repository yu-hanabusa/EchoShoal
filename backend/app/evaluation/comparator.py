"""比較器 — シミュレーション結果と期待トレンドの比較.

設計方針:
  - 評価はトレンド方向の一致のみ（UP/DOWN/STABLE）
  - 恣意的な重み・規模スコアは一切使わない
  - 全トレンドを均等に扱い、単純な正解率で評価する

純粋関数のみで構成され、インフラ依存なし。
"""

from __future__ import annotations

from collections import Counter

from app.evaluation.models import (
    BaselineAccuracy,
    BenchmarkScenario,
    EvaluationResult,
    ExpectedOutcome,
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


# ─── 成功/失敗予測評価 ───


def evaluate_outcome(
    expected_outcome: ExpectedOutcome | None,
    success_score: dict | None,
) -> tuple[bool | None, int | None, str | None]:
    """成功/失敗予測の正誤を判定する.

    Returns:
        (outcome_correct, predicted_score, predicted_verdict)
    """
    if expected_outcome is None or success_score is None:
        return None, None, None

    score = success_score.get("score")
    verdict = success_score.get("verdict", "")

    if score is None:
        return None, None, None

    # 50は0-100の自然な中間点: >= 50は成功予測、< 50は失敗予測
    predicted_success = score >= 50
    expected_success = expected_outcome == ExpectedOutcome.SUCCESS

    return predicted_success == expected_success, score, verdict


# ─── ベースライン計算 ───


def compute_baseline(expected_trends: list[ExpectedTrend]) -> BaselineAccuracy:
    """ナイーブベースラインの精度を計算する.

    「全トレンドをUPと予測」「最頻方向で全予測」した場合の正解率を返す。
    シミュレーターが偶然以上の予測力を持つかの判定に使う。
    """
    if not expected_trends:
        return BaselineAccuracy(
            all_up_accuracy=0.0,
            majority_class_accuracy=0.0,
            lift_over_baseline=0.0,
        )

    total = len(expected_trends)
    directions = [et.direction for et in expected_trends]

    # 全UPベースライン
    all_up_correct = sum(1 for d in directions if d == TrendDirection.UP)
    all_up_accuracy = all_up_correct / total

    # 最頻方向ベースライン（多数決）
    counts = Counter(directions)
    majority_correct = counts.most_common(1)[0][1]
    majority_class_accuracy = majority_correct / total

    return BaselineAccuracy(
        all_up_accuracy=round(all_up_accuracy, 4),
        majority_class_accuracy=round(majority_class_accuracy, 4),
        lift_over_baseline=0.0,  # 後でシミュレーター精度と比較して設定
    )


# ─── ベンチマーク全体評価 ───


def evaluate_benchmark(
    benchmark: BenchmarkScenario,
    rounds: list[RoundResult],
    success_score: dict | None = None,
) -> EvaluationResult:
    """1つのベンチマーク全体を評価する（方向正解率 + 成功予測 + ベースライン比較）."""
    trend_results = [
        evaluate_trend(et, rounds) for et in benchmark.expected_trends
    ]

    if trend_results:
        direction_accuracy = sum(
            tr.direction_correct for tr in trend_results
        ) / len(trend_results)
    else:
        direction_accuracy = 0.0

    # ベースライン比較
    baseline = compute_baseline(benchmark.expected_trends)
    baseline.lift_over_baseline = round(
        direction_accuracy - baseline.majority_class_accuracy, 4,
    )

    # 成功/失敗予測の評価
    outcome_correct, predicted_score, predicted_verdict = evaluate_outcome(
        benchmark.expected_outcome, success_score,
    )

    # combined_accuracy: direction_accuracyとoutcome正誤の単純平均
    combined_accuracy = None
    if outcome_correct is not None:
        outcome_value = 1.0 if outcome_correct else 0.0
        combined_accuracy = round((direction_accuracy + outcome_value) / 2, 4)

    return EvaluationResult(
        benchmark_id=benchmark.id,
        benchmark_name=benchmark.name,
        trend_results=trend_results,
        direction_accuracy=round(direction_accuracy, 4),
        simulation_rounds=len(rounds),
        baseline=baseline,
        expected_outcome=(
            benchmark.expected_outcome.value if benchmark.expected_outcome else None
        ),
        predicted_score=predicted_score,
        predicted_verdict=predicted_verdict,
        outcome_correct=outcome_correct,
        combined_accuracy=combined_accuracy,
    )
