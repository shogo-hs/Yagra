# Tool-Use Workflow Example

LLM がツール呼び出しの要否を判断し、必要に応じて外部処理を経由するパターンのサンプルです。

## フロー

```
planner -[use_tool]→ tool_executor → synthesizer → finish
        -[direct]→   synthesizer   → finish
```

| ノード | 役割 |
|--------|------|
| planner | ツール使用の要否を判断（use_tool / direct） |
| tool_executor | ツールを実行（検索、API、DB クエリなど） |
| synthesizer | ツール結果を統合して最終回答を作成 |
| finish | ワークフロー終了 |

## セットアップ

```bash
export OPENAI_API_KEY="your-api-key"
python run_example.py
```

## 実際のツールに置き換える

`run_example.py` の `make_tool_executor_handler()` 内のモック実装を、
実際のツール呼び出しに差し替えてください。

```python
def handler(state: dict) -> dict:
    question = state.get("question", "")
    # 例: 検索 API を呼び出す
    result = my_search_api(question)
    return {**state, "tool_result": result}
```

## テンプレートとして使用

```bash
yagra init --template tool-use --output ./my-workflow
```
