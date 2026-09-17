"""Domain vocabulary for Files direct file-management commands.

Direct commands are ordinary operator file operations — create directory,
create text file, rename, bounded text save and delete — confined to one
exact Active ResourceLibrary.  They are never media-organization decisions:
no recognition, metadata, naming or classification input participates, and
every mutation is executed only through OrganizerExecutor.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

#: Longest single name (basename) accepted for Create/Rename.  This matches
#: the common filesystem/SMB per-component limit without assuming one provider.
MAX_BASENAME_BYTES = 255

#: Largest bounded text document admitted for open or save.  The same limit
#: applies to both directions so a loaded document is always saveable.
MAX_TEXT_BYTES = 512 * 1024

#: Most top-level paths one Delete command may target.
MAX_DELETE_PATHS = 50

#: Most entries one bounded impact enumeration may visit before it refuses
#: to continue.  Stops unbounded walks before any mutation is authorized.
MAX_IMPACT_ENTRIES = 5000

#: Deepest directory nesting one impact enumeration may descend.
MAX_IMPACT_DEPTH = 32

#: Largest total byte size one bounded Delete impact may cover.
MAX_IMPACT_BYTES = 20 * 1024**3

#: Most top-level source paths one Copy/Move command may name.  Bounded so the
#: confirmed logical transfer manifest stays reviewable and independently
#: recoverable per top-level selection, matching the Delete selection bound.
MAX_TRANSFER_PATHS = 50

#: Most entries one bounded transfer may enumerate across every selected tree
#: before it refuses to continue.  The same bounded scope protects admission
#: and every durable per-entry checkpoint.
MAX_TRANSFER_ENTRIES = 5000

#: Deepest directory nesting one bounded transfer enumeration may descend.
MAX_TRANSFER_DEPTH = 32

#: Largest total byte size one bounded transfer may cover.
MAX_TRANSFER_BYTES = 20 * 1024**3

#: Reserved Windows device names that must never be created through a name
#: field because SMB shares reject or dangerously reinterpret them.
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)

#: Allowlisted bounded-text extensions for open/save/create.  Media binary
#: containers are deliberately absent; editing is not media probing.
TEXT_FILE_EXTENSIONS = frozenset(
    {
        ".ass",
        ".csv",
        ".ini",
        ".json",
        ".log",
        ".md",
        ".nfo",
        ".srt",
        ".ssa",
        ".sub",
        ".txt",
        ".vtt",
        ".xml",
        ".yaml",
        ".yml",
    }
)


class DirectFileOperation(StrEnum):
    CREATE_DIRECTORY = "create_directory"
    CREATE_TEXT = "create_text"
    RENAME = "rename"
    SAVE_TEXT = "save_text"
    DELETE = "delete"


class TransferOperation(StrEnum):
    """The two explicitly requested Files transfer operations.

    There is deliberately no implicit third value: a Copy is never executed as a
    Move, a Move is never executed as a Copy, and no organize operation is
    reused as a stand-in.
    """

    COPY = "copy"
    MOVE = "move"


class TransferConflictMode(StrEnum):
    """The explicit destination-conflict choice of one bounded transfer.

    ``FAIL`` is the default no-overwrite behavior: a conflicting destination is
    reported as an exact affected-item failure and nothing is replaced.
    ``SKIP`` leaves the conflicting destination and source untouched.
    ``KEEP_BOTH`` publishes the transfer at a backend-generated unique name.
    Replace is intentionally absent: it would require one destination-bound
    destructive confirmation and is not implemented by this Task.
    """

    FAIL = "fail"
    SKIP = "skip"
    KEEP_BOTH = "keep_both"


class TransferCheckpoint(StrEnum):
    """The durable per-entry checkpoint of one compound cross-Storage Move."""

    SOURCE_OBSERVED = "source_observed"
    COPY_WRITTEN = "copy_written"
    DESTINATION_VERIFIED = "destination_verified"
    SOURCE_DELETED = "source_deleted"


class TransferEntryKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True)
class TransferManifestEntry:
    """One bounded, provider-neutral source entry of a transfer manifest.

    ``fingerprint`` is the provider's verifiable entry identity when the
    provider publishes one; it is empty when it does not (OpenList and SMB
    regular entries, S3 virtual directories).  Size and ``modified_at`` are
    always the exact observed provider metadata.  No host path, credential or
    provider DTO ever appears here.
    """

    path: str
    kind: TransferEntryKind
    size: int
    modified_at: str
    fingerprint: str

    @property
    def is_directory(self) -> bool:
        return self.kind is TransferEntryKind.DIRECTORY


@dataclass(frozen=True)
class TransferManifest:
    """The pinned, confirmed logical scope of one bounded Copy/Move command.

    The manifest binds the exact Active configuration revision/digest, the
    source and destination ResourceLibrary/Storage identities, the normalized
    relative roots, the requested operation, the explicit conflict choice, the
    deterministic per-entry destination paths and the bounded entry scope.  Only
    an opaque digest of this server-side value is returned to the browser.
    """

    revision_id: str
    revision_digest: str
    source_resource_library_id: str
    source_storage_id: str
    source_root: str
    destination_resource_library_id: str
    destination_storage_id: str
    destination_root: str
    destination_directory: str
    operation: TransferOperation
    conflict_mode: TransferConflictMode
    same_storage: bool
    top_level_paths: tuple[str, ...]
    entries: tuple[TransferManifestEntry, ...]
    destinations: tuple[tuple[str, str], ...]
    keep_both_names: tuple[tuple[str, str], ...]
    digest: str

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def total_bytes(self) -> int:
        return sum(entry.size for entry in self.entries if not entry.is_directory)

    @property
    def file_count(self) -> int:
        return sum(1 for entry in self.entries if not entry.is_directory)

    @property
    def directory_count(self) -> int:
        return sum(1 for entry in self.entries if entry.is_directory)

    def destination_for(self, path: str) -> str | None:
        return dict(self.destinations).get(path)


@dataclass(frozen=True)
class TransferConflict:
    """One exact destination conflict of the bounded transfer scope."""

    path: str
    destination: str
    resolution: str


@dataclass(frozen=True)
class TransferImpact:
    """The zero-mutation impact/admission result one transfer confirmation holds.

    ``manifest`` is the exact pinned scope; ``conflicts`` names every current
    destination conflict together with the deterministic resolution the chosen
    mode would apply.  The browser receives only the bounded document and the
    opaque ``digest``.
    """

    manifest: TransferManifest
    conflicts: tuple[TransferConflict, ...]
    capability: str
    unavailable: tuple[str, ...] = ()

    def document(self) -> dict[str, object]:
        return {
            "resourceLibraryId": self.manifest.source_resource_library_id,
            "destinationResourceLibraryId": self.manifest.destination_resource_library_id,
            "operation": self.manifest.operation.value,
            "conflictMode": self.manifest.conflict_mode.value,
            "sameStorage": self.manifest.same_storage,
            "sourceLibraryRoot": self.manifest.source_root,
            "destinationDirectory": self.manifest.destination_directory,
            "capability": self.capability,
            "topLevelPaths": list(self.manifest.top_level_paths),
            "destinations": [
                {"path": path, "destination": destination}
                for path, destination in self.manifest.destinations
            ],
            "entries": [
                {
                    "path": entry.path,
                    "isDirectory": entry.is_directory,
                    "size": entry.size,
                    "modifiedAt": entry.modified_at,
                }
                for entry in self.manifest.entries
            ],
            "fileCount": self.manifest.file_count,
            "directoryCount": self.manifest.directory_count,
            "totalBytes": self.manifest.total_bytes,
            "conflicts": [
                {
                    "path": conflict.path,
                    "destination": conflict.destination,
                    "resolution": conflict.resolution,
                }
                for conflict in self.conflicts
            ],
            "unavailable": list(self.unavailable),
            "manifestDigest": self.manifest.digest,
            "sideEffects": "none",
            "retrySafe": True,
            "nextAction": (
                "confirm this exact bounded transfer to execute it"
                if not self.unavailable
                else "correct the reported limitation before submitting the transfer"
            ),
        }


@dataclass(frozen=True)
class SourceCleanupProjection:
    """Read-only evidence of one OrganizePolicy ``sourceDirectoryCleanup``.

    This explains the already-pinned destructive policy exactly: the configured
    mode/patterns/bounds, the currently matched regular files, every blocking
    entry and the expected directory/prefix outcome.  It is explanatory evidence
    for the pinned OrganizePolicy, never a reusable direct Delete token.
    """

    parent: str
    mode: str
    ignore_patterns: tuple[str, ...]
    max_parent_directories: int
    max_entries: int
    matched_files: tuple[str, ...]
    blocking_entries: tuple[str, ...]
    expected_directory_outcome: str

    def document(self) -> dict[str, object]:
        return {
            "parent": self.parent,
            "mode": self.mode,
            "ignorePatterns": list(self.ignore_patterns),
            "maxParentDirectories": self.max_parent_directories,
            "maxEntries": self.max_entries,
            "matchedFiles": list(self.matched_files),
            "blockingEntries": list(self.blocking_entries),
            "expectedDirectoryOutcome": self.expected_directory_outcome,
            "permanentDelete": self.mode == "ignorable",
            "sideEffects": "none",
            "retrySafe": True,
        }


def transfer_manifest_digest(payload: dict[str, object]) -> str:
    """The opaque, secret-free digest of one server-side transfer manifest."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "t1." + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]


def unsafe_direct_basename(value: object) -> bool:
    """Whether value is unusable as one path component for Create/Rename.

    Rejects separators, traversal segments, control characters, reserved
    device names and trailing dots/spaces that SMB would silently strip.
    """

    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > MAX_BASENAME_BYTES:
        return True
    if value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        return True
    if any(ord(char) < 0x20 for char in value):
        return True
    if any(char in ':*?"<>|' for char in value):
        return True
    if value.rstrip(" ").rstrip(".") != value:
        return True
    if value.split(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
        return True
    return False


def is_text_file_name(value: str) -> bool:
    """Whether a basename is an allowlisted bounded-text file name."""

    if not isinstance(value, str) or value.startswith(".") or "/" in value:
        return False
    suffix = value.rpartition(".")[2].lower()
    return bool(suffix) and f".{suffix}" in TEXT_FILE_EXTENSIONS


@dataclass(frozen=True)
class TextVersionEvidence:
    """Executor-admitted evidence pinning one exact loaded text version."""

    size: int
    modified_at: str
    digest: str

    def document(self) -> dict[str, object]:
        return {"size": self.size, "modifiedAt": self.modified_at, "digest": self.digest}


@dataclass(frozen=True)
class DirectFileTextDocument:
    """One zero-mutation bounded text read result."""

    resource_library_id: str
    path: str
    content: str
    evidence: TextVersionEvidence


@dataclass(frozen=True)
class EntryVersionEvidence:
    """Loaded-version evidence of one bounded *text* document.

    This is the text-edit fence only: it covers the exact bytes the operator
    loaded, which are bounded by :data:`MAX_TEXT_BYTES`, so the bounded text
    read that produces it is also the content-authoritative admission for the
    Save.  It is never Rename or Delete evidence — those commands are fenced by
    :class:`DirectEntryEvidence`, because a version check that reads the whole
    entry would make an ordinary file-management command's cost proportional to
    the media file size.
    """

    size: int
    modified_at: str
    digest: str


@dataclass(frozen=True)
class DirectEntryEvidence:
    """Metadata-only exact-version evidence of one entry, for Rename and Delete.

    Every component comes from a provider observation (`stat`/`list`):
    ``fingerprint`` is the provider's own verifiable entry identity (Local:
    ``inode:…:ctime:…``, S3: the object validator).  There is deliberately no
    content digest here: the whole point of this type is that Rename and Delete
    prove the exact observed version from provider metadata alone, so their cost
    never depends on file size and no media byte is read to fence a mutation.

    A provider that publishes no such identity cannot prove the entry version at
    all, and the command fails closed before any Task or Storage mutation rather
    than falling back to size, `mtime` or a content prefix.
    """

    size: int
    modified_at: str
    is_directory: bool
    fingerprint: str


@dataclass(frozen=True)
class RenameEvidence:
    """Server-issued version evidence one Rename command must return.

    ``token`` binds the exact entry version the backend observed — Active
    ResourceLibrary, ResourceLibrary-relative path, entry type, size, modified
    time and the provider's verifiable entry identity — without disclosing any
    of those implementation values to the browser.  Only the backend can mint
    it, and an older token never matches a changed entry, so replaying stale
    evidence fails closed instead of renaming a replacement.
    """

    resource_library_id: str
    path: str
    is_directory: bool
    size: int
    modified_at: str
    token: str

    def document(self) -> dict[str, object]:
        return {
            "resourceLibraryId": self.resource_library_id,
            "path": self.path,
            "isDirectory": self.is_directory,
            "size": self.size,
            "modifiedAt": self.modified_at,
            # The provider identity stays server-side: the browser only needs
            # the opaque version token it must return.
            "evidence": self.token,
        }


def entry_version_token(
    *,
    resource_library_id: str,
    path: str,
    is_directory: bool,
    size: int,
    modified_at: str,
    fingerprint: str,
) -> str:
    """The opaque, secret-free version token of one observed entry.

    The token covers the exact observed entry version — including the provider's
    verifiable entry identity — so re-deriving it from a later observation only
    reproduces the client's token while nothing about the entry changed.  It is
    not a permission: the command still requires the operator's permission, the
    Active ResourceLibrary and every admission check.
    """

    payload = json.dumps(
        {
            "resourceLibraryId": resource_library_id,
            "path": path,
            "isDirectory": is_directory,
            "size": size,
            "modifiedAt": modified_at,
            "fingerprint": fingerprint,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "v1." + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class DirectFileImpactEntry:
    """One bounded entry of a Delete impact enumeration.

    ``modified_at`` and ``fingerprint`` participate in the scope digest so a
    same-size source replacement (or a same-name directory replacement) between
    the impact preview and the confirmation is rejected as stale instead of
    deleting the replaced content.  ``fingerprint`` is the provider's verifiable
    entry identity (Local: inode+ctime, S3: the object validator) and is
    mandatory: an entry the provider cannot identify never enters a confirmed
    Delete scope, so no size/`mtime` fallback can authorize a mutation.
    """

    path: str
    is_directory: bool
    size: int
    modified_at: str
    fingerprint: str


@dataclass(frozen=True)
class DeleteImpact:
    """Bounded, human-presentable effect of one Delete request.

    ``scope_digest`` pins the exact enumerated scope so the later mutating
    command can prove the operator confirmed this exact effect.
    """

    resource_library_id: str
    top_level_paths: tuple[str, ...]
    entries: tuple[DirectFileImpactEntry, ...]
    file_count: int
    directory_count: int
    total_bytes: int
    truncated: bool
    scope_digest: str

    def document(self) -> dict[str, object]:
        return {
            "resourceLibraryId": self.resource_library_id,
            "topLevelPaths": list(self.top_level_paths),
            "entries": [
                {
                    "path": entry.path,
                    "isDirectory": entry.is_directory,
                    "size": entry.size,
                    "modifiedAt": entry.modified_at,
                    # The provider identity participates in the scope digest
                    # (see the application service) but is deliberately not
                    # disclosed to the browser: the client only needs the
                    # bounded path/size/mtime summary plus the digest.
                }
                for entry in self.entries
            ],
            "fileCount": self.file_count,
            "directoryCount": self.directory_count,
            "totalBytes": self.total_bytes,
            "truncated": self.truncated,
            "scopeDigest": self.scope_digest,
        }
