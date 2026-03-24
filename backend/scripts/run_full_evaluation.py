"""通常ベンチマーク + 汚染テストの一括実行 + ドキュメント生成スクリプト.

1. Phase 1: 全9シナリオの通常ベンチマーク（3回実行、統計評価）
2. Phase 2: 全9シナリオの汚染A/Bテスト（各1回）
3. Phase 3: 結果をJSONに保存 + docs/BENCHMARK_RESULTS.md を生成
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

RESULTS_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = RESULTS_DIR.parent / "docs"
NUM_RUNS = 3


async def main() -> None:
    from app.core.job_manager import JobManager
    from app.core.redis_client import RedisClient
    from app.evaluation.benchmarks import list_benchmarks
    from app.evaluation.contamination import run_contamination_test
    from app.evaluation.runner import run_benchmark_multi

    redis = RedisClient()
    jm = JobManager(redis)
    benchmarks = list_benchmarks()
    total_start = time.monotonic()

    # ======================================================
    #  Phase 1: 通常ベンチマーク（各3回実行）
    # ======================================================
    print("=" * 70)
    print(f"  Phase 1: 通常ベンチマーク（各{NUM_RUNS}回実行）")
    print("=" * 70)

    stats_results: dict[str, dict] = {}

    for i, bm in enumerate(benchmarks):
        print(f"\n--- [{i+1}/{len(benchmarks)}] {bm.name} ({bm.scenario_input.num_rounds}R x {NUM_RUNS}runs) ---")
        try:
            stats = await run_benchmark_multi(bm.id, jm, num_runs=NUM_RUNS)
            stats_results[bm.id] = {
                "name": bm.name,
                "expected_outcome": bm.expected_outcome.value if bm.expected_outcome else None,
                "num_rounds": bm.scenario_input.num_rounds,
                "mean_accuracy": stats.mean_direction_accuracy,
                "median_accuracy": stats.median_direction_accuracy,
                "stddev": stats.stddev_direction_accuracy,
                "min": stats.min_direction_accuracy,
                "max": stats.max_direction_accuracy,
                "ci_95": list(stats.confidence_interval_95) if stats.confidence_interval_95 else None,
                "per_trend": stats.per_trend_hit_rates,
                "outcome_hit_rate": stats.outcome_hit_rate,
                "runs": [
                    {
                        "accuracy": r.direction_accuracy,
                        "outcome_correct": r.outcome_correct,
                        "predicted_verdict": r.predicted_verdict,
                        "trends": [
                            {
                                "metric": t.metric,
                                "expected": t.expected_direction.value,
                                "actual": t.actual_direction.value,
                                "correct": t.direction_correct,
                                "change_rate": t.actual_change_rate,
                            }
                            for t in r.trend_results
                        ],
                    }
                    for r in stats.per_run_results
                ],
            }
            print(f"  Mean: {stats.mean_direction_accuracy:.0%} (sd={stats.stddev_direction_accuracy:.3f})")
            print(f"  Outcome hit: {stats.outcome_hit_rate:.0%}" if stats.outcome_hit_rate is not None else "  Outcome: N/A")
        except Exception as exc:
            print(f"  FAILED: {exc}")

    phase1_time = time.monotonic() - total_start
    print(f"\nPhase 1 complete: {phase1_time:.0f}s ({phase1_time/60:.1f}min)")

    # ======================================================
    #  Phase 2: 汚染A/Bテスト（各1回）
    # ======================================================
    print("\n" + "=" * 70)
    print("  Phase 2: 汚染A/Bテスト（実名 vs 匿名）")
    print("=" * 70)

    contamination_results: dict[str, dict] = {}
    phase2_start = time.monotonic()

    for i, bm in enumerate(benchmarks):
        print(f"\n--- [{i+1}/{len(benchmarks)}] {bm.name} ---")
        try:
            ct = await run_contamination_test(bm.id, jm)
            contamination_results[bm.id] = {
                "name": bm.name,
                "real_accuracy": ct.real_accuracy,
                "anon_accuracy": ct.anon_accuracy,
                "real_outcome": ct.real_outcome_correct,
                "anon_outcome": ct.anon_outcome_correct,
                "contamination_score": ct.contamination_score,
                "contamination_level": ct.contamination_level.value,
                "time": ct.execution_time_seconds,
            }
            print(f"  Real={ct.real_accuracy:.0%}  Anon={ct.anon_accuracy:.0%}  Score={ct.contamination_score:+.1f}pp ({ct.contamination_level.value})")
        except Exception as exc:
            print(f"  FAILED: {exc}")

    phase2_time = time.monotonic() - phase2_start
    total_time = time.monotonic() - total_start

    # ======================================================
    #  Phase 3: 結果保存 + ドキュメント生成
    # ======================================================
    print("\n" + "=" * 70)
    print("  Phase 3: 結果保存 + ドキュメント生成")
    print("=" * 70)

    # JSON保存
    all_results = {
        "generated_at": datetime.now().isoformat(),
        "num_runs": NUM_RUNS,
        "phase1_time_seconds": round(phase1_time, 1),
        "phase2_time_seconds": round(phase2_time, 1),
        "total_time_seconds": round(total_time, 1),
        "benchmarks": stats_results,
        "contamination": contamination_results,
    }

    json_path = RESULTS_DIR / "evaluation_results.json"
    json_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  JSON saved: {json_path}")

    # Markdown生成
    md = _generate_markdown(all_results)
    md_path = DOCS_DIR / "BENCHMARK_RESULTS.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  Markdown saved: {md_path}")

    # サマリー表示
    print("\n" + "=" * 70)
    print("  Final Summary")
    print("=" * 70)
    if stats_results:
        accs = [v["mean_accuracy"] for v in stats_results.values()]
        print(f"  Benchmarks: {len(stats_results)}/{len(benchmarks)}")
        print(f"  Mean direction accuracy: {sum(accs)/len(accs):.0%}")
    if contamination_results:
        scores = [v["contamination_score"] for v in contamination_results.values()]
        print(f"  Mean contamination score: {sum(scores)/len(scores):+.1f}pp")
    print(f"  Total time: {total_time:.0f}s ({total_time/60:.1f}min, {total_time/3600:.1f}h)")
    print("=" * 70)

    await redis.close()


def _generate_markdown(data: dict) -> str:
    """結果データからBENCHMARK_RESULTS.mdを生成する."""
    lines: list[str] = []
    w = lines.append

    benchmarks = data["benchmarks"]
    contamination = data["contamination"]
    num_runs = data["num_runs"]
    total_time = data["total_time_seconds"]

    w("# Benchmark Results")
    w("")
    w("EchoShoalシミュレーションエンジンの予測精度を、実在のサービス事例（成功5件・失敗4件）で評価した結果。")
    w("")
    w(f"> Generated: {data['generated_at'][:10]}")
    w("")

    # 評価方法
    w("## 評価方法")
    w("")
    w("### 通常ベンチマーク")
    w(f"- 各シナリオを{num_runs}回実行し、市場ディメンションのトレンド方向（up/down/stable）を史実と比較")
    w("- **方向精度** = 正しく予測したディメンション数 / 評価対象ディメンション数")
    w("- LLM: Ollama qwen3:14b（エージェント行動決定・市場分析）")
    w("- シナリオテキスト（market_report, stakeholders, user_behavior）は基準時点以前の情報のみを含む")
    w("")
    w("### LLM知識汚染テスト（Contamination A/B Test）")
    w("- 同一シナリオを**実名版**と**匿名版**で実行し、方向精度の差分を計測")
    w("- 匿名版ではサービス名・創業者名・競合名等を架空の名前に置換")
    w("- 差分（contamination_score）が大きい場合、LLMの学習データに含まれる結果情報が予測に影響している")
    w("- 差分が小さい場合、シミュレータの構造的推論力が予測に寄与している")
    w("")
    w("| contamination_score | レベル | 解釈 |")
    w("|---|---|---|")
    w("| 5pp以下 | none | 差なし。純粋な推論 |")
    w("| 5-15pp | low | 軽微な知識リーク |")
    w("| 15-30pp | moderate | 中程度の知識リーク |")
    w("| 30pp超 | high | 強い知識リーク |")
    w("| -5pp未満 | negative | 匿名版の方が高い（名前バイアス） |")
    w("")

    # 通常ベンチマーク サマリー
    w("## 通常ベンチマーク結果")
    w("")

    if benchmarks:
        accs = [v["mean_accuracy"] for v in benchmarks.values()]
        outcomes = [v for v in benchmarks.values() if v["outcome_hit_rate"] is not None]
        outcome_correct = sum(1 for v in outcomes if v["outcome_hit_rate"] and v["outcome_hit_rate"] >= 0.5)
        passed = sum(1 for v in benchmarks.values() if v["mean_accuracy"] >= 0.6)

        w(f"- **全体平均方向精度: {sum(accs)/len(accs):.1%}**")
        w(f"- **合格シナリオ (>=60%): {passed}/{len(benchmarks)}**")
        if outcomes:
            w(f"- 成功/失敗予測正解: {outcome_correct}/{len(outcomes)}")
        w(f"- 総実行時間: {data['phase1_time_seconds']/3600:.1f}時間（{len(benchmarks)}シナリオ x {num_runs}回）")
        w("")

        w("| シナリオ | 種別 | 平均精度 | sd | 95% CI | 成功/失敗予測 |")
        w("|---------|------|---------|-----|--------|------------|")
        for bid, v in benchmarks.items():
            kind = "成功" if v["expected_outcome"] == "success" else "失敗"
            ci = f"[{v['ci_95'][0]:.0%}-{v['ci_95'][1]:.0%}]" if v.get("ci_95") else "N/A"
            outcome_str = f"{v['outcome_hit_rate']:.0%}" if v.get("outcome_hit_rate") is not None else "N/A"
            w(f"| {v['name']} | {kind} | {v['mean_accuracy']:.1%} | {v['stddev']:.3f} | {ci} | {outcome_str} |")
        w("")

    # シナリオ別詳細
    w("## シナリオ別詳細")
    w("")

    for bid, v in benchmarks.items():
        kind = "成功" if v["expected_outcome"] == "success" else "失敗"
        w(f"### {v['name']} ({kind}) -- {v['mean_accuracy']:.1%}")
        w("")
        if v.get("per_trend"):
            w("| ディメンション | ヒット率 | 期待 |")
            w("|--------------|---------|------|")
            for metric, hit_rate in v["per_trend"].items():
                # 期待方向を最初のrunから取得
                expected = "?"
                if v["runs"]:
                    for t in v["runs"][0]["trends"]:
                        if t["metric"] == metric:
                            expected = t["expected"]
                            break
                w(f"| {metric} | {hit_rate:.0%} ({int(hit_rate * num_runs)}/{num_runs}) | {expected} |")
            w("")

    # 汚染テスト結果
    w("## LLM知識汚染テスト結果")
    w("")

    if contamination:
        scores = [v["contamination_score"] for v in contamination.values()]
        real_accs = [v["real_accuracy"] for v in contamination.values()]
        anon_accs = [v["anon_accuracy"] for v in contamination.values()]

        w(f"- **平均汚染スコア: {sum(scores)/len(scores):+.1f}pp**")
        w(f"- 平均実名版精度: {sum(real_accs)/len(real_accs):.1%}")
        w(f"- 平均匿名版精度: {sum(anon_accs)/len(anon_accs):.1%}")
        w(f"- 実行時間: {data['phase2_time_seconds']/3600:.1f}時間")
        w("")

        w("| シナリオ | 実名版 | 匿名版 | 汚染スコア | レベル |")
        w("|---------|-------|-------|-----------|--------|")
        for bid, v in contamination.items():
            w(f"| {v['name']} | {v['real_accuracy']:.0%} | {v['anon_accuracy']:.0%} | {v['contamination_score']:+.1f}pp | {v['contamination_level']} |")
        w("")

        # 解釈
        mean_score = sum(scores) / len(scores)
        w("### 解釈")
        w("")
        if mean_score <= 10:
            w("平均汚染スコアが10pp以下であり、シミュレータの推論力は概ね信頼できる。")
            w("LLMの学習データに含まれる歴史的結果への依存度は低い。")
        elif mean_score <= 20:
            w("平均汚染スコアが10-20ppであり、中程度のLLM知識依存がある。")
            w("匿名版の精度がシミュレータの実質的な予測力を示す。")
        else:
            w("平均汚染スコアが20pp以上であり、LLMの記憶への依存が大きい。")
            w("新規サービスの予測には匿名版の精度を参考にすべき。")
        w("")

    # 技術情報
    w("## 技術情報")
    w("")
    w("- シミュレーションエンジン: OASIS SNS Simulation")
    w("- エージェント行動決定: Ollama qwen3:14b")
    w("- レポート生成: Claude API")
    w("- シナリオテキスト: 各サービスの基準時点以前の情報のみ（未来情報除去済み）")
    w("- 匿名化: サービス名・創業者名・競合名等を架空名に置換")
    w(f"- 総実行時間: {total_time/3600:.1f}時間")
    w("")

    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(main())
