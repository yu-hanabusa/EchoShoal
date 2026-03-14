"""Simulation engine - orchestrates agent-based market simulation.

エージェントの行動・状態を知識グラフに時系列記録し、
可視性制御付きGraphRAGでエージェント間の情報非対称性を実現する。
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable, Coroutine
from typing import Any

from app.config import settings
from app.core.graph.agent_memory import AgentMemoryStore, get_visibility
from app.core.graph.rag import GraphRAGRetriever
from app.core.llm.router import LLMRouter
from app.simulation.agents.base import BaseAgent
from app.simulation.events.effects import apply_active_events
from app.simulation.events.models import MarketEvent
from app.simulation.events.scheduler import EventScheduler
from app.simulation.models import (
    Industry,
    MarketState,
    RoundResult,
    ScenarioInput,
    SkillCategory,
)
from app.simulation.scenario_analyzer import EnrichedScenario

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Orchestrates the agent-based simulation of the IT labor market.

    Each round:
    1. Activate a subset of agents
    2. [RAG] Each agent gets its own context (visible actions only)
    3. Each active agent decides actions (personality-biased LLM + noise)
    4. Actions are applied to agent states
    5. [Graph] Actions and state snapshots are recorded to Neo4j
    6. Market state is updated based on aggregate agent actions
    7. Round result is recorded
    """

    # コールバック型: async def callback(current_round, total_rounds) -> None
    ProgressCallback = Callable[[int, int], Coroutine[Any, Any, None]]

    def __init__(
        self,
        agents: list[BaseAgent],
        llm: LLMRouter,
        scenario: ScenarioInput | None = None,
        on_progress: ProgressCallback | None = None,
        event_scheduler: EventScheduler | None = None,
        rag: GraphRAGRetriever | None = None,
        agent_memory: AgentMemoryStore | None = None,
        enriched_scenario: EnrichedScenario | None = None,
    ):
        self.agents = agents
        self.llm = llm
        self.scenario = scenario
        self.market = MarketState()
        self.results: list[RoundResult] = []
        self._llm_call_count = 0
        self._on_progress = on_progress
        self._event_scheduler = event_scheduler
        self._rag = rag
        self._memory = agent_memory
        self._enriched_scenario = enriched_scenario
        self._scenario_summary = enriched_scenario.context_summary if enriched_scenario else ""

    async def run(self, num_rounds: int | None = None) -> list[RoundResult]:
        """Run the full simulation."""
        rounds = num_rounds or (self.scenario.num_rounds if self.scenario else settings.default_rounds)
        rounds = min(rounds, settings.max_rounds)

        logger.info("Starting simulation: %d rounds, %d agents", rounds, len(self.agents))

        # シナリオ解析結果で市場初期状態を調整
        if self._enriched_scenario:
            self._initialize_from_scenario(self._enriched_scenario)

        # シナリオ要約をエージェントに渡す
        if self._scenario_summary:
            for agent in self.agents:
                agent.set_scenario_context(self._scenario_summary)

        # エージェントノードを知識グラフに登録
        if self._memory:
            await self._register_agents()

        for round_num in range(1, rounds + 1):
            if self._llm_call_count >= settings.max_llm_calls:
                logger.warning("LLM call limit reached at round %d", round_num)
                break

            result = await self._run_round(round_num)
            self.results.append(result)

            if self._on_progress:
                await self._on_progress(round_num, rounds)

        return self.results

    async def _register_agents(self) -> None:
        """全エージェントをNeo4jに登録する."""
        for agent in self.agents:
            try:
                await self._memory.ensure_agent_node(
                    agent_id=agent.id,
                    name=agent.name,
                    agent_type=agent.profile.agent_type,
                    industry=agent.profile.industry.value,
                )
            except Exception:
                logger.warning("Agent登録失敗: %s", agent.name)

    async def _run_round(self, round_number: int) -> RoundResult:
        """Execute a single simulation round."""
        self.market.round_number = round_number
        all_actions: list[dict[str, Any]] = []
        events: list[str] = []

        # Activate subset of agents
        active_agents = self._select_active_agents()
        logger.info("Round %d: %d/%d agents active", round_number, len(active_agents), len(self.agents))

        # アクティブイベントの説明テキストを生成
        active_events_text = ""
        if self._event_scheduler:
            active = self._event_scheduler.get_active_events(round_number)
            if active:
                event_lines = [f"【現在発生中のイベント（R{round_number}）】"]
                for evt in active:
                    event_lines.append(f"  - {evt.name}: {evt.description}")
                active_events_text = "\n".join(event_lines)

        # Each agent decides and applies actions
        for agent in active_agents:
            try:
                # エージェント固有のRAGコンテキスト取得（可視性制御付き）
                rag_context = ""
                if self._rag:
                    try:
                        ctx = await self._rag.get_agent_context(
                            agent.id, round_number,
                            active_events_text=active_events_text,
                        )
                        rag_context = ctx.to_prompt()
                    except Exception:
                        logger.warning("RAGコンテキスト取得失敗: agent=%s", agent.name)

                # LLM意思決定（性格バイアス + ノイズ注入済み）
                actions = await agent.decide_actions(self.market, rag_context=rag_context)
                self._llm_call_count += 1

                # 行動を適用
                await agent.apply_actions(actions, self.market)

                # 行動をグラフに記録
                for action in actions:
                    all_actions.append({
                        "agent": agent.name,
                        "type": action.action_type,
                        "description": action.description,
                        "visibility": get_visibility(action.action_type),
                        "skill": action.parameters.get("skill", ""),
                        "count": action.parameters.get("count", 1),
                    })
                    if self._memory:
                        try:
                            await self._memory.record_action(
                                agent_id=agent.id,
                                agent_name=agent.name,
                                round_number=round_number,
                                action_type=action.action_type,
                                description=action.description,
                            )
                        except Exception:
                            logger.warning("行動記録失敗: agent=%s", agent.name)

                # 状態スナップショット + スキルをグラフに記録
                if self._memory:
                    try:
                        await self._memory.record_state(
                            agent_id=agent.id,
                            round_number=round_number,
                            state={
                                "revenue": agent.state.revenue,
                                "cost": agent.state.cost,
                                "headcount": agent.state.headcount,
                                "satisfaction": agent.state.satisfaction,
                                "reputation": agent.state.reputation,
                                "active_contracts": agent.state.active_contracts,
                            },
                        )
                        # スキル習熟度をグラフに記録
                        skill_dict = {
                            sc.value: prof
                            for sc, prof in agent.state.skills.items()
                        }
                        if skill_dict:
                            await self._memory.record_skills(agent.id, skill_dict)
                    except Exception:
                        logger.warning("状態記録失敗: agent=%s", agent.name)

            except Exception:
                logger.exception("Agent %s failed in round %d", agent.name, round_number)
                events.append(f"Agent {agent.name} encountered an error")

        # Update market state based on aggregate actions
        self._update_market(all_actions)

        # Apply events (replaces old _apply_scenario_effects)
        if self._event_scheduler:
            event_msgs = apply_active_events(
                self._event_scheduler.events, round_number, self.market
            )
            events.extend(event_msgs)
        elif self.scenario:
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

    def _initialize_from_scenario(self, enriched: EnrichedScenario) -> None:
        """シナリオ解析結果で市場初期状態を調整する."""
        for skill in enriched.detected_skills:
            self.market.skill_demand[skill] = min(
                1.0, self.market.skill_demand[skill] + 0.1
            )
            logger.info("シナリオ初期化: %s の需要を+0.1", skill.value)

        for industry in enriched.detected_industries:
            self.market.industry_growth[industry] += 0.05
            logger.info("シナリオ初期化: %s の成長率を+0.05", industry.value)

        if enriched.detected_policies:
            logger.info(
                "シナリオ初期化: 検出政策 %s",
                ", ".join(enriched.detected_policies),
            )

    def _update_market(self, actions: list[dict[str, Any]]) -> None:
        """Update market state based on aggregate agent actions.

        各アクションのスキル・数量パラメータを使い、
        スキル別に需要・供給を更新する。
        """
        _HIRE_ACTIONS = {"recruit", "hire_engineers", "hire_internal"}
        _TRAIN_ACTIONS = {"upskill", "learn_skill", "internal_training", "invest_rd"}
        _DEMAND_ACTIONS = {"bid_project", "expand_sales", "outsource_project", "start_dx"}

        for action in actions:
            action_type = action["type"]
            skill_str = action.get("skill")
            count = action.get("count", 1)

            # スキルが指定されていればそのスキルだけに影響
            target_skills: list[SkillCategory] = []
            if skill_str:
                try:
                    target_skills = [SkillCategory(skill_str)]
                except ValueError:
                    pass

            if action_type in _HIRE_ACTIONS:
                if target_skills:
                    for sc in target_skills:
                        self.market.skill_demand[sc] = min(
                            1.0, self.market.skill_demand[sc] + count * 0.005
                        )
                else:
                    # スキル未指定の場合は全スキルに薄く影響
                    for sc in SkillCategory:
                        self.market.skill_demand[sc] = min(
                            1.0, self.market.skill_demand[sc] + count * 0.001
                        )

            elif action_type in _TRAIN_ACTIONS:
                if target_skills:
                    for sc in target_skills:
                        self.market.skill_supply[sc] = min(
                            1.0, self.market.skill_supply[sc] + count * 0.003
                        )
                else:
                    for sc in SkillCategory:
                        self.market.skill_supply[sc] = min(
                            1.0, self.market.skill_supply[sc] + count * 0.0005
                        )

            elif action_type in _DEMAND_ACTIONS:
                if target_skills:
                    for sc in target_skills:
                        self.market.skill_demand[sc] = min(
                            1.0, self.market.skill_demand[sc] + 0.003
                        )

        # Price adjustment based on demand/supply ratio per skill
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
