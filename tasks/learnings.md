# タスク間学習ログ

**最終更新**: 2026-04-24
**蓄積開始**: 2026-04-24（Task #3 完了時）

> agent-company-v2 Phase 2f の知見蓄積ルールに従う。PMの結果レポートから「技術的発見 / プロジェクト固有パターン / PMO指摘パターン / 環境的発見」を体系的に記録する。2回以上繰り返されるパターンは Developer Spec のデフォルトに昇格する。

---

## 技術的発見

| Task | 知見 | 影響範囲 |
|------|------|---------|
| #3 | `yagra validate --workflow <path>` に `--bundle-root "$(dirname "$f")"` を付けないと `examples/*/workflow.yaml` の `prompt_ref` 解決に失敗する | examples/ 配下を検証する CI / スクリプト / MCP `validate_workflow` 利用箇所すべて |
| #3 | GitHub Actions で examples 検証する場合は `for f in examples/*/workflow.yaml; do ... done` + `shopt -s nullglob` + 0-match ガード（`if [ -z "$files" ]; then exit 1; fi`）が必要。silent success を防ぐため | CI workflow を書くとき / Yagra 以外のワークフロー CI にも応用可能 |
| #3 | `uv sync --locked --dev` は PyPI 公開版ではなく開発中のコードで検証する。`uv pip install --system yagra` は false negative/positive のリスクあり | CI における Yagra 自身のドッグフーディング |

## プロジェクト固有パターン

| Task | パターン | 適用場面 |
|------|---------|---------|
| #3 | 新 GitHub Actions workflow を追加する際は既存 `ci.yml` のバージョンラインを継承する（`actions/checkout@v6` / `actions/setup-python@v6` / `astral-sh/setup-uv@v7`） | 新 workflow ファイル作成時 |
| #3 | `main` ブランチには branch protection あり（REVIEW_REQUIRED）。直接 push / マージ不可。全変更は feature branch → PR → user 承認マージの経路を通る | 全タスク、特に PO 側の tracking 文書更新時の commit 運用 |
| #3 | 新 workflow には必ず `concurrency: group: <wf-name>-${{ github.ref }}` + `cancel-in-progress: true` を入れる（PMO 指摘で標準化） | 全 CI workflow |
| #3 | 機能追加・修正は CHANGELOG.md の `[Unreleased]` セクションに Added / Fixed 等のカテゴリで追記する | すべての user-visible 変更 |

## PMO指摘パターン分析

| 指摘カテゴリ | 頻度 | 対策 |
|-------------|:----:|------|
| concurrency 制御の追加（#3 で 1 回） | 1 | 2 回目以降出たら Developer Spec の CI workflow テンプレートに必須項目として昇格 |
| 0-match 時の silent success 防止（#3 で 1 回） | 1 | 2 回目以降出たら同様に昇格 |
| CHANGELOG 追記（#3 で 1 回） | 1 | 2 回目以降出たら Mission Brief のチェックリスト標準項目に昇格 |

> 現時点ではどのカテゴリも頻度 1 のため、昇格は見送り。#4 以降で繰り返し出現するか監視する。

## 環境的発見

| 項目 | 内容 | 対処 |
|------|------|------|
| PM Agent 内の Task(Agent) ツール不在 | Claude Code Agent（general-purpose opus）から起動した PM 相当 Agent は、さらなる subagent（Task/Agent）を起動できない環境制約あり | PM が Developer/PMO 工程を sequentially 代行（ロール境界を出力で明確化、検証証拠を分離記録）。agent-company-v2 skill の `references/architecture.md` が推奨する自律選択が物理的に取れないケース |
| playwright chromium 欠落 | `tests/integration/test_studio_js_utils.py` の 33 テストが `BrowserType.launch: Executable doesn't exist` で失敗する pre-existing 状態 | 今回の変更と無関係。`playwright install chromium` を実行すれば解消するが、現状では未影響テストとして記録・スキップ判断 |

---

## 運用メモ

- **PM Agent 起動時**: 上記「技術的発見 / プロジェクト固有パターン」から、今回のタスクに該当するものを抽出して渡す（全文は渡さない）
- **Developer Spec へ昇格する閾値**: PMO 指摘カテゴリが 2 回以上繰り返されたら対策列を Developer Spec のデフォルトに昇格する
- **環境制約の扱い**: PM Agent 内 subagent 不在のような制約は、スキル側（agent-company-v2）の harness 更新候補として ssr にフィードバックする可能性あり
