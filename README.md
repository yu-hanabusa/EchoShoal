# EchoShoal

サービスビジネスインパクトシミュレーター。エージェントベースモデリング（ABM）とLLMを組み合わせ、特定のサービスが成功するかどうかの判断材料やIFシナリオを提供します。

## 概要

EchoShoalは「このサービスをリリースしたら市場はどう反応するか」「競合が参入した場合のインパクトは」といった問いに対して、シミュレーションベースの予測を提供するツールです。

### 主な特徴

- **エージェントベースシミュレーション**: 7種のステークホルダー（企業、フリーランス、個人開発者、行政、投資家/VC、プラットフォーマー、業界団体/コミュニティ）が各ラウンドでLLMにより意思決定
- **動的イベントシステム**: シナリオに基づいて政策変更・景気変動・技術変革・競合の動きなどのイベントをLLMが自動生成
- **日本語NLP解析**: ルールベース辞書で技術名・政策名を自動検出、組織名はLLMが抽出
- **8次元の市場ディメンション**: ユーザー獲得率、収益ポテンシャル、技術成熟度、競合圧力、規制リスク、市場認知度、エコシステム健全性、資金調達環境
- **資料影響分析**: 入力文書がシミュレーション結果にどう影響したかをLLMが分析
- **追加情報提案**: シミュレーション精度向上に必要な情報をLLMが提案
- **定量予測**: 線形回帰・移動平均によるディメンション別トレンド分析
- **レポート生成**: Claude API（またはOllamaフォールバック）による分析レポート自動生成
- **非同期ジョブ**: Redis によるジョブ管理とリアルタイム進捗通知

## 技術スタック

| レイヤー | 技術 |
|---|---|
| Backend | FastAPI (Python 3.13) + uv |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS v4 |
| Graph DB | Neo4j Community Edition |
| Cache/Queue | Redis |
| LLM (light) | Ollama (qwen2.5:14b) |
| LLM (heavy) | Claude API / OpenAI API（未設定時はOllamaフォールバック） |
| NLP | ルールベース辞書 + LLM |
| Testing | pytest + pytest-asyncio + httpx |

## 前提条件

- Windows 11（ネイティブ実行、WSL不要）
- Python 3.13（`uv` で依存管理）
- Node.js v22+ / pnpm
- Docker Desktop for Windows（Neo4j + Redis用）
- Ollama for Windows（ローカルLLM）

## セットアップ

### 初回のみ

```bash
# バックエンド依存インストール
cd backend
cp .env.example .env   # .envを作成し、APIキー等を設定
uv sync

# フロントエンド依存インストール
cd frontend
pnpm install
```

### 起動手順（毎回）

以下の順序で4つのサービスを起動してください。

```bash
# 1. Docker Desktop を起動してから:
docker compose up -d          # Neo4j (7474/7687) + Redis (6379)

# 2. Ollama（別ターミナル、またはバックグラウンド）
ollama serve                  # localhost:11434
# 初回のみモデルをpull:
# ollama pull qwen2.5:14b

# 3. バックエンド（別ターミナル）
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. フロントエンド（別ターミナル）
cd frontend
pnpm dev                      # localhost:5173
```

**起動確認URL:**
- フロントエンド: http://localhost:5173
- バックエンドAPI: http://localhost:8000/api/health
- Neo4j Browser: http://localhost:7474
- Ollama API: http://localhost:11434

### 停止

```bash
# フロントエンド: Ctrl+C
# バックエンド: Ctrl+C
# Ollama: Ctrl+C（またはタスクマネージャーから停止）
docker compose down            # Neo4j + Redis 停止
```

## 使い方

1. フロントエンドにアクセス
2. 「New Simulation」からサービス名とシナリオを入力
3. 必要に応じてサービス文書（README、競合分析等）をアップロード
4. シミュレーション実行後、結果画面で市場ディメンションの推移を確認
5. レポート画面でLLMによる詳細分析を確認

## ライセンス

Private
