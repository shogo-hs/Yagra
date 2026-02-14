"""Workflow フォーム入力を workflow データへ適用する。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


def apply_form_edits(
    workflow: Mapping[str, Any],
    node_creates: Sequence[Mapping[str, Any]] | None = None,
    node_edits: Sequence[Mapping[str, Any]] | None = None,
    edge_creates: Sequence[Mapping[str, Any]] | None = None,
    edge_rewires: Sequence[Mapping[str, Any]] | None = None,
    edge_edits: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """フォーム編集内容を workflow へ適用して新しいデータを返す。

    Args:
        workflow: 変更対象 workflow データ。
        node_creates: ノード追加の一覧。
        node_edits: ノード編集の一覧。
        edge_creates: エッジ追加の一覧。
        edge_rewires: エッジ再接続の一覧。
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

    _apply_node_creates(nodes=nodes, node_creates=node_creates or [])
    _apply_node_edits(nodes=nodes, node_edits=node_edits or [])
    _apply_edge_creates(nodes=nodes, edges=edges, edge_creates=edge_creates or [])
    _apply_edge_rewires(nodes=nodes, edges=edges, edge_rewires=edge_rewires or [])
    _apply_edge_edits(edges=edges, edge_edits=edge_edits or [])
    return patched


def _apply_node_creates(nodes: list[Any], node_creates: Sequence[Mapping[str, Any]]) -> None:
    """ノード追加一覧を workflow.nodes へ適用する。

    Args:
        nodes: workflow のノード配列。
        node_creates: ノード追加一覧。

    Raises:
        ValueError: ノード追加入力が不正な場合。
    """
    node_indexes = _build_node_index(nodes)
    for create in node_creates:
        create_mapping = _ensure_mapping(create, label="node create")
        node_id_raw = create_mapping.get("node_id")
        handler_raw = create_mapping.get("handler")
        if not isinstance(node_id_raw, str) or not node_id_raw.strip():
            raise ValueError("node create requires non-empty 'node_id'")
        if not isinstance(handler_raw, str) or not handler_raw.strip():
            raise ValueError("node create requires non-empty 'handler'")

        node_id = node_id_raw.strip()
        if node_id in node_indexes:
            raise ValueError(f"node already exists: {node_id}")

        params_payload = create_mapping.get("params")
        node_payload: dict[str, Any] = {"id": node_id, "handler": handler_raw.strip()}
        if params_payload is not None:
            if not isinstance(params_payload, Mapping):
                raise ValueError(f"node params must be a mapping: {node_id}")
            node_payload["params"] = deepcopy(dict(params_payload))

        nodes.append(node_payload)
        node_indexes[node_id] = len(nodes) - 1


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
        normalized = _normalize_optional_condition(
            edit_mapping.get("condition"),
            edge_index=edge_index,
        )
        if normalized is None:
            target_edge.pop("condition", None)
        else:
            target_edge["condition"] = normalized


def _apply_edge_creates(
    nodes: list[Any],
    edges: list[Any],
    edge_creates: Sequence[Mapping[str, Any]],
) -> None:
    """エッジ追加一覧を workflow.edges へ適用する。

    Args:
        nodes: workflow のノード配列。
        edges: workflow のエッジ配列。
        edge_creates: エッジ追加一覧。

    Raises:
        ValueError: エッジ追加入力が不正な場合。
    """
    known_node_ids = set(_build_node_index(nodes))
    for create in edge_creates:
        create_mapping = _ensure_mapping(create, label="edge create")
        source = _required_node_reference(
            create_mapping.get("source"),
            field_name="source",
            known_node_ids=known_node_ids,
        )
        target = _required_node_reference(
            create_mapping.get("target"),
            field_name="target",
            known_node_ids=known_node_ids,
        )

        edge_payload: dict[str, Any] = {"source": source, "target": target}
        if "condition" in create_mapping:
            condition = _normalize_optional_condition(
                create_mapping.get("condition"),
                edge_index=len(edges),
            )
            if condition is not None:
                edge_payload["condition"] = condition
        edges.append(edge_payload)


def _apply_edge_rewires(
    nodes: list[Any],
    edges: list[Any],
    edge_rewires: Sequence[Mapping[str, Any]],
) -> None:
    """エッジ再接続一覧を workflow.edges へ適用する。

    Args:
        nodes: workflow のノード配列。
        edges: workflow のエッジ配列。
        edge_rewires: エッジ再接続一覧。

    Raises:
        ValueError: エッジ再接続入力が不正な場合。
    """
    known_node_ids = set(_build_node_index(nodes))
    for rewire in edge_rewires:
        rewire_mapping = _ensure_mapping(rewire, label="edge rewire")
        edge_index = rewire_mapping.get("edge_index")
        if not isinstance(edge_index, int):
            raise ValueError("edge rewire requires integer 'edge_index'")
        if edge_index < 0 or edge_index >= len(edges):
            raise ValueError(f"edge index out of range: {edge_index}")

        target_edge = edges[edge_index]
        if not isinstance(target_edge, dict):
            raise ValueError(f"edge payload must be a mapping: {edge_index}")

        has_update = False
        if "source" in rewire_mapping:
            target_edge["source"] = _required_node_reference(
                rewire_mapping.get("source"),
                field_name="source",
                known_node_ids=known_node_ids,
            )
            has_update = True
        if "target" in rewire_mapping:
            target_edge["target"] = _required_node_reference(
                rewire_mapping.get("target"),
                field_name="target",
                known_node_ids=known_node_ids,
            )
            has_update = True
        if "condition" in rewire_mapping:
            normalized = _normalize_optional_condition(
                rewire_mapping.get("condition"),
                edge_index=edge_index,
            )
            if normalized is None:
                target_edge.pop("condition", None)
            else:
                target_edge["condition"] = normalized
            has_update = True

        if not has_update:
            raise ValueError(
                "edge rewire requires at least one of 'source', 'target' or 'condition'"
            )


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


def _required_node_reference(
    value: Any,
    field_name: str,
    known_node_ids: set[str],
) -> str:
    """ノード参照文字列を検証して正規化する。

    Args:
        value: 入力値。
        field_name: 対象フィールド名。
        known_node_ids: 既知ノードID集合。

    Returns:
        検証済みノードID。

    Raises:
        ValueError: 参照が不正、または未定義ノードの場合。
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"edge {field_name} must be a non-empty string")
    normalized = value.strip()
    if normalized not in known_node_ids:
        raise ValueError(f"edge {field_name} node not found: {normalized}")
    return normalized


def _normalize_optional_condition(value: Any, edge_index: int) -> str | None:
    """Condition 入力を正規化する。

    Args:
        value: 入力値。
        edge_index: 対象エッジindex。

    Returns:
        正規化済み condition。未設定相当は `None`。

    Raises:
        ValueError: condition 型が不正な場合。
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"edge condition must be a string or null: {edge_index}")
    normalized = value.strip()
    return normalized if normalized else None


def _ensure_mapping(payload: Any, label: str) -> dict[str, Any]:
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
