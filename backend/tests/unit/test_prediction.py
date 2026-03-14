"""定量予測モジュールのユニットテスト."""

import pytest

from app.prediction.comparator import compare_predictions
from app.prediction.models import PredictionResult, SkillPrediction, TrendData
from app.prediction.trend import (
    compute_trend,
    linear_regression,
    moving_average,
    predict_from_results,
)
from app.simulation.models import MarketState, RoundResult, SkillCategory


def make_rounds(n: int = 6) -> list[RoundResult]:
    """AI需要が徐々に増加するテスト用ラウンド."""
    rounds = []
    for i in range(1, n + 1):
        ms = MarketState(round_number=i)
        ms.skill_demand[SkillCategory.AI_ML] = 0.5 + i * 0.03
        ms.skill_supply[SkillCategory.AI_ML] = 0.3 + i * 0.01
        ms.unit_prices[SkillCategory.AI_ML] = 85.0 + i * 1.5
        ms.ai_automation_rate = 0.05 + i * 0.01
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
    def test_generates_all_skill_predictions(self):
        rounds = make_rounds(6)
        result = predict_from_results(rounds)
        assert result.simulation_months == 6
        assert len(result.skill_predictions) == len(SkillCategory)

    def test_ai_ml_demand_increasing(self):
        rounds = make_rounds(6)
        result = predict_from_results(rounds)
        ai_pred = next(sp for sp in result.skill_predictions if sp.skill == "ai_ml")
        assert ai_pred.demand_trend.slope > 0
        assert ai_pred.predicted_demand > ai_pred.current_demand

    def test_ai_ml_price_increasing(self):
        rounds = make_rounds(6)
        result = predict_from_results(rounds)
        ai_pred = next(sp for sp in result.skill_predictions if sp.skill == "ai_ml")
        assert ai_pred.price_trend.slope > 0
        assert ai_pred.predicted_price > ai_pred.current_price

    def test_shortage_estimate_positive_when_demand_exceeds_supply(self):
        rounds = make_rounds(6)
        result = predict_from_results(rounds)
        ai_pred = next(sp for sp in result.skill_predictions if sp.skill == "ai_ml")
        # demand > supply なので不足あり
        assert ai_pred.shortage_estimate > 0

    def test_macro_predictions(self):
        rounds = make_rounds(6)
        result = predict_from_results(rounds)
        assert "unemployment_rate" in result.macro_predictions
        assert "ai_automation_rate" in result.macro_predictions
        ai_auto = result.macro_predictions["ai_automation_rate"]
        assert ai_auto.slope > 0  # 増加傾向

    def test_highlights_generated(self):
        rounds = make_rounds(12)
        result = predict_from_results(rounds)
        # 12ラウンドで変化率が十分大きければハイライトが生成される
        assert isinstance(result.highlights, list)

    def test_empty_rounds(self):
        result = predict_from_results([])
        assert result.simulation_months == 0
        assert len(result.skill_predictions) == 0


# --- シナリオ比較テスト ---

class TestComparePredictions:
    def _make_prediction(self, ai_demand: float, ai_price: float) -> PredictionResult:
        return PredictionResult(
            simulation_months=12,
            skill_predictions=[
                SkillPrediction(
                    skill="ai_ml",
                    current_demand=0.5,
                    predicted_demand=ai_demand,
                    demand_trend=TrendData(values=[0.5, ai_demand]),
                    current_price=85.0,
                    predicted_price=ai_price,
                    price_trend=TrendData(values=[85.0, ai_price]),
                    shortage_estimate=5000,
                ),
                SkillPrediction(
                    skill="legacy",
                    current_demand=0.5,
                    predicted_demand=0.3,
                    demand_trend=TrendData(values=[0.5, 0.3]),
                    current_price=55.0,
                    predicted_price=50.0,
                    price_trend=TrendData(values=[55.0, 50.0]),
                    shortage_estimate=0,
                ),
            ],
            macro_predictions={
                "ai_automation_rate": TrendData(
                    values=[0.05, 0.15], end_value=0.15, change_rate=200.0
                ),
            },
        )

    def test_compare_basic(self):
        base = self._make_prediction(0.7, 95.0)
        alt = self._make_prediction(0.9, 110.0)
        result = compare_predictions(base, alt, "ベース", "AI加速")

        assert result["base_label"] == "ベース"
        assert result["alternative_label"] == "AI加速"
        assert len(result["skill_comparison"]) == 2

    def test_demand_diff(self):
        base = self._make_prediction(0.7, 95.0)
        alt = self._make_prediction(0.9, 110.0)
        result = compare_predictions(base, alt)

        ai_diff = next(s for s in result["skill_comparison"] if s["skill"] == "ai_ml")
        assert ai_diff["demand_diff"] == pytest.approx(0.2)
        assert ai_diff["price_diff"] == pytest.approx(15.0)

    def test_most_impacted_skills(self):
        base = self._make_prediction(0.7, 95.0)
        alt = self._make_prediction(0.9, 110.0)
        result = compare_predictions(base, alt)

        assert "ai_ml" in result["most_impacted_skills"]

    def test_macro_comparison(self):
        base = self._make_prediction(0.7, 95.0)
        alt = self._make_prediction(0.9, 110.0)
        result = compare_predictions(base, alt)

        assert "ai_automation_rate" in result["macro_comparison"]
