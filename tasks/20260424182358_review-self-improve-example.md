# PMO Review: #24 `examples/self-improve/` walking example

**作成日**: 2026-04-24 18:23 JST
**担当**: PMO（PM 代行、agent-company-v2 制約下）
**対象 PR**: https://github.com/shogo-hs/Yagra/pull/51
**対象ブランチ**: `feature/add-self-improve-example`
**Contract**: `tasks/20260424180122_contract-po-pm-self-improve-example.md`
**Intent**: `tasks/20260424181320_intent-self-improve-example.md`
**Plan**: `tasks/20260424181320_plan-self-improve-example.md`
**Mission Brief**: `tasks/20260424181320_mission-brief-self-improve-example.md`

## 判定サマリ

**Accept（条件付き）**: DoD 14 項目中 13 項目 PASS、SC-14 のみ PM 環境制約で未実施。Critical / Major 問題 0 件。残課題は user 環境での実走確認のみで、コード品質 / 構造 / ドキュメントは基準を満たす。

## DoD 14 項目照合

| # | 基準 | 結果 | 根拠 |
|---|------|------|------|
| SC-1 | `yagra validate` が `is_valid: true`（error 0） | **PASS** | `uv run yagra validate --workflow examples/self-improve/workflow.yaml --bundle-root examples/self-improve --format json` で `is_valid: true` 確認。warning 3 件（`prompt_state_warning`）は既存 example 同水準 |
| SC-2 | `judge` ノードが inline rubric（2 criteria: clarity/accuracy、scale 1-5）、`prompt_ref` なし | **PASS** | `examples/self-improve/workflow.yaml` L19-31 で `rubric:` inline 宣言、`prompt_ref` キー存在せず、default system prompt 活用構成 |
| SC-3 | state に `judge_result` 格納、stdout で `_overall` 強調 | **PASS** | `run_example.py` L96-98 `">>> Overall score: {overall:.2f} <<<"` を明確に強調。output 構造は handler 実装通り `{score, reasoning, rubric_items}` |
| SC-4 | 4 ファイル構成、参考 `rubric.yaml` 不同梱 | **PASS** | `examples/self-improve/` 直下は `README.md` / `prompts.yaml` / `run_example.py` / `workflow.yaml` の 4 ファイルのみ |
| SC-5 | `generate` = OpenAI gpt-4o-mini / `judge` = claude_agent_sdk + sonnet | **PASS** | `workflow.yaml` L10-17（generate）と L19-21（judge）で仕様通り |
| SC-6 | README Prerequisites に `uv add "yagra[llm,judge]"` + `OPENAI_API_KEY` + `claude login` 明示 | **PASS** | `README.md` Prerequisites 節と Setup 節で 3 点全て記載 |
| SC-7 | README 5 ブロック（日本語主体） | **PASS** | README.md 構成: 概要 / Prerequisites + Setup / 実行 / 自己改善サイクル（擬似対話）/ Customization。全て日本語主体、コード文字列のみ英語 |
| SC-8 | 将来拡張として `evaluate_traces` 等 MCP tool 追加予定を 1-2 行（issue 番号書かない） | **PASS** | README.md「将来拡張」節で `evaluate_traces` 機能名のみ言及、`#25` 等の issue 番号なし |
| SC-9 | `validate-example.yml` で自動検証緑 | **PASS** | PR #51 の CI ジョブ `validate-examples`（ランID 24882177880）PASS 18s |
| SC-10 | CHANGELOG `[Unreleased]` Added に 1 行追記 | **PASS** | `CHANGELOG.md` L8 に追記、既存スタイル踏襲 |
| SC-11 | pre-commit 全通過 | **PASS** | `uv run pre-commit run --all-files` = ruff format / ruff check / mypy 全 PASS。PR #51 `quality` job（ランID 24882177846）PASS 2m0s |
| SC-12 | 既存テスト 1000 PASSED 維持 | **PASS** | `uv run pytest -q --ignore=tests/integration/test_studio_js_utils.py` = 1000 passed, 16 warnings, 26.59s。playwright 33 pre-existing 失敗は除外 |
| SC-13 | `src/` 変更なし | **PASS** | `git diff main...HEAD -- src/` 出力空 |
| SC-14 | 手動スモーク（draft / `_overall` / rubric_items 確認） | **未実施** | PM 環境に `OPENAI_API_KEY` なし。早期 exit 経路と import 成功は確認済。user 環境での実走確認を PO に依頼 |

**Pass: 13 / 14 / Blocked-on-Env: 1**

## 指摘レベル別

### Critical（Release blocker）: 0 件

該当なし。

### Major（Accept は可だが改善望ましい）: 0 件

該当なし。

### Minor（情報レベル）: 3 件

1. **M1**: Contract E6 の「日本語主体（既存 `examples/llm-structured/` 等と揃える）」と実際の `examples/llm-structured/README.md`（英語主体）が不一致。本 PR では `examples/llm-basic/` と同じ**日本語主体**を採用。PR body の判断記録に明記済み。将来的に既存 example 言語ポリシーの整理が望ましい
2. **M2**: pytest 並列実行時に 3 件 flaky（`test_run_mcp_server_calls_server_run` / `test_run_mcp_server_version_fallback` / `test_runs_inside_running_event_loop_via_executor`）。個別実行では全て PASS。本 PR とは無関係な pre-existing。学習ログへの記録は PO reporting phase で集約
3. **M3**: `prompt_state_warning` 3 件（state_schema 未定義）は info / warning 水準。既存 example と同水準のため放置可。将来 `state_schema` 明記の guideline を設ければ一括改善

## Hexagonal 境界チェック

- **src/ diff**: 空（`git diff main...HEAD -- src/` 実測）
- **example 配下のみ**: `examples/self-improve/` + `CHANGELOG.md` + `tasks/` 配下のみ
- **Port / Adapter 違反**: なし
- **結論**: Hexagonal 遵守

## コミット構造チェック

| Commit | Type | 50 文字以内 | 内容 |
|--------|------|-----------|------|
| 75c1ebd | docs(tasks) | OK | #24 自己改善 example 計画文書追加 |
| eb410c5 | feat(examples) | OK | self-improve walking example を追加 |
| 6022167 | docs(changelog) | OK | self-improve example 追記 |

Plan D-1 通りの 3 分割、全てプレフィックス付き、日本語 50 文字以内。

## CI ログ

- `validate-examples`: PASS 18s（https://github.com/shogo-hs/Yagra/actions/runs/24882177880/job/72853090301）
- `quality`: PASS 2m0s（https://github.com/shogo-hs/Yagra/actions/runs/24882177846/job/72853090169）

## 判定

**Accept**（手動スモーク 1 項目は user 環境での確認を PO に依頼）

- Critical / Major 0 件
- Minor 3 件は全て情報レベル（release blocker ではない）
- DoD 13/14 PASS + 1 Blocked-on-Env
- CI 2 job 全緑
- Hexagonal 境界遵守
- Contract Step 7 完了
