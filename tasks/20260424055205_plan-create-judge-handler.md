# Plan: #23 `create_judge_handler` 実装

**タスク ID**: Backlog #23
**作成日**: 2026-04-24
**参照 Contract**: `tasks/20260424143714_contract-po-pm-create-judge-handler.md`
**参照 Intent**: `tasks/20260424054919_intent-create-judge-handler.md`

---

## Developer 構成

PM 環境制約（Task/Agent 起動不可）により、Developer 1 名 + PMO を **PM が sequentially 代行**。
実作業は工程ベースで分離記録する:

- 工程 A: Port + Adapter + resolve_provider（新規 4 ファイル + 対応 test 3 ファイル）
- 工程 B: judge handler 本体 + rubric loader + unit test（新規 1 ファイル + test 1 ファイル）
- 工程 C: catalog / `__init__` / pyproject / workflow_explainer / docs / CHANGELOG / 統合テスト
- 工程 D: 品質ゲート（pre-commit, pytest full suite）+ PMO セルフレビュー

各工程完了ごとに `tasks/` に進捗補足ドキュメント（必要に応じて `developer1-*.md` 形式）を追加する。

---

## 実装順序

### Phase 1: 基礎構造（工程 A）

1. **`src/yagra/ports/outbound/llm_provider.py` 新設**
   - Protocol + `runtime_checkable` で `LLMProviderPort` を定義
   - メソッド: `complete_structured(prompt: str, schema: dict, model: str, **kwargs) -> dict`
     - 戻り値は dict（provider が JSON をパース済みのもの）
   - 例外: `LLMProviderError`（基底）/ `LLMProviderCallError`（通信系）/ `LLMProviderConfigError`（設定系）
   - `litellm` / `claude_agent_sdk` 具象を絶対に import しない

2. **`src/yagra/adapters/outbound/llm_providers/__init__.py` 新設**
   - `resolve_provider(name: str) -> LLMProviderPort` を実装
   - 受付け: `"claude_agent_sdk"` / `"litellm"`、未知文字列は `ValueError` with hint
   - 遅延 import で循環依存回避

3. **`src/yagra/adapters/outbound/llm_providers/litellm_provider.py` 新設**
   - `LiteLLMProvider` 実装
   - `litellm.completion` 呼出、`response_format={"type":"json_object"}` + system prompt への schema 注入
   - JSON parse + ValidationError → `LLMProviderCallError` 変換
   - `model` 引数から `provider/model` 文字列へ。`model="openai/gpt-4o"` のような fully-qualified 文字列はそのまま

4. **`src/yagra/adapters/outbound/llm_providers/claude_agent_sdk_provider.py` 新設**
   - `ClaudeAgentSDKProvider` 実装
   - `claude_agent_sdk` を関数内で遅延 import、ImportError 時は 4 フィールド構造化エラー
   - `query()` + `ClaudeAgentOptions(output_format={"type":"json_schema","schema":...})` 経由
   - デフォルトモデル `"sonnet"`
   - **async bridge**: `asyncio.get_running_loop()` 検出時は `ThreadPoolExecutor` で別スレッド化、それ以外は `asyncio.run` 直接利用
   - `ResultMessage.structured_output` を取得して dict 返却

5. **テスト（3 ファイル）**
   - `tests/unit/adapters/outbound/llm_providers/__init__.py`（空）
   - `test_litellm_provider.py`: litellm モック、≥2 ケース（success / 通信エラー）
   - `test_claude_agent_sdk_provider.py`: `sys.modules` で `claude_agent_sdk` を MagicMock、≥2 ケース（success / running loop 時 ThreadPoolExecutor 分離成功）
   - `test_resolve_provider.py`: ≥2 ケース（既知名 OK / 未知名 ValueError）

### Phase 2: judge handler（工程 B）

6. **`src/yagra/handlers/judge.py` 新設**
   - `create_judge_handler(provider: LLMProviderPort | None = None, retry: int = 3, timeout: int = 30)` 実装
   - `JudgeHandlerError` / `JudgeHandlerConfigError` / `JudgeHandlerCallError` 定義（4 フィールド構造化エラー）
   - rubric YAML loader（`_load_rubric(ref_or_inline, workflow_dir)`）を同ファイル内に実装
     - `rubric_ref`: `path#key` 構文対応（key 省略で root 読込）
     - `rubric` inline: dict をそのまま
   - rubric バリデーション:
     - `criteria` が空 / 欠如 → `rubric_empty`
     - `criteria[].name` 欠如 → `rubric_missing_name`
     - `scale.min >= scale.max` → `rubric_invalid_scale`
   - rubric → JSON Schema 変換 (criteria → object properties、`require_reasoning: true` で reasoning required)
   - provider 解決の hybrid pattern:
     1. 関数引数 `provider` が Port instance → そのまま使用
     2. `params["provider"]` 文字列 → `resolve_provider()` 経由
     3. どちらもなし → `"claude_agent_sdk"` デフォルト
   - `_llm_common.interpolate_prompt` / `build_messages` 再利用して prompt 補間
   - provider から受け取った structured_output を検証（`score` / `reasoning` 欠如 → `invalid_judge_output`）
   - 結果を `{output_key: {score: ..., reasoning: ..., rubric_items: [...]}}` 形式で返却
   - `JUDGE_HANDLER_PARAMS_SCHEMA` 定義（SC-5 の要件）

7. **テスト `tests/unit/handlers/test_judge.py` 新設**
   - ≥4 ケース:
     1. 正常系（provider モック + inline rubric）
     2. rubric `scale.min >= scale.max` → `rubric_invalid_scale`
     3. provider エラー → `JudgeHandlerCallError` の propagation
     4. `params["provider"]="claude_agent_sdk"` で `claude_agent_sdk` 未インストール時 → 4 フィールド `ImportError`
   - 追加: rubric 空 criteria / name 欠如 / rubric_ref ファイル読込 / output 不正 のケース

### Phase 3: 統合（工程 C）

8. **`src/yagra/handlers/catalog.py` 更新**: `judge` を `BUILTIN_HANDLERS_INFO` に追加

9. **`src/yagra/handlers/__init__.py` 更新**: `create_judge_handler` と `JUDGE_HANDLER_PARAMS_SCHEMA` を export

10. **`src/yagra/application/use_cases/workflow_explainer.py` 更新**: `builtin_handlers = {"llm", "structured_llm", "streaming_llm", "judge"}` にし、judge の default output_key `"judge_result"` 分岐を追加

11. **`pyproject.toml` 更新**:
    - `[project.optional-dependencies]` に `judge = ["claude-agent-sdk"]`
    - `[tool.mypy.overrides]` に `claude_agent_sdk` / `claude_agent_sdk.*` を追加

12. **`docs/agent-integration-guide.md` 更新**: judge handler セクション追加（rubric YAML 例 + provider 切替例 + 使い方）

13. **`CHANGELOG.md` 更新**: `[Unreleased]` Added に judge handler + `LLMProviderPort` + `yagra[judge]` extra を記載

14. **`tests/integration/test_validate_judge_workflow.py` 新設**（SC-14）:
    - judge handler node を含む workflow YAML を `validate_workflow_for_ui` で検証
    - is_valid: true、error issue なし
    - output_key 未指定の judge ノードが output_variable 抽出で `judge_result` を返すことを確認

15. **既存テストへの影響確認**:
    - `test_handler_params_schema.py` の handler 数アサーション箇所（3 → 4 ハンドラに増える）を更新
    - `test_json_output_contains_three_handlers` など名称が「3 つ」前提のテストを修正

### Phase 4: 品質ゲート（工程 D）

16. **`uv run pre-commit run --all-files`** All Passed 確認
17. **`uv run pytest -q`** 既存 952 + 新規 PASSED 確認（playwright 33 skipped は pre-existing）
18. **Hexagonal 境界検査**:
    - `grep -r "import litellm\|import claude_agent_sdk" src/yagra/ports/` → 0 件
    - `grep -r "from yagra.handlers\|from yagra.adapters" src/yagra/domain/` → 0 件
19. **PMO セルフレビュー**: `tasks/{TS}_review-create-judge-handler.md` 作成、SC-1〜SC-14 green 確認

---

## 主要設計判断メモ

### Port `complete_structured` のシグネチャ

```python
@runtime_checkable
class LLMProviderPort(Protocol):
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

- 位置引数を最小化し kwargs 爆発を回避
- dict を返す（Pydantic インスタンスは handler 層で責務）

### rubric → JSON Schema 変換（最小版）

```yaml
criteria:
  - name: relevance
    scale: {min: 1, max: 5}
require_reasoning: true
```

→

```json
{
  "type": "object",
  "required": ["score", "reasoning", "rubric_items"],
  "properties": {
    "score": {
      "type": "object",
      "properties": {
        "relevance": {"type": "integer", "minimum": 1, "maximum": 5}
      },
      "required": ["relevance"]
    },
    "reasoning": {"type": "string"},
    "rubric_items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "score": {"type": "integer"},
          "reasoning": {"type": "string"}
        },
        "required": ["name", "score"]
      }
    }
  }
}
```

### 構造化エラー形式（#4 継承）

```python
raise JudgeHandlerConfigError({
    "error": "rubric_invalid_scale",
    "message": "scale.min must be < scale.max",
    "summary": {"criterion": "relevance", "min": 5, "max": 3},
    "hint": "Ensure scale.min < scale.max in your rubric YAML",
})
```

### PM 事前確認ポイント

- `structured_llm_handler.py` の `schema_yaml` YAML paraser は judge では流用しない（rubric YAML は独自 schema のため）
- `_llm_common.py` の `interpolate_prompt` は judge の system prompt 生成で再利用可能
- `workflow_explainer.py` の builtin_handlers セットに judge を追加する必要がある（output_key default "judge_result"）

---

## チェックリスト（SC 対応）

- [ ] SC-1: `ports/outbound/llm_provider.py` 新設（Protocol、具象 import なし）
- [ ] SC-2a: `LiteLLMProvider` 実装 + test
- [ ] SC-2b: `ClaudeAgentSDKProvider` 実装 + test + async bridge
- [ ] SC-2c: `resolve_provider()` Factory + test
- [ ] SC-3: `create_judge_handler` 実装（hybrid pattern + sonnet default + async safety）
- [ ] SC-4: `handlers/__init__.py` + `catalog.py` 反映、`yagra handlers` / `list_handlers` MCP に現れる
- [ ] SC-5: `JUDGE_HANDLER_PARAMS_SCHEMA`（oneOf / enum / default）
- [ ] SC-6: `pyproject.toml` に `yagra[judge]`、未インストール時 4 フィールド ImportError
- [ ] SC-7: 各 unit test ≥ ケース数
- [ ] SC-8: 全テスト PASSED
- [ ] SC-9: pre-commit All Passed
- [ ] SC-10: Hexagonal 境界違反 0
- [ ] SC-11: `docs/agent-integration-guide.md` 更新
- [ ] SC-12: `CHANGELOG.md` [Unreleased] Added 記載
- [ ] SC-13: rubric 不正値検出テスト（scale / 空 criteria / name 欠如）
- [ ] SC-14: `yagra validate` 統合テスト

---

## リスク再評価

| リスク | 影響 | 対応 |
|-------|------|------|
| `claude_agent_sdk` を sys.modules にモック時の型衝突 | 中 | `MagicMock` で `query`, `ClaudeAgentOptions`, `ResultMessage` を全て用意 |
| `builtin_handlers` セット変更で既存テスト破壊 | 中 | `test_handler_params_schema.py` の「3 handlers」系テストを修正（4 handlers へ） |
| rubric ref の `#key` parser 未使用 | 低 | Contract で key 省略 OK 明記、path-only で root YAML 読込 |
| async bridge の ThreadPoolExecutor スレッドリーク | 低 | `with ThreadPoolExecutor()` コンテキストで使用 |
| CHANGELOG 追記漏れ | 低 | Mission Brief チェックリスト標準項目（#4 で確立） |
