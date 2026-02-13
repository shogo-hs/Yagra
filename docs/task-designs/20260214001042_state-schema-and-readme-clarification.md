# タスク設計書: StateSchema対応とREADME仕様明確化

最終更新: 2026-02-14
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `src/graphyml/__init__.py`, `src/graphyml/application/use_cases/state_graph_builder.py`, `README.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-02, G-03
- 関連マイルストーンID: M-02, M-03

## 0. TL;DR
- ユーザーFBで指摘された導入障壁を解消するため、API機能追加とREADME仕様明確化を同時に行う。
- `Graphyml.from_workflow(...)` に `state_schema` と `dict` レジストリ受け取りを追加する。
- 条件分岐・catalog解決・`end_at` 挙動を README に明示し、Quick Start を分岐付き例へ改訂する。
- 既存挙動との後方互換を維持しつつ、テストで新仕様を担保する。

## 1. 背景 / 課題
- 現状は `StateGraph(dict)` 固定で、State 型を明示した LangGraph 的な利用体験が README から見えない。
- `InMemoryNodeRegistry` を必須前提にしており、簡易利用時に API が冗長に見える。
- 条件分岐の実行契約（`__next__`）や `prompt_ref`/`model_ref` 解決後に handler が受け取る値が README で説明不足。
- `end_at` が LangGraph `END` とどう関係するか不明で、挙動誤解を招く。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- `state_schema` を指定可能にし、TypedDict/Pydantic の State でグラフ構築できる。
- `registry` に `dict[str, callable]` を直接渡せる。
- README で分岐契約・catalog解決・`end_at` の挙動を明確化する。
- 新仕様をテストで検証する。

### 2.2 非ゴール
- YAML DSL を `branches` 形式へ刷新する（現行 `condition` + `__next__` 契約は維持）。
- LangGraph の全機能（reducers など）を Graphyml API に完全露出する。
- 既存 YAML スキーマ自体の破壊的変更。

## 3. スコープ / 影響範囲
- 変更対象:
  - `src/graphyml/__init__.py`
  - `src/graphyml/application/use_cases/state_graph_builder.py`
  - 必要に応じ `src/graphyml/application/use_cases/__init__.py`
  - `tests/integration/*.py`
  - `README.md`
- 影響範囲: ライブラリ利用 API、README 導線、統合テスト。
- 互換性:
  - 既存の `NodeRegistryPort` 渡しは維持。
  - 既存 YAML（`condition` と `__next__` 契約）は維持。
- 依存関係: LangGraph `StateGraph` の state schema 受け取り仕様に依存。

## 4. 要件
### 4.1 機能要件
- `Graphyml.from_workflow(...)` へ `state_schema` 引数（任意、既定 `dict`）を追加。
- `Graphyml.from_workflow(...)` の `registry` が `Mapping[str, NodeHandler]` でも受理されること。
- `state_graph_builder` のビルド処理で `StateGraph(state_schema)` を使うこと。
- README に以下を追記/修正する。
  - TypedDict を使った State 定義例
  - 条件分岐の実行契約（node が `{"__next__": "label"}` を返す）
  - `prompt_ref`/`model_ref` が解決後に `params["prompt"]`/`params["model"]` へ展開されること
  - `end_at` は finish point として扱われること
- 既存テストに加えて、以下を検証する統合テストを追加/更新。
  - dict registry 受け取り
  - state_schema 指定での実行

### 4.2 非機能要件 / 制約
- Python 3.12 型チェック（mypy）を維持する。
- docstring は既存規約（Google style/日本語）を維持する。
- 既存 public API を壊さない。

## 5. 仕様 / 設計
### 5.1 全体方針
- API 入口で registry 型を正規化し、内部は既存 `NodeRegistryPort` 契約で統一する。
- state schema は builder 層へ引き渡し、グラフ生成時のみ反映する。
- README は「現仕様を正確に伝える」ことを優先し、未対応DSLの記載は避ける。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/graphyml/__init__.py` | `from_workflow` に `state_schema` 追加、`dict` registry 受理 | 利用API改善 | 後方互換維持 |
| `src/graphyml/application/use_cases/state_graph_builder.py` | `state_schema` を `StateGraph` へ反映 | グラフ構築挙動 | 既定は `dict` |
| `tests/integration/*` | dict registry / state_schema テスト追加 | 回帰防止 | 新規または既存更新 |
| `README.md` | Quick Start と仕様説明を明確化 | 導入障壁低減 | FB反映 |

### 5.3 詳細
#### API
- 変更後の想定シグネチャ:
  - `Graphyml.from_workflow(workflow_path, registry, bundle_root=None, state_schema=dict)`
- `registry` 受理型:
  - `NodeRegistryPort`
  - `Mapping[str, NodeHandler]`

#### UI
- 該当なし。

#### データモデル / 永続化
- YAML スキーマは現状維持。
- 条件分岐は `edges[].condition` と `state["__next__"]` の一致で解決する仕様を明記。

#### 設定 / 環境変数
- 該当なし。

### 5.4 代替案と不採用理由
- 代替案A: README だけ修正し、API は現状維持。
  - 不採用理由: 実利用時の冗長さ（registry）と State 型の不満が残る。
- 代替案B: `branches` DSL を追加して仕様刷新する。
  - 不採用理由: スキーマ拡張・実装変更が大きく、今回の改善目的に対して過剰。

## 6. 移行 / ロールアウト
- API拡張 → テスト追加/更新 → README 更新の順で実施。
- ロールバック条件: 既存利用者の呼び出しが壊れる、または m ypy/pytest が失敗する場合。
- ロールバック手順: 追加引数・型分岐を段階的に戻し、破壊箇所を最小修正する。

## 7. テスト計画
- 単体: 必要に応じ registry 正規化の単体検証。
- 結合: workflow 実行テストで dict registry / state_schema 指定を検証。
- 手動: README 記載 API と実装シグネチャを突合。
- LLM/外部依存: 該当なし。
- 合格条件: `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q` が成功。

## 8. 受け入れ基準
- `Graphyml.from_workflow` で dict registry が使える。
- `Graphyml.from_workflow` で state schema 指定ができる。
- README で分岐契約、catalog解決、`end_at` 挙動が説明されている。
- 追加/更新テストが通る。

## 9. リスク / 対策
- リスク: registry の受理型拡張で型曖昧さが増える。
  - 対策: 入口で型判定を限定し、非対応型は明示エラーにする。
- リスク: state schema の型注釈が厳密化しすぎて利用性が下がる。
  - 対策: API 型は実用優先で緩めにし、README に推奨パターンを示す。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] `from_workflow` に `state_schema` と dict registry 対応を実装する。
- [x] builder に state schema 反映を実装する。
- [x] 統合テストを追加/更新する。
- [x] README を仕様明確化版へ更新する。
- [x] lint/type/test を実行する。

## 12. ドキュメント更新
- [x] `README.md`（仕様明確化）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/`（`docs/task-designs/*.md`）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-14 00:14
- 承認コメント: 「実装フェーズを開始してください」

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
