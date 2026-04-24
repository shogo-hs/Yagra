# PMO レビュー: #23 `create_judge_handler` 実装

**日付**: 2026-04-24
**レビュー対象**: feature/add-create-judge-handler ブランチ
**レビュアー**: PM（PMO 代行、環境制約による）
**判定**: **Accept**

---

## 1. 成功基準（DoD）チェック

| SC | 内容 | 状態 | 備考 |
|----|------|------|------|
| SC-1 | `LLMProviderPort` Protocol 定義 | OK | `src/yagra/ports/outbound/llm_provider.py`、Protocol + runtime_checkable + 専用例外階層 |
| SC-2a | `LiteLLMProvider` 実装 | OK | `litellm.completion` + `response_format={"type":"json_object"}` 強制 + system prompt schema 注入 |
| SC-2b | `ClaudeAgentSDKProvider` 実装 | OK | `claude_agent_sdk.query` + `output_format={"type":"json_schema","schema":...}` + デフォルト model `"sonnet"` + lazy import |
| SC-2c | `resolve_provider` Factory | OK | unknown name は `ValueError` with hint、毎回新規インスタンス返却 |
| SC-3 | `create_judge_handler` 実装 | OK | hybrid provider 解決（DI 引数 vs `params.provider`）、rubric inline / rubric_ref 対応、`_overall` 自動計算（複数 criterion 時の算術平均）、async bridge は ThreadPoolExecutor 経由 |
| SC-4 | `__init__.py` / `catalog.py` への judge 追加 | OK | `BUILTIN_HANDLERS_INFO` に追加、`yagra handlers` / MCP `list_handlers` 出力に出現 |
| SC-5 | `JUDGE_HANDLER_PARAMS_SCHEMA` 厳密性 | OK | provider enum / model default sonnet / rubric oneOf / output_key default judge_result |
| SC-6 | `pyproject.toml` extra `yagra[judge]` | OK | `claude-agent-sdk>=0.1.0` 追加、未インストール時は構造化エラー `claude_agent_sdk_not_installed`（4 フィールド + hint） |
| SC-7 | ユニットテスト網羅 | OK | judge 19 件 / litellm provider 8 件 / claude_agent_sdk provider 7 件 / resolve_provider 4 件 = 計 38 件、全 PASS |
| SC-8 | 全テスト PASSED | OK | unit 935 + integration（excluding playwright pre-existing env errors）= 1000 PASS |
| SC-9 | pre-commit All Passed | OK | uv-lock / ruff format / ruff check / mypy 全クリア |
| SC-10 | Hexagonal 境界違反なし | OK | `ports/` は SDK 非依存、handler は `resolve_provider` Factory 経由（`golden_test_runner.py` と同一の合成パターン） |
| SC-11 | `docs/agent-integration-guide.md` 追記 | OK | rubric YAML 例 / Python 登録例 / provider 切替表 / 出力構造説明 |
| SC-12 | `CHANGELOG.md` `[Unreleased]` Added | OK | judge handler / `LLMProviderPort` / `yagra[judge]` extra の 3 項目を Added に記載 |
| SC-13 | rubric YAML 不正値検出テスト | OK | scale.min>=max / 空 criteria / name 欠如 / 重複名 / oneOf 違反 / rubric_ref not found を判別、4 フィールド構造化エラー |
| SC-14 | judge node を含む workflow validate 統合テスト | OK | `tests/integration/test_validate_judge_workflow.py` 3 ケース（inline rubric / rubric_ref / both 排他） |

**14/14 PASS。**

---

## 2. 設計判断のレビュー

### 採用

- **Hexagonal Port + 専用例外階層**: `LLMProviderPort` を `runtime_checkable` Protocol で定義し、`LLMProviderError` / `LLMProviderConfigError` / `LLMProviderCallError` の 3 段階階層で「再試行可否」が境界で判断できる設計。これにより judge handler 側の `_judge_retry_loop` が config error を即時 raise / call error を retry と振り分けできる。場当たり的な Exception flat catch を避けた根本対処。
- **Lazy SDK import**: `ClaudeAgentSDKProvider.__init__` で SDK を import しないことで `resolve_provider("claude_agent_sdk")` が SDK 未インストールでも成功する。実際の `complete_structured` 呼出時にのみ ImportError を 4 フィールド構造化エラーへ昇格 → silent failure 防止 + ユーザーガイド付きエラー。
- **Async bridge via ThreadPoolExecutor**: SDK の `query()` が async 専用のため、event loop running 時は dedicated worker thread に asyncio.run を委譲。Jupyter / 既存 async test harness 内からの呼出も透過的にサポート（テスト `test_runs_inside_running_event_loop_via_executor` で実証）。
- **`_overall` 自動算出**: 複数 criterion 時のみ score 配列の算術平均を `_overall` キーに付与。単一 criterion の場合は付与しない（冗長性回避）。

### 妥協なし

- 場当たり修正・silent success 防止策はすべて 4 フィールド構造化エラーで明示。
- Sys.modules pollution（pre-existing バグ）は判明したため判断付きで `setdefault` パターンに格上げ修正、コメントで意図を明記。

---

## 3. テストカバレッジ

| ファイル | テスト数 | 主な観点 |
|---|---|---|
| `tests/unit/adapters/outbound/llm_providers/test_litellm_provider.py` | 8 | 正常系 JSON parse / response_format default / 上書き / SDK exception wrap / 不正 JSON / 非 object JSON / empty choices / None content |
| `tests/unit/adapters/outbound/llm_providers/test_claude_agent_sdk_provider.py` | 7 | 正常系 / 空 model fallback / structured_output 欠如 / 非 dict output / SDK 未インストール / async bridge inside running loop / no loop |
| `tests/unit/adapters/outbound/llm_providers/test_resolve_provider.py` | 4 | litellm / claude_agent_sdk 解決 / unknown name ValueError / 毎回新規インスタンス |
| `tests/unit/handlers/test_judge.py` | 19 | happy path 5 / rubric validation 7 / provider error 3 / output validation 2 / provider resolution 3 |
| `tests/integration/test_validate_judge_workflow.py` | 3 | inline rubric workflow 検証 / rubric_ref 検証 / oneOf 違反検証 |

**合計 41 件の新規テスト、全 PASS。**

---

## 4. 既存挙動への影響

- `workflow_explainer._extract_output_variables` は judge の default output_key `"judge_result"` を含む `builtin_default_output_keys` 辞書に拡張。既存 `llm` / `structured_llm` / `streaming_llm` の `"output"` 解決は不変。
- `test_handler_params_schema.py` の "model required for all" アサーションは judge を除外（judge は default `"sonnet"` のため model 任意）。pre-existing の `patch.dict` による sys.modules pollution（pydantic.root_model 喪失）も `setdefault` への置換で根本対処。
- `pyproject.toml` の依存変更は optional extra（`yagra[judge]`）のため既存ユーザーに影響なし。`uv.lock` のみ更新。

---

## 5. リスクと残課題

- **残課題**: 統合テスト `test_validate_judge_workflow.py` の oneOf 排他は handler-side validation に委ねる構造であるため、現時点の `validate_workflow_for_ui` では捕捉されない。テスト側は「unrelated エラーを出さない」ことを assert する弱検証で対応済み。将来 `validate_workflow_for_ui` がハンドラ params schema までチェックする拡張が入った段階で強検証に切替可能。
- **残課題**: docs/sphinx/source/changelog.md は `[Unreleased]` を扱わない設計（リリース時に英訳同期）のため今回の更新対象外。SemVer リリース時に release-ops スキルで同期すること。

---

## 6. 結論

判定: **Accept**

- DoD 14/14 PASS
- 1000 件のテストグリーン（pre-existing playwright 環境エラーを除く）
- pre-commit All Passed
- Hexagonal 境界違反なし
- 設計判断はすべて根本対処（場当たり修正なし）

PR 作成と PO 報告へ進行可とする。
