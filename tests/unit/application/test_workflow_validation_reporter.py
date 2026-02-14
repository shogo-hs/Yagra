from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yagra.application.use_cases import validate_workflow_for_ui

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


def test_validate_workflow_for_ui_reports_valid_fixture() -> None:
    report = validate_workflow_for_ui(WORKFLOW_ROOT / "branch-inline.yaml")

    assert report.is_valid is True
    assert report.issues == []


def test_validate_workflow_for_ui_reports_reference_error_with_location(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["nodes"][1]["params"] = {"prompt_ref": "planner"}
    workflow_path = _write_workflow(tmp_path / "reference-error.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert issue.code == "reference_error"
    assert issue.location == ("nodes", 1, "params", "prompt_ref")


def test_validate_workflow_for_ui_reports_schema_error_with_location(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["edges"] = []
    workflow_path = _write_workflow(tmp_path / "schema-error.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    assert any(issue.code == "schema_error" for issue in report.issues)
    assert any(issue.location == ("edges",) for issue in report.issues)


def test_validate_workflow_for_ui_reports_structure_error_with_location(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["edges"][1]["target"] = "unknown_finish"
    workflow_path = _write_workflow(tmp_path / "structure-error.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert issue.code == "structure_error"
    assert issue.location == ("edges", 1, "target")


def test_validate_workflow_for_ui_reports_edge_rule_error_with_locations(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["edges"] = [
        {"source": "router", "target": "planner"},
        {"source": "router", "target": "finish", "condition": "done"},
        {"source": "planner", "target": "finish"},
    ]
    workflow_path = _write_workflow(tmp_path / "edge-rule-error.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    edge_rule_issues = [issue for issue in report.issues if issue.code == "edge_rule_error"]
    assert len(edge_rule_issues) == 2
    assert {issue.location for issue in edge_rule_issues} == {
        ("edges", 0),
        ("edges", 1, "condition"),
    }
