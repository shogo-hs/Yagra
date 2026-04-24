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
| `yagra analyze [--workflow <name>] [--limit <n>]` | 実行トレースを集約してサマリを出力 | ノード別の遅延・エラー率を確認し改善点を発見する |

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
| `chat` | MessagesState と add_messages reducer を使ったシングルノードチャット |
| `loop` | Planner → Evaluator ループパターン |
| `parallel` | Send API を使った Fan-out/Fan-in マップリデュースパターン |
| `rag` | Retrieve → Rerank → Generate の RAG パターン |
| `subgraph` | 複数ワークフローを組み合わせるネストサブグラフパターン |
| `tool-use` | LLM が外部ツールを呼び出すかどうかを判断して実行するパターン |
| `multi-agent` | オーケストレーター・リサーチャー・ライターが協調するマルチエージェントパターン |
| `human-review` | `interrupt_before` によるヒューマン・イン・ザ・ループパターン |

## LLM-as-a-Judge ハンドラー (`judge`)

`judge` は、宣言的なルーブリック（評価基準）に対して入力を採点する組み込みハンドラーです。回答品質の評価、安全性チェック、A/B 比較などを YAML だけで構築できます。

### ルーブリック YAML の例

```yaml
# rubrics/quality.yaml
default:
  criteria:
    - name: "relevance"
      description: "回答が質問の意図に答えているか"
      scale:
        type: "integer"
        min: 1
        max: 5
    - name: "accuracy"
      description: "回答内容が事実として正確か"
      scale:
        type: "integer"
        min: 1
        max: 5
  require_reasoning: true
```

### ワークフローへの組み込み

```yaml
# workflows/judge.yaml
version: "1.0"
start_at: "judge"
end_at:
  - "judge"

nodes:
  - id: "judge"
    handler: "judge"
    params:
      rubric_ref: "rubrics/quality.yaml#default"
      provider: "claude_agent_sdk"   # default; "litellm" でも可
      model: "sonnet"                # provider に応じて識別子を変える
      prompt_ref: "prompts/judge.yaml#judge"  # user prompt の参照（下記注意事項を必ず参照）
      output_key: "judge_result"

edges: []
```

### ⚠ Prompt 解決の落とし穴（必読）

`judge` ハンドラーの prompt 仕様には、初見で間違えやすいポイントが 2 つある。walking example や新規ワークフロー生成で agent がつまずかないよう、必ず以下を把握する。

1. **default の user template は `"{query}"`**。`prompt_ref` / `prompt` を省略した場合、judge は `state["query"]` を user prompt に展開する。直前のノードが `output_key: "draft"` のように `query` 以外のキーに書き出していると、judge は空の入力を評価し「No content was provided」といった低スコアの reasoning を返す。対処は次のいずれか:
   - 直前ノードの `output_key` を `query` にする
   - `prompt_ref` を指定し、user template で実際の state key を参照する（例: `"Evaluate the following draft:\n\n{draft}"`）

   なお default の **system prompt は rubric から自動生成される**ため、user template だけを与えれば済むケースが多い。

2. **workflow YAML に inline `prompt:` を書くと validator が拒否する**。ハンドラー本体（`create_judge_handler` 内部）は `params["prompt"] = {"system": ..., "user": ...}` を受け付けるが、`yagra validate` / `Yagra.from_workflow` が通る前段の validator（`application/services/reference_resolver.py`）が inline 形式をブロックし、`"inline prompt is no longer supported; use prompt_ref to reference an external prompt file"` のエラーを返す。workflow YAML では必ず `prompt_ref: "<file>#<key>"` を使い、テンプレートは外部の prompts YAML（通例 `prompts.yaml` の `judge:` セクション）に置く。

```yaml
# prompts.yaml（judge の user prompt 例）
judge:
  user: "Evaluate the following draft:\n\n{draft}"
  # system は省略可（rubric から自動生成される）
```

walking example の実装例は `examples/self-improve/` を参照。

### Python 側の登録

```python
from yagra import Yagra
from yagra.handlers import create_judge_handler

# YAML の `params.provider` で provider を切り替え可能（DI 引数も受け付ける）
handler = create_judge_handler(retry=3, timeout=30)
registry = {"judge": handler}

yagra = Yagra.from_workflow("workflows/judge.yaml", registry)
result = yagra.invoke({"question": "...", "answer": "..."})

# 構造化スコアと推論コメントを取得
print(result["judge_result"])
# {
#   "score": {"relevance": 4, "accuracy": 5, "_overall": 4.5},
#   "reasoning": "...",
#   "rubric_items": [...]
# }
```

### Provider 切り替え

| Provider | 認証 | 必要なインストール | 備考 |
|---|---|---|---|
| `claude_agent_sdk` (default) | Claude サブスクリプション (no API key) | `uv add "yagra[judge]"` | `query()` がストリーミング |
| `litellm` | 各プロバイダーの API キー (環境変数) | 追加インストール不要 | `model: "openai/gpt-4o"` 形式 |

`claude_agent_sdk` は `claude-agent-sdk` パッケージを必要とします。未インストール時は構造化エラー `claude_agent_sdk_not_installed`（hint 付き）を fail-fast で返します。

#### LLM handlers (`llm` / `structured_llm` / `streaming_llm`) の provider 切り替え

judge handler と同じ Hybrid 解決は、`create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler` にも適用されます。

```yaml
nodes:
  - id: "chat"
    handler: "llm"
    params:
      prompt_ref: "prompts/chat.yaml#default"
      model:
        provider: "openai"
        name: "gpt-4o"
      output_key: "response"
      provider: "litellm"   # default; 省略可。"claude_agent_sdk" は structured_llm のみ対応
```

Python 側で dependency injection も可能です:

```python
from yagra.handlers import create_llm_handler
from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider

# 明示的な provider 注入（例: テスト時の fake 注入）
handler = create_llm_handler(provider=LiteLLMProvider(), retry=3, timeout=30)
```

サポート対応表:

| Handler | `litellm` | `claude_agent_sdk` |
|---|---|---|
| `llm` | ✅ | ❌（`complete_unsupported` で fail-fast） |
| `structured_llm` | ✅ | ✅ |
| `streaming_llm` | ✅ | ❌（`streaming_unsupported` で fail-fast） |
| `judge` | ✅ | ✅（default） |

未知の provider 名は構造化エラー `unknown_provider`（4-field payload: `{error, message, summary, hint}`）を返し、silent success を防ぎます。

### 出力構造とスコア集約

- `score`: 各 criterion 名をキーとした数値マップ。複数 criterion の場合は `_overall`（算術平均）が自動で付与されます。
- `reasoning`: `require_reasoning: true` の場合のみ必須。
- `rubric_items`: criterion ごとの個別スコアと、必要に応じた個別コメントの配列。

LLM 応答が必須項目を欠いた場合は構造化エラー `judge_output_validation_error` が即座に発生し、silent success を防ぎます（fail-fast 原則）。

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
2. 改善後の YAML を自ら生成し、`propose_update` ツールで差分をプレビューする
   - 引数: workflow_path（YAML パス）, candidate_yaml（改善後の YAML 全文）, reason（変更理由、任意）
   - `propose_update` は自然言語指示ではなく完成形の YAML を受け取る点に注意
   - 必ず diff・is_valid フィールドを確認し、変更内容を人間に説明してから次へ進む
   - candidate_yaml を手元に保持しておく（apply_update でそのまま使う）

【ステップ 3: 回帰テスト】
3. `run_golden_tests` ツールでゴールデンケースを実行する
   - 引数: workflow_path（同上）
   - passed が total と一致しない場合は candidate_yaml を修正して propose_update をやり直す

【ステップ 4: 適用またはロールバック】
4a. 全件 passed の場合: `apply_update` ツールで変更を適用する
    - 引数: workflow_path（YAML パス）, candidate_yaml（ステップ 2 で使った YAML）
    - 推奨: ステップ 3 の結果を `last_golden_result` として渡すと二重実行を回避できる
    - レスポンスの backup_id を記録しておく（ロールバック時に必要）
4b. apply 後に問題が発覚した場合: `rollback_update` で元に戻す
    - 引数: workflow_path, backup_id（apply_update レスポンスより）

【重要な制約】
- apply_update はデフォルトで run_golden_tests の成功（passed == total）を要求する（`golden_pass_required=True`）。passed != total の場合は `error: "golden_not_passed"` を返し、ワークフローファイルは書き換えられない
- ゴールデンケースが 1 件も存在しない場合は silent success を避けるため、`warnings: ["no_golden_cases_defined"]` 付きで apply が許可される。この warning が返ったらユーザーに明示し、ゴールデンケース未整備である旨を伝える
- ステップ 3 で取得した `run_golden_tests` の戻り値をそのまま `last_golden_result` として渡すと、apply_update 側で再実行を避けられる。省略時は apply_update が内部で run_golden_tests を実行する
- レガシーな強制スキップが必要な場合は `golden_pass_required=false` を明示する（非推奨）
- candidate_yaml の diff をユーザーに確認なしに apply しない（ユーザーに diff を提示して承認を得る）
- rollback_update は apply_update 後に問題が発覚した場合に使用する（テスト失敗時は apply 前に candidate_yaml を修正する）
```

### MCP ツール呼び出し順序（最小フロー）

```
1. analyze_traces(workflow_name, limit=20)
      ↓ 問題ノードと改善点を特定
2. [エージェントが改善後の YAML を生成]
      ↓
   propose_update(workflow_path, candidate_yaml, reason)
      ↓ diff・is_valid を確認・ユーザーに提示
3. run_golden_tests(workflow_path)
      ↓ 全件 passed を確認
4. apply_update(workflow_path, candidate_yaml)
      ↓ ワークフロー YAML を更新（backup_id を受け取る）
```

テストが失敗した場合のフロー:

```
3. run_golden_tests → 失敗
      ↓
   [candidate_yaml を修正]
      ↓
   propose_update(workflow_path, candidate_yaml_v2, reason)
      ↓
3. run_golden_tests → 再実行
      ↓ 全件 passed を確認
4. apply_update(workflow_path, candidate_yaml_v2)
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
   → translate ノードで空文字列が返るケースを発見

2. [エージェントが改善後の YAML を生成]
   system prompt に空入力ハンドリングの指示を追加した candidate_yaml を作成

3. propose_update(
     workflow_path="workflow.yaml",
     candidate_yaml="version: \"1.0\"\n...",
     reason="translate ノードのシステムプロンプトに空入力ハンドリングを追加"
   )
   → is_valid: true, diff を取得

4. ユーザーに diff を提示:
   「以下の変更を提案します:
    - system prompt に 'If the input text is empty, return an empty string.' を追加
    適用しますか?」

5. ユーザー承認後:
   golden_result = run_golden_tests(workflow_path="workflow.yaml")
   → 1 passed, 0 failed

6. apply_update(
     workflow_path="workflow.yaml",
     candidate_yaml="version: \"1.0\"\n...",
     last_golden_result=golden_result  # ステップ 5 の結果を再利用すると二重実行を回避できる
   )
   → success: true, backup_id: "workflow_20260222T130000_a1b2c3d4"
   → ワークフロー YAML が更新されました
```

### `apply_update` のゴールデンゲート

`apply_update` はデフォルトで `golden_pass_required=True` が有効となっており、`run_golden_tests` の `passed == total` を書き込み前に要求します。ゲートの挙動は以下の通り:

| 状況 | `golden_pass_required` | `last_golden_result` | 挙動 |
|------|:---:|:---:|------|
| 事前 `run_golden_tests` 済み（全 pass） | True | 結果 dict | dict を再利用して即 apply |
| 事前未実行 | True | None（省略） | 内部で `run_golden_tests` を実行して判定 |
| 事前 `run_golden_tests` 済み（fail あり） | True | 結果 dict | `error: "golden_not_passed"` を返し、ファイルは書き換えない |
| ゴールデンケース未定義（total == 0） | True | どちらでも | `success: true, warnings: ["no_golden_cases_defined"]` — ユーザーに明示して放置しない |
| レガシー互換 | False | - | ゴールデンゲートを完全スキップ（非推奨） |

`error: "golden_not_passed"` のレスポンスには以下のフィールドが含まれます:

```json
{
  "error": "golden_not_passed",
  "message": "Golden tests did not fully pass: 2/3 passed, 1 failed",
  "summary": {"total": 3, "passed": 2, "failed": 1},
  "hint": "run_golden_tests の失敗ケースを確認し、candidate_yaml を修正してから再度 apply_update を実行してください"
}
```

エージェントはこの構造化エラーを受け取ったら、失敗ケースを確認したうえで `candidate_yaml` を修正し、再び `propose_update` → `run_golden_tests` → `apply_update` のサイクルに戻ることを推奨します。

