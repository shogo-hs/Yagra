# Yagra エージェント統合ガイド

このガイドでは、コーディングエージェント（Claude、GPT-4 等）が Yagra を使ってワークフロー YAML を自律的に生成・検証・修正するための手順と例を説明します。

## 前提

- Yagra がインストール済み (`pip install yagra` または `uv add yagra`)
- Python 3.12+

## エージェントが利用できる CLI ツール

| コマンド | 説明 | 典型的な使い方 |
|---|---|---|
| `yagra schema` | GraphSpec の JSON Schema を出力 | スキーマを取得して YAML 生成の参考にする |
| `yagra handlers --format json` | 組み込みハンドラーの params スキーマを出力 | 使用可能なパラメータを発見する |
| `yagra init --list` | 利用可能なテンプレート一覧を表示 | 典型パターンの雛形を取得する |
| `yagra init --template <name>` | テンプレートから YAML を生成 | 雛形からカスタマイズする |
| `yagra validate --workflow <path> --format json` | YAML を検証して JSON で結果を返す | 修正ループでエラーを確認する |
| `yagra validate --workflow - --format json` | stdin から YAML を検証（パイプ対応）| 一時ファイルなしで検証する |
| `yagra explain --workflow <path> --format json` | ワークフローの実行パス・変数フローを静的解析して出力 | 生成した YAML の実行経路・依存変数を把握する |
| `yagra visualize --workflow <path>` | ワークフローを HTML で可視化 | 生成した YAML の構造を把握する |

## ワークフロー生成→検証→修正ループ

エージェントが Yagra ワークフローを生成する際の標準フローは以下のとおりです:

```
1. yagra schema         → スキーマ取得
2. yagra handlers       → ハンドラー params 取得
3. YAML 生成            → エージェントが YAML を生成
4. yagra validate       → 検証（JSON 出力）
5. エラーがあれば修正   → issues の message/context を読んで修正
6. yagra validate       → 再検証（is_valid: true を確認）
7. 完了
```

## Worked Example: テキスト翻訳ワークフローの生成

### Step 1: スキーマを取得する

```bash
yagra schema > schema.json
```

または、エージェントが直接取得する場合:

```bash
yagra schema | python3 -c "import sys,json; s=json.load(sys.stdin); print(json.dumps(s, indent=2, ensure_ascii=False))"
```

### Step 2: 利用可能なハンドラーを確認する

```bash
yagra handlers --format json
```

出力例（抜粋）:
```json
{
  "handlers": [
    {
      "name": "llm",
      "description": "LLM テキスト出力ハンドラー。create_llm_handler() で生成する",
      "params_schema": {
        "type": "object",
        "properties": {
          "prompt": { "description": "プロンプト定義" },
          "model": { "description": "使用する LLM モデル名" },
          "output_key": { "description": "出力を格納するステートキー名", "default": "output" }
        },
        "required": ["model"]
      }
    }
  ]
}
```

### Step 3: YAML を生成する（エージェントの出力例）

エージェントが以下の YAML を生成したとします:

```yaml
# translate_workflow.yaml
version: "1.0"
start_at: translate
end_at:
  - translat  # タイポ（意図的な誤り）
nodes:
  - id: translate
    handler: llm
    params:
      prompt: "以下のテキストを英語に翻訳してください:\n\n{text}"
      model: gpt-4o-mini
      output_key: translation
edges: []
```

### Step 4: 検証する

```bash
yagra validate --workflow translate_workflow.yaml --format json
```

出力:
```json
{
  "is_valid": false,
  "issues": [
    {
      "code": "structure_error",
      "message": "end_at が未定義ノードを参照しています: translat",
      "location": ["end_at", 0],
      "severity": "error",
      "context": {
        "actual_value": "translat",
        "available_values": ["translate"],
        "suggestion": "translate"
      }
    }
  ]
}
```

### Step 5: エラーを修正する

`issues[0].context.suggestion` が `"translate"` を示しているので、エージェントは以下のように修正します:

```yaml
version: "1.0"
start_at: translate
end_at:
  - translate  # 修正済み
nodes:
  - id: translate
    handler: llm
    params:
      prompt: "以下のテキストを英語に翻訳してください:\n\n{text}"
      model: gpt-4o-mini
      output_key: translation
edges: []
```

再検証:

```bash
yagra validate --workflow translate_workflow.yaml --format json
```

出力:
```json
{
  "is_valid": true,
  "issues": []
}
```

### stdin を使ったパイプライン例

一時ファイルを使わずに生成→検証を行う場合:

```bash
# エージェントが YAML を生成して直接パイプに流す
cat <<'EOF' | yagra validate --workflow - --format json
version: "1.0"
start_at: translate
end_at:
  - translate
nodes:
  - id: translate
    handler: llm
    params:
      prompt: "translate {text}"
      model: gpt-4o-mini
edges: []
EOF
```

## エージェント向けシステムプロンプト例

以下のプロンプトをシステムプロンプトに追加することで、エージェントが Yagra YAML を生成するよう指示できます:

```
あなたは Yagra ワークフロー YAML を生成するエキスパートです。

Yagra ワークフローを生成する際は、以下の手順に従ってください:

1. `yagra schema` で JSON Schema を取得してフィールドの意味を確認する
2. `yagra handlers --format json` で使用可能なハンドラーと params を確認する
3. 要件に合った YAML を生成する
4. `yagra validate --workflow <path> --format json` で検証し、is_valid が true になるまで修正する

検証エラーが返った場合は、issues 配列の各要素を確認してください:
- `message`: エラーの説明
- `location`: エラーが発生したフィールドのパス
- `context.suggestion`: 修正候補（ノード ID ミスの場合に提示される）
- `context.available_values`: 利用可能な値の一覧

Yagra YAML の基本構造:
- `version`: "1.0" を指定
- `start_at`: 最初に実行するノードの id
- `end_at`: 終了ノードの id リスト
- `nodes`: ノード定義のリスト（id, handler, params）
- `edges`: エッジ定義のリスト（source, target, condition）
```

## 利用可能なテンプレート

```bash
yagra init --list
```

テンプレートを雛形として使用する場合:

```bash
yagra init --template branch --output ./my_workflow/
```

生成された `workflow.yaml` を要件に合わせてカスタマイズし、`yagra validate` で検証してください。

利用可能なテンプレート:

| テンプレート名 | 説明 |
|---|---|
| `branch` | 条件分岐パターン |
| `loop` | Planner → Evaluator ループパターン |
| `rag` | Retrieve → Rerank → Generate の RAG パターン |

## MCP サーバーを使った統合

Yagra は MCP（Model Context Protocol）サーバーを提供しており、Claude などの MCP 対応エージェントが直接ツールとして呼び出せます。

インストール（mcp オプション付き）:

```bash
uv add "yagra[mcp]"
```

MCP サーバーの起動:

```bash
yagra mcp
```

利用可能な MCP ツール:

| ツール名 | 説明 |
|---|---|
| `validate_workflow` | YAML 文字列を検証して結果を返す |
| `explain_workflow` | YAML 文字列を解析して実行情報を返す |
| `list_templates` | 利用可能なテンプレート名を返す |
| `list_handlers` | 組み込みハンドラーの params スキーマを返す |
| `get_traces` | 実行トレースを取得する |
| `analyze_traces` | 複数トレースの集約サマリを生成する |
| `propose_update` | YAML 修正差分を生成しプレビューする |
| `apply_update` | 提案された YAML 変更を適用する |
| `rollback_update` | 適用済み変更をロールバックする |
| `run_golden_tests` | ゴールデンケースに基づく回帰テストを実行する |

## ゴールデンテスト（回帰検証）

ゴールデンテストは、ワークフロー YAML の変更後に既存の動作が壊れていないかを検証する仕組みです。LLM ノードはモック応答で差し替えるため、API 呼び出しなしで決定論的にテストできます。同一ハンドラー名（例: `handler: "llm"`）を使う複数ノードがある場合も、`node_id` 単位でモックが解決されるため競合しません。

### CLI によるゴールデンテスト

```bash
# 成功したトレースからゴールデンケースを保存
yagra golden save \
  --trace .yagra/traces/translate/translate_20260221T120000_a1b2c3d4.json \
  --name happy-path \
  --strategy translate:structural \
  --strategy format:exact

# 保存済みゴールデンケースの一覧を表示
yagra golden list

# 特定のワークフローに対してゴールデンテストを実行
yagra golden test --workflow workflows/translate.yaml

# 特定のケースのみ実行
yagra golden test --workflow workflows/translate.yaml --name happy-path

# JSON 形式で結果を出力
yagra golden test --workflow workflows/translate.yaml --format json
```

`--strategy` は繰り返し指定可能で、`node_id:strategy` 形式（`exact` / `structural` / `skip` / `auto`）を受け付けます。

### MCP ツール `run_golden_tests` によるエージェント統合

エージェントは `run_golden_tests` MCP ツールを使って、ワークフロー変更提案の回帰テストを自動実行できます。

**最適化サイクルでの利用フロー**:

```
1. propose_update    → YAML 修正差分をプレビュー
2. run_golden_tests  → ゴールデンケースで回帰テスト
3. (全件 passed なら) apply_update → 変更を適用
   (失敗があれば) 提案を修正して 1 に戻る
```

**`run_golden_tests` の入力パラメータ**:

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `workflow_path` | string | Yes | ワークフロー YAML のパス |
| `case_name` | string | No | 特定のケース名（省略時は全ケース実行） |
| `golden_dir` | string | No | ゴールデンケースのディレクトリ（デフォルト: `.yagra/golden/`） |

**レスポンス例**（全件パス時）:

```json
{
  "results": [
    {
      "case_name": "happy-path",
      "passed": true,
      "execution_path_match": true,
      "node_results": [
        {"node_id": "translate_node", "status": "pass", "strategy_used": "structural"},
        {"node_id": "format_node", "status": "pass", "strategy_used": "exact"}
      ],
      "summary": "All 2 nodes passed"
    }
  ],
  "total": 1,
  "passed": 1,
  "failed": 0
}
```

## 最適化サイクルの自律実行

コーディングエージェント（Claude Code、Cursor、Copilot 等）が Yagra の最適化サイクル（Build → Run → Analyze → Update）を自律的に実行するためのプロンプト例と MCP ツール呼び出し手順です。

### エージェント向けシステムプロンプト例

以下のプロンプトをシステムプロンプトに追加することで、エージェントが最適化サイクルを自律実行できます:

```
あなたは Yagra ワークフローの最適化エキスパートです。

ユーザーから最適化の依頼を受けたら、以下の手順に従って自律的にサイクルを実行してください:

【ステップ 1: トレース分析】
1. `analyze_traces` ツールでトレースを集約分析する
   - 引数: workflow_name（ワークフロー名）, limit（直近 N 件）
   - 注目点: error_rate が高いノード, avg_latency が大きいノード, suggestions フィールド

【ステップ 2: 改善提案】
2. 分析結果をもとに `propose_update` ツールで YAML 差分を生成する
   - 引数: workflow_path（YAML パス）, instruction（改善指示を具体的に記述）
   - 必ず diff フィールドを確認し、変更内容を人間に説明してから次へ進む
   - session_id を記録しておく

【ステップ 3: 回帰テスト】
3. `run_golden_tests` ツールでゴールデンケースを実行する
   - 引数: workflow_path（同上）
   - passed が total と一致しない場合は propose_update をやり直す

【ステップ 4: 適用またはロールバック】
4a. 全件 passed の場合: `apply_update` ツールで変更を適用する
    - 引数: session_id（ステップ 2 で取得したもの）
4b. テスト失敗が解消できない場合: ユーザーに報告し、`rollback_update` でセッションを破棄する

【重要な制約】
- apply_update を実行する前に必ず run_golden_tests を実行する
- diff の内容をユーザーに確認なしに apply しない（ユーザーに diff を提示して承認を得る）
- rollback_update は apply_update 後に問題が発覚した場合にも使用できる
```

### MCP ツール呼び出し順序（最小フロー）

```
1. analyze_traces(workflow_name, limit=20)
      ↓ 問題ノードと改善点を特定
2. propose_update(workflow_path, instruction)
      ↓ session_id を取得・diff をユーザーに提示
3. run_golden_tests(workflow_path)
      ↓ 全件 passed を確認
4. apply_update(session_id)
      ↓ ワークフロー YAML を更新
```

テストが失敗した場合のフロー:

```
3. run_golden_tests → 失敗
      ↓
   propose_update(instruction を修正して再提案)
      ↓
3. run_golden_tests → 再実行
      ↓ 全件 passed を確認
4. apply_update
```

### トレースがない場合の対応

初回実行でトレースが蓄積されていない場合は、`get_traces` でトレースファイルが存在するか確認してください。存在しない場合はまずワークフローを実行してトレースを生成します:

```python
app = Yagra.from_workflow("workflow.yaml", registry, observability=True)
app.invoke({"query": "テスト入力"}, trace=True)
# → .yagra/traces/ 以下に JSON ファイルが生成される
```

### ゴールデンケースがない場合の対応

`run_golden_tests` を実行する前に、少なくとも 1 件のゴールデンケースを保存してください:

```bash
# 最新のトレースファイルを確認
ls -lt .yagra/traces/<workflow_name>/

# ゴールデンケースとして保存
yagra golden save \
  --trace .yagra/traces/<workflow_name>/<trace_file>.json \
  --name happy-path
```

または `yagra golden list` でケースが登録済みかどうかを確認できます。

### 完全なエンドツーエンドの例（エージェント視点）

```
ユーザー: 「translate ワークフローのプロンプトを改善して」

エージェントの実行手順:
1. analyze_traces(workflow_name="translate", limit=20)
   → answer_translate ノードで空文字列が返るケースを発見

2. propose_update(
     workflow_path="workflow.yaml",
     instruction="translate ノードのシステムプロンプトに、空入力の場合は空文字列を返すよう指示を追加する"
   )
   → session_id: "sess_abc123", diff を取得

3. ユーザーに diff を提示:
   「以下の変更を提案します:
    - system prompt に 'If the input text is empty, return an empty string.' を追加
    適用しますか?」

4. ユーザー承認後:
   run_golden_tests(workflow_path="workflow.yaml")
   → 1 passed, 0 failed

5. apply_update(session_id="sess_abc123")
   → ワークフロー YAML が更新されました
```
