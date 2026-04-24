# Intent: #23 `create_judge_handler` 実装

**タスク ID**: Backlog #23
**作成日**: 2026-04-24
**作成者**: PM Agent
**参照 Contract**: `tasks/20260424143714_contract-po-pm-create-judge-handler.md`

---

## 背景

Yagra の差別化軸「AI が AI を評価・改善」の根幹実装。Phase 3「LLM-as-a-Judge Handlers」の最初のタスク。
現状、judge に該当する実装は 0 件。本タスクでビジョン体現度 2/5 → 3/5 へ動かす。

## ゴール

YAML で宣言した rubric に基づき、LLM が構造化スコア＋根拠を返す `create_judge_handler` を実装し、
Port/Adapter 境界を導入して provider を差し替え可能にする。

## 成功基準（Contract SC-1〜SC-14 転記）

- [ ] **SC-1**: `src/yagra/ports/outbound/llm_provider.py` に `LLMProviderPort`（Protocol + `runtime_checkable`）
- [ ] **SC-2a**: `src/yagra/adapters/outbound/llm_providers/litellm_provider.py` に `LiteLLMProvider`（`litellm.completion` + `response_format={"type":"json_object"}` + schema 注入）
- [ ] **SC-2b**: `src/yagra/adapters/outbound/llm_providers/claude_agent_sdk_provider.py` に `ClaudeAgentSDKProvider`（`claude_agent_sdk.query` + `output_format={"type":"json_schema","schema":...}` + デフォルト `"sonnet"`）
- [ ] **SC-2c**: `src/yagra/adapters/outbound/llm_providers/__init__.py` に `resolve_provider(name: str) -> LLMProviderPort` Factory
- [ ] **SC-3**: `src/yagra/handlers/judge.py` に `create_judge_handler(provider=None, ...)`（hybrid pattern: 引数 or params 解決、両未指定時 `claude_agent_sdk` フォールバック、async bridge safety）
- [ ] **SC-4**: `handlers/__init__.py` + `handlers/catalog.py` に `judge` 登録、`yagra handlers` / `list_handlers` MCP 出力に現れる
- [ ] **SC-5**: `JUDGE_HANDLER_PARAMS_SCHEMA`（`provider: enum`, `rubric`/`rubric_ref`: oneOf, `prompt`/`prompt_ref`: oneOf, `output_key: default "judge_result"`）
- [ ] **SC-6**: `pyproject.toml` `[project.optional-dependencies]` に `judge = ["claude-agent-sdk"]`。未インストール時 `ImportError` を構造化 4 フィールド形式で raise（hint 含む）
- [ ] **SC-7**: 各種ユニットテスト
  - `tests/unit/handlers/test_judge.py` ≥4 ケース
  - `tests/unit/adapters/outbound/llm_providers/test_litellm_provider.py` ≥2 ケース
  - `tests/unit/adapters/outbound/llm_providers/test_claude_agent_sdk_provider.py` ≥2 ケース
  - `tests/unit/adapters/outbound/llm_providers/test_resolve_provider.py` ≥2 ケース
- [ ] **SC-8**: 全テスト PASSED（既存 952 + 新規）
- [ ] **SC-9**: `uv run pre-commit run --all-files` All Passed
- [ ] **SC-10**: Hexagonal 境界違反 0
- [ ] **SC-11**: `docs/agent-integration-guide.md` に `judge` handler の使い方を追記
- [ ] **SC-12**: `CHANGELOG.md` [Unreleased] Added に記載
- [ ] **SC-13**: rubric 不正値（`scale.min >= scale.max` / 空 criteria / name 欠如 等）を構造化 4 フィールド形式で検出
- [ ] **SC-14**: `yagra validate` 統合テスト（judge handler node を含む workflow が正常に検証される）

## In Scope

- `LLMProviderPort` Protocol 新設
- `LiteLLMProvider` / `ClaudeAgentSDKProvider` + `resolve_provider()` Factory
- `create_judge_handler` 実装
- rubric YAML パーサ（最小版: criteria list + scale + require_reasoning）
- ユニットテスト 4 ファイル + 統合テスト 1 件
- docs / CHANGELOG / dependency 更新

## Out of Scope

- 既存 `create_llm_handler` 等の Port 経由への移行（別タスク）
- `examples/self-improve/` → #24
- `evaluate_traces` MCP → #25
- E2E 統合 → #26
- LLM-as-a-Judge ドキュメント（best practices）→ #27
- rubric テンプレートライブラリ拡充 → #27
- Studio UI 対応（別タスク）

## Feature Branch

`feature/add-create-judge-handler`

## 想定影響ファイル

**新規 (8)**:
- `src/yagra/ports/outbound/llm_provider.py`
- `src/yagra/adapters/outbound/llm_providers/__init__.py`
- `src/yagra/adapters/outbound/llm_providers/litellm_provider.py`
- `src/yagra/adapters/outbound/llm_providers/claude_agent_sdk_provider.py`
- `src/yagra/handlers/judge.py`
- `tests/unit/handlers/test_judge.py`
- `tests/unit/adapters/outbound/llm_providers/__init__.py`
- `tests/unit/adapters/outbound/llm_providers/test_litellm_provider.py`
- `tests/unit/adapters/outbound/llm_providers/test_claude_agent_sdk_provider.py`
- `tests/unit/adapters/outbound/llm_providers/test_resolve_provider.py`
- `tests/integration/test_validate_judge_workflow.py`（SC-14 想定）

**更新 (5)**:
- `src/yagra/handlers/__init__.py`（judge エクスポート）
- `src/yagra/handlers/catalog.py`（BUILTIN_HANDLERS_INFO に judge 追加）
- `pyproject.toml`（`yagra[judge]` extra）
- `docs/agent-integration-guide.md`（judge 使い方追記）
- `CHANGELOG.md`（[Unreleased] Added）

## リスク（Contract 継承 + PM 追加確認）

| リスク | 対応方針 |
|-------|---------|
| `claude_agent_sdk` がテスト環境にない | テストは `sys.modules` or `importlib` モックで処理。実インストールは任意 |
| async-only API の sync bridge | `asyncio.get_running_loop()` 検出 → ThreadPoolExecutor で分離 |
| PM 環境制約（Task/Agent 不在） | Contract で公式承認済み、PM が Developer/PMO を sequentially 代行 |
| catalog.py への追加で既存テスト崩れ | `test_handler_params_schema.py` 等の既存テストが壊れないか確認 |

## 検証の観点（PM 自己チェック）

- Hexagonal: `ports/llm_provider.py` 内で `litellm` / `claude_agent_sdk` を import していない
- `domain/` に新規ファイルが import されていない
- 構造化エラー 4 フィールド `{error, message, summary, hint}` 形式遵守
- #4 の learnings（CHANGELOG [Unreleased] 標準化、構造化エラー、silent success 防止）を踏襲

## 開始予定手順

1. Step 2 調査（PM 直接実施。`_llm_common.py` / `structured_llm_handler.py` / `catalog.py` / `pyproject.toml` の詳細確認）
2. Step 3 計画作成
3. Step 4 Mission Brief
4. Step 5 feature branch 作成 + PM 代行で sequential 実装
5. Step 6 PR 作成 + PMO セルフレビュー
6. Step 7 reject 時 revise（最大 2 回）
7. Step 8 PO 向け結果レポート
