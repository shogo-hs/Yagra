"""Yagra 初期化のスモークテスト。"""

from __future__ import annotations

import sys

import pytest

from yagra import main


def test_main_requires_subcommand(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI がサブコマンド必須であることを確認する。

    Args:
        monkeypatch: `sys.argv` を差し替える pytest fixture。
        capsys: 標準出力・標準エラーのキャプチャを提供する pytest fixture。
    """
    monkeypatch.setattr(sys, "argv", ["yagra"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "usage: yagra" in captured.err
