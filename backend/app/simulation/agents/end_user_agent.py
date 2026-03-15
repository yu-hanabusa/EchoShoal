"""End User (エンドユーザー) agent — existing users, potential users, switchers."""

from __future__ import annotations

from app.simulation.agents.base import BaseAgent


class EndUserAgent(BaseAgent):
    """エンドユーザーエージェント.

    競合サービスの既存ユーザー、潜在ユーザー、乗り換え検討者など。
    サービスを「使う側」の視点で行動し、市場浸透に直接影響する。
    """

    def available_actions(self) -> list[str]:
        return [
            "adopt_new_service",       # 対象サービスに乗り換える
            "stay_with_current",       # 現在のサービスを継続利用
            "trial",                   # 対象サービスを試用する
            "churn",                   # 対象サービスを解約・離脱
            "recommend",               # 他者にサービスを推薦（口コミ）
            "complain",                # 不満・批判を表明
            "compare_alternatives",    # 複数サービスを比較検討
            "ignore",                  # 関心なし・無視
        ]
