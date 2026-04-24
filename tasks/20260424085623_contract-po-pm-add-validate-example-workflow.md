# PO-PM Task Contract: #3 `.github/workflows/validate-example.yml` 実在化

**layer:** PO → PM
**created:** 2026-04-23
**status:** aligned
**task size:** S（CI workflow 新規作成、単一ファイル + 既存 docs 参照確認）
**process path:** 簡易（アライメント Agent 省略、Step 4 へ直接）

---

## ビジョンコンテキスト（PO観点）

### このタスクの位置づけ
ビジョン整合性監査で検出した **Critical C3** の解消。`docs/product/vision.md` の Phase 4（Approve & Update）「CI Integration」が実証サンプルとして機能するための欠落ピース。

- `docs/ci-integration-guide.md` が `.github/workflows/validate-example.yml` を複数箇所で参照しているが、ファイルが実在しない
- クイックスタート手順（`cp .github/workflows/validate-example.yml .github/workflows/yagra-validate.yml`）が辿れない状態

### 期待する成果
CI 統合を真似ようとしたユーザーが、リポジトリ内の実ファイルをコピーしてそのまま使える状態にする。同時に、この CI が Yagra 自身の examples/ に対しても回り、llm-basic 他 5 個の workflow.yaml を継続検証する。

### 優先度の根拠
Must — ビジョン整合性監査 Critical C3。Phase 1 ゲートの必須解消項目。#2 と独立で実装可能。

### 品質・スコープの判断基準
- **妥協してよい点**:
  - 「変更ファイルのみ検証」等の高度な設定は含めなくてよい（ガイド側で説明されているが基本実装のみで可）
  - PR コメント投稿機能はオプション（`scripts/pr-comment-example.sh` は既存、必要なら CI から参照するのみ）
- **妥協してはいけない点**:
  - `docs/ci-integration-guide.md` の記載と実装が矛盾しないこと
  - 既存 examples/ 全ての workflow.yaml で CI が緑通過すること
  - 既存 CI (`ci.yml` 内の `quality` job) と互換・衝突しないこと
  - Yagra プロジェクトの uv/Python 3.12 方針に従うこと

---

## 技術コンテキスト（PM観点）

### 現状（PO 調査済み）
- `.github/workflows/` は `ci.yml` / `docs.yml` / `publish.yml` のみ。`validate-example.yml` は**未作成**
- `ci.yml` は Python 3.12 + `astral-sh/setup-uv@v7` + `uv sync --locked --dev --all-extras` を使用
- `docs/ci-integration-guide.md` の記述:
  - トリガ: `pull_request` + `push`（main）想定
  - `uv pip install --system yagra` 推奨（CI 用）
  - `find . -name "workflow.yaml"` で検索し `yagra validate` を走らせる想定
  - `--format json` 併用例、`--bundle-root` 言及
  - `scripts/pr-comment-example.sh` が既に存在しそこから呼び出し可能
- Yagra の `examples/*/workflow.yaml` は全 6 個（human-review, llm-basic, llm-streaming, llm-structured, multi-agent, tool-use）

### 技術的アプローチ（推奨）
1. `.github/workflows/validate-example.yml` を新規作成
2. トリガ: `pull_request` + `push (main)`
3. 手順:
   - checkout
   - uv セットアップ（既存 `ci.yml` と同じ Python 3.12 + setup-uv@v7）
   - `uv sync --locked --dev` （`--all-extras` は必要なら）
   - `examples/*/workflow.yaml` を列挙して順次 `uv run yagra validate --workflow "$f" --bundle-root "$(dirname "$f")" --format json`
   - 1 個でも失敗したら job exit 1
4. `docs/ci-integration-guide.md` の参照（`yagra validate` 使用例、インストール手順）と整合性確保
5. README 等に特段の追記不要（ガイドは既存）

### 技術リスク
- `examples/human-review/workflow.yaml` 等の `prompt_ref` が解決できるか（bundle-root の設定）— 実装時に確認
- `uv pip install --system yagra` は PyPI リリース済み版を入れる。開発中コード検証のためには `uv sync --locked --dev` の方が安全

### 見積もり
S — 1 ファイル新規 + 動作確認

### 代替案
- (却下) `ci.yml` に validate step を追加統合: ガイドが独立ファイル参照を前提としているため、別ファイルを維持
- (却下) `uv pip install --system yagra` のみ使用: PyPI 最新版と現在開発中コードに乖離があると false negative/positive の懸念、`uv sync` + `uv run yagra` で現行コード検証

---

## 合意事項

### 成功基準

| # | 基準 | 検証コマンド | 実質性チェック |
|---|------|------------|--------------|
| 1 | `.github/workflows/validate-example.yml` が実在 | `test -f .github/workflows/validate-example.yml && echo OK` | ファイル中身が空でなく、有効な GitHub Actions YAML であること |
| 2 | トリガが `pull_request` + `push (main)` を含む | `uv run python -c "import yaml; c = yaml.safe_load(open('.github/workflows/validate-example.yml')); assert 'pull_request' in c.get(True, c.get('on', {})); print('OK')"` | （`on` キーの YAML パース後の真偽値化注意） |
| 3 | ローカルで examples/ 全 workflow.yaml を検証するスクリプトが緑 | `for f in examples/*/workflow.yaml; do uv run yagra validate --workflow "$f" --bundle-root "$(dirname "$f")" --format json > /dev/null; done; echo "exit=$?"` | exit=0 で通過（warnings は許容） |
| 4 | `docs/ci-integration-guide.md` の参照先と矛盾しない | `grep -n "validate-example.yml" docs/ci-integration-guide.md` → 参照が残っており、かつ参照先のファイルが実在すること | ガイドのクイックスタート手順が現実的に辿れる |
| 5 | `uv run pre-commit run --all-files` 通過 | `uv run pre-commit run --all-files` | ruff format / ruff check / mypy すべて Passed（YAML ファイル追加のみなので影響軽微） |
| 6 | PR 作成時に CI（本ジョブ）が実ジョブとして起動する | `gh pr checks {pr_number}` で `validate-example` job が Running/Success であること | 既存 `quality` ジョブと併存、衝突しない |

**検証コマンドの要件**: 上記はいずれもシェル実行可能。手動ステップなし。

### スコープ
- **In:**
  - `.github/workflows/validate-example.yml` 新規作成
  - 必要に応じた `docs/ci-integration-guide.md` の文言微修正（実装と矛盾が残る場合のみ）
- **Out:**
  - 既存 `ci.yml` / `docs.yml` / `publish.yml` の変更
  - `scripts/pr-comment-example.sh` の変更
  - 「変更ファイルのみ検証」等の高度な設定
  - Yagra handler 実装の変更
  - examples/ 配下の YAML 変更（#2 で修復済み）

### 制約
- Python 3.12 + uv 0.x（既存 `ci.yml` と同じ toolchain）
- `actions/checkout@v6` 等、既存 `ci.yml` と同じバージョンラインを使用
- Yagra プロジェクトの CONTRIBUTING.md に従う（uv add/sync のみ、pip install 禁止）

---

## アライメントで解消した懸念

| # | 提起者 | 懸念 | 解決内容 |
|---|--------|------|---------|
| 1 | PO | PyPI 版 vs 開発中コード版どちらでバリデートするか | 開発中コード版（`uv sync --locked --dev` + `uv run yagra validate`）を採用。Yagra 自身のリポジトリで false negative を避ける |
| 2 | PO | examples/ の `prompt_ref` 解決失敗リスク | `--bundle-root "$(dirname "$f")"` を明示。ローカル検証で確認済み（#2 のコミット 91443e5 時点） |
| 3 | PO | 並列 #3 PR と #2 PR の feature branch 派生の衝突 | PR #47 マージ後に main から派生する運用で解消済み |

## エスカレーション事項

なし（PO 裁量の範囲で完了可能）。

---

## 付記：PM 実行ヒント

- Developer 数: S サイズ → 2（skill 規定。Developer 1 で実装、Developer 2 で品質補完・追加検証ケース）
- Mission Brief にはこの contract の「成功基準」と「スコープ」を転記すること
- PMO レビューは sonnet（S/M サイズルーティング）
- Feature branch 名: `feature/add-validate-example-workflow`
- PR タイトル案: `chore(ci): validate-example.yml を追加し examples/ 全体を検証 (#3)`
