"""エージェント動的生成: シード文書とシナリオからエージェントを自動生成する.

MiroFishのOasisProfileGenerator相当。
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
from app.simulation.agents.enterprise import EnterpriseITAgent
from app.simulation.agents.freelancer import FreelancerAgent
from app.simulation.agents.ses_company import SESCompanyAgent
from app.simulation.agents.sier_company import SIerCompanyAgent
from app.simulation.models import Industry, ScenarioInput, SkillCategory
from app.simulation.scenario_analyzer import EnrichedScenario

logger = logging.getLogger(__name__)

# agent_type → エージェントクラスのマッピング
_AGENT_CLASS_MAP: dict[str, type[BaseAgent]] = {
    "SES企業": SESCompanyAgent,
    "SIer企業": SIerCompanyAgent,
    "フリーランス": FreelancerAgent,
    "事業会社IT": EnterpriseITAgent,
}

# industry文字列 → Industryの正規化
_INDUSTRY_MAP: dict[str, Industry] = {
    "sier": Industry.SIER,
    "ses": Industry.SES,
    "freelance": Industry.FREELANCE,
    "web_startup": Industry.WEB_STARTUP,
    "enterprise_it": Industry.ENTERPRISE_IT,
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
        """LLMにエンティティ情報を渡してエージェントを生成する.

        Args:
            scenario: シナリオ入力
            enriched: NLP解析済みシナリオ
            document_entities: 文書から抽出されたエンティティ
                {"technologies": [...], "organizations": [...], "policies": [...]}

        Returns:
            生成されたエージェントのリスト
        """
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
        logger.info("デフォルトエージェント（10体）を使用")
        return create_default_agents(self.llm)

    def _system_prompt(self) -> str:
        return (
            "あなたは日本のIT人材市場の専門家です。\n"
            "シナリオと参考資料の情報に基づいて、シミュレーションに登場するエージェント（企業・個人）を生成してください。\n"
            "各エージェントは日本のIT業界の実態を反映した、リアリティのある設定にしてください。\n"
            "エージェントの種類は必ず以下のいずれかにしてください:\n"
            "- SES企業: エンジニアを客先に派遣する企業\n"
            "- SIer企業: システム開発を請け負う企業\n"
            "- フリーランス: 独立したエンジニア個人\n"
            "- 事業会社IT: 非IT企業の社内IT部門\n\n"
            "industryは sier, ses, freelance, web_startup, enterprise_it のいずれかにしてください。\n"
            "skillsのキーは legacy, web_frontend, web_backend, cloud_infra, ai_ml, security, mobile, erp のいずれかにしてください。\n"
            "回答はJSON形式のみ。説明文は不要です。"
        )

    def _build_prompt(
        self,
        scenario: ScenarioInput,
        enriched: EnrichedScenario,
        document_entities: dict[str, list[str]] | None,
    ) -> str:
        lines = [
            "以下の情報に基づいて、シミュレーションに登場する5〜15体のエージェントをJSON形式で生成してください。",
            "",
            f"【シナリオ】\n{scenario.description}",
        ]

        if enriched.detected_skills:
            skills = ", ".join(s.value for s in enriched.detected_skills)
            lines.append(f"\n【検出されたスキルカテゴリ】\n{skills}")

        if enriched.detected_industries:
            industries = ", ".join(i.value for i in enriched.detected_industries)
            lines.append(f"\n【検出された業界】\n{industries}")

        if enriched.detected_policies:
            lines.append(f"\n【検出された政策】\n{', '.join(enriched.detected_policies)}")

        entities = document_entities or {}
        if entities.get("organizations"):
            lines.append(f"\n【参考資料に登場する企業・組織】\n{', '.join(entities['organizations'])}")
            lines.append("↑これらの企業名をエージェント名として使ってください。")

        if entities.get("technologies"):
            lines.append(f"\n【参考資料に登場する技術】\n{', '.join(entities['technologies'])}")

        if entities.get("policies"):
            lines.append(f"\n【参考資料に登場する政策】\n{', '.join(entities['policies'])}")

        lines.append("")
        lines.append(
            '回答形式:\n{"agents": [\n'
            '  {\n'
            '    "name": "エージェント名",\n'
            '    "agent_type": "SES企業|SIer企業|フリーランス|事業会社IT",\n'
            '    "industry": "sier|ses|freelance|web_startup|enterprise_it",\n'
            '    "description": "背景説明（1-2文）",\n'
            '    "headcount": 数値,\n'
            '    "revenue": 数値（万円/月）,\n'
            '    "cost": 数値（万円/月）,\n'
            '    "skills": {"スキルカテゴリ": 0.0-1.0, ...},\n'
            '    "personality": {\n'
            '      "conservatism": 0.0-1.0,\n'
            '      "bandwagon": 0.0-1.0,\n'
            '      "overconfidence": 0.0-1.0,\n'
            '      "sunk_cost_bias": 0.0-1.0,\n'
            '      "info_sensitivity": 0.0-1.0,\n'
            '      "noise": 0.0-0.3,\n'
            '      "description": "性格の説明"\n'
            '    }\n'
            '  }\n'
            ']}'
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
        agent_type = raw.get("agent_type", "SES企業")
        agent_class = _AGENT_CLASS_MAP.get(agent_type)
        if not agent_class:
            logger.warning("未知のagent_type: %s、SES企業として扱う", agent_type)
            agent_class = SESCompanyAgent

        industry_str = raw.get("industry", "ses")
        industry = _INDUSTRY_MAP.get(industry_str, Industry.SES)

        # スキル
        raw_skills = raw.get("skills", {})
        skills: dict[SkillCategory, float] = {}
        for skill_key, proficiency in raw_skills.items():
            try:
                sc = SkillCategory(skill_key)
                skills[sc] = max(0.0, min(1.0, float(proficiency)))
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
            agent_type=agent_type,
            industry=industry,
            description=raw.get("description", ""),
        )

        state = AgentState(
            headcount=max(1, int(raw.get("headcount", 10))),
            revenue=max(0, float(raw.get("revenue", 100))),
            cost=max(0, float(raw.get("cost", 50))),
            skills=skills,
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
