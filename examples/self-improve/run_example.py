"""Self-Improve Walking Example.

Yagra の差別化軸「AI が AI を評価」を体感するサンプル。

2 ノードのワークフローで構成されており、`generate` ノードが LLM で文章を生成し、
続く `judge` ノードが LLM-as-a-Judge として出力を宣言的 rubric で評価する。
最終 state には draft 本文と `judge_result`（スコア・根拠・per-criterion の rubric_items）が格納される。

Requirements:
    - ``uv add "yagra[llm,judge]"`` がインストールされていること
    - ``OPENAI_API_KEY`` 環境変数が設定されていること（generate ノード用、LiteLLM 経由）
    - ``claude login`` 済みであること（judge ノード用、Claude Agent SDK の subscription 認証）

Usage:
    $ export OPENAI_API_KEY="your-openai-key"
    $ claude login     # 未実行の場合
    $ python run_example.py
"""

import os
import sys
from pathlib import Path

from yagra import Yagra
from yagra.handlers import (
    JudgeHandlerError,
    create_judge_handler,
    create_llm_handler,
)


def main() -> None:
    """Self-Improve walking example の実行本体."""
    # OPENAI_API_KEY のバリデーション（generate ノード用、LiteLLM 経由）
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required")
        print("\nPlease set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key'")
        print(
            "\nNote: The judge node uses claude_agent_sdk with Claude subscription auth "
            "(no API key required, just `claude login`)."
        )
        sys.exit(1)

    # ハンドラーの作成
    print("Creating LLM handler (generate node, LiteLLM / openai gpt-4o-mini)...")
    llm_handler = create_llm_handler(retry=3, timeout=30)

    print("Creating Judge handler (judge node, claude_agent_sdk / sonnet)...")
    judge_handler = create_judge_handler(retry=3, timeout=60)

    # Registry に登録
    registry = {
        "llm": llm_handler,
        "judge": judge_handler,
    }

    # Workflow から Yagra インスタンスを作成
    workflow_path = Path(__file__).parent / "workflow.yaml"
    print(f"Loading workflow from: {workflow_path}")
    app = Yagra.from_workflow(workflow_path, registry)

    # 実行
    inputs = {"topic": "Hexagonal Architecture", "length": 3}
    print(f"\nExecuting workflow with input: {inputs}")

    try:
        result = app.invoke(inputs)
    except JudgeHandlerError as exc:
        # 4-field structured error (error, message, summary, hint) を整形表示
        print("\n[Judge handler error]")
        payload = exc.payload
        print(f"  error  : {payload.get('error')}")
        print(f"  message: {payload.get('message')}")
        print(f"  summary: {payload.get('summary')}")
        print(f"  hint   : {payload.get('hint')}")
        print(
            "\nMost common causes: claude_agent_sdk not installed "
            "(uv add 'yagra[judge]'), or `claude login` not executed."
        )
        sys.exit(1)

    # ---- 結果表示 ----
    # 1. draft（generate ノードの出力）
    print("\n" + "=" * 60)
    print("Draft (generate node, gpt-4o-mini)")
    print("=" * 60)
    print(result.get("draft", "<no draft>"))

    # 2. judge_result（judge ノードの出力）
    judge_result = result.get("judge_result") or {}
    score = judge_result.get("score") or {}
    reasoning = judge_result.get("reasoning", "<no reasoning>")
    rubric_items = judge_result.get("rubric_items") or []

    print("\n" + "=" * 60)
    print("Judge Result (judge node, claude_agent_sdk / sonnet)")
    print("=" * 60)
    # _overall を強調（差別化軸「AI が AI を評価」の体感ポイント）
    overall = score.get("_overall")
    if overall is not None:
        print(f"  >>> Overall score: {overall:.2f}  <<<")
    else:
        print("  >>> Overall score: (unavailable)  <<<")
    # per-criterion score（_overall を除く）
    print("\n  Per-criterion scores:")
    for name, value in score.items():
        if name == "_overall":
            continue
        print(f"    - {name}: {value}")
    print(f"\n  Reasoning: {reasoning}")
    # rubric_items（per-criterion の詳細理由）
    if rubric_items:
        print("\n  Rubric items:")
        for item in rubric_items:
            name = item.get("name", "<unknown>")
            item_score = item.get("score", "?")
            item_reasoning = item.get("reasoning", "")
            print(f"    - {name} ({item_score}): {item_reasoning}")
    print("=" * 60)


if __name__ == "__main__":
    main()
