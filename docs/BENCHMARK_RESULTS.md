# Benchmark Results

EchoShoalシミュレーションエンジンの精度を、実在のサービス事例（成功5件・失敗4件）で評価した結果。

## 評価方法

- 各シナリオを3回実行し、市場ディメンション（user_adoption, competitive_pressure等）のトレンド方向（up/down/stable）を史実と比較
- **方向精度** = 正しく予測したディメンション数 / 評価対象ディメンション数
- 合格閾値: 60%
- LLM: Ollama qwen3:14b（エージェント行動決定）
- 総実行時間: 約18時間（9シナリオ x 3回）

## 全体サマリー

| シナリオ | 種別 | 平均精度 | σ | 95% CI | 判定 |
|---------|------|---------|-----|--------|------|
| Slack Launch 2014 | 成功 | 58.3% | 0.382 | [0.0%-100.0%] | FAIL |
| Notion vs Confluence 2020 | 成功 | 100.0% | 0.000 | [100.0%-100.0%] | PASS |
| GitHub Copilot 2022 | 成功 | 73.3% | 0.116 | [52.1%-94.5%] | PASS |
| Zoom COVID-19 2020 | 成功 | 58.3% | 0.144 | [31.8%-84.9%] | FAIL |
| ChatGPT Launch 2022 | 成功 | 72.2% | 0.096 | [54.6%-89.9%] | PASS |
| Google Wave 2009 | 失敗 | 11.1% | 0.192 | [0.0%-46.5%] | FAIL |
| Google+ 2011 | 失敗 | 88.9% | 0.192 | [53.5%-100.0%] | PASS |
| Quibi 2020 | 失敗 | 83.3% | 0.144 | [56.8%-100.0%] | PASS |
| Jasper AI 2023 | 失敗 | 91.7% | 0.144 | [65.1%-100.0%] | PASS |

- **全体平均方向精度: 70.8%**
- **合格シナリオ: 6/9**
- 成功事例の平均精度: 72.4%（5件）
- 失敗事例の平均精度: 68.8%（4件）
- 再現性（σ平均）: 0.157（LLMの非決定性により中程度のばらつき）

## シナリオ別詳細

### 成功事例

#### Slack Launch 2014 — 58.3% (FAIL)

2014年のSlack正式リリース。フリーミアムモデルでチームコミュニケーション市場に参入。

| ディメンション | ヒット率 | 期待 | 備考 |
|--------------|---------|------|------|
| user_adoption | 1/3 (33%) | up | 実行間で大きなばらつき（25%〜100%） |
| competitive_pressure | 3/3 (100%) | up | 安定して正確 |
| market_awareness | 2/3 (67%) | up | |
| ecosystem_health | 1/3 (33%) | up | |

課題: user_adoptionの予測が不安定。初期値が低い成功事例で採用増加の再現が困難。

#### Notion vs Confluence 2020 — 100.0% (PASS)

NotionのPLGモデルによる市場拡大。COVID-19によるリモートワーク需要と合致。

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| user_adoption | 3/3 (100%) | up |
| competitive_pressure | 3/3 (100%) | up |
| revenue_potential | 3/3 (100%) | up |

全3回で100%の方向精度。最も安定したシナリオ。

#### GitHub Copilot 2022 — 73.3% (PASS)

Microsoft/GitHubによるAIコード補完ツールの一般公開。

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| tech_maturity | 2/3 (67%) | up |
| user_adoption | 2/3 (67%) | up |
| competitive_pressure | 3/3 (100%) | up |
| revenue_potential | 1/3 (33%) | up |
| ai_disruption_level | 3/3 (100%) | up |

課題: revenue_potentialの予測精度が低い。

#### Zoom COVID-19 2020 — 58.3% (FAIL)

パンデミック下でのZoomの急成長。

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| user_adoption | 2/3 (67%) | up |
| competitive_pressure | 2/3 (67%) | up |
| regulatory_risk | 3/3 (100%) | up |
| revenue_potential | 0/3 (0%) | up |

課題: revenue_potentialが全実行で下降と予測。外的ショック（パンデミック）による爆発的成長の再現が困難。

#### ChatGPT Launch 2022 — 72.2% (PASS)

OpenAIによるChatGPTの無料公開。生成AI市場の転換点。

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| user_adoption | 1/3 (33%) | up |
| competitive_pressure | 3/3 (100%) | up |
| funding_climate | 0/3 (0%) | up |
| regulatory_risk | 3/3 (100%) | up |
| tech_maturity | 3/3 (100%) | up |
| ai_disruption_level | 3/3 (100%) | up |

課題: funding_climateが全実行で下降。エージェントが投資リスクを過大評価する傾向。

### 失敗事例

#### Google Wave 2009 — 11.1% (FAIL)

Googleの統合コミュニケーションツール。2010年に開発中止。

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| user_adoption | 0/3 (0%) | stable |
| market_awareness | 0/3 (0%) | down |
| ecosystem_health | 1/3 (33%) | down |

課題: エージェントがGoogle Waveをポジティブに評価しすぎる。market_awarenessとecosystem_healthを上昇と予測してしまう。

#### Google+ 2011 — 88.9% (PASS)

GoogleのSNS参入。Facebookの8億ユーザーに対抗。2019年に終了。

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| user_adoption | 2/3 (67%) | down |
| competitive_pressure | 3/3 (100%) | up |
| revenue_potential | 3/3 (100%) | down |

失敗事例の中で高精度。ネットワーク効果による支配的競合の存在を正しく反映。

#### Quibi 2020 — 83.3% (PASS)

17.5億ドル調達のモバイル専用短尺動画サービス。6ヶ月で終了。

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| user_adoption | 3/3 (100%) | down |
| revenue_potential | 3/3 (100%) | down |
| competitive_pressure | 3/3 (100%) | up |
| funding_climate | 1/3 (33%) | down |

課題: funding_climateの下降予測が不安定。

#### Jasper AI 2023 — 91.7% (PASS)

GPT-3ベースのマーケティングコピー生成SaaS。ChatGPT登場後に競争力を喪失。

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| user_adoption | 2/3 (67%) | down |
| competitive_pressure | 3/3 (100%) | up |
| revenue_potential | 3/3 (100%) | down |
| ai_disruption_level | 3/3 (100%) | up |

最高精度のシナリオ。プラットフォーマーリスクの再現に成功。

## 分析

### 強み
- **competitive_pressure**: 全シナリオで高精度（ほぼ100%）。競合環境の変化を正確に捉える
- **regulatory_risk**: 追跡したシナリオで100%の精度
- **失敗事例の予測**: 失敗サービスのuser_adoption/revenue_potential下降を高精度で予測
- **AI disruption**: AI関連シナリオでai_disruption_levelを100%正確に予測

### 弱み
- **revenue_potential（成功事例）**: 成功サービスの収益成長を過小評価する傾向
- **funding_climate**: 投資環境の変化予測が不安定
- **外的ショック**: パンデミック等の予測不能な外部要因による急変動の再現が困難
- **Google Wave**: 失敗サービスをポジティブに評価しすぎる（Googleブランドバイアスの可能性）
- **再現性**: LLMの非決定性により、同一シナリオでも実行間で最大75ポイントの差（Slack: 25%〜100%）

### 今後の改善方向
- エージェントのrevenue_potential評価ロジックの改善
- 外的ショック（パンデミック、経済危機等）のシミュレーション強化
- LLM出力の安定化（temperatureチューニング、アンサンブル手法の検討）
- Google Waveのような「過度に野心的なプロダクト」の失敗パターン学習
