from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from mediaflow.domain.metadata import MediaIdentity, MediaType
from mediaflow.domain.parser import ParseResult


class MissingVariableStrategy(StrEnum):
    ERROR = "error"
    EMPTY = "empty"
    OMIT_TOKEN = "omit_token"


class NamingMediaTypeMode(StrEnum):
    AUTO = "auto"
    MOVIE = "movie"
    TV = "tv"


class SanitizePolicy(StrEnum):
    CROSS_PLATFORM = "cross_platform"


class NamingErrorCode(StrEnum):
    INVALID_TEMPLATE = "invalid_template"
    UNKNOWN_VARIABLE = "unknown_variable"
    MISSING_VARIABLE = "missing_variable"
    INVALID_FORMAT_SPECIFIER = "invalid_format_specifier"
    POLICY_NOT_FOUND = "policy_not_found"
    POLICY_DISABLED = "policy_disabled"
    INVALID_COMPONENT = "invalid_component"
    EMPTY_COMPONENT = "empty_component"
    UNSAFE_PATH = "unsafe_path"
    COMPONENT_TOO_LONG = "component_too_long"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    INTERNAL_ERROR = "internal_error"


class NamingError(ValueError):
    def __init__(self, code: NamingErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class NamingTemplate:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise NamingError(NamingErrorCode.INVALID_TEMPLATE, "naming template is empty")


@dataclass(frozen=True)
class NamingPolicy:
    policy_id: str
    name: str
    movie_directory_template: NamingTemplate | str = "{title} ({year})"
    movie_file_template: NamingTemplate | str = "{title} ({year}).{ext}"
    tv_series_directory_template: NamingTemplate | str = "{title} ({year})"
    tv_season_directory_template: NamingTemplate | str = "Season {season:02}"
    tv_episode_file_template: NamingTemplate | str = (
        "{title} - S{season:02}E{episode:02} - {episode_title}.{ext}"
    )
    multi_episode_file_template: NamingTemplate | str = "{title} - S{season:02}{episodes}.{ext}"
    description: str = ""
    enabled: bool = True
    media_type_mode: NamingMediaTypeMode = NamingMediaTypeMode.AUTO
    missing_variable_strategy: MissingVariableStrategy = MissingVariableStrategy.OMIT_TOKEN
    sanitize_policy: SanitizePolicy = SanitizePolicy.CROSS_PLATFORM
    max_component_length: int = 200
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.name.strip():
            raise NamingError(
                NamingErrorCode.INVALID_TEMPLATE, "naming policy ID and name are required"
            )
        if self.max_component_length < 1:
            raise NamingError(
                NamingErrorCode.COMPONENT_TOO_LONG,
                "max component length must be positive",
            )
        for field_name in (
            "movie_directory_template",
            "movie_file_template",
            "tv_series_directory_template",
            "tv_season_directory_template",
            "tv_episode_file_template",
            "multi_episode_file_template",
        ):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                value if isinstance(value, NamingTemplate) else NamingTemplate(value),
            )


@dataclass(frozen=True)
class NamingContext:
    recognition_type_id: str
    media_identity: MediaIdentity
    parse_result: ParseResult
    original_filename: str = ""
    extension: str = ""

    def __post_init__(self) -> None:
        if not self.recognition_type_id.strip():
            raise ValueError("recognition type ID is required")


@dataclass(frozen=True)
class NamingResult:
    # First two fields preserve the bootstrap positional constructor used by Organizer tests.
    directory: str
    filename: str
    policy_id: str = ""
    recognition_type_id: str = ""
    media_type: MediaType | None = None
    directory_segments: tuple[str, ...] = ()
    rendered_variables: tuple[tuple[str, str], ...] = ()
    warnings: tuple[str, ...] = ()
    sanitization_changes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.directory_segments and self.directory:
            object.__setattr__(self, "directory_segments", (self.directory,))
