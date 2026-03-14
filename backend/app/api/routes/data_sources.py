"""データソース管理 API エンドポイント.

統計データの収集・知識グラフへの投入・状態確認を行う。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.data_sources.pipeline import DataCollectionPipeline
from app.core.graph.client import GraphClient
from app.core.graph.schema import KnowledgeGraphRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])


async def _get_graph_client() -> GraphClient:
    """GraphClientを取得し接続確認する."""
    client = GraphClient()
    if not await client.is_available():
        raise HTTPException(status_code=503, detail="Neo4jに接続できません")
    return client


@router.post("/collect")
async def collect_data() -> dict[str, Any]:
    """統計データを収集し、知識グラフに投入する.

    e-Stat API + 静的参考データを取得してNeo4jに格納する。
    冪等操作（何度実行しても同じ結果）。
    """
    graph_client = await _get_graph_client()
    try:
        pipeline = DataCollectionPipeline(graph_client)
        result = await pipeline.run()

        return {
            "status": "completed",
            "total_records": result.total_records,
            "stored_records": result.stored_records,
            "sources": result.sources,
            "errors": result.errors,
        }
    finally:
        await graph_client.close()


@router.get("/status")
async def get_data_status() -> dict[str, Any]:
    """知識グラフ内のデータ状態を取得する."""
    graph_client = await _get_graph_client()
    try:
        pipeline = DataCollectionPipeline(graph_client)
        status = await pipeline.get_data_status()
        return {"status": "ok", **status}
    finally:
        await graph_client.close()


@router.get("/ontology")
async def get_ontology() -> dict[str, Any]:
    """知識グラフの全体構造を取得する（神の視点）."""
    graph_client = await _get_graph_client()
    try:
        repo = KnowledgeGraphRepository(graph_client)
        ontology = await repo.get_full_ontology()
        return {"status": "ok", **ontology}
    finally:
        await graph_client.close()
