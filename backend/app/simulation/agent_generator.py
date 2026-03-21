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

    @staticmethod
    def _enforce_max_agents(agents: list[BaseAgent]) -> list[BaseAgent]:
        """エージェント数がoasis_max_agentsを超えないよう切り詰める."""
        from app.config import settings
        max_agents = settings.oasis_max_agents
        if len(agents) <= max_agents:
            return agents
        logger.warning(
            "エージェント数が上限を超過: %d体 → %d体に制限",
            len(agents), max_agents,
        )
        return agents[:max_agents]

    async def generate(
        self,
        scenario: ScenarioInput,
        enriched: EnrichedScenario,
        document_entities: dict[str, list[str]] | None = None,
        collected_data: Any | None = None,
        stakeholder_report: str = "",
    ) -> list[BaseAgent]:
        """エンティティからエージェントを生成する.

        0. 対象サービスを主人公エージェントとして生成（能動的に意思決定）
        1. 文書エンティティの企業・組織をそれぞれエージェント化
        2. シナリオからユーザー層のアーキタイプを生成
        3. 不足しているステークホルダーをLLMが補完

        collected_data: 市場調査で収集した構造化データ（FinanceData等）
        stakeholder_report: 市場調査のステークホルダーレポート（テキスト）
        """
        self._stakeholder_report = stakeholder_report
        agents: list[BaseAgent] = []
        entities = document_entities or {}
        orgs = entities.get("organizations", [])

        # 市場調査データから企業名→財務データのルックアップ構築
        self._finance_lookup: dict[str, dict[str, Any]] = {}
        if collected_data and hasattr(collected_data, "finance_data"):
            for fd in collected_data.finance_data:
                self._finance_lookup[fd.company_name.lower()] = {
                    "company_name": fd.company_name,
                    "ticker": fd.ticker,
                    "market_cap": fd.market_cap,
                    "revenue": fd.revenue,
                    "sector": fd.sector,
                }

        # Step 0: 対象サービスを主人公エージェントとして生成
        self._protagonist_aliases: set[str] = set()
        if scenario.service_name:
            protagonist = await self._create_protagonist(scenario)
            if protagonist:
                agents.append(protagonist)

        # Step 1: 文書から抽出された組織をエージェント化
        if orgs:
            orgs = _filter_entities(orgs)
            # 対象サービスおよびその運営企業は既にStep 0で生成済みなので重複排除
            orgs = [o for o in orgs if o.lower() not in self._protagonist_aliases]
        if orgs:
            logger.info("文書エンティティから%d組織をエージェント化", len(orgs))
            entity_agents = await self._entities_to_agents(orgs, scenario)
            agents.extend(entity_agents)

        # Step 2: シナリオからユーザー層・補完エージェントを生成
        existing_names = {a.name for a in agents}
        complement_agents = await self._generate_complement_agents(
            scenario, enriched, existing_names, agents,
        )
        agents.extend(complement_agents)

        if agents:
            logger.info("エージェント生成完了: %d体（エンティティ%d + 補完%d）",
                        len(agents), len([a for a in agents if a in entity_agents]) if orgs else 0,
                        len(complement_agents))
            return self._enforce_max_agents(agents)

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
            '"operator":"運営企業名（例: ChatGPT→OpenAI, Gmail→Google）",'
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
            # 運営企業名を記録（競合エージェント生成時に除外するため）
            operator = response.pop("operator", "")
            self._protagonist_aliases.add(service.lower())
            if operator:
                self._protagonist_aliases.add(operator.lower())
                logger.info("主人公の運営企業: %s（競合から除外）", operator)
            agent = self._create_agent(response)
            if agent:
                logger.info("主人公エージェント生成: %s (headcount=%d)",
                            service, agent.state.headcount)
            return agent
        except Exception:
            logger.warning("主人公エージェント生成失敗、デフォルトで作成")
            self._protagonist_aliases.add(service.lower())
            return self._create_agent({
                "name": service,
                "stakeholder_type": "enterprise",
                "description": f"シミュレーション対象サービス「{service}」の運営チーム",
                "headcount": 50,
                "revenue": 100,
            })

    def _build_org_info_text(self, org_names: list[str]) -> str:
        """組織名リストに財務データを付加したテキストを構築する."""
        lines = []
        for name in org_names[:30]:
            fd = self._finance_lookup.get(name.lower())
            if fd:
                parts = [name]
                if fd["market_cap"]:
                    cap_b = fd["market_cap"] / 1e9
                    parts.append(f"時価総額: ${cap_b:.1f}B")
                if fd["revenue"]:
                    rev_b = fd["revenue"] / 1e9
                    parts.append(f"年間売上: ${rev_b:.1f}B")
                if fd["sector"]:
                    parts.append(f"セクター: {fd['sector']}")
                lines.append(" / ".join(parts))
            else:
                lines.append(name)
        return "\n".join(f"- {line}" for line in lines)

    async def _entities_to_agents(
        self,
        org_names: list[str],
        scenario: ScenarioInput,
    ) -> list[BaseAgent]:
        """組織名リストからエージェントを一括生成する."""
        if not org_names:
            return []

        org_info_text = self._build_org_info_text(org_names)
        prompt = (
            f"サービス: {scenario.service_name or '不明'}\n"
            f"概要: {scenario.description[:300]}\n\n"
            f"組織一覧（財務データがある場合は付記）:\n{org_info_text}\n\n"
            "各組織について以下を判定しJSON返却してください:\n"
            "- stakeholder_type: この市場における役割\n"
            "- description: 日本語で組織の立場と対象サービスへの態度を具体的に\n"
            "- headcount: 組織の従業員数（実際の規模に近い値）\n"
            "- revenue: 月間売上（万円）\n\n"
            "【重要1】対象サービスの市場に無関係な組織は除外してください:\n"
            "- 情報ソース（Yahoo Finance, Bloomberg, TechCrunch, Google Trends等）\n"
            "- 調査対象の市場と直接関係ない開発ツール・プラットフォーム（GitHub, GitLab等）\n"
            "- リサーチ・コンサル会社（McKinsey, Gartner等）\n"
            "→ 除外する組織は \"exclude\": true を付与してください\n\n"
            "【重要2】企業とサービス/製品を区別してください:\n"
            "- 「Google」「Microsoft」等の企業名 → 企業全体の従業員数\n"
            "- 「Google Bard」「Azure」「Copilot」等のサービス名 → そのサービスの事業部門規模を推定\n"
            "  （例: Azure事業部 ≒ 数千人, Copilot事業部 ≒ 数百人）\n"
            "- 同一企業の複数サービスが一覧にある場合、それぞれ異なるheadcountにすること\n"
            "- 重複する組織（例: Google と Alphabet）は1つにまとめ、もう片方は除外\n\n"
            "有効なJSONのみを返してください。マークダウンやコードブロックは不要です。\n"
            '{"agents":[{"name":"組織名","stakeholder_type":"enterprise",'
            '"description":"日本語で役割・態度・立場を説明",'
            '"headcount":5000,"revenue":10000,"exclude":false}]}\n\n'
            "stakeholder_type: enterprise/end_user/government/investor/platformer/community"
        )

        try:
            response = await self.llm.generate_json(
                task_type=TaskType.PERSONA_GENERATION,
                prompt=prompt,
                system_prompt="JSON形式で返答。descriptionは日本語で。",
            )
            return self._parse_agents(response)
        except Exception:
            logger.warning("エンティティ→エージェント変換失敗、個別LLMフォールバック")
            return await self._entities_to_agents_fallback(org_names, scenario)

    async def _entities_to_agents_fallback(
        self, org_names: list[str], scenario: ScenarioInput,
    ) -> list[BaseAgent]:
        """個別LLM呼び出しによるフォールバック: 財務データを活用して推定."""
        agents: list[BaseAgent] = []
        for name in org_names[:30]:
            # 財務データコンテキストを構築
            fd = self._finance_lookup.get(name.lower())
            finance_ctx = ""
            if fd:
                parts = []
                if fd["market_cap"]:
                    parts.append(f"時価総額: ${fd['market_cap']/1e9:.1f}B")
                if fd["revenue"]:
                    parts.append(f"年間売上: ${fd['revenue']/1e9:.1f}B")
                if fd["sector"]:
                    parts.append(f"セクター: {fd['sector']}")
                if parts:
                    finance_ctx = f"\n財務データ: {', '.join(parts)}"

            try:
                prompt = (
                    f"組織「{name}」について推定してください。{finance_ctx}\n"
                    f"サービス: {scenario.service_name or '不明'}\n"
                    f"文脈: {scenario.description[:200]}\n\n"
                    "この組織が対象サービスの市場に直接関係するか判定してください。\n"
                    "情報ソース（Yahoo Finance等）、開発ツール（GitHub等）、\n"
                    "リサーチ会社など市場に無関係な組織は exclude: true としてください。\n\n"
                    "有効なJSONのみを返してください:\n"
                    '{"stakeholder_type":"enterprise","headcount":推定従業員数,'
                    '"revenue":推定月間売上万円,"description":"この組織の概要を日本語で1文",'
                    '"exclude":false}'
                )
                response = await self.llm.generate_json(
                    task_type=TaskType.AGENT_DECISION,
                    prompt=prompt,
                    system_prompt="組織のプロフィールをJSON形式で返答。",
                )
                response["name"] = name
                if response.get("exclude"):
                    logger.info("LLMが市場無関係と判定しスキップ: %s", name)
                    continue
                agent = self._create_agent(response)
                if agent:
                    agents.append(agent)
                    continue
            except Exception:
                pass

            # LLMも失敗: デフォルト値で作成
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
        existing_agents: list[BaseAgent] | None = None,
    ) -> list[BaseAgent]:
        """既存エージェントに不足しているステークホルダーを補完する."""
        existing_list = ", ".join(existing_names) if existing_names else "none"

        # 現在の構成比を算出
        type_counts: dict[str, int] = {}
        if existing_agents:
            for a in existing_agents:
                st = a.profile.stakeholder_type.value
                type_counts[st] = type_counts.get(st, 0) + 1
        composition_text = ", ".join(f"{k}: {v}体" for k, v in type_counts.items()) if type_counts else "なし"

        # ステークホルダーレポートの要約（あれば）
        stakeholder_ctx = ""
        if self._stakeholder_report:
            stakeholder_ctx = (
                f"\n【市場調査ステークホルダーレポート（抜粋）】\n"
                f"{self._stakeholder_report[:500]}\n"
            )

        # 財務データから市場規模コンテキストを構築
        finance_ctx = ""
        if self._finance_lookup:
            companies_with_cap = [
                (v["company_name"], v["market_cap"])
                for v in self._finance_lookup.values()
                if v.get("market_cap")
            ]
            if companies_with_cap:
                total_cap = sum(c[1] for c in companies_with_cap)
                finance_ctx = (
                    f"\n【市場規模の参考データ】\n"
                    f"関連上場企業{len(companies_with_cap)}社の時価総額合計: ${total_cap/1e9:.0f}B\n"
                    f"→ この規模の市場には複数のVC・機関投資家が関与しているはず。\n"
                    f"  レポートに登場する具体的な投資家名を使ってください。\n"
                )

        service = scenario.service_name or "対象サービス"
        prompt = (
            f"サービス: {service}\n"
            f"概要: {scenario.description[:300]}\n"
            f"既存エージェント: {existing_list}\n"
            f"現在の構成: {composition_text}\n"
            f"{stakeholder_ctx}{finance_ctx}\n"
            "【重要】現在の構成はenterprise/platformerに偏っています。\n"
            "シミュレーションの質を上げるため、以下の種別を重点的に補完してください:\n"
            f"- end_user: 最低3セグメント（'{service}の潜在ユーザー層', '競合サービスの既存ユーザー層', "
            "'テクノロジーに懐疑的な層'等、集団を表す名前にする）\n"
            "- investor: 最低2体（ステークホルダーレポートや概要に登場する具体的なVC・投資家名を使う。"
            "  例: Sequoia Capital, a16z, SoftBank Vision Fund等。この市場に実際に投資している/しそうな投資家）\n"
            "- community: 最低1体（業界団体、OSS/開発者コミュニティ等）\n"
            "- government: 最低1体（規制当局）\n\n"
            f"注意: '{service}'自体およびその運営企業（{', '.join(self._protagonist_aliases)}）は"
            "シミュレーション対象なのでエージェントにしないでください。\n\n"
            "有効なJSONのみを返してください:\n"
            '{"agents":[{"name":"名前","stakeholder_type":"end_user",'
            '"description":"日本語で役割・態度・立場を具体的に説明",'
            '"headcount":5000}]}\n\n'
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
            return [
                a for a in agents
                if a.name not in existing_names
                and a.name.lower() not in self._protagonist_aliases
            ]
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
                if raw.get("exclude"):
                    logger.info("LLMが市場無関係と判定しスキップ: %s", name)
                    continue
                if _is_non_market_player(name):
                    logger.info("非市場プレイヤーをスキップ: %s", name)
                    continue
                if hasattr(self, "_protagonist_aliases") and name.lower() in self._protagonist_aliases:
                    logger.info("主人公/運営企業をスキップ: %s", name)
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

        # ペルソナ（LLM応答がなければ種別プリセットを使用）
        raw_persona = raw.get("personality", {})
        preset = _get_personality_preset(stakeholder_str)
        personality = AgentPersonality(
            conservatism=_clamp(raw_persona.get("conservatism", preset["conservatism"])),
            bandwagon=_clamp(raw_persona.get("bandwagon", preset["bandwagon"])),
            overconfidence=_clamp(raw_persona.get("overconfidence", preset["overconfidence"])),
            sunk_cost_bias=_clamp(raw_persona.get("sunk_cost_bias", preset["sunk_cost_bias"])),
            info_sensitivity=_clamp(raw_persona.get("info_sensitivity", preset["info_sensitivity"])),
            noise=_clamp(raw_persona.get("noise", preset["noise"]), 0.0, 0.3),
            description=raw_persona.get("description", "") or str(preset["description"]),
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


# ステークホルダー種別ごとの性格プリセット（LLM不要フォールバック用）
_PERSONALITY_PRESETS: dict[str, dict[str, float | str]] = {
    "platformer": {
        "conservatism": 0.7, "bandwagon": 0.3, "overconfidence": 0.6,
        "sunk_cost_bias": 0.7, "info_sensitivity": 0.7, "noise": 0.05,
        "description": "大規模プラットフォーム。既存エコシステムの防衛意識が強く、競合の動きに敏感",
    },
    "enterprise": {
        "conservatism": 0.6, "bandwagon": 0.4, "overconfidence": 0.4,
        "sunk_cost_bias": 0.6, "info_sensitivity": 0.6, "noise": 0.08,
        "description": "企業としての安定志向。実績と信頼性を重視する堅実な判断",
    },
    "government": {
        "conservatism": 0.8, "bandwagon": 0.2, "overconfidence": 0.2,
        "sunk_cost_bias": 0.4, "info_sensitivity": 0.8, "noise": 0.03,
        "description": "規制と安全性を重視。データに基づく慎重な判断。イノベーションと規制のバランスを取る",
    },
    "investor": {
        "conservatism": 0.3, "bandwagon": 0.5, "overconfidence": 0.5,
        "sunk_cost_bias": 0.3, "info_sensitivity": 0.9, "noise": 0.1,
        "description": "市場データに極めて敏感。成長性とリスクを冷静に分析。トレンドにも注目",
    },
    "community": {
        "conservatism": 0.4, "bandwagon": 0.6, "overconfidence": 0.3,
        "sunk_cost_bias": 0.3, "info_sensitivity": 0.7, "noise": 0.1,
        "description": "業界全体の発展を重視。新技術・新サービスに対してオープンだが公平性も求める",
    },
    "freelancer": {
        "conservatism": 0.3, "bandwagon": 0.5, "overconfidence": 0.4,
        "sunk_cost_bias": 0.2, "info_sensitivity": 0.6, "noise": 0.12,
        "description": "柔軟で新しいツールに積極的。コストパフォーマンスと生産性を最重視",
    },
    "indie_developer": {
        "conservatism": 0.2, "bandwagon": 0.3, "overconfidence": 0.6,
        "sunk_cost_bias": 0.2, "info_sensitivity": 0.5, "noise": 0.15,
        "description": "独自路線の革新志向。技術的な面白さと市場機会を追求。リスクを恐れない",
    },
    "end_user": {
        "conservatism": 0.5, "bandwagon": 0.6, "overconfidence": 0.3,
        "sunk_cost_bias": 0.5, "info_sensitivity": 0.4, "noise": 0.1,
        "description": "使い勝手と価格を重視。周囲の評判に影響されやすい。乗り換えコストに敏感",
    },
}


def _get_personality_preset(stakeholder_type: str) -> dict[str, float | str]:
    """ステークホルダー種別に応じた性格プリセットを返す."""
    return _PERSONALITY_PRESETS.get(stakeholder_type, _PERSONALITY_PRESETS["enterprise"])
