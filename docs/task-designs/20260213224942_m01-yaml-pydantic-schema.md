# タスク設計書: M-01 Graphyml YAML/Pydantic スキーマ定義

最終更新: 2026-02-13
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/product/goals.md`, `docs/product/milestones.md`, `docs/product/progress.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-01
- 関連マイルストーンID: M-01

## 0. TL;DR
- M-01 の目的に合わせて、Graphyml の YAML 定義を受ける Pydantic スキーマを新規実装する。
- `nodes / edges / params / start_at / end_at` を最小必須要素として定義し、分岐・ループを表現可能にする。
- スキーマ検証で、ノード重複・未定義ノード参照・開始/終了ノード不整合を実行前に検出する。
- 正常系/異常系の単体テストを追加し、M-01 の DoD（失敗ケースをテスト化）を満たす。

## 1. 背景 / 課題
- 現在の `src/graphyml/` は初期化直後の骨組みのみで、YAML 定義のドメインモデルが未実装。
- G-01 / M-01 で定義された「YAML を Pydantic で検証できる状態」を満たせていない。
- 先にスキーマ契約を確定しないと、M-02（Registry）/M-03（StateGraphビルダー）の入出力境界が不明確なまま進む。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- Graphyml YAML の最小契約を Pydantic モデルとして定義する。
- 分岐（条件付き edge）とループ（循環 edge）を許容する構造を持つ。
- YAML 読み込み前提で使える検証 API（dict 受け取り）を提供する。
- 不正入力を検出する単体テストを追加する。

### 2.2 非ゴール
- LangGraph `StateGraph` の組み立て実装は行わない（M-03で対応）。
- ノード実処理の Registry 解決は行わない（M-02で対応）。
- CLI 実行導線や外部 I/O アダプタ実装は行わない。

## 3. スコープ / 影響範囲
- 変更対象: `src/graphyml/domain/**`, `tests/unit/**`（必要に応じて `src/graphyml/application/**` に補助関数）。
- 影響範囲: YAML 契約の定義と検証失敗時のエラー形、M-02/M-03 の入力モデル。
- 互換性: 初回導入のため後方互換問題はない。
- 依存関係: `pydantic`（本番依存として追加）、`pytest`（既存）。

## 4. 要件
### 4.1 機能要件
- 下記トップレベル構造を受ける Pydantic モデルを提供する。
  - `version: str`
  - `start_at: str`
  - `end_at: list[str]`
  - `nodes: list[NodeSpec]`
  - `edges: list[EdgeSpec]`
  - `params: dict[str, Any]`（任意）
- `NodeSpec` は少なくとも `id`, `handler`, `params`（任意）を持つ。
- `EdgeSpec` は `source`, `target`, `condition`（任意）を持つ。
- バリデーションで以下を検出する。
  - ノードID重複
  - `start_at` / `end_at` が未定義ノードを指す
  - edge が未定義ノードを参照する
  - ノード/edge が空配列
- 分岐は `condition` によって表現可能であること。
- ループは循環 edge を許容すること（循環自体はエラーにしない）。

### 4.2 非機能要件 / 制約
- Pydantic v2 系で実装する。
- 型ヒント必須、`mypy` を通す。
- docstring は Google style（日本語説明）で記述する。
- 既存アーキテクチャ方針（Hexagonal）に従い、ドメインモデルを `domain` 配下へ配置する。

## 5. 仕様 / 設計
### 5.1 全体方針
- スキーマ契約は `domain` に閉じる。
- YAML パース（文字列→dict）は本タスク範囲外とし、検証入口は dict ベースにする。
- 今後の拡張（retry policy, timeout, metadata）を阻害しないよう、任意パラメータは `params` に集約する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/graphyml/domain/entities/graph_schema.py` | Graph/Node/Edge の Pydantic モデルを追加 | YAML 契約の正本化 | 新規 |
| `src/graphyml/domain/services/schema_validator.py` | 構造整合性チェック関数を追加 | 実行前エラー検出 | 新規 |
| `tests/unit/domain/test_graph_schema.py` | 正常系/異常系テストを追加 | M-01 DoD 達成 | 新規 |
| `pyproject.toml` | 本番依存に `pydantic` を追加 | ランタイム依存の確立 | 更新 |
| `docs/product/progress.md` | G01-I01 / G01-I03 の状態更新 | 進捗同期 | 更新（必要時） |

### 5.3 詳細
#### API
- 該当なし。

#### UI
- 該当なし。

#### データモデル / 永続化
- `GraphSpec`:
  - `version: str`
  - `start_at: str`
  - `end_at: list[str]`
  - `nodes: list[NodeSpec]`
  - `edges: list[EdgeSpec]`
  - `params: dict[str, Any] = {}`
- `NodeSpec`:
  - `id: str`
  - `handler: str`
  - `params: dict[str, Any] = {}`
- `EdgeSpec`:
  - `source: str`
  - `target: str`
  - `condition: str | None = None`

#### 設定 / 環境変数
- 追加なし。

### 5.4 代替案と不採用理由
- 代替案A: `TypedDict` + 手書き検証で実装する。
  - 不採用理由: エラー表現と拡張性が弱く、M-01 の「Pydantic で検証」の目的に反する。
- 代替案B: YAML 文字列を直接入力にした検証APIを先に作る。
  - 不採用理由: パース責務とスキーマ責務が混ざり、M-02/M-03 への再利用性が落ちる。

## 6. 移行 / ロールアウト
- フェーズ1: モデル実装（Node/Edge/Graph）。
- フェーズ2: 整合性チェック（参照整合・重複検出）。
- フェーズ3: 単体テスト追加と品質ゲート実行。
- ロールバック条件: 既存品質ゲート（ruff/mypy/pytest）が壊れる場合。
- ロールバック手順: 追加ファイルを取り消し、設計書を更新して再設計する。

## 7. テスト計画
- 単体:
  - 正常系: 分岐/ループを含む YAML 相当 dict を受理できる。
  - 異常系: ノード重複、未定義参照、空配列を検出できる。
- 結合: 該当なし（M-03で実施）。
- 手動: `uv run pytest -q`, `uv run mypy .`, `uv run ruff check .`。
- LLM/外部依存: 該当なし。
- 合格条件: 新規テストがすべて通過し、既存テストを壊さない。

## 8. 受け入れ基準
- `GraphSpec` / `NodeSpec` / `EdgeSpec` が実装されている。
- 正常系で分岐・ループを含む構成を受理できる。
- 異常系で重複・未定義参照を例外として返せる。
- `tests/unit/domain/test_graph_schema.py` の正常系/異常系が通る。
- `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q` が成功する。

## 9. リスク / 対策
- スキーマを厳しくしすぎて将来拡張を阻害するリスク。
  - 対策: 拡張ポイントを `params` に寄せ、必須項目を最小化する。
- エラーメッセージが利用者に不親切になるリスク。
  - 対策: 失敗ケースごとにテストで期待エラー文言を管理する。
- ループ許容の扱いが曖昧になるリスク。
  - 対策: 「循環は許容、未定義参照のみ禁止」を仕様として明記する。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] `pydantic` を本番依存へ追加する。
- [x] `GraphSpec` / `NodeSpec` / `EdgeSpec` を実装する。
- [x] 整合性検証ロジック（重複/参照整合）を実装する。
- [x] 正常系/異常系テストを追加する。
- [x] 品質ゲート（ruff/mypy/pytest）を通す。

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/product/progress.md`（状態更新が必要な場合）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-13 22:54
- 承認コメント: 「承認します」にて実装承認

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
