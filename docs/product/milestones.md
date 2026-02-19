# 到達ステップ

最終更新: 2026-02-19 <!-- 競合分析を踏まえ M-35/M-36 を追加 -->

補足:
- M-21〜M-23 は完了（G-09）。`GraphSpec` に `interrupt_before` / `interrupt_after` フィールドを追加しバリデーション統合（M-21）、`build_state_graph()` に `checkpointer` 引数を追加（M-22）、`Yagra` に `from_workflow(checkpointer=)` / `invoke(thread_id=)` / `resume()` を追加（M-23）。MemorySaver を使った中断・再開サイクルの動作を単体テスト 15 件で確認済み。G-01〜G-13 すべて Done。
- M-35 は完了（G-12）。`.github/workflows/validate-example.yml`（yagra validate + explain を GitHub Actions で実行し PR コメントに投稿）、`scripts/pr-comment-example.sh`（PR コメント投稿スクリプト）、`docs/ci-integration-guide.md`（CI 統合ガイド）を提供。
- M-36 は完了（G-13）。multi-agent（orchestrator/researcher/writer パターン）、tool-use（planner/tool_executor/synthesizer パターン）、human-review（generator/publisher + interrupt_before パターン）の 3 テンプレートを追加。各テンプレートに `template.yaml`（ユースケース説明）・動作サンプル（`examples/`）・README を付属。`list_templates_with_info()` で `yagra init --list` にユースケース説明を表示する機能を実装。単体テスト 15 件追加。
- M-28〜M-34 は完了（G-11）。`GraphSpec`/`NodeSpec`/`EdgeSpec` 全フィールドに `description`/`examples` 付与（M-28）、`WorkflowValidationIssue` に `severity`/`context` とファジーマッチ修正提案を追加（M-29）、`yagra explain` コマンド実装（M-30）、`yagra validate --workflow -` で stdin 対応（M-31）、組み込みハンドラーの params スキーマ公開と `yagra handlers` コマンド追加（M-32）、エージェント統合ガイド作成（M-33）、MCP サーバー実装（M-34）。単体テスト 181 件（+約 60 件）・ruff/mypy クリア。
- M-27 は完了。WebUI の Schema Settings テキストエリアに入力された YAML スキーマ（`name: str` / `age: int` 等のフラット形式）を `schema_builder.py` で Pydantic BaseModel に動的変換し、`create_structured_llm_handler(schema=None)` 時に `params.schema_yaml` から実行時解決する。Python コードでのスキーマ定義が不要になり、YAML + WebUI だけで構造化出力が完結する。単体テスト 27 件・動的ハンドラーテスト 5 件・結合テスト 3 件追加。
- M-20 は完了。WebUI のノードプロパティパネルに Output Settings セクション（output_key テキスト入力）を追加。isLlmHandler 条件下で表示し、空欄時はデフォルト（"output"）を使用。Apply 時に params.output_key に書き込む。G-08 DoD 達成。
- M-19 は完了。プロンプトテンプレートの `{変数名}` を `re.findall` で自動抽出し、`input_keys` の明示指定が不要になった。`input_keys` 指定時は後方互換で動作（`None` と `[]` を区別）。3 handler すべて対応、単体テスト 5 件追加。
- M-18 は完了（v0.4.1）。handler 入力を type セレクト（llm/structured_llm/streaming_llm/custom）に変更。組み込み型選択時は handler 名を自動入力、custom 選択時のみ自由テキスト入力。
- M-17 は完了。handler 値（llm/structured_llm/streaming_llm）に応じてノードプロパティパネルのフォームが切り替わり、structured_llm では Schema Settings（schema_yaml 入力）、streaming_llm では Streaming Settings（stream: false チェックボックス）が表示される。
- M-15 は完了。`create_structured_llm_handler(schema=PydanticModel)` で型安全な構造化出力が動作することを確認済み。単体テスト 16 件・結合テスト 3 件追加。WebUI スキーマ編集は M-16 にスコープ移動（WebUI フォーム設計の大幅変更を伴うため）。
- M-16 は完了。`create_streaming_llm_handler()` でストリーミングレスポンスを受け取れ、YAML 定義だけで動作することを確認済み。単体テスト 13 件・結合テスト 3 件追加。
- M-14 は完了。`examples/llm-basic/` で YAML 定義だけで LLM 呼び出しが動作することを確認済み。Issue #11（例外テストの fixture 競合）はコア機能に影響なし。

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
| M-13 | G-06 | テンプレートライブラリを整備する | `yagra init --template <name>` で典型パターン（branch, loop, rag 等）のスキャフォールドを生成できる | Done |
| M-14 | G-07 | 基本 LLM ハンドラーユーティリティを提供する | `create_llm_handler()` で litellm 統合ハンドラーを生成でき、YAML 定義だけでテキスト入出力が動作する | Done |
| M-15 | G-07 | 構造化出力ハンドラーを実装する | Pydantic model 指定で型安全な出力を得られ、YAML 定義だけで動作する | Done |
| M-16 | G-07 | ストリーミングハンドラーを実装する | `create_streaming_llm_handler()` でストリーミングレスポンスを受け取れ、YAML 定義だけで動作する | Done |
| M-17 | G-07 | WebUI ハンドラータイプ別フォームを実装する | handler 値に応じてフォームが切り替わり、structured_llm ノードで Pydantic スキーマを WebUI から編集できる | Done |
| M-18 | G-08 | WebUI handler type セレクトを実装する | handler 入力が type セレクト（llm/structured_llm/streaming_llm/custom）になり、組み込み型選択時は handler 名が自動入力される | Done |
| M-19 | G-08 | input_keys を廃止しプロンプト変数を自動検出する | プロンプトテンプレート内の `{変数名}` を自動抽出して state から取得する。`input_keys` パラメータの明示指定が不要になる | Done |
| M-20 | G-08 | WebUI で output_key を設定できるようにする | ノードプロパティパネルに output_key テキスト入力を追加し、I/O が WebUI から完結する | Done |
| M-21 | G-09 | YAML スキーマと検証に HITL フィールドを追加する | `GraphSpec` に `interrupt_before` / `interrupt_after` を追加し、未定義ノード参照をバリデーションで検知できる | Done |
| M-22 | G-09 | StateGraph ビルダーに checkpointer と interrupt を統合する | `build_state_graph()` が checkpointer と interrupt リストを `compile()` に渡し、checkpointer 未設定時に明確なエラーを返す | Done |
| M-23 | G-09 | Yagra API に HITL 実行サイクルを追加する | `from_workflow(checkpointer=)` / `invoke(thread_id=)` / `resume()` で中断・再開のサイクルが動作する | Done |
| M-24 | G-10 | ノードの入力変数・出力変数をグラフ上にバッジ表示する | 各ノードのプロンプト変数（入力）と `output_key`（出力）がノード上にバッジとして表示され、データフローが視覚的に把握できる | Done |
| M-25 | G-10 | データフローバッジの ON/OFF トグルを実装する | ツールバーのトグルスイッチで入力バッジ・出力バッジの表示/非表示を独立に切り替えられ、グラフの視認性を制御できる | Done |
| M-26 | G-10 | 入出力バッジの UX を洗練する | バッジの色分け・ツールチップ・レイアウト崩れ防止など、ノード数が多い実用ワークフローでも視認性を維持できる | Open |
| M-27 | G-07 | WebUI の schema_yaml から動的に Pydantic モデルを生成する | `schema_yaml`（フラットな `key: type` 形式）を WebUI で入力し、Python コードなしで構造化出力が動作する | Done |
| M-28 | G-11 | JSON Schema に意味情報を付与する | `GraphSpec` / `NodeSpec` / `EdgeSpec` の各フィールドに `description` / `examples` を追加し、`params` のハンドラー別構造をドキュメント化する。`yagra schema` 出力だけでエージェントが有効な YAML を書ける | Done |
| M-29 | G-11 | バリデーション結果に修正提案を追加する | `WorkflowValidationIssue` に `severity` / `context`（`actual_value` / `available_values` / `suggestion`）を追加し、ノード ID のファジーマッチによる「もしかして」候補を返す | Done |
| M-30 | G-11 | `yagra explain` コマンドを追加する | ワークフロー YAML を実行せずに解析し、実行パス・必要ハンドラー・変数フローを JSON で出力する | Done |
| M-31 | G-11 | CLI の stdin 対応とパイプライン親和性を向上する | `yagra validate --workflow -` で stdin からの YAML 入力を受け付け、エージェントの生成→検証パイプラインを一時ファイルなしで実行できる | Done |
| M-32 | G-11 | ハンドラースキーマレジストリと `yagra handlers` コマンドを追加する | 組み込みハンドラーが受け付ける `params` の構造を JSON Schema で公開し、`yagra handlers --format json` でエージェントが発見できる | Done |
| M-33 | G-11 | エージェント統合ガイドとワーキングサンプルを整備する | スキーマ取得→YAML 生成→検証→修正ループの worked example と、エージェント向けプロンプト例をドキュメント化する | Done |
| M-34 | G-11 | MCP サーバーとして Yagra 機能を公開する | `validate` / `explain` / `list_templates` / `list_handlers` を MCP ツールとして提供し、エージェントが CLI を経由せずに直接呼び出せる | Done |
| M-35 | G-12 | GitHub Actions 統合を提供する | `yagra validate` を GitHub Actions ワークフローに組み込むサンプル設定と使用ガイドを提供し、PR ごとにワークフロー変更を自動検証できる | Done |
| M-36 | G-13 | テンプレートライブラリを拡充する | multi-agent・tool-use・human-review（G-09 完了後）の実用テンプレートを追加し、各テンプレートに動作可能サンプルコードを付属させる | Done |

## Goal 別の実装項目

各 Goal に紐づく実装項目の完了状況。

### G-01: YAML だけで LangGraph フロー構成を定義できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G01-I01 | Yagra YAML の Pydantic スキーマを定義する | Done | `src/yagra/domain/entities/graph_schema.py` |
| G01-I02 | 条件分岐・ループを含むサンプル YAML を作成する | Done | `examples/workflows/` |
| G01-I03 | 不正 YAML の検証エラーをテスト化する | Done | `tests/unit/domain/test_graph_schema.py` |

### G-02: YAML 定義と Python 実処理を疎結合に接続できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G02-I01 | Registry インターフェースを ports として定義する | Done | `src/yagra/ports/outbound/node_registry.py` |
| G02-I02 | ノード名と callable を紐づける実装を作る | Done | `src/yagra/adapters/outbound/in_memory_node_registry.py` |
| G02-I03 | 未登録ノード時のエラーハンドリングを整備する | Done | `tests/unit/adapters/test_in_memory_node_registry.py` |

### G-03: YAML 差し替えで複数ワークフローを低コストに運用できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G03-I01 | YAML から StateGraph を組み立てるビルダーを実装する | Done | `src/yagra/application/use_cases/state_graph_builder.py` |
| G03-I02 | 複数 YAML で同一実装を切り替えるサンプルを用意する | Done | `tests/fixtures/workflows/` |
| G03-I03 | Zero-Boilerplate の利用例を README に記載する | Done | `README.md` |

### G-04: 開発運用で品質ゲートを常時維持できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G04-I01 | `uv` ベースの品質ゲートを導入する | Done | `pyproject.toml` |
| G04-I02 | GitHub Actions で lint/type/test を自動実行する | Done | `.github/workflows/ci.yml` |
| G04-I03 | pre-commit / pre-push をローカルへ導入する | Done | `.pre-commit-config.yaml` |

### G-05: 非エンジニアが WebUI 上でワークフローを可視化・編集し、迷わず運用できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G05-I01 | WebUI 可視化に必要な検証契約（エラー形式）を定義する | Done | `src/yagra/application/use_cases/workflow_validation_reporter.py` |
| G05-I02 | YAML からノード/エッジ/条件分岐を表示する Read Only 画面を実装する | Done | `src/yagra/application/use_cases/workflow_visualization.py` |
| G05-I03 | ノード詳細で `prompt` / `model` / `*_ref` を確認できるようにする | Done | `src/yagra/application/use_cases/workflow_visualization.py` |
| G05-I04 | 編集保存時の差分確認とロールバック方針を整備する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` |
| G05-I05 | prompt/model/条件をフォーム編集できるようにする | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` |
| G05-I06 | DnD でノード追加とエッジ接続変更を行い round-trip 整合を維持する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` |
| G05-I07 | 主要操作の情報設計と導線を見直し、初見でも操作順が分かる UI にする | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` |
| G05-I08 | レイアウト/配色/ラベル体系を改善し、可読性と視認性を向上する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (M-11) |

### G-06: コーディングエージェントが Yagra ワークフローを正確に生成・検証できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G06-I01 | `yagra schema export` コマンドを実装する | Done | `src/yagra/__init__.py` (`_run_schema_command`) |
| G06-I02 | `yagra validate` コマンドを実装し `--format json` オプションを追加する | Done | `src/yagra/__init__.py` (`_run_validate_command`) |
| G06-I03 | テンプレート YAML を整備する（branch, loop, rag 等） | Done | `src/yagra/templates/` |
| G06-I04 | `yagra init --template` コマンドを実装する | Done | `src/yagra/__init__.py` (`_run_init_command`) |

### G-07: LLM ノードのボイラープレート削減と高度な出力制御ができる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G07-I01 | `create_llm_handler()` ユーティリティを実装する | Done | `src/yagra/handlers/llm_handler.py` |
| G07-I02 | YAML 定義だけで LLM 呼び出しが動作する実行可能なサンプルを整備する | Done | `examples/llm-basic/` |
| G07-I03 | 単体テストを整備する（正常系・リトライ・kwargs 等） | Done | `tests/unit/handlers/test_llm_handler.py` |
| G07-I04 | 構造化出力ハンドラー（Pydantic）を実装する | Done | `src/yagra/handlers/structured_llm_handler.py` |
| G07-I05 | ストリーミングハンドラーを実装する | Done | `src/yagra/handlers/streaming_llm_handler.py` |
| G07-I06 | WebUI でハンドラータイプ別フォームを実装する（structured_llm スキーマ編集含む） | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` |
| G07-I07 | WebUI の `schema_yaml` から動的に Pydantic モデルを生成し、Python コードなしで構造化出力を実現する | Done | `src/yagra/handlers/schema_builder.py`, `src/yagra/handlers/structured_llm_handler.py` (M-27) |

### G-08: YAML で LLM ノードのデータフロー（入出力キー）を宣言的に制御でき、WebUI から設定できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G08-I01 | WebUI の handler 入力を type セレクト（llm/structured_llm/streaming_llm/custom）に変更する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (M-18, v0.4.1) |
| G08-I02 | `input_keys` パラメータを廃止し、プロンプトテンプレートから `{変数名}` を自動検出して state から取得する | Done | `src/yagra/handlers/llm_handler.py` 等 (M-19) |
| G08-I03 | 全組み込み handler で `input_keys` 自動検出に対応する（`llm` / `structured_llm` / `streaming_llm`） | Done | `src/yagra/handlers/*.py` (M-19) |
| G08-I04 | `input_keys` 廃止の後方互換を確保する（指定されていた場合は従来通り動作） | Done | `src/yagra/handlers/*.py` (M-19) |
| G08-I05 | WebUI のノードプロパティパネルに output_key テキスト入力を追加する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (M-20) |

### G-09: ワークフロー実行中に人間の確認・承認・修正を挟める

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G09-I01 | `GraphSpec` に `interrupt_before` / `interrupt_after` フィールドを追加する | Done | `src/yagra/domain/entities/graph_schema.py` |
| G09-I02 | HITL フィールドの参照整合性バリデーションを追加する | Done | `src/yagra/domain/services/schema_validator.py` |
| G09-I03 | バリデーションパイプラインに HITL 検証を統合する | Done | `src/yagra/application/use_cases/workflow_validation_reporter.py` |
| G09-I04 | `build_state_graph()` に `checkpointer` パラメータを追加し interrupt リストを `compile()` に転送する | Done | `src/yagra/application/use_cases/state_graph_builder.py` |
| G09-I05 | `Yagra` クラスに `checkpointer` / `thread_id` / `resume()` を追加する | Done | `src/yagra/__init__.py` |
| G09-I06 | HITL 実行サイクルの統合テストを整備する | Done | `tests/unit/domain/test_hitl.py` |

### G-10: WebUI のグラフ上で各ノードの入力変数と出力変数を一目で把握できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G10-I01 | ノードの `rawNode.params` から入力変数（`prompt`(dict) または `prompt_ref`(str) があればテンプレートの `{変数名}` または `input_keys`）を抽出する JavaScript ヘルパーを実装する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (WorkflowNode 内) |
| G10-I02 | ノードの `rawNode.params` から出力変数（`output_key` が明示指定されている場合のみ。conditional edge の source ノードには `__next__` を追加）を抽出する JavaScript ヘルパーを実装する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (WorkflowNode 内) |
| G10-I03 | `buildNodesFromPayload()` で抽出した入力変数・出力変数を `node.data` に格納する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (buildNodesFromPayload) |
| G10-I04 | WorkflowNode コンポーネントのテンプレートに入力バッジ（IN ラベル＋変数名 pill）を追加する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (WorkflowNode template) |
| G10-I05 | WorkflowNode コンポーネントのテンプレートに出力バッジ（OUT ラベル＋変数名 pill）を追加する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (WorkflowNode template) |
| G10-I06 | 入力バッジ・出力バッジの CSS スタイル（色分け・pill デザイン・レスポンシブ対応）を実装する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (CSS) |
| G10-I07 | ツールバーに入力バッジ ON/OFF トグルと出力バッジ ON/OFF トグルを追加する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (toolbar) |
| G10-I08 | バッジ数が多い場合のレイアウト崩れ防止（折り返し上限・ツールチップ展開）を実装する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` (CSS/JS) |
| G10-I09 | Read-Only 可視化 HTML にも入出力変数情報を表示する | Done | `src/yagra/application/use_cases/workflow_visualization.py` |

### G-11: コーディングエージェントが Yagra ワークフローを高精度に自律生成・修正できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G11-I01 | `GraphSpec` / `NodeSpec` / `EdgeSpec` の全フィールドに `description` と `examples` を追加する | Done | `src/yagra/domain/entities/graph_schema.py` |
| G11-I02 | `params` のハンドラー別構造（`prompt_ref`, `model`, `schema_yaml` 等）をスキーマドキュメントとして整備する | Done | `src/yagra/domain/entities/graph_schema.py`, `src/yagra/handlers/*_handler.py` |
| G11-I03 | `WorkflowValidationIssue` に `severity` / `context` フィールドを追加する | Done | `src/yagra/application/use_cases/workflow_validation_reporter.py` |
| G11-I04 | ノード ID 参照エラー時にファジーマッチで候補を提示する | Done | `src/yagra/domain/services/schema_validator.py` |
| G11-I05 | `yagra explain` コマンドを実装する（実行パス・必要ハンドラー・変数フローの JSON 出力） | Done | `src/yagra/__init__.py`, `src/yagra/application/use_cases/workflow_explainer.py` |
| G11-I06 | `yagra validate` で stdin (`--workflow -`) を受け付ける | Done | `src/yagra/__init__.py` |
| G11-I07 | 組み込みハンドラーの params スキーマを登録・公開する仕組みを実装する | Done | `src/yagra/handlers/*_handler.py` |
| G11-I08 | `yagra handlers --format json` コマンドを実装する | Done | `src/yagra/__init__.py` |
| G11-I09 | エージェント統合ガイド（生成→検証→修正ループの worked example）を作成する | Done | `docs/agent-integration-guide.md` |
| G11-I10 | MCP サーバーを実装し、`validate` / `explain` / `list_templates` / `list_handlers` をツールとして公開する | Done | `src/yagra/adapters/inbound/mcp_server.py` |

### G-12: ワークフロー定義を Git で管理し、CI で自動検証できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G12-I01 | GitHub Actions での `yagra validate` 実行サンプルを作成する | Done | `.github/workflows/validate-example.yml` |
| G12-I02 | CI 統合ガイドドキュメントを整備する | Done | `docs/ci-integration-guide.md` |
| G12-I03 | `yagra explain` の出力を PR コメントに貼り付けるサンプルスクリプトを提供する | Done | `scripts/pr-comment-example.sh` |

### G-13: 多様なユースケースに対応するテンプレートから素早く開発を開始できる

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G13-I01 | multi-agent テンプレートを追加する（エージェント間連携パターン） | Done | `src/yagra/templates/multi-agent/` |
| G13-I02 | tool-use テンプレートを追加する（外部ツール呼び出しパターン） | Done | `src/yagra/templates/tool-use/` |
| G13-I03 | human-review テンプレートを追加する（G-09 完了後：HITL パターン） | Done | `src/yagra/templates/human-review/` |
| G13-I04 | 各テンプレートに動作可能なサンプルコードを付属させる | Done | `examples/` |
| G13-I05 | `yagra init --list` でテンプレート一覧にユースケース説明を追加する | Done | `src/yagra/__init__.py` |

## 運用ルール

- マイルストーンは時期ではなく「到達ステップ」として管理する。
- 各マイルストーンは必ず Goal ID に紐づける。
- 完了したマイルストーンは削除せず、状態を `Done` に更新して履歴を残す。
- Goal 別の実装項目は、マイルストーン完了時に状態を更新する。
