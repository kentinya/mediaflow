"""Shared strategy engine and renderer tests.

The standalone ``strategy-test`` console was retired.  These tests keep the
current engine/renderer assertions that used to be reached through that
console: offline analysis, the C -> A naming/classification identity, the
read-only guard and the case runner.  The installed ``mediaflow`` command is
covered by the application CLI tests.
"""

from __future__ import annotations

import io
import unittest

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import (
    ReadOnlyStrategyStorage,
    StrategyMutationError,
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.cli import render_strategy_result
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.storage import StorageCapabilities
from mediaflow.infrastructure.strategy_configuration import (
    development_strategy_configuration,
    smoke_strategy_configuration,
)


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


class StrategyEngineTests(unittest.TestCase):
    def test_offline_pipeline_renders_all_stages_and_c_to_a_mapping(self) -> None:
        runner = strategy_runner_from_configuration(development_strategy_configuration())
        result = runner.run_path(
            "/C/The.Matrix.1999.2160p.WEB-DL.x265.mkv",
            live_metadata=False,
            resource_library_id="special",
        )
        value = render_strategy_result(result)
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
        runner = strategy_runner_from_configuration(
            smoke_strategy_configuration(), MetadataProviderRegistry((provider,))
        )
        result = runner.run_path("/C/The.Matrix.1999.mkv", live_metadata=False)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(result.recognition.recognition_type_id, "C")
        self.assertEqual(result.policy.naming_policy_id, "A")

    def test_read_only_guard_rejects_every_mutation_immediately(self) -> None:
        guard = ReadOnlyStrategyStorage(DummyStorage())
        calls = {
            "write": lambda: guard.write("path", io.BytesIO(b"x")),
            "create_directory": lambda: guard.create_directory("dir"),
            "move": lambda: guard.move("a", "b"),
            "copy": lambda: guard.copy("a", "b"),
            "delete": lambda: guard.delete("a"),
            "hard_link": lambda: guard.hard_link("a", "b"),
            "soft_link": lambda: guard.soft_link("a", "b"),
        }
        for operation, call in calls.items():
            with self.subTest(operation=operation), self.assertRaises(StrategyMutationError):
                call()

    def test_case_runner_reports_expected_actual_and_evidence(self) -> None:
        runner = strategy_runner_from_configuration(smoke_strategy_configuration())
        document = {
            "cases": [
                {
                    "name": "matched",
                    "path": "/C/The.Matrix.1999.mkv",
                    "expect": {"recognitionType": "C"},
                },
                {
                    "name": "mismatch",
                    "path": "/C/The.Matrix.1999.mkv",
                    "expect": {"recognitionType": "A"},
                },
            ]
        }
        summary = runner.run_cases(document)
        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.failed, 1)
        failed = next(item for item in summary.cases if not item.passed)
        self.assertEqual(failed.expected["recognitionType"], "A")
        self.assertEqual(failed.actual["recognitionType"], "C")


if __name__ == "__main__":
    unittest.main()
