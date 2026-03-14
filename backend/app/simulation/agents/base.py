"""Base agent class for the IT labor market simulation."""

from __future__ import annotations

import random
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field

from app.core.llm.router import LLMRouter, TaskType
from app.simulation.agents.utils import _parse_skill
from app.simulation.models import Industry, MarketState, SkillCategory


class AgentPersonality(BaseModel):
    """エージェントの性格・認知バイアス.

    各パラメータは 0.0〜1.0 の範囲で設定する。
    """

    conservatism: float = 0.5
    """保守性: 高い→現状維持を好む、新技術や変化を嫌う"""

    bandwagon: float = 0.5
    """同調性: 高い→他社がやっていることを真似する"""

    overconfidence: float = 0.5
    """過信度: 高い→リスクを過小評価、自社能力を過大評価"""

    sunk_cost_bias: float = 0.5
    """サンクコストバイアス: 高い→過去に投資した領域を捨てられない"""

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
    industry: Industry
    description: str = ""


class AgentState(BaseModel):
    """Mutable state of an agent that changes each round."""
    skills: dict[SkillCategory, float] = Field(default_factory=dict)  # skill -> proficiency 0-1
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


# デフォルトの性格（パラメータ指定がない場合に使用）
DEFAULT_PERSONALITY = AgentPersonality()


class BaseAgent(ABC):
    """Base class for all simulation agents.

    Each agent observes the MarketState, decides actions using the LLM,
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
        self, market: MarketState, rag_context: str = ""
    ) -> list[AgentAction]:
        """Use LLM to decide which actions to take this round.

        1. 性格バイアス付きプロンプトでLLMに判断させる
        2. 低確率でノイズ注入（ランダム行動に差し替え）
        3. 失敗時はフォールバック

        Args:
            market: 現在の市場状態
            rag_context: 知識グラフからの参考情報テキスト（省略可）
        """
        try:
            prompt = self._build_decision_prompt(market, rag_context=rag_context)
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
        self, actions: list[AgentAction], market: MarketState
    ) -> None:
        """Apply decided actions to update agent state."""
        for action in actions:
            self._execute_action(action, market)
            self._action_history.append(action)

    @abstractmethod
    def _execute_action(self, action: AgentAction, market: MarketState) -> None:
        """Execute a single action and update internal state."""
        ...

    def _clamp_state(self) -> None:
        """reputation と satisfaction を [0, 1] の範囲に制限する。"""
        self.state.reputation = max(0.0, min(1.0, self.state.reputation))
        self.state.satisfaction = max(0.0, min(1.0, self.state.satisfaction))

    def _improve_skill(self, raw_skill: str | None, delta: float) -> bool:
        """スキル習熟度を delta 分だけ変更する。成功時 True を返す。"""
        sc = _parse_skill(raw_skill)
        if sc is None:
            return False
        current = self.state.skills.get(sc, 0.0)
        self.state.skills[sc] = max(0.0, min(1.0, current + delta))
        return True

    def _build_system_prompt(self) -> str:
        personality_text = self._build_personality_prompt()
        return (
            f"あなたは日本のIT業界における{self.profile.agent_type}のシミュレーションエージェントです。\n"
            f"名前: {self.profile.name}\n"
            f"業界: {self.profile.industry.value}\n"
            f"説明: {self.profile.description}\n\n"
            f"【あなたの性格・判断傾向】\n{personality_text}\n\n"
            f"取りうるアクション: {', '.join(self.available_actions())}\n\n"
            "上記の性格に基づいて市場状況を判断し、アクションをJSON形式で回答してください。\n"
            "あなたは完全に合理的ではありません。上記の性格傾向に従って判断してください。\n"
            '回答形式: {"actions": [{"action_type": "...", "description": "理由を含む説明", "parameters": {}}]}'
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
            lines.append("あなたは保守的で、新しい技術や変化を恐れます。実績のある方法を強く好みます。")
        elif p.conservatism <= 0.3:
            lines.append("あなたは革新的で、新しい技術やアプローチに積極的に挑戦します。")

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
            lines.append("過去に投資した技術や事業への愛着が非常に強く、たとえ市場が変わっても切り替えが難しいです。")
        elif p.sunk_cost_bias <= 0.3:
            lines.append("過去の投資にこだわらず、状況に応じて柔軟に方向転換できます。")

        # 情報感度
        if p.info_sensitivity <= 0.3:
            lines.append("市場情報の収集・分析が苦手で、重要なトレンドを見落としがちです。")
        elif p.info_sensitivity >= 0.7:
            lines.append("市場情報に敏感で、データに基づいた判断を好みます。")

        return "\n".join(lines) if lines else "バランスの取れた判断をします。"

    def _build_decision_prompt(
        self, market: MarketState, rag_context: str = ""
    ) -> str:
        top_demand = sorted(
            market.skill_demand.items(), key=lambda x: x[1], reverse=True
        )[:3]
        demand_str = ", ".join(f"{s.value}: {v:.2f}" for s, v in top_demand)

        prompt = (
            f"【ラウンド {market.round_number}】\n"
            f"自社状況: 売上{self.state.revenue}万円, コスト{self.state.cost}万円, "
            f"人員{self.state.headcount}名, 契約{self.state.active_contracts}件\n"
            f"満足度: {self.state.satisfaction:.2f}, 評判: {self.state.reputation:.2f}\n"
            f"保有スキル: {dict(self.state.skills)}\n\n"
            f"市場状況:\n"
            f"  需要上位: {demand_str}\n"
            f"  失業率: {market.unemployment_rate:.1%}\n"
            f"  AI自動化率: {market.ai_automation_rate:.1%}\n"
            f"  リモートワーク率: {market.remote_work_rate:.1%}\n"
            f"  オフショア率: {market.overseas_outsource_rate:.1%}\n"
        )

        if rag_context:
            prompt += rag_context

        prompt += "\n\n最大2つのアクションを選んでください。"
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
                )
            )
        return actions

    def to_summary(self) -> dict[str, Any]:
        """Return a summary dict for reports."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.profile.agent_type,
            "industry": self.profile.industry.value,
            "description": self.profile.description,
            "headcount": self.state.headcount,
            "revenue": self.state.revenue,
            "satisfaction": self.state.satisfaction,
            "reputation": self.state.reputation,
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
