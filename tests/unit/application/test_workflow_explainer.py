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
# _enumerate_paths: 孤立ノード・ループ検出
# ---------------------------------------------------------------------------


def test_explain_execution_paths_isolated_node() -> None:
    # start_at ノードがエッジなし・end_at にもない場合（孤立ノード）は
    # そのままパスとして記録される
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
    # "solo" はエッジなし・end_at にないのでそのままパスとして打ち切られる
    assert ["solo"] in result["execution_paths"]


def test_explain_execution_paths_loop_detected() -> None:
    # a → b → a というループ構造。ループ検出で "...(loop:a)" として打ち切られる
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
    # ループが検出されてパスが "...(loop:a)" で打ち切られる
    assert any("...(loop:a)" in p for p in paths)


def test_explain_execution_paths_loop_label_format() -> None:
    # ループ打ち切りラベルのフォーマットが "...(loop:{node_name})" であることを確認
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
    # ループ打ち切りエントリは "...(loop:router)" 形式
    assert any(p[-1] == "...(loop:router)" for p in loop_paths)


# ---------------------------------------------------------------------------
# _extract_input_variables: prompt が str / dict / list の場合
# ---------------------------------------------------------------------------


def _make_node(params: dict) -> NodeSpec:
    return NodeSpec.model_validate(
        {"id": "test_node", "handler": "llm", "params": params}
    )


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
    # 重複なし・登場順で返される
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
    # {lang} は2回登場するが重複なし
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
    # 文字列要素はスキップ、dict要素のみ解析
    assert result == ["text"]


def test_extract_input_variables_no_prompt_returns_empty() -> None:
    node = _make_node({"model": "gpt-4o-mini"})
    result = _extract_input_variables(node)
    assert result == []


def test_extract_input_variables_prompt_unsupported_type_returns_empty() -> None:
    # prompt が str / dict / list 以外の型（int など）の場合は空リストを返す
    node = _make_node({"model": "gpt-4o-mini", "prompt": 42})
    result = _extract_input_variables(node)
    assert result == []
