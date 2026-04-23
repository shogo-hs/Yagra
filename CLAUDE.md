# CLAUDE.md — Yagra

Yagra は LangGraph ベースの AI エージェントワークフローランタイム。
本ファイルは Claude Code 向けの運用規約。人間向けの入口は @README.md。

## プロジェクト要点
- Hexagonal Architecture（adapters / application / domain / ports）
- Python 3.12+ / uv / LangGraph / MCP Server
- 詳細: @README.md / @CONTRIBUTING.md / @docs/architecture/

## 役割分離
- `README.md`: 人間が最初に理解するための入口（目的・全体像・セットアップ）
- `CLAUDE.md`（本ファイル）: エージェントが実行時に守る規約
- 同じ内容を両方に重複記載しない

## 作業モード（運用規範）
1. 計画優先: 3 ステップ以上 or 設計判断を伴うタスクは必ず計画を提示し承認を得る
2. サブエージェント優先: 調査・探索・並列分析はサブエージェント化
3. 完了前検証: テスト実行・ログ確認を行い「スタッフエンジニアが承認するか」を自問
4. 根本原因優先: 場当たり修正禁止
5. 最小変更: 必要箇所のみ変更
6. 想定外の大量差分・履歴破壊操作・広範囲削除が必要な場合は作業を停止しユーザー再確認

## タスクルーティング
- スキル一覧と選択指針: @.claude/rules/skill-catalog.md

## 開発コマンド・コーディング標準
- セットアップ、テスト、lint、pre-commit、パッケージ管理: @CONTRIBUTING.md
- Python パッケージ操作は `uv add / uv remove / uv sync` のみ。`pip install` / `uv pip install` 禁止
- アーキテクチャ・SOLID 規約: @docs/rules/code_architecture/ / @docs/rules/solid/
- ADR: @docs/adr/（`/adr-management` で作成）

## プロダクト文脈
- ビジョン・ゴール・マイルストーン: @docs/product/（正本）
- API 仕様: @docs/api/

## リリース規範
- Semantic Versioning、`pyproject.toml` の `version` と一致
- 3 箇所同期: CHANGELOG.md（日本語正本）/ docs/sphinx/source/changelog.md（英語）/ GitHub Release（英語）
- Keep a Changelog 形式（Added / Changed / Deprecated / Removed / Fixed / Security）
- 具体手順: @.claude/skills/release-ops/SKILL.md

## セキュリティ（4 層防御）
- Layer 1: `.claude/settings.json` の permissions.deny（.env*, credentials, secret 読取禁止）
- Layer 2: PreToolUse フック（将来実装予定）
- Layer 3: MCP / サンドボックス境界
- Layer 4: 本 CLAUDE.md + @.claude/rules/security.md の運用規範
- 環境変数: `.env.development` / `.env.production` + dotenvx `encrypted:` 形式。`.env.keys` コミット禁止

## Claude Code 運用ノート
- コミュニケーション言語: 日本語
- 計画・タスクは tasks/todo.md、教訓は tasks/lessons.md
- Skills は `.claude/skills/<name>/SKILL.md`（`commands/` は非推奨）

## 参照
- 詳細ガイド: @CONTRIBUTING.md
