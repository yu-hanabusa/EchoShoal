"""エージェント記憶の知識グラフ管理.

エージェントの行動・状態を時系列でNeo4jに記録し、
可視性制御に基づいて他エージェントの視点から取得する。
すべてのデータは simulation_id でスコープされる。
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.graph.client import GraphClient

logger = logging.getLogger(__name__)

# 行動の可視性定義
ACTION_VISIBILITY: dict[str, str] = {
    # 企業
    "adopt_service": "public",
    "reject_service": "private",
    "build_competitor": "public",
    "acquire_startup": "public",
    "invest_rd": "partial",
    "lobby_regulation": "partial",
    "partner": "public",
    "wait_and_observe": "private",
    # フリーランス
    "adopt_tool": "public",
    "offer_service": "public",
    "upskill": "private",
    "build_portfolio": "public",
    "raise_rate": "public",
    "switch_platform": "public",
    "network": "public",
    "rest": "private",
    # 個人開発者
    "launch_competing_product": "public",
    "pivot_product": "public",
    "open_source": "public",
    "monetize": "public",
    "abandon_project": "private",
    "seek_funding": "partial",
    "build_community": "public",
    # 行政
    "regulate": "public",
    "subsidize": "public",
    "certify": "public",
    "investigate": "public",
    "deregulate": "public",
    "partner_public": "public",
    "issue_guideline": "public",
    # 投資家/VC
    "invest_seed": "public",
    "invest_series": "public",
    "divest": "partial",
    "fund_competitor": "partial",
    "market_signal": "public",
    "wait_and_see": "private",
    "mentor": "partial",
    # プラットフォーマー
    "launch_competing_feature": "public",
    "acquire_service": "public",
    "partner_integrate": "public",
    "restrict_api": "public",
    "price_undercut": "public",
    "ignore": "private",
    "open_platform": "public",
    # 業界団体
    "endorse": "public",
    "set_standard": "public",
    "reject_standard": "public",
    "create_alternative": "public",
    "educate_market": "public",
    "observe": "private",
    "publish_report": "public",
    # エンドユーザー
    "adopt_new_service": "public",
    "stay_with_current": "private",
    "trial": "public",
    "churn": "public",
    "recommend": "public",
    "complain": "public",
    "compare_alternatives": "partial",
}


def get_visibility(action_type: str) -> str:
    """行動タイプから可視性を取得する."""
    return ACTION_VISIBILITY.get(action_type, "public")


class AgentMemoryStore:
    """エージェントの行動・状態を知識グラフに記録・取得する."""

    def __init__(self, graph_client: GraphClient, simulation_id: str = ""):
        self.graph = graph_client
        self.simulation_id = simulation_id

    async def ensure_agent_node(
        self,
        agent_id: str,
        name: str,
        agent_type: str,
        industry: str,
    ) -> None:
        """Agentノードが存在することを保証する（冪等）."""
        await self.graph.execute_write(
            "MERGE (a:Agent {agent_id: $agent_id, simulation_id: $sim_id}) "
            "SET a.name = $name, a.agent_type = $agent_type, "
            "    a.industry = $industry",
            {
                "agent_id": agent_id,
                "sim_id": self.simulation_id,
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
            "MATCH (a:Agent {agent_id: $agent_id, simulation_id: $sim_id}) "
            "CREATE (s:AgentSnapshot {"
            "  agent_id: $agent_id, simulation_id: $sim_id, round: $round, "
            "  revenue: $revenue, cost: $cost, headcount: $headcount, "
            "  active_contracts: $active_contracts"
            "}) "
            "CREATE (a)-[:STATE_AT {round: $round}]->(s)",
            {
                "agent_id": agent_id,
                "sim_id": self.simulation_id,
                "round": round_number,
                "revenue": state.get("revenue", 0.0),
                "cost": state.get("cost", 0.0),
                "headcount": state.get("headcount", 0),
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
            "MATCH (a:Agent {agent_id: $agent_id, simulation_id: $sim_id}) "
            "CREATE (ar:ActionRecord {"
            "  agent_id: $agent_id, agent_name: $agent_name, "
            "  simulation_id: $sim_id, "
            "  round: $round, action_type: $action_type, "
            "  description: $description, visibility: $visibility"
            "}) "
            "CREATE (a)-[:PERFORMED {round: $round}]->(ar)",
            {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "sim_id": self.simulation_id,
                "round": round_number,
                "action_type": action_type,
                "description": description,
                "visibility": visibility,
            },
        )

    async def record_market_effect(
        self,
        agent_id: str,
        round_number: int,
        action_type: str,
        skill: str,
        demand_delta: float,
        supply_delta: float,
    ) -> None:
        """行動が市場に与えた影響を因果チェーンとして記録する.

        ActionRecord -[CAUSED]-> MarketEffect -[AFFECTS_SKILL]-> Skill
        """
        if abs(demand_delta) < 0.001 and abs(supply_delta) < 0.001:
            return  # 影響が微小なら記録しない
        try:
            await self.graph.execute_write(
                "MATCH (a:Agent {agent_id: $agent_id, simulation_id: $sim_id})"
                "-[:PERFORMED]->(ar:ActionRecord {round: $round, action_type: $action_type}) "
                "WITH ar LIMIT 1 "
                "CREATE (me:MarketEffect {"
                "  simulation_id: $sim_id, round: $round, "
                "  skill: $skill, demand_delta: $demand_delta, "
                "  supply_delta: $supply_delta"
                "}) "
                "CREATE (ar)-[:CAUSED]->(me)",
                {
                    "agent_id": agent_id,
                    "sim_id": self.simulation_id,
                    "round": round_number,
                    "action_type": action_type,
                    "skill": skill,
                    "demand_delta": round(demand_delta, 4),
                    "supply_delta": round(supply_delta, 4),
                },
            )
        except Exception:
            pass  # 因果記録失敗は致命的ではない

    async def get_visible_actions(
        self,
        observer_id: str,
        from_round: int = 1,
        to_round: int | None = None,
    ) -> list[dict[str, Any]]:
        """観察者から見える行動を取得する（同一シミュレーション内のみ）."""
        to_round_val = to_round or 9999

        return await self.graph.execute_read(
            "MATCH (a:Agent)-[:PERFORMED]->(ar:ActionRecord) "
            "WHERE ar.simulation_id = $sim_id "
            "  AND ar.round >= $from_round AND ar.round <= $to_round "
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
                "sim_id": self.simulation_id,
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
        """自分自身の行動・状態履歴を取得する（同一シミュレーション内）."""
        actions = await self.graph.execute_read(
            "MATCH (:Agent {agent_id: $agent_id, simulation_id: $sim_id})"
            "-[:PERFORMED]->(ar:ActionRecord) "
            "RETURN ar.action_type AS action_type, ar.description AS description, "
            "       ar.round AS round "
            "ORDER BY ar.round DESC "
            "LIMIT $limit",
            {"agent_id": agent_id, "sim_id": self.simulation_id, "limit": last_n_rounds * 2},
        )

        snapshots = await self.graph.execute_read(
            "MATCH (:Agent {agent_id: $agent_id, simulation_id: $sim_id})"
            "-[:STATE_AT]->(s:AgentSnapshot) "
            "RETURN s.round AS round, s.revenue AS revenue, s.cost AS cost, "
            "       s.headcount AS headcount "
            "ORDER BY s.round DESC "
            "LIMIT $limit",
            {"agent_id": agent_id, "sim_id": self.simulation_id, "limit": last_n_rounds},
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
        """エージェントのスキル習熟度をグラフに記録する."""
        for skill_name, proficiency in skills.items():
            try:
                await self.graph.execute_write(
                    "MATCH (a:Agent {agent_id: $agent_id, simulation_id: $sim_id}) "
                    "MERGE (s:Skill {name: $skill_name}) "
                    "MERGE (a)-[r:SKILLED_IN]->(s) "
                    "SET r.proficiency = $proficiency",
                    {
                        "agent_id": agent_id,
                        "sim_id": self.simulation_id,
                        "skill_name": skill_name,
                        "proficiency": proficiency,
                    },
                )
            except Exception:
                logger.warning("スキル記録失敗: agent=%s, skill=%s", agent_id, skill_name)

    async def record_relationship(
        self,
        from_id: str,
        to_id: str,
        relation_type: str,
        round_number: int,
        description: str = "",
    ) -> None:
        """エージェント間の関係をグラフに記録する（冪等: 同じ関係は上書き）."""
        await self.graph.execute_write(
            "MATCH (a:Agent {agent_id: $from_id, simulation_id: $sim_id}) "
            "MATCH (b:Agent {agent_id: $to_id, simulation_id: $sim_id}) "
            "MERGE (a)-[r:RELATES_TO {relation_type: $rel_type}]->(b) "
            "SET r.since_round = $round, r.description = $desc",
            {
                "from_id": from_id,
                "to_id": to_id,
                "sim_id": self.simulation_id,
                "rel_type": relation_type,
                "round": round_number,
                "desc": description,
            },
        )

    async def get_related_agents(
        self, agent_id: str
    ) -> list[dict[str, Any]]:
        """このエージェントと関係のあるエージェント一覧を取得する."""
        return await self.graph.execute_read(
            "MATCH (a:Agent {agent_id: $agent_id, simulation_id: $sim_id})"
            "-[r:RELATES_TO]-(b:Agent) "
            "RETURN b.agent_id AS agent_id, b.name AS name, "
            "       r.relation_type AS relation_type, "
            "       r.description AS description, "
            "       r.since_round AS since_round "
            "ORDER BY r.since_round DESC",
            {"agent_id": agent_id, "sim_id": self.simulation_id},
        )
