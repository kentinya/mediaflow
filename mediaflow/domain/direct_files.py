"""Domain vocabulary for Files direct file-management commands.

Direct commands are ordinary operator file operations — create directory,
create text file, rename, bounded text save and delete — confined to one
exact Active ResourceLibrary.  They are never media-organization decisions:
no recognition, metadata, naming or classification input participates, and
every mutation is executed only through OrganizerExecutor.
"""

from __future__ import annotations

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
    """

    size: int
    modified_at: str
    digest: str | None = None
    is_directory: bool | None = None


@dataclass(frozen=True)
class DirectFileImpactEntry:
    """One bounded entry of a Delete impact enumeration.

    ``modified_at`` participates in the scope digest so a same-size source
    replacement between the impact preview and the confirmation is rejected
    as stale instead of deleting the replaced content.
    """

    path: str
    is_directory: bool
    size: int
    modified_at: str


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
                }
                for entry in self.entries
            ],
            "fileCount": self.file_count,
            "directoryCount": self.directory_count,
            "totalBytes": self.total_bytes,
            "truncated": self.truncated,
            "scopeDigest": self.scope_digest,
        }
