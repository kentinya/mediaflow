"""Bounded manual Scan domain values.

Manual Scan is intentionally a discovery-only workflow.  These values describe the
operator's exact scope and the durable evidence produced by the StorageScanner; they do
not contain provider, planning, execution, or destination data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from mediaflow.domain.library import ScanMode
from mediaflow.domain.scanner import FileChange, FileScanStatus
from mediaflow.domain.task_persistence import PersistentTaskStatus


class ManualScanScopeKind(StrEnum):
    FILE = "file"
    RESOURCE_LIBRARY = "resource_library"


ScanScopeKind = ManualScanScopeKind


def _bounded_identifier(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"manual Scan {label} is required")
    value = value.strip()
    if len(value) > maximum or any(character.isspace() for character in value):
        raise ValueError(f"manual Scan {label} is invalid")
    return value


@dataclass(frozen=True)
class ManualScanRequest:
    """An exact, path-free Scan admission request."""

    scope_kind: ManualScanScopeKind
    resource_library_id: str
    mode: ScanMode
    file_id: str | None = None
    source_occurrence_id: str | None = None
    source_fingerprint: str | None = None

    def __post_init__(self) -> None:
        kind = ManualScanScopeKind(self.scope_kind)
        object.__setattr__(self, "scope_kind", kind)
        object.__setattr__(self, "mode", ScanMode(self.mode))
        object.__setattr__(
            self,
            "resource_library_id",
            _bounded_identifier(self.resource_library_id, "ResourceLibrary ID"),
        )
        if kind is ManualScanScopeKind.FILE:
            object.__setattr__(self, "file_id", _bounded_identifier(self.file_id, "file ID"))
            object.__setattr__(
                self,
                "source_occurrence_id",
                _bounded_identifier(self.source_occurrence_id, "source occurrence ID"),
            )
            fingerprint = _bounded_identifier(
                self.source_fingerprint, "source fingerprint", maximum=128
            )
            if len(fingerprint) != 64 or any(
                character not in "0123456789abcdefABCDEF" for character in fingerprint
            ):
                raise ValueError("manual Scan source fingerprint is invalid")
            object.__setattr__(self, "source_fingerprint", fingerprint.lower())
        elif any(
            value is not None
            for value in (self.file_id, self.source_occurrence_id, self.source_fingerprint)
        ):
            raise ValueError("ResourceLibrary Scan cannot include FileIndex source identity")

    @property
    def scope_id(self) -> str:
        return (
            self.file_id
            if self.scope_kind is ManualScanScopeKind.FILE
            else self.resource_library_id
        )

    def document(self) -> dict[str, object]:
        return {
            "scopeKind": self.scope_kind.value,
            "scopeId": self.scope_id,
            "resourceLibraryId": self.resource_library_id,
            "fileId": self.file_id,
            "sourceOccurrenceId": self.source_occurrence_id,
            "sourceFingerprint": self.source_fingerprint,
            "mode": self.mode.value,
        }


@dataclass(frozen=True)
class ManualScanItemOutcome:
    item_id: str
    task_id: str
    storage_id: str
    resource_library_id: str
    source_path: str
    file_id: str | None
    status: FileScanStatus
    change: FileChange | None
    stage: str
    created_at: datetime
    updated_at: datetime
    source_occurrence_id: str | None = None
    source_fingerprint: str | None = None
    source_fingerprint_state: str = "unverified"
    error: str | None = None
    known_effects: str = "none"
    retry_safe: bool = True
    next_action: str = "inspect the current FileIndex state"

    def document(self) -> dict[str, object]:
        return {
            "itemId": self.item_id,
            "taskId": self.task_id,
            "storageId": self.storage_id,
            "resourceLibraryId": self.resource_library_id,
            "sourcePath": self.source_path,
            "fileId": self.file_id,
            "status": self.status.value,
            "change": self.change.value if self.change else None,
            "stage": self.stage,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "sourceOccurrenceId": self.source_occurrence_id,
            "sourceFingerprint": self.source_fingerprint,
            "sourceFingerprintState": self.source_fingerprint_state,
            "error": self.error,
            "knownEffects": self.known_effects,
            "retrySafe": self.retry_safe,
            "nextAction": self.next_action,
            "sideEffects": "none",
        }


@dataclass(frozen=True)
class ManualScanTask:
    task_id: str
    scope_kind: ManualScanScopeKind
    resource_library_id: str
    mode: ScanMode
    status: PersistentTaskStatus
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    created_at: datetime
    updated_at: datetime
    file_id: str | None = None
    source_occurrence_id: str | None = None
    source_fingerprint: str | None = None
    storage_id: str | None = None
    source_path: str | None = None
    cancellation_requested: bool = False
    progress: dict[str, int] = field(default_factory=dict)
    errors: tuple[dict[str, object], ...] = ()
    reconciliation_complete: bool = False
    failure_stage: str | None = None
    known_effects: str = "none"
    retry_safe: bool = True
    next_action: str = "inspect the persisted Scan Task"

    @property
    def scope_id(self) -> str:
        return (
            self.file_id
            if self.scope_kind is ManualScanScopeKind.FILE
            else self.resource_library_id
        )

    def document(self, items: tuple[ManualScanItemOutcome, ...] = ()) -> dict[str, Any]:
        progress = dict(self.progress)
        return {
            "taskId": self.task_id,
            "scopeKind": self.scope_kind.value,
            "scopeId": self.scope_id,
            "resourceLibraryId": self.resource_library_id,
            "fileId": self.file_id,
            "sourceOccurrenceId": self.source_occurrence_id,
            "sourceFingerprint": self.source_fingerprint,
            "storageId": self.storage_id,
            "sourcePath": self.source_path,
            "mode": self.mode.value,
            "status": self.status.value,
            "configurationSnapshotId": self.configuration_snapshot_id,
            "configurationSnapshotDigest": self.configuration_snapshot_digest,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "cancellationRequested": self.cancellation_requested,
            "progress": progress,
            "errors": [dict(error) for error in self.errors],
            "reconciliationComplete": self.reconciliation_complete,
            "failureStage": self.failure_stage,
            "knownEffects": self.known_effects,
            "retrySafe": self.retry_safe,
            "nextAction": self.next_action,
            "sideEffects": "none",
            "items": [item.document() for item in items],
        }
