#!/usr/bin/env python3
"""canonical から AGENTS.md / Cursor rules / Playbooks を生成・検証する。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

CANONICAL_FILES = {
    "global": Path("docs/ai/canonical/global-policies.md"),
    "routing": Path("docs/ai/canonical/task-routing.md"),
    "coding": Path("docs/ai/canonical/coding-standards.md"),
}

OUTPUT_FILES = {
    "agents": Path("AGENTS.md"),
    "cursor_global": Path(".cursor/rules/00-global.mdc"),
    "cursor_routing": Path(".cursor/rules/10-task-routing.mdc"),
    "cursor_playbooks": Path(".cursor/rules/20-playbooks.mdc"),
}

PLAYBOOK_CANONICAL_DIR = Path("docs/ai/canonical/playbooks")
PLAYBOOK_OUTPUT_DIR = Path("docs/ai/playbooks")

AUTO_GENERATED_NOTICE = "<!-- AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY. -->\n"
FRONTMATTER_PATTERN = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)
AGENTS_WARN_BYTES = 8 * 1024
AGENTS_HARD_LIMIT_BYTES = 32 * 1024
ROUTING_BULLET_PLAYBOOK_PATTERN = re.compile(r"-\s*(.+?)\s*:\s*`([a-z0-9-]+)`")
ROUTING_TABLE_PLAYBOOK_LINK_PATTERN = re.compile(
    r"\[([^\]]+)\]\((?:\./)?docs/ai/playbooks/([a-z0-9-]+)\.md(?:#[^)]+)?\)"
)
ROUTING_TABLE_HEADER_LABELS = {"判断ケース", "ケース", "タスク", "---"}


def auto_header(source: str) -> str:
    """生成ファイル向けヘッダを返す。"""
    return AUTO_GENERATED_NOTICE + f"<!-- source: {source} + scripts/sync_ai_context.py -->\n"


def strip_first_heading(markdown: str) -> str:
    """先頭見出しを除去して本文だけを返す。"""
    lines = markdown.strip().splitlines()
    if lines and lines[0].startswith("#"):
        return "\n".join(lines[1:]).strip()
    return "\n".join(lines).strip()


def read_canonical(root: Path) -> dict[str, str]:
    """canonical ファイルを読み込む。"""
    contents: dict[str, str] = {}
    for key, rel_path in CANONICAL_FILES.items():
        path = root / rel_path
        if not path.exists():
            raise FileNotFoundError(f"missing canonical file: {path}")
        contents[key] = path.read_text(encoding="utf-8")
    return contents


def extract_playbook_routes(routing_markdown: str) -> list[tuple[str, str]]:
    """task-routing から (表示名, playbook名) の順序付き一覧を抽出する。"""
    routes: list[tuple[str, str]] = []
    seen: set[str] = set()

    for line in routing_markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        link_match = ROUTING_TABLE_PLAYBOOK_LINK_PATTERN.search(stripped)
        if link_match is None:
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        header_candidate = cells[0].replace("`", "").strip() if cells else ""
        if header_candidate and header_candidate not in ROUTING_TABLE_HEADER_LABELS:
            label = header_candidate
        else:
            label = link_match.group(1).strip()
        playbook = link_match.group(2)

        if playbook in seen:
            continue
        routes.append((label, playbook))
        seen.add(playbook)

    for line in routing_markdown.splitlines():
        match = ROUTING_BULLET_PLAYBOOK_PATTERN.search(line.strip())
        if not match:
            continue
        label, playbook = match.group(1), match.group(2)
        if playbook in seen:
            continue
        routes.append((label, playbook))
        seen.add(playbook)
    return routes


def read_canonical_playbooks(root: Path, playbook_names: list[str]) -> dict[str, str]:
    """playbook canonical を読み込む。"""
    contents: dict[str, str] = {}
    for playbook_name in playbook_names:
        path = root / PLAYBOOK_CANONICAL_DIR / f"{playbook_name}.md"
        if not path.exists():
            raise FileNotFoundError(f"missing playbook canonical: {path}")
        contents[playbook_name] = path.read_text(encoding="utf-8")
    return contents


def with_auto_header(markdown: str, source: str) -> str:
    """frontmatter がある場合は保持したまま自動生成ヘッダを挿入する。"""
    header = auto_header(source)
    body = markdown.strip() + "\n"

    match = FRONTMATTER_PATTERN.match(body)
    if match is None:
        return f"{header}\n{body}"

    frontmatter = match.group(0).rstrip() + "\n"
    remainder = body[match.end() :].strip()
    if remainder:
        return f"{frontmatter}\n{header}\n{remainder}\n"
    return f"{frontmatter}\n{header}\n"


def build_agents(canonical: dict[str, str]) -> str:
    """AGENTS.md の内容を生成する。"""
    global_body = strip_first_heading(canonical["global"])
    routing_body = strip_first_heading(canonical["routing"])
    coding_body = strip_first_heading(canonical["coding"])

    return (
        "# AGENTS.md\n\n"
        f"{auto_header('docs/ai/canonical/*')}\n"
        "## このファイルについて\n"
        "- このファイルは自動生成です。直接編集しないでください。\n"
        "- 変更は `docs/ai/canonical/` を編集し、`python3 scripts/sync_ai_context.py` を実行してください。\n\n"
        "## 1. グローバルポリシー\n"
        f"{global_body}\n\n"
        "## 2. タスクルーティング\n"
        f"{routing_body}\n\n"
        "## 3. コーディング標準\n"
        f"{coding_body}\n"
    )


def build_cursor_rule(description: str, body: str, source: str) -> str:
    """Cursor rule (.mdc) の内容を生成する。"""
    return (
        "---\n"
        f'description: "{description}"\n'
        "alwaysApply: true\n"
        "---\n\n"
        f"{auto_header(source)}\n"
        f"{body.strip()}\n"
    )


def build_cursor_playbooks_rule(playbook_routes: list[tuple[str, str]]) -> str:
    """Cursor から共通 playbook を参照するための rule 本文を生成する。"""
    lines = [
        "# 共通Playbook運用",
        "",
        "- 詳細手順の正本は `docs/ai/canonical/playbooks/*.md` とし、実行時は `docs/ai/playbooks/*.md` を参照する。",
        "- 依頼内容が該当する playbook を選び、実行フローと厳守ルールに従う。",
        "- 複数 playbook が該当する場合は、最小セットを順に適用する。",
        "- 手順の重複記述を避け、ルール本文には参照先のみを書く。",
        "",
        "## Playbook 参照先",
    ]
    for label, playbook_name in playbook_routes:
        lines.append(f"- {label}: `docs/ai/playbooks/{playbook_name}.md`")
    lines.extend(
        [
            "",
            "## 運用注意",
            "- playbook 更新時は `docs/ai/canonical/playbooks/` を編集する。",
            "- 反映は `python3 scripts/sync_ai_context.py` を実行する。",
        ]
    )
    return "\n".join(lines)


def build_outputs(
    canonical: dict[str, str],
    playbook_routes: list[tuple[str, str]],
    playbooks: dict[str, str],
) -> dict[Path, str]:
    """出力ファイル群を生成する。"""
    global_body = strip_first_heading(canonical["global"])
    routing_body = strip_first_heading(canonical["routing"])
    coding_body = strip_first_heading(canonical["coding"])

    cursor_global = "# グローバルポリシー\n\n" + global_body + "\n\n# コーディング標準\n\n" + coding_body
    cursor_routing = "# タスクルーティング\n\n" + routing_body

    outputs: dict[Path, str] = {
        OUTPUT_FILES["agents"]: build_agents(canonical),
        OUTPUT_FILES["cursor_global"]: build_cursor_rule(
            "プロジェクト共通ポリシーと標準",
            cursor_global,
            source="docs/ai/canonical/*",
        ),
        OUTPUT_FILES["cursor_routing"]: build_cursor_rule(
            "タスク別のPlaybookルーティング",
            cursor_routing,
            source="docs/ai/canonical/*",
        ),
        OUTPUT_FILES["cursor_playbooks"]: build_cursor_rule(
            "共通Playbook参照ルール",
            build_cursor_playbooks_rule(playbook_routes),
            source="docs/ai/canonical/playbooks/*",
        ),
    }
    for playbook_name, markdown in playbooks.items():
        source = f"docs/ai/canonical/playbooks/{playbook_name}.md"
        outputs[PLAYBOOK_OUTPUT_DIR / f"{playbook_name}.md"] = with_auto_header(markdown, source)
    return outputs


def normalized_content(content: str) -> str:
    """末尾改行を正規化した文字列を返す。"""
    return content.rstrip() + "\n"


def validate_agents_size(outputs: dict[Path, str]) -> int:
    """AGENTS.md のサイズを検査して、継続可否を返す。"""
    agents_rel_path = OUTPUT_FILES["agents"]
    agents_content = normalized_content(outputs[agents_rel_path])
    size = len(agents_content.encode("utf-8"))

    if size > AGENTS_WARN_BYTES:
        print(
            f"[WARN] AGENTS.md size is {size} bytes "
            f"(recommended <= {AGENTS_WARN_BYTES} bytes)."
        )

    if size > AGENTS_HARD_LIMIT_BYTES:
        print(
            f"[NG] AGENTS.md size is {size} bytes "
            f"(hard limit: {AGENTS_HARD_LIMIT_BYTES} bytes)."
        )
        print("Move detailed procedures from AGENTS.md to docs/ai/playbooks/*.md.")
        return 1
    return 0


def write_outputs(root: Path, outputs: dict[Path, str]) -> list[Path]:
    """出力を書き込み、変更されたファイル一覧を返す。"""
    changed: list[Path] = []
    for rel_path, content in outputs.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = normalized_content(content)
        if path.exists() and path.read_text(encoding="utf-8") == normalized:
            continue
        path.write_text(normalized, encoding="utf-8")
        changed.append(rel_path)
    return changed


def check_outputs(root: Path, outputs: dict[Path, str]) -> list[Path]:
    """期待値との差分があるファイル一覧を返す。"""
    drift: list[Path] = []
    for rel_path, content in outputs.items():
        path = root / rel_path
        expected = normalized_content(content)
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            drift.append(rel_path)
    return drift


def parse_args() -> argparse.Namespace:
    """CLI 引数を解析する。"""
    parser = argparse.ArgumentParser(description="AI context files synchronizer")
    parser.add_argument("--check", action="store_true", help="差分検知のみ実施して終了する")
    parser.add_argument(
        "--root",
        default=".",
        help="テンプレートリポジトリのルートパス（既定: カレントディレクトリ）",
    )
    return parser.parse_args()


def main() -> int:
    """メイン処理。"""
    args = parse_args()
    root = Path(args.root).resolve()
    canonical = read_canonical(root)
    playbook_routes = extract_playbook_routes(canonical["routing"])
    playbook_names = [playbook_name for _, playbook_name in playbook_routes]
    playbooks = read_canonical_playbooks(root, playbook_names)
    outputs = build_outputs(canonical, playbook_routes, playbooks)
    size_validation = validate_agents_size(outputs)
    if size_validation != 0:
        return size_validation

    if args.check:
        drift = check_outputs(root, outputs)
        if drift:
            print("[NG] Generated files are out of date:")
            for rel_path in drift:
                print(f"  - {rel_path}")
            print("Run: python3 scripts/sync_ai_context.py")
            return 1
        print("[OK] Generated files are up to date.")
        return 0

    changed = write_outputs(root, outputs)
    if changed:
        print("[OK] Updated generated files:")
        for rel_path in changed:
            print(f"  - {rel_path}")
    else:
        print("[OK] No changes needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
