"""評価 API エンドポイント — ベンチマーク一覧・実行・結果取得."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.job_manager import JobManager, JobStatus
from app.core.redis_client import RedisClient
from app.evaluation.benchmarks import get_benchmark, list_benchmarks
from app.evaluation.runner import (
    run_all_benchmarks,
    run_benchmark,
    run_benchmark_multi,
    run_benchmark_with_research,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])

_redis: RedisClient | None = None
_job_manager: JobManager | None = None


def _get_job_manager() -> JobManager:
    global _redis, _job_manager
    if _job_manager is None:
        _redis = RedisClient()
        _job_manager = JobManager(_redis)
    return _job_manager


# ─── ベンチマーク一覧 ───


@router.get("/benchmarks")
async def get_benchmarks() -> list[dict[str, Any]]:
    """利用可能なベンチマークシナリオの一覧を返す."""
    benchmarks = list_benchmarks()
    return [
        {
            "id": b.id,
            "name": b.name,
            "description": b.description,
            "tags": b.tags,
            "expected_trend_count": len(b.expected_trends),
            "num_rounds": b.scenario_input.num_rounds,
            "reference_url": b.reference_url,
            "reference_description": b.reference_description,
        }
        for b in benchmarks
    ]


# ─── 単一ベンチマーク実行 ───


@router.post("/run/{benchmark_id}")
async def run_single_benchmark(benchmark_id: str) -> JSONResponse:
    """指定ベンチマークを実行して評価する.

    バックグラウンドタスクとして実行し、ジョブIDを返す。
    結果は GET /api/evaluation/{job_id}/result で取得可能。
    """
    benchmark = get_benchmark(benchmark_id)
    if benchmark is None:
        raise HTTPException(
            status_code=404,
            detail=f"ベンチマーク '{benchmark_id}' が見つかりません",
        )

    job_manager = _get_job_manager()
    job_id = await job_manager.create_job(
        scenario_description=f"[評価] {benchmark.name}",
    )

    async def _task() -> None:
        try:
            await job_manager.set_running(job_id)
            result = await run_benchmark(benchmark_id, job_manager)
            await job_manager.set_completed(job_id, {
                "type": "evaluation_single",
                "benchmark_id": benchmark_id,
                "evaluation": result.model_dump(),
            })
        except Exception as exc:
            logger.exception("ベンチマーク実行失敗: %s", benchmark_id)
            await job_manager.set_failed(job_id, str(exc))

    asyncio.create_task(_task())

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "queued",
            "benchmark_id": benchmark_id,
            "benchmark_name": benchmark.name,
        },
    )


# ─── 単一ベンチマーク複数回実行（統計評価） ───


@router.post("/run/{benchmark_id}/multi")
async def run_benchmark_statistical(
    benchmark_id: str,
    num_runs: int = Query(default=5, ge=2, le=20),
) -> JSONResponse:
    """指定ベンチマークを複数回実行して統計的に評価する.

    LLMの非決定性を考慮し、方向一致の再現性を統計的に評価する。
    """
    benchmark = get_benchmark(benchmark_id)
    if benchmark is None:
        raise HTTPException(
            status_code=404,
            detail=f"ベンチマーク '{benchmark_id}' が見つかりません",
        )

    job_manager = _get_job_manager()
    job_id = await job_manager.create_job(
        scenario_description=f"[統計評価] {benchmark.name} x{num_runs}回",
    )

    async def _task() -> None:
        try:
            await job_manager.set_running(job_id)
            stats = await run_benchmark_multi(
                benchmark_id, job_manager, num_runs, parent_job_id=job_id,
            )
            await job_manager.set_completed(job_id, {
                "type": "evaluation_multi",
                "benchmark_id": benchmark_id,
                "num_runs": num_runs,
                "statistics": stats.model_dump(),
            })
        except Exception as exc:
            logger.exception("統計評価失敗: %s", benchmark_id)
            await job_manager.set_failed(job_id, str(exc))

    asyncio.create_task(_task())

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "queued",
            "benchmark_id": benchmark_id,
            "benchmark_name": benchmark.name,
            "num_runs": num_runs,
        },
    )


# ─── 市場調査 + シミュレーション + 評価（一連ベンチマーク） ───


@router.post("/run/{benchmark_id}/full")
async def run_full_benchmark(benchmark_id: str) -> JSONResponse:
    """市場調査 → シミュレーション → 評価の一連フローを実行する.

    1. 市場調査パイプラインでデータ収集 + 3レポート生成
    2. 調査結果をドキュメントとしてシミュレーションに渡す
    3. シミュレーション実行 + 期待トレンド比較
    """
    benchmark = get_benchmark(benchmark_id)
    if benchmark is None:
        raise HTTPException(
            status_code=404,
            detail=f"ベンチマーク '{benchmark_id}' が見つかりません",
        )

    job_manager = _get_job_manager()
    job_id = await job_manager.create_job(
        scenario_description=f"[市場調査+評価] {benchmark.name}",
    )

    async def _task() -> None:
        try:
            await job_manager.set_running(job_id)
            result = await run_benchmark_with_research(
                benchmark_id, job_manager, parent_job_id=job_id,
            )
            await job_manager.set_completed(job_id, {
                "type": "evaluation_full",
                "benchmark_id": benchmark_id,
                "full_result": result.model_dump(),
            })
        except Exception as exc:
            logger.exception("一連ベンチマーク実行失敗: %s", benchmark_id)
            await job_manager.set_failed(job_id, str(exc))

    asyncio.create_task(_task())

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "queued",
            "benchmark_id": benchmark_id,
            "benchmark_name": benchmark.name,
            "type": "full",
        },
    )


# ─── 全ベンチマーク実行 ───


@router.post("/run-all")
async def run_all() -> JSONResponse:
    """全ベンチマークを順次実行して総合評価する.

    各ベンチマークはシミュレーションを完全に実行するため、
    完了まで相応の時間がかかる。
    """
    job_manager = _get_job_manager()
    benchmarks = list_benchmarks()
    job_id = await job_manager.create_job(
        scenario_description=f"[全ベンチマーク評価] {len(benchmarks)}件",
    )

    async def _task() -> None:
        try:
            await job_manager.set_running(job_id)
            suite_result = await run_all_benchmarks(
                job_manager, parent_job_id=job_id,
            )
            await job_manager.set_completed(job_id, {
                "type": "evaluation_suite",
                "suite": suite_result.model_dump(),
            })
        except Exception as exc:
            logger.exception("全ベンチマーク実行失敗")
            await job_manager.set_failed(job_id, str(exc))

    asyncio.create_task(_task())

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "queued",
            "benchmark_count": len(benchmarks),
        },
    )


# ─── 結果取得 ───


@router.get("/{job_id}/result")
async def get_evaluation_result(job_id: str) -> dict[str, Any]:
    """評価ジョブの結果を取得する."""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    response: dict[str, Any] = {
        "job_id": job_id,
        "status": info.status.value,
    }

    if info.status == JobStatus.COMPLETED:
        result = await job_manager.get_result(job_id)
        if result:
            response["result"] = result
    elif info.status == JobStatus.FAILED:
        response["error"] = info.error
    elif info.status in (JobStatus.RUNNING, JobStatus.QUEUED):
        response["progress"] = info.progress

    return response
