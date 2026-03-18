"""市場調査データモデル."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TrendData(BaseModel):
    """Google Trends から取得した検索関心度データ."""

    keyword: str
    interest_over_time: dict[str, float] = Field(
        default_factory=dict,
        description="日付(YYYY-MM) → 関心度(0-100)",
    )
    related_queries: list[str] = Field(default_factory=list)


class GitHubData(BaseModel):
    """GitHub API から取得したリポジトリ統計."""

    repo_name: str
    full_name: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    contributors_count: int = 0
    language: str = ""
    description: str = ""
    topics: list[str] = Field(default_factory=list)
    created_at: str = ""


class FinanceData(BaseModel):
    """Yahoo Finance から取得した企業財務データ."""

    company_name: str
    ticker: str = ""
    market_cap: float | None = None
    revenue: float | None = None
    stock_price: float | None = None
    currency: str = "USD"
    sector: str = ""


class CollectedMarketData(BaseModel):
    """全コレクターから収集された生データ."""

    trends: list[TrendData] = Field(default_factory=list)
    github_repos: list[GitHubData] = Field(default_factory=list)
    finance_data: list[FinanceData] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    """市場調査パイプラインの最終出力."""

    market_report: str = ""
    user_behavior: str = ""
    stakeholders: str = ""
    collected_data: CollectedMarketData = Field(
        default_factory=CollectedMarketData,
    )
