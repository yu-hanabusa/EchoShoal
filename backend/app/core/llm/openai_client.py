"""OpenAI API client for heavy LLM tasks."""

import httpx

from app.config import settings
from app.core.llm.base import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI API (also works with OpenAI-compatible endpoints)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
    ):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        if not self.api_key:
            raise ValueError("OpenAI API key is not configured. Set ECHOSHOAL_OPENAI_API_KEY.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def is_available(self) -> bool:
        return bool(self.api_key)
