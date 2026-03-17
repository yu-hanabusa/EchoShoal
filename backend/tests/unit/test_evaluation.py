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
)
from app.evaluation.models import (
    BenchmarkScenario,
    EvaluationResult,
    EvaluationSuiteResult,
    ExpectedTrend,
    RunStatistics,
    TrendDirection,
    TrendResult,
)
from app.main import app
from app.simulation.models import (
    MarketDimension,
    ServiceMarketState,
    RoundResult,
)


# ─── ヘルパー ───


def make_rounds_with_trend(
    n: int = 12,
    dim: MarketDimension = MarketDimension.USER_ADOPTION,
    dim_start: float = 0.3,
    dim_delta: float = 0.02,
    economic_sentiment_start: float = 0.5,
    economic_sentiment_delta: float = 0.0,
    ai_disruption_start: float = 0.3,
    ai_disruption_delta: float = 0.0,
    tech_hype_start: float = 0.5,
    tech_hype_delta: float = 0.0,
    regulatory_pressure_start: float = 0.3,
    regulatory_pressure_delta: float = 0.0,
) -> list[RoundResult]:
    """制御されたトレンドを持つテスト用ラウンドを生成する."""
    rounds = []
    for i in range(n):
        ms = ServiceMarketState(round_number=i + 1)
        ms.dimensions[dim] = dim_start + i * dim_delta
        ms.economic_sentiment = economic_sentiment_start + i * economic_sentiment_delta
        ms.ai_disruption_level = ai_disruption_start + i * ai_disruption_delta
        ms.tech_hype_level = tech_hype_start + i * tech_hype_delta
        ms.regulatory_pressure = regulatory_pressure_start + i * regulatory_pressure_delta
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
        et = ExpectedTrend(metric="dimensions.user_adoption", direction=TrendDirection.UP)
        assert et.start_round is None
        assert et.end_round is None
        assert et.description == ""

    def test_trend_result_construction(self):
        tr = TrendResult(
            metric="dimensions.user_adoption",
            expected_direction=TrendDirection.UP,
            actual_direction=TrendDirection.UP,
            actual_change_rate=18.0,
            direction_correct=True,
        )
        assert tr.direction_correct is True

    def test_evaluation_result_construction(self):
        er = EvaluationResult(
            benchmark_id="test",
            benchmark_name="テスト",
            trend_results=[],
            direction_accuracy=0.8,
            simulation_rounds=12,
        )
        assert 0 <= er.direction_accuracy <= 1

    def test_evaluation_suite_result(self):
        sr = EvaluationSuiteResult(
            results=[],
            mean_direction_accuracy=0.7,
            total_benchmarks=9,
            passed_benchmarks=5,
        )
        assert sr.pass_threshold == 0.6

    def test_run_statistics_construction(self):
        rs = RunStatistics(
            num_runs=5,
            per_run_results=[],
            mean_direction_accuracy=0.75,
            stddev_direction_accuracy=0.1,
            min_direction_accuracy=0.6,
            max_direction_accuracy=0.9,
            per_trend_hit_rates={"dimensions.user_adoption": 0.8},
        )
        assert rs.num_runs == 5
        assert rs.per_trend_hit_rates["dimensions.user_adoption"] == 0.8


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
        assert len(benchmarks) == 9  # 5 success + 4 failure

    def test_get_benchmark_returns_correct(self):
        b = get_benchmark("slack_2014")
        assert b is not None
        assert b.name == "Slack Launch 2014"

    def test_get_benchmark_returns_none_for_unknown(self):
        assert get_benchmark("nonexistent") is None

    def test_scenario_inputs_are_valid(self):
        """各ベンチマークのScenarioInputがバリデーションを通ること."""
        for b in list_benchmarks():
            assert len(b.scenario_input.description) >= 10
            assert 1 <= b.scenario_input.num_rounds <= 36

    def test_all_benchmarks_have_tags(self):
        for b in list_benchmarks():
            assert len(b.tags) > 0

    def test_success_benchmarks_exist(self):
        """成功事例ベンチマークが存在すること."""
        success = [b for b in list_benchmarks() if "success" in b.tags]
        assert len(success) >= 5

    def test_failure_benchmarks_exist(self):
        """失敗事例ベンチマークが存在すること."""
        failure = [b for b in list_benchmarks() if "failure" in b.tags]
        assert len(failure) >= 4

    def test_failure_benchmarks_have_down_trends(self):
        """失敗事例には少なくとも1つのDOWNトレンドが含まれること."""
        failure = [b for b in list_benchmarks() if "failure" in b.tags]
        for b in failure:
            down_trends = [
                et for et in b.expected_trends if et.direction == TrendDirection.DOWN
            ]
            assert len(down_trends) > 0, f"{b.id} has no DOWN trends"

    def test_expected_trends_have_valid_metrics(self):
        """メトリクスパスが有効なフォーマットであること."""
        valid_prefixes = {
            "dimensions",
            "economic_sentiment",
            "tech_hype_level",
            "regulatory_pressure",
            "remote_work_adoption",
            "ai_disruption_level",
        }
        for b in list_benchmarks():
            for et in b.expected_trends:
                prefix = et.metric.split(".")[0]
                assert prefix in valid_prefixes, (
                    f"{b.id}: invalid metric '{et.metric}'"
                )

    def test_no_arbitrary_numeric_params(self):
        """ScenarioInputに恣意的な数値パラメータが含まれないこと."""
        for b in list_benchmarks():
            assert not hasattr(b.scenario_input, "economic_climate")
            assert not hasattr(b.scenario_input, "tech_disruption")

    def test_no_weights_or_magnitudes(self):
        """ExpectedTrendに重みや規模値が含まれないこと."""
        for b in list_benchmarks():
            for et in b.expected_trends:
                assert not hasattr(et, "weight")
                assert not hasattr(et, "magnitude")
                assert not hasattr(et, "magnitude_tolerance")


# ─── メトリクス抽出テスト ───


class TestExtractMetricValues:
    def test_dimension_extraction(self):
        rounds = make_rounds_with_trend(n=5, dim_start=0.3, dim_delta=0.1)
        values = extract_metric_values(rounds, "dimensions.user_adoption")
        assert len(values) == 5
        assert values[0] == pytest.approx(0.3)
        assert values[4] == pytest.approx(0.7)

    def test_macro_metric_extraction(self):
        rounds = make_rounds_with_trend(
            n=5, economic_sentiment_start=0.5, economic_sentiment_delta=0.05,
        )
        values = extract_metric_values(rounds, "economic_sentiment")
        assert len(values) == 5
        assert values[0] == pytest.approx(0.5)
        assert values[4] == pytest.approx(0.7)

    def test_ai_disruption_extraction(self):
        rounds = make_rounds_with_trend(
            n=5, ai_disruption_start=0.3, ai_disruption_delta=0.05,
        )
        values = extract_metric_values(rounds, "ai_disruption_level")
        assert len(values) == 5
        assert values[0] == pytest.approx(0.3)
        assert values[4] == pytest.approx(0.5)

    def test_invalid_metric_returns_empty(self):
        rounds = make_rounds_with_trend(n=3)
        assert extract_metric_values(rounds, "invalid_metric") == []
        assert extract_metric_values(rounds, "dimensions.nonexistent") == []

    def test_round_slicing_start(self):
        rounds = make_rounds_with_trend(n=10, dim_start=0.3, dim_delta=0.01)
        values = extract_metric_values(rounds, "dimensions.user_adoption", start_round=6)
        assert len(values) == 5  # rounds 6-10

    def test_round_slicing_end(self):
        rounds = make_rounds_with_trend(n=10, dim_start=0.3, dim_delta=0.01)
        values = extract_metric_values(rounds, "dimensions.user_adoption", end_round=5)
        assert len(values) == 5  # rounds 1-5

    def test_round_slicing_range(self):
        rounds = make_rounds_with_trend(n=10, dim_start=0.3, dim_delta=0.01)
        values = extract_metric_values(
            rounds, "dimensions.user_adoption", start_round=3, end_round=7,
        )
        assert len(values) == 5  # rounds 3-7

    def test_empty_rounds(self):
        assert extract_metric_values([], "dimensions.user_adoption") == []


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
        values = [0.500, 0.501, 0.502, 0.501, 0.502, 0.501]
        assert compute_actual_direction(values) == TrendDirection.STABLE

    def test_single_value_is_stable(self):
        assert compute_actual_direction([0.5]) == TrendDirection.STABLE


# ─── 単一トレンド評価テスト ───


class TestEvaluateTrend:
    def test_correct_direction_up(self):
        """期待UP、実際UPの場合にdirection_correct=True."""
        rounds = make_rounds_with_trend(
            n=12, dim_start=0.3, dim_delta=0.02,
        )
        et = ExpectedTrend(
            metric="dimensions.user_adoption",
            direction=TrendDirection.UP,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True

    def test_wrong_direction(self):
        """期待UP、実際DOWNの場合にdirection_correct=False."""
        rounds = make_rounds_with_trend(
            n=12, dim_start=0.7, dim_delta=-0.02,
        )
        et = ExpectedTrend(
            metric="dimensions.user_adoption",
            direction=TrendDirection.UP,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is False

    def test_correct_direction_down(self):
        rounds = make_rounds_with_trend(
            n=12, dim_start=0.7, dim_delta=-0.02,
        )
        et = ExpectedTrend(
            metric="dimensions.user_adoption",
            direction=TrendDirection.DOWN,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True

    def test_stable_direction(self):
        rounds = make_rounds_with_trend(
            n=12, dim_start=0.5, dim_delta=0.0,
        )
        et = ExpectedTrend(
            metric="dimensions.user_adoption",
            direction=TrendDirection.STABLE,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True

    def test_insufficient_data(self):
        """データが不足する場合のフォールバック."""
        rounds = make_rounds_with_trend(n=1)
        et = ExpectedTrend(
            metric="dimensions.user_adoption",
            direction=TrendDirection.UP,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is False

    def test_round_slicing_applied(self):
        """start_round/end_roundが正しく適用される."""
        rounds = make_rounds_with_trend(
            n=12, dim_start=0.3, dim_delta=0.02,
        )
        et = ExpectedTrend(
            metric="dimensions.user_adoption",
            direction=TrendDirection.UP,
            start_round=1,
            end_round=6,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True

    def test_ai_disruption_metric(self):
        rounds = make_rounds_with_trend(
            n=12, ai_disruption_start=0.3, ai_disruption_delta=0.02,
        )
        et = ExpectedTrend(
            metric="ai_disruption_level",
            direction=TrendDirection.UP,
        )
        result = evaluate_trend(et, rounds)
        assert result.direction_correct is True

    def test_actual_change_rate_populated(self):
        """actual_change_rateが正しく計算されること."""
        rounds = make_rounds_with_trend(
            n=12, dim_start=0.3, dim_delta=0.02,
        )
        et = ExpectedTrend(
            metric="dimensions.user_adoption",
            direction=TrendDirection.UP,
        )
        result = evaluate_trend(et, rounds)
        assert result.actual_change_rate > 0


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
        """全トレンドが正しい方向に動く場合 → direction_accuracy=1.0."""
        rounds = make_rounds_with_trend(
            n=12,
            dim_start=0.3,
            dim_delta=0.02,
            ai_disruption_start=0.3,
            ai_disruption_delta=0.02,
        )
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
            ),
            ExpectedTrend(
                metric="ai_disruption_level",
                direction=TrendDirection.UP,
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert result.direction_accuracy == 1.0

    def test_partial_match(self):
        """一部のトレンドのみ正しい場合 → direction_accuracy=0.5."""
        rounds = make_rounds_with_trend(
            n=12,
            dim_start=0.3,
            dim_delta=0.02,  # UP
            economic_sentiment_start=0.6,
            economic_sentiment_delta=-0.02,  # DOWN
        )
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
            ),
            ExpectedTrend(
                metric="economic_sentiment",
                direction=TrendDirection.UP,  # 実際はDOWN
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert result.direction_accuracy == pytest.approx(0.5)

    def test_no_match(self):
        """全トレンドが不正解の場合 → direction_accuracy=0.0."""
        rounds = make_rounds_with_trend(
            n=12,
            dim_start=0.7,
            dim_delta=-0.02,  # DOWN
        )
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,  # 不正解
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert result.direction_accuracy == 0.0

    def test_direction_accuracy_range(self):
        """direction_accuracyは常に0〜1."""
        rounds = make_rounds_with_trend(n=12)
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert 0.0 <= result.direction_accuracy <= 1.0

    def test_all_trends_evaluated(self):
        """全トレンドが評価されること."""
        rounds = make_rounds_with_trend(
            n=12,
            dim_start=0.3, dim_delta=0.02,
            economic_sentiment_start=0.5, economic_sentiment_delta=0.01,
            ai_disruption_start=0.3, ai_disruption_delta=0.02,
        )
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
            ),
            ExpectedTrend(
                metric="economic_sentiment",
                direction=TrendDirection.UP,
            ),
            ExpectedTrend(
                metric="ai_disruption_level",
                direction=TrendDirection.UP,
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert len(result.trend_results) == 3

    def test_equal_weight_for_all_trends(self):
        """全トレンドが均等に評価されること（重みなし）."""
        rounds = make_rounds_with_trend(
            n=12,
            dim_start=0.3,
            dim_delta=0.02,  # user_adoption UP
            economic_sentiment_start=0.6,
            economic_sentiment_delta=-0.02,  # economic_sentiment DOWN
        )
        # 1/2正解 → 0.5
        benchmark = self._make_benchmark([
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,  # 正解
            ),
            ExpectedTrend(
                metric="economic_sentiment",
                direction=TrendDirection.UP,  # 不正解
            ),
        ])
        result = evaluate_benchmark(benchmark, rounds)
        assert result.direction_accuracy == pytest.approx(0.5)


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
        assert len(data) == 9
        assert all("id" in b for b in data)
        assert all("name" in b for b in data)
        assert all("expected_trend_count" in b for b in data)


class TestRunBenchmarkEndpoint:
    @pytest.mark.asyncio
    async def test_returns_202(self):
        mock_jm = make_mock_job_manager()
        with patch("app.api.routes.evaluation._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/evaluation/run/slack_2014")
        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "eval-job-id"
        assert data["benchmark_id"] == "slack_2014"

    @pytest.mark.asyncio
    async def test_unknown_benchmark_returns_404(self):
        mock_jm = make_mock_job_manager()
        with patch("app.api.routes.evaluation._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/evaluation/run/nonexistent")
        assert response.status_code == 404


class TestRunMultiEndpoint:
    @pytest.mark.asyncio
    async def test_returns_202(self):
        mock_jm = make_mock_job_manager()
        with patch("app.api.routes.evaluation._get_job_manager", return_value=mock_jm):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/evaluation/run/slack_2014/multi?num_runs=3",
                )
        assert response.status_code == 202
        data = response.json()
        assert data["num_runs"] == 3
        assert data["benchmark_id"] == "slack_2014"


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
        assert data["benchmark_count"] == 9


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
            "benchmark_id": "slack_2014",
            "evaluation": {"direction_accuracy": 0.75},
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
