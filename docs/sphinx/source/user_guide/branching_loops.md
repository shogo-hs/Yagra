# Branching & Loops

This guide explains how to implement conditional branching and loop patterns in Yagra workflows.

## Conditional Branching

Conditional branching lets you route execution to different nodes based on runtime conditions.

### Basic Branching Pattern

**Workflow Structure**:
- A **classifier node** evaluates state and decides the next path
- **Conditional edges** connect the classifier to different target nodes
- The classifier returns `__next__` with the branch label

**Example**: FAQ vs General Query Routing

```yaml
nodes:
  - id: "classifier"
    handler: "classify_intent"
  - id: "faq_bot"
    handler: "answer_faq"
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

**Handler Implementation**:

```python
def classify_intent(state: AgentState, params: dict) -> dict:
    query = state.get("query", "")
    if "pricing" in query.lower() or "料金" in query:
        intent = "faq"
    else:
        intent = "general"
    return {"intent": intent, "__next__": intent}
```

**Key Points**:
- The handler must return `{"__next__": "<branch_label>"}`
- Branch labels must match `condition` values in edges
- Each branch must have a corresponding edge

### Multi-Way Branching

You can have more than two branches:

```yaml
nodes:
  - id: "router"
    handler: "route_request"
  - id: "sales"
    handler: "handle_sales"
  - id: "support"
    handler: "handle_support"
  - id: "billing"
    handler: "handle_billing"
  - id: "finish"
    handler: "finish"

edges:
  - source: "router"
    target: "sales"
    condition: "sales"
  - source: "router"
    target: "support"
    condition: "support"
  - source: "router"
    target: "billing"
    condition: "billing"
  - source: "sales"
    target: "finish"
  - source: "support"
    target: "finish"
  - source: "billing"
    target: "finish"
```

```python
def route_request(state: AgentState, params: dict) -> dict:
    query = state.get("query", "").lower()
    if "buy" in query or "purchase" in query:
        route = "sales"
    elif "help" in query or "問題" in query:
        route = "support"
    elif "invoice" in query or "請求" in query:
        route = "billing"
    else:
        route = "support"  # Default
    return {"route": route, "__next__": route}
```

## Loop Patterns

Loops enable iterative workflows where execution returns to a previous node based on conditions.

### Basic Loop: Planner → Evaluator

A common pattern for iterative refinement:

1. **Planner** generates a plan
2. **Evaluator** checks if plan is good enough
3. If not good enough, return to **Planner** (loop)
4. If good enough, proceed to **Finish**

**Workflow**:

```yaml
nodes:
  - id: "planner"
    handler: "generate_plan"
  - id: "evaluator"
    handler: "evaluate_plan"
  - id: "finish"
    handler: "finalize"

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

**Handlers**:

```python
def generate_plan(state: AgentState, params: dict) -> dict:
    iteration = state.get("iteration", 0)
    # Generate plan (possibly improved if iteration > 0)
    plan = f"Plan v{iteration + 1}"
    return {
        "plan": plan,
        "iteration": iteration + 1,
    }


def evaluate_plan(state: AgentState, params: dict) -> dict:
    iteration = state.get("iteration", 0)
    max_iterations = params.get("max_iterations", 3)

    # Check quality (simplified)
    plan = state.get("plan", "")
    is_good = len(plan) > 20  # Dummy criteria

    if is_good or iteration >= max_iterations:
        return {"__next__": "done"}
    else:
        return {"__next__": "retry"}
```

### Loop with State Accumulation

Track history across iterations:

```python
def generate_plan(state: AgentState, params: dict) -> dict:
    iteration = state.get("iteration", 0)
    history = state.get("history", [])
    previous_feedback = history[-1] if history else None

    # Generate improved plan based on feedback
    plan = f"Plan v{iteration + 1}"
    if previous_feedback:
        plan += f" (improved from: {previous_feedback})"

    return {
        "plan": plan,
        "iteration": iteration + 1,
    }


def evaluate_plan(state: AgentState, params: dict) -> dict:
    iteration = state.get("iteration", 0)
    max_iterations = params.get("max_iterations", 3)
    history = state.get("history", [])
    plan = state.get("plan", "")

    # Evaluate and provide feedback
    is_good = iteration >= 2  # Simplified

    if is_good:
        return {"__next__": "done"}
    else:
        feedback = "Plan needs more detail"
        return {
            "history": history + [feedback],
            "__next__": "retry",
        }
```

### Preventing Infinite Loops

Always include a **termination condition** to avoid infinite loops:

1. **Max iterations**: Exit after N iterations
2. **Quality threshold**: Exit when quality is acceptable
3. **Timeout**: (Not directly supported in Yagra—implement in handler)

Example:

```python
def evaluator(state: AgentState, params: dict) -> dict:
    iteration = state.get("iteration", 0)
    max_iterations = params.get("max_iterations", 5)

    if iteration >= max_iterations:
        return {"__next__": "done"}  # Force exit

    # ... quality check ...
```

## Advanced Patterns

### Nested Branching

Combine branches within branches:

```yaml
nodes:
  - id: "intent_classifier"
    handler: "classify_intent"
  - id: "faq_router"
    handler: "route_faq"
  - id: "pricing_bot"
    handler: "answer_pricing"
  - id: "feature_bot"
    handler: "answer_features"
  - id: "general_bot"
    handler: "answer_general"
  - id: "finish"
    handler: "finish"

edges:
  # First level: Intent classification
  - source: "intent_classifier"
    target: "faq_router"
    condition: "faq"
  - source: "intent_classifier"
    target: "general_bot"
    condition: "general"

  # Second level: FAQ subcategories
  - source: "faq_router"
    target: "pricing_bot"
    condition: "pricing"
  - source: "faq_router"
    target: "feature_bot"
    condition: "features"

  # All paths converge to finish
  - source: "pricing_bot"
    target: "finish"
  - source: "feature_bot"
    target: "finish"
  - source: "general_bot"
    target: "finish"
```

### Loop with Branch Exit

Combine loops and branches:

```yaml
nodes:
  - id: "generator"
    handler: "generate_content"
  - id: "reviewer"
    handler: "review_content"
  - id: "approver"
    handler: "approve_content"
  - id: "finish"
    handler: "finalize"

edges:
  - source: "generator"
    target: "reviewer"
  - source: "reviewer"
    target: "generator"
    condition: "needs_revision"
  - source: "reviewer"
    target: "approver"
    condition: "ready_for_approval"
  - source: "approver"
    target: "generator"
    condition: "rejected"
  - source: "approver"
    target: "finish"
    condition: "approved"
```

## Visualizing Branching and Loops

Use `yagra visualize` to see branching and loop structure:

```bash
yagra visualize --workflow workflows/loop.yaml --output loop.html
```

Open `loop.html` to see:
- Nodes as boxes
- Edges as arrows
- Conditional edges labeled with conditions
- Loops as circular paths

Use `yagra studio` for interactive editing:

```bash
yagra studio --workflow workflows/loop.yaml --port 8787
```

## Best Practices

### Branching

1. **Explicit labels**: Use descriptive condition names (`"needs_revision"` not `"0"`)
2. **Default fallback**: Handle unexpected cases (e.g., default to `"general"`)
3. **Validate branches**: Ensure all conditions have corresponding edges

### Loops

1. **Set max iterations**: Always include a termination condition
2. **Track progress**: Use `iteration` or `attempt_count` in state
3. **Provide feedback**: Pass quality feedback to improve next iteration
4. **Monitor cost**: Each iteration may call expensive LLM APIs

### Debugging

1. **Add logging**: Print `__next__` value in handlers
2. **Validate workflow**: Use `yagra validate --format json` to catch edge errors
3. **Visualize**: Generate HTML to visually verify flow

## Common Pitfalls

### Missing `__next__` in Branching Node

**Error**: LangGraph raises an error because it doesn't know which edge to take.

**Solution**: Always return `__next__` in branching nodes:

```python
def classifier(state: AgentState, params: dict) -> dict:
    intent = "faq" if "pricing" in state["query"] else "general"
    return {"intent": intent, "__next__": intent}  # ✅
```

### Infinite Loop Without Exit

**Symptom**: Workflow runs forever or times out.

**Solution**: Add max iteration check:

```python
iteration = state.get("iteration", 0)
if iteration >= max_iterations:
    return {"__next__": "done"}  # Force exit
```

### Mismatched Condition Labels

**Error**: `ValidationError: condition 'xyz' has no corresponding edge`

**Solution**: Ensure edge `condition` matches `__next__` value:

```yaml
edges:
  - source: "evaluator"
    target: "finish"
    condition: "done"  # Must match __next__ value
```

```python
return {"__next__": "done"}  # ✅ Matches
```

## Examples

See `examples/workflows/` for complete examples:
- `branch-inline.yaml`: Simple branching
- `loop-split.yaml`: Loop with conditional exit
- `rag.yaml`: Multi-stage RAG pipeline

## Next Steps

- [Templates](templates.md)
- [CLI Reference](../cli_reference.md)
- [Examples](../examples.md)
