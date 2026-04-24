# Intent: #24 `examples/self-improve/` walking example

**作成日**: 2026-04-24 18:13 JST
**担当**: PM (agent-company-v2 - Developer/PMO sequentially 代行)
**対応バックログ**: #24 Must
**Contract**: `tasks/20260424180122_contract-po-pm-self-improve-example.md`

## ゴール

Yagra の差別化軸「AI が AI を評価」を体感できる walking example を `examples/self-improve/` に実装する。
`generate`（LiteLLM openai gpt-4o-mini）→ `judge`（claude_agent_sdk sonnet + inline rubric）の 2 ノード最小構成で、
`judge_result` の output 構造（`{score: {clarity, accuracy, _overall}, reasoning, rubric_items}`）が stdout から読み取れる状態にする。

## In スコープ

- `examples/self-improve/` 新規 4 ファイル: `workflow.yaml` / `prompts.yaml` / `run_example.py` / `README.md`
- `CHANGELOG.md` `[Unreleased]` Added に 1 行追記
- `tasks/` 配下の Intent / Plan / Mission Brief / PMO Review 4 文書
- 未コミットの PO tracking 更新 4 ファイル（初期コミットで取り込み）

## Out スコープ

- `src/yagra/` 変更（Hexagonal 境界遵守 = SC-13）
- 参考 `rubric.yaml` 同梱（Contract E2 で不採用確定）
- judge 用 `prompts.yaml` セクション（Contract E7 で default system prompt 活用確定）
- MCP tool `evaluate_traces` / docs/sphinx の LLM-as-a-Judge 節（#25/#26/#27 別タスク）
- propose → judge → apply の E2E 自動テスト（#26 別タスク）
- LLM を CI で実走させる変更（SC-9 既存方針維持）

## 成功基準（SC-1〜SC-14、Contract 確定版転記）

### 2.1 Workflow / Example 構造

- **SC-1**: `examples/self-improve/workflow.yaml` が `generate` → `judge` の 2 ノード workflow で、`yagra validate --workflow examples/self-improve/workflow.yaml --bundle-root examples/self-improve` が `is_valid: true`（error 0）
- **SC-2**: `judge` ノードが **inline rubric**（2 criteria: `clarity`, `accuracy` 各 `scale: {min: 1, max: 5}`）で構成され、`prompt_ref` を指定せず default system prompt を活用
- **SC-3**: 実行結果の state に `judge_result` があり、中身が `{score: {<c1>: int, <c2>: int, _overall: float}, reasoning: str, rubric_items: list}`。`run_example.py` の stdout で `score._overall` を強調表示

### 2.2 ファイル構成・認証・依存

- **SC-4**: 4 ファイル構成（既存 example と揃える）
- **SC-5**: `generate` = OpenAI `gpt-4o-mini` (`OPENAI_API_KEY` 要求) / `judge` = `claude_agent_sdk` + `sonnet` (`claude login` 要求)
- **SC-6**: README Prerequisites に `uv add "yagra[llm,judge]"` + `OPENAI_API_KEY` + `claude login` の両方必要を明示
- **SC-7**: README 5 ブロック日本語主体（概要／Prerequisites／実行手順／Propose-Judge-Apply 擬似対話／Customization）
- **SC-8**: README (d) に将来拡張として `evaluate_traces` 等 MCP tool 追加予定を 1-2 行（**issue 番号書かない**）

### 2.3 CI・品質ゲート

- **SC-9**: `validate-example.yml` が self-improve を自動検出し緑（glob `examples/*/workflow.yaml`）
- **SC-10**: `CHANGELOG.md` `[Unreleased]` Added に 1 行追記
- **SC-11**: `uv run pre-commit run --all-files` 全通過（ruff format / ruff check / mypy）
- **SC-12**: 既存テストスイートを壊さない（1000 PASSED 維持、playwright 除外）
- **SC-13**: `src/` 変更なし（Hexagonal 境界遵守）

### 2.4 手動スモーク

- **SC-14**: `claude login` + `OPENAI_API_KEY` の環境で `python run_example.py` 実走 → 終了コード 0 / draft / `_overall` / `rubric_items` 確認

## Step 1 dry-run 結果

- 試験用 workflow.yaml を `/tmp/yagra-dryrun/self-improve/` に作成し `uv run yagra validate` 実行
- 結果: `is_valid: true`、warning は `prompt_state_warning`（state_schema 未定義の info/warning、既存 example と同水準）
- **R3（validate-example CI で example 自動検出）**: glob 合致 OK
- **R4（`yagra[judge]` extra の CI 可用性）**: judge extra 不在でも handler を実 import せず schema のみ検証され validate 通過を確認

## リスクと対策

| Risk | 対策 |
|------|------|
| SC-14 手動スモーク実行不可（`OPENAI_API_KEY` 未設定） | 完了レポートで「スモーク未実施、CI validate で schema 確認済み、ユーザー環境実走は user まかせ」を PO にエスカレーション |
| `sonnet` alias 変更 | README に「フルモデル ID 差し替え可」1 行記述（Contract R2） |
| `prompt_state_warning` が error 扱いされる | validate-example CI は `is_valid` のみ判定。warning は緑通過に影響しない既存仕様 |

## PM 代行工程

Contract Section 7 Step 4 以降、Developer 代行 → Quality Gate → PMO 代行の順に sequentially 実行。
ロール境界は出力で明示（「--- Developer 工程 ---」「--- PMO 工程 ---」）。
