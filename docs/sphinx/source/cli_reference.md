# CLI Reference

Yagra provides command-line tools for workflow management, validation, and visualization.

## Command Overview

```bash
yagra <command> [options]
```

**Available commands**:
- `init`: Initialize from template
- `schema`: Export JSON Schema
- `validate`: Validate workflow YAML
- `golden`: Manage golden regression test cases
- `studio`: Launch visual editor WebUI
- `handlers`: Display params schema for built-in handlers
- `explain`: Statically analyze workflow YAML
- `prompt`: Manage and inspect prompt YAML files
- `mcp`: Start MCP server in stdio mode

## `yagra init`

Initialize a workflow from a template.

### Usage

```bash
yagra init --template <template_name> --output <directory> [--force]
yagra init --list
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--template` | Template name to use (`branch`, `chat`, `human-review`, `loop`, `multi-agent`, `parallel`, `rag`, `subgraph`, `tool-use`) | Required (unless `--list`) |
| `--output` | Output directory | Current directory (`.`) |
| `--force` | Overwrite existing files | `False` |
| `--list` | List available templates | N/A |

### Examples

**List templates**:

```bash
yagra init --list
```

Output:
```
Available templates:
  - branch
  - chat
  - human-review
  - loop
  - multi-agent
  - parallel
  - rag
  - subgraph
  - tool-use
```

**Initialize from template**:

```bash
yagra init --template branch --output my-workflow
```

**Overwrite existing files**:

```bash
yagra init --template loop --output existing-dir --force
```

### Behavior

1. Copies template files to output directory
2. Creates `workflow.yaml` (and `prompts/<template>_prompts.yaml` if the template uses prompts)
3. Validates the generated workflow
4. Reports success or validation errors

## `yagra schema`

Export JSON Schema for workflow YAML. Useful for coding agents and IDE autocomplete.

### Usage

```bash
yagra schema [--output <file>]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--output` | Output file path | Print to stdout |

### Examples

**Print to stdout**:

```bash
yagra schema
```

**Save to file**:

```bash
yagra schema --output workflow-schema.json
```

### Behavior

- Exports `GraphSpec` Pydantic model as JSON Schema
- Includes all field definitions, validation rules, and descriptions
- Compatible with JSON Schema Draft 7

### Use Cases

- **Coding agents**: Let agents generate valid workflows
- **IDE support**: Enable autocomplete in editors (e.g., VS Code with YAML extension)
- **Documentation**: Generate schema documentation automatically

## `yagra validate`

Validate a workflow YAML file and report issues.

### Usage

```bash
yagra validate --workflow <file> [--bundle-root <dir>] [--format <text|json>]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--workflow` | Path to workflow YAML | Required |
| `--bundle-root` | Base directory for reference resolution | Workflow parent directory |
| `--format` | Output format (`text` or `json`) | `text` |

### Examples

**Basic validation**:

```bash
yagra validate --workflow workflows/support.yaml
```

**JSON output** (for agent consumption):

```bash
yagra validate --workflow workflows/support.yaml --format json
```

**Custom bundle root**:

```bash
yagra validate --workflow workflows/support.yaml --bundle-root /path/to/project
```

### Output Formats

#### Text Format (Default)

Human-readable output:

```
✓ ワークフローは valid です。
```

Or if invalid:

```
✗ ワークフローに問題があります:

[ERROR] nodes.0.id: field required
[ERROR] edges.0.source: node 'unknown_node' does not exist
```

#### JSON Format

Structured output for agents:

```json
{
  "is_valid": false,
  "issues": [
    {
      "severity": "error",
      "category": "schema",
      "message": "field required",
      "location": "nodes.0.id"
    },
    {
      "severity": "error",
      "category": "reference",
      "message": "node 'unknown_node' does not exist",
      "location": "edges.0.source"
    }
  ]
}
```

### Exit Codes

- `0`: Valid workflow
- `1`: Invalid workflow

### Validation Steps

Yagra validates:
1. **Schema compliance**: YAML matches `GraphSpec` Pydantic model
2. **Node ID uniqueness**: No duplicate node IDs
3. **Edge references**: All `source`/`target` nodes exist
4. **Start/End validity**: `start_at` and `end_at` nodes exist
5. **Prompt references**: `prompt_ref` paths resolve to valid files
6. **Fallback references**: `fallback` node IDs exist and are not self-referencing
7. **Prompt-state consistency** (warning): `{variable}` in prompts should exist in `state_schema` or upstream `output_key`; `output_key` should be declared in `state_schema`

**Note**: `is_valid` is determined by **error-severity issues only**. Warning and info-level issues (such as prompt-state consistency hints) are reported but do not cause `is_valid` to be `false`.

## `yagra golden`

Manage golden cases for workflow regression testing.

### Usage

```bash
yagra golden save --trace <trace.json> --name <case-name> [--description <text>] \
  [--strategy <node_id:strategy>]... [--golden-dir <dir>]
yagra golden test --workflow <workflow.yaml> [--name <case-name>] [--golden-dir <dir>] \
  [--bundle-root <dir>] [--format <text|json>]
yagra golden list [--workflow <workflow-name>] [--golden-dir <dir>] [--format <text|json>]
```

### `yagra golden save`

Create a golden case from a trace JSON file.

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--trace` | Path to trace JSON file | Required |
| `--name` | Golden case name (kebab-case) | Required |
| `--description` | Human-readable case description | `""` |
| `--strategy` | Per-node comparison override. Repeatable. Format: `node_id:strategy` (`exact`, `structural`, `skip`, `auto`) | None |
| `--golden-dir` | Golden case base directory | `.yagra/golden` |

#### Examples

```bash
# Basic save
yagra golden save --trace .yagra/traces/translate/run.json --name happy-path

# Save with per-node strategy overrides
yagra golden save \
  --trace .yagra/traces/translate/run.json \
  --name strict-format-check \
  --strategy translate:structural \
  --strategy format:exact
```

### `yagra golden test`

Run saved golden cases against a workflow YAML.

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--workflow` | Path to workflow YAML file | Required |
| `--name` | Specific case name (runs all cases if omitted) | None |
| `--golden-dir` | Golden case base directory | `.yagra/golden` |
| `--bundle-root` | Base directory for split-reference resolution | Workflow parent |
| `--format` | Output format (`text` or `json`) | `text` |

#### Examples

```bash
# Run all cases for a workflow
yagra golden test --workflow workflows/translate.yaml

# Run one case
yagra golden test --workflow workflows/translate.yaml --name happy-path

# Machine-readable output
yagra golden test --workflow workflows/translate.yaml --format json
```

### `yagra golden list`

List saved golden cases.

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--workflow` | Filter by workflow name | None |
| `--golden-dir` | Golden case base directory | `.yagra/golden` |
| `--format` | Output format (`text` or `json`) | `text` |

#### Example

```bash
yagra golden list
```

## `yagra studio`

Launch an interactive WebUI for visual workflow editing.

### Usage

```bash
yagra studio [--workflow <file>] [--bundle-root <dir>] [--ui-state <file>] \
  [--workspace-root <dir>] [--backup-dir <dir>] [--host <host>] [--port <port>]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--workflow` | Workflow YAML to edit | None (launcher mode) |
| `--bundle-root` | Base directory for reference resolution | Workflow parent |
| `--ui-state` | UI sidecar JSON path | `<workflow>.workflow-ui.json` |
| `--workspace-root` | Workspace root for launcher | Current directory |
| `--backup-dir` | Backup directory | `.yagra/backups` |
| `--host` | Bind host | `127.0.0.1` |
| `--port` | Bind port | `8787` |

### Examples

**Launcher mode** (recommended):

```bash
yagra studio --port 8787
```

Opens a launcher UI where you can:
- Select existing workflows
- Create new workflows

**Direct workflow editing**:

```bash
yagra studio --workflow workflows/support.yaml --port 8787
```

**Custom workspace**:

```bash
yagra studio --workspace-root /path/to/project --port 8787
```

### Features

#### Visual Editing
- **Node Properties**: Handler input uses a type selector with automatic form adaptation:
  - **Handler type selector**: choose `llm`, `structured_llm`, `streaming_llm`, or `custom`
    - Predefined types auto-fill the handler name (no manual typing required)
    - `custom` type enables free-text input for user-defined handlers
  - `llm` / `structured_llm` / `streaming_llm` → Prompt Settings and Model Settings displayed
  - `structured_llm` → Additional **Schema Settings** section (edit `schema_yaml` as YAML text)
  - `streaming_llm` → Additional **Streaming Settings** section (`stream: false` checkbox)
  - `custom` → LLM-specific sections hidden (free-text handler name input visible)
- **Drag & Drop**: Add nodes, connect edges, adjust layout
- **Re-wiring**: Drag edge endpoints to change connections

#### Workflow Settings (Right Panel)

The **Workflow Settings** panel on the right side of the canvas controls global workflow configuration:

| Field | Description |
|-------|-------------|
| `version` | Workflow schema version (default: `1.0`) |
| `start_at` | Entry node selected from a dropdown |
| `end_at` | Exit nodes selected via checkboxes |
| `interrupt_before` | Nodes to pause before (HITL) selected via checkboxes |
| `interrupt_after` | Nodes to pause after (HITL) selected via checkboxes |
| `state_schema` | Typed state field definitions (table editor) |

##### Setting Up `state_schema` in Studio

The `state_schema` section lets you define typed fields for the workflow state directly in the UI:

1. In the **Workflow Settings** panel, scroll to the **state_schema** section
2. Click **+ Add Field** to add a new row
3. Fill in each column:
   - **field name**: The key used in `state` (e.g., `messages`, `results`, `query`)
   - **type**: One of `str`, `int`, `float`, `bool`, `list`, `dict`, `messages`
   - **reducer**: Leave empty for default overwrite behavior, or select `add` for fan-in merging of list fields
4. Click **✕** on a row to remove it
5. Click **Preview Diff** to review the generated YAML, then **Save**

**Example configurations**:

| Use Case | field name | type | reducer |
|----------|-----------|------|---------|
| Chat history | `messages` | `messages` | (none) |
| Parallel fan-in | `results` | `list` | `add` |
| Query string | `query` | `str` | (none) |

The generated YAML will look like:

```yaml
state_schema:
  messages:
    type: messages
  results:
    type: list
    reducer: add
  query:
    type: str
```

> **Note**: `fan_out` edges and `subgraph` nodes require YAML direct editing — the Studio currently supports `state_schema` only as a table editor.

#### Resilience Settings (Node Properties)

The **Resilience Settings** section in the Node Properties panel allows configuration of retry, timeout, and fallback behavior per node. Available for all handler types.

| Field | Description |
|-------|-------------|
| **Enable retry** | Toggle to activate retry behavior |
| **max attempts** | Maximum retry attempts (1–10). Default: 3 |
| **backoff** | Strategy: `exponential` (delays double each attempt) or `fixed` (constant delay) |
| **base delay (s)** | Initial delay in seconds between retries (0–60). Default: 2 |
| **timeout (seconds)** | Maximum execution time for the node (1–600). Leave empty for no timeout |
| **fallback node** | Dropdown to select a fallback node (executes if the node fails after retries) |

These settings map directly to the YAML `retry`, `timeout_seconds`, and `fallback` fields on the node. See [Workflow YAML Reference — Resilience](user_guide/workflow_yaml.md#resilience-retry-timeout-fallback) for details.

#### Diff Preview
- View exact YAML diff before saving
- Validation results inline with diff
- Reject or accept changes

#### Backup & Rollback
- Automatic backup on save
- List available backups
- Rollback to previous version by backup ID

#### Live Validation

Studio validates your workflow automatically as you edit:

- **Debounced auto-validation**: Every form change (node edits, edge edits, metadata changes, connections) triggers a validation request after a 400ms debounce delay via `POST /api/workflow/validate`
- **Severity-aware display**: Issues are shown with color-coded severity badges — `error` (red), `warning` (yellow), `info` (blue)
- **Canvas node highlights**: Nodes with validation errors are highlighted with a red border; nodes with warnings get a yellow border
- **Warning-aware pass state**: When `is_valid` is true but warnings/info exist, displays "Validation passed (with warnings)" alongside the issue list
- **Prevents saving invalid workflows**: Save is blocked when error-level issues exist

### Accessing Studio

After starting the server:

```bash
yagra studio --port 8787
```

Output:

```
workflow studio started: http://127.0.0.1:8787
press Ctrl+C to stop
```

Open `http://127.0.0.1:8787/` in your browser.

### Studio UI Overview

- **Graph Canvas**: Visual workflow editor (drag, drop, connect)
- **Node Properties**: Form for editing selected node
- **Edge Properties**: Form for editing selected edge
- **Diff Panel**: Preview changes before saving
- **Backup Panel**: Manage backups and rollback

### Studio Workflow

1. **Select/Create Workflow**: Choose from launcher or load directly
2. **Edit Visually**:
   - Click node to edit properties
   - Drag from output port to input port to connect
   - Drag edge endpoint to rewire
3. **Preview Changes**: Click "Preview Diff"
4. **Save**: Click "Save" to persist changes
5. **Rollback** (if needed): Select backup and restore

## `yagra handlers`

Display the params schema for each built-in handler.

### Usage

```bash
yagra handlers [--format <text|json>]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format (`text` or `json`) | `text` |

### Built-in Handlers

| Handler | Description |
|---------|-------------|
| `llm` | Standard LLM call with prompt rendering |
| `structured_llm` | LLM call that returns structured (schema-constrained) output |
| `streaming_llm` | LLM call with server-sent event streaming support |

### Examples

**Text output** (human-readable):

```bash
yagra handlers
```

Output:

```
llm
  model        (str, required)   LLM model name to use.
  temperature  (float, optional) Sampling temperature. Default: 0.0
  ...

structured_llm
  model        (str, required)   LLM model name to use.
  schema_yaml  (str, required)   YAML string defining the output schema.
  ...

streaming_llm
  model        (str, required)   LLM model name to use.
  stream       (bool, optional)  Enable streaming mode. Default: true
  ...
```

**JSON output** (for agent consumption):

```bash
yagra handlers --format json
```

Output:

```json
{
  "llm": { ... },
  "structured_llm": { ... },
  "streaming_llm": { ... }
}
```

## `yagra explain`

Statically analyze a workflow YAML and report its structure: entry point, exit points, execution paths, required handlers, and variable flow.

### Usage

```bash
yagra explain --workflow <file|-> [--bundle-root <dir>] [--format <text|json>]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--workflow` | Path to workflow YAML, or `-` to read from stdin | Required |
| `--bundle-root` | Base directory for reference resolution | Workflow parent directory |
| `--format` | Output format (`text` or `json`) | `json` |

### Examples

**Analyze a workflow file**:

```bash
yagra explain --workflow workflows/support.yaml
```

**Read from stdin**:

```bash
cat workflows/support.yaml | yagra explain --workflow -
```

**Text output**:

```bash
yagra explain --workflow workflows/support.yaml --format text
```

**Pipe JSON output to `jq`**:

```bash
yagra explain --workflow workflows/support.yaml | jq '.execution_paths'
```

### JSON Output Structure

```json
{
  "entry_point": "start_node",
  "exit_points": ["end_node_a", "end_node_b"],
  "execution_paths": [
    ["start_node", "branch_node", "end_node_a"],
    ["start_node", "branch_node", "end_node_b"]
  ],
  "required_handlers": ["llm", "structured_llm"],
  "variable_flow": {
    "start_node": {
      "inputs": [],
      "outputs": ["user_input"]
    },
    "branch_node": {
      "inputs": ["user_input"],
      "outputs": ["response"]
    }
  }
}
```

| Field | Description |
|-------|-------------|
| `entry_point` | ID of the node where execution begins |
| `exit_points` | IDs of nodes where execution terminates |
| `execution_paths` | All possible node sequences from entry to exit |
| `required_handlers` | Distinct handler names referenced by the workflow |
| `variable_flow` | Per-node mapping of input and output variable names |

(yagra-analyze)=
## `yagra analyze`

Aggregate and summarize execution traces stored under `.yagra/traces/`. Useful for identifying slow nodes, high error rates, or patterns across multiple runs.

### Usage

```bash
yagra analyze [--trace-dir <dir>] [--workflow <name>] [--limit <n>] [--format <text|json>]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--trace-dir` | Root trace directory | `.yagra/traces` |
| `--workflow` | Filter by workflow name | All workflows |
| `--limit` | Limit to N most recent traces | No limit |
| `--format` | Output format (`text` or `json`) | `text` |

### Examples

**Summarize all traces**:

```bash
yagra analyze
```

**Filter by workflow name**:

```bash
yagra analyze --workflow my-workflow
```

**Show the 10 most recent traces as JSON**:

```bash
yagra analyze --workflow my-workflow --limit 10 --format json
```

**Pipe JSON output to `jq`**:

```bash
yagra analyze --format json | jq '.node_summaries[] | select(.error_rate > 0)'
```

### JSON Output Structure

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
      "error_rate": 0.05
    }
  ],
  "suggestions": [
    "answer_faq: high latency detected — consider prompt optimization"
  ]
}
```

### See Also

- Use `yagra mcp` and the `analyze_traces` MCP tool for agent-driven trace analysis
- Use `get_traces` MCP tool to inspect individual trace records

## `yagra prompt`

Manage and inspect prompt YAML files.

### `yagra prompt info`

Display metadata and version information for a prompt YAML file.

```bash
yagra prompt info --file <path> [--format text|json]
```

**Options**:
- `--file` (required): Path to the prompt YAML file
- `--format`: Output format — `text` (default) or `json`

**Output** (text format):
- File path
- Version from `_meta.version` (or "(not set)" if absent)
- Changelog entries from `_meta.changelog` (if present)
- List of prompt keys (excluding `_meta`)

**Example**:

```bash
$ yagra prompt info --file prompts.yaml
File: /path/to/prompts.yaml
Version: 2.0
Changelog:
  - 2.0: Added persona variable to system prompt
  - 1.0: Initial version
Prompt keys: greeting, farewell
```

**JSON output**:

```bash
$ yagra prompt info --file prompts.yaml --format json
{
  "file": "/path/to/prompts.yaml",
  "version": "2.0",
  "changelog": ["2.0: Added persona variable", "1.0: Initial version"],
  "prompt_keys": ["greeting", "farewell"],
  "meta": {"version": "2.0", "changelog": ["..."]}
}
```

### Prompt YAML `_meta` Section

Prompt YAML files can include an optional `_meta` section for version metadata:

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

The `_meta.version` value is checked against `@version` suffixes in `prompt_ref` references during validation.  See [Prompt Model](user_guide/prompt_model.md) for details.

(yagra-mcp)=
## `yagra mcp`

Start a Model Context Protocol (MCP) server in stdio mode, allowing AI agents and editors to interact with Yagra programmatically.

### Installation

The MCP extra must be installed:

```bash
uv add 'yagra[mcp]'
```

### Usage

```bash
yagra mcp
```

The server communicates over stdin/stdout using the MCP protocol. No additional options are required.

### Provided Tools

| Tool | Required params | Description |
|------|----------------|-------------|
| `validate_workflow` | `yaml_content` | Validate a workflow YAML string and return structured issues. Pass `base_dir` to resolve relative `prompt_ref` paths. |
| `validate_workflow_file` | `workflow_path` | Validate a workflow YAML file by path (more convenient than `validate_workflow` when the file is accessible). |
| `explain_workflow` | `yaml_content` | Statically analyze a workflow YAML string and return execution paths, required handlers, and variable flow. |
| `explain_workflow_file` | `workflow_path` | Statically analyze a workflow YAML file by path. |
| `list_templates` | — | List available `yagra init` templates with name, description, and use_case. |
| `list_handlers` | — | List built-in handlers and their params schemas. |
| `get_template` | `name` | Return the file contents of a template (workflow.yaml + prompt files). Use `list_templates` first to get the name. |
| `get_traces` | — | Retrieve raw execution trace records from `.yagra/traces/`. Optional: `workflow_name`, `limit`, `trace_dir`. |
| `analyze_traces` | — | Aggregate execution traces and return per-node statistics (success rate, latency, token usage, cost). Optional: `workflow_name`, `limit`, `trace_dir`. |
| `propose_update` | `workflow_path`, `candidate_yaml` | Preview a YAML change as a diff with validation result. Optional: `reason`. |
| `apply_update` | `workflow_path`, `candidate_yaml` | Apply the candidate YAML with an automatic backup. Returns `backup_id`. Optional: `base_revision`, `backup_dir`. |
| `rollback_update` | `workflow_path`, `backup_id` | Restore the workflow to a previous backup. Optional: `backup_dir`. |
| `run_golden_tests` | `workflow_path` | Run golden regression tests against the workflow. Optional: `golden_dir`, `case_name`, `format`. |

### Example: Claude Desktop Integration

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "yagra": {
      "command": "yagra",
      "args": ["mcp"]
    }
  }
}
```

### Example: VS Code / Cursor Integration

```json
{
  "mcp": {
    "servers": {
      "yagra": {
        "command": "yagra",
        "args": ["mcp"]
      }
    }
  }
}
```

Once connected, the agent has access to all 13 tools listed in the table above. See the [Optimization Cycle guide](user_guide/optimization_cycle.md) for end-to-end usage examples.

## Environment Variables

Yagra does not currently use environment variables for CLI configuration. All options are passed via command-line flags.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation error or operation failed |
| 2 | Invalid command-line arguments |

## Next Steps

- [Getting Started](getting_started.md)
- [Workflow YAML Reference](user_guide/workflow_yaml.md)
- [API Reference](api.md)
