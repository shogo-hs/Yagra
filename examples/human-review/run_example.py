"""Human-in-the-Loop (HITL) workflow example.

このサンプルは、人間の確認・承認ステップを挟むワークフローパターンの例です。

フロー:
  generator -[interrupt_before publisher]→ [人間のレビュー] → publisher → finish

構成:
  - generator: コンテンツのドラフトを生成するエージェント
  - publisher: 人間の承認後にコンテンツを公開するエージェント
  - interrupt_before: publisher ノードの実行前に処理を中断
  - resume(): 人間のレビュー結果を注入して処理を再開

Requirements:
    - yagra[llm] がインストールされていること
    - OPENAI_API_KEY 環境変数が設定されていること
    - langgraph の checkpointer（MemorySaver 等）が必要

Usage:
    $ export OPENAI_API_KEY="your-api-key"
    $ python run_example.py
"""

import os
import sys
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from yagra import Yagra
from yagra.handlers import create_llm_handler


def make_generator_handler(llm_handler):  # type: ignore[no-untyped-def]
    """ジェネレーターハンドラーを作成する。

    Args:
        llm_handler: 基底となる LLM ハンドラー。

    Returns:
        ドラフトを生成するハンドラー。
    """

    def handler(state: dict) -> dict:  # type: ignore[type-arg]
        """LLM でドラフトコンテンツを生成する。

        Args:
            state: 現在の状態。

        Returns:
            draft を追加した状態。
        """
        return llm_handler(state)

    return handler


def make_publisher_handler(llm_handler):  # type: ignore[no-untyped-def]
    """パブリッシャーハンドラーを作成する。

    Args:
        llm_handler: 基底となる LLM ハンドラー。

    Returns:
        承認済みコンテンツを公開するハンドラー。
    """

    def handler(state: dict) -> dict:  # type: ignore[type-arg]
        """人間の承認後にコンテンツを公開する。

        Args:
            state: 現在の状態。approved / review_comment が含まれる。

        Returns:
            final_output を追加した状態。
        """
        return llm_handler(state)

    return handler


def main() -> None:
    """HITL ワークフローのサンプル実行."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required")
        print("\nPlease set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

    llm_handler = create_llm_handler(retry=3, timeout=30)

    registry = {
        "generator_handler": make_generator_handler(llm_handler),
        "publisher_handler": make_publisher_handler(llm_handler),
    }

    workflow_path = Path(__file__).parent / "workflow.yaml"
    print(f"Loading workflow from: {workflow_path}")

    # MemorySaver を checkpointer として使用（本番では PostgresSaver 等を使用）
    checkpointer = MemorySaver()
    yagra = Yagra.from_workflow(workflow_path, registry, checkpointer=checkpointer)

    task = "AIと機械学習の最新トレンドについての短い記事を書いてください"
    thread_id = "hitl-example-001"

    print("\nStep 1: ドラフト生成を開始します...")
    print(f"  タスク: {task}")
    print(f"  スレッドID: {thread_id}")

    # Step 1: invoke でドラフト生成 → publisher の前で中断
    result1 = yagra.invoke({"task": task}, thread_id=thread_id)

    print("\n" + "=" * 60)
    print("ドラフト生成完了（publisher ノードで中断）:")
    print("=" * 60)
    draft = result1.get("draft", "(none)")
    print(draft)

    # Step 2: 人間のレビュー（シミュレーション）
    print("\n" + "=" * 60)
    print("Step 2: 人間のレビュー（シミュレーション）")
    print("=" * 60)
    approved = True
    review_comment = "内容が良好です。公開を承認します。"
    print(f"  承認: {approved}")
    print(f"  コメント: {review_comment}")

    # Step 3: 承認結果を注入して resume
    print("\nStep 3: 承認結果を注入して再開...")
    result2 = yagra.resume(
        update={"approved": approved, "review_comment": review_comment},
        thread_id=thread_id,
    )

    print("\n" + "=" * 60)
    print("最終出力（公開済みコンテンツ）:")
    print("=" * 60)
    print(result2.get("output", "(none)"))
    print("=" * 60)


if __name__ == "__main__":
    main()
