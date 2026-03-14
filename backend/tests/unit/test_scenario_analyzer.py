"""シナリオ解析サービスのユニットテスト."""

import pytest

from app.simulation.models import Industry, ScenarioInput, SkillCategory
from app.simulation.scenario_analyzer import ScenarioAnalyzer


class TestScenarioAnalyzer:
    def setup_method(self):
        self.analyzer = ScenarioAnalyzer()

    def test_detect_ai_skills(self):
        scenario = ScenarioInput(
            description="生成AIとLLMの急速な普及により、Python エンジニアの需要が大幅に増加する"
        )
        result = self.analyzer.analyze(scenario)
        assert SkillCategory.AI_ML in result.detected_skills
        assert SkillCategory.WEB_BACKEND in result.detected_skills  # Python

    def test_detect_cloud_skills(self):
        scenario = ScenarioInput(
            description="AWS と Kubernetes によるクラウドネイティブ化が進み、インフラエンジニアが不足する"
        )
        result = self.analyzer.analyze(scenario)
        assert SkillCategory.CLOUD_INFRA in result.detected_skills

    def test_detect_industries(self):
        scenario = ScenarioInput(
            description="SES業界ではフリーランスへの転向が加速し、SIer企業との関係が変化する"
        )
        result = self.analyzer.analyze(scenario)
        assert Industry.SES in result.detected_industries
        assert Industry.FREELANCE in result.detected_industries
        assert Industry.SIER in result.detected_industries

    def test_detect_policies(self):
        scenario = ScenarioInput(
            description="インボイス制度の導入によりフリーランスエンジニアの収入が減少する可能性がある"
        )
        result = self.analyzer.analyze(scenario)
        assert "インボイス制度" in result.detected_policies
        assert Industry.FREELANCE in result.detected_industries

    def test_user_specified_skills_preserved(self):
        scenario = ScenarioInput(
            description="セキュリティ人材の需要が増加するシナリオ",
            focus_skills=[SkillCategory.SECURITY],
        )
        result = self.analyzer.analyze(scenario)
        assert SkillCategory.SECURITY in result.detected_skills

    def test_user_specified_industries_preserved(self):
        scenario = ScenarioInput(
            description="テストシナリオの説明文です",
            focus_industries=[Industry.WEB_STARTUP],
        )
        result = self.analyzer.analyze(scenario)
        assert Industry.WEB_STARTUP in result.detected_industries

    def test_merge_user_and_nlp_skills(self):
        scenario = ScenarioInput(
            description="AWS のスキルが重要になるシナリオ",
            focus_skills=[SkillCategory.AI_ML],
        )
        result = self.analyzer.analyze(scenario)
        assert SkillCategory.AI_ML in result.detected_skills
        assert SkillCategory.CLOUD_INFRA in result.detected_skills

    def test_no_detection_plain_text(self):
        scenario = ScenarioInput(
            description="日本のIT人材市場の将来的な変化を予測するシナリオ"
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
