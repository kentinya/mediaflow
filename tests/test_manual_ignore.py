from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.manual_ignore import ManualIgnoreService
from mediaflow.application.media_organizer import MediaOrganizerBatchResult
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.metadata import MetadataIdentificationStatus
from mediaflow.domain.metadata_correction import MetadataCorrectionStatus
from mediaflow.domain.metadata_review import MetadataReviewStatus
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import RecognitionResult, RecognitionStatus
from mediaflow.domain.recognition_review import RecognitionReviewStatus
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from tests.test_metadata_review import create_processing_item, identification


class ManualIgnoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = development_strategy_configuration()

    def _create_waiting(self, repository, kind):
        coordinator, task, item = create_processing_item(repository)
        if kind == "recognition":
            review = RecognitionReviewService(repository, self.strategy.recognition_types).create(
                item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED)
            )
        elif kind == "metadata":
            review = MetadataReviewService(repository).create(item, identification(), "C")
        else:
            policy = next(
                value for value in self.strategy.metadata_policies if value.policy_id == "A"
            )
            review = MetadataCorrectionService(repository, self.strategy.metadata_policies).create(
                item,
                identification(MetadataIdentificationStatus.NOT_FOUND, count=0),
                policy,
                ParseResult("Unknown", year=2025),
            )
        return coordinator, task, item, review

    def test_each_supported_waiting_review_can_be_ignored_atomically(self) -> None:
        expected = {
            "recognition": RecognitionReviewStatus.IGNORED,
            "metadata": MetadataReviewStatus.IGNORED,
            "metadata_correction": MetadataCorrectionStatus.IGNORED,
        }
        getters = {
            "recognition": "get_recognition_review",
            "metadata": "get_metadata_review",
            "metadata_correction": "get_metadata_correction",
        }
        for kind in expected:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                    coordinator, task, item, review = self._create_waiting(repository, kind)
                    decision = ManualIgnoreService(repository).ignore(
                        task.task_id,
                        item.item_id,
                        actor=" operator ",
                        note=" intentionally ignored ",
                    )
                    stored = repository.get_item(item.item_id)
                    self.assertEqual(stored.status, TaskItemStatus.IGNORED)
                    self.assertEqual(
                        getattr(repository, getters[kind])(review.review_id).status,
                        expected[kind],
                    )
                    self.assertEqual(decision.review_kind.value, kind)
                    self.assertEqual(decision.actor, "operator")
                    self.assertEqual(
                        repository.list_manual_ignore_audit(item.item_id)[0].note,
                        "intentionally ignored",
                    )
                    self.assertEqual(
                        coordinator.retryable_items(task.task_id, failed_only=False), ()
                    )
                    summary = coordinator.finish(task.task_id, MediaOrganizerBatchResult(()))
                    self.assertEqual(summary.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                    self.assertEqual(summary.completed_items, 0)
                    with self.assertRaises(ValueError):
                        ManualIgnoreService(repository).ignore(
                            task.task_id, item.item_id, actor="operator"
                        )
                    self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_wrong_task_unsupported_state_and_missing_review_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task, item, _ = self._create_waiting(repository, "recognition")
                with self.assertRaises(LookupError):
                    ManualIgnoreService(repository).ignore(
                        "wrong-task", item.item_id, actor="operator"
                    )
                with self.assertRaises(ValueError):
                    ManualIgnoreService(repository).ignore(task.task_id, item.item_id, actor="   ")
                repository._connection.execute(
                    "UPDATE recognition_reviews SET status='resolved' WHERE item_id=?",
                    (item.item_id,),
                )
                with self.assertRaisesRegex(ValueError, "matching pending"):
                    ManualIgnoreService(repository).ignore(
                        task.task_id, item.item_id, actor="operator"
                    )
                second = PersistentTaskCoordinator(repository, repository).create(
                    "preview", execute_authorized=False
                )
                pending = PersistentTaskCoordinator(repository, repository).begin_item(
                    second.task_id, "source", "movies", "Other.mkv", "Other.mkv"
                )
                with self.assertRaises(ValueError):
                    ManualIgnoreService(repository).ignore(
                        second.task_id, pending.item_id, actor="operator"
                    )
                self.assertEqual(repository.list_manual_ignore_audit(item.item_id), ())

    def test_audit_failure_rolls_back_review_and_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, task, item, review = self._create_waiting(repository, "metadata")
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TRIGGER reject_ignore BEFORE INSERT ON manual_ignore_audit
                BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                with self.assertRaises(sqlite3.IntegrityError):
                    ManualIgnoreService(repository).ignore(
                        task.task_id, item.item_id, actor="operator"
                    )
                self.assertEqual(
                    repository.get_item(item.item_id).status, TaskItemStatus.WAITING_METADATA
                )
                self.assertEqual(
                    repository.get_metadata_review(review.review_id).status,
                    MetadataReviewStatus.PENDING,
                )

    def test_concurrent_ignore_commits_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, task, item, _ = self._create_waiting(repository, "metadata_correction")
            barrier = threading.Barrier(2)
            outcomes = []

            def ignore(actor):
                try:
                    with SQLiteTaskRepository(database) as repository:
                        barrier.wait()
                        ManualIgnoreService(repository).ignore(
                            task.task_id, item.item_id, actor=actor
                        )
                    outcomes.append("ok")
                except (ValueError, sqlite3.OperationalError):
                    outcomes.append("rejected")

            threads = [threading.Thread(target=ignore, args=(actor,)) for actor in ("one", "two")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(outcomes), ["ok", "rejected"])
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(len(repository.list_manual_ignore_audit(item.item_id)), 1)

    def test_cli_ignore_needs_no_storage_or_provider_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = root / "strategy.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                _, task, item, review = self._create_waiting(repository, "recognition")
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("ignore command constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "tasks",
                        "ignore-item",
                        task.task_id,
                        item.item_id,
                        "--actor",
                        "operator",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("Review kind: recognition", output.getvalue())
            self.assertIn("Ignored items: 1", output.getvalue())
            self.assertIn("Media mutation: 0", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).status,
                    RecognitionReviewStatus.IGNORED,
                )


if __name__ == "__main__":
    unittest.main()
