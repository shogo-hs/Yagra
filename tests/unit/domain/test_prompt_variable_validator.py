"""prompt_variable_validator のユニットテスト。"""

from __future__ import annotations

from typing import Any

import pytest

from yagra.domain.entities import GraphSpec
from yagra.domain.services.prompt_variable_validator import collect_prompt_variable_issues


def _make_spec(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]] | None = None,
    params: dict[str, Any] | None = None,
    start_at: str | None = None,
    end_at: list[str] | None = None,
) -> GraphSpec:
    node_ids = [n["id"] for n in nodes]
    return GraphSpec.model_validate(
        {
            "version": "1.0",
            "start_at": start_at or node_ids[0],
            "end_at": end_at or [node_ids[-1]],
            "nodes": nodes,
            "edges": edges or [],
            "params": params or {},
        }
    )


def _llm_node(
    node_id: str,
    user_prompt: str,
    output_key: str | None = None,
    input_keys: list[str] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "prompt": {"system": "you are helpful", "user": user_prompt},
        "model": {"provider": "openai", "name": "gpt-4"},
    }
    if output_key is not None:
        params["output_key"] = output_key
    if input_keys is not None:
        params["input_keys"] = input_keys
    return {"id": node_id, "handler": "llm", "params": params}


# ---------------------------------------------------------------------------
# 線形パス
# ---------------------------------------------------------------------------


def test_linear_no_variable_no_issue() -> None:
    """変数を参照しないプロンプトはエラーなし。"""
    spec = _make_spec(
        nodes=[
            _llm_node("a", "hello world"),
            _llm_node("b", "goodbye world"),
        ],
        edges=[{"source": "a", "target": "b"}],
    )
    assert collect_prompt_variable_issues(spec) == []


def test_linear_variable_exists_no_issue() -> None:
    """前ノードの output_key と変数名が一致する場合はエラーなし。"""
    spec = _make_spec(
        nodes=[
            _llm_node("a", "ask something", output_key="result"),
            _llm_node("b", "{result} をやさしく言い換えて"),
        ],
        edges=[{"source": "a", "target": "b"}],
    )
    assert collect_prompt_variable_issues(spec) == []


def test_linear_variable_missing_raises_issue() -> None:
    """前ノードの output_key と変数名が一致しない場合はエラー。"""
    spec = _make_spec(
        nodes=[
            _llm_node("a", "ask something", output_key="output"),
            _llm_node("b", "{result} をやさしく言い換えて"),
        ],
        edges=[{"source": "a", "target": "b"}],
    )
    issues = collect_prompt_variable_issues(spec)
    assert len(issues) == 1
    assert "result" in issues[0].message
    assert issues[0].location == ("nodes", 1, "params", "prompt", "user")


def test_default_output_key_is_output() -> None:
    """output_key 未指定のノードはデフォルト 'output' を出力する。"""
    spec = _make_spec(
        nodes=[
            _llm_node("a", "ask something"),  # output_key 未指定 → "output"
            _llm_node("b", "{output} をやさしく言い換えて"),
        ],
        edges=[{"source": "a", "target": "b"}],
    )
    assert collect_prompt_variable_issues(spec) == []


# ---------------------------------------------------------------------------
# spec.params による初期 state キー
# ---------------------------------------------------------------------------


def test_initial_params_key_is_available() -> None:
    """spec.params で宣言した初期キーは変数として利用可能。"""
    spec = _make_spec(
        nodes=[_llm_node("a", "{user_input} に答えてください")],
        params={"user_input": ""},
    )
    assert collect_prompt_variable_issues(spec) == []


def test_undeclared_external_key_raises_issue() -> None:
    """spec.params に宣言されていない外部キーはエラー。"""
    spec = _make_spec(
        nodes=[_llm_node("a", "{user_input} に答えてください")],
        params={},
    )
    issues = collect_prompt_variable_issues(spec)
    assert len(issues) == 1
    assert "user_input" in issues[0].message


# ---------------------------------------------------------------------------
# カスタムハンドラーは対象外
# ---------------------------------------------------------------------------


def test_custom_handler_skipped() -> None:
    """カスタムハンドラーのノードはバリデーション対象外。"""
    spec = _make_spec(
        nodes=[
            {
                "id": "custom",
                "handler": "my_custom_handler",
                "params": {"prompt": {"system": "", "user": "{missing_key}"}},
            }
        ],
    )
    assert collect_prompt_variable_issues(spec) == []


@pytest.mark.parametrize("handler", ["llm", "streaming_llm", "structured_llm"])
def test_all_llm_handlers_are_validated(handler: str) -> None:
    """Llm / streaming_llm / structured_llm は全てバリデーション対象。"""
    node: dict[str, Any] = {
        "id": "node",
        "handler": handler,
        "params": {
            "prompt": {"system": "", "user": "{missing}"},
            "model": {"provider": "openai", "name": "gpt-4"},
        },
    }
    spec = _make_spec(nodes=[node])
    issues = collect_prompt_variable_issues(spec)
    assert len(issues) == 1
    assert "missing" in issues[0].message


# ---------------------------------------------------------------------------
# input_keys 明示指定
# ---------------------------------------------------------------------------


def test_explicit_input_keys_used_instead_of_template() -> None:
    """input_keys が明示されている場合は template からの抽出より優先される。"""
    # プロンプトに {foo} があるが input_keys=["bar"] と明示 → bar の欠落をチェック
    spec = _make_spec(
        nodes=[
            _llm_node("a", "{foo} を答えて", input_keys=["bar"]),
        ],
    )
    issues = collect_prompt_variable_issues(spec)
    # foo は無視され bar が要求される → bar は state にないのでエラー
    assert len(issues) == 1
    assert "bar" in issues[0].message


def test_explicit_input_keys_all_available_no_issue() -> None:
    """input_keys で指定したキーが全て初期 params にある場合はエラーなし。"""
    spec = _make_spec(
        nodes=[
            _llm_node("a", "{foo} を答えて", input_keys=["bar"]),
        ],
        params={"bar": ""},
    )
    assert collect_prompt_variable_issues(spec) == []


# ---------------------------------------------------------------------------
# 条件分岐（全パスチェック）
# ---------------------------------------------------------------------------


def test_branching_variable_missing_on_one_path_raises_issue() -> None:
    """条件分岐でいずれかのパスで変数が欠落していればエラー。

    start --[A]--> node_b --> end
    start --[B]--> end

    end が {aaa} を要求するが、条件B では node_b を経由しないため
    aaa が state に存在しないパスがある → エラー。
    """
    spec = _make_spec(
        nodes=[
            _llm_node("start", "最初の質問", output_key="output"),
            _llm_node("node_b", "中間処理", output_key="aaa"),
            _llm_node("end", "{aaa} をやさしく言い換えて"),
        ],
        edges=[
            {"source": "start", "target": "node_b", "condition": "A"},
            {"source": "start", "target": "end", "condition": "B"},
            {"source": "node_b", "target": "end"},
        ],
        start_at="start",
        end_at=["end"],
    )
    issues = collect_prompt_variable_issues(spec)
    assert len(issues) == 1
    assert "aaa" in issues[0].message


def test_branching_variable_available_on_all_paths_no_issue() -> None:
    """条件分岐で全パスに変数が存在する場合はエラーなし。

    start --[A]--> node_b --> merge
    start --[B]--> node_c --> merge

    node_b と node_c が両方 output_key=aaa を出力し、
    merge が {aaa} を要求する。
    """
    spec = _make_spec(
        nodes=[
            _llm_node("start", "最初の質問"),
            _llm_node("node_b", "パスA処理", output_key="aaa"),
            _llm_node("node_c", "パスB処理", output_key="aaa"),
            _llm_node("merge", "{aaa} をまとめて"),
        ],
        edges=[
            {"source": "start", "target": "node_b", "condition": "A"},
            {"source": "start", "target": "node_c", "condition": "B"},
            {"source": "node_b", "target": "merge"},
            {"source": "node_c", "target": "merge"},
        ],
        start_at="start",
        end_at=["merge"],
    )
    assert collect_prompt_variable_issues(spec) == []


# ---------------------------------------------------------------------------
# 循環グラフはスキップ
# ---------------------------------------------------------------------------


def test_cyclic_graph_is_skipped() -> None:
    """循環グラフがあるとき（構造エラー）はバリデーションをスキップしてエラーなし。"""
    # a → b → a の循環
    spec = GraphSpec.model_validate(
        {
            "version": "1.0",
            "start_at": "a",
            "end_at": ["a"],
            "nodes": [
                {
                    "id": "a",
                    "handler": "llm",
                    "params": {
                        "prompt": {"system": "", "user": "{missing}"},
                        "model": {"provider": "openai", "name": "gpt-4"},
                    },
                },
                {
                    "id": "b",
                    "handler": "llm",
                    "params": {
                        "prompt": {"system": "", "user": "hello"},
                        "model": {"provider": "openai", "name": "gpt-4"},
                    },
                },
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "a"},
            ],
            "params": {},
        }
    )
    # 循環があるのでスキップ → issues なし
    assert collect_prompt_variable_issues(spec) == []
