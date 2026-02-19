# Workflow YAML Reference

This page describes the complete YAML schema for defining Yagra workflows.

## Overview

A workflow YAML file defines:
- **Nodes**: Processing units (e.g., classifiers, generators, evaluators)
- **Edges**: Transitions between nodes (unconditional or conditional)
- **Start/End points**: Entry and exit nodes

Yagra validates the YAML against a Pydantic schema (`GraphSpec`) and builds a LangGraph `StateGraph`.

## Top-Level Structure

```yaml
version: "1.0"           # Required: Schema version
start_at: "node_id"      # Required: Entry node ID
end_at:                  # Required: List of exit node IDs
  - "finish"
  - "error_handler"
state_schema:            # Optional: Typed state field definitions
  field_name:
    type: str            # str | int | float | bool | list | dict | messages
nodes:                   # Required: List of node definitions
  - id: "node_1"
    handler: "handler_name"
    params: {}
edges:                   # Required: List of edge definitions
  - source: "node_1"
    target: "node_2"
    condition: null      # Optional: Conditional branching
params: {}               # Optional: Global parameters
interrupt_before:        # Optional: Pause before these nodes (HITL)
  - "review_node"
interrupt_after:         # Optional: Pause after these nodes (HITL)
  - "generate_node"
```

## State Schema

The optional `state_schema` section defines typed fields for the workflow's state. Yagra uses these definitions to build a typed `TypedDict` and configure LangGraph reducers.

### Basic Field

```yaml
state_schema:
  query:
    type: str
  count:
    type: int
  active:
    type: bool
  tags:
    type: list
```

Supported types: `str`, `int`, `float`, `bool`, `list`, `dict`, `messages`

### Fan-In with Reducer

Use `reducer: add` on list fields to enable parallel fan-in (combines outputs from multiple concurrent nodes):

```yaml
state_schema:
  results:
    type: list
    reducer: add    # operator.add: merges lists from parallel nodes
```

### Chat History (MessagesState)

Use `type: messages` to enable LangGraph's `add_messages` reducer for conversational state:

```yaml
state_schema:
  messages:
    type: messages    # Activates add_messages: new messages are appended, not overwritten
```

Handlers should return `{"messages": [new_message]}` to append to the conversation history.

## Node Specification

Each node defines a processing unit.

### Basic Node

```yaml
nodes:
  - id: "classifier"
    handler: "classify_intent"
```

- `id` (str, required): Unique node identifier
- `handler` (str, required): Handler function name (resolved via registry)

### Node with Parameters

```yaml
nodes:
  - id: "generator"
    handler: "generate_answer"
    params:
      prompt_ref: "../prompts/generator.yaml#system"
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.7
          max_tokens: 1000
```

- `params` (dict, optional): Parameters passed to the handler
  - `prompt_ref`: External prompt reference (see [Prompt & Model](prompt_model.md))
  - `model`: Model configuration (inline definition)
  - Custom parameters: Any additional data your handler needs

### Subgraph Node

Use `handler: "subgraph"` with `params.workflow_ref` to embed another workflow YAML as a nested subgraph:

```yaml
nodes:
  - id: "sub_agent"
    handler: "subgraph"
    params:
      workflow_ref: ./sub_workflow.yaml   # Relative path from this workflow file
```

The subgraph shares the parent's registry and checkpointer. All handlers referenced in both YAMLs must be registered in the same registry when building the graph.

### Node Handler Signature

Your handler function receives `(state, params)` or just `(state)`:

```python
def my_handler(state: AgentState, params: dict) -> dict:
    prompt = params.get("prompt", {})
    model = params.get("model", {})
    # ... process state and return updates
    return {"key": "value"}
```

Yagra tries calling with `params` first, falls back to `state`-only if that fails.

## Edge Specification

Edges define transitions between nodes.

### Unconditional Edge

```yaml
edges:
  - source: "node_1"
    target: "node_2"
```

Always transitions from `node_1` to `node_2`.

### Conditional Edge

```yaml
edges:
  - source: "classifier"
    target: "faq_bot"
    condition: "faq"
  - source: "classifier"
    target: "general_bot"
    condition: "general"
```

- `condition` (str, optional): Branching label
- The source node must return `{"__next__": "faq"}` or `{"__next__": "general"}`

**Contract**: The source node is responsible for setting `__next__` in the state.

Example:

```python
def classifier(state: AgentState, params: dict) -> dict:
    intent = "faq" if "pricing" in state["query"] else "general"
    return {"intent": intent, "__next__": intent}
```

### Fan-Out Edge (Parallel Dispatch)

Use `fan_out` to dispatch items from a list in parallel using LangGraph's Send API:

```yaml
edges:
  - source: "prepare"
    target: "process_item"
    fan_out:
      items_key: items    # State key containing the list (e.g., state["items"])
      item_key: item      # Key passed to each parallel invocation (e.g., state["item"])
```

- `fan_out` is mutually exclusive with `condition`
- The target node receives `{item_key: single_item}` for each element in `state[items_key]`
- Use `reducer: add` on the output state field to merge results from all parallel executions

**Example: Map-Reduce**

```yaml
state_schema:
  items:
    type: list
  results:
    type: list
    reducer: add

edges:
  - source: "prepare"
    target: "process_item"
    fan_out:
      items_key: items
      item_key: item
  - source: "process_item"
    target: "aggregate"
```

Handler for `process_item`:

```python
def process_handler(state: dict) -> dict:
    item = state["item"]   # Single item from the fan-out
    result = do_work(item)
    return {"results": [result]}   # Appended to state["results"] via reducer: add
```

## Start and End Points

### `start_at`

The node ID where execution begins.

```yaml
start_at: "classifier"
```

### `end_at`

A list of node IDs where execution can terminate.

```yaml
end_at:
  - "finish"
  - "error"
```

Yagra registers these nodes as LangGraph finish points. When execution reaches any of these nodes, the graph stops.

**Note**: Do not write `END` explicitly in YAML—Yagra handles this internally.

## Global Parameters

Optional top-level `params` apply to all nodes unless overridden.

```yaml
params:
  default_temperature: 0.7
  retry_limit: 3

nodes:
  - id: "node_1"
    handler: "handler_1"
    params:
      temperature: 0.9  # Overrides default
```

## HITL / Interrupt

Use `interrupt_before` and `interrupt_after` to pause execution at specific nodes for Human-in-the-Loop (HITL) review. Yagra passes these lists directly to LangGraph's `compile(interrupt_before=..., interrupt_after=...)`.

### `interrupt_before`

Pause execution **before** the listed nodes run. Use this to require human approval before a critical action.

```yaml
interrupt_before:
  - "send_email"
  - "deploy"
```

When the graph reaches `send_email`, execution suspends. The human can inspect state and then call `Yagra.resume()` to continue.

### `interrupt_after`

Pause execution **after** the listed nodes run. Use this to allow humans to review or modify the node's output before the workflow continues.

```yaml
interrupt_after:
  - "generate_draft"
```

### Resume after Interrupt

```python
from yagra import Yagra

app = Yagra(registry=registry, checkpointer=checkpointer)
app.run(workflow_path="workflow.yaml", state={"query": "hello"}, config={"configurable": {"thread_id": "1"}})

# --- human reviews state here ---

app.resume(config={"configurable": {"thread_id": "1"}})
```

A `checkpointer` is required for interrupt/resume to work. Yagra passes it to `StateGraph.compile()`.

**Note**: `interrupt_before` and `interrupt_after` node IDs must exist in the `nodes` list.

## Validation Rules

Yagra validates workflows before building the graph:

1. **Schema compliance**: YAML must match `GraphSpec` Pydantic model
2. **Node ID uniqueness**: No duplicate node IDs
3. **Edge references**: All `source`/`target` must reference existing nodes
4. **Start/End validity**: `start_at` and `end_at` nodes must exist
5. **Prompt references**: `prompt_ref` paths must resolve to valid files
6. **Edge rules**: Mixed conditional and unconditional edges from the same source are not allowed; `fan_out` edges cannot be combined with other edge types from the same source
7. **State schema**: `reducer: add` requires `type: list` or `type: messages`

Use `yagra validate` to check compliance:

```bash
yagra validate --workflow workflow.yaml --format json
```

## Example: Complete Workflow

```yaml
version: "1.0"
start_at: "retrieve"
end_at:
  - "generate"

nodes:
  - id: "retrieve"
    handler: "retrieve_documents"
    params:
      top_k: 5
  - id: "rerank"
    handler: "rerank_documents"
    params:
      prompt_ref: "../prompts/rerank.yaml#system"
  - id: "generate"
    handler: "generate_answer"
    params:
      prompt_ref: "../prompts/generate.yaml#system"
      model:
        provider: "anthropic"
        name: "claude-3-sonnet"

edges:
  - source: "retrieve"
    target: "rerank"
  - source: "rerank"
    target: "generate"
```

## Next Steps

- [Prompt & Model Configuration](prompt_model.md)
- [Branching & Loops](branching_loops.md)
- [CLI Reference](../cli_reference.md)
