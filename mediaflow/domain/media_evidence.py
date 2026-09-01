"""Provider-neutral immutable evidence captured at TaskItem pipeline boundaries.

The evidence contract intentionally stores normalized, bounded facts only.  It never
stores raw Provider DTOs, credentials, headers, cookies, private configuration,
unbounded exception text, or Storage/Provider handles.  Legacy rows that predate
evidence capture are represented by ``available=False`` sections rather than by
reconstructing facts from status strings, filenames, or current configuration.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mediaflow.domain.manual_safety import redact_evidence_value

EVIDENCE_SECTION_NAMES = (
    "parse",
    "recognition",
    "metadata",
    "policies",
    "naming",
    "classification",
    "plan",
    "operation",
    "capabilities",
)


@dataclass(frozen=True)
class EvidenceSection:
    """One bounded, deterministic detail section."""

    available: bool
    value: dict[str, Any] | None = None
    items: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    truncated: bool = False
    unavailable_reason: str | None = None

    def document(self) -> dict[str, Any]:
        document = {
            "available": self.available,
            "value": self.value,
            "items": [dict(item) for item in self.items],
            "warnings": list(self.warnings),
            "truncated": self.truncated,
            "unavailableReason": self.unavailable_reason,
        }
        return redact_evidence_value(document)  # type: ignore[return-value]


def unavailable_section(reason: str = "legacy evidence was not captured") -> EvidenceSection:
    return EvidenceSection(False, unavailable_reason=reason)


@dataclass(frozen=True)
class PipelineEvidence:
    """Immutable captured evidence for one TaskItem attempt."""

    evidence_id: str
    task_id: str
    item_id: str
    attempts: int
    source_storage_id: str
    source_path: str
    captured_at: datetime
    configuration_snapshot_id: str | None
    configuration_snapshot_digest: str | None
    outcome: str
    sections: Mapping[str, EvidenceSection]
    warnings: tuple[str, ...] = ()
    error: str | None = None
    truncated: bool = False

    def section(self, name: str) -> EvidenceSection:
        return self.sections.get(name, unavailable_section())

    def document(self) -> dict[str, Any]:
        document = {
            "evidenceId": self.evidence_id,
            "taskId": self.task_id,
            "itemId": self.item_id,
            "attempts": self.attempts,
            "sourceStorageId": self.source_storage_id,
            "sourcePath": self.source_path,
            "capturedAt": self.captured_at.isoformat(),
            "configurationSnapshotId": self.configuration_snapshot_id,
            "configurationSnapshotDigest": self.configuration_snapshot_digest,
            "outcome": self.outcome,
            "sections": {name: self.section(name).document() for name in EVIDENCE_SECTION_NAMES},
            "warnings": list(self.warnings),
            "error": self.error,
            "truncated": self.truncated,
        }
        return redact_evidence_value(document)  # type: ignore[return-value]


def evidence_from_document(
    document: Mapping[str, Any],
) -> PipelineEvidence:
    """Rebuild an immutable evidence record from its bounded JSON document."""

    from datetime import datetime

    document = redact_evidence_value(document)  # type: ignore[assignment]

    sections = {
        name: EvidenceSection(
            bool(raw.get("available")),
            dict(raw["value"]) if raw.get("value") is not None else None,
            tuple(dict(item) for item in raw.get("items", ())),
            tuple(str(item) for item in raw.get("warnings", ())),
            bool(raw.get("truncated")),
            raw.get("unavailableReason"),
        )
        for name, raw in document.get("sections", {}).items()
        if isinstance(raw, Mapping)
    }
    return PipelineEvidence(
        evidence_id=str(document["evidenceId"]),
        task_id=str(document["taskId"]),
        item_id=str(document["itemId"]),
        attempts=int(document.get("attempts", 0)),
        source_storage_id=str(document["sourceStorageId"]),
        source_path=str(document["sourcePath"]),
        captured_at=datetime.fromisoformat(str(document["capturedAt"])),
        configuration_snapshot_id=document.get("configurationSnapshotId"),
        configuration_snapshot_digest=document.get("configurationSnapshotDigest"),
        outcome=str(document["outcome"]),
        sections=sections,
        warnings=tuple(str(item) for item in document.get("warnings", ())),
        error=document.get("error"),
        truncated=bool(document.get("truncated")),
    )


def redact_pipeline_evidence(evidence: PipelineEvidence) -> PipelineEvidence:
    """Return a shape-preserving, secret-free copy of pipeline evidence."""

    return evidence_from_document(evidence.document())
