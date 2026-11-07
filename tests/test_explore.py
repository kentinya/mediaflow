from __future__ import annotations

import unittest
from dataclasses import replace

from mediaflow.application.explore import ExploreService
from mediaflow.application.metadata import (
    MetadataCache,
    MetadataCacheKey,
    MetadataProviderRegistry,
)
from mediaflow.domain.explore import (
    EXPLORE_MAX_ITEMS,
    ExploreBrowseQuery,
    ExploreError,
    ExploreErrorCode,
    ExploreSearchQuery,
    ExploreSort,
    safe_image_path,
)
from mediaflow.domain.metadata import MediaType, MetadataError, MetadataErrorCode
from mediaflow.infrastructure.metadata_provider_bootstrap import (
    LazyMetadataProviderRegistryFactory,
    metadata_provider_registry_from_environment,
)
from mediaflow.infrastructure.tmdb import (
    _EXPLORE_MAX_RESPONSE_BYTES,
    TMDBClient,
    TMDBConfig,
    TMDBProvider,
)

TOKEN = "explore-secret-token"


class FakeResponse:
    def __init__(self, status: int, payload=None, headers=None, json_error=None) -> None:
        self.status_code = status
        self.payload = payload
        self.headers = headers or {}
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class ScriptedTransport:
    """Route-aware fake transport recording every bounded read call.

    Route values are a plain payload dict (200), a ``FakeResponse`` (any
    status) or an ``Exception`` (raised); an unknown route answers 404.
    """

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.calls: list[dict[str, object]] = []

    def request(self, method, url, *, params, headers, timeout, max_response_bytes=None):
        path = url.split("/3/", 1)[-1] if "/3/" in url else url
        self.calls.append(
            {
                "method": method,
                "path": path,
                "params": dict(params),
                "headers": dict(headers),
                "timeout": timeout,
                "max_response_bytes": max_response_bytes,
            }
        )
        result = self.routes.get(path, FakeResponse(404, {}))
        if isinstance(result, Exception):
            raise result
        if isinstance(result, FakeResponse):
            return result
        return FakeResponse(200, result)


class LegacyTransport:
    """Historical signature without any bounded-read keyword."""

    def __init__(self) -> None:
        self.calls = 0

    def request(self, method, url, *, params, headers, timeout):
        self.calls += 1
        return FakeResponse(200, {"results": [], "total_pages": 1, "total_results": 0})


def movie_item(identifier: int, title: str, *, votes: float = 8.4, count: int = 120) -> dict:
    return {
        "id": identifier,
        "title": title,
        "original_title": title,
        "release_date": "2020-05-01",
        "vote_average": votes,
        "vote_count": count,
        "genre_ids": [28, 878],
        "poster_path": f"/poster{identifier}.jpg",
        "backdrop_path": f"/backdrop{identifier}.jpg",
    }


GENRE_PAYLOAD = {
    "genres": [
        {"id": 28, "name": "动作"},
        {"id": 878, "name": "科幻"},
        {"id": 18, "name": "剧情"},
    ]
}
LANGUAGE_PAYLOAD = [
    {"iso_639_1": "zh", "english_name": "Chinese", "name": "中文"},
    {"iso_639_1": "en", "english_name": "English", "name": "English"},
    {"iso_639_1": "xx", "english_name": "", "name": ""},
    {"iso_639_1": "ja", "english_name": "Japanese", "name": "日本語"},
    {"iso_639_1": "fo", "english_name": "Faroese", "name": "føroyskt"},
]


def routes_for_movie_browse() -> dict[str, object]:
    return {
        "discover/movie": {
            "page": 1,
            "total_pages": 3,
            "total_results": 42,
            "results": [movie_item(101, "Alpha"), movie_item(102, "Beta", count=0, votes=0)],
        },
        "genre/movie/list": GENRE_PAYLOAD,
        "genre/tv/list": GENRE_PAYLOAD,
        "configuration/languages": LANGUAGE_PAYLOAD,
        "discover/tv": {
            "page": 1,
            "total_pages": 2,
            "total_results": 10,
            "results": [
                {
                    "id": 900,
                    "name": "Alpha Show",
                    "original_name": "Alpha",
                    "first_air_date": "2019-01-15",
                    "vote_average": 7.5,
                    "vote_count": 40,
                    "genre_ids": [18],
                    "poster_path": None,
                }
            ],
        },
        "search/movie": {
            "page": 1,
            "total_pages": 1,
            "total_results": 1,
            "results": [movie_item(7, "Matrix")],
        },
        "movie/603": {
            "id": 603,
            "title": "The Matrix",
            "original_title": "The Matrix",
            "release_date": "1999-03-31",
            "vote_average": 8.2,
            "vote_count": 23000,
            "genres": [{"id": 878, "name": "科幻"}],
            "overview": "黑客帝国简介",
            "runtime": 136,
            "poster_path": "/matrix.jpg",
            "backdrop_path": "/matrix-bg.jpg",
        },
    }


def make_provider(
    routes: dict[str, object], **config_changes
) -> tuple[TMDBProvider, ScriptedTransport]:
    transport = ScriptedTransport(routes)
    config = replace(TMDBConfig(TOKEN), **config_changes)
    return TMDBProvider(TMDBClient(config, transport)), transport


def make_with_sequence(responses: list[object]):
    class SequenceTransport:
        def __init__(self) -> None:
            self.calls = []
            self._responses = list(responses)

        def request(self, method, url, *, params, headers, timeout, max_response_bytes=None):
            self.calls.append(url.rsplit("/", 1)[-1])
            value = self._responses.pop(0)
            if isinstance(value, Exception):
                raise value
            return value if isinstance(value, FakeResponse) else FakeResponse(200, value)

    transport = SequenceTransport()
    return TMDBProvider(TMDBClient(TMDBConfig(TOKEN), transport)), transport


class ExploreDomainTests(unittest.TestCase):
    def test_image_path_contract_accepts_only_one_safe_segment(self) -> None:
        self.assertEqual(safe_image_path("/abc123.jpg"), "/abc123.jpg")
        for value in (
            "https://image.tmdb.org/t/p/w342/x.jpg",
            "//evil.example/x.jpg",
            "/../secret.jpg",
            "/%2e%2e/x.jpg",
            "/x.jpg?token=1",
            "/x.jpg#frag",
            "/a/b.jpg",
            "/",
            "",
            None,
            5,
            "/with space.jpg",
            "/x" * 400,
        ):
            self.assertIsNone(safe_image_path(value), value)

    def test_browse_query_limits_and_defaults(self) -> None:
        default = ExploreBrowseQuery(MediaType.MOVIE)
        self.assertEqual(default.sort, ExploreSort.POPULAR)
        self.assertIsNone(default.effective_min_votes)
        rating = ExploreBrowseQuery(MediaType.MOVIE, ExploreSort.RATING)
        self.assertEqual(rating.effective_min_votes, 100)
        explicit = ExploreBrowseQuery(MediaType.MOVIE, ExploreSort.RATING, min_votes=250)
        self.assertEqual(explicit.effective_min_votes, 250)
        for invalid in (
            lambda: ExploreBrowseQuery(MediaType.MOVIE, page=0),
            lambda: ExploreBrowseQuery(MediaType.MOVIE, page=501),
            lambda: ExploreBrowseQuery(MediaType.MOVIE, year=0),
            lambda: ExploreBrowseQuery(MediaType.MOVIE, year=10000),
            lambda: ExploreBrowseQuery(MediaType.MOVIE, min_rating=float("nan")),
            lambda: ExploreBrowseQuery(MediaType.MOVIE, min_rating=10.1),
            lambda: ExploreBrowseQuery(MediaType.MOVIE, min_votes=-1),
            lambda: ExploreBrowseQuery(MediaType.MOVIE, min_votes=1_000_000_001),
            lambda: ExploreSearchQuery(MediaType.MOVIE, ""),
            lambda: ExploreSearchQuery(MediaType.MOVIE, "x" * 201),
            lambda: ExploreSearchQuery(MediaType.MOVIE, "bad\nkeyword"),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ExploreError):
                invalid()


class TMDBExploreAdapterTests(unittest.TestCase):
    def test_browse_maps_to_official_discover_parameters_and_bounds_items(self) -> None:
        provider, transport = make_provider(routes_for_movie_browse())
        page = provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["path"], "discover/movie")
        self.assertEqual(call["params"]["language"], "zh-CN")
        self.assertEqual(call["params"]["sort_by"], "popularity.desc")
        self.assertEqual(call["params"]["include_adult"], "false")
        self.assertEqual(call["params"]["page"], 1)
        self.assertEqual(call["max_response_bytes"], _EXPLORE_MAX_RESPONSE_BYTES)
        self.assertEqual(call["headers"]["Authorization"], f"Bearer {TOKEN}")
        self.assertEqual(page.total_results, 42)
        self.assertEqual(page.total_pages, 3)
        self.assertTrue(page.has_more)
        self.assertEqual([item.provider_id for item in page.items], ["101", "102"])
        # An unrated work never publishes a fabricated score.
        self.assertIsNone(page.items[1].vote_average)
        self.assertEqual(page.items[0].poster_path, "/poster101.jpg")

    def test_rating_and_date_sorts_carry_their_real_filters(self) -> None:
        provider, transport = make_provider(routes_for_movie_browse())
        provider.browse(ExploreBrowseQuery(MediaType.MOVIE, ExploreSort.RATING, min_rating=7.5))
        params = transport.calls[-1]["params"]
        self.assertEqual(params["sort_by"], "vote_average.desc")
        self.assertEqual(params["vote_count.gte"], "100")
        self.assertEqual(params["vote_average.gte"], "7.5")
        provider.browse(
            ExploreBrowseQuery(
                MediaType.MOVIE, ExploreSort.DATE, year=2020, genre_id=28, original_language="en"
            )
        )
        params = transport.calls[-1]["params"]
        self.assertEqual(params["sort_by"], "primary_release_date.desc")
        self.assertEqual(params["primary_release_year"], "2020")
        self.assertEqual(params["with_genres"], "28")
        self.assertEqual(params["with_original_language"], "en")
        provider.browse(ExploreBrowseQuery(MediaType.TV, ExploreSort.DATE, year=2019))
        params = transport.calls[-1]["params"]
        self.assertEqual(params["sort_by"], "first_air_date.desc")
        self.assertEqual(params["first_air_date_year"], "2019")

    def test_search_reads_one_page_with_no_explore_filters(self) -> None:
        routes = {
            "search/movie": {
                "page": 1,
                "total_pages": 1,
                "total_results": 1,
                "results": [movie_item(7, "Matrix")],
            },
        }
        provider, transport = make_provider(routes)
        page = provider.search(ExploreSearchQuery(MediaType.MOVIE, "matrix"))
        call = transport.calls[0]
        self.assertEqual(call["path"], "search/movie")
        self.assertEqual(call["params"]["query"], "matrix")
        self.assertEqual(call["params"]["language"], "zh-CN")
        self.assertNotIn("sort_by", call["params"])
        self.assertNotIn("with_genres", call["params"])
        self.assertEqual(page.keyword, "matrix")

    def test_options_catalog_is_bounded_with_chinese_first_labels(self) -> None:
        provider, transport = make_provider(routes_for_movie_browse())
        options = provider.options(MediaType.MOVIE)
        self.assertEqual(transport.calls[0]["path"], "genre/movie/list")
        self.assertEqual(transport.calls[1]["path"], "configuration/languages")
        self.assertEqual([genre.name for genre in options.genres], ["动作", "科幻", "剧情"])
        labels = {language.code: language.name for language in options.languages}
        # Chinese label first, the provider's real name where none exists.
        self.assertEqual(labels["zh"], "中文")
        self.assertEqual(labels["en"], "英语")
        self.assertEqual(labels["ja"], "日语")
        self.assertEqual(labels["fo"], "Faroese")
        self.assertNotIn("xx", labels)

    def test_cache_hits_key_isolation_source_isolation_and_capacity(self) -> None:
        provider, transport = make_provider(routes_for_movie_browse())
        provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        self.assertEqual(len(transport.calls), 1)
        provider.browse(ExploreBrowseQuery(MediaType.MOVIE, page=2))
        self.assertEqual(len(transport.calls), 2)
        other_provider, other_transport = make_provider(
            routes_for_movie_browse(), base_url="https://other.example/3"
        )
        other_provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        self.assertEqual(len(other_transport.calls), 1)
        # Capacity 256: the oldest entry is evicted, so page 1 re-reads while
        # a recent page is still a cache hit.
        for page in range(3, 258):
            provider.browse(ExploreBrowseQuery(MediaType.MOVIE, page=page))
        self.assertEqual(len(transport.calls), 257)
        provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        self.assertEqual(len(transport.calls), 258)
        provider.browse(ExploreBrowseQuery(MediaType.MOVIE, page=100))
        self.assertEqual(len(transport.calls), 258)

    def test_malformed_pages_fail_safely_and_oversized_reads_are_terminal(self) -> None:
        provider, transport = make_provider({"discover/movie": {"results": "junk"}})
        with self.assertRaises(MetadataError) as caught:
            provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        self.assertEqual(caught.exception.code, MetadataErrorCode.MALFORMED_RESPONSE)
        self.assertEqual(len(transport.calls), 1)

        too_large = MetadataError(
            MetadataErrorCode.RESPONSE_TOO_LARGE,
            "TMDB response exceeded the configured read limit",
        )
        provider, transport = make_provider({"discover/movie": too_large})
        with self.assertRaises(MetadataError) as caught:
            provider.browse(ExploreBrowseQuery(MediaType.MOVIE, page=9))
        self.assertEqual(caught.exception.code, MetadataErrorCode.RESPONSE_TOO_LARGE)
        # Terminal: the bounded read never retries an oversized body.
        self.assertEqual(len(transport.calls), 1)

    def test_upstream_status_errors_keep_their_retry_semantics(self) -> None:
        delays: list[float] = []
        transport = ScriptedTransport(
            {"discover/movie": FakeResponse(429, {}, {"Retry-After": "0.5"})}
        )
        client = TMDBClient(replace(TMDBConfig(TOKEN), retry_count=2), transport, delays.append)
        provider = TMDBProvider(client)
        with self.assertRaises(MetadataError) as caught:
            provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        self.assertEqual(caught.exception.code, MetadataErrorCode.RATE_LIMITED)
        self.assertEqual(len(transport.calls), 3)
        self.assertEqual(delays, [0.5, 0.5])

        # Temporary 5xx then success reuses the same bounded call shape.
        routes = routes_for_movie_browse()
        sequence = [FakeResponse(503, {}), FakeResponse(503, {}), routes["discover/movie"]]
        provider, transport = make_with_sequence(sequence)
        page = provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        self.assertEqual(len(transport.calls), 3)
        self.assertEqual(page.total_results, 42)

    def test_detail_identity_includes_media_type_and_normalizes_fields(self) -> None:
        routes = routes_for_movie_browse()
        routes["tv/603"] = {
            "id": 603,
            "name": "Alpha Show",
            "original_name": "Alpha",
            "first_air_date": "2019-02-01",
            "vote_average": 7.1,
            "vote_count": 10,
            "genres": [{"id": 18, "name": "剧情"}],
            "overview": "剧集简介",
            "number_of_seasons": 3,
            "poster_path": "/show.jpg",
        }
        provider, transport = make_provider(routes)
        show = provider.detail(MediaType.TV, 603)
        movie = provider.detail(MediaType.MOVIE, 603)
        self.assertEqual([call["path"] for call in transport.calls], ["tv/603", "movie/603"])
        self.assertEqual(movie.title, "The Matrix")
        self.assertEqual(movie.genres, ("科幻",))
        self.assertEqual(movie.runtime, 136)
        self.assertEqual(movie.year, 1999)
        self.assertEqual(movie.external_url, "https://www.themoviedb.org/movie/603")
        self.assertEqual(show.title, "Alpha Show")
        self.assertEqual(show.number_of_seasons, 3)
        self.assertIsNone(show.runtime)
        self.assertEqual(show.external_url, "https://www.themoviedb.org/tv/603")

    def test_real_empty_page_and_missing_detail(self) -> None:
        routes = {
            "discover/movie": {"page": 1, "total_pages": 1, "total_results": 0, "results": []},
            "movie/404": FakeResponse(404, {}),
        }
        provider, _ = make_provider(routes)
        page = provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        self.assertEqual(page.items, ())
        self.assertEqual(page.total_results, 0)
        self.assertFalse(page.has_more)
        with self.assertRaises(MetadataError) as caught:
            provider.detail(MediaType.MOVIE, 404)
        self.assertEqual(caught.exception.code, MetadataErrorCode.NOT_FOUND)

    def test_detail_id_mismatch_is_malformed(self) -> None:
        routes = {"movie/10": dict(routes_for_movie_browse()["movie/603"])}
        provider, _ = make_provider(routes)
        with self.assertRaises(MetadataError) as caught:
            provider.detail(MediaType.MOVIE, 10)
        self.assertEqual(caught.exception.code, MetadataErrorCode.MALFORMED_RESPONSE)

    def test_responses_are_capped_at_twenty_items(self) -> None:
        routes = {
            "discover/movie": {
                "page": 1,
                "total_pages": 5,
                "total_results": 100,
                "results": [movie_item(index, f"Work {index}") for index in range(1, 31)],
            }
        }
        provider, _ = make_provider(routes)
        page = provider.browse(ExploreBrowseQuery(MediaType.MOVIE))
        self.assertEqual(len(page.items), EXPLORE_MAX_ITEMS)

    def test_organize_reads_keep_their_legacy_transport_signature(self) -> None:
        transport = LegacyTransport()
        client = TMDBClient(TMDBConfig(TOKEN), transport)
        payload = client.get("search/movie", {"query": "x"})
        self.assertEqual(payload["total_pages"], 1)
        self.assertEqual(transport.calls, 1)

    def test_bounded_transport_rejects_declared_and_streamed_oversize(self) -> None:
        import httpx

        from mediaflow.infrastructure.tmdb import HttpxTransport

        limit = _EXPLORE_MAX_RESPONSE_BYTES

        def declared_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x" * (limit + 1))

        declared = HttpxTransport(
            TMDBConfig(TOKEN), client=httpx.Client(transport=httpx.MockTransport(declared_handler))
        )
        with self.assertRaises(MetadataError) as caught:
            declared.request(
                "GET",
                "https://api.themoviedb.org/3/discover/movie",
                params={},
                headers={},
                timeout=(5, 10),
                max_response_bytes=limit,
            )
        self.assertEqual(caught.exception.code, MetadataErrorCode.RESPONSE_TOO_LARGE)

        def streaming_handler(request: httpx.Request) -> httpx.Response:
            response = httpx.Response(200, content=b"y" * (limit + 512))
            # Simulate a chunked/unknown-length body: no declared length at
            # all, so only the streamed accumulation can bound the read.
            response.headers.pop("content-length", None)
            return response

        streaming = HttpxTransport(
            TMDBConfig(TOKEN),
            client=httpx.Client(transport=httpx.MockTransport(streaming_handler)),
        )
        with self.assertRaises(MetadataError) as caught:
            streaming.request(
                "GET",
                "https://api.themoviedb.org/3/discover/movie",
                params={},
                headers={},
                timeout=(5, 10),
                max_response_bytes=limit,
            )
        self.assertEqual(caught.exception.code, MetadataErrorCode.RESPONSE_TOO_LARGE)

        def ok_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b'{"total_pages": 1}')

        ok = HttpxTransport(
            TMDBConfig(TOKEN), client=httpx.Client(transport=httpx.MockTransport(ok_handler))
        )
        response = ok.request(
            "GET",
            "https://api.themoviedb.org/3/discover/movie",
            params={},
            headers={},
            timeout=(5, 10),
            max_response_bytes=limit,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"total_pages": 1})


class ExploreServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider, self.transport = make_provider(routes_for_movie_browse())
        self.factory_calls = 0
        self.requested: tuple[str, ...] = ()
        self.service = ExploreService(self._factory)

    def _factory(self, provider_ids):
        self.factory_calls += 1
        self.requested = tuple(provider_ids)
        return MetadataProviderRegistry((self.provider,))

    def test_success_document_and_applied_defaults(self) -> None:
        document = self.service.browse({})
        self.assertEqual(self.requested, ("tmdb",))
        self.assertEqual(document["provider"], "tmdb")
        self.assertEqual(document["mediaType"], "movie")
        self.assertEqual(document["page"], 1)
        self.assertEqual(document["totalPages"], 3)
        self.assertEqual(document["totalResults"], 42)
        self.assertTrue(document["hasMore"])
        self.assertEqual(document["pageLimit"], 500)
        self.assertEqual(document["applied"], {"mediaType": "movie", "page": 1, "sort": "popular"})
        rating = self.service.browse({"sort": ["rating"]})
        self.assertEqual(rating["applied"]["minVotes"], 100)
        self.assertEqual(rating["items"][0]["providerId"], "101")

    def test_invalid_parameters_are_rejected_before_provider_resolution(self) -> None:
        cases = [
            {"unknown": ["1"]},
            {"page": ["1", "2"]},
            {"page": ["0"]},
            {"page": ["501"]},
            {"page": ["abc"]},
            {"mediaType": ["anime"]},
            {"sort": ["random"]},
            {"year": ["0"]},
            {"year": ["10000"]},
            {"minRating": ["nan"]},
            {"minRating": ["11"]},
            {"minVotes": ["-1"]},
            {"genreId": ["0"]},
            {"originalLanguage": ["EN"]},
            {"genreId": [""]},
            {"mediaType": [""]},
        ]
        for params in cases:
            with self.subTest(params=params), self.assertRaises(ExploreError) as caught:
                self.service.browse(params)
            self.assertEqual(caught.exception.code, ExploreErrorCode.INVALID_REQUEST)
        self.assertEqual(self.factory_calls, 0)

    def test_search_requires_explicit_type_and_keyword_only(self) -> None:
        with self.assertRaises(ExploreError):
            self.service.search({"query": ["matrix"]})
        allowed = self.service.search({"mediaType": ["movie"], "query": ["matrix"]})
        self.assertEqual(allowed["applied"], {"mediaType": "movie", "page": 1, "query": "matrix"})
        with self.assertRaises(ExploreError) as caught:
            self.service.search(
                {"mediaType": ["movie"], "query": ["m"], "sort": ["rating"], "year": ["2020"]}
            )
        self.assertEqual(caught.exception.code, ExploreErrorCode.INVALID_REQUEST)

    def test_filter_membership_is_validated_against_the_catalog(self) -> None:
        with self.assertRaises(ExploreError) as caught:
            self.service.browse({"genreId": ["9999"]})
        self.assertEqual(caught.exception.code, ExploreErrorCode.INVALID_REQUEST)
        with self.assertRaises(ExploreError) as caught:
            self.service.browse({"originalLanguage": ["kw"]})
        self.assertEqual(caught.exception.code, ExploreErrorCode.INVALID_REQUEST)
        document = self.service.browse({"genreId": ["28"], "originalLanguage": ["en"]})
        self.assertEqual(document["applied"]["genreId"], 28)
        self.assertEqual(document["applied"]["originalLanguage"], "en")

    def test_catalog_requests_do_not_grow_with_work_count(self) -> None:
        self.service.browse({"genreId": ["28"]})
        first = len(self.transport.calls)
        self.service.browse({"genreId": ["878"]})
        second = len(self.transport.calls)
        self.assertEqual(first, 3)  # browse + genre + languages once
        self.assertEqual(second, 4)  # only the new browse page after that

    def test_upstream_failures_are_translated_to_bounded_categories(self) -> None:
        mapping = [
            (FakeResponse(401, {}), ExploreErrorCode.PROVIDER_AUTHENTICATION),
            (FakeResponse(403, {}), ExploreErrorCode.PROVIDER_PERMISSION),
            (FakeResponse(404, {}), ExploreErrorCode.NOT_FOUND),
            (TimeoutError("boom"), ExploreErrorCode.PROVIDER_TIMEOUT),
            (OSError("conn"), ExploreErrorCode.PROVIDER_UNAVAILABLE),
            (FakeResponse(503, {}), ExploreErrorCode.PROVIDER_UNAVAILABLE),
        ]
        for failure, code in mapping:
            with self.subTest(failure=failure):
                provider, _ = make_provider({"discover/movie": failure})
                service = ExploreService(lambda ids: MetadataProviderRegistry((provider,)))
                with self.assertRaises(ExploreError) as caught:
                    service.browse({})
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn(TOKEN, caught.exception.message)
                self.assertTrue(caught.exception.next_action)

    def test_missing_credential_guidance_is_secret_free(self) -> None:
        factory = LazyMetadataProviderRegistryFactory(
            lambda ids: metadata_provider_registry_from_environment(ids, environ={})
        )
        service = ExploreService(factory)
        with self.assertRaises(ExploreError) as caught:
            service.browse({})
        self.assertEqual(caught.exception.code, ExploreErrorCode.PROVIDER_NOT_CONFIGURED)
        self.assertIn("TMDB_ACCESS_TOKEN", caught.exception.next_action or "")
        self.assertIn("restart", caught.exception.next_action or "")

    def test_unsupported_and_absent_provider_are_bounded_errors(self) -> None:
        absent = ExploreService(None)
        with self.assertRaises(ExploreError) as caught:
            absent.browse({})
        self.assertEqual(caught.exception.code, ExploreErrorCode.PROVIDER_NOT_CONFIGURED)

        class OrganizeOnlyProvider:
            provider_id = "tmdb"

        unsupported = ExploreService(
            lambda ids: MetadataProviderRegistry((OrganizeOnlyProvider(),))  # type: ignore[arg-type]
        )
        with self.assertRaises(ExploreError) as caught:
            unsupported.search({"mediaType": ["movie"], "query": ["x"]})
        self.assertEqual(caught.exception.code, ExploreErrorCode.PROVIDER_NOT_CONFIGURED)

    def test_paging_normalizes_real_totals(self) -> None:
        last_page = self.service.browse({"page": ["9"]})
        self.assertEqual(last_page["page"], 9)
        self.assertFalse(last_page["hasMore"])
        boundary = self.service.browse({"page": ["3"]})
        self.assertEqual(boundary["page"], 3)
        self.assertFalse(boundary["hasMore"])


class MetadataCacheBoundTests(unittest.TestCase):
    def test_ttl_expiration_and_default_unbounded_semantics(self) -> None:
        now = [100.0]
        cache = MetadataCache(clock=lambda: now[0])
        key = MetadataCacheKey("tmdb", "op", (("a", "b"),))
        cache.put(key, "value", 10)
        self.assertEqual(cache.get(key), "value")
        now[0] = 111.0
        self.assertIsNone(cache.get(key))
        # Historical default stays unbounded: many entries all remain reachable.
        for index in range(400):
            cache.put(MetadataCacheKey("tmdb", "op", (("i", str(index)),)), index, 1000)
        self.assertEqual(cache.get(MetadataCacheKey("tmdb", "op", (("i", "399"),))), 399)

    def test_capacity_evicts_oldest_entry(self) -> None:
        now = [0.0]
        cache = MetadataCache(clock=lambda: now[0], max_entries=2)
        first = MetadataCacheKey("tmdb", "op", (("i", "1"),))
        second = MetadataCacheKey("tmdb", "op", (("i", "2"),))
        third = MetadataCacheKey("tmdb", "op", (("i", "3"),))
        cache.put(first, "a", 100)
        cache.put(second, "b", 100)
        cache.put(third, "c", 100)
        self.assertIsNone(cache.get(first))
        self.assertEqual(cache.get(second), "b")
        self.assertEqual(cache.get(third), "c")
        with self.assertRaises(ValueError):
            MetadataCache(max_entries=0)


if __name__ == "__main__":
    unittest.main()
