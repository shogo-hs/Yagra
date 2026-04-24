# Plan: #24 `examples/self-improve/` walking example

**作成日**: 2026-04-24 18:13 JST
**担当**: PM (Developer/PMO sequentially 代行)
**Intent**: `tasks/20260424181320_intent-self-improve-example.md`
**Contract**: `tasks/20260424180122_contract-po-pm-self-improve-example.md`

## 進行計画（Contract Step 4 以降の展開）

### Phase A: Developer 工程代行（Step 4）

**A-1. `examples/self-improve/workflow.yaml` 作成**
- Contract Section 3 の YAML を転記
- `generate` → `judge` の 2 ノード + 1 エッジ
- `judge.params.rubric` は inline（criteria: clarity / accuracy）
- `prompt_ref` なし（default system prompt 活用）
- 期待: `yagra validate` が is_valid: true

**A-2. `examples/self-improve/prompts.yaml` 作成**
- `generate:` セクションのみ
- system = 簡潔なテクニカルライター指示、user = `{topic}` と `{length}` 変数でフォーマット
- invoke 入力は `{"topic": ..., "length": ...}` を想定
- judge 用セクションなし（Contract E7）

**A-3. `examples/self-improve/run_example.py` 作成**
- docstring（日本語）: `yagra[llm,judge]` + `OPENAI_API_KEY` + `claude login` の 3 点前提
- `create_llm_handler` と `create_judge_handler` の両方を registry に登録
- `OPENAI_API_KEY` 未設定時に早期 exit（既存 `llm-basic/run_example.py` と同パターン）
- `claude login` 未実行時は handler 側 structured error（4-field）が raise される → `JudgeHandlerError` を try/except で stdout に整形表示
- stdout: draft / `judge_result.score._overall`（強調）/ 全 criterion score / reasoning / rubric_items

**A-4. `examples/self-improve/README.md` 作成**
- 5 ブロック（日本語主体）:
  1. **概要**: ビジョン「AI が AI を評価」位置づけ（1-2 段落）
  2. **Prerequisites & Setup**: `uv add "yagra[llm,judge]"` / `OPENAI_API_KEY` / `claude login` / モデル要件
  3. **実行手順**: `python run_example.py` + 期待 stdout サンプル
  4. **Propose-Judge-Apply 擬似対話**: 5-6 ステップで Claude Code + MCP 対話（`propose_update` → `judge` → `apply_update`）。将来拡張として `evaluate_traces` 等 MCP tool 予定（issue 番号なし）
  5. **Customization**: rubric ファイル化（`rubric_ref`）、generate の provider 切替（LiteLLM の `openai`/`anthropic`）、judge 側の custom `prompt_ref`

**A-5. `CHANGELOG.md` `[Unreleased]` Added 追記**
- 1 行、日本語、既存フォーマット踏襲

### Phase B: 品質ゲート（Step 5）

- **B-1**: `uv run pre-commit run --all-files` → 全 PASS
- **B-2**: `uv run pytest -q` → 1000 PASSED 維持（playwright 33 失敗は pre-existing、report 時に明示）
- **B-3**: `uv run yagra validate --workflow examples/self-improve/workflow.yaml --bundle-root examples/self-improve` → is_valid: true

### Phase C: 手動スモーク（Step 6 / SC-14）

- 環境: `OPENAI_API_KEY` 未設定（確認済み）
- → **実走は未実施**。代わりに `run_example.py` のコード path を静的に確認（import 成功 / API key 判定ロジック正常）
- PO 向け完了レポートで「ユーザー環境実走が必要」を明示

### Phase D: コミット + push + PR（Step 7）

- **D-1**: 論理単位コミット分割
  - Commit 1: `docs(tasks): #24 自己改善 example の計画文書を追加`
    - `tasks/20260424180122_contract-po-pm-self-improve-example.md`
    - `tasks/20260424181320_intent-self-improve-example.md`
    - `tasks/20260424181320_plan-self-improve-example.md`
    - `tasks/20260424181320_mission-brief-self-improve-example.md`
    - PO tracking 更新 4 ファイル（`tasks/progress.md` / `tasks/backlog.md` / `tasks/learnings.md` / `tasks/vision-alignment-log.md`）
  - Commit 2: `feat(examples): self-improve walking example を追加`
    - `examples/self-improve/workflow.yaml`
    - `examples/self-improve/prompts.yaml`
    - `examples/self-improve/run_example.py`
    - `examples/self-improve/README.md`
  - Commit 3: `docs(changelog): self-improve example 追記`
    - `CHANGELOG.md`

- **D-2**: `git push -u origin feature/add-self-improve-example`
- **D-3**: `gh pr create --base main --title "feat(examples): self-improve walking example を追加 (#24)" --body <<EOF ...` で DoD 14 項目 checklist 付き PR

### Phase E: PMO レビュー代行（Step 8）

- `tasks/20260424XXXXXX_review-self-improve-example.md` 作成
- DoD 14/14 照合表
- Critical / Major / Minor 判定
- Hexagonal 境界違反チェック（`git diff main...HEAD -- src/` が空であること）
- 判定: Accept / Changes Requested / Reject

### Phase F: PO 向け完了レポート（Step 9）

- PR URL
- DoD 14/14 pass/fail 表
- PMO 判定
- 手動スモーク結果（実施可否）
- 未対応事項・判断記録・次タスク示唆

## 実装スケッチ

### workflow.yaml（確定）
Contract Section 3 転記。

### prompts.yaml（決定案）
```yaml
generate:
  system: "You are a concise technical writer."
  user: "Write a {length}-sentence introduction about {topic}. Keep it factual and accessible."
```

### run_example.py（骨子）
```python
"""Self-Improve Walking Example.

2 ノード workflow（generate → judge）で、LLM 出力を LLM-as-a-Judge で評価する
Yagra の差別化軸を体感するサンプル。

Prerequisites:
    - uv add "yagra[llm,judge]"
    - OPENAI_API_KEY  （generate ノード用）
    - claude login    （judge ノードの claude_agent_sdk 用）
"""
import os, sys
from pathlib import Path
from yagra import Yagra
from yagra.handlers import create_llm_handler, create_judge_handler
from yagra.handlers.judge import JudgeHandlerError

def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY is required for the 'generate' node.")
        sys.exit(1)
    registry = {"llm": create_llm_handler(...), "judge": create_judge_handler(...)}
    app = Yagra.from_workflow(Path(__file__).parent / "workflow.yaml", registry)
    try:
        result = app.invoke({"topic": "Hexagonal Architecture", "length": 3})
    except JudgeHandlerError as exc:
        print("Judge handler failed (structured error):", exc.payload)
        sys.exit(1)
    # draft / score._overall / per-criterion scores / reasoning / rubric_items を stdout
```

### README（骨子）
既存 `examples/llm-structured/README.md` と同じ章立て。(d) は擬似対話形式。

## 禁止事項

- `src/` への変更（SC-13）
- `pip install` / `uv pip install` の使用（規約違反）
- rubric.yaml ファイル同梱（Contract E2）
- judge 用 prompt（`prompt_ref` / `prompt.user` 等）の YAML 記述（Contract E7）
- README での claude_agent_sdk を generate 側に匂わせる記述（Contract E1 禁止事項）
- 特定 issue 番号（#25 等）の README 記載（Contract E8）
- 破壊的 git 操作（rebase / force push）
- pre-commit hook skip（`--no-verify`）

## チェックリスト（実装完了判定）

- [ ] workflow.yaml 作成 + validate is_valid: true
- [ ] prompts.yaml 作成（generate のみ）
- [ ] run_example.py 作成（structured error ハンドリング込み）
- [ ] README.md 5 ブロック（日本語主体）
- [ ] CHANGELOG.md `[Unreleased]` Added 追記
- [ ] pre-commit 全通過
- [ ] pytest 1000 PASSED（playwright 除外）
- [ ] yagra validate is_valid: true
- [ ] コミット 3 分割
- [ ] PR 作成（DoD checklist 付き）
- [ ] PMO review 書類作成
- [ ] PO 完了レポート
