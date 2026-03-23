"""LLM知識汚染テスト（Contamination A/B Test）.

同一シナリオを実名版と匿名化版で実行し、方向一致率の差分から
LLMの学習データに含まれる結果情報によるバイアスを定量的に測定する。

  A（実名版）: LLMは学習データの知識を活用できる
  B（匿名版）: LLMはシナリオの構造的分析のみで予測する
  差分 = LLMの事前知識バイアスの大きさ

公平性の担保:
  両版とも補足資料（scenarios/ディレクトリ）を使わない。
  これにより「実名版だけ補足資料がある」という不公平を排除する。
"""

from __future__ import annotations

import logging
import time
from enum import Enum

from pydantic import BaseModel, Field

from app.core.job_manager import JobManager
from app.evaluation.benchmarks import ANONYMIZATION_MAPS, get_benchmark, list_benchmarks
from app.evaluation.models import EvaluationResult

logger = logging.getLogger(__name__)


class ContaminationLevel(str, Enum):
    """汚染レベル."""

    NONE = "none"          # ≤ 5pp
    LOW = "low"            # 5-15pp
    MODERATE = "moderate"  # 15-30pp
    HIGH = "high"          # > 30pp
    NEGATIVE = "negative"  # < -5pp (匿名版の方が高い)


class ContaminationResult(BaseModel):
    """単一ベンチマークのA/Bテスト結果."""

    benchmark_id: str
    benchmark_name: str
    # A（実名版）
    real_accuracy: float
    real_outcome_correct: bool | None = None
    # B（匿名版）
    anon_accuracy: float
    anon_outcome_correct: bool | None = None
    # 汚染指標
    contamination_score: float  # real - anon (パーセントポイント)
    contamination_ratio: float  # score / real (0除算時は0)
    contamination_level: ContaminationLevel
    execution_time_seconds: float = 0.0


class ContaminationSuiteResult(BaseModel):
    """全ベンチマークの汚染テスト結果."""

    results: list[ContaminationResult]
    mean_contamination_score: float
    mean_real_accuracy: float
    mean_anon_accuracy: float
    total_benchmarks: int
    execution_time_seconds: float = 0.0


class ContaminationStatResult(BaseModel):
    """単一ベンチマークの統計的A/Bテスト結果（複数回実行）."""

    benchmark_id: str
    benchmark_name: str
    num_runs: int
    # 実名版の統計
    real_mean_accuracy: float
    real_accuracies: list[float] = Field(default_factory=list)
    # 匿名版の統計
    anon_mean_accuracy: float
    anon_accuracies: list[float] = Field(default_factory=list)
    # 汚染指標
    contamination_score: float
    contamination_level: ContaminationLevel
    execution_time_seconds: float = 0.0


def _classify_contamination(score: float) -> ContaminationLevel:
    """汚染スコアからレベルを分類する."""
    if score < -5:
        return ContaminationLevel.NEGATIVE
    if score <= 5:
        return ContaminationLevel.NONE
    if score <= 15:
        return ContaminationLevel.LOW
    if score <= 30:
        return ContaminationLevel.MODERATE
    return ContaminationLevel.HIGH


def _build_contamination_result(
    benchmark_id: str,
    benchmark_name: str,
    real_eval: EvaluationResult,
    anon_eval: EvaluationResult,
    elapsed: float,
) -> ContaminationResult:
    """実名版と匿名版の結果から汚染指標を算出する."""
    real_acc = real_eval.direction_accuracy * 100
    anon_acc = anon_eval.direction_accuracy * 100
    score = real_acc - anon_acc
    ratio = score / real_acc if real_acc > 0 else 0.0

    return ContaminationResult(
        benchmark_id=benchmark_id,
        benchmark_name=benchmark_name,
        real_accuracy=round(real_eval.direction_accuracy, 4),
        real_outcome_correct=real_eval.outcome_correct,
        anon_accuracy=round(anon_eval.direction_accuracy, 4),
        anon_outcome_correct=anon_eval.outcome_correct,
        contamination_score=round(score, 2),
        contamination_ratio=round(ratio, 4),
        contamination_level=_classify_contamination(score),
        execution_time_seconds=round(elapsed, 2),
    )


async def run_contamination_test(
    benchmark_id: str,
    job_manager: JobManager,
) -> ContaminationResult:
    """単一ベンチマークのA/Bテストを実行する.

    1. 実名版を実行（補足資料なし）
    2. 匿名版を実行（補足資料なし）
    3. 差分を計算
    """
    from app.evaluation.runner import run_benchmark

    benchmark = get_benchmark(benchmark_id)
    if benchmark is None:
        msg = f"ベンチマーク '{benchmark_id}' が見つかりません"
        raise ValueError(msg)
    if benchmark_id not in ANONYMIZATION_MAPS:
        msg = f"ベンチマーク '{benchmark_id}' に匿名化マッピングがありません"
        raise ValueError(msg)

    start_time = time.monotonic()

    # A: 実名版（補足資料なし）
    logger.info("汚染テスト A（実名版）開始: %s", benchmark_id)
    real_eval = await run_benchmark(
        benchmark_id, job_manager, anonymize=False, skip_scenario_docs=True,
    )

    # B: 匿名版（補足資料なし）
    logger.info("汚染テスト B（匿名版）開始: %s", benchmark_id)
    anon_eval = await run_benchmark(
        benchmark_id, job_manager, anonymize=True, skip_scenario_docs=True,
    )

    elapsed = time.monotonic() - start_time
    result = _build_contamination_result(
        benchmark_id, benchmark.name, real_eval, anon_eval, elapsed,
    )

    logger.info(
        "汚染テスト完了: %s -実名=%.2f, 匿名=%.2f, 汚染=%+.1fpp (%s)",
        benchmark.name,
        result.real_accuracy,
        result.anon_accuracy,
        result.contamination_score,
        result.contamination_level.value,
    )
    return result


async def run_contamination_test_multi(
    benchmark_id: str,
    job_manager: JobManager,
    num_runs: int = 3,
) -> ContaminationStatResult:
    """単一ベンチマークの統計的A/Bテストを実行する."""
    from app.evaluation.runner import run_benchmark

    benchmark = get_benchmark(benchmark_id)
    if benchmark is None:
        msg = f"ベンチマーク '{benchmark_id}' が見つかりません"
        raise ValueError(msg)

    start_time = time.monotonic()
    real_accuracies: list[float] = []
    anon_accuracies: list[float] = []

    for i in range(num_runs):
        logger.info("汚染テスト 実行 %d/%d: %s", i + 1, num_runs, benchmark_id)

        try:
            real_eval = await run_benchmark(
                benchmark_id, job_manager, anonymize=False, skip_scenario_docs=True,
            )
            real_accuracies.append(real_eval.direction_accuracy)
        except Exception:
            logger.exception("実名版 %d/%d 失敗", i + 1, num_runs)

        try:
            anon_eval = await run_benchmark(
                benchmark_id, job_manager, anonymize=True, skip_scenario_docs=True,
            )
            anon_accuracies.append(anon_eval.direction_accuracy)
        except Exception:
            logger.exception("匿名版 %d/%d 失敗", i + 1, num_runs)

    real_mean = sum(real_accuracies) / len(real_accuracies) if real_accuracies else 0.0
    anon_mean = sum(anon_accuracies) / len(anon_accuracies) if anon_accuracies else 0.0
    score = (real_mean - anon_mean) * 100

    elapsed = time.monotonic() - start_time

    return ContaminationStatResult(
        benchmark_id=benchmark_id,
        benchmark_name=benchmark.name,
        num_runs=num_runs,
        real_mean_accuracy=round(real_mean, 4),
        real_accuracies=[round(a, 4) for a in real_accuracies],
        anon_mean_accuracy=round(anon_mean, 4),
        anon_accuracies=[round(a, 4) for a in anon_accuracies],
        contamination_score=round(score, 2),
        contamination_level=_classify_contamination(score),
        execution_time_seconds=round(elapsed, 2),
    )


async def run_contamination_suite(
    job_manager: JobManager,
) -> ContaminationSuiteResult:
    """全ベンチマークの汚染テストを実行する."""
    start_time = time.monotonic()
    results: list[ContaminationResult] = []

    for benchmark in list_benchmarks():
        if benchmark.id not in ANONYMIZATION_MAPS:
            continue
        try:
            result = await run_contamination_test(benchmark.id, job_manager)
            results.append(result)
        except Exception:
            logger.exception("汚染テスト '%s' をスキップ", benchmark.id)

    elapsed = time.monotonic() - start_time

    mean_score = (
        sum(r.contamination_score for r in results) / len(results)
        if results else 0.0
    )
    mean_real = (
        sum(r.real_accuracy for r in results) / len(results)
        if results else 0.0
    )
    mean_anon = (
        sum(r.anon_accuracy for r in results) / len(results)
        if results else 0.0
    )

    return ContaminationSuiteResult(
        results=results,
        mean_contamination_score=round(mean_score, 2),
        mean_real_accuracy=round(mean_real, 4),
        mean_anon_accuracy=round(mean_anon, 4),
        total_benchmarks=len(results),
        execution_time_seconds=round(elapsed, 2),
    )
