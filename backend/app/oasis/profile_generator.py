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
            "reputation": agent.state.reputation,
            "satisfaction": agent.state.satisfaction,
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
        "enterprise": "Market defender" if conservatism >= 0.6 else "Market challenger",
        "freelancer": "Cautious adopter" if conservatism >= 0.6 else "Early adopter",
        "indie_developer": "Niche builder" if conservatism >= 0.6 else "Disruptor",
        "government": "Regulatory enforcer" if conservatism >= 0.6 else "Innovation promoter",
        "investor": "Conservative investor" if conservatism >= 0.6 else "Growth investor",
        "platformer": "Platform defender" if conservatism >= 0.6 else "Platform expander",
        "community": "Standard keeper" if conservatism >= 0.6 else "Community builder",
        "end_user": "Loyal user" if conservatism >= 0.6 else "Open to alternatives",
    }
    return stances.get(stakeholder_type, "Neutral observer")
