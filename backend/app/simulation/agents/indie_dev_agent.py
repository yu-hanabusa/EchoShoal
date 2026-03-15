"""Individual Developer (個人開発者) agent — self-initiated products."""

from __future__ import annotations

from app.simulation.agents.base import AgentAction, BaseAgent
from app.simulation.models import ServiceMarketState


class IndieDevAgent(BaseAgent):
    """個人開発者エージェント.

    自分のプロダクトで勝負する。対象サービスの競合を作るか、
    エコシステムに参加するかなどを判断する。
    """

    def available_actions(self) -> list[str]:
        return [
            "launch_competing_product",  # 競合プロダクトをリリース
            "pivot_product",             # 既存プロダクトの方向転換
            "open_source",               # OSSとして公開
            "monetize",                  # 収益化（有料化・広告等）
            "abandon_project",           # プロジェクト放棄
            "seek_funding",              # 資金調達を目指す
            "build_community",           # ユーザーコミュニティ構築
        ]

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        match action.action_type:
            case "launch_competing_product":
                self.state.cost += 10
                self.state.reputation += 0.05
                self._improve_capability("competitive_pressure", 0.12)
                self._improve_capability("tech_maturity", 0.08)
            case "pivot_product":
                self.state.cost += 5
                self.state.satisfaction -= 0.05
                self._improve_capability(action.parameters.get("dimension", "user_adoption"), 0.1)
            case "open_source":
                self.state.reputation += 0.08
                self.state.revenue *= 0.5  # 直接収益は減
                self._improve_capability("ecosystem_health", 0.15)
                self._improve_capability("market_awareness", 0.1)
            case "monetize":
                self.state.revenue += 10
                self.state.satisfaction += 0.03
                self._improve_capability("revenue_potential", 0.1)
            case "abandon_project":
                self.state.cost = max(0, self.state.cost - 5)
                self.state.satisfaction -= 0.1
                self.state.active_contracts = 0
            case "seek_funding":
                self.state.cost += 3
                self.state.reputation += 0.03
                self._improve_capability("funding_climate", 0.1)
            case "build_community":
                self.state.cost += 2
                self.state.reputation += 0.05
                self._improve_capability("ecosystem_health", 0.08)
                self._improve_capability("user_adoption", 0.05)

        self._clamp_state()
