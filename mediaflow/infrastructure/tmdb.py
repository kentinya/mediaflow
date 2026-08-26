from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from mediaflow.application.metadata import MetadataCache, MetadataCacheKey
from mediaflow.domain.metadata import (
    EpisodeIdentity,
    MediaCandidate,
    MediaIdentity,
    MediaType,
    MetadataError,
    MetadataErrorCode,
    MetadataPolicy,
    ProviderCapabilities,
    RetryPolicy,
)
from mediaflow.domain.parser import ParseResult


@dataclass(frozen=True)
class TMDBConfig:
    access_token: str
    provider_id: str = "tmdb"
    name: str = "The Movie Database"
    base_url: str = "https://api.themoviedb.org/3"
    language: str = "en-US"
    region: str | None = None
    connect_timeout: float = 5
    request_timeout: float = 10
    max_concurrency: int = 4
    retry_count: int = 2
    retry_base_delay: float = 0.1
    retry_max_delay: float = 2
    cache_ttl: float = 3600
    proxy: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if (
            not self.access_token
            or not self.provider_id
            or not self.base_url.startswith("https://")
        ):
            raise ValueError("TMDB token, provider id, and HTTPS base URL are required")
        if min(self.connect_timeout, self.request_timeout, self.max_concurrency) <= 0:
            raise ValueError("TMDB timeout and concurrency values must be positive")
        if (
            self.retry_count < 0
            or self.retry_base_delay < 0
            or self.retry_max_delay < self.retry_base_delay
        ):
            raise ValueError("invalid TMDB retry configuration")

    def __repr__(self) -> str:
        return (
            "TMDBConfig(access_token='***', "
            f"provider_id={self.provider_id!r}, name={self.name!r}, base_url={self.base_url!r}, "
            f"language={self.language!r}, region={self.region!r}, enabled={self.enabled!r})"
        )


class HTTPResponse(Protocol):
    status_code: int
    headers: Any

    def json(self) -> Any: ...


class HTTPTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any],
        headers: dict[str, str],
        timeout: Any,
    ) -> HTTPResponse: ...


class HttpxTransport:
    def __init__(self, config: TMDBConfig) -> None:
        try:
            import httpx
        except ImportError as error:
            raise RuntimeError("TMDBProvider requires the 'tmdb' optional dependency") from error
        self._httpx = httpx
        self._client = httpx.Client(proxy=config.proxy)

    def request(self, method, url, *, params, headers, timeout):
        try:
            return self._client.request(
                method, url, params=params, headers=headers, timeout=timeout
            )
        except self._httpx.TimeoutException as error:
            raise TimeoutError("TMDB request timed out") from error
        except self._httpx.RequestError as error:
            raise OSError("TMDB connection failed") from error


class TMDBClient:
    def __init__(
        self,
        config: TMDBConfig,
        transport: HTTPTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._transport = transport or HttpxTransport(config)
        self._sleep = sleeper
        self._semaphore = threading.BoundedSemaphore(config.max_concurrency)

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        request_timeout: float | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> dict[str, Any]:
        if not self.config.enabled:
            raise MetadataError(MetadataErrorCode.PROVIDER_UNAVAILABLE, "TMDB provider is disabled")
        url = self.config.base_url.rstrip("/") + "/" + path.lstrip("/")
        safe_params = {key: value for key, value in (params or {}).items() if value is not None}
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Accept": "application/json",
        }
        effective_timeout = (
            self.config.request_timeout if request_timeout is None else request_timeout
        )
        retry_count = self.config.retry_count if retry_policy is None else retry_policy.retry_count
        retry_base_delay = (
            self.config.retry_base_delay if retry_policy is None else retry_policy.base_delay
        )
        retry_max_delay = (
            self.config.retry_max_delay if retry_policy is None else retry_policy.max_delay
        )
        last_error: MetadataError | None = None
        for attempt in range(retry_count + 1):
            try:
                with self._semaphore:
                    response = self._transport.request(
                        "GET",
                        url,
                        params=safe_params,
                        headers=headers,
                        timeout=(self.config.connect_timeout, effective_timeout),
                    )
            except (TimeoutError, OSError) as error:
                code = (
                    MetadataErrorCode.TIMEOUT
                    if isinstance(error, TimeoutError)
                    else MetadataErrorCode.CONNECTION_FAILED
                )
                last_error = MetadataError(code, "TMDB request failed", cause=error)
                if attempt >= retry_count:
                    raise last_error from error
                self._sleep(self._delay(attempt, None, retry_base_delay, retry_max_delay))
                continue
            if response.status_code == 429:
                last_error = MetadataError(
                    MetadataErrorCode.RATE_LIMITED, "TMDB rate limit exceeded"
                )
                if attempt >= retry_count:
                    raise last_error
                self._sleep(
                    self._delay(
                        attempt,
                        response.headers.get("Retry-After"),
                        retry_base_delay,
                        retry_max_delay,
                    )
                )
                continue
            if response.status_code in {500, 502, 503, 504}:
                last_error = MetadataError(
                    MetadataErrorCode.PROVIDER_UNAVAILABLE, "TMDB service is unavailable"
                )
                if attempt >= retry_count:
                    raise last_error
                self._sleep(self._delay(attempt, None, retry_base_delay, retry_max_delay))
                continue
            _raise_status(response.status_code)
            try:
                payload = response.json()
            except Exception as error:
                raise MetadataError(
                    MetadataErrorCode.MALFORMED_RESPONSE, "TMDB returned invalid JSON", cause=error
                ) from error
            if not isinstance(payload, dict):
                raise MetadataError(
                    MetadataErrorCode.MALFORMED_RESPONSE,
                    "TMDB returned an unexpected response shape",
                )
            return payload
        assert last_error is not None
        raise last_error

    @staticmethod
    def _delay(
        attempt: int,
        retry_after: str | None,
        retry_base_delay: float,
        retry_max_delay: float,
    ) -> float:
        if retry_after:
            try:
                return min(retry_max_delay, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return min(retry_max_delay, retry_base_delay * (2**attempt))


class TMDBProvider:
    capabilities = ProviderCapabilities(True, True, True, True, True, True, True)

    def __init__(self, client: TMDBClient, cache: MetadataCache | None = None) -> None:
        self._client = client
        self._cache = cache or MetadataCache()

    @property
    def provider_id(self) -> str:
        return self._client.config.provider_id

    def _get(
        self, path: str, params: dict[str, Any] | None, policy: MetadataPolicy
    ) -> dict[str, Any]:
        return self._client.get(
            path,
            params,
            request_timeout=policy.timeout,
            retry_policy=policy.retry_policy,
        )

    def search_movie(
        self,
        query: ParseResult,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ):
        return self._search("movie", query, policy, force_refresh)

    def search_tv(
        self,
        query: ParseResult,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ):
        return self._search("tv", query, policy, force_refresh)

    def _search(
        self, kind: str, query: ParseResult, policy: MetadataPolicy | None, force_refresh: bool
    ):
        policy = policy or MetadataPolicy("tmdb-default", self.provider_id)
        language, region = (
            policy.language or self._client.config.language,
            policy.region or self._client.config.region,
        )
        key = _key(
            self.provider_id,
            f"search_{kind}",
            query=query.title_candidate,
            year=query.year,
            language=language,
            region=region,
        )
        if not force_refresh and (cached := self._cache.get(key)) is not None:
            return cached
        results: list[MediaCandidate] = []
        year_filters = (
            (query.year, None) if kind == "movie" and query.year is not None else (query.year,)
        )
        for year_filter in year_filters:
            for page in range(1, policy.max_search_pages + 1):
                params = {
                    "query": query.title_candidate,
                    "language": language,
                    "page": page,
                    "include_adult": "false",
                }
                if kind == "movie":
                    params.update({"primary_release_year": year_filter, "region": region})
                else:
                    params["first_air_date_year"] = query.year
                payload = self._get(f"search/{kind}", params, policy)
                page_results = payload.get("results")
                if not isinstance(page_results, list):
                    raise MetadataError(
                        MetadataErrorCode.MALFORMED_RESPONSE,
                        "TMDB search results are malformed",
                    )
                for item in page_results:
                    results.append(
                        _candidate(
                            item,
                            MediaType.MOVIE if kind == "movie" else MediaType.TV,
                            self.provider_id,
                            regional_movie_release=kind == "movie" and region is not None,
                        )
                    )
                    if len(results) >= policy.max_candidates:
                        break
                total_pages = payload.get("total_pages", 1)
                if (
                    len(results) >= policy.max_candidates
                    or not isinstance(total_pages, int)
                    or page >= total_pages
                ):
                    break
            if results:
                break
        value = tuple(results)
        ttl = policy.cache_policy.search_ttl if value else policy.cache_policy.negative_ttl
        self._cache.put(key, value, ttl)
        return value

    def get_movie(
        self, provider_id: str, policy: MetadataPolicy | None = None, *, force_refresh: bool = False
    ):
        return self._details("movie", provider_id, policy, force_refresh)

    def get_tv(
        self, provider_id: str, policy: MetadataPolicy | None = None, *, force_refresh: bool = False
    ):
        return self._details("tv", provider_id, policy, force_refresh)

    def _details(
        self, kind: str, provider_id: str, policy: MetadataPolicy | None, force_refresh: bool
    ):
        policy = policy or MetadataPolicy("tmdb-default", self.provider_id)
        language = policy.language or self._client.config.language
        key = _key(self.provider_id, f"details_{kind}", id=provider_id, language=language)
        if not force_refresh and (cached := self._cache.get(key)) is not None:
            return cached
        payload = self._get(
            f"{kind}/{provider_id}",
            {
                "language": language,
                "append_to_response": "alternative_titles,translations,external_ids",
            },
            policy,
        )
        identity = _identity(
            payload, MediaType.MOVIE if kind == "movie" else MediaType.TV, self.provider_id
        )
        self._cache.put(key, identity, policy.cache_policy.details_ttl)
        return identity

    def get_season(
        self,
        provider_id: str,
        season: int,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ):
        policy = policy or MetadataPolicy("tmdb-default", self.provider_id)
        language = policy.language or self._client.config.language
        key = _key(self.provider_id, "season", id=provider_id, season=season, language=language)
        if not force_refresh and (cached := self._cache.get(key)) is not None:
            return cached
        payload = self._get(f"tv/{provider_id}/season/{season}", {"language": language}, policy)
        episodes = payload.get("episodes")
        if not isinstance(episodes, list):
            raise MetadataError(
                MetadataErrorCode.MALFORMED_RESPONSE, "TMDB season episodes are malformed"
            )
        metadata = tuple(_episode(item) for item in episodes)
        identity = MediaIdentity(
            self.provider_id,
            str(provider_id),
            MediaType.TV,
            _required_text(payload, "name"),
            season=season,
            episode_metadata=metadata,
        )
        self._cache.put(key, identity, policy.cache_policy.details_ttl)
        return identity

    def get_episode(
        self,
        provider_id: str,
        season: int,
        episode: int,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ):
        policy = policy or MetadataPolicy("tmdb-default", self.provider_id)
        language = policy.language or self._client.config.language
        key = _key(
            self.provider_id,
            "episode",
            id=provider_id,
            season=season,
            episode=episode,
            language=language,
        )
        if not force_refresh and (cached := self._cache.get(key)) is not None:
            return cached
        payload = self._get(
            f"tv/{provider_id}/season/{season}/episode/{episode}",
            {"language": language},
            policy,
        )
        item = _episode(payload)
        identity = MediaIdentity(
            self.provider_id,
            str(provider_id),
            MediaType.TV,
            item.title,
            season=season,
            episode=episode,
            episodes=(episode,),
            episode_title=item.title,
            episode_metadata=(item,),
        )
        self._cache.put(key, identity, policy.cache_policy.details_ttl)
        return identity

    def find_by_external_id(
        self,
        source: str,
        external_id: str,
        policy: MetadataPolicy | None = None,
        *,
        force_refresh: bool = False,
    ):
        supported = {
            "imdb_id",
            "facebook_id",
            "instagram_id",
            "tvdb_id",
            "tiktok_id",
            "twitter_id",
            "wikidata_id",
            "youtube_id",
        }
        if source not in supported:
            raise MetadataError(
                MetadataErrorCode.UNSUPPORTED_OPERATION,
                "TMDB does not support this external ID source",
            )
        policy = policy or MetadataPolicy("tmdb-default", self.provider_id)
        language = policy.language or self._client.config.language
        key = _key(self.provider_id, "find", source=source, id=external_id, language=language)
        if not force_refresh and (cached := self._cache.get(key)) is not None:
            return cached
        payload = self._get(
            f"find/{external_id}",
            {"external_source": source, "language": language},
            policy,
        )
        candidates = []
        for key_name, media_type in (
            ("movie_results", MediaType.MOVIE),
            ("tv_results", MediaType.TV),
        ):
            values = payload.get(key_name, [])
            if not isinstance(values, list):
                raise MetadataError(
                    MetadataErrorCode.MALFORMED_RESPONSE, "TMDB find results are malformed"
                )
            candidates.extend(_candidate(item, media_type, self.provider_id) for item in values)
        result = tuple(candidates)
        self._cache.put(
            key,
            result,
            policy.cache_policy.search_ttl if result else policy.cache_policy.negative_ttl,
        )
        return result


def _candidate(
    payload: Any,
    media_type: MediaType,
    provider: str,
    *,
    regional_movie_release: bool = False,
) -> MediaCandidate:
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), int):
        raise MetadataError(
            MetadataErrorCode.MALFORMED_RESPONSE, "TMDB candidate is missing an integer id"
        )
    title_key, original_key, date_key = (
        ("title", "original_title", "release_date")
        if media_type is MediaType.MOVIE
        else ("name", "original_name", "first_air_date")
    )
    title = _required_text(payload, title_key)
    date = payload.get(date_key) if isinstance(payload.get(date_key), str) else None
    canonical_date = None if regional_movie_release else date
    regional_date = date if regional_movie_release else None
    return MediaCandidate(
        provider,
        str(payload["id"]),
        media_type,
        title,
        payload.get(original_key) if isinstance(payload.get(original_key), str) else None,
        _year(canonical_date),
        alternative_titles=_alternative_titles(payload, media_type),
        translated_titles=_translated_titles(payload, media_type),
        release_date=date,
        canonical_release_date=canonical_date,
        regional_release_date=regional_date,
        overview=payload.get("overview") if isinstance(payload.get("overview"), str) else None,
        original_language=payload.get("original_language")
        if isinstance(payload.get("original_language"), str)
        else None,
        popularity=float(payload["popularity"])
        if isinstance(payload.get("popularity"), (int, float))
        else None,
        poster_path=payload.get("poster_path")
        if isinstance(payload.get("poster_path"), str)
        else None,
        backdrop_path=payload.get("backdrop_path")
        if isinstance(payload.get("backdrop_path"), str)
        else None,
    )


def _alternative_titles(payload: dict[str, Any], media_type: MediaType) -> tuple[str, ...]:
    """Map provider-supplied aliases when present without requiring another request."""
    raw = payload.get("alternative_titles")
    if isinstance(raw, list):
        return tuple(dict.fromkeys(item for item in raw if isinstance(item, str) and item))
    if not isinstance(raw, dict):
        return ()
    key = "titles" if media_type is MediaType.MOVIE else "results"
    values = raw.get(key, ())
    if not isinstance(values, list):
        return ()
    return tuple(
        dict.fromkeys(
            item["title"]
            for item in values
            if isinstance(item, dict) and isinstance(item.get("title"), str) and item["title"]
        )
    )


def _translated_titles(payload: dict[str, Any], media_type: MediaType) -> tuple[str, ...]:
    raw = payload.get("translations")
    if not isinstance(raw, dict) or not isinstance(raw.get("translations"), list):
        return ()
    title_key = "title" if media_type is MediaType.MOVIE else "name"
    values = []
    for item in raw["translations"]:
        if not isinstance(item, dict) or not isinstance(item.get("data"), dict):
            continue
        title = item["data"].get(title_key)
        if isinstance(title, str) and title.strip():
            values.append(title)
    return tuple(dict.fromkeys(values))


_TMDB_GENRE_NAMES = {
    12: "Adventure",
    14: "Fantasy",
    16: "Animation",
    18: "Drama",
    27: "Horror",
    28: "Action",
    35: "Comedy",
    36: "History",
    37: "Western",
    53: "Thriller",
    80: "Crime",
    99: "Documentary",
    878: "Science Fiction",
    9648: "Mystery",
    10402: "Music",
    10749: "Romance",
    10751: "Family",
    10752: "War",
    10759: "Action & Adventure",
    10762: "Kids",
    10763: "News",
    10764: "Reality",
    10765: "Sci-Fi & Fantasy",
    10766: "Soap",
    10767: "Talk",
    10768: "War & Politics",
    10770: "TV Movie",
}


def _normalized_genre(value: dict[str, Any]) -> str:
    genre_id = value.get("id")
    if isinstance(genre_id, int) and genre_id in _TMDB_GENRE_NAMES:
        return _TMDB_GENRE_NAMES[genre_id]
    name = value.get("name")
    return name.strip() if isinstance(name, str) else ""


def _identity(payload: Any, media_type: MediaType, provider: str) -> MediaIdentity:
    candidate = _candidate(payload, media_type, provider)
    genres = tuple(
        _normalized_genre(item)
        for item in payload.get("genres", [])
        if isinstance(item, dict) and _normalized_genre(item)
    )
    country_key = "production_countries" if media_type is MediaType.MOVIE else "origin_country"
    countries_raw = payload.get(country_key, [])
    countries = tuple(
        item.get("iso_3166_1", "") if isinstance(item, dict) else item
        for item in countries_raw
        if isinstance(item, (dict, str))
    )
    languages_raw = payload.get("spoken_languages", [])
    languages = tuple(
        item.get("iso_639_1", "")
        for item in languages_raw
        if isinstance(item, dict) and item.get("iso_639_1")
    )
    alternatives = _alternative_titles(payload, media_type)
    external = payload.get("external_ids", {})
    external_ids = (
        tuple(
            sorted(
                (key, value) for key, value in external.items() if isinstance(value, str) and value
            )
        )
        if isinstance(external, dict)
        else ()
    )
    return MediaIdentity(
        provider,
        candidate.provider_id,
        media_type,
        candidate.title,
        candidate.original_title,
        candidate.year,
        genres=genres,
        countries=tuple(filter(None, countries)),
        languages=languages,
        alternative_titles=alternatives,
        translated_titles=candidate.translated_titles,
        release_date=candidate.release_date,
        canonical_release_date=candidate.canonical_release_date,
        regional_release_date=candidate.regional_release_date,
        overview=candidate.overview,
        external_ids=external_ids,
        poster_path=candidate.poster_path,
        backdrop_path=candidate.backdrop_path,
    )


def _episode(payload: Any) -> EpisodeIdentity:
    if not isinstance(payload, dict) or not isinstance(payload.get("episode_number"), int):
        raise MetadataError(MetadataErrorCode.MALFORMED_RESPONSE, "TMDB episode is malformed")
    return EpisodeIdentity(
        payload["episode_number"],
        _required_text(payload, "name"),
        payload.get("air_date") if isinstance(payload.get("air_date"), str) else None,
        payload.get("overview") if isinstance(payload.get("overview"), str) else None,
    )


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MetadataError(
            MetadataErrorCode.MALFORMED_RESPONSE, f"TMDB response is missing required field {key!r}"
        )
    return value


def _year(date: str | None) -> int | None:
    if date and len(date) >= 4 and date[:4].isdigit():
        return int(date[:4])
    return None


def _key(provider: str, operation: str, **arguments: Any) -> MetadataCacheKey:
    return MetadataCacheKey(
        provider, operation, tuple(sorted((key, str(value)) for key, value in arguments.items()))
    )


def _raise_status(status: int) -> None:
    mapping = {
        400: MetadataErrorCode.INVALID_REQUEST,
        401: MetadataErrorCode.AUTHENTICATION_FAILED,
        403: MetadataErrorCode.PERMISSION_DENIED,
        404: MetadataErrorCode.NOT_FOUND,
    }
    if status in mapping:
        raise MetadataError(mapping[status], f"TMDB request failed with HTTP {status}")
    if status < 200 or status >= 300:
        raise MetadataError(MetadataErrorCode.UNKNOWN, f"TMDB request failed with HTTP {status}")
