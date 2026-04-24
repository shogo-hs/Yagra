"""Port-routing DI tests for the three LLM handlers.

These tests cover Contract #28 SC-5 / SC-13:

- SC-5: ``create_llm_handler`` / ``create_structured_llm_handler`` /
  ``create_streaming_llm_handler`` accept an explicit
  :class:`LLMProviderPort` instance for DI.
- SC-13: When an explicit provider is omitted, the handler resolves one
  from ``params["provider"]`` (default ``"litellm"``), and unknown names
  raise :class:`LLMHandlerConfigError` with a 4-field structured payload.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from yagra.handlers.errors import LLMHandlerConfigError
from yagra.handlers.llm_handler import create_llm_handler
from yagra.handlers.streaming_llm_handler import create_streaming_llm_handler
from yagra.handlers.structured_llm_handler import create_structured_llm_handler
from yagra.ports.outbound.llm_provider import (
    LLMCompletion,
    LLMProviderPort,
    LLMStreamChunk,
    LLMTokenUsage,
)


class _FakeProvider(LLMProviderPort):
    """In-memory LLMProviderPort implementation for DI tests."""

    def __init__(
        self,
        *,
        completion_content: str = "",
        structured: dict[str, Any] | None = None,
        stream_chunks: list[str] | None = None,
    ) -> None:
        self.completion_content = completion_content
        self.structured_value: dict[str, Any] = structured or {}
        self.stream_chunks = stream_chunks or []
        self.complete_calls: list[dict[str, Any]] = []
        self.structured_calls: list[dict[str, Any]] = []
        self.streaming_calls: list[dict[str, Any]] = []

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> LLMCompletion:
        self.complete_calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model,
                "timeout": timeout,
                "kwargs": kwargs,
            }
        )
        return LLMCompletion(
            content=self.completion_content,
            usage=LLMTokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        )

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.structured_calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema": schema,
                "model": model,
                "timeout": timeout,
                "kwargs": kwargs,
            }
        )
        return self.structured_value

    def complete_streaming(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> Iterator[LLMStreamChunk]:
        self.streaming_calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model,
                "timeout": timeout,
                "kwargs": kwargs,
            }
        )
        for delta in self.stream_chunks:
            yield LLMStreamChunk(delta=delta, done=False)
        yield LLMStreamChunk(delta="", done=True)


class TestLLMHandlerDI:
    """SC-5: create_llm_handler accepts an explicit LLMProviderPort."""

    def test_explicit_provider_is_used_without_resolver(self) -> None:
        """An explicit provider short-circuits the resolver path entirely."""
        fake = _FakeProvider(completion_content="hello from fake")
        handler = create_llm_handler(provider=fake, retry=1, timeout=5)

        result = handler(
            {"name": "Alice"},
            {
                "prompt": {"system": "sys", "user": "Hi {name}"},
                "model": {"provider": "openai", "name": "gpt-4o"},
                "output_key": "reply",
            },
        )

        assert result == {"reply": "hello from fake"}
        assert len(fake.complete_calls) == 1
        call = fake.complete_calls[0]
        assert call["user_prompt"] == "Hi Alice"
        assert call["model"] == "openai/gpt-4o"
        assert call["timeout"] == 5


class TestStructuredLLMHandlerDI:
    """SC-5: create_structured_llm_handler accepts an explicit LLMProviderPort."""

    def test_explicit_provider_is_used_without_resolver(self) -> None:
        """An explicit provider short-circuits the resolver path entirely."""
        from pydantic import BaseModel

        class _Out(BaseModel):
            value: int

        fake = _FakeProvider(structured={"value": 42})
        handler = create_structured_llm_handler(schema=_Out, provider=fake, retry=1)

        result = handler(
            {},
            {
                "prompt": {"system": "sys", "user": "user"},
                "model": {"provider": "openai", "name": "gpt-4o"},
                "output_key": "parsed",
            },
        )

        assert result["parsed"].value == 42
        assert len(fake.structured_calls) == 1
        assert fake.structured_calls[0]["model"] == "openai/gpt-4o"


class TestStreamingLLMHandlerDI:
    """SC-5: create_streaming_llm_handler accepts an explicit LLMProviderPort."""

    def test_explicit_provider_is_used_without_resolver(self) -> None:
        """An explicit provider short-circuits the resolver path entirely."""
        fake = _FakeProvider(stream_chunks=["Hello", " ", "world"])
        handler = create_streaming_llm_handler(provider=fake, retry=1, timeout=5)

        result = handler(
            {},
            {
                "prompt": {"system": "sys", "user": "user"},
                "model": {"provider": "openai", "name": "gpt-4o"},
                "output_key": "stream",
            },
        )

        assert "".join(result["stream"]) == "Hello world"
        assert len(fake.streaming_calls) == 1


class TestLLMHandlerParamsProvider:
    """SC-13: ``params["provider"]`` selects the provider by name."""

    def test_default_is_litellm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without explicit provider or params key, ``resolve_provider`` is asked for 'litellm'."""
        captured: dict[str, str] = {}

        class _StubProvider(_FakeProvider):
            pass

        def _fake_resolve(name: str) -> LLMProviderPort:
            captured["name"] = name
            return _StubProvider(completion_content="ok")

        import yagra.adapters.outbound.llm_providers as providers_pkg

        monkeypatch.setattr(providers_pkg, "resolve_provider", _fake_resolve)

        handler = create_llm_handler(retry=1)
        handler(
            {},
            {
                "prompt": {"system": "s", "user": "u"},
                "model": {"provider": "openai", "name": "gpt-4o"},
            },
        )
        assert captured["name"] == "litellm"

    def test_params_provider_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``params["provider"]`` is forwarded verbatim to the resolver."""
        captured: dict[str, str] = {}

        class _StubProvider(_FakeProvider):
            pass

        def _fake_resolve(name: str) -> LLMProviderPort:
            captured["name"] = name
            return _StubProvider(completion_content="ok")

        import yagra.adapters.outbound.llm_providers as providers_pkg

        monkeypatch.setattr(providers_pkg, "resolve_provider", _fake_resolve)

        handler = create_llm_handler(retry=1)
        handler(
            {},
            {
                "prompt": {"system": "s", "user": "u"},
                "model": {"provider": "openai", "name": "gpt-4o"},
                "provider": "my_fake",
            },
        )
        assert captured["name"] == "my_fake"

    def test_unknown_provider_raises_structured_config_error(self) -> None:
        """Unknown provider names surface a 4-field structured payload."""
        handler = create_llm_handler(retry=1)
        with pytest.raises(LLMHandlerConfigError) as excinfo:
            handler(
                {},
                {
                    "prompt": {"system": "s", "user": "u"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "provider": "no_such_provider",
                },
            )
        payload = excinfo.value.args[0]
        assert isinstance(payload, dict)
        assert set(payload) == {"error", "message", "summary", "hint"}
        assert payload["error"] == "unknown_provider"
        assert "no_such_provider" in payload["summary"]["provider"]

    def test_non_string_provider_raises_structured_config_error(self) -> None:
        """Non-string params.provider is rejected with a 4-field payload."""
        handler = create_llm_handler(retry=1)
        with pytest.raises(LLMHandlerConfigError) as excinfo:
            handler(
                {},
                {
                    "prompt": {"system": "s", "user": "u"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "provider": 123,  # not a str
                },
            )
        payload = excinfo.value.args[0]
        assert isinstance(payload, dict)
        assert payload["error"] == "invalid_provider_param"


class TestStructuredHandlerUnknownProvider:
    """SC-13 for ``create_structured_llm_handler``."""

    def test_unknown_provider_raises_structured_config_error(self) -> None:
        from pydantic import BaseModel

        class _Out(BaseModel):
            value: int

        handler = create_structured_llm_handler(schema=_Out, retry=1)
        with pytest.raises(LLMHandlerConfigError) as excinfo:
            handler(
                {},
                {
                    "prompt": {"system": "s", "user": "u"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "provider": "ghost_provider",
                },
            )
        payload = excinfo.value.args[0]
        assert set(payload) == {"error", "message", "summary", "hint"}
        assert payload["error"] == "unknown_provider"


class TestStreamingHandlerUnknownProvider:
    """SC-13 for ``create_streaming_llm_handler``."""

    def test_unknown_provider_raises_structured_config_error(self) -> None:
        handler = create_streaming_llm_handler(retry=1)
        with pytest.raises(LLMHandlerConfigError) as excinfo:
            handler(
                {},
                {
                    "prompt": {"system": "s", "user": "u"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "provider": "ghost_provider",
                },
            )
        payload = excinfo.value.args[0]
        assert set(payload) == {"error", "message", "summary", "hint"}
        assert payload["error"] == "unknown_provider"
