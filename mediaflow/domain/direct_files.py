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

#: Chunk size of the complete streaming content digest one Rename evidence
#: carries.  The digest covers the entire entry content — a prefix-only sample
#: cannot prove the version of a file whose remaining bytes changed — while the
#: read stays memory bounded by this constant.
RENAME_DIGEST_CHUNK_BYTES = 1024 * 1024

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
    """Server-issued observed state of one entry, used as mutation fencing.

    The Rename/Delete/Save commands bind this evidence at admission and the
    executor re-verifies it at the last safe boundary before the mutating
    Storage call, so a source replaced after it was observed is never
    destroyed or overwritten.

    ``fingerprint`` is the provider's optional stable identity token (e.g.
    inode+ctime for Local, ETag for S3).  When the provider offers one it is
    the strongest fence available, including for directories where size is
    constant and mtime may legitimately move.

    ``digest`` is the exact observed content digest of the bytes this evidence
    covers: the full loaded document for a bounded text Save, and the complete
    streamed content of the entry for a Rename.  A Rename digest always covers
    the whole file — a prefix-only sample cannot prove the version of a file
    whose remaining bytes changed — and it is the fence that stays
    deterministic even where a provider's timestamps are too coarse to separate
    two writes, so a same-size/same-mtime content replacement is still refused
    on a provider that offers no fingerprint at all.
    """

    size: int
    modified_at: str
    digest: str | None = None
    is_directory: bool | None = None
    fingerprint: str | None = None


@dataclass(frozen=True)
class RenameEvidence:
    """Server-issued version evidence one Rename command must return.

    ``token`` binds the exact entry version the backend observed — Active
    ResourceLibrary, ResourceLibrary-relative path, entry type, size, modified
    time, the provider fingerprint and the complete streamed content digest —
    without disclosing any of those implementation values to the browser.  Only
    the backend can mint it, and an older token never matches a changed entry,
    so replaying stale evidence fails closed instead of renaming a replacement.
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
            # The provider fingerprint and the content digest stay server-side:
            # the browser only needs the opaque version token it must return.
            "evidence": self.token,
        }


def stream_content_digest(
    stream, *, chunk_bytes: int = RENAME_DIGEST_CHUNK_BYTES
) -> tuple[str, int]:
    """The SHA-256 digest and byte count of one complete provider stream.

    The whole content is hashed in bounded chunks, so the evidence proves the
    complete entry version while memory stays constant.  Short reads are
    tolerated (the loop stops only at end of stream), and the byte count it
    returns lets a caller prove the stream still had exactly the observed size.
    """

    digest = hashlib.sha256()
    counted = 0
    while True:
        chunk = stream.read(chunk_bytes)
        if not chunk:
            break
        digest.update(chunk)
        counted += len(chunk)
    return digest.hexdigest(), counted


def entry_version_token(
    *,
    resource_library_id: str,
    path: str,
    is_directory: bool,
    size: int,
    modified_at: str,
    fingerprint: str | None,
    content_digest: str | None,
) -> str:
    """The opaque, secret-free version token of one observed entry.

    The token covers the exact observed entry version, so re-deriving it from a
    later observation only reproduces the client's token while nothing about the
    entry changed.  It is not a permission: the command still requires the
    operator's permission, the Active ResourceLibrary and every admission check.
    """

    payload = json.dumps(
        {
            "resourceLibraryId": resource_library_id,
            "path": path,
            "isDirectory": is_directory,
            "size": size,
            "modifiedAt": modified_at,
            "fingerprint": fingerprint,
            "contentDigest": content_digest,
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
    deleting the replaced content.  ``fingerprint`` carries the provider's
    stable identity token when the provider offers one (Local: inode+ctime,
    S3: ETag); providers without one fall back to mtime fencing.
    """

    path: str
    is_directory: bool
    size: int
    modified_at: str
    fingerprint: str | None = None


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
