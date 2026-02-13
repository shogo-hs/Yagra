# タスク設計書: M-03 YAML から StateGraph を構築するビルダー実装

最終更新: 2026-02-13
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/product/goals.md`, `docs/product/milestones.md`, `docs/product/progress.md`, `docs/task-designs/20260213224942_m01-yaml-pydantic-schema.md`, `docs/task-designs/20260213230010_m02-registry-binding.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-03
- 関連マイルストーンID: M-03

## 0. TL;DR
- M-03 の目的に合わせて、`GraphSpec` + `NodeRegistry` から LangGraph `StateGraph` を構築・コンパイルするユースケースを実装する。
- 分岐（condition付き edge）とループ（循環 edge）を含む YAML からグラフを実行できることを、サンプル YAML と統合テストで検証する。
- 利用者の入口は常に 1 ファイル（`workflow.yaml`）にし、必要な場合のみ `prompt_ref` / `model_ref` で外部 YAML を参照できるようにする。
- プロンプト/モデルのノード結び付けはビルダー層で解決し、ノード callable には解決済み設定を渡す。
- 文字列定義（YAML）と実処理（Python callable）の分離を維持し、Graphyml の Zero-Boilerplate 価値を実証する。
- G03-I01/G03-I02 を Done へ更新し、M-03 完了条件に到達する。

## 1. 背景 / 課題
- M-01 により YAML/Pydantic スキーマ検証、M-02 により handler 解決 Registry は整備済み。
- ただし現状は「定義を読める」までで、LangGraph `StateGraph` を実際に組み立てて実行する層が未実装。
- G-03 の DoD（設定差し替えだけで別ワークフロー起動）を達成するには、ビルダー実装と複数 YAML 実行デモが必要。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- `GraphSpec` から `StateGraph` を組み立てるビルダー関数を実装する。
- handler 名を Registry で解決してノード登録できる。
- `workflow.yaml` 単一入口でインスタンス化できる API（例: `Graphyml.from_workflow(...)`）を提供する。
- `prompt_ref` / `model_ref` を使った分割構成を同じ入口から解決できる。
- 条件分岐とループを含むグラフを YAML 差し替えで実行できることをテストで示す。
- サンプル YAML を 2 種類以上用意し、同一ビルダーで動作する。

### 2.2 非ゴール
- プロダクション向けの永続ストア・チェックポイント導入は行わない。
- 高度な LangGraph 機能（subgraph、interrupt、human-in-the-loop）は対象外。
- CLI コマンドの UX 整備は最小限に留める（必要時のみ簡易ヘルパー）。

## 3. スコープ / 影響範囲
- 変更対象: `src/graphyml/application/use_cases/**`, `src/graphyml/adapters/inbound/**`（必要時）、`tests/integration/**`, `tests/fixtures/**`, `docs/product/progress.md`, `README.md`（利用例追加時）。
- 影響範囲: Graphyml の実行基盤（M-03）と、次工程である M-04 以降のデモ/回帰テスト基盤。
- 互換性: 初回導入のため後方互換問題はない。
- 依存関係: `langgraph`（runtime 依存として追加予定）、既存 `pydantic` / `pytest`。

## 4. 要件
### 4.1 機能要件
- `langgraph` を runtime 依存に追加する。
- `pyyaml` を runtime 依存に追加する。
- 下記ユースケースを提供する。
  - `build_state_graph(spec: GraphSpec, registry: NodeRegistryPort) -> CompiledStateGraph`
  - `build_from_workflow_path(workflow_path: PathLike, registry: NodeRegistryPort, bundle_root: PathLike | None = None) -> CompiledStateGraph`
- 下記クラス API を提供する。
  - `Graphyml.from_workflow(workflow_path: PathLike, registry: NodeRegistryPort, bundle_root: PathLike | None = None)`
- ノード構築要件:
  - `spec.nodes` の各 `handler` を Registry で解決して `StateGraph` に登録する。
  - ノード実行時は `state` と「解決済みノード設定（`node.params` + ref解決結果）」を callable に渡すラッパーを適用する。
- エッジ構築要件:
  - `condition` なし edge は通常遷移として登録する。
  - `condition` あり edge は source ごとに条件ルーティングとして登録する。
- 条件分岐の実行規約:
  - ノード結果の `__next__` キーを分岐ラベルとして扱う。
  - 未定義ラベルが返された場合は `GraphBuildError`（または同等の専用例外）を送出する。
- 開始/終了要件:
  - `start_at` をエントリポイントへ設定する。
  - `end_at` の各ノードを終端として設定する。
- サンプル要件:
  - 単一ファイル構成サンプルを 1 パターン以上作成する。
  - 分割参照（`prompt_ref` / `model_ref`）構成サンプルを 1 パターン以上作成する。

### 4.3 YAML参照仕様
- 入口ファイルは `workflow.yaml` とする。
- 分割参照する場合、`nodes[].params` に以下を許可する。
  - `prompt_ref`: `<path>#<key>` または `<key>`（`params.prompt_catalog` と組み合わせ）
  - `model_ref`: `<path>#<key>` または `<key>`（`params.model_catalog` と組み合わせ）
- ビルダー層で参照を解決し、ノード callable には以下のキーを渡す。
  - `params.prompt`（解決済みプロンプト定義）
  - `params.model`（解決済みモデル定義）
- 参照解決失敗時は専用例外（例: `WorkflowReferenceError`）を送出する。

### 4.2 非機能要件 / 制約
- 型ヒントを必須にし、`mypy` を通す。
- `ruff` / `pytest` / `pre-commit` を通す。
- docstring は Google style（日本語）で記述する。
- StateGraph 構築ロジックは application 層に集約し、ports/adapters の責務を混在させない。

## 5. 仕様 / 設計
### 5.1 全体方針
- `GraphSpec` は domain、`NodeRegistryPort` は ports、組み立ては application のユースケースとして分離する。
- M-02 で整備した `InMemoryNodeRegistry` を直接差し替え可能な構造を維持する。
- 分岐仕様を `__next__` に固定し、M-03 完了時点で利用者が迷わない最小契約を確立する。
- 入口 UX は「1ファイル指定」を固定し、分割は内部解決で吸収する（単一入口・内部分割）。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/graphyml/application/use_cases/state_graph_builder.py` | `GraphSpec` から `CompiledStateGraph` を構築するユースケースを追加 | M-03 の中核実装 | 新規 |
| `src/graphyml/application/use_cases/workflow_loader.py` | `workflow.yaml` 読み込みと ref 解決を追加 | 単一入口 + 分割参照解決 | 新規 |
| `src/graphyml/application/services/reference_resolver.py` | `prompt_ref/model_ref` 解決ロジックを追加 | ノード設定解決の共通化 | 新規 |
| `src/graphyml/__init__.py` | `Graphyml.from_workflow(...)` 入口 API を公開 | ライブラリ利用性向上 | 更新 |
| `src/graphyml/application/use_cases/__init__.py` | ビルダーの公開 | 利用導線の統一 | 新規/更新 |
| `tests/integration/test_state_graph_builder.py` | 分岐・ループを含む統合テストを追加 | M-03 DoD 検証 | 新規 |
| `tests/fixtures/workflows/*.yaml` | 複数ワークフローのサンプル YAML を追加 | YAML 差し替え検証 | 新規 |
| `tests/fixtures/prompts/*.yaml` | 分割参照用プロンプト定義を追加 | ref 解決検証 | 新規 |
| `tests/fixtures/models/*.yaml` | 分割参照用モデル定義を追加 | ref 解決検証 | 新規 |
| `pyproject.toml` / `uv.lock` | `langgraph` 依存追加 | ランタイム実行基盤 | 更新 |
| `docs/product/progress.md` | G03-I01/G03-I02 の状態更新 | 進捗同期 | 更新 |
| `README.md` | 利用例を必要最小限追記 | G03-I03 の着手基盤 | 任意 |

### 5.3 詳細
#### API
- 外部 HTTP API は追加しない。
- ライブラリ内部 API として `build_state_graph` / `build_from_workflow_path` を提供する。
- 利用者向け API として `Graphyml.from_workflow(...)` を提供する。

#### UI
- 該当なし。

#### データモデル / 永続化
- 既存 `GraphSpec` を入力として利用する。
- 永続化は行わず、実行時メモリ内で構築・実行する。
- 分割参照データ（prompts/models）はビルド時に解決し、実行時は解決済み設定を使う。

#### 設定 / 環境変数
- 追加なし。

### 5.4 代替案と不採用理由
- 代替案A: application 層を作らず adapters 層で直接 `StateGraph` を構築する。
  - 不採用理由: ユースケース責務が崩れ、将来の差し替え/テスト容易性が落ちる。
- 代替案B: 条件分岐を callable 返り値ではなく固定エッジ順で処理する。
  - 不採用理由: YAML だけで分岐制御できず、Declarative の目的に反する。

## 6. 移行 / ロールアウト
- フェーズ1: `langgraph` / `pyyaml` 依存追加と `workflow.yaml` ローダー実装。
- フェーズ2: 条件分岐・ループ対応のビルダー実装。
- フェーズ3: 単一構成 + 分割構成サンプルと統合テスト追加。
- フェーズ4: 進捗ドキュメント更新と品質ゲート実行。
- ロールバック条件: `ruff` / `mypy` / `pytest` 失敗、またはサンプル YAML 実行失敗。
- ロールバック手順: M-03 追加差分を取り消し、分岐仕様を再設計して再着手する。

## 7. テスト計画
- 単体:
  - ビルダー内部補助関数（条件 edge グルーピング、ルート解決）の検証。
- 結合:
  - サンプルA（単一ファイル, 分岐あり）で期待ノード遷移になる。
  - サンプルB（分割参照, ループあり）で停止条件到達まで動作する。
  - `Graphyml.from_workflow(...)` で同一 API から別 YAML が動作する。
- 手動:
  - `uv run ruff check .`
  - `uv run mypy .`
  - `uv run pytest -q`
- LLM/外部依存:
  - LLM 呼び出しは行わず、テストでは純関数ハンドラを使う。
- 合格条件:
  - 新規統合テストが通り、既存 M-01/M-02 テストを壊さない。

## 8. 受け入れ基準
- `build_state_graph` が `GraphSpec` と `NodeRegistryPort` を受けて実行可能なグラフを返す。
- `Graphyml.from_workflow(...)` に `workflow.yaml` パスを渡してインスタンス化できる。
- 条件分岐（`condition`）とループ（循環 edge）を含む YAML を実行できる。
- 単一構成/分割構成の複数 YAML を同一入口 API で切り替え実行できる。
- `tests/integration/test_state_graph_builder.py` が通る。
- `uv run ruff check .` / `uv run mypy .` / `uv run pytest -q` が成功する。

## 9. リスク / 対策
- LangGraph 依存追加により型周りが複雑化するリスク。
  - 対策: まず `dict[str, Any]` ベースの最小状態モデルで実装し、型厳密化は次段で行う。
- 条件分岐キー規約（`__next__`）が暗黙化するリスク。
  - 対策: 設計書・README・テストで規約を明示する。
- ループで無限実行するリスク。
  - 対策: テストハンドラ側に明示停止条件を持たせ、反復回数を制御する。
- 分割参照パス解決が壊れるリスク。
  - 対策: `workflow.yaml` 基準の相対解決と `bundle_root` 明示指定の両方を統合テストで検証する。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] `langgraph` / `pyyaml` を runtime 依存へ追加する。
- [x] `workflow.yaml` ローダー（単一入口 + ref 解決）を実装する。
- [x] `build_state_graph` と `Graphyml.from_workflow(...)` を実装する。
- [x] 単一構成/分割構成の YAML サンプルを追加する。
- [x] 統合テストを追加する。
- [x] `docs/product/progress.md`（必要に応じて `README.md`）を更新する。
- [x] 品質ゲート（ruff/mypy/pytest）を通す。

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/product/progress.md`（G-03進捗更新）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-13 23:28
- 承認コメント: 「お願いします」にて実装依頼

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
