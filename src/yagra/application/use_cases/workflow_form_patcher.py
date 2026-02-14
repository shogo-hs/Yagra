"""Workflow フォーム入力を workflow データへ適用する。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


def apply_form_edits(
    workflow: Mapping[str, Any],
    node_edits: Sequence[Mapping[str, Any]] | None = None,
    edge_edits: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """フォーム編集内容を workflow へ適用して新しいデータを返す。

    Args:
        workflow: 変更対象 workflow データ。
        node_edits: ノード編集の一覧。
        edge_edits: エッジ編集の一覧。

    Returns:
        編集結果の workflow データ。

    Raises:
        ValueError: 編集入力が不正な場合。
    """
    workflow_mapping = _ensure_mapping(workflow, label="workflow")
    patched = deepcopy(workflow_mapping)

    nodes = patched.get("nodes")
    edges = patched.get("edges")
    if not isinstance(nodes, list):
        raise ValueError("workflow.nodes must be a list")
    if not isinstance(edges, list):
        raise ValueError("workflow.edges must be a list")

    _apply_node_edits(nodes=nodes, node_edits=node_edits or [])
    _apply_edge_edits(edges=edges, edge_edits=edge_edits or [])
    return patched


def _apply_node_edits(nodes: list[Any], node_edits: Sequence[Mapping[str, Any]]) -> None:
    """ノード編集一覧を workflow.nodes へ適用する。

    Args:
        nodes: workflow のノード配列。
        node_edits: ノード編集一覧。

    Raises:
        ValueError: ノード編集入力が不正な場合。
    """
    node_indexes = _build_node_index(nodes)
    for edit in node_edits:
        edit_mapping = _ensure_mapping(edit, label="node edit")
        node_id = edit_mapping.get("node_id")
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node edit requires non-empty 'node_id'")
        if node_id not in node_indexes:
            raise ValueError(f"node not found: {node_id}")

        target_node = nodes[node_indexes[node_id]]
        if not isinstance(target_node, dict):
            raise ValueError(f"node payload must be a mapping: {node_id}")
        params = target_node.get("params")
        if params is None:
            params = {}
            target_node["params"] = params
        if not isinstance(params, dict):
            raise ValueError(f"node params must be a mapping: {node_id}")

        _apply_optional_string_field(edit_mapping, params, "prompt_ref")
        _apply_optional_string_field(edit_mapping, params, "model_ref")
        _apply_optional_mapping_field(edit_mapping, params, "prompt")
        _apply_optional_mapping_field(edit_mapping, params, "model")


def _apply_edge_edits(edges: list[Any], edge_edits: Sequence[Mapping[str, Any]]) -> None:
    """エッジ編集一覧を workflow.edges へ適用する。

    Args:
        edges: workflow のエッジ配列。
        edge_edits: エッジ編集一覧。

    Raises:
        ValueError: エッジ編集入力が不正な場合。
    """
    for edit in edge_edits:
        edit_mapping = _ensure_mapping(edit, label="edge edit")
        edge_index = edit_mapping.get("edge_index")
        if not isinstance(edge_index, int):
            raise ValueError("edge edit requires integer 'edge_index'")
        if edge_index < 0 or edge_index >= len(edges):
            raise ValueError(f"edge index out of range: {edge_index}")

        target_edge = edges[edge_index]
        if not isinstance(target_edge, dict):
            raise ValueError(f"edge payload must be a mapping: {edge_index}")

        if "condition" not in edit_mapping:
            continue
        condition = edit_mapping.get("condition")
        if condition is None:
            target_edge.pop("condition", None)
            continue
        if not isinstance(condition, str):
            raise ValueError(f"edge condition must be a string or null: {edge_index}")
        normalized = condition.strip()
        if not normalized:
            target_edge.pop("condition", None)
        else:
            target_edge["condition"] = normalized


def _apply_optional_string_field(
    edit: dict[str, Any],
    params: dict[str, Any],
    field_name: str,
) -> None:
    """任意文字列フィールドを params に適用する。

    Args:
        edit: 変更入力。
        params: 適用対象 params。
        field_name: 対象フィールド名。

    Raises:
        ValueError: 値が不正な場合。
    """
    if field_name not in edit:
        return
    value = edit.get(field_name)
    if value is None:
        params.pop(field_name, None)
        return
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    normalized = value.strip()
    if not normalized:
        params.pop(field_name, None)
    else:
        params[field_name] = normalized


def _apply_optional_mapping_field(
    edit: dict[str, Any],
    params: dict[str, Any],
    field_name: str,
) -> None:
    """任意辞書フィールドを params に適用する。

    Args:
        edit: 変更入力。
        params: 適用対象 params。
        field_name: 対象フィールド名。

    Raises:
        ValueError: 値が不正な場合。
    """
    if field_name not in edit:
        return
    value = edit.get(field_name)
    if value is None:
        params.pop(field_name, None)
        return
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping or null")
    params[field_name] = deepcopy(dict(value))


def _build_node_index(nodes: list[Any]) -> dict[str, int]:
    """ノードIDから配列indexを引く辞書を作る。

    Args:
        nodes: workflow のノード配列。

    Returns:
        ノードID-index マップ。

    Raises:
        ValueError: ノードIDが不正、または重複している場合。
    """
    index_map: dict[str, int] = {}
    for index, node_raw in enumerate(nodes):
        if not isinstance(node_raw, Mapping):
            raise ValueError(f"node payload must be a mapping: {index}")
        node = dict(node_raw)
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"node id must be a non-empty string: {index}")
        if node_id in index_map:
            raise ValueError(f"duplicated node id in workflow: {node_id}")
        index_map[node_id] = index
    return index_map


def _ensure_mapping(payload: Mapping[str, Any], label: str) -> dict[str, Any]:
    """入力が辞書互換であることを検証して辞書化する。

    Args:
        payload: 検証対象データ。
        label: エラー文言で使う入力名。

    Returns:
        shallow copy した辞書データ。

    Raises:
        ValueError: payload が辞書互換でない場合。
    """
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(payload)
