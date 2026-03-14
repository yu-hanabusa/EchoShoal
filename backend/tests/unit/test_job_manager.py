"""ジョブマネージャのユニットテスト（Redis モック使用）."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.job_manager import JobInfo, JobManager, JobStatus
from app.core.redis_client import RedisClient


def make_mock_redis() -> MagicMock:
    """RedisClient のモックを作成."""
    mock = MagicMock(spec=RedisClient)
    mock.get_json = AsyncMock(return_value=None)
    mock.set_json = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock()
    return mock


class TestJobManager:
    @pytest.mark.asyncio
    async def test_create_job_returns_uuid(self):
        redis = make_mock_redis()
        manager = JobManager(redis)
        job_id = await manager.create_job()
        assert len(job_id) == 36  # UUID format
        redis.set_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_sets_created_status(self):
        redis = make_mock_redis()
        manager = JobManager(redis)
        await manager.create_job()

        call_args = redis.set_json.call_args[0]
        data = call_args[1]
        assert data["status"] == "created"

    @pytest.mark.asyncio
    async def test_set_running(self):
        redis = make_mock_redis()
        redis.get_json = AsyncMock(return_value={
            "job_id": "test-id",
            "status": "queued",
            "created_at": "2026-01-01",
            "error": None,
        })
        manager = JobManager(redis)
        await manager.set_running("test-id")

        call_args = redis.set_json.call_args[0]
        assert call_args[1]["status"] == "running"

    @pytest.mark.asyncio
    async def test_set_completed_saves_result(self):
        redis = make_mock_redis()
        redis.get_json = AsyncMock(return_value={
            "job_id": "test-id",
            "status": "running",
            "created_at": "2026-01-01",
            "error": None,
        })
        manager = JobManager(redis)
        result = {"summary": {"total_rounds": 5}}
        await manager.set_completed("test-id", result)

        # set_json は2回呼ばれる（ステータス更新 + 結果保存）
        assert redis.set_json.call_count == 2

    @pytest.mark.asyncio
    async def test_set_failed_stores_error(self):
        redis = make_mock_redis()
        redis.get_json = AsyncMock(return_value={
            "job_id": "test-id",
            "status": "running",
            "created_at": "2026-01-01",
            "error": None,
        })
        manager = JobManager(redis)
        await manager.set_failed("test-id", "LLM呼び出し失敗")

        call_args = redis.set_json.call_args[0]
        assert call_args[1]["status"] == "failed"
        assert call_args[1]["error"] == "LLM呼び出し失敗"

    @pytest.mark.asyncio
    async def test_update_progress(self):
        redis = make_mock_redis()
        manager = JobManager(redis)
        await manager.update_progress("test-id", 5, 24)

        call_args = redis.set_json.call_args[0]
        data = call_args[1]
        assert data["current_round"] == 5
        assert data["total_rounds"] == 24
        assert data["percentage"] == pytest.approx(20.8, abs=0.1)

    @pytest.mark.asyncio
    async def test_get_job_info_returns_none_for_missing(self):
        redis = make_mock_redis()
        manager = JobManager(redis)
        info = await manager.get_job_info("nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_get_job_info_returns_job_info(self):
        redis = make_mock_redis()

        async def mock_get_json(key):
            if "status" in key:
                return {
                    "job_id": "test-id",
                    "status": "running",
                    "created_at": "2026-01-01",
                    "error": None,
                }
            if "progress" in key:
                return {"current_round": 3, "total_rounds": 10, "percentage": 30.0}
            return None

        redis.get_json = AsyncMock(side_effect=mock_get_json)
        manager = JobManager(redis)
        info = await manager.get_job_info("test-id")

        assert info is not None
        assert info.status == JobStatus.RUNNING
        assert info.progress["current_round"] == 3

    @pytest.mark.asyncio
    async def test_get_result(self):
        redis = make_mock_redis()
        redis.get_json = AsyncMock(return_value={"summary": {"total_rounds": 5}})
        manager = JobManager(redis)
        result = await manager.get_result("test-id")
        assert result is not None
        assert result["summary"]["total_rounds"] == 5

    @pytest.mark.asyncio
    async def test_get_result_returns_none_for_missing(self):
        redis = make_mock_redis()
        manager = JobManager(redis)
        result = await manager.get_result("nonexistent")
        assert result is None


class TestJobStatus:
    def test_status_values(self):
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"


class TestJobInfo:
    def test_model(self):
        info = JobInfo(
            job_id="test",
            status=JobStatus.COMPLETED,
            created_at="2026-01-01",
            progress={"current_round": 10, "total_rounds": 10},
        )
        assert info.job_id == "test"
        assert info.error is None
