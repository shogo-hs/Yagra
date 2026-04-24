# 実装計画: `.github/workflows/validate-example.yml` 実在化

**layer:** PM 計画
**created:** 2026-04-24
**parent intent:** `tasks/20260424085835_intent-add-validate-example-workflow.md`

---

## ゴール

`docs/ci-integration-guide.md` から参照される `.github/workflows/validate-example.yml` を実在化し、examples/*/workflow.yaml 全 6 個が CI で継続検証される状態にする。

## タスク複雑度: S

- 変更ファイル: 1 ファイル新規（必要時 `docs/ci-integration-guide.md` の微修正）
- 設計判断は実質 1 つ（yagra のインストール方法 = `uv sync --locked --dev` + `uv run` / 合意済み）
- Developer 数: **2** （skill 規定：実装 + 品質補完）

## コードベース調査結果（PM 直接調査、Explore Agent 省略）

### 既存 CI (`ci.yml`) のテンプレート
- `on: pull_request / push.branches: [main]` の構造
- `actions/checkout@v6` + `actions/setup-python@v6` (Python 3.12) + `astral-sh/setup-uv@v7` (enable-cache: true)
- `uv sync --locked --dev --all-extras`
- `permissions: contents: read, pull-requests: write`

### ガイド (`docs/ci-integration-guide.md`) の期待
- `cp .github/workflows/validate-example.yml .github/workflows/yagra-validate.yml` でユーザーがコピー流用
- `find . -name "workflow.yaml"` で検索するスニペット例示
- `--format json` 使用例、`--bundle-root` 言及
- `scripts/pr-comment-example.sh` が既存（`yagra validate` + `yagra explain` を PR コメントに貼る補助）

### examples/ 構造（6 個）
- `examples/human-review/workflow.yaml`
- `examples/llm-basic/workflow.yaml`
- `examples/llm-streaming/workflow.yaml`
- `examples/llm-structured/workflow.yaml`
- `examples/multi-agent/workflow.yaml`
- `examples/tool-use/workflow.yaml`

### PM 事前検証結果
`for f in examples/*/workflow.yaml; do uv run yagra validate --workflow "$f" --bundle-root "$(dirname "$f")" --format json; done` を PM が手元で実行し、**全 6 個が `is_valid: true`** で通過することを確認済み。

## 実装方針

### 1. `.github/workflows/validate-example.yml` の構成

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
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
      - run: uv sync --locked --dev
      - name: Validate all examples/*/workflow.yaml
        run: |
          set -e
          found=0
          for f in examples/*/workflow.yaml; do
            if [ -f "$f" ]; then
              echo "::group::Validating $f"
              uv run yagra validate \
                --workflow "$f" \
                --bundle-root "$(dirname "$f")" \
                --format json
              echo "::endgroup::"
              found=$((found + 1))
            fi
          done
          if [ "$found" -eq 0 ]; then
            echo "::error::No examples/*/workflow.yaml found"
            exit 1
          fi
          echo "Validated $found workflow(s)"
```

### 2. ガイド整合性確認

- `docs/ci-integration-guide.md` の参照（行 19, 22, 27, 145, 214）はすべて実在ファイルを指すようになる → 内容矛盾なし、**原則無変更**
- ただし、`.github/workflows/validate-example.yml` の実装が "`find . -name workflow.yaml`" パターンと食い違う場合（今回は `examples/*/workflow.yaml` を固定列挙する簡易版）、ガイド側の説明箇所で軽微な補足が必要になる可能性がある → Dev1 判断

## 成功基準（PO-PM Contract 転記）

| # | 基準 | 検証コマンド |
|---|------|------------|
| 1 | ファイル実在 | `test -f .github/workflows/validate-example.yml && echo OK` |
| 2 | トリガ | `uv run python -c "import yaml; c=yaml.safe_load(open('.github/workflows/validate-example.yml')); on=c.get(True,c.get('on',{})); assert 'pull_request' in on and 'push' in on; print('OK')"` |
| 3 | examples 検証 | `for f in examples/*/workflow.yaml; do uv run yagra validate --workflow "$f" --bundle-root "$(dirname "$f")" --format json > /dev/null \|\| exit 1; done; echo OK` |
| 4 | ガイド参照整合 | `grep -n "validate-example.yml" docs/ci-integration-guide.md` |
| 5 | pre-commit | `uv run pre-commit run --all-files` |
| 6 | CI 併存 | `test -f .github/workflows/ci.yml && test -f .github/workflows/validate-example.yml` |

## リスク

| リスク | 対策 |
|-------|------|
| GitHub Actions YAML の `on:` キーが Python `yaml.safe_load` で `True` ブール値にパースされる | 成功基準 #2 の検証コマンドで `c.get(True, c.get('on', {}))` と両対応 |
| `uv sync --locked --dev` が CI 環境で失敗（Python 3.12 前提なのに runner が別版） | `actions/setup-python@v6` で `python-version: "3.12"` を固定 |
| `--all-extras` を付けないと MCP extras 系の問題が起きる | Dev1 が `uv sync --locked --dev` で検証 NG なら `--all-extras` に変更（事前検証で `--dev` のみでも yagra CLI は動くと確認済み） |
| `examples/*/workflow.yaml` のマッチ数が 0 になったら job が silent-pass するサイレント破壊 | 上記スニペットの `found=0` カウントと最後の `exit 1` で防止 |

## Developer 配分（V2 Sequential）

| # | Model | 予想される貢献領域（Dev 自律決定） |
|---|-------|----------------------------|
| Developer 1 | sonnet | workflow YAML 実装 + ローカル検証（成功基準 1-4, 6） |
| Developer 2 | sonnet | pre-commit 検証 + サイレント破壊防止の補強・エッジケース（成功基準 5 + 堅牢性） |

**注:** PM はロールを割り振らない。Dev1 commit の diff を Dev2 が見て自律決定する。Dev1 が全部カバーしていれば Dev2 は棄権してよい。

## Developer 起動時の必須条件

- Feature branch `feature/add-validate-example-workflow` 上で作業
- `uv add` / `uv remove` / `uv sync` のみ。`pip install` 禁止
- コミットメッセージは日本語・Conventional Commits・50 文字以内目安
- 新規テスト不要（CI workflow YAML は実際に PR を作らないと実ジョブ起動しないため）。その代わり「ローカルでの examples 検証ループ通過」を検証証拠とする
- PM が Dev1 → Dev2 の間に pytest / pre-commit run --all-files を統合スモークとして実行する
