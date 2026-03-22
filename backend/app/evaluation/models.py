"""評価モデル — ベンチマーク定義・期待トレンド・評価結果のデータ構造.

設計方針:
  - 恣意的な重み・規模値は使わない
  - 評価はトレンド方向の一致率のみ（UP/DOWN/STABLE）
  - 複数回実行の統計で有効性を示す
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.simulation.models import ScenarioInput


class TrendDirection(str, Enum):
    """期待されるトレンドの方向."""

    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class ExpectedOutcome(str, Enum):
    """ベンチマークの期待される成功/失敗結果."""

    SUCCESS = "success"
    FAILURE = "failure"


class ExpectedTrend(BaseModel):
    """ベンチマークが主張する単一の期待トレンド.

    metric はドット区切りのパス:
      - "dimensions.user_adoption", "dimensions.competitive_pressure"
      - "economic_sentiment", "tech_hype_level", "regulatory_pressure", "ai_disruption_level"
    """

    metric: str
    direction: TrendDirection
    description: str = ""
    start_round: int | None = None  # 部分期間の評価用
    end_round: int | None = None


class BenchmarkScenario(BaseModel):
    """歴史的事例に基づくベンチマークシナリオ.

    実際の過去イベントの期待される市場反応を定義する。
    入力はシナリオ説明文（description）のみ。
    数値パラメータで結果を誘導しない。
    """

    id: str
    name: str
    description: str
    scenario_input: ScenarioInput
    expected_trends: list[ExpectedTrend]
    expected_outcome: ExpectedOutcome | None = None  # 成功/失敗の期待結果
    tags: list[str] = Field(default_factory=list)
    reference_url: str = ""  # 参考文献URL
    reference_description: str = ""  # 参考文献の説明


class TrendResult(BaseModel):
    """単一トレンドの評価結果."""

    metric: str
    expected_direction: TrendDirection
    actual_direction: TrendDirection
    actual_change_rate: float
    direction_correct: bool


class DimensionTimeline(BaseModel):
    """1つのディメンションのラウンド推移."""

    dimension: str
    values: list[float]  # ラウンド順


class AgentRecord(BaseModel):
    """エージェントのサマリー情報."""

    name: str
    stakeholder_type: str
    actions: list[str] = Field(default_factory=list)  # 取った行動の種類


class TokenUsageSummary(BaseModel):
    """トークン使用量のサマリー（ベンチマークレポート用）."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_calls: int = 0
    estimated_cost_usd: float = 0.0
    by_task_type: dict[str, dict] = Field(default_factory=dict)
    by_provider: dict[str, dict] = Field(default_factory=dict)
    agent_conversations: list[dict] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    """1つのベンチマークの評価結果."""

    benchmark_id: str
    benchmark_name: str
    trend_results: list[TrendResult]
    direction_accuracy: float  # 方向正解率 (0.0〜1.0)
    simulation_rounds: int
    execution_time_seconds: float = 0.0
    # 成功/失敗予測の評価
    expected_outcome: str | None = None      # "success" or "failure"
    predicted_score: int | None = None       # SuccessScore.score (0-100)
    predicted_verdict: str | None = None     # SuccessScore.verdict
    outcome_correct: bool | None = None      # 予測が期待と一致したか
    combined_accuracy: float | None = None   # (direction_accuracy + outcome_accuracy) / 2
    dimension_timelines: list[DimensionTimeline] = Field(default_factory=list)
    agents: list[AgentRecord] = Field(default_factory=list)
    token_usage: TokenUsageSummary | None = None


class RunStatistics(BaseModel):
    """複数回実行の統計情報."""

    num_runs: int
    per_run_results: list[EvaluationResult]
    mean_direction_accuracy: float
    stddev_direction_accuracy: float
    min_direction_accuracy: float
    max_direction_accuracy: float
    per_trend_hit_rates: dict[str, float]  # metric → N回中何回方向一致したか
    outcome_hit_rate: float | None = None  # N回中何回outcomeが正解だったか


class ResearchData(BaseModel):
    """ベンチマーク用市場調査データ."""

    market_report: str = ""
    user_behavior: str = ""
    stakeholders: str = ""
    sources_used: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    trends_count: int = 0
    github_repos_count: int = 0
    finance_data_count: int = 0


class FullBenchmarkResult(BaseModel):
    """市場調査 → シミュレーション → 評価の一連結果."""

    benchmark_id: str
    benchmark_name: str
    research: ResearchData
    evaluation: EvaluationResult
    research_time_seconds: float = 0.0
    total_time_seconds: float = 0.0


class EvaluationSuiteResult(BaseModel):
    """全ベンチマークの評価結果."""

    results: list[EvaluationResult]
    mean_direction_accuracy: float
    total_benchmarks: int
    passed_benchmarks: int  # direction_accuracy >= pass_threshold
    pass_threshold: float = 0.6
    execution_time_seconds: float = 0.0
    mean_combined_accuracy: float | None = None
    outcome_correct_count: int = 0
    outcome_evaluated_count: int = 0
