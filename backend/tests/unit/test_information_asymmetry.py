"""情報非対称性のユニットテスト.

OASISエンジンのインメモリ可視性フィルタリングが正しく動作することを検証する。
"""

import pytest

from app.core.graph.agent_memory import get_visibility
from app.oasis import simulation_runner


def _setup_module_state():
    """テスト用にモジュールレベルの状態をセットアップする."""
    simulation_runner._active_oasis_agent_map = {
        1: "大手企業A",
        2: "投資家B",
        3: "フリーランスC",
        4: "大手企業D",
        5: "エンドユーザーE",
    }
    simulation_runner._active_agent_type_map = {
        1: "enterprise",
        2: "investor",
        3: "freelancer",
        4: "enterprise",
        5: "end_user",
    }
    simulation_runner._active_action_history = [
        # public: 全員に見える
        {
            "agent_name": "大手企業A", "agent_id": "es1", "agent_type": "enterprise",
            "type": "adopt_service", "description": "サービス採用を決定",
            "visibility": "public", "round": 1,
        },
        # partial (enterprise): 企業エージェントのみに見える
        {
            "agent_name": "大手企業D", "agent_id": "es4", "agent_type": "enterprise",
            "type": "invest_rd", "description": "R&D投資を実施",
            "visibility": "partial", "round": 1,
        },
        # partial (investor): 投資家のみに見える
        {
            "agent_name": "投資家B", "agent_id": "es2", "agent_type": "investor",
            "type": "divest", "description": "投資撤退を検討",
            "visibility": "partial", "round": 2,
        },
        # private: 本人のみに見える
        {
            "agent_name": "フリーランスC", "agent_id": "es3", "agent_type": "freelancer",
            "type": "reject_service", "description": "不採用と判断",
            "visibility": "private", "round": 2,
        },
        # public: 全員に見える
        {
            "agent_name": "エンドユーザーE", "agent_id": "es5", "agent_type": "end_user",
            "type": "trial", "description": "トライアル開始",
            "visibility": "public", "round": 2,
        },
    ]


def _teardown_module_state():
    """テスト後にモジュールレベルの状態をクリアする."""
    simulation_runner._active_oasis_agent_map = {}
    simulation_runner._active_agent_type_map = {}
    simulation_runner._active_action_history = []
    simulation_runner._active_agent_contexts = {}


class TestBuildPerAgentContexts:
    """_build_per_agent_contexts のテスト."""

    def setup_method(self):
        _setup_module_state()

    def teardown_method(self):
        _teardown_module_state()

    def test_enterprise_sees_public_and_enterprise_partial(self):
        """企業エージェントはpublic + 企業のpartialが見える."""
        contexts = simulation_runner._build_per_agent_contexts()
        ctx = contexts.get(1, "")  # 大手企業A (oasis_id=1)

        # public: 他社のadopt_service, trial が見える
        assert "エンドユーザーE" in ctx
        assert "trial" in ctx
        # partial (enterprise): 大手企業DのR&D投資が見える
        assert "大手企業D" in ctx
        assert "invest_rd" in ctx
        # partial (investor): 投資家Bのdivestは見えない
        assert "divest" not in ctx
        # private: フリーランスCのreject_serviceは見えない
        assert "reject_service" not in ctx

    def test_investor_sees_public_and_investor_partial(self):
        """投資家エージェントはpublic + 投資家のpartialが見える."""
        contexts = simulation_runner._build_per_agent_contexts()
        ctx = contexts.get(2, "")  # 投資家B (oasis_id=2)

        # public: 全員のpublicアクションが見える
        assert "大手企業A" in ctx
        assert "adopt_service" in ctx
        # partial (investor): 自分のdivestは「あなたの直近の行動」として見える
        assert "divest" in ctx
        # partial (enterprise): 大手企業DのR&D投資は見えない
        assert "invest_rd" not in ctx
        # private: フリーランスCの不採用は見えない
        assert "reject_service" not in ctx

    def test_freelancer_sees_own_private(self):
        """フリーランスは自分のprivateアクションが見える."""
        contexts = simulation_runner._build_per_agent_contexts()
        ctx = contexts.get(3, "")  # フリーランスC (oasis_id=3)

        # 自分のprivateアクション: 見える（あなたの直近の行動）
        assert "reject_service" in ctx
        # public: 他者のpublicアクションが見える
        assert "大手企業A" in ctx
        # partial (enterprise): 企業のpartialは見えない
        assert "invest_rd" not in ctx

    def test_end_user_sees_only_public_and_own(self):
        """エンドユーザーはpublicと自分のアクションのみ見える."""
        contexts = simulation_runner._build_per_agent_contexts()
        ctx = contexts.get(5, "")  # エンドユーザーE (oasis_id=5)

        # public: 大手企業Aのadopt_serviceが見える
        assert "大手企業A" in ctx
        assert "adopt_service" in ctx
        # partial (enterprise/investor): 見えない
        assert "invest_rd" not in ctx
        assert "divest" not in ctx
        # private: 見えない
        assert "reject_service" not in ctx

    def test_same_type_enterprise_sees_partial(self):
        """同じ企業タイプのエージェントはpartialが共有される."""
        contexts = simulation_runner._build_per_agent_contexts()
        # 大手企業D (oasis_id=4) は企業A のpublicアクションが見える
        ctx = contexts.get(4, "")
        assert "大手企業A" in ctx
        assert "adopt_service" in ctx
        # 自分のpartial (invest_rd) は「あなたの直近の行動」として見える
        assert "invest_rd" in ctx

    def test_empty_history_returns_empty(self):
        """行動履歴が空の場合は空のコンテキストを返す."""
        simulation_runner._active_action_history = []
        contexts = simulation_runner._build_per_agent_contexts()
        assert contexts == {}


class TestRecordActionsToHistory:
    """_record_actions_to_history のテスト."""

    def setup_method(self):
        simulation_runner._active_action_history = []

    def teardown_method(self):
        simulation_runner._active_action_history = []

    def test_records_with_correct_visibility(self):
        """ACTION_VISIBILITYに基づいて正しい可視性が設定される."""
        from unittest.mock import MagicMock

        # ダミーのEchoShoalエージェント
        agent = MagicMock()
        agent.id = "es1"
        agent.profile.stakeholder_type.value = "enterprise"

        round_actions = [
            {"agent": "A社", "agent_id": "es1", "type": "adopt_service",
             "description": "採用", "round_number": 1},
            {"agent": "A社", "agent_id": "es1", "type": "invest_rd",
             "description": "R&D", "round_number": 1},
            {"agent": "A社", "agent_id": "es1", "type": "reject_service",
             "description": "不採用", "round_number": 1},
            {"agent": "A社", "agent_id": "es1", "type": "post_opinion",
             "description": "意見投稿", "round_number": 1},
        ]

        simulation_runner._record_actions_to_history(round_actions, [agent])

        history = simulation_runner._active_action_history
        assert len(history) == 4
        assert history[0]["visibility"] == "public"     # adopt_service
        assert history[1]["visibility"] == "partial"     # invest_rd
        assert history[2]["visibility"] == "private"     # reject_service
        assert history[3]["visibility"] == "public"      # post_opinion (unknown → default public)

    def test_records_agent_type(self):
        """エージェントのステークホルダータイプが記録される."""
        from unittest.mock import MagicMock

        agent = MagicMock()
        agent.id = "es1"
        agent.profile.stakeholder_type.value = "investor"

        round_actions = [
            {"agent": "VC", "agent_id": "es1", "type": "invest_seed",
             "description": "投資", "round_number": 1},
        ]

        simulation_runner._record_actions_to_history(round_actions, [agent])

        assert simulation_runner._active_action_history[0]["agent_type"] == "investor"


class TestGetVisibilityForOasisActions:
    """OASIS固有アクションのデフォルト可視性テスト."""

    def test_oasis_actions_default_to_public(self):
        """OASIS固有のSNSアクションはACTION_VISIBILITYに未定義→publicにフォールバック."""
        assert get_visibility("post_opinion") == "public"
        assert get_visibility("comment") == "public"
        assert get_visibility("amplify") == "public"
        assert get_visibility("quote_opinion") == "public"
        assert get_visibility("follow_stakeholder") == "public"

    def test_strategic_actions_have_explicit_visibility(self):
        """戦略的アクションはACTION_VISIBILITYに明示的に定義されている."""
        assert get_visibility("invest_rd") == "partial"
        assert get_visibility("divest") == "partial"
        assert get_visibility("reject_service") == "private"
        assert get_visibility("adopt_service") == "public"


class TestBuildInterpolatedContext:
    """_build_interpolated_context のテスト."""

    def test_with_full_interpolated_info(self):
        """補間情報がすべて揃っている場合のコンテキスト構築."""
        from unittest.mock import MagicMock
        enriched = MagicMock()
        enriched.interpolated_info.competitors = ["Slack", "Teams"]
        enriched.interpolated_info.revenue_model = "SaaS月額制"
        enriched.interpolated_info.target_users = "中小企業"
        enriched.interpolated_info.market_size_estimate = "500億円"
        enriched.interpolated_info.price_range = "月額1000〜5000円"
        enriched.interpolated_info.tech_stack = "React + Node.js"
        enriched.interpolated_info.team_size_estimate = "5-10名"

        ctx = simulation_runner._build_interpolated_context(enriched)
        assert "Slack" in ctx
        assert "SaaS月額制" in ctx
        assert "500億円" in ctx
        assert "【市場分析情報（LLM推定）】" in ctx

    def test_with_no_enriched(self):
        """enrichedがNoneの場合は空文字."""
        assert simulation_runner._build_interpolated_context(None) == ""

    def test_with_empty_info(self):
        """補間情報がすべて空の場合は空文字."""
        from unittest.mock import MagicMock
        enriched = MagicMock()
        enriched.interpolated_info.competitors = []
        enriched.interpolated_info.revenue_model = ""
        enriched.interpolated_info.target_users = ""
        enriched.interpolated_info.market_size_estimate = ""
        enriched.interpolated_info.price_range = ""
        enriched.interpolated_info.tech_stack = ""
        enriched.interpolated_info.team_size_estimate = ""

        assert simulation_runner._build_interpolated_context(enriched) == ""


class TestSharedKnowledgeInContext:
    """共有知識がエージェントコンテキストに含まれるかのテスト."""

    def setup_method(self):
        _setup_module_state()

    def teardown_method(self):
        _teardown_module_state()

    def test_shared_knowledge_injected_to_all_agents(self):
        """GraphRAG共有知識が全エージェントのコンテキストに含まれる."""
        simulation_runner._active_shared_knowledge = "【参考資料の要約】\nSlackは2014年に急成長した"
        contexts = simulation_runner._build_per_agent_contexts()
        for oasis_id in simulation_runner._active_agent_type_map:
            assert "Slackは2014年に急成長した" in contexts.get(oasis_id, "")

    def test_empty_shared_knowledge_no_effect(self):
        """共有知識が空の場合は影響なし."""
        simulation_runner._active_shared_knowledge = ""
        contexts = simulation_runner._build_per_agent_contexts()
        for ctx in contexts.values():
            assert "参考資料" not in ctx
