# PO-PM Task Contract: #24 `examples/self-improve/` walking example

**作成日**: 2026-04-24
**担当 PO**: Claude (agent-company-v2 スキル)
**対応バックログ**: #24（Must / 依存 #23 解消済み）
**状態**: **確定**（PM Alignment Agent 1 往復で Q1-Q5 + E6-E8 確定）

---

## 1. ビジョンコンテキスト（PO 観点）

### このタスクの位置づけ

`docs/product/vision.md` L70 で「`create_judge_handler()` 等を提供し、… 評価 rubric の宣言、スコア + 根拠の構造化出力、propose → judge → apply の自己改善ループに連結する基盤を提供する」と約束した walking example の実体化。

L109 の「やること」に「LLM-as-a-Judge handler と**自己改善ループの walking example** を提供する」と明記されており、本タスクが未実装だと「judge handler は存在するが **ユーザーが体験する導線がない**」状態となり、UX 一貫性が維持できない。

### 期待する成果

- **Yagra 自身のリポジトリに「差別化軸を体験できる walking example」が存在する状態**
- ユーザーは `examples/self-improve/` を clone/copy して、Yagra + Claude Code + MCP で「AI が AI を評価 → 承認 → 更新」のサイクルを体感できる
- #23 で実装した `create_judge_handler` の使い方を rubric / schema / output 構造まで自己完結で示す
- `examples/self-improve/workflow.yaml` は他 example と同様に `validate-example.yml` CI で自動検証される

### 優先度の根拠（Must）

- ビジョン（L109「やること」）に明示された約束の未履行箇所
- #23 完了で差別化軸スコア 2→4 に到達したが、残り 1 点（5/5）達成には「**ユーザーが体験する walking example**」が必要
- `examples/llm-basic/` / `examples/llm-structured/` 等、他 handler には軒並み example があり、judge だけ example がないと UX 非一貫

### 品質・スコープ判断基準

- **妥協してよい**:
  - propose → judge → apply の完全な **E2E ループを workflow.yaml 内で自動実走させる**必要はない（propose_update / apply_update は MCP tool であり workflow node から直接呼ばない設計、そのためループの完結は README で IDE 操作として説明）
  - LLM 呼び出しを含む `run_example.py` は CI では回さない（他 example と同水準の扱い、validator のみ CI 対象）
  - rubric は inline のみで完結させる（外部ファイル `rubric.yaml` は同梱しない、README のコードブロックで紹介のみ）
- **妥協してはいけない**:
  - **ビジョン約束の「自己改善サイクル」が README から読み取れる** こと。単なる judge の単発呼び出しデモに縮退させない
  - workflow.yaml は `yagra validate` で error 0 通過（warning は他 example と同水準なら可）
  - judge は Claude SDK 経由（default `claude_agent_sdk` + sonnet）で subscription auth 動作が可能。judge 側に追加の API キーを要求しない（Local-First 原則）
  - handler / rubric の structured error / fail-fast 挙動を walking example で崩さない
  - walking example を通じて **judge handler の実際の output 構造**（`{score: {name_1, name_2, _overall}, reasoning, rubric_items}`）が正確に示される

---

## 2. 成功基準（DoD）確定版

### 2.1 Workflow / Example 構造

| # | 基準 | 検証手段 |
|---|------|---------|
| SC-1 | `examples/self-improve/workflow.yaml` が `generate`（LLM 生成）→ `judge`（評価）の 2 ノード workflow で、`yagra validate --workflow examples/self-improve/workflow.yaml --bundle-root examples/self-improve` が `is_valid: true`（error 0） | `yagra validate` コマンド |
| SC-2 | `judge` ノードが **inline rubric**（2 criteria: 例として `clarity` と `accuracy`、それぞれ `scale: {min: 1, max: 5}`）で構成され、**`prompt_ref` を指定せず default system prompt を活用**する構成（学習効果重視） | workflow.yaml 検査 |
| SC-3 | 実行結果の state に `judge_result` キーが存在し、その中身が **judge handler の実装通りの構造**: `{score: {<criterion1>: int, <criterion2>: int, _overall: float}, reasoning: str, rubric_items: list}`。`run_example.py` の stdout で `score._overall` を強調表示 | `run_example.py` 実走（手動スモーク） |

### 2.2 ファイル構成・認証・依存

| # | 基準 | 検証手段 |
|---|------|---------|
| SC-4 | `examples/self-improve/` に以下 4 ファイル（他 example と同一構成）: `workflow.yaml` / `prompts.yaml`（generate 用のみ、judge は default 活用のため無し）/ `run_example.py` / `README.md`。**参考 `rubric.yaml` は同梱しない**（README のコードブロックのみで紹介） | ファイル配置確認 |
| SC-5 | `run_example.py` は以下で動作: (a) `generate` ノードは **OpenAI `gpt-4o-mini` default**（`OPENAI_API_KEY` 要求、既存 llm-basic/llm-structured と同等）(b) `judge` ノードは **`provider: "claude_agent_sdk"` + `model: "sonnet"`**（`claude login` 済み subscription auth、API key 不要） | `run_example.py` コード検査 + 手動スモーク |
| SC-6 | README の Prerequisites に `uv add "yagra[llm,judge]"` と **`OPENAI_API_KEY` + `claude login` の両方が必要**である旨を明示 | README 目視検査 |
| SC-7 | README に以下 5 ブロックが揃う（**日本語主体**で既存 example と揃える）: (a) 概要・ビジョン文脈（1-2 段落で「AI が AI を評価」の position 説明）(b) Prerequisites + Setup (c) 実行手順（`run_example.py`） (d) **自己改善サイクル（propose → judge → apply）の Claude Code + MCP 対話手順**（架空の擬似スクリプト 5-6 ステップ） (e) rubric・provider のカスタマイズ方法 | README 目視検査 |
| SC-8 | README (d) に「**将来の自己改善サイクル拡張として、MCP に `evaluate_traces` 等の tool 追加予定**」程度の 1-2 行で未来見通しを書く（**特定 issue 番号は書かない**、プロダクトドキュメント整合性を保つ） | README 目視検査 |

### 2.3 CI・品質ゲート

| # | 基準 | 検証手段 |
|---|------|---------|
| SC-9 | `.github/workflows/validate-example.yml` が `examples/self-improve/workflow.yaml` を自動検出し、PR で緑通過（`examples/*/workflow.yaml` glob に合致、追加修正不要の想定。ただし PM は **実装開始前に `yagra validate` のドライランで `yagra[judge]` 不在時の挙動を確認**すること） | GitHub Actions + dry-run |
| SC-10 | `CHANGELOG.md` `[Unreleased]` の Added に「examples/self-improve/ walking example 追加」を 1 行追記 | CHANGELOG 目視検査 |
| SC-11 | `uv run pre-commit run --all-files` 全通過（ruff format / ruff check / mypy） | pre-commit 実行 |
| SC-12 | 既存テストスイートを壊さない（unit + integration は #23 完了時点の 1000 PASSED を維持、playwright は pre-existing 除外） | `uv run pytest` |
| SC-13 | Hexagonal 境界違反なし。`src/` に手を入れない（example 側のみ、`yagra[judge]` を利用者として使う立場） | diff 確認 |

### 2.4 手動スモーク

| # | 基準 | 検証手段 |
|---|------|---------|
| SC-14 | **`claude login` 済み + `OPENAI_API_KEY` 設定済みの環境で `python run_example.py` を 1 回実走し、以下が成立することを確認**: (a) 終了コード 0 (b) stdout に draft 文字列 (c) `score._overall` 数値（2 criterion の平均）(d) `rubric_items` 配列 | 手動実行 + stdout 記録 |

**合計 14 SC。全 PASS で Accept 基準とする。**

---

## 3. 実装方針（確定）

### Approach A'（確定）: generate → judge 2 ノード walking example

```yaml
# examples/self-improve/workflow.yaml（確定仕様）
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
      # prompt_ref を指定せず default system prompt を活用（rubric から自動生成）
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

- `prompts.yaml` は generate 用 system/user prompt のみ（judge 用はない）
- `run_example.py` で 2 ノード実行、stdout に draft / judge_result.score / _overall / reasoning を表示
- `judge.params.user_prompt_template` は省略し、judge handler が state の `draft` を自動で user prompt に含める default 挙動を使う（handler 実装仕様を確認して利用）

### 除外項目

- Approach B（judge 単独）→ 不採用（generate→judge の連結こそビジョンの核）
- Approach C（propose/apply を workflow 内ノード化）→ 不採用（設計思想と不整合）
- 参考 `rubric.yaml` の同梱 → 不採用（README コードブロックで紹介のみ）
- generate 側 Claude SDK 対応の README 記述 → 削除（llm handler は LiteLLM 体系、claude_agent_sdk provider は judge 専用のため誤情報になる）

---

## 4. PO 事前判断（E1-E8 確定）

### E1. `generate` ノードの provider（確定）

- **default**: OpenAI `gpt-4o-mini`（API key 要求）。既存 llm-basic/llm-structured と同等の扱い
- **README Customization**: 「Anthropic API key をお持ちなら `model.provider: anthropic, model.name: "claude-sonnet-4-xxx"` にも切替可」の LiteLLM 互換情報のみ記述
- **禁止**: 「generate も claude_agent_sdk に統一可能」の記述（llm handler は LiteLLM 体系、claude_agent_sdk provider 名は judge handler 専用）

### E2. rubric の表現（確定）

- **inline rubric を main ストーリーに採用**（workflow.yaml に直書き）
- **rubric.yaml 参考ファイルは同梱しない**（最小構成）
- **README バリエーション節**: `rubric_ref: "rubric.yaml#default"` による外部ファイル化の 1 段落コード例のみ

### E3. README での Propose/Apply サイクル（確定）

- **架空だが再現性ある擬似スクリプト**形式（実測ログのサニタイズは不要）
- 5-6 ステップで propose → judge → apply の 3 段を明示
- 例:
  ```
  Q: 「self-improve workflow を実行して judge の結果を教えて」
  A: (run_example.py 実行) → draft / score._overall=3.5 / reasoning
  Q: 「clarity のスコアが低いので prompt を改善して」
  A: (propose_update) → diff 提案
  Q: 「OK、apply して」
  A: (apply_update, golden_pass_required=True) → 更新完了
  ```

### E4. `run_example.py` 実装（確定）

- 他 example と同一テンプレート（`from yagra import Yagra` + `app.invoke(...)` + stdout）
- stdout で `judge_result.score._overall` を強調（差別化軸の体験）
- docstring は既存 example と同じく日本語

### E5. CI スコープ（確定）

- `validate-example.yml` の glob `examples/*/workflow.yaml` で自動検出（修正不要）
- `run_example.py` は CI 対象外（LLM 実走は手動スモーク SC-14 のみ）
- PM は **Step 1 で `yagra validate` のドライラン + `yagra[judge]` 不在環境での挙動確認**（CI 可用性リスク R3/R4 の初手検証）

### E6. README 言語（確定）

- **日本語主体**（既存 `examples/llm-structured/` 等と揃える）
- コード内文字列（prompt 等）は英語可（モデルへの入力として）

### E7. judge の prompt_ref（確定）

- **judge 側は `prompt_ref` を指定せず default system prompt を活用**（handler が rubric から自動生成）
- 学習効果: ユーザーが「rubric だけで動く」ことを体感できる。手書き prompt による誤誘導リスクも回避
- README で「prompt_ref を追加して custom system prompt を使う例」を補足的に 1 段落記述（必須ではない）

### E8. #25-28 との順序依存（確定）

- README に **`evaluate_traces` 等の MCP tool 追加予定**の 1-2 行の未来見通しを書く
- **特定 issue 番号は書かない**（プロダクトドキュメント整合性維持）
- 例: 「現時点では propose/apply は MCP の `propose_update` / `apply_update` 経由で操作します。将来、実行トレース全体を LLM で一括評価する `evaluate_traces` 等の tool 追加を予定しています」

---

## 5. 技術リスクと緩和策（PM 指摘の確認）

### R1: generate 側 provider 選択 → 緩和済み

- README では **LiteLLM の正しい provider 名**（`openai` / `anthropic`）のみ記述。claude_agent_sdk の匂わせは削除

### R2: Claude SDK `sonnet` alias の安定性 → 緩和済み

- default `sonnet` 採用、README に「フルモデル ID 差し替え例」を 1 行記述
- SC-14 の手動スモークで alias 解決可否を実測

### R3: validate-example CI で example 自動検出 → PM が Step 1 で確認

- glob `examples/*/workflow.yaml` への合致は確実な想定
- `yagra validate` が judge handler の rubric schema を許容するか初手で確認（`--bundle-root` 付きで dry-run）

### R4: `yagra[judge]` extra の CI 可用性 → PM が Step 1 で確認

- CI は `uv sync --locked --dev` のみ、judge extra は optional
- `yagra validate` が handler を実 import せず schema のみ検証するのが現仕様（既存 6 example が CI 緑の理由）
- Step 1 のドライランで「judge extra 不在でも validate 通過する」ことを確認。通らない場合は PO へエスカレーション

---

## 6. スコープ境界（やらない）

- MCP tool `evaluate_traces` の追加（#25 で別タスク）
- propose → judge → run_golden_tests → apply の E2E 統合テスト追加（#26 で別タスク）
- LLM-as-a-Judge の docs/sphinx ドキュメント（#27 で別タスク）
- `create_llm_handler` 等の Port 経由移行（#28 で別タスク）
- Claude SDK の API 変更対応（SDK 0.1.0 前提）
- 参考 `rubric.yaml` ファイルの同梱（README コードブロックのみで紹介）
- judge 用 `prompts.yaml` セクション（default system prompt を活用）

---

## 7. 進行計画（PM 実行）

1. **Step 0**: 環境確認（`git status` clean、Yagra main 最新、claude login 済み、`OPENAI_API_KEY` 設定確認）
2. **Step 1**: `yagra validate` ドライラン（R3/R4 確認 + rubric schema 許容確認）
3. **Step 2**: feature branch 作成 `feature/add-self-improve-example`
4. **Step 3**: Intent / Plan / Mission Brief 作成（`tasks/{TS}_*.md`）
5. **Step 4**: Developer 1 工程（PM 代行）: `workflow.yaml` / `prompts.yaml` / `run_example.py` / `README.md` / `CHANGELOG.md` 実装
6. **Step 5**: 品質ゲート: `uv run pre-commit run --all-files` + `uv run pytest`（SC-11, SC-12）
7. **Step 6**: 手動スモーク（SC-14）: `claude login` 済み環境で `python run_example.py` 実走
8. **Step 7**: PR 作成 + CI 緑確認（`validate-examples` job が self-improve を検出・緑）
9. **Step 8**: PMO レビュー（PM 代行）: DoD 14 項目の checklist 照合、`tasks/{TS}_review-*.md` 作成
10. **Step 9**: PO への完了レポート（結果要約、PR URL、未対応事項）

**PM 環境制約**: Task(Agent) ツール不在が #3 / #4 / #23 で 3 回連続確認済み。PM が Developer/PMO を sequentially 代行する。ロール境界を出力で明確化する。

---

## 8. 参考資料

- `docs/product/vision.md` L70, L109（ビジョンの walking example 約束）
- `examples/llm-structured/` (4 ファイル構成テンプレート)
- `examples/multi-agent/` (複数ノード example のパターン)
- `src/yagra/handlers/judge.py`（#23 の実装 / rubric schema / output 構造）
- `src/yagra/handlers/judge.py` L583-726（`_rubric_to_json_schema` / `_validate_judge_output` = output 構造の authoritative ソース）
- `docs/agent-integration-guide.md` の「LLM-as-a-Judge」節（#23 で追加）
- 学習ログ `tasks/learnings.md`（judge Port / Lazy SDK import / async bridge / hybrid signature パターン）

---

## 9. 合意記録

- **2026-04-24 18:01 JST**: PO Brief ドラフト v1 作成
- **2026-04-24 18:05 JST**: PM Alignment Agent 1 往復完了（Q1-Q5 + R1-R4 + E6-E8 フィードバック取得）
- **2026-04-24 18:10 JST**: PO Brief 確定版 v2（Q1 の output 構造修正、E6-E8 追加判断、SC を 10→14 に増強）
- **次**: Phase 2c（PM Agent 起動）
