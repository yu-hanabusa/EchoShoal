"""Redis クライアント — 接続管理と基本操作."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis への非同期接続を管理するクライアント."""

    def __init__(self, url: str | None = None):
        self._url = url or settings.redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """接続を初期化する."""
        if self._client is not None:
            return
        self._client = aioredis.from_url(
            self._url,
            decode_responses=True,
        )
        await self._client.ping()
        logger.info("Redis に接続しました: %s", self._url)

    async def close(self) -> None:
        """接続を閉じる."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _ensure_connected(self) -> aioredis.Redis:
        if self._client is None:
            await self.connect()
        return self._client

    async def get(self, key: str) -> str | None:
        client = await self._ensure_connected()
        return await client.get(key)

    async def set(
        self, key: str, value: str, ttl: int | None = None
    ) -> None:
        client = await self._ensure_connected()
        if ttl:
            await client.setex(key, ttl, value)
        else:
            await client.set(key, value)

    async def delete(self, key: str) -> None:
        client = await self._ensure_connected()
        await client.delete(key)

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """JSON 文字列を取得し、dict にパースして返す."""
        raw = await self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(
        self, key: str, value: dict[str, Any], ttl: int | None = None
    ) -> None:
        """dict を JSON 文字列として保存する."""
        await self.set(key, json.dumps(value, ensure_ascii=False), ttl)

    async def is_available(self) -> bool:
        """Redis が利用可能か確認する."""
        try:
            client = await self._ensure_connected()
            await client.ping()
            return True
        except Exception:
            logger.warning("Redis への接続に失敗しました")
            return False
