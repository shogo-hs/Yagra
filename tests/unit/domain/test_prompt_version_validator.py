"""Unit tests for prompt_version_validator."""

from __future__ import annotations

from yagra.application.services.reference_resolver import PromptVersionInfo
from yagra.domain.services.prompt_version_validator import (
    collect_prompt_version_issues,
)

_LOCATION = ("nodes", 0, "params", "prompt_ref")


class TestCollectPromptVersionIssues:
    """Tests for collect_prompt_version_issues."""

    def test_no_version_no_meta_no_issue(self) -> None:
        """Both absent produces no issues."""
        infos = [
            PromptVersionInfo(
                catalog_path="prompts.yaml",
                key_path="greeting",
                version_requested=None,
                version_actual=None,
                location=_LOCATION,
            )
        ]
        assert collect_prompt_version_issues(infos) == []

    def test_version_match_no_issue(self) -> None:
        """Matching versions produce no issues."""
        infos = [
            PromptVersionInfo(
                catalog_path="prompts.yaml",
                key_path="greeting",
                version_requested="1.0",
                version_actual="1.0",
                location=_LOCATION,
            )
        ]
        assert collect_prompt_version_issues(infos) == []

    def test_version_mismatch_warning(self) -> None:
        """Mismatched versions produce a warning."""
        infos = [
            PromptVersionInfo(
                catalog_path="prompts.yaml",
                key_path="greeting",
                version_requested="1.0",
                version_actual="2.0",
                location=_LOCATION,
            )
        ]
        issues = collect_prompt_version_issues(infos)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "1.0" in issues[0].message
        assert "2.0" in issues[0].message
        assert issues[0].context is not None
        assert issues[0].context["requested_version"] == "1.0"
        assert issues[0].context["actual_version"] == "2.0"

    def test_version_requested_but_no_meta_warning(self) -> None:
        """Version requested but _meta.version missing produces warning."""
        infos = [
            PromptVersionInfo(
                catalog_path="prompts.yaml",
                key_path="greeting",
                version_requested="v1",
                version_actual=None,
                location=_LOCATION,
            )
        ]
        issues = collect_prompt_version_issues(infos)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "no _meta.version" in issues[0].message

    def test_meta_exists_but_not_pinned_info(self) -> None:
        """_meta.version exists but prompt_ref has no @version produces info."""
        infos = [
            PromptVersionInfo(
                catalog_path="prompts.yaml",
                key_path="greeting",
                version_requested=None,
                version_actual="1.0",
                location=_LOCATION,
            )
        ]
        issues = collect_prompt_version_issues(infos)
        assert len(issues) == 1
        assert issues[0].severity == "info"
        assert "@1.0" in issues[0].message

    def test_empty_infos_no_issues(self) -> None:
        """Empty input produces no issues."""
        assert collect_prompt_version_issues([]) == []

    def test_multiple_nodes_mixed(self) -> None:
        """Multiple nodes with different scenarios."""
        infos = [
            # Match — no issue
            PromptVersionInfo(
                catalog_path="prompts.yaml",
                key_path="a",
                version_requested="1.0",
                version_actual="1.0",
                location=("nodes", 0, "params", "prompt_ref"),
            ),
            # Mismatch — warning
            PromptVersionInfo(
                catalog_path="prompts.yaml",
                key_path="b",
                version_requested="1.0",
                version_actual="2.0",
                location=("nodes", 1, "params", "prompt_ref"),
            ),
            # Unpinned — info
            PromptVersionInfo(
                catalog_path="prompts.yaml",
                key_path="c",
                version_requested=None,
                version_actual="3.0",
                location=("nodes", 2, "params", "prompt_ref"),
            ),
        ]
        issues = collect_prompt_version_issues(infos)
        assert len(issues) == 2
        assert issues[0].severity == "warning"
        assert issues[1].severity == "info"

    def test_location_is_preserved(self) -> None:
        """Issue location matches the input info location."""
        loc = ("nodes", 5, "params", "prompt_ref")
        infos = [
            PromptVersionInfo(
                catalog_path="x.yaml",
                key_path=None,
                version_requested="v1",
                version_actual="v2",
                location=loc,
            )
        ]
        issues = collect_prompt_version_issues(infos)
        assert issues[0].location == loc
