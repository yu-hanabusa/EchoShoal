"""エージェント動的生成: 文書エンティティ → エージェント変換.

MiroFish方式: 文書から抽出したエンティティ（企業名、組織名等）を
個別のエージェントに変換する。文書を投入するほどエージェントが増え、
グラフが自然に広がる。
"""

from __future__ import annotations

import logging
import re
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


# ---------------------------------------------------------------------------
# Non-market-player filter: entities that should NOT become agents
# ---------------------------------------------------------------------------

# Exact-match blocklist (case-insensitive)
_BLOCKLIST_NAMES: set[str] = {
    # Research / analyst firms
    "mckinsey", "mckinsey global institute", "mckinsey & company",
    "idc", "international data corporation",
    "gartner", "gartner inc",
    "forrester", "forrester research",
    "radicati", "radicati group", "the radicati group",
    "evans data", "evans data corporation",
    "statista", "cb insights", "pitchbook",
    "deloitte", "pwc", "kpmg", "ey", "ernst & young",
    "accenture", "bain", "bain & company", "bcg",
    "boston consulting group", "roland berger",
    # Standards / regulations / certifications
    "hipaa", "gdpr", "fedramp", "coppa", "ferpa",
    "ismap", "soc2", "soc 2", "iso 27001", "iso27001",
    "pci dss", "ccpa", "pipeda", "appi",
    "nist", "iec", "iso",
    # Generic / meta entities that are not market players
    "united nations", "world economic forum",
    "ieee", "ietf", "w3c",
}

# Regex patterns for categories of non-player entities (case-insensitive)
_BLOCKLIST_PATTERNS: list[re.Pattern[str]] = [
    # Research / consulting / analyst firms
    re.compile(r"\b(research|analytics|institute|consulting)\b", re.IGNORECASE),
    re.compile(r"\bresearch\s+(group|firm|corp)", re.IGNORECASE),
    re.compile(r"\b(analyst|advisory)\s+(firm|group)\b", re.IGNORECASE),
    # Standards and regulation bodies
    re.compile(
        r"^(HIPAA|GDPR|FedRAMP|COPPA|FERPA|ISMAP|SOC\s*2|ISO\s*\d|PCI|CCPA|NIST|PIPEDA|APPI)\b",
        re.IGNORECASE,
    ),
    # Data/survey providers
    re.compile(r"\b(data\s+corp|survey|census)\b", re.IGNORECASE),
]


def _is_non_market_player(name: str) -> bool:
    """Return True if the entity should be filtered out (not a market player).

    Checks exact blocklist then pattern blocklist.
    """
    normalized = name.strip().lower()

    # Short / empty names are not useful
    if len(normalized) < 2:
        return True

    # Exact match
    if normalized in _BLOCKLIST_NAMES:
        return True

    # Pattern match
    for pattern in _BLOCKLIST_PATTERNS:
        if pattern.search(name):
            return True

    return False


def _filter_entities(org_names: list[str]) -> list[str]:
    """Filter out non-market-player entities from an organization list."""
    filtered = [name for name in org_names if not _is_non_market_player(name)]
    removed = len(org_names) - len(filtered)
    if removed:
        logger.info(
            "非市場プレイヤーを%d件除外（リサーチ会社・規格等）", removed,
        )
    return filtered


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

        0. 対象サービスを主人公エージェントとして生成（能動的に意思決定）
        1. 文書エンティティの企業・組織をそれぞれエージェント化
        2. シナリオからユーザー層のアーキタイプを生成
        3. 不足しているステークホルダーをLLMが補完
        """
        agents: list[BaseAgent] = []
        entities = document_entities or {}
        orgs = entities.get("organizations", [])

        # Step 0: 対象サービスを主人公エージェントとして生成
        if scenario.service_name:
            protagonist = await self._create_protagonist(scenario)
            if protagonist:
                agents.append(protagonist)

        # Step 1: 文書から抽出された組織をエージェント化
        if orgs:
            orgs = _filter_entities(orgs)
            # 対象サービスは既にStep 0で生成済みなので重複排除
            service_name = scenario.service_name.lower() if scenario.service_name else ""
            if service_name:
                orgs = [o for o in orgs if o.lower() != service_name]
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

        if not agents:
            # フォールバック
            from app.simulation.factory import create_default_agents
            logger.info("エージェント生成失敗、デフォルトを使用")
        return create_default_agents(self.llm)

    async def _create_protagonist(self, scenario: ScenarioInput) -> BaseAgent | None:
        """対象サービスを主人公エージェントとして生成する.

        主人公は市場の変化に応じて能動的に意思決定する:
        - 競合の動きに対する対抗策
        - ユーザーフィードバックへの対応
        - 価格改定、機能追加、マーケティング等
        """
        service = scenario.service_name
        if not service:
            return None

        prompt = (
            f"サービス「{service}」を運営する企業/チームのプロフィールを推定してください。\n"
            f"概要: {scenario.description[:300]}\n\n"
            '{"name":"サービス名","stakeholder_type":"enterprise",'
            '"description":"このサービスの立場・戦略・強みを日本語で",'
            '"headcount":推定従業員数,'
            '"revenue":推定月間売上(万円),'
            '"personality":{"conservatism":0.0-1.0,"bandwagon":0.0-1.0,'
            '"overconfidence":0.0-1.0,"sunk_cost_bias":0.0-1.0,'
            '"info_sensitivity":0.0-1.0,"noise":0.05-0.15,'
            '"description":"意思決定の特徴を日本語で"}}'
        )

        try:
            response = await self.llm.generate_json(
                task_type=TaskType.PERSONA_GENERATION,
                prompt=prompt,
                system_prompt="対象サービスの運営者のプロフィールをJSON形式で返答。",
            )
            response["name"] = service  # 名前はサービス名で固定
            response["stakeholder_type"] = "enterprise"
            agent = self._create_agent(response)
            if agent:
                logger.info("主人公エージェント生成: %s (headcount=%d)",
                            service, agent.state.headcount)
            return agent
        except Exception:
            logger.warning("主人公エージェント生成失敗、デフォルトで作成")
            return self._create_agent({
                "name": service,
                "stakeholder_type": "enterprise",
                "description": f"シミュレーション対象サービス「{service}」の運営チーム",
                "headcount": 50,
                "revenue": 100,
            })

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
            "各組織について以下を判定しJSON返却してください:\n"
            "- stakeholder_type: この市場における役割\n"
            "- description: 日本語で組織の立場と対象サービスへの態度を具体的に\n"
            "- headcount: 組織の従業員数（実際の規模に近い値）\n"
            "- revenue: 月間売上（万円）\n"
            "- personality: 組織の意思決定傾向\n\n"
            '{"agents":[{"name":"組織名","stakeholder_type":"enterprise",'
            '"description":"日本語で役割・態度・立場を説明",'
            '"headcount":5000,"revenue":10000,'
            '"personality":{"conservatism":0.7,"bandwagon":0.3,"overconfidence":0.5,'
            '"sunk_cost_bias":0.6,"info_sensitivity":0.5,"noise":0.1,'
            '"description":"大企業のため保守的で既存製品への愛着が強い"}}]}\n\n'
            "stakeholder_type: enterprise/end_user/government/investor/platformer/community\n"
            "conservatism: 高い=変化を恐れる/低い=新しいものに積極的\n"
            "bandwagon: 高い=トレンドに流される/低い=独自路線\n"
            "overconfidence: 高い=リスクを過小評価/低い=慎重\n"
            "sunk_cost_bias: 高い=過去の投資にこだわる/低い=柔軟に方向転換\n"
            "info_sensitivity: 高い=市場情報に敏感/低い=鈍感"
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

        service = scenario.service_name or "対象サービス"
        prompt = (
            f"サービス: {service}\n"
            f"概要: {scenario.description[:300]}\n"
            f"既存エージェント: {existing_list}\n\n"
            "不足しているエージェントを追加してください:\n"
            f"- エンドユーザー層（'{service}の潜在ユーザー層', '競合サービスの既存ユーザー層'等、"
            "集団を表す名前にする）\n"
            "- 具体的な競合（実名のサービス/企業名）\n"
            "- 行政、投資家、コミュニティ\n\n"
            f"注意: '{service}'自体はシミュレーション対象なのでエージェントにしないでください。\n\n"
            "各エージェントにheadcount（組織規模）とpersonality（意思決定傾向）を設定:\n"
            '{"agents":[{"name":"名前","stakeholder_type":"end_user",'
            '"description":"日本語で役割・態度・立場を具体的に説明",'
            '"headcount":5000,'
            '"personality":{"conservatism":0.5,"bandwagon":0.5,"overconfidence":0.5,'
            '"sunk_cost_bias":0.5,"info_sensitivity":0.5,"noise":0.1,'
            '"description":"このセグメントの特徴を日本語で"}}]}\n\n'
            "stakeholder_type: enterprise/end_user/government/investor/platformer/community\n"
            "headcount目安: エンドユーザー層=1000-10000, 大企業=5000-100000, "
            "スタートアップ=10-100, 行政=500, 投資家=30, コミュニティ=200"
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
                name = raw.get("name", "")
                if _is_non_market_player(name):
                    logger.info("非市場プレイヤーをスキップ: %s", name)
                    continue
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

        # ステークホルダー種別ごとのデフォルト値
        _defaults: dict[str, tuple[int, float, float]] = {
            # (headcount, revenue, cost)
            "platformer": (5000, 10000, 8000),
            "enterprise": (200, 500, 400),
            "government": (300, 0, 500),
            "investor": (30, 1000, 200),
            "community": (50, 10, 15),
            "freelancer": (1, 80, 10),
            "indie_developer": (1, 10, 5),
            "end_user": (1000, 0, 0),  # ユーザーセグメントの想定規模
        }
        defaults = _defaults.get(stakeholder_str, (10, 100, 50))

        state = AgentState(
            headcount=max(1, int(raw.get("headcount", defaults[0]))),
            revenue=max(0, float(raw.get("revenue", defaults[1]))),
            cost=max(0, float(raw.get("cost", defaults[2]))),
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

        # ユーザー層を必ず追加（サービス名に応じた名前にする）
        service = scenario.service_name or "対象サービス"
        user_segments = [
            (f"競合サービスの既存ユーザー層", "競合サービスの既存利用者。乗り換えコストと比較検討を行う"),
            (f"{service}のターゲットユーザー層", f"{service}が狙うセグメントの潜在ユーザー"),
            ("未導入の潜在ユーザー層", "まだこのカテゴリのツールを導入していない組織"),
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
