"""Durable, bounded exact-analysis admission for Preview work.

The existing exact Preview services analyse a whole definition scope or manual
intent synchronously inside the HTTP request.  A large scope therefore blocks
the request for the whole source walk and Provider batch, and the operator has
no durable identity to read back, no progress and no safe cancellation while
that work runs.

This module owns the *domain* shape of the durable analysis envelope that fixes
that: the exact pinned context the analysis was admitted for, its bounded
lifecycle, its cooperative pause/cancel flags and the durable identity of the
Preview it eventually publishes.  It is deliberately additive to the existing
Preview records: a completed analysis simply links the Preview the existing
service already produces and persists.

Safety: nothing in this module mutates Storage.  An analysis record is a
metadata-only observation; only ``OrganizerExecutor`` may ever change media.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

MAX_ANALYSIS_ID_LENGTH = 128
MAX_ANALYSIS_TEXT_LENGTH = 512

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class PreviewAnalysisKind(StrEnum):
    """Which existing exact-Preview authority one durable analysis produces."""

    DEFINITION = "definition"
    MANUAL = "manual"


class PreviewAnalysisStatus(StrEnum):
    """Durable lifecycle of one admitted exact analysis."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_ANALYSIS_STATUSES = frozenset(
    {
        PreviewAnalysisStatus.COMPLETED,
        PreviewAnalysisStatus.FAILED,
        PreviewAnalysisStatus.CANCELLED,
    }
)

CLAIMABLE_ANALYSIS_STATUSES = frozenset(
    {
        PreviewAnalysisStatus.QUEUED,
        PreviewAnalysisStatus.RUNNING,
    }
)


class PreviewAnalysisError(ValueError):
    """A bounded, operator-correctable exact-analysis error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "preview_analysis_rejected",
        status: int = 409,
        next_action: str = "reload the exact context and request a fresh analysis",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.next_action = next_action
        self.details = dict(details or {})


class PreviewAnalysisConflict(PreviewAnalysisError):
    """A fenced analysis publication lost its version or claim CAS."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="preview_analysis_conflict",
            status=409,
            next_action="reload the durable analysis state and decide again",
            details=details,
        )


class PreviewAnalysisUnavailable(PreviewAnalysisError):
    """The durable analysis store or a required read-only dependency is unavailable."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="preview_analysis_unavailable",
            status=503,
            next_action=(
                "restore the durable analysis store and the pinned Active runtime, then retry"
            ),
            details=details,
        )


class PreviewAnalysisOwnershipLost(PreviewAnalysisError):
    """A Worker tried to publish a step it no longer owns."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="preview_analysis_ownership_lost",
            status=409,
            next_action="wait for the current owner to settle, then reload the analysis",
            details=details,
        )


@dataclass(frozen=True)
class PreviewAnalysisProgress:
    """Bounded, secret-free progress of one admitted analysis."""

    phase: str
    message: str
    visited_entries: int = 0
    analysed_items: int = 0
    total_items: int = 0

    def __post_init__(self) -> None:
        for label, value, maximum in (
            ("phase", self.phase, 64),
            ("message", self.message, MAX_ANALYSIS_TEXT_LENGTH),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > maximum
                or "\x00" in value
            ):
                raise ValueError(f"preview analysis {label} is invalid")
        for label, value in (
            ("visited entries", self.visited_entries),
            ("analysed items", self.analysed_items),
            ("total items", self.total_items),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"preview analysis {label} must be a non-negative integer")

    def document(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "message": self.message,
            "visitedEntries": self.visited_entries,
            "analysedItems": self.analysed_items,
            "totalItems": self.total_items,
        }

    @classmethod
    def from_document(cls, value: object) -> PreviewAnalysisProgress:
        if not isinstance(value, dict):
            raise ValueError("preview analysis progress must be an object")
        try:
            return cls(
                str(value["phase"]),
                str(value["message"]),
                int(value.get("visitedEntries", 0)),
                int(value.get("analysedItems", 0)),
                int(value.get("totalItems", 0)),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("preview analysis progress document is invalid") from error


@dataclass(frozen=True)
class PreviewAnalysis:
    """One durable admitted exact analysis of a pinned Preview context.

    The record is deliberately *identity only*: it names the exact published
    definition or manual intent and the immutable configuration pin the
    analysis must run under, and it links the Preview the existing exact-Preview
    service eventually publishes.  It never carries execution authority, and a
    cancelled or failed analysis leaves no Preview behind.
    """

    analysis_id: str
    kind: PreviewAnalysisKind
    actor: str
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    status: PreviewAnalysisStatus
    version: int
    progress: PreviewAnalysisProgress
    created_at: datetime
    updated_at: datetime
    definition_id: str | None = None
    definition_fingerprint: str | None = None
    intent_id: str | None = None
    intent_version: int | None = None
    preview_id: str | None = None
    error: str | None = None
    cancel_requested: bool = False
    pause_requested: bool = False
    claim_worker_id: str | None = None
    claim_token: str | None = None
    claim_expires_at: datetime | None = None
    attempts: int = 0
    admission_request_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.analysis_id, str) or not _SAFE_ID.fullmatch(self.analysis_id):
            raise ValueError("preview analysis ID is invalid")
        if not isinstance(self.kind, PreviewAnalysisKind):
            raise ValueError("preview analysis kind is invalid")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("preview analysis actor is invalid")
        for label, value in (
            ("configuration snapshot", self.configuration_snapshot_id),
            ("configuration digest", self.configuration_snapshot_digest),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"preview analysis {label} identity is required")
        if not isinstance(self.status, PreviewAnalysisStatus):
            raise ValueError("preview analysis status is invalid")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("preview analysis version must be a positive integer")
        if not isinstance(self.progress, PreviewAnalysisProgress):
            raise ValueError("preview analysis progress is invalid")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("preview analysis timestamps must include timezone")
        if self.claim_expires_at is not None and self.claim_expires_at.tzinfo is None:
            raise ValueError("preview analysis claim deadline must include timezone")
        if self.kind is PreviewAnalysisKind.DEFINITION:
            if not isinstance(self.definition_id, str) or not self.definition_id.strip():
                raise ValueError("definition analysis requires a definition identity")
            if self.definition_fingerprint is not None and not _SHA256.fullmatch(
                self.definition_fingerprint
            ):
                raise ValueError("definition analysis fingerprint is invalid")
        else:
            if not isinstance(self.intent_id, str) or not self.intent_id.strip():
                raise ValueError("manual analysis requires an intent identity")
            if self.intent_version is not None and (
                isinstance(self.intent_version, bool)
                or not isinstance(self.intent_version, int)
                or self.intent_version < 1
            ):
                raise ValueError("manual analysis intent version is invalid")
        if self.admission_request_id is not None and (
            not isinstance(self.admission_request_id, str)
            or not _SAFE_ID.fullmatch(self.admission_request_id)
        ):
            raise ValueError("preview analysis admission request identity is invalid")
        if self.error is not None and (
            not isinstance(self.error, str)
            or not self.error.strip()
            or len(self.error) > MAX_ANALYSIS_TEXT_LENGTH
        ):
            raise ValueError("preview analysis error is invalid")
        if self.attempts < 0:
            raise ValueError("preview analysis attempts must be non-negative")

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_ANALYSIS_STATUSES

    @property
    def claimable(self) -> bool:
        return self.status in CLAIMABLE_ANALYSIS_STATUSES

    def document(self) -> dict[str, object]:
        return {
            "analysisId": self.analysis_id,
            "kind": self.kind.value,
            "actor": self.actor,
            "configurationSnapshotId": self.configuration_snapshot_id,
            "configurationSnapshotDigest": self.configuration_snapshot_digest,
            "status": self.status.value,
            "version": self.version,
            "progress": self.progress.document(),
            "definitionId": self.definition_id,
            "definitionFingerprint": self.definition_fingerprint,
            "intentId": self.intent_id,
            "intentVersion": self.intent_version,
            "previewId": self.preview_id,
            "error": self.error,
            "cancelRequested": self.cancel_requested,
            "pauseRequested": self.pause_requested,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "admissionRequestId": self.admission_request_id,
            "zeroMutation": True,
            "sideEffects": "none",
        }


__all__ = [
    "CLAIMABLE_ANALYSIS_STATUSES",
    "MAX_ANALYSIS_ID_LENGTH",
    "MAX_ANALYSIS_TEXT_LENGTH",
    "PreviewAnalysis",
    "PreviewAnalysisConflict",
    "PreviewAnalysisError",
    "PreviewAnalysisKind",
    "PreviewAnalysisOwnershipLost",
    "PreviewAnalysisProgress",
    "PreviewAnalysisStatus",
    "PreviewAnalysisUnavailable",
    "TERMINAL_ANALYSIS_STATUSES",
]
