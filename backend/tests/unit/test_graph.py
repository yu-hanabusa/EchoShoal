"""Neo4j グラフクライアントのユニットテスト（モック使用）."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.graph.client import GraphClient
from app.core.graph.schema import (
    KnowledgeGraphRepository,
    SCHEMA_CONSTRAINTS,
    SEED_INDUSTRIES,
    SEED_SKILL_CATEGORIES,
    SEED_ROLES,
    initialize_schema,
    seed_initial_data,
)


class TestGraphClient:
    def test_init_defaults(self):
        client = GraphClient()
        assert client._driver is None

    @pytest.mark.asyncio
    async def test_is_available_returns_false_on_error(self):
        client = GraphClient(uri="bolt://nonexistent:9999")
        # 接続失敗時は False を返す
        result = await client.is_available()
        assert result is False

    @pytest.mark.asyncio
    async def test_close_without_connect(self):
        client = GraphClient()
        await client.close()  # エラーにならないこと
        assert client._driver is None


class TestSchemaConstants:
    def test_constraints_count(self):
        assert len(SCHEMA_CONSTRAINTS) == 8  # 6 original + StatRecord + Agent

    def test_seed_industries_count(self):
        assert len(SEED_INDUSTRIES) == 5

    def test_seed_skill_categories_count(self):
        assert len(SEED_SKILL_CATEGORIES) == 8

    def test_seed_roles_count(self):
        assert len(SEED_ROLES) == 8

    def test_all_industries_have_required_fields(self):
        for ind in SEED_INDUSTRIES:
            assert "name" in ind
            assert "label_ja" in ind
            assert "description" in ind

    def test_all_categories_have_skills(self):
        for cat in SEED_SKILL_CATEGORIES:
            assert "name" in cat
            assert "skills" in cat
            assert len(cat["skills"]) >= 3


class TestInitializeSchema:
    @pytest.mark.asyncio
    async def test_calls_execute_write_for_each_constraint(self):
        mock_client = MagicMock(spec=GraphClient)
        mock_client.execute_write = AsyncMock()

        await initialize_schema(mock_client)

        assert mock_client.execute_write.call_count == len(SCHEMA_CONSTRAINTS)


class TestSeedInitialData:
    @pytest.mark.asyncio
    async def test_seeds_all_data(self):
        mock_client = MagicMock(spec=GraphClient)
        mock_client.execute_write = AsyncMock()

        await seed_initial_data(mock_client)

        # 業界 + カテゴリ + カテゴリ内スキル + 職種
        total_skills = sum(len(cat["skills"]) for cat in SEED_SKILL_CATEGORIES)
        expected_calls = (
            len(SEED_INDUSTRIES)
            + len(SEED_SKILL_CATEGORIES)
            + total_skills
            + len(SEED_ROLES)
        )
        assert mock_client.execute_write.call_count == expected_calls


class TestKnowledgeGraphRepository:
    @pytest.mark.asyncio
    async def test_get_skills_by_category(self):
        mock_client = MagicMock(spec=GraphClient)
        mock_client.execute_read = AsyncMock(return_value=[
            {"name": "Python"}, {"name": "Go"}
        ])

        repo = KnowledgeGraphRepository(mock_client)
        result = await repo.get_skills_by_category("web_backend")

        assert len(result) == 2
        mock_client.execute_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_company(self):
        mock_client = MagicMock(spec=GraphClient)
        mock_client.execute_write = AsyncMock()

        repo = KnowledgeGraphRepository(mock_client)
        await repo.add_company("テスト企業", "ses", {"size": "large"})

        mock_client.execute_write.assert_called_once()
        # パラメータ辞書は第2位置引数
        params = mock_client.execute_write.call_args[0][1]
        assert params["name"] == "テスト企業"
        assert params["industry"] == "ses"

    @pytest.mark.asyncio
    async def test_add_skill_relation_invalid_type(self):
        mock_client = MagicMock(spec=GraphClient)
        repo = KnowledgeGraphRepository(mock_client)

        with pytest.raises(ValueError, match="無効な関係タイプ"):
            await repo.add_skill_relation("Python", "Go", "INVALID")

    @pytest.mark.asyncio
    async def test_add_policy(self):
        mock_client = MagicMock(spec=GraphClient)
        mock_client.execute_write = AsyncMock()

        repo = KnowledgeGraphRepository(mock_client)
        await repo.add_policy(
            "DX推進法",
            "デジタル変革を推進する法律",
            [{"type": "Industry", "name": "enterprise_it", "impact_type": "positive", "magnitude": 0.8}],
        )

        assert mock_client.execute_write.call_count == 2  # ポリシー作成 + 影響先紐付け

    @pytest.mark.asyncio
    async def test_get_full_ontology(self):
        mock_client = MagicMock(spec=GraphClient)
        mock_client.execute_read = AsyncMock(return_value=[])

        repo = KnowledgeGraphRepository(mock_client)
        result = await repo.get_full_ontology()

        assert "industries" in result
        assert "skill_categories" in result
        assert "roles" in result
        assert "policies" in result
        assert mock_client.execute_read.call_count == 4
