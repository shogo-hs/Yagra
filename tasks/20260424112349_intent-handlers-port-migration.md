# Intent: #28 既存 LLM handlers の LLMProviderPort 経由移行

**タスク ID**: backlog #28
**作成日**: 2026-04-24
**Feature Branch**: `feature/handlers-port-migration`
**Contract 正本**: `tasks/20260424201756_contract-po-pm-handlers-port-migration.md`
**サイズ**: L（3-5 時間、8 phase workflow A-H、推定 ~305 分）

---

## タスクの核

#28 既存 LLM handlers の litellm 直接依存を解消し、Port/Adapter 層を通す。

対象 3 handlers:
- `create_llm_handler` (`src/yagra/handlers/llm_handler.py`)
- `create_structured_llm_handler` (`src/yagra/handlers/structured_llm_handler.py`)
- `create_streaming_llm_handler` (`src/yagra/handlers/streaming_llm_handler.py`)

現状: 全 handler が `import litellm` + `litellm.completion(...)` を直呼び
目標: `resolve_provider(...)` 経由 + `LLMProviderPort` Protocol 経由呼出

---

## 成功基準（Contract 転記）

### SC-1: Port 拡張と adapter 実装
- `LLMProviderPort` Protocol に 2 メソッド追加:
  - `complete(system_prompt, user_prompt, model, timeout=30, **kwargs) -> LLMCompletion`
  - `complete_streaming(system_prompt, user_prompt, model, timeout=30, **kwargs) -> Iterator[LLMStreamChunk]`
- `complete_structured` は現状維持
- `LiteLLMProvider` が全 3 メソッドを実装
- `ClaudeAgentSDKProvider` は `complete`/`complete_streaming` で `LLMProviderConfigError` を返す

### SC-2: handler 層の Port 経由化
- 3 handler すべてで `import litellm` 削除、`litellm.` 関数呼出ゼロ
- `resolve_provider(...)` 経由で provider 取得

### SC-3: backward compat（YAML 変更不要）
- 既存 3 examples (`llm-basic`, `llm-structured`, `llm-streaming`) 無改修で動作
- `params["provider"]` 未指定時 default `"litellm"`
- streaming 公開戻り値型は `Generator[str, None, None]` 維持

### SC-4: DI（hybrid signature）
- `provider: LLMProviderPort | None = None` を 3 handler factory で受付
- DI > `params["provider"]` 優先

### SC-5: 既存テスト全通過 + 新規テスト追加
- 既存 975 件すべて継続 PASS
- 各 handler に DI 経路・params 経路の単体テスト最低 1 件ずつ追加（6 件以上）
- `LiteLLMProvider.complete`/`complete_streaming` 単体テスト追加
- `ClaudeAgentSDKProvider` が `complete`/`complete_streaming` で `LLMProviderConfigError` を投げる assert

### SC-6: Hexagonal 境界の機械的検証
- `grep -r "import litellm" src/yagra/handlers/` = 空
- `grep -r "litellm\." src/yagra/handlers/` = 空
- `src/` 配下で `import litellm` ヒットは `src/yagra/adapters/outbound/llm_providers/litellm_provider.py` のみ
- `src/yagra/ports/outbound/llm_provider.py` に `litellm`/`claude_agent_sdk` import なし

### SC-7: ドキュメント同期
- `docs/agent-integration-guide.md` LLM handler セクションに provider 説明追加
- `CHANGELOG.md` `[Unreleased]` に Changed/Added エントリ

### SC-8: pre-commit 全通過
- `uv run pre-commit run --all-files` All Passed
- `uv run pytest -q` 全 pass

### SC-9: schema 一貫性
- 3 handler `*_PARAMS_SCHEMA` に `provider` フィールド追加（optional、default `"litellm"`、enum `["litellm", "claude_agent_sdk"]`）
- `yagra handlers --format json` 出力で 3 handler すべてに provider 表示
- `JUDGE_HANDLER_PARAMS_SCHEMA` と同等構造

### SC-10: Port 層 dataclass 追加
- `ports/outbound/llm_provider.py` に:
  - `@dataclass(frozen=True, slots=True) LLMTokenUsage(prompt_tokens: int, completion_tokens: int, total_tokens: int)`
  - `@dataclass(frozen=True, slots=True) LLMCompletion(content: str, usage: LLMTokenUsage | None = None, raw: dict[str, Any] | None = None)`
  - `@dataclass(frozen=True, slots=True) LLMStreamChunk(delta: str, done: bool = False, usage: LLMTokenUsage | None = None)`
- pure Python（SDK import 禁止）
- tests/unit/ports/ または tests/unit/adapters/llm_providers/ に smoke test 追加

### SC-11: handlers/errors.py 新設
- `src/yagra/handlers/errors.py` 新設、`LLMHandlerError`/`LLMHandlerConfigError`/`LLMHandlerCallError` 移植
- 既存 `llm_handler.py`/`structured_llm_handler.py`/`streaming_llm_handler.py`/`_llm_common.py` が `yagra.handlers.errors` から import
- 互換性: `llm_handler.py` は `from yagra.handlers.errors import ...` + `__all__` 再 export で既存 import path 温存
- 循環 import 消失（`python -c "import yagra.handlers"` 成功）

### SC-12: token usage reporting の Port 経由化
- `_llm_common.py` の `report_token_usage`/`report_streaming_token_usage` を `LLMTokenUsage` dataclass 受取形に書換え
- 新関数名（例: `report_completion_usage`）として追加、litellm 直呼びバージョン削除
- streaming report は `LLMStreamChunk.usage` から反映（best-effort）

### SC-13: テスト mock 対象の書き換え
- 既存 `patch("yagra.handlers.{llm_handler,structured_llm_handler,streaming_llm_handler}.litellm")` mock を更新
- 新方針: `LLMProviderPort` の fake 実装を DI 注入、または `patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm")` にシフト

### SC-14: mypy strict 維持
- mypy で Port/adapter/handler すべて型エラーゼロ
- dataclass 引数型、`Iterator[LLMStreamChunk]`、`LLMCompletion` 戻り値の型一貫性

### SC-15: streaming 仕様の公開 API 不変 + 内部 contract 一貫性
- `create_streaming_llm_handler` state value 型は `Generator[str, None, None]` 維持
- 内部 `_yield_stream_text(chunks) -> Generator[str, None, None]` を `_llm_common.py` に追加
- `done=True` または `usage is not None` chunk で最終 token usage report、`delta` 空 terminal chunk は yield しない

### SC-16: params.provider のバリデーションとエラーメッセージ
- `params["provider"]` が `resolve_provider` で解決できない場合 `LLMHandlerConfigError` を hint 付きで送出
- hint 文言 judge と統一: `"Unknown provider '<name>'. Available: litellm, claude_agent_sdk. Install 'yagra[judge]' for claude_agent_sdk."`

---

## In スコープ

- SC-1〜SC-16 すべて
- Port 2 メソッド追加 + 3 dataclass 追加
- `LiteLLMProvider` の `complete`/`complete_streaming` 実装
- `ClaudeAgentSDKProvider` は subset
- 3 handler の Port 経由書換え
- `handlers/errors.py` 新設
- schema + ドキュメント + CHANGELOG 更新

## Out スコープ

- `ClaudeAgentSDKProvider` の `complete`/`complete_streaming` 実装（将来別タスク）
- `fake provider` 実装（#5 で必要なら別タスク）
- token usage reporting adapter 層完全移設
- handler の `adapters/outbound/handlers/` 再配置（#14 別タスク）
- `_llm_common.py` の API 破壊的変更
- MCP/CLI 側変更
- `complete_structured` 戻り型 dataclass 化

---

## 予定工数（8 phase）

| Phase | 内容 | 推定時間 |
|-------|------|---------|
| A | Port 拡張（dataclass + Protocol + smoke test） | 25 分 |
| B | `handlers/errors.py` 新設 + 循環 import 解消 smoke | 25 分 |
| C | `LiteLLMProvider.complete`/`complete_streaming` + 単体テスト | 50 分 |
| D | `ClaudeAgentSDKProvider` subset 対応 + テスト | 15 分 |
| E | 3 handler を Port 経由書換え（`import litellm` 削除） | 60 分 |
| F | 既存テスト mock 書換え + 新規 handler テスト 6 件以上 | 70 分 |
| G | `*_PARAMS_SCHEMA` + docs + CHANGELOG 更新 | 35 分 |
| H | 全検証（pre-commit / pytest / grep 境界） + PR 作成 | 25 分 |

合計: ~305 分（約 5 時間）

---

## 重点リスク

### R1: 循環 import（SC-11 で解消）
`_llm_common.py` → `llm_handler.py` の現行依存方向。`handlers/errors.py` 新設で断つ。

### R2: streaming semantics（SC-15 で担保）
`Generator[str, None, None]` 公開 API 維持。`_yield_stream_text` で unwrap。

### R3: token usage reporting（SC-12 で担保）
`LLMTokenUsage` dataclass で固定。streaming は best-effort。

### R4: structured_llm dynamic schema_yaml + 2 重 format 指定（R4）
`LiteLLMProvider.complete_structured` にそのまま維持（#23 壊さず）。

### R5: 既存テスト mock 書換え規模（Step 0 調査必須）
Contract 予測 83 件前後。Step 2 で正確件数を grep し Intent 追記予定。

### R6: Claude Agent SDK subset の互換性
judge handler は `complete_structured` のみ使用。subset エラーは SC-16 と文言統一。

### R7: mypy strict 通過 + dataclass 引数順
`LLMStreamChunk(delta, done=False, usage=None)` の順で default 末尾保持。
