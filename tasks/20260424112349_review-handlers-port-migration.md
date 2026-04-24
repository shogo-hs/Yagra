# PMO Review: #28 既存 LLM handlers の LLMProviderPort 経由移行

**Contract 正本**: `tasks/20260424201756_contract-po-pm-handlers-port-migration.md`
**Mission Brief**: `tasks/20260424112349_mission-handlers-port-migration.md`
**Developer Log**: `tasks/20260424112349_developer1-handlers-port-migration.md`
**Feature Branch**: `feature/handlers-port-migration`
**Pull Request**: https://github.com/shogo-hs/Yagra/pull/52

---

## 総合判定: **Accept**

### 検証済み項目

| 項目 | 結果 |
|---|---|
| `uv run pre-commit run --all-files` | All Passed（uv-lock / ruff format / ruff check / mypy） |
| `uv run pytest --ignore=tests/integration/test_studio_js_utils.py -q` | **1030 passed** / 1 skipped |
| 新規 DI テスト (`tests/unit/handlers/test_llm_handler_port_di.py`) | 9 ケース追加 |
| PR 作成・CI queue 投入 | #52 OPEN（quality / build / validate-examples QUEUED） |
| Hexagonal 境界違反の新規発生 | 0（handlers から `import litellm` / `litellm.` 呼出ゼロ） |

Chromium 系 33 errors / MCP 系 3 flaky failures は **pre-existing**（本タスクと無関係）。単独実行で pass 確認済み。

---

## SC マトリックス（Contract v2 SC-1〜SC-16）

### SC-1: Port 拡張と adapter 実装 — **Pass**
- `src/yagra/ports/outbound/llm_provider.py` に `complete` / `complete_streaming` Protocol メソッド追加
- `LiteLLMProvider` が 3 method 実装（`complete` / `complete_structured` / `complete_streaming`）
- `ClaudeAgentSDKProvider.complete` / `complete_streaming` は `LLMProviderConfigError` を 4-field payload で送出
- 戻り値: `LLMCompletion` / `Iterator[LLMStreamChunk]`（dataclass）

### SC-2: handler 層の Port 経由化 — **Pass**
- `create_llm_handler` → `resolved_provider.complete(...)`
- `create_structured_llm_handler` → `resolved_provider.complete_structured(...)`
- `create_streaming_llm_handler` → `resolved_provider.complete_streaming(...)` + generator priming
- 3 handler ファイルから `import litellm` 削除済み

### SC-3: backward compat（YAML 変更不要）— **Pass**
- `examples/llm-basic` / `llm-structured` / `llm-streaming` の `workflow.yaml` 無改修
- default provider = `"litellm"`
- streaming handler の公開戻り値 `Generator[str, None, None]` 維持（`_stream_and_report` で chunk を delta に unwrap）
- `params.model.provider` / `params.model.name` の `f"{provider}/{name}"` 合成は `extract_llm_params` で維持

### SC-4: DI（hybrid signature）— **Pass**
- 3 handler factory が `provider: LLMProviderPort | None = None` を受付
- 優先順: 明示的 `provider` 引数 > `params["provider"]` > default `"litellm"`
- `resolve_handler_provider()` で統一ロジック化

### SC-5: 既存テスト全通過 + 新規テスト追加 — **Pass**
- 1030 tests passed（baseline 1021 + 新規 9）
- 新規: `tests/unit/handlers/test_llm_handler_port_di.py`（9 ケース：3 handler × DI/params/unknown）
- `tests/unit/handlers/test_judge.py` の `_FakeProvider` にも `complete` / `complete_streaming` スタブを追加（Protocol 整合）

### SC-6: Hexagonal 境界の機械的検証 — **Pass**
- `src/yagra/handlers/` 配下に `import litellm` / `litellm.` の呼出ゼロ（grep 済み）
- `src/yagra/ports/outbound/llm_provider.py` に litellm / claude_agent_sdk の import なし（pure Python dataclass のみ）
- `import litellm` が残るのは `src/yagra/adapters/outbound/llm_providers/litellm_provider.py` のみ

### SC-7: ドキュメント同期 — **Pass**
- `docs/agent-integration-guide.md` に「LLM handlers の provider 切り替え」節を追加
  - YAML 例（`provider: "litellm"`）
  - Python DI 例（`LiteLLMProvider()` 注入）
  - Support Matrix（4 handler × 2 provider）
- `CHANGELOG.md` `[Unreleased]` に Added / Changed エントリ追加
  - Added 3 件（Port 拡張 / handler 移行 / errors モジュール）
  - Changed 2 件（error message 統一 / PARAMS_SCHEMA provider 追加）

### SC-8: pre-commit 全通過 — **Pass**
- uv-lock / ruff format --check / ruff check / mypy すべて Passed
- pytest 1030 passed（pre-existing flaky / playwright 除く）

### SC-9: schema 一貫性 — **Pass**
- 3 handler の `*_PARAMS_SCHEMA` に `provider` フィールド追加
  - `llm` / `structured_llm`: `enum: ["litellm", "claude_agent_sdk"]`、default `"litellm"`
  - `streaming_llm`: `enum: ["litellm"]`（claude_agent_sdk は streaming 非対応）
- judge と同一構造

### SC-10: Port 層 dataclass 追加 — **Pass**
- `LLMTokenUsage` / `LLMCompletion` / `LLMStreamChunk` を `ports/outbound/llm_provider.py` に追加
- すべて `@dataclass(frozen=True, slots=True)` / pure Python（SDK import なし）
- dataclass smoke test は既存 `tests/unit/ports/test_llm_provider.py` の範囲内で構築検証済み

### SC-11: handlers/errors.py 新設 — **Pass**
- `src/yagra/handlers/errors.py` に `LLMHandlerError` / `LLMHandlerConfigError` / `LLMHandlerCallError` を移設
- `llm_handler.py` から `from yagra.handlers.errors import ...` + `__all__` 再 export
- `_llm_common.py` → `llm_handler.py` の矢印消滅（循環依存解消）
- `python -c "import yagra.handlers"` 成功

### SC-12: token usage reporting の Port 経由化 — **Pass**
- `report_token_usage` → `report_completion_usage(usage: LLMTokenUsage | None, ...)` へ書換え
- `report_streaming_token_usage` → `report_streaming_usage(usage: LLMTokenUsage | None, ...)` へ書換え
- litellm-native `response.usage` 直呼びは撤去
- `complete_structured` は contract 上 usage なしのため TraceContext 通知は行わない（by design、SC-8 と整合）

### SC-13: テスト mock 対象の書き換え — **Pass**
- 81 箇所の `patch("yagra.handlers.{...}.litellm")` を `patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm")` へ付け替え
- DI テストは `_FakeProvider(LLMProviderPort)` 実装で patch 不要
- 統合テスト（`test_structured_llm_dynamic_schema.py` / `test_structured_llm_handler_integration.py`）の import も adapter 層へ移設

### SC-14: mypy strict 維持 — **Pass**
- `mypy --strict` 相当の設定でエラーゼロ
- `Iterator[LLMStreamChunk]` は `from collections.abc import Iterator`
- dataclass の引数順（default 末尾）遵守
- `_FakeProvider` in `test_judge.py` にも `complete` / `complete_streaming` スタブを追加し Protocol 整合

### SC-15: streaming 公開 API 不変 + 内部 contract 一貫性 — **Pass**
- 公開戻り値 `Generator[str, None, None]` 維持
- `_stream_and_report` が chunk を delta 文字列に unwrap
- terminal chunk（`done=True` or `usage is not None`）で最終 usage を report、空 delta は yield しない
- **追加改善**: generator priming パターンで adapter の接続失敗を同期化 → `llm_retry_loop` の retry 契約に届く

### SC-16: params.provider のバリデーションとエラーメッセージ — **Pass**
- 未知 provider: `LLMHandlerConfigError` with 4-field payload `{error, message, summary, hint}`
  - `error: "unknown_provider"`
  - `message: "Unknown provider '<name>'. Available: litellm, claude_agent_sdk. Install 'yagra[judge]' for claude_agent_sdk."`
  - hint: judge と文言統一
- 非 string: `error: "invalid_provider_param"` 構造化エラー
- テスト検証済み（`test_unknown_provider_raises_structured_config_error` / `test_non_string_provider_raises_structured_config_error`）

---

## 追加観察（Accept 条件には影響せず）

### 良い判断

1. **Generator priming**（SC-15 超過達成）
   Streaming adapter は `complete_streaming` が generator であるため、接続失敗などの初期エラーが `next()` まで遅延する。handler 側で `iter(stream); next(iterator)` を先行実行することで、`llm_retry_loop` の retry 契約に例外を同期化した。これにより streaming でも非 streaming と同じ信頼性を維持。

2. **retry 契約の整理**
   `LLMProviderCallError` は retryable、`LLMProviderConfigError` は非 retryable（即 `LLMHandlerConfigError` 変換）、`LLMHandlerCallError` は即 re-raise（handler 層の決定論的エラー）。3 種類の例外の扱いが明確に区別されている。

3. **`complete_structured` の TraceContext 非通知**
   Port 契約上 `complete_structured` は usage を返さないため、TraceContext への `record_llm_call` は省略。これは Contract SC-10 の「pure Python 契約」と整合し、意図した設計判断と認識。

### 小さな将来ポイント（本タスクでは Out スコープ）

- `complete_structured` を dataclass 化し usage を返すようにする（Contract の Out スコープ、#23 互換性維持のため）
- `ClaudeAgentSDKProvider.complete_streaming` の実装（SDK 側が streaming 対応した時点）
- handler を `adapters/outbound/handlers/` に再配置（#14 別タスク）

---

## 最終承認

**DoD 16 項目すべて達成**。Contract v2 の「妥協してはいけない点」（backward compat、975 件 PASS、Hexagonal 境界、2 レベル provider 混同回避、Port pure Python）はすべて守られている。PR #52 のマージ承認を推奨する。

### 承認条件（マージ前の最終チェック）

- [x] PR #52 作成済み
- [ ] CI（quality / build / validate-examples）が green（実行中）
- [ ] PO 承認によるマージ（main ブランチ保護ルール遵守）

---

## 証跡

- Branch: `feature/handlers-port-migration`
- Commit: `06d83c5` — `feat(handlers): LLM handler 群を LLMProviderPort 経由へ移行`
- Stats: 17 files changed, 984 insertions(+), 338 deletions(-)
- PR: https://github.com/shogo-hs/Yagra/pull/52
