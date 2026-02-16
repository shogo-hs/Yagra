# Examples

This page showcases the example workflows included in the Yagra repository.

## Example 1: Conditional Branching (`branch-inline`)

Route execution to different handlers based on runtime classification.

### Workflow Structure

- **Router**: Determines whether the query needs planning or can be answered directly
- **Planner**: Generates a plan (only when routed via `needs_plan`)
- **Finish**: Collects the final answer

### Files

**`examples/workflows/branch-inline.yaml`**:

```yaml
version: "1.0"
start_at: "router"
end_at:
  - "finish"
params:
  workflow_name: "branch-inline"
nodes:
  - id: "router"
    handler: "router_handler"
  - id: "planner"
    handler: "planner_handler"
    params:
      prompt_ref: "../prompts/branch_prompts.yaml#planner"
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.2
  - id: "finish"
    handler: "finish_handler"
edges:
  - source: "router"
    target: "planner"
    condition: "needs_plan"
  - source: "router"
    target: "finish"
    condition: "direct_answer"
  - source: "planner"
    target: "finish"
```

**`examples/prompts/branch_prompts.yaml`**:

```yaml
planner:
  system: "You are planner."
  user: "Plan for: {goal}"
```

**Handler implementation**:

```python
from typing import TypedDict
from yagra import Yagra


class AgentState(TypedDict, total=False):
    query: str
    plan: str
    answer: str
    __next__: str


def router_handler(state: AgentState, params: dict) -> dict:
    query = state.get("query", "").lower()
    if "plan" in query or "complex" in query:
        return {"__next__": "needs_plan"}
    return {"__next__": "direct_answer"}


def planner_handler(state: AgentState, params: dict) -> dict:
    prompt = params.get("prompt", {})
    # In real implementation, call LLM with prompt
    return {"plan": f"Plan for: {state.get('query', '')}"}


def finish_handler(state: AgentState, params: dict) -> dict:
    plan = state.get("plan", "")
    return {"answer": plan if plan else state.get("query", "")}


registry = {
    "router_handler": router_handler,
    "planner_handler": planner_handler,
    "finish_handler": finish_handler,
}

app = Yagra.from_workflow(
    workflow_path="examples/workflows/branch-inline.yaml",
    registry=registry,
    state_schema=AgentState,
)

result = app.invoke({"query": "Plan a complex project"})
print(f"Answer: {result['answer']}")
```

---

## Example 2: Planner-Evaluator Loop (`loop-split`)

Generate a plan, evaluate its quality, and loop back for refinement until acceptable.

### Workflow Structure

- **Planner**: Generates or refines a plan
- **Evaluator**: Checks plan quality; returns `retry` or `done`
- **Finish**: Finalizes the output

### Files

**`examples/workflows/loop-split.yaml`**:

```yaml
version: "1.0"
start_at: "planner"
end_at:
  - "finish"
nodes:
  - id: "planner"
    handler: "planner_loop_handler"
    params:
      prompt_ref: "../prompts/support_prompts.yaml#planner"
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.1
          max_tokens: 256
  - id: "evaluator"
    handler: "evaluator_loop_handler"
    params:
      prompt_ref: "../prompts/support_prompts.yaml#evaluator"
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.1
          max_tokens: 256
  - id: "finish"
    handler: "finish_handler"
    params:
      prompt_ref: "../prompts/support_prompts.yaml#finish"
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.1
          max_tokens: 256
edges:
  - source: "planner"
    target: "evaluator"
  - source: "evaluator"
    target: "planner"
    condition: "retry"
  - source: "evaluator"
    target: "finish"
    condition: "done"
```

**`examples/prompts/support_prompts.yaml`**:

```yaml
planner:
  system: "You are planner."
  user: "Create a concise plan."
evaluator:
  system: "You are evaluator."
  user: "Return retry or done."
finish:
  system: "You are finisher."
  user: "Summarize final answer."
```

**Handler implementation**:

```python
from typing import TypedDict
from yagra import Yagra


class AgentState(TypedDict, total=False):
    task: str
    plan: str
    iteration: int
    answer: str
    __next__: str


def planner_loop_handler(state: AgentState, params: dict) -> dict:
    iteration = state.get("iteration", 0)
    # In real implementation, call LLM with prompt
    plan = f"Plan v{iteration + 1}"
    return {"plan": plan, "iteration": iteration + 1}


def evaluator_loop_handler(state: AgentState, params: dict) -> dict:
    iteration = state.get("iteration", 0)
    max_iterations = 3

    # Simple quality check (in real implementation, use LLM)
    if iteration >= 2:
        return {"__next__": "done"}
    return {"__next__": "retry"}


def finish_handler(state: AgentState, params: dict) -> dict:
    return {"answer": state.get("plan", "")}


registry = {
    "planner_loop_handler": planner_loop_handler,
    "evaluator_loop_handler": evaluator_loop_handler,
    "finish_handler": finish_handler,
}

app = Yagra.from_workflow(
    workflow_path="examples/workflows/loop-split.yaml",
    registry=registry,
    state_schema=AgentState,
)

result = app.invoke({"task": "Write a blog post about AI agents"})
print(f"Final plan: {result['plan']}")
print(f"Iterations: {result['iteration']}")
```

## Running Examples

All examples are available in the `examples/` directory of the Yagra repository:

```bash
git clone https://github.com/shogo-hs/Yagra.git
cd Yagra/examples
```

## Visualizing Examples

Generate HTML visualizations:

```bash
yagra visualize --workflow examples/workflows/branch-inline.yaml --output branch.html
yagra visualize --workflow examples/workflows/loop-split.yaml --output loop.html
```

## Using Templates

Yagra also provides templates for common patterns. Templates include both workflow YAML and prompt files, ready to use:

```bash
yagra init --list
yagra init --template branch --output my-workflow
yagra init --template loop --output my-loop
yagra init --template rag --output my-rag
```

See [Templates](user_guide/templates.md) for details.

## Next Steps

- [User Guide](user_guide/workflow_yaml.md)
- [CLI Reference](cli_reference.md)
- [API Reference](api.md)
