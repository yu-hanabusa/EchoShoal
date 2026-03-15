"""Freelancer (フリーランス) agent — service as extension of contract work."""

from __future__ import annotations

from app.simulation.agents.base import BaseAgent


class FreelancerAgent(BaseAgent):
    """フリーランスエージェント.

    対象サービスを自分の業務に取り入れるか、
    それを活用したサービス提供を行うかを判断する。
    """

    def available_actions(self) -> list[str]:
        return [
            "adopt_tool",         # 対象サービスをツールとして採用
            "offer_service",      # サービスを活用した受託を提供
            "upskill",            # 関連スキル習得
            "build_portfolio",    # ポートフォリオ構築
            "raise_rate",         # 単価交渉（上げる）
            "switch_platform",    # 別プラットフォームに移行
            "network",            # 人脈構築・コミュニティ参加
            "rest",               # 休養
        ]
