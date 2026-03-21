# EchoShoal システムアーキテクチャ

## 1. システム全体構成図

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ユーザー（ブラウザ）                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP (localhost:5173)
┌──────────────────────────────┴──────────────────────────────────────┐
│                   Frontend (React 19 + TypeScript)                   │
│                                                                      │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ HomePage │  │NewSimulation   │  │ Simulation   │  │ Report    │  │
│  │ /        │  │Page /new       │  │ Page /:jobId │  │ Page      │  │
│  └──────────┘  └────────────────┘  └──────────────┘  └───────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ 共通コンポーネント                                            │    │
│  │ NavBar │ ProgressBar │ MarketChart │ SocialFeed              │    │
│  │ RelationshipGraph │ AgentPersonaCard │ ScoreGauge            │    │
│  │ DimensionRadar │ DimensionSparkline │ SectionNav             │    │
│  │ RiskOpportunityCard                                          │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌────────────────────────────────────────┐                          │
│  │ API Client (fetch) + React Query       │                          │
│  │ サーバー状態管理 │ ポーリング │ キャッシュ │                          │
│  └────────────────────────┬───────────────┘                          │
└───────────────────────────┼──────────────────────────────────────────┘
                            │ REST API (Vite proxy → localhost:8000)
┌───────────────────────────┴──────────────────────────────────────────┐
│                    Backend (FastAPI + Python 3.13)                    │
│                                                                      │
│  ┌─────────────────────── API Layer ──────────────────────────────┐  │
│  │ /api/simulations/  │ /api/simulations/{id}/report             │  │
│  │ /api/simulations/{id}/prediction │ /api/evaluation/           │  │
│  │ /api/data/ │ /api/health                                      │  │
│  └──────────────────────────┬────────────────────────────────────┘  │
│                              │                                       │
│  ┌──────────── Application Layer ─────────────────────────────────┐  │
│  │                                                                │  │
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   │  │
│  │  │  Scenario     │   │  Simulation  │   │  Report          │   │  │
│  │  │  Analyzer     │──▶│  Engine      │──▶│  Generator       │   │  │
│  │  │  (NLP+LLM)    │   │  (OASIS)     │   │  (Claude API)    │   │  │
│  │  └──────────────┘   └──────────────┘   └──────────────────┘   │  │
│  │          │                  │                     │             │  │
│  │  ┌───────┴──────┐   ┌──────┴───────┐   ┌────────┴─────────┐  │  │
│  │  │  Agent       │   │  Event       │   │  Prediction      │  │  │
│  │  │  Generator   │   │  Scheduler   │   │  & Comparator    │  │  │
│  │  │  (LLM動的生成)│   │  (LLMイベント)│   │  (線形回帰)      │  │  │
│  │  └──────────────┘   └──────────────┘   └──────────────────┘  │  │
│  │                                                                │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
│                                │                                     │
│  ┌─────────────── Core Services Layer ────────────────────────────┐  │
│  │                                                                │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │  │
│  │  │ LLM      │  │ NLP      │  │ Graph    │  │ Document     │  │  │
│  │  │ Router   │  │ Analyzer │  │ Client   │  │ Processor    │  │  │
│  │  │          │  │ (辞書)   │  │ (Neo4j)  │  │ (PDF/TXT)    │  │  │
│  │  └────┬─────┘  └──────────┘  └────┬─────┘  └──────────────┘  │  │
│  │       │                            │                           │  │
│  │  ┌────┴─────┐  ┌──────────┐  ┌────┴─────┐  ┌──────────────┐  │  │
│  │  │ Agent    │  │ GraphRAG │  │ Data     │  │ Job          │  │  │
│  │  │ Memory   │  │ Retriever│  │ Sources  │  │ Manager      │  │  │
│  │  │ Store    │  │ (可視性)  │  │ (e-Stat) │  │ (Redis)      │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │  │
│  │                                                                │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────┬──────────────┬──────────────┬──────────────┬─────────────────┘
       │              │              │              │
  ┌────┴────┐   ┌─────┴────┐   ┌────┴────┐   ┌────┴────────┐
  │ Ollama  │   │  Neo4j   │   │  Redis  │   │ Claude API  │
  │ qwen2.5 │   │  (Graph  │   │  (Job   │   │ / OpenAI    │
  │ :14b    │   │   DB)    │   │  Queue) │   │  API        │
  │ :11434  │   │  :7687   │   │  :6379  │   │  (外部)      │
  └─────────┘   └──────────┘   └─────────┘   └─────────────┘
   ローカルLLM    Docker         Docker         クラウドLLM
```

## 2. コンポーネント責務一覧

### 2.1 API Layer

| コンポーネント | ファイル | 責務 |
|--------------|---------|------|
| Simulations API | `api/routes/simulations.py` | シミュレーションのCRUD・実行・進捗取得 |
| Reports API | `api/routes/reports.py` | AIレポート取得（JSON/Markdown） |
| Predictions API | `api/routes/predictions.py` | 定量予測・シナリオ比較 |
| Evaluation API | `api/routes/evaluation.py` | ベンチマーク実行・統計評価 |
| Data Sources API | `api/routes/data_sources.py` | e-Stat統計データ収集 |

### 2.2 Application Layer

| コンポーネント | ファイル | 責務 |
|--------------|---------|------|
| ScenarioAnalyzer | `simulation/scenario_analyzer.py` | NLP＋LLMでシナリオを解析・補間 |
| AgentGenerator | `simulation/agent_generator.py` | LLMがシナリオに適したエージェントを動的生成 |
| OASISSimulationEngine | `oasis/simulation_runner.py` | OASIS SNS空間でのシミュレーション実行 |
| EventScheduler | `simulation/events/scheduler.py` | LLMが市場イベントを生成・スケジューリング |
| ReportGenerator | `reports/generator.py` | Claude APIで7セクション＋成功スコアのレポート生成 |
| TrendAnalyzer | `prediction/trend.py` | 線形回帰・移動平均・6ヶ月予測 |
| PredictionComparator | `prediction/comparator.py` | 2シナリオの差分比較 |
| BenchmarkRunner | `evaluation/runner.py` | ベンチマーク実行・統計評価 |

### 2.3 Core Services Layer

| コンポーネント | ファイル | 責務 |
|--------------|---------|------|
| LLMRouter | `core/llm/router.py` | タスク種別に応じてOllama/Claude/OpenAIにルーティング |
| NLPAnalyzer | `core/nlp/analyzer.py` | ルールベース辞書による技術名・政策名抽出 |
| GraphClient | `core/graph/client.py` | Neo4j非同期クライアント |
| GraphRAGRetriever | `core/graph/rag.py` | 可視性制御付きコンテキスト取得 |
| AgentMemoryStore | `core/graph/agent_memory.py` | エージェントの行動履歴をNeo4jに記録 |
| DocumentProcessor | `core/documents/processor.py` | 文書パース→NLP解析→Neo4j格納 |
| DataCollectionPipeline | `core/data_sources/pipeline.py` | e-Stat統計データ収集→Neo4j格納 |
| JobManager | `core/job_manager.py` | Redis上の非同期ジョブライフサイクル管理 |
| RedisClient | `core/redis_client.py` | Redis非同期ラッパー |

### 2.4 Agent Types（8種）

| エージェント | ファイル | ステークホルダー | 主要アクション |
|-------------|---------|--------------|--------------|
| EnterpriseAgent | `agents/enterprise_agent.py` | 企業 | adopt, reject, build_competitor, acquire, partner |
| FreelancerAgent | `agents/freelancer_agent.py` | フリーランス | adopt_tool, offer_service, upskill, switch_platform |
| IndieDevAgent | `agents/indie_dev_agent.py` | 個人開発者 | launch_competing, pivot, open_source, monetize |
| GovernmentAgent | `agents/government_agent.py` | 行政 | regulate, subsidize, certify, deregulate |
| InvestorAgent | `agents/investor_agent.py` | 投資家/VC | invest_seed, invest_series, divest, fund_competitor |
| PlatformerAgent | `agents/platformer_agent.py` | プラットフォーマー | launch_feature, acquire, restrict_api, price_undercut |
| CommunityAgent | `agents/community_agent.py` | 業界団体 | endorse, set_standard, create_alternative |
| EndUserAgent | `agents/end_user_agent.py` | エンドユーザー | adopt, trial, churn, recommend, complain |

## 3. 外部サービス依存関係

```
┌─────────────────────────────────────────────┐
│              EchoShoal Backend               │
├─────────────────────────────────────────────┤
│                                              │
│  軽量LLMタスク ──────────▶ Ollama (ローカル)  │
│  ・エージェント意思決定       qwen2.5:14b     │
│  ・市場状態更新               :11434          │
│  ・イベント生成                               │
│  ・エージェント面談                            │
│                                              │
│  重量LLMタスク ──────────▶ Claude API (外部)  │
│  ・レポート生成               claude-sonnet   │
│  ・成功スコア算出                             │
│  ・ペルソナ生成                               │
│  ・オントロジー設計                            │
│  （フォールバック: OpenAI / Ollama）           │
│                                              │
│  知識グラフ ─────────────▶ Neo4j (Docker)     │
│  ・エージェント記憶             :7687          │
│  ・因果チェーン                               │
│  ・文書エンティティ                            │
│  ・スキル・企業・政策ノード                     │
│                                              │
│  ジョブ管理 ─────────────▶ Redis (Docker)     │
│  ・ジョブ状態管理               :6379          │
│  ・シナリオ保存                               │
│  ・結果キャッシュ（7日TTL）                    │
│                                              │
│  日本語NLP ──────────────▶ ルールベース辞書    │
│  ・技術名抽出（正規表現）                      │
│  ・政策名抽出（正規表現）                      │
│                                              │
│  OASIS ──────────────────▶ SQLite (ローカル)  │
│  ・SNSインタラクションDB                      │
│  ・シミュレーションごとに1DB                   │
│                                              │
│  統計データ ─────────────▶ e-Stat API (外部)  │
│  ・日本の産業統計                             │
│                                              │
└─────────────────────────────────────────────┘
```

## 4. LLMルーティング

```
                    ┌──────────────┐
                    │  LLM Router  │
                    │  (router.py) │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         Light Tasks   Heavy Tasks   Fallback
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Ollama  │ │  Claude  │ │  OpenAI  │
        │ Client   │ │ Client   │ │ Client   │
        └──────────┘ └──────────┘ └──────────┘

Light Tasks (Ollama):          Heavy Tasks (Claude/OpenAI):
- AGENT_DECISION               - REPORT_GENERATION
- EMOTION_UPDATE               - ONTOLOGY_DESIGN
                               - USER_CHAT
                               - PERSONA_GENERATION
```

## 5. シミュレーションエンジン

```
OASISSimulationEngine
  │
  ├─ CAMEL-AI OASIS フレームワーク
  ├─ X(Twitter)/Reddit 的SNS空間
  ├─ エージェント間の投稿・コメント・リポスト
  ├─ 自動的な関係グラフ成長
  ├─ SQLiteにインタラクション記録
  └─ Neo4jへ同期
```

## 6. ジョブ状態遷移

```
    ┌─────────┐    POST /api/simulations/     ┌─────────┐
    │ (なし)  │ ─────────────────────────────▶ │ CREATED │
    └─────────┘                                └────┬────┘
                                                    │ 文書処理完了
                                                    ▼
                                               ┌─────────┐
                                               │ QUEUED  │
                                               └────┬────┘
                                                    │ バックグラウンドタスク開始
                                                    ▼
                                               ┌─────────┐
                                               │ RUNNING │ ◀── 進捗更新
                                               └────┬────┘     (current/total/phase)
                                                    │
                                          ┌─────────┴─────────┐
                                          │                   │
                                          ▼                   ▼
                                   ┌───────────┐       ┌──────────┐
                                   │ COMPLETED │       │  FAILED  │
                                   └───────────┘       └──────────┘
                                    結果を7日間Redis       エラー情報
                                    に保存                 を記録

Redis Key Pattern:
  job:{job_id}:status   → ジョブ状態メタデータ
  job:{job_id}:result   → シミュレーション結果
  job:{job_id}:progress → 進捗情報 (current_round, total_rounds, phase)
  job:{job_id}:scenario → ScenarioInput
  jobs:index            → 全ジョブのソート済みセット
```

## 7. ネットワーク構成

```
localhost
├── :5173   Frontend (Vite dev server)
│            └── /api/* → proxy → :8000
├── :8000   Backend (FastAPI + Uvicorn)
├── :7474   Neo4j Browser (Web UI)
├── :7687   Neo4j Bolt Protocol
├── :6379   Redis
└── :11434  Ollama API

外部ネットワーク
├── api.anthropic.com       Claude API
├── api.openai.com          OpenAI API
├── api.e-stat.go.jp        e-Stat統計API
└── api.github.com          GitHub API (README取得)
```

## 8. ディレクトリ構成（全体）

```
EchoShoal/
├── backend/                          # Python 3.13 + FastAPI
│   ├── app/
│   │   ├── main.py                   # FastAPIアプリ + CORS + ルーティング
│   │   ├── config.py                 # pydantic-settings設定
│   │   │
│   │   ├── api/routes/               # ── API Layer ──
│   │   │   ├── simulations.py        # シミュレーション CRUD + 実行
│   │   │   ├── reports.py            # レポート取得
│   │   │   ├── predictions.py        # 予測 + 比較
│   │   │   ├── evaluation.py         # ベンチマーク評価
│   │   │   └── data_sources.py       # e-Stat データ収集
│   │   │
│   │   ├── simulation/               # ── Application Layer ──
│   │   │   ├── models.py             # ドメインモデル定義
│   │   │   ├── scenario_analyzer.py  # シナリオ解析 + LLM補間
│   │   │   ├── agent_generator.py    # 動的エージェント生成
│   │   │   ├── factory.py            # デフォルトエージェント（8体）
│   │   │   ├── agents/               # 8種のステークホルダーエージェント
│   │   │   │   ├── base.py           # BaseAgent + Personality + Action
│   │   │   │   ├── enterprise_agent.py
│   │   │   │   ├── freelancer_agent.py
│   │   │   │   ├── indie_dev_agent.py
│   │   │   │   ├── government_agent.py
│   │   │   │   ├── investor_agent.py
│   │   │   │   ├── platformer_agent.py
│   │   │   │   ├── community_agent.py
│   │   │   │   ├── end_user_agent.py
│   │   │   │   └── utils.py
│   │   │   └── events/               # 市場イベントシステム
│   │   │       ├── models.py         # イベントモデル
│   │   │       ├── scheduler.py      # LLM駆動イベント生成
│   │   │       └── effects.py        # イベント効果適用
│   │   │
│   │   ├── oasis/                    # OASIS統合 (SNS空間シミュレーション)
│   │   │   ├── config.py             # OASIS + CAMEL-AI設定
│   │   │   ├── simulation_runner.py  # OASISSimulationEngine
│   │   │   ├── profile_generator.py  # EchoShoalエージェント → OASISプロファイル
│   │   │   ├── action_analyzer.py    # SNSアクション → 市場影響分析
│   │   │   └── graph_sync.py         # OASIS SQLite → Neo4j同期
│   │   │
│   │   ├── prediction/               # 定量予測
│   │   │   ├── models.py
│   │   │   ├── trend.py              # 線形回帰 + 移動平均
│   │   │   └── comparator.py         # シナリオ比較
│   │   │
│   │   ├── reports/                  # レポート生成
│   │   │   ├── models.py
│   │   │   ├── generator.py          # Claude API でレポート生成
│   │   │   └── extractor.py          # ラウンドデータ抽出
│   │   │
│   │   ├── evaluation/               # ベンチマーク評価
│   │   │   ├── benchmarks.py         # 9つの歴史的ベンチマーク定義
│   │   │   ├── models.py
│   │   │   ├── runner.py             # ベンチマーク実行 (単発/統計/一括)
│   │   │   ├── comparator.py         # トレンド方向精度検証
│   │   │   └── scenarios/            # ベンチマーク補足資料
│   │   │
│   │   └── core/                     # ── Core Services Layer ──
│   │       ├── llm/
│   │       │   ├── router.py         # タスク種別→プロバイダ ルーティング
│   │       │   ├── base.py           # LLMクライアント抽象基底
│   │       │   ├── ollama_client.py  # Ollama HTTP クライアント
│   │       │   ├── claude_client.py  # Anthropic Claude API
│   │       │   └── openai_client.py  # OpenAI API
│   │       ├── nlp/
│   │       │   └── analyzer.py       # ルールベース辞書NLP
│   │       ├── graph/
│   │       │   ├── client.py         # Neo4j非同期ドライバ
│   │       │   ├── schema.py         # グラフスキーマ + リポジトリ
│   │       │   ├── rag.py            # GraphRAG (可視性制御付きコンテキスト取得)
│   │       │   └── agent_memory.py   # エージェント行動記録
│   │       ├── documents/
│   │       │   ├── parser.py         # PDF/DOCX/TXT パーサー
│   │       │   ├── processor.py      # 文書 → NLP → Neo4j
│   │       │   ├── fetcher.py        # GitHub README 取得
│   │       │   └── models.py
│   │       ├── data_sources/
│   │       │   ├── pipeline.py       # e-Stat API オーケストレーション
│   │       │   ├── estat.py          # e-Stat API クライアント
│   │       │   └── models.py
│   │       ├── redis_client.py       # Redis非同期ラッパー
│   │       └── job_manager.py        # ジョブライフサイクル管理
│   │
│   ├── tests/                        # テストスイート
│   │   ├── unit/                     # ユニットテスト
│   │   ├── integration/              # 統合テスト
│   │   └── e2e/                      # E2Eテスト
│   └── pyproject.toml                # Python依存関係 (uv)
│
├── frontend/                         # React 19 + TypeScript + Vite
│   ├── src/
│   │   ├── main.tsx                  # エントリポイント
│   │   ├── App.tsx                   # ルーティング + React Query
│   │   ├── index.css                 # Tailwind CSS + デザインシステム
│   │   ├── api/
│   │   │   ├── client.ts            # APIクライアント (fetch)
│   │   │   └── types.ts             # TypeScript型定義
│   │   ├── pages/                    # 6ページ
│   │   └── components/              # 11コンポーネント
│   ├── package.json                  # Node依存関係 (pnpm)
│   ├── vite.config.ts                # Vite設定 + APIプロキシ
│   └── tsconfig.json                 # TypeScript設定
│
├── docs/                             # ドキュメント
├── docker-compose.yml                # Neo4j + Redis
├── CLAUDE.md                         # 開発ガイドライン
└── README.md                         # プロジェクト説明
```
