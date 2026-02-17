"""LLM handler basic example.

このサンプルは、Yagra の LLM ハンドラーユーティリティを使った最も基本的な例です。
YAML 定義だけで LLM ノードを実行できることを示します。

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

from yagra import Yagra
from yagra.handlers import create_llm_handler


def main() -> None:
    """LLM handler のサンプル実行."""
    # OpenAI API key のバリデーション
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required")
        print("\nPlease set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

    # LLM handler の作成
    print("Creating LLM handler...")
    llm_handler = create_llm_handler(retry=3, timeout=30)

    # Registry に登録
    registry = {"llm": llm_handler}

    # Workflow から Yagra インスタンスを作成
    workflow_path = Path(__file__).parent / "workflow.yaml"
    print(f"Loading workflow from: {workflow_path}")
    yagra = Yagra.from_workflow(workflow_path, registry)

    # 実行
    print("\nExecuting workflow with input: {'user_name': 'Alice'}")
    result = yagra.invoke({"user_name": "Alice"})

    # 結果表示
    print("\n" + "=" * 60)
    print("Response:")
    print("=" * 60)
    print(result["response"])
    print("=" * 60)


if __name__ == "__main__":
    main()
