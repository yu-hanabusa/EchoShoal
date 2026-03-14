"""LLM Router - routes requests to Ollama (light) or Claude/OpenAI (heavy) based on task type."""

from enum import Enum
from typing import Any

from app.core.llm.ollama_client import OllamaClient
from app.core.llm.claude_client import ClaudeClient
from app.core.llm.openai_client import OpenAIClient
from app.config import settings


class TaskType(str, Enum):
    """Task types that determine which LLM to use."""

    AGENT_DECISION = "agent_decision"  # -> Ollama (light)
    EMOTION_UPDATE = "emotion_update"  # -> Ollama (light)
    REPORT_GENERATION = "report_generation"  # -> Claude/OpenAI (heavy)
    ONTOLOGY_DESIGN = "ontology_design"  # -> Claude/OpenAI (heavy)
    USER_CHAT = "user_chat"  # -> Claude/OpenAI (heavy)
    AGENT_INTERVIEW = "agent_interview"  # -> Ollama (light)
    PERSONA_GENERATION = "persona_generation"  # -> Claude/OpenAI (heavy)


LIGHT_TASKS = {
    TaskType.AGENT_DECISION,
    TaskType.EMOTION_UPDATE,
    TaskType.AGENT_INTERVIEW,
}

HEAVY_TASKS = {
    TaskType.REPORT_GENERATION,
    TaskType.ONTOLOGY_DESIGN,
    TaskType.USER_CHAT,
    TaskType.PERSONA_GENERATION,
}


class LLMRouter:
    """Routes LLM requests to the appropriate provider based on task type."""

    def __init__(
        self,
        ollama_client: OllamaClient | None = None,
        claude_client: ClaudeClient | None = None,
        openai_client: OpenAIClient | None = None,
        heavy_provider: str | None = None,
    ):
        self._ollama = ollama_client
        self._claude = claude_client
        self._openai = openai_client
        self._heavy_provider = heavy_provider or settings.default_heavy_provider

    @property
    def ollama(self) -> OllamaClient:
        if self._ollama is None:
            self._ollama = OllamaClient()
        return self._ollama

    @property
    def heavy_client(self) -> ClaudeClient | OpenAIClient:
        if self._heavy_provider == "claude":
            if self._claude is None:
                self._claude = ClaudeClient()
            return self._claude
        else:
            if self._openai is None:
                self._openai = OpenAIClient()
            return self._openai

    def _select_client(self, task_type: TaskType) -> OllamaClient | ClaudeClient | OpenAIClient:
        if task_type in LIGHT_TASKS:
            return self.ollama
        # クライアントが明示的に注入されている場合はそのまま使用
        if self._heavy_provider == "claude" and self._claude is not None:
            return self._claude
        if self._heavy_provider == "openai" and self._openai is not None:
            return self._openai
        # APIキー未設定の場合はOllamaにフォールバック
        if self._heavy_provider == "claude" and not settings.claude_api_key:
            return self.ollama
        if self._heavy_provider == "openai" and not settings.openai_api_key:
            return self.ollama
        return self.heavy_client

    async def generate(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Generate a response using the appropriate LLM for the task type."""
        client = self._select_client(task_type)
        return await client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            temperature=temperature,
        )

    async def generate_json(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Generate a JSON response. Lower temperature for structured output."""
        import json

        response = await self.generate(
            task_type=task_type,
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=True,
            temperature=temperature,
        )
        return json.loads(response)
