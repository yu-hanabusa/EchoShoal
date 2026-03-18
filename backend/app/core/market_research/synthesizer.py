"""市場調査シンセサイザー — 収集データをLLMで3つの構造化レポートに合成."""

from __future__ import annotations

import logging

from app.core.llm.router import LLMRouter, TaskType
from app.core.market_research.models import CollectedMarketData

logger = logging.getLogger(__name__)


def _year_constraint(target_year: int | None) -> str:
    """対象年に関するプロンプト制約文を生成する."""
    if not target_year:
        return ""
    return (
        f"\n\n【重要な制約】\n"
        f"あなたは{target_year}年時点のアナリストです。\n"
        f"- {target_year}年末時点までに公開されている情報のみを使用してください\n"
        f"- {target_year + 1}年以降に起きた出来事、製品リリース、買収、IPO、業績は絶対に含めないでください\n"
        f"- 「その後〜になった」「将来〜する」のような未来の記述は禁止です\n"
        f"- 予測を書く場合は「{target_year}年時点での予測」として記述してください\n"
    )


def _system_prompt(role: str, target_year: int | None) -> str:
    """対象年制約付きのシステムプロンプトを生成する."""
    if target_year:
        return f"あなたは{target_year}年時点の{role}です。{target_year}年以降の情報は一切知りません。{target_year}年末までの情報のみに基づいて回答してください。"
    return f"あなたは{role}です。正確かつ定量的なレポートを作成してください。"


async def synthesize_market_report(
    llm: LLMRouter,
    service_name: str,
    description: str,
    target_year: int | None,
    collected: CollectedMarketData,
) -> str:
    """市場分析レポートを生成する."""
    data_context = _build_data_context(collected, target_year)
    year_str = f"{target_year}年時点の" if target_year else "現在の"

    prompt = (
        f"以下のサービスについて、{year_str}市場分析レポートを日本語で作成してください。\n\n"
        f"サービス名: {service_name}\n"
        f"説明: {description}\n\n"
        f"【収集された実データ】\n{data_context}\n\n"
        "以下のセクション構成で作成してください。各セクションは■で始めてください。\n"
        "実データがある場合は必ず引用し、ない場合は業界知識に基づいて推定してください。\n\n"
        "■ 市場規模の推移と予測\n"
        "TAM/SAM/SOMの推定、年間成長率(CAGR)\n\n"
        "■ 市場シェアと競合状況\n"
        "主要プレイヤーのシェア、競合の強み弱み\n\n"
        "■ 規制環境\n"
        "関連法規制、コンプライアンス要件\n\n"
        "■ 技術トレンド\n"
        "関連技術の動向、採用率\n\n"
        "■ 資金調達環境\n"
        "VC投資動向、主要ラウンド情報\n\n"
        "■ 参入障壁\n"
        "技術的障壁、ネットワーク効果、規制障壁\n"
        + _year_constraint(target_year)
    )

    try:
        return await llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_system_prompt("市場調査アナリスト", target_year),
        )
    except Exception as e:
        logger.warning("市場分析レポート生成失敗: %s", e)
        return ""


async def synthesize_user_behavior(
    llm: LLMRouter,
    service_name: str,
    description: str,
    target_year: int | None,
    collected: CollectedMarketData,
) -> str:
    """ユーザー行動レポートを生成する."""
    data_context = _build_data_context(collected, target_year)
    year_str = f"{target_year}年時点の" if target_year else "現在の"

    prompt = (
        f"以下のサービスについて、{year_str}ユーザー行動分析レポートを日本語で作成してください。\n\n"
        f"サービス名: {service_name}\n"
        f"説明: {description}\n\n"
        f"【収集された実データ】\n{data_context}\n\n"
        "以下のセクション構成で作成してください。各セクションは■で始めてください。\n\n"
        "■ ユーザーの利用実態\n"
        "利用頻度、利用シーン、主要メトリクス（DAU/MAU等）\n\n"
        "■ ユーザーが求める機能\n"
        "優先度順の機能要求リスト\n\n"
        "■ ツール選定の決め手\n"
        "意思決定要因とその重要度（%）\n\n"
        "■ 業種別ペインポイント\n"
        "4-6業種のニーズと課題\n\n"
        "■ ユーザーペルソナ\n"
        "4つの代表的ペルソナ（名前、役職、背景、動機、判断基準）\n\n"
        "■ スイッチングコスト\n"
        "技術的・組織的・心理的・金銭的コスト\n\n"
        "■ 導入の意思決定プロセス\n"
        "企業規模別のタイムラインと意思決定ステージ\n"
        + _year_constraint(target_year)
    )

    try:
        return await llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_system_prompt("ユーザーリサーチ専門家", target_year),
        )
    except Exception as e:
        logger.warning("ユーザー行動レポート生成失敗: %s", e)
        return ""


async def synthesize_stakeholders(
    llm: LLMRouter,
    service_name: str,
    description: str,
    target_year: int | None,
    collected: CollectedMarketData,
) -> str:
    """ステークホルダー分析レポートを生成する."""
    data_context = _build_data_context(collected, target_year)
    year_str = f"{target_year}年時点の" if target_year else "現在の"

    prompt = (
        f"以下のサービスについて、{year_str}ステークホルダー分析レポートを日本語で作成してください。\n\n"
        f"サービス名: {service_name}\n"
        f"説明: {description}\n\n"
        f"【収集された実データ】\n{data_context}\n\n"
        "6〜10のステークホルダーを特定し、各々について以下の形式で記述してください。\n"
        "各ステークホルダーは■で始めてください。\n\n"
        "記述項目:\n"
        "- 種別: competitor / investor / end_user / government / community / platformer のいずれか\n"
        "- 市場影響力: 1-5（5が最大）とその根拠\n"
        "- 現状満足度: 1-5（1が不満=新サービスの機会）\n"
        "- 動機: なぜこのサービスに関心を持つか\n"
        "- リソース: 従業員数、年間売上、市場ポジション\n"
        "- 予想行動: このサービスに対してどう反応するか\n"
        "- 意思決定特性: 判断速度、リスク許容度、優先事項\n\n"
        "実在の企業名・組織名を使用してください。"
        + _year_constraint(target_year)
    )

    try:
        return await llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_system_prompt("事業戦略コンサルタント", target_year),
        )
    except Exception as e:
        logger.warning("ステークホルダーレポート生成失敗: %s", e)
        return ""


def _build_data_context(
    collected: CollectedMarketData,
    target_year: int | None = None,
) -> str:
    """収集データをLLMプロンプト用テキストに変換する."""
    lines: list[str] = []
    year_note = f"（{target_year}年時点）" if target_year else ""

    if collected.trends:
        trend_note = f"（{target_year - 2}〜{target_year - 1}年、リリース前の市場動向）" if target_year else ""
        lines.append(f"【Google Trends 検索関心度{trend_note}】")
        for t in collected.trends:
            if t.interest_over_time:
                values = list(t.interest_over_time.values())
                avg = sum(values) / len(values) if values else 0
                peak = max(values) if values else 0
                lines.append(f"  {t.keyword}: 平均関心度 {avg:.0f}, ピーク {peak:.0f}")
            if t.related_queries:
                lines.append(f"    関連クエリ: {', '.join(t.related_queries[:5])}")

    if collected.github_repos:
        lines.append(f"\n【GitHub リポジトリ統計（※Star数等は現在値、参考情報）】")
        for r in collected.github_repos:
            created = f" (作成: {r.created_at[:10]})" if r.created_at else ""
            lines.append(
                f"  {r.full_name or r.repo_name}{created}: "
                f"★{r.stars:,} Fork:{r.forks:,} "
                f"Lang:{r.language}"
            )
            if r.description:
                lines.append(f"    {r.description}")

    if collected.finance_data:
        lines.append(f"\n【Yahoo Finance 企業財務{year_note}】")
        for f in collected.finance_data:
            parts = [f"  {f.company_name} ({f.ticker})"]
            if f.market_cap:
                cap_b = f.market_cap / 1e9
                parts.append(f"推定時価総額: ${cap_b:.1f}B")
            if f.stock_price:
                parts.append(f"株価: ${f.stock_price:.2f}")
            if f.sector:
                parts.append(f"セクター: {f.sector}")
            lines.append(" / ".join(parts))

    if not lines:
        lines.append("（外部データの取得に失敗しました。業界知識に基づいて推定してください）")

    return "\n".join(lines)
