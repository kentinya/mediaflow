from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.recognition_batch_retry import RecognitionBatchRetryService
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.application.strategy_test import strategy_runner_from_configuration
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.recognition import RecognitionResult, RecognitionStatus
from mediaflow.domain.recognition_review import RecognitionReviewStatus
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration


class RecognitionBatchRetryTests(unittest.TestCase):
    def _waiting(self, repository, source="Unknown.mkv", task=None):
        coordinator = PersistentTaskCoordinator(repository, repository)
        task = task or coordinator.create("preview", execute_authorized=False)
        item = coordinator.begin_item(task.task_id, "source", "unmatched", source, source)
        review = RecognitionReviewService(
            repository, development_strategy_configuration().recognition_types
        ).create(item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED))
        return coordinator, task, item, review

    def test_batch_requests_oldest_first_pending_set_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                first = self._waiting(repository, "First.mkv", task)
                second = self._waiting(repository, "Second.mkv", task)
                third = self._waiting(repository, "Third.mkv", task)
                decisions = RecognitionBatchRetryService(repository).request_pending(
                    actor=" operator ",
                    note=" rules updated ",
                    limit=2,
                )
                self.assertEqual(
                    [decision.review_id for decision in decisions],
                    [
                        first[3].review_id,
                        second[3].review_id,
                    ],
                )
                self.assertEqual(len(decisions), 2)
                self.assertEqual(decisions[0].actor, "operator")
                for review in (first[3], second[3]):
                    stored = repository.get_recognition_review(review.review_id)
                    self.assertEqual(stored.status, RecognitionReviewStatus.RETRY_REQUESTED)
                    self.assertEqual(
                        repository.list_recognition_retry_audit(review.review_id)[0].note,
                        "rules updated",
                    )
                    self.assertEqual(
                        repository.get_item(review.item_id).status,
                        TaskItemStatus.PENDING,
                    )
                self.assertEqual(
                    repository.get_recognition_review(third[3].review_id).status,
                    RecognitionReviewStatus.PENDING,
                )
                retryable = coordinator.retryable_items(task.task_id, failed_only=False)
                self.assertEqual(
                    {item.item_id for item in retryable},
                    {
                        first[2].item_id,
                        second[2].item_id,
                    },
                )
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_task_filter_empty_invalid_limits_and_invalid_actor_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task, _, review = self._waiting(repository)
                service = RecognitionBatchRetryService(repository)
                with self.assertRaisesRegex(ValueError, "actor"):
                    service.request_pending(actor="   ")
                for limit in (0, -1, 101, True):
                    with self.subTest(limit=limit):
                        with self.assertRaisesRegex(ValueError, "limit"):
                            service.request_pending(actor="operator", limit=limit)
                with self.assertRaisesRegex(ValueError, "no pending"):
                    service.request_pending(actor="operator", task_id="missing")
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).status,
                    RecognitionReviewStatus.PENDING,
                )

    def test_task_filter_selects_only_specified_task_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                first_task = coordinator.create("preview", execute_authorized=False)
                second_task = coordinator.create("preview", execute_authorized=False)
                _, _, first_item, first_review = self._waiting(repository, "First.mkv", first_task)
                _, _, _, second_review = self._waiting(repository, "Second.mkv", second_task)
                decisions = RecognitionBatchRetryService(repository).request_pending(
                    actor="operator",
                    limit=10,
                    task_id=first_task.task_id,
                )
                self.assertEqual(
                    [decision.review_id for decision in decisions], [first_review.review_id]
                )
                self.assertEqual(
                    repository.get_recognition_review(first_review.review_id).status,
                    RecognitionReviewStatus.RETRY_REQUESTED,
                )
                self.assertEqual(
                    repository.get_recognition_review(second_review.review_id).status,
                    RecognitionReviewStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(first_item.item_id).status,
                    TaskItemStatus.PENDING,
                )

    def test_any_invalid_member_rolls_back_whole_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, task, first_item, first_review = self._waiting(repository, "First.mkv")
                _, _, second_item, second_review = self._waiting(
                    repository, "Second.mkv", task=task
                )
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TRIGGER reject_batch_retry BEFORE INSERT ON recognition_retry_audit
                BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                service = RecognitionBatchRetryService(repository)
                with self.assertRaises(sqlite3.IntegrityError):
                    service.request_pending(actor="operator", limit=2)
                self.assertEqual(
                    repository.get_recognition_review(first_review.review_id).status,
                    RecognitionReviewStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_recognition_review(second_review.review_id).status,
                    RecognitionReviewStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(first_item.item_id).status,
                    TaskItemStatus.WAITING_RECOGNITION,
                )
                self.assertEqual(
                    repository.get_item(second_item.item_id).status,
                    TaskItemStatus.WAITING_RECOGNITION,
                )
                self.assertEqual(
                    repository.list_recognition_retry_audit(first_review.review_id), ()
                )
                self.assertEqual(
                    repository.list_recognition_retry_audit(second_review.review_id), ()
                )

    def test_concurrent_batch_requests_commit_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                self._waiting(repository, "One.mkv", task)
                self._waiting(repository, "Two.mkv", task)
            barrier = threading.Barrier(2)
            outcomes = []

            def request(actor):
                try:
                    with SQLiteTaskRepository(database) as repository:
                        barrier.wait()
                        RecognitionBatchRetryService(repository).request_pending(
                            actor=actor, limit=2
                        )
                    outcomes.append("ok")
                except (ValueError, sqlite3.OperationalError):
                    outcomes.append("rejected")

            threads = [threading.Thread(target=request, args=(actor,)) for actor in ("one", "two")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(outcomes), ["ok", "rejected"])
            with SQLiteTaskRepository(database) as repository:
                reviews = repository.list_recognition_reviews()
                self.assertEqual(
                    sum(
                        len(repository.list_recognition_retry_audit(review.review_id))
                        for review in reviews
                    ),
                    2,
                )

    def test_resume_selection_and_c_preservation_semantics_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                _, _, item, review = self._waiting(repository, "Unknown.mkv", task)
                RecognitionBatchRetryService(repository).request_pending(actor="operator", limit=1)
                retryable = coordinator.retryable_items(task.task_id, failed_only=False)
                self.assertEqual([value.item_id for value in retryable], [item.item_id])
                self.assertIsNone(
                    repository.get_recognition_review(review.review_id).selected_recognition_type
                )

        runner = strategy_runner_from_configuration(development_strategy_configuration())
        for library_id, expected in (("movies", "A"), ("tv", "B"), ("special", "C")):
            with self.subTest(library_id=library_id):
                result = runner.run_path("/Unknown.2025.mkv", resource_library_id=library_id)
                self.assertEqual(result.recognition.recognition_type_id, expected)
                if expected == "C":
                    self.assertEqual(result.policy.metadata_policy_id, "C")
                    self.assertEqual(result.policy.naming_policy_id, "A")
                    self.assertEqual(result.policy.classification_policy_id, "A")
                    self.assertEqual(result.policy.organize_policy_id, "A")
                    self.assertTrue(result.recognition_type_preserved)

    def test_cli_batch_request_constructs_no_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = root / "strategy.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                _, task, _, _ = self._waiting(repository)
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("batch recognition retry constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "recognition-reviews",
                        "retry-pending",
                        "--actor",
                        "operator",
                        "--limit",
                        "1",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("BATCH RECOGNITION RETRY", output.getvalue())
            self.assertIn("Requested: 1", output.getvalue())
            self.assertIn("Media mutation: 0", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(
                    repository.list_recognition_reviews()[0].status,
                    RecognitionReviewStatus.RETRY_REQUESTED,
                )


if __name__ == "__main__":
    unittest.main()
