"""エージェント動的生成: シード文書とシナリオからエージェントを自動生成する.

文書から抽出したエンティティとシナリオテキストをLLMに渡し、
シミュレーションに登場するエージェントの構成を動的に決定する。
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.llm.router import LLMRouter, TaskType
from app.simulation.agents.base import (
    AgentPersonality,
    AgentProfile,
    AgentState,
    BaseAgent,
)
from app.simulation.agents.community_agent import CommunityAgent
from app.simulation.agents.enterprise_agent import EnterpriseAgent
from app.simulation.agents.freelancer_agent import FreelancerAgent
from app.simulation.agents.government_agent import GovernmentAgent
from app.simulation.agents.indie_dev_agent import IndieDevAgent
from app.simulation.agents.investor_agent import InvestorAgent
from app.simulation.agents.platformer_agent import PlatformerAgent
from app.simulation.models import StakeholderType, ScenarioInput, MarketDimension
from app.simulation.scenario_analyzer import EnrichedScenario

logger = logging.getLogger(__name__)

# agent_type → エージェントクラスのマッピング
_AGENT_CLASS_MAP: dict[str, type[BaseAgent]] = {
    "大手企業": EnterpriseAgent,
    "中堅企業": EnterpriseAgent,
    "スタートアップ": EnterpriseAgent,
    "企業": EnterpriseAgent,
    "フリーランス": FreelancerAgent,
    "個人開発者": IndieDevAgent,
    "行政": GovernmentAgent,
    "投資家/VC": InvestorAgent,
    "投資家": InvestorAgent,
    "VC": InvestorAgent,
    "プラットフォーマー": PlatformerAgent,
    "業界団体": CommunityAgent,
    "コミュニティ": CommunityAgent,
}

# stakeholder_type文字列 → StakeholderTypeの正規化
_STAKEHOLDER_MAP: dict[str, StakeholderType] = {
    "enterprise": StakeholderType.ENTERPRISE,
    "freelancer": StakeholderType.FREELANCER,
    "indie_developer": StakeholderType.INDIE_DEVELOPER,
    "government": StakeholderType.GOVERNMENT,
    "investor": StakeholderType.INVESTOR,
    "platformer": StakeholderType.PLATFORMER,
    "community": StakeholderType.COMMUNITY,
}


class AgentGenerator:
    """シード文書とシナリオからエージェントを動的に生成する."""

    def __init__(self, llm: LLMRouter):
        self.llm = llm

    async def generate(
        self,
        scenario: ScenarioInput,
        enriched: EnrichedScenario,
        document_entities: dict[str, list[str]] | None = None,
    ) -> list[BaseAgent]:
        """LLMにエンティティ情報を渡してエージェントを生成する."""
        try:
            prompt = self._build_prompt(scenario, enriched, document_entities)
            response = await self.llm.generate_json(
                task_type=TaskType.PERSONA_GENERATION,
                prompt=prompt,
                system_prompt=self._system_prompt(),
            )
            agents = self._parse_agents(response)
            if agents:
                logger.info("エージェント動的生成成功: %d体", len(agents))
                return agents
        except Exception:
            logger.warning("エージェント動的生成失敗、フォールバック使用")

        # フォールバック: factory.pyのデフォルトエージェント
        from app.simulation.factory import create_default_agents
        logger.info("デフォルトエージェント（8体）を使用")
        return create_default_agents(self.llm)

    def _system_prompt(self) -> str:
        return (
            "You are a service business expert. Generate stakeholder agents for a simulation.\n\n"
            "Each agent must have mode: 'individual' or 'archetype'.\n"
            "- individual: A specific named entity that directly impacts the service (e.g. 'Slack', 'Microsoft', 'Digital Agency')\n"
            "- archetype: A representative of a group that behaves similarly (e.g. 'Security-conscious mid-size enterprises')\n"
            "  For archetypes, set represents_count to the number of entities this agent represents.\n\n"
            "Generate as many agents as the market structure requires. Do NOT limit to a fixed number.\n"
            "stakeholder_type must be: enterprise, freelancer, indie_developer, government, investor, platformer, community\n"
            "Respond with JSON only."
        )

    def _build_prompt(
        self,
        scenario: ScenarioInput,
        enriched: EnrichedScenario,
        document_entities: dict[str, list[str]] | None,
    ) -> str:
        lines = [
            f"Service: {scenario.service_name or 'unknown'}",
            f"Scenario: {scenario.description[:600]}",
            "",
            "Generate agents that reflect the REAL market structure for this service.",
            "Use 'individual' mode for specific named players (competitors, key regulators, major platforms).",
            "Use 'archetype' mode for groups that behave similarly (e.g. 'early-adopter SMBs', 'conservative enterprises').",
            "There is no fixed limit on agent count. Generate what the market requires.",
        ]

        if scenario.target_market:
            lines.append(f"\n【ターゲット市場】\n{scenario.target_market}")

        if enriched.detected_dimensions:
            dims = ", ".join(d.value for d in enriched.detected_dimensions)
            lines.append(f"\n【検出されたマーケットディメンション】\n{dims}")

        if enriched.detected_stakeholders:
            stakeholders = ", ".join(s.value for s in enriched.detected_stakeholders)
            lines.append(f"\n【検出されたステークホルダー】\n{stakeholders}")

        if enriched.detected_policies:
            lines.append(f"\n【検出された政策】\n{', '.join(enriched.detected_policies)}")

        entities = document_entities or {}
        if entities.get("organizations"):
            lines.append(f"\n【参考資料に登場する企業・組織】\n{', '.join(entities['organizations'])}")
            lines.append("↑これらの企業名をエージェント名として使ってください。")

        if entities.get("technologies"):
            lines.append(f"\n【参考資料に登場する技術】\n{', '.join(entities['technologies'])}")

        lines.append("")
        lines.append(
            'Return EXACTLY this JSON format:\n'
            '{"agents": [{"name": "Slack", "agent_type": "enterprise", '
            '"stakeholder_type": "enterprise", "mode": "individual", "represents_count": 1, '
            '"description": "Leading competitor", "headcount": 2000, "revenue": 5000, "cost": 4000, '
            '"capabilities": {"competitive_pressure": 0.8}, '
            '"personality": {"conservatism": 0.3, "bandwagon": 0.2, "overconfidence": 0.5, '
            '"sunk_cost_bias": 0.3, "info_sensitivity": 0.8, "noise": 0.05, "description": "Market leader"}}, '
            '{"name": "Conservative mid-size enterprises", "agent_type": "enterprise", '
            '"stakeholder_type": "enterprise", "mode": "archetype", "represents_count": 20, '
            '"description": "Traditional companies slow to adopt new tools", "headcount": 200, '
            '"revenue": 500, "cost": 400, '
            '"capabilities": {"user_adoption": 0.3}, '
            '"personality": {"conservatism": 0.8, "bandwagon": 0.4, "overconfidence": 0.2, '
            '"sunk_cost_bias": 0.7, "info_sensitivity": 0.3, "noise": 0.1, "description": "Risk averse"}}]}'
        )

        return "\n".join(lines)

    def _parse_agents(self, response: dict[str, Any]) -> list[BaseAgent]:
        """LLMのJSON応答からエージェントインスタンスを生成する."""
        raw_agents = response.get("agents", [])
        if not raw_agents:
            return []

        agents: list[BaseAgent] = []
        for raw in raw_agents:
            try:
                agent = self._create_agent(raw)
                if agent:
                    agents.append(agent)
            except Exception:
                logger.warning("エージェント生成スキップ: %s", raw.get("name", "unknown"))

        return agents

    def _create_agent(self, raw: dict[str, Any]) -> BaseAgent | None:
        """1体のエージェントを生成する."""
        agent_type = raw.get("agent_type", "企業")
        agent_class = _AGENT_CLASS_MAP.get(agent_type)
        if not agent_class:
            logger.warning("未知のagent_type: %s、企業として扱う", agent_type)
            agent_class = EnterpriseAgent

        stakeholder_str = raw.get("stakeholder_type", "enterprise")
        stakeholder_type = _STAKEHOLDER_MAP.get(stakeholder_str, StakeholderType.ENTERPRISE)

        # capabilities
        raw_caps = raw.get("capabilities", {})
        capabilities: dict[MarketDimension, float] = {}
        for dim_key, influence in raw_caps.items():
            try:
                dim = MarketDimension(dim_key)
                capabilities[dim] = max(0.0, min(1.0, float(influence)))
            except (ValueError, TypeError):
                pass

        # ペルソナ
        raw_persona = raw.get("personality", {})
        personality = AgentPersonality(
            conservatism=_clamp(raw_persona.get("conservatism", 0.5)),
            bandwagon=_clamp(raw_persona.get("bandwagon", 0.5)),
            overconfidence=_clamp(raw_persona.get("overconfidence", 0.5)),
            sunk_cost_bias=_clamp(raw_persona.get("sunk_cost_bias", 0.5)),
            info_sensitivity=_clamp(raw_persona.get("info_sensitivity", 0.5)),
            noise=_clamp(raw_persona.get("noise", 0.1), 0.0, 0.3),
            description=raw_persona.get("description", ""),
        )

        mode = raw.get("mode", "individual")
        if mode not in ("individual", "archetype"):
            mode = "individual"
        represents_count = max(1, int(raw.get("represents_count", 1)))

        profile = AgentProfile(
            name=raw.get("name", "Unknown"),
            agent_type=agent_type,
            stakeholder_type=stakeholder_type,
            description=raw.get("description", ""),
            mode=mode,
            represents_count=represents_count,
        )

        state = AgentState(
            headcount=max(1, int(raw.get("headcount", 10))),
            revenue=max(0, float(raw.get("revenue", 100))),
            cost=max(0, float(raw.get("cost", 50))),
            capabilities=capabilities,
        )

        return agent_class(
            profile=profile,
            state=state,
            llm=self.llm,
            personality=personality,
        )


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    """値を範囲内にクランプする."""
    try:
        return max(low, min(high, float(value)))
    except (ValueError, TypeError):
        return (low + high) / 2
