"""ベンチマーク評価の統合実行スクリプト.

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

  # 市場調査フェーズ付き実行
  uv run python scripts/run_benchmarks.py --with-research

  # JSON結果を出力
  uv run python scripts/run_benchmarks.py --output json

  # 一覧表示のみ
  uv run python scripts/run_benchmarks.py --list

前提:
  - Docker (Neo4j + Redis) が起動していること
  - Ollama が起動していること (qwen3:14b)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.job_manager import JobManager  # noqa: E402
from app.core.redis_client import RedisClient  # noqa: E402
from app.evaluation.benchmarks import get_benchmark, list_benchmarks  # noqa: E402
from app.evaluation.models import EvaluationResult, TokenUsageSummary  # noqa: E402
from app.evaluation.runner import (  # noqa: E402
    run_benchmark,
    run_benchmark_multi,
    run_benchmark_with_research,
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


# ─── 表示ユーティリティ ───


def _separator() -> str:
    return "=" * 70


def _format_token_summary(tu: TokenUsageSummary | None) -> str:
    """トークン情報を1行文字列にする."""
    if not tu or tu.total_tokens == 0:
        return ""
    return f"{tu.total_tokens:,} tokens, {tu.total_calls} calls, ${tu.estimated_cost_usd:.4f}"


def _token_usage_to_dict(tu: TokenUsageSummary) -> dict:
    """TokenUsageSummary をJSON出力用 dict に変換する."""
    return {
        "total_input_tokens": tu.total_input_tokens,
        "total_output_tokens": tu.total_output_tokens,
        "total_tokens": tu.total_tokens,
        "total_calls": tu.total_calls,
        "estimated_cost_usd": tu.estimated_cost_usd,
        "by_task_type": tu.by_task_type,
        "by_provider": tu.by_provider,
    }


def _get_token_field(r: dict, field: str) -> float:
    """結果dictからトークン情報のフィールドを取得する（dict/オブジェクト両対応）."""
    tu = r["token_usage"]
    if isinstance(tu, dict):
        return tu.get(field, 0)
    return getattr(tu, field, 0)


def _get_benchmark_or_exit(benchmark_id: str) -> object:
    """ベンチマークを取得し、見つからなければエラー終了する."""
    benchmark = get_benchmark(benchmark_id)
    if benchmark is None:
        logger.error("ベンチマーク '%s' が見つかりません", benchmark_id)
        available = [b.id for b in list_benchmarks()]
        logger.info("利用可能: %s", ", ".join(available))
        sys.exit(1)
    return benchmark


def _format_result_row(r: dict) -> str:
    """結果テーブルの1行."""
    if r.get("error"):
        return f"{r['name']:<30} {'ERROR':>6} {'N/A':>6} {'-':>4} {'N/A':>6} {r['time']:>6.0f}s"

    status = "PASS" if r["accuracy"] >= 0.6 else "FAIL"
    acc = f"{r['accuracy']:.0%}"
    outcome = (
        "OK" if r.get("outcome_correct") is True
        else "NG" if r.get("outcome_correct") is False
        else "-"
    )
    combined = (
        f"{r['combined_accuracy']:.0%}"
        if r.get("combined_accuracy") is not None
        else "N/A"
    )
    tokens_str = _format_token_summary(r.get("token_usage"))
    time_str = f"{r['time']:>6.0f}s"

    line = f"{r['name']:<30} {status:>6} {acc:>6} {outcome:>4} {combined:>6} {time_str}"
    if tokens_str:
        line += f"  [{tokens_str}]"
    return line


def _eval_to_row(result: EvaluationResult, elapsed: float) -> dict:
    """EvaluationResult を表示用 dict に変換する."""
    return {
        "id": result.benchmark_id,
        "name": result.benchmark_name,
        "accuracy": result.direction_accuracy,
        "combined_accuracy": result.combined_accuracy,
        "outcome_correct": result.outcome_correct,
        "expected_outcome": result.expected_outcome,
        "predicted_score": result.predicted_score,
        "predicted_verdict": result.predicted_verdict,
        "time": elapsed,
        "token_usage": result.token_usage,
        "trends": [
            {
                "metric": tr.metric,
                "ok": tr.direction_correct,
                "actual": tr.actual_direction.value,
                "expected": tr.expected_direction.value,
                "change_rate": tr.actual_change_rate,
            }
            for tr in result.trend_results
        ],
    }


# ─── テキスト出力 ───


def print_results_table(results: list[dict]) -> None:
    """結果テーブルを表示する."""
    print(_separator())
    print(f"{'ベンチマーク':<30} {'結果':>6} {'方向':>6} {'予測':>4} {'統合':>6} {'時間':>8}")
    print(_separator())
    for r in results:
        print(_format_result_row(r))
    print(_separator())

    accs = [r["accuracy"] for r in results if not r.get("error")]
    if not accs:
        return

    mean_acc = sum(accs) / len(accs)
    passed = sum(1 for a in accs if a >= 0.6)

    outcome_ok = sum(1 for r in results if r.get("outcome_correct") is True)
    outcome_total = sum(1 for r in results if r.get("outcome_correct") is not None)

    combined_accs = [r["combined_accuracy"] for r in results if r.get("combined_accuracy") is not None]
    mean_combined = sum(combined_accs) / len(combined_accs) if combined_accs else 0

    print(
        f"方向合格: {passed}/{len(results)} | 方向精度: {mean_acc:.1%} | "
        f"成功予測: {outcome_ok}/{outcome_total} | 統合精度: {mean_combined:.1%}"
    )

    # トークン集計
    token_usages = [r["token_usage"] for r in results if r.get("token_usage") and r["token_usage"].total_tokens > 0]
    if token_usages:
        total_tokens = sum(tu.total_tokens for tu in token_usages)
        total_calls = sum(tu.total_calls for tu in token_usages)
        total_cost = sum(tu.estimated_cost_usd for tu in token_usages)
        print(
            f"トークン合計: {total_tokens:,} tokens, {total_calls} calls, "
            f"${total_cost:.4f} (平均 ${total_cost / len(token_usages):.4f}/回)"
        )

        # プロバイダー別
        prov_totals: dict[str, dict[str, float]] = {}
        for tu in token_usages:
            for prov, data in tu.by_provider.items():
                if prov not in prov_totals:
                    prov_totals[prov] = {"input": 0, "output": 0, "calls": 0, "cost": 0.0}
                prov_totals[prov]["input"] += data.get("input_tokens", 0)
                prov_totals[prov]["output"] += data.get("output_tokens", 0)
                prov_totals[prov]["calls"] += data.get("calls", 0)
                prov_totals[prov]["cost"] += data.get("estimated_cost_usd", 0)
        for prov, pd in sorted(prov_totals.items(), key=lambda x: x[1]["cost"], reverse=True):
            print(
                f"  {prov}: input={pd['input']:,.0f} + output={pd['output']:,.0f} = "
                f"{pd['input']+pd['output']:,.0f} tokens, "
                f"{pd['calls']:.0f} calls, ${pd['cost']:.4f}"
            )


def print_trend_details(result: EvaluationResult) -> None:
    """トレンド詳細を表示する."""
    print("トレンド詳細:")
    for tr in result.trend_results:
        marker = "OK" if tr.direction_correct else "NG"
        print(
            f"  [{marker}] {tr.metric:<35} "
            f"期待={tr.expected_direction.value:<6} "
            f"実際={tr.actual_direction.value:<6} "
            f"変化率={tr.actual_change_rate:+.1f}%"
        )
    if result.outcome_correct is not None:
        outcome_mark = "OK" if result.outcome_correct else "NG"
        print(
            f"  [{outcome_mark}] 成功予測: スコア={result.predicted_score}, "
            f"verdict={result.predicted_verdict}, "
            f"期待={result.expected_outcome}"
        )


def print_multi_result(benchmark_name: str, stats) -> None:
    """統計評価結果を表示する."""
    print(_separator())
    print(f"統計評価: {benchmark_name}")
    print(f"実行回数: {stats.num_runs}")
    print(f"平均方向精度: {stats.mean_direction_accuracy:.1%}")
    print(f"標準偏差: {stats.stddev_direction_accuracy:.4f}")
    print(f"最小: {stats.min_direction_accuracy:.1%}")
    print(f"最大: {stats.max_direction_accuracy:.1%}")
    if stats.outcome_hit_rate is not None:
        print(f"成功予測ヒット率: {stats.outcome_hit_rate:.1%}")
    print()
    print("トレンド別ヒット率:")
    for metric, rate in stats.per_trend_hit_rates.items():
        marker = "OK" if rate >= 0.6 else "!!"
        print(f"  {metric:<40} {rate:>5.0%}  [{marker}]")

    # トークン集計
    token_usages = [
        r.token_usage for r in stats.per_run_results
        if r.token_usage and r.token_usage.total_tokens > 0
    ]
    if token_usages:
        avg_tokens = sum(tu.total_tokens for tu in token_usages) / len(token_usages)
        avg_cost = sum(tu.estimated_cost_usd for tu in token_usages) / len(token_usages)
        print(f"\nトークン使用量 (平均): {avg_tokens:,.0f} tokens, ${avg_cost:.4f}/回")

    print(_separator())


# ─── リサーチ付き実行の表示 ───


def print_research_result(result, elapsed: float) -> None:
    """リサーチ付きベンチマーク結果を表示する."""
    ev = result.evaluation
    cost_str = ""
    tokens_str = ""
    if ev.token_usage and ev.token_usage.total_tokens > 0:
        tokens_str = f", トークン={ev.token_usage.total_tokens:,}"
        cost_str = f", コスト=${ev.token_usage.estimated_cost_usd:.4f}"
    logger.info(
        "  → 方向精度=%.2f, 調査=%.1fs, シミュレーション=%.1fs, 合計=%.1fs%s%s",
        ev.direction_accuracy,
        result.research_time_seconds,
        ev.execution_time_seconds,
        elapsed,
        tokens_str,
        cost_str,
    )


# ─── JSON出力 ───


def _result_to_json(r: dict) -> dict:
    """表示用dict をJSON出力用に変換する."""
    out = {
        "id": r.get("id", ""),
        "name": r["name"],
        "accuracy": r["accuracy"],
        "combined_accuracy": r.get("combined_accuracy"),
        "status": "ERROR" if r.get("error") else ("PASS" if r["accuracy"] >= 0.6 else "FAIL"),
        "time": r["time"],
        "expected_outcome": r.get("expected_outcome"),
        "predicted_score": r.get("predicted_score"),
        "predicted_verdict": r.get("predicted_verdict"),
        "outcome_correct": r.get("outcome_correct"),
        "trends": r.get("trends", []),
    }
    tu = r.get("token_usage")
    if tu:
        out["token_usage"] = _token_usage_to_dict(tu)
    return out


def _research_result_to_json(result, elapsed: float) -> dict:
    """FullBenchmarkResult をJSON出力用に変換する."""
    ev = result.evaluation
    token_data = _token_usage_to_dict(ev.token_usage) if ev.token_usage else {}

    return {
        "benchmark_id": result.benchmark_id,
        "benchmark_name": result.benchmark_name,
        "direction_accuracy": ev.direction_accuracy,
        "combined_accuracy": ev.combined_accuracy,
        "outcome_correct": ev.outcome_correct,
        "trend_results": [
            {
                "metric": t.metric,
                "expected": t.expected_direction.value,
                "actual": t.actual_direction.value,
                "change_rate": t.actual_change_rate,
                "correct": t.direction_correct,
            }
            for t in ev.trend_results
        ],
        "research_time_seconds": result.research_time_seconds,
        "simulation_time_seconds": ev.execution_time_seconds,
        "total_time_seconds": round(elapsed, 2),
        "sources_used": result.research.sources_used,
        "research_errors": result.research.errors,
        "trends_count": result.research.trends_count,
        "github_repos_count": result.research.github_repos_count,
        "finance_data_count": result.research.finance_data_count,
        "token_usage": token_data,
    }


# ─── レポートファイル生成 ───


def generate_report_file(
    all_results: list[dict],
    total_elapsed: float,
    output_path: Path,
    *,
    with_research: bool = False,
) -> None:
    """テキストレポートをファイルに出力する."""
    lines: list[str] = []
    mode = "市場調査 + シミュレーション + 評価" if with_research else "シミュレーション + 評価"
    lines.append(_separator())
    lines.append(f"EchoShoal ベンチマーク結果 ({mode})")
    lines.append(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"実行数: {len(all_results)}")
    lines.append(f"総実行時間: {total_elapsed / 60:.1f}分")
    lines.append(_separator())
    lines.append("")

    # ベンチマーク別集計
    benchmark_ids = list(dict.fromkeys(r.get("id", r.get("benchmark_id", "")) for r in all_results))
    for bid in benchmark_ids:
        runs = [r for r in all_results if r.get("id", r.get("benchmark_id", "")) == bid]
        name = runs[0].get("name", runs[0].get("benchmark_name", bid))
        successes = [r for r in runs if not r.get("error")]
        errors = [r for r in runs if r.get("error")]

        lines.append(f"■ {name} ({bid})")
        lines.append(f"  成功: {len(successes)}/{len(runs)}, エラー: {len(errors)}")

        if successes:
            accs = [r["accuracy"] for r in successes]
            mean_acc = sum(accs) / len(accs)
            if len(accs) > 1:
                variance = sum((a - mean_acc) ** 2 for a in accs) / (len(accs) - 1)
                stddev = math.sqrt(variance)
                lines.append(f"  方向精度: mean={mean_acc:.4f}, stddev={stddev:.4f}, min={min(accs):.4f}, max={max(accs):.4f}")
            else:
                lines.append(f"  方向精度: {mean_acc:.4f}")

            # トレンドごとのヒット率
            trend_hits: dict[str, int] = {}
            trend_total: dict[str, int] = {}
            for r in successes:
                for t in r.get("trends", []):
                    metric = t["metric"]
                    trend_total[metric] = trend_total.get(metric, 0) + 1
                    if t["ok"]:
                        trend_hits[metric] = trend_hits.get(metric, 0) + 1
            for metric in trend_total:
                hits = trend_hits.get(metric, 0)
                total = trend_total[metric]
                lines.append(f"    {metric}: {hits}/{total} ({hits/total*100:.0f}%)")

            # トークン使用量
            token_runs = [r for r in successes if r.get("token_usage")]
            if token_runs:
                avg_tokens = sum(_get_token_field(r, "total_tokens") for r in token_runs) / len(token_runs)
                avg_calls = sum(_get_token_field(r, "total_calls") for r in token_runs) / len(token_runs)
                avg_cost = sum(_get_token_field(r, "estimated_cost_usd") for r in token_runs) / len(token_runs)
                lines.append(f"  トークン使用量 (平均): {avg_tokens:,.0f} tokens, {avg_calls:.0f} calls, ${avg_cost:.4f}/回")

            # 実行時間
            avg_time = sum(r["time"] for r in successes) / len(successes)
            lines.append(f"  平均時間: {avg_time:.1f}s")

        lines.append("")

    # 全体サマリー
    all_accs = [r["accuracy"] for r in all_results if not r.get("error")]
    total_errors = sum(1 for r in all_results if r.get("error"))
    if all_accs:
        lines.append(_separator())
        lines.append("全体サマリー")
        lines.append(f"  全体方向精度: {sum(all_accs)/len(all_accs):.4f}")
        lines.append(f"  成功: {len(all_accs)}/{len(all_results)}, エラー: {total_errors}")
        passed = sum(1 for a in all_accs if a >= 0.6)
        lines.append(f"  パス率(≥60%): {passed}/{len(all_accs)} ({passed/len(all_accs)*100:.1f}%)")
        lines.append(_separator())

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("レポート保存: %s", output_path)


# ─── インフラ確認 ───


async def check_infrastructure() -> bool:
    """インフラの接続確認."""
    errors = []

    try:
        redis = RedisClient()
        if not await redis.is_available():
            errors.append("Redis に接続できません (docker compose up -d)")
    except Exception:
        errors.append("Redis に接続できません (docker compose up -d)")

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


# ─── メイン ───


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
        "--with-research",
        action="store_true",
        help="市場調査フェーズ付きで実行",
    )
    parser.add_argument(
        "--output", "-o",
        choices=["text", "json"],
        default="text",
        help="出力形式（デフォルト: text）",
    )
    parser.add_argument(
        "--report",
        help="テキストレポートの出力先パス（指定時のみ生成）",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="ベンチマーク一覧を表示して終了",
    )
    parser.add_argument(
        "--log-file",
        help="ログファイルの出力先パス（指定時のみ）",
    )
    args = parser.parse_args()

    # ログファイル
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(file_handler)

    # 一覧表示
    if args.list:
        benchmarks = list_benchmarks()
        print(_separator())
        print(f"{'ID':<30} {'名前':<30} {'トレンド':>6} {'ラウンド':>8} {'タグ'}")
        print(_separator())
        for b in benchmarks:
            tags = ", ".join(b.tags)
            print(
                f"{b.id:<30} {b.name:<30} {len(b.expected_trends):>6} "
                f"{b.scenario_input.num_rounds:>8}  {tags}"
            )
        print(_separator())
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

    all_results: list[dict] = []
    json_results: list[dict] = []

    # Ctrl+C でグレースフルシャットダウン
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _on_sigint() -> None:
        if not shutdown_event.is_set():
            shutdown_event.set()
            logger.warning("Ctrl+C を検出 — 実行を中断しています...")

    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, _on_sigint)
    else:
        signal.signal(signal.SIGINT, lambda *_: _on_sigint())

    try:
        if args.with_research:
            await _run_with_research(args, job_manager, all_results, json_results, shutdown=shutdown_event)
        elif args.runs >= 2:
            await _run_multi(args, job_manager, all_results, json_results, shutdown=shutdown_event)
        else:
            await _run_single(args, job_manager, all_results, json_results, shutdown=shutdown_event)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.warning("ベンチマーク実行を中断しました")

    elapsed = time.monotonic() - start_time
    print(f"\n総実行時間: {elapsed:.1f}s ({elapsed / 60:.1f}分)")

    if shutdown_event.is_set():
        print("\n⚠ 中断されました。Ollama の GPU を解放するには:")
        print("  ollama stop qwen3:14b")

    # JSON出力
    if args.output == "json" and json_results:
        output_path = Path("benchmark_results.json")
        output_path.write_text(json.dumps(json_results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"詳細結果: {output_path}")

    # レポートファイル
    if args.report and all_results:
        generate_report_file(
            all_results, elapsed, Path(args.report),
            with_research=args.with_research,
        )

    try:
        await redis.close()
    except Exception:
        pass


async def _run_single(
    args: argparse.Namespace,
    job_manager: JobManager,
    all_results: list[dict],
    json_results: list[dict],
    *,
    shutdown: asyncio.Event | None = None,
) -> None:
    """通常実行（各ベンチマーク1回）."""
    if args.benchmark:
        # 特定ベンチマーク
        benchmark = _get_benchmark_or_exit(args.benchmark)

        logger.info("ベンチマーク実行: %s", benchmark.name)
        start = time.monotonic()
        result = await run_benchmark(args.benchmark, job_manager)
        elapsed = time.monotonic() - start

        row = _eval_to_row(result, elapsed)
        all_results.append(row)
        json_results.append(_result_to_json(row))

        print_results_table([row])
        print()
        print_trend_details(result)
    else:
        # 全件
        logger.info("全ベンチマーク評価開始 (%d件)", len(list_benchmarks()))
        benchmarks = list_benchmarks()

        for i, b in enumerate(benchmarks):
            if shutdown and shutdown.is_set():
                logger.warning("中断: 残り %d 件をスキップ", len(benchmarks) - i)
                break

            logger.info("[%d/%d] %s", i + 1, len(benchmarks), b.name)
            start = time.monotonic()
            try:
                result = await run_benchmark(b.id, job_manager)
                elapsed = time.monotonic() - start

                row = _eval_to_row(result, elapsed)
                all_results.append(row)
                json_results.append(_result_to_json(row))

                status = "PASS" if result.direction_accuracy >= 0.6 else "FAIL"
                logger.info("  → %s 方向精度=%.1%%  (%.0fs)", status, result.direction_accuracy * 100, elapsed)

                # 個別トレンド表示
                for tr in result.trend_results:
                    mark = "OK" if tr.direction_correct else "NG"
                    logger.info("     [%s] %s: %s (期待: %s)", mark, tr.metric, tr.actual_direction.value, tr.expected_direction.value)

            except Exception as e:
                elapsed = time.monotonic() - start
                logger.error("  → ERROR: %s (%.0fs)", e, elapsed)
                row = {"id": b.id, "name": b.name, "accuracy": 0, "error": True, "time": elapsed}
                all_results.append(row)
                json_results.append({"id": b.id, "name": b.name, "status": "ERROR", "error": str(e), "time": round(elapsed, 1)})

        print()
        print_results_table(all_results)


async def _run_multi(
    args: argparse.Namespace,
    job_manager: JobManager,
    all_results: list[dict],
    json_results: list[dict],
    *,
    shutdown: asyncio.Event | None = None,
) -> None:
    """統計評価（N回実行）."""
    if args.benchmark:
        benchmark = _get_benchmark_or_exit(args.benchmark)

        logger.info("統計評価開始: %s (%d回実行)", benchmark.name, args.runs)
        stats = await run_benchmark_multi(args.benchmark, job_manager, args.runs)
        print_multi_result(benchmark.name, stats)

        for r in stats.per_run_results:
            row = _eval_to_row(r, r.execution_time_seconds)
            all_results.append(row)
            json_results.append(_result_to_json(row))
    else:
        # 全件×N回
        logger.info("全ベンチマーク統計評価: 各%d回実行", args.runs)
        benchmarks = list_benchmarks()
        all_stats = []
        for b in benchmarks:
            if shutdown and shutdown.is_set():
                logger.warning("中断: 残りのベンチマークをスキップ")
                break

            logger.info("\n--- %s ---", b.name)
            stats = await run_benchmark_multi(b.id, job_manager, args.runs)
            all_stats.append((b.name, stats))
            print_multi_result(b.name, stats)

            for r in stats.per_run_results:
                row = _eval_to_row(r, r.execution_time_seconds)
                all_results.append(row)
                json_results.append(_result_to_json(row))

        # 全体サマリー
        print(_separator())
        print("全体サマリー")
        print(_separator())
        print(f"{'ベンチマーク':<30} {'平均精度':>8} {'標準偏差':>8} {'予測率':>8} {'実行数':>6}")
        print(_separator())
        for name, stats in all_stats:
            outcome_str = f"{stats.outcome_hit_rate:.1%}" if stats.outcome_hit_rate is not None else "N/A"
            print(
                f"{name:<30} {stats.mean_direction_accuracy:>7.1%} "
                f"{stats.stddev_direction_accuracy:>8.4f} "
                f"{outcome_str:>8} "
                f"{len(stats.per_run_results):>5}/{stats.num_runs}"
            )


async def _run_with_research(
    args: argparse.Namespace,
    job_manager: JobManager,
    all_results: list[dict],
    json_results: list[dict],
    *,
    shutdown: asyncio.Event | None = None,
) -> None:
    """市場調査付き実行."""
    if args.benchmark:
        benchmarks_to_run = [_get_benchmark_or_exit(args.benchmark)]
    else:
        benchmarks_to_run = list_benchmarks()

    total_runs = len(benchmarks_to_run) * args.runs
    run_count = 0

    logger.info("市場調査付きベンチマーク: %d件 × %d回 = %d実行", len(benchmarks_to_run), args.runs, total_runs)

    for b_idx, benchmark in enumerate(benchmarks_to_run):
        if shutdown and shutdown.is_set():
            logger.warning("中断: 残りのベンチマークをスキップ")
            break

        logger.info("[%d/%d] %s (×%d回)", b_idx + 1, len(benchmarks_to_run), benchmark.name, args.runs)

        for run_idx in range(args.runs):
            if shutdown and shutdown.is_set():
                logger.warning("中断: 残りの実行をスキップ")
                break

            run_count += 1
            logger.info("  実行 %d/%d (全体 %d/%d)", run_idx + 1, args.runs, run_count, total_runs)

            run_start = time.monotonic()
            try:
                result = await run_benchmark_with_research(benchmark.id, job_manager)
                elapsed = time.monotonic() - run_start

                print_research_result(result, elapsed)

                row = _eval_to_row(result.evaluation, elapsed)
                row["research_time"] = result.research_time_seconds
                all_results.append(row)
                json_results.append(_research_result_to_json(result, elapsed))

            except Exception:
                elapsed = time.monotonic() - run_start
                logger.exception("  → 失敗 (%.1fs)", elapsed)
                row = {"id": benchmark.id, "name": benchmark.name, "accuracy": 0, "error": True, "time": elapsed}
                all_results.append(row)
                json_results.append({
                    "benchmark_id": benchmark.id,
                    "benchmark_name": benchmark.name,
                    "error": True,
                    "total_time_seconds": round(elapsed, 2),
                })

    print()
    print_results_table(all_results)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n中断されました。Ollama の GPU を解放するには:")
        print("  ollama stop qwen3:14b")
