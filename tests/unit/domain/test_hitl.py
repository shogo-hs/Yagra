"""G-09: HITL (Human-in-the-Loop) 機能のテスト。

GraphSpec の interrupt_before / interrupt_after フィールドと
state_graph_builder の checkpointer 連携をテストする。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from yagra.domain.entities import GraphSpec


def _base_payload() -> dict[str, Any]:
    """最小構成の GraphSpec ペイロードを返す。

    Returns:
        テスト用 GraphSpec ペイロード辞書。
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


# --- GraphSpec フィールドテスト ---


def test_graph_spec_interrupt_before_defaults_to_empty() -> None:
    """interrupt_before のデフォルト値が空リストであることを確認する。

    Returns:
        None
    """
    payload = _base_payload()
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_before == []


def test_graph_spec_interrupt_after_defaults_to_empty() -> None:
    """interrupt_after のデフォルト値が空リストであることを確認する。

    Returns:
        None
    """
    payload = _base_payload()
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_after == []


def test_graph_spec_interrupt_before_accepts_node_ids() -> None:
    """interrupt_before にノード ID リストを設定できることを確認する。

    Returns:
        None
    """
    payload = _base_payload()
    payload["interrupt_before"] = ["nodeA"]
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_before == ["nodeA"]


def test_graph_spec_interrupt_after_accepts_node_ids() -> None:
    """interrupt_after にノード ID リストを設定できることを確認する。

    Returns:
        None
    """
    payload = _base_payload()
    payload["interrupt_after"] = ["nodeA"]
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_after == ["nodeA"]


def test_graph_spec_interrupt_before_accepts_multiple_nodes() -> None:
    """interrupt_before に複数ノード ID を設定できることを確認する。

    Returns:
        None
    """
    payload = _base_payload()
    payload["nodes"].append({"id": "nodeC", "handler": "handler_c"})
    payload["edges"].append({"source": "nodeB", "target": "nodeC"})
    payload["end_at"] = ["nodeC"]
    payload["interrupt_before"] = ["nodeA", "nodeB"]
    spec = GraphSpec.model_validate(payload)

    assert spec.interrupt_before == ["nodeA", "nodeB"]


def test_graph_spec_interrupt_fields_serialize_to_yaml_compatible() -> None:
    """interrupt_before / interrupt_after がシリアライズ可能であることを確認する。

    Returns:
        None
    """
    payload = _base_payload()
    payload["interrupt_before"] = ["nodeA"]
    payload["interrupt_after"] = ["nodeB"]
    spec = GraphSpec.model_validate(payload)

    dumped = spec.model_dump()

    assert dumped["interrupt_before"] == ["nodeA"]
    assert dumped["interrupt_after"] == ["nodeB"]


# --- バリデーションテスト ---


def test_validation_detects_unknown_interrupt_before_node() -> None:
    """Interrupt_before に未定義ノード ID が含まれる場合に問題を検知することを確認する。

    Returns:
        None
    """
    from yagra.domain.services.schema_validator import collect_graph_structure_issues

    payload = _base_payload()
    payload["interrupt_before"] = ["nonexistent_node"]
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert any("interrupt_before" in str(issue.location) for issue in issues)
    assert any("nonexistent_node" in issue.message for issue in issues)


def test_validation_detects_unknown_interrupt_after_node() -> None:
    """Interrupt_after に未定義ノード ID が含まれる場合に問題を検知することを確認する。

    Returns:
        None
    """
    from yagra.domain.services.schema_validator import collect_graph_structure_issues

    payload = _base_payload()
    payload["interrupt_after"] = ["nonexistent_node"]
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert any("interrupt_after" in str(issue.location) for issue in issues)
    assert any("nonexistent_node" in issue.message for issue in issues)


def test_validation_passes_for_valid_interrupt_nodes() -> None:
    """有効なノード ID が interrupt_before / interrupt_after に設定されている場合に問題なしを返すことを確認する。

    Returns:
        None
    """
    from yagra.domain.services.schema_validator import collect_graph_structure_issues

    payload = _base_payload()
    payload["interrupt_before"] = ["nodeA"]
    payload["interrupt_after"] = ["nodeB"]
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    interrupt_issues = [i for i in issues if "interrupt" in str(i.location)]
    assert interrupt_issues == []


# --- build_state_graph との統合テスト ---


def test_build_state_graph_without_checkpointer_ignores_interrupts() -> None:
    """Checkpointer なしでは interrupt が無効（コンパイルが成功する）ことを確認する。

    Returns:
        None
    """
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

    # checkpointer=None でもコンパイルエラーが起きないことを確認
    compiled = build_state_graph(spec, registry, checkpointer=None)
    assert compiled is not None


def test_build_state_graph_with_checkpointer_passes_interrupts() -> None:
    """Checkpointer を渡すと compile() に interrupt_before が伝わることを確認する。

    Returns:
        None
    """
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


# --- Yagra.from_workflow / invoke / resume の API テスト ---


def test_yagra_from_workflow_accepts_checkpointer(tmp_path: Any) -> None:
    """Yagra.from_workflow が checkpointer キーワード引数を受け付けることを確認する。

    Args:
        tmp_path: 一時ディレクトリを提供する pytest fixture。

    Returns:
        None
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

    # checkpointer を渡しても例外が起きないことを確認
    yagra = Yagra.from_workflow(workflow_path, registry, checkpointer=checkpointer)
    assert yagra is not None


def test_yagra_invoke_accepts_thread_id(tmp_path: Any) -> None:
    """Yagra.invoke が thread_id キーワード引数を受け付けることを確認する。

    Args:
        tmp_path: 一時ディレクトリを提供する pytest fixture。

    Returns:
        None
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

    # thread_id 付きで invoke できることを確認
    result = yagra.invoke({"key": "value"}, thread_id="test-thread-1")
    assert isinstance(result, dict)


def test_yagra_resume_accepts_thread_id(tmp_path: Any) -> None:
    """Yagra.resume が thread_id キーワード引数を受け付けることを確認する。

    interrupt_before を使って中断→resume するフローを検証する。

    Args:
        tmp_path: 一時ディレクトリを提供する pytest fixture。

    Returns:
        None
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

    # invoke で nodeB の手前で中断する
    result1 = yagra.invoke({"input": "hello"}, thread_id=thread_id)
    # 中断後は nodeB 実行前なので visited_b は存在しない
    assert result1.get("visited_a") is True
    assert "visited_b" not in result1

    # resume で中断点から再開する
    result2 = yagra.resume(thread_id=thread_id)
    assert result2.get("visited_b") is True


def test_yagra_resume_with_state_update(tmp_path: Any) -> None:
    """Yagra.resume が状態更新を受け取れることを確認する。

    Args:
        tmp_path: 一時ディレクトリを提供する pytest fixture。

    Returns:
        None
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

    # nodeB は state["approved"] を確認して result に記録する
    registry: dict[str, Any] = {
        "handler_a": lambda s, p: s,
        "handler_b": lambda s, p: {**s, "result": "approved" if s.get("approved") else "rejected"},
    }

    checkpointer = MemorySaver()
    yagra = Yagra.from_workflow(workflow_path, registry, checkpointer=checkpointer)

    thread_id = "hitl-update-thread"

    # invoke で中断
    yagra.invoke({"input": "review me"}, thread_id=thread_id)

    # 人間が approved=True を注入して resume
    result = yagra.resume(update={"approved": True}, thread_id=thread_id)
    assert result.get("result") == "approved"
