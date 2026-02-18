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
