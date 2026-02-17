"""Structured output LLM handler example.

このサンプルは、Yagra の構造化出力 LLM ハンドラーを使った例です。
Pydantic モデルを指定することで、LLM のレスポンスを型安全な構造化データとして受け取れます。

Requirements:
    - yagra[llm] がインストールされていること
    - OPENAI_API_KEY 環境変数が設定されていること

Usage:
    $ export OPENAI_API_KEY="your-api-key"
    $ python run_example.py
"""

import os
import sys
from pathlib import Path

from pydantic import BaseModel

from yagra import Yagra
from yagra.handlers import create_structured_llm_handler


class PersonInfo(BaseModel):
    """抽出する人物情報のスキーマ."""

    name: str
    age: int


def main() -> None:
    """構造化出力 LLM ハンドラーのサンプル実行."""
    # OpenAI API key のバリデーション
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required")
        print("\nPlease set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

    # 構造化出力ハンドラーの作成（Pydantic モデルを指定）
    print(f"Creating structured LLM handler with schema: {PersonInfo.__name__}")
    structured_handler = create_structured_llm_handler(
        schema=PersonInfo,
        retry=3,
        timeout=30,
    )

    # Registry に登録
    registry = {"structured_llm": structured_handler}

    # Workflow から Yagra インスタンスを作成
    workflow_path = Path(__file__).parent / "workflow.yaml"
    print(f"Loading workflow from: {workflow_path}")
    yagra = Yagra.from_workflow(workflow_path, registry)

    # 実行
    input_text = "My name is Alice and I am 30 years old."
    print(f"\nExecuting workflow with input text: '{input_text}'")
    result = yagra.invoke({"text": input_text})

    # 結果表示
    print("\n" + "=" * 60)
    print("Structured Output Result:")
    print("=" * 60)
    person: PersonInfo = result["person"]
    print(f"Type   : {type(person).__name__}")
    print(f"Name   : {person.name}")
    print(f"Age    : {person.age}")
    print("=" * 60)

    # 型安全性の確認
    print("\n[Type Safety]")
    print(f"  person.name is str : {isinstance(person.name, str)}")
    print(f"  person.age is int  : {isinstance(person.age, int)}")


if __name__ == "__main__":
    main()
