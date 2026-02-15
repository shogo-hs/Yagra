# Changelog

このプロジェクトの主な変更履歴を記録します。

## [Unreleased]

### Changed
- なし

### Fixed
- なし

## [0.1.7] - 2026-02-15

### Fixed
- Studio の `prompt_ref` パス解決を workspace root 基準に統一し、`prompts/...` が `workflows/prompts/...` と誤解決される不整合を修正。
- `studio --workflow` 起動時に `bundle_root` 未指定なら `workspace_root` を既定採用し、保存/読込と実行時参照の解決基準を一致させた。

## [0.1.6] - 2026-02-15

### Changed
- Studio の `prompt yaml` 自動生成先を workflow 同階層から workspace root（project root）直下の `prompts/` に変更。
- `studio --workflow` 起動時の `workspace_root` 既定値を調整し、workflow がカレント配下にある場合は project root（カレント）を優先するよう変更。

## [0.1.5] - 2026-02-14

### Fixed
- Studio Launcher の初期化時に JavaScript 構文エラーが発生し、`Open Existing Workflow` の一覧が表示されない不具合を修正。
- HTML 応答内の backslash 正規化ロジックに対する回帰テストを追加。

## [0.1.4] - 2026-02-14

### Fixed
- Studio で subdirectory 配下の workflow を編集する際、`prompt_ref` に workspace 相対パスが保存されて resolver 解決に失敗する不具合を修正。
  - 保存時は `prompt_ref` を workflow 相対パスへ正規化。
  - 読込時は workflow 相対 `prompt_ref` を workspace 相対へ変換して Studio file API と整合。

## [0.1.3] - 2026-02-14

### Added
- Studio の `POST /api/studio/file/read` に `prompt_entries` を追加し、Node Properties で prompt 内容を直接反映できるようにした。
- Node Properties に `prompt key` 入力を追加し、`prompt_ref=<path>#<key>` を UI から作成できるようにした。

### Changed
- `model_ref` を完全廃止し、モデル設定を `nodes[].params.model` のインライン定義へ統一。
- Studio の prompt 導線を Node Properties に一本化し、`Workflow Settings.prompt_catalog` と `Prompt File` セクションを廃止。
- `prompt_ref` 解決仕様を path ベース（`<path>` / `<path>#<key>`）へ統一。
- prompt YAML 自動生成先を workspace 直下から、編集中 workflow YAML と同階層の `prompts/` 配下へ変更。

## [0.1.2] - 2026-02-14

### Added
- Workflow Studio のランチャー導線（既存 workflow 選択 / 新規作成）を追加。
- 保存時バックアップと rollback 安全化を含む Studio 初期運用フローを追加。
- エッジ接続ポート（source/target handle）の永続化を追加。

### Changed
- Studio の Node Properties を専用フォーム化し、`system prompt` / `user prompt` と model 設定を編集しやすく改善。
- `prompt_ref` / `model_ref` の catalog 参照導線と Studio API ドキュメントを整備。
- 単一ノード workflow で `edges: []` を許可するよう validation 契約を更新。
- Studio inbound の port 分離と quickstart/API ドキュメントを改善。

### Fixed
- `prompt_ref` / `model_ref` 利用時の実行時パラメータ正規化を追加し、ref/inline 入力の実行時表現を統一。

## [0.1.1] - 2026-02-14

### Changed
- パッケージ名・import 名を `graphyml` から `yagra` へ変更し、公開 API の主名称を `Yagra` に統一。
- publish workflow にタグ名（`vX.Y.Z`）と `pyproject.toml` の `version` 一致チェックを追加。

## [0.1.0] - 2026-02-13

### Added
- Yagra YAML スキーマ（Pydantic）と検証ロジックを実装。
- Registry パターン（port + in-memory adapter）を実装。
- workflow YAML から LangGraph StateGraph を構築するビルダーを実装。
- `Yagra.from_workflow(...)` / `invoke(...)` の公開 API を追加。
- 分岐・ループ・分割参照を含む利用者向けサンプル YAML を `examples/` に追加。
- 品質ゲート（ruff/mypy/pytest, pre-commit/pre-push）を整備。

### Changed
- README に Zero-Boilerplate の利用例とサンプル導線を追加。
- `docs/product/*` の目標・到達ステップ・進捗状態を最新化。
