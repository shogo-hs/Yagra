# Prompt & Model Configuration

This guide explains how to configure prompts and models in Yagra workflows.

## Overview

Yagra separates configuration from code:
- **Prompts**: Stored in external YAML files, referenced via `prompt_ref`
- **Models**: Defined inline in workflow YAML under `params.model`

This separation enables:
- Non-engineers to adjust prompts without touching code
- Easy A/B testing of different models
- Version control and review of prompt changes

## Prompt Configuration

### External Prompt Files

Prompts are stored in separate YAML files (typically under `prompts/`).

**Example**: `prompts/support_prompts.yaml`

```yaml
faq:
  system: |
    You are a helpful FAQ assistant.
    Answer questions about pricing, features, and policies.
  user: |
    Question: {query}

general:
  system: |
    You are a general-purpose assistant.
  user: |
    User query: {query}
```

### Referencing Prompts in Workflow

Use `prompt_ref` to link a node to a prompt:

```yaml
nodes:
  - id: "faq_bot"
    handler: "answer_faq"
    params:
      prompt_ref: "../prompts/support_prompts.yaml#faq"
```

**Syntax**:
- `<path>`: Path to YAML file (relative to workflow or `bundle_root`)
- `#<key>`: Key path within the YAML (e.g., `#faq`, `#nested.key`)

### Prompt Resolution

Yagra resolves `prompt_ref` before passing `params` to the handler:

```python
def answer_faq(state: AgentState, params: dict) -> dict:
    prompt = params["prompt"]  # Resolved content
    system = prompt["system"]
    user = prompt["user"]
    # {variable} placeholders are automatically expanded from state
    # by the built-in LLM handlers — no manual .format() needed
    # ... call LLM with system and user prompts
```

**Note**: `prompt_ref` is removed from `params` after resolution—use `params["prompt"]` instead.

> **Tip (built-in handlers)**: When using `llm`, `streaming_llm`, or `structured_llm`, you do **not** need to call `.format()` yourself. The handler automatically extracts every `{variable}` placeholder from **both** the `system` and `user` templates and substitutes the corresponding values from the graph state.

### Path Resolution Rules

1. **Explicit relative path** (e.g., `../prompts/foo.yaml`):
   - Resolved relative to the workflow YAML file

2. **Implicit path** (e.g., `support_prompts.yaml`):
   - First tries workflow parent directory
   - Then searches up the directory tree

3. **Custom `bundle_root`**:
   - Use `--bundle-root` to override the base directory

Example:

```bash
yagra validate --workflow workflows/support.yaml --bundle-root /path/to/project
```

### Prompt YAML Structure

Prompts must be mappings with `system` and `user` keys:

```yaml
my_prompt:
  system: "System message"
  user: "User message with {placeholder}"
```

You can nest prompts:

```yaml
retrieval:
  search:
    system: "Search prompt"
    user: "Query: {query}"
  rerank:
    system: "Rerank prompt"
    user: "Candidates: {candidates}"
```

Reference nested prompts: `prompt_ref: "prompts.yaml#retrieval.search"`

### State Variable Injection in Prompts

Built-in LLM handlers (`llm`, `streaming_llm`, `structured_llm`) automatically inject state values into **both** the `system` and `user` prompt templates.

**How it works**:

Every `{variable}` placeholder found in the `system` or `user` template is automatically extracted and resolved from the current graph state.

```yaml
# system uses {persona}, user uses {query} — both are auto-detected
my_prompt:
  system: |
    You are {persona}. Answer concisely.
  user: |
    Question: {query}
```

> **Note**: If a placeholder key is not present in the current state the handler substitutes an empty string and logs a warning—it does **not** raise an exception.

### Prompts in Custom Handler Nodes

You can associate a prompt with a `custom` handler node just like you would with a built-in LLM handler.
The resolved `params["prompt"]` dict is passed to your function, and you can apply the templates however you like.

**Workflow YAML**:

```yaml
nodes:
  - id: "planner"
    handler: "planner_handler"   # custom Python function
    params:
      prompt_ref: "../prompts/branch_prompts.yaml#planner"
```

**Handler code**:

```python
def planner_handler(state: AgentState, params: dict) -> dict:
    prompt = params.get("prompt", {})
    system = prompt.get("system", "")
    user = prompt.get("user", "").format(**state)  # manual substitution
    # ... call your LLM or custom logic
    return {"plan": result}
```

> **Studio**: When a node's handler type is set to **custom**, the *Prompt Settings* section is shown in the Node Properties panel so you can attach and edit a prompt without writing YAML by hand.

## Prompt Variable Type-Safety Validation

Yagra validates that prompt template variables are consistent with your workflow's `state_schema` and node outputs. These checks produce **warning** or **info** level issues (not errors), so they do not block workflow execution but help catch inconsistencies early.

### What is checked

1. **Variable exists in available keys** (warning): Each `{variable}` in a prompt template should be declared in `state_schema` or produced as an `output_key` by another node in the workflow.

2. **output_key declared in state_schema** (warning): When a node specifies an explicit `output_key`, it should be declared in the workflow-level `state_schema` (only checked when `state_schema` is non-empty).

3. **No state_schema defined** (info): When `state_schema` is not defined but prompt variables are used, an informational message is emitted suggesting that adding a `state_schema` would enable type-safety checks.

### Example — variable not in state_schema (warning)

```yaml
state_schema:
  answer:
    type: str
  # 'query' not declared here

nodes:
  - id: "respond"
    handler: "llm"
    params:
      prompt:
        user: "Question: {query}"    # 'query' not in state_schema → warning
      model: { provider: openai, name: gpt-4o-mini }
```

**Fix**: Declare `query` in `state_schema`:

```yaml
state_schema:
  query:
    type: str
  answer:
    type: str
```

### Example — output_key not in state_schema (warning)

```yaml
state_schema:
  query:
    type: str
  # 'extracted_info' not declared here

nodes:
  - id: "extract"
    handler: "llm"
    params:
      output_key: "extracted_info"    # Not in state_schema → warning
      model: { provider: openai, name: gpt-4o-mini }
```

**Fix**: Add `extracted_info` to `state_schema`:

```yaml
state_schema:
  query:
    type: str
  extracted_info:
    type: dict
```

### Interaction with `is_valid`

These prompt-state validation issues are **warning/info only** and do **not** cause `is_valid` to be `false`. The `is_valid` flag is determined exclusively by error-severity issues (schema violations, missing references, etc.).

## Prompt Versioning

Prompt YAML files can include an optional `_meta` section to track version metadata:

```yaml
_meta:
  version: "2.0"
  changelog:
    - "2.0: Added persona variable to system prompt"
    - "1.0: Initial version"

greeting:
  system: "You are {persona}."
  user: "Hello! My name is {user_name}."
```

### Version Pinning with `@version`

You can pin a specific prompt version in `prompt_ref` using the `@version` suffix:

```yaml
nodes:
  - id: "greet"
    handler: "llm"
    params:
      prompt_ref: "prompts.yaml#greeting@2.0"
      model:
        provider: "openai"
        name: "gpt-4o-mini"
```

Supported formats:
- `prompts.yaml#greeting@v2` — file + key + version
- `prompts.yaml@v2` — file + version (entire file)
- `prompts.yaml#greeting` — file + key without version (existing syntax)

### Version Validation

Yagra validates version consistency during workflow validation:

| Scenario | Severity | Message |
|---|---|---|
| `@version` matches `_meta.version` | (no issue) | — |
| `@version` differs from `_meta.version` | **warning** | Version mismatch detected |
| `@version` specified but `_meta.version` missing | **warning** | Prompt file has no version metadata |
| `_meta.version` exists but `prompt_ref` unpinned | **info** | Consider pinning with `@version` suffix |

These version validation issues are **warning/info only** and do **not** affect `is_valid`.

### Inspecting Prompt Metadata

Use the CLI to inspect prompt file metadata:

```bash
yagra prompt info --file prompts.yaml
yagra prompt info --file prompts.yaml --format json
```

See [CLI Reference](../cli_reference.md) for details.

## Model Configuration

### Inline Model Definition

Models are defined directly in workflow YAML under `params.model`:

```yaml
nodes:
  - id: "generator"
    handler: "generate_answer"
    params:
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.7
          max_tokens: 1000
```

**Fields**:
- `provider` (str): Model provider (e.g., `"openai"`, `"anthropic"`)
- `name` (str): Model name (e.g., `"gpt-4.1-mini"`, `"claude-3-sonnet"`)
- `kwargs` (dict, optional): Additional arguments (temperature, max_tokens, etc.)

### Accessing Model Config in Handlers

```python
def generate_answer(state: AgentState, params: dict) -> dict:
    model_config = params.get("model", {})
    provider = model_config["provider"]
    name = model_config["name"]
    kwargs = model_config.get("kwargs", {})

    # Use with your LLM client
    # e.g., OpenAI(model=name, **kwargs)
    # ...
```

### Why Inline Instead of `model_ref`?

Earlier versions of Yagra supported `model_ref`, but it was removed in favor of inline definitions for simplicity. Inline definitions:
- Are easier to version control (single file)
- Reduce indirection (no need to chase references)
- Work well for most use cases

If you need to share model configs across multiple nodes, use YAML anchors:

```yaml
_model_defaults: &default_model
  provider: "openai"
  name: "gpt-4.1-mini"
  kwargs:
    temperature: 0.7

nodes:
  - id: "node_1"
    handler: "handler_1"
    params:
      model: *default_model
  - id: "node_2"
    handler: "handler_2"
    params:
      model:
        <<: *default_model
        kwargs:
          temperature: 0.9  # Override temperature
```

## Studio Integration

Yagra Studio provides visual editing for prompts and models:

1. **Prompt Editing** (LLM handlers **and** custom handler nodes):
   - Select a prompt YAML from dropdown (project YAML files, excluding tool and dot-directories)
   - Edit `system` and `user` fields in form
   - Auto-create prompt YAML if not selected
   - The *Prompt Settings* section is visible for `llm`, `structured_llm`, `streaming_llm`, and `custom` handler types

2. **Model Editing**:
   - Fill in `provider`, `name`, and `kwargs` via form
   - Changes are reflected in workflow YAML immediately

3. **Output Key** (LLM handler nodes only):
   - In the **Output Settings** section of the Node Properties panel, enter the state key where the handler result is stored
   - Leave blank to use the default (`"output"`)
   - Writes `params.output_key` to workflow YAML on Apply

4. **Diff Preview**:
   - Review changes before saving
   - See exact YAML diff with validation results

Launch Studio:

```bash
yagra studio --workflow workflows/support.yaml --port 8787
```

Open `http://127.0.0.1:8787/` and edit visually.

## Best Practices

### Prompt Management

1. **One file per domain**: Group related prompts (e.g., `support_prompts.yaml`, `rag_prompts.yaml`)
2. **Use descriptive keys**: `faq_system` is better than `prompt1`
3. **Include placeholders**: Use `{variable}` for dynamic content
4. **Version control**: Track prompt changes via Git for review and rollback

### Model Selection

1. **Match task complexity**: Use smaller models (e.g., `gpt-4.1-mini`) for simple tasks
2. **Tune temperature**: Lower (0.1-0.3) for factual, higher (0.7-0.9) for creative
3. **Set limits**: Use `max_tokens` to control output length and cost
4. **Test alternatives**: Swap models easily to compare quality and cost

## Example: Complete Configuration

**Workflow**: `workflows/support.yaml`

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
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.3
  - id: "general_bot"
    handler: "answer_general"
    params:
      prompt_ref: "../prompts/support_prompts.yaml#general"
      model:
        provider: "anthropic"
        name: "claude-3-haiku"
        kwargs:
          temperature: 0.7
          max_tokens: 500
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

**Prompts**: `prompts/support_prompts.yaml`

```yaml
faq:
  system: |
    You are a FAQ assistant. Provide concise answers to common questions.
  user: |
    Question: {query}

general:
  system: |
    You are a helpful assistant. Provide detailed answers to user queries.
  user: |
    Query: {query}
```

## Troubleshooting

### `prompt_ref` Not Resolved

**Error**: `ValidationError: prompt_ref path not found`

**Solutions**:
1. Check file path is correct (relative to workflow or `bundle_root`)
2. Ensure key exists in YAML (e.g., `#faq` in `support_prompts.yaml`)
3. Use `--bundle-root` to override base directory

### Model Config Not Passed

**Issue**: `model` is `None` or empty in handler

**Solution**: Ensure `params.model` is defined in workflow YAML:

```yaml
params:
  model:
    provider: "openai"
    name: "gpt-4.1-mini"
```

### Prompt Variable Not Found (`prompt_state_variable_not_found`)

**Warning**: `"prompt_state_variable_not_found": Prompt variable 'foo' not found in state_schema or upstream output_keys for node 'my_node'`

Yagra validates that every `{variable}` in a prompt template exists in `state_schema` or is produced by an upstream node's `output_key`. This is a **warning-level** check (does not affect `is_valid`).

**Fix option 1 — declare in `state_schema`**:

```yaml
state_schema:
  query:
    type: str
```

**Fix option 2 — produce it from an upstream node**:

```yaml
nodes:
  - id: "extract_query"
    handler: "llm"
    params:
      output_key: "query"   # Produces the 'query' key
```

## Next Steps

- [Branching & Loops](branching_loops.md)
- [Templates](templates.md)
- [CLI Reference](../cli_reference.md)
