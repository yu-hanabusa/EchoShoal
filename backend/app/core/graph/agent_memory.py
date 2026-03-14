"""エージェント記憶の知識グラフ管理.

エージェントの行動・状態を時系列でNeo4jに記録し、
可視性制御に基づいて他エージェントの視点から取得する。

ノード:
  - Agent {agent_id, name, agent_type, industry}
  - AgentSnapshot {agent_id, round, revenue, cost, headcount, satisfaction, reputation}
  - ActionRecord {agent_id, agent_name, round, action_type, description, visibility}

リレーション:
  - Agent -[STATE_AT {round}]-> AgentSnapshot
  - Agent -[PERFORMED {round}]-> ActionRecord
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.graph.client import GraphClient

logger = logging.getLogger(__name__)

# 行動の可視性定義
ACTION_VISIBILITY: dict[str, str] = {
    # SIer
    "bid_project": "public",
    "hire_engineers": "public",
    "outsource": "partial",
    "invest_rd": "public",
    "offshore": "private",
    "internal_training": "private",
    # SES
    "recruit": "public",
    "upskill": "private",
    "adjust_margin": "private",
    "expand_sales": "public",
    "release_bench": "private",
    "shift_domain": "public",
    # Freelance
    "take_contract": "partial",
    "learn_skill": "private",
    "raise_rate": "public",
    "lower_rate": "public",
    "network": "public",
    "rest": "private",
    # Enterprise IT
    "hire_internal": "public",
    "outsource_project": "partial",
    "start_dx": "public",
    "maintain_legacy": "private",
    "adopt_saas": "private",
    "insource": "public",
}


def get_visibility(action_type: str) -> str:
    """行動タイプから可視性を取得する."""
    return ACTION_VISIBILITY.get(action_type, "public")


class AgentMemoryStore:
    """エージェントの行動・状態を知識グラフに記録・取得する."""

    def __init__(self, graph_client: GraphClient):
        self.graph = graph_client

    async def ensure_agent_node(
        self,
        agent_id: str,
        name: str,
        agent_type: str,
        industry: str,
    ) -> None:
        """Agentノードが存在することを保証する（冪等）."""
        await self.graph.execute_write(
            "MERGE (a:Agent {agent_id: $agent_id}) "
            "SET a.name = $name, a.agent_type = $agent_type, "
            "    a.industry = $industry",
            {
                "agent_id": agent_id,
                "name": name,
                "agent_type": agent_type,
                "industry": industry,
            },
        )

    async def record_state(
        self,
        agent_id: str,
        round_number: int,
        state: dict[str, Any],
    ) -> None:
        """エージェントの状態スナップショットを記録する."""
        await self.graph.execute_write(
            "MATCH (a:Agent {agent_id: $agent_id}) "
            "CREATE (s:AgentSnapshot {"
            "  agent_id: $agent_id, round: $round, "
            "  revenue: $revenue, cost: $cost, headcount: $headcount, "
            "  satisfaction: $satisfaction, reputation: $reputation, "
            "  active_contracts: $active_contracts"
            "}) "
            "CREATE (a)-[:STATE_AT {round: $round}]->(s)",
            {
                "agent_id": agent_id,
                "round": round_number,
                "revenue": state.get("revenue", 0.0),
                "cost": state.get("cost", 0.0),
                "headcount": state.get("headcount", 0),
                "satisfaction": state.get("satisfaction", 0.5),
                "reputation": state.get("reputation", 0.5),
                "active_contracts": state.get("active_contracts", 0),
            },
        )

    async def record_action(
        self,
        agent_id: str,
        agent_name: str,
        round_number: int,
        action_type: str,
        description: str,
    ) -> None:
        """エージェントの行動を可視性付きで記録する."""
        visibility = get_visibility(action_type)
        await self.graph.execute_write(
            "MATCH (a:Agent {agent_id: $agent_id}) "
            "CREATE (ar:ActionRecord {"
            "  agent_id: $agent_id, agent_name: $agent_name, "
            "  round: $round, action_type: $action_type, "
            "  description: $description, visibility: $visibility"
            "}) "
            "CREATE (a)-[:PERFORMED {round: $round}]->(ar)",
            {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "round": round_number,
                "action_type": action_type,
                "description": description,
                "visibility": visibility,
            },
        )

    async def get_visible_actions(
        self,
        observer_id: str,
        from_round: int = 1,
        to_round: int | None = None,
    ) -> list[dict[str, Any]]:
        """観察者から見える行動を取得する.

        可視性ルール:
        - public: 全エージェントに見える
        - private: 自分の行動のみ見える
        - partial: 当面はpublic扱い（将来、取引関係で制御）
        """
        to_round_val = to_round or 9999

        return await self.graph.execute_read(
            "MATCH (a:Agent)-[:PERFORMED]->(ar:ActionRecord) "
            "WHERE ar.round >= $from_round AND ar.round <= $to_round "
            "  AND ("
            "    ar.visibility = 'public' "
            "    OR ar.visibility = 'partial' "
            "    OR ar.agent_id = $observer_id"
            "  ) "
            "RETURN ar.agent_name AS agent_name, ar.action_type AS action_type, "
            "       ar.description AS description, ar.round AS round, "
            "       ar.visibility AS visibility, ar.agent_id AS agent_id "
            "ORDER BY ar.round DESC "
            "LIMIT 50",
            {
                "observer_id": observer_id,
                "from_round": from_round,
                "to_round": to_round_val,
            },
        )

    async def get_agent_history(
        self,
        agent_id: str,
        last_n_rounds: int = 5,
    ) -> dict[str, Any]:
        """自分自身の行動・状態履歴を取得する（private含む全情報）."""
        actions = await self.graph.execute_read(
            "MATCH (:Agent {agent_id: $agent_id})-[:PERFORMED]->(ar:ActionRecord) "
            "RETURN ar.action_type AS action_type, ar.description AS description, "
            "       ar.round AS round "
            "ORDER BY ar.round DESC "
            "LIMIT $limit",
            {"agent_id": agent_id, "limit": last_n_rounds * 2},
        )

        snapshots = await self.graph.execute_read(
            "MATCH (:Agent {agent_id: $agent_id})-[:STATE_AT]->(s:AgentSnapshot) "
            "RETURN s.round AS round, s.revenue AS revenue, s.cost AS cost, "
            "       s.headcount AS headcount, s.satisfaction AS satisfaction, "
            "       s.reputation AS reputation "
            "ORDER BY s.round DESC "
            "LIMIT $limit",
            {"agent_id": agent_id, "limit": last_n_rounds},
        )

        return {"actions": actions, "snapshots": snapshots}

    async def get_market_activity_summary(
        self,
        observer_id: str,
        last_n_rounds: int = 3,
        current_round: int = 1,
    ) -> str:
        """市場で起きたpublic行動のサマリーテキストを生成する."""
        from_round = max(1, current_round - last_n_rounds)
        actions = await self.get_visible_actions(
            observer_id=observer_id,
            from_round=from_round,
            to_round=current_round - 1,
        )

        if not actions:
            return ""

        # 他者の行動のみ（自分の行動は own_history で見る）
        other_actions = [a for a in actions if a["agent_id"] != observer_id]
        if not other_actions:
            return ""

        lines: list[str] = ["【直近の市場動向】"]
        for act in other_actions[:15]:
            lines.append(
                f"  R{act['round']}: {act['agent_name']} → "
                f"{act['action_type']}（{act['description'][:40]}）"
            )

        return "\n".join(lines)

    async def record_skills(
        self,
        agent_id: str,
        skills: dict[str, float],
    ) -> None:
        """エージェントのスキル習熟度をグラフに記録する.

        SKILLED_IN リレーションで Agent → Skill を結ぶ。
        """
        for skill_name, proficiency in skills.items():
            try:
                await self.graph.execute_write(
                    "MATCH (a:Agent {agent_id: $agent_id}) "
                    "MERGE (s:Skill {name: $skill_name}) "
                    "MERGE (a)-[r:SKILLED_IN]->(s) "
                    "SET r.proficiency = $proficiency",
                    {
                        "agent_id": agent_id,
                        "skill_name": skill_name,
                        "proficiency": proficiency,
                    },
                )
            except Exception:
                logger.warning("スキル記録失敗: agent=%s, skill=%s", agent_id, skill_name)
