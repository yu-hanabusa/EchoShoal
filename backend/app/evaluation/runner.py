"""評価ランナー — ベンチマーク実行のオーケストレーション.

既存のシミュレーションインフラ（LLM, Neo4j, Redis）を使って
ベンチマークシナリオを実行し、結果を期待値と比較する。

複数回実行の統計機能により、LLMの非決定性を考慮した有効性評価が可能。
補足資料（scenarios/{id}/*.txt）が存在する場合は自動的に読み込み、
知識グラフに格納してシミュレーション精度を向上させる。
"""

from __future__ import annotations

import logging
import math
import time
from pathlib import Path

from app.core.graph.agent_memory import AgentMemoryStore
from app.core.graph.client import GraphClient
from app.core.graph.rag import GraphRAGRetriever
from app.core.job_manager import JobManager
from app.core.llm.router import LLMRouter
from app.evaluation.benchmarks import get_benchmark, list_benchmarks
from app.evaluation.comparator import evaluate_benchmark
from app.evaluation.models import (
    AgentRecord,
    BenchmarkScenario,
    DimensionTimeline,
    EvaluationResult,
    EvaluationSuiteResult,
    FullBenchmarkResult,
    ResearchData,
    RunStatistics,
    TokenUsageSummary,
)
from app.simulation.agent_generator import AgentGenerator
from app.simulation.events.scheduler import EventScheduler
from app.simulation.models import RoundResult
from app.simulation.scenario_analyzer import ScenarioAnalyzer

logger = logging.getLogger(__name__)

# 補足資料ディレクトリ
_SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


async def _setup_graph_components(
    simulation_id: str,
) -> tuple[GraphRAGRetriever | None, AgentMemoryStore | None, GraphClient | None]:
    """グラフコンポーネントの初期化（シミュレーションルートと同じパターン）."""
    try:
        graph_client = GraphClient()
        if not await graph_client.is_available():
            return None, None, None
        agent_memory = AgentMemoryStore(graph_client, simulation_id=simulation_id)
        rag = GraphRAGRetriever(graph_client, agent_memory, simulation_id=simulation_id)
        return rag, agent_memory, graph_client
    except Exception:
        logger.warning("グラフコンポーネント初期化失敗: simulation_id=%s", simulation_id)
        return None, None, None


def _load_scenario_documents(benchmark_id: str) -> list[tuple[str, str]]:
    """補足資料ディレクトリからテキストファイルを読み込む.

    Returns:
        list of (filename, text) tuples
    """
    scenario_dir = _SCENARIOS_DIR / benchmark_id
    if not scenario_dir.is_dir():
        return []

    docs: list[tuple[str, str]] = []
    for txt_file in sorted(scenario_dir.glob("*.txt")):
        try:
            text = txt_file.read_text(encoding="utf-8")
            if text.strip():
                docs.append((txt_file.name, text))
        except Exception:
            logger.warning("補足資料の読み込み失敗: %s", txt_file)
    return docs


async def _process_scenario_documents(
    docs: list[tuple[str, str]],
    graph_client: GraphClient,
    simulation_id: str,
) -> None:
    """補足資料を知識グラフに格納する."""
    from app.core.documents.parser import DocumentParser
    from app.core.documents.processor import DocumentProcessor

    parser = DocumentParser()
    processor = DocumentProcessor(graph_client, simulation_id=simulation_id)

    for filename, text in docs:
        try:
            parsed = parser.parse(text.encode("utf-8"), filename, source="benchmark")
            await processor.process(parsed)
            logger.info("補足資料を処理: %s (%d文字)", filename, len(text))
        except Exception:
            logger.warning("補足資料の処理失敗: %s", filename)


from dataclasses import dataclass, field as dc_field


def _extract_token_usage(summary: dict) -> TokenUsageSummary | None:
    """engine.get_summary() の token_usage を TokenUsageSummary に変換する."""
    raw = summary.get("token_usage")
    if not raw:
        return None
    total = raw.get("total", {})
    return TokenUsageSummary(
        total_input_tokens=total.get("input_tokens", 0),
        total_output_tokens=total.get("output_tokens", 0),
        total_tokens=total.get("total_tokens", 0),
        total_calls=total.get("calls", 0),
        estimated_cost_usd=total.get("estimated_cost_usd", 0.0),
        by_task_type=raw.get("by_task_type", {}),
        by_provider=raw.get("by_provider", {}),
        agent_conversations=raw.get("agent_conversations", []),
    )


@dataclass
class _SimulationOutput:
    """シミュレーション結果とメタデータ."""

    rounds: list[RoundResult]
    summary: dict = dc_field(default_factory=dict)  # engine.get_summary() の結果
    report: dict | None = None
    social_feed: list[dict] | None = None

    @property
    def agent_summaries(self) -> list[dict]:
        return self.summary.get("agents", [])


async def run_simulation_for_benchmark(
    benchmark: BenchmarkScenario,
    job_id: str,
    job_manager: JobManager,
    collected_data: object | None = None,
    stakeholder_report: str = "",
) -> _SimulationOutput:
    """ベンチマーク用にシミュレーションを実行し、結果を返す."""
    scenario = benchmark.scenario_input

    await job_manager.set_running(job_id)

    # 全体ステップ: 準備4 + シミュレーションN + 完了1 = N+5
    total_steps = scenario.num_rounds + 5
    step = 0

    llm = LLMRouter()

    step += 1
    await job_manager.update_progress(job_id, step, total_steps, phase="シナリオ解析中")
    analyzer = ScenarioAnalyzer(llm=llm)
    enriched = await analyzer.analyze_async(scenario)

    rag, agent_memory, graph_client = await _setup_graph_components(job_id)

    try:
        # 補足資料の読み込みと知識グラフ格納
        docs = _load_scenario_documents(benchmark.id)
        if docs and graph_client:
            logger.info("補足資料 %d件を読み込み: %s", len(docs), benchmark.id)
            await _process_scenario_documents(docs, graph_client, job_id)
        elif docs:
            logger.info(
                "補足資料 %d件あるがグラフ未接続のためスキップ: %s",
                len(docs), benchmark.id,
            )

        # エージェントへのドキュメントエンティティ受け渡し
        doc_entities = None
        if docs and graph_client:
            from app.core.documents.processor import DocumentProcessor
            proc = DocumentProcessor(graph_client, simulation_id=job_id)
            doc_entities = await proc.get_document_entities()

        step += 1
        await job_manager.update_progress(job_id, step, total_steps, phase="エージェント生成中")
        generator = AgentGenerator(llm)
        agents = await generator.generate(
            scenario, enriched, doc_entities, collected_data, stakeholder_report,
        )

        step += 1
        await job_manager.update_progress(job_id, step, total_steps, phase="イベントスケジュール生成中")
        event_scheduler = EventScheduler(llm=llm)
        await event_scheduler.generate_from_scenario(scenario)

        step += 1
        await job_manager.update_progress(job_id, step, total_steps, phase="市場初期状態をLLMが推定中")

        async def on_progress(current: int, total: int) -> None:
            await job_manager.update_progress(
                job_id, step + current, total_steps,
                phase=f"{current}ヶ月目をシミュレーション中（{total}ヶ月中）",
            )

        from app.oasis.simulation_runner import OASISSimulationEngine
        oasis_engine = None
        social_feed = None

        oasis_engine = OASISSimulationEngine(
            agents=agents, llm=llm, scenario=scenario,
            on_progress=on_progress, event_scheduler=event_scheduler,
            enriched_scenario=enriched, simulation_id=job_id,
            rag=rag, agent_memory=agent_memory,
        )

        # 市場調査の財務データをmarket_analyzer用に設定
        if collected_data and hasattr(collected_data, "finance_data"):
            finance_lines = []
            for fd in collected_data.finance_data:
                parts = [fd.company_name]
                if fd.market_cap:
                    parts.append(f"時価総額${fd.market_cap/1e9:.0f}B")
                if fd.revenue:
                    parts.append(f"売上${fd.revenue/1e9:.1f}B")
                finance_lines.append(" / ".join(parts))
            if finance_lines:
                oasis_engine._finance_summary = (
                    "関連企業の財務状況:\n" + "\n".join(f"  {l}" for l in finance_lines)
                )

        engine = oasis_engine

        rounds = await engine.run()
        summary = engine.get_summary()

        # OASISソーシャルフィード取得 + グラフ同期
        if oasis_engine is not None:
            try:
                social_feed = oasis_engine.get_social_feed()
            except Exception:
                logger.warning("OASISソーシャルフィード取得失敗")

            # OASIS → Neo4j グラフ同期（関係線の描画に必要）
            if graph_client and agent_memory:
                try:
                    from app.oasis.graph_sync import sync_oasis_to_neo4j
                    from app.oasis.config import get_database_path

                    oasis_id_map = {}
                    for i, agent in enumerate(agents):
                        oasis_id_map[i] = agent.id

                    sync_result = await sync_oasis_to_neo4j(
                        db_path=get_database_path(job_id),
                        graph_client=graph_client,
                        simulation_id=job_id,
                        agent_id_map=oasis_id_map,
                    )
                    logger.info(
                        "OASISグラフ同期完了: %dエッジ同期 (%dエラー)",
                        sync_result.edges_synced, sync_result.errors,
                    )
                except Exception:
                    logger.warning("OASISグラフ同期失敗: benchmark=%s", benchmark.id)

        # レポート生成
        report_dict = None
        try:
            from app.reports.extractor import build_report_data
            from app.reports.generator import ReportGenerator
            report_input = build_report_data(
                rounds=rounds,
                scenario_description=scenario.description,
                agents_summary=summary.get("agents", []),
                confidence_notes=(
                    enriched.interpolated_info.confidence_notes
                    if enriched and enriched.interpolated_info else None
                ),
            )
            report_generator = ReportGenerator(llm=llm)
            report = await report_generator.generate(report_input)
            report_dict = report.model_dump()
            logger.info("レポート生成完了: benchmark=%s", benchmark.id)
        except Exception:
            logger.warning("レポート生成失敗: benchmark=%s", benchmark.id)

        return _SimulationOutput(
            rounds=rounds,
            summary=summary,
            report=report_dict,
            social_feed=social_feed,
        )
    finally:
        if graph_client:
            try:
                await graph_client.close()
            except Exception:
                logger.debug("GraphClient close失敗（ベンチマーク終了処理中）")


async def run_benchmark(
    benchmark_id: str,
    job_manager: JobManager,
) -> EvaluationResult:
    """単一ベンチマークを実行して評価結果を返す."""
    benchmark = get_benchmark(benchmark_id)
    if benchmark is None:
        msg = f"ベンチマーク '{benchmark_id}' が見つかりません"
        raise ValueError(msg)

    job_id = await job_manager.create_job(
        scenario_description=f"[評価] {benchmark.name}",
    )
    await job_manager.save_scenario(job_id, benchmark.scenario_input.model_dump())

    start_time = time.monotonic()

    try:
        output = await run_simulation_for_benchmark(benchmark, job_id, job_manager)
        results = output.rounds
        elapsed = time.monotonic() - start_time

        success_score = output.report.get("success_score") if output.report else None
        evaluation = evaluate_benchmark(benchmark, results, success_score=success_score)
        evaluation.execution_time_seconds = round(elapsed, 2)

        # ディメンション推移を記録
        from app.simulation.models import MarketDimension
        for dim in MarketDimension:
            values = [
                r.market_state.dimensions.get(dim, 0.0) for r in results
            ]
            evaluation.dimension_timelines.append(
                DimensionTimeline(dimension=dim.value, values=values)
            )

        # エージェント情報を記録
        for agent_sum in output.agent_summaries:
            evaluation.agents.append(AgentRecord(
                name=agent_sum.get("name", ""),
                stakeholder_type=agent_sum.get("stakeholder_type", ""),
                actions=agent_sum.get("action_types", []),
            ))

        # トークン使用量を記録
        evaluation.token_usage = _extract_token_usage(output.summary)

        # 結果をRedisに保存（通常シミュレーションと同じ形式 + 評価情報）
        summary = output.summary
        result_data = {
            "scenario": benchmark.scenario_input.model_dump(),
            "summary": summary,
            "rounds": [r.model_dump() for r in results],
            "report": output.report,
            "evaluation": evaluation.model_dump(),
            "benchmark_id": benchmark_id,
        }
        if output.social_feed:
            result_data["social_feed"] = output.social_feed
        await job_manager.set_completed(job_id, result_data)

        logger.info(
            "評価完了: %s — 方向精度=%.2f, 実行時間=%.1fs",
            benchmark.name,
            evaluation.direction_accuracy,
            elapsed,
        )
        return evaluation

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        logger.exception("評価失敗: %s", benchmark.name)
        await job_manager.set_failed(job_id, str(exc))
        raise


async def run_benchmark_multi(
    benchmark_id: str,
    job_manager: JobManager,
    num_runs: int = 5,
    parent_job_id: str | None = None,
) -> RunStatistics:
    """同一ベンチマークを複数回実行し、統計情報を返す.

    LLMの非決定性を考慮し、方向一致の再現性を統計的に評価する。
    """
    per_run_results: list[EvaluationResult] = []

    for i in range(num_runs):
        logger.info("ベンチマーク '%s' 実行 %d/%d", benchmark_id, i + 1, num_runs)
        if parent_job_id:
            await job_manager.update_progress(
                parent_job_id, i + 1, num_runs,
                phase=f"実行 {i + 1}/{num_runs} 回目",
            )
        try:
            result = await run_benchmark(benchmark_id, job_manager)
            per_run_results.append(result)
        except Exception:
            logger.exception("実行 %d/%d 失敗、スキップ", i + 1, num_runs)

    if not per_run_results:
        return RunStatistics(
            num_runs=num_runs,
            per_run_results=[],
            mean_direction_accuracy=0.0,
            stddev_direction_accuracy=0.0,
            min_direction_accuracy=0.0,
            max_direction_accuracy=0.0,
            per_trend_hit_rates={},
        )

    accuracies = [r.direction_accuracy for r in per_run_results]
    mean_acc = sum(accuracies) / len(accuracies)

    if len(accuracies) > 1:
        variance = sum((a - mean_acc) ** 2 for a in accuracies) / (len(accuracies) - 1)
        stddev_acc = math.sqrt(variance)
    else:
        stddev_acc = 0.0

    # 各トレンドごとのヒット率を計算
    benchmark = get_benchmark(benchmark_id)
    per_trend_hit_rates: dict[str, float] = {}
    if benchmark:
        for et in benchmark.expected_trends:
            hits = sum(
                1 for result in per_run_results
                for tr in result.trend_results
                if tr.metric == et.metric and tr.direction_correct
            )
            per_trend_hit_rates[et.metric] = hits / len(per_run_results)

    outcome_evaluated = [r for r in per_run_results if r.outcome_correct is not None]
    outcome_hit_rate = (
        sum(1 for r in outcome_evaluated if r.outcome_correct) / len(outcome_evaluated)
        if outcome_evaluated else None
    )

    return RunStatistics(
        num_runs=num_runs,
        per_run_results=per_run_results,
        mean_direction_accuracy=round(mean_acc, 4),
        stddev_direction_accuracy=round(stddev_acc, 4),
        min_direction_accuracy=round(min(accuracies), 4),
        max_direction_accuracy=round(max(accuracies), 4),
        per_trend_hit_rates=per_trend_hit_rates,
        outcome_hit_rate=outcome_hit_rate,
    )


async def run_benchmark_with_research(
    benchmark_id: str,
    job_manager: JobManager,
    parent_job_id: str | None = None,
) -> FullBenchmarkResult:
    """市場調査 → シミュレーション → 評価の一連ベンチマークを実行する.

    1. 市場調査パイプラインでデータ収集 + レポート生成
    2. 調査結果をドキュメントとしてシミュレーションに渡す
    3. シミュレーション実行 + 期待トレンド比較
    """
    benchmark = get_benchmark(benchmark_id)
    if benchmark is None:
        msg = f"ベンチマーク '{benchmark_id}' が見つかりません"
        raise ValueError(msg)

    scenario = benchmark.scenario_input
    total_time_start = time.monotonic()

    job_id = await job_manager.create_job(
        scenario_description=f"[市場調査+評価] {benchmark.name}",
    )
    await job_manager.save_scenario(job_id, scenario.model_dump())

    if parent_job_id:
        await job_manager.update_progress(
            parent_job_id, 1, 3, phase=f"市場調査中: {benchmark.name}",
        )

    # ── Phase 1: 市場調査 ──
    research_start = time.monotonic()
    research_data = ResearchData()
    research_collected_data = None  # 構造化データ（エージェント生成に渡す）
    research_stakeholder_report = ""  # ステークホルダーレポート（エージェント補完に渡す）

    try:
        from app.core.market_research.pipeline import run_market_research
        from app.simulation.scenario_analyzer import ScenarioAnalyzer

        llm = LLMRouter()

        # 競合推定
        competitors: list[str] = []
        try:
            analyzer = ScenarioAnalyzer(llm=llm)
            enriched = await analyzer.analyze_async(scenario)
            if enriched.interpolated_info:
                competitors = enriched.interpolated_info.competitors
        except Exception:
            logger.warning("競合推定失敗（市場調査は続行）: benchmark=%s", benchmark_id)

        result = await run_market_research(
            service_name=scenario.service_name,
            description=scenario.description,
            target_year=scenario.target_year,
            competitors=competitors,
            llm=llm,
        )

        research_collected_data = result.collected_data
        research_stakeholder_report = result.stakeholders

        research_data = ResearchData(
            market_report=result.market_report,
            user_behavior=result.user_behavior,
            stakeholders=result.stakeholders,
            sources_used=result.collected_data.sources_used,
            errors=result.collected_data.errors,
            trends_count=len(result.collected_data.trends),
            github_repos_count=len(result.collected_data.github_repos),
            finance_data_count=len(result.collected_data.finance_data),
        )

        # 市場調査結果をNeo4jドキュメントとして格納
        from app.core.graph.client import GraphClient as _GC
        try:
            gc = _GC()
            if await gc.is_available():
                from app.core.documents.models import ParsedDocument
                from app.core.documents.processor import DocumentProcessor
                processor = DocumentProcessor(gc, simulation_id=job_id)
                for fname, text in [
                    ("market_report.txt", result.market_report),
                    ("user_behavior.txt", result.user_behavior),
                    ("stakeholders.txt", result.stakeholders),
                ]:
                    if text.strip():
                        doc = ParsedDocument(
                            text=text, filename=fname, source="market_research",
                        )
                        await processor.process(doc)
                await gc.close()
        except Exception:
            logger.warning("市場調査ドキュメント格納失敗: benchmark=%s", benchmark_id)

        logger.info(
            "市場調査完了: benchmark=%s, sources=%s, errors=%d",
            benchmark_id, research_data.sources_used, len(research_data.errors),
        )
    except Exception:
        logger.exception("市場調査失敗: benchmark=%s", benchmark_id)

    research_time = time.monotonic() - research_start

    # ── Phase 2: シミュレーション + 評価 ──
    if parent_job_id:
        await job_manager.update_progress(
            parent_job_id, 2, 3, phase=f"シミュレーション実行中: {benchmark.name}",
        )

    sim_start = time.monotonic()

    try:
        output = await run_simulation_for_benchmark(
            benchmark, job_id, job_manager,
            collected_data=research_collected_data,
            stakeholder_report=research_stakeholder_report,
        )
        results = output.rounds

        success_score = output.report.get("success_score") if output.report else None
        evaluation = evaluate_benchmark(benchmark, results, success_score=success_score)
        evaluation.execution_time_seconds = round(time.monotonic() - sim_start, 2)

        # ディメンション推移を記録
        from app.simulation.models import MarketDimension
        for dim in MarketDimension:
            values = [
                r.market_state.dimensions.get(dim, 0.0) for r in results
            ]
            evaluation.dimension_timelines.append(
                DimensionTimeline(dimension=dim.value, values=values)
            )

        # エージェント情報を記録
        for agent_sum in output.agent_summaries:
            evaluation.agents.append(AgentRecord(
                name=agent_sum.get("name", ""),
                stakeholder_type=agent_sum.get("stakeholder_type", ""),
                actions=agent_sum.get("action_types", []),
            ))

        # トークン使用量を記録
        evaluation.token_usage = _extract_token_usage(output.summary)

        # 結果をRedisに保存
        result_data = {
            "scenario": scenario.model_dump(),
            "summary": output.summary,
            "rounds": [r.model_dump() for r in results],
            "report": output.report,
            "evaluation": evaluation.model_dump(),
            "research": research_data.model_dump(),
            "benchmark_id": benchmark_id,
        }
        if output.social_feed:
            result_data["social_feed"] = output.social_feed
        await job_manager.set_completed(job_id, result_data)

    except Exception as exc:
        logger.exception("シミュレーション失敗: benchmark=%s", benchmark_id)
        await job_manager.set_failed(job_id, str(exc))
        raise

    total_time = time.monotonic() - total_time_start

    if parent_job_id:
        await job_manager.update_progress(
            parent_job_id, 3, 3, phase=f"完了: {benchmark.name}",
        )

    logger.info(
        "一連ベンチマーク完了: %s — 方向精度=%.2f, 調査=%.1fs, 合計=%.1fs",
        benchmark.name, evaluation.direction_accuracy, research_time, total_time,
    )

    return FullBenchmarkResult(
        benchmark_id=benchmark_id,
        benchmark_name=benchmark.name,
        research=research_data,
        evaluation=evaluation,
        research_time_seconds=round(research_time, 2),
        total_time_seconds=round(total_time, 2),
    )


async def run_all_benchmarks(
    job_manager: JobManager,
    pass_threshold: float = 0.6,
    parent_job_id: str | None = None,
) -> EvaluationSuiteResult:
    """全ベンチマークを順次実行して総合評価を返す."""
    benchmarks = list_benchmarks()
    start_time = time.monotonic()
    total = len(benchmarks)

    results: list[EvaluationResult] = []
    for idx, benchmark in enumerate(benchmarks):
        if parent_job_id:
            await job_manager.update_progress(
                parent_job_id, idx + 1, total,
                phase=f"ベンチマーク {idx + 1}/{total}: {benchmark.name}",
            )
        try:
            result = await run_benchmark(benchmark.id, job_manager)
            results.append(result)
        except Exception:
            logger.exception("ベンチマーク '%s' をスキップ", benchmark.id)

    elapsed = time.monotonic() - start_time

    if not results:
        return EvaluationSuiteResult(
            results=[],
            mean_direction_accuracy=0.0,
            total_benchmarks=len(benchmarks),
            passed_benchmarks=0,
            pass_threshold=pass_threshold,
            execution_time_seconds=round(elapsed, 2),
        )

    mean_dir_acc = sum(r.direction_accuracy for r in results) / len(results)
    passed = sum(1 for r in results if r.direction_accuracy >= pass_threshold)

    # 成功/失敗予測の集計
    outcome_results = [r for r in results if r.outcome_correct is not None]
    outcome_correct_count = sum(1 for r in outcome_results if r.outcome_correct)
    outcome_evaluated_count = len(outcome_results)

    combined_accs = [r.combined_accuracy for r in results if r.combined_accuracy is not None]
    mean_combined = round(sum(combined_accs) / len(combined_accs), 4) if combined_accs else None

    return EvaluationSuiteResult(
        results=results,
        mean_direction_accuracy=round(mean_dir_acc, 4),
        total_benchmarks=len(benchmarks),
        passed_benchmarks=passed,
        pass_threshold=pass_threshold,
        execution_time_seconds=round(elapsed, 2),
        mean_combined_accuracy=mean_combined,
        outcome_correct_count=outcome_correct_count,
        outcome_evaluated_count=outcome_evaluated_count,
    )
