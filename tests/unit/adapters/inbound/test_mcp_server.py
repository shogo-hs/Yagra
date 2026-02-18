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
