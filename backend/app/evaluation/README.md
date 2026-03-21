# ベンチマーク評価システム

EchoShoalのシミュレーション精度を、過去の実在サービスの市場投入事例を使って検証するシステムです。

## 評価の考え方

### なぜベンチマークが必要か

LLMベースのシミュレーターは「もっともらしい結果」を生成しやすいため、実在の事例と照合して妥当性を確認する必要があります。EchoShoalでは、過去にリリースされたサービスの**リリース時点で分かっていた情報のみ**をシナリオとして入力し、シミュレーション結果が**実際に起きたこと**と整合するかを検証します。

### 評価指標: 方向一致率

評価は**トレンドの方向（UP / DOWN / STABLE）が一致したかどうか**のみで判定します。

```
例: Slack 2014

  期待: user_adoption → UP（実際にSlackは急成長した）
  実際: シミュレーション結果で 0.30 → 0.65 に上昇 → UP
  判定: 一致 ✅

  期待: competitive_pressure → UP（多数の競合が参入した）
  実際: シミュレーション結果で 0.25 → 0.55 に上昇 → UP
  判定: 一致 ✅

  方向一致率 = 一致したトレンド数 / 全トレンド数
```

**「どの程度上がるべきか」の数値は評価に使いません。** 数値目標を設けると恣意的なチューニングが必要になり、シミュレーター本来の設計思想（恣意的パラメータの排除）と矛盾するためです。

### 方向判定の閾値

変化率が ±3% 以内の場合は STABLE と判定します。これは「有意な変化があったか」を区別するための閾値です。

```
変化率 > +3%  → UP
変化率 < -3%  → DOWN
-3% ≤ 変化率 ≤ +3%  → STABLE
```

## ベンチマークシナリオ一覧

### 成功事例（5件）

| ID | サービス | 年 | 主要な期待トレンド | ラウンド数 |
|---|---|---|---|---|
| `slack_2014` | Slack | 2014 | user_adoption↑, competitive_pressure↑, market_awareness↑, ecosystem_health↑ | 12 |
| `notion_vs_confluence_2020` | Notion | 2020 | user_adoption↑, competitive_pressure↑, revenue_potential↑ | 18 |
| `github_copilot_2022` | GitHub Copilot | 2022 | tech_maturity↑, user_adoption↑, competitive_pressure↑, revenue_potential↑ | 12 |
| `zoom_2020` | Zoom | 2020 | user_adoption↑, competitive_pressure↑, regulatory_risk↑, revenue_potential↑ | 12 |
| `chatgpt_2022` | ChatGPT | 2022 | user_adoption↑, competitive_pressure↑, funding_climate↑, regulatory_risk↑, tech_maturity↑ | 12 |

### 失敗事例（4件）

| ID | サービス | 年 | 主要な期待トレンド | ラウンド数 |
|---|---|---|---|---|
| `google_wave_2009` | Google Wave | 2009 | user_adoption→（横ばい）, market_awareness↓, ecosystem_health↓ | 12 |
| `google_plus_2011` | Google+ | 2011 | user_adoption↓, competitive_pressure↑, revenue_potential↓ | 18 |
| `quibi_2020` | Quibi | 2020 | user_adoption↓, revenue_potential↓, competitive_pressure↑, funding_climate↓ | 8 |
| `jasper_ai_2023` | Jasper AI | 2023 | user_adoption↓, competitive_pressure↑, revenue_potential↓ | 12 |

### シナリオ設計のルール

1. **入力はリリース時点の情報のみ** — 結果（成功/失敗、ユーザー数推移等）は含めない。LLMが「答え合わせ」ではなく「予測」を行えるようにする
2. **期待トレンドは方向のみ** — UP / DOWN / STABLE。数値目標や重みは使わない
3. **成功と失敗の両方を含める** — 「何でも成功と予測する」シミュレーターを排除するため

## 補足資料

各シナリオには `scenarios/{id}/` ディレクトリに補足資料が格納されています。

```
scenarios/
├── slack_2014/
│   ├── slack_2014_market_report.txt      # 市場レポート
│   ├── slack_2014_readme.txt             # サービス概要
│   ├── slack_2014_stakeholders.txt       # ステークホルダー分析
│   └── slack_2014_user_behavior.txt      # ユーザー行動分析
├── google_wave_2009/
│   └── ...
└── ...
```

これらはシミュレーション開始時に自動的に知識グラフ（Neo4j）に格納され、エージェントの意思決定に影響を与えます。

## 実行時間の目安

以下はOllama qwen3:14b / RTX 4070 Ti SUPER (VRAM 16GB) 環境での参考値です。

| 実行パターン | 所要時間 |
|---|---|
| 1シナリオ単発（12ラウンド） | 約10〜15分 |
| 1シナリオ単発（18ラウンド） | 約15〜20分 |
| 市場調査+シミュレーション | 約20〜25分 |
| 統計評価（5回実行） | 約1〜1.5時間 |
| 全9シナリオ一括（各1回） | 約2〜3時間 |
| 全9シナリオ×5回統計 | 約10〜15時間 |

GPUのスペックやOllamaモデルのサイズによって大きく変動します。8Bモデルを使用した場合は上記の半分程度になります。

## 実行方法

### フロントエンドから

1. http://localhost:5173/benchmarks にアクセス
2. シナリオを選択して「実行」または「調査+実行」をクリック

### APIから

```bash
# ベンチマーク一覧の取得
curl http://localhost:8000/api/evaluation/benchmarks

# 単発実行
curl -X POST http://localhost:8000/api/evaluation/run/slack_2014

# 統計評価（N回実行）— LLMの非決定性を考慮した再現性検証
curl -X POST http://localhost:8000/api/evaluation/run/slack_2014/multi?num_runs=5

# 市場調査+シミュレーション+評価の一連実行
curl -X POST http://localhost:8000/api/evaluation/run/slack_2014/full

# 全ベンチマーク一括実行
curl -X POST http://localhost:8000/api/evaluation/run-all

# 評価結果の取得
curl http://localhost:8000/api/evaluation/{job_id}/result
```

### 統計評価の読み方

LLMの出力は確率的であるため、1回の実行結果だけでは信頼性を判断できません。同一シナリオを複数回実行して統計的に評価します。

```
ベンチマーク: Slack 2014（5回実行）

  Run 1: 方向一致率 75% (3/4)
  Run 2: 方向一致率 100% (4/4)
  Run 3: 方向一致率 75% (3/4)
  Run 4: 方向一致率 100% (4/4)
  Run 5: 方向一致率 75% (3/4)

  平均方向一致率: 85%
  標準偏差: 13.7%
  → 概ね妥当な方向性を予測できている
```

**合格基準**: 方向一致率 60% 以上をパスとしています（`run-all` 実行時）。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `benchmarks.py` | 9つのベンチマークシナリオ定義（シナリオ説明文 + 期待トレンド） |
| `comparator.py` | シミュレーション結果と期待トレンドの方向比較（純粋関数、インフラ依存なし） |
| `runner.py` | ベンチマーク実行のオーケストレーション（単発/統計/一括/市場調査付き） |
| `models.py` | データモデル定義 |
| `scenarios/` | 各シナリオの補足資料（市場レポート、README等） |
