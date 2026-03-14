"""GiNZA NLP アナライザーのユニットテスト（ルールベース部分のみ）."""

import pytest

from app.core.nlp.analyzer import JapaneseAnalyzer, _map_ginza_label


class TestRuleBasedExtraction:
    """GiNZA なしでも動作するルールベース抽出のテスト."""

    def setup_method(self):
        self.analyzer = JapaneseAnalyzer()

    def test_extract_programming_languages(self):
        text = "Python と Go のエンジニアが不足しています"
        result = self.analyzer.analyze(text)
        assert "Python" in result.technologies
        assert "Go" in result.technologies

    def test_extract_cloud_services(self):
        text = "AWS と Kubernetes の需要が急増"
        result = self.analyzer.analyze(text)
        assert "AWS" in result.technologies
        assert "Kubernetes" in result.technologies

    def test_extract_ai_terms(self):
        text = "生成AIとLLMの普及でデータサイエンティストの需要が増加"
        result = self.analyzer.analyze(text)
        assert "LLM" in result.technologies
        assert "生成AI" in result.technologies

    def test_extract_policy(self):
        text = "DX推進法と電子帳簿保存法の施行によりIT投資が加速"
        result = self.analyzer.analyze(text)
        assert "DX推進法" in result.policies
        assert "電子帳簿保存法" in result.policies

    def test_extract_multiple_categories(self):
        text = "React と AWS を使える SRE が不足。インボイス制度の影響でフリーランスが減少"
        result = self.analyzer.analyze(text)
        assert "React" in result.technologies
        assert "AWS" in result.technologies
        assert "インボイス制度" in result.policies

    def test_no_duplicates(self):
        text = "Python Python Python の需要が増加"
        result = self.analyzer.analyze(text)
        assert result.technologies.count("Python") == 1

    def test_empty_text(self):
        result = self.analyzer.analyze("")
        assert len(result.technologies) == 0
        assert len(result.policies) == 0

    def test_no_match_text(self):
        result = self.analyzer.analyze("今日は天気がいいですね")
        assert len(result.technologies) == 0
        assert len(result.policies) == 0

    def test_entity_positions(self):
        text = "Python エンジニア"
        result = self.analyzer.analyze(text)
        tech_entities = [e for e in result.entities if e.label == "TECHNOLOGY"]
        assert len(tech_entities) >= 1
        assert tech_entities[0].start == 0
        assert tech_entities[0].end == 6


class TestGinzaLabelMapping:
    def test_org_mapping(self):
        assert _map_ginza_label("ORG") == "ORGANIZATION"

    def test_money_mapping(self):
        assert _map_ginza_label("MONEY") == "QUANTITY"

    def test_law_mapping(self):
        assert _map_ginza_label("LAW") == "POLICY"

    def test_unknown_mapping(self):
        assert _map_ginza_label("UNKNOWN_LABEL") == "OTHER"
