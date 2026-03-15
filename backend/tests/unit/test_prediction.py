"""定量予測モジュールのユニットテスト."""

import pytest

from app.prediction.comparator import compare_predictions
from app.prediction.models import PredictionResult, DimensionPrediction, TrendData
from app.prediction.trend import (
    compute_trend,
    linear_regression,
    moving_average,
    predict_from_results,
)
from app.simulation.models import ServiceMarketState, RoundResult, MarketDimension


def make_rounds(n: int = 6) -> list[RoundResult]:
    """ユーザー獲得率が徐々に増加するテスト用ラウンド."""
    rounds = []
    for i in range(1, n + 1):
        ms = ServiceMarketState(round_number=i)
        ms.dimensions[MarketDimension.USER_ADOPTION] = 0.3 + i * 0.03
        ms.dimensions[MarketDimension.COMPETITIVE_PRESSURE] = 0.3 + i * 0.01
        ms.ai_disruption_level = 0.3 + i * 0.01
        rounds.append(RoundResult(
            round_number=i,
            market_state=ms,
            actions_taken=[],
            events=[],
        ))
    return rounds


# --- 線形回帰テスト ---

class TestLinearRegression:
    def test_increasing(self):
        slope, intercept = linear_regression([1.0, 2.0, 3.0, 4.0, 5.0])
        assert slope == pytest.approx(1.0)
        assert intercept == pytest.approx(1.0)

    def test_flat(self):
        slope, _ = linear_regression([5.0, 5.0, 5.0])
        assert slope == pytest.approx(0.0)

    def test_decreasing(self):
        slope, _ = linear_regression([10.0, 8.0, 6.0, 4.0])
        assert slope == pytest.approx(-2.0)

    def test_single_value(self):
        slope, intercept = linear_regression([42.0])
        assert slope == 0.0
        assert intercept == 42.0

    def test_two_values(self):
        slope, _ = linear_regression([0.0, 1.0])
        assert slope == pytest.approx(1.0)


class TestMovingAverage:
    def test_basic(self):
        result = moving_average([1, 2, 3, 4, 5], window=3)
        assert len(result) == 5
        assert result[2] == pytest.approx(2.0)  # (1+2+3)/3
        assert result[4] == pytest.approx(4.0)  # (3+4+5)/3

    def test_window_larger_than_data(self):
        result = moving_average([1, 2], window=5)
        assert len(result) == 2

    def test_window_1(self):
        values = [3.0, 5.0, 7.0]
        result = moving_average(values, window=1)
        assert result == values


class TestComputeTrend:
    def test_increasing_trend(self):
        trend = compute_trend([0.5, 0.6, 0.7, 0.8])
        assert trend.slope > 0
        assert trend.change_rate > 0
        assert trend.start_value == 0.5
        assert trend.end_value == 0.8
        assert len(trend.moving_avg) == 4

    def test_empty_values(self):
        trend = compute_trend([])
        assert trend.slope == 0.0
        assert trend.values == []

    def test_zero_start(self):
        trend = compute_trend([0.0, 0.1, 0.2])
        assert trend.change_rate == 0.0  # 0除算回避


# --- 予測生成テスト ---

class TestPredictFromResults:
    def test_generates_all_dimension_predictions(self):
        rounds = make_rounds(6)
        result = predict_from_results(rounds)
        assert result.simulation_months == 6
        assert len(result.dimension_predictions) == len(MarketDimension)

    def test_user_adoption_increasing(self):
        rounds = make_rounds(6)
        result = predict_from_results(rounds)
        ua_pred = next(dp for dp in result.dimension_predictions if dp.dimension == "user_adoption")
        assert ua_pred.trend.slope > 0
        assert ua_pred.predicted_value > ua_pred.current_value

    def test_macro_predictions(self):
        rounds = make_rounds(6)
        result = predict_from_results(rounds)
        assert "ai_disruption_level" in result.macro_predictions
        ai_trend = result.macro_predictions["ai_disruption_level"]
        assert ai_trend.slope > 0  # 増加傾向

    def test_highlights_generated(self):
        rounds = make_rounds(12)
        result = predict_from_results(rounds)
        # 12ラウンドで変化率が十分大きければハイライトが生成される
        assert isinstance(result.highlights, list)

    def test_empty_rounds(self):
        result = predict_from_results([])
        assert result.simulation_months == 0
        assert len(result.dimension_predictions) == 0


# --- シナリオ比較テスト ---

class TestComparePredictions:
    def _make_prediction(self, ua_value: float, cp_value: float) -> PredictionResult:
        return PredictionResult(
            simulation_months=12,
            dimension_predictions=[
                DimensionPrediction(
                    dimension="user_adoption",
                    current_value=0.3,
                    predicted_value=ua_value,
                    trend=TrendData(values=[0.3, ua_value]),
                ),
                DimensionPrediction(
                    dimension="competitive_pressure",
                    current_value=0.3,
                    predicted_value=cp_value,
                    trend=TrendData(values=[0.3, cp_value]),
                ),
            ],
            macro_predictions={
                "ai_disruption_level": TrendData(
                    values=[0.3, 0.5], end_value=0.5, change_rate=66.7
                ),
            },
        )

    def test_compare_basic(self):
        base = self._make_prediction(0.5, 0.4)
        alt = self._make_prediction(0.7, 0.6)
        result = compare_predictions(base, alt, "ベース", "高成長")

        assert result["base_label"] == "ベース"
        assert result["alternative_label"] == "高成長"
        assert len(result["dimension_comparison"]) == 2

    def test_value_diff(self):
        base = self._make_prediction(0.5, 0.4)
        alt = self._make_prediction(0.7, 0.6)
        result = compare_predictions(base, alt)

        ua_diff = next(d for d in result["dimension_comparison"] if d["dimension"] == "user_adoption")
        assert ua_diff["value_diff"] == pytest.approx(0.2)

    def test_most_impacted_dimensions(self):
        base = self._make_prediction(0.5, 0.4)
        alt = self._make_prediction(0.7, 0.6)
        result = compare_predictions(base, alt)

        assert "user_adoption" in result["most_impacted_dimensions"]

    def test_macro_comparison(self):
        base = self._make_prediction(0.5, 0.4)
        alt = self._make_prediction(0.7, 0.6)
        result = compare_predictions(base, alt)

        assert "ai_disruption_level" in result["macro_comparison"]
