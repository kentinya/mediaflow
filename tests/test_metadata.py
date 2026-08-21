from __future__ import annotations

import threading
import unittest
from dataclasses import replace

from mediaflow.application.classification import (
    ClassificationPolicyRegistry,
    ClassificationPreviewService,
)
from mediaflow.application.metadata import (
    CandidateMatcher,
    MetadataCache,
    MetadataCacheKey,
    MetadataIdentificationService,
    MetadataProviderRegistry,
)
from mediaflow.domain.classification import ClassificationContext, ClassificationStatus
from mediaflow.domain.metadata import (
    CandidateMatchStatus,
    EpisodeIdentity,
    MediaCandidate,
    MediaIdentity,
    MediaType,
    MetadataError,
    MetadataErrorCode,
    MetadataIdentificationStatus,
    MetadataPolicy,
    ProviderCapabilities,
)
from mediaflow.domain.naming import NamingResult
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import RecognitionResult, RecognitionType
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.infrastructure.tmdb import TMDBClient, TMDBConfig, TMDBProvider


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


class FakeTransport:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, *, params, headers, timeout):
        self.calls.append((method, url, params, headers, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class BlockingTransport:
    def __init__(self) -> None:
        self.active = 0
        self.maximum = 0
        self.lock = threading.Lock()
        self.reached_limit = threading.Event()
        self.release = threading.Event()

    def request(self, method, url, *, params, headers, timeout):
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            if self.active == 2:
                self.reached_limit.set()
        self.release.wait(2)
        with self.lock:
            self.active -= 1
        return FakeResponse(200, {"ok": True})


def config(**changes) -> TMDBConfig:
    return replace(TMDBConfig("super-secret-token"), **changes)


def policy(media_type=MediaType.MOVIE, **changes) -> MetadataPolicy:
    return replace(MetadataPolicy("metadata", "tmdb", media_type=media_type), **changes)


class TMDBClientTests(unittest.TestCase):
    def test_bearer_auth_endpoint_parameters_and_timeout(self) -> None:
        transport = FakeTransport((FakeResponse(200, {"results": [], "total_pages": 1}),))
        client = TMDBClient(config(), transport)
        client.get("search/movie", {"query": "The Matrix", "language": "en-US"})
        method, url, params, headers, timeout = transport.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://api.themoviedb.org/3/search/movie")
        self.assertEqual(params["query"], "The Matrix")
        self.assertEqual(headers["Authorization"], "Bearer super-secret-token")
        self.assertEqual(timeout, (5, 10))

    def test_429_retry_after_and_5xx_retry_are_bounded(self) -> None:
        transport = FakeTransport(
            (
                FakeResponse(429, {}, {"Retry-After": "0.25"}),
                FakeResponse(503, {}),
                FakeResponse(200, {"ok": True}),
            )
        )
        delays = []
        payload = TMDBClient(config(retry_count=2), transport, delays.append).get("movie/603")
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(delays, [0.25, 0.2])
        self.assertEqual(len(transport.calls), 3)

    def test_timeout_connection_and_http_errors_are_unified(self) -> None:
        cases = (
            (TimeoutError(), MetadataErrorCode.TIMEOUT),
            (OSError(), MetadataErrorCode.CONNECTION_FAILED),
            (FakeResponse(401, {}), MetadataErrorCode.AUTHENTICATION_FAILED),
            (FakeResponse(403, {}), MetadataErrorCode.PERMISSION_DENIED),
            (FakeResponse(404, {}), MetadataErrorCode.NOT_FOUND),
        )
        for response, expected in cases:
            with self.subTest(expected=expected), self.assertRaises(MetadataError) as caught:
                TMDBClient(config(retry_count=0), FakeTransport((response,))).get("movie/1")
            self.assertEqual(caught.exception.code, expected)

    def test_invalid_json_and_shape_are_malformed(self) -> None:
        for response in (
            FakeResponse(200, json_error=ValueError("bad token")),
            FakeResponse(200, []),
        ):
            with self.subTest(response=response), self.assertRaises(MetadataError) as caught:
                TMDBClient(config(), FakeTransport((response,))).get("movie/1")
            self.assertEqual(caught.exception.code, MetadataErrorCode.MALFORMED_RESPONSE)
            self.assertNotIn("super-secret-token", str(caught.exception))

    def test_configuration_redacts_secret(self) -> None:
        value = config()
        self.assertNotIn("super-secret-token", repr(value))
        self.assertIn("***", repr(value))

    def test_request_concurrency_is_bounded(self) -> None:
        transport = BlockingTransport()
        client = TMDBClient(config(max_concurrency=2), transport)
        threads = [
            threading.Thread(target=client.get, args=(f"movie/{number}",)) for number in range(4)
        ]
        for thread in threads:
            thread.start()
        self.assertTrue(transport.reached_limit.wait(1))
        self.assertEqual(transport.maximum, 2)
        transport.release.set()
        for thread in threads:
            thread.join(2)
        self.assertEqual(transport.maximum, 2)


class TMDBProviderTests(unittest.TestCase):
    def test_region_search_date_is_not_mapped_as_canonical_year(self) -> None:
        transport = FakeTransport(
            (
                FakeResponse(
                    200,
                    {
                        "total_pages": 1,
                        "results": [
                            {
                                "id": 129,
                                "title": "千与千寻",
                                "original_title": "千と千尋の神隠し",
                                "release_date": "2019-06-21",
                            }
                        ],
                    },
                ),
            )
        )
        candidate = TMDBProvider(TMDBClient(config(), transport)).search_movie(
            ParseResult("千与千寻", year=2001),
            policy(language="zh-CN", region="CN", max_search_pages=1),
        )[0]
        self.assertIsNone(candidate.canonical_year)
        self.assertEqual(candidate.regional_year, 2019)
        self.assertEqual(transport.calls[0][2]["primary_release_year"], 2001)
        self.assertEqual(transport.calls[0][2]["region"], "CN")

    def test_movie_search_pagination_mapping_and_cache(self) -> None:
        transport = FakeTransport(
            (
                FakeResponse(
                    200,
                    {
                        "total_pages": 2,
                        "results": [
                            {
                                "id": 1,
                                "title": "Wrong",
                                "original_title": "Wrong",
                                "release_date": "2000-01-01",
                            }
                        ],
                    },
                ),
                FakeResponse(
                    200,
                    {
                        "total_pages": 2,
                        "results": [
                            {
                                "id": 603,
                                "title": "The Matrix",
                                "original_title": "The Matrix",
                                "release_date": "1999-03-30",
                                "original_language": "en",
                                "alternative_titles": ["矩阵"],
                            }
                        ],
                    },
                ),
            )
        )
        provider = TMDBProvider(TMDBClient(config(), transport))
        parsed = ParseResult("The Matrix", year=1999)
        first = provider.search_movie(parsed, policy(max_search_pages=2))
        second = provider.search_movie(parsed, policy(max_search_pages=2))
        self.assertEqual([item.provider_id for item in first], ["1", "603"])
        self.assertEqual(first, second)
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(transport.calls[0][2]["primary_release_year"], 1999)
        self.assertEqual(first[1].alternative_titles, ("矩阵",))

    def test_force_refresh_and_cache_key_include_language_region_and_year(self) -> None:
        responses = tuple(FakeResponse(200, {"total_pages": 1, "results": []}) for _ in range(8))
        transport = FakeTransport(responses)
        provider = TMDBProvider(TMDBClient(config(), transport))
        parsed = ParseResult("Example", year=2024)
        provider.search_movie(parsed, policy(language="en-US", region="US"))
        provider.search_movie(parsed, policy(language="zh-CN", region="CN"))
        provider.search_movie(replace(parsed, year=2023), policy(language="en-US", region="US"))
        provider.search_movie(parsed, policy(language="en-US", region="US"), force_refresh=True)
        self.assertEqual(len(transport.calls), 8)
        self.assertEqual(transport.calls[2][2]["language"], "zh-CN")
        self.assertEqual(transport.calls[2][2]["region"], "CN")

    def test_movie_search_relaxes_primary_year_only_after_empty_strict_result(self) -> None:
        transport = FakeTransport(
            (
                FakeResponse(200, {"total_pages": 1, "results": []}),
                FakeResponse(
                    200,
                    {
                        "total_pages": 1,
                        "results": [
                            {
                                "id": 129,
                                "title": "千与千寻",
                                "original_title": "千と千尋の神隠し",
                                "release_date": "2019-06-21",
                            }
                        ],
                    },
                ),
            )
        )
        result = TMDBProvider(TMDBClient(config(), transport)).search_movie(
            ParseResult("千与千寻", year=2001),
            policy(language="zh-CN", region="CN", max_search_pages=1),
        )
        self.assertEqual(result[0].provider_id, "129")
        self.assertEqual(transport.calls[0][2]["primary_release_year"], 2001)
        self.assertNotIn("primary_release_year", transport.calls[1][2])

    def test_movie_and_tv_details_map_internal_identity(self) -> None:
        movie = {
            "id": 603,
            "title": "矩阵",
            "original_title": "The Matrix",
            "release_date": "1999-03-30",
            "overview": "Overview",
            "genres": [{"id": 16, "name": "动画"}],
            "production_countries": [{"iso_3166_1": "JP", "name": "日本"}],
            "spoken_languages": [{"iso_639_1": "en"}],
            "alternative_titles": {"titles": [{"title": "Matrix"}]},
            "translations": {
                "translations": [
                    {"iso_639_1": "zh", "iso_3166_1": "CN", "data": {"title": "黑客帝国"}}
                ]
            },
            "external_ids": {"imdb_id": "tt0133093"},
        }
        tv = {
            "id": 1399,
            "name": "权力的游戏",
            "original_name": "Game of Thrones",
            "first_air_date": "2011-04-17",
            "genres": [{"name": "Drama"}],
            "origin_country": ["US"],
            "spoken_languages": [{"iso_639_1": "en"}],
            "alternative_titles": {"results": [{"title": "GOT"}]},
            "external_ids": {"imdb_id": "tt0944947"},
        }
        transport = FakeTransport((FakeResponse(200, movie), FakeResponse(200, tv)))
        provider = TMDBProvider(TMDBClient(config(), transport))
        movie_identity = provider.get_movie("603", policy())
        self.assertEqual(provider.get_movie("603", policy()), movie_identity)
        tv_identity = provider.get_tv("1399", policy(MediaType.TV))
        self.assertEqual(
            (
                movie_identity.title,
                movie_identity.original_title,
                movie_identity.genres,
                movie_identity.external_ids,
            ),
            ("矩阵", "The Matrix", ("Animation",), (("imdb_id", "tt0133093"),)),
        )
        self.assertEqual(movie_identity.translated_titles, ("黑客帝国",))
        self.assertEqual(
            transport.calls[0][2]["append_to_response"],
            "alternative_titles,translations,external_ids",
        )
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(
            (tv_identity.media_type, tv_identity.alternative_titles), (MediaType.TV, ("GOT",))
        )

    def test_localized_tmdb_genre_flows_into_development_classification_policy(self) -> None:
        details = {
            "id": 129,
            "title": "千与千寻",
            "original_title": "千と千尋の神隠し",
            "release_date": "2001-07-20",
            "genres": [{"id": 16, "name": "动画"}],
            "production_countries": [{"iso_3166_1": "JP", "name": "日本"}],
        }
        identity = TMDBProvider(
            TMDBClient(config(), FakeTransport((FakeResponse(200, details),)))
        ).get_movie("129", policy(language="zh-CN", region="CN"))
        policies = development_strategy_configuration().classification_policies
        classification = ClassificationPreviewService(
            ClassificationPolicyRegistry(policies)
        ).preview(
            ClassificationContext(
                RecognitionType("A", "A"),
                identity,
                ParseResult("千与千寻", year=2001),
                NamingResult("千与千寻 (2001)", "千与千寻 (2001).mkv"),
            ),
            "A",
        )
        self.assertEqual(("Animation",), identity.genres)
        self.assertEqual(("JP",), identity.countries)
        self.assertEqual(ClassificationStatus.CLASSIFIED, classification.status)
        self.assertEqual("Movies", classification.library)
        self.assertEqual("Anime", classification.category)

    def test_tv_search_season_episode_and_external_id_endpoints(self) -> None:
        responses = (
            FakeResponse(
                200,
                {
                    "total_pages": 1,
                    "results": [
                        {
                            "id": 10,
                            "name": "Show",
                            "original_name": "Show",
                            "first_air_date": "2020-01-01",
                        }
                    ],
                },
            ),
            FakeResponse(
                200,
                {
                    "id": 10,
                    "name": "Show",
                    "season_number": 1,
                    "episodes": [
                        {"episode_number": 1, "name": "One"},
                        {"episode_number": 2, "name": "Two"},
                    ],
                },
            ),
            FakeResponse(
                200, {"id": 100, "episode_number": 2, "name": "Two", "air_date": "2020-01-02"}
            ),
            FakeResponse(
                200,
                {
                    "movie_results": [
                        {
                            "id": 603,
                            "title": "The Matrix",
                            "original_title": "The Matrix",
                            "release_date": "1999-01-01",
                        }
                    ],
                    "tv_results": [],
                },
            ),
        )
        transport = FakeTransport(responses)
        provider = TMDBProvider(TMDBClient(config(), transport))
        self.assertEqual(
            provider.search_tv(ParseResult("Show"), policy(MediaType.TV))[0].media_type,
            MediaType.TV,
        )
        self.assertEqual(
            tuple(
                item.episode
                for item in provider.get_season("10", 1, policy(MediaType.TV)).episode_metadata
            ),
            (1, 2),
        )
        self.assertEqual(
            provider.get_episode("10", 1, 2, policy(MediaType.TV)).episode_title, "Two"
        )
        self.assertEqual(
            provider.find_by_external_id("imdb_id", "tt0133093", policy())[0].provider_id, "603"
        )
        paths = [call[1].removeprefix("https://api.themoviedb.org/3/") for call in transport.calls]
        self.assertEqual(
            paths, ["search/tv", "tv/10/season/1", "tv/10/season/1/episode/2", "find/tt0133093"]
        )

    def test_malformed_candidate_and_unsupported_external_source(self) -> None:
        provider = TMDBProvider(
            TMDBClient(
                config(),
                FakeTransport(
                    (FakeResponse(200, {"total_pages": 1, "results": [{"title": "No ID"}]}),)
                ),
            )
        )
        with self.assertRaises(MetadataError) as caught:
            provider.search_movie(ParseResult("No ID"), policy())
        self.assertEqual(caught.exception.code, MetadataErrorCode.MALFORMED_RESPONSE)
        with self.assertRaises(MetadataError) as caught:
            provider.find_by_external_id("unsupported", "x", policy())
        self.assertEqual(caught.exception.code, MetadataErrorCode.UNSUPPORTED_OPERATION)


class CandidateMatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matcher = CandidateMatcher()
        self.policy = policy()

    def test_wrong_first_result_later_correct_result_is_selected(self) -> None:
        candidates = (
            MediaCandidate("tmdb", "1", MediaType.MOVIE, "The Matrix Resurrections", year=2021),
            MediaCandidate("tmdb", "603", MediaType.MOVIE, "The Matrix", year=1999),
        )
        result = self.matcher.match(ParseResult("The Matrix", year=1999), candidates, self.policy)
        self.assertEqual(result.status, CandidateMatchStatus.MATCHED)
        self.assertEqual(result.best_candidate.provider_id, "603")

    def test_same_title_different_year_original_and_alternative_titles(self) -> None:
        cases = (
            (
                ParseResult("Example", year=2024),
                (
                    MediaCandidate("tmdb", "1", MediaType.MOVIE, "Example", year=1999),
                    MediaCandidate("tmdb", "2", MediaType.MOVIE, "Example", year=2024),
                ),
                "2",
            ),
            (
                ParseResult("千と千尋の神隠し", year=2001),
                (
                    MediaCandidate(
                        "tmdb", "3", MediaType.MOVIE, "Spirited Away", "千と千尋の神隠し", 2001
                    ),
                ),
                "3",
            ),
            (
                ParseResult("Matrix", year=1999),
                (
                    MediaCandidate(
                        "tmdb",
                        "603",
                        MediaType.MOVIE,
                        "The Matrix",
                        year=1999,
                        alternative_titles=("Matrix",),
                    ),
                ),
                "603",
            ),
        )
        for parsed, candidates, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    self.matcher.match(parsed, candidates, self.policy).best_candidate.provider_id,
                    expected,
                )

    def test_missing_year_needs_confirmation_and_low_score_not_found(self) -> None:
        exact = self.matcher.match(
            ParseResult("The Matrix"),
            (MediaCandidate("tmdb", "603", MediaType.MOVIE, "The Matrix", year=1999),),
            self.policy,
        )
        low = self.matcher.match(
            ParseResult("Completely Different"),
            (MediaCandidate("tmdb", "1", MediaType.MOVIE, "Other"),),
            self.policy,
        )
        self.assertEqual(exact.status, CandidateMatchStatus.NEED_CONFIRM)
        self.assertEqual(low.status, CandidateMatchStatus.NOT_FOUND)

    def test_close_scores_are_ambiguous_and_order_is_deterministic(self) -> None:
        candidates = (
            MediaCandidate("tmdb", "20", MediaType.MOVIE, "Example", year=2024),
            MediaCandidate("tmdb", "10", MediaType.MOVIE, "Example", year=2024),
        )
        first = self.matcher.match(ParseResult("Example", year=2024), candidates, self.policy)
        second = self.matcher.match(
            ParseResult("Example", year=2024), tuple(reversed(candidates)), self.policy
        )
        self.assertEqual(first.status, CandidateMatchStatus.AMBIGUOUS)
        self.assertEqual(first, second)
        self.assertEqual(first.best_candidate.provider_id, "10")

    def test_localized_and_alternative_titles_are_strong_explainable_evidence(self) -> None:
        cases = (
            ("哈姆奈特", 2025, "Hamnet", ("哈姆奈特",)),
            ("千与千寻", 2001, "Spirited Away", ("千与千寻", "千と千尋の神隠し")),
        )
        for local_title, year, provider_title, alternatives in cases:
            with self.subTest(local_title=local_title):
                result = self.matcher.match(
                    ParseResult(local_title, year=year),
                    (
                        MediaCandidate(
                            "tmdb",
                            "858024",
                            MediaType.MOVIE,
                            provider_title,
                            year=year,
                            alternative_titles=alternatives,
                        ),
                    ),
                    self.policy,
                )
                self.assertEqual(result.status, CandidateMatchStatus.MATCHED)
                score = result.candidate_scores[0]
                self.assertEqual(score.matched_provider_title, local_title)
                self.assertEqual(score.matched_title_source, "alternative_title")
                self.assertIn("exact alternative_title match", score.components[0].reason)

    def test_same_year_without_title_evidence_does_not_match(self) -> None:
        result = self.matcher.match(
            ParseResult("完全不同的中文标题", year=2025),
            (MediaCandidate("tmdb", "1", MediaType.MOVIE, "Unrelated Film", year=2025),),
            self.policy,
        )
        self.assertEqual(result.status, CandidateMatchStatus.NOT_FOUND)

    def test_identical_alternative_titles_remain_ambiguous(self) -> None:
        candidates = tuple(
            MediaCandidate(
                "tmdb",
                str(number),
                MediaType.MOVIE,
                title,
                year=2025,
                alternative_titles=("同名电影",),
            )
            for number, title in ((1, "Film One"), (2, "Film Two"))
        )
        result = self.matcher.match(ParseResult("同名电影", year=2025), candidates, self.policy)
        self.assertEqual(result.status, CandidateMatchStatus.AMBIGUOUS)

    def test_canonical_year_outranks_regional_release_year(self) -> None:
        candidates = (
            MediaCandidate("tmdb", "535075", MediaType.MOVIE, "千与千寻诞生秘话", year=2001),
            MediaCandidate(
                "tmdb",
                "129",
                MediaType.MOVIE,
                "千与千寻",
                "千と千尋の神隠し",
                2001,
                canonical_release_date="2001-07-20",
                regional_release_date="2019-06-21",
            ),
        )
        result = self.matcher.match(ParseResult("千与千寻", year=2001), candidates, self.policy)
        self.assertEqual(result.status, CandidateMatchStatus.MATCHED)
        self.assertEqual(result.best_candidate.provider_id, "129")
        best = result.candidate_scores[0]
        self.assertTrue(best.exact_year)
        self.assertEqual(best.candidate.canonical_year, 2001)
        self.assertEqual(best.candidate.regional_year, 2019)
        self.assertIn("canonical year difference is 0", best.components[1].reason)
        self.assertEqual(
            next(item for item in best.components if item.name == "regional_year").score, 0
        )

    def test_regional_filename_year_does_not_redefine_canonical_identity(self) -> None:
        candidate = MediaCandidate(
            "tmdb",
            "129",
            MediaType.MOVIE,
            "千与千寻",
            year=2001,
            canonical_release_date="2001-07-20",
            regional_release_date="2019-06-21",
        )
        result = self.matcher.match(ParseResult("千与千寻", year=2019), (candidate,), self.policy)
        self.assertNotEqual(result.status, CandidateMatchStatus.MATCHED)
        self.assertFalse(result.candidate_scores[0].exact_year)

    def test_missing_local_year_has_no_date_penalty(self) -> None:
        candidate = MediaCandidate(
            "tmdb",
            "129",
            MediaType.MOVIE,
            "千与千寻",
            year=2001,
            regional_release_date="2019-06-21",
        )
        result = self.matcher.match(ParseResult("千与千寻"), (candidate,), self.policy)
        year = next(item for item in result.candidate_scores[0].components if item.name == "year")
        self.assertEqual(year.score, 0)

    def test_same_title_remake_uses_canonical_year(self) -> None:
        candidates = (
            MediaCandidate("tmdb", "1", MediaType.MOVIE, "Movie X", year=1999),
            MediaCandidate("tmdb", "2", MediaType.MOVIE, "Movie X", year=2024),
        )
        result = self.matcher.match(ParseResult("Movie X", year=2024), candidates, self.policy)
        self.assertEqual(result.best_candidate.provider_id, "2")


class FakeProvider:
    provider_id = "tmdb"
    capabilities = ProviderCapabilities(True, True, True, True, True)

    def __init__(self, *, missing_episode=False) -> None:
        self.missing_episode = missing_episode
        self.calls = []

    def search_movie(self, query, policy=None, **kwargs):
        self.calls.append("search_movie")
        return (
            MediaCandidate("tmdb", "603", MediaType.MOVIE, query.title_candidate, year=query.year),
        )

    def get_movie(self, provider_id, policy=None, **kwargs):
        self.calls.append("get_movie")
        return MediaIdentity("tmdb", provider_id, MediaType.MOVIE, "The Matrix", year=1999)

    def search_tv(self, query, policy=None, **kwargs):
        self.calls.append("search_tv")
        return (MediaCandidate("tmdb", "10", MediaType.TV, query.title_candidate, year=query.year),)

    def get_tv(self, provider_id, policy=None, **kwargs):
        self.calls.append("get_tv")
        return MediaIdentity("tmdb", provider_id, MediaType.TV, "Show", year=2020)

    def get_season(self, provider_id, season, policy=None, **kwargs):
        self.calls.append("get_season")
        episodes = (
            (EpisodeIdentity(1, "One"),)
            if self.missing_episode
            else (EpisodeIdentity(1, "One"), EpisodeIdentity(2, "Two"))
        )
        return MediaIdentity(
            "tmdb", provider_id, MediaType.TV, "Season", season=season, episode_metadata=episodes
        )


class LocalizedProvider(FakeProvider):
    capabilities = ProviderCapabilities(True, True, True, True, True, False, True)

    def __init__(self, candidates, identities) -> None:
        super().__init__()
        self.candidates = tuple(candidates)
        self.identities = identities

    def search_movie(self, query, policy=None, **kwargs):
        self.calls.append("search_movie")
        return self.candidates

    def get_movie(self, provider_id, policy=None, **kwargs):
        self.calls.append(f"get_movie:{provider_id}")
        return self.identities[provider_id]


class MetadataServiceAndCacheTests(unittest.TestCase):
    def test_region_adjusted_search_year_is_replaced_by_bounded_canonical_details(self) -> None:
        search = {
            "total_pages": 1,
            "results": [
                {
                    "id": 535075,
                    "title": "千与千寻诞生秘话",
                    "original_title": "The Making of Spirited Away",
                    "release_date": "2001-01-01",
                },
                {
                    "id": 129,
                    "title": "千与千寻",
                    "original_title": "千と千尋の神隠し",
                    "release_date": "2019-06-21",
                },
            ],
        }
        correct_details = {
            "id": 129,
            "title": "千与千寻",
            "original_title": "千と千尋の神隠し",
            "release_date": "2001-07-20",
        }
        documentary_details = {
            "id": 535075,
            "title": "千与千寻诞生秘话",
            "original_title": "The Making of Spirited Away",
            "release_date": "2001-01-01",
        }
        transport = FakeTransport(
            tuple(
                FakeResponse(200, item) for item in (search, correct_details, documentary_details)
            )
        )
        service = MetadataIdentificationService(
            MetadataProviderRegistry((TMDBProvider(TMDBClient(config(), transport)),))
        )
        result = service.identify(
            RecognitionResult(RecognitionType("A", "A"), "movie"),
            ParseResult("千与千寻", year=2001),
            policy(language="zh-CN", region="CN", max_search_pages=1),
        )
        self.assertEqual(result.status, MetadataIdentificationStatus.MATCHED)
        self.assertEqual(result.identity.provider_id, "129")
        self.assertEqual(result.identity.year, 2001)
        self.assertEqual(result.identity.regional_year, 2019)
        self.assertEqual(result.match.best_candidate.canonical_year, 2001)
        self.assertEqual(result.match.best_candidate.regional_year, 2019)

    def test_bounded_details_enrichment_matches_localized_title_and_preserves_c(self) -> None:
        candidates = (
            MediaCandidate("tmdb", "1", MediaType.MOVIE, "Wrong", year=2025),
            MediaCandidate("tmdb", "858024", MediaType.MOVIE, "Hamnet", year=2025),
            MediaCandidate("tmdb", "3", MediaType.MOVIE, "Another", year=2025),
        )
        identities = {
            "1": MediaIdentity("tmdb", "1", MediaType.MOVIE, "Wrong", year=2025),
            "858024": MediaIdentity(
                "tmdb",
                "858024",
                MediaType.MOVIE,
                "Hamnet",
                year=2025,
                translated_titles=("哈姆奈特",),
            ),
            "3": MediaIdentity("tmdb", "3", MediaType.MOVIE, "Another", year=2025),
        }
        provider = LocalizedProvider(candidates, identities)
        result = MetadataIdentificationService(MetadataProviderRegistry((provider,))).identify(
            RecognitionResult(RecognitionType("C", "C"), "rule-c"),
            ParseResult("哈姆奈特", year=2025),
            policy(max_candidate_enrichments=2),
        )
        self.assertEqual(result.status, MetadataIdentificationStatus.MATCHED)
        self.assertEqual(result.identity.provider_id, "858024")
        self.assertEqual(result.recognition_type_id, "C")
        self.assertEqual(result.identity.recognition_type_id, "C")
        score = result.match.candidate_scores[0]
        self.assertEqual(score.matched_provider_title, "哈姆奈特")
        self.assertEqual(score.matched_title_source, "translation")
        self.assertEqual(provider.calls[0], "search_movie")
        self.assertEqual(len([call for call in provider.calls if call.startswith("get_movie:")]), 2)

    def test_enrichment_does_not_accept_same_year_without_localized_title(self) -> None:
        candidate = MediaCandidate("tmdb", "1", MediaType.MOVIE, "Unrelated", year=2025)
        provider = LocalizedProvider(
            (candidate,),
            {"1": MediaIdentity("tmdb", "1", MediaType.MOVIE, "Unrelated", year=2025)},
        )
        result = MetadataIdentificationService(MetadataProviderRegistry((provider,))).identify(
            RecognitionResult(RecognitionType("A", "A"), "rule-a"),
            ParseResult("中文标题", year=2025),
            policy(),
        )
        self.assertEqual(result.status, MetadataIdentificationStatus.NOT_FOUND)

    def test_recognition_type_c_remains_c_after_movie_identification(self) -> None:
        provider = FakeProvider()
        service = MetadataIdentificationService(MetadataProviderRegistry((provider,)))
        recognition = RecognitionResult(RecognitionType("C", "C"), "rule-c")
        result = service.identify(recognition, ParseResult("The Matrix", year=1999), policy())
        self.assertEqual(result.status, MetadataIdentificationStatus.MATCHED)
        self.assertEqual(result.recognition_type_id, "C")
        self.assertEqual(result.identity.recognition_type_id, "C")
        self.assertNotEqual(result.recognition_type_id, "A")

        direct = service.identify_by_provider_id(recognition, "603", MediaType.MOVIE, policy())
        self.assertEqual(direct.identity.provider_id, "603")
        self.assertEqual(direct.identity.recognition_type_id, "C")

    def test_multi_episode_is_verified_with_one_season_request(self) -> None:
        provider = FakeProvider()
        service = MetadataIdentificationService(MetadataProviderRegistry((provider,)))
        parsed = ParseResult("Show", year=2020, season=1, episode=1, episodes=(1, 2))
        result = service.identify(
            RecognitionResult(RecognitionType("B", "B"), "rule-b"), parsed, policy(MediaType.TV)
        )
        self.assertEqual(result.identity.episodes, (1, 2))
        self.assertEqual(
            tuple(item.title for item in result.identity.episode_metadata), ("One", "Two")
        )
        self.assertEqual(provider.calls.count("get_season"), 1)

    def test_invalid_episode_becomes_metadata_mismatch(self) -> None:
        provider = FakeProvider(missing_episode=True)
        service = MetadataIdentificationService(MetadataProviderRegistry((provider,)))
        parsed = ParseResult("Show", year=2020, season=1, episode=2, episodes=(2,))
        result = service.identify(
            RecognitionResult(RecognitionType("B", "B"), "rule-b"), parsed, policy(MediaType.TV)
        )
        self.assertEqual(result.status, MetadataIdentificationStatus.METADATA_MISMATCH)
        self.assertIsNone(result.identity)

    def test_request_budget_is_enforced(self) -> None:
        provider = FakeProvider()
        service = MetadataIdentificationService(MetadataProviderRegistry((provider,)))
        result = service.identify(
            RecognitionResult(RecognitionType("A", "A"), "rule-a"),
            ParseResult("The Matrix", year=1999),
            policy(max_provider_requests=1),
        )
        self.assertEqual(result.status, MetadataIdentificationStatus.PROVIDER_ERROR)
        self.assertEqual(result.error.code, MetadataErrorCode.INVALID_REQUEST)
        self.assertEqual(provider.calls, ["search_movie"])

    def test_cache_ttl_and_invalidation(self) -> None:
        now = [10.0]
        cache = MetadataCache(lambda: now[0])
        key = MetadataCacheKey("tmdb", "search_movie", (("query", "Matrix"),))
        cache.put(key, ("value",), 5)
        self.assertEqual(cache.get(key), ("value",))
        now[0] = 15.0
        self.assertIsNone(cache.get(key))
        cache.put(key, "new", 5)
        cache.invalidate(key)
        self.assertIsNone(cache.get(key))

    def test_registry_validation(self) -> None:
        provider = FakeProvider()
        self.assertIs(MetadataProviderRegistry((provider,)).resolve("tmdb"), provider)
        with self.assertRaises(ValueError):
            MetadataProviderRegistry((provider, provider))
        with self.assertRaises(LookupError):
            MetadataProviderRegistry(()).resolve("missing")


if __name__ == "__main__":
    unittest.main()
