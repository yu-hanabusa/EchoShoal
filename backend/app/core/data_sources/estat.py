"""e-Stat API v3 クライアント.

政府統計の総合窓口（e-Stat）からIT人材関連の統計データを取得する。
API仕様: https://www.e-stat.go.jp/api/api-info/e-stat-manual3-0

取得対象:
- 賃金構造基本統計調査（情報通信業の従業者数・平均給与）
- 労働力調査（IT関連職種の就業者数）
- 経済センサス（情報通信業の事業所数）
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.core.data_sources.models import StatMeta, StatRecord

logger = logging.getLogger(__name__)

# IT人材関連の主要統計テーブルID
# e-Stat で事前に調査し、安定して利用可能なIDを定義
KNOWN_STAT_TABLES: dict[str, dict[str, str]] = {
    # 賃金構造基本統計調査: 産業別の常用労働者数・給与
    "wage_structure": {
        "stats_id": "0003084610",
        "description": "賃金構造基本統計調査 - 産業別きまって支給する現金給与額",
        "category": "labor",
    },
    # 労働力調査: 職業別就業者数
    "labor_force": {
        "stats_id": "0003031152",
        "description": "労働力調査 - 職業別就業者数",
        "category": "labor",
    },
    # 経済センサス: 産業別事業所数
    "economic_census": {
        "stats_id": "0003234671",
        "description": "経済センサス - 産業別事業所数・従業者数",
        "category": "industry",
    },
}

# 情報通信業をフィルタするためのカテゴリコード（産業分類）
_ICT_INDUSTRY_CODES = {
    "G": "情報通信業",
    "37": "通信業",
    "38": "放送業",
    "39": "情報サービス業",
    "40": "インターネット附随サービス業",
    "391": "ソフトウェア業",
    "392": "情報処理・提供サービス業",
}


class EStatClient:
    """e-Stat API v3 非同期クライアント."""

    BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.estat_api_key
        if not self._api_key:
            logger.warning("e-Stat APIキーが未設定です（ECHOSHOAL_ESTAT_API_KEY）")

    @property
    def is_configured(self) -> bool:
        """APIキーが設定済みか."""
        return bool(self._api_key)

    async def search_stats(self, keyword: str, limit: int = 10) -> list[StatMeta]:
        """統計表をキーワード検索する."""
        if not self.is_configured:
            return []

        params = {
            "appId": self._api_key,
            "lang": "J",
            "searchWord": keyword,
            "limit": str(limit),
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/json/getStatsList", params=params
                )
                resp.raise_for_status()
                data = resp.json()

            result_info = data.get("GET_STATS_LIST", {}).get("DATALIST_INF", {})
            tables = result_info.get("TABLE_INF", [])
            if isinstance(tables, dict):
                tables = [tables]

            return [
                StatMeta(
                    stats_id=t.get("@id", ""),
                    title=_extract_text(t.get("TITLE", "")),
                    survey_name=_extract_text(t.get("STAT_NAME", "")),
                    updated_at=t.get("UPDATED_DATE", ""),
                )
                for t in tables
            ]
        except Exception:
            logger.exception("e-Stat 統計表検索に失敗: keyword=%s", keyword)
            return []

    async def get_stats_data(
        self,
        stats_id: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """統計表のデータを取得する（生データ）."""
        if not self.is_configured:
            return []

        request_params: dict[str, str] = {
            "appId": self._api_key,
            "lang": "J",
            "statsDataId": stats_id,
            "metaGetFlg": "Y",
            "sectionHeaderFlg": "1",
        }
        if params:
            request_params.update(params)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/json/getStatsData", params=request_params
                )
                resp.raise_for_status()
                data = resp.json()

            stat_data = data.get("GET_STATS_DATA", {})
            data_inf = stat_data.get("STATISTICAL_DATA", {}).get("DATA_INF", {})
            values = data_inf.get("VALUE", [])
            if isinstance(values, dict):
                values = [values]

            return values
        except Exception:
            logger.exception("e-Stat データ取得に失敗: stats_id=%s", stats_id)
            return []

    async def collect_ict_stats(self) -> list[StatRecord]:
        """IT人材関連の統計データをまとめて収集する.

        KNOWN_STAT_TABLES で定義した統計表からデータを取得し、
        情報通信業に関連するレコードを抽出する。
        """
        if not self.is_configured:
            logger.warning("e-Stat APIキー未設定のためスキップ")
            return []

        records: list[StatRecord] = []

        for table_key, table_info in KNOWN_STAT_TABLES.items():
            try:
                raw_data = await self.get_stats_data(table_info["stats_id"])
                parsed = self._parse_ict_records(
                    raw_data, table_key, table_info["category"]
                )
                records.extend(parsed)
                logger.info(
                    "e-Stat [%s]: %d件取得", table_key, len(parsed)
                )
            except Exception:
                logger.exception("e-Stat [%s] の処理に失敗", table_key)

        return records

    def _parse_ict_records(
        self,
        raw_data: list[dict[str, Any]],
        table_key: str,
        category: str,
    ) -> list[StatRecord]:
        """生データからICT関連のStatRecordを生成する."""
        records: list[StatRecord] = []

        for row in raw_data:
            value_str = row.get("$", "")
            if not value_str or value_str in ("-", "…", "x", "***"):
                continue

            try:
                value = float(value_str.replace(",", ""))
            except (ValueError, TypeError):
                continue

            # 年次を抽出（@time から YYYY を取得）
            time_code = row.get("@time", "")
            year = _extract_year(time_code)
            if year < 2015:
                continue

            # カテゴリコード等から名前を構築
            name = f"{table_key}_{time_code}"
            unit = _guess_unit(row, table_key)

            records.append(
                StatRecord(
                    name=name,
                    source="e-Stat",
                    year=year,
                    value=value,
                    unit=unit,
                    category=category,
                    metadata={
                        "stats_id": KNOWN_STAT_TABLES[table_key]["stats_id"],
                        "table_key": table_key,
                        "raw_time": time_code,
                    },
                )
            )

        return records


def _extract_text(obj: Any) -> str:
    """e-Stat JSON のテキストフィールドを展開する.

    文字列の場合はそのまま返し、辞書の場合は "$" キーの値を返す。
    """
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return obj.get("$", str(obj))
    return str(obj)


def _extract_year(time_code: str) -> int:
    """時間コード（例: '2023000000', '2023100000'）から年を抽出する."""
    try:
        return int(time_code[:4])
    except (ValueError, IndexError):
        return 0


def _guess_unit(row: dict[str, Any], table_key: str) -> str:
    """統計表の種類からデータの単位を推定する."""
    unit_str = row.get("@unit", "")
    if unit_str:
        return unit_str

    unit_map = {
        "wage_structure": "万円",
        "labor_force": "万人",
        "economic_census": "社",
    }
    return unit_map.get(table_key, "")
