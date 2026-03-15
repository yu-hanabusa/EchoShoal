"""GitHub README自動取得 — URLからREADMEコンテンツを取得する."""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_GITHUB_REPO_PATTERN = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"
)

_GITHUB_API_TIMEOUT = 15.0


async def fetch_github_readme(url: str) -> str | None:
    """GitHub URLからREADMEのプレーンテキストを取得する.

    Args:
        url: GitHub リポジトリURL (e.g. "https://github.com/owner/repo")

    Returns:
        READMEのテキスト内容、取得失敗時はNone
    """
    match = _GITHUB_REPO_PATTERN.match(url.strip())
    if not match:
        logger.info("GitHub URLパターンに一致しません: %s", url)
        return None

    owner, repo = match.group(1), match.group(2)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"

    try:
        async with httpx.AsyncClient(timeout=_GITHUB_API_TIMEOUT) as client:
            response = await client.get(
                api_url,
                headers={
                    "Accept": "application/vnd.github.raw",
                    "User-Agent": "EchoShoal/1.0",
                },
            )
            response.raise_for_status()
            content = response.text
            if content:
                logger.info("GitHub README取得成功: %s/%s (%d chars)", owner, repo, len(content))
                return content
    except httpx.HTTPStatusError as exc:
        logger.warning("GitHub API HTTP error: %s - %d", url, exc.response.status_code)
    except httpx.RequestError as exc:
        logger.warning("GitHub API request error: %s - %s", url, exc)
    except Exception:
        logger.warning("GitHub README取得失敗: %s", url)

    return None


def is_github_url(url: str | None) -> bool:
    """URLがGitHubリポジトリURLかどうかを判定する."""
    if not url:
        return False
    return bool(_GITHUB_REPO_PATTERN.match(url.strip()))
