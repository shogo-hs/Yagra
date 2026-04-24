# Task Intent: #4 `_tool_apply_update` golden_pass_required オプション追加

**created:** 2026-04-24 11:49 JST
**slug:** apply-update-golden-gate
**size:** M
**contract:** `tasks/20260424114514_contract-po-pm-apply-update-golden-gate.md`

---

## Why

プロダクトビジョン `docs/product/vision.md` Phase 4「Approve & Update」の「Safe Iteration」思想を API レベルで担保する。ビジョン整合性監査で Major として検出された「`apply_update` が `run_golden_tests` 成功前提で動作していない」綻びを解消し、エージェントが意図せず golden 失敗状態で apply する事故を構造的に防ぐ。

- docs/agent-integration-guide.md:375 の「apply_update 前に必ず run_golden_tests を実行する」記述を API が強制するよう進化させる
- 続く #23 `create_judge_handler` の自己改善サイクル（propose → judge → golden → apply）の前提条件となる

## What

`src/yagra/adapters/inbound/mcp_server.py::_tool_apply_update` に以下 3 引数を追加する（Option C ハイブリッド設計）:

- `golden_pass_required: bool = True`（デフォルト ON）
- `last_golden_result: dict | None = None`（事前 run 結果の再利用）
- `golden_dir: str = ".yagra/golden"`（内部実行時の探索ディレクトリ）

### 挙動仕様（Contract 転記）

| 状況 | `golden_pass_required` | `last_golden_result` | 挙動 |
|------|:---:|:---:|------|
| 呼び出し側が事前 run_golden_tests 済み | True | dict あり | dict の `total == passed` で pass 判定 → pass なら apply、fail なら `error: "golden_not_passed"` |
| 呼び出し側が事前実行せず | True | None | 内部で `_tool_run_golden_tests(workflow_path, golden_dir)` を実行 → 同様に判定 |
| golden case 未定義（total=0） | True | どちらでも | warnings 付き apply 許可（`warnings: ["no_golden_cases_defined"]`）|
| backward-compat | False | - | 従来挙動（golden チェックなし）|

### 構造化エラーフォーマット（Contract 転記）

```json
{
  "error": "golden_not_passed",
  "message": "Golden tests did not fully pass: 2/3 passed, 1 failed",
  "summary": {"total": 3, "passed": 2, "failed": 1},
  "hint": "run_golden_tests の失敗ケースを確認し、candidate_yaml を修正してから再度 apply_update を実行してください"
}
```

**内部実行タイミング:** `save_workflow_with_backup` の**前**に golden チェック。失敗時は workflow ファイルを書き換えない。

## 成功基準（Contract 10 項目）

| # | 基準 | 検証コマンド |
|---|------|------------|
| 1 | `_tool_apply_update` に 3 引数追加（デフォルト値付き） | `uv run python -c "from yagra.adapters.inbound.mcp_server import _tool_apply_update; import inspect; print(inspect.signature(_tool_apply_update))"` |
| 2 | `golden_pass_required=True` かつ golden 未 pass 時、構造化エラー + 書込なし | 新規ユニットテスト（失敗ケース）で `error == "golden_not_passed"` と `summary` を assert、apply 前後でファイル内容同一 |
| 3 | golden case 未定義時 warnings 付き apply 許可 | 新規ユニットテスト（空 golden_dir）で `success: True` / `warnings: ["no_golden_cases_defined"]` |
| 4 | `golden_pass_required=False` で従来挙動 | 新規ユニットテスト backward-compat |
| 5 | MCP Pydantic スキーマ description 更新 | schema 文字列に `golden_pass_required` 言及あり |
| 6 | `docs/agent-integration-guide.md` 更新 | `grep -n "golden_pass_required" docs/agent-integration-guide.md` |
| 7 | `tests/unit/adapters/inbound/test_mcp_server.py` に 3 ケース以上追加 | `uv run pytest tests/unit/adapters/inbound/test_mcp_server.py -k golden_gate -v` |
| 8 | E2E 新デフォルトで pass | `uv run pytest tests/integration/test_optimization_cycle_e2e.py -v` |
| 9 | CHANGELOG.md `[Unreleased]` に追記 | `grep -n "golden_pass_required" CHANGELOG.md` |
| 10 | `uv run pre-commit run --all-files` 通過 | 同上 |

## In Scope

- `_tool_apply_update` シグネチャ + 実装変更
- private helper `_assert_golden_passed(...)` 抽出（mcp_server.py 内）
- `list_tools` デコレータ内の `apply_update` Tool inputSchema 更新（新引数の description 追加）
- `call_tool` ディスパッチャに新引数のパススルー追加
- `docs/agent-integration-guide.md:375` 周辺の記述更新
- 既存テスト更新 + 新規テスト追加（4 ケース以上）
- CHANGELOG.md `[Unreleased]` Changed / Fixed 追記

## Out of Scope

- `yagra apply` CLI 追加
- `allow_missing_golden` オプション（YAGNI）
- golden case 自動生成
- `propose_update` / `rollback_update` の変更
- #23 `create_judge_handler` 実装

## 設計判断メモ

- **Hexagonal 境界:** `_tool_apply_update` は既に同 adapter の `_tool_run_golden_tests` を呼んでよい（どちらも adapter 内 → application 経由）。新 use case 切り出しは YAGNI。
- **Pydantic Model 化の回避:** `last_golden_result` schema は「任意 dict」で受ける。内部で `total` / `passed` のみ参照する契約とする。
- **silent success 防止:** golden case 未定義時も必ず warnings を返す（PMO 指摘パターン学習で過去 #3 でも指摘された同系思想）。

---

## 次ステップ

1. Step 2: コードベース調査を PM 直接実施（Explore Agent 不在環境）
2. Step 3: 計画作成（Developer 数 = 1、PM 代行）
3. Step 4: Mission Brief 作成（本 Intent + Contract 挙動仕様を転記）
4. Step 5: Feature branch `feature/apply-update-golden-gate` + PM 代行 Developer
5. Step 6: PR 作成 + PM 代行 PMO レビュー
6. Step 7/8: 結果レポート
