"""OASIS → Neo4j グラフ同期 — インタラクションから関係グラフを自動成長.

OASISのSQLiteデータベース（follow/comment/like/repost）から
エージェント間の関係を抽出し、Neo4jのRELATES_TOリレーションシップとして記録する。

MiroFish方式: インタラクション数に基づいて関係の強度が自動的に成長する。
  - フォロー → 関心 (interest)
  - コメント → 議論 (discussion)
  - リポスト → 拡散 (amplification)
  - いいね → 支持 (support)
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from app.core.graph.client import GraphClient

logger = logging.getLogger(__name__)


# OASISインタラクション → Neo4j関係タイプのマッピング
INTERACTION_TO_RELATION = {
    "follow": "interest",
    "comment": "discussion",
    "repost": "amplification",
    "like": "support",
    "dislike": "opposition",
    "quote": "reference",
}


@dataclass
class InteractionEdge:
    """エージェント間のインタラクションエッジ."""

    source_id: int  # OASIS user_id
    target_id: int  # OASIS user_id
    relation_type: str
    weight: int = 1  # インタラクション回数
    sample_content: str = ""  # コメント/投稿の内容サンプル


@dataclass
class GraphSyncResult:
    """同期結果のサマリー."""

    nodes_synced: int = 0
    edges_synced: int = 0
    new_edges: int = 0
    updated_edges: int = 0
    errors: int = 0


async def sync_oasis_to_neo4j(
    db_path: str,
    graph_client: GraphClient,
    simulation_id: str,
    agent_id_map: dict[int, str],
) -> GraphSyncResult:
    """OASISのSQLiteからインタラクションを抽出し、Neo4jに同期する.

    Args:
        db_path: OASISのSQLiteデータベースパス
        graph_client: Neo4jクライアント
        simulation_id: シミュレーションID
        agent_id_map: OASIS user_id → EchoShoal agent_id のマッピング
    """
    result = GraphSyncResult()

    try:
        edges = extract_interactions(db_path)
        logger.info(
            "OASISインタラクション抽出: %d件",
            len(edges),
        )

        for edge in edges:
            source_es_id = agent_id_map.get(edge.source_id)
            target_es_id = agent_id_map.get(edge.target_id)
            if not source_es_id or not target_es_id:
                continue

            try:
                await _upsert_relationship(
                    graph_client,
                    simulation_id,
                    source_es_id,
                    target_es_id,
                    edge.relation_type,
                    edge.weight,
                    edge.sample_content,
                )
                result.edges_synced += 1
            except Exception:
                result.errors += 1
                logger.debug(
                    "関係同期失敗: %s → %s (%s)",
                    source_es_id, target_es_id, edge.relation_type,
                )

        result.nodes_synced = len(agent_id_map)
        logger.info(
            "OASIS→Neo4j同期完了: %dノード, %dエッジ (%dエラー)",
            result.nodes_synced, result.edges_synced, result.errors,
        )

    except Exception:
        logger.exception("OASIS→Neo4j同期失敗")

    return result


def extract_interactions(db_path: str) -> list[InteractionEdge]:
    """OASISのSQLiteからすべてのインタラクションエッジを抽出する."""
    edges: list[InteractionEdge] = []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # フォロー関係
        edges.extend(_extract_follows(conn))

        # コメント関係（投稿者 → コメント者）
        edges.extend(_extract_comment_interactions(conn))

        # いいね関係
        edges.extend(_extract_like_interactions(conn))

        # リポスト関係
        edges.extend(_extract_repost_interactions(conn))

        conn.close()

    except Exception:
        logger.warning("インタラクション抽出失敗: %s", db_path)

    # 同一エッジを集約（重みを加算）
    return _aggregate_edges(edges)


def _extract_follows(conn: sqlite3.Connection) -> list[InteractionEdge]:
    """フォロー関係を抽出する."""
    edges = []
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT follower_id, followee_id FROM follow"
        )
        for row in cursor.fetchall():
            edges.append(InteractionEdge(
                source_id=row["follower_id"],
                target_id=row["followee_id"],
                relation_type="interest",
            ))
    except sqlite3.OperationalError:
        pass
    return edges


def _extract_comment_interactions(conn: sqlite3.Connection) -> list[InteractionEdge]:
    """コメントからの議論関係を抽出する.

    コメント者 → 投稿者 の「議論」関係として記録。
    """
    edges = []
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c.user_id AS commenter_id, p.user_id AS poster_id, "
            "       c.content "
            "FROM comment c "
            "JOIN post p ON c.post_id = p.post_id "
            "WHERE c.user_id != p.user_id"
        )
        for row in cursor.fetchall():
            edges.append(InteractionEdge(
                source_id=row["commenter_id"],
                target_id=row["poster_id"],
                relation_type="discussion",
                sample_content=row["content"][:100] if row["content"] else "",
            ))
    except sqlite3.OperationalError:
        pass
    return edges


def _extract_like_interactions(conn: sqlite3.Connection) -> list[InteractionEdge]:
    """いいね/ディスライクからの支持/反対関係を抽出する."""
    edges = []

    # いいね
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT l.user_id AS liker_id, p.user_id AS poster_id "
            "FROM \"like\" l "
            "JOIN post p ON l.post_id = p.post_id "
            "WHERE l.user_id != p.user_id"
        )
        for row in cursor.fetchall():
            edges.append(InteractionEdge(
                source_id=row["liker_id"],
                target_id=row["poster_id"],
                relation_type="support",
            ))
    except sqlite3.OperationalError:
        pass

    # ディスライク
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT d.user_id AS disliker_id, p.user_id AS poster_id "
            "FROM dislike d "
            "JOIN post p ON d.post_id = p.post_id "
            "WHERE d.user_id != p.user_id"
        )
        for row in cursor.fetchall():
            edges.append(InteractionEdge(
                source_id=row["disliker_id"],
                target_id=row["poster_id"],
                relation_type="opposition",
            ))
    except sqlite3.OperationalError:
        pass

    return edges


def _extract_repost_interactions(conn: sqlite3.Connection) -> list[InteractionEdge]:
    """リポスト/引用から拡散関係を抽出する."""
    edges = []
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT p1.user_id AS reposter_id, p2.user_id AS original_poster_id "
            "FROM post p1 "
            "JOIN post p2 ON p1.original_post_id = p2.post_id "
            "WHERE p1.original_post_id IS NOT NULL "
            "  AND p1.user_id != p2.user_id"
        )
        for row in cursor.fetchall():
            edges.append(InteractionEdge(
                source_id=row["reposter_id"],
                target_id=row["original_poster_id"],
                relation_type="amplification",
            ))
    except sqlite3.OperationalError:
        pass
    return edges


def _aggregate_edges(edges: list[InteractionEdge]) -> list[InteractionEdge]:
    """同一方向・同一タイプのエッジを集約し、重みを加算する."""
    aggregated: dict[tuple[int, int, str], InteractionEdge] = {}

    for edge in edges:
        key = (edge.source_id, edge.target_id, edge.relation_type)
        if key in aggregated:
            aggregated[key].weight += 1
            # より長いサンプルを保持
            if len(edge.sample_content) > len(aggregated[key].sample_content):
                aggregated[key].sample_content = edge.sample_content
        else:
            aggregated[key] = InteractionEdge(
                source_id=edge.source_id,
                target_id=edge.target_id,
                relation_type=edge.relation_type,
                weight=edge.weight,
                sample_content=edge.sample_content,
            )

    return list(aggregated.values())


async def _upsert_relationship(
    graph_client: GraphClient,
    simulation_id: str,
    source_id: str,
    target_id: str,
    relation_type: str,
    weight: int,
    description: str,
) -> None:
    """Neo4jにリレーションシップをUPSERTする.

    既存の関係があれば重みを更新、なければ新規作成。
    """
    await graph_client.execute_write(
        "MATCH (a:Agent {agent_id: $source_id, simulation_id: $sim_id}) "
        "MATCH (b:Agent {agent_id: $target_id, simulation_id: $sim_id}) "
        "MERGE (a)-[r:RELATES_TO {relation_type: $rel_type}]->(b) "
        "ON CREATE SET r.weight = $weight, r.description = $desc, "
        "              r.source = 'oasis', r.created_at = datetime() "
        "ON MATCH SET r.weight = r.weight + $weight, "
        "             r.updated_at = datetime()",
        {
            "source_id": source_id,
            "target_id": target_id,
            "sim_id": simulation_id,
            "rel_type": relation_type,
            "weight": weight,
            "desc": description[:200],
        },
    )


async def sync_round_interactions(
    db_path: str,
    graph_client: GraphClient,
    simulation_id: str,
    agent_id_map: dict[int, str],
    round_number: int,
) -> int:
    """特定ラウンドのインタラクションのみをNeo4jに同期する.

    毎ラウンド呼ばれることを想定。差分のみを同期する。
    """
    edges = extract_interactions(db_path)
    synced = 0

    for edge in edges:
        source_es_id = agent_id_map.get(edge.source_id)
        target_es_id = agent_id_map.get(edge.target_id)
        if not source_es_id or not target_es_id:
            continue

        try:
            await _upsert_relationship(
                graph_client, simulation_id,
                source_es_id, target_es_id,
                edge.relation_type, edge.weight,
                f"Round {round_number}: {edge.sample_content}",
            )
            synced += 1
        except Exception:
            pass

    return synced
