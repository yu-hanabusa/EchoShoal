"""シナリオ解析サービス — NLP解析とLLMを使ってシナリオを強化する."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.llm.router import LLMRouter, TaskType
from app.core.nlp.analyzer import AnalysisResult, JapaneseAnalyzer
from app.simulation.models import Industry, ScenarioInput, SkillCategory

logger = logging.getLogger(__name__)

# 技術名 → SkillCategory へのマッピング
_TECH_TO_CATEGORY: dict[str, SkillCategory] = {
    # レガシー
    "COBOL": SkillCategory.LEGACY, "VB.NET": SkillCategory.LEGACY,
    "メインフレーム": SkillCategory.LEGACY, "AS/400": SkillCategory.LEGACY,
    # Web フロントエンド
    "React": SkillCategory.WEB_FRONTEND, "Vue.js": SkillCategory.WEB_FRONTEND,
    "TypeScript": SkillCategory.WEB_FRONTEND, "Angular": SkillCategory.WEB_FRONTEND,
    "Next.js": SkillCategory.WEB_FRONTEND,
    # Web バックエンド
    "Python": SkillCategory.WEB_BACKEND, "Go": SkillCategory.WEB_BACKEND,
    "Node.js": SkillCategory.WEB_BACKEND, "Java": SkillCategory.WEB_BACKEND,
    "PHP": SkillCategory.WEB_BACKEND, "Ruby": SkillCategory.WEB_BACKEND,
    # クラウド
    "AWS": SkillCategory.CLOUD_INFRA, "GCP": SkillCategory.CLOUD_INFRA,
    "Azure": SkillCategory.CLOUD_INFRA, "Kubernetes": SkillCategory.CLOUD_INFRA,
    "Docker": SkillCategory.CLOUD_INFRA, "Terraform": SkillCategory.CLOUD_INFRA,
    # AI/ML
    "PyTorch": SkillCategory.AI_ML, "TensorFlow": SkillCategory.AI_ML,
    "LLM": SkillCategory.AI_ML, "ChatGPT": SkillCategory.AI_ML,
    "GPT-4": SkillCategory.AI_ML, "Claude": SkillCategory.AI_ML,
    "Gemini": SkillCategory.AI_ML, "生成AI": SkillCategory.AI_ML,
    "機械学習": SkillCategory.AI_ML, "深層学習": SkillCategory.AI_ML,
    # モバイル
    "Swift": SkillCategory.MOBILE, "Kotlin": SkillCategory.MOBILE,
    "Flutter": SkillCategory.MOBILE, "React Native": SkillCategory.MOBILE,
    # ERP
    "SAP": SkillCategory.ERP, "Oracle ERP": SkillCategory.ERP,
    "Salesforce": SkillCategory.ERP, "ServiceNow": SkillCategory.ERP,
}

# 組織名キーワード → Industry へのマッピング
_ORG_KEYWORDS_TO_INDUSTRY: dict[str, Industry] = {
    "SIer": Industry.SIER, "SI企業": Industry.SIER,
    "SES": Industry.SES,
    "フリーランス": Industry.FREELANCE,
    "スタートアップ": Industry.WEB_STARTUP, "Web系": Industry.WEB_STARTUP,
    "情シス": Industry.ENTERPRISE_IT, "情報システム": Industry.ENTERPRISE_IT,
    "DX推進": Industry.ENTERPRISE_IT,
}


@dataclass
class EnrichedScenario:
    """NLP解析で強化されたシナリオ情報."""
    original: ScenarioInput
    analysis: AnalysisResult
    detected_skills: list[SkillCategory] = field(default_factory=list)
    detected_industries: list[Industry] = field(default_factory=list)
    detected_policies: list[str] = field(default_factory=list)
    context_summary: str = ""


class ScenarioAnalyzer:
    """シナリオテキストを解析し、シミュレーションに必要な情報を抽出する."""

    def __init__(self, llm: LLMRouter | None = None):
        self._analyzer = JapaneseAnalyzer()
        self._llm = llm

    async def analyze_async(self, scenario: ScenarioInput) -> EnrichedScenario:
        """シナリオを非同期で解析する（LLMパラメータ推定あり）."""
        enriched = self.analyze(scenario)

        # LLMでパラメータを推定
        if self._llm and (scenario.ai_acceleration == 0 and scenario.economic_shock == 0):
            estimated = await self._estimate_params_with_llm(scenario.description)
            if estimated:
                enriched.original.ai_acceleration = estimated.get("ai_acceleration", 0.0)
                enriched.original.economic_shock = estimated.get("economic_shock", 0.0)
                if not scenario.policy_change and estimated.get("policy_change"):
                    enriched.original.policy_change = estimated["policy_change"]
                logger.info(
                    "LLMパラメータ推定: AI=%.1f, 経済=%.1f, 政策=%s",
                    enriched.original.ai_acceleration,
                    enriched.original.economic_shock,
                    enriched.original.policy_change or "なし",
                )

            # context_summaryを再構築（推定値を反映）
            enriched.context_summary = self._build_context_summary(
                enriched.original,
                enriched.detected_skills,
                enriched.detected_industries,
                enriched.detected_policies,
            )

        return enriched

    def analyze(self, scenario: ScenarioInput) -> EnrichedScenario:
        """シナリオを解析して強化情報を返す."""
        analysis = self._analyzer.analyze(scenario.description)

        # 技術名 → SkillCategory
        detected_skills = list(set(
            _TECH_TO_CATEGORY[tech]
            for tech in analysis.technologies
            if tech in _TECH_TO_CATEGORY
        ))

        # 組織名キーワード → Industry
        detected_industries = list(set(
            industry
            for keyword, industry in _ORG_KEYWORDS_TO_INDUSTRY.items()
            if keyword in scenario.description
        ))

        # ユーザー指定を優先しつつ、NLP検出を補完
        merged_skills = list(set(scenario.focus_skills + detected_skills))
        merged_industries = list(set(scenario.focus_industries + detected_industries))

        context_summary = self._build_context_summary(
            scenario, merged_skills, merged_industries, analysis.policies,
        )

        enriched = EnrichedScenario(
            original=scenario,
            analysis=analysis,
            detected_skills=merged_skills,
            detected_industries=merged_industries,
            detected_policies=analysis.policies,
            context_summary=context_summary,
        )

        logger.info(
            "シナリオ解析完了: スキル%d件, 業界%d件, 政策%d件",
            len(merged_skills), len(merged_industries), len(analysis.policies),
        )

        # ポリシー自動検出（NLPルールベース、LLM不要）
        if not scenario.policy_change and analysis.policies:
            enriched.original.policy_change = ", ".join(analysis.policies)

        return enriched

    async def _estimate_params_with_llm(self, description: str) -> dict[str, Any] | None:
        """LLMにシナリオテキストを渡してパラメータを推定させる."""
        if not self._llm:
            return None

        prompt = (
            "以下のシナリオテキストを分析し、日本のIT人材市場シミュレーションのパラメータを推定してください。\n\n"
            f"シナリオ:\n{description}\n\n"
            "以下のJSON形式で回答してください:\n"
            "{\n"
            '  "ai_acceleration": <-1.0〜1.0の数値。AI技術の普及加速度。正=AI普及が加速、負=停滞>,\n'
            '  "economic_shock": <-1.0〜1.0の数値。経済ショック。正=好景気、負=不況>,\n'
            '  "policy_change": <関連する政策変更があれば文字列、なければnull>,\n'
            '  "reasoning": <判断の根拠を1-2文で説明>\n'
            "}"
        )

        try:
            response = await self._llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=prompt,
                system_prompt="あなたは日本のIT市場の専門アナリストです。シナリオテキストからシミュレーションパラメータを客観的に推定してください。",
            )
            # 値を -1.0〜1.0 にクランプ
            ai = max(-1.0, min(1.0, float(response.get("ai_acceleration", 0))))
            econ = max(-1.0, min(1.0, float(response.get("economic_shock", 0))))
            reasoning = response.get("reasoning", "")
            if reasoning:
                logger.info("LLMパラメータ推定根拠: %s", reasoning)

            return {
                "ai_acceleration": ai,
                "economic_shock": econ,
                "policy_change": response.get("policy_change"),
            }
        except Exception:
            logger.warning("LLMパラメータ推定失敗、デフォルト値を使用")
            return None

    def _build_context_summary(
        self,
        scenario: ScenarioInput,
        skills: list[SkillCategory],
        industries: list[Industry],
        policies: list[str],
    ) -> str:
        """シナリオの要約テキストを生成する（エージェントプロンプト注入用）."""
        lines: list[str] = [scenario.description]

        if skills:
            skill_names = ", ".join(s.value for s in skills)
            lines.append(f"注目スキル: {skill_names}")
        if industries:
            ind_names = ", ".join(i.value for i in industries)
            lines.append(f"関連業界: {ind_names}")
        if policies:
            lines.append(f"関連政策: {', '.join(policies)}")
        if scenario.ai_acceleration > 0.3:
            lines.append(f"AI加速度が高い（{scenario.ai_acceleration:+.1f}）: AI技術の急速な普及が予想される")
        elif scenario.ai_acceleration < -0.3:
            lines.append(f"AI減速（{scenario.ai_acceleration:+.1f}）: AI導入が停滞する見通し")
        if scenario.economic_shock < -0.3:
            lines.append(f"経済ショック（{scenario.economic_shock:+.1f}）: 景気後退による投資縮小")
        elif scenario.economic_shock > 0.3:
            lines.append(f"経済好調（{scenario.economic_shock:+.1f}）: IT投資拡大の見通し")
        if scenario.policy_change:
            lines.append(f"政策変更: {scenario.policy_change}")

        return "\n".join(lines)
