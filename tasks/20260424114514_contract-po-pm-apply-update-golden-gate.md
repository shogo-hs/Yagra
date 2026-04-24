# PO-PM Task Contract: #4 `_tool_apply_update` golden_pass_required オプション追加

**layer:** PO → PM
**created:** 2026-04-24
**status:** aligned
**task size:** M（設計判断あり、複数ファイル、Hexagonal 低リスク）
**process path:** 標準（Step 1-4、1往復アライメントで完結）

---

## ビジョンコンテキスト（PO観点）

### このタスクの位置づけ
ビジョン整合性監査で検出した **Major** 項目の解消。`docs/product/vision.md` Phase 4（Approve & Update）「Safe Iteration」で「apply_update 実行前の golden test 通過」を謳うが、API が強制していない。`docs/agent-integration-guide.md:375` も「apply_update 前に必ず run_golden_tests を実行する」と書きながら実装で担保されていない、思想的綻び。

### 期待する成果
apply_update が「golden test 通過」を前提とした API に進化する。エージェントが意図せず golden 失敗状態のまま apply する事故を防ぐ。続く #23 (`create_judge_handler`) 実装後の自己改善サイクル（propose → judge → golden → apply）完結性の前提条件にもなる。

### 優先度の根拠
Must — 監査で検出した思想的綻びの補正。

### 品質・スコープの判断基準
- **妥協してよい点**:
  - backward-compat は default パラメータで吸収できる程度で OK
  - strict モード（golden case 未定義時に error 中止）の追加オプション化は YAGNI として見送り
- **妥協してはいけない点**:
  - `golden_pass_required=True` で golden 未 pass 時、apply_update は **必ず失敗を返す**（silent success 禁止）
  - エラーレスポンスが構造化され、エージェントが「なぜ失敗したか」を理解できる
  - MCP ツールの Pydantic スキーマと docs/agent-integration-guide.md の記述が一致
  - 既存テスト（`test_mcp_server.py` / `test_optimization_cycle_e2e.py`）が壊れない

---

## 技術コンテキスト（PM観点）

### 現状（PM 調査済み）
- 実装: `src/yagra/adapters/inbound/mcp_server.py:824` `_tool_apply_update(workflow_path, candidate_yaml, base_revision=None, backup_dir=".yagra/backups")`
- golden: 同ファイル:952 `_tool_run_golden_tests(workflow_path, golden_dir=".yagra/golden", case_name=None, fmt="json")`
- E2E テスト（`test_optimization_cycle_e2e.py:192`）は **golden case を作成していない**（発見事項）
- Hexagonal 抵触リスク: 低。`_tool_run_golden_tests` は既に `application/use_cases/golden_test_runner.py` 経由で呼ぶ構造

### 技術的アプローチ（採用決定: Option C ハイブリッド）

```python
def _tool_apply_update(
    workflow_path: str,
    candidate_yaml: str,
    base_revision: str | None = None,
    backup_dir: str = ".yagra/backups",
    golden_pass_required: bool = True,  # 新規 (デフォルト ON)
    last_golden_result: dict[str, Any] | None = None,  # 新規
    golden_dir: str = ".yagra/golden",  # 新規 (内部実行時に使用)
) -> dict[str, Any]:
```

#### 挙動仕様（PO 確定）

| 状況 | `golden_pass_required` | `last_golden_result` | 挙動 |
|------|:---:|:---:|------|
| 呼び出し側が事前 run_golden_tests 済み | True | dict あり | dict の `summary.total == summary.passed` を検証 → pass なら apply、fail なら `error: "golden_not_passed"` |
| 呼び出し側が事前実行せず | True | None | 内部で `_tool_run_golden_tests(candidate_yaml の書込前の workflow_path, golden_dir)` を実行 → 同様に判定 |
| **golden case が未定義（total=0）** | True | どちらでも | **warning 付き apply 許可**（レスポンスに `"warnings": ["no_golden_cases_defined"]`）。silent success 禁止のため warnings 必須 |
| strict モード（将来） | - | - | 見送り。必要なら後続タスクで `allow_missing_golden: bool = True` を導入 |
| backward-compat | False | - | 従来挙動（golden チェックなし） |

**構造化エラーフォーマット:**
```json
{
  "error": "golden_not_passed",
  "message": "Golden tests did not fully pass: 2/3 passed, 1 failed",
  "summary": {"total": 3, "passed": 2, "failed": 1},
  "hint": "run_golden_tests の失敗ケースを確認し、candidate_yaml を修正してから再度 apply_update を実行してください"
}
```

**内部実行タイミング:** `save_workflow_with_backup` の**前**に golden チェックを実行。apply 失敗時は workflow ファイルを書き換えない。

#### Hexagonal 境界への配慮
- `_tool_run_golden_tests` は既に adapter 内で use case を呼ぶ構造。`_tool_apply_update` が同 adapter の `_tool_run_golden_tests` を内部呼び出ししても adapters → application 経由で境界違反なし
- 新 use case 切り出しは YAGNI。ただし golden check ロジックは **private helper**（`_assert_golden_passed(...)`）として mcp_server.py 内に切り出す（将来 CLI からも呼べる構造を確保）
- `last_golden_result` の schema は **任意 dict**（`run_golden_tests` の戻り値そのまま受ける）。内部で `summary.total` / `summary.passed` のみを参照する契約
- Pydantic Model で固めるのは YAGNI

### 技術リスク（PO 判断で解消）

| # | リスク | PO 判断 |
|---|--------|---------|
| 1 | E2E テストに golden case 不在 → デフォルト ON で壊れる | **golden case 未定義時は warning 付き apply 許可**で E2E は壊さない。silent success 防止のため warnings を必ず返す |
| 2 | `last_golden_result` schema 厳格性 | **任意 dict**。内部で `summary.total` / `summary.passed` のみ参照。Pydantic Model 化は YAGNI |
| 3 | `save_workflow_with_backup` との順序 | golden チェック → backup → 書込 の順序を保証する（failed 時は書込まない） |

### 見積もり
- **サイズ: M**
- **Developer 数: 1**（PM 環境制約により PM が Developer/PMO を sequentially 代行。skill M サイズ規定の 3 名を、PM 代行の 1 ロール + PMO 代行で圧縮）
- **推定ファイル変更数: 5**
  1. `src/yagra/adapters/inbound/mcp_server.py`（apply_update 実装、Pydantic description 更新）
  2. `tests/unit/adapters/inbound/test_mcp_server.py`（3ケース以上追加）
  3. `tests/integration/test_optimization_cycle_e2e.py`（新デフォルトで壊れないことを確認。必要なら golden case 追加 or 明示的 False 指定）
  4. `docs/agent-integration-guide.md`（L375 周辺の記述を「デフォルトで強制」に更新、warnings 仕様を追記）
  5. `CHANGELOG.md`（[Unreleased] Changed / Fixed）

### 代替案（却下）
- **Option A 単独**: 呼び出し側が `last_golden_result` を渡さないと素通り → silent fail 防止要件を満たさない。却下
- **Option B 単独**: 毎回内部実行で二重コスト。呼び出し側が既に golden 実行済みの場合に再利用できない。却下
- **strict モード（`allow_missing_golden=False`）**: E2E を壊す上に、「golden case なし ＝ 検証不能」は応用によって自然な状態。YAGNI として見送り。将来必要になれば追加オプション化可能

---

## 合意事項

### 成功基準

| # | 基準 | 検証コマンド | 実質性チェック |
|---|------|------------|--------------|
| 1 | `_tool_apply_update` に `golden_pass_required: bool = True` / `last_golden_result: dict \| None = None` / `golden_dir: str = ".yagra/golden"` 引数追加 | `uv run python -c "from yagra.adapters.inbound.mcp_server import _tool_apply_update; import inspect; sig = inspect.signature(_tool_apply_update); print(sig)"` | 3 引数がデフォルト値付きで存在 |
| 2 | `golden_pass_required=True` かつ golden 未 pass 時、構造化エラー返却 + 書込されない | 新規ユニットテスト（失敗ケース）で `error == "golden_not_passed"` と `summary` フィールドを assert。apply 前後でファイル内容が同一 | silent success なし |
| 3 | `golden_pass_required=True` かつ golden case 未定義時、warnings 付き apply 許可 | 新規ユニットテスト（空 golden_dir ケース）で `success: True` / `warnings: ["no_golden_cases_defined"]` を assert | 既存 E2E が新デフォルトで壊れない |
| 4 | `golden_pass_required=False` で従来挙動 | 新規ユニットテスト（旧挙動互換ケース）で backward-compat 確認 | 既存呼び出しが明示オプトアウトで従来動作 |
| 5 | MCP ツールの Pydantic スキーマ description に「デフォルト True。run_golden_tests の passed == total が前提」を明記。`last_golden_result` 仕様も description に記載 | `uv run python -c "from yagra.adapters.inbound.mcp_server import create_mcp_server; ..." で schema を取得し文字列チェック`（具体コマンドは PM で決定） | AI エージェントが description だけで挙動を理解できる |
| 6 | `docs/agent-integration-guide.md` の「apply_update 実行前に必ず run_golden_tests」記述が実装と整合 | `grep -n "golden_pass_required" docs/agent-integration-guide.md` → 言及あり | docs ↔ 実装の乖離 0 |
| 7 | `tests/unit/adapters/inbound/test_mcp_server.py` に 3 ケース以上追加（pass / fail / `golden_pass_required=False` / no-case warning） | `uv run pytest tests/unit/adapters/inbound/test_mcp_server.py -k golden_gate -v` で 4 ケース以上 PASSED | 明確な挙動契約 |
| 8 | `tests/integration/test_optimization_cycle_e2e.py` が新デフォルトで pass（または意図を持って `golden_pass_required=False` 明示） | `uv run pytest tests/integration/test_optimization_cycle_e2e.py -v` で既存 pass | 既存 E2E 壊さない |
| 9 | CHANGELOG.md `[Unreleased]` の Changed / Fixed に追記 | `grep -n "golden_pass_required" CHANGELOG.md` | user-visible 変更として記録 |
| 10 | `uv run pre-commit run --all-files` 通過 | 同上 | ruff/mypy Passed |

### スコープ
- **In:**
  - `_tool_apply_update` のシグネチャ + 実装変更
  - private helper `_assert_golden_passed(...)` 抽出（将来の CLI 共有を想定）
  - Pydantic スキーマ description 更新（`@mcp.tool()` デコレータの Pydantic Field）
  - `docs/agent-integration-guide.md` の該当箇所更新
  - 既存テスト更新 + 新規テスト追加
  - CHANGELOG 追記
- **Out:**
  - `yagra apply` CLI 追加（別タスク）
  - `allow_missing_golden` オプション追加（YAGNI）
  - golden case 自動生成（別タスク、別フェーズ）
  - `propose_update` / `rollback_update` の変更（別タスク）
  - #23 `create_judge_handler` 実装

### 制約
- Python 3.12 / uv / LangGraph / MCP
- Hexagonal Architecture（adapters → application 経由のみ、domain/ports への逆依存禁止）
- Yagra プロジェクトの CONTRIBUTING.md に従う（uv add/sync のみ、pip install 禁止）
- main ブランチ保護あり → feature branch → PR → user マージ
- コミット前に `uv run pre-commit run --all-files` 必須

---

## アライメントで解消した懸念

| # | 提起者 | 懸念 | 解決 |
|---|--------|------|------|
| 1 | PM | golden case 未定義時（total=0）の挙動 | PO 判断: warning 付き apply 許可（既存 E2E 保護）。silent success 防止のため warnings 必須 |
| 2 | PM | `last_golden_result` schema 厳格性 | PO 判断: 任意 dict。内部で `summary.total` / `summary.passed` のみ参照。Pydantic Model 化は YAGNI |
| 3 | PM | E2E テストが新デフォルトで壊れるリスク | 懸念 #1 の判断で解消。追加で、E2E 側も「この E2E は golden case を作成していないことを明示する」コメントを残す |
| 4 | PO | Option A / B / C の選択 | PM 分析を受けて Option C（ハイブリッド）採用 |

## エスカレーション事項
なし（PO 裁量で完了可能）。

---

## 付記：PM 実行ヒント

- Developer 数: PM 環境制約により PM が 1 Developer + PMO を sequentially 代行
- Mission Brief には本 contract の「挙動仕様テーブル」「成功基準」「スコープ」「エラーレスポンスフォーマット」を転記
- PMO レビューは sonnet（M サイズルーティング）
- Feature branch 名案: `feature/apply-update-golden-gate`
- PR タイトル案: `feat(mcp): apply_update に golden_pass_required オプション追加（デフォルト ON）(#4)`
- 既存 E2E テスト `_WORKFLOW_YAML_V2` 付近に「golden case なし → no_golden_cases_defined warning を受け取る」ことを明示するアサーションを追加推奨

## 参考

- 前回 PMO 指摘パターン（`tasks/learnings.md` より）:
  - CHANGELOG 追記（#3 で 1 回発生）→ 2 回目なので Mission Brief のチェックリストに昇格検討
  - 0-match silent success 防止（#3 で 1 回発生）→ 本タスクの「golden case 未定義時 warning」と同系統の思想
