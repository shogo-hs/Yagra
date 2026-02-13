# タスク設計書: G03-I03 と G04-I03 の完了対応

最終更新: 2026-02-13
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: docs / infra
- 関連: `README.md`, `.pre-commit-config.yaml`, `docs/product/goals.md`, `docs/product/milestones.md`, `docs/product/progress.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-03, G-04
- 関連マイルストーンID: M-03, M-04

## 0. TL;DR
- `G03-I03` と `G04-I03` を同時に完了させるため、README の利用例追記とローカルフック運用の確定を行う。
- README には `Graphyml.from_workflow(...)` を使った Zero-Boilerplate 実行例を追加する。
- pre-commit/pre-push は `uv run pre-commit install --hook-type pre-commit --hook-type pre-push` を実行し、`pre-commit run --all-files` で運用可能状態を確認する。
- 完了後は product ドキュメントの状態を `Done` へ更新し、整合を保つ。

## 1. 背景 / 課題
- `docs/product/progress.md` で `G03-I03` は Planned のまま、README に利用者向けの具体的な実行例が不足している。
- `G04-I03` は In Progress で、`.pre-commit-config.yaml` は存在するがローカル導入完了を示す実行結果が未確定。
- これらが未完了のままだと、ライブラリ利用導線と開発品質ゲート運用の両方で「使える状態」の証跡が弱い。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- README に Zero-Boilerplate 利用例を追加し、YAML差し替え実行の最短導線を提示する。
- pre-commit / pre-push フックをローカルへ導入し、品質ゲートを手元で常時実行できる状態にする。
- `G03-I03` と `G04-I03` を `Done` へ更新し、必要に応じて `G-03`, `G-04`, `M-04` の状態も整合させる。

### 2.2 非ゴール
- 新しいワークフロー構築機能や Registry 機能の実装は行わない。
- CI ワークフロー自体の新規設計・大幅変更は行わない。
- AGENTS/Playbook 正本の運用ルール変更は行わない。

## 3. スコープ / 影響範囲
- 変更対象: `README.md`, `docs/product/goals.md`, `docs/product/milestones.md`, `docs/product/progress.md`。
- 実行対象: ローカル環境での `uv run pre-commit install ...`, `uv run pre-commit run --all-files`。
- 影響範囲: 利用者オンボーディング、ローカル開発時の品質ゲート運用。
- 互換性: コード実装の挙動互換性への影響はなし（ドキュメント/運用更新中心）。
- 依存関係: 既存 `Graphyml` API、`.pre-commit-config.yaml`、`uv`。

## 4. 要件
### 4.1 機能要件
- README に以下を含む利用例を追加する。
  - 依存同期手順（`uv sync --dev`）
  - `InMemoryNodeRegistry` へ handler 登録
  - `Graphyml.from_workflow(...)` でのインスタンス化
  - `invoke(...)` 実行例
- ローカルフック導入コマンドを実行し、成功を確認する。
- `pre-commit run --all-files` が通ることを確認する。
- progress/goals/milestones の状態を完了結果に合わせて更新する。

### 4.2 非機能要件 / 制約
- README は人間向け導線に限定し、エージェント実行規約は記載しない。
- 既存セクション構造を大きく崩さず、差分最小で追記する。
- ドキュメント更新は表記ゆれ（Done/In Progress）を残さない。

## 5. 仕様 / 設計
### 5.1 全体方針
- 既存公開 API をそのまま使った最小実例を README に示す。
- フック導入は設定ファイル変更ではなく「導入実行 + 検証結果」で完了を定義する。
- 完了判定は `progress.md` の Item 状態に連動して更新する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `README.md` | Zero-Boilerplate の実行サンプルを追加 | 利用導線の明確化 | `Graphyml.from_workflow(...)` を明記 |
| `docs/product/progress.md` | `G03-I03` と `G04-I03` を `Done` へ更新 | 進捗同期 | 現在地文言も更新 |
| `docs/product/goals.md` | `G-03` と `G-04` の状態を見直し | Goal整合 | 完了条件充足時は `Done` |
| `docs/product/milestones.md` | `M-04` 状態を見直し | マイルストーン整合 | G04-I03完了時に `Done` |

### 5.3 詳細
#### API
- 利用例で使う公開 API は `graphyml.Graphyml.from_workflow` と `graphyml.Graphyml.invoke`。

#### UI
- 該当なし。

#### データモデル / 永続化
- 該当なし。

#### 設定 / 環境変数
- 追加なし。

### 5.4 代替案と不採用理由
- 代替案A: README に文章説明のみ追加し、コード例を載せない。
  - 不採用理由: ライブラリ利用者の初回実行コストが高いままになる。
- 代替案B: pre-commit 導入は実行せず、手順記述だけで完了とする。
  - 不採用理由: `G04-I03` の「導入完了」証跡が不足する。

## 6. 移行 / ロールアウト
- README 追記 → フック導入コマンド実行 → 全ファイルフック実行 → progress/goals/milestones 更新の順で実施。
- ロールバック条件: フック導入や品質ゲート実行で恒常的失敗が発生し、既存開発フローを阻害する場合。
- ロールバック手順: 追加ドキュメント差分を戻し、失敗原因と再実行条件を設計書へ追記する。

## 7. テスト計画
- 単体: 既存テストを再実行して回帰がないことを確認する（`uv run pytest -q`）。
- 結合: `uv run pre-commit run --all-files` を実行し、format/lint/type/test が連動して通ることを確認する。
- 手動: README のコード例と現在 API を突き合わせ、参照パスが実在することを確認する。
- LLM/外部依存: 該当なし。
- 合格条件: pre-commit と pytest が成功し、進捗ドキュメント状態が矛盾しない。

## 8. 受け入れ基準
- `README.md` に Zero-Boilerplate の具体的実行例が追加されている。
- `uv run pre-commit install --hook-type pre-commit --hook-type pre-push` が成功している。
- `uv run pre-commit run --all-files` が成功している。
- `docs/product/progress.md` の `G03-I03` と `G04-I03` が `Done`。
- 関連する Goal/Milestone の状態が矛盾なく更新されている。

## 9. リスク / 対策
- リスク: README 例が現行 API と不一致になる。
  - 対策: `src/graphyml/__init__.py` と `adapters/outbound` の公開シンボル名を確認して記載する。
- リスク: pre-push で `pytest` 実行が重く、開発体験が低下する。
  - 対策: まず現行設計を維持して運用を確定し、重さが課題化した時点で別タスクで段階最適化する。
- リスク: 状態更新漏れで docs 間矛盾が再発する。
  - 対策: 更新後に `rg` で `G-03/G-04/M-04/G03-I03/G04-I03` を横断確認する。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] README に Zero-Boilerplate 利用例を追記する。
- [x] pre-commit/pre-push フックをローカルへ導入する。
- [x] `uv run pre-commit run --all-files` を実行して成功を確認する。
- [x] `docs/product/progress.md` の G03-I03/G04-I03 を更新する。
- [x] 必要な Goal/Milestone 状態を更新し整合を確認する。

## 12. ドキュメント更新
- [x] `README.md`（利用例を追加）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/`（`docs/product/*.md`, `docs/task-designs/*.md` を更新）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-13 23:41
- 承認コメント: 「OK」にて承認

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
