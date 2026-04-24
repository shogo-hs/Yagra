# PO-PM Task Contract: #28 既存 LLM handlers の LLMProviderPort 経由移行（ドラフト v1）

**タスク ID**: backlog #28
**作成日**: 2026-04-24
**Feature Branch**: `feature/handlers-port-migration`

---

## ビジョンコンテキスト（PO観点）

### このタスクの位置づけ

- Yagra ビジョンの差別化軸「AI が AI を評価・改善する」を支える基盤側タスク
- #23 で `LLMProviderPort` + `LiteLLMProvider` + `ClaudeAgentSDKProvider` + `resolve_provider` が整備されたが、**既存の 3 handlers (`create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler`) は今も `litellm.completion` を直接呼んでいる**
- 結果として、Hexagonal 境界は handler 層で破れており、`#5 最適化サイクル E2E 補強` で LLM 呼出を差し替えたいとき judge 以外は adapter 注入点がない

### 期待する成果

1. **Hexagonal 純度 +1**: `handlers/` 層が `litellm` に直接依存しなくなり、`ports/outbound/llm_provider.py` の抽象契約を通る
2. **#5 E2E の土台整備**: `litellm` テスト用 fake provider（または vcrpy 録画）を注入可能になり、propose→golden→apply の E2E を決定論的に実走できる準備が整う
3. **API 一貫性**: judge handler と同じ DI / `params["provider"]` hybrid signature を 3 handlers でも採用し、Yagra 全体で「provider 選択は `resolve_provider` に一元化」というルールを確立

### 優先度の根拠

- **Should**: Must のクイックウィン（#6）より構造改善寄与が大きいが、#5（Must）の前提として先行すべきと PO 判断
- ユーザー指示: 「Hexagonal 純度を先に上げて #5 の土台を整える」

### 品質・スコープ判断基準

- **妥協してよい点**:
  - `ClaudeAgentSDKProvider` の非構造化 `complete()` / `complete_streaming()` 実装は subset で可（未対応メソッドは `LLMProviderConfigError` を返す）。Claude Agent SDK は元々構造化応答寄りなので、text-only / streaming を優先対応する必要性は薄い
  - 既存の litellm-specific な token usage reporting（`report_token_usage` / `report_streaming_token_usage`）は adapter 側に移設しきらなくてよい（handler 層で token 情報を受け取れる仕組みを残せば段階的移行可能）
- **妥協してはいけない点**:
  - **既存 workflow YAML を変更不要にする**（backward compat。既存 examples / テストが無改修で通る）
  - **既存 946 件 + judge 29 件 = 975 件のテストが全通過**（handler 系の挙動変更は禁止）
  - **Hexagonal 境界違反を新規発生させない**（`handlers/` → `adapters/outbound/llm_providers/` への直接 import は禁止。`resolve_provider` 経由のみ）
  - **`params["provider"]` のセマンティクス**: judge では `"claude_agent_sdk"` / `"litellm"`（Yagra adapter 名）だが、llm / structured_llm / streaming_llm の既存 YAML には `model.provider` = `"openai"`（litellm 内部 provider 名）が入っている。この **2 レベルの provider 概念を混同させない設計**が必須

---

## 成功基準（案、PO ドラフト）

### SC-1: Port 拡張と adapter 実装
- `LLMProviderPort` に以下 2 メソッドを追加:
  - `complete(system_prompt, user_prompt, model, timeout, **kwargs) -> dict` （少なくとも `{"content": str, "usage": {...}}` を返す）
  - `complete_streaming(system_prompt, user_prompt, model, timeout, **kwargs) -> Iterator[str]`（または同等の Generator 返却契約）
- `LiteLLMProvider` が全 3 メソッドを実装
- `ClaudeAgentSDKProvider` は `complete_structured` のみ対応のまま、`complete` / `complete_streaming` は `LLMProviderConfigError` を返す（hint 付き構造化エラー）

### SC-2: handler 層の Port 経由化
- `create_llm_handler` が `resolve_provider(name)` 経由で provider を取得し、`provider.complete(...)` を呼ぶ
- `create_structured_llm_handler` が `provider.complete_structured(...)` を呼ぶ（schema を渡す）
- `create_streaming_llm_handler` が `provider.complete_streaming(...)` を呼ぶ
- いずれも **`import litellm` を削除**（handler モジュール内で litellm シンボルが出現しないこと）

### SC-3: backward compat（YAML 変更不要）
- 既存の `examples/llm-basic/workflow.yaml` / `examples/llm-structured/workflow.yaml` / `examples/llm-streaming/workflow.yaml` が一切変更なしで動作する
- `params["provider"]` 未指定時のデフォルトは `"litellm"`（`resolve_provider("litellm")` が返る）
- `params.model.provider` = `"openai"` 等（litellm 内部 provider 名）は現状通り `f"{provider}/{name}"` の形式で adapter に渡される

### SC-4: DI（hybrid signature）
- 3 handler factory が `provider: LLMProviderPort | None = None` を受け付ける（judge と同じ）
- DI > params の優先順位を固定（既存 judge の仕様と同一）
- 既存の `retry` / `timeout` 引数は維持

### SC-5: テスト全通過 + 新規テスト追加
- 既存テスト全通過: `tests/` 配下の 946 件 + judge 29 件 = 975 件（+ playwright 33 件は pre-existing skip）
- 各 handler に「DI 経路」と「`params["provider"]` 経路」の単体テストを最低 1 件ずつ追加（合計 6 件以上）
- `LiteLLMProvider.complete` / `complete_streaming` の単体テストを追加（mock `litellm.completion` で戻り値・streaming chunk を検証）

### SC-6: Hexagonal 境界の機械的検証
- `grep -r "import litellm" src/yagra/handlers/` の結果が空
- `grep -r "import litellm" src/yagra/adapters/outbound/llm_providers/` のみにヒット
- `grep -r "litellm\." src/yagra/handlers/` の結果が空（関数呼出レベル）

### SC-7: ドキュメント同期
- `docs/agent-integration-guide.md` の LLM handler セクションに `params.provider`（default `"litellm"`）の説明を追加
- 既存の 3 handler README（`examples/llm-basic/README.md` 等）は変更不要（YAML 不変なので）
- `CHANGELOG.md` の `[Unreleased]` に Changed / Added でエントリ追加

### SC-8: pre-commit 全通過
- `uv run pre-commit run --all-files` が All Passed
- `uv run pytest -q` が全 pass

### SC-9: schema 一貫性（軽微）
- 3 handler の `*_PARAMS_SCHEMA` に `provider` フィールドを追加（optional、default "litellm"）
- `yagra handlers --format json` 出力で 3 handler すべてに provider が表示される
- `JUDGE_HANDLER_PARAMS_SCHEMA` と同等のスキーマ構造に揃える

---

## In/Out スコープ

### In スコープ（今回やる）
- 上記 SC-1〜SC-9
- `LLMProviderPort` の拡張（`complete` / `complete_streaming` 追加）
- `LiteLLMProvider` への全 3 メソッド実装
- `ClaudeAgentSDKProvider` は既存機能維持 + 未対応メソッドの構造化エラー化
- 3 handler を `resolve_provider` 経由に書き換え
- 関連テスト追加
- ドキュメント（agent-integration-guide / CHANGELOG）更新

### Out スコープ（今回やらない）
- `ClaudeAgentSDKProvider` の `complete` / `complete_streaming` 実装（subset のまま）
- `fake provider` の実装（#5 で必要なら別タスク）
- token usage reporting の adapter 移設（次回リファクタ候補、別タスク）
- handler 層の `adapters/outbound/handlers/` 再配置（#14、別タスク）
- `_llm_common.py` の API 破壊的変更（引数追加は OK、削除は避ける）
- MCP / CLI 側の変更（provider 選択ロジックは handler 内部に留める）

---

## 設計上の未決事項（PM Alignment で確定したい）

### Q1: Port 拡張の形状
**方針 A（推奨）**: 単一 Port に 3 メソッド追加（`complete` / `complete_streaming` / `complete_structured`）
**方針 C**: Port を 3 つに分離（`TextLLMProviderPort` / `StreamingLLMProviderPort` / `StructuredLLMProviderPort`）

→ PM の判断: ISP 純粋性 vs 実装クラス増加のトレードオフ。推奨は A（単一 Port、Claude Agent SDK は subset）。

### Q2: `complete()` の戻り値形状
- 案 1: `str`（text content のみ）
- 案 2: `dict[str, Any]`（`{"content": str, "usage": {...}}` で token 情報を含む）
- 案 3: `NamedTuple` / `dataclass`（`LLMCompletion` 型を新設）

→ 案 2 を推奨（handler 側の token usage reporting を維持しやすい）。PM の判断求む。

### Q3: `complete_streaming()` の戻り値形状
- 案 1: `Iterator[str]`（chunk のみ yield）
- 案 2: `Iterator[dict]`（`{"content": str, "done": bool, "usage": ...}`）
- 案 3: Generator を返し、最後に `StopIteration` の value 属性で usage を返す（Python generator の return 機能活用）

→ 案 1 が実装シンプル。token usage はベストエフォート（現状も best-effort）。PM の判断求む。

### Q4: `params["provider"]` の検証タイミング
- 案 1: handler 関数実行時に `resolve_provider(params.get("provider", "litellm"))`
- 案 2: factory 生成時に provider を解決（but params ベースだと factory 時点では未解決）
- 案 3: DI > params の優先順位で、DI 指定があれば params.provider を無視（judge 仕様と同じ）

→ 案 3 を推奨（judge 仕様と完全同一）。

### Q5: ClaudeAgentSDKProvider が `complete` / `complete_streaming` を呼ばれたときのエラーコード
- 候補: `"not_implemented"` / `"provider_not_supported"` / `"feature_unavailable"`
- hint: `"Claude Agent SDK は構造化出力のみ対応。llm / streaming_llm handler で使う場合は provider: litellm を指定してください"`

→ PM の判断求む。

### Q6: 既存 handler のエラー階層
- 現状: `LLMHandlerError` / `LLMHandlerConfigError` / `LLMHandlerCallError`（handler 固有）
- judge: `JudgeHandlerError` / `JudgeHandlerConfigError` / `JudgeHandlerCallError`（judge 固有）
- Port: `LLMProviderError` / `LLMProviderConfigError` / `LLMProviderCallError`（provider 固有）
- Port 経由化後、handler は Port 例外をどう翻訳するか？

→ 案 A: judge と同じく「Port 例外を handler 例外にラップして再送出」
→ 案 B: Port 例外をそのまま上げる（handler 固有例外を廃止）
→ 案 A 推奨（backward compat、既存 test が `LLMHandlerCallError` を assert している可能性）。PM の判断求む。

### Q7: テスト再編の深度
- 案 1: 最小 — 既存 mock `litellm.completion` をそのまま維持、handler layer の test は既存のまま
- 案 2: 中 — 新規「Port 経由」テストを追加、既存 litellm 直呼び test は deprecate マーク
- 案 3: 深 — 全 handler test を `LLMProviderPort` mock ベースに書き直し

→ 案 2 を推奨（既存 test を壊さない、新規 test で Port 経路を検証）。PM の判断求む。

---

## 主要リスク

### リスク R1: 循環 import
- `_llm_common.py` → `llm_handler.py` の順で依存関係がある（`LLMHandlerCallError` を import）
- Port 経由化で `_llm_common.py` が `LLMProviderPort` を import する必要が出る可能性
- 対処: `_llm_common.py` の依存方向を確認、必要なら example-extract して循環を切る

### リスク R2: streaming の semantics
- 現状 `create_streaming_llm_handler` は `Generator[str, None, None]` を返すため、呼び出し側が for ループで消費する前に provider への参照が保たれる必要がある
- Port 経由で ClaudeAgentSDKProvider のように async bridge している場合、generator lifecycle が壊れないか要検証

### リスク R3: token usage の trace reporting
- `_llm_common.py` の `report_token_usage` / `report_streaming_token_usage` は `response.usage` を litellm 応答オブジェクトから取得する
- Port の `complete()` が `dict` を返す場合、usage 情報の構造を新たに定義する必要
- 対処: SC-1 で戻り値形状を決定（Q2）

### リスク R4: structured_llm の dynamic schema_yaml
- 現状 `create_structured_llm_handler` は `schema_yaml` から Pydantic model を動的生成し、`model.model_json_schema()` で JSON Schema を得て system prompt に埋め込む
- Port の `complete_structured` は `schema: dict` を受け取るので、handler 側で変換すれば OK
- ただし既存の litellm 直呼び test で `response_format={"type": "json_object"}` + system prompt に schema を埋める挙動があり、この 2 重フォーマット指定を adapter 側でどう吸収するか検討要

---

## 推奨アプローチ（PO ドラフト）

### 作業順序

1. **Port 拡張**: `LLMProviderPort` に `complete` / `complete_streaming` を追加
2. **LiteLLMProvider 拡張**: 2 メソッド実装 + 単体テスト
3. **ClaudeAgentSDKProvider 拡張**: 2 メソッド未対応エラー化 + 単体テスト
4. **handler リファクタリング**: 3 handlers を `resolve_provider` 経由に書き換え（`import litellm` 削除）
5. **テスト追加**: 各 handler に DI / params.provider の経路 test（6 件以上）
6. **schema 更新**: 3 handler の `*_PARAMS_SCHEMA` に `provider` フィールド追加
7. **ドキュメント**: agent-integration-guide + CHANGELOG
8. **pre-commit + 全テスト実行**

### 見積もり
- サイズ: **M**（ファイル変更数 ~8、新規テスト ~10 件、ドキュメント 2 箇所）
- 時間目安: 1-2 時間（PM 代行で sequential 実行）

---

## 次のアクション

1. 本 Brief ドラフトを PM Alignment Agent に渡して:
   - 理解確認（上記方針で齟齬ないか）
   - Q1-Q7 の回答
   - 追加のリスク / 懸念の提示
   - エスカレーション事項
2. PM Alignment 回答を反映して Brief v2 を作成 → Contract として確定
3. Phase 2c に進み PM Agent を起動

---

## 添付・参照

- ビジョン正本: `docs/product/vision.md`
- `LLMProviderPort`: `src/yagra/ports/outbound/llm_provider.py`
- `LiteLLMProvider`: `src/yagra/adapters/outbound/llm_providers/litellm_provider.py`
- `ClaudeAgentSDKProvider`: `src/yagra/adapters/outbound/llm_providers/claude_agent_sdk_provider.py`
- 既存 handlers: `src/yagra/handlers/llm_handler.py` / `structured_llm_handler.py` / `streaming_llm_handler.py` / `_llm_common.py`
- 既存 judge handler（参考実装）: `src/yagra/handlers/judge.py`
- 既存 examples（backward compat 対象）: `examples/llm-basic/` / `examples/llm-structured/` / `examples/llm-streaming/`
- 過去タスク learnings: `tasks/learnings.md`（#23 の Port/Adapter 設計パターン、hybrid signature、lazy SDK import、async bridge、sys.modules setdefault が参考）
