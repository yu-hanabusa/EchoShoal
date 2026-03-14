"""Redis クライアントのユニットテスト."""

import pytest

from app.core.redis_client import RedisClient


class TestRedisClient:
    def test_init_defaults(self):
        client = RedisClient()
        assert client._client is None
        assert "redis://" in client._url

    def test_init_custom_url(self):
        client = RedisClient(url="redis://custom:1234")
        assert client._url == "redis://custom:1234"

    @pytest.mark.asyncio
    async def test_close_without_connect(self):
        client = RedisClient()
        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_is_available_returns_false_on_error(self):
        client = RedisClient(url="redis://nonexistent:9999")
        result = await client.is_available()
        assert result is False
