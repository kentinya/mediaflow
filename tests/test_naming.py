from __future__ import annotations

import unittest
from dataclasses import replace

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.naming import (
    NamingEngine,
    NamingPolicyRegistry,
    NamingPreviewService,
    SafeTemplateRenderer,
)
from mediaflow.application.strategy_test import (
    ReadOnlyStrategyStorage,
    SyntheticMetadataProvider,
    default_strategy_runner,
)
from mediaflow.domain.metadata import MediaCandidate, MediaIdentity, MediaType
from mediaflow.domain.naming import (
    MissingVariableStrategy,
    NamingContext,
    NamingError,
    NamingErrorCode,
    NamingMediaTypeMode,
    NamingPolicy,
    NamingTemplate,
)
from mediaflow.domain.parser import ParseResult
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from tests.test_strategy_cli import DummyStorage

TITLE_CASES = (
    "The Matrix",
    "Dune: Part Two",
    "2001: A Space Odyssey",
    "Mission: Impossible",
    "AC/DC",
    "Movie?",
    'Quote"Title',
    "A<B>C",
    "Test|Name",
    "Star*Movie",
    "Back\\Slash",
    "../../Movie",
    "../Movie",
    "/absolute/path",
    "C:\\Windows",
    "\\\\server\\share",
    "s3://bucket/object",
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM9",
    "LPT1",
    "LPT9",
    ".",
    "..",
    "流浪地球",
    "你好，李焕英",
    "哈姆奈特",
    "君の名は。",
    "千と千尋の神隠し",
    "기생충",
    "Amélie",
    "Léon",
    "Das Leben der Anderen",
    "El laberinto del fauno",
    "Cidade de Deus",
    "Иди и смотри",
    "درباره الی",
    "The   Matrix",
    "The\tMatrix",
    "The\nMatrix",
    "The\u00a0Matrix",
    "Trailing. ",
    " leading space ",
    "Emoji 🎬 Movie",
    "e\u0301cole",
    "Movie [Extended]",
    "Movie - Director's Cut",
)


class NamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = NamingEngine()
        self.movie_policy = NamingPolicy("A", "Movie", media_type_mode=NamingMediaTypeMode.MOVIE)
        self.tv_policy = NamingPolicy("B", "TV", media_type_mode=NamingMediaTypeMode.TV)

    @staticmethod
    def context(
        *,
        media_type=MediaType.MOVIE,
        title="The Matrix",
        year=1999,
        season=None,
        episode=None,
        episodes=(),
        episode_title=None,
        original_title=None,
        provider="tmdb",
        provider_id="603",
        recognition_type="A",
        parsed=None,
        extension="MKV",
    ) -> NamingContext:
        identity = MediaIdentity(
            provider,
            provider_id,
            media_type,
            title,
            original_title,
            year,
            season,
            episode,
            tuple(episodes),
            episode_title,
            recognition_type_id=recognition_type,
        )
        parsed = parsed or ParseResult(title, extension=extension.lower())
        return NamingContext(recognition_type, identity, parsed, f"source.{extension}", extension)

    def test_movie_and_provider_id_naming(self) -> None:
        policy = replace(
            self.movie_policy,
            movie_directory_template="{title} ({year}) [tmdbid-{provider_id}]",
            movie_file_template="{title} ({year}) [tmdbid-{provider_id}].{ext}",
        )
        result = self.engine.name(
            self.context(title="哈姆奈特", year=2025, provider_id="858024"), policy
        )
        self.assertEqual(result.directory, "哈姆奈特 (2025) [tmdbid-858024]")
        self.assertEqual(result.filename, "哈姆奈特 (2025) [tmdbid-858024].mkv")

    def test_tv_single_episode_season_and_episode_zero(self) -> None:
        cases = (
            (1, 3, "Long, Long Time", "Season 01", "S01E03"),
            (0, 1, "Special", "Season 00", "S00E01"),
            (1, 0, "Pilot Zero", "Season 01", "S01E00"),
        )
        for season, episode, title, expected_season, expected_episode in cases:
            with self.subTest(season=season, episode=episode):
                result = self.engine.name(
                    self.context(
                        media_type=MediaType.TV,
                        title="The Last of Us",
                        year=2023,
                        season=season,
                        episode=episode,
                        episode_title=title,
                    ),
                    self.tv_policy,
                )
                self.assertEqual(result.directory_segments[1], expected_season)
                self.assertIn(expected_episode, result.filename)
                self.assertIn(title, result.filename)

    def test_multi_episode_contiguous_and_non_contiguous(self) -> None:
        cases = (
            ((1, 2), "S01E01-E02"),
            ((1, 2, 3), "S01E01-E03"),
            ((1, 3), "S01E01E03"),
            ((3, 1, 3), "S01E01E03"),
        )
        for episodes, expected in cases:
            with self.subTest(episodes=episodes):
                result = self.engine.name(
                    self.context(
                        media_type=MediaType.TV,
                        title="Show",
                        season=1,
                        episodes=episodes,
                    ),
                    self.tv_policy,
                )
                self.assertIn(expected, result.filename)
        self.assertNotIn(
            "E01-E03",
            self.engine.name(
                self.context(media_type=MediaType.TV, season=1, episodes=(1, 3)),
                self.tv_policy,
            ).filename,
        )

    def test_missing_year_and_episode_title_strategies(self) -> None:
        error_policy = replace(
            self.movie_policy, missing_variable_strategy=MissingVariableStrategy.ERROR
        )
        with self.assertRaisesRegex(NamingError, "year"):
            self.engine.name(self.context(year=None), error_policy)
        omitted = self.engine.name(self.context(year=None), self.movie_policy)
        self.assertEqual(omitted.directory, "The Matrix")
        self.assertEqual(omitted.filename, "The Matrix.mkv")
        empty = self.engine.name(
            self.context(year=None),
            replace(
                self.movie_policy,
                missing_variable_strategy=MissingVariableStrategy.EMPTY,
            ),
        )
        self.assertEqual(empty.directory, "The Matrix ()")
        tv = self.engine.name(
            self.context(media_type=MediaType.TV, season=1, episode=2), self.tv_policy
        )
        self.assertEqual(tv.filename, "The Matrix - S01E02.mkv")

    def test_parse_year_fallback_and_release_variables(self) -> None:
        parsed = ParseResult(
            "The Matrix",
            year=1999,
            resolution_tag="2160p",
            source_tag="WEB-DL",
            video_codec_tag="H265",
            audio_codec_tag="DDP",
            audio_channels_tag="5.1",
            hdr_tags=("DV", "HDR"),
            version_tags=("IMAX", "Extended"),
            release_group="GROUP",
            extension="mkv",
        )
        policy = replace(
            self.movie_policy,
            movie_file_template=(
                "{title} ({year}) [{resolution}] [{source}] [{video_codec}] "
                "[{audio}] [{hdr}] [{version}] [{release_group}].{ext}"
            ),
        )
        result = self.engine.name(self.context(year=None, parsed=parsed), policy)
        self.assertEqual(
            result.filename,
            "The Matrix (1999) [2160p] [WEB-DL] [H265] "
            "[DDP5.1] [DV HDR] [IMAX Extended] [GROUP].mkv",
        )
        self.assertIn("missing_year_fallback:parse_result", result.warnings)

    def test_numeric_formatting_and_extension_normalization(self) -> None:
        renderer = SafeTemplateRenderer()
        variables = {
            name: None
            for name in (
                "title",
                "original_title",
                "year",
                "season",
                "episode",
                "episodes",
                "episode_range",
                "episode_title",
                "provider",
                "provider_id",
                "resolution",
                "source",
                "video_codec",
                "audio",
                "audio_codec",
                "audio_channels",
                "hdr",
                "version",
                "release_group",
                "ext",
            )
        }
        variables.update(season=1, episode=2)
        rendered = renderer.render(
            NamingTemplate("S{season:03}E{episode:02}"),
            variables,
            MissingVariableStrategy.ERROR,
        )
        self.assertEqual(rendered.value, "S001E02")
        self.assertTrue(
            self.engine.name(self.context(extension="Mp4"), self.movie_policy).filename.endswith(
                ".mp4"
            )
        )

    def test_template_validation_and_policy_registry_errors(self) -> None:
        invalid = (
            ("{unknown}", NamingErrorCode.UNKNOWN_VARIABLE),
            ("{season:bad}", NamingErrorCode.INVALID_FORMAT_SPECIFIER),
            ("{title", NamingErrorCode.INVALID_TEMPLATE),
            ("../{title}", NamingErrorCode.UNSAFE_PATH),
            ("/absolute", NamingErrorCode.UNSAFE_PATH),
            ("C:\\Windows", NamingErrorCode.UNSAFE_PATH),
        )
        for template, code in invalid:
            with self.subTest(template=template), self.assertRaises(NamingError) as raised:
                NamingPolicyRegistry(
                    (replace(self.movie_policy, movie_directory_template=template),)
                )
            self.assertEqual(raised.exception.code, code)
        with self.assertRaises(NamingError) as missing:
            NamingPolicyRegistry(()).resolve("missing")
        self.assertEqual(missing.exception.code, NamingErrorCode.POLICY_NOT_FOUND)
        with self.assertRaises(NamingError) as disabled:
            NamingPolicyRegistry((replace(self.movie_policy, enabled=False),)).resolve("A")
        self.assertEqual(disabled.exception.code, NamingErrorCode.POLICY_DISABLED)

    def test_fifty_representative_titles_are_safe_unicode_and_deterministic(self) -> None:
        self.assertEqual(len(TITLE_CASES), 50)
        for title in TITLE_CASES:
            with self.subTest(title=title):
                context = self.context(title=title)
                first = self.engine.name(context, self.movie_policy)
                second = self.engine.name(context, self.movie_policy)
                self.assertEqual(first, second)
                for component in (*first.directory_segments, first.filename):
                    self.assertTrue(component)
                    self.assertNotIn("/", component)
                    self.assertNotIn("\\", component)
                    self.assertNotIn("\x00", component)
                    self.assertNotIn(component, (".", ".."))
        self.assertEqual(
            self.engine.name(
                self.context(title="Mission: Impossible"), self.movie_policy
            ).directory,
            "Mission - Impossible (1999)",
        )
        self.assertEqual(
            self.engine.name(self.context(title="AC/DC"), self.movie_policy).directory,
            "AC DC (1999)",
        )
        self.assertIn(
            "Amélie", self.engine.name(self.context(title="Amélie"), self.movie_policy).directory
        )

    def test_long_component_preserves_extension_and_suffix(self) -> None:
        policy = replace(
            self.movie_policy,
            movie_directory_template="{title} [tmdbid-{provider_id}]",
            movie_file_template="{title} [tmdbid-{provider_id}].{ext}",
            max_component_length=80,
        )
        result = self.engine.name(self.context(title="非常长的电影标题" * 30), policy)
        self.assertLessEqual(len(result.directory), 80)
        self.assertLessEqual(len(result.filename), 80)
        self.assertTrue(result.filename.endswith("[tmdbid-603].mkv"))
        self.assertIn("component_truncated", result.warnings)

    def test_c_uses_naming_a_and_remains_c(self) -> None:
        configuration = development_strategy_configuration()
        strategy = default_strategy_runner().run_path("/C/The.Matrix.1999.mkv")
        registry = NamingPolicyRegistry(configuration.naming_policies)
        result = NamingPreviewService(registry).preview(
            self.context(recognition_type="C"), strategy.policy.naming_policy_id
        )
        self.assertEqual(strategy.policy.naming_policy_id, "A")
        self.assertEqual(result.policy_id, "A")
        self.assertEqual(result.recognition_type_id, "C")
        self.assertEqual(strategy.recognition.recognition_type_id, "C")

    def test_parse_recognition_metadata_naming_pipeline_has_no_side_effects(self) -> None:
        provider = SyntheticMetadataProvider(
            (MediaCandidate("tmdb", "603", MediaType.MOVIE, "The Matrix", year=1999),)
        )
        guard = ReadOnlyStrategyStorage(DummyStorage())
        strategy = default_strategy_runner(
            MetadataProviderRegistry((provider,)), storage_guard=guard
        ).run_path("/C/The.Matrix.1999.2160p.WEB-DL.mkv", live_metadata=True)
        calls_before_naming = provider.calls
        result = NamingPreviewService(
            NamingPolicyRegistry(development_strategy_configuration().naming_policies)
        ).preview(
            NamingContext(
                strategy.recognition.recognition_type_id,
                strategy.metadata.identity,
                strategy.parsed,
                strategy.parsed.original_filename,
                strategy.parsed.extension,
            ),
            strategy.policy.naming_policy_id,
        )
        self.assertEqual(result.directory_segments, ("The Matrix (1999)",))
        self.assertEqual(result.filename, "The Matrix (1999).mkv")
        self.assertEqual(result.recognition_type_id, "C")
        self.assertEqual(provider.calls, calls_before_naming)
        self.assertTrue(all(count == 0 for count in guard.mutation_calls.values()))
        self.assertFalse(hasattr(self.engine, "storage"))
        self.assertFalse(hasattr(self.engine, "metadata_provider"))


if __name__ == "__main__":
    unittest.main()
