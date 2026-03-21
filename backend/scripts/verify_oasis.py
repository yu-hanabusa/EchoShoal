"""OASIS + Ollama 動作検証スクリプト.

検証項目:
1. OASIS環境がOllamaで起動すること
2. エージェントが1回発言できること
3. SQLiteにアクションログが記録されること
"""

import asyncio
import os
import sqlite3
import sys
import tempfile

# プロジェクトのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def verify_oasis_basic():
    """OASIS基本動作検証."""
    print("=" * 60)
    print("OASIS + Ollama 動作検証")
    print("=" * 60)

    # Step 1: CAMEL-AIモデル作成
    print("\n[1/5] CAMEL-AIモデル作成...")
    try:
        from camel.models import ModelFactory
        from camel.types import ModelPlatformType

        model = ModelFactory.create(
            model_platform=ModelPlatformType.OLLAMA,
            model_type="qwen2.5:14b",
            url="http://localhost:11434/v1",
            model_config_dict={
                "temperature": 0.7,
                "max_tokens": 512,
            },
        )
        print("  OK: CAMEL-AIモデル作成成功")
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

    # Step 2: AgentGraph作成
    print("\n[2/5] AgentGraph作成...")
    try:
        from oasis import AgentGraph, SocialAgent
        from oasis.social_agent.agent import UserInfo
        from oasis.social_platform.typing import ActionType

        agent_graph = AgentGraph()
        available_actions = ActionType.get_default_reddit_actions()

        # 3体のテストエージェント
        agents_data = [
            {
                "name": "TechStartup",
                "desc": "You are TechStartup, a new entrant in the business chat market. "
                        "Discuss your product's advantages and market strategy.",
            },
            {
                "name": "EnterpriseCorp",
                "desc": "You are EnterpriseCorp, a large traditional company evaluating new services. "
                        "Share your perspective on adoption criteria and concerns.",
            },
            {
                "name": "IndustryAnalyst",
                "desc": "You are IndustryAnalyst, a market researcher. "
                        "Provide analysis and opinions on the market dynamics.",
            },
        ]

        social_agents = []
        for i, data in enumerate(agents_data):
            user_info = UserInfo(
                user_name=f"agent_{i}",
                name=data["name"],
                description=data["desc"],
                profile={
                    "other_info": {
                        "user_profile": data["desc"],
                        "gender": "Non-binary",
                        "age": 30,
                        "mbti": "INTJ",
                        "country": "Japan",
                    }
                },
                recsys_type="reddit",
            )
            agent = SocialAgent(
                agent_id=i,
                user_info=user_info,
                agent_graph=agent_graph,
                model=model,
                available_actions=available_actions,
            )
            agent_graph.add_agent(agent)
            social_agents.append(agent)

        # 初期フォロー関係
        agent_graph.add_edge(0, 1)
        agent_graph.add_edge(1, 0)
        agent_graph.add_edge(2, 0)
        agent_graph.add_edge(2, 1)

        print(f"  OK: {agent_graph.get_num_nodes()}ノード, {agent_graph.get_num_edges()}エッジ")
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 3: OASIS環境作成
    print("\n[3/5] OASIS環境作成...")
    db_path = os.path.join(tempfile.gettempdir(), "oasis_verify.db")
    try:
        import oasis

        env = oasis.make(
            agent_graph=agent_graph,
            platform=oasis.DefaultPlatformType.REDDIT,
            database_path=db_path,
        )
        await env.reset()
        print(f"  OK: OASIS環境起動 (DB: {db_path})")
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: シード投稿 + LLMアクション実行
    print("\n[4/5] シード投稿 + LLMアクション...")
    try:
        from oasis import LLMAction, ManualAction

        # シード投稿
        seed_actions = {
            social_agents[0]: [ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": "Excited to announce our new business chat service! "
                             "It features AI-powered translation and ISMAP certification."},
            )]
        }
        await env.step(seed_actions)
        print("  OK: シード投稿完了")

        # LLMアクション（全エージェントが自律的に行動）
        print("  LLMアクション実行中（Ollamaで推論中...）")
        llm_actions = {agent: LLMAction() for agent in social_agents}
        await env.step(llm_actions)
        print("  OK: LLMアクション完了")

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        await env.close()
        return False

    # Step 5: SQLiteからアクションログ確認
    print("\n[5/5] アクションログ確認...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 投稿数
        cursor.execute("SELECT COUNT(*) FROM post")
        post_count = cursor.fetchone()[0]

        # コメント数
        try:
            cursor.execute("SELECT COUNT(*) FROM comment")
            comment_count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            comment_count = 0

        # トレース数
        cursor.execute("SELECT COUNT(*) FROM trace")
        trace_count = cursor.fetchone()[0]

        # 投稿内容のサンプル
        cursor.execute("SELECT u.name, p.content FROM post p LEFT JOIN user u ON p.user_id = u.user_id LIMIT 5")
        posts = cursor.fetchall()

        conn.close()

        print(f"  投稿数: {post_count}")
        print(f"  コメント数: {comment_count}")
        print(f"  トレース数: {trace_count}")
        print("\n  --- 投稿サンプル ---")
        for name, content in posts:
            print(f"  [{name}] {content[:100]}...")

        await env.close()

        # クリーンアップ
        if os.path.exists(db_path):
            os.unlink(db_path)

        if post_count > 0 and trace_count > 0:
            print("\n" + "=" * 60)
            print("検証1 合格: OASISがOllamaで起動し、エージェントが発言できました")
            print("=" * 60)
            return True
        else:
            print("\n  FAIL: アクションログが空です")
            return False

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        await env.close()
        return False


if __name__ == "__main__":
    result = asyncio.run(verify_oasis_basic())
    sys.exit(0 if result else 1)
