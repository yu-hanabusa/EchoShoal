"""エージェント動的生成: 文書エンティティ → エージェント変換.

MiroFish方式: 文書から抽出したエンティティ（企業名、組織名等）を
個別のエージェントに変換する。文書を投入するほどエージェントが増え、
グラフが自然に広がる。
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
from app.simulation.agents.end_user_agent import EndUserAgent
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
    "enterprise": EnterpriseAgent,
    "freelancer": FreelancerAgent,
    "indie_developer": IndieDevAgent,
    "government": GovernmentAgent,
    "investor": InvestorAgent,
    "platformer": PlatformerAgent,
    "community": CommunityAgent,
    "end_user": EndUserAgent,
}

_STAKEHOLDER_MAP: dict[str, StakeholderType] = {
    "enterprise": StakeholderType.ENTERPRISE,
    "freelancer": StakeholderType.FREELANCER,
    "indie_developer": StakeholderType.INDIE_DEVELOPER,
    "government": StakeholderType.GOVERNMENT,
    "investor": StakeholderType.INVESTOR,
    "platformer": StakeholderType.PLATFORMER,
    "community": StakeholderType.COMMUNITY,
    "end_user": StakeholderType.END_USER,
}


class AgentGenerator:
    """文書エンティティとシナリオからエージェントを動的に生成する.

    MiroFish方式: エンティティごとにエージェント化。
    """

    def __init__(self, llm: LLMRouter):
        self.llm = llm

    async def generate(
        self,
        scenario: ScenarioInput,
        enriched: EnrichedScenario,
        document_entities: dict[str, list[str]] | None = None,
    ) -> list[BaseAgent]:
        """エンティティからエージェントを生成する.

        1. 文書エンティティの企業・組織をそれぞれエージェント化
        2. シナリオからユーザー層のアーキタイプを生成
        3. 不足しているステークホルダーをLLMが補完
        """
        agents: list[BaseAgent] = []
        entities = document_entities or {}
        orgs = entities.get("organizations", [])

        # Step 1: 文書から抽出された組織をエージェント化
        if orgs:
            logger.info("文書エンティティから%d組織をエージェント化", len(orgs))
            entity_agents = await self._entities_to_agents(orgs, scenario)
            agents.extend(entity_agents)

        # Step 2: シナリオからユーザー層・補完エージェントを生成
        existing_names = {a.name for a in agents}
        complement_agents = await self._generate_complement_agents(
            scenario, enriched, existing_names,
        )
        agents.extend(complement_agents)

        if agents:
            logger.info("エージェント生成完了: %d体（エンティティ%d + 補完%d）",
                        len(agents), len([a for a in agents if a in entity_agents]) if orgs else 0,
                        len(complement_agents))
            return agents

        # フォールバック
        from app.simulation.factory import create_default_agents
        logger.info("エージェント生成失敗、デフォルトを使用")
        return create_default_agents(self.llm)

    async def _entities_to_agents(
        self,
        org_names: list[str],
        scenario: ScenarioInput,
    ) -> list[BaseAgent]:
        """組織名リストからエージェントを一括生成する.

        LLMに各組織の役割・性格を推定させる。
        """
        if not org_names:
            return []

        # LLMに一括で各組織の情報を推定させる
        names_text = "\n".join(f"- {name}" for name in org_names[:30])
        prompt = (
            f"Service being evaluated: {scenario.service_name or 'unknown'}\n"
            f"Scenario: {scenario.description[:400]}\n\n"
            f"The following organizations/entities were found in reference documents:\n{names_text}\n\n"
            "For EACH entity, determine its role in relation to the service and create an agent profile.\n"
            "Return EXACTLY this JSON format:\n"
            '{"agents": [{"name": "Entity Name", '
            '"stakeholder_type": "enterprise|freelancer|indie_developer|government|investor|platformer|community|end_user", '
            '"mode": "individual", "represents_count": 1, '
            '"description": "Role in this market", '
            '"headcount": 100, "revenue": 500, "cost": 400, '
            '"personality": {"conservatism": 0.5, "bandwagon": 0.5, "overconfidence": 0.5, '
            '"sunk_cost_bias": 0.5, "info_sensitivity": 0.5, "noise": 0.1, '
            '"description": "Personality traits"}}]}'
        )

        try:
            response = await self.llm.generate_json(
                task_type=TaskType.PERSONA_GENERATION,
                prompt=prompt,
                system_prompt=(
                    "You are a market analyst. For each organization found in documents, "
                    "determine its stakeholder type and personality in relation to the service being evaluated. "
                    "All entities should be mode: individual. Respond with JSON only."
                ),
            )
            return self._parse_agents(response)
        except Exception:
            logger.warning("エンティティ→エージェント変換失敗")
            return []

    async def _generate_complement_agents(
        self,
        scenario: ScenarioInput,
        enriched: EnrichedScenario,
        existing_names: set[str],
    ) -> list[BaseAgent]:
        """既存エージェントに不足しているステークホルダーを補完する.

        - 必ずユーザー層（end_user archetype）を含める
        - 必要な競合が不足していれば追加
        - 行政・投資家等が不足していれば追加
        """
        existing_list = ", ".join(existing_names) if existing_names else "none"

        prompt = (
            f"Service: {scenario.service_name or 'unknown'}\n"
            f"Scenario: {scenario.description[:400]}\n\n"
            f"Already generated agents: {existing_list}\n\n"
            "Generate ADDITIONAL agents that are MISSING from the above list.\n"
            "You MUST include:\n"
            "1. End user segments as archetypes (e.g. 'Existing Slack users (×5000)', "
            "'Potential users unaware of service (×10000)', 'Users considering switching (×2000)')\n"
            "2. Any major competitors NOT already in the list\n"
            "3. Relevant government agencies, investors, communities if missing\n\n"
            "Do NOT duplicate agents that already exist.\n"
            "Use mode: 'archetype' with represents_count for user groups.\n"
            "Use mode: 'individual' for specific named entities.\n\n"
            "Return EXACTLY this JSON format:\n"
            '{"agents": [{"name": "Agent Name", '
            '"stakeholder_type": "enterprise|end_user|government|investor|platformer|community", '
            '"mode": "individual|archetype", "represents_count": 1, '
            '"description": "Role description", '
            '"headcount": 100, "revenue": 500, "cost": 400, '
            '"personality": {"conservatism": 0.5, "bandwagon": 0.5, "overconfidence": 0.5, '
            '"sunk_cost_bias": 0.5, "info_sensitivity": 0.5, "noise": 0.1, '
            '"description": "Personality"}}]}'
        )

        try:
            response = await self.llm.generate_json(
                task_type=TaskType.PERSONA_GENERATION,
                prompt=prompt,
                system_prompt=(
                    "You are a market simulation expert. Generate MISSING stakeholder agents "
                    "to complete the market structure. Focus on end_user segments (archetypes) "
                    "that represent different user groups. Respond with JSON only."
                ),
            )
            agents = self._parse_agents(response)
            # 重複排除
            return [a for a in agents if a.name not in existing_names]
        except Exception:
            logger.warning("補完エージェント生成失敗")
            return []

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
        stakeholder_str = raw.get("stakeholder_type", "enterprise")
        stakeholder_type = _STAKEHOLDER_MAP.get(stakeholder_str, StakeholderType.ENTERPRISE)
        agent_class = _AGENT_CLASS_MAP.get(stakeholder_str, EnterpriseAgent)

        mode = raw.get("mode", "individual")
        if mode not in ("individual", "archetype"):
            mode = "individual"
        represents_count = max(1, int(raw.get("represents_count", 1)))

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

        profile = AgentProfile(
            name=raw.get("name", "Unknown"),
            agent_type=stakeholder_str,
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
