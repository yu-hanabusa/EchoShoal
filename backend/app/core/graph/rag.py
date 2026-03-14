"""GraphRAG検索モジュール.

エージェントの視点から見える情報のみを知識グラフから取得し、
LLMプロンプトに注入する。

情報の非対称性:
- public行動: 全エージェントに見える
- private行動: 自分だけが見える
- partial行動: 当面はpublic扱い（将来、取引関係で制御）
- ユーザー（API）のみが全情報を見られる（神の視点）
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
    reference_stats: str = ""

    def to_prompt(self) -> str:
        """プロンプト用テキストに変換する.

        内容がない場合は空文字を返す。
        """
        sections: list[str] = []

        if self.own_history:
            sections.append(self.own_history)
        if self.market_activity:
            sections.append(self.market_activity)
        if self.reference_stats:
            sections.append(self.reference_stats)

        if not sections:
            return ""

        return "\n\n" + "\n\n".join(sections)


class GraphRAGRetriever:
    """エージェントの視点から見える情報を知識グラフから取得する.

    Neo4jのCypherクエリでグラフ走査し、可視性制御を適用する。
    ベクトル検索は使わないため、WSL2の8GB RAM制限下でも軽量に動作する。
    """

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
    ) -> AgentDecisionContext:
        """特定エージェントの視点から見える情報を取得する.

        Args:
            agent_id: 観察者のエージェントID
            round_number: 現在のラウンド番号

        Returns:
            AgentDecisionContext: そのエージェントが見える範囲の情報
        """
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

        # 3. 統計データ
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

        # 状態変化
        if snapshots:
            latest = snapshots[0]
            lines.append(
                f"  直近状態(R{latest['round']}): "
                f"売上{latest['revenue']:.0f}万円, コスト{latest['cost']:.0f}万円, "
                f"人員{latest['headcount']}名, "
                f"満足度{latest['satisfaction']:.2f}, 評判{latest['reputation']:.2f}"
            )

            # 前回との比較（あれば）
            if len(snapshots) >= 2:
                prev = snapshots[1]
                rev_delta = latest["revenue"] - prev["revenue"]
                hc_delta = latest["headcount"] - prev["headcount"]
                if rev_delta != 0 or hc_delta != 0:
                    lines.append(
                        f"  前回比: 売上{rev_delta:+.0f}万円, 人員{hc_delta:+d}名"
                    )

        # 行動履歴
        if actions:
            lines.append("  直近の行動:")
            for act in actions[:6]:
                lines.append(
                    f"    R{act['round']}: {act['action_type']}"
                    f"（{act['description'][:30]}）"
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
