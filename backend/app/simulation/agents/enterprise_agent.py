"""Enterprise (企業) agent — large, medium, startup companies."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.models import ServiceMarketState


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

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        match action.action_type:
            case "adopt_service":
                self.state.cost += 20
                self.state.satisfaction += 0.05
                self._improve_capability(action.parameters.get("dimension", "user_adoption"), 0.1)
            case "reject_service":
                self.state.satisfaction -= 0.02
            case "build_competitor":
                self.state.cost += 100
                self.state.headcount += 5
                self._improve_capability("competitive_pressure", 0.15)
                self._improve_capability("tech_maturity", 0.1)
            case "acquire_startup":
                cost = action.parameters.get("cost", 500)
                self.state.cost += cost
                self.state.reputation += 0.05
                self._improve_capability("market_awareness", 0.1)
            case "invest_rd":
                amount = action.parameters.get("amount", 50)
                self.state.cost += amount
                self._improve_capability(action.parameters.get("dimension", "tech_maturity"), 0.12)
            case "lobby_regulation":
                self.state.cost += 30
                self._improve_capability("regulatory_risk", 0.1)
                self.state.reputation -= 0.02
            case "partner":
                self.state.cost += 10
                self.state.reputation += 0.03
                self._improve_capability("ecosystem_health", 0.08)
            case "wait_and_observe":
                pass  # 影響なし

        self._clamp_state()
