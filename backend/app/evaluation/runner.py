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
    RunStatistics,
)
from app.simulation.agent_generator import AgentGenerator
from app.simulation.engine import SimulationEngine
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
        agents = await generator.generate(scenario, enriched, doc_entities)

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

        # OASISエンジンを使用（通常シミュレーションと同じ）
        from app.config import settings
        use_oasis = settings.simulation_engine == "oasis"
        oasis_engine = None
        social_feed = None

        if use_oasis:
            try:
                from app.oasis.simulation_runner import OASISSimulationEngine
                oasis_engine = OASISSimulationEngine(
                    agents=agents, llm=llm, scenario=scenario,
                    on_progress=on_progress, event_scheduler=event_scheduler,
                    enriched_scenario=enriched, simulation_id=job_id,
                    rag=rag, agent_memory=agent_memory,
                )
                engine = oasis_engine
            except Exception:
                logger.warning("OASISエンジン初期化失敗、legacyにフォールバック")
                engine = SimulationEngine(
                    agents=agents, llm=llm, scenario=scenario,
                    on_progress=on_progress, event_scheduler=event_scheduler,
                    enriched_scenario=enriched, rag=rag, agent_memory=agent_memory,
                )
        else:
            engine = SimulationEngine(
                agents=agents, llm=llm, scenario=scenario,
                on_progress=on_progress, event_scheduler=event_scheduler,
                enriched_scenario=enriched, rag=rag, agent_memory=agent_memory,
            )

        rounds = await engine.run()
        summary = engine.get_summary()

        # OASISソーシャルフィード取得 + グラフ同期
        if oasis_engine is not None:
            try:
                social_feed = oasis_engine.get_social_feed(limit=50)
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

        evaluation = evaluate_benchmark(benchmark, results)
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

    return RunStatistics(
        num_runs=num_runs,
        per_run_results=per_run_results,
        mean_direction_accuracy=round(mean_acc, 4),
        stddev_direction_accuracy=round(stddev_acc, 4),
        min_direction_accuracy=round(min(accuracies), 4),
        max_direction_accuracy=round(max(accuracies), 4),
        per_trend_hit_rates=per_trend_hit_rates,
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

    return EvaluationSuiteResult(
        results=results,
        mean_direction_accuracy=round(mean_dir_acc, 4),
        total_benchmarks=len(benchmarks),
        passed_benchmarks=passed,
        pass_threshold=pass_threshold,
        execution_time_seconds=round(elapsed, 2),
    )
