from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yagra.application.use_cases.workflow_edit_session import load_workflow_edit_session
from yagra.application.use_cases.workflow_form_model import (
    build_workflow_catalog_preview,
    build_workflow_form_view,
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
            {
                "id": "planner",
                "handler": "planner_handler",
                "params": {
                    "prompt": {"system": "You are planner.", "user": "Create a plan."},
                    "model": {"provider": "openai", "name": "gpt-4.1-mini"},
                },
            },
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "router", "target": "planner", "condition": "needs_plan"},
            {"source": "planner", "target": "finish"},
        ],
        "params": {},
    }


def _write_workflow(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_build_workflow_form_view_includes_catalog_keys_and_refs() -> None:
    workflow_path = WORKFLOW_ROOT / "loop-split.yaml"
    session = load_workflow_edit_session(workflow_path=workflow_path, bundle_root=FIXTURES_ROOT)

    view = build_workflow_form_view(
        workflow=session.workflow,
        ui_state=session.ui_state,
        workflow_path=workflow_path,
        bundle_root=FIXTURES_ROOT,
    )

    assert view.revision == session.revision
    assert len(view.nodes) == 3
    planner = next(item for item in view.nodes if item.id == "planner")
    assert planner.prompt_ref == "planner"
    assert planner.model_ref == "default"
    assert "planner" in view.prompt_catalog_keys
    assert "default" in view.model_catalog_keys

    assert len(view.edges) == 3
    retry_edge = next(item for item in view.edges if item.condition == "retry")
    assert retry_edge.source == "evaluator"
    assert retry_edge.target == "planner"


def test_build_workflow_form_view_handles_inline_prompt_and_model(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "inline.yaml", _base_payload())
    session = load_workflow_edit_session(workflow_path=workflow_path)

    view = build_workflow_form_view(
        workflow=session.workflow,
        ui_state=session.ui_state,
        workflow_path=workflow_path,
    )

    planner = next(item for item in view.nodes if item.id == "planner")
    assert planner.prompt_ref is None
    assert planner.model_ref is None
    assert planner.prompt == {"system": "You are planner.", "user": "Create a plan."}
    assert planner.model == {"provider": "openai", "name": "gpt-4.1-mini"}
    assert view.prompt_catalog_keys == ()
    assert view.model_catalog_keys == ()


def test_build_workflow_form_view_allows_missing_nodes_and_edges(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "empty.yaml", {})
    session = load_workflow_edit_session(workflow_path=workflow_path)

    view = build_workflow_form_view(
        workflow=session.workflow,
        ui_state=session.ui_state,
        workflow_path=workflow_path,
    )

    assert view.revision == session.revision
    assert view.nodes == ()
    assert view.edges == ()


def test_build_workflow_catalog_preview_collects_keys() -> None:
    workflow_path = WORKFLOW_ROOT / "loop-split.yaml"
    session = load_workflow_edit_session(workflow_path=workflow_path, bundle_root=FIXTURES_ROOT)

    preview = build_workflow_catalog_preview(
        workflow=session.workflow,
        workflow_path=workflow_path,
        bundle_root=FIXTURES_ROOT,
    )

    assert preview.prompt_catalog_path is not None
    assert preview.model_catalog_path is not None
    assert "planner" in preview.prompt_catalog_keys
    assert "default" in preview.model_catalog_keys
    assert preview.issues == ()


def test_build_workflow_catalog_preview_reports_missing_and_invalid_catalogs(
    tmp_path: Path,
) -> None:
    payload = _base_payload()
    payload["params"] = {
        "prompt_catalog": "prompts/missing.yaml",
        "model_catalog": 123,
    }
    workflow_path = _write_workflow(tmp_path / "catalog-preview-error.yaml", payload)

    preview = build_workflow_catalog_preview(
        workflow=payload,
        workflow_path=workflow_path,
    )

    issue_codes = {issue.code for issue in preview.issues}
    assert "catalog_not_found" in issue_codes
    assert "catalog_path_type_error" in issue_codes
