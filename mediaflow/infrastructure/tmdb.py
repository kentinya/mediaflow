from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from mediaflow.application.metadata import MetadataCache, MetadataCacheKey
from mediaflow.domain.explore import (
    EXPLORE_MAX_ITEMS,
    EXPLORE_MAX_OPTIONS,
    ExploreBrowseQuery,
    ExploreDetail,
    ExploreGenre,
    ExploreItem,
    ExploreLanguage,
    ExploreOptions,
    ExplorePage,
    ExploreSearchQuery,
    ExploreSort,
    safe_image_path,
)
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
        max_response_bytes: int | None = None,
    ) -> HTTPResponse: ...


class _BoundedJsonResponse:
    """One body already read under an explicit byte bound."""

    def __init__(self, status_code: int, headers: Any, body: bytes) -> None:
        self.status_code = status_code
        self.headers = headers
        self._body = body

    def json(self) -> Any:
        return json.loads(self._body)


class HttpxTransport:
    def __init__(self, config: TMDBConfig, *, client: Any | None = None) -> None:
        try:
            import httpx
        except ImportError as error:
            raise RuntimeError("TMDBProvider requires the 'tmdb' optional dependency") from error
        self._httpx = httpx
        # An injected client is a test seam (local fake transport); production
        # construction is unchanged.
        self._client = client if client is not None else httpx.Client(proxy=config.proxy)

    def request(self, method, url, *, params, headers, timeout, max_response_bytes=None):
        if max_response_bytes is None:
            return self._request_unbounded(
                method, url, params=params, headers=headers, timeout=timeout
            )
        return self._request_bounded(
            method, url, params=params, headers=headers, timeout=timeout, limit=max_response_bytes
        )

    def _request_unbounded(self, method, url, *, params, headers, timeout):
        """The historical eager path: byte-for-byte unchanged behavior."""

        try:
            return self._client.request(
                method, url, params=params, headers=headers, timeout=timeout
            )
        except self._httpx.TimeoutException as error:
            raise TimeoutError("TMDB request timed out") from error
        except self._httpx.RequestError as error:
            raise OSError("TMDB connection failed") from error

    def _request_bounded(self, method, url, *, params, headers, timeout, limit):
        """Read at most ``limit`` bytes, including responses with no declared
        Content-Length; an oversized body fails as a terminal provider error
        instead of being buffered whole."""

        try:
            request = self._client.build_request(
                method, url, params=params, headers=headers, timeout=timeout
            )
            response = self._client.send(request, stream=True)
        except self._httpx.TimeoutException as error:
            raise TimeoutError("TMDB request timed out") from error
        except self._httpx.RequestError as error:
            raise OSError("TMDB connection failed") from error
        try:
            declared = response.headers.get("content-length")
            if declared is not None:
                try:
                    if int(declared) > limit:
                        raise MetadataError(
                            MetadataErrorCode.RESPONSE_TOO_LARGE,
                            "TMDB response exceeded the configured read limit",
                        )
                except ValueError:
                    pass
            body = bytearray()
            try:
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        raise MetadataError(
                            MetadataErrorCode.RESPONSE_TOO_LARGE,
                            "TMDB response exceeded the configured read limit",
                        )
            except self._httpx.TimeoutException as error:
                raise TimeoutError("TMDB request timed out") from error
            except self._httpx.RequestError as error:
                raise OSError("TMDB connection failed") from error
            return _BoundedJsonResponse(response.status_code, response.headers, bytes(body))
        finally:
            response.close()


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
        max_response_bytes: int | None = None,
        expect_array: bool = False,
    ) -> Any:
        """One bounded GET; ``max_response_bytes`` is opt-in per caller so the
        historical organize read path keeps its exact transport behavior.
        ``expect_array`` only lets a known top-level JSON array endpoint (the
        TMDB language catalog) pass the object-shape guard."""

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
        transport_options: dict[str, Any] = (
            {} if max_response_bytes is None else {"max_response_bytes": max_response_bytes}
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
                        **transport_options,
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
            if not isinstance(payload, dict) and not (expect_array and isinstance(payload, list)):
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


# The one Explore read locale: Chinese-first with honest provider fallback
# (TMDB returns zh-CN titles/overviews where they exist, original text where
# they do not). It is part of every Explore cache key.
_EXPLORE_LANGUAGE = "zh-CN"
_EXPLORE_LIST_TTL = 300.0
_EXPLORE_DETAIL_TTL = 3600.0
#: The Explore cache is one bounded in-memory TTL cache, never a new platform.
_EXPLORE_CACHE_MAX_ENTRIES = 256
#: The 2 MiB metadata response bound for Explore reads.
_EXPLORE_MAX_RESPONSE_BYTES = 2 * 1024 * 1024

_EXPLORE_SORT_PARAMS: dict[ExploreSort, str] = {
    ExploreSort.POPULAR: "popularity.desc",
    ExploreSort.RATING: "vote_average.desc",
    ExploreSort.DATE: "primary_release_date.desc",
}
_EXPLORE_TV_SORT_PARAMS: dict[ExploreSort, str] = {
    ExploreSort.POPULAR: "popularity.desc",
    ExploreSort.RATING: "vote_average.desc",
    ExploreSort.DATE: "first_air_date.desc",
}

#: Chinese-first display labels for common ISO-639-1 language codes; a code
#: without a label falls back to the provider's real English/native name.
_EXPLORE_LANGUAGE_LABELS: dict[str, str] = {
    "ar": "阿拉伯语",
    "cs": "捷克语",
    "da": "丹麦语",
    "de": "德语",
    "el": "希腊语",
    "en": "英语",
    "es": "西班牙语",
    "fi": "芬兰语",
    "fr": "法语",
    "he": "希伯来语",
    "hi": "印地语",
    "hu": "匈牙利语",
    "id": "印度尼西亚语",
    "it": "意大利语",
    "ja": "日语",
    "ko": "韩语",
    "ms": "马来语",
    "nl": "荷兰语",
    "no": "挪威语",
    "pl": "波兰语",
    "pt": "葡萄牙语",
    "ro": "罗马尼亚语",
    "ru": "俄语",
    "sv": "瑞典语",
    "th": "泰语",
    "tl": "他加禄语",
    "tr": "土耳其语",
    "uk": "乌克兰语",
    "vi": "越南语",
    "zh": "中文",
}
_LANGUAGE_CODE = re.compile(r"[a-z]{2,3}")


class TMDBProvider:
    capabilities = ProviderCapabilities(True, True, True, True, True, True, True)

    def __init__(self, client: TMDBClient, cache: MetadataCache | None = None) -> None:
        self._client = client
        self._cache = cache or MetadataCache()
        # Explore reads keep their own capacity-bounded TTL cache alongside
        # the historical organize cache, which stays byte-identical.
        self._explore_cache = MetadataCache(max_entries=_EXPLORE_CACHE_MAX_ENTRIES)

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

    # -- Explore reads (optional browse capability, Slice 51 Task 51.1) -----
    #
    # These four reads reuse this adapter's client, transport, concurrency,
    # retry and 429 controls plus a dedicated 256-entry TTL cache. They never
    # change the organize ``MetadataProvider`` methods above, and every
    # upstream call carries the explicit 2 MiB response bound.

    def browse(self, query: ExploreBrowseQuery) -> ExplorePage:
        sort_params = (
            _EXPLORE_TV_SORT_PARAMS if query.media_type is MediaType.TV else _EXPLORE_SORT_PARAMS
        )
        params: dict[str, Any] = {
            "language": _EXPLORE_LANGUAGE,
            "page": query.page,
            "include_adult": "false",
            "sort_by": sort_params[query.sort],
        }
        # The vote floor applies to every sort as soon as the operator chose
        # one; the 100-vote default belongs to the rating sort only. The echo
        # (``applied``) and the upstream parameter must describe the same read.
        if query.effective_min_votes is not None:
            params["vote_count.gte"] = str(query.effective_min_votes)
        if query.genre_id is not None:
            params["with_genres"] = str(query.genre_id)
        if query.original_language is not None:
            params["with_original_language"] = query.original_language
        if query.year is not None:
            year_field = (
                "primary_release_year"
                if query.media_type is MediaType.MOVIE
                else "first_air_date_year"
            )
            params[year_field] = str(query.year)
        if query.min_rating is not None:
            params["vote_average.gte"] = _number_param(query.min_rating)
        kind = query.media_type.value
        key = self._explore_key(
            "browse",
            media_type=kind,
            sort=query.sort.value,
            genre_id=query.genre_id,
            original_language=query.original_language,
            year=query.year,
            min_rating=query.min_rating,
            min_votes=query.effective_min_votes,
            page=query.page,
        )
        if (cached := self._explore_cache.get(key)) is not None:
            return cached
        payload = self._explore_get(f"discover/{kind}", params)
        page = _explore_page(
            payload,
            query.media_type,
            self.provider_id,
            page=query.page,
            sort=query.sort,
            genre_id=query.genre_id,
            original_language=query.original_language,
            year=query.year,
            min_rating=query.min_rating,
            min_votes=query.effective_min_votes,
        )
        self._explore_cache.put(key, page, _EXPLORE_LIST_TTL)
        return page

    def search(self, query: ExploreSearchQuery) -> ExplorePage:
        key = self._explore_key(
            "search",
            media_type=query.media_type.value,
            keyword=query.keyword,
            page=query.page,
        )
        if (cached := self._explore_cache.get(key)) is not None:
            return cached
        payload = self._explore_get(
            f"search/{query.media_type.value}",
            {
                "language": _EXPLORE_LANGUAGE,
                "query": query.keyword,
                "page": query.page,
                "include_adult": "false",
            },
        )
        page = _explore_page(
            payload,
            query.media_type,
            self.provider_id,
            page=query.page,
            sort=ExploreSort.POPULAR,
            keyword=query.keyword,
            min_votes=None,
        )
        self._explore_cache.put(key, page, _EXPLORE_LIST_TTL)
        return page

    def detail(self, media_type: MediaType, provider_id: int) -> ExploreDetail:
        key = self._explore_key("detail", media_type=media_type.value, provider_id=provider_id)
        if (cached := self._explore_cache.get(key)) is not None:
            return cached
        payload = self._explore_get(
            f"{media_type.value}/{provider_id}",
            {"language": _EXPLORE_LANGUAGE},
        )
        detail = _explore_detail(payload, media_type, self.provider_id, provider_id)
        self._explore_cache.put(key, detail, _EXPLORE_DETAIL_TTL)
        return detail

    def options(self, media_type: MediaType) -> ExploreOptions:
        key = self._explore_key("options", media_type=media_type.value)
        if (cached := self._explore_cache.get(key)) is not None:
            return cached
        kind = media_type.value
        genre_payload = self._explore_get(f"genre/{kind}/list", {"language": _EXPLORE_LANGUAGE})
        language_payload = self._explore_get("configuration/languages", expect_array=True)
        options = ExploreOptions(
            self.provider_id,
            media_type,
            _explore_genres(genre_payload),
            _explore_languages(language_payload),
        )
        self._explore_cache.put(key, options, _EXPLORE_DETAIL_TTL)
        return options

    def _explore_get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        expect_array: bool = False,
    ) -> Any:
        return self._client.get(
            path,
            params,
            max_response_bytes=_EXPLORE_MAX_RESPONSE_BYTES,
            expect_array=expect_array,
        )

    def _explore_key(self, operation: str, **arguments: Any) -> MetadataCacheKey:
        """One key carrying source instance, locale and every applied value."""

        values: dict[str, Any] = {
            "source": self._client.config.base_url,
            "locale": _EXPLORE_LANGUAGE,
        }
        values.update(arguments)
        return MetadataCacheKey(
            self.provider_id,
            f"explore_{operation}",
            tuple(sorted((name, str(value)) for name, value in values.items())),
        )


def _malformed(message: str) -> MetadataError:
    return MetadataError(MetadataErrorCode.MALFORMED_RESPONSE, message)


def _number_param(value: float) -> str:
    return format(value, "g")


def _explore_page(
    payload: Any,
    media_type: MediaType,
    provider: str,
    *,
    page: int,
    sort: ExploreSort,
    keyword: str | None = None,
    genre_id: int | None = None,
    original_language: str | None = None,
    year: int | None = None,
    min_rating: float | None = None,
    min_votes: int | None = None,
) -> ExplorePage:
    """One bounded provider page; a malformed/over-size page fails safely
    instead of degrading into a believable empty result."""

    if not isinstance(payload, dict):
        raise _malformed("TMDB page is malformed")
    results = payload.get("results")
    if not isinstance(results, list):
        raise _malformed("TMDB page results are malformed")
    total_pages = payload.get("total_pages")
    total_results = payload.get("total_results")
    if (
        not isinstance(total_pages, int)
        or isinstance(total_pages, bool)
        or total_pages < 1
        or not isinstance(total_results, int)
        or isinstance(total_results, bool)
        or total_results < 0
    ):
        raise _malformed("TMDB page totals are malformed")
    items = tuple(_explore_item(raw, media_type, provider) for raw in results[:EXPLORE_MAX_ITEMS])
    return ExplorePage(
        provider,
        media_type,
        page,
        total_pages,
        total_results,
        items,
        sort,
        genre_id=genre_id,
        original_language=original_language,
        year=year,
        min_rating=min_rating,
        min_votes=min_votes,
        keyword=keyword,
    )


def _explore_text(payload: dict[str, Any], key: str, *, required: bool) -> str | None:
    value = payload.get(key)
    if value is None or value == "":
        if required:
            raise _malformed(f"TMDB item is missing required field {key!r}")
        return None
    if not isinstance(value, str):
        raise _malformed(f"TMDB item field {key!r} is malformed")
    return value


def _explore_item(payload: Any, media_type: MediaType, provider: str) -> ExploreItem:
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), int):
        raise _malformed("TMDB item is missing an integer id")
    identifier = payload["id"]
    if isinstance(identifier, bool) or identifier < 1:
        raise _malformed("TMDB item id is out of range")
    title_key, original_key, date_key = (
        ("title", "original_title", "release_date")
        if media_type is MediaType.MOVIE
        else ("name", "original_name", "first_air_date")
    )
    title = _explore_text(payload, title_key, required=True)
    original = _explore_text(payload, original_key, required=False)
    release_date = _explore_text(payload, date_key, required=False)
    vote_count = payload.get("vote_count")
    if not isinstance(vote_count, int) or isinstance(vote_count, bool) or vote_count < 0:
        raise _malformed("TMDB item vote_count is malformed")
    vote_average: float | None
    raw_average = payload.get("vote_average")
    if vote_count == 0:
        # Unrated means unrated: never publish a fabricated 0-point score.
        vote_average = None
    elif (
        not isinstance(raw_average, (int, float))
        or isinstance(raw_average, bool)
        or not (0 <= float(raw_average) <= 10)
    ):
        raise _malformed("TMDB item vote_average is malformed")
    else:
        vote_average = float(raw_average)
    genre_ids_raw = payload.get("genre_ids")
    if genre_ids_raw is None:
        genre_ids: tuple[int, ...] = ()
    elif isinstance(genre_ids_raw, list) and all(
        isinstance(value, int) and not isinstance(value, bool) for value in genre_ids_raw
    ):
        genre_ids = tuple(dict.fromkeys(genre_ids_raw))
    else:
        raise _malformed("TMDB item genre_ids are malformed")
    return ExploreItem(
        provider,
        str(identifier),
        media_type,
        title,  # type: ignore[arg-type]
        original,
        _year(release_date),
        release_date,
        vote_average,
        vote_count,
        safe_image_path(payload.get("poster_path")),
        safe_image_path(payload.get("backdrop_path")),
        genre_ids,
    )


def _explore_detail(
    payload: Any, media_type: MediaType, provider: str, expected_id: int
) -> ExploreDetail:
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), int):
        raise _malformed("TMDB detail is missing an integer id")
    if payload["id"] != expected_id:
        raise _malformed("TMDB detail id does not match the requested work")
    title_key, original_key, date_key = (
        ("title", "original_title", "release_date")
        if media_type is MediaType.MOVIE
        else ("name", "original_name", "first_air_date")
    )
    title = _explore_text(payload, title_key, required=True)
    original = _explore_text(payload, original_key, required=False)
    release_date = _explore_text(payload, date_key, required=False)
    overview = _explore_text(payload, "overview", required=False)
    vote_count = payload.get("vote_count")
    if not isinstance(vote_count, int) or isinstance(vote_count, bool) or vote_count < 0:
        raise _malformed("TMDB detail vote_count is malformed")
    raw_average = payload.get("vote_average")
    vote_average: float | None = None
    if vote_count > 0:
        if not isinstance(raw_average, (int, float)) or isinstance(raw_average, bool):
            raise _malformed("TMDB detail vote_average is malformed")
        if not (0 <= float(raw_average) <= 10):
            raise _malformed("TMDB detail vote_average is malformed")
        vote_average = float(raw_average)
    genres_raw = payload.get("genres")
    if not isinstance(genres_raw, list):
        raise _malformed("TMDB detail genres are malformed")
    genres: list[str] = []
    for entry in genres_raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise _malformed("TMDB detail genre is malformed")
        name = entry["name"].strip()
        if name and name not in genres:
            genres.append(name)
    runtime = _explore_optional_int(payload, "runtime")
    seasons = _explore_optional_int(payload, "number_of_seasons")
    episodes = _explore_optional_int(payload, "number_of_episodes")
    first_air = (
        _explore_text(payload, "first_air_date", required=False)
        if media_type is MediaType.TV
        else None
    )
    return ExploreDetail(
        provider,
        str(expected_id),
        media_type,
        title,  # type: ignore[arg-type]
        original,
        _year(release_date),
        release_date,
        vote_average,
        vote_count,
        tuple(genres),
        overview,
        runtime,
        first_air,
        seasons,
        episodes,
        safe_image_path(payload.get("poster_path")),
        safe_image_path(payload.get("backdrop_path")),
        f"https://www.themoviedb.org/{media_type.value}/{expected_id}",
    )


def _explore_optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _malformed(f"TMDB detail {key} is malformed")
    return value


def _explore_genres(payload: Any) -> tuple[ExploreGenre, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("genres"), list):
        raise _malformed("TMDB genre catalog is malformed")
    genres: list[ExploreGenre] = []
    seen: set[int] = set()
    for entry in payload["genres"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), int):
            raise _malformed("TMDB genre catalog entry is malformed")
        genre_id = entry["id"]
        name = entry.get("name")
        if isinstance(genre_id, bool) or genre_id < 1 or not isinstance(name, str):
            raise _malformed("TMDB genre catalog entry is malformed")
        cleaned = name.strip()
        if not cleaned or genre_id in seen:
            continue
        seen.add(genre_id)
        genres.append(ExploreGenre(genre_id, cleaned))
        if len(genres) >= EXPLORE_MAX_OPTIONS:
            break
    return tuple(genres)


def _explore_languages(payload: Any) -> tuple[ExploreLanguage, ...]:
    if not isinstance(payload, list):
        raise _malformed("TMDB language catalog is malformed")
    languages: list[ExploreLanguage] = []
    seen: set[str] = set()
    for entry in payload:
        if not isinstance(entry, dict):
            raise _malformed("TMDB language catalog entry is malformed")
        code = entry.get("iso_639_1")
        if not isinstance(code, str) or not _LANGUAGE_CODE.fullmatch(code) or code in seen:
            continue
        # Chinese label first; otherwise the provider's own real English or
        # native name; an entry with no displayable name is not published.
        english = entry.get("english_name")
        native = entry.get("name")
        label = _EXPLORE_LANGUAGE_LABELS.get(code)
        if label is None and isinstance(english, str) and english.strip():
            label = english.strip()
        if label is None and isinstance(native, str) and native.strip():
            label = native.strip()
        if label is None:
            continue
        seen.add(code)
        languages.append(ExploreLanguage(code, label))
        if len(languages) >= EXPLORE_MAX_OPTIONS:
            break
    return tuple(languages)


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
