from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mediaflow.domain.classification import ClassificationResult
    from mediaflow.domain.metadata import MediaIdentity
    from mediaflow.domain.naming import NamingResult


class OrganizeOperationType(StrEnum):
    CREATE_DIRECTORY = "create_directory"
    MOVE = "move"
    COPY = "copy"
    HARD_LINK = "hard_link"
    SOFT_LINK = "soft_link"
    DELETE = "delete"


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
    destination_location: StorageLocation | None = None
    overwrite_authorized: bool = False
    attachment_plans: tuple[AttachmentPlan, ...] = ()

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

    @property
    def createdDirectories(self) -> tuple[str, ...]:
        return self.created_directories

    @property
    def completedOperations(self) -> tuple[str, ...]:
        return self.completed_operations
