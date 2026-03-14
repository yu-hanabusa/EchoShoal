"""シナリオ解析サービス — NLP解析と知識グラフを連携してシナリオを強化する."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

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

    def __init__(self):
        self._analyzer = JapaneseAnalyzer()

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

        enriched = EnrichedScenario(
            original=scenario,
            analysis=analysis,
            detected_skills=merged_skills,
            detected_industries=merged_industries,
            detected_policies=analysis.policies,
        )

        logger.info(
            "シナリオ解析完了: スキル%d件, 業界%d件, 政策%d件",
            len(merged_skills), len(merged_industries), len(analysis.policies),
        )

        return enriched
