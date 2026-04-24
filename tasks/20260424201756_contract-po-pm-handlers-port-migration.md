# PO-PM Task Contract: #28 既存 LLM handlers の LLMProviderPort 経由移行（最終版 v2）

**タスク ID**: backlog #28
**作成日**: 2026-04-24（v1 18:09 → v2 20:17 JST）
**Feature Branch**: `feature/handlers-port-migration`
**Brief 版**: v2（PM Alignment Agent フィードバック反映版 / 本ファイルが Contract 正本）
**前版**: `tasks/20260424200943_contract-po-pm-handlers-port-migration.md`（ドラフト v1、Q1-Q7 未確定）

---

## Contract 変更履歴
- v1 → v2: PM Alignment Agent のレビュー結果を反映
  - 複雑度: M → **L**（3-5 時間、PO 裁量内で継続）
  - Q1: 単一 Port 拡張（方針 A）を確定
  - Q2: `dict` ではなく **dataclass `LLMCompletion`** を採用（PM 推奨）
  - Q3: `Iterator[str]` ではなく **`Iterator[LLMStreamChunk]`** を採用（PM 推奨、公開 API は `Generator[str, None, None]` 維持）
  - E1-1 / E1-2 / E1-3: すべて **Accept**（Port 層純度向上に必要）
  - SC-1〜SC-9（v1）に加え SC-10〜SC-16 を新設

---

## ビジョンコンテキスト（PO観点）

### このタスクの位置づけ

- Yagra ビジョン差別化軸「AI が AI を評価・改善する」を支える基盤側タスク
- #23 で `LLMProviderPort` + `LiteLLMProvider` + `ClaudeAgentSDKProvider` + `resolve_provider` が整備されたが、既存 3 handlers（`create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler`）は今も `litellm.completion` を直接呼んでおり Hexagonal 境界が破れている
- `#5 最適化サイクル E2E 補強` で LLM 呼出を fake provider / vcrpy 録画に差し替えたいとき、judge 以外は adapter 注入点がない

### 期待する成果

1. **Hexagonal 純度 +1**: `handlers/` 層が `litellm` に直接依存しなくなる。`ports/outbound/llm_provider.py` の抽象契約を全 handler が通る
2. **#5 E2E の土台整備**: fake provider / vcrpy を注入可能になり、propose→golden→apply の E2E を決定論的に実走できる準備が整う
3. **API 一貫性**: judge handler と同じ DI / `params["provider"]` hybrid signature を 3 handlers で採用し、「provider 選択は `resolve_provider` 一元化」ルールを確立
4. **Port 契約の表現力向上**: dataclass 戻り値で token usage 情報が loss-less に handler へ到達し、token trace reporting が継続する

### 優先度の根拠

- **Should**（backlog #28 記載通り）
- ユーザー指示: 「Hexagonal 純度を先に上げて #5 の土台を整える」
- Must タスク #5 の前提として先行実施

### 品質・スコープ判断基準

- **妥協してよい点**:
  - `ClaudeAgentSDKProvider` の `complete()` / `complete_streaming()` は `LLMProviderConfigError` を返す subset 対応で可（Claude Agent SDK は構造化応答寄り）
  - token usage reporting は best-effort 維持（streaming は chunk から組み立てる厳密版にしなくて可）
- **妥協してはいけない点**:
  - **既存 workflow YAML を変更不要にする**（backward compat、既存 examples / テスト無改修で通る）
  - **全既存テスト（946 件 + judge 29 件 = 975 件）が継続 PASS**
  - **Hexagonal 境界違反を新規発生させない**（`handlers/` → `adapters/outbound/llm_providers/` への直接 import 禁止、`resolve_provider` 経由のみ）
  - **`params["provider"]` と `params.model.provider` の 2 レベル provider 概念を混同させない設計**
  - **`ports/outbound/llm_provider.py` に具象 SDK を import しない**（dataclass のみ pure Python で追加）

---

## 成功基準（確定版）

### SC-1: Port 拡張と adapter 実装
- `LLMProviderPort` Protocol に 2 メソッドを追加:
  - `complete(system_prompt, user_prompt, model, timeout=30, **kwargs) -> LLMCompletion`
  - `complete_streaming(system_prompt, user_prompt, model, timeout=30, **kwargs) -> Iterator[LLMStreamChunk]`
- 既存の `complete_structured` は現状維持（戻り値 `dict[str, Any]`）
- `LiteLLMProvider` が全 3 メソッドを実装
- `ClaudeAgentSDKProvider` は `complete_structured` のみ対応維持、`complete` / `complete_streaming` は `LLMProviderConfigError` を返す（hint 付き構造化エラー）

### SC-2: handler 層の Port 経由化
- `create_llm_handler` が `resolve_provider(...)` 経由で provider を取得し `provider.complete(...)` を呼ぶ
- `create_structured_llm_handler` が `provider.complete_structured(...)` を呼ぶ（schema を JSON Schema dict で渡す）
- `create_streaming_llm_handler` が `provider.complete_streaming(...)` を呼ぶ
- 3 ファイルすべてで **`import litellm` を削除**、`litellm.` の関数呼出もゼロ

### SC-3: backward compat（YAML 変更不要）
- `examples/llm-basic/workflow.yaml` / `examples/llm-structured/workflow.yaml` / `examples/llm-streaming/workflow.yaml` が一切変更なしで動作
- `params["provider"]` 未指定時のデフォルトは `"litellm"`（`resolve_provider("litellm")`）
- `params.model.provider` = `"openai"` 等（litellm 内部 provider 名）は現状通り `f"{provider}/{name}"` で adapter に渡される
- streaming handler の公開戻り値型は **`Generator[str, None, None]` を維持**（内部で `LLMStreamChunk.delta` を yield に変換）

### SC-4: DI（hybrid signature）
- 3 handler factory が `provider: LLMProviderPort | None = None` を受け付ける（judge と同じ）
- DI > `params["provider"]` の優先順位を固定
- 既存の `retry` / `timeout` 引数は維持

### SC-5: 既存テスト全通過 + 新規テスト追加
- 既存 946 件 + judge 29 件 = **975 件すべて継続 PASS**（playwright 33 件は pre-existing skip）
- 各 handler に「DI 経路」「`params["provider"]` 経路」の単体テストを最低 1 件ずつ追加（合計 6 件以上）
- `LiteLLMProvider.complete` / `complete_streaming` の単体テストを追加（mock `litellm.completion` で chunks / usage を検証）
- `ClaudeAgentSDKProvider` が `complete` / `complete_streaming` で `LLMProviderConfigError` を投げる assert を追加

### SC-6: Hexagonal 境界の機械的検証
- `grep -r "import litellm" src/yagra/handlers/` の結果が空
- `grep -r "litellm\." src/yagra/handlers/` の結果が空
- `import litellm` がヒットする `src/` 配下のファイルが `src/yagra/adapters/outbound/llm_providers/litellm_provider.py` のみ
- `src/yagra/ports/outbound/llm_provider.py` に `litellm` / `claude_agent_sdk` の import がない（dataclass は pure Python のみで構成）

### SC-7: ドキュメント同期
- `docs/agent-integration-guide.md` の LLM handler セクションに:
  - `params.provider`（default `"litellm"`、候補 `"claude_agent_sdk"`）の説明
  - judge と同じ 2 レベル provider 概念の注記（adapter 名 vs litellm 内部 provider 名）
- `CHANGELOG.md` の `[Unreleased]` に Changed / Added エントリ追加（Keep a Changelog 形式）

### SC-8: pre-commit 全通過
- `uv run pre-commit run --all-files` が All Passed（ruff format / ruff check / mypy）
- `uv run pytest -q` が全 pass（975 件 + 新規 ≥6 件）

### SC-9: schema 一貫性
- 3 handler の `*_PARAMS_SCHEMA` に `provider` フィールド追加（optional、default `"litellm"`、enum `["litellm", "claude_agent_sdk"]`）
- `yagra handlers --format json` 出力で 3 handler すべてに provider が表示される
- `JUDGE_HANDLER_PARAMS_SCHEMA` と同等のスキーマ構造に揃える

### SC-10: Port 層 dataclass 追加（PM Alignment 反映 / E1-1）
- `src/yagra/ports/outbound/llm_provider.py` に以下 3 dataclass を追加:
  - `@dataclass(frozen=True, slots=True) LLMTokenUsage(prompt_tokens: int, completion_tokens: int, total_tokens: int)`
  - `@dataclass(frozen=True, slots=True) LLMCompletion(content: str, usage: LLMTokenUsage | None = None, raw: dict[str, Any] | None = None)`
  - `@dataclass(frozen=True, slots=True) LLMStreamChunk(delta: str, done: bool = False, usage: LLMTokenUsage | None = None)`
- いずれも pure Python（SDK import 禁止）。`raw` は adapter が provider-native レスポンスを格納する optional フィールド（handler 層が参照する必要はないが観測可能性のため残す）
- 対応する単体テストを `tests/unit/ports/` または `tests/unit/adapters/llm_providers/` に追加（dataclass 構築 + 等価性の smoke test で可）

### SC-11: handlers/errors.py 新設（PM Alignment 反映 / E1-3）
- `src/yagra/handlers/errors.py` を新設し、`LLMHandlerError` / `LLMHandlerConfigError` / `LLMHandlerCallError` を移植
- 既存 `src/yagra/handlers/llm_handler.py` / `structured_llm_handler.py` / `streaming_llm_handler.py` / `_llm_common.py` が `yagra.handlers.errors` から import するように書き換え
- 互換性のため `llm_handler.py` は `from yagra.handlers.errors import ...` + `__all__` 再 export を残す（既存テストの `from yagra.handlers.llm_handler import LLMHandlerCallError` が壊れないため）
- 循環 import が検出されないこと（`python -c "import yagra.handlers"` が成功し `_llm_common.py` → `llm_handler.py` の矢印が消える）

### SC-12: token usage reporting の Port 経由化
- `_llm_common.py` の `report_token_usage` / `report_streaming_token_usage` を、litellm-native `response.usage` ではなく **`LLMTokenUsage` dataclass** を受け取る形に書き換える
- 既存のシグネチャは別関数名（例: `report_completion_usage(usage: LLMTokenUsage | None, litellm_model: str, provider: str)` ）として新規追加し、litellm 直呼びバージョンは削除する
- streaming の report は `LLMStreamChunk.usage` が得られた最後のチャンクから反映する（best-effort）

### SC-13: テスト mock 対象の書き換え（PM Alignment 反映 / E2-2）
- 既存 `patch("yagra.handlers.llm_handler.litellm")` / `patch("yagra.handlers.structured_llm_handler.litellm")` / `patch("yagra.handlers.streaming_llm_handler.litellm")` を含むテストは、 `litellm` import 削除に合わせて mock 対象を更新:
  - 新方針: `LLMProviderPort` の fake 実装（`Fake...Provider` 等）を DI で注入する、または `patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm")` にシフト
- 影響箇所は事前調査で grep 済み。新規発生する書き換え数が多い場合でも SC-5 の「既存 975 件 PASS」を最優先する

### SC-14: mypy strict 維持
- `mypy --strict`（または既存 `mypy` 設定）で Port / adapter / handler すべて型エラーゼロ
- dataclass 引数型、`Iterator[LLMStreamChunk]`、`LLMCompletion` の戻り値アノテーションが一貫している

### SC-15: streaming 仕様の公開 API 不変 + 内部 contract 一貫性
- `create_streaming_llm_handler` が返す state value の型は **`Generator[str, None, None]`** を維持（既存 README / example が利用）
- 内部で `LLMStreamChunk` を `delta` 文字列に unwrap する変換層（`_yield_stream_text(chunks: Iterator[LLMStreamChunk]) -> Generator[str, None, None]`）を `_llm_common.py` に追加
- `LLMStreamChunk.done=True` または `usage is not None` の chunk で最終 token usage を report し、`delta` が空の terminal chunk は yield しない

### SC-16: params.provider のバリデーションとエラーメッセージ
- `params["provider"]` が `resolve_provider` で解決できない場合、`LLMHandlerConfigError` を hint 付きで送出（例: `"Unknown provider '<name>'. Available: litellm, claude_agent_sdk. Install 'yagra[judge]' for claude_agent_sdk."`）
- hint のテキストは judge の同種エラーと文言統一

---

## In/Out スコープ

### In スコープ（今回やる）
- SC-1〜SC-16 すべて
- `LLMProviderPort` に `complete` / `complete_streaming` メソッド追加（`complete_structured` は現状維持）
- `LLMCompletion` / `LLMStreamChunk` / `LLMTokenUsage` dataclass を `ports/outbound/llm_provider.py` に追加
- `LiteLLMProvider` に `complete` / `complete_streaming` 実装
- `ClaudeAgentSDKProvider` は `complete` / `complete_streaming` で `LLMProviderConfigError` を返す subset 対応
- 3 handler を `resolve_provider` 経由に書き換え（`import litellm` 削除）
- `handlers/errors.py` 新設 + `_llm_common.py` の依存グラフ整流化
- 3 handler の `*_PARAMS_SCHEMA` に provider 追加
- 既存テストの mock 対象書き換え + 新規 Port/handler テスト 6 件以上
- `docs/agent-integration-guide.md` / `CHANGELOG.md` 更新

### Out スコープ（今回やらない）
- `ClaudeAgentSDKProvider` の `complete` / `complete_streaming` 実装（将来別タスク）
- `fake provider` 実装（#5 で必要なら別タスク）
- token usage reporting の adapter 層への完全移設（今回は Port dataclass 経由で手当て）
- handler の `adapters/outbound/handlers/` 再配置（#14 別タスク）
- `_llm_common.py` の API 破壊的変更（引数追加 OK、既存関数削除は避ける）
- MCP / CLI 側の変更（provider 選択は handler 内部に留める）
- `complete_structured` の戻り型 dataclass 化（#23 との互換性維持のため後回し）

---

## 主要リスク（PM Alignment の C1-C7 も統合）

### R1: 循環 import（v1 R1 踏襲）
- `_llm_common.py` → `llm_handler.py` の現行依存方向を **SC-11** で `handlers/errors.py` 新設により解消
- 検証: `python -c "import yagra.handlers"` が一発で成功

### R2: streaming semantics（v1 R2 踏襲）
- `LLMStreamChunk` を挟む設計により、chunk lifecycle が provider / handler 両方で明示される
- 既存の `Generator[str, None, None]` 公開 API は `_yield_stream_text` で維持（SC-15）
- LiteLLMProvider の `stream=True` 呼出で `complete_streaming` が StopIteration value で usage を返せない litellm の制約がある場合、best-effort 対応（terminal chunk に `usage` を埋める or None）

### R3: token usage の trace reporting（v1 R3 踏襲）
- `LLMTokenUsage` dataclass で構造を固定（SC-10）
- `report_completion_usage(usage: LLMTokenUsage | None, ...)` 新関数で既存仕様と互換
- streaming は best-effort 継続

### R4: structured_llm の dynamic schema_yaml + 2 重フォーマット指定（v1 R4 踏襲）
- 現行の `response_format={"type": "json_object"}` + system prompt 埋込の 2 重指定は `LiteLLMProvider.complete_structured` 側にそのまま維持（#23 の挙動を壊さない）
- handler 側は `schema_yaml` → Pydantic model → `model_json_schema()` → dict を provider に渡すのみ

### R5: 既存テストの mock 書換え規模（PM C1 相当）
- `litellm` を直接 patch しているテストが相当数存在（PM 調査で 83 件前後見込み）
- 書換え規模が大きいため、**PM は Step 0 で grep して正確な件数を見積り、SC-13 を満たす最小変更を優先**
- 影響範囲と書換え方針を PM Intent に明記

### R6: Claude Agent SDK subset の互換性（PM C2 相当）
- judge handler は既に `complete_structured` のみを利用しているため、subset 維持で破壊しない
- subset エラーは **hint 文言を SC-16 と統一**（ユーザー体験ブレ防止）

### R7: mypy strict 通過 + dataclass 引数順（PM C5 相当）
- `LLMStreamChunk(delta: str, done: bool = False, usage: LLMTokenUsage | None = None)` のように default 引数は必ず末尾
- `Iterator[LLMStreamChunk]` は `from collections.abc import Iterator` を使用
- `mypy` 設定で `disallow_untyped_defs = True` の場合、新規関数にすべて annotation を付与

---

## PO 判断事項（E1-1〜E1-3 / E2-1〜E2-2 に対する回答）

| 番号 | PM 提案内容 | PO 判断 |
|-----|------------|--------|
| E1-1 | `LLMCompletion` / `LLMStreamChunk` / `LLMTokenUsage` dataclass を Port 層に追加 | **Accept** — architecture.md 準拠（pure Python、SDK 非依存）、Port 契約の表現力向上、token usage を loss-less に渡せる利点が大きい |
| E1-2 | streaming 内部契約を `Iterator[LLMStreamChunk]` に変更（公開 API は `Generator[str, None, None]` 維持） | **Accept** — 既存ユーザーには無影響、内部 contract が token usage を乗せられる |
| E1-3 | `handlers/errors.py` 新設で error 階層を一元化、`_llm_common.py` の循環依存を断つ | **Accept** — SC-11 として明示、再 export で既存 import path を温存 |
| E2-1 | 複雑度 M → L に再見積もり（3-5 時間） | **Accept（PO 裁量）** — backlog Should レベルで 3-5 時間は許容範囲、ユーザーエスカレーション不要 |
| E2-2 | テスト書換え 83 件 + 新規 15 件程度 | **Accept** — SC-13 で明示。ただし PM は Step 0 で最新の件数を grep して Intent に記録 |

---

## 採用アプローチ（PM Alignment 反映版）

### 作業順序（8 フェーズ、推定 ~305 分 = 約 5 時間）

| Phase | 内容 | 推定時間 |
|-------|------|---------|
| **A** | Port 拡張: `LLMCompletion` / `LLMStreamChunk` / `LLMTokenUsage` dataclass + `complete` / `complete_streaming` Protocol 追加 + 単体 smoke test | 25 分 |
| **B** | `handlers/errors.py` 新設 + 既存 error class の移植と再 export + 循環 import 解消の smoke 検証 | 25 分 |
| **C** | `LiteLLMProvider.complete` / `complete_streaming` 実装 + 単体テスト（chunk 分解、token usage、timeout、error 変換） | 50 分 |
| **D** | `ClaudeAgentSDKProvider` の `complete` / `complete_streaming` を `LLMProviderConfigError` で return する subset 対応 + テスト | 15 分 |
| **E** | 3 handler を `resolve_provider` 経由に書換え（`import litellm` 削除、hybrid signature 追加、`_llm_common.py` の report 関数書換え）| 60 分 |
| **F** | 既存テスト mock 書換え（litellm patch → Port fake / adapter-level patch）+ 新規 handler テスト 6 件以上 + schema 一貫性テスト | 70 分 |
| **G** | `*_PARAMS_SCHEMA` に `provider` 追加 / `yagra handlers --format json` 確認 / `docs/agent-integration-guide.md` / `CHANGELOG.md` 更新 | 35 分 |
| **H** | `uv run pre-commit run --all-files` + `uv run pytest -q` + grep 境界チェック（SC-6）+ PR 作成 | 25 分 |

### 見積もり（確定）
- サイズ: **L**
- 時間目安: 3-5 時間（PM 代行で sequential 実行、5 回目再現予定）
- 変更ファイル数: ~14（新規 2 + 更新 12）
- 新規テスト: 最低 15 件（Port smoke 3 + LiteLLMProvider 6 + handler DI/params 6）

---

## 次のアクション（Phase 2c）

1. 本 Contract v2 を Contract 正本として確定
2. PM Agent を起動（Phase 2c）:
   - PO-PM Task Contract（本ファイル全文）
   - プロダクトビジョン
   - プロジェクト規約（architecture.md / SOLID / Hexagonal rule 含む）
   - 過去タスクからの学習（#23 の Port/Adapter 設計パターン、hybrid signature、lazy SDK import、async bridge、sys.modules setdefault、#24 の docstring backslash D301、structured error 4 フィールド、walking example bug）
3. PM Agent が Intent / Plan / Mission Brief / 実装 / PR / PMO レビューを sequential に代行
4. PO 検証（Phase 2d）でビジョン整合性スコア更新 → Phase 2e PR merge 待機 → Phase 2f knowledge 蓄積

---

## 添付・参照

- ビジョン正本: `docs/product/vision.md`
- Architecture rules: `.claude/rules/architecture.md`（`ports/` に SDK import 禁止、dataclass は pure Python のみ）
- `LLMProviderPort`: `src/yagra/ports/outbound/llm_provider.py`
- `LiteLLMProvider`: `src/yagra/adapters/outbound/llm_providers/litellm_provider.py`
- `ClaudeAgentSDKProvider`: `src/yagra/adapters/outbound/llm_providers/claude_agent_sdk_provider.py`
- 既存 handlers: `src/yagra/handlers/llm_handler.py` / `structured_llm_handler.py` / `streaming_llm_handler.py` / `_llm_common.py`
- 既存 judge handler（参考実装）: `src/yagra/handlers/judge.py`
- 既存 examples（backward compat 対象）: `examples/llm-basic/` / `examples/llm-structured/` / `examples/llm-streaming/`
- 過去タスク learnings: `tasks/learnings.md`（#23 の Port/Adapter 設計、hybrid signature、lazy SDK import、async bridge、sys.modules setdefault、#24 の docstring D301、structured error 4 フィールド、walking example bug）
- ドラフト v1: `tasks/20260424200943_contract-po-pm-handlers-port-migration.md`
