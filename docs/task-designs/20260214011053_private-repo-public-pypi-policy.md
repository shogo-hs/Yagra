# タスク設計書: Privateリポジトリ運用とPyPI公開方針の反映

最終更新: 2026-02-14
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: docs / infra / backend
- 関連: `README.md`, `pyproject.toml`, `.github/workflows/publish.yml`, `docs/product/progress.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-04
- 関連マイルストーンID: M-04

## 0. TL;DR
- GitHub リポジトリを Private のまま維持し、PyPI 配布物のみ Public とする運用方針を正式反映する。
- README を「利用者向け導線（`pip install yagra`）」優先へ再整理し、開発者向け clone 手順はメンテナー向けとして分離する。
- `pyproject.toml` の `project.urls` を公開利用者視点で矛盾しない値へ見直す。

## 1. 背景 / 課題
- 方針として「リポジトリ非公開・成果物公開」が確定した。
- 現状 README 先頭が clone 手順中心で、PyPI 利用者が最初に必要な導線が弱い。
- `project.urls` が private URL のみだと PyPI 公開ページ上で利用者が参照不能となる可能性がある。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- README に Private repo / Public PyPI 方針を明記する。
- README 先頭導線を `pip install yagra` 起点へ変更する。
- `pyproject.toml` の公開メタデータを方針と整合させる。

### 2.2 非ゴール
- GitHub リポジトリの可視性変更（Private→Public）。
- ライブラリ API・挙動の変更。
- PyPI Web UI 上の操作（Trusted Publisher 設定そのもの）。

## 3. スコープ / 影響範囲
- 変更対象: `README.md`, `pyproject.toml`, 必要に応じて `docs/product/progress.md`。
- 影響範囲: 公開ドキュメント導線、PyPI メタデータ表示、リリース運用の明確性。
- 互換性: ランタイム互換性への影響なし（ドキュメント/メタデータ中心）。
- 依存関係: GitHub Actions publish workflow（`.github/workflows/publish.yml`）との整合確認。

## 4. 要件
### 4.1 機能要件
- README:
  - 利用者向けインストール手順を先頭に配置する。
  - メンテナー向け開発セットアップを分離し、private repo アクセス前提を明記する。
  - Private repo / Public PyPI の運用方針を明文化する。
- `pyproject.toml`:
  - `project.urls` を公開利用者にとって矛盾しない公開可能 URL 構成に更新する。
- 公開手順:
  - Trusted Publisher が private の当該 repo を対象とする運用であることを README に明記する。

### 4.2 非機能要件 / 制約
- 既存品質ゲート（ruff/mypy/pytest）を維持する。
- README は人間向け入口として過不足なく簡潔に保つ。

## 5. 仕様 / 設計
### 5.1 全体方針
- 公開利用者は PyPI 経由で導入できることを最優先に見せる。
- 開発者向け情報は「メンテナー向け」に分離し、アクセス前提を明示する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `README.md` | 導線を `pip install` 優先へ再構成、運用方針を明記 | 公開面の誤解防止 | 更新 |
| `pyproject.toml` | `project.urls` を公開前提で見直し | PyPI 表示整合 | 更新 |
| `docs/product/progress.md` | 方針反映の記録を追記（必要時） | 進捗追跡 | 任意更新 |

### 5.3 詳細
#### API
- 該当なし。

#### UI
- 該当なし。

#### データモデル / 永続化
- 該当なし。

#### 設定 / 環境変数
- 該当なし（既存 publish workflow の運用説明のみ更新）。

### 5.4 代替案と不採用理由
- 代替案A: README を現状維持し、利用者には private repo 参照を許容する。
  - 不採用理由: Public PyPI 利用者の初期体験として不親切で混乱を招く。
- 代替案B: `project.urls` を private repo URL のまま維持する。
  - 不採用理由: 公開ページ上でアクセス不能リンクが並び、信頼性を損なう。

## 6. 移行 / ロールアウト
- 1) README 更新
- 2) `pyproject.toml` 更新
- 3) 必要に応じ進捗ドキュメント更新
- ロールバック条件: README 導線や URL メタデータに齟齬がある場合。
- ロールバック手順: 当該コミットを戻し、記述を最小修正して再適用する。

## 7. テスト計画
- 単体: `uv run pytest -q`
- 結合: `uv build` と `uvx twine check dist/*`
- 手動: README の先頭導線と公開方針記述を目視確認
- LLM/外部依存: Trusted Publisher 設定は外部 UI 手動確認対象
- 合格条件: `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q`, `uv build`, `uvx twine check dist/*` が成功

## 8. 受け入れ基準
- README で Private repo / Public PyPI 方針が明確に読める。
- README の先頭導線が `pip install yagra` になっている。
- `pyproject.toml` の `project.urls` が公開利用者視点で矛盾しない。
- 品質ゲートと配布検証が成功する。

## 9. リスク / 対策
- リスク: メンテナー向け情報が薄くなり内部運用が迷う。
  - 対策: README 内にメンテナー向けセクションを残す。
- リスク: 公開方針の記述と実際の publish 設定がずれる。
  - 対策: `.github/workflows/publish.yml` と README を同時に読み合わせる。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] README を Public PyPI 利用導線へ再構成する。
- [x] `pyproject.toml` の `project.urls` を方針整合へ更新する。
- [x] 必要に応じ `docs/product/progress.md` を更新する。
- [x] 品質ゲートと配布検証を実行する。

## 12. ドキュメント更新
- [x] `README.md`（予定）
- [ ] `AGENTS.md`（不要見込み）
- [x] `docs/`（`docs/task-designs/*.md`, 必要時 `docs/product/progress.md`）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-14
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
