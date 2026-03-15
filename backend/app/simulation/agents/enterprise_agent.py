"""Enterprise (企業) agent — large, medium, startup companies."""

from __future__ import annotations

from app.simulation.agents.base import BaseAgent


class EnterpriseAgent(BaseAgent):
    """企業エージェント.

    対象サービスを採用するか、競合を作るか、買収するかなどを判断する。
    企業規模（大手・中堅・スタートアップ）によって行動傾向が異なる。
    """

    def available_actions(self) -> list[str]:
        return [
            "adopt_service",      # 対象サービスを採用
            "reject_service",     # 対象サービスを不採用
            "build_competitor",   # 競合サービスを自社開発
            "acquire_startup",    # サービス提供元を買収
            "invest_rd",          # R&D投資で代替技術開発
            "lobby_regulation",   # 規制ロビー活動
            "partner",            # サービス提供元と提携
            "wait_and_observe",   # 様子見
        ]
