# 進捗スコアボード

最終更新: 2026-02-13

## 更新ルール

- 更新頻度: 状態変化があったタイミングで更新する。
- 更新者: 該当 Goal に紐づくタスク設計を更新した担当者。
- 記載単位: Goal ID 単位。
- 進捗表示: `%` は使わず、「やるべきこと一覧」「完了済み」「未完了」「現在地」で記録する。

## Goal別進捗

### G-01: YAML だけで LangGraph フロー構成を定義できる

**やるべきこと一覧**

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G01-I01 | Graphyml YAML の Pydantic スキーマを定義する | Done | `src/graphyml/domain/entities/graph_schema.py` |
| G01-I02 | 条件分岐・ループを含むサンプル YAML を作成する | Planned | `docs/product/vision.md` |
| G01-I03 | 不正 YAML の検証エラーをテスト化する | Done | `tests/unit/domain/test_graph_schema.py` |

- 完了済み: G01-I01, G01-I03
- 未完了: G01-I02
- 現在地: Pydantic スキーマと検証テストは整備済みで、サンプル YAML 整備が次の作業。

### G-02: YAML 定義と Python 実処理を疎結合に接続できる

**やるべきこと一覧**

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G02-I01 | Registry インターフェースを ports として定義する | Done | `src/graphyml/ports/outbound/node_registry.py` |
| G02-I02 | ノード名と callable を紐づける実装を作る | Done | `src/graphyml/adapters/outbound/in_memory_node_registry.py` |
| G02-I03 | 未登録ノード時のエラーハンドリングを整備する | Done | `tests/unit/adapters/test_in_memory_node_registry.py` |

- 完了済み: G02-I01, G02-I02, G02-I03
- 未完了: なし
- 現在地: Registry 契約と in-memory 実装は完了し、次はユースケースへの接続（M-03）へ進む段階。

### G-03: YAML 差し替えで複数ワークフローを低コストに運用できる

**やるべきこと一覧**

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G03-I01 | YAML から StateGraph を組み立てるビルダーを実装する | Done | `src/graphyml/application/use_cases/state_graph_builder.py` |
| G03-I02 | 複数 YAML で同一実装を切り替えるサンプルを用意する | Done | `tests/fixtures/workflows/` |
| G03-I03 | Zero-Boilerplate の利用例を README に記載する | Planned | `README.md` |

- 完了済み: G03-I01, G03-I02
- 未完了: G03-I03
- 現在地: ビルダーとサンプル実行は完了し、README 利用例の整備が残タスク。

### G-04: 開発運用で品質ゲートを常時維持できる

**やるべきこと一覧**

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G04-I01 | `uv` ベースの品質ゲートを導入する | Done | `pyproject.toml` |
| G04-I02 | GitHub Actions で lint/type/test を自動実行する | Done | `.github/workflows/ci.yml` |
| G04-I03 | pre-commit / pre-push をローカルへ導入する | In Progress | `.pre-commit-config.yaml` |

- 完了済み: G04-I01, G04-I02
- 未完了: G04-I03
- 現在地: CI は導入済みで、ローカルフック適用を進めている段階。
