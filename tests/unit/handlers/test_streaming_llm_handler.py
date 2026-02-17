"""Unit tests for streaming LLM handler."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from yagra.handlers.llm_handler import LLMHandlerCallError, LLMHandlerConfigError
from yagra.handlers.streaming_llm_handler import create_streaming_llm_handler


def _make_chunk(content: str | None) -> MagicMock:
    """Creates a mock litellm streaming chunk."""
    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content=content))]
    return chunk


def _make_mock_litellm(chunks: list[MagicMock]) -> MagicMock:
    """Creates a mock litellm module with streaming response."""
    mock = MagicMock()
    mock.completion.return_value = iter(chunks)
    return mock


# --- テスト用パラメータ ---
_BASE_PARAMS = {
    "prompt": {"system": "You are a helpful assistant.", "user": "Hello"},
    "model": {"provider": "openai", "name": "gpt-4o"},
    "output_key": "response",
}


class TestCreateStreamingLLMHandler:
    """Tests for create_streaming_llm_handler factory function."""

    def test_returns_callable(self) -> None:
        """Returns a callable handler."""
        mock_litellm = _make_mock_litellm([])
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
        assert callable(handler)

    def test_raises_import_error_when_litellm_not_installed(self) -> None:
        """Raises ImportError when litellm is not installed."""
        with patch("yagra.handlers.streaming_llm_handler.litellm", None):
            with patch.dict("sys.modules", {"litellm": None}):
                with pytest.raises(ImportError, match="litellm is not installed"):
                    create_streaming_llm_handler()


class TestStreamingLLMHandler:
    """Tests for the handler returned by create_streaming_llm_handler."""

    def test_returns_generator(self) -> None:
        """Handler returns a Generator under output_key."""
        chunks = [_make_chunk("Hello"), _make_chunk(" world")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            assert isinstance(result["response"], Generator)

    def test_yields_chunks_in_order(self) -> None:
        """Generator yields chunks in the correct order."""
        chunks = [_make_chunk("Hello"), _make_chunk(","), _make_chunk(" world")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            collected = list(result["response"])
        assert collected == ["Hello", ",", " world"]

    def test_default_output_key_is_output(self) -> None:
        """Default output_key is 'output' when not specified."""
        params = {k: v for k, v in _BASE_PARAMS.items() if k != "output_key"}
        chunks = [_make_chunk("hi")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, params)
            assert "output" in result

    def test_variable_interpolation(self) -> None:
        """State variables are interpolated into the user prompt."""
        params = {
            "prompt": {"system": "sys", "user": "Hello {name}"},
            "model": {"provider": "openai", "name": "gpt-4o"},
            "output_key": "response",
        }
        chunks = [_make_chunk("Hi")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({"name": "Alice"}, params)
            list(result["response"])  # consume generator
            messages = mock_litellm.completion.call_args[1]["messages"]
        assert messages[1]["content"] == "Hello Alice"

    def test_model_kwargs_passed_to_litellm(self) -> None:
        """model.kwargs are passed through to litellm.completion."""
        params = {
            "prompt": {"system": "sys", "user": "Hello"},
            "model": {
                "provider": "openai",
                "name": "gpt-4o",
                "kwargs": {"temperature": 0.5},
            },
            "output_key": "response",
        }
        chunks = [_make_chunk("ok")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, params)
            list(result["response"])
            call_kwargs = mock_litellm.completion.call_args[1]
        assert call_kwargs["temperature"] == 0.5

    def test_stream_true_auto_added(self) -> None:
        """stream=True is automatically added to litellm call."""
        chunks = [_make_chunk("ok")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            list(result["response"])
            call_kwargs = mock_litellm.completion.call_args[1]
        assert call_kwargs["stream"] is True

    def test_explicit_stream_false_not_overridden(self) -> None:
        """Explicit stream=False in model.kwargs is not overridden."""
        params = {
            "prompt": {"system": "sys", "user": "Hello"},
            "model": {
                "provider": "openai",
                "name": "gpt-4o",
                "kwargs": {"stream": False},
            },
            "output_key": "response",
        }
        chunks = [_make_chunk("ok")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, params)
            list(result["response"])
            call_kwargs = mock_litellm.completion.call_args[1]
        assert call_kwargs["stream"] is False

    def test_none_delta_chunks_are_skipped(self) -> None:
        """Chunks with None delta.content are skipped."""
        chunks = [
            _make_chunk("Hello"),
            _make_chunk(None),
            _make_chunk(" world"),
        ]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            collected = list(result["response"])
        assert collected == ["Hello", " world"]

    def test_buffered_join(self) -> None:
        """Generator can be buffered with join."""
        chunks = [_make_chunk("Hello"), _make_chunk(" world")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            full_text = "".join(result["response"])
        assert full_text == "Hello world"

    def test_missing_prompt_raises_config_error(self) -> None:
        """Missing prompt raises LLMHandlerConfigError."""
        params = {k: v for k, v in _BASE_PARAMS.items() if k != "prompt"}
        mock_litellm = _make_mock_litellm([])
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            with pytest.raises(LLMHandlerConfigError, match="'prompt' must be a dict"):
                handler({}, params)

    def test_missing_model_raises_config_error(self) -> None:
        """Missing model raises LLMHandlerConfigError."""
        params = {k: v for k, v in _BASE_PARAMS.items() if k != "model"}
        mock_litellm = _make_mock_litellm([])
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            with pytest.raises(LLMHandlerConfigError, match="'model' must be a dict"):
                handler({}, params)

    def test_retry_on_api_error(self) -> None:
        """Handler retries on API errors with backoff."""
        mock_litellm = MagicMock()
        mock_litellm.completion.side_effect = [
            Exception("API error"),
            iter([_make_chunk("ok")]),
        ]
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            with patch("yagra.handlers.streaming_llm_handler.time.sleep"):
                handler = create_streaming_llm_handler(retry=3)
                result = handler({}, _BASE_PARAMS)
                assert list(result["response"]) == ["ok"]
        assert mock_litellm.completion.call_count == 2

    def test_max_retry_exceeded_raises_call_error(self) -> None:
        """Raises LLMHandlerCallError after exhausting all retries."""
        mock_litellm = MagicMock()
        mock_litellm.completion.side_effect = Exception("API error")
        with patch("yagra.handlers.streaming_llm_handler.litellm", mock_litellm):
            with patch("yagra.handlers.streaming_llm_handler.time.sleep"):
                handler = create_streaming_llm_handler(retry=2)
                with pytest.raises(LLMHandlerCallError, match="LLM call failed after 2 attempts"):
                    handler({}, _BASE_PARAMS)
