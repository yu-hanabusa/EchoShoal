"""全ベンチマーク統計評価 — 全9シナリオ×5回実行してレポート出力.

使い方:
  cd backend
  uv run python scripts/run_full_benchmark.py

出力:
  backend/benchmark_report.txt — 全結果のレポート

前提:
  - Docker (Neo4j + Redis) が起動していること
  - Ollama が起動していること (qwen2.5:14b)
"""

from __future__ import annotations

import asyncio
import logging
import math
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.job_manager import JobManager  # noqa: E402
from app.core.redis_client import RedisClient  # noqa: E402
from app.evaluation.benchmarks import get_benchmark, list_benchmarks  # noqa: E402
from app.evaluation.models import EvaluationResult, RunStatistics  # noqa: E402
from app.evaluation.runner import run_benchmark_multi  # noqa: E402

NUM_RUNS = 5
REPORT_PATH = Path(__file__).resolve().parent.parent / "benchmark_report.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark")

# 内部ログを抑制
for name in ("app.simulation", "app.core.llm", "app.core.graph",
             "app.core.nlp", "app.oasis", "httpx", "httpcore"):
    logging.getLogger(name).setLevel(logging.WARNING)


async def check_infrastructure() -> bool:
    """インフラの接続確認."""
    errors = []
    try:
        redis = RedisClient()
        if not await redis.is_available():
            errors.append("Redis")
        await redis.close()
    except Exception:
        errors.append("Redis")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code != 200:
                errors.append("Ollama")
    except Exception:
        errors.append("Ollama")

    if errors:
        logger.error("接続失敗: %s — docker compose up -d && ollama serve", ", ".join(errors))
        return False
    return True


def _confidence_interval_95(values: list[float]) -> tuple[float, float]:
    """95%信頼区間を計算する（t分布近似）."""
    n = len(values)
    if n < 2:
        mean = values[0] if values else 0.0
        return (mean, mean)

    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    stderr = math.sqrt(variance / n)

    # t値の近似（n=5: 2.776, n=10: 2.262, n>=30: ~1.96）
    t_values = {2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
                6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
    t_val = t_values.get(n, 1.96)

    margin = t_val * stderr
    return (max(0.0, mean - margin), min(1.0, mean + margin))


def build_report(
    all_stats: list[tuple[str, str, list[str], RunStatistics]],
    total_elapsed: float,
) -> str:
    """レポートテキストを生成する."""
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append("=" * 78)
    lines.append("EchoShoal ベンチマーク評価レポート")
    lines.append(f"実行日時: {now}")
    lines.append(f"各シナリオ実行回数: {NUM_RUNS}")
    lines.append(f"総実行時間: {total_elapsed:.0f}秒 ({total_elapsed / 60:.1f}分)")
    lines.append("=" * 78)

    # ═══════════════════════════════════════════════════════════════
    #  1. 全体サマリー
    # ═══════════════════════════════════════════════════════════════
    lines.append("")
    lines.append("■ 全体サマリー")
    lines.append("")
    lines.append(
        f"{'シナリオ':<30} {'種別':<6} {'平均精度':>8} {'σ':>7} "
        f"{'95%CI':>14} {'最小':>6} {'最大':>6} {'判定'}"
    )
    lines.append("-" * 78)

    total_mean = 0.0
    pass_count = 0

    for name, bench_id, tags, stats in all_stats:
        tag = "成功" if "success" in tags else "失敗"
        passed = stats.mean_direction_accuracy >= 0.6
        marker = "PASS" if passed else "FAIL"
        if passed:
            pass_count += 1
        total_mean += stats.mean_direction_accuracy

        accuracies = [r.direction_accuracy for r in stats.per_run_results]
        ci_low, ci_high = _confidence_interval_95(accuracies)

        lines.append(
            f"{name:<30} {tag:<6} "
            f"{stats.mean_direction_accuracy:>7.1%} "
            f"{stats.stddev_direction_accuracy:>7.4f} "
            f"[{ci_low:.1%}-{ci_high:.1%}] "
            f"{stats.min_direction_accuracy:>5.1%} "
            f"{stats.max_direction_accuracy:>5.1%} "
            f"[{marker}]"
        )

    lines.append("-" * 78)
    overall_mean = total_mean / len(all_stats) if all_stats else 0
    lines.append(f"全体平均方向精度: {overall_mean:.1%}")
    lines.append(f"合格シナリオ: {pass_count}/{len(all_stats)} (閾値: 60%)")

    # 成功/失敗別
    success_accs = [s.mean_direction_accuracy for _, _, t, s in all_stats if "success" in t]
    failure_accs = [s.mean_direction_accuracy for _, _, t, s in all_stats if "failure" in t]
    if success_accs:
        lines.append(f"成功事例の平均精度: {sum(success_accs)/len(success_accs):.1%} ({len(success_accs)}件)")
    if failure_accs:
        lines.append(f"失敗事例の平均精度: {sum(failure_accs)/len(failure_accs):.1%} ({len(failure_accs)}件)")

    # ═══════════════════════════════════════════════════════════════
    #  2. 各シナリオの詳細
    # ═══════════════════════════════════════════════════════════════
    for name, bench_id, tags, stats in all_stats:
        benchmark = get_benchmark(bench_id)
        lines.append("")
        lines.append("=" * 78)
        tag = "成功事例" if "success" in tags else "失敗事例"
        lines.append(f"■ {name} ({tag})")
        lines.append("=" * 78)

        # シナリオ説明
        if benchmark:
            lines.append("")
            lines.append("  【シナリオ説明】")
            desc = benchmark.scenario_input.description
            # 80文字ごとに折り返し
            while desc:
                lines.append(f"  {desc[:76]}")
                desc = desc[76:]

        # 統計サマリー
        lines.append("")
        lines.append("  【統計サマリー】")
        lines.append(f"  実行回数: {stats.num_runs}")
        lines.append(f"  成功実行: {len(stats.per_run_results)}/{stats.num_runs}")
        lines.append(f"  平均方向精度: {stats.mean_direction_accuracy:.1%}")
        lines.append(f"  標準偏差: {stats.stddev_direction_accuracy:.4f}")
        lines.append(f"  範囲: {stats.min_direction_accuracy:.1%} 〜 {stats.max_direction_accuracy:.1%}")

        accuracies = [r.direction_accuracy for r in stats.per_run_results]
        ci_low, ci_high = _confidence_interval_95(accuracies)
        lines.append(f"  95%信頼区間: [{ci_low:.1%} - {ci_high:.1%}]")

        # 各実行の結果
        lines.append("")
        lines.append("  【各実行の方向精度】")
        for i, r in enumerate(stats.per_run_results, 1):
            lines.append(f"    実行{i}: {r.direction_accuracy:.1%} ({r.execution_time_seconds:.0f}秒)")

        # トレンド別ヒット率
        lines.append("")
        lines.append("  【トレンド別ヒット率】")
        for metric, rate in stats.per_trend_hit_rates.items():
            hits = int(rate * len(stats.per_run_results))
            total = len(stats.per_run_results)
            marker = "OK" if rate >= 0.6 else "!!"
            lines.append(f"    [{marker}] {metric:<40} {hits}/{total} ({rate:.0%})")

        # エージェント一覧（最初の実行から）
        if stats.per_run_results and stats.per_run_results[0].agents:
            lines.append("")
            lines.append("  【生成されたエージェント（実行1の例）】")
            for ag in stats.per_run_results[0].agents:
                actions_str = ", ".join(ag.actions[:5]) if ag.actions else "記録なし"
                lines.append(f"    - {ag.name} ({ag.stakeholder_type}): {actions_str}")

        # ディメンション推移（最初の実行から）
        if stats.per_run_results and stats.per_run_results[0].dimension_timelines:
            lines.append("")
            lines.append("  【ディメンション推移（実行1）】")
            for dt in stats.per_run_results[0].dimension_timelines:
                if not dt.values:
                    continue
                start_v = dt.values[0]
                end_v = dt.values[-1]
                change = end_v - start_v
                direction = "↑" if change > 0.03 else ("↓" if change < -0.03 else "→")
                sparkline = _make_sparkline(dt.values)
                lines.append(
                    f"    {dt.dimension:<25} "
                    f"{start_v:.2f} → {end_v:.2f} ({change:+.2f}) {direction}  "
                    f"{sparkline}"
                )

        # 各実行のトレンド詳細
        lines.append("")
        lines.append("  【各実行のトレンド詳細】")
        for i, r in enumerate(stats.per_run_results, 1):
            lines.append(f"    --- 実行{i} (方向精度: {r.direction_accuracy:.1%}) ---")
            for tr in r.trend_results:
                marker = "OK" if tr.direction_correct else "NG"
                lines.append(
                    f"      [{marker}] {tr.metric:<35} "
                    f"期待={tr.expected_direction.value:<6} "
                    f"実際={tr.actual_direction.value:<6} "
                    f"変化率={tr.actual_change_rate:+.1f}%"
                )

    # ═══════════════════════════════════════════════════════════════
    #  3. 結論
    # ═══════════════════════════════════════════════════════════════
    lines.append("")
    lines.append("=" * 78)
    lines.append("■ 結論")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"  全体平均方向精度: {overall_mean:.1%}")
    if success_accs:
        lines.append(f"  成功事例平均: {sum(success_accs)/len(success_accs):.1%}")
    if failure_accs:
        lines.append(f"  失敗事例平均: {sum(failure_accs)/len(failure_accs):.1%}")
    lines.append(f"  合格シナリオ: {pass_count}/{len(all_stats)}")
    lines.append("")

    if overall_mean >= 0.7:
        lines.append("  評価: シミュレータは高い方向予測精度を示している。")
        lines.append("  歴史的事例の市場トレンド方向を概ね正確に再現できている。")
    elif overall_mean >= 0.5:
        lines.append("  評価: シミュレータは一定の方向予測精度を示しているが、改善の余地がある。")
        lines.append("  一部のトレンドについては方向を正しく予測できていない。")
    else:
        lines.append("  評価: シミュレータの方向予測精度は不十分。")
        lines.append("  シナリオ設計またはエンジンの改善が必要。")

    # 安定性評価
    all_stddevs = [s.stddev_direction_accuracy for _, _, _, s in all_stats]
    mean_stddev = sum(all_stddevs) / len(all_stddevs) if all_stddevs else 0
    lines.append("")
    lines.append(f"  再現性（標準偏差の平均）: {mean_stddev:.4f}")
    if mean_stddev < 0.1:
        lines.append("  → 再現性は高い。同一シナリオの繰り返し実行で安定した結果が得られている。")
    elif mean_stddev < 0.2:
        lines.append("  → 再現性は中程度。LLMの非決定性による結果のばらつきがある。")
    else:
        lines.append("  → 再現性は低い。結果が実行ごとに大きくばらつく。")

    lines.append("")
    return "\n".join(lines)


def _make_sparkline(values: list[float]) -> str:
    """数値列からASCIIスパークラインを生成する."""
    if not values:
        return ""
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0
    return "".join(
        blocks[min(8, int((v - mn) / rng * 8))] for v in values
    )


async def main() -> None:
    logger.info("=== 全ベンチマーク統計評価 (各%d回) ===", NUM_RUNS)

    if not await check_infrastructure():
        sys.exit(1)

    redis = RedisClient()
    job_manager = JobManager(redis)
    benchmarks = list_benchmarks()

    logger.info(
        "対象: %d件 × %d回 = %d回のシミュレーション",
        len(benchmarks), NUM_RUNS, len(benchmarks) * NUM_RUNS,
    )

    start_time = time.monotonic()
    all_stats: list[tuple[str, str, list[str], RunStatistics]] = []

    for i, benchmark in enumerate(benchmarks, 1):
        logger.info(
            "\n[%d/%d] %s (%d回実行開始)",
            i, len(benchmarks), benchmark.name, NUM_RUNS,
        )
        bench_start = time.monotonic()

        try:
            stats = await run_benchmark_multi(benchmark.id, job_manager, NUM_RUNS)
            bench_elapsed = time.monotonic() - bench_start
            all_stats.append((benchmark.name, benchmark.id, benchmark.tags, stats))

            logger.info(
                "[%d/%d] %s 完了: 平均精度=%.1f%%, 時間=%.0f秒",
                i, len(benchmarks), benchmark.name,
                stats.mean_direction_accuracy * 100,
                bench_elapsed,
            )
        except Exception:
            logger.exception("[%d/%d] %s 失敗", i, len(benchmarks), benchmark.name)

    total_elapsed = time.monotonic() - start_time

    # レポート生成・保存
    report = build_report(all_stats, total_elapsed)
    REPORT_PATH.write_text(report, encoding="utf-8")
    logger.info("レポート保存: %s", REPORT_PATH)

    # コンソールにも出力（Windows cp932で表示できない文字を置換）
    try:
        print(report)
    except UnicodeEncodeError:
        safe_report = report.encode("ascii", errors="replace").decode("ascii")
        print(safe_report)

    try:
        await redis.close()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
