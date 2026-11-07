from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.domain.explore import (
    ExploreBrowseQuery,
    ExploreDetail,
    ExploreError,  # noqa: F401  (import guard: domain errors never reach the API layer)
    ExploreGenre,
    ExploreItem,
    ExploreLanguage,
    ExploreOptions,
    ExplorePage,
    ExploreSearchQuery,
    ExploreSort,
)
from mediaflow.domain.metadata import MediaType, MetadataError, MetadataErrorCode
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.tmdb import (
    HttpxTransport,
    TMDBClient,
    TMDBConfig,
    TMDBProvider,
)
from mediaflow.interfaces.service_api import MediaFlowApi

VIEWER_PRINCIPAL = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
NO_READ_PRINCIPAL = ResolvedApiPrincipal(
    "audit-only", "audit-token", frozenset({ApiPermission.READ_SECURITY_AUDIT})
)
PRINCIPALS = (VIEWER_PRINCIPAL, NO_READ_PRINCIPAL)


class FakeExploreProvider:
    """Bounded Explore port double; organizing-only fakes stay untouched."""

    provider_id = "tmdb"

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.browse_error: MetadataError | None = None
        self.detail_error: MetadataError | None = None
        self.search_error: MetadataError | None = None

    def browse(self, query: ExploreBrowseQuery) -> ExplorePage:
        self.calls.append(("browse", query))
        if self.browse_error is not None:
            raise self.browse_error
        return ExplorePage(
            "tmdb",
            query.media_type,
            query.page,
            3,
            42,
            (
                ExploreItem(
                    "tmdb",
                    str(600 + query.page),
                    query.media_type,
                    "Alpha",
                    "Alpha",
                    2020,
                    "2020-05-01",
                    8.1 if query.sort is ExploreSort.RATING else 7.5,
                    120,
                    "/alpha.jpg",
                    "/alpha-bg.jpg",
                    (28,),
                ),
            ),
            query.sort,
            genre_id=query.genre_id,
            original_language=query.original_language,
            year=query.year,
            min_rating=query.min_rating,
            min_votes=query.effective_min_votes,
            keyword=None,
        )

    def search(self, query: ExploreSearchQuery) -> ExplorePage:
        self.calls.append(("search", query))
        if self.search_error is not None:
            raise self.search_error
        return ExplorePage(
            "tmdb",
            query.media_type,
            query.page,
            1,
            0,
            (),
            ExploreSort.POPULAR,
            keyword=query.keyword,
        )

    def detail(self, media_type: MediaType, provider_id: int) -> ExploreDetail:
        self.calls.append(("detail", (media_type, provider_id)))
        if self.detail_error is not None:
            raise self.detail_error
        return ExploreDetail(
            "tmdb",
            str(provider_id),
            media_type,
            "Alpha Movie" if media_type is MediaType.MOVIE else "Alpha Show",
            "Alpha",
            2020,
            "2020-05-01",
            8.1,
            120,
            ("动作",),
            "简介",
            100 if media_type is MediaType.MOVIE else None,
            None if media_type is MediaType.MOVIE else "2019-01-15",
            None if media_type is MediaType.MOVIE else 2,
            None if media_type is MediaType.MOVIE else 24,
            "/alpha.jpg",
            "/alpha-bg.jpg",
            f"https://www.themoviedb.org/{media_type.value}/{provider_id}",
        )

    def options(self, media_type: MediaType) -> ExploreOptions:
        self.calls.append(("options", media_type))
        return ExploreOptions(
            "tmdb",
            media_type,
            (ExploreGenre(28, "动作"), ExploreGenre(878, "科幻")),
            (ExploreLanguage("zh", "中文"), ExploreLanguage("en", "英语")),
        )


class ReadOnlySpyRepository:
    """Delegating repository that flags any call beyond the request audit."""

    def __init__(self, inner) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "violations", [])
        object.__setattr__(self, "recording", False)

    def __getattr__(self, name):
        inner = getattr(object.__getattribute__(self, "_inner"), name)
        if name == "append_security_audit" or not callable(inner):
            return inner

        def guarded(*args, **kwargs):
            if object.__getattribute__(self, "recording"):
                object.__getattribute__(self, "violations").append(name)
            return inner(*args, **kwargs)

        return guarded


def request(api, path: str, *, method: str = "GET", token: str = "viewer-token"):
    status: list[str] = []
    headers: list = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if "?" in path:
        path, _, query = path.partition("?")
        environ["PATH_INFO"] = path
        environ["QUERY_STRING"] = query
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def start_response(value, values):
        status.append(value)
        headers.extend(values)

    body = b"".join(api(environ, start_response))
    return int(status[0].split()[0]), dict(headers), json.loads(body)


class ExploreApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.database = Path(self._temporary.name) / "explore.sqlite3"
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        self.provider = FakeExploreProvider()
        self.factory_calls = 0
        self.api = self._build_api(self._factory)

    def _factory(self, provider_ids):
        self.factory_calls += 1
        self.requested = tuple(provider_ids)
        return MetadataProviderRegistry((self.provider,))

    def _build_api(self, factory, repository=None) -> MediaFlowApi:
        return MediaFlowApi(
            repository if repository is not None else self.repository,
            None,
            principals=PRINCIPALS,
            metadata_provider_registry_factory=factory,
        )

    # -- success documents ---------------------------------------------------

    def test_browse_search_options_and_detail_documents(self) -> None:
        status, _, body = request(self.api, "/api/v1/explore/browse?mediaType=movie&sort=rating")
        self.assertEqual(status, 200)
        self.assertEqual(body["provider"], "tmdb")
        self.assertEqual(body["mediaType"], "movie")
        self.assertEqual(body["pageLimit"], 500)
        self.assertEqual(
            body["applied"],
            {
                "mediaType": "movie",
                "page": 1,
                "sort": "rating",
                "minVotes": 100,
            },
        )
        self.assertEqual(body["items"][0]["providerId"], "601")

        status, _, options = request(self.api, "/api/v1/explore/options?mediaType=tv")
        self.assertEqual(status, 200)
        self.assertEqual(options["mediaType"], "tv")
        self.assertEqual([genre["name"] for genre in options["genres"]], ["动作", "科幻"])
        self.assertEqual([language["code"] for language in options["languages"]], ["zh", "en"])

        status, _, search = request(
            self.api, "/api/v1/explore/search?mediaType=movie&query=matrix&page=2"
        )
        self.assertEqual(status, 200)
        self.assertEqual(search["applied"], {"mediaType": "movie", "page": 2, "query": "matrix"})
        self.assertEqual(search["totalResults"], 0)
        self.assertEqual(self.requested, ("tmdb",))

        status, _, detail = request(self.api, "/api/v1/explore/movie/603")
        self.assertEqual(status, 200)
        self.assertEqual(detail["title"], "Alpha Movie")
        self.assertEqual(detail["externalUrl"], "https://www.themoviedb.org/movie/603")
        # The nullable episode count runs through the wire contract as-is.
        self.assertIsNone(detail["numberOfEpisodes"])
        status, _, show = request(self.api, "/api/v1/explore/tv/603")
        self.assertEqual(status, 200)
        self.assertEqual(show["numberOfEpisodes"], 24)
        self.assertEqual(show["numberOfSeasons"], 2)

        browse_calls = [entry for entry in self.provider.calls if entry[0] == "browse"]
        self.assertEqual(browse_calls[0][1].sort, ExploreSort.RATING)

    def test_detail_identity_is_media_type_plus_exact_id(self) -> None:
        status, _, movie = request(self.api, "/api/v1/explore/movie/603")
        self.assertEqual(status, 200)
        status, _, show = request(self.api, "/api/v1/explore/tv/603")
        self.assertEqual(status, 200)
        self.assertEqual(movie["title"], "Alpha Movie")
        self.assertEqual(show["title"], "Alpha Show")
        self.assertIn(("detail", (MediaType.MOVIE, 603)), self.provider.calls)
        self.assertIn(("detail", (MediaType.TV, 603)), self.provider.calls)

    def test_unknown_and_invalid_detail_routes(self) -> None:
        for path, expected in (
            ("/api/v1/explore/anime/1", 404),
            ("/api/v1/explore/movie/0", 400),
            ("/api/v1/explore/movie/-5", 400),
            ("/api/v1/explore/movie/99999999999", 400),
            ("/api/v1/explore/movie/abc", 400),
            ("/api/v1/explore/movie/603?extra=1", 400),
            ("/api/v1/explore/unknown-op", 404),
        ):
            with self.subTest(path=path):
                status, _, body = request(self.api, path)
                self.assertEqual(status, expected, body)
        self.assertEqual(
            [entry for entry in self.provider.calls if entry[0] == "detail"],
            [],
        )

    # -- permissions before any provider access -----------------------------

    def test_authentication_and_read_permission_precede_provider_access(self) -> None:
        status, headers, body = request(self.api, "/api/v1/explore/browse", token=None)
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")
        self.assertIn("WWW-Authenticate", headers)
        status, _, body = request(self.api, "/api/v1/explore/browse", token="wrong")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

        status, headers, body = request(self.api, "/api/v1/explore/browse", token="audit-token")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "forbidden")
        # No legitimate READ: no provider resolution, no cache, no upstream read.
        self.assertEqual(self.factory_calls, 0)
        self.assertEqual(self.provider.calls, [])

        # A valid READ then really reaches the port.
        status, _, _ = request(self.api, "/api/v1/explore/browse")
        self.assertEqual(status, 200)
        self.assertEqual(self.factory_calls, 1)

    def test_non_get_explore_requests_follow_the_unknown_route_rule(self) -> None:
        status, _, body = request(self.api, "/api/v1/explore/browse", method="POST")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(self.provider.calls, [])

    # -- parameter validation -------------------------------------------------

    def test_invalid_queries_are_bounded_400_before_provider(self) -> None:
        cases = (
            "/api/v1/explore/browse?unknown=1",
            "/api/v1/explore/browse?page=1&page=2",
            "/api/v1/explore/browse?page=501",
            "/api/v1/explore/browse?sort=random",
            "/api/v1/explore/browse?mediaType=anime",
            "/api/v1/explore/browse?year=10000",
            "/api/v1/explore/browse?minRating=nan",
            "/api/v1/explore/browse?minRating=11",
            "/api/v1/explore/browse?minVotes=-1",
            "/api/v1/explore/search?query=matrix",
            "/api/v1/explore/search?mediaType=movie&query=",
            "/api/v1/explore/search?mediaType=movie&query=bad%0Aword",
            "/api/v1/explore/search?mediaType=movie&query=matrix&year=2020",
            "/api/v1/explore/options",
            "/api/v1/explore/options?mediaType=anime",
        )
        for path in cases:
            with self.subTest(path=path):
                status, _, body = request(self.api, path)
                self.assertEqual(status, 400, body)
                self.assertEqual(body["error"]["code"], "invalid_request")
        self.assertEqual(self.provider.calls, [])

    # -- normalized failure categories ---------------------------------------

    def test_upstream_failures_keep_http_status_with_provider_body_code(self) -> None:
        mapping = (
            (
                MetadataError(MetadataErrorCode.AUTHENTICATION_FAILED, "tmdb 401"),
                401,
                "provider_authentication_failed",
                ("WWW-Authenticate",),
                False,
            ),
            (
                MetadataError(MetadataErrorCode.PERMISSION_DENIED, "tmdb 403"),
                403,
                "provider_permission_denied",
                ("X-Frame-Options",),
                False,
            ),
            (
                MetadataError(MetadataErrorCode.RATE_LIMITED, "429"),
                429,
                "provider_rate_limited",
                ("X-Frame-Options",),
                True,
            ),
            (
                MetadataError(MetadataErrorCode.TIMEOUT, "timeout"),
                504,
                "provider_timeout",
                ("X-Frame-Options",),
                True,
            ),
            (
                MetadataError(MetadataErrorCode.MALFORMED_RESPONSE, "bad json"),
                502,
                "provider_malformed",
                ("X-Frame-Options",),
                True,
            ),
            (
                MetadataError(MetadataErrorCode.PROVIDER_UNAVAILABLE, "5xx"),
                502,
                "provider_unavailable",
                ("X-Frame-Options",),
                True,
            ),
        )
        for failure, expected_status, expected_code, headers, retryable in mapping:
            with self.subTest(code=expected_code):
                self.provider.browse_error = failure
                status, headers_map, body = request(self.api, "/api/v1/explore/browse")
                self.assertEqual(status, expected_status, body)
                self.assertEqual(body["error"]["code"], expected_code)
                for header in headers:
                    if header == "WWW-Authenticate":
                        self.assertNotIn(header, headers_map)
                    else:
                        self.assertIn(header, headers_map)
                self.assertEqual(body["error"]["details"]["sideEffects"], "none")
                self.assertEqual(body["error"]["details"]["retrySafe"], retryable)
                if not retryable:
                    self.assertIn("nextAction", body["error"]["details"])
                self.assertNotIn("viewer-token", json.dumps(body))

    def test_local_401_still_challenges_but_provider_401_does_not(self) -> None:
        self.provider.browse_error = MetadataError(
            MetadataErrorCode.AUTHENTICATION_FAILED, "upstream rejected credential"
        )
        status, headers, body = request(self.api, "/api/v1/explore/browse")
        self.assertEqual(status, 401)
        self.assertNotIn("WWW-Authenticate", headers)
        self.assertEqual(body["error"]["code"], "provider_authentication_failed")
        status, headers, body = request(self.api, "/api/v1/explore/browse", token=None)
        self.assertEqual(status, 401)
        self.assertIn("WWW-Authenticate", headers)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_missing_title_and_missing_configuration_are_distinct(self) -> None:
        self.provider.detail_error = MetadataError(MetadataErrorCode.NOT_FOUND, "gone")
        status, _, body = request(self.api, "/api/v1/explore/movie/404")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

        api = self._build_api(None)
        status, _, body = request(api, "/api/v1/explore/browse")
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "provider_not_configured")
        self.assertIn("nextAction", body["error"]["details"])
        self.assertEqual(body["error"]["details"]["retrySafe"], False)

    # -- audit and durable effects -------------------------------------------

    def test_audit_routes_exclude_keywords_and_ids(self) -> None:
        status, _, _ = request(
            self.api, "/api/v1/explore/search?mediaType=movie&query=top-secret-word"
        )
        self.assertEqual(status, 200)
        status, _, _ = request(self.api, "/api/v1/explore/movie/603")
        self.assertEqual(status, 200)
        records = list(self.repository.list_security_audit())
        routes = {record.route for record in records if record.route.startswith("/api/v1/explore")}
        self.assertEqual(routes, {"/api/v1/explore/search", "/api/v1/explore/{mediaType}/{id}"})
        self.assertNotIn(
            "top-secret-word", json.dumps([record.route for record in records], ensure_ascii=False)
        )

    def test_explore_requests_touch_no_repository_surface_beyond_audit(self) -> None:
        spy_repository = ReadOnlySpyRepository(
            SQLiteTaskRepository(Path(self._temporary.name) / "spy.sqlite3")
        )
        api = self._build_api(self._factory, repository=spy_repository)
        spy_repository.recording = True
        for path in (
            "/api/v1/explore/browse",
            "/api/v1/explore/search?mediaType=movie&query=matrix",
            "/api/v1/explore/options?mediaType=movie",
            "/api/v1/explore/movie/603",
            "/api/v1/explore/browse?page=1&page=2",
        ):
            request(api, path)
        self.assertEqual(spy_repository.violations, [])


ZERO_PAGE = {
    "page": 1,
    "total_pages": 0,
    "total_results": 0,
    "results": [],
}
PRODUCTION_GENRES = {
    "movie": {"genres": [{"id": 28, "name": "动作"}, {"id": 18, "name": "剧情"}]},
    "tv": {"genres": [{"id": 18, "name": "剧情"}, {"id": 10765, "name": "科幻与奇幻"}]},
}
PRODUCTION_LANGUAGES = [
    {"iso_639_1": "ko", "english_name": "Korean", "name": "한국어"},
    {"iso_639_1": "en", "english_name": "English", "name": "English"},
]


class ProductionAdapterExploreApiTests(unittest.TestCase):
    """The real TMDB adapter/API boundary, not an internal page double."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.repository = SQLiteTaskRepository(
            Path(self._temporary.name) / "production-explore.sqlite3"
        )
        self.addCleanup(self.repository.close)
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.page_payload = dict(ZERO_PAGE)

    def _handler(self, request):
        import httpx

        path = request.url.path
        if path.startswith("/3/"):
            path = path[3:]
        params = dict(request.url.params)
        self.calls.append((path, params))
        if path in {"discover/movie", "discover/tv", "search/movie", "search/tv"}:
            return httpx.Response(200, json=self.page_payload)
        if path in {"genre/movie/list", "genre/tv/list"}:
            return httpx.Response(200, json=PRODUCTION_GENRES[path.split("/")[1]])
        if path == "configuration/languages":
            return httpx.Response(200, json=PRODUCTION_LANGUAGES)
        return httpx.Response(404, json={"status_code": 34, "status_message": "not found"})

    def _api(self) -> MediaFlowApi:
        import httpx

        client = httpx.Client(transport=httpx.MockTransport(self._handler))
        self.addCleanup(client.close)
        config = TMDBConfig("production-adapter-token")
        provider = TMDBProvider(TMDBClient(config, transport=HttpxTransport(config, client=client)))
        return MediaFlowApi(
            self.repository,
            None,
            principals=PRINCIPALS,
            metadata_provider_registry_factory=(
                lambda _provider_ids: MetadataProviderRegistry((provider,))
            ),
        )

    def _list_calls(self, route: str) -> list[dict[str, str]]:
        return [params for path, params in self.calls if path == route]

    def test_zero_page_answers_cross_the_production_adapter_and_api(self) -> None:
        api = self._api()
        cases = (
            (
                "/api/v1/explore/browse?mediaType=movie&sort=rating&minVotes=250"
                "&genreId=28&originalLanguage=ko&year=2024&minRating=7.5&page=1",
                "discover/movie",
                {
                    "mediaType": "movie",
                    "page": 1,
                    "sort": "rating",
                    "genreId": 28,
                    "originalLanguage": "ko",
                    "year": 2024,
                    "minRating": 7.5,
                    "minVotes": 250,
                },
                {
                    "page": "1",
                    "sort_by": "vote_average.desc",
                    "with_genres": "28",
                    "with_original_language": "ko",
                    "primary_release_year": "2024",
                    "vote_average.gte": "7.5",
                    "vote_count.gte": "250",
                },
            ),
            (
                "/api/v1/explore/browse?mediaType=tv&sort=date&genreId=18"
                "&originalLanguage=ko&year=2024&page=1",
                "discover/tv",
                {
                    "mediaType": "tv",
                    "page": 1,
                    "sort": "date",
                    "genreId": 18,
                    "originalLanguage": "ko",
                    "year": 2024,
                },
                {
                    "page": "1",
                    "sort_by": "first_air_date.desc",
                    "with_genres": "18",
                    "with_original_language": "ko",
                    "first_air_date_year": "2024",
                },
            ),
            (
                "/api/v1/explore/search?mediaType=movie&query=no%20such%20work&page=1",
                "search/movie",
                {"mediaType": "movie", "page": 1, "query": "no such work"},
                {"page": "1", "query": "no such work"},
            ),
            (
                "/api/v1/explore/search?mediaType=tv&query=no%20such%20work&page=1",
                "search/tv",
                {"mediaType": "tv", "page": 1, "query": "no such work"},
                {"page": "1", "query": "no such work"},
            ),
        )
        for path, route, applied, expected_params in cases:
            with self.subTest(path=path):
                status, _, body = request(api, path)
                self.assertEqual(status, 200, body)
                self.assertNotIn("error", body)
                self.assertEqual(body["provider"], "tmdb")
                self.assertEqual(body["mediaType"], applied["mediaType"])
                self.assertEqual(body["page"], 1)
                self.assertEqual(body["totalPages"], 1)
                self.assertEqual(body["totalResults"], 0)
                self.assertEqual(body["items"], [])
                self.assertFalse(body["hasMore"])
                self.assertEqual(body["applied"], applied)
                calls_before = len(self._list_calls(route))
                self.assertGreaterEqual(calls_before, 1)
                sent = self._list_calls(route)[-1]
                for name, value in expected_params.items():
                    self.assertEqual(sent[name], value)
                # A repeated identical read is the same bounded cache entry:
                # the API document is stable and no new upstream list read runs.
                status, _, repeated = request(api, path)
                self.assertEqual(status, 200)
                self.assertEqual(repeated, body)
                self.assertEqual(len(self._list_calls(route)), calls_before)

    def test_malformed_upstream_totals_remain_502_through_the_production_adapter(self) -> None:
        invalid_totals = (
            {"page": 1, "total_pages": -1, "total_results": 0, "results": []},
            {"page": 1, "total_pages": True, "total_results": 0, "results": []},
            {"page": 1, "total_pages": 0, "total_results": 1, "results": []},
            {
                "page": 1,
                "total_pages": 0,
                "total_results": 0,
                "results": [
                    {
                        "id": 1,
                        "title": "Leaked",
                        "original_title": "Leaked",
                        "release_date": "2020-01-01",
                    }
                ],
            },
        )
        for payload in invalid_totals:
            with self.subTest(payload=payload):
                self.page_payload = payload
                self.calls.clear()
                api = self._api()
                status, _, body = request(api, "/api/v1/explore/browse?mediaType=movie")
                self.assertEqual(status, 502, body)
                self.assertEqual(body["error"]["code"], "provider_malformed")
                self.assertEqual(
                    self._list_calls("discover/movie"),
                    [
                        {
                            "language": "zh-CN",
                            "page": "1",
                            "include_adult": "false",
                            "sort_by": "popularity.desc",
                        }
                    ],
                )

    def test_invalid_request_page_never_reaches_the_production_provider(self) -> None:
        api = self._api()
        for page in ("0", "501"):
            with self.subTest(page=page):
                status, _, body = request(
                    api, f"/api/v1/explore/browse?mediaType=movie&page={page}"
                )
                self.assertEqual(status, 400, body)
                self.assertEqual(body["error"]["code"], "invalid_request")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
