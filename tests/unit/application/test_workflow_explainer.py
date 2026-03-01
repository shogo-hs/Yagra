"""Tests for workflow_explainer."""

from pathlib import Path

from yagra.application.use_cases.workflow_explainer import (
    _extract_input_variables,
    _extract_vars_from_prompt_ref,
    _extract_vars_from_value,
    explain_workflow,
)
from yagra.domain.entities.graph_schema import GraphSpec, NodeSpec

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures"


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


# ---------------------------------------------------------------------------
# _extract_input_variables: input_keys is ignored (deprecated)
# ---------------------------------------------------------------------------


def test_extract_input_variables_input_keys_ignored() -> None:
    # input_keys is no longer used; returns empty when no prompt is present
    node = _make_node({"model": "gpt-4o-mini", "input_keys": ["foo", "bar"]})
    result = _extract_input_variables(node)
    assert result == []


# ---------------------------------------------------------------------------
# _extract_input_variables: prompt_ref path (line 216)
# ---------------------------------------------------------------------------


def test_extract_input_variables_prompt_ref_with_workflow_dir(tmp_path: Path) -> None:
    # When prompt_ref is provided and workflow_dir is given, reads the file (line 216)
    prompt_file = tmp_path / "prompts.yaml"
    prompt_file.write_text("system: Hello {name}\nuser: Question {query}\n", encoding="utf-8")
    node = _make_node({"model": "gpt-4o-mini", "prompt_ref": "prompts.yaml"})
    result = _extract_input_variables(node, workflow_dir=tmp_path)
    assert "name" in result
    assert "query" in result


def test_extract_input_variables_prompt_ref_without_workflow_dir() -> None:
    # When prompt_ref is present but workflow_dir is None, returns empty (via _extract_vars_from_prompt_ref)
    node = _make_node({"model": "gpt-4o-mini", "prompt_ref": "prompts/file.yaml"})
    result = _extract_input_variables(node, workflow_dir=None)
    assert result == []


def test_extract_input_variables_prompt_ref_not_found_returns_empty(tmp_path: Path) -> None:
    # When prompt_ref file cannot be found, returns empty (input_keys no longer used as fallback)
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt_ref": "nonexistent.yaml",
            "input_keys": ["fallback_var"],
        }
    )
    result = _extract_input_variables(node, workflow_dir=tmp_path)
    assert result == []


def test_extract_input_variables_string_prompt_no_vars_returns_empty() -> None:
    # When prompt string has no vars, returns empty (input_keys no longer used as fallback)
    node = _make_node(
        {
            "model": "gpt-4o-mini",
            "prompt": "hello world",
            "input_keys": ["needed_var"],
        }
    )
    result = _extract_input_variables(node)
    assert result == []


# ---------------------------------------------------------------------------
# _extract_vars_from_prompt_ref: direct tests (lines 264-291)
# ---------------------------------------------------------------------------


def test_extract_vars_from_prompt_ref_workflow_dir_none() -> None:
    # When workflow_dir is None, returns immediately with empty list (line 264-265)
    result = _extract_vars_from_prompt_ref("prompts/foo.yaml", workflow_dir=None)
    assert result == []


def test_extract_vars_from_prompt_ref_reads_file(tmp_path: Path) -> None:
    # Reads file and extracts variables from it (lines 277-291)
    prompt_file = tmp_path / "foo.yaml"
    prompt_file.write_text("user: translate {text} to {lang}\n", encoding="utf-8")
    result = _extract_vars_from_prompt_ref("foo.yaml", workflow_dir=tmp_path)
    assert "text" in result
    assert "lang" in result


def test_extract_vars_from_prompt_ref_with_anchor(tmp_path: Path) -> None:
    # When '#section' anchor is provided, extracts only from that section (lines 268-270, 285-291)
    prompt_file = tmp_path / "prompts.yaml"
    prompt_file.write_text(
        "planner:\n  system: Plan {task}\n  user: Execute {query}\nother:\n  user: Ignore {ignored}\n",
        encoding="utf-8",
    )
    result = _extract_vars_from_prompt_ref("prompts.yaml#planner", workflow_dir=tmp_path)
    assert "task" in result
    assert "query" in result
    assert "ignored" not in result


def test_extract_vars_from_prompt_ref_with_anchor_data_not_dict(tmp_path: Path) -> None:
    # When file contains a list (not dict) but anchor is specified, returns empty (line 288-289)
    prompt_file = tmp_path / "list_prompts.yaml"
    prompt_file.write_text("- item1\n- item2\n", encoding="utf-8")
    result = _extract_vars_from_prompt_ref("list_prompts.yaml#section", workflow_dir=tmp_path)
    assert result == []


def test_extract_vars_from_prompt_ref_file_not_found(tmp_path: Path) -> None:
    # When file does not exist, returns empty list (exception caught, line 282-283)
    result = _extract_vars_from_prompt_ref("nonexistent.yaml", workflow_dir=tmp_path)
    assert result == []


def test_extract_vars_from_prompt_ref_invalid_yaml(tmp_path: Path) -> None:
    # When file contains invalid YAML, returns empty list (exception caught, line 282-283)
    prompt_file = tmp_path / "bad.yaml"
    prompt_file.write_text("key: [unclosed bracket\n", encoding="utf-8")
    result = _extract_vars_from_prompt_ref("bad.yaml", workflow_dir=tmp_path)
    assert result == []


def test_extract_vars_from_prompt_ref_absolute_path(tmp_path: Path) -> None:
    # Absolute path (not relative to workflow_dir) is resolved correctly (line 274)
    prompt_file = tmp_path / "abs_prompts.yaml"
    prompt_file.write_text("user: Hello {name}\n", encoding="utf-8")
    result = _extract_vars_from_prompt_ref(str(prompt_file), workflow_dir=tmp_path)
    assert "name" in result


def test_extract_vars_from_prompt_ref_uses_fixtures(tmp_path: Path) -> None:
    # Uses the existing fixture file with anchor
    result = _extract_vars_from_prompt_ref(
        "prompts/support_prompts.yaml#planner", workflow_dir=FIXTURES_ROOT
    )
    # support_prompts.yaml planner section has no {variables}, so result should be empty
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _extract_vars_from_value: list items traversal (lines 315-317)
# ---------------------------------------------------------------------------


def test_extract_vars_from_value_with_list() -> None:
    # When value is a list containing strings with variables (lines 315-317)
    value = ["Hello {foo}", "World {bar}"]
    result = _extract_vars_from_value(value)
    assert "foo" in result
    assert "bar" in result


def test_extract_vars_from_value_nested_list_in_dict() -> None:
    # Nested list inside dict (lines 312-317)
    value = {"messages": ["Translate {text}", "to {lang}"]}
    result = _extract_vars_from_value(value)
    assert "text" in result
    assert "lang" in result


# ---------------------------------------------------------------------------
# explain_workflow: warnings when prompt_ref unresolved (workflow_dir=None)
# ---------------------------------------------------------------------------


def test_explain_workflow_prompt_ref_without_workflow_dir_emits_warning() -> None:
    # When workflow_dir is None and a node has prompt_ref, a warning is appended
    spec = GraphSpec.model_validate(
        {
            "version": "1",
            "start_at": "node_a",
            "end_at": ["node_a"],
            "nodes": [
                {
                    "id": "node_a",
                    "handler": "llm",
                    "params": {
                        "model": "gpt-4o-mini",
                        "prompt_ref": "prompts/file.yaml",
                    },
                }
            ],
            "edges": [],
        }
    )
    result = explain_workflow(spec, workflow_dir=None)
    assert len(result["warnings"]) == 1
    assert result["warnings"][0]["code"] == "prompt_ref_unresolved"
    assert result["warnings"][0]["node_id"] == "node_a"
