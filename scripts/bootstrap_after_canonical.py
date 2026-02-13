#!/usr/bin/env python3
"""canonical 編集後の初期化処理を順次実行する。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """CLI 引数を解析する。"""
    parser = argparse.ArgumentParser(
        description="canonical 同期 + bootstrap_python_project を連続実行する"
    )
    parser.add_argument(
        "--root",
        default=".",
        help="テンプレート/プロジェクトのルートパス（既定: カレントディレクトリ）",
    )
    parser.add_argument("--project-name", required=True, help="プロジェクト名")
    parser.add_argument("--description", default="<TBD>", help="プロジェクト説明")
    parser.add_argument("--task-design-dir", help="タスク設計ディレクトリ（例: docs/task-designs）")
    parser.add_argument("--package-name", help="Python パッケージ名")
    parser.add_argument("--python-version", default="3.12+", help="Python バージョン表記")
    return parser.parse_args()


def ensure_file_exists(path: Path, label: str) -> None:
    """必須ファイルの存在を確認する。"""
    if not path.exists():
        raise FileNotFoundError(f"{label} が見つかりません: {path}")


def run_step(step_name: str, cmd: list[str], cwd: Path) -> None:
    """1ステップ実行し、失敗時に例外を送出する。"""
    printable = " ".join(cmd)
    print(f"[STEP] {step_name}", flush=True)
    print(f"  $ {printable}", flush=True)
    completed = subprocess.run(cmd, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd)


def main() -> int:
    """メイン処理。"""
    args = parse_args()
    root = Path(args.root).resolve()

    sync_script = root / "scripts" / "sync_ai_context.py"
    bootstrap_script = (
        root
        / "scripts"
        / "playbooks"
        / "python-project-bootstrap"
        / "bootstrap_python_project.py"
    )

    try:
        ensure_file_exists(sync_script, "sync スクリプト")
        ensure_file_exists(bootstrap_script, "bootstrap スクリプト")
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 2

    python = sys.executable
    bootstrap_cmd = [
        python,
        str(bootstrap_script),
        "--target",
        str(root),
        "--project-name",
        args.project_name,
        "--description",
        args.description,
        "--python-version",
        args.python_version,
    ]
    if args.task_design_dir:
        bootstrap_cmd.extend(["--task-design-dir", args.task_design_dir])
    if args.package_name:
        bootstrap_cmd.extend(["--package-name", args.package_name])

    steps = [
        ("AI context 生成", [python, str(sync_script)]),
        ("AI context drift 検証", [python, str(sync_script), "--check"]),
        ("Python プロジェクト初期構成生成", bootstrap_cmd),
    ]

    completed_steps: list[str] = []
    try:
        for step_name, cmd in steps:
            run_step(step_name, cmd, cwd=root)
            completed_steps.append(step_name)
    except subprocess.CalledProcessError as exc:
        print("")
        print(f"[FAILED] {len(completed_steps) + 1}/{len(steps)} で失敗")
        print(f"  step: {steps[len(completed_steps)][0]}")
        print(f"  exit: {exc.returncode}")
        return exc.returncode or 1

    print("")
    print("[OK] すべてのステップが完了しました。")
    print(f"  completed: {len(completed_steps)}/{len(steps)}")
    for step_name in completed_steps:
        print(f"  - {step_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
