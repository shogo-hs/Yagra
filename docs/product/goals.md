# ユーザー到達状態ゴール

最終更新: 2026-02-13

## ゴール一覧

| Goal ID | ユーザーが到達したい状態 | 到達判定（Definition of Done） | 状態 |
| --- | --- | --- | --- |
| G-01 | YAML だけで LangGraph フロー構成を定義できる | ノード・エッジ・条件分岐を含む YAML を Pydantic で検証できる | In Progress |
| G-02 | YAML 定義と Python 実処理を疎結合に接続できる | Registry でノード名から Python callable を解決し、実行に成功する | In Progress |
| G-03 | YAML 差し替えで複数ワークフローを低コストに運用できる | Graph 構築コードを追加せずに設定変更だけで別フローを起動できる | In Progress |
| G-04 | 開発運用で品質ゲートを常時維持できる | CI / pre-commit で format・lint・type・test が一貫して通る | In Progress |

## 運用ルール

- ゴールは 3〜5 個に絞る。
- 各ゴールは必ず「ユーザーが到達したい状態」で書く。
- 各ゴールに `到達判定（Definition of Done）` を 1 つ以上持たせる。
