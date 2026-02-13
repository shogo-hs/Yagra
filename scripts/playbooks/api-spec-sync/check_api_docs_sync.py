#!/usr/bin/env python3
"""API実装変更に対してAPIドキュメント変更があるかを簡易検知する。"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

DEFAULT_CODE_PATHS = ["src", "app", "backend", "server"]


def run_git(args: list[str]) -> str:
    """Git コマンドを実行し、標準出力を返す。

    Args:
        args: `git` に渡すサブコマンドと引数。

    Returns:
        コマンド実行結果の標準出力。

    Raises:
        RuntimeError: コマンド実行が失敗した場合。
    """
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def has_ref(ref: str) -> bool:
    """指定した Git ref が存在するかを返す。

    Args:
        ref: 検証対象の Git ref。

    Returns:
        ref が存在する場合は `True`、存在しない場合は `False`。
    """
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def normalize(path: str) -> str:
    """パス文字列を POSIX 形式に正規化する。

    Args:
        path: 正規化対象のパス。

    Returns:
        正規化後のパス文字列。
    """
    return str(pathlib.PurePosixPath(path.strip()))


def is_under(path: str, root: str) -> bool:
    """パスが指定ルート配下にあるかを判定する。

    Args:
        path: 判定対象パス。
        root: ルートとなるパス。

    Returns:
        `path` が `root` 自身、または `root` 配下であれば `True`。
    """
    root_norm = normalize(root).rstrip("/")
    return path == root_norm or path.startswith(root_norm + "/")


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。

    Returns:
        解析済みの引数オブジェクト。
    """
    parser = argparse.ArgumentParser(
        description="API実装変更に対してAPIドキュメント更新漏れがないかを検査する"
    )
    parser.add_argument(
        "--docs-root",
        required=True,
        help="APIドキュメントのルートディレクトリ（例: docs/api）",
    )
    parser.add_argument(
        "--base-ref",
        default="HEAD",
        help="差分比較の基準ref（既定: HEAD）",
    )
    parser.add_argument(
        "--code-path",
        action="append",
        default=None,
        help="API実装が置かれるパス。複数指定可（例: --code-path services/api）",
    )
    parser.add_argument(
        "--api-pattern",
        default=r"(route|router|handler|controller|endpoint|openapi|swagger|dto|schema|api)",
        help="API実装とみなすファイル名/パスの正規表現",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="判定対象ファイルを詳細表示する",
    )
    return parser.parse_args()


def collect_changed_files(base_ref: str) -> list[str]:
    """比較対象 ref から変更ファイル一覧を収集する。

    Args:
        base_ref: 差分比較の基準となる Git ref。

    Returns:
        正規化済みの変更ファイルパス一覧。

    Raises:
        RuntimeError: 指定 ref が見つからない場合。
    """
    changed: set[str] = set()

    if has_ref(base_ref):
        output = run_git(["diff", "--name-only", base_ref, "--"])
        changed.update(normalize(line) for line in output.splitlines() if line.strip())
        if base_ref == "HEAD":
            untracked = run_git(["ls-files", "--others", "--exclude-standard"])
            changed.update(normalize(line) for line in untracked.splitlines() if line.strip())
        return sorted(changed)

    if base_ref != "HEAD":
        raise RuntimeError(f"指定されたrefが見つかりません: {base_ref}")

    unstaged = run_git(["diff", "--name-only", "--"])
    staged = run_git(["diff", "--name-only", "--cached", "--"])
    untracked = run_git(["ls-files", "--others", "--exclude-standard"])
    merged = "\n".join([unstaged, staged, untracked])
    changed.update(normalize(line) for line in merged.splitlines() if line.strip())
    return sorted(changed)


def main() -> int:
    """API ドキュメント同期チェックを実行する。

    Returns:
        成功時は `0`、更新漏れ検知時は `1`、実行エラー時は `2`。
    """
    args = parse_args()

    try:
        inside = run_git(["rev-parse", "--is-inside-work-tree"]).strip()
    except RuntimeError as err:
        print(f"[ERROR] git実行に失敗: {err}", file=sys.stderr)
        return 2

    if inside != "true":
        print("[ERROR] gitリポジトリ内で実行してください", file=sys.stderr)
        return 2

    try:
        changed = collect_changed_files(args.base_ref)
    except RuntimeError as err:
        print(f"[ERROR] 差分取得に失敗: {err}", file=sys.stderr)
        return 2
    if not changed:
        print("[OK] 変更差分はありません。")
        return 0

    api_regex = re.compile(args.api_pattern, flags=re.IGNORECASE)
    code_paths = args.code_path or DEFAULT_CODE_PATHS
    code_roots = [normalize(p).rstrip("/") for p in code_paths]
    docs_root = normalize(args.docs_root).rstrip("/")

    docs_changed = [p for p in changed if is_under(p, docs_root) and p.endswith(".md")]

    api_impl_changed: list[str] = []
    for path in changed:
        if not any(is_under(path, root) for root in code_roots):
            continue
        if api_regex.search(path):
            api_impl_changed.append(path)

    if args.verbose:
        print("[INFO] changed files:")
        for p in changed:
            print(f"  - {p}")

    if not api_impl_changed:
        print("[OK] API実装に該当する変更は検出されませんでした。")
        return 0

    if docs_changed:
        print("[OK] API実装変更とAPIドキュメント変更の両方を検出しました。")
        print("[INFO] API実装変更:")
        for p in api_impl_changed:
            print(f"  - {p}")
        print("[INFO] APIドキュメント変更:")
        for p in docs_changed:
            print(f"  - {p}")
        return 0

    print("[NG] API実装変更を検出しましたが、APIドキュメント更新が見つかりません。")
    print("[INFO] API実装変更:")
    for p in api_impl_changed:
        print(f"  - {p}")
    print(f"[ACTION] {docs_root}/ 配下のMarkdownを更新してください。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
