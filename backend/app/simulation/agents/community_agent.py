"""Community/Industry Group (業界団体/コミュニティ) agent."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.models import ServiceMarketState


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

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        match action.action_type:
            case "endorse":
                self.state.cost += 5
                self._improve_capability("market_awareness", 0.12)
                self._improve_capability("user_adoption", 0.08)
                self.state.reputation += 0.05
            case "set_standard":
                self.state.cost += 20
                self._improve_capability("tech_maturity", 0.15)
                self._improve_capability("ecosystem_health", 0.1)
                self.state.reputation += 0.08
            case "reject_standard":
                self.state.cost += 5
                self._improve_capability("competitive_pressure", 0.1)
                self._improve_capability("market_awareness", -0.05)
                self.state.reputation -= 0.03
            case "create_alternative":
                self.state.cost += 30
                self._improve_capability("competitive_pressure", 0.15)
                self._improve_capability("ecosystem_health", 0.08)
            case "educate_market":
                self.state.cost += 10
                self._improve_capability("market_awareness", 0.15)
                self._improve_capability("user_adoption", 0.05)
                self.state.reputation += 0.03
            case "publish_report":
                self.state.cost += 8
                self._improve_capability("market_awareness", 0.1)
                self.state.reputation += 0.05
            case "observe":
                pass  # 影響なし

        self._clamp_state()
