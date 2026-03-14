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
        assert get_visibility("bid_project") == "public"
        assert get_visibility("hire_engineers") == "public"
        assert get_visibility("recruit") == "public"
        assert get_visibility("raise_rate") == "public"
        assert get_visibility("start_dx") == "public"

    def test_private_actions(self):
        assert get_visibility("offshore") == "private"
        assert get_visibility("adjust_margin") == "private"
        assert get_visibility("release_bench") == "private"
        assert get_visibility("learn_skill") == "private"
        assert get_visibility("maintain_legacy") == "private"

    def test_partial_actions(self):
        assert get_visibility("outsource") == "partial"
        assert get_visibility("take_contract") == "partial"
        assert get_visibility("outsource_project") == "partial"

    def test_unknown_defaults_to_public(self):
        assert get_visibility("unknown_action") == "public"

    def test_all_agent_actions_have_visibility(self):
        """全エージェントの行動タイプがACTION_VISIBILITYに定義されている."""
        expected_actions = {
            # SIer
            "bid_project", "hire_engineers", "outsource", "invest_rd",
            "offshore", "internal_training",
            # SES
            "recruit", "upskill", "adjust_margin", "expand_sales",
            "release_bench", "shift_domain",
            # Freelance
            "take_contract", "learn_skill", "raise_rate", "lower_rate",
            "network", "rest",
            # Enterprise
            "hire_internal", "outsource_project", "start_dx",
            "maintain_legacy", "adopt_saas", "insource",
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
        await store.ensure_agent_node("id1", "テスト", "SES企業", "ses")
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
            action_type="recruit",
            description="エンジニア採用",
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
            action_type="offshore",
            description="コスト削減",
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
            {"agent_name": "A社", "action_type": "recruit", "description": "採用",
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
            {"agent_name": "自社", "action_type": "recruit", "description": "採用",
             "round": 1, "visibility": "public", "agent_id": "id1"},
        ])
        summary = await store.get_market_activity_summary("id1", current_round=2)
        # 自分の行動は市場動向に含めない
        assert summary == ""

    @pytest.mark.asyncio
    async def test_get_market_activity_summary_includes_others(self):
        store, _ = self._make_store(execute_read_return=[
            {"agent_name": "他社", "action_type": "recruit", "description": "採用",
             "round": 1, "visibility": "public", "agent_id": "id2"},
        ])
        summary = await store.get_market_activity_summary("id1", current_round=2)
        assert "他社" in summary
        assert "recruit" in summary
