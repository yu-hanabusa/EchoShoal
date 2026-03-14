"""Neo4j グラフデータベースクライアント."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


class GraphClient:
    """Neo4j への非同期接続を管理するクライアント."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self._uri = uri or settings.neo4j_uri
        self._user = user or settings.neo4j_user
        self._password = password or settings.neo4j_password
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """ドライバを初期化して接続確認する."""
        if self._driver is not None:
            return
        self._driver = AsyncGraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
        )
        await self._driver.verify_connectivity()
        logger.info("Neo4j に接続しました: %s", self._uri)

    async def close(self) -> None:
        """接続を閉じる."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j 接続を閉じました")

    @asynccontextmanager
    async def session(self, database: str = "neo4j"):
        """非同期セッションを取得するコンテキストマネージャ."""
        if self._driver is None:
            await self.connect()
        async with self._driver.session(database=database) as session:
            yield session

    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """読み取りクエリを実行し、結果をdict のリストで返す."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """書き込みクエリを実行し、結果をdict のリストで返す."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def is_available(self) -> bool:
        """Neo4j が利用可能か確認する."""
        try:
            if self._driver is None:
                await self.connect()
            await self._driver.verify_connectivity()
            return True
        except Exception:
            logger.warning("Neo4j への接続に失敗しました")
            return False
