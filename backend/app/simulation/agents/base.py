"""Base agent class for the IT labor market simulation."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.core.llm.router import LLMRouter, TaskType
from app.simulation.agents.utils import _parse_skill
from app.simulation.models import Industry, MarketState, SkillCategory


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


class BaseAgent(ABC):
    """Base class for all simulation agents.

    Each agent observes the MarketState, decides actions using the LLM,
    and updates its own state accordingly.
    """

    def __init__(self, profile: AgentProfile, state: AgentState, llm: LLMRouter):
        self.profile = profile
        self.state = state
        self.llm = llm
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

    async def decide_actions(self, market: MarketState) -> list[AgentAction]:
        """Use LLM to decide which actions to take this round."""
        prompt = self._build_decision_prompt(market)
        system_prompt = self._build_system_prompt()

        response = await self.llm.generate_json(
            task_type=TaskType.AGENT_DECISION,
            prompt=prompt,
            system_prompt=system_prompt,
        )

        actions = self._parse_actions(response)
        return actions

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
        """スキル習熟度を delta 分だけ上げる。成功時 True を返す。"""
        sc = _parse_skill(raw_skill)
        if sc is None:
            return False
        current = self.state.skills.get(sc, 0.0)
        self.state.skills[sc] = min(1.0, current + delta)
        return True

    def _build_system_prompt(self) -> str:
        return (
            f"あなたは日本のIT業界における{self.profile.agent_type}のシミュレーションエージェントです。\n"
            f"名前: {self.profile.name}\n"
            f"業界: {self.profile.industry.value}\n"
            f"説明: {self.profile.description}\n"
            f"取りうるアクション: {', '.join(self.available_actions())}\n\n"
            "市場状況を分析し、次のラウンドで取るべきアクションをJSON形式で回答してください。\n"
            '回答形式: {"actions": [{"action_type": "...", "description": "...", "parameters": {}}]}'
        )

    def _build_decision_prompt(self, market: MarketState) -> str:
        top_demand = sorted(
            market.skill_demand.items(), key=lambda x: x[1], reverse=True
        )[:3]
        demand_str = ", ".join(f"{s.value}: {v:.2f}" for s, v in top_demand)

        return (
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
            f"  オフショア率: {market.overseas_outsource_rate:.1%}\n\n"
            f"最大2つのアクションを選んでください。"
        )

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
            "headcount": self.state.headcount,
            "revenue": self.state.revenue,
            "satisfaction": self.state.satisfaction,
            "reputation": self.state.reputation,
        }
