"""Tests for simulation data models."""

import pytest
from pydantic import ValidationError

from app.simulation.models import (
    DocumentReference,
    MarketDimension,
    RoundResult,
    ScenarioInput,
    ServiceMarketState,
    StakeholderType,
    SuccessScore,
)


class TestServiceMarketState:
    def test_default_initialization(self):
        state = ServiceMarketState()
        assert state.round_number == 0
        assert len(state.dimensions) == len(MarketDimension)
        # All dimensions default to 0.0 (LLM initializes from scenario)
        for dim in MarketDimension:
            assert state.dimensions[dim] == 0.0

    def test_macro_defaults(self):
        state = ServiceMarketState()
        assert state.economic_sentiment == 0.0
        assert state.tech_hype_level == 0.0
        assert state.regulatory_pressure == 0.0
        assert state.ai_disruption_level == 0.0

    def test_pressure_ratio(self):
        state = ServiceMarketState()
        assert state.pressure_ratio(MarketDimension.USER_ADOPTION) == 0.0

    def test_pressure_ratio_custom_value(self):
        state = ServiceMarketState(
            dimensions={MarketDimension.USER_ADOPTION: 0.8}
        )
        assert state.pressure_ratio(MarketDimension.USER_ADOPTION) == 0.8

    def test_service_name(self):
        state = ServiceMarketState(service_name="TestService")
        assert state.service_name == "TestService"


class TestScenarioInput:
    def test_valid_scenario(self):
        scenario = ScenarioInput(
            description="新しいSaaSサービスの市場インパクトを予測するシナリオ",
            num_rounds=12,
            service_name="TestApp",
        )
        assert scenario.num_rounds == 12
        assert scenario.service_name == "TestApp"

    def test_description_too_short(self):
        with pytest.raises(ValidationError):
            ScenarioInput(description="短い")

    def test_rounds_clamped(self):
        with pytest.raises(ValidationError):
            ScenarioInput(
                description="テストシナリオの説明文です",
                num_rounds=100,
            )

    def test_default_values(self):
        scenario = ScenarioInput(description="テストシナリオの説明文です")
        assert scenario.num_rounds == 24
        assert scenario.service_name == ""
        assert scenario.service_url is None
        assert scenario.target_market is None
        assert scenario.regulatory_change is None


class TestStakeholderType:
    def test_all_types(self):
        assert len(StakeholderType) == 8

    def test_values(self):
        assert StakeholderType.ENTERPRISE.value == "enterprise"
        assert StakeholderType.FREELANCER.value == "freelancer"
        assert StakeholderType.INDIE_DEVELOPER.value == "indie_developer"
        assert StakeholderType.GOVERNMENT.value == "government"
        assert StakeholderType.INVESTOR.value == "investor"
        assert StakeholderType.PLATFORMER.value == "platformer"
        assert StakeholderType.COMMUNITY.value == "community"
        assert StakeholderType.END_USER.value == "end_user"


class TestMarketDimension:
    def test_all_dimensions(self):
        assert len(MarketDimension) == 8

    def test_values(self):
        assert MarketDimension.USER_ADOPTION.value == "user_adoption"
        assert MarketDimension.REVENUE_POTENTIAL.value == "revenue_potential"
        assert MarketDimension.TECH_MATURITY.value == "tech_maturity"


class TestRoundResult:
    def test_round_result(self):
        result = RoundResult(
            round_number=1,
            market_state=ServiceMarketState(round_number=1),
            actions_taken=[{"agent": "TestCo", "type": "adopt_service"}],
            events=["市場変動"],
        )
        assert result.round_number == 1
        assert len(result.actions_taken) == 1
        assert "市場変動" in result.events

    def test_round_result_with_document_references(self):
        doc_ref = DocumentReference(
            document_id="doc-1",
            document_name="テスト文書",
            agent_id="agent-1",
            agent_name="TestAgent",
            round_number=1,
            context_snippet="テスト文脈",
        )
        result = RoundResult(
            round_number=1,
            market_state=ServiceMarketState(round_number=1),
            document_references=[doc_ref],
        )
        assert len(result.document_references) == 1
        assert result.document_references[0].document_name == "テスト文書"


class TestSuccessScore:
    def test_default_values(self):
        score = SuccessScore()
        assert score.score == 50
        assert score.verdict == ""
        assert score.key_factors == []
        assert score.risks == []
        assert score.opportunities == []

    def test_valid_score(self):
        score = SuccessScore(
            score=85,
            verdict="成功見込み",
            key_factors=["ユーザー獲得率が高い"],
            risks=["競合参入リスク"],
            opportunities=["市場拡大の余地"],
        )
        assert score.score == 85
        assert score.verdict == "成功見込み"
        assert len(score.key_factors) == 1

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            SuccessScore(score=101)
        with pytest.raises(ValidationError):
            SuccessScore(score=-1)
