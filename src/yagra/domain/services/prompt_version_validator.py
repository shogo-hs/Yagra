"""Validates prompt version consistency between prompt_ref and _meta.version.

Compares the ``@version`` suffix in ``prompt_ref`` references against the
``_meta.version`` field in the referenced prompt catalog file.  Issues are
advisory (warning or info) and never affect workflow validity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from yagra.application.services.reference_resolver import PromptVersionInfo

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class PromptVersionIssue:
    """A single issue detected during prompt version validation.

    Attributes:
        message: Human-readable description of the issue.
        location: Path within the workflow where the issue was detected.
        severity: Issue severity — ``"warning"`` or ``"info"``.
        context: Additional structured data for programmatic consumption.
    """

    message: str
    location: Location
    severity: Literal["warning", "info"] = "warning"
    context: dict[str, Any] | None = None


def collect_prompt_version_issues(
    version_infos: list[PromptVersionInfo],
) -> list[PromptVersionIssue]:
    """Validates version consistency for resolved prompt references.

    Checks performed:

    1. ``@version`` requested but ``_meta.version`` is missing in the prompt
       catalog file → **warning**.
    2. ``@version`` requested and ``_meta.version`` exists but they differ →
       **warning**.
    3. ``_meta.version`` exists but ``prompt_ref`` does not pin a version →
       **info** (advisory to consider pinning).

    When both are absent or versions match, no issue is emitted.

    Args:
        version_infos: Version metadata collected during reference resolution.

    Returns:
        List of detected issues.  Empty list if no issues found.
    """
    issues: list[PromptVersionIssue] = []

    for info in version_infos:
        if info.version_requested is not None:
            if info.version_actual is None:
                # Version requested but _meta.version missing
                issues.append(
                    PromptVersionIssue(
                        message=(
                            f"prompt_ref requests version '{info.version_requested}' "
                            f"but '{info.catalog_path}' has no _meta.version"
                        ),
                        location=info.location,
                        severity="warning",
                        context={
                            "requested_version": info.version_requested,
                            "catalog_path": info.catalog_path,
                        },
                    )
                )
            elif info.version_requested != info.version_actual:
                # Version mismatch
                issues.append(
                    PromptVersionIssue(
                        message=(
                            f"prompt_ref requests version '{info.version_requested}' "
                            f"but '{info.catalog_path}' has _meta.version "
                            f"'{info.version_actual}'"
                        ),
                        location=info.location,
                        severity="warning",
                        context={
                            "requested_version": info.version_requested,
                            "actual_version": info.version_actual,
                            "catalog_path": info.catalog_path,
                        },
                    )
                )
        elif info.version_actual is not None:
            # _meta.version exists but not pinned in prompt_ref
            issues.append(
                PromptVersionIssue(
                    message=(
                        f"'{info.catalog_path}' has _meta.version "
                        f"'{info.version_actual}' but prompt_ref does not pin "
                        f"a version; consider using '@{info.version_actual}' suffix"
                    ),
                    location=info.location,
                    severity="info",
                    context={
                        "actual_version": info.version_actual,
                        "catalog_path": info.catalog_path,
                    },
                )
            )

    return issues
