■ 概要
GitHub Copilotは、GitHubとOpenAIが共同開発したAIペアプログラミングツールである。
OpenAI Codexモデルをベースに、コードエディタ上でリアルタイムにコード補完・生成を行う。
2021年6月にテクニカルプレビューとして公開され、2022年6月21日に一般提供（GA）を開始した。
月額$10/個人、$19/ビジネスの価格設定で、開発者の生産性を飛躍的に向上させるツールとして
ソフトウェア開発業界に大きなインパクトを与えた。

■ 解決する課題
・定型コード（ボイラープレート）の繰り返し記述による開発効率の低下
・APIドキュメントの検索・参照に費やす時間
・テストコード作成の負担
・馴染みのない言語・フレームワークでの開発時の学習コスト
・コードレビューの負担増大（チーム規模拡大に伴う）
・Stack Overflow等での検索・コピー&ペーストワークフローの非効率性

■ 主な機能
・コード補完：カーソル位置に基づく複数行のコード提案（Ghost Text）
・コメントからのコード生成：自然言語コメントをコードに変換
・多言語対応：Python、JavaScript、TypeScript、Ruby、Go、Java等の主要言語に対応
・コンテキスト理解：開いているファイルや周辺コードを考慮した提案
・複数候補の提示：Alternative Suggestionsで異なる実装パターンを選択可能
・エディタ統合：VS Code、JetBrains IDE、Neovim、Visual Studio対応

■ 技術スタック
・AIモデル：OpenAI Codex（GPT-3ベースのコード特化モデル）
・学習データ：GitHubの公開リポジトリのソースコード
・インフラ：Microsoft Azure上でホスティング
・エディタ拡張：Language Server Protocol（LSP）ベースの統合
・通信：リアルタイムAPI呼び出し（エディタからクラウドへ）

■ 価格プラン（2022年GA時点）
・Individual：$10/月 または $100/年
・Business：$19/ユーザー/月（2023年2月発表）
・学生・OSS開発者：無料（GitHub Education、人気OSSメンテナー対象）
・60日間の無料トライアル

■ ターゲット市場
・一次ターゲット：プロフェッショナルソフトウェア開発者（全世界約2,700万人）
・二次ターゲット：学生、ホビー開発者、コーディング学習者
・三次ターゲット：企業の開発チーム（セキュリティ要件を満たすBusiness版で対応）
・特に生産性向上へのプレッシャーが強い、スタートアップやテック企業の開発者

■ チーム・資金調達
・開発元：GitHub（2018年にMicrosoft が$7.5Bで買収）
・AI技術提供：OpenAI（Microsoftが2019年に$1B、2021年にさらに追加出資）
・GitHub CEO：Thomas Dohmke（2021年11月就任）
・GitHub全体の従業員数：約3,000名（2022年時点）
・Copilot専任チームの規模は非公開だが、GitHub Next研究チームが中心

■ 当時の状況と実績
・テクニカルプレビュー期間（2021年6月〜2022年6月）：約120万人の開発者が利用
・GA開始後の最初の数ヶ月で有料加入者が急増
・GitHubの内部調査：Copilot使用時にコーディング速度が最大55%向上
・提案されたコードの約40%がそのまま受け入れられると報告
・2022年末時点で有料ユーザー数は非公開だが、2023年2月のBusiness版発表時に
  「急成長中」と表明
・2023年末までに有料ユーザー120万人超を達成（GitHubが2024年初に公開）

■ ロードマップ（2022年時点の公開情報）
・Copilot for Business：企業向け機能の強化（2023年2月に提供開始）
・コードの出典表示機能（既存コードとの類似性検出）
・セキュリティ脆弱性フィルタリング
・より多くのIDE対応
・GitHub Copilot X構想（チャット、PR要約、ドキュメント生成 — 2023年発表）

■ 競合との比較
・Amazon CodeWhisperer：2022年6月プレビュー開始。AWSサービスとの統合が強み。
  2023年4月にGA、個人向け無料プランを提供。Copilotに対する直接的な対抗馬。
・Tabnine：2018年設立のイスラエル企業。オンプレミスでの実行が可能で、
  コードプライバシーを重視する企業に訴求。月額$12。
・Kite：2014年設立のAIコード補完ツール。2022年11月にサービス終了を発表。
  Copilotの登場により競争力を維持できなくなったと見られる。
・IntelliCode（Microsoft）：VS Code内蔵のAI補完。Copilotほど高度ではないが
  無料で利用可能。Copilotの廉価版的位置づけ。

■ 参考文献
・GitHub Blog "GitHub Copilot is generally available" (2022年6月)
・GitHub Research "Quantifying GitHub Copilot's impact" (2022年9月)
・The Verge "GitHub Copilot launches" (2022年6月)
・OpenAI Blog "OpenAI Codex" (2021年8月)
・Wall Street Journal "GitHub's Copilot AI Tool" (2022年)
