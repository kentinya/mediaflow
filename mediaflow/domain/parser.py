from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol


@dataclass(frozen=True)
class FileContext:
    storage_id: str
    resource_library_id: str
    path: str
    filename: str
    parent_directories: tuple[str, ...] = field(default_factory=tuple)
    extension: str = ""
    parent_path: str = ""
    size: int | None = None
    modified_at: datetime | None = None

    @property
    def directory_names(self) -> tuple[str, ...]:
        return self.parent_directories


class EvidenceSource(StrEnum):
    FILENAME = "filename"
    PARENT_DIRECTORY = "parent_directory"
    SEASON_DIRECTORY = "season_directory"


class EvidenceConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ParseEvidence:
    field: str
    value: str
    source: EvidenceSource
    confidence: EvidenceConfidence


class ParseWarningCode(StrEnum):
    CONFLICTING_YEAR = "conflicting_year"
    CONFLICTING_TITLE = "conflicting_title"
    CONFLICTING_SEASON = "conflicting_season"
    AMBIGUOUS_EPISODE = "ambiguous_episode"
    INVALID_EPISODE_RANGE = "invalid_episode_range"
    MULTIPLE_YEAR_CANDIDATES = "multiple_year_candidates"
    MALFORMED_EPISODE = "malformed_episode"


@dataclass(frozen=True)
class ParseWarning:
    code: ParseWarningCode
    message: str


class ParserErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    INVALID_PATH = "invalid_path"
    INTERNAL_PARSER_ERROR = "internal_parser_error"


class ParserError(ValueError):
    def __init__(self, code: ParserErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParseResult:
    title_candidate: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    episodes: tuple[int, ...] = field(default_factory=tuple)
    resolution_tag: str | None = None
    source_tag: str | None = None
    video_codec_tag: str | None = None
    audio_tag: str | None = None
    hdr_tag: str | None = None
    version_tag: str | None = None
    release_group: str | None = None
    original_filename: str = ""
    normalized_filename: str = ""
    alternative_title_candidates: tuple[str, ...] = field(default_factory=tuple)
    audio_codec_tag: str | None = None
    audio_channels_tag: str | None = None
    hdr_tags: tuple[str, ...] = field(default_factory=tuple)
    version_tags: tuple[str, ...] = field(default_factory=tuple)
    language_tags: tuple[str, ...] = field(default_factory=tuple)
    extension: str = ""
    raw_tags: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[ParseEvidence, ...] = field(default_factory=tuple)
    warnings: tuple[ParseWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.audio_codec_tag is None and self.audio_tag is not None:
            object.__setattr__(self, "audio_codec_tag", self.audio_tag)
        if self.audio_tag is None and self.audio_codec_tag is not None:
            object.__setattr__(self, "audio_tag", self.audio_codec_tag)
        if not self.hdr_tags and self.hdr_tag:
            object.__setattr__(self, "hdr_tags", (self.hdr_tag,))
        if self.hdr_tag is None and self.hdr_tags:
            object.__setattr__(self, "hdr_tag", self.hdr_tags[0])
        if not self.version_tags and self.version_tag:
            object.__setattr__(self, "version_tags", (self.version_tag,))
        if self.version_tag is None and self.version_tags:
            object.__setattr__(self, "version_tag", self.version_tags[0])


class Parser(Protocol):
    def parse(self, context: FileContext) -> ParseResult: ...
