"""Yagra MCP server. Provides validate / explain / list_templates / list_handlers as MCP tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
