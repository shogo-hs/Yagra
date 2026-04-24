"""Unit tests for LiteLLMProvider."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


class TestLiteLLMProviderSuccess:
    """Success-path tests for :class:`LiteLLMProvider`."""

    def _make_response(self, content: str) -> MagicMock:
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content=content))]
        return response

    def test_returns_parsed_json_dict(self) -> None:
        """Confirms JSON body is parsed into a dict on a happy path."""
        expected = {"score": {"relevance": 4}, "reasoning": "ok"}
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = self._make_response(json.dumps(expected))

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider

            provider = LiteLLMProvider()
            result = provider.complete_structured(
                system_prompt="Judge the answer",
                user_prompt="How good is this?",
                schema={"type": "object"},
                model="openai/gpt-4o",
            )

        assert result == expected

    def test_response_format_defaults_to_json_object(self) -> None:
        """Confirms response_format=json_object is forced when not overridden."""
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = self._make_response(json.dumps({"a": 1}))

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider

            provider = LiteLLMProvider()
            provider.complete_structured(
                system_prompt="sys",
                user_prompt="user",
                schema={"type": "object"},
                model="openai/gpt-4o",
            )

        kwargs = mock_litellm.completion.call_args.kwargs
        assert kwargs["response_format"] == {"type": "json_object"}
        assert "json" in kwargs["messages"][0]["content"].lower()

    def test_response_format_not_overridden_when_provided(self) -> None:
        """Confirms custom response_format in kwargs is preserved."""
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = self._make_response(json.dumps({"a": 1}))

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider

            provider = LiteLLMProvider()
            provider.complete_structured(
                system_prompt="sys",
                user_prompt="user",
                schema={"type": "object"},
                model="openai/gpt-4o",
                response_format={"type": "text"},
            )

        kwargs = mock_litellm.completion.call_args.kwargs
        assert kwargs["response_format"] == {"type": "text"}


class TestLiteLLMProviderErrors:
    """Error-path tests for :class:`LiteLLMProvider`."""

    def test_completion_exception_wrapped(self) -> None:
        """Confirms underlying SDK exceptions are wrapped in LLMProviderCallError."""
        mock_litellm = MagicMock()
        mock_litellm.completion.side_effect = RuntimeError("network down")

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMProviderCallError

            provider = LiteLLMProvider()
            with pytest.raises(LLMProviderCallError, match="litellm.completion failed"):
                provider.complete_structured(
                    system_prompt="s",
                    user_prompt="u",
                    schema={"type": "object"},
                    model="openai/gpt-4o",
                )

    def test_invalid_json_raises_call_error(self) -> None:
        """Confirms non-JSON content raises LLMProviderCallError."""
        mock_litellm = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="not json"))]
        mock_litellm.completion.return_value = response

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMProviderCallError

            provider = LiteLLMProvider()
            with pytest.raises(LLMProviderCallError, match="valid JSON"):
                provider.complete_structured(
                    system_prompt="s",
                    user_prompt="u",
                    schema={"type": "object"},
                    model="openai/gpt-4o",
                )

    def test_non_object_json_raises_call_error(self) -> None:
        """Confirms non-object JSON (e.g. list) raises LLMProviderCallError."""
        mock_litellm = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content=json.dumps([1, 2, 3])))]
        mock_litellm.completion.return_value = response

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMProviderCallError

            provider = LiteLLMProvider()
            with pytest.raises(LLMProviderCallError, match="not a JSON object"):
                provider.complete_structured(
                    system_prompt="s",
                    user_prompt="u",
                    schema={"type": "object"},
                    model="openai/gpt-4o",
                )

    def test_empty_choices_raises_call_error(self) -> None:
        """Confirms empty choices list raises LLMProviderCallError."""
        mock_litellm = MagicMock()
        response = MagicMock()
        response.choices = []
        mock_litellm.completion.return_value = response

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMProviderCallError

            provider = LiteLLMProvider()
            with pytest.raises(LLMProviderCallError, match="empty choices"):
                provider.complete_structured(
                    system_prompt="s",
                    user_prompt="u",
                    schema={"type": "object"},
                    model="openai/gpt-4o",
                )

    def test_none_content_raises_call_error(self) -> None:
        """Confirms None content raises LLMProviderCallError."""
        mock_litellm = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content=None))]
        mock_litellm.completion.return_value = response

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMProviderCallError

            provider = LiteLLMProvider()
            with pytest.raises(LLMProviderCallError, match="None content"):
                provider.complete_structured(
                    system_prompt="s",
                    user_prompt="u",
                    schema={"type": "object"},
                    model="openai/gpt-4o",
                )


def _build_response_mock(
    content: str,
    *,
    usage: dict[str, int] | None = None,
) -> MagicMock:
    """Builds a mock litellm response for ``complete()`` tests.

    ``spec_set`` limits attribute access to the whitelist so that
    ``getattr(response, "_usage", None)`` does not auto-return a MagicMock.
    """
    response = MagicMock(spec_set=["choices", "usage", "model_dump"])
    response.choices = [MagicMock(message=MagicMock(content=content))]
    if usage is not None:
        usage_mock = MagicMock(
            spec_set=["prompt_tokens", "completion_tokens", "total_tokens"]
        )
        usage_mock.prompt_tokens = usage["prompt_tokens"]
        usage_mock.completion_tokens = usage["completion_tokens"]
        usage_mock.total_tokens = usage["total_tokens"]
        response.usage = usage_mock
    else:
        response.usage = None
    response.model_dump = lambda: None
    return response


class TestLiteLLMProviderComplete:
    """Tests for :meth:`LiteLLMProvider.complete`."""

    def test_returns_llm_completion_with_content(self) -> None:
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = _build_response_mock("hi there")

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMCompletion

            result = LiteLLMProvider().complete(
                system_prompt="sys",
                user_prompt="user",
                model="openai/gpt-4o",
            )

        assert isinstance(result, LLMCompletion)
        assert result.content == "hi there"
        assert result.usage is None
        assert result.raw is None

    def test_returns_llm_token_usage_when_provided(self) -> None:
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = _build_response_mock(
            "ok",
            usage={"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
        )

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider

            result = LiteLLMProvider().complete(
                system_prompt="sys",
                user_prompt="user",
                model="openai/gpt-4o",
            )

        assert result.usage is not None
        assert result.usage.prompt_tokens == 5
        assert result.usage.completion_tokens == 7
        assert result.usage.total_tokens == 12

    def test_empty_choices_raises_call_error(self) -> None:
        mock_litellm = MagicMock()
        response = MagicMock()
        response.choices = []
        mock_litellm.completion.return_value = response

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMProviderCallError

            with pytest.raises(LLMProviderCallError, match="empty choices"):
                LiteLLMProvider().complete(
                    system_prompt="s", user_prompt="u", model="openai/gpt-4o",
                )

    def test_none_content_raises_call_error(self) -> None:
        mock_litellm = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content=None))]
        mock_litellm.completion.return_value = response

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMProviderCallError

            with pytest.raises(LLMProviderCallError, match="None content"):
                LiteLLMProvider().complete(
                    system_prompt="s", user_prompt="u", model="openai/gpt-4o",
                )

    def test_completion_exception_wrapped(self) -> None:
        mock_litellm = MagicMock()
        mock_litellm.completion.side_effect = RuntimeError("boom")

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMProviderCallError

            with pytest.raises(LLMProviderCallError, match="litellm.completion failed"):
                LiteLLMProvider().complete(
                    system_prompt="s", user_prompt="u", model="openai/gpt-4o",
                )


class TestLiteLLMProviderCompleteStreaming:
    """Tests for :meth:`LiteLLMProvider.complete_streaming`."""

    def _stream_chunks(self, deltas: list[str]) -> MagicMock:
        """Builds a streaming-response iterable of chunk mocks."""

        chunks: list[MagicMock] = []
        for delta in deltas:
            chunk = MagicMock(spec_set=["choices"])
            chunk.choices = [MagicMock(delta=MagicMock(content=delta))]
            chunks.append(chunk)

        response = MagicMock(spec_set=["__iter__", "usage"])
        response.__iter__ = lambda self: iter(chunks)
        response.usage = None
        return response

    def test_emits_each_delta_and_terminal_chunk(self) -> None:
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = self._stream_chunks(
            ["Hello", " ", "world"]
        )

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMStreamChunk

            chunks = list(
                LiteLLMProvider().complete_streaming(
                    system_prompt="sys",
                    user_prompt="user",
                    model="openai/gpt-4o",
                )
            )

        assert [c.delta for c in chunks if c.delta] == ["Hello", " ", "world"]
        assert isinstance(chunks[-1], LLMStreamChunk)
        assert chunks[-1].done is True
        assert chunks[-1].delta == ""

    def test_terminal_chunk_carries_usage_when_available(self) -> None:
        response = self._stream_chunks(["Hi"])
        usage_mock = MagicMock()
        usage_mock.prompt_tokens = 3
        usage_mock.completion_tokens = 4
        usage_mock.total_tokens = 7
        response.usage = usage_mock

        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = response

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider

            chunks = list(
                LiteLLMProvider().complete_streaming(
                    system_prompt="s", user_prompt="u", model="openai/gpt-4o",
                )
            )

        terminal = chunks[-1]
        assert terminal.done is True
        assert terminal.usage is not None
        assert terminal.usage.total_tokens == 7

    def test_open_stream_exception_wrapped(self) -> None:
        mock_litellm = MagicMock()
        mock_litellm.completion.side_effect = RuntimeError("network broken")

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider
            from yagra.ports.outbound.llm_provider import LLMProviderCallError

            with pytest.raises(LLMProviderCallError, match="stream.*failed"):
                list(
                    LiteLLMProvider().complete_streaming(
                        system_prompt="s", user_prompt="u", model="openai/gpt-4o",
                    )
                )

    def test_stream_forces_stream_true_regardless_of_caller(self) -> None:
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = self._stream_chunks([])

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider

            list(
                LiteLLMProvider().complete_streaming(
                    system_prompt="s",
                    user_prompt="u",
                    model="openai/gpt-4o",
                    stream=False,  # caller intends non-stream, but we force True
                )
            )

        kwargs = mock_litellm.completion.call_args.kwargs
        assert kwargs["stream"] is True
