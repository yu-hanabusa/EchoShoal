# EchoShoal フロントエンドアーキテクチャ

## 1. 技術スタック

| 技術 | バージョン | 用途 |
|------|----------|------|
| React | 19.2.4 | UIフレームワーク |
| TypeScript | 5.9.3 | 型安全な開発 |
| Vite | 8.0.0 | ビルドツール + 開発サーバー |
| React Router | 7.13.1 | クライアントサイドルーティング |
| TanStack React Query | 5.90.21 | サーバー状態管理 |
| Tailwind CSS | 4.2.1 | ユーティリティファーストCSS |
| Recharts | 3.8.0 | LineChart, RadarChart |
| D3 | 3.0.0 | 力学グラフ可視化 |
| react-markdown | 10.1.0 | Markdown レンダリング |

## 2. ルーティング構成

```
BrowserRouter
  └── Routes
      ├── /                        → HomePage
      ├── /new                     → NewSimulationPage
      ├── /simulation/:jobId       → SimulationPage
      ├── /simulation/:jobId/report → ReportPage
      ├── /benchmarks              → BenchmarkListPage
      └── /benchmark/:jobId        → BenchmarkResultPage
```

## 3. コンポーネントツリー

```
App
├── QueryClientProvider (React Query)
│   └── BrowserRouter (React Router)
│       └── NavBar ──────────────────── 全ページ共通ヘッダー
│           │
│           ├── HomePage ────────────── シミュレーション一覧
│           │   └── (テーブル行 × N)
│           │       ├── 状態ラベル (色分け)
│           │       ├── 名前 (インライン編集可能)
│           │       └── 削除ボタン
│           │
│           ├── NewSimulationPage ──── 新規作成フォーム
│           │   ├── サービス名入力
│           │   ├── GitHub URL入力
│           │   ├── サービス説明テキストエリア
│           │   ├── シナリオテキストエリア
│           │   ├── ファイルアップロード (複数)
│           │   └── シミュレーション期間スライダー
│           │
│           ├── SimulationPage ─────── 実行/結果表示
│           │   │
│           │   ├── [Running状態]
│           │   │   └── ProgressBar ── 進捗バー + ラウンド表示
│           │   │
│           │   └── [Completed状態]
│           │       ├── サマリーカード (定性評価4項目)
│           │       ├── RelationshipGraph ── D3力学グラフ
│           │       │   ├── タイムスライダー
│           │       │   ├── ノードドラッグ
│           │       │   ├── ズーム
│           │       │   └── エージェント詳細パネル
│           │       ├── SocialFeed ───── SNS投稿フィード
│           │       │   ├── テキストフィルター
│           │       │   ├── 投稿カード × N
│           │       │   └── 展開式コメント
│           │       ├── OASISプラットフォーム統計
│           │       ├── MarketChart ──── 成長系ディメンション
│           │       ├── MarketChart ──── リスク系ディメンション
│           │       └── AgentPersonaCard (モーダル)
│           │           └── RadarChart (性格6軸)
│           │
│           ├── ReportPage ──────────── AIレポート表示
│           │   ├── ScoreGauge ─────── 成功スコアゲージ (0-100)
│           │   ├── SectionNav ─────── スティッキーセクションナビ
│           │   ├── エグゼクティブサマリー (Markdown)
│           │   ├── DimensionRadar ─── 8次元レーダーチャート
│           │   ├── DimensionSparkline ─ ディメンション別ミニチャート
│           │   ├── RiskOpportunityCard ─ リスク/機会カード
│           │   ├── 予測ハイライト
│           │   └── レポートセクション × 6 (Markdown)
│           │
│           ├── BenchmarkListPage ──── ベンチマーク一覧
│           │   └── ベンチマークカード × N
│           │
│           └── BenchmarkResultPage ── ベンチマーク結果表示
```

## 4. 状態管理設計

### 4.1 サーバー状態（React Query）

Redux/Contextは使用しない。全てのサーバー状態はReact Queryで管理する。

```
QueryClient
├── staleTime: 30秒
├── retry: 1回
│
├── queryKey: ["simulations"]
│   └── listSimulations(skip, limit)
│
├── queryKey: ["simulation", jobId]
│   └── getSimulation(jobId)
│       refetchInterval:
│         status === "running" || "queued" → 2000ms
│         それ以外 → false (ポーリング停止)
│
├── queryKey: ["report", jobId]
│   └── getReport(jobId)
│
└── queryKey: ["prediction", jobId]
    └── getPrediction(jobId)
```

### 4.2 クライアント状態（React useState）

```
HomePage:
├── page: number           # ページネーション
├── editingId: string      # インライン編集中のジョブID
└── editValue: string      # 編集中の名前

NewSimulationPage:
├── serviceName: string    # サービス名
├── serviceUrl: string     # GitHub URL
├── serviceDescription: string # サービス説明
├── description: string    # シナリオ説明
├── numRounds: number      # シミュレーション期間
├── files: File[]          # アップロードファイル
└── submitting: boolean    # 送信中フラグ

RelationshipGraph:
├── selectedRound: number  # タイムスライダーの現在位置
└── selectedAgent: string  # 選択中のエージェントID

SocialFeed:
├── expanded: Set<string>  # 展開中の投稿ID
└── filter: string         # テキストフィルター
```

## 5. APIクライアント設計

```
api/client.ts
│
├── request<T>(path, options)     # 共通fetchラッパー
│   ├── Content-Type: application/json
│   ├── エラー時: res.detail からメッセージ抽出
│   └── ベースURL: /api (Viteプロキシ → localhost:8000)
│
├── listSimulations(skip, limit)  → GET  /api/simulations/
├── getSimulation(jobId)          → GET  /api/simulations/{id}
├── getProgress(jobId)            → GET  /api/simulations/{id}/progress
├── getReport(jobId)              → GET  /api/simulations/{id}/report
├── getPrediction(jobId)          → GET  /api/simulations/{id}/prediction
├── getSimulationDocuments(jobId) → GET  /api/simulations/{id}/documents
├── getSimulationGraph(jobId)     → GET  /api/simulations/{id}/graph
├── compareSimulations(base, alt) → GET  /api/simulations/{base}/compare/{alt}
├── uploadSimulationDocument()    → POST /api/simulations/{id}/documents
├── updateSimulation(jobId, data) → PATCH /api/simulations/{id}
├── deleteSimulation(jobId)       → DELETE /api/simulations/{id}
└── healthCheck()                 → GET  /api/health
```

## 6. 型定義体系

```
api/types.ts

JobStatus = "created" | "queued" | "running" | "completed" | "failed"

ScenarioInput                    ← シミュレーション作成パラメータ
├── description: string
├── num_rounds: number
├── service_name?: string
├── service_url?: string
└── target_market?: string

JobInfo                          ← シミュレーション情報
├── job_id: string
├── status: JobStatus
├── scenario_name?: string
├── progress?: { current_round, total_rounds, phase }
├── scenario?: ScenarioInput
├── result?: SimulationResult
└── error?: string

SimulationResult                 ← シミュレーション結果
├── scenario: ScenarioInput
├── summary: string
├── rounds: RoundResult[]
├── agents?: AgentSummary[]
├── relationships?: Relationship[]
├── social_feed?: SocialPost[]
├── oasis_stats?: OasisStats
└── report?: SimulationReport

RoundResult                      ← 1ラウンドの結果
├── round_number: number
├── market_state: ServiceMarketState
├── actions_taken: ActionTaken[]
├── events: string[]
└── summary?: string

ServiceMarketState               ← 市場の8次元 + マクロ指標
├── dimensions: Record<string, number>  (0.0〜1.0)
├── economic_sentiment: number
├── tech_hype_level: number
├── regulatory_pressure: number
└── ai_disruption_level: number

AgentSummary                     ← エージェント情報
├── agent_id, name, agent_type, stakeholder_type
├── headcount, revenue, satisfaction, reputation
├── personality?: AgentPersonality
└── description?: string

AgentPersonality                 ← 性格パラメータ（6軸）
├── conservatism: number         (0-1)
├── bandwagon: number            (0-1)
├── overconfidence: number       (0-1)
├── sunk_cost_bias: number       (0-1)
├── info_sensitivity: number     (0-1)
├── noise: number                (0-0.3)
└── description?: string

SocialPost                       ← OASIS SNS投稿
├── post_id, author_name, content, round
├── likes, dislikes, shares
├── comments: SocialComment[]
└── created_at

SimulationReport                 ← AIレポート
├── title, executive_summary
├── success_score: SuccessScore
├── sections: { title, content }[]
└── generated_at

SuccessScore                     ← 成功スコア
├── score: number                (0-100)
├── verdict: string              ("成功見込み" / "要注意" / "困難")
├── key_factors: string[]
├── risks: string[]
└── opportunities: string[]

PredictionResult                 ← 定量予測
├── dimension_predictions: { dimension, current, predicted, trend, change_rate }[]
├── macro_predictions: { indicator, current, predicted, trend }[]
└── highlights: string[]
```

## 7. デザインシステム

### 7.1 カラーパレット

```css
/* ブランド・インタラクティブ */
--color-brand: #1e293b            /* ロゴ、プライマリ */
--color-interactive: #4f46e5      /* ボタン、リンク */
--color-interactive-hover: #4338ca /* ホバー */
--color-interactive-light: #eef2ff /* 背景アクセント */

/* セマンティックカラー */
--color-positive: #059669         /* 成長、良好 (成功スコア≥70) */
--color-negative: #e11d48         /* 低下、悪化 (成功スコア<40) */
--color-caution: #d97706          /* 警告 (成功スコア 40-69) */
--color-neutral: #64748b          /* 非アクティブ */

/* サーフェス */
--color-surface-0: #ffffff        /* カード背景 */
--color-surface-1: #f8fafc        /* ページ背景 */
--color-surface-2: #f1f5f9        /* ホバー背景 */

/* テキスト */
--color-text-primary: #0f172a     /* 見出し、本文 */
--color-text-secondary: #475569   /* 補足テキスト */
--color-text-tertiary: #94a3b8    /* ヒント */
```

### 7.2 ディメンション色定義

```
user_adoption:        #22c55e (緑)     ユーザー獲得率
revenue_potential:    #3b82f6 (青)     収益ポテンシャル
tech_maturity:        #8b5cf6 (紫)     技術成熟度
competitive_pressure: #ef4444 (赤)     競合圧力
regulatory_risk:      #f97316 (橙)     規制リスク
market_awareness:     #eab308 (黄)     市場認知度
ecosystem_health:     #06b6d4 (シアン)  エコシステム健全性
funding_climate:      #6b7280 (灰)     資金調達環境
```

### 7.3 フォントスタック

```
Inter, "Hiragino Kaku Gothic ProN", "Noto Sans JP", system-ui, sans-serif
```

## 8. コンポーネント詳細

### 8.1 RelationshipGraph（力学グラフ）

```
Props:
├── rounds: RoundResult[]           # 全ラウンド結果
├── agents: AgentSummary[]          # エージェント情報
├── serviceName?: string            # サービス名（中心に固定）
└── initialRelationships?: Relationship[] # 初期関係

機能:
├── D3 force-directed レイアウト
│   ├── link distance: 関係タイプにより調整
│   ├── charge: -200 (反発力)
│   ├── center: SVGの中心
│   └── collision: ノード半径による衝突回避
│
├── ノード
│   ├── サービスノード: 中心に固定、最大サイズ
│   ├── エージェントノード: stakeholder_typeで色分け
│   └── 選択時: 詳細パネル表示
│
├── エッジ（3種類の統合）
│   ├── 初期関係 (initialRelationships)
│   ├── アクションベース (reacting_to から構築)
│   └── 間接関係 (同じ話題への言及)
│
├── インタラクション
│   ├── タイムスライダー: ラウンドごとに表示切替
│   ├── ドラッグ: ノードを移動
│   ├── ズーム: スクロールで拡大/縮小
│   └── クリック: エージェント詳細パネル
│
└── サイズ: 700×500px (viewBox)
```

### 8.2 MarketChart（ディメンション推移チャート）

```
Props:
├── rounds: RoundResult[]     # 全ラウンド結果
├── title: string             # チャートタイトル
└── dimensions?: string[]     # 表示するディメンション

機能:
├── Recharts LineChart
├── マルチライン（1ディメンション=1ライン）
├── DIMENSION_COLORSで色分け
├── ツールチップ（月表示）
├── 凡例（日本語ラベル）
└── レスポンシブ幅、固定高260px
```

### 8.3 SocialFeed（SNSフィード）

```
Props:
├── feed: SocialPost[]         # OASIS投稿一覧
└── agents?: AgentSummary[]    # エージェント情報（種別表示用）

機能:
├── スクロール可能リスト（最大600px）
├── テキストフィルター（著者名・内容検索）
├── 投稿カード
│   ├── アバター（名前ハッシュから色生成）
│   ├── 著者名 + ステークホルダー種別ラベル
│   ├── ラウンドバッジ
│   ├── 投稿内容（タグ・JSON・Unicode除去済み）
│   └── エンゲージメント指標（いいね/低評価/共有/コメント数）
└── 展開式コメント
    └── コメント内容 + 著者名
```

### 8.4 AgentPersonaCard

```
AgentPersonaCard Props:
├── agent: AgentSummary        # エージェント詳細
└── onClose: () => void        # 閉じるコールバック

機能:
├── モーダルオーバーレイ
├── Recharts RadarChart（6軸パーソナリティ）
│   ├── conservatism (保守性)
│   ├── bandwagon (同調性)
│   ├── overconfidence (過信度)
│   ├── sunk_cost_bias (埋没費用バイアス)
│   ├── info_sensitivity (情報感度)
│   └── noise (ノイズ)
├── エージェント種別バッジ
├── 財務指標（売上、人員、満足度、評判）
└── 説明テキスト
```

### 8.5 ScoreGauge（成功スコアゲージ）

```
Props:
├── score: number              # 0-100
├── verdict: string            # "成功見込み" / "要注意" / "困難"
└── size?: number              # ゲージサイズ

機能:
├── SVG円弧ゲージ
├── 色分け（緑≥70/黄≥40/赤<40）
└── 中央にスコア数値 + 判定テキスト
```

### 8.6 DimensionRadar（レーダーチャート）

```
Props:
└── dimensions: Record<string, number>  # 8次元の最終値

機能:
├── Recharts RadarChart
├── 8軸で市場状態をスナップショット表示
└── ディメンション色に対応
```

### 8.7 DimensionSparkline（ミニトレンドチャート）

```
Props:
├── data: number[]             # ラウンド別の値
├── color: string              # ライン色
└── width/height               # サイズ

機能:
├── 小さなインラインラインチャート
└── ディメンション別トレンドを一目で表示
```

### 8.8 RiskOpportunityCard（リスク/機会カード）

```
Props:
├── items: string[]            # リスクまたは機会のリスト
├── type: "risk" | "opportunity"
└── title: string

機能:
├── アイコン付きリスト表示
└── リスク=赤、機会=緑の色分け
```

### 8.9 SectionNav（セクションナビゲーション）

```
Props:
└── sections: { id, label }[]  # ナビゲーション項目

機能:
├── スティッキーサイドバー
├── スクロール位置に応じてアクティブ項目をハイライト
└── クリックで該当セクションへスクロール
```

## 9. ビルド・開発構成

```
vite.config.ts:
├── plugins: [react(), tailwindcss()]
├── server.port: 5173
└── server.proxy:
    ├── /api → http://localhost:8000
    └── /ws  → ws://localhost:8000

tsconfig.json:
├── target: ES2023
├── strict: true
├── noUnusedLocals: true
├── noUnusedParameters: true
└── jsx: react-jsx

開発コマンド:
├── pnpm dev      → Vite開発サーバー (:5173)
├── pnpm build    → tsc + vite build
└── pnpm preview  → ビルド結果プレビュー
```

## 10. 設計判断の記録

| 判断 | 理由 |
|------|------|
| React Query のみ（Redux/Context不使用） | 全データがサーバー由来。クライアント専用状態は各コンポーネントのuseStateで十分 |
| スマートポーリング（refetchInterval関数） | running/queued時のみ2秒ポーリング。完了後は停止しサーバー負荷を削減 |
| D3直接操作（React仮想DOMと分離） | force-directedグラフはDOMの直接操作が必要。Reactの再レンダリングと干渉しないようuseEffect内で完結 |
| Tailwindユーティリティファースト | CSSファイル不要（index.css以外）。コンポーネントとスタイルが一体化し保守性向上 |
| 反転メトリクス（competitive_pressure等） | competitive_pressureやregulatory_riskは低い方が良い。UIでは 1-value で「優位度」として表示 |
| Markdown レンダリング | バックエンドがMarkdown形式でレポート返却。フロントでHTMLに変換し一貫した表示 |
| FormData送信（JSON不使用） | ファイルアップロードを含むためmultipart/form-dataが必須 |
| ダークモード非実装 | ライトモードのみ。ビジネスツールとしてシンプルさを優先 |
