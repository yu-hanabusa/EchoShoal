"""API エンドポイントのユニットテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.job_manager import JobInfo, JobManager, JobStatus
from app.main import app


def make_mock_job_manager() -> MagicMock:
    mock = MagicMock(spec=JobManager)
    mock.create_job = AsyncMock(return_value="test-job-id")
    mock.get_job_info = AsyncMock()
    mock.get_result = AsyncMock()
    return mock


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestCreateSimulation:
    @pytest.mark.asyncio
    async def test_returns_202_with_job_id(self):
        mock_jm = make_mock_job_manager()
        with patch("app.api.routes.simulations._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/simulations/", data={
                    "description": "AI技術の普及によるIT人材市場の変化予測テスト",
                })
            assert response.status_code == 202
            data = response.json()
            assert data["job_id"] == "test-job-id"
            assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_invalid_scenario_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/simulations/", json={
                "description": "短い",
            })
        assert response.status_code == 422


class TestGetSimulation:
    @pytest.mark.asyncio
    async def test_returns_404_for_missing_job(self):
        mock_jm = make_mock_job_manager()
        mock_jm.get_job_info = AsyncMock(return_value=None)
        with patch("app.api.routes.simulations._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/simulations/nonexistent")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_running_status(self):
        mock_jm = make_mock_job_manager()
        mock_jm.get_job_info = AsyncMock(return_value=JobInfo(
            job_id="test-id",
            status=JobStatus.RUNNING,
            created_at="2026-01-01",
            progress={"current_round": 5, "total_rounds": 24},
        ))
        with patch("app.api.routes.simulations._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/simulations/test-id")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["progress"]["current_round"] == 5

    @pytest.mark.asyncio
    async def test_returns_completed_with_result(self):
        mock_jm = make_mock_job_manager()
        mock_jm.get_job_info = AsyncMock(return_value=JobInfo(
            job_id="test-id",
            status=JobStatus.COMPLETED,
            created_at="2026-01-01",
        ))
        mock_jm.get_result = AsyncMock(return_value={
            "summary": {"total_rounds": 10},
            "rounds": [],
        })
        with patch("app.api.routes.simulations._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/simulations/test-id")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert "result" in data


class TestGetProgress:
    @pytest.mark.asyncio
    async def test_returns_progress(self):
        mock_jm = make_mock_job_manager()
        mock_jm.get_job_info = AsyncMock(return_value=JobInfo(
            job_id="test-id",
            status=JobStatus.RUNNING,
            created_at="2026-01-01",
            progress={"current_round": 12, "total_rounds": 24, "percentage": 50.0},
        ))
        with patch("app.api.routes.simulations._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/simulations/test-id/progress")
            assert response.status_code == 200
            data = response.json()
            assert data["progress"]["percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_returns_404_for_missing(self):
        mock_jm = make_mock_job_manager()
        mock_jm.get_job_info = AsyncMock(return_value=None)
        with patch("app.api.routes.simulations._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/simulations/nonexistent/progress")
            assert response.status_code == 404
