"""SIer (System Integrator) company agent."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.agents.utils import _parse_skill
from app.simulation.models import MarketState


class SIerCompanyAgent(BaseAgent):
    """SIer企業エージェント.

    大規模システム開発を請負。多重下請け構造の元請け側。
    プロジェクト獲得と下請け管理が主な活動。
    """

    def available_actions(self) -> list[str]:
        return [
            "bid_project",      # プロジェクト入札
            "hire_engineers",   # エンジニア採用
            "outsource",        # 下請けに発注
            "invest_rd",        # R&D投資
            "offshore",         # オフショア開発
            "internal_training",  # 社内研修
        ]

    def _execute_action(self, action: AgentAction, market: MarketState) -> None:
        match action.action_type:
            case "bid_project":
                scale = action.parameters.get("scale", "medium")
                revenue_map = {"small": 50, "medium": 150, "large": 500}
                cost_map = {"small": 40, "medium": 120, "large": 400}
                self.state.revenue += revenue_map.get(scale, 150)
                self.state.cost += cost_map.get(scale, 120)
                self.state.active_contracts += 1
            case "hire_engineers":
                count = action.parameters.get("count", 2)
                self.state.headcount += count
                self.state.cost += count * 45  # SIerの方が人件費高い
            case "outsource":
                self.state.cost += 30
                self.state.revenue += 10  # 中抜き利益
                self.state.reputation -= 0.02  # 多重下請けは評判低下
            case "invest_rd":
                amount = action.parameters.get("amount", 20)
                self.state.cost += amount
                skill = action.parameters.get("skill", "ai_ml")
                sc = _parse_skill(skill)
                if sc is not None:
                    current = self.state.skills.get(sc, 0.0)
                    self.state.skills[sc] = min(1.0, current + 0.15)
            case "offshore":
                savings = action.parameters.get("savings", 20)
                self.state.cost -= savings
                self.state.reputation -= 0.03
            case "internal_training":
                self.state.cost += 10
                self.state.satisfaction += 0.05

        self._clamp_state()
