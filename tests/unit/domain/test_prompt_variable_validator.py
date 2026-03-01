"""Tests for prompt_variable_validator domain service."""

from __future__ import annotations

from yagra.domain.services.prompt_variable_validator import (
    _extract_required_vars,
    _get_output_key,
)

# ---------------------------------------------------------------------------
# _extract_required_vars
# ---------------------------------------------------------------------------


def test_extract_required_vars_input_keys_ignored() -> None:
    """input_keys is no longer used; auto-extraction from prompt is the only path."""
    params = {"input_keys": ["question", "context"]}
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


def test_extract_required_vars_extracts_from_system_template() -> None:
    params = {"prompt": {"system": "You always respond in {language}.", "user": "Hello."}}
    result = _extract_required_vars(params)
    assert result == ["language"]


def test_extract_required_vars_extracts_from_both_system_and_user() -> None:
    params = {"prompt": {"system": "Respond in {lang}.", "user": "Translate {text}."}}
    result = _extract_required_vars(params)
    assert result == ["lang", "text"]


def test_extract_required_vars_deduplicates_shared_variable() -> None:
    params = {"prompt": {"system": "Use {lang}.", "user": "Output in {lang}."}}
    result = _extract_required_vars(params)
    assert result == ["lang"]


def test_extract_required_vars_system_only_no_user_key() -> None:
    params = {"prompt": {"system": "You are a {role}."}}
    result = _extract_required_vars(params)
    assert result == ["role"]


def test_extract_required_vars_system_not_str_returns_user_vars() -> None:
    params = {"prompt": {"system": 123, "user": "Hello {name}."}}
    result = _extract_required_vars(params)
    assert result == ["name"]


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
