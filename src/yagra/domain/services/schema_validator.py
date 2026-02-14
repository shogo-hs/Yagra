"""Yagra YAML スキーマの整合性検証を提供する。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from yagra.domain.entities.graph_schema import GraphSpec

type Location = tuple[str | int, ...]


class GraphSchemaValidationError(ValueError):
    """Yagra の YAML スキーマ検証失敗を表す例外。"""


@dataclass(frozen=True, slots=True)
class GraphStructureIssue:
    """GraphSpec 構造検証で検知した単一問題。"""

    message: str
    location: Location


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
        issues.append(
            GraphStructureIssue(
                message=f"start_at が未定義ノードを参照しています: {spec.start_at}",
                location=("start_at",),
            )
        )

    for index, node_id in enumerate(spec.end_at):
        if node_id not in node_id_set:
            issues.append(
                GraphStructureIssue(
                    message=f"end_at が未定義ノードを参照しています: {node_id}",
                    location=("end_at", index),
                )
            )

    for index, edge in enumerate(spec.edges):
        if edge.source not in node_id_set:
            issues.append(
                GraphStructureIssue(
                    message=f"edge.source が未定義ノードを参照しています: {edge.source}",
                    location=("edges", index, "source"),
                )
            )
        if edge.target not in node_id_set:
            issues.append(
                GraphStructureIssue(
                    message=f"edge.target が未定義ノードを参照しています: {edge.target}",
                    location=("edges", index, "target"),
                )
            )

    return issues


def validate_graph_structure(spec: GraphSpec) -> None:
    """GraphSpec の参照整合性と一意性を検証する。

    Args:
        spec: 構造整合性を検証する `GraphSpec` オブジェクト。

    Raises:
        GraphSchemaValidationError: ノード重複や未定義参照が見つかった場合。
    """
    issues = collect_graph_structure_issues(spec)
    if issues:
        raise GraphSchemaValidationError(" / ".join(issue.message for issue in issues))


def validate_graph_spec(payload: Mapping[str, Any]) -> GraphSpec:
    """辞書形式の入力を `GraphSpec` として検証する。

    Args:
        payload: YAML をパースした辞書データ。

    Returns:
        検証済みの `GraphSpec`。

    Raises:
        GraphSchemaValidationError: Pydantic 検証、または構造整合性検証に失敗した場合。
    """
    try:
        spec = GraphSpec.model_validate(payload)
    except ValidationError as exc:
        raise GraphSchemaValidationError(f"Pydanticスキーマ検証に失敗しました: {exc}") from exc

    validate_graph_structure(spec)
    return spec
