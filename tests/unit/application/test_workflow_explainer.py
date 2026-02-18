"""Tests for workflow_explainer."""

from yagra.application.use_cases.workflow_explainer import explain_workflow
from yagra.domain.entities.graph_schema import GraphSpec


def _make_spec(overrides: dict) -> GraphSpec:
    base = {
        "version": "1",
        "start_at": "node_a",
        "end_at": ["node_a"],
        "nodes": [{"id": "node_a", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "hello"}}],
        "edges": [],
    }
    base.update(overrides)
    return GraphSpec.model_validate(base)


def test_explain_entry_and_exit():
    spec = _make_spec({})
    result = explain_workflow(spec)
    assert result["entry_point"] == "node_a"
    assert result["exit_points"] == ["node_a"]


def test_explain_required_handlers():
    spec = _make_spec({})
    result = explain_workflow(spec)
    assert "llm" in result["required_handlers"]


def test_explain_variable_flow_extracts_prompt_vars():
    spec = _make_spec({
        "nodes": [{"id": "node_a", "handler": "llm", "params": {
            "model": "gpt-4o-mini",
            "prompt": "translate {text} to {lang}",
            "output_key": "translation",
        }}],
    })
    result = explain_workflow(spec)
    assert result["variable_flow"]["node_a"]["inputs"] == ["text", "lang"]
    assert "translation" in result["variable_flow"]["node_a"]["outputs"]


def test_explain_conditional_node_has_next_in_outputs():
    spec = GraphSpec.model_validate({
        "version": "1",
        "start_at": "classify",
        "end_at": ["approve", "reject"],
        "nodes": [
            {"id": "classify", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "classify {input}"}},
            {"id": "approve", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "approved"}},
            {"id": "reject", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "rejected"}},
        ],
        "edges": [
            {"source": "classify", "target": "approve", "condition": "approved"},
            {"source": "classify", "target": "reject", "condition": "rejected"},
        ],
    })
    result = explain_workflow(spec)
    assert "__next__" in result["variable_flow"]["classify"]["outputs"]


def test_explain_execution_paths_linear():
    spec = GraphSpec.model_validate({
        "version": "1",
        "start_at": "a",
        "end_at": ["b"],
        "nodes": [
            {"id": "a", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "x"}},
            {"id": "b", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "y"}},
        ],
        "edges": [{"source": "a", "target": "b"}],
    })
    result = explain_workflow(spec)
    assert result["execution_paths"] == [["a", "b"]]


def test_explain_execution_paths_branch():
    spec = GraphSpec.model_validate({
        "version": "1",
        "start_at": "classify",
        "end_at": ["approve", "reject"],
        "nodes": [
            {"id": "classify", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "c"}},
            {"id": "approve", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "a"}},
            {"id": "reject", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "r"}},
        ],
        "edges": [
            {"source": "classify", "target": "approve", "condition": "approved"},
            {"source": "classify", "target": "reject", "condition": "rejected"},
        ],
    })
    result = explain_workflow(spec)
    paths = result["execution_paths"]
    assert ["classify", "approve"] in paths
    assert ["classify", "reject"] in paths
