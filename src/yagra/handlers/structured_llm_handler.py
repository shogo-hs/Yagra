"""Structured output LLM handler using litellm and Pydantic.

This module provides an LLM handler that returns type-safe structured data
by parsing LLM responses with a Pydantic model.
"""

import json
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from yagra.handlers.llm_handler import LLMHandlerCallError, LLMHandlerConfigError
from yagra.ports.outbound.node_registry import NodeHandler

if TYPE_CHECKING:
    import litellm  # type: ignore[import-not-found]
else:
    litellm = None  # type: ignore[assignment]


def create_structured_llm_handler(
    schema: type[BaseModel],
    retry: int = 3,
    timeout: int = 30,
) -> NodeHandler:
    """Creates a structured output LLM handler with Pydantic model validation.

    Generates a handler that calls an LLM via litellm and parses the response
    into a Pydantic model instance. The LLM is instructed to return JSON,
    and the response is validated against the provided schema.

    Args:
        schema: Pydantic BaseModel subclass used to validate and parse the LLM response.
        retry: Number of retries on API errors (default: 3).
        timeout: Timeout in seconds (default: 30).

    Returns:
        NodeHandler: Handler function that takes (state, params) and returns a dict.
            The output_key value will be a Pydantic model instance.

    Raises:
        ImportError: If litellm is not installed.

    Examples:
        Basic usage:

        >>> from pydantic import BaseModel
        >>> class UserInfo(BaseModel):
        ...     name: str
        ...     age: int
        >>> handler = create_structured_llm_handler(schema=UserInfo, retry=3, timeout=30)
        >>> state = {"text": "My name is Alice and I am 30 years old."}
        >>> params = {
        ...     "prompt": {"system": "Extract user info as JSON", "user": "{text}"},
        ...     "model": {"provider": "openai", "name": "gpt-4o"},
        ...     "input_keys": ["text"],
        ...     "output_key": "user_info",
        ... }
        >>> result = handler(state, params)
        >>> print(result["user_info"])  # UserInfo(name='Alice', age=30)

        YAML definition example:

        .. code-block:: yaml

            nodes:
              - id: "extract"
                handler: "structured_llm"
                params:
                  prompt_ref: "prompts/extract.yaml#user_info"
                  model:
                    provider: "openai"
                    name: "gpt-4o"
                  input_keys: ["text"]
                  output_key: "user_info"
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
        """Invokes the LLM and returns a validated Pydantic model instance.

        Calls the LLM with JSON output mode and parses the response using
        the schema provided to create_structured_llm_handler.

        Args:
            state: Workflow state dictionary.
            params: Node parameters (prompt, model, input_keys, output_key).

        Returns:
            dict: Response in the format {output_key: schema_instance}.
                The value is a validated Pydantic model instance.

        Raises:
            LLMHandlerConfigError: If required parameters are missing or invalid.
            LLMHandlerCallError: If LLM invocation or JSON parsing/validation fails.
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

        # 3. JSON出力を促すシステムプロンプトを付加
        json_system_prompt = (
            f"{system_prompt}\n\nRespond with valid JSON only. "
            f"The JSON must conform to the following schema:\n"
            f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        ).strip()

        messages = [
            {"role": "system", "content": json_system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 4. model.kwargs の取得（response_format はデフォルトで json_object を付加）
        model_kwargs = dict(model.get("kwargs", {}))
        if "response_format" not in model_kwargs:
            model_kwargs["response_format"] = {"type": "json_object"}

        litellm_model = f"{provider}/{model_name}"

        # 5. LLM呼び出し（リトライ付き）
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

                # 6. JSONパース・Pydanticバリデーション
                try:
                    instance = schema.model_validate_json(content)
                except (ValidationError, ValueError) as e:
                    msg = f"Failed to parse LLM response as {schema.__name__}: {e}"
                    raise LLMHandlerCallError(msg) from e

                return {output_key: instance}

            except LLMHandlerCallError:
                # LLMレスポンスのエラーはリトライせず即座に送出
                raise
            except Exception as e:
                last_error = e
                if attempt < retry - 1:
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                    continue
                break

        # リトライ尽きた
        msg = f"LLM call failed after {retry} attempts: {last_error}"
        raise LLMHandlerCallError(msg) from last_error

    return handler
