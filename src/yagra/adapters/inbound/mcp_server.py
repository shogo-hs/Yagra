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
                    "When is_valid is false, issues contain fix suggestions (context.suggestion)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "yaml_content": {
                            "type": "string",
                            "description": "The Yagra workflow YAML string to validate",
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
                    "Use this to understand the workflow structure before running it."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "yaml_content": {
                            "type": "string",
                            "description": "The Yagra workflow YAML string to analyze",
                        },
                    },
                    "required": ["yaml_content"],
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
            result = _tool_validate_workflow(arguments.get("yaml_content", ""))
        elif name == "explain_workflow":
            result = _tool_explain_workflow(arguments.get("yaml_content", ""))
        elif name == "list_templates":
            result = _tool_list_templates()
        elif name == "list_handlers":
            result = _tool_list_handlers()
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    return server


def _tool_validate_workflow(yaml_content: str) -> dict[str, Any]:
    """Implementation of the validate_workflow tool.

    Args:
        yaml_content: The Yagra workflow YAML string to validate.

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
        workflow_path=Path("<mcp>"),
        bundle_root=None,
    )
    return report.to_dict()


def _tool_explain_workflow(yaml_content: str) -> dict[str, Any]:
    """Implementation of the explain_workflow tool.

    Args:
        yaml_content: The Yagra workflow YAML string to analyze.

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
        workflow_path=Path("<mcp>"),
        bundle_root=None,
    )
    if not report.is_valid:
        return {
            "error": "workflow validation failed",
            "issues": report.to_dict()["issues"],
        }

    spec = GraphSpec.model_validate(payload)
    return explain_workflow(spec)


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
        ]
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
