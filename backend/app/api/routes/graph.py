"""知識グラフ可視化 API エンドポイント.

フロントエンドのグラフライブラリ（Cytoscape.js等）向けに
ノードとエッジのデータを提供する。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.graph.client import GraphClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])


async def _get_graph_client() -> GraphClient:
    client = GraphClient()
    if not await client.is_available():
        raise HTTPException(status_code=503, detail="Neo4jに接続できません")
    return client


@router.get("/visualization")
async def get_graph_visualization() -> dict[str, Any]:
    """知識グラフのノードとエッジをCytoscape.js形式で返す."""
    graph_client = await _get_graph_client()
    try:
        elements = await _build_cytoscape_elements(graph_client)
        return {"elements": elements}
    finally:
        await graph_client.close()


async def _build_cytoscape_elements(client: GraphClient) -> list[dict[str, Any]]:
    """Neo4jからCytoscape.jsのelements配列を構築する."""
    elements: list[dict[str, Any]] = []

    # ノード: Industry
    industries = await client.execute_read(
        "MATCH (i:Industry) RETURN i.name AS id, i.label_ja AS label"
    )
    for row in industries:
        elements.append({
            "data": {"id": f"industry_{row['id']}", "label": row["label"] or row["id"], "type": "Industry"},
        })

    # ノード: SkillCategory + Skill
    categories = await client.execute_read(
        "MATCH (sc:SkillCategory) "
        "OPTIONAL MATCH (s:Skill)-[:CATEGORIZED_AS]->(sc) "
        "RETURN sc.name AS cat_id, sc.label_ja AS cat_label, collect(s.name) AS skills"
    )
    for row in categories:
        cat_id = f"cat_{row['cat_id']}"
        elements.append({
            "data": {"id": cat_id, "label": row["cat_label"] or row["cat_id"], "type": "SkillCategory"},
        })
        for skill in (row["skills"] or []):
            skill_id = f"skill_{skill}"
            elements.append({
                "data": {"id": skill_id, "label": skill, "type": "Skill"},
            })
            elements.append({
                "data": {"source": skill_id, "target": cat_id, "label": "CATEGORIZED_AS"},
            })

    # ノード: Role
    roles = await client.execute_read(
        "MATCH (r:Role) RETURN r.name AS id, r.label_ja AS label"
    )
    for row in roles:
        elements.append({
            "data": {"id": f"role_{row['id']}", "label": row["label"] or row["id"], "type": "Role"},
        })

    # ノード: Policy
    policies = await client.execute_read(
        "MATCH (p:Policy) RETURN p.name AS id, p.description AS description"
    )
    for row in policies:
        elements.append({
            "data": {"id": f"policy_{row['id']}", "label": row["id"], "type": "Policy"},
        })

    # エッジ: Policy -[AFFECTS]-> Industry/Skill
    affects = await client.execute_read(
        "MATCH (p:Policy)-[a:AFFECTS]->(t) "
        "RETURN p.name AS source, t.name AS target, labels(t)[0] AS target_type, "
        "       a.impact_type AS impact_type"
    )
    for row in affects:
        target_prefix = "industry_" if row["target_type"] == "Industry" else "skill_"
        elements.append({
            "data": {
                "source": f"policy_{row['source']}",
                "target": f"{target_prefix}{row['target']}",
                "label": f"AFFECTS ({row.get('impact_type', '')})",
            },
        })

    # エッジ: Skill -[REQUIRES/EVOLVES_INTO]-> Skill
    skill_rels = await client.execute_read(
        "MATCH (s1:Skill)-[r]->(s2:Skill) "
        "WHERE type(r) IN ['REQUIRES', 'EVOLVES_INTO'] "
        "RETURN s1.name AS source, s2.name AS target, type(r) AS rel_type"
    )
    for row in skill_rels:
        elements.append({
            "data": {
                "source": f"skill_{row['source']}",
                "target": f"skill_{row['target']}",
                "label": row["rel_type"],
            },
        })

    # ノード: Document + MENTIONS edges
    docs = await client.execute_read(
        "MATCH (d:Document) "
        "OPTIONAL MATCH (d)-[:MENTIONS]->(e) "
        "RETURN d.doc_id AS doc_id, d.filename AS filename, "
        "       collect({name: e.name, type: labels(e)[0]}) AS mentions"
    )
    for row in docs:
        doc_node_id = f"doc_{row['doc_id']}"
        elements.append({
            "data": {"id": doc_node_id, "label": row["filename"], "type": "Document"},
        })
        for mention in (row["mentions"] or []):
            if mention.get("name"):
                prefix_map = {"Skill": "skill_", "Company": "company_", "Policy": "policy_"}
                target_prefix = prefix_map.get(mention.get("type", ""), "")
                target_id = f"{target_prefix}{mention['name']}"
                elements.append({
                    "data": {"source": doc_node_id, "target": target_id, "label": "MENTIONS"},
                })

    return elements
