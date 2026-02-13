"""Yagra YAML スキーマの整合性検証を提供する。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from yagra.domain.entities.graph_schema import GraphSpec


class GraphSchemaValidationError(ValueError):
    """Yagra の YAML スキーマ検証失敗を表す例外。"""


def validate_graph_structure(spec: GraphSpec) -> None:
    """GraphSpec の参照整合性と一意性を検証する。

    Args:
        spec: 構造整合性を検証する `GraphSpec` オブジェクト。

    Raises:
        GraphSchemaValidationError: ノード重複や未定義参照が見つかった場合。
    """
    node_ids = [node.id for node in spec.nodes]
    node_id_set = set(node_ids)
    errors: list[str] = []

    duplicates = sorted([node_id for node_id, count in Counter(node_ids).items() if count > 1])
    if duplicates:
        duplicated_labels = ", ".join(duplicates)
        errors.append(f"ノードIDが重複しています: {duplicated_labels}")

    if spec.start_at not in node_id_set:
        errors.append(f"start_at が未定義ノードを参照しています: {spec.start_at}")

    unknown_end_nodes = sorted([node_id for node_id in spec.end_at if node_id not in node_id_set])
    if unknown_end_nodes:
        labels = ", ".join(unknown_end_nodes)
        errors.append(f"end_at が未定義ノードを参照しています: {labels}")

    unknown_sources = sorted({edge.source for edge in spec.edges if edge.source not in node_id_set})
    if unknown_sources:
        labels = ", ".join(unknown_sources)
        errors.append(f"edge.source が未定義ノードを参照しています: {labels}")

    unknown_targets = sorted({edge.target for edge in spec.edges if edge.target not in node_id_set})
    if unknown_targets:
        labels = ", ".join(unknown_targets)
        errors.append(f"edge.target が未定義ノードを参照しています: {labels}")

    if errors:
        raise GraphSchemaValidationError(" / ".join(errors))


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
