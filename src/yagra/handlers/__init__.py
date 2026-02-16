"""LLM handler utilities for Yagra workflows.

このモジュールは、LLMノードのボイラープレートコードを削減するための
ユーティリティ関数を提供します。

Examples:
    基本的なLLMハンドラーの作成と登録:

    >>> from yagra import Yagra
    >>> from yagra.handlers import create_llm_handler
    >>>
    >>> llm_handler = create_llm_handler(retry=3, timeout=30)
    >>> registry = {"llm": llm_handler}
    >>>
    >>> yagra = Yagra.from_workflow("workflow.yaml", registry)
    >>> result = yagra.invoke({"query": "Hello"})
"""

from yagra.handlers.llm_handler import create_llm_handler

__all__ = ["create_llm_handler"]
