---
name: task-design-gate
description: 実装前にタスク設計書を作成し、スコープ・前提・リスクをそろえたうえでユーザー承認を取得するためのPlaybook。実装・リファクタ・移行・デバッグなど、ファイル変更を伴う依頼で事前計画が必要なときに使う。
---

<!-- AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY. -->
<!-- source: docs/ai/canonical/playbooks/task-design-gate.md + scripts/sync_ai_context.py -->

# タスク設計ゲート

実装ファイルを編集する前に、必ず次の手順を実行する。

1. 依頼内容を 1 文で言い換える。
2. 関連コードと制約を調査する。
3. `docs/ai/playbook-assets/task-design-gate/references/_task-design-template.md` を読み、テンプレートを埋める。
4. 設計書を提示し、ユーザーに明示的な承認を求める。
5. 承認が出るまで、実装ファイルの編集を開始しない。
6. 承認NGまたは修正依頼があれば、設計書を更新して再確認する。

## ゲートルール

- 承認前に実装ファイルを編集しない。
- 承認前に許可されるのは、読み取り中心の調査コマンドのみとする。
- 永続化する計画メモの作成・更新は、ユーザーが明示的に求めた場合のみ許可する。
- `10. オープン事項 / 要確認` に未解消項目がある場合、ステータスを `保留(blocked)` にし、実装を開始しない。
- 承認後は合意済みスコープ内でのみ実装し、スコープ逸脱が発生したら即時に再合意を取る。

## 出力ルール

- `docs/ai/playbook-assets/task-design-gate/references/_task-design-template.md` の見出し順を厳守して Markdown で出力する。
- タスク設計書のメタデータには、`関連ゴールID` と `関連マイルストーンID` を必ず記載する。
- 各セクションはリポジトリ固有の具体内容で記載し、一般論を避ける。
- ファイルは必ず明示的なパスで列挙する。
- 少なくとも 1 つ以上のリスクと検証手順を含める。
- 保存先はリポジトリ配下の `docs/task-designs/` に固定する。
- `docs/task-designs/` が存在しない場合は作成してから保存する。
- 新規設計書のファイル名は `YYYYMMDDHHMMSS_{task-name}.md` とし、`YYYYMMDDHHMMSS` は初版作成日時（JST）を使う。
- `task-name` は英小文字の kebab-case を使う。
- 更新時はファイル名を変更せず、本文の `最終更新` のみ更新する。
- 作成時刻が不明な既存ドキュメントは `YYYYMMDD000000_{task-name}.md` を使う。
- `README.md` と `_task-design-template.md` は命名プレフィックス規則の例外とする。

## ハイブリッド運用（任意）

この運用をプロジェクト全体に常時適用したい依頼があれば、`docs/ai/playbook-assets/task-design-gate/references/agents-md-snippet.md` を参照し、`AGENTS.md` への追記を提案する。
