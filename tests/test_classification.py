from __future__ import annotations

import io
import unittest

from mediaflow.application.classification import (
    ClassificationEngine,
    ClassificationPolicyRegistry,
)
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import (
    ReadOnlyStrategyStorage,
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.cli import main
from mediaflow.domain.classification import (
    ClassificationContext,
    ClassificationError,
    ClassificationErrorCode,
    ClassificationPolicy,
    ClassificationRule,
    ClassificationStatus,
)
from mediaflow.domain.metadata import MediaCandidate, MediaIdentity, MediaType
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import RecognitionType
from mediaflow.infrastructure.strategy_configuration import smoke_strategy_configuration
from tests.test_strategy_cli import DummyStorage


def context(
    *,
    media_type=MediaType.MOVIE,
    title="Movie",
    year=2024,
    genres=(),
    countries=(),
    languages=(),
    keywords=(),
    recognition_type="A",
):
    return ClassificationContext(
        RecognitionType(recognition_type, recognition_type),
        MediaIdentity(
            "tmdb",
            "1",
            media_type,
            title,
            year=year,
            genres=tuple(genres),
            countries=tuple(countries),
            languages=tuple(languages),
            keywords=tuple(keywords),
        ),
        ParseResult(title, year=year),
    )


def rule(rule_id, category, *, priority=0, **conditions):
    return ClassificationRule(
        rule_id,
        rule_id,
        "movies",
        "Movies",
        category,
        priority=priority,
        **conditions,
    )


class ClassificationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ClassificationEngine()

    def test_movie_animation_and_action_classification(self) -> None:
        policy = ClassificationPolicy(
            "A",
            "Movies",
            (
                rule(
                    "animation-movie",
                    "Animation",
                    priority=100,
                    media_types=(MediaType.MOVIE,),
                    genres=("Animation",),
                ),
                rule(
                    "action-movie",
                    "Action",
                    priority=90,
                    media_types=(MediaType.MOVIE,),
                    genres=("Action",),
                ),
            ),
        )
        cases = (("Animation", "animation-movie"), ("Action", "action-movie"))
        for genre, expected in cases:
            with self.subTest(genre=genre):
                result = self.engine.classify(context(genres=(genre,)), policy)
                self.assertEqual(result.status, ClassificationStatus.CLASSIFIED)
                self.assertEqual(result.matched_rule_id, expected)
                self.assertEqual(result.relative_path, genre)

    def test_tv_classification(self) -> None:
        policy = ClassificationPolicy(
            "B",
            "TV",
            (
                ClassificationRule(
                    "tv-series",
                    "TV Series",
                    "tv",
                    "TV Shows",
                    "Series",
                    media_types=(MediaType.TV,),
                ),
            ),
        )
        result = self.engine.classify(context(media_type=MediaType.TV), policy)
        self.assertEqual((result.library, result.category), ("TV Shows", "Series"))

    def test_anime_higher_priority_wins_animation_conflict(self) -> None:
        configuration = smoke_strategy_configuration()
        policy = configuration.classification_policies[0]
        result = self.engine.classify(context(genres=("Animation",), countries=("JP",)), policy)
        self.assertEqual(result.matched_rule_id, "anime-movie")
        self.assertEqual(result.category, "Anime")

    def test_country_language_year_and_keyword_conditions(self) -> None:
        policy = ClassificationPolicy(
            "A",
            "Movies",
            (
                rule(
                    "modern-marvel-japan",
                    "Special",
                    media_types=(MediaType.MOVIE,),
                    countries=("JP",),
                    languages=("ja",),
                    year_min=2020,
                    year_max=2030,
                    keywords=("Marvel",),
                ),
            ),
        )
        result = self.engine.classify(
            context(
                title="Marvel Story",
                countries=("jp",),
                languages=("JA",),
                keywords=("superhero",),
            ),
            policy,
        )
        self.assertEqual(result.status, ClassificationStatus.CLASSIFIED)
        self.assertIn("keyword=Marvel", result.evidence)

    def test_priority_and_equal_priority_order_are_deterministic(self) -> None:
        rules = (
            rule("z-rule", "Z", priority=100, genres=("Drama",)),
            rule("a-rule", "A", priority=100, genres=("Drama",)),
            rule("low", "Low", priority=1, genres=("Drama",)),
        )
        first = self.engine.classify(
            context(genres=("Drama",)), ClassificationPolicy("A", "A", rules)
        )
        second = self.engine.classify(
            context(genres=("Drama",)), ClassificationPolicy("A", "A", tuple(reversed(rules)))
        )
        self.assertEqual(first, second)
        self.assertEqual(first.matched_rule_id, "a-rule")

    def test_no_match_is_explicit_and_has_no_fallback(self) -> None:
        policy = ClassificationPolicy("A", "A", (rule("action", "Action", genres=("Action",)),))
        result = self.engine.classify(context(genres=("Comedy",)), policy)
        self.assertEqual(result.status, ClassificationStatus.UNCLASSIFIED)
        self.assertEqual(result.media_library_id, "")
        self.assertIsNone(result.matched_rule_id)

    def test_disabled_policy_and_registry_errors(self) -> None:
        disabled = ClassificationPolicy("A", "A", enabled=False)
        with self.assertRaises(ClassificationError) as caught:
            self.engine.classify(context(), disabled)
        self.assertEqual(caught.exception.code, ClassificationErrorCode.POLICY_DISABLED)
        registry = ClassificationPolicyRegistry((disabled,))
        with self.assertRaises(ClassificationError):
            registry.resolve("A")
        with self.assertRaises(ClassificationError):
            ClassificationPolicyRegistry((disabled, disabled))

    def test_c_reuses_policy_a_without_changing_recognition_type(self) -> None:
        policy = smoke_strategy_configuration().classification_policies[0]
        result = self.engine.classify(
            context(
                recognition_type="C",
                genres=("Animation",),
                countries=("JP",),
            ),
            policy,
        )
        self.assertEqual(result.policy_id, "A")
        self.assertEqual(result.recognition_type_id, "C")
        self.assertEqual(result.category, "Anime")

    def test_invalid_paths_and_ranges_are_rejected(self) -> None:
        with self.assertRaises(ClassificationError):
            rule("bad", "Bad", relative_category_path="../Bad")
        with self.assertRaises(ClassificationError):
            rule("bad-year", "Bad", year_min=2025, year_max=2020)

    def test_strategy_preview_pipeline_is_read_only(self) -> None:
        guard = ReadOnlyStrategyStorage(DummyStorage())
        candidate = MediaCandidate(
            "tmdb",
            "129",
            MediaType.MOVIE,
            "千与千寻",
            year=2001,
            genres=("Animation",),
            countries=("JP",),
            languages=("ja",),
        )
        provider = SyntheticMetadataProvider((candidate,))
        runner = strategy_runner_from_configuration(
            smoke_strategy_configuration(), MetadataProviderRegistry((provider,)), guard
        )
        output, errors = io.StringIO(), io.StringIO()
        code = main(
            [
                "--live-metadata",
                "--show-naming",
                "--show-classification",
                "/C/千与千寻.2001.mkv",
            ],
            stdout=output,
            stderr=errors,
            runner_factory=lambda live: runner,
        )
        value = output.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(errors.getvalue(), "")
        self.assertIn("CLASSIFICATION PREVIEW", value)
        self.assertIn("RecognitionType: C", value)
        self.assertIn("ClassificationPolicy: A", value)
        self.assertIn("Matched Rule: anime-movie", value)
        self.assertIn("Library: Movies", value)
        self.assertIn("Category: Anime", value)
        self.assertIn("Classification execution calls: 1", value)
        self.assertIn("Organizer execution calls: 0", value)
        self.assertTrue(all(count == 0 for count in guard.mutation_calls.values()))


if __name__ == "__main__":
    unittest.main()
