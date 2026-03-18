"""Yahoo Finance コレクター — 企業財務データを取得（対象年限定）."""

from __future__ import annotations

import asyncio
import logging

from app.core.market_research.models import FinanceData

logger = logging.getLogger(__name__)

# 主要IT企業のティッカーマッピング
_KNOWN_TICKERS: dict[str, str] = {
    # Big Tech
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "apple": "AAPL",
    "amazon": "AMZN",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    # SaaS / Enterprise
    "salesforce": "CRM",
    "slack": "WORK",
    "atlassian": "TEAM",
    "zoom": "ZM",
    "shopify": "SHOP",
    "twilio": "TWLO",
    "cloudflare": "NET",
    "datadog": "DDOG",
    "snowflake": "SNOW",
    "palantir": "PLTR",
    "adobe": "ADBE",
    "oracle": "ORCL",
    "ibm": "IBM",
    "sap": "SAP",
    "servicenow": "NOW",
    "workday": "WDAY",
    "hubspot": "HUBS",
    "dropbox": "DBX",
    "docusign": "DOCU",
    "okta": "OKTA",
    "crowdstrike": "CRWD",
    "palo alto": "PANW",
    "splunk": "SPLK",
    "confluent": "CFLT",
    "mongodb": "MDB",
    "elastic": "ESTC",
    "gitlab": "GTLB",
    "hashicorp": "HCP",
    # Mobility / Marketplace
    "uber": "UBER",
    "lyft": "LYFT",
    "airbnb": "ABNB",
    "doordash": "DASH",
    # Hardware / Semiconductor
    "cisco": "CSCO",
    "intel": "INTC",
    "amd": "AMD",
    "qualcomm": "QCOM",
    # Japan
    "sony": "SONY",
    "ntt": "9432.T",
    "softbank": "9984.T",
    "toyota": "TM",
    "rakuten": "4755.T",
    "chatwork": "4448.T",
    "cybozu": "4776.T",
}


async def collect_finance(
    company_names: list[str],
    target_year: int | None = None,
) -> list[FinanceData]:
    """Yahoo Finance から対象年時点の企業財務データを取得する.

    現在のデータ(info)は使わず、対象年の株価履歴から時価総額を推定する。
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance未インストール、スキップ")
        return []

    tickers = _resolve_tickers(company_names)
    if not tickers:
        return []

    def _fetch() -> list[FinanceData]:
        results: list[FinanceData] = []
        for name, ticker in tickers[:5]:
            try:
                stock = yf.Ticker(ticker)

                # 対象年の株価履歴のみ使用（現在のinfoは使わない）
                year = target_year or 2024
                hist = stock.history(
                    start=f"{year}-01-01",
                    end=f"{year}-12-31",
                )

                if hist is None or hist.empty:
                    logger.info("Yahoo Finance: %s の%d年データなし", ticker, year)
                    continue

                stock_price = float(hist["Close"].iloc[-1])

                # 発行済株式数からその時点の時価総額を推定
                shares = (stock.info or {}).get("sharesOutstanding")
                market_cap = stock_price * shares if shares else None

                # sectorは時代を問わない静的情報なので使用可
                sector = (stock.info or {}).get("sector", "")

                results.append(FinanceData(
                    company_name=name,
                    ticker=ticker,
                    market_cap=market_cap,
                    revenue=None,  # 現在の値しか取れないため使用しない
                    stock_price=stock_price,
                    currency=(stock.info or {}).get("currency", "USD"),
                    sector=sector,
                ))
            except Exception as e:
                logger.warning("Yahoo Finance取得失敗 %s: %s", ticker, e)

        return results

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=25,
        )
    except asyncio.TimeoutError:
        logger.warning("Yahoo Financeタイムアウト")
        return []


async def collect_finance_direct(
    tickers: list[tuple[str, str]],
    target_year: int | None = None,
) -> list[FinanceData]:
    """LLMが抽出したティッカーリストから直接Yahoo Financeデータを取得する.

    _resolve_tickers を経由せず、ティッカーシンボルを直接使う。
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance未インストール、スキップ")
        return []

    if not tickers:
        return []

    def _fetch() -> list[FinanceData]:
        results: list[FinanceData] = []
        for name, ticker in tickers[:8]:
            try:
                stock = yf.Ticker(ticker)
                year = target_year or 2024

                hist = stock.history(
                    start=f"{year}-01-01",
                    end=f"{year}-12-31",
                )

                if hist is None or hist.empty:
                    logger.info("Yahoo Finance: %s (%s) の%d年データなし", name, ticker, year)
                    continue

                stock_price = float(hist["Close"].iloc[-1])

                shares = (stock.info or {}).get("sharesOutstanding")
                market_cap = stock_price * shares if shares else None
                sector = (stock.info or {}).get("sector", "")

                results.append(FinanceData(
                    company_name=name,
                    ticker=ticker,
                    market_cap=market_cap,
                    revenue=None,
                    stock_price=stock_price,
                    currency=(stock.info or {}).get("currency", "USD"),
                    sector=sector,
                ))
            except Exception as e:
                logger.warning("Yahoo Finance取得失敗 %s (%s): %s", name, ticker, e)

        return results

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=30,
        )
    except asyncio.TimeoutError:
        logger.warning("Yahoo Financeタイムアウト")
        return []


def _resolve_tickers(names: list[str]) -> list[tuple[str, str]]:
    """企業名をティッカーシンボルに解決する."""
    resolved: list[tuple[str, str]] = []
    for name in names:
        key = name.lower().strip()
        # 完全一致
        if key in _KNOWN_TICKERS:
            resolved.append((name, _KNOWN_TICKERS[key]))
            continue
        # 部分一致
        for known, ticker in _KNOWN_TICKERS.items():
            if known in key or key in known:
                resolved.append((name, ticker))
                break
    return resolved
