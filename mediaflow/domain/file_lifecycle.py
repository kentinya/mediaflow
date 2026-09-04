"""Provider-neutral source lifecycle vocabulary.

The FileIndex location is deliberately stable while a source occurrence changes when the
bounded Storage observation changes.  This module contains only value objects and mapping
helpers; it never reads or mutates Storage.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class OccurrenceState(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    LEGACY = "legacy"


class ProcessingDisposition(StrEnum):
    UNKNOWN = "unknown"
    ORGANIZED = "organized"
    SKIPPED = "skipped"
    ATTENTION = "attention"
    CONFLICT = "conflict"
    REVIEW = "review"
    PARTIAL = "partial"
    FAILED = "failed"
    UNVERIFIED = "unverified"
    REPROCESS_REQUESTED = "reprocess_requested"


@dataclass(frozen=True)
class SourceFingerprint:
    """A bounded, secret-free fingerprint obtained from a Storage listing entry."""

    algorithm: str
    value: str | None
    evidence: dict[str, Any]
    state: OccurrenceState

    def document(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "value": self.value,
            "evidence": dict(self.evidence),
            "state": self.state.value,
        }


@dataclass(frozen=True)
class FileIndexOccurrence:
    occurrence_id: str
    file_id: str
    storage_id: str
    resource_library_id: str
    path: str
    fingerprint: str | None
    fingerprint_algorithm: str | None
    fingerprint_evidence: dict[str, Any]
    state: OccurrenceState
    first_seen_at: datetime
    last_seen_at: datetime
    is_current: bool
    superseded_at: datetime | None
    processing_disposition: ProcessingDisposition
    processing_result_id: str | None
    processing_effect_certainty: str
    processing_retry_safety: str
    processing_next_action: str
    processing_updated_at: datetime | None

    def document(self) -> dict[str, Any]:
        return {
            "occurrenceId": self.occurrence_id,
            "fileId": self.file_id,
            "storageId": self.storage_id,
            "resourceLibraryId": self.resource_library_id,
            "path": self.path,
            "fingerprint": self.fingerprint,
            "fingerprintAlgorithm": self.fingerprint_algorithm,
            "fingerprintEvidence": dict(self.fingerprint_evidence),
            "state": self.state.value,
            "firstSeenAt": self.first_seen_at.isoformat(),
            "lastSeenAt": self.last_seen_at.isoformat(),
            "current": self.is_current,
            "supersededAt": self.superseded_at.isoformat() if self.superseded_at else None,
            "processingDisposition": self.processing_disposition.value,
            "processingResultId": self.processing_result_id,
            "processingEffectCertainty": self.processing_effect_certainty,
            "processingRetrySafety": self.processing_retry_safety,
            "processingNextAction": self.processing_next_action,
            "processingUpdatedAt": (
                self.processing_updated_at.isoformat() if self.processing_updated_at else None
            ),
        }


@dataclass(frozen=True)
class ReprocessRequest:
    request_id: str
    file_id: str
    occurrence_id: str
    fingerprint: str
    actor: str
    requested_at: datetime
    status: str
    next_action: str
    error: str | None = None

    def document(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "fileId": self.file_id,
            "occurrenceId": self.occurrence_id,
            "fingerprint": self.fingerprint,
            "actor": self.actor,
            "requestedAt": self.requested_at.isoformat(),
            "status": self.status,
            "nextAction": self.next_action,
            "error": self.error,
            "sideEffects": "none",
        }


class FileIndexLifecycleError(ValueError):
    """Bounded, fail-closed lifecycle admission error for API and Web callers."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 409,
        durable_state: str = "unchanged",
        retry_safe: bool = True,
        next_action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.durable_state = durable_state
        self.retry_safe = retry_safe
        self.next_action = next_action
        self.details = dict(details or {})


def source_fingerprint(storage_id: str, resource_library_id: str, entry) -> SourceFingerprint:
    """Build deterministic evidence from a bounded Storage stat/list entry.

    Scanner code intentionally does not call ``read``.  Some Storage providers expose a
    stable opaque validator (ETag, checksum, version, or generation); those values are
    included in the hash but never emitted as evidence.  Unknown provider attributes are
    ignored so a provider cannot smuggle arbitrary or secret data into the lifecycle record.
    """

    evidence: dict[str, Any] = {"source": "storage_entry", "providerValidators": []}
    canonical: dict[str, Any] = {
        "storageId": storage_id,
        "resourceLibraryId": resource_library_id,
        "path": getattr(entry, "path", None),
        "filename": getattr(entry, "name", None),
        "size": getattr(entry, "size", None),
        "modifiedAt": _datetime_value(getattr(entry, "modified_at", None)),
    }
    valid = (
        isinstance(storage_id, str)
        and bool(storage_id)
        and isinstance(resource_library_id, str)
        and bool(resource_library_id)
        and isinstance(canonical["path"], str)
        and bool(canonical["path"])
        and isinstance(canonical["filename"], str)
        and isinstance(canonical["size"], int)
        and not isinstance(canonical["size"], bool)
        and canonical["size"] >= 0
        and canonical["modifiedAt"] is not None
    )
    validators: dict[str, str | int] = {}
    for name in (
        "fingerprint",
        "validator",
        "etag",
        "checksum",
        "content_hash",
        "version_id",
        "generation",
    ):
        value = getattr(entry, name, None)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
            text = str(value)
            if len(text) <= 256:
                validators[name] = value
                evidence["providerValidators"].append(name)
    canonical["providerValidators"] = validators
    if not valid:
        return SourceFingerprint(
            "storage-entry-sha256",
            None,
            {
                "source": "storage_entry",
                "providerValidators": tuple(evidence["providerValidators"]),
            },
            OccurrenceState.UNVERIFIED,
        )
    digest = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    evidence.update(
        {
            "size": canonical["size"],
            "modifiedAt": canonical["modifiedAt"],
            "bounded": True,
        }
    )
    return SourceFingerprint("storage-entry-sha256", digest, evidence, OccurrenceState.VERIFIED)


def occurrence_id_for(
    storage_id: str, resource_library_id: str, path: str, fingerprint: str | None
) -> str:
    value = json.dumps(
        {
            "storageId": storage_id,
            "resourceLibraryId": resource_library_id,
            "path": path,
            "fingerprint": fingerprint,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "occ-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:40]


def disposition_for_result(result) -> ProcessingDisposition:
    """Map a durable Result outcome without using scan/discovery state."""

    status = str(getattr(result, "status", "")).lower()
    operation = str(getattr(result, "operation", "")).lower()
    if operation in {"skip", "noop"} and status in {"success", "completed", "organized"}:
        return ProcessingDisposition.SKIPPED
    if status in {"success", "completed", "organized"}:
        return ProcessingDisposition.ORGANIZED
    if status == "skipped":
        return ProcessingDisposition.SKIPPED
    if status in {"partial", "partial_success"}:
        return ProcessingDisposition.PARTIAL
    if status in {"failed", "cancelled"}:
        return ProcessingDisposition.FAILED
    if status in {"attention"}:
        return ProcessingDisposition.ATTENTION
    if status in {"waiting_confirm", "conflict"}:
        return ProcessingDisposition.CONFLICT
    if status in {
        "waiting_recognition",
        "waiting_metadata",
        "waiting_metadata_correction",
        "waiting_classification",
        "review",
        "need_confirm",
    }:
        return ProcessingDisposition.REVIEW
    if status in {"dry_run", "preview", "pending", "processing"}:
        return ProcessingDisposition.UNKNOWN
    effect_certainty = str(getattr(result, "effect_certainty", "unknown")).lower()
    if effect_certainty in {"unknown", "attempted_unverified"}:
        return ProcessingDisposition.UNVERIFIED
    return ProcessingDisposition.UNKNOWN


def retry_safety_for_effect_certainty(certainty: object) -> str:
    normalized = str(getattr(certainty, "value", certainty) or "unknown").lower()
    if normalized in {"unknown", "attempted_unverified"}:
        return "unsafe"
    if normalized in {"none", "verified_complete"}:
        return "safe"
    return "unknown"


def next_action_for_disposition(disposition: ProcessingDisposition) -> str:
    return {
        ProcessingDisposition.UNKNOWN: (
            "observe a verified current occurrence, then run explicit analysis"
        ),
        ProcessingDisposition.ORGANIZED: (
            "inspect the linked Result; request explicit Reprocess only if "
            "duplicate work is intended"
        ),
        ProcessingDisposition.SKIPPED: (
            "review the skip reason; request explicit Reprocess only if processing is intended"
        ),
        ProcessingDisposition.ATTENTION: (
            "inspect the bounded blocker and resolve it before another analysis request"
        ),
        ProcessingDisposition.CONFLICT: (
            "resolve the conflict/review, then request a fresh bounded analysis"
        ),
        ProcessingDisposition.REVIEW: (
            "resolve the linked review, then request a fresh bounded analysis"
        ),
        ProcessingDisposition.PARTIAL: (
            "inspect the checkpoint and recorded effects before retrying or Reprocessing"
        ),
        ProcessingDisposition.FAILED: (
            "repair the reported failure, then explicitly retry or Reprocess"
        ),
        ProcessingDisposition.UNVERIFIED: (
            "refresh the current source occurrence before processing"
        ),
        ProcessingDisposition.REPROCESS_REQUESTED: (
            "run the later explicit Scan or Preview admission for this occurrence"
        ),
    }[disposition]


def _datetime_value(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
