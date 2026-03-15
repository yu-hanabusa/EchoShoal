"""Simulation engine - orchestrates agent-based service impact simulation.

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
from app.simulation.events.scheduler import EventScheduler
from app.simulation.models import (
    DocumentReference,
    ServiceMarketState,
    RoundResult,
    ScenarioInput,
    MarketDimension,
)
from app.simulation.scenario_analyzer import EnrichedScenario

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Orchestrates the agent-based simulation of service business impact.

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
        self.market = ServiceMarketState(
            service_name=scenario.service_name if scenario else "",
        )
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
                    industry=agent.profile.stakeholder_type.value,
                )
            except Exception:
                logger.warning("Agent登録失敗: %s", agent.name)

    async def _run_round(self, round_number: int) -> RoundResult:
        """Execute a single simulation round."""
        self.market.round_number = round_number
        all_actions: list[dict[str, Any]] = []
        events: list[str] = []
        doc_refs: list[DocumentReference] = []

        # グラフからディメンション供給を同期（定量的フィードバック）
        await self._sync_market_from_graph()

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

                        # 文書参照ログを記録
                        for doc_ref in getattr(ctx, 'document_references', []):
                            doc_refs.append(DocumentReference(
                                document_id=doc_ref.get("id", ""),
                                document_name=doc_ref.get("name", ""),
                                agent_id=agent.id,
                                agent_name=agent.name,
                                round_number=round_number,
                                context_snippet=doc_ref.get("snippet", ""),
                            ))
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
                        "agent_id": agent.id,
                        "type": action.action_type,
                        "description": action.description,
                        "visibility": get_visibility(action.action_type),
                        "dimension": action.parameters.get("dimension", ""),
                        "count": action.parameters.get("count", 1),
                        "reputation": agent.state.reputation,
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

                # 状態スナップショット + capabilitiesをグラフに記録
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
                        # ディメンション影響力をグラフに記録
                        cap_dict = {
                            dim.value: influence
                            for dim, influence in agent.state.capabilities.items()
                        }
                        if cap_dict:
                            await self._memory.record_skills(agent.id, cap_dict)
                    except Exception:
                        logger.warning("状態記録失敗: agent=%s", agent.name)

            except Exception:
                logger.exception("Agent %s failed in round %d", agent.name, round_number)
                events.append(f"Agent {agent.name} encountered an error")

        # Update market state based on aggregate actions
        market_effects = self._update_market(all_actions)

        # 因果チェーンをグラフに記録
        if self._memory and market_effects:
            for effect in market_effects:
                try:
                    await self._memory.record_market_effect(
                        agent_id=effect["agent_id"],
                        round_number=round_number,
                        action_type=effect["action_type"],
                        skill=effect["dimension"],
                        demand_delta=effect["dimension_delta"],
                        supply_delta=0.0,
                    )
                except Exception:
                    pass

        # Apply events
        if self._event_scheduler:
            event_msgs = apply_active_events(
                self._event_scheduler.events, round_number, self.market
            )
            events.extend(event_msgs)
        elif self.scenario:
            self._apply_scenario_effects(round_number)

        # ナラティブ生成（アクション数が多いまたはイベントがあるラウンド）
        narrative = ""
        if len(all_actions) >= 3 or events:
            narrative = await self._generate_round_narrative(
                round_number, all_actions, events
            )

        return RoundResult(
            round_number=round_number,
            market_state=self.market.model_copy(),
            actions_taken=all_actions,
            events=events,
            summary=narrative,
            document_references=doc_refs,
        )

    async def _generate_round_narrative(
        self,
        round_number: int,
        actions: list[dict[str, Any]],
        events: list[str],
    ) -> str:
        """LLMにラウンドの出来事を渡し、1-2文のナラティブを生成する."""
        action_lines = []
        for a in actions[:8]:
            action_lines.append(f"- {a.get('agent', '?')}: {a['type']}（{a.get('description', '')[:50]}）")
        actions_text = "\n".join(action_lines) if action_lines else "特になし"
        events_text = "\n".join(events) if events else "なし"

        prompt = (
            f"ラウンド{round_number}で起きた出来事を1-2文の日本語で要約してください。\n"
            f"サービス名: {self.market.service_name}\n\n"
            f"アクション:\n{actions_text}\n\n"
            f"イベント:\n{events_text}\n\n"
            "短く端的に、ストーリーとして要約してください。JSON不要、テキストのみ。"
        )

        try:
            return await self.llm.generate(
                task_type=TaskType.AGENT_DECISION,
                prompt=prompt,
                system_prompt="シミュレーションの各ラウンドを簡潔なナラティブにまとめてください。",
                temperature=0.7,
            )
        except Exception:
            return ""

    async def _sync_market_from_graph(self) -> None:
        """グラフのCAPABLE_OFデータから市場のディメンションを同期する."""
        if not self._memory:
            return
        try:
            dim_data = await self._memory.graph.execute_read(
                "MATCH (a:Agent {simulation_id: $sim_id})-[r:SKILLED_IN]->(s:Skill) "
                "RETURN s.name AS dimension, avg(r.proficiency) AS avg_influence, "
                "       count(a) AS agent_count",
                {"sim_id": self._memory.simulation_id},
            )
            for row in dim_data:
                try:
                    dim = MarketDimension(row["dimension"])
                    graph_value = min(1.0, row["avg_influence"] * row["agent_count"] * 0.05)
                    current = self.market.dimensions[dim]
                    self.market.dimensions[dim] = current * 0.7 + graph_value * 0.3
                except ValueError:
                    pass
        except Exception:
            logger.warning("グラフからのディメンション同期に失敗")

    def _select_active_agents(self) -> list[BaseAgent]:
        """Randomly activate a subset of agents each round."""
        rate = settings.agent_activation_rate
        return [a for a in self.agents if random.random() < rate]

    def _initialize_from_scenario(self, enriched: EnrichedScenario) -> None:
        """シナリオ解析結果で市場初期状態を調整する."""
        for dim in enriched.detected_dimensions:
            self.market.dimensions[dim] = min(
                1.0, self.market.dimensions[dim] + 0.1
            )
            logger.info("シナリオ初期化: %s の値を+0.1", dim.value)

        if enriched.detected_policies:
            logger.info(
                "シナリオ初期化: 検出政策 %s",
                ", ".join(enriched.detected_policies),
            )

    def _update_market(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Update market state based on aggregate agent actions.

        すべてのアクションが市場に影響を与える。
        因果チェーン記録用のeffectsリストを返す。
        """
        market_effects: list[dict[str, Any]] = []

        # アクション → ディメンション影響のマッピング
        # {action_type: {dimension: delta}}
        _ACTION_EFFECTS: dict[str, dict[str, float]] = {
            # 企業アクション
            "adopt_service": {"user_adoption": 0.02, "revenue_potential": 0.01},
            "reject_service": {"user_adoption": -0.01},
            "build_competitor": {"competitive_pressure": 0.03, "tech_maturity": 0.01},
            "acquire_startup": {"competitive_pressure": -0.02, "market_awareness": 0.02},
            "invest_rd": {"tech_maturity": 0.015},
            "lobby_regulation": {"regulatory_risk": 0.02},
            "partner": {"ecosystem_health": 0.015, "user_adoption": 0.01},
            # フリーランス
            "adopt_tool": {"user_adoption": 0.01, "market_awareness": 0.005},
            "offer_service": {"revenue_potential": 0.01, "ecosystem_health": 0.005},
            "upskill": {"tech_maturity": 0.005},
            "build_portfolio": {"market_awareness": 0.005},
            "raise_rate": {"revenue_potential": 0.005},
            "switch_platform": {"ecosystem_health": -0.005},
            "network": {"market_awareness": 0.005},
            # 個人開発者
            "launch_competing_product": {"competitive_pressure": 0.02, "tech_maturity": 0.01},
            "pivot_product": {"user_adoption": 0.005},
            "open_source": {"ecosystem_health": 0.02, "market_awareness": 0.01},
            "monetize": {"revenue_potential": 0.01},
            "seek_funding": {"funding_climate": 0.01},
            "build_community": {"ecosystem_health": 0.01, "user_adoption": 0.005},
            # 行政
            "regulate": {"regulatory_risk": 0.03},
            "subsidize": {"funding_climate": 0.02, "user_adoption": 0.01},
            "certify": {"market_awareness": 0.015, "regulatory_risk": -0.01},
            "investigate": {"regulatory_risk": 0.02},
            "deregulate": {"regulatory_risk": -0.02, "ecosystem_health": 0.01},
            "partner_public": {"user_adoption": 0.015, "market_awareness": 0.01},
            "issue_guideline": {"regulatory_risk": 0.01, "tech_maturity": 0.005},
            # 投資家
            "invest_seed": {"funding_climate": 0.02, "market_awareness": 0.01},
            "invest_series": {"funding_climate": 0.03, "revenue_potential": 0.015},
            "divest": {"funding_climate": -0.02},
            "fund_competitor": {"competitive_pressure": 0.02, "funding_climate": 0.005},
            "market_signal": {"market_awareness": 0.01},
            "mentor": {"tech_maturity": 0.005, "ecosystem_health": 0.005},
            # プラットフォーマー
            "launch_competing_feature": {"competitive_pressure": 0.04, "market_awareness": 0.02},
            "acquire_service": {"competitive_pressure": -0.02, "market_awareness": 0.02},
            "partner_integrate": {"ecosystem_health": 0.02, "user_adoption": 0.015},
            "restrict_api": {"competitive_pressure": 0.02, "ecosystem_health": -0.015},
            "price_undercut": {"competitive_pressure": 0.03, "revenue_potential": -0.02},
            "open_platform": {"ecosystem_health": 0.015, "user_adoption": 0.01},
            # 業界団体
            "endorse": {"market_awareness": 0.015, "user_adoption": 0.01},
            "set_standard": {"tech_maturity": 0.02, "ecosystem_health": 0.015},
            "reject_standard": {"competitive_pressure": 0.01, "market_awareness": -0.005},
            "create_alternative": {"competitive_pressure": 0.02, "ecosystem_health": 0.01},
            "educate_market": {"market_awareness": 0.02, "user_adoption": 0.005},
            "publish_report": {"market_awareness": 0.015},
            # 共通: 影響なし
            "wait_and_observe": {},
            "wait_and_see": {},
            "ignore": {},
            "observe": {},
            "rest": {},
            "abandon_project": {"competitive_pressure": -0.005},
        }

        for action in actions:
            action_type = action["type"]
            dim_str = action.get("dimension")

            effects = _ACTION_EFFECTS.get(action_type, {})
            # 評判が高いエージェントほどアクションの市場影響が大きい
            rep = action.get("reputation", 0.5)
            rep_multiplier = 0.5 + rep  # 0.5〜1.5の範囲

            for dim_key, delta in effects.items():
                try:
                    dim = MarketDimension(dim_key)
                    scaled_delta = delta * rep_multiplier
                    self.market.dimensions[dim] = max(
                        0.0, min(1.0, self.market.dimensions[dim] + scaled_delta)
                    )
                    market_effects.append({
                        "agent_id": action.get("agent_id", ""),
                        "action_type": action_type,
                        "dimension": dim_key,
                        "dimension_delta": scaled_delta,
                    })
                except ValueError:
                    pass

            # パラメータで指定されたディメンションにも追加影響
            if dim_str and dim_str not in effects:
                try:
                    dim = MarketDimension(dim_str)
                    extra_delta = 0.005 * rep_multiplier
                    self.market.dimensions[dim] = max(
                        0.0, min(1.0, self.market.dimensions[dim] + extra_delta)
                    )
                except ValueError:
                    pass

        return market_effects

    def _apply_scenario_effects(self, round_number: int) -> None:
        """Apply scenario-specific effects to the market."""
        if not self.scenario:
            return

        # Tech disruption gradually increases relevant dimensions
        if self.scenario.tech_disruption != 0:
            delta = self.scenario.tech_disruption * 0.005
            self.market.ai_disruption_level = max(
                0.0, min(1.0, self.market.ai_disruption_level + delta)
            )
            if self.scenario.tech_disruption > 0:
                self.market.dimensions[MarketDimension.TECH_MATURITY] = min(
                    1.0,
                    self.market.dimensions[MarketDimension.TECH_MATURITY] + 0.01,
                )

        # Economic climate affects sentiment
        if self.scenario.economic_climate != 0:
            delta = self.scenario.economic_climate * 0.01
            self.market.economic_sentiment = max(
                0.0, min(1.0, self.market.economic_sentiment + delta)
            )

    def get_summary(self) -> dict[str, Any]:
        """Return simulation summary."""
        return {
            "total_rounds": len(self.results),
            "final_market": self.market.model_dump(),
            "agents": [a.to_summary() for a in self.agents],
            "llm_calls": self._llm_call_count,
        }
