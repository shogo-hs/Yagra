"""Unit tests for LLM handler."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# litellmをモックとしてインポート時に注入
@pytest.fixture
def mock_litellm_import():
    """litellmをモック化する fixture（autouse=True を削除して Issue #11 を修正）."""
    with patch.dict("sys.modules", {"litellm": MagicMock()}):
        yield


from yagra.handlers.llm_handler import (  # noqa: E402
    LLMHandlerCallError,
    LLMHandlerConfigError,
    create_llm_handler,
)


class TestCreateLLMHandler:
    """create_llm_handler関数のテスト."""

    def test_create_llm_handler_returns_callable(self, mock_litellm_import: None) -> None:
        """ファクトリ関数がcallableを返すこと."""
        handler = create_llm_handler()
        assert callable(handler)

    def test_create_llm_handler_without_litellm_raises_import_error(self) -> None:
        """litellmがインストールされていない場合にImportErrorが発生すること."""
        # litellm グローバル変数を None にパッチして未インストール状態を再現する
        with patch("yagra.handlers.llm_handler.litellm", None):
            with pytest.raises(ImportError, match="litellm is not installed"):
                from yagra.handlers.llm_handler import create_llm_handler as create_fn

                create_fn()


class TestLLMHandler:
    """LLMハンドラーの動作テスト."""

    def test_handler_basic_call(self, mock_litellm_import: None) -> None:
        """正常系: LLM呼び出しが成功すること."""
        handler = create_llm_handler(retry=1, timeout=10)

        # litellm.completionをモック
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello, world!"))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
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

    def test_handler_prompt_interpolation(self, mock_litellm_import: None) -> None:
        """{variable}形式の変数置換が正しく動作すること."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
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

            # litellm.completionが正しいメッセージで呼ばれたか確認
            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "My name is Alice and I am 30 years old"
            assert result == {"result": "Test response"}

    @pytest.mark.skip(
        reason="Issue #11: pytest fixture と例外ハンドリングの競合。"
        "実装は正しく動作しており、結合テストでカバー済み"
    )
    def test_handler_missing_prompt_raises_error(self, mock_litellm_import: None) -> None:
        """promptパラメータが不足している場合にエラーが発生すること.

        Note: このテストは Issue #11 によりスキップされています。
        例外は正しく発生しますが、pytest.raises および try/except での検証が
        fixture との競合により失敗します。実際の例外発生は結合テストで検証済みです。
        """
        handler = create_llm_handler()

        state: dict[str, Any] = {}
        params = {
            "model": {"provider": "openai", "name": "gpt-4"},
        }

        with pytest.raises(LLMHandlerConfigError, match="'prompt' must be a dict"):
            handler(state, params)

    @pytest.mark.skip(reason="Issue #11: fixture と例外ハンドリングの競合")
    def test_handler_missing_model_raises_error(self, mock_litellm_import: None) -> None:
        """modelパラメータが不足している場合にエラーが発生すること."""
        handler = create_llm_handler()

        state: dict[str, Any] = {}
        params = {
            "prompt": {"system": "Test", "user": "Test"},
        }

        with pytest.raises(LLMHandlerConfigError, match="'model' must be a dict"):
            handler(state, params)

    @pytest.mark.skip(reason="Issue #11: fixture と例外ハンドリングの競合")
    def test_handler_missing_model_provider_raises_error(self, mock_litellm_import: None) -> None:
        """model.providerが不足している場合にエラーが発生すること."""
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

    def test_handler_retry_on_failure(self, mock_litellm_import: None) -> None:
        """失敗時にリトライが実行されること."""
        handler = create_llm_handler(retry=3, timeout=10)

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            # 最初の2回は失敗、3回目で成功
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Success"))]

            mock_litellm.completion.side_effect = [
                Exception("Rate limit"),
                Exception("Timeout"),
                mock_response,
            ]

            with patch("yagra.handlers.llm_handler.time.sleep"):  # sleepをスキップ
                state = {"query": "test"}
                params = {
                    "prompt": {"system": "Test", "user": "{query}"},
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "output_key": "output",
                }

                result = handler(state, params)

                assert result == {"output": "Success"}
                assert mock_litellm.completion.call_count == 3

    @pytest.mark.skip(reason="Issue #11: fixture と例外ハンドリングの競合")
    def test_handler_fails_after_max_retry(self, mock_litellm_import: None) -> None:
        """最大リトライ回数に達した場合にエラーが発生すること."""
        handler = create_llm_handler(retry=2, timeout=10)

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            mock_litellm.completion.side_effect = Exception("Persistent error")

            with patch("yagra.handlers.llm_handler.time.sleep"):
                state = {"query": "test"}
                params = {
                    "prompt": {"system": "Test", "user": "{query}"},
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "output_key": "output",
                }

                with pytest.raises(LLMHandlerCallError, match="LLM call failed after 2 attempts"):
                    handler(state, params)

    def test_handler_with_model_kwargs(self, mock_litellm_import: None) -> None:
        """model.kwargsが正しくlitellmに渡されること."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Response"))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
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

    def test_handler_default_output_key(self, mock_litellm_import: None) -> None:
        """output_keyが省略された場合、デフォルトで'output'が使われること."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Default output"))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                # output_key省略
            }

            result = handler(state, params)

            assert "output" in result
            assert result["output"] == "Default output"

    @pytest.mark.skip(reason="Issue #11: fixture と例外ハンドリングの競合")
    def test_handler_empty_response_raises_error(self, mock_litellm_import: None) -> None:
        """LLMが空のレスポンスを返した場合にエラーが発生すること."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = []

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerCallError, match="LLM returned empty response"):
                handler(state, params)

    @pytest.mark.skip(reason="Issue #11: fixture と例外ハンドリングの競合")
    def test_handler_none_content_raises_error(self, mock_litellm_import: None) -> None:
        """LLMがNoneコンテンツを返した場合にエラーが発生すること."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerCallError, match="LLM returned None content"):
                handler(state, params)


class TestLLMHandlerAutoDetect:
    """input_keys 自動検出のテスト."""

    def test_auto_detect_single_variable(self, mock_litellm_import: None) -> None:
        """プロンプトに {query} があれば state から自動取得すること."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Auto detect response"))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "Hello"}
            params = {
                "prompt": {"system": "Assistant", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                "output_key": "response",
                # input_keys 未指定 → 自動検出
            }

            result = handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "Hello"
            assert result == {"response": "Auto detect response"}

    def test_auto_detect_multiple_variables(self, mock_litellm_import: None) -> None:
        """プロンプトに {name} と {age} があれば両方 state から自動取得すること."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Multi var response"))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"name": "Alice", "age": "30"}
            params = {
                "prompt": {"system": "Assistant", "user": "Name: {name}, Age: {age}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                # input_keys 未指定 → 自動検出
            }

            handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "Name: Alice, Age: 30"

    def test_explicit_input_keys_takes_priority(self, mock_litellm_import: None) -> None:
        """input_keys が明示指定されていればそちらを優先すること（後方互換）."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Explicit keys response"))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "Hello"}
            params = {
                "prompt": {"system": "Assistant", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                "input_keys": ["query"],  # 明示指定
            }

            result = handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "Hello"
            assert result == {"output": "Explicit keys response"}

    def test_explicit_empty_input_keys_disables_interpolation(
        self, mock_litellm_import: None
    ) -> None:
        """input_keys: [] を明示指定した場合は変数埋め込みなし（後方互換）."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="No interpolation"))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state = {"query": "Hello"}
            params = {
                "prompt": {"system": "Assistant", "user": "No variables here"},
                "model": {"provider": "openai", "name": "gpt-4"},
                "input_keys": [],  # 空リスト明示
            }

            result = handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == "No variables here"
            assert result == {"output": "No interpolation"}

    def test_auto_detect_missing_key_uses_empty_string(self, mock_litellm_import: None) -> None:
        """自動検出したキーが state に存在しない場合は空文字を使うこと."""
        handler = create_llm_handler(retry=1, timeout=10)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Empty key response"))]

        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response

            state: dict[str, str] = {}  # query が存在しない
            params = {
                "prompt": {"system": "Assistant", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                # input_keys 未指定 → 自動検出
            }

            result = handler(state, params)

            call_args = mock_litellm.completion.call_args
            messages = call_args.kwargs["messages"]
            assert messages[1]["content"] == ""  # 空文字に置換
            assert result == {"output": "Empty key response"}


class TestLLMHandlerValidationErrors:
    """パラメータバリデーションエラーのテスト（patch コンテキストで動作確認）."""

    def test_handler_prompt_not_dict_raises_config_error(
        self, mock_litellm_import: None
    ) -> None:
        """prompt が dict でない場合に LLMHandlerConfigError が発生すること."""
        with patch("yagra.handlers.llm_handler.litellm") as _mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            state: dict[str, Any] = {}
            params = {
                "prompt": "not a dict",
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerConfigError, match="'prompt' must be a dict"):
                handler(state, params)

    def test_handler_model_not_dict_raises_config_error(
        self, mock_litellm_import: None
    ) -> None:
        """model が dict でない場合に LLMHandlerConfigError が発生すること."""
        with patch("yagra.handlers.llm_handler.litellm") as _mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            state: dict[str, Any] = {}
            params = {
                "prompt": {"system": "Test", "user": "Test"},
                "model": "gpt-4",
            }

            with pytest.raises(LLMHandlerConfigError, match="'model' must be a dict"):
                handler(state, params)

    def test_handler_model_missing_provider_raises_config_error(
        self, mock_litellm_import: None
    ) -> None:
        """model に provider が欠損している場合に LLMHandlerConfigError が発生すること."""
        with patch("yagra.handlers.llm_handler.litellm") as _mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            state: dict[str, Any] = {}
            params = {
                "prompt": {"system": "Test", "user": "Test"},
                "model": {"name": "gpt-4"},  # provider なし
            }

            with pytest.raises(
                LLMHandlerConfigError,
                match="'model' must have 'provider' and 'name' keys",
            ):
                handler(state, params)

    def test_handler_model_missing_name_raises_config_error(
        self, mock_litellm_import: None
    ) -> None:
        """model に name が欠損している場合に LLMHandlerConfigError が発生すること."""
        with patch("yagra.handlers.llm_handler.litellm") as _mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            state: dict[str, Any] = {}
            params = {
                "prompt": {"system": "Test", "user": "Test"},
                "model": {"provider": "openai"},  # name なし
            }

            with pytest.raises(
                LLMHandlerConfigError,
                match="'model' must have 'provider' and 'name' keys",
            ):
                handler(state, params)

    def test_handler_prompt_interpolation_key_error_raises_config_error(
        self, mock_litellm_import: None
    ) -> None:
        """input_keys に存在するキーが user テンプレートに含まれない変数を参照する場合に
        LLMHandlerConfigError が発生すること.

        input_keys=["a"] で user="{b}" のとき、
        input_values = {"a": state.get("a", "")} となり、
        "{b}".format(a="") で KeyError: 'b' が発生する。
        """
        with patch("yagra.handlers.llm_handler.litellm") as _mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            state: dict[str, Any] = {"a": "value_a"}
            params = {
                "prompt": {"system": "Test", "user": "Hello {b}"},
                "model": {"provider": "openai", "name": "gpt-4"},
                "input_keys": ["a"],  # "b" を含まない keys で format するため KeyError
            }

            with pytest.raises(
                LLMHandlerConfigError,
                match="Missing key in state for prompt interpolation",
            ):
                handler(state, params)


class TestLLMHandlerCallErrors:
    """LLM 呼び出しエラーのテスト（patch コンテキストで動作確認）."""

    def test_handler_empty_choices_raises_call_error(
        self, mock_litellm_import: None
    ) -> None:
        """LLM が空の choices を返した場合に LLMHandlerCallError が発生すること."""
        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            mock_response = MagicMock()
            mock_response.choices = []
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerCallError, match="LLM returned empty response"):
                handler(state, params)

    def test_handler_none_content_raises_call_error(
        self, mock_litellm_import: None
    ) -> None:
        """LLM が None コンテンツを返した場合に LLMHandlerCallError が発生すること."""
        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            handler = create_llm_handler(retry=1, timeout=10)

            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content=None))]
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerCallError, match="LLM returned None content"):
                handler(state, params)

    def test_handler_call_error_not_retried(self, mock_litellm_import: None) -> None:
        """LLMHandlerCallError はリトライせずに即座に送出されること.

        retry=3 を指定しても、empty choices の場合は completion が1回しか
        呼ばれないことを確認する（line 187 の ``raise`` ブランチ）。
        """
        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            handler = create_llm_handler(retry=3, timeout=10)

            mock_response = MagicMock()
            mock_response.choices = []  # LLMHandlerCallError をトリガー
            mock_litellm.completion.return_value = mock_response

            state = {"query": "test"}
            params = {
                "prompt": {"system": "Test", "user": "{query}"},
                "model": {"provider": "openai", "name": "gpt-4"},
            }

            with pytest.raises(LLMHandlerCallError):
                handler(state, params)

            # リトライされず1回だけ呼ばれること
            assert mock_litellm.completion.call_count == 1

    def test_handler_api_error_retried_and_finally_fails(
        self, mock_litellm_import: None
    ) -> None:
        """API 呼び出し失敗がリトライされ、最終的に LLMHandlerCallError が発生すること."""
        with patch("yagra.handlers.llm_handler.litellm") as mock_litellm:
            with patch("yagra.handlers.llm_handler.time.sleep"):
                handler = create_llm_handler(retry=2, timeout=10)

                mock_litellm.completion.side_effect = RuntimeError("api error")

                state = {"query": "test"}
                params = {
                    "prompt": {"system": "Test", "user": "{query}"},
                    "model": {"provider": "openai", "name": "gpt-4"},
                    "output_key": "output",
                }

                with pytest.raises(
                    LLMHandlerCallError, match="LLM call failed after 2 attempts"
                ):
                    handler(state, params)

                # retry=2 なので completion が2回呼ばれること
                assert mock_litellm.completion.call_count == 2
