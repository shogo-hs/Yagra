"""Integration tests for streaming LLM handler with workflow execution.

ストリーミング LLM ハンドラーが YAML ワークフローと統合して正しく動作することを検証します。
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_chunk(content: str | None) -> MagicMock:
    """Creates a mock litellm streaming chunk."""
    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content=content))]
    return chunk


class TestStreamingLLMHandlerIntegration:
    """ストリーミング LLM ハンドラーの結合テスト."""

    def test_streaming_handler_with_prompt_ref(self) -> None:
        """prompt_ref を使ったストリーミング出力が正しく動作すること."""
        prompts_yaml = """\
chat:
  system: "You are a helpful assistant."
  user: "Answer: {query}"
"""

        workflow_yaml = """\
version: "1.0"
start_at: "chat"
end_at:
  - "chat"

nodes:
  - id: "chat"
    handler: "streaming_llm"
    params:
      prompt_ref: "prompts.yaml#chat"
      model:
        provider: "openai"
        name: "gpt-4o"
      input_keys: ["query"]
      output_key: "response"

edges: []
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch("yagra.handlers.streaming_llm_handler.litellm") as mock_litellm:
                chunks = [_make_chunk("Hello"), _make_chunk(" world"), _make_chunk("!")]
                mock_litellm.completion.return_value = iter(chunks)

                from yagra import Yagra
                from yagra.handlers import create_streaming_llm_handler

                handler = create_streaming_llm_handler(retry=1, timeout=10)
                registry = {"streaming_llm": handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({"query": "Say hello"})

            assert "response" in result
            full_text = "".join(result["response"])
            assert full_text == "Hello world!"

    def test_streaming_handler_chunks_joined(self) -> None:
        """チャンクを結合した文字列が期待値と一致すること."""
        prompts_yaml = """\
summarize:
  system: "Summarize the following."
  user: "{text}"
"""

        workflow_yaml = """\
version: "1.0"
start_at: "summarize"
end_at:
  - "summarize"

nodes:
  - id: "summarize"
    handler: "streaming_llm"
    params:
      prompt_ref: "prompts.yaml#summarize"
      model:
        provider: "anthropic"
        name: "claude-3-haiku-20240307"
      input_keys: ["text"]
      output_key: "summary"

edges: []
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch("yagra.handlers.streaming_llm_handler.litellm") as mock_litellm:
                chunks = [
                    _make_chunk("This"),
                    _make_chunk(" is"),
                    _make_chunk(None),  # None chunks should be skipped
                    _make_chunk(" a"),
                    _make_chunk(" summary."),
                ]
                mock_litellm.completion.return_value = iter(chunks)

                from yagra import Yagra
                from yagra.handlers import create_streaming_llm_handler

                handler = create_streaming_llm_handler(retry=1, timeout=10)
                registry = {"streaming_llm": handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({"text": "Some long text here."})

            assert "summary" in result
            full_text = "".join(result["summary"])
            assert full_text == "This is a summary."

    def test_streaming_handler_with_model_kwargs(self) -> None:
        """model.kwargs が正しく LLM に渡されること."""
        prompts_yaml = """\
test:
  system: "System prompt."
  user: "User prompt."
"""

        workflow_yaml = """\
version: "1.0"
start_at: "generate"
end_at:
  - "generate"

nodes:
  - id: "generate"
    handler: "streaming_llm"
    params:
      prompt_ref: "prompts.yaml#test"
      model:
        provider: "openai"
        name: "gpt-4o"
        kwargs:
          temperature: 0.7
          max_tokens: 200
      output_key: "result"

edges: []
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch("yagra.handlers.streaming_llm_handler.litellm") as mock_litellm:
                mock_litellm.completion.return_value = iter([_make_chunk("ok")])

                from yagra import Yagra
                from yagra.handlers import create_streaming_llm_handler

                handler = create_streaming_llm_handler(retry=1, timeout=10)
                registry = {"streaming_llm": handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({})
                list(result["result"])  # consume generator

            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 200
            assert call_kwargs["stream"] is True
