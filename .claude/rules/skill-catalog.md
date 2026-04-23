---
paths:
  - "**"
---

# Yagra スキルカタログ

## スキル一覧

| コマンド | 用途 |
|---------|------|
| `/task-design-gate` | タスク設計ゲート（実装前のスコープ確定・承認取得） |
| `/python-uv-ci-setup` | Python + uv + ruff/mypy/pytest + pre-commit + GitHub Actions を一括整備 |
| `/python-project-bootstrap` | 新規 Python プロジェクトを Hexagonal 前提で初期構築 |
| `/api-spec-sync` | API 実装と仕様ドキュメント（index + エンドポイント）を同期 |
| `/adr-management` | 設計判断を ADR として記録・更新 |
| `/git-commit` | 規約に沿ったコミット（日本語、50文字以内、プレフィックス） |
| `/release-ops` | SemVer リリース（CHANGELOG 3 箇所同期、タグ、GitHub Release） |

## スキルの使い分け

- 実装前にスコープ整理・承認を得たい → `/task-design-gate`
- 新規 Python プロジェクトを立ち上げたい → `/python-project-bootstrap`
- CI / 品質ゲートを整備したい → `/python-uv-ci-setup`
- API 実装を変更した、仕様ドキュメントを同期したい → `/api-spec-sync`
- 設計方針の採否を記録したい → `/adr-management`
- 変更をコミットしたい → `/git-commit`
- バージョンをリリースしたい → `/release-ops`

## スキル設計の規約

- スキルは `.claude/skills/<name>/SKILL.md` に配置（`commands/` は非推奨）
- 補助資料は `.claude/skills/<name>/references/` に配置（Progressive Disclosure）
- 補助スクリプトは `scripts/playbooks/<name>/` に配置（既存慣習を継承）
- 新規スキル追加時は本ファイルの表と「使い分け」節を必ず更新する
