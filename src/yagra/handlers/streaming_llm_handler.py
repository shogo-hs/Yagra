"""Streaming LLM handler using litellm.

This module provides an LLM handler that returns a streaming response
as a Generator, allowing callers to process chunks incrementally.
"""

from collections.abc import Generator
from typing import Any

import litellm

from yagra.ports.outbound.node_registry import NodeHandler


def create_streaming_llm_handler(
    retry: int = 3,
    timeout: int = 60,
) -> NodeHandler:
    """Creates a streaming LLM invocation handler.

    Generates a handler that calls an LLM via litellm with streaming enabled.
    The response is returned as a Generator yielding string chunks, allowing
    callers to process output incrementally or buffer it with ``"".join(...)``.

    Args:
        retry: Number of retries on API errors before streaming starts (default: 3).
        timeout: Timeout in seconds (default: 60, longer than non-streaming).

    Returns:
        NodeHandler: Handler function that takes (state, params) and returns a dict.
            The output_key value will be a ``Generator[str, None, None]``.

    Note:
        The returned Generator is single-use. Once consumed, it cannot be iterated again.

    Examples:
        Incremental processing:

        >>> handler = create_streaming_llm_handler(retry=3, timeout=60)
        >>> state = {"query": "Hello"}
        >>> params = {
        ...     "prompt": {"system": "You are a helpful assistant", "user": "{query}"},
        ...     "model": {"provider": "openai", "name": "gpt-4o"},
        ...     "output_key": "response",
        ... }
        >>> result = handler(state, params)
        >>> for chunk in result["response"]:
        ...     print(chunk, end="", flush=True)

        Buffered processing:

        >>> result = handler(state, params)
        >>> full_text = "".join(result["response"])

        YAML definition example:

        .. code-block:: yaml

            nodes:
              - id: "chat"
                handler: "streaming_llm"
                params:
                  prompt_ref: "prompts/chat.yaml#default"
                  model:
                    provider: "openai"
                    name: "gpt-4o"
                  output_key: "response"
    """

    def handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Invokes the LLM with streaming and returns a chunk generator.

        Calls the LLM via litellm with ``stream=True`` and wraps the response
        in a Generator that yields string chunks as they arrive.

        Args:
            state: Workflow state dictionary.
            params: Node parameters (prompt, model, output_key).

        Returns:
            dict: Response in the format ``{output_key: Generator[str, None, None]}``.
                The generator yields string chunks from the LLM response.

        Raises:
            LLMHandlerConfigError: If required parameters are missing or invalid.
            LLMHandlerCallError: If LLM invocation fails after all retries.
        """
        from yagra.handlers._llm_common import (
            build_messages,
            extract_llm_params,
            interpolate_prompt,
            llm_retry_loop,
            report_streaming_token_usage,
        )

        p = extract_llm_params(params, default_retry=retry)
        system_prompt, user_prompt = interpolate_prompt(
            p.system_prompt_template,
            p.user_prompt_template,
            state,
        )
        messages = build_messages(system_prompt, user_prompt)

        # Force stream=True unless explicitly overridden
        model_kwargs = dict(p.model_kwargs)
        if "stream" not in model_kwargs:
            model_kwargs["stream"] = True

        def _call() -> dict[str, Any]:
            response = litellm.completion(
                model=p.litellm_model,
                messages=messages,
                timeout=timeout,
                **model_kwargs,
            )

            _bound_model: str = p.litellm_model
            _bound_provider: str = p.provider

            def _stream(
                resp: Any,
                bound_model: str = _bound_model,
                bound_provider: str = _bound_provider,
            ) -> Generator[str, None, None]:
                """Yields string chunks from the LLM streaming response.

                Reports token usage to TraceContext after the stream is fully consumed.

                Args:
                    resp: Litellm streaming response object (iterable).
                    bound_model: litellm model string, bound at definition time.
                    bound_provider: Provider name, bound at definition time.

                Yields:
                    str: Non-empty content chunks from the LLM response.
                """
                for chunk in resp:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta is None:
                        continue
                    content = delta.content
                    if content is not None:
                        yield content
                report_streaming_token_usage(resp, bound_model, bound_provider)

            return {p.output_key: _stream(response)}

        return llm_retry_loop(_call, p.effective_retry)

    return handler


STREAMING_LLM_HANDLER_PARAMS_SCHEMA: dict = {
    "type": "object",
    "description": "Parameters for the streaming output handler created by create_streaming_llm_handler",
    "properties": {
        "prompt": {
            "oneOf": [
                {
                    "type": "string",
                    "description": "Prompt text. State values can be expanded using {variable_name}",
                },
                {"type": "object", "description": "Prompt dictionary in role/content format"},
                {"type": "array", "description": "List of multiple messages"},
            ],
            "description": "Prompt definition. Mutually exclusive with prompt_ref",
        },
        "prompt_ref": {
            "type": "string",
            "description": (
                "Path to the prompt file (relative to the workflow YAML). "
                "Use '#key' to select a section from a multi-prompt YAML "
                "(e.g. 'prompts/all.yaml#greet'). "
                "Nested keys use dot notation (e.g. 'prompts/all.yaml#chat.default'). "
                "Mutually exclusive with prompt"
            ),
            "examples": [
                "prompts/translate.yaml#default",
                "./prompts/summarize.md",
                "prompts/multi.yaml#chat.system",
            ],
        },
        "model": {
            "type": "object",
            "description": "LLM model configuration. provider and name are required. Additional parameters such as the stream flag can be passed via kwargs",
            "properties": {
                "provider": {"type": "string", "examples": ["openai", "anthropic"]},
                "name": {"type": "string", "examples": ["gpt-4o-mini", "claude-opus-4-6"]},
                "kwargs": {
                    "type": "object",
                    "description": "Additional litellm parameters such as the stream flag",
                },
            },
            "required": ["provider", "name"],
        },
        "output_key": {
            "type": "string",
            "description": "State key name to store the streaming output. Defaults to 'output'",
            "default": "output",
        },
        "stream": {
            "type": "boolean",
            "description": "Whether to enable streaming. If false, buffers the output and returns it all at once",
            "default": True,
        },
    },
    "required": ["model"],
    "oneOf": [
        {"required": ["prompt"]},
        {"required": ["prompt_ref"]},
    ],
}
