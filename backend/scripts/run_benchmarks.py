"""ベンチマーク評価の実行スクリプト.

使い方:
  cd backend

  # 全ベンチマークを1回ずつ実行
  uv run python scripts/run_benchmarks.py

  # 特定のベンチマークのみ
  uv run python scripts/run_benchmarks.py --benchmark slack_2014

  # 統計評価（同一シナリオを複数回実行）
  uv run python scripts/run_benchmarks.py --benchmark slack_2014 --runs 5

  # 全ベンチマークを各3回ずつ実行（統計評価）
  uv run python scripts/run_benchmarks.py --runs 3

  # 一覧表示のみ
  uv run python scripts/run_benchmarks.py --list

前提:
  - Docker (Neo4j + Redis) が起動していること
  - Ollama が起動していること (qwen2.5:14b)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.job_manager import JobManager  # noqa: E402
from app.core.redis_client import RedisClient  # noqa: E402
from app.evaluation.benchmarks import get_benchmark, list_benchmarks  # noqa: E402
from app.evaluation.runner import (  # noqa: E402
    run_all_benchmarks,
    run_benchmark,
    run_benchmark_multi,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark")

# シミュレーション内部ログを抑制
logging.getLogger("app.simulation").setLevel(logging.WARNING)
logging.getLogger("app.core.llm").setLevel(logging.WARNING)
logging.getLogger("app.core.graph").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


def print_separator() -> None:
    print("=" * 70)


def print_result_table(results: list[dict]) -> None:
    """結果をテーブル形式で表示する."""
    print_separator()
    print(f"{'ベンチマーク':<30} {'方向精度':>8} {'トレンド数':>10} {'時間(s)':>8}")
    print_separator()
    for r in results:
        marker = "PASS" if r["accuracy"] >= 0.6 else "FAIL"
        print(
            f"{r['name']:<30} {r['accuracy']:>7.1%}  "
            f"{r['correct']}/{r['total']:>8}  "
            f"{r['time']:>7.1f}  [{marker}]"
        )
    print_separator()

    accuracies = [r["accuracy"] for r in results]
    mean_acc = sum(accuracies) / len(accuracies) if accuracies else 0
    passed = sum(1 for a in accuracies if a >= 0.6)
    print(f"平均方向精度: {mean_acc:.1%}")
    print(f"合格: {passed}/{len(results)} (閾値: 60%)")


def print_multi_result(benchmark_name: str, stats) -> None:
    """統計評価結果を表示する."""
    print_separator()
    print(f"統計評価: {benchmark_name}")
    print(f"実行回数: {stats.num_runs}")
    print(f"平均方向精度: {stats.mean_direction_accuracy:.1%}")
    print(f"標準偏差: {stats.stddev_direction_accuracy:.4f}")
    print(f"最小: {stats.min_direction_accuracy:.1%}")
    print(f"最大: {stats.max_direction_accuracy:.1%}")
    print()
    print("トレンド別ヒット率:")
    for metric, rate in stats.per_trend_hit_rates.items():
        marker = "OK" if rate >= 0.6 else "!!"
        print(f"  {metric:<40} {rate:>5.0%}  [{marker}]")
    print_separator()


async def check_infrastructure() -> bool:
    """インフラの接続確認."""
    errors = []

    # Redis
    try:
        redis = RedisClient()
        if not await redis.is_available():
            errors.append("Redis に接続できません (docker compose up -d)")
    except Exception:
        errors.append("Redis に接続できません (docker compose up -d)")

    # Ollama
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code != 200:
                errors.append("Ollama に接続できません (ollama serve)")
    except Exception:
        errors.append("Ollama に接続できません (ollama serve)")

    if errors:
        logger.error("インフラ接続エラー:")
        for e in errors:
            logger.error("  - %s", e)
        return False
    return True


async def main() -> None:
    parser = argparse.ArgumentParser(description="ベンチマーク評価の実行")
    parser.add_argument(
        "--benchmark", "-b",
        help="特定のベンチマークIDのみ実行（省略で全件）",
    )
    parser.add_argument(
        "--runs", "-n",
        type=int, default=1,
        help="各ベンチマークの実行回数（2以上で統計評価）",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="ベンチマーク一覧を表示して終了",
    )
    args = parser.parse_args()

    # 一覧表示
    if args.list:
        benchmarks = list_benchmarks()
        print_separator()
        print(f"{'ID':<30} {'名前':<30} {'トレンド':>6} {'ラウンド':>8} {'タグ'}")
        print_separator()
        for b in benchmarks:
            tags = ", ".join(b.tags)
            print(
                f"{b.id:<30} {b.name:<30} {len(b.expected_trends):>6} "
                f"{b.scenario_input.num_rounds:>8}  {tags}"
            )
        print_separator()
        print(f"合計: {len(benchmarks)}件")
        return

    # インフラ確認
    logger.info("インフラ接続を確認中...")
    if not await check_infrastructure():
        sys.exit(1)
    logger.info("インフラ接続OK")

    redis = RedisClient()
    job_manager = JobManager(redis)

    start_time = time.monotonic()

    if args.benchmark:
        # 特定ベンチマーク
        benchmark = get_benchmark(args.benchmark)
        if benchmark is None:
            logger.error("ベンチマーク '%s' が見つかりません", args.benchmark)
            available = [b.id for b in list_benchmarks()]
            logger.info("利用可能: %s", ", ".join(available))
            sys.exit(1)

        if args.runs >= 2:
            # 統計評価
            logger.info(
                "統計評価開始: %s (%d回実行)", benchmark.name, args.runs,
            )
            stats = await run_benchmark_multi(
                args.benchmark, job_manager, args.runs,
            )
            print_multi_result(benchmark.name, stats)
        else:
            # 単一実行
            logger.info("ベンチマーク実行: %s", benchmark.name)
            result = await run_benchmark(args.benchmark, job_manager)
            print_result_table([{
                "name": result.benchmark_name,
                "accuracy": result.direction_accuracy,
                "correct": sum(t.direction_correct for t in result.trend_results),
                "total": len(result.trend_results),
                "time": result.execution_time_seconds,
            }])
            print()
            print("トレンド詳細:")
            for tr in result.trend_results:
                marker = "OK" if tr.direction_correct else "NG"
                print(
                    f"  [{marker}] {tr.metric:<35} "
                    f"期待={tr.expected_direction.value:<6} "
                    f"実際={tr.actual_direction.value:<6} "
                    f"変化率={tr.actual_change_rate:+.1f}%"
                )
    else:
        # 全ベンチマーク
        if args.runs >= 2:
            # 全件×N回
            logger.info("全ベンチマーク統計評価: 各%d回実行", args.runs)
            benchmarks = list_benchmarks()
            all_stats = []
            for b in benchmarks:
                logger.info("\n--- %s ---", b.name)
                stats = await run_benchmark_multi(b.id, job_manager, args.runs)
                all_stats.append((b.name, stats))
                print_multi_result(b.name, stats)

            # 全体サマリー
            print_separator()
            print("全体サマリー")
            print_separator()
            print(f"{'ベンチマーク':<30} {'平均精度':>8} {'標準偏差':>8} {'実行数':>6}")
            print_separator()
            for name, stats in all_stats:
                print(
                    f"{name:<30} {stats.mean_direction_accuracy:>7.1%} "
                    f"{stats.stddev_direction_accuracy:>8.4f} "
                    f"{len(stats.per_run_results):>5}/{stats.num_runs}"
                )
        else:
            # 全件×1回
            logger.info("全ベンチマーク評価開始 (%d件)", len(list_benchmarks()))
            suite = await run_all_benchmarks(job_manager)
            results = []
            for r in suite.results:
                results.append({
                    "name": r.benchmark_name,
                    "accuracy": r.direction_accuracy,
                    "correct": sum(t.direction_correct for t in r.trend_results),
                    "total": len(r.trend_results),
                    "time": r.execution_time_seconds,
                })
            print_result_table(results)

    elapsed = time.monotonic() - start_time
    print(f"\n総実行時間: {elapsed:.1f}s ({elapsed / 60:.1f}分)")

    try:
        await redis.close()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
