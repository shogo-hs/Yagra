# Mission Brief: #28 既存 LLM handlers の LLMProviderPort 経由移行

**Contract 正本**: `tasks/20260424201756_contract-po-pm-handlers-port-migration.md`
**Intent**: `tasks/20260424112349_intent-handlers-port-migration.md`
**Plan**: `tasks/20260424112349_plan-handlers-port-migration.md`
**Feature Branch**: `feature/handlers-port-migration`

---

## Developer 向けミッション

既存 3 handler（`create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler`）から litellm 直接依存を剥がし、`LLMProviderPort` 経由に切り替える。Port 層に `LLMCompletion` / `LLMStreamChunk` / `LLMTokenUsage` dataclass を追加し、`handlers/errors.py` 新設で循環 import を解消する。

既存 workflow YAML / examples / テストの動作を壊さず、Hexagonal 純度 +1。Contract の SC-1〜SC-16 すべて達成。

---

## 推奨実装スケッチ

### Phase A: `src/yagra/ports/outbound/llm_provider.py` 拡張

```python
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class LLMTokenUsage:
    """LLM provider が返す token 消費量（pure Python / SDK 非依存）."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class LLMCompletion:
    """``LLMProviderPort.complete`` の戻り値.

    Attributes:
        content: 生成されたテキスト.
        usage: 使用 token 情報. provider が返さなければ ``None``.
        raw: provider-native レスポンス. 観測可能性のための optional.
    """

    content: str
    usage: LLMTokenUsage | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class LLMStreamChunk:
    """``LLMProviderPort.complete_streaming`` が yield する 1 chunk.

    Attributes:
        delta: 追加の文字列断片.
        done: ストリーム終端か.
        usage: terminal chunk にのみ載る usage. それ以外は ``None``.
    """

    delta: str
    done: bool = False
    usage: LLMTokenUsage | None = None


class LLMProviderError(RuntimeError):
    """Base exception ..."""

class LLMProviderConfigError(LLMProviderError):
    """設定不備 ..."""

class LLMProviderCallError(LLMProviderError):
    """Provider 呼出中の通信エラー ..."""


@runtime_checkable
class LLMProviderPort(Protocol):
    def complete_structured(
        self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any],
        model: str, timeout: int = 30, **kwargs: Any,
    ) -> dict[str, Any]: ...

    def complete(
        self, *, system_prompt: str, user_prompt: str, model: str,
        timeout: int = 30, **kwargs: Any,
    ) -> LLMCompletion: ...

    def complete_streaming(
        self, *, system_prompt: str, user_prompt: str, model: str,
        timeout: int = 30, **kwargs: Any,
    ) -> Iterator[LLMStreamChunk]: ...
```

### Phase B: `src/yagra/handlers/errors.py` 新設

```python
"""LLM handler 層の共通例外階層.

`_llm_common.py` が `llm_handler.py` の error 定義を import することで
生じていた循環依存を断つため独立させる。
"""

from __future__ import annotations


class LLMHandlerError(Exception):
    """Base exception class for LLM handler execution errors."""


class LLMHandlerConfigError(LLMHandlerError):
    """Configuration error for LLM handler."""


class LLMHandlerCallError(LLMHandlerError):
    """Error during LLM invocation."""


__all__ = [
    "LLMHandlerCallError",
    "LLMHandlerConfigError",
    "LLMHandlerError",
]
```

`llm_handler.py` 側は再 export:

```python
# llm_handler.py 冒頭
from yagra.handlers.errors import (
    LLMHandlerCallError,
    LLMHandlerConfigError,
    LLMHandlerError,
)

__all__ = [
    "LLMHandlerError",
    "LLMHandlerConfigError",
    "LLMHandlerCallError",
    "LLM_HANDLER_PARAMS_SCHEMA",
    "create_llm_handler",
]
```

### Phase C: `LiteLLMProvider.complete` / `complete_streaming`

```python
def complete(
    self, *, system_prompt: str, user_prompt: str, model: str,
    timeout: int = 30, **kwargs: Any,
) -> LLMCompletion:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = litellm.completion(
            model=model, messages=messages, timeout=timeout, **kwargs,
        )
    except Exception as exc:
        raise LLMProviderCallError(f"litellm.completion failed: {exc}") from exc

    if not response.choices:
        raise LLMProviderCallError("litellm returned empty choices")
    content = response.choices[0].message.content
    if content is None:
        raise LLMProviderCallError("litellm returned None content")

    usage = _extract_usage(response)
    raw = getattr(response, "model_dump", lambda: None)() if hasattr(response, "model_dump") else None
    return LLMCompletion(content=content, usage=usage, raw=raw)


def complete_streaming(
    self, *, system_prompt: str, user_prompt: str, model: str,
    timeout: int = 30, **kwargs: Any,
) -> Iterator[LLMStreamChunk]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    call_kwargs = dict(kwargs)
    call_kwargs["stream"] = True  # force streaming regardless of caller
    try:
        response = litellm.completion(
            model=model, messages=messages, timeout=timeout, **call_kwargs,
        )
    except Exception as exc:
        raise LLMProviderCallError(f"litellm.completion (stream) failed: {exc}") from exc

    yield from _chunks_from_litellm(response)


def _chunks_from_litellm(response: Any) -> Iterator[LLMStreamChunk]:
    last_delta: str | None = None
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        content = delta.content
        if content:
            yield LLMStreamChunk(delta=content, done=False)
            last_delta = content
    # terminal chunk: try to retrieve usage if litellm exposes it post-stream
    usage = _extract_usage(response)
    yield LLMStreamChunk(delta="", done=True, usage=usage)


def _extract_usage(response_or_stream: Any) -> LLMTokenUsage | None:
    raw_usage = getattr(response_or_stream, "usage", None) or getattr(response_or_stream, "_usage", None)
    if raw_usage is None:
        return None
    return LLMTokenUsage(
        prompt_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
        total_tokens=getattr(raw_usage, "total_tokens", 0) or 0,
    )
```

### Phase D: ClaudeAgentSDKProvider subset

```python
_COMPLETE_UNSUPPORTED_PAYLOAD: dict[str, Any] = {
    "error": "claude_agent_sdk_complete_unsupported",
    "message": "ClaudeAgentSDKProvider does not support plain text completion",
    "summary": {"provider": "claude_agent_sdk", "method": "complete"},
    "hint": "Use LiteLLMProvider for complete/complete_streaming; claude_agent_sdk is subset-only (complete_structured)",
}

_STREAM_UNSUPPORTED_PAYLOAD: dict[str, Any] = {
    "error": "claude_agent_sdk_streaming_unsupported",
    "message": "ClaudeAgentSDKProvider does not support streaming completion",
    "summary": {"provider": "claude_agent_sdk", "method": "complete_streaming"},
    "hint": "Use LiteLLMProvider for complete_streaming; claude_agent_sdk is subset-only",
}

def complete(self, **kwargs) -> LLMCompletion:
    raise LLMProviderConfigError(_COMPLETE_UNSUPPORTED_PAYLOAD)

def complete_streaming(self, **kwargs) -> Iterator[LLMStreamChunk]:
    raise LLMProviderConfigError(_STREAM_UNSUPPORTED_PAYLOAD)
    yield  # unreachable: makes mypy understand this is a generator
```

注意: `complete_streaming` は Iterator を返す契約だが、この実装は raise 前に yield を評価しないので、関数本体に `yield` を含めることで mypy を満足させつつ実際の yield は発生しない。

### Phase E: handler 側書き換え

`create_llm_handler` サンプル:

```python
def create_llm_handler(
    provider: LLMProviderPort | None = None,
    retry: int = 3,
    timeout: int = 30,
) -> NodeHandler:
    def handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        from yagra.handlers._llm_common import (
            extract_llm_params,
            interpolate_prompt,
            llm_retry_loop,
            report_completion_usage,
            resolve_handler_provider,
        )

        p = extract_llm_params(params, default_retry=retry)
        system_prompt, user_prompt = interpolate_prompt(
            p.system_prompt_template, p.user_prompt_template, state,
        )
        resolved = resolve_handler_provider(provider, params.get("provider"))

        def _call() -> dict[str, Any]:
            completion = resolved.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=p.litellm_model,
                timeout=timeout,
                **p.model_kwargs,
            )
            report_completion_usage(completion.usage, p.litellm_model, p.provider)
            return {p.output_key: completion.content}

        return llm_retry_loop(_call, p.effective_retry)

    return handler
```

重要: `_call()` 内部で `LLMProviderCallError` を `LLMHandlerCallError` に translate する必要あり（judge と同様パターン）。`llm_retry_loop` を Port 例外対応に拡張するか、handler 側で try/except する。推奨は `llm_retry_loop` 内で `LLMProviderCallError` → `LLMHandlerCallError` に変換する拡張。

### Phase E 補助: `resolve_handler_provider`

```python
def resolve_handler_provider(
    provider_arg: LLMProviderPort | None,
    params_provider: Any,
) -> LLMProviderPort:
    if provider_arg is not None:
        if not isinstance(provider_arg, LLMProviderPort):
            raise LLMHandlerConfigError(
                {
                    "error": "invalid_provider_instance",
                    "message": "provider argument does not implement LLMProviderPort",
                    "summary": {"type": type(provider_arg).__name__},
                    "hint": "Pass an LLMProviderPort implementation or omit the argument",
                }
            )
        return provider_arg

    if params_provider is None:
        name = "litellm"
    elif isinstance(params_provider, str):
        name = params_provider
    else:
        raise LLMHandlerConfigError(
            {
                "error": "invalid_provider_param",
                "message": "'provider' param must be a string",
                "summary": {"type": type(params_provider).__name__},
                "hint": "Set params.provider to 'litellm' or 'claude_agent_sdk'",
            }
        )

    from yagra.adapters.outbound.llm_providers import resolve_provider
    try:
        return resolve_provider(name)
    except ValueError as exc:
        raise LLMHandlerConfigError(
            {
                "error": "unknown_provider",
                "message": str(exc),
                "summary": {"provider": name},
                "hint": "Use 'litellm' or 'claude_agent_sdk'. Install 'yagra[judge]' for claude_agent_sdk.",
            }
        ) from exc
```

**注意**: 既存 `LLMHandlerConfigError` は `super().__init__(msg)` しか持たないため、構造化 dict を渡すと `str(exc)` = str(dict) になる。judge の `JudgeHandlerError` は `self.payload = payload` 属性を追加しており、実装上の対称性のため、**`LLMHandlerError` にも同様の payload 属性を追加してよい**（Contract の Out スコープを壊さない、backward compat も維持される）。

### Phase E: streaming unwrap

```python
# _llm_common.py
def _yield_stream_text(chunks: Iterator[LLMStreamChunk]) -> Generator[str, None, None]:
    last_usage: LLMTokenUsage | None = None
    for chunk in chunks:
        if chunk.usage is not None:
            last_usage = chunk.usage
        if chunk.delta:
            yield chunk.delta
        if chunk.done:
            break
    # last_usage を上位から参照できる closure 経由でレポートする必要あり
```

streaming handler では generator factory を使って `last_usage` を handler 側で受け取り、report する仕組みにする:

```python
def _stream_and_report(
    chunks: Iterator[LLMStreamChunk],
    litellm_model: str,
    provider_name: str,
) -> Generator[str, None, None]:
    last_usage: LLMTokenUsage | None = None
    for chunk in chunks:
        if chunk.usage is not None:
            last_usage = chunk.usage
        if chunk.delta:
            yield chunk.delta
        if chunk.done:
            break
    report_streaming_usage(last_usage, litellm_model, provider_name)
```

### Phase G: schema 更新

3 handler の `*_PARAMS_SCHEMA` すべてに provider を追加:

```python
"provider": {
    "type": "string",
    "enum": ["litellm", "claude_agent_sdk"],
    "default": "litellm",
    "description": (
        "LLM provider adapter. 'litellm' (default) supports 100+ providers via API keys; "
        "'claude_agent_sdk' uses Claude subscription auth (subset: structured output only)."
    ),
},
```

### Phase G: CHANGELOG エントリ

```markdown
## [Unreleased]

### Added
- `LLMProviderPort.complete` / `complete_streaming` Protocol メソッド追加
- `LLMCompletion` / `LLMStreamChunk` / `LLMTokenUsage` dataclass を `ports/outbound/llm_provider.py` に追加（pure Python、SDK 非依存）
- `src/yagra/handlers/errors.py` 新設で LLM handler 例外階層を一元化
- 3 LLM handler の `*_PARAMS_SCHEMA` に `provider` フィールド追加（default `"litellm"`、enum `["litellm", "claude_agent_sdk"]`）

### Changed
- 既存 `create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler` を `LLMProviderPort` 経由に移行。litellm への直接依存を剥離
- 3 handler factory に `provider: LLMProviderPort | None = None` を追加（judge handler と同じ hybrid signature）
- `handlers/_llm_common.py` の token usage reporting を `LLMTokenUsage` dataclass 受取形式に書換え
- `ClaudeAgentSDKProvider.complete` / `complete_streaming` は subset（`LLMProviderConfigError` 4-field payload を raise）
```

---

## チェックリスト（Contract SC 対応）

実装時に 1 つずつ確認すること。

- [ ] **SC-1**: Port Protocol に `complete` / `complete_streaming` 追加、`LiteLLMProvider` 両方実装、`ClaudeAgentSDKProvider` は `LLMProviderConfigError` を raise
- [ ] **SC-2**: 3 handler で `import litellm` 削除、`litellm.` 関数呼出ゼロ、`resolve_provider` / hybrid signature 経由のみ
- [ ] **SC-3**: `examples/llm-basic/workflow.yaml` / `examples/llm-structured/workflow.yaml` / `examples/llm-streaming/workflow.yaml` 無改修で動作、default provider `"litellm"`、streaming 戻り値 `Generator[str, None, None]` 維持
- [ ] **SC-4**: 3 handler factory が `provider: LLMProviderPort | None = None` を受付、DI > params 優先
- [ ] **SC-5**: ベースライン 996 passed 継続 + 新規テスト ≥6 件（DI + params 各 handler で最低 1 件ずつ）
- [ ] **SC-6**: grep 境界チェック 4 件すべて PASS
- [ ] **SC-7**: `docs/agent-integration-guide.md` に provider 説明 + 2 レベル provider 注記、`CHANGELOG.md` `[Unreleased]` に Added/Changed
- [ ] **SC-8**: `uv run pre-commit run --all-files` All Passed、`uv run pytest -q` 全 pass（pre-existing flaky/playwright 除く）
- [ ] **SC-9**: 3 handler の schema に provider、`yagra handlers --format json` で確認
- [ ] **SC-10**: `LLMCompletion` / `LLMStreamChunk` / `LLMTokenUsage` dataclass 追加（`@dataclass(frozen=True, slots=True)`）、tests/unit/ports/ に smoke test
- [ ] **SC-11**: `handlers/errors.py` 新設、`llm_handler.py` 再 export、`python -c "import yagra.handlers"` 成功、`_llm_common.py` → `llm_handler.py` 矢印消滅
- [ ] **SC-12**: `report_completion_usage(usage: LLMTokenUsage | None, ...)` 新関数、litellm 直呼びバージョン削除、streaming best-effort
- [ ] **SC-13**: `patch("yagra.handlers.{...}.litellm")` → Fake provider DI または `adapter-level` patch にシフト
- [ ] **SC-14**: mypy 型エラーゼロ、dataclass 引数順 default 末尾、`Iterator[LLMStreamChunk]` は `from collections.abc import Iterator`
- [ ] **SC-15**: streaming 公開 API `Generator[str, None, None]` 維持、`_yield_stream_text`（または `_stream_and_report`）で unwrap、terminal chunk の usage で report
- [ ] **SC-16**: `params["provider"]` unknown 時 `LLMHandlerConfigError` 4-field payload、hint 文言 judge と統一

---

## 事前組込項目

- **CHANGELOG 追記**（PMO 昇格項目）: `[Unreleased]` Added + Changed エントリ
- **4 フィールド構造化エラー**: `{error, message, summary, hint}` 全失敗経路で採用
- **r""" docstring**: バックスラッシュ例を含む docstring は必ず `r"""` プレフィックス（D301 回避）

---

## スコープ境界

### In
- SC-1〜SC-16 のすべて

### Out（touch 禁止）
- `ClaudeAgentSDKProvider` の `complete` / `complete_streaming` 実装（今回は subset only）
- fake provider 実装（#5 別タスク）
- token usage reporting の adapter 層完全移設
- handler の `adapters/outbound/handlers/` 再配置（#14 別タスク）
- `_llm_common.py` の破壊的 API 変更（既存関数削除は OK、既存 **引数削除** は禁止）
- MCP/CLI 変更
- `complete_structured` 戻り型 dataclass 化

---

## 検証証拠の記録先

- `tasks/20260424112349_developer1-handlers-port-migration.md`: Phase A-H 各工程の出力、テスト結果、コマンド出力
- `tasks/20260424112349_review-handlers-port-migration.md`: PMO レビュー（Contract SC-1〜SC-16 を DoD として判定）
- `tasks/progress.md`: 各 phase 完了時に Edit で更新（Write 禁止）
