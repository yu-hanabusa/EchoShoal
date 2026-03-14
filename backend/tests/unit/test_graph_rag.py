"""Tests for GraphRAG retriever."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.graph.rag import AgentDecisionContext, GraphRAGRetriever


class TestAgentDecisionContext:
    def test_to_prompt_empty(self):
        ctx = AgentDecisionContext()
        assert ctx.to_prompt() == ""

    def test_to_prompt_with_history(self):
        ctx = AgentDecisionContext(own_history="【自社の直近の行動】\n  テスト")
        result = ctx.to_prompt()
        assert "自社の直近の行動" in result

    def test_to_prompt_with_all_sections(self):
        ctx = AgentDecisionContext(
            own_history="自社履歴",
            market_activity="市場動向",
            reference_stats="統計データ",
        )
        result = ctx.to_prompt()
        assert "自社履歴" in result
        assert "市場動向" in result
        assert "統計データ" in result


class TestGraphRAGRetriever:
    def _make_retriever(self):
        graph = MagicMock()
        graph.execute_read = AsyncMock(return_value=[])
        memory = MagicMock()
        memory.get_agent_history = AsyncMock(return_value={"actions": [], "snapshots": []})
        memory.get_market_activity_summary = AsyncMock(return_value="")
        return GraphRAGRetriever(graph, memory), graph, memory

    @pytest.mark.asyncio
    async def test_get_agent_context_calls_memory(self):
        retriever, graph, memory = self._make_retriever()
        ctx = await retriever.get_agent_context("agent-1", round_number=5)

        memory.get_agent_history.assert_called_once_with("agent-1", last_n_rounds=5)
        memory.get_market_activity_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_context_returns_context(self):
        retriever, _, _ = self._make_retriever()
        ctx = await retriever.get_agent_context("agent-1", round_number=3)

        assert isinstance(ctx, AgentDecisionContext)

    @pytest.mark.asyncio
    async def test_format_own_history_with_snapshots(self):
        retriever, _, memory = self._make_retriever()
        memory.get_agent_history = AsyncMock(return_value={
            "actions": [
                {"action_type": "recruit", "description": "採用", "round": 3},
            ],
            "snapshots": [
                {"round": 3, "revenue": 100, "cost": 50, "headcount": 10,
                 "satisfaction": 0.7, "reputation": 0.6},
                {"round": 2, "revenue": 90, "cost": 45, "headcount": 9,
                 "satisfaction": 0.65, "reputation": 0.55},
            ],
        })

        ctx = await retriever.get_agent_context("agent-1", round_number=4)
        prompt = ctx.to_prompt()

        assert "売上100万円" in prompt
        assert "recruit" in prompt
        assert "+10万円" in prompt  # 前回比

    @pytest.mark.asyncio
    async def test_graceful_on_memory_failure(self):
        retriever, _, memory = self._make_retriever()
        memory.get_agent_history = AsyncMock(side_effect=RuntimeError("DB down"))
        memory.get_market_activity_summary = AsyncMock(side_effect=RuntimeError("DB down"))

        # エラーでも例外は上がらず空コンテキストを返す
        ctx = await retriever.get_agent_context("agent-1", round_number=3)
        assert ctx.own_history == ""
        assert ctx.market_activity == ""
