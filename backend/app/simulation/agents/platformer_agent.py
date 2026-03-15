"""Platformer (プラットフォーマー) agent — AWS, Google, Microsoft, etc."""

from __future__ import annotations

from app.simulation.agents.base import BaseAgent


class PlatformerAgent(BaseAgent):
    """プラットフォーマーエージェント.

    AWS/Google/Microsoft等の大手テック企業。
    競合機能をリリースするか、買収するか、提携するかなどを判断する。
    """

    def available_actions(self) -> list[str]:
        return [
            "launch_competing_feature",  # 競合機能をリリース
            "acquire_service",           # サービスを買収
            "partner_integrate",         # API連携・パートナーシップ
            "restrict_api",              # API制限・囲い込み
            "price_undercut",            # 価格競争（低価格で対抗）
            "ignore",                    # 無視（市場規模が小さいと判断）
            "open_platform",             # プラットフォーム開放
        ]
