"""GitHub API コレクター — リポジトリ統計データを取得（対象年限定）."""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.core.market_research.models import GitHubData

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"


async def collect_github(
    keywords: list[str],
    service_url: str | None = None,
    target_year: int | None = None,
) -> list[GitHubData]:
    """GitHub API からリポジトリ統計を取得する.

    target_yearが指定された場合、その年以前に作成されたリポジトリのみを返す。
    Star数等は現在値だが、注記付きで返す。
    """
    results: list[GitHubData] = []
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_api_token:
        headers["Authorization"] = f"token {settings.github_api_token}"

    try:
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            # 直接URLがあればそのリポジトリを取得
            if service_url and "github.com/" in service_url:
                repo_data = await _fetch_repo_from_url(client, service_url)
                if repo_data and _is_within_year(repo_data, target_year):
                    results.append(repo_data)

            # キーワードで検索
            created_filter = f" created:<={target_year}-12-31" if target_year else ""
            for kw in keywords[:3]:
                repos = await _search_repos(client, kw, created_filter)
                for repo in repos:
                    if not any(r.full_name == repo.full_name for r in results):
                        results.append(repo)
                        if len(results) >= 5:
                            break
                if len(results) >= 5:
                    break

    except Exception as e:
        logger.warning("GitHub API取得失敗: %s", e)

    return results


def _is_within_year(repo: GitHubData, target_year: int | None) -> bool:
    """リポジトリが対象年以前に作成されたかチェックする."""
    if target_year is None:
        return True
    if not repo.created_at:
        return True
    try:
        created_year = int(repo.created_at[:4])
        return created_year <= target_year
    except (ValueError, IndexError):
        return True


async def _fetch_repo_from_url(
    client: httpx.AsyncClient, url: str,
) -> GitHubData | None:
    """GitHub URLからリポジトリ情報を取得."""
    try:
        parts = url.rstrip("/").split("github.com/")
        if len(parts) < 2:
            return None
        repo_path = parts[1].split("/")
        if len(repo_path) < 2:
            return None
        owner, repo = repo_path[0], repo_path[1]

        resp = await client.get(f"{_GITHUB_API}/repos/{owner}/{repo}")
        if resp.status_code != 200:
            return None
        return _parse_repo(resp.json())
    except Exception:
        return None


async def _search_repos(
    client: httpx.AsyncClient, query: str, created_filter: str = "",
) -> list[GitHubData]:
    """GitHub Search APIでリポジトリを検索."""
    try:
        full_query = f"{query}{created_filter}"
        resp = await client.get(
            f"{_GITHUB_API}/search/repositories",
            params={"q": full_query, "sort": "stars", "per_page": 2},
        )
        if resp.status_code != 200:
            return []
        items = resp.json().get("items", [])
        return [_parse_repo(item) for item in items]
    except Exception:
        return []


def _parse_repo(data: dict) -> GitHubData:
    """GitHub APIレスポンスをGitHubDataに変換."""
    return GitHubData(
        repo_name=data.get("name", ""),
        full_name=data.get("full_name", ""),
        stars=data.get("stargazers_count", 0),
        forks=data.get("forks_count", 0),
        open_issues=data.get("open_issues_count", 0),
        language=data.get("language", "") or "",
        description=data.get("description", "") or "",
        topics=data.get("topics", []) or [],
        created_at=data.get("created_at", ""),
    )
