"""LLM handler 層の共通例外階層.

``_llm_common.py`` が ``llm_handler.py`` の例外定義を import することで
発生していた循環依存を断つため、専用モジュールへ切り出している。

例外はすべて ``Exception`` 派生。judge handler の ``JudgeHandlerError``
のように構造化 payload を扱いたい場合、呼出元で ``payload`` 属性付き dict
を渡す運用を許容する（後方互換のため属性必須化はしない）。
"""

from __future__ import annotations

from typing import Any


class LLMHandlerError(Exception):
    """Base exception class for LLM handler execution errors.

    Supports two call styles for backward compatibility:

    - ``LLMHandlerError("message")`` — plain message (legacy path).
    - ``LLMHandlerError({"error": ..., "message": ..., ...})`` — structured
      4-field payload (``error`` / ``message`` / ``summary`` / ``hint``) for
      user-facing errors. The payload becomes accessible via the
      :attr:`payload` attribute.
    """

    def __init__(self, detail: Any = None) -> None:
        """Accept either a string message or a structured payload dict.

        Args:
            detail: Message string (legacy) or dict with structured fields.
        """
        super().__init__(detail)
        self.payload: dict[str, Any] | None = detail if isinstance(detail, dict) else None


class LLMHandlerConfigError(LLMHandlerError):
    """Configuration error for LLM handler."""


class LLMHandlerCallError(LLMHandlerError):
    """Error during LLM invocation."""


__all__ = [
    "LLMHandlerCallError",
    "LLMHandlerConfigError",
    "LLMHandlerError",
]
