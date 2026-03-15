"""ジョブ管理 — シミュレーションの非同期実行とステータス管理.

シミュレーションのライフサイクル:
  CREATED → (文書アップロード) → QUEUED → RUNNING → COMPLETED/FAILED
"""

from __future__ import annotations

import logging
import time
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
_KEY_SCENARIO = "job:{job_id}:scenario"
_KEY_INDEX = "jobs:index"  # Sorted Set (score=created_at timestamp)

# TTL: 結果は7日間保持
_RESULT_TTL = 86400 * 7


class JobStatus(str, Enum):
    """ジョブの状態."""
    CREATED = "created"    # 作成済み（文書アップロード待ち）
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
    scenario_description: str = ""


class JobManager:
    """Redis を使ったジョブ管理."""

    def __init__(self, redis: RedisClient):
        self.redis = redis

    async def create_job(self, scenario_description: str = "") -> str:
        """新しいジョブを作成し、ジョブIDを返す.

        ジョブはCREATED状態で作成される（文書アップロード待ち）。
        """
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await self.redis.set_json(
            _KEY_STATUS.format(job_id=job_id),
            {
                "job_id": job_id,
                "status": JobStatus.CREATED.value,
                "created_at": now,
                "error": None,
                "scenario_description": scenario_description[:200],
            },
            ttl=_RESULT_TTL,
        )
        # インデックスに追加
        try:
            client = await self.redis._ensure_connected()
            await client.zadd(_KEY_INDEX, {job_id: time.time()})
        except Exception:
            logger.warning("ジョブインデックス更新失敗: %s", job_id)

        logger.info("ジョブ作成: %s", job_id)
        return job_id

    async def save_scenario(self, job_id: str, scenario: dict[str, Any]) -> None:
        """シナリオ入力を保存する."""
        await self.redis.set_json(
            _KEY_SCENARIO.format(job_id=job_id), scenario, ttl=_RESULT_TTL,
        )

    async def get_scenario(self, job_id: str) -> dict[str, Any] | None:
        """保存されたシナリオ入力を取得する."""
        return await self.redis.get_json(_KEY_SCENARIO.format(job_id=job_id))

    async def set_queued(self, job_id: str) -> None:
        """ジョブをキュー済みに更新する（実行開始時）."""
        info = await self._get_status_raw(job_id)
        if info:
            info["status"] = JobStatus.QUEUED.value
            await self.redis.set_json(
                _KEY_STATUS.format(job_id=job_id), info, ttl=_RESULT_TTL
            )

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
        self, job_id: str, current_round: int, total_rounds: int,
        phase: str = "",
    ) -> None:
        """進捗を更新する."""
        await self.redis.set_json(
            _KEY_PROGRESS.format(job_id=job_id),
            {
                "current_round": current_round,
                "total_rounds": total_rounds,
                "percentage": round(current_round / total_rounds * 100, 1),
                "phase": phase,
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
            scenario_description=info.get("scenario_description", ""),
        )

    async def get_result(self, job_id: str) -> dict[str, Any] | None:
        """ジョブの結果を取得する."""
        return await self.redis.get_json(_KEY_RESULT.format(job_id=job_id))

    async def list_jobs(self, limit: int = 20) -> list[JobInfo]:
        """過去のジョブ一覧を取得する（新しい順）."""
        try:
            client = await self.redis._ensure_connected()
            job_ids = await client.zrevrange(_KEY_INDEX, 0, limit - 1)
        except Exception:
            logger.warning("ジョブ一覧取得失敗")
            return []

        jobs: list[JobInfo] = []
        for job_id_bytes in job_ids:
            job_id = job_id_bytes.decode() if isinstance(job_id_bytes, bytes) else job_id_bytes
            info = await self.get_job_info(job_id)
            if info:
                jobs.append(info)
        return jobs

    async def delete_job(self, job_id: str) -> bool:
        """ジョブとその関連データをRedisから削除する."""
        try:
            await self.redis.delete(_KEY_STATUS.format(job_id=job_id))
            await self.redis.delete(_KEY_RESULT.format(job_id=job_id))
            await self.redis.delete(_KEY_PROGRESS.format(job_id=job_id))
            await self.redis.delete(_KEY_SCENARIO.format(job_id=job_id))
            # インデックスから削除
            client = await self.redis._ensure_connected()
            await client.zrem(_KEY_INDEX, job_id)
            logger.info("ジョブ削除: %s", job_id)
            return True
        except Exception:
            logger.warning("ジョブ削除失敗: %s", job_id)
            return False

    async def _get_status_raw(self, job_id: str) -> dict[str, Any] | None:
        return await self.redis.get_json(_KEY_STATUS.format(job_id=job_id))
