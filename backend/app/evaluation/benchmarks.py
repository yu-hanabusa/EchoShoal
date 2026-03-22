"""歴史的ベンチマークシナリオ — 過去のサービスリリース事例に基づく検証用シナリオ集.

設計方針:
  - 入力はシナリオ説明文（description）のみ。数値パラメータで結果を誘導しない。
  - descriptionには「リリース時点で分かっている情報のみ」を記載する。
    結果（成功/失敗、ユーザー数の推移等）は含めない。
    LLMが「答え合わせ」ではなく「予測」を行えるようにする。
  - 期待トレンドは方向（UP/DOWN/STABLE）のみ。重みや規模値は使わない。
  - 成功事例と失敗事例の両方を含め、シミュレータの有効性を多角的に検証する。
"""

from __future__ import annotations

from app.evaluation.models import (
    BenchmarkScenario,
    ExpectedOutcome,
    ExpectedTrend,
    TrendDirection,
)
from app.simulation.models import ScenarioInput


# ═══════════════════════════════════════════════════════════════
#  成功事例
# ═══════════════════════════════════════════════════════════════


def _slack_2014() -> BenchmarkScenario:
    """Slack Launch (2014) — メッセージングプラットフォームがメールを破壊."""
    return BenchmarkScenario(
        id="slack_2014",
        name="Slack Launch 2014",
        description=(
            "2014年のSlack正式リリース。ビジネスコミュニケーション市場に"
            "product-led growthで参入。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "2014年2月、チームコミュニケーションツール「Slack」が正式リリースされる。"
                "Flickr共同創業者のStewart Butterfieldが率いるTiny Speck社が開発。"
                "元々はオンラインゲーム「Glitch」の社内ツールとして生まれた。"
                "フリーミアムモデルを採用し、無料プランでメッセージ履歴1万件、連携5つまで。"
                "有料プランは月額6.67ドル/ユーザー。"
                "チャンネルベースのメッセージング、全文検索、80以上のサードパーティ連携が特徴。"
                "主なターゲットはテクノロジー企業とスタートアップの開発チーム。"
                "競合はHipChat（Atlassian、月額2ドル）、Campfire（37signals）、"
                "Microsoft Lync、Yammer。ビジネスメール市場はRaticati Groupによると"
                "1人あたり1日121通のメールが処理されている状況。"
                "2014年4月にシリーズC 4,270万ドルを調達済み。"
                "SaaS市場は年25-30%成長中、VC投資環境は好況。"
            ),
            num_rounds=12,
            service_name="Slack",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                description="フリーミアムモデルによるユーザー獲得",
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                description="大手テック企業の競合参入",
            ),
            ExpectedTrend(
                metric="dimensions.market_awareness",
                direction=TrendDirection.UP,
                description="口コミとメディア露出による認知度上昇",
            ),
            ExpectedTrend(
                metric="dimensions.ecosystem_health",
                direction=TrendDirection.UP,
                description="サードパーティ連携エコシステムの成長",
            ),
        ],
        expected_outcome=ExpectedOutcome.SUCCESS,
        tags=["saas", "success", "product_led_growth"],
    )


def _notion_vs_confluence() -> BenchmarkScenario:
    """Notion vs Confluence (2020) — PLGがエンタープライズを破壊."""
    return BenchmarkScenario(
        id="notion_vs_confluence_2020",
        name="Notion vs Confluence 2020",
        description=(
            "Notionがproduct-led growthでエンタープライズWiki市場に参入。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "2020年、ドキュメント・ナレッジ管理ツール「Notion」が本格的に市場拡大を開始。"
                "個人利用の無料プランからチーム・企業プランへの転換を狙うPLGモデル。"
                "Wiki、タスク管理、データベースを統合したオールインワンワークスペース。"
                "既存のエンタープライズWiki市場はAtlassianのConfluenceが支配的。"
                "2020年4月にシリーズBで5,000万ドルを調達、評価額20億ドル。"
                "競合はConfluence、Coda、Roam Research、Google Docs。"
                "COVID-19によりリモートワークが急増し、コラボレーションツールの需要が拡大中。"
                "個人開発者やデザイナーの間で評判が広がりつつある。"
            ),
            num_rounds=18,
            service_name="Notion",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                description="ボトムアップ型の浸透",
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                description="Atlassianの防衛的対応",
            ),
            ExpectedTrend(
                metric="dimensions.revenue_potential",
                direction=TrendDirection.UP,
                description="エンタープライズ転換による収益化",
            ),
        ],
        expected_outcome=ExpectedOutcome.SUCCESS,
        tags=["saas", "success", "plg", "enterprise"],
    )


def _github_copilot_2022() -> BenchmarkScenario:
    """GitHub Copilot (2022) — AI支援開発ツールの登場."""
    return BenchmarkScenario(
        id="github_copilot_2022",
        name="GitHub Copilot 2022",
        description=(
            "GitHub CopilotがAIペアプログラミングという新カテゴリで公開。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "2022年6月、GitHub（Microsoft傘下）がAIコード補完ツール「GitHub Copilot」を"
                "一般開発者向けに公開する。月額10ドルのサブスクリプションモデル。"
                "OpenAI Codexを基盤とし、IDEに統合してリアルタイムにコードを提案する。"
                "テクニカルプレビュー期間中に120万人以上の開発者が利用。"
                "プラットフォーマー（GitHub/Microsoft）が提供元であり、VS Code統合が強力。"
                "競合としてAmazon CodeWhisperer（無料）、Tabnine、Kiteが存在。"
                "著作権やオープンソースライセンスに関する法的懸念が浮上している。"
                "世界の開発者数は約2,700万人（Evans Data Corporation調べ）。"
                "AI技術の進歩が加速中でLLMの性能向上が急速。"
            ),
            num_rounds=12,
            service_name="GitHub Copilot",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.tech_maturity",
                direction=TrendDirection.UP,
                description="AI技術の急速な成熟",
            ),
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                description="開発者による採用",
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                description="AmazonやGoogleの競合ツール投入",
            ),
            ExpectedTrend(
                metric="dimensions.regulatory_risk",
                direction=TrendDirection.UP,
                description="著作権・OSSライセンスに関する法的懸念の高まり",
            ),
            ExpectedTrend(
                metric="ai_disruption_level",
                direction=TrendDirection.UP,
                description="AI破壊度の上昇",
            ),
        ],
        expected_outcome=ExpectedOutcome.SUCCESS,
        tags=["ai", "success", "developer_tools"],
    )


def _zoom_2020() -> BenchmarkScenario:
    """Zoom (2020) — パンデミック駆動の成長."""
    return BenchmarkScenario(
        id="zoom_2020",
        name="Zoom COVID-19 2020",
        description=(
            "COVID-19パンデミック下でのZoomのビデオ会議市場での展開。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "2020年初頭、COVID-19パンデミックが世界的に拡大し、"
                "リモートワークへの移行が急速に進む。"
                "ビデオ会議ツール「Zoom」は2019年にIPO済みで、"
                "2019年12月時点のDAP（1日の会議参加者数）は約1,000万人。"
                "シンプルな参加体験（ブラウザからワンクリック参加）が特徴。"
                "無料プランは40分制限、有料プランは月額14.99ドル/ホスト。"
                "競合はMicrosoft Teams（Office 365バンドル）、Cisco WebEx、"
                "Google Meet、Skype。Teamsは既に企業市場で広く導入済み。"
                "Zoom Bombingというセキュリティ問題が報告され始めている。"
                "パンデミックにより経済全体は後退局面。"
            ),
            num_rounds=12,
            service_name="Zoom",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                description="パンデミック駆動のユーザー獲得",
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                description="Microsoft Teams・Google Meetの急速な対抗措置",
            ),
            ExpectedTrend(
                metric="dimensions.market_awareness",
                direction=TrendDirection.UP,
                description="パンデミックによる認知度の急上昇",
            ),
        ],
        expected_outcome=ExpectedOutcome.SUCCESS,
        tags=["saas", "success", "pandemic", "video_conferencing"],
    )


def _chatgpt_2022() -> BenchmarkScenario:
    """ChatGPT Launch (2022) — AIサービスの公開."""
    return BenchmarkScenario(
        id="chatgpt_2022",
        name="ChatGPT Launch 2022",
        description=(
            "OpenAIが汎用AIチャットサービスを無料で公開。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "2022年11月、OpenAIが汎用AIチャットサービス「ChatGPT」を無料で公開する。"
                "GPT-3.5をベースに、RLHF（人間のフィードバックによる強化学習）で対話に最適化。"
                "テキスト生成、質問応答、コード生成、翻訳など多用途に対応。"
                "OpenAIはMicrosoftから100億ドルの投資を受けている。"
                "Google、Meta、Amazonなど大手テック企業もAI研究に巨額投資中。"
                "生成AI市場はGrand View Researchによると2022年時点で約100億ドル規模。"
                "AI倫理・規制の議論がEUを中心に進行中（EU AI Act草案）。"
                "既存のAIアシスタント（Siri、Alexa、Google Assistant）は"
                "タスク特化型で汎用的な対話能力は限定的。"
            ),
            num_rounds=12,
            service_name="ChatGPT",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.UP,
                description="ユーザー獲得",
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                description="大手テック企業の競合参入",
            ),
            ExpectedTrend(
                metric="dimensions.funding_climate",
                direction=TrendDirection.UP,
                description="AI投資の増加",
            ),
            ExpectedTrend(
                metric="dimensions.regulatory_risk",
                direction=TrendDirection.UP,
                description="AI規制議論の活発化",
            ),
            ExpectedTrend(
                metric="dimensions.tech_maturity",
                direction=TrendDirection.UP,
                description="LLM技術の進化",
            ),
            ExpectedTrend(
                metric="ai_disruption_level",
                direction=TrendDirection.UP,
                description="AI破壊度の上昇",
            ),
        ],
        expected_outcome=ExpectedOutcome.SUCCESS,
        tags=["ai", "success", "explosive_growth"],
    )


# ═══════════════════════════════════════════════════════════════
#  失敗事例
# ═══════════════════════════════════════════════════════════════


def _google_wave_2009() -> BenchmarkScenario:
    """Google Wave (2009) — コラボレーションツール."""
    return BenchmarkScenario(
        id="google_wave_2009",
        name="Google Wave 2009",
        description=(
            "Googleがメール・チャット・Wikiを統合するプラットフォームを公開。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "2009年5月、GoogleがGoogle I/Oで「Google Wave」を発表。"
                "「メールが今日発明されたらどうなるか」というコンセプトで、"
                "メール・チャット・Wiki・共同編集をリアルタイムで統合する。"
                "Google Maps開発者のLars/Jens Rasmussen兄弟が主導。"
                "招待制の限定公開で段階的にユーザーを拡大する計画。"
                "Google Wave Protocol（オープンプロトコル）で外部連携を目指す。"
                "競合は従来のメール（Gmail、Outlook）、チャット（AIM、MSN）、"
                "Wiki（MediaWiki、Confluence）。これらは分断されたツール群。"
                "当時のコラボレーション市場はIDCによると約58億ドル規模。"
                "リーマンショック後の経済回復初期でIT投資は慎重。"
                "Google Wave Previewとして開発者向けにAPIを公開。"
            ),
            num_rounds=12,
            service_name="Google Wave",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.DOWN,
                description="複雑すぎるUIと不明確なユースケースによる定着困難",
            ),
            ExpectedTrend(
                metric="dimensions.revenue_potential",
                direction=TrendDirection.DOWN,
                description="無料サービスで収益モデルが不明確",
            ),
            ExpectedTrend(
                metric="dimensions.tech_maturity",
                direction=TrendDirection.DOWN,
                description="先進的すぎる技術と市場ニーズの乖離リスク",
            ),
        ],
        expected_outcome=ExpectedOutcome.FAILURE,
        tags=["collaboration", "failure", "platformer"],
    )


def _google_plus_2011() -> BenchmarkScenario:
    """Google+ (2011) — SNS参入."""
    return BenchmarkScenario(
        id="google_plus_2011",
        name="Google+ 2011",
        description=(
            "GoogleがFacebook対抗のSNSをローンチ。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "2011年6月、GoogleがSNS「Google+」をローンチする。"
                "Vic Gundotraが主導し、Googleの戦略的最優先プロジェクトとして大規模投資。"
                "「サークル」機能で友人を分類し選択的に共有できるのが差別化ポイント。"
                "Hangouts（ビデオ通話）、Sparks（興味ベースのフィード）を搭載。"
                "Gmail、YouTube等のGoogleサービスとのアカウント統合を計画。"
                "競合のFacebookは2011年時点で約8億人のアクティブユーザー。"
                "Twitterは約1億DAU。LinkedInはビジネスSNSで2億会員。"
                "SNS広告市場は約59億ドル規模（eMarketer推計）。"
                "招待制で段階的に公開を拡大する戦略。"
            ),
            num_rounds=18,
            service_name="Google+",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.DOWN,
                description="アクティブユーザーが定着しない",
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                description="Google参入により一時的に競合圧力が上昇",
            ),
            ExpectedTrend(
                metric="dimensions.revenue_potential",
                direction=TrendDirection.DOWN,
                description="広告収益モデルが機能しない",
            ),
        ],
        expected_outcome=ExpectedOutcome.FAILURE,
        tags=["sns", "failure", "platformer"],
    )


def _quibi_2020() -> BenchmarkScenario:
    """Quibi (2020) — 短尺動画サービス."""
    return BenchmarkScenario(
        id="quibi_2020",
        name="Quibi 2020",
        description=(
            "大型資金調達を受けた短尺プレミアム動画サービスがローンチ。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "2020年4月、ハリウッドの重鎮ジェフリー・カッツェンバーグと"
                "元HP CEOメグ・ホイットマンが共同創業した短尺動画サービス「Quibi」がローンチ。"
                "17.5億ドルの大型資金調達に成功。10分以内のプレミアムコンテンツに特化。"
                "月額4.99ドル（広告付き）/7.99ドル（広告なし）のサブスクリプション。"
                "モバイル専用で、通勤・移動中の隙間時間をターゲット。"
                "独自技術「Turnstyle」で縦横切り替え視聴に対応。"
                "ハリウッドの著名監督・俳優によるオリジナルコンテンツを多数制作。"
                "競合はNetflix（1.83億会員）、Disney+、TikTok（無料・UGC）、YouTube。"
                "COVID-19パンデミックが世界的に拡大中で、外出・通勤が激減。"
                "ストリーミング市場は約500億ドル規模で成長中。"
            ),
            num_rounds=8,
            service_name="Quibi",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.DOWN,
                description="プロダクトマーケットフィットの欠如",
            ),
            ExpectedTrend(
                metric="dimensions.revenue_potential",
                direction=TrendDirection.DOWN,
                description="サブスク収益が伸びない",
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                description="TikTok・YouTubeとの競合激化",
            ),
            ExpectedTrend(
                metric="dimensions.funding_climate",
                direction=TrendDirection.DOWN,
                description="このカテゴリへの投資冷え込み",
            ),
        ],
        expected_outcome=ExpectedOutcome.FAILURE,
        tags=["streaming", "failure", "startup"],
    )


def _jasper_ai_2023() -> BenchmarkScenario:
    """Jasper AI (2021-2023) — AI文章生成SaaS."""
    return BenchmarkScenario(
        id="jasper_ai_2023",
        name="Jasper AI 2023",
        description=(
            "GPT-3 APIラッパー型のAI文章生成SaaSの市場展開。"
        ),
        scenario_input=ScenarioInput(
            description=(
                "2021年にJarvis（後にJasper AIに改名）としてローンチされた"
                "AI文章生成SaaS。OpenAIのGPT-3 APIを使ったマーケティングコピー生成ツール。"
                "ブログ記事、広告コピー、SNS投稿などのテンプレートベースの文章生成が特徴。"
                "月額49ドル〜のサブスクリプションモデル。"
                "2022年10月にシリーズAで1.25億ドルを調達、評価額15億ドル。"
                "ARRは約1億ドルに到達。10万以上の有料顧客。"
                "競合はCopy.ai、Writesonic、Rytr等の同種ツール。"
                "基盤技術（GPT-3）はOpenAI APIとして誰でもアクセス可能。"
                "OpenAIが汎用AIチャットサービス「ChatGPT」の無料公開を準備中との報道がある。"
                "生成AIコンテンツ市場は急速に拡大中。"
            ),
            num_rounds=12,
            service_name="Jasper AI",
        ),
        expected_trends=[
            ExpectedTrend(
                metric="dimensions.user_adoption",
                direction=TrendDirection.DOWN,
                description="基盤技術への直接アクセスによるユーザー流出",
            ),
            ExpectedTrend(
                metric="dimensions.competitive_pressure",
                direction=TrendDirection.UP,
                description="基盤モデル直接利用による競合激化",
            ),
            ExpectedTrend(
                metric="dimensions.revenue_potential",
                direction=TrendDirection.DOWN,
                description="無料代替手段の登場で有料SaaSの価値低下",
            ),
            ExpectedTrend(
                metric="ai_disruption_level",
                direction=TrendDirection.UP,
                description="AI技術の進歩がラッパー型ビジネスを脅かす",
            ),
        ],
        expected_outcome=ExpectedOutcome.FAILURE,
        tags=["ai", "failure", "saas", "disrupted"],
    )


# ═══════════════════════════════════════════════════════════════
#  匿名化マッピング（A/Bテスト用）
# ═══════════════════════════════════════════════════════════════

from app.evaluation.anonymizer import AnonymizationMap

ANONYMIZATION_MAPS: dict[str, AnonymizationMap] = {
    "slack_2014": AnonymizationMap(
        service_alias="TeamConnect",
        replacements=[
            ("Stewart Butterfield", "創業者A"),
            ("Tiny Speck", "スタートアップX"),
            ("Flickr", "写真共有サービス"),
            ("Glitch", "オンラインゲーム"),
            ("HipChat", "ChatTool-A"),
            ("Campfire", "ChatTool-B"),
            ("Microsoft Lync", "UC-Platform-A"),
            ("Skype for Business", "UC-Platform-A Next"),
            ("Yammer", "SocialTool-A"),
            ("37signals", "開発会社B"),
            ("Basecamp", "PM-Tool-A"),
            ("Atlassian", "DevToolCo"),
            ("Slack", "TeamConnect"),
        ],
    ),
    "notion_vs_confluence_2020": AnonymizationMap(
        service_alias="DocuSpace",
        replacements=[
            ("Confluence", "WikiTool-A"),
            ("Atlassian", "DevToolCo"),
            ("Roam Research", "NoteTool-B"),
            ("Google Docs", "CloudDocs-A"),
            ("Notion", "DocuSpace"),
            ("Coda", "DocTool-C"),
            ("Jira", "DevTracker-A"),
        ],
    ),
    "github_copilot_2022": AnonymizationMap(
        service_alias="CodeAssist",
        replacements=[
            ("GitHub Copilot", "CodeAssist"),
            ("Amazon CodeWhisperer", "CodeGen-A"),
            ("CodeWhisperer", "CodeGen-A"),
            ("Tabnine", "CodeGen-B"),
            ("Kite", "CodeGen-C"),
            ("IntelliCode", "CodeGen-D"),
            ("OpenAI Codex", "AIモデルX"),
            ("OpenAI", "AIラボX"),
            ("Codex", "AIモデルX"),
            ("GitHub", "DevPlatform"),
            ("Microsoft", "大手テック企業M"),
            ("VS Code", "主要エディタ"),
        ],
    ),
    "zoom_2020": AnonymizationMap(
        service_alias="MeetNow",
        replacements=[
            ("Microsoft Teams", "VideoChat-A"),
            ("Google Meet", "VideoChat-B"),
            ("Cisco WebEx", "VideoChat-C"),
            ("WebEx", "VideoChat-C"),
            ("Skype for Business", "VideoChat-D"),
            ("Skype", "VideoChat-D"),
            ("Zoom Rooms", "MeetNow Rooms"),
            ("Zoom Phone", "MeetNow Phone"),
            ("Zoom", "MeetNow"),
        ],
    ),
    "chatgpt_2022": AnonymizationMap(
        service_alias="DialogAI",
        replacements=[
            ("GPT-3.5", "LLM-v2"),
            ("GPT-3", "LLM-v1"),
            ("RLHF", "対話最適化手法"),
            ("OpenAI", "AIラボX"),
            ("ChatGPT", "DialogAI"),
            ("Google Assistant", "音声AI-A"),
            ("Alexa", "音声AI-B"),
            ("Siri", "音声AI-C"),
            ("Microsoft", "大手テック企業M"),
            ("Bing", "検索エンジンB"),
            ("Google", "検索大手G"),
        ],
    ),
    "google_wave_2009": AnonymizationMap(
        service_alias="WaveComm",
        replacements=[
            ("Google Wave", "WaveComm"),
            ("Google I/O", "開発者カンファレンス"),
            ("Lars Rasmussen", "開発者A"),
            ("Jens Rasmussen", "開発者B"),
            ("Wave Protocol", "WaveComm Protocol"),
            ("Gmail", "メールサービスG"),
            ("Google Apps", "クラウドオフィスG"),
            ("Google Docs", "クラウドドキュメントG"),
            ("Microsoft Exchange", "メールサーバーM"),
            ("Outlook", "メールクライアントM"),
            ("SharePoint", "社内WikiM"),
            ("Campfire", "チャットツールC"),
            ("Basecamp", "PMツールC"),
            ("Google", "大手テック企業G"),
        ],
    ),
    "google_plus_2011": AnonymizationMap(
        service_alias="CircleNet",
        replacements=[
            ("Vic Gundotra", "プロジェクトリーダーV"),
            ("Google+", "CircleNet"),
            ("Google Plus", "CircleNet"),
            ("Facebook", "SNS-A"),
            ("Twitter", "SNS-B"),
            ("LinkedIn", "SNS-C"),
            ("Tumblr", "SNS-D"),
            ("Pinterest", "SNS-E"),
            ("Hangouts", "ビデオ通話機能"),
            ("Sparks", "興味フィード機能"),
            ("Circles", "グループ分類機能"),
            ("Gmail", "メールサービスG"),
            ("YouTube", "動画サービスY"),
            ("Google", "大手テック企業G"),
        ],
    ),
    "quibi_2020": AnonymizationMap(
        service_alias="QuickVid",
        replacements=[
            ("Jeffrey Katzenberg", "ハリウッド重鎮A"),
            ("Katzenberg", "重鎮A"),
            ("Meg Whitman", "経営者B"),
            ("Whitman", "経営者B"),
            ("Turnstyle", "回転表示技術"),
            ("Netflix", "StreamingCo-A"),
            ("Disney+", "StreamingCo-B"),
            ("TikTok", "ShortVideo-A"),
            ("YouTube", "VideoPlatform-A"),
            ("HBO Max", "StreamingCo-C"),
            ("Hulu", "StreamingCo-D"),
            ("T-Mobile", "通信キャリアT"),
            ("Quibi", "QuickVid"),
        ],
    ),
    "jasper_ai_2023": AnonymizationMap(
        service_alias="CopyGen",
        replacements=[
            ("Jasper AI", "CopyGen"),
            ("Jasper", "CopyGen"),
            ("Jarvis", "CopyGen旧名"),
            ("Copy.ai", "AIWriter-A"),
            ("Writesonic", "AIWriter-B"),
            ("Rytr", "AIWriter-C"),
            ("Grammarly", "文法チェッカーG"),
            ("OpenAI", "AIラボX"),
            ("GPT-3", "LLM-v1"),
            ("ChatGPT", "AIラボX汎用サービス"),
            ("Microsoft", "大手テック企業M"),
            ("Insight Partners", "投資ファンドI"),
        ],
    ),
}


# ─── レジストリ ───

_BENCHMARK_FACTORIES = [
    # 成功事例
    _slack_2014,
    _notion_vs_confluence,
    _github_copilot_2022,
    _zoom_2020,
    _chatgpt_2022,
    # 失敗事例
    _google_wave_2009,
    _google_plus_2011,
    _quibi_2020,
    _jasper_ai_2023,
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
