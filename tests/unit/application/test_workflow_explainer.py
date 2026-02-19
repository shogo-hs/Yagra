"""Tests for workflow_explainer."""

from yagra.application.use_cases.workflow_explainer import (
    _extract_input_variables,
    explain_workflow,
)
from yagra.domain.entities.graph_schema import GraphSpec, NodeSpec


def _make_spec(overrides: dict) -> GraphSpec:
    base = {
        "version": "1",
        "start_at": "node_a",
        "end_at": ["node_a"],
        "nodes": [
            {
                "id": "node_a",
                "handler": "llm",
                "params": {"model": "gpt-4o-mini", "prompt": "hello"},
            }
        ],
        "edges": [],
    }
    base.update(overrides)
    return GraphSpec.model_validate(base)


def test_explain_entry_and_exit():
    spec = _make_spec({})
    result = explain_workflow(spec)
    assert result["entry_point"] == "node_a"
    assert result["exit_points"] == ["node_a"]


def test_explain_required_handlers():
    spec = _make_spec({})
    result = explain_workflow(spec)
    assert "llm" in result["required_handlers"]


def test_explain_variable_flow_extracts_prompt_vars():
    spec = _make_spec(
        {
            "nodes": [
                {
                    "id": "node_a",
                    "handler": "llm",
                    "params": {
                        "model": "gpt-4o-mini",
                        "prompt": "translate {text} to {lang}",
                        "output_key": "translation",
                    },
                }
            ],
        }
    )
    result = explain_workflow(spec)
    assert result["variable_flow"]["node_a"]["inputs"] == ["text", "lang"]
    assert "translation" in result["variable_flow"]["node_a"]["outputs"]


def test_explain_conditional_node_has_next_in_outputs():
    spec = GraphSpec.model_validate(
        {
            "version": "1",
            "start_at": "classify",
            "end_at": ["approve", "reject"],
            "nodes": [
                {
                    "id": "classify",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "classify {input}"},
                },
                {
                    "id": "approve",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "approved"},
                },
                {
                    "id": "reject",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "rejected"},
                },
            ],
            "edges": [
                {"source": "classify", "target": "approve", "condition": "approved"},
                {"source": "classify", "target": "reject", "condition": "rejected"},
            ],
        }
    )
    result = explain_workflow(spec)
    assert "__next__" in result["variable_flow"]["classify"]["outputs"]


def test_explain_execution_paths_linear():
    spec = GraphSpec.model_validate(
        {
            "version": "1",
            "start_at": "a",
            "end_at": ["b"],
            "nodes": [
                {"id": "a", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "x"}},
                {"id": "b", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "y"}},
            ],
            "edges": [{"source": "a", "target": "b"}],
        }
    )
    result = explain_workflow(spec)
    assert result["execution_paths"] == [["a", "b"]]


def test_explain_execution_paths_branch():
    spec = GraphSpec.model_validate(
        {
            "version": "1",
            "start_at": "classify",
            "end_at": ["approve", "reject"],
            "nodes": [
                {
                    "id": "classify",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "c"},
                },
                {
                    "id": "approve",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "a"},
                },
                {
                    "id": "reject",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "r"},
                },
            ],
            "edges": [
                {"source": "classify", "target": "approve", "condition": "approved"},
                {"source": "classify", "target": "reject", "condition": "rejected"},
            ],
        }
    )
    result = explain_workflow(spec)
    paths = result["execution_paths"]
    assert ["classify", "approve"] in paths
    assert ["classify", "reject"] in paths


# ---------------------------------------------------------------------------
# _enumerate_paths: isolated node and loop detection
# ---------------------------------------------------------------------------


def test_explain_execution_paths_isolated_node() -> None:
    # When start_at node has no edges and is not in end_at (isolated node),
    # it is recorded as-is in the paths
    spec = GraphSpec.model_validate(
        {
            "version": "1",
            "start_at": "solo",
            "end_at": ["other"],
            "nodes": [
                {
                    "id": "solo",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "standalone"},
                },
                {
                    "id": "other",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "other"},
                },
            ],
            "edges": [],
        }
    )
    result = explain_workflow(spec)
    # "solo" has no edges and is not in end_at, so it is terminated as-is in the path
    assert ["solo"] in result["execution_paths"]


def test_explain_execution_paths_loop_detected() -> None:
    # Loop structure a → b → a. Loop is detected and terminated as "...(loop:a)"
    spec = GraphSpec.model_validate(
        {
            "version": "1",
            "start_at": "a",
            "end_at": ["c"],
            "nodes": [
                {"id": "a", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "a"}},
                {"id": "b", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "b"}},
                {"id": "c", "handler": "llm", "params": {"model": "gpt-4o-mini", "prompt": "c"}},
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "a"},
            ],
        }
    )
    result = explain_workflow(spec)
    paths = result["execution_paths"]
    # Loop is detected and path is terminated with "...(loop:a)"
    assert any("...(loop:a)" in p for p in paths)


def test_explain_execution_paths_loop_label_format() -> None:
    # Confirm that the loop termination label format is "...(loop:{node_name})"
    spec = GraphSpec.model_validate(
        {
            "version": "1",
            "start_at": "router",
            "end_at": ["finish"],
            "nodes": [
                {
                    "id": "router",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "route"},
                },
                {
                    "id": "worker",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "work"},
                },
                {
                    "id": "finish",
                    "handler": "llm",
                    "params": {"model": "gpt-4o-mini", "prompt": "done"},
                },
            ],
            "edges": [
                {"source": "router", "target": "worker"},
                {"source": "worker", "target": "router"},
                {"source": "router", "target": "finish", "condition": "done"},
            ],
        }
    )
    result = explain_workflow(spec)
    paths = result["execution_paths"]
    loop_paths = [p for p in paths if any("...(loop:" in node for node in p)]
    assert len(loop_paths) > 0
    # Loop termination entry is in "...(loop:router)" format
    assert any(p[-1] == "...(loop:router)" for p in loop_paths)


# ---------------------------------------------------------------------------
# _extract_input_variables: cases where prompt is str / dict / list
# ---------------------------------------------------------------------------


def _make_node(params: dict) -> NodeSpec:
    return NodeSpec.model_validate({"id": "test_node", "handler": "llm", "params": params})


def test_extract_input_variables_prompt_is_string() -> None:
    node = _make_node({"model": "gpt-4o-mini", "prompt": "translate {text} to {lang}"})
    result = _extract_input_variables(node)
    assert result == ["text", "lang"]


def test_extract_input_variables_prompt_is_string_no_vars() -> None:
    node = _make_node({"model": "gpt-4o-mini", "prompt": "hello world"})
    result = _extract_input_variables(node)
    assert result == []


def test_extract_input_variables_prompt_is_dict_with_content() -> None:
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt": {"role": "user", "content": "summarize {document}"},
        }
    )
    result = _extract_input_variables(node)
    assert result == ["document"]


def test_extract_input_variables_prompt_is_dict_content_not_str() -> None:
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt": {"role": "user", "content": 42},
        }
    )
    result = _extract_input_variables(node)
    assert result == []


def test_extract_input_variables_prompt_is_dict_no_content_key() -> None:
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt": {"role": "user"},
        }
    )
    result = _extract_input_variables(node)
    assert result == []


def test_extract_input_variables_prompt_is_list_single_message() -> None:
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt": [
                {"role": "user", "content": "translate {text}"},
            ],
        }
    )
    result = _extract_input_variables(node)
    assert result == ["text"]


def test_extract_input_variables_prompt_is_list_multiple_messages() -> None:
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt": [
                {"role": "system", "content": "You are a {persona}."},
                {"role": "user", "content": "translate {text} to {lang}"},
            ],
        }
    )
    result = _extract_input_variables(node)
    # No duplicates, returned in order of appearance
    assert result == ["persona", "text", "lang"]


def test_extract_input_variables_prompt_is_list_deduplicates_vars() -> None:
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt": [
                {"role": "system", "content": "Use {lang}."},
                {"role": "user", "content": "translate {text} to {lang}"},
            ],
        }
    )
    result = _extract_input_variables(node)
    # {lang} appears twice but no duplicates
    assert result.count("lang") == 1
    assert "text" in result


def test_extract_input_variables_prompt_is_list_message_content_not_str() -> None:
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt": [
                {"role": "user", "content": 99},
            ],
        }
    )
    result = _extract_input_variables(node)
    assert result == []


def test_extract_input_variables_prompt_is_list_non_dict_messages_skipped() -> None:
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt": [
                "plain string message",
                {"role": "user", "content": "translate {text}"},
            ],
        }
    )
    result = _extract_input_variables(node)
    # String elements are skipped; only dict elements are analyzed
    assert result == ["text"]


def test_extract_input_variables_no_prompt_returns_empty() -> None:
    node = _make_node({"model": "gpt-4o-mini"})
    result = _extract_input_variables(node)
    assert result == []


def test_extract_input_variables_prompt_unsupported_type_returns_empty() -> None:
    # Returns an empty list when prompt is a type other than str / dict / list (e.g., int)
    node = _make_node({"model": "gpt-4o-mini", "prompt": 42})
    result = _extract_input_variables(node)
    assert result == []


# ---------------------------------------------------------------------------
# fan_out edge: variable_flow should reflect items_key / item_key
# ---------------------------------------------------------------------------


def test_explain_variable_flow_fan_out_source_has_items_key_in_outputs() -> None:
    spec = GraphSpec.model_validate(
        {
            "version": "1",
            "start_at": "prepare",
            "end_at": ["aggregate"],
            "state_schema": {
                "items": {"type": "list"},
                "results": {"type": "list", "reducer": "add"},
            },
            "nodes": [
                {"id": "prepare", "handler": "prepare_handler", "params": {}},
                {"id": "process_item", "handler": "process_handler", "params": {}},
                {"id": "aggregate", "handler": "aggregate_handler", "params": {}},
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
    )
    result = explain_workflow(spec)

    # prepare node should show "items" in outputs (it populates state["items"])
    assert "items" in result["variable_flow"]["prepare"]["outputs"]
    # process_item node should show "item" in inputs (injected per fan-out)
    assert "item" in result["variable_flow"]["process_item"]["inputs"]


def test_explain_execution_paths_fan_out_includes_target() -> None:
    spec = GraphSpec.model_validate(
        {
            "version": "1",
            "start_at": "prepare",
            "end_at": ["aggregate"],
            "state_schema": {
                "items": {"type": "list"},
                "results": {"type": "list", "reducer": "add"},
            },
            "nodes": [
                {"id": "prepare", "handler": "prepare_handler", "params": {}},
                {"id": "process_item", "handler": "process_handler", "params": {}},
                {"id": "aggregate", "handler": "aggregate_handler", "params": {}},
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
    )
    result = explain_workflow(spec)

    # fan_out edge is traversed normally in path enumeration
    assert result["execution_paths"] == [["prepare", "process_item", "aggregate"]]
