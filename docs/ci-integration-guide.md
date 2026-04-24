# CI Integration Guide

Yagra ワークフロー定義を GitHub Actions で自動検証するためのガイドです。

## 概要

Yagra ワークフロー（`workflow.yaml`）は YAML ファイルであるため、Git で管理して CI で自動検証できます。
`yagra validate` は PR ごとにワークフロー定義の整合性を確認し、構造エラーや参照ミスを本番反映前に検出します。

**主なユースケース:**
- PR レビュー時にワークフロー変更を自動検証する
- `yagra explain` の出力を PR コメントに貼り付けて、変更内容を可視化する
- 非エンジニアが WebUI で編集した YAML を、マージ前に品質ゲートを通過させる

## クイックスタート

### 1. サンプルワークフローをコピー

`.github/workflows/validate-example.yml` を参考に、リポジトリの `.github/workflows/` にコピーします。

```bash
cp .github/workflows/validate-example.yml .github/workflows/yagra-validate.yml
```

### 2. ワークフローファイルのパスを設定

`validate-example.yml` の検証対象パスを、実際のワークフローファイルの場所に合わせます。
デフォルトでは `examples/*/workflow.yaml` を検証する glob を使用しています。

```yaml
# デフォルト: examples/ 配下の workflow.yaml を検証（Yagra リポジトリ準拠）
for f in examples/*/workflow.yaml; do ... done

# 特定ディレクトリを検索する場合（find で再帰検索する例）
WORKFLOW_FILES=$(find ./workflows -name "workflow.yaml")
```

### 3. yagra をインストール

```yaml
- name: Install yagra
  run: uv pip install --system yagra
```

開発中のコードを使う場合:

```yaml
- name: Install yagra (local)
  run: uv pip install --system -e .
```

## yagra validate の仕様

### 終了コード

| 終了コード | 意味 |
|-----------|------|
| `0` | バリデーション成功（valid） |
| `1` | バリデーション失敗（invalid） |
| `2` | 引数エラー |

GitHub Actions では、`exit code 1` でジョブが失敗します。

### JSON 出力

`--format json` を指定すると、構造化されたバリデーション結果を JSON で取得できます。
エラー詳細・修正提案を含むため、PR コメントへの埋め込みに適しています。

```bash
yagra validate --workflow workflow.yaml --format json
```

出力例（invalid の場合）:

```json
{
  "is_valid": false,
  "issues": [
    {
      "code": "structure_error",
      "message": "ノード 'my_node' が edges で参照されていますが定義されていません",
      "location": ["edges", 0, "target"],
      "severity": "error",
      "context": {
        "actual_value": "my_node",
        "available_values": ["router", "planner", "finish"],
        "suggestion": "planner"
      }
    }
  ]
}
```

### stdin 対応

パイプ経由で YAML を渡せます。スクリプトやエージェントとの連携に便利です。

```bash
cat workflow.yaml | yagra validate --workflow -
echo $?  # 0=valid, 1=invalid
```

## yagra explain で変更内容を可視化

`yagra explain` はワークフローを実行せずに静的解析し、実行パス・必要ハンドラー・変数フローを出力します。
PR コメントに埋め込むことで、レビュアーがコードを読まずにフロー変更を把握できます。

```bash
yagra explain --workflow workflow.yaml --format text
```

出力例:

```
Workflow: my-workflow
Nodes: 3
  - router (router_handler)
  - planner (llm)
  - finish (finish_handler)

Edges: 3
  router -[needs_plan]-> planner
  router -[direct_answer]-> finish
  planner -> finish

Execution Paths:
  Path 1: router -> planner -> finish
  Path 2: router -> finish

Required Handlers:
  - router_handler
  - llm (built-in)
  - finish_handler
```

### PR コメントに埋め込むサンプル

`scripts/pr-comment-example.sh` を使うと、`yagra validate` と `yagra explain` の結果を PR コメントに投稿できます。

```bash
GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }} \
GITHUB_REPO=${{ github.repository }} \
  bash scripts/pr-comment-example.sh workflows/my-workflow.yaml ${{ github.event.pull_request.number }}
```

GitHub Actions での完全な例は `.github/workflows/validate-example.yml` を参照してください。

## 高度な設定

### 変更されたファイルのみを検証

PR で変更されたワークフローファイルのみを検証することで、CI 時間を短縮できます。

```yaml
- name: Get changed workflow files
  id: changed-files
  run: |
    CHANGED=$(git diff --name-only origin/${{ github.base_ref }}...HEAD \
      | grep 'workflow\.yaml$' || true)
    echo "files=$CHANGED" >> "$GITHUB_OUTPUT"

- name: Validate changed workflows
  if: steps.changed-files.outputs.files != ''
  run: |
    for f in ${{ steps.changed-files.outputs.files }}; do
      yagra validate --workflow "$f" --format json
    done
```

### bundle-root の設定

`prompt_ref` で外部 YAML ファイルを参照している場合、`--bundle-root` でベースディレクトリを指定します。

```bash
yagra validate --workflow workflows/my-workflow.yaml --bundle-root .
```

### MCP サーバーとの連携

`yagra mcp` を使うと、コーディングエージェントが MCP プロトコル経由でバリデーションを実行できます。
エージェントが YAML を生成→検証→修正するループを自律的に回せます。

詳細: [agent-integration-guide.md](agent-integration-guide.md)

## トラブルシューティング

### `yagra: command not found`

```yaml
- name: Install yagra
  run: pip install yagra  # または uv pip install --system yagra
```

### バリデーションが失敗するが原因が分からない

JSON 形式で詳細なエラー情報を確認してください。

```bash
yagra validate --workflow workflow.yaml --format json | jq '.issues[]'
```

`context.suggestion` フィールドに修正候補が含まれている場合があります。

### `prompt_ref` の解決に失敗する

`--bundle-root` でプロンプトファイルのベースディレクトリを指定してください。

```bash
yagra validate --workflow workflow.yaml --bundle-root ./
```

## 関連ドキュメント

- [agent-integration-guide.md](agent-integration-guide.md) - コーディングエージェントとの連携
- `.github/workflows/validate-example.yml` - GitHub Actions サンプル
- `scripts/pr-comment-example.sh` - PR コメント投稿スクリプト
