from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

DEFAULT_MEDIA_EXTENSIONS = ("mkv", "mp4", "avi", "mov", "wmv", "ts", "m2ts", "webm", "iso")
DEFAULT_EXCLUDE_RULES = (
    "**/.git/**",
    "**/@eaDir/**",
    "**/#recycle/**",
    "**/.Trash/**",
    "*.part",
    "*.tmp",
    "*.download",
    "*.crdownload",
    "*.!qB",
)


class ScanMode(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"


class ScanRuleKind(StrEnum):
    PATH = "path"
    FILENAME = "filename"
    EXTENSION = "extension"
    DIRECTORY = "directory"
    GLOB = "glob"
    REGEX = "regex"


@dataclass(frozen=True)
class ScanRule:
    kind: ScanRuleKind
    pattern: str

    def __post_init__(self) -> None:
        if not self.pattern or "\x00" in self.pattern:
            raise ValueError("scan rule pattern must be non-empty and contain no NUL")
        if self.kind is ScanRuleKind.REGEX:
            re.compile(self.pattern)


@dataclass(frozen=True)
class FileStabilityPolicy:
    minimum_age_seconds: int = 0
    modified_threshold_seconds: int = 0
    stable_size_duration_seconds: int = 0

    def __post_init__(self) -> None:
        if (
            self.minimum_age_seconds < 0
            or self.modified_threshold_seconds < 0
            or self.stable_size_duration_seconds < 0
        ):
            raise ValueError("file stability durations must be non-negative")

    @property
    def min_file_age_seconds(self) -> int:
        return self.minimum_age_seconds

    @property
    def min_stable_duration_seconds(self) -> int:
        return self.stable_size_duration_seconds


@dataclass(frozen=True)
class ResourceLibrary:
    library_id: str
    name: str
    storage_id: str
    root_path: str
    enabled: bool = True
    include_rules: tuple[ScanRule | str, ...] = field(default_factory=tuple)
    exclude_rules: tuple[ScanRule | str, ...] = field(default_factory=lambda: DEFAULT_EXCLUDE_RULES)
    stability_policy: FileStabilityPolicy = field(default_factory=FileStabilityPolicy)
    recognition_rule_set_id: str | None = None
    scan_mode: ScanMode = ScanMode.FULL
    max_depth: int | None = None
    file_extensions: tuple[str, ...] = field(default_factory=lambda: DEFAULT_MEDIA_EXTENSIONS)
    max_scan_concurrency: int = 4
    persistence_batch_size: int = 500
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.library_id or not self.name or not self.storage_id:
            raise ValueError("library ID, name, and storage ID are required")
        if self.max_depth is not None and self.max_depth < 0:
            raise ValueError("max_depth must be non-negative or None")
        if self.max_scan_concurrency < 1 or self.persistence_batch_size < 1:
            raise ValueError("scan concurrency and persistence batch size must be positive")
        normalized: list[str] = []
        for extension in self.file_extensions:
            value = extension.lower().lstrip(".")
            if not value or "/" in value or "\\" in value or "\x00" in value:
                raise ValueError("invalid file extension")
            normalized.append(value)
        object.__setattr__(self, "file_extensions", tuple(dict.fromkeys(normalized)))
        object.__setattr__(self, "include_rules", tuple(_rule(rule) for rule in self.include_rules))
        object.__setattr__(self, "exclude_rules", tuple(_rule(rule) for rule in self.exclude_rules))


def _rule(value: ScanRule | str) -> ScanRule:
    return value if isinstance(value, ScanRule) else ScanRule(ScanRuleKind.GLOB, value)


@dataclass(frozen=True)
class MediaLibrary:
    library_id: str
    name: str
    storage_id: str
    root_path: str
    enabled: bool = True
