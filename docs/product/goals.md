# ユーザー到達状態ゴール

最終更新: 2026-02-19 <!-- 競合分析を踏まえ G-12/G-13 を追加 -->

## ゴール一覧

| Goal ID | ユーザーが到達したい状態 | 到達判定（Definition of Done） | 状態 |
| --- | --- | --- | --- |
| G-01 | YAML だけで LangGraph フロー構成を定義できる | ノード・エッジ・条件分岐を含む YAML を Pydantic で検証できる | Done |
| G-02 | YAML 定義と Python 実処理を疎結合に接続できる | Registry でノード名から Python callable を解決し、実行に成功する | Done |
| G-03 | YAML 差し替えで複数ワークフローを低コストに運用できる | Graph 構築コードを追加せずに設定変更だけで別フローを起動できる | Done |
| G-04 | 開発運用で品質ゲートを常時維持できる | CI / pre-commit で format・lint・type・test が一貫して通る | Done |
| G-05 | 非エンジニアが WebUI 上でワークフローを可視化・編集し、迷わず運用できる | Read Only 可視化と編集（prompt/model/エッジ接続）を WebUI で行い、round-trip 後も意味整合を維持しつつ、主要操作の導線と視認性が初見ユーザーにとって自己説明的である | Done |
| G-06 | コーディングエージェントが Yagra ワークフローを正確に生成・検証できる | JSON Schema 公開と validate CLI の JSON 出力により、エージェントがスキーマ準拠の YAML 生成→検証→修正ループを実行できる。加えて、テンプレートライブラリにより典型パターンの生成精度が向上している | Done |
| G-07 | LLM ノードのボイラープレート削減と高度な出力制御ができる | 基本的な LLM 呼び出し、構造化出力（Pydantic）、ストリーミングレスポンスをハンドラーユーティリティで簡潔に実装でき、YAML 定義だけで動作する | Done |
| G-08 | YAML で LLM ノードのデータフロー（入出力キー）を宣言的に制御でき、WebUI から設定できる | `input_keys` を廃止しプロンプト変数を自動検出する仕組みにより YAML 記述量を削減し、`output_key` を WebUI から設定できる。handler タイプ別の責務分離（`llm`: 1 キー出力、`structured_llm`: 複数キー構造化出力、`custom`: 自由制御）が明確になっている | Done |
| G-09 | ワークフロー実行中に人間の確認・承認・修正を挟める | YAML で `interrupt_before` / `interrupt_after` を宣言し、`Yagra.invoke()` → 中断 → `Yagra.resume()` のサイクルで実行を制御できる | Done |
| G-10 | WebUI のグラフ上で各ノードの入力変数と出力変数を一目で把握できる | 各ノードがプロンプトで要求する変数（入力）と `output_key`（出力）がグラフノード上にバッジとして表示され、ON/OFF トグルで表示切り替えができる | Done |
| G-11 | コーディングエージェントが Yagra ワークフローを高精度に自律生成・修正できる | スキーマに意味情報（description/examples）が含まれ、バリデーションが修正提案を返し、ハンドラーパラメータが発見可能で、エージェントが生成→検証→修正ループを人間の介入なしに完結できる。加えて、エージェント統合ガイドにより導入手順が明確化されている | Done |
| G-12 | ワークフロー定義を Git で管理し、CI で自動検証できる | `yagra validate` を GitHub Actions に組み込み、PR ごとにワークフロー変更を自動検証できる。変更差分・実行パスの変化が PR コメントとして可視化され、チームがコードレビューと同じ感覚でワークフローをレビューできる | Done |
| G-13 | 多様なユースケースに対応するテンプレートから素早く開発を開始できる | multi-agent・tool-use・human-review 等の実用テンプレートが揃い、`yagra init --list` でユースケース別に選択できる。各テンプレートには動作可能なサンプルコードが付属し、5 分以内に動作確認できる | Done |

## 運用ルール

- アクティブなゴールは 3〜5 個に絞る。
- 各ゴールは必ず「ユーザーが到達したい状態」で書く。
- 各ゴールに `到達判定（Definition of Done）` を 1 つ以上持たせる。

補足:
- G-05 は M-11 で UI ビジュアル品質向上まで完了。CSS Variables によるデザインシステム統一、状態表現の明確化、タイポグラフィ・余白の体系化により、非エンジニアが迷わず運用できる WebUI が整った。
- G-06 は AI-Native 方針に基づく新規ゴール。M-12（JSON Schema + validate CLI）、M-13（テンプレートライブラリ）により完了。コーディングエージェントが Yagra ワークフローを正確に生成・検証できる環境が整った。
- G-07 は DX 改善ゴール。LLM ノードの実装を簡潔にし、初学者の参入障壁を下げる。4 段階で実装：M-14（基本 LLM ハンドラー）、M-15（構造化出力）、M-16（ストリーミング）、M-17（WebUI ハンドラータイプ別フォーム）。
- G-07 は M-17（WebUI ハンドラータイプ別フォーム）の完了をもって Done。M-27 で WebUI の `schema_yaml` から動的 Pydantic モデル生成を追加し、Python コードなしで構造化出力が完結するようになった。G-01〜G-07 すべて Done。
- G-08 は handler データフロー改善ゴール。handler タイプ別の責務整理を前提に、`input_keys` の自動検出と `output_key` の WebUI 設定を実現する。3 段階で実装: M-18（handler type セレクト — v0.4.1）、M-19（input_keys 自動検出 — v0.4.2）、M-20（output_key の WebUI 設定）。G-01〜G-08 すべて Done。
- G-09 は M-21（GraphSpec HITL フィールド追加）・M-22（StateGraph checkpointer 統合）・M-23（Yagra API resume() 追加）の3段階で実装完了。`interrupt_before` / `interrupt_after` バリデーション、MemorySaver 対応の動作確認済み。G-01〜G-09, G-10, G-11 すべて Done。
- G-10 は M-24（バッジ表示）、M-25（ON/OFF トグル）の完了をもって Done（v0.5.0）。Studio WebUI および Read-Only 可視化 HTML の両方で IN/OUT バッジが表示され、ツールバーのチェックボックスで独立したトグルが可能になった。G-01〜G-08, G-10 すべて Done。
- G-11 は G-06（AI-Native 基盤）を深化させるゴール。M-28（スキーマ意味情報付与）・M-29（バリデーション修正提案）・M-30（explain コマンド）・M-31（stdin 対応）・M-32（handlers コマンド）・M-33（エージェント統合ガイド）・M-34（MCP サーバー）の 7 マイルストーンで実装完了。G-01〜G-11 すべて Done。
- G-12 は M-35（GitHub Actions 統合）で実装完了。`.github/workflows/validate-example.yml`、PR コメントスクリプト、CI 統合ガイドを提供し、LangFlow・Flowise 等が不得意とする CI/CD 統合領域で競合優位を確立した。
- G-13 は M-36（テンプレート拡充）で実装完了。multi-agent・tool-use・human-review の 3 テンプレートを追加（合計 6 テンプレート）。各テンプレートに `template.yaml`（メタ情報）・動作サンプル・README を付属。`yagra init --list` にユースケース説明を表示する機能も追加。
