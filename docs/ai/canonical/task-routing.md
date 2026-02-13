# タスクルーティング

| 判断ケース | この条件なら使う | 参照先Playbook |
| --- | --- | --- |
| 実装前設計 | 実装・修正・移行など、ファイル変更前にスコープ整理と承認が必要 | [task-design-gate](docs/ai/playbooks/task-design-gate.md) |
| Python の CI / 品質ゲート導入 | `uv` 前提で lint/type/test/CI を一貫運用したい | [python-uv-ci-setup](docs/ai/playbooks/python-uv-ci-setup.md) |
| 新規プロジェクト初期構築 | Python プロジェクトを Hexagonal + 運用標準で立ち上げ、`docs/product/*.md` を初期擦り合わせする | [python-project-bootstrap](docs/ai/playbooks/python-project-bootstrap.md) |
| API 仕様同期 | API 実装と仕様ドキュメントの差分を同期する | [api-spec-sync](docs/ai/playbooks/api-spec-sync.md) |
| 設計判断の記録・更新 | アーキテクチャ方針や運用ルールの採否を ADR として記録・更新する | [adr-management](docs/ai/playbooks/adr-management.md) |
| コミット実行 | 変更内容を確認して規約に沿ったコミットを行う | [git-commit](docs/ai/playbooks/git-commit.md) |

## 使い分けルール

- AGENTS.md には「いつどの Playbook を使うか」を書き、実行時はリンク先ドキュメントを参照する。
- 詳細手順の正本は `docs/ai/canonical/playbooks/*.md` に集約し、`scripts/sync_ai_context.py` で `docs/ai/playbooks/*.md` へ配布する。
- 参照資料は `docs/ai/playbook-assets/`、補助スクリプトは `scripts/playbooks/` に集約する。
- 同じ手順を AGENTS.md と Playbook に重複記載しない。
