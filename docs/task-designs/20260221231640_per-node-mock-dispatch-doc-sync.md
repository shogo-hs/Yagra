# タスク設計書: 同一ハンドラー名競合の修正（ノード単位モック解決）とドキュメント同期

最終更新: 2026-02-21
- ステータス: 承認済み(approved)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/product/vision.md`, `docs/product/goals.md`, `docs/product/milestones.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-20
- 関連マイルストーンID: M-50

## 0. TL;DR
- Golden Test リプレイ時に、同一ハンドラー名（例: `llm`）を使う複数ノードが衝突する問題を修正する。
- `NodeRegistryPort` に `resolve_for_node(name, node_id)` を導入し、`StateGraph` 構築時にノード単位でハンドラーを解決する。
- `build_golden_registry()` をノード単位ディスパッチに変更し、LLM モックを `node_id` ごとに分離する。
- `docs/`、`README.md`、`CHANGELOG.md`、Sphinx 向け changelog を同期し、仕様差分を明示する。

## 1. 背景 / 課題
- Golden Test のモック差し替えがハンドラー名単位だったため、同じ `handler: llm` を持つ複数ノードで応答が競合していた。
- その結果、ノードごとに異なる `output_snapshot` を返すべきケースで、誤ったモック応答が使われ回帰検証の信頼性が低下する。
- 実装修正後にドキュメントへ反映しないと、利用者に誤った前提（ハンドラー名単位モック）を与える。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- ノード単位モック解決により、同一ハンドラー名を持つ複数 LLM ノードでも正しくゴールデンリプレイできる。
- 仕様差分を関連ドキュメントへ反映し、CLI/MCP 利用者向け説明の整合を取る。
- `uv run pytest` が全件通過する。

### 2.2 非ゴール
- Golden Test の比較戦略そのもの（exact / structural / skip / auto）の仕様変更。
- 新規 CLI サブコマンドや MCP ツールの追加。
- 既存 Goal/Milestone の状態変更（Done/Planned の再分類）。

## 3. スコープ / 影響範囲
- 変更対象: `src/yagra/application/use_cases/golden_test_runner.py`, `src/yagra/application/use_cases/state_graph_builder.py`, `src/yagra/ports/outbound/node_registry.py`, `tests/unit/application/test_golden_test_runner.py`, 関連ドキュメント
- 影響範囲: Golden Test 実行時のハンドラー解決、ノード実行時のレジストリインターフェース、利用者向け仕様説明
- 互換性: `resolve()` は維持し、`resolve_for_node()` はデフォルトで `resolve()` へ委譲するため後方互換あり
- 依存関係: 既存の `NodeRegistryPort` 実装、`build_state_graph()`、Golden Test リプレイ処理

## 4. 要件
### 4.1 機能要件
- `build_state_graph()` がノード追加時に `registry.resolve_for_node(node.handler, node.id)` を使用すること。
- Golden Registry が LLM ノードのモックを `node_id` 単位で保持し、同一ハンドラー名でも正しいスナップショットを返すこと。
- 非 LLM ノードおよびゴールデンケース外ノードは既存レジストリ解決を維持すること。
- ドキュメントに「同一ハンドラー名でもノード単位でモック解決される」旨を反映すること。

### 4.2 非機能要件 / 制約
- Hexagonal Architecture を崩さず、Port 拡張で実現すること。
- Python 3.12+ / 型ヒント / `ruff` / `mypy` / `pytest` 前提を維持すること。
- 変更履歴は Keep a Changelog 形式に従って追記すること。

## 5. 仕様 / 設計
### 5.1 全体方針
- `NodeRegistryPort` にノードコンテキスト付き解決 API を追加し、既存実装はデフォルト委譲で後方互換を維持する。
- Golden Test 専用レジストリで `node_id -> mock handler` マップを持ち、LLM ノードをノード単位でディスパッチする。
- 利用者ドキュメントは「決定論的リプレイ」の説明に加え、同一ハンドラー名競合が解消された挙動を明示する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/yagra/ports/outbound/node_registry.py` | `resolve_for_node()` 追加（既定は `resolve()` 委譲） | 小 | 後方互換維持 |
| `src/yagra/application/use_cases/state_graph_builder.py` | ハンドラー解決を `resolve_for_node()` に変更 | 中 | 実行時解決経路変更 |
| `src/yagra/application/use_cases/golden_test_runner.py` | `_GoldenNodeRegistry` 導入、LLM モックの node_id ディスパッチ化 | 中 | 競合修正の本体 |
| `tests/unit/application/test_golden_test_runner.py` | 同一ハンドラー名でノード別応答を検証するケースへ更新 | 小 | 回帰テスト強化 |
| `README.md` / `CHANGELOG.md` / `docs/` | 仕様反映・変更履歴同期 | 小 | 文書整合性 |

### 5.3 詳細
#### API
- 外部 API 追加なし。

#### UI
- 変更なし。

#### データモデル / 永続化
- 変更なし（ゴールデンケース JSON 形式は維持）。

#### 設定 / 環境変数
- 変更なし。

### 5.4 代替案と不採用理由
- 代替案A: 既存 `resolve(name)` のみを使い、ハンドラー名を強制一意にする。
  - 不採用理由: 既存ワークフロー互換性を壊し、ユーザー負担が大きい。
- 代替案B: Golden Test 側だけでノード名をハンドラー名へ埋め込む。
  - 不採用理由: Port 設計が歪み、通常実行との整合が崩れる。

## 6. 移行 / ロールアウト
- 互換 API 追加のため段階的ロールアウト不要。
- ロールバック条件: Golden Test で既存ケースが広範囲に失敗し、原因が本修正に起因すると判明した場合。
- ロールバック手順: 対象コミットを revert し、`uv run pytest` 再実行で回復確認。

## 7. テスト計画
- 単体: `tests/unit/application/test_golden_test_runner.py` の node_id ディスパッチ検証。
- 結合: `build_state_graph()` 経由でのハンドラー解決が壊れていないことを既存テストで確認。
- 手動: ドキュメント更新差分のレビュー（用語・挙動の一致）。
- LLM/外部依存: ゴールデンモックのみを使用し API 呼び出しなし。
- 合格条件: `uv run pytest` が全件成功し、関連ドキュメントの説明が実装と一致する。

## 8. 受け入れ基準
- 同一ハンドラー名の複数 LLM ノードで、各ノードが自身の `output_snapshot` を返す。
- 非 LLM ノードは従来どおり実ハンドラー解決される。
- `README.md`、`CHANGELOG.md`、`docs/sphinx/source/changelog.md` を含む関連ドキュメントに修正内容が反映される。
- `uv run pytest` が成功する。

## 9. リスク / 対策
- リスク: `NodeRegistryPort` 拡張で既存実装が未対応の場合に解決エラーが出る。
- 対策: `resolve_for_node()` のデフォルト実装を `resolve()` 委譲にして破壊的変更を回避する。
- リスク: ドキュメント同期漏れで利用者の認識が分裂する。
- 対策: `docs/` 全体を grep で走査し、golden/mock 関連記述を重点確認する。

## 10. オープン事項 / 要確認
- 該当なし

## 11. 実装タスクリスト
- [x] ノード単位ハンドラー解決 API を Port に追加
- [x] Golden Registry を node_id ディスパッチに修正
- [x] 単体テストを node_id ベース期待値へ更新
- [x] 関連ドキュメントを実装挙動に同期
- [x] `uv run pytest` の全件通過確認
- [ ] コミット・PR作成

## 12. ドキュメント更新
- [x] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/`（該当ファイルあれば）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-21 23:16 JST
- 承認コメント: fix/per-node-mock-dispatch の残タスク（docs同期・テスト・PR作成）を実施する。

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
