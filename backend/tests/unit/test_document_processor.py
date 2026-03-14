"""Tests for document processor (NLP → knowledge graph pipeline)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.documents.models import ParsedDocument, ProcessResult
from app.core.documents.processor import DocumentProcessor


class TestDocumentProcessor:
    def _make_processor(self, graph_read_return=None):
        graph = MagicMock()
        graph.execute_read = AsyncMock(return_value=graph_read_return or [])
        graph.execute_write = AsyncMock(return_value=[{"created_by": None}])

        # NLPアナライザをモック
        nlp = MagicMock()
        mock_result = MagicMock()
        mock_result.technologies = ["Python", "AWS"]
        mock_result.organizations = ["NTTデータ"]
        mock_result.policies = ["DX推進法"]
        mock_result.keywords = ["IT人材", "クラウド"]
        mock_result.entities = [MagicMock()] * 4  # 4 entities total
        nlp.analyze.return_value = mock_result

        return DocumentProcessor(graph, nlp), graph, nlp

    def _make_doc(self):
        return ParsedDocument(
            filename="test_report.txt",
            text="PythonとAWSを使った開発がNTTデータで増えている。DX推進法の影響。",
            source="テストソース",
        )

    @pytest.mark.asyncio
    async def test_process_creates_document_node(self):
        proc, graph, _ = self._make_processor()
        doc = self._make_doc()

        result = await proc.process(doc)

        # Documentノード作成のMERGEが呼ばれた
        write_calls = graph.execute_write.call_args_list
        assert any("Document" in str(c) for c in write_calls)

    @pytest.mark.asyncio
    async def test_process_returns_result(self):
        proc, _, _ = self._make_processor()
        doc = self._make_doc()

        result = await proc.process(doc)

        assert isinstance(result, ProcessResult)
        assert result.document_id == doc.id
        assert result.filename == "test_report.txt"
        assert "Python" in result.technologies
        assert "AWS" in result.technologies
        assert "NTTデータ" in result.organizations
        assert "DX推進法" in result.policies

    @pytest.mark.asyncio
    async def test_process_links_technologies(self):
        proc, graph, _ = self._make_processor()
        doc = self._make_doc()

        await proc.process(doc)

        # Skill MERGEが呼ばれた
        write_calls = [str(c) for c in graph.execute_write.call_args_list]
        assert any("Skill" in c for c in write_calls)
        assert any("MENTIONS" in c for c in write_calls)

    @pytest.mark.asyncio
    async def test_process_links_organizations(self):
        proc, graph, _ = self._make_processor()
        doc = self._make_doc()

        await proc.process(doc)

        write_calls = [str(c) for c in graph.execute_write.call_args_list]
        assert any("Company" in c for c in write_calls)

    @pytest.mark.asyncio
    async def test_process_links_policies(self):
        proc, graph, _ = self._make_processor()
        doc = self._make_doc()

        await proc.process(doc)

        write_calls = [str(c) for c in graph.execute_write.call_args_list]
        assert any("Policy" in c for c in write_calls)

    @pytest.mark.asyncio
    async def test_entities_found_count(self):
        proc, _, _ = self._make_processor()
        doc = self._make_doc()

        result = await proc.process(doc)

        # Python, AWS + NTTデータ + DX推進法 = 4
        assert result.entities_found == 4

    @pytest.mark.asyncio
    async def test_get_documents_empty(self):
        proc, _, _ = self._make_processor()
        docs = await proc.get_documents()
        assert docs == []

    @pytest.mark.asyncio
    async def test_get_documents_returns_list(self):
        proc, graph, _ = self._make_processor(graph_read_return=[
            {
                "doc_id": "abc",
                "filename": "test.txt",
                "source": "src",
                "text_length": 100,
                "entity_count": 5,
                "uploaded_at": "2024-01-01",
            }
        ])
        docs = await proc.get_documents()
        assert len(docs) == 1
        assert docs[0].doc_id == "abc"

    @pytest.mark.asyncio
    async def test_get_document_detail_not_found(self):
        proc, _, _ = self._make_processor()
        detail = await proc.get_document_detail("nonexistent")
        assert detail is None

    @pytest.mark.asyncio
    async def test_get_document_detail_found(self):
        graph = MagicMock()
        graph.execute_read = AsyncMock(side_effect=[
            [{"doc_id": "abc", "filename": "test.txt", "source": "src",
              "text_length": 100, "page_count": 1, "entity_count": 2,
              "uploaded_at": "2024-01-01"}],
            [{"type": "Skill", "name": "Python"}, {"type": "Policy", "name": "DX推進法"}],
        ])
        proc = DocumentProcessor(graph)
        detail = await proc.get_document_detail("abc")
        assert detail is not None
        assert detail["doc_id"] == "abc"
        assert len(detail["mentions"]) == 2
