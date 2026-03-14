"""Base class for LLM clients."""

from abc import ABC, abstractmethod


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

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the LLM service is available."""
        ...
