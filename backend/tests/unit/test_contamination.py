"""LLM知識汚染テスト（anonymizer + contamination）のユニットテスト."""

from __future__ import annotations

import pytest

from app.evaluation.anonymizer import (
    AnonymizationMap,
    anonymize_documents,
    anonymize_scenario,
)
from app.evaluation.benchmarks import ANONYMIZATION_MAPS, get_benchmark, list_benchmarks
from app.evaluation.contamination import (
    ContaminationLevel,
    ContaminationResult,
    _build_contamination_result,
    _classify_contamination,
)
from app.evaluation.models import EvaluationResult, TrendResult, TrendDirection


# ═══════════════════════════════════════════════════════════════
#  匿名化マッピング
# ═══════════════════════════════════════════════════════════════


class TestAnonymizationMap:
    """匿名化マッピングの基本テスト."""

    def test_all_benchmarks_have_anonymization_maps(self) -> None:
        """全ベンチマークに匿名化マッピングが定義されている."""
        for benchmark in list_benchmarks():
            assert benchmark.id in ANONYMIZATION_MAPS, (
                f"ベンチマーク '{benchmark.id}' に匿名化マッピングがありません"
            )

    def test_service_alias_not_empty(self) -> None:
        """全マッピングのservice_aliasが空でない."""
        for bid, amap in ANONYMIZATION_MAPS.items():
            assert amap.service_alias, f"{bid}: service_aliasが空"

    def test_replacements_not_empty(self) -> None:
        """全マッピングにreplacementsが定義されている."""
        for bid, amap in ANONYMIZATION_MAPS.items():
            assert len(amap.replacements) > 0, f"{bid}: replacementsが空"

    def test_service_name_in_replacements(self) -> None:
        """各マッピングのreplacementsにサービス名の置換が含まれている."""
        for bid, amap in ANONYMIZATION_MAPS.items():
            benchmark = get_benchmark(bid)
            assert benchmark is not None
            service_name = benchmark.scenario_input.service_name
            if service_name:
                replacement_originals = [r[0] for r in amap.replacements]
                assert service_name in replacement_originals, (
                    f"{bid}: サービス名 '{service_name}' がreplacementsに含まれていません"
                )

    def test_service_alias_is_natural_name(self) -> None:
        """匿名化後の名前が自然なサービス名であること（ServiceAlphaなどではない）."""
        for bid, amap in ANONYMIZATION_MAPS.items():
            assert "ServiceAlpha" not in amap.service_alias, (
                f"{bid}: service_aliasがまだ仮名です: {amap.service_alias}"
            )


# ═══════════════════════════════════════════════════════════════
#  匿名化関数
# ═══════════════════════════════════════════════════════════════


class TestAnonymizeScenario:
    """anonymize_scenario のテスト."""

    def test_service_name_replaced(self) -> None:
        """サービス名が匿名化後に置換される."""
        benchmark = get_benchmark("slack_2014")
        assert benchmark is not None
        amap = ANONYMIZATION_MAPS["slack_2014"]

        anon = anonymize_scenario(benchmark, amap)
        assert anon.scenario_input.service_name == "TeamConnect"
        assert "Slack" not in anon.scenario_input.description

    def test_description_anonymized(self) -> None:
        """description内のサービス名が置換される."""
        benchmark = get_benchmark("chatgpt_2022")
        assert benchmark is not None
        amap = ANONYMIZATION_MAPS["chatgpt_2022"]

        anon = anonymize_scenario(benchmark, amap)
        assert "ChatGPT" not in anon.scenario_input.description
        assert "DialogAI" in anon.scenario_input.description

    def test_original_not_modified(self) -> None:
        """元のオブジェクトは変更されない."""
        benchmark = get_benchmark("slack_2014")
        assert benchmark is not None
        amap = ANONYMIZATION_MAPS["slack_2014"]
        original_name = benchmark.scenario_input.service_name

        _ = anonymize_scenario(benchmark, amap)
        assert benchmark.scenario_input.service_name == original_name

    def test_url_cleared(self) -> None:
        """匿名化時にURLが除去される."""
        benchmark = get_benchmark("slack_2014")
        assert benchmark is not None
        amap = ANONYMIZATION_MAPS["slack_2014"]

        anon = anonymize_scenario(benchmark, amap)
        assert anon.scenario_input.service_url == ""

    def test_longer_strings_replaced_first(self) -> None:
        """長い文字列が先に置換される（部分一致の問題を回避）."""
        amap = AnonymizationMap(
            service_alias="TestService",
            replacements=[
                ("GitHub Copilot", "CodeAssist"),
                ("GitHub", "DevPlatform"),
            ],
        )
        benchmark = get_benchmark("github_copilot_2022")
        assert benchmark is not None

        anon = anonymize_scenario(benchmark, amap)
        # "GitHub Copilot" が先に置換されるので "DevPlatform Copilot" にはならない
        assert "DevPlatform Copilot" not in anon.scenario_input.description


class TestAnonymizeDocuments:
    """anonymize_documents のテスト."""

    def test_documents_anonymized(self) -> None:
        """ドキュメント内のサービス名が置換される."""
        docs = [
            ("test.txt", "Slackはチームツールです。HipChatが競合です。"),
        ]
        amap = ANONYMIZATION_MAPS["slack_2014"]
        anon_docs = anonymize_documents(docs, amap)

        assert len(anon_docs) == 1
        filename, text = anon_docs[0]
        assert filename == "test.txt"
        assert "Slack" not in text
        assert "TeamConnect" in text
        assert "HipChat" not in text

    def test_empty_docs(self) -> None:
        """空のドキュメントリストを処理できる."""
        amap = ANONYMIZATION_MAPS["slack_2014"]
        result = anonymize_documents([], amap)
        assert result == []


# ═══════════════════════════════════════════════════════════════
#  汚染指標
# ═══════════════════════════════════════════════════════════════


class TestClassifyContamination:
    """_classify_contamination のテスト."""

    def test_none_level(self) -> None:
        assert _classify_contamination(0) == ContaminationLevel.NONE
        assert _classify_contamination(5) == ContaminationLevel.NONE

    def test_low_level(self) -> None:
        assert _classify_contamination(6) == ContaminationLevel.LOW
        assert _classify_contamination(15) == ContaminationLevel.LOW

    def test_moderate_level(self) -> None:
        assert _classify_contamination(16) == ContaminationLevel.MODERATE
        assert _classify_contamination(30) == ContaminationLevel.MODERATE

    def test_high_level(self) -> None:
        assert _classify_contamination(31) == ContaminationLevel.HIGH
        assert _classify_contamination(50) == ContaminationLevel.HIGH

    def test_negative_level(self) -> None:
        assert _classify_contamination(-6) == ContaminationLevel.NEGATIVE
        assert _classify_contamination(-30) == ContaminationLevel.NEGATIVE

    def test_boundary_minus_5(self) -> None:
        assert _classify_contamination(-5) == ContaminationLevel.NONE


class TestBuildContaminationResult:
    """_build_contamination_result のテスト."""

    def _make_eval(self, accuracy: float, outcome_correct: bool | None = None) -> EvaluationResult:
        return EvaluationResult(
            benchmark_id="test",
            benchmark_name="Test",
            trend_results=[],
            direction_accuracy=accuracy,
            simulation_rounds=12,
            outcome_correct=outcome_correct,
        )

    def test_basic_contamination(self) -> None:
        real = self._make_eval(0.75)
        anon = self._make_eval(0.50)
        result = _build_contamination_result("test", "Test", real, anon, 100.0)

        assert result.real_accuracy == 0.75
        assert result.anon_accuracy == 0.50
        assert result.contamination_score == 25.0  # 75% - 50% = 25pp
        assert result.contamination_level == ContaminationLevel.MODERATE

    def test_no_contamination(self) -> None:
        real = self._make_eval(0.60)
        anon = self._make_eval(0.60)
        result = _build_contamination_result("test", "Test", real, anon, 50.0)

        assert result.contamination_score == 0.0
        assert result.contamination_level == ContaminationLevel.NONE

    def test_negative_contamination(self) -> None:
        real = self._make_eval(0.25)
        anon = self._make_eval(0.75)
        result = _build_contamination_result("test", "Test", real, anon, 50.0)

        assert result.contamination_score == -50.0
        assert result.contamination_level == ContaminationLevel.NEGATIVE

    def test_zero_real_accuracy(self) -> None:
        real = self._make_eval(0.0)
        anon = self._make_eval(0.50)
        result = _build_contamination_result("test", "Test", real, anon, 50.0)

        assert result.contamination_ratio == 0.0  # 0除算回避


# ═══════════════════════════════════════════════════════════════
#  APIエンドポイント
# ═══════════════════════════════════════════════════════════════


class TestContaminationEndpoints:
    """汚染テストAPIエンドポイントのテスト."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_contamination_benchmarks(self, client) -> None:
        """汚染テスト可能ベンチマーク一覧が返される."""
        response = client.get("/api/evaluation/contamination/benchmarks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 9  # 全9シナリオ
        for item in data:
            assert item["has_anonymization_map"] is True
            assert item["anonymized_name"] is not None

    def test_contamination_run_returns_202(self, client) -> None:
        """汚染テスト実行がジョブIDを返す."""
        response = client.post("/api/evaluation/contamination/run/slack_2014")
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["type"] == "contamination_single"

    def test_contamination_run_unknown_benchmark(self, client) -> None:
        """存在しないベンチマークで404."""
        response = client.post("/api/evaluation/contamination/run/nonexistent")
        assert response.status_code == 404

    def test_contamination_run_all_returns_202(self, client) -> None:
        """全汚染テスト実行がジョブIDを返す."""
        response = client.post("/api/evaluation/contamination/run-all")
        assert response.status_code == 202
        data = response.json()
        assert data["type"] == "contamination_suite"
        assert data["benchmark_count"] == 9
