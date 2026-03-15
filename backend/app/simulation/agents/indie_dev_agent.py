"""Individual Developer (個人開発者) agent — self-initiated products."""

from __future__ import annotations

from app.simulation.agents.base import BaseAgent


class IndieDevAgent(BaseAgent):
    """個人開発者エージェント.

    自分のプロダクトで勝負する。対象サービスの競合を作るか、
    エコシステムに参加するかなどを判断する。
    """

    def available_actions(self) -> list[str]:
        return [
            "launch_competing_product",  # 競合プロダクトをリリース
            "pivot_product",             # 既存プロダクトの方向転換
            "open_source",               # OSSとして公開
            "monetize",                  # 収益化（有料化・広告等）
            "abandon_project",           # プロジェクト放棄
            "seek_funding",              # 資金調達を目指す
            "build_community",           # ユーザーコミュニティ構築
        ]
