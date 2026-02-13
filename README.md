# Graphyml: Declarative LangGraph Builder

Graphyml は、YAML 定義から LangGraph の `StateGraph` を構築・実行する Python ライブラリです。
フロー構造とプロンプト/モデル設定をコードから分離し、YAML 差し替えだけでワークフローを切り替えられます。

## 主な特徴

- Schema-Driven: Pydantic による YAML 検証で記述ミスを早期検知
- Registry Pattern: YAML の `handler` 名と Python callable を疎結合に接続
- Zero-Boilerplate: `Graphyml.from_workflow(...)` で構築コードを最小化

## 要件

- Python 3.12+
- `uv`

## セットアップ

```bash
git clone https://github.com/shogo-hs/Graphyml.git
cd Graphyml
uv sync --dev
```

## クイックスタート

### 1. ノード実装と Registry を用意する

```python
from graphyml import Graphyml
from graphyml.adapters.outbound import InMemoryNodeRegistry


def classify_intent(state: dict, params: dict) -> dict:
    query = state.get("query", "")
    return {"intent": "faq" if "料金" in query else "general"}


def generate_answer(state: dict, params: dict) -> dict:
    intent = state.get("intent", "general")
    return {"answer": f"intent={intent}"}


registry = InMemoryNodeRegistry(
    {
        "classify_intent": classify_intent,
        "generate_answer": generate_answer,
    }
)
```

### 2. Workflow YAML を定義する

`workflows/support.yaml`

```yaml
version: "1.0"
start_at: classify
end_at: [answer]
nodes:
  - id: classify
    handler: classify_intent
  - id: answer
    handler: generate_answer
edges:
  - source: classify
    target: answer
```

### 3. 実行する

```python
app = Graphyml.from_workflow("workflows/support.yaml", registry=registry)
result = app.invoke({"query": "料金を教えてください"})
print(result["answer"])
```

## YAML 仕様（要点）

トップレベル:

- `version: str`
- `start_at: str`
- `end_at: list[str]`
- `nodes: list[NodeSpec]`
- `edges: list[EdgeSpec]`
- `params: dict[str, Any]`（任意）

`NodeSpec`:

- `id: str`
- `handler: str`
- `params: dict[str, Any]`（任意）

`EdgeSpec`:

- `source: str`
- `target: str`
- `condition: str | null`（任意、条件分岐用）

### 分割参照（prompt/model）

workflow の `params` にカタログを定義し、ノード側で `*_ref` を指定できます。

- `params.prompt_catalog`
- `params.model_catalog`
- `node.params.prompt_ref`
- `node.params.model_ref`

例:

```yaml
params:
  prompt_catalog: "../prompts/support_prompts.yaml"
  model_catalog: "../models/openai_models.yaml"

nodes:
  - id: planner
    handler: planner_loop_handler
    params:
      prompt_ref: planner
      model_ref: default
```

## 同梱サンプル

- `examples/workflows/branch-inline.yaml`
  - 条件分岐（`condition`）で遷移先を切り替える例
- `examples/workflows/loop-split.yaml`
  - ループ + 条件分岐 + 分割参照の例
- `examples/prompts/support_prompts.yaml`
- `examples/models/openai_models.yaml`

## 開発コマンド

```bash
uv run ruff check .
uv run mypy .
uv run pytest -q
uv run pre-commit run --all-files
```

## ライセンスと変更履歴

- ライセンス: `LICENSE`（MIT）
- 変更履歴: `CHANGELOG.md`

## エージェント実行規約

エージェント運用ルールは `AGENTS.md` を参照してください。
