"""Tests for simulation API endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.simulation.models import MarketState, RoundResult


@pytest.fixture
def mock_engine_run():
    """Mock the simulation engine to avoid LLM calls."""
    results = [
        RoundResult(
            round_number=1,
            market_state=MarketState(round_number=1),
            actions_taken=[{"agent": "TestCo", "type": "recruit", "description": "テスト"}],
            events=[],
            summary="Round 1 complete",
        )
    ]
    with patch("app.api.routes.simulations.SimulationEngine") as mock_cls:
        instance = mock_cls.return_value
        instance.run = AsyncMock(return_value=results)
        instance.get_summary.return_value = {
            "total_rounds": 1,
            "final_market": MarketState(round_number=1).model_dump(),
            "agents": [],
            "llm_calls": 1,
        }
        yield instance


class TestSimulationAPI:
    @pytest.mark.asyncio
    async def test_run_simulation(self, mock_engine_run):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/simulations/", json={
                "description": "AI技術の普及によるIT人材市場の変化予測テスト",
                "num_rounds": 3,
                "focus_skills": ["ai_ml"],
            })

        assert response.status_code == 200
        data = response.json()
        assert "scenario" in data
        assert "summary" in data
        assert "rounds" in data

    @pytest.mark.asyncio
    async def test_invalid_scenario_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/simulations/", json={
                "description": "短い",  # Too short
            })

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_health_check(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
