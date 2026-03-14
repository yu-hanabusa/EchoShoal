"""Simulation API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.llm.router import LLMRouter
from app.simulation.engine import SimulationEngine
from app.simulation.factory import create_default_agents
from app.simulation.models import ScenarioInput

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


@router.post("/", response_model=dict[str, Any])
async def run_simulation(scenario: ScenarioInput) -> dict[str, Any]:
    """Run a market simulation based on the given scenario.

    Returns simulation results including per-round market states and agent actions.
    """
    llm = LLMRouter()
    agents = create_default_agents(llm)
    engine = SimulationEngine(agents=agents, llm=llm, scenario=scenario)

    try:
        results = await engine.run()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}") from exc

    return {
        "scenario": scenario.model_dump(),
        "summary": engine.get_summary(),
        "rounds": [r.model_dump() for r in results],
    }
