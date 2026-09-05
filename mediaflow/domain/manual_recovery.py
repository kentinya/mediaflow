"""Durable link between an original manual Organize item and its continued execution.

The link is deliberately read-oriented persistence around the existing one-shot
``ManualExecutionAuthorization``.  It records that a new exact Preview and
authorization were created from an original manual execution item after a
completed single-item re-analysis, so the operator can return to the original
Organize journey after reload.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class ManualRecoveryLinkStatus(StrEnum):
    AUTHORIZED = "authorized"
    CONSUMED = "consumed"
    STALE = "stale"


@dataclass(frozen=True)
class ManualRecoveryLink:
    """One bounded source-item -> exact continuation authority record."""

    link_id: str
    source_task_id: str
    source_item_id: str
    analysis_continuation_id: str
    analysis_task_id: str
    analysis_result_id: str
    intent_id: str
    preview_id: str
    authorization_id: str
    actor: str
    status: ManualRecoveryLinkStatus
    created_at: datetime
    updated_at: datetime
    execution_id: str | None = None

    def next_action(self) -> str:
        if self.status is ManualRecoveryLinkStatus.AUTHORIZED:
            return (
                "inspect the linked exact Preview and execute the one-shot continuation "
                "authority once with explicit confirmation"
            )
        if self.status is ManualRecoveryLinkStatus.CONSUMED:
            return (
                "inspect the linked continued execution and its independent "
                "Task/TaskItem/Result/checkpoint evidence"
            )
        return (
            "refresh the original manual item checkpoint and request a fresh "
            "current-source Preview before authorizing execution"
        )

    def document(self) -> dict[str, object]:
        return {
            "link_id": self.link_id,
            "source_task_id": self.source_task_id,
            "source_item_id": self.source_item_id,
            "analysis_continuation_id": self.analysis_continuation_id,
            "analysis_task_id": self.analysis_task_id,
            "analysis_result_id": self.analysis_result_id,
            "intent_id": self.intent_id,
            "preview_id": self.preview_id,
            "authorization_id": self.authorization_id,
            "execution_id": self.execution_id,
            "actor": self.actor,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "next_action": self.next_action(),
            "authorizationPath": (
                "/api/v1/manual-execution-authorizations/" + self.authorization_id
            ),
            "previewPath": "/api/v1/manual-previews/" + self.preview_id,
            "executionPath": (
                "/api/v1/manual-executions/" + self.execution_id
                if self.execution_id is not None
                else None
            ),
        }


class ManualRecoveryLinkRepository(Protocol):
    def create_manual_recovery_link(self, link: ManualRecoveryLink) -> None: ...
    def get_manual_recovery_link(self, link_id: str) -> ManualRecoveryLink | None: ...
    def get_manual_recovery_link_by_source(
        self, source_task_id: str, source_item_id: str
    ) -> ManualRecoveryLink | None: ...
    def get_manual_recovery_link_by_authorization(
        self, authorization_id: str
    ) -> ManualRecoveryLink | None: ...
    def complete_manual_recovery_link(
        self,
        link_id: str,
        *,
        execution_id: str,
        now: datetime,
    ) -> ManualRecoveryLink: ...
    def mark_manual_recovery_link_stale(
        self,
        link_id: str,
        *,
        now: datetime,
    ) -> ManualRecoveryLink: ...
