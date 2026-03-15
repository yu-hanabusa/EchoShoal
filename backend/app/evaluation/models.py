"""評価モデル — ベンチマーク定義・期待トレンド・評価結果のデータ構造."""

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
    magnitude: float = 0.0  # 期待される変化率(%), 方向に合わせた正負
    magnitude_tolerance: float = 50.0  # 許容される乖離(%)
    description: str = ""
    start_round: int | None = None  # 部分期間の評価用
    end_round: int | None = None
    weight: float = 1.0  # スコア計算時の重み


class BenchmarkScenario(BaseModel):
    """歴史的事例に基づくベンチマークシナリオ.

    実際の過去イベントの期待される市場反応を定義する。
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
    expected_magnitude: float
    actual_change_rate: float
    direction_correct: bool
    magnitude_error: float  # 正規化された乖離
    score: float  # 0.0〜1.0


class EvaluationResult(BaseModel):
    """1つのベンチマークの評価結果."""

    benchmark_id: str
    benchmark_name: str
    trend_results: list[TrendResult]
    direction_accuracy: float  # 方向正解率 (0.0〜1.0)
    mean_magnitude_error: float  # 重み付き平均規模誤差
    correlation: float | None = None  # ピアソン相関
    overall_score: float  # 総合スコア (0.0〜1.0)
    simulation_rounds: int
    execution_time_seconds: float = 0.0


class EvaluationSuiteResult(BaseModel):
    """全ベンチマークの評価結果."""

    results: list[EvaluationResult]
    mean_overall_score: float
    mean_direction_accuracy: float
    total_benchmarks: int
    passed_benchmarks: int  # overall_score > pass_threshold
    pass_threshold: float = 0.5
    execution_time_seconds: float = 0.0
