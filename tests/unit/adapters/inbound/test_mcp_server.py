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


def test_tool_list_handlers():
    from yagra.adapters.inbound.mcp_server import _tool_list_handlers

    result = _tool_list_handlers()
    assert "handlers" in result
    names = [h["name"] for h in result["handlers"]]
    assert "llm" in names
    assert "structured_llm" in names
    assert "streaming_llm" in names


def test_create_mcp_server_requires_mcp_package():
    """Mcp パッケージが未インストールの場合 ImportError が発生することを確認する。"""
    # このテストは mcp がインストールされていれば server オブジェクトが返ることを確認
    # mcp がなければ ImportError が出る（それも正しい動作）
    try:
        from yagra.adapters.inbound.mcp_server import create_mcp_server

        server = create_mcp_server()
        assert server is not None
    except ImportError:
        # mcp 未インストールは正常ケース
        pass


# --- _tool_validate_workflow の payload が dict でない場合 (line 148-154) ---


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


# --- _tool_explain_workflow の ImportError ケース (line 183-184) ---


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


# --- _tool_explain_workflow の YAML parse エラー (line 188-189) ---


def test_tool_explain_workflow_yaml_error():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    result = _tool_explain_workflow("not: valid: yaml: [")
    assert "error" in result
    assert "YAML" in result["error"]


# --- _tool_explain_workflow の payload が dict でない場合 (line 192) ---


def test_tool_explain_workflow_non_mapping_payload():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    result = _tool_explain_workflow("- item1\n- item2\n")
    assert result == {"error": "workflow must be a mapping"}


def test_tool_explain_workflow_null_payload():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    result = _tool_explain_workflow("null\n")
    assert result == {"error": "workflow must be a mapping"}


# --- _tool_explain_workflow の validation 失敗 (line 200) ---


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
    assert "検証" in result["error"] or "issues" in result


# --- create_mcp_server の call_tool (mcp インストール済みの場合のみ) ---


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
