# タスク設計書: PyPI 公開ワークフロー整備

最終更新: 2026-02-14
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: infra / docs
- 関連: `.github/workflows/ci.yml`, `pyproject.toml`, `CHANGELOG.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-04
- 関連マイルストーンID: M-04

## 0. TL;DR
- PyPI 向けの公開導線を整えるため、`publish.yml` を追加する。
- トリガーは Git タグ公開（`v*`）とし、build → twine check → pypi publish を実行する。
- 既存の品質ゲート（CI）は維持し、公開処理は別ワークフローへ分離する。
- 公開実行前提（PyPI Trusted Publisher 設定）は README へ短く明記する。

## 1. 背景 / 課題
- 現在は lint/type/test の CI はあるが、配布先（PyPI）への公開フローが未整備。
- 手動公開のみだと再現性と監査性が低く、リリース時の手順漏れリスクが高い。
- `pyproject.toml` は配布メタデータを満たしたため、次は公開の自動化が妥当。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- `.github/workflows/publish.yml` を追加し、タグベースで公開可能にする。
- 公開前に build アーティファクト検証（twine check）を通す。
- 公開前提条件（PyPI 側設定）を README に明記する。

### 2.2 非ゴール
- PyPI 側の Trusted Publisher 設定自体は行わない（リポジトリ外作業）。
- 版数自動更新や changelog 自動生成は行わない。
- TestPyPI への二重公開フローは今回作らない。

## 3. スコープ / 影響範囲
- 変更対象: `.github/workflows/publish.yml`, `README.md`（公開手順追記）
- 影響範囲: リリース運用、公開手順の再現性
- 互換性: ランタイムコードへの影響なし
- 依存関係: GitHub OIDC、PyPI Trusted Publisher、`uv build`

## 4. 要件
### 4.1 機能要件
- `publish.yml` のトリガー:
  - `push.tags: ["v*"]`
  - 任意で `workflow_dispatch`
- ジョブ内手順:
  - Python / uv セットアップ
  - `uv build`
  - `uv run twine check dist/*`
  - `pypa/gh-action-pypi-publish` で publish（OIDC）
- 必要権限:
  - `id-token: write`
- README に「公開前提（PyPI Trusted Publisher 設定）」を明記。

### 4.2 非機能要件 / 制約
- Secrets に API トークンを置かない（OIDC Trusted Publisher 前提）。
- 既存 CI と責務を分離し、publish ワークフローは公開時のみ実行。
- YAML は既存ワークフロー記法と整合する。

## 5. 仕様 / 設計
### 5.1 全体方針
- リリース公開処理を専用 workflow に分離して可視化する。
- 公開直前の artifact 妥当性確認を必須化する。
- 人手での操作は「タグ作成」までに限定する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `.github/workflows/publish.yml` | PyPI 公開用 workflow を追加 | リリース導線の自動化 | 新規 |
| `README.md` | 公開前提条件（Trusted Publisher）を追記 | 運用明確化 | 更新 |

### 5.3 詳細
#### API
- 該当なし。

#### UI
- 該当なし。

#### データモデル / 永続化
- 該当なし。

#### 設定 / 環境変数
- GitHub Actions の OIDC 権限 (`id-token: write`) を利用。
- PyPI 側に対象リポジトリの Trusted Publisher 登録が必要。

### 5.4 代替案と不採用理由
- 代替案A: 手動 `uv build` + `twine upload` のみで運用。
  - 不採用理由: 再現性・監査性が低く、人的ミスリスクが高い。
- 代替案B: TestPyPI と本番 PyPI の2段公開を同時導入。
  - 不採用理由: 初回導入としては複雑で、運用負荷が上がる。

## 6. 移行 / ロールアウト
- `publish.yml` 追加 → README追記 → 手動実行（dry-run相当）確認。
- ロールバック条件: workflow 記述不備でリリースフローが停止した場合。
- ロールバック手順: `publish.yml` を一時無効化し、問題行を修正して再有効化。

## 7. テスト計画
- 単体: 該当なし。
- 結合: GitHub Actions の workflow 構文と実行ログ確認（実公開はタグ時）。
- 手動: `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q`。
- LLM/外部依存: PyPI 側設定は手動確認。
- 合格条件: ローカル品質ゲート成功、workflow 構文が妥当、README に前提が明記される。

## 8. 受け入れ基準
- `.github/workflows/publish.yml` が追加されている。
- タグ push で PyPI 公開ジョブが起動する定義になっている。
- publish 前に `twine check` が実行される。
- README に Trusted Publisher 前提が記載されている。

## 9. リスク / 対策
- リスク: PyPI Trusted Publisher 未設定で publish 失敗。
  - 対策: README に前提手順を明記し、失敗時の確認ポイントを簡潔に記載する。
- リスク: タグ誤発行で意図しない公開が走る。
  - 対策: `v*` タグ運用ルールを固定し、レビュー後のみタグ作成する。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] `.github/workflows/publish.yml` を追加する。
- [x] README に公開前提（Trusted Publisher）を追記する。
- [x] 品質ゲート（ruff/mypy/pytest）を実行する。

## 12. ドキュメント更新
- [x] `README.md`（公開前提追記）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/`（`docs/task-designs/*.md`）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-14 00:41
- 承認コメント: 「OK.」

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
