from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from yagra.application.use_cases.workflow_visualization import (
    build_workflow_visualization_view,
    render_workflow_visualization_html,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures"
WORKFLOW_ROOT = FIXTURES_ROOT / "workflows"


def _base_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["finish"],
        "nodes": [
            {"id": "router", "handler": "router_handler"},
            {"id": "planner", "handler": "planner_handler"},
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "router", "target": "planner"},
            {"source": "planner", "target": "finish"},
        ],
    }


def _write_workflow(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_build_workflow_visualization_view_includes_resolved_model_and_prompt() -> None:
    view = build_workflow_visualization_view(
        WORKFLOW_ROOT / "loop-split.yaml",
        bundle_root=FIXTURES_ROOT,
    )

    assert view.start_at == "planner"
    assert view.end_at == ("finish",)
    assert any(node.id == "planner" for node in view.nodes)

    planner_node = next(node for node in view.nodes if node.id == "planner")
    assert "planner_loop_handler" in planner_node.handler
    assert "You are planner." in planner_node.params_json
    assert "gpt-4.1-mini" in planner_node.params_json


def test_render_workflow_visualization_html_contains_graph_and_node_details() -> None:
    html_text = render_workflow_visualization_html(
        WORKFLOW_ROOT / "branch-inline.yaml", title="Demo"
    )

    assert "Read Only" in html_text
    assert "flowchart LR" in html_text
    assert "router" in html_text
    assert "planner_handler" in html_text
    assert "needs_plan" in html_text
    assert "https://cdn.jsdelivr.net" not in html_text
    assert "import mermaid from" not in html_text
    assert "window.__esbuild_esm_mermaid_nm" in html_text


def test_render_workflow_visualization_html_raises_on_invalid_workflow(tmp_path: Path) -> None:
    payload = _base_payload()
    del payload["edges"]
    workflow_path = _write_workflow(tmp_path / "invalid.yaml", payload)

    with pytest.raises(ValueError, match="workflow validation failed"):
        render_workflow_visualization_html(workflow_path)


def test_build_workflow_visualization_view_fan_out_edge_is_marked(tmp_path: Path) -> None:
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "prepare",
        "end_at": ["aggregate"],
        "state_schema": {
            "items": {"type": "list"},
            "results": {"type": "list", "reducer": "add"},
        },
        "nodes": [
            {"id": "prepare", "handler": "prepare_handler"},
            {"id": "process_item", "handler": "process_handler"},
            {"id": "aggregate", "handler": "aggregate_handler"},
        ],
        "edges": [
            {
                "source": "prepare",
                "target": "process_item",
                "fan_out": {"items_key": "items", "item_key": "item"},
            },
            {"source": "process_item", "target": "aggregate"},
        ],
    }
    workflow_path = _write_workflow(tmp_path / "fan-out.yaml", payload)

    view = build_workflow_visualization_view(workflow_path)

    fan_out_edge = next(e for e in view.edges if e.source == "prepare")
    normal_edge = next(e for e in view.edges if e.source == "process_item")
    assert fan_out_edge.is_fan_out is True
    assert fan_out_edge.condition is None
    assert normal_edge.is_fan_out is False


def test_render_workflow_visualization_html_fan_out_label_shown(tmp_path: Path) -> None:
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "prepare",
        "end_at": ["aggregate"],
        "state_schema": {
            "items": {"type": "list"},
            "results": {"type": "list", "reducer": "add"},
        },
        "nodes": [
            {"id": "prepare", "handler": "prepare_handler"},
            {"id": "process_item", "handler": "process_handler"},
            {"id": "aggregate", "handler": "aggregate_handler"},
        ],
        "edges": [
            {
                "source": "prepare",
                "target": "process_item",
                "fan_out": {"items_key": "items", "item_key": "item"},
            },
            {"source": "process_item", "target": "aggregate"},
        ],
    }
    workflow_path = _write_workflow(tmp_path / "fan-out.yaml", payload)

    html_text = render_workflow_visualization_html(workflow_path)

    # Mermaid graph is HTML-escaped when embedded (both quotes and arrows are escaped)
    assert "prepare -- &quot;fan-out&quot; --&gt; process_item" in html_text
    assert ">fan-out<" in html_text
