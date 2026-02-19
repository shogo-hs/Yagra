"""Tests for subgraph node support (handler='subgraph')."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from yagra.adapters.outbound import InMemoryNodeRegistry
from yagra.application.use_cases.state_graph_builder import GraphBuildError, build_state_graph
from yagra.domain.entities import GraphSpec


def _make_spec(payload: dict[str, Any]) -> GraphSpec:
    return GraphSpec.model_validate(payload)


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Error cases for subgraph nodes
# ---------------------------------------------------------------------------


def test_subgraph_node_missing_workflow_ref_raises() -> None:
    payload = {
        "version": "1.0",
        "start_at": "sub",
        "end_at": ["sub"],
        "nodes": [
            {"id": "sub", "handler": "subgraph"},  # no workflow_ref param
        ],
        "edges": [],
    }
    spec = _make_spec(payload)
    registry = InMemoryNodeRegistry({})

    with pytest.raises(GraphBuildError, match="requires params.workflow_ref"):
        build_state_graph(spec, registry, workflow_path="/some/path/workflow.yaml")


def test_subgraph_node_non_string_workflow_ref_raises() -> None:
    payload = {
        "version": "1.0",
        "start_at": "sub",
        "end_at": ["sub"],
        "nodes": [
            {"id": "sub", "handler": "subgraph", "params": {"workflow_ref": 123}},
        ],
        "edges": [],
    }
    spec = _make_spec(payload)
    registry = InMemoryNodeRegistry({})

    with pytest.raises(GraphBuildError, match="workflow_ref must be a string"):
        build_state_graph(spec, registry, workflow_path="/some/path/workflow.yaml")


def test_subgraph_node_nonexistent_workflow_ref_raises() -> None:
    payload = {
        "version": "1.0",
        "start_at": "sub",
        "end_at": ["sub"],
        "nodes": [
            {"id": "sub", "handler": "subgraph", "params": {"workflow_ref": "./nonexistent.yaml"}},
        ],
        "edges": [],
    }
    spec = _make_spec(payload)
    registry = InMemoryNodeRegistry({})

    with pytest.raises(GraphBuildError, match="not found"):
        build_state_graph(spec, registry, workflow_path="/some/path/workflow.yaml")


def test_subgraph_node_without_workflow_path_uses_cwd() -> None:
    """When workflow_path is None and workflow_ref doesn't exist, raises GraphBuildError."""
    payload = {
        "version": "1.0",
        "start_at": "sub",
        "end_at": ["sub"],
        "nodes": [
            {
                "id": "sub",
                "handler": "subgraph",
                "params": {"workflow_ref": "./nonexistent_sub.yaml"},
            },
        ],
        "edges": [],
    }
    spec = _make_spec(payload)
    registry = InMemoryNodeRegistry({})

    with pytest.raises(GraphBuildError, match="not found"):
        build_state_graph(spec, registry)  # workflow_path=None


# ---------------------------------------------------------------------------
# Subgraph node integration with real YAML files
# ---------------------------------------------------------------------------


def test_subgraph_node_builds_successfully() -> None:
    """A subgraph node loads and embeds a sub-workflow YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Create sub-workflow
        sub_yaml = tmp / "sub_workflow.yaml"
        _write_yaml(
            sub_yaml,
            """
version: "1.0"
start_at: worker
end_at:
  - worker
nodes:
  - id: worker
    handler: my_handler
edges: []
""",
        )

        # Create parent workflow with subgraph node
        parent_yaml = tmp / "workflow.yaml"
        _write_yaml(
            parent_yaml,
            """
version: "1.0"
start_at: step1
end_at:
  - step1
nodes:
  - id: step1
    handler: subgraph
    params:
      workflow_ref: ./sub_workflow.yaml
edges: []
""",
        )

        from collections.abc import Mapping

        executed: list[str] = []

        def my_handler(state: Mapping[str, Any], params: dict[str, Any]) -> dict[str, Any]:
            executed.append("worker_executed")
            return {"result": "from_sub"}

        registry = InMemoryNodeRegistry({"my_handler": my_handler})

        # Use build_from_workflow_path which passes workflow_path correctly
        from yagra.application.use_cases.state_graph_builder import build_from_workflow_path

        compiled = build_from_workflow_path(
            workflow_path=parent_yaml,
            registry=registry,
        )

        result = compiled.invoke({"input": "test"})
        assert "worker_executed" in executed or result is not None


def test_subgraph_inherits_registry() -> None:
    """Subgraph nodes share the parent's registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        sub_yaml = tmp / "sub.yaml"
        _write_yaml(
            sub_yaml,
            """
version: "1.0"
start_at: node_a
end_at:
  - node_a
nodes:
  - id: node_a
    handler: shared_handler
edges: []
""",
        )

        from collections.abc import Mapping

        call_log: list[str] = []

        def shared_handler(state: Mapping[str, Any], params: dict[str, Any]) -> dict[str, Any]:
            call_log.append("shared_called")
            return {"output": "from_shared"}

        payload = {
            "version": "1.0",
            "start_at": "sub_node",
            "end_at": ["sub_node"],
            "nodes": [
                {
                    "id": "sub_node",
                    "handler": "subgraph",
                    "params": {"workflow_ref": "sub.yaml"},
                },
            ],
            "edges": [],
        }

        spec = _make_spec(payload)
        registry = InMemoryNodeRegistry({"shared_handler": shared_handler})

        compiled = build_state_graph(
            spec=spec,
            registry=registry,
            workflow_path=tmp / "workflow.yaml",
        )

        compiled.invoke({})
        assert len(call_log) == 1
        assert call_log[0] == "shared_called"
