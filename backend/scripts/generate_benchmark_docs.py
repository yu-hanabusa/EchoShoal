"""ベンチマーク用補足資料の自動生成スクリプト.

各ベンチマークシナリオに対して、Claude APIを使って3種類の補足資料を生成する:
  1. {id}_readme.txt     — サービスREADME（製品概要・機能・技術・価格）
  2. {id}_market_report.txt — 市場レポート（市場規模・シェア・競合・規制）
  3. {id}_user_behavior.txt — ユーザー行動レポート（ニーズ・ペルソナ・導入プロセス）

使い方:
  cd backend
  uv run python scripts/generate_benchmark_docs.py
  uv run python scripts/generate_benchmark_docs.py --benchmark slack_2014
  uv run python scripts/generate_benchmark_docs.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.core.llm.claude_client import ClaudeClient  # noqa: E402
from app.evaluation.benchmarks import get_benchmark, list_benchmarks  # noqa: E402
from app.evaluation.models import BenchmarkScenario  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 生成先ディレクトリ
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "app" / "evaluation" / "scenarios"

# ─── プロンプトテンプレート ───

_SYSTEM_BASE = (
    "あなたは{era}のITサービス市場に詳しいビジネスアナリストです。\n"
    "以下のサービスについて、{era}当時の視点で資料を作成してください。\n"
    "当時実在した具体的な数値・企業名・出来事を含めてください。\n"
    "架空の数値は使わず、一般に知られている事実に基づいてください。\n"
    "出典が特定できる場合は末尾に出典一覧を記載してください。\n"
    "日本語で回答してください。"
)

_PROMPT_README = """
以下のサービスについて、{era}当時のサービスREADMEを作成してください。

サービス名: {service_name}
背景: {description}

以下の構成で書いてください（■ で区切り）:
■ 概要（サービスの一文説明、ターゲットユーザー）
■ 解決する課題（3-5つ）
■ 主な機能（基本機能・差別化機能を分けて）
■ 技術スタック（当時の技術）
■ 価格プラン（当時の実際の価格体系）
■ ターゲット市場（第1ターゲット・第2ターゲット）
■ チーム・資金調達（当時の状況）
■ 当時の状況と実績（ユーザー数、成長率など）
■ ロードマップ（当時の計画）
■ 競合との差別化マトリクス（テーブル形式）
"""

_PROMPT_MARKET_REPORT = """
以下のサービスが参入した市場について、{era}当時の市場レポートを作成してください。

サービス名: {service_name}
背景: {description}

以下の構成で書いてください（■ で区切り）:
■ 市場規模の推移と予測（当時の調査データ）
■ 市場シェア（主要プレイヤーのシェア）
■ 各ツール/サービスの特徴と強み（主要3-5社）
■ 規制環境（当時の規制状況）
■ 技術トレンド（当時の技術動向）
■ 資金調達環境（当時の投資動向）
■ 参入障壁（この市場特有の障壁）

末尾に出典一覧を記載してください。
当時の実際の調査会社のレポート名、ニュース記事などを参照してください。
"""

_PROMPT_USER_BEHAVIOR = """
以下のサービスのユーザー行動・ニーズレポートを{era}当時の視点で作成してください。

サービス名: {service_name}
背景: {description}

以下の構成で書いてください（■ で区切り）:
■ ユーザーの利用実態（当時の調査データ）
■ ユーザーが求める機能・改善要望
■ ツール選定時の決め手（導入企業の選定基準）
■ 業種別ユーザーペインポイント（3-4業種）
■ ユーザーペルソナ（3-4名の具体的なペルソナ）
■ 各ツールのユーザー層の特徴と乗り換え動機
■ スイッチングコスト（技術的・組織的・心理的）
■ 導入の意思決定プロセス（企業規模別）

末尾に出典一覧を記載してください。
"""


def _get_era(benchmark: BenchmarkScenario) -> str:
    """ベンチマークIDから時代を抽出する."""
    # ID例: slack_2014, zoom_2020, google_wave_2009
    parts = benchmark.id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return f"{parts[1]}年"
    # フォールバック: 名前から推測
    for word in benchmark.name.split():
        if word.isdigit() and len(word) == 4:
            return f"{word}年"
    return "当時"


async def generate_doc(
    client: ClaudeClient,
    benchmark: BenchmarkScenario,
    doc_type: str,
    prompt_template: str,
) -> str:
    """1つの資料を生成する."""
    era = _get_era(benchmark)
    system = _SYSTEM_BASE.format(era=era)
    prompt = prompt_template.format(
        era=era,
        service_name=benchmark.scenario_input.service_name,
        description=benchmark.scenario_input.description,
    )

    logger.info("  生成中: %s_%s.txt ...", benchmark.id, doc_type)
    result = await client.generate(
        prompt=prompt,
        system_prompt=system,
        temperature=0.3,  # 事実ベースなので低めに
    )
    return result


async def generate_for_benchmark(
    client: ClaudeClient,
    benchmark: BenchmarkScenario,
    output_dir: Path,
    dry_run: bool = False,
) -> None:
    """1つのベンチマークに対して3ファイルを生成する."""
    scenario_dir = output_dir / benchmark.id
    scenario_dir.mkdir(parents=True, exist_ok=True)

    doc_specs = [
        ("readme", _PROMPT_README),
        ("market_report", _PROMPT_MARKET_REPORT),
        ("user_behavior", _PROMPT_USER_BEHAVIOR),
    ]

    for doc_type, prompt_template in doc_specs:
        filepath = scenario_dir / f"{benchmark.id}_{doc_type}.txt"

        if filepath.exists():
            logger.info("  スキップ（既存）: %s", filepath.name)
            continue

        if dry_run:
            logger.info("  [DRY RUN] 生成予定: %s", filepath.name)
            continue

        content = await generate_doc(client, benchmark, doc_type, prompt_template)
        filepath.write_text(content, encoding="utf-8")
        logger.info("  保存: %s (%d文字)", filepath.name, len(content))


async def main() -> None:
    parser = argparse.ArgumentParser(description="ベンチマーク用補足資料を自動生成")
    parser.add_argument(
        "--benchmark", "-b",
        help="特定のベンチマークIDのみ生成（省略で全件）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際にはAPIを呼ばず、生成予定を表示",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存ファイルを上書き",
    )
    args = parser.parse_args()

    if not args.dry_run and not settings.claude_api_key:
        logger.error("Claude API keyが未設定です。ECHOSHOAL_CLAUDE_API_KEY を設定してください。")
        sys.exit(1)

    client = ClaudeClient()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.benchmark:
        benchmark = get_benchmark(args.benchmark)
        if benchmark is None:
            logger.error("ベンチマーク '%s' が見つかりません", args.benchmark)
            available = [b.id for b in list_benchmarks()]
            logger.info("利用可能: %s", ", ".join(available))
            sys.exit(1)
        benchmarks = [benchmark]
    else:
        benchmarks = list_benchmarks()

    logger.info("=== ベンチマーク資料生成 ===")
    logger.info("対象: %d件", len(benchmarks))
    logger.info("出力先: %s", OUTPUT_DIR)

    if args.force:
        logger.info("--force: 既存ファイルを上書きします")
        for b in benchmarks:
            scenario_dir = OUTPUT_DIR / b.id
            if scenario_dir.exists():
                for f in scenario_dir.glob("*.txt"):
                    f.unlink()

    for benchmark in benchmarks:
        logger.info("\n[%s] %s", benchmark.id, benchmark.name)
        await generate_for_benchmark(client, benchmark, OUTPUT_DIR, args.dry_run)

    logger.info("\n=== 完了 ===")

    # 結果サマリー
    total_files = sum(
        1 for b in benchmarks
        for f in (OUTPUT_DIR / b.id).glob("*.txt")
        if (OUTPUT_DIR / b.id).exists()
    )
    expected = len(benchmarks) * 3
    logger.info("生成済みファイル: %d / %d", total_files, expected)


if __name__ == "__main__":
    asyncio.run(main())
