# Plan: #28 既存 LLM handlers の LLMProviderPort 経由移行

**タスク ID**: backlog #28
**Feature Branch**: `feature/handlers-port-migration`
**Contract 正本**: `tasks/20260424201756_contract-po-pm-handlers-port-migration.md`
**Intent**: `tasks/20260424112349_intent-handlers-port-migration.md`

---

## 現状把握（Step 2 調査結果）

- 既存 `LLMProviderPort`: `complete_structured` のみ定義、Protocol + `runtime_checkable`
- `LiteLLMProvider`: `complete_structured` のみ実装（JSON 用、`response_format` + schema 埋込）
- `ClaudeAgentSDKProvider`: `complete_structured` のみ実装（`ClaudeAgentOptions(output_format={...})`）
- `resolve_provider("litellm")` / `resolve_provider("claude_agent_sdk")` が factory、unknown は `ValueError`
- 3 handler（`llm_handler.py` / `structured_llm_handler.py` / `streaming_llm_handler.py`）はいずれも `import litellm` + `litellm.completion(...)` 直呼び
- `_llm_common.py` から `from yagra.handlers.llm_handler import LLMHandlerCallError, LLMHandlerConfigError` で error class を取得 = **循環 import の source**
- litellm を patch しているテスト: 計 87 occurrences 5 ファイル

---

## 実装フェーズ（Contract 転記 + 変更ファイル詳細）

### Phase A: Port 拡張（dataclass + Protocol 追加）[25 分]

**変更ファイル**:
- `src/yagra/ports/outbound/llm_provider.py`（更新）
  - `LLMTokenUsage` / `LLMCompletion` / `LLMStreamChunk` dataclass 追加（pure Python）
  - `LLMProviderPort` に `complete` / `complete_streaming` Protocol メソッド追加
  - `complete_structured` はそのまま（既存挙動維持）
- `tests/unit/ports/test_llm_provider_dataclasses.py`（新規）
  - 3 dataclass の smoke test（構築、等価性、frozen 確認）

**SC**: SC-1 / SC-10 / SC-14

---

### Phase B: handlers/errors.py 新設（循環 import 解消）[25 分]

**変更ファイル**:
- `src/yagra/handlers/errors.py`（新規）
  - `LLMHandlerError` / `LLMHandlerConfigError` / `LLMHandlerCallError` を移植
- `src/yagra/handlers/llm_handler.py`（更新）
  - error class 定義を削除し `from yagra.handlers.errors import ...` + `__all__` で再 export
- `src/yagra/handlers/_llm_common.py`（更新）
  - `from yagra.handlers.errors import ...` に書換え
- `src/yagra/handlers/structured_llm_handler.py`（更新）
  - `from yagra.handlers.errors import ...` に書換え
- `src/yagra/handlers/streaming_llm_handler.py`（本 phase ではまだ litellm 削除しない。必要な error import のみ追加）

**Smoke 検証**:
- `python -c "import yagra.handlers"` が一発成功
- 既存テストの `from yagra.handlers.llm_handler import LLMHandlerCallError` が通る

**SC**: SC-11

---

### Phase C: LiteLLMProvider の complete / complete_streaming 実装 [50 分]

**変更ファイル**:
- `src/yagra/adapters/outbound/llm_providers/litellm_provider.py`（更新）
  - `complete(system_prompt, user_prompt, model, timeout=30, **kwargs) -> LLMCompletion` 実装
    - litellm.completion 呼出 → `LLMCompletion(content, usage=LLMTokenUsage(...), raw=response)`
    - 空 choices / None content / 例外は `LLMProviderCallError`
  - `complete_streaming(system_prompt, user_prompt, model, timeout=30, **kwargs) -> Iterator[LLMStreamChunk]` 実装
    - litellm.completion(stream=True) → chunk 毎に `LLMStreamChunk(delta, done, usage)` yield
    - 最終 chunk では `done=True` + usage 付与（response.usage が取得できれば）
- `tests/unit/adapters/llm_providers/test_litellm_provider.py`（更新 / 新規テスト追加）
  - `complete` の単体テスト: chunk なしの response → `LLMCompletion` 検証
  - `complete` の空 choices / None content / 例外伝搬テスト
  - `complete_streaming` の chunk 分解 / token usage / terminal chunk 検証

**SC**: SC-1 / SC-5 / SC-14

---

### Phase D: ClaudeAgentSDKProvider subset 対応 [15 分]

**変更ファイル**:
- `src/yagra/adapters/outbound/llm_providers/claude_agent_sdk_provider.py`（更新）
  - `complete(...)`: `LLMProviderConfigError` を 4-field payload で raise
  - `complete_streaming(...)`: `LLMProviderConfigError` を 4-field payload で raise
  - payload は "subset 未対応" メッセージ、hint は "Use LiteLLMProvider for completion/streaming"
- `tests/unit/adapters/llm_providers/test_claude_agent_sdk_provider.py`（更新）
  - `complete` / `complete_streaming` が `LLMProviderConfigError` 4-field payload で raise されること

**SC**: SC-1 / SC-16

---

### Phase E: 3 handler を Port 経由に書換え + hybrid signature [60 分]

**変更ファイル**:
- `src/yagra/handlers/_llm_common.py`（更新）
  - `report_token_usage` / `report_streaming_token_usage` を `LLMTokenUsage` 受取形式に書換え（既存関数名は削除 → 新関数 `report_completion_usage(usage: LLMTokenUsage | None, litellm_model, provider)` / `report_streaming_usage(usage: LLMTokenUsage | None, ...)` に置換）
  - `_yield_stream_text(chunks: Iterator[LLMStreamChunk]) -> Generator[str, None, None]` 追加
  - `resolve_handler_provider(provider_arg, params_provider) -> LLMProviderPort` 追加（judge の `_resolve_provider_instance` と同形、ただし default `"litellm"` + `LLMHandlerConfigError` を raise）

- `src/yagra/handlers/llm_handler.py`（更新）
  - `import litellm` 削除
  - `create_llm_handler(provider: LLMProviderPort | None = None, retry=3, timeout=30)` hybrid signature
  - `resolved_provider.complete(...)` で呼出
  - `LLMCompletion.content` を `output_key` に格納
  - `report_completion_usage(completion.usage, ...)` で trace
- `src/yagra/handlers/structured_llm_handler.py`（更新）
  - `import litellm` 削除
  - `create_structured_llm_handler(schema=None, provider=None, retry=3, timeout=30)` hybrid signature
  - `resolved_provider.complete_structured(schema=model_json_schema_dict, ...)` で呼出
  - 戻り値 dict を Pydantic validate
- `src/yagra/handlers/streaming_llm_handler.py`（更新）
  - `import litellm` 削除
  - `create_streaming_llm_handler(provider=None, retry=3, timeout=60)` hybrid signature
  - `chunks = resolved_provider.complete_streaming(...)` → `_yield_stream_text(chunks)` で `Generator[str, None, None]`
  - terminal chunk の usage を `report_streaming_usage` で trace

**SC**: SC-2 / SC-3 / SC-4 / SC-12 / SC-15 / SC-16

---

### Phase F: テスト mock 書換え + 新規 handler テスト [70 分]

**変更ファイル（テスト書換え）**:
- `tests/unit/handlers/test_llm_handler.py`
  - `patch("yagra.handlers.llm_handler.litellm")` → Fake `LLMProviderPort` DI 注入、または `patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm")`
  - 29 occurrences 書換え
- `tests/unit/handlers/test_structured_llm_handler.py`
  - 同様の書換え 27 occurrences
- `tests/unit/handlers/test_streaming_llm_handler.py`
  - 同様の書換え 25 occurrences
- `tests/integration/test_llm_handler_integration.py`
  - 3 occurrences 書換え
- `tests/integration/test_streaming_llm_handler_integration.py`
  - 3 occurrences 書換え

**変更ファイル（新規テスト）**:
- `tests/unit/handlers/test_llm_handler.py`（既存に追加）
  - DI 経路（`provider=FakeProvider()`）テスト 1 件
  - `params["provider"]` 経路テスト 1 件
  - `params["provider"]` unknown 時 `LLMHandlerConfigError` 4-field payload テスト 1 件
- `tests/unit/handlers/test_structured_llm_handler.py`
  - DI 経路 1 件 / params 経路 1 件
- `tests/unit/handlers/test_streaming_llm_handler.py`
  - DI 経路 1 件 / params 経路 1 件

合計新規テスト: **最低 9 件（6 件要件 + α）**

**SC**: SC-5 / SC-13

---

### Phase G: schema 一貫性 + docs + CHANGELOG [35 分]

**変更ファイル**:
- `src/yagra/handlers/llm_handler.py`
  - `LLM_HANDLER_PARAMS_SCHEMA` に `provider` フィールド追加（optional、default `"litellm"`、enum `["litellm", "claude_agent_sdk"]`）
- `src/yagra/handlers/structured_llm_handler.py`
  - `STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA` に provider 追加
- `src/yagra/handlers/streaming_llm_handler.py`
  - `STREAMING_LLM_HANDLER_PARAMS_SCHEMA` に provider 追加
- `src/yagra/handlers/_llm_common.py`
  - `BASE_PARAMS_SCHEMA_PROPERTIES` に provider を追加する、または各 schema 直接更新
- `docs/agent-integration-guide.md`
  - LLM handler セクションに `params.provider` 説明追加 + 2 レベル provider 注記
- `CHANGELOG.md`
  - `[Unreleased]` に Changed / Added エントリ追加（Keep a Changelog 形式）

**SC**: SC-7 / SC-9

---

### Phase H: 全検証 + PR 作成 [25 分]

**検証コマンド**:
```bash
# Hexagonal 境界 (SC-6)
grep -r "import litellm" src/yagra/handlers/ | grep -v test  # 空のはず
grep -r "litellm\." src/yagra/handlers/ | grep -v test       # 空のはず
grep -r "import litellm" src/ | grep -v test                  # litellm_provider.py のみ
grep -r "litellm\|claude_agent_sdk" src/yagra/ports/          # 空のはず（dataclass は pure Python）

# 循環 import (SC-11)
python -c "import yagra.handlers"   # 成功

# pre-commit (SC-8)
uv run pre-commit run --all-files

# 全テスト (SC-5 / SC-8)
uv run pytest -q

# schema (SC-9)
uv run yagra handlers --format json | python -c "import sys, json; d=json.load(sys.stdin); [print(h['name'], 'provider' in h['params']['properties']) for h in d]"
```

**PR 作成**:
- タイトル: `feat(handlers): LLMProviderPort 経由移行 + Port 層 dataclass 追加`
- body: Contract SC 対応表、変更ファイル一覧、テスト件数推移、pre-commit ALL Passed 宣言

**SC**: SC-5 / SC-6 / SC-8 / SC-11 / SC-14

---

## 変更ファイル総一覧

### 新規（3）
- `src/yagra/handlers/errors.py`
- `tests/unit/ports/test_llm_provider_dataclasses.py`
- （必要に応じて `tests/unit/ports/__init__.py`）

### 更新（12）
- `src/yagra/ports/outbound/llm_provider.py`
- `src/yagra/adapters/outbound/llm_providers/litellm_provider.py`
- `src/yagra/adapters/outbound/llm_providers/claude_agent_sdk_provider.py`
- `src/yagra/handlers/llm_handler.py`
- `src/yagra/handlers/structured_llm_handler.py`
- `src/yagra/handlers/streaming_llm_handler.py`
- `src/yagra/handlers/_llm_common.py`
- `tests/unit/adapters/llm_providers/test_litellm_provider.py`
- `tests/unit/adapters/llm_providers/test_claude_agent_sdk_provider.py`
- `tests/unit/handlers/test_llm_handler.py`
- `tests/unit/handlers/test_structured_llm_handler.py`
- `tests/unit/handlers/test_streaming_llm_handler.py`
- `tests/integration/test_llm_handler_integration.py`
- `tests/integration/test_streaming_llm_handler_integration.py`
- `docs/agent-integration-guide.md`
- `CHANGELOG.md`

## 総計
- 新規テスト: 最低 9 件（DI/params/unknown x 3 handler）+ port dataclass 3 件 + LiteLLMProvider complete/complete_streaming 6 件 + CASDKProvider subset 2 件 = **20 件以上**
- 既存テスト: 996 件継続 PASS（pre-existing 3 flaky + 33 playwright error を除く）

## Developer 数

PM 環境制約により 1 Developer + PMO を PM が sequentially 代行（5 回目）。

## チェックリスト（Mission Brief に転送）

- [ ] SC-1〜SC-16 すべて PASS
- [ ] `import litellm` が `handlers/` ディレクトリから消えた
- [ ] `ports/outbound/llm_provider.py` に litellm/claude_agent_sdk import なし
- [ ] `python -c "import yagra.handlers"` 成功
- [ ] `uv run pre-commit run --all-files` ALL Passed
- [ ] `uv run pytest -q` 全 PASS（pre-existing flaky 3 件と playwright 33 error は無視）
- [ ] schema に provider フィールド追加
- [ ] docs + CHANGELOG 更新
- [ ] PR body に Contract SC 対応表記載
