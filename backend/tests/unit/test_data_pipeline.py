"""Tests for data collection pipeline and e-Stat client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.data_sources.estat import EStatClient, _extract_text, _extract_year
from app.core.data_sources.models import CollectResult, StatRecord
from app.core.data_sources.pipeline import DataCollectionPipeline


class TestEStatHelpers:
    def test_extract_text_string(self):
        assert _extract_text("テスト") == "テスト"

    def test_extract_text_dict(self):
        assert _extract_text({"$": "テスト値"}) == "テスト値"

    def test_extract_year_valid(self):
        assert _extract_year("2023000000") == 2023
        assert _extract_year("2020100000") == 2020

    def test_extract_year_invalid(self):
        assert _extract_year("") == 0
        assert _extract_year("abc") == 0


class TestEStatClient:
    def test_is_configured_with_key(self):
        client = EStatClient(api_key="test-key")
        assert client.is_configured is True

    def test_is_configured_without_key(self):
        with patch("app.core.data_sources.estat.settings") as mock_settings:
            mock_settings.estat_api_key = ""
            client = EStatClient(api_key="")
            assert client.is_configured is False

    @pytest.mark.asyncio
    async def test_collect_ict_stats_without_key(self):
        client = EStatClient(api_key="")
        records = await client.collect_ict_stats()
        assert records == []


class TestStatRecord:
    def test_create(self):
        record = StatRecord(
            name="test_record",
            source="test",
            year=2023,
            value=100.0,
        )
        assert record.name == "test_record"
        assert record.unit == "人"  # default

    def test_with_metadata(self):
        record = StatRecord(
            name="test",
            source="e-Stat",
            year=2023,
            value=42.0,
            metadata={"key": "value"},
        )
        assert record.metadata["key"] == "value"


class TestDataCollectionPipeline:
    def _make_pipeline(self, graph_read_return=None):
        graph = MagicMock()
        graph.execute_read = AsyncMock(return_value=graph_read_return or [])
        graph.execute_write = AsyncMock(return_value=[])
        estat = MagicMock()
        estat.is_configured = False
        estat.collect_ict_stats = AsyncMock(return_value=[])
        return DataCollectionPipeline(graph, estat), graph

    @pytest.mark.asyncio
    async def test_run_without_estat(self):
        """e-Stat APIキーなしでも静的データは投入される."""
        pipeline, graph = self._make_pipeline()
        result = await pipeline.run()

        assert result.total_records > 0  # 静的データがある
        assert "static_reference" in result.sources
        assert graph.execute_write.call_count > 0

    @pytest.mark.asyncio
    async def test_static_records_exist(self):
        pipeline, _ = self._make_pipeline()
        records = pipeline._get_static_records()

        assert len(records) >= 5
        # IT人材数のデータがある
        names = {r.name for r in records}
        assert "ipa_it_engineers_2023" in names

    @pytest.mark.asyncio
    async def test_get_data_status(self):
        """get_data_statusが3回のクエリを実行する."""
        graph = MagicMock()
        # 3回のexecute_readに異なる返値を設定
        graph.execute_read = AsyncMock(side_effect=[
            [{"source": "e-Stat", "category": "labor", "count": 5, "latest_year": 2023}],
            [{"total": 10}],
            [{"total_links": 3}],
        ])
        graph.execute_write = AsyncMock(return_value=[])
        estat = MagicMock()
        estat.is_configured = False
        pipeline = DataCollectionPipeline(graph, estat)
        status = await pipeline.get_data_status()
        assert status["total_records"] == 10
        assert status["total_links"] == 3

    @pytest.mark.asyncio
    async def test_run_with_estat_error(self):
        """e-Stat APIエラー時もクラッシュせず静的データは投入される."""
        graph = MagicMock()
        graph.execute_read = AsyncMock(return_value=[])
        graph.execute_write = AsyncMock(return_value=[])
        estat = MagicMock()
        estat.is_configured = True
        estat.collect_ict_stats = AsyncMock(side_effect=RuntimeError("API Error"))

        pipeline = DataCollectionPipeline(graph, estat)
        result = await pipeline.run()

        assert len(result.errors) > 0
        assert result.stored_records > 0  # 静的データは成功
