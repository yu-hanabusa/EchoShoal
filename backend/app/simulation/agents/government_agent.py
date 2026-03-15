"""Government (行政) agent — regulations, subsidies, public services."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.models import ServiceMarketState


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

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        match action.action_type:
            case "regulate":
                self.state.cost += 20
                self._improve_capability("regulatory_risk", 0.2)
                self.state.reputation += 0.02
            case "subsidize":
                self.state.cost += 50
                self._improve_capability("funding_climate", 0.15)
                self._improve_capability("user_adoption", 0.08)
                self.state.reputation += 0.05
            case "certify":
                self.state.cost += 10
                self._improve_capability("market_awareness", 0.1)
                self._improve_capability("regulatory_risk", -0.05)
                self.state.reputation += 0.03
            case "investigate":
                self.state.cost += 15
                self._improve_capability("regulatory_risk", 0.15)
                self.state.reputation -= 0.02
            case "deregulate":
                self.state.cost += 5
                self._improve_capability("regulatory_risk", -0.15)
                self._improve_capability("ecosystem_health", 0.08)
            case "partner_public":
                self.state.cost += 30
                self._improve_capability("user_adoption", 0.1)
                self._improve_capability("market_awareness", 0.08)
                self.state.reputation += 0.05
            case "issue_guideline":
                self.state.cost += 10
                self._improve_capability("regulatory_risk", 0.05)
                self._improve_capability("tech_maturity", 0.05)

        self._clamp_state()
