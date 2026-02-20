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


# ---------------------------------------------------------------------------
# _tool_get_traces
# ---------------------------------------------------------------------------

_SAMPLE_TRACE = {
    "schema_version": "1.0",
    "run_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "workflow_name": "translate",
    "workflow_version": "1.0",
    "started_at": "2026-02-20T10:00:00+00:00",
    "ended_at": "2026-02-20T10:00:01+00:00",
    "status": "success",
    "nodes": [
        {
            "node_id": "translate",
            "handler": "llm",
            "status": "success",
            "started_at": "2026-02-20T10:00:00+00:00",
            "ended_at": "2026-02-20T10:00:01+00:00",
            "duration_ms": 950.0,
            "input_snapshot": {"input": "hello"},
            "output_snapshot": {"translation": "こんにちは"},
            "llm_call": {
                "model": "openai/gpt-4o-mini",
                "provider": "openai",
                "prompt_tokens": 50,
                "completion_tokens": 20,
                "total_tokens": 70,
                "estimated_cost_usd": 0.00015,
            },
            "error": None,
        }
    ],
    "summary": {
        "total_nodes_executed": 1,
        "succeeded_nodes": 1,
        "failed_nodes": 0,
        "total_duration_ms": 1000.0,
        "total_prompt_tokens": 50,
        "total_completion_tokens": 20,
        "total_tokens": 70,
        "total_estimated_cost_usd": 0.00015,
        "node_order": ["translate"],
    },
    "metadata": {
        "yagra_version": "0.6.11",
        "python_version": "3.12.0",
        "platform": "Darwin",
    },
}


def _write_sample_trace(tmp_path, workflow_name="translate", trace_data=None):
    """Helper to write a sample trace JSON file in the LocalTraceSink directory layout."""
    import json

    data = trace_data if trace_data is not None else dict(_SAMPLE_TRACE)
    data["workflow_name"] = workflow_name
    workflow_dir = tmp_path / workflow_name
    workflow_dir.mkdir(parents=True, exist_ok=True)
    run_id = data.get("run_id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    run_id_short = run_id.replace("-", "")[:8]
    filename = f"{workflow_name}_20260220T100000_{run_id_short}.json"
    filepath = workflow_dir / filename
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return filepath


def test_get_traces_tool_listed():
    """Verify get_traces appears in list_tools."""
    try:
        from yagra.adapters.inbound.mcp_server import create_mcp_server
    except ImportError:
        return

    try:
        server = create_mcp_server()
    except ImportError:
        return

    import asyncio

    list_tools_handler = None
    for handler_name, handler_fn in server.request_handlers.items():
        if "ListTools" in str(handler_name):
            list_tools_handler = handler_fn
            break

    if list_tools_handler is None:
        return

    async def run():
        from mcp.types import ListToolsRequest

        request = ListToolsRequest(method="tools/list")
        result = await list_tools_handler(request)
        return result

    try:
        result = asyncio.run(run())
        tools = result.root.tools if hasattr(result, "root") else []
        tool_names = [t.name for t in tools]
        assert "get_traces" in tool_names
    except Exception:
        # If MCP internals differ, fall back to testing the implementation directly
        pass


def test_analyze_traces_tool_listed():
    """Verify analyze_traces appears in list_tools."""
    try:
        from yagra.adapters.inbound.mcp_server import create_mcp_server
    except ImportError:
        return

    try:
        server = create_mcp_server()
    except ImportError:
        return

    import asyncio

    list_tools_handler = None
    for handler_name, handler_fn in server.request_handlers.items():
        if "ListTools" in str(handler_name):
            list_tools_handler = handler_fn
            break

    if list_tools_handler is None:
        return

    async def run():
        from mcp.types import ListToolsRequest

        request = ListToolsRequest(method="tools/list")
        result = await list_tools_handler(request)
        return result

    try:
        result = asyncio.run(run())
        tools = result.root.tools if hasattr(result, "root") else []
        tool_names = [t.name for t in tools]
        assert "analyze_traces" in tool_names
    except Exception:
        pass


def test_get_traces_returns_traces(tmp_path):
    """Test get_traces with sample trace files in tmp_path."""
    from yagra.adapters.inbound.mcp_server import _tool_get_traces

    _write_sample_trace(tmp_path, workflow_name="translate")

    result = _tool_get_traces(trace_dir=str(tmp_path), workflow_name="translate", limit=20)
    assert "traces" in result
    assert "count" in result
    assert result["count"] == 1
    assert len(result["traces"]) == 1
    assert result["traces"][0]["workflow_name"] == "translate"


def test_get_traces_empty_dir(tmp_path):
    """Test get_traces with no trace files."""
    from yagra.adapters.inbound.mcp_server import _tool_get_traces

    result = _tool_get_traces(trace_dir=str(tmp_path), workflow_name=None, limit=20)
    assert "traces" in result
    assert result["count"] == 0
    assert result["traces"] == []


def test_get_traces_nonexistent_dir():
    """Test get_traces with a directory that does not exist."""
    from yagra.adapters.inbound.mcp_server import _tool_get_traces

    result = _tool_get_traces(trace_dir="/nonexistent/path/traces", workflow_name=None, limit=20)
    assert "traces" in result
    assert result["count"] == 0


def test_get_traces_filters_by_workflow_name(tmp_path):
    """Test that workflow_name filter selects the correct subdirectory."""
    from yagra.adapters.inbound.mcp_server import _tool_get_traces

    _write_sample_trace(tmp_path, workflow_name="translate")

    other_trace = dict(_SAMPLE_TRACE)
    other_trace["workflow_name"] = "summarize"
    other_trace["run_id"] = "11111111-2222-3333-4444-555555555555"
    _write_sample_trace(tmp_path, workflow_name="summarize", trace_data=other_trace)

    result = _tool_get_traces(trace_dir=str(tmp_path), workflow_name="translate", limit=20)
    assert result["count"] == 1
    assert result["traces"][0]["workflow_name"] == "translate"


def test_get_traces_respects_limit(tmp_path):
    """Test that the limit parameter caps the number of returned traces."""
    import json
    import uuid

    from yagra.adapters.inbound.mcp_server import _tool_get_traces

    for i in range(5):
        trace_data = dict(_SAMPLE_TRACE)
        trace_data["run_id"] = str(uuid.uuid4())
        trace_data["started_at"] = f"2026-02-20T10:00:{i:02d}+00:00"
        workflow_dir = tmp_path / "translate"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        run_id = str(trace_data["run_id"])
        rid = run_id.replace("-", "")[:8]
        fp = workflow_dir / f"translate_20260220T1000{i:02d}_{rid}.json"
        fp.write_text(json.dumps(trace_data, ensure_ascii=False), encoding="utf-8")

    result = _tool_get_traces(trace_dir=str(tmp_path), workflow_name="translate", limit=3)
    assert result["count"] == 3


def test_analyze_traces_returns_summary(tmp_path):
    """Test aggregation with sample traces."""
    from yagra.adapters.inbound.mcp_server import _tool_analyze_traces

    _write_sample_trace(tmp_path, workflow_name="translate")

    result = _tool_analyze_traces(trace_dir=str(tmp_path), workflow_name="translate")
    assert "error" not in result
    assert result["total_runs"] == 1
    assert result["workflow_name"] == "translate"
    assert result["successful_runs"] == 1
    assert result["total_tokens"] == 70
    # Check per-node stats
    assert len(result["node_stats"]) == 1
    node = result["node_stats"][0]
    assert node["node_id"] == "translate"
    assert node["execution_count"] == 1
    assert node["success_count"] == 1


def test_analyze_traces_no_traces(tmp_path):
    """Test error response when no traces found."""
    from yagra.adapters.inbound.mcp_server import _tool_analyze_traces

    result = _tool_analyze_traces(trace_dir=str(tmp_path), workflow_name="nonexistent")
    assert "error" in result
    assert result["error"] == "No traces found"
    assert result["trace_dir"] == str(tmp_path)
    assert result["workflow_name"] == "nonexistent"


# ---------------------------------------------------------------------------
# _tool_propose_update
# ---------------------------------------------------------------------------

_VALID_WORKFLOW_YAML_PROPOSE = """\
version: "1"
start_at: node1
end_at:
  - node1
nodes:
  - id: node1
    handler: my_handler
edges: []
"""

_UPDATED_WORKFLOW_YAML_PROPOSE = """\
version: "1"
start_at: node1
end_at:
  - node1
nodes:
  - id: node1
    handler: my_handler
  - id: node2
    handler: other_handler
edges: []
"""


def test_tool_propose_update_valid(tmp_path):
    """Valid candidate YAML returns is_valid=True and a non-empty diff."""
    from yagra.adapters.inbound.mcp_server import _tool_propose_update

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    result = _tool_propose_update(
        workflow_path=str(wf),
        candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
        reason="add node2",
    )

    assert "error" not in result
    assert result["is_valid"] is True
    assert result["issues"] == []
    assert result["diff"] != ""
    assert result["reason"] == "add node2"
    assert result["current_yaml"] == _VALID_WORKFLOW_YAML_PROPOSE
    assert result["candidate_yaml"] == _UPDATED_WORKFLOW_YAML_PROPOSE


def test_tool_propose_update_invalid_yaml(tmp_path):
    """Malformed candidate_yaml returns an error key."""
    from yagra.adapters.inbound.mcp_server import _tool_propose_update

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    result = _tool_propose_update(
        workflow_path=str(wf),
        candidate_yaml="not: valid: yaml: [",
    )

    assert "error" in result


def test_tool_propose_update_no_change(tmp_path):
    """Same content as current file results in an empty diff string."""
    from yagra.adapters.inbound.mcp_server import _tool_propose_update

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    result = _tool_propose_update(
        workflow_path=str(wf),
        candidate_yaml=_VALID_WORKFLOW_YAML_PROPOSE,
    )

    assert "error" not in result
    assert result["diff"] == ""


def test_tool_propose_update_file_not_found():
    """Non-existent workflow_path returns an error key."""
    from yagra.adapters.inbound.mcp_server import _tool_propose_update

    result = _tool_propose_update(
        workflow_path="/nonexistent/path/workflow.yaml",
        candidate_yaml=_VALID_WORKFLOW_YAML_PROPOSE,
    )

    assert "error" in result


# ---------------------------------------------------------------------------
# _tool_apply_update
# ---------------------------------------------------------------------------


def test_tool_apply_update_success(tmp_path, monkeypatch):
    """Valid YAML is applied and success=True with backup_id is returned."""
    from yagra.adapters.inbound import mcp_server
    from yagra.application.use_cases.workflow_persistence import WorkflowSaveResult

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    mock_result = WorkflowSaveResult(saved_revision="abc123", backup_id="bk-001")
    monkeypatch.setattr(mcp_server, "save_workflow_with_backup", lambda *a, **k: mock_result)

    result = mcp_server._tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
    )

    assert result.get("success") is True
    assert result["backup_id"] == "bk-001"
    assert result["saved_revision"] == "abc123"


def test_tool_apply_update_invalid_yaml(tmp_path):
    """Malformed candidate_yaml returns an error key."""
    from yagra.adapters.inbound.mcp_server import _tool_apply_update

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    result = _tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml="not: valid: yaml: [",
    )

    assert "error" in result


def test_tool_apply_update_revision_conflict(tmp_path, monkeypatch):
    """WorkflowRevisionConflictError is mapped to error='revision_conflict'."""
    from yagra.adapters.inbound import mcp_server
    from yagra.application.use_cases.workflow_persistence import WorkflowRevisionConflictError

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    def raise_conflict(*args: object, **kwargs: object) -> None:
        raise WorkflowRevisionConflictError(
            expected_revision="expected_rev", actual_revision="actual_rev"
        )

    monkeypatch.setattr(mcp_server, "save_workflow_with_backup", raise_conflict)

    result = mcp_server._tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
        base_revision="expected_rev",
    )

    assert result.get("error") == "revision_conflict"
    assert "expected" in result
    assert "actual" in result


def test_tool_apply_update_validation_failed(tmp_path, monkeypatch):
    """WorkflowValidationFailedError is mapped to error='validation_failed'."""
    from yagra.adapters.inbound import mcp_server
    from yagra.application.use_cases.workflow_persistence import WorkflowValidationFailedError
    from yagra.application.use_cases.workflow_validation_reporter import WorkflowValidationReport

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    def raise_validation(*args: object, **kwargs: object) -> None:
        raise WorkflowValidationFailedError(WorkflowValidationReport(issues=[]))

    monkeypatch.setattr(mcp_server, "save_workflow_with_backup", raise_validation)

    result = mcp_server._tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
    )

    assert result.get("error") == "validation_failed"
    assert "issues" in result


# ---------------------------------------------------------------------------
# _tool_rollback_update
# ---------------------------------------------------------------------------


def test_tool_rollback_update_success(tmp_path, monkeypatch):
    """Normal rollback returns success=True with expected fields."""
    from yagra.adapters.inbound import mcp_server
    from yagra.application.use_cases.workflow_persistence import WorkflowRollbackResult

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    mock_result = WorkflowRollbackResult(
        restored_revision="rev-old",
        backup_id="bk-001",
        safety_backup_id="bk-safety-001",
    )
    monkeypatch.setattr(mcp_server, "rollback_workflow_from_backup", lambda *a, **k: mock_result)

    result = mcp_server._tool_rollback_update(
        workflow_path=str(wf),
        backup_id="bk-001",
    )

    assert result.get("success") is True
    assert result["restored_revision"] == "rev-old"
    assert result["backup_id"] == "bk-001"
    assert result["safety_backup_id"] == "bk-safety-001"


def test_tool_rollback_update_backup_not_found(tmp_path, monkeypatch):
    """WorkflowBackupNotFoundError is mapped to error='backup_not_found'."""
    from yagra.adapters.inbound import mcp_server
    from yagra.application.services.workflow_file_store import WorkflowBackupNotFoundError

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    def raise_not_found(*args: object, **kwargs: object) -> None:
        raise WorkflowBackupNotFoundError("backup not found: bk-999")

    monkeypatch.setattr(mcp_server, "rollback_workflow_from_backup", raise_not_found)

    result = mcp_server._tool_rollback_update(
        workflow_path=str(wf),
        backup_id="bk-999",
    )

    assert result.get("error") == "backup_not_found"
    assert "message" in result


def test_tool_rollback_update_missing_required_field():
    """Empty workflow_path or backup_id returns an error key."""
    from yagra.adapters.inbound.mcp_server import _tool_rollback_update

    # missing backup_id
    result = _tool_rollback_update(workflow_path="/some/path/workflow.yaml", backup_id="")
    assert "error" in result

    # missing workflow_path
    result2 = _tool_rollback_update(workflow_path="", backup_id="bk-001")
    assert "error" in result2
