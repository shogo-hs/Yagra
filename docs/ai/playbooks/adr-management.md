---
name: adr-management
description: 設計判断（アーキテクチャ、運用ルール、依存方針など）の採否を ADR として記録・更新し、変更理由を追跡可能にするためのPlaybook。方針の新規決定、方針変更、既存判断の置換が発生したときに使う。
---

<!-- AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY. -->
<!-- source: docs/ai/canonical/playbooks/adr-management.md + scripts/sync_ai_context.py -->

# ADR管理

設計判断を文章化し、後から採否理由を追跡できる状態を維持する。

## 実行手順

1. 判断対象を明確化する。
- 対象となる方針（例: アーキテクチャ、ツール選定、運用ルール）を 1 つに絞る。
- 影響範囲（コード、CI、運用、ドキュメント）を整理する。

2. 既存 ADR を確認する。
- `docs/adr/README.md` の一覧を確認し、重複や置換関係がないかを調べる。
- 既存判断を置換する場合は、旧ADRのステータスを `置換済み(superseded)` に更新する。

3. ADR を作成または更新する。
- 新規作成時は `docs/ai/playbook-assets/adr-management/references/_adr-template.md` を使用する。
- 保存先は `docs/adr/`、ファイル名は `NNNN-short-title.md`（4桁連番 + kebab-case）を使う。
- 本文には「文脈」「決定」「代替案」「影響」「フォローアップ」を必ず記載する。

4. 関連ドキュメントを同期する。
- 方針変更が `AGENTS.md` / Playbook / README / CI 設定へ影響する場合は同一タスクで更新する。
- 変更理由が追跡できるように、関連ファイルから ADR への参照を追加する。

5. レビュー観点を明示する。
- トレードオフが比較可能か。
- 非採用案の却下理由が具体的か。
- 追加コスト（移行、教育、運用）を説明しているか。

6. 結果を報告する。
- 追加/更新した ADR ファイル。
- 置換した ADR（ある場合）。
- 同時に更新した実装・ドキュメントファイル。

## 運用ルール

- 重要な設計判断は、口頭・チャットだけで完結させず ADR に残す。
- 1ADR に複数の無関係な判断を混在させない。
- ステータスは `提案(proposed)` / `承認済み(accepted)` / `却下(rejected)` / `置換済み(superseded)` を使用する。
- 置換関係がある場合は、新旧 ADR の双方に相互リンクを張る。

## 参照ファイル

- ADRテンプレート: `docs/ai/playbook-assets/adr-management/references/_adr-template.md`
- ADR一覧: `docs/adr/README.md`
