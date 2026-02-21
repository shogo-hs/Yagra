"""Unit tests for Yagra public trace API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from yagra import Yagra
from yagra.domain.entities.trace import WorkflowRunTrace


def _write_minimal_workflow(path: Path) -> Path:
    payload = {
        "version": "1.0",
        "start_at": "step_a",
        "end_at": ["step_b"],
        "nodes": [
            {"id": "step_a", "handler": "handler_a"},
            {"id": "step_b", "handler": "handler_b"},
        ],
        "edges": [{"source": "step_a", "target": "step_b"}],
        "params": {},
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _make_registry() -> dict[str, Any]:
    def _handler_a(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        return {"step_a_value": state.get("value")}

    def _handler_b(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        return {"result": state.get("step_a_value")}

    return {
        "handler_a": _handler_a,
        "handler_b": _handler_b,
    }


def test_get_last_trace_returns_none_when_observability_disabled(tmp_path: Path) -> None:
    workflow_path = _write_minimal_workflow(tmp_path / "workflow.yaml")
    yagra = Yagra.from_workflow(
        workflow_path=workflow_path,
        registry=_make_registry(),
        observability=False,
    )

    assert yagra.get_last_trace() is None
    yagra.invoke({"value": "disabled"}, trace=False)
    assert yagra.get_last_trace() is None


def test_get_last_trace_returns_none_before_first_invoke(tmp_path: Path) -> None:
    workflow_path = _write_minimal_workflow(tmp_path / "workflow.yaml")
    yagra = Yagra.from_workflow(
        workflow_path=workflow_path,
        registry=_make_registry(),
        observability=True,
    )

    assert yagra.get_last_trace() is None


def test_get_last_trace_available_after_invoke_with_trace_false(tmp_path: Path) -> None:
    workflow_path = _write_minimal_workflow(tmp_path / "workflow.yaml")
    yagra = Yagra.from_workflow(
        workflow_path=workflow_path,
        registry=_make_registry(),
        observability=True,
    )

    yagra.invoke({"value": "alpha"}, trace=False)
    trace = yagra.get_last_trace()

    assert isinstance(trace, WorkflowRunTrace)
    assert [node.node_id for node in trace.nodes] == ["step_a", "step_b"]


def test_get_last_trace_available_after_invoke_with_trace_true(tmp_path: Path) -> None:
    workflow_path = _write_minimal_workflow(tmp_path / "workflow.yaml")
    yagra = Yagra.from_workflow(
        workflow_path=workflow_path,
        registry=_make_registry(),
        observability=True,
    )
    trace_dir = tmp_path / "traces"

    with pytest.warns(UserWarning, match=r"\[yagra\] trace written to:"):
        yagra.invoke({"value": "beta"}, trace=True, trace_dir=trace_dir)

    trace = yagra.get_last_trace()
    assert isinstance(trace, WorkflowRunTrace)
    assert list(trace_dir.glob("**/*.json"))


def test_get_last_trace_is_overwritten_by_latest_invoke(tmp_path: Path) -> None:
    workflow_path = _write_minimal_workflow(tmp_path / "workflow.yaml")
    yagra = Yagra.from_workflow(
        workflow_path=workflow_path,
        registry=_make_registry(),
        observability=True,
    )

    yagra.invoke({"value": "first"}, trace=False)
    first_trace = yagra.get_last_trace()
    assert isinstance(first_trace, WorkflowRunTrace)
    assert first_trace.nodes[0].input_snapshot["value"] == "first"

    yagra.invoke({"value": "second"}, trace=False)
    second_trace = yagra.get_last_trace()
    assert isinstance(second_trace, WorkflowRunTrace)
    assert second_trace.nodes[0].input_snapshot["value"] == "second"
    assert second_trace is not first_trace
