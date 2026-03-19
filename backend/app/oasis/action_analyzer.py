"""OASIS アクションログ分析 — SNSアクティビティから市場インサイトを抽出.

OASISのSQLiteデータベースからアクションログを読み取り、
投稿内容・コメント・リポスト数から市場動向を分析する。

分析結果はLLMによる市場ディメンション更新の入力として使用される。
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from app.oasis.simulation_runner import _truncate_at_sentence

logger = logging.getLogger(__name__)


@dataclass
class RoundActivity:
    """1ラウンドのSNSアクティビティ集計."""

    round_number: int = 0
    posts: list[dict[str, Any]] = field(default_factory=list)
    comments: list[dict[str, Any]] = field(default_factory=list)
    likes: int = 0
    dislikes: int = 0
    reposts: int = 0
    new_follows: int = 0
    total_engagement: int = 0

    # コンテンツ分析
    top_topics: list[str] = field(default_factory=list)
    sentiment_signals: list[str] = field(default_factory=list)


@dataclass
class CumulativeStats:
    """シミュレーション全体の累積統計."""

    total_posts: int = 0
    total_comments: int = 0
    total_likes: int = 0
    total_dislikes: int = 0
    total_follows: int = 0
    most_active_agents: list[str] = field(default_factory=list)
    most_discussed_topics: list[str] = field(default_factory=list)
    engagement_trend: str = ""  # "growing", "stable", "declining"


def extract_round_activity(
    db_path: str,
    round_number: int,
    agents_per_round: int = 20,
) -> RoundActivity:
    """OASISのSQLiteから特定ラウンドのアクティビティを抽出する.

    OASISはラウンド概念を持たないため、traceテーブルのタイムスタンプから
    推定する。実装ではラウンド番号に対応するオフセットで取得。
    """
    activity = RoundActivity(round_number=round_number)

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        offset = (round_number - 1) * agents_per_round * 3  # 推定オフセット

        # 投稿取得
        cursor.execute(
            "SELECT p.post_id, p.content, p.num_likes, p.num_dislikes, "
            "       p.num_shares, u.name AS author "
            "FROM post p "
            "LEFT JOIN user u ON p.user_id = u.user_id "
            "WHERE p.content IS NOT NULL AND p.content != '' "
            "ORDER BY p.created_at ASC "
            "LIMIT ? OFFSET ?",
            (agents_per_round * 2, offset),
        )
        for row in cursor.fetchall():
            activity.posts.append({
                "post_id": row["post_id"],
                "author": row["author"] or "Unknown",
                "content": _truncate_at_sentence(row["content"], 500),
                "likes": row["num_likes"],
                "dislikes": row["num_dislikes"],
                "shares": row["num_shares"],
            })

        # コメント取得
        cursor.execute(
            "SELECT c.content, c.num_likes, u.name AS author "
            "FROM comment c "
            "LEFT JOIN user u ON c.user_id = u.user_id "
            "ORDER BY c.created_at ASC "
            "LIMIT ? OFFSET ?",
            (agents_per_round * 2, offset),
        )
        for row in cursor.fetchall():
            activity.comments.append({
                "author": row["author"] or "Unknown",
                "content": _truncate_at_sentence(row["content"], 500) if row["content"] else "",
                "likes": row["num_likes"],
            })

        # 集計
        activity.likes = sum(p.get("likes", 0) for p in activity.posts)
        activity.dislikes = sum(p.get("dislikes", 0) for p in activity.posts)
        activity.reposts = sum(p.get("shares", 0) for p in activity.posts)
        activity.total_engagement = (
            activity.likes + len(activity.comments) + activity.reposts
        )

        # フォロー数
        try:
            cursor.execute("SELECT COUNT(*) FROM follow")
            activity.new_follows = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            pass

        conn.close()

    except Exception:
        logger.warning("ラウンドアクティビティ抽出失敗: round=%d", round_number)

    return activity


def extract_cumulative_stats(db_path: str) -> CumulativeStats:
    """シミュレーション全体の累積統計を取得する."""
    stats = CumulativeStats()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 各テーブルのカウント
        for table, attr in [
            ("post", "total_posts"),
            ("comment", "total_comments"),
            ("follow", "total_follows"),
        ]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
                setattr(stats, attr, cursor.fetchone()[0])
            except sqlite3.OperationalError:
                pass

        # いいね/ディスライクの合計
        try:
            cursor.execute("SELECT COALESCE(SUM(num_likes), 0), COALESCE(SUM(num_dislikes), 0) FROM post")
            row = cursor.fetchone()
            stats.total_likes = row[0]
            stats.total_dislikes = row[1]
        except sqlite3.OperationalError:
            pass

        # 最もアクティブなエージェント
        try:
            cursor.execute(
                "SELECT u.name, COUNT(*) AS action_count "
                "FROM trace t "
                "LEFT JOIN user u ON t.user_id = u.user_id "
                "GROUP BY t.user_id "
                "ORDER BY action_count DESC "
                "LIMIT 5"
            )
            stats.most_active_agents = [
                row[0] for row in cursor.fetchall() if row[0]
            ]
        except sqlite3.OperationalError:
            pass

        conn.close()

    except Exception:
        logger.warning("累積統計取得失敗")

    return stats


def build_market_analysis_prompt(
    activity: RoundActivity,
    cumulative: CumulativeStats,
) -> str:
    """アクティビティデータから市場分析用プロンプトを構築する."""
    post_summaries = []
    for p in activity.posts[:10]:
        post_summaries.append(
            f"  [{p['author']}] {p['content'][:100]} "
            f"(likes:{p['likes']}, dislikes:{p['dislikes']}, shares:{p['shares']})"
        )
    posts_text = "\n".join(post_summaries) if post_summaries else "  (no posts this round)"

    comment_summaries = []
    for c in activity.comments[:8]:
        comment_summaries.append(f"  [{c['author']}] {c['content'][:80]}")
    comments_text = "\n".join(comment_summaries) if comment_summaries else "  (no comments)"

    return (
        f"=== Round {activity.round_number} Social Media Activity ===\n\n"
        f"Posts:\n{posts_text}\n\n"
        f"Comments:\n{comments_text}\n\n"
        f"Engagement: {activity.total_engagement} total "
        f"(likes:{activity.likes}, comments:{len(activity.comments)}, "
        f"reposts:{activity.reposts})\n\n"
        f"Cumulative: {cumulative.total_posts} posts, "
        f"{cumulative.total_comments} comments, "
        f"{cumulative.total_follows} follow relationships\n"
        f"Most active: {', '.join(cumulative.most_active_agents[:3])}\n"
    )
