"""Tests for LLM Router - verifies correct routing of tasks to providers."""

import json
from unittest.mock import AsyncMock

import pytest

from app.core.llm.router import LLMRouter, TaskType, LIGHT_TASKS, HEAVY_TASKS
from app.core.llm.token_tracker import TokenUsage
from app.core.llm.ollama_client import OllamaClient
from app.core.llm.claude_client import ClaudeClient


def _make_usage(provider: str = "") -> TokenUsage:
    return TokenUsage(input_tokens=10, output_tokens=5, provider=provider, model="test")


@pytest.fixture
def mock_ollama():
    client = AsyncMock(spec=OllamaClient)
    client.generate = AsyncMock(return_value="ollama response")
    client.generate_with_usage = AsyncMock(return_value=("ollama response", _make_usage("ollama")))
    return client


@pytest.fixture
def mock_claude():
    client = AsyncMock(spec=ClaudeClient)
    client.generate = AsyncMock(return_value="claude response")
    client.generate_with_usage = AsyncMock(return_value=("claude response", _make_usage("claude")))
    return client


@pytest.fixture
def router(mock_ollama, mock_claude):
    return LLMRouter(
        ollama_client=mock_ollama,
        claude_client=mock_claude,
        heavy_provider="claude",
    )


class TestTaskTypeClassification:
    """Verify that task types are correctly classified as light or heavy."""

    def test_agent_decision_is_light(self):
        assert TaskType.AGENT_DECISION in LIGHT_TASKS

    def test_emotion_update_is_light(self):
        assert TaskType.EMOTION_UPDATE in LIGHT_TASKS

    def test_report_generation_is_heavy(self):
        assert TaskType.REPORT_GENERATION in HEAVY_TASKS

    def test_ontology_design_is_heavy(self):
        assert TaskType.ONTOLOGY_DESIGN in HEAVY_TASKS

    def test_user_chat_is_heavy(self):
        assert TaskType.USER_CHAT in HEAVY_TASKS

    def test_persona_generation_is_heavy(self):
        assert TaskType.PERSONA_GENERATION in HEAVY_TASKS

    def test_all_task_types_are_classified(self):
        """Every TaskType must be in either LIGHT_TASKS or HEAVY_TASKS."""
        all_classified = LIGHT_TASKS | HEAVY_TASKS
        for task_type in TaskType:
            assert task_type in all_classified, f"{task_type} is not classified"


class TestLLMRouting:
    """Verify that the router sends requests to the correct provider."""

    @pytest.mark.asyncio
    async def test_light_task_routes_to_ollama(self, router, mock_ollama):
        result = await router.generate(TaskType.AGENT_DECISION, "test prompt")
        assert result == "ollama response"
        mock_ollama.generate_with_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_heavy_task_routes_to_claude(self, router, mock_claude):
        result = await router.generate(TaskType.REPORT_GENERATION, "test prompt")
        assert result == "claude response"
        mock_claude.generate_with_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_passes_parameters(self, router, mock_ollama):
        await router.generate(
            TaskType.AGENT_DECISION,
            prompt="choose action",
            system_prompt="you are an agent",
            json_mode=True,
            temperature=0.3,
        )
        mock_ollama.generate_with_usage.assert_called_once_with(
            prompt="choose action",
            system_prompt="you are an agent",
            json_mode=True,
            temperature=0.3,
        )

    @pytest.mark.asyncio
    async def test_generate_json_returns_parsed_dict(self, router, mock_ollama):
        mock_ollama.generate_with_usage = AsyncMock(
            return_value=('{"action": "HIRE", "count": 3}', _make_usage("ollama"))
        )
        result = await router.generate_json(TaskType.AGENT_DECISION, "choose action")
        assert result == {"action": "HIRE", "count": 3}

    @pytest.mark.asyncio
    async def test_generate_json_uses_low_temperature(self, router, mock_ollama):
        mock_ollama.generate_with_usage = AsyncMock(
            return_value=('{"ok": true}', _make_usage("ollama"))
        )
        await router.generate_json(TaskType.AGENT_DECISION, "test")
        call_kwargs = mock_ollama.generate_with_usage.call_args[1]
        assert call_kwargs["temperature"] == 0.3
        # json_mode=Falseでレスポンスから抽出（qwen3 thinking model対応）
        assert call_kwargs["json_mode"] is False

    @pytest.mark.asyncio
    async def test_generate_json_raises_on_invalid_json(self, router, mock_ollama):
        mock_ollama.generate_with_usage = AsyncMock(
            return_value=("not json", _make_usage("ollama"))
        )
        with pytest.raises(ValueError, match="JSON parse failed"):
            await router.generate_json(TaskType.AGENT_DECISION, "test")


class TestHeavyProviderSwitch:
    """Verify that the heavy provider can be switched between Claude and OpenAI."""

    @pytest.mark.asyncio
    async def test_openai_as_heavy_provider(self, mock_ollama):
        mock_openai = AsyncMock()
        mock_openai.generate_with_usage = AsyncMock(
            return_value=("openai response", _make_usage("openai"))
        )
        router = LLMRouter(
            ollama_client=mock_ollama,
            openai_client=mock_openai,
            heavy_provider="openai",
        )
        result = await router.generate(TaskType.REPORT_GENERATION, "test")
        assert result == "openai response"
        mock_openai.generate_with_usage.assert_called_once()
