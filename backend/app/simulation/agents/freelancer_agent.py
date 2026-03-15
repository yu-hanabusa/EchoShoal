"""Freelancer (フリーランス) agent — service as extension of contract work."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.models import ServiceMarketState


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

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        match action.action_type:
            case "adopt_tool":
                self.state.cost += 3
                self.state.satisfaction += 0.05
                self._improve_capability(action.parameters.get("dimension", "tech_maturity"), 0.1)
            case "offer_service":
                self.state.revenue += 15
                self.state.active_contracts += 1
                self._improve_capability("revenue_potential", 0.08)
            case "upskill":
                self.state.cost += 5
                self.state.revenue *= 0.8  # 学習中は稼働減
                self._improve_capability(action.parameters.get("dimension", "tech_maturity"), 0.12)
            case "build_portfolio":
                self.state.cost += 3
                self.state.reputation += 0.05
                self._improve_capability("market_awareness", 0.08)
            case "raise_rate":
                self.state.revenue *= 1.1
                self.state.reputation += 0.03
            case "switch_platform":
                self.state.cost += 5
                self.state.satisfaction -= 0.03
                self._improve_capability("ecosystem_health", 0.05)
            case "network":
                self.state.cost += 2
                self.state.reputation += 0.05
                self._improve_capability("market_awareness", 0.05)
            case "rest":
                self.state.satisfaction += 0.1
                self.state.revenue *= 0.3

        self._clamp_state()
