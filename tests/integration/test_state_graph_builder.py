from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from graphyml import Graphyml
from graphyml.adapters.outbound import InMemoryNodeRegistry

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
WORKFLOW_ROOT = FIXTURES_ROOT / "workflows"


def _router_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    _ = params
    next_label = "needs_plan" if state.get("needs_plan") else "direct_answer"
    return {"__next__": next_label}


def _planner_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    prompt = params.get("prompt", {})
    model = params.get("model", {})
    goal = state.get("goal", "unknown")
    return {
        "planned": True,
        "plan_goal": goal,
        "planner_prompt": prompt.get("system"),
        "planner_model": model.get("name"),
    }


def _planner_loop_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    attempts = int(state.get("attempts", 0)) + 1
    prompt = params.get("prompt", {})
    model = params.get("model", {})
    return {
        "attempts": attempts,
        "planner_prompt": prompt.get("system"),
        "planner_model": model.get("name"),
    }


def _evaluator_loop_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    _ = params
    next_label = "retry" if int(state.get("attempts", 0)) < 2 else "done"
    return {"__next__": next_label}


def _finish_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    prompt = params.get("prompt", {})
    model = params.get("model", {})
    return {
        "done": True,
        "finish_prompt": prompt.get("system"),
        "finish_model": model.get("name"),
        "attempts": state.get("attempts"),
    }


def _build_registry() -> InMemoryNodeRegistry:
    return InMemoryNodeRegistry(
        {
            "router_handler": _router_handler,
            "planner_handler": _planner_handler,
            "planner_loop_handler": _planner_loop_handler,
            "evaluator_loop_handler": _evaluator_loop_handler,
            "finish_handler": _finish_handler,
        }
    )


def _build_registry_mapping() -> dict[str, Any]:
    return {
        "router_handler": _router_handler,
        "planner_handler": _planner_handler,
        "planner_loop_handler": _planner_loop_handler,
        "evaluator_loop_handler": _evaluator_loop_handler,
        "finish_handler": _finish_handler,
    }


class BranchState(TypedDict, total=False):
    needs_plan: bool
    goal: str
    planned: bool
    done: bool
    planner_model: str


def test_graphyml_from_workflow_runs_inline_branch_workflow() -> None:
    engine = Graphyml.from_workflow(
        workflow_path=WORKFLOW_ROOT / "branch-inline.yaml",
        registry=_build_registry(),
    )

    result_planned = engine.invoke({"needs_plan": True, "goal": "write tests"})
    assert result_planned["planned"] is True
    assert result_planned["done"] is True
    assert result_planned["planner_model"] == "gpt-4.1-mini"

    result_direct = engine.invoke({"needs_plan": False})
    assert result_direct["done"] is True
    assert "planned" not in result_direct


def test_graphyml_from_workflow_runs_split_reference_loop_workflow() -> None:
    engine = Graphyml.from_workflow(
        workflow_path=WORKFLOW_ROOT / "loop-split.yaml",
        registry=_build_registry(),
        bundle_root=FIXTURES_ROOT,
    )

    result = engine.invoke({"attempts": 0})
    assert result["done"] is True
    assert result["attempts"] == 2
    assert result["planner_prompt"] == "You are planner."
    assert result["planner_model"] == "gpt-4.1-mini"
    assert result["finish_prompt"] == "You are finisher."


def test_graphyml_from_workflow_accepts_registry_mapping_and_state_schema() -> None:
    engine = Graphyml.from_workflow(
        workflow_path=WORKFLOW_ROOT / "branch-inline.yaml",
        registry=_build_registry_mapping(),
        state_schema=BranchState,
    )

    result = engine.invoke({"needs_plan": True, "goal": "typed state"})
    assert result["planned"] is True
    assert result["done"] is True
    assert result["planner_model"] == "gpt-4.1-mini"
