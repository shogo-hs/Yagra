"""GraphSpec から LangGraph StateGraph を構築する。"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from copy import deepcopy
from os import PathLike
from typing import Any, cast

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from yagra.application.use_cases.workflow_loader import load_graph_spec_from_workflow
from yagra.domain.entities import GraphSpec
from yagra.ports.outbound import NodeRegistryPort
from yagra.ports.outbound.node_registry import NodeHandler


class GraphBuildError(ValueError):
    """StateGraph の構築に失敗した場合の例外。"""


def build_state_graph(
    spec: GraphSpec,
    registry: NodeRegistryPort,
    state_schema: Any = dict,
) -> CompiledStateGraph:
    """`GraphSpec` と Registry からコンパイル済み StateGraph を構築する。

    Args:
        spec: 検証済みの workflow 定義。
        registry: handler 名を callable へ解決するレジストリ。
        state_schema: LangGraph の状態スキーマ。既定は `dict`。

    Returns:
        コンパイル済みの `CompiledStateGraph`。

    Raises:
        GraphBuildError: エッジ定義不整合や条件分岐解決不正がある場合。
    """
    state_graph = StateGraph(state_schema)

    for node in spec.nodes:
        handler = registry.resolve(node.handler)
        state_graph.add_node(node.id, _build_node_runner(handler=handler, node_params=node.params))

    state_graph.set_entry_point(spec.start_at)

    conditional_by_source, unconditional_by_source = _split_edges(spec)
    _validate_edge_source_conflicts(conditional_by_source, unconditional_by_source)

    for source, targets in unconditional_by_source.items():
        for target in targets:
            state_graph.add_edge(source, target)

    for source, route_map in conditional_by_source.items():
        hashable_route_map = cast(dict[Hashable, str], dict(route_map))
        state_graph.add_conditional_edges(
            source,
            _build_router(source=source, route_map=route_map),
            hashable_route_map,
        )

    for end_node in spec.end_at:
        state_graph.set_finish_point(end_node)

    return state_graph.compile()


def build_from_workflow_path(
    workflow_path: str | PathLike[str],
    registry: NodeRegistryPort,
    bundle_root: str | PathLike[str] | None = None,
    state_schema: Any = dict,
) -> CompiledStateGraph:
    """Workflow パスを入口に `CompiledStateGraph` を構築する。

    Args:
        workflow_path: 入口 workflow ファイルのパス。
        registry: handler 名を callable へ解決するレジストリ。
        bundle_root: 分割参照時の基準ディレクトリ。未指定時は workflow 親を使う。
        state_schema: LangGraph の状態スキーマ。既定は `dict`。

    Returns:
        コンパイル済みの `CompiledStateGraph`。
    """
    spec = load_graph_spec_from_workflow(workflow_path=workflow_path, bundle_root=bundle_root)
    return build_state_graph(spec=spec, registry=registry, state_schema=state_schema)


def _split_edges(spec: GraphSpec) -> tuple[dict[str, dict[str, str]], dict[str, list[str]]]:
    """エッジを条件付き/通常遷移に分類する。"""
    conditional_by_source: dict[str, dict[str, str]] = {}
    unconditional_by_source: dict[str, list[str]] = {}

    for edge in spec.edges:
        if edge.condition is None:
            unconditional_by_source.setdefault(edge.source, []).append(edge.target)
            continue

        route_map = conditional_by_source.setdefault(edge.source, {})
        if edge.condition in route_map:
            raise GraphBuildError(
                f"duplicate conditional edge label '{edge.condition}' for source '{edge.source}'"
            )
        route_map[edge.condition] = edge.target

    return conditional_by_source, unconditional_by_source


def _validate_edge_source_conflicts(
    conditional_by_source: Mapping[str, Any],
    unconditional_by_source: Mapping[str, Any],
) -> None:
    """同一 source で条件付き/通常遷移が混在していないか確認する。"""
    conflict_sources = sorted(set(conditional_by_source) & set(unconditional_by_source))
    if conflict_sources:
        labels = ", ".join(conflict_sources)
        raise GraphBuildError(f"mixed conditional and normal edges are not allowed: {labels}")


def _build_node_runner(handler: NodeHandler, node_params: Mapping[str, Any]) -> NodeHandler:
    """ノード実行用のラッパー callable を返す。"""
    frozen_params = deepcopy(dict(node_params))

    def _run(state: Mapping[str, Any]) -> dict[str, Any]:
        result = _invoke_handler(handler=handler, state=state, node_params=frozen_params)
        if not isinstance(result, Mapping):
            raise GraphBuildError("node handler must return a mapping state update")
        merged_state = dict(state)
        merged_state.update(dict(result))
        return merged_state

    return _run


def _invoke_handler(
    handler: NodeHandler,
    state: Mapping[str, Any],
    node_params: Mapping[str, Any],
) -> Any:
    """Handler を `handler(state, params)` 優先で呼び出す。"""
    try:
        return handler(dict(state), dict(node_params))
    except TypeError:
        try:
            return handler(dict(state))
        except TypeError as exc_without_params:
            raise GraphBuildError(
                "node handler invocation failed for both signatures: "
                "handler(state, params) and handler(state)"
            ) from exc_without_params


def _build_router(source: str, route_map: Mapping[str, str]) -> NodeHandler:
    """`__next__` キーから条件遷移先を選択するルーターを返す。"""
    allowed = sorted(route_map.keys())

    def _route(state: Mapping[str, Any]) -> str:
        label = state.get("__next__")
        if not isinstance(label, str):
            joined = ", ".join(allowed)
            raise GraphBuildError(
                f"conditional route for '{source}' requires string '__next__' in state (allowed: {joined})"
            )
        if label not in route_map:
            joined = ", ".join(allowed)
            raise GraphBuildError(
                f"unknown conditional route '{label}' for '{source}' (allowed: {joined})"
            )
        return label

    return _route
