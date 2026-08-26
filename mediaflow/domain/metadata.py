from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import RecognitionType


class MediaType(StrEnum):
    MOVIE = "movie"
    TV = "tv"


class MediaQueryType(StrEnum):
    MOVIE = "movie"
    TV = "tv"
    AUTO = "auto"
    NONE = "none"


METADATA_POLICY_CONFIGURATION_FIELDS = frozenset(
    {
        "id",
        "name",
        "providerId",
        "mediaType",
        "mediaQueryType",
        "language",
        "region",
        "automaticThreshold",
        "confirmationThreshold",
        "minimumScoreGap",
        "timeout",
        "retryCount",
        "maxCandidates",
        "maxSearchPages",
        "maxProviderRequests",
        "maxCandidateEnrichments",
        "enabled",
    }
)


@dataclass(frozen=True)
class ProviderCapabilities:
    can_search_movie: bool = False
    can_search_tv: bool = False
    can_get_season: bool = False
    can_get_episode: bool = False
    can_find_by_external_id: bool = False
    can_get_images: bool = False
    can_get_alternative_titles: bool = False


@dataclass(frozen=True)
class MediaCandidate:
    provider: str
    provider_id: str
    media_type: MediaType
    title: str
    original_title: str | None = None
    year: int | None = None
    score: float | None = None
    alternative_titles: tuple[str, ...] = ()
    translated_titles: tuple[str, ...] = ()
    release_date: str | None = None
    canonical_release_date: str | None = None
    regional_release_date: str | None = None
    overview: str | None = None
    original_language: str | None = None
    genres: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    popularity: float | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    external_ids: tuple[tuple[str, str], ...] = ()

    @property
    def canonical_year(self) -> int | None:
        return self.year

    @property
    def regional_year(self) -> int | None:
        return _date_year(self.regional_release_date)


@dataclass(frozen=True)
class EpisodeIdentity:
    episode: int
    title: str
    air_date: str | None = None
    overview: str | None = None


@dataclass(frozen=True)
class MediaIdentity:
    provider: str
    provider_id: str
    media_type: MediaType
    title: str
    original_title: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    episodes: tuple[int, ...] = field(default_factory=tuple)
    episode_title: str | None = None
    genres: tuple[str, ...] = field(default_factory=tuple)
    countries: tuple[str, ...] = field(default_factory=tuple)
    languages: tuple[str, ...] = field(default_factory=tuple)
    keywords: tuple[str, ...] = field(default_factory=tuple)
    alternative_titles: tuple[str, ...] = ()
    translated_titles: tuple[str, ...] = ()
    release_date: str | None = None
    canonical_release_date: str | None = None
    regional_release_date: str | None = None
    overview: str | None = None
    external_ids: tuple[tuple[str, str], ...] = ()
    poster_path: str | None = None
    backdrop_path: str | None = None
    confidence: float | None = None
    matched_by: str | None = None
    recognition_type_id: str | None = None
    episode_metadata: tuple[EpisodeIdentity, ...] = ()

    @property
    def canonical_year(self) -> int | None:
        return self.year

    @property
    def regional_year(self) -> int | None:
        return _date_year(self.regional_release_date)


def _date_year(value: str | None) -> int | None:
    return int(value[:4]) if value and len(value) >= 4 and value[:4].isdigit() else None


@dataclass(frozen=True)
class RetryPolicy:
    retry_count: int = 2
    base_delay: float = 0.1
    max_delay: float = 2.0

    def __post_init__(self) -> None:
        if self.retry_count < 0 or self.base_delay < 0 or self.max_delay < self.base_delay:
            raise ValueError("invalid retry policy")


@dataclass(frozen=True)
class CachePolicy:
    search_ttl: float = 3600
    details_ttl: float = 86400
    negative_ttl: float = 60

    def __post_init__(self) -> None:
        if min(self.search_ttl, self.details_ttl, self.negative_ttl) < 0:
            raise ValueError("cache TTL values must not be negative")


@dataclass(frozen=True)
class MetadataPolicy:
    # Preserve the first fields of the bootstrap model.
    policy_id: str
    provider_id: str
    media_type: MediaType | None = None
    language: str | None = None
    region: str | None = None
    name: str = ""
    media_query_type: MediaQueryType | None = None
    automatic_threshold: float = 90
    confirmation_threshold: float = 70
    minimum_score_gap: float = 5
    timeout: float = 10
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    cache_policy: CachePolicy = field(default_factory=CachePolicy)
    max_candidates: int = 20
    max_search_pages: int = 2
    max_provider_requests: int = 6
    max_candidate_enrichments: int = 2
    enabled: bool = True

    def __post_init__(self) -> None:
        if (
            not isinstance(self.policy_id, str)
            or not self.policy_id
            or not isinstance(self.provider_id, str)
            or not self.provider_id
            or len(self.policy_id) > 64
            or len(self.provider_id) > 64
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.provider_id)
        ):
            raise ValueError("metadata policy identifiers must not be empty")
        if not isinstance(self.name, str) or len(self.name) > 120:
            raise ValueError("invalid metadata policy name")
        if not 0 <= self.confirmation_threshold <= self.automatic_threshold <= 100:
            raise ValueError("invalid metadata confidence thresholds")
        if (
            not math.isfinite(self.minimum_score_gap)
            or not 0 <= self.minimum_score_gap <= 100
            or not math.isfinite(self.timeout)
            or not 0 < self.timeout <= 120
            or not 0 <= self.retry_policy.retry_count <= 10
            or not 1 <= self.max_candidates <= 100
            or not 1 <= self.max_search_pages <= 10
            or not 1 <= self.max_provider_requests <= 100
            or not 0 <= self.max_candidate_enrichments <= 100
        ):
            raise ValueError("invalid metadata policy limits")
        if self.language is not None and (
            not isinstance(self.language, str)
            or len(self.language) > 35
            or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", self.language)
        ):
            raise ValueError("invalid metadata policy language")
        if self.region is not None and (
            not isinstance(self.region, str)
            or len(self.region) > 3
            or not re.fullmatch(r"(?:[A-Za-z]{2}|[0-9]{3})", self.region)
        ):
            raise ValueError("invalid metadata policy region")

    @property
    def query_type(self) -> MediaQueryType:
        if self.media_query_type is not None:
            return self.media_query_type
        if self.media_type is MediaType.MOVIE:
            return MediaQueryType.MOVIE
        if self.media_type is MediaType.TV:
            return MediaQueryType.TV
        return MediaQueryType.AUTO


class CandidateMatchStatus(StrEnum):
    MATCHED = "matched"
    NEED_CONFIRM = "need_confirm"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ScoreComponent:
    name: str
    score: float
    reason: str


@dataclass(frozen=True)
class CandidateScore:
    candidate: MediaCandidate
    total_score: float
    components: tuple[ScoreComponent, ...]
    exact_title: bool = False
    exact_year: bool = False
    matched_local_title: str | None = None
    matched_provider_title: str | None = None
    matched_title_source: str | None = None


@dataclass(frozen=True)
class CandidateMatchResult:
    status: CandidateMatchStatus
    best_candidate: MediaCandidate | None = None
    score: float = 0
    candidate_scores: tuple[CandidateScore, ...] = ()
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class MetadataIdentificationStatus(StrEnum):
    MATCHED = "matched"
    NEED_CONFIRM = "need_confirm"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    PROVIDER_ERROR = "provider_error"
    METADATA_MISMATCH = "metadata_mismatch"


@dataclass(frozen=True)
class MetadataIdentificationResult:
    status: MetadataIdentificationStatus
    recognition_type: RecognitionType
    identity: MediaIdentity | None = None
    match: CandidateMatchResult | None = None
    query: str = ""
    error: MetadataError | None = None

    @property
    def recognition_type_id(self) -> str:
        return self.recognition_type.type_id


class MetadataErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    AUTHENTICATION_FAILED = "authentication_failed"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    CONNECTION_FAILED = "connection_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MALFORMED_RESPONSE = "malformed_response"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    UNKNOWN = "unknown"


class MetadataError(RuntimeError):
    def __init__(
        self, code: MetadataErrorCode, message: str, *, cause: Exception | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.__cause__ = cause


class MetadataProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def search_movie(
        self,
        query: ParseResult,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ) -> Sequence[MediaCandidate]: ...
    def get_movie(
        self, provider_id: str, policy: MetadataPolicy | None = None, *, force_refresh: bool = False
    ) -> MediaIdentity: ...
    def search_tv(
        self,
        query: ParseResult,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ) -> Sequence[MediaCandidate]: ...
    def get_tv(
        self, provider_id: str, policy: MetadataPolicy | None = None, *, force_refresh: bool = False
    ) -> MediaIdentity: ...
    def get_season(
        self,
        provider_id: str,
        season: int,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ) -> MediaIdentity: ...
    def get_episode(
        self,
        provider_id: str,
        season: int,
        episode: int,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ) -> MediaIdentity: ...
    def find_by_external_id(
        self,
        source: str,
        external_id: str,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ) -> Sequence[MediaCandidate]: ...
