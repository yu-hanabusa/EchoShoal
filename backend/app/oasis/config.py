"""OASIS framework configuration — Ollama backend integration.

OASISのモデル設定をEchoShoalの既存設定と統合する。
CAMEL-AIのModelFactoryを使用してOllamaバックエンドを構成。
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def create_oasis_model():
    """OASIS用のCAMEL-AIモデルインスタンスを生成する.

    EchoShoalの設定からOllamaのURLとモデル名を取得し、
    CAMEL-AIのModelFactoryで生成する。
    """
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType, ModelType

    model = ModelFactory.create(
        model_platform=ModelPlatformType.OLLAMA,
        model_type=settings.ollama_model,
        url=f"{settings.ollama_base_url}/v1",
        model_config_dict={
            "temperature": settings.oasis_temperature,
            "max_tokens": settings.oasis_max_output_tokens,
            # qwen3のthinkingモードを無効化 — <think>タグがCAMELの
            # ツール呼び出し解析を壊し、response.msg=Noneになる問題を防ぐ
            "extra_body": {"think": False},
        },
    )
    logger.info("OASISモデル作成: platform=Ollama, model=%s", settings.ollama_model)
    return model


def get_oasis_platform():
    """OASIS SNSプラットフォームタイプを取得する."""
    from oasis.social_platform.platform import Platform

    platform_name = settings.oasis_platform.lower()
    if platform_name == "twitter":
        return Platform.Twitter
    return Platform.Reddit  # デフォルト: Reddit（長文議論向き）


def get_database_path(simulation_id: str) -> str:
    """シミュレーション固有のOASIS SQLiteデータベースパスを返す."""
    import os
    import re
    # パストラバーサル防止: simulation_idはUUID形式のみ許可
    if not re.match(r"^[a-zA-Z0-9_-]+$", simulation_id):
        raise ValueError(f"Invalid simulation_id: {simulation_id}")
    base_dir = os.path.join("simulations", simulation_id)
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "oasis.db")
