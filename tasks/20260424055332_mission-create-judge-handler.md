# Mission Brief: #23 `create_judge_handler` 実装

**宛先**: Developer 1（PM 代行）
**作成日**: 2026-04-24
**参照**: Contract `20260424143714_contract-*` / Intent `20260424054919_*` / Plan `20260424055205_*`

---

## ミッション

Yagra に「LLM-as-a-Judge」基本版を導入する。新規 Port `LLMProviderPort` を境界とし、`LiteLLMProvider` / `ClaudeAgentSDKProvider` の 2 具象 + Factory を adapters 層に配置する。handler 層に `create_judge_handler` を新設し、rubric YAML から LLM が構造化スコアを返す機能を実現する。

---

## 挙動仕様（Contract 転記 + 詳細化）

### YAML インターフェース

```yaml
nodes:
  - id: "judge_node"
    handler: "judge"
    params:
      provider: "claude_agent_sdk"   # or "litellm", 省略時 claude_agent_sdk
      model: "sonnet"                 # provider 依存
      rubric_ref: "rubrics/quality.yaml#default"   # または rubric inline
      prompt_ref: "prompts/judge.yaml#system"
      output_key: "judge_result"
```

### rubric YAML スキーマ

```yaml
default:
  description: "回答品質の評価ルーブリック"
  criteria:
    - name: "relevance"
      description: "質問との関連性"
      scale: {min: 1, max: 5}
    - name: "accuracy"
      scale: {min: 1, max: 5}
  require_reasoning: true
```

### 出力構造

```python
{
    "judge_result": {
        "score": {"relevance": 4, "accuracy": 5, "_overall": 4.5},
        "reasoning": "...",
        "rubric_items": [
            {"name": "relevance", "score": 4, "reasoning": "..."},
            ...
        ],
    }
}
```

`_overall` は criteria 数値スコアの平均を自動計算（float）。

### Provider 解決ロジック

```python
def _resolve_provider_instance(
    provider_arg: LLMProviderPort | None,
    params_provider: str | None,
) -> LLMProviderPort:
    if isinstance(provider_arg, LLMProviderPort):
        return provider_arg
    name = params_provider or "claude_agent_sdk"
    return resolve_provider(name)
```

### 構造化エラー（#4 継承 4 フィールド）

```python
raise JudgeHandlerConfigError({
    "error": "rubric_invalid_scale",
    "message": "scale.min must be less than scale.max",
    "summary": {"criterion": "relevance", "min": 5, "max": 3},
    "hint": "Ensure scale.min < scale.max in your rubric YAML",
})
```

### async bridge（SC-3）

```python
def _run_async(coro: Coroutine) -> Any:
    try:
        asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)
```

### Silent success 防止

- rubric criteria 空 → `rubric_empty` で fail-fast
- provider structured_output に `score`/`reasoning` 欠如 → `invalid_judge_output` で fail-fast

---

## 実装スケッチ

### 1. `src/yagra/ports/outbound/llm_provider.py`

```python
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class LLMProviderError(RuntimeError):
    pass


class LLMProviderConfigError(LLMProviderError):
    pass


class LLMProviderCallError(LLMProviderError):
    pass


@runtime_checkable
class LLMProviderPort(Protocol):
    """Structured JSON output を返す LLM provider の契約."""

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> dict[str, Any]:
        ...
```

### 2. `src/yagra/adapters/outbound/llm_providers/__init__.py`

```python
from __future__ import annotations

from yagra.ports.outbound.llm_provider import LLMProviderPort


def resolve_provider(name: str) -> LLMProviderPort:
    if name == "claude_agent_sdk":
        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )
        return ClaudeAgentSDKProvider()
    if name == "litellm":
        from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
        return LiteLLMProvider()
    raise ValueError(
        f"Unknown LLM provider '{name}'. "
        f"Expected one of: 'claude_agent_sdk', 'litellm'."
    )
```

### 3. `litellm_provider.py` の要点

- `litellm.completion(model=..., messages=..., response_format={"type": "json_object"})`
- system prompt の末尾に schema JSON を注入
- 応答 `content` を `json.loads` → dict
- 通信失敗 → `LLMProviderCallError`、JSON parse 失敗 → `LLMProviderCallError`

### 4. `claude_agent_sdk_provider.py` の要点

```python
def complete_structured(self, *, system_prompt, user_prompt, schema, model, timeout, **kwargs):
    try:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
    except ImportError as exc:
        raise ImportError({
            "error": "claude_agent_sdk_not_installed",
            "message": "claude-agent-sdk is required for ClaudeAgentSDKProvider",
            "summary": {"provider": "claude_agent_sdk"},
            "hint": 'Run `uv add "yagra[judge]"` to enable Claude Agent SDK provider',
        }) from exc

    async def _invoke() -> dict:
        options = ClaudeAgentOptions(
            output_format={"type": "json_schema", "schema": schema},
            model=model or "sonnet",
        )
        combined = f"{system_prompt}\n\n{user_prompt}".strip()
        async for msg in query(prompt=combined, options=options):
            if isinstance(msg, ResultMessage) and msg.structured_output:
                return msg.structured_output
        raise LLMProviderCallError("Claude Agent SDK returned no structured output")

    return _run_async(_invoke())
```

### 5. `handlers/judge.py` のコア構造

```python
def create_judge_handler(
    provider: LLMProviderPort | None = None,
    retry: int = 3,
    timeout: int = 30,
) -> NodeHandler:
    def handler(state, params):
        # 1. rubric 解決（params.rubric / rubric_ref → dict）
        rubric_dict = _resolve_rubric(params, workflow_dir=params.get("_workflow_dir"))
        _validate_rubric(rubric_dict)  # silent success 防止

        # 2. schema 変換
        schema = _rubric_to_json_schema(rubric_dict)

        # 3. provider 解決（hybrid pattern）
        resolved_provider = _resolve_provider_instance(provider, params.get("provider"))

        # 4. prompt 補間
        prompt = params.get("prompt") or {}
        system_prompt, user_prompt = interpolate_prompt(
            prompt.get("system", _default_system_prompt(rubric_dict)),
            prompt.get("user", "{query}"),
            state,
        )

        # 5. provider 呼出 + retry
        def _call() -> dict:
            return resolved_provider.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                model=params.get("model", "sonnet"),
                timeout=timeout,
            )

        result = llm_retry_loop(_call, retry)

        # 6. output validation
        _validate_judge_output(result, rubric_dict)

        # 7. _overall score 計算
        result["score"]["_overall"] = _compute_overall(result["score"], rubric_dict)

        output_key = params.get("output_key", "judge_result")
        return {output_key: result}

    return handler
```

### 6. `workflow_explainer.py` の変更

```python
builtin_handlers = {"llm", "structured_llm", "streaming_llm", "judge"}
builtin_default_output_keys = {
    "llm": "output",
    "structured_llm": "output",
    "streaming_llm": "output",
    "judge": "judge_result",
}
if not output_key and node.handler in builtin_handlers:
    outputs.append(builtin_default_output_keys[node.handler])
```

---

## 禁止事項

- **`ports/outbound/llm_provider.py` に `litellm` / `claude_agent_sdk` を import しない**（Hexagonal 厳守）
- **`domain/` レイヤに judge 関連 import を追加しない**
- **既存 `create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler` に破壊変更を加えない**
- **`pip install` 禁止、`uv add` のみ**
- **判定 silent success（rubric 空 or output 欠損で警告のみ）を許容しない**
- **既存テストを `--ignore` や `skip` で回避しない**

---

## 実装チェックリスト（SC ↔ 実装項目対応）

- [ ] SC-1: `LLMProviderPort` 新設、具象 import なし
- [ ] SC-2a: `LiteLLMProvider`: `litellm.completion` + JSON parse + 通信系エラー変換
- [ ] SC-2b: `ClaudeAgentSDKProvider`: async 対応、`output_format={"type":"json_schema",...}`、デフォルト `"sonnet"`、構造化 ImportError
- [ ] SC-2c: `resolve_provider()`: 既知 2 名 OK / 未知 ValueError
- [ ] SC-3: `create_judge_handler`: hybrid provider 解決、async safe、_overall 自動計算
- [ ] SC-4: `catalog.py` + `handlers/__init__.py` に judge 登録
- [ ] SC-5: `JUDGE_HANDLER_PARAMS_SCHEMA`: `provider` enum、`rubric`/`rubric_ref` oneOf、`prompt`/`prompt_ref` oneOf、`output_key` default
- [ ] SC-6: `pyproject.toml` `[project.optional-dependencies]` に `judge = ["claude-agent-sdk"]`、mypy overrides に ignore_missing_imports
- [ ] SC-7: 各 unit test 作成（≥4 / ≥2 / ≥2 / ≥2 ケース）
- [ ] SC-8: 全テスト PASSED（既存 952 + 新規）
- [ ] SC-9: pre-commit All Passed
- [ ] SC-10: Hexagonal 境界違反 0
  - `grep -r "import litellm\|from litellm\|import claude_agent_sdk\|from claude_agent_sdk" src/yagra/ports/` → 0 件
  - `grep -r "from yagra.handlers\|from yagra.adapters" src/yagra/domain/` → 0 件
- [ ] SC-11: `docs/agent-integration-guide.md` に judge 使い方追記（rubric YAML 例 + provider 切替）
- [ ] SC-12: `CHANGELOG.md` [Unreleased] Added に記載
- [ ] SC-13: rubric 不正値テスト（scale.min >= max / criteria 空 / name 欠如 / rubric_ref 未発見）
- [ ] SC-14: `tests/integration/test_validate_judge_workflow.py` で judge node の workflow 検証
- [ ] 追加: `test_handler_params_schema.py` の handler 数前提テスト修正（3 → 4）
- [ ] 追加: workflow_explainer `builtin_handlers` に judge + 分岐 default output_key

---

## 検証手順（Developer 自己チェック）

1. `uv run pre-commit run --all-files`
2. `uv run pytest -q` 全 PASSED
3. `uv run yagra handlers --format json | python -c "import json,sys; d=json.loads(sys.stdin.read()); print([h['name'] for h in d['handlers']])"` → `['llm', 'structured_llm', 'streaming_llm', 'judge']` を確認
4. Hexagonal 境界 grep（上記）
5. rubric 例の unit test で provider モック呼出時の schema 注入確認

---

## 完了条件

- SC-1〜SC-14 全項目 green
- pre-commit + pytest 両 PASSED
- PMO レビューで Critical / Major 0 件
