"""シナリオ解析サービス — NLP解析とLLMを使ってシナリオを強化する."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from app.core.llm.router import LLMRouter, TaskType
from app.core.nlp.analyzer import AnalysisResult, JapaneseAnalyzer
from app.simulation.models import StakeholderType, ScenarioInput, MarketDimension

logger = logging.getLogger(__name__)

# 技術名 → MarketDimension へのマッピング
_TECH_TO_DIMENSION: dict[str, MarketDimension] = {
    # AI/ML関連 → tech_maturity
    "PyTorch": MarketDimension.TECH_MATURITY, "TensorFlow": MarketDimension.TECH_MATURITY,
    "LLM": MarketDimension.TECH_MATURITY, "ChatGPT": MarketDimension.TECH_MATURITY,
    "GPT-4": MarketDimension.TECH_MATURITY, "Claude": MarketDimension.TECH_MATURITY,
    "Gemini": MarketDimension.TECH_MATURITY, "生成AI": MarketDimension.TECH_MATURITY,
    "機械学習": MarketDimension.TECH_MATURITY, "深層学習": MarketDimension.TECH_MATURITY,
    # クラウド → ecosystem_health
    "AWS": MarketDimension.ECOSYSTEM_HEALTH, "GCP": MarketDimension.ECOSYSTEM_HEALTH,
    "Azure": MarketDimension.ECOSYSTEM_HEALTH, "Kubernetes": MarketDimension.ECOSYSTEM_HEALTH,
    "Docker": MarketDimension.ECOSYSTEM_HEALTH,
    # Web技術 → tech_maturity
    "React": MarketDimension.TECH_MATURITY, "Vue.js": MarketDimension.TECH_MATURITY,
    "Next.js": MarketDimension.TECH_MATURITY, "Python": MarketDimension.TECH_MATURITY,
    "Go": MarketDimension.TECH_MATURITY, "Node.js": MarketDimension.TECH_MATURITY,
    # モバイル → user_adoption
    "Swift": MarketDimension.USER_ADOPTION, "Kotlin": MarketDimension.USER_ADOPTION,
    "Flutter": MarketDimension.USER_ADOPTION, "React Native": MarketDimension.USER_ADOPTION,
    # SaaS/プラットフォーム → competitive_pressure
    "SAP": MarketDimension.COMPETITIVE_PRESSURE, "Salesforce": MarketDimension.COMPETITIVE_PRESSURE,
    "ServiceNow": MarketDimension.COMPETITIVE_PRESSURE,
}

# 組織名キーワード → StakeholderType へのマッピング
_ORG_KEYWORDS_TO_STAKEHOLDER: dict[str, StakeholderType] = {
    "企業": StakeholderType.ENTERPRISE, "大手": StakeholderType.ENTERPRISE,
    "スタートアップ": StakeholderType.ENTERPRISE,
    "フリーランス": StakeholderType.FREELANCER,
    "個人開発": StakeholderType.INDIE_DEVELOPER, "インディー": StakeholderType.INDIE_DEVELOPER,
    "行政": StakeholderType.GOVERNMENT, "政府": StakeholderType.GOVERNMENT,
    "デジタル庁": StakeholderType.GOVERNMENT,
    "VC": StakeholderType.INVESTOR, "投資": StakeholderType.INVESTOR,
    "ファンド": StakeholderType.INVESTOR,
    "AWS": StakeholderType.PLATFORMER, "Google": StakeholderType.PLATFORMER,
    "Microsoft": StakeholderType.PLATFORMER, "Apple": StakeholderType.PLATFORMER,
    "コミュニティ": StakeholderType.COMMUNITY, "OSS": StakeholderType.COMMUNITY,
    "業界団体": StakeholderType.COMMUNITY,
}


@dataclass
class InterpolatedInfo:
    """LLMが推定した不足情報（ユーザー未入力の情報を補間）."""
    revenue_model: str = ""
    price_range: str = ""
    competitors: list[str] = field(default_factory=list)
    target_users: str = ""
    tech_stack: str = ""
    team_size_estimate: str = ""
    market_size_estimate: str = ""
    confidence_notes: list[str] = field(default_factory=list)


@dataclass
class EnrichedScenario:
    """NLP解析で強化されたシナリオ情報."""
    original: ScenarioInput
    analysis: AnalysisResult
    detected_dimensions: list[MarketDimension] = field(default_factory=list)
    detected_stakeholders: list[StakeholderType] = field(default_factory=list)
    detected_policies: list[str] = field(default_factory=list)
    context_summary: str = ""
    interpolated_info: InterpolatedInfo = field(default_factory=InterpolatedInfo)


class ScenarioAnalyzer:
    """シナリオテキストを解析し、シミュレーションに必要な情報を抽出する."""

    def __init__(self, llm: LLMRouter | None = None):
        self._analyzer = JapaneseAnalyzer()
        self._llm = llm

    async def analyze_async(self, scenario: ScenarioInput) -> EnrichedScenario:
        """シナリオを非同期で解析する（LLMパラメータ推定あり）."""
        enriched = self.analyze(scenario)

        # LLMで不足情報を補間
        if self._llm:
            interpolated = await self._interpolate_missing_info(scenario)
            if interpolated:
                enriched.interpolated_info = interpolated
                # 補間情報をcontext_summaryに追加
                enriched.context_summary = self._build_context_summary(
                    enriched.original,
                    enriched.detected_dimensions,
                    enriched.detected_stakeholders,
                    enriched.detected_policies,
                    interpolated,
                )
                logger.info(
                    "LLM情報補間: 収益モデル=%s, 競合%d件, 信頼度メモ%d件",
                    interpolated.revenue_model or "未推定",
                    len(interpolated.competitors),
                    len(interpolated.confidence_notes),
                )

        return enriched

    def analyze(self, scenario: ScenarioInput) -> EnrichedScenario:
        """シナリオを解析して強化情報を返す."""
        analysis = self._analyzer.analyze(scenario.description)

        # 技術名 → MarketDimension
        detected_dimensions = list(set(
            _TECH_TO_DIMENSION[tech]
            for tech in analysis.technologies
            if tech in _TECH_TO_DIMENSION
        ))

        # 組織名キーワード → StakeholderType
        detected_stakeholders = list(set(
            stakeholder
            for keyword, stakeholder in _ORG_KEYWORDS_TO_STAKEHOLDER.items()
            if keyword in scenario.description
        ))

        context_summary = self._build_context_summary(
            scenario, detected_dimensions, detected_stakeholders, analysis.policies,
        )

        enriched = EnrichedScenario(
            original=scenario,
            analysis=analysis,
            detected_dimensions=detected_dimensions,
            detected_stakeholders=detected_stakeholders,
            detected_policies=analysis.policies,
            context_summary=context_summary,
        )

        logger.info(
            "シナリオ解析完了: ディメンション%d件, ステークホルダー%d件, 政策%d件",
            len(detected_dimensions), len(detected_stakeholders), len(analysis.policies),
        )

        # ポリシー自動検出（NLPルールベース、LLM不要）
        if not scenario.regulatory_change and analysis.policies:
            enriched.original.regulatory_change = ", ".join(analysis.policies)

        return enriched

    async def _interpolate_missing_info(self, scenario: ScenarioInput) -> InterpolatedInfo | None:
        """LLMにサービス情報を渡し、不足している市場情報を推定させる."""
        if not self._llm:
            return None

        prompt = (
            "以下のサービス情報を分析し、シミュレーションに必要な不足情報を推定してください。\n"
            "推定に自信がない項目は空文字にしてください。\n\n"
            f"サービス名: {scenario.service_name or '未指定'}\n"
            f"説明: {scenario.description}\n"
            f"ターゲット市場: {scenario.target_market or '未指定'}\n"
            f"URL: {scenario.service_url or 'なし'}\n\n"
            "以下のJSON形式で回答してください:\n"
            "{\n"
            '  "revenue_model": "SaaS月額/フリーミアム/広告/マーケットプレイス等",\n'
            '  "price_range": "無料/月額500円〜/年額10万円〜 等の推定価格帯",\n'
            '  "competitors": ["競合サービス1", "競合サービス2", ...],\n'
            '  "target_users": "ターゲットユーザー像の推定",\n'
            '  "tech_stack": "推定される技術スタック",\n'
            '  "team_size_estimate": "推定チーム規模（例: 5-10人のスタートアップ）",\n'
            '  "market_size_estimate": "推定市場規模（例: 国内100億円規模）",\n'
            '  "confidence_notes": ["推定根拠1", "推定根拠2", ...]\n'
            "}"
        )

        try:
            response = await self._llm.generate_json(
                task_type=TaskType.AGENT_DECISION,
                prompt=prompt,
                system_prompt=(
                    "あなたはサービスビジネスの専門アナリストです。"
                    "入力された情報から、類似サービスの知識に基づいて不足情報を推定してください。"
                    "推定に自信がない場合は空文字にしてください。"
                ),
            )
            competitors = response.get("competitors", [])
            if not isinstance(competitors, list):
                competitors = []
            notes = response.get("confidence_notes", [])
            if not isinstance(notes, list):
                notes = []

            return InterpolatedInfo(
                revenue_model=str(response.get("revenue_model", "")),
                price_range=str(response.get("price_range", "")),
                competitors=[str(c) for c in competitors[:10]],
                target_users=str(response.get("target_users", "")),
                tech_stack=str(response.get("tech_stack", "")),
                team_size_estimate=str(response.get("team_size_estimate", "")),
                market_size_estimate=str(response.get("market_size_estimate", "")),
                confidence_notes=[str(n) for n in notes[:10]],
            )
        except Exception:
            logger.warning("LLM情報補間失敗")
            return None

    def _build_context_summary(
        self,
        scenario: ScenarioInput,
        dimensions: list[MarketDimension],
        stakeholders: list[StakeholderType],
        policies: list[str],
        interpolated: InterpolatedInfo | None = None,
    ) -> str:
        """シナリオの要約テキストを生成する（エージェントプロンプト注入用）."""
        lines: list[str] = []

        if scenario.service_name:
            lines.append(f"対象サービス: {scenario.service_name}")
        lines.append(scenario.description)

        if scenario.target_market:
            lines.append(f"ターゲット市場: {scenario.target_market}")
        if dimensions:
            dim_names = ", ".join(d.value for d in dimensions)
            lines.append(f"注目ディメンション: {dim_names}")
        if stakeholders:
            st_names = ", ".join(s.value for s in stakeholders)
            lines.append(f"関連ステークホルダー: {st_names}")
        if policies:
            lines.append(f"関連政策: {', '.join(policies)}")
        if scenario.regulatory_change:
            lines.append(f"規制変更: {scenario.regulatory_change}")

        # LLM補間情報を追加
        if interpolated:
            interp_lines: list[str] = []
            if interpolated.revenue_model:
                interp_lines.append(f"収益モデル（推定）: {interpolated.revenue_model}")
            if interpolated.price_range:
                interp_lines.append(f"価格帯（推定）: {interpolated.price_range}")
            if interpolated.competitors:
                interp_lines.append(f"推定競合: {', '.join(interpolated.competitors)}")
            if interpolated.target_users:
                interp_lines.append(f"ターゲットユーザー（推定）: {interpolated.target_users}")
            if interpolated.market_size_estimate:
                interp_lines.append(f"市場規模（推定）: {interpolated.market_size_estimate}")
            if interp_lines:
                lines.append("\n【LLM推定による補間情報】")
                lines.extend(interp_lines)

        return "\n".join(lines)
