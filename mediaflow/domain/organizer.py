from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mediaflow.domain.classification import ClassificationResult
    from mediaflow.domain.metadata import MediaIdentity
    from mediaflow.domain.naming import NamingResult

from mediaflow.domain.duplicates import DuplicateComparisonResult, HashPolicy


class OrganizeOperationType(StrEnum):
    CREATE_DIRECTORY = "create_directory"
    MOVE = "move"
    COPY = "copy"
    HARD_LINK = "hard_link"
    SOFT_LINK = "soft_link"
    DELETE = "delete"


@dataclass(frozen=True)
class DestinationComposition:
    media_library_root: str
    relative_destination: str
    target: str
    unsafe_contribution: str | None = None

    @property
    def safe(self) -> bool:
        return self.unsafe_contribution is None


def safe_destination_root(value: str) -> str | None:
    """Normalize a MediaLibrary root; it is the only destination input allowed absolute."""
    if not value or "\\" in value or "\x00" in value:
        return None
    if any(part in {".", ".."} for part in value.split("/")):
        return None
    absolute = value.startswith("/")
    normalized = posixpath.normpath(value)
    parts = normalized.lstrip("/").split("/")
    if any(part in {"", ".", ".."} for part in parts) and normalized != "/":
        return None
    if not absolute and normalized.startswith("../"):
        return None
    return normalized


def unsafe_relative_destination_path(value: str) -> bool:
    return (
        not value
        or value.startswith(("/", "\\"))
        or "\\" in value
        or "\x00" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    )


def unsafe_destination_filename(value: str) -> bool:
    return unsafe_relative_destination_path(value) or "/" in value


def compose_destination(
    media_library_root: str,
    classification_relative_path: str,
    naming_directory: str,
    naming_directory_segments: tuple[str, ...],
    naming_filename: str,
) -> DestinationComposition:
    root = safe_destination_root(media_library_root)
    unsafe: str | None = None
    if root is None:
        unsafe = "mediaLibrary.rootPath"
    elif unsafe_relative_destination_path(classification_relative_path):
        unsafe = "classification.relativePath"
    elif unsafe_relative_destination_path(naming_directory):
        unsafe = "naming.directory"
    else:
        for index, segment in enumerate(naming_directory_segments):
            if unsafe_relative_destination_path(segment):
                unsafe = f"naming.directorySegments[{index}]"
                break
    if unsafe is None and unsafe_destination_filename(naming_filename):
        unsafe = "naming.filename"
    if unsafe is not None:
        return DestinationComposition("", "", "", unsafe)
    assert root is not None
    relative = posixpath.join(
        classification_relative_path, *naming_directory_segments, naming_filename
    )
    return DestinationComposition(root, relative, posixpath.join(root, relative))


class PlanOperation(StrEnum):
    MOVE = "MOVE"
    COPY = "COPY"
    LINK = "LINK"
    NOOP = "NOOP"
    SKIP = "SKIP"


class PlanStatus(StrEnum):
    READY = "ready"
    CONFLICT = "conflict"
    NOOP = "noop"
    INVALID = "invalid"


class ExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    DRY_RUN = "DRY_RUN"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"


class ExecutionEffectCertainty(StrEnum):
    """Executor-owned evidence about the net effect of one invocation."""

    VERIFIED_COMPLETE = "verified_complete"
    ATTEMPTED_UNVERIFIED = "attempted_unverified"
    NONE = "none"
    UNKNOWN = "unknown"


class ConflictType(StrEnum):
    DESTINATION_EXISTS = "DESTINATION_EXISTS"
    TARGET_COLLISION = "TARGET_COLLISION"
    DUPLICATE_MEDIA = "DUPLICATE_MEDIA"
    INVALID_DESTINATION = "INVALID_DESTINATION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Conflict:
    type: ConflictType
    source: str
    destination: str
    details: str


class ConflictStrategy(StrEnum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"
    MANUAL = "manual"


@dataclass(frozen=True)
class AttachmentPolicy:
    enabled: bool = False
    subtitles: bool = True
    nfo: bool = True
    artwork: bool = True
    trailers: bool = True
    other_same_stem: bool = False


@dataclass(frozen=True)
class RollbackPolicy:
    enabled: bool = False
    cleanup_created_directories: bool = True


class DirectoryCleanupMode(StrEnum):
    NONE = "none"
    EMPTY = "empty"
    IGNORABLE = "ignorable"


@dataclass(frozen=True)
class DirectoryCleanupPolicy:
    mode: DirectoryCleanupMode = DirectoryCleanupMode.NONE
    max_parent_directories: int = 1
    ignore_patterns: tuple[str, ...] = ()
    max_entries: int = 100

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_parent_directories, bool)
            or not 1 <= self.max_parent_directories <= 10
        ):
            raise ValueError("cleanup maximum parent directories must be between 1 and 10")
        if isinstance(self.max_entries, bool) or not 1 <= self.max_entries <= 1000:
            raise ValueError("cleanup maximum entries must be between 1 and 1000")
        if len(self.ignore_patterns) > 32:
            raise ValueError("cleanup supports at most 32 ignore patterns")
        for pattern in self.ignore_patterns:
            if (
                not pattern
                or len(pattern) > 128
                or "/" in pattern
                or "\\" in pattern
                or "\x00" in pattern
                or pattern in {"*", "**"}
            ):
                raise ValueError("cleanup ignore pattern is unsafe")
        if self.mode is not DirectoryCleanupMode.IGNORABLE and self.ignore_patterns:
            raise ValueError("cleanup ignore patterns require ignorable mode")
        if self.mode is DirectoryCleanupMode.IGNORABLE and not self.ignore_patterns:
            raise ValueError("ignorable cleanup requires explicit ignore patterns")


class DirectoryCleanupStatus(StrEnum):
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"
    SUCCESS = "success"
    STOPPED = "stopped"
    REFUSED = "refused"
    FAILED = "failed"


@dataclass(frozen=True)
class DirectoryCleanupStep:
    action: str
    path: str
    success: bool
    reason: str | None = None


class RollbackStatus(StrEnum):
    DISABLED = "disabled"
    NOT_NEEDED = "not_needed"
    SUCCESS = "success"
    PARTIAL = "partial"
    REFUSED = "refused"


@dataclass(frozen=True)
class RollbackStep:
    action: str
    storage_id: str
    source: str | None
    destination: str | None
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class DuplicateIdentity:
    provider: str
    provider_id: str
    media_type: str
    season: int | None = None
    episodes: tuple[int, ...] = ()

    @classmethod
    def from_media_identity(cls, identity: MediaIdentity) -> DuplicateIdentity:
        episodes = identity.episodes or (
            (identity.episode,) if identity.episode is not None else ()
        )
        return cls(
            identity.provider.casefold(),
            identity.provider_id,
            identity.media_type.value,
            identity.season,
            tuple(sorted(set(episodes))),
        )


@dataclass(frozen=True)
class OrganizePolicy:
    policy_id: str
    operation: OrganizeOperationType
    conflict_strategy: ConflictStrategy = ConflictStrategy.MANUAL
    attachments: AttachmentPolicy = field(default_factory=AttachmentPolicy)
    duplicate_detection: HashPolicy = field(default_factory=HashPolicy)
    rollback: RollbackPolicy = field(default_factory=RollbackPolicy)
    source_directory_cleanup: DirectoryCleanupPolicy = field(default_factory=DirectoryCleanupPolicy)


@dataclass(frozen=True)
class OrganizeOperation:
    operation_type: OrganizeOperationType
    source: str | None
    target: str
    overwrite: bool = False


@dataclass(frozen=True)
class StorageLocation:
    """A portable path inside one configured Storage."""

    storage_id: str
    path: str

    def __post_init__(self) -> None:
        if not self.storage_id.strip() or not self.path.strip():
            raise ValueError("storage location ID and path are required")
        if self.path.startswith(("/", "\\")) or "\\" in self.path or "\x00" in self.path:
            raise ValueError("storage location path must be relative")
        if any(part in {"", ".", ".."} for part in self.path.split("/")):
            raise ValueError("storage location path contains an invalid component")


class AttachmentType(StrEnum):
    SUBTITLE = "subtitle"
    NFO = "nfo"
    POSTER = "poster"
    FANART = "fanart"
    TRAILER = "trailer"
    IMAGE = "image"
    OTHER = "other"


@dataclass(frozen=True)
class MediaAttachment:
    source: StorageLocation
    attachment_type: AttachmentType
    suffix: str = ""
    language: str | None = None
    flags: tuple[str, ...] = ()
    size: int = 0


@dataclass(frozen=True)
class MediaFileSet:
    primary: StorageLocation
    attachments: tuple[MediaAttachment, ...] = ()


@dataclass(frozen=True)
class AttachmentPlan:
    source: StorageLocation
    destination: StorageLocation
    attachment_type: AttachmentType
    operation: PlanOperation
    suffix: str = ""


@dataclass(frozen=True)
class OrganizePlan:
    source_storage_id: str
    target_storage_id: str
    source: str
    target: str
    recognition_type_id: str
    naming_policy_id: str
    classification_policy_id: str
    organize_policy_id: str
    operations: tuple[OrganizeOperation, ...] = field(default_factory=tuple)
    operation: PlanOperation = PlanOperation.MOVE
    media_identity: MediaIdentity | None = None
    naming_result: NamingResult | None = None
    classification_result: ClassificationResult | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    conflicts: tuple[Conflict, ...] = field(default_factory=tuple)
    status: PlanStatus = PlanStatus.READY
    plan_id: str = ""
    link_operation: OrganizeOperationType | None = None
    media_library_root: str = ""
    relative_destination: str = ""
    source_location: StorageLocation | None = None
    duplicate_comparison: DuplicateComparisonResult | None = None
    destination_location: StorageLocation | None = None
    overwrite_authorized: bool = False
    attachment_plans: tuple[AttachmentPlan, ...] = ()
    rollback_policy: RollbackPolicy = field(default_factory=RollbackPolicy)
    source_library_root: str = ""
    source_directory_cleanup: DirectoryCleanupPolicy = field(default_factory=DirectoryCleanupPolicy)

    @property
    def destination(self) -> str:
        return self.target


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    operation: PlanOperation
    source: str
    destination: str
    created_directories: tuple[str, ...] = field(default_factory=tuple)
    completed_operations: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    duration: float = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    plan_id: str = ""
    resolved_destination: str = ""
    rollback_status: RollbackStatus = RollbackStatus.NOT_NEEDED
    rollback_steps: tuple[RollbackStep, ...] = ()
    cleanup_status: DirectoryCleanupStatus = DirectoryCleanupStatus.DISABLED
    cleanup_steps: tuple[DirectoryCleanupStep, ...] = ()
    effect_certainty: ExecutionEffectCertainty = ExecutionEffectCertainty.UNKNOWN
    uncertain_effects: tuple[str, ...] = ()

    @property
    def createdDirectories(self) -> tuple[str, ...]:
        return self.created_directories

    @property
    def completedOperations(self) -> tuple[str, ...]:
        return self.completed_operations
