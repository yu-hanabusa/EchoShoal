"""Platformer (プラットフォーマー) agent — AWS, Google, Microsoft, etc."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.models import ServiceMarketState


class PlatformerAgent(BaseAgent):
    """プラットフォーマーエージェント.

    AWS/Google/Microsoft等の大手テック企業。
    競合機能をリリースするか、買収するか、提携するかなどを判断する。
    """

    def available_actions(self) -> list[str]:
        return [
            "launch_competing_feature",  # 競合機能をリリース
            "acquire_service",           # サービスを買収
            "partner_integrate",         # API連携・パートナーシップ
            "restrict_api",              # API制限・囲い込み
            "price_undercut",            # 価格競争（低価格で対抗）
            "ignore",                    # 無視（市場規模が小さいと判断）
            "open_platform",             # プラットフォーム開放
        ]

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        match action.action_type:
            case "launch_competing_feature":
                self.state.cost += 50
                self._improve_capability("competitive_pressure", 0.25)
                self._improve_capability("market_awareness", 0.1)
                self.state.reputation += 0.02
            case "acquire_service":
                cost = action.parameters.get("cost", 1000)
                self.state.cost += cost
                self._improve_capability("competitive_pressure", -0.1)
                self._improve_capability("market_awareness", 0.15)
                self.state.reputation += 0.05
            case "partner_integrate":
                self.state.cost += 10
                self._improve_capability("ecosystem_health", 0.15)
                self._improve_capability("user_adoption", 0.08)
                self.state.reputation += 0.05
            case "restrict_api":
                self._improve_capability("competitive_pressure", 0.15)
                self._improve_capability("ecosystem_health", -0.1)
                self.state.reputation -= 0.08
            case "price_undercut":
                self.state.cost += 30
                self._improve_capability("competitive_pressure", 0.2)
                self._improve_capability("revenue_potential", -0.1)
            case "ignore":
                pass  # 影響なし
            case "open_platform":
                self.state.cost += 15
                self._improve_capability("ecosystem_health", 0.12)
                self._improve_capability("user_adoption", 0.05)
                self.state.reputation += 0.03

        self._clamp_state()
