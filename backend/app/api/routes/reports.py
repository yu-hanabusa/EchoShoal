"""レポート API エンドポイント."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from app.core.job_manager import JobManager, JobStatus
from app.core.llm.router import LLMRouter
from app.core.redis_client import RedisClient
from app.reports.extractor import build_report_data
from app.reports.generator import ReportGenerator
from app.simulation.models import MarketState, RoundResult

router = APIRouter(prefix="/api/simulations", tags=["reports"])

_redis: RedisClient | None = None
_job_manager: JobManager | None = None


def _get_job_manager() -> JobManager:
    global _redis, _job_manager
    if _job_manager is None:
        _redis = RedisClient()
        _job_manager = JobManager(_redis)
    return _job_manager


@router.get("/{job_id}/report")
async def get_report(job_id: str, format: str = "json") -> Any:
    """シミュレーション結果のレポートを生成して返す.

    Args:
        job_id: シミュレーションジョブID
        format: 出力形式（"json" または "markdown"）
    """
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

    # 結果からRoundResultを復元
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

    # レポートデータ抽出
    report_data = build_report_data(
        rounds=rounds,
        scenario_description=result.get("scenario", {}).get("description", ""),
        agents_summary=result.get("summary", {}).get("agents", []),
    )

    # レポート生成
    llm = LLMRouter()
    generator = ReportGenerator(llm=llm)
    report = await generator.generate(report_data)

    if format == "markdown":
        return PlainTextResponse(
            content=report.to_markdown(),
            media_type="text/markdown",
        )

    return report.model_dump()
