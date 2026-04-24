"""LLM handler utilities for Yagra workflows.

This module provides utility functions for reducing boilerplate code
in LLM nodes.

Examples:
    Creating and registering a basic LLM handler:

    >>> from yagra import Yagra
    >>> from yagra.handlers import create_llm_handler
    >>>
    >>> llm_handler = create_llm_handler(retry=3, timeout=30)
    >>> registry = {"llm": llm_handler}
    >>>
    >>> yagra = Yagra.from_workflow("workflow.yaml", registry)
    >>> result = yagra.invoke({"query": "Hello"})

    Creating and registering a structured output handler:

    >>> from pydantic import BaseModel
    >>> from yagra.handlers import create_structured_llm_handler
    >>>
    >>> class UserInfo(BaseModel):
    ...     name: str
    ...     age: int
    >>>
    >>> handler = create_structured_llm_handler(schema=UserInfo)
    >>> registry = {"structured_llm": handler}

    Creating and registering a streaming handler:

    >>> from yagra.handlers import create_streaming_llm_handler
    >>>
    >>> handler = create_streaming_llm_handler(retry=3, timeout=60)
    >>> registry = {"streaming_llm": handler}
    >>>
    >>> yagra = Yagra.from_workflow("workflow.yaml", registry)
    >>> result = yagra.invoke({"query": "Hello"})
    >>> for chunk in result["response"]:
    ...     print(chunk, end="", flush=True)
"""

from yagra.handlers.catalog import BUILTIN_HANDLERS_INFO
from yagra.handlers.judge import (
    JUDGE_HANDLER_PARAMS_SCHEMA,
    JudgeHandlerCallError,
    JudgeHandlerConfigError,
    JudgeHandlerError,
    create_judge_handler,
)
from yagra.handlers.llm_handler import LLM_HANDLER_PARAMS_SCHEMA, create_llm_handler
from yagra.handlers.schema_builder import build_model_from_schema_yaml
from yagra.handlers.streaming_llm_handler import (
    STREAMING_LLM_HANDLER_PARAMS_SCHEMA,
    create_streaming_llm_handler,
)
from yagra.handlers.structured_llm_handler import (
    STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA,
    create_structured_llm_handler,
)

__all__ = [
    "BUILTIN_HANDLERS_INFO",
    "JUDGE_HANDLER_PARAMS_SCHEMA",
    "LLM_HANDLER_PARAMS_SCHEMA",
    "STREAMING_LLM_HANDLER_PARAMS_SCHEMA",
    "STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA",
    "JudgeHandlerCallError",
    "JudgeHandlerConfigError",
    "JudgeHandlerError",
    "build_model_from_schema_yaml",
    "create_judge_handler",
    "create_llm_handler",
    "create_streaming_llm_handler",
    "create_structured_llm_handler",
]
