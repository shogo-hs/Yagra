# llm-streaming サンプル

`create_streaming_llm_handler()` を使って LLM のレスポンスをストリーミングで受け取るサンプルです。

## 概要

このサンプルでは以下を示します：

- `create_streaming_llm_handler()` の基本的な使い方
- ストリーミングレスポンスの逐次処理（チャンクごとに出力）
- ストリーミングレスポンスのバッファリング（全テキストを一括取得）

## ファイル構成

```
examples/llm-streaming/
├── workflow.yaml   # ワークフロー定義
├── prompts.yaml    # プロンプト定義
├── run_example.py  # 実行スクリプト
└── README.md       # このファイル
```

## セットアップ

```bash
# yagra[llm] をインストール
uv sync --extra llm
```

## 実行

```bash
OPENAI_API_KEY=<your-key> uv run python examples/llm-streaming/run_example.py
```

## ハンドラーの使い方

### 基本（逐次処理）

```python
from yagra.handlers import create_streaming_llm_handler

handler = create_streaming_llm_handler(retry=3, timeout=60)
registry = {"streaming_llm": handler}

result = handler(state, params)
for chunk in result["response"]:
    print(chunk, end="", flush=True)
```

### バッファリング

```python
result = handler(state, params)
full_text = "".join(result["response"])
print(full_text)
```

> **注意**: Generator は一度しか消費できません。`for chunk in ...` または `"".join(...)` のどちらか一方だけ使用してください。

## ハンドラー比較

| ハンドラー | 戻り値 | 用途 |
|---|---|---|
| `create_llm_handler()` | `str` | テキスト生成（全文返却） |
| `create_structured_llm_handler()` | `BaseModel` インスタンス | 型安全な構造化出力 |
| `create_streaming_llm_handler()` | `Generator[str]` | 逐次ストリーミング出力 |

## YAML 設定

```yaml
nodes:
  - id: "stream_chat"
    handler: "streaming_llm"
    params:
      prompt_ref: "prompts.yaml#chat"
      model:
        provider: "openai"
        name: "gpt-4o"
        kwargs:
          temperature: 0.7
          # stream: false  # 明示的に無効化する場合のみ指定（デフォルトは true）
      input_keys: ["query"]
      output_key: "response"
```

## カスタマイズ

```python
# タイムアウトを延長（長文生成時）
handler = create_streaming_llm_handler(retry=3, timeout=120)

# 別プロバイダー（Anthropic）
# workflow.yaml の model.provider を "anthropic"、name を "claude-3-haiku-20240307" に変更
```
