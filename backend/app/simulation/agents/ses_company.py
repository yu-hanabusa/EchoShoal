"""SES (System Engineering Service) company agent."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.agents.utils import _parse_skill
from app.simulation.models import MarketState


class SESCompanyAgent(BaseAgent):
    """SES企業エージェント.

    SES企業はエンジニアを客先に派遣して利益を得る。
    マージン率と稼働率が重要なKPI。
    """

    def available_actions(self) -> list[str]:
        return [
            "recruit",          # エンジニア採用
            "upskill",          # 社員のスキルアップ研修
            "adjust_margin",    # マージン率調整
            "expand_sales",     # 営業拡大
            "release_bench",    # 待機社員の整理
            "shift_domain",     # 注力ドメイン変更
        ]

    def _execute_action(self, action: AgentAction, market: MarketState) -> None:
        match action.action_type:
            case "recruit":
                count = action.parameters.get("count", 1)
                self.state.headcount += count
                self.state.cost += count * 35  # 平均月35万コスト/人
            case "upskill":
                skill = action.parameters.get("skill")
                sc = _parse_skill(skill)
                if sc is not None:
                    current = self.state.skills.get(sc, 0.0)
                    self.state.skills[sc] = min(1.0, current + 0.1)
                    self.state.cost += 5  # 研修コスト
            case "adjust_margin":
                direction = action.parameters.get("direction", "up")
                delta = 0.02 if direction == "up" else -0.02
                self.state.revenue *= (1 + delta)
                self.state.reputation += -delta  # マージン上げると評判下がる
            case "expand_sales":
                self.state.cost += 10
                self.state.active_contracts += 1
                self.state.revenue += 15
            case "release_bench":
                count = min(action.parameters.get("count", 1), self.state.headcount)
                self.state.headcount -= count
                self.state.cost -= count * 35
                self.state.satisfaction -= 0.05  # 解雇は満足度低下
            case "shift_domain":
                pass  # ドメイン変更はスキル構成に影響（将来実装）

        self._clamp_state()
