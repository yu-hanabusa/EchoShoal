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
    skill_landscape: str = ""
    active_events: str = ""
    document_insights: str = ""
    reference_stats: str = ""
    agent_relationships: str = ""

    def to_prompt(self) -> str:
        """プロンプト用テキストに変換する."""
        sections: list[str] = []

        if self.own_history:
            sections.append(self.own_history)
        if self.market_activity:
            sections.append(self.market_activity)
        if self.industry_landscape:
            sections.append(self.industry_landscape)
        if self.skill_landscape:
            sections.append(self.skill_landscape)
        if self.active_events:
            sections.append(self.active_events)
        if self.document_insights:
            sections.append(self.document_insights)
        if self.reference_stats:
            sections.append(self.reference_stats)
        if self.agent_relationships:
            sections.append(self.agent_relationships)

        if not sections:
            return ""

        return "\n\n" + "\n\n".join(sections)


class GraphRAGRetriever:
    """エージェントの視点から見える情報を知識グラフから取得する."""

    def __init__(
        self,
        graph_client: GraphClient,
        agent_memory: AgentMemoryStore,
        simulation_id: str = "",
    ):
        self.graph = graph_client
        self.memory = agent_memory
        self.simulation_id = simulation_id

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

        # 4. 市場のスキル分布（SKILLED_INから）
        try:
            ctx.skill_landscape = await self._get_skill_landscape()
        except Exception:
            logger.warning("スキル分布の取得に失敗")

        # 5. アクティブイベントの説明
        if active_events_text:
            ctx.active_events = active_events_text

        # 6. アップロード文書から得た知識
        try:
            ctx.document_insights = await self._get_document_insights()
        except Exception:
            logger.warning("文書知識の取得に失敗")

        # 7. 統計データ
        try:
            ctx.reference_stats = await self._get_reference_stats()
        except Exception:
            logger.warning("統計データの取得に失敗")

        # 8. エージェント間の関係（RELATES_TO）
        try:
            ctx.agent_relationships = await self._get_agent_relationships(agent_id)
        except Exception:
            logger.warning("エージェント関係の取得に失敗: agent=%s", agent_id)

        return ctx

    def _format_own_history(self, history: dict[str, Any]) -> str:
        """自分の行動・状態履歴をテキストに変換する.

        行動と結果（状態変化）を紐付けて表示し、
        LLMが「何をしたら何が起きたか」を理解できるようにする。
        """
        actions = history.get("actions", [])
        snapshots = history.get("snapshots", [])

        if not actions and not snapshots:
            return ""

        lines: list[str] = ["【自社の直近の行動と結果】"]

        # スナップショットをラウンド別にインデックス
        snap_by_round: dict[int, dict[str, Any]] = {}
        for s in snapshots:
            snap_by_round[s["round"]] = s

        # 行動をラウンド別にグループ化
        actions_by_round: dict[int, list[str]] = {}
        for act in actions:
            r = act["round"]
            if r not in actions_by_round:
                actions_by_round[r] = []
            actions_by_round[r].append(act["action_type"])

        # ラウンド順に行動→結果を表示
        rounds_shown = sorted(set(list(snap_by_round.keys()) + list(actions_by_round.keys())), reverse=True)[:5]

        prev_snap: dict[str, Any] | None = None
        for r in reversed(rounds_shown):
            snap = snap_by_round.get(r)
            acts = actions_by_round.get(r, [])

            act_str = ", ".join(acts) if acts else "行動なし"

            if snap and prev_snap:
                rev_d = snap["revenue"] - prev_snap["revenue"]
                hc_d = snap["headcount"] - prev_snap["headcount"]
                sat_d = snap["satisfaction"] - prev_snap["satisfaction"]
                rep_d = snap["reputation"] - prev_snap["reputation"]
                changes = []
                if rev_d != 0:
                    changes.append(f"売上{rev_d:+.0f}万円")
                if hc_d != 0:
                    changes.append(f"人員{hc_d:+d}名")
                if abs(sat_d) >= 0.01:
                    changes.append(f"満足度{sat_d:+.2f}")
                if abs(rep_d) >= 0.01:
                    changes.append(f"評判{rep_d:+.2f}")
                change_str = ", ".join(changes) if changes else "変化なし"
                lines.append(f"  {r}ヶ月目: {act_str} → 結果: {change_str}")
            elif snap:
                lines.append(
                    f"  {r}ヶ月目: {act_str} → "
                    f"売上{snap['revenue']:.0f}万円, 人員{snap['headcount']}名"
                )

            prev_snap = snap

        return "\n".join(lines)

    async def _get_industry_landscape(self, round_number: int) -> str:
        """業界別の公開行動集計を取得する（競合環境の把握）."""
        from_round = max(1, round_number - 3)
        results = await self.graph.execute_read(
            "MATCH (a:Agent)-[:PERFORMED]->(ar:ActionRecord) "
            "WHERE ar.simulation_id = $sim_id "
            "  AND ar.round >= $from_round AND ar.visibility = 'public' "
            "RETURN a.industry AS industry, ar.action_type AS action, "
            "       count(*) AS count "
            "ORDER BY industry, count DESC",
            {"sim_id": self.simulation_id, "from_round": from_round},
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

    async def _get_skill_landscape(self) -> str:
        """市場のスキル分布を取得する（SKILLED_INリレーションから）."""
        results = await self.graph.execute_read(
            "MATCH (a:Agent {simulation_id: $sim_id})-[r:SKILLED_IN]->(s:Skill) "
            "RETURN s.name AS skill, count(a) AS holders, "
            "       round(avg(r.proficiency) * 100) / 100.0 AS avg_level "
            "ORDER BY holders DESC",
            {"sim_id": self.simulation_id},
        )

        if not results:
            return ""

        lines: list[str] = ["【市場のスキル分布】"]
        for row in results:
            lines.append(
                f"  {row['skill']}: {row['holders']}社/人が保有 "
                f"(平均習熟度{row['avg_level']:.1f})"
            )

        return "\n".join(lines)

    async def _get_document_insights(self) -> str:
        """アップロード文書から得た知識を取得する.

        2段階の情報を提供:
        1. 文書の要約テキスト（市場データ、価格、ユーザー行動の詳細）
        2. 抽出されたエンティティとその関係（企業名、技術名、政策名）
        """
        # 1. 文書の要約テキストを取得
        summary_results = await self.graph.execute_read(
            "MATCH (d:Document) "
            "WHERE d.simulation_id = $sim_id AND d.text_summary IS NOT NULL "
            "  AND d.text_summary <> '' "
            "RETURN d.filename AS filename, d.text_summary AS summary "
            "ORDER BY d.uploaded_at DESC "
            "LIMIT 5",
            {"sim_id": self.simulation_id},
        )

        lines: list[str] = []

        if summary_results:
            lines.append("【参考資料の要約】")
            for row in summary_results:
                lines.append(f"--- {row['filename']} ---")
                lines.append(row["summary"])

        # 2. エンティティ情報
        results = await self.graph.execute_read(
            "MATCH (d:Document)-[:MENTIONS]->(e) "
            "WHERE d.simulation_id = $sim_id "
            "RETURN d.source AS source, labels(e)[0] AS type, "
            "       collect(DISTINCT e.name) AS entities "
            "ORDER BY d.uploaded_at DESC "
            "LIMIT 5",
            {"sim_id": self.simulation_id},
        )

        if results:
            lines.append("【参考資料のエンティティ】")
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

        # 3. エンティティ間の関係
        rel_results = await self.graph.execute_read(
            "MATCH (d:Document {simulation_id: $sim_id})-[:MENTIONS]->(src) "
            "MATCH (src)-[r:ENTITY_RELATION]->(tgt) "
            "RETURN src.name AS source, r.relation_type AS rel_type, "
            "       tgt.name AS target "
            "LIMIT 20",
            {"sim_id": self.simulation_id},
        )

        if rel_results:
            _REL_LABELS = {
                "COMPETES_WITH": "と競合",
                "PROVIDES_INFRA": "にインフラ提供",
                "TARGET_SECTOR": "をターゲット",
                "PARTNERS_WITH": "と提携",
                "INVESTS_IN": "に投資",
                "REGULATES": "を規制",
                "USES": "を利用",
                "ACQUIRES": "を買収",
                "DEPENDS_ON": "に依存",
                "AFFECTS": "に影響",
            }
            lines.append("  --- エンティティ間の関係 ---")
            for row in rel_results:
                label = _REL_LABELS.get(row["rel_type"], row["rel_type"])
                lines.append(f"  {row['source']} {label} {row['target']}")

        return "\n".join(lines) if lines else ""

    async def _get_agent_relationships(self, agent_id: str) -> str:
        """エージェント間の関係（RELATES_TO）を取得する."""
        results = await self.graph.execute_read(
            "MATCH (a:Agent {agent_id: $agent_id, simulation_id: $sim_id})"
            "-[r:RELATES_TO]->(b:Agent) "
            "RETURN a.name AS source, r.relation_type AS rel_type, "
            "       b.name AS target "
            "UNION "
            "MATCH (b:Agent)-[r:RELATES_TO]->"
            "(a:Agent {agent_id: $agent_id, simulation_id: $sim_id}) "
            "RETURN b.name AS source, r.relation_type AS rel_type, "
            "       a.name AS target",
            {"agent_id": agent_id, "sim_id": self.simulation_id},
        )

        if not results:
            return ""

        # Resolve agent's own name for labeling
        own_name: str | None = None
        name_result = await self.graph.execute_read(
            "MATCH (a:Agent {agent_id: $agent_id, simulation_id: $sim_id}) "
            "RETURN a.name AS name LIMIT 1",
            {"agent_id": agent_id, "sim_id": self.simulation_id},
        )
        if name_result:
            own_name = name_result[0]["name"]

        _REL_LABELS = {
            "competitor": "と競合",
            "partner": "と提携",
            "investor": "に投資",
            "user": "を利用",
            "regulator": "を規制",
            "acquirer": "を買収",
            "interest": "に関心",
            "former_user": "を解約済み",
            "advocate": "を推薦",
            "critic": "を批判",
        }

        lines: list[str] = ["【エージェント間の関係】"]
        for row in results:
            src = "自社" if row["source"] == own_name else row["source"]
            tgt = "自社" if row["target"] == own_name else row["target"]
            label = _REL_LABELS.get(row["rel_type"], row["rel_type"])
            lines.append(f"  {src} {label} {tgt}")

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
