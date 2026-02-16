# 到達ステップ

最終更新: 2026-02-16

## ステップ一覧

| Milestone ID | 対応 Goal ID | 到達ステップ | 完了条件 | 状態 |
| --- | --- | --- | --- | --- |
| M-01 | G-01 | Yagra YAML スキーマ（nodes/edges/params）を確定する | Pydantic モデルで妥当性検証し、失敗ケースをテスト化する | Done |
| M-02 | G-02 | Registry パターンでノード実装をバインド可能にする | 文字列キーから callable 解決ができ、未登録時エラーが明示される | Done |
| M-03 | G-03 | YAML から LangGraph StateGraph を構築するビルダーを実装する | 複数 YAML で異なるフローが実行できるデモが動作する | Done |
| M-04 | G-04 | CI とローカル品質ゲートを整備する | `ruff` / `mypy` / `pytest` / pre-commit が継続運用可能な状態になる | Done |
| M-05 | G-05 | WebUI 向けの検証契約を定義する | 構造エラー・参照エラー・エッジ制約違反を UI 表示可能な形式で返却できる | Done |
| M-06 | G-05 | WebUI でワークフロー可視化（Read Only）を実現する | YAML 読み込みでノード/エッジ/condition とノード詳細を表示できる | Done |
| M-07 | G-05 | WebUI 編集の保存・差分基盤を整備する | 編集内容を安全保存でき、失敗時のロールバック方針が定義される | Done |
| M-08 | G-05 | WebUI 上で prompt/model/条件のフォーム編集を可能にする | 非エンジニアがコード変更なしで主要設定を更新し、即時検証できる | Done |
| M-09 | G-05 | WebUI 上で DnD によるノード追加・接続編集を実現する | ノード追加・接続変更・round-trip 検証が成立し、YAML 意味整合が維持される | Done |
| M-10 | G-05 | UI 情報設計と操作導線を明確化する | Add Node / Connect / Rewire / Save の流れが画面上で理解でき、主要操作が座標手入力なしで完了できる | Done |
| M-11 | G-05 | UI ビジュアル品質と可読性を向上する | レイアウト・配色・ラベル体系を改善し、重要情報の判別と誤操作防止が現状より向上する | Done |
| M-12 | G-06 | JSON Schema 公開と validate CLI を整備する | `yagra schema export` で JSON Schema を出力でき、`yagra validate --format json` で構造化エラーを返却できる | Done |
| M-13 | G-06 | テンプレートライブラリを整備する | `yagra init --template <name>` で典型パターン（branch, loop, rag 等）のスキャフォールドを生成できる | Todo |

## 運用ルール

- マイルストーンは時期ではなく「到達ステップ」として管理する。
- 各マイルストーンは必ず Goal ID に紐づける。
- 完了したマイルストーンは削除せず、状態を `Done` に更新して履歴を残す。
