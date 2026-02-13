from __future__ import annotations

from pathlib import Path
from typing import Any

from graphyml import Graphyml
from graphyml.adapters.outbound import InMemoryNodeRegistry

EXAMPLES_ROOT = Path(__file__).resolve().parents[2] / "examples"
WORKFLOW_ROOT = EXAMPLES_ROOT / "workflows"


def _router_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    _ = params
    next_label = "needs_plan" if state.get("needs_plan") else "direct_answer"
    return {"__next__": next_label}


def _planner_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    prompt = params.get("prompt", {})
    model = params.get("model", {})
    return {
        "planned": True,
        "plan_goal": state.get("goal", "unknown"),
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
    prompt = params.get("prompt", {})
    next_label = "retry" if int(state.get("attempts", 0)) < 2 else "done"
    return {
        "__next__": next_label,
        "evaluator_prompt": prompt.get("system"),
    }


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


def test_examples_branch_inline_workflow_runs() -> None:
    engine = Graphyml.from_workflow(
        workflow_path=WORKFLOW_ROOT / "branch-inline.yaml",
        registry=_build_registry(),
    )

    planned_result = engine.invoke({"needs_plan": True, "goal": "write tests"})
    assert planned_result["planned"] is True
    assert planned_result["done"] is True
    assert planned_result["planner_model"] == "gpt-4.1-mini"

    direct_result = engine.invoke({"needs_plan": False})
    assert direct_result["done"] is True
    assert "planned" not in direct_result


def test_examples_loop_split_workflow_runs_without_bundle_root_override() -> None:
    engine = Graphyml.from_workflow(
        workflow_path=WORKFLOW_ROOT / "loop-split.yaml",
        registry=_build_registry(),
    )

    result = engine.invoke({"attempts": 0})
    assert result["done"] is True
    assert result["attempts"] == 2
    assert result["planner_prompt"] == "You are planner."
    assert result["evaluator_prompt"] == "You are evaluator."
    assert result["finish_prompt"] == "You are finisher."
    assert result["planner_model"] == "gpt-4.1-mini"
