# Human-in-the-Loop (HITL) Workflow Example

人間の確認・承認ステップを挟むワークフローパターンのサンプルです。

## ワークフロー構成

```
generator → [interrupt_before publisher] → [人間のレビュー] → publisher
```

- **generator**: コンテンツのドラフトを生成
- **publisher**: 人間の承認後にコンテンツを公開
- **interrupt_before: publisher**: publisher ノード実行前に自動で処理を中断

## 実行フロー

1. `yagra.invoke()` でワークフローを開始（generator 実行 → publisher 前で中断）
2. 人間がドラフトをレビューして承認/却下を判断
3. `yagra.resume(update={"approved": True, ...})` で結果を注入して再開

## セットアップ

```bash
pip install "yagra[llm]"
export OPENAI_API_KEY="your-api-key"
```

## 実行

```bash
python run_example.py
```

## カスタマイズ

### YAML で interrupt ポイントを変更する

```yaml
interrupt_before:
  - publisher   # publisher 前で中断（デフォルト）

# または実行後に中断
interrupt_after:
  - generator   # generator 実行後に中断
```

### checkpointer を永続化する

本番環境では `MemorySaver` の代わりに永続ストレージを使用します：

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string("postgresql://...")
yagra = Yagra.from_workflow(workflow_path, registry, checkpointer=checkpointer)
```

### スレッド ID でセッションを管理する

`thread_id` を使って複数の並行ワークフロー実行を管理できます：

```python
# セッション1
result1 = yagra.invoke(state1, thread_id="session-001")
yagra.resume(update=approval1, thread_id="session-001")

# セッション2（並行実行）
result2 = yagra.invoke(state2, thread_id="session-002")
yagra.resume(update=approval2, thread_id="session-002")
```
