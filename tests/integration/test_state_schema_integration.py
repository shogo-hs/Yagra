"""Integration tests for state_schema / MessagesState support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import AIMessage, HumanMessage

from yagra import Yagra


def _write_workflow(tmp_path: Path, payload: dict[str, Any]) -> Path:
    p = tmp_path / "workflow.yaml"
    p.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# state_schema omitted → legacy dict behavior (backward compat)
# ---------------------------------------------------------------------------


def test_state_schema_omitted_works_as_before(tmp_path: Path) -> None:
    """Workflows without state_schema continue to work exactly as before."""
    workflow_path = _write_workflow(
        tmp_path,
        {
            "version": "1.0",
            "start_at": "greet",
            "end_at": ["greet"],
            "nodes": [{"id": "greet", "handler": "greet_handler"}],
            "edges": [],
        },
    )

    def greet_handler(state: dict, params: dict) -> dict:
        return {"greeting": f"Hello, {state.get('name', 'world')}"}

    engine = Yagra.from_workflow(workflow_path, registry={"greet_handler": greet_handler})
    result = engine.invoke({"name": "Yagra"})
    assert result["greeting"] == "Hello, Yagra"


# ---------------------------------------------------------------------------
# state_schema with plain types (str, int, etc.)
# ---------------------------------------------------------------------------


def test_state_schema_plain_types(tmp_path: Path) -> None:
    """state_schema with str/int fields builds correctly and executes."""
    workflow_path = _write_workflow(
        tmp_path,
        {
            "version": "1.0",
            "start_at": "counter",
            "end_at": ["counter"],
            "nodes": [{"id": "counter", "handler": "counter_handler"}],
            "edges": [],
            "state_schema": {
                "count": {"type": "int"},
                "label": {"type": "str"},
            },
        },
    )

    def counter_handler(state: dict, params: dict) -> dict:
        return {"count": state.get("count", 0) + 1, "label": "done"}

    engine = Yagra.from_workflow(workflow_path, registry={"counter_handler": counter_handler})
    result = engine.invoke({"count": 5})
    assert result["count"] == 6
    assert result["label"] == "done"


# ---------------------------------------------------------------------------
# state_schema with messages type → add_messages reducer
# ---------------------------------------------------------------------------


def test_state_schema_messages_type_appends_messages(tmp_path: Path) -> None:
    """Messages field with add_messages reducer appends instead of overwriting."""
    workflow_path = _write_workflow(
        tmp_path,
        {
            "version": "1.0",
            "start_at": "chat",
            "end_at": ["chat"],
            "nodes": [{"id": "chat", "handler": "chat_handler"}],
            "edges": [],
            "state_schema": {
                "messages": {"type": "messages"},
            },
        },
    )

    def chat_handler(state: dict, params: dict) -> dict:
        # Add an AI reply to the existing messages
        return {"messages": [AIMessage(content="Hi! How can I help?")]}

    engine = Yagra.from_workflow(workflow_path, registry={"chat_handler": chat_handler})

    # Invoke with an initial human message
    initial_message = HumanMessage(content="Hello!")
    result = engine.invoke({"messages": [initial_message]})

    # add_messages reducer should have appended: [HumanMessage, AIMessage]
    messages = result["messages"]
    assert len(messages) == 2
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert messages[0].content == "Hello!"
    assert messages[1].content == "Hi! How can I help?"


def test_state_schema_messages_not_overwritten_without_reducer(tmp_path: Path) -> None:
    """Without state_schema, messages field is overwritten (plain dict behavior)."""
    workflow_path = _write_workflow(
        tmp_path,
        {
            "version": "1.0",
            "start_at": "chat",
            "end_at": ["chat"],
            "nodes": [{"id": "chat", "handler": "chat_handler"}],
            "edges": [],
            # NO state_schema → plain dict
        },
    )

    def chat_handler(state: dict, params: dict) -> dict:
        return {"messages": [AIMessage(content="Hi!")]}

    engine = Yagra.from_workflow(workflow_path, registry={"chat_handler": chat_handler})

    result = engine.invoke({"messages": [HumanMessage(content="Hello!")]})
    # Without reducer, messages is overwritten by the handler's return value
    messages = result["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], AIMessage)


# ---------------------------------------------------------------------------
# state_schema: explicit state_schema kwarg takes precedence over YAML
# ---------------------------------------------------------------------------


def test_explicit_state_schema_takes_precedence_over_yaml(tmp_path: Path) -> None:
    """Explicitly passed state_schema overrides the YAML state_schema."""
    from typing import TypedDict

    workflow_path = _write_workflow(
        tmp_path,
        {
            "version": "1.0",
            "start_at": "node",
            "end_at": ["node"],
            "nodes": [{"id": "node", "handler": "handler"}],
            "edges": [],
            "state_schema": {"messages": {"type": "messages"}},  # YAML defines messages
        },
    )

    class CustomState(TypedDict, total=False):
        value: str

    def handler(state: dict, params: dict) -> dict:
        return {"value": "ok"}

    # Pass explicit state_schema → should use CustomState, not YAML's messages
    engine = Yagra.from_workflow(
        workflow_path,
        registry={"handler": handler},
        state_schema=CustomState,
    )
    result = engine.invoke({"value": "initial"})
    assert result["value"] == "ok"


# ---------------------------------------------------------------------------
# state_schema with multi-step workflow and messages reducer
# ---------------------------------------------------------------------------


def test_state_schema_messages_multi_step(tmp_path: Path) -> None:
    """Messages accumulate correctly across multiple nodes."""
    workflow_path = _write_workflow(
        tmp_path,
        {
            "version": "1.0",
            "start_at": "node_a",
            "end_at": ["node_b"],
            "nodes": [
                {"id": "node_a", "handler": "handler_a"},
                {"id": "node_b", "handler": "handler_b"},
            ],
            "edges": [{"source": "node_a", "target": "node_b"}],
            "state_schema": {
                "messages": {"type": "messages"},
                "step": {"type": "int"},
            },
        },
    )

    def handler_a(state: dict, params: dict) -> dict:
        return {
            "messages": [AIMessage(content="Step A response")],
            "step": 1,
        }

    def handler_b(state: dict, params: dict) -> dict:
        return {
            "messages": [AIMessage(content="Step B response")],
            "step": 2,
        }

    engine = Yagra.from_workflow(
        workflow_path,
        registry={"handler_a": handler_a, "handler_b": handler_b},
    )

    result = engine.invoke({"messages": [HumanMessage(content="Start")], "step": 0})

    # add_messages accumulates: HumanMessage + AI(A) + AI(B)
    assert len(result["messages"]) == 3
    assert result["step"] == 2
