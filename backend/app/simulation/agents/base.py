"""Base agent class for the Service Business Impact Simulation."""

from __future__ import annotations

import random
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field

from app.core.llm.router import LLMRouter, TaskType
from app.simulation.agents.utils import _parse_dimension
from app.simulation.models import StakeholderType, ServiceMarketState, MarketDimension


class AgentPersonality(BaseModel):
    """エージェントの性格・認知バイアス.

    各パラメータは 0.0〜1.0 の範囲で設定する。
    """

    conservatism: float = 0.5
    """保守性: 高い→現状維持を好む、変化を嫌う"""

    bandwagon: float = 0.5
    """同調性: 高い→他者がやっていることを真似する"""

    overconfidence: float = 0.5
    """過信度: 高い→リスクを過小評価、自己能力を過大評価"""

    sunk_cost_bias: float = 0.5
    """サンクコストバイアス: 高い→過去に投資した方向を捨てられない"""

    info_sensitivity: float = 0.5
    """情報感度: 低い→市場情報を見落とす/誤解する"""

    noise: float = 0.1
    """ノイズ: 一定確率でLLM判断後にランダム行動に差し替える"""

    description: str = ""
    """性格の自由記述（プロンプト注入用）"""


class AgentProfile(BaseModel):
    """Static profile of an agent (does not change during simulation)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    agent_type: str
    stakeholder_type: StakeholderType
    description: str = ""


class AgentState(BaseModel):
    """Mutable state of an agent that changes each round."""
    capabilities: dict[MarketDimension, float] = Field(default_factory=dict)  # dimension -> influence 0-1
    revenue: float = 0.0        # 売上 (万円/月)
    cost: float = 0.0           # コスト (万円/月)
    headcount: int = 0          # 人数
    satisfaction: float = 0.5   # 満足度 0-1
    reputation: float = 0.5    # 市場での評判 0-1
    active_contracts: int = 0
    risk_tolerance: float = 0.5  # リスク許容度 0-1


class AgentAction(BaseModel):
    """An action taken by an agent in a round."""
    agent_id: str
    action_type: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    impact: dict[str, float] = Field(default_factory=dict)
    self_impact: dict[str, float] = Field(default_factory=dict)
    reacting_to: str = ""  # 誰の行動に対する反応か（エージェント名）


# デフォルトの性格（パラメータ指定がない場合に使用）
DEFAULT_PERSONALITY = AgentPersonality()


class BaseAgent(ABC):
    """Base class for all simulation agents.

    Each agent observes the ServiceMarketState, decides actions using the LLM,
    and updates its own state accordingly.
    Agents have personalities that bias their decisions and introduce noise.
    """

    def __init__(
        self,
        profile: AgentProfile,
        state: AgentState,
        llm: LLMRouter,
        personality: AgentPersonality | None = None,
    ):
        self.profile = profile
        self.state = state
        self.llm = llm
        self.personality = personality or DEFAULT_PERSONALITY
        self._action_history: list[AgentAction] = []
        self._scenario_summary: str = ""

    def set_scenario_context(self, summary: str) -> None:
        """シナリオの要約テキストを設定する（エンジンから呼ばれる）."""
        self._scenario_summary = summary

    @property
    def id(self) -> str:
        return self.profile.id

    @property
    def name(self) -> str:
        return self.profile.name

    @abstractmethod
    def available_actions(self) -> list[str]:
        """Return list of action types this agent can take."""
        ...

    async def decide_actions(
        self, market: ServiceMarketState, rag_context: str = "",
        total_rounds: int = 0,
    ) -> list[AgentAction]:
        """Use LLM to decide which actions to take this round.

        1. 性格バイアス付きプロンプトでLLMに判断させる
        2. 低確率でノイズ注入（ランダム行動に差し替え）
        3. 失敗時はフォールバック
        """
        try:
            prompt = self._build_decision_prompt(market, rag_context=rag_context, total_rounds=total_rounds)
            system_prompt = self._build_system_prompt()

            response = await self.llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=prompt,
                system_prompt=system_prompt,
            )

            actions = self._parse_actions(response)
            if actions:
                # ノイズ注入: 性格のnoise確率でランダム行動に差し替え
                if random.random() < self.personality.noise:
                    actions = self._inject_noise(actions)
                    logger.info("Agent %s: ノイズ注入（非合理的判断）", self.name)
                return actions
        except Exception:
            logger.warning("Agent %s: LLM呼び出し失敗、フォールバック使用", self.name)

        # フォールバック: 最初の利用可能アクション
        fallback_type = self.available_actions()[0] if self.available_actions() else None
        if fallback_type:
            return [AgentAction(
                agent_id=self.id,
                action_type=fallback_type,
                description="フォールバック（LLM応答なし）",
            )]
        return []

    def _inject_noise(self, actions: list[AgentAction]) -> list[AgentAction]:
        """行動をランダムに1つ差し替える（非合理的判断のシミュレーション）."""
        available = self.available_actions()
        random_action = random.choice(available)
        return [AgentAction(
            agent_id=self.id,
            action_type=random_action,
            description="直感的判断（合理的根拠なし）",
        )]

    async def apply_actions(
        self, actions: list[AgentAction], market: ServiceMarketState
    ) -> None:
        """Apply decided actions to update agent state."""
        for action in actions:
            self._execute_action(action, market)
            self._action_history.append(action)

    def _execute_action(self, action: AgentAction, market: ServiceMarketState) -> None:
        """LLMが決めたself_impactに基づいてエージェント状態を更新する.

        固定値は使用しない。LLMが行動選択時にself_impactも返すため、
        それをそのまま適用する。
        """
        si = action.self_impact
        if si:
            self.state.cost += si.get("cost_delta", 0.0)
            self.state.revenue += si.get("revenue_delta", 0.0)
            self.state.reputation += si.get("reputation_delta", 0.0)
            self.state.satisfaction += si.get("satisfaction_delta", 0.0)
            self.state.headcount += int(si.get("headcount_delta", 0))
            self.state.active_contracts += int(si.get("contracts_delta", 0))
        self._clamp_state()

    def _clamp_state(self) -> None:
        """reputation と satisfaction を [0, 1] の範囲に制限する。"""
        self.state.reputation = max(0.0, min(1.0, self.state.reputation))
        self.state.satisfaction = max(0.0, min(1.0, self.state.satisfaction))

    def _improve_capability(self, raw_dimension: str | None, delta: float) -> bool:
        """ディメンション影響力を delta 分だけ変更する。成功時 True を返す。"""
        dim = _parse_dimension(raw_dimension)
        if dim is None:
            return False
        current = self.state.capabilities.get(dim, 0.0)
        self.state.capabilities[dim] = max(0.0, min(1.0, current + delta))
        return True

    def _build_system_prompt(self) -> str:
        personality_text = self._build_personality_prompt()
        scenario_section = ""
        if self._scenario_summary:
            scenario_section = f"\n【シミュレーションシナリオ】\n{self._scenario_summary}\n"

        return (
            f"あなたはサービスビジネスインパクトシミュレーションにおける{self.profile.agent_type}のエージェントです。\n"
            f"名前: {self.profile.name}\n"
            f"ステークホルダー種別: {self.profile.stakeholder_type.value}\n"
            f"説明: {self.profile.description}\n"
            f"{scenario_section}\n"
            f"【あなたの性格・判断傾向】\n{personality_text}\n\n"
            f"取りうるアクション: {', '.join(self.available_actions())}\n\n"
            "Choose 1-2 actions. If reacting to another agent, set reacting_to to their name.\n"
            "Respond with EXACTLY this JSON format:\n"
            '{"actions": [{"action_type": "' + (self.available_actions()[0] if self.available_actions() else "wait") + '", '
            '"description": "reason for this action", '
            '"reacting_to": "", '
            '"parameters": {}, '
            '"self_impact": {"cost_delta": 10, "revenue_delta": 5, "reputation_delta": 0.02, '
            '"satisfaction_delta": 0.01, "headcount_delta": 0, "contracts_delta": 0}}]}'
        )

    def _build_personality_prompt(self) -> str:
        """性格パラメータから自然言語のプロンプトテキストを生成する."""
        p = self.personality
        lines: list[str] = []

        # 自由記述があればまず追加
        if p.description:
            lines.append(p.description)

        # 保守性
        if p.conservatism >= 0.7:
            lines.append("あなたは保守的で、新しいサービスや変化を恐れます。実績のある方法を強く好みます。")
        elif p.conservatism <= 0.3:
            lines.append("あなたは革新的で、新しいサービスやアプローチに積極的に挑戦します。")

        # 同調性
        if p.bandwagon >= 0.7:
            lines.append("他社や業界のトレンドに敏感で、みんながやっていることを真似する傾向があります。")
        elif p.bandwagon <= 0.3:
            lines.append("独自路線を好み、他社の動向に流されず独立した判断をします。")

        # 過信度
        if p.overconfidence >= 0.7:
            lines.append("自社の能力を過大評価しがちで、リスクを過小に見積もります。大胆な行動を好みます。")
        elif p.overconfidence <= 0.3:
            lines.append("自社の能力を客観的に見る傾向があり、慎重にリスクを評価します。")

        # サンクコスト
        if p.sunk_cost_bias >= 0.7:
            lines.append("過去に投資した事業への愛着が非常に強く、たとえ市場が変わっても切り替えが難しいです。")
        elif p.sunk_cost_bias <= 0.3:
            lines.append("過去の投資にこだわらず、状況に応じて柔軟に方向転換できます。")

        # 情報感度
        if p.info_sensitivity <= 0.3:
            lines.append("市場情報の収集・分析が苦手で、重要なトレンドを見落としがちです。")
        elif p.info_sensitivity >= 0.7:
            lines.append("市場情報に敏感で、データに基づいた判断を好みます。")

        return "\n".join(lines) if lines else "バランスの取れた判断をします。"

    def _build_decision_prompt(
        self, market: ServiceMarketState, rag_context: str = "",
        total_rounds: int = 0,
    ) -> str:
        top_dims = sorted(
            market.dimensions.items(), key=lambda x: x[1], reverse=True
        )[:3]
        dim_str = ", ".join(f"{d.value}: {v:.2f}" for d, v in top_dims)

        # 経過時間の文脈（1ラウンド = 1ヶ月）
        round_num = market.round_number
        remaining = total_rounds - round_num if total_rounds > 0 else 0
        time_context = f"（シミュレーション開始から{round_num}ヶ月目"
        if total_rounds > 0:
            time_context += f" / 全{total_rounds}ヶ月、残り{remaining}ヶ月"
        time_context += "）"

        prompt = (
            f"【ラウンド {round_num}】{time_context}\n"
            f"対象サービス: {market.service_name}\n"
            f"自社状況: 売上{self.state.revenue}万円, コスト{self.state.cost}万円, "
            f"人員{self.state.headcount}名, 契約{self.state.active_contracts}件\n"
            f"満足度: {self.state.satisfaction:.2f}, 評判: {self.state.reputation:.2f}\n"
            f"影響力: {dict(self.state.capabilities)}\n\n"
            f"市場状況:\n"
            f"  注目ディメンション: {dim_str}\n"
            f"  経済センチメント: {market.economic_sentiment:.2f}\n"
            f"  技術ハイプ: {market.tech_hype_level:.2f}\n"
            f"  規制圧力: {market.regulatory_pressure:.2f}\n"
            f"  AI破壊度: {market.ai_disruption_level:.2f}\n"
        )

        if rag_context:
            prompt += f"\n{rag_context}"

        prompt += (
            "\n\n他のステークホルダーの行動を踏まえてアクションを選んでください。"
            "特定のエージェントの行動に反応する場合は reacting_to にそのエージェント名を入れてください。"
        )
        return prompt

    def _parse_actions(self, response: dict[str, Any]) -> list[AgentAction]:
        """Parse LLM response into AgentAction list."""
        actions = []
        raw_actions = response.get("actions", [])
        valid_actions = set(self.available_actions())

        for raw in raw_actions[:2]:  # max 2 actions per round
            action_type = raw.get("action_type", "")
            if action_type not in valid_actions:
                continue
            actions.append(
                AgentAction(
                    agent_id=self.id,
                    action_type=action_type,
                    description=raw.get("description", ""),
                    parameters=raw.get("parameters", {}),
                    self_impact=raw.get("self_impact", {}),
                    reacting_to=str(raw.get("reacting_to", "")),
                )
            )
        return actions

    def to_summary(self) -> dict[str, Any]:
        """Return a summary dict for reports."""
        # Collect unique action types from action history
        action_types = sorted({a.action_type for a in self._action_history})

        return {
            "id": self.id,
            "name": self.name,
            "type": self.profile.agent_type,
            "stakeholder_type": self.profile.stakeholder_type.value,
            "description": self.profile.description,
            "headcount": self.state.headcount,
            "revenue": self.state.revenue,
            "satisfaction": self.state.satisfaction,
            "reputation": self.state.reputation,
            "action_types": action_types,
            "personality": {
                "conservatism": self.personality.conservatism,
                "bandwagon": self.personality.bandwagon,
                "overconfidence": self.personality.overconfidence,
                "sunk_cost_bias": self.personality.sunk_cost_bias,
                "info_sensitivity": self.personality.info_sensitivity,
                "noise": self.personality.noise,
                "description": self.personality.description,
            },
        }
