from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.task_runtime import (
    PersistentTaskCoordinator,
    TaskPauseRequested,
)
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.final_cli import final_main, render_task
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository


class TaskPauseResumeTest(unittest.TestCase):
    def test_schema_fourteen_migrates_pause_fields_without_changing_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_version VALUES ('runtime', 14);
                CREATE TABLE tasks (
                    task_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    execute_authorized INTEGER NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                    total_items INTEGER NOT NULL, completed_items INTEGER NOT NULL,
                    failed_items INTEGER NOT NULL, error TEXT
                );
                INSERT INTO tasks VALUES (
                    'legacy', 'preview', 'completed', 0,
                    '2026-08-23T00:00:00+00:00', '2026-08-23T00:00:00+00:00',
                    NULL, '2026-08-23T00:00:00+00:00', 1, 1, 0, NULL
                );
                """
            )
            connection.commit()
            connection.close()

            with SQLiteTaskRepository(database) as repository:
                task = repository.get_task("legacy")
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                self.assertIsNotNone(task)
                assert task is not None
                self.assertFalse(task.pause_requested)
                self.assertIsNone(task.scope_path)
                self.assertIsNone(task.item_limit)
                self.assertEqual(task.status, PersistentTaskStatus.COMPLETED)

    def test_pause_request_is_durable_idempotent_and_rejects_terminal_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create(
                    "preview", execute_authorized=False, scope_path="/media", item_limit=20
                )
                first = coordinator.request_pause(task.task_id)
                second = coordinator.request_pause(task.task_id)
                self.assertTrue(first.pause_requested)
                self.assertTrue(second.pause_requested)
            with SQLiteTaskRepository(database) as reopened:
                persisted = reopened.get_task(task.task_id)
                self.assertTrue(persisted.pause_requested)
                paused = PersistentTaskCoordinator(reopened, reopened).acknowledge_pause(
                    task.task_id
                )
                self.assertEqual(paused.status, PersistentTaskStatus.PAUSED)
                self.assertFalse(paused.pause_requested)
                with self.assertRaisesRegex(ValueError, "only a running task"):
                    PersistentTaskCoordinator(reopened, reopened).request_pause(task.task_id)

    def test_pause_is_acknowledged_only_at_checkpoint_and_releases_item_lock(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("organize", execute_authorized=True)
            item = coordinator.begin_item(task.task_id, "source", "library", "movie.mkv", "movie")
            coordinator.request_pause(task.task_id)

            self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.PROCESSING)
            with self.assertRaises(TaskPauseRequested):
                coordinator.begin_item(task.task_id, "source", "library", "next.mkv", "next")

            paused = coordinator.acknowledge_pause(task.task_id)
            self.assertEqual(paused.status, PersistentTaskStatus.PAUSED)
            self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.PAUSED)
            self.assertTrue(repository.acquire("source", "movie.mkv", "other", datetime.now(UTC)))

    def test_pause_request_does_not_interrupt_in_flight_item(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("organize", execute_authorized=True)
            entered = threading.Event()
            release = threading.Event()

            def in_flight() -> None:
                item = coordinator.begin_item(
                    task.task_id, "source", "library", "movie.mkv", "movie"
                )
                entered.set()
                release.wait(2)
                repository.upsert_item(
                    replace(
                        item,
                        status=TaskItemStatus.SUCCESS,
                        stage="completed",
                        updated_at=datetime.now(UTC),
                    )
                )
                repository.release(item.storage_id, item.source_path, item.task_id)

            worker = threading.Thread(target=in_flight)
            worker.start()
            self.assertTrue(entered.wait(2))
            coordinator.request_pause(task.task_id)
            self.assertTrue(worker.is_alive())
            release.set()
            worker.join(2)
            paused = coordinator.acknowledge_pause(task.task_id)
            self.assertEqual(paused.status, PersistentTaskStatus.PAUSED)
            self.assertEqual(repository.list_items(task.task_id)[0].status, TaskItemStatus.SUCCESS)

    def test_concurrent_pause_requests_have_one_durable_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "preview", execute_authorized=False
                )
            barrier = threading.Barrier(2)
            outcomes = []

            def request() -> None:
                with SQLiteTaskRepository(database) as repository:
                    barrier.wait()
                    outcomes.append(
                        PersistentTaskCoordinator(repository, repository)
                        .request_pause(task.task_id)
                        .pause_requested
                    )

            threads = [threading.Thread(target=request) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(outcomes, [True, True])
            with SQLiteTaskRepository(database) as repository:
                self.assertTrue(repository.task_pause_requested(task.task_id))

    def test_paused_items_are_resumable_but_successful_results_are_excluded(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("preview", execute_authorized=False)
            paused = coordinator.record_discovered(
                task.task_id, "s", "r", "paused.mkv", "paused.mkv"
            )
            repository.upsert_item(replace(paused, status=TaskItemStatus.PAUSED, stage="paused"))
            success = coordinator.record_discovered(
                task.task_id, "s", "r", "success.mkv", "success.mkv"
            )
            repository.upsert_item(
                replace(success, status=TaskItemStatus.SUCCESS, stage="completed")
            )
            selected = coordinator.retryable_items(task.task_id, failed_only=False)
            self.assertEqual([item.source_path for item in selected], ["paused.mkv"])

    def test_resume_never_upgrades_execute_authority(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            dry_run = coordinator.create("preview", execute_authorized=False)
            coordinator.request_pause(dry_run.task_id)
            coordinator.acknowledge_pause(dry_run.task_id)
            with self.assertRaisesRegex(ValueError, "not execute-authorized"):
                coordinator.reopen(dry_run.task_id, execute=True)

            authorized = coordinator.create("organize", execute_authorized=True)
            coordinator.request_pause(authorized.task_id)
            paused = coordinator.acknowledge_pause(authorized.task_id)
            self.assertFalse(
                PersistentTaskCoordinator(repository, repository)
                .create(paused.command, execute_authorized=False)
                .execute_authorized
            )

    def test_pause_is_distinct_from_cancellation(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("preview", execute_authorized=False)
            coordinator.request_pause(task.task_id)
            paused = coordinator.acknowledge_pause(task.task_id)
            self.assertEqual(paused.status, PersistentTaskStatus.PAUSED)
            self.assertIsNone(paused.completed_at)
            cancelled = coordinator.cancel(task.task_id)
            self.assertEqual(cancelled.status, PersistentTaskStatus.CANCELLED)
            self.assertIsNotNone(cancelled.completed_at)

    def test_pause_command_constructs_no_storage_or_provider(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document["persistence"] = {"databasePath": str(database)}
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "preview", execute_authorized=False
                )
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("pause constructed Storage"),
            ):
                code = final_main(
                    ["--config", str(config), "tasks", "pause", task.task_id],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(code, 0, errors.getvalue())
            self.assertIn("Pause requested: YES", output.getvalue())

    def test_task_output_is_bounded_and_shows_pause_state(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("preview", execute_authorized=False)
            requested = coordinator.request_pause(task.task_id)
            rendered = render_task(requested, ())
            self.assertIn("Pause requested: YES", rendered)
            self.assertNotIn("token", rendered.casefold())

    def test_paused_scan_resume_rescans_scope_without_repeating_discovered_item(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "Incoming"
            incoming.mkdir()
            (incoming / "first.mkv").write_bytes(b"first")
            (incoming / "second.mkv").write_bytes(b"second")
            target = root / "Target"
            target.mkdir()
            database = root / "runtime.sqlite3"
            document["storages"][0]["rootPath"] = str(root)
            document["storages"][1]["rootPath"] = str(target)
            document["resourceLibraries"][0]["storagePath"] = "Incoming"
            document["resourceLibraries"][0]["displayRootPath"] = str(incoming)
            document["persistence"] = {"databasePath": str(database)}
            document["historyPath"] = str(root / "history.jsonl")
            config = root / "config.json"
            config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                original = coordinator.create("scan", execute_authorized=False)
                coordinator.record_discovered(
                    original.task_id,
                    "source-storage",
                    "source",
                    "Incoming/first.mkv",
                    "source-storage:Incoming/first.mkv",
                )
                coordinator.request_pause(original.task_id)
                coordinator.acknowledge_pause(original.task_id)

            output, errors = io.StringIO(), io.StringIO()
            code = final_main(
                ["--config", str(config), "tasks", "resume", original.task_id],
                stdout=output,
                stderr=errors,
            )
            self.assertEqual(code, 0, errors.getvalue())
            with SQLiteTaskRepository(database) as repository:
                continuation = next(
                    task for task in repository.list_tasks() if task.task_id != original.task_id
                )
                paths = {item.source_path for item in repository.list_items(continuation.task_id)}
                self.assertEqual(paths, {"Incoming/second.mkv"})
                self.assertEqual(continuation.status, PersistentTaskStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
