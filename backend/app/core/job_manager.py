"""ジョブ管理 — シミュレーションの非同期実行とステータス管理."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.core.redis_client import RedisClient

logger = logging.getLogger(__name__)

# Redis キー設計
_KEY_STATUS = "job:{job_id}:status"
_KEY_RESULT = "job:{job_id}:result"
_KEY_PROGRESS = "job:{job_id}:progress"

# TTL: 結果は24時間保持
_RESULT_TTL = 86400


class JobStatus(str, Enum):
    """ジョブの状態."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobInfo(BaseModel):
    """ジョブの状態情報."""
    job_id: str
    status: JobStatus
    created_at: str
    progress: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class JobManager:
    """Redis を使ったジョブ管理."""

    def __init__(self, redis: RedisClient):
        self.redis = redis

    async def create_job(self) -> str:
        """新しいジョブを作成し、ジョブIDを返す."""
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await self.redis.set_json(
            _KEY_STATUS.format(job_id=job_id),
            {
                "job_id": job_id,
                "status": JobStatus.QUEUED.value,
                "created_at": now,
                "error": None,
            },
            ttl=_RESULT_TTL,
        )
        logger.info("ジョブ作成: %s", job_id)
        return job_id

    async def set_running(self, job_id: str) -> None:
        """ジョブを実行中に更新する."""
        info = await self._get_status_raw(job_id)
        if info:
            info["status"] = JobStatus.RUNNING.value
            await self.redis.set_json(
                _KEY_STATUS.format(job_id=job_id), info, ttl=_RESULT_TTL
            )

    async def set_completed(self, job_id: str, result: dict[str, Any]) -> None:
        """ジョブを完了に更新し、結果を保存する."""
        info = await self._get_status_raw(job_id)
        if info:
            info["status"] = JobStatus.COMPLETED.value
            await self.redis.set_json(
                _KEY_STATUS.format(job_id=job_id), info, ttl=_RESULT_TTL
            )
        await self.redis.set_json(
            _KEY_RESULT.format(job_id=job_id), result, ttl=_RESULT_TTL
        )
        logger.info("ジョブ完了: %s", job_id)

    async def set_failed(self, job_id: str, error: str) -> None:
        """ジョブを失敗に更新する."""
        info = await self._get_status_raw(job_id)
        if info:
            info["status"] = JobStatus.FAILED.value
            info["error"] = error
            await self.redis.set_json(
                _KEY_STATUS.format(job_id=job_id), info, ttl=_RESULT_TTL
            )
        logger.error("ジョブ失敗: %s - %s", job_id, error)

    async def update_progress(
        self, job_id: str, current_round: int, total_rounds: int
    ) -> None:
        """進捗を更新する."""
        await self.redis.set_json(
            _KEY_PROGRESS.format(job_id=job_id),
            {
                "current_round": current_round,
                "total_rounds": total_rounds,
                "percentage": round(current_round / total_rounds * 100, 1),
            },
            ttl=_RESULT_TTL,
        )

    async def get_job_info(self, job_id: str) -> JobInfo | None:
        """ジョブ情報を取得する."""
        info = await self._get_status_raw(job_id)
        if info is None:
            return None
        progress = await self.redis.get_json(
            _KEY_PROGRESS.format(job_id=job_id)
        ) or {}
        return JobInfo(
            job_id=info["job_id"],
            status=JobStatus(info["status"]),
            created_at=info["created_at"],
            progress=progress,
            error=info.get("error"),
        )

    async def get_result(self, job_id: str) -> dict[str, Any] | None:
        """ジョブの結果を取得する."""
        return await self.redis.get_json(_KEY_RESULT.format(job_id=job_id))

    async def _get_status_raw(self, job_id: str) -> dict[str, Any] | None:
        return await self.redis.get_json(_KEY_STATUS.format(job_id=job_id))
