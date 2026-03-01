"""Validates prompt template variables against state_schema and node output keys."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from yagra.domain.entities import GraphSpec
from yagra.domain.services.prompt_variable_validator import (
    _extract_required_vars,
    _get_output_key,
)

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class PromptStateIssue:
    """A single issue detected during prompt-state consistency validation."""

    message: str
    location: Location
    severity: Literal["warning", "info"] = "warning"
    context: dict[str, Any] | None = None


def collect_prompt_state_issues(spec: GraphSpec) -> list[PromptStateIssue]:
    """Validates prompt variables and output keys against state_schema.

    Checks performed:
    1. Each ``{variable}`` in a node's prompt exists in the set of available
       keys (state_schema keys + all nodes' output_key). Severity: warning.
    2. Each node's ``output_key`` exists in ``state_schema`` when state_schema
       is non-empty. Severity: warning.
    3. When state_schema is empty but prompt variables are present, emits an
       info-level advisory. Severity: info.

    The available key set is computed globally (all nodes' output_key values
    plus state_schema keys) without topological ordering. This is a
    conservative approach that avoids false positives from execution-order
    dependencies.

    Args:
        spec: Validated workflow definition with resolved prompt references.

    Returns:
        List of detected issues. Empty list if no issues found.
    """
    issues: list[PromptStateIssue] = []
    available_keys = _collect_available_keys(spec)
    has_state_schema = bool(spec.state_schema)

    for index, node in enumerate(spec.nodes):
        prompt = node.params.get("prompt")
        if not isinstance(prompt, dict):
            continue

        required_vars = _extract_required_vars(node.params)
        output_key = _get_output_key(node.params)

        # Check 1: prompt variables exist in available keys
        for var in required_vars:
            if var not in available_keys:
                issues.append(
                    PromptStateIssue(
                        message=(
                            f"node '{node.id}': prompt variable '{{{var}}}' "
                            f"is not found in state_schema or any node's output_key"
                        ),
                        location=("nodes", index, "params", "prompt"),
                        severity="warning",
                        context={
                            "variable": var,
                            "available_keys": sorted(available_keys),
                        },
                    )
                )

        # Check 2: output_key exists in state_schema (when defined)
        if has_state_schema and output_key not in spec.state_schema:
            issues.append(
                PromptStateIssue(
                    message=(
                        f"node '{node.id}': output_key '{output_key}' "
                        f"is not defined in state_schema"
                    ),
                    location=("nodes", index, "params"),
                    severity="warning",
                    context={
                        "output_key": output_key,
                        "state_schema_keys": sorted(spec.state_schema.keys()),
                    },
                )
            )

        # Check 3: info when state_schema is empty but variables are used
        if not has_state_schema and required_vars:
            issues.append(
                PromptStateIssue(
                    message=(
                        f"node '{node.id}': prompt uses variables "
                        f"{required_vars} but no state_schema is defined. "
                        f"Consider adding a state_schema for type safety."
                    ),
                    location=("nodes", index, "params", "prompt"),
                    severity="info",
                    context={"variables": required_vars},
                )
            )

    return issues


def _collect_available_keys(spec: GraphSpec) -> set[str]:
    """Collects all keys that are available for prompt variable interpolation.

    Includes state_schema keys and every node's output_key. Uses a global
    (non-topological) approach to avoid false positives.

    Args:
        spec: Workflow definition.

    Returns:
        Set of available key names.
    """
    keys: set[str] = set(spec.state_schema.keys())
    for node in spec.nodes:
        output_key = _get_output_key(node.params)
        keys.add(output_key)
    return keys
