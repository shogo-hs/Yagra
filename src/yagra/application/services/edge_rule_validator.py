"""Provides rule validation for workflow edge definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from yagra.domain.entities import GraphSpec

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class EdgeRuleIssue:
    """A single issue detected during edge definition rule validation."""

    message: str
    location: Location
    severity: Literal["error", "warning", "info"] = "error"


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
    fanout_edge_indexes: dict[str, list[int]] = {}

    for index, edge in enumerate(spec.edges):
        if edge.fan_out is not None:
            fanout_edge_indexes.setdefault(edge.source, []).append(index)
            continue

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

    fanout_conflict_sources = sorted(
        set(fanout_edge_indexes) & (set(conditional_edge_indexes) | set(normal_edge_indexes))
    )
    for source in fanout_conflict_sources:
        message = f"fan_out edge cannot be combined with other edge types: {source}"
        for index in fanout_edge_indexes[source]:
            issues.append(EdgeRuleIssue(message=message, location=("edges", index, "fan_out")))
        for index in conditional_edge_indexes.get(source, []):
            issues.append(EdgeRuleIssue(message=message, location=("edges", index, "condition")))
        for index in normal_edge_indexes.get(source, []):
            issues.append(EdgeRuleIssue(message=message, location=("edges", index)))

    # Hint: notify which labels the LLM must output for conditional branch source nodes
    node_index_by_id: dict[str, int] = {node.id: i for i, node in enumerate(spec.nodes)}
    for node_id, labels_map in conditional_labels_by_source.items():
        node_index = node_index_by_id.get(node_id)
        if node_index is None:
            continue
        node = spec.nodes[node_index]
        # Only warn for llm handler (structured_llm is already caught by handler_compatibility_validator)
        if node.handler != "llm":
            continue
        # Only emit hint when prompt is inline dict form; skip prompt_ref (static content not visible)
        if "prompt" not in node.params or "prompt_ref" in node.params:
            continue
        label_list = sorted(labels_map.keys())
        issues.append(
            EdgeRuleIssue(
                message=(
                    f"node '{node_id}' (handler: 'llm') is a conditional branch source. "
                    f"The LLM must output exactly one of these labels as plain text with no extra text: "
                    f"{label_list}. "
                    f"Make sure your prompt explicitly instructs this."
                ),
                location=("nodes", node_index, "handler"),
                severity="info",
            )
        )

    return issues
