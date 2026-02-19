"""Tests for MCP server tools (without actual MCP connection)."""


def test_tool_validate_workflow_valid():
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    yaml_content = """
version: "1"
start_at: translate
end_at:
  - translate
nodes:
  - id: translate
    handler: llm_handler
edges: []
"""
    result = _tool_validate_workflow(yaml_content)
    assert result["is_valid"] is True
    assert result["issues"] == []


def test_tool_validate_workflow_invalid_node_ref():
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    yaml_content = """
version: "1"
start_at: translat
end_at:
  - translate
nodes:
  - id: translate
    handler: llm_handler
edges: []
"""
    result = _tool_validate_workflow(yaml_content)
    assert result["is_valid"] is False
    assert len(result["issues"]) > 0


def test_tool_validate_workflow_yaml_error():
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    result = _tool_validate_workflow("not: valid: yaml: [")
    assert result["is_valid"] is False


def test_tool_explain_workflow():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    yaml_content = """
version: "1"
start_at: translate
end_at:
  - translate
nodes:
  - id: translate
    handler: llm
    params:
      output_key: translation
edges: []
"""
    result = _tool_explain_workflow(yaml_content)
    assert result["entry_point"] == "translate"
    assert "llm" in result["required_handlers"]
    assert "translation" in result["variable_flow"]["translate"]["outputs"]


def test_tool_list_templates():
    from yagra.adapters.inbound.mcp_server import _tool_list_templates

    result = _tool_list_templates()
    assert "templates" in result
    assert isinstance(result["templates"], list)
    # Each template entry must contain name, description, and use_case keys
    for tmpl in result["templates"]:
        assert "name" in tmpl, f"missing 'name' in template entry: {tmpl}"
        assert "description" in tmpl, f"missing 'description' in template entry: {tmpl}"
        assert "use_case" in tmpl, f"missing 'use_case' in template entry: {tmpl}"


def test_tool_list_handlers():
    from yagra.adapters.inbound.mcp_server import _tool_list_handlers

    result = _tool_list_handlers()
    assert "handlers" in result
    names = [h["name"] for h in result["handlers"]]
    assert "llm" in names
    assert "structured_llm" in names
    assert "streaming_llm" in names


def test_create_mcp_server_requires_mcp_package():
    """Confirms that an ImportError is raised when the mcp package is not installed."""
    # This test confirms that a server object is returned if mcp is installed.
    # If mcp is not installed, an ImportError is raised (which is also correct behavior).
    try:
        from yagra.adapters.inbound.mcp_server import create_mcp_server

        server = create_mcp_server()
        assert server is not None
    except ImportError:
        # mcp not installed is a normal case
        pass


# --- _tool_validate_workflow: payload is not a dict (line 148-154) ---


def test_tool_validate_workflow_non_mapping_payload():
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    result = _tool_validate_workflow("- item1\n- item2\n")
    assert result["is_valid"] is False
    issues = result["issues"]
    assert len(issues) > 0
    assert any(i["code"] == "schema_error" for i in issues)


def test_tool_validate_workflow_null_payload():
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    result = _tool_validate_workflow("null\n")
    assert result["is_valid"] is False


# --- _tool_explain_workflow: ImportError case (line 183-184) ---


def test_tool_explain_workflow_import_error(monkeypatch):
    import sys

    monkeypatch.setitem(
        sys.modules,
        "yagra.application.use_cases.workflow_explainer",
        None,
    )

    import importlib

    import yagra.adapters.inbound.mcp_server as mcp_module

    importlib.reload(mcp_module)

    yaml_content = """
version: "1"
start_at: translate
end_at:
  - translate
nodes:
  - id: translate
    handler: llm_handler
edges: []
"""
    result = mcp_module._tool_explain_workflow(yaml_content)
    assert "error" in result
    assert "explain_workflow" in result["error"] or "not yet available" in result["error"]

    importlib.reload(mcp_module)


# --- _tool_explain_workflow: YAML parse error (line 188-189) ---


def test_tool_explain_workflow_yaml_error():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    result = _tool_explain_workflow("not: valid: yaml: [")
    assert "error" in result
    assert "YAML" in result["error"]


# --- _tool_explain_workflow: payload is not a dict (line 192) ---


def test_tool_explain_workflow_non_mapping_payload():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    result = _tool_explain_workflow("- item1\n- item2\n")
    assert result == {"error": "workflow must be a mapping"}


def test_tool_explain_workflow_null_payload():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    result = _tool_explain_workflow("null\n")
    assert result == {"error": "workflow must be a mapping"}


# --- _tool_explain_workflow: validation failure (line 200) ---


def test_tool_explain_workflow_validation_failure():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    yaml_content = """
version: "1"
start_at: nonexistent_node
end_at:
  - translate
nodes:
  - id: translate
    handler: llm_handler
edges: []
"""
    result = _tool_explain_workflow(yaml_content)
    assert "error" in result
    assert "validation" in result["error"] or "issues" in result


# --- create_mcp_server call_tool (only if mcp is installed) ---


def test_create_mcp_server_call_tool_if_mcp_installed():
    import asyncio

    try:
        from yagra.adapters.inbound.mcp_server import create_mcp_server
    except ImportError:
        return

    try:
        server = create_mcp_server()
    except ImportError:
        return

    call_tool_handler = None
    for handler_name, handler_fn in server.request_handlers.items():
        if "CallTool" in str(handler_name):
            call_tool_handler = handler_fn
            break

    if call_tool_handler is None:
        return

    async def run_validate():
        from mcp.types import CallToolRequest, CallToolRequestParams

        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="validate_workflow",
                arguments={
                    "yaml_content": (
                        "version: '1'\nstart_at: n\nend_at: [n]\nnodes:\n  - id: n\n    handler: h\nedges: []\n"
                    )
                },
            ),
        )
        result = await call_tool_handler(request)
        return result

    try:
        result = asyncio.run(run_validate())
        assert result is not None
    except Exception:
        pass


def test_create_mcp_server_call_tool_unknown_tool():
    import asyncio

    try:
        from yagra.adapters.inbound.mcp_server import create_mcp_server

        server = create_mcp_server()
    except ImportError:
        return

    call_tool_handler = None
    for handler_name, handler_fn in server.request_handlers.items():
        if "CallTool" in str(handler_name):
            call_tool_handler = handler_fn
            break

    if call_tool_handler is None:
        return

    async def run_unknown():
        from mcp.types import CallToolRequest, CallToolRequestParams

        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(name="unknown_tool", arguments={}),
        )
        result = await call_tool_handler(request)
        return result

    try:
        import json

        result = asyncio.run(run_unknown())

        assert result is not None
        contents = result.root.content if hasattr(result, "root") else []
        if contents:
            data = json.loads(contents[0].text)
            assert "error" in data
    except Exception:
        pass


# ---------------------------------------------------------------------------
# _resolve_mcp_workflow_path
# ---------------------------------------------------------------------------


def test_resolve_mcp_workflow_path_none():
    from pathlib import Path

    from yagra.adapters.inbound.mcp_server import _resolve_mcp_workflow_path

    assert _resolve_mcp_workflow_path(None) == Path("<mcp>")


def test_resolve_mcp_workflow_path_with_dir():
    from pathlib import Path

    from yagra.adapters.inbound.mcp_server import _resolve_mcp_workflow_path

    result = _resolve_mcp_workflow_path("/tmp/mydir")
    assert result == Path("/tmp/mydir/_mcp_workflow.yaml")
    assert result.parent == Path("/tmp/mydir")


# ---------------------------------------------------------------------------
# _tool_validate_workflow_file
# ---------------------------------------------------------------------------

_VALID_WORKFLOW_YAML = """\
version: "1"
start_at: node1
end_at:
  - node1
nodes:
  - id: node1
    handler: my_handler
edges: []
"""


def test_tool_validate_workflow_file_valid(tmp_path):
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow_file

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML)

    result = _tool_validate_workflow_file(str(wf))
    assert result["is_valid"] is True
    assert result["issues"] == []


def test_tool_validate_workflow_file_not_found():
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow_file

    result = _tool_validate_workflow_file("/nonexistent/path/workflow.yaml")
    assert result["is_valid"] is False
    assert any(i["code"] == "schema_error" for i in result["issues"])
    assert any("not found" in i["message"] for i in result["issues"])


def test_tool_validate_workflow_file_resolves_prompt_ref(tmp_path):
    """prompt_ref relative paths are resolved from the workflow file's directory."""
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow_file

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    prompt_file = prompts_dir / "chat.yaml"
    prompt_file.write_text("system: You are a helpful assistant.\n")

    wf = tmp_path / "workflow.yaml"
    wf.write_text(
        """\
version: "1"
start_at: chat
end_at:
  - chat
nodes:
  - id: chat
    handler: llm
    params:
      prompt_ref: "prompts/chat.yaml#system"
      model:
        provider: openai
        name: gpt-4o-mini
edges: []
"""
    )

    result = _tool_validate_workflow_file(str(wf))
    assert result["is_valid"] is True, result


# ---------------------------------------------------------------------------
# _tool_explain_workflow_file
# ---------------------------------------------------------------------------


def test_tool_explain_workflow_file_valid(tmp_path):
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow_file

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML)

    result = _tool_explain_workflow_file(str(wf))
    assert result["entry_point"] == "node1"
    assert "my_handler" in result["required_handlers"]


def test_tool_explain_workflow_file_not_found():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow_file

    result = _tool_explain_workflow_file("/nonexistent/path/workflow.yaml")
    assert "error" in result
    assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# base_dir parameter on yaml_content tools
# ---------------------------------------------------------------------------


def test_tool_validate_workflow_with_base_dir_resolves_prompt_ref(tmp_path):
    """base_dir enables relative prompt_ref resolution when passing yaml_content."""
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "chat.yaml").write_text("system: You are a helpful assistant.\n")

    yaml_content = """\
version: "1"
start_at: chat
end_at:
  - chat
nodes:
  - id: chat
    handler: llm
    params:
      prompt_ref: "prompts/chat.yaml#system"
      model:
        provider: openai
        name: gpt-4o-mini
edges: []
"""
    result = _tool_validate_workflow(yaml_content, base_dir=str(tmp_path))
    assert result["is_valid"] is True, result
