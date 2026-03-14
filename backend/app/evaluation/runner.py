"""評価ランナー — ベンチマーク実行のオーケストレーション.

既存のシミュレーションインフラ（LLM, Neo4j, Redis）を使って
ベンチマークシナリオを実行し、結果を期待値と比較する。
"""

from __future__ import annotations

import logging
import time

from app.core.graph.agent_memory import AgentMemoryStore
from app.core.graph.client import GraphClient
from app.core.graph.rag import GraphRAGRetriever
from app.core.job_manager import JobManager
from app.core.llm.router import LLMRouter
from app.evaluation.benchmarks import get_benchmark, list_benchmarks
from app.evaluation.comparator import evaluate_benchmark
from app.evaluation.models import (
    BenchmarkScenario,
    EvaluationResult,
    EvaluationSuiteResult,
)
from app.simulation.agent_generator import AgentGenerator
from app.simulation.engine import SimulationEngine
from app.simulation.events.scheduler import EventScheduler
from app.simulation.models import RoundResult
from app.simulation.scenario_analyzer import ScenarioAnalyzer

logger = logging.getLogger(__name__)


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
        return None, None, None


async def run_simulation_for_benchmark(
    benchmark: BenchmarkScenario,
    job_id: str,
    job_manager: JobManager,
) -> list[RoundResult]:
    """ベンチマーク用にシミュレーションを実行し、結果を返す."""
    scenario = benchmark.scenario_input

    await job_manager.set_running(job_id)

    llm = LLMRouter()

    analyzer = ScenarioAnalyzer(llm=llm)
    enriched = await analyzer.analyze_async(scenario)

    rag, agent_memory, graph_client = await _setup_graph_components(job_id)

    try:
        generator = AgentGenerator(llm)
        agents = await generator.generate(scenario, enriched, None)

        event_scheduler = EventScheduler(llm=llm)
        await event_scheduler.generate_from_scenario(scenario)

        async def on_progress(current: int, total: int) -> None:
            await job_manager.update_progress(job_id, current, total)

        engine = SimulationEngine(
            agents=agents,
            llm=llm,
            scenario=scenario,
            on_progress=on_progress,
            event_scheduler=event_scheduler,
            enriched_scenario=enriched,
            rag=rag,
            agent_memory=agent_memory,
        )

        return await engine.run()
    finally:
        if graph_client:
            try:
                await graph_client.close()
            except Exception:
                pass


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
        results = await run_simulation_for_benchmark(benchmark, job_id, job_manager)
        elapsed = time.monotonic() - start_time

        evaluation = evaluate_benchmark(benchmark, results)
        evaluation.execution_time_seconds = round(elapsed, 2)

        # 結果をRedisに保存
        result_data = {
            "type": "evaluation",
            "benchmark_id": benchmark_id,
            "evaluation": evaluation.model_dump(),
            "rounds": [r.model_dump() for r in results],
        }
        await job_manager.set_completed(job_id, result_data)

        logger.info(
            "評価完了: %s — スコア=%.2f, 方向精度=%.2f, 実行時間=%.1fs",
            benchmark.name,
            evaluation.overall_score,
            evaluation.direction_accuracy,
            elapsed,
        )
        return evaluation

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        logger.exception("評価失敗: %s", benchmark.name)
        await job_manager.set_failed(job_id, str(exc))
        raise


async def run_all_benchmarks(
    job_manager: JobManager,
    pass_threshold: float = 0.5,
) -> EvaluationSuiteResult:
    """全ベンチマークを順次実行して総合評価を返す."""
    benchmarks = list_benchmarks()
    start_time = time.monotonic()

    results: list[EvaluationResult] = []
    for benchmark in benchmarks:
        try:
            result = await run_benchmark(benchmark.id, job_manager)
            results.append(result)
        except Exception:
            logger.exception("ベンチマーク '%s' をスキップ", benchmark.id)

    elapsed = time.monotonic() - start_time

    if not results:
        return EvaluationSuiteResult(
            results=[],
            mean_overall_score=0.0,
            mean_direction_accuracy=0.0,
            total_benchmarks=len(benchmarks),
            passed_benchmarks=0,
            pass_threshold=pass_threshold,
            execution_time_seconds=round(elapsed, 2),
        )

    mean_score = sum(r.overall_score for r in results) / len(results)
    mean_dir_acc = sum(r.direction_accuracy for r in results) / len(results)
    passed = sum(1 for r in results if r.overall_score >= pass_threshold)

    return EvaluationSuiteResult(
        results=results,
        mean_overall_score=round(mean_score, 4),
        mean_direction_accuracy=round(mean_dir_acc, 4),
        total_benchmarks=len(benchmarks),
        passed_benchmarks=passed,
        pass_threshold=pass_threshold,
        execution_time_seconds=round(elapsed, 2),
    )
