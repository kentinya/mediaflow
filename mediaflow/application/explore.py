"""Read-only Explore application service (Slice 51 / Task 51.1).

One service owns the whole Explore read contract between the API surface and
the deployment provider port:

- it parses and strictly validates one normalized query-string dictionary
  (unknown, duplicate, empty, out-of-range and non-finite values are rejected
  as a bounded ``invalid_request`` before any Provider read);
- it resolves the deployment-supported ``tmdb`` provider lazily and only for
  an Explore read — no Shell/status read ever constructs or contacts a
  Provider, and the organized ``MetadataProvider`` contract is untouched;
- it validates a genre/language filter against the provider's own bounded
  catalog (at most one cached catalog read, never per work) and applies the
  rating-sort default vote floor before calling the port;
- it normalizes provider answers into provider-neutral documents and
  translates every provider failure into one secret-free category with a
  safe next action — the API never sees a TMDB DTO and never sees an upstream
  exception body.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from mediaflow.domain.explore import (
    EXPLORE_MAX_ITEMS,
    EXPLORE_MAX_VOTES,
    EXPLORE_MAX_WORK_ID,
    EXPLORE_MAX_YEAR,
    EXPLORE_PAGE_LIMIT,
    ExploreBrowseQuery,
    ExploreDetail,
    ExploreError,
    ExploreErrorCode,
    ExploreOptions,
    ExplorePage,
    ExploreProvider,
    ExploreSearchQuery,
    ExploreSort,
    is_explore_media_type,
    parse_int_parameter,
    parse_rating_parameter,
    parse_work_id,
    validate_keyword,
    validate_language_code,
)
from mediaflow.domain.metadata import MediaType, MetadataError, MetadataErrorCode
from mediaflow.infrastructure.metadata_provider_bootstrap import (
    MetadataProviderBootstrapError,
)

#: The one deployment provider Explore reads from.
EXPLORE_PROVIDER_ID = "tmdb"

_BROWSE_FIELDS = frozenset(
    {"mediaType", "genreId", "originalLanguage", "year", "minRating", "minVotes", "sort", "page"}
)
_SEARCH_FIELDS = frozenset({"mediaType", "query", "page"})
_OPTIONS_FIELDS = frozenset({"mediaType"})
_SORTS = frozenset({sort.value for sort in ExploreSort})

_MISSING_CREDENTIAL_ACTION = (
    "set TMDB_ACCESS_TOKEN in the deployment environment, restart the service, then reload Explore"
)
_UNCONFIGURED_ACTION = (
    "configure the deployment's TMDB metadata provider, restart the service, then reload Explore"
)


def _invalid(message: str) -> ExploreError:
    return ExploreError(ExploreErrorCode.INVALID_REQUEST, message)


def _read_parameters(
    params: Mapping[str, Sequence[str]],
    allowed: frozenset[str],
    *,
    required: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """One normalized, single-valued view of the raw query dictionary."""

    unknown = sorted(set(params) - allowed)
    if unknown:
        raise _invalid(f"unsupported query parameter {unknown[0]!r}")
    values: dict[str, str] = {}
    for key in sorted(params):
        raw = list(params[key])
        if len(raw) != 1:
            raise _invalid(f"query parameter {key!r} must be specified once")
        values[key] = raw[0]
    missing = sorted(required - set(values))
    if missing:
        raise _invalid(f"query parameter {missing[0]!r} is required")
    return values


def _media_type(raw: str) -> MediaType:
    if not is_explore_media_type(raw):
        raise _invalid("mediaType must be movie or tv")
    return MediaType(raw)


def _translate_provider_error(error: MetadataError) -> ExploreError:
    """One normalized, secret-free category per provider failure family."""

    mapping: dict[MetadataErrorCode, tuple[ExploreErrorCode, str, str]] = {
        MetadataErrorCode.AUTHENTICATION_FAILED: (
            ExploreErrorCode.PROVIDER_AUTHENTICATION,
            "The provider rejected the credential configured for this service.",
            _MISSING_CREDENTIAL_ACTION,
        ),
        MetadataErrorCode.PERMISSION_DENIED: (
            ExploreErrorCode.PROVIDER_PERMISSION,
            "The provider denied access for the configured credential.",
            _MISSING_CREDENTIAL_ACTION,
        ),
        MetadataErrorCode.RATE_LIMITED: (
            ExploreErrorCode.PROVIDER_RATE_LIMITED,
            "The provider is rate limiting requests; nothing was changed.",
            "wait a moment, then retry the same read",
        ),
        MetadataErrorCode.TIMEOUT: (
            ExploreErrorCode.PROVIDER_TIMEOUT,
            "The provider did not answer in time; nothing was changed.",
            "retry the same read",
        ),
        MetadataErrorCode.CONNECTION_FAILED: (
            ExploreErrorCode.PROVIDER_UNAVAILABLE,
            "The provider could not be reached from this service; nothing was changed.",
            "check the service network egress, then retry the same read",
        ),
        MetadataErrorCode.PROVIDER_UNAVAILABLE: (
            ExploreErrorCode.PROVIDER_UNAVAILABLE,
            "The provider service is unavailable; nothing was changed.",
            "retry the same read",
        ),
        MetadataErrorCode.RESPONSE_TOO_LARGE: (
            ExploreErrorCode.PROVIDER_MALFORMED,
            "The provider returned a response beyond the allowed read limit; nothing was changed.",
            "retry the same read; if it persists, the provider or its network path is faulty",
        ),
        MetadataErrorCode.MALFORMED_RESPONSE: (
            ExploreErrorCode.PROVIDER_MALFORMED,
            "The provider returned unusable data; nothing was changed.",
            "retry the same read",
        ),
        MetadataErrorCode.NOT_FOUND: (
            ExploreErrorCode.NOT_FOUND,
            "The requested title does not exist for this provider.",
            "return to the list and pick another title",
        ),
    }
    code, message, next_action = mapping.get(
        error.code,
        (
            ExploreErrorCode.PROVIDER_UNAVAILABLE,
            "The provider could not complete this read; nothing was changed.",
            "retry the same read",
        ),
    )
    return ExploreError(code, message, next_action=next_action)


class ExploreService:
    """The one Explore read boundary: validated query in, document out."""

    def __init__(
        self,
        provider_registry_factory: Callable[[Sequence[str]], object] | None = None,
    ) -> None:
        self._registry_factory = provider_registry_factory

    # -- provider resolution -------------------------------------------------

    def _provider(self) -> ExploreProvider:
        """Resolve the deployment-supported provider on demand, secret-free.

        Resolution happens only inside an Explore read: the factory itself is
        the existing lazy registry bootstrap, so a Shell/status/API-structure
        read never constructs a provider or reads its environment credential.
        """

        if self._registry_factory is None:
            raise ExploreError(
                ExploreErrorCode.PROVIDER_NOT_CONFIGURED,
                "This deployment does not provide the metadata provider Explore reads.",
                next_action=_UNCONFIGURED_ACTION,
            )
        try:
            registry = self._registry_factory((EXPLORE_PROVIDER_ID,))
            provider = registry.resolve(EXPLORE_PROVIDER_ID)  # type: ignore[attr-defined]
        except MetadataProviderBootstrapError as error:
            raise ExploreError(
                ExploreErrorCode.PROVIDER_NOT_CONFIGURED,
                error.message,
                next_action=error.next_action,
            ) from error
        except LookupError as error:
            raise ExploreError(
                ExploreErrorCode.PROVIDER_NOT_CONFIGURED,
                "The metadata provider Explore reads is not configured by this service.",
                next_action=_UNCONFIGURED_ACTION,
            ) from error
        if not isinstance(provider, ExploreProvider):
            raise ExploreError(
                ExploreErrorCode.PROVIDER_NOT_CONFIGURED,
                "The configured metadata provider does not support Explore reads.",
                next_action=_UNCONFIGURED_ACTION,
            )
        return provider

    @staticmethod
    def _call(operation: Callable[[], object]):
        try:
            return operation()
        except MetadataError as error:
            raise _translate_provider_error(error) from error

    # -- reads ---------------------------------------------------------------

    def browse(self, params: Mapping[str, Sequence[str]]) -> dict[str, object]:
        values = _read_parameters(params, _BROWSE_FIELDS)
        media_type = _media_type(values.get("mediaType", "movie"))
        sort_raw = values.get("sort", ExploreSort.POPULAR.value)
        if sort_raw not in _SORTS:
            raise _invalid("sort must be popular, rating or date")
        sort = ExploreSort(sort_raw)
        genre_id = (
            parse_int_parameter(
                values["genreId"], "genreId", minimum=1, maximum=EXPLORE_MAX_WORK_ID
            )
            if "genreId" in values
            else None
        )
        original_language = (
            validate_language_code(values["originalLanguage"])
            if "originalLanguage" in values
            else None
        )
        year = (
            parse_int_parameter(values["year"], "year", minimum=1, maximum=EXPLORE_MAX_YEAR)
            if "year" in values
            else None
        )
        min_rating = (
            parse_rating_parameter(values["minRating"], "minRating")
            if "minRating" in values
            else None
        )
        min_votes = (
            parse_int_parameter(
                values["minVotes"], "minVotes", minimum=0, maximum=EXPLORE_MAX_VOTES
            )
            if "minVotes" in values
            else None
        )
        page = (
            parse_int_parameter(values["page"], "page", minimum=1, maximum=EXPLORE_PAGE_LIMIT)
            if "page" in values
            else 1
        )
        query = ExploreBrowseQuery(
            media_type,
            sort,
            genre_id,
            original_language,
            year,
            min_rating,
            min_votes,
            page,
        )
        provider = self._provider()
        if query.genre_id is not None or query.original_language is not None:
            options: ExploreOptions = self._call(lambda: provider.options(media_type))
            if query.genre_id is not None and query.genre_id not in {
                genre.genre_id for genre in options.genres
            }:
                raise _invalid("genreId does not belong to this media type")
            if query.original_language is not None and query.original_language not in {
                language.code for language in options.languages
            }:
                raise _invalid("originalLanguage is not in the supported catalog")
        page_result: ExplorePage = self._call(lambda: provider.browse(query))
        return _page_document(page_result)

    def search(self, params: Mapping[str, Sequence[str]]) -> dict[str, object]:
        values = _read_parameters(
            params, _SEARCH_FIELDS, required=frozenset({"mediaType", "query"})
        )
        media_type = _media_type(values["mediaType"])
        keyword = validate_keyword(values["query"])
        page = (
            parse_int_parameter(values["page"], "page", minimum=1, maximum=EXPLORE_PAGE_LIMIT)
            if "page" in values
            else 1
        )
        query = ExploreSearchQuery(media_type, keyword, page)
        provider = self._provider()
        page_result: ExplorePage = self._call(lambda: provider.search(query))
        return _page_document(page_result)

    def options(self, params: Mapping[str, Sequence[str]]) -> dict[str, object]:
        values = _read_parameters(params, _OPTIONS_FIELDS, required=frozenset({"mediaType"}))
        media_type = _media_type(values["mediaType"])
        provider = self._provider()
        options: ExploreOptions = self._call(lambda: provider.options(media_type))
        return _options_document(options)

    def detail(self, media_type_raw: str, provider_id_raw: str) -> dict[str, object]:
        media_type = _media_type(media_type_raw)
        provider_id = parse_work_id(provider_id_raw)
        provider = self._provider()
        detail: ExploreDetail = self._call(lambda: provider.detail(media_type, provider_id))
        return _detail_document(detail)


# -- response documents ------------------------------------------------------


def _applied_document(query: ExplorePage) -> dict[str, object]:
    applied: dict[str, object] = {
        "mediaType": query.media_type.value,
        "page": query.page,
    }
    if query.keyword is not None:
        applied["query"] = query.keyword
    else:
        applied["sort"] = query.sort.value
        if query.genre_id is not None:
            applied["genreId"] = query.genre_id
        if query.original_language is not None:
            applied["originalLanguage"] = query.original_language
        if query.year is not None:
            applied["year"] = query.year
        if query.min_rating is not None:
            applied["minRating"] = query.min_rating
        if query.min_votes is not None:
            applied["minVotes"] = query.min_votes
    return applied


def _item_document(item) -> dict[str, object]:
    return {
        "provider": item.provider,
        "providerId": item.provider_id,
        "mediaType": item.media_type.value,
        "title": item.title,
        "originalTitle": item.original_title,
        "year": item.year,
        "releaseDate": item.release_date,
        "voteAverage": item.vote_average,
        "voteCount": item.vote_count,
        "posterPath": item.poster_path,
        "backdropPath": item.backdrop_path,
        "genreIds": list(item.genre_ids),
    }


def _page_document(page: ExplorePage) -> dict[str, object]:
    items = tuple(page.items[:EXPLORE_MAX_ITEMS])
    return {
        "provider": page.provider,
        "mediaType": page.media_type.value,
        "page": page.page,
        "totalPages": page.total_pages,
        "totalResults": page.total_results,
        "hasMore": page.has_more,
        "pageLimit": page.page_limit,
        "applied": _applied_document(page),
        "items": [_item_document(item) for item in items],
    }


def _options_document(options: ExploreOptions) -> dict[str, object]:
    return {
        "provider": options.provider,
        "mediaType": options.media_type.value,
        "genres": [{"id": genre.genre_id, "name": genre.name} for genre in options.genres],
        "languages": [
            {"code": language.code, "name": language.name} for language in options.languages
        ],
    }


def _detail_document(detail: ExploreDetail) -> dict[str, object]:
    return {
        "provider": detail.provider,
        "providerId": detail.provider_id,
        "mediaType": detail.media_type.value,
        "title": detail.title,
        "originalTitle": detail.original_title,
        "year": detail.year,
        "releaseDate": detail.release_date,
        "voteAverage": detail.vote_average,
        "voteCount": detail.vote_count,
        "genres": list(detail.genres),
        "overview": detail.overview,
        "runtime": detail.runtime,
        "firstAirDate": detail.first_air_date,
        "numberOfSeasons": detail.number_of_seasons,
        "posterPath": detail.poster_path,
        "backdropPath": detail.backdrop_path,
        "externalUrl": detail.external_url,
    }


__all__ = ["ExploreService"]
