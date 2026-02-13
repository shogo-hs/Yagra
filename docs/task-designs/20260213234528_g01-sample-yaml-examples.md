# タスク設計書: G01-I02 分岐・ループサンプル YAML 整備

最終更新: 2026-02-13
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `README.md`, `tests/fixtures/workflows/`, `docs/product/goals.md`, `docs/product/progress.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-01
- 関連マイルストーンID: M-01

## 0. TL;DR
- `G01-I02` 完了のため、分岐・ループを含む利用者向けサンプル YAML を `examples/` 配下へ整備する。
- 既存テストフィクスチャをベースに、単一YAML（inline）と分割参照（split）の2系統を提供する。
- README からサンプルへ到達できる導線を追加し、進捗ドキュメントの状態を `Done` に更新する。
- 追加したサンプルがスキーマ検証と読み込みで壊れていないことをテストで担保する。

## 1. 背景 / 課題
- `docs/product/progress.md` では `G01-I02` が未完了で、`G-01` の最後の未達項目になっている。
- 現在の分岐・ループ YAML は `tests/fixtures/workflows/` にあり、利用者向けの正式サンプルとしては見つけにくい。
- README に「どのサンプルYAMLを使えばよいか」の案内が不足しており、初回利用時に探索コストが発生する。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- 利用者が分岐・ループの YAML 例を `examples/` から直接参照できる状態にする。
- サンプル YAML が Graphyml のスキーマ契約・参照解決契約を満たすことをテストで保証する。
- `G01-I02` を `Done` にし、必要に応じて `G-01` の状態を更新する。

### 2.2 非ゴール
- 新しいワークフロー機能（新ノード属性・新エッジ仕様）の追加は行わない。
- LangGraph ビルダー実装の機能拡張は行わない。
- 外部LLMプロバイダとの実接続コードは追加しない。

## 3. スコープ / 影響範囲
- 変更対象: `examples/workflows/`, `examples/prompts/`, `examples/models/`, `README.md`, `tests/`, `docs/product/*.md`。
- 影響範囲: ライブラリ利用者のオンボーディング、G-01 の進捗判定。
- 互換性: 既存 API/挙動への破壊的変更はなし。
- 依存関係: 既存 `GraphSpec` スキーマ、workflow loader、reference resolver に依存。

## 4. 要件
### 4.1 機能要件
- 分岐サンプル（条件付き遷移）YAML を1つ追加する。
- ループサンプル（循環 + 条件分岐）YAML を1つ追加する。
- 少なくとも1つは `prompt_ref`/`model_ref` を使う分割参照構成を含める。
- README にサンプルファイル一覧と使い方（実行時の `workflow_path` 差し替え）を追記する。
- サンプル YAML の検証テストを追加し、CI で継続的に確認できるようにする。
- `docs/product/progress.md` の `G01-I02` を `Done` に更新する。

### 4.2 非機能要件 / 制約
- サンプルは ASCII 中心で記述し、可読性を優先する。
- 既存のテストフィクスチャと意味が重複しても、利用者向け配置とテスト用途を明確に分ける。
- README にはエージェント実行規約を記載せず、人間向け利用導線に限定する。

## 5. 仕様 / 設計
### 5.1 全体方針
- 既存 `tests/fixtures/workflows/*.yaml` の構成をベースに、利用者向けに `examples/` へ再配置する。
- 「単一YAMLで完結する例」と「分割参照する例」を並べ、設計選択を比較できるようにする。
- テストは examples を直接読み込んで検証し、サンプルの陳腐化を防ぐ。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `examples/workflows/branch-inline.yaml` | 分岐サンプルを追加 | 利用者向け例の提供 | 新規 |
| `examples/workflows/loop-split.yaml` | ループ+分割参照サンプルを追加 | 利用者向け例の提供 | 新規 |
| `examples/prompts/*.yaml` | split 用プロンプト定義を追加 | 参照解決例の提供 | 新規 |
| `examples/models/*.yaml` | split 用モデル定義を追加 | 参照解決例の提供 | 新規 |
| `README.md` | examples の説明と利用導線を追記 | 初回利用性向上 | 更新 |
| `tests/integration/*` もしくは `tests/unit/*` | examples の検証テストを追加 | 回帰防止 | 新規/更新 |
| `docs/product/progress.md` | G01-I02 を `Done` 更新 | 進捗同期 | 更新 |
| `docs/product/goals.md` | G-01 状態の見直し | 状態整合 | G01-I02完了時に `Done` |

### 5.3 詳細
#### API
- 追加 API はなし。既存 `Graphyml.from_workflow(...)` の利用パスのみ追記する。

#### UI
- 該当なし。

#### データモデル / 永続化
- `GraphSpec` の既存項目（`nodes/edges/start_at/end_at/params`）のみを利用する。
- split 例は `params.prompt_catalog`, `params.model_catalog`, `node.params.prompt_ref`, `node.params.model_ref` を使用する。

#### 設定 / 環境変数
- 追加なし。

### 5.4 代替案と不採用理由
- 代替案A: `tests/fixtures` をそのまま README から参照する。
  - 不採用理由: テスト補助ファイルを利用者向け入口にするのは責務が曖昧で、将来の整理で参照切れが起きやすい。
- 代替案B: 単一YAMLの例だけを追加する。
  - 不採用理由: 既に議論済みの分割参照パターンが伝わらず、実運用イメージが不足する。

## 6. 移行 / ロールアウト
- `examples/` 追加 → README 追記 → テスト追加/更新 → 進捗ドキュメント更新の順で実施する。
- ロールバック条件: examples 追加で既存テストが破綻する、または README 導線が誤解を招く場合。
- ロールバック手順: 当該ファイルを差し戻し、設計書へ原因と修正方針を追記する。

## 7. テスト計画
- 単体: examples YAML を `validate_graph_spec` で検証するテストを追加する。
- 結合: split 例を `load_graph_spec_from_workflow` で読み込み、参照解決後に主要フィールドが展開されることを確認する。
- 手動: README 記載パスが実在し、サンプル名と説明が一致することを確認する。
- LLM/外部依存: なし（ダミーハンドラ/ローカルファイルのみ）。
- 合格条件: `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q` が成功する。

## 8. 受け入れ基準
- `examples/workflows/` に分岐例とループ例が追加されている。
- ループ例で分割参照（prompts/models）が機能する構成になっている。
- README から examples の使い方が分かる。
- テストで examples の妥当性が検証される。
- `docs/product/progress.md` で `G01-I02` が `Done` になっている。

## 9. リスク / 対策
- リスク: examples と tests/fixtures が二重管理になり乖離する。
  - 対策: examples を検証するテストを追加し、更新時に検出できるようにする。
- リスク: README 記述が実ファイル名とずれる。
  - 対策: 追記後に `rg` と目視でパス一致を確認する。
- リスク: G-01 を Done に更新する根拠が弱い。
  - 対策: `G01-I01/I02/I03` がすべて Done であることを progress で確認後に更新する。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] `examples/workflows` に branch/loop サンプルを追加する。
- [x] `examples/prompts` / `examples/models` に split 参照ファイルを追加する。
- [x] README に examples 利用導線を追記する。
- [x] examples 妥当性を検証するテストを追加する。
- [x] `docs/product/progress.md` と `docs/product/goals.md` を更新する。

## 12. ドキュメント更新
- [x] `README.md`（examples 利用導線を追加）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/`（`docs/product/*.md`, `docs/task-designs/*.md`）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-13 23:48
- 承認コメント: 「OK」にて承認

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
