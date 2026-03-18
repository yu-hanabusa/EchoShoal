"""市場調査パイプライン — データ収集 → LLM合成 → 結果返却."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.config import settings
from app.core.llm.router import LLMRouter, TaskType
from app.core.market_research.models import CollectedMarketData, ResearchResult

logger = logging.getLogger(__name__)


async def run_market_research(
    service_name: str,
    description: str,
    target_year: int | None = None,
    competitors: list[str] | None = None,
    service_url: str | None = None,
    llm: LLMRouter | None = None,
) -> ResearchResult:
    """市場調査パイプラインを実行する.

    1. LLMで関連する上場企業ティッカーを動的に抽出
    2. 並列データ収集（Google Trends, GitHub, Yahoo Finance）
    3. LLM合成（3レポート生成）
    """
    if not settings.market_research_enabled:
        return ResearchResult()

    if llm is None:
        llm = LLMRouter()

    if target_year is None:
        target_year = datetime.now().year

    # 1. キーワード構築 + LLMでティッカー抽出
    keywords = _build_keywords(service_name, competitors or [])
    tickers = await _resolve_tickers_with_llm(
        llm, service_name, description, target_year, competitors or [],
    )

    logger.info(
        "市場調査開始: service=%s, year=%d, keywords=%s, tickers=%s",
        service_name, target_year, keywords, tickers,
    )

    # 2. 並列データ収集
    collected = await _collect_all(
        keywords=keywords,
        tickers=tickers,
        target_year=target_year,
        service_url=service_url,
    )

    logger.info(
        "データ収集完了: trends=%d, github=%d, finance=%d, errors=%d",
        len(collected.trends),
        len(collected.github_repos),
        len(collected.finance_data),
        len(collected.errors),
    )

    # 3. LLM合成
    from app.core.market_research.synthesizer import (
        synthesize_market_report,
        synthesize_stakeholders,
        synthesize_user_behavior,
    )

    market_report, user_behavior, stakeholders = await asyncio.gather(
        synthesize_market_report(llm, service_name, description, target_year, collected),
        synthesize_user_behavior(llm, service_name, description, target_year, collected),
        synthesize_stakeholders(llm, service_name, description, target_year, collected),
    )

    return ResearchResult(
        market_report=market_report,
        user_behavior=user_behavior,
        stakeholders=stakeholders,
        collected_data=collected,
    )


async def _resolve_tickers_with_llm(
    llm: LLMRouter,
    service_name: str,
    description: str,
    target_year: int,
    competitors: list[str],
) -> list[tuple[str, str]]:
    """LLMに関連する上場企業のティッカーシンボルを抽出させる.

    Returns:
        (企業名, ティッカー) のリスト
    """
    competitor_text = ""
    if competitors:
        competitor_text = f"\n既知の競合: {', '.join(competitors)}"

    prompt = (
        f"サービス「{service_name}」（{description}）について、\n"
        f"{target_year}年時点でこの市場に関連する主要な上場企業を5〜8社挙げてください。\n"
        f"{competitor_text}\n\n"
        "以下の条件を守ってください:\n"
        f"- {target_year}年時点で上場していた企業のみ（未上場企業は除外）\n"
        "- 直接の競合だけでなく、プラットフォーム提供者、インフラ企業、買収候補なども含む\n"
        "- 米国株のティッカーシンボルで返す（日本企業は.Tを付ける）\n\n"
        "JSON形式で返してください:\n"
        '{"tickers": [{"name": "Microsoft", "ticker": "MSFT"}, {"name": "Cisco", "ticker": "CSCO"}]}'
    )

    try:
        response = await llm.generate_json(
            task_type=TaskType.AGENT_DECISION,
            prompt=prompt,
            system_prompt=(
                f"あなたは{target_year}年時点の株式アナリストです。"
                "指定されたサービスの市場に関連する上場企業のティッカーを正確に返してください。"
            ),
        )
        raw = response.get("tickers", [])
        if not isinstance(raw, list):
            return []

        result: list[tuple[str, str]] = []
        for item in raw:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                ticker = str(item.get("ticker", "")).strip().upper()
                if name and ticker and len(ticker) <= 6:
                    result.append((name, ticker))
        logger.info("LLMが%d社のティッカーを抽出: %s", len(result), result)
        return result[:8]

    except Exception as e:
        logger.warning("LLMティッカー抽出失敗: %s", e)
        return []


async def _collect_all(
    keywords: list[str],
    tickers: list[tuple[str, str]],
    target_year: int,
    service_url: str | None,
) -> CollectedMarketData:
    """全コレクターを並列実行する."""
    from app.core.market_research.collectors.github_api import collect_github
    from app.core.market_research.collectors.google_trends import collect_trends
    from app.core.market_research.collectors.yahoo_finance import collect_finance

    collected = CollectedMarketData()

    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                collect_trends(keywords, target_year),
                collect_github(keywords, service_url, target_year),
                collect_finance_by_tickers(tickers, target_year),
                return_exceptions=True,
            ),
            timeout=settings.market_research_timeout,
        )

        # Google Trends
        if isinstance(results[0], list):
            collected.trends = results[0]
            if results[0]:
                collected.sources_used.append("Google Trends")
        elif isinstance(results[0], Exception):
            collected.errors.append(f"Google Trends: {results[0]}")

        # GitHub
        if isinstance(results[1], list):
            collected.github_repos = results[1]
            if results[1]:
                collected.sources_used.append("GitHub API")
        elif isinstance(results[1], Exception):
            collected.errors.append(f"GitHub: {results[1]}")

        # Yahoo Finance
        if isinstance(results[2], list):
            collected.finance_data = results[2]
            if results[2]:
                collected.sources_used.append("Yahoo Finance")
        elif isinstance(results[2], Exception):
            collected.errors.append(f"Yahoo Finance: {results[2]}")

    except asyncio.TimeoutError:
        collected.errors.append("データ収集全体がタイムアウト")
    except Exception as e:
        collected.errors.append(f"データ収集エラー: {e}")

    return collected


async def collect_finance_by_tickers(
    tickers: list[tuple[str, str]],
    target_year: int,
) -> list:
    """LLMが抽出したティッカーリストからYahoo Financeデータを取得."""
    from app.core.market_research.collectors.yahoo_finance import collect_finance_direct

    return await collect_finance_direct(tickers, target_year)


def _build_keywords(service_name: str, competitors: list[str]) -> list[str]:
    """検索キーワードリストを構築する."""
    keywords: list[str] = []
    if service_name:
        keywords.append(service_name)
    for comp in competitors:
        if comp and comp not in keywords:
            keywords.append(comp)
    return keywords[:5]
