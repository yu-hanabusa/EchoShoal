"""シミュレーション API エンドポイント — 非同期ジョブ方式."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.core.job_manager import JobManager, JobStatus
from app.core.llm.router import LLMRouter
from app.core.redis_client import RedisClient
from app.simulation.engine import SimulationEngine
from app.simulation.factory import create_default_agents
from app.simulation.models import ScenarioInput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

# アプリケーションレベルの Redis / JobManager インスタンス
_redis: RedisClient | None = None
_job_manager: JobManager | None = None


def _get_job_manager() -> JobManager:
    """JobManager のシングルトンを取得."""
    global _redis, _job_manager
    if _job_manager is None:
        _redis = RedisClient()
        _job_manager = JobManager(_redis)
    return _job_manager


async def _run_simulation_task(
    job_id: str, scenario: ScenarioInput, job_manager: JobManager
) -> None:
    """バックグラウンドでシミュレーションを実行する."""
    try:
        await job_manager.set_running(job_id)

        llm = LLMRouter()
        agents = create_default_agents(llm)

        async def on_progress(current: int, total: int) -> None:
            await job_manager.update_progress(job_id, current, total)

        engine = SimulationEngine(
            agents=agents, llm=llm, scenario=scenario, on_progress=on_progress
        )

        results = await engine.run()

        result_data = {
            "scenario": scenario.model_dump(),
            "summary": engine.get_summary(),
            "rounds": [r.model_dump() for r in results],
        }
        await job_manager.set_completed(job_id, result_data)

    except Exception as exc:
        logger.exception("シミュレーション失敗: job=%s", job_id)
        await job_manager.set_failed(job_id, str(exc))


@router.post("/")
async def create_simulation(scenario: ScenarioInput) -> JSONResponse:
    """シミュレーションジョブを作成し、バックグラウンドで実行を開始する.

    Returns 202 Accepted with job_id.
    """
    job_manager = _get_job_manager()
    job_id = await job_manager.create_job()

    # バックグラウンドタスクとして起動
    asyncio.create_task(_run_simulation_task(job_id, scenario, job_manager))

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "queued"},
    )


@router.get("/{job_id}")
async def get_simulation(job_id: str) -> dict[str, Any]:
    """ジョブのステータスと結果を取得する.

    - queued/running: ステータス情報のみ
    - completed: ステータス + 結果
    - failed: ステータス + エラー詳細
    """
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)

    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    response: dict[str, Any] = info.model_dump()

    if info.status == JobStatus.COMPLETED:
        result = await job_manager.get_result(job_id)
        if result:
            response["result"] = result

    return response


@router.get("/{job_id}/progress")
async def get_simulation_progress(job_id: str) -> dict[str, Any]:
    """シミュレーションの進捗を取得する."""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)

    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    return {
        "job_id": job_id,
        "status": info.status.value,
        "progress": info.progress,
    }
