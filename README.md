# EchoShoal

AIを活用したサービスビジネスインパクトシミュレーター — エージェントベースモデリング（ABM）とLLMを組み合わせ、サービスの市場インパクトをシミュレーションで予測します。

## 概要

「このサービスをリリースしたら市場はどう反応するか」「競合が参入したらどうなるか」——EchoShoalはこうした問いに対して、多様なステークホルダーのAIエージェントが仮想SNS上で議論・行動するシミュレーションを通じて、定量的な予測を提供します。

### 主な特徴

- **OASIS SNSシミュレーション** — エージェントがX(Twitter)/Reddit風のSNSプラットフォーム上で投稿・コメント・リアクションを行い、市場の反応を再現
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

## 技術スタック

| レイヤー | 技術 |
|---|---|
| バックエンド | FastAPI (Python 3.13) + uv |
| フロントエンド | React 19 + TypeScript + Vite + Tailwind CSS v4 |
| グラフDB | Neo4j Community Edition |
| キャッシュ/キュー | Redis |
| LLM（軽量） | Ollama (qwen3:14b) — エージェント意思決定、イベント生成 |
| LLM（高品質） | Claude API / OpenAI API — レポート生成、ペルソナ設計（未設定時はOllamaフォールバック） |
| シミュレーション | OASIS（SNSベースのABMプラットフォーム） |
| 可視化 | Recharts + D3.js |

## 前提条件

以下のソフトウェアを事前にインストールしてください。

| ソフトウェア | インストール | 備考 |
|---|---|---|
| [Python 3.13](https://www.python.org/downloads/) | 公式サイトからダウンロード | |
| [uv](https://docs.astral.sh/uv/) | `pip install uv` または `curl -LsSf https://astral.sh/uv/install.sh \| sh` | Python依存管理 |
| [Node.js v22+](https://nodejs.org/) | 公式サイトからダウンロード | |
| [pnpm](https://pnpm.io/) | `npm install -g pnpm` | フロントエンド依存管理 |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | 公式サイトからダウンロード | Neo4j + Redis用 |
| [Ollama](https://ollama.com/) | 公式サイトからダウンロード | 無料のローカルLLM。APIキー不要でシミュレーション実行可能 |

**任意:** [Claude API key](https://console.anthropic.com/) / [OpenAI API key](https://platform.openai.com/) — 設定するとレポート品質が向上しますが、未設定でもOllamaで全機能が動作します

### 動作確認環境

| 項目 | スペック |
|---|---|
| OS | Windows 11 Home |
| CPU | AMD Ryzen 7 7800X3D (8コア/16スレッド) |
| メモリ | 32 GB |
| GPU | NVIDIA GeForce RTX 4070 Ti SUPER (VRAM 16 GB) |
| Python | 3.13.2 |
| Node.js | v22.17.0 |
| Docker | Docker Desktop 29.2.1 |

### Ollamaモデルの選定

デフォルトのLLMモデルは **qwen3:14b** を推奨しています。

| モデル | サイズ | 選定理由 |
|---|---|---|
| **qwen3:14b** (推奨) | 9.3 GB | 日本語性能が高く、14Bクラスで最もバランスが良い。32Kコンテキスト対応。VRAM 12GB以上推奨 |
| qwen2.5:14b | 9.0 GB | qwen3の前世代。安定性重視の場合の代替 |
| llama3.1:8b | 4.9 GB | VRAM 8GB環境向け。日本語品質はやや劣る |
| gemma3:4b | 3.3 GB | 軽量環境向け。最低限の動作確認用 |

モデルは `.env` の `ECHOSHOAL_OLLAMA_MODEL` で変更可能です。VRAM容量に応じて適切なモデルを選択してください。

## セットアップ

### 初回のみ

```bash
# バックエンド依存インストール
cd backend
cp .env.example .env   # .envを作成し、必要に応じてAPIキー等を設定
uv sync

# フロントエンド依存インストール
cd frontend
pnpm install

# Ollamaモデルのダウンロード（VRAM 12GB以上推奨、8GBの場合は llama3.1:8b を使用）
ollama pull qwen3:14b
```

### 起動手順（毎回）

```bash
# 1. Docker Desktopを起動してから:
docker compose up -d          # Neo4j (7474/7687) + Redis (6379)

# 2. Ollamaを起動
ollama serve                  # localhost:11434

# 3. バックエンド起動（別ターミナル）
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. フロントエンド起動（別ターミナル）
cd frontend
pnpm dev                      # localhost:5173
```

**起動確認URL:**
- フロントエンド: http://localhost:5173
- バックエンドAPI: http://localhost:8000/api/health
- Neo4jブラウザ: http://localhost:7474

### 停止

```bash
# フロントエンド / バックエンド / Ollama: Ctrl+C
docker compose down            # Neo4j + Redis を停止
```

## 使い方

1. フロントエンド (http://localhost:5173) にアクセス
2. 「新規シミュレーション」からサービス名・シナリオ説明を入力
3. （任意）GitHubリポジトリURLを指定すると自動でREADMEを取得
4. （任意）市場調査を実行して外部データを収集
5. （任意）参考資料（PDF、Markdown、テキスト）をアップロード
6. シミュレーション実行 → エージェントがSNS上で議論
7. 結果画面で市場ディメンションの推移・関係グラフ・SNS投稿を確認
8. レポート画面でLLMによる詳細分析・成功スコア・リスク/機会を確認

## プロジェクト構成

```
EchoShoal/
├── backend/
│   ├── app/
│   │   ├── api/              # REST APIエンドポイント
│   │   ├── core/
│   │   │   ├── documents/    # ドキュメント解析・NLP
│   │   │   ├── graph/        # Neo4jクライアント・RAG
│   │   │   ├── llm/          # LLMルーティング (Ollama/Claude/OpenAI)
│   │   │   ├── market_research/  # 市場調査 (Google Trends, GitHub, Yahoo Finance)
│   │   │   └── nlp/          # ルールベースエンティティ抽出
│   │   ├── evaluation/       # ベンチマークシナリオ・評価
│   │   ├── oasis/            # OASIS SNSシミュレーションエンジン
│   │   ├── prediction/       # 定量トレンド予測
│   │   ├── reports/          # LLMレポート生成
│   │   └── simulation/       # エージェント・イベント・市場状態
│   │       ├── agents/       # 8種のステークホルダーエージェント
│   │       └── events/       # 動的イベントスケジューラ
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/              # APIクライアント・型定義
│       ├── components/       # チャート・グラフ・SNSフィード
│       └── pages/            # シミュレーション・レポート・ベンチマーク画面
└── docker-compose.yml
```

## 設定

すべての設定は環境変数で管理されています（詳細は [backend/.env.example](backend/.env.example) を参照）。

主要な設定項目:

| 変数名 | 説明 | 必須 |
|---|---|---|
| `ECHOSHOAL_CLAUDE_API_KEY` | Claude APIキー（高品質レポート用） | 任意 |
| `ECHOSHOAL_OPENAI_API_KEY` | OpenAI APIキー（代替） | 任意 |
| `ECHOSHOAL_OLLAMA_MODEL` | ローカルLLMモデル名 | デフォルト: `qwen3:14b` |
| `ECHOSHOAL_ESTAT_API_KEY` | e-Stat APIキー（政府統計データ） | 任意 |
| `ECHOSHOAL_NEO4J_PASSWORD` | Neo4jパスワード | 必須 |
| `ECHOSHOAL_DEFAULT_ROUNDS` | シミュレーションラウンド数 | デフォルト: `12` |

## 開発

```bash
# テスト実行
cd backend && uv run pytest

# テスト実行（詳細表示、最初の失敗で停止）
cd backend && uv run pytest -x -v

# フロントエンド開発サーバー
cd frontend && pnpm dev

# フロントエンドビルド
cd frontend && pnpm build
```

## ベンチマーク評価

過去のサービスリリース事例（成功5件・失敗4件）を使い、シミュレーターの予測精度を検証できます。フロントエンドの `/benchmarks` ページから実行するか、APIを直接呼び出します。

**実行時間の目安**（Ollama qwen3:14b / RTX 4070 Ti SUPER環境）:
- 1シナリオ（12ラウンド）: 約10〜15分
- 市場調査付き: 約20〜25分
- 全9シナリオ一括: 約2〜3時間

```bash
# API経由で単発実行（例: Slack 2014）
curl -X POST http://localhost:8000/api/evaluation/run/slack_2014

# 統計評価（5回実行して再現性を検証）
curl -X POST http://localhost:8000/api/evaluation/run/slack_2014/multi?num_runs=5

# 全ベンチマーク一括実行
curl -X POST http://localhost:8000/api/evaluation/run-all
```

詳細な評価手法・シナリオ一覧は [backend/app/evaluation/README.md](backend/app/evaluation/README.md)、過去の評価結果は [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md) を参照してください。

## ライセンス

[Apache License 2.0](LICENSE) の下で公開されています。
