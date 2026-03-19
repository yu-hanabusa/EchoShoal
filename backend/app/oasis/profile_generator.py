"""OASIS プロファイル生成 — EchoShoalエージェント → OASISプロファイル変換.

MiroFish方式: AgentGeneratorが生成したBaseAgentを
OASISが要求するプロファイル形式（辞書/CSV互換）に変換する。
パーソナリティ情報はOASISの背景メモリとして注入。
"""

from __future__ import annotations

import logging
from typing import Any

from app.simulation.agents.base import BaseAgent

logger = logging.getLogger(__name__)


def agent_to_oasis_profile(agent: BaseAgent) -> dict[str, Any]:
    """EchoShoalのBaseAgentをOASISプロファイル辞書に変換する.

    Returns:
        OASISが要求する形式のプロファイル辞書:
        - user_id: エージェントID
        - user_name: エージェント名
        - bio: 説明文（ステークホルダー種別 + description）
        - personality_description: 性格の詳細記述（LLMプロンプト注入用）
        - stakeholder_type: 元のステークホルダー種別
        - available_actions: このエージェントが取りうるアクション
    """
    p = agent.personality
    personality_lines = []

    if p.description:
        personality_lines.append(p.description)

    # 性格傾向を自然言語化
    traits = {
        "conservatism": ("conservative, prefers proven approaches",
                         "innovative, embraces new approaches"),
        "bandwagon": ("follows industry trends closely",
                      "independent thinker, resists trends"),
        "overconfidence": ("bold risk-taker, may underestimate risks",
                           "cautious, carefully evaluates risks"),
        "info_sensitivity": ("data-driven, highly informed",
                             "may miss market signals"),
    }
    for attr, (high_desc, low_desc) in traits.items():
        val = getattr(p, attr, 0.5)
        if val >= 0.7:
            personality_lines.append(high_desc)
        elif val <= 0.3:
            personality_lines.append(low_desc)

    personality_text = ". ".join(personality_lines) if personality_lines else "Balanced decision-maker"

    # ステークホルダー種別に応じたスタンスを生成
    stakeholder = agent.profile.stakeholder_type.value
    stance = _infer_stance(stakeholder, p.conservatism)

    # bio生成
    bio_parts = [f"[{stakeholder.upper()}]"]
    if agent.profile.description:
        bio_parts.append(agent.profile.description)
    bio = " | ".join(bio_parts)

    return {
        "user_id": agent.id,
        "user_name": agent.name,
        "bio": bio,
        "personality_description": personality_text,
        "stance": stance,
        "stakeholder_type": stakeholder,
        "available_actions": agent.available_actions(),
        # エージェント初期状態（OASIS背景メモリとして注入）
        "initial_state": {
            "revenue": agent.state.revenue,
            "cost": agent.state.cost,
            "headcount": agent.state.headcount,
        },
        # OASISのRedditプロファイルに必須のフィールド
        "gender": "Non-binary",
        "age": 35,
        "mbti": _infer_mbti(p),
        "country": "Japan",
    }


def agents_to_oasis_profiles(agents: list[BaseAgent]) -> list[dict[str, Any]]:
    """複数エージェントを一括変換する."""
    profiles = []
    for agent in agents:
        try:
            profile = agent_to_oasis_profile(agent)
            profiles.append(profile)
        except Exception:
            logger.warning("OASISプロファイル変換失敗: %s", agent.name)
    logger.info("OASISプロファイル変換完了: %d/%d体", len(profiles), len(agents))
    return profiles


def build_agent_graph(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """OASISエージェントグラフを構築する.

    プロファイルリストから、OASIS環境に渡すエージェントグラフ構造を生成。
    初期関係はステークホルダー種別に基づいて推定する。
    """
    nodes = []
    edges = []

    # ノード生成
    for profile in profiles:
        nodes.append({
            "id": profile["user_id"],
            "profile": profile,
        })

    # 初期エッジ: 同じステークホルダー種別のエージェント同士をフォロー関係に
    by_type: dict[str, list[str]] = {}
    for profile in profiles:
        st = profile["stakeholder_type"]
        by_type.setdefault(st, []).append(profile["user_id"])

    for agent_ids in by_type.values():
        for i, aid in enumerate(agent_ids):
            for bid in agent_ids[i + 1:]:
                edges.append({"source": aid, "target": bid, "relation": "follows"})
                edges.append({"source": bid, "target": aid, "relation": "follows"})

    # クロスタイプの初期関係（投資家→企業、行政→全体など）
    investors = by_type.get("investor", [])
    enterprises = by_type.get("enterprise", [])
    for inv_id in investors:
        for ent_id in enterprises:
            edges.append({"source": inv_id, "target": ent_id, "relation": "follows"})

    government = by_type.get("government", [])
    for gov_id in government:
        for profile in profiles:
            if profile["user_id"] != gov_id:
                edges.append({"source": gov_id, "target": profile["user_id"], "relation": "follows"})

    logger.info("OASISエージェントグラフ構築: %dノード, %dエッジ", len(nodes), len(edges))
    return {"nodes": nodes, "edges": edges}


def _infer_mbti(personality) -> str:
    """性格パラメータからMBTIタイプを推定する."""
    e_i = "E" if personality.bandwagon >= 0.5 else "I"
    s_n = "N" if personality.info_sensitivity >= 0.5 else "S"
    t_f = "T" if personality.conservatism >= 0.5 else "F"
    j_p = "J" if personality.sunk_cost_bias >= 0.5 else "P"
    return f"{e_i}{s_n}{t_f}{j_p}"


def _infer_stance(stakeholder_type: str, conservatism: float) -> str:
    """ステークホルダー種別と保守性からスタンスを推定する."""
    stances = {
        "enterprise": "自社サービスの優位性を主張し、新規参入者には警戒的。市場シェアを守る立場" if conservatism >= 0.6 else "市場の変化に対応し、必要なら競合と差別化を図る",
        "freelancer": "実績あるツールを好み、乗り換えに慎重" if conservatism >= 0.6 else "新しいツールを積極的に試し、良ければ推薦する",
        "indie_developer": "既存の枠組みで堅実に開発" if conservatism >= 0.6 else "市場を破壊する革新的なアプローチを好む",
        "government": "規制と安全性を重視。新サービスには慎重な審査が必要" if conservatism >= 0.6 else "イノベーション促進の立場。新サービスの導入を後押し",
        "investor": "安定した収益モデルを重視。過大な期待には懐疑的" if conservatism >= 0.6 else "成長可能性に投資。新サービスの市場拡大に期待",
        "platformer": "自社プラットフォームの優位性を強調し、競合サービスには対抗策を講じる。新参者を脅威として認識" if conservatism >= 0.6 else "自社の強みを活かしつつ、市場拡大の機会を探る",
        "community": "業界の標準化と公正な競争を重視" if conservatism >= 0.6 else "新しいサービスやツールの普及を支援する",
        "end_user": "現在使っているサービスに満足しており、乗り換えに消極的" if conservatism >= 0.6 else "より良いサービスがあれば乗り換えを検討する",
    }
    return stances.get(stakeholder_type, "中立的な立場で市場を観察")
