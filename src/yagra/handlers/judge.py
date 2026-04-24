"""LLM-as-a-Judge handler implementation.

Implements ``create_judge_handler``: a factory returning a workflow node
handler that evaluates arbitrary inputs against a declarative rubric using
any :class:`~yagra.ports.outbound.llm_provider.LLMProviderPort` adapter.

Design highlights:

- **Hexagonal-friendly**: the handler depends only on the port contract, so
  callers can inject a custom provider (e.g. for testing) or delegate to
  :func:`~yagra.adapters.outbound.llm_providers.resolve_provider` based on
  the ``provider`` string in workflow YAML params.
- **Silent-success prevention**: missing rubric criteria or missing output
  fields raise structured 4-field errors (#4 learnings) rather than
  producing a placeholder score.
- **Default provider**: ``claude_agent_sdk`` with model ``sonnet`` (no API
  key required; uses the logged-in Claude subscription).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from yagra.handlers._llm_common import interpolate_prompt
from yagra.ports.outbound.llm_provider import (
    LLMProviderCallError,
    LLMProviderConfigError,
    LLMProviderError,
    LLMProviderPort,
)
from yagra.ports.outbound.node_registry import NodeHandler


class JudgeHandlerError(Exception):
    """Base exception for judge handler failures.

    Errors carry a 4-field structured payload so both humans and agents can
    react predictably:

    ``{"error": <code>, "message": <human>, "summary": <context>, "hint": <remediation>}``
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        """Initializes with a structured payload.

        Args:
            payload: 4-field structured error dictionary.
        """
        super().__init__(payload)
        self.payload = payload


class JudgeHandlerConfigError(JudgeHandlerError):
    """Configuration-level judge handler error (rubric / params invalid)."""


class JudgeHandlerCallError(JudgeHandlerError):
    """Runtime judge handler error (provider failure / invalid output)."""


_DEFAULT_PROVIDER_NAME = "claude_agent_sdk"
_DEFAULT_MODEL = "sonnet"
_DEFAULT_OUTPUT_KEY = "judge_result"


def create_judge_handler(
    provider: LLMProviderPort | None = None,
    retry: int = 3,
    timeout: int = 30,
) -> NodeHandler:
    r"""Creates an LLM-as-a-Judge node handler.

    Accepts either a pre-built :class:`LLMProviderPort` instance (handy for
    tests and dependency injection) or falls back to resolving one from the
    ``provider`` string declared in workflow params. Either way, the handler
    interpolates the prompt against the node state, converts the rubric to
    a JSON Schema, asks the provider to return structured JSON, and
    validates the result before writing it to ``state[output_key]``.

    Args:
        provider: Explicit provider instance. When ``None``, the handler
            resolves one from ``params["provider"]`` (default
            ``"claude_agent_sdk"``).
        retry: Retry count for transient provider errors (default 3).
        timeout: Per-call timeout in seconds (default 30).

    Returns:
        NodeHandler that takes ``(state, params)`` and returns
        ``{output_key: {"score": ..., "reasoning": ..., "rubric_items": [...]}}``.

    Examples:
        YAML definition:

        .. code-block:: yaml

            nodes:
              - id: "judge"
                handler: "judge"
                params:
                  provider: "claude_agent_sdk"
                  model: "sonnet"
                  rubric_ref: "rubrics/quality.yaml#default"
                  prompt_ref: "prompts/judge.yaml#judge"
                  output_key: "judge_result"

        Python (dependency injection):

        >>> from yagra.handlers import create_judge_handler
        >>> my_provider = ...  # implements LLMProviderPort
        >>> handler = create_judge_handler(provider=my_provider)

    Prompt Resolution Pitfalls:
        Two specifications frequently trip up first-time users. Both are
        intentional but under-documented elsewhere:

        1. **Default user template is ``"{query}"``**. When ``prompt_ref`` /
           ``prompt`` is omitted, the handler substitutes ``state["query"]``
           into the user prompt. If the upstream node writes its output to a
           different key (e.g. ``output_key: "draft"`` on a generate node),
           the judge will see an empty / literal ``"{query}"`` prompt and
           score against nothing. Either (a) name the upstream output key
           ``query``, or (b) supply an explicit ``prompt_ref`` whose user
           template interpolates the actual state key
           (e.g. ``"Evaluate the following draft:\\n\\n{draft}"``). The default
           system prompt *is* auto-generated from the rubric, so only the user
           template needs attention in the common case.

        2. **Inline ``prompt:`` in workflow YAML is rejected by the validator**.
           The handler code itself accepts ``params["prompt"] = {"system":
           ..., "user": ...}`` (see the runtime branch above), but
           :mod:`yagra.application.services.reference_resolver` blocks inline
           prompts at load time with the error ``"inline prompt is no longer
           supported; use prompt_ref to reference an external prompt file"``.
           In workflow YAML, always use ``prompt_ref: "<file>#<key>"`` and
           define the template in an external prompts YAML (typical naming:
           ``prompts.yaml`` with a ``judge:`` section). The inline form only
           works when a handler is invoked programmatically outside the
           workflow loader.
    """

    def handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Executes the judge evaluation for a single workflow node invocation.

        Args:
            state: Workflow state dictionary.
            params: Node parameters (``rubric`` or ``rubric_ref``, optional
                ``prompt``/``prompt_ref``, ``model``, ``provider``,
                ``output_key``).

        Returns:
            ``{output_key: {"score": {...}, "reasoning": str, "rubric_items": [...]}}``.

        Raises:
            JudgeHandlerConfigError: Rubric missing, empty, or malformed.
            JudgeHandlerCallError: Provider invocation fails or returns an
                output that does not contain the required fields.
        """
        rubric_dict = _resolve_rubric(params)
        _validate_rubric(rubric_dict)

        schema = _rubric_to_json_schema(rubric_dict)

        resolved_provider = _resolve_provider_instance(provider, params.get("provider"))

        prompt = params.get("prompt") or {}
        if not isinstance(prompt, dict):
            raise JudgeHandlerConfigError(
                {
                    "error": "invalid_prompt",
                    "message": "'prompt' must be a dict with 'system' and 'user' keys",
                    "summary": {"type": type(prompt).__name__},
                    "hint": "Pass prompt as {'system': ..., 'user': ...} or use prompt_ref",
                }
            )
        system_template = prompt.get("system") or _default_system_prompt(rubric_dict)
        user_template = prompt.get("user") or "{query}"
        system_prompt, user_prompt = interpolate_prompt(
            system_template,
            user_template,
            state,
        )

        model = params.get("model") or _DEFAULT_MODEL

        def _call() -> dict[str, Any]:
            return resolved_provider.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                model=model,
                timeout=timeout,
            )

        raw_result = _judge_retry_loop(_call, retry, resolved_provider)
        validated = _validate_judge_output(raw_result, rubric_dict)

        output_key = params.get("output_key", _DEFAULT_OUTPUT_KEY)
        return {output_key: validated}

    return handler


def _judge_retry_loop(
    fn: Callable[[], dict[str, Any]],
    retry: int,
    provider: LLMProviderPort,
) -> dict[str, Any]:
    """Calls ``fn`` with retry/backoff, converting provider errors at the boundary.

    Unlike :func:`yagra.handlers._llm_common.llm_retry_loop`, this loop
    translates :class:`LLMProviderCallError` / :class:`LLMProviderConfigError`
    into the judge-specific structured exceptions. Config errors are NOT
    retried since they are deterministic (e.g. missing SDK).

    Args:
        fn: Callable returning the provider response dict.
        retry: Number of attempts (minimum 1).
        provider: Provider instance (used for error payload metadata).

    Returns:
        Provider response dict.

    Raises:
        JudgeHandlerConfigError: If the provider reports a config error.
        JudgeHandlerCallError: If all retries are exhausted or the provider
            raises an unexpected error.
    """
    attempts = max(retry, 1)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except LLMProviderConfigError as exc:
            payload = (
                exc.args[0]
                if exc.args and isinstance(exc.args[0], dict)
                else {
                    "error": "provider_config_error",
                    "message": str(exc),
                    "summary": {},
                    "hint": "Inspect provider initialization",
                }
            )
            raise JudgeHandlerConfigError(payload) from exc
        except LLMProviderCallError as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(2**attempt)
                continue
            break
        except LLMProviderError as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(2**attempt)
                continue
            break

    raise JudgeHandlerCallError(
        {
            "error": "provider_call_failed",
            "message": f"Provider call failed after {attempts} attempt(s): {last_error}",
            "summary": {"provider": type(provider).__name__, "attempts": attempts},
            "hint": ("Verify provider credentials / network; see logs for the underlying cause"),
        }
    ) from last_error


def _resolve_provider_instance(
    provider_arg: LLMProviderPort | None,
    params_provider: Any,
) -> LLMProviderPort:
    """Resolves the provider instance following the hybrid pattern.

    1. If ``provider_arg`` is a port instance, use it as-is (DI / test).
    2. Else take ``params_provider`` string or default to
       ``claude_agent_sdk`` and delegate to :func:`resolve_provider`.

    Args:
        provider_arg: Explicit port instance or ``None``.
        params_provider: Provider name from workflow YAML params.

    Returns:
        A concrete :class:`LLMProviderPort` implementation.

    Raises:
        JudgeHandlerConfigError: If ``params_provider`` is not a string or
            resolves to an unknown provider name.
    """
    if provider_arg is not None:
        if not isinstance(provider_arg, LLMProviderPort):
            raise JudgeHandlerConfigError(
                {
                    "error": "invalid_provider_instance",
                    "message": ("provider argument does not implement LLMProviderPort"),
                    "summary": {"type": type(provider_arg).__name__},
                    "hint": "Pass an LLMProviderPort implementation or omit the argument",
                }
            )
        return provider_arg

    if params_provider is None:
        name = _DEFAULT_PROVIDER_NAME
    elif isinstance(params_provider, str):
        name = params_provider
    else:
        raise JudgeHandlerConfigError(
            {
                "error": "invalid_provider_param",
                "message": "'provider' param must be a string",
                "summary": {"type": type(params_provider).__name__},
                "hint": "Set params.provider to 'claude_agent_sdk' or 'litellm'",
            }
        )

    # Lazy import keeps adapter modules out of the import graph until actually needed.
    from yagra.adapters.outbound.llm_providers import resolve_provider

    try:
        return resolve_provider(name)
    except ValueError as exc:
        raise JudgeHandlerConfigError(
            {
                "error": "unknown_provider",
                "message": str(exc),
                "summary": {"provider": name},
                "hint": "Use 'claude_agent_sdk' or 'litellm'",
            }
        ) from exc


def _resolve_rubric(params: dict[str, Any]) -> dict[str, Any]:
    """Resolves the rubric from either ``rubric`` (inline) or ``rubric_ref``.

    Args:
        params: Node params dict.

    Returns:
        Rubric as a dict.

    Raises:
        JudgeHandlerConfigError: If neither ``rubric`` nor ``rubric_ref`` is
            provided, both are provided, or the referenced file cannot be
            loaded.
    """
    inline = params.get("rubric")
    ref = params.get("rubric_ref")

    if inline is not None and ref is not None:
        raise JudgeHandlerConfigError(
            {
                "error": "rubric_conflict",
                "message": "specify either 'rubric' (inline) or 'rubric_ref', not both",
                "summary": {},
                "hint": "Remove one of the two to disambiguate",
            }
        )

    if inline is not None:
        if not isinstance(inline, dict):
            raise JudgeHandlerConfigError(
                {
                    "error": "invalid_rubric_type",
                    "message": "'rubric' must be a mapping (dict)",
                    "summary": {"type": type(inline).__name__},
                    "hint": "Provide rubric as a YAML mapping with 'criteria' key",
                }
            )
        return deepcopy(inline)

    if ref is not None:
        if not isinstance(ref, str):
            raise JudgeHandlerConfigError(
                {
                    "error": "invalid_rubric_ref",
                    "message": "'rubric_ref' must be a string",
                    "summary": {"type": type(ref).__name__},
                    "hint": "Use a path string like 'rubrics/quality.yaml#default'",
                }
            )
        return _load_rubric_from_ref(ref, params)

    raise JudgeHandlerConfigError(
        {
            "error": "rubric_missing",
            "message": "either 'rubric' (inline) or 'rubric_ref' (file) is required",
            "summary": {},
            "hint": "Add params.rubric_ref: 'rubrics/<file>.yaml#<key>' or inline rubric",
        }
    )


def _load_rubric_from_ref(ref: str, params: dict[str, Any]) -> dict[str, Any]:
    """Loads rubric from a ``path#key`` style reference.

    Supports the same ``path#dotted.key`` convention used by
    ``prompt_ref``. When no ``#`` is present, the whole YAML document is
    returned. Resolves the path relative to ``params['_workflow_dir']``
    if present, falling back to the current working directory.

    Args:
        ref: Rubric reference string (``"rubrics/a.yaml"`` or
            ``"rubrics/a.yaml#default"``).
        params: Node params (to read optional ``_workflow_dir``).

    Returns:
        Rubric dict.

    Raises:
        JudgeHandlerConfigError: If the file is missing or the key path
            cannot be resolved.
    """
    path_part, _, key_part = ref.partition("#")
    if not path_part.strip():
        raise JudgeHandlerConfigError(
            {
                "error": "rubric_ref_empty_path",
                "message": "rubric_ref path segment is empty",
                "summary": {"ref": ref},
                "hint": "Provide a YAML file path before the '#' separator",
            }
        )

    workflow_dir = params.get("_workflow_dir")
    raw_path = Path(path_part.strip())
    if raw_path.is_absolute():
        target = raw_path
    elif workflow_dir:
        target = Path(workflow_dir) / raw_path
    else:
        target = raw_path

    target = target.resolve() if target.exists() else target

    if not target.exists():
        raise JudgeHandlerConfigError(
            {
                "error": "rubric_not_found",
                "message": f"Rubric reference '{ref}' not found",
                "summary": {"path": str(target)},
                "hint": "Ensure the file exists and the path is correct",
            }
        )

    with target.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if data is None:
        raise JudgeHandlerConfigError(
            {
                "error": "rubric_empty_file",
                "message": f"Rubric file is empty: {target}",
                "summary": {"path": str(target)},
                "hint": "Add at least one rubric entry to the YAML file",
            }
        )

    key = key_part.strip()
    if not key:
        if not isinstance(data, dict):
            raise JudgeHandlerConfigError(
                {
                    "error": "invalid_rubric_type",
                    "message": "Rubric YAML root must be a mapping when no #key is specified",
                    "summary": {"type": type(data).__name__},
                    "hint": "Use 'file.yaml#default' or wrap the document as a mapping",
                }
            )
        return data

    current: Any = data
    for segment in key.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise JudgeHandlerConfigError(
                {
                    "error": "rubric_key_not_found",
                    "message": f"Rubric key '{key}' not found in {target}",
                    "summary": {"path": str(target), "key": key},
                    "hint": "Check available keys at the top level of the YAML file",
                }
            )
        current = current[segment]

    if not isinstance(current, dict):
        raise JudgeHandlerConfigError(
            {
                "error": "invalid_rubric_type",
                "message": f"Rubric at '{key}' is not a mapping",
                "summary": {"path": str(target), "key": key},
                "hint": "Rubric entries must be YAML mappings",
            }
        )
    return current


def _validate_rubric(rubric: dict[str, Any]) -> None:
    """Validates the rubric structure (criteria presence, scale validity).

    Args:
        rubric: Rubric dict.

    Raises:
        JudgeHandlerConfigError: For any structural violation. Silent
            success is not permitted — an empty criteria list fails fast.
    """
    criteria = rubric.get("criteria")
    if criteria is None or (isinstance(criteria, list) and len(criteria) == 0):
        raise JudgeHandlerConfigError(
            {
                "error": "rubric_empty",
                "message": "rubric.criteria must contain at least one entry",
                "summary": {"criteria_count": 0},
                "hint": "Add at least one {name, scale} criterion to the rubric",
            }
        )

    if not isinstance(criteria, list):
        raise JudgeHandlerConfigError(
            {
                "error": "invalid_criteria_type",
                "message": "rubric.criteria must be a list",
                "summary": {"type": type(criteria).__name__},
                "hint": "Use YAML list syntax: '- name: ...\\n  scale: ...'",
            }
        )

    seen_names: set[str] = set()
    for index, item in enumerate(criteria):
        if not isinstance(item, dict):
            raise JudgeHandlerConfigError(
                {
                    "error": "invalid_criterion_type",
                    "message": f"rubric.criteria[{index}] must be a mapping",
                    "summary": {"index": index, "type": type(item).__name__},
                    "hint": "Each criterion must be a YAML mapping with 'name' and 'scale'",
                }
            )
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise JudgeHandlerConfigError(
                {
                    "error": "rubric_missing_name",
                    "message": f"rubric.criteria[{index}].name is required and must be a string",
                    "summary": {"index": index, "name": name},
                    "hint": "Add a non-empty 'name' field to each criterion",
                }
            )
        if name in seen_names:
            raise JudgeHandlerConfigError(
                {
                    "error": "rubric_duplicate_name",
                    "message": f"rubric.criteria[{index}].name '{name}' is duplicated",
                    "summary": {"index": index, "name": name},
                    "hint": "Each criterion must have a unique name",
                }
            )
        seen_names.add(name)

        scale = item.get("scale")
        if not isinstance(scale, dict):
            raise JudgeHandlerConfigError(
                {
                    "error": "rubric_missing_scale",
                    "message": f"rubric.criteria[{index}].scale must be a mapping",
                    "summary": {"index": index, "criterion": name},
                    "hint": "Define scale as {min: <int>, max: <int>}",
                }
            )
        scale_min = scale.get("min")
        scale_max = scale.get("max")
        if not isinstance(scale_min, int) or not isinstance(scale_max, int):
            raise JudgeHandlerConfigError(
                {
                    "error": "rubric_invalid_scale_type",
                    "message": (f"rubric.criteria[{index}].scale.min / scale.max must be integers"),
                    "summary": {
                        "index": index,
                        "criterion": name,
                        "min": scale_min,
                        "max": scale_max,
                    },
                    "hint": "Set both min and max to integers (e.g. min: 1, max: 5)",
                }
            )
        if scale_min >= scale_max:
            raise JudgeHandlerConfigError(
                {
                    "error": "rubric_invalid_scale",
                    "message": (f"rubric.criteria[{index}].scale.min must be less than scale.max"),
                    "summary": {
                        "index": index,
                        "criterion": name,
                        "min": scale_min,
                        "max": scale_max,
                    },
                    "hint": "Ensure scale.min < scale.max in your rubric YAML",
                }
            )


def _rubric_to_json_schema(rubric: dict[str, Any]) -> dict[str, Any]:
    """Converts a rubric dict into a JSON Schema describing the judge output.

    Every criterion becomes an integer property on ``score`` with the
    corresponding min/max. When ``require_reasoning`` is true (default),
    ``reasoning`` is required; otherwise optional. ``rubric_items`` mirrors
    per-criterion reasoning for traceability.

    Args:
        rubric: Validated rubric dict.

    Returns:
        JSON Schema dict suitable for the provider's structured output.
    """
    criteria: list[dict[str, Any]] = rubric["criteria"]
    require_reasoning = bool(rubric.get("require_reasoning", True))

    score_properties: dict[str, Any] = {}
    score_required: list[str] = []
    for item in criteria:
        name = str(item["name"])
        scale_min = int(item["scale"]["min"])
        scale_max = int(item["scale"]["max"])
        score_properties[name] = {
            "type": "integer",
            "minimum": scale_min,
            "maximum": scale_max,
        }
        score_required.append(name)

    schema: dict[str, Any] = {
        "type": "object",
        "required": ["score", "rubric_items"],
        "properties": {
            "score": {
                "type": "object",
                "properties": score_properties,
                "required": score_required,
            },
            "reasoning": {"type": "string"},
            "rubric_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "score": {"type": "integer"},
                        "reasoning": {"type": "string"},
                    },
                    "required": ["name", "score"],
                },
            },
        },
    }
    if require_reasoning:
        schema["required"].append("reasoning")
    return schema


def _validate_judge_output(
    raw: dict[str, Any],
    rubric: dict[str, Any],
) -> dict[str, Any]:
    """Validates and normalizes the provider's structured output.

    Args:
        raw: Provider response dict.
        rubric: Original rubric dict (for expected criteria names).

    Returns:
        Normalized judge output with ``_overall`` populated in ``score``.

    Raises:
        JudgeHandlerCallError: If required fields are missing or malformed.
    """
    if not isinstance(raw, dict):
        raise JudgeHandlerCallError(
            {
                "error": "invalid_judge_output",
                "message": "Provider output is not a JSON object",
                "summary": {"type": type(raw).__name__},
                "hint": "Ensure the provider returns a JSON object matching the schema",
            }
        )

    score = raw.get("score")
    if not isinstance(score, dict):
        raise JudgeHandlerCallError(
            {
                "error": "invalid_judge_output",
                "message": "judge output is missing a valid 'score' object",
                "summary": {"score_type": type(score).__name__},
                "hint": "Provider must return 'score' as an object keyed by criterion name",
            }
        )

    expected_names = [str(item["name"]) for item in rubric["criteria"]]
    missing = [n for n in expected_names if n not in score]
    if missing:
        raise JudgeHandlerCallError(
            {
                "error": "invalid_judge_output",
                "message": f"judge output is missing score fields: {missing}",
                "summary": {"missing": missing, "received": sorted(score.keys())},
                "hint": "Provider output must include a score for every rubric criterion",
            }
        )

    reasoning = raw.get("reasoning", "")
    require_reasoning = bool(rubric.get("require_reasoning", True))
    if require_reasoning and not isinstance(reasoning, str):
        raise JudgeHandlerCallError(
            {
                "error": "invalid_judge_output",
                "message": "'reasoning' is required and must be a string",
                "summary": {"type": type(reasoning).__name__},
                "hint": "Provider must return a 'reasoning' string when require_reasoning is true",
            }
        )

    rubric_items = raw.get("rubric_items", [])
    if not isinstance(rubric_items, list):
        raise JudgeHandlerCallError(
            {
                "error": "invalid_judge_output",
                "message": "'rubric_items' must be a list",
                "summary": {"type": type(rubric_items).__name__},
                "hint": "Provider must return rubric_items as a list of per-criterion entries",
            }
        )

    numeric_scores = [
        score[name] for name in expected_names if isinstance(score[name], (int, float))
    ]
    overall: float | None
    if numeric_scores:
        overall = sum(numeric_scores) / len(numeric_scores)
    else:
        overall = None

    normalized_score: dict[str, Any] = {name: score[name] for name in expected_names}
    if overall is not None:
        normalized_score["_overall"] = overall

    return {
        "score": normalized_score,
        "reasoning": reasoning if isinstance(reasoning, str) else "",
        "rubric_items": list(rubric_items),
    }


def _default_system_prompt(rubric: dict[str, Any]) -> str:
    """Builds a minimal system prompt when the user did not supply one.

    Args:
        rubric: Validated rubric dict.

    Returns:
        Generic judge system prompt referencing the rubric.
    """
    description = rubric.get("description", "an evaluation rubric")
    criteria_summary = ", ".join(
        f"{item['name']} ({item['scale']['min']}-{item['scale']['max']})"
        for item in rubric["criteria"]
    )
    return (
        f"You are an evaluator following {description}. "
        f"Score the input strictly according to the rubric criteria: {criteria_summary}. "
        f"Always return valid JSON with the required 'score', 'reasoning', and "
        f"'rubric_items' fields."
    )


JUDGE_HANDLER_PARAMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Parameters for the LLM-as-a-Judge handler created by create_judge_handler. "
        "Evaluates arbitrary inputs against a declarative rubric and returns "
        "structured scores with reasoning."
    ),
    "properties": {
        "provider": {
            "type": "string",
            "enum": ["claude_agent_sdk", "litellm"],
            "default": "claude_agent_sdk",
            "description": (
                "LLM provider adapter. 'claude_agent_sdk' uses Claude subscription "
                "auth (no API key); 'litellm' requires provider API keys"
            ),
        },
        "model": {
            "type": "string",
            "description": (
                "Provider-dependent model identifier. ClaudeAgentSDKProvider accepts "
                "aliases like 'sonnet' or 'opus'; LiteLLMProvider takes 'provider/name' "
                "strings like 'openai/gpt-4o'"
            ),
            "examples": ["sonnet", "opus", "openai/gpt-4o"],
            "default": "sonnet",
        },
        "rubric": {
            "type": "object",
            "description": (
                "Inline rubric definition. Mutually exclusive with rubric_ref. Must "
                "contain a non-empty 'criteria' list"
            ),
        },
        "rubric_ref": {
            "type": "string",
            "description": (
                "Path to a rubric YAML file (optionally with '#key' to select an entry). "
                "Mutually exclusive with rubric"
            ),
            "examples": [
                "rubrics/quality.yaml#default",
                "rubrics/safety.yaml",
            ],
        },
        "prompt": {
            "oneOf": [
                {
                    "type": "object",
                    "description": "Prompt dictionary with 'system' and 'user' keys",
                },
                {"type": "string"},
            ],
            "description": "Inline prompt definition. Mutually exclusive with prompt_ref",
        },
        "prompt_ref": {
            "type": "string",
            "description": (
                "Path to a prompt YAML file (supports '#key' syntax). Mutually "
                "exclusive with prompt"
            ),
            "examples": ["prompts/judge.yaml#system"],
        },
        "output_key": {
            "type": "string",
            "description": "State key to store the judge result. Default 'judge_result'",
            "default": _DEFAULT_OUTPUT_KEY,
        },
    },
    "oneOf": [
        {"required": ["rubric"]},
        {"required": ["rubric_ref"]},
    ],
}


__all__ = [
    "JUDGE_HANDLER_PARAMS_SCHEMA",
    "JudgeHandlerCallError",
    "JudgeHandlerConfigError",
    "JudgeHandlerError",
    "create_judge_handler",
]
