"""予測 API エンドポイント."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.job_manager import JobManager, JobStatus
from app.core.redis_client import RedisClient
from app.prediction.comparator import compare_predictions
from app.prediction.trend import predict_from_results
from app.simulation.models import ServiceMarketState, RoundResult

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
            market_state=ServiceMarketState(**r["market_state"]),
            actions_taken=r.get("actions_taken", []),
            events=r.get("events", []),
        )
        for r in result.get("rounds", [])
    ]

    if not rounds:
        raise HTTPException(status_code=400, detail="シミュレーション結果が空です")

    prediction = predict_from_results(rounds)
    return prediction.model_dump()


def _extract_rounds(result: dict[str, Any]) -> list[RoundResult]:
    """結果データからRoundResultリストを構築する."""
    return [
        RoundResult(
            round_number=r["round_number"],
            market_state=ServiceMarketState(**r["market_state"]),
            actions_taken=r.get("actions_taken", []),
            events=r.get("events", []),
        )
        for r in result.get("rounds", [])
    ]


@router.get("/{job_id}/compare/{alt_job_id}")
async def compare_simulations(
    job_id: str,
    alt_job_id: str,
    base_label: str = "ベースシナリオ",
    alt_label: str = "代替シナリオ",
) -> dict[str, Any]:
    """2つのシミュレーション結果を比較する."""
    job_manager = _get_job_manager()

    # 両方のジョブを取得
    for jid, label in [(job_id, "ベース"), (alt_job_id, "代替")]:
        info = await job_manager.get_job_info(jid)
        if info is None:
            raise HTTPException(status_code=404, detail=f"{label}ジョブが見つかりません: {jid}")
        if info.status != JobStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=f"{label}シミュレーションが完了していません")

    base_result = await job_manager.get_result(job_id)
    alt_result = await job_manager.get_result(alt_job_id)
    if not base_result or not alt_result:
        raise HTTPException(status_code=404, detail="結果データが見つかりません")

    base_rounds = _extract_rounds(base_result)
    alt_rounds = _extract_rounds(alt_result)
    if not base_rounds or not alt_rounds:
        raise HTTPException(status_code=400, detail="シミュレーション結果が空です")

    base_prediction = predict_from_results(base_rounds)
    alt_prediction = predict_from_results(alt_rounds)

    return compare_predictions(base_prediction, alt_prediction, base_label, alt_label)
