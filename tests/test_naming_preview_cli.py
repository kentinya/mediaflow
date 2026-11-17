from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import (
    ReadOnlyStrategyStorage,
    StrategyDirectoryRunner,
    StrategyTestConfiguration,
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.cli import render_strategy_result
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.naming import MissingVariableStrategy
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.strategy_configuration import smoke_strategy_configuration
from tests.test_strategy_cli import DummyStorage


class NamingPreviewTests(unittest.TestCase):
    @staticmethod
    def runner(
        candidates,
        *,
        episodes=(),
        policy_a=None,
        guard=None,
    ):
        provider = SyntheticMetadataProvider(tuple(candidates), tuple(episodes))
        configuration = smoke_strategy_configuration()
        if policy_a is not None:
            policies = tuple(
                policy_a if policy.policy_id == "A" else policy
                for policy in configuration.naming_policies
            )
            configuration = StrategyTestConfiguration(
                configuration.recognition_types,
                configuration.recognition_rules,
                configuration.recognition_type_policies,
                configuration.metadata_policies,
                policies,
            )
        return (
            strategy_runner_from_configuration(
                configuration, MetadataProviderRegistry((provider,)), guard
            ),
            provider,
        )

    def test_movie_unicode_provider_id_c_and_safety_preview(self) -> None:
        configuration = smoke_strategy_configuration()
        policy_a = replace(
            configuration.naming_policies[0],
            movie_directory_template="{title} ({year}) [tmdbid-{provider_id}]",
            movie_file_template="{title} ({year}) [tmdbid-{provider_id}].{ext}",
        )
        guard = ReadOnlyStrategyStorage(DummyStorage())
        runner, _ = self.runner(
            (MediaCandidate("tmdb", "858024", MediaType.MOVIE, "哈姆奈特", year=2025),),
            policy_a=policy_a,
            guard=guard,
        )
        result = runner.run_path("/C/哈姆奈特.2025.mkv", live_metadata=True, show_naming=True)
        value = render_strategy_result(result)
        self.assertIn("NAMING PREVIEW", value)
        self.assertIn("RecognitionType: C", value)
        self.assertIn("NamingPolicy: A", value)
        self.assertIn("哈姆奈特 (2025) [tmdbid-858024]", value)
        self.assertIn("RecognitionType preserved: YES", value)
        self.assertIn("Classification execution calls: 0", value)
        self.assertIn("Organizer execution calls: 0", value)
        self.assertIn("Storage mutations: 0", value)
        self.assertTrue(all(count == 0 for count in guard.mutation_calls.values()))

    def test_tv_and_multi_episode_previews(self) -> None:
        candidate = MediaCandidate("tmdb", "100", MediaType.TV, "Show", year=2024)
        for path, episodes, expected in (
            ("/B/Show.2024.S01E03.mkv", (3,), "Show - S01E03 - Episode 3.mkv"),
            ("/B/Show.2024.S01E01E03.mkv", (1, 3), "Show - S01E01E03.mkv"),
        ):
            with self.subTest(path=path):
                runner, _ = self.runner((candidate,), episodes=episodes)
                result = runner.run_path(path, live_metadata=True, show_naming=True)
                value = render_strategy_result(result)
                self.assertEqual(result.naming.directory_segments, ("Show (2024)", "Season 01"))
                self.assertIn(expected, value)

    def test_sanitization_and_missing_variable_warning_and_error(self) -> None:
        configuration = smoke_strategy_configuration()
        base = configuration.naming_policies[0]
        warning_policy = replace(
            base,
            movie_directory_template="{title} ({year}) - {original_title}",
            movie_file_template="{title} ({year}) - {original_title}.{ext}",
        )
        candidate = MediaCandidate("tmdb", "1", MediaType.MOVIE, "Mission: Impossible", year=1996)
        warning_runner, _ = self.runner((candidate,), policy_a=warning_policy)
        warning = warning_runner.run_path(
            "/A/Mission.Impossible.1996.mkv", live_metadata=True, show_naming=True
        )
        value = render_strategy_result(warning)
        self.assertIn("Mission - Impossible (1996)", value)
        self.assertIn("missing_variable:original_title", value)

        error_policy = replace(
            warning_policy, missing_variable_strategy=MissingVariableStrategy.ERROR
        )
        error_runner, _ = self.runner((candidate,), policy_a=error_policy)
        error = error_runner.run_path(
            "/A/Mission.Impossible.1996.mkv", live_metadata=True, show_naming=True
        )
        self.assertIn(
            "error: required naming variable 'original_title' is missing",
            render_strategy_result(error),
        )

    def test_offline_show_naming_does_not_invent_identity(self) -> None:
        runner = strategy_runner_from_configuration(smoke_strategy_configuration())
        result = runner.run_path("/A/The.Matrix.1999.mkv", live_metadata=False, show_naming=True)
        value = render_strategy_result(result)
        self.assertIn("Status: unavailable: MediaIdentity required", value)
        self.assertIn("MediaIdentity unavailable; naming was not executed", value)

    def test_directory_naming_preview_limit_and_zero_mutation(self) -> None:
        candidate = MediaCandidate("tmdb", "603", MediaType.MOVIE, "The Matrix", year=1999)
        runner, _ = self.runner((candidate,))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for child in ("one", "two"):
                target = root / "A" / child
                target.mkdir(parents=True)
                (target / "The.Matrix.1999.mkv").write_bytes(b"media")
            storage = LocalStorage("strategy-directory", directory, read_only=True)
            guard = ReadOnlyStrategyStorage(storage)
            runner = StrategyDirectoryRunner(
                StorageScanner({"strategy-directory": storage}),
                ResourceLibrary("strategy-directory", "Directory", "strategy-directory", ""),
                runner,
                guard,
            )
            summary = runner.run(live_metadata=True, limit=1, show_naming=True)
        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.errors, 0)
        self.assertEqual(summary.naming_ok, 1)
        self.assertTrue(all(count == 0 for count in guard.mutation_calls.values()))

    def test_case_file_naming_expectations_and_mismatch_output(self) -> None:
        document = {
            "cases": [
                {
                    "name": "matrix-naming",
                    "path": "/A/The.Matrix.1999.mkv",
                    "candidates": [{"providerId": "603", "title": "The Matrix", "year": 1999}],
                    "expect": {
                        "recognitionType": "A",
                        "naming": {
                            "directory": "The Matrix (1999)",
                            "directorySegments": ["The Matrix (1999)"],
                            "filename": "The Matrix (1999).mkv",
                        },
                    },
                }
            ]
        }
        runner = strategy_runner_from_configuration(smoke_strategy_configuration())
        passed = runner.run_cases(document, show_naming=True)
        self.assertEqual((passed.total, passed.passed, passed.failed), (1, 1, 0))
        document["cases"][0]["expect"]["naming"]["filename"] = "Wrong.mkv"
        failed = runner.run_cases(document, show_naming=True)
        self.assertEqual(failed.failed, 1)
        case = failed.cases[0]
        self.assertEqual(case.expected["naming"]["filename"], "Wrong.mkv")
        self.assertEqual(case.actual["naming"]["filename"], "The Matrix (1999).mkv")


if __name__ == "__main__":
    unittest.main()
