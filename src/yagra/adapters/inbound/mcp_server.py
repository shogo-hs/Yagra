"""Yagra MCP サーバー。validate / explain / list_templates / list_handlers を MCP ツールとして提供する。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def create_mcp_server() -> Any:
    """Yagra MCP サーバーを生成して返す。

    mcp ライブラリが未インストールの場合は ImportError を送出する。

    Returns:
        設定済みの mcp.server.Server インスタンス。

    Raises:
        ImportError: mcp ライブラリがインストールされていない場合。
    """
    try:
        import mcp.server.stdio  # noqa: F401
        from mcp.server import Server
        from mcp.types import TextContent, Tool
    except ImportError as exc:
        raise ImportError(
            "MCP サーバーを使用するには mcp パッケージが必要です。\n"
            "'uv add yagra[mcp]' または 'pip install yagra[mcp]' でインストールしてください。"
        ) from exc

    server = Server("yagra")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """利用可能な MCP ツールのリストを返す。"""
        return [
            Tool(
                name="validate_workflow",
                description=(
                    "Yagra ワークフロー YAML を検証し、バリデーション結果を JSON で返す。"
                    "is_valid が false の場合、issues に修正提案（context.suggestion）が含まれる。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "yaml_content": {
                            "type": "string",
                            "description": "検証する Yagra ワークフロー YAML の文字列",
                        },
                    },
                    "required": ["yaml_content"],
                },
            ),
            Tool(
                name="explain_workflow",
                description=(
                    "Yagra ワークフロー YAML を静的解析し、実行パス・必要ハンドラー・変数フローを JSON で返す。"
                    "ワークフローを実行する前に構造を把握するために使用する。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "yaml_content": {
                            "type": "string",
                            "description": "解析する Yagra ワークフロー YAML の文字列",
                        },
                    },
                    "required": ["yaml_content"],
                },
            ),
            Tool(
                name="list_templates",
                description="利用可能な Yagra ワークフローテンプレートの名前リストを返す。",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="list_handlers",
                description=(
                    "Yagra 組み込みハンドラーの一覧と params スキーマを返す。"
                    "ワークフロー YAML の params フィールドに指定できるキーを確認するために使用する。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """MCP ツールを実行する。

        Args:
            name: 実行するツール名。
            arguments: ツールの引数辞書。

        Returns:
            ツール実行結果を含む TextContent のリスト。
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
    """validate_workflow ツールの実装。

    Args:
        yaml_content: 検証する Yagra ワークフロー YAML の文字列。

    Returns:
        バリデーション結果を含む辞書（is_valid, issues）。
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
            message=f"YAML パースエラー: {exc}",
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
    """explain_workflow ツールの実装。

    Args:
        yaml_content: 解析する Yagra ワークフロー YAML の文字列。

    Returns:
        実行パス・必要ハンドラー・変数フローを含む辞書。
        検証エラー時は error キーを含む辞書。
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
        return {"error": f"YAML パースエラー: {exc}"}

    if not isinstance(payload, dict):
        return {"error": "workflow must be a mapping"}

    report = validate_workflow_payload_for_ui(
        payload=payload,
        workflow_path=Path("<mcp>"),
        bundle_root=None,
    )
    if not report.is_valid:
        return {
            "error": "ワークフローの検証に失敗しました",
            "issues": report.to_dict()["issues"],
        }

    spec = GraphSpec.model_validate(payload)
    return explain_workflow(spec)


def _tool_list_templates() -> dict[str, Any]:
    """list_templates ツールの実装。

    Returns:
        利用可能なテンプレート名リストを含む辞書。
    """
    from yagra.application.services.template_initializer import list_templates

    return {"templates": list_templates()}


def _tool_list_handlers() -> dict[str, Any]:
    """list_handlers ツールの実装。

    Returns:
        組み込みハンドラーの一覧と params スキーマを含む辞書。
    """
    from yagra.handlers.llm_handler import LLM_HANDLER_PARAMS_SCHEMA
    from yagra.handlers.streaming_llm_handler import STREAMING_LLM_HANDLER_PARAMS_SCHEMA
    from yagra.handlers.structured_llm_handler import STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA

    return {
        "handlers": [
            {
                "name": "llm",
                "description": "LLM テキスト出力ハンドラー。create_llm_handler() で生成する",
                "params_schema": LLM_HANDLER_PARAMS_SCHEMA,
            },
            {
                "name": "structured_llm",
                "description": "Pydantic 構造化出力ハンドラー。create_structured_llm_handler() で生成する",
                "params_schema": STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA,
            },
            {
                "name": "streaming_llm",
                "description": "ストリーミング出力ハンドラー。create_streaming_llm_handler() で生成する",
                "params_schema": STREAMING_LLM_HANDLER_PARAMS_SCHEMA,
            },
        ]
    }


async def run_mcp_server() -> None:
    """MCP サーバーを stdio モードで起動する。

    Raises:
        ImportError: mcp ライブラリがインストールされていない場合。
    """
    import mcp.server.stdio
    from mcp.server.models import InitializationOptions

    server = create_mcp_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="yagra",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )
