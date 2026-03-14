"""Simulation engine - orchestrates agent-based market simulation."""

from __future__ import annotations

import logging
import random
from collections.abc import Callable, Coroutine
from typing import Any

from app.config import settings
from app.core.llm.router import LLMRouter
from app.simulation.agents.base import BaseAgent
from app.simulation.models import (
    MarketState,
    RoundResult,
    ScenarioInput,
    SkillCategory,
)

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Orchestrates the agent-based simulation of the IT labor market.

    Each round:
    1. Activate a subset of agents
    2. Each active agent observes market and decides actions (via LLM)
    3. Actions are applied to agent states
    4. Market state is updated based on aggregate agent actions
    5. Round result is recorded
    """

    # コールバック型: async def callback(current_round, total_rounds) -> None
    ProgressCallback = Callable[[int, int], Coroutine[Any, Any, None]]

    def __init__(
        self,
        agents: list[BaseAgent],
        llm: LLMRouter,
        scenario: ScenarioInput | None = None,
        on_progress: ProgressCallback | None = None,
    ):
        self.agents = agents
        self.llm = llm
        self.scenario = scenario
        self.market = MarketState()
        self.results: list[RoundResult] = []
        self._llm_call_count = 0
        self._on_progress = on_progress

    async def run(self, num_rounds: int | None = None) -> list[RoundResult]:
        """Run the full simulation."""
        rounds = num_rounds or (self.scenario.num_rounds if self.scenario else settings.default_rounds)
        rounds = min(rounds, settings.max_rounds)

        logger.info("Starting simulation: %d rounds, %d agents", rounds, len(self.agents))

        for round_num in range(1, rounds + 1):
            if self._llm_call_count >= settings.max_llm_calls:
                logger.warning("LLM call limit reached at round %d", round_num)
                break

            result = await self._run_round(round_num)
            self.results.append(result)

            if self._on_progress:
                await self._on_progress(round_num, rounds)

        return self.results

    async def _run_round(self, round_number: int) -> RoundResult:
        """Execute a single simulation round."""
        self.market.round_number = round_number
        all_actions: list[dict[str, Any]] = []
        events: list[str] = []

        # Activate subset of agents
        active_agents = self._select_active_agents()
        logger.info("Round %d: %d/%d agents active", round_number, len(active_agents), len(self.agents))

        # Each agent decides and applies actions
        for agent in active_agents:
            try:
                actions = await agent.decide_actions(self.market)
                self._llm_call_count += 1
                await agent.apply_actions(actions, self.market)

                for action in actions:
                    all_actions.append({
                        "agent": agent.name,
                        "type": action.action_type,
                        "description": action.description,
                    })
            except Exception:
                logger.exception("Agent %s failed in round %d", agent.name, round_number)
                events.append(f"Agent {agent.name} encountered an error")

        # Update market state based on aggregate actions
        self._update_market(all_actions)

        # Apply scenario effects
        if self.scenario:
            self._apply_scenario_effects(round_number)

        return RoundResult(
            round_number=round_number,
            market_state=self.market.model_copy(),
            actions_taken=all_actions,
            events=events,
        )

    def _select_active_agents(self) -> list[BaseAgent]:
        """Randomly activate a subset of agents each round."""
        rate = settings.agent_activation_rate
        return [a for a in self.agents if random.random() < rate]

    def _update_market(self, actions: list[dict[str, Any]]) -> None:
        """Update market state based on aggregate agent actions."""
        hire_count = sum(1 for a in actions if a["type"] in ("recruit", "hire_engineers", "hire_internal"))
        train_count = sum(1 for a in actions if a["type"] in ("upskill", "learn_skill", "internal_training", "invest_rd"))

        # Hiring increases demand, training increases supply
        for skill in SkillCategory:
            if hire_count > 0:
                self.market.skill_demand[skill] = min(
                    1.0, self.market.skill_demand[skill] + hire_count * 0.01
                )
            if train_count > 0:
                self.market.skill_supply[skill] = min(
                    1.0, self.market.skill_supply[skill] + train_count * 0.005
                )

        # Price adjustment based on demand/supply
        for skill in SkillCategory:
            ratio = self.market.demand_supply_ratio(skill)
            if ratio > 1.2:
                self.market.unit_prices[skill] *= 1.02  # 需要超過 → 単価上昇
            elif ratio < 0.8:
                self.market.unit_prices[skill] *= 0.98  # 供給過多 → 単価下降

    def _apply_scenario_effects(self, round_number: int) -> None:
        """Apply scenario-specific effects to the market."""
        if not self.scenario:
            return

        # AI acceleration gradually increases automation rate
        if self.scenario.ai_acceleration != 0:
            delta = self.scenario.ai_acceleration * 0.005
            self.market.ai_automation_rate = max(
                0.0, min(1.0, self.market.ai_automation_rate + delta)
            )
            # AI acceleration boosts AI/ML demand
            if self.scenario.ai_acceleration > 0:
                self.market.skill_demand[SkillCategory.AI_ML] = min(
                    1.0,
                    self.market.skill_demand[SkillCategory.AI_ML] + 0.01,
                )

        # Economic shock affects all unit prices
        if self.scenario.economic_shock != 0:
            shock_factor = 1 + (self.scenario.economic_shock * 0.01)
            for skill in SkillCategory:
                self.market.unit_prices[skill] *= shock_factor

    def get_summary(self) -> dict[str, Any]:
        """Return simulation summary."""
        return {
            "total_rounds": len(self.results),
            "final_market": self.market.model_dump(),
            "agents": [a.to_summary() for a in self.agents],
            "llm_calls": self._llm_call_count,
        }
