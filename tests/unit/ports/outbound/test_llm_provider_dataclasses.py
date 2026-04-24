"""Smoke tests for Port-layer dataclasses (``LLMCompletion`` etc.).

These dataclasses are pure Python and must not depend on any SDK. Confirm
construction, equality, immutability (``frozen=True``), and default values.
"""

from __future__ import annotations

import pytest

from yagra.ports.outbound.llm_provider import (
    LLMCompletion,
    LLMStreamChunk,
    LLMTokenUsage,
)


class TestLLMTokenUsage:
    """Tests for :class:`LLMTokenUsage`."""

    def test_construction_and_fields(self) -> None:
        usage = LLMTokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30

    def test_equality(self) -> None:
        a = LLMTokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3)
        b = LLMTokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3)
        assert a == b

    def test_frozen(self) -> None:
        usage = LLMTokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3)
        with pytest.raises(AttributeError):
            usage.prompt_tokens = 999  # type: ignore[misc]


class TestLLMCompletion:
    """Tests for :class:`LLMCompletion`."""

    def test_construction_defaults(self) -> None:
        comp = LLMCompletion(content="hello")
        assert comp.content == "hello"
        assert comp.usage is None
        assert comp.raw is None

    def test_construction_with_usage(self) -> None:
        usage = LLMTokenUsage(prompt_tokens=5, completion_tokens=7, total_tokens=12)
        comp = LLMCompletion(content="world", usage=usage, raw={"model": "gpt-4o"})
        assert comp.usage is usage
        assert comp.raw == {"model": "gpt-4o"}

    def test_frozen(self) -> None:
        comp = LLMCompletion(content="hello")
        with pytest.raises(AttributeError):
            comp.content = "mutated"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = LLMCompletion(content="x")
        b = LLMCompletion(content="x")
        assert a == b


class TestLLMStreamChunk:
    """Tests for :class:`LLMStreamChunk`."""

    def test_defaults(self) -> None:
        chunk = LLMStreamChunk(delta="partial")
        assert chunk.delta == "partial"
        assert chunk.done is False
        assert chunk.usage is None

    def test_terminal_chunk_with_usage(self) -> None:
        usage = LLMTokenUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7)
        chunk = LLMStreamChunk(delta="", done=True, usage=usage)
        assert chunk.done is True
        assert chunk.usage is usage

    def test_frozen(self) -> None:
        chunk = LLMStreamChunk(delta="abc")
        with pytest.raises(AttributeError):
            chunk.delta = "xyz"  # type: ignore[misc]
