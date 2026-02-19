"""Yagra YAML の構造整合性検証を提供する。"""

from __future__ import annotations

import difflib
from collections import Counter
from dataclasses import dataclass
from typing import Any

from yagra.domain.entities.graph_schema import GraphSpec

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class GraphStructureIssue:
    """GraphSpec 構造検証で検知した単一問題。"""

    message: str
    location: Location
    context: dict[str, Any] | None = None


def _fuzzy_candidates(target: str, candidates: set[str]) -> list[str]:
    """ファジーマッチで類似候補を返す。

    Args:
        target: 検索対象の文字列。
        candidates: 候補として使用する文字列のセット。

    Returns:
        類似度が高い順に最大 3 件の候補リスト。
    """
    return difflib.get_close_matches(target, candidates, n=3, cutoff=0.6)


def collect_graph_structure_issues(spec: GraphSpec) -> list[GraphStructureIssue]:
    """GraphSpec の参照整合性と一意性違反を収集する。

    Args:
        spec: 構造整合性を検証する `GraphSpec` オブジェクト。

    Returns:
        検知した構造問題の一覧。問題がなければ空リスト。
    """
    node_ids = [node.id for node in spec.nodes]
    node_id_set = set(node_ids)
    issues: list[GraphStructureIssue] = []

    duplicated_ids = {node_id for node_id, count in Counter(node_ids).items() if count > 1}
    for index, node_id in enumerate(node_ids):
        if node_id in duplicated_ids:
            issues.append(
                GraphStructureIssue(
                    message=f"ノードIDが重複しています: {node_id}",
                    location=("nodes", index, "id"),
                )
            )

    if spec.start_at not in node_id_set:
        candidates = _fuzzy_candidates(spec.start_at, node_id_set)
        issues.append(
            GraphStructureIssue(
                message=f"start_at が未定義ノードを参照しています: {spec.start_at}",
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
                    message=f"end_at が未定義ノードを参照しています: {node_id}",
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
                    message=f"interrupt_before が未定義ノードを参照しています: {node_id}",
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
                    message=f"interrupt_after が未定義ノードを参照しています: {node_id}",
                    location=("interrupt_after", index),
                    context={
                        "actual_value": node_id,
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
                    message=f"edge.source が未定義ノードを参照しています: {edge.source}",
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
                    message=f"edge.target が未定義ノードを参照しています: {edge.target}",
                    location=("edges", index, "target"),
                    context={
                        "actual_value": edge.target,
                        "available_values": sorted(node_id_set),
                        "suggestion": candidates[0] if candidates else None,
                    },
                )
            )

    return issues
