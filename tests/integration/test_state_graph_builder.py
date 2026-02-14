from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import yaml

from yagra import Yagra
from yagra.adapters.outbound import InMemoryNodeRegistry

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
    engine = Yagra.from_workflow(
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
    engine = Yagra.from_workflow(
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
    engine = Yagra.from_workflow(
        workflow_path=WORKFLOW_ROOT / "branch-inline.yaml",
        registry=_build_registry_mapping(),
        state_schema=BranchState,
    )

    result = engine.invoke({"needs_plan": True, "goal": "typed state"})
    assert result["planned"] is True
    assert result["done"] is True
    assert result["planner_model"] == "gpt-4.1-mini"


def test_graphyml_from_workflow_merges_model_ref_with_inline_overrides(tmp_path: Path) -> None:
    workflow_path = tmp_path / "model-override.yaml"
    workflow_path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "start_at": "start",
                "end_at": ["apply_model"],
                "nodes": [
                    {"id": "start", "handler": "start_handler"},
                    {
                        "id": "apply_model",
                        "handler": "apply_model_handler",
                        "params": {
                            "model_ref": "default",
                            "model": {"temperature": 0.55},
                        },
                    },
                ],
                "edges": [{"source": "start", "target": "apply_model"}],
                "params": {"model_catalog": "models/openai_models.yaml"},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    def _start_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        return dict(state)

    def _apply_model_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        _ = state
        model = params.get("model", {})
        kwargs = model.get("kwargs", {}) if isinstance(model, dict) else {}
        return {
            "provider": model.get("provider") if isinstance(model, dict) else None,
            "name": model.get("name") if isinstance(model, dict) else None,
            "temperature": model.get("temperature") if isinstance(model, dict) else None,
            "kwargs_temperature": kwargs.get("temperature") if isinstance(kwargs, dict) else None,
        }

    engine = Yagra.from_workflow(
        workflow_path=workflow_path,
        registry={
            "start_handler": _start_handler,
            "apply_model_handler": _apply_model_handler,
        },
        bundle_root=FIXTURES_ROOT,
    )

    result = engine.invoke({})
    assert result["provider"] == "openai"
    assert result["name"] == "gpt-4.1-mini"
    assert result["temperature"] == 0.55
    assert result["kwargs_temperature"] == 0.1


def test_graphyml_from_workflow_normalizes_runtime_params_and_hides_ref_keys(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "runtime-params-normalized.yaml"
    workflow_path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "start_at": "start",
                "end_at": ["inspect"],
                "nodes": [
                    {"id": "start", "handler": "start_handler"},
                    {
                        "id": "inspect",
                        "handler": "inspect_handler",
                        "params": {
                            "prompt_ref": "planner",
                            "prompt": {"system": "Override planner system prompt."},
                            "model_ref": "default",
                            "model": {"temperature": 0.42},
                        },
                    },
                ],
                "edges": [{"source": "start", "target": "inspect"}],
                "params": {
                    "prompt_catalog": "prompts/support_prompts.yaml",
                    "model_catalog": "models/openai_models.yaml",
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    def _start_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        _ = params
        return dict(state)

    def _inspect_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        _ = state
        prompt = params.get("prompt", {})
        model = params.get("model", {})
        kwargs = model.get("kwargs", {}) if isinstance(model, dict) else {}
        return {
            "prompt_system": prompt.get("system") if isinstance(prompt, dict) else None,
            "prompt_user": prompt.get("user") if isinstance(prompt, dict) else None,
            "model_name": model.get("name") if isinstance(model, dict) else None,
            "model_temperature": model.get("temperature") if isinstance(model, dict) else None,
            "kwargs_temperature": kwargs.get("temperature") if isinstance(kwargs, dict) else None,
            "has_prompt_ref": "prompt_ref" in params,
            "has_model_ref": "model_ref" in params,
        }

    engine = Yagra.from_workflow(
        workflow_path=workflow_path,
        registry={
            "start_handler": _start_handler,
            "inspect_handler": _inspect_handler,
        },
        bundle_root=FIXTURES_ROOT,
    )

    result = engine.invoke({})
    assert result["prompt_system"] == "Override planner system prompt."
    assert result["prompt_user"] == "Create a concise plan."
    assert result["model_name"] == "gpt-4.1-mini"
    assert result["model_temperature"] == 0.42
    assert result["kwargs_temperature"] == 0.1
    assert result["has_prompt_ref"] is False
    assert result["has_model_ref"] is False
