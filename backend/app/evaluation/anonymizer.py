"""匿名化モジュール — ベンチマークのサービス名・関連固有名詞を置換する.

目的:
  LLMの学習データに含まれる歴史的サービスの結果情報によるバイアスを
  定量的に測定するためのA/Bテスト機能を提供する。

  - Run A（実名）: LLMは学習データの知識を活用できる
  - Run B（匿名）: LLMはシナリオの構造的分析のみで予測する
  - 差分 = LLMの事前知識バイアスの大きさ
"""

from __future__ import annotations

import copy
import re

from pydantic import BaseModel, Field

from app.evaluation.models import BenchmarkScenario
from app.simulation.models import ScenarioInput


class AnonymizationMap(BaseModel):
    """1つのベンチマークシナリオの匿名化マッピング.

    replacements は (実名, 匿名名) のリスト。
    長い文字列から順に置換するため、順序は重要。
    例: "GitHub Copilot" → "ServiceAlpha" は "GitHub" → "PlatformCo" より先に処理。
    """

    service_alias: str  # 匿名化後のサービス名
    replacements: list[tuple[str, str]] = Field(default_factory=list)


def _build_sorted_replacements(anon_map: AnonymizationMap) -> list[tuple[str, str]]:
    """長い文字列から先に置換するようにソートする."""
    return sorted(anon_map.replacements, key=lambda x: len(x[0]), reverse=True)


def _apply_replacements(text: str, replacements: list[tuple[str, str]]) -> str:
    """テキストに置換を適用する（大文字小文字を区別）."""
    for original, replacement in replacements:
        text = text.replace(original, replacement)
    return text


def anonymize_scenario(
    benchmark: BenchmarkScenario,
    anon_map: AnonymizationMap,
) -> BenchmarkScenario:
    """ベンチマークシナリオを匿名化したコピーを返す.

    元のオブジェクトは変更しない。
    """
    replacements = _build_sorted_replacements(anon_map)

    # ScenarioInput の匿名化
    original_input = benchmark.scenario_input
    anon_input = ScenarioInput(
        description=_apply_replacements(original_input.description, replacements),
        num_rounds=original_input.num_rounds,
        service_name=anon_map.service_alias,
        service_url="",  # URLは匿名化時に除去
        target_market=original_input.target_market,
        target_year=original_input.target_year,
    )

    # BenchmarkScenario のコピーを作成
    anon_benchmark = benchmark.model_copy(
        update={
            "scenario_input": anon_input,
            "name": _apply_replacements(benchmark.name, replacements),
            "description": _apply_replacements(benchmark.description, replacements),
        },
    )
    return anon_benchmark


def anonymize_documents(
    docs: list[tuple[str, str]],
    anon_map: AnonymizationMap,
) -> list[tuple[str, str]]:
    """シナリオ補足資料テキストを匿名化する.

    Returns:
        list of (filename, anonymized_text) tuples
    """
    replacements = _build_sorted_replacements(anon_map)
    return [
        (filename, _apply_replacements(text, replacements))
        for filename, text in docs
    ]
