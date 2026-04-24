"""Integration tests for LLM handler with workflow execution.

This test validates that the LLM handler works correctly when integrated with a YAML workflow.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestLLMHandlerIntegration:
    """Integration tests for the LLM handler."""

    def test_llm_handler_with_prompt_ref(self) -> None:
        """External prompt reference using prompt_ref should work correctly."""
        # Prompts YAML
        prompts_yaml = """
greeting:
  system: "You are a friendly assistant"
  user: "Hello {user_name}"
"""

        # Workflow YAML (correct schema format)
        workflow_yaml = """
version: "1.0"
start_at: "chat"
end_at:
  - "chat"

nodes:
  - id: "chat"
    handler: "llm"
    params:
      prompt_ref: "prompts.yaml#greeting"
      model:
        provider: "openai"
        name: "gpt-4"
      output_key: "response"

edges: []
params:
  user_name: ""
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch(
                "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
            ) as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="Hi Bob!"))]
                mock_litellm.completion.return_value = mock_response

                from yagra import Yagra
                from yagra.handlers import create_llm_handler

                llm_handler = create_llm_handler(retry=1, timeout=10)
                registry = {"llm": llm_handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({"user_name": "Bob"})

                assert "response" in result
                assert result["response"] == "Hi Bob!"

                # Verify that the prompt was loaded correctly
                call_args = mock_litellm.completion.call_args
                messages = call_args.kwargs["messages"]
                assert messages[0]["content"] == "You are a friendly assistant"
                assert messages[1]["content"] == "Hello Bob"

    def test_llm_handler_with_model_kwargs(self) -> None:
        """model.kwargs should be passed correctly to the LLM."""
        # Prompts YAML
        prompts_yaml = """
test:
  system: "Assistant"
  user: "Test"
"""

        # Workflow YAML
        workflow_yaml = """
version: "1.0"
start_at: "chat"
end_at:
  - "chat"

nodes:
  - id: "chat"
    handler: "llm"
    params:
      prompt_ref: "prompts.yaml#test"
      model:
        provider: "openai"
        name: "gpt-4"
        kwargs:
          temperature: 0.5
          max_tokens: 100
      output_key: "response"

edges: []
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch(
                "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
            ) as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="Response"))]
                mock_litellm.completion.return_value = mock_response

                from yagra import Yagra
                from yagra.handlers import create_llm_handler

                llm_handler = create_llm_handler(retry=1, timeout=10)
                registry = {"llm": llm_handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({})

                assert result["response"] == "Response"

                # Verify that model.kwargs was passed correctly
                call_args = mock_litellm.completion.call_args
                assert call_args.kwargs["temperature"] == 0.5
                assert call_args.kwargs["max_tokens"] == 100

    def test_llm_handler_with_multiple_prompt_variables(self) -> None:
        """Multiple prompt variables should be auto-detected and processed correctly."""
        # Prompts YAML
        prompts_yaml = """
multi_input:
  system: "Assistant"
  user: "Name: {name}, Age: {age}, City: {city}"
"""

        # Workflow YAML
        workflow_yaml = """
version: "1.0"
start_at: "chat"
end_at:
  - "chat"

nodes:
  - id: "chat"
    handler: "llm"
    params:
      prompt_ref: "prompts.yaml#multi_input"
      model:
        provider: "openai"
        name: "gpt-4"
      output_key: "response"

edges: []
params:
  name: ""
  age: ""
  city: ""
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch(
                "yagra.adapters.outbound.llm_providers.litellm_provider.litellm"
            ) as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="OK"))]
                mock_litellm.completion.return_value = mock_response

                from yagra import Yagra
                from yagra.handlers import create_llm_handler

                llm_handler = create_llm_handler(retry=1, timeout=10)
                registry = {"llm": llm_handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({"name": "Alice", "age": 30, "city": "Tokyo"})

                assert result["response"] == "OK"

                # Verify that the prompt was interpolated correctly
                call_args = mock_litellm.completion.call_args
                messages = call_args.kwargs["messages"]
                assert messages[1]["content"] == "Name: Alice, Age: 30, City: Tokyo"
