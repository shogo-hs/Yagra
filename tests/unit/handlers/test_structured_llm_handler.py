"""Unit tests for structured LLM handler."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel


# Pydantic model for testing
class PersonInfo(BaseModel):
    name: str
    age: int


class ExtractedEntities(BaseModel):
    names: list[str]
    locations: list[str]


class TestCreateStructuredLLMHandler:
    """Tests for the create_structured_llm_handler factory function."""

    def test_returns_callable(self) -> None:
        """Confirms that create_structured_llm_handler returns a callable."""
        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            from yagra.handlers import create_structured_llm_handler

            handler = create_structured_llm_handler(schema=PersonInfo)
            assert callable(handler)

    def test_raises_import_error_when_litellm_not_installed(self) -> None:
        """Confirms that ImportError is raised when litellm is not installed."""
        import sys

        # Remove litellm module from cache
        modules_to_remove = [k for k in sys.modules if "litellm" in k]
        original_modules = {k: sys.modules.pop(k) for k in modules_to_remove}

        # Reload structured_llm_handler module as well
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
    """Tests for the behavior of the structured LLM handler."""

    @pytest.fixture
    def mock_litellm(self) -> MagicMock:
        """Fixture that returns a mock for litellm."""
        return MagicMock()

    def _make_mock_response(self, content: str) -> MagicMock:
        """Generates a mock LLM response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        return mock_response

    def test_basic_structured_output(self, mock_litellm: MagicMock) -> None:
        """Confirms that a Pydantic model instance is stored in output_key on success."""
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
        """Confirms that the default key 'output' is used when output_key is not specified."""
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
        """Confirms that state variables are correctly interpolated into the prompt."""
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
        """Confirms that model.kwargs are correctly passed to litellm."""
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
        """Confirms that response_format=json_object is added by default."""
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
        """Confirms that response_format in model.kwargs is not overridden."""
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
        """Confirms that LLMHandlerCallError is raised when JSON parsing fails."""
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
        """Confirms that LLMHandlerCallError is raised when Pydantic validation fails."""
        # name is str but age is missing
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
        """Confirms that LLMHandlerConfigError is raised when prompt is not set."""
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
        """Confirms that LLMHandlerConfigError is raised when model is not set."""
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
        """Confirms that retry is executed on API error."""
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
        """Confirms that LLMHandlerCallError is raised after the maximum number of retries."""
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
        """Confirms that a complex schema with list-type fields works correctly."""
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
        """Confirms that the JSON Schema is included in the system prompt."""
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
    """Tests for the dynamic schema generation handler using schema_yaml."""

    @pytest.fixture
    def mock_litellm(self) -> MagicMock:
        """Fixture that returns a mock for litellm."""
        return MagicMock()

    def _make_mock_response(self, content: str) -> MagicMock:
        """Generates a mock LLM response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        return mock_response

    def test_dynamic_schema_basic(self, mock_litellm: MagicMock) -> None:
        """Confirms that a dynamic model is used with schema=None + schema_yaml."""
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
        """Confirms that calling the factory with no arguments works with schema_yaml."""
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
        """Confirms that LLMHandlerConfigError is raised with schema=None and no schema_yaml."""
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
        """Confirms that SchemaYamlError is raised with schema=None and invalid schema_yaml."""
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
        """Confirms that a static schema takes priority over schema_yaml."""
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
                    "schema_yaml": "title: str",  # this is ignored
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


class TestStructuredLLMHandlerEdgeCases:
    """Tests covering edge-case branches in the structured LLM handler."""

    @pytest.fixture
    def mock_litellm(self) -> MagicMock:
        return MagicMock()

    def _make_mock_response(self, content: str) -> MagicMock:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        return mock_response

    def test_missing_provider_raises_config_error(self, mock_litellm: MagicMock) -> None:
        """Covers lines 149-150: model dict missing 'provider' raises LLMHandlerConfigError."""
        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.llm_handler import LLMHandlerConfigError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            with pytest.raises(
                LLMHandlerConfigError, match="'model' must have 'provider' and 'name' keys"
            ):
                handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "model": {"name": "gpt-4o"},  # provider missing
                    },
                )

    def test_missing_model_name_raises_config_error(self, mock_litellm: MagicMock) -> None:
        """Covers lines 149-150: model dict missing 'name' raises LLMHandlerConfigError."""
        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.llm_handler import LLMHandlerConfigError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            with pytest.raises(
                LLMHandlerConfigError, match="'model' must have 'provider' and 'name' keys"
            ):
                handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "model": {"provider": "openai"},  # name missing
                    },
                )

    def test_explicit_input_keys_used_when_provided(self, mock_litellm: MagicMock) -> None:
        """Covers line 162: explicit input_keys path is taken instead of auto-extraction."""
        json_content = json.dumps({"name": "Tom", "age": 50})
        mock_litellm.completion.return_value = self._make_mock_response(json_content)

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            result = handler(
                state={"my_key": "Tom is 50 years old."},
                params={
                    "prompt": {"system": "Extract", "user": "Data: {my_key}"},
                    "model": {"provider": "openai", "name": "gpt-4o"},
                    "input_keys": ["my_key"],  # explicit keys
                    "output_key": "person",
                },
            )

        call_messages = mock_litellm.completion.call_args.kwargs["messages"]
        assert "Tom is 50 years old." in call_messages[1]["content"]
        assert result["person"].name == "Tom"

    def test_prompt_interpolation_key_error_raises_config_error(
        self, mock_litellm: MagicMock
    ) -> None:
        """Covers lines 175-177: KeyError during format raises LLMHandlerConfigError."""
        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.llm_handler import LLMHandlerConfigError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            # Use explicit input_keys pointing to a key not in state, and a template that
            # has a different brace variable so format() raises KeyError.
            with pytest.raises(
                LLMHandlerConfigError, match="Missing key in state for prompt interpolation"
            ):
                handler(
                    state={},
                    params={
                        # input_keys is None so auto-extraction is used.
                        # system contains {missing_var} which won't be in state.
                        "prompt": {"system": "Hello {missing_var}", "user": "test"},
                        "model": {"provider": "openai", "name": "gpt-4o"},
                        # Force it: explicitly set input_keys to something that causes
                        # the format to fail. We pass input_keys=[] so keys=[] but the
                        # template still contains {missing_var} which format() won't fill.
                        "input_keys": [],
                    },
                )

    def test_empty_choices_raises_call_error(self, mock_litellm: MagicMock) -> None:
        """Covers lines 210-211: empty choices list raises LLMHandlerCallError."""
        mock_response = MagicMock()
        mock_response.choices = []  # empty choices
        mock_litellm.completion.return_value = mock_response

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.llm_handler import LLMHandlerCallError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            with pytest.raises(LLMHandlerCallError, match="LLM returned empty response"):
                handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "model": {"provider": "openai", "name": "gpt-4o"},
                    },
                )

    def test_none_content_raises_call_error(self, mock_litellm: MagicMock) -> None:
        """Covers lines 215-216: None content raises LLMHandlerCallError."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]
        mock_litellm.completion.return_value = mock_response

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.llm_handler import LLMHandlerCallError
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)
            with pytest.raises(LLMHandlerCallError, match="LLM returned None content"):
                handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "model": {"provider": "openai", "name": "gpt-4o"},
                    },
                )

    def test_token_usage_recorded_when_trace_context_active(self, mock_litellm: MagicMock) -> None:
        """Covers line 233: TraceContext.current() returns a context and record_llm_call is called."""
        json_content = json.dumps({"name": "Zara", "age": 27})
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=json_content))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_litellm.completion.return_value = mock_response

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.application.use_cases.trace_collector import TraceContext
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)

            mock_ctx = MagicMock(spec=TraceContext)

            with patch(
                "yagra.application.use_cases.trace_collector.TraceContext.current",
                return_value=mock_ctx,
            ):
                result = handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "model": {"provider": "openai", "name": "gpt-4o"},
                        "output_key": "person",
                    },
                )

        assert result["person"].name == "Zara"
        mock_ctx.record_llm_call.assert_called_once_with(
            model="openai/gpt-4o",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

    def test_token_usage_not_recorded_when_usage_is_none(self, mock_litellm: MagicMock) -> None:
        """Covers the response.usage is not None guard: no call when usage is None."""
        json_content = json.dumps({"name": "Leo", "age": 33})
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=json_content))]
        mock_response.usage = None  # no usage data
        mock_litellm.completion.return_value = mock_response

        with patch("yagra.handlers.structured_llm_handler.litellm", mock_litellm):
            from yagra.handlers.structured_llm_handler import (
                create_structured_llm_handler,
            )

            handler = create_structured_llm_handler(schema=PersonInfo, retry=1)

            mock_ctx = MagicMock()
            with patch(
                "yagra.application.use_cases.trace_collector.TraceContext.current",
                return_value=mock_ctx,
            ):
                result = handler(
                    state={},
                    params={
                        "prompt": {"system": "Extract", "user": "Extract"},
                        "model": {"provider": "openai", "name": "gpt-4o"},
                        "output_key": "person",
                    },
                )

        assert result["person"].name == "Leo"
        mock_ctx.record_llm_call.assert_not_called()
