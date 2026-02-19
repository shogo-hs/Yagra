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
- `visualize`: Generate visualization HTML
- `studio`: Launch visual editor WebUI
- `handlers`: Display params schema for built-in handlers
- `explain`: Statically analyze workflow YAML
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

## `yagra visualize`

Generate a read-only HTML visualization of the workflow.

### Usage

```bash
yagra visualize --workflow <file> [--bundle-root <dir>] [--output <file>] [--title <title>]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--workflow` | Path to workflow YAML | Required |
| `--bundle-root` | Base directory for reference resolution | Workflow parent directory |
| `--output` | Output HTML file path | `workflow-visualization.html` |
| `--title` | Page title | Workflow file name |

### Examples

**Basic visualization**:

```bash
yagra visualize --workflow workflows/support.yaml --output /tmp/workflow.html
```

**Custom title**:

```bash
yagra visualize --workflow workflows/loop.yaml --title "Loop Workflow" --output loop.html
```

### Output

- Standalone HTML file with embedded Mermaid diagram
- No internet connection required (Mermaid is bundled)
- Nodes, edges, and conditional branches are visualized
- Opens directly in any browser

### Example Visualization

![Visualization Example](https://via.placeholder.com/600x400?text=Workflow+Visualization)

- Nodes: Boxes
- Edges: Arrows
- Conditional edges: Labeled arrows

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

#### Diff Preview
- View exact YAML diff before saving
- Validation results inline with diff
- Reject or accept changes

#### Backup & Rollback
- Automatic backup on save
- List available backups
- Rollback to previous version by backup ID

#### Validation
- Real-time validation as you edit
- Detailed error messages with location
- Prevents saving invalid workflows

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

## `yagra mcp`

Start a Model Context Protocol (MCP) server in stdio mode, allowing AI agents and editors to interact with Yagra programmatically.

### Installation

The MCP extra must be installed:

```bash
pip install "yagra[mcp]"
```

### Usage

```bash
yagra mcp
```

The server communicates over stdin/stdout using the MCP protocol. No additional options are required.

### Provided Tools

| Tool | Description |
|------|-------------|
| `validate_workflow` | Validate a workflow YAML and return structured issues |
| `explain_workflow` | Statically analyze a workflow and return structure report |
| `list_templates` | List available `yagra init` templates |
| `list_handlers` | List built-in handlers with their params schema |

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

Once connected, the agent can call `validate_workflow`, `explain_workflow`, `list_templates`, and `list_handlers` directly as tools.

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
