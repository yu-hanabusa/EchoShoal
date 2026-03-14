"""文書アップロード・管理 API エンドポイント.

文書（PDF/テキスト）をアップロードし、NLP解析 → 知識グラフ格納を行う。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.documents.models import DocumentInfo, ProcessResult
from app.core.documents.parser import DocumentParseError, DocumentParser
from app.core.documents.processor import DocumentProcessor
from app.core.graph.client import GraphClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


async def _get_graph_client() -> GraphClient:
    """GraphClientを取得し接続確認する."""
    client = GraphClient()
    if not await client.is_available():
        raise HTTPException(status_code=503, detail="Neo4jに接続できません")
    return client


@router.post("/upload", response_model=ProcessResult)
async def upload_document(
    file: UploadFile = File(...),
    source: str = Form(default=""),
) -> ProcessResult:
    """文書をアップロードし、NLP解析 → 知識グラフに格納する.

    対応形式: .txt, .pdf
    ファイルサイズ上限: 10MB
    """
    # ファイル読み込み
    content = await file.read()

    # パース（テキスト抽出 + バリデーション）
    parser = DocumentParser()
    try:
        doc = parser.parse(content, file.filename or "unknown", source=source)
    except DocumentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # NLP解析 → 知識グラフ格納
    graph_client = await _get_graph_client()
    try:
        processor = DocumentProcessor(graph_client)
        result = await processor.process(doc)
        logger.info(
            "文書アップロード完了: %s → エンティティ%d件",
            doc.filename, result.entities_found,
        )
        return result
    finally:
        await graph_client.close()


@router.get("/", response_model=list[DocumentInfo])
async def list_documents() -> list[DocumentInfo]:
    """アップロード済み文書の一覧を取得する."""
    graph_client = await _get_graph_client()
    try:
        processor = DocumentProcessor(graph_client)
        return await processor.get_documents()
    finally:
        await graph_client.close()


@router.get("/{doc_id}")
async def get_document(doc_id: str) -> dict[str, Any]:
    """文書の詳細と関連エンティティを取得する."""
    graph_client = await _get_graph_client()
    try:
        processor = DocumentProcessor(graph_client)
        detail = await processor.get_document_detail(doc_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="文書が見つかりません")
        return detail
    finally:
        await graph_client.close()
