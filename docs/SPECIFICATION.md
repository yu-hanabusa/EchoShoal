# EchoShoal 仕様書

## 1. プロジェクト概要

### 1.1 目的

EchoShoalは**サービスビジネスインパクトシミュレーター**である。特定のサービスが市場に投入された場合に、各ステークホルダー（企業、フリーランス、個人開発者、行政、投資家、プラットフォーマー、業界団体）がどのように反応し、そのサービスが成功するか否かを予測する。

### 1.2 解決する課題

- 新規サービスをリリースする際の「成功するか？」という問いに対し、定量的かつ多角的な判断材料を提供
- 「もし価格を変えたら？」「競合が参入したら？」のWhat-ifシナリオを比較可能にする
- 入力は最小限（サービス名＋説明文）でよく、不足情報はLLMが自動補間する

### 1.3 システム構成図

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React + TypeScript)            │
│  NewSimulationPage → SimulationPage → ReportPage            │
└────────────────────────────┬────────────────────────────────┘
                             │ REST API
┌────────────────────────────┴────────────────────────────────┐
│                     Backend (FastAPI)                        │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Scenario │  │ Simulation│  │ Report   │  │ Prediction│  │
│  │ Analyzer │→ │ Engine    │→ │ Generator│  │ & Compare │  │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └───────────┘  │
│       │              │              │                        │
│  ┌────┴──────────────┴──────────────┴─────┐                 │
│  │           Core Services                 │                 │
│  │  LLM Router │ NLP │ Graph │ Documents  │                 │
│  └──────┬──────────┬──────────┬───────────┘                 │
└─────────┼──────────┼──────────┼─────────────────────────────┘
          │          │          │
    ┌─────┴───┐ ┌────┴───┐ ┌───┴────┐
    │ Ollama  │ │ Neo4j  │ │ Redis  │
    │ (LLM)  │ │(Graph) │ │(Queue) │
    └─────────┘ └────────┘ └────────┘
```

### 1.4 技術スタック

| レイヤー | 技術 | 用途 |
|---------|------|------|
| Backend | FastAPI (Python 3.13) + uv | APIサーバー |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS v4 | SPA |
| Graph DB | Neo4j Community Edition 5 | 知識グラフ、因果チェーン記録 |
| Cache/Queue | Redis 7 | ジョブ管理、結果キャッシュ |
| LLM (軽量) | Ollama (qwen2.5:14b / gemma3:12b) | エージェント意思決定、イベント生成 |
| LLM (重量) | Claude API / OpenAI API | レポート生成、成功スコア算出 |
| NLP | ルールベース辞書 + LLM | 技術名・政策名・組織名抽出 |
| Testing | pytest + pytest-asyncio + httpx | 354テスト |

---

## 2. ドメインモデル

### 2.1 ステークホルダータイプ（8種）

シミュレーション内でエージェントとして自律的に意思決定する主体。

| タイプ | 値 | 説明 | 例 |
|--------|-----|------|----|
| 企業 | `enterprise` | 大手・中堅・スタートアップ | 大手テクノロジー企業、スタートアップ |
| フリーランス | `freelancer` | 受託の延長でサービス活用 | フルスタックエンジニア |
| 個人開発者 | `indie_developer` | 自発的プロダクト開発 | 副業開発者 |
| 行政 | `government` | 規制・補助金 | デジタル庁 |
| 投資家/VC | `investor` | 資金提供・市場シグナル | VCファンド |
| プラットフォーマー | `platformer` | AWS/Google等の大手テック | グローバルクラウド |
| 業界団体 | `community` | 標準化・OSS推進 | OSSコミュニティ |
| エンドユーザー | `end_user` | サービスの最終利用者 | 一般ユーザー層 |

### 2.2 マーケットディメンション（8次元）

シミュレーションが毎ラウンド追跡する市場指標（0.0〜1.0スケール）。

| ディメンション | 値 | 説明 | 初期値 |
|---------------|-----|------|--------|
| ユーザー獲得率 | `user_adoption` | サービスのユーザー浸透度 | LLM推定 |
| 収益ポテンシャル | `revenue_potential` | 収益化の可能性 | LLM推定 |
| 技術成熟度 | `tech_maturity` | 技術的完成度 | LLM推定 |
| 競合圧力 | `competitive_pressure` | 競合からの脅威度 | LLM推定 |
| 規制リスク | `regulatory_risk` | 規制による制約 | LLM推定 |
| 市場認知度 | `market_awareness` | 市場での認知度 | LLM推定 |
| エコシステム健全性 | `ecosystem_health` | 連携サービス・コミュニティの活性度 | LLM推定 |
| 資金調達環境 | `funding_climate` | 投資環境の良さ | LLM推定 |

### 2.3 外的要因（環境パラメータ）

エージェントではなく「世界側」に起きるマクロ環境指標（0.0〜1.0）。

| 指標 | 説明 | 初期値 |
|------|------|--------|
| `economic_sentiment` | 経済センチメント | LLM推定 |
| `tech_hype_level` | 技術ハイプレベル | LLM推定 |
| `regulatory_pressure` | 規制圧力 | LLM推定 |
| `remote_work_adoption` | リモートワーク普及率 | LLM推定 |
| `ai_disruption_level` | AI破壊的変化の度合い | LLM推定 |

### 2.4 データモデル定義

#### ScenarioInput（ユーザー入力）

```
description: str          # シナリオ説明文（10〜2000文字、必須）
num_rounds: int            # シミュレーション期間（1〜36ヶ月、デフォルト24）
service_name: str          # サービス名（任意）
service_url: str | None    # GitHub URL等（任意、GitHub URLならREADME自動取得）
target_market: str | None  # ターゲット市場の説明（任意）
economic_climate: float    # 経済環境（-1.0〜1.0、0で自動推定）
tech_disruption: float     # 技術破壊度（-1.0〜1.0、0で自動推定）
regulatory_change: str | None  # 規制変更（任意、NLPで自動検出）
```

#### ServiceMarketState（市場スナップショット）

```
round_number: int                           # ラウンド番号
service_name: str                           # サービス名
dimensions: dict[MarketDimension, float]    # 8次元の値
economic_sentiment: float                   # マクロ: 経済センチメント
tech_hype_level: float                      # マクロ: 技術ハイプ
regulatory_pressure: float                  # マクロ: 規制圧力
remote_work_adoption: float                 # マクロ: リモートワーク普及率
ai_disruption_level: float                  # マクロ: AI破壊度
```

#### RoundResult（ラウンド結果）

```
round_number: int                           # ラウンド番号
market_state: ServiceMarketState            # その時点の市場状態
actions_taken: list[dict]                   # 実行されたアクション一覧
events: list[str]                           # 発生したイベント
summary: str                                # LLM生成のナラティブ（1-2文）
document_references: list[DocumentReference] # 参照された文書ログ
```

#### SuccessScore（成功スコア）

```
score: int           # 0〜100（70以上: 成功見込み、40-69: 要注意、39以下: 困難）
verdict: str         # "成功見込み" / "要注意" / "困難"
key_factors: list    # 判定根拠（最大5件）
risks: list          # リスク（最大5件）
opportunities: list  # 機会（最大5件）
```

---

## 3. エージェントアーキテクチャ

### 3.1 エージェントの構造

各エージェントは以下の3つの要素で構成される。

**AgentProfile（静的プロフィール、不変）**
- `id`: UUID
- `name`: エージェント名
- `agent_type`: 種別（"大手企業"、"フリーランス"等）
- `stakeholder_type`: StakeholderType列挙型
- `description`: 背景説明

**AgentState（可変状態、毎ラウンド更新）**
- `capabilities`: 各ディメンションへの影響力（0-1）
- `revenue`: 月間売上（万円）
- `cost`: 月間コスト（万円）
- `headcount`: 人員数
- `satisfaction`: 満足度（0-1）
- `reputation`: 市場評判（0-1）
- `active_contracts`: 契約数
- `risk_tolerance`: リスク許容度（0-1）

**AgentPersonality（認知バイアス、不変）**
- `conservatism` (0-1): 保守性。高い→変化を嫌う
- `bandwagon` (0-1): 同調性。高い→他者を真似する
- `overconfidence` (0-1): 過信度。高い→リスクを過小評価
- `sunk_cost_bias` (0-1): 埋没費用バイアス。高い→過去の投資を捨てられない
- `info_sensitivity` (0-1): 情報感度。低い→トレンドを見落とす
- `noise` (0-0.3): ノイズ確率。LLM判断後にランダム行動に差し替える確率
- `description`: 性格の自由記述テキスト（プロンプトに注入）

### 3.2 エージェント別アクション一覧

#### 企業（EnterpriseAgent）
| アクション | 説明 | 可視性 |
|-----------|------|--------|
| `adopt_service` | 対象サービスを採用 | public |
| `reject_service` | 対象サービスを不採用 | private |
| `build_competitor` | 競合サービスを自社開発 | public |
| `acquire_startup` | サービス提供元を買収 | public |
| `invest_rd` | R&D投資 | partial |
| `lobby_regulation` | 規制ロビー活動 | partial |
| `partner` | サービス提供元と提携 | public |
| `wait_and_observe` | 様子見 | private |

#### フリーランス（FreelancerAgent）
| アクション | 説明 | 可視性 |
|-----------|------|--------|
| `adopt_tool` | ツールとして採用 | public |
| `offer_service` | サービスを活用した受託提供 | public |
| `upskill` | スキル習得 | private |
| `build_portfolio` | ポートフォリオ構築 | public |
| `raise_rate` | 単価交渉 | public |
| `switch_platform` | 別プラットフォームへ移行 | public |
| `network` | 人脈構築 | public |
| `rest` | 休養 | private |

#### 個人開発者（IndieDevAgent）
| アクション | 説明 | 可視性 |
|-----------|------|--------|
| `launch_competing_product` | 競合プロダクトリリース | public |
| `pivot_product` | 方向転換 | public |
| `open_source` | OSSとして公開 | public |
| `monetize` | 収益化 | public |
| `abandon_project` | プロジェクト放棄 | private |
| `seek_funding` | 資金調達 | partial |
| `build_community` | コミュニティ構築 | public |

#### 行政（GovernmentAgent）
| アクション | 説明 | 可視性 |
|-----------|------|--------|
| `regulate` | 規制導入 | public |
| `subsidize` | 補助金/助成金 | public |
| `certify` | 認証/承認 | public |
| `investigate` | 調査/監査 | public |
| `deregulate` | 規制緩和 | public |
| `partner_public` | 官民連携 | public |
| `issue_guideline` | ガイドライン策定 | public |

#### 投資家/VC（InvestorAgent）
| アクション | 説明 | 可視性 |
|-----------|------|--------|
| `invest_seed` | シード投資 | public |
| `invest_series` | シリーズ投資 | public |
| `divest` | 投資引き上げ | partial |
| `fund_competitor` | 競合に投資 | partial |
| `market_signal` | 市場シグナル発信 | public |
| `wait_and_see` | 様子見 | private |
| `mentor` | メンタリング | partial |

#### プラットフォーマー（PlatformerAgent）
| アクション | 説明 | 可視性 |
|-----------|------|--------|
| `launch_competing_feature` | 競合機能リリース | public |
| `acquire_service` | サービス買収 | public |
| `partner_integrate` | API連携/提携 | public |
| `restrict_api` | API制限/囲い込み | public |
| `price_undercut` | 価格競争 | public |
| `ignore` | 無視 | private |
| `open_platform` | プラットフォーム開放 | public |

#### 業界団体/コミュニティ（CommunityAgent）
| アクション | 説明 | 可視性 |
|-----------|------|--------|
| `endorse` | 推薦/支持 | public |
| `set_standard` | 標準規格採用 | public |
| `reject_standard` | 標準規格除外 | public |
| `create_alternative` | 代替作成 | public |
| `educate_market` | 市場教育 | public |
| `observe` | 様子見 | private |
| `publish_report` | 調査レポート公開 | public |

### 3.3 意思決定フロー

```
1. エンジンがエージェントに市場状態を渡す
   ↓
2. GraphRAGが可視性制御付きコンテキストを生成
   - 他エージェントのpublic/partialアクション
   - 自身の過去の行動履歴
   - 市場活動サマリー
   - 文書から抽出されたエンティティ
   ↓
3. システムプロンプト構築
   - エージェントの役割・ステークホルダー種別
   - 性格パラメータから自然言語テキスト生成
   - シナリオ要約（LLM補間情報含む）
   - 利用可能アクション一覧
   ↓
4. LLMが最大2つのアクションをJSON形式で選択
   ↓
5. ノイズ注入チェック（personality.noise確率でランダム行動に差し替え）
   ↓
6. アクション適用（エージェント状態更新）
   ↓
7. Neo4jに記録（行動＋状態スナップショット＋因果チェーン）
```

#### エンドユーザー（EndUserAgent）
| アクション | 説明 | 可視性 |
|-----------|------|--------|
| `adopt_new_service` | 新サービスを採用 | public |
| `stay_with_current` | 現状サービスを継続利用 | private |
| `trial` | トライアル利用 | public |
| `churn` | サービス離脱 | public |
| `recommend` | 他者へ推薦 | public |
| `complain` | 不満表明 | public |
| `compare_alternatives` | 代替サービスと比較 | private |

### 3.4 デフォルトエージェント構成（8体）

LLMが利用不可の場合のフォールバック。

| # | 名前 | 種別 | 特徴 |
|---|------|------|------|
| 1 | 大手テクノロジー企業A | 企業（大手） | 保守的、資金力豊富、防衛的 |
| 2 | スタートアップB | 企業（新興） | アグレッシブ、過信気味、素早い |
| 3 | フリーランスC | フリーランス | 早期採用者、技術好奇心旺盛 |
| 4 | 個人開発者D | 個人開発者 | SNSに影響されやすい、実装力あり |
| 5 | デジタル庁 | 行政 | 意思決定遅い、影響力大 |
| 6 | VCファンドE | 投資家 | データドリブン、ハイプに敏感 |
| 7 | グローバルクラウドF | プラットフォーマー | 市場が大きければ即参入、小さければ無視 |
| 8 | 業界コミュニティG | 業界団体 | オープン性重視、ベンダーロックイン批判的 |

---

## 4. シミュレーションエンジン

### 4.1 実行フロー

```
入力: ScenarioInput + 文書（任意） + GitHub URL（任意）
  │
  ├─ 1. シナリオ解析（ScenarioAnalyzer）
  │    ├─ NLP解析: 技術名・組織名・政策名を抽出
  │    ├─ LLMパラメータ推定: economic_climate, tech_disruption
  │    └─ LLM情報補間: 収益モデル、競合、市場規模等を推定
  │
  ├─ 2. GitHub README取得（service_urlがGitHub URLの場合）
  │    └─ README → DocumentProcessor → Neo4jに格納
  │
  ├─ 3. エージェント生成（AgentGenerator）
  │    ├─ LLMがシナリオに適したエージェントを5〜15体生成
  │    └─ 失敗時: デフォルト8体にフォールバック
  │
  ├─ 4. 市場初期状態をLLMが設定（全ディメンション＋マクロ指標）
  │
  ├─ 5. イベントスケジュール生成（EventScheduler）
  │    ├─ LLMが3〜5個のイベントを生成
  │    └─ 失敗時: イベントなし（根拠のない固定値は使用しない）
  │
  └─ 6. シミュレーション実行（OASISSimulationEngine）
       │
       └─ ラウンド1〜N を繰り返し:
            ├─ グラフからエージェント能力分布を取得（参考情報）
            ├─ エージェント活性化（約40%をランダム選択）
            ├─ 各アクティブエージェント:
            │   ├─ GraphRAGコンテキスト取得（可視性制御付き）
            │   ├─ LLM意思決定（性格バイアス＋ノイズ＋self_impact推定）
            │   ├─ self_impact適用 → エージェント状態更新
            │   └─ Neo4j記録（行動＋状態＋因果チェーン）
            ├─ 市場更新（LLMが全アクションの影響を状況判断）
            ├─ イベント適用
            └─ ナラティブ生成（アクション3件以上またはイベント時）
```

### 4.2 市場更新ロジック

**固定係数テーブルは使用しない。** 各ラウンドでLLMが以下の情報を受け取り、市場への影響を状況判断する。

**LLMへの入力:**
- 現在の全ディメンション値
- 現在のマクロ指標
- 実行された全アクション（エージェント名、評判、行動タイプ、説明）
- グラフ上のエージェント能力分布

**LLMからの出力:**
```json
{
  "dimension_deltas": {"user_adoption": 0.05, "competitive_pressure": -0.02, ...},
  "macro_deltas": {"economic_sentiment": 0.01, ...}
}
```

**安全制約:**
- ディメンションdelta: -0.1〜+0.1にクランプ
- マクロdelta: -0.05〜+0.05にクランプ
- 全値: 0.0〜1.0にクランプ
- LLM失敗時: 市場は変化しない（安全側にフォールバック）

### 4.3 イベントシステム

**イベントタイプ:**
- `policy_change` — 政策・制度変更
- `economic_shock` — 景気変動
- `tech_disruption` — 技術的変革
- `competitive_move` — 競合の動き
- `industry_shift` — 業界構造変化
- `natural_disaster` — 自然災害

**イベント影響:**
```
dimension_delta: dict[str, float]         # ディメンションへの影響
economic_sentiment_delta: float           # 経済センチメント変化
tech_hype_delta: float                    # 技術ハイプ変化
regulatory_pressure_delta: float          # 規制圧力変化
ai_disruption_delta: float               # AI破壊度変化
```

各イベントは`trigger_round`から`duration`ラウンド間有効。

### 4.4 情報非対称性（可視性制御）

エージェントは他のエージェントの**すべての行動を見ることはできない**。

- **public**: 全エージェントに見える（例: サービス採用、競合リリース）
- **partial**: 一部のエージェントに見える（例: R&D投資、メンタリング）
- **private**: 本人のみ見える（例: 不採用判断、プロジェクト放棄、様子見）

GraphRAGRetrieverが観察者ごとに異なるコンテキストを生成する。

---

## 5. LLM情報補間レイヤー

### 5.1 概要

ユーザーが入力しなかった情報をLLMが類似サービスの知識に基づいて推定し、シミュレーションの精度を向上させる。

### 5.2 補間される情報

| フィールド | 説明 | 例 |
|-----------|------|-----|
| `revenue_model` | 収益モデル | "SaaS月額" / "フリーミアム" / "広告" |
| `price_range` | 価格帯 | "無料プラン + 月額1,000円〜" |
| `competitors` | 推定競合 | ["Slack", "Microsoft Teams", "Discord"] |
| `target_users` | ターゲットユーザー | "中小企業のリモートチーム" |
| `tech_stack` | 技術スタック | "React + Node.js + PostgreSQL" |
| `team_size_estimate` | チーム規模 | "5-10人のスタートアップ" |
| `market_size_estimate` | 市場規模 | "国内500億円規模" |
| `confidence_notes` | 推定根拠 | ["類似SaaSの市場データに基づく推定"] |

### 5.3 利用箇所

- **エージェントプロンプト**: context_summaryに「【LLM推定による補間情報】」として注入
- **レポート**: 推定値の信頼度を考慮した追加情報提案
- **動的エージェント生成**: 補間情報を元により適切なエージェントを生成

---

## 6. レポート生成

### 6.1 レポート構成

1. **サービス成功スコア** — 0-100のLLM算出スコア + 判定理由/リスク/機会
2. **エグゼクティブサマリー** — 3-5文の総合評価
3. **市場インパクト分析** — マクロ指標の推移分析
4. **ディメンション分析** — 8次元それぞれのトレンド分析
5. **ステークホルダー影響分析** — 各ステークホルダーへの影響
6. **資料影響分析** — 入力文書がどのエージェントの判断にどう影響したか
7. **追加情報提案** — シミュレーション精度向上に必要な情報の提案
8. **提言** — サービス提供者・投資家・ユーザー企業向けのアクション提案

### 6.2 成功スコア詳細

LLMが最終ディメンション値 + マクロ指標 + アクション集計を分析し、JSON形式でスコアを返す。

**判定基準:**
- **70-100 (成功見込み)**: user_adoptionが高い、funding_climateが良好、competitive_pressureが管理可能
- **40-69 (要注意)**: 一部指標は良いが課題あり
- **0-39 (困難)**: 複数ディメンションで不利な状況

---

## 7. 定量予測

### 7.1 予測手法

- **線形回帰**: 全ラウンドの値から傾き（slope）と切片を最小二乗法で計算
- **移動平均**: ウィンドウサイズ3の単純移動平均
- **6ヶ月予測**: 最終値 + (slope × 6) で将来値を推定

### 7.2 ハイライト自動生成

- 最も成長したディメンション（変化率 > 5%の場合）
- 最も低下したディメンション（変化率 < -5%の場合）
- 競合圧力警告（予測値 > 0.7の場合）
- ユーザー獲得評価（高: > 0.6、低: < 0.2）
- AI破壊度トラッキング

### 7.3 シナリオ比較

2つのシミュレーション結果を比較して以下を算出:
- 各ディメンションの値差分
- マクロ指標の差分
- 最も影響を受けたディメンション上位3件

---

## 8. ベンチマーク評価

実在のサービスリリース事例を使ってシミュレータの精度を検証する。

### 8.1 ベンチマークシナリオ（9件）

| ID | サービス | 年 | 主要期待トレンド |
|----|---------|-----|-----------------|
| `slack_2014` | Slack | 2014 | user_adoption UP, competitive_pressure UP |
| `notion_vs_confluence_2020` | Notion | 2020 | user_adoption UP, revenue_potential UP |
| `github_copilot_2022` | GitHub Copilot | 2022 | tech_maturity UP, competitive_pressure UP |
| `zoom_2020` | Zoom | 2020 | user_adoption UP, revenue_potential UP |
| `chatgpt_2022` | ChatGPT | 2022 | user_adoption UP, funding_climate UP |
| `stripe_2011` | Stripe | 2011 | tech_maturity UP, ecosystem_health UP |
| `tiktok_2018` | TikTok | 2018 | user_adoption UP, regulatory_risk UP |
| `figma_2016` | Figma | 2016 | user_adoption UP, tech_maturity UP |
| `uber_2012` | Uber | 2012 | user_adoption UP, regulatory_risk UP |

### 8.2 評価スコア算出

**恣意的な重みは使用しない。** 方向一致率のみで評価する。

```
各期待トレンドについて:
  期待: user_adoption → UP
  実際: 初期値0.3 → 最終値0.65 → 方向UP → 一致 ✅

スコア = 方向が一致したトレンド数 / 全トレンド数

統計評価（複数回実行）:
  N回実行して各回の方向一致率を計算
  → 平均方向一致率 + 標準偏差 で再現性を検証
```

---

## 9. 知識グラフ構造

### 9.1 Neo4jノードタイプ

```
:Agent          {agent_id, simulation_id, name, agent_type, industry}
:AgentSnapshot  {agent_id, simulation_id, round, revenue, cost, headcount, ...}
:ActionRecord   {agent_id, agent_name, simulation_id, round, action_type, description, visibility}
:MarketEffect   {simulation_id, round, skill, demand_delta, supply_delta}
:Skill          {name}
:Document       {doc_id, simulation_id, filename, source, text_length}
:Company        {name}
:Policy         {name}
```

### 9.2 リレーションシップ

```
Agent -[STATE_AT {round}]-> AgentSnapshot
Agent -[PERFORMED {round}]-> ActionRecord
Agent -[SKILLED_IN {proficiency}]-> Skill
ActionRecord -[CAUSED]-> MarketEffect
Document -[MENTIONS]-> Skill|Company|Policy
```

### 9.3 因果チェーン

```
Agent → PERFORMED → ActionRecord → CAUSED → MarketEffect → AFFECTS → Skill/Dimension
```

これにより「なぜこのディメンションが上がったのか」を遡って説明できる。

---

## 10. APIエンドポイント

### 10.1 シミュレーション

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/simulations/` | シミュレーション作成＋即時実行 |
| GET | `/api/simulations/` | 一覧取得 |
| GET | `/api/simulations/{job_id}` | 結果取得 |
| GET | `/api/simulations/{job_id}/progress` | 進捗取得 |
| DELETE | `/api/simulations/{job_id}` | 削除 |
| POST | `/api/simulations/{job_id}/documents` | 追加文書アップロード |
| GET | `/api/simulations/{job_id}/documents` | 文書一覧 |
| POST | `/api/simulations/{job_id}/rerun` | 再実行 |
| GET | `/api/simulations/{job_id}/graph` | グラフ可視化データ |

### 10.2 レポート・予測

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/simulations/{job_id}/report` | レポート生成（成功スコア含む） |
| GET | `/api/simulations/{job_id}/prediction` | 定量予測 |
| GET | `/api/simulations/{job_id}/compare/{alt_job_id}` | 2シナリオ比較 |

### 10.3 その他

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/health` | ヘルスチェック |
| POST | `/api/data/collect` | e-Stat統計データ収集 |
| GET | `/api/data/ontology` | 知識グラフ構造 |
| GET | `/api/evaluation/benchmarks` | ベンチマーク一覧 |
| POST | `/api/evaluation/run` | ベンチマーク実行 |

### 10.4 レスポンス例

**POST /api/simulations/ リクエスト（FormData）:**
```
description: "チームコミュニケーションツールをフリーミアムモデルで投入..."
service_name: "TeamChat"
service_url: "https://github.com/example/teamchat"
num_rounds: 24
files: [README.txt]
```

**GET /api/simulations/{id}/report レスポンス:**
```json
{
  "title": "サービスビジネスインパクトレポート",
  "executive_summary": "TeamChatは...",
  "success_score": {
    "score": 72,
    "verdict": "成功見込み",
    "key_factors": ["フリーミアムモデルがuser_adoptionを押し上げ"],
    "risks": ["プラットフォーマーの競合機能リリースリスク"],
    "opportunities": ["エンタープライズ転換による収益化"]
  },
  "sections": [
    {"title": "市場インパクト分析", "content": "..."},
    {"title": "ディメンション分析", "content": "..."},
    {"title": "ステークホルダー影響分析", "content": "..."},
    {"title": "資料影響分析", "content": "..."},
    {"title": "追加情報提案", "content": "..."},
    {"title": "提言", "content": "..."}
  ]
}
```

---

## 11. フロントエンド

### 11.1 ページ構成

| パス | ページ | 説明 |
|------|--------|------|
| `/` | HomePage | シミュレーション一覧 |
| `/new` | NewSimulationPage | 新規作成フォーム |
| `/simulation/:jobId` | SimulationPage | 結果表示（3タブ: 結果/文書/グラフ） |
| `/simulation/:jobId/report` | ReportPage | レポート＋成功スコア |

### 11.2 NewSimulationPage

**入力フィールド:**
1. Service Name — テキスト入力（任意）
2. GitHub URL — URL入力（任意、GitHubならREADME自動取得）
3. Scenario — テキストエリア（10-2000文字、必須）
4. Seed Documents — ファイルアップロード（.txt/.pdf、複数可、任意）
5. Simulation Period — 数値入力（1-36ヶ月）

### 11.3 SimulationPage

**結果表示（Completed時）:**
- サマリーカード: 定性評価4項目（市場浸透、競合優位性、収益性、エコシステム）
- D3 force-directed 関係図: エージェント間関係の可視化 + タイムスライダー
- ソーシャルフィード: OASIS SNS投稿一覧（投稿・コメント・エンゲージメント）
- OASISプラットフォーム統計
- チャート2枚: 成長系ディメンション / リスク系ディメンション
- エージェントテーブル: 最終状態 + パーソナリティレーダーチャート（モーダル）

### 11.4 ReportPage

- 成功スコアカード（0-100、色分け: 緑≥70/黄≥40/赤<40）
- エグゼクティブサマリー
- 予測ハイライト
- ディメンション別予測テーブル（現在値/予測値/変化率）
- レポートセクション（6セクション）

---

## 12. 設定

### 12.1 環境変数

すべての設定は`ECHOSHOAL_`プレフィックス付き環境変数で管理（`pydantic-settings`）。

```bash
# LLM
ECHOSHOAL_OLLAMA_BASE_URL=http://localhost:11434
ECHOSHOAL_OLLAMA_MODEL=qwen2.5:14b
ECHOSHOAL_CLAUDE_API_KEY=              # 必須（レポート生成用）
ECHOSHOAL_OPENAI_API_KEY=              # 代替
ECHOSHOAL_DEFAULT_HEAVY_PROVIDER=claude

# データベース
ECHOSHOAL_NEO4J_URI=bolt://localhost:7687
ECHOSHOAL_NEO4J_USER=neo4j
ECHOSHOAL_NEO4J_PASSWORD=              # 必須
ECHOSHOAL_REDIS_URL=redis://localhost:6379

# シミュレーション
ECHOSHOAL_MAX_ROUNDS=36
ECHOSHOAL_DEFAULT_ROUNDS=24
ECHOSHOAL_AGENT_ACTIVATION_RATE=0.4
ECHOSHOAL_MAX_LLM_CALLS=5000
ECHOSHOAL_MAX_CONCURRENT_SIMULATIONS=3
ECHOSHOAL_RATE_LIMIT_PER_MINUTE=10

# OASIS統合
ECHOSHOAL_OASIS_PLATFORM=reddit       # "reddit" or "twitter"
ECHOSHOAL_OASIS_MAX_AGENTS=200        # 最大エージェント数
ECHOSHOAL_OASIS_ROUNDS_PER_STEP=1     # OASISステップ数/ラウンド
ECHOSHOAL_OASIS_MESSAGE_WINDOW_SIZE=10 # メッセージ窓サイズ
ECHOSHOAL_OASIS_CONTEXT_TOKEN_LIMIT=4096
ECHOSHOAL_OASIS_MAX_OUTPUT_TOKENS=512
```

### 12.2 インフラ構成

```bash
docker compose up -d    # Neo4j (7474/7687) + Redis (6379)
ollama run qwen2.5:14b  # ローカルLLM (11434)
```

---

## 13. セキュリティ

### 13.1 秘密情報管理
- APIキー・パスワードはソースコードに**一切**ハードコーディングしない
- `pydantic-settings`経由で環境変数から読み込み
- `.env`は`.gitignore`に含まれ、コミットされない
- `.env.example`にはキー名のみ（値は空）

### 13.2 入力バリデーション
- すべてのAPIエンドポイントでPydanticモデルによるバリデーション
- ScenarioInput: 10-2000文字制限
- GitHub URL: 正規表現パターン検証（SSRF防止）
- ファイルアップロード: .txt/.pdfのみ

### 13.3 Neo4jクエリ
- すべてパラメータ化クエリ（`$variable`構文）
- 文字列結合によるCypherインジェクションなし

### 13.4 CORS
- `allow_origins`はlocalhost:5173/5174/5175のみ（`*`ではない）

---

## 14. テスト

### 14.1 テスト構成

```
backend/tests/
├── unit/                    # 354テスト
│   ├── test_models.py       # ドメインモデル
│   ├── test_agents/         # エージェント（base + 7種concrete）
│   ├── test_oasis.py        # OASISエンジン
│   ├── test_events.py       # イベントシステム
│   ├── test_scenario_analyzer.py  # シナリオ解析 + 補間
│   ├── test_reports.py      # レポート生成
│   ├── test_prediction.py   # 予測
│   ├── test_evaluation.py   # ベンチマーク評価
│   ├── test_agent_memory.py # グラフ記録
│   ├── test_fetcher.py      # GitHub取得
│   └── ...
├── integration/             # 統合テスト
└── e2e/                     # E2Eテスト
```

### 14.2 実行方法

```bash
cd backend
uv run pytest                    # 全テスト実行
uv run pytest tests/unit         # ユニットテストのみ
uv run pytest -x -v              # 最初の失敗で停止、詳細表示
```

### 14.3 開発後の必須ワークフロー

```
1. /test           — 全テスト実行、失敗を修正
2. /security-review — シークレット漏洩、インジェクションリスクを検査
3. /refactor        — コード品質、重複、型安全性をレビュー
→ 3つすべてパスしてからコミット
```

---

## 15. プロジェクト構造

```
EchoShoal/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # APIエンドポイント
│   │   │   ├── simulations.py   # シミュレーションCRUD + 実行
│   │   │   ├── reports.py       # レポート生成
│   │   │   ├── predictions.py   # 予測 + シナリオ比較
│   │   │   ├── data_sources.py  # e-Stat統計データ
│   │   │   └── evaluation.py    # ベンチマーク評価
│   │   ├── core/
│   │   │   ├── llm/router.py    # LLMルーティング（Ollama/Claude/OpenAI）
│   │   │   ├── nlp/analyzer.py  # ルールベース辞書NLP
│   │   │   ├── graph/
│   │   │   │   ├── client.py    # Neo4jクライアント
│   │   │   │   ├── schema.py    # グラフスキーマ管理
│   │   │   │   ├── rag.py       # GraphRAGリトリーバー
│   │   │   │   └── agent_memory.py  # エージェント記憶（可視性制御）
│   │   │   ├── documents/
│   │   │   │   ├── parser.py    # 文書パーサー
│   │   │   │   ├── processor.py # 文書処理→Neo4j
│   │   │   │   └── fetcher.py   # GitHub README取得
│   │   │   ├── redis_client.py  # Redisクライアント
│   │   │   └── job_manager.py   # 非同期ジョブ管理
│   │   ├── simulation/
│   │   │   ├── models.py        # ドメインモデル定義
│   │   │   ├── models.py        # ドメインモデル定義
│   │   │   ├── factory.py       # デフォルトエージェント生成
│   │   │   ├── agent_generator.py  # LLMによる動的エージェント生成
│   │   │   ├── scenario_analyzer.py # シナリオ解析 + LLM補間
│   │   │   ├── agents/
│   │   │   │   ├── base.py      # BaseAgent + Personality
│   │   │   │   ├── enterprise_agent.py
│   │   │   │   ├── freelancer_agent.py
│   │   │   │   ├── indie_dev_agent.py
│   │   │   │   ├── government_agent.py
│   │   │   │   ├── investor_agent.py
│   │   │   │   ├── platformer_agent.py
│   │   │   │   ├── community_agent.py
│   │   │   │   ├── end_user_agent.py
│   │   │   │   └── utils.py
│   │   │   └── events/
│   │   │       ├── models.py    # イベントモデル
│   │   │       ├── scheduler.py # イベントスケジューラ
│   │   │       └── effects.py   # イベント効果適用
│   │   ├── oasis/                  # OASIS統合（SNS空間シミュレーション）
│   │   │   ├── config.py          # OASIS + CAMEL-AI設定
│   │   │   ├── simulation_runner.py # OASISSimulationEngine
│   │   │   ├── profile_generator.py # エージェント→OASISプロファイル変換
│   │   │   ├── action_analyzer.py # SNSアクション→市場影響分析
│   │   │   └── graph_sync.py     # OASIS SQLite→Neo4j同期
│   │   ├── prediction/
│   │   │   ├── trend.py         # 線形回帰・移動平均
│   │   │   ├── comparator.py    # シナリオ比較
│   │   │   └── models.py        # 予測モデル
│   │   ├── reports/
│   │   │   ├── generator.py     # レポート生成（7セクション + 成功スコア）
│   │   │   ├── extractor.py     # データ抽出
│   │   │   └── models.py        # レポートモデル
│   │   ├── evaluation/
│   │   │   ├── benchmarks.py    # 9つの歴史的ベンチマーク
│   │   │   ├── comparator.py    # 精度評価
│   │   │   ├── runner.py        # ベンチマーク実行
│   │   │   └── models.py        # 評価モデル
│   │   ├── config.py            # 設定（pydantic-settings）
│   │   └── main.py              # FastAPIアプリ
│   └── tests/                   # 354テスト
├── frontend/
│   └── src/
│       ├── api/
│       │   ├── client.ts        # APIクライアント
│       │   └── types.ts         # TypeScript型定義
│       ├── pages/
│       │   ├── HomePage.tsx
│       │   ├── NewSimulationPage.tsx
│       │   ├── SimulationPage.tsx
│       │   └── ReportPage.tsx
│       ├── components/
│       │   ├── NavBar.tsx         # ナビゲーションヘッダー
│       │   ├── ProgressBar.tsx    # 進捗バー
│       │   ├── MarketChart.tsx    # ディメンション推移チャート
│       │   ├── AgentTable.tsx     # エージェント一覧
│       │   ├── AgentPersonaCard.tsx # パーソナリティレーダーモーダル
│       │   ├── RelationshipGraph.tsx # D3力学グラフ
│       │   ├── SocialFeed.tsx     # SNS投稿フィード
│       │   ├── ActionTimeline.tsx  # 行動タイムライン
│       │   └── DocumentUpload.tsx # 文書アップロード
│       └── App.tsx              # ルーティング
├── docker-compose.yml           # Neo4j + Redis
├── CLAUDE.md                    # 開発ガイドライン
└── README.md                    # プロジェクト説明
```
