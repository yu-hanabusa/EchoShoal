"""Simulation engine - orchestrates agent-based service impact simulation.

エージェントの行動・状態を知識グラフに時系列記録し、
可視性制御付きGraphRAGでエージェント間の情報非対称性を実現する。
"""

from __future__ import annotations

import json
import logging
import random
from collections.abc import Callable, Coroutine
from typing import Any

from app.config import settings
from app.core.graph.agent_memory import AgentMemoryStore, get_visibility
from app.core.graph.rag import GraphRAGRetriever
from app.core.llm.router import LLMRouter, TaskType
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
        self._initial_relationships: list[dict[str, str]] = []

    async def run(self, num_rounds: int | None = None) -> list[RoundResult]:
        """Run the full simulation."""
        rounds = num_rounds or (self.scenario.num_rounds if self.scenario else settings.default_rounds)
        rounds = min(rounds, settings.max_rounds)
        self._total_rounds = rounds

        logger.info("Starting simulation: %d rounds, %d agents", rounds, len(self.agents))

        # シナリオ解析結果で市場初期状態をLLMが設定
        if self._enriched_scenario:
            await self._initialize_from_scenario(self._enriched_scenario)

        # シナリオ要約をエージェントに渡す
        if self._scenario_summary:
            for agent in self.agents:
                agent.set_scenario_context(self._scenario_summary)

        # エージェントノードを知識グラフに登録
        if self._memory:
            await self._register_agents()

        # 初期関係構造をLLMで推定
        await self._generate_initial_relationships()

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

        # グラフからエージェント能力分布を取得（市場更新時の参考情報として使用）
        graph_context = await self._get_graph_context_for_market()

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

        # Each agent decides and applies actions (sequential: later agents see earlier actions)
        round_actions_so_far: list[dict[str, str]] = []

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

                # 同一ラウンド内の先行エージェント行動を注入（public/partialのみ）
                intra_round = self._format_intra_round_actions(round_actions_so_far, agent.name)
                if intra_round:
                    rag_context += intra_round

                # LLM意思決定（性格バイアス + ノイズ注入済み）
                actions = await agent.decide_actions(self.market, rag_context=rag_context)
                self._llm_call_count += 1

                # 行動を適用
                await agent.apply_actions(actions, self.market)

                # 行動をグラフに記録 + ラウンド内行動リストに追加
                for action in actions:
                    action_record = {
                        "agent": agent.name,
                        "agent_id": agent.id,
                        "type": action.action_type,
                        "description": action.description,
                        "visibility": get_visibility(action.action_type),
                        "dimension": action.parameters.get("dimension", ""),
                        "count": action.parameters.get("count", 1),
                        "reputation": agent.state.reputation,
                        "reacting_to": action.reacting_to,
                    }
                    all_actions.append(action_record)
                    round_actions_so_far.append(action_record)

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

                    # アクションに基づく関係記録
                    if self._memory and action.reacting_to:
                        await self._record_relationship_from_action(
                            agent, action, round_number,
                        )

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
        market_effects = await self._update_market(all_actions, round_number, graph_context)

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
                    logger.warning("市場効果記録失敗: agent=%s, round=%d", effect["agent_id"], round_number)

        # Apply events
        if self._event_scheduler:
            event_msgs = apply_active_events(
                self._event_scheduler.events, round_number, self.market
            )
            events.extend(event_msgs)

        # ナラティブ生成（アクション数が多いまたはイベントがあるラウンド）
        narrative = ""
        if len(all_actions) >= 3 or events:
            narrative = await self._generate_round_narrative(
                round_number, all_actions, events
            )

        return RoundResult(
            round_number=round_number,
            market_state=self.market.model_copy(deep=True),
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

    async def _get_graph_context_for_market(self) -> str:
        """グラフからエージェントの能力分布を取得し、市場更新の参考テキストを返す."""
        if not self._memory:
            return ""
        try:
            dim_data = await self._memory.graph.execute_read(
                "MATCH (a:Agent {simulation_id: $sim_id})-[r:SKILLED_IN]->(s:Skill) "
                "RETURN s.name AS dimension, avg(r.proficiency) AS avg_influence, "
                "       count(a) AS agent_count",
                {"sim_id": self._memory.simulation_id},
            )
            if not dim_data:
                return ""
            lines = ["【グラフ上のエージェント能力分布】"]
            for row in dim_data:
                lines.append(
                    f"  {row['dimension']}: 平均影響力={row['avg_influence']:.2f}, "
                    f"関与エージェント数={row['agent_count']}"
                )
            return "\n".join(lines)
        except Exception:
            return ""

    @staticmethod
    def _format_intra_round_actions(
        actions_so_far: list[dict[str, str]], current_agent: str
    ) -> str:
        """同一ラウンド内の先行エージェントのpublic/partial行動をテキスト化する."""
        visible = [
            a for a in actions_so_far
            if a.get("visibility") in ("public", "partial") and a.get("agent") != current_agent
        ]
        if not visible:
            return ""
        lines = ["\n【このラウンドで先に行動したステークホルダー】"]
        for a in visible:
            lines.append(f"  - {a['agent']}: {a['type']}「{a.get('description', '')[:60]}」")
        return "\n".join(lines)

    # アクション→関係タイプのマッピング
    _ACTION_TO_RELATION: dict[str, str] = {
        "build_competitor": "competitor",
        "launch_competing_product": "competitor",
        "launch_competing_feature": "competitor",
        "price_undercut": "competitor",
        "partner": "partner",
        "partner_integrate": "partner",
        "partner_public": "partner",
        "invest_seed": "investor",
        "invest_series": "investor",
        "fund_competitor": "investor",
        "regulate": "regulator",
        "investigate": "regulator",
        "acquire_service": "acquirer",
        "acquire_startup": "acquirer",
        "adopt_new_service": "user",
        "churn": "former_user",
        "recommend": "advocate",
        "complain": "critic",
    }

    async def _record_relationship_from_action(
        self,
        agent: BaseAgent,
        action: "AgentAction",
        round_number: int,
    ) -> None:
        """アクションのreacting_toに基づいてエージェント間関係をNeo4jに記録する."""
        if not self._memory or not action.reacting_to:
            return
        # reacting_toからターゲットエージェントを特定
        target = next(
            (a for a in self.agents if a.name == action.reacting_to), None
        )
        if not target:
            return
        relation_type = self._ACTION_TO_RELATION.get(action.action_type, "interaction")
        try:
            await self._memory.record_relationship(
                from_id=agent.id,
                to_id=target.id,
                relation_type=relation_type,
                round_number=round_number,
                description=f"{agent.name} → {action.action_type} → {target.name}",
            )
        except Exception:
            logger.debug("関係記録失敗: %s → %s", agent.name, action.reacting_to)

    def _select_active_agents(self) -> list[BaseAgent]:
        """Randomly activate a subset of agents each round."""
        rate = settings.agent_activation_rate
        return [a for a in self.agents if random.random() < rate]

    async def _initialize_from_scenario(self, enriched: EnrichedScenario) -> None:
        """LLMにシナリオを渡し、全ディメンション＋マクロ指標の初期値を推定させる."""
        prompt = (
            f"Service: {enriched.original.service_name or 'unknown'}\n"
            f"Scenario: {enriched.original.description[:500]}\n\n"
            "Estimate the INITIAL market state (0.0-1.0 scale) for this service "
            "AT THE MOMENT OF LAUNCH.\n\n"
            "各ディメンションの意味:\n"
            "- user_adoption: このサービスの市場浸透度（0.0=未発売, 0.1=ベータ段階, 0.5=普及中, 1.0=市場飽和）\n"
            "- revenue_potential: 収益化の見込み（0.0=収益モデル未定, 0.5=初期収益あり）\n"
            "- tech_maturity: 基盤技術の成熟度（0.0=実験段階, 0.5=実用レベル, 1.0=枯れた技術）\n"
            "- competitive_pressure: 競合の激しさ（0.0=競合なし, 0.5=複数競合, 1.0=レッドオーシャン）\n"
            "- regulatory_risk: 規制リスク（0.0=規制なし, 0.5=規制議論中, 1.0=厳格な規制下）\n"
            "- market_awareness: 市場認知度（0.0=無名, 0.5=業界で認知, 1.0=一般認知）\n"
            "- ecosystem_health: 連携エコシステム（0.0=なし, 0.5=パートナー数社, 1.0=豊富）\n"
            "- funding_climate: 資金調達環境（0.0=投資冷え込み, 0.5=通常, 1.0=バブル）\n\n"
            "Return EXACTLY this JSON structure with your estimated values:\n"
            '{"dimensions": {'
            '"user_adoption": 0.1, "revenue_potential": 0.2, "tech_maturity": 0.3, '
            '"competitive_pressure": 0.5, "regulatory_risk": 0.2, "market_awareness": 0.1, '
            '"ecosystem_health": 0.2, "funding_climate": 0.3}, '
            '"economic_sentiment": 0.5, "tech_hype_level": 0.4, '
            '"regulatory_pressure": 0.3, "ai_disruption_level": 0.3}'
        )

        try:
            response = await self.llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=prompt,
                system_prompt=(
                    "あなたはサービスビジネスの市場アナリストです。"
                    "シナリオの内容から、シミュレーション開始時点の市場状態を客観的に推定してください。"
                ),
            )
            self._llm_call_count += 1

            # ディメンション初期値を設定（LLMの判断をそのまま使用）
            raw_dims = response.get("dimensions", {})
            for dim in MarketDimension:
                if dim.value in raw_dims:
                    val = max(0.0, min(1.0, float(raw_dims[dim.value])))
                    self.market.dimensions[dim] = val

            # マクロ指標の初期値を設定
            for key in ("economic_sentiment", "tech_hype_level", "regulatory_pressure", "ai_disruption_level"):
                if key in response:
                    val = max(0.0, min(1.0, float(response[key])))
                    setattr(self.market, key, val)

            logger.info("LLMによる市場初期化完了: %s", {d.value: self.market.dimensions[d] for d in MarketDimension})

        except Exception:
            logger.warning("LLM市場初期化失敗、値は0.0のまま")

        if enriched.detected_policies:
            logger.info("検出政策: %s", ", ".join(enriched.detected_policies))

    async def _update_market(
        self, actions: list[dict[str, Any]], round_number: int, graph_context: str = ""
    ) -> list[dict[str, Any]]:
        """LLMにアクション一覧と市場状態を渡し、市場への影響を判断させる.

        固定係数テーブルは使用しない。LLMが状況に応じて影響度を判断する。
        """
        if not actions:
            return []

        market_effects: list[dict[str, Any]] = []

        # アクションサマリーを構築
        actions_summary = []
        for a in actions[:15]:
            rep = a.get("reputation", 0.0)
            actions_summary.append(
                f"- {a.get('agent', '?')}（reputation {rep:.1f}）: {a['type']}「{a.get('description', '')[:60]}」"
            )
        actions_text = "\n".join(actions_summary)

        # 現在の市場状態
        current_dims = {d.value: round(v, 3) for d, v in self.market.dimensions.items()}

        prompt = (
            f"Round {round_number}. Service: {self.market.service_name}\n"
            f"Current dimensions: {json.dumps(current_dims)}\n"
            f"Actions this round:\n{actions_text}\n\n"
            "Estimate market impact of these actions. "
            "Return EXACTLY this JSON structure with your estimated delta values (-0.1 to +0.1):\n"
            '{"dimension_deltas": {'
            '"user_adoption": 0.02, "revenue_potential": 0.01, "tech_maturity": 0.0, '
            '"competitive_pressure": 0.0, "regulatory_risk": 0.0, "market_awareness": 0.01, '
            '"ecosystem_health": 0.0, "funding_climate": 0.0}, '
            '"macro_deltas": {"economic_sentiment": 0.0, "tech_hype_level": 0.0, '
            '"regulatory_pressure": 0.0, "ai_disruption_level": 0.0}}'
        )

        try:
            response = await self.llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=prompt,
                system_prompt=(
                    "あなたはサービスビジネスの市場アナリストです。"
                    "エージェントの行動がサービスの市場にどう影響するかを、"
                    "行動の種類・エージェントの評判と規模・現在の市場状況を考慮して判断してください。"
                ),
            )
            self._llm_call_count += 1

            # ディメンションdeltaを適用
            raw_dims = response.get("dimension_deltas", {})
            for dim_key, delta in raw_dims.items():
                try:
                    dim = MarketDimension(dim_key)
                    clamped_delta = max(-0.1, min(0.1, float(delta)))
                    self.market.dimensions[dim] = max(
                        0.0, min(1.0, self.market.dimensions[dim] + clamped_delta)
                    )
                    if abs(clamped_delta) > 0.001:
                        market_effects.append({
                            "agent_id": actions[0].get("agent_id", "") if actions else "",
                            "action_type": "aggregate",
                            "dimension": dim_key,
                            "dimension_delta": clamped_delta,
                        })
                except (ValueError, TypeError):
                    pass

            # マクロdeltaを適用
            raw_macros = response.get("macro_deltas", {})
            for key in ("economic_sentiment", "tech_hype_level", "regulatory_pressure", "ai_disruption_level"):
                if key in raw_macros:
                    try:
                        delta = max(-0.05, min(0.05, float(raw_macros[key])))
                        current = getattr(self.market, key)
                        setattr(self.market, key, max(0.0, min(1.0, current + delta)))
                    except (ValueError, TypeError):
                        pass

        except Exception:
            logger.exception("LLM市場更新失敗、市場は変化なし")

        return market_effects

    def get_summary(self) -> dict[str, Any]:
        """Return simulation summary."""
        return {
            "total_rounds": len(self.results),
            "final_market": self.market.model_dump(),
            "agents": [a.to_summary() for a in self.agents],
            "llm_calls": self._llm_call_count,
            "initial_relationships": self._initial_relationships,
        }

    # ENTITY_RELATION → エージェント間関係タイプのマッピング
    _ENTITY_REL_TO_AGENT_REL: dict[str, str] = {
        "COMPETES_WITH": "competitor",
        "PROVIDES_INFRA": "partner",
        "TARGET_SECTOR": "user",
        "PARTNERS_WITH": "partner",
        "INVESTS_IN": "investor",
        "REGULATES": "regulator",
        "USES": "user",
        "ACQUIRES": "acquirer",
        "DEPENDS_ON": "partner",
        "AFFECTS": "interest",
    }

    async def _generate_initial_relationships(self) -> None:
        """初期関係を生成する.

        優先順位:
        1. ドキュメントから抽出済みのENTITY_RELATIONをエージェント名に照合
        2. LLMでエージェント間関係を推定（未カバー分）
        3. ステークホルダー種別ベースの構造的関係（フォールバック）
        """
        agent_names = [a.name for a in self.agents]
        if len(agent_names) < 2:
            return

        # 1. ドキュメントのENTITY_RELATIONからエージェント間関係を導出
        doc_rels = await self._relationships_from_documents(agent_names)
        if doc_rels:
            self._initial_relationships.extend(doc_rels)
            logger.info(
                "ドキュメント由来の初期関係%d件を生成", len(doc_rels),
            )

        # カバー済みエージェントペアを記録
        covered_pairs = {
            (r["from"], r["to"]) for r in self._initial_relationships
        }

        # 2. LLMでエージェント間関係を推定（未カバー分）
        names_text = ", ".join(agent_names[:30])
        service = self.scenario.service_name if self.scenario else ""

        prompt = (
            f"サービス: {service}\n"
            f"エージェント一覧: {names_text}\n\n"
            "これらのエージェント間の初期的な関係を推定してください。\n"
            "関係タイプ: competitor(競合), user(利用), investor(投資), "
            "regulator(規制), partner(提携), interest(関心)\n\n"
            '{"relationships":[{"from":"A","to":"B","type":"competitor"}]}'
        )

        try:
            response = await self.llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=prompt,
                system_prompt="JSON形式で返答。市場構造に基づいて関係を推定。",
            )
            rels = response.get("relationships", [])
            if isinstance(rels, list):
                valid_names = set(agent_names)
                for r in rels:
                    if (isinstance(r, dict)
                            and r.get("from") in valid_names
                            and r.get("to") in valid_names
                            and r.get("from") != r.get("to")
                            and (r["from"], r["to"]) not in covered_pairs):
                        self._initial_relationships.append({
                            "from": r["from"],
                            "to": r["to"],
                            "type": str(r.get("type", "interest")),
                            "round": 0,
                            "weight": 1,
                        })
                        covered_pairs.add((r["from"], r["to"]))
                logger.info("初期関係%d件（LLM+ドキュメント合計）", len(self._initial_relationships))
        except Exception:
            logger.warning("LLMによる初期関係生成失敗")

        # 3. フォールバック: 最低限の関係が必要
        if not self._initial_relationships:
            self._generate_structural_relationships()

    async def _relationships_from_documents(
        self, agent_names: list[str],
    ) -> list[dict[str, Any]]:
        """Neo4jのENTITY_RELATIONをエージェント名に照合して初期関係を導出する."""
        if not self._memory:
            return []

        sim_id = self.scenario.service_name if self.scenario else ""
        if not sim_id:
            return []

        try:
            rows = await self._memory.graph.execute_read(
                "MATCH (src)-[r:ENTITY_RELATION]->(tgt) "
                "RETURN src.name AS source, tgt.name AS target, "
                "       r.relation_type AS rel_type",
            )
        except Exception:
            logger.warning("ENTITY_RELATION取得失敗")
            return []

        if not rows:
            return []

        # エージェント名の照合用インデックス（部分一致対応）
        name_lower = {n.lower(): n for n in agent_names}

        def match_agent(entity_name: str) -> str | None:
            el = entity_name.lower()
            # 完全一致
            if el in name_lower:
                return name_lower[el]
            # エンティティ名がエージェント名に含まれる or 逆
            for nl, original in name_lower.items():
                if el in nl or nl in el:
                    return original
            return None

        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for row in rows:
            rel_type = row.get("rel_type", "")
            agent_rel = self._ENTITY_REL_TO_AGENT_REL.get(rel_type)
            if not agent_rel:
                continue

            src_agent = match_agent(row["source"])
            tgt_agent = match_agent(row["target"])
            if not src_agent or not tgt_agent or src_agent == tgt_agent:
                continue
            if (src_agent, tgt_agent) in seen:
                continue

            results.append({
                "from": src_agent,
                "to": tgt_agent,
                "type": agent_rel,
                "round": 0,
                "weight": 2,  # ドキュメント由来は重み高め
            })
            seen.add((src_agent, tgt_agent))

        return results

    def _generate_structural_relationships(self) -> None:
        """ステークホルダー種別に基づく構造的な関係を生成する.

        これは恣意的ではなく、種別の定義から導かれる関係:
        - platformer/enterprise → 対象サービスの競合
        - end_user → 対象サービスの潜在ユーザー
        - investor → 対象サービスへの出資者
        - government → 市場の規制者
        - community → 市場への関心者
        """
        service = self.scenario.service_name if self.scenario else ""
        sn_lower = service.lower()

        # 対象サービスのエージェントを特定
        target_agent = None
        for a in self.agents:
            if sn_lower and sn_lower in a.name.lower():
                target_agent = a.name
                break

        if not target_agent:
            return

        _type_map = {
            "platformer": "competitor",
            "enterprise": "competitor",
            "end_user": "user",
            "investor": "investor",
            "government": "regulator",
            "community": "interest",
            "freelancer": "interest",
            "indie_developer": "interest",
        }

        for a in self.agents:
            if a.name == target_agent:
                continue

            rel_type = _type_map.get(a.profile.stakeholder_type.value, "interest")

            self._initial_relationships.append({
                "from": a.name,
                "to": target_agent,
                "type": rel_type,
                "round": 0,
                "weight": 1,
            })

        logger.info("構造的関係%d件を生成", len(self._initial_relationships))
