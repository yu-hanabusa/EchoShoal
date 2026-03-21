"""文書処理パイプライン: NLP解析 → 知識グラフ格納.

アップロードされた文書からエンティティを抽出し、
既存の知識グラフノードにリンクする。
新規エンティティは必要に応じてノードを作成する。
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.documents.models import (
    DocumentInfo,
    ExtractedRelationship,
    ParsedDocument,
    ProcessResult,
)
from app.core.graph.client import GraphClient
from app.core.nlp.analyzer import AnalysisResult, JapaneseAnalyzer

logger = logging.getLogger(__name__)

# LLMが返す関係タイプの許可リスト
_ALLOWED_RELATION_TYPES = frozenset({
    "COMPETES_WITH",
    "PROVIDES_INFRA",
    "TARGET_SECTOR",
    "PARTNERS_WITH",
    "INVESTS_IN",
    "REGULATES",
    "USES",
    "ACQUIRES",
    "DEPENDS_ON",
    "AFFECTS",
})

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
        simulation_id: str = "",
    ):
        self.graph = graph_client
        self.nlp = nlp_analyzer or JapaneseAnalyzer()
        self.simulation_id = simulation_id

    async def process(self, doc: ParsedDocument) -> ProcessResult:
        """文書を解析し、知識グラフに格納する.

        1. ルールベース辞書で技術名・政策名を抽出
        2. LLMで組織名・サービス名を抽出
        3. Documentノード作成
        4. 抽出エンティティを既存ノードにリンク
        """
        # ルールベース辞書で技術名・政策名を抽出
        analysis = self.nlp.analyze(doc.text)

        # LLMで組織名を抽出
        llm_orgs = await self._extract_orgs_with_llm(doc.text)
        if llm_orgs:
            existing = set(analysis.organizations)
            for org in llm_orgs:
                if org not in existing:
                    analysis.organizations.append(org)

        logger.info(
            "文書 '%s' を解析: 技術%d件, 組織%d件（LLM抽出）, 政策%d件",
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

        # エンティティ間の関係をLLMで抽出
        entities_map = {
            "technologies": analysis.technologies,
            "organizations": analysis.organizations,
            "policies": analysis.policies,
        }
        relationships = await self._extract_relationships_with_llm(
            doc.text, entities_map,
        )
        relationships_stored = await self._store_relationships(
            doc.id, relationships,
        )

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
            relationships=relationships,
            relationships_stored=relationships_stored,
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
            "    d.text_summary = $text_summary, "
            "    d.full_text = $full_text, "
            "    d.page_count = $page_count, "
            "    d.entity_count = $entity_count, "
            "    d.simulation_id = $simulation_id, "
            "    d.uploaded_at = datetime()",
            {
                "doc_id": doc.id,
                "filename": doc.filename,
                "source": doc.source,
                "text_length": len(doc.text),
                "text_summary": self._extract_summary(doc.text),
                "full_text": doc.text,
                "page_count": doc.page_count,
                "entity_count": len(analysis.entities),
                "simulation_id": self.simulation_id,
            },
        )

    @staticmethod
    def _extract_summary(text: str, max_chars: int = 2000) -> str:
        """ドキュメント本文から要約テキストを抽出する.

        各セクション（■区切り）の冒頭を抽出し、
        エージェントがRAGで参照できる形にする。
        LLMは使わず、構造的な切り出しのみで行う。
        """
        if not text:
            return ""

        lines = text.strip().split("\n")
        summary_parts: list[str] = []
        current_section = ""
        section_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            # セクション区切りを検出（■ または === で始まる行）
            if stripped.startswith("■") or stripped.startswith("==="):
                # 前のセクションを保存
                if current_section and section_lines:
                    content = " ".join(section_lines[:3])  # 各セクション冒頭3行
                    summary_parts.append(f"{current_section}: {content}")
                current_section = stripped.lstrip("■ ")
                section_lines = []
            elif stripped and current_section:
                section_lines.append(stripped)
            elif stripped and not current_section:
                # タイトル行（最初のセクション前）
                if not summary_parts:
                    summary_parts.append(stripped)

        # 最後のセクション
        if current_section and section_lines:
            content = " ".join(section_lines[:3])
            summary_parts.append(f"{current_section}: {content}")

        result = "\n".join(summary_parts)
        if len(result) > max_chars:
            result = result[:max_chars] + "..."
        return result

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
        """このシミュレーションにアップロードされた文書一覧を取得する."""
        results = await self.graph.execute_read(
            "MATCH (d:Document) "
            "WHERE d.simulation_id = $simulation_id "
            "RETURN d.doc_id AS doc_id, d.filename AS filename, "
            "       d.source AS source, d.text_length AS text_length, "
            "       d.entity_count AS entity_count, "
            "       toString(d.uploaded_at) AS uploaded_at "
            "ORDER BY d.uploaded_at DESC",
            {"simulation_id": self.simulation_id},
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

    async def _extract_relationships_with_llm(
        self,
        text: str,
        entities: dict[str, list[str]],
    ) -> list[ExtractedRelationship]:
        """抽出済みエンティティ間の関係をLLMで推定する."""
        all_names = set()
        for names in entities.values():
            all_names.update(names)

        if len(all_names) < 2:
            return []

        entity_lines = []
        for category, names in entities.items():
            if names:
                entity_lines.append(f"- {category}: {', '.join(names)}")
        entity_text = "\n".join(entity_lines)

        allowed_types = ", ".join(sorted(_ALLOWED_RELATION_TYPES))

        try:
            from app.core.llm.router import LLMRouter, TaskType
            llm = LLMRouter()
            response = await llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=(
                    f"Text:\n{text[:2000]}\n\n"
                    f"Extracted entities:\n{entity_text}\n\n"
                    "Identify relationships between these entities based on the text.\n"
                    f"Allowed relationship types: {allowed_types}\n\n"
                    "Return JSON:\n"
                    '{"relationships": [{"source": "Entity A", "target": "Entity B", '
                    '"type": "COMPETES_WITH"}]}\n'
                    "Rules:\n"
                    "- source and target MUST be from the extracted entities list above\n"
                    "- type MUST be one of the allowed types\n"
                    "- Do not create self-referential relationships\n"
                ),
                system_prompt="Extract entity relationships. JSON only.",
            )
            raw = response.get("relationships", [])
            if not isinstance(raw, list):
                return []

            results: list[ExtractedRelationship] = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                source = str(item.get("source", "")).strip()
                target = str(item.get("target", "")).strip()
                rel_type = str(item.get("type", "")).strip().upper()

                # バリデーション
                if source == target:
                    continue
                if rel_type not in _ALLOWED_RELATION_TYPES:
                    continue
                # エンティティ名の完全一致またはサブストリングマッチ
                source_match = self._match_entity(source, all_names)
                target_match = self._match_entity(target, all_names)
                if not source_match or not target_match:
                    continue

                results.append(ExtractedRelationship(
                    source=source_match,
                    target=target_match,
                    relation_type=rel_type,
                ))
            logger.info("LLMが%d件のエンティティ間関係を抽出", len(results))
            return results
        except Exception:
            logger.warning("LLMによるエンティティ関係抽出失敗")
            return []

    @staticmethod
    def _match_entity(name: str, known_names: set[str]) -> str | None:
        """LLMが返した名前を抽出済みエンティティに照合する."""
        if name in known_names:
            return name
        # サブストリングマッチ（LLMが略称や表記揺れを返す場合）
        for known in known_names:
            if name in known or known in name:
                return known
        return None

    async def _store_relationships(
        self,
        doc_id: str,
        relationships: list[ExtractedRelationship],
    ) -> int:
        """抽出した関係をNeo4jに格納する."""
        stored = 0
        for rel in relationships:
            if rel.relation_type not in _ALLOWED_RELATION_TYPES:
                continue
            try:
                await self.graph.execute_write(
                    "MATCH (src) WHERE src.name = $source "
                    "  AND (src:Company OR src:Skill OR src:Policy) "
                    "MATCH (tgt) WHERE tgt.name = $target "
                    "  AND (tgt:Company OR tgt:Skill OR tgt:Policy) "
                    "MERGE (src)-[r:ENTITY_RELATION {relation_type: $rel_type}]->(tgt) "
                    "SET r.source_doc = $doc_id, r.confidence = $confidence",
                    {
                        "source": rel.source,
                        "target": rel.target,
                        "rel_type": rel.relation_type,
                        "doc_id": doc_id,
                        "confidence": rel.confidence,
                    },
                )
                stored += 1
            except Exception:
                logger.warning(
                    "関係格納失敗: %s -[%s]-> %s",
                    rel.source, rel.relation_type, rel.target,
                )
        if stored:
            logger.info("Neo4jに%d件のエンティティ関係を格納", stored)
        return stored

    async def _extract_orgs_with_llm(self, text: str) -> list[str]:
        """文書テキストから組織名・サービス名を抽出する.

        1. LLMで抽出を試みる
        2. LLM失敗時は正規表現ベースのフォールバック
        """
        orgs: list[str] = []

        # LLM抽出
        try:
            from app.core.llm.router import LLMRouter, TaskType
            llm = LLMRouter()
            response = await llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=(
                    f"Text:\n{text[:1500]}\n\n"
                    "List all company/service/agency names that are **market players** "
                    "(competitors, partners, customers, regulators, investors).\n"
                    "EXCLUDE:\n"
                    "- Information sources cited in the text (e.g. Yahoo Finance, "
                    "Bloomberg, TechCrunch, Google Trends, Wikipedia)\n"
                    "- Development tools/platforms not competing in this market "
                    "(e.g. GitHub, GitLab, Stack Overflow)\n"
                    "- Research/consulting firms (e.g. McKinsey, Gartner)\n"
                    "Only include organizations that actively participate in the "
                    "market being discussed.\n"
                    '{"organizations":["Slack","Microsoft Teams","LINE WORKS"]}'
                ),
                system_prompt="Extract market player names. JSON only.",
            )
            raw = response.get("organizations", [])
            if isinstance(raw, list):
                orgs = [str(o).strip() for o in raw if o and len(str(o).strip()) > 1]
        except Exception:
            logger.warning("LLMによる組織名抽出失敗、正規表現フォールバック使用")

        # 正規表現フォールバック: 既知のサービス名・企業名をパターンマッチ
        if len(orgs) < 3:
            import re
            known_patterns = [
                r"Slack", r"Microsoft\s+Teams", r"Teams", r"LINE\s+WORKS",
                r"Chatwork", r"Google\s+Chat", r"Discord", r"Zoom",
                r"Salesforce", r"AWS", r"Azure", r"Google\s+Cloud",
                r"デジタル庁", r"総務省", r"金融庁", r"経済産業省",
                r"サイボウズ", r"freee", r"マネーフォワード",
                r"NTT", r"富士通", r"NEC", r"日立",
            ]
            found_regex = set(orgs)
            for pattern in known_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # パターンにマッチした実際のテキストを使う
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        name = match.group(0).strip()
                        if name not in found_regex:
                            orgs.append(name)
                            found_regex.add(name)
            if len(orgs) > len(found_regex) - len(set(orgs)):
                logger.info("正規表現で%d件の組織名を追加抽出", len(orgs))

        return orgs

    async def get_document_entities(self) -> dict[str, list[str]]:
        """このシミュレーションの文書から抽出された全エンティティを集約する."""
        results = await self.graph.execute_read(
            "MATCH (d:Document {simulation_id: $sim_id})-[:MENTIONS]->(e) "
            "RETURN labels(e)[0] AS type, collect(DISTINCT e.name) AS names",
            {"sim_id": self.simulation_id},
        )

        entities: dict[str, list[str]] = {
            "technologies": [],
            "organizations": [],
            "policies": [],
        }
        for row in results:
            node_type = row.get("type", "")
            names = row.get("names", [])
            if node_type == "Skill":
                entities["technologies"].extend(names)
            elif node_type == "Company":
                entities["organizations"].extend(names)
            elif node_type == "Policy":
                entities["policies"].extend(names)

        return entities

    async def get_document_detail(self, doc_id: str) -> dict[str, Any] | None:
        """文書の詳細と関連エンティティを取得する."""
        doc = await self.graph.execute_read(
            "MATCH (d:Document {doc_id: $doc_id}) "
            "RETURN d.doc_id AS doc_id, d.filename AS filename, "
            "       d.source AS source, d.text_length AS text_length, "
            "       d.page_count AS page_count, d.entity_count AS entity_count, "
            "       d.text_summary AS text_summary, "
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

    async def get_document_full_text(self, doc_id: str) -> str | None:
        """文書の全文テキストを取得する."""
        result = await self.graph.execute_read(
            "MATCH (d:Document {doc_id: $doc_id, simulation_id: $simulation_id}) "
            "RETURN d.full_text AS full_text",
            {"doc_id": doc_id, "simulation_id": self.simulation_id},
        )
        if not result:
            return None
        return result[0].get("full_text")
