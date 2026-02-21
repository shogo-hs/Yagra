"""Yagra MCP server. Provides validate / explain / list_templates / list_handlers as MCP tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# These imports are lifted to the module level so that tests can monkeypatch them.
try:
    from yagra.application.services.workflow_file_store import WorkflowBackupNotFoundError
    from yagra.application.use_cases.workflow_persistence import (
        WorkflowRevisionConflictError,
        WorkflowValidationFailedError,
        rollback_workflow_from_backup,
        save_workflow_with_backup,
    )
except Exception:  # pragma: no cover – isolated import guard
    pass


def create_mcp_server() -> Any:
    """Creates and returns the Yagra MCP server.

    Raises ImportError if the mcp library is not installed.

    Returns:
        A configured mcp.server.Server instance.

    Raises:
        ImportError: If the mcp library is not installed.
    """
    try:
        import mcp.server.stdio  # noqa: F401
        from mcp.server import Server
        from mcp.types import TextContent, Tool
    except ImportError as exc:
        raise ImportError(
            "The mcp package is required to use the MCP server.\n"
            "Install it with 'uv add yagra[mcp]' or 'pip install yagra[mcp]'."
        ) from exc

    server = Server("yagra")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Returns the list of available MCP tools."""
        return [
            Tool(
                name="validate_workflow",
                description=(
                    "Validates a Yagra workflow YAML and returns the validation result as JSON. "
                    "When is_valid is false, issues contain fix suggestions (context.suggestion). "
                    "TIP: pass base_dir (the directory containing your workflow YAML) "
                    "to resolve relative prompt_ref paths correctly."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "yaml_content": {
                            "type": "string",
                            "description": "The Yagra workflow YAML string to validate",
                        },
                        "base_dir": {
                            "type": "string",
                            "description": (
                                "Base directory for resolving relative paths in prompt_ref "
                                "and other file references. Use the directory containing "
                                "your workflow YAML file."
                            ),
                        },
                    },
                    "required": ["yaml_content"],
                },
            ),
            Tool(
                name="explain_workflow",
                description=(
                    "Statically analyzes a Yagra workflow YAML and returns execution paths, "
                    "required handlers, and variable flow as JSON. "
                    "Use this to understand the workflow structure before running it. "
                    "TIP: pass base_dir (the directory containing your workflow YAML) "
                    "to resolve relative prompt_ref paths correctly."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "yaml_content": {
                            "type": "string",
                            "description": "The Yagra workflow YAML string to analyze",
                        },
                        "base_dir": {
                            "type": "string",
                            "description": (
                                "Base directory for resolving relative paths in prompt_ref "
                                "and other file references. Use the directory containing "
                                "your workflow YAML file."
                            ),
                        },
                    },
                    "required": ["yaml_content"],
                },
            ),
            Tool(
                name="validate_workflow_file",
                description=(
                    "Validates a Yagra workflow YAML file by path. "
                    "More convenient than yaml_content when the file is accessible. "
                    "Automatically resolves prompt_ref relative paths using the file's directory."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_path": {
                            "type": "string",
                            "description": "Absolute or CWD-relative path to the workflow YAML file.",
                        },
                    },
                    "required": ["workflow_path"],
                },
            ),
            Tool(
                name="explain_workflow_file",
                description=(
                    "Statically analyzes a Yagra workflow YAML file by path and returns "
                    "execution paths, required handlers, and variable flow as JSON. "
                    "More convenient than yaml_content when the file is accessible. "
                    "Automatically resolves prompt_ref relative paths using the file's directory."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_path": {
                            "type": "string",
                            "description": "Absolute or CWD-relative path to the workflow YAML file.",
                        },
                    },
                    "required": ["workflow_path"],
                },
            ),
            Tool(
                name="list_templates",
                description="Returns the list of available Yagra workflow template names.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="list_handlers",
                description=(
                    "Returns the list of Yagra built-in handlers and their params schemas. "
                    "Use this to check which keys can be specified in the params field of workflow YAML."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_template",
                description=(
                    "Returns the file contents of a Yagra workflow template. "
                    "Use list_templates first to see available template names. "
                    "Returns a 'files' dict mapping relative paths to file contents "
                    "(e.g. 'workflow.yaml', 'prompts/my_prompts.yaml'). "
                    "Useful for understanding the structure of a template before initializing it."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Template name (from list_templates)",
                        }
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="propose_update",
                description=(
                    "Receive a candidate YAML proposed by the agent and return the diff "
                    "against the current workflow file together with the validation result. "
                    "Use this to preview changes before applying them."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_path": {
                            "type": "string",
                            "description": "Path to the existing workflow YAML file",
                        },
                        "candidate_yaml": {
                            "type": "string",
                            "description": "Proposed YAML content to apply",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for the proposed change",
                        },
                    },
                    "required": ["workflow_path", "candidate_yaml"],
                },
            ),
            Tool(
                name="apply_update",
                description=(
                    "Validate the candidate YAML and apply it to the workflow file with a backup. "
                    "Returns backup_id which can be used to rollback if needed."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_path": {
                            "type": "string",
                            "description": "Path to the workflow YAML file to update",
                        },
                        "candidate_yaml": {
                            "type": "string",
                            "description": "New YAML content to apply",
                        },
                        "base_revision": {
                            "type": "string",
                            "description": (
                                "Expected current revision (for conflict detection). "
                                "Omit to skip conflict check."
                            ),
                        },
                        "backup_dir": {
                            "type": "string",
                            "description": "Directory for backups (default: .yagra/backups)",
                        },
                    },
                    "required": ["workflow_path", "candidate_yaml"],
                },
            ),
            Tool(
                name="rollback_update",
                description=(
                    "Restore the workflow file to a previous version identified by backup_id. "
                    "The current state is saved as a safety backup before rolling back."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_path": {
                            "type": "string",
                            "description": "Path to the workflow YAML file to rollback",
                        },
                        "backup_id": {
                            "type": "string",
                            "description": "Backup ID to restore from",
                        },
                        "backup_dir": {
                            "type": "string",
                            "description": "Directory for backups (default: .yagra/backups)",
                        },
                    },
                    "required": ["workflow_path", "backup_id"],
                },
            ),
            Tool(
                name="get_traces",
                description=(
                    "Retrieve raw execution trace data from local trace files. "
                    "Returns structured JSON traces with per-node execution details, "
                    "timing, token usage, and errors."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trace_dir": {
                            "type": "string",
                            "description": ("Root trace directory. Defaults to '.yagra/traces'."),
                        },
                        "workflow_name": {
                            "type": "string",
                            "description": "Filter by workflow name.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": ("Maximum number of traces to return. Defaults to 20."),
                        },
                    },
                },
            ),
            Tool(
                name="analyze_traces",
                description=(
                    "Aggregate multiple execution traces and return statistical summary. "
                    "Provides per-node success rates, latency percentiles, "
                    "token consumption, and cost statistics."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trace_dir": {
                            "type": "string",
                            "description": ("Root trace directory. Defaults to '.yagra/traces'."),
                        },
                        "workflow_name": {
                            "type": "string",
                            "description": "Filter by workflow name.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Limit traces to aggregate.",
                        },
                    },
                },
            ),
            Tool(
                name="run_golden_tests",
                description=(
                    "Run golden test cases against a workflow to verify regression. "
                    "Replays saved golden cases with LLM handlers mocked by recorded outputs, "
                    "then compares execution paths and node snapshots. "
                    "Use after propose_update to verify changes don't break existing behavior."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_path": {
                            "type": "string",
                            "description": "Path to the workflow YAML file to test against.",
                        },
                        "golden_dir": {
                            "type": "string",
                            "description": (
                                "Directory containing golden case files. "
                                "Defaults to '.yagra/golden/'."
                            ),
                        },
                        "case_name": {
                            "type": "string",
                            "description": (
                                "Specific golden case name to run. "
                                "If omitted, runs all cases for the workflow."
                            ),
                        },
                        "format": {
                            "type": "string",
                            "enum": ["json", "summary"],
                            "description": (
                                "Output format: 'json' for full structured results, "
                                "'summary' for a concise human-readable summary. "
                                "Defaults to 'json'."
                            ),
                        },
                    },
                    "required": ["workflow_path"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Executes an MCP tool.

        Args:
            name: Name of the tool to execute.
            arguments: Argument dictionary for the tool.

        Returns:
            List of TextContent containing the tool execution result.
        """
        if name == "validate_workflow":
            result = _tool_validate_workflow(
                yaml_content=arguments.get("yaml_content", ""),
                base_dir=arguments.get("base_dir"),
            )
        elif name == "explain_workflow":
            result = _tool_explain_workflow(
                yaml_content=arguments.get("yaml_content", ""),
                base_dir=arguments.get("base_dir"),
            )
        elif name == "validate_workflow_file":
            result = _tool_validate_workflow_file(arguments.get("workflow_path", ""))
        elif name == "explain_workflow_file":
            result = _tool_explain_workflow_file(arguments.get("workflow_path", ""))
        elif name == "list_templates":
            result = _tool_list_templates()
        elif name == "list_handlers":
            result = _tool_list_handlers()
        elif name == "get_template":
            result = _tool_get_template(arguments.get("name", ""))
        elif name == "propose_update":
            result = _tool_propose_update(
                workflow_path=arguments.get("workflow_path", ""),
                candidate_yaml=arguments.get("candidate_yaml", ""),
                reason=arguments.get("reason"),
            )
        elif name == "apply_update":
            result = _tool_apply_update(
                workflow_path=arguments.get("workflow_path", ""),
                candidate_yaml=arguments.get("candidate_yaml", ""),
                base_revision=arguments.get("base_revision"),
                backup_dir=arguments.get("backup_dir", ".yagra/backups"),
            )
        elif name == "rollback_update":
            result = _tool_rollback_update(
                workflow_path=arguments.get("workflow_path", ""),
                backup_id=arguments.get("backup_id", ""),
                backup_dir=arguments.get("backup_dir", ".yagra/backups"),
            )
        elif name == "get_traces":
            result = _tool_get_traces(
                trace_dir=arguments.get("trace_dir", ".yagra/traces"),
                workflow_name=arguments.get("workflow_name"),
                limit=arguments.get("limit", 20),
            )
        elif name == "analyze_traces":
            result = _tool_analyze_traces(
                trace_dir=arguments.get("trace_dir", ".yagra/traces"),
                workflow_name=arguments.get("workflow_name"),
                limit=arguments.get("limit"),
            )
        elif name == "run_golden_tests":
            result = _tool_run_golden_tests(
                workflow_path=arguments.get("workflow_path", ""),
                golden_dir=arguments.get("golden_dir", ".yagra/golden"),
                case_name=arguments.get("case_name"),
                fmt=arguments.get("format", "json"),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    return server


def _resolve_mcp_workflow_path(base_dir: str | None) -> Path:
    """Resolves the workflow path for MCP tool invocations.

    When base_dir is provided, returns ``Path(base_dir) / "_mcp_workflow.yaml"``
    so that ``workflow_path.parent`` equals *base_dir*, enabling correct
    relative-path resolution for ``prompt_ref`` and other file references.

    When base_dir is None, returns the legacy sentinel ``Path("<mcp>")``.

    Args:
        base_dir: Base directory string from the MCP tool argument, or None.

    Returns:
        Path to use as workflow_path in validate_workflow_payload_for_ui.
    """
    if base_dir is None:
        return Path("<mcp>")
    return Path(base_dir) / "_mcp_workflow.yaml"


def _tool_validate_workflow(yaml_content: str, base_dir: str | None = None) -> dict[str, Any]:
    """Implementation of the validate_workflow tool.

    Args:
        yaml_content: The Yagra workflow YAML string to validate.
        base_dir: Base directory for resolving relative paths in prompt_ref
            and other file references. If None, uses ``Path("<mcp>")`` (legacy behavior).

    Returns:
        Dictionary containing the validation result (is_valid, issues).
    """
    import yaml as yaml_lib

    from yagra.application.use_cases.workflow_validation_reporter import (
        WorkflowValidationIssue,
        WorkflowValidationReport,
        validate_workflow_payload_for_ui,
    )

    try:
        payload = yaml_lib.safe_load(yaml_content)
    except yaml_lib.YAMLError as exc:
        issue = WorkflowValidationIssue(
            code="schema_error",
            message=f"YAML parse error: {exc}",
            location=(),
        )
        report = WorkflowValidationReport(issues=[issue])
        return report.to_dict()

    if not isinstance(payload, dict):
        issue = WorkflowValidationIssue(
            code="schema_error",
            message="workflow must be a mapping",
            location=(),
        )
        report = WorkflowValidationReport(issues=[issue])
        return report.to_dict()

    report = validate_workflow_payload_for_ui(
        payload=payload,
        workflow_path=_resolve_mcp_workflow_path(base_dir),
        bundle_root=None,
    )
    return report.to_dict()


def _tool_explain_workflow(yaml_content: str, base_dir: str | None = None) -> dict[str, Any]:
    """Implementation of the explain_workflow tool.

    Args:
        yaml_content: The Yagra workflow YAML string to analyze.
        base_dir: Base directory for resolving relative paths in prompt_ref
            and other file references. If None, uses ``Path("<mcp>")`` (legacy behavior).

    Returns:
        Dictionary containing execution paths, required handlers, and variable flow.
        Returns a dictionary with an error key on validation failure.
    """
    import yaml as yaml_lib

    from yagra.application.use_cases.workflow_validation_reporter import (
        validate_workflow_payload_for_ui,
    )
    from yagra.domain.entities.graph_schema import GraphSpec

    try:
        from yagra.application.use_cases.workflow_explainer import explain_workflow
    except ImportError:
        return {"error": "explain_workflow is not yet available"}

    try:
        payload = yaml_lib.safe_load(yaml_content)
    except yaml_lib.YAMLError as exc:
        return {"error": f"YAML parse error: {exc}"}

    if not isinstance(payload, dict):
        return {"error": "workflow must be a mapping"}

    report = validate_workflow_payload_for_ui(
        payload=payload,
        workflow_path=_resolve_mcp_workflow_path(base_dir),
        bundle_root=None,
    )
    if not report.is_valid:
        return {
            "error": "workflow validation failed",
            "issues": report.to_dict()["issues"],
        }

    spec = GraphSpec.model_validate(payload)
    return explain_workflow(spec, workflow_dir=Path(base_dir) if base_dir else None)


def _tool_validate_workflow_file(workflow_path: str) -> dict[str, Any]:
    """Implementation of the validate_workflow_file tool.

    Reads the workflow YAML from the given file path and validates it.
    Automatically uses the file's directory as base_dir for relative-path
    resolution (e.g., prompt_ref).

    Args:
        workflow_path: Absolute or CWD-relative path to the workflow YAML file.

    Returns:
        Dictionary containing the validation result (is_valid, issues).
        Returns a report with schema_error if the file cannot be read.
    """
    from yagra.application.use_cases.workflow_validation_reporter import (
        WorkflowValidationIssue,
        WorkflowValidationReport,
    )

    try:
        resolved = Path(workflow_path).resolve()
        yaml_content = resolved.read_text(encoding="utf-8")
    except FileNotFoundError:
        issue = WorkflowValidationIssue(
            code="schema_error",
            message=f"workflow file not found: {workflow_path}",
            location=(),
        )
        return WorkflowValidationReport(issues=[issue]).to_dict()
    except OSError as exc:
        issue = WorkflowValidationIssue(
            code="schema_error",
            message=f"failed to read workflow file: {exc}",
            location=(),
        )
        return WorkflowValidationReport(issues=[issue]).to_dict()

    return _tool_validate_workflow(yaml_content=yaml_content, base_dir=str(resolved.parent))


def _tool_explain_workflow_file(workflow_path: str) -> dict[str, Any]:
    """Implementation of the explain_workflow_file tool.

    Reads the workflow YAML from the given file path and statically analyzes it.
    Automatically uses the file's directory as base_dir for relative-path
    resolution (e.g., prompt_ref).

    Args:
        workflow_path: Absolute or CWD-relative path to the workflow YAML file.

    Returns:
        Dictionary containing execution paths, required handlers, and variable flow.
        Returns a dictionary with an error key if the file cannot be read or
        validation fails.
    """
    try:
        resolved = Path(workflow_path).resolve()
        yaml_content = resolved.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"error": f"workflow file not found: {workflow_path}"}
    except OSError as exc:
        return {"error": f"failed to read workflow file: {exc}"}

    return _tool_explain_workflow(yaml_content=yaml_content, base_dir=str(resolved.parent))


def _tool_list_templates() -> dict[str, Any]:
    """Implementation of the list_templates tool.

    Returns:
        Dictionary containing available templates with name, description, and use_case.
    """
    from yagra.application.services.template_initializer import list_templates_with_info

    return {
        "templates": [
            {"name": t.name, "description": t.description, "use_case": t.use_case}
            for t in list_templates_with_info()
        ]
    }


def _tool_list_handlers() -> dict[str, Any]:
    """Implementation of the list_handlers tool.

    Returns:
        Dictionary containing the list of built-in handlers and their params schemas.
    """
    from yagra.handlers.llm_handler import LLM_HANDLER_PARAMS_SCHEMA
    from yagra.handlers.streaming_llm_handler import STREAMING_LLM_HANDLER_PARAMS_SCHEMA
    from yagra.handlers.structured_llm_handler import STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA

    return {
        "handlers": [
            {
                "name": "llm",
                "description": "LLM text output handler. Generated by create_llm_handler()",
                "params_schema": LLM_HANDLER_PARAMS_SCHEMA,
            },
            {
                "name": "structured_llm",
                "description": "Pydantic structured output handler. Generated by create_structured_llm_handler()",
                "params_schema": STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA,
            },
            {
                "name": "streaming_llm",
                "description": "Streaming output handler. Generated by create_streaming_llm_handler()",
                "params_schema": STREAMING_LLM_HANDLER_PARAMS_SCHEMA,
            },
        ],
        "custom_handler_guide": {
            "description": (
                "Custom handlers can be registered in the registry dict passed to Yagra.from_workflow(). "
                "The handler name in YAML must match the key in the registry."
            ),
            "signature": "def my_handler(state: dict, params: dict) -> dict",
            "rules": [
                "Must accept (state: dict, params: dict) and return a dict of state updates.",
                "The returned dict is merged into the workflow state (not replaced).",
                "For conditional branching: set state['__next__'] = '<condition_label>' in the returned dict.",
                "output_key in params is passed as-is from the workflow YAML; read it with params.get('output_key', 'output').",
                "Do NOT set output_key explicitly in YAML for conditional branch source nodes — omit it so __next__ is set automatically by the llm handler.",
            ],
            "example": (
                "def my_router(state: dict, params: dict) -> dict:\n"
                "    label = classify(state['input'])  # returns 'positive', 'negative', etc.\n"
                "    return {'__next__': label}\n\n"
                "registry = {'my_router': my_router, 'llm': create_llm_handler()}\n"
                "app = Yagra.from_workflow('workflow.yaml', registry=registry)"
            ),
        },
    }


def _tool_get_template(name: str) -> dict[str, Any]:
    """Implementation of the get_template tool.

    Returns the file contents of the named template as a dict mapping relative
    file paths to their UTF-8 string content.

    Args:
        name: Template name (from list_templates).

    Returns:
        Dictionary with ``name`` and ``files`` keys on success, or ``error``,
        ``name``, and ``available`` keys when the template is not found.
    """
    from yagra.application.services.template_initializer import (
        TemplateNotFoundError,
        get_template_files,
        list_templates,
    )

    try:
        files = get_template_files(name)
        return {"name": name, "files": files}
    except TemplateNotFoundError:
        return {
            "error": "template not found",
            "name": name,
            "available": list_templates(),
        }


def _tool_get_traces(
    trace_dir: str = ".yagra/traces",
    workflow_name: str | None = None,
    limit: int | None = 20,
) -> dict[str, Any]:
    """Implementation of the get_traces tool.

    Retrieves raw execution trace data from local trace files.

    Args:
        trace_dir: Root trace directory. Defaults to ``.yagra/traces``.
        workflow_name: Filter by workflow name. If None, load all workflows.
        limit: Maximum number of traces to return. Defaults to 20.

    Returns:
        Dictionary with ``traces`` and ``count`` keys on success,
        or ``error`` key on failure.
    """
    try:
        from yagra.application.use_cases.trace_aggregator import load_traces

        traces = load_traces(
            trace_dir=trace_dir,
            workflow_name=workflow_name,
            limit=limit,
        )
        return {"traces": traces, "count": len(traces)}
    except Exception as exc:
        return {"error": str(exc)}


def _tool_analyze_traces(
    trace_dir: str = ".yagra/traces",
    workflow_name: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Implementation of the analyze_traces tool.

    Aggregates multiple execution traces and returns statistical summary.

    Args:
        trace_dir: Root trace directory. Defaults to ``.yagra/traces``.
        workflow_name: Filter by workflow name. If None, load all workflows.
        limit: Limit traces to aggregate. If None, aggregate all available.

    Returns:
        Dictionary containing the aggregated summary on success.
        Returns a dictionary with ``error`` key when no traces are found
        or an exception occurs.
    """
    try:
        from yagra.application.use_cases.trace_aggregator import (
            aggregate_traces,
            load_traces,
        )

        traces = load_traces(
            trace_dir=trace_dir,
            workflow_name=workflow_name,
            limit=limit,
        )
        if not traces:
            return {
                "error": "No traces found",
                "trace_dir": trace_dir,
                "workflow_name": workflow_name,
            }
        summary = aggregate_traces(traces)
        return summary.to_dict()
    except Exception as exc:
        return {"error": str(exc)}


def _tool_propose_update(
    workflow_path: str,
    candidate_yaml: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Implementation of the propose_update tool.

    Reads the current workflow file, validates the candidate YAML, and returns
    a unified diff together with the validation report.

    Args:
        workflow_path: Path to the existing workflow YAML file.
        candidate_yaml: Proposed YAML content to apply.
        reason: Reason for the proposed change. Optional.

    Returns:
        Dictionary containing workflow_path, is_valid, issues, diff, reason,
        current_yaml, and candidate_yaml.  On error, returns a dict with an
        ``error`` key.
    """
    import difflib

    import yaml as yaml_lib

    from yagra.application.use_cases.workflow_validation_reporter import (
        validate_workflow_payload_for_ui,
    )

    resolved = Path(workflow_path).expanduser().resolve()
    if not resolved.exists():
        return {"error": f"workflow file not found: {workflow_path}"}

    try:
        current_yaml = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        return {"error": f"failed to read workflow file: {exc}"}

    try:
        candidate_payload = yaml_lib.safe_load(candidate_yaml)
    except yaml_lib.YAMLError as exc:
        return {"error": f"YAML parse error: {exc}"}

    if not isinstance(candidate_payload, dict):
        return {"error": "candidate_yaml must be a mapping"}

    report = validate_workflow_payload_for_ui(
        payload=candidate_payload,
        workflow_path=resolved,
        bundle_root=None,
    )

    diff_lines = list(
        difflib.unified_diff(
            current_yaml.splitlines(keepends=True),
            candidate_yaml.splitlines(keepends=True),
            fromfile="current",
            tofile="proposed",
        )
    )
    diff_str = "".join(diff_lines)

    return {
        "workflow_path": str(resolved),
        "is_valid": report.is_valid,
        "issues": [issue.to_dict() for issue in report.issues],
        "diff": diff_str,
        "reason": reason if reason is not None else "",
        "current_yaml": current_yaml,
        "candidate_yaml": candidate_yaml,
    }


def _tool_apply_update(
    workflow_path: str,
    candidate_yaml: str,
    base_revision: str | None = None,
    backup_dir: str = ".yagra/backups",
) -> dict[str, Any]:
    """Implementation of the apply_update tool.

    Validates the candidate YAML and writes it to the workflow file, creating a
    backup beforehand.  When *base_revision* is omitted the current revision is
    computed automatically so that no conflict error is raised.

    Args:
        workflow_path: Path to the workflow YAML file to update.
        candidate_yaml: New YAML content to apply.
        base_revision: Expected current revision. When omitted the current
            revision is calculated and used, skipping conflict detection.
        backup_dir: Directory for backups.

    Returns:
        Dictionary with ``success``, ``workflow_path``, ``backup_id``, and
        ``saved_revision`` on success.  On error, returns a dict with an
        ``error`` key.
    """
    import yaml as yaml_lib

    from yagra.application.use_cases.workflow_edit_session import compute_workflow_revision

    try:
        candidate_payload = yaml_lib.safe_load(candidate_yaml)
    except yaml_lib.YAMLError as exc:
        return {"error": f"YAML parse error: {exc}"}

    if not isinstance(candidate_payload, dict):
        return {"error": "candidate_yaml must be a mapping"}

    resolved = Path(workflow_path).expanduser().resolve()
    if not resolved.exists():
        return {"error": f"workflow file not found: {workflow_path}"}

    effective_base_revision: str
    if base_revision is None:
        try:
            current_workflow = yaml_lib.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, yaml_lib.YAMLError) as exc:
            return {"error": f"failed to read current workflow: {exc}"}
        if not isinstance(current_workflow, dict):
            return {"error": "current workflow file is not a mapping"}
        effective_base_revision = compute_workflow_revision(current_workflow, {})
    else:
        effective_base_revision = base_revision

    try:
        result = save_workflow_with_backup(
            workflow_path=resolved,
            candidate_workflow=candidate_payload,
            candidate_ui_state={},
            base_revision=effective_base_revision,
            backup_dir=backup_dir,
        )
    except WorkflowRevisionConflictError as exc:
        return {
            "error": "revision_conflict",
            "message": str(exc),
            "expected": exc.expected_revision,
            "actual": exc.actual_revision,
        }
    except WorkflowValidationFailedError as exc:
        return {
            "error": "validation_failed",
            "issues": [issue.to_dict() for issue in exc.report.issues],
        }
    except Exception as exc:
        return {"error": "apply_failed", "message": str(exc)}

    return {
        "success": True,
        "workflow_path": str(resolved),
        "backup_id": result.backup_id,
        "saved_revision": result.saved_revision,
    }


def _tool_rollback_update(
    workflow_path: str,
    backup_id: str,
    backup_dir: str = ".yagra/backups",
) -> dict[str, Any]:
    """Implementation of the rollback_update tool.

    Restores the workflow file from the specified backup.  The current state is
    preserved as a safety backup before overwriting.

    Args:
        workflow_path: Path to the workflow YAML file to rollback.
        backup_id: Backup ID to restore from.
        backup_dir: Directory for backups.

    Returns:
        Dictionary with ``success``, ``workflow_path``, ``restored_revision``,
        ``backup_id``, and ``safety_backup_id`` on success.  On error, returns a
        dict with an ``error`` key.
    """
    if not workflow_path:
        return {"error": "workflow_path is required"}
    if not backup_id:
        return {"error": "backup_id is required"}

    try:
        result = rollback_workflow_from_backup(
            workflow_path=workflow_path,
            backup_id=backup_id,
            backup_dir=backup_dir,
        )
    except WorkflowBackupNotFoundError as exc:
        return {"error": "backup_not_found", "message": str(exc)}
    except Exception as exc:
        return {"error": "rollback_failed", "message": str(exc)}

    return {
        "success": True,
        "workflow_path": str(Path(workflow_path).expanduser().resolve()),
        "restored_revision": result.restored_revision,
        "backup_id": result.backup_id,
        "safety_backup_id": result.safety_backup_id,
    }


def _tool_run_golden_tests(
    workflow_path: str,
    golden_dir: str = ".yagra/golden",
    case_name: str | None = None,
    fmt: str = "json",
) -> dict[str, Any]:
    """Implementation of the run_golden_tests tool.

    Runs golden test cases against a workflow YAML to detect regressions.
    LLM handlers are mocked with recorded golden outputs so no external
    API calls are made during testing.

    Args:
        workflow_path: Path to the workflow YAML file to test.
        golden_dir: Directory containing golden case files.
        case_name: Specific case name to run. If None, runs all cases
            for the workflow.
        fmt: Output format ('json' or 'summary').

    Returns:
        Dictionary containing test results. On success, includes
        ``results`` (list of per-case results) and ``summary`` keys.
        On error, returns a dict with an ``error`` key.
    """
    from yagra.adapters.outbound.local_golden_case_store import LocalGoldenCaseStore
    from yagra.application.use_cases.golden_test_runner import GoldenTestRunner
    from yagra.ports.outbound.golden_case_repository import (
        GoldenCaseNotFoundError,
        GoldenCaseRepositoryError,
    )

    resolved = Path(workflow_path).expanduser().resolve()
    if not resolved.exists():
        return {"error": f"workflow file not found: {workflow_path}"}

    workflow_name = resolved.stem

    repository = LocalGoldenCaseStore(base_dir=golden_dir)
    runner = GoldenTestRunner(repository=repository)

    try:
        if case_name is not None:
            golden_case = repository.load(workflow_name, case_name)
            results = [runner.run(golden_case=golden_case, workflow_path=resolved)]
        else:
            results = runner.run_all(
                workflow_name=workflow_name,
                workflow_path=resolved,
            )
    except GoldenCaseNotFoundError as exc:
        return {"error": "golden_case_not_found", "message": str(exc)}
    except GoldenCaseRepositoryError as exc:
        return {"error": "golden_case_repository_error", "message": str(exc)}
    except Exception as exc:
        return {"error": "test_execution_failed", "message": str(exc)}

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    if fmt == "summary":
        lines = [f"Golden tests for '{workflow_name}': {passed}/{total} passed"]
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{status}] {r.case_name}: {r.summary}")
        return {
            "workflow_name": workflow_name,
            "total": total,
            "passed": passed,
            "failed": failed,
            "all_passed": failed == 0,
            "summary": "\n".join(lines),
        }

    return {
        "workflow_name": workflow_name,
        "total": total,
        "passed": passed,
        "failed": failed,
        "all_passed": failed == 0,
        "results": [r.model_dump(mode="json") for r in results],
    }


async def run_mcp_server() -> None:
    """Starts the MCP server in stdio mode.

    Raises:
        ImportError: If the mcp library is not installed.
    """
    from importlib.metadata import version as pkg_version

    import mcp.server.stdio
    from mcp.server.lowlevel.server import NotificationOptions
    from mcp.server.models import InitializationOptions

    try:
        _server_version = pkg_version("yagra")
    except Exception:
        _server_version = "0.0.0"

    server = create_mcp_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="yagra",
                server_version=_server_version,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
