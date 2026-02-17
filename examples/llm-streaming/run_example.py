"""Streaming LLM handler example.

このサンプルは create_streaming_llm_handler() を使って
LLM のレスポンスをストリーミングで受け取る方法を示します。

実行方法:
    OPENAI_API_KEY=<your-key> uv run python examples/llm-streaming/run_example.py
"""

import os
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from yagra import Yagra
from yagra.handlers import create_streaming_llm_handler

WORKFLOW_PATH = Path(__file__).parent / "workflow.yaml"


def main() -> None:
    """ストリーミング LLM ハンドラーのデモを実行します."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY が設定されていません。")
        print(
            "実行例: OPENAI_API_KEY=<your-key> uv run python examples/llm-streaming/run_example.py"
        )
        sys.exit(1)

    # ハンドラーを作成してレジストリに登録
    streaming_handler = create_streaming_llm_handler(retry=3, timeout=60)
    registry = {"streaming_llm": streaming_handler}

    # ワークフローを構築
    yagra = Yagra.from_workflow(WORKFLOW_PATH, registry)

    # ワークフローを実行
    query = "Python の非同期処理について100文字程度で説明してください。"
    print(f"Query: {query}")
    print("Response (streaming):")
    print("-" * 40)

    result = yagra.invoke({"query": query})

    # ストリーミングで逐次出力
    for chunk in result["response"]:
        print(chunk, end="", flush=True)

    print("\n" + "-" * 40)
    print("Done.")

    # バッファリングの例
    print("\n[バッファリング例]")
    result2 = yagra.invoke({"query": "Yagra を一言で説明してください。"})
    full_text = "".join(result2["response"])
    print(f"Full response: {full_text}")


if __name__ == "__main__":
    main()
