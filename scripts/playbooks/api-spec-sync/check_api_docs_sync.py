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
    result = subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def has_ref(ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def normalize(path: str) -> str:
    return str(pathlib.PurePosixPath(path.strip()))


def is_under(path: str, root: str) -> bool:
    root_norm = normalize(root).rstrip("/")
    return path == root_norm or path.startswith(root_norm + "/")


def parse_args() -> argparse.Namespace:
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
