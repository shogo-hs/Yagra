"""Smoke test for Yagra initialization."""

from __future__ import annotations

import sys

import pytest

from yagra import main


def test_main_requires_subcommand(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirms that the CLI requires a subcommand.

    Args:
        monkeypatch: pytest fixture that replaces `sys.argv`.
        capsys: pytest fixture that captures stdout and stderr.
    """
    monkeypatch.setattr(sys, "argv", ["yagra"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "usage: yagra" in captured.err
