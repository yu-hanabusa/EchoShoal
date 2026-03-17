■ 概要
Google Waveは、2009年5月にGoogle I/O開発者会議で発表されたリアルタイムコラボレーションプラットフォームである。「もし今日メールが発明されたらどうなるか」というコンセプトのもと、メール・チャット・Wiki・ドキュメント共同編集を一つの「Wave」と呼ばれるスレッドに統合した。Google Maps開発で知られるLars RasmussenとJens Rasmussen兄弟がシドニーのGoogle開発拠点で設計・開発を主導した。

■ 解決する課題
2009年当時、ビジネスコミュニケーションはメール（非同期）、チャット（同期）、Wiki（知識蓄積）、ドキュメント共同編集がそれぞれ別ツールで行われていた。メールスレッドは長大化し、添付ファイルのバージョン管理は混乱を招いていた。Google Waveはこれらの断片化を解消し、一つの統合空間でリアルタイムコラボレーションを実現することを目指した。

■ 主な機能
- リアルタイム文字入力表示：相手が入力中の文字が1文字ずつリアルタイムに見える
- Wave：メール・チャット・ドキュメントを融合した新しい通信単位
- Wavelet：Wave内の個別の会話スレッド
- Blip：Wavelet内の個々のメッセージ
- ドラッグ＆ドロップによるファイル共有と画像のインライン表示
- Playback機能：Waveの編集履歴を時系列で再生可能
- Extension API：サードパーティがロボット（Bot）やガジェットを開発可能
- Google Wave Federation Protocol：異なるサーバー間でのWave共有を可能にするオープンプロトコル

■ 技術スタック
- フロントエンド：Google Web Toolkit（GWT）ベースのJavaScriptクライアント
- バックエンド：Java（Google App Engine上で動作）
- 通信プロトコル：XMPP拡張によるFederationプロトコル
- リアルタイム同期：Operational Transformation（OT）アルゴリズム
- API：Google Wave Robots API、Google Wave Gadgets API

■ 価格プラン
無料サービス。Googleアカウントがあれば利用可能。ただし2009年9月30日の限定プレビュー開始時は招待制で、初期ユーザー約10万人に招待状が配布された。2010年5月に一般公開された。

■ ターゲット市場
- 企業のプロジェクトチーム（メール代替としてのリアルタイムコラボレーション）
- ソフトウェア開発者（API/拡張機能によるカスタマイズ）
- メディア・出版業界（共同執筆・編集）
- 教育機関（リアルタイム共同学習）

■ チーム・資金調達
Google社内プロジェクトとして、シドニーのGoogle開発拠点で約50名の開発チームにより開発された。プロジェクトリーダーはLars Rasmussen（Google Maps共同開発者）。Jens Rasmussen（同じくGoogle Maps共同開発者）がテクニカルリードを務めた。Google社内予算で運営されており、外部資金調達は不要であった。

■ 当時の状況と実績
2009年5月のGoogle I/Oでのデモは80分間に及び、開発者から大きな注目を集めた。デモ中に会場から何度も拍手が起きた。2009年9月30日に招待制プレビューを開始し、初期には約10万アカウントが配布された。しかし一般ユーザーにとってUIが複雑すぎ、「何に使うのか」が直感的に理解できないという問題が表面化した。パフォーマンスの問題も深刻で、多数の参加者がいるWaveではブラウザが極端に遅くなった。2010年8月4日、GoogleのEric Schmidt CEOがWaveの開発中止を発表した。

■ ロードマップ（発表時点）
- 2009年Q2：Google I/Oでのデモと開発者プレビュー
- 2009年Q3：招待制限定プレビュー開始
- 2010年Q1：サードパーティ拡張機能の充実
- 2010年Q2：一般公開
- 2010年以降：Gmail統合、Google Apps for Business統合（実現せず）

■ 競合との比較
- Gmail：2009年時点で約1.5億ユーザー。非同期メールとして確立。Waveはこれを「置き換える」意図があったが、ユーザーの学習コストが高すぎた
- Microsoft SharePoint：企業向けコラボレーション。複雑だが企業IT部門に浸透
- Campfire（37signals）：シンプルなグループチャット。少人数チーム向け
- EtherPad：リアルタイム共同編集。GoogleがWave開発中の2009年12月に買収
- Yammer：企業内SNS。2008年TechCrunch50で優勝し急成長中

■ 出典
- Rasmussen, L. "Google Wave Developer Preview at Google I/O 2009" (2009年5月28日)
- Google Official Blog "Update on Google Wave" (2010年8月4日)
- Patel, N. TechCrunch "Google Wave is Dead" (2010年8月4日)
- Google Wave Federation Protocol仕様書 (2009年)
