from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.strategy_test import strategy_runner_from_configuration
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.metadata import MetadataIdentificationStatus
from mediaflow.domain.metadata_correction import MetadataCorrectionStatus
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from tests.test_metadata_review import identification


class MetadataCorrectionBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = development_strategy_configuration()

    def _waiting(self, repository, number=1, task=None):
        coordinator = PersistentTaskCoordinator(repository, repository)
        if task is None:
            task = coordinator.create("preview", execute_authorized=False)
        item = coordinator.begin_item(
            task.task_id, "source", "movies", f"Unknown-{number}.mkv", f"Unknown-{number}.mkv"
        )
        policy = next(value for value in self.strategy.metadata_policies if value.policy_id == "A")
        review = MetadataCorrectionService(repository, self.strategy.metadata_policies).create(
            item,
            identification(MetadataIdentificationStatus.NOT_FOUND, count=0),
            policy,
            ParseResult("Unknown", year=2025),
        )
        return coordinator, task, item, review

    def test_batch_resolves_oldest_first_pending_corrections_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                first = self._waiting(repository, number=1, task=task)
                second = self._waiting(repository, number=2, task=task)
                third = self._waiting(repository, number=3, task=task)
                service = MetadataCorrectionService(repository, self.strategy.metadata_policies)
                reviews = service.resolve_pending(
                    query=" Correct Title ",
                    year=2024,
                    media_type="tv",
                    actor=" operator ",
                    note=" fixed ",
                    limit=2,
                )
                self.assertEqual(
                    [review.review_id for review in reviews],
                    [
                        first[3].review_id,
                        second[3].review_id,
                    ],
                )
                for review in reviews:
                    stored = repository.get_metadata_correction(review.review_id)
                    self.assertEqual(stored.status, MetadataCorrectionStatus.RESOLVED)
                    self.assertEqual(stored.corrected_query, "Correct Title")
                    self.assertEqual(stored.corrected_year, 2024)
                    self.assertEqual(stored.corrected_media_type, "tv")
                    self.assertEqual(stored.actor, "operator")
                    self.assertEqual(
                        repository.get_item(review.item_id).status, TaskItemStatus.PENDING
                    )
                    audit = repository.list_metadata_correction_audit(review.review_id)[0]
                    self.assertEqual(audit.corrected_query, "Correct Title")
                    self.assertEqual(audit.corrected_year, 2024)
                    self.assertEqual(audit.note, "fixed")
                self.assertEqual(
                    repository.get_metadata_correction(third[3].review_id).status,
                    MetadataCorrectionStatus.PENDING,
                )
                self.assertEqual(
                    {
                        item.item_id
                        for item in coordinator.retryable_items(task.task_id, failed_only=False)
                    },
                    {first[2].item_id, second[2].item_id},
                )
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_task_filter_and_limit_select_only_selected_corrections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                first_task = coordinator.create("preview", execute_authorized=False)
                second_task = coordinator.create("preview", execute_authorized=False)
                first = self._waiting(repository, number=1, task=first_task)
                second = self._waiting(repository, number=2, task=first_task)
                third = self._waiting(repository, number=3, task=second_task)
                service = MetadataCorrectionService(repository, self.strategy.metadata_policies)
                reviews = service.resolve_pending(
                    query="Correct Title",
                    media_type="movie",
                    actor="operator",
                    limit=2,
                    task_id=first_task.task_id,
                )
                self.assertEqual(
                    {review.review_id for review in reviews},
                    {first[3].review_id, second[3].review_id},
                )
                self.assertEqual(
                    repository.get_metadata_correction(third[3].review_id).status,
                    MetadataCorrectionStatus.PENDING,
                )

    def test_invalid_inputs_and_empty_selection_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task, _, _ = self._waiting(repository)
                service = MetadataCorrectionService(repository, self.strategy.metadata_policies)
                with self.assertRaisesRegex(ValueError, "query or direct provider"):
                    service.resolve_pending(query="", media_type="movie", actor="operator")
                with self.assertRaisesRegex(ValueError, "provider ID"):
                    service.resolve_pending(
                        query=None,
                        provider_id="bad provider id",
                        media_type="movie",
                        actor="operator",
                    )
                with self.assertRaisesRegex(ValueError, "year"):
                    service.resolve_pending(
                        query="Title", year=1800, media_type="movie", actor="operator"
                    )
                with self.assertRaisesRegex(ValueError, "media type"):
                    service.resolve_pending(query="Title", media_type="invalid", actor="operator")
                with self.assertRaisesRegex(ValueError, "actor"):
                    service.resolve_pending(query="Title", media_type="movie", actor="   ")
                for limit in (0, -1, 101, True):
                    with self.subTest(limit=limit):
                        with self.assertRaisesRegex(ValueError, "limit"):
                            service.resolve_pending(
                                query="Title",
                                media_type="movie",
                                actor="operator",
                                limit=limit,
                            )
                with self.assertRaisesRegex(ValueError, "no pending"):
                    service.resolve_pending(
                        query="Title",
                        media_type="movie",
                        actor="operator",
                        task_id="missing",
                    )

    def test_stale_policy_or_provider_fails_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task, item, review = self._waiting(repository)
                stale_service = MetadataCorrectionService(repository, ())
                with self.assertRaisesRegex(ValueError, "MetadataPolicy"):
                    stale_service.resolve_pending(
                        query="Title", media_type="movie", actor="operator", limit=1
                    )
                self.assertEqual(
                    repository.get_metadata_correction(review.review_id).status,
                    MetadataCorrectionStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status,
                    TaskItemStatus.WAITING_METADATA_CORRECTION,
                )
                self.assertEqual(repository.list_metadata_correction_audit(review.review_id), ())

    def test_any_invalid_member_rolls_back_whole_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, task, first_item, first_review = self._waiting(repository, number=1)
                _, _, second_item, second_review = self._waiting(repository, number=2, task=task)
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TRIGGER reject_metadata_correction_batch
                BEFORE INSERT ON metadata_correction_decision_audit
                BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                service = MetadataCorrectionService(repository, self.strategy.metadata_policies)
                with self.assertRaises(sqlite3.IntegrityError):
                    service.resolve_pending(
                        query="Title", media_type="movie", actor="operator", limit=2
                    )
                self.assertEqual(
                    repository.get_metadata_correction(first_review.review_id).status,
                    MetadataCorrectionStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_metadata_correction(second_review.review_id).status,
                    MetadataCorrectionStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(first_item.item_id).status,
                    TaskItemStatus.WAITING_METADATA_CORRECTION,
                )
                self.assertEqual(
                    repository.get_item(second_item.item_id).status,
                    TaskItemStatus.WAITING_METADATA_CORRECTION,
                )

    def test_concurrent_batch_resolve_commits_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, task, first_item, first_review = self._waiting(repository, number=1)
                _, _, second_item, second_review = self._waiting(repository, number=2, task=task)
            barrier = threading.Barrier(2)
            outcomes = []

            def resolve(actor):
                try:
                    with SQLiteTaskRepository(database) as repository:
                        barrier.wait()
                        MetadataCorrectionService(
                            repository, self.strategy.metadata_policies
                        ).resolve_pending(
                            query="Title",
                            media_type="movie",
                            actor=actor,
                            limit=2,
                        )
                    outcomes.append("ok")
                except (ValueError, sqlite3.OperationalError):
                    outcomes.append("rejected")

            threads = [threading.Thread(target=resolve, args=(actor,)) for actor in ("one", "two")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(outcomes), ["ok", "rejected"])
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(
                    len(repository.list_metadata_correction_audit(first_review.review_id)), 1
                )
                self.assertEqual(
                    len(repository.list_metadata_correction_audit(second_review.review_id)), 1
                )

    def test_cli_batch_correction_constructs_no_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = root / "strategy.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                _, task, _, review = self._waiting(repository)
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("batch metadata correction constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "metadata-corrections",
                        "resolve-pending",
                        "--query",
                        "Correct Title",
                        "--media-type",
                        "movie",
                        "--actor",
                        "operator",
                        "--limit",
                        "1",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("BATCH METADATA CORRECTION", output.getvalue())
            self.assertIn("Resolved: 1", output.getvalue())
            self.assertIn("Media mutation: 0", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(
                    repository.get_metadata_correction(review.review_id).status,
                    MetadataCorrectionStatus.RESOLVED,
                )

    def test_c_preservation_and_retryable_selection_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                _, _, item, review = self._waiting(repository, task=task)
                MetadataCorrectionService(
                    repository, self.strategy.metadata_policies
                ).resolve_pending(
                    query="Correct Title",
                    media_type="movie",
                    actor="operator",
                    limit=1,
                )
                retryable = coordinator.retryable_items(task.task_id, failed_only=False)
                self.assertEqual([value.item_id for value in retryable], [item.item_id])
                self.assertEqual(
                    repository.get_metadata_correction(review.review_id).corrected_query,
                    "Correct Title",
                )

        runner = strategy_runner_from_configuration(development_strategy_configuration())
        result = runner.run_path("/Unknown.2025.mkv", resource_library_id="special")
        self.assertEqual(result.recognition.recognition_type_id, "C")
        self.assertEqual(result.policy.metadata_policy_id, "C")
        self.assertEqual(result.policy.naming_policy_id, "A")
        self.assertEqual(result.policy.classification_policy_id, "A")
        self.assertEqual(result.policy.organize_policy_id, "A")
        self.assertTrue(result.recognition_type_preserved)


if __name__ == "__main__":
    unittest.main()
