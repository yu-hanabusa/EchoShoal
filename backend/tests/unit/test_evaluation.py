"""評価モジュールのユニットテスト.

comparator/benchmarks/models のロジックをインフラなしでテスト。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.job_manager import JobInfo, JobManager, JobStatus
from app.evaluation.benchmarks import BENCHMARKS, get_benchmark, list_benchmarks
from app.evaluation.comparator import (
    DIRECTION_THRESHOLD,
    compute_actual_direction,
    evaluate_benchmark,
    evaluate_trend,
    extract_metric_values,
    pearson_r,
)
from app.evaluation.models import (
    BenchmarkScenario,
    EvaluationResult,
    EvaluationSuiteResult,
    ExpectedTrend,
    TrendDirection,
    TrendResult,
)
from app.main import app
from app.simulation.models import (
    Industry,
    MarketState,
    RoundResult,
    SkillCategory,
)


# ─── ヘルパー ───


def make_rounds_with_trend(
    n: int = 12,
    skill: SkillCategory = SkillCategory.AI_ML,
    demand_start: float = 0.5,
    demand_delta: float = 0.02,
    price_start: float = 85.0,
    price_delta: float = 1.0,
    unemployment_start: float = 0.02,
    unemployment_delta: float = 0.0,
    ai_auto_start: float = 0.05,
    ai_auto_delta: float = 0.0,
    remote_start: float = 0.45,
    remote_delta: float = 0.0,
    offshore_start: float = 0.15,
    offshore_delta: float = 0.0,
    industry: Industry = Industry.SIER,
    industry_growth_start: float = 0.0,
    industry_growth_delta: float = 0.0,
) -> list[RoundResult]:
    """制御されたトレンドを持つテスト用ラウンドを生成する."""
    rounds = []
    for i in range(n):
        ms = MarketState(round_number=i + 1)
        ms.skill_demand[skill] = demand_start + i * demand_delta
        ms.unit_prices[skill] = price_start + i * price_delta
        ms.unemployment_rate = unemployment_start + i * unemployment_delta
        ms.ai_automation_rate = ai_auto_start + i * ai_auto_delta
        ms.remote_work_rate = remote_start + i * remote_delta
        ms.overseas_outsource_rate = offshore_start + i * offshore_delta
        ms.industry_growth[industry] = industry_growth_start + i * industry_growth_delta
        rounds.append(RoundResult(
            round_number=i + 1,
            market_state=ms,
        ))
    return rounds


# ─── モデルテスト ───


class TestModels:
    def test_trend_direction_values(self):
        assert TrendDirection.UP == "up"
        assert TrendDirection.DOWN == "down"
        assert TrendDirection.STABLE == "stable"

    def test_expected_trend_defaults(self):
        et = ExpectedTrend(metric="skill_demand.ai_ml", direction=TrendDirection.UP)
        assert et.magnitude == 0.0
        assert et.weight == 1.0
        assert et.start_round is None
        assert et.end_round is None

    def test_trend_result_construction(self):
        tr = TrendResult(
            metric="skill_demand.ai_ml",
            expected_direction=TrendDirection.UP,
            actual_direction=TrendDirection.UP,
            expected_magnitude=20.0,
            actual_change_rate=18.0,
            direction_correct=True,
            magnitude_error=0.1,
            score=0.97,
        )
        assert tr.direction_correct is True
        assert tr.score == 0.97

    def test_evaluation_result_construction(self):
        er = EvaluationResult(
            benchmark_id="test",
            benchmark_name="テスト",
            trend_results=[],
            direction_accuracy=0.8,
            mean_magnitude_error=0.2,
            overall_score=0.7,
            simulation_rounds=12,
        )
        assert er.correlation is None
        assert 0 <= er.overall_score <= 1

    def test_evaluation_suite_result(self):
        sr = EvaluationSuiteResult(
            results=[],
            mean_overall_score=0.6,
            mean_direction_accuracy=0.7,
            total_benchmarks=5,
            passed_benchmarks=3,
        )
        assert sr.pass_threshold == 0.5


# ─── ベンチマークレジストリテスト ───


class TestBenchmarks:
    def test_all_benchmarks_have_unique_ids(self):
        benchmarks = list_benchmarks()
        ids = [b.id for b in benchmarks]
        assert len(ids) == len(set(ids))

    def test_all_benchmarks_have_expected_trends(self):
        for b in list_benchmarks():
            assert len(b.expected_trends) > 0, f"{b.id} has no expected trends"

    def test_list_benchmarks_returns_all(self):
        benchmarks = list_benchmarks()
        assert len(benchmarks) == 5

    def test_get_benchmark_returns_correct(self):
        b = get_benchmark("lehman_2008")
        assert b is not None
        assert b.name == "リーマンショック 2008"

    def test_get_benchmark_returns_none_for_unknown(self):
        assert get_benchmark("nonexistent") is None

    def test_scenario_inputs_are_valid(self):
        """各ベンチマークのScenarioInputがバリデーションを通ること."""
        for b in list_benchmarks():
            assert len(b.scenario_input.description) >= 10
            assert 1 <= b.scenario_input.num_rounds <= 36
            assert -1.0 <= b.scenario_input.economic_shock <= 1.0
            assert -1.0 <= b.scenario_input.ai_acceleration <= 1.0

    def test_all_benchmarks_have_tags(self):
        for b in list_benchmarks():
            assert len(b.tags) > 0

    def test_all_benchmarks_have_references(self):
        for b in list_benchmarks():
            assert b.reference_url != ""
            assert b.reference_description != ""

    def test_expected_trends_have_valid_metrics(self):
        """メトリクスパスが有効なフォーマットであること."""
        valid_prefixes = {
            "skill_demand", "skill_supply", "unit_prices",
            "industry_growth", "unemployment_rate",
            "ai_automation_rate", "remote_work_rate",
            "overseas_outsource_rate",
        }
        for b in list_benchmarks():
            for et in b.expected_trends:
                prefix = et.metric.split(".")[0]
                assert prefix in valid_prefixes, (
                    f"{b.id}: invalid metric '{et.metric}'"
                )


# ─── メトリクス抽出テスト ───


class TestExtractMetricValues:
    def test_skill_demand_extraction(self):
        rounds = make_rounds_with_trend(n=5, demand_start=0.3, demand_delta=0.1)
        values = extract_metric_values(rounds, "skill_demand.ai_ml")
        assert len(values) == 5
        assert values[0] == pytest.approx(0.3)
        assert values[4] == pytest.approx(0.7)

    def test_unit_prices_extraction(self):
        rounds = make_rounds_with_trend(n=5, price_start=80.0, price_delta=2.0)
        values = extract_metric_values(rounds, "unit_prices.ai_ml")
        assert values[0] == pytest.approx(80.0)
        assert values[4] == pytest.approx(88.0)

    def test_macro_metric_extraction(self):
        rounds = make_rounds_with_trend(n=5, unemployment_start=0.02, unemployment_delta=0.005)
        values = extract_metric_values(rounds, "unemployment_rate")
        assert len(values) == 5
        assert values[0] == pytest.approx(0.02)
        assert values[4] == pytest.approx(0.04)

    def test_industry_growth_extraction(self):
        rounds = make_rounds_with_trend(
            n=5, industry=Industry.SIER,
            industry_growth_start=0.0, industry_growth_delta=-0.05,
        )
        values = extract_metric_values(rounds, "industry_growth.sier")
        assert len(values) == 5
        assert values[4] == pytest.approx(-0.2)

    def test_invalid_metric_returns_empty(self):
        rounds = make_rounds_with_trend(n=3)
        assert extract_metric_values(rounds, "invalid_metric") == []
        assert extract_metric_values(rounds, "skill_demand.nonexistent") == []

    def test_round_slicing_start(self):
        rounds = make_rounds_with_trend(n=10, demand_start=0.5, demand_delta=0.01)
        values = extract_metric_values(rounds, "skill_demand.ai_ml", start_round=6)
        assert len(values) == 5  # rounds 6-10

    def test_round_slicing_end(self):
        rounds = make_rounds_with_trend(n=10, demand_start=0.5, demand_delta=0.01)
        values = extract_metric_values(rounds, "skill_demand.ai_ml", end_round=5)
        assert len(values) == 5  # rounds 1-5

    def test_round_slicing_range(self):
        rounds = make_rounds_with_trend(n=10, demand_start=0.5, demand_delta=0.01)
        values = extract_metric_values(
            rounds, "skill_demand.ai_ml", start_round=3, end_round=7,
        )
        assert len(values) == 5  # rounds 3-7

    def test_empty_rounds(self):
        assert extract_metric_values([], "skill_demand.ai_ml") == []


# ─── 方向判定テスト ───


class TestComputeActualDirection:
    def test_increasing_is_up(self):
        values = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75]
        assert compute_actual_direction(values) == TrendDirection.UP

    def test_decreasing_is_down(self):
        values = [0.8, 0.75, 0.7, 0.65, 0.6, 0.55]
        assert compute_actual_direction(values) == TrendDirection.DOWN

    def test_flat_is_stable(self):
        values = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        assert compute_actual_direction(values) == TrendDirection.STABLE

    def test_near_flat_is_stable(self):
        # 変化率がDIRECTION_THRESHOLD以内なら安定
        values = [0.500, 0.501, 0.502, 0.501, 0.502, 0.501]
        assert compute_actual_direction(values) == TrendDirection.STABLE

    def test_single_value_is_stable(self):
        assert compute_actual_direction([0.5]) == TrendDirection.STABLE


# ─── 単一トレンド評価テスト ───


class TestEvaluateTrend:
    def test_correct_direction_up_scores_high(self):
        """期待UP、実際UPの場合にスコアが高い."""
        rounds = make_rounds_with_trend(
            n=12, demand_start=0.5, demand_delta=0.02,
        )
        et = ExpectedTrend(
            metric="skill_demand.ai_ml",
            direction=TrendDirection.UP,
            magnitude=20.0,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True
        assert result.score >= 0.7

    def test_wrong_direction_scores_low(self):
        """期待UP、実際DOWNの場合にスコアが低い."""
        rounds = make_rounds_with_trend(
            n=12, demand_start=0.7, demand_delta=-0.02,
        )
        et = ExpectedTrend(
            metric="skill_demand.ai_ml",
            direction=TrendDirection.UP,
            magnitude=20.0,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is False
        assert result.score < 0.5

    def test_correct_direction_down(self):
        rounds = make_rounds_with_trend(
            n=12, demand_start=0.7, demand_delta=-0.02,
        )
        et = ExpectedTrend(
            metric="skill_demand.ai_ml",
            direction=TrendDirection.DOWN,
            magnitude=-20.0,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True

    def test_stable_direction(self):
        rounds = make_rounds_with_trend(
            n=12, demand_start=0.5, demand_delta=0.0,
        )
        et = ExpectedTrend(
            metric="skill_demand.ai_ml",
            direction=TrendDirection.STABLE,
            magnitude=0.0,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True

    def test_magnitude_close_scores_higher(self):
        """規模が近いほどスコアが高い."""
        rounds = make_rounds_with_trend(
            n=12, demand_start=0.5, demand_delta=0.02,
        )
        et_close = ExpectedTrend(
            metric="skill_demand.ai_ml",
            direction=TrendDirection.UP,
            magnitude=44.0,  # 実際の変化率に近い
        )
        et_far = ExpectedTrend(
            metric="skill_demand.ai_ml",
            direction=TrendDirection.UP,
            magnitude=200.0,  # 実際から大きく外れる
        )
        result_close = evaluate_trend(et_close, rounds)
        result_far = evaluate_trend(et_far, rounds)
        assert result_close.score >= result_far.score

    def test_insufficient_data(self):
        """データが不足する場合のフォールバック."""
        rounds = make_rounds_with_trend(n=1)
        et = ExpectedTrend(
            metric="skill_demand.ai_ml",
            direction=TrendDirection.UP,
            magnitude=20.0,
        )
        result = evaluate_trend(et, rounds)
        assert result.score == 0.0

    def test_round_slicing_applied(self):
        """start_round/end_roundが正しく適用される."""
        rounds = make_rounds_with_trend(
            n=12, demand_start=0.5, demand_delta=0.02,
        )
        et = ExpectedTrend(
            metric="skill_demand.ai_ml",
            direction=TrendDirection.UP,
            magnitude=20.0,
            start_round=1,
            end_round=6,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True

    def test_unemployment_metric(self):
        rounds = make_rounds_with_trend(
            n=12, unemployment_start=0.02, unemployment_delta=0.003,
        )
        et = ExpectedTrend(
            metric="unemployment_rate",
            direction=TrendDirection.UP,
            magnitude=30.0,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True


# ─── ピアソン相関テスト ───


class TestPearsonR:
    def test_perfect_positive(self):
        r = pearson_r([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert r is not None
        assert r == pytest.approx(1.0)

    def test_perfect_negative(self):
        r = pearson_r([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])
        assert r is not None
        assert r == pytest.approx(-1.0)

    def test_no_correlation(self):
        r = pearson_r([1, 2, 3, 4, 5], [2, 4, 1, 5, 3])
        assert r is not None
        assert -0.5 < r < 0.5

    def test_insufficient_data(self):
        assert pearson_r([1, 2], [3, 4]) is None
        assert pearson_r([1], [2]) is None

    def test_zero_variance(self):
        assert pearson_r([5, 5, 5], [1, 2, 3]) is None

    def test_mismatched_lengths(self):
        assert pearson_r([1, 2, 3], [1, 2]) is None


# ─── ベンチマーク全体評価テスト ───


class TestEvaluateBenchmark:
    def _make_benchmark(
        self,
        trends: list[ExpectedTrend],
    ) -> BenchmarkScenario:
        from app.simulation.models import ScenarioInput
        return BenchmarkScenario(
            id="test_bench",
            name="テストベンチマーク",
            description="テスト用",
            scenario_input=ScenarioInput(
                description="テスト用シナリオ（10文字以上必要）",
                num_rounds=12,
            ),
            expected_trends=trends,
        )

    def test_perfect_match(self):
        """全トレンドが正しい方向に動く場合."""
        rounds = make_rounds_with_trend(
            n=12,
            demand_start=0.5,
            demand_delta=0.02,
            unemployment_start=0.02,
            unemployment_delta=0.003,
        )
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="skill_demand.ai_ml",
                direction=TrendDirection.UP,
                magnitude=20.0,
            ),
            ExpectedTrend(
                metric="unemployment_rate",
                direction=TrendDirection.UP,
                magnitude=30.0,
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert result.direction_accuracy == 1.0
        assert result.overall_score >= 0.6

    def test_partial_match(self):
        """一部のトレンドのみ正しい場合."""
        rounds = make_rounds_with_trend(
            n=12,
            demand_start=0.5,
            demand_delta=0.02,  # UP
            unemployment_start=0.05,
            unemployment_delta=-0.002,  # DOWN
        )
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="skill_demand.ai_ml",
                direction=TrendDirection.UP,
                magnitude=20.0,
                weight=1.0,
            ),
            ExpectedTrend(
                metric="unemployment_rate",
                direction=TrendDirection.UP,  # 実際はDOWN
                magnitude=30.0,
                weight=1.0,
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert 0.0 < result.direction_accuracy < 1.0

    def test_overall_score_range(self):
        """スコアは常に0〜1."""
        rounds = make_rounds_with_trend(n=12)
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="skill_demand.ai_ml",
                direction=TrendDirection.UP,
                magnitude=20.0,
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert 0.0 <= result.overall_score <= 1.0

    def test_correlation_computed_with_enough_trends(self):
        """3つ以上のトレンドがある場合に相関が計算される."""
        rounds = make_rounds_with_trend(
            n=12,
            demand_start=0.5, demand_delta=0.02,
            price_start=85.0, price_delta=1.0,
            unemployment_start=0.02, unemployment_delta=0.003,
        )
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="skill_demand.ai_ml",
                direction=TrendDirection.UP,
                magnitude=20.0,
            ),
            ExpectedTrend(
                metric="unit_prices.ai_ml",
                direction=TrendDirection.UP,
                magnitude=15.0,
            ),
            ExpectedTrend(
                metric="unemployment_rate",
                direction=TrendDirection.UP,
                magnitude=30.0,
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert result.correlation is not None

    def test_weighted_scoring(self):
        """重みが高いトレンドが正しい場合、スコアが高くなる."""
        rounds = make_rounds_with_trend(
            n=12,
            demand_start=0.5,
            demand_delta=0.02,  # AI_ML demand UP
            unemployment_start=0.05,
            unemployment_delta=-0.002,  # unemployment DOWN
        )
        # 重要なトレンド(AI_ML UP)が正解、低重要(unemployment UP)が不正解
        benchmark_high_weight = self._make_benchmark([
            ExpectedTrend(
                metric="skill_demand.ai_ml",
                direction=TrendDirection.UP,
                magnitude=20.0,
                weight=3.0,  # 高い重み
            ),
            ExpectedTrend(
                metric="unemployment_rate",
                direction=TrendDirection.UP,  # 不正解
                magnitude=30.0,
                weight=1.0,
            ),
        ])
        # 逆: 低重要トレンドが正解、高重要が不正解
        benchmark_low_weight = self._make_benchmark([
            ExpectedTrend(
                metric="skill_demand.ai_ml",
                direction=TrendDirection.UP,
                magnitude=20.0,
                weight=1.0,
            ),
            ExpectedTrend(
                metric="unemployment_rate",
                direction=TrendDirection.UP,  # 不正解
                magnitude=30.0,
                weight=3.0,  # 高い重み
            ),
        ])
        result_high = evaluate_benchmark(benchmark_high_weight, rounds)
        result_low = evaluate_benchmark(benchmark_low_weight, rounds)
        assert result_high.direction_accuracy > result_low.direction_accuracy


# ─── APIエンドポイントテスト ───


def make_mock_job_manager() -> MagicMock:
    mock = MagicMock(spec=JobManager)
    mock.create_job = AsyncMock(return_value="eval-job-id")
    mock.get_job_info = AsyncMock()
    mock.get_result = AsyncMock()
    mock.save_scenario = AsyncMock()
    return mock


class TestBenchmarksEndpoint:
    @pytest.mark.asyncio
    async def test_list_benchmarks(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/evaluation/benchmarks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        assert all("id" in b for b in data)
        assert all("name" in b for b in data)
        assert all("expected_trend_count" in b for b in data)
        assert all("reference_url" in b for b in data)


class TestRunBenchmarkEndpoint:
    @pytest.mark.asyncio
    async def test_returns_202(self):
        mock_jm = make_mock_job_manager()
        with patch("app.api.routes.evaluation._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/evaluation/run/lehman_2008")
        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "eval-job-id"
        assert data["benchmark_id"] == "lehman_2008"

    @pytest.mark.asyncio
    async def test_unknown_benchmark_returns_404(self):
        mock_jm = make_mock_job_manager()
        with patch("app.api.routes.evaluation._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/evaluation/run/nonexistent")
        assert response.status_code == 404


class TestRunAllEndpoint:
    @pytest.mark.asyncio
    async def test_returns_202(self):
        mock_jm = make_mock_job_manager()
        with patch("app.api.routes.evaluation._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/evaluation/run-all")
        assert response.status_code == 202
        data = response.json()
        assert data["benchmark_count"] == 5


class TestGetResultEndpoint:
    @pytest.mark.asyncio
    async def test_returns_completed_result(self):
        mock_jm = make_mock_job_manager()
        mock_jm.get_job_info = AsyncMock(return_value=JobInfo(
            job_id="eval-job-id",
            status=JobStatus.COMPLETED,
            created_at="2026-01-01",
        ))
        mock_jm.get_result = AsyncMock(return_value={
            "type": "evaluation_single",
            "benchmark_id": "lehman_2008",
            "evaluation": {"overall_score": 0.75},
        })
        with patch("app.api.routes.evaluation._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/evaluation/eval-job-id/result")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "result" in data

    @pytest.mark.asyncio
    async def test_returns_404_for_missing(self):
        mock_jm = make_mock_job_manager()
        mock_jm.get_job_info = AsyncMock(return_value=None)
        with patch("app.api.routes.evaluation._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/evaluation/nonexistent/result")
        assert response.status_code == 404
