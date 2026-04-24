# Mission Brief: #24 `examples/self-improve/` walking example

**作成日**: 2026-04-24 18:13 JST
**担当**: Developer 工程（PM 代行）
**Intent**: `tasks/20260424181320_intent-self-improve-example.md`
**Plan**: `tasks/20260424181320_plan-self-improve-example.md`
**Contract**: `tasks/20260424180122_contract-po-pm-self-improve-example.md`

## ミッション

`examples/self-improve/` に walking example 4 ファイル（workflow.yaml / prompts.yaml / run_example.py / README.md）+ CHANGELOG 追記 を実装する。Hexagonal 境界遵守（`src/` 変更禁止）。

## 実装スケッチ

### 1. `examples/self-improve/workflow.yaml`

Contract Section 3 の確定 YAML をそのまま適用:

```yaml
version: "1.0"
start_at: "generate"
end_at:
  - "judge"

nodes:
  - id: "generate"
    handler: "llm"
    params:
      prompt_ref: "prompts.yaml#generate"
      model:
        provider: "openai"
        name: "gpt-4o-mini"
        kwargs:
          temperature: 0.7
      output_key: "draft"

  - id: "judge"
    handler: "judge"
    params:
      provider: "claude_agent_sdk"
      model: "sonnet"
      rubric:
        description: "Evaluate the draft for clarity and accuracy"
        criteria:
          - name: "clarity"
            description: "Is the output clear and easy to understand?"
            scale: { min: 1, max: 5 }
          - name: "accuracy"
            description: "Does the output match the requested spec?"
            scale: { min: 1, max: 5 }
      output_key: "judge_result"

edges:
  - source: "generate"
    target: "judge"
```

### 2. `examples/self-improve/prompts.yaml`

```yaml
generate:
  system: "You are a concise technical writer."
  user: "Write a {length}-sentence introduction about {topic}. Keep it factual and accessible."
```

### 3. `examples/self-improve/run_example.py`

- モジュール docstring（日本語）: 3 点前提（`yagra[llm,judge]` / `OPENAI_API_KEY` / `claude login`）
- `main()`:
  - `OPENAI_API_KEY` 未設定時 early exit（sys.exit(1)）
  - `registry = {"llm": create_llm_handler(retry=3, timeout=30), "judge": create_judge_handler(retry=3, timeout=60)}`
  - `Yagra.from_workflow(Path(__file__).parent / "workflow.yaml", registry)`
  - `invoke({"topic": "Hexagonal Architecture", "length": 3})`
  - `JudgeHandlerError` を try/except で捕捉し 4-field structured error を整形 print
- stdout 構成:
  ```
  === Draft (generate node) ===
  <draft 本文>

  === Judge Result (judge node) ===
  Overall score: 3.50   ← 強調
  - clarity:  4
  - accuracy: 3
  Reasoning: <reasoning 本文>
  Rubric items:
    - clarity (4): <per-criterion reasoning>
    - accuracy (3): <per-criterion reasoning>
  ```

### 4. `examples/self-improve/README.md`

5 ブロック（日本語主体）:

1. **概要**
   - ビジョン文脈「AI が AI を評価」の 1-2 段落
   - `generate`（LiteLLM openai gpt-4o-mini）→ `judge`（claude_agent_sdk sonnet）の位置づけ
2. **Prerequisites & Setup**
   - `uv add "yagra[llm,judge]"`
   - `export OPENAI_API_KEY="..."`
   - `claude login`（Claude subscription auth、API key 不要）
3. **実行手順**
   - `python run_example.py` + 期待 stdout サンプル（_overall, score, reasoning 含む）
4. **自己改善サイクル（Claude Code + MCP 対話）**
   - 5-6 ステップの擬似対話（Q/A 形式）
   - 最後に「将来 `evaluate_traces` 等 MCP tool 追加を予定」を 1-2 行（**issue 番号書かない**）
5. **Customization**
   - rubric.yaml 外部ファイル化（`rubric_ref: "rubric.yaml#default"`）の 1 段落コード例
   - generate provider 切替（LiteLLM の `openai` / `anthropic` のみ、claude_agent_sdk を匂わせない）
   - judge 側 custom `prompt_ref` の補足（optional）
   - `sonnet` alias → フルモデル ID 差し替え例 1 行

### 5. `CHANGELOG.md` 更新

`[Unreleased]` の Added 節に 1 行追記（日本語、既存フォーマット踏襲）:

```markdown
- `examples/self-improve/` walking example を追加。`generate`（LiteLLM gpt-4o-mini）→ `judge`（claude_agent_sdk sonnet）の 2 ノード構成で LLM-as-a-Judge の self-improve サイクルを体感できる (#24)
```

## 禁止事項

- `src/` 配下の修正禁止（SC-13 Hexagonal 境界）
- `pip install` / `uv pip install` 使用禁止（規約）
- `rubric.yaml` 実ファイル同梱禁止（Contract E2）
- judge 用 `prompt_ref` / `prompt` YAML 記述禁止（Contract E7 / default 活用）
- 特定 issue 番号（#25-28 等）README 記載禁止（Contract E8）
- generate 側に `claude_agent_sdk` を匂わせる記述禁止（Contract E1）
- pre-commit hook skip（`--no-verify`）禁止
- 破壊的 git 操作禁止（reset --hard / push --force）

## チェックリスト（CHANGELOG 事前組込含む）

### ファイル作成
- [ ] `examples/self-improve/workflow.yaml`
- [ ] `examples/self-improve/prompts.yaml`
- [ ] `examples/self-improve/run_example.py`
- [ ] `examples/self-improve/README.md`

### 既存ファイル修正
- [ ] `CHANGELOG.md` `[Unreleased]` Added 追記（**Mission Brief 標準項目、事前組込**）

### 品質ゲート
- [ ] `uv run pre-commit run --all-files` 全 PASS
- [ ] `uv run pytest -q` 1000 PASSED 維持（playwright 33 除外）
- [ ] `uv run yagra validate --workflow examples/self-improve/workflow.yaml --bundle-root examples/self-improve` → is_valid: true

### DoD（PMO レビュー前チェック）
- [ ] SC-1 〜 SC-14 の 14 項目で自己評価 14/14
- [ ] `git diff main...HEAD -- src/` が空であること

## CHANGELOG 事前組込の根拠

`tasks/learnings.md` 「プロジェクト固有パターン」#4:
> CHANGELOG 事前組込: Mission Brief チェックリスト標準項目。PMO 指摘 0 件のため事前に対応

→ 本 Mission Brief で CHANGELOG 更新タスクを「既存ファイル修正」セクションに独立列挙、PMO 指摘前に組込。

## 実行順序

1. workflow.yaml → validate dry-run
2. prompts.yaml
3. run_example.py
4. README.md
5. CHANGELOG.md
6. 品質ゲート一式
7. コミット 3 分割（Plan D-1 参照）
8. PR 作成
9. PMO レビュー代行
10. PO 完了レポート
