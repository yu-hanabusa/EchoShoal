"""シナリオ解析サービスのユニットテスト."""

import pytest

from app.simulation.models import StakeholderType, ScenarioInput, MarketDimension
from app.simulation.scenario_analyzer import InterpolatedInfo, ScenarioAnalyzer


class TestScenarioAnalyzer:
    def setup_method(self):
        self.analyzer = ScenarioAnalyzer()

    def test_detect_ai_dimensions(self):
        scenario = ScenarioInput(
            description="生成AIとLLMの急速な普及により、Python エンジニアの需要が大幅に増加する"
        )
        result = self.analyzer.analyze(scenario)
        assert MarketDimension.TECH_MATURITY in result.detected_dimensions

    def test_detect_cloud_dimensions(self):
        scenario = ScenarioInput(
            description="AWS と Kubernetes によるクラウドネイティブ化が進み、インフラエンジニアが不足する"
        )
        result = self.analyzer.analyze(scenario)
        assert MarketDimension.ECOSYSTEM_HEALTH in result.detected_dimensions

    def test_detect_stakeholders(self):
        scenario = ScenarioInput(
            description="フリーランスへの転向が加速し、大手企業との関係が変化する"
        )
        result = self.analyzer.analyze(scenario)
        assert StakeholderType.FREELANCER in result.detected_stakeholders
        assert StakeholderType.ENTERPRISE in result.detected_stakeholders

    def test_detect_policies(self):
        scenario = ScenarioInput(
            description="インボイス制度の導入によりフリーランスエンジニアの収入が減少する可能性がある"
        )
        result = self.analyzer.analyze(scenario)
        assert "インボイス制度" in result.detected_policies
        assert StakeholderType.FREELANCER in result.detected_stakeholders

    def test_detect_government_stakeholder(self):
        scenario = ScenarioInput(
            description="デジタル庁の政策により行政のDX推進が加速するシナリオ"
        )
        result = self.analyzer.analyze(scenario)
        assert StakeholderType.GOVERNMENT in result.detected_stakeholders

    def test_detect_investor_stakeholder(self):
        scenario = ScenarioInput(
            description="VCからの投資が急増し、スタートアップエコシステムが活性化する"
        )
        result = self.analyzer.analyze(scenario)
        assert StakeholderType.INVESTOR in result.detected_stakeholders

    def test_detect_platformer_stakeholder(self):
        scenario = ScenarioInput(
            description="Google と Microsoft がAIサービスで競合し、プラットフォーム戦争が激化する"
        )
        result = self.analyzer.analyze(scenario)
        assert StakeholderType.PLATFORMER in result.detected_stakeholders

    def test_detect_community_stakeholder(self):
        scenario = ScenarioInput(
            description="OSSコミュニティと業界団体が標準化を推進するシナリオ"
        )
        result = self.analyzer.analyze(scenario)
        assert StakeholderType.COMMUNITY in result.detected_stakeholders

    def test_no_detection_plain_text(self):
        scenario = ScenarioInput(
            description="日本のサービス市場の将来的な変化を予測するシナリオ"
        )
        result = self.analyzer.analyze(scenario)
        assert len(result.detected_policies) == 0

    def test_original_scenario_preserved(self):
        scenario = ScenarioInput(
            description="テストシナリオの説明文です",
            num_rounds=12,
        )
        result = self.analyzer.analyze(scenario)
        assert result.original.num_rounds == 12
        assert result.original.description == "テストシナリオの説明文です"

    def test_context_summary_includes_service_name(self):
        scenario = ScenarioInput(
            description="テストサービスの市場インパクトを予測するシナリオ",
            service_name="TestService",
            target_market="開発者ツール",
        )
        result = self.analyzer.analyze(scenario)
        assert "TestService" in result.context_summary
        assert "開発者ツール" in result.context_summary

    def test_interpolated_info_defaults(self):
        """InterpolatedInfoがデフォルトで空の状態で初期化される."""
        scenario = ScenarioInput(
            description="テストシナリオの説明文です",
        )
        result = self.analyzer.analyze(scenario)
        assert result.interpolated_info.revenue_model == ""
        assert result.interpolated_info.competitors == []
        assert result.interpolated_info.confidence_notes == []

    def test_context_summary_with_interpolated_info(self):
        """補間情報がcontext_summaryに反映される."""
        analyzer = ScenarioAnalyzer()
        scenario = ScenarioInput(
            description="テストサービスの市場インパクト",
            service_name="TestApp",
        )
        info = InterpolatedInfo(
            revenue_model="SaaS月額",
            competitors=["Competitor1", "Competitor2"],
            market_size_estimate="100億円",
        )
        summary = analyzer._build_context_summary(
            scenario, [], [], [], interpolated=info,
        )
        assert "SaaS月額" in summary
        assert "Competitor1" in summary
        assert "100億円" in summary
        assert "LLM推定" in summary
