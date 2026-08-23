from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HashMode(StrEnum):
    NONE = "none"
    FAST = "fast"
    FULL = "full"


@dataclass(frozen=True)
class HashPolicy:
    mode: HashMode = HashMode.NONE
    fast_sample_bytes: int = 1_048_576
    full_max_file_size: int = 1_099_511_627_776
    chunk_size: int = 1_048_576

    def __post_init__(self) -> None:
        if not isinstance(self.mode, HashMode):
            raise ValueError("Hash mode must be NONE, FAST, or FULL")
        values = (self.fast_sample_bytes, self.full_max_file_size, self.chunk_size)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("Hash policy limits must be integers")
        if not 1 <= self.fast_sample_bytes <= 64 * 1024 * 1024:
            raise ValueError("fast Hash sample must be between 1 byte and 64 MiB")
        if not 1 <= self.chunk_size <= 16 * 1024 * 1024:
            raise ValueError("Hash chunk size must be between 1 byte and 16 MiB")
        if not 1 <= self.full_max_file_size <= 16 * 1024**4:
            raise ValueError("full Hash maximum file size is invalid")


class HashStatus(StrEnum):
    SKIPPED = "skipped"
    COMPLETE = "complete"
    INDETERMINATE = "indeterminate"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class FileHashEvidence:
    mode: HashMode
    algorithm: str
    digest: str
    file_size: int
    bytes_hashed: int
    complete_content: bool


@dataclass(frozen=True)
class HashResult:
    status: HashStatus
    evidence: FileHashEvidence | None = None
    reason: str | None = None


class DuplicateStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    UNIQUE = "unique"
    DUPLICATE = "duplicate"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class DuplicateComparisonResult:
    status: DuplicateStatus
    mode: HashMode
    source_hash: HashResult | None = None
    destination_hash: HashResult | None = None
    reason: str | None = None
