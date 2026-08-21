from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.task_runtime import PersistentTaskCoordinator, TaskLockError
from mediaflow.domain.scanner import FileChange
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository


class PersistentTaskTests(unittest.TestCase):
    def test_schema_task_item_and_unicode_result_survive_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.record_discovered(
                    task.task_id, "源存储", "电影", "电影/千与千寻.mkv", "千与千寻.mkv"
                )
                repository.append_result(
                    PersistentResultRecord(
                        "result-1",
                        task.task_id,
                        item.item_id,
                        "源存储",
                        item.source_path,
                        "目标存储",
                        "动漫/千与千寻.mkv",
                        "C",
                        "tmdb",
                        "129",
                        "C",
                        "A",
                        "A",
                        "A",
                        "MOVE",
                        "dry_run",
                        datetime.now(UTC),
                        "千与千寻",
                    )
                )
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.get_task(task.task_id), task)
                self.assertEqual(reopened.list_items(task.task_id)[0].source_path, item.source_path)
                result = reopened.list_results(task.task_id)[0]
                self.assertEqual(result.title, "千与千寻")
                self.assertEqual(result.recognition_type, "C")

    def test_lock_is_storage_aware_and_explicitly_reclaimable(self) -> None:
        now = datetime.now(UTC)
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            self.assertTrue(repository.acquire("a", "folder//movie.mkv", "task-a", now))
            self.assertFalse(repository.acquire("a", "folder/movie.mkv", "task-b", now))
            self.assertTrue(repository.acquire("b", "folder/movie.mkv", "task-b", now))
            self.assertTrue(repository.acquire("a", "other/movie.mkv", "task-b", now))
            self.assertEqual(repository.reclaim_task_locks("task-a"), 1)
            self.assertTrue(repository.acquire("a", "folder/movie.mkv", "task-b", now))
            repository.release("a", "folder/movie.mkv", "task-b")
            self.assertTrue(repository.acquire("a", "folder/movie.mkv", "task-c", now))
            with self.assertRaises(ValueError):
                repository.acquire("a", "../movie.mkv", "task", now)

    def test_lock_conflict_is_persisted_without_storage_access(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            first = coordinator.create("organize", execute_authorized=True)
            second = coordinator.create("organize", execute_authorized=True)
            coordinator.begin_item(first.task_id, "s", "r", "movie.mkv", "movie.mkv")
            with self.assertRaises(TaskLockError):
                coordinator.begin_item(second.task_id, "s", "r", "movie.mkv", "movie.mkv")
            item = repository.list_items(second.task_id)[0]
            self.assertEqual(item.status, TaskItemStatus.FAILED)
            self.assertEqual(item.stage, "lock")

    def test_retry_selection_and_execute_authority(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("preview", execute_authorized=False)
            now = datetime.now(UTC)
            base = PersistentTaskItem(
                "failed",
                task.task_id,
                "s",
                "r",
                "failed.mkv",
                "failed.mkv",
                TaskItemStatus.FAILED,
                "failed",
                1,
                now,
                now,
            )
            repository.upsert_item(base)
            repository.upsert_item(
                replace(
                    base,
                    item_id="partial",
                    source_path="partial.mkv",
                    status=TaskItemStatus.PARTIAL,
                )
            )
            repository.upsert_item(
                replace(
                    base,
                    item_id="success",
                    source_path="success.mkv",
                    status=TaskItemStatus.SUCCESS,
                )
            )
            repository.upsert_item(
                replace(
                    base,
                    item_id="crash-after-success",
                    source_path="completed-before-crash.mkv",
                    status=TaskItemStatus.PROCESSING,
                )
            )
            repository.append_result(
                PersistentResultRecord(
                    "completed-result",
                    task.task_id,
                    "crash-after-success",
                    "s",
                    "completed-before-crash.mkv",
                    "target",
                    "Movies/completed.mkv",
                    "A",
                    "tmdb",
                    "1",
                    "A",
                    "A",
                    "A",
                    "A",
                    "MOVE",
                    "success",
                    now,
                )
            )
            self.assertEqual(
                {
                    item.item_id
                    for item in coordinator.retryable_items(task.task_id, failed_only=True)
                },
                {"failed", "partial"},
            )
            with self.assertRaisesRegex(ValueError, "not execute-authorized"):
                coordinator.reopen(task.task_id, execute=True)

    def test_persistence_config_validation_creates_no_database(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "nested", "runtime.sqlite3")
            document["persistence"] = {"databasePath": str(database)}
            load_runtime_configuration(copy.deepcopy(document))
            self.assertFalse(database.exists())
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            output, errors = io.StringIO(), io.StringIO()
            code = final_main(
                ["--config", str(config), "config", "validate"],
                stdout=output,
                stderr=errors,
            )
            self.assertEqual(code, 0, errors.getvalue())
            self.assertFalse(database.exists())

    def test_active_task_is_discoverable_after_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "organize", execute_authorized=True
                )
                stale = replace(task, updated_at=datetime.now(UTC) - timedelta(hours=1))
                repository.update_task(stale)
            with SQLiteTaskRepository(database) as reopened:
                loaded = reopened.get_task(task.task_id)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded.status, PersistentTaskStatus.RUNNING)

    def test_cancel_persists_items_releases_locks_and_stops_new_items(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("organize", execute_authorized=True)
            item = coordinator.begin_item(task.task_id, "s", "r", "movie.mkv", "movie.mkv")
            cancelled = coordinator.cancel(task.task_id)
            self.assertEqual(cancelled.status, PersistentTaskStatus.CANCELLED)
            self.assertEqual(
                repository.get_item(item.item_id).status,
                TaskItemStatus.CANCELLED,
            )
            self.assertTrue(repository.acquire("s", "movie.mkv", "another-task", datetime.now(UTC)))
            with self.assertRaisesRegex(RuntimeError, "not running"):
                coordinator.begin_item(task.task_id, "s", "r", "later.mkv", "later.mkv")

    def test_production_scan_uses_persistent_file_index_and_task_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "Incoming" / "电影"
            incoming.mkdir(parents=True)
            (root / "Target").mkdir()
            media = incoming / "Movie.2025.mkv"
            media.write_bytes(b"movie")
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["storages"][0]["rootPath"] = str(root)
            document["storages"][1]["rootPath"] = str(root / "Target")
            document["resourceLibraries"][0]["storagePath"] = "Incoming"
            document["resourceLibraries"][0]["displayRootPath"] = str(root / "Incoming")
            database = root / "state" / "runtime.sqlite3"
            document["persistence"] = {"databasePath": str(database)}
            document["historyPath"] = str(root / "state" / "history.jsonl")
            config = root / "config.json"
            config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

            first_output, errors = io.StringIO(), io.StringIO()
            self.assertEqual(
                0,
                final_main(
                    ["--config", str(config), "scan"],
                    stdout=first_output,
                    stderr=errors,
                ),
                errors.getvalue(),
            )
            with SQLiteFileIndexRepository(database) as index:
                record = index.find_by_path(
                    "source-storage", "source", "Incoming/电影/Movie.2025.mkv"
                )
                self.assertIsNotNone(record)
                assert record is not None
                self.assertEqual(record.change, FileChange.NEW)

            second_output, errors = io.StringIO(), io.StringIO()
            self.assertEqual(
                0,
                final_main(
                    ["--config", str(config), "scan"],
                    stdout=second_output,
                    stderr=errors,
                ),
                errors.getvalue(),
            )
            with SQLiteFileIndexRepository(database) as index:
                record = index.find_by_path(
                    "source-storage", "source", "Incoming/电影/Movie.2025.mkv"
                )
                assert record is not None
                self.assertEqual(record.change, FileChange.UNCHANGED)

            tasks_output, errors = io.StringIO(), io.StringIO()
            self.assertEqual(
                0,
                final_main(
                    ["--config", str(config), "tasks", "list"],
                    stdout=tasks_output,
                    stderr=errors,
                ),
            )
            self.assertIn("TASKS", tasks_output.getvalue())
            first_task_id = first_output.getvalue().split("Task ID: ", 1)[1].splitlines()[0]
            show_output = io.StringIO()
            self.assertEqual(
                0,
                final_main(
                    ["--config", str(config), "tasks", "show", first_task_id],
                    stdout=show_output,
                    stderr=errors,
                ),
            )
            self.assertIn("Incoming/电影/Movie.2025.mkv", show_output.getvalue())


if __name__ == "__main__":
    unittest.main()
