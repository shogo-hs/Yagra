r"""YAML スキーマ定義から Pydantic BaseModel を動的に生成するユーティリティ。

WebUI の Schema Settings テキストエリアに入力された YAML を
Pydantic モデルに変換し、structured_llm ハンドラーで使用する。

YAML フォーマット例::

    name: str
    age: int
    score: float
    tags: list[str]

Examples:
    基本的な使用方法:

    >>> from yagra.handlers.schema_builder import build_model_from_schema_yaml
    >>> schema_yaml = "name: str\\nage: int"
    >>> Model = build_model_from_schema_yaml(schema_yaml)
    >>> instance = Model(name="Alice", age=30)
    >>> print(instance)
    name='Alice' age=30
"""

from typing import Any

import yaml
from pydantic import BaseModel, create_model

# 安全な型マッピング辞書。eval() を使用せず、
# ホワイトリスト方式で型文字列を Python 型に解決する。
TYPE_MAP: dict[str, Any] = {
    # プリミティブ型
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    # コレクション型
    "list[str]": list[str],
    "list[int]": list[int],
    "list[float]": list[float],
    "list[bool]": list[bool],
    # 辞書型
    "dict[str, str]": dict[str, str],
    "dict[str, int]": dict[str, int],
    "dict[str, Any]": dict[str, Any],
    # Optional 型
    "str | None": str | None,
    "int | None": int | None,
    "float | None": float | None,
    "bool | None": bool | None,
}


class SchemaYamlError(ValueError):
    """schema_yaml のパースまたはモデル生成に失敗した場合の例外。

    YAML 構文エラー、未サポートの型指定、不正なフォーマットなど、
    動的スキーマ生成に関連するすべてのエラーをこの例外で表現する。
    """


def build_model_from_schema_yaml(
    schema_yaml: str,
    model_name: str = "DynamicSchema",
) -> type[BaseModel]:
    r"""YAML 文字列から Pydantic BaseModel サブクラスを動的に生成する。

    フラットな ``key: type`` 形式の YAML を受け取り、各フィールドの型を
    安全な TYPE_MAP で解決して ``pydantic.create_model()`` でモデルを生成する。

    入力例::

        name: str
        age: int
        tags: list[str]
        nickname: str | None

    Args:
        schema_yaml: YAML 形式のスキーマ定義文字列（フラットな key: type 形式）。
        model_name: 生成するモデルのクラス名。デフォルトは ``"DynamicSchema"``。

    Returns:
        動的に生成された Pydantic BaseModel サブクラス。

    Raises:
        SchemaYamlError: YAML パースエラー、未サポート型、空フィールド、
            不正なフォーマットの場合に送出する。

    Examples:
        >>> Model = build_model_from_schema_yaml("name: str\\nage: int")
        >>> instance = Model.model_validate({"name": "Alice", "age": 30})
        >>> instance.name
        'Alice'
    """
    # 1. YAML パース
    try:
        parsed = yaml.safe_load(schema_yaml)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML syntax in schema_yaml: {e}"
        raise SchemaYamlError(msg) from e

    # 2. パース結果のバリデーション
    if not isinstance(parsed, dict):
        msg = "schema_yaml must be a YAML mapping of field_name: type (e.g. 'name: str')"
        raise SchemaYamlError(msg)

    if len(parsed) == 0:
        msg = "schema_yaml must define at least one field"
        raise SchemaYamlError(msg)

    # 3. 各フィールドの型解決と Pydantic フィールド定義の構築
    field_definitions: dict[str, Any] = {}
    supported_types = ", ".join(sorted(TYPE_MAP.keys()))

    for field_name, type_str in parsed.items():
        if not isinstance(field_name, str):
            msg = f"Field name must be a string, got {type(field_name).__name__}: {field_name}"
            raise SchemaYamlError(msg)

        if not isinstance(type_str, str):
            msg = (
                f"Type for field '{field_name}' must be a string, "
                f"got {type(type_str).__name__}: {type_str}"
            )
            raise SchemaYamlError(msg)

        type_str_normalized = type_str.strip()

        resolved_type = TYPE_MAP.get(type_str_normalized)
        if resolved_type is None:
            msg = (
                f"Unsupported type '{type_str_normalized}' for field '{field_name}'. "
                f"Supported types: {supported_types}"
            )
            raise SchemaYamlError(msg)

        # Optional 型の場合はデフォルト値を None に設定
        if "| None" in type_str_normalized:
            field_definitions[field_name] = (resolved_type, None)
        else:
            field_definitions[field_name] = (resolved_type, ...)

    # 4. pydantic.create_model() でモデル生成
    return create_model(model_name, **field_definitions)
