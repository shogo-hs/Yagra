"""Integration tests for structured LLM handler with workflow execution.

Validates that the structured output LLM handler works correctly when integrated with a YAML workflow.
"""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

import yagra.handlers.structured_llm_handler as slm_module


class PersonInfo(BaseModel):
    name: str
    age: int


class ExtractedEntities(BaseModel):
    names: list[str]
    locations: list[str]


class TestStructuredLLMHandlerIntegration:
    """Integration tests for the structured LLM handler."""

    @pytest.fixture(autouse=True)
    def _reset_litellm_global(self) -> Generator[None, None, None]:
        """Resets the global litellm variable in structured_llm_handler before and after each test."""
        original = slm_module.litellm
        slm_module.litellm = None  # type: ignore[assignment]
        yield
        slm_module.litellm = original

    def test_structured_handler_with_prompt_ref(self) -> None:
        """Structured output using prompt_ref should work correctly."""
        prompts_yaml = """\
extract:
  system: "Extract person info as JSON"
  user: "Extract person from: {text}"
"""

        workflow_yaml = """\
version: "1.0"
start_at: "extract"
end_at:
  - "extract"

nodes:
  - id: "extract"
    handler: "structured_llm"
    params:
      prompt_ref: "prompts.yaml#extract"
      model:
        provider: "openai"
        name: "gpt-4o"
      output_key: "person"

edges: []
params:
  text: ""
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch.object(slm_module, "litellm") as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content=json.dumps({"name": "Alice", "age": 30})))
                ]
                mock_litellm.completion.return_value = mock_response

                from yagra import Yagra
                from yagra.handlers import create_structured_llm_handler

                handler = create_structured_llm_handler(schema=PersonInfo, retry=1, timeout=10)
                registry = {"structured_llm": handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({"text": "Alice is 30 years old."})

            assert "person" in result
            assert isinstance(result["person"], PersonInfo)
            assert result["person"].name == "Alice"
            assert result["person"].age == 30

    def test_structured_handler_with_multiple_prompt_variables(self) -> None:
        """Multiple prompt variables should be auto-detected and processed correctly."""
        prompts_yaml = """\
extract_entities:
  system: "Extract entities as JSON"
  user: "Text: {text}, Context: {context}"
"""

        workflow_yaml = """\
version: "1.0"
start_at: "extract"
end_at:
  - "extract"

nodes:
  - id: "extract"
    handler: "structured_llm"
    params:
      prompt_ref: "prompts.yaml#extract_entities"
      model:
        provider: "openai"
        name: "gpt-4o"
      output_key: "entities"

edges: []
params:
  text: ""
  context: ""
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch.object(slm_module, "litellm") as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps({"names": ["Alice", "Bob"], "locations": ["Tokyo"]})
                        )
                    )
                ]
                mock_litellm.completion.return_value = mock_response

                from yagra import Yagra
                from yagra.handlers import create_structured_llm_handler

                handler = create_structured_llm_handler(
                    schema=ExtractedEntities, retry=1, timeout=10
                )
                registry = {"structured_llm": handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({"text": "Alice and Bob visited Tokyo.", "context": "travel"})

            assert "entities" in result
            assert isinstance(result["entities"], ExtractedEntities)
            assert "Alice" in result["entities"].names
            assert "Tokyo" in result["entities"].locations

            # Verify that both input values are embedded in the prompt
            call_messages = mock_litellm.completion.call_args.kwargs["messages"]
            user_content = call_messages[1]["content"]
            assert "Alice and Bob visited Tokyo." in user_content
            assert "travel" in user_content

    def test_structured_handler_with_model_kwargs(self) -> None:
        """model.kwargs should be passed correctly to the LLM."""
        prompts_yaml = """\
test:
  system: "Extract"
  user: "Extract person"
"""

        workflow_yaml = """\
version: "1.0"
start_at: "extract"
end_at:
  - "extract"

nodes:
  - id: "extract"
    handler: "structured_llm"
    params:
      prompt_ref: "prompts.yaml#test"
      model:
        provider: "openai"
        name: "gpt-4o"
        kwargs:
          temperature: 0.0
          max_tokens: 100
      output_key: "person"

edges: []
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch.object(slm_module, "litellm") as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content=json.dumps({"name": "Test", "age": 0})))
                ]
                mock_litellm.completion.return_value = mock_response

                from yagra import Yagra
                from yagra.handlers import create_structured_llm_handler

                handler = create_structured_llm_handler(schema=PersonInfo, retry=1, timeout=10)
                registry = {"structured_llm": handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                yagra.invoke({})

            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert call_kwargs["temperature"] == 0.0
            assert call_kwargs["max_tokens"] == 100
