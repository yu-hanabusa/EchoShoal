"""Tests for simulation data models."""

import pytest
from pydantic import ValidationError

from app.simulation.models import (
    Industry,
    MarketState,
    RoundResult,
    ScenarioInput,
    SkillCategory,
)


class TestMarketState:
    def test_default_initialization(self):
        state = MarketState()
        assert state.round_number == 0
        assert len(state.skill_demand) == len(SkillCategory)
        assert len(state.skill_supply) == len(SkillCategory)
        assert len(state.unit_prices) == len(SkillCategory)
        assert state.total_engineers == 1_090_000

    def test_demand_supply_ratio_balanced(self):
        state = MarketState()
        ratio = state.demand_supply_ratio(SkillCategory.WEB_BACKEND)
        assert ratio == 1.0  # Both default to 0.5

    def test_demand_supply_ratio_shortage(self):
        state = MarketState(
            skill_demand={SkillCategory.AI_ML: 0.9},
            skill_supply={SkillCategory.AI_ML: 0.3},
        )
        ratio = state.demand_supply_ratio(SkillCategory.AI_ML)
        assert ratio == 3.0

    def test_demand_supply_ratio_zero_supply(self):
        state = MarketState(
            skill_supply={SkillCategory.AI_ML: 0.0},
            skill_demand={SkillCategory.AI_ML: 0.5},
        )
        ratio = state.demand_supply_ratio(SkillCategory.AI_ML)
        assert ratio == float("inf")

    def test_unit_prices_default(self):
        state = MarketState()
        assert state.unit_prices[SkillCategory.AI_ML] == 85.0
        assert state.unit_prices[SkillCategory.LEGACY] == 55.0

    def test_industry_growth_default(self):
        state = MarketState()
        for industry in Industry:
            assert state.industry_growth[industry] == 0.0


class TestScenarioInput:
    def test_valid_scenario(self):
        scenario = ScenarioInput(
            description="AI技術の急速な普及によるIT人材市場への影響",
            num_rounds=12,
            focus_skills=[SkillCategory.AI_ML],
        )
        assert scenario.num_rounds == 12
        assert SkillCategory.AI_ML in scenario.focus_skills

    def test_description_too_short(self):
        with pytest.raises(ValidationError):
            ScenarioInput(description="短い")

    def test_rounds_clamped(self):
        with pytest.raises(ValidationError):
            ScenarioInput(
                description="テストシナリオの説明文です",
                num_rounds=100,
            )

    def test_ai_acceleration_bounds(self):
        with pytest.raises(ValidationError):
            ScenarioInput(
                description="テストシナリオの説明文です",
                ai_acceleration=2.0,
            )

    def test_default_values(self):
        scenario = ScenarioInput(description="テストシナリオの説明文です")
        assert scenario.num_rounds == 24
        assert scenario.ai_acceleration == 0.0
        assert scenario.economic_shock == 0.0


class TestRoundResult:
    def test_round_result(self):
        result = RoundResult(
            round_number=1,
            market_state=MarketState(round_number=1),
            actions_taken=[{"agent": "TestCo", "type": "recruit"}],
            events=["市場変動"],
        )
        assert result.round_number == 1
        assert len(result.actions_taken) == 1
        assert "市場変動" in result.events
