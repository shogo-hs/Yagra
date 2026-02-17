# Getting Started

This guide will help you install Yagra and build your first workflow.

## Installation

### Requirements

- Python 3.12 or later
- pip (or uv for faster installs)

### Install from PyPI

```bash
pip install yagra
```

Or with `uv`:

```bash
uv pip install yagra
```

### Install with LLM Support

To use the built-in LLM handler utilities (`create_llm_handler`, `create_structured_llm_handler`, `create_streaming_llm_handler`), install the optional `llm` extra:

```bash
pip install 'yagra[llm]'
```

Or with `uv`:

```bash
uv add 'yagra[llm]'
```

This installs [litellm](https://github.com/BerriAI/litellm), which provides a unified interface to OpenAI, Anthropic, Google, and other LLM providers.

### Verify Installation

```bash
yagra --help
```

You should see available commands: `init`, `schema`, `validate`, `visualize`, `studio`.

## Your First Workflow

### Option 1: Quick Start with Templates

Yagra provides templates for common patterns. This is the fastest way to get started.

#### 1. List Available Templates

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

#### 2. Initialize from Template

```bash
yagra init --template branch --output my-first-workflow
cd my-first-workflow
```

This generates:
- `workflow.yaml`: Workflow definition
- `prompts/branch_prompts.yaml`: Prompt definitions

#### 3. Validate the Workflow

```bash
yagra validate --workflow workflow.yaml
```

If valid, you'll see:
```
✓ ワークフローは valid です。
```

#### 4. Visualize the Workflow

```bash
yagra visualize --workflow workflow.yaml --output workflow.html
```

Open `workflow.html` in your browser to see a visual representation.

### Option 2: Build from Scratch

If you prefer to understand each component, follow this step-by-step guide.

#### 1. Define Your State Schema

```python
# my_workflow.py
from typing import TypedDict

class AgentState(TypedDict, total=False):
    query: str
    intent: str
    answer: str
    __next__: str  # For conditional branching
```

#### 2. Implement Handler Functions

```python
def classify_intent(state: AgentState, params: dict) -> dict:
    """Classify user intent based on query."""
    query = state.get("query", "")
    if "料金" in query or "price" in query.lower():
        intent = "faq"
    else:
        intent = "general"
    return {"intent": intent, "__next__": intent}


def answer_faq(state: AgentState, params: dict) -> dict:
    """Answer FAQ questions."""
    prompt = params.get("prompt", {})
    system_prompt = prompt.get("system", "You are a helpful assistant.")
    return {"answer": f"FAQ: {system_prompt}"}


def answer_general(state: AgentState, params: dict) -> dict:
    """Answer general questions."""
    model = params.get("model", {})
    model_name = model.get("name", "unknown")
    return {"answer": f"GENERAL via {model_name}"}


def finish(state: AgentState, params: dict) -> dict:
    """Finalize the answer."""
    return {"answer": state.get("answer", "No answer")}
```

#### 3. Create Workflow YAML

Create `workflows/support.yaml`:

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
      prompt_ref: "../prompts/support_prompts.yaml#faq"
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

#### 4. Create Prompt YAML

Create `prompts/support_prompts.yaml`:

```yaml
faq:
  system: |
    You are a FAQ bot. Answer common questions about pricing, features, and policies.
  user: |
    Question: {query}
```

#### 5. Build and Run

```python
from yagra import Yagra

# Register handlers
registry = {
    "classify_intent": classify_intent,
    "answer_faq": answer_faq,
    "answer_general": answer_general,
    "finish": finish,
}

# Build graph from workflow
app = Yagra.from_workflow(
    workflow_path="workflows/support.yaml",
    registry=registry,
    state_schema=AgentState,
)

# Execute
result = app.invoke({"query": "料金を教えて"})
print(result["answer"])
```

## Next Steps

- **Learn YAML Syntax**: [Workflow YAML Reference](user_guide/workflow_yaml.md)
- **Explore CLI Tools**: [CLI Reference](cli_reference.md)
- **Try Visual Editor**: Run `yagra studio --port 8787` to launch the WebUI
- **See Examples**: [Examples](examples.md)

## Common Issues

### `ModuleNotFoundError: No module named 'yagra'`

Make sure Yagra is installed in your active Python environment:

```bash
pip list | grep yagra
```

If not listed, reinstall:

```bash
pip install yagra
```

### `ValidationError` on Workflow Load

Check your YAML syntax with:

```bash
yagra validate --workflow your_workflow.yaml --format json
```

This outputs structured error messages you can address.

### Prompt Reference Not Resolved

Ensure:
1. The prompt YAML file exists at the specified path
2. The path is relative to the workflow YAML or use `--bundle-root`
3. The key path (e.g., `#faq`) exists in the YAML

Example:

```yaml
# ✅ Correct
prompt_ref: "../prompts/support_prompts.yaml#faq"

# ❌ Incorrect (missing file)
prompt_ref: "../prompts/missing.yaml#faq"
```

## Using LLM Handlers

Yagra provides built-in handler utilities for common LLM patterns. Install the `llm` extra first:

```bash
pip install 'yagra[llm]'
```

Then register a handler in your Python code:

```python
from yagra import Yagra
from yagra.handlers import create_llm_handler

registry = {"llm": create_llm_handler()}
yagra = Yagra.from_workflow("workflow.yaml", registry)
result = yagra.invoke({"query": "Hello!"})
print(result["response"])
```

Three handler types are available:

| Handler | Factory | Output |
|---|---|---|
| Basic LLM | `create_llm_handler()` | `str` |
| Structured Output | `create_structured_llm_handler(schema=MyModel)` | Pydantic model instance |
| Streaming | `create_streaming_llm_handler()` | `Generator[str, None, None]` |

For working examples, see:
- [`examples/llm-basic/`](https://github.com/shogo-hs/Yagra/tree/main/examples/llm-basic)
- [`examples/llm-structured/`](https://github.com/shogo-hs/Yagra/tree/main/examples/llm-structured)
- [`examples/llm-streaming/`](https://github.com/shogo-hs/Yagra/tree/main/examples/llm-streaming)
