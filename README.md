# EchoShoal

AI-powered Service Business Impact Simulator — エージェントベースモデリング（ABM）とLLMを組み合わせ、サービスの市場インパクトをシミュレーションで予測します。

## Overview

「このサービスをリリースしたら市場はどう反応するか」「競合が参入したらどうなるか」——EchoShoalはこうした問いに対して、多様なステークホルダーのAIエージェントが仮想SNS上で議論・行動するシミュレーションを通じて、定量的な予測を提供します。

### Key Features

- **OASIS SNSシミュレーション** — エージェントがReddit風プラットフォーム上で投稿・コメント・リアクションを行い、市場の反応を再現
- **8種のステークホルダーエージェント** — 企業・フリーランス・個人開発者・行政・投資家/VC・プラットフォーマー・業界コミュニティ・エンドユーザーがLLMで意思決定
- **認知バイアスモデル** — 各エージェントに保守性・バンドワゴン効果・過信・サンクコストなどの性格特性を付与し、リアルな行動を再現
- **動的イベント生成** — LLMがシナリオに基づき政策変更・景気変動・技術変革などのイベントを自動生成
- **自動市場調査** — Google Trends・GitHub API・Yahoo Financeからデータを収集し、LLMが市場レポート・ユーザー行動分析・ステークホルダー分析を合成
- **ドキュメント影響分析** — アップロードした資料（README、競合分析等）がシミュレーション結果にどう影響したかをLLMが分析
- **8次元の市場メトリクス** — ユーザー獲得率・収益ポテンシャル・技術成熟度・競合圧力・規制リスク・市場認知度・エコシステム健全性・資金調達環境
- **ナレッジグラフ** — Neo4jで文書・エンティティ・エージェントの関係をグラフ構造で管理・可視化
- **定量予測** — 線形回帰・移動平均によるディメンション別トレンド分析
- **レポート生成** — Claude API（Ollamaフォールバック）による6セクション構成の詳細分析レポート
- **ベンチマーク評価** — 過去の事例（Slack 2014等）を使った精度検証。複数回実行による統計的評価
- **シミュレーション比較** — 異なるシナリオの結果を並べて比較

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.13) + uv |
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS v4 |
| Graph DB | Neo4j Community Edition |
| Cache/Queue | Redis |
| LLM (light) | Ollama (qwen2.5:14b) — エージェント意思決定、イベント生成 |
| LLM (heavy) | Claude API / OpenAI API — レポート生成、ペルソナ設計（未設定時はOllamaフォールバック） |
| Simulation | OASIS (SNS-based ABM platform) |
| Visualization | Recharts + D3.js |

## Prerequisites

- Python 3.13 (`uv` for dependency management)
- Node.js v22+ / pnpm
- Docker Desktop (Neo4j + Redis)
- Ollama (local LLM)
- (Optional) Claude API key / OpenAI API key for higher quality reports

## Setup

### First Time

```bash
# Backend dependencies
cd backend
cp .env.example .env   # Edit .env to set API keys
uv sync

# Frontend dependencies
cd frontend
pnpm install

# Pull Ollama model
ollama pull qwen2.5:14b
```

### Start Services

```bash
# 1. Start infrastructure (Docker Desktop must be running)
docker compose up -d          # Neo4j (7474/7687) + Redis (6379)

# 2. Start Ollama
ollama serve                  # localhost:11434

# 3. Start backend (separate terminal)
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. Start frontend (separate terminal)
cd frontend
pnpm dev                      # localhost:5173
```

**Health check URLs:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api/health
- Neo4j Browser: http://localhost:7474

### Stop

```bash
# Frontend / Backend / Ollama: Ctrl+C
docker compose down            # Stop Neo4j + Redis
```

## Usage

1. フロントエンド (http://localhost:5173) にアクセス
2. 「New Simulation」からサービス名・シナリオ説明を入力
3. （任意）GitHubリポジトリURLを指定すると自動でREADMEを取得
4. （任意）市場調査を実行して外部データを収集
5. （任意）参考資料（PDF、Markdown、テキスト）をアップロード
6. シミュレーション実行 → エージェントがSNS上で議論
7. 結果画面で市場ディメンションの推移・関係グラフ・SNS投稿を確認
8. レポート画面でLLMによる詳細分析・成功スコア・リスク/機会を確認

## Project Structure

```
EchoShoal/
├── backend/
│   ├── app/
│   │   ├── api/              # REST API endpoints
│   │   ├── core/
│   │   │   ├── documents/    # Document parsing & NLP
│   │   │   ├── graph/        # Neo4j client & RAG
│   │   │   ├── llm/          # LLM routing (Ollama/Claude/OpenAI)
│   │   │   ├── market_research/  # Google Trends, GitHub, Yahoo Finance
│   │   │   └── nlp/          # Rule-based entity extraction
│   │   ├── evaluation/       # Benchmark scenarios & evaluation
│   │   ├── oasis/            # OASIS SNS simulation engine
│   │   ├── prediction/       # Quantitative trend prediction
│   │   ├── reports/          # LLM report generation
│   │   └── simulation/       # Agent types, events, market state
│   │       ├── agents/       # 8 stakeholder agent types
│   │       └── events/       # Dynamic event scheduler
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/              # API client & types
│       ├── components/       # Charts, graphs, social feed
│       └── pages/            # Simulation, report, benchmark pages
└── docker-compose.yml
```

## Configuration

All settings are managed via environment variables (see [backend/.env.example](backend/.env.example)).

Key variables:

| Variable | Description | Required |
|---|---|---|
| `ECHOSHOAL_CLAUDE_API_KEY` | Claude API key (for high-quality reports) | Optional |
| `ECHOSHOAL_OPENAI_API_KEY` | OpenAI API key (alternative) | Optional |
| `ECHOSHOAL_OLLAMA_MODEL` | Local LLM model name | Default: `qwen2.5:14b` |
| `ECHOSHOAL_ESTAT_API_KEY` | e-Stat API key (government statistics) | Optional |
| `ECHOSHOAL_NEO4J_PASSWORD` | Neo4j password | Required |
| `ECHOSHOAL_DEFAULT_ROUNDS` | Simulation rounds | Default: `24` |

## Development

```bash
# Run tests
cd backend && uv run pytest

# Run tests (verbose, stop on first failure)
cd backend && uv run pytest -x -v

# Frontend dev server
cd frontend && pnpm dev

# Frontend build
cd frontend && pnpm build
```

## License

Licensed under the [Apache License 2.0](LICENSE).
