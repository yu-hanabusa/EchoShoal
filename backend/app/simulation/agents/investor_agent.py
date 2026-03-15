"""Investor/VC (投資家) agent — funding, market influence."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.models import ServiceMarketState


class InvestorAgent(BaseAgent):
    """投資家/VCエージェント.

    対象サービスに投資するか、競合に投資するか、
    市場シグナルを発するかなどを判断する。
    """

    def available_actions(self) -> list[str]:
        return [
            "invest_seed",        # シード投資
            "invest_series",      # シリーズ投資（大型）
            "divest",             # 投資引き上げ
            "fund_competitor",    # 競合に投資
            "market_signal",      # 市場シグナル発信（評価コメント等）
            "wait_and_see",       # 様子見
            "mentor",             # メンタリング・助言
        ]

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        match action.action_type:
            case "invest_seed":
                amount = action.parameters.get("amount", 100)
                self.state.cost += amount
                self._improve_capability("funding_climate", 0.15)
                self._improve_capability("market_awareness", 0.08)
                self.state.reputation += 0.03
            case "invest_series":
                amount = action.parameters.get("amount", 500)
                self.state.cost += amount
                self._improve_capability("funding_climate", 0.25)
                self._improve_capability("revenue_potential", 0.1)
                self.state.reputation += 0.05
            case "divest":
                self.state.revenue += 50
                self._improve_capability("funding_climate", -0.15)
                self.state.reputation -= 0.05
            case "fund_competitor":
                amount = action.parameters.get("amount", 200)
                self.state.cost += amount
                self._improve_capability("competitive_pressure", 0.15)
                self._improve_capability("funding_climate", 0.05)
            case "market_signal":
                sentiment = action.parameters.get("sentiment", "positive")
                if sentiment == "positive":
                    self._improve_capability("market_awareness", 0.1)
                    self.state.reputation += 0.03
                else:
                    self._improve_capability("market_awareness", -0.05)
                    self.state.reputation -= 0.02
            case "wait_and_see":
                pass  # 影響なし
            case "mentor":
                self.state.cost += 5
                self._improve_capability("tech_maturity", 0.05)
                self._improve_capability("ecosystem_health", 0.05)
                self.state.reputation += 0.02

        self._clamp_state()
