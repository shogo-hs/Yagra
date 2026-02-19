"""Tests for prompt_variable_validator domain service."""

from __future__ import annotations

from yagra.domain.services.prompt_variable_validator import (
    _extract_required_vars,
    _get_output_key,
)

# ---------------------------------------------------------------------------
# _extract_required_vars
# ---------------------------------------------------------------------------


def test_extract_required_vars_input_keys_list_of_strings() -> None:
    params = {"input_keys": ["question", "context"]}
    result = _extract_required_vars(params)
    assert result == ["question", "context"]


def test_extract_required_vars_input_keys_list_of_non_strings_coerced() -> None:
    params = {"input_keys": [1, 2, 3]}
    result = _extract_required_vars(params)
    assert result == ["1", "2", "3"]


def test_extract_required_vars_input_keys_not_list_returns_empty() -> None:
    params = {"input_keys": "question"}
    result = _extract_required_vars(params)
    assert result == []


def test_extract_required_vars_input_keys_not_list_int_returns_empty() -> None:
    params = {"input_keys": 42}
    result = _extract_required_vars(params)
    assert result == []


def test_extract_required_vars_prompt_not_dict_returns_empty() -> None:
    params = {"prompt": "hello {name}"}
    result = _extract_required_vars(params)
    assert result == []


def test_extract_required_vars_prompt_none_returns_empty() -> None:
    params: dict[str, object] = {}
    result = _extract_required_vars(params)
    assert result == []


def test_extract_required_vars_user_template_not_str_returns_empty() -> None:
    params = {"prompt": {"user": 123}}
    result = _extract_required_vars(params)
    assert result == []


def test_extract_required_vars_user_template_is_list_returns_empty() -> None:
    params = {"prompt": {"user": ["part1", "part2"]}}
    result = _extract_required_vars(params)
    assert result == []


def test_extract_required_vars_extracts_from_user_template() -> None:
    params = {"prompt": {"user": "translate {text} to {lang}"}}
    result = _extract_required_vars(params)
    assert result == ["text", "lang"]


def test_extract_required_vars_user_template_empty_string() -> None:
    params = {"prompt": {"user": ""}}
    result = _extract_required_vars(params)
    assert result == []


def test_extract_required_vars_prompt_dict_without_user_key() -> None:
    params = {"prompt": {"system": "You are a helpful assistant."}}
    result = _extract_required_vars(params)
    assert result == []


# ---------------------------------------------------------------------------
# _get_output_key
# ---------------------------------------------------------------------------


def test_get_output_key_returns_specified_key() -> None:
    params = {"output_key": "result"}
    result = _get_output_key(params)
    assert result == "result"


def test_get_output_key_default_when_absent() -> None:
    params: dict[str, object] = {}
    result = _get_output_key(params)
    assert result == "output"


def test_get_output_key_empty_string_returns_default() -> None:
    params = {"output_key": ""}
    result = _get_output_key(params)
    assert result == "output"


def test_get_output_key_zero_returns_default() -> None:
    params = {"output_key": 0}
    result = _get_output_key(params)
    assert result == "output"


def test_get_output_key_none_returns_default() -> None:
    params = {"output_key": None}
    result = _get_output_key(params)
    assert result == "output"
