"""Read-only Explore domain (Slice 51 / Task 51.1).

One bounded, provider-neutral model for the V2 Explore homepage: an internal
browse/search query, a one-page result window, one options catalog and one
exact work detail. This module decides only how a query is validated and how a
provider answer is represented; it never performs HTTP, never resolves a
deployment Provider and never touches Storage, Tasks or Configuration.

The image reference contract lives here as well: a provider image reference is
either ``None`` or exactly one safe path segment (``/abc123.jpg``). A full
URL, protocol-relative value, traversal, encoded separator, query or fragment
is never a valid reference, so no caller can be tricked into loading an
arbitrary image source.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from mediaflow.domain.metadata import MediaType

#: One Explore response carries at most this many works (TMDB page size).
EXPLORE_MAX_ITEMS = 20
#: One options catalog carries at most this many choices per collection.
EXPLORE_MAX_OPTIONS = 300
#: The service page window: page is an integer in ``1..EXPLORE_PAGE_LIMIT``.
EXPLORE_PAGE_LIMIT = 500
#: The service work-ID window for detail reads (SQLite/PostgreSQL int4 bound).
EXPLORE_MAX_WORK_ID = 2_147_483_647
#: The service year window.
EXPLORE_MAX_YEAR = 9_999
#: The service rating window (TMDB vote average is 0..10).
EXPLORE_MAX_RATING = 10.0
#: The service vote-count window.
EXPLORE_MAX_VOTES = 1_000_000_000
#: The keyword window, measured in Unicode code points after trimming.
EXPLORE_MAX_KEYWORD = 200

#: The 默认 rating-sort vote floor applied when the operator does not choose
#: one; it is always echoed back in ``applied.minVotes``.
EXPLORE_DEFAULT_RATING_MIN_VOTES = 100

_EXPLORE_MEDIA_TYPES = frozenset({MediaType.MOVIE.value, MediaType.TV.value})
_LANGUAGE_CODE = re.compile(r"[a-z]{2,3}")
_WORK_ID = re.compile(r"[0-9]{1,10}")
#: One safe image path segment: leading slash, then only unreserved characters
#: plus ``.``; no second slash, no ``..`` segment, no ``% ? #`` and no spaces.
_IMAGE_PATH = re.compile(r"/[A-Za-z0-9][A-Za-z0-9._-]{0,254}")


class ExploreSort(StrEnum):
    """The three supported descending Explore sorts."""

    POPULAR = "popular"
    RATING = "rating"
    DATE = "date"


class ExploreErrorCode(StrEnum):
    """Normalized, secret-free Explore failure categories."""

    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    PROVIDER_AUTHENTICATION = "provider_authentication_failed"
    PROVIDER_PERMISSION = "provider_permission_denied"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_MALFORMED = "provider_malformed"
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"


class ExploreError(RuntimeError):
    """One bounded Explore failure; ``message``/``next_action`` are ours."""

    def __init__(
        self,
        code: ExploreErrorCode,
        message: str,
        *,
        next_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.next_action = next_action


def is_explore_media_type(value: str) -> bool:
    return value in _EXPLORE_MEDIA_TYPES


def parse_work_id(value: str) -> int:
    """Parse a detail work ID or raise the bounded invalid-request error."""

    if not _WORK_ID.fullmatch(value):
        raise ExploreError(
            ExploreErrorCode.INVALID_REQUEST,
            "work id must be a positive integer",
        )
    identifier = int(value)
    if identifier < 1 or identifier > EXPLORE_MAX_WORK_ID:
        raise ExploreError(
            ExploreErrorCode.INVALID_REQUEST,
            "work id must be a positive integer within the supported range",
        )
    return identifier


def safe_image_path(value: object) -> str | None:
    """Return ``value`` only when it is exactly one safe provider image path.

    Anything else — a full URL, protocol-relative value, ``..`` traversal,
    percent-encoded separator, query/fragment, whitespace, wrong type or an
    over-long name — returns ``None`` so the caller renders a missing-image
    placeholder instead of loading an untrusted source.
    """

    if not isinstance(value, str) or len(value) > 255:
        return None
    if not _IMAGE_PATH.fullmatch(value):
        return None
    if ".." in value or "//" in value:
        return None
    return value


def validate_keyword(raw: str) -> str:
    """Trim and validate one search keyword (1–200 code points, no controls)."""

    keyword = raw.strip()
    if not 1 <= len(keyword) <= EXPLORE_MAX_KEYWORD:
        raise ExploreError(
            ExploreErrorCode.INVALID_REQUEST,
            "query must be 1 to 200 characters after trimming",
        )
    for character in keyword:
        if unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
            raise ExploreError(
                ExploreErrorCode.INVALID_REQUEST,
                "query must not contain control characters",
            )
    return keyword


def validate_language_code(raw: str) -> str:
    if not _LANGUAGE_CODE.fullmatch(raw):
        raise ExploreError(
            ExploreErrorCode.INVALID_REQUEST,
            "originalLanguage must be a supported language code",
        )
    return raw


def parse_int_parameter(
    value: str,
    field: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    """Parse one bounded integer query value; bool-like input never applies."""

    if not re.fullmatch(r"-?[0-9]{1,10}", value):
        raise ExploreError(
            ExploreErrorCode.INVALID_REQUEST,
            f"{field} must be an integer within {minimum}..{maximum}",
        )
    parsed = int(value)
    if parsed < minimum or parsed > maximum:
        raise ExploreError(
            ExploreErrorCode.INVALID_REQUEST,
            f"{field} must be an integer within {minimum}..{maximum}",
        )
    return parsed


def parse_rating_parameter(value: str, field: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ExploreError(
            ExploreErrorCode.INVALID_REQUEST,
            f"{field} must be a number within 0..{EXPLORE_MAX_RATING}",
        ) from error
    if not math.isfinite(parsed) or not 0 <= parsed <= EXPLORE_MAX_RATING:
        raise ExploreError(
            ExploreErrorCode.INVALID_REQUEST,
            f"{field} must be a finite number within 0..{EXPLORE_MAX_RATING}",
        )
    return parsed


@dataclass(frozen=True)
class ExploreGenre:
    genre_id: int
    name: str


@dataclass(frozen=True)
class ExploreLanguage:
    code: str
    name: str


@dataclass(frozen=True)
class ExploreOptions:
    provider: str
    media_type: MediaType
    genres: tuple[ExploreGenre, ...]
    languages: tuple[ExploreLanguage, ...]

    def __post_init__(self) -> None:
        if len(self.genres) > EXPLORE_MAX_OPTIONS or len(self.languages) > EXPLORE_MAX_OPTIONS:
            raise ValueError("explore options must stay within the catalog limit")


@dataclass(frozen=True)
class ExploreBrowseQuery:
    """One validated, fully explicit browse page read."""

    media_type: MediaType
    sort: ExploreSort = ExploreSort.POPULAR
    genre_id: int | None = None
    original_language: str | None = None
    year: int | None = None
    min_rating: float | None = None
    min_votes: int | None = None
    page: int = 1

    def __post_init__(self) -> None:
        if self.media_type not in _EXPLORE_MEDIA_TYPES:
            raise ExploreError(ExploreErrorCode.INVALID_REQUEST, "mediaType must be movie or tv")
        if not 1 <= self.page <= EXPLORE_PAGE_LIMIT:
            raise ExploreError(
                ExploreErrorCode.INVALID_REQUEST,
                f"page must be an integer within 1..{EXPLORE_PAGE_LIMIT}",
            )
        if self.genre_id is not None and not 1 <= self.genre_id <= EXPLORE_MAX_WORK_ID:
            raise ExploreError(
                ExploreErrorCode.INVALID_REQUEST, "genreId is outside the supported range"
            )
        if self.original_language is not None:
            validate_language_code(self.original_language)
        if self.year is not None and not 1 <= self.year <= EXPLORE_MAX_YEAR:
            raise ExploreError(ExploreErrorCode.INVALID_REQUEST, "year must be within 1..9999")
        if self.min_rating is not None and (
            not math.isfinite(self.min_rating) or not 0 <= self.min_rating <= EXPLORE_MAX_RATING
        ):
            raise ExploreError(ExploreErrorCode.INVALID_REQUEST, "minRating must be within 0..10")
        if self.min_votes is not None and not 0 <= self.min_votes <= EXPLORE_MAX_VOTES:
            raise ExploreError(
                ExploreErrorCode.INVALID_REQUEST, "minVotes is outside the supported range"
            )

    @property
    def effective_min_votes(self) -> int | None:
        """The vote floor actually applied to the provider read."""

        if self.min_votes is None and self.sort is ExploreSort.RATING:
            return EXPLORE_DEFAULT_RATING_MIN_VOTES
        return self.min_votes

    @property
    def is_default(self) -> bool:
        return (
            self.sort is ExploreSort.POPULAR
            and self.genre_id is None
            and self.original_language is None
            and self.year is None
            and self.min_rating is None
            and self.min_votes is None
            and self.page == 1
        )


@dataclass(frozen=True)
class ExploreSearchQuery:
    media_type: MediaType
    keyword: str
    page: int = 1

    def __post_init__(self) -> None:
        if self.media_type not in _EXPLORE_MEDIA_TYPES:
            raise ExploreError(ExploreErrorCode.INVALID_REQUEST, "mediaType must be movie or tv")
        validate_keyword(self.keyword)
        if not 1 <= self.page <= EXPLORE_PAGE_LIMIT:
            raise ExploreError(
                ExploreErrorCode.INVALID_REQUEST,
                f"page must be an integer within 1..{EXPLORE_PAGE_LIMIT}",
            )


@dataclass(frozen=True)
class ExploreItem:
    provider: str
    provider_id: str
    media_type: MediaType
    title: str
    original_title: str | None = None
    year: int | None = None
    release_date: str | None = None
    #: ``None`` means genuinely unrated (no votes) — never a fabricated 0.
    vote_average: float | None = None
    vote_count: int = 0
    poster_path: str | None = None
    backdrop_path: str | None = None
    genre_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class ExplorePage:
    """One bounded result window plus the query actually applied."""

    provider: str
    media_type: MediaType
    page: int
    total_pages: int
    total_results: int
    items: tuple[ExploreItem, ...]
    sort: ExploreSort
    genre_id: int | None = None
    original_language: str | None = None
    year: int | None = None
    min_rating: float | None = None
    min_votes: int | None = None
    page_limit: int = EXPLORE_PAGE_LIMIT
    keyword: str | None = None

    def __post_init__(self) -> None:
        if len(self.items) > EXPLORE_MAX_ITEMS:
            raise ValueError("an explore page must stay within the item limit")
        if self.total_pages < 1 or self.total_results < 0 or self.page < 1:
            raise ValueError("invalid explore page window")

    @property
    def has_more(self) -> bool:
        return self.page < self.total_pages and self.page < self.page_limit


@dataclass(frozen=True)
class ExploreDetail:
    """One exact work; identity is provider + media type + immutable ID."""

    provider: str
    provider_id: str
    media_type: MediaType
    title: str
    original_title: str | None = None
    year: int | None = None
    release_date: str | None = None
    vote_average: float | None = None
    vote_count: int = 0
    genres: tuple[str, ...] = ()
    overview: str | None = None
    runtime: int | None = None
    first_air_date: str | None = None
    number_of_seasons: int | None = None
    #: TV total episode count when the provider publishes one; ``None`` stays
    #: an honest missing value and is never fabricated from season data.
    number_of_episodes: int | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    external_url: str = ""


@runtime_checkable
class ExploreProvider(Protocol):
    """The one read-only Explore port a deployment provider may implement.

    It is deliberately separate from ``MetadataProvider``: organizing keeps its
    existing provider contract (no fake has to grow browse methods), and the
    application layer proves support with one structural check before use.
    """

    @property
    def provider_id(self) -> str: ...

    def browse(self, query: ExploreBrowseQuery) -> ExplorePage: ...

    def search(self, query: ExploreSearchQuery) -> ExplorePage: ...

    def detail(self, media_type: MediaType, provider_id: int) -> ExploreDetail: ...

    def options(self, media_type: MediaType) -> ExploreOptions: ...
