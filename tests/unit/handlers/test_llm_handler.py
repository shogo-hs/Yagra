"""Unit tests for LLM handler."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from yagra.handlers.llm_handler import (
    LLMHandlerCallError,
    LLMHandlerConfigError,
    create_llm_handler,
)


class TestCreateLLMHandler:
    """Tests for the create_llm_handler function."""

    def test_create_llm_handler_returns_callable(self) -> None:
        """Confirms that the factory function returns a callable."""
        handler = create_llm_handler()
        assert callable(handler)


class TestLLMHandler:
    """Tests for the behavior of the LLM handler."""

    def test_handler_basic_call(self) -> None:
        """Confirms that a successful LLM call works correctly."""
        handler = create_llm_handler(retry=1, timeout=10)

        # Mock litellm.completion
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello, world!"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "こんにちは"}
            params = {
                "prompt": {"system": "You are a helpful assistant", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                "output_key": "response",
            }

            result = handler(state, params)

            assert result == {"response": "Hello, world!"}
            mock_litellm.completion.assert_called_once()

    def test_handler_prompt_interpolation(self) -> None:
        """Confirms that {variable} format variable substitution works correctly."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"name": "Alice", "age": 30}
            params = {
                "prompt": {
                    "system": "Assistant",
                    "user": "My name is {name} and I am {age} years old",
                },
                "model": {"provider": "openai", "name": "gpt-4"},
                "output_key": "result",
            }

            result = handler(state, params)

            # Verify litellm.completion was called with the correct messages
            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "My name is Alice and I am 30 years old"
            assert result == {"result": "Test response"}

    def test_handler_missing_prompt_raises_error(self) -> None:
        """Confirms that an error is raised when the prompt parameter is missing."""
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm"):
            handler = create_llm_handler()

            state: dict[str, Any] = {}
            params = {
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerConfigError, match="'prompt' must be a dict"):
                handler(state, params)

    def test_handler_missing_model_raises_error(self) -> None:
        """Confirms that an error is raised when the model parameter is missing."""
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm"):
            handler = create_llm_handler()

            state: dict[str, Any] = {}
            params = {
                "prompt": {"system": "Test", "user": "Test"},
            }

            with pytest.raises(LLMHandlerConfigError, match="'model' must be a dict"):
                handler(state, params)

    def test_handler_missing_model_provider_raises_error(self) -> None:
        """Confirms that an error is raised when model.provider is missing."""
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm"):
            handler = create_llm_handler()

            state: dict[str, Any] = {}
            params = {
                "prompt": {"system": "Test", "user": "Test"},
                "model": {"name": "gpt-4"},
            }

            with pytest.raises(
                LLMHandlerConfigError, match="'model' must have 'provider' and 'name' keys"
            ):
                handler(state, params)

    def test_handler_retry_on_failure(self) -> None:
        """Confirms that retry is executed on failure."""
        handler = create_llm_handler(retry=3, timeout=10)

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            # First 2 attempts fail, 3rd succeeds
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Success"))]

            mock_litellm.completion.side_effect = [
                Exception("Rate limit"),
                Exception("Timeout"),
                mock_response,
            ]

            with patch("yagra.handlers._llm_common.time.sleep"):  # skip sleep
                state = {"query": "test"}
                params = {
                    "prompt": {"system": "Test", "user": "{query}"},
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "output_key": "output",
                }

                result = handler(state, params)

                assert result == {"output": "Success"}
                assert mock_litellm.completion.call_count == 3

    def test_handler_fails_after_max_retry(self) -> None:
        """Confirms that an error is raised when the maximum retry count is reached."""
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            handler = create_llm_handler(retry=2, timeout=10)
            mock_litellm.completion.side_effect = Exception("Persistent error")

            with patch("yagra.handlers._llm_common.time.sleep"):
                state = {"query": "test"}
                params = {
                    "prompt": {"system": "Test", "user": "{query}"},
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "output_key": "output",
                }

                with pytest.raises(LLMHandlerCallError, match="LLM call failed after 2 attempts"):
                    handler(state, params)

    def test_handler_with_model_kwargs(self) -> None:
        """Confirms that model.kwargs are correctly passed to litellm."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {
                    "provider": "openai",
                    "name": "gpt-4",
                    "kwargs": {"temperature": 0.5, "max_tokens": 100},
                },
            }

            handler(state, params)

            call_args = mock_litellm.completion.call_args
            assert call_args.kwargs["temperature"] == 0.5
            assert call_args.kwargs["max_tokens"] == 100

    def test_handler_default_output_key(self) -> None:
        """Confirms that 'output' is used as the default when output_key is omitted."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Default output"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                # output_key omitted
            }

            result = handler(state, params)

            assert "output" in result
            assert result["output"] == "Default output"

    def test_handler_empty_response_raises_error(self) -> None:
        """Confirms that an error is raised when the LLM returns an empty response."""
        mock_response = MagicMock()
        mock_response.choices = []

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerCallError, match="litellm returned empty choices"):
                handler(state, params)

    def test_handler_none_content_raises_error(self) -> None:
        """Confirms that an error is raised when the LLM returns None content."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerCallError, match="litellm returned None content"):
                handler(state, params)


class TestLLMHandlerSystemPromptInterpolation:
    """Tests for state variable interpolation in system prompt."""

    def test_system_prompt_variable_interpolation(self) -> None:
        """Confirms that {variable} in system prompt is substituted from state."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"language": "Japanese", "query": "Hello"}
            params = {
                "prompt": {
                    "system": "You are a helpful assistant. Always respond in {language}.",
                    "user": "{query}",
                },
                "model": {"provider": "openai", "name": "gpt-4"},
                "output_key": "result",
            }

            handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert (
                messages[0]["content"] == "You are a helpful assistant. Always respond in Japanese."
            )
            assert messages[1]["content"] == "Hello"

    def test_system_prompt_only_variable(self) -> None:
        """Confirms that variables only in system prompt (no user vars) are auto-detected."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"role": "translator"}
            params = {
                "prompt": {
                    "system": "You are a {role}.",
                    "user": "Translate this text.",
                },
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[0]["content"] == "You are a translator."
            assert messages[1]["content"] == "Translate this text."

    def test_system_and_user_share_variable(self) -> None:
        """Confirms that the same variable in both system and user is expanded correctly."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"lang": "French"}
            params = {
                "prompt": {
                    "system": "Respond in {lang}.",
                    "user": "Translate to {lang}.",
                },
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[0]["content"] == "Respond in French."
            assert messages[1]["content"] == "Translate to French."

    def test_explicit_input_keys_applies_to_both_prompts(self) -> None:
        """Confirms that explicit input_keys are applied to both system and user prompts."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"lang": "Spanish", "text": "Hello world"}
            params = {
                "prompt": {
                    "system": "You respond in {lang}.",
                    "user": "Translate: {text}",
                },
                "model": {"provider": "openai", "name": "gpt-4"},
                "input_keys": ["lang", "text"],
            }

            handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[0]["content"] == "You respond in Spanish."
            assert messages[1]["content"] == "Translate: Hello world"


class TestLLMHandlerAutoDetect:
    """Tests for automatic input_keys detection."""

    def test_auto_detect_single_variable(self) -> None:
        """Confirms that {query} in the prompt is automatically fetched from state."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Auto detect response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "Hello"}
            params = {
                "prompt": {"system": "Assistant", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                "output_key": "response",
                # input_keys not specified → auto-detection
            }

            result = handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "Hello"
            assert result == {"response": "Auto detect response"}

    def test_auto_detect_multiple_variables(self) -> None:
        """Confirms that both {name} and {age} in the prompt are auto-fetched from state."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Multi var response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"name": "Alice", "age": "30"}
            params = {
                "prompt": {"system": "Assistant", "user": "Name: {name}, Age: {age}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                # input_keys not specified → auto-detection
            }

            handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "Name: Alice, Age: 30"

    def test_explicit_input_keys_takes_priority(self) -> None:
        """Confirms that explicitly specified input_keys take priority (backward compatibility)."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Explicit keys response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "Hello"}
            params = {
                "prompt": {"system": "Assistant", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                "input_keys": ["query"],  # explicitly specified
            }

            result = handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "Hello"
            assert result == {"output": "Explicit keys response"}

    def test_explicit_empty_input_keys_disables_interpolation(self) -> None:
        """Confirms that explicitly specifying input_keys: [] disables interpolation (backward compatibility)."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="No interpolation"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "Hello"}
            params = {
                "prompt": {"system": "Assistant", "user": "No variables here"},
                "model": {"provider": "openai", "name": "gpt-4"},
                "input_keys": [],  # explicitly empty list
            }

            result = handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "No variables here"
            assert result == {"output": "No interpolation"}

    def test_auto_detect_missing_key_uses_empty_string(self) -> None:
        """Confirms that an empty string is used when an auto-detected key is not in state."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Empty key response"))]

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state: dict[str, str] = {}  # query does not exist
            params = {
                "prompt": {"system": "Assistant", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                # input_keys not specified → auto-detection
            }

            result = handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == ""  # replaced with empty string
            assert result == {"output": "Empty key response"}


class TestLLMHandlerValidationErrors:
    """Tests for parameter validation errors (verified in patch context)."""

    def test_handler_prompt_not_dict_raises_config_error(self) -> None:
        """Confirms that LLMHandlerConfigError is raised when prompt is not a dict."""
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as _mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            state: dict[str, Any] = {}
            params = {
                "prompt": "not a dict",
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerConfigError, match="'prompt' must be a dict"):
                handler(state, params)

    def test_handler_model_not_dict_raises_config_error(self) -> None:
        """Confirms that LLMHandlerConfigError is raised when model is not a dict."""
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as _mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            state: dict[str, Any] = {}
            params = {
                "prompt": {"system": "Test", "user": "Test"},
                "model": "gpt-4",
            }

            with pytest.raises(LLMHandlerConfigError, match="'model' must be a dict"):
                handler(state, params)

    def test_handler_model_missing_provider_raises_config_error(self) -> None:
        """Confirms that LLMHandlerConfigError is raised when provider is missing from model."""
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as _mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            state: dict[str, Any] = {}
            params = {
                "prompt": {"system": "Test", "user": "Test"},
                "model": {"name": "gpt-4"},  # no provider
            }

            with pytest.raises(
                LLMHandlerConfigError,
                match="'model' must have 'provider' and 'name' keys",
            ):
                handler(state, params)

    def test_handler_model_missing_name_raises_config_error(self) -> None:
        """Confirms that LLMHandlerConfigError is raised when name is missing from model."""
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as _mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            state: dict[str, Any] = {}
            params = {
                "prompt": {"system": "Test", "user": "Test"},
                "model": {"provider": "openai"},  # no name
            }

            with pytest.raises(
                LLMHandlerConfigError,
                match="'model' must have 'provider' and 'name' keys",
            ):
                handler(state, params)

    def test_handler_input_keys_ignored_auto_extraction_resolves(self) -> None:
        """Confirms that input_keys is ignored and auto-extraction from template succeeds.

        With auto-extraction, {b} in user template is resolved from state (defaulting to "").
        The input_keys parameter is no longer consulted.
        """
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "response"
            mock_response.usage = None
            mock_litellm.completion.return_value = mock_response

            state: dict[str, Any] = {"a": "value_a"}
            params = {
                "prompt": {"system": "Test", "user": "Hello {b}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                "input_keys": ["a"],  # ignored; {b} is auto-extracted and resolved to ""
            }

            # No error raised; auto-extraction finds {b} and resolves it from state as ""
            handler(state, params)


class TestLLMHandlerCallErrors:
    """Tests for LLM call errors (verified in patch context)."""

    def test_handler_empty_choices_raises_call_error(self) -> None:
        """Confirms that LLMHandlerCallError is raised when LLM returns empty choices.

        Under the Port-routed implementation, empty choices surface as an
        :class:`LLMProviderCallError` which is retried by ``llm_retry_loop``
        and finally wrapped into :class:`LLMHandlerCallError`.
        """
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            mock_response = MagicMock()
            mock_response.choices = []
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerCallError, match="litellm returned empty choices"):
                handler(state, params)

    def test_handler_none_content_raises_call_error(self) -> None:
        """Confirms that LLMHandlerCallError is raised when LLM returns None content."""
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content=None))]
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerCallError, match="litellm returned None content"):
                handler(state, params)

    def test_provider_call_error_is_retried(self) -> None:
        """Port-level call errors are retried by ``llm_retry_loop``.

        Confirms the Port-routed retry contract: an
        :class:`LLMProviderCallError` raised by the adapter (empty choices)
        is retried ``effective_retry`` times before finally surfacing as
        :class:`LLMHandlerCallError`.
        """
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            with patch("yagra.handlers._llm_common.time.sleep"):
                handler = create_llm_handler(retry=3, timeout=10)

                mock_response = MagicMock()
                mock_response.choices = []  # empty choices -> LLMProviderCallError
                mock_litellm.completion.return_value = mock_response

                state = {"query": "test"}
                params = {
                    "prompt": {"system": "Test", "user": "{query}"},
                    "model": {"provider": "openai", "name": "gpt-4"},
                }

                with pytest.raises(LLMHandlerCallError):
                    handler(state, params)

                # Port-level call errors retry up to retry= count
                assert mock_litellm.completion.call_count == 3

    def test_handler_api_error_retried_and_finally_fails(self) -> None:
        """Confirms that API call failures are retried and finally raise LLMHandlerCallError."""
        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
        ) as mock_litellm:
            with patch("yagra.handlers._llm_common.time.sleep"):
                handler = create_llm_handler(retry=2, timeout=10)

                mock_litellm.completion.side_effect = RuntimeError("api error")

                state = {"query": "test"}
                params = {
                    "prompt": {"system": "Test", "user": "{query}"},
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "output_key": "output",
                }

                with pytest.raises(LLMHandlerCallError, match="LLM call failed after 2 attempts"):
                    handler(state, params)

                # retry=2 so completion is called twice
                assert mock_litellm.completion.call_count == 2
