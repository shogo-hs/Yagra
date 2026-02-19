"""Provides rule validation for workflow edge definitions."""

from __future__ import annotations

from dataclasses import dataclass

from yagra.domain.entities import GraphSpec

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class EdgeRuleIssue:
    """A single issue detected during edge definition rule validation."""

    message: str
    location: Location


def collect_edge_rule_issues(spec: GraphSpec) -> list[EdgeRuleIssue]:
    """Collects rule violations related to edge definitions.

    Args:
        spec: Workflow definition to validate.

    Returns:
        List of detected issues. Empty list if no issues found.
    """
    issues: list[EdgeRuleIssue] = []
    conditional_labels_by_source: dict[str, dict[str, int]] = {}
    conditional_edge_indexes: dict[str, list[int]] = {}
    normal_edge_indexes: dict[str, list[int]] = {}

    for index, edge in enumerate(spec.edges):
        if edge.condition is None:
            normal_edge_indexes.setdefault(edge.source, []).append(index)
            continue

        conditional_edge_indexes.setdefault(edge.source, []).append(index)
        labels = conditional_labels_by_source.setdefault(edge.source, {})
        if edge.condition in labels:
            issues.append(
                EdgeRuleIssue(
                    message=(
                        f"duplicate conditional edge label '{edge.condition}' "
                        f"for source '{edge.source}'"
                    ),
                    location=("edges", index, "condition"),
                )
            )
            continue
        labels[edge.condition] = index

    conflict_sources = sorted(set(conditional_edge_indexes) & set(normal_edge_indexes))
    for source in conflict_sources:
        message = f"mixed conditional and normal edges are not allowed: {source}"
        for index in conditional_edge_indexes[source]:
            issues.append(EdgeRuleIssue(message=message, location=("edges", index, "condition")))
        for index in normal_edge_indexes[source]:
            issues.append(EdgeRuleIssue(message=message, location=("edges", index)))

    return issues
