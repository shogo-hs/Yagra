"""Generates workflow validation reports for the WebUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from yagra.application.services import WorkflowReferenceError, resolve_workflow_references
from yagra.application.services.edge_rule_validator import collect_edge_rule_issues
from yagra.domain.entities import GraphSpec
from yagra.domain.services.schema_validator import collect_graph_structure_issues

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class WorkflowValidationIssue:
    """A single validation issue for UI display."""

    code: str
    message: str
    location: Location = ()
    severity: Literal["error", "warning", "info"] = "error"
    context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dict in API response format.

        Returns:
            Dictionary containing code, message, location, severity, and context.
            The context key is omitted if context is None.
        """
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "location": list(self.location),
            "severity": self.severity,
        }
        if self.context is not None:
            result["context"] = self.context
        return result


@dataclass(slots=True)
class WorkflowValidationReport:
    """Report holding workflow validation results."""

    issues: list[WorkflowValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Returns whether no issues exist."""
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dict in API response format.

        Returns:
            Dictionary containing is_valid and issues.
        """
        return {
            "is_valid": self.is_valid,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class WorkflowValidationFailedError(ValueError):
    """Exception raised when workflow validation fails."""

    def __init__(self, report: WorkflowValidationReport) -> None:
        """Initializes the validation failure exception.

        Args:
            report: Report containing the validation failure details.
        """
        self.report = report
        super().__init__(format_validation_report(report))


def load_validated_graph_spec(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> GraphSpec:
    """Validates a workflow and returns a GraphSpec only on success.

    Args:
        workflow_path: Path to the entry workflow YAML.
        bundle_root: Base directory for split references. Defaults to workflow parent directory.

    Returns:
        Validated `GraphSpec`.

    Raises:
        WorkflowValidationFailedError: If workflow validation fails.
    """
    report = validate_workflow_for_ui(workflow_path=workflow_path, bundle_root=bundle_root)
    if not report.is_valid:
        raise WorkflowValidationFailedError(report)

    workflow_abspath = Path(workflow_path).expanduser().resolve()
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None
    payload = _load_yaml_mapping_for_ui(path=workflow_abspath, report=WorkflowValidationReport())
    if payload is None:
        # This point should not be reached if validate_workflow_for_ui returned valid.
        raise WorkflowValidationFailedError(
            WorkflowValidationReport(
                issues=[
                    WorkflowValidationIssue(
                        code="schema_error",
                        message="workflow payload loading failed unexpectedly",
                        location=(),
                    )
                ]
            )
        )
    resolved_payload = resolve_workflow_references(
        payload=payload,
        workflow_path=workflow_abspath,
        bundle_root=bundle_root_path,
    )
    return GraphSpec.model_validate(resolved_payload)


def validate_workflow_for_ui(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> WorkflowValidationReport:
    """Validates a workflow for the UI and returns a structured report.

    Args:
        workflow_path: Path to the entry workflow YAML.
        bundle_root: Base directory for split references. Defaults to workflow parent directory.

    Returns:
        `WorkflowValidationReport` holding the validation results.
    """
    report = WorkflowValidationReport()
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None

    payload = _load_yaml_mapping_for_ui(path=workflow_abspath, report=report)
    if payload is None:
        return report

    return validate_workflow_payload_for_ui(
        payload=payload,
        workflow_path=workflow_abspath,
        bundle_root=bundle_root_path,
    )


def validate_workflow_payload_for_ui(
    payload: dict[str, Any],
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> WorkflowValidationReport:
    """Validates a workflow payload for the UI and returns a structured report.

    Args:
        payload: Workflow dictionary data to validate.
        workflow_path: Path to the entry workflow YAML.
        bundle_root: Base directory for split references. Defaults to workflow parent directory.

    Returns:
        `WorkflowValidationReport` holding the validation results.
    """
    report = WorkflowValidationReport()
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None

    try:
        resolved_payload = resolve_workflow_references(
            payload=payload,
            workflow_path=workflow_abspath,
            bundle_root=bundle_root_path,
        )
    except WorkflowReferenceError as exc:
        report.issues.append(
            WorkflowValidationIssue(
                code="reference_error",
                message=str(exc),
                location=exc.location,
            )
        )
        return report

    spec = _validate_graph_spec_for_ui(resolved_payload=resolved_payload, report=report)
    if spec is None:
        return report

    for structure_issue in collect_graph_structure_issues(spec):
        report.issues.append(
            WorkflowValidationIssue(
                code="structure_error",
                message=structure_issue.message,
                location=structure_issue.location,
                severity="error",
                context=structure_issue.context,
            )
        )

    for edge_rule_issue in collect_edge_rule_issues(spec):
        report.issues.append(
            WorkflowValidationIssue(
                code="edge_rule_error",
                message=edge_rule_issue.message,
                location=edge_rule_issue.location,
            )
        )

    return report


def _load_yaml_mapping_for_ui(
    path: Path, report: WorkflowValidationReport
) -> dict[str, Any] | None:
    """Loads a YAML file as a dictionary and records any failure in the report.

    Args:
        path: Path to the workflow to load.
        report: Validation report to append issues to.

    Returns:
        Loaded dictionary data, or `None` on load failure.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        report.issues.append(
            WorkflowValidationIssue(
                code="schema_error",
                message=f"failed to load workflow: {exc}",
                location=(),
            )
        )
        return None

    if not isinstance(payload, dict):
        report.issues.append(
            WorkflowValidationIssue(
                code="schema_error",
                message=f"workflow must be a mapping: {path}",
                location=(),
            )
        )
        return None

    return payload


def format_validation_report(report: WorkflowValidationReport) -> str:
    """Formats the validation report into a readable message.

    Args:
        report: Validation report to format.

    Returns:
        Formatted message string.
    """
    if report.is_valid:
        return "workflow validation passed"
    return _format_validation_issues(report.issues)


def _validate_graph_spec_for_ui(
    resolved_payload: dict[str, Any],
    report: WorkflowValidationReport,
) -> GraphSpec | None:
    """Validates the resolved payload as GraphSpec.

    Args:
        resolved_payload: Reference-resolved workflow data.
        report: Validation report to append issues to.

    Returns:
        Validated `GraphSpec`, or `None` on schema error.
    """
    try:
        return GraphSpec.model_validate(resolved_payload)
    except ValidationError as exc:
        issues = _convert_pydantic_errors(exc)
        if not issues:
            issues = [
                WorkflowValidationIssue(
                    code="schema_error",
                    message="Pydantic schema validation failed",
                    location=(),
                )
            ]
        report.issues.extend(issues)
        return None


def _convert_pydantic_errors(exc: ValidationError) -> list[WorkflowValidationIssue]:
    """Converts a Pydantic ValidationError to UI-facing issues.

    Args:
        exc: Pydantic validation error to convert.

    Returns:
        List of converted issues.
    """
    issues: list[WorkflowValidationIssue] = []
    for error in exc.errors():
        raw_loc = error.get("loc", ())
        message = str(error.get("msg", "validation error"))
        issues.append(
            WorkflowValidationIssue(
                code="schema_error",
                message=message,
                location=_normalize_location(raw_loc),
            )
        )
    return issues


def _normalize_location(raw_loc: Any) -> Location:
    """Normalizes a Pydantic loc value to the `Location` format.

    Args:
        raw_loc: Location value returned by Pydantic.

    Returns:
        Normalized location tuple.
    """
    if not isinstance(raw_loc, tuple):
        return ()

    normalized: list[str | int] = []
    for part in raw_loc:
        if isinstance(part, (str, int)):
            normalized.append(part)
        else:
            normalized.append(str(part))
    return tuple(normalized)


def _format_validation_issues(issues: list[WorkflowValidationIssue]) -> str:
    """Converts the validation issue list into a newline-separated string.

    Args:
        issues: List of issues to convert.

    Returns:
        Formatted message string.
    """
    lines: list[str] = ["workflow validation failed:"]
    for issue in issues:
        location = _format_location(issue.location)
        lines.append(f"- [{issue.code}] {issue.message} (at: {location})")
    return "\n".join(lines)


def _format_location(location: Location) -> str:
    """Converts a Location tuple to dot notation.

    Args:
        location: Location tuple to display.

    Returns:
        Location string in dot notation.
    """
    if not location:
        return "<root>"

    parts: list[str] = []
    for part in location:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            if parts:
                parts.append(f".{part}")
            else:
                parts.append(part)
    return "".join(parts)
