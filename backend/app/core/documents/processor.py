"""文書処理パイプライン: NLP解析 → 知識グラフ格納.

アップロードされた文書からエンティティを抽出し、
既存の知識グラフノードにリンクする。
新規エンティティは必要に応じてノードを作成する。
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.documents.models import DocumentInfo, ParsedDocument, ProcessResult
from app.core.graph.client import GraphClient
from app.core.nlp.analyzer import AnalysisResult, JapaneseAnalyzer

logger = logging.getLogger(__name__)

# NLP抽出結果の技術名 → 既存 Skill ノード名のマッピング
_TECH_TO_SKILL: dict[str, str] = {
    "Python": "Python",
    "Go": "Go",
    "Java": "Java",
    "PHP": "PHP",
    "Ruby": "Ruby",
    "TypeScript": "TypeScript",
    "JavaScript": "TypeScript",  # JSはTSにマージ
    "Kotlin": "Kotlin",
    "Swift": "Swift",
    "COBOL": "COBOL",
    "VB.NET": "VB.NET",
    "React": "React",
    "Vue.js": "Vue.js",
    "Angular": "Angular",
    "Next.js": "Next.js",
    "Flutter": "Flutter",
    "React Native": "React Native",
    "AWS": "AWS",
    "GCP": "GCP",
    "Azure": "Azure",
    "Kubernetes": "Kubernetes",
    "Docker": "Docker",
    "Terraform": "Terraform",
    "PyTorch": "PyTorch",
    "TensorFlow": "TensorFlow",
    "LLM": "LLM",
    "SAP": "SAP",
    "Salesforce": "Salesforce",
    "ServiceNow": "ServiceNow",
}


class DocumentProcessor:
    """文書を解析し、知識グラフに格納するパイプライン."""

    def __init__(
        self,
        graph_client: GraphClient,
        nlp_analyzer: JapaneseAnalyzer | None = None,
    ):
        self.graph = graph_client
        self.nlp = nlp_analyzer or JapaneseAnalyzer()

    async def process(self, doc: ParsedDocument) -> ProcessResult:
        """文書を解析し、知識グラフに格納する.

        1. NLP解析（GiNZA + ルールベース）
        2. Documentノード作成
        3. 抽出エンティティを既存ノードにリンク
        """
        # NLP解析
        analysis = self.nlp.analyze(doc.text)
        logger.info(
            "文書 '%s' を解析: 技術%d件, 組織%d件, 政策%d件",
            doc.filename,
            len(analysis.technologies),
            len(analysis.organizations),
            len(analysis.policies),
        )

        # Documentノード作成
        await self._store_document(doc, analysis)

        # エンティティをグラフにリンク
        new_nodes = 0
        new_nodes += await self._link_technologies(doc.id, analysis.technologies)
        new_nodes += await self._link_organizations(doc.id, analysis.organizations)
        new_nodes += await self._link_policies(doc.id, analysis.policies)

        return ProcessResult(
            document_id=doc.id,
            filename=doc.filename,
            entities_found=(
                len(analysis.technologies)
                + len(analysis.organizations)
                + len(analysis.policies)
            ),
            technologies=analysis.technologies,
            organizations=analysis.organizations,
            policies=analysis.policies,
            keywords=analysis.keywords[:20],
            new_nodes_created=new_nodes,
        )

    async def _store_document(
        self, doc: ParsedDocument, analysis: AnalysisResult
    ) -> None:
        """Documentノードを知識グラフに作成する."""
        await self.graph.execute_write(
            "MERGE (d:Document {doc_id: $doc_id}) "
            "SET d.filename = $filename, "
            "    d.source = $source, "
            "    d.text_length = $text_length, "
            "    d.page_count = $page_count, "
            "    d.entity_count = $entity_count, "
            "    d.uploaded_at = datetime()",
            {
                "doc_id": doc.id,
                "filename": doc.filename,
                "source": doc.source,
                "text_length": len(doc.text),
                "page_count": doc.page_count,
                "entity_count": len(analysis.entities),
            },
        )

    async def _link_entities(
        self,
        doc_id: str,
        names: list[str],
        node_label: str,
        name_mapper: dict[str, str] | None = None,
        extra_on_create: str = "",
    ) -> int:
        """抽出エンティティを知識グラフノードにリンクする共通処理.

        既存ノードがなければ新規作成（MERGEで冪等）。
        """
        new_count = 0
        on_create = "ON CREATE SET n._created_by = 'document_upload'"
        if extra_on_create:
            on_create += f", {extra_on_create}"

        for raw_name in names:
            resolved_name = (name_mapper or {}).get(raw_name, raw_name)
            try:
                result = await self.graph.execute_write(
                    f"MERGE (n:{node_label} {{name: $name}}) "
                    f"{on_create} "
                    "WITH n "
                    "MATCH (d:Document {doc_id: $doc_id}) "
                    "MERGE (d)-[:MENTIONS]->(n) "
                    "RETURN n._created_by AS created_by",
                    {"name": resolved_name, "doc_id": doc_id},
                )
                if result and result[0].get("created_by") == "document_upload":
                    new_count += 1
            except Exception:
                logger.warning("%sリンク失敗: %s", node_label, raw_name)
        return new_count

    async def _link_technologies(
        self, doc_id: str, technologies: list[str]
    ) -> int:
        """抽出された技術名を既存Skillノードにリンクする."""
        return await self._link_entities(
            doc_id, technologies, "Skill", name_mapper=_TECH_TO_SKILL,
        )

    async def _link_organizations(
        self, doc_id: str, organizations: list[str]
    ) -> int:
        """抽出された組織名をCompanyノードにリンクする."""
        return await self._link_entities(doc_id, organizations, "Company")

    async def _link_policies(
        self, doc_id: str, policies: list[str]
    ) -> int:
        """抽出された政策名をPolicyノードにリンクする."""
        return await self._link_entities(
            doc_id, policies, "Policy", extra_on_create="n.description = ''",
        )

    async def get_documents(self) -> list[DocumentInfo]:
        """アップロード済み文書の一覧を取得する."""
        results = await self.graph.execute_read(
            "MATCH (d:Document) "
            "RETURN d.doc_id AS doc_id, d.filename AS filename, "
            "       d.source AS source, d.text_length AS text_length, "
            "       d.entity_count AS entity_count, "
            "       toString(d.uploaded_at) AS uploaded_at "
            "ORDER BY d.uploaded_at DESC"
        )
        return [
            DocumentInfo(
                doc_id=r["doc_id"],
                filename=r["filename"],
                source=r.get("source", ""),
                text_length=r.get("text_length", 0),
                entity_count=r.get("entity_count", 0),
                uploaded_at=r.get("uploaded_at", ""),
            )
            for r in results
        ]

    async def get_document_detail(self, doc_id: str) -> dict[str, Any] | None:
        """文書の詳細と関連エンティティを取得する."""
        doc = await self.graph.execute_read(
            "MATCH (d:Document {doc_id: $doc_id}) "
            "RETURN d.doc_id AS doc_id, d.filename AS filename, "
            "       d.source AS source, d.text_length AS text_length, "
            "       d.page_count AS page_count, d.entity_count AS entity_count, "
            "       toString(d.uploaded_at) AS uploaded_at",
            {"doc_id": doc_id},
        )
        if not doc:
            return None

        # 関連エンティティ取得
        mentions = await self.graph.execute_read(
            "MATCH (d:Document {doc_id: $doc_id})-[:MENTIONS]->(e) "
            "RETURN labels(e)[0] AS type, e.name AS name",
            {"doc_id": doc_id},
        )

        return {
            **doc[0],
            "mentions": mentions,
        }
