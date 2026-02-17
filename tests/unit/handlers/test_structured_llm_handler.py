"""Unit tests for structured LLM handler.

構造化出力 LLM ハンドラーの単体テスト。
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel


# テスト用 Pydantic モデル
class PersonInfo(BaseModel):
    name: str
    age: int


class ExtractedEntities(BaseModel):
    names: list[str]
    locations: list[str]


class TestCreateStructuredLLMHandler:
    """create_structured_llm_handler ファクトリ関数のテスト."""

    def test_returns_callable(self) -> None:
        """create_structured_llm_handler が callable を返すこと."""
        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            from yagra.handlers import create_structured_llm_handler

            handler = create_structured_llm_handler(schema=PersonInfo)
            assert callable(handler)

    def test_raises_import_error_when_litellm_not_installed(self) -> None:
        """Litellm が未インストール時に ImportError が送出されること."""
        import sys

        # litellm モジュールをキャッシュから除去
        modules_to_remove = [k for k in sys.modules if "litellm" in k]
        original_modules = {k: sys.modules.pop(k) for k in modules_to_remove}

        # structured_llm_handler モジュールも再ロード
        if "yagra.handlers.structured_llm_handler" in sys.modules:
            del sys.modules["yagra.handlers.structured_llm_handler"]

        try:
            with patch.dict("sys.modules", {"litellm": None}):
                if "yagra.handlers.structured_llm_handler" in sys.modules:
                    del sys.modules["yagra.handlers.structured_llm_handler"]
                from yagra.handlers.structured_llm_handler import (
                    create_structured_llm_handler,
                )

                with pytest.raises(ImportError, match="litellm is not installed"):
                    create_structured_llm_handler(schema=PersonInfo)
        finally:
            sys.modules.update(original_modules)


class TestStructuredLLMHandler:
    """structured LLM handler の動作テスト."""

    @pytest.fixture
    def mock_litellm(self) -> MagicMock:
        """Litellm のモックを返すフィクスチャ."""
        return MagicMock()

    def _make_mock_response(self, content: str) -> MagicMock:
        """LLM レスポンスのモックを生成する."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        return mock_response

    def test_basic_structured_output(self, mock_litellm: MagicMock) -> None:
        """正常系: Pydantic モデルインスタンスが output_key に格納されること."""
        json_content = json.dumps({"name": "Alice", "age": 30})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            result = handler(
                state={"text": "Alice is 30 years old."},
                params={
                    "prompt": {
                        "system": "Extract person info",
                        "user": "{text}",
                    },
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "output_key": "person",
                },
            )

        assert "person" in result
        assert isinstance(result["person"], PersonInfo)
        assert result["person"].name == "Alice"
        assert result["person"].age == 30

    def test_output_key_default(self, mock_litellm: MagicMock) -> None:
        """output_key が未指定の場合はデフォルト 'output' が使われること."""
        json_content = json.dumps({"name": "Bob", "age": 25})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            result = handler(
                state={},
                params={
                    "prompt": {"system": "Extract", "user": "Extract person"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                },
            )

        assert "output" in result
        assert isinstance(result["output"], PersonInfo)

    def test_input_variable_interpolation(self, mock_litellm: MagicMock) -> None:
        """State の変数がプロンプトに正しく埋め込まれること."""
        json_content = json.dumps({"name": "Charlie", "age": 40})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            handler(
                state={"user_input": "Charlie is 40."},
                params={
                    "prompt": {"system": "Extract", "user": "Input: {user_input}"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "output_key": "person",
                },
            )

        call_messages = mock_litellm.completion.call_args.kwargs["messages"]
        assert "Input: Charlie is 40." in call_messages[1]["content"]

    def test_model_kwargs_passed_to_litellm(self, mock_litellm: MagicMock) -> None:
        """model.kwargs が litellm に正しく渡されること."""
        json_content = json.dumps({"name": "Dave", "age": 20})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            handler(
                state={},
                params={
                    "prompt": {"system": "Extract", "user": "Extract"},
                    "model": {
                        "provider": "openai",
                        "name": "gpt-4o",
                        "kwargs": {"temperature": 0.0, "max_tokens": 200},
                    },
                    "output_key": "person",
                },
            )

        call_kwargs = mock_litellm.completion.call_args.kwargs
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["max_tokens"] == 200

    def test_default_response_format_json_object(self, mock_litellm: MagicMock) -> None:
        """デフォルトで response_format=json_object が付加されること."""
        json_content = json.dumps({"name": "Eve", "age": 28})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            handler(
                state={},
                params={
                    "prompt": {"system": "Extract", "user": "Extract"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "output_key": "person",
                },
            )

        call_kwargs = mock_litellm.completion.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_custom_response_format_not_overridden(self, mock_litellm: MagicMock) -> None:
        """model.kwargs に response_format が指定された場合は上書きしないこと."""
        json_content = json.dumps({"name": "Frank", "age": 35})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        custom_format = {"type": "text"}

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            handler(
                state={},
                params={
                    "prompt": {"system": "Extract", "user": "Extract"},
                    "model": {
                        "provider": "openai",
                        "name": "gpt-4o",
                        "kwargs": {"response_format": custom_format},
                    },
                    "output_key": "person",
                },
            )

        call_kwargs = mock_litellm.completion.call_args.kwargs
        assert call_kwargs["response_format"] == custom_format

    def test_json_parse_failure_raises_call_error(self, mock_litellm: MagicMock) -> None:
        """JSON パース失敗時に LLMHandlerCallError が送出されること."""
        mock_litellm.completion.return_value = self._make_mock_response("This is not valid JSON")

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.llm_handler import LLMHandlerCallError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            with pytest.raises(LLMHandlerCallError, match="Failed to parse"):
                handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "model": {"provider": "openai", "name": "gpt-4o"},
                        "output_key": "person",
                    },
                )

    def test_pydantic_validation_failure_raises_call_error(self, mock_litellm: MagicMock) -> None:
        """Pydantic バリデーション失敗時に LLMHandlerCallError が送出されること."""
        # name は str だが age が欠けている
        invalid_json = json.dumps({"name": "Grace"})
        mock_litellm.completion.return_value = self._make_mock_response(invalid_json)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.llm_handler import LLMHandlerCallError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            with pytest.raises(LLMHandlerCallError, match="Failed to parse"):
                handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "model": {"provider": "openai", "name": "gpt-4o"},
                        "output_key": "person",
                    },
                )

    def test_missing_prompt_raises_config_error(self, mock_litellm: MagicMock) -> None:
        """Prompt が未設定の場合に LLMHandlerConfigError が送出されること."""
        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.llm_handler import LLMHandlerConfigError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            with pytest.raises(LLMHandlerConfigError, match="'prompt' must be a dict"):
                handler(
                    state={},
                    params={
                        "model": {"provider": "openai", "name": "gpt-4o"},
                        "output_key": "person",
                    },
                )

    def test_missing_model_raises_config_error(self, mock_litellm: MagicMock) -> None:
        """Model が未設定の場合に LLMHandlerConfigError が送出されること."""
        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.llm_handler import LLMHandlerConfigError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            with pytest.raises(LLMHandlerConfigError, match="'model' must be a dict"):
                handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "output_key": "person",
                    },
                )

    def test_retry_on_api_error(self, mock_litellm: MagicMock) -> None:
        """API エラー時にリトライが実行されること."""
        json_content = json.dumps({"name": "Henry", "age": 45})
        mock_litellm.completion.side_effect = [
            Exception("API Error"),
            self._make_mock_response(json_content),
        ]

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            with patch("yagra.handlers.structured_llm_handler.time.sleep") as mock_sleep:
                from yagra.handlers.structured_llm_handler import (
                    create_structured_llm_handler,
                )

                handler = create_structured_llm_handler(schema=PersonInfo, retry=2)
                result = handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "model": {"provider": "openai", "name": "gpt-4o"},
                        "output_key": "person",
                    },
                )

        assert result["person"].name == "Henry"
        assert mock_litellm.completion.call_count == 2
        mock_sleep.assert_called_once_with(1)  # 2**0 = 1

    def test_raises_after_max_retries(self, mock_litellm: MagicMock) -> None:
        """最大リトライ回数を超えた場合に LLMHandlerCallError が送出されること."""
        mock_litellm.completion.side_effect = Exception("Persistent Error")

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            with patch("yagra.handlers.structured_llm_handler.time.sleep"):
                from yagra.handlers.llm_handler import LLMHandlerCallError
                from yagra.handlers.structured_llm_handler import (
                    create_structured_llm_handler,
                )

                handler = create_structured_llm_handler(schema=PersonInfo, retry=2)
                with pytest.raises(LLMHandlerCallError, match="LLM call failed after 2 attempts"):
                    handler(
                        state={},
                        params={
                            "prompt": {"system": "Extract", "user": "Extract"},
                            "model": {"provider": "openai", "name": "gpt-4o"},
                            "output_key": "person",
                        },
                    )

    def test_complex_schema(self, mock_litellm: MagicMock) -> None:
        """リスト型フィールドを持つ複雑なスキーマが正しく動作すること."""
        json_content = json.dumps({"names": ["Alice", "Bob"], "locations": ["Tokyo", "Osaka"]})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=ExtractedEntities, retry=1)
            result = handler(
                state={"text": "Alice and Bob visited Tokyo and Osaka."},
                params={
                    "prompt": {"system": "Extract entities", "user": "{text}"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "output_key": "entities",
                },
            )

        assert isinstance(result["entities"], ExtractedEntities)
        assert result["entities"].names == ["Alice", "Bob"]
        assert result["entities"].locations == ["Tokyo", "Osaka"]

    def test_schema_json_schema_in_system_prompt(self, mock_litellm: MagicMock) -> None:
        """システムプロンプトに JSON Schema が含まれること."""
        json_content = json.dumps({"name": "Ivy", "age": 22})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            handler(
                state={},
                params={
                    "prompt": {"system": "You are a helper", "user": "Extract"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "output_key": "person",
                },
            )

        call_messages = mock_litellm.completion.call_args.kwargs["messages"]
        system_content = call_messages[0]["content"]
        assert "You are a helper" in system_content
        assert "json" in system_content.lower()


class TestDynamicSchemaHandler:
    """schema_yaml による動的スキーマ生成ハンドラーのテスト."""

    @pytest.fixture
    def mock_litellm(self) -> MagicMock:
        """Litellm のモックを返すフィクスチャ."""
        return MagicMock()

    def _make_mock_response(self, content: str) -> MagicMock:
        """LLM レスポンスのモックを生成する."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        return mock_response

    def test_dynamic_schema_basic(self, mock_litellm: MagicMock) -> None:
        """schema=None + schema_yaml で動的モデルが使われること."""
        json_content = json.dumps({"name": "Alice", "age": 30})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=None, retry=1)
            result = handler(
                state={"text": "Alice is 30"},
                params={
                    "schema_yaml": "name: str\nage: int",
                    "prompt": {
                        "system": "Extract person info",
                        "user": "{text}",
                    },
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "output_key": "person",
                },
            )

        assert "person" in result
        assert result["person"].name == "Alice"
        assert result["person"].age == 30

    def test_dynamic_schema_default_no_schema(self, mock_litellm: MagicMock) -> None:
        """ファクトリを引数なしで呼び、schema_yaml で動作すること."""
        json_content = json.dumps({"title": "Hello"})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(retry=1)
            result = handler(
                state={},
                params={
                    "schema_yaml": "title: str",
                    "prompt": {
                        "system": "Extract title",
                        "user": "Hello World",
                    },
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "output_key": "data",
                },
            )

        assert result["data"].title == "Hello"

    def test_no_schema_and_no_schema_yaml_raises_config_error(self) -> None:
        """schema=None + schema_yaml 無しで LLMHandlerConfigError が送出されること."""
        with patch("yagra.handlers.structured_llm_handler.litellm", MagicMock()):
            from yagra.handlers.llm_handler import LLMHandlerConfigError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(retry=1)
            with pytest.raises(LLMHandlerConfigError, match="schema_yaml"):
                handler(
                    state={},
                    params={
                        "prompt": {
                            "system": "Extract",
                            "user": "test",
                        },
                        "model": {"provider": "openai", "name": "gpt-4o"},
                    },
                )

    def test_invalid_schema_yaml_raises_schema_yaml_error(self) -> None:
        """schema=None + 不正な schema_yaml で SchemaYamlError が送出されること."""
        with patch("yagra.handlers.structured_llm_handler.litellm", MagicMock()):
            from yagra.handlers.schema_builder import SchemaYamlError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(retry=1)
            with pytest.raises(SchemaYamlError, match="Unsupported type"):
                handler(
                    state={},
                    params={
                        "schema_yaml": "field: UnknownType",
                        "prompt": {
                            "system": "Extract",
                            "user": "test",
                        },
                        "model": {"provider": "openai", "name": "gpt-4o"},
                    },
                )

    def test_static_schema_takes_priority(self, mock_litellm: MagicMock) -> None:
        """静的スキーマ指定時は schema_yaml より優先されること."""
        json_content = json.dumps({"name": "Bob", "age": 25})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            result = handler(
                state={},
                params={
                    "schema_yaml": "title: str",  # これは無視される
                    "prompt": {
                        "system": "Extract",
                        "user": "Bob is 25",
                    },
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "output_key": "person",
                },
            )

        assert isinstance(result["person"], PersonInfo)
        assert result["person"].name == "Bob"
