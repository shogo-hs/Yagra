# Changelog

このプロジェクトの主な変更履歴を記録します。

## [Unreleased]

### Changed
- 🔄 **Studio: Add Node 統合**: ノード追加を DnD のみに一本化。Add Node ボタン・フォームを廃止し、ドロップ後にサイドパネルで id/handler を設定するフローに統一
- ⌨️ **Studio: キーボードショートカット追加**: Ctrl+S で保存（入力フィールド内でも有効）、Escape で選択解除を追加。ツールバーにショートカットヘルプ表示

### Added
- ✨ **Studio: fan_out エッジ編集**: Edge Properties に items_key / item_key 入力を追加。Send API による並列ファンアウトを UI から直接設定可能に（condition との排他バリデーション付き）
- ✨ **Studio: subgraph ハンドラータイプ**: handler type セレクタに subgraph を追加。workflow_ref 入力フィールドで子ワークフロー YAML を指定可能に
- ✨ **Studio: カスタムパラメータエディタ**: custom / subgraph ハンドラー選択時に任意の key-value パラメータを追加・編集可能な汎用テーブルエディタを追加
- ✨ **Studio: Advanced Model Settings**: LLM ハンドラーに frequency_penalty、presence_penalty、seed、stop パラメータの編集 UI を追加（折りたたみ式）
- 💡 **Studio: 空キャンバスガイダンス**: ノードが 0 個の場合にキャンバス中央に「Drag a node from the left panel to get started」ガイドを表示

## [1.1.0] - 2026-03-01

### Added
- ✨ **C-1: retry / fallback / timeout YAML 宣言**: ノードレベルで retry（max_attempts、backoff 戦略、base_delay_seconds）、timeout_seconds、fallback を YAML で直接宣言可能に
  - `RetrySpec` モデル追加（max_attempts: 1–10、backoff: exponential|fixed、base_delay_seconds: 0–60）
  - `NodeSpec` に `retry` / `timeout_seconds` / `fallback` フィールドを追加（全て Optional）
  - `state_graph_builder` がリトライラッパー・タイムアウトラッパー・フォールバックルーティングを自動適用
  - LLM ハンドラーに `_retry_override` を導入し、YAML レベル retry とハンドラ内リトライの二重実行を防止
  - スキーマバリデーションで fallback ノード ID の存在確認・自己参照禁止を検証
- ✨ **F-0: Studio UI に Resilience Settings 追加**: ノードプロパティパネルに retry 設定（Enable retry チェックボックス、max_attempts、backoff、base_delay）、timeout_seconds テキスト入力、fallback ノードドロップダウンを追加。全ハンドラータイプで利用可能
- ✨ **D-1: プロンプト変数 × state_schema 型安全バリデーション**: `prompt_state_validator` を追加。プロンプトテンプレートの `{variable}` が state_schema または upstream ノードの output_key に存在するかを warning レベルで検証。output_key が state_schema に未定義の場合も warning。state_schema 未定義時は info レベルで通知
- ✨ **F-2: Studio リアルタイムバリデーション**: フォーム変更時に自動でバリデーションを実行し結果をインライン表示
  - `POST /api/workflow/validate` エンドポイント追加（diff 計算なしの軽量バリデーション）
  - JS 側デバウンス（400ms）でフォーム変更時に自動呼び出し（ノード編集・エッジ編集・メタデータ変更・接続追加に対応）
  - バリデーション issue の severity（error/warning/info）を色分きバッジで表示
  - キャンバスノードにエラーハイライト（赤枠）・警告ハイライト（黄枠）を表示
  - `is_valid: true` でも warning/info issue がある場合は「Validation passed (with warnings)」と共に表示
- ✨ **F-1: Studio ノード DnD フル機能**: Studio UI のノード操作を大幅に強化
  - パレットからキャンバスへのドラッグ&ドロップによるノード追加（ID 自動生成、既存フォーム入力も併存）
  - Delete / Backspace キーでノード・エッジを削除（確認ダイアログ付き、start_at/end_at の自動整合）
  - Ctrl+D / Cmd+D でノード複製（ID に `_copy` サフィックス、位置オフセット）
  - dagre ライブラリによる自動レイアウト（LR / TB 方向切替、Auto Layout ボタン）
  - Node Properties パネルに Duplicate / Delete ボタンを追加
- ✨ **D-2: プロンプトバージョニング**: プロンプト YAML に `_meta.version` メタデータを導入し、`prompt_ref` で `@version` サフィックスによるバージョン指定を追加
  - `prompt_ref: "prompts.yaml#greeting@v2"` 構文でバージョンを指定可能（`file@version` も対応）
  - `_meta.version` との照合：不一致時は warning、`_meta` 未定義で `@version` 指定時は warning、`_meta` 存在で未ピン留めは info
  - `prompt_version_validator` を新規追加し、バリデーションパイプラインに統合
  - `yagra prompt info --file <path>` CLI コマンドを追加（`_meta` 情報・プロンプトキー一覧を表示、`--format json` 対応）

### Changed
- **litellm を必須依存に昇格**: オプショナル依存（`yagra[llm]`）から通常依存に変更。全 LLM ハンドラがコア機能であるため、条件付き import パターンを削除し型安全性を向上
- 🔧 **P-0: `is_valid` を error severity のみで判定**: `WorkflowValidationReport.is_valid` が `not self.issues` から `not any(i.severity == "error" for i in self.issues)` に変更。warning/info レベルの issue が追加されても既存ワークフローの valid 判定に影響しない
- 🔧 **コスト推定を litellm に委譲**: 静的コストテーブル（`cost_table.py`）を廃止し、`litellm.cost_per_token()` に委譲。価格情報が litellm のリリースに追従して自動更新される
- 🔧 **Handler DRY 化**: LLM ハンドラ（`llm` / `structured_llm` / `streaming_llm`）の共通ロジックを `_llm_common.py` に抽出（`extract_llm_params`、`interpolate_prompt`、`llm_retry_loop`、`report_token_usage`、`build_params_schema`）。内部リファクタリングのため、ユーザー向け API に変更なし
- 🔧 **ハンドラカタログ分離**: ハンドラカタログを `catalog.py` に集約。内部リファクタリングのため、ユーザー向け API に変更なし

### Removed
- 🗑️ **`yagra visualize` コマンド廃止**: Studio UI に完全統合されたため、Read-Only HTML 可視化コマンドを削除。Mermaid ベンダーアセット（2.7MB）も除去
- 🗑️ **`TraceSinkPort.flush()` 廃止**: 全実装が no-op だった未使用メソッドを削除
- 🗑️ **`cost_table.py` 廃止**: 静的コストテーブルを削除。litellm の動的価格データベースに置換
- 🗑️ **`input_keys` パラメータ廃止（破壊的変更）**: ワークフロー YAML ノードの `params.input_keys` を削除。プロンプトテンプレート内の `{variable}` パターンからの自動抽出のみに統一。v0.4.2 で非推奨化済み（G08-I02）
- 🗑️ **`validate_workflow_file` / `explain_workflow_file` MCP ツール廃止（MCP クライアントに破壊的変更）**: `validate_workflow_file` は `validate_workflow`（`workflow_path` パラメータを使用）に統合。`explain_workflow_file` は `explain_workflow`（`workflow_path` パラメータを使用）に統合。MCP ツール数が 13 から 11 に削減

## [1.0.1] - 2026-02-22

### Added
- ✨ **Phase 5: ワークフロー回帰テスト — Golden Test（G-20, M-49–M-52）**: ワークフロー YAML 変更後にゴールデンケースベースの回帰検証ができる機能を実装。LLM ノードをモック応答で差し替えることで、API 呼び出しなし・決定論的にワークフロー構造の正当性を検証する
  - **M-49 ドメインモデルと保存機構**: `GoldenCase` / `NodeSnapshot` / `ComparisonStrategy` のドメインエンティティを定義。`LocalGoldenCaseStore` で `.yagra/golden/` に JSON 永続化。`GoldenCaseManager` でトレースからのゴールデンケース生成・保存・一覧・削除を提供
  - **M-50 テスト実行エンジンと比較戦略**: `GoldenTestRunner` がゴールデンケースに基づくリプレイテストを実行。LLM ハンドラーをモック応答で差し替え、実行パス・ノード入出力の回帰を検証。比較戦略（exact / structural / skip / auto）に対応
  - **M-51 `yagra golden` CLI コマンド**: `yagra golden save`（トレースからゴールデンケース保存）、`yagra golden test`（回帰テスト実行）、`yagra golden list`（ケース一覧表示）を追加
    - `yagra golden save` に繰り返し指定可能な `--strategy node_id:strategy` を追加。ノード単位の比較戦略上書き（`exact` / `structural` / `skip` / `auto`）を保存時に指定可能。形式不正・未知戦略・重複 node_id はエラーで終了
  - **M-52 MCP ツール `run_golden_tests`**: MCP サーバーに `run_golden_tests` ツールを追加。`propose_update → run_golden_tests → apply_update` の最適化サイクルが MCP 経由で完結
- ✨ **`Yagra.get_last_trace()` public API を追加（Issue #28）**: `observability=True` で実行した直近の `invoke()` トレースを `WorkflowRunTrace | None` として取得可能に。`trace=False` でも in-memory トレースは常に利用でき、`trace=True` は JSON ファイル永続化のみを制御
  - `TraceCollector.reset()` を追加し、`invoke()` ごとにノードトレースをリセット
  - `GoldenTestRunner` と統合テストから `yagra._trace_collector` の private 直接参照（`# noqa: SLF001`）を除去して `get_last_trace()` に統一
- ✨ **M-48 最適化サイクルのドキュメント・サンプルを整備（G-19, G19-I02, G19-I03）**: Build → Run → Analyze → Update の全工程を 30 分以内に完走できるチュートリアルドキュメントを追加
  - `docs/sphinx/source/user_guide/optimization_cycle.md` を新規作成（G19-I02）: Overview・Prerequisites・各ステップ（Build / Run & Observe / Analyze / Propose & Review / Regression Test / Apply or Rollback）・翻訳ワークフロー改善の worked example を収録
  - `docs/agent-integration-guide.md` に「最適化サイクルの自律実行」セクションを追記（G19-I03）: エージェント向けシステムプロンプト例・MCP ツール呼び出し順序・トレース未蓄積時/ゴールデンケース未作成時の対応・完全な E2E 実行例を提供

### Fixed
- 🐛 **Golden Test: 同一ハンドラー名競合を修正（ノード単位モック解決）**: `handler: "llm"` など同じハンドラー名を使う複数ノードがある場合、従来はハンドラー名単位のモック解決により応答が競合することがあった。`resolve_for_node(name, node_id)` を導入し、Golden Test リプレイ時は `node_id` 単位でモックをディスパッチするよう修正
  - `build_state_graph()` は `registry.resolve_for_node(node.handler, node.id)` でハンドラーを解決
  - Golden Test レジストリは LLM モックを `node_id -> handler` として保持し、同名ハンドラーでもノードごとの `output_snapshot` を正しく返却
  - `tests/unit/application/test_golden_test_runner.py` に同一ハンドラー名ノードの回帰テストを追加

### v1.0.1 達成ゴール
- ✅ G-20: ワークフロー変更後にゴールデンケースベースの回帰検証ができる
- ✅ G-19（M-48）: 最適化サイクルのドキュメントとサンプルが整備され、ユーザーが 30 分以内に初回サイクルを完了できる

## [1.0.0] - 2026-02-21

### Added
- ✨ **Phase 4: Approve & Update サイクル（G-18, G-19, M-45–M-47）**: エージェントが提案した YAML 修正をユーザー承認後に安全に適用する仕組みを実装。Build → Run & Observe → Analyze & Propose → Approve & Update の全最適化サイクルがローカル完結で動作
  - `propose_update` MCP ツール: エージェントが生成した候補 YAML の diff とバリデーション結果を返す
  - `apply_update` MCP ツール: 候補 YAML をバックアップ付きで適用（`save_workflow_with_backup` 活用）
  - `rollback_update` MCP ツール: `backup_id` 指定で以前のバージョンに復元
  - `WorkflowEditSession`: diff 生成・バリデーション・パッチ適用を一括管理するセッションクラス
  - `WorkflowFormModel` / `WorkflowFormPatcher`: UI 駆動のフォームベース編集に対応した構造化モデルとパッチャー
  - `WorkflowValidationReporter`: バリデーション結果を修正提案付きのレポートとして出力
  - Build → Run & Observe → Analyze & Propose → Approve & Update の全工程 E2E 統合テストを追加

### Fixed
- 🔧 **asyncio event loop 競合の解消**: `test_mcp_installed_runs_asyncio` で `asyncio.run()` が pytest-anyio の event loop と競合していた問題を `ThreadPoolExecutor` で別スレッド実行することで解消。フルスイート実行時も安定して通過するように

### Changed
- 📈 **テストカバレッジ 91% → 96%**: 全モジュールを対象にカバレッジを改善。`workflow_explainer`, `workflow_form_model`, `workflow_persistence`, `workflow_edit_session`, `edge_rule_validator`, `reference_resolver`, `local_trace_sink`, `workflow_file_store`, `structured_llm_handler`, `template_initializer`, `workflow_validation_reporter` が 100% カバレッジに到達。合計 760 テスト通過

### v1.0.0 達成ゴール
- ✅ G-14: ワークフロー実行時にノード単位の構造化ログが自動出力される
- ✅ G-15: LLM 呼び出しのトークン消費とコストを実行ログから把握できる
- ✅ G-16: コーディングエージェントが実行ログを MCP 経由で取得・分析できる
- ✅ G-17: 複数回の実行結果を集約し、品質傾向を把握できる
- ✅ G-18: エージェントの改善提案に基づき YAML を安全に更新できる
- ✅ G-19: Build→Observe→Analyze→Update の最適化サイクルを手元環境で完結できる

## [0.6.11] - 2026-02-20

### Fixed
- 🔧 **CI: Playwright テストが Chromium 未インストールでエラーになる問題を修正**: GitHub Actions の `quality` ジョブに `playwright install chromium --with-deps` ステップを追加し、Chromium が確実に利用可能になるよう修正
- 🔧 **CI: pytest-playwright の event loop が `asyncio.run()` テストと競合する問題を修正**: pytest-playwright はセッションスコープの event loop を保持するため、既存の `asyncio.run()` を使うテスト（`test_mcp_installed_runs_asyncio`）と同一プロセスで実行すると `cannot be called from a running event loop` エラーが発生していた。Playwright テストを独立した `pytest` プロセスで実行するよう CI を分割

## [0.6.10] - 2026-02-20

### Fixed
- 🐛 **Studio: `workspacePathToPromptRefPath` がワークフローディレクトリ外のパスを正規化しない問題を修正**: ワークスペース基準パスをワークフロー相対パスに変換する際、`../` が必要なケース（兄弟ディレクトリや workspace root 直下のファイル）でも `../` を付けずそのまま返していた。`relativePosixPath` の結果を `../` 有無に関わらず使用するよう修正

### Added
- ✅ **Studio: JS パス変換ユーティリティの pytest-playwright テストを追加**: `promptRefPathToWorkspacePath`・`workspacePathToPromptRefPath`・`getWorkflowDirectoryRelative` 等 7 関数を対象に、実際の Chromium ブラウザ上で JS を実行する統合テストを追加（32 ケース）。サブディレクトリ配置・root 直下配置・`../` 脱出・ラウンドトリップ等のエッジケースをカバー

## [0.6.9] - 2026-02-20

### Fixed
- 🐛 **Studio: `prompt yaml` ドロップダウンが空欄になる問題を修正**: ワークフローファイルが workspace_root のサブディレクトリ（例: `bdi_workflow/`）に置かれている場合、`prompt_ref` に記載された相対パス（`prompts/bdi_prompts.yaml`）をワークスペース基準パス（`bdi_workflow/prompts/bdi_prompts.yaml`）へ変換できず、`yamlFiles` リストの該当エントリと一致しないため dropdown が空欄のように見えていた。`promptRefPathToWorkspacePath` でベアな相対パスもワークフローディレクトリ基準で解決するよう修正
- 🐛 **Studio: dropdown で YAML ファイルを選択して Apply した際に `prompt_ref` のパスが workspace_root 基準になっていた問題を修正**: `workspacePathToPromptRefPath` がワークフローディレクトリからの相対パスへ正規化せず workspace 基準パスをそのまま保存していた。ワークフローファイルの親ディレクトリを基準に相対化するよう修正

## [0.6.8] - 2026-02-20

### Fixed
- 🐛 **Studio: `bundle_root=None` 時に `workspace_root` で上書きされ `prompt_ref` が誤解決される問題を修正**: `create_workflow_studio_server` で `bundle_root` が指定されていない場合、`bundle_root_path` が `workspace_root_path` にセットされてしまい、`prompts/bdi_prompts.yaml` のような相対パスが `<workspace>/prompts/bdi_prompts.yaml` に解決されていた。`None` のまま渡すよう修正し、ワークフローファイルの親ディレクトリを基準に正しく解決されるようになった
- 🐛 **Studio: `build_workflow_catalog_preview` が `build_workflow_form_view` 内で二重に呼び出されていた問題を修正**: `get_form()` から既に呼ばれているにもかかわらず `build_workflow_form_view` 末尾でも重複して呼び出していた。内側の呼び出しを削除し `prompt_catalog_keys=()` に固定することで不要な処理を排除

### Changed
- ⚡ **Studio: ワークフロー一覧取得を高速化**: `rglob("*")` による全ファイル走査（`.venv/` 等を含む数万ファイル）を `os.scandir` ベースの再帰ウォークに変更。除外ディレクトリ（`.venv`, `node_modules`, `__pycache__` 等）には入らないよう早期プルーニングすることで、大規模リポジトリでの「Select Workflow」表示速度を改善

## [0.6.7] - 2026-02-20

### Fixed
- 🐛 **Studio: `prompt_ref` が解決できない場合にプロンプトが表示されない問題を修正**: `build_workflow_form_view` でワークフロー全体の `resolve_workflow_references` が失敗した場合でも、ノードごとに個別に `prompt_ref` ファイルをロードするフォールバックを追加。これにより一部ノードの参照エラーが他ノードのプロンプト表示を妨げなくなった
- 🐛 **`explain_workflow`: `base_dir` なし時に `variable_flow.inputs` が常に空になる問題に警告を追加**: `workflow_dir` が指定されていない（MCP で `base_dir` 未指定）場合、`prompt_ref` ファイルが読めないため変数抽出をスキップするが、その旨の `warnings` エントリが返されなかった。`explain_workflow` のレスポンスに `warnings` フィールドを追加し、スキップが発生したノードの理由を明示するようにした

### Added
- ✨ **MCP: `get_template` ツールを追加**: テンプレート名を渡すとそのテンプレートのファイル一覧と内容（`workflow.yaml`、`prompts/*.yaml` 等）を返す新ツール。`list_templates` でテンプレート名を確認してから `get_template` でサンプルの YAML 構造を把握できるようになり、MCP 経由でのワークフロー作成がドキュメント参照なしでも完結するようになった

## [0.6.6] - 2026-02-20

### Fixed
- 🐛 **`explain_workflow`: `prompt_ref` を辿って変数を正しく抽出**: `resolve_workflow_references` 実行後のワークフローで `prompt_ref` が解決済みの `{system, user}` dict に置き換わるため、変数抽出が常に空リストを返していた問題を修正
  - `_extract_input_variables` の dict ブランチが `content` キーのみ参照していたのを `_extract_vars_from_value` で全フィールド再帰走査に変更
  - `explain_workflow` の `variable_flow` で `prompt_ref` ノードの `inputs` が正しく表示されるようになった

### Added
- ✨ **MCP: `validate_workflow` / `explain_workflow` に `base_dir` TIP を追加**: ツール説明に `base_dir` パラメータを渡すべきケースをガイドとして明記し、エージェントが `prompt_ref` の相対パス解決に失敗しにくくなった
- ✨ **MCP: `list_handlers` にカスタムハンドラーガイドを追加**: `custom_handler_guide` フィールドとして署名規約・ルール・コード例を返すように変更。エージェントが仕様書なしでカスタムハンドラーを実装できる
- ✨ **バリデーション: 条件分岐 source ノードの LLM 出力ラベルヒント**: `llm` ハンドラーが conditional edge の source になっている場合、出力すべきラベル一覧を `severity: info` の `edge_rule_error` として返すように変更。プロンプトにラベル指示が抜けるミスを防ぎやすくなった
  - `EdgeRuleIssue` に `severity` フィールド（`Literal["error","warning","info"]`）を追加
  - `WorkflowValidationIssue` への変換時に `severity` を引き継ぐよう修正

## [0.6.5] - 2026-02-19

### Fixed
- 🐛 **Studio: custom ハンドラノードに Prompt Settings を常時表示**: custom ハンドラ選択時に Prompt Settings セクションが表示されない問題を修正
  - 原因：`showPromptFields` computed が `setup()` の return オブジェクトに含まれていなかったため、テンプレートから常に `undefined`（falsy）として評価されていた
  - チェックボックス（"use prompt (optional)"）を廃止し、LLM ハンドラと同様に Prompt Settings を常時表示するようシンプル化

### Changed
- 📝 **ドキュメント更新**:
  - `prompt_model.md` に system プロンプトへの state 変数自動注入の説明を追加（v0.6.4 相当）
  - `prompt_model.md` に custom ハンドラへの prompt 設定方法とハンドラコード例を追加
  - `prompt_model.md` の Studio Integration セクションを更新（Prompt Settings が custom ハンドラにも表示される旨を明記）
  - `prompt_model.md` の手動 `.format()` 例を修正（組み込みハンドラでは不要な旨を注記）

## [0.6.4] - 2026-02-19

### Added
- ✨ **`system` プロンプトへの state 変数注入サポート**: LLM ハンドラ（`llm` / `streaming_llm` / `structured_llm`）の `system` プロンプトでも `{variable}` 形式で state の値を参照可能に
  - 自動検出モード（`input_keys` 未指定）：`system` と `user` 両テンプレートから `{variable}` を抽出し重複除去した上で両方に展開
  - 明示指定モード（`input_keys` 指定）：従来通り指定されたキーを `system` / `user` 両方に適用
  - `prompt_variable_validator` も `system` プロンプトの変数を検証対象に追加（後方互換性あり）

## [0.6.3] - 2026-02-19

### Added
- ✨ **State Reducer / MessagesState サポート**: `state_schema` フィールドに `reducer: add` および `type: messages` を追加
  - `state_schema` の各フィールドに `reducer: "add"` を指定すると `Annotated[list, operator.add]` 型として解決され、並列ノードの出力を自動集約（fan-in）できる
  - `type: messages` を指定すると LangGraph の `add_messages` reducer が有効化され、チャット履歴が追記モードで管理される
  - 新テンプレート `chat` 追加（MessagesState を使ったシンプルなチャットボット）
- ✨ **Send API / 並列ファンアウト サポート**: `fan_out` エッジによる map-reduce パターンを YAML で宣言的に定義可能に
  - エッジに `fan_out: {items_key, item_key}` を指定すると LangGraph の Send API で並列ディスパッチされる
  - `fan_out` は `condition` と同時指定不可（Pydantic バリデーションで防御）
  - 新テンプレート `parallel` 追加（prepare → 並列 process → aggregate の map-reduce パターン）
- ✨ **SubGraph サポート**: `handler: "subgraph"` ノードで別の workflow YAML をサブグラフとしてネスト可能に
  - `params.workflow_ref` に相対パスを指定すると `build_state_graph` が再帰的にサブワークフローをビルド
  - 親グラフと registry・checkpointer を共有
  - 新テンプレート `subgraph` 追加（main_step → sub_agent → finalize パターン）
- ✨ **edge_rule_validator の fan_out 対応**: `fan_out` エッジを独立したカテゴリとして扱い、通常/conditional エッジとの混在を YAML 検証時点で正しく検出
- ✨ **Studio の `state_schema` エディタ**: Yagra Studio の Workflow Settings パネルに `state_schema` テーブルエディタを追加
  - フィールド名・型・reducer をテーブル形式で編集可能
  - `+ Add Field` / `✕` ボタンで行追加・削除
  - 保存時に YAML の `state_schema` セクションへ自動変換。ロード時に既存 YAML から復元
  - `fan_out` エッジ・subgraph ノードは引き続き YAML 直接編集が必要（Studio 非対応）
- 📝 **ドキュメント更新**:
  - `workflow_yaml.md` に `state_schema`・`fan_out`・subgraph ノードの説明を追加
  - `templates.md` に `parallel`, `subgraph`, `chat` テンプレートを追加
  - `cli_reference.md` の Studio セクションに Workflow Settings パネルと `state_schema` 設定手順を追加

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
