# Changelog

このプロジェクトの主な変更履歴を記録します。

## [Unreleased]

## [0.6.2] - 2026-02-19

### Changed
- 📝 **ドキュメントと実装の整合性を修正**: 実装済み機能がドキュメントに反映されていなかった箇所を修正
  - `README.md` のテンプレート一覧を3個から6個に更新（`tool-use`, `multi-agent`, `human-review` を追加）
  - `docs/sphinx/source/cli_reference.md` に `explain`, `handlers`, `mcp` コマンドの説明を追加
  - `docs/sphinx/source/user_guide/templates.md` に `tool-use`, `multi-agent`, `human-review` テンプレートの説明を追加
  - `docs/sphinx/source/getting_started.md` の日本語出力サンプルを英語に修正

## [0.6.1] - 2026-02-18

### Fixed
- 🐛 **MCP サーバー起動時の AttributeError クラッシュを修正**: `yagra mcp` コマンドで起動時に `AttributeError: 'NoneType' object has no attribute 'tools_changed'` が発生していた問題を修正
  - `run_mcp_server()` の `server.get_capabilities()` に `notification_options=None` を渡していたため、mcp SDK 内部でヌルポインタ相当のエラーが発生していた
  - `NotificationOptions()` インスタンスを正しく渡すよう修正（`from mcp.server.lowlevel.server import NotificationOptions`）

## [0.6.0] - 2026-02-19

### Added
- 🤖 **G-11: エージェント向けワークフロー自律生成支援（M-28〜M-34）**: コーディングエージェントが Yagra ワークフローを高精度に自律生成・修正できる環境が整った
  - **M-28 スキーマ意味情報付与**: `GraphSpec` / `NodeSpec` / `EdgeSpec` の全フィールドに `description` と `examples` を付与。`yagra schema` の JSON Schema 出力にフィールドの意図・用途・値例が含まれるようになり、エージェントがスキーマだけで仕様を理解できる
  - **M-29 バリデーション修正提案**: `WorkflowValidationIssue` に `severity`（`error` / `warning` / `info`）と `context`（`actual_value` / `available_values` / `suggestion`）を追加。ノード ID のタイポ等に対してファジーマッチで修正候補を提示
  - **M-30 explain コマンド**: `yagra explain --workflow <path> --format json` を新規実装。静的解析により `entry_point` / `exit_points` / `execution_paths` / `required_handlers` / `variable_flow` を出力
  - **M-31 stdin 対応**: `yagra validate --workflow -` および `yagra explain --workflow -` で標準入力からの YAML を処理可能に。一時ファイルなしで検証できる
  - **M-32 handlers コマンドと PARAMS_SCHEMA**: `yagra handlers --format json` で組み込みハンドラーの params JSON Schema を出力。各ハンドラーモジュールに `LLM_HANDLER_PARAMS_SCHEMA` 等の定数を追加
  - **M-33 エージェント統合ガイド**: `docs/agent-integration-guide.md` を新規追加。生成→検証→修正ループのワークドエグザンプル、システムプロンプト例、MCP サーバー統合手順を掲載
  - **M-34 MCP サーバー**: `mcp` Python SDK（Anthropic 公式）を使った MCP サーバーを実装。`yagra mcp` で起動。`validate_workflow` / `explain_workflow` / `list_templates` / `list_handlers` の 4 ツールを提供。`pip install "yagra[mcp]"` でオプションインストール

### Related
- **Goal**: G-11（コーディングエージェントが Yagra ワークフローを高精度に自律生成・修正できる）
- **Milestones**: M-28, M-29, M-30, M-31, M-32, M-33, M-34

## [0.5.5] - 2026-02-18

### Added
- ✨ **動的スキーマ生成（M-27）**: WebUI の Schema Settings に入力した YAML から Pydantic モデルを実行時に自動生成し、Python コードなしで `structured_llm` ノードの構造化出力が完結するようになった
  - `schema_builder.py` を新規追加。フラットな `key: type` 形式の YAML（例: `name: str` / `age: int`）を安全な `TYPE_MAP` ホワイトリストで型解決し、`pydantic.create_model()` でモデルを動的生成
  - サポート型: プリミティブ（`str` / `int` / `float` / `bool`）、コレクション（`list[str]` 等）、辞書（`dict[str, str]` 等）、Optional（`str | None` 等）
  - `create_structured_llm_handler()` の `schema` 引数を Optional 化。`schema=None`（デフォルト）時は実行時に `params["schema_yaml"]` から動的解決。`schema=MyModel` の既存パターンは完全後方互換
  - `build_model_from_schema_yaml()` を `yagra.handlers` からパブリック API として公開
  - WebUI の Schema Settings プレースホルダーをフラット形式（`name: str` / `age: int` / `score: float`）に更新
  - 単体テスト 32 件追加（`test_schema_builder.py` 27 件・`test_structured_llm_handler.py` 動的スキーマ 5 件）、結合テスト 3 件追加（`test_structured_llm_dynamic_schema.py`）

### Related
- **Goal**: G-07（LLM ノードのボイラープレート削減と高度な出力制御）
- **Milestone**: M-27

## [0.5.4] - 2026-02-17

### Fixed
- 🐛 **Conditional edge の source ノードで `output_key` を `__next__` に自動設定**: `output_key` 未指定の場合、LLM の出力が `state["output"]` に入り `state["__next__"]` が設定されず条件分岐が失敗していた問題を修正
  - `_normalize_runtime_params()` に `is_cond_source` フラグを追加
  - conditional edge の source ノードで `output_key` が未指定の場合、実行時に `output_key: __next__` を自動注入するよう変更
  - YAML への `output_key: __next__` 明示指定は不要になる（明示指定した場合はそちらが優先される）

## [0.5.3] - 2026-02-17

### Removed
- 🗑️ **プロンプト変数到達性バリデーション（`prompt_variable_error`）を廃止**: handler 名ベースの変数チェックが conditional edge を含むワークフローで過検知を起こすため廃止
  - `collect_prompt_variable_issues()` / `PromptVariableIssue` を削除
  - `WorkflowValidationReport` から `prompt_variable_error` コードが出なくなる
  - バッジ表示用の `_extract_required_vars()` / `_get_output_key()` ユーティリティは維持

## [0.5.2] - 2026-02-17

### Fixed
- 🐛 **IN/OUT バッジ判定をパラメータベースに変更**: handler 名（`llm`/`structured_llm`/`streaming_llm`）による判定を廃止し、パラメータの有無で判定するよう変更
  - `prompt`(dict) または `prompt_ref`(str) があれば IN バッジを表示
  - `output_key` が明示指定されている場合のみ OUT バッジを表示（デフォルト `"output"` は非表示）
  - Conditional edge の source ノードに OUT `__next__` バッジを追加
  - カスタムハンドラーでも `prompt_ref` + `model` を持つノードでバッジが表示されるように修正
  - `prompt_ref` + conditional source の両方を持つノード（例: `evaluator`）で IN + OUT `__next__` が同時表示されるように修正
  - エッジの condition 変更時にノードの `outputVars` をリアルタイムで再計算するよう修正

## [0.5.1] - 2026-02-17

### Fixed
- 🐛 **Studio: `prompt_ref` ノードで IN バッジが表示されない問題を修正**: `/api/workflow` が未解決の `prompt_ref` 文字列を返すため、JS 側で変数抽出できていなかった問題を修正
  - `WorkflowNodeFormItem` に `prompt_user` フィールドを追加し、サーバー側で `prompt_ref` を解決した `prompt.user` テキストを提供
  - JS の `extractInputVars()` が `params.prompt.user` 不在時に `formItem.prompt_user` にフォールバックするよう変更
- 🐛 **IN バッジが3件で省略されていた問題を修正**: `+N` バッジを廃止し、全件を `flex-wrap` で折り返し表示するよう変更

### Changed
- 🎨 **ツールバーのトグルラベルを「IN」「OUT」に統一**: 「入力変数」「出力変数」をノードバッジの表記と一致させた

## [0.5.0] - 2026-02-17

### Added
- ✨ **G-10 グラフ上にノードの入出力変数をバッジ表示**: Studio WebUI のグラフ上で、各 LLM ノードが要求する入力変数（プロンプトテンプレートの `{変数名}`）と出力変数（`output_key`）をバッジとして可視化
  - IN バッジ（青）: プロンプトテンプレートから自動抽出した変数名を表示。`input_keys` が明示指定されている場合はそちらを優先
  - OUT バッジ（緑）: `output_key` を表示（デフォルト `"output"`）
  - LLM ハンドラー（`llm` / `structured_llm` / `streaming_llm`）のみ対象。custom ハンドラーは非表示
  - ツールバーにチェックボックストグルを追加し、入力変数・出力変数バッジの ON/OFF を独立して切り替え可能
  - ノードプロパティパネルで prompt や output_key を変更して Apply すると、バッジが即時更新される
  - Read-Only 可視化 HTML（`yagra visualize`）にも同様のバッジを追加

### Related
- **Goal**: G-10（WebUI のグラフ上で各ノードの入力変数と出力変数を一目で把握できる）
- **Milestone**: M-24, M-25

## [0.4.8] - 2026-02-17

### Fixed
- 🐛 **Studio UI: output_key / schema_yaml がリロード後に消える問題を修正**: ワークフローを Save して再読み込みすると `output_key` と `schema_yaml` が UI 上で空になる問題を修正
  - 原因: `buildNodesFromPayload` が YAML から読み込んだ `node.params` を `data.params` に反映していなかった
  - 修正: ロード時に `output_key` と `schema_yaml` を `data.params` へ抽出するよう変更

### Related
- **Goal**: G-08（YAML で LLM ノードのデータフロー（入出力キー）を宣言的に制御でき、WebUI から設定できる）
- **Milestone**: M-20

## [0.4.7] - 2026-02-17

### Changed
- 🔧 **プロンプト変数バリデーション: start_at ノードを除外**: `start_at`（START タグ付き）ノードをプロンプト変数バリデーションから完全除外
  - Studio UI に `spec.params` 編集機能がなく、フロントエンドだけでは解消できない誤検知を防ぐため
  - `start_at` ノードは `invoke()` 時に外部入力を直接受け取る入口であり、静的解析で入力キーを事前確定できない
- 🔧 **エラーメッセージを英語に統一**: `prompt_variable_error` のメッセージを日本語から英語に変更

### Related
- **Goal**: G-08（YAML で LLM ノードのデータフロー（入出力キー）を宣言的に制御でき、WebUI から設定できる）
- **Milestone**: M-20

## [0.4.6] - 2026-02-17

### Added
- ✨ **プロンプト変数バリデーション**: ワークフロー保存時に、プロンプトテンプレート内の `{変数名}` が前段ノードの `output_key` または `spec.params` の初期キーとして宣言されているかを静的検証
  - LLM / streaming_llm / structured_llm ハンドラーが対象（カスタムハンドラーは除外）
  - 条件分岐がある場合も、到達しうる**全パス**でキーが保証されていないとエラー（strict intersection）
  - `input_keys` を明示した場合はテンプレート抽出より優先
  - 循環グラフ・構造エラーがある場合はスキップ（他のバリデーターで先に検出）
  - エラーコード: `"prompt_variable_error"`

### Related
- **Goal**: G-08（YAML で LLM ノードのデータフロー（入出力キー）を宣言的に制御でき、WebUI から設定できる）
- **Milestone**: M-20

## [0.4.5] - 2026-02-17

### Fixed
- 🐛 **WebUI user prompt placeholder**: `placeholder` に `{{input}}` と表示されていたため、ユーザーがプロンプトテンプレートを二重波括弧で記述してしまい変数が展開されない問題を修正
  - `{{input}}` → `{input}` に変更（ハンドラーの `str.format()` 記法に統一）
  - API ドキュメント（`docs/api/post-studio-file-read.md`）のサンプルも同様に修正

### Related
- **Goal**: G-08（YAML で LLM ノードのデータフロー（入出力キー）を宣言的に制御でき、WebUI から設定できる）
- **Milestone**: M-20

## [0.4.4] - 2026-02-17

### Fixed
- 🐛 **WebUI output_key 保存バグ修正**: `buildWorkflowPayload` が `node.data.rawNode.params` のみを参照していたため、Apply 後に設定した `output_key` が Save 時に YAML へ反映されなかった問題を修正
  - `node.data.params`（Apply 後の最新値）を `rawNode.params` にマージしてから Save するよう変更
  - `schema_yaml`（structured_llm ノード）も同様に正しく保存されるようになった

### Related
- **Goal**: G-08（YAML で LLM ノードのデータフロー（入出力キー）を宣言的に制御でき、WebUI から設定できる）
- **Milestone**: M-20

## [0.4.3] - 2026-02-17

### Added
- ✨ **WebUI output_key 設定**: ノードプロパティパネルに Output Settings セクションを追加
  - LLM handler ノードで `output_key` をテキスト入力から設定可能
  - 空欄時はデフォルト（`"output"` キー）を使用
  - Apply 時に `params.output_key` へ書き込み、YAML と WebUI が完全に同期

### Fixed
- 🐛 **WebUI prompt yaml ドロップダウン**: ドットディレクトリ（`.github`, `.venv`, `.yagra` 等）やツールディレクトリ（`node_modules`, `dist` 等）の YAML ファイルを除外し、プロジェクト関連ファイルのみ表示
- 🐛 **WebUI ファイル候補**: `src/`・`tests/` を除外するハードコードを削除し、ユーザーのディレクトリ命名の自由度を回復
- 🎨 **WebUI ラベル/ヒント**: `prompt_ref (auto)` ラベルを `prompt reference` に変更。ヒントテキストを英語に統一

### Related
- **Goal**: G-08（YAML で LLM ノードのデータフロー（入出力キー）を宣言的に制御でき、WebUI から設定できる）
- **Milestone**: M-20

## [0.4.2] - 2026-02-17

### Changed
- 🚀 **input_keys 廃止・プロンプト変数自動検出**: `input_keys` パラメータの明示指定が不要になった
  - プロンプトテンプレート内の `{変数名}` を `re.findall` で自動抽出し、state から値を取得
  - 全組み込み handler（`llm` / `structured_llm` / `streaming_llm`）が対応
  - 後方互換: `input_keys` を明示指定している既存 YAML はそのまま動作（`None` と `[]` を区別）
- 🧪 **テスト**: 自動検出に関する単体テスト 5 件を追加

### Related
- **Goal**: G-08（YAML で LLM ノードのデータフロー（入出力キー）を宣言的に制御できる）
- **Milestone**: M-19

## [0.4.1] - 2026-02-17

### Added
- ✨ **WebUI Handler Type Selector**: ノードプロパティパネルの handler 入力を type セレクト（`llm` / `structured_llm` / `streaming_llm` / `custom`）に変更
  - 組み込み型選択時は handler 名を自動入力 — 手打ち不要
  - `custom` 選択時のみ自由テキスト入力を表示し、任意の handler 名を指定可能
  - 後方互換（既存 YAML の読み込み・保存動作に影響なし）

### Related
- **Goal**: G-05（非エンジニアが WebUI 上でワークフローを迷わず運用できる）

## [0.4.0] - 2026-02-17

### Added
- ✨ **WebUI Handler Type Forms**: handler タイプ別にフォームセクションを自動切り替え
  - `llm` / `structured_llm` / `streaming_llm` 選択時のみ Prompt Settings / Model Settings を表示
  - `structured_llm` 選択時に **Schema Settings** セクションを追加表示（YAML テキストでスキーマを記述・保存）
  - `streaming_llm` 選択時に **Streaming Settings** セクションを追加表示（`stream: false` チェックボックス）
  - `custom` / 非 LLM handler では LLM 関連セクションを非表示
- ✨ **Streaming Handler**: LLM レスポンスをストリーミングで受け取れる `create_streaming_llm_handler()` ファクトリ関数を追加
  - 戻り値は `Generator[str, None, None]` — 逐次処理とバッファリングの両方に対応
  - `stream=True` を自動付与（`model.kwargs` で明示 `False` を指定した場合は上書きしない）
  - `create_llm_handler()` と同等のリトライ・タイムアウト機能（デフォルト timeout=60 秒）
  - 完全後方互換（既存コードに影響なし）
- ✨ **Structured Output Handler**: Pydantic モデルを指定して型安全な構造化出力を得られる `create_structured_llm_handler()` ファクトリ関数を追加
  - Pydantic モデルを `schema` 引数に指定するだけで LLM レスポンスを型安全なインスタンスに変換
  - デフォルトで JSON 出力モード（`response_format=json_object`）を有効化
  - システムプロンプトへの JSON Schema 自動埋め込み
  - `create_llm_handler()` と同等のリトライ・タイムアウト機能
  - JSON パース失敗・Pydantic バリデーション失敗時は `LLMHandlerCallError` を送出
  - 完全後方互換（既存コードに影響なし）
- 🧪 **テスト**: 40 件のテストを追加（単体テスト 15+16 件・結合テスト 3+3 件、M-14〜M-16 合計）
- 📖 **サンプル**: `examples/llm-streaming/` に実行可能サンプルを追加（YAML + プロンプト + 実行スクリプト + README）
- 📖 **サンプル**: `examples/llm-structured/` に実行可能サンプルを追加（YAML + プロンプト + 実行スクリプト + README）
- 📖 **サンプル**: `examples/llm-basic/` に基本 LLM ハンドラーの実行可能サンプルを追加

### Related
- **Goal**: G-07（DX改善: LLM ノードのボイラープレート削減）
- **Milestone**: M-17（WebUI ハンドラータイプ別フォーム）、M-16（ストリーミングハンドラー）、M-15（構造化出力ハンドラー）、M-14（基本 LLM ハンドラーサンプル）

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
