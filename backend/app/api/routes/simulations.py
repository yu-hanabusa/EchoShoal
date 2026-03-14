"""シミュレーション API エンドポイント — 非同期ジョブ方式."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.job_manager import JobManager, JobStatus
from app.core.llm.router import LLMRouter
from app.core.redis_client import RedisClient
from app.simulation.engine import SimulationEngine
from app.simulation.events.scheduler import EventScheduler
from app.simulation.factory import create_default_agents
from app.simulation.models import ScenarioInput
from app.simulation.scenario_analyzer import ScenarioAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

# アプリケーションレベルの Redis / JobManager インスタンス
_redis: RedisClient | None = None
_job_manager: JobManager | None = None

# レートリミット用（インメモリ）
_active_simulations: int = 0
_request_timestamps: deque[float] = deque()


def _get_job_manager() -> JobManager:
    """JobManager のシングルトンを取得."""
    global _redis, _job_manager
    if _job_manager is None:
        _redis = RedisClient()
        _job_manager = JobManager(_redis)
    return _job_manager


def _check_rate_limit() -> None:
    """レートリミットをチェック。超過時はHTTPExceptionを投げる."""
    global _active_simulations
    now = time.monotonic()

    # 古いタイムスタンプを削除（60秒以上前）
    while _request_timestamps and now - _request_timestamps[0] > 60:
        _request_timestamps.popleft()

    if _active_simulations >= settings.max_concurrent_simulations:
        raise HTTPException(
            status_code=429,
            detail=f"同時実行上限（{settings.max_concurrent_simulations}件）に達しています",
        )

    if len(_request_timestamps) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"リクエスト上限（{settings.rate_limit_per_minute}件/分）に達しています",
        )

    _request_timestamps.append(now)


async def _run_simulation_task(
    job_id: str, scenario: ScenarioInput, job_manager: JobManager
) -> None:
    """バックグラウンドでシミュレーションを実行する."""
    global _active_simulations
    try:
        await job_manager.set_running(job_id)

        llm = LLMRouter()
        agents = create_default_agents(llm)

        # シナリオ解析（NLPでスキル・業界を自動検出）
        analyzer = ScenarioAnalyzer()
        enriched = analyzer.analyze(scenario)
        logger.info(
            "シナリオ解析: スキル%d件, 業界%d件検出",
            len(enriched.detected_skills), len(enriched.detected_industries),
        )

        # イベントスケジュール生成
        event_scheduler = EventScheduler(llm=llm)
        await event_scheduler.generate_from_scenario(scenario)

        async def on_progress(current: int, total: int) -> None:
            await job_manager.update_progress(job_id, current, total)

        engine = SimulationEngine(
            agents=agents, llm=llm, scenario=scenario,
            on_progress=on_progress, event_scheduler=event_scheduler,
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
    finally:
        _active_simulations -= 1


@router.post("/")
async def create_simulation(scenario: ScenarioInput) -> JSONResponse:
    """シミュレーションジョブを作成し、バックグラウンドで実行を開始する.

    Returns 202 Accepted with job_id.
    """
    global _active_simulations
    _check_rate_limit()

    job_manager = _get_job_manager()
    job_id = await job_manager.create_job()

    _active_simulations += 1
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
