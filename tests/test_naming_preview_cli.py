from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from dataclasses import replace

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import (
    ReadOnlyStrategyStorage,
    StrategyTestConfiguration,
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.cli import main
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.naming import MissingVariableStrategy
from mediaflow.infrastructure.strategy_configuration import smoke_strategy_configuration
from tests.test_strategy_cli import DummyStorage


class NamingPreviewCLITests(unittest.TestCase):
    @staticmethod
    def runner(
        candidates,
        *,
        media_type=MediaType.MOVIE,
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
        output, errors = io.StringIO(), io.StringIO()
        code = main(
            ["--live-metadata", "/C/哈姆奈特.2025.mkv", "--show-naming"],
            stdout=output,
            stderr=errors,
            runner_factory=lambda live: runner,
        )
        value = output.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(errors.getvalue(), "")
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
                runner, _ = self.runner((candidate,), media_type=MediaType.TV, episodes=episodes)
                output = io.StringIO()
                code = main(
                    ["--live-metadata", path, "--show-naming"],
                    stdout=output,
                    stderr=io.StringIO(),
                    runner_factory=lambda live, configured=runner: configured,
                )
                self.assertEqual(code, 0)
                self.assertIn("Directory segments: ['Show (2024)', 'Season 01']", output.getvalue())
                self.assertIn(expected, output.getvalue())

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
        output = io.StringIO()
        self.assertEqual(
            main(
                [
                    "--live-metadata",
                    "/A/Mission.Impossible.1996.mkv",
                    "--show-naming",
                ],
                stdout=output,
                stderr=io.StringIO(),
                runner_factory=lambda live: warning_runner,
            ),
            0,
        )
        self.assertIn("Mission - Impossible (1996)", output.getvalue())
        self.assertIn("missing_variable:original_title", output.getvalue())

        error_policy = replace(
            warning_policy, missing_variable_strategy=MissingVariableStrategy.ERROR
        )
        error_runner, _ = self.runner((candidate,), policy_a=error_policy)
        error_output = io.StringIO()
        self.assertEqual(
            main(
                [
                    "--live-metadata",
                    "/A/Mission.Impossible.1996.mkv",
                    "--show-naming",
                ],
                stdout=error_output,
                stderr=io.StringIO(),
                runner_factory=lambda live: error_runner,
            ),
            1,
        )
        self.assertIn(
            "error: required naming variable 'original_title' is missing", error_output.getvalue()
        )

    def test_offline_show_naming_does_not_invent_identity(self) -> None:
        output = io.StringIO()
        self.assertEqual(
            main(
                ["--offline", "/A/The.Matrix.1999.mkv", "--show-naming"],
                stdout=output,
                stderr=io.StringIO(),
            ),
            0,
        )
        self.assertIn("Status: unavailable: MediaIdentity required", output.getvalue())
        self.assertIn("MediaIdentity unavailable; naming was not executed", output.getvalue())

    def test_directory_naming_preview_limit_and_zero_mutation(self) -> None:
        candidate = MediaCandidate("tmdb", "603", MediaType.MOVIE, "The Matrix", year=1999)
        runner, _ = self.runner((candidate,))
        with tempfile.TemporaryDirectory() as directory:
            for child in ("one", "two"):
                target = os.path.join(directory, "A", child)
                os.makedirs(target)
                with open(os.path.join(target, "The.Matrix.1999.mkv"), "wb") as handle:
                    handle.write(b"media")
            output, errors = io.StringIO(), io.StringIO()
            code = main(
                [
                    "--directory",
                    directory,
                    "--live-metadata",
                    "--show-naming",
                    "--limit",
                    "1",
                ],
                stdout=output,
                stderr=errors,
                runner_factory=lambda live: runner,
            )
        value = output.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(errors.getvalue(), "")
        self.assertIn("PASS | A | The Matrix | 1999 | The Matrix (1999)", value)
        self.assertIn("Total: 1", value)
        self.assertIn("Naming OK: 1", value)
        self.assertIn("Classification executions: 0", value)
        self.assertIn("Organizer executions: 0", value)
        for operation in (
            "Write",
            "CreateDirectory",
            "Move",
            "Copy",
            "Delete",
            "HardLink",
            "SoftLink",
        ):
            self.assertIn(f"{operation}=0", value)

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
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "cases.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(document, handle)
            passed = io.StringIO()
            self.assertEqual(
                main(["--cases", path, "--show-naming"], stdout=passed, stderr=io.StringIO()),
                0,
            )
            self.assertIn("Passed: 1", passed.getvalue())
            document["cases"][0]["expect"]["naming"]["filename"] = "Wrong.mkv"
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(document, handle)
            failed = io.StringIO()
            self.assertEqual(
                main(["--cases", path, "--show-naming"], stdout=failed, stderr=io.StringIO()),
                1,
            )
        self.assertIn("Expected:", failed.getvalue())
        self.assertIn("Actual:", failed.getvalue())
        self.assertIn("Wrong.mkv", failed.getvalue())


if __name__ == "__main__":
    unittest.main()
