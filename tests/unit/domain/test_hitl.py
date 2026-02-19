"""G-09: Tests for HITL (Human-in-the-Loop) functionality.

Tests the interrupt_before / interrupt_after fields of GraphSpec
and their integration with the state_graph_builder checkpointer.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from yagra.domain.entities import GraphSpec


def _base_payload() -> dict[str, Any]:
    """Returns a minimal GraphSpec payload.

    Returns:
        GraphSpec payload dictionary for testing.
    """
    return {
        "version": "1.0",
        "start_at": "nodeA",
        "end_at": ["nodeB"],
        "nodes": [
            {"id": "nodeA", "handler": "handler_a"},
            {"id": "nodeB", "handler": "handler_b"},
        ],
        "edges": [
            {"source": "nodeA", "target": "nodeB"},
        ],
        "params": {},
    }


# --- GraphSpec field tests ---


def test_graph_spec_interrupt_before_defaults_to_empty() -> None:
    """Confirms that the default value of interrupt_before is an empty list."""
    payload = _base_payload()
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_before == []


def test_graph_spec_interrupt_after_defaults_to_empty() -> None:
    """Confirms that the default value of interrupt_after is an empty list."""
    payload = _base_payload()
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_after == []


def test_graph_spec_interrupt_before_accepts_node_ids() -> None:
    """Confirms that a list of node IDs can be set in interrupt_before."""
    payload = _base_payload()
    payload["interrupt_before"] = ["nodeA"]
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_before == ["nodeA"]


def test_graph_spec_interrupt_after_accepts_node_ids() -> None:
    """Confirms that a list of node IDs can be set in interrupt_after."""
    payload = _base_payload()
    payload["interrupt_after"] = ["nodeA"]
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_after == ["nodeA"]


def test_graph_spec_interrupt_before_accepts_multiple_nodes() -> None:
    """Confirms that multiple node IDs can be set in interrupt_before."""
    payload = _base_payload()
    payload["nodes"].append({"id": "nodeC", "handler": "handler_c"})
    payload["edges"].append({"source": "nodeB", "target": "nodeC"})
    payload["end_at"] = ["nodeC"]
    payload["interrupt_before"] = ["nodeA", "nodeB"]
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_before == ["nodeA", "nodeB"]


def test_graph_spec_interrupt_fields_serialize_to_yaml_compatible() -> None:
    """Confirms that interrupt_before / interrupt_after are serializable."""
    payload = _base_payload()
    payload["interrupt_before"] = ["nodeA"]
    payload["interrupt_after"] = ["nodeB"]
    spec = GraphSpec.model_validate(payload)

    dumped = spec.model_dump()

    assert dumped["interrupt_before"] == ["nodeA"]
    assert dumped["interrupt_after"] == ["nodeB"]


# --- Validation tests ---


def test_validation_detects_unknown_interrupt_before_node() -> None:
    """Confirms that an undefined node ID in interrupt_before is detected as an issue."""
    from yagra.domain.services.schema_validator import collect_graph_structure_issues

    payload = _base_payload()
    payload["interrupt_before"] = ["nonexistent_node"]
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert any("interrupt_before" in str(issue.location) for issue in issues)
    assert any("nonexistent_node" in issue.message for issue in issues)


def test_validation_detects_unknown_interrupt_after_node() -> None:
    """Confirms that an undefined node ID in interrupt_after is detected as an issue."""
    from yagra.domain.services.schema_validator import collect_graph_structure_issues

    payload = _base_payload()
    payload["interrupt_after"] = ["nonexistent_node"]
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert any("interrupt_after" in str(issue.location) for issue in issues)
    assert any("nonexistent_node" in issue.message for issue in issues)


def test_validation_passes_for_valid_interrupt_nodes() -> None:
    """Confirms that no issues are reported when valid node IDs are set in interrupt_before / interrupt_after."""
    from yagra.domain.services.schema_validator import collect_graph_structure_issues

    payload = _base_payload()
    payload["interrupt_before"] = ["nodeA"]
    payload["interrupt_after"] = ["nodeB"]
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    interrupt_issues = [i for i in issues if "interrupt" in str(i.location)]
    assert interrupt_issues == []


# --- Integration tests with build_state_graph ---


def test_build_state_graph_without_checkpointer_ignores_interrupts() -> None:
    """Confirms that interrupts are disabled (compilation succeeds) without a checkpointer."""
    from yagra.adapters.outbound import InMemoryNodeRegistry
    from yagra.application.use_cases.state_graph_builder import build_state_graph
    from yagra.domain.entities import GraphSpec

    payload = _base_payload()
    payload["interrupt_before"] = ["nodeA"]
    spec = GraphSpec.model_validate(payload)

    registry = InMemoryNodeRegistry(
        {
            "handler_a": lambda s, p: s,
            "handler_b": lambda s, p: s,
        }
    )

    # Confirm that no compile error occurs even with checkpointer=None
    compiled = build_state_graph(spec, registry, checkpointer=None)
    assert compiled is not None


def test_build_state_graph_with_checkpointer_passes_interrupts() -> None:
    """Confirms that interrupt_before is passed to compile() when a checkpointer is provided."""
    from yagra.adapters.outbound import InMemoryNodeRegistry
    from yagra.application.use_cases.state_graph_builder import build_state_graph
    from yagra.domain.entities import GraphSpec

    payload = _base_payload()
    payload["interrupt_before"] = ["nodeA"]
    spec = GraphSpec.model_validate(payload)

    registry = InMemoryNodeRegistry(
        {
            "handler_a": lambda s, p: s,
            "handler_b": lambda s, p: s,
        }
    )

    mock_checkpointer = MagicMock()

    with patch(
        "yagra.application.use_cases.state_graph_builder.StateGraph.compile"
    ) as mock_compile:
        mock_compile.return_value = MagicMock()
        build_state_graph(spec, registry, checkpointer=mock_checkpointer)

        mock_compile.assert_called_once()
        call_kwargs = mock_compile.call_args.kwargs
        assert call_kwargs.get("checkpointer") is mock_checkpointer
        assert call_kwargs.get("interrupt_before") == ["nodeA"]


# --- API tests for Yagra.from_workflow / invoke / resume ---


def test_yagra_from_workflow_accepts_checkpointer(tmp_path: Any) -> None:
    """Confirms that Yagra.from_workflow accepts the checkpointer keyword argument.

    Args:
        tmp_path: pytest fixture providing a temporary directory.
    """
    import yaml
    from langgraph.checkpoint.memory import MemorySaver

    from yagra import Yagra

    workflow_yaml = {
        "version": "1.0",
        "start_at": "nodeA",
        "end_at": ["nodeB"],
        "nodes": [
            {"id": "nodeA", "handler": "handler_a"},
            {"id": "nodeB", "handler": "handler_b"},
        ],
        "edges": [{"source": "nodeA", "target": "nodeB"}],
        "params": {},
    }
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(yaml.dump(workflow_yaml))

    registry: dict[str, Any] = {
        "handler_a": lambda s, p: s,
        "handler_b": lambda s, p: s,
    }

    checkpointer = MemorySaver()

    # Confirm that no exception is raised when checkpointer is passed
    yagra = Yagra.from_workflow(workflow_path, registry, checkpointer=checkpointer)
    assert yagra is not None


def test_yagra_invoke_accepts_thread_id(tmp_path: Any) -> None:
    """Confirms that Yagra.invoke accepts the thread_id keyword argument.

    Args:
        tmp_path: pytest fixture providing a temporary directory.
    """
    import yaml
    from langgraph.checkpoint.memory import MemorySaver

    from yagra import Yagra

    workflow_yaml = {
        "version": "1.0",
        "start_at": "nodeA",
        "end_at": ["nodeB"],
        "nodes": [
            {"id": "nodeA", "handler": "handler_a"},
            {"id": "nodeB", "handler": "handler_b"},
        ],
        "edges": [{"source": "nodeA", "target": "nodeB"}],
        "params": {},
        "interrupt_before": [],
    }
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(yaml.dump(workflow_yaml))

    registry: dict[str, Any] = {
        "handler_a": lambda s, p: s,
        "handler_b": lambda s, p: s,
    }

    checkpointer = MemorySaver()
    yagra = Yagra.from_workflow(workflow_path, registry, checkpointer=checkpointer)

    # Confirm that invoke can be called with thread_id
    result = yagra.invoke({"key": "value"}, thread_id="test-thread-1")
    assert isinstance(result, dict)


def test_yagra_resume_accepts_thread_id(tmp_path: Any) -> None:
    """Confirms that Yagra.resume accepts the thread_id keyword argument.

    Verifies the flow of interrupting with interrupt_before and then resuming.

    Args:
        tmp_path: pytest fixture providing a temporary directory.
    """
    import yaml
    from langgraph.checkpoint.memory import MemorySaver

    from yagra import Yagra

    workflow_yaml = {
        "version": "1.0",
        "start_at": "nodeA",
        "end_at": ["nodeB"],
        "nodes": [
            {"id": "nodeA", "handler": "handler_a"},
            {"id": "nodeB", "handler": "handler_b"},
        ],
        "edges": [{"source": "nodeA", "target": "nodeB"}],
        "params": {},
        "interrupt_before": ["nodeB"],
    }
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(yaml.dump(workflow_yaml))

    registry: dict[str, Any] = {
        "handler_a": lambda s, p: {**s, "visited_a": True},
        "handler_b": lambda s, p: {**s, "visited_b": True},
    }

    checkpointer = MemorySaver()
    yagra = Yagra.from_workflow(workflow_path, registry, checkpointer=checkpointer)

    thread_id = "hitl-test-thread"

    # Interrupt before nodeB on invoke
    result1 = yagra.invoke({"input": "hello"}, thread_id=thread_id)
    # After interrupt, nodeB has not run yet so visited_b does not exist
    assert result1.get("visited_a") is True
    assert "visited_b" not in result1

    # Resume from the interrupt point
    result2 = yagra.resume(thread_id=thread_id)
    assert result2.get("visited_b") is True


def test_yagra_resume_with_state_update(tmp_path: Any) -> None:
    """Confirms that Yagra.resume can receive a state update.

    Args:
        tmp_path: pytest fixture providing a temporary directory.
    """
    import yaml
    from langgraph.checkpoint.memory import MemorySaver

    from yagra import Yagra

    workflow_yaml = {
        "version": "1.0",
        "start_at": "nodeA",
        "end_at": ["nodeB"],
        "nodes": [
            {"id": "nodeA", "handler": "handler_a"},
            {"id": "nodeB", "handler": "handler_b"},
        ],
        "edges": [{"source": "nodeA", "target": "nodeB"}],
        "params": {},
        "interrupt_before": ["nodeB"],
    }
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(yaml.dump(workflow_yaml))

    # nodeB checks state["approved"] and records the result
    registry: dict[str, Any] = {
        "handler_a": lambda s, p: s,
        "handler_b": lambda s, p: {**s, "result": "approved" if s.get("approved") else "rejected"},
    }

    checkpointer = MemorySaver()
    yagra = Yagra.from_workflow(workflow_path, registry, checkpointer=checkpointer)

    thread_id = "hitl-update-thread"

    # Interrupt on invoke
    yagra.invoke({"input": "review me"}, thread_id=thread_id)

    # Human injects approved=True and resumes
    result = yagra.resume(update={"approved": True}, thread_id=thread_id)
    assert result.get("result") == "approved"
