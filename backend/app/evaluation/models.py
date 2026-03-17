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


class EvaluationResult(BaseModel):
    """1つのベンチマークの評価結果."""

    benchmark_id: str
    benchmark_name: str
    trend_results: list[TrendResult]
    direction_accuracy: float  # 方向正解率 (0.0〜1.0)
    simulation_rounds: int
    execution_time_seconds: float = 0.0
    dimension_timelines: list[DimensionTimeline] = Field(default_factory=list)
    agents: list[AgentRecord] = Field(default_factory=list)


class RunStatistics(BaseModel):
    """複数回実行の統計情報."""

    num_runs: int
    per_run_results: list[EvaluationResult]
    mean_direction_accuracy: float
    stddev_direction_accuracy: float
    min_direction_accuracy: float
    max_direction_accuracy: float
    per_trend_hit_rates: dict[str, float]  # metric → N回中何回方向一致したか


class EvaluationSuiteResult(BaseModel):
    """全ベンチマークの評価結果."""

    results: list[EvaluationResult]
    mean_direction_accuracy: float
    total_benchmarks: int
    passed_benchmarks: int  # direction_accuracy >= pass_threshold
    pass_threshold: float = 0.6
    execution_time_seconds: float = 0.0
