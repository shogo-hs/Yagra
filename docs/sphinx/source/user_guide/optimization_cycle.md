# Optimization Cycle

This guide walks you through the **Build → Run → Analyze → Update** optimization cycle — the core workflow for iteratively improving your Yagra workflows using AI agents.

## Overview

Yagra's optimization cycle closes the loop between workflow execution and workflow improvement:

```
┌─────────────────────────────────────────────────────────┐
│                  Optimization Cycle                      │
│                                                          │
│  1. Build     →  Define workflow in YAML                 │
│  2. Run       →  Execute and capture traces              │
│  3. Analyze   →  Identify improvement opportunities      │
│  4. Propose   →  Generate a YAML diff                    │
│  5. Test      →  Validate with golden cases              │
│  6. Apply     →  Commit the change (or rollback)         │
│                                                          │
│       ↑                                     │            │
│       └─────────── iterate ─────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

All steps run locally — no external SaaS or cloud service required.

## Prerequisites

Install Yagra with LLM and MCP support:

```bash
uv add 'yagra[llm,mcp]'
```

Verify the installation:

```bash
yagra --help
```

Set your LLM API key (example: OpenAI):

```bash
export OPENAI_API_KEY=sk-...
```

## Step 1: Build — Define Your Workflow

Create a workflow YAML. Use a template to get started quickly:

```bash
yagra init --template branch --output my-workflow
cd my-workflow
```

Validate before proceeding:

```bash
yagra validate --workflow workflow.yaml
```

Expected output:

```
✓ ワークフローは valid です。
```

See [Workflow YAML Reference](workflow_yaml.md) for the full schema.

## Step 2: Run & Observe — Capture Traces

Enable observability when building the graph, then invoke it with `trace=True` to persist the trace to disk:

```python
from yagra import Yagra
from my_handlers import registry, AgentState

app = Yagra.from_workflow(
    workflow_path="workflow.yaml",
    registry=registry,
    state_schema=AgentState,
    observability=True,
)

result = app.invoke({"query": "What is the refund policy?"}, trace=True)
print(result)
```

Traces are saved under `.yagra/traces/<workflow_name>/` as JSON files:

```
.yagra/traces/my-workflow/my-workflow_20260222T120000_a1b2c3d4.json
```

You can also retrieve the latest trace in memory without file I/O:

```python
last_trace = app.get_last_trace()  # WorkflowRunTrace | None
```

## Step 3: Analyze — Identify Improvement Opportunities

Use the MCP tools to analyze accumulated traces. Start the MCP server:

```bash
yagra mcp
```

Then call `analyze_traces` from your AI agent or MCP client:

```json
{
  "tool": "analyze_traces",
  "arguments": {
    "workflow_name": "my-workflow",
    "limit": 20
  }
}
```

Example response:

```json
{
  "workflow_name": "my-workflow",
  "total_traces": 20,
  "node_summaries": [
    {
      "node_id": "classifier",
      "avg_latency_ms": 342,
      "error_rate": 0.0
    },
    {
      "node_id": "answer_faq",
      "avg_latency_ms": 1820,
      "error_rate": 0.05,
      "notes": "5% of responses were empty — likely a prompt gap"
    }
  ],
  "suggestions": [
    "answer_faq: add fallback instructions to the system prompt"
  ]
}
```

To inspect individual traces, call `get_traces`:

```json
{
  "tool": "get_traces",
  "arguments": {
    "workflow_name": "my-workflow",
    "limit": 5
  }
}
```

## Step 4: Propose & Review — Generate a YAML Diff

Ask an agent (or call the MCP tool directly) to propose a YAML improvement:

```json
{
  "tool": "propose_update",
  "arguments": {
    "workflow_path": "workflow.yaml",
    "instruction": "Add a fallback instruction to answer_faq's system prompt when no relevant FAQ entry is found."
  }
}
```

Example response:

```json
{
  "session_id": "sess_abc123",
  "diff": "--- a/workflow.yaml\n+++ b/workflow.yaml\n@@ -12,6 +12,8 @@\n     params:\n       prompt_ref: \"../prompts/support_prompts.yaml#faq\"\n+      fallback_message: \"I'm sorry, I don't have information on that topic. Please contact support.\"\n       model:\n         provider: openai",
  "preview_yaml": "version: \"1.0\"\n..."
}
```

Review the `diff` field before applying. Keep the `session_id` — you'll need it for `apply_update` or `rollback_update`.

## Step 5: Regression Test — Validate with Golden Cases

Before applying the change, verify that existing behavior is preserved using golden cases.

### Save a golden case from a successful trace

```bash
yagra golden save \
  --trace .yagra/traces/my-workflow/my-workflow_20260222T120000_a1b2c3d4.json \
  --name happy-path
```

### Run golden tests via CLI

```bash
yagra golden test --workflow workflow.yaml
```

Example output:

```
Running golden tests for workflow.yaml
  ✓ happy-path  (2/2 nodes passed)

Results: 1 passed, 0 failed
```

### Run golden tests via MCP tool

```json
{
  "tool": "run_golden_tests",
  "arguments": {
    "workflow_path": "workflow.yaml"
  }
}
```

Example response:

```json
{
  "results": [
    {
      "case_name": "happy-path",
      "passed": true,
      "execution_path_match": true,
      "node_results": [
        {"node_id": "classifier", "status": "pass", "strategy_used": "exact"},
        {"node_id": "answer_faq", "status": "pass", "strategy_used": "structural"}
      ],
      "summary": "All 2 nodes passed"
    }
  ],
  "total": 1,
  "passed": 1,
  "failed": 0
}
```

If any test fails, revise the proposal before applying.

## Step 6: Apply or Rollback — Commit the Change

### Apply the proposal

Once golden tests pass, apply the change:

```json
{
  "tool": "apply_update",
  "arguments": {
    "session_id": "sess_abc123"
  }
}
```

The workflow YAML is updated in place. A backup of the previous version is kept automatically.

### Rollback if needed

If the applied change causes issues, roll back:

```json
{
  "tool": "rollback_update",
  "arguments": {
    "session_id": "sess_abc123"
  }
}
```

The workflow YAML is restored to the version before `apply_update` was called.

---

## Worked Example: Improving a Translation Workflow

This end-to-end example shows how to improve a simple translation workflow step by step.

### Initial Setup

Create the workflow directory:

```bash
mkdir translate-workflow && cd translate-workflow
```

Create `workflow.yaml`:

```yaml
version: "1.0"
start_at: translate
end_at:
  - finish
nodes:
  - id: translate
    handler: llm
    params:
      prompt_ref: "prompts/translate_prompts.yaml#translate"
      output_key: translation
      model:
        provider: openai
        name: gpt-4.1-mini
  - id: finish
    handler: passthrough
edges:
  - source: translate
    target: finish
```

Create `prompts/translate_prompts.yaml`:

```yaml
translate:
  system: "You are a translator."
  user: "Translate the following text to English:\n\n{text}"
```

Create `handlers.py`:

```python
from typing import TypedDict
from yagra import Yagra
from yagra.handlers import create_llm_handler


class TranslateState(TypedDict, total=False):
    text: str
    translation: str


def passthrough(state: TranslateState, params: dict) -> dict:
    return {}


registry = {
    "llm": create_llm_handler(),
    "passthrough": passthrough,
}
```

Validate:

```bash
yagra validate --workflow workflow.yaml
# ✓ ワークフローは valid です。
```

### Run & Capture Traces

Create `run.py`:

```python
from handlers import registry, TranslateState
from yagra import Yagra

app = Yagra.from_workflow(
    workflow_path="workflow.yaml",
    registry=registry,
    state_schema=TranslateState,
    observability=True,
)

test_inputs = [
    {"text": "こんにちは、世界！"},
    {"text": "今日は天気がいいですね。"},
    {"text": ""},  # edge case: empty input
]

for inp in test_inputs:
    app.invoke(inp, trace=True)

print("Traces saved to .yagra/traces/")
```

```bash
python run.py
```

### Analyze Traces

Start MCP server in a separate terminal:

```bash
yagra mcp
```

Call `analyze_traces` from your agent:

```json
{
  "tool": "analyze_traces",
  "arguments": {"workflow_name": "workflow", "limit": 10}
}
```

The agent finds that the `translate` node returns an empty string for the empty-input case.
Suggestion: add input validation instructions to the system prompt.

### Save a Golden Case

```bash
yagra golden save \
  --trace .yagra/traces/workflow/workflow_20260222T120000_a1b2c3d4.json \
  --name normal-translation \
  --strategy translate:structural
```

### Propose an Update

```json
{
  "tool": "propose_update",
  "arguments": {
    "workflow_path": "workflow.yaml",
    "instruction": "Update the translate node's system prompt to handle empty input gracefully by returning an empty string without error."
  }
}
```

The agent updates `prompts/translate_prompts.yaml`:

```yaml
translate:
  system: |
    You are a professional translator.
    If the input text is empty, return an empty string without any additional message.
  user: "Translate the following text to English:\n\n{text}"
```

Note the `session_id` from the response (e.g., `sess_xyz789`).

### Run Golden Tests

```bash
yagra golden test --workflow workflow.yaml
# ✓ normal-translation  (1/1 nodes passed)
```

All tests pass.

### Apply the Change

```json
{
  "tool": "apply_update",
  "arguments": {"session_id": "sess_xyz789"}
}
```

The improved workflow is now live. Run more test cases and repeat the cycle as needed.

---

## Agent Automation

For AI coding agents (Claude Code, Cursor, Copilot, etc.), you can automate the entire cycle using Yagra's MCP tools. The recommended tool call sequence is:

```
analyze_traces        → identify problems in recent executions
propose_update        → generate a YAML diff
run_golden_tests      → verify existing behavior is preserved
apply_update          → commit the improvement
  (or rollback_update if tests failed)
```

For system prompt examples and a full automation guide, see:
[Agent Integration Guide](../../../agent-integration-guide.md)

## Next Steps

- [Workflow YAML Reference](workflow_yaml.md) — complete YAML schema
- [CLI Reference](../cli_reference.md) — `yagra golden`, `yagra mcp`, and more
- [Examples](../examples.md) — ready-to-run workflow examples
