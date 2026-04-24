# Mission Brief: `.github/workflows/validate-example.yml` 実在化

**layer:** PM → Developer 群（Sequential）
**created:** 2026-04-24
**parent:** `tasks/20260424085623_contract-po-pm-add-validate-example-workflow.md`

---

## ミッション

### ゴール

`docs/ci-integration-guide.md` が参照している `.github/workflows/validate-example.yml` を**実ファイルとしてリポジトリに作成**し、`examples/*/workflow.yaml` 全 6 個が CI で継続検証される状態にする。あわせてガイドと実装の矛盾がない状態を確保する。

### 成功基準

| # | 基準 | 検証コマンド | 実質性チェック |
|---|------|------------|--------------|
| 1 | `.github/workflows/validate-example.yml` が実在し、有効な GitHub Actions YAML | `test -f .github/workflows/validate-example.yml && uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/validate-example.yml')); print('OK')"` | 中身が空でなくパースに成功 |
| 2 | トリガに `pull_request` と `push (main)` を含む | `uv run python -c "import yaml; c=yaml.safe_load(open('.github/workflows/validate-example.yml')); on=c.get(True,c.get('on',{})); assert 'pull_request' in on and 'push' in on, on; print('OK')"` | `on:` が `True` にパースされる問題に対応 |
| 3 | examples 全 6 個を検証するループがローカルで緑通過 | `set -e; found=0; for f in examples/*/workflow.yaml; do uv run yagra validate --workflow "$f" --bundle-root "$(dirname "$f")" --format json > /dev/null; found=$((found+1)); done; test "$found" -eq 6 && echo OK` | 6 個すべて is_valid:true で exit 0 |
| 4 | `docs/ci-integration-guide.md` の参照と実装が矛盾しない | `grep -c "validate-example.yml" docs/ci-integration-guide.md` が 0 でない + 全参照先ファイルが実在 | 参照がガイド側に残りつつ、実体もある |
| 5 | `uv run pre-commit run --all-files` 全件 Passed | `uv run pre-commit run --all-files` | ruff format / ruff check / mypy すべて Passed |
| 6 | 既存 `ci.yml` と併存（衝突しない） | `test -f .github/workflows/ci.yml && test -f .github/workflows/validate-example.yml && echo OK` | 両ファイルが同時に存在 |

### コードベース状況

#### 既存 CI (`.github/workflows/ci.yml`) のパターン（参考テンプレート）

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
  pull-requests: write
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
      - run: uv sync --locked --dev --all-extras
```

→ 新規 `validate-example.yml` もこのバージョンラインに揃えること。

#### ガイド (`docs/ci-integration-guide.md`) の参照（5 箇所）

- 行 19, 22: `cp .github/workflows/validate-example.yml .github/workflows/yagra-validate.yml` の手順
- 行 27: `find` コマンドのパスを差し替える旨の説明
- 行 145: 「完全な例」へのリンク
- 行 214: 「関連ドキュメント」でのリンク

→ これらの参照は現状ガイドに存在しており、実ファイル作成後は**齟齬解消**となる。**ガイドは原則変更しない**（矛盾が発生する場合のみ最小限の修正）。

#### examples 構造（全 6 個）

```
examples/human-review/workflow.yaml
examples/llm-basic/workflow.yaml
examples/llm-streaming/workflow.yaml
examples/llm-structured/workflow.yaml
examples/multi-agent/workflow.yaml
examples/tool-use/workflow.yaml
```

**PM 事前検証結果:** `for f in examples/*/workflow.yaml; do uv run yagra validate --workflow "$f" --bundle-root "$(dirname "$f")" --format json; done` を PM ローカルで実行し、**全 6 個が `is_valid: true`** を確認済み。よって成功基準 #3 の緑通過は現行 yagra で担保されている。

#### 補助スクリプト

- `scripts/pr-comment-example.sh` が存在。ガイドからは参照されているが、今回のタスクでは**変更しない**（Out of Scope）。workflow から呼び出すかはオプション。最小実装では呼び出さない方針。

### アーキテクチャ方針

- **GitHub Actions workflow の原則**: 1 job = 1 目的。`validate-examples` ジョブは「examples/*/workflow.yaml を yagra validate にかける」ことだけに集中させる。
- **既存 `ci.yml` と独立**: 共通する setup ステップはあえて共有しない（ガイドが独立ファイルを前提としているため）。
- **uv で現行コード検証**: `uv pip install --system yagra` ではなく `uv sync --locked --dev` + `uv run yagra` を使う（PO-PM 合意）。これにより Yagra リポジトリ内での validate は**現在開発中のコード**で走る。
- **サイレント破壊防止**: `examples/*/workflow.yaml` のマッチ数が 0 のとき job が silent-pass しないよう、カウンタ変数と `exit 1` ガードを入れる。

### 品質基準

- **GitHub Actions YAML のベストプラクティス**:
  - `permissions:` は最小権限（`contents: read` のみで十分）
  - アクションはバージョン固定（`@v6`, `@v7` 等、既存 `ci.yml` と同じ）
  - step 名に日本語または英語の明確な名前を付ける
  - `::group::` / `::endgroup::` で長い出力を折り畳む
- **エラーハンドリング**:
  - `set -e`（shell 内でエラー即時停止）
  - 0 マッチ時の exit 1 ガード
  - 1 つでも validate 失敗したらジョブ fail
- **シェルスクリプトの安全性**:
  - 変数展開は `"$var"` で quote
  - `for f in examples/*/workflow.yaml` で glob を直接使う（`find` は不要だが、ガイドが `find` 言及しているのでどちらでもよい。`for` が簡潔）

### コーディング規約

- プロジェクト全体で YAML のインデントは 2 スペース
- コメントは日本語 or 英語どちらでも可（既存 ci.yml は英語ステップ名、内部コメントなし）
- 既存 workflow と同じ構造感（`name:` → `on:` → `permissions:` → `jobs:` の順序）

### 制約

#### In Scope
- `.github/workflows/validate-example.yml` の新規作成（本体）
- ガイドとの矛盾が発生した場合のみ `docs/ci-integration-guide.md` の最小限の文言修正

#### Out of Scope
- 既存 `.github/workflows/ci.yml` / `docs.yml` / `publish.yml` の変更
- `scripts/pr-comment-example.sh` の変更（workflow からは呼び出さない最小実装）
- 「変更ファイルのみ検証」のような高度な最適化（将来タスク）
- Yagra handler 実装や examples/ 配下の YAML 変更
- 新規 pytest テストの作成（CI workflow YAML のテストは PR 起動時の実ジョブで担保）

#### 禁止事項
- `pip install` / `uv pip install` の使用（`uv add / uv remove / uv sync` のみ）
- `actions/checkout@v4` 等の古いメジャー（`ci.yml` は `@v6` 系）
- 「変更ファイル差分だけ検証」のような高度なロジック（最小実装から逸脱）
- `actions/cache@v3` 等の旧バージョン（`ci.yml` は `@v5` 系）
- 秘密情報の記述（`GITHUB_TOKEN` 等は workflow-scoped の自動供給で足りる）

### 推奨実装スケッチ

```yaml
name: Validate Example Workflows

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  validate-examples:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Set up uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      - name: Sync dependencies
        run: uv sync --locked --dev

      - name: Validate examples/*/workflow.yaml
        run: |
          set -e
          found=0
          for f in examples/*/workflow.yaml; do
            if [ -f "$f" ]; then
              echo "::group::$f"
              uv run yagra validate \
                --workflow "$f" \
                --bundle-root "$(dirname "$f")" \
                --format json
              echo "::endgroup::"
              found=$((found + 1))
            fi
          done
          if [ "$found" -eq 0 ]; then
            echo "::error::No examples/*/workflow.yaml matched the glob"
            exit 1
          fi
          echo "Validated $found workflow(s)"
```

上記は指針であり、**Developer が合理的な変更を加えてよい**（例: `--all-extras` を付ける、ステップ名を調整する等）。ただし成功基準 #1-#6 を全て満たすこと。

### 検証手順（Developer が必ず実行）

Developer は以下を**実行して出力を記録**すること。「通るはず」では受け付けない:

1. `test -f .github/workflows/validate-example.yml && echo OK`
2. `uv run python -c "import yaml; c=yaml.safe_load(open('.github/workflows/validate-example.yml')); on=c.get(True,c.get('on',{})); assert 'pull_request' in on and 'push' in on; print('OK')"`
3. `for f in examples/*/workflow.yaml; do uv run yagra validate --workflow "$f" --bundle-root "$(dirname "$f")" --format json > /dev/null || exit 1; done; echo OK`
4. `grep -n "validate-example.yml" docs/ci-integration-guide.md`
5. `uv run pre-commit run --all-files`
6. `test -f .github/workflows/ci.yml && test -f .github/workflows/validate-example.yml && echo OK`

すべてのコマンド出力を**検証証拠**テーブルに記録すること。

### 成果物のコミット

Feature branch `feature/add-validate-example-workflow` 上で:
- コミットメッセージ: 日本語・Conventional Commits プレフィックス（例: `chore(ci): validate-example.yml を追加し examples/ を検証`）
- 50 文字以内目安
- body には成功基準の番号と対応を記載すると PMO レビューで助かる
