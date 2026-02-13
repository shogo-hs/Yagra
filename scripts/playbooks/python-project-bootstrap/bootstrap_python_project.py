#!/usr/bin/env python3
"""Python プロジェクトの初期構成を生成する。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYBOOK_ASSETS_ROOT = REPO_ROOT / "docs" / "ai" / "playbook-assets"
TASK_DESIGN_TEMPLATE_PATH = (
    PLAYBOOK_ASSETS_ROOT
    / "task-design-gate"
    / "references"
    / "_task-design-template.md"
)
API_INDEX_TEMPLATE_PATH = (
    PLAYBOOK_ASSETS_ROOT
    / "api-spec-sync"
    / "references"
    / "_index_template.md"
)
API_ENDPOINT_TEMPLATE_PATH = (
    PLAYBOOK_ASSETS_ROOT
    / "api-spec-sync"
    / "references"
    / "_endpoint_template.md"
)
PRODUCT_VISION_TEMPLATE_PATH = REPO_ROOT / "docs" / "product" / "vision.md"
PRODUCT_GOALS_TEMPLATE_PATH = REPO_ROOT / "docs" / "product" / "goals.md"
PRODUCT_MILESTONES_TEMPLATE_PATH = REPO_ROOT / "docs" / "product" / "milestones.md"
PRODUCT_PROGRESS_TEMPLATE_PATH = REPO_ROOT / "docs" / "product" / "progress.md"


def load_template(path: Path, fallback: str) -> str:
    """テンプレートを正本から読み込み、なければフォールバックを返す。"""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


def normalize_package_name(name: str) -> str:
    """プロジェクト名から Python パッケージ名を生成する。"""
    candidate = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    if not candidate:
        candidate = "app"
    if candidate[0].isdigit():
        candidate = f"_{candidate}"
    return candidate


def detect_task_design_dir(target: Path, explicit: str | None) -> str:
    """既存構成に合わせてタスク設計ディレクトリを決める。"""
    if explicit:
        return explicit.strip("/")

    docs_task_designs = target / "docs" / "task-designs"
    docs_tasks = target / "docs" / "tasks"
    if docs_task_designs.exists():
        return "docs/task-designs"
    if docs_tasks.exists():
        return "docs/tasks"
    return "docs/task-designs"


def write_text_file(path: Path, content: str, force: bool, report: dict[str, list[str]]) -> None:
    """ファイルを作成または更新し、結果を集計する。"""
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == content:
            report["unchanged"].append(str(path))
            return
        if force:
            path.write_text(content, encoding="utf-8")
            report["updated"].append(str(path))
        else:
            report["skipped"].append(str(path))
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    report["created"].append(str(path))


def ensure_directories(paths: list[Path], report: dict[str, list[str]]) -> None:
    """必要なディレクトリ群を作成する。"""
    for path in paths:
        if path.exists():
            continue
        path.mkdir(parents=True, exist_ok=True)
        report["created_dirs"].append(str(path))


def ensure_gitignore(target: Path, report: dict[str, list[str]]) -> None:
    """推奨エントリを .gitignore に追加する。"""
    required_entries = [
        ".env.keys",
        ".venv/",
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".worktrees/",
    ]
    gitignore_path = target / ".gitignore"
    if gitignore_path.exists():
        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    changed = False
    existing = set(lines)
    for entry in required_entries:
        if entry not in existing:
            lines.append(entry)
            changed = True

    if not gitignore_path.exists():
        gitignore_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        report["created"].append(str(gitignore_path))
    elif changed:
        gitignore_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        report["updated"].append(str(gitignore_path))
    else:
        report["unchanged"].append(str(gitignore_path))


def build_agents_md(
    project_name: str,
    description: str,
    python_version: str,
    task_design_dir: str,
) -> str:
    """AGENTS.md の初期テンプレートを返す。"""
    task_readme = f"{task_design_dir}/README.md"
    task_template = f"{task_design_dir}/_task-design-template.md"

    return f"""# AGENTS.md

## プロジェクト概要
- **名前**: {project_name}
- **説明**: {description}
- **ランタイム**:
  - backend: Python {python_version} (`uv` 管理)

## AIコーディング向けドキュメント
- 人向けの運用ガイドは `README.md` を参照する。
- 実装方針:
  - `docs/rules/solid/README.md`
  - `docs/rules/code_architecture/README.md`
- アーキテクチャ概要: `docs/architecture/hexagonal-architecture.md`
- タスク設計: `{task_readme}`
- タスク設計テンプレート: `{task_template}`
- APIテンプレート: `docs/api/_endpoint_template.md`
- API一覧: `docs/api/index.md`
- プロダクト方針:
  - `docs/product/vision.md`
  - `docs/product/goals.md`
  - `docs/product/milestones.md`
  - `docs/product/progress.md`

## Task Design Gate (Mandatory)

- すべてのタスク依頼で、作業開始前に必ずタスク設計書を作成する（例外なし）。
- タスク設計書は `{task_design_dir}/` に保存する。ディレクトリが存在しない場合は作成する。
- ファイル名は `YYYYMMDDHHMMSS_{{task-name}}.md`（JST 初版作成日時）を使用する。
- `task-name` は英小文字の kebab-case を使用する。
- 設計書に未解消のオープン事項がある間は実装を開始しない。
- 実装ファイルの編集は、設計書に対するユーザーの明示承認後にのみ許可する。
- 実装中にスコープ変更が発生した場合、実装を停止して設計書を更新し、再承認を取得する。
- 新規プロダクト開発の開始前に、`docs/product/*.md` をユーザーと擦り合わせて初期確定する。

## Playbook運用ルール

- 既存 Playbook で対応できる場合は再利用を優先する。
- CI 設定は必須とし、`python-uv-ci-setup` を利用して完了させる。
- API 仕様変更がある場合は `api-spec-sync` を使って `docs/api/` と実装を同期する。
- 実装前の設計ゲートは `task-design-gate` を利用する。
- コミット時は `git-commit` を利用して規約を満たす。
- AGENTS.md には方針とルーティングのみ記載し、詳細手順は各 Playbook に集約する。

## Playbook配置方針（チーム再現性）
- 原則として新規作成は Playbook 同梱のテンプレートリポジトリから開始する。
- 空リポジトリから開始する場合のみ、グローバル `python-project-bootstrap` を初回1回だけ使用する。
- 初回生成直後に手順正本を `<repo>/docs/ai/canonical/playbooks/` に配置してコミットし、以後は repo ローカルを正本にする。
- 個人ホーム配下の Playbook は補助用途とし、必須依存にしない。
- 共有 Playbook の更新は PR でレビューする。

## コードスタイル
- 共通:
  - 実装方針の基本として `docs/rules/solid/README.md` を参照する。
  - DRY 原則を守り、重複ロジックは責務に応じて層へ集約する。
- Python:
  - PEP 8 / 4 スペースインデント、型ヒント必須。
  - ログは標準の `logging` を利用し、モジュール単位でロガーを取得する。
  - 関数・メソッドの docstring は Google style を採用し、概要・入出力が分かる説明を記述する。
  - `Args` / `Returns` / `Raises` は該当する要素がある場合に記載する。

## 作業ルール
- 必ず作業後に、作業によって生じた変更と `README.md`, `AGENTS.md` の内容差分を確認し、差があれば更新すること。
- タスク依頼時はすぐにコードを書き始めず、まず `{task_design_dir}/` 配下にタスク設計ドキュメントを配置し、レビューを仰ぐこと。
- タスク実行時は適宜「実装タスクリスト」の進捗を更新しながら進めること。
- まとまった変更は小さなコミットに分割する。
- ランタイム設定や手順を変更したら本ファイルを更新すること。

## 環境変数 / シークレット運用
- 環境変数は `.env.development`, `.env.production` から取得する。
- 秘密情報は dotenvx で暗号化し、`encrypted:` 形式で管理する。
- `DOTENV_PUBLIC_KEY_DEVELOPMENT`, `DOTENV_PUBLIC_KEY_PRODUCTION` を利用する。
- `.env.keys` は秘密鍵を含むためコミットしない。

## CI / 品質ゲート
- CI 設定は必須。`python-uv-ci-setup` で `.pre-commit-config.yaml` と `.github/workflows/ci.yml` を整備する。
- 実行コマンドや失敗時の復旧手順は `docs/ai/playbooks/python-uv-ci-setup.md` の記述を正本とする。

## Git戦略: Git Worktree ワークフロー
- ルートディレクトリで `git switch` や `git checkout` によるブランチ切り替えは禁止。
- タスクごとに `.worktrees/<branch-name>/` を作成して作業する。

### 新規タスク着手時の手順
1. `.worktrees/` が存在するか確認し、`.gitignore` に追加されていることを確認する。
2. 新しいタスク開始時に worktree を作成する。
   ```bash
   git worktree add .worktrees/feat/<task-name> -b feat/<task-name>
   ```
3. 必ず `.worktrees/<branch-name>/` 以下を編集対象にする。
4. マージ後は不要 worktree を削除する。
   ```bash
   git worktree remove .worktrees/<branch-name>
   git worktree prune
   ```

## Git コミットメッセージ
**重要: すべてのコミットメッセージは日本語で記述すること。**

- 必ずプレフィックスを使用する (`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`)
- プレフィックスを含めて 50 文字以内
- 現在形（辞書形）または体言止めを使用する
- 末尾に句点（。）を付けない
- 形式: `prefix: メッセージ`

## コミュニケーション
- ユーザーとエージェント間の連絡は日本語で行うこと。
"""


def build_solid_rules() -> str:
    """SOLID/DRY ガイドを返す。"""
    return """# SOLID / DRY ガイドライン

## 目的

設計品質を一定に保つため、SOLID 原則と DRY 原則を実装判断の基準として採用する。

## SOLID

### S: Single Responsibility Principle
- 1 つのモジュールは 1 つの責務のみを持つ。
- 変更理由が複数になる実装は分割する。

### O: Open/Closed Principle
- 既存コードの破壊的変更ではなく、拡張で要件に対応する。
- 条件分岐の増殖より抽象化と差し替えを優先する。

### L: Liskov Substitution Principle
- 置換可能性を壊す継承・実装を禁止する。
- 契約を破る例外仕様や戻り値変更を避ける。

### I: Interface Segregation Principle
- 大きすぎるインターフェースを避ける。
- 利用側が必要な最小契約に分割する。

### D: Dependency Inversion Principle
- 上位層は実装ではなく抽象に依存する。
- 外部 I/O には ports を介して接続する。

## DRY

- 同一ルールが複数箇所に出現する場合は共通化する。
- ただし誤った早期抽象化は避け、責務境界が明確な共通化のみ採用する。

## 運用チェック

- 重複したバリデーションが複数 adapter に存在しないか。
- use case に技術詳細が混入していないか。
- テストしづらい密結合が発生していないか。
"""


def build_code_architecture_rules(package_name: str) -> str:
    """アーキテクチャガイドを返す。"""
    return f"""# コードアーキテクチャ方針

## 採用アーキテクチャ

本プロジェクトは Hexagonal Architecture（Ports and Adapters）を採用する。

## 依存方向

- `src/{package_name}/adapters` -> `src/{package_name}/application`
- `src/{package_name}/application` -> `src/{package_name}/domain`
- `src/{package_name}/ports` は契約のみを保持し、実装は持たない。
- `domain` は外部ライブラリ・フレームワークへ依存しない。

## 層責務

- `domain`: エンティティ、値オブジェクト、ドメインサービス
- `application`: ユースケース、トランザクション境界、アプリケーションサービス
- `ports`: 入出力契約（抽象）
- `adapters`: Web/API/DB/外部サービス連携の実装

## 禁止事項

- domain 層で DB クエリや HTTP 呼び出しを行う。
- adapter 層へビジネスルールを複製する。
- use case で framework 依存型を直接受け取る。
"""


def build_hexagonal_architecture_doc(package_name: str) -> str:
    """Hexagonal 概要ドキュメントを返す。"""
    return f"""# Hexagonal Architecture

## ディレクトリ構成

```text
src/{package_name}/
  adapters/
    inbound/
    outbound/
  application/
    use_cases/
    services/
  domain/
    entities/
    value_objects/
    services/
  ports/
    inbound/
    outbound/
```

## 開発ガイド

1. まず `domain` でビジネスルールを定義する。
2. `application` でユースケースを実装する。
3. 外部 I/O は `ports` に契約を定義する。
4. `adapters` で `ports` の実装を提供する。

## テスト戦略

- 単体テストは `domain` と `application` を中心に行う。
- 結合テストは adapter + 外部依存の接続点を検証する。
- port 契約を満たすことをインターフェーステストで確認する。
"""


def build_product_vision_template() -> str:
    """プロダクトビジョンの初期テンプレートを返す。"""
    fallback = """# プロダクトビジョン

最終更新: <YYYY-MM-DD>
"""
    return load_template(PRODUCT_VISION_TEMPLATE_PATH, fallback)


def build_product_goals_template() -> str:
    """ユーザー到達状態ゴールの初期テンプレートを返す。"""
    fallback = """# ユーザー到達状態ゴール

最終更新: <YYYY-MM-DD>
"""
    return load_template(PRODUCT_GOALS_TEMPLATE_PATH, fallback)


def build_product_milestones_template() -> str:
    """到達ステップの初期テンプレートを返す。"""
    fallback = """# 到達ステップ

最終更新: <YYYY-MM-DD>
"""
    return load_template(PRODUCT_MILESTONES_TEMPLATE_PATH, fallback)


def build_product_progress_template() -> str:
    """進捗スコアボードの初期テンプレートを返す。"""
    fallback = """# 進捗スコアボード

最終更新: <YYYY-MM-DD>
"""
    return load_template(PRODUCT_PROGRESS_TEMPLATE_PATH, fallback)


def build_task_readme(task_design_dir: str) -> str:
    """タスク設計ディレクトリ README を返す。"""
    return f"""# タスク設計書の保存先

このディレクトリにタスク設計書を保存する。

- 全タスク依頼で、作業開始前にタスク設計書の作成を必須とする。
- 保存先: `{task_design_dir}/`
- 命名規則: `YYYYMMDDHHMMSS_{{task-name}}.md`
- 時刻: 初版作成日時（JST）
- `task-name`: 英小文字の kebab-case
- 更新時: 原則ファイル名を変更しない
"""


def build_task_template() -> str:
    """タスク設計テンプレートを返す。"""
    fallback = """# タスク設計書テンプレート

## ファイル命名規則

- 保存先: リポジトリ配下の `docs/task-designs/` に保存する。
- `docs/task-designs/` が存在しない場合は作成してから保存する。
- 形式: `YYYYMMDDHHMMSS_{task-name}.md`
- `YYYYMMDDHHMMSS` は初版作成日時を日本時間（JST）で使用する。
- `task-name` は英小文字の kebab-case を推奨（スペースなし）。
- 更新時は原則ファイル名を変更しない。更新日は本文の `最終更新` を更新する。
- 既存ドキュメントで作成時刻が不明な場合は `YYYYMMDD000000_{task-name}.md` を使用する。
- `README.md` と `_task-design-template.md` は例外（プレフィックス不要）。

例:

- `docs/task-designs/20260101103045_frontend-run-history-delete.md`
- `docs/task-designs/20251224000000_backend-run-history-list-api-auth.md`

## 本文フォーマット

以下の順序で出力すること。該当なしは `該当なし` と明記する。

# タスク設計書: <タイトル>

最終更新: <YYYY-MM-DD>
- ステータス: <下書き(draft) / レビュー待ち(review-ready) / 承認済み(approved) / 保留(blocked) / 実装中(in-progress) / 完了(done)>
- 作成者: <名前>
- レビュー: <担当者>
- 対象コンポーネント: <backend / frontend / docs / infra / data>
- 関連: <リンクや関連設計書>
- チケット/リンク: <Issue/PR/外部リンク>
- 関連ゴールID: <G-01 など。該当なしの場合は `該当なし`>
- 関連マイルストーンID: <M-01 など。該当なしの場合は `該当なし`>

## 0. TL;DR
- <目的と結論を3〜5行で要約>
- <何をどこに追加/変更するか>
- <影響範囲や注意点>

## 1. 背景 / 課題
- <なぜこの変更が必要か>
- <現状の課題や制約>

## 2. ゴール / 非ゴール
### 2.1 ゴール
- <達成したい状態>

### 2.2 非ゴール
- <今回やらないこと>

## 3. スコープ / 影響範囲
- 変更対象: <API/画面/データ/設定など>
- 影響範囲: <利用者/運用/データなど>
- 互換性: <後方互換/破壊的変更の有無>
- 依存関係: <外部API/ライブラリ/他チーム依存>

## 4. 要件
### 4.1 機能要件
- <機能要件>

### 4.2 非機能要件 / 制約
- <性能/可用性/セキュリティ/運用制約>

## 5. 仕様 / 設計
### 5.1 全体方針
- <設計方針>

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| <component / file / API> | <何を変えるか> | <影響> | <補足> |

### 5.3 詳細
#### API
- <エンドポイント/リクエスト/レスポンス/エラー>

#### UI
- <画面/導線/コピー/バリデーション>

#### データモデル / 永続化
- <スキーマ/保存先/移行>

#### 設定 / 環境変数
- <追加/変更/デフォルト値>

### 5.4 代替案と不採用理由
- 代替案A: <案>
  - 不採用理由: <理由>
- 代替案B: <案>
  - 不採用理由: <理由>

## 6. 移行 / ロールアウト
- <段階的リリース/フラグ/リスク低減策>
- ロールバック条件: <切り戻し判断基準>
- ロールバック手順: <手順>

## 7. テスト計画
- 単体: <対象>
- 結合: <対象>
- 手動: <手順>
- LLM/外部依存: <モック方針>
- 合格条件: <何をもってテスト完了とするか>

## 8. 受け入れ基準
- <操作手順と期待結果を列挙>

## 9. リスク / 対策
- <リスクと回避策>

## 10. オープン事項 / 要確認
- <未確定事項・相談事項>
- ※本セクションが埋まっている（=未解消事項がある）場合、**実装は開始しない**。依頼者と実行者で合意が取れ次第、項目を解消してから着手する。

## 11. 実装タスクリスト
- [ ] <実装タスク>
- [ ] <テスト追加>
- [ ] <必要な移行/運用作業>

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [ ] `docs/`（該当ファイルあれば）

## 13. 承認ログ
- 承認者: <名前>
- 承認日時: <YYYY-MM-DD HH:mm>
- 承認コメント: <条件付き承認の場合は条件を明記>

## 実装開始条件
- [ ] ステータスが `承認済み(approved)` である
- [ ] 10. オープン事項が空である
- [ ] 受け入れ基準とテスト計画に合意済み
"""
    return load_template(TASK_DESIGN_TEMPLATE_PATH, fallback)


def build_api_index() -> str:
    """API index テンプレートを返す。"""
    fallback = """# <サービス名> API エンドポイント一覧

最終更新: `<YYYY-MM-DD>`
ベースURL: `<https://api.example.com>`

## 1. 運用ルール

- API実装の変更と同時にこの一覧を更新する。
- 1エンドポイントにつき詳細ドキュメントは1ファイルにする。
- 一覧リンク切れを残さない。

## 2. 共通仕様

### 2.1 認証

- 対象: `<例: /api/v1/*>`
- ヘッダー: `<例: Authorization: Bearer <ID_TOKEN>>`
- 未認証時: `<例: 401 Unauthorized>`

### 2.2 共通ヘッダー

- `Content-Type: application/json`（ボディありの場合）
- `X-Request-Id`（任意）

### 2.3 エラーフォーマット

```json
{
  "error": {
    "message": "Authorization header is missing",
    "type": "http_error",
    "details": {
      "field": "optional"
    }
  }
}
```

### 2.4 タイムアウト・リトライ方針（任意）

- タイムアウト: `<例: 30s>`
- リトライ: `<例: GETのみ最大2回>`

## 3. エンドポイント一覧

### <ドメイン名1>

- [GET /path](./sample-get.md) - `<概要>`
- [POST /path](./sample-post.md) - `<概要>`

### <ドメイン名2>

- [PATCH /path/{id}](./sample-patch.md) - `<概要>`
- [DELETE /path/{id}](./sample-delete.md) - `<概要>`

## 4. 非推奨 / 廃止（任意）

- `GET /legacy/path` - `<廃止日/代替API>`

## 5. 変更履歴（任意）

- `<YYYY-MM-DD>`: `<変更内容要約>`
"""
    return load_template(API_INDEX_TEMPLATE_PATH, fallback)


def build_api_endpoint_template() -> str:
    """API エンドポイントテンプレートを返す。"""
    fallback = """# <METHOD> <PATH> — <機能名>

一覧: [<サービス名> API エンドポイント一覧](<indexファイルへの相対パス>)
最終更新: `<YYYY-MM-DD>`

## 1. 概要

- 目的: `<このAPIが何をするか>`
- 利用者/権限: `<例: ログイン済みユーザーのみ>`
- 副作用: `<例: DBへ保存 / 非同期ジョブ起動>`

## 2. リクエスト

### 2.1 ヘッダー

| 項目 | 必須 | 値 | 説明 |
| --- | --- | --- | --- |
| Authorization | Yes | Bearer `<ID_TOKEN>` | 認証が必要な場合 |
| Content-Type | Conditional | application/json | ボディありの場合 |

### 2.2 パスパラメータ

| name | type | required | 説明 | 例 |
| --- | --- | --- | --- | --- |
| id | string | Yes | 対象ID | `abc123` |

> パスパラメータがない場合は「なし」と明記する。

### 2.3 クエリパラメータ

| name | type | required | デフォルト | 説明 | 例 |
| --- | --- | --- | --- | --- | --- |
| limit | integer | No | 20 | 取得件数 | `10` |

> クエリパラメータがない場合は「なし」と明記する。

### 2.4 リクエストボディ

| field | type | required | 制約 | 説明 | 例 |
| --- | --- | --- | --- | --- | --- |
| title | string | Yes | 1..120文字 | タイトル | `日報` |

> ボディがない場合は「なし」と明記する。

### 2.5 リクエスト例

```bash
curl -X <METHOD> '<BASE_URL><PATH>' \
  -H 'Authorization: Bearer <ID_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"example":"value"}'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | 成功データを返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| id | string | No | リソースID | `abc123` |

### 3.3 成功レスポンス例

```json
{
  "id": "abc123"
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | validation_error | invalid request | パラメータ不正 | 入力修正 |
| 401 | http_error | unauthorized | 認証失敗 | 再ログイン |
| 404 | http_error | not found | 対象なし | 画面再読込 |
| 500 | internal_error | internal server error | サーバー異常 | リトライ/問い合わせ |

## 5. 備考

- タイムアウト: `<例: 30s>`
- 冪等性: `<例: Idempotency-Keyで担保>`
- 非同期処理: `<例: 202でjob_id返却>`

## 6. 実装同期メモ

- 関連実装ファイル: `<path/to/router>`, `<path/to/handler>`
- 関連テスト: `<path/to/test>`
- 未解決事項: `<TODO(要実装確認)>`
"""
    return load_template(API_ENDPOINT_TEMPLATE_PATH, fallback)


def build_env_file(environment: str) -> str:
    """環境別 .env テンプレートを返す。"""
    suffix = environment.upper()
    return f"""#/-------------------[DOTENV_PUBLIC_KEY]--------------------/
#/            public-key encryption for .env files          /
#/----------------------------------------------------------/
DOTENV_PUBLIC_KEY_{suffix}="<REPLACE_WITH_PUBLIC_KEY>"

APP_ENV="{environment}"
LOG_LEVEL="INFO"

# --- 設定値 (平文) ---
DATABASE_URL="postgresql://app:app@localhost:5432/app"

# --- 秘密情報 (暗号化) ---
OPENAI_API_KEY="encrypted:<REPLACE_WITH_ENCRYPTED_VALUE>"
"""


def parse_args() -> argparse.Namespace:
    """CLI 引数を解析する。"""
    parser = argparse.ArgumentParser(description="Python プロジェクト初期構成を生成する")
    parser.add_argument("--target", default=".", help="生成先ルートディレクトリ")
    parser.add_argument("--project-name", required=True, help="プロジェクト名")
    parser.add_argument("--description", default="<TBD>", help="プロジェクト説明")
    parser.add_argument("--package-name", help="Python パッケージ名")
    parser.add_argument("--python-version", default="3.12+", help="Python バージョン表記")
    parser.add_argument(
        "--task-design-dir",
        help="タスク設計ディレクトリ（既定: docs/task-designs、legacy: docs/tasks）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存ファイルを上書きする",
    )
    return parser.parse_args()


def main() -> None:
    """メイン処理。"""
    args = parse_args()
    target = Path(args.target).resolve()
    package_name = args.package_name or normalize_package_name(args.project_name)
    task_design_dir = detect_task_design_dir(target, args.task_design_dir)

    report: dict[str, list[str]] = {
        "created_dirs": [],
        "created": [],
        "updated": [],
        "skipped": [],
        "unchanged": [],
    }

    directories = [
        target / "src" / package_name / "adapters" / "inbound",
        target / "src" / package_name / "adapters" / "outbound",
        target / "src" / package_name / "application" / "use_cases",
        target / "src" / package_name / "application" / "services",
        target / "src" / package_name / "domain" / "entities",
        target / "src" / package_name / "domain" / "value_objects",
        target / "src" / package_name / "domain" / "services",
        target / "src" / package_name / "ports" / "inbound",
        target / "src" / package_name / "ports" / "outbound",
        target / "tests" / "unit",
        target / "tests" / "integration",
        target / "docs" / "rules" / "solid",
        target / "docs" / "rules" / "code_architecture",
        target / "docs" / "architecture",
        target / "docs" / "api",
        target / "docs" / "product",
        target / Path(task_design_dir),
    ]
    ensure_directories(directories, report)

    files = {
        target / "AGENTS.md": build_agents_md(
            project_name=args.project_name,
            description=args.description,
            python_version=args.python_version,
            task_design_dir=task_design_dir,
        ),
        target / "docs" / "rules" / "solid" / "README.md": build_solid_rules(),
        target / "docs" / "rules" / "code_architecture" / "README.md": build_code_architecture_rules(package_name),
        target / "docs" / "architecture" / "hexagonal-architecture.md": build_hexagonal_architecture_doc(package_name),
        target / Path(task_design_dir) / "README.md": build_task_readme(task_design_dir),
        target / Path(task_design_dir) / "_task-design-template.md": build_task_template(),
        target / "docs" / "api" / "index.md": build_api_index(),
        target / "docs" / "api" / "_endpoint_template.md": build_api_endpoint_template(),
        target / "docs" / "product" / "vision.md": build_product_vision_template(),
        target / "docs" / "product" / "goals.md": build_product_goals_template(),
        target / "docs" / "product" / "milestones.md": build_product_milestones_template(),
        target / "docs" / "product" / "progress.md": build_product_progress_template(),
        target / ".env.development": build_env_file("development"),
        target / ".env.production": build_env_file("production"),
    }

    for path, content in files.items():
        write_text_file(path, content, force=args.force, report=report)

    ensure_gitignore(target, report)

    print(f"Target: {target}")
    print(f"Package: {package_name}")
    print(f"Task design dir: {task_design_dir}")
    print("")

    for key in ["created_dirs", "created", "updated", "skipped", "unchanged"]:
        items = report[key]
        print(f"{key}: {len(items)}")
        for item in items:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
