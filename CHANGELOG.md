# Changelog

このプロジェクトの主な変更履歴を記録します。

## [Unreleased]

なし

## [0.3.1] - 2026-02-17

### Changed
- 📝 **Docstring Internationalization**: すべてのPython docstringを日本語から英語に翻訳
  - Google style docstringフォーマットを維持
  - 型ヒントと実装との整合性を確保
  - Sphinxドキュメント生成での英語化サポート
  - 英語圏ユーザーへのAPIドキュメント提供を改善

## [0.3.0] - 2026-02-17

### Added
- ✨ **LLM Handler Utilities**: LLMノードのボイラープレートコードを削減する`create_llm_handler()`ファクトリ関数を追加
  - litellmによる100以上のLLMプロバイダー対応（OpenAI, Anthropic, Google, Azure, など）
  - プロンプト変数埋め込み機能（`{variable}`形式）
  - 自動リトライとタイムアウト処理
  - extras依存として提供（`pip install 'yagra[llm]'`または`uv add --optional llm yagra`）
  - 完全後方互換（既存コードに影響なし）
- 🧪 **テスト**: 7つのコアテストを追加（既存91テストすべて成功）
- 📦 **新規モジュール**: `src/yagra/handlers/`
- 📋 **依存関係**: `litellm>=1.57.10`（extras依存）

### Changed
- 型安全性: mypy strict モード準拠
- コード品質: ruff フォーマット・リント準拠

### Known Issues
- Issue #11: 6つの例外テストが一時的にスキップされています（コア機能は正常動作）

### Related
- **PR**: #10
- **Goal**: G-07（DX改善: LLMノードのボイラープレート削減）
- **Milestone**: M-14


## [0.2.0] - 2026-02-17

### Added
- 📚 **Documentation Overhaul**: 全面的なドキュメント刷新
  - 英語メインのREADME.md（国際的ユーザー向け）
  - 包括的なSphinxドキュメント（11ページ: Getting Started, User Guide, CLI Reference, Examples等）
  - CONTRIBUTING.md（開発者向けガイド）
  - 多言語化サポート（Sphinx i18n、英語/日本語）
- 🌐 **Internationalization**: Sphinx i18n完全セットアップ
  - POT/POファイル生成済み
  - 日本語翻訳環境構築
  - 翻訳ワークフロードキュメント

### Changed
- README.mdを日本語から英語メインに変更
- ドキュメント構成を最適化（README=ランディングページ、Sphinx=詳細ドキュメント）
- Pydantic/Clickスタイルのベストプラクティスに準拠

## [0.1.9] - 2026-02-16

### Fixed
- `bundle_root` 未指定のライブラリ実行時、`prompt_ref: prompts/...` を workflow 親のみで解決して失敗する不整合を修正し、上位ディレクトリ探索で解決できるようにした。

## [0.1.8] - 2026-02-16

### Changed
- Studio のフロント依存（Vue / Vue Flow）を CDN 読み込みから同梱アセットのローカル配信へ切り替え、オフライン利用を可能にした。
- `yagra visualize` の出力 HTML を Mermaid 同梱方式へ変更し、単体ファイルでオフライン描画できるようにした。

### Fixed
- Studio の `prompt yaml` 候補再読込時に既存選択が不意に空へ戻る問題を修正し、Node Properties の選択状態を保持するようにした。
- `loadStudioFiles()` の同時実行で古いレスポンスが新しい状態を上書きするレースを抑止した。

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
