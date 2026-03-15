# OASIS統合設計計画

## 1. 目的

EchoShoalのシミュレーションエンジンをOASIS（Open Agent Social Interaction Simulations）で強化し、
MiroFish方式のエージェント間インタラクション（SNS的投稿・コメント・反応）と
関係グラフの有機的成長を実現する。

## 2. 現状の課題

| 課題 | 原因 |
|------|------|
| エージェント数が10-20体と少ない | Ollama逐次呼び出しの速度制約 |
| 関係グラフが広がらない | reacting_toベースの限定的な関係構築 |
| インタラクションが浅い | ラウンドごとに1-2アクション選択するだけ |
| エージェントの「考え」が見えない | SNS的な投稿・コメントがない |

## 3. OASIS概要

- **パッケージ**: `camel-oasis` (PyPI, v0.2.5)
- **ライセンス**: Apache 2.0
- **基盤**: CAMEL-AIフレームワーク
- **対応LLM**: OpenAI互換API（Ollama対応）
- **プラットフォーム**: Twitter/Reddit的なSNS空間
- **アクション**: 23種（投稿、コメント、リポスト、フォロー等）
- **スケール**: 最大100万エージェント

## 4. 統合アーキテクチャ

### 4.1 変更前（現在）

```
ユーザー入力
  → ScenarioAnalyzer（NLP + LLM）
  → AgentGenerator（エンティティ→エージェント）
  → SimulationEngine（ラウンド制、逐次LLM呼び出し）
    → 各エージェントが1-2アクション選択
    → 市場ディメンション更新（LLM判断）
  → ReportGenerator
```

### 4.2 変更後（OASIS統合）

```
ユーザー入力
  → ScenarioAnalyzer（NLP + LLM）— 既存を維持
  → EntityToAgentConverter（文書エンティティ→OASISプロファイル）— 新規
  → OASISSimulationEngine（新規、既存のSimulationEngineを置換）
    → OASIS環境でエージェントがSNS空間でインタラクション
    → Time Engineで活性化制御（Ollamaの速度制約を緩和）
    → インタラクション → 関係グラフ自動成長
    → アクションログ → 市場ディメンション更新
  → ReportGenerator — 既存を維持（入力フォーマットを調整）
```

### 4.3 既存コンポーネントの扱い

| コンポーネント | 扱い |
|--------------|------|
| `ScenarioAnalyzer` | そのまま維持 |
| `AgentGenerator` | OASISプロファイル形式に出力を変更 |
| `SimulationEngine` | OASISSimulationEngineに置換 |
| エージェントクラス（7+1種） | OASISエージェントに変換。available_actionsは維持 |
| `EventScheduler` | OASIS側のイベントとして注入 |
| `AgentMemoryStore` (Neo4j) | OASISのSQLiteトレースから同期 |
| `GraphRAGRetriever` | OASISのインタラクション履歴から構築 |
| `ReportGenerator` | OASISのアクションログを入力に変更 |
| フロントエンド (React) | そのまま維持、グラフ表示を改善 |

## 5. 実装計画

### Phase 1: OASIS基盤セットアップ

**ファイル:**
- `backend/pyproject.toml` — `camel-oasis` 依存追加
- `backend/app/oasis/__init__.py` — 新パッケージ
- `backend/app/oasis/config.py` — OASIS設定（Ollamaバックエンド）

**作業内容:**
```python
# OASIS + Ollama設定
from camel.models import ModelFactory, ModelPlatformType

model = ModelFactory.create(
    model_platform=ModelPlatformType.OLLAMA,
    model_type="llama3.1:8b",
    url="http://localhost:11434/v1",
)
```

**検証:** OASISが起動し、Ollamaでエージェントが1回発言できることを確認

### Phase 2: プロファイル変換

**ファイル:**
- `backend/app/oasis/profile_generator.py` — MiroFishのOasisProfileGenerator相当

**作業内容:**
- 現在の`AgentGenerator`が生成するエージェントを、OASISのプロファイル形式（CSV/JSON）に変換
- 文書エンティティ → OASISエージェントプロファイル
- パーソナリティ情報をOASISの背景メモリとして注入

**OASISプロファイル形式:**
```json
{
  "user_id": "agent_001",
  "name": "Slack",
  "bio": "Leading business chat competitor with 2600+ integrations",
  "personality": "Confident market leader, aggressive on pricing",
  "stance": "Defensive against new entrants"
}
```

### Phase 3: シミュレーションエンジン置換

**ファイル:**
- `backend/app/oasis/simulation_runner.py` — OASISシミュレーション実行
- `backend/app/simulation/engine.py` — 既存エンジンをOASISラッパーに変更

**作業内容:**
```python
import oasis

# 環境作成
env = oasis.make(
    agent_graph=agent_graph,
    platform=oasis.DefaultPlatformType.REDDIT,  # ビジネス議論に適した形式
    database_path=f"simulations/{job_id}/simulation.db",
)

# シミュレーション実行
await env.reset()
for round in range(num_rounds):
    actions = await env.step()  # 各エージェントがSNS空間で行動
    # アクションログを記録
    # 進捗を更新
```

**Time Engine活用:**
- 全エージェントを毎ラウンド活性化するのではなく、確率的に選択
- Ollamaの処理速度に合わせてアクティブエージェント数を制御
- `settings.agent_activation_rate`で制御（既存の仕組みを活用）

### Phase 4: アクションログ → 市場ディメンション変換

**ファイル:**
- `backend/app/oasis/action_analyzer.py` — OASISアクションログの分析

**作業内容:**
- OASISのSQLiteアクションログを読み取り
- 投稿内容・コメント・リポスト数から市場ディメンションへの影響をLLMが判断
- 既存の`_update_market()`ロジックをOASISアクションログ入力に適応

**OASISアクション → ディメンション変換例:**
```
エージェント「Slack」が投稿: "We're launching Japanese localization"
  → competitive_pressure ↑, market_awareness ↑

エージェント「保守的企業群」がコメント: "We need ISMAP certification first"
  → regulatory_risk ↑, user_adoption ↓

エージェント「Slackユーザー層」がリポスト: 50回
  → market_awareness ↑↑（リポスト数で重み付け）
```

### Phase 5: 関係グラフの自動成長

**ファイル:**
- `backend/app/oasis/graph_sync.py` — OASISインタラクション → Neo4jグラフ同期

**作業内容:**
- OASISのインタラクションテーブル（SQLite）からフォロー/コメント/リポスト関係を抽出
- Neo4jのRELATES_TOリレーションシップとして記録
- フォロー → 関心, コメント → 議論, リポスト → 拡散, いいね → 支持
- インタラクション数に基づいて関係の強度を計算

**MiroFish方式のグラフ成長:**
```
ラウンド1: Slack, Teams, TeamChat の3ノード + 初期関係
ラウンド5: ユーザー層が反応し始め、フォロー/コメントでエッジ増加
ラウンド10: 投資家がコメント、行政がガイドライン投稿 → 新エッジ
ラウンド20: 全エージェントが密に接続された関係グラフ
```

### Phase 6: フロントエンド改善

**ファイル:**
- `frontend/src/components/RelationshipGraph.tsx` — 改善
- `frontend/src/components/SocialFeed.tsx` — 新規（SNS投稿表示）

**作業内容:**
- RelationshipGraph: エッジの太さをインタラクション数で変える（1回=細い、10回=太い）
- SocialFeed: エージェントの投稿・コメントをSNSフィード形式で時系列表示
- ノードクリック時にそのエージェントの投稿履歴を表示

### Phase 7: APIとの互換性維持

**作業内容:**
- 既存のAPI（`/api/simulations/`）はそのまま維持
- OASISのアクションログを既存の`RoundResult`形式に変換して返す
- `.env`に`ECHOSHOAL_SIMULATION_ENGINE=oasis|legacy`を追加し、切り替え可能に
- Claude API/OpenAI APIキーが設定されていればOASIS側でも使用可能に

## 6. 依存関係

```
# 追加パッケージ
camel-oasis>=0.2.5     # OASISフレームワーク
camel-ai               # CAMEL基盤（oasisの依存）
```

**既存依存への影響:**
- Ollamaクライアント: CAMEL-AIのOllama統合を使用（既存のOllamaClientと共存可能）
- Neo4j: そのまま維持（OASIS SQLite → Neo4j同期を追加）
- Redis: そのまま維持（ジョブ管理は変更なし）

## 7. 設定（.env追加項目）

```bash
# シミュレーションエンジン選択
ECHOSHOAL_SIMULATION_ENGINE=oasis  # "oasis" or "legacy"

# OASIS設定
ECHOSHOAL_OASIS_PLATFORM=reddit    # "twitter" or "reddit"
ECHOSHOAL_OASIS_MAX_AGENTS=200     # 最大エージェント数
ECHOSHOAL_OASIS_ROUNDS_PER_STEP=1  # OASISのステップ数/ラウンド

# LLM API（互換性維持）
ECHOSHOAL_CLAUDE_API_KEY=           # Claude API（オプション）
ECHOSHOAL_OPENAI_API_KEY=           # OpenAI API（オプション）
```

## 8. リスクと対策

| リスク | 対策 |
|--------|------|
| OASIS + Ollamaの速度が遅い | Time Engineでアクティブエージェント数を制御。1ラウンドあたりのアクティブ数を10-20に制限 |
| OASISのAPI変更 | バージョン固定（>=0.2.5）。抽象レイヤーを設けて直接依存を避ける |
| 既存テストの破壊 | `SIMULATION_ENGINE=legacy`で既存エンジンも動作可能に。テストはlegacyモードで実行 |
| OASISのSNS空間がビジネスシミュレーションに合わない | Reddit形式を採用（長文議論に適する）。投稿テンプレートをビジネス文脈に調整 |

## 9. 実装順序

```
Phase 1 (基盤) → Phase 2 (プロファイル) → Phase 3 (エンジン)
  ※ここまでで最小限動作する

Phase 4 (アクション分析) → Phase 5 (グラフ成長)
  ※シミュレーション結果の質が向上

Phase 6 (フロントエンド) → Phase 7 (互換性)
  ※ユーザー体験の改善
```

**推定工数:** Phase 1-3で約1セッション、Phase 4-7で約1セッション

## 10. 検証方法

1. Phase 1完了後: OASISがOllamaで起動し、エージェントが1回発言できること
2. Phase 3完了後: サンプルシナリオで20+エージェントがSNS空間でインタラクションすること
3. Phase 5完了後: タイムスライダーでグラフが成長すること
4. Phase 7完了後: `uv run pytest`で既存テスト全パス + 新テスト追加
5. 最終: `/test` → `/security-review` → `/refactor`
