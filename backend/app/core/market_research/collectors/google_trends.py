"""Google Trends コレクター — 検索関心度の時系列データを取得."""

from __future__ import annotations

import asyncio
import logging
import time

from app.core.market_research.models import TrendData

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_RETRY_WAIT = 5  # seconds


async def collect_trends(
    keywords: list[str],
    target_year: int | None = None,
) -> list[TrendData]:
    """Google Trends から検索関心度を取得する.

    対象年が指定された場合、リリース前の市場動向を把握するため
    対象年の「前年」までのトレンドを取得する。
    （対象年にリリースされるサービスにとって、対象年以降のデータは未来の情報）

    429 Too Many Requests の場合は最大2回リトライする。

    Args:
        keywords: 検索キーワードリスト（最大5件）
        target_year: 対象年。Noneなら直近12ヶ月
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("pytrends未インストール、スキップ")
        return []

    keywords = keywords[:5]
    if not keywords:
        return []

    if target_year:
        # 対象年の前年までの2年間を取得（リリース前の市場動向）
        timeframe = f"{target_year - 2}-01-01 {target_year - 1}-12-31"
    else:
        timeframe = "today 12-m"

    def _fetch() -> list[TrendData]:
        results: list[TrendData] = []

        for attempt in range(_MAX_RETRIES + 1):
            try:
                pytrends = TrendReq(hl="ja-JP", tz=540, timeout=(10, 25))
                pytrends.build_payload(keywords, timeframe=timeframe)

                interest = pytrends.interest_over_time()
                if interest is None or interest.empty:
                    return results

                for kw in keywords:
                    if kw not in interest.columns:
                        continue
                    series = interest[kw]
                    interest_dict = {
                        d.strftime("%Y-%m"): float(v)
                        for d, v in series.items()
                        if str(d) != "isPartial"
                    }
                    results.append(TrendData(
                        keyword=kw,
                        interest_over_time=interest_dict,
                    ))

                # 関連クエリ（最初のキーワードのみ）
                try:
                    related = pytrends.related_queries()
                    if related and keywords[0] in related:
                        top = related[keywords[0]].get("top")
                        if top is not None and not top.empty:
                            queries = top["query"].tolist()[:10]
                            if results:
                                results[0].related_queries = queries
                except Exception:
                    pass

                return results

            except Exception as e:
                is_rate_limit = "429" in str(e)
                if is_rate_limit and attempt < _MAX_RETRIES:
                    logger.info(
                        "Google Trendsレート制限、%d秒後にリトライ (%d/%d)",
                        _RETRY_WAIT, attempt + 1, _MAX_RETRIES,
                    )
                    time.sleep(_RETRY_WAIT)
                    continue
                logger.warning("Google Trends取得失敗: %s", e)
                return results

        return results

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=30,
        )
    except asyncio.TimeoutError:
        logger.warning("Google Trendsタイムアウト")
        return []
