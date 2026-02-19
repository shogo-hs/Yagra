"""Streaming LLM handler using litellm.

This module provides an LLM handler that returns a streaming response
as a Generator, allowing callers to process chunks incrementally.
"""

import re
import time
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from yagra.handlers.llm_handler import LLMHandlerCallError, LLMHandlerConfigError
from yagra.ports.outbound.node_registry import NodeHandler

if TYPE_CHECKING:
    import litellm  # type: ignore[import-not-found]
else:
    litellm = None  # type: ignore[assignment]


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

    Raises:
        ImportError: If litellm is not installed.

    Note:
        The returned Generator is single-use. Once consumed, it cannot be iterated again.

    Examples:
        Incremental processing:

        >>> handler = create_streaming_llm_handler(retry=3, timeout=60)
        >>> state = {"query": "Hello"}
        >>> params = {
        ...     "prompt": {"system": "You are a helpful assistant", "user": "{query}"},
        ...     "model": {"provider": "openai", "name": "gpt-4o"},
        ...     "input_keys": ["query"],
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
                  input_keys: ["query"]
                  output_key: "response"
    """
    global litellm
    if litellm is None:
        try:
            import litellm
        except ImportError as e:
            msg = (
                "litellm is not installed. "
                "Install with: pip install 'yagra[llm]' or uv add --optional llm yagra"
            )
            raise ImportError(msg) from e

    def handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Invokes the LLM with streaming and returns a chunk generator.

        Calls the LLM via litellm with ``stream=True`` and wraps the response
        in a Generator that yields string chunks as they arrive.

        Args:
            state: Workflow state dictionary.
            params: Node parameters (prompt, model, input_keys, output_key).

        Returns:
            dict: Response in the format ``{output_key: Generator[str, None, None]}``.
                The generator yields string chunks from the LLM response.

        Raises:
            LLMHandlerConfigError: If required parameters are missing or invalid.
            LLMHandlerCallError: If LLM invocation fails after all retries.
        """
        # 1. Extract and validate parameters
        prompt = params.get("prompt")
        if not isinstance(prompt, dict):
            msg = "'prompt' must be a dict with 'system' and 'user' keys"
            raise LLMHandlerConfigError(msg)

        model = params.get("model")
        if not isinstance(model, dict):
            msg = "'model' must be a dict with 'provider', 'name', and optional 'kwargs'"
            raise LLMHandlerConfigError(msg)

        provider = model.get("provider")
        model_name = model.get("name")
        if not provider or not model_name:
            msg = "'model' must have 'provider' and 'name' keys"
            raise LLMHandlerConfigError(msg)

        output_key = params.get("output_key", "output")

        # 2. Interpolate variables into the prompt
        system_prompt = prompt.get("system", "")
        user_prompt_template = prompt.get("user", "")

        # If input_keys is explicitly specified, use it (backward compatibility);
        # otherwise auto-extract {variable} patterns from the prompt template
        explicit_keys = params.get("input_keys")
        keys = (
            explicit_keys
            if explicit_keys is not None
            else re.findall(r"\{(\w+)\}", user_prompt_template)
        )

        input_values = {key: state.get(key, "") for key in keys}

        try:
            user_prompt = user_prompt_template.format(**input_values)
        except KeyError as e:
            msg = f"Missing key in state for prompt interpolation: {e}"
            raise LLMHandlerConfigError(msg) from e

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 3. Retrieve model.kwargs (stream=True is added automatically; explicit False is not overridden)
        model_kwargs = dict(model.get("kwargs", {}))
        if "stream" not in model_kwargs:
            model_kwargs["stream"] = True

        litellm_model = f"{provider}/{model_name}"

        # 4. LLM invocation (with retry, until streaming starts)
        last_error = None
        for attempt in range(retry):
            try:
                response = litellm.completion(
                    model=litellm_model,
                    messages=messages,
                    timeout=timeout,
                    **model_kwargs,
                )

                # 5. Return a generator that yields chunks
                def _stream(
                    resp: Any,
                ) -> Generator[str, None, None]:
                    """Yields string chunks from the LLM streaming response.

                    Args:
                        resp: Litellm streaming response object (iterable).

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

                return {output_key: _stream(response)}

            except LLMHandlerCallError:
                raise
            except Exception as e:
                last_error = e
                if attempt < retry - 1:
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                    continue
                break

        msg = f"LLM call failed after {retry} attempts: {last_error}"
        raise LLMHandlerCallError(msg) from last_error

    return handler


STREAMING_LLM_HANDLER_PARAMS_SCHEMA: dict = {
    "type": "object",
    "description": "Parameters for the streaming output handler created by create_streaming_llm_handler",
    "properties": {
        "prompt": {
            "type": ["string", "object", "array"],
            "description": "Prompt definition. Mutually exclusive with prompt_ref",
        },
        "prompt_ref": {
            "type": "string",
            "description": "Path to the prompt file. Mutually exclusive with prompt",
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
        "input_keys": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Explicit state keys to pass to the prompt. Auto-extracted from {variable_name} in the prompt template if omitted",
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
