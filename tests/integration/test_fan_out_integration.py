"""Integration tests for Send API fan-out / fan-in pattern."""

from collections.abc import Mapping
from typing import Any

from yagra.adapters.outbound import InMemoryNodeRegistry
from yagra.application.use_cases.state_graph_builder import build_state_graph
from yagra.domain.entities import GraphSpec


def _make_spec(payload: dict[str, Any]) -> GraphSpec:
    return GraphSpec.model_validate(payload)


# ---------------------------------------------------------------------------
# Direct LangGraph Send API verification (confirms underlying behavior)
# ---------------------------------------------------------------------------


def test_fan_out_fan_in_via_langgraph_directly() -> None:
    """Verifies that LangGraph Send API supports parallel fan-out / fan-in.

    This test uses LangGraph directly (not Yagra YAML) to confirm the underlying
    behavior that Yagra's fan_out edge feature relies on.
    """
    import operator

    # Build TypedDict via functional form to avoid forward-ref issues
    from typing import Annotated, TypedDict, cast

    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send

    WorkflowState = TypedDict(  # noqa: UP013
        "WorkflowState",
        {
            "topics": list,
            "summaries": Annotated[list, operator.add],
        },
        total=False,
    )

    graph: StateGraph = StateGraph(cast(type, WorkflowState))

    def summarize(state: WorkflowState) -> WorkflowState:
        topic = state.get("topic", "?")
        return {"summaries": [f"summary:{topic}"]}

    graph.add_node("summarize", summarize)

    def fan_out(state: WorkflowState) -> list[Send]:
        return [Send("summarize", {"topic": t}) for t in state.get("topics", [])]

    graph.add_conditional_edges(START, fan_out)
    graph.add_edge("summarize", END)

    compiled = graph.compile()
    result = compiled.invoke({"topics": ["AI", "ML", "DL"], "summaries": []})  # type: ignore[arg-type]

    assert len(result["summaries"]) == 3
    assert set(result["summaries"]) == {"summary:AI", "summary:ML", "summary:DL"}


# ---------------------------------------------------------------------------
# Yagra YAML with fan_out edge
# ---------------------------------------------------------------------------


def test_build_state_graph_with_fan_out_edge() -> None:
    """End-to-end test: YAML with fan_out edge dispatches Send to target node.

    Note: Send API passes item_key only to the target node's local state.
    The global state_schema should only define keys that are truly shared.
    The 'task' field should NOT be defined in state_schema when used as a Send payload
    (it is local to each parallel Send invocation).
    """
    collected: list[str] = []

    def process_handler(state: Mapping[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        task = state.get("task", "?")
        collected.append(task)
        return {"results": [f"done:{task}"]}

    payload = {
        "version": "1.0",
        "start_at": "dispatch",
        "end_at": ["process"],
        "nodes": [
            {"id": "dispatch", "handler": "noop"},
            {"id": "process", "handler": "process"},
        ],
        "edges": [
            {
                "source": "dispatch",
                "target": "process",
                "fan_out": {"items_key": "tasks", "item_key": "task"},
            },
        ],
        # Note: 'task' is NOT in state_schema. It's a per-Send local value.
        # Only global aggregation state (results with reducer:add) is defined here.
        "state_schema": {
            "tasks": {"type": "list"},
            "results": {"type": "list", "reducer": "add"},
        },
    }

    spec = _make_spec(payload)

    def noop_handler(state: Mapping[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        return {}

    registry = InMemoryNodeRegistry({"noop": noop_handler, "process": process_handler})
    compiled = build_state_graph(spec, registry)

    result = compiled.invoke({"tasks": ["task1", "task2", "task3"], "results": []})

    assert len(result["results"]) == 3
    assert set(result["results"]) == {"done:task1", "done:task2", "done:task3"}
    assert set(collected) == {"task1", "task2", "task3"}


def test_build_state_graph_fan_out_with_empty_list() -> None:
    """Fan-out with empty items list produces no parallel executions."""
    executed: list[str] = []

    def process_handler(state: Mapping[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        executed.append(state.get("item", "?"))
        return {"results": [state.get("item", "?")]}

    payload = {
        "version": "1.0",
        "start_at": "source",
        "end_at": ["target"],
        "nodes": [
            {"id": "source", "handler": "noop"},
            {"id": "target", "handler": "process"},
        ],
        "edges": [
            {
                "source": "source",
                "target": "target",
                "fan_out": {"items_key": "items", "item_key": "item"},
            },
        ],
        "state_schema": {
            "items": {"type": "list"},
            "results": {"type": "list", "reducer": "add"},
        },
    }

    spec = _make_spec(payload)
    registry = InMemoryNodeRegistry({"noop": lambda s, p: {}, "process": process_handler})
    compiled = build_state_graph(spec, registry)

    result = compiled.invoke({"items": [], "results": []})
    assert result["results"] == []
    assert executed == []


def test_build_state_graph_fan_out_single_item() -> None:
    """Fan-out with single item executes exactly once."""
    executed: list[str] = []

    def process_handler(state: Mapping[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        name = state.get("name", "?")
        executed.append(name)
        return {"outputs": [f"processed:{name}"]}

    payload = {
        "version": "1.0",
        "start_at": "fan",
        "end_at": ["worker"],
        "nodes": [
            {"id": "fan", "handler": "noop"},
            {"id": "worker", "handler": "process"},
        ],
        "edges": [
            {
                "source": "fan",
                "target": "worker",
                "fan_out": {"items_key": "names", "item_key": "name"},
            },
        ],
        "state_schema": {
            "names": {"type": "list"},
            "outputs": {"type": "list", "reducer": "add"},
        },
    }

    spec = _make_spec(payload)
    registry = InMemoryNodeRegistry({"noop": lambda s, p: {}, "process": process_handler})
    compiled = build_state_graph(spec, registry)

    result = compiled.invoke({"names": ["alice"], "outputs": []})
    assert result["outputs"] == ["processed:alice"]
    assert executed == ["alice"]
