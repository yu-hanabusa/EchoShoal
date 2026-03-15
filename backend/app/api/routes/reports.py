"""レポート API エンドポイント."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from app.core.job_manager import JobManager, JobStatus
from app.core.llm.router import LLMRouter
from app.core.redis_client import RedisClient
from app.reports.extractor import build_report_data
from app.reports.generator import ReportGenerator
from app.simulation.models import ServiceMarketState, RoundResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["reports"])

_redis: RedisClient | None = None
_job_manager: JobManager | None = None

REPORT_CACHE_PREFIX = "report:"
REPORT_CACHE_TTL = 60 * 60 * 24 * 7  # 7日間


def _get_job_manager() -> JobManager:
    global _redis, _job_manager
    if _job_manager is None:
        _redis = RedisClient()
        _job_manager = JobManager(_redis)
    return _job_manager


def _get_redis() -> RedisClient:
    global _redis
    if _redis is None:
        _redis = RedisClient()
    return _redis


@router.get("/{job_id}/report")
async def get_report(job_id: str, format: str = "json") -> Any:
    """シミュレーション結果のレポートを返す。生成済みならキャッシュから返す。"""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)

    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    if info.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"シミュレーションが完了していません（現在: {info.status.value}）",
        )

    # キャッシュ確認
    redis = _get_redis()
    cache_key = f"{REPORT_CACHE_PREFIX}{job_id}"
    cached = await redis.get(cache_key)
    if cached:
        logger.info("レポートキャッシュヒット: %s", job_id)
        report_data = json.loads(cached)
        if format == "markdown":
            from app.reports.models import SimulationReport
            report = SimulationReport(**report_data)
            return PlainTextResponse(
                content=report.to_markdown(),
                media_type="text/markdown",
            )
        return report_data

    # キャッシュなし → 生成
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

    report_input = build_report_data(
        rounds=rounds,
        scenario_description=result.get("scenario", {}).get("description", ""),
        agents_summary=result.get("summary", {}).get("agents", []),
    )

    llm = LLMRouter()
    generator = ReportGenerator(llm=llm)
    report = await generator.generate(report_input)

    # キャッシュに保存
    report_dict = report.model_dump()
    try:
        await redis.set(cache_key, json.dumps(report_dict, ensure_ascii=False), ex=REPORT_CACHE_TTL)
        logger.info("レポートキャッシュ保存: %s", job_id)
    except Exception:
        logger.warning("レポートキャッシュ保存失敗: %s", job_id)

    if format == "markdown":
        return PlainTextResponse(
            content=report.to_markdown(),
            media_type="text/markdown",
        )

    return report_dict
