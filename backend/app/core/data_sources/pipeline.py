"""統計データを知識グラフに投入するパイプライン.

EStatClient で取得した StatRecord を Neo4j の知識グラフに格納し、
Industry / Skill ノードとのリレーションを作成する。
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.data_sources.estat import EStatClient
from app.core.data_sources.models import CollectResult, StatRecord
from app.core.graph.client import GraphClient

logger = logging.getLogger(__name__)

# 統計データ名 → 業界ノードのマッピング
_STAT_TO_INDUSTRY: dict[str, str] = {
    "wage_structure": "ses",  # 賃金データ → SES業界に関連
    "labor_force": "sier",  # 労働力データ → SIer業界に関連
    "economic_census": "enterprise_it",  # 事業所データ → 事業会社IT
}

# 統計カテゴリ → 関連する業界一覧
_CATEGORY_INDUSTRIES: dict[str, list[str]] = {
    "labor": ["sier", "ses", "freelance", "web_startup", "enterprise_it"],
    "industry": ["sier", "ses", "web_startup", "enterprise_it"],
    "skill": ["sier", "ses", "freelance", "web_startup"],
}


class DataCollectionPipeline:
    """統計データを収集し、知識グラフに格納するパイプライン."""

    def __init__(
        self,
        graph_client: GraphClient,
        estat_client: EStatClient | None = None,
    ):
        self.graph = graph_client
        self.estat = estat_client or EStatClient()

    async def run(self) -> CollectResult:
        """パイプライン全体を実行する.

        1. e-Stat APIからデータ取得
        2. StatRecordノードとしてNeo4jに格納
        3. 業界ノードとのリレーション作成
        """
        result = CollectResult()

        # e-Stat からデータ収集
        if self.estat.is_configured:
            try:
                records = await self.estat.collect_ict_stats()
                result.total_records += len(records)
                result.sources.append("e-Stat")

                stored = await self._store_records(records)
                result.stored_records += stored
                logger.info("e-Stat: %d/%d件を知識グラフに格納", stored, len(records))
            except Exception as exc:
                msg = f"e-Stat データ収集エラー: {exc}"
                logger.exception(msg)
                result.errors.append(msg)
        else:
            result.errors.append("e-Stat APIキー未設定（ECHOSHOAL_ESTAT_API_KEY）")

        # 静的データ（IPA白書等のハードコードされた参考値）を投入
        static_records = self._get_static_records()
        result.total_records += len(static_records)
        stored = await self._store_records(static_records)
        result.stored_records += stored
        result.sources.append("static_reference")
        logger.info("静的参考データ: %d件を知識グラフに格納", stored)

        return result

    async def _store_records(self, records: list[StatRecord]) -> int:
        """StatRecordをNeo4jに格納し、リレーションを作成する."""
        stored = 0
        for record in records:
            try:
                await self._upsert_stat_record(record)
                await self._link_to_industries(record)
                stored += 1
            except Exception:
                logger.warning("StatRecord格納失敗: %s", record.name)
        return stored

    async def _upsert_stat_record(self, record: StatRecord) -> None:
        """StatRecordノードをupsert（冪等）する."""
        await self.graph.execute_write(
            "MERGE (sr:StatRecord {name: $name}) "
            "SET sr.source = $source, "
            "    sr.year = $year, "
            "    sr.value = $value, "
            "    sr.unit = $unit, "
            "    sr.category = $category, "
            "    sr.updated_at = datetime()",
            {
                "name": record.name,
                "source": record.source,
                "year": record.year,
                "value": record.value,
                "unit": record.unit,
                "category": record.category,
            },
        )

    async def _link_to_industries(self, record: StatRecord) -> None:
        """StatRecordを関連する業界ノードにリンクする."""
        industries = _CATEGORY_INDUSTRIES.get(record.category, [])

        # table_keyベースでより具体的な業界を特定
        table_key = record.metadata.get("table_key", "")
        if table_key in _STAT_TO_INDUSTRY:
            primary = _STAT_TO_INDUSTRY[table_key]
            if primary not in industries:
                industries = [primary, *industries]

        for industry_name in industries:
            await self.graph.execute_write(
                "MATCH (sr:StatRecord {name: $stat_name}) "
                "MATCH (i:Industry {name: $industry_name}) "
                "MERGE (sr)-[d:DESCRIBES]->(i) "
                "SET d.metric = $category, d.year = $year",
                {
                    "stat_name": record.name,
                    "industry_name": industry_name,
                    "category": record.category,
                    "year": record.year,
                },
            )

    def _get_static_records(self) -> list[StatRecord]:
        """IPA白書やIPAの公開データに基づく静的参考データ.

        e-Stat APIが利用できない場合でも最低限のデータを確保する。
        出典: IPA IT人材白書2024, 経産省DXレポート 等
        """
        return [
            StatRecord(
                name="ipa_it_engineers_2023",
                source="IPA IT人材白書2024",
                year=2023,
                value=1_090_000,
                unit="人",
                category="labor",
                metadata={"description": "日本のIT人材数（推計）"},
            ),
            StatRecord(
                name="ipa_it_shortage_2030",
                source="経産省 IT人材需給調査",
                year=2030,
                value=790_000,
                unit="人",
                category="labor",
                metadata={"description": "2030年のIT人材不足数（高位シナリオ）"},
            ),
            StatRecord(
                name="ipa_ses_market_2023",
                source="IPA IT人材白書2024",
                year=2023,
                value=3_500_000,
                unit="万円",
                category="industry",
                metadata={"description": "SES業界の平均年収"},
            ),
            StatRecord(
                name="ipa_freelance_ratio_2023",
                source="IPA IT人材白書2024",
                year=2023,
                value=7.2,
                unit="%",
                category="labor",
                metadata={"description": "IT人材に占めるフリーランスの割合"},
            ),
            StatRecord(
                name="ipa_ai_adoption_2023",
                source="IPA DX白書2024",
                year=2023,
                value=23.5,
                unit="%",
                category="skill",
                metadata={"description": "企業のAI導入率"},
            ),
            StatRecord(
                name="ipa_cloud_adoption_2023",
                source="総務省 通信利用動向調査",
                year=2023,
                value=77.7,
                unit="%",
                category="skill",
                metadata={"description": "企業のクラウドサービス利用率"},
            ),
            StatRecord(
                name="ipa_remote_work_it_2023",
                source="総務省 通信利用動向調査",
                year=2023,
                value=51.7,
                unit="%",
                category="labor",
                metadata={"description": "情報通信業のテレワーク実施率"},
            ),
            StatRecord(
                name="ipa_legacy_systems_2025",
                source="経産省 DXレポート",
                year=2025,
                value=60,
                unit="%",
                category="industry",
                metadata={"description": "2025年時点でレガシーシステムが残存する企業割合（推計）"},
            ),
            StatRecord(
                name="meti_dx_investment_2023",
                source="経産省 DX推進指標",
                year=2023,
                value=17_900,
                unit="億円",
                category="industry",
                metadata={"description": "国内DX関連投資額"},
            ),
            StatRecord(
                name="ipa_security_incident_2023",
                source="IPA 情報セキュリティ白書",
                year=2023,
                value=13_279,
                unit="件",
                category="skill",
                metadata={"description": "サイバーセキュリティインシデント報告件数"},
            ),
        ]

    async def get_data_status(self) -> dict[str, Any]:
        """知識グラフ内の統計データの状態を取得する."""
        counts = await self.graph.execute_read(
            "MATCH (sr:StatRecord) "
            "RETURN sr.source AS source, sr.category AS category, "
            "       count(sr) AS count, max(sr.year) AS latest_year "
            "ORDER BY source"
        )
        total = await self.graph.execute_read(
            "MATCH (sr:StatRecord) RETURN count(sr) AS total"
        )
        links = await self.graph.execute_read(
            "MATCH (:StatRecord)-[d:DESCRIBES]->() "
            "RETURN count(d) AS total_links"
        )

        return {
            "total_records": total[0]["total"] if total else 0,
            "total_links": links[0]["total_links"] if links else 0,
            "by_source": counts,
        }
