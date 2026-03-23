"""通常ベンチマーク + 汚染テストの一括実行スクリプト.

1. 全9シナリオの通常ベンチマーク（修正済みシナリオデータ）
2. 全9シナリオの汚染A/Bテスト

結果はコンソールに表示されます。
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

# backendディレクトリをパスに追加（scripts/から実行時用）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Windows cp932エンコーディング問題を回避
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Ollamaのログを抑制
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def main() -> None:
    from app.core.job_manager import JobManager
    from app.core.redis_client import RedisClient
    from app.evaluation.benchmarks import list_benchmarks
    from app.evaluation.runner import run_benchmark
    from app.evaluation.contamination import run_contamination_test

    redis = RedisClient()
    jm = JobManager(redis)

    benchmarks = list_benchmarks()

    # ═══════════════════════════════════════════════════════════════
    #  Phase 1: 通常ベンチマーク（修正済みシナリオデータ）
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  Phase 1: 通常ベンチマーク（未来情報除去済み）")
    print("=" * 70)

    normal_results = {}
    total_start = time.monotonic()

    for i, bm in enumerate(benchmarks):
        print(f"\n--- [{i+1}/{len(benchmarks)}] {bm.name} ({bm.scenario_input.num_rounds}ラウンド) ---")
        try:
            result = await run_benchmark(bm.id, jm)
            normal_results[bm.id] = result
            mark = "OK" if result.outcome_correct else "NG"
            print(f"  方向精度: {result.direction_accuracy:.2%}")
            print(f"  成功/失敗予測: {result.predicted_verdict} {mark}")
            print(f"  実行時間: {result.execution_time_seconds:.1f}s")
            for tr in result.trend_results:
                m = "OK" if tr.direction_correct else "NG"
                print(f"    {m} {tr.metric}: {tr.expected_direction.value} -> {tr.actual_direction.value}")
        except Exception as exc:
            print(f"  NG 失敗: {exc}")

    phase1_time = time.monotonic() - total_start

    # Phase 1 サマリー
    print("\n" + "=" * 70)
    print("  Phase 1 サマリー")
    print("=" * 70)
    if normal_results:
        accs = [r.direction_accuracy for r in normal_results.values()]
        outcomes = [r for r in normal_results.values() if r.outcome_correct is not None]
        outcome_correct = sum(1 for r in outcomes if r.outcome_correct)
        print(f"  完了: {len(normal_results)}/{len(benchmarks)}")
        print(f"  平均方向精度: {sum(accs)/len(accs):.2%}")
        print(f"  成功/失敗予測正解: {outcome_correct}/{len(outcomes)}")
        print(f"  所要時間: {phase1_time:.0f}s ({phase1_time/60:.1f}分)")
        for bid, r in normal_results.items():
            mark = "OK" if r.outcome_correct else "NG"
            print(f"    {bid}: 方向={r.direction_accuracy:.2%}, 予測={r.predicted_verdict} {mark}")

    # ═══════════════════════════════════════════════════════════════
    #  Phase 2: 汚染A/Bテスト
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  Phase 2: LLM知識汚染テスト（実名 vs 匿名）")
    print("=" * 70)

    contamination_results = {}
    phase2_start = time.monotonic()

    for i, bm in enumerate(benchmarks):
        print(f"\n--- [{i+1}/{len(benchmarks)}] {bm.name} 汚染テスト ---")
        try:
            ct_result = await run_contamination_test(bm.id, jm)
            contamination_results[bm.id] = ct_result
            print(f"  実名版精度: {ct_result.real_accuracy:.2%}")
            print(f"  匿名版精度: {ct_result.anon_accuracy:.2%}")
            print(f"  汚染スコア: {ct_result.contamination_score:+.1f}pp ({ct_result.contamination_level.value})")
            print(f"  実行時間: {ct_result.execution_time_seconds:.1f}s")
        except Exception as exc:
            print(f"  NG 失敗: {exc}")

    phase2_time = time.monotonic() - phase2_start

    # Phase 2 サマリー
    print("\n" + "=" * 70)
    print("  Phase 2 サマリー: 汚染テスト結果")
    print("=" * 70)
    if contamination_results:
        scores = [r.contamination_score for r in contamination_results.values()]
        real_accs = [r.real_accuracy for r in contamination_results.values()]
        anon_accs = [r.anon_accuracy for r in contamination_results.values()]
        print(f"  完了: {len(contamination_results)}/{len(benchmarks)}")
        print(f"  平均実名版精度: {sum(real_accs)/len(real_accs):.2%}")
        print(f"  平均匿名版精度: {sum(anon_accs)/len(anon_accs):.2%}")
        print(f"  平均汚染スコア: {sum(scores)/len(scores):+.1f}pp")
        print(f"  所要時間: {phase2_time:.0f}s ({phase2_time/60:.1f}分)")
        print()
        print(f"  {'シナリオ':<30} {'実名':>6} {'匿名':>6} {'汚染':>8} {'レベル':<10}")
        print(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*8} {'-'*10}")
        for bid, r in contamination_results.items():
            print(f"  {bid:<30} {r.real_accuracy:>5.0%} {r.anon_accuracy:>5.0%} {r.contamination_score:>+7.1f}pp {r.contamination_level.value:<10}")

    # 総合
    total_time = time.monotonic() - total_start
    print("\n" + "=" * 70)
    print(f"  総所要時間: {total_time:.0f}s ({total_time/60:.1f}分)")
    print("=" * 70)

    await redis.close()


if __name__ == "__main__":
    asyncio.run(main())
