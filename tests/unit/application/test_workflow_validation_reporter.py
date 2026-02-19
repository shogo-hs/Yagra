from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from yagra.application.use_cases import (
    WorkflowValidationFailedError,
    format_validation_report,
    load_validated_graph_spec,
    validate_workflow_for_ui,
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
    del payload["edges"]
    workflow_path = _write_workflow(tmp_path / "schema-error.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    assert any(issue.code == "schema_error" for issue in report.issues)
    assert any(issue.location == ("edges",) for issue in report.issues)


def test_validate_workflow_for_ui_accepts_single_node_without_edges(tmp_path: Path) -> None:
    payload = {
        "version": "1.0",
        "start_at": "only",
        "end_at": ["only"],
        "nodes": [
            {"id": "only", "handler": "only_handler"},
        ],
        "edges": [],
        "params": {},
    }
    workflow_path = _write_workflow(tmp_path / "single-node.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is True
    assert report.issues == []


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


def test_load_validated_graph_spec_returns_graph_spec() -> None:
    spec = load_validated_graph_spec(WORKFLOW_ROOT / "branch-inline.yaml")

    assert spec.start_at == "router"
    assert len(spec.nodes) == 3


def test_load_validated_graph_spec_raises_workflow_validation_failed_error(
    tmp_path: Path,
) -> None:
    payload = _base_payload()
    del payload["edges"]
    workflow_path = _write_workflow(tmp_path / "invalid.yaml", payload)

    with pytest.raises(WorkflowValidationFailedError) as exc:
        load_validated_graph_spec(workflow_path)

    report = exc.value.report
    assert report.is_valid is False
    assert any(issue.code == "schema_error" for issue in report.issues)
    assert "workflow validation failed" in format_validation_report(report)


def test_load_validated_graph_spec_accepts_inline_model_mapping(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["nodes"][1]["params"] = {
        "model": {
            "provider": "openai",
            "name": "gpt-4.1-mini",
            "temperature": 0.7,
            "max_tokens": 512,
        },
    }
    workflow_path = _write_workflow(tmp_path / "model-inline.yaml", payload)

    spec = load_validated_graph_spec(workflow_path)

    planner_node = next(node for node in spec.nodes if node.id == "planner")
    model = planner_node.params["model"]
    assert model["provider"] == "openai"
    assert model["name"] == "gpt-4.1-mini"
    assert model["temperature"] == 0.7
    assert model["max_tokens"] == 512


def test_load_validated_graph_spec_rejects_inline_prompt(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["params"] = {}
    payload["nodes"][1]["params"] = {
        "prompt": {
            "system": "You are planner.",
            "user": "Create a plan.",
        },
    }
    workflow_path = _write_workflow(tmp_path / "inline-prompt.yaml", payload)

    with pytest.raises(WorkflowValidationFailedError) as exc:
        load_validated_graph_spec(workflow_path)

    report = exc.value.report
    assert report.is_valid is False
    assert any(issue.code == "reference_error" for issue in report.issues)
    assert any(issue.location == ("nodes", 1, "params", "prompt") for issue in report.issues)


def test_load_validated_graph_spec_resolves_workspace_relative_prompt_ref_without_bundle_root(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workflow_path = workspace_root / "workflows" / "main.yaml"
    prompt_path = workspace_root / "prompts" / "catalog.yaml"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(
        yaml.safe_dump(
            {
                "intent": {
                    "system": "Classify intent.",
                    "user": "{{input}}",
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    payload = _base_payload()
    payload["nodes"][1]["params"] = {
        "prompt_ref": "prompts/catalog.yaml#intent",
    }
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    _write_workflow(workflow_path, payload)

    spec = load_validated_graph_spec(workflow_path)

    planner_node = next(node for node in spec.nodes if node.id == "planner")
    prompt = planner_node.params["prompt"]
    assert prompt["system"] == "Classify intent."
    assert prompt["user"] == "{{input}}"


def test_validate_workflow_for_ui_reports_error_when_model_ref_is_used(
    tmp_path: Path,
) -> None:
    payload = _base_payload()
    payload["nodes"][1]["params"] = {
        "model_ref": "default",
    }
    workflow_path = _write_workflow(tmp_path / "model-ref-unsupported.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    issue = report.issues[0]
    assert issue.code == "reference_error"
    assert issue.location == ("nodes", 1, "params", "model_ref")


def test_validate_workflow_for_ui_reports_error_when_inline_prompt_is_used(
    tmp_path: Path,
) -> None:
    payload = _base_payload()
    payload["params"] = {}
    payload["nodes"][1]["params"] = {
        "prompt": {"system": "inline prompt"},
    }
    workflow_path = _write_workflow(tmp_path / "inline-prompt-error.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    issue = report.issues[0]
    assert issue.code == "reference_error"
    assert issue.location == ("nodes", 1, "params", "prompt")


# --- severity / context / fuzzy match tests ---

VALID_SPEC_DICT: dict[str, Any] = {
    "version": "1",
    "start_at": "translate",
    "end_at": ["translate"],
    "nodes": [{"id": "translate", "handler": "llm", "params": {}}],
    "edges": [],
}


def test_workflow_validation_issue_default_severity_is_error() -> None:
    issue = __import__(
        "yagra.application.use_cases.workflow_validation_reporter",
        fromlist=["WorkflowValidationIssue"],
    ).WorkflowValidationIssue(code="test", message="msg")

    assert issue.severity == "error"


def test_workflow_validation_issue_to_dict_contains_severity() -> None:
    from yagra.application.use_cases.workflow_validation_reporter import WorkflowValidationIssue

    issue = WorkflowValidationIssue(code="test", message="msg", severity="warning")
    d = issue.to_dict()

    assert d["severity"] == "warning"


def test_workflow_validation_issue_to_dict_excludes_context_when_none() -> None:
    from yagra.application.use_cases.workflow_validation_reporter import WorkflowValidationIssue

    issue = WorkflowValidationIssue(code="test", message="msg")
    d = issue.to_dict()

    assert "context" not in d


def test_workflow_validation_issue_to_dict_includes_context_when_set() -> None:
    from yagra.application.use_cases.workflow_validation_reporter import WorkflowValidationIssue

    ctx = {"actual_value": "foo", "suggestion": "bar"}
    issue = WorkflowValidationIssue(code="test", message="msg", context=ctx)
    d = issue.to_dict()

    assert d["context"] == ctx


def test_validate_workflow_structure_error_context_has_suggestion(tmp_path: Path) -> None:
    """Should return a suggestion in context.suggestion when the node ID has one character changed."""
    payload: dict[str, Any] = {
        "version": "1",
        "start_at": "translat",  # one character missing
        "end_at": ["translate"],
        "nodes": [{"id": "translate", "handler": "llm", "params": {}}],
        "edges": [],
    }
    workflow_path = _write_workflow(tmp_path / "fuzzy-start-at.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    structure_issues = [i for i in report.issues if i.code == "structure_error"]
    assert len(structure_issues) == 1
    issue = structure_issues[0]
    assert issue.location == ("start_at",)
    assert issue.context is not None
    assert issue.context["suggestion"] == "translate"
