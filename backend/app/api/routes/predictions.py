"""予測 API エンドポイント."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.job_manager import JobManager, JobStatus
from app.core.redis_client import RedisClient
from app.prediction.trend import predict_from_results
from app.simulation.models import MarketState, RoundResult

router = APIRouter(prefix="/api/simulations", tags=["predictions"])

_redis: RedisClient | None = None
_job_manager: JobManager | None = None


def _get_job_manager() -> JobManager:
    global _redis, _job_manager
    if _job_manager is None:
        _redis = RedisClient()
        _job_manager = JobManager(_redis)
    return _job_manager


@router.get("/{job_id}/prediction")
async def get_prediction(job_id: str) -> dict[str, Any]:
    """シミュレーション結果に基づく定量予測を返す."""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)

    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    if info.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"シミュレーションが完了していません（現在: {info.status.value}）",
        )

    result = await job_manager.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="結果データが見つかりません")

    rounds = [
        RoundResult(
            round_number=r["round_number"],
            market_state=MarketState(**r["market_state"]),
            actions_taken=r.get("actions_taken", []),
            events=r.get("events", []),
        )
        for r in result.get("rounds", [])
    ]

    if not rounds:
        raise HTTPException(status_code=400, detail="シミュレーション結果が空です")

    prediction = predict_from_results(rounds)
    return prediction.model_dump()
