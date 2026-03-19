"""Claude API client for heavy LLM tasks."""

import httpx

from app.config import settings
from app.core.llm.base import BaseLLMClient
from app.core.llm.token_tracker import TokenUsage


class ClaudeClient(BaseLLMClient):
    """Client for Anthropic Claude API."""

    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        self.api_key = api_key or settings.claude_api_key
        self.model = model or settings.claude_model
        self.timeout = timeout

    def _build_request(
        self,
        prompt: str,
        system_prompt: str | None,
        json_mode: bool,
        temperature: float,
    ) -> tuple[dict[str, str], dict]:
        """リクエストヘッダーとペイロードを構築する."""
        if not self.api_key:
            raise ValueError("Claude API key is not configured. Set ECHOSHOAL_CLAUDE_API_KEY.")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }

        messages = [{"role": "user", "content": prompt}]

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system_prompt:
            effective_system = system_prompt
            if json_mode:
                effective_system += "\n\nYou must respond with valid JSON only. No other text."
            payload["system"] = effective_system
        elif json_mode:
            payload["system"] = "You must respond with valid JSON only. No other text."

        return headers, payload

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        headers, payload = self._build_request(prompt, system_prompt, json_mode, temperature)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def generate_with_usage(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> tuple[str, TokenUsage]:
        headers, payload = self._build_request(prompt, system_prompt, json_mode, temperature)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            text = data["content"][0]["text"]
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                provider="claude",
                model=self.model,
            )
            return text, usage

    async def is_available(self) -> bool:
        return bool(self.api_key)
