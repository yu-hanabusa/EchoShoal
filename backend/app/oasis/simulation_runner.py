"""OASIS シミュレーションエンジン — SNS空間でのエージェント間インタラクション.

OASISフレームワークを使用して、エージェントがReddit/Twitter的なSNS空間で
投稿・コメント・リポスト・フォローを通じてインタラクションする。
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

# OASIS エージェント会話のトークン使用量を収集するためのモジュールレベル参照
# シミュレーション実行中にセットされ、_jp_perform_action から参照される
_active_token_tracker: Any | None = None
_active_oasis_agent_map: dict[int, str] = {}  # OASIS agent_id -> agent name
_active_round_number: int = 0


def _truncate_at_sentence(text: str, max_len: int = 500) -> str:
    """文末（。！？!?）で区切って切り詰める。区切りがなければmax_lenで切る。"""
    if len(text) <= max_len:
        return text
    # max_len以内で最後の文末記号を探す
    for i in range(max_len - 1, -1, -1):
        if text[i] in "。！？!?\n":
            return text[: i + 1]
    # 文末記号が見つからなければmax_lenで切る
    return text[:max_len]


class OASISSimulationEngine:
    """OASISベースのシミュレーションエンジン.

    run() と get_summary() インターフェースで、
    OASIS環境を使用してエージェント間のSNSインタラクションを実行する。
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
        self._initial_relationships: list[dict[str, Any]] = []

        # OASIS環境（run()で初期化）
        self._env = None
        self._agent_graph = None
        self._oasis_agents: dict[str, Any] = {}  # agent.id -> SocialAgent
        self._db_path = ""
        self._round_post_ranges: list[tuple[int, int]] = []  # (first_post_id, last_post_id) per round
        self._last_known_post_id: int = 0
        self._last_known_trace_count: int = 0  # traceテーブルの既知件数（ラウンド区切り用）
        self._prev_engagement_stats: dict[str, int] | None = None  # 前ラウンドのエンゲージメント統計
        self._finance_summary: str = ""  # 市場調査の財務データ要約（market_analyzer用）

    async def run(self, num_rounds: int | None = None) -> list[RoundResult]:
        """OASIS環境でシミュレーションを実行する."""
        global _active_token_tracker, _active_oasis_agent_map, _active_round_number

        rounds = num_rounds or (self.scenario.num_rounds if self.scenario else settings.default_rounds)
        rounds = min(rounds, settings.max_rounds)

        logger.info("OASISシミュレーション開始: %dラウンド, %dエージェント", rounds, len(self.agents))

        # トークントラッカーをモジュールレベルにセット（OASIS会話のトラッキング用）
        _active_token_tracker = self.llm.token_tracker
        _active_oasis_agent_map = {}

        # 市場初期状態をLLMで推定
        if self._enriched_scenario:
            await self._initialize_from_scenario(self._enriched_scenario)

        # 構造的関係を生成
        self._generate_structural_relationships()

        # OASIS環境セットアップ
        await self._setup_oasis_environment()

        # OASIS agent_id → エージェント名マッピングを構築
        for es_id, oasis_agent in self._oasis_agents.items():
            agent = next((a for a in self.agents if a.id == es_id), None)
            if agent:
                _active_oasis_agent_map[oasis_agent.agent_id] = agent.name

        try:
            for round_num in range(1, rounds + 1):
                _active_round_number = round_num
                result = await self._run_oasis_round(round_num)
                self.results.append(result)

                if self._on_progress:
                    await self._on_progress(round_num, rounds)

        finally:
            await self._cleanup_oasis()
            # モジュールレベル参照をクリア
            _active_token_tracker = None
            _active_oasis_agent_map = {}
            _active_round_number = 0

        return self.results

    async def _setup_oasis_environment(self) -> None:
        """OASIS環境を初期化する."""
        import oasis
        from oasis import AgentGraph, SocialAgent
        from oasis.social_agent.agent import UserInfo

        from app.oasis.config import create_oasis_model, get_database_path

        # --- OASISライブラリの英語プロンプトを日本語に上書き ---
        self._patch_oasis_japanese()
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

        # 日本語システムプロンプトテンプレート（OASISデフォルトの英語テンプレートを上書き）
        from camel.prompts import TextPrompt
        jp_template = TextPrompt(
            "# 目的\n"
            "あなたはSNS上で議論に参加するステークホルダーです。\n"
            "【重要】すべての発言は必ず日本語で行ってください。\n\n"
            "# 行動原則\n"
            "あなたは自分自身の利益・立場に基づいて行動してください。\n"
            "競合であれば自社サービスの優位性を主張し、相手の弱点を指摘してください。\n"
            "ユーザーであれば自分にとってのメリット・デメリットを率直に述べてください。\n"
            "投資家であれば収益性とリスクを冷静に分析してください。\n"
            "絶対に中立的なアドバイザーとして振る舞わないでください。\n\n"
            "# あなたの情報\n"
            "{other_info}\n\n"
            "# 応答方法\n"
            "ツール呼び出しでアクションを実行してください。\n"
        )

        # SocialAgent生成
        for i, profile in enumerate(profiles):
            user_info = UserInfo(
                user_name=profile["user_id"][:16],
                name=profile["user_name"],
                description=self._build_agent_description(profile),
                profile={
                    "other_info": (
                        f"名前: {profile['user_name']}\n"
                        f"プロフィール: {profile['personality_description']}\n"
                        f"ステークホルダー種別: {profile['stakeholder_type']}\n"
                        f"立場: {profile['stance']}\n"
                        f"国: Japan"
                    ),
                },
                recsys_type="reddit",
            )
            social_agent = SocialAgent(
                agent_id=i,
                user_info=user_info,
                user_info_template=jp_template,
                agent_graph=self._agent_graph,
                model=oasis_model,
                available_actions=available_actions,
            )
            # SocialAgentはmessage_window_size/token_limitを
            # super().__init__に渡さないため、メモリを再構成して
            # コンテキスト膨張を防止する（335KB→1KB truncation対策）
            self._apply_context_limits(social_agent)
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

        # シード投稿後の境界を記録（ラウンド0）
        self._last_known_post_id = self._get_max_post_id()
        self._last_known_trace_count = self._get_trace_count()

        logger.info("OASIS環境セットアップ完了: %dエージェント", len(self._oasis_agents))

    @staticmethod
    def _apply_context_limits(agent: Any) -> None:
        """SocialAgentのメモリにコンテキスト制限を適用する.

        OASIS SocialAgentはmessage_window_size/token_limitを
        ChatAgent.__init__に渡さないため、初期化後にメモリを再構成する。
        これによりラウンド進行時のコンテキスト膨張（335KB→truncation）を防止する。
        """
        from camel.memories import ChatHistoryMemory, ScoreBasedContextCreator

        context_creator = ScoreBasedContextCreator(
            agent.model_backend.token_counter,
            settings.oasis_context_token_limit,
        )
        agent._memory = ChatHistoryMemory(
            context_creator,
            window_size=settings.oasis_message_window_size,
            agent_id=agent.agent_id,
        )

    @staticmethod
    def _patch_oasis_japanese() -> None:
        """OASISライブラリの英語テンプレートを日本語に上書きする."""
        from string import Template as StdTemplate

        from oasis.social_agent.agent_environment import SocialEnvironment

        SocialEnvironment.followers_env_template = StdTemplate(
            "フォロワー数: $num_followers人"
        )
        SocialEnvironment.follows_env_template = StdTemplate(
            "フォロー数: $num_follows人"
        )
        SocialEnvironment.posts_env_template = StdTemplate(
            "タイムラインに以下の投稿があります: $posts"
        )
        SocialEnvironment.groups_env_template = StdTemplate(
            "グループチャンネル一覧: $all_groups\n"
            "参加済みグループ: $joined_groups\n"
            "受信メッセージ: $messages\n"
            "参加済みのグループにのみメッセージを送信できます。"
        )
        SocialEnvironment.env_template = StdTemplate(
            "$groups_env\n"
            "$posts_env\n"
            "あなたのプロフィールと投稿内容に基づいて、"
            "最も適切なアクションを選んでください。"
            "「いいね」だけでなく、投稿やコメントも積極的に行ってください。"
            "【重要】すべての発言は必ず日本語で行ってください。"
        )

        # perform_action_by_llm のユーザーメッセージを日本語化
        import oasis.social_agent.agent as agent_module
        from camel.messages import BaseMessage

        async def _jp_perform_action(self: Any) -> Any:  # type: ignore[override]
            from oasis.social_agent.agent import ALL_SOCIAL_ACTIONS, agent_log

            env_prompt = await self.env.to_text_prompt()
            user_msg = BaseMessage.make_user_message(
                role_name="User",
                content=(
                    f"SNSの環境を観察して、適切なアクションを実行してください。"
                    f"「いいね」だけでなく、投稿・コメント・リポストなど"
                    f"多様なアクションを行ってください。"
                    f"【重要】すべての発言は必ず日本語で行ってください。"
                    f"\n\n現在のSNS環境:\n{env_prompt}"
                ),
            )
            try:
                agent_log.info(
                    f"Agent {self.social_agent_id} observing environment: "
                    f"{env_prompt}"
                )
                response = await self.astep(user_msg)

                # トークン使用量をトラッカーに記録
                if _active_token_tracker is not None:
                    usage_dict = response.info.get("usage") or {}
                    if usage_dict:
                        from app.core.llm.token_tracker import TokenUsage
                        from app.config import settings as _settings
                        agent_name = _active_oasis_agent_map.get(
                            self.social_agent_id, f"oasis_agent_{self.social_agent_id}"
                        )
                        usage = TokenUsage(
                            input_tokens=usage_dict.get("prompt_tokens", 0),
                            output_tokens=usage_dict.get("completion_tokens", 0),
                            provider="ollama",
                            model=_settings.ollama_model,
                        )
                        _active_token_tracker.record(
                            usage=usage,
                            task_type="oasis_conversation",
                            round_number=_active_round_number,
                            agent_name=agent_name,
                        )

                for tool_call in response.info["tool_calls"]:
                    action_name = tool_call.tool_name
                    args = tool_call.args
                    agent_log.info(
                        f"Agent {self.social_agent_id} performed "
                        f"action: {action_name} with args: {args}"
                    )
                    if action_name not in ALL_SOCIAL_ACTIONS:
                        agent_log.info(
                            f"Agent {self.social_agent_id} get the result: "
                            f"{tool_call.result}"
                        )
                    return response
            except Exception as e:
                agent_log.error(f"Agent {self.social_agent_id} error: {e}")
                return e

        agent_module.SocialAgent.perform_action_by_llm = _jp_perform_action  # type: ignore[assignment]

    def _build_agent_description(self, profile: dict[str, Any]) -> str:
        """OASISエージェントの説明文を構築する."""
        st = profile['stakeholder_type']
        name = profile['user_name']
        bio = profile['bio']
        parts = [
            f"【あなたの正体】あなたは「{name}」です。「{name}」以外の何者でもありません。",
            f"【言語】すべての発言は必ず日本語で行ってください。",
            f"【プロフィール】{bio}",
            f"【立場】{profile['stance']}",
        ]
        if self.scenario:
            sn = self.scenario.service_name
            parts.append(
                f"【議論の背景】新サービス「{sn}」が市場に参入しようとしています。"
                f"あなたは「{name}」の立場からこれについて議論してください。"
            )

            # 主人公（対象サービス）の場合
            if name == sn:
                parts.append(
                    f"あなたは「{sn}」の運営チームです。"
                    "市場の変化、競合の動き、ユーザーの声に応じて能動的に戦略を決定してください。"
                    "価格改定、新機能リリース、マーケティング強化、提携、資金調達など、"
                    "自社の成長のためにあらゆる手段を検討してください。"
                )
            # 種別ごとの行動指針（名前と説明を使って具体的に）
            elif st in ("platformer", "enterprise"):
                parts.append(
                    f"【重要】あなたは「{name}」の関係者です。「{sn}」の関係者ではありません。\n"
                    f"「{name}」の強みや優位性を具体的に主張し、「{sn}」の弱点を指摘してください。\n"
                    f"「{sn}」を推薦したり、「{sn}」の機能を解説することは絶対にしないでください。\n"
                    f"「{sn}」について聞かれたら「{name}」と比較して「{name}」が優れている点を述べてください。"
                )
            elif st == "end_user":
                parts.append(
                    f"あなたは「{name}」を代表するユーザーです。"
                    f"「{sn}」の使い勝手、価格、セキュリティなどを"
                    "自分たちの立場から率直に評価してください。"
                    "既存ツールとの比較、乗り換えコスト、不満や期待を具体的に述べてください。"
                )
            elif st == "investor":
                parts.append(
                    f"あなたは投資家「{name}」です。"
                    f"「{sn}」の収益性、市場規模、成長性、競合優位性を"
                    "冷静に分析してください。投資リスクも指摘してください。"
                )
            elif st == "government":
                parts.append(
                    f"あなたは「{name}」の立場です。"
                    "規制適合性、セキュリティ基準、公共調達の観点からコメントしてください。"
                )
            elif st == "community":
                parts.append(
                    f"あなたは「{name}」のメンバーです。"
                    "業界全体の動向、技術トレンド、コミュニティの意見を共有してください。"
                )
        return "\n".join(parts)

    async def _inject_seed_posts(self) -> None:
        """シナリオに基づくシード投稿を注入する."""
        from oasis.social_platform.typing import ActionType

        if not self.scenario or not self._env:
            return

        # 多様な視点のシード投稿（5件: 情報、ユーザー、投資、競合、技術）
        sn = self.scenario.service_name
        oasis_agents = list(self._oasis_agents.values())
        seed_agents = oasis_agents[:min(5, len(oasis_agents))]

        seed_topics = [
            f"【新サービス情報】「{sn}」が市場に参入します。"
            f"概要: {_truncate_at_sentence(self.scenario.description, 500)}",
            f"【ユーザー視点】「{sn}」を実際に使ってみた感想を共有しましょう。"
            "使い勝手、価格、既存ツールとの比較、乗り換えコストなど率直な意見をお願いします。",
            f"【投資・ビジネス視点】「{sn}」の収益モデルと成長性について議論しましょう。"
            "市場規模、競合優位性、資金調達状況、収益化の見通しはどうでしょうか。",
            f"【競合分析】「{sn}」と既存サービスを比較して、どちらが優れているか議論しましょう。"
            "各サービスの強み・弱み、ユーザーにとっての選択基準は何でしょうか。",
            f"【技術・エコシステム】「{sn}」の技術基盤やサードパーティ連携について議論しましょう。"
            "API公開、プラグイン、他サービスとの統合性はどうでしょうか。",
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
                events.append(f"{round_number}ヶ月目: OASISステップ実行失敗")

        # SQLiteからこのラウンドのアクションを取得（traceオフセットで現ラウンド分のみ）
        new_trace_count = self._get_trace_count()
        round_trace_count = new_trace_count - self._last_known_trace_count
        round_actions = self._extract_round_actions(round_number, round_trace_count)
        self._last_known_trace_count = new_trace_count
        all_actions.extend(round_actions)

        # SNS議論内容から市場ディメンションを更新（アクション0件でも投稿があれば実行）
        await self._update_market_from_actions(round_actions, round_number)

        # 外部イベント効果を適用
        if self._event_scheduler:
            event_effects = apply_active_events(
                self._event_scheduler.events, round_number, self.market
            )
            events.extend(event_effects)

        # ラウンドのpost_id範囲を記録
        new_max = self._get_max_post_id()
        self._round_post_ranges.append((self._last_known_post_id + 1, new_max))
        self._last_known_post_id = new_max

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

    def _get_max_post_id(self) -> int:
        """OASISのSQLiteから最大post_idを取得する."""
        if not self._db_path:
            return 0
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(post_id) FROM post")
            row = cursor.fetchone()
            conn.close()
            return row[0] or 0
        except Exception:
            return 0

    def _get_trace_count(self) -> int:
        """OASISのSQLiteからtrace件数を取得する."""
        if not self._db_path:
            return 0
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trace")
            row = cursor.fetchone()
            conn.close()
            return row[0] or 0
        except Exception:
            return 0

    def _post_id_to_round(self, post_id: int) -> int | None:
        """post_idからラウンド番号を推定する."""
        if not self._round_post_ranges:
            return None
        for i, (start, end) in enumerate(self._round_post_ranges):
            if start <= post_id <= end:
                return i + 1
        # シード投稿（ラウンド0 = セットアップ時の投稿）
        if self._round_post_ranges and post_id < self._round_post_ranges[0][0]:
            return 0
        # 最終ラウンド以降
        return len(self._round_post_ranges)

    @staticmethod
    def _apply_soft_boundary_delta(current: float, raw_delta: float, max_abs_delta: float) -> float:
        """ソフトバウンダリ付きdelta適用.

        delta × 境界までの距離 で自然に減衰する。
        恣意的な係数ではなく、「残り距離の比率だけ動く」幾何学的制約。
        0.9にいるとき+0.1 → effective = 0.1 × 0.1 = 0.01（ほぼ動かない）
        0.5にいるとき+0.1 → effective = 0.1 × 0.5 = 0.05（中程度）
        """
        clamped = max(-max_abs_delta, min(max_abs_delta, float(raw_delta)))
        if clamped > 0:
            effective = clamped * (1.0 - current)
        elif clamped < 0:
            effective = clamped * current
        else:
            return current
        return max(0.0, min(1.0, current + effective))

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
                content = f"【市場ニュース】{evt.name}: {evt.description}"
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

    # 市場に直接影響するコンテンツ系アクション
    _CONTENT_ACTIONS: frozenset[str] = frozenset({
        "create_post", "CREATE_POST",
        "create_comment", "CREATE_COMMENT",
        "like_post", "LIKE_POST",
        "dislike_post", "DISLIKE_POST",
        "repost", "REPOST",
        "quote_post", "QUOTE_POST",
        "follow", "FOLLOW",
        "unfollow", "UNFOLLOW",
    })

    def _extract_round_actions(self, round_number: int, trace_limit: int = 0) -> list[dict[str, Any]]:
        """OASISのSQLiteからこのラウンドのアクションを抽出する.

        trace_limit: このラウンドで追加されたtrace件数。
        0の場合はフォールバックとしてエージェント数×3件を取得。
        refresh/search_posts/trend等の非コンテンツアクションは除外する。
        """
        if not self._db_path:
            return []

        limit = trace_limit if trace_limit > 0 else len(self._oasis_agents) * 3

        actions = []
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # traceテーブルから最新N件（このラウンド分）を取得
            cursor.execute(
                "SELECT t.user_id, t.action, t.info, t.created_at, u.name "
                "FROM trace t "
                "LEFT JOIN user u ON t.user_id = u.user_id "
                "ORDER BY t.created_at DESC "
                "LIMIT ?",
                (limit,),
            )

            # エージェントIDマッピング（OASIS agent_id -> EchoShoal agent_id）
            id_map = {}
            for es_id, oasis_agent in self._oasis_agents.items():
                id_map[oasis_agent.agent_id] = es_id

            for row in cursor.fetchall():
                oasis_action = row["action"]

                # 非コンテンツアクション（refresh, search, trend等）を除外
                if oasis_action not in self._CONTENT_ACTIONS:
                    continue

                agent_name = row["name"] or f"Agent_{row['user_id']}"
                es_agent_id = id_map.get(row["user_id"], "")

                action_record = {
                    "agent": agent_name,
                    "agent_id": es_agent_id,
                    "type": _map_oasis_action(oasis_action),
                    "description": "",
                    "oasis_action": oasis_action,
                    "visibility": "public",
                    "round_number": round_number,
                }

                # 投稿/コメント内容を取得（現ラウンドのpost_id以降のみ）
                min_post_id = self._last_known_post_id + 1
                if oasis_action in ("create_post", "CREATE_POST"):
                    content = self._get_latest_post_content(conn, row["user_id"], min_post_id)
                    if content:
                        action_record["description"] = _truncate_at_sentence(content, 500)

                elif oasis_action in ("create_comment", "CREATE_COMMENT"):
                    content = self._get_latest_comment_content(conn, row["user_id"], min_post_id)
                    if content:
                        action_record["description"] = _truncate_at_sentence(content, 500)

                elif oasis_action in ("like_post", "LIKE_POST", "dislike_post", "DISLIKE_POST"):
                    action_record["description"] = _truncate_at_sentence(str(row["info"]), 200) if row["info"] else "post"

                elif oasis_action in ("follow", "FOLLOW", "unfollow", "UNFOLLOW"):
                    action_record["description"] = _truncate_at_sentence(str(row["info"]), 200) if row["info"] else "user"

                elif oasis_action in ("repost", "REPOST", "quote_post", "QUOTE_POST"):
                    action_record["description"] = _truncate_at_sentence(str(row["info"]), 500) if row["info"] else "post"

                # 空のdescriptionを除外
                if not action_record["description"].strip():
                    continue
                actions.append(action_record)

            conn.close()

        except Exception:
            logger.warning("OASISアクション抽出失敗: round=%d", round_number)

        return actions

    @staticmethod
    def _get_latest_post_content(conn: sqlite3.Connection, user_id: int, min_post_id: int = 0) -> str:
        """ユーザーの最新投稿内容を取得する.

        min_post_id > 0 の場合、そのID以降の投稿のみ対象（ラウンド絞り込み）。
        """
        cursor = conn.cursor()
        if min_post_id > 0:
            cursor.execute(
                "SELECT content FROM post WHERE user_id = ? AND post_id >= ? ORDER BY created_at DESC LIMIT 1",
                (user_id, min_post_id),
            )
        else:
            cursor.execute(
                "SELECT content FROM post WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            )
        row = cursor.fetchone()
        return row["content"] if row else ""

    @staticmethod
    def _get_latest_comment_content(conn: sqlite3.Connection, user_id: int, min_post_id: int = 0) -> str:
        """ユーザーの最新コメント内容を取得する.

        min_post_id > 0 の場合、そのID以降の投稿へのコメントのみ対象（ラウンド絞り込み）。
        """
        cursor = conn.cursor()
        if min_post_id > 0:
            cursor.execute(
                "SELECT c.content FROM comment c "
                "JOIN post p ON c.post_id = p.post_id "
                "WHERE c.user_id = ? AND p.post_id >= ? "
                "ORDER BY c.created_at DESC LIMIT 1",
                (user_id, min_post_id),
            )
        else:
            cursor.execute(
                "SELECT content FROM comment WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            )
        row = cursor.fetchone()
        return row["content"] if row else ""

    def _get_round_discussions(self, round_number: int) -> str:
        """そのラウンドの投稿・コメントテキストをSQLiteから取得する.

        post_idレンジを使って現ラウンドの投稿のみ取得し、
        発言者名付きのテキストとして返す。
        """
        if not self._db_path:
            return ""

        # 現ラウンドのpost_idレンジ
        min_post_id = self._last_known_post_id + 1
        # ラウンドのpost_id範囲がすでに記録されている場合はそれを使う
        if round_number <= len(self._round_post_ranges):
            rng = self._round_post_ranges[round_number - 1]
            min_post_id = rng[0]

        lines: list[str] = []
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # このラウンドの新規投稿を取得
            cursor.execute(
                "SELECT p.post_id, p.content, p.num_likes, p.num_dislikes, u.name "
                "FROM post p "
                "LEFT JOIN user u ON p.user_id = u.user_id "
                "WHERE p.post_id >= ? AND p.content IS NOT NULL AND p.content != '' "
                "ORDER BY p.post_id ASC LIMIT 20",
                (min_post_id,),
            )
            new_posts = cursor.fetchall()

            # 新規投稿がない場合、直近の累積投稿（いいね数上位）を取得
            if not new_posts:
                cursor.execute(
                    "SELECT p.post_id, p.content, p.num_likes, p.num_dislikes, u.name "
                    "FROM post p "
                    "LEFT JOIN user u ON p.user_id = u.user_id "
                    "WHERE p.content IS NOT NULL AND p.content != '' "
                    "ORDER BY p.num_likes DESC, p.post_id DESC LIMIT 10",
                )
                new_posts = cursor.fetchall()
                if new_posts:
                    lines.append("（このラウンドの新規投稿なし — 直近の注目投稿を参照）")

            for row in new_posts:
                author = row["name"] or "Unknown"
                content = _truncate_at_sentence(row["content"], 200)
                likes_info = ""
                if row["num_likes"] or row["num_dislikes"]:
                    likes_info = f" [+{row['num_likes']}/-{row['num_dislikes']}]"
                lines.append(f"[{author}]{likes_info}: {content}")

                # この投稿へのコメント
                cursor.execute(
                    "SELECT c.content, c.num_likes, u.name "
                    "FROM comment c "
                    "LEFT JOIN user u ON c.user_id = u.user_id "
                    "WHERE c.post_id = ? "
                    "ORDER BY c.created_at ASC LIMIT 5",
                    (row["post_id"],),
                )
                for comment in cursor.fetchall():
                    c_author = comment["name"] or "Unknown"
                    c_content = _truncate_at_sentence(comment["content"], 150)
                    lines.append(f"  └ [{c_author}]: {c_content}")

            conn.close()
        except Exception:
            logger.warning("ラウンド議論テキスト取得失敗: round=%d", round_number)

        return "\n".join(lines)

    async def _update_market_from_actions(
        self, actions: list[dict[str, Any]], round_number: int
    ) -> None:
        """SNS上の議論内容から市場ディメンションを更新する.

        アクション記録に加え、そのラウンドの投稿・コメントテキストを
        直接取得してLLMに渡す。全エージェントが同じ投稿を見ているため、
        投稿内容が市場の「世論」を反映する。
        """
        service_name = self.market.service_name

        # そのラウンドの議論テキストを取得
        discussions = self._get_round_discussions(round_number)

        # アクション統計
        action_types: dict[str, int] = {}
        for a in actions:
            t = a.get("oasis_action", a.get("type", "?"))
            action_types[t] = action_types.get(t, 0) + 1
        action_stats = ", ".join(f"{k}: {v}" for k, v in action_types.items()) if action_types else "なし"

        # インタラクション統計 + 前ラウンドとの変化率
        stats = self._get_interaction_stats()
        prev_stats = self._prev_engagement_stats or {}
        engagement_changes = []
        for key in ("posts", "comments", "likes", "follows"):
            current_val = stats.get(key, 0)
            prev_val = prev_stats.get(key, 0)
            delta = current_val - prev_val
            if delta != 0:
                engagement_changes.append(f"{key} {delta:+d}")
        engagement_delta_text = ", ".join(engagement_changes) if engagement_changes else "変化なし"
        self._prev_engagement_stats = dict(stats)

        stats_text = (
            f"Total posts: {stats.get('posts', 0)}, "
            f"Comments: {stats.get('comments', 0)}, "
            f"Likes: {stats.get('likes', 0)}, "
            f"Follows: {stats.get('follows', 0)}\n"
            f"Engagement change (前ラウンド比): {engagement_delta_text}"
        )

        current_dims = {d.value: round(v, 3) for d, v in self.market.dimensions.items()}

        # 直近のトレンド情報を構築（前ラウンドまでの推移）
        trend_lines = []
        if len(self.results) >= 2:
            prev_dims = {
                d.value: round(v, 3)
                for d, v in self.results[-1].market_state.dimensions.items()
            }
            first_dims = {
                d.value: round(v, 3)
                for d, v in self.results[0].market_state.dimensions.items()
            }
            for dim_name, current_val in current_dims.items():
                first_val = first_dims.get(dim_name, current_val)
                prev_val = prev_dims.get(dim_name, current_val)
                total_change = current_val - first_val
                recent_change = current_val - prev_val
                arrow = "↑" if total_change > 0.02 else "↓" if total_change < -0.02 else "→"
                trend_lines.append(
                    f"  {dim_name}: {first_val}→{current_val} ({arrow}{total_change:+.3f}), 前回比{recent_change:+.3f}"
                )
        trend_text = "\n".join(trend_lines) if trend_lines else "  （初回ラウンド、トレンドデータなし）"

        # 境界に近いディメンションをLLMに明示
        near_boundary = []
        for dim_name, val in current_dims.items():
            if val >= 0.85:
                near_boundary.append(f"  {dim_name}={val} (上限に近い — 大きなイベントなしでは上昇困難)")
            elif val <= 0.15:
                near_boundary.append(f"  {dim_name}={val} (下限に近い — 大きなイベントなしでは下降困難)")
        boundary_text = "\n".join(near_boundary) if near_boundary else "  なし"

        # 議論がなければスキップ
        if not discussions and not actions:
            return

        # 財務データ（funding_climate判断材料）
        finance_text = self._finance_summary if self._finance_summary else ""

        prompt = (
            f"Round {round_number}. Target service: {service_name}\n"
            f"Current dimensions: {current_dims}\n\n"
            f"Trend (開始→現在, 全体変化, 前回比):\n{trend_text}\n\n"
            f"=== SNS上の議論（このラウンドの投稿・コメント） ===\n"
            f"{discussions or '（このラウンドの新規投稿なし）'}\n\n"
            f"{finance_text}\n" if finance_text else ""
            f"Action stats: {action_stats}\n"
            f"Engagement stats: {stats_text}\n\n"
            f"Boundary awareness (極端な値のディメンション):\n{boundary_text}\n\n"
            "Rules:\n"
            f"- '{service_name}'の投稿 = 対象サービスのアクション。積極的な施策はuser_adoption, market_awarenessにプラス。\n"
            "- 競合の投稿 = competitive_pressureの上昇要因。批判的な意見はuser_adoptionにマイナス。\n"
            "- ユーザーの肯定的投稿 = user_adoption, ecosystem_healthにプラス。否定的 = マイナス。\n"
            "- 投資家の関心 = funding_climateにプラス。\n"
            "- 0.0/1.0に近いディメンションは、重大なイベントがない限りdelta≒0.0を返すこと。\n\n"
            "【重要】因果関係の注意:\n"
            "- 規制議論の活発化 ≠ ユーザー離脱。規制はregulatory_riskに反映し、user_adoptionには直接影響させない。\n"
            "  規制議論が盛んなのはむしろ市場が成長している証拠であることが多い。\n"
            "- Engagement change（いいね・コメント・フォローの増加）はユーザー関心の代理指標。\n"
            "  エンゲージメントが増加中ならuser_adoptionとmarket_awarenessにプラス。\n"
            "- 議論のトーンがネガティブでも、議論量が増えていれば市場関心は高まっている。\n\n"
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
                round_number=round_number,
                agent_name="market_analyzer",
            )
            self._llm_call_count += 1

            # ディメンションdelta適用（ソフトバウンダリ）
            raw_dims = response.get("dimension_deltas", {})
            for dim_key, delta in raw_dims.items():
                try:
                    dim = MarketDimension(dim_key)
                    self.market.dimensions[dim] = self._apply_soft_boundary_delta(
                        self.market.dimensions[dim], float(delta), 0.1,
                    )
                except (ValueError, TypeError):
                    pass

            # マクロdelta適用（ソフトバウンダリ）
            raw_macros = response.get("macro_deltas", {})
            for key in ("economic_sentiment", "tech_hype_level", "regulatory_pressure", "ai_disruption_level"):
                if key in raw_macros:
                    try:
                        current = getattr(self.market, key)
                        new_val = self._apply_soft_boundary_delta(
                            current, float(raw_macros[key]), 0.05,
                        )
                        setattr(self.market, key, new_val)
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
                round_number=0,
                agent_name="market_initializer",
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
                round_number=round_number,
                agent_name="narrator",
            )
        except Exception:
            return ""

    def _generate_structural_relationships(self) -> None:
        """ステークホルダー種別に基づく構造的な関係を生成する."""
        service = self.scenario.service_name if self.scenario else ""
        sn_lower = service.lower()

        target_agent = None
        for a in self.agents:
            if sn_lower and sn_lower in a.name.lower():
                target_agent = a.name
                break

        if not target_agent:
            return

        _type_map = {
            "platformer": "competitor", "enterprise": "competitor",
            "end_user": "user", "investor": "investor",
            "government": "regulator", "community": "interest",
            "freelancer": "interest", "indie_developer": "interest",
        }

        for a in self.agents:
            if a.name == target_agent:
                continue
            rel_type = _type_map.get(a.profile.stakeholder_type.value, "interest")
            self._initial_relationships.append({
                "from": a.name, "to": target_agent,
                "type": rel_type, "round": 0, "weight": 1,
            })
        logger.info("構造的関係%d件を生成", len(self._initial_relationships))

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

        # OASISのSNSインタラクションから関係エッジを構築
        oasis_relationships = self._extract_oasis_relationships()
        all_relationships = self._initial_relationships + oasis_relationships

        return {
            "total_rounds": len(self.results),
            "final_market": self.market.model_dump(),
            "agents": agents_summary,
            "llm_calls": self._llm_call_count,
            "oasis_stats": stats,
            "engine": "oasis",
            "initial_relationships": all_relationships,
            "token_usage": self.llm.token_tracker.get_summary(),
        }

    def _extract_oasis_relationships(self) -> list[dict[str, Any]]:
        """OASISのSQLiteからエージェント間インタラクションを関係エッジとして抽出する."""
        if not self._db_path:
            return []

        from app.oasis.graph_sync import extract_interactions
        try:
            edges = extract_interactions(self._db_path)
        except Exception:
            return []

        # OASIS user_id → EchoShoal agent名のマッピング
        id_to_name: dict[int, str] = {}
        for i, agent in enumerate(self.agents):
            id_to_name[i] = agent.name

        relationships: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for edge in edges:
            src_name = id_to_name.get(edge.source_id)
            tgt_name = id_to_name.get(edge.target_id)
            if not src_name or not tgt_name or src_name == tgt_name:
                continue
            if (src_name, tgt_name) in seen:
                continue

            relationships.append({
                "from": src_name,
                "to": tgt_name,
                "type": edge.relation_type,
                "round": 1,  # OASISインタラクションはラウンド情報なし
                "weight": edge.weight,
            })
            seen.add((src_name, tgt_name))

        return relationships

    def get_social_feed(self, limit: int = 0) -> list[dict[str, Any]]:
        """OASISのSNS投稿をフィード形式で取得する."""
        if not self._db_path:
            return []

        feed = []
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 投稿取得（limit=0 で全件）
            query = (
                "SELECT p.post_id, p.content, p.created_at, p.num_likes, "
                "       p.num_dislikes, p.num_shares, u.name AS author "
                "FROM post p "
                "LEFT JOIN user u ON p.user_id = u.user_id "
                "WHERE p.content IS NOT NULL AND p.content != '' "
                "ORDER BY p.created_at ASC"
            )
            if limit > 0:
                query += " LIMIT ?"
                cursor.execute(query, (limit,))
            else:
                cursor.execute(query)
            for row in cursor.fetchall():
                # post_idからラウンド番号を推定
                round_num = self._post_id_to_round(row["post_id"])

                post = {
                    "id": f"post_{row['post_id']}",
                    "type": "post",
                    "author": row["author"] or "Unknown",
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "round": round_num,
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
