"""Durable bounded discovery of ResourceLibrary folder/mixed selections.

This module owns the *domain* shape of the Slice 44 RO-6 discovery stage: the
exact admitted scope, the concrete budgets, the durable counters, the bounded
findings and the frozen source list.  It is deliberately additive to the
existing manual-organize domain: discovery produces an ordinary
``ManualSourceIdentity`` list that the existing intent/Preview/execution
boundary consumes unchanged.

Safety: nothing in this module mutates Storage.  A discovery record is a
metadata-only observation; only ``OrganizerExecutor`` may ever change media.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

MAX_DISCOVERY_ID_LENGTH = 128
MAX_DISCOVERY_TEXT_LENGTH = 512
MAX_DISCOVERY_SCOPE_PATHS = 100
MAX_DISCOVERY_PRIMARY_SOURCES = 100
MAX_DISCOVERY_VISITED_ENTRIES = 10_000
MAX_DISCOVERY_VISITED_DIRECTORIES = 1_000
MAX_DISCOVERY_PAGE_FETCHES = 2_000
MAX_DISCOVERY_PAGE_LIMIT = 100
MAX_DISCOVERY_DEPTH = 32
MAX_DISCOVERY_ACTIVE_SECONDS = 600.0
MAX_DISCOVERY_PATH_BYTES = 4096
MAX_DISCOVERY_SEGMENTS = 128
MAX_DISCOVERY_ENTRY_NAME_BYTES = 1024
MAX_DISCOVERY_CURSOR_BYTES = 2048
MAX_DISCOVERY_FINDINGS = 100
MAX_DISCOVERY_REASONS = 32
MAX_DISCOVERY_OBSERVATIONS = 100
MAX_DISCOVERY_REFUSALS = 16

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")


class DiscoveryStatus(StrEnum):
    """Durable lifecycle of one admitted discovery."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_STABILITY = "waiting_stability"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_DISCOVERY_STATUSES = frozenset(
    {
        DiscoveryStatus.COMPLETED,
        DiscoveryStatus.PARTIAL_SUCCESS,
        DiscoveryStatus.FAILED,
        DiscoveryStatus.CANCELLED,
    }
)

CLAIMABLE_DISCOVERY_STATUSES = frozenset(
    {
        DiscoveryStatus.QUEUED,
        DiscoveryStatus.RUNNING,
        # A completed walk that observed not-yet-proven stability stays
        # claimable so a later observation can prove the interval.
        DiscoveryStatus.WAITING_STABILITY,
    }
)

#: Lifecycle statuses a *settlement* writes rather than a bounded traversal.
#: ``_publish_paused``, ``_cancel`` and ``_fail`` settle one boundary and release
#: the claim; they never describe the outcome of a walk.  A fenced projection
#: that carries one of them therefore describes a control the operator may
#: already have superseded, so its lifecycle must never be replayed as the
#: traversal outcome: the latest accepted control decides the lifecycle, and a
#: cleared pause is not a completed traversal.
SETTLEMENT_DISCOVERY_STATUSES = frozenset(
    {
        DiscoveryStatus.PAUSED,
        DiscoveryStatus.CANCELLED,
        DiscoveryStatus.FAILED,
    }
)


def is_settlement_status(status: object) -> bool:
    """Whether one discovery status is a settled control rather than a walk."""

    return status in SETTLEMENT_DISCOVERY_STATUSES


class DiscoveryEntryKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"


class DiscoveryFindingKind(StrEnum):
    PRIMARY = "primary"
    EXCLUDED = "excluded"
    UNSTABLE = "unstable"
    ERROR = "error"
    TRUNCATED = "truncated"


class DiscoveryIncompleteReason(StrEnum):
    """Why a discovery is not a complete walk of its admitted scope."""

    NONE = "none"
    PRIMARY_LIMIT = "primary_limit"
    ENTRY_LIMIT = "entry_limit"
    DIRECTORY_LIMIT = "directory_limit"
    PAGE_LIMIT = "page_limit"
    DEPTH_LIMIT = "depth_limit"
    TIME_LIMIT = "time_limit"
    READ_FAILURE = "read_failure"
    CANCELLED = "cancelled"
    CURSOR_REPEATED = "cursor_repeated"
    CURSOR_INVALID = "cursor_invalid"
    UNSAFE_ENTRY = "unsafe_entry"
    SAFETY_DEPTH_LIMIT = "safety_depth_limit"


#: The incomplete reasons that mean a durable budget or safety bound was
#: exhausted, so the recorded sources are a truncated prefix of the admitted
#: scope rather than a complete walk.  A discovery stopped by one of these
#: can never be finalized into an executable source list: the operator must
#: narrow the scope and start a new bounded discovery.  An ordinary read
#: failure is deliberately absent from this set: a partially read scope whose
#: known findings are explicitly reviewed remains a legal, separately
#: confirmed subset.
BUDGET_LIMITED_REASONS = frozenset(
    {
        DiscoveryIncompleteReason.PRIMARY_LIMIT,
        DiscoveryIncompleteReason.ENTRY_LIMIT,
        DiscoveryIncompleteReason.DIRECTORY_LIMIT,
        DiscoveryIncompleteReason.PAGE_LIMIT,
        DiscoveryIncompleteReason.DEPTH_LIMIT,
        DiscoveryIncompleteReason.SAFETY_DEPTH_LIMIT,
        DiscoveryIncompleteReason.TIME_LIMIT,
        DiscoveryIncompleteReason.CURSOR_REPEATED,
        DiscoveryIncompleteReason.CURSOR_INVALID,
        DiscoveryIncompleteReason.UNSAFE_ENTRY,
    }
)


def discovery_budget_limited(reason: DiscoveryIncompleteReason | str) -> bool:
    """Whether one incomplete reason marks a budget/safety-exhausted walk."""

    value = reason.value if isinstance(reason, DiscoveryIncompleteReason) else reason
    return value in {item.value for item in BUDGET_LIMITED_REASONS}


def discovery_material_refusal(progress: DiscoveryProgress) -> DiscoveryIncompleteReason | None:
    """The durable, monotonic material refusal of one discovery, if any.

    A material refusal (budget, safety depth, cyclic cursor or an unsafe
    provider entry) can never be erased by a later ordinary read failure, a
    later pass or a restart: it is recorded separately from the *current*
    ``incomplete_reason`` and is the single authority that disables Finalize.
    The earliest recorded material fact wins so the explanation stays stable.
    """

    for reason in progress.refusal_reasons:
        if discovery_budget_limited(reason):
            return reason
    if discovery_budget_limited(progress.incomplete_reason):
        # A record written before the durable refusal list existed still keeps
        # its own material final reason as an equivalent refusal.
        return progress.incomplete_reason
    return None


def discovery_scope_signature(entries: tuple[DiscoveryScopeEntry, ...]) -> str:
    """The canonical, order-stable signature of one deduplicated scope.

    Admission reconciliation compares this exact signature, so an identical
    actor/scope/pin resubmission can be matched to its already durable open
    record without ever guessing from labels or creation times.
    """

    return json.dumps(
        [entry.document() for entry in entries],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def deduplicate_sources(
    sources: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], ...]:
    """One exact source per admitted Storage/ResourceLibrary/source path.

    A repeated provider page, a repeated observation pass or a resumed Worker
    must never enlarge the frozen manifest with the same ordinary source twice.
    The first durable observation wins; its identity and stability evidence are
    preserved unchanged.
    """

    seen: set[tuple[object, object, object]] = set()
    kept: list[dict[str, object]] = []
    for source in sources:
        key = (
            source.get("storageId"),
            source.get("resourceLibraryId"),
            source.get("path"),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(source)
    return tuple(kept)


class DiscoveryError(ValueError):
    """A bounded, operator-correctable discovery error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_discovery",
        next_action: str = "correct the selected scope and start a bounded discovery again",
        status: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action
        self.status = status
        self.details = dict(details or {})


class DiscoveryConflict(DiscoveryError):
    """A fenced discovery publication lost its version CAS.

    ``attempted`` carries the exact bounded projection the live owner tried to
    publish, and ``attempted_observations`` the stability observations that were
    part of the same atomic write, when the raiser has them.  A same-owner
    operator control reconciles that work with the fresh record instead of
    discarding it; a lost claim ignores it entirely.  Neither is part of
    ``details``: the operator projection must never publish a claim token, a
    fingerprint or a physical Storage path.
    """

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, object] | None = None,
        attempted: object | None = None,
        attempted_observations: tuple = (),
    ) -> None:
        super().__init__(
            message,
            code="discovery_conflict",
            status=409,
            next_action="reload the discovery and retry the same deliberate action",
            details=details,
        )
        self.attempted = attempted
        self.attempted_observations = attempted_observations


class DiscoveryUnavailable(DiscoveryError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="discovery_unavailable",
            status=503,
            next_action="restore the pinned Active runtime and Processing Worker, then retry",
            details=details,
        )


class DiscoveryOwnershipLost(DiscoveryError):
    """A Worker tried to publish a step it no longer owns.

    This is deliberately *not* a ``DiscoveryConflict``: a version conflict is
    an operator control change the current owner may still settle, while a lost
    claim means another Worker owns the walk now.  The only correct reaction is
    to stop without writing, so the successor's claim, state, controls, manifest,
    counters and observations stay exactly as the successor published them.
    """

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="discovery_ownership_lost",
            status=409,
            next_action=(
                "refresh the discovery; another Processing Worker owns this walk and "
                "continues it under its own claim"
            ),
            details=details,
        )


@dataclass(frozen=True)
class DiscoveryScopeEntry:
    """One submitted ResourceLibrary-relative selection with its real entry type."""

    path: str
    kind: DiscoveryEntryKind

    def document(self) -> dict[str, object]:
        return {"path": self.path, "kind": self.kind.value}

    @classmethod
    def from_document(cls, value: object) -> DiscoveryScopeEntry:
        if not isinstance(value, dict):
            raise ValueError("discovery scope entry is invalid")
        path = value.get("path")
        kind = value.get("kind")
        if not isinstance(path, str) or not isinstance(kind, str):
            raise ValueError("discovery scope entry is invalid")
        return cls(path, DiscoveryEntryKind(kind))


@dataclass(frozen=True)
class DiscoveryBudgets:
    """The exact, persisted budgets of one admitted discovery."""

    max_scope_paths: int = MAX_DISCOVERY_SCOPE_PATHS
    max_primary_sources: int = MAX_DISCOVERY_PRIMARY_SOURCES
    max_visited_entries: int = MAX_DISCOVERY_VISITED_ENTRIES
    max_visited_directories: int = MAX_DISCOVERY_VISITED_DIRECTORIES
    max_page_fetches: int = MAX_DISCOVERY_PAGE_FETCHES
    page_limit: int = MAX_DISCOVERY_PAGE_LIMIT
    max_depth: int = MAX_DISCOVERY_DEPTH
    max_active_seconds: float = MAX_DISCOVERY_ACTIVE_SECONDS
    max_path_bytes: int = MAX_DISCOVERY_PATH_BYTES
    max_segments: int = MAX_DISCOVERY_SEGMENTS
    max_entry_name_bytes: int = MAX_DISCOVERY_ENTRY_NAME_BYTES
    max_cursor_bytes: int = MAX_DISCOVERY_CURSOR_BYTES
    max_findings: int = MAX_DISCOVERY_FINDINGS

    def document(self) -> dict[str, object]:
        return {
            "maxScopePaths": self.max_scope_paths,
            "maxPrimarySources": self.max_primary_sources,
            "maxVisitedEntries": self.max_visited_entries,
            "maxVisitedDirectories": self.max_visited_directories,
            "maxPageFetches": self.max_page_fetches,
            "pageLimit": self.page_limit,
            "maxDepth": self.max_depth,
            "maxActiveSeconds": self.max_active_seconds,
            "maxPathBytes": self.max_path_bytes,
            "maxSegments": self.max_segments,
            "maxEntryNameBytes": self.max_entry_name_bytes,
            "maxCursorBytes": self.max_cursor_bytes,
            "maxFindings": self.max_findings,
        }

    @classmethod
    def from_document(cls, value: object) -> DiscoveryBudgets:
        if not isinstance(value, dict):
            raise ValueError("discovery budgets are invalid")
        defaults = cls()
        fields = {
            "max_scope_paths": ("maxScopePaths", defaults.max_scope_paths),
            "max_primary_sources": ("maxPrimarySources", defaults.max_primary_sources),
            "max_visited_entries": ("maxVisitedEntries", defaults.max_visited_entries),
            "max_visited_directories": (
                "maxVisitedDirectories",
                defaults.max_visited_directories,
            ),
            "max_page_fetches": ("maxPageFetches", defaults.max_page_fetches),
            "page_limit": ("pageLimit", defaults.page_limit),
            "max_depth": ("maxDepth", defaults.max_depth),
            "max_active_seconds": ("maxActiveSeconds", defaults.max_active_seconds),
            "max_path_bytes": ("maxPathBytes", defaults.max_path_bytes),
            "max_segments": ("maxSegments", defaults.max_segments),
            "max_entry_name_bytes": ("maxEntryNameBytes", defaults.max_entry_name_bytes),
            "max_cursor_bytes": ("maxCursorBytes", defaults.max_cursor_bytes),
            "max_findings": ("maxFindings", defaults.max_findings),
        }
        values: dict[str, object] = {}
        for name, (key, fallback) in fields.items():
            raw = value.get(key, fallback)
            if name == "max_active_seconds":
                values[name] = float(raw)
            else:
                values[name] = int(raw)
        return cls(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class DiscoveryCounters:
    """Durable work counters; never reset by pause/restart/continue."""

    visited_entries: int = 0
    visited_directories: int = 0
    page_fetches: int = 0
    primary_sources: int = 0
    excluded_entries: int = 0
    unstable_entries: int = 0
    error_entries: int = 0
    active_seconds: float = 0.0

    def document(self) -> dict[str, object]:
        return {
            "visitedEntries": self.visited_entries,
            "visitedDirectories": self.visited_directories,
            "pageFetches": self.page_fetches,
            "primarySources": self.primary_sources,
            "excludedEntries": self.excluded_entries,
            "unstableEntries": self.unstable_entries,
            "errorEntries": self.error_entries,
            "activeSeconds": self.active_seconds,
        }

    @classmethod
    def from_document(cls, value: object) -> DiscoveryCounters:
        if not isinstance(value, dict):
            raise ValueError("discovery counters are invalid")
        return cls(
            visited_entries=int(value.get("visitedEntries", 0)),
            visited_directories=int(value.get("visitedDirectories", 0)),
            page_fetches=int(value.get("pageFetches", 0)),
            primary_sources=int(value.get("primarySources", 0)),
            excluded_entries=int(value.get("excludedEntries", 0)),
            unstable_entries=int(value.get("unstableEntries", 0)),
            error_entries=int(value.get("errorEntries", 0)),
            active_seconds=float(value.get("activeSeconds", 0.0)),
        )


@dataclass(frozen=True)
class DiscoveryReasonCount:
    """One bounded explanation bucket with its bounded occurrence count."""

    reason: str
    count: int
    example_path: str | None = None

    def document(self) -> dict[str, object]:
        value: dict[str, object] = {"reason": self.reason, "count": self.count}
        if self.example_path is not None:
            value["examplePath"] = self.example_path
        return value

    @classmethod
    def from_document(cls, value: object) -> DiscoveryReasonCount:
        if not isinstance(value, dict):
            raise ValueError("discovery reason is invalid")
        reason = value.get("reason")
        if not isinstance(reason, str) or not reason or len(reason) > MAX_DISCOVERY_TEXT_LENGTH:
            raise ValueError("discovery reason is invalid")
        example = value.get("examplePath")
        return cls(
            reason,
            int(value.get("count", 0)),
            example if isinstance(example, str) else None,
        )


@dataclass(frozen=True)
class DiscoveryFinding:
    """One bounded, secret-free discovery finding for one visited source."""

    kind: DiscoveryFindingKind
    path: str
    reason: str
    size: int | None = None
    modified_at: datetime | None = None
    depth: int = 0

    def document(self) -> dict[str, object]:
        value: dict[str, object] = {
            "kind": self.kind.value,
            "path": self.path,
            "reason": self.reason,
            "depth": self.depth,
        }
        if self.size is not None:
            value["size"] = self.size
        if self.modified_at is not None:
            value["modifiedAt"] = self.modified_at.isoformat()
        return value

    @classmethod
    def from_document(cls, value: object) -> DiscoveryFinding:
        if not isinstance(value, dict):
            raise ValueError("discovery finding is invalid")
        path = value.get("path")
        reason = value.get("reason")
        if not isinstance(path, str) or not isinstance(reason, str):
            raise ValueError("discovery finding is invalid")
        modified = value.get("modifiedAt")
        return cls(
            DiscoveryFindingKind(str(value.get("kind"))),
            path,
            reason,
            int(value["size"]) if isinstance(value.get("size"), int) else None,
            datetime.fromisoformat(modified) if isinstance(modified, str) else None,
            int(value.get("depth", 0)),
        )


@dataclass(frozen=True)
class DiscoveryObservation:
    """One durable bounded observation of a real source in this context."""

    path: str
    size: int
    modified_at: datetime
    fingerprint: str | None
    observed_at: datetime
    stable_since: datetime | None = None

    def document(self) -> dict[str, object]:
        return {
            "path": self.path,
            "size": self.size,
            "modifiedAt": self.modified_at.isoformat(),
            "fingerprint": self.fingerprint,
            "observedAt": self.observed_at.isoformat(),
            "stableSince": self.stable_since.isoformat() if self.stable_since else None,
        }

    @classmethod
    def from_document(cls, value: object) -> DiscoveryObservation:
        if not isinstance(value, dict):
            raise ValueError("discovery observation is invalid")
        path = value.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("discovery observation is invalid")
        fingerprint = value.get("fingerprint")
        stable_since = value.get("stableSince")
        return cls(
            path,
            int(value.get("size", 0)),
            datetime.fromisoformat(str(value.get("modifiedAt"))),
            fingerprint if isinstance(fingerprint, str) else None,
            datetime.fromisoformat(str(value.get("observedAt"))),
            datetime.fromisoformat(str(stable_since)) if isinstance(stable_since, str) else None,
        )


@dataclass(frozen=True)
class DiscoveryProgress:
    """The exact bounded, durably resumable progress of one discovery."""

    phase: str
    scope_entries: tuple[DiscoveryScopeEntry, ...]
    counters: DiscoveryCounters
    incomplete_reason: DiscoveryIncompleteReason
    findings: tuple[DiscoveryFinding, ...] = ()
    reasons: tuple[DiscoveryReasonCount, ...] = ()
    pending_files: tuple[str, ...] = ()
    pending_directories: tuple[str, ...] = ()
    active_directory: str | None = None
    active_cursor: str | None = None
    active_cursors_seen: tuple[str, ...] = ()
    message: str = ""
    #: Durable, monotonic material refusals observed anywhere in this walk.
    #: Unlike ``incomplete_reason`` (the *current* dominant fact) this list is
    #: never erased by a later ordinary read failure or a later pass, so a
    #: truncated prefix can never be presented as a complete, freezable scope.
    refusal_reasons: tuple[DiscoveryIncompleteReason, ...] = ()

    def document(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "scopeEntries": [item.document() for item in self.scope_entries],
            "counters": self.counters.document(),
            "incompleteReason": self.incomplete_reason.value,
            "refusalReasons": [item.value for item in self.refusal_reasons],
            "findings": [item.document() for item in self.findings],
            "reasons": [item.document() for item in self.reasons],
            "pendingFiles": list(self.pending_files),
            "pendingDirectories": list(self.pending_directories),
            "activeDirectory": self.active_directory,
            "activeCursor": self.active_cursor,
            "activeCursorsSeen": list(self.active_cursors_seen),
            "message": self.message,
        }

    @classmethod
    def from_document(cls, value: object) -> DiscoveryProgress:
        if not isinstance(value, dict):
            raise ValueError("discovery progress is invalid")
        scope = value.get("scopeEntries", [])
        findings = value.get("findings", [])
        reasons = value.get("reasons", [])
        pending_files = value.get("pendingFiles", [])
        pending = value.get("pendingDirectories", [])
        seen = value.get("activeCursorsSeen", [])
        refusals = value.get("refusalReasons", [])
        for raw in (scope, findings, reasons, pending_files, pending, seen, refusals):
            if not isinstance(raw, list):
                raise ValueError("discovery progress is invalid")
        active_directory = value.get("activeDirectory")
        active_cursor = value.get("activeCursor")
        if active_directory is not None and not isinstance(active_directory, str):
            raise ValueError("discovery progress is invalid")
        if active_cursor is not None and not isinstance(active_cursor, str):
            raise ValueError("discovery progress is invalid")
        return cls(
            str(value.get("phase", "queued")),
            tuple(DiscoveryScopeEntry.from_document(item) for item in scope),
            DiscoveryCounters.from_document(value.get("counters", {})),
            DiscoveryIncompleteReason(str(value.get("incompleteReason", "none"))),
            tuple(DiscoveryFinding.from_document(item) for item in findings),
            tuple(DiscoveryReasonCount.from_document(item) for item in reasons),
            tuple(str(item) for item in pending_files),
            tuple(str(item) for item in pending),
            active_directory,
            active_cursor,
            tuple(str(item) for item in seen),
            str(value.get("message", ""))[:MAX_DISCOVERY_TEXT_LENGTH],
            tuple(DiscoveryIncompleteReason(str(item)) for item in refusals),
        )


@dataclass(frozen=True)
class MediaDiscovery:
    """One durable bounded discovery of an exact admitted ResourceLibrary scope."""

    discovery_id: str
    actor: str
    resource_library_id: str
    storage_id: str
    snapshot_id: str
    snapshot_digest: str
    status: DiscoveryStatus
    version: int
    budgets: DiscoveryBudgets
    progress: DiscoveryProgress
    created_at: datetime
    updated_at: datetime
    sources: tuple[dict[str, object], ...] = ()
    intent_id: str | None = None
    frozen_at: datetime | None = None
    claim_worker_id: str | None = None
    claim_token: str | None = None
    claim_expires_at: datetime | None = None
    attempts: int = 0
    pause_requested: bool = False
    cancel_requested: bool = False
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.discovery_id, str) or not _SAFE_ID.fullmatch(self.discovery_id):
            raise ValueError("discovery ID is invalid")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("discovery actor is invalid")
        for name, value in (
            ("ResourceLibrary", self.resource_library_id),
            ("Storage", self.storage_id),
            ("configuration snapshot", self.snapshot_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"discovery {name} identity is required")
        if not isinstance(self.snapshot_digest, str) or not self.snapshot_digest.strip():
            raise ValueError("discovery configuration digest is required")
        if not isinstance(self.status, DiscoveryStatus):
            raise ValueError("discovery status is invalid")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("discovery timestamps must include timezone")
        if len(self.sources) > self.budgets.max_primary_sources:
            raise ValueError("discovery source list exceeds its admitted bound")

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_DISCOVERY_STATUSES

    @property
    def frozen(self) -> bool:
        return self.frozen_at is not None and bool(self.sources)

    def document(self, *, include_sources: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "discoveryId": self.discovery_id,
            "actor": self.actor,
            "resourceLibraryId": self.resource_library_id,
            "storageId": self.storage_id,
            "status": self.status.value,
            "version": self.version,
            "budgets": self.budgets.document(),
            "progress": self.progress.document(),
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "intentId": self.intent_id,
            "frozenAt": self.frozen_at.isoformat() if self.frozen_at is not None else None,
            "attempts": self.attempts,
            "pauseRequested": self.pause_requested,
            "cancelRequested": self.cancel_requested,
            "error": self.error,
            "primarySourceCount": len(self.sources),
            "sideEffects": "none",
        }
        if include_sources:
            value["sources"] = [dict(item) for item in self.sources]
        return value

    def to_json(self) -> str:
        return json.dumps(self.document(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_document(cls, value: object) -> MediaDiscovery:
        if not isinstance(value, dict):
            raise ValueError("discovery document is invalid")
        budgets = DiscoveryBudgets.from_document(value.get("budgets", {}))
        sources = value.get("sources", [])
        if not isinstance(sources, list):
            raise ValueError("discovery sources are invalid")
        frozen = value.get("frozenAt")
        expires = value.get("claimExpiresAt")
        return cls(
            str(value.get("discoveryId")),
            str(value.get("actor")),
            str(value.get("resourceLibraryId")),
            str(value.get("storageId")),
            str(value.get("snapshotId")),
            str(value.get("snapshotDigest")),
            DiscoveryStatus(str(value.get("status"))),
            int(value.get("version", 1)),
            budgets,
            DiscoveryProgress.from_document(value.get("progress", {})),
            datetime.fromisoformat(str(value.get("createdAt"))),
            datetime.fromisoformat(str(value.get("updatedAt"))),
            tuple(dict(item) for item in sources if isinstance(item, dict)),
            str(value["intentId"]) if isinstance(value.get("intentId"), str) else None,
            datetime.fromisoformat(str(frozen)) if isinstance(frozen, str) else None,
            str(value["claimWorkerId"]) if isinstance(value.get("claimWorkerId"), str) else None,
            str(value["claimToken"]) if isinstance(value.get("claimToken"), str) else None,
            datetime.fromisoformat(str(expires)) if isinstance(expires, str) else None,
            int(value.get("attempts", 0)),
            bool(value.get("pauseRequested", False)),
            bool(value.get("cancelRequested", False)),
            str(value["error"]) if isinstance(value.get("error"), str) else None,
        )


def bounded_path(value: object, *, allow_empty: bool = False) -> str:
    """Validate one ResourceLibrary-relative path without trimming it."""

    if value == "" and allow_empty:
        return ""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise DiscoveryError(
            "the selected scope must be a safe ResourceLibrary-relative path",
            code="invalid_path",
            next_action="select folders or files inside the ResourceLibrary and retry",
        )
    if value.startswith(("/", "\\")) or "\\" in value or ":" in value:
        raise DiscoveryError(
            "the selected scope must be a safe ResourceLibrary-relative path",
            code="invalid_path",
            next_action="select folders or files inside the ResourceLibrary and retry",
        )
    if len(value.encode("utf-8")) > MAX_DISCOVERY_PATH_BYTES:
        raise DiscoveryError(
            "the selected scope path is longer than the Files limit",
            code="invalid_path",
            next_action="select a shorter path inside the ResourceLibrary",
        )
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise DiscoveryError(
            "the selected scope must not escape the ResourceLibrary",
            code="invalid_path",
            next_action="select folders or files inside the ResourceLibrary and retry",
        )
    if len(parts) > MAX_DISCOVERY_SEGMENTS:
        raise DiscoveryError(
            "the selected scope has too many path segments",
            code="invalid_path",
            next_action="select a shallower scope and retry",
        )
    return "/".join(parts)


def deduplicate_scope(entries: tuple[DiscoveryScopeEntry, ...]) -> tuple[DiscoveryScopeEntry, ...]:
    """Drop exact repeats and component-aware parent/descendant overlaps.

    The result keeps the submitted order of the entries that survive.  A
    directory that already covers a later file or descendant directory wins,
    and an explicit file is never silently replaced by a different scope.
    """

    kept: list[DiscoveryScopeEntry] = []
    for entry in entries:
        redundant = False
        for existing in kept:
            if existing.path == entry.path:
                redundant = True
                break
            if existing.kind is DiscoveryEntryKind.DIRECTORY and _covers(existing.path, entry.path):
                redundant = True
                break
        if redundant:
            continue
        # A later directory may subsume an earlier explicit file/descendant.
        kept = [
            existing
            for existing in kept
            if not (
                entry.kind is DiscoveryEntryKind.DIRECTORY and _covers(entry.path, existing.path)
            )
        ]
        kept.append(entry)
    return tuple(kept)


def _covers(parent: str, child: str) -> bool:
    return child == parent or child.startswith(parent.rstrip("/") + "/")


def is_confined(path: str, root: str) -> bool:
    """Whether a Storage path stays inside one ResourceLibrary root."""

    normalized = path.strip("/")
    root_value = root.strip("/")
    if not root_value:
        return True
    return normalized == root_value or normalized.startswith(root_value + "/")
