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
from mediaflow.application.recognition_retry import RecognitionRetryService
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


class RecognitionRetryTests(unittest.TestCase):
    def _waiting(self, repository):
        coordinator = PersistentTaskCoordinator(repository, repository)
        task = coordinator.create("preview", execute_authorized=False)
        item = coordinator.begin_item(
            task.task_id, "source", "unmatched", "Unknown.mkv", "Unknown.mkv"
        )
        review = RecognitionReviewService(
            repository, development_strategy_configuration().recognition_types
        ).create(item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED))
        return coordinator, task, item, review

    def test_request_is_atomic_audited_and_retryable_without_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator, task, item, review = self._waiting(repository)
                decision = RecognitionRetryService(repository).request(
                    review.review_id,
                    actor=" operator ",
                    note=" rules updated ",
                )
                self.assertEqual(decision.actor, "operator")
                self.assertEqual(decision.note, "rules updated")
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).status,
                    RecognitionReviewStatus.RETRY_REQUESTED,
                )
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.PENDING)
                self.assertEqual(
                    coordinator.retryable_items(task.task_id, failed_only=False)[0].item_id,
                    item.item_id,
                )
                self.assertEqual(repository.list_recognition_review_audit(review.review_id), ())
                self.assertEqual(
                    repository.list_recognition_retry_audit(review.review_id)[0].decision_id,
                    decision.decision_id,
                )
                with self.assertRaises(ValueError):
                    RecognitionRetryService(repository).request(review.review_id, actor="operator")
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_resolved_ignored_missing_wrong_state_and_empty_actor_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task, item, review = self._waiting(repository)
                with self.assertRaises(LookupError):
                    RecognitionRetryService(repository).request("missing", actor="operator")
                with self.assertRaises(ValueError):
                    RecognitionRetryService(repository).request(review.review_id, actor="  ")
                repository.upsert_item(
                    item.__class__(**{**item.__dict__, "status": TaskItemStatus.FAILED})
                )
                with self.assertRaisesRegex(ValueError, "not waiting"):
                    RecognitionRetryService(repository).request(review.review_id, actor="operator")

            with SQLiteTaskRepository(Path(directory, "ignored.sqlite3")) as repository:
                _, task, item, review = self._waiting(repository)
                ManualIgnoreService(repository).ignore(task.task_id, item.item_id, actor="operator")
                with self.assertRaisesRegex(ValueError, "not pending"):
                    RecognitionRetryService(repository).request(review.review_id, actor="operator")

            with SQLiteTaskRepository(Path(directory, "resolved.sqlite3")) as repository:
                _, _, _, review = self._waiting(repository)
                RecognitionReviewService(
                    repository, development_strategy_configuration().recognition_types
                ).resolve(review.review_id, "A")
                with self.assertRaisesRegex(ValueError, "not pending"):
                    RecognitionRetryService(repository).request(review.review_id, actor="operator")

    def test_current_rules_re_evaluate_a_b_c_without_hidden_default(self) -> None:
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
        unmatched = runner.run_path("/Unknown.2025.mkv", resource_library_id="still-unmatched")
        self.assertEqual(unmatched.recognition.status, RecognitionStatus.UNRECOGNIZED)
        self.assertIsNone(unmatched.recognition.recognition_type_id)

    def test_concurrent_requests_commit_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, _, _, review = self._waiting(repository)
            barrier = threading.Barrier(2)
            outcomes = []

            def request(actor):
                try:
                    with SQLiteTaskRepository(database) as repository:
                        barrier.wait()
                        RecognitionRetryService(repository).request(review.review_id, actor=actor)
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
                self.assertEqual(len(repository.list_recognition_retry_audit(review.review_id)), 1)

    def test_audit_failure_rolls_back_review_and_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, _, item, review = self._waiting(repository)
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TRIGGER reject_recognition_retry BEFORE INSERT
                ON recognition_retry_audit BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                with self.assertRaises(sqlite3.IntegrityError):
                    RecognitionRetryService(repository).request(review.review_id, actor="operator")
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).status,
                    RecognitionReviewStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status,
                    TaskItemStatus.WAITING_RECOGNITION,
                )
                self.assertEqual(repository.list_recognition_retry_audit(review.review_id), ())

    def test_cli_request_constructs_no_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = root / "strategy.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                _, _, item, review = self._waiting(repository)
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("recognition retry constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "recognition-reviews",
                        "retry",
                        review.review_id,
                        "--actor",
                        "operator",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("Status: retry_requested", output.getvalue())
            self.assertIn("retry_requested", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
