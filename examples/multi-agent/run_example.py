"""Multi-agent workflow example.

このサンプルは、複数の専門エージェントが協調してタスクを処理する
マルチエージェントパターンの例です。

フロー:
  orchestrator → researcher -[done]→ writer → finish
                            -[retry]→ researcher（再調査ループ）

構成:
  - orchestrator: タスクを分解して調査プランを作成する LLM エージェント
  - researcher: プランに従って情報収集するエージェント（再試行あり）
  - writer: 調査結果を整形して最終回答を作成するエージェント

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


def make_orchestrator_handler(llm_handler):  # type: ignore[no-untyped-def]
    """オーケストレーターハンドラーを作成する。

    Args:
        llm_handler: 基底となる LLM ハンドラー。

    Returns:
        オーケストレーター用のラッパーハンドラー。
    """

    def handler(state: dict) -> dict:  # type: ignore[type-arg]
        """LLM で調査プランを生成し、state に格納する。

        Args:
            state: 現在の状態。

        Returns:
            orchestrator_plan を追加した状態。
        """
        return llm_handler(state)

    return handler


def make_researcher_handler(llm_handler):  # type: ignore[no-untyped-def]
    """リサーチャーハンドラーを作成する。

    レスポンスの先頭行が "retry" または "done" であることを期待し、
    __next__ キーに値を書き込んでルーターへ伝える。

    Args:
        llm_handler: 基底となる LLM ハンドラー。

    Returns:
        リサーチャー用のラッパーハンドラー。
    """

    def handler(state: dict) -> dict:  # type: ignore[type-arg]
        """LLM で調査を実行し、retry/done を判定する。

        Args:
            state: 現在の状態。

        Returns:
            research_result と __next__ を追加した状態。
        """
        result = llm_handler(state)
        research_result: str = result.get("research_result", "")

        # 先頭行で retry/done を判定
        first_line = (
            research_result.strip().splitlines()[0].strip().lower() if research_result else "done"
        )
        if first_line == "retry":
            next_node = "retry"
        else:
            next_node = "done"

        return {**result, "__next__": next_node}

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
    """マルチエージェントワークフローのサンプル実行."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required")
        print("\nPlease set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

    llm_handler = create_llm_handler(retry=3, timeout=30)

    registry = {
        "llm": llm_handler,
        "orchestrator_handler": make_orchestrator_handler(llm_handler),
        "researcher_handler": make_researcher_handler(llm_handler),
        "finish_handler": make_finish_handler(),
    }

    workflow_path = Path(__file__).parent / "workflow.yaml"
    print(f"Loading workflow from: {workflow_path}")
    yagra = Yagra.from_workflow(workflow_path, registry)

    task = "Explain the key differences between LangGraph and traditional LLM chains"
    print(f"\nExecuting multi-agent workflow with task:\n  '{task}'\n")

    result = yagra.invoke({"task": task})

    print("=" * 60)
    print("Orchestrator Plan:")
    print("=" * 60)
    print(result.get("orchestrator_plan", "(none)"))
    print()
    print("=" * 60)
    print("Research Result:")
    print("=" * 60)
    print(result.get("research_result", "(none)"))
    print()
    print("=" * 60)
    print("Final Output:")
    print("=" * 60)
    print(result.get("final_output", "(none)"))
    print("=" * 60)


if __name__ == "__main__":
    main()
