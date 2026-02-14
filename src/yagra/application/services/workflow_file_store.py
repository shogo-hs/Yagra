"""workflow ファイルの保存・バックアップ操作を提供する。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from os import PathLike
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

import yaml


class WorkflowBackupNotFoundError(FileNotFoundError):
    """指定されたバックアップが見つからない場合の例外。"""


@dataclass(frozen=True, slots=True)
class WorkflowBackupRecord:
    """バックアップ作成結果を保持する。"""

    backup_id: str
    workflow_backup_path: Path
    ui_state_backup_path: Path


class WorkflowFileStore:
    """workflow と UI サイドカーの永続化処理を担当する。"""

    def __init__(self, backup_root: str | PathLike[str]) -> None:
        """保存先設定を初期化する。

        Args:
            backup_root: バックアップ格納ルートディレクトリ。
        """
        self._backup_root = Path(backup_root).expanduser().resolve()

    def load_workflow(self, workflow_path: str | PathLike[str]) -> dict[str, Any]:
        """Workflow YAML を辞書として読み込む。

        Args:
            workflow_path: 読み込み対象 workflow パス。

        Returns:
            読み込んだ workflow 辞書。

        Raises:
            ValueError: YAML が辞書形式でない場合。
        """
        path = Path(workflow_path).expanduser().resolve()
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"workflow の読み込みに失敗しました: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"workflow must be a mapping: {path}")
        return dict(payload)

    def load_ui_state(self, ui_state_path: str | PathLike[str]) -> dict[str, Any]:
        """UI サイドカー JSON を辞書として読み込む。

        Args:
            ui_state_path: 読み込み対象 UI サイドカーパス。

        Returns:
            読み込んだ UI サイドカー辞書。未存在時は空辞書。

        Raises:
            ValueError: JSON が辞書形式でない場合。
        """
        path = Path(ui_state_path).expanduser().resolve()
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"ui_state の読み込みに失敗しました: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"ui_state must be a mapping: {path}")
        return dict(payload)

    def write_workflow_atomic(
        self,
        workflow_path: str | PathLike[str],
        payload: dict[str, Any],
    ) -> None:
        """Workflow YAML を atomic write で保存する。

        Args:
            workflow_path: 保存対象 workflow パス。
            payload: 保存する workflow データ。
        """
        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        self._atomic_write_text(Path(workflow_path).expanduser().resolve(), text)

    def write_ui_state_atomic(
        self,
        ui_state_path: str | PathLike[str],
        payload: dict[str, Any],
    ) -> None:
        """UI サイドカー JSON を atomic write で保存する。

        Args:
            ui_state_path: 保存対象 UI サイドカーパス。
            payload: 保存する UI サイドカーデータ。
        """
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self._atomic_write_text(Path(ui_state_path).expanduser().resolve(), text)

    def create_backup(
        self,
        workflow_path: str | PathLike[str],
        ui_state_path: str | PathLike[str],
        workflow_payload: dict[str, Any],
        ui_state_payload: dict[str, Any],
    ) -> WorkflowBackupRecord:
        """Workflow と UI サイドカーのバックアップを作成する。

        Args:
            workflow_path: 対象 workflow パス。
            ui_state_path: 対象 UI サイドカーパス。
            workflow_payload: バックアップ対象 workflow データ。
            ui_state_payload: バックアップ対象 UI サイドカーデータ。

        Returns:
            作成したバックアップ情報。
        """
        workflow_abspath = Path(workflow_path).expanduser().resolve()
        _ = Path(ui_state_path).expanduser().resolve()

        workflow_text = yaml.safe_dump(workflow_payload, sort_keys=False, allow_unicode=True)
        ui_state_text = (
            json.dumps(ui_state_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )

        digest = sha256(f"{workflow_text}\n{ui_state_text}".encode()).hexdigest()[:8]
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
        backup_id = f"{timestamp}_{digest}"

        backup_dir = self._backup_root / workflow_abspath.stem
        backup_dir.mkdir(parents=True, exist_ok=True)

        workflow_backup_path = backup_dir / f"{backup_id}.yaml"
        ui_state_backup_path = backup_dir / f"{backup_id}.workflow-ui.json"
        workflow_backup_path.write_text(workflow_text, encoding="utf-8")
        ui_state_backup_path.write_text(ui_state_text, encoding="utf-8")
        self._prune_backups(backup_dir)
        return WorkflowBackupRecord(
            backup_id=backup_id,
            workflow_backup_path=workflow_backup_path,
            ui_state_backup_path=ui_state_backup_path,
        )

    def restore_backup(
        self,
        workflow_path: str | PathLike[str],
        ui_state_path: str | PathLike[str],
        backup_id: str,
    ) -> None:
        """指定バックアップから workflow と UI サイドカーを復元する。

        Args:
            workflow_path: 復元先 workflow パス。
            ui_state_path: 復元先 UI サイドカーパス。
            backup_id: 復元対象バックアップID。

        Raises:
            WorkflowBackupNotFoundError: バックアップが存在しない場合。
        """
        workflow_abspath = Path(workflow_path).expanduser().resolve()
        ui_state_abspath = Path(ui_state_path).expanduser().resolve()
        backup_dir = self._backup_root / workflow_abspath.stem

        workflow_backup_path = backup_dir / f"{backup_id}.yaml"
        ui_state_backup_path = backup_dir / f"{backup_id}.workflow-ui.json"
        if not workflow_backup_path.exists() or not ui_state_backup_path.exists():
            raise WorkflowBackupNotFoundError(
                f"backup not found: {backup_id} ({workflow_backup_path}, {ui_state_backup_path})"
            )

        workflow_text = workflow_backup_path.read_text(encoding="utf-8")
        ui_state_text = ui_state_backup_path.read_text(encoding="utf-8")
        self._atomic_write_text(workflow_abspath, workflow_text)
        self._atomic_write_text(ui_state_abspath, ui_state_text)

    def _atomic_write_text(self, path: Path, text: str) -> None:
        """同一ファイルシステム内で atomic write を行う。

        Args:
            path: 書き込み先パス。
            text: 書き込む文字列。
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.tmp-",
            suffix=f"-{uuid4().hex}",
            delete=False,
        ) as handle:
            handle.write(text)
            temp_path = Path(handle.name)

        try:
            os.replace(temp_path, path)
        except OSError:
            temp_path.unlink(missing_ok=True)
            raise

    def _prune_backups(self, backup_dir: Path, keep_last: int = 30) -> None:
        """バックアップ世代数を制限する。

        Args:
            backup_dir: 対象バックアップディレクトリ。
            keep_last: 残す世代数。
        """
        workflow_backups = sorted(backup_dir.glob("*.yaml"))
        if len(workflow_backups) <= keep_last:
            return

        stale_workflows = workflow_backups[: len(workflow_backups) - keep_last]
        for stale_workflow in stale_workflows:
            stale_ui_state = backup_dir / f"{stale_workflow.stem}.workflow-ui.json"
            stale_workflow.unlink(missing_ok=True)
            stale_ui_state.unlink(missing_ok=True)
