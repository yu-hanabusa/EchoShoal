"""歴史的ベンチマークシナリオ — 過去の実イベントに基づく検証用シナリオ集.

各ベンチマークは:
  1. 実際に起きた出来事をシナリオテキストとして定義
  2. その結果として期待される市場トレンドを列挙
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
from app.simulation.models import Industry, ScenarioInput, SkillCategory


def _lehman_2008() -> BenchmarkScenario:
    """リーマンショック (2008) — 世界金融危機によるIT投資の急激な縮小."""
    return BenchmarkScenario(
        id="lehman_2008",
        name="リーマンショック 2008",
        description=(
            "2008年のリーマン・ブラザーズ破綻に端を発する世界金融危機。"
            "日本のIT投資は前年比10-15%縮小し、SIer各社は新規案件の凍結・"
            "既存プロジェクトの縮小に直面。SES業界ではエンジニアの稼働率が"
            "大幅に低下し、フリーランスの案件数が激減した。"
            "一方でレガシーシステムの保守案件は比較的安定していた。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "世界的な金融危機が発生し、IT投資が前年比15%縮小。"
                "大手SIerの新規プロジェクトが凍結され、"
                "SES企業のエンジニア稼働率が急落。"
                "企業はコスト削減を最優先し、新規開発より保守に注力。"
                "フリーランスエンジニアの案件が大幅に減少。"
            ),
            num_rounds=12,
            focus_industries=[Industry.SIER, Industry.SES, Industry.FREELANCE],
            economic_shock=-0.8,
            ai_acceleration=0.0,
        ),
        expected_trends=[
            ExpectedTrend(
                metric="unemployment_rate",
                direction=TrendDirection.UP,
                magnitude=30.0,
                description="IT失業率上昇（企業の採用凍結・人員削減）",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="skill_demand.web_backend",
                direction=TrendDirection.DOWN,
                magnitude=-15.0,
                description="新規Web開発案件の凍結による需要減",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="skill_demand.web_frontend",
                direction=TrendDirection.DOWN,
                magnitude=-15.0,
                description="フロントエンド需要の減少",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="skill_demand.legacy",
                direction=TrendDirection.STABLE,
                magnitude=-3.0,
                description="レガシー保守は比較的安定",
                weight=1.2,
            ),
            ExpectedTrend(
                metric="unit_prices.web_backend",
                direction=TrendDirection.DOWN,
                magnitude=-10.0,
                description="供給過剰による単価低下",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="industry_growth.sier",
                direction=TrendDirection.DOWN,
                magnitude=-20.0,
                description="SIer業界の急激な縮小",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="industry_growth.ses",
                direction=TrendDirection.DOWN,
                magnitude=-15.0,
                description="SES稼働率低下",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="industry_growth.freelance",
                direction=TrendDirection.DOWN,
                magnitude=-20.0,
                description="フリーランス案件の激減",
                weight=1.2,
            ),
            ExpectedTrend(
                metric="overseas_outsource_rate",
                direction=TrendDirection.DOWN,
                magnitude=-5.0,
                description="オフショアも縮小（全体のIT投資減少のため）",
                weight=0.8,
            ),
        ],
        tags=["economic", "historical", "recession"],
        reference_url="https://www.ipa.go.jp/jinzai/chousa/itjinzai.html",
        reference_description="IPA IT人材白書 2009-2010: リーマンショック後のIT人材需給動向",
    )


def _covid_2020() -> BenchmarkScenario:
    """COVID-19 (2020) — パンデミックによるリモートワーク急拡大とDX加速."""
    return BenchmarkScenario(
        id="covid_2020",
        name="COVID-19パンデミック 2020",
        description=(
            "2020年のCOVID-19パンデミックにより、日本企業はリモートワークへの"
            "急激な移行を迫られた。クラウドインフラ・Webアプリ需要が急増する一方、"
            "対面が前提のSES/SIerの常駐案件は一時的に混乱。"
            "DX推進が政府方針として強化され、IT投資は二極化した。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "感染症パンデミックにより全国的な緊急事態宣言が発令。"
                "企業は急速にリモートワーク体制に移行し、"
                "クラウドインフラとWebアプリケーションへの投資が急増。"
                "対面前提のSES常駐案件は一時混乱するも、"
                "DX推進の国策により中長期的にはIT投資が増加。"
            ),
            num_rounds=12,
            focus_industries=[Industry.SIER, Industry.SES, Industry.ENTERPRISE_IT],
            focus_skills=[SkillCategory.CLOUD_INFRA, SkillCategory.WEB_FRONTEND],
            economic_shock=-0.3,
            ai_acceleration=0.2,
            policy_change="テレワーク推進・DX推進政策",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="remote_work_rate",
                direction=TrendDirection.UP,
                magnitude=50.0,
                description="リモートワーク率の急上昇（2019年の約10%→2020年の約30%超）",
                weight=2.0,
            ),
            ExpectedTrend(
                metric="skill_demand.cloud_infra",
                direction=TrendDirection.UP,
                magnitude=25.0,
                description="クラウド移行需要の急増（AWS/Azure/GCP）",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="skill_demand.web_frontend",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="社内ツールのWeb化・SaaS需要",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="skill_demand.web_backend",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="API/マイクロサービス需要の増加",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="skill_demand.security",
                direction=TrendDirection.UP,
                magnitude=20.0,
                description="リモート環境のセキュリティ需要増",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="unit_prices.cloud_infra",
                direction=TrendDirection.UP,
                magnitude=10.0,
                description="クラウド人材の単価上昇",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="unemployment_rate",
                direction=TrendDirection.UP,
                magnitude=10.0,
                description="短期的な失業率上昇",
                weight=0.8,
                end_round=6,
            ),
            ExpectedTrend(
                metric="overseas_outsource_rate",
                direction=TrendDirection.UP,
                magnitude=10.0,
                description="リモート文化がオフショア受容度を上昇",
                weight=0.8,
            ),
            ExpectedTrend(
                metric="industry_growth.enterprise_it",
                direction=TrendDirection.UP,
                magnitude=10.0,
                description="内製化・DX投資の拡大",
                weight=1.0,
            ),
        ],
        tags=["pandemic", "historical", "dx", "remote_work"],
        reference_url="https://www.soumu.go.jp/johotsusintokei/whitepaper/",
        reference_description="総務省 情報通信白書 2021: テレワーク動向とDX推進の実態",
    )


def _dx_2025_cliff() -> BenchmarkScenario:
    """2025年の崖 — 経産省DXレポートに基づくレガシー刷新の政策圧力."""
    return BenchmarkScenario(
        id="dx_2025_cliff",
        name="2025年の崖（DX推進）",
        description=(
            "2018年の経産省DXレポートで指摘された「2025年の崖」問題。"
            "基幹系レガシーシステムの老朽化・ブラックボックス化が放置された場合、"
            "2025年以降に年間最大12兆円の経済損失が生じるとの警告。"
            "これによりレガシーからクラウド・モダン技術への移行需要が急増。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "経済産業省が2025年の崖レポートを公表し、"
                "レガシーシステムの刷新が国家的課題に。"
                "大企業を中心にCOBOL/メインフレームからクラウドネイティブへの"
                "マイグレーション案件が急増。"
                "クラウド・AI人材の獲得競争が激化し、"
                "レガシー技術者は再教育プログラムの対象に。"
            ),
            num_rounds=24,
            focus_industries=[Industry.SIER, Industry.ENTERPRISE_IT],
            focus_skills=[
                SkillCategory.LEGACY,
                SkillCategory.CLOUD_INFRA,
                SkillCategory.AI_ML,
            ],
            economic_shock=0.0,
            ai_acceleration=0.3,
            policy_change="2025年の崖対応DX推進・レガシーシステム刷新義務化",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="skill_demand.legacy",
                direction=TrendDirection.DOWN,
                magnitude=-20.0,
                description="レガシー新規需要の減少（移行後は不要に）",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="skill_demand.cloud_infra",
                direction=TrendDirection.UP,
                magnitude=30.0,
                description="クラウド移行による需要急増",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="skill_demand.ai_ml",
                direction=TrendDirection.UP,
                magnitude=20.0,
                description="DXに伴うAI/データ活用の需要増",
                weight=1.2,
            ),
            ExpectedTrend(
                metric="unit_prices.legacy",
                direction=TrendDirection.DOWN,
                magnitude=-10.0,
                description="レガシー技術者の単価低下傾向",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="unit_prices.cloud_infra",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="クラウド人材の単価上昇",
                weight=1.2,
            ),
            ExpectedTrend(
                metric="unit_prices.ai_ml",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="AI人材の単価上昇",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="industry_growth.web_startup",
                direction=TrendDirection.UP,
                magnitude=10.0,
                description="DX関連のスタートアップ成長",
                weight=0.8,
            ),
            ExpectedTrend(
                metric="industry_growth.enterprise_it",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="内製化推進による企業IT部門の拡大",
                weight=1.0,
            ),
        ],
        tags=["policy", "historical", "dx", "legacy_modernization"],
        reference_url="https://www.meti.go.jp/shingikai/mono_info_service/digital_transformation/20180907_report.html",
        reference_description="経産省 DXレポート（2018）: 2025年の崖と対応策",
    )


def _abenomics_recovery() -> BenchmarkScenario:
    """アベノミクスIT投資回復 (2013-2015) — 経済刺激策によるIT市場の活況."""
    return BenchmarkScenario(
        id="abenomics_recovery",
        name="アベノミクスIT投資回復 2013-2015",
        description=(
            "2012年末に発足した第二次安倍政権の経済政策（アベノミクス）により、"
            "大規模金融緩和・財政出動・成長戦略が実施された。"
            "IT業界では金融機関のシステム更改、マイナンバー関連需要、"
            "企業のIT投資回復により人材需給が逼迫。"
            "特にSIer大手は業績回復し、SES/派遣の稼働率も改善した。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "大規模な金融緩和と財政出動により景気が回復。"
                "金融機関のシステム更改需要やマイナンバー制度対応で"
                "IT投資が大幅に増加。SIer各社の受注が回復し、"
                "IT人材の需給が逼迫し始めている。"
                "エンジニアの採用競争が激化。"
            ),
            num_rounds=12,
            focus_industries=[Industry.SIER, Industry.SES, Industry.ENTERPRISE_IT],
            economic_shock=0.5,
            ai_acceleration=0.0,
        ),
        expected_trends=[
            ExpectedTrend(
                metric="unemployment_rate",
                direction=TrendDirection.DOWN,
                magnitude=-20.0,
                description="景気回復による失業率低下",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="skill_demand.web_backend",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="Webシステム開発需要の回復",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="skill_demand.erp",
                direction=TrendDirection.UP,
                magnitude=20.0,
                description="マイナンバー・基幹系需要",
                weight=1.2,
            ),
            ExpectedTrend(
                metric="skill_demand.legacy",
                direction=TrendDirection.UP,
                magnitude=10.0,
                description="金融系レガシーシステム更改",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="unit_prices.web_backend",
                direction=TrendDirection.UP,
                magnitude=10.0,
                description="人材逼迫による単価上昇",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="unit_prices.erp",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="ERP人材の単価上昇",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="industry_growth.sier",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="SIer業界の受注回復",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="industry_growth.ses",
                direction=TrendDirection.UP,
                magnitude=10.0,
                description="SES稼働率の改善",
                weight=1.0,
            ),
        ],
        tags=["economic", "historical", "recovery"],
        reference_url="https://www.jisa.or.jp/it_info/statistics/",
        reference_description="JISA IT技術者動向調査: アベノミクス期のIT人材需給",
    )


def _ai_boom_2023() -> BenchmarkScenario:
    """生成AIブーム (2023) — ChatGPT登場に端を発するAI人材需要の爆発."""
    return BenchmarkScenario(
        id="ai_boom_2023",
        name="生成AIブーム 2023",
        description=(
            "2022年末のChatGPT公開を契機とした生成AIブーム。"
            "日本企業も生成AI導入を加速し、AI/ML人材の需要が爆発的に増加。"
            "一方で、AIによる自動化がコーディング・テスト工程を代替し始め、"
            "定型的な開発業務の需要減少懸念も。"
            "AIガバナンス・セキュリティの専門人材も新たに需要が発生。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "生成AIの登場により企業のAI導入が加速。"
                "AI/ML人材の需要が爆発的に増加し、"
                "クラウドインフラへの投資も同時に拡大。"
                "AIによる自動化で定型的な開発業務は縮小傾向。"
                "レガシーシステムのAI活用による近代化も進む。"
                "AIセキュリティ・ガバナンスの専門家需要が新規に発生。"
            ),
            num_rounds=12,
            focus_industries=[Industry.WEB_STARTUP, Industry.ENTERPRISE_IT],
            focus_skills=[SkillCategory.AI_ML, SkillCategory.CLOUD_INFRA, SkillCategory.SECURITY],
            economic_shock=0.1,
            ai_acceleration=0.8,
        ),
        expected_trends=[
            ExpectedTrend(
                metric="skill_demand.ai_ml",
                direction=TrendDirection.UP,
                magnitude=40.0,
                description="AI/ML人材需要の爆発的増加",
                weight=2.0,
            ),
            ExpectedTrend(
                metric="unit_prices.ai_ml",
                direction=TrendDirection.UP,
                magnitude=25.0,
                description="AI人材の単価高騰",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="skill_demand.cloud_infra",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="AI基盤としてのクラウド需要増",
                weight=1.2,
            ),
            ExpectedTrend(
                metric="skill_demand.security",
                direction=TrendDirection.UP,
                magnitude=15.0,
                description="AIガバナンス・セキュリティ需要",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="ai_automation_rate",
                direction=TrendDirection.UP,
                magnitude=30.0,
                description="AI自動化率の上昇",
                weight=1.5,
            ),
            ExpectedTrend(
                metric="skill_demand.legacy",
                direction=TrendDirection.DOWN,
                magnitude=-10.0,
                description="AI自動化によるレガシー需要の加速的減少",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="industry_growth.web_startup",
                direction=TrendDirection.UP,
                magnitude=20.0,
                description="AI系スタートアップの活況",
                weight=1.0,
            ),
            ExpectedTrend(
                metric="unit_prices.legacy",
                direction=TrendDirection.DOWN,
                magnitude=-5.0,
                description="レガシー技術者の相対的価値低下",
                weight=0.8,
            ),
        ],
        tags=["ai", "historical", "technology_disruption"],
        reference_url="https://www.ipa.go.jp/jinzai/chousa/itjinzai.html",
        reference_description="IPA IT人材白書 2024: 生成AI時代のIT人材需給",
    )


# ─── レジストリ ───

_BENCHMARK_FACTORIES = [
    _lehman_2008,
    _covid_2020,
    _dx_2025_cliff,
    _abenomics_recovery,
    _ai_boom_2023,
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
