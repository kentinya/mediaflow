from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.task_retry import TaskRetryRequestService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository


class TaskRetryTests(unittest.TestCase):
    def _failed(self, repository, number=1, task=None):
        coordinator = PersistentTaskCoordinator(repository, repository)
        if task is None:
            task = coordinator.create("preview", execute_authorized=False)
        item = coordinator.begin_item(
            task.task_id, "source", "movies", f"Bad-{number}.mkv", f"Bad-{number}.mkv"
        )
        failed = replace(
            item,
            status=TaskItemStatus.FAILED,
            stage="failed",
            error="original failure",
        )
        repository.upsert_item(failed)
        return coordinator, task, failed

    def test_batch_retry_requests_oldest_first_failed_items(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                first = self._failed(repository, number=1, task=task)
                second = self._failed(repository, number=2, task=task)
                third = self._failed(repository, number=3, task=task)
                decisions = TaskRetryRequestService(repository).request(
                    actor=" operator ",
                    note=" retry ",
                    limit=2,
                )
                self.assertEqual(
                    [decision.item_id for decision in decisions],
                    [
                        first[2].item_id,
                        second[2].item_id,
                    ],
                )
                for decision in decisions:
                    stored = repository.get_item(decision.item_id)
                    self.assertEqual(stored.status, TaskItemStatus.PENDING)
                    self.assertEqual(stored.stage, "task_retry_requested")
                    audit = repository.list_task_retry_audit(decision.item_id)[0]
                    self.assertEqual(audit.actor, "operator")
                    self.assertEqual(audit.note, "retry")
                self.assertEqual(
                    repository.get_item(third[2].item_id).status, TaskItemStatus.FAILED
                )
                retryable = coordinator.retryable_items(task.task_id, failed_only=False)
                self.assertEqual(
                    {item.item_id for item in retryable},
                    {
                        first[2].item_id,
                        second[2].item_id,
                        third[2].item_id,
                    },
                )
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_task_filter_invalid_limits_actor_and_empty_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task, _ = self._failed(repository)
                service = TaskRetryRequestService(repository)
                with self.assertRaisesRegex(ValueError, "actor"):
                    service.request(actor="   ")
                for limit in (0, -1, 101, True):
                    with self.subTest(limit=limit):
                        with self.assertRaisesRegex(ValueError, "limit"):
                            service.request(actor="operator", limit=limit)
                with self.assertRaisesRegex(ValueError, "no failed"):
                    service.request(actor="operator", task_id="missing")

    def test_any_invalid_member_rolls_back_whole_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, task, first_item = self._failed(repository, number=1)
                _, _, second_item = self._failed(repository, number=2, task=task)
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TRIGGER reject_task_retry BEFORE INSERT ON task_retry_audit
                BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                service = TaskRetryRequestService(repository)
                with self.assertRaises(sqlite3.IntegrityError):
                    service.request(actor="operator", limit=2)
                self.assertEqual(
                    repository.get_item(first_item.item_id).status, TaskItemStatus.FAILED
                )
                self.assertEqual(
                    repository.get_item(second_item.item_id).status, TaskItemStatus.FAILED
                )
                self.assertEqual(repository.list_task_retry_audit(first_item.item_id), ())
                self.assertEqual(repository.list_task_retry_audit(second_item.item_id), ())

    def test_concurrent_batch_retry_commits_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, task, first_item = self._failed(repository, number=1)
                _, _, second_item = self._failed(repository, number=2, task=task)
            barrier = threading.Barrier(2)
            outcomes = []

            def request(actor):
                try:
                    with SQLiteTaskRepository(database) as repository:
                        barrier.wait()
                        TaskRetryRequestService(repository).request(actor=actor, limit=2)
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
                self.assertEqual(len(repository.list_task_retry_audit(first_item.item_id)), 1)
                self.assertEqual(len(repository.list_task_retry_audit(second_item.item_id)), 1)

    def test_cli_retry_request_constructs_no_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = root / "strategy.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                _, task, _ = self._failed(repository)
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("task retry request constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "tasks",
                        "retry-request",
                        "--actor",
                        "operator",
                        "--limit",
                        "1",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("BATCH TASK RETRY REQUEST", output.getvalue())
            self.assertIn("Requested: 1", output.getvalue())
            self.assertIn("Media mutation: 0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
