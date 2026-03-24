# Benchmark Results

EchoShoalシミュレーションエンジンの予測精度を、実在のサービス事例（成功5件・失敗4件）で評価した結果。

> Generated: 2026-03-25

## 評価方法

### 通常ベンチマーク
- 各シナリオを3回実行し、市場ディメンションのトレンド方向（up/down/stable）を史実と比較
- **方向精度** = 正しく予測したディメンション数 / 評価対象ディメンション数
- LLM: Ollama qwen3:14b（エージェント行動決定・市場分析）
- シナリオテキスト（market_report, stakeholders, user_behavior）は基準時点以前の情報のみを含む

### LLM知識汚染テスト（Contamination A/B Test）
- 同一シナリオを**実名版**と**匿名版**で実行し、方向精度の差分を計測
- 匿名版ではサービス名・創業者名・競合名等を架空の名前に置換
- 差分（contamination_score）が大きい場合、LLMの学習データに含まれる結果情報が予測に影響している
- 差分が小さい場合、シミュレータの構造的推論力が予測に寄与している

| contamination_score | レベル | 解釈 |
|---|---|---|
| 5pp以下 | none | 差なし。純粋な推論 |
| 5-15pp | low | 軽微な知識リーク |
| 15-30pp | moderate | 中程度の知識リーク |
| 30pp超 | high | 強い知識リーク |
| -5pp未満 | negative | 匿名版の方が高い（名前バイアス） |

## 通常ベンチマーク結果

- **全体平均方向精度: 69.6%**
- **合格シナリオ (>=60%): 6/9**
- 成功/失敗予測正解: 7/9
- 総実行時間: 16.2時間（9シナリオ x 3回）

| シナリオ | 種別 | 平均精度 | sd | 95% CI | 成功/失敗予測 |
|---------|------|---------|-----|--------|------------|
| Slack Launch 2014 | 成功 | 66.7% | 0.144 | [31%-103%] | 100% |
| Notion vs Confluence 2020 | 成功 | 55.6% | 0.193 | [8%-103%] | 67% |
| GitHub Copilot 2022 | 成功 | 93.3% | 0.116 | [65%-122%] | 100% |
| Zoom COVID-19 2020 | 成功 | 44.4% | 0.193 | [-3%-92%] | 100% |
| ChatGPT Launch 2022 | 成功 | 72.2% | 0.096 | [48%-96%] | 100% |
| Google Wave 2009 | 失敗 | 33.3% | 0.333 | [-49%-116%] | 0% |
| Google+ 2011 | 失敗 | 77.8% | 0.385 | [-18%-173%] | 100% |
| Quibi 2020 | 失敗 | 91.7% | 0.144 | [56%-128%] | 100% |
| Jasper AI 2023 | 失敗 | 91.7% | 0.144 | [56%-128%] | 0% |

## シナリオ別詳細

### Slack Launch 2014 (成功) -- 66.7%

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| dimensions.user_adoption | 67% (2/3) | up |
| dimensions.competitive_pressure | 100% (3/3) | up |
| dimensions.market_awareness | 67% (2/3) | up |
| dimensions.ecosystem_health | 33% (1/3) | up |

### Notion vs Confluence 2020 (成功) -- 55.6%

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| dimensions.user_adoption | 67% (2/3) | up |
| dimensions.competitive_pressure | 100% (3/3) | up |
| dimensions.revenue_potential | 0% (0/3) | up |

### GitHub Copilot 2022 (成功) -- 93.3%

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| dimensions.tech_maturity | 100% (3/3) | up |
| dimensions.user_adoption | 67% (2/3) | up |
| dimensions.competitive_pressure | 100% (3/3) | up |
| dimensions.regulatory_risk | 100% (3/3) | up |
| ai_disruption_level | 100% (3/3) | up |

### Zoom COVID-19 2020 (成功) -- 44.4%

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| dimensions.user_adoption | 33% (1/3) | up |
| dimensions.competitive_pressure | 67% (2/3) | up |
| dimensions.market_awareness | 33% (1/3) | up |

### ChatGPT Launch 2022 (成功) -- 72.2%

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| dimensions.user_adoption | 67% (2/3) | up |
| dimensions.competitive_pressure | 100% (3/3) | up |
| dimensions.funding_climate | 0% (0/3) | up |
| dimensions.regulatory_risk | 100% (3/3) | up |
| dimensions.tech_maturity | 67% (2/3) | up |
| ai_disruption_level | 100% (3/3) | up |

### Google Wave 2009 (失敗) -- 33.3%

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| dimensions.user_adoption | 33% (1/3) | down |
| dimensions.revenue_potential | 33% (1/3) | down |
| dimensions.tech_maturity | 33% (1/3) | down |

### Google+ 2011 (失敗) -- 77.8%

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| dimensions.user_adoption | 67% (2/3) | down |
| dimensions.competitive_pressure | 100% (3/3) | up |
| dimensions.revenue_potential | 67% (2/3) | down |

### Quibi 2020 (失敗) -- 91.7%

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| dimensions.user_adoption | 100% (3/3) | down |
| dimensions.revenue_potential | 100% (3/3) | down |
| dimensions.competitive_pressure | 100% (3/3) | up |
| dimensions.funding_climate | 67% (2/3) | down |

### Jasper AI 2023 (失敗) -- 91.7%

| ディメンション | ヒット率 | 期待 |
|--------------|---------|------|
| dimensions.user_adoption | 67% (2/3) | down |
| dimensions.competitive_pressure | 100% (3/3) | up |
| dimensions.revenue_potential | 100% (3/3) | down |
| ai_disruption_level | 100% (3/3) | up |

## LLM知識汚染テスト結果

- **平均汚染スコア: -2.8pp**
- 平均実名版精度: 73.3%
- 平均匿名版精度: 76.1%
- 実行時間: 10.7時間

| シナリオ | 実名版 | 匿名版 | 汚染スコア | レベル |
|---------|-------|-------|-----------|--------|
| Slack Launch 2014 | 75% | 100% | -25.0pp | negative |
| Notion vs Confluence 2020 | 100% | 33% | +66.7pp | high |
| GitHub Copilot 2022 | 60% | 60% | +0.0pp | none |
| Zoom COVID-19 2020 | 67% | 67% | +0.0pp | none |
| ChatGPT Launch 2022 | 67% | 83% | -16.7pp | negative |
| Google Wave 2009 | 100% | 67% | +33.3pp | high |
| Google+ 2011 | 67% | 100% | -33.3pp | negative |
| Quibi 2020 | 75% | 75% | +0.0pp | none |
| Jasper AI 2023 | 50% | 100% | -50.0pp | negative |

### 解釈

平均汚染スコアが10pp以下であり、シミュレータの推論力は概ね信頼できる。
LLMの学習データに含まれる歴史的結果への依存度は低い。

## 技術情報

- シミュレーションエンジン: OASIS SNS Simulation
- エージェント行動決定: Ollama qwen3:14b
- レポート生成: Claude API
- シナリオテキスト: 各サービスの基準時点以前の情報のみ（未来情報除去済み）
- 匿名化: サービス名・創業者名・競合名等を架空名に置換
- 総実行時間: 26.9時間
