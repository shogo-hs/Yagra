"""LLM handler implementation using litellm.

This module provides a generic LLM invocation handler using litellm.
It supports over 100 LLM providers through a unified API.
"""

import time
from typing import TYPE_CHECKING, Any

from yagra.ports.outbound.node_registry import NodeHandler

if TYPE_CHECKING:
    import litellm  # type: ignore[import-not-found]
else:
    litellm = None  # type: ignore[assignment]


class LLMHandlerError(Exception):
    """Base exception class for LLM handler execution errors."""

    pass


class LLMHandlerConfigError(LLMHandlerError):
    """Configuration error for LLM handler."""

    pass


class LLMHandlerCallError(LLMHandlerError):
    """Error during LLM invocation."""

    pass


def create_llm_handler(
    retry: int = 3,
    timeout: int = 30,
) -> NodeHandler:
    """Creates an LLM invocation handler.

    Generates a handler that supports over 100 LLM providers using litellm.
    Simply specify `prompt_ref`, `model`, `input_keys`, and `output_key` in the YAML
    definition to enable LLM invocation.

    Args:
        retry: Number of retries on API errors (default: 3).
        timeout: Timeout in seconds (default: 30).

    Returns:
        NodeHandler: Handler function that takes (state, params) and returns a dict.

    Raises:
        ImportError: If litellm is not installed.

    Examples:
        Basic usage:

        >>> handler = create_llm_handler(retry=3, timeout=30)
        >>> state = {"query": "Hello"}
        >>> params = {
        ...     "prompt": {"system": "You are a helpful assistant", "user": "{query}"},
        ...     "model": {"provider": "openai", "name": "gpt-4", "kwargs": {"temperature": 0.7}},
        ...     "input_keys": ["query"],
        ...     "output_key": "response",
        ... }
        >>> result = handler(state, params)
        >>> print(result["response"])  # LLM response

        YAML definition example:

        .. code-block:: yaml

            nodes:
              - id: "chat"
                handler: "llm"
                params:
                  prompt_ref: "prompts/chat.yaml#system"
                  model:
                    provider: "openai"
                    name: "gpt-4"
                    kwargs:
                      temperature: 0.7
                  input_keys: ["query"]
                  output_key: "response"
    """
    # litellmをimport（グローバル変数として保存）
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
        """Invokes the LLM and returns the response.

        Args:
            state: Workflow state dictionary.
            params: Node parameters (prompt, model, input_keys, output_key).

        Returns:
            dict: Response in the format {output_key: response_text}.

        Raises:
            LLMHandlerConfigError: If required parameters are missing.
            LLMHandlerCallError: If LLM invocation fails.
        """
        # 1. パラメータ抽出と検証
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

        input_keys = params.get("input_keys", [])
        output_key = params.get("output_key", "output")

        # 2. プロンプトに変数を埋め込み
        system_prompt = prompt.get("system", "")
        user_prompt_template = prompt.get("user", "")

        # stateから入力値を取得
        input_values = {key: state.get(key, "") for key in input_keys}

        # {variable}形式の変数を置換
        try:
            user_prompt = user_prompt_template.format(**input_values)
        except KeyError as e:
            msg = f"Missing key in state for prompt interpolation: {e}"
            raise LLMHandlerConfigError(msg) from e

        # 3. LLM呼び出し（リトライ付き）
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        model_kwargs = model.get("kwargs", {})
        litellm_model = f"{provider}/{model_name}"

        last_error = None
        for attempt in range(retry):
            try:
                response = litellm.completion(
                    model=litellm_model,
                    messages=messages,
                    timeout=timeout,
                    **model_kwargs,
                )

                # レスポンス抽出
                if not response.choices or len(response.choices) == 0:
                    msg = "LLM returned empty response"
                    raise LLMHandlerCallError(msg)

                content = response.choices[0].message.content
                if content is None:
                    msg = "LLM returned None content"
                    raise LLMHandlerCallError(msg)

                return {output_key: content}

            except LLMHandlerCallError:
                # LLMレスポンスのエラーはリトライせず即座に送出
                raise
            except Exception as e:
                last_error = e
                if attempt < retry - 1:
                    # 指数バックオフ
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                    continue
                break

        # リトライ尽きた
        msg = f"LLM call failed after {retry} attempts: {last_error}"
        raise LLMHandlerCallError(msg) from last_error

    return handler
