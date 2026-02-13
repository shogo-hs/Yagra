# codex-cursor-python-template

Codex と Cursor を併用する Python プロジェクト向けのテンプレート。

## 目的

- AI 向け運用ルールの二重管理を防ぐ。
- `AGENTS.md`（Codex）と `.cursor/rules/*.mdc`（Cursor）を同じ正本から生成する。
- 手順本文を `docs/ai/canonical/playbooks/` に集約し、実行時は `docs/ai/playbooks/*.md` を参照する。
- 参照資料と補助スクリプトを repo 同梱で管理し、チーム再現性を確保する。

## 構成

```text
.
├── AGENTS.md                             # 自動生成
├── .cursor/rules/*.mdc                   # 自動生成
├── docs/ai/canonical/*.md                # 正本（手動編集）
├── docs/ai/canonical/playbooks/*.md      # Playbook手順の正本（手動編集）
├── docs/ai/playbooks/*.md                # 自動生成（実行時の参照先）
├── docs/ai/playbook-assets/**            # 参照資料（手動編集）
├── docs/product/*.md                     # プロダクト方針・目標・進捗の正本（手動編集）
├── scripts/playbooks/**                  # 補助スクリプト（手動編集）
├── scripts/sync_ai_context.py            # 生成/検証
├── scripts/bootstrap_after_canonical.py  # 同期後ブートストラップ
└── .github/workflows/ai-context-sync.yml
```

## 同梱Playbook一覧

- `task-design-gate`
- `python-uv-ci-setup`
- `python-project-bootstrap`
- `api-spec-sync`
- `adr-management`
- `git-commit`

## 更新方針

- ルール本文は `docs/ai/canonical/` と `docs/ai/canonical/playbooks/` だけを編集する。
- `docs/ai/playbooks/*.md`、`AGENTS.md`、`.cursor/rules/*.mdc` は自動生成物として直接編集しない。
- Playbook の参照資料は `docs/ai/playbook-assets/`、補助スクリプトは `scripts/playbooks/` を正本とする。

## プロダクト方針と進捗管理

- プロダクト方針の正本は `docs/product/` に置く。
- 各タスク設計は `関連ゴールID` / `関連マイルストーンID` を明記し、日々の実装をユーザー到達状態へ接続する。
- テンプレート利用開始時は、`python-project-bootstrap` の初期対話で `docs/product/*.md` をユーザーと擦り合わせて埋める。

`docs/product/` の役割:

- `docs/product/vision.md`: 最終的に目指す状態、対象ユーザー、再設定ルール
- `docs/product/goals.md`: ユーザー到達状態ゴール（Goal ID）と到達判定
- `docs/product/milestones.md`: 到達ステップ（Milestone ID）
- `docs/product/progress.md`: やるべきこと一覧、完了済み、未完了、現在地

## README と AGENTS の書き分け

| 書く場所 | 主な読者 | 記載する内容 | 記載しない内容 |
| --- | --- | --- | --- |
| `README.md` | 人間（開発者・利用者） | プロジェクト概要、構成、導入手順、運用導線 | エージェント向けの詳細実行規約 |
| `AGENTS.md` | AIエージェント | 実行時に守るルール、タスクルーティング、品質ゲート | 人向けの背景説明や長いオンボーディング解説 |

- エージェント向けの運用ルールを変更する場合は、`AGENTS.md` を直接編集せず `docs/ai/canonical/*.md` を更新して再生成する。
- ルーティングと実行手順は `AGENTS.md` から `docs/ai/playbooks/*.md` を参照する。

## 運用ルール

1. 必要な正本（canonical / playbook-assets / scripts/playbooks）を編集する。
2. `python3 scripts/sync_ai_context.py` を実行して生成物を更新する。
3. `python3 scripts/sync_ai_context.py --check` で drift がないことを確認する。
4. PR では CI の `AI Context Sync` チェックを必須にする。

## クイックスタート

```bash
python3 scripts/sync_ai_context.py
python3 scripts/sync_ai_context.py --check
```

## 役割分担（誰が何をするか）

| 区分 | ユーザー | エージェント |
| --- | --- | --- |
| 意思決定 | Vision、優先順位、受け入れ可否を決める | 判断材料を整理し、選択肢を提示する |
| 実作業 | 回答・承認・最終判断を行う | コマンド実行、ファイル編集、検証、差分整理を行う |
| リリース導線 | `commit` / `push` / `PR` 実行を依頼する | 依頼された Git 操作を実行し、結果を報告する |

## 新規立ち上げフロー（実行者つき）

| Step | ユーザーがやること | エージェントがやること | 成果物 |
| --- | --- | --- | --- |
| 1 | テンプレートから新規リポジトリを作成し clone する | 該当なし | ローカル作業ディレクトリ |
| 2 | 「初期化を進めて」と依頼する | `sync_ai_context.py --check` と bootstrap を実行する | 初期ファイル一式 |
| 3 | `docs/product` 擦り合わせ質問に回答する | `product-docs-alignment` に沿って 1〜3 問ずつ進行し、回答を反映する | `docs/product/*.md` 初期確定 |
| 4 | 開発タスクを依頼する | `docs/task-designs` に設計書を作成し、承認待ちにする | タスク設計書 |
| 5 | 設計内容を承認する | 実装・検証・差分説明を行う | 実装差分 |
| 6 | `commit & push` / `PR作成` を依頼する | Git 操作を実行し、URL/結果を共有する | PR |

## 新しいプロジェクトの立ち上げ手順

1. テンプレートから新規リポジトリを作成し、ローカルへ clone する。
2. `docs/ai/canonical/*.md` と `docs/ai/canonical/playbooks/*.md` をプロジェクト方針に合わせて編集する。
3. 反映確認を実行する。
   ```bash
   python3 scripts/sync_ai_context.py
   python3 scripts/sync_ai_context.py --check
   ```
4. 初期化をまとめて実行する。
   ```bash
   python3 scripts/bootstrap_after_canonical.py \
     --project-name "<project-name>" \
     --description "<project-description>" \
     --task-design-dir "docs/task-designs"
   ```

`bootstrap_after_canonical.py` は安全のため、`sync_ai_context.py` と `--check` を再実行してから
`python-project-bootstrap` 用の補助スクリプトを呼び出す。

### 立ち上げ直後に必ず行うこと（必須）

- CI 設定は必須。`python-uv-ci-setup` Playbook を使って `.pre-commit-config.yaml` と `.github/workflows/ci.yml` を整備する。
- 手順正本は `<repo>/docs/ai/canonical/playbooks/` に固定し、生成物をコミット管理する。

## Symlink について

- 既定運用では symlink を使わない。
- 理由: OS/Git 設定差（例: `core.symlinks`）でチーム運用が不安定になりうるため。
- 必要な場合のみローカル実験として利用し、チーム標準は同期スクリプト方式を維持する。

## Codex + Cursor 併用ポリシー

- 実行導線は `AGENTS.md` と `.cursor/rules/*.mdc` に統一する。
- 詳細手順は `docs/ai/playbooks/*.md` を共通参照先にする。
- 正本更新後は必ず `sync_ai_context.py` で再生成し、`--check` を通す。
