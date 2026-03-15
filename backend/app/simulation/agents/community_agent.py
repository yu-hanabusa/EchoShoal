"""Community/Industry Group (業界団体/コミュニティ) agent."""

from __future__ import annotations

from app.simulation.agents.base import BaseAgent


class CommunityAgent(BaseAgent):
    """業界団体/コミュニティエージェント.

    標準化を推進するか、代替を作るか、教育活動をするかなどを判断する。
    """

    def available_actions(self) -> list[str]:
        return [
            "endorse",              # 推薦・支持
            "set_standard",         # 標準規格として採用
            "reject_standard",      # 標準規格から除外
            "create_alternative",   # オープンな代替を作成
            "educate_market",       # 市場教育・啓蒙活動
            "observe",              # 様子見
            "publish_report",       # 調査レポート公開
        ]
