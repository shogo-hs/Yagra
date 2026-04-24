# 実装計画: #4 `_tool_apply_update` golden_pass_required オプション追加

**created:** 2026-04-24 11:50 JST
**intent:** `tasks/20260424114909_intent-apply-update-golden-gate.md`
**contract:** `tasks/20260424114514_contract-po-pm-apply-update-golden-gate.md`

---

## ゴールの再確認

`_tool_apply_update` を「golden test 通過」を前提とした API に進化させる。Option C ハイブリッド（`last_golden_result` 受領 or 未指定時は内部で `_tool_run_golden_tests` を実行）で実現。デフォルト ON（`golden_pass_required=True`）、golden case 未定義時は warnings 付きで apply 許可（silent success 防止）。

## Developer 数の決定

- タスクサイズ: **M**（設計判断あり、複数ファイル、Hexagonal 低リスク）
- skill V2 規定では Developer 3 名だが、PM 環境制約（Task/Agent ツール不在）により圧縮:
  - **Developer 1（PM 代行）**: 実装 + テスト + ドキュメント + CHANGELOG 全てを担当
  - **PMO 代行**: PM 自身がレビューする
- Contract の付記通りの運用

## 変更ファイル（5 ファイル想定）

| # | ファイル | 変更内容 |
|---|---------|---------|
| 1 | `src/yagra/adapters/inbound/mcp_server.py` | `_tool_apply_update` に 3 引数追加。private helper `_assert_golden_passed(...)` 抽出。`list_tools` の Tool inputSchema 更新（新引数 description 追加）。`call_tool` ディスパッチャに新引数パススルー追加 |
| 2 | `tests/unit/adapters/inbound/test_mcp_server.py` | golden_gate 系のテスト 5 ケース追加（pass / fail / no-case warning / opt-out / schema description） |
| 3 | `tests/integration/test_optimization_cycle_e2e.py` | 既存 E2E は golden case 未定義なので、新デフォルト `True` のもとで warnings 付き apply が通ることを assert 追加。意図コメントも追加 |
| 4 | `docs/agent-integration-guide.md` | L375 周辺「必ず run_golden_tests を実行する」記述を「デフォルトで強制される」に更新。warnings 仕様を追記 |
| 5 | `CHANGELOG.md` | `[Unreleased]` に `### Changed` + `### Fixed` 追記 |

## 実装スケッチ（PM 代行 Developer 向け）

### `_assert_golden_passed(...)` helper

```python
def _assert_golden_passed(
    workflow_path: str,
    golden_dir: str,
    last_golden_result: dict[str, Any] | None,
) -> tuple[bool, dict[str, Any] | None, list[str]]:
    """Helper: run golden tests or reuse cached result, then judge pass.

    Returns:
        (passed, error_payload, warnings)
        - passed == True かつ error_payload is None → apply 続行
        - passed == False かつ error_payload is not None → 呼出元で return する
        - warnings は常に list（空可）
    """
    # 1) last_golden_result が渡されているか判定
    if last_golden_result is not None:
        result = last_golden_result
    else:
        result = _tool_run_golden_tests(
            workflow_path=workflow_path,
            golden_dir=golden_dir,
            case_name=None,
            fmt="json",
        )
        # _tool_run_golden_tests エラーをそのまま returnable payload にする
        if "error" in result:
            return False, {
                "error": "golden_check_failed",
                "message": f"Failed to run golden tests: {result.get('message', result['error'])}",
                "hint": "golden_dir を確認するか、golden_pass_required=False で明示的にスキップしてください",
            }, []

    total = int(result.get("total", 0))
    passed_count = int(result.get("passed", 0))
    failed_count = int(result.get("failed", total - passed_count))

    # 2) golden case 未定義（total=0）→ warning 付き pass
    if total == 0:
        return True, None, ["no_golden_cases_defined"]

    # 3) passed == total なら pass
    if passed_count == total and failed_count == 0:
        return True, None, []

    # 4) それ以外は構造化エラー
    return False, {
        "error": "golden_not_passed",
        "message": f"Golden tests did not fully pass: {passed_count}/{total} passed, {failed_count} failed",
        "summary": {"total": total, "passed": passed_count, "failed": failed_count},
        "hint": "run_golden_tests の失敗ケースを確認し、candidate_yaml を修正してから再度 apply_update を実行してください",
    }, []
```

### `_tool_apply_update` 改修

```python
def _tool_apply_update(
    workflow_path: str,
    candidate_yaml: str,
    base_revision: str | None = None,
    backup_dir: str = ".yagra/backups",
    golden_pass_required: bool = True,
    last_golden_result: dict[str, Any] | None = None,
    golden_dir: str = ".yagra/golden",
) -> dict[str, Any]:
    # ... 既存の YAML parse / 存在確認 / base_revision ロジック ...

    # 新規: golden チェック（save_workflow_with_backup より前）
    warnings_list: list[str] = []
    if golden_pass_required:
        # workflow_path はまだ書き換えていないので resolved をそのまま使える
        passed, error_payload, warns = _assert_golden_passed(
            workflow_path=str(resolved),
            golden_dir=golden_dir,
            last_golden_result=last_golden_result,
        )
        if not passed and error_payload is not None:
            return error_payload
        warnings_list.extend(warns)

    # 既存の save_workflow_with_backup 呼び出しと同じ
    # ...

    response: dict[str, Any] = {
        "success": True,
        "workflow_path": str(resolved),
        "backup_id": result.backup_id,
        "saved_revision": result.saved_revision,
    }
    if warnings_list:
        response["warnings"] = warnings_list
    return response
```

### `list_tools` の description 更新ポイント

- `apply_update` ツールの description に「By default, requires golden tests to pass before apply」を追記
- inputSchema.properties に以下を追加:
  - `golden_pass_required` (boolean, default true): description に挙動説明
  - `last_golden_result` (object): description に「run_golden_tests の戻り値をそのまま渡す。未指定時は内部で実行」
  - `golden_dir` (string, default `.yagra/golden`): description に「golden case の探索ディレクトリ」

### `call_tool` ディスパッチャ

```python
elif name == "apply_update":
    result = _tool_apply_update(
        workflow_path=arguments.get("workflow_path", ""),
        candidate_yaml=arguments.get("candidate_yaml", ""),
        base_revision=arguments.get("base_revision"),
        backup_dir=arguments.get("backup_dir", ".yagra/backups"),
        golden_pass_required=arguments.get("golden_pass_required", True),
        last_golden_result=arguments.get("last_golden_result"),
        golden_dir=arguments.get("golden_dir", ".yagra/golden"),
    )
```

## 新規テストケース（5 件）

| # | テスト名 | 観点 |
|---|---------|------|
| 1 | `test_tool_apply_update_golden_gate_pass_with_result` | `golden_pass_required=True` + `last_golden_result={"total":2,"passed":2,"failed":0}` → apply 成功 |
| 2 | `test_tool_apply_update_golden_gate_fail_blocks_apply` | `last_golden_result={"total":3,"passed":2,"failed":1}` → `error: "golden_not_passed"` + workflow ファイルが書き換わっていない |
| 3 | `test_tool_apply_update_golden_gate_no_cases_warning` | 空 `golden_dir` → `success: True` + `warnings: ["no_golden_cases_defined"]` |
| 4 | `test_tool_apply_update_golden_gate_opt_out` | `golden_pass_required=False` → golden チェックせず従来挙動（現行テストと等価） |
| 5 | `test_tool_apply_update_golden_gate_tool_schema_description` | `create_mcp_server` の `apply_update` Tool description/inputSchema に `golden_pass_required` の記述あり |

E2E テスト側にも追加アサーション 1 件:
- `test_full_optimization_cycle` 内で `apply_result.get("warnings") == ["no_golden_cases_defined"]` を assert し、golden case 未定義時の動作を明示

## リスク・懸念点

| # | リスク | 軽減策 |
|---|-------|-------|
| 1 | `_tool_run_golden_tests` が内部で workflow を読む。`save_workflow_with_backup` より前に呼ぶので問題なし | 呼出順序を明示。テストでも順序を保証 |
| 2 | `last_golden_result` の形式が `run_golden_tests` の json 出力と異なる（`summary` キー vs フラット） | `_tool_run_golden_tests` の戻り値はフラット `{total, passed, failed, ...}` 形式。Contract のエラー形式 `summary: {...}` は error レスポンス内部の構造。helper 実装で両者を混同しないよう注意 |
| 3 | 既存 E2E の実行順序が `apply_update` → `rollback_update` で、apply 時に warnings が入ると rollback に影響しないか | rollback は apply の戻り値 `backup_id` のみ参照するので warnings 追加は影響なし。追加 assert を足しても既存動作は保たれる |
| 4 | Hexagonal 境界違反のリスク | 本変更は adapter 内クロージャのみ。新 use case 切り出しなし。`_tool_run_golden_tests` は既に adapter 内で use case 経由で動作しているため境界違反なし |

## 禁止事項（スコープ逸脱防止）

- `yagra apply` CLI 追加（別タスク #X）
- `allow_missing_golden` オプション追加（YAGNI）
- `propose_update` / `rollback_update` の変更
- golden case 自動生成
- golden_runner の内部実装変更
- `application/use_cases/` 層への新規ファイル追加（YAGNI）

## 検証手順

| Step | コマンド | 期待 |
|------|---------|------|
| 1 | `uv run pytest tests/unit/adapters/inbound/test_mcp_server.py -k golden_gate -v` | 5 件 PASSED |
| 2 | `uv run pytest tests/unit/adapters/inbound/test_mcp_server.py -v` | 既存 apply_update テスト全件 PASSED（リグレッション 0） |
| 3 | `uv run pytest tests/integration/test_optimization_cycle_e2e.py -v` | `test_full_optimization_cycle` PASSED |
| 4 | `uv run pytest` | playwright 33 件 pre-existing 失敗は許容。それ以外 0 失敗 |
| 5 | `uv run pre-commit run --all-files` | ruff/mypy/format 全 PASSED |
| 6 | `uv run python -c "from yagra.adapters.inbound.mcp_server import _tool_apply_update; import inspect; print(inspect.signature(_tool_apply_update))"` | 7 引数のシグネチャ確認 |
| 7 | `grep -n "golden_pass_required" CHANGELOG.md docs/agent-integration-guide.md` | 双方に言及あり |
