from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import (
    ReadOnlyStrategyStorage,
    StrategyConfigurationError,
    StrategyDirectoryRunner,
    StrategyMutationError,
    StrategyTestConfiguration,
    SyntheticMetadataProvider,
    default_strategy_runner,
    strategy_runner_from_configuration,
)
from mediaflow.cli import main, render_strategy_result
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.storage import StorageCapabilities
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration


class DummyStorage:
    storage_id = "dummy"
    name = "Dummy"
    read_only = False
    capabilities = StorageCapabilities(True, True, True, True, True)

    def list(self, path):
        return ()

    def stat(self, path):
        raise FileNotFoundError(path)

    def exists(self, path):
        return False

    def read(self, path):
        return io.BytesIO(b"safe")


class StrategyCLITests(unittest.TestCase):
    @staticmethod
    def missing_a_policy_runner():
        configuration = development_strategy_configuration()
        incomplete = StrategyTestConfiguration(
            configuration.recognition_types,
            configuration.recognition_rules,
            configuration.recognition_type_policies,
            tuple(policy for policy in configuration.metadata_policies if policy.policy_id != "A"),
        )
        return strategy_runner_from_configuration(incomplete)

    def test_offline_pipeline_displays_all_stages_and_c_mapping(self) -> None:
        output, errors = io.StringIO(), io.StringIO()
        code = main(
            [
                "--offline",
                "/C/The.Matrix.1999.2160p.WEB-DL.x265.mkv",
                "--resource-library-id",
                "special",
            ],
            stdout=output,
            stderr=errors,
        )
        value = output.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(errors.getvalue(), "")
        for heading in (
            "PARSER",
            "RECOGNITION",
            "RECOGNITION TYPE POLICY",
            "METADATA",
            "CANDIDATES",
            "MATCH RESULT",
            "FINAL",
        ):
            self.assertIn(heading, value)
        self.assertIn("RecognitionType: C", value)
        self.assertIn("MetadataPolicy: C", value)
        self.assertIn("NamingPolicy: A", value)
        self.assertIn("ClassificationPolicy: A", value)
        self.assertIn("OrganizePolicy: A", value)
        self.assertIn("RecognitionType preserved: YES", value)
        self.assertIn("Storage mutations: 0", value)

    def test_offline_mode_never_calls_metadata_provider(self) -> None:
        provider = SyntheticMetadataProvider(
            (MediaCandidate("tmdb", "603", MediaType.MOVIE, "The Matrix", year=1999),)
        )
        runner = default_strategy_runner(MetadataProviderRegistry((provider,)))
        runner.run_path("/C/The.Matrix.1999.mkv", live_metadata=False)
        self.assertEqual(provider.calls, 0)

    def test_offline_bootstrap_needs_no_tmdb_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            output, errors = io.StringIO(), io.StringIO()
            code = main(
                [
                    "--offline",
                    "/A/Movie.2024.mkv",
                    "--resource-library-id",
                    "movies",
                ],
                stdout=output,
                stderr=errors,
            )
        self.assertEqual(code, 0)
        self.assertEqual(errors.getvalue(), "")
        self.assertIn("MetadataPolicy: A", output.getvalue())

    def test_development_configuration_resolves_a_b_c_and_preserves_c(self) -> None:
        runner = default_strategy_runner()
        expected = {"A": ("A", "A", "A", "A"), "B": ("B", "B", "B", "B"), "C": ("C", "A", "A", "A")}
        for recognition_type, policy_ids in expected.items():
            with self.subTest(recognition_type=recognition_type):
                result = runner.run_path(f"/{recognition_type}/Title.2024.mkv")
                self.assertEqual(
                    (
                        result.policy.metadata_policy_id,
                        result.policy.naming_policy_id,
                        result.policy.classification_policy_id,
                        result.policy.organize_policy_id,
                    ),
                    policy_ids,
                )
                self.assertEqual(result.recognition.recognition_type_id, recognition_type)
        self.assertTrue(runner.run_path("/C/Title.2024.mkv").recognition_type_preserved)

    def test_missing_metadata_policy_is_a_clear_configuration_error(self) -> None:
        runner = self.missing_a_policy_runner()
        with self.assertRaisesRegex(
            StrategyConfigurationError,
            "MetadataPolicy 'A'.*RecognitionTypePolicy 'type-A'.*not configured",
        ):
            runner.validate_configuration()

    def test_directory_validates_global_configuration_before_scanning(self) -> None:
        class CountingScanner:
            calls = 0

            def scan(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("scan must not start")

        scanner = CountingScanner()
        guard = ReadOnlyStrategyStorage(DummyStorage())
        directory = StrategyDirectoryRunner(
            scanner,
            ResourceLibrary("test", "test", "dummy", ""),
            self.missing_a_policy_runner(),
            guard,
        )
        with self.assertRaises(StrategyConfigurationError):
            directory.run()
        self.assertEqual(scanner.calls, 0)
        self.assertTrue(all(count == 0 for count in guard.mutation_calls.values()))

    def test_directory_cli_reports_missing_policy_as_startup_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output, errors = io.StringIO(), io.StringIO()
            code = main(
                ["--directory", directory],
                stdout=output,
                stderr=errors,
                runner_factory=lambda live: self.missing_a_policy_runner(),
            )
        self.assertEqual(code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("ConfigurationError: MetadataPolicy 'A'", errors.getvalue())
        self.assertIn("RecognitionTypePolicy 'type-A'", errors.getvalue())
        self.assertNotIn("error |", errors.getvalue())

    def test_live_metadata_uses_real_pipeline_and_wrong_first_is_not_selected(self) -> None:
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate("tmdb", "1", MediaType.MOVIE, "The Matrix Resurrections", year=2021),
                MediaCandidate("tmdb", "603", MediaType.MOVIE, "The Matrix", year=1999),
            )
        )
        runner = default_strategy_runner(MetadataProviderRegistry((provider,)))
        result = runner.run_path("/C/The.Matrix.1999.mkv", live_metadata=True)
        self.assertEqual(result.metadata.identity.provider_id, "603")
        self.assertEqual(result.metadata_policy.policy_id, "C")
        self.assertEqual(result.metadata.recognition_type_id, "C")
        output = render_strategy_result(result)
        self.assertIn("Provider ID: 1", output)
        self.assertIn("Provider ID: 603", output)
        self.assertIn("Score breakdown:", output)
        self.assertIn("Selected provider ID: 603", output)

    def test_show_plan_runs_complete_preview_without_execution(self) -> None:
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "129",
                    MediaType.MOVIE,
                    "Spirited Away",
                    year=2001,
                    genres=("Animation",),
                    countries=("Japan",),
                ),
            )
        )
        guard = ReadOnlyStrategyStorage(DummyStorage())
        runner = strategy_runner_from_configuration(
            development_strategy_configuration(), MetadataProviderRegistry((provider,)), guard
        )
        output, errors = io.StringIO(), io.StringIO()
        code = main(
            [
                "--live-metadata",
                "--show-naming",
                "--show-classification",
                "--show-plan",
                "--resource-library-id",
                "movies",
                "/movies/Spirited.Away.2001.mkv",
            ],
            stdout=output,
            stderr=errors,
            runner_factory=lambda live: runner,
        )
        value = output.getvalue()
        self.assertEqual(0, code)
        self.assertEqual("", errors.getvalue())
        self.assertIn("ORGANIZE PLAN", value)
        self.assertIn("Operation: MOVE", value)
        self.assertIn(
            "Destination: Movies/Anime/Spirited Away (2001)/Spirited Away (2001).mkv", value
        )
        self.assertIn("Execution: NOT EXECUTED", value)
        self.assertIn("EXECUTION RESULT", value)
        self.assertIn("Status: DRY_RUN", value)
        self.assertTrue(all(count == 0 for count in guard.mutation_calls.values()))

    def test_execute_flag_moves_one_local_file_only_when_explicit(self) -> None:
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "129",
                    MediaType.MOVIE,
                    "Spirited Away",
                    year=2001,
                    genres=("Animation",),
                    countries=("Japan",),
                ),
            )
        )
        runner = strategy_runner_from_configuration(
            development_strategy_configuration(), MetadataProviderRegistry((provider,))
        )
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            source = os.path.join(source_root, "Spirited.Away.2001.mkv")
            with open(source, "wb") as handle:
                handle.write(b"media")
            dry_output, dry_errors = io.StringIO(), io.StringIO()
            dry_code = main(
                [
                    "--live-metadata",
                    "--show-plan",
                    "--execution-root",
                    target_root,
                    "--resource-library",
                    "movies",
                    source,
                ],
                stdout=dry_output,
                stderr=dry_errors,
                runner_factory=lambda live: runner,
            )
            relative_destination = "Movies/Anime/Spirited Away (2001)/Spirited Away (2001).mkv"
            resolved_destination = os.path.join(target_root, relative_destination)
            self.assertEqual(0, dry_code)
            self.assertEqual("", dry_errors.getvalue())
            self.assertTrue(os.path.exists(source))
            self.assertIn(f"Source: {source}", dry_output.getvalue())
            self.assertIn(f"Destination: {relative_destination}", dry_output.getvalue())
            self.assertIn(f"Resolved destination: {resolved_destination}", dry_output.getvalue())
            self.assertIn("Status: DRY_RUN", dry_output.getvalue())
            output, errors = io.StringIO(), io.StringIO()
            code = main(
                [
                    "--live-metadata",
                    "--show-plan",
                    "--execute",
                    "--execution-root",
                    target_root,
                    "--resource-library",
                    "movies",
                    source,
                ],
                stdout=output,
                stderr=errors,
                runner_factory=lambda live: runner,
            )
            destination = os.path.join(
                target_root,
                "Movies",
                "Anime",
                "Spirited Away (2001)",
                "Spirited Away (2001).mkv",
            )
            self.assertEqual(0, code)
            self.assertEqual("", errors.getvalue())
            self.assertFalse(os.path.exists(source))
            self.assertEqual(b"media", Path(destination).read_bytes())
            self.assertIn("Mode: EXECUTE", output.getvalue())
            self.assertIn("Status: SUCCESS", output.getvalue())
            self.assertIn(f"Source: {source}", output.getvalue())
            self.assertIn(f"Resolved destination: {destination}", output.getvalue())

    def test_live_metadata_displays_localized_title_match_evidence(self) -> None:
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "858024",
                    MediaType.MOVIE,
                    "Hamnet",
                    year=2025,
                    translated_titles=("哈姆奈特",),
                ),
            )
        )
        runner = default_strategy_runner(MetadataProviderRegistry((provider,)))
        result = runner.run_path(
            "/A/哈姆奈特 (2025)/哈姆奈特 (2025).mkv",
            live_metadata=True,
            resource_library_id="movies",
        )
        output = render_strategy_result(result)
        self.assertIn("TMDB query language: en-US", output)
        self.assertIn("Matched provider title: 哈姆奈特", output)
        self.assertIn("Matched title source: translation", output)
        self.assertIn("exact translation match", output)
        self.assertIn("Status: matched", output)

    def test_candidate_output_distinguishes_canonical_and_regional_year(self) -> None:
        provider = SyntheticMetadataProvider(
            (
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
        )
        result = default_strategy_runner(MetadataProviderRegistry((provider,))).run_path(
            "/A/千与千寻 (2001).mkv", live_metadata=True
        )
        output = render_strategy_result(result)
        self.assertIn("Canonical year: 2001", output)
        self.assertIn("Regional year: 2019", output)
        self.assertIn("canonical year difference is 0", output)
        self.assertIn("regional release year 2019 is informational only", output)
        self.assertEqual(result.metadata.identity.year, 2001)

    def test_ambiguous_and_no_result_are_visible(self) -> None:
        cases = (
            (
                (
                    MediaCandidate("tmdb", "1", MediaType.MOVIE, "Example", year=2024),
                    MediaCandidate("tmdb", "2", MediaType.MOVIE, "Example", year=2024),
                ),
                "/A/Example.2024.mkv",
                "ambiguous",
            ),
            ((), "/A/Missing.2024.mkv", "not_found"),
        )
        for candidates, path, expected in cases:
            with self.subTest(expected=expected):
                provider = SyntheticMetadataProvider(candidates)
                runner = default_strategy_runner(MetadataProviderRegistry((provider,)))
                result = runner.run_path(path, live_metadata=True)
                self.assertEqual(result.metadata.status.value, expected)

    def test_case_file_runner_and_starter_dataset(self) -> None:
        output, errors = io.StringIO(), io.StringIO()
        code = main(["--cases", "testdata/strategy/cases.json"], stdout=output, stderr=errors)
        self.assertEqual(code, 0)
        self.assertIn("Total: 14", output.getvalue())
        self.assertIn("Passed: 14", output.getvalue())
        self.assertIn("Failed: 0", output.getvalue())

    def test_expectation_mismatch_reports_expected_actual_and_evidence(self) -> None:
        document = {
            "cases": [
                {
                    "name": "intentional-failure",
                    "path": "/C/The.Matrix.1999.mkv",
                    "expect": {"recognitionType": "A"},
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "cases.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(document, handle)
            output = io.StringIO()
            code = main(["--cases", path], stdout=output, stderr=io.StringIO())
        self.assertEqual(code, 1)
        self.assertIn("Expected:", output.getvalue())
        self.assertIn("Actual:", output.getvalue())
        self.assertIn("Matched rules:", output.getvalue())
        self.assertIn("Recognition evidence:", output.getvalue())

    def test_read_only_guard_rejects_every_mutation_immediately(self) -> None:
        guard = ReadOnlyStrategyStorage(DummyStorage())
        operations = (
            ("Write", lambda: guard.write("x", b"x")),
            ("CreateDirectory", lambda: guard.create_directory("x")),
            ("Move", lambda: guard.move("a", "b")),
            ("Copy", lambda: guard.copy("a", "b")),
            ("Delete", lambda: guard.delete("x")),
            ("HardLink", lambda: guard.hard_link("a", "b")),
            ("SoftLink", lambda: guard.soft_link("a", "b")),
        )
        for name, operation in operations:
            with self.subTest(name=name), self.assertRaises(StrategyMutationError):
                operation()
        self.assertEqual(guard.mutation_calls, {name: 1 for name, _ in operations})

    def test_complete_strategy_pipeline_has_zero_storage_mutations(self) -> None:
        guard = ReadOnlyStrategyStorage(DummyStorage())
        default_strategy_runner(storage_guard=guard).run_path("/C/The.Matrix.1999.mkv")
        self.assertEqual(
            guard.mutation_calls,
            {
                "Write": 0,
                "CreateDirectory": 0,
                "Move": 0,
                "Copy": 0,
                "Delete": 0,
                "HardLink": 0,
                "SoftLink": 0,
            },
        )

    def test_secret_is_redacted_from_cli_errors(self) -> None:
        secret = "do-not-print-this-token"

        def failing_factory(live):
            raise RuntimeError(f"Authorization: Bearer {secret}")

        output, errors = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"TMDB_ACCESS_TOKEN": secret}):
            code = main(
                ["--live-metadata", "/A/Movie.2024.mkv"],
                stdout=output,
                stderr=errors,
                runner_factory=failing_factory,
            )
        self.assertEqual(code, 2)
        self.assertNotIn(secret, errors.getvalue())
        self.assertIn("Authorization: Bearer ***", errors.getvalue())

    def test_directory_mode_reuses_scanner_filters_extensions_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            os.makedirs(os.path.join(directory, "C"))
            for filename in ("The.Matrix.1999.mkv", "Second.Movie.2020.mp4", "ignored.txt"):
                with open(os.path.join(directory, "C", filename), "wb") as handle:
                    handle.write(b"media")
            output, errors = io.StringIO(), io.StringIO()
            code = main(
                [
                    "--directory",
                    directory,
                    "--limit",
                    "1",
                    "--resource-library-id",
                    "special",
                ],
                stdout=output,
                stderr=errors,
            )
        value = output.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(errors.getvalue(), "")
        self.assertIn("Total: 1", value)
        self.assertIn("Matched: 1", value)
        self.assertIn(" | C | ", value)
        self.assertNotIn("ignored", value)
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

    def test_directory_defaults_offline_and_live_mode_uses_fake_provider(self) -> None:
        provider = SyntheticMetadataProvider(
            (MediaCandidate("tmdb", "603", MediaType.MOVIE, "The Matrix", year=1999),)
        )
        runner = default_strategy_runner(MetadataProviderRegistry((provider,)))
        with tempfile.TemporaryDirectory() as directory:
            os.makedirs(os.path.join(directory, "C"))
            with open(os.path.join(directory, "C", "The.Matrix.1999.mkv"), "wb") as handle:
                handle.write(b"media")
            offline = io.StringIO()
            self.assertEqual(
                main(
                    ["--directory", directory],
                    stdout=offline,
                    stderr=io.StringIO(),
                    runner_factory=lambda live: runner,
                ),
                0,
            )
            self.assertEqual(provider.calls, 0)
            self.assertIn("matched | C | The Matrix/1999 | offline/-", offline.getvalue())

            live = io.StringIO()
            self.assertEqual(
                main(
                    ["--directory", directory, "--live-metadata", "--limit", "20"],
                    stdout=live,
                    stderr=io.StringIO(),
                    runner_factory=lambda enabled: runner,
                ),
                0,
            )
        self.assertGreater(provider.calls, 0)
        self.assertIn("matched | C | The Matrix/1999 | matched/", live.getvalue())


if __name__ == "__main__":
    unittest.main()
