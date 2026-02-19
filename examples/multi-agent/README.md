# Multi-Agent Workflow Example

複数の専門エージェントが協調して複雑なタスクを処理するパターンのサンプルです。

## フロー

```
orchestrator → researcher -[done]→ writer → finish
                          -[retry]→ researcher
```

| ノード | 役割 |
|--------|------|
| orchestrator | タスクを分解して調査プランを作成 |
| researcher | プランに従って情報収集（最大3回の再試行） |
| writer | 調査結果を整形して最終回答を作成 |
| finish | ワークフロー終了 |

## セットアップ

```bash
export OPENAI_API_KEY="your-api-key"
python run_example.py
```

## カスタマイズ

`prompts.yaml` の各プロンプトを書き換えることで、任意のマルチエージェントフローに応用できます。

## テンプレートとして使用

```bash
yagra init --template multi-agent --output ./my-workflow
```
