"""Tests for build_state_schema_type."""

from __future__ import annotations

from typing import get_type_hints

from yagra.application.use_cases.state_graph_builder import build_state_schema_type
from yagra.domain.entities.graph_schema import StateFieldSpec


def _field(type_name: str) -> StateFieldSpec:
    return StateFieldSpec(type=type_name)


def test_build_state_schema_type_returns_dict_for_empty() -> None:
    result = build_state_schema_type({})
    assert result is dict


def test_build_state_schema_type_returns_type_for_str_field() -> None:
    schema = {"result": _field("str")}
    result = build_state_schema_type(schema)
    assert result is not dict
    hints = get_type_hints(result)
    assert hints["result"] is str


def test_build_state_schema_type_returns_correct_python_types() -> None:
    schema = {
        "name": _field("str"),
        "count": _field("int"),
        "score": _field("float"),
        "active": _field("bool"),
        "items": _field("list"),
        "meta": _field("dict"),
    }
    result = build_state_schema_type(schema)
    hints = get_type_hints(result)
    assert hints["name"] is str
    assert hints["count"] is int
    assert hints["score"] is float
    assert hints["active"] is bool
    assert hints["items"] is list
    assert hints["meta"] is dict


def test_build_state_schema_type_messages_field_uses_annotated() -> None:
    from typing import get_args, get_origin

    from langgraph.graph.message import add_messages

    schema = {"messages": _field("messages")}
    result = build_state_schema_type(schema)
    hints = get_type_hints(result, include_extras=True)
    messages_hint = hints["messages"]

    # Should be Annotated[list, add_messages]
    origin = get_origin(messages_hint)
    assert origin is not None  # Annotated has an origin
    args = get_args(messages_hint)
    assert args[0] is list
    assert args[1] is add_messages


def test_build_state_schema_type_mixed_with_messages() -> None:
    from typing import get_args

    from langgraph.graph.message import add_messages

    schema = {
        "messages": _field("messages"),
        "result": _field("str"),
    }
    result = build_state_schema_type(schema)
    hints = get_type_hints(result, include_extras=True)

    assert hints["result"] is str
    args = get_args(hints["messages"])
    assert args[0] is list
    assert args[1] is add_messages
