# Yagra

<p align="center">
  <img src="docs/assets/yagra-logo.jpg" alt="Yagra logo" width="720" />
</p>

<p align="center">
  <a href="https://github.com/shogo-hs/Yagra/actions/workflows/ci.yml"><img src="https://github.com/shogo-hs/Yagra/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/yagra/"><img src="https://img.shields.io/pypi/v/yagra.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/yagra/"><img src="https://img.shields.io/pypi/pyversions/yagra.svg" alt="Python"></a>
  <a href="https://github.com/shogo-hs/Yagra/blob/main/LICENSE"><img src="https://img.shields.io/github/license/shogo-hs/Yagra.svg" alt="License"></a>
  <a href="https://pypi.org/project/yagra/"><img src="https://img.shields.io/pypi/dm/yagra.svg" alt="Downloads"></a>
</p>

**Declarative LangGraph Builder powered by YAML**

Yagra enables you to build [LangGraph](https://langchain-ai.github.io/langgraph/)'s `StateGraph` from YAML definitions, separating workflow logic from Python implementation. Define nodes, edges, and branching conditions in YAML files—swap configurations without touching code.

Designed for **LLM agent developers**, **prompt engineers**, and **non-technical stakeholders** who want to iterate on workflows quickly without diving into Python code every time.

Built with **AI-Native principles**: JSON Schema export and validation CLI enable coding agents (Claude Code, Codex, etc.) to generate and validate workflows automatically.

## ✨ Key Features

- **Declarative Workflow Management**: Define nodes, edges, and conditional branching in YAML
- **Implementation-Configuration Separation**: Connect YAML `handler` strings to Python callables via Registry
- **Schema Validation**: Catch configuration errors early with Pydantic-based validation
- **Custom State Schema**: Pass any `TypedDict` (including `MessagesState`) via `state_schema` — full LangGraph reducer support
- **Advanced Patterns**: Fan-out/fan-in (parallel map-reduce via Send API) and subgraph nesting for composable workflows
- **Node Resilience**: Declare `retry` (exponential/fixed backoff), `timeout_seconds`, and `fallback` per node directly in YAML — no wrapper code needed
- **Visual Workflow Editor**: Launch Studio WebUI for visual editing, drag-and-drop node/edge management, and diff preview
- **Template Library**: Quick-start templates for common patterns (branching, loops, RAG, parallel, subgraph, and more)
- **Golden Test (Regression Testing)**: Save execution traces as golden cases, then replay with mocked LLM responses to verify workflow structure after YAML changes — no API calls needed. Mock dispatch is resolved per node, so multiple nodes sharing the same handler name are replayed correctly. `yagra golden save` supports repeatable `--strategy node_id:strategy` overrides (`exact`/`structural`/`skip`/`auto`) to persist per-node comparison behavior. Available via CLI (`yagra golden`) and MCP tool (`run_golden_tests`)
- **MCP Server**: Expose Yagra tools to AI agents via [Model Context Protocol](https://modelcontextprotocol.io/) (`yagra[mcp]`)
- **AI-Ready**: JSON Schema export (`yagra schema`) and structured validation for coding agents

## 📦 Installation

- Python 3.12+

```bash
# Recommended (uv)
uv add yagra

# With LLM handler utilities (optional)
uv add 'yagra[llm]'

# Or with pip
pip install yagra
pip install 'yagra[llm]'
```

### 🤖 Using with Claude Code (Recommended)

This repository includes a `.mcp.json` configuration file, so Claude Code automatically recognizes the Yagra MCP server when you open the project. No additional setup is required beyond installing the MCP extra.

```bash
# Install with MCP support
pip install "yagra[mcp]"
# or
uv add "yagra[mcp]"
```

Once installed, start a conversation with Claude Code in this project and try:

- *"Create a customer support FAQ routing workflow"*
- *"Analyze the traces and suggest improvements to my workflow"*
- *"Generate a RAG workflow for document Q&A"*

For a complete walkthrough, see the **[Agent Integration Guide](docs/agent-integration-guide.md)**.

---

### 🔄 Optimization Cycle

Yagra is designed for an iterative improvement loop driven by AI agents:

```
┌─────────┐    ┌──────────────┐    ┌──────────────────┐    ┌────────────────┐
│  Build  │───▶│ Run & Observe│───▶│ Analyze & Propose│───▶│ Approve & Apply│
└─────────┘    └──────────────┘    └──────────────────┘    └───────┬────────┘
     ▲                                                              │
     └──────────────────────────────────────────────────────────────┘
```

| Phase | Description |
|---|---|
| **Build** | Start from a template with `yagra init`, or ask Claude to generate a workflow YAML from a description. |
| **Run & Observe** | Execute your workflow with `observability=True` to collect execution traces automatically. |
| **Analyze & Propose** | Use the `analyze_traces` MCP tool to identify bottlenecks or failures, then `propose_update` to preview a diff before any changes are applied. |
| **Approve & Apply** | Review the diff and confirm with `apply_update`. If something goes wrong, `rollback_update` restores the previous version instantly. |

---

### LLM Handler Utilities (Beta)

Yagra provides handler utilities to reduce boilerplate code for LLM nodes:

```python
from yagra.handlers import create_llm_handler

# Create a generic LLM handler
llm = create_llm_handler(retry=3, timeout=30)

# Register and use in workflow
registry = {"llm": llm}
app = Yagra.from_workflow("workflow.yaml", registry)
```

**YAML Definition:**
```yaml
nodes:
  - id: "chat"
    handler: "llm"
    params:
      prompt_ref: "prompts/chat.yaml#system"
      model:
        provider: "openai"
        name: "gpt-4"
        kwargs:
          temperature: 0.7
      output_key: "response"
```

The handler automatically:
- Extracts and interpolates prompts
- Calls LLM via [litellm](https://github.com/BerriAI/litellm) (100+ providers)
- Handles retries and timeouts
- Returns structured output

**See the full working example**: [`examples/llm-basic/`](examples/llm-basic/)

### Structured Output Handler (Beta)

Use `create_structured_llm_handler()` to get type-safe Pydantic model instances from LLM responses:

```python
from pydantic import BaseModel
from yagra.handlers import create_structured_llm_handler

class PersonInfo(BaseModel):
    name: str
    age: int

handler = create_structured_llm_handler(schema=PersonInfo)
registry = {"structured_llm": handler}
app = Yagra.from_workflow("workflow.yaml", registry)

result = app.invoke({"text": "My name is Alice and I am 30."})
person: PersonInfo = result["person"]  # Type-safe!
print(person.name, person.age)  # Alice 30
```

The handler automatically:
- Enables JSON output mode (`response_format=json_object`)
- Injects JSON Schema into the system prompt
- Validates and parses the response with Pydantic

**Dynamic schema (no Python code required)**: Define the schema directly in your workflow YAML using `schema_yaml`, and call `create_structured_llm_handler()` with no arguments:

```python
# No Pydantic model needed in Python code
handler = create_structured_llm_handler()
registry = {"structured_llm": handler}
```

```yaml
# workflow.yaml
nodes:
  - id: "extract"
    handler: "structured_llm"
    params:
      schema_yaml: |
        name: str
        age: int
        hobbies: list[str]
      prompt_ref: "prompts.yaml#extract"
      model:
        provider: "openai"
        name: "gpt-4o"
      output_key: "person"
```

Supported types in `schema_yaml`: `str`, `int`, `float`, `bool`, `list[str]`, `list[int]`, `dict[str, str]`, `str | None`, etc.

**See the full working example**: [`examples/llm-structured/`](examples/llm-structured/)

### Streaming Handler (Beta)

Stream LLM responses chunk by chunk:

```python
from yagra.handlers import create_streaming_llm_handler

handler = create_streaming_llm_handler(retry=3, timeout=60)
registry = {"streaming_llm": handler}

yagra = Yagra.from_workflow("workflow.yaml", registry)
result = yagra.invoke({"query": "Tell me about Python async"})

# Incremental processing
for chunk in result["response"]:
    print(chunk, end="", flush=True)

# Or buffered
full_text = "".join(result["response"])
```

> **Note**: The `Generator` is single-use. Consume it once with either `for` or `"".join(...)`.

**See the full working example**: [`examples/llm-streaming/`](examples/llm-streaming/)


## 🚀 Quick Start

### Option 1: From Template (Recommended)

Yagra provides ready-to-use templates for common workflow patterns.

```bash
# List available templates
yagra init --list

# Initialize from a template
yagra init --template branch --output my-workflow

# Validate the generated workflow
yagra validate --workflow my-workflow/workflow.yaml
```

Available templates:
- **branch**: Conditional branching pattern
- **chat**: Single-node chat with `MessagesState` and `add_messages` reducer
- **loop**: Planner → Evaluator loop pattern
- **parallel**: Fan-out/fan-in map-reduce pattern via Send API
- **rag**: Retrieve → Rerank → Generate RAG pattern
- **subgraph**: Nested subgraph pattern for composable multi-workflow architectures
- **tool-use**: LLM decides whether to invoke external tools and executes them to answer
- **multi-agent**: Orchestrator, researcher, and writer agents collaborate in a multi-agent pattern
- **human-review**: Human-in-the-loop pattern that pauses for review and approval via `interrupt_before`

### Option 2: From Scratch

#### 1. Define State and Handler Functions

```python
from typing import TypedDict
from yagra import Yagra


class AgentState(TypedDict, total=False):
    query: str
    intent: str
    answer: str
    __next__: str  # For conditional branching


def classify_intent(state: AgentState, params: dict) -> dict:
    intent = "faq" if "料金" in state.get("query", "") else "general"
    return {"intent": intent, "__next__": intent}


def answer_faq(state: AgentState, params: dict) -> dict:
    prompt = params.get("prompt", {})
    return {"answer": f"FAQ: {prompt.get('system', '')}"}


def answer_general(state: AgentState, params: dict) -> dict:
    model = params.get("model", {})
    return {"answer": f"GENERAL via {model.get('name', 'unknown')}"}


def finish(state: AgentState, params: dict) -> dict:
    return {"answer": state.get("answer", "")}
```

#### 2. Define Workflow YAML

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

#### 3. Register Handlers and Run

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

## 🔍 Observability (Public Trace API)

If you enable `observability=True`, Yagra stores the latest execution trace in memory.

```python
app = Yagra.from_workflow(
    workflow_path="workflows/support.yaml",
    registry=registry,
    observability=True,
)

app.invoke({"query": "料金を教えて"}, trace=False)
last_trace = app.get_last_trace()  # WorkflowRunTrace | None
```

- `get_last_trace()` returns `None` when `observability=False` or before the first `invoke()`.
- `trace=True` controls JSON file output only (`.yagra/traces/` or `trace_dir`), and does not affect in-memory availability of `get_last_trace()`.

## 🛠️ CLI Tools

Yagra provides CLI commands for workflow management:

### `yagra init`

Initialize a workflow from a template.

```bash
yagra init --template branch --output my-workflow
```

### `yagra schema`

Export JSON Schema for workflow YAML (useful for coding agents).

```bash
yagra schema --output workflow-schema.json
```

### `yagra validate`

Validate a workflow YAML and report issues.

```bash
# Human-readable output
yagra validate --workflow workflows/support.yaml

# JSON output for agent consumption
yagra validate --workflow workflows/support.yaml --format json
```

### `yagra explain`

Statically analyze a workflow YAML to show execution paths, required handlers, and variable flow.

```bash
# JSON output (default)
yagra explain --workflow workflows/support.yaml

# Read from stdin (pipe-friendly)
cat workflows/support.yaml | yagra explain --workflow -
```

### `yagra handlers`

List built-in handler parameter schemas (useful for coding agents).

```bash
# Human-readable output
yagra handlers

# JSON output for agent consumption
yagra handlers --format json
```

### `yagra analyze`

Aggregate and summarize execution traces from `.yagra/traces/`.

```bash
# Summarize all traces
yagra analyze

# Filter by workflow name, show 10 most recent traces
yagra analyze --workflow my-workflow --limit 10

# JSON output for agent consumption
yagra analyze --format json
```

### `yagra prompt`

Inspect prompt YAML files and their version metadata.

```bash
# Display prompt file metadata and keys
yagra prompt info --file prompts.yaml

# JSON output
yagra prompt info --file prompts.yaml --format json
```

### `yagra mcp`

Launch Yagra as an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server. Requires `yagra[mcp]` extra.

```bash
# Install with MCP support
pip install "yagra[mcp]"
# or
uv add "yagra[mcp]"

# Start the MCP server (stdio mode)
yagra mcp
```

Available MCP tools: `validate_workflow`, `validate_workflow_file`, `explain_workflow`, `explain_workflow_file`, `list_templates`, `list_handlers`, `get_template`, `get_traces`, `analyze_traces`, `propose_update`, `apply_update`, `rollback_update`, `run_golden_tests`

### `yagra studio`

Launch an interactive WebUI for visual editing, drag-and-drop node/edge management, and workflow persistence.

```bash
# Launch with workflow selector (recommended)
yagra studio --port 8787

# Launch with a specific workflow
yagra studio --workflow workflows/support.yaml --port 8787
```

Open `http://127.0.0.1:8787/` in your browser.

**Studio Features:**
- **Handler Type Selector**: Node Properties panel provides a type selector (`llm` / `structured_llm` / `streaming_llm` / `custom`)
  - Predefined types auto-populate the handler name — no manual typing required
  - `custom` type enables free-text input for user-defined handlers
- **Handler-Aware Forms**: Form sections adapt automatically to the selected handler type
  - `structured_llm` → Schema Settings section (edit `schema_yaml` as YAML)
  - `streaming_llm` → Streaming Settings section (`stream: false` toggle)
  - `custom` → LLM-specific sections hidden automatically
- **Resilience Settings**: Configure retry (max attempts, backoff, base delay), timeout, and fallback per node — all handler types supported
- **State Schema Editor**: Define workflow-level `state_schema` fields visually via a table editor (name, type, reducer columns) — no YAML hand-editing required
- **Visual Editing**: Edit prompts, models, and conditions via forms
- **Drag & Drop**: Add nodes, connect edges, adjust layout visually
- **Diff Preview**: Review changes before saving
- **Backup & Rollback**: Automatic backups with rollback support
- **Live Validation**: Auto-validates on every form change (400ms debounce) with severity-aware issue display (error/warning/info badges) and canvas node error highlights

## 📚 Documentation

Full documentation is available at **[shogo-hs.github.io/Yagra](https://shogo-hs.github.io/Yagra/)**

- **[User Guide](https://shogo-hs.github.io/Yagra/)**: Installation, YAML syntax, CLI tools
- **[API Reference](https://shogo-hs.github.io/Yagra/api.html)**: Python API documentation
- **[Examples](https://shogo-hs.github.io/Yagra/examples.html)**: Practical use cases
- **[Agent Integration Guide](docs/agent-integration-guide.md)**: Step-by-step guide for using Claude Code with Yagra MCP

You can also build documentation locally:

```bash
uv run sphinx-build -b html docs/sphinx/source docs/sphinx/_build/html
```

## 🎯 Use Cases

- Prototype LLM agent flows and iterate rapidly by swapping YAML files
- Enable non-engineers to adjust workflows (prompts, models, branching) without code changes
- Integrate with coding agents for automated workflow generation and validation
- Reduce boilerplate code when building LangGraph applications with complex control flow

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

<p align="center">
  <sub>Built with ❤️ for the LangGraph community</sub>
</p>
