# タスク設計書: yagra への改名と公開フロー強化

最終更新: 2026-02-14
- ステータス: 完了(completed)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / infra / docs
- 関連: `pyproject.toml`, `src/graphyml/**`, `.github/workflows/publish.yml`, `README.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-03, G-04
- 関連マイルストーンID: M-03, M-04

## 0. TL;DR
- プロジェクト名とライブラリ名を `yagra`（YAml + GRAph）へ統一する。
- パッケージモジュールを `src/graphyml` から `src/yagra` へ改名し、公開 API も `Yagra` 名へ揃える。
- PyPI 公開の安全性向上として、`publish.yml` に「タグ名と `pyproject` 版数一致チェック」を追加する。
- Trusted Publisher 前提を README に明示し、公開時の事故リスクを下げる。

## 1. 背景 / 課題
- 現在の名称（Graphyml）を `yagra` に統一したい要望がある。
- 既存 publish workflow はタグ push で公開できるが、タグと版数不一致の検出がない。
- Trusted Publisher 未設定時の失敗ポイントは README にあるが、公開手順の前提をさらに明確化する余地がある。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- `pip install` 対象のパッケージ名を `yagra` に変更する。
- `import yagra` で利用できる状態にする。
- 公開 API 名を `Yagra` に統一する。
- publish workflow に版数整合チェックを入れる。
- README を新名称と公開前提に合わせて更新する。

### 2.2 非ゴール
- GitHub リポジトリ名そのものの変更（`Graphyml` -> `yagra`）は行わない。
- PyPI の Trusted Publisher 設定作業（外部サービス側操作）は行わない。
- 新機能（DSL 拡張、実行ロジック変更）の追加は行わない。

## 3. スコープ / 影響範囲
- 変更対象:
  - `pyproject.toml`
  - `src/graphyml/**` -> `src/yagra/**`（ディレクトリ改名 + import 書き換え）
  - `tests/**`（import 更新）
  - `.github/workflows/publish.yml`
  - `README.md`, `CHANGELOG.md`, 必要な docs
- 影響範囲:
  - import パス
  - 配布名（wheel/sdist 名）
  - 公開 workflow の失敗条件

## 4. 要件
### 4.1 機能要件
- `pyproject.toml`:
  - `[project].name = "yagra"`
  - `[project.scripts]` を `yagra = "yagra:main"` へ変更
- ソース改名:
  - `src/graphyml/` を `src/yagra/` へ移行
  - import 文を `from yagra...` へ変更
- 公開 API:
  - `class Yagra` を提供
- publish workflow:
  - タグ `vX.Y.Z` と `pyproject.toml` の `version` 一致をチェック
  - 不一致時は publish せず fail
- README:
  - 名称を `yagra` へ更新
  - Trusted Publisher 前提とタグ運用（版数一致）を明記

### 4.2 非機能要件 / 制約
- 既存品質ゲート（ruff/mypy/pytest）を通す。
- 大量置換に伴う誤置換を避けるため、差分確認を段階的に行う。
- 既存挙動（workflow 実行結果）を変えない。

## 5. 仕様 / 設計
### 5.1 全体方針
- まずモジュール名を `yagra` に移行し、テストを通して import 破壊を解消する。
- 次に公開系（pyproject/publish/README）を更新する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/yagra/**` | モジュール改名と import 更新 | import パス変更 | `src/graphyml` から移行 |
| `src/yagra/__init__.py` | `Yagra` を公開 API として提供 | API 表記改善 | 更新 |
| `tests/**` | `graphyml` import を `yagra` に更新 | テスト整合 | 更新 |
| `pyproject.toml` | package 名/entrypoint を `yagra` 化 | 配布名変更 | 更新 |
| `.github/workflows/publish.yml` | タグ/版数一致チェック追加 | 公開安全性向上 | 更新 |
| `README.md` | 名称更新と公開手順更新 | 利用導線整合 | 更新 |
| `CHANGELOG.md` | 改名変更履歴追記 | 変更履歴整備 | 更新 |

### 5.3 詳細
#### API
- 追加/変更:
  - `class Yagra`（新名称）

#### UI
- 該当なし。

#### データモデル / 永続化
- 該当なし。

#### 設定 / 環境変数
- publish workflow 内で tag/version 一致判定を shell で実施。

### 5.4 代替案と不採用理由
- 代替案A: パッケージ名だけ `yagra` に変え、モジュール名は `graphyml` のまま維持。
  - 不採用理由: import 名と配布名がずれ、利用者に混乱を招く。

## 6. 移行 / ロールアウト
- 1) モジュール改名 + import 修正
- 2) API 名称を `Yagra` へ統一
- 3) pyproject/publish/README 更新
- 4) 品質ゲート実行
- ロールバック条件: import 破壊や公開設定不備が発生した場合。
- ロールバック手順: 変更をコミット単位で戻し、原因箇所を最小修正して再適用。

## 7. テスト計画
- 単体: 既存 unit/integration を全実行。
- 結合: `uv build` と `uvx twine check dist/*` を実行。
- 手動: `import yagra` / `from yagra import Yagra` 動作確認。
- LLM/外部依存: PyPI 側 Trusted Publisher は手動確認。
- 合格条件: `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q`, `uv build`, `uvx twine check` が成功。

## 8. 受け入れ基準
- `pyproject.toml` の配布名と entrypoint が `yagra` になっている。
- ソース/テストの import が `yagra` 基準で通る。
- `Yagra` クラスが公開 API として提供される。
- publish workflow に tag/version 一致チェックがある。
- README が新名称と公開前提に整合している。

## 9. リスク / 対策
- リスク: 改名範囲が広く import 漏れが出る。
  - 対策: `rg` で `graphyml` 残存箇所を全件確認し、段階的に修正する。
- リスク: PyPI 上で `yagra` 名が取得済みに変わる可能性。
  - 対策: 公開直前に `https://pypi.org/pypi/yagra/json` を再確認する。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] `src/graphyml` を `src/yagra` へ移行し、import を更新する。
- [x] `Yagra` を公開 API 名として実装する。
- [x] `pyproject.toml` の配布名/entrypoint を `yagra` へ更新する。
- [x] `publish.yml` に tag/version 一致チェックを追加する。
- [x] README/CHANGELOG を `yagra` 名へ更新し、公開前提を明確化する。
- [x] 品質ゲートと配布検証（build/twine）を実行する。

## 12. ドキュメント更新
- [x] `README.md`（名称/公開手順更新）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/`（`docs/task-designs/*.md`）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-14
- 承認コメント: 実装フェーズ開始を承認（DX 最優先、`state_schema` 重視、README の契約明文化を重視）。

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
