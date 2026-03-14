"""レポート生成のユニットテスト."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.reports.extractor import (
    build_report_data,
    extract_action_summary,
    extract_macro_timeline,
    extract_price_timeline,
    extract_significant_rounds,
    extract_skill_demand_timeline,
)
from app.reports.generator import ReportGenerator, _summarize_timeline
from app.reports.models import ReportSection, SimulationReport
from app.simulation.models import MarketState, RoundResult, SkillCategory


def make_rounds(n: int = 3) -> list[RoundResult]:
    """テスト用のRoundResultリストを生成."""
    rounds = []
    for i in range(1, n + 1):
        ms = MarketState(round_number=i)
        # 徐々にAI需要を上げる
        ms.skill_demand[SkillCategory.AI_ML] = 0.5 + i * 0.05
        ms.unit_prices[SkillCategory.AI_ML] = 85.0 + i * 2
        ms.unemployment_rate = 0.02 + i * 0.001
        ms.ai_automation_rate = 0.05 + i * 0.01

        actions = []
        if i % 2 == 1:
            actions.append({"agent": "TestCo", "type": "recruit", "description": "採用"})
        actions.append({"agent": "TestFL", "type": "learn_skill", "description": "学習"})

        rounds.append(RoundResult(
            round_number=i,
            market_state=ms,
            actions_taken=actions,
            events=[f"ラウンド{i}イベント"] if i == 2 else [],
        ))
    return rounds


# --- モデルテスト ---

class TestSimulationReport:
    def test_to_markdown(self):
        report = SimulationReport(
            title="テストレポート",
            scenario_description="テストシナリオ",
            executive_summary="サマリーテキスト",
            sections=[
                ReportSection(title="分析1", content="内容1"),
                ReportSection(title="分析2", content="内容2"),
            ],
            generated_at="2026-03-14T00:00:00",
        )
        md = report.to_markdown()
        assert "# テストレポート" in md
        assert "> テストシナリオ" in md
        assert "## エグゼクティブサマリー" in md
        assert "サマリーテキスト" in md
        assert "## 分析1" in md
        assert "## 分析2" in md

    def test_empty_report(self):
        report = SimulationReport()
        md = report.to_markdown()
        assert "# IT人材市場予測レポート" in md


class TestReportSection:
    def test_with_data(self):
        section = ReportSection(
            title="テスト", content="内容",
            data={"key": [1, 2, 3]},
        )
        assert section.data is not None
        assert section.data["key"] == [1, 2, 3]


# --- 指標抽出テスト ---

class TestExtractSkillDemandTimeline:
    def test_extracts_all_skills(self):
        rounds = make_rounds(3)
        timeline = extract_skill_demand_timeline(rounds)
        assert len(timeline) == len(SkillCategory)
        assert len(timeline["ai_ml"]) == 3

    def test_ai_ml_increasing(self):
        rounds = make_rounds(3)
        timeline = extract_skill_demand_timeline(rounds)
        assert timeline["ai_ml"][0] < timeline["ai_ml"][2]


class TestExtractPriceTimeline:
    def test_extracts_prices(self):
        rounds = make_rounds(3)
        timeline = extract_price_timeline(rounds)
        assert timeline["ai_ml"][0] == pytest.approx(87.0)
        assert timeline["ai_ml"][2] == pytest.approx(91.0)


class TestExtractMacroTimeline:
    def test_extracts_macro_indicators(self):
        rounds = make_rounds(3)
        timeline = extract_macro_timeline(rounds)
        assert "unemployment_rate" in timeline
        assert "ai_automation_rate" in timeline
        assert len(timeline["unemployment_rate"]) == 3

    def test_values_increasing(self):
        rounds = make_rounds(3)
        timeline = extract_macro_timeline(rounds)
        assert timeline["ai_automation_rate"][0] < timeline["ai_automation_rate"][2]


class TestExtractActionSummary:
    def test_counts_actions(self):
        rounds = make_rounds(3)
        summary = extract_action_summary(rounds)
        assert summary["learn_skill"] == 3  # 毎ラウンド
        assert summary["recruit"] == 2  # ラウンド1, 3

    def test_sorted_descending(self):
        rounds = make_rounds(3)
        summary = extract_action_summary(rounds)
        counts = list(summary.values())
        assert counts == sorted(counts, reverse=True)


class TestExtractSignificantRounds:
    def test_finds_significant_rounds(self):
        rounds = make_rounds(5)
        significant = extract_significant_rounds(rounds, top_n=2)
        assert len(significant) <= 2
        assert all("round" in s for s in significant)
        assert all("change_magnitude" in s for s in significant)

    def test_empty_rounds(self):
        assert extract_significant_rounds([]) == []

    def test_single_round(self):
        assert extract_significant_rounds(make_rounds(1)) == []


class TestBuildReportData:
    def test_builds_complete_data(self):
        rounds = make_rounds(3)
        data = build_report_data(
            rounds=rounds,
            scenario_description="テスト",
            agents_summary=[{"name": "Test"}],
        )
        assert data["total_rounds"] == 3
        assert "skill_demand_timeline" in data
        assert "price_timeline" in data
        assert "macro_timeline" in data
        assert "action_summary" in data
        assert "significant_rounds" in data
        assert data["agents"] == [{"name": "Test"}]


# --- レポート生成テスト ---

class TestSummarizeTimeline:
    def test_normal(self):
        result = _summarize_timeline([0.5, 0.6, 0.7])
        assert "0.500→0.700" in result
        assert "+" in result

    def test_empty(self):
        assert _summarize_timeline([]) == "データなし"

    def test_zero_start(self):
        result = _summarize_timeline([0.0, 0.5])
        assert "0.000→0.500" in result


class TestReportGenerator:
    @pytest.mark.asyncio
    async def test_generate_calls_llm(self):
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="分析テキスト")

        generator = ReportGenerator(llm=mock_llm)
        data = build_report_data(make_rounds(3), "テストシナリオ")
        report = await generator.generate(data)

        assert report.executive_summary == "分析テキスト"
        assert len(report.sections) == 4
        assert report.sections[0].title == "市場動向分析"
        assert report.sections[1].title == "スキル需給分析"
        assert report.sections[2].title == "業界別影響分析"
        assert report.sections[3].title == "提言"
        # summary + 4 sections = 5 LLM calls
        assert mock_llm.generate.call_count == 5

    @pytest.mark.asyncio
    async def test_report_sections_have_content(self):
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="生成されたテキスト")

        generator = ReportGenerator(llm=mock_llm)
        data = build_report_data(make_rounds(3))
        report = await generator.generate(data)

        for section in report.sections:
            assert section.content == "生成されたテキスト"
