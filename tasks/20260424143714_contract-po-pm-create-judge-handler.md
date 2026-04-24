# PO-PM Task Contract: #23 `create_judge_handler` 実装（LLM-as-a-Judge 基本版 + Port/Adapter）

**タスク ID**: Backlog #23
**サイズ**: M（設計判断あり、新規ファイル 5-7 個、テスト複数、既存コード影響最小）
**作成日**: 2026-04-24
**ステータス**: PO-PM Alignment 1往復目

---

## ビジョンコンテキスト（PO観点）

### このタスクの位置づけ
- ビジョン正本 `docs/product/vision.md` の **差別化軸「AI が AI を評価・改善」** の根幹実装
- Phase 3「LLM-as-a-Judge Handlers」の最初の実装タスク
- ビジョン体現度スコア「差別化軸の実装度 2/5 → 3/5」へ動かす起点
- 後続タスク #24 (`examples/self-improve/`) / #25 (`evaluate_traces` MCP) / #26 (E2E) / #27 (docs) の基盤

### 期待する成果
1. **動く `create_judge_handler`**: YAML で宣言した rubric に基づき LLM が構造化スコア＋根拠を返す
2. **Port/Adapter 基盤**: LLM provider を切り替え可能にする `LLMProviderPort` と 2 つの adapter
3. **API キー不要の実走**: Claude Agent SDK のサブスクリプション認証で E2E まで到達可能
4. **既存 handler 非破壊**: `create_llm_handler` 等は litellm のまま維持（後続タスクで段階移行）

### 優先度の根拠（Must）
- ビジョン根幹。放置すると「ビジョンを標榜しているが実装 0 件」の乖離が続く
- 依存 #1（方針確定）解消済み。実装ブロッカーなし
- #4 (apply_update golden gate) 完了で「propose → judge → golden → apply」サイクルの後半部分は整備済み

### 品質・スコープ判断基準
- **妥協してよい点**: 初版では Claude provider のみ fully 動作でも可（litellm provider は後続タスクで深掘り）。rubric のテンプレートライブラリは #27 で別途整備
- **妥協できない点**:
  - Port/Adapter 境界の Hexagonal 準拠（`ports/` は Protocol のみ、`adapters/` に具象、循環依存なし）
  - rubric YAML → JSON Schema 変換で provider 非依存なインターフェース
  - `yagra handlers` / MCP `list_handlers` の出力に `judge` が表示される
  - ユニットテスト ≥3 ケース網羅（provider をモックで差し替え）

---

## 成功基準（DoD）

PM は以下を **すべて** 満たした状態で PMO に提出すること:

- [ ] **SC-1**: `src/yagra/ports/outbound/llm_provider.py` に `LLMProviderPort`（Protocol）が定義されている
- [ ] **SC-2a**: `src/yagra/adapters/outbound/llm_providers/litellm_provider.py` に `LiteLLMProvider` が実装されている（`litellm.completion` 経由で JSON 構造化出力、`response_format={"type":"json_object"}` + system prompt への schema 注入）
- [ ] **SC-2b**: `src/yagra/adapters/outbound/llm_providers/claude_agent_sdk_provider.py` に `ClaudeAgentSDKProvider` が実装されている（`claude_agent_sdk.query` + `output_format={"type":"json_schema","schema":...}`、デフォルトモデル `"sonnet"`）
- [ ] **SC-2c**: `src/yagra/adapters/outbound/llm_providers/__init__.py` に `resolve_provider(name: str) -> LLMProviderPort` Factory 関数が実装されている（`"claude_agent_sdk"` / `"litellm"` 文字列 → 具象 adapter 解決、未知文字列は `ValueError` with hint）
- [ ] **SC-3**: `src/yagra/handlers/judge.py` に `create_judge_handler(provider: LLMProviderPort | None = None, ...)` が実装されている
  - `provider=None` の場合は `params["provider"]` 文字列から `resolve_provider()` で解決（既存 `create_structured_llm_handler` の「引数 vs params hybrid」パターンと対称）
  - 両方未指定時は `"claude_agent_sdk"` にフォールバック
  - `ClaudeAgentSDKProvider` のデフォルトモデルは `"sonnet"` 固定（ユーザー指定、コスト/品質バランス最適）
  - rubric を YAML ファイル（`rubric_ref`）またはインライン（`rubric`）で受け取れる
  - 出力は `{output_key: {"score": ..., "reasoning": ..., "rubric_items": [...]}}` 形式
  - **async ブリッジ安全動作**: `ClaudeAgentSDKProvider` は `asyncio.get_running_loop()` で running loop を検出し、running 中は ThreadPoolExecutor 経由で sync 化（or 明確な `JudgeHandlerCallError` を raise。どちらを採るかは PM 裁量）
- [ ] **SC-4**: `src/yagra/handlers/__init__.py` と `src/yagra/handlers/catalog.py` に `judge` が追加され、`yagra handlers` / MCP `list_handlers` の出力に現れる
- [ ] **SC-5**: `JUDGE_HANDLER_PARAMS_SCHEMA`（JSON Schema）が定義されている。既存 `LLM_HANDLER_PARAMS_SCHEMA` と同等の厳密さ:
  - `provider`: `enum: ["claude_agent_sdk", "litellm"]` + `default: "claude_agent_sdk"`
  - `model`: 文字列（provider 依存、`ClaudeAgentSDKProvider` は `"sonnet"` / `"opus"` 等の alias）
  - `rubric` と `rubric_ref` は `oneOf`（相互排他、必須）
  - `prompt` と `prompt_ref` は `oneOf`（相互排他、オプショナル）
  - `output_key`: 文字列、default `"judge_result"`
- [ ] **SC-6**: `pyproject.toml` に `claude-agent-sdk` を optional extra `yagra[judge]` として追加。未インストール状態で `ClaudeAgentSDKProvider` 初期化 or `create_judge_handler(provider="claude_agent_sdk")` 呼出時に構造化 `ImportError` を raise（4 フィールド形式、`hint: 'Run `uv add "yagra[judge]"` to enable Claude Agent SDK provider'`）
- [ ] **SC-7**: ユニットテストが以下を網羅する:
  - `tests/unit/handlers/test_judge.py` — ≥4 ケース（正常系、rubric 不正 = `scale.min >= scale.max` 等、provider エラー、`claude_agent_sdk` 未インストール時 `ImportError`）、provider モックで動作
  - `tests/unit/adapters/outbound/llm_providers/test_litellm_provider.py` — `litellm.completion` をモック、≥2 ケース
  - `tests/unit/adapters/outbound/llm_providers/test_claude_agent_sdk_provider.py` — `claude_agent_sdk.query` をモック、≥2 ケース（通常実行 + async event loop running 時の安全動作）
  - `tests/unit/adapters/outbound/llm_providers/test_resolve_provider.py` — Factory 関数のテスト ≥2 ケース（known name / unknown name ValueError）
- [ ] **SC-8**: **全テスト PASSED**（既存 952/952 + 新規）。`uv run pytest` で確認。playwright 33 件 skipped は pre-existing として許容
- [ ] **SC-9**: `uv run pre-commit run --all-files` All Passed（ruff format / ruff check / mypy）
- [ ] **SC-10**: Hexagonal 境界違反なし:
  - `ports/` が具象（`litellm` / `claude_agent_sdk`）を import しない
  - `domain/` が新規ファイルを import しない（judge は application 層寄りの handler）
  - adapters/outbound/llm_providers/ から application/handlers への逆依存なし
- [ ] **SC-11**: `docs/agent-integration-guide.md` に `judge` handler の使い方が追記されている（rubric YAML 例 + provider 切替例）
- [ ] **SC-12**: `CHANGELOG.md` の `[Unreleased]` に **Added** として `judge` handler と `LLMProviderPort` 新設を記載（#3/#4 同様のフォーマット）
- [ ] **SC-13**: rubric YAML の不正値検出テスト — `scale.min >= scale.max`、`criteria` 空配列、`criteria[].name` 欠如 など、構造化エラー 4 フィールドで返る
- [ ] **SC-14**: `yagra validate` で judge handler node を含む workflow YAML を検証しても false negative/positive が出ないことを統合テスト 1 本で確認（`tests/integration/test_validate_judge_workflow.py` か既存テストへの追加）

---

## 挙動仕様

### YAML 側のインターフェース

```yaml
# workflow.yaml
nodes:
  - id: "judge_node"
    handler: "judge"
    params:
      provider: "claude_agent_sdk"      # or "litellm" (将来)、省略時デフォルト claude_agent_sdk
      model: "sonnet"                    # provider 依存の model 識別子（claude_agent_sdk はデフォルト sonnet）
      rubric_ref: "rubrics/quality.yaml#default"  # または rubric: {...} インライン
      prompt_ref: "prompts/judge.yaml#system"     # rubric と合わせて judge 指示を組立
      output_key: "judge_result"
```

### rubric YAML のスキーマ（最小版）

```yaml
# rubrics/quality.yaml
default:
  description: "回答品質の評価ルーブリック"
  criteria:
    - name: "relevance"
      description: "質問との関連性 (1-5)"
      scale: {min: 1, max: 5}
    - name: "accuracy"
      description: "事実の正確性 (1-5)"
      scale: {min: 1, max: 5}
  require_reasoning: true
```

### 出力の構造

```python
{
    "judge_result": {
        "score": {"relevance": 4, "accuracy": 5, "_overall": 4.5},
        "reasoning": "回答は質問の意図に合致しており...",
        "rubric_items": [
            {"name": "relevance", "score": 4, "reasoning": "..."},
            {"name": "accuracy", "score": 5, "reasoning": "..."},
        ],
    }
}
```

### Provider 切替の解決

| `params.provider` 値 | 解決先 | 条件 |
|---------------------|-------|------|
| `"claude_agent_sdk"`（デフォルト） | `ClaudeAgentSDKProvider()` | `claude_agent_sdk` がインストール済み + `claude login` 済み |
| `"litellm"` | `LiteLLMProvider()` | API キー（`ANTHROPIC_API_KEY` 等）が環境変数にあり |
| `LLMProviderPort` インスタンス | そのまま使用（テスト・カスタム用） | - |

### エラーフォーマット（#4 と同形式）

```python
# rubric_ref が見つからない場合
raise JudgeHandlerConfigError(
    "rubric_not_found",
    f"Rubric reference '{rubric_ref}' not found",
    hint="Ensure the file exists and the key is correct",
)
```

### Silent Success 防止

- rubric の `criteria` が空配列の場合は実行を許可せず `JudgeHandlerConfigError("rubric_empty", ...)` で raise（#4 の no-case warning とは異なり、judge は criteria が必須のため fail-fast）
- provider が返した structured_output に想定フィールド（`score` / `reasoning`）が欠けている場合は `JudgeHandlerCallError("invalid_judge_output", ...)` で raise

---

## PM 技術コンテキスト（PO が事前調査で把握した事項）

### 既存構造の観察

- `src/yagra/ports/outbound/` に Port 群（`node_registry.py` / `golden_case_repository.py` / `trace_sink.py`）
  - 命名: `<名詞>.py`、内容: Protocol または ABC 定義のみ
- `src/yagra/adapters/outbound/` に具象（`in_memory_node_registry.py` / `local_golden_case_store.py` / `local_trace_sink.py`）
  - 新規 `llm_providers/` サブディレクトリは OK（既存 outbound 直下パターンからの拡張）
- `src/yagra/handlers/` は handler factory。既存 `llm_handler.py` / `structured_llm_handler.py` / `streaming_llm_handler.py` は `litellm` を直接 import
  - judge は Port 経由にすることで handlers/ レイヤから具象 provider 依存を分離する（将来の既存 handler 段階移行の基盤になる）

### Claude Agent SDK の利用ポイント（kb 参照）

- `pip install claude-agent-sdk` → `uv add` で追加
- 認証: `claude login` 済みサブスクリプション（API キー不要）
- 構造化出力:
  ```python
  from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
  options = ClaudeAgentOptions(output_format={"type": "json_schema", "schema": schema})
  async for msg in query(prompt=..., options=options):
      if isinstance(msg, ResultMessage) and msg.structured_output:
          return msg.structured_output
  ```
- handler は sync 関数なので、adapter 内で `asyncio.run` or 同期 API（あれば）を使う

### 既存テスト雛形

- `tests/unit/handlers/` に既存 handler のユニットテストあり（モック方式を踏襲）
- `tests/unit/adapters/outbound/` パターン（`test_local_*.py`）

### 学習ログ（過去タスクから継承）

- Mission Brief チェックリスト標準項目: CHANGELOG [Unreleased] 追記（#4 で標準化済み、PMO 指摘 0 件実績）
- 構造化エラー 4 フィールド `{error, message, summary, hint}` 形式（#4 で雛形確立、judge でも踏襲）
- silent success 防止: rubric 0 件や provider 未インストール時は warning 付き error（#4 no-case warning パターン応用）

---

## スコープ境界

### In Scope

- `LLMProviderPort` 新設（Protocol）
- `LiteLLMProvider` / `ClaudeAgentSDKProvider` 新設
- `create_judge_handler` 実装
- rubric YAML パーサ（既存 `prompts` パーサを参考にシンプルに）
- ユニットテスト + 統合（`yagra handlers` / `list_handlers` MCP 出力確認）
- docs / CHANGELOG / dependency 更新

### Out of Scope（別タスク）

- **既存 `create_llm_handler` 等の Port 経由への移行** → 後続タスクでバックログ追加
- **`examples/self-improve/` walking example** → #24 で実装
- **`evaluate_traces` MCP tool** → #25 で実装
- **E2E 統合テスト（propose → judge → golden → apply）** → #26 で実装
- **LLM-as-a-Judge ドキュメント（rubric best practices）** → #27 で実装
- **rubric テンプレートライブラリの複数用意** → #27 で実装
- **Studio UI での judge node 対応** → Studio 側 refactoring 後に別タスクで検討

---

## リスクと対応方針

| リスク | 対応方針 |
|-------|---------|
| `claude_agent_sdk` のテスト環境でのモック難度 | `claude_agent_sdk.query` を完全にモック化。実 API は E2E (#24, #26) で検証 |
| `claude_agent_sdk` の `query()` は async-only | adapter 内で `asyncio.run` で sync 化。handler は sync 関数のまま |
| rubric YAML のスキーマバリエーション爆発 | 初版は criteria の list 形式のみサポート。nested rubric は #27 で検討 |
| Port 設計の抽象度 | 初版は `complete_structured(prompt, schema, model)` のみ。streaming / multi-turn は将来拡張 |
| optional extra 設計ミス | `yagra[judge]` として `claude-agent-sdk` を entry point。`yagra[mcp]` の既存パターンを踏襲 |

---

## PMO レビュー観点

- Hexagonal 準拠（`ports/` に具象 import なし、`domain/` 不侵入）
- SRP 遵守（provider / handler / rubric parser の責務分離）
- エラーメッセージ品質（#4 の 4 フィールド形式踏襲）
- テスト網羅性（provider モック / rubric バリエーション / エラーケース）
- docs ↔ 実装の整合（agent-integration-guide.md 更新）
- CHANGELOG [Unreleased] 追記
- mypy strict 通過

---

## Developer 数の見立て（PM 環境制約込み）

- M サイズ（設計判断複数、新規ファイル 5-7、テスト 3+1+1）
- skill 規定では M = 2 Developer だが、PM 環境で Task/Agent 不在の制約あり（#3 / #4 で 2 回連続再現）
- → PM が 1 Developer + PMO を sequentially 代行する前提で PM 起動
- Contract 前提事項として Step 5 での sequential 代行をあらかじめ明記

---

## PM Alignment 結果（2026-04-24、1 往復で完結）

### PO 判断（確定事項）

| # | 論点 | PO 判断 | 根拠 |
|---|------|--------|------|
| E1 | `create_judge_handler` signature | **両対応** = 引数 `provider: LLMProviderPort \| None` + params 文字列解決 | 既存 `create_structured_llm_handler` の hybrid パターンと対称、DI テスト容易性と YAML UX 両立 |
| E2 | optional extra 名 | **`yagra[judge]`** | vision の「LLM-as-a-Judge」用語と一致、ユーザー可視名基準 |
| E3 | Port に `complete_text` も定義するか | **No（YAGNI）** | 初版は `complete_structured` のみ。段階移行時に後方互換を保って Port 拡張可能 |
| E4 | docs 追記場所 | **`docs/agent-integration-guide.md`** に追記 | 既存 MCP tool 連携の延長。`docs/sphinx/user_guide/llm_as_a_judge.md` は #27 で別途整備 |
| E5 | rubric の #24 との共通化 | **#24 Contract 作成時に再整合確認**。初版は柔軟な schema で実装 | 実装後に example を作って合わなければ revise |
| #2 | rubric→JSON Schema 変換粒度 | **最小**（PM 推奨採用） | criteria の list→object properties、`require_reasoning` で reasoning string 必須化 |
| #3 | async sync ブリッジ | **`asyncio.run` + 既に running loop 時は ThreadPoolExecutor** | `nest_asyncio` 依存追加を避ける。SC-3 に安全動作を明記 |
| #5 | CI で `claude_agent_sdk` install | **不要**（モックのみ） | テスト高速化。実走は #24/#26 E2E で確認 |
| 代替案 A | Port に `complete_text` 同時定義 | **不採用** | E3 と同理由（YAGNI） |
| 代替案 B | `resolve_provider()` Factory | **採用** | `adapters/outbound/llm_providers/__init__.py` に配置。SC-2c に反映済み |

### PM からの SC 追加要求（全て採用、Contract に反映済み）

- SC-2 を SC-2a/2b/2c に分解 ✓
- SC-3 に async 安全動作追補 ✓
- SC-5 の JSON Schema 厳密化（oneOf / enum / default） ✓
- SC-7 の unit test ケース追加（ImportError 形式、resolve_provider、async loop running） ✓
- SC-13 rubric 不正値検出 ✓
- SC-14 yagra validate 統合テスト ✓
- silent success 防止（rubric 0 件 fail-fast + 不正 output fail）を挙動仕様に明記 ✓

### 残未確定（PM 裁量）

- Protocol vs ABC for `LLMProviderPort`: **Protocol + `runtime_checkable`** 推奨（PM 裁量）
- `rubric_ref` の `path#key` 構文サポート: 初版は key 省略時 root 読込 OK（PM 裁量）
- `handlers/_llm_common.py` の prompt 補間ロジック再利用: 可能な範囲で再利用（PM 裁量）
