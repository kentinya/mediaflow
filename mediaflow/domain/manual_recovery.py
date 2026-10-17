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


class ManualRecoveryPreparationStatus(StrEnum):
    """Durable lifecycle of one non-authorizing recovery plan summary.

    A preparation records that the current source item was re-analyzed under
    its own pinned configuration and that an exact zero-mutation Preview now
    holds the operator-visible plan summary.  ``PREPARED`` means the summary is
    readable and the operator may still explicitly confirm a ready subset;
    it never means execution authority exists.  ``CONFIRMED`` records that an
    exact subset was admitted through the existing one-shot authority path and
    links that execution.  ``SUPERSEDED`` and ``STALE`` keep the historical
    summary inspectable while refusing to treat it as the current plan.
    """

    PREPARED = "prepared"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"
    STALE = "stale"


@dataclass(frozen=True)
class ManualRecoveryPreparation:
    """One durable, non-authorizing plan summary for a recovery source item.

    The record deliberately carries **no** ``authorization_id`` while it is
    ``PREPARED``: a summary is a read/prepare artifact, and the schema must not
    force a fake authorization to store it.  ``authorization_id`` and
    ``execution_id`` are populated only when the operator explicitly confirms
    an exact ready subset, which consumes the existing one-shot authority.
    """

    preparation_id: str
    source_task_id: str
    source_item_id: str
    analysis_continuation_id: str
    analysis_task_id: str
    analysis_result_id: str
    intent_id: str
    preview_id: str
    intent_version: int
    checkpoint_version: str
    input_fingerprint: str
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    actor: str
    status: ManualRecoveryPreparationStatus
    created_at: datetime
    updated_at: datetime
    authorization_id: str | None = None
    execution_id: str | None = None

    @property
    def prepared(self) -> bool:
        return self.status is ManualRecoveryPreparationStatus.PREPARED

    def next_action(self) -> str:
        if self.status is ManualRecoveryPreparationStatus.PREPARED:
            return (
                "review the current plan summary, select the ready subset and explicitly "
                "confirm the exact Organize action"
            )
        if self.status is ManualRecoveryPreparationStatus.CONFIRMED:
            return "inspect the linked execution and its independent Task/TaskItem/Result evidence"
        if self.status is ManualRecoveryPreparationStatus.SUPERSEDED:
            return (
                "a newer decision or analysis replaced this summary; request a fresh "
                "summary from the current item state"
            )
        return (
            "the original source or pinned configuration changed; re-check the item and "
            "request a fresh summary"
        )

    def document(self) -> dict[str, object]:
        return {
            "preparation_id": self.preparation_id,
            "source_task_id": self.source_task_id,
            "source_item_id": self.source_item_id,
            "analysis_continuation_id": self.analysis_continuation_id,
            "analysis_task_id": self.analysis_task_id,
            "analysis_result_id": self.analysis_result_id,
            "intent_id": self.intent_id,
            "preview_id": self.preview_id,
            "intent_version": self.intent_version,
            "checkpoint_version": self.checkpoint_version,
            "input_fingerprint": self.input_fingerprint,
            "configuration_snapshot_id": self.configuration_snapshot_id,
            "configuration_snapshot_digest": self.configuration_snapshot_digest,
            "actor": self.actor,
            "status": self.status.value,
            "authorization_id": self.authorization_id,
            "execution_id": self.execution_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "next_action": self.next_action(),
            "previewPath": "/api/v1/manual-previews/" + self.preview_id,
            "executionPath": (
                "/api/v1/manual-executions/" + self.execution_id
                if self.execution_id is not None
                else None
            ),
        }


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
            "call the authorize-organize continuation route again to create a fresh "
            "exact Preview and one-shot authority once the linked re-analysis and "
            "current source evidence still hold"
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
    def supersede_manual_recovery_link(
        self,
        link_id: str,
        *,
        analysis_continuation_id: str,
        analysis_task_id: str,
        analysis_result_id: str,
        intent_id: str,
        preview_id: str,
        authorization_id: str,
        actor: str,
        now: datetime,
    ) -> ManualRecoveryLink: ...


class ManualRecoveryPreparationRepository(Protocol):
    def create_manual_recovery_preparation(
        self, preparation: ManualRecoveryPreparation
    ) -> None: ...
    def get_manual_recovery_preparation(
        self, preparation_id: str
    ) -> ManualRecoveryPreparation | None: ...
    def get_current_manual_recovery_preparation(
        self, source_task_id: str, source_item_id: str
    ) -> ManualRecoveryPreparation | None: ...
    def list_manual_recovery_preparations(
        self, source_task_id: str, source_item_id: str, *, limit: int = 32
    ) -> tuple[ManualRecoveryPreparation, ...]: ...
    def supersede_manual_recovery_preparation(
        self, preparation_id: str, *, now: datetime
    ) -> ManualRecoveryPreparation: ...
    def complete_manual_recovery_preparation(
        self,
        preparation_id: str,
        *,
        authorization_id: str,
        execution_id: str,
        now: datetime,
    ) -> ManualRecoveryPreparation: ...
