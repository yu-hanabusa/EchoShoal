"""全ベンチマーク1回ずつ実行スクリプト（CLIから直接実行）."""
import asyncio
import json
import time

async def main():
    from app.core.redis_client import RedisClient
    from app.core.job_manager import JobManager
    from app.evaluation.benchmarks import list_benchmarks
    from app.evaluation.runner import run_benchmark

    redis = RedisClient()
    job_manager = JobManager(redis)

    benchmarks = list_benchmarks()
    print(f"=== 全ベンチマーク実行開始: {len(benchmarks)}件 ===\n")

    results = []
    total_start = time.monotonic()

    for i, b in enumerate(benchmarks):
        print(f"[{i+1}/{len(benchmarks)}] {b.name} ({b.id})...")
        start = time.monotonic()
        try:
            result = await run_benchmark(b.id, job_manager)
            elapsed = time.monotonic() - start
            status = "PASS" if result.direction_accuracy >= 0.6 else "FAIL"
            print(f"  -> {status} 精度={result.direction_accuracy:.1%} ({elapsed:.0f}s)")
            for tr in result.trend_results:
                mark = "OK" if tr.direction_correct else "NG"
                print(f"     [{mark}] {tr.metric}: {tr.actual_direction} (期待: {tr.expected_direction})")
            results.append({
                "id": b.id,
                "name": b.name,
                "accuracy": result.direction_accuracy,
                "status": status,
                "time": round(elapsed, 1),
                "trends": [
                    {"metric": tr.metric, "ok": tr.direction_correct,
                     "actual": tr.actual_direction, "expected": tr.expected_direction}
                    for tr in result.trend_results
                ],
            })
        except Exception as e:
            elapsed = time.monotonic() - start
            print(f"  -> ERROR: {e} ({elapsed:.0f}s)")
            results.append({"id": b.id, "name": b.name, "status": "ERROR", "error": str(e), "time": round(elapsed, 1)})

    total_elapsed = time.monotonic() - total_start

    # サマリ
    print(f"\n{'='*60}")
    print(f"{'ベンチマーク':<30} {'結果':>6} {'精度':>8} {'時間':>8}")
    print(f"{'-'*60}")
    for r in results:
        acc = f"{r.get('accuracy', 0):.1%}" if r['status'] != 'ERROR' else 'N/A'
        print(f"{r['name']:<30} {r['status']:>6} {acc:>8} {r['time']:>6.0f}s")

    passed = sum(1 for r in results if r['status'] == 'PASS')
    accs = [r['accuracy'] for r in results if r['status'] != 'ERROR']
    mean_acc = sum(accs) / len(accs) if accs else 0
    print(f"{'-'*60}")
    print(f"合格: {passed}/{len(results)} | 平均精度: {mean_acc:.1%} | 合計時間: {total_elapsed:.0f}s")

    # JSON出力
    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n詳細結果: benchmark_results.json")

if __name__ == "__main__":
    asyncio.run(main())
