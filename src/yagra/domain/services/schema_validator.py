"""Provides structural integrity validation for Yagra YAML graph specs."""

from __future__ import annotations

import difflib
from collections import Counter
from dataclasses import dataclass
from typing import Any

from yagra.domain.entities.graph_schema import GraphSpec

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class GraphStructureIssue:
    """A single issue detected during GraphSpec structural validation."""

    message: str
    location: Location
    context: dict[str, Any] | None = None


def _fuzzy_candidates(target: str, candidates: set[str]) -> list[str]:
    """Return similar candidates via fuzzy matching.

    Args:
        target: The string to search for.
        candidates: Set of strings to match against.

    Returns:
        Up to 3 candidates sorted by similarity (highest first).
    """
    return difflib.get_close_matches(target, candidates, n=3, cutoff=0.6)


def collect_graph_structure_issues(spec: GraphSpec) -> list[GraphStructureIssue]:
    """Collect reference integrity and uniqueness violations in a GraphSpec.

    Args:
        spec: The `GraphSpec` object to validate for structural integrity.

    Returns:
        List of detected structural issues. Empty list if no issues found.
    """
    node_ids = [node.id for node in spec.nodes]
    node_id_set = set(node_ids)
    issues: list[GraphStructureIssue] = []

    duplicated_ids = {node_id for node_id, count in Counter(node_ids).items() if count > 1}
    for index, node_id in enumerate(node_ids):
        if node_id in duplicated_ids:
            issues.append(
                GraphStructureIssue(
                    message=f"Duplicate node ID: {node_id}",
                    location=("nodes", index, "id"),
                )
            )

    if spec.start_at not in node_id_set:
        candidates = _fuzzy_candidates(spec.start_at, node_id_set)
        issues.append(
            GraphStructureIssue(
                message=f"start_at references an undefined node: {spec.start_at}",
                location=("start_at",),
                context={
                    "actual_value": spec.start_at,
                    "available_values": sorted(node_id_set),
                    "suggestion": candidates[0] if candidates else None,
                },
            )
        )

    for index, node_id in enumerate(spec.end_at):
        if node_id not in node_id_set:
            candidates = _fuzzy_candidates(node_id, node_id_set)
            issues.append(
                GraphStructureIssue(
                    message=f"end_at references an undefined node: {node_id}",
                    location=("end_at", index),
                    context={
                        "actual_value": node_id,
                        "available_values": sorted(node_id_set),
                        "suggestion": candidates[0] if candidates else None,
                    },
                )
            )

    for index, node_id in enumerate(spec.interrupt_before):
        if node_id not in node_id_set:
            candidates = _fuzzy_candidates(node_id, node_id_set)
            issues.append(
                GraphStructureIssue(
                    message=f"interrupt_before references an undefined node: {node_id}",
                    location=("interrupt_before", index),
                    context={
                        "actual_value": node_id,
                        "available_values": sorted(node_id_set),
                        "suggestion": candidates[0] if candidates else None,
                    },
                )
            )

    for index, node_id in enumerate(spec.interrupt_after):
        if node_id not in node_id_set:
            candidates = _fuzzy_candidates(node_id, node_id_set)
            issues.append(
                GraphStructureIssue(
                    message=f"interrupt_after references an undefined node: {node_id}",
                    location=("interrupt_after", index),
                    context={
                        "actual_value": node_id,
                        "available_values": sorted(node_id_set),
                        "suggestion": candidates[0] if candidates else None,
                    },
                )
            )

    end_at_set = set(spec.end_at)
    for index, edge in enumerate(spec.edges):
        if edge.source in end_at_set:
            issues.append(
                GraphStructureIssue(
                    message=f"end_at node cannot be used as an edge source: {edge.source}",
                    location=("edges", index, "source"),
                    context={
                        "actual_value": edge.source,
                        "end_at_nodes": sorted(end_at_set),
                    },
                )
            )

    for index, node in enumerate(spec.nodes):
        if node.fallback is not None:
            if node.fallback == node.id:
                issues.append(
                    GraphStructureIssue(
                        message=f"node '{node.id}' fallback cannot reference itself",
                        location=("nodes", index, "fallback"),
                    )
                )
            elif node.fallback not in node_id_set:
                candidates = _fuzzy_candidates(node.fallback, node_id_set)
                issues.append(
                    GraphStructureIssue(
                        message=f"node '{node.id}' fallback references an undefined node: {node.fallback}",
                        location=("nodes", index, "fallback"),
                        context={
                            "actual_value": node.fallback,
                            "available_values": sorted(node_id_set),
                            "suggestion": candidates[0] if candidates else None,
                        },
                    )
                )

    for index, edge in enumerate(spec.edges):
        if edge.source not in node_id_set:
            candidates = _fuzzy_candidates(edge.source, node_id_set)
            issues.append(
                GraphStructureIssue(
                    message=f"edge.source references an undefined node: {edge.source}",
                    location=("edges", index, "source"),
                    context={
                        "actual_value": edge.source,
                        "available_values": sorted(node_id_set),
                        "suggestion": candidates[0] if candidates else None,
                    },
                )
            )
        if edge.target not in node_id_set:
            candidates = _fuzzy_candidates(edge.target, node_id_set)
            issues.append(
                GraphStructureIssue(
                    message=f"edge.target references an undefined node: {edge.target}",
                    location=("edges", index, "target"),
                    context={
                        "actual_value": edge.target,
                        "available_values": sorted(node_id_set),
                        "suggestion": candidates[0] if candidates else None,
                    },
                )
            )

    return issues
