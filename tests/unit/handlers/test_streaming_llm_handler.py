"""Unit tests for streaming LLM handler."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from yagra.application.use_cases.trace_collector import TraceContext, _trace_context
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


# --- Parameters for testing ---
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
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
        assert callable(handler)


class TestStreamingLLMHandler:
    """Tests for the handler returned by create_streaming_llm_handler."""

    def test_returns_generator(self) -> None:
        """Handler returns a Generator under output_key."""
        chunks = [_make_chunk("Hello"), _make_chunk(" world")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            assert isinstance(result["response"], Generator)

    def test_yields_chunks_in_order(self) -> None:
        """Generator yields chunks in the correct order."""
        chunks = [_make_chunk("Hello"), _make_chunk(","), _make_chunk(" world")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            collected = list(result["response"])
        assert collected == ["Hello", ",", " world"]

    def test_default_output_key_is_output(self) -> None:
        """Default output_key is 'output' when not specified."""
        params = {k: v for k, v in _BASE_PARAMS.items() if k != "output_key"}
        chunks = [_make_chunk("hi")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
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
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
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
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, params)
            list(result["response"])
            call_kwargs = mock_litellm.completion.call_args[1]
        assert call_kwargs["temperature"] == 0.5

    def test_stream_true_auto_added(self) -> None:
        """stream=True is automatically added to litellm call."""
        chunks = [_make_chunk("ok")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            list(result["response"])
            call_kwargs = mock_litellm.completion.call_args[1]
        assert call_kwargs["stream"] is True

    def test_streaming_always_forces_stream_true(self) -> None:
        """Streaming handler always forces ``stream=True`` at the Port boundary.

        Even when the caller supplies ``model.kwargs.stream = False``, the
        litellm streaming adapter unconditionally sets ``stream=True`` to
        satisfy the :meth:`LLMProviderPort.complete_streaming` contract.
        """
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
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, params)
            list(result["response"])
            call_kwargs = mock_litellm.completion.call_args[1]
        assert call_kwargs["stream"] is True

    def test_none_delta_chunks_are_skipped(self) -> None:
        """Chunks with None delta.content are skipped."""
        chunks = [
            _make_chunk("Hello"),
            _make_chunk(None),
            _make_chunk(" world"),
        ]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            collected = list(result["response"])
        assert collected == ["Hello", " world"]

    def test_buffered_join(self) -> None:
        """Generator can be buffered with join."""
        chunks = [_make_chunk("Hello"), _make_chunk(" world")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            full_text = "".join(result["response"])
        assert full_text == "Hello world"

    def test_missing_prompt_raises_config_error(self) -> None:
        """Missing prompt raises LLMHandlerConfigError."""
        params = {k: v for k, v in _BASE_PARAMS.items() if k != "prompt"}
        mock_litellm = _make_mock_litellm([])
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            with pytest.raises(LLMHandlerConfigError, match="'prompt' must be a dict"):
                handler({}, params)

    def test_missing_model_raises_config_error(self) -> None:
        """Missing model raises LLMHandlerConfigError."""
        params = {k: v for k, v in _BASE_PARAMS.items() if k != "model"}
        mock_litellm = _make_mock_litellm([])
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
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
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            with patch("yagra.handlers._llm_common.time.sleep"):
                handler = create_streaming_llm_handler(retry=3)
                result = handler({}, _BASE_PARAMS)
                assert list(result["response"]) == ["ok"]
        assert mock_litellm.completion.call_count == 2

    def test_max_retry_exceeded_raises_call_error(self) -> None:
        """Raises LLMHandlerCallError after exhausting all retries."""
        mock_litellm = MagicMock()
        mock_litellm.completion.side_effect = Exception("API error")
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            with patch("yagra.handlers._llm_common.time.sleep"):
                handler = create_streaming_llm_handler(retry=2)
                with pytest.raises(LLMHandlerCallError, match="LLM call failed after 2 attempts"):
                    handler({}, _BASE_PARAMS)


class TestStreamingLLMHandlerModelValidation:
    """Tests for model provider/name validation."""

    def test_model_missing_provider_raises_config_error(self) -> None:
        """Model に provider がない場合は LLMHandlerConfigError を送出する。"""
        params = {
            "prompt": {"system": "sys", "user": "Hello"},
            "model": {"name": "gpt-4o"},
            "output_key": "response",
        }
        mock_litellm = _make_mock_litellm([])
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            with pytest.raises(
                LLMHandlerConfigError, match="'model' must have 'provider' and 'name' keys"
            ):
                handler({}, params)

    def test_model_missing_name_raises_config_error(self) -> None:
        """Model に name がない場合は LLMHandlerConfigError を送出する。"""
        params = {
            "prompt": {"system": "sys", "user": "Hello"},
            "model": {"provider": "openai"},
            "output_key": "response",
        }
        mock_litellm = _make_mock_litellm([])
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            with pytest.raises(
                LLMHandlerConfigError, match="'model' must have 'provider' and 'name' keys"
            ):
                handler({}, params)

    def test_model_empty_provider_raises_config_error(self) -> None:
        """Model の provider が空文字の場合は LLMHandlerConfigError を送出する。"""
        params = {
            "prompt": {"system": "sys", "user": "Hello"},
            "model": {"provider": "", "name": "gpt-4o"},
            "output_key": "response",
        }
        mock_litellm = _make_mock_litellm([])
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            with pytest.raises(
                LLMHandlerConfigError, match="'model' must have 'provider' and 'name' keys"
            ):
                handler({}, params)


class TestStreamingLLMHandlerAutoExtract:
    """Tests for auto-extraction of input_keys from prompt templates."""

    def test_auto_extract_from_both_prompts(self) -> None:
        """System と user の両方からテンプレート変数を自動抽出する。"""
        params = {
            "prompt": {"system": "Respond in {lang}.", "user": "Hello {name}"},
            "model": {"provider": "openai", "name": "gpt-4o"},
            "output_key": "response",
            # input_keys を省略 → 自動抽出
        }
        chunks = [_make_chunk("Hi")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({"lang": "English", "name": "Alice"}, params)
            list(result["response"])  # generator を消費
            messages = mock_litellm.completion.call_args[1]["messages"]
        assert messages[0]["content"] == "Respond in English."
        assert messages[1]["content"] == "Hello Alice"


class TestStreamingLLMHandlerInputKeysIgnored:
    """Tests that input_keys is ignored and auto-extraction is used."""

    def test_input_keys_ignored_auto_extraction_resolves(self) -> None:
        """input_keys is ignored; auto-extraction finds all template variables and resolves them."""
        # With auto-extraction, both {name} and {other} are found and resolved from state.
        # {other} defaults to "" since it's not in state.
        params_with_extra = {
            "prompt": {"system": "sys", "user": "Hello {name} and {other}"},
            "model": {"provider": "openai", "name": "gpt-4o"},
            "input_keys": ["name"],  # ignored
            "output_key": "response",
        }
        chunks = [_make_chunk("Hi")]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({"name": "Alice"}, params_with_extra)
            list(result["response"])  # consume generator
            messages = mock_litellm.completion.call_args[1]["messages"]
        assert messages[1]["content"] == "Hello Alice and "


class TestStreamingLLMHandlerEmptyChoices:
    """Tests for chunks with empty choices list."""

    def test_empty_choices_chunk_is_skipped(self) -> None:
        """Choices が空リストのチャンクは無視され、正常に動作する。"""

        def _make_empty_choices_chunk() -> MagicMock:
            chunk = MagicMock()
            chunk.choices = []
            return chunk

        chunks = [
            _make_chunk("Hello"),
            _make_empty_choices_chunk(),
            _make_chunk(" world"),
        ]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            collected = list(result["response"])
        assert collected == ["Hello", " world"]


class TestStreamingLLMHandlerNoneDelta:
    """Tests for chunks where delta object is None."""

    def test_none_delta_object_is_skipped(self) -> None:
        """Delta オブジェクト自体が None のチャンクは無視され、正常に動作する。"""

        def _make_none_delta_chunk() -> MagicMock:
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=None)]
            return chunk

        chunks = [
            _make_chunk("Hello"),
            _make_none_delta_chunk(),
            _make_chunk(" world"),
        ]
        mock_litellm = _make_mock_litellm(chunks)
        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            collected = list(result["response"])
        assert collected == ["Hello", " world"]


class TestStreamingLLMHandlerTokenUsage:
    """Tests for token usage reporting via TraceContext."""

    def _make_mock_litellm_with_usage(
        self, chunks: list[MagicMock], usage: MagicMock | None
    ) -> MagicMock:
        """Streaming response に usage を持たせたモック litellm を作成する。"""
        mock = MagicMock()
        # iter() で作った通常の iterator に usage 属性を付けるため、
        # カスタムクラスを使う
        response = _IterableWithUsage(chunks, usage)
        mock.completion.return_value = response
        return mock

    def test_token_usage_recorded_when_trace_context_active(self) -> None:
        """Usage あり + TraceContext アクティブ → record_llm_call が呼ばれる。"""
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15

        chunks = [_make_chunk("Hi")]
        mock_litellm = self._make_mock_litellm_with_usage(chunks, mock_usage)

        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()

            # TraceContext をアクティブにする
            ctx = TraceContext()
            _trace_context.active = ctx
            try:
                result = handler({}, _BASE_PARAMS)
                list(result["response"])  # generator を消費して usage reporting を実行
                llm_call = ctx.consume_llm_call()
            finally:
                _trace_context.active = None

        assert llm_call is not None
        assert llm_call.prompt_tokens == 10
        assert llm_call.completion_tokens == 5
        assert llm_call.total_tokens == 15
        assert llm_call.model == "openai/gpt-4o"
        assert llm_call.provider == "openai"

    def test_token_usage_skipped_when_no_trace_context(self) -> None:
        """Usage あり + TraceContext なし → エラーなく完了する。"""
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15

        chunks = [_make_chunk("Hi")]
        mock_litellm = self._make_mock_litellm_with_usage(chunks, mock_usage)

        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            # TraceContext がアクティブでない状態（デフォルト）
            result = handler({}, _BASE_PARAMS)
            collected = list(result["response"])

        assert collected == ["Hi"]

    def test_token_usage_skipped_when_usage_is_none(self) -> None:
        """Usage なし → エラーなく完了する。"""
        chunks = [_make_chunk("Hi")]
        mock_litellm = self._make_mock_litellm_with_usage(chunks, usage=None)

        with patch("yagra.adapters.outbound.llm_providers.litellm_provider.litellm", mock_litellm):
            handler = create_streaming_llm_handler()
            result = handler({}, _BASE_PARAMS)
            collected = list(result["response"])

        assert collected == ["Hi"]


class _IterableWithUsage:
    """streaming response のモック用: イテラブルかつ usage 属性を持つ。"""

    def __init__(self, chunks: list[MagicMock], usage: MagicMock | None) -> None:
        self._chunks = chunks
        self.usage = usage

    def __iter__(self):  # noqa: ANN201
        return iter(self._chunks)


class TestStreamingLLMHandlerCallErrorReraised:
    """Tests for LLMHandlerCallError immediate re-raise behavior.

    Under the Port-routed implementation the litellm adapter translates any
    SDK-native exception into :class:`LLMProviderCallError`. Direct
    :class:`LLMHandlerCallError` can only originate from a handler-layer
    fault, so we exercise ``llm_retry_loop`` directly to verify it
    re-raises without consuming retries.
    """

    def test_llm_handler_call_error_is_not_retried(self) -> None:
        """``llm_retry_loop`` re-raises LLMHandlerCallError without sleeping."""
        from yagra.handlers._llm_common import llm_retry_loop

        call_count = 0

        def _raise() -> dict[str, object]:
            nonlocal call_count
            call_count += 1
            raise LLMHandlerCallError("direct call error")

        with patch("yagra.handlers._llm_common.time.sleep") as mock_sleep:
            with pytest.raises(LLMHandlerCallError, match="direct call error"):
                llm_retry_loop(_raise, 3)

        assert call_count == 1
        mock_sleep.assert_not_called()
