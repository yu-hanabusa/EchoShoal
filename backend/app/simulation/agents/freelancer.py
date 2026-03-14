"""Freelance engineer agent."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.agents.utils import _parse_skill
from app.simulation.models import MarketState


class FreelancerAgent(BaseAgent):
    """フリーランスエンジニアエージェント.

    個人で案件を受注。スキルと単価の最適化が重要。
    """

    def available_actions(self) -> list[str]:
        return [
            "take_contract",    # 案件受注
            "learn_skill",      # スキル習得
            "raise_rate",       # 単価交渉（上げる）
            "lower_rate",       # 単価交渉（下げる）
            "network",          # 人脈構築
            "rest",             # 休養（バーンアウト防止）
        ]

    def _execute_action(self, action: AgentAction, market: MarketState) -> None:
        match action.action_type:
            case "take_contract":
                skill_name = action.parameters.get("skill", "web_backend")
                sc = _parse_skill(skill_name)
                if sc is not None:
                    base_price = market.unit_prices.get(sc, 65.0)
                    proficiency = self.state.skills.get(sc, 0.3)
                    self.state.revenue = base_price * (0.7 + 0.6 * proficiency)
                    self.state.active_contracts = 1
                    self.state.satisfaction -= 0.02  # 稼働による疲労
            case "learn_skill":
                if self._improve_skill(action.parameters.get("skill", "ai_ml"), 0.12):
                    self.state.cost += 3  # 学習コスト
                    self.state.revenue *= 0.5  # 稼働減
            case "raise_rate":
                self.state.revenue *= 1.1
                self.state.reputation += 0.03
            case "lower_rate":
                self.state.revenue *= 0.9
                self.state.active_contracts += 1  # 単価下げると案件取りやすい
            case "network":
                self.state.cost += 2
                self.state.reputation += 0.05
            case "rest":
                self.state.satisfaction += 0.1
                self.state.revenue *= 0.3  # 休養中は収入減

        self._clamp_state()
