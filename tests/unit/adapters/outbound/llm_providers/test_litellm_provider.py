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
