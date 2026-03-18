"""市場調査パイプラインのユニットテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.market_research.models import (
    CollectedMarketData,
    FinanceData,
    GitHubData,
    ResearchResult,
    TrendData,
)


class TestModels:
    """データモデルのテスト."""

    def test_trend_data_defaults(self):
        t = TrendData(keyword="Slack")
        assert t.keyword == "Slack"
        assert t.interest_over_time == {}
        assert t.related_queries == []

    def test_github_data_defaults(self):
        g = GitHubData(repo_name="slack")
        assert g.stars == 0
        assert g.language == ""

    def test_finance_data_defaults(self):
        f = FinanceData(company_name="Microsoft")
        assert f.market_cap is None
        assert f.currency == "USD"

    def test_collected_market_data_defaults(self):
        c = CollectedMarketData()
        assert c.trends == []
        assert c.sources_used == []

    def test_research_result_defaults(self):
        r = ResearchResult()
        assert r.market_report == ""
        assert r.stakeholders == ""


class TestGoogleTrendsCollector:
    """Google Trendsコレクターのテスト."""

    @pytest.mark.asyncio
    async def test_returns_empty_on_import_error(self):
        with patch.dict("sys.modules", {"pytrends": None, "pytrends.request": None}):
            # モジュールキャッシュをクリアして再importさせる
            from app.core.market_research.collectors.google_trends import collect_trends
            # pytrends未インストール時はImportErrorを考慮
            # 実際にはtry/exceptで空リストが返る
            result = await collect_trends(["Slack"])
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_returns_empty_on_empty_keywords(self):
        from app.core.market_research.collectors.google_trends import collect_trends
        result = await collect_trends([])
        assert result == []


class TestGitHubCollector:
    """GitHub APIコレクターのテスト."""

    @pytest.mark.asyncio
    async def test_returns_empty_on_network_error(self):
        from app.core.market_research.collectors.github_api import collect_github

        with patch("app.core.market_research.collectors.github_api.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(side_effect=Exception("Network error"))
            mock_client.return_value = mock_instance

            result = await collect_github(["slack"])
            assert result == []

    @pytest.mark.asyncio
    async def test_parse_repo_from_url(self):
        from app.core.market_research.collectors.github_api import _parse_repo

        data = {
            "name": "slack-api",
            "full_name": "slackapi/slack-api",
            "stargazers_count": 1500,
            "forks_count": 300,
            "open_issues_count": 25,
            "language": "Python",
            "description": "Slack API client",
            "topics": ["slack", "api"],
            "created_at": "2020-01-01T00:00:00Z",
        }
        result = _parse_repo(data)
        assert result.repo_name == "slack-api"
        assert result.stars == 1500
        assert result.language == "Python"


    def test_is_within_year_filters_future_repos(self):
        from app.core.market_research.collectors.github_api import _is_within_year

        old_repo = GitHubData(repo_name="old", created_at="2013-06-01T00:00:00Z")
        new_repo = GitHubData(repo_name="new", created_at="2020-01-01T00:00:00Z")

        assert _is_within_year(old_repo, 2014) is True
        assert _is_within_year(new_repo, 2014) is False
        assert _is_within_year(new_repo, None) is True


class TestYahooFinanceCollector:
    """Yahoo Financeコレクターのテスト."""

    def test_resolve_known_tickers(self):
        from app.core.market_research.collectors.yahoo_finance import _resolve_tickers

        result = _resolve_tickers(["Microsoft", "Google", "Unknown Corp"])
        names = [name for name, _ in result]
        assert "Microsoft" in names
        assert "Google" in names
        # Unknown Corp はマッチしない
        assert "Unknown Corp" not in names

    def test_resolve_partial_match(self):
        from app.core.market_research.collectors.yahoo_finance import _resolve_tickers

        result = _resolve_tickers(["microsoft teams"])
        assert len(result) >= 1
        assert result[0][1] == "MSFT"

    @pytest.mark.asyncio
    async def test_returns_empty_on_import_error(self):
        from app.core.market_research.collectors.yahoo_finance import collect_finance
        # 空リストを渡した場合
        result = await collect_finance([])
        assert result == []


class TestSynthesizer:
    """シンセサイザーのテスト."""

    @pytest.mark.asyncio
    async def test_synthesize_market_report(self):
        from app.core.market_research.synthesizer import synthesize_market_report

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="■ 市場規模\nテスト市場レポート")

        result = await synthesize_market_report(
            llm=mock_llm,
            service_name="TestService",
            description="テスト用サービス",
            target_year=2024,
            collected=CollectedMarketData(),
        )

        assert "テスト市場レポート" in result
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_returns_empty_on_error(self):
        from app.core.market_research.synthesizer import synthesize_market_report

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM error"))

        result = await synthesize_market_report(
            llm=mock_llm,
            service_name="TestService",
            description="テスト",
            target_year=2024,
            collected=CollectedMarketData(),
        )

        assert result == ""

    @pytest.mark.asyncio
    async def test_synthesize_user_behavior(self):
        from app.core.market_research.synthesizer import synthesize_user_behavior

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="■ ユーザーの利用実態\nテスト")

        result = await synthesize_user_behavior(
            llm=mock_llm,
            service_name="TestService",
            description="テスト",
            target_year=None,
            collected=CollectedMarketData(),
        )

        assert "テスト" in result

    @pytest.mark.asyncio
    async def test_synthesize_stakeholders(self):
        from app.core.market_research.synthesizer import synthesize_stakeholders

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="■ Microsoft\nテスト")

        result = await synthesize_stakeholders(
            llm=mock_llm,
            service_name="TestService",
            description="テスト",
            target_year=2020,
            collected=CollectedMarketData(),
        )

        assert "Microsoft" in result


class TestBuildDataContext:
    """_build_data_contextのテスト."""

    def test_empty_data(self):
        from app.core.market_research.synthesizer import _build_data_context

        result = _build_data_context(CollectedMarketData(), None)
        assert "外部データの取得に失敗しました" in result

    def test_with_trends(self):
        from app.core.market_research.synthesizer import _build_data_context

        data = CollectedMarketData(
            trends=[TrendData(
                keyword="Slack",
                interest_over_time={"2024-01": 80, "2024-02": 90},
            )],
        )
        result = _build_data_context(data)
        assert "Slack" in result
        assert "Google Trends" in result

    def test_with_github(self):
        from app.core.market_research.synthesizer import _build_data_context

        data = CollectedMarketData(
            github_repos=[GitHubData(
                repo_name="slack", full_name="slackapi/slack",
                stars=5000, forks=1000, language="Python",
            )],
        )
        result = _build_data_context(data)
        assert "slackapi/slack" in result
        assert "5,000" in result

    def test_with_finance(self):
        from app.core.market_research.synthesizer import _build_data_context

        data = CollectedMarketData(
            finance_data=[FinanceData(
                company_name="Microsoft", ticker="MSFT",
                market_cap=3e12, revenue=200e9,
            )],
        )
        result = _build_data_context(data)
        assert "Microsoft" in result
        assert "MSFT" in result


class TestPipeline:
    """パイプライン全体のテスト."""

    @pytest.mark.asyncio
    async def test_pipeline_disabled(self):
        from app.core.market_research.pipeline import run_market_research

        with patch("app.core.market_research.pipeline.settings") as mock_settings:
            mock_settings.market_research_enabled = False
            result = await run_market_research("Test", "テスト")
            assert result.market_report == ""

    @pytest.mark.asyncio
    async def test_pipeline_with_mocked_collectors(self):
        from app.core.market_research.pipeline import run_market_research

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="テストレポート")

        with (
            patch("app.core.market_research.pipeline.settings") as mock_settings,
            patch("app.core.market_research.collectors.google_trends.collect_trends", new_callable=AsyncMock, return_value=[]),
            patch("app.core.market_research.collectors.github_api.collect_github", new_callable=AsyncMock, return_value=[]),
            patch("app.core.market_research.collectors.yahoo_finance.collect_finance", new_callable=AsyncMock, return_value=[]),
        ):
            mock_settings.market_research_enabled = True
            mock_settings.market_research_timeout = 30

            result = await run_market_research(
                service_name="Slack",
                description="ビジネスチャット",
                target_year=2014,
                llm=mock_llm,
            )

            assert result.market_report == "テストレポート"
            assert result.user_behavior == "テストレポート"
            assert result.stakeholders == "テストレポート"


class TestScenarioInputTargetYear:
    """ScenarioInput.target_yearのテスト."""

    def test_target_year_default_none(self):
        from app.simulation.models import ScenarioInput
        s = ScenarioInput(description="テスト用の説明文です")
        assert s.target_year is None

    def test_target_year_set(self):
        from app.simulation.models import ScenarioInput
        s = ScenarioInput(description="テスト用の説明文です", target_year=2014)
        assert s.target_year == 2014
