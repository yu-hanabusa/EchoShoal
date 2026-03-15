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
        """組織名リストからエージェントを一括生成する."""
        if not org_names:
            return []

        names_text = ", ".join(org_names[:30])
        prompt = (
            f"サービス: {scenario.service_name or '不明'}\n"
            f"概要: {scenario.description[:300]}\n"
            f"組織一覧: {names_text}\n\n"
            "各組織の役割を判定しJSON返却:\n"
            '{"agents":[{"name":"組織名","stakeholder_type":"enterprise","description":"日本語で役割説明"}]}\n'
            "stakeholder_type: enterprise/end_user/government/investor/platformer/community/freelancer/indie_developer"
        )

        try:
            response = await self.llm.generate_json(
                task_type=TaskType.PERSONA_GENERATION,
                prompt=prompt,
                system_prompt="JSON形式で返答。descriptionは日本語で。",
            )
            return self._parse_agents(response)
        except Exception:
            logger.warning("エンティティ→エージェント変換失敗、直接生成にフォールバック")
            # LLM失敗時: 組織名から直接エージェントを作る
            return self._entities_to_agents_fallback(org_names)

    def _entities_to_agents_fallback(self, org_names: list[str]) -> list[BaseAgent]:
        """LLM不要のフォールバック: 組織名から直接エージェントを生成."""
        agents: list[BaseAgent] = []
        for name in org_names[:30]:
            agent = self._create_agent({
                "name": name,
                "stakeholder_type": "enterprise",
                "description": f"市場参加者: {name}",
            })
            if agent:
                agents.append(agent)
        return agents

    async def _generate_complement_agents(
        self,
        scenario: ScenarioInput,
        enriched: EnrichedScenario,
        existing_names: set[str],
    ) -> list[BaseAgent]:
        """既存エージェントに不足しているステークホルダーを補完する."""
        existing_list = ", ".join(existing_names) if existing_names else "none"

        prompt = (
            f"サービス: {scenario.service_name or '不明'}\n"
            f"概要: {scenario.description[:300]}\n"
            f"既存エージェント: {existing_list}\n\n"
            "不足しているエージェントを追加:\n"
            "- エンドユーザー（例: '既存Slackユーザー', '中小企業の潜在ユーザー'）\n"
            "- 具体的な競合（Slack, Microsoft Teams等の実名）\n"
            "- 行政、投資家、コミュニティ\n\n"
            '{"agents":[{"name":"名前","stakeholder_type":"enterprise","description":"日本語で役割説明"}]}\n'
            "stakeholder_type: enterprise/end_user/government/investor/platformer/community"
        )

        try:
            response = await self.llm.generate_json(
                task_type=TaskType.PERSONA_GENERATION,
                prompt=prompt,
                system_prompt="JSON形式で返答。descriptionは日本語で。",
            )
            agents = self._parse_agents(response)
            return [a for a in agents if a.name not in existing_names]
        except Exception:
            logger.warning("補完エージェント生成失敗、シナリオベースフォールバック")
            return self._complement_fallback(scenario, existing_names)

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


    def _complement_fallback(
        self,
        scenario: ScenarioInput,
        existing_names: set[str],
    ) -> list[BaseAgent]:
        """LLM不要のフォールバック: シナリオテキストから競合名等を抽出してエージェント化."""
        import re

        desc = scenario.description
        agents: list[BaseAgent] = []

        # シナリオ内の既知の企業名/サービス名を検出
        known_competitors = [
            ("Slack", "platformer", "2600以上の連携機能を持つビジネスチャットの先駆者"),
            ("Microsoft Teams", "platformer", "Microsoft 365統合で圧倒的シェアを持つ企業向けチャット"),
            ("LINE WORKS", "enterprise", "46万社導入の日本市場に強いビジネスチャット"),
            ("Chatwork", "enterprise", "中小企業に人気の国産ビジネスチャット"),
            ("Google Chat", "platformer", "Google Workspace連携のチャットサービス"),
            ("Discord", "community", "ゲーマー発のコミュニケーションツール、ビジネス展開中"),
        ]

        for name, stype, description in known_competitors:
            if name.lower() in desc.lower() and name not in existing_names:
                agent = self._create_agent({
                    "name": name,
                    "stakeholder_type": stype,
                    "description": description,
                })
                if agent:
                    agents.append(agent)

        # ユーザー層を必ず追加
        user_segments = [
            ("既存チャットツールユーザー", "競合サービスの既存利用者。乗り換えコストと比較検討を行う"),
            ("セキュリティ重視企業ユーザー", "セキュリティ・コンプライアンスを最優先とする企業のIT担当者"),
            ("中小企業の潜在ユーザー", "まだビジネスチャットを導入していない中小企業の経営者・管理者"),
        ]
        for name, description in user_segments:
            if name not in existing_names:
                agent = self._create_agent({
                    "name": name,
                    "stakeholder_type": "end_user",
                    "description": description,
                })
                if agent:
                    agents.append(agent)

        # 行政・投資家が不足していれば追加
        type_names = {a.profile.stakeholder_type for a in agents}
        all_existing_types = type_names | {
            _STAKEHOLDER_MAP.get(n, StakeholderType.ENTERPRISE)
            for n in existing_names
        }

        if StakeholderType.GOVERNMENT not in all_existing_types:
            agent = self._create_agent({
                "name": "デジタル庁",
                "stakeholder_type": "government",
                "description": "デジタル社会推進を担う政府機関。IT導入促進と規制のバランスを取る",
            })
            if agent:
                agents.append(agent)

        if StakeholderType.INVESTOR not in all_existing_types:
            agent = self._create_agent({
                "name": "国内SaaS投資ファンド",
                "stakeholder_type": "investor",
                "description": "日本のSaaS市場に注力するVCファンド",
            })
            if agent:
                agents.append(agent)

        logger.info("シナリオベースフォールバック: %d体生成", len(agents))
        return agents


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    """値を範囲内にクランプする."""
    try:
        return max(low, min(high, float(value)))
    except (ValueError, TypeError):
        return (low + high) / 2
