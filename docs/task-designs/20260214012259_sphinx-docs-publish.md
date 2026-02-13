# タスク設計書: Sphinxドキュメント公開基盤の導入

最終更新: 2026-02-14
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: docs / infra / backend
- 関連: `README.md`, `pyproject.toml`, `.github/workflows/ci.yml`, `.github/workflows/publish.yml`
- チケット/リンク: 該当なし
- 関連ゴールID: G-04
- 関連マイルストーンID: M-04

## 0. TL;DR
- Sphinx を導入し、Yagra の利用者向けドキュメントを静的サイトとして生成する。
- GitHub Actions でドキュメントビルドと GitHub Pages 公開を自動化する。
- Private リポジトリ運用を維持しつつ、成果物（Pages サイト）を公開可能にする運用手順を README に明記する。

## 1. 背景 / 課題
- 現在は README 中心の導線のみで、構造化されたドキュメントサイトがない。
- API/利用手順/設計上の契約を段階的に追加するための公開基盤が未整備。
- 既存 CI は lint/type/test のみで、ドキュメント生成の検証と公開パイプラインがない。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- Sphinx ベースのドキュメントビルド基盤を導入する。
- `main` 反映時に GitHub Actions で Pages へ公開できる状態にする。
- ローカルで `uv` 経由で同等ビルドを再現できるようにする。

### 2.2 非ゴール
- ドキュメント本文を大規模に作り込むこと（今回は最小構成）。
- Read the Docs など別ホスティング基盤への同時対応。
- API 内容やライブラリ挙動の変更。

## 3. スコープ / 影響範囲
- 変更対象:
  - `pyproject.toml`（Sphinx 関連 dev 依存追加）
  - `docs/sphinx/**`（Sphinx ソース/設定）
  - `.github/workflows/docs.yml`（新規: docs build & deploy）
  - `README.md`（ローカルビルド手順/公開 URL 導線）
- 影響範囲:
  - 開発者のローカルドキュメント作成フロー
  - GitHub Actions の追加実行
  - 公開サイト（GitHub Pages）
- 互換性:
  - ランタイムコードへの影響なし
- 依存関係:
  - GitHub Pages のリポジトリ設定（Source: GitHub Actions）
  - `uv` による dev 依存解決

## 4. 要件
### 4.1 機能要件
- Sphinx 基本構成を作成する。
  - `docs/sphinx/source/conf.py`
  - `docs/sphinx/source/index.md`（MyST Markdown）
  - `docs/sphinx/source/api.md`（API 参照の入口）
- API 参照ページを自動生成できる設定を入れる（`autodoc` / `autosummary`）。
- GitHub Actions で以下を行う workflow を追加する。
  - ドキュメントビルド
  - Pages artifact upload
  - Pages deploy
- README に以下を追記する。
  - ローカルビルドコマンド
  - 公開場所（GitHub Pages）
  - メンテナー向け公開条件

### 4.2 非機能要件 / 制約
- `uv add` を使って依存追加する（`pip install` 禁止）。
- 既存品質ゲート（ruff/mypy/pytest）を維持する。
- docs workflow は publish workflow と競合しない構成にする。

## 5. 仕様 / 設計
### 5.1 全体方針
- ドキュメントは Sphinx + MyST で作成し、Markdown を主に使える形にする。
- API 参照は `src/yagra` から自動抽出し、手動更新コストを抑える。
- 公開先は GitHub Pages（Actions Deploy）を採用する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `pyproject.toml` | Sphinx 関連の dev 依存追加 | 開発環境 | `uv add --group dev` で反映 |
| `docs/sphinx/source/conf.py` | Sphinx 設定追加（extensions/path/theme） | docs ビルド | 新規 |
| `docs/sphinx/source/index.md` | トップページ追加 | 公開サイト | 新規 |
| `docs/sphinx/source/api.md` | API 参照ページ追加 | 公開サイト | 新規 |
| `.github/workflows/docs.yml` | docs build/deploy workflow 追加 | CI/CD | 新規 |
| `README.md` | docs のローカル/公開手順追記 | 利用導線 | 更新 |

### 5.3 詳細
#### API
- 該当なし。

#### UI
- 該当なし（静的ドキュメントサイトのみ）。

#### データモデル / 永続化
- 該当なし。

#### 設定 / 環境変数
- GitHub Actions 権限:
  - `pages: write`
  - `id-token: write`
- docs workflow の `environment` は `github-pages` を使用。

### 5.4 代替案と不採用理由
- 代替案A: MkDocs で構築する。
  - 不採用理由: 今回要望が Sphinx 指定であり、API 自動参照も Sphinx が素直。
- 代替案B: README のみを拡張し、サイト公開は行わない。
  - 不採用理由: 「公開したい」要件を満たせない。

## 6. 移行 / ロールアウト
- 1) Sphinx 基本構成と依存追加
- 2) ローカルビルド確認
- 3) docs workflow 追加
- 4) README 更新
- 5) main 反映後、Pages 初回デプロイ確認
- ロールバック条件: docs workflow が恒常的に失敗し CI 運用へ悪影響が出る場合。
- ロールバック手順: docs workflow と Sphinx 設定追加分を取り消し、最小構成へ戻す。

## 7. テスト計画
- 単体: 該当なし
- 結合:
  - `uv run sphinx-build -b html docs/sphinx/source docs/sphinx/_build/html`
  - `uv run ruff check .`
  - `uv run mypy .`
  - `uv run pytest -q`
- 手動:
  - 生成された `docs/sphinx/_build/html/index.html` を開いて表示確認
  - GitHub Actions の docs workflow 成功確認
- LLM/外部依存: GitHub Pages 公開確認は GitHub 側 UI で実施
- 合格条件: ローカルビルド成功 + 既存品質ゲート成功 + docs workflow 設定妥当

## 8. 受け入れ基準
- `docs/sphinx/source/` に Sphinx プロジェクトが存在する。
- ローカルで Sphinx HTML ビルドが成功する。
- `.github/workflows/docs.yml` で Pages 公開フローが定義されている。
- README に docs ビルドと公開に関する説明がある。

## 9. リスク / 対策
- リスク: Private リポジトリ設定により Pages 公開が失敗する。
  - 対策: README に「Pages の Source を GitHub Actions に設定する」前提を明記し、失敗時の確認ポイントを示す。
- リスク: API 自動参照で import エラーが発生する。
  - 対策: `conf.py` で `src/` の path を明示し、最小限の参照対象に絞る。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] `uv add --group dev sphinx myst-parser furo` を実行して依存を追加する。
- [x] `docs/sphinx/source/` の Sphinx 構成ファイルを追加する。
- [x] `.github/workflows/docs.yml` を追加して Pages 公開フローを定義する。
- [x] README に docs ビルド/公開手順を追記する。
- [x] 品質ゲートと Sphinx ビルドを実行して検証する。

## 12. ドキュメント更新
- [x] `README.md`（docs 手順の追記）
- [ ] `AGENTS.md`（不要）
- [x] `docs/`（`docs/task-designs/*.md`, `docs/sphinx/**`）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-14
- 承認コメント: ok

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
