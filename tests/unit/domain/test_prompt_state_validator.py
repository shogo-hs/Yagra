"""Tests for prompt_state_validator: validates prompt variables against state_schema."""

from __future__ import annotations

from typing import Any

from yagra.domain.entities import GraphSpec
from yagra.domain.services.prompt_state_validator import (
    _collect_available_keys,
    collect_prompt_state_issues,
)


def _build_spec(
    nodes: list[dict[str, Any]],
    state_schema: dict[str, Any] | None = None,
) -> GraphSpec:
    """Helper to build a minimal GraphSpec for testing."""
    node_ids = [n["id"] for n in nodes]
    return GraphSpec.model_validate(
        {
            "version": "1.0",
            "start_at": node_ids[0],
            "end_at": [node_ids[-1]],
            "nodes": nodes,
            "edges": [],
            "state_schema": state_schema or {},
        }
    )


# ---------------------------------------------------------------------------
# _collect_available_keys
# ---------------------------------------------------------------------------


def test_collect_available_keys_includes_state_schema_keys() -> None:
    spec = _build_spec(
        nodes=[{"id": "a", "handler": "h", "params": {}}],
        state_schema={"query": {"type": "str"}, "result": {"type": "str"}},
    )
    keys = _collect_available_keys(spec)
    assert "query" in keys
    assert "result" in keys


def test_collect_available_keys_includes_output_keys() -> None:
    spec = _build_spec(
        nodes=[
            {"id": "a", "handler": "h", "params": {"output_key": "translation"}},
            {"id": "b", "handler": "h", "params": {}},
        ],
    )
    keys = _collect_available_keys(spec)
    assert "translation" in keys
    assert "output" in keys  # default output_key


def test_collect_available_keys_combines_schema_and_output() -> None:
    spec = _build_spec(
        nodes=[
            {"id": "a", "handler": "h", "params": {"output_key": "result"}},
        ],
        state_schema={"query": {"type": "str"}},
    )
    keys = _collect_available_keys(spec)
    assert keys == {"query", "result"}


# ---------------------------------------------------------------------------
# collect_prompt_state_issues: no issues
# ---------------------------------------------------------------------------


def test_no_issues_when_variables_in_state_schema() -> None:
    spec = _build_spec(
        nodes=[
            {
                "id": "translate",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "Translate", "user": "{text}"},
                    "output_key": "translation",
                },
            },
        ],
        state_schema={
            "text": {"type": "str"},
            "translation": {"type": "str"},
        },
    )
    issues = collect_prompt_state_issues(spec)
    assert issues == []


def test_no_issues_when_variable_matches_another_node_output() -> None:
    spec = _build_spec(
        nodes=[
            {
                "id": "step1",
                "handler": "h",
                "params": {"output_key": "intermediate"},
            },
            {
                "id": "step2",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "Process", "user": "{intermediate}"},
                    "output_key": "final",
                },
            },
        ],
        state_schema={"final": {"type": "str"}, "intermediate": {"type": "str"}},
    )
    issues = collect_prompt_state_issues(spec)
    assert issues == []


def test_no_issues_when_no_prompt_in_params() -> None:
    spec = _build_spec(
        nodes=[{"id": "a", "handler": "custom", "params": {}}],
        state_schema={"x": {"type": "str"}},
    )
    issues = collect_prompt_state_issues(spec)
    assert issues == []


# ---------------------------------------------------------------------------
# collect_prompt_state_issues: variable not found → warning
# ---------------------------------------------------------------------------


def test_warning_when_variable_not_in_available_keys() -> None:
    spec = _build_spec(
        nodes=[
            {
                "id": "node1",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "You are a bot", "user": "Process {unknown_var}"},
                    "output_key": "result",
                },
            },
        ],
        state_schema={"result": {"type": "str"}},
    )
    issues = collect_prompt_state_issues(spec)

    warnings = [i for i in issues if i.severity == "warning"]
    assert len(warnings) == 1
    assert "unknown_var" in warnings[0].message
    assert warnings[0].location == ("nodes", 0, "params", "prompt")
    assert warnings[0].context is not None
    assert warnings[0].context["variable"] == "unknown_var"


def test_warning_for_multiple_missing_variables() -> None:
    spec = _build_spec(
        nodes=[
            {
                "id": "node1",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "{role}", "user": "{topic} about {detail}"},
                    "output_key": "result",
                },
            },
        ],
        state_schema={"result": {"type": "str"}},
    )
    issues = collect_prompt_state_issues(spec)

    var_warnings = [
        i for i in issues if i.severity == "warning" and "variable" in (i.context or {})
    ]
    missing_vars = {i.context["variable"] for i in var_warnings}
    assert missing_vars == {"role", "topic", "detail"}


# ---------------------------------------------------------------------------
# collect_prompt_state_issues: output_key not in state_schema → warning
# ---------------------------------------------------------------------------


def test_warning_when_output_key_not_in_state_schema() -> None:
    spec = _build_spec(
        nodes=[
            {
                "id": "node1",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "Hi", "user": "{query}"},
                    "output_key": "answer",
                },
            },
        ],
        state_schema={"query": {"type": "str"}},  # "answer" not in schema
    )
    issues = collect_prompt_state_issues(spec)

    output_warnings = [
        i for i in issues if i.severity == "warning" and "output_key" in (i.context or {})
    ]
    assert len(output_warnings) == 1
    assert "answer" in output_warnings[0].message
    assert output_warnings[0].context["output_key"] == "answer"


def test_no_output_key_warning_when_state_schema_empty() -> None:
    """output_key check is only performed when state_schema is non-empty."""
    spec = _build_spec(
        nodes=[
            {
                "id": "node1",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "Hi", "user": "Hello"},
                    "output_key": "answer",
                },
            },
        ],
    )
    issues = collect_prompt_state_issues(spec)

    output_warnings = [
        i for i in issues if i.severity == "warning" and "output_key" in (i.context or {})
    ]
    assert len(output_warnings) == 0


# ---------------------------------------------------------------------------
# collect_prompt_state_issues: state_schema empty + variables → info
# ---------------------------------------------------------------------------


def test_info_when_no_state_schema_but_variables_used() -> None:
    spec = _build_spec(
        nodes=[
            {
                "id": "node1",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "Bot", "user": "{query}"},
                },
            },
        ],
    )
    issues = collect_prompt_state_issues(spec)

    info_issues = [i for i in issues if i.severity == "info"]
    assert len(info_issues) == 1
    assert "state_schema" in info_issues[0].message
    assert info_issues[0].context is not None
    assert "query" in info_issues[0].context["variables"]


def test_no_info_when_no_state_schema_and_no_variables() -> None:
    spec = _build_spec(
        nodes=[
            {
                "id": "node1",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "Hello world", "user": "No variables here"},
                },
            },
        ],
    )
    issues = collect_prompt_state_issues(spec)
    assert issues == []


# ---------------------------------------------------------------------------
# collect_prompt_state_issues: input_keys explicit
# ---------------------------------------------------------------------------


def test_explicit_input_keys_used_for_validation() -> None:
    spec = _build_spec(
        nodes=[
            {
                "id": "node1",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "Bot", "user": "{text}"},
                    "input_keys": ["custom_key"],
                    "output_key": "result",
                },
            },
        ],
        state_schema={"text": {"type": "str"}, "result": {"type": "str"}},
    )
    issues = collect_prompt_state_issues(spec)

    # "custom_key" is not in state_schema, so warning
    var_warnings = [i for i in issues if "variable" in (i.context or {})]
    assert len(var_warnings) == 1
    assert var_warnings[0].context["variable"] == "custom_key"


# ---------------------------------------------------------------------------
# collect_prompt_state_issues: prompt not resolved (skip)
# ---------------------------------------------------------------------------


def test_skips_nodes_without_prompt_dict() -> None:
    """Nodes where prompt_ref was not resolved (prompt is not a dict) are skipped."""
    spec = _build_spec(
        nodes=[
            {
                "id": "node1",
                "handler": "llm",
                "params": {"prompt_ref": "prompts.yaml#greeting"},
            },
        ],
        state_schema={"text": {"type": "str"}},
    )
    issues = collect_prompt_state_issues(spec)
    assert issues == []


# ---------------------------------------------------------------------------
# collect_prompt_state_issues: default output_key
# ---------------------------------------------------------------------------


def test_default_output_key_is_output() -> None:
    """When output_key is not specified, 'output' is used as default."""
    spec = _build_spec(
        nodes=[
            {
                "id": "node1",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "Hi", "user": "{text}"},
                },
            },
        ],
        state_schema={"text": {"type": "str"}},
        # "output" is not in state_schema → warning
    )
    issues = collect_prompt_state_issues(spec)

    output_warnings = [
        i for i in issues if i.severity == "warning" and "output_key" in (i.context or {})
    ]
    assert len(output_warnings) == 1
    assert output_warnings[0].context["output_key"] == "output"
