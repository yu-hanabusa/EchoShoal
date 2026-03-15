"""OASIS シミュレーションランナー — SNS空間でのエージェント間インタラクション.

OASISフレームワークを使用して、エージェントがReddit/Twitter的なSNS空間で
投稿・コメント・リポスト・フォローを通じてインタラクションする。

既存のSimulationEngineを置換し、同じRoundResult形式で結果を返す。
"""

from __future__ import annotations

import logging
import random
import sqlite3
from collections.abc import Callable, Coroutine
from typing import Any

from app.config import settings
from app.core.llm.router import LLMRouter, TaskType
from app.simulation.agents.base import BaseAgent
from app.simulation.events.effects import apply_active_events
from app.simulation.events.scheduler import EventScheduler
from app.simulation.models import (
    MarketDimension,
    RoundResult,
    ScenarioInput,
    ServiceMarketState,
)
from app.simulation.scenario_analyzer import EnrichedScenario

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], Coroutine[Any, Any, None]]


class OASISSimulationEngine:
    """OASISベースのシミュレーションエンジン.

    既存のSimulationEngineと同じインターフェース（run(), get_summary()）を持ち、
    内部でOASIS環境を使用してエージェント間のSNSインタラクションを実行する。
    """

    def __init__(
        self,
        agents: list[BaseAgent],
        llm: LLMRouter,
        scenario: ScenarioInput | None = None,
        on_progress: ProgressCallback | None = None,
        event_scheduler: EventScheduler | None = None,
        enriched_scenario: EnrichedScenario | None = None,
        simulation_id: str = "",
        # 以下は既存互換のために受け取るが、OASISでは別途管理する
        rag=None,
        agent_memory=None,
    ):
        self.agents = agents
        self.llm = llm
        self.scenario = scenario
        self.market = ServiceMarketState(
            service_name=scenario.service_name if scenario else "",
        )
        self.results: list[RoundResult] = []
        self._on_progress = on_progress
        self._event_scheduler = event_scheduler
        self._enriched_scenario = enriched_scenario
        self._simulation_id = simulation_id
        self._llm_call_count = 0

        # OASIS環境（run()で初期化）
        self._env = None
        self._agent_graph = None
        self._oasis_agents: dict[str, Any] = {}  # agent.id -> SocialAgent
        self._db_path = ""

    async def run(self, num_rounds: int | None = None) -> list[RoundResult]:
        """OASIS環境でシミュレーションを実行する."""
        rounds = num_rounds or (self.scenario.num_rounds if self.scenario else settings.default_rounds)
        rounds = min(rounds, settings.max_rounds)

        logger.info("OASISシミュレーション開始: %dラウンド, %dエージェント", rounds, len(self.agents))

        # 市場初期状態をLLMで推定
        if self._enriched_scenario:
            await self._initialize_from_scenario(self._enriched_scenario)

        # OASIS環境セットアップ
        await self._setup_oasis_environment()

        try:
            for round_num in range(1, rounds + 1):
                result = await self._run_oasis_round(round_num)
                self.results.append(result)

                if self._on_progress:
                    await self._on_progress(round_num, rounds)

        finally:
            await self._cleanup_oasis()

        return self.results

    async def _setup_oasis_environment(self) -> None:
        """OASIS環境を初期化する."""
        import oasis
        from oasis import AgentGraph, SocialAgent
        from oasis.social_agent.agent import UserInfo

        from app.oasis.config import create_oasis_model, get_database_path
        from app.oasis.profile_generator import agents_to_oasis_profiles, build_agent_graph

        # モデル作成
        oasis_model = create_oasis_model()

        # プロファイル変換
        profiles = agents_to_oasis_profiles(self.agents)
        graph_data = build_agent_graph(profiles)

        # エージェントグラフ構築
        self._agent_graph = AgentGraph()

        # Redditデフォルトアクション
        from oasis.social_platform.typing import ActionType
        available_actions = ActionType.get_default_reddit_actions()

        # SocialAgent生成
        for i, profile in enumerate(profiles):
            user_info = UserInfo(
                user_name=profile["user_id"][:16],
                name=profile["user_name"],
                description=self._build_agent_description(profile),
                profile={
                    "other_info": {
                        "user_profile": profile["personality_description"],
                        "stakeholder_type": profile["stakeholder_type"],
                        "stance": profile["stance"],
                        "gender": profile.get("gender", "Non-binary"),
                        "age": profile.get("age", 35),
                        "mbti": profile.get("mbti", "INTJ"),
                        "country": profile.get("country", "Japan"),
                    }
                },
                recsys_type="reddit",
            )
            social_agent = SocialAgent(
                agent_id=i,
                user_info=user_info,
                agent_graph=self._agent_graph,
                model=oasis_model,
                available_actions=available_actions,
            )
            self._agent_graph.add_agent(social_agent)
            self._oasis_agents[profile["user_id"]] = social_agent

        # 初期エッジ追加
        for edge in graph_data["edges"]:
            source_idx = next(
                (i for i, p in enumerate(profiles) if p["user_id"] == edge["source"]),
                None,
            )
            target_idx = next(
                (i for i, p in enumerate(profiles) if p["user_id"] == edge["target"]),
                None,
            )
            if source_idx is not None and target_idx is not None:
                self._agent_graph.add_edge(source_idx, target_idx)

        # OASIS環境作成
        self._db_path = get_database_path(self._simulation_id or "default")

        self._env = oasis.make(
            agent_graph=self._agent_graph,
            platform=oasis.DefaultPlatformType.REDDIT,
            database_path=self._db_path,
        )

        await self._env.reset()

        # シナリオのシード投稿を注入
        await self._inject_seed_posts()

        logger.info("OASIS環境セットアップ完了: %dエージェント", len(self._oasis_agents))

    def _build_agent_description(self, profile: dict[str, Any]) -> str:
        """OASISエージェントの説明文を構築する."""
        parts = [
            f"You are {profile['user_name']}, a {profile['stakeholder_type']} stakeholder.",
            f"Bio: {profile['bio']}",
            f"Stance: {profile['stance']}",
            f"Personality: {profile['personality_description']}",
        ]
        if self.scenario:
            parts.append(
                f"Context: Evaluating the impact of '{self.scenario.service_name}' "
                f"on the market. {self.scenario.description[:200]}"
            )
        parts.append(
            "Discuss, debate, and share your perspective on this service's market impact. "
            "React to other stakeholders' posts. Be specific and concrete."
        )
        return "\n".join(parts)

    async def _inject_seed_posts(self) -> None:
        """シナリオに基づくシード投稿を注入する."""
        from oasis.social_platform.typing import ActionType

        if not self.scenario or not self._env:
            return

        # 最初の3体のエージェントにシード投稿を作成させる
        oasis_agents = list(self._oasis_agents.values())
        seed_agents = oasis_agents[:min(3, len(oasis_agents))]

        seed_topics = [
            f"New service alert: '{self.scenario.service_name}' has entered the market. "
            f"Here's what we know: {self.scenario.description[:300]}",
            f"Market analysis thread: What does '{self.scenario.service_name}' mean for our industry? "
            "Let's discuss the potential impact.",
            f"I've been looking into '{self.scenario.service_name}'. "
            "Curious what other stakeholders think about adoption prospects.",
        ]

        try:
            from oasis import ManualAction
            seed_actions = {}
            for agent, topic in zip(seed_agents, seed_topics):
                seed_actions[agent] = [
                    ManualAction(
                        action_type=ActionType.CREATE_POST,
                        action_args={"content": topic},
                    )
                ]
            await self._env.step(seed_actions)
            logger.info("シード投稿注入完了: %d件", len(seed_actions))
        except Exception:
            logger.warning("シード投稿注入失敗")

    async def _run_oasis_round(self, round_number: int) -> RoundResult:
        """1ラウンドのOASISシミュレーションを実行する."""
        self.market.round_number = round_number
        all_actions: list[dict[str, Any]] = []
        events: list[str] = []

        # Time Engine: アクティブエージェントを確率的に選択
        active_agents = self._select_active_oasis_agents()

        logger.info(
            "OASIS Round %d: %d/%d agents active",
            round_number, len(active_agents), len(self._oasis_agents),
        )

        # イベント投稿（外部要因をSNS投稿として注入）
        if self._event_scheduler:
            event_msgs = await self._inject_events_as_posts(round_number)
            events.extend(event_msgs)

        # LLMアクション実行（アクティブエージェントが自律的に行動）
        if active_agents and self._env:
            try:
                from oasis import LLMAction
                actions_dict = {agent: LLMAction() for agent in active_agents}

                for step in range(settings.oasis_rounds_per_step):
                    await self._env.step(actions_dict)
                    self._llm_call_count += len(active_agents)

            except Exception:
                logger.exception("OASISステップ実行失敗: round=%d", round_number)
                events.append(f"Round {round_number}: OASIS step failed")

        # SQLiteからこのラウンドのアクションを取得
        round_actions = self._extract_round_actions(round_number)
        all_actions.extend(round_actions)

        # アクションログから市場ディメンションを更新
        if round_actions:
            await self._update_market_from_actions(round_actions, round_number)

        # 外部イベント効果を適用
        if self._event_scheduler:
            event_effects = apply_active_events(
                self._event_scheduler.events, round_number, self.market
            )
            events.extend(event_effects)

        # ナラティブ生成
        narrative = ""
        if len(all_actions) >= 2 or events:
            narrative = await self._generate_round_narrative(
                round_number, all_actions, events
            )

        return RoundResult(
            round_number=round_number,
            market_state=self.market.model_copy(deep=True),
            actions_taken=all_actions,
            events=events,
            summary=narrative,
        )

    def _select_active_oasis_agents(self) -> list:
        """Time Engine: アクティブエージェントを確率的に選択する."""
        rate = settings.agent_activation_rate
        all_agents = list(self._oasis_agents.values())
        return [a for a in all_agents if random.random() < rate]

    async def _inject_events_as_posts(self, round_number: int) -> list[str]:
        """外部イベントをSNS投稿として注入する."""
        if not self._event_scheduler or not self._env:
            return []

        active_events = self._event_scheduler.get_active_events(round_number)
        if not active_events:
            return []

        from oasis import ManualAction
        from oasis.social_platform.typing import ActionType

        event_msgs = []
        oasis_agents = list(self._oasis_agents.values())

        for evt in active_events:
            # ランダムなエージェントがイベントニュースを投稿
            if oasis_agents:
                poster = random.choice(oasis_agents)
                content = (
                    f"[MARKET EVENT] {evt.name}: {evt.description} "
                    f"(Impact: {evt.event_type.value})"
                )
                try:
                    await self._env.step({
                        poster: [ManualAction(
                            action_type=ActionType.CREATE_POST,
                            action_args={"content": content},
                        )]
                    })
                except Exception:
                    logger.warning("イベント投稿失敗: %s", evt.name)
                event_msgs.append(f"{evt.name}: {evt.description}")

        return event_msgs

    def _extract_round_actions(self, round_number: int) -> list[dict[str, Any]]:
        """OASISのSQLiteからこのラウンドのアクションを抽出する.

        traceテーブルから最新のアクションを取得し、
        EchoShoalのアクション形式に変換する。
        """
        if not self._db_path:
            return []

        actions = []
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # traceテーブルから最新のアクションを取得
            # ラウンドごとのオフセットは、各ラウンドのアクション数から推定
            cursor.execute(
                "SELECT t.user_id, t.action, t.info, t.created_at, u.name "
                "FROM trace t "
                "LEFT JOIN user u ON t.user_id = u.user_id "
                "ORDER BY t.created_at DESC "
                "LIMIT ?",
                (len(self._oasis_agents) * 3,),  # 最大3アクション/エージェント
            )

            # エージェントIDマッピング（OASIS agent_id -> EchoShoal agent_id）
            id_map = {}
            for es_id, oasis_agent in self._oasis_agents.items():
                id_map[oasis_agent.agent_id] = es_id

            for row in cursor.fetchall():
                oasis_action = row["action"]
                agent_name = row["name"] or f"Agent_{row['user_id']}"
                es_agent_id = id_map.get(row["user_id"], "")

                # OASISアクション → EchoShoalアクション形式に変換
                action_record = {
                    "agent": agent_name,
                    "agent_id": es_agent_id,
                    "type": _map_oasis_action(oasis_action),
                    "description": str(row["info"])[:200] if row["info"] else "",
                    "oasis_action": oasis_action,
                    "visibility": "public",
                    "round_number": round_number,
                    "reputation": 0.5,
                }

                # 投稿/コメント内容を取得
                if oasis_action in ("create_post", "CREATE_POST"):
                    content = self._get_latest_post_content(conn, row["user_id"])
                    if content:
                        action_record["description"] = content[:200]

                elif oasis_action in ("create_comment", "CREATE_COMMENT"):
                    content = self._get_latest_comment_content(conn, row["user_id"])
                    if content:
                        action_record["description"] = content[:200]

                actions.append(action_record)

            conn.close()

        except Exception:
            logger.warning("OASISアクション抽出失敗: round=%d", round_number)

        return actions

    @staticmethod
    def _get_latest_post_content(conn: sqlite3.Connection, user_id: int) -> str:
        """ユーザーの最新投稿内容を取得する."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM post WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        return row["content"] if row else ""

    @staticmethod
    def _get_latest_comment_content(conn: sqlite3.Connection, user_id: int) -> str:
        """ユーザーの最新コメント内容を取得する."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM comment WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        return row["content"] if row else ""

    async def _update_market_from_actions(
        self, actions: list[dict[str, Any]], round_number: int
    ) -> None:
        """OASISアクションログから市場ディメンションを更新する.

        投稿内容・コメント・リポスト数からLLMが市場への影響を判断。
        """
        if not actions:
            return

        # アクションサマリー構築
        actions_summary = []
        for a in actions[:15]:
            actions_summary.append(
                f"- {a.get('agent', '?')}: [{a.get('oasis_action', a['type'])}] "
                f"{a.get('description', '')[:80]}"
            )
        actions_text = "\n".join(actions_summary)

        # インタラクション統計
        stats = self._get_interaction_stats()
        stats_text = (
            f"Total posts: {stats.get('posts', 0)}, "
            f"Comments: {stats.get('comments', 0)}, "
            f"Likes: {stats.get('likes', 0)}, "
            f"Follows: {stats.get('follows', 0)}"
        )

        current_dims = {d.value: round(v, 3) for d, v in self.market.dimensions.items()}

        prompt = (
            f"Round {round_number}. Service: {self.market.service_name}\n"
            f"Current dimensions: {current_dims}\n"
            f"Platform activity:\n{actions_text}\n\n"
            f"Engagement stats: {stats_text}\n\n"
            "Based on the social media discussion and engagement patterns, "
            "estimate market dimension changes. High engagement = more awareness. "
            "Negative sentiment = higher risk. Competitor posts = higher competitive pressure.\n"
            "Return EXACTLY this JSON with delta values (-0.1 to +0.1):\n"
            '{"dimension_deltas": {'
            '"user_adoption": 0.0, "revenue_potential": 0.0, "tech_maturity": 0.0, '
            '"competitive_pressure": 0.0, "regulatory_risk": 0.0, "market_awareness": 0.0, '
            '"ecosystem_health": 0.0, "funding_climate": 0.0}, '
            '"macro_deltas": {"economic_sentiment": 0.0, "tech_hype_level": 0.0, '
            '"regulatory_pressure": 0.0, "ai_disruption_level": 0.0}}'
        )

        try:
            import json
            response = await self.llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=prompt,
                system_prompt=(
                    "あなたはSNS上の議論パターンからサービスの市場影響を分析するアナリストです。"
                    "投稿・コメント・いいね数の傾向から市場ディメンションの変化を推定してください。"
                ),
            )
            self._llm_call_count += 1

            # ディメンションdelta適用
            raw_dims = response.get("dimension_deltas", {})
            for dim_key, delta in raw_dims.items():
                try:
                    dim = MarketDimension(dim_key)
                    clamped_delta = max(-0.1, min(0.1, float(delta)))
                    self.market.dimensions[dim] = max(
                        0.0, min(1.0, self.market.dimensions[dim] + clamped_delta)
                    )
                except (ValueError, TypeError):
                    pass

            # マクロdelta適用
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
            logger.warning("OASIS市場更新失敗: round=%d", round_number)

    def _get_interaction_stats(self) -> dict[str, int]:
        """OASISのSQLiteからインタラクション統計を取得する."""
        if not self._db_path:
            return {}
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            stats = {}
            for table in ("post", "comment", "like", "follow"):
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
                    stats[f"{table}s"] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    stats[f"{table}s"] = 0

            conn.close()
            return stats
        except Exception:
            return {}

    async def _initialize_from_scenario(self, enriched: EnrichedScenario) -> None:
        """LLMにシナリオを渡し、市場初期状態を推定させる（既存エンジンと同一ロジック）."""
        prompt = (
            f"Service: {enriched.original.service_name or 'unknown'}\n"
            f"Scenario: {enriched.original.description[:500]}\n\n"
            "Estimate the INITIAL market state (0.0-1.0 scale) for this service.\n"
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

            raw_dims = response.get("dimensions", {})
            for dim in MarketDimension:
                if dim.value in raw_dims:
                    val = max(0.0, min(1.0, float(raw_dims[dim.value])))
                    self.market.dimensions[dim] = val

            for key in ("economic_sentiment", "tech_hype_level", "regulatory_pressure", "ai_disruption_level"):
                if key in response:
                    val = max(0.0, min(1.0, float(response[key])))
                    setattr(self.market, key, val)

            logger.info("OASISシミュレーション市場初期化完了")

        except Exception:
            logger.warning("LLM市場初期化失敗、デフォルト値を使用")

    async def _generate_round_narrative(
        self,
        round_number: int,
        actions: list[dict[str, Any]],
        events: list[str],
    ) -> str:
        """ラウンドのナラティブを生成する."""
        action_lines = []
        for a in actions[:8]:
            action_lines.append(
                f"- {a.get('agent', '?')}: {a.get('oasis_action', a['type'])} "
                f"({a.get('description', '')[:60]})"
            )
        actions_text = "\n".join(action_lines) if action_lines else "特になし"
        events_text = "\n".join(events) if events else "なし"

        prompt = (
            f"ラウンド{round_number}のSNS上の議論を1-2文で要約してください。\n"
            f"サービス名: {self.market.service_name}\n\n"
            f"SNSアクティビティ:\n{actions_text}\n\n"
            f"市場イベント:\n{events_text}\n\n"
            "短く端的に、市場への影響を含めてストーリーとして要約してください。テキストのみ。"
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

    async def _cleanup_oasis(self) -> None:
        """OASIS環境をクリーンアップする."""
        if self._env:
            try:
                await self._env.close()
            except Exception:
                logger.debug("OASIS環境クローズ失敗")

    def get_summary(self) -> dict[str, Any]:
        """シミュレーション結果のサマリーを返す（既存互換）."""
        # エージェントのto_summary()を使用
        agents_summary = [a.to_summary() for a in self.agents]

        # OASISのインタラクション統計を追加
        stats = self._get_interaction_stats()

        return {
            "total_rounds": len(self.results),
            "final_market": self.market.model_dump(),
            "agents": agents_summary,
            "llm_calls": self._llm_call_count,
            "oasis_stats": stats,
            "engine": "oasis",
        }

    def get_social_feed(self, limit: int = 50) -> list[dict[str, Any]]:
        """OASISのSNS投稿をフィード形式で取得する."""
        if not self._db_path:
            return []

        feed = []
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 投稿取得
            cursor.execute(
                "SELECT p.post_id, p.content, p.created_at, p.num_likes, "
                "       p.num_dislikes, p.num_shares, u.name AS author "
                "FROM post p "
                "LEFT JOIN user u ON p.user_id = u.user_id "
                "WHERE p.content IS NOT NULL AND p.content != '' "
                "ORDER BY p.created_at DESC "
                "LIMIT ?",
                (limit,),
            )
            for row in cursor.fetchall():
                post = {
                    "id": f"post_{row['post_id']}",
                    "type": "post",
                    "author": row["author"] or "Unknown",
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "likes": row["num_likes"],
                    "dislikes": row["num_dislikes"],
                    "shares": row["num_shares"],
                    "comments": [],
                }

                # コメント取得
                cursor.execute(
                    "SELECT c.content, c.created_at, c.num_likes, u.name AS author "
                    "FROM comment c "
                    "LEFT JOIN user u ON c.user_id = u.user_id "
                    "WHERE c.post_id = ? "
                    "ORDER BY c.created_at ASC "
                    "LIMIT 10",
                    (row["post_id"],),
                )
                for comment_row in cursor.fetchall():
                    post["comments"].append({
                        "author": comment_row["author"] or "Unknown",
                        "content": comment_row["content"],
                        "created_at": comment_row["created_at"],
                        "likes": comment_row["num_likes"],
                    })

                feed.append(post)

            conn.close()
        except Exception:
            logger.warning("SNSフィード取得失敗")

        return feed


def _map_oasis_action(oasis_action: str) -> str:
    """OASISアクション名をEchoShoalのアクション名に変換する."""
    mapping = {
        "create_post": "post_opinion",
        "CREATE_POST": "post_opinion",
        "create_comment": "comment",
        "CREATE_COMMENT": "comment",
        "like_post": "endorse",
        "LIKE_POST": "endorse",
        "dislike_post": "critique",
        "DISLIKE_POST": "critique",
        "repost": "amplify",
        "REPOST": "amplify",
        "quote_post": "quote_opinion",
        "QUOTE_POST": "quote_opinion",
        "follow": "follow_stakeholder",
        "FOLLOW": "follow_stakeholder",
        "unfollow": "unfollow",
        "UNFOLLOW": "unfollow",
        "search_posts": "market_research",
        "SEARCH_POSTS": "market_research",
        "do_nothing": "observe",
        "DO_NOTHING": "observe",
    }
    return mapping.get(oasis_action, oasis_action)
