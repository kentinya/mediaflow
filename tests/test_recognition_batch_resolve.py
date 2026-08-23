from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

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


class RecognitionBatchResolveTests(unittest.TestCase):
    def _waiting(self, repository, source="Unknown.mkv", task=None):
        coordinator = PersistentTaskCoordinator(repository, repository)
        if task is None:
            task = coordinator.create("preview", execute_authorized=False)
        item = coordinator.begin_item(task.task_id, "source", "unmatched", source, source)
        review = RecognitionReviewService(
            repository, development_strategy_configuration().recognition_types
        ).create(item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED))
        return coordinator, task, item, review

    def test_batch_resolves_oldest_first_pending_set_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                first = self._waiting(repository, "First.mkv", task)
                second = self._waiting(repository, "Second.mkv", task)
                third = self._waiting(repository, "Third.mkv", task)
                service = RecognitionReviewService(
                    repository, development_strategy_configuration().recognition_types
                )
                reviews = service.resolve_pending(
                    "C",
                    actor=" operator ",
                    note=" reviewed ",
                    limit=2,
                )
                self.assertEqual(
                    [review.review_id for review in reviews],
                    [
                        first[3].review_id,
                        second[3].review_id,
                    ],
                )
                self.assertEqual(reviews[0].actor, "operator")
                for review in reviews:
                    stored = repository.get_recognition_review(review.review_id)
                    self.assertEqual(stored.status, RecognitionReviewStatus.RESOLVED)
                    self.assertEqual(stored.selected_recognition_type, "C")
                    self.assertEqual(
                        repository.get_item(review.item_id).status, TaskItemStatus.PENDING
                    )
                    audit = repository.list_recognition_review_audit(review.review_id)[0]
                    self.assertEqual(audit.recognition_type_id, "C")
                    self.assertEqual(audit.actor, "operator")
                    self.assertEqual(audit.note, "reviewed")
                self.assertEqual(
                    repository.get_recognition_review(third[3].review_id).status,
                    RecognitionReviewStatus.PENDING,
                )
                self.assertEqual(
                    {
                        item.item_id
                        for item in coordinator.retryable_items(task.task_id, failed_only=False)
                    },
                    {first[2].item_id, second[2].item_id},
                )
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_task_filter_empty_limits_invalid_actor_and_unknown_type_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task, _, _ = self._waiting(repository)
                service = RecognitionReviewService(
                    repository, development_strategy_configuration().recognition_types
                )
                with self.assertRaisesRegex(ValueError, "actor"):
                    service.resolve_pending("A", actor="   ")
                with self.assertRaisesRegex(ValueError, "enabled"):
                    service.resolve_pending("X", actor="operator")
                for limit in (0, -1, 101, True):
                    with self.subTest(limit=limit):
                        with self.assertRaisesRegex(ValueError, "limit"):
                            service.resolve_pending("A", actor="operator", limit=limit)
                with self.assertRaisesRegex(ValueError, "no pending"):
                    service.resolve_pending("A", actor="operator", task_id="missing")

    def test_task_filter_selects_only_specified_task_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                first_task = coordinator.create("preview", execute_authorized=False)
                second_task = coordinator.create("preview", execute_authorized=False)
                first = self._waiting(repository, "First.mkv", first_task)
                second = self._waiting(repository, "Second.mkv", second_task)
                service = RecognitionReviewService(
                    repository, development_strategy_configuration().recognition_types
                )
                reviews = service.resolve_pending(
                    "C",
                    actor="operator",
                    limit=10,
                    task_id=first_task.task_id,
                )
                self.assertEqual([review.review_id for review in reviews], [first[3].review_id])
                self.assertEqual(
                    repository.get_recognition_review(first[3].review_id).selected_recognition_type,
                    "C",
                )
                self.assertEqual(
                    repository.get_recognition_review(second[3].review_id).status,
                    RecognitionReviewStatus.PENDING,
                )

    def test_type_missing_from_snapshot_fails_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task, item, review = self._waiting(repository)
                repository._connection.execute(
                    """DELETE FROM recognition_review_choices
                    WHERE review_id=? AND recognition_type_id=?""",
                    (review.review_id, "C"),
                )
                repository._connection.commit()
                service = RecognitionReviewService(
                    repository, development_strategy_configuration().recognition_types
                )
                with self.assertRaisesRegex(ValueError, "snapshot"):
                    service.resolve_pending("C", actor="operator", limit=1)
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).status,
                    RecognitionReviewStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status,
                    TaskItemStatus.WAITING_RECOGNITION,
                )
                self.assertEqual(repository.list_recognition_review_audit(review.review_id), ())

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
                """CREATE TRIGGER reject_recognition_batch_resolve
                BEFORE INSERT ON recognition_review_decision_audit
                BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                service = RecognitionReviewService(
                    repository, development_strategy_configuration().recognition_types
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    service.resolve_pending("C", actor="operator", limit=2)
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

    def test_concurrent_batch_resolve_commits_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                self._waiting(repository, "One.mkv", task)
                self._waiting(repository, "Two.mkv", task)
            barrier = threading.Barrier(2)
            outcomes = []

            def resolve(actor):
                try:
                    with SQLiteTaskRepository(database) as repository:
                        barrier.wait()
                        RecognitionReviewService(
                            repository, development_strategy_configuration().recognition_types
                        ).resolve_pending("C", actor=actor, limit=2)
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
                    sum(
                        len(repository.list_recognition_review_audit(review.review_id))
                        for review in repository.list_recognition_reviews()
                    ),
                    2,
                )

    def test_cli_batch_resolve_constructs_no_storage_or_provider(self) -> None:
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
                side_effect=AssertionError("batch recognition resolve constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "recognition-reviews",
                        "resolve-pending",
                        "--recognition-type",
                        "C",
                        "--actor",
                        "operator",
                        "--limit",
                        "1",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("BATCH RECOGNITION RESOLVE", output.getvalue())
            self.assertIn("Resolved: 1", output.getvalue())
            self.assertIn("Media mutation: 0", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).status,
                    RecognitionReviewStatus.RESOLVED,
                )

    def test_c_preservation_and_retryable_selection_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                _, _, item, review = self._waiting(repository, "Unknown.mkv", task)
                RecognitionReviewService(
                    repository, development_strategy_configuration().recognition_types
                ).resolve_pending("C", actor="operator", limit=1)
                retryable = coordinator.retryable_items(task.task_id, failed_only=False)
                self.assertEqual([value.item_id for value in retryable], [item.item_id])
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).selected_recognition_type,
                    "C",
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
