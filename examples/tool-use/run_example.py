"""Tool-use workflow example.

このサンプルは、LLM がツール呼び出しを判断して外部処理を経由するパターンの例です。

フロー:
  planner -[use_tool]→ tool_executor → synthesizer → finish
          -[direct]→   synthesizer   → finish

構成:
  - planner: ツール使用の要否を判断する LLM エージェント
  - tool_executor: ツールを実行するエージェント（このサンプルでは模擬実行）
  - synthesizer: ツール結果を統合して最終回答を作成するエージェント

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


def make_planner_handler(llm_handler):  # type: ignore[no-untyped-def]
    """プランナーハンドラーを作成する。

    レスポンスの先頭行が "use_tool" または "direct" で始まることを期待し、
    __next__ キーに値を書き込んでルーターへ伝える。

    Args:
        llm_handler: 基底となる LLM ハンドラー。

    Returns:
        プランナー用のラッパーハンドラー。
    """

    def handler(state: dict) -> dict:  # type: ignore[type-arg]
        """LLM でツール使用判断を行い、__next__ を設定する。

        Args:
            state: 現在の状態。

        Returns:
            tool_plan と __next__ を追加した状態。
        """
        result = llm_handler(state)
        tool_plan: str = result.get("tool_plan", "")

        first_line = tool_plan.strip().splitlines()[0].strip().lower() if tool_plan else "direct"
        if first_line == "use_tool":
            next_node = "use_tool"
        else:
            next_node = "direct"

        return {**result, "__next__": next_node}

    return handler


def make_tool_executor_handler():  # type: ignore[no-untyped-def]
    """ツール実行ハンドラーを作成する（モック実装）。

    実際のユースケースでは、この関数内で外部 API 呼び出しや
    データベースクエリなどを実行します。

    Returns:
        ツール実行用ハンドラー。
    """

    def handler(state: dict) -> dict:  # type: ignore[type-arg]
        """ツール実行を模擬し、tool_result を state に格納する。

        Args:
            state: 現在の状態。

        Returns:
            tool_result を追加した状態。
        """
        question = state.get("question", "")
        tool_plan = state.get("tool_plan", "")

        # モック: 実際のツール実行ではここで外部 API などを呼び出す
        mock_result = (
            f"[Mock Tool Result]\n"
            f"Question: {question}\n"
            f"Tool plan: {tool_plan}\n"
            f"Simulated tool execution completed. "
            f"In a real scenario, this would contain actual search results, "
            f"database records, or API responses."
        )

        return {**state, "tool_result": mock_result}

    return handler


def make_finish_handler():  # type: ignore[no-untyped-def]
    """フィニッシュハンドラーを作成する（何もしない）。

    Returns:
        状態をそのまま返すハンドラー。
    """

    def handler(state: dict) -> dict:  # type: ignore[type-arg]
        """状態をそのまま返す。

        Args:
            state: 現在の状態。

        Returns:
            変更なしの状態。
        """
        return state

    return handler


def main() -> None:
    """ツール使用ワークフローのサンプル実行."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required")
        print("\nPlease set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

    llm_handler = create_llm_handler(retry=3, timeout=30)

    registry = {
        "llm": llm_handler,
        "planner_handler": make_planner_handler(llm_handler),
        "tool_executor_handler": make_tool_executor_handler(),
        "finish_handler": make_finish_handler(),
    }

    workflow_path = Path(__file__).parent / "workflow.yaml"
    print(f"Loading workflow from: {workflow_path}")
    yagra = Yagra.from_workflow(workflow_path, registry)

    question = "What is the current population of Tokyo?"
    print(f"\nExecuting tool-use workflow with question:\n  '{question}'\n")

    result = yagra.invoke({"question": question})

    print("=" * 60)
    print("Planner Decision:")
    print("=" * 60)
    print(result.get("tool_plan", "(none)"))
    print()

    if result.get("tool_result"):
        print("=" * 60)
        print("Tool Result:")
        print("=" * 60)
        print(result.get("tool_result", "(none)"))
        print()

    print("=" * 60)
    print("Final Answer:")
    print("=" * 60)
    print(result.get("final_answer", "(none)"))
    print("=" * 60)


if __name__ == "__main__":
    main()
