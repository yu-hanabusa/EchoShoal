"""Tests for agent memory store (knowledge graph)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.graph.agent_memory import (
    ACTION_VISIBILITY,
    AgentMemoryStore,
    get_visibility,
)


class TestGetVisibility:
    def test_public_actions(self):
        assert get_visibility("adopt_service") == "public"
        assert get_visibility("build_competitor") == "public"
        assert get_visibility("acquire_startup") == "public"
        assert get_visibility("adopt_tool") == "public"
        assert get_visibility("launch_competing_product") == "public"
        assert get_visibility("regulate") == "public"
        assert get_visibility("invest_seed") == "public"
        assert get_visibility("launch_competing_feature") == "public"
        assert get_visibility("endorse") == "public"
        assert get_visibility("raise_rate") == "public"

    def test_private_actions(self):
        assert get_visibility("reject_service") == "private"
        assert get_visibility("wait_and_observe") == "private"
        assert get_visibility("upskill") == "private"
        assert get_visibility("rest") == "private"
        assert get_visibility("abandon_project") == "private"
        assert get_visibility("wait_and_see") == "private"
        assert get_visibility("ignore") == "private"
        assert get_visibility("observe") == "private"

    def test_partial_actions(self):
        assert get_visibility("invest_rd") == "partial"
        assert get_visibility("lobby_regulation") == "partial"
        assert get_visibility("seek_funding") == "partial"
        assert get_visibility("divest") == "partial"
        assert get_visibility("fund_competitor") == "partial"
        assert get_visibility("mentor") == "partial"

    def test_unknown_defaults_to_public(self):
        assert get_visibility("unknown_action") == "public"

    def test_all_agent_actions_have_visibility(self):
        """全エージェントの行動タイプがACTION_VISIBILITYに定義されている."""
        expected_actions = {
            # Enterprise
            "adopt_service", "reject_service", "build_competitor",
            "acquire_startup", "invest_rd", "lobby_regulation",
            "partner", "wait_and_observe",
            # Freelancer
            "adopt_tool", "offer_service", "upskill",
            "build_portfolio", "raise_rate", "switch_platform",
            "network", "rest",
            # IndieDevAgent
            "launch_competing_product", "pivot_product", "open_source",
            "monetize", "abandon_project", "seek_funding", "build_community",
            # Government
            "regulate", "subsidize", "certify", "investigate",
            "deregulate", "partner_public", "issue_guideline",
            # Investor
            "invest_seed", "invest_series", "divest",
            "fund_competitor", "market_signal", "wait_and_see", "mentor",
            # Platformer
            "launch_competing_feature", "acquire_service",
            "partner_integrate", "restrict_api", "price_undercut",
            "ignore", "open_platform",
            # Community
            "endorse", "set_standard", "reject_standard",
            "create_alternative", "educate_market", "observe",
            "publish_report",
            # EndUser
            "adopt_new_service", "stay_with_current", "trial",
            "churn", "recommend", "complain", "compare_alternatives",
        }
        assert expected_actions == set(ACTION_VISIBILITY.keys())


class TestAgentMemoryStore:
    def _make_store(self, execute_read_return=None, execute_write_return=None):
        graph = MagicMock()
        graph.execute_read = AsyncMock(return_value=execute_read_return or [])
        graph.execute_write = AsyncMock(return_value=execute_write_return or [])
        return AgentMemoryStore(graph), graph

    @pytest.mark.asyncio
    async def test_ensure_agent_node(self):
        store, graph = self._make_store()
        await store.ensure_agent_node("id1", "テスト", "大手企業", "enterprise")
        graph.execute_write.assert_called_once()
        call_args = graph.execute_write.call_args
        assert "MERGE" in call_args[0][0]
        assert call_args[0][1]["agent_id"] == "id1"

    @pytest.mark.asyncio
    async def test_record_action(self):
        store, graph = self._make_store()
        await store.record_action(
            agent_id="id1",
            agent_name="テスト",
            round_number=3,
            action_type="adopt_service",
            description="サービス採用",
        )
        graph.execute_write.assert_called_once()
        call_args = graph.execute_write.call_args
        assert call_args[0][1]["visibility"] == "public"

    @pytest.mark.asyncio
    async def test_record_action_private(self):
        store, graph = self._make_store()
        await store.record_action(
            agent_id="id1",
            agent_name="テスト",
            round_number=3,
            action_type="wait_and_observe",
            description="様子見",
        )
        call_args = graph.execute_write.call_args
        assert call_args[0][1]["visibility"] == "private"

    @pytest.mark.asyncio
    async def test_record_state(self):
        store, graph = self._make_store()
        await store.record_state(
            agent_id="id1",
            round_number=5,
            state={"revenue": 100, "cost": 50, "headcount": 10,
                   "satisfaction": 0.7, "reputation": 0.6, "active_contracts": 3},
        )
        graph.execute_write.assert_called_once()
        call_args = graph.execute_write.call_args
        assert call_args[0][1]["round"] == 5
        assert call_args[0][1]["revenue"] == 100

    @pytest.mark.asyncio
    async def test_get_visible_actions_includes_public(self):
        store, graph = self._make_store(execute_read_return=[
            {"agent_name": "A社", "action_type": "adopt_service", "description": "採用",
             "round": 1, "visibility": "public", "agent_id": "id2"},
        ])
        actions = await store.get_visible_actions("id1", from_round=1)
        assert len(actions) == 1
        # Cypherクエリにvisibility条件が含まれていることを確認
        query = graph.execute_read.call_args[0][0]
        assert "public" in query
        assert "observer_id" in str(graph.execute_read.call_args[0][1])

    @pytest.mark.asyncio
    async def test_get_market_activity_summary_empty(self):
        store, graph = self._make_store(execute_read_return=[])
        summary = await store.get_market_activity_summary("id1", current_round=1)
        assert summary == ""

    @pytest.mark.asyncio
    async def test_get_market_activity_summary_excludes_self(self):
        store, _ = self._make_store(execute_read_return=[
            {"agent_name": "自社", "action_type": "adopt_service", "description": "採用",
             "round": 1, "visibility": "public", "agent_id": "id1"},
        ])
        summary = await store.get_market_activity_summary("id1", current_round=2)
        # 自分の行動は市場動向に含めない
        assert summary == ""

    @pytest.mark.asyncio
    async def test_get_market_activity_summary_includes_others(self):
        store, _ = self._make_store(execute_read_return=[
            {"agent_name": "他社", "action_type": "adopt_service", "description": "採用",
             "round": 1, "visibility": "public", "agent_id": "id2"},
        ])
        summary = await store.get_market_activity_summary("id1", current_round=2)
        assert "他社" in summary
        assert "adopt_service" in summary
