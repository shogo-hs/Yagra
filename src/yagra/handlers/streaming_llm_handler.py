"""Streaming LLM handler routed through :class:`LLMProviderPort`.

This module provides an LLM handler that returns a streaming response as a
:class:`~collections.abc.Generator` of ``str`` chunks. The streaming
provider contract internally uses ``LLMStreamChunk`` dataclass, but the
public API keeps the simpler ``Generator[str, None, None]`` shape so
existing callers and examples remain unchanged.
"""

from collections.abc import Generator, Iterator
from typing import Any

from yagra.ports.outbound.llm_provider import (
    LLMProviderPort,
    LLMStreamChunk,
    LLMTokenUsage,
)
from yagra.ports.outbound.node_registry import NodeHandler


def create_streaming_llm_handler(
    provider: LLMProviderPort | None = None,
    retry: int = 3,
    timeout: int = 60,
) -> NodeHandler:
    """Creates a streaming LLM invocation handler.

    Generates a handler that calls an LLM via litellm with streaming enabled.
    The response is returned as a Generator yielding string chunks, allowing
    callers to process output incrementally or buffer it with ``"".join(...)``.

    Args:
        provider: Explicit :class:`LLMProviderPort` instance. When ``None``,
            the handler resolves one from ``params["provider"]`` (default
            ``"litellm"``).
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
            extract_llm_params,
            interpolate_prompt,
            llm_retry_loop,
            report_streaming_usage,
            resolve_handler_provider,
        )

        p = extract_llm_params(params, default_retry=retry)
        system_prompt, user_prompt = interpolate_prompt(
            p.system_prompt_template,
            p.user_prompt_template,
            state,
        )

        resolved_provider = resolve_handler_provider(provider, params.get("provider"))

        def _call() -> dict[str, Any]:
            stream = resolved_provider.complete_streaming(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=p.litellm_model,
                timeout=timeout,
                **p.model_kwargs,
            )

            # Prime the stream so connection failures surface synchronously
            # and are retried by ``llm_retry_loop``. Without this, adapter
            # generators defer their internal ``try`` until the first
            # ``next()`` call, which would bypass the retry contract.
            iterator = iter(stream)
            primed: list[LLMStreamChunk] = []
            try:
                head = next(iterator)
            except StopIteration:
                head = None
            if head is not None:
                primed.append(head)

            def _stream_and_report(
                preloaded: list[LLMStreamChunk],
                tail: Iterator[LLMStreamChunk],
                bound_model: str = p.litellm_model,
                bound_provider: str = p.provider,
            ) -> Generator[str, None, None]:
                """Unwraps port-level chunks into a plain string generator.

                Accumulates the terminal :class:`LLMTokenUsage` if the
                provider emits one and reports it to TraceContext after the
                stream is exhausted. Reporting failures are silently ignored
                inside :func:`report_streaming_usage` so they never break the
                caller's iteration.

                Args:
                    preloaded: Chunks already consumed by the priming step.
                    tail: Remaining iterator of :class:`LLMStreamChunk`.
                    bound_model: litellm model string, bound at definition
                        time to keep the generator reentrant-safe.
                    bound_provider: Provider name, bound at definition time.

                Yields:
                    str: Non-empty delta strings from the LLM response.
                """
                last_usage: LLMTokenUsage | None = None
                import itertools as _itertools  # noqa: PLC0415

                for chunk in _itertools.chain(preloaded, tail):
                    if chunk.usage is not None:
                        last_usage = chunk.usage
                    if chunk.delta:
                        yield chunk.delta
                    if chunk.done:
                        break
                report_streaming_usage(last_usage, bound_model, bound_provider)

            return {p.output_key: _stream_and_report(primed, iterator)}

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
        "provider": {
            "type": "string",
            "description": (
                "LLMProviderPort adapter to route calls through. Defaults to 'litellm'. "
                "The Claude Agent SDK does not support streaming."
            ),
            "enum": ["litellm"],
            "default": "litellm",
        },
    },
    "required": ["model"],
    "oneOf": [
        {"required": ["prompt"]},
        {"required": ["prompt_ref"]},
    ],
}
