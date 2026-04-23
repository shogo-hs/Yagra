# Yagra Claude Code Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Yagra を canonical 配布モデルから Claude Code ネイティブ `.claude/` 構造へ移行する。既存の運用規約は完全保全しつつ、`CONTRIBUTING.md` との重複を排除する。

**Architecture:** 3 フェーズの段階マイグレーション。Phase 1 は非破壊的に新構造を追加、Phase 2 は `docs/ai/` 下の残存ドキュメントを精査移動、Phase 3 は旧ファイルを一掃。各フェーズを独立 PR として扱う。

**Tech Stack:** Claude Code（`.claude/` SKILL.md 形式）、Markdown、Python 3.12+ / uv、git

**Reference:** `docs/superpowers/specs/2026-04-23-yagra-claude-code-setup-design.md`

---

## File Structure

### 新規作成（Phase 1）

| パス | 責務 |
|------|------|
| `.claude/settings.json` | Layer 1 permissions（allow/deny リスト、model 指定） |
| `.claude/settings.local.json.example` | 開発者ローカル設定のテンプレ |
| `.claude/rules/skill-catalog.md` | スキル表と選択指針（paths: `**`） |
| `.claude/rules/security.md` | Layer 4 運用規範（paths: `**`） |
| `.claude/rules/architecture.md` | Hexagonal 境界規律（paths: `src/yagra/**`） |
| `.claude/agents/architecture-reviewer.md` | Hex/SOLID 違反検出サブエージェント |
| `.claude/skills/task-design-gate/SKILL.md` + `references/` | 既存 playbook から移行 |
| `.claude/skills/python-uv-ci-setup/SKILL.md` + `references/` | 同上 |
| `.claude/skills/python-project-bootstrap/SKILL.md` + `references/` | 同上 |
| `.claude/skills/api-spec-sync/SKILL.md` + `references/` | 同上 |
| `.claude/skills/adr-management/SKILL.md` + `references/` | 同上 |
| `.claude/skills/git-commit/SKILL.md` | 同上（references 不要） |
| `.claude/skills/release-ops/SKILL.md` | 新規（SemVer + 3 箇所同期 + Keep a Changelog） |
| `.claude/scripts/.gitkeep` | 将来のフック配置用 |
| `CLAUDE.md` | 新規実体、~85 行（現状はシンボリックリンク） |

### 変更（Phase 1-2）

| パス | 変更内容 |
|------|----------|
| `.gitignore` | 229 行目 `.claude/` 削除、`.claude/settings.local.json` / `.claude/logs/` 除外追加 |
| `docs/ai/agent-integration-guide.md` | 精査後に `docs/agent-integration-guide.md` へ移動 or 削除 |
| `docs/ai/ci-integration-guide.md` | 同上 |

### 削除（Phase 3）

- `AGENTS.md`
- `.cursor/`（ディレクトリ全体）
- `docs/ai/canonical/`（全体）
- `docs/ai/playbooks/`（全体）
- `docs/ai/playbook-assets/`（全体）
- `docs/ai/`（空化後）
- `scripts/sync_ai_context.py`
- `scripts/bootstrap_after_canonical.py`（canonical 前提スクリプト）

### 保全（変更なし）

- `CONTRIBUTING.md`（311 行、開発規範の正本）
- `docs/rules/code_architecture/`, `docs/rules/solid/`
- `docs/adr/`, `docs/api/`, `docs/architecture/`, `docs/product/`, `docs/sphinx/`, `docs/task-designs/`
- `scripts/playbooks/`（api-spec-sync / python-project-bootstrap の補助スクリプト）
- `.mcp.json`（Yagra 自身の MCP サーバ定義）

---

## Phase 0: 準備

### Task 0: 作業ブランチ作成と仕様コミット

**Files:**
- Commit: `docs/superpowers/specs/2026-04-23-yagra-claude-code-setup-design.md`

- [ ] **Step 1: ブランチを作成**

```bash
cd /workspace/Yagra
git checkout -b feat/claude-code-setup
git branch --show-current
```

Expected: `feat/claude-code-setup`

- [ ] **Step 2: 仕様書をコミット**

```bash
cd /workspace/Yagra
git add docs/superpowers/
git commit -m "docs: Claude Code移行設計仕様を追加"
git log -1 --oneline
```

Expected: 新コミットハッシュと件名が表示される。

---

## Phase 1: 加算（非破壊）

### Task 1-pre: `.gitignore` を先に更新（Phase 1 前提）

**Files:**
- Modify: `.gitignore`（229 行目 `.claude/` を削除し、代わりに local/logs のみ除外）

**Context:** 現状 `.gitignore` 229 行目に `.claude/` が記載されており、Tasks 1〜13 が作成する `.claude/` 配下のファイルが `git add` できない。このため Task 14 を Phase 1 の最初に前倒しで実施する。元の Task 14 は完了済みとしてスキップする。

- [ ] **Step 1: 現状の該当行を確認**

```bash
cd /workspace/Yagra
grep -n "^\.claude" .gitignore
```

Expected: `229:.claude/` のような行が表示される。

- [ ] **Step 2: `.gitignore` を編集**

`.gitignore` 内の `.claude/` 行を以下 3 行に置換する：

```
.claude/settings.local.json
.claude/logs/
.claude/scripts/*.log
```

Edit:
- old_string: `.claude/`（該当行のみ、一意性のため前後文脈を含めて指定）
- new_string: `.claude/settings.local.json`<newline>`.claude/logs/`<newline>`.claude/scripts/*.log`

- [ ] **Step 3: 検証**

```bash
cd /workspace/Yagra
grep -n "\.claude" .gitignore
git check-ignore .claude/ 2>&1 || echo ".claude/ no longer ignored - OK"
```

Expected: 3 行表示、`.claude/ no longer ignored - OK`。

- [ ] **Step 4: コミット**

```bash
cd /workspace/Yagra
git add .gitignore
git commit -m "chore: .claude/ を git 追跡対象に変更（settings.local/logs のみ除外）"
```

---

### Task 1: `.claude/settings.json` と `.claude/settings.local.json.example` を作成

**Files:**
- Create: `.claude/settings.json`
- Create: `.claude/settings.local.json.example`
- Create: `.claude/scripts/.gitkeep`

- [ ] **Step 1: ディレクトリ作成**

```bash
cd /workspace/Yagra
mkdir -p .claude/skills .claude/rules .claude/agents .claude/scripts
touch .claude/scripts/.gitkeep
```

- [ ] **Step 2: `.claude/settings.json` を作成**

Write file `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "Skill",
      "Edit",
      "Write",
      "Bash(git status*)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Bash(git show*)",
      "Bash(git add*)",
      "Bash(git commit*)",
      "Bash(git branch*)",
      "Bash(git checkout*)",
      "Bash(git push)",
      "Bash(git pull)",
      "Bash(uv *)",
      "Bash(pytest*)",
      "Bash(ruff*)",
      "Bash(mypy*)",
      "Bash(pre-commit*)",
      "Bash(ls*)",
      "Bash(mkdir*)",
      "Bash(wc*)",
      "mcp__*"
    ],
    "deny": [
      "Read(.env)",
      "Read(.env.*)",
      "Read(**/.env)",
      "Read(**/.env.*)",
      "Read(.env.keys)",
      "Read(**/.env.keys)",
      "Read(**/credentials*)",
      "Read(**/*secret*)",
      "Bash(rm -rf *)",
      "Bash(git push --force*)",
      "Bash(git reset --hard*)"
    ]
  },
  "model": "claude-opus-4-7",
  "effortLevel": "high"
}
```

- [ ] **Step 3: `.claude/settings.local.json.example` を作成**

Write file `.claude/settings.local.json.example`:

```json
{
  "permissions": {
    "defaultMode": "bypassPermissions",
    "allow": []
  },
  "enabledMcpjsonServers": ["yagra"]
}
```

- [ ] **Step 4: JSON 構文の検証**

```bash
cd /workspace/Yagra
python3 -c "import json; json.load(open('.claude/settings.json')); json.load(open('.claude/settings.local.json.example')); print('OK')"
```

Expected: `OK`

- [ ] **Step 5: コミット**

```bash
cd /workspace/Yagra
git add .claude/settings.json .claude/settings.local.json.example .claude/scripts/.gitkeep
git commit -m "feat: Claude Code settings.json と Layer 1 permissions を追加"
```

---

### Task 2: `.claude/rules/skill-catalog.md` を作成

**Files:**
- Create: `.claude/rules/skill-catalog.md`

- [ ] **Step 1: ファイル作成**

Write file `.claude/rules/skill-catalog.md`:

```markdown
---
paths:
  - "**"
---

# Yagra スキルカタログ

## スキル一覧

| コマンド | 用途 |
|---------|------|
| `/task-design-gate` | タスク設計ゲート（実装前のスコープ確定・承認取得） |
| `/python-uv-ci-setup` | Python + uv + ruff/mypy/pytest + pre-commit + GitHub Actions を一括整備 |
| `/python-project-bootstrap` | 新規 Python プロジェクトを Hexagonal 前提で初期構築 |
| `/api-spec-sync` | API 実装と仕様ドキュメント（index + エンドポイント）を同期 |
| `/adr-management` | 設計判断を ADR として記録・更新 |
| `/git-commit` | 規約に沿ったコミット（日本語、50文字以内、プレフィックス） |
| `/release-ops` | SemVer リリース（CHANGELOG 3 箇所同期、タグ、GitHub Release） |

## スキルの使い分け

- 実装前にスコープ整理・承認を得たい → `/task-design-gate`
- 新規 Python プロジェクトを立ち上げたい → `/python-project-bootstrap`
- CI / 品質ゲートを整備したい → `/python-uv-ci-setup`
- API 実装を変更した、仕様ドキュメントを同期したい → `/api-spec-sync`
- 設計方針の採否を記録したい → `/adr-management`
- 変更をコミットしたい → `/git-commit`
- バージョンをリリースしたい → `/release-ops`

## スキル設計の規約

- スキルは `.claude/skills/<name>/SKILL.md` に配置（`commands/` は非推奨）
- 補助資料は `.claude/skills/<name>/references/` に配置（Progressive Disclosure）
- 補助スクリプトは `scripts/playbooks/<name>/` に配置（既存慣習を継承）
- 新規スキル追加時は本ファイルの表と「使い分け」節を必ず更新する
```

- [ ] **Step 2: コミット**

```bash
cd /workspace/Yagra
git add .claude/rules/skill-catalog.md
git commit -m "feat: スキルカタログ（skill-catalog.md）を追加"
```

---

### Task 3: `.claude/rules/security.md` を作成

**Files:**
- Create: `.claude/rules/security.md`

- [ ] **Step 1: ファイル作成**

Write file `.claude/rules/security.md`:

```markdown
---
paths:
  - "**"
---

# セキュリティ運用規範（Layer 4）

## 4 層防御の位置づけ

- Layer 1: `.claude/settings.json` の `permissions.deny`（`.env*` 読取禁止 等）
- Layer 2: PreToolUse フック（将来実装予定）
- Layer 3: MCP / サンドボックス境界
- Layer 4: 本ファイル + `CLAUDE.md` の運用規範

## 秘密情報の取扱い

- `.env`, `.env.*`, `.env.keys`, `credentials*`, `*secret*` の読取は Layer 1 で禁止済み
- 読取できても WebFetch / WebSearch / MCP / `curl` 等で外部送信しない
- 秘密情報がソースに含まれる疑いがある場合は作業を停止しユーザーに確認する
- APIキー・トークン・秘密鍵・`.env.keys` は出力・コミット・Issue/PR本文へ記載しない

## 環境変数運用

- `.env.development` / `.env.production` を利用する
- 秘密情報は dotenvx の `encrypted:` 形式で管理する
- `.env.keys` はコミット禁止

## 破壊的操作

- `rm -rf`, `git reset --hard`, `git push --force` は Layer 1 で deny 済み
- それ以外の取消困難操作（DB truncate、広範囲ファイル上書き等）は実行前にユーザー確認
- 未追跡ファイルの削除前に `git status` を確認
- 想定外の大量差分・履歴破壊操作・広範囲削除が必要な場合は作業を停止しユーザー再確認

## パッケージ管理

- Python パッケージ操作は `uv add` / `uv remove` / `uv sync` のみ
- `pip install` / `uv pip install` は禁止

## 外部通信

- WebFetch / WebSearch 利用時は、送信内容に秘密情報が含まれないことを確認
- MCP サーバ経由の外部送信も同等に扱う
```

- [ ] **Step 2: コミット**

```bash
cd /workspace/Yagra
git add .claude/rules/security.md
git commit -m "feat: セキュリティ運用規範（Layer 4）を追加"
```

---

### Task 4: `.claude/rules/architecture.md` を作成

**Files:**
- Create: `.claude/rules/architecture.md`

- [ ] **Step 1: ファイル作成**

Write file `.claude/rules/architecture.md`:

```markdown
---
paths:
  - "src/yagra/**"
  - "tests/**"
---

# Yagra Architecture Rules

## Hexagonal 境界

Yagra は Hexagonal Architecture を採用する。依存方向は外側から内側へ固定する。

- `domain/`: ドメインエンティティ・サービス。外部技術へ依存しない
- `ports/`: 境界を定義するインターフェース
- `application/`: ユースケース・サービス。`domain` と `ports` のみを参照
- `adapters/`: `ports` の具象実装（inbound: CLI/API、outbound: DB/ファイル/HTTP）

## 禁止事項（機械的チェック対象）

- `domain/` 内で `adapters` / `application` を import しない
- `domain/` 内に I/O コード（HTTP、DB、ファイル読書き）を書かない
- `application/` から adapters 実装を直接参照しない（ports 経由で）
- `ports/` に具象実装を書かない（インターフェース定義のみ）

## SOLID 原則

- Single Responsibility: 1 モジュール 1 責務
- Open/Closed: 拡張に開き、変更に閉じる
- Liskov Substitution: 派生型は基底型と置換可能
- Interface Segregation: クライアント固有のインターフェース
- Dependency Inversion: 抽象に依存（具象に依存しない）

## 変更時のチェックポイント

- import 文を確認し、逆方向依存がないことを検証
- 新規ファイルの配置先が責務に合っているか
- `docs/rules/code_architecture/` と `docs/rules/solid/` のルールに整合しているか

## 参照

- @docs/rules/code_architecture/
- @docs/rules/solid/
- @docs/architecture/
```

- [ ] **Step 2: コミット**

```bash
cd /workspace/Yagra
git add .claude/rules/architecture.md
git commit -m "feat: Hexagonal境界規律ルール（architecture.md）を追加"
```

---

### Task 5: `.claude/agents/architecture-reviewer.md` を作成

**Files:**
- Create: `.claude/agents/architecture-reviewer.md`

- [ ] **Step 1: ファイル作成**

Write file `.claude/agents/architecture-reviewer.md`:

```markdown
---
name: architecture-reviewer
description: Yagra の Hexagonal Architecture / SOLID 違反を検出する専用レビュアー。src/yagra/ 配下に変更を加えた際、import 関係・モジュール境界・副作用の局在性を機械的にチェックするときに使う。
tools: Read, Glob, Grep, Bash
---

# Architecture Reviewer

## 責務

Yagra のアーキテクチャ制約違反を検出する：

- **Hexagonal 境界違反**:
  - `domain/` → `adapters/` / `application/` への逆依存
  - `application/` → `adapters/` 直接参照（ports 経由であるべき）
  - `ports/` 内の具象実装（インターフェース定義のみであるべき）
  - `domain/` 内の I/O 混入（HTTP / DB / ファイル / 環境変数）
- **SOLID 違反**:
  - Single Responsibility: 1 ファイル / 1 クラスが複数責務を持つ
  - Dependency Inversion: 具象クラスへの直接依存
  - Interface Segregation: 過度に大きいインターフェース
- **既存ルール違反**: `docs/rules/code_architecture/` と `docs/rules/solid/` に記載の規約

## 使用方法

`src/yagra/` 配下に変更を加えた後にこのサブエージェントを呼び出す：

> Use the architecture-reviewer agent to check my changes in `src/yagra/adapters/`

## レビュー手順

1. 変更ファイルの特定: `git diff --name-only main...HEAD -- src/yagra/ tests/`
2. import 文の抽出: `grep -rn "^import \|^from " <changed-files>`
3. Hexagonal 境界チェック: 層ごとの import 制約に違反がないか検証
4. SOLID 観点の目視レビュー
5. `docs/rules/` のルールとの整合確認
6. 違反があれば根拠（ルールの該当箇所）と共に指摘

## 参照

- @docs/rules/code_architecture/
- @docs/rules/solid/
- @docs/architecture/
- @.claude/rules/architecture.md
```

- [ ] **Step 2: コミット**

```bash
cd /workspace/Yagra
git add .claude/agents/architecture-reviewer.md
git commit -m "feat: architecture-reviewer サブエージェントを追加"
```

---

### Task 6: `task-design-gate` スキルを移行

**Files:**
- Create: `.claude/skills/task-design-gate/SKILL.md`
- Create: `.claude/skills/task-design-gate/references/_task-design-template.md`
- Create: `.claude/skills/task-design-gate/references/agents-md-snippet.md`

**Source:** `docs/ai/playbooks/task-design-gate.md` + `docs/ai/playbook-assets/task-design-gate/references/`

- [ ] **Step 1: ディレクトリ作成**

```bash
cd /workspace/Yagra
mkdir -p .claude/skills/task-design-gate/references
```

- [ ] **Step 2: 参照ファイルをコピー**

```bash
cd /workspace/Yagra
cp docs/ai/playbook-assets/task-design-gate/references/_task-design-template.md .claude/skills/task-design-gate/references/
cp docs/ai/playbook-assets/task-design-gate/references/agents-md-snippet.md .claude/skills/task-design-gate/references/
ls .claude/skills/task-design-gate/references/
```

Expected: `_task-design-template.md` と `agents-md-snippet.md` が表示される。

- [ ] **Step 3: `SKILL.md` を新規作成**

Write file `.claude/skills/task-design-gate/SKILL.md`:

```markdown
---
name: task-design-gate
description: 実装前にタスク設計書を作成し、スコープ・前提・リスクをそろえたうえでユーザー承認を取得するためのスキル。実装・リファクタ・移行・デバッグなど、ファイル変更を伴う依頼で事前計画が必要なときに使う。
---

# タスク設計ゲート

実装ファイルを編集する前に、必ず次の手順を実行する。

1. 依頼内容を 1 文で言い換える。
2. 関連コードと制約を調査する。
3. `.claude/skills/task-design-gate/references/_task-design-template.md` を読み、テンプレートを埋める。
4. 設計書を提示し、ユーザーに明示的な承認を求める。
5. 承認が出るまで、実装ファイルの編集を開始しない。
6. 承認 NG または修正依頼があれば、設計書を更新して再確認する。

## ゲートルール

- 承認前に実装ファイルを編集しない。
- 承認前に許可されるのは、読み取り中心の調査コマンドのみとする。
- 永続化する計画メモの作成・更新は、ユーザーが明示的に求めた場合のみ許可する。
- `10. オープン事項 / 要確認` に未解消項目がある場合、ステータスを `保留(blocked)` にし、実装を開始しない。
- 承認後は合意済みスコープ内でのみ実装し、スコープ逸脱が発生したら即時に再合意を取る。

## 出力ルール

- `.claude/skills/task-design-gate/references/_task-design-template.md` の見出し順を厳守して Markdown で出力する。
- **タスク設計書のメタデータには、`関連ゴールID` と `関連マイルストーンID` を必ず記載する**。
- 各セクションはリポジトリ固有の具体内容で記載し、一般論を避ける。
- ファイルは必ず明示的なパスで列挙する。
- 少なくとも 1 つ以上のリスクと検証手順を含める。
- 保存先はリポジトリ配下の `docs/task-designs/` に固定する。
- `docs/task-designs/` が存在しない場合は作成してから保存する。
- 新規設計書のファイル名は `YYYYMMDDHHMMSS_{task-name}.md` とし、`YYYYMMDDHHMMSS` は初版作成日時（JST）を使う。
- `task-name` は英小文字の kebab-case を使う。
- 更新時はファイル名を変更せず、本文の `最終更新` のみ更新する。
- 作成時刻が不明な既存ドキュメントは `YYYYMMDD000000_{task-name}.md` を使う。
- `README.md` と `_task-design-template.md` は命名プレフィックス規則の例外とする。

## ハイブリッド運用（任意）

この運用をプロジェクト全体に常時適用したい依頼があれば、`.claude/skills/task-design-gate/references/agents-md-snippet.md` を参照し、`CLAUDE.md` への追記を提案する。
```

- [ ] **Step 4: 参照ファイル内のパスを更新**

参照ファイル内部の旧パス `docs/ai/playbook-assets/task-design-gate/` を新パス `.claude/skills/task-design-gate/` に置換する。

```bash
cd /workspace/Yagra
# 内部のパス参照を確認
grep -l "docs/ai/playbook-assets/task-design-gate" .claude/skills/task-design-gate/references/ 2>/dev/null || echo "No references to update"
```

もし置換対象がある場合:

```bash
cd /workspace/Yagra
for f in .claude/skills/task-design-gate/references/*.md; do
  sed -i 's|docs/ai/playbook-assets/task-design-gate|.claude/skills/task-design-gate|g' "$f"
done
grep -rn "docs/ai/playbook-assets" .claude/skills/task-design-gate/ || echo "All paths updated"
```

Expected: `All paths updated`

- [ ] **Step 5: コミット**

```bash
cd /workspace/Yagra
git add .claude/skills/task-design-gate/
git commit -m "feat: task-design-gate スキルを .claude/skills/ へ移行"
```

---

### Task 7: `git-commit` スキルを移行

**Files:**
- Create: `.claude/skills/git-commit/SKILL.md`

**Source:** `docs/ai/playbooks/git-commit.md`（references 不要）

- [ ] **Step 1: ディレクトリ作成**

```bash
cd /workspace/Yagra
mkdir -p .claude/skills/git-commit
```

- [ ] **Step 2: `SKILL.md` を作成**

Write file `.claude/skills/git-commit/SKILL.md`:

```markdown
---
name: git-commit
description: Git の変更を安全にコミットするためのスキル。`git status` と `git diff` で差分を確認し、変更内容に合うプレフィックスを選んで日本語コミットメッセージ規約を満たしたうえで `git commit` を実行する必要があるときに使う。コミット実行依頼、コミットメッセージ作成依頼、コミット直前の最終確認で適用する。
---

# Git コミット実行

重要: すべてのコミットメッセージは日本語で記述する。

## 実行手順

1. ワークツリーと差分を確認する。
   - `git status --short`
   - `git diff --`
   - `git diff --staged --`

2. 変更意図ごとにコミット単位を整理する。
   - 無関係な変更が混在する場合はコミットを分割する。
   - コミット対象が空なら停止して理由を報告する。

3. 必要なファイルのみをステージする。
   - 個別指定を優先する: `git add <path>`
   - 追加後に再確認する: `git status --short`

4. プレフィックスを選択する。
   - `feat`: 新機能の追加
   - `fix`: バグ修正
   - `docs`: ドキュメントのみの変更
   - `style`: 動作に影響しない変更（フォーマットなど）
   - `refactor`: 機能追加やバグ修正を伴わない構造変更
   - `perf`: パフォーマンス改善
   - `test`: テストの追加または修正
   - `chore`: ビルド、補助ツール、依存関係などの変更

5. コミットメッセージを作成し、規約チェックを通す。
   - 形式: `prefix: メッセージ`
   - 全体文字数: 50 文字以内（prefix を含む）
   - 文体: 現在形（辞書形）または体言止め
   - 末尾: 句点（。）を付けない
   - 言語: プレフィックス後の本文は日本語のみ

6. 文字数を機械的に確認する。
   - `msg='feat: ユーザー認証機能を追加'`
   - `printf %s "$msg" | wc -m`
   - 50 を超える場合は短く書き直して再計測する。

7. コミットを実行する。
   - `git commit -m "$msg"`
   - 実行後に `git show --stat --oneline -1` で内容を確認する。

8. 結果を報告する。
   - コミットハッシュ、件名、変更ファイルを簡潔に共有する。
   - 未ステージ変更が残る場合は明示する。

## メッセージ例

- 良い例: `feat: ユーザー認証機能を追加`
- 悪い例: `feat: Add user authentication`
```

- [ ] **Step 3: コミット**

```bash
cd /workspace/Yagra
git add .claude/skills/git-commit/
git commit -m "feat: git-commit スキルを .claude/skills/ へ移行"
```

---

### Task 8: `adr-management` スキルを移行

**Files:**
- Create: `.claude/skills/adr-management/SKILL.md`
- Create: `.claude/skills/adr-management/references/_adr-template.md`

**Source:** `docs/ai/playbooks/adr-management.md` + `docs/ai/playbook-assets/adr-management/references/_adr-template.md`

- [ ] **Step 1: ディレクトリ作成と参照ファイルコピー**

```bash
cd /workspace/Yagra
mkdir -p .claude/skills/adr-management/references
cp docs/ai/playbook-assets/adr-management/references/_adr-template.md .claude/skills/adr-management/references/
ls .claude/skills/adr-management/references/
```

Expected: `_adr-template.md` が表示される。

- [ ] **Step 2: `SKILL.md` を作成**

Write file `.claude/skills/adr-management/SKILL.md`:

```markdown
---
name: adr-management
description: 設計判断（アーキテクチャ、運用ルール、依存方針など）の採否を ADR として記録・更新し、変更理由を追跡可能にするためのスキル。方針の新規決定、方針変更、既存判断の置換が発生したときに使う。
---

# ADR 管理

設計判断を文章化し、後から採否理由を追跡できる状態を維持する。

## 実行手順

1. 判断対象を明確化する。
   - 対象となる方針（例: アーキテクチャ、ツール選定、運用ルール）を 1 つに絞る。
   - 影響範囲（コード、CI、運用、ドキュメント）を整理する。

2. 既存 ADR を確認する。
   - `docs/adr/README.md` の一覧を確認し、重複や置換関係がないかを調べる。
   - 既存判断を置換する場合は、旧 ADR のステータスを `置換済み(superseded)` に更新する。

3. ADR を作成または更新する。
   - 新規作成時は `.claude/skills/adr-management/references/_adr-template.md` を使用する。
   - 保存先は `docs/adr/`、ファイル名は `NNNN-short-title.md`（4 桁連番 + kebab-case）を使う。
   - 本文には「文脈」「決定」「代替案」「影響」「フォローアップ」を必ず記載する。

4. 関連ドキュメントを同期する。
   - 方針変更が `CLAUDE.md` / スキル / README / CI 設定へ影響する場合は同一タスクで更新する。
   - 変更理由が追跡できるように、関連ファイルから ADR への参照を追加する。

5. レビュー観点を明示する。
   - トレードオフが比較可能か。
   - 非採用案の却下理由が具体的か。
   - 追加コスト（移行、教育、運用）を説明しているか。

6. 結果を報告する。
   - 追加 / 更新した ADR ファイル。
   - 置換した ADR（ある場合）。
   - 同時に更新した実装・ドキュメントファイル。

## 運用ルール

- 重要な設計判断は、口頭・チャットだけで完結させず ADR に残す。
- 1 ADR に複数の無関係な判断を混在させない。
- ステータスは `提案(proposed)` / `承認済み(accepted)` / `却下(rejected)` / `置換済み(superseded)` を使用する。
- 置換関係がある場合は、新旧 ADR の双方に相互リンクを張る。

## 参照ファイル

- ADR テンプレート: `.claude/skills/adr-management/references/_adr-template.md`
- ADR 一覧: `docs/adr/README.md`
```

- [ ] **Step 3: コミット**

```bash
cd /workspace/Yagra
git add .claude/skills/adr-management/
git commit -m "feat: adr-management スキルを .claude/skills/ へ移行"
```

---

### Task 9: `api-spec-sync` スキルを移行

**Files:**
- Create: `.claude/skills/api-spec-sync/SKILL.md`
- Create: `.claude/skills/api-spec-sync/references/_endpoint_template.md`
- Create: `.claude/skills/api-spec-sync/references/_index_template.md`
- Create: `.claude/skills/api-spec-sync/references/sync-checklist.md`

**Source:** `docs/ai/playbooks/api-spec-sync.md` + `docs/ai/playbook-assets/api-spec-sync/references/*`

- [ ] **Step 1: ディレクトリ作成と参照ファイルコピー**

```bash
cd /workspace/Yagra
mkdir -p .claude/skills/api-spec-sync/references
cp docs/ai/playbook-assets/api-spec-sync/references/_endpoint_template.md .claude/skills/api-spec-sync/references/
cp docs/ai/playbook-assets/api-spec-sync/references/_index_template.md .claude/skills/api-spec-sync/references/
cp docs/ai/playbook-assets/api-spec-sync/references/sync-checklist.md .claude/skills/api-spec-sync/references/
ls .claude/skills/api-spec-sync/references/
```

Expected: 3 ファイル表示。

- [ ] **Step 2: `SKILL.md` を作成**

Write file `.claude/skills/api-spec-sync/SKILL.md`:

```markdown
---
name: api-spec-sync
description: REST/HTTP API の定義書（index + 1 エンドポイント 1 ファイル）を新規作成・更新し、実装差分と常時同期させるためのスキル。API 実装の追加・変更・削除、認証仕様変更、エラー形式変更、入出力スキーマ変更が発生したときに使う。
---

# API 定義書同期

API 実装の変更と API ドキュメント更新を同一タスクで完結させる。

## 実行手順

1. 実装差分から影響エンドポイントを特定する。
   - ルーター・ハンドラー・コントローラー・DTO/Schema・OpenAPI 定義の差分を確認する。
   - 追加 / 変更 / 削除をエンドポイント単位に整理する。

2. 一覧ドキュメントを更新する。
   - `.claude/skills/api-spec-sync/references/_index_template.md` を読み、`index.md` の共通仕様とエンドポイント一覧を更新する。
   - 新規エンドポイント追加時は、必ず一覧リンクを追加する。
   - 廃止エンドポイントは一覧から削除し、必要に応じて「非推奨 / 廃止」に移す。

3. エンドポイント詳細ドキュメントを更新する。
   - `.claude/skills/api-spec-sync/references/_endpoint_template.md` を読み、対象エンドポイントの詳細ファイルを作成 / 更新する。
   - 命名は `<resource>-<method>.md` を基本とし、必要ならプロジェクト規約に合わせる。
   - 1 エンドポイント 1 ファイルを厳守する。

4. 実装と仕様を突合する。
   - HTTP メソッド、パス、認証、パラメータ、リクエスト / レスポンススキーマ、ステータスコード、エラーを確認する。
   - 実装で確認できない項目は推測しない。`TODO(要実装確認)` として明示する。

5. 同期ゲートを通す。
   - `.claude/skills/api-spec-sync/references/sync-checklist.md` のチェックを上から順に実施する。
   - 必要なら `python3 scripts/playbooks/api-spec-sync/check_api_docs_sync.py --docs-root <API ドキュメントルート>` を実行する。
   - API 実装が変わっているのにドキュメント差分がない場合、タスク完了にしない。

6. 変更結果を報告する。
   - 更新した一覧ファイルと詳細ファイルを明示する。
   - 実装側の関連ファイルと未解決 TODO を明示する。

## 厳守ルール

- API 実装変更と API ドキュメント更新を分離しない。
- 共通仕様（認証、エラーフォーマット、ベース URL）変更時は `index.md` を必ず更新する。
- エンドポイント仕様変更時は該当詳細ファイルを必ず更新する。
- 差分が大きい場合でも、最小限の追記で済ませず仕様全体の整合を優先する。

## 参照ファイル

- 一覧テンプレート: `.claude/skills/api-spec-sync/references/_index_template.md`
- 詳細テンプレート: `.claude/skills/api-spec-sync/references/_endpoint_template.md`
- 同期チェック: `.claude/skills/api-spec-sync/references/sync-checklist.md`
- 同期漏れ簡易検知スクリプト: `scripts/playbooks/api-spec-sync/check_api_docs_sync.py`
```

- [ ] **Step 3: 参照ファイル内のパス更新**

```bash
cd /workspace/Yagra
for f in .claude/skills/api-spec-sync/references/*.md; do
  sed -i 's|docs/ai/playbook-assets/api-spec-sync|.claude/skills/api-spec-sync|g' "$f"
done
grep -rn "docs/ai/playbook-assets" .claude/skills/api-spec-sync/ || echo "All paths updated"
```

Expected: `All paths updated`

- [ ] **Step 4: コミット**

```bash
cd /workspace/Yagra
git add .claude/skills/api-spec-sync/
git commit -m "feat: api-spec-sync スキルを .claude/skills/ へ移行"
```

---

### Task 10: `python-uv-ci-setup` スキルを移行

**Files:**
- Create: `.claude/skills/python-uv-ci-setup/SKILL.md`
- Create: `.claude/skills/python-uv-ci-setup/references/templates.md`
- Create: `.claude/skills/python-uv-ci-setup/references/tooling-best-practices.md`

**Source:** `docs/ai/playbooks/python-uv-ci-setup.md` + `docs/ai/playbook-assets/python-uv-ci-setup/references/*`

- [ ] **Step 1: ディレクトリ作成と参照ファイルコピー**

```bash
cd /workspace/Yagra
mkdir -p .claude/skills/python-uv-ci-setup/references
cp docs/ai/playbook-assets/python-uv-ci-setup/references/templates.md .claude/skills/python-uv-ci-setup/references/
cp docs/ai/playbook-assets/python-uv-ci-setup/references/tooling-best-practices.md .claude/skills/python-uv-ci-setup/references/
ls .claude/skills/python-uv-ci-setup/references/
```

Expected: 2 ファイル表示。

- [ ] **Step 2: `SKILL.md` を作成**

Write file `.claude/skills/python-uv-ci-setup/SKILL.md`:

```markdown
---
name: python-uv-ci-setup
description: uv を使う Python プロジェクトで、format/lint/静的型チェック/テスト/docstring ルールをローカルと GitHub Actions で一貫運用するためのセットアップスキル。`pyproject.toml` の `[dependency-groups]`、`.pre-commit-config.yaml`、`.github/workflows/ci.yml` を新規作成または更新し、`uv run pre-commit install` まで完了させる依頼で使う。
---

# Python uv CI セットアップ

このスキルでは、`uv + ruff + mypy + pytest + pre-commit + GitHub Actions` を最小差分で導入し、ローカルと CI の品質ゲートをそろえる。

## 実行フロー

1. 前提を確認する。
   - ルートに `pyproject.toml` があるか確認する。なければ `uv init` を提案する。
   - `uv --version` と `python --version` を確認する。
   - Git 管理下か確認する。未初期化なら `git init` を実行してから進む。

2. 既存設定を監査する。
   - `pyproject.toml` の `[dependency-groups]`、`[tool.ruff]`、`[tool.mypy]`、`[tool.pytest.*]` を確認する。
   - `.pre-commit-config.yaml` と `.github/workflows/*.yml` を確認する。
   - 既存設定がある場合は上書きせず、重複を避けて統合する。

3. `pyproject.toml` を `uv` 前提で整備する。
   - 開発依存を `dependency-groups.dev` に集約する。
   - 最低限の開発依存をそろえる: `ruff`, `mypy`, `pytest`, `pre-commit`。
   - ルールは `.claude/skills/python-uv-ci-setup/references/templates.md` の `pyproject.toml` テンプレートを基準にし、既存プロジェクトに合わせて微調整する。

4. pre-commit を設定する。
   - `.pre-commit-config.yaml` を作成または更新する。
   - `uv-pre-commit` の `uv-lock` を入れてロックファイル整合を強制する。
   - `uv run` 経由で `ruff format --check`、`ruff check`、`mypy` を実行する。
   - `pytest` は既定で `pre-push` に配置して開発体験を維持する。全コミットで必須にしたい場合は `stages` を `pre-commit` に変更する。

5. GitHub Actions を設定する。
   - `.github/workflows/ci.yml` を作成または更新する。
   - `actions/setup-python` と `astral-sh/setup-uv` を使い、`uv sync --locked --dev` の後に同等チェックを実行する。
   - キャッシュは `setup-uv` の `enable-cache: true` を基本にする。

6. ローカルセットアップを完了する。
   - `uv lock`
   - `uv sync --locked --dev`
   - `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`
   - `uv run pre-commit run --all-files`

7. 最終検証を実行する。
   - `uv run ruff format --check .`
   - `uv run ruff check .`
   - `uv run mypy .`
   - `uv run pytest -q`

8. 結果を報告する。
   - 追加・更新したファイル
   - 実行コマンドと結果
   - 残課題（既存コード由来の lint/type/test 失敗など）

## 運用ルール

- 型チェックは `mypy` に固定し、`ty` は使わない。
- docstring は Google style を採用し、短文 1 行のみの記述を避ける。
- docstring の先頭では「何をする処理か」「どの条件で使うか」を日本語で具体的に説明する。
- 引数がある処理は `Args`、戻り値がある処理は `Returns`、例外を送出しうる処理は `Raises` を記載する。
- `pydocstyle` の `convention = "google"` を有効化し、必要に応じて日本語運用に不要なルールのみ最小限で除外する。
- `project.requires-python` を定義し、Ruff のバージョン推論と整合させる。
- CI とローカルで実行コマンドを一致させる。

## 参照ファイル

- 設定方針と採用理由: `.claude/skills/python-uv-ci-setup/references/tooling-best-practices.md`
- そのまま適用できる雛形: `.claude/skills/python-uv-ci-setup/references/templates.md`
```

- [ ] **Step 3: 参照ファイル内のパス更新**

```bash
cd /workspace/Yagra
for f in .claude/skills/python-uv-ci-setup/references/*.md; do
  sed -i 's|docs/ai/playbook-assets/python-uv-ci-setup|.claude/skills/python-uv-ci-setup|g' "$f"
done
grep -rn "docs/ai/playbook-assets" .claude/skills/python-uv-ci-setup/ || echo "All paths updated"
```

Expected: `All paths updated`

- [ ] **Step 4: コミット**

```bash
cd /workspace/Yagra
git add .claude/skills/python-uv-ci-setup/
git commit -m "feat: python-uv-ci-setup スキルを .claude/skills/ へ移行"
```

---

### Task 11: `python-project-bootstrap` スキルを移行

**Files:**
- Create: `.claude/skills/python-project-bootstrap/SKILL.md`
- Create: `.claude/skills/python-project-bootstrap/references/agents-md-checklist.md`
- Create: `.claude/skills/python-project-bootstrap/references/agents-playbooks-boundary.md`
- Create: `.claude/skills/python-project-bootstrap/references/env-and-dotenvx.md`
- Create: `.claude/skills/python-project-bootstrap/references/product-docs-alignment.md`
- Create: `.claude/skills/python-project-bootstrap/references/project-structure.md`

**Source:** `docs/ai/playbooks/python-project-bootstrap.md` + `docs/ai/playbook-assets/python-project-bootstrap/references/*`

- [ ] **Step 1: ディレクトリ作成と参照ファイルコピー**

```bash
cd /workspace/Yagra
mkdir -p .claude/skills/python-project-bootstrap/references
cp docs/ai/playbook-assets/python-project-bootstrap/references/*.md .claude/skills/python-project-bootstrap/references/
ls .claude/skills/python-project-bootstrap/references/
```

Expected: 5 ファイル表示（agents-md-checklist, agents-playbooks-boundary, env-and-dotenvx, product-docs-alignment, project-structure）

- [ ] **Step 2: `SKILL.md` を作成**

Write file `.claude/skills/python-project-bootstrap/SKILL.md`:

```markdown
---
name: python-project-bootstrap
description: 新しい Python プロジェクトの初期セットアップを標準化するスキル。CLAUDE.md と docs/product を対話で確定し、Hexagonal Architecture 前提のディレクトリ、SOLID/DRY ガイド、API/タスク設計ドキュメント、`.env.development`/`.env.production` と dotenvx 暗号化運用を整備するときに使う。CI は必須工程とし、品質ゲート設定は必ず `python-uv-ci-setup` を呼び出して完了させる依頼で適用する。
---

# Python プロジェクト初期構築

このスキルは、Python 新規プロジェクトの「最初に揃えるべき構造と運用ドキュメント」を再利用可能な手順で作る。

## 実行ルール

- CLAUDE.md の不明点がある状態で雛形を確定しない。必ず対話で埋める。
- `docs/product/vision.md` / `docs/product/goals.md` / `docs/product/milestones.md` / `docs/product/progress.md` を空欄のまま放置しない。初期化時に必ずユーザーと擦り合わせる。
- 質問は 1〜3 問ずつ行い、回答を反映して次の質問へ進む。
- CI 設定は必須。必ず `python-uv-ci-setup` を使って完了させる。
- 既存ファイルがある場合は破壊的上書きを避け、差分統合を優先する。
- CLAUDE.md は常時有効ルールのみを記載し、長い手順やコマンドはスキル側へ集約する。
- 原則として新規作成はスキル同梱のテンプレートから開始する。

## 実行フロー

1. 前提を確認する。
   - ルートディレクトリと Git 管理状態を確認する。
   - 既存の `CLAUDE.md` と `docs/task-designs` の有無を確認する。
   - 既存プロジェクトで `docs/tasks` を使っている場合のみ、後方互換として既存パス命名を尊重する。

2. CLAUDE.md 情報を対話で確定する。
   - `.claude/skills/python-project-bootstrap/references/agents-md-checklist.md` の必須項目から埋める。
   - `.claude/skills/python-project-bootstrap/references/agents-playbooks-boundary.md` を基準に、CLAUDE.md とスキルの責務境界を固定する。
   - 未確定項目は既定値を勝手に固定せず、ユーザー確認を優先する。
   - 既定値を使う場合は「既定値を採用した」と明示してから確定する。

3. 初期構成を生成する。
   - `scripts/playbooks/python-project-bootstrap/bootstrap_python_project.py` を実行して、ディレクトリと初期ドキュメントを生成する。
   - 例: `python3 scripts/playbooks/python-project-bootstrap/bootstrap_python_project.py --target <project-root> --project-name <name> --package-name <package_name> --description "<description>"`
   - 必要に応じて `--task-design-dir docs/task-designs`（既定）や `--force` を使う。

4. プロダクト方針（docs/product）を対話で初期確定する。
   - `.claude/skills/python-project-bootstrap/references/product-docs-alignment.md` を使い、1〜3 問ずつ擦り合わせる。
   - 最低限、次を埋める。
     - `docs/product/vision.md`: 対象ユーザー、解く課題、成功状態
     - `docs/product/goals.md`: ユーザー到達状態ゴールと到達判定
     - `docs/product/milestones.md`: 到達ステップ
     - `docs/product/progress.md`: やるべきこと一覧ベースの現在地
   - 不確定項目が残る場合は、`仮置き` と明記して次の確認タイミングを残す。

5. 生成内容をレビューする。
   - `.claude/skills/python-project-bootstrap/references/project-structure.md` を基準に、`adapters/application/domain/ports` の責務分離を確認する。
   - `docs/rules/solid/README.md` と `docs/rules/code_architecture/README.md` の導線が CLAUDE.md から参照できることを確認する。
   - `.claude/skills/python-project-bootstrap/references/env-and-dotenvx.md` を基準に `.env.*` の運用記載が整合しているか確認する。
   - `docs/product/*.md` が生成され、対話で確定した内容が反映されていることを確認する。

6. CI を必須で設定する。
   - 生成直後に必ず `python-uv-ci-setup` を呼び出して、`uv` ベースの品質ゲートと GitHub Actions を整備する。
   - 本スキル内で CI 設定を再実装しない（DRY を維持）。

7. 検証する。
   - 生成ファイル一覧を確認する。
   - `CLAUDE.md` の必須セクションが埋まっていることを確認する。
   - `docs/product/vision.md` / `docs/product/goals.md` / `docs/product/milestones.md` / `docs/product/progress.md` が初期記入されていることを確認する。
   - `.env.development` / `.env.production` の整合を確認する。
   - CI 設定完了後に `uv run pre-commit install` が実行可能な状態であることを確認する。

8. 結果を報告する。
   - 作成・更新したファイル
   - 対話で確定した項目
   - `docs/product` で合意した内容（Vision / Goal / Milestone / Progress）
   - CI 設定の実行結果
   - 残課題（手動で埋めるべき値や鍵など）

## 参照ファイル

- CLAUDE.md ヒアリング項目: `.claude/skills/python-project-bootstrap/references/agents-md-checklist.md`
- CLAUDE.md とスキルの責務境界: `.claude/skills/python-project-bootstrap/references/agents-playbooks-boundary.md`
- `docs/product` 擦り合わせ質問: `.claude/skills/python-project-bootstrap/references/product-docs-alignment.md`
- Hexagonal 構成と責務: `.claude/skills/python-project-bootstrap/references/project-structure.md`
- `.env.*` と dotenvx 暗号化運用: `.claude/skills/python-project-bootstrap/references/env-and-dotenvx.md`
```

- [ ] **Step 3: 参照ファイル内のパス更新**

```bash
cd /workspace/Yagra
for f in .claude/skills/python-project-bootstrap/references/*.md; do
  sed -i 's|docs/ai/playbook-assets/python-project-bootstrap|.claude/skills/python-project-bootstrap|g' "$f"
done
grep -rn "docs/ai/playbook-assets" .claude/skills/python-project-bootstrap/ || echo "All paths updated"
```

Expected: `All paths updated`

- [ ] **Step 4: `scripts/playbooks/python-project-bootstrap/bootstrap_python_project.py` 内の旧パス参照を更新**

```bash
cd /workspace/Yagra
grep -n "docs/ai/canonical\|docs/ai/playbooks" scripts/playbooks/python-project-bootstrap/bootstrap_python_project.py
```

該当箇所（line 177 付近と line 206 付近）を特定し、言及内容を新パス（`.claude/skills/python-project-bootstrap/` や `.claude/skills/python-uv-ci-setup/SKILL.md`）に更新する。

具体的な置換:
- `docs/ai/canonical/playbooks/` → `.claude/skills/<name>/SKILL.md`（具体文脈で置換）
- `docs/ai/playbooks/python-uv-ci-setup.md` → `.claude/skills/python-uv-ci-setup/SKILL.md`

```bash
cd /workspace/Yagra
sed -i 's|docs/ai/playbooks/python-uv-ci-setup.md|.claude/skills/python-uv-ci-setup/SKILL.md|g' scripts/playbooks/python-project-bootstrap/bootstrap_python_project.py
# canonical/playbooks への言及はコメント文の修正になる可能性が高い。手動確認:
grep -n "docs/ai" scripts/playbooks/python-project-bootstrap/bootstrap_python_project.py
```

残った canonical 参照は、「初回生成直後に手順正本を...へ配置」の文脈なので、その記述を「生成直後にスキル本体を `.claude/skills/<name>/SKILL.md` に配置してコミットする」に手動で書き換える。

- [ ] **Step 5: コミット**

```bash
cd /workspace/Yagra
git add .claude/skills/python-project-bootstrap/ scripts/playbooks/python-project-bootstrap/
git commit -m "feat: python-project-bootstrap スキルを .claude/skills/ へ移行"
```

---

### Task 12: `release-ops` スキルを新規作成

**Files:**
- Create: `.claude/skills/release-ops/SKILL.md`

**Context:** 新規スキル。既存 AGENTS.md の「3 箇所同期」「Keep a Changelog」「SemVer + pyproject.toml バージョン一致」規約を収容。

- [ ] **Step 1: ディレクトリ作成**

```bash
cd /workspace/Yagra
mkdir -p .claude/skills/release-ops
```

- [ ] **Step 2: `SKILL.md` を作成**

Write file `.claude/skills/release-ops/SKILL.md`:

```markdown
---
name: release-ops
description: Yagra のバージョンリリース実行スキル。Semantic Versioning に従い、CHANGELOG.md（日本語正本）/ docs/sphinx/source/changelog.md（英語）/ GitHub Release（英語）を同期し、pyproject.toml の version と一致させる。Keep a Changelog 形式を遵守する。リリース実行・バージョンバンプ依頼で使う。
---

# リリース運用

Yagra のリリースは 3 箇所の変更履歴を同期する必要がある。本スキルはその手順を規定する。

## 実行フロー

1. リリース範囲を確認する。
   - 前回リリースタグからの `git log --oneline <last-tag>..HEAD` を確認する。
   - 変更を `Added / Changed / Deprecated / Removed / Fixed / Security` に分類する。
   - 破壊的変更の有無を明示する。

2. バージョン番号を決定する（Semantic Versioning）。
   - MAJOR: 破壊的変更
   - MINOR: 後方互換な機能追加
   - PATCH: 後方互換なバグ修正
   - 確定したバージョンを `NEW_VERSION` として以後の手順で使う。

3. `pyproject.toml` の `version` を更新する。
   - `[project]` セクションの `version = "X.Y.Z"` を `NEW_VERSION` に変更する。
   - `uv lock` を実行してロックファイルを更新する。

4. `CHANGELOG.md`（ルート、日本語、正本）を更新する。
   - Keep a Changelog 形式（https://keepachangelog.com/ja/）を厳守する。
   - `[Unreleased]` セクションの項目を `[NEW_VERSION] - YYYY-MM-DD` へ移す。
   - セクション見出しは `Added / Changed / Deprecated / Removed / Fixed / Security` のみを使用する。
   - 末尾のリンク参照（`[NEW_VERSION]: https://.../compare/...`）も更新する。

5. `docs/sphinx/source/changelog.md`（英語、ユーザー向け）を同期する。
   - ルート `CHANGELOG.md` の NEW_VERSION 分を英訳して追加する。
   - ユーザー視点で重要な変更のみを要約する（内部リファクタは含めない）。
   - Sphinx ビルド対応の Markdown 構文を使う。

6. コミットとタグを作成する。
   - `git add pyproject.toml uv.lock CHANGELOG.md docs/sphinx/source/changelog.md`
   - `git commit -m "chore: vNEW_VERSION リリース"`（50 文字以内）
   - `git tag -a vNEW_VERSION -m "Release vNEW_VERSION"`

7. プッシュする。
   - `git push origin <branch>`
   - `git push origin vNEW_VERSION`

8. GitHub Release を作成する（英語、詳細説明付き）。
   - `gh release create vNEW_VERSION --title "vNEW_VERSION" --notes-file <tempfile>`
   - 内容は `docs/sphinx/source/changelog.md` の該当セクションをベースに、より詳細な説明を追加する。
   - 破壊的変更がある場合は "⚠️ Breaking Changes" セクションを冒頭に置く。

9. 結果を報告する。
   - リリースされたバージョン
   - 同期した 3 箇所のリンク（CHANGELOG 該当アンカー、Sphinx 該当アンカー、GitHub Release URL）
   - 付与したタグ

## 厳守ルール

- **3 箇所の変更履歴同期は必須**（CHANGELOG.md / Sphinx / GitHub Release）。どれか一つでも欠けたらリリース未完了とする。
- `CHANGELOG.md` が正本で日本語、Sphinx と GitHub Release は英語。
- `pyproject.toml` の `version` は `NEW_VERSION` と完全一致させる。
- Keep a Changelog のセクション見出し以外は使わない（カスタム見出し禁止）。
- リリース前に `uv run pre-commit run --all-files` と `uv run pytest` が全てパスすることを確認する。
- 破壊的変更がある場合は MAJOR バンプを強制する。

## 参照

- Keep a Changelog: https://keepachangelog.com/ja/1.1.0/
- Semantic Versioning: https://semver.org/lang/ja/
```

- [ ] **Step 3: コミット**

```bash
cd /workspace/Yagra
git add .claude/skills/release-ops/
git commit -m "feat: release-ops スキルを新規追加（3箇所同期・SemVer・Keep a Changelog）"
```

---

### Task 13: `CLAUDE.md` を実体ファイル化

**Files:**
- Delete: `CLAUDE.md`（シンボリックリンク）
- Create: `CLAUDE.md`（実体ファイル）

**Context:** 現状 `CLAUDE.md -> AGENTS.md` のシンボリックリンク。これを解除し、Claude Code 専用の実体に置き換える。

- [ ] **Step 1: シンボリックリンクを削除**

```bash
cd /workspace/Yagra
ls -la CLAUDE.md
```

Expected: `CLAUDE.md -> AGENTS.md` の表示。

```bash
cd /workspace/Yagra
rm CLAUDE.md
ls -la CLAUDE.md 2>&1 || echo "removed"
```

Expected: `removed`

- [ ] **Step 2: 新しい `CLAUDE.md` を作成**

Write file `CLAUDE.md`:

```markdown
# CLAUDE.md — Yagra

Yagra は LangGraph ベースの AI エージェントワークフローランタイム。
本ファイルは Claude Code 向けの運用規約。人間向けの入口は @README.md。

## プロジェクト要点
- Hexagonal Architecture（adapters / application / domain / ports）
- Python 3.12+ / uv / LangGraph / MCP Server
- 詳細: @README.md / @CONTRIBUTING.md / @docs/architecture/

## 役割分離
- `README.md`: 人間が最初に理解するための入口（目的・全体像・セットアップ）
- `CLAUDE.md`（本ファイル）: エージェントが実行時に守る規約
- 同じ内容を両方に重複記載しない

## 作業モード（運用規範）
1. 計画優先: 3 ステップ以上 or 設計判断を伴うタスクは必ず計画を提示し承認を得る
2. サブエージェント優先: 調査・探索・並列分析はサブエージェント化
3. 完了前検証: テスト実行・ログ確認を行い「スタッフエンジニアが承認するか」を自問
4. 根本原因優先: 場当たり修正禁止
5. 最小変更: 必要箇所のみ変更
6. 想定外の大量差分・履歴破壊操作・広範囲削除が必要な場合は作業を停止しユーザー再確認

## タスクルーティング
- スキル一覧と選択指針: @.claude/rules/skill-catalog.md
- タスク設計書には `関連ゴールID` / `関連マイルストーンID` を必ず記載（@.claude/skills/task-design-gate/SKILL.md）

## 開発コマンド・コーディング標準
- セットアップ、テスト、lint、pre-commit、パッケージ管理: @CONTRIBUTING.md
- Python パッケージ操作は `uv add / uv remove / uv sync` のみ。`pip install` / `uv pip install` 禁止
- アーキテクチャ・SOLID 規約: @docs/rules/code_architecture/ / @docs/rules/solid/
- ADR: @docs/adr/（`/adr-management` で作成）

## プロダクト文脈
- ビジョン・ゴール・マイルストーン: @docs/product/（正本）
- API 仕様: @docs/api/

## リリース規範
- Semantic Versioning、`pyproject.toml` の `version` と一致
- 3 箇所同期: CHANGELOG.md（日本語正本）/ docs/sphinx/source/changelog.md（英語）/ GitHub Release（英語）
- Keep a Changelog 形式（Added / Changed / Deprecated / Removed / Fixed / Security）
- 具体手順: @.claude/skills/release-ops/SKILL.md

## セキュリティ（4 層防御）
- Layer 1: `.claude/settings.json` の permissions.deny（.env*, credentials, secret 読取禁止）
- Layer 2: PreToolUse フック（将来実装予定）
- Layer 3: MCP / サンドボックス境界
- Layer 4: 本 CLAUDE.md + @.claude/rules/security.md の運用規範
- 環境変数: `.env.development` / `.env.production` + dotenvx `encrypted:` 形式。`.env.keys` コミット禁止

## Claude Code 運用ノート
- コミュニケーション言語: 日本語
- 計画・タスクは tasks/todo.md、教訓は tasks/lessons.md
- Skills は `.claude/skills/<name>/SKILL.md`（`commands/` は非推奨）

## 参照
- 詳細ガイド: @CONTRIBUTING.md
```

- [ ] **Step 3: シンボリックリンクでないことを検証**

```bash
cd /workspace/Yagra
ls -la CLAUDE.md
```

Expected: `-rw-r--r--` から始まる通常ファイル行（`->` を含まない）。

- [ ] **Step 4: 行数を確認**

```bash
cd /workspace/Yagra
wc -l CLAUDE.md
```

Expected: 50-100 行の範囲。

- [ ] **Step 5: コミット**

```bash
cd /workspace/Yagra
git add CLAUDE.md
git commit -m "feat: CLAUDE.md を実体化（シンボリックリンク解除）"
```

---

### Task 14: `.gitignore` を更新（**Task 1-pre で完了済み**）

**Status:** Task 1-pre（Phase 1 の最初）で前倒し実施済み。本 Task はスキップ可。検証のみ実施する。

**Files:**
- Modify: `.gitignore`（line 229 の `.claude/` 削除、代わりに local/logs のみ除外）

- [ ] **Step 1: 現状の該当行を確認**

```bash
cd /workspace/Yagra
grep -n "^\.claude" .gitignore
```

Expected: `229:.claude/` のような行が表示される。

- [ ] **Step 2: `.gitignore` を編集**

`.gitignore` 内の `.claude/` 行を以下 3 行に置換する：

```
.claude/settings.local.json
.claude/logs/
.claude/scripts/*.log
```

Edit コマンド:
- old_string: `.claude/`（該当行のみ。一意性のため前後の文脈を含めて指定する必要がある場合あり）
- new_string: `.claude/settings.local.json\n.claude/logs/\n.claude/scripts/*.log`

- [ ] **Step 3: 検証**

```bash
cd /workspace/Yagra
grep -n "\.claude" .gitignore
```

Expected: 3 行表示（`.claude/settings.local.json`, `.claude/logs/`, `.claude/scripts/*.log`）。`.claude/` 単独行は存在しない。

- [ ] **Step 4: `.claude/` が git 追跡対象になっていることを確認**

```bash
cd /workspace/Yagra
git check-ignore .claude/settings.json && echo "STILL IGNORED - BAD" || echo "TRACKED - OK"
git check-ignore .claude/settings.local.json && echo "IGNORED - OK" || echo "NOT IGNORED - BAD"
```

Expected: 1 行目 `TRACKED - OK`、2 行目 `IGNORED - OK`。

- [ ] **Step 5: コミット**

```bash
cd /workspace/Yagra
git add .gitignore
git commit -m "chore: .claude/ を git 追跡対象に変更（settings.local/logs のみ除外）"
```

---

### Task 15: `CONTRIBUTING.md` の運用規約カバレッジ監査

**Files:**
- Read: `CONTRIBUTING.md`
- Potentially modify: `CONTRIBUTING.md`（欠落項目があれば別 PR で提案）

**Context:** 仕様書 1.4 の運用規約マッピングで `CONTRIBUTING.md` に割当てた項目が実際に記載されているか検証する。

- [ ] **Step 1: `CONTRIBUTING.md` を全文読む**

```bash
cd /workspace/Yagra
cat CONTRIBUTING.md | head -200
cat CONTRIBUTING.md | tail -120
```

- [ ] **Step 2: 以下のキーワードの記載有無をチェック**

```bash
cd /workspace/Yagra
echo "=== uv 強制 ==="
grep -in "uv add\|uv remove\|uv sync\|pip install" CONTRIBUTING.md
echo "=== dotenvx / env ==="
grep -in "dotenvx\|\.env\.development\|\.env\.production\|\.env\.keys" CONTRIBUTING.md
echo "=== CI 必須 ==="
grep -in "CI\|GitHub Actions\|pre-commit\|quality gate" CONTRIBUTING.md
echo "=== SemVer / Release ==="
grep -in "semantic versioning\|semver\|changelog\|keep a changelog" CONTRIBUTING.md
```

- [ ] **Step 3: 欠落項目をレポート**

結果から、以下 4 項目の CONTRIBUTING.md 記載状況を判定：

| 項目 | 期待記載 | 判定 |
|------|----------|------|
| `uv add / uv remove / uv sync` 強制、`pip install` 禁止 | 記載あり | ○ / × |
| `.env.development` / `.env.production` + dotenvx `encrypted:` 形式 | 記載あり | ○ / × |
| CI 必須・品質ゲート不一致許容しない | 記載あり | ○ / × |
| リリース手順（SemVer / Keep a Changelog / 3 箇所同期） | 一部記載でも可 | ○ / × |

**欠落があれば、Phase 1 の最後の Task に CONTRIBUTING.md 追記タスクを追加する（実行は別 PR として提案）**。判定結果をコミットメッセージに含めて記録する。

- [ ] **Step 4: 監査結果をコミット（記録のみ、CONTRIBUTING.md に変更なしなら空コミット不要）**

欠落がなかった場合はスキップ。欠落があり、本 Phase 内で追記することになった場合のみ以下を実行：

```bash
cd /workspace/Yagra
git add CONTRIBUTING.md
git commit -m "docs: CONTRIBUTING.md に運用規約の欠落項目を追記"
```

---

### Task 16: Phase 1 統合検証

**Files:**
- Verify: `.claude/` 構造全体

- [ ] **Step 1: `.claude/` 構造を確認**

```bash
cd /workspace/Yagra
find .claude -type f | sort
```

Expected: 以下の構成が揃っている：
- `.claude/settings.json`
- `.claude/settings.local.json.example`
- `.claude/scripts/.gitkeep`
- `.claude/rules/skill-catalog.md`
- `.claude/rules/security.md`
- `.claude/rules/architecture.md`
- `.claude/agents/architecture-reviewer.md`
- `.claude/skills/task-design-gate/SKILL.md` + 2 references
- `.claude/skills/git-commit/SKILL.md`
- `.claude/skills/adr-management/SKILL.md` + 1 reference
- `.claude/skills/api-spec-sync/SKILL.md` + 3 references
- `.claude/skills/python-uv-ci-setup/SKILL.md` + 2 references
- `.claude/skills/python-project-bootstrap/SKILL.md` + 5 references
- `.claude/skills/release-ops/SKILL.md`

- [ ] **Step 2: 各 SKILL.md フロントマターの必須キー検証**

```bash
cd /workspace/Yagra
for f in .claude/skills/*/SKILL.md; do
  echo "=== $f ==="
  head -5 "$f"
done
```

Expected: 全ファイルが以下の形式で開始する：
```
---
name: <skill-name>
description: <1 行説明>
---
```

- [ ] **Step 3: 旧パス参照の残存チェック**

```bash
cd /workspace/Yagra
grep -rn "docs/ai/playbook-assets\|docs/ai/playbooks\|docs/ai/canonical" .claude/ CLAUDE.md
```

Expected: 結果が空（旧パス参照なし）。

- [ ] **Step 4: CLAUDE.md / rules の `@` 参照先が存在するか確認**

```bash
cd /workspace/Yagra
for ref in README.md CONTRIBUTING.md docs/architecture docs/rules/code_architecture docs/rules/solid docs/adr docs/product docs/api .claude/rules/skill-catalog.md .claude/rules/security.md .claude/skills/task-design-gate/SKILL.md .claude/skills/release-ops/SKILL.md; do
  if [ -e "$ref" ]; then
    echo "OK: $ref"
  else
    echo "MISSING: $ref"
  fi
done
```

Expected: 全て `OK:`。`MISSING:` が出た場合は参照先の存在を確認し、未作成なら作成、存在するがパスが違うなら修正。

- [ ] **Step 5: pytest / ruff / mypy を実行して回帰がないことを確認**

```bash
cd /workspace/Yagra
uv run pre-commit run --all-files 2>&1 | tail -20
uv run pytest -q 2>&1 | tail -10
```

Expected: いずれも成功。失敗時は原因特定（Phase 1 変更由来なら修正、既存バグなら別 Issue）。

- [ ] **Step 6: Phase 1 完了コミット（すでに個別コミット済みのため、マージ用タグ付け）**

```bash
cd /workspace/Yagra
git log --oneline main..feat/claude-code-setup
```

Expected: Task 0 〜 Task 15 の各コミットが順に表示される。

- [ ] **Step 7: Phase 1 を PR として用意**

```bash
cd /workspace/Yagra
git push -u origin feat/claude-code-setup
```

PR タイトル: `feat: Claude Code .claude/ 構造を追加（Phase 1/3）`
PR 本文:
```
## Summary
Claude Code ネイティブの `.claude/` 構造を非破壊的に追加する Phase 1。
旧 AGENTS.md / docs/ai/ / .cursor/ は Phase 2-3 で整理する。

## 追加内容
- `.claude/settings.json`（Layer 1 permissions）
- `.claude/rules/` 3 ファイル（skill-catalog / security / architecture）
- `.claude/agents/architecture-reviewer.md`
- `.claude/skills/` 7 スキル（6 移行 + release-ops 新規）
- `CLAUDE.md` 実体化
- `.gitignore` 調整

## 設計仕様
docs/superpowers/specs/2026-04-23-yagra-claude-code-setup-design.md

## Test plan
- [ ] `.claude/` 構造の確認
- [ ] 旧パス参照の残存チェック
- [ ] `uv run pre-commit run --all-files` 成功
- [ ] `uv run pytest -q` 成功
- [ ] Claude Code セッションで CLAUDE.md と skill-catalog が参照されること
```

**この時点でユーザーに PR レビューを依頼する。マージ後に Phase 2 へ進む。**

---

## Phase 2: 移動

### Task 17: `agent-integration-guide.md` / `ci-integration-guide.md` 監査

**Files:**
- Read: `docs/ai/agent-integration-guide.md`
- Read: `docs/ai/ci-integration-guide.md`

**Context:** 仕様書 Phase 2 の判断基準 (a)〜(d) を適用する。

- [ ] **Step 1: canonical 配布物かどうかの判定**

```bash
cd /workspace/Yagra
# 自動生成コメントの確認
head -10 docs/ai/agent-integration-guide.md
head -10 docs/ai/ci-integration-guide.md

# sync_ai_context.py のソースリストに含まれるか
grep -n "agent-integration-guide\|ci-integration-guide" scripts/sync_ai_context.py || echo "NOT in sync script"
```

- [ ] **Step 2: 判定**

| ファイル | 自動生成コメント | sync_ai_context.py 参照 | 内容の主題 | 判定 |
|----------|------------------|-------------------------|------------|------|
| `agent-integration-guide.md` | ... | ... | ... | 保持 / 削除 |
| `ci-integration-guide.md` | ... | ... | ... | 保持 / 削除 |

判定基準（仕様書 Phase 2 より）:
- (a) `scripts/sync_ai_context.py` のソース一覧に含まれる → 生成物 → 削除
- (b) ファイル冒頭に「自動生成」「do not edit」等の注記がある → 生成物 → 削除
- (c) 内容が canonical と重複 → 生成物 → 削除
- (d) いずれでもなく運用知識を含む → 手書き → 移動

- [ ] **Step 3: 保持するファイルを移動**

**判定が「保持」の場合のみ実行**:

```bash
cd /workspace/Yagra
# 例: agent-integration-guide.md が保持の場合
git mv docs/ai/agent-integration-guide.md docs/agent-integration-guide.md
# 例: ci-integration-guide.md が保持の場合
git mv docs/ai/ci-integration-guide.md docs/ci-integration-guide.md
```

- [ ] **Step 4: 相互参照のパス更新（必要な場合）**

```bash
cd /workspace/Yagra
grep -rn "docs/ai/agent-integration-guide\|docs/ai/ci-integration-guide" . --include="*.md" --exclude-dir=.git
```

該当ファイルを Edit で更新。CLAUDE.md 内の参照も調整。

- [ ] **Step 5: コミット**

```bash
cd /workspace/Yagra
git add -A
git status
git commit -m "docs: integration-guide を docs/ 直下に整理（Phase 2）"
```

判定が「削除」のみだった場合はここではコミット対象なし（Phase 3 で削除扱い）。

---

### Task 18: `docs/ai/` 残存ファイルの最終確認

**Files:**
- Verify: `docs/ai/`

- [ ] **Step 1: `docs/ai/` 下に残っている保持候補ファイルを列挙**

```bash
cd /workspace/Yagra
find docs/ai -maxdepth 1 -type f
```

Expected: Task 17 で移動済みの場合は空リスト、未判定の手書きドキュメントがあればここで判定する。

- [ ] **Step 2: 保持すべきファイルがあれば移動**

残存ファイルがあれば、Task 17 と同じ基準で判定し、保持なら `docs/` 直下へ移動する。

- [ ] **Step 3: 参照破れの最終チェック**

```bash
cd /workspace/Yagra
grep -rn "docs/ai/" . --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --exclude-dir=.git --exclude-dir=.claude | grep -v "docs/ai/canonical\|docs/ai/playbooks\|docs/ai/playbook-assets"
```

Expected: 空（Phase 3 で削除される canonical/playbooks/playbook-assets 以外の `docs/ai/` 参照がない）。

- [ ] **Step 4: Phase 2 完了コミット（変更があれば）**

変更がなかった場合はこの Task ごとスキップ可。あれば:

```bash
cd /workspace/Yagra
git add -A
git commit -m "docs: docs/ai/ 残存ドキュメントを整理（Phase 2）"
```

- [ ] **Step 5: Phase 2 PR 準備**

```bash
cd /workspace/Yagra
git push origin feat/claude-code-setup
```

Phase 1 の PR にコミットを追加するか、別ブランチ (`feat/claude-code-setup-phase2`) を切るかはチーム方針に従う。推奨は**同一 PR に Phase 2 コミットを追加**（小規模変更のため）。

---

## Phase 3: 削除

### Task 19: 旧パス参照を全リポジトリから除去

**Files:**
- Potentially modify: 参照を含む各種ファイル

**Context:** `AGENTS.md`, `docs/ai/canonical/`, `docs/ai/playbooks/`, `.cursor/`, `scripts/sync_ai_context.py` への参照を CI / README / その他から除去する。

- [ ] **Step 1: 参照箇所を列挙**

```bash
cd /workspace/Yagra
echo "=== AGENTS.md references ==="
grep -rn "AGENTS\.md" . --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=docs/superpowers

echo "=== docs/ai/ references ==="
grep -rn "docs/ai/" . --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=docs/superpowers

echo "=== sync_ai_context.py references ==="
grep -rn "sync_ai_context" . --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=docs/superpowers

echo "=== .cursor references ==="
grep -rn "\.cursor" . --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.gitignore" --exclude-dir=.git --exclude-dir=.cursor --exclude-dir=.claude --exclude-dir=docs/superpowers
```

- [ ] **Step 2: 各参照を処置**

見つかった参照ごとに：
- README.md / CONTRIBUTING.md などドキュメント内の参照 → 新しいパス (`.claude/skills/...`) または `CLAUDE.md` へのリンクに置換
- `.github/workflows/*.yml` 内で `sync_ai_context.py` が呼ばれている場合 → 該当ステップを削除
- `pyproject.toml` や `Makefile` に参照あれば同様に整理

具体的な置換ルール:
- `AGENTS.md` → `CLAUDE.md`
- `docs/ai/playbooks/<name>.md` → `.claude/skills/<name>/SKILL.md`
- `docs/ai/canonical/<x>` → 削除 or `CLAUDE.md`/`CONTRIBUTING.md` の該当箇所へ
- `python3 scripts/sync_ai_context.py` → 削除
- `.cursor/rules/*.mdc` → 削除（参照は不要に）

- [ ] **Step 3: 検証**

```bash
cd /workspace/Yagra
grep -rn "AGENTS\.md\|docs/ai/\|sync_ai_context\|\.cursor" . --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=docs/superpowers --exclude-dir=docs/ai --exclude-dir=.cursor | grep -v "docs/ai/canonical\|docs/ai/playbooks\|docs/ai/playbook-assets\|scripts/sync_ai_context\|AGENTS\.md$\|\.cursor$" || echo "All old refs cleaned"
```

Expected: `All old refs cleaned`

- [ ] **Step 4: コミット**

```bash
cd /workspace/Yagra
git add -A
git commit -m "chore: 旧パス参照（AGENTS.md / docs/ai/ / sync_ai_context）を新構造に置換"
```

---

### Task 20: `AGENTS.md` と `.cursor/` を削除

**Files:**
- Delete: `AGENTS.md`
- Delete: `.cursor/`

- [ ] **Step 1: `AGENTS.md` を削除**

```bash
cd /workspace/Yagra
git rm AGENTS.md
```

- [ ] **Step 2: `.cursor/` を削除**

```bash
cd /workspace/Yagra
git rm -r .cursor/
```

- [ ] **Step 3: 削除後の状態を確認**

```bash
cd /workspace/Yagra
ls AGENTS.md 2>&1 || echo "AGENTS.md removed"
ls .cursor/ 2>&1 || echo ".cursor removed"
```

Expected: 両方 `removed` メッセージ。

- [ ] **Step 4: コミット**

```bash
cd /workspace/Yagra
git commit -m "chore: AGENTS.md と .cursor/ を削除（Claude Code 専用化）"
```

---

### Task 21: `docs/ai/` 配下を削除

**Files:**
- Delete: `docs/ai/canonical/`
- Delete: `docs/ai/playbooks/`
- Delete: `docs/ai/playbook-assets/`
- Delete: `docs/ai/`（空化後）

- [ ] **Step 1: `docs/ai/` 配下の残存ファイルを確認**

```bash
cd /workspace/Yagra
find docs/ai -type f
```

Task 17-18 で保持判定したファイルが移動済みであることを前提とする。残っているのは canonical / playbooks / playbook-assets のみのはず。

- [ ] **Step 2: 削除**

```bash
cd /workspace/Yagra
git rm -r docs/ai/canonical/
git rm -r docs/ai/playbooks/
git rm -r docs/ai/playbook-assets/
```

- [ ] **Step 3: `docs/ai/` が空になったか確認し、空なら削除**

```bash
cd /workspace/Yagra
ls -la docs/ai/ 2>&1
```

もし残存ファイル・ディレクトリがなければ:

```bash
cd /workspace/Yagra
rmdir docs/ai/
```

- [ ] **Step 4: コミット**

```bash
cd /workspace/Yagra
git add -A
git commit -m "chore: docs/ai/ 配下（canonical / playbooks / playbook-assets）を削除"
```

---

### Task 22: `scripts/sync_ai_context.py` と `scripts/bootstrap_after_canonical.py` を削除

**Files:**
- Delete: `scripts/sync_ai_context.py`
- Delete: `scripts/bootstrap_after_canonical.py`

**Context:** canonical 配布モデルに依存するスクリプトを削除。`scripts/playbooks/` 配下は保持（補助スクリプト）。

- [ ] **Step 1: 削除対象を確認**

```bash
cd /workspace/Yagra
ls -la scripts/sync_ai_context.py scripts/bootstrap_after_canonical.py
```

- [ ] **Step 2: 他から参照されていないことを再確認**

```bash
cd /workspace/Yagra
grep -rn "sync_ai_context\|bootstrap_after_canonical" . --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=docs/superpowers
```

Expected: 結果が空（自己参照以外）。

- [ ] **Step 3: 削除**

```bash
cd /workspace/Yagra
git rm scripts/sync_ai_context.py scripts/bootstrap_after_canonical.py
```

- [ ] **Step 4: `scripts/playbooks/` が保持されていることを確認**

```bash
cd /workspace/Yagra
ls scripts/playbooks/
```

Expected: `api-spec-sync` と `python-project-bootstrap` のサブディレクトリが存在。

- [ ] **Step 5: コミット**

```bash
cd /workspace/Yagra
git commit -m "chore: canonical 配布スクリプト（sync_ai_context / bootstrap_after_canonical）を削除"
```

---

### Task 23: Phase 3 最終検証

**Files:**
- Verify: リポジトリ全体

- [ ] **Step 1: 削除対象が全て除去されていることを確認**

```bash
cd /workspace/Yagra
for p in AGENTS.md .cursor docs/ai scripts/sync_ai_context.py scripts/bootstrap_after_canonical.py; do
  if [ -e "$p" ]; then
    echo "STILL EXISTS: $p"
  else
    echo "REMOVED: $p"
  fi
done
```

Expected: 全て `REMOVED:`。

- [ ] **Step 2: 参照破れの最終チェック**

```bash
cd /workspace/Yagra
grep -rn "AGENTS\.md\|docs/ai/\|sync_ai_context\|bootstrap_after_canonical\|\.cursor" . --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=docs/superpowers | grep -v "^Binary" | head -20
```

Expected: 結果が空（または `docs/superpowers/specs/` 内の仕様書言及のみ）。

- [ ] **Step 3: pre-commit / pytest 実行**

```bash
cd /workspace/Yagra
uv run pre-commit run --all-files 2>&1 | tail -20
uv run pytest -q 2>&1 | tail -10
```

Expected: 両方成功。

- [ ] **Step 4: Claude Code セッション動作確認（手動）**

- 新しい Claude Code セッションを起動
- `CLAUDE.md` が自動注入されることを確認
- `/task-design-gate` 等のスキルが呼び出せることを確認
- `src/yagra/` 配下のファイルを読んだ際に `architecture.md` ルールが注入されることを確認
- `.env` 読取が deny されることを確認（`cat .env.development` などを試す → deny される）

- [ ] **Step 5: Phase 3 完了、最終コミット（変更があれば）**

ここまでの Task で個別コミット済みのため、新規コミットは通常不要。

- [ ] **Step 6: PR 更新 / マージ**

```bash
cd /workspace/Yagra
git log --oneline main..feat/claude-code-setup | head -30
git push origin feat/claude-code-setup
```

PR 説明を Phase 2-3 完了の内容で更新する。

PR タイトル例（単一 PR 運用の場合）: `feat: Claude Code ネイティブ構造に完全移行（3 フェーズ）`

Phase ごとに PR を分けた場合は 3 つ目の PR タイトル例: `chore: 旧 canonical モデル関連ファイルを削除（Phase 3/3）`

---

## 完了基準

仕様書セクション 13（成功基準）の 7 項目を確認:

- [ ] Claude Code セッションで `CLAUDE.md` + `.claude/rules/*` が正常注入される
- [ ] 7 スキル全てが `/<skill-name>` で呼び出し可能
- [ ] `architecture-reviewer` が `src/yagra/` 配下の変更レビューで機能する
- [ ] `.env` 読取試行が Layer 1 で deny される
- [ ] 既存 `pytest` / `ruff` / `mypy` / `pre-commit` が全てパス
- [ ] `docs/ai/`, `.cursor/`, `AGENTS.md`, `scripts/sync_ai_context.py` への参照がリポジトリ内から全て除去
- [ ] `CONTRIBUTING.md` との情報重複が `CLAUDE.md` 内に存在しない

---

## ロールバック計画

Phase 1 が問題を起こした場合:

```bash
cd /workspace/Yagra
git checkout main
git branch -D feat/claude-code-setup
```

Phase 2-3 が問題を起こした場合（PR を分けていれば Phase 1 はそのまま残る）:
- 該当 PR を revert する
- Phase 1 状態では旧ファイルがまだ存在し、古い AGENTS.md 経路も動作する

マージ後に発見された致命的問題:

```bash
cd /workspace/Yagra
git revert <merge-commit-hash>
```

シンボリックリンク `CLAUDE.md -> AGENTS.md` の復元は `git checkout <pre-migration-commit> -- CLAUDE.md AGENTS.md` で可能。
