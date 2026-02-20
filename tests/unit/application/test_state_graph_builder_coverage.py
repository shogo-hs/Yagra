"""Additional tests to cover missing lines in state_graph_builder.py."""

from __future__ import annotations

from typing import Any

import pytest

from yagra.adapters.outbound import InMemoryNodeRegistry
from yagra.application.use_cases.state_graph_builder import (
    GraphBuildError,
    _build_node_runner,
    _build_router,
    _invoke_handler,
    build_state_graph,
    build_state_schema_type,
)
from yagra.domain.entities import GraphSpec
from yagra.domain.entities.graph_schema import StateFieldSpec


def _make_spec(payload: dict[str, Any]) -> GraphSpec:
    return GraphSpec.model_validate(payload)


def _field(type_name: str, reducer: str | None = None) -> StateFieldSpec:
    return StateFieldSpec(type=type_name, reducer=reducer)


# ---------------------------------------------------------------------------
# build_state_schema_type: line 86 — unsupported field type raises GraphBuildError
# ---------------------------------------------------------------------------


def test_build_state_schema_type_raises_for_unsupported_type() -> None:
    """Line 86: GraphBuildError raised when an unknown type name is encountered.

    StateFieldSpec validates allowed types at the pydantic level, so we patch
    _PYTHON_TYPE_MAP to remove a known type, causing build_state_schema_type
    to hit the GraphBuildError branch.
    """
    from unittest.mock import patch

    import yagra.application.use_cases.state_graph_builder as _mod

    # Use a valid StateFieldSpec with type 'str', but remove 'str' from the map
    # so the lookup returns None and triggers the error.
    fake_spec = StateFieldSpec(type="str")
    schema = {"my_field": fake_spec}

    patched_map = {k: v for k, v in _mod._PYTHON_TYPE_MAP.items() if k != "str"}
    with patch.object(_mod, "_PYTHON_TYPE_MAP", patched_map):
        with pytest.raises(GraphBuildError, match="unsupported state field type"):
            build_state_schema_type(schema)


# ---------------------------------------------------------------------------
# build_state_graph: line 172 — trace_collector.wrap_node path
# ---------------------------------------------------------------------------


def test_build_state_graph_wraps_nodes_with_trace_collector() -> None:
    """Line 172: When trace_collector is provided, wrap_node is called for each non-subgraph node."""
    payload = {
        "version": "1.0",
        "start_at": "node_a",
        "end_at": ["node_a"],
        "nodes": [{"id": "node_a", "handler": "my_handler"}],
        "edges": [],
    }
    spec = _make_spec(payload)

    call_log: list[str] = []

    def my_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        call_log.append("executed")
        return dict(state)

    registry = InMemoryNodeRegistry({"my_handler": my_handler})

    wrapped_log: list[str] = []

    class _FakeTraceCollector:
        def wrap_node(self, node_id: str, handler: Any, handler_name: str) -> Any:
            wrapped_log.append(node_id)
            return handler  # return the original handler unchanged

    compiled = build_state_graph(spec, registry, trace_collector=_FakeTraceCollector())
    compiled.invoke({})

    assert "node_a" in wrapped_log
    assert "executed" in call_log


# ---------------------------------------------------------------------------
# build_state_graph: line 192 — add_node after spec validation (covered indirectly;
# this test targets a node using conditional edges to ensure full build_state_graph path)
# ---------------------------------------------------------------------------


def test_build_state_graph_conditional_edge_adds_correctly() -> None:
    """Line 192 coverage: state_graph.add_node called for conditional-source nodes."""
    payload = {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["branch_a", "branch_b"],
        "nodes": [
            {"id": "router", "handler": "router_handler"},
            {"id": "branch_a", "handler": "leaf_handler"},
            {"id": "branch_b", "handler": "leaf_handler"},
        ],
        "edges": [
            {"source": "router", "target": "branch_a", "condition": "a"},
            {"source": "router", "target": "branch_b", "condition": "b"},
        ],
    }
    spec = _make_spec(payload)

    def router_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        return {"__next__": state.get("route", "a")}

    def leaf_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        return {"done": True}

    registry = InMemoryNodeRegistry(
        {"router_handler": router_handler, "leaf_handler": leaf_handler}
    )

    compiled = build_state_graph(spec, registry)
    result = compiled.invoke({"route": "a"})
    assert result["done"] is True


# ---------------------------------------------------------------------------
# _split_edges: line 282 — duplicate conditional edge label raises
# ---------------------------------------------------------------------------


def test_split_edges_raises_on_duplicate_conditional_label() -> None:
    """Line 282: Duplicate condition label from same source raises GraphBuildError."""
    payload = {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["branch_a"],
        "nodes": [
            {"id": "router", "handler": "h"},
            {"id": "branch_a", "handler": "h"},
        ],
        "edges": [
            {"source": "router", "target": "branch_a", "condition": "same_label"},
            {"source": "router", "target": "branch_a", "condition": "same_label"},
        ],
    }
    spec = _make_spec(payload)
    registry = InMemoryNodeRegistry({"h": lambda s: s})

    with pytest.raises(GraphBuildError, match="duplicate conditional edge label"):
        build_state_graph(spec, registry)


# ---------------------------------------------------------------------------
# _validate_edge_source_conflicts: lines 297-298 — mixed conditional+normal edges
# ---------------------------------------------------------------------------


def test_validate_edge_source_conflicts_raises_for_mixed_edges() -> None:
    """Lines 297-298: Mixing conditional and unconditional edges from same source raises."""
    payload = {
        "version": "1.0",
        "start_at": "source",
        "end_at": ["dest_a", "dest_b"],
        "nodes": [
            {"id": "source", "handler": "h"},
            {"id": "dest_a", "handler": "h"},
            {"id": "dest_b", "handler": "h"},
        ],
        "edges": [
            {"source": "source", "target": "dest_a"},
            {"source": "source", "target": "dest_b", "condition": "maybe"},
        ],
    }
    spec = _make_spec(payload)
    registry = InMemoryNodeRegistry({"h": lambda s: s})

    with pytest.raises(GraphBuildError, match="mixed conditional and normal edges"):
        build_state_graph(spec, registry)


# ---------------------------------------------------------------------------
# _build_subgraph_node: lines 411-412 — load_graph_spec_from_workflow raises
# ---------------------------------------------------------------------------


def test_build_subgraph_node_raises_when_load_fails(tmp_path: Any) -> None:
    """Lines 411-412: When loading a subgraph YAML raises, GraphBuildError is re-raised."""
    # Create a syntactically valid file so the "not found" check passes,
    # but then make load_graph_spec_from_workflow raise
    sub_yaml = tmp_path / "broken_sub.yaml"
    sub_yaml.write_text("this is not valid yaml content: [")

    payload = {
        "version": "1.0",
        "start_at": "sub",
        "end_at": ["sub"],
        "nodes": [
            {
                "id": "sub",
                "handler": "subgraph",
                "params": {"workflow_ref": str(sub_yaml)},
            },
        ],
        "edges": [],
    }
    spec = _make_spec(payload)
    registry = InMemoryNodeRegistry({})

    with pytest.raises(GraphBuildError, match="failed to load subgraph"):
        build_state_graph(spec, registry, workflow_path=None)


# ---------------------------------------------------------------------------
# _build_node_runner: line 443 — non-mapping return from handler
# ---------------------------------------------------------------------------


def test_build_node_runner_raises_when_handler_returns_non_mapping() -> None:
    """Line 443: GraphBuildError raised when handler returns a non-Mapping value."""

    def bad_handler(state: dict[str, Any], params: dict[str, Any]) -> Any:
        return "this is not a mapping"  # noqa: PGH003

    runner = _build_node_runner(handler=bad_handler, node_params={})

    with pytest.raises(GraphBuildError, match="node handler must return a mapping"):
        runner({"key": "value"})


# ---------------------------------------------------------------------------
# _invoke_handler: lines 480-484 — both signatures fail with TypeError
# ---------------------------------------------------------------------------


def test_invoke_handler_raises_when_both_signatures_fail() -> None:
    """Lines 480-484: When handler(state, params) and handler(state) both raise TypeError."""

    def bad_handler() -> None:
        # Accepts zero arguments — both invocation attempts will raise TypeError
        pass

    with pytest.raises(GraphBuildError, match="node handler invocation failed"):
        _invoke_handler(handler=bad_handler, state={}, node_params={})


def test_invoke_handler_falls_back_to_single_arg_signature() -> None:
    """When handler(state, params) raises TypeError, handler(state) is tried next."""

    def single_arg_handler(state: dict[str, Any]) -> dict[str, Any]:
        return {"result": state.get("input", "none")}

    result = _invoke_handler(handler=single_arg_handler, state={"input": "test"}, node_params={})
    assert result == {"result": "test"}


# ---------------------------------------------------------------------------
# _build_router: lines 497-498 (non-string __next__) and 502-503 (unknown label)
# ---------------------------------------------------------------------------


def test_build_router_raises_when_next_is_not_string() -> None:
    """Lines 497-498: Router raises GraphBuildError when state['__next__'] is not a str."""
    route_map = {"option_a": "node_a", "option_b": "node_b"}
    router = _build_router(source="my_source", route_map=route_map)

    with pytest.raises(GraphBuildError, match="requires string '__next__'"):
        router({"__next__": 42})  # int instead of str

    with pytest.raises(GraphBuildError, match="requires string '__next__'"):
        router({})  # missing __next__ → None


def test_build_router_raises_when_next_label_is_unknown() -> None:
    """Lines 502-503: Router raises GraphBuildError when __next__ value not in route_map."""
    route_map = {"option_a": "node_a", "option_b": "node_b"}
    router = _build_router(source="my_source", route_map=route_map)

    with pytest.raises(GraphBuildError, match="unknown conditional route"):
        router({"__next__": "nonexistent_option"})


def test_build_router_returns_label_when_valid() -> None:
    """Happy path: router returns the correct label when __next__ is valid."""
    route_map = {"yes": "node_yes", "no": "node_no"}
    router = _build_router(source="checker", route_map=route_map)

    assert router({"__next__": "yes"}) == "yes"
    assert router({"__next__": "no"}) == "no"


# ---------------------------------------------------------------------------
# build_state_graph: line 192 — fan-out add_conditional_edges path
# ---------------------------------------------------------------------------


def test_build_state_graph_fan_out_edge_reaches_add_conditional_edges() -> None:
    """Line 192: build_state_graph calls state_graph.add_conditional_edges for fan-out edges."""
    payload = {
        "version": "1.0",
        "start_at": "prepare",
        "end_at": ["aggregate"],
        "state_schema": {
            "items": {"type": "list"},
            "results": {"type": "list", "reducer": "add"},
        },
        "nodes": [
            {"id": "prepare", "handler": "prepare_handler"},
            {"id": "process_item", "handler": "process_handler"},
            {"id": "aggregate", "handler": "aggregate_handler"},
        ],
        "edges": [
            {
                "source": "prepare",
                "target": "process_item",
                "fan_out": {"items_key": "items", "item_key": "item"},
            },
            {"source": "process_item", "target": "aggregate"},
        ],
    }
    spec = _make_spec(payload)

    def prepare_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        return {"items": ["a", "b"]}

    def process_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        return {"results": [state.get("item", "")]}

    def aggregate_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        return {"done": True}

    registry = InMemoryNodeRegistry(
        {
            "prepare_handler": prepare_handler,
            "process_handler": process_handler,
            "aggregate_handler": aggregate_handler,
        }
    )

    # build_state_graph must reach line 192 (fan-out add_conditional_edges)
    compiled = build_state_graph(spec, registry)
    assert compiled is not None
