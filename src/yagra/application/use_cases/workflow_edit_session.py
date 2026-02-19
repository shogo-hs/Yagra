"""Provides loading of workflow editing sessions and diff generation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from difflib import unified_diff
from hashlib import sha256
from os import PathLike
from pathlib import Path
from typing import Any, Literal

import yaml

from yagra.application.use_cases.workflow_validation_reporter import (
    WorkflowValidationReport,
    validate_workflow_payload_for_ui,
)

type Location = tuple[str | int, ...]

UI_STATE_SUFFIX = ".workflow-ui.json"


@dataclass(frozen=True, slots=True)
class WorkflowEditSession:
    """Holds the current state of the editing session."""

    workflow: dict[str, Any]
    ui_state: dict[str, Any]
    revision: str
    validation_report: WorkflowValidationReport


@dataclass(frozen=True, slots=True)
class WorkflowChange:
    """Represents a single change event."""

    kind: Literal["add", "remove", "update"]
    path: Location
    before: Any | None
    after: Any | None

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dictionary in API response format.

        Returns:
            Dictionary containing kind, path, before, and after.
        """
        return {
            "kind": self.kind,
            "path": list(self.path),
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True, slots=True)
class WorkflowDiffResult:
    """Represents the diff calculation result."""

    base_revision: str
    candidate_revision: str
    summary: dict[str, int]
    changes: tuple[WorkflowChange, ...]
    yaml_unified_diff: str
    validation_report: WorkflowValidationReport

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dictionary in API response format.

        Returns:
            Dictionary containing diff information and the validation report.
        """
        return {
            "base_revision": self.base_revision,
            "candidate_revision": self.candidate_revision,
            "summary": self.summary,
            "changes": [change.to_dict() for change in self.changes],
            "yaml_unified_diff": self.yaml_unified_diff,
            "validation_report": self.validation_report.to_dict(),
        }


def resolve_ui_state_path(
    workflow_path: str | PathLike[str],
    ui_state_path: str | PathLike[str] | None = None,
) -> Path:
    """Returns the absolute path of the UI sidecar file associated with the workflow.

    Args:
        workflow_path: Target workflow file path.
        ui_state_path: Explicitly specified UI sidecar path.

    Returns:
        Absolute path of the UI sidecar file.
    """
    if ui_state_path is not None:
        return Path(ui_state_path).expanduser().resolve()
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    return workflow_abspath.with_suffix(UI_STATE_SUFFIX)


def load_workflow_edit_session(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
    ui_state_path: str | PathLike[str] | None = None,
) -> WorkflowEditSession:
    """Loads the workflow and UI sidecar and returns an editing session.

    Args:
        workflow_path: File path of the workflow to load.
        bundle_root: Base directory for split reference resolution.
        ui_state_path: UI sidecar file path.

    Returns:
        A `WorkflowEditSession` holding the current state.

    Raises:
        ValueError: If the workflow or ui_state cannot be loaded as a dictionary.
    """
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    ui_state_abspath = resolve_ui_state_path(
        workflow_path=workflow_abspath,
        ui_state_path=ui_state_path,
    )

    workflow_payload = _load_workflow_mapping(workflow_abspath)
    ui_state_payload = _load_ui_state_mapping(ui_state_abspath)
    validation_report = validate_workflow_payload_for_ui(
        payload=deepcopy(workflow_payload),
        workflow_path=workflow_abspath,
        bundle_root=bundle_root,
    )
    revision = compute_workflow_revision(workflow_payload, ui_state_payload)
    return WorkflowEditSession(
        workflow=workflow_payload,
        ui_state=ui_state_payload,
        revision=revision,
        validation_report=validation_report,
    )


def build_workflow_diff(
    base_workflow: Mapping[str, Any],
    candidate_workflow: Mapping[str, Any],
    base_ui_state: Mapping[str, Any],
    candidate_ui_state: Mapping[str, Any],
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> WorkflowDiffResult:
    """Generates diff information for a workflow editing proposal.

    Args:
        base_workflow: Current workflow data.
        candidate_workflow: Post-edit workflow data.
        base_ui_state: Current UI sidecar.
        candidate_ui_state: Post-edit UI sidecar.
        workflow_path: Workflow file path.
        bundle_root: Base directory for split reference resolution.

    Returns:
        A `WorkflowDiffResult` holding the diff and validation results.

    Raises:
        ValueError: If the workflow or ui_state is not in dictionary format.
    """
    base_workflow_mapping = _ensure_mapping(base_workflow, label="base workflow")
    candidate_workflow_mapping = _ensure_mapping(candidate_workflow, label="candidate workflow")
    base_ui_state_mapping = _ensure_mapping(base_ui_state, label="base ui_state")
    candidate_ui_state_mapping = _ensure_mapping(candidate_ui_state, label="candidate ui_state")

    changes = _collect_changes(
        before=base_workflow_mapping,
        after=candidate_workflow_mapping,
        path=(),
    )
    changes.extend(
        _collect_changes(
            before=base_ui_state_mapping,
            after=candidate_ui_state_mapping,
            path=("ui_state",),
        )
    )
    summary = _build_summary(changes)
    diff_text = _build_yaml_unified_diff(
        before=base_workflow_mapping,
        after=candidate_workflow_mapping,
    )
    validation_report = validate_workflow_payload_for_ui(
        payload=deepcopy(candidate_workflow_mapping),
        workflow_path=workflow_path,
        bundle_root=bundle_root,
    )

    return WorkflowDiffResult(
        base_revision=compute_workflow_revision(base_workflow_mapping, base_ui_state_mapping),
        candidate_revision=compute_workflow_revision(
            candidate_workflow_mapping,
            candidate_ui_state_mapping,
        ),
        summary=summary,
        changes=tuple(changes),
        yaml_unified_diff=diff_text,
        validation_report=validation_report,
    )


def compute_workflow_revision(
    workflow: Mapping[str, Any],
    ui_state: Mapping[str, Any],
) -> str:
    """Calculates the revision from the contents of the workflow and UI sidecar.

    Args:
        workflow: Workflow data.
        ui_state: UI sidecar data.

    Returns:
        A SHA256-based revision string.
    """
    workflow_mapping = _ensure_mapping(workflow, label="workflow")
    ui_state_mapping = _ensure_mapping(ui_state, label="ui_state")
    payload = {"ui_state": ui_state_mapping, "workflow": workflow_mapping}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _load_workflow_mapping(path: Path) -> dict[str, Any]:
    """Loads the workflow YAML as a dictionary.

    Args:
        path: Path to the workflow to load.

    Returns:
        The loaded workflow dictionary.

    Raises:
        ValueError: If loading the YAML fails.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Failed to load workflow: {path}: {exc}") from exc
    return _ensure_mapping(payload, label=f"workflow: {path}")


def _load_ui_state_mapping(path: Path) -> dict[str, Any]:
    """Loads the UI sidecar JSON as a dictionary.

    Args:
        path: Path to the UI sidecar to load.

    Returns:
        The loaded UI sidecar dictionary. Returns an empty dictionary if the file does not exist.

    Raises:
        ValueError: If the JSON is not in dictionary format.
    """
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to load ui_state: {path}: {exc}") from exc
    return _ensure_mapping(payload, label=f"ui_state: {path}")


def _ensure_mapping(payload: Any, label: str) -> dict[str, Any]:
    """Validates that the format is dict and returns it.

    Args:
        payload: Data to validate.
        label: Target name to include in error messages.

    Returns:
        Shallow copy of the data converted to a dictionary.

    Raises:
        ValueError: If payload is not a dictionary.
    """
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(payload)


def _collect_changes(before: Any, after: Any, path: Location) -> list[WorkflowChange]:
    """Recursively compares two values and extracts change events.

    Args:
        before: The value before the change.
        after: The value after the change.
        path: The current traversal path.

    Returns:
        List of extracted change events.
    """
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        changes: list[WorkflowChange] = []
        before_mapping = dict(before)
        after_mapping = dict(after)
        keys = sorted(set(before_mapping) | set(after_mapping), key=lambda item: str(item))
        for key in keys:
            token = _path_token(key)
            child_path = path + (token,)
            if key not in before_mapping:
                changes.append(
                    WorkflowChange(
                        kind="add",
                        path=child_path,
                        before=None,
                        after=deepcopy(after_mapping[key]),
                    )
                )
                continue
            if key not in after_mapping:
                changes.append(
                    WorkflowChange(
                        kind="remove",
                        path=child_path,
                        before=deepcopy(before_mapping[key]),
                        after=None,
                    )
                )
                continue
            changes.extend(
                _collect_changes(
                    before=before_mapping[key],
                    after=after_mapping[key],
                    path=child_path,
                )
            )
        return changes

    if isinstance(before, list) and isinstance(after, list):
        changes = []
        max_length = max(len(before), len(after))
        for index in range(max_length):
            child_path = path + (index,)
            if index >= len(before):
                changes.append(
                    WorkflowChange(
                        kind="add",
                        path=child_path,
                        before=None,
                        after=deepcopy(after[index]),
                    )
                )
                continue
            if index >= len(after):
                changes.append(
                    WorkflowChange(
                        kind="remove",
                        path=child_path,
                        before=deepcopy(before[index]),
                        after=None,
                    )
                )
                continue
            changes.extend(
                _collect_changes(
                    before=before[index],
                    after=after[index],
                    path=child_path,
                )
            )
        return changes

    if before != after:
        return [
            WorkflowChange(
                kind="update",
                path=path,
                before=deepcopy(before),
                after=deepcopy(after),
            )
        ]
    return []


def _build_summary(changes: list[WorkflowChange]) -> dict[str, int]:
    """Aggregates change events into category counts.

    Args:
        changes: List of change events to aggregate.

    Returns:
        Dictionary holding the count per category.
    """
    summary = {
        "total": len(changes),
        "nodes": 0,
        "edges": 0,
        "params": 0,
        "ui_state": 0,
        "other": 0,
    }
    for change in changes:
        if not change.path:
            summary["other"] += 1
            continue
        category = change.path[0]
        if category == "nodes":
            summary["nodes"] += 1
        elif category == "edges":
            summary["edges"] += 1
        elif category == "params":
            summary["params"] += 1
        elif category == "ui_state":
            summary["ui_state"] += 1
        else:
            summary["other"] += 1
    return summary


def _build_yaml_unified_diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    """Generates a unified diff string for the workflow YAML.

    Args:
        before: Workflow before the change.
        after: Workflow after the change.

    Returns:
        Unified diff string. Returns an empty string if there are no differences.
    """
    before_text = yaml.safe_dump(before, sort_keys=False, allow_unicode=True)
    after_text = yaml.safe_dump(after, sort_keys=False, allow_unicode=True)
    lines = unified_diff(
        before_text.splitlines(),
        after_text.splitlines(),
        fromfile="current/workflow.yaml",
        tofile="candidate/workflow.yaml",
        lineterm="",
    )
    return "\n".join(lines)


def _path_token(value: Any) -> str | int:
    """Normalizes dict keys to change path tokens.

    Args:
        value: The dictionary key to convert.

    Returns:
        Token used in the path representation.
    """
    if isinstance(value, (str, int)):
        return value
    return str(value)
