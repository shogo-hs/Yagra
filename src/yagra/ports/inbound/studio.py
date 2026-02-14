"""Workflow Studio の inbound port 契約を定義する。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StudioError(Exception):
    """Studio 操作で返すアプリケーションエラー。"""

    error: str
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """API 応答へ変換可能な辞書を返す。"""
        payload: dict[str, Any] = {"error": self.error}
        if self.message is not None:
            payload["message"] = self.message
        payload.update(self.details)
        return payload


class StudioBadRequestError(StudioError):
    """入力値が不正な場合のエラー。"""


class StudioNotFoundError(StudioError):
    """対象リソースが見つからない場合のエラー。"""


class StudioConflictError(StudioError):
    """競合が発生した場合のエラー。"""


class StudioUnprocessableEntityError(StudioError):
    """構文は正しいが処理不能な場合のエラー。"""


class StudioPort(ABC):
    """Workflow Studio の入力境界。"""

    @abstractmethod
    def get_studio_target(self) -> dict[str, Any]:
        """現在の Studio ターゲット情報を返す。"""

    @abstractmethod
    def get_studio_files(self) -> dict[str, Any]:
        """ワークスペース配下の workflow 候補一覧を返す。"""

    @abstractmethod
    def open_studio_target(self, body: dict[str, Any]) -> dict[str, Any]:
        """既存 workflow を Studio ターゲットとして開く。"""

    @abstractmethod
    def create_studio_target(self, body: dict[str, Any]) -> dict[str, Any]:
        """新規 workflow を作成して Studio ターゲットとして開く。"""

    @abstractmethod
    def get_workflow(self) -> dict[str, Any]:
        """現在の workflow と UI state を返す。"""

    @abstractmethod
    def get_form(self) -> dict[str, Any]:
        """フォーム編集向け workflow 表示情報を返す。"""

    @abstractmethod
    def diff(self, body: dict[str, Any]) -> dict[str, Any]:
        """編集案の差分を返す。"""

    @abstractmethod
    def form_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        """フォーム編集入力から差分プレビューを返す。"""

    @abstractmethod
    def catalog_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        """Catalog 設定プレビューを返す。"""

    @abstractmethod
    def save(self, body: dict[str, Any]) -> dict[str, Any]:
        """編集案を保存する。"""

    @abstractmethod
    def rollback(self, body: dict[str, Any]) -> dict[str, Any]:
        """バックアップ ID を指定して復元する。"""
