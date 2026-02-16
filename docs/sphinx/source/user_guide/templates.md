# Template Library

Yagra provides ready-to-use templates for common workflow patterns. Templates let you bootstrap workflows quickly without writing YAML from scratch.

## Available Templates

### `branch`: Conditional Branching

**Pattern**: Classify → Branch → Merge

**Use Case**: Route requests based on intent (FAQ, general, support, etc.)

**Structure**:
- Classifier node determines intent
- Conditional edges route to specialized handlers
- All paths converge to finish node

**Initialize**:

```bash
yagra init --template branch --output my-branch-workflow
```

**Generated Files**:
- `workflow.yaml`: Workflow with classifier → faq_bot / general_bot → finish
- `prompts/branch_prompts.yaml`: System and user prompts

**Customize**:
1. Edit `classify_intent` logic in your Python code
2. Adjust prompts in `prompts/branch_prompts.yaml`
3. Add/remove branches by editing `edges` in `workflow.yaml`

---

### `loop`: Planner → Evaluator Loop

**Pattern**: Generate → Evaluate → Retry or Done

**Use Case**: Iterative refinement (planning, content generation, validation)

**Structure**:
- Planner generates output
- Evaluator checks quality
- Loop back to planner if needs improvement
- Exit to finish when quality is acceptable

**Initialize**:

```bash
yagra init --template loop --output my-loop-workflow
```

**Generated Files**:
- `workflow.yaml`: planner → evaluator → (retry/done)
- `prompts/loop_prompts.yaml`: Planner and evaluator prompts

**Customize**:
1. Implement quality criteria in `evaluator` handler
2. Set `max_iterations` in `evaluator` params
3. Adjust prompts for your domain (e.g., code generation, text summarization)

---

### `rag`: Retrieve → Rerank → Generate

**Pattern**: RAG (Retrieval-Augmented Generation)

**Use Case**: Question answering with document retrieval

**Structure**:
- Retrieve relevant documents from knowledge base
- Rerank documents by relevance
- Generate answer based on top documents

**Initialize**:

```bash
yagra init --template rag --output my-rag-workflow
```

**Generated Files**:
- `workflow.yaml`: retrieve → rerank → generate
- `prompts/rag_prompts.yaml`: Rerank and generation prompts

**Customize**:
1. Implement `retrieve_documents` with your vector DB
2. Implement `rerank_documents` with reranking model
3. Adjust `generate_answer` to format context and query

## Using Templates

### List Available Templates

```bash
yagra init --list
```

Output:

```
利用可能なテンプレート:
  - branch
  - loop
  - rag
```

### Initialize from Template

```bash
yagra init --template <template_name> --output <directory>
```

**Options**:
- `--template`: Template name (required)
- `--output`: Output directory (default: current directory)
- `--force`: Overwrite existing files

**Example**:

```bash
yagra init --template branch --output my-workflow
cd my-workflow
```

### Validate Generated Workflow

After initialization, Yagra automatically validates the generated workflow:

```bash
yagra init --template branch --output my-workflow
```

Output:

```
テンプレート 'branch' から初期化しました: /path/to/my-workflow

ワークフローを検証しています: /path/to/my-workflow/workflow.yaml
✓ ワークフローは valid です。
```

If validation fails, errors are displayed for you to fix.

### Run Generated Workflow

Templates generate ready-to-run workflows. You just need to implement handlers:

```python
from typing import TypedDict
from yagra import Yagra


class AgentState(TypedDict, total=False):
    query: str
    intent: str
    answer: str
    __next__: str


def classify_intent(state: AgentState, params: dict) -> dict:
    # Implement your classification logic
    intent = "faq" if "pricing" in state.get("query", "") else "general"
    return {"intent": intent, "__next__": intent}


def answer_faq(state: AgentState, params: dict) -> dict:
    # Use params["prompt"] and params["model"]
    return {"answer": "FAQ answer"}


def answer_general(state: AgentState, params: dict) -> dict:
    return {"answer": "General answer"}


def finish(state: AgentState, params: dict) -> dict:
    return {"answer": state.get("answer", "")}


registry = {
    "classify_intent": classify_intent,
    "answer_faq": answer_faq,
    "answer_general": answer_general,
    "finish": finish,
}

app = Yagra.from_workflow(
    workflow_path="my-workflow/workflow.yaml",
    registry=registry,
    state_schema=AgentState,
)

result = app.invoke({"query": "What's the pricing?"})
print(result["answer"])
```

## Extending Templates

Templates are starting points. Extend them for your use case:

### Add Nodes

Edit `workflow.yaml`:

```yaml
nodes:
  # ... existing nodes ...
  - id: "new_node"
    handler: "new_handler"
    params:
      prompt_ref: "../prompts/new_prompts.yaml#new"
```

Register the handler:

```python
def new_handler(state: AgentState, params: dict) -> dict:
    # Your logic
    return {"result": "value"}

registry["new_handler"] = new_handler
```

### Add Branches

Add conditional edges in `workflow.yaml`:

```yaml
edges:
  # ... existing edges ...
  - source: "classifier"
    target: "new_node"
    condition: "new_intent"
```

Update classifier to return new condition:

```python
def classify_intent(state: AgentState, params: dict) -> dict:
    if "keyword" in state["query"]:
        return {"intent": "new_intent", "__next__": "new_intent"}
    # ... existing logic ...
```

### Combine Templates

Mix patterns from multiple templates:

1. Initialize from one template (e.g., `branch`)
2. Add loop logic from `loop` template
3. Integrate retrieval step from `rag` template

## Template Design Principles

Yagra templates follow these principles:

1. **Minimal but complete**: Templates are fully functional out of the box
2. **Clear separation**: Workflow YAML + prompt YAML, no inline prompts
3. **Best practices**: Use `prompt_ref`, inline model config, validation-ready
4. **Domain-agnostic**: Templates use generic placeholders (adjust for your domain)

## Creating Custom Templates

Want to contribute a new template? See [Contributing](../contributing.md) for guidelines.

**Template requirements**:
- Must include `workflow.yaml` and `prompts/<template>_prompts.yaml`
- Must pass `yagra validate` without errors
- Should demonstrate a common pattern (not overly specific)
- Should include clear documentation

## Next Steps

- [Workflow YAML Reference](workflow_yaml.md)
- [Branching & Loops](branching_loops.md)
- [CLI Reference](../cli_reference.md)
- [Examples](../examples.md)
