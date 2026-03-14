# EchoShoal

日本のIT人材市場予測シミュレーター。エージェントベースモデリング（ABM）とLLMを組み合わせ、SIer・SES・フリーランス・事業会社IT部門の市場動向を予測します。

## 概要

EchoShoalは「AIコーディングツール普及後のSIer業界はどう変わるか」「フリーランスエンジニアの単価はどう推移するか」といった問いに対して、シミュレーションベースの予測を提供するツールです。

### 主な特徴

- **エージェントベースシミュレーション**: 10種類のエージェント（SES企業3社、SIer企業2社、フリーランス3名、事業会社IT2社）が各ラウンドでLLMにより意思決定
- **動的イベントシステム**: シナリオに基づいて政策変更・景気変動・技術変革などのイベントをLLMが自動生成
- **日本語NLP解析**: GiNZA + ルールベース辞書でシナリオテキストから技術名・政策名を自動検出
- **定量予測**: 線形回帰・移動平均によるスキル需給・単価のトレンド分析と人材不足数の推定
- **レポート生成**: Claude API（またはOllamaフォールバック）による分析レポート自動生成
- **非同期ジョブ**: Redis によるジョブ管理とリアルタイム進捗通知

## 技術スタック

| レイヤー | 技術 |
|---|---|
| Backend | FastAPI (Python 3.13) + uv |
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS v4 |
| Graph DB | Neo4j Community Edition |
| Cache/Queue | Redis |
| LLM (light) | Ollama (qwen2.5:14b) |
| LLM (heavy) | Claude API / OpenAI API（未設定時はOllamaフォールバック） |
| NLP | GiNZA (spaCy) + ルールベース辞書 |
| Testing | pytest + pytest-asyncio + httpx |

## プロジェクト構造

```
EchoShoal/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # APIエンドポイント
│   │   │   ├── simulations.py   # POST /api/simulations/ (非同期ジョブ)
│   │   │   ├── reports.py       # GET /api/simulations/{id}/report
│   │   │   └── predictions.py   # GET /api/simulations/{id}/prediction
│   │   ├── core/
│   │   │   ├── llm/             # LLMルーター (Ollama/Claude/OpenAI)
│   │   │   ├── nlp/             # 日本語テキスト解析 (GiNZA)
│   │   │   ├── graph/           # Neo4j クライアント + 知識グラフスキーマ
│   │   │   ├── redis_client.py  # Redis クライアント
│   │   │   └── job_manager.py   # 非同期ジョブ管理
│   │   ├── simulation/
│   │   │   ├── engine.py        # シミュレーションエンジン
│   │   │   ├── models.py        # MarketState, ScenarioInput等
│   │   │   ├── factory.py       # デフォルトエージェント生成
│   │   │   ├── scenario_analyzer.py  # NLP→スキル/業界自動検出
│   │   │   ├── agents/          # エージェント4種
│   │   │   └── events/          # 外部イベントシステム
│   │   ├── prediction/          # 定量予測（トレンド分析、シナリオ比較）
│   │   └── reports/             # レポート生成（指標抽出、Claude分析）
│   └── tests/                   # 199テスト
├── frontend/
│   ├── src/
│   │   ├── api/                 # APIクライアント + 型定義
│   │   ├── pages/               # Home / Simulation / Report
│   │   └── components/          # ScenarioForm, MarketChart, AgentTable等
├── docker-compose.yml
└── CLAUDE.md
```

## セットアップ

### 必要なもの

- **Ollama**: https://ollama.com/download
- **Redis**: WSL2上にネイティブインストール、またはDocker
- **Neo4j Community Edition**: WSL2上にネイティブインストール、またはDocker
- **Python 3.12+**: uv でパッケージ管理
- **Node.js 18+**: pnpm でフロントエンド管理

### 環境構築

#### 1. Ollama（Windowsネイティブ）

```bash
# インストール後
ollama pull qwen2.5:14b
```

#### 2. Redis + Neo4j（WSL2上）

```bash
# Redis
sudo apt-get install -y redis-server
sudo service redis-server start

# Neo4j（公式リポジトリ追加後）
sudo neo4j-admin dbms set-initial-password echoshoal
sudo service neo4j start
```

#### 3. バックエンド（WSL2上）

```bash
cd ~/echoshoal/backend

# .envファイル作成
cat > .env << 'EOF'
ECHOSHOAL_OLLAMA_BASE_URL=http://localhost:11434
ECHOSHOAL_OLLAMA_MODEL=qwen2.5:14b
ECHOSHOAL_CLAUDE_API_KEY=
ECHOSHOAL_OPENAI_API_KEY=
ECHOSHOAL_DEFAULT_HEAVY_PROVIDER=claude
ECHOSHOAL_NEO4J_URI=bolt://localhost:7687
ECHOSHOAL_NEO4J_USER=neo4j
ECHOSHOAL_NEO4J_PASSWORD=echoshoal
ECHOSHOAL_REDIS_URL=redis://localhost:6379
EOF

# 依存関係インストール + 起動
uv sync
uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### 4. フロントエンド（Windows側）

```bash
cd frontend
pnpm install
pnpm dev
```

### 起動コマンド（2回目以降）

```bash
# 1. WSL2サービス起動
wsl -d Ubuntu-22.04 -- bash -c "sudo service redis-server start && sudo service neo4j start"

# 2. バックエンド起動
wsl -d Ubuntu-22.04 -- bash -lc 'export PATH="$HOME/.local/bin:$PATH"; cd ~/echoshoal/backend; uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &'

# 3. フロントエンド起動
cd frontend && pnpm dev
```

ブラウザで http://localhost:5173 にアクセス。

## API

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `/api/health` | GET | ヘルスチェック（Redis/Neo4j接続状態含む） |
| `/api/simulations/` | POST | シミュレーションジョブ作成（202 + job_id） |
| `/api/simulations/{job_id}` | GET | ジョブステータス + 結果取得 |
| `/api/simulations/{job_id}/progress` | GET | 進捗確認 |
| `/api/simulations/{job_id}/report` | GET | 分析レポート生成・取得 |
| `/api/simulations/{job_id}/prediction` | GET | 定量予測取得 |

## テスト

```bash
cd backend
uv run pytest                    # 全テスト実行
uv run pytest tests/unit         # ユニットテストのみ
uv run pytest -x -v              # 最初の失敗で停止、詳細表示
```

## 開発状況

### 実装済み（Phase 1-9）

- [x] FastAPI + React + LLMルーター
- [x] シミュレーションエンジン（エージェント4種、ラウンド制ABM）
- [x] Neo4j知識グラフスキーマ + GiNZA NLP + シナリオ解析
- [x] 非同期ジョブシステム（Redis）
- [x] 外部イベントシステム（LLM動的生成）
- [x] レポート生成（Claude API / Ollamaフォールバック）
- [x] 定量予測（トレンド分析 + シナリオ比較）
- [x] フロントエンドSPA（シナリオ入力 → チャート → レポート）
- [x] 統合・品質向上（LLMフォールバック、レートリミット）

### 未実装（今後の拡張）

- [ ] **データ収集パイプライン（RAG）**: 文書アップロード → エンティティ抽出 → 知識グラフ構築
- [ ] **統計データ連携**: e-Stat API、IPA白書等からの自動データ取得
- [ ] **知識グラフ活用**: エージェント意思決定時にNeo4jのスキル関係を参照
- [ ] **エージェントインタビュー**: シミュレーション後に特定エージェントへ質問
- [ ] **バックテスト**: 過去データで予測精度を検証
- [ ] **ユーザー認証**: マルチテナント対応

## ライセンス

Private
