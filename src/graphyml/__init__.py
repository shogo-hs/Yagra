"""Graphyml パッケージのエントリポイント。"""


def main() -> None:
    """Graphyml の初期化状態を標準出力へ表示する。

    開発環境の初期化が完了していることを確認するための最小 CLI として使う。
    本実装では副作用を持たず、メッセージ表示のみを行う。
    """
    print("Graphyml bootstrap is ready.")
