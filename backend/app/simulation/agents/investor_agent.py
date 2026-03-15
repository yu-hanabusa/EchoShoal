"""Investor/VC (投資家) agent — funding, market influence."""

from __future__ import annotations

from app.simulation.agents.base import BaseAgent


class InvestorAgent(BaseAgent):
    """投資家/VCエージェント.

    対象サービスに投資するか、競合に投資するか、
    市場シグナルを発するかなどを判断する。
    """

    def available_actions(self) -> list[str]:
        return [
            "invest_seed",        # シード投資
            "invest_series",      # シリーズ投資（大型）
            "divest",             # 投資引き上げ
            "fund_competitor",    # 競合に投資
            "market_signal",      # 市場シグナル発信（評価コメント等）
            "wait_and_see",       # 様子見
            "mentor",             # メンタリング・助言
        ]
