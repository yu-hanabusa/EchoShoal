"""文書処理のデータモデル."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    """テキスト抽出済みの文書."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    text: str
    page_count: int = 1
    source: str = Field(default="", description="ユーザーが指定するソース名（例: IPA白書2024）")


class ExtractedRelationship(BaseModel):
    """文書から抽出されたエンティティ間の関係."""

    source: str
    target: str
    relation_type: str
    confidence: float = 1.0


class ProcessResult(BaseModel):
    """文書処理結果のサマリー."""

    document_id: str
    filename: str
    entities_found: int = 0
    technologies: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    new_nodes_created: int = 0
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    relationships_stored: int = 0


class DocumentInfo(BaseModel):
    """文書の情報（一覧表示用）."""

    doc_id: str
    filename: str
    source: str = ""
    text_length: int = 0
    entity_count: int = 0
    uploaded_at: str = ""
