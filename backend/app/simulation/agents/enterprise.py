"""Enterprise IT department agent (事業会社の情シス)."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.models import MarketState


class EnterpriseITAgent(BaseAgent):
    """事業会社IT部門エージェント.

    社内システムの保守・DX推進を担う。
    外部ベンダー依存 vs 内製化の意思決定が重要。
    """

    def available_actions(self) -> list[str]:
        return [
            "hire_internal",       # 社内エンジニア採用
            "outsource_project",   # 外部委託
            "start_dx",           # DXプロジェクト開始
            "maintain_legacy",    # レガシー保守
            "adopt_saas",         # SaaS導入
            "insource",           # 内製化推進
        ]

    def _execute_action(self, action: AgentAction, market: MarketState) -> None:
        match action.action_type:
            case "hire_internal":
                count = action.parameters.get("count", 1)
                self.state.headcount += count
                self.state.cost += count * 50  # 事業会社は給与高め
                self.state.satisfaction += 0.03  # 内製化は満足度向上
            case "outsource_project":
                budget = action.parameters.get("budget", 100)
                self.state.cost += budget
                self.state.active_contracts += 1
            case "start_dx":
                self.state.cost += 80
                self._improve_skill(action.parameters.get("skill", "cloud_infra"), 0.2)
                self.state.reputation += 0.05
            case "maintain_legacy":
                self.state.cost += 20
                self._improve_skill("legacy", 0.05)
                self.state.satisfaction -= 0.03  # レガシー保守は満足度低下
            case "adopt_saas":
                self.state.cost += 15  # 月額SaaS費用
                self.state.headcount = max(0, self.state.headcount - 1)
                self.state.satisfaction += 0.02
            case "insource":
                self.state.cost += 30
                self.state.headcount += 2
                self.state.active_contracts = max(0, self.state.active_contracts - 1)
                self.state.reputation += 0.03

        self._clamp_state()
