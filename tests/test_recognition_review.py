from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.media_organizer import MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import (
    StrategyTestResult,
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import (
    RecognitionResult,
    RecognitionStatus,
    RecognitionType,
)
from mediaflow.domain.recognition_review import RecognitionReviewStatus, RecognitionSelection
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration


class FakeUnrecognizedStrategy:
    def run_path(self, path, **kwargs):
        return StrategyTestResult(
            path,
            ParseResult("Unknown", original_filename="Unknown.mkv", extension="mkv"),
            RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
            None,
        )


class RecognitionReviewTests(unittest.TestCase):
    def test_tracked_unrecognized_waits_with_enabled_choices_and_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteTaskRepository(Path(directory, "runtime.sqlite3"))
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("preview", execute_authorized=False)
            configuration = development_strategy_configuration()
            storage = LocalStorage("source", directory)
            service = MediaOrganizerService(
                FakeUnrecognizedStrategy(),
                StorageScanner({"source": storage}, InMemoryFileIndexRepository()),
                {"source": storage},
                {"movies": MediaLibrary("movies", "Movies", "source", "target")},
                configuration.recognition_type_policies,
                JsonLinesOperationHistoryRepository(Path(directory, "history.jsonl")),
                task_coordinator=coordinator,
                task_id=task.task_id,
            )
            result = service.process_file(
                "Unknown.mkv",
                resource_library=ResourceLibrary("unknown", "Unknown", "source", ""),
                storage_path="Unknown.mkv",
            )
            self.assertIsNone(result.error)
            item = repository.list_items(task.task_id)[0]
            self.assertEqual(item.status, TaskItemStatus.WAITING_RECOGNITION)
            review = repository.list_recognition_reviews()[0]
            self.assertEqual(review.status, RecognitionReviewStatus.PENDING)
            self.assertEqual(
                {
                    choice.recognition_type_id
                    for choice in repository.list_recognition_review_choices(review.review_id)
                },
                {"A", "B", "C"},
            )
            self.assertTrue(repository.acquire("source", "Unknown.mkv", "other", datetime.now(UTC)))
            locked = service.process_file(
                "Unknown.mkv",
                resource_library=ResourceLibrary("unknown", "Unknown", "source", ""),
                storage_path="Unknown.mkv",
            )
            self.assertIn("locked", locked.error)
            repository.close()

    def test_resolve_is_atomic_audited_and_rejects_stale_or_invalid_choice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "unknown", "Unknown.mkv", "Unknown.mkv"
                )
                types = (
                    RecognitionType("A", "Movie"),
                    RecognitionType("C", "Special"),
                    RecognitionType("disabled", "Disabled", enabled=False),
                )
                service = RecognitionReviewService(repository, types)
                review = service.create(
                    item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED)
                )
                with self.assertRaises(ValueError):
                    service.resolve(review.review_id, "disabled")
                with self.assertRaises(ValueError):
                    service.resolve(review.review_id, "missing")
                stale_service = RecognitionReviewService(
                    repository,
                    (
                        RecognitionType("A", "Movie", enabled=False),
                        RecognitionType("C", "Special"),
                    ),
                )
                with self.assertRaisesRegex(ValueError, "no longer enabled"):
                    stale_service.resolve(review.review_id, "A")
                resolved = service.resolve(
                    review.review_id, "C", actor=" operator ", note=" preserve C "
                )
                self.assertEqual(resolved.selected_recognition_type, "C")
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.PENDING)
                audit = repository.list_recognition_review_audit(review.review_id)
                self.assertEqual(audit[0].recognition_type_id, "C")
                self.assertEqual(audit[0].note, "preserve C")
                with self.assertRaises(ValueError):
                    service.resolve(review.review_id, "A")

    def test_manual_c_selection_uses_configured_policies_and_preserves_c(self) -> None:
        configuration = development_strategy_configuration()
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "1",
                    MediaType.MOVIE,
                    "Unknown",
                    year=2024,
                    genres=("Action",),
                    countries=("US",),
                ),
            )
        )
        result = strategy_runner_from_configuration(
            configuration, MetadataProviderRegistry((provider,))
        ).run_path(
            "/unknown/Unknown.2024.mkv",
            live_metadata=True,
            show_naming=True,
            show_classification=True,
            resource_library_id="unmatched",
            recognition_selection=RecognitionSelection("C"),
        )
        self.assertEqual(result.recognition.recognition_type_id, "C")
        self.assertEqual(result.policy.metadata_policy_id, "C")
        self.assertEqual(result.policy.naming_policy_id, "A")
        self.assertEqual(result.policy.classification_policy_id, "A")
        self.assertEqual(result.policy.organize_policy_id, "A")
        self.assertEqual(result.metadata.recognition_type_id, "C")
        self.assertTrue(result.recognition_type_preserved)

    def test_cli_review_commands_need_no_storage_or_provider_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = Path(directory, "strategy.json")
            config_path.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "missing-storage", "unknown", "Unknown.mkv", "Unknown.mkv"
                )
                review = RecognitionReviewService(
                    repository, development_strategy_configuration().recognition_types
                ).create(item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED))
            output, error = io.StringIO(), io.StringIO()
            code = final_main(
                [
                    "--config",
                    str(config_path),
                    "recognition-reviews",
                    "resolve",
                    review.review_id,
                    "--recognition-type",
                    "A",
                    "--actor",
                    "operator",
                ],
                stdout=output,
                stderr=error,
            )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("Selected RecognitionType: A", output.getvalue())
            self.assertNotIn("token", output.getvalue().casefold())
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
