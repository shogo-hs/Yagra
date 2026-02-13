# Yagra: Declarative LangGraph Builder

Yagra は、YAML 定義から LangGraph の `StateGraph` を構築・実行する Python ライブラリです。
フロー制御（分岐・ループ）とノード設定（prompt/model など）をコードから分離し、
`workflow.yaml` の差し替えで挙動を切り替えられます。

## 公開運用ポリシー

- パッケージ配布: Public（PyPI）
- ソースリポジトリ: Private（GitHub）
- 利用者向け導線は PyPI を正とし、リポジトリ参照は必須としません。

## 主な特徴

- Schema-Driven: Pydantic で YAML 構造を検証
- Registry Pattern: `handler` 文字列と Python callable を疎結合に接続
- Typed State: `state_schema` に TypedDict/Pydantic などの状態スキーマを指定可能
- Zero-Boilerplate: `Yagra.from_workflow(...)` で構築コードを最小化

## インストール（利用者向け）

- Python 3.12+

```bash
pip install yagra
```

## 開発セットアップ（メンテナー向け）

この手順は private リポジトリへのアクセス権があるメンテナー向けです。

```bash
git clone https://github.com/shogo-hs/Graphyml.git
cd Graphyml
uv sync --dev
```

## クイックスタート（条件分岐あり）

### 1. State とノード関数を定義

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
    model = params.get("model", {})
    return {"answer": f"GENERAL via {model.get('name', 'unknown')}"}


def finish(state: AgentState, params: dict) -> dict:
    _ = params
    return {"answer": state.get("answer", "")}
```

### 2. Workflow YAML を定義

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
    params:
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
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

### 3. Registry と実行

`registry` は `dict[str, callable]` を直接渡せます（`InMemoryNodeRegistry` は内部で自動利用）。

```python
registry = {
    "classify_intent": classify_intent,
    "answer_faq": answer_faq,
    "answer_general": answer_general,
    "finish": finish,
}

app = Yagra.from_workflow(
    workflow_path="workflows/support.yaml",
    registry=registry,
    state_schema=AgentState,
)

result = app.invoke({"query": "料金を教えて"})
print(result["answer"])
```

## API

### `Yagra.from_workflow(...)`

```python
Yagra.from_workflow(
    workflow_path: str | PathLike,
    registry: NodeRegistryPort | Mapping[str, NodeHandler],
    bundle_root: str | PathLike | None = None,
    state_schema: Any = dict,
) -> Yagra
```

- `workflow_path`: 入口となる workflow YAML
- `registry`: `NodeRegistryPort` 実装、または `dict[str, callable]`
- `bundle_root`: 分割参照解決の基準ディレクトリ（省略時は workflow の親）
- `state_schema`: LangGraph の状態スキーマ（既定 `dict`）

### `Yagra.invoke(...)`

```python
Yagra.invoke(state: Mapping[str, Any]) -> dict[str, Any]
```

## 仕様上の契約（Implicit Contracts）

### 1. 条件分岐の契約

- `edges[].condition` は分岐ラベルです。
- 分岐元ノードは `{"__next__": "<condition-label>"}` を state update として返します。
- 例: `condition: "faq"` がある場合、`__next__` は `"faq"` を返す必要があります。

### 2. catalog 参照解決の契約

- `prompt_ref`/`model_ref` は実行前に解決されます。
- handler が受け取る `params` には解決済み値が入ります。
  - `params["prompt"]`
  - `params["model"]`
- 参照形式:
  - `<key>`（`workflow.params.prompt_catalog` / `model_catalog` を使用）
  - `<path>#<key.path>`（明示参照）

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

### 3. `end_at` の挙動

- `end_at` は「終了ノードIDのリスト」です（複数可）。
- Yagra は各ノードを LangGraph の finish point として登録します。
- YAML 上で `END` という特別ノードを直接書く仕様ではありません。

### 4. ノード関数シグネチャ

Yagra は次の順で呼び出しを試みます。

1. `handler(state, params)`
2. `handler(state)`

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
- `condition: str | null`（任意）

## 同梱サンプル

- `examples/workflows/branch-inline.yaml`
  - 条件分岐の最小例
- `examples/workflows/loop-split.yaml`
  - ループ + 条件分岐 + `prompt_ref`/`model_ref` 分割参照
- `examples/prompts/support_prompts.yaml`
- `examples/models/openai_models.yaml`

## 開発コマンド

```bash
uv run ruff check .
uv run mypy .
uv run pytest -q
uv run pre-commit run --all-files
```

## PyPI 公開

公開ワークフローは `v*` タグ push をトリガーに実行されます。

- workflow: `.github/workflows/publish.yml`
- build: `uv build`
- 検証: `uvx twine check dist/*`
- publish: `pypa/gh-action-pypi-publish`（OIDC）

前提:

- PyPI 側で private repository `shogo-hs/Graphyml` を Trusted Publisher として登録しておく
- GitHub Actions の `pypi` environment が利用可能である
- Git タグ（`vX.Y.Z`）と `pyproject.toml` の `version` を一致させる

リリース実行例:

```bash
git tag v0.1.1
git push origin v0.1.1
```

## ライセンスと変更履歴

- ライセンス: `LICENSE`（MIT）
- 変更履歴: `CHANGELOG.md`

## エージェント実行規約

エージェント運用ルールは `AGENTS.md` を参照してください。
