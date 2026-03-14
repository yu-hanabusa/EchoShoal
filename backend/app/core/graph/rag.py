"""GraphRAG検索モジュール.

エージェントの視点から見える情報を知識グラフから取得し、
LLMプロンプトに注入する。

情報ソース:
1. 自己履歴（private含む）
2. 市場の公開行動（可視性フィルタ適用）
3. 業界別の競合環境集計
4. アクティブイベントの説明
5. アップロード文書から得た知識
6. 統計データ
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.graph.agent_memory import AgentMemoryStore
from app.core.graph.client import GraphClient

logger = logging.getLogger(__name__)


@dataclass
class AgentDecisionContext:
    """エージェントの意思決定に必要なコンテキスト."""

    own_history: str = ""
    market_activity: str = ""
    industry_landscape: str = ""
    active_events: str = ""
    document_insights: str = ""
    reference_stats: str = ""

    def to_prompt(self) -> str:
        """プロンプト用テキストに変換する."""
        sections: list[str] = []

        if self.own_history:
            sections.append(self.own_history)
        if self.market_activity:
            sections.append(self.market_activity)
        if self.industry_landscape:
            sections.append(self.industry_landscape)
        if self.active_events:
            sections.append(self.active_events)
        if self.document_insights:
            sections.append(self.document_insights)
        if self.reference_stats:
            sections.append(self.reference_stats)

        if not sections:
            return ""

        return "\n\n" + "\n\n".join(sections)


class GraphRAGRetriever:
    """エージェントの視点から見える情報を知識グラフから取得する."""

    def __init__(
        self,
        graph_client: GraphClient,
        agent_memory: AgentMemoryStore,
    ):
        self.graph = graph_client
        self.memory = agent_memory

    async def get_agent_context(
        self,
        agent_id: str,
        round_number: int,
        active_events_text: str = "",
    ) -> AgentDecisionContext:
        """特定エージェントの視点から見える情報を取得する."""
        ctx = AgentDecisionContext()

        # 1. 自分の行動履歴（private含む全情報）
        try:
            history = await self.memory.get_agent_history(agent_id, last_n_rounds=5)
            ctx.own_history = self._format_own_history(history)
        except Exception:
            logger.warning("自己履歴の取得に失敗: agent=%s", agent_id)

        # 2. 市場で見えている他者の行動（可視性フィルタ適用済み）
        try:
            ctx.market_activity = await self.memory.get_market_activity_summary(
                observer_id=agent_id,
                last_n_rounds=3,
                current_round=round_number,
            )
        except Exception:
            logger.warning("市場動向の取得に失敗: agent=%s", agent_id)

        # 3. 業界別の競合環境集計
        try:
            ctx.industry_landscape = await self._get_industry_landscape(round_number)
        except Exception:
            logger.warning("競合環境の取得に失敗")

        # 4. アクティブイベントの説明
        if active_events_text:
            ctx.active_events = active_events_text

        # 5. アップロード文書から得た知識
        try:
            ctx.document_insights = await self._get_document_insights()
        except Exception:
            logger.warning("文書知識の取得に失敗")

        # 6. 統計データ
        try:
            ctx.reference_stats = await self._get_reference_stats()
        except Exception:
            logger.warning("統計データの取得に失敗")

        return ctx

    def _format_own_history(self, history: dict[str, Any]) -> str:
        """自分の行動・状態履歴をテキストに変換する."""
        actions = history.get("actions", [])
        snapshots = history.get("snapshots", [])

        if not actions and not snapshots:
            return ""

        lines: list[str] = ["【自社の直近の行動・状態】"]

        if snapshots:
            latest = snapshots[0]
            lines.append(
                f"  直近状態(R{latest['round']}): "
                f"売上{latest['revenue']:.0f}万円, コスト{latest['cost']:.0f}万円, "
                f"人員{latest['headcount']}名, "
                f"満足度{latest['satisfaction']:.2f}, 評判{latest['reputation']:.2f}"
            )

            if len(snapshots) >= 2:
                prev = snapshots[1]
                rev_delta = latest["revenue"] - prev["revenue"]
                hc_delta = latest["headcount"] - prev["headcount"]
                if rev_delta != 0 or hc_delta != 0:
                    lines.append(
                        f"  前回比: 売上{rev_delta:+.0f}万円, 人員{hc_delta:+d}名"
                    )

        if actions:
            lines.append("  直近の行動:")
            for act in actions[:6]:
                lines.append(
                    f"    R{act['round']}: {act['action_type']}"
                    f"（{act['description'][:30]}）"
                )

        return "\n".join(lines)

    async def _get_industry_landscape(self, round_number: int) -> str:
        """業界別の公開行動集計を取得する（競合環境の把握）."""
        from_round = max(1, round_number - 3)
        results = await self.graph.execute_read(
            "MATCH (a:Agent)-[:PERFORMED]->(ar:ActionRecord) "
            "WHERE ar.round >= $from_round AND ar.visibility = 'public' "
            "RETURN a.industry AS industry, ar.action_type AS action, "
            "       count(*) AS count "
            "ORDER BY industry, count DESC",
            {"from_round": from_round},
        )

        if not results:
            return ""

        # 業界別に集計
        by_industry: dict[str, list[str]] = {}
        for row in results:
            ind = row["industry"]
            if ind not in by_industry:
                by_industry[ind] = []
            by_industry[ind].append(f"{row['action']}x{row['count']}")

        lines: list[str] = ["【業界動向（直近3ラウンド）】"]
        for industry, actions in by_industry.items():
            lines.append(f"  {industry}: {', '.join(actions[:5])}")

        return "\n".join(lines)

    async def _get_document_insights(self) -> str:
        """アップロード文書から得た知識を取得する."""
        results = await self.graph.execute_read(
            "MATCH (d:Document)-[:MENTIONS]->(e) "
            "RETURN d.source AS source, labels(e)[0] AS type, "
            "       collect(DISTINCT e.name) AS entities "
            "ORDER BY d.uploaded_at DESC "
            "LIMIT 5"
        )

        if not results:
            return ""

        lines: list[str] = ["【参考資料からの知識】"]
        for row in results:
            source = row["source"] or "不明"
            entity_type = row["type"]
            entities = row["entities"][:10]
            type_label = {"Skill": "技術", "Company": "企業", "Policy": "政策"}.get(
                entity_type, entity_type
            )
            lines.append(
                f"  {source}: {type_label} - {', '.join(entities)}"
            )

        return "\n".join(lines)

    async def _get_reference_stats(self) -> str:
        """統計データをテキストに変換する."""
        stats = await self.graph.execute_read(
            "MATCH (sr:StatRecord) "
            "WHERE sr.category IN ['labor', 'industry'] "
            "RETURN sr.name AS name, sr.source AS source, "
            "       sr.year AS year, sr.value AS value, sr.unit AS unit "
            "ORDER BY sr.year DESC, sr.name "
            "LIMIT 10"
        )

        if not stats:
            return ""

        lines: list[str] = ["【参考統計データ】"]
        for stat in stats:
            lines.append(
                f"  - {stat['name']}: {stat['value']}{stat['unit']} "
                f"({stat['source']}, {stat['year']}年)"
            )

        return "\n".join(lines)
