"""Government (行政) agent — regulations, subsidies, public services."""

from __future__ import annotations

from app.simulation.agents.base import BaseAgent


class GovernmentAgent(BaseAgent):
    """行政エージェント.

    規制を作るか、補助金を出すか、認証を与えるかなどを判断する。
    対象サービスの市場環境を大きく変える力を持つ。
    """

    def available_actions(self) -> list[str]:
        return [
            "regulate",           # 規制を導入
            "subsidize",          # 補助金・助成金を出す
            "certify",            # 認証・承認を与える
            "investigate",        # 調査・監査を行う
            "deregulate",         # 規制緩和
            "partner_public",     # 官民連携
            "issue_guideline",    # ガイドライン策定
        ]
