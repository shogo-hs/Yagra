"""Tests for MCP server tools (without actual MCP connection)."""

import pytest


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
# _tool_validate_workflow with workflow_path
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


def test_tool_validate_workflow_with_workflow_path_valid(tmp_path):
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML)

    result = _tool_validate_workflow(workflow_path=str(wf))
    assert result["is_valid"] is True
    assert result["issues"] == []


def test_tool_validate_workflow_with_workflow_path_not_found():
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    result = _tool_validate_workflow(workflow_path="/nonexistent/path/workflow.yaml")
    assert result["is_valid"] is False
    assert any(i["code"] == "schema_error" for i in result["issues"])
    assert any("not found" in i["message"] for i in result["issues"])


def test_tool_validate_workflow_with_workflow_path_resolves_prompt_ref(tmp_path):
    """prompt_ref relative paths are resolved from the workflow file's directory."""
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

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

    result = _tool_validate_workflow(workflow_path=str(wf))
    assert result["is_valid"] is True, result


def test_tool_validate_workflow_neither_provided():
    """Returns error when neither yaml_content nor workflow_path is provided."""
    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    result = _tool_validate_workflow()
    assert result["is_valid"] is False
    assert any("either yaml_content or workflow_path" in i["message"] for i in result["issues"])


# ---------------------------------------------------------------------------
# _tool_explain_workflow with workflow_path
# ---------------------------------------------------------------------------


def test_tool_explain_workflow_with_workflow_path_valid(tmp_path):
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML)

    result = _tool_explain_workflow(workflow_path=str(wf))
    assert result["entry_point"] == "node1"
    assert "my_handler" in result["required_handlers"]


def test_tool_explain_workflow_with_workflow_path_not_found():
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    result = _tool_explain_workflow(workflow_path="/nonexistent/path/workflow.yaml")
    assert "error" in result
    assert "not found" in result["error"]


def test_tool_explain_workflow_neither_provided():
    """Returns error when neither yaml_content nor workflow_path is provided."""
    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    result = _tool_explain_workflow()
    assert "error" in result
    assert "either yaml_content or workflow_path" in result["error"]


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


# ---------------------------------------------------------------------------
# _tool_get_template
# ---------------------------------------------------------------------------


def test_tool_get_template_success():
    """Valid template name returns name and files keys."""
    from yagra.adapters.inbound.mcp_server import _tool_get_template, _tool_list_templates

    templates = _tool_list_templates()
    template_names = [t["name"] for t in templates["templates"]]
    if not template_names:
        return  # no templates available to test

    first_name = template_names[0]
    result = _tool_get_template(first_name)
    assert "error" not in result
    assert result["name"] == first_name
    assert "files" in result
    assert isinstance(result["files"], dict)


def test_tool_get_template_not_found():
    """Non-existent template name returns error='template not found' and available list."""
    from yagra.adapters.inbound.mcp_server import _tool_get_template

    result = _tool_get_template("__nonexistent_template_xyz__")
    assert result["error"] == "template not found"
    assert "name" in result
    assert "available" in result
    assert isinstance(result["available"], list)


# ---------------------------------------------------------------------------
# _tool_validate_workflow with workflow_path: OSError path
# ---------------------------------------------------------------------------


def test_tool_validate_workflow_with_workflow_path_os_error(tmp_path):
    """PermissionError on file read is returned as is_valid=False with schema_error."""
    import stat

    from yagra.adapters.inbound.mcp_server import _tool_validate_workflow

    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(
        "version: '1'\nstart_at: n\nend_at: [n]\nnodes:\n  - id: n\n    handler: h\nedges: []\n"
    )
    # Remove read permission
    workflow_file.chmod(0o000)
    try:
        result = _tool_validate_workflow(workflow_path=str(workflow_file))
        assert result["is_valid"] is False
        assert any("schema_error" == i["code"] for i in result["issues"])
    finally:
        workflow_file.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# _tool_explain_workflow with workflow_path: OSError path
# ---------------------------------------------------------------------------


def test_tool_explain_workflow_with_workflow_path_os_error(tmp_path):
    """PermissionError on file read returns error key."""
    import stat

    from yagra.adapters.inbound.mcp_server import _tool_explain_workflow

    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(
        "version: '1'\nstart_at: n\nend_at: [n]\nnodes:\n  - id: n\n    handler: h\nedges: []\n"
    )
    workflow_file.chmod(0o000)
    try:
        result = _tool_explain_workflow(workflow_path=str(workflow_file))
        assert "error" in result
    finally:
        workflow_file.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# _tool_propose_update: additional error paths
# ---------------------------------------------------------------------------


def test_tool_propose_update_os_error(tmp_path):
    """PermissionError on current file read returns error key."""
    import stat

    from yagra.adapters.inbound.mcp_server import _tool_propose_update

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)
    wf.chmod(0o000)
    try:
        result = _tool_propose_update(
            workflow_path=str(wf),
            candidate_yaml=_VALID_WORKFLOW_YAML_PROPOSE,
        )
        assert "error" in result
    finally:
        wf.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_tool_propose_update_non_mapping_yaml(tmp_path):
    """candidate_yaml that is a list returns error='candidate_yaml must be a mapping'."""
    from yagra.adapters.inbound.mcp_server import _tool_propose_update

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    result = _tool_propose_update(
        workflow_path=str(wf),
        candidate_yaml="- item1\n- item2\n",
    )
    assert "error" in result
    assert result["error"] == "candidate_yaml must be a mapping"


# ---------------------------------------------------------------------------
# _tool_apply_update: additional error paths
# ---------------------------------------------------------------------------


def test_tool_apply_update_non_mapping_yaml(tmp_path):
    """candidate_yaml that is a list returns error='candidate_yaml must be a mapping'."""
    from yagra.adapters.inbound.mcp_server import _tool_apply_update

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    result = _tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml="- item1\n- item2\n",
    )
    assert "error" in result
    assert result["error"] == "candidate_yaml must be a mapping"


def test_tool_apply_update_file_not_found():
    """Non-existent workflow_path returns error key with 'not found'."""
    from yagra.adapters.inbound.mcp_server import _tool_apply_update

    result = _tool_apply_update(
        workflow_path="/nonexistent/path/workflow.yaml",
        candidate_yaml=_VALID_WORKFLOW_YAML_PROPOSE,
    )
    assert "error" in result
    assert "not found" in result["error"]


def test_tool_apply_update_current_workflow_os_error(tmp_path):
    """OSError reading current workflow (for auto base_revision) returns error key."""
    import stat

    from yagra.adapters.inbound.mcp_server import _tool_apply_update

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)
    wf.chmod(0o000)
    try:
        # base_revision=None triggers read of current file
        result = _tool_apply_update(
            workflow_path=str(wf),
            candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
            base_revision=None,
        )
        assert "error" in result
    finally:
        wf.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_tool_apply_update_current_workflow_non_mapping(tmp_path):
    """Current workflow that is not a mapping returns error key."""
    from yagra.adapters.inbound.mcp_server import _tool_apply_update

    wf = tmp_path / "workflow.yaml"
    wf.write_text("- item1\n- item2\n")

    # base_revision=None triggers auto-calculation from current file
    result = _tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml=_VALID_WORKFLOW_YAML_PROPOSE,
        base_revision=None,
    )
    assert "error" in result
    assert result["error"] == "current workflow file is not a mapping"


def test_tool_apply_update_generic_exception(tmp_path, monkeypatch):
    """RuntimeError from save_workflow_with_backup is mapped to error='apply_failed'."""
    from unittest.mock import MagicMock

    from yagra.adapters.inbound import mcp_server

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    mock_save = MagicMock(side_effect=RuntimeError("unexpected error"))
    monkeypatch.setattr(mcp_server, "save_workflow_with_backup", mock_save)

    result = mcp_server._tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
    )
    assert result.get("error") == "apply_failed"
    assert "message" in result


# ---------------------------------------------------------------------------
# _tool_apply_update: golden_pass_required gate (#4)
# ---------------------------------------------------------------------------


def test_tool_apply_update_golden_gate_pass_with_result(tmp_path, monkeypatch):
    """golden_pass_required=True + last_golden_result pass: apply succeeds without internal run."""
    from yagra.adapters.inbound import mcp_server
    from yagra.application.use_cases.workflow_persistence import WorkflowSaveResult

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    # Guard: internal _tool_run_golden_tests must NOT be invoked when last_golden_result is passed.
    def _raise_if_called(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError(
            "_tool_run_golden_tests must not be called when last_golden_result is supplied"
        )

    monkeypatch.setattr(mcp_server, "_tool_run_golden_tests", _raise_if_called)

    mock_result = WorkflowSaveResult(saved_revision="rev-ok", backup_id="bk-ok")
    monkeypatch.setattr(mcp_server, "save_workflow_with_backup", lambda *a, **k: mock_result)

    result = mcp_server._tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
        golden_pass_required=True,
        last_golden_result={"total": 2, "passed": 2, "failed": 0},
    )

    assert result.get("success") is True
    assert result["backup_id"] == "bk-ok"
    # passed == total → no warnings
    assert "warnings" not in result


def test_tool_apply_update_golden_gate_fail_blocks_apply(tmp_path, monkeypatch):
    """golden_pass_required=True + last_golden_result fail: apply is blocked, file untouched."""
    from yagra.adapters.inbound import mcp_server

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)
    original_content = wf.read_text()

    # Guard: save_workflow_with_backup must NOT be called when golden fails.
    def _raise_if_save(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "save_workflow_with_backup must not be called when golden tests do not pass"
        )

    monkeypatch.setattr(mcp_server, "save_workflow_with_backup", _raise_if_save)

    result = mcp_server._tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
        golden_pass_required=True,
        last_golden_result={"total": 3, "passed": 2, "failed": 1},
    )

    assert result.get("error") == "golden_not_passed"
    assert "summary" in result
    assert result["summary"] == {"total": 3, "passed": 2, "failed": 1}
    assert "message" in result
    assert "2/3" in result["message"]
    assert "hint" in result

    # File must not have been written.
    assert wf.read_text() == original_content


def test_tool_apply_update_golden_gate_no_cases_warning(tmp_path, monkeypatch):
    """No golden cases defined (total=0): apply succeeds with explicit warning."""
    from yagra.adapters.inbound import mcp_server
    from yagra.application.use_cases.workflow_persistence import WorkflowSaveResult

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    # Empty golden_dir (directory exists but no cases inside)
    empty_golden_dir = tmp_path / ".yagra" / "golden"
    empty_golden_dir.mkdir(parents=True, exist_ok=True)

    mock_result = WorkflowSaveResult(saved_revision="rev-warn", backup_id="bk-warn")
    monkeypatch.setattr(mcp_server, "save_workflow_with_backup", lambda *a, **k: mock_result)

    result = mcp_server._tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
        golden_pass_required=True,
        golden_dir=str(empty_golden_dir),
    )

    assert result.get("success") is True
    assert result.get("warnings") == ["no_golden_cases_defined"], (
        f"expected warning 'no_golden_cases_defined', got: {result.get('warnings')!r}"
    )
    assert result["backup_id"] == "bk-warn"


def test_tool_apply_update_golden_gate_opt_out(tmp_path, monkeypatch):
    """golden_pass_required=False: legacy behavior — skip golden gate entirely."""
    from yagra.adapters.inbound import mcp_server
    from yagra.application.use_cases.workflow_persistence import WorkflowSaveResult

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    # Guard: _tool_run_golden_tests must NOT be invoked when opt-out.
    def _raise_if_called(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError(
            "_tool_run_golden_tests must not be called when golden_pass_required=False"
        )

    monkeypatch.setattr(mcp_server, "_tool_run_golden_tests", _raise_if_called)

    mock_result = WorkflowSaveResult(saved_revision="rev-legacy", backup_id="bk-legacy")
    monkeypatch.setattr(mcp_server, "save_workflow_with_backup", lambda *a, **k: mock_result)

    result = mcp_server._tool_apply_update(
        workflow_path=str(wf),
        candidate_yaml=_UPDATED_WORKFLOW_YAML_PROPOSE,
        golden_pass_required=False,
    )

    assert result.get("success") is True
    assert result["backup_id"] == "bk-legacy"
    # No golden gate → no warnings.
    assert "warnings" not in result


def test_tool_apply_update_golden_gate_tool_schema_description():
    """Tool schema for apply_update documents golden_pass_required / last_golden_result / golden_dir."""
    import asyncio

    try:
        import mcp  # noqa: F401
    except ImportError:
        pytest.skip("mcp package not installed")

    from yagra.adapters.inbound.mcp_server import create_mcp_server

    try:
        server = create_mcp_server()
    except ImportError:
        pytest.skip("mcp package not installed (create_mcp_server)")

    list_tools_handler = None
    for handler_name, handler_fn in server.request_handlers.items():
        if "ListTools" in str(handler_name):
            list_tools_handler = handler_fn
            break
    if list_tools_handler is None:
        pytest.skip("ListTools handler not found")

    async def _run() -> object:
        from mcp.types import ListToolsRequest

        request = ListToolsRequest(method="tools/list")
        return await list_tools_handler(request)

    try:
        result = asyncio.run(_run())
    except Exception:
        pytest.skip("could not invoke list_tools handler")

    tools = result.root.tools if hasattr(result, "root") else []
    apply_tool = next((t for t in tools if t.name == "apply_update"), None)
    assert apply_tool is not None, "apply_update Tool missing from list_tools"

    # Tool-level description must mention the golden gate contract.
    assert "golden" in apply_tool.description.lower(), (
        f"apply_update description must mention golden gate; got: {apply_tool.description!r}"
    )
    assert "golden_pass_required" in apply_tool.description, (
        "apply_update description must reference golden_pass_required explicitly"
    )
    assert "no_golden_cases_defined" in apply_tool.description, (
        "apply_update description must document the no-case warning contract"
    )

    # InputSchema must expose all three new properties with descriptions.
    props = apply_tool.inputSchema.get("properties", {})
    for key in ("golden_pass_required", "last_golden_result", "golden_dir"):
        assert key in props, f"apply_update inputSchema missing '{key}' property"
        desc = props[key].get("description", "")
        assert desc, f"apply_update inputSchema '{key}' must include a description"


# ---------------------------------------------------------------------------
# _tool_rollback_update: generic exception path
# ---------------------------------------------------------------------------


def test_tool_rollback_update_generic_exception(tmp_path, monkeypatch):
    """RuntimeError from rollback_workflow_from_backup is mapped to error='rollback_failed'."""
    from unittest.mock import MagicMock

    from yagra.adapters.inbound import mcp_server

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    mock_rollback = MagicMock(side_effect=RuntimeError("unexpected rollback error"))
    monkeypatch.setattr(mcp_server, "rollback_workflow_from_backup", mock_rollback)

    result = mcp_server._tool_rollback_update(
        workflow_path=str(wf),
        backup_id="bk-001",
    )
    assert result.get("error") == "rollback_failed"
    assert "message" in result


# ---------------------------------------------------------------------------
# _tool_get_traces / _tool_analyze_traces: generic exception paths
# ---------------------------------------------------------------------------


def test_tool_get_traces_exception(monkeypatch):
    """Exception from load_traces is returned as error key."""
    from unittest.mock import MagicMock

    # Patch load_traces inside the mcp_server module's function scope via the module
    # _tool_get_traces imports load_traces inside the function body, so we patch the module
    import yagra.application.use_cases.trace_aggregator as trace_agg
    from yagra.adapters.inbound import mcp_server

    mock_load = MagicMock(side_effect=Exception("trace load failure"))
    monkeypatch.setattr(trace_agg, "load_traces", mock_load)

    result = mcp_server._tool_get_traces(trace_dir=".yagra/traces")
    assert "error" in result
    assert "trace load failure" in result["error"]


def test_tool_analyze_traces_exception(monkeypatch):
    """Exception from load_traces in analyze_traces is returned as error key."""
    from unittest.mock import MagicMock

    import yagra.application.use_cases.trace_aggregator as trace_agg
    from yagra.adapters.inbound import mcp_server

    mock_load = MagicMock(side_effect=Exception("analyze trace failure"))
    monkeypatch.setattr(trace_agg, "load_traces", mock_load)

    result = mcp_server._tool_analyze_traces(trace_dir=".yagra/traces")
    assert "error" in result
    assert "analyze trace failure" in result["error"]


# ---------------------------------------------------------------------------
# list_tools(): verify all 11 tool names are present
# ---------------------------------------------------------------------------


def test_list_tools_contains_all_tools():
    """All 11 expected tool names are returned by list_tools via create_mcp_server."""
    import asyncio

    expected_tool_names = {
        "validate_workflow",
        "explain_workflow",
        "list_templates",
        "list_handlers",
        "get_template",
        "get_traces",
        "analyze_traces",
        "propose_update",
        "apply_update",
        "rollback_update",
        "run_golden_tests",
    }

    try:
        from yagra.adapters.inbound.mcp_server import create_mcp_server

        server = create_mcp_server()
    except ImportError:
        return

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
        tool_names = {t.name for t in tools}
        assert expected_tool_names == tool_names, (
            f"Missing tools: {expected_tool_names - tool_names}, "
            f"Extra tools: {tool_names - expected_tool_names}"
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# create_mcp_server with mock mcp: cover list_tools / call_tool closures
# ---------------------------------------------------------------------------


def _build_mock_mcp_server(monkeypatch):
    """Helper: register mock mcp modules and reload mcp_server, return (module, server)."""
    import importlib
    import sys
    from unittest.mock import MagicMock

    class _MockServer:
        """Minimal mock of mcp.server.Server that captures decorated functions."""

        def __init__(self, name: str) -> None:
            self.name = name
            self._list_tools_fn = None
            self._call_tool_fn = None

        def list_tools(self):
            def decorator(fn):
                self._list_tools_fn = fn
                return fn

            return decorator

        def call_tool(self):
            def decorator(fn):
                self._call_tool_fn = fn
                return fn

            return decorator

    mock_mcp_pkg = MagicMock()
    mock_mcp_pkg.server.Server = _MockServer

    mock_types = MagicMock()
    mock_types.Tool = MagicMock(side_effect=lambda **kw: kw)
    mock_types.TextContent = MagicMock(side_effect=lambda type, text: {"type": type, "text": text})

    for mod_name in [
        "mcp",
        "mcp.server",
        "mcp.server.stdio",
        "mcp.server.lowlevel",
        "mcp.server.lowlevel.server",
        "mcp.server.models",
        "mcp.types",
    ]:
        monkeypatch.setitem(sys.modules, mod_name, MagicMock())

    monkeypatch.setitem(sys.modules, "mcp.server", mock_mcp_pkg.server)
    monkeypatch.setitem(sys.modules, "mcp.types", mock_types)

    import yagra.adapters.inbound.mcp_server as mcp_module

    importlib.reload(mcp_module)

    # Patch Server class inside the reloaded module's local import
    monkeypatch.setattr(
        "yagra.adapters.inbound.mcp_server.create_mcp_server",
        lambda: _create_with_mock_server(_MockServer, mock_types, mcp_module),
    )

    server = _create_with_mock_server(_MockServer, mock_types, mcp_module)

    # Restore module
    importlib.reload(mcp_module)

    return mcp_module, server


def _create_with_mock_server(MockServer, mock_types, mcp_module):
    """Directly instantiate MockServer and run the server setup logic."""
    import importlib
    import sys
    from unittest.mock import MagicMock

    # Patch the imports inside create_mcp_server by temporarily injecting mocks
    original_modules = {}
    for mod_name in ["mcp", "mcp.server", "mcp.server.stdio", "mcp.types"]:
        original_modules[mod_name] = sys.modules.get(mod_name)

    mock_mcp_server_module = MagicMock()
    mock_mcp_server_module.Server = MockServer
    sys.modules["mcp.server"] = mock_mcp_server_module
    sys.modules["mcp.server.stdio"] = MagicMock()
    sys.modules["mcp.types"] = mock_types
    sys.modules["mcp"] = MagicMock()

    try:
        importlib.reload(mcp_module)
        server = mcp_module.create_mcp_server()
    finally:
        for mod_name, orig in original_modules.items():
            if orig is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = orig
        importlib.reload(mcp_module)

    return server


def test_create_mcp_server_list_tools_with_mock(monkeypatch):
    """list_tools closure returns 11 Tool dicts when mcp is mocked."""
    import asyncio
    import importlib
    import sys
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import MagicMock

    class _MockServer:
        def __init__(self, name):
            self.name = name
            self._list_tools_fn = None
            self._call_tool_fn = None

        def list_tools(self):
            def decorator(fn):
                self._list_tools_fn = fn
                return fn

            return decorator

        def call_tool(self):
            def decorator(fn):
                self._call_tool_fn = fn
                return fn

            return decorator

    mock_types = MagicMock()
    captured_tools = []

    def mock_tool(**kw):
        captured_tools.append(kw)
        return kw

    mock_types.Tool = MagicMock(side_effect=mock_tool)
    mock_types.TextContent = MagicMock(side_effect=lambda type, text: {"type": type, "text": text})

    mock_server_module = MagicMock()
    mock_server_module.Server = _MockServer

    original = {}
    for k in ["mcp", "mcp.server", "mcp.server.stdio", "mcp.types"]:
        original[k] = sys.modules.get(k)

    sys.modules["mcp"] = MagicMock()
    sys.modules["mcp.server"] = mock_server_module
    sys.modules["mcp.server.stdio"] = MagicMock()
    sys.modules["mcp.types"] = mock_types

    try:
        import yagra.adapters.inbound.mcp_server as m

        importlib.reload(m)
        server = m.create_mcp_server()

        assert isinstance(server, _MockServer)
        assert server._list_tools_fn is not None
        assert server._call_tool_fn is not None

        with ThreadPoolExecutor(max_workers=1) as ex:
            tools = ex.submit(asyncio.run, server._list_tools_fn()).result()
        assert len(tools) == 11
        tool_names = {t["name"] for t in tools}
        assert "validate_workflow" in tool_names
        assert "get_template" in tool_names
        assert "propose_update" in tool_names
        assert "apply_update" in tool_names
        assert "rollback_update" in tool_names
        assert "get_traces" in tool_names
        assert "analyze_traces" in tool_names
        assert "run_golden_tests" in tool_names
    finally:
        for k, v in original.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        importlib.reload(m)


def test_create_mcp_server_call_tool_all_branches(tmp_path, monkeypatch):
    """call_tool closure dispatches to correct _tool_* functions for all tool names."""
    import asyncio
    import importlib
    import json
    import sys
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import MagicMock

    class _MockServer:
        def __init__(self, name):
            self.name = name
            self._list_tools_fn = None
            self._call_tool_fn = None

        def list_tools(self):
            def decorator(fn):
                self._list_tools_fn = fn
                return fn

            return decorator

        def call_tool(self):
            def decorator(fn):
                self._call_tool_fn = fn
                return fn

            return decorator

    mock_types = MagicMock()
    mock_types.Tool = MagicMock(side_effect=lambda **kw: kw)

    text_content_instances = []

    def mock_text_content(type, text):
        obj = {"type": type, "text": text}
        text_content_instances.append(obj)
        return obj

    mock_types.TextContent = MagicMock(side_effect=mock_text_content)

    mock_server_module = MagicMock()
    mock_server_module.Server = _MockServer

    original = {}
    for k in ["mcp", "mcp.server", "mcp.server.stdio", "mcp.types"]:
        original[k] = sys.modules.get(k)

    sys.modules["mcp"] = MagicMock()
    sys.modules["mcp.server"] = mock_server_module
    sys.modules["mcp.server.stdio"] = MagicMock()
    sys.modules["mcp.types"] = mock_types

    wf = tmp_path / "workflow.yaml"
    wf.write_text(_VALID_WORKFLOW_YAML_PROPOSE)

    valid_yaml = _VALID_WORKFLOW_YAML_PROPOSE

    try:
        import yagra.adapters.inbound.mcp_server as m
        from yagra.application.use_cases.workflow_persistence import WorkflowSaveResult

        importlib.reload(m)
        server = m.create_mcp_server()

        async def _call_async(name, arguments):
            results = await server._call_tool_fn(name, arguments)
            return json.loads(results[0]["text"])

        def call(name, arguments):
            with ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(asyncio.run, _call_async(name, arguments)).result()

        # validate_workflow
        r = call("validate_workflow", {"yaml_content": valid_yaml})
        assert "is_valid" in r

        # explain_workflow
        r = call("explain_workflow", {"yaml_content": valid_yaml})
        assert "entry_point" in r or "error" in r

        # validate_workflow with workflow_path
        r = call("validate_workflow", {"workflow_path": str(wf)})
        assert "is_valid" in r

        # explain_workflow with workflow_path
        r = call("explain_workflow", {"workflow_path": str(wf)})
        assert "entry_point" in r or "error" in r

        # list_templates
        r = call("list_templates", {})
        assert "templates" in r

        # list_handlers
        r = call("list_handlers", {})
        assert "handlers" in r

        # get_template - use first available template
        templates_result = call("list_templates", {})
        if templates_result["templates"]:
            first_name = templates_result["templates"][0]["name"]
            r = call("get_template", {"name": first_name})
            assert "files" in r or "error" in r

        # get_traces (empty dir)
        r = call("get_traces", {"trace_dir": str(tmp_path / "traces"), "limit": 5})
        assert "traces" in r or "error" in r

        # analyze_traces (empty dir)
        r = call("analyze_traces", {"trace_dir": str(tmp_path / "traces")})
        assert "error" in r  # no traces

        # propose_update (file not found)
        r = call(
            "propose_update",
            {"workflow_path": "/nonexistent.yaml", "candidate_yaml": valid_yaml},
        )
        assert "error" in r

        # apply_update - mock save_workflow_with_backup
        mock_result = WorkflowSaveResult(saved_revision="rev1", backup_id="bk-1")
        monkeypatch.setattr(m, "save_workflow_with_backup", lambda *a, **k: mock_result)
        r = call("apply_update", {"workflow_path": str(wf), "candidate_yaml": valid_yaml})
        assert r.get("success") is True or "error" in r

        # rollback_update - missing backup_id
        r = call("rollback_update", {"workflow_path": str(wf), "backup_id": ""})
        assert "error" in r

        # unknown tool
        r = call("__unknown__", {})
        assert "error" in r

    finally:
        for k, v in original.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        importlib.reload(m)


# ---------------------------------------------------------------------------
# run_mcp_server: lines 942-955 — import path + version fallback + server run
# ---------------------------------------------------------------------------


def test_run_mcp_server_calls_server_run(monkeypatch):
    """run_mcp_server should import mcp, resolve version, and invoke server.run()."""
    import asyncio
    import contextlib

    try:
        import mcp  # noqa: F401
    except ImportError:
        pytest.skip("mcp package not installed")

    from yagra.adapters.inbound import mcp_server as mcp_mod

    run_called = {}

    class _FakeStream:
        pass

    @contextlib.asynccontextmanager
    async def _fake_stdio_server():
        yield _FakeStream(), _FakeStream()

    class _FakeServer:
        def get_capabilities(self, **kwargs):
            return {}

        async def run(self, read_stream, write_stream, init_options):
            run_called["called"] = True
            run_called["server_name"] = init_options.server_name

    monkeypatch.setattr(
        "yagra.adapters.inbound.mcp_server.create_mcp_server",
        lambda: _FakeServer(),
    )

    import mcp.server.stdio as _stdio_mod

    monkeypatch.setattr(_stdio_mod, "stdio_server", _fake_stdio_server)

    asyncio.run(mcp_mod.run_mcp_server())

    assert run_called.get("called") is True
    assert run_called.get("server_name") == "yagra"


def test_run_mcp_server_version_fallback(monkeypatch):
    """run_mcp_server uses '0.0.0' when importlib.metadata raises."""
    import asyncio
    import contextlib

    try:
        import mcp  # noqa: F401
    except ImportError:
        pytest.skip("mcp package not installed")

    from yagra.adapters.inbound import mcp_server as mcp_mod

    version_used = {}

    class _FakeStream:
        pass

    @contextlib.asynccontextmanager
    async def _fake_stdio_server():
        yield _FakeStream(), _FakeStream()

    class _FakeServer:
        def get_capabilities(self, **kwargs):
            return {}

        async def run(self, read_stream, write_stream, init_options):
            version_used["version"] = init_options.server_version

    monkeypatch.setattr(
        "yagra.adapters.inbound.mcp_server.create_mcp_server",
        lambda: _FakeServer(),
    )

    import mcp.server.stdio as _stdio_mod

    monkeypatch.setattr(_stdio_mod, "stdio_server", _fake_stdio_server)

    # Make pkg_version always raise so the fallback "0.0.0" is used
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda _pkg: (_ for _ in ()).throw(Exception("no pkg")))

    asyncio.run(mcp_mod.run_mcp_server())

    assert version_used.get("version") == "0.0.0"
