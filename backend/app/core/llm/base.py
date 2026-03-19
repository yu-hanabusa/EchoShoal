"""Base class for LLM clients."""

from abc import ABC, abstractmethod

from app.core.llm.token_tracker import TokenUsage


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Generate a text response from the LLM."""
        ...

    async def generate_with_usage(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> tuple[str, TokenUsage]:
        """Generate a text response and return token usage.

        デフォルト実装は generate() を呼んでトークン数0を返す。
        各クライアントでオーバーライドしてAPIレスポンスからトークン数を取得する。
        """
        text = await self.generate(prompt, system_prompt, json_mode, temperature)
        return text, TokenUsage()

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the LLM service is available."""
        ...
