# Mission Brief: #4 `_tool_apply_update` golden_pass_required オプション追加

**created:** 2026-04-24 11:51 JST
**intent:** `tasks/20260424114909_intent-apply-update-golden-gate.md`
**plan:** `tasks/20260424115020_plan-apply-update-golden-gate.md`
**contract:** `tasks/20260424114514_contract-po-pm-apply-update-golden-gate.md`

---

## ゴール（1-3 文）

Yagra MCP `apply_update` ツールを「golden test 成功前提」の API に進化させる。`golden_pass_required: bool = True` / `last_golden_result: dict | None = None` / `golden_dir: str` を追加し、Option C ハイブリッド（キャッシュ渡し or 内部実行）で pass 判定する。golden case 未定義時は `warnings: ["no_golden_cases_defined"]` 付きで apply を許可（silent success 防止）。

## 成功基準テーブル（Contract 転記 + 検証コマンド）

| # | 基準 | 検証コマンド | 実質性チェック |
|---|------|------------|--------------|
| 1 | `_tool_apply_update` に 3 引数追加（デフォルト値付き） | `uv run python -c "from yagra.adapters.inbound.mcp_server import _tool_apply_update; import inspect; print(inspect.signature(_tool_apply_update))"` | 7 引数がデフォルト値付きで存在 |
| 2 | `golden_pass_required=True` かつ golden 未 pass 時、構造化エラー返却 + 書込なし | 新規ユニットテスト（失敗ケース）で `error == "golden_not_passed"` と `summary` フィールドを assert。apply 前後でファイル内容が同一 | silent success なし |
| 3 | `golden_pass_required=True` かつ golden case 未定義時、warnings 付き apply 許可 | 新規ユニットテスト（空 `golden_dir`）で `success: True` / `warnings: ["no_golden_cases_defined"]` を assert | 既存 E2E が新デフォルトで壊れない |
| 4 | `golden_pass_required=False` で従来挙動 | 新規ユニットテスト（旧挙動互換ケース）で backward-compat 確認 | 既存呼び出しが明示オプトアウトで従来動作 |
| 5 | MCP ツール Pydantic schema description に仕様明記 | schema 取得スクリプトで `golden_pass_required` 文字列を含むこと、`last_golden_result` / `golden_dir` の description もあること | AI エージェントが description だけで挙動を理解できる |
| 6 | `docs/agent-integration-guide.md` 更新 | `grep -n "golden_pass_required" docs/agent-integration-guide.md` で言及あり | docs↔実装乖離 0 |
| 7 | `tests/unit/adapters/inbound/test_mcp_server.py` に 3 ケース以上追加 | `uv run pytest tests/unit/adapters/inbound/test_mcp_server.py -k golden_gate -v` で 4 件以上 PASSED | 明確な挙動契約 |
| 8 | E2E テスト既存パス | `uv run pytest tests/integration/test_optimization_cycle_e2e.py -v` で PASSED | 既存 E2E 壊さない |
| 9 | CHANGELOG.md `[Unreleased]` 追記 | `grep -n "golden_pass_required" CHANGELOG.md` で言及あり | user-visible 変更として記録 |
| 10 | `uv run pre-commit run --all-files` 通過 | 同上 | ruff/mypy Passed |

## 挙動仕様（Contract 転記）

| 状況 | `golden_pass_required` | `last_golden_result` | 挙動 |
|------|:---:|:---:|------|
| 呼び出し側が事前 run_golden_tests 済み | True | dict あり | dict の `total == passed` を検証 → pass なら apply、fail なら `error: "golden_not_passed"` |
| 呼び出し側が事前実行せず | True | None | 内部で `_tool_run_golden_tests(workflow_path, golden_dir)` を実行 → 同様に判定 |
| **golden case が未定義（total=0）** | True | どちらでも | **warning 付き apply 許可**（`warnings: ["no_golden_cases_defined"]`）。silent success 禁止のため warnings 必須 |
| backward-compat | False | - | 従来挙動（golden チェックなし） |

### 構造化エラーフォーマット

```json
{
  "error": "golden_not_passed",
  "message": "Golden tests did not fully pass: 2/3 passed, 1 failed",
  "summary": {"total": 3, "passed": 2, "failed": 1},
  "hint": "run_golden_tests の失敗ケースを確認し、candidate_yaml を修正してから再度 apply_update を実行してください"
}
```

### 内部実行タイミング

`save_workflow_with_backup` の **前** に golden チェック。apply 失敗時は workflow ファイルを書き換えない。

## コードベース状況（Step 2 結果）

### 主要ファイル

- **`src/yagra/adapters/inbound/mcp_server.py`**
  - L824-904 `_tool_apply_update` 定義（現行シグネチャ 4 引数）
  - L952-1033 `_tool_run_golden_tests` 定義（戻り値: `{workflow_name, total, passed, failed, all_passed, results: [...]}` のフラット dict）
  - L192-223 `list_tools` 内 `apply_update` Tool inputSchema
  - L378-384 `call_tool` 内 `apply_update` ディスパッチャ

- **`tests/unit/adapters/inbound/test_mcp_server.py`**
  - L722-744 既存 YAML フィクスチャ `_VALID_WORKFLOW_YAML_PROPOSE` / `_UPDATED_WORKFLOW_YAML_PROPOSE`
  - L817-899, L1089-1175 既存 `_tool_apply_update` テスト群（success, invalid_yaml, revision_conflict, validation_failed, non_mapping, file_not_found, os_error, non_mapping_current, generic_exception）
  - L1245-1295 `test_list_tools_contains_all_tools` — Tool 名集合の spot check

- **`tests/integration/test_optimization_cycle_e2e.py`**
  - 現行 E2E は golden case を作成していない → 新デフォルト ON で warnings 付き apply 許可フローが必須
  - L192-202 apply_update 呼び出し箇所 → `warnings` 追加 assert を足す

- **`docs/agent-integration-guide.md`**
  - L374-377 重要な制約セクションに「apply_update を実行する前に必ず run_golden_tests を実行する」記述

- **`CHANGELOG.md`**
  - L5-11 `[Unreleased]` セクションに既に Added / Fixed あり。新規 Changed + Fixed サブセクションを追記

### `_tool_run_golden_tests` 戻り値形式（重要）

```python
{
    "workflow_name": "workflow",
    "total": 2,
    "passed": 2,
    "failed": 0,
    "all_passed": True,
    "results": [...],  # fmt="json" のとき
}
```

**注意:** Contract のエラーレスポンスでは `summary: {total, passed, failed}` のネスト形式だが、これは **error 払出時の構造**。`last_golden_result` から読むキーは `total` / `passed` がトップレベル。両者を混同しないこと。

## アーキテクチャ方針（守るべき設計）

### Hexagonal 境界

- `_tool_apply_update` は adapter（inbound）内クロージャなので、同 adapter 内の `_tool_run_golden_tests` を呼んでよい
- 新 use case 切り出しは YAGNI（Contract 決定事項）
- private helper `_assert_golden_passed(...)` は **mcp_server.py 内に配置**する。`application/` や `domain/` には置かない（将来 CLI 共有は必要時に切り出す）
- `application/` / `domain/` に新規ファイル追加しない

### 依存方向

- adapters → application → domain（既存方向を維持）
- domain / ports には触れない

## 品質基準（フレームワーク推奨パターンの遵守）

- **型ヒント必須**: `golden_pass_required: bool = True` / `last_golden_result: dict[str, Any] | None = None` / `golden_dir: str = ".yagra/golden"`
- **Google スタイル docstring（日本語）**: `Args` / `Returns` / `Raises` 明記
- **関数責務の分離**: golden チェックロジックは `_assert_golden_passed(...)` helper に切り出す（SRP）
- **構造化エラー**: Contract の error フォーマットに忠実に従う（`error` / `message` / `summary` / `hint`）
- **silent success 禁止**: warnings は必ず list で返す（`warnings: [] のときは key を返さない`）
- **既存スタイル**: `return {"error": ..., "message": ...}` パターンは既存と統一

## コーディング規約

- Python 3.12+、`from __future__ import annotations` 既存ファイルで使用中
- `ruff check` / `ruff format` / `mypy` 必須（pre-commit で自動実行）
- 相対インポートより絶対インポート（既存慣習に合わせる）
- テストは pytest スタイル、既存の `monkeypatch` / `tmp_path` パターンに追従
- 新規テスト関数名は `test_tool_apply_update_golden_gate_*` 形式

## 制約（スコープ境界）

### In Scope

- `_tool_apply_update` のシグネチャ + 実装変更
- private helper `_assert_golden_passed(...)` を mcp_server.py 内に追加
- `list_tools` の `apply_update` Tool inputSchema 更新（3 引数 description 追加）
- `call_tool` ディスパッチャに新引数パススルー
- `docs/agent-integration-guide.md` の該当箇所更新
- 新規テスト 5 件追加（test_mcp_server.py）+ E2E に warnings assert 1 件追加
- `CHANGELOG.md` `[Unreleased]` Changed / Fixed 追記

### Out of Scope

- `yagra apply` CLI 追加
- `allow_missing_golden` オプション（YAGNI）
- golden case 自動生成
- `propose_update` / `rollback_update` の変更
- #23 `create_judge_handler` 実装
- `docs/sphinx/source/user_guide/optimization_cycle.md` 更新（英語ドキュメントは release-ops で同期するべきもの）
- `application/use_cases/` / `domain/` 新規ファイル追加

### 禁止事項

- 既存テスト関数の削除・無効化（新規追加のみ）
- `save_workflow_with_backup` / `_tool_run_golden_tests` の改変
- golden_runner 内部実装の変更
- `--no-verify` / pre-commit skip
- `pip install` / `uv pip install` 使用
- 想定外の大量差分（単一 helper + `_tool_apply_update` 改修が核。周辺は最小修正）

## 実装スケッチ（Plan から抜粋）

### `_assert_golden_passed(...)` helper

```python
def _assert_golden_passed(
    workflow_path: str,
    golden_dir: str,
    last_golden_result: dict[str, Any] | None,
) -> tuple[bool, dict[str, Any] | None, list[str]]:
    """Golden テストの通過を判定する private helper。

    呼び出し側が事前に run_golden_tests 済みなら last_golden_result を
    再利用し、未指定なら内部で _tool_run_golden_tests を実行する。

    Args:
        workflow_path: 判定対象のワークフロー YAML パス。
        golden_dir: golden case を探索するディレクトリ。
        last_golden_result: 事前実行済みの run_golden_tests 結果。None の場合は内部実行。

    Returns:
        (passed, error_payload, warnings)
        - passed が True かつ error_payload が None なら apply を続行する。
        - passed が False なら error_payload をそのまま return する。
        - warnings は pass 時の注意喚起（空でも可）。
    """
    if last_golden_result is not None:
        result = last_golden_result
    else:
        result = _tool_run_golden_tests(
            workflow_path=workflow_path,
            golden_dir=golden_dir,
            case_name=None,
            fmt="json",
        )
        if "error" in result:
            return False, {
                "error": "golden_check_failed",
                "message": f"Failed to run golden tests: {result.get('message', result['error'])}",
                "hint": "golden_dir を確認するか、golden_pass_required=False で明示的にスキップしてください",
            }, []

    total = int(result.get("total", 0))
    passed_count = int(result.get("passed", 0))
    failed_count = int(result.get("failed", total - passed_count))

    if total == 0:
        return True, None, ["no_golden_cases_defined"]

    if passed_count == total and failed_count == 0:
        return True, None, []

    return False, {
        "error": "golden_not_passed",
        "message": (
            f"Golden tests did not fully pass: {passed_count}/{total} passed, {failed_count} failed"
        ),
        "summary": {"total": total, "passed": passed_count, "failed": failed_count},
        "hint": (
            "run_golden_tests の失敗ケースを確認し、"
            "candidate_yaml を修正してから再度 apply_update を実行してください"
        ),
    }, []
```

### `_tool_apply_update` 統合ポイント

- `save_workflow_with_backup` を呼ぶ **前** に golden チェックブロックを挿入
- `golden_pass_required=False` なら helper を呼ばずスキップ
- `passed == True` で warnings を溜めておき、最終レスポンスに `warnings` key を追加（空なら key 省略）

### `list_tools` の `apply_update` description 更新

```
"Validate the candidate YAML and apply it to the workflow file with a backup. "
"By default, requires golden tests to pass (run_golden_tests: passed == total) "
"before writing the file. Returns backup_id which can be used to rollback if needed."
```

### `inputSchema.properties` に以下 3 項目を追加

- `golden_pass_required`: `{"type": "boolean", "description": "Require golden tests to pass before apply. Default true. Set to false to skip golden gate."}`
- `last_golden_result`: `{"type": "object", "description": "Result dict from a prior run_golden_tests call (fields: total, passed, failed). If omitted, run_golden_tests is invoked internally using golden_dir."}`
- `golden_dir`: `{"type": "string", "description": "Directory to search for golden cases when last_golden_result is not provided. Defaults to '.yagra/golden'."}`

## チェックリスト（完了判定）

Developer は以下を **全て Yes** にしてから完了報告する:

- [ ] `_tool_apply_update` のシグネチャが 7 引数（`golden_pass_required` / `last_golden_result` / `golden_dir` 追加）
- [ ] private helper `_assert_golden_passed(...)` が mcp_server.py 内に存在
- [ ] golden 未 pass 時は `save_workflow_with_backup` が **呼ばれない**（ファイル内容変化なし）
- [ ] golden case 未定義時は `warnings: ["no_golden_cases_defined"]` 付きで apply 成功
- [ ] `list_tools` の `apply_update` Tool description / inputSchema に 3 引数分の記述追加
- [ ] `call_tool` ディスパッチャに 3 引数パススルー追加
- [ ] `docs/agent-integration-guide.md` に `golden_pass_required` の言及追加
- [ ] 新規テスト 5 件 + E2E assert 1 件が PASSED
- [ ] 既存 apply_update テスト全件 PASSED（リグレッション 0）
- [ ] `CHANGELOG.md` `[Unreleased]` に Changed / Fixed 追記
- [ ] `uv run pre-commit run --all-files` 通過
- [ ] 検証証拠（コマンド実行結果）を developer 記録ファイルに明記

## 参考: 過去 PMO 指摘パターン（learnings.md より）

- CHANGELOG 追記（#3 で 1 回）→ 本タスクで 2 回目発生。Mission Brief のチェックリスト標準項目に昇格
- 0-match silent success 防止（#3 で 1 回）→ 本タスクの「golden case 未定義時 warning」と同系統。silent success 絶対禁止
