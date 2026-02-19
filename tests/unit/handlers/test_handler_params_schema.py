"""Unit tests for handler PARAMS_SCHEMA constants and `yagra handlers` CLI command."""

import json
from unittest.mock import MagicMock, patch

with patch.dict("sys.modules", {"litellm": MagicMock()}):
    from yagra.handlers.llm_handler import LLM_HANDLER_PARAMS_SCHEMA
    from yagra.handlers.streaming_llm_handler import STREAMING_LLM_HANDLER_PARAMS_SCHEMA
    from yagra.handlers.structured_llm_handler import STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA


class TestLLMHandlerParamsSchema:
    """Tests for validating the contents of LLM_HANDLER_PARAMS_SCHEMA."""

    def test_schema_is_dict(self) -> None:
        """Schema should be a dict."""
        assert isinstance(LLM_HANDLER_PARAMS_SCHEMA, dict)

    def test_schema_type_is_object(self) -> None:
        """Top-level type of the schema should be 'object'."""
        assert LLM_HANDLER_PARAMS_SCHEMA["type"] == "object"

    def test_model_is_required(self) -> None:
        """'model' should be included in required."""
        assert "model" in LLM_HANDLER_PARAMS_SCHEMA["required"]

    def test_properties_contains_expected_keys(self) -> None:
        """Properties should contain prompt, prompt_ref, model, and output_key."""
        props = LLM_HANDLER_PARAMS_SCHEMA["properties"]
        for key in ("prompt", "prompt_ref", "model", "output_key"):
            assert key in props, f"'{key}' not found in properties"

    def test_one_of_requires_prompt_or_prompt_ref(self) -> None:
        """OneOf should define prompt or prompt_ref as required."""
        one_of = LLM_HANDLER_PARAMS_SCHEMA["oneOf"]
        required_sets = [set(item.get("required", [])) for item in one_of]
        assert {"prompt"} in required_sets
        assert {"prompt_ref"} in required_sets


class TestStructuredLLMHandlerParamsSchema:
    """Tests for validating the contents of STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA."""

    def test_schema_is_dict(self) -> None:
        """Schema should be a dict."""
        assert isinstance(STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA, dict)

    def test_schema_type_is_object(self) -> None:
        """Top-level type of the schema should be 'object'."""
        assert STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA["type"] == "object"

    def test_model_is_required(self) -> None:
        """'model' should be included in required."""
        assert "model" in STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA["required"]

    def test_properties_contains_expected_keys(self) -> None:
        """Properties should contain model, output_key, and schema_yaml."""
        props = STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA["properties"]
        for key in ("model", "output_key", "schema_yaml"):
            assert key in props, f"'{key}' not found in properties"

    def test_one_of_requires_prompt_or_prompt_ref(self) -> None:
        """OneOf should define prompt or prompt_ref as required."""
        one_of = STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA["oneOf"]
        required_sets = [set(item.get("required", [])) for item in one_of]
        assert {"prompt"} in required_sets
        assert {"prompt_ref"} in required_sets


class TestStreamingLLMHandlerParamsSchema:
    """Tests for validating the contents of STREAMING_LLM_HANDLER_PARAMS_SCHEMA."""

    def test_schema_is_dict(self) -> None:
        """Schema should be a dict."""
        assert isinstance(STREAMING_LLM_HANDLER_PARAMS_SCHEMA, dict)

    def test_schema_type_is_object(self) -> None:
        """Top-level type of the schema should be 'object'."""
        assert STREAMING_LLM_HANDLER_PARAMS_SCHEMA["type"] == "object"

    def test_model_is_required(self) -> None:
        """'model' should be included in required."""
        assert "model" in STREAMING_LLM_HANDLER_PARAMS_SCHEMA["required"]

    def test_properties_contains_expected_keys(self) -> None:
        """Properties should contain prompt, prompt_ref, model, output_key, and stream."""
        props = STREAMING_LLM_HANDLER_PARAMS_SCHEMA["properties"]
        for key in ("prompt", "prompt_ref", "model", "output_key", "stream"):
            assert key in props, f"'{key}' not found in properties"

    def test_one_of_requires_prompt_or_prompt_ref(self) -> None:
        """OneOf should define prompt or prompt_ref as required."""
        one_of = STREAMING_LLM_HANDLER_PARAMS_SCHEMA["oneOf"]
        required_sets = [set(item.get("required", [])) for item in one_of]
        assert {"prompt"} in required_sets
        assert {"prompt_ref"} in required_sets


class TestHandlersExportsFromInit:
    """Tests confirming that PARAMS_SCHEMA constants are exported from handlers/__init__.py."""

    def test_all_schemas_exported(self) -> None:
        """All three schema constants should be included in __all__."""
        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            import yagra.handlers as h

            assert "LLM_HANDLER_PARAMS_SCHEMA" in h.__all__
            assert "STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA" in h.__all__
            assert "STREAMING_LLM_HANDLER_PARAMS_SCHEMA" in h.__all__

    def test_schemas_accessible_from_handlers_package(self) -> None:
        """Schema constants should be directly accessible from the handlers package."""
        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            from yagra.handlers import (
                LLM_HANDLER_PARAMS_SCHEMA as llm_schema,
            )
            from yagra.handlers import (
                STREAMING_LLM_HANDLER_PARAMS_SCHEMA as streaming_schema,
            )
            from yagra.handlers import (
                STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA as structured_schema,
            )

            assert isinstance(llm_schema, dict)
            assert isinstance(structured_schema, dict)
            assert isinstance(streaming_schema, dict)


class TestHandlersCLICommand:
    """Tests for the `yagra handlers` CLI command."""

    def _run_handlers_command(self, format_: str = "json") -> str:
        """Calls _run_handlers_command in a mock environment and returns captured stdout.

        Args:
            format_: Output format ("text" or "json").

        Returns:
            String written to stdout.
        """
        import argparse
        import io

        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            from yagra import _run_handlers_command

            args = argparse.Namespace(format=format_)
            captured = io.StringIO()
            with patch(
                "builtins.print", side_effect=lambda *a, **kw: captured.write(str(a[0]) + "\n")
            ):
                _run_handlers_command(args)
            return captured.getvalue()

    def test_json_output_contains_three_handlers(self) -> None:
        """JSON output should contain the three handlers: llm, structured_llm, and streaming_llm."""
        import argparse
        import io

        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            from yagra import _run_handlers_command

            args = argparse.Namespace(format="json")
            captured = io.StringIO()
            with patch(
                "builtins.print", side_effect=lambda *a, **kw: captured.write(str(a[0]) + "\n")
            ):
                exit_code = _run_handlers_command(args)

            assert exit_code == 0
            output = captured.getvalue()
            data = json.loads(output)
            assert "handlers" in data
            handler_names = [h["name"] for h in data["handlers"]]
            assert "llm" in handler_names
            assert "structured_llm" in handler_names
            assert "streaming_llm" in handler_names

    def test_json_output_each_handler_has_params_schema(self) -> None:
        """Each handler in JSON output should contain params_schema."""
        import argparse
        import io

        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            from yagra import _run_handlers_command

            args = argparse.Namespace(format="json")
            captured = io.StringIO()
            with patch(
                "builtins.print", side_effect=lambda *a, **kw: captured.write(str(a[0]) + "\n")
            ):
                _run_handlers_command(args)

            data = json.loads(captured.getvalue())
            for handler in data["handlers"]:
                assert "params_schema" in handler, f"params_schema missing for {handler['name']}"
                assert isinstance(handler["params_schema"], dict)

    def test_json_output_model_required_in_all_schemas(self) -> None:
        """'model' should be included in required for all handler schemas in JSON output."""
        import argparse
        import io

        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            from yagra import _run_handlers_command

            args = argparse.Namespace(format="json")
            captured = io.StringIO()
            with patch(
                "builtins.print", side_effect=lambda *a, **kw: captured.write(str(a[0]) + "\n")
            ):
                _run_handlers_command(args)

            data = json.loads(captured.getvalue())
            for handler in data["handlers"]:
                schema = handler["params_schema"]
                assert "model" in schema.get("required", []), (
                    f"'model' not in required for handler '{handler['name']}'"
                )

    def test_text_output_returns_zero(self) -> None:
        """Should return exit code 0 when text format is specified."""
        import argparse
        import io

        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            from yagra import _run_handlers_command

            args = argparse.Namespace(format="text")
            captured = io.StringIO()
            with patch(
                "builtins.print",
                side_effect=lambda *a, **kw: captured.write((str(a[0]) if a else "") + "\n"),
            ):
                exit_code = _run_handlers_command(args)

            assert exit_code == 0
            output = captured.getvalue()
            assert "llm" in output
            assert "structured_llm" in output
            assert "streaming_llm" in output
