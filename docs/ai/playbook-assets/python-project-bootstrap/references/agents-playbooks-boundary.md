# AGENTS.md と Playbooks の責務境界

## 結論

- AGENTS.md は「常時有効なルール」を記述する。
- Playbooks は「条件付きで使う実行手順」を記述する。
- チーム再現性を優先する場合、参照資料と補助スクリプトはリポジトリ配下に配置して運用する。
- 新規作成はテンプレートリポジトリを優先し、空リポジトリ時のみグローバル bootstrap を1回だけ許容する。

## AGENTS.md に書く

- 目的、前提、品質基準、禁止事項
- どのタスクでどの Playbook を使うか（短いルーティング）
- タスク設計ゲート、言語ポリシー、コミット規約
- CI を必須とするかどうか

## AGENTS.md に書かない

- 長いコマンド列
- ツールごとの詳細設定値
- 例外分岐を含む実行手順

## Playbooks に書く

- 実行順序、分岐条件、失敗時のリカバリ
- コマンド、テンプレート、検証手順
- 実装時に必要な補助資料（playbook-assets）

## チーム再現性ポリシー

- 原則として新規作成は Playbook 同梱テンプレートリポジトリから開始する。
- 共有する参照資料は `docs/ai/playbook-assets/`、補助スクリプトは `scripts/playbooks/` に配置する。
- 個人ホーム配下の資産への依存を必須要件にしない。
- 空リポジトリから開始する場合のみ、グローバル `python-project-bootstrap` を初回1回だけ使う。
- 初回生成直後に Playbook 正本を `<repo>/docs/ai/canonical/playbooks/` へ配置し、以後は repo ローカルを正本にする。
- AGENTS.md では Playbook 名と役割のみを記述し、詳細は repo 内 playbook を参照する。
- Playbook 更新時は PR で差分レビューする。

## ルーティング例

- タスク設計ゲート: `task-design-gate`
- Python の CI 設定: `python-uv-ci-setup`
- API 仕様同期: `api-spec-sync`
- コミット実行: `git-commit`

上記は AGENTS.md では「いつ使うか」だけ記載し、具体手順は各 Playbook に委譲する。
