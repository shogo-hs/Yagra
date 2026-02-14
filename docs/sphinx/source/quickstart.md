# Quickstart

Yagra は、workflow YAML と handler registry から LangGraph を構築して実行するライブラリです。  
このページでは最短で「インストール → workflow 定義 → 実行」までを確認します。

## 1. Install

```bash
pip install yagra
```

## 2. Define a Workflow YAML

`workflows/support.yaml`

```yaml
version: "1.0"
start_at: "classifier"
end_at:
  - "finish"

nodes:
  - id: "classifier"
    handler: "classify_intent"
  - id: "faq_bot"
    handler: "answer_faq"
    params:
      prompt:
        system: "pricing response"
  - id: "general_bot"
    handler: "answer_general"
  - id: "finish"
    handler: "finish"

edges:
  - source: "classifier"
    target: "faq_bot"
    condition: "faq"
  - source: "classifier"
    target: "general_bot"
    condition: "general"
  - source: "faq_bot"
    target: "finish"
  - source: "general_bot"
    target: "finish"
```

## 3. Register handlers and run

```python
from typing import TypedDict

from yagra import Yagra


class AgentState(TypedDict, total=False):
    query: str
    intent: str
    answer: str
    __next__: str


def classify_intent(state: AgentState, params: dict) -> dict:
    _ = params
    intent = "faq" if "料金" in state.get("query", "") else "general"
    return {"intent": intent, "__next__": intent}


def answer_faq(state: AgentState, params: dict) -> dict:
    prompt = params.get("prompt", {})
    return {"answer": f"FAQ: {prompt.get('system', '')}"}


def answer_general(state: AgentState, params: dict) -> dict:
    _ = params
    return {"answer": "GENERAL"}


def finish(state: AgentState, params: dict) -> dict:
    _ = params
    return {"answer": state.get("answer", "")}


app = Yagra.from_workflow(
    workflow_path="workflows/support.yaml",
    registry={
        "classify_intent": classify_intent,
        "answer_faq": answer_faq,
        "answer_general": answer_general,
        "finish": finish,
    },
    state_schema=AgentState,
)

result = app.invoke({"query": "料金を教えて"})
print(result["answer"])
```

## 4. CLI helpers (optional)

Workflow をブラウザで確認・編集したい場合は CLI を使えます。

```bash
yagra visualize --workflow workflows/support.yaml --output /tmp/workflow.html
yagra studio --port 8787
yagra studio --workflow workflows/support.yaml --port 8787
```

`yagra studio` 実行後は `http://127.0.0.1:8787/` を開いて編集できます。
Node Properties の `prompt yaml` から YAML ファイルを選ぶと prompt が自動読込されます。
未選択のまま `Apply Node Edit` すると workflow YAML と同階層の `prompts/` 配下に YAML が自動作成され、`prompt_ref` が自動設定されます。
`prompt key` を指定すると `prompt_ref` は `path#key` になり、作成される YAML は key 配下に `system/user` を持つ構造になります。
`model_ref` は廃止されているため、モデル設定は `nodes[].params.model` にインライン定義してください。

## Next

- API の詳細は `API Reference` ページを参照してください。
