# LLM Handler Basic Example

## 概要

このサンプルは、Yagra の LLM ハンドラーユーティリティを使った最も基本的な例です。
YAML 定義だけで LLM ノードを実行できることを示します。

## 機能

- `create_llm_handler()` による汎用 LLM ハンドラーの作成
- YAML での LLM ノード定義（プロンプト、モデル、入出力設定）
- プロンプトの外部ファイル参照（`prompt_ref`）
- litellm による 100+ LLM プロバイダー対応

## セットアップ

### 1. Yagra を LLM サポート付きでインストール

```bash
pip install 'yagra[llm]'
```

または uv を使用:

```bash
uv pip install 'yagra[llm]'
```

### 2. OpenAI API キーを設定

```bash
export OPENAI_API_KEY="your-api-key"
```

## 実行

```bash
cd examples/llm-basic
python run_example.py
```

期待される出力:

```
Creating LLM handler...
Loading workflow from: /path/to/examples/llm-basic/workflow.yaml

Executing workflow with input: {'user_name': 'Alice'}

============================================================
Response:
============================================================
Hello Alice! It's wonderful to meet you! I hope you're having a great day!
============================================================
```

## ファイル構成

```
examples/llm-basic/
├── workflow.yaml       # ワークフロー定義
├── prompts.yaml        # プロンプト定義
├── run_example.py      # 実行スクリプト
└── README.md           # このファイル
```

### workflow.yaml

LLM ノードを含むワークフロー定義。`handler: "llm"` で LLM ハンドラーを指定し、
`params` でプロンプト、モデル、入出力キーを設定します。

```yaml
version: "1.0"
start_at: "greeting"
end_at:
  - "greeting"

nodes:
  - id: "greeting"
    handler: "llm"
    params:
      prompt_ref: "prompts.yaml#greeting"
      model:
        provider: "openai"
        name: "gpt-4"
        kwargs:
          temperature: 0.7
      output_key: "response"

edges: []
```

### prompts.yaml

プロンプト定義。`workflow.yaml` から `prompt_ref` で参照されます。
`{user_name}` のような変数は、プロンプトテンプレートから自動検出されてステート値で置換されます。

```yaml
greeting:
  system: "You are a friendly assistant."
  user: "Hello! My name is {user_name}. Please greet me warmly."
```

### run_example.py

LLM ハンドラーを作成し、レジストリに登録して実行するスクリプト。

## カスタマイズ

### モデルの変更

`workflow.yaml` の `model` セクションを編集:

```yaml
model:
  provider: "anthropic"  # または "openai", "azure", "gemini" など
  name: "claude-3-opus-20240229"
  kwargs:
    temperature: 0.5
    max_tokens: 1000
```

### プロンプトの変更

`prompts.yaml` を編集してプロンプトをカスタマイズ:

```yaml
greeting:
  system: "You are a professional business assistant."
  user: "Please provide a formal greeting for {user_name}."
```

### リトライとタイムアウトの調整

`run_example.py` の `create_llm_handler()` 呼び出しを編集:

```python
llm_handler = create_llm_handler(retry=5, timeout=60)
```

## トラブルシューティング

### ImportError: litellm is not installed

```bash
pip install 'yagra[llm]'
```

### OPENAI_API_KEY が未設定

```bash
export OPENAI_API_KEY="your-api-key"
```

### API エラー

- API キーが正しいことを確認
- API クォータが残っていることを確認
- ネットワーク接続を確認

## 次のステップ

- [構造化出力サンプル](../llm-structured/) (Coming soon in M-15)
- [ストリーミングサンプル](../llm-streaming/) (Coming soon in M-16)
- [公式ドキュメント](https://shogo-hs.github.io/Yagra/)
