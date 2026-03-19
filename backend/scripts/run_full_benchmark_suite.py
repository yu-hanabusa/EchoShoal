"""全ベンチマーク × N回の一連テスト（市場調査 → シミュレーション → 評価）.

Usage:
    cd backend
    uv run python scripts/run_full_benchmark_suite.py [--runs 5]

結果は backend/benchmark_full_results.json と benchmark_full_report.txt に出力される。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import sys
import time
from datetime import datetime
from pathlib import Path

# backendディレクトリからの実行を想定
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.job_manager import JobManager
from app.core.redis_client import RedisClient
from app.evaluation.benchmarks import list_benchmarks
from app.evaluation.runner import run_benchmark_with_research

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("benchmark_full_log.txt", encoding="utf-8"),
    ],
)
logger = logging.getLogger("benchmark_suite")


async def main(num_runs: int = 5) -> None:
    redis = RedisClient()
    job_manager = JobManager(redis)

    benchmarks = list_benchmarks()
    total = len(benchmarks) * num_runs
    logger.info("=" * 60)
    logger.info("一連ベンチマーク開始: %d件 × %d回 = %d実行", len(benchmarks), num_runs, total)
    logger.info("=" * 60)

    all_results: list[dict] = []
    suite_start = time.monotonic()
    run_count = 0

    for b_idx, benchmark in enumerate(benchmarks):
        logger.info("")
        logger.info("━" * 50)
        logger.info("[%d/%d] %s (×%d回)", b_idx + 1, len(benchmarks), benchmark.name, num_runs)
        logger.info("━" * 50)

        per_benchmark_results: list[dict] = []

        for run_idx in range(num_runs):
            run_count += 1
            logger.info(
                "  実行 %d/%d (全体 %d/%d): %s",
                run_idx + 1, num_runs, run_count, total, benchmark.name,
            )

            run_start = time.monotonic()
            try:
                result = await run_benchmark_with_research(
                    benchmark.id, job_manager,
                )
                elapsed = time.monotonic() - run_start

                # トークン使用量
                tu = result.evaluation.token_usage
                token_data = {}
                if tu:
                    token_data = {
                        "total_input_tokens": tu.total_input_tokens,
                        "total_output_tokens": tu.total_output_tokens,
                        "total_tokens": tu.total_tokens,
                        "total_calls": tu.total_calls,
                        "estimated_cost_usd": tu.estimated_cost_usd,
                        "by_task_type": tu.by_task_type,
                        "by_provider": tu.by_provider,
                    }

                entry = {
                    "benchmark_id": result.benchmark_id,
                    "benchmark_name": result.benchmark_name,
                    "run": run_idx + 1,
                    "direction_accuracy": result.evaluation.direction_accuracy,
                    "trend_results": [
                        {
                            "metric": t.metric,
                            "expected": t.expected_direction.value,
                            "actual": t.actual_direction.value,
                            "change_rate": t.actual_change_rate,
                            "correct": t.direction_correct,
                        }
                        for t in result.evaluation.trend_results
                    ],
                    "research_time_seconds": result.research_time_seconds,
                    "simulation_time_seconds": result.evaluation.execution_time_seconds,
                    "total_time_seconds": round(elapsed, 2),
                    "sources_used": result.research.sources_used,
                    "research_errors": result.research.errors,
                    "trends_count": result.research.trends_count,
                    "github_repos_count": result.research.github_repos_count,
                    "finance_data_count": result.research.finance_data_count,
                    "token_usage": token_data,
                }
                per_benchmark_results.append(entry)
                all_results.append(entry)

                cost_str = f", コスト=${tu.estimated_cost_usd:.4f}" if tu else ""
                tokens_str = f", トークン={tu.total_tokens:,}" if tu else ""
                logger.info(
                    "    → 方向精度=%.2f, 調査=%.1fs, シミュレーション=%.1fs, 合計=%.1fs%s%s",
                    result.evaluation.direction_accuracy,
                    result.research_time_seconds,
                    result.evaluation.execution_time_seconds,
                    elapsed,
                    tokens_str,
                    cost_str,
                )

            except Exception:
                elapsed = time.monotonic() - run_start
                logger.exception("    → 失敗 (%.1fs)", elapsed)
                all_results.append({
                    "benchmark_id": benchmark.id,
                    "benchmark_name": benchmark.name,
                    "run": run_idx + 1,
                    "error": True,
                    "total_time_seconds": round(elapsed, 2),
                })

        # ベンチマークごとの統計
        accuracies = [r["direction_accuracy"] for r in per_benchmark_results if "direction_accuracy" in r]
        if accuracies:
            mean_acc = sum(accuracies) / len(accuracies)
            if len(accuracies) > 1:
                variance = sum((a - mean_acc) ** 2 for a in accuracies) / (len(accuracies) - 1)
                stddev = math.sqrt(variance)
            else:
                stddev = 0.0
            logger.info(
                "  統計: mean=%.4f, stddev=%.4f, min=%.4f, max=%.4f (%d/%d成功)",
                mean_acc, stddev, min(accuracies), max(accuracies),
                len(accuracies), num_runs,
            )

    suite_elapsed = time.monotonic() - suite_start

    # JSON結果保存
    output_json = Path("benchmark_full_results.json")
    output_json.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("結果JSON保存: %s", output_json)

    # テキストレポート生成
    _generate_report(all_results, benchmarks, num_runs, suite_elapsed)

    logger.info("=" * 60)
    logger.info("全実行完了: %.1f分", suite_elapsed / 60)
    logger.info("=" * 60)


def _generate_report(
    all_results: list[dict],
    benchmarks: list,
    num_runs: int,
    total_elapsed: float,
) -> None:
    """テキストレポートを生成する."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"EchoShoal 一連ベンチマーク結果 (市場調査 + シミュレーション + 評価)")
    lines.append(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"ベンチマーク数: {len(benchmarks)} × {num_runs}回 = {len(benchmarks) * num_runs}実行")
    lines.append(f"総実行時間: {total_elapsed / 60:.1f}分")
    lines.append("=" * 70)
    lines.append("")

    for benchmark in benchmarks:
        bid = benchmark.id
        runs = [r for r in all_results if r.get("benchmark_id") == bid]
        successes = [r for r in runs if "direction_accuracy" in r]
        errors = [r for r in runs if r.get("error")]

        lines.append(f"■ {benchmark.name} ({bid})")
        lines.append(f"  成功: {len(successes)}/{len(runs)}, エラー: {len(errors)}")

        if successes:
            accs = [r["direction_accuracy"] for r in successes]
            mean_acc = sum(accs) / len(accs)
            lines.append(f"  方向精度: mean={mean_acc:.4f}, min={min(accs):.4f}, max={max(accs):.4f}")

            # トレンドごとのヒット率
            trend_hits: dict[str, int] = {}
            trend_total: dict[str, int] = {}
            for r in successes:
                for t in r.get("trend_results", []):
                    metric = t["metric"]
                    trend_total[metric] = trend_total.get(metric, 0) + 1
                    if t["correct"]:
                        trend_hits[metric] = trend_hits.get(metric, 0) + 1

            for metric in trend_total:
                hits = trend_hits.get(metric, 0)
                total = trend_total[metric]
                lines.append(f"    {metric}: {hits}/{total} ({hits/total*100:.0f}%)")

            # 市場調査データ品質
            sources = set()
            for r in successes:
                for s in r.get("sources_used", []):
                    sources.add(s)
            avg_trends = sum(r.get("trends_count", 0) for r in successes) / len(successes)
            avg_github = sum(r.get("github_repos_count", 0) for r in successes) / len(successes)
            avg_finance = sum(r.get("finance_data_count", 0) for r in successes) / len(successes)
            lines.append(f"  データソース: {', '.join(sorted(sources)) or 'なし'}")
            lines.append(f"  平均収集数: Trends={avg_trends:.1f}, GitHub={avg_github:.1f}, Finance={avg_finance:.1f}")

            # トークン使用量・コスト
            token_runs = [r for r in successes if r.get("token_usage")]
            if token_runs:
                avg_tokens = sum(r["token_usage"].get("total_tokens", 0) for r in token_runs) / len(token_runs)
                avg_calls = sum(r["token_usage"].get("total_calls", 0) for r in token_runs) / len(token_runs)
                avg_cost = sum(r["token_usage"].get("estimated_cost_usd", 0) for r in token_runs) / len(token_runs)
                total_cost = sum(r["token_usage"].get("estimated_cost_usd", 0) for r in token_runs)
                lines.append(f"  トークン使用量 (平均): {avg_tokens:,.0f} tokens, {avg_calls:.0f} calls, ${avg_cost:.4f}/回")
                lines.append(f"  トークン使用量 (合計{len(token_runs)}回): ${total_cost:.4f}")

                # タスク種別内訳（全実行を合算）
                task_totals: dict[str, dict[str, float]] = {}
                for r in token_runs:
                    for task, data in r["token_usage"].get("by_task_type", {}).items():
                        if task not in task_totals:
                            task_totals[task] = {"tokens": 0, "calls": 0, "cost": 0.0}
                        task_totals[task]["tokens"] += data.get("input_tokens", 0) + data.get("output_tokens", 0)
                        task_totals[task]["calls"] += data.get("calls", 0)
                        task_totals[task]["cost"] += data.get("estimated_cost_usd", 0)
                if task_totals:
                    lines.append(f"  タスク種別内訳 (全{len(token_runs)}回合算):")
                    for task, td in sorted(task_totals.items(), key=lambda x: x[1]["cost"], reverse=True):
                        lines.append(
                            f"    {task}: {td['tokens']:,.0f} tokens, "
                            f"{td['calls']:.0f} calls, ${td['cost']:.4f}"
                        )

                # プロバイダー内訳
                prov_totals: dict[str, dict[str, float]] = {}
                for r in token_runs:
                    for prov, data in r["token_usage"].get("by_provider", {}).items():
                        if prov not in prov_totals:
                            prov_totals[prov] = {"tokens": 0, "calls": 0, "cost": 0.0}
                        prov_totals[prov]["tokens"] += data.get("input_tokens", 0) + data.get("output_tokens", 0)
                        prov_totals[prov]["calls"] += data.get("calls", 0)
                        prov_totals[prov]["cost"] += data.get("estimated_cost_usd", 0)
                if prov_totals:
                    lines.append(f"  プロバイダー内訳:")
                    for prov, pd in sorted(prov_totals.items(), key=lambda x: x[1]["cost"], reverse=True):
                        lines.append(
                            f"    {prov}: {pd['tokens']:,.0f} tokens, "
                            f"{pd['calls']:.0f} calls, ${pd['cost']:.4f}"
                        )

            # 実行時間
            avg_research = sum(r.get("research_time_seconds", 0) for r in successes) / len(successes)
            avg_sim = sum(r.get("simulation_time_seconds", 0) for r in successes) / len(successes)
            avg_total = sum(r.get("total_time_seconds", 0) for r in successes) / len(successes)
            lines.append(f"  平均時間: 調査={avg_research:.1f}s, シミュレーション={avg_sim:.1f}s, 合計={avg_total:.1f}s")

        lines.append("")

    # 全体サマリー
    all_accs = [r["direction_accuracy"] for r in all_results if "direction_accuracy" in r]
    total_errors = sum(1 for r in all_results if r.get("error"))
    if all_accs:
        lines.append("=" * 70)
        lines.append("全体サマリー")
        lines.append(f"  全体方向精度: {sum(all_accs)/len(all_accs):.4f}")
        lines.append(f"  成功: {len(all_accs)}/{len(all_results)}, エラー: {total_errors}")
        passed = sum(1 for a in all_accs if a >= 0.6)
        lines.append(f"  パス率(≥60%): {passed}/{len(all_accs)} ({passed/len(all_accs)*100:.1f}%)")

        # 全体トークン使用量・コスト
        all_token_runs = [r for r in all_results if r.get("token_usage")]
        if all_token_runs:
            suite_tokens = sum(r["token_usage"].get("total_tokens", 0) for r in all_token_runs)
            suite_calls = sum(r["token_usage"].get("total_calls", 0) for r in all_token_runs)
            suite_cost = sum(r["token_usage"].get("estimated_cost_usd", 0) for r in all_token_runs)
            lines.append("")
            lines.append("トークン使用量・コスト (全体)")
            lines.append(f"  総トークン数: {suite_tokens:,}")
            lines.append(f"  総LLM呼び出し数: {suite_calls:,}")
            lines.append(f"  推定総コスト: ${suite_cost:.4f}")
            if all_token_runs:
                lines.append(f"  1回あたり平均コスト: ${suite_cost / len(all_token_runs):.4f}")

            # プロバイダー別合計
            suite_prov: dict[str, dict[str, float]] = {}
            for r in all_token_runs:
                for prov, data in r["token_usage"].get("by_provider", {}).items():
                    if prov not in suite_prov:
                        suite_prov[prov] = {"input": 0, "output": 0, "calls": 0, "cost": 0.0}
                    suite_prov[prov]["input"] += data.get("input_tokens", 0)
                    suite_prov[prov]["output"] += data.get("output_tokens", 0)
                    suite_prov[prov]["calls"] += data.get("calls", 0)
                    suite_prov[prov]["cost"] += data.get("estimated_cost_usd", 0)
            for prov, pd in sorted(suite_prov.items(), key=lambda x: x[1]["cost"], reverse=True):
                lines.append(
                    f"  {prov}: input={pd['input']:,} + output={pd['output']:,} = "
                    f"{pd['input']+pd['output']:,} tokens, "
                    f"{pd['calls']:.0f} calls, ${pd['cost']:.4f}"
                )

        lines.append("=" * 70)

    report_path = Path("benchmark_full_report.txt")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("レポート保存: %s", report_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一連ベンチマーク実行")
    parser.add_argument("--runs", type=int, default=5, help="各ベンチマークの実行回数")
    args = parser.parse_args()
    asyncio.run(main(num_runs=args.runs))
