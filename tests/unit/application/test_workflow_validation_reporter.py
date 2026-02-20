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


def test_validate_workflow_for_ui_accepts_fan_out_edge(tmp_path: Path) -> None:
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

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is True
    assert report.issues == []


def test_validate_workflow_for_ui_reports_fan_out_conflict_with_normal_edge(tmp_path: Path) -> None:
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["finish"],
        "state_schema": {
            "items": {"type": "list"},
            "results": {"type": "list", "reducer": "add"},
        },
        "nodes": [
            {"id": "router", "handler": "router_handler"},
            {"id": "process_item", "handler": "process_handler"},
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "router", "target": "finish"},  # normal edge
            {
                "source": "router",
                "target": "process_item",
                "fan_out": {"items_key": "items", "item_key": "item"},
            },  # fan_out edge: conflict
        ],
    }
    workflow_path = _write_workflow(tmp_path / "fan-out-conflict.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    edge_rule_issues = [issue for issue in report.issues if issue.code == "edge_rule_error"]
    assert len(edge_rule_issues) == 2
    locations = {issue.location for issue in edge_rule_issues}
    assert ("edges", 0) in locations
    assert ("edges", 1, "fan_out") in locations


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


# ---------------------------------------------------------------------------
# handler_compatibility_error: structured_llm / streaming_llm as branch source
# ---------------------------------------------------------------------------


def test_validate_workflow_reports_structured_llm_as_branch_source(tmp_path: Path) -> None:
    """structured_llm node used as conditional branch source should produce an error."""
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "extractor",
        "end_at": ["yes_path", "no_path"],
        "nodes": [
            {"id": "extractor", "handler": "structured_llm", "params": {}},
            {"id": "yes_path", "handler": "yes_handler"},
            {"id": "no_path", "handler": "no_handler"},
        ],
        "edges": [
            {"source": "extractor", "target": "yes_path", "condition": "yes"},
            {"source": "extractor", "target": "no_path", "condition": "no"},
        ],
    }
    workflow_path = _write_workflow(tmp_path / "structured-branch.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    compat_issues = [i for i in report.issues if i.code == "handler_compatibility_error"]
    assert len(compat_issues) == 1
    issue = compat_issues[0]
    assert issue.location == ("nodes", 0, "handler")
    assert "extractor" in issue.message
    assert "structured_llm" in issue.message
    assert "__next__" in issue.message
    assert issue.context is not None
    assert issue.context["node_id"] == "extractor"
    assert issue.context["handler"] == "structured_llm"
    assert "suggestion" in issue.context


def test_validate_workflow_reports_streaming_llm_as_branch_source(tmp_path: Path) -> None:
    """streaming_llm node used as conditional branch source should produce an error."""
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "streamer",
        "end_at": ["done"],
        "nodes": [
            {
                "id": "streamer",
                "handler": "streaming_llm",
                "params": {"output_key": "chunks"},
            },
            {"id": "done", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "streamer", "target": "done", "condition": "ok"},
        ],
    }
    workflow_path = _write_workflow(tmp_path / "streaming-branch.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    assert report.is_valid is False
    compat_issues = [i for i in report.issues if i.code == "handler_compatibility_error"]
    assert len(compat_issues) == 1
    issue = compat_issues[0]
    assert issue.context is not None
    assert issue.context["output_key"] == "chunks"


def test_validate_workflow_llm_handler_as_branch_source_is_valid(tmp_path: Path) -> None:
    """The llm (basic text handler) as conditional branch source should NOT raise an error."""
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "classifier",
        "end_at": ["path_a", "path_b"],
        "nodes": [
            {"id": "classifier", "handler": "llm", "params": {}},
            {"id": "path_a", "handler": "handler_a"},
            {"id": "path_b", "handler": "handler_b"},
        ],
        "edges": [
            {"source": "classifier", "target": "path_a", "condition": "a"},
            {"source": "classifier", "target": "path_b", "condition": "b"},
        ],
    }
    workflow_path = _write_workflow(tmp_path / "llm-branch.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    compat_issues = [i for i in report.issues if i.code == "handler_compatibility_error"]
    assert len(compat_issues) == 0


def test_validate_workflow_custom_handler_as_branch_source_is_valid(tmp_path: Path) -> None:
    """Custom handler as conditional branch source should not raise an error."""
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["finish"],
        "nodes": [
            {"id": "router", "handler": "my_router"},
            {"id": "path_a", "handler": "handler_a"},
            {"id": "path_b", "handler": "handler_b"},
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "router", "target": "path_a", "condition": "a"},
            {"source": "router", "target": "path_b", "condition": "b"},
            {"source": "path_a", "target": "finish"},
            {"source": "path_b", "target": "finish"},
        ],
    }
    workflow_path = _write_workflow(tmp_path / "custom-branch.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    compat_issues = [i for i in report.issues if i.code == "handler_compatibility_error"]
    assert len(compat_issues) == 0


def test_validate_workflow_structured_llm_without_branch_is_valid(tmp_path: Path) -> None:
    """structured_llm with only normal (non-conditional) edges should not raise an error."""
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "extractor",
        "end_at": ["finish"],
        "nodes": [
            {"id": "extractor", "handler": "structured_llm", "params": {}},
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "extractor", "target": "finish"},
        ],
    }
    workflow_path = _write_workflow(tmp_path / "structured-no-branch.yaml", payload)

    report = validate_workflow_for_ui(workflow_path)

    compat_issues = [i for i in report.issues if i.code == "handler_compatibility_error"]
    assert len(compat_issues) == 0


# ---------------------------------------------------------------------------
# load_validated_graph_spec: line 110 — unexpected None payload after valid report
# ---------------------------------------------------------------------------


def test_load_validated_graph_spec_raises_when_payload_is_none_unexpectedly(
    tmp_path: Path,
) -> None:
    """Line 110: WorkflowValidationFailedError raised when _load_yaml_mapping_for_ui returns None.

    Exercises the defensive branch when validate_workflow_for_ui returned a valid report.
    """
    from unittest.mock import patch

    from yagra.application.use_cases import (
        WorkflowValidationFailedError,
        load_validated_graph_spec,
    )
    from yagra.application.use_cases.workflow_validation_reporter import WorkflowValidationReport

    payload = _base_payload()
    workflow_path = _write_workflow(tmp_path / "valid.yaml", payload)

    # validate_workflow_for_ui returns valid, but _load_yaml_mapping_for_ui returns None
    with (
        patch(
            "yagra.application.use_cases.workflow_validation_reporter.validate_workflow_for_ui",
            return_value=WorkflowValidationReport(),
        ),
        patch(
            "yagra.application.use_cases.workflow_validation_reporter._load_yaml_mapping_for_ui",
            return_value=None,
        ),
    ):
        with pytest.raises(WorkflowValidationFailedError) as exc_info:
            load_validated_graph_spec(workflow_path)

    report = exc_info.value.report
    assert not report.is_valid
    assert any(i.code == "schema_error" for i in report.issues)
    assert any("unexpectedly" in i.message for i in report.issues)


# ---------------------------------------------------------------------------
# validate_workflow_for_ui: line 148 — returns early when payload is None (YAML load error)
# ---------------------------------------------------------------------------


def test_validate_workflow_for_ui_returns_early_on_yaml_load_failure(tmp_path: Path) -> None:
    """Line 148: validate_workflow_for_ui returns the report immediately.

    Exercises the early return when _load_yaml_mapping_for_ui returns None (e.g. file read error).
    """
    from unittest.mock import patch

    from yagra.application.use_cases.workflow_validation_reporter import (
        WorkflowValidationIssue,
        WorkflowValidationReport,
        validate_workflow_for_ui,
    )

    payload = _base_payload()
    workflow_path = _write_workflow(tmp_path / "any.yaml", payload)

    pre_populated_report = WorkflowValidationReport(
        issues=[WorkflowValidationIssue(code="schema_error", message="injected failure")]
    )

    def _fake_load(path, report):
        # Populate the report and return None (simulating load failure)
        report.issues.extend(pre_populated_report.issues)
        return None

    with patch(
        "yagra.application.use_cases.workflow_validation_reporter._load_yaml_mapping_for_ui",
        side_effect=_fake_load,
    ):
        result = validate_workflow_for_ui(workflow_path)

    assert not result.is_valid
    assert any(i.code == "schema_error" for i in result.issues)


# ---------------------------------------------------------------------------
# _load_yaml_mapping_for_ui: lines 250-258 (OSError) and 261-268 (non-dict payload)
# ---------------------------------------------------------------------------


def test_load_yaml_mapping_for_ui_records_os_error(tmp_path: Path) -> None:
    """Lines 250-258: OSError during YAML load is caught and added to report as schema_error."""
    import stat

    from yagra.application.use_cases.workflow_validation_reporter import (
        WorkflowValidationReport,
        _load_yaml_mapping_for_ui,
    )

    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text("version: '1'\n")
    workflow_file.chmod(0o000)
    try:
        report = WorkflowValidationReport()
        result = _load_yaml_mapping_for_ui(workflow_file, report)
        assert result is None
        assert len(report.issues) == 1
        assert report.issues[0].code == "schema_error"
        assert "failed to load workflow" in report.issues[0].message
    finally:
        workflow_file.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_load_yaml_mapping_for_ui_records_yaml_parse_error(tmp_path: Path) -> None:
    """Lines 250-258: yaml.YAMLError during YAML load is caught and recorded."""
    from yagra.application.use_cases.workflow_validation_reporter import (
        WorkflowValidationReport,
        _load_yaml_mapping_for_ui,
    )

    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text("not: valid: yaml: [")

    report = WorkflowValidationReport()
    result = _load_yaml_mapping_for_ui(workflow_file, report)
    assert result is None
    assert len(report.issues) == 1
    assert report.issues[0].code == "schema_error"
    assert "failed to load workflow" in report.issues[0].message


def test_load_yaml_mapping_for_ui_records_non_dict_payload(tmp_path: Path) -> None:
    """Lines 261-268: A non-dict YAML root (e.g. a list) is recorded as schema_error."""
    from yagra.application.use_cases.workflow_validation_reporter import (
        WorkflowValidationReport,
        _load_yaml_mapping_for_ui,
    )

    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text("- item1\n- item2\n")

    report = WorkflowValidationReport()
    result = _load_yaml_mapping_for_ui(workflow_file, report)
    assert result is None
    assert len(report.issues) == 1
    assert report.issues[0].code == "schema_error"
    assert "workflow must be a mapping" in report.issues[0].message


# ---------------------------------------------------------------------------
# _validate_graph_spec_for_ui: line 305 — empty pydantic error list fallback
# ---------------------------------------------------------------------------


def test_validate_graph_spec_for_ui_uses_fallback_when_pydantic_errors_empty(
    tmp_path: Path,
) -> None:
    """Line 305: When _convert_pydantic_errors returns [], a generic fallback issue is added."""
    from unittest.mock import patch

    # Build a ValidationError by using an invalid payload
    import pydantic
    from pydantic import ValidationError

    from yagra.application.use_cases.workflow_validation_reporter import (
        WorkflowValidationReport,
        _validate_graph_spec_for_ui,
    )

    class _M(pydantic.BaseModel):
        x: int

    try:
        _M.model_validate({"x": "not_an_int_but_pydantic_coerces"})
        # pydantic v2 coerces — force a real error
        _M.model_validate({"x": []})
    except ValidationError as ve:
        real_exc = ve
    else:
        pytest.skip("Could not produce a ValidationError for this test")

    # Patch _convert_pydantic_errors to return [] to trigger the fallback
    with (
        patch(
            "yagra.application.use_cases.workflow_validation_reporter._convert_pydantic_errors",
            return_value=[],
        ),
        patch(
            "yagra.application.use_cases.workflow_validation_reporter.GraphSpec.model_validate",
            side_effect=real_exc,
        ),
    ):
        report = WorkflowValidationReport()
        result = _validate_graph_spec_for_ui({"dummy": True}, report)

    assert result is None
    assert len(report.issues) == 1
    assert report.issues[0].code == "schema_error"
    assert "Pydantic schema validation failed" in report.issues[0].message


# ---------------------------------------------------------------------------
# _normalize_location: line 349 (non-tuple raw_loc) and line 356 (non-str/int part)
# ---------------------------------------------------------------------------


def test_normalize_location_returns_empty_tuple_for_non_tuple_input() -> None:
    """Line 349: When raw_loc is not a tuple, _normalize_location returns ()."""
    from yagra.application.use_cases.workflow_validation_reporter import _normalize_location

    assert _normalize_location("not_a_tuple") == ()
    assert _normalize_location(None) == ()
    assert _normalize_location(42) == ()
    assert _normalize_location(["list", "not", "tuple"]) == ()


def test_normalize_location_converts_non_str_int_parts_to_str() -> None:
    """Line 356: Parts that are neither str nor int are converted to str()."""
    from yagra.application.use_cases.workflow_validation_reporter import _normalize_location

    # A tuple containing a non-str/non-int part (e.g. a float)
    result = _normalize_location(("nodes", 1, 3.14))
    assert result == ("nodes", 1, "3.14")
