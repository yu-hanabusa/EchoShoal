"""トークン使用量トラッキング.

LLM呼び出しごとのトークン数を記録し、タスク種別・プロバイダー・エージェント別に集計する。
コスト算出に必要なデータを提供する。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class TokenUsage:
    """1回のLLM呼び出しのトークン使用量."""

    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""  # "ollama", "claude", "openai"
    model: str = ""


@dataclass
class TokenRecord:
    """トークン使用量 + メタデータ（タスク種別、エージェント情報等）."""

    usage: TokenUsage
    task_type: str = ""
    # エージェント会話の詳細トラッキング用
    round_number: int = 0
    agent_name: str = ""


# モデル別料金テーブル (USD per 1M tokens)
# 2025年5月時点の公開価格
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Claude models
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    # OpenAI models
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    # Ollama (local, free)
    "ollama": {"input": 0.0, "output": 0.0},
}


def _estimate_cost(model: str, provider: str, input_tokens: int, output_tokens: int) -> float:
    """モデル名からコストを算出する (USD)."""
    if provider == "ollama":
        return 0.0
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        # 未知のモデルはデフォルト料金（安全側に高め）
        if provider == "claude":
            pricing = {"input": 3.0, "output": 15.0}
        elif provider == "openai":
            pricing = {"input": 2.50, "output": 10.0}
        else:
            return 0.0
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


class TokenTracker:
    """トークン使用量を集計するトラッカー.

    スレッドセーフ。シミュレーション全体で1インスタンスを使用する。
    """

    def __init__(self) -> None:
        self._records: list[TokenRecord] = []
        self._lock = threading.Lock()

    def record(
        self,
        usage: TokenUsage,
        task_type: str = "",
        round_number: int = 0,
        agent_name: str = "",
    ) -> None:
        """トークン使用量を記録する."""
        with self._lock:
            self._records.append(TokenRecord(
                usage=usage,
                task_type=task_type,
                round_number=round_number,
                agent_name=agent_name,
            ))

    def get_summary(self) -> dict[str, Any]:
        """集計結果を返す."""
        with self._lock:
            records = list(self._records)

        total_input = 0
        total_output = 0
        total_cost = 0.0
        total_calls = len(records)

        by_task: dict[str, dict[str, Any]] = {}
        by_provider: dict[str, dict[str, Any]] = {}
        agent_conversations: list[dict[str, Any]] = []

        for rec in records:
            u = rec.usage
            cost = _estimate_cost(u.model, u.provider, u.input_tokens, u.output_tokens)

            total_input += u.input_tokens
            total_output += u.output_tokens
            total_cost += cost

            # タスク種別ごと
            tt = rec.task_type or "unknown"
            if tt not in by_task:
                by_task[tt] = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "estimated_cost_usd": 0.0}
            by_task[tt]["input_tokens"] += u.input_tokens
            by_task[tt]["output_tokens"] += u.output_tokens
            by_task[tt]["calls"] += 1
            by_task[tt]["estimated_cost_usd"] = round(by_task[tt]["estimated_cost_usd"] + cost, 6)

            # プロバイダーごと
            prov = u.provider or "unknown"
            if prov not in by_provider:
                by_provider[prov] = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "estimated_cost_usd": 0.0, "model": u.model}
            by_provider[prov]["input_tokens"] += u.input_tokens
            by_provider[prov]["output_tokens"] += u.output_tokens
            by_provider[prov]["calls"] += 1
            by_provider[prov]["estimated_cost_usd"] = round(by_provider[prov]["estimated_cost_usd"] + cost, 6)

            # エージェント会話の詳細（AGENT_DECISIONでagent_nameがある場合）
            if rec.agent_name:
                agent_conversations.append({
                    "round": rec.round_number,
                    "agent": rec.agent_name,
                    "task_type": rec.task_type,
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                    "estimated_cost_usd": round(cost, 6),
                })

        return {
            "total": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "total_tokens": total_input + total_output,
                "calls": total_calls,
                "estimated_cost_usd": round(total_cost, 6),
            },
            "by_task_type": by_task,
            "by_provider": by_provider,
            "agent_conversations": agent_conversations,
        }
