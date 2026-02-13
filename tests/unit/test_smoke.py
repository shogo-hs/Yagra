"""Yagra 初期化のスモークテスト。"""

from __future__ import annotations

import pytest

from yagra import main


def test_main_prints_bootstrap_message(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI エントリポイントが起動メッセージを出力することを確認する。

    Args:
        capsys: 標準出力のキャプチャを提供する pytest fixture。
    """
    main()
    captured = capsys.readouterr()
    assert "Yagra bootstrap is ready." in captured.out
