# 進捗スコアボード

最終更新: 2026-02-14

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
| G01-I01 | Yagra YAML の Pydantic スキーマを定義する | Done | `src/yagra/domain/entities/graph_schema.py` |
| G01-I02 | 条件分岐・ループを含むサンプル YAML を作成する | Done | `examples/workflows/` |
| G01-I03 | 不正 YAML の検証エラーをテスト化する | Done | `tests/unit/domain/test_graph_schema.py` |

- 完了済み: G01-I01, G01-I02, G01-I03
- 未完了: なし
- 現在地: G-01 の項目は完了。分岐・ループを含むサンプル YAML と検証テストを整備済み。

### G-02: YAML 定義と Python 実処理を疎結合に接続できる

**やるべきこと一覧**

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G02-I01 | Registry インターフェースを ports として定義する | Done | `src/yagra/ports/outbound/node_registry.py` |
| G02-I02 | ノード名と callable を紐づける実装を作る | Done | `src/yagra/adapters/outbound/in_memory_node_registry.py` |
| G02-I03 | 未登録ノード時のエラーハンドリングを整備する | Done | `tests/unit/adapters/test_in_memory_node_registry.py` |

- 完了済み: G02-I01, G02-I02, G02-I03
- 未完了: なし
- 現在地: G-02 の項目は完了。Registry 契約と in-memory 実装、未登録時エラーハンドリングまで整備済み。

### G-03: YAML 差し替えで複数ワークフローを低コストに運用できる

**やるべきこと一覧**

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G03-I01 | YAML から StateGraph を組み立てるビルダーを実装する | Done | `src/yagra/application/use_cases/state_graph_builder.py` |
| G03-I02 | 複数 YAML で同一実装を切り替えるサンプルを用意する | Done | `tests/fixtures/workflows/` |
| G03-I03 | Zero-Boilerplate の利用例を README に記載する | Done | `README.md` |

- 完了済み: G03-I01, G03-I02, G03-I03
- 未完了: なし
- 現在地: G-03 の項目は完了。YAML 差し替え実行と README 利用導線まで整備済み。

### G-04: 開発運用で品質ゲートを常時維持できる

**やるべきこと一覧**

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G04-I01 | `uv` ベースの品質ゲートを導入する | Done | `pyproject.toml` |
| G04-I02 | GitHub Actions で lint/type/test を自動実行する | Done | `.github/workflows/ci.yml` |
| G04-I03 | pre-commit / pre-push をローカルへ導入する | Done | `.pre-commit-config.yaml` |

- 完了済み: G04-I01, G04-I02, G04-I03
- 未完了: なし
- 現在地: G-04 の項目は完了。CI とローカルフックで品質ゲートを継続実行できる状態。あわせて publish workflow にタグ/版数一致チェックを追加し、公開安全性を強化済み。

### G-05: 非エンジニアが WebUI 上でワークフローを可視化・編集し、迷わず運用できる

**やるべきこと一覧**

| Item ID | やるべきこと | 状態 | 根拠 |
| --- | --- | --- | --- |
| G05-I01 | WebUI 可視化に必要な検証契約（エラー形式）を定義する | Done | `src/yagra/application/use_cases/workflow_validation_reporter.py` |
| G05-I02 | YAML からノード/エッジ/条件分岐を表示する Read Only 画面を実装する | Done | `src/yagra/application/use_cases/workflow_visualization.py` |
| G05-I03 | ノード詳細で `prompt` / `model` / `*_ref` を確認できるようにする | Done | `src/yagra/application/use_cases/workflow_visualization.py` |
| G05-I04 | 編集保存時の差分確認とロールバック方針を整備する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` |
| G05-I05 | prompt/model/条件をフォーム編集できるようにする | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` |
| G05-I06 | DnD でノード追加とエッジ接続変更を行い round-trip 整合を維持する | Done | `src/yagra/adapters/inbound/workflow_studio_server.py` |
| G05-I07 | 主要操作の情報設計と導線を見直し、初見でも操作順が分かる UI にする | In Progress | `src/yagra/adapters/inbound/workflow_studio_server.py` |
| G05-I08 | レイアウト/配色/ラベル体系を改善し、可読性と視認性を向上する | Todo | `docs/product/milestones.md` (M-11) |

- 完了済み: G05-I01, G05-I02, G05-I03, G05-I04, G05-I05, G05-I06
- 未完了: G05-I07, G05-I08
- 現在地: M-05〜M-09 で機能到達（可視化・フォーム編集・DnD 編集）は完了。M-10 の実装として Add Node 自動配置、エッジ線クリック選択、Rewire トグル、Raw JSON 撤去に加え、ノード側面の output/input ポートDnD導線を反映し、操作理解性の改善を継続中。

## 補足（2026-02-14）

- 配布名・import 名を `yagra` に統一し、公開 API は `Yagra` を主名称とした。
- 運用方針を「GitHub リポジトリは Private、PyPI 成果物は Public」に統一した。
- Sphinx + GitHub Pages によるドキュメント公開基盤を導入した（`.github/workflows/docs.yml`）。
- 次フェーズ方針として「非エンジニア向け WebUI（可視化→編集）」をプロダクト管理対象に追加した。
