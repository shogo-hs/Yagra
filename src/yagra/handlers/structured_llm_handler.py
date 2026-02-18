"""Structured output LLM handler using litellm and Pydantic.

This module provides an LLM handler that returns type-safe structured data
by parsing LLM responses with a Pydantic model.
"""

import json
import re
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from yagra.handlers.llm_handler import LLMHandlerCallError, LLMHandlerConfigError
from yagra.handlers.schema_builder import build_model_from_schema_yaml
from yagra.ports.outbound.node_registry import NodeHandler

if TYPE_CHECKING:
    import litellm  # type: ignore[import-not-found]
else:
    litellm = None  # type: ignore[assignment]


def create_structured_llm_handler(
    schema: type[BaseModel] | None = None,
    retry: int = 3,
    timeout: int = 30,
) -> NodeHandler:
    r"""Pydantic モデルバリデーション付きの構造化出力 LLM ハンドラーを生成する。

    litellm を介して LLM を呼び出し、レスポンスを Pydantic モデルインスタンスに
    パースするハンドラーを生成する。LLM には JSON で返却するよう指示し、
    指定されたスキーマでバリデーションを行う。

    スキーマの指定方法は 2 通り:

    1. **静的スキーマ**: ``schema`` 引数に Pydantic BaseModel サブクラスを渡す。
    2. **動的スキーマ**: ``schema`` を省略し、ワークフロー YAML の
       ``params.schema_yaml`` にフラットな ``key: type`` 形式で定義する。

    動的スキーマの YAML 例::

        name: str
        age: int
        tags: list[str]

    Args:
        schema: Pydantic BaseModel サブクラス。省略時は実行時に
            ``params["schema_yaml"]`` から動的にモデルを生成する。
        retry: API エラー時のリトライ回数（デフォルト: 3）。
        timeout: タイムアウト秒数（デフォルト: 30）。

    Returns:
        NodeHandler: (state, params) を受け取り dict を返すハンドラー関数。
            output_key の値は Pydantic モデルインスタンスになる。

    Raises:
        ImportError: litellm がインストールされていない場合。

    Examples:
        静的スキーマ指定:

        >>> from pydantic import BaseModel
        >>> class UserInfo(BaseModel):
        ...     name: str
        ...     age: int
        >>> handler = create_structured_llm_handler(schema=UserInfo, retry=3, timeout=30)

        動的スキーマ（schema_yaml を params で指定）:

        >>> handler = create_structured_llm_handler()  # schema=None
        >>> # params["schema_yaml"] = "name: str\\nage: int" で実行時に解決

        YAML 定義例:

        .. code-block:: yaml

            nodes:
              - id: "extract"
                handler: "structured_llm"
                params:
                  schema_yaml: |
                    name: str
                    age: int
                  prompt:
                    system: "Extract user info as JSON"
                    user: "{text}"
                  model:
                    provider: "openai"
                    name: "gpt-4o"
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
        """LLM を呼び出し、バリデーション済み Pydantic モデルインスタンスを返す。

        JSON 出力モードで LLM を呼び出し、create_structured_llm_handler に
        指定されたスキーマ、または params["schema_yaml"] から動的に生成した
        スキーマを使ってレスポンスをパースする。

        Args:
            state: ワークフロー state 辞書。
            params: ノードパラメータ（prompt, model, schema_yaml, output_key 等）。

        Returns:
            {output_key: schema_instance} 形式の辞書。
            値はバリデーション済み Pydantic モデルインスタンス。

        Raises:
            LLMHandlerConfigError: 必須パラメータが不足または不正な場合。
            LLMHandlerCallError: LLM 呼び出しまたは JSON パース/バリデーション失敗時。
            SchemaYamlError: schema_yaml のパースまたはモデル生成に失敗した場合。
        """
        # 0. スキーマ解決（静的 > 動的）
        resolved_schema: type[BaseModel]
        if schema is not None:
            resolved_schema = schema
        else:
            schema_yaml = params.get("schema_yaml")
            if not schema_yaml:
                msg = "Either 'schema' argument or 'schema_yaml' param is required"
                raise LLMHandlerConfigError(msg)
            resolved_schema = build_model_from_schema_yaml(schema_yaml)

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

        output_key = params.get("output_key", "output")

        # 2. プロンプトに変数を埋め込み
        system_prompt = prompt.get("system", "")
        user_prompt_template = prompt.get("user", "")

        # input_keys が明示指定されていればそちらを優先（後方互換）
        # 未指定（None）の場合はプロンプトテンプレートから {変数名} を自動抽出
        explicit_keys = params.get("input_keys")
        keys = (
            explicit_keys
            if explicit_keys is not None
            else re.findall(r"\{(\w+)\}", user_prompt_template)
        )

        # stateから入力値を取得
        input_values = {key: state.get(key, "") for key in keys}

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
            f"{json.dumps(resolved_schema.model_json_schema(), ensure_ascii=False)}"
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

                if not response.choices:
                    msg = "LLM returned empty response"
                    raise LLMHandlerCallError(msg)

                content = response.choices[0].message.content
                if content is None:
                    msg = "LLM returned None content"
                    raise LLMHandlerCallError(msg)

                # 6. JSONパース・Pydanticバリデーション
                try:
                    instance = resolved_schema.model_validate_json(content)
                except (ValidationError, ValueError) as e:
                    msg = f"Failed to parse LLM response as {resolved_schema.__name__}: {e}"
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

        msg = f"LLM call failed after {retry} attempts: {last_error}"
        raise LLMHandlerCallError(msg) from last_error

    return handler


STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA: dict = {
    "type": "object",
    "description": "create_structured_llm_handler で生成した Pydantic 構造化出力ハンドラーのパラメータ",
    "properties": {
        "prompt": {"$ref": "#/definitions/prompt_field"},
        "prompt_ref": {"$ref": "#/definitions/prompt_ref_field"},
        "model": {
            "type": "object",
            "description": "LLM モデル設定。provider と name が必須。kwargs に追加パラメータを渡せる",
            "properties": {
                "provider": {"type": "string", "examples": ["openai", "anthropic"]},
                "name": {"type": "string", "examples": ["gpt-4o-mini", "claude-opus-4-6"]},
                "kwargs": {"type": "object"},
            },
            "required": ["provider", "name"],
        },
        "input_keys": {
            "type": "array",
            "items": {"type": "string"},
            "description": "プロンプトに渡す state キーの明示指定。省略時はプロンプトテンプレートの {変数名} から自動抽出",
        },
        "output_key": {
            "type": "string",
            "description": "構造化出力を格納するステートキー名。省略時は 'output'",
            "default": "output",
        },
        "schema_yaml": {
            "type": "string",
            "description": "Pydantic モデルのフィールド定義。'フィールド名: 型' を改行区切りで記述。対応型: str, int, float, bool, list, dict",
            "examples": ["name: str\nage: int\ncity: str", "title: str\nsummary: str\ntags: list"],
        },
    },
    "required": ["model"],
    "oneOf": [
        {"required": ["prompt"]},
        {"required": ["prompt_ref"]},
    ],
}
