from __future__ import annotations

import json
import os
import tempfile
import unittest

from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import (
    ReadOnlyStrategyStorage,
    StrategyDirectoryRunner,
    strategy_runner_from_configuration,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.recognition import RecognitionStatus
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.strategy_configuration import (
    development_strategy_configuration,
    smoke_strategy_configuration,
)
from mediaflow.infrastructure.strategy_user_configuration import load_strategy_configuration


class StrategyConfigurationTests(unittest.TestCase):
    @staticmethod
    def document(root="/media/movies"):
        return {
            "version": 1,
            "resourceLibraries": [
                {"id": "movies", "rootPath": root},
                {"id": "tv", "rootPath": "/media/tv"},
                {"id": "special", "rootPath": "/media/special"},
            ],
            "recognitionTypes": [
                {"id": "A", "name": "Movie"},
                {"id": "B", "name": "TV"},
                {"id": "C", "name": "Special"},
            ],
            "recognitionRules": [
                {
                    "id": "movie-library",
                    "name": "Movies",
                    "priority": 100,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {
                        "field": "resource_library_id",
                        "operator": "equals",
                        "value": "movies",
                    },
                    "outputRecognitionType": "A",
                },
                {
                    "id": "tv-library",
                    "name": "TV",
                    "priority": 100,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {
                        "field": "resource_library_id",
                        "operator": "equals",
                        "value": "tv",
                    },
                    "outputRecognitionType": "B",
                },
                {
                    "id": "special-rule",
                    "name": "Special",
                    "priority": 100,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {
                        "field": "resource_library_id",
                        "operator": "equals",
                        "value": "special",
                    },
                    "outputRecognitionType": "C",
                },
            ],
            "recognitionTypePolicies": [
                {
                    "id": "type-A",
                    "recognitionType": "A",
                    "metadataPolicy": "A",
                    "namingPolicy": "A",
                    "classificationPolicy": "A",
                    "organizePolicy": "A",
                },
                {
                    "id": "type-B",
                    "recognitionType": "B",
                    "metadataPolicy": "B",
                    "namingPolicy": "B",
                    "classificationPolicy": "B",
                    "organizePolicy": "B",
                },
                {
                    "id": "type-C",
                    "recognitionType": "C",
                    "metadataPolicy": "C",
                    "namingPolicy": "A",
                    "classificationPolicy": "A",
                    "organizePolicy": "A",
                },
            ],
        }

    def test_user_resource_libraries_resolve_a_b_c_and_preserve_c(self) -> None:
        loaded = load_strategy_configuration(
            self.document(), base=development_strategy_configuration()
        )
        runner = strategy_runner_from_configuration(loaded.strategy)
        cases = (("movies", "A"), ("tv", "B"), ("special", "C"))
        for library_id, expected in cases:
            with self.subTest(library_id=library_id):
                result = runner.run_path("/Title.2025.mkv", resource_library_id=library_id)
                self.assertEqual(result.recognition.recognition_type_id, expected)
                self.assertEqual(result.policy.recognition_type_id, expected)
        special = runner.run_path("/Title.2025.mkv", resource_library_id="special")
        self.assertEqual(special.policy.metadata_policy_id, "C")
        self.assertEqual(special.policy.naming_policy_id, "A")
        self.assertEqual(special.policy.classification_policy_id, "A")
        self.assertEqual(special.policy.organize_policy_id, "A")
        self.assertTrue(special.recognition_type_preserved)

    def test_documented_example_configuration_loads(self) -> None:
        with open("config/strategy.example.json", encoding="utf-8") as handle:
            loaded = load_strategy_configuration(
                json.load(handle), base=development_strategy_configuration()
            )
        self.assertEqual(
            [binding.library_id for binding in loaded.resource_libraries],
            ["source"],
        )
        self.assertEqual(loaded.resource_libraries[0].root_path, "/mnt/HDD_2/Media")
        self.assertEqual(len(loaded.strategy.recognition_rules), 3)
        runner = strategy_runner_from_configuration(loaded.strategy)
        for path, expected in (
            ("Media/电影/Movie.2025.mkv", "A"),
            ("Media/电视剧/Show.S01E01.mkv", "B"),
            ("Media/C/Special.2025.mkv", "C"),
        ):
            with self.subTest(path=path):
                result = runner.run_path(path, resource_library_id="source")
                self.assertEqual(result.recognition.recognition_type_id, expected)
        policy_a = next(
            policy for policy in loaded.strategy.metadata_policies if policy.policy_id == "A"
        )
        self.assertEqual(policy_a.language, "zh-CN")
        self.assertEqual(policy_a.region, "CN")
        self.assertEqual(policy_a.max_candidate_enrichments, 2)

    def test_resource_library_binding_does_not_require_a_display_root(self) -> None:
        document = self.document()
        for library in document["resourceLibraries"]:
            library.pop("rootPath", None)
            library.pop("displayRootPath", None)
        loaded = load_strategy_configuration(document, base=development_strategy_configuration())
        self.assertTrue(all(item.root_path is None for item in loaded.resource_libraries))

    def test_metadata_policy_locale_and_enrichment_are_user_configurable(self) -> None:
        document = self.document()
        document["metadataPolicies"] = [
            {
                "id": "A",
                "language": "zh-CN",
                "region": "CN",
                "maxCandidateEnrichments": 1,
                "maxProviderRequests": 4,
            }
        ]
        policy_a = load_strategy_configuration(
            document, base=development_strategy_configuration()
        ).strategy.metadata_policies[0]
        self.assertEqual(
            (
                policy_a.language,
                policy_a.region,
                policy_a.max_candidate_enrichments,
                policy_a.max_provider_requests,
            ),
            ("zh-CN", "CN", 1, 4),
        )

    def test_unmatched_has_no_hidden_default_to_a(self) -> None:
        loaded = load_strategy_configuration(
            self.document(), base=development_strategy_configuration()
        )
        result = strategy_runner_from_configuration(loaded.strategy).run_path(
            "/Unknown.2025.mkv", resource_library_id="unconfigured"
        )
        self.assertEqual(result.recognition.status, RecognitionStatus.UNRECOGNIZED)
        self.assertIsNone(result.recognition.recognition_type_id)
        self.assertEqual(result.recognition.matched_rules, ())
        self.assertIsNone(result.policy)

    def test_smoke_fixture_and_development_configuration_are_separate(self) -> None:
        smoke = strategy_runner_from_configuration(smoke_strategy_configuration())
        development = strategy_runner_from_configuration(development_strategy_configuration())
        self.assertEqual(
            smoke.run_path("/A/Movie.2025.mkv").recognition.recognition_type_id,
            "A",
        )
        self.assertEqual(
            development.run_path(
                "/Movie.2025.mkv", resource_library_id="movies"
            ).recognition.recognition_type_id,
            "A",
        )
        self.assertEqual(
            development.run_path("/A/Movie.2025.mkv").recognition.status,
            RecognitionStatus.UNRECOGNIZED,
        )

    def test_directory_runner_uses_configured_library_and_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            media_root = os.path.join(directory, "电影")
            os.makedirs(os.path.join(media_root, "哈姆奈特 (2025)"))
            media_file = os.path.join(media_root, "哈姆奈特 (2025)", "哈姆奈特 (2025).mkv")
            with open(media_file, "wb") as handle:
                handle.write(b"media")
            loaded = load_strategy_configuration(
                self.document(media_root), base=development_strategy_configuration()
            )
            storage = LocalStorage("movies", media_root, read_only=True)
            guard = ReadOnlyStrategyStorage(storage)
            library = ResourceLibrary("movies", "Movies", "movies", "")
            runner = StrategyDirectoryRunner(
                StorageScanner({"movies": storage}),
                library,
                strategy_runner_from_configuration(loaded.strategy),
                guard,
            )
            summary = runner.run(limit=20)
        self.assertEqual(summary.matched, 1)
        self.assertEqual(summary.errors, 0)
        self.assertTrue(all(count == 0 for count in guard.mutation_calls.values()))

    def test_single_file_library_selection_and_unmatched_path(self) -> None:
        loaded = load_strategy_configuration(
            self.document(), base=development_strategy_configuration()
        )
        runner = strategy_runner_from_configuration(loaded.strategy)
        explicit = runner.run_path("/outside/Movie.2025.mkv", resource_library_id="movies")
        unmatched = runner.run_path("/outside/Movie.2025.mkv")
        special = runner.run_path("/outside/Special.2025.mkv", resource_library_id="special")
        self.assertEqual(explicit.recognition.recognition_type_id, "A")
        self.assertEqual(unmatched.recognition.status, RecognitionStatus.UNRECOGNIZED)
        self.assertIsNone(unmatched.recognition.recognition_type_id)
        self.assertEqual(special.recognition.recognition_type_id, "C")
        self.assertEqual(special.policy.metadata_policy_id, "C")
        self.assertEqual(special.policy.naming_policy_id, "A")
        self.assertTrue(special.recognition_type_preserved)

    def test_partial_document_requires_an_explicit_base(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit base"):
            load_strategy_configuration(self.document())


if __name__ == "__main__":
    unittest.main()
