# Changelog

All notable changes to Yagra are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For the canonical changelog (Japanese), see [CHANGELOG.md](https://github.com/shogo-hs/Yagra/blob/main/CHANGELOG.md) in the repository root.

## [Unreleased]

### Added
- ✨ **C-1: Retry / Fallback / Timeout YAML declaration**: Node-level retry (max_attempts, backoff strategy, base_delay_seconds), timeout_seconds, and fallback can now be declared directly in YAML
  - `RetrySpec` model added (max_attempts: 1–10, backoff: exponential|fixed, base_delay_seconds: 0–60)
  - `NodeSpec` extended with `retry`, `timeout_seconds`, `fallback` fields (all Optional)
  - `state_graph_builder` automatically wraps nodes with retry, timeout, and fallback routing
  - `_retry_override` introduced in LLM handlers to prevent double retry when YAML-level retry is configured
  - Schema validation enforces fallback node existence and rejects self-referencing fallbacks
- ✨ **F-0: Studio UI Resilience Settings**: Node Properties panel now includes a "Resilience Settings" section with retry configuration (Enable retry checkbox, max_attempts, backoff, base_delay), timeout_seconds input, and fallback node dropdown. Available for all handler types
- ✨ **D-1: Prompt variable × state_schema type-safety validation**: Added `prompt_state_validator`. Validates that `{variable}` placeholders in prompt templates exist in state_schema or upstream node output_keys (warning level). Also warns when output_key is not declared in state_schema. Emits info when state_schema is undefined but variables are used
- ✨ **F-2: Studio real-time validation**: Automatically validates on form changes and displays results inline
  - Added `POST /api/workflow/validate` endpoint (lightweight validation without diff computation)
  - JS-side debounce (400ms) auto-triggers on node edits, edge edits, metadata changes, and connection additions
  - Validation issue severity (error/warning/info) shown with color-coded badges
  - Canvas nodes highlighted with red border (error) or yellow border (warning)
  - When `is_valid: true` with warning/info issues, displays "Validation passed (with warnings)" alongside issues
- ✨ **D-2: Prompt versioning**: Introduced `_meta.version` metadata in prompt YAML files and `@version` suffix for `prompt_ref` version pinning
  - `prompt_ref: "prompts.yaml#greeting@v2"` syntax for version pinning (`file@version` also supported)
  - Version consistency checks: mismatch → warning, `_meta` missing with `@version` → warning, `_meta` present but unpinned → info
  - Added `prompt_version_validator` integrated into the validation pipeline
  - Added `yagra prompt info --file <path>` CLI command (displays `_meta` info and prompt keys, supports `--format json`)

### Changed
- 🔧 **P-0: `is_valid` now checks error severity only**: `WorkflowValidationReport.is_valid` changed from `not self.issues` to `not any(i.severity == "error" for i in self.issues)`. Warning/info-level issues no longer affect the valid/invalid determination of existing workflows

## [1.0.1] - 2026-02-22

### Added
- ✨ **Phase 5: Workflow regression testing — Golden Test (G-20, M-49–M-52)**: Added golden-case-based regression verification after workflow YAML changes. LLM nodes are replaced with mock responses, enabling deterministic, API-free validation of workflow structure correctness
  - **M-49 Domain model and persistence**: Defined `GoldenCase` / `NodeSnapshot` / `ComparisonStrategy` domain entities. `LocalGoldenCaseStore` persists cases as JSON under `.yagra/golden/`. `GoldenCaseManager` provides golden case generation from traces, save, list, and delete operations
  - **M-50 Test execution engine and comparison strategies**: `GoldenTestRunner` executes replay tests based on golden cases. LLM handlers are replaced with mock responses to verify execution path and node I/O regression. Supports comparison strategies: `exact`, `structural`, `skip`, `auto`
  - **M-51 `yagra golden` CLI commands**: Added `yagra golden save` (save golden case from trace), `yagra golden test` (run regression tests), `yagra golden list` (list cases)
    - Added repeatable `--strategy node_id:strategy` to `yagra golden save`. Per-node comparison strategy overrides (`exact` / `structural` / `skip` / `auto`) can now be persisted at save time. Invalid format, unknown strategy names, and duplicate `node_id` entries are rejected with clear CLI errors
  - **M-52 MCP tool `run_golden_tests`**: Added `run_golden_tests` to the MCP server. The `propose_update → run_golden_tests → apply_update` optimization cycle is now fully available via MCP
- ✨ **Added `Yagra.get_last_trace()` public API (Issue #28)**: The most recent `invoke()` trace is now available as `WorkflowRunTrace | None` when `observability=True`. In-memory trace capture runs for every `invoke()` even with `trace=False`; `trace=True` now controls JSON persistence only
  - Added `TraceCollector.reset()` and removed private `yagra._trace_collector` access from golden runner/integration tests, unified to `get_last_trace()`
- ✨ **M-48: Optimization cycle documentation and samples (G-19, G19-I02, G19-I03)**: Added a tutorial that enables users to complete the full Build → Run → Analyze → Update cycle within 30 minutes
  - New `docs/sphinx/source/user_guide/optimization_cycle.md` (G19-I02): covers Overview, Prerequisites, step-by-step guide (Build / Run & Observe / Analyze / Propose & Review / Regression Test / Apply or Rollback), and a worked example improving a translation workflow end-to-end
  - Added "Autonomous Optimization Cycle" section to `docs/agent-integration-guide.md` (G19-I03): includes system prompt template, MCP tool call sequence, handling for missing traces / golden cases, and a full E2E example from the agent's perspective

### Fixed
- 🐛 **Golden Test: resolved same-handler-name collisions with per-node mock dispatch**: When multiple LLM nodes shared the same handler name (e.g., two nodes with `handler: "llm"`), replay could return the wrong mock response. Golden replay now resolves handlers per node via `resolve_for_node(name, node_id)`
  - `build_state_graph()` now resolves handlers with `registry.resolve_for_node(node.handler, node.id)`
  - Golden replay registry stores LLM mocks as `node_id -> handler`, so each node returns its own recorded `output_snapshot`
  - Added a regression test for same-handler-name multi-node replay in `tests/unit/application/test_golden_test_runner.py`

### v1.0.1 Goals Achieved
- ✅ G-20: Golden-case-based regression verification available after workflow YAML changes
- ✅ G-19 (M-48): Optimization cycle documentation and samples ready; users can complete the first cycle within 30 minutes

## [1.0.0] - 2026-02-21

### Added
- ✨ **Phase 4: Approve & Update cycle (G-18, G-19, M-45–M-47)**: Enables safe YAML updates based on agent improvement proposals, completing the full Build → Run & Observe → Analyze & Propose → Approve & Update optimization cycle in a local environment
  - `propose_update` MCP tool: returns diff and validation result for agent-generated candidate YAML
  - `apply_update` MCP tool: applies candidate YAML with backup support (via `save_workflow_with_backup`)
  - `rollback_update` MCP tool: restores a previous version by `backup_id`
  - `WorkflowEditSession`: unified session class for diff generation, validation, and patch application
  - `WorkflowFormModel` / `WorkflowFormPatcher`: structured model and patcher for UI-driven form-based editing
  - `WorkflowValidationReporter`: outputs validation results as actionable reports with fix suggestions
  - Full E2E integration test covering the complete Build → Observe → Analyze → Update cycle

### Fixed
- 🔧 **asyncio event loop conflict resolved**: `test_mcp_installed_runs_asyncio` was conflicting with pytest-anyio's event loop when run in the full suite. Fixed by running `asyncio.run()` in a separate thread via `ThreadPoolExecutor`

### Changed
- 📈 **Test coverage improved from 91% to 96%**: All targeted modules now reach 95%+ coverage. `workflow_explainer`, `workflow_form_model`, `workflow_persistence`, `workflow_edit_session`, `edge_rule_validator`, `reference_resolver`, `local_trace_sink`, `workflow_file_store`, `structured_llm_handler`, `template_initializer`, and `workflow_validation_reporter` all reach 100%. Total: 760 tests passing

### v1.0.0 Goals Achieved
- ✅ G-14: Structured per-node logs automatically output during workflow execution
- ✅ G-15: Token consumption and LLM costs tracked in execution logs
- ✅ G-16: Coding agents can retrieve and analyze execution logs via MCP
- ✅ G-17: Aggregate multiple run results to understand quality trends
- ✅ G-18: Safely update YAML based on agent improvement proposals
- ✅ G-19: Complete Build→Observe→Analyze→Update optimization cycle runs locally end-to-end

## [0.6.11] - 2026-02-20

### Fixed
- 🔧 **CI: Chromium not installed for Playwright tests**: Added `playwright install chromium --with-deps` step to the `quality` CI job so Chromium is always available when running browser-based JS utility tests.
- 🔧 **CI: pytest-playwright event loop conflicts with `asyncio.run()` tests**: pytest-playwright holds a session-scoped event loop, causing `asyncio.run() cannot be called from a running event loop` in the existing `test_mcp_installed_runs_asyncio` test when run in the same process. Fixed by splitting Playwright tests into a separate `pytest` invocation.

## [0.6.10] - 2026-02-20

### Fixed
- 🐛 **Studio: `workspacePathToPromptRefPath` did not relativize paths outside the workflow directory**: When converting a workspace-root-relative path to a workflow-relative `prompt_ref`, paths in sibling directories or at the workspace root were returned as-is instead of being prefixed with `../`. Fixed by always using the `relativePosixPath` result regardless of `../` presence.

### Added
- ✅ **Studio: pytest-playwright tests for JS path-utility functions**: 32 integration test cases covering all 7 utility functions (`promptRefPathToWorkspacePath`, `workspacePathToPromptRefPath`, `getWorkflowDirectoryRelative`, etc.) executed in real Chromium. Covers subdirectory layouts, root-level workflows, `../` escaping, and round-trips.

## [0.6.9] - 2026-02-20

### Fixed
- 🐛 **Studio: "prompt yaml" dropdown appears empty for workflows in subdirectories**: When a workflow lives in a subdirectory of the workspace root (e.g. `bdi_workflow/`), the `prompt_ref` relative path (`prompts/bdi_prompts.yaml`) was not being resolved to its workspace-root-relative form (`bdi_workflow/prompts/bdi_prompts.yaml`), so no option in `yamlFiles` matched and the dropdown looked empty. Fixed `promptRefPathToWorkspacePath` to resolve bare relative paths against the workflow directory, not returning them as-is.
- 🐛 **Studio: selecting a YAML file from the dropdown saved a workspace-root-relative `prompt_ref` instead of workflow-relative**: `workspacePathToPromptRefPath` was returning the workspace-root-relative path unchanged. Fixed to compute a path relative to the workflow file's directory so the stored `prompt_ref` stays portable.

## [0.6.8] - 2026-02-20

### Fixed
- 🐛 **Studio: `prompt_ref` resolves to wrong path when `bundle_root` is not specified**: `create_workflow_studio_server` was overwriting `bundle_root_path` with `workspace_root_path` when `bundle_root=None`, causing relative paths like `prompts/bdi_prompts.yaml` to resolve against the workspace root instead of the workflow's parent directory. Fixed by keeping `bundle_root_path` as `None` and letting the workflow loader use the correct default.
- 🐛 **Studio: `build_workflow_catalog_preview` called twice per form request**: `build_workflow_form_view` was calling `build_workflow_catalog_preview` internally, while `get_form()` also called it explicitly. Removed the redundant inner call and fixed `prompt_catalog_keys=()` to eliminate the double work.

### Changed
- ⚡ **Studio: faster workflow list on "Select Workflow"**: Replaced `rglob("*")` (which traversed tens of thousands of files including `.venv/`) with an `os.scandir`-based recursive walk that prunes excluded directories (`.venv`, `node_modules`, `__pycache__`, etc.) early. Significantly reduces scan time for large repositories.

## [0.6.7] - 2026-02-20

### Fixed
- 🐛 **Studio: prompt not shown when `prompt_ref` resolution fails**: `build_workflow_form_view` now falls back to per-node `prompt_ref` loading when the whole-workflow `resolve_workflow_references` call raises. A single broken node no longer prevents prompt content from appearing in other nodes.
- 🐛 **`explain_workflow`: `variable_flow.inputs` silently empty without `base_dir`**: When `workflow_dir` is `None` (MCP call without `base_dir`), `prompt_ref` files cannot be read and variable extraction is skipped. The response now includes a `warnings` list with a `prompt_ref_unresolved` entry for each affected node, making the limitation visible rather than silent.

### Added
- ✨ **MCP: new `get_template` tool**: Returns the full file contents of a named template (e.g. `workflow.yaml`, `prompts/*.yaml`) as a `files` dict. Use `list_templates` to discover available names, then `get_template` to inspect the YAML structure — enables workflow creation via MCP without external documentation.

## [0.6.6] - 2026-02-20

### Fixed
- 🐛 **`explain_workflow`: correctly extract variables from `prompt_ref` nodes**: After `resolve_workflow_references` runs, `prompt_ref` is replaced by a resolved dict (`{system, user}`). The dict branch in `_extract_input_variables` previously only looked at the `content` key and always returned an empty list. It now calls `_extract_vars_from_value` for full recursive traversal, so `variable_flow` in `explain_workflow` correctly reports input variables for `prompt_ref` nodes.

### Added
- ✨ **MCP: `base_dir` TIP in `validate_workflow` / `explain_workflow` descriptions**: Tool descriptions now include a hint to pass `base_dir` (the directory containing the workflow YAML) so that relative `prompt_ref` paths are resolved correctly.
- ✨ **MCP: `list_handlers` now includes a `custom_handler_guide`**: Returns the handler signature convention, routing rules (`__next__`), and a code example — allowing agents to implement custom handlers without external documentation.
- ✨ **Validation: condition label hint for `llm` conditional branch sources**: When an `llm` handler node is the source of conditional edges, validation now emits a `severity: info` issue listing the exact labels the LLM must output. `EdgeRuleIssue` gains a `severity` field (`error` / `warning` / `info`), which is propagated through `WorkflowValidationIssue`.

## [0.6.5] - 2026-02-19

### Fixed
- 🐛 **Studio: always show Prompt Settings for custom handler nodes**: Fixed a bug where the Prompt Settings section was not displayed when a custom handler was selected
  - Root cause: `showPromptFields` computed was missing from the `setup()` return object, causing the template to always evaluate it as `undefined` (falsy)
  - Removed the "use prompt (optional)" checkbox; Prompt Settings are now always visible for custom handler nodes, consistent with LLM handler nodes

### Changed
- 📝 **Documentation updates**:
  - `prompt_model.md`: added explanation of automatic state variable injection in `system` prompts (feature introduced in v0.6.4)
  - `prompt_model.md`: added section on using prompts with custom handler nodes, including example handler code
  - `prompt_model.md`: updated Studio Integration section to reflect that Prompt Settings are shown for custom handler nodes
  - `prompt_model.md`: corrected manual `.format()` example (not needed with built-in handlers)

## [0.6.4] - 2026-02-19

### Added
- ✨ **State variable injection in `system` prompts**: LLM handlers (`llm` / `streaming_llm` / `structured_llm`) now support `{variable}` substitution in `system` prompts using state values
  - Auto-detection mode (no `input_keys`): extracts `{variable}` patterns from both `system` and `user` templates, deduplicates, and expands both
  - Explicit mode (`input_keys` specified): applies the specified keys to both `system` and `user` prompts (backward compatible)
  - `prompt_variable_validator` also validates variables in `system` prompts (backward compatible)

## [0.6.3] - 2026-02-19

### Added
- ✨ **State Reducer / MessagesState support**: Added `reducer: add` and `type: messages` to `state_schema` fields
  - `reducer: "add"` resolves to `Annotated[list, operator.add]`, enabling fan-in aggregation from parallel nodes
  - `type: messages` activates LangGraph's `add_messages` reducer for append-mode chat history
  - New `chat` template (simple chatbot using MessagesState)
- ✨ **Send API / Parallel Fan-Out support**: Map-reduce patterns via `fan_out` edges in YAML
  - `fan_out: {items_key, item_key}` dispatches items in parallel via LangGraph's Send API
  - `fan_out` and `condition` are mutually exclusive (Pydantic validation enforced)
  - New `parallel` template (prepare → parallel process → aggregate map-reduce pattern)
- ✨ **SubGraph support**: Nest another workflow YAML as a subgraph via `handler: "subgraph"` nodes
  - `params.workflow_ref` (relative path) triggers recursive build inside `build_state_graph`
  - Shares the parent's registry and checkpointer
  - New `subgraph` template (main_step → sub_agent → finalize pattern)
- ✨ **edge_rule_validator fan_out support**: `fan_out` edges are treated as an independent category; mixing with regular/conditional edges is now correctly caught at YAML validation time
- ✨ **Studio `state_schema` editor**: Added a `state_schema` table editor to the Workflow Settings panel in Yagra Studio
  - Edit field name, type, and reducer in a table UI
  - `+ Add Field` / `✕` buttons for adding and removing rows
  - Auto-converts to YAML `state_schema` on save; restores from existing YAML on load
  - `fan_out` edges and `subgraph` nodes still require direct YAML editing (not supported in Studio)
- 📝 **Documentation updates**:
  - `workflow_yaml.md`: Added `state_schema`, `fan_out`, and subgraph node documentation
  - `templates.md`: Added `parallel`, `subgraph`, and `chat` template documentation
  - `cli_reference.md`: Added Workflow Settings panel and `state_schema` setup instructions to the Studio section

## [0.6.2] - 2026-02-19

### Changed
- 📝 **Documentation and implementation alignment fixes**: Corrected documentation gaps where implemented features were not reflected in docs
  - Updated `README.md` template list from 3 to 6 templates (added `tool-use`, `multi-agent`, `human-review`)
  - Added `explain`, `handlers`, `mcp` command documentation to `docs/sphinx/source/cli_reference.md`
  - Added `tool-use`, `multi-agent`, `human-review` template descriptions to `docs/sphinx/source/user_guide/templates.md`
  - Fixed Japanese output samples in `docs/sphinx/source/getting_started.md` to English

## [0.6.1] - 2026-02-18

### Fixed
- **MCP server crash on startup**: `yagra mcp` raised `AttributeError: 'NoneType' object has no attribute 'tools_changed'` on startup
  - `run_mcp_server()` was passing `notification_options=None` to `server.get_capabilities()`, causing a null-pointer equivalent error inside the mcp SDK
  - Fixed by importing and passing a `NotificationOptions()` instance (`from mcp.server.lowlevel.server import NotificationOptions`)

## [0.6.0] - 2026-02-19

### Added
- 🤖 **G-11: Agent-Friendly Workflow Generation (M-28–M-34)**: Coding agents can now autonomously generate and fix Yagra workflows with high accuracy
  - **M-28 Schema semantic metadata**: All fields in `GraphSpec` / `NodeSpec` / `EdgeSpec` now have `description` and `examples`. `yagra schema` output includes field intent, usage, and value examples — agents can understand the spec from schema alone
  - **M-29 Validation fix suggestions**: `WorkflowValidationIssue` now includes `severity` (`error` / `warning` / `info`) and `context` (`actual_value` / `available_values` / `suggestion`). Fuzzy matching surfaces typo corrections for node IDs
  - **M-30 `explain` command**: `yagra explain --workflow <path> --format json` — static analysis outputs `entry_point`, `exit_points`, `execution_paths`, `required_handlers`, and `variable_flow`
  - **M-31 stdin support**: `yagra validate --workflow -` and `yagra explain --workflow -` now accept YAML from stdin — no temp files needed
  - **M-32 `handlers` command + PARAMS_SCHEMA**: `yagra handlers --format json` outputs the params JSON Schema for each built-in handler. Each handler module now exports a `*_PARAMS_SCHEMA` constant
  - **M-33 Agent integration guide**: `docs/agent-integration-guide.md` — worked example of generate→validate→fix loop, system prompt template, and MCP server integration instructions
  - **M-34 MCP server**: MCP server via the official `mcp` Python SDK (Anthropic). Launch with `yagra mcp`. Exposes 4 tools: `validate_workflow`, `explain_workflow`, `list_templates`, `list_handlers`. Install with `pip install "yagra[mcp]"`

### Related
- **Goal**: G-11 (Coding agents can autonomously generate and fix Yagra workflows with high accuracy)
- **Milestones**: M-28, M-29, M-30, M-31, M-32, M-33, M-34

## [0.5.5] - 2026-02-18

### Added
- **Dynamic schema generation (M-27)**: `structured_llm` nodes can now generate Pydantic models at runtime from `schema_yaml` defined in the workflow YAML or entered in the WebUI Schema Settings — no Python code required for structured output
  - New `schema_builder.py` module: converts flat `key: type` YAML (e.g. `name: str`, `age: int`) to a Pydantic `BaseModel` via a safe `TYPE_MAP` whitelist (no `eval()`)
  - Supported types: primitives (`str`, `int`, `float`, `bool`), collections (`list[str]` etc.), dicts (`dict[str, str]` etc.), Optional (`str | None` etc.)
  - `create_structured_llm_handler()` `schema` parameter is now optional. When `schema=None` (default), the handler resolves the schema at runtime from `params["schema_yaml"]`. Existing `schema=MyModel` usage is fully backward-compatible.
  - `build_model_from_schema_yaml()` is now exported as a public API from `yagra.handlers`
  - WebUI Schema Settings placeholder updated to flat format (`name: str` / `age: int` / `score: float`)
  - 32 new unit tests (`test_schema_builder.py` × 27, dynamic schema in `test_structured_llm_handler.py` × 5) and 3 new integration tests (`test_structured_llm_dynamic_schema.py`)

### Related
- **Goal**: G-07 (Reduce LLM node boilerplate and enable advanced output control)
- **Milestone**: M-27

## [0.5.4] - 2026-02-17

### Fixed
- **Conditional edge source nodes now automatically set `output_key` to `__next__`** — Without this, LLM output was stored under `state["output"]` instead of `state["__next__"]`, causing the conditional router to fail with a `GraphBuildError`
  - `_normalize_runtime_params()` now accepts `is_cond_source` flag
  - When `output_key` is not specified on a conditional edge source node, `output_key: __next__` is injected at runtime automatically
  - Explicit `output_key: __next__` in YAML is no longer required (explicit values still take precedence)

## [0.5.3] - 2026-02-17

### Removed
- **Prompt variable reachability validation (`prompt_variable_error`) removed** — The handler-name-based variable reachability check produced false positives on workflows with conditional edges; removed to restore flexibility
  - `collect_prompt_variable_issues()` / `PromptVariableIssue` deleted from `prompt_variable_validator`
  - `prompt_variable_error` code will no longer appear in `WorkflowValidationReport`
  - `_extract_required_vars()` / `_get_output_key()` utilities retained for badge display

## [0.5.2] - 2026-02-17

### Fixed
- **IN/OUT badge detection changed to parameter-based logic** — Replaced handler-name-based detection (`llm`/`structured_llm`/`streaming_llm`) with parameter-based detection for more accurate and flexible badge display
  - IN badge shown when `prompt` (dict) or `prompt_ref` (str) is present in node params
  - OUT badge shown only when `output_key` is explicitly specified (default `"output"` is no longer shown)
  - Conditional edge source nodes now show OUT `__next__` badge
  - Custom handler nodes with `prompt_ref` + `model` now correctly show IN badges
  - Nodes with both `prompt_ref` and conditional edge source (e.g. `evaluator`) now show IN + OUT `__next__` simultaneously
  - Node `outputVars` are now recalculated in real-time when edge conditions change

## [0.5.1] - 2026-02-17

### Fixed
- **Studio: IN badges not shown for `prompt_ref` nodes** — The `/api/workflow` endpoint returns unresolved `prompt_ref` strings, so variable extraction failed on the JS side. Added `prompt_user` field to `WorkflowNodeFormItem` to expose the server-resolved `prompt.user` text; `extractInputVars()` now falls back to `prompt_user` when `params.prompt.user` is absent.
- **IN badges were truncated after 3 items** — Removed the `+N` overflow badge and replaced with full `flex-wrap` display so all variables are shown within the node card width.

### Changed
- **Toolbar toggle labels unified to IN / OUT** — Renamed "入力変数" / "出力変数" to "IN" / "OUT" to match the badge labels on the graph nodes.

## [0.5.0] - 2026-02-17

### Added
- **G-10: Data flow variable badges on graph nodes** — Each LLM node in the Studio WebUI now shows input variable badges (blue, from `{variable}` in prompt templates) and an output variable badge (green, from `output_key`) directly on the graph node
  - IN badges (blue): extracted from prompt template `{variable}` placeholders; `input_keys` takes precedence if explicitly set
  - OUT badge (green): shows `output_key` (defaults to `"output"`)
  - Applies to `llm`, `structured_llm`, and `streaming_llm` handlers; custom handlers are excluded
  - Toolbar checkboxes to independently toggle IN/OUT badge visibility
  - Badges update immediately when `prompt` or `output_key` is changed in the node properties panel and applied
  - Read-Only visualization HTML (`yagra visualize`) also shows the same badges

### Related
- **Goal**: G-10 (Visualize each node's input and output variables on the WebUI graph at a glance)
- **Milestone**: M-24, M-25

## [0.4.8] - 2026-02-17

### Fixed
- **Studio UI: output_key / schema_yaml lost after reload** — Fixed a bug where `output_key` and `schema_yaml` were cleared in the node editor after saving a workflow and reloading. `buildNodesFromPayload` was not populating `data.params` from the loaded YAML node params, so the node editor watch could not read them.

### Related
- **Goal**: G-08 (Declarative control of LLM node data flow via YAML, configurable from WebUI)
- **Milestone**: M-20

## [0.4.7] - 2026-02-17

### Changed
- **Prompt variable validation: exclude start_at node**: The `start_at` (START-tagged) node is now fully excluded from prompt variable validation
  - Prevents false positives when the Studio UI has no `spec.params` editor — the start node receives external inputs at `invoke()` time which cannot be statically determined
- **Error messages in English**: `prompt_variable_error` messages are now consistently in English

### Related
- **Goal**: G-08 (Declarative control of LLM node data flow via YAML, configurable from WebUI)
- **Milestone**: M-20

## [0.4.6] - 2026-02-17

### Added
- **Prompt variable validation**: Static validation at save time that verifies all `{variable}` references in prompt templates are resolvable from upstream node `output_key` or declared `spec.params` initial keys
  - Applies to `llm`, `streaming_llm`, and `structured_llm` handlers (custom handlers are excluded)
  - Validates across ALL execution paths — if a conditional branch exists, the variable must be guaranteed on every path reaching the node (strict intersection)
  - When `input_keys` is explicitly set on a node, it takes precedence over template variable extraction
  - Skipped for cyclic graphs and workflows with structural errors (caught by earlier validators)
  - Error code: `"prompt_variable_error"`

### Related
- **Goal**: G-08 (Declarative control of LLM node data flow via YAML, configurable from WebUI)
- **Milestone**: M-20

## [0.4.5] - 2026-02-17

### Fixed
- **WebUI user prompt placeholder**: The user prompt textarea displayed `{{input}}` as placeholder text, causing users to write prompt templates with double-brace syntax which is not expanded by the handler's `str.format()` logic
  - Changed placeholder from `{{input}}` to `{input}` to match the single-brace `{variable}` convention
  - Fixed the same incorrect example in `docs/api/post-studio-file-read.md`

### Related
- **Goal**: G-08 (Declarative control of LLM node data flow via YAML, configurable from WebUI)
- **Milestone**: M-20

## [0.4.4] - 2026-02-17

### Fixed
- **WebUI output_key save bug**: Fixed an issue where `output_key` set via the UI was not persisted to YAML on Save
  - `buildWorkflowPayload` was only reading from `node.data.rawNode.params`, ignoring the updated `node.data.params` written by `applyNodeEdit`
  - Now merges `node.data.params` (latest edited values) over `rawNode.params` before building the save payload
  - `schema_yaml` (structured_llm nodes) is also now correctly persisted

### Related
- **Goal**: G-08 (Declarative control of LLM node data flow via YAML, configurable from WebUI)
- **Milestone**: M-20

## [0.4.3] - 2026-02-17

### Added
- **WebUI output_key setting**: Added Output Settings section to the Node Properties panel
  - LLM handler nodes can now set `output_key` via text input
  - Blank input falls back to the default (`"output"` key)
  - On Apply, writes to `params.output_key` — WebUI and YAML are fully in sync

### Fixed
- **WebUI prompt yaml dropdown**: Excluded YAML files under dot-directories (`.github`, `.venv`, `.yagra`, etc.) and tool directories (`node_modules`, `dist`, etc.) — only project-relevant files are listed
- **WebUI file candidates**: Removed hardcoded exclusion of `src/` and `tests/` to restore full flexibility in user directory naming
- **WebUI labels/hints**: Renamed `prompt_ref (auto)` label to `prompt reference`; unified all hint texts to English

### Related
- **Goal**: G-08 (Declarative control of LLM node data flow via YAML, configurable from WebUI)
- **Milestone**: M-20

## [0.4.2] - 2026-02-17

### Changed
- **Auto-detect prompt variables**: `input_keys` parameter is no longer required
  - Template variables (`{variable_name}`) are automatically extracted from the prompt template using `re.findall` and fetched from state
  - All built-in handlers (`llm`, `structured_llm`, `streaming_llm`) support auto-detection
  - Fully backward compatible: existing YAML with explicit `input_keys` continues to work (`None` vs `[]` distinction preserved)
- **Testing**: Added 5 unit tests for auto-detection behavior

### Related
- **Goal**: G-08 (Declarative control of LLM node data flow via YAML)
- **Milestone**: M-19

## [0.4.1] - 2026-02-17

### Added
- **WebUI Handler Type Selector**: Handler input in Node Properties panel changed to a type selector (`llm` / `structured_llm` / `streaming_llm` / `custom`)
  - Predefined types auto-fill the handler name — no manual typing required
  - `custom` type shows free-text input for user-defined handlers
  - Fully backward compatible (existing YAML load/save behavior unchanged)

### Related
- **Goal**: G-05 (Non-engineers can operate workflows in WebUI without confusion)

## [0.4.0] - 2026-02-17

### Added
- **WebUI Handler Type Forms**: Node properties panel shows handler type-specific form sections
  - Prompt Settings / Model Settings only shown for `llm`, `structured_llm`, and `streaming_llm` handlers
  - **Schema Settings** section added for `structured_llm` (edit `schema_yaml` as YAML text)
  - **Streaming Settings** section added for `streaming_llm` (`stream: false` checkbox)
  - LLM-related sections hidden for `custom` and non-LLM handlers
- **Streaming Handler**: Added `create_streaming_llm_handler()` factory function for streaming LLM responses
  - Returns `Generator[str, None, None]` — supports both incremental and buffered processing
  - Automatically adds `stream=True` (respects explicit `stream=False` in `model.kwargs`)
  - Same retry and timeout features as `create_llm_handler()` (default timeout=60s)
  - Fully backward compatible
- **Structured Output Handler**: Added `create_structured_llm_handler()` factory function for type-safe structured output using Pydantic models
  - Specify a Pydantic model as the `schema` argument to automatically parse and validate LLM responses
  - JSON output mode enabled by default (`response_format=json_object`)
  - JSON Schema automatically injected into the system prompt
  - Same retry and timeout features as `create_llm_handler()`
  - Raises `LLMHandlerCallError` on JSON parse failure or Pydantic validation failure
  - Fully backward compatible
- **Testing**: Added 40 tests total (15+16 unit tests, 3+3 integration tests for M-14–M-16)
- **Examples**: Added `examples/llm-streaming/` with a working example (YAML + prompts + run script + README)
- **Examples**: Added `examples/llm-structured/` with a working example (YAML + prompts + run script + README)
- **Examples**: Added `examples/llm-basic/` with a working example for the basic LLM handler

### Related
- **Goal**: G-07 (DX improvement: reduce LLM node boilerplate)
- **Milestone**: M-16 (streaming handler), M-15 (structured output handler), M-14 (basic LLM handler samples)

## [0.3.1] - 2026-02-17

### Changed
- **Docstring Internationalization**: Translated all Python docstrings from Japanese to English
  - Maintained Google style docstring format
  - Ensured consistency with type hints and implementation
  - Improved Sphinx documentation accessibility for English-speaking users
  - Enhanced API documentation for international user base

## [0.3.0] - 2026-02-17

### Added
- **LLM Handler Utilities**: Added `create_llm_handler()` factory function to reduce LLM node boilerplate
  - Support for 100+ LLM providers via litellm (OpenAI, Anthropic, Google, Azure, etc.)
  - Prompt variable interpolation (`{variable}` syntax)
  - Automatic retry and timeout handling
  - Provided as extras dependency (`pip install 'yagra[llm]'` or `uv add --optional llm yagra`)
  - Fully backward compatible (no impact on existing code)
- **Testing**: Added 7 core tests (all 91 existing tests passing)
- **New Module**: `src/yagra/handlers/`
- **Dependencies**: `litellm>=1.57.10` (extras dependency)

### Changed
- Type safety: mypy strict mode compliance
- Code quality: ruff format and lint compliance

### Known Issues
- Issue #11: 6 exception tests temporarily skipped (core functionality works normally)

### Related
- **PR**: #10
- **Goal**: G-07 (DX improvement: reduce LLM node boilerplate)
- **Milestone**: M-14

## [0.2.0] - 2026-02-17

### Added
- Comprehensive English documentation for README and Sphinx (11 pages: Getting Started, User Guide, CLI Reference, Examples, etc.)
- CONTRIBUTING.md for development guidelines
- Multilingual documentation support via Sphinx i18n (English primary, Japanese secondary)
- POT/PO file generation and Japanese translation environment

### Changed
- Switched README.md from Japanese to English as the primary language
- Optimized documentation structure (README = landing page, Sphinx = detailed docs)
- Aligned with Pydantic/Click best practices

## [0.1.9] - 2026-02-16

### Fixed
- Fixed `prompt_ref` resolution failure when `bundle_root` was not specified in library usage; now searches parent directories to resolve `prompts/...` paths.

## [0.1.8] - 2026-02-16

### Changed
- Switched Studio frontend dependencies (Vue / Vue Flow) from CDN to bundled local assets, enabling offline usage.
- Changed `yagra visualize` output HTML to bundle Mermaid locally for offline rendering.

### Fixed
- Fixed Studio `prompt yaml` dropdown resetting selection unexpectedly during candidate reload; Node Properties now preserves selection state.
- Prevented race condition in `loadStudioFiles()` where stale responses could overwrite newer state.

## [0.1.7] - 2026-02-15

### Fixed
- Unified Studio `prompt_ref` path resolution to workspace root basis, fixing incorrect resolution of `prompts/...` as `workflows/prompts/...`.
- When `bundle_root` is not specified with `studio --workflow`, workspace root is now used as default, aligning save/load and runtime reference resolution.

## [0.1.6] - 2026-02-15

### Changed
- Changed Studio `prompt yaml` auto-generation target from workflow sibling directory to `prompts/` under workspace root (project root).
- Adjusted `studio --workflow` default `workspace_root` to prefer project root (current directory) when workflow is under the current directory.

## [0.1.5] - 2026-02-14

### Fixed
- Fixed JavaScript syntax error during Studio Launcher initialization that prevented `Open Existing Workflow` list from displaying.
- Added regression tests for backslash normalization logic in HTML responses.

## [0.1.4] - 2026-02-14

### Fixed
- Fixed `prompt_ref` saving workspace-relative paths instead of workflow-relative paths when editing workflows in subdirectories via Studio.
  - Save: Normalize `prompt_ref` to workflow-relative path.
  - Load: Convert workflow-relative `prompt_ref` to workspace-relative for Studio file API compatibility.

## [0.1.3] - 2026-02-14

### Added
- Added `prompt_entries` to `POST /api/studio/file/read` to reflect prompt content directly in Node Properties.
- Added `prompt key` input to Node Properties, enabling `prompt_ref=<path>#<key>` creation from the UI.

### Changed
- Fully removed `model_ref`; unified model configuration to inline `nodes[].params.model` definitions.
- Consolidated Studio prompt workflow into Node Properties; removed `Workflow Settings.prompt_catalog` and `Prompt File` sections.
- Unified `prompt_ref` resolution to path-based (`<path>` / `<path>#<key>`).
- Changed prompt YAML auto-generation target from workspace root to `prompts/` under the workflow YAML directory.

## [0.1.2] - 2026-02-14

### Added
- Added Workflow Studio launcher flow (existing workflow selection / new workflow creation).
- Added save-time backup and rollback safety for Studio initial operations.
- Added edge connection port (source/target handle) persistence.

### Changed
- Redesigned Studio Node Properties as dedicated forms for editing `system prompt` / `user prompt` and model settings.
- Organized `prompt_ref` / `model_ref` catalog reference flow and Studio API documentation.
- Updated validation to allow `edges: []` for single-node workflows.
- Improved Studio inbound port separation and quickstart/API documentation.

### Fixed
- Added runtime parameter normalization for `prompt_ref` / `model_ref` usage, unifying ref/inline input runtime representations.

## [0.1.1] - 2026-02-14

### Changed
- Renamed package and import name from `graphyml` to `yagra`; unified public API primary name to `Yagra`.
- Added tag name (`vX.Y.Z`) and `pyproject.toml` version consistency check to publish workflow.

## [0.1.0] - 2026-02-13

### Added
- Implemented Yagra YAML schema (Pydantic) and validation logic.
- Implemented Registry pattern (port + in-memory adapter).
- Implemented builder to construct LangGraph StateGraph from workflow YAML.
- Added `Yagra.from_workflow(...)` / `invoke(...)` public API.
- Added example YAMLs with branching, loops, and split references in `examples/`.
- Set up quality gates (ruff/mypy/pytest, pre-commit/pre-push).

### Changed
- Added Zero-Boilerplate usage examples and sample navigation to README.
- Updated `docs/product/*` goals, milestones, and progress.

## Links

- [PyPI](https://pypi.org/project/yagra/)
- [GitHub Repository](https://github.com/shogo-hs/Yagra)
- [GitHub Releases](https://github.com/shogo-hs/Yagra/releases)
