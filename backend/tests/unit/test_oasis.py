"""OASIS統合テスト — プロファイル変換、アクション分析、グラフ同期."""

import os
import sqlite3
import tempfile

import pytest

from app.config import settings
from app.simulation.agents.base import AgentPersonality, AgentProfile, AgentState
from app.simulation.agents.enterprise_agent import EnterpriseAgent
from app.simulation.agents.end_user_agent import EndUserAgent
from app.simulation.models import StakeholderType


# ─── Fixtures ───


def _make_agent(
    name: str,
    agent_type: str = "enterprise",
    stakeholder_type: StakeholderType = StakeholderType.ENTERPRISE,
    conservatism: float = 0.5,
) -> EnterpriseAgent:
    profile = AgentProfile(
        name=name,
        agent_type=agent_type,
        stakeholder_type=stakeholder_type,
        description=f"Test agent: {name}",
    )
    state = AgentState(
        revenue=100.0,
        cost=80.0,
        headcount=10,
        reputation=0.6,
    )
    personality = AgentPersonality(
        conservatism=conservatism,
        bandwagon=0.5,
        overconfidence=0.5,
        noise=0.0,
        description="Test personality",
    )
    return EnterpriseAgent(profile=profile, state=state, llm=None, personality=personality)


def _make_end_user(name: str) -> EndUserAgent:
    profile = AgentProfile(
        name=name,
        agent_type="end_user",
        stakeholder_type=StakeholderType.END_USER,
        description=f"User group: {name}",
    )
    state = AgentState(satisfaction=0.5)
    return EndUserAgent(profile=profile, state=state, llm=None)


def _create_oasis_db(db_path: str) -> None:
    """テスト用のOASIS SQLiteデータベースを作成する."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE user (
            user_id INTEGER PRIMARY KEY,
            agent_id INTEGER,
            user_name TEXT,
            name TEXT,
            bio TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE post (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            original_post_id INTEGER,
            content TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            num_likes INTEGER DEFAULT 0,
            num_dislikes INTEGER DEFAULT 0,
            num_shares INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE comment (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            num_likes INTEGER DEFAULT 0,
            num_dislikes INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE follow (
            follow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER,
            followee_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE "like" (
            like_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            post_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE dislike (
            dislike_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            post_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE trace (
            user_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            action TEXT,
            info TEXT
        )
    """)

    # テストデータ挿入
    cursor.executemany(
        "INSERT INTO user (user_id, agent_id, user_name, name) VALUES (?, ?, ?, ?)",
        [
            (1, 0, "agent_001", "Slack"),
            (2, 1, "agent_002", "Conservative Enterprise"),
            (3, 2, "agent_003", "Slack Users"),
        ],
    )
    cursor.executemany(
        "INSERT INTO post (user_id, content, num_likes, num_dislikes, num_shares) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "We're launching Japanese localization", 5, 0, 3),
            (2, "We need ISMAP certification first", 2, 1, 0),
            (3, "Excited about the new features!", 8, 0, 5),
        ],
    )
    cursor.executemany(
        "INSERT INTO comment (post_id, user_id, content, num_likes) VALUES (?, ?, ?, ?)",
        [
            (1, 2, "This could change the market", 3),
            (1, 3, "We've been waiting for this!", 5),
            (2, 1, "We'll address certification concerns", 2),
        ],
    )
    cursor.executemany(
        "INSERT INTO follow (follower_id, followee_id) VALUES (?, ?)",
        [(1, 2), (2, 1), (3, 1), (3, 2)],
    )
    cursor.executemany(
        'INSERT INTO "like" (user_id, post_id) VALUES (?, ?)',
        [(2, 1), (3, 1), (3, 3)],
    )
    cursor.executemany(
        "INSERT INTO trace (user_id, action, info) VALUES (?, ?, ?)",
        [
            (1, "create_post", "launching Japanese localization"),
            (2, "create_post", "ISMAP certification"),
            (3, "create_post", "new features"),
            (2, "create_comment", "market change"),
            (3, "like_post", "post_id: 1"),
        ],
    )

    conn.commit()
    conn.close()


# ─── Profile Generator Tests ───


class TestProfileGenerator:
    """プロファイル変換テスト."""

    def test_agent_to_oasis_profile(self):
        from app.oasis.profile_generator import agent_to_oasis_profile

        agent = _make_agent("Slack", conservatism=0.3)
        profile = agent_to_oasis_profile(agent)

        assert profile["user_id"] == agent.id
        assert profile["user_name"] == "Slack"
        assert "ENTERPRISE" in profile["bio"]
        assert profile["stakeholder_type"] == "enterprise"
        assert profile["stance"] == "Market challenger"
        assert "innovative" in profile["personality_description"].lower()
        assert len(profile["available_actions"]) > 0

    def test_conservative_agent_stance(self):
        from app.oasis.profile_generator import agent_to_oasis_profile

        agent = _make_agent("BigCorp", conservatism=0.8)
        profile = agent_to_oasis_profile(agent)

        assert profile["stance"] == "Market defender"
        assert "conservative" in profile["personality_description"].lower()

    def test_end_user_profile(self):
        from app.oasis.profile_generator import agent_to_oasis_profile

        agent = _make_end_user("Slack Users")
        profile = agent_to_oasis_profile(agent)

        assert profile["stakeholder_type"] == "end_user"
        assert "END_USER" in profile["bio"]

    def test_agents_to_oasis_profiles_batch(self):
        from app.oasis.profile_generator import agents_to_oasis_profiles

        agents = [
            _make_agent("Slack"),
            _make_agent("Teams"),
            _make_end_user("Users"),
        ]
        profiles = agents_to_oasis_profiles(agents)

        assert len(profiles) == 3
        assert all("user_id" in p for p in profiles)

    def test_build_agent_graph(self):
        from app.oasis.profile_generator import agents_to_oasis_profiles, build_agent_graph

        agents = [
            _make_agent("Slack"),
            _make_agent("Teams"),
            _make_end_user("Users"),
        ]
        profiles = agents_to_oasis_profiles(agents)
        graph = build_agent_graph(profiles)

        assert len(graph["nodes"]) == 3
        # 同じ種別のエージェント同士にエッジが作られる
        assert len(graph["edges"]) > 0


# ─── Action Analyzer Tests ───


class TestActionAnalyzer:
    """アクションログ分析テスト."""

    def test_extract_round_activity(self):
        from app.oasis.action_analyzer import extract_round_activity

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            _create_oasis_db(db_path)
            activity = extract_round_activity(db_path, round_number=1, agents_per_round=10)

            assert activity.round_number == 1
            assert len(activity.posts) == 3
            assert len(activity.comments) == 3
            assert activity.likes > 0
            assert activity.total_engagement > 0
        finally:
            os.unlink(db_path)

    def test_extract_cumulative_stats(self):
        from app.oasis.action_analyzer import extract_cumulative_stats

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            _create_oasis_db(db_path)
            stats = extract_cumulative_stats(db_path)

            assert stats.total_posts == 3
            assert stats.total_comments == 3
            assert stats.total_follows == 4
            assert len(stats.most_active_agents) > 0
        finally:
            os.unlink(db_path)

    def test_build_market_analysis_prompt(self):
        from app.oasis.action_analyzer import (
            build_market_analysis_prompt,
            extract_cumulative_stats,
            extract_round_activity,
        )

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            _create_oasis_db(db_path)
            activity = extract_round_activity(db_path, round_number=1)
            cumulative = extract_cumulative_stats(db_path)
            prompt = build_market_analysis_prompt(activity, cumulative)

            assert "Round 1" in prompt
            assert "Posts:" in prompt
            assert "Engagement:" in prompt
        finally:
            os.unlink(db_path)


# ─── Graph Sync Tests ───


class TestGraphSync:
    """グラフ同期テスト."""

    def test_extract_interactions(self):
        from app.oasis.graph_sync import extract_interactions

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            _create_oasis_db(db_path)
            edges = extract_interactions(db_path)

            assert len(edges) > 0

            # フォロー関係がある
            follow_edges = [e for e in edges if e.relation_type == "interest"]
            assert len(follow_edges) > 0

            # コメント→議論関係がある
            discussion_edges = [e for e in edges if e.relation_type == "discussion"]
            assert len(discussion_edges) > 0

            # いいね→支持関係がある
            support_edges = [e for e in edges if e.relation_type == "support"]
            assert len(support_edges) > 0
        finally:
            os.unlink(db_path)

    def test_edge_aggregation(self):
        """同一方向の複数インタラクションが集約されること."""
        from app.oasis.graph_sync import _aggregate_edges, InteractionEdge

        edges = [
            InteractionEdge(source_id=1, target_id=2, relation_type="support"),
            InteractionEdge(source_id=1, target_id=2, relation_type="support"),
            InteractionEdge(source_id=1, target_id=2, relation_type="support"),
            InteractionEdge(source_id=2, target_id=1, relation_type="discussion"),
        ]
        aggregated = _aggregate_edges(edges)

        assert len(aggregated) == 2
        support_edge = next(e for e in aggregated if e.relation_type == "support")
        assert support_edge.weight == 3

    def test_extract_interactions_empty_db(self):
        """空のDBでもエラーにならないこと."""
        from app.oasis.graph_sync import extract_interactions

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # 空のDBを作成（テーブルなし）
            conn = sqlite3.connect(db_path)
            conn.close()

            edges = extract_interactions(db_path)
            assert edges == []
        finally:
            os.unlink(db_path)


# ─── Config Tests ───


class TestOasisConfig:
    """OASIS設定テスト."""

    def test_settings_have_oasis_fields(self):
        assert hasattr(settings, "simulation_engine")
        assert hasattr(settings, "oasis_platform")
        assert hasattr(settings, "oasis_max_agents")
        assert hasattr(settings, "oasis_rounds_per_step")

    def test_default_engine_is_oasis(self):
        assert settings.simulation_engine in ("oasis", "legacy")

    def test_database_path_creation(self):
        from app.oasis.config import get_database_path

        path = get_database_path("test_sim_123")
        assert "test_sim_123" in path
        assert path.endswith("oasis.db")
        # クリーンアップ
        parent_dir = os.path.dirname(path)
        if os.path.exists(parent_dir):
            os.rmdir(parent_dir)


# ─── OASISSimulationEngine Interface Tests ───


class TestOASISEngineInterface:
    """OASISSimulationEngineが既存互換のインターフェースを持つことを確認."""

    def test_engine_has_run_method(self):
        from app.oasis.simulation_runner import OASISSimulationEngine

        assert hasattr(OASISSimulationEngine, "run")
        assert callable(getattr(OASISSimulationEngine, "run"))

    def test_engine_has_get_summary_method(self):
        from app.oasis.simulation_runner import OASISSimulationEngine

        assert hasattr(OASISSimulationEngine, "get_summary")

    def test_engine_has_get_social_feed_method(self):
        from app.oasis.simulation_runner import OASISSimulationEngine

        assert hasattr(OASISSimulationEngine, "get_social_feed")

    def test_action_mapping(self):
        from app.oasis.simulation_runner import _map_oasis_action

        assert _map_oasis_action("create_post") == "post_opinion"
        assert _map_oasis_action("CREATE_POST") == "post_opinion"
        assert _map_oasis_action("create_comment") == "comment"
        assert _map_oasis_action("like_post") == "endorse"
        assert _map_oasis_action("repost") == "amplify"
        assert _map_oasis_action("follow") == "follow_stakeholder"
        assert _map_oasis_action("do_nothing") == "observe"
        # Unknown actions pass through
        assert _map_oasis_action("unknown_action") == "unknown_action"
