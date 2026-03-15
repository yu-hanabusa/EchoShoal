"""歴史的ベンチマークシナリオ — 過去のサービスリリース事例に基づく検証用シナリオ集.

各ベンチマークは:
  1. 実際に起きたサービスリリースをシナリオテキストとして定義
  2. その結果として期待されるマーケットディメンションのトレンドを列挙
  3. 参考文献URLを付与

シミュレーション結果とこれらの期待トレンドを比較することで
シミュレータの方向精度・規模精度を定量評価できる。
"""

from __future__ import annotations

from app.evaluation.models import (
    BenchmarkScenario,
    ExpectedTrend,
    TrendDirection,
)
from app.simulation.models import ScenarioInput


def _slack_2014() -> BenchmarkScenario:
    """Slack Launch (2014) — メッセージングプラットフォームがメールを破壊."""
    return BenchmarkScenario(
        id="slack_2014",
        name="Slack Launch 2014",
        description=(
            "2014年のSlack正式リリース。ビジネスコミュニケーション市場に"
            "product-led growthで参入し、既存のメールやHipChatを急速に置換。"
            "フリーミアムモデルと優れたUXにより爆発的にユーザーを獲得。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "チームコミュニケーションツールが正式リリースされる。"
                "フリーミアムモデルを採用し、直感的なUXで既存のメール・チャットツールを置換。"
                "エンジニアやスタートアップから口コミで急速に拡大。"
                "Microsoftなどの大手が競合製品で対抗する可能性。"
            ),
            num_rounds=12,
            service_name="Slack",
            target_market="ビジネスコミュニケーション",
            economic_climate=0.2,
            tech_disruption=0.3,
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                magnitude=30.0,
                description="フリーミアムモデルによる急速なユーザー獲得",
                weight=2.0,
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                magnitude=20.0,
                description="大手テック企業の競合参入",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="dimensions.market_awareness",
                direction=TrendDirection.UP,
                magnitude=25.0,
                description="口コミとメディア露出による認知度急上昇",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="dimensions.ecosystem_health",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="サードパーティ連携エコシステムの成長",
                weight=1.0,
            ),
        ],
        tags=["saas", "historical", "product_led_growth"],
    )


def _notion_vs_confluence() -> BenchmarkScenario:
    """Notion vs Confluence (2020) — PLGがエンタープライズを破壊."""
    return BenchmarkScenario(
        id="notion_vs_confluence_2020",
        name="Notion vs Confluence 2020",
        description=(
            "Notionがproduct-led growthでConfluenceのエンタープライズ市場に参入。"
            "個人利用から始まりチーム→企業へとボトムアップで浸透。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "ドキュメント・ナレッジ管理ツールがPLGモデルで市場参入。"
                "個人利用の無料プランからチーム・企業プランへの転換を狙う。"
                "既存のエンタープライズWiki（Confluence等）がシェアを持つ市場。"
                "優れたエディタUXとオールインワンの機能が差別化要因。"
            ),
            num_rounds=18,
            service_name="Notion",
            target_market="ドキュメント・ナレッジ管理",
            economic_climate=0.0,
            tech_disruption=0.2,
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                magnitude=20.0,
                description="ボトムアップ型の浸透",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="Atlassianの防衛的対応",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="dimensions.revenue_potential",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="エンタープライズ転換による収益化",
                weight=1.0,
            ),
        ],
        tags=["saas", "historical", "plg", "enterprise"],
    )


def _github_copilot_2022() -> BenchmarkScenario:
    """GitHub Copilot (2022) — AI支援開発ツールの登場."""
    return BenchmarkScenario(
        id="github_copilot_2022",
        name="GitHub Copilot 2022",
        description=(
            "GitHub Copilotの一般公開。AIペアプログラミングという新カテゴリを作り、"
            "開発者の生産性を大幅に向上。有料サブスクリプションモデル。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "AIコード補完ツールが一般開発者向けに公開される。"
                "月額制サブスクリプションモデル。コード生成の精度が高く、"
                "開発者の生産性を30-50%向上させると評価される。"
                "プラットフォーマー（GitHub/Microsoft）が提供元。"
                "Amazon CodeWhisperer等の競合も登場。"
            ),
            num_rounds=12,
            service_name="GitHub Copilot",
            target_market="AI開発支援ツール",
            economic_climate=0.0,
            tech_disruption=0.7,
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.tech_maturity",
                direction=TrendDirection.UP,
                magnitude=25.0,
                description="AI技術の急速な成熟",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                magnitude=20.0,
                description="開発者による急速な採用",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                magnitude=25.0,
                description="AmazonやGoogleの競合ツール投入",
                weight=1.2,
            ),
            ExpectedTrend(
                metric="dimensions.revenue_potential",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="サブスクリプション収益の安定化",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="ai_disruption_level",
                direction=TrendDirection.UP,
                magnitude=20.0,
                description="AI破壊度の上昇",
                weight=1.0,
            ),
        ],
        tags=["ai", "historical", "developer_tools"],
    )


def _zoom_2020() -> BenchmarkScenario:
    """Zoom (2020) — パンデミック駆動の爆発的成長."""
    return BenchmarkScenario(
        id="zoom_2020",
        name="Zoom COVID-19 2020",
        description=(
            "COVID-19パンデミックによるZoomの爆発的成長。"
            "既存のWebEx/Teamsに対してUXの簡便さで圧勝。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "ビデオ会議ツールがパンデミックにより突然必需品に。"
                "既存のWebExやSkypeに比べて圧倒的に簡単な参加体験。"
                "無料プランの40分制限がフリーミアム戦略として機能。"
                "セキュリティ問題（Zoom Bombing）が一時的に信頼を低下させる。"
                "MicrosoftがTeamsの無料化で対抗。"
            ),
            num_rounds=12,
            service_name="Zoom",
            target_market="ビデオ会議",
            economic_climate=-0.3,
            tech_disruption=0.5,
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                magnitude=40.0,
                description="パンデミック駆動の爆発的ユーザー獲得",
                weight=2.0,
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                magnitude=25.0,
                description="MicrosoftのTeams無料化攻勢",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="dimensions.regulatory_risk",
                direction=TrendDirection.UP,
                magnitude=10.0,
                description="セキュリティ懸念による規制圧力",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="dimensions.revenue_potential",
                direction=TrendDirection.UP,
                magnitude=30.0,
                description="有料プランへの大量転換",
                weight=1.5,
            ),
        ],
        tags=["saas", "historical", "pandemic", "video_conferencing"],
    )


def _chatgpt_2022() -> BenchmarkScenario:
    """ChatGPT Launch (2022) — AIサービスの爆発的採用."""
    return BenchmarkScenario(
        id="chatgpt_2022",
        name="ChatGPT Launch 2022",
        description=(
            "2022年11月のChatGPT公開。2ヶ月で1億ユーザーを突破し、"
            "AI領域への投資が爆発的に増加。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "汎用AIチャットサービスが無料で公開される。"
                "2ヶ月で1億ユーザーを突破する史上最速の成長。"
                "Google、Microsoft、Metaが競合AIサービスを急遽投入。"
                "AI規制の議論が世界中で活発化。"
                "スタートアップ投資がAI分野に集中。"
            ),
            num_rounds=12,
            service_name="ChatGPT",
            target_market="汎用AIアシスタント",
            economic_climate=0.0,
            tech_disruption=0.9,
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                magnitude=40.0,
                description="史上最速のユーザー獲得",
                weight=2.0,
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                magnitude=30.0,
                description="GAFAM全社の競合参入",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="dimensions.funding_climate",
                direction=TrendDirection.UP,
                magnitude=25.0,
                description="AI投資の爆発的増加",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="dimensions.regulatory_risk",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="AI規制議論の活発化",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="dimensions.tech_maturity",
                direction=TrendDirection.UP,
                magnitude=20.0,
                description="LLM技術の急速な進化",
                weight=1.2,
            ),
            ExpectedTrend(
                metric="ai_disruption_level",
                direction=TrendDirection.UP,
                magnitude=30.0,
                description="AI破壊度の急上昇",
                weight=1.5,
            ),
        ],
        tags=["ai", "historical", "explosive_growth"],
    )


# ─── レジストリ ───

_BENCHMARK_FACTORIES = [
    _slack_2014,
    _notion_vs_confluence,
    _github_copilot_2022,
    _zoom_2020,
    _chatgpt_2022,
]

BENCHMARKS: dict[str, BenchmarkScenario] = {
    b.id: b for b in (f() for f in _BENCHMARK_FACTORIES)
}


def get_benchmark(benchmark_id: str) -> BenchmarkScenario | None:
    """IDでベンチマークを取得する."""
    return BENCHMARKS.get(benchmark_id)


def list_benchmarks() -> list[BenchmarkScenario]:
    """全ベンチマークを返す."""
    return list(BENCHMARKS.values())
