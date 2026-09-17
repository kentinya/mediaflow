from __future__ import annotations

import copy
import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

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


class Schema34To35UpgradeTests(unittest.TestCase):
    """The real 34 -> 35 task_items upgrade keeps every write order-independent.

    A database upgraded in place appends ``progress`` after the occurrence
    columns, while a fresh database declares ``progress`` directly after
    ``error``.  Every TaskItem write must name its columns explicitly, so both
    layouts store and load identical values and no later caller can silently
    reintroduce physical-column-order dependence.
    """

    _TASKS_DDL = """
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
            execute_authorized INTEGER NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
            total_items INTEGER NOT NULL, completed_items INTEGER NOT NULL,
            failed_items INTEGER NOT NULL, error TEXT,
            pause_requested INTEGER NOT NULL DEFAULT 0,
            scope_path TEXT, item_limit INTEGER,
            configuration_snapshot_id TEXT, configuration_snapshot_digest TEXT
        )
    """

    _SCHEMA34_TASK_ITEMS_DDL = """
        CREATE TABLE task_items (
            item_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, storage_id TEXT NOT NULL,
            resource_library_id TEXT NOT NULL, source_path TEXT NOT NULL,
            source_display TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
            attempts INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            plan_id TEXT, destination_storage_id TEXT, destination_path TEXT,
            execution_status TEXT, error TEXT,
            source_occurrence_id TEXT, source_fingerprint TEXT,
            source_fingerprint_state TEXT NOT NULL DEFAULT 'unverified',
            UNIQUE(task_id, storage_id, source_path),
            FOREIGN KEY(task_id) REFERENCES tasks(task_id)
        )
    """

    _SCHEMA34_TASK_RESULTS_DDL = """
        CREATE TABLE task_results (
            result_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, item_id TEXT NOT NULL,
            source_storage_id TEXT NOT NULL, source_path TEXT NOT NULL,
            destination_storage_id TEXT, destination_path TEXT, recognition_type TEXT,
            provider TEXT, provider_id TEXT, metadata_policy_id TEXT,
            naming_policy_id TEXT, classification_policy_id TEXT,
            organize_policy_id TEXT, operation TEXT, status TEXT NOT NULL,
            created_at TEXT NOT NULL, title TEXT, error TEXT,
            completed_operations TEXT NOT NULL DEFAULT '[]',
            attachment_count INTEGER NOT NULL DEFAULT 0,
            retry_attempts INTEGER NOT NULL DEFAULT 0,
            retry_category TEXT,
            cleanup_status TEXT,
            cleanup_step_count INTEGER NOT NULL DEFAULT 0,
            effect_certainty TEXT NOT NULL DEFAULT 'unknown',
            uncertain_effects TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(task_id) REFERENCES tasks(task_id),
            FOREIGN KEY(item_id) REFERENCES task_items(item_id)
        )
    """

    _FILE_LOCKS_DDL = """
        CREATE TABLE file_locks (
            storage_id TEXT NOT NULL, path TEXT NOT NULL, task_id TEXT NOT NULL,
            acquired_at TEXT NOT NULL, PRIMARY KEY(storage_id, path)
        )
    """

    @staticmethod
    def _create_schema34_database(path: Path) -> None:
        """Create a production-shaped schema-34 runtime database.

        ``task_items`` already carries the occurrence columns the schema-34
        additive migration appended after ``error``, and has no ``progress``
        column; ``task_results`` likewise predates the occurrence columns.
        The production repository migration then appends ``progress`` at the
        physical end of the upgraded table.
        """

        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            connection.execute("INSERT INTO schema_version VALUES ('runtime', 34)")
            for ddl in (
                Schema34To35UpgradeTests._TASKS_DDL,
                Schema34To35UpgradeTests._SCHEMA34_TASK_ITEMS_DDL,
                Schema34To35UpgradeTests._SCHEMA34_TASK_RESULTS_DDL,
                Schema34To35UpgradeTests._FILE_LOCKS_DDL,
            ):
                connection.execute(ddl)
            connection.execute("CREATE INDEX task_items_task_status ON task_items(task_id, status)")
            connection.commit()
        finally:
            connection.close()

    def test_upgraded_layout_persists_and_reloads_task_items(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "upgraded.sqlite3")
            self._create_schema34_database(database)
            # The physical layout before the production migration: the
            # occurrence columns sit directly after ``error``.
            with sqlite3.connect(database) as connection:
                before = [
                    row[1] for row in connection.execute("PRAGMA table_info(task_items)").fetchall()
                ]
            self.assertEqual(
                before[-3:],
                ["source_occurrence_id", "source_fingerprint", "source_fingerprint_state"],
            )
            self.assertNotIn("progress", before)

            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                # The migration appended ``progress`` at the physical end.
                with sqlite3.connect(database) as connection:
                    after = [
                        row[1]
                        for row in connection.execute("PRAGMA table_info(task_items)").fetchall()
                    ]
                self.assertEqual(after[-1], "progress")
                self.assertEqual(
                    after[-4:-1],
                    ["source_occurrence_id", "source_fingerprint", "source_fingerprint_state"],
                )

                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("organize", execute_authorized=True)

                # 1. An ordinary TaskItem inserts and reloads with progress NULL
                #    on the upgraded layout.
                ordinary = coordinator.record_discovered(
                    task.task_id, "源存储", "电影", "电影/千与千寻.mkv", "千与千寻.mkv"
                )
                loaded = repository.get_item(ordinary.item_id)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded.source_path, ordinary.source_path)
                self.assertIsNone(loaded.progress)
                self.assertEqual(loaded.source_fingerprint_state, "unverified")

                # 2. A transfer TaskItem persists and reloads bounded progress
                #    without corrupting any other column.
                transfer = replace(
                    ordinary,
                    item_id=str(uuid5(NAMESPACE_URL, f"{task.task_id}:目标存储:媒体/千与千寻.mkv")),
                    storage_id="源存储",
                    resource_library_id="电影",
                    source_path="媒体/千与千寻.mkv",
                    source_display="千与千寻.mkv",
                    status=TaskItemStatus.PROCESSING,
                    stage="transfer",
                    destination_storage_id="目标存储",
                    destination_path="媒体/千与千寻.mkv",
                    progress=json.dumps(
                        {
                            "version": 1,
                            "status": "processing",
                            "confirmedEntries": [
                                ["媒体/千与千寻.mkv", "媒体/千与千寻.mkv", "file"]
                            ],
                            "confirmedTruncated": False,
                            "completedEntries": 0,
                            "failedEntries": 0,
                            "skippedEntries": 0,
                            "truncated": False,
                            "entries": [],
                        }
                    ),
                )
                repository.upsert_item(transfer)
                reloaded = repository.get_item(transfer.item_id)
                self.assertIsNotNone(reloaded)
                assert reloaded is not None
                self.assertEqual(reloaded.status, TaskItemStatus.PROCESSING)
                self.assertEqual(
                    json.loads(reloaded.progress or "")["confirmedEntries"],
                    [["媒体/千与千寻.mkv", "媒体/千与千寻.mkv", "file"]],
                )
                self.assertEqual(reloaded.destination_storage_id, "目标存储")
                self.assertEqual(reloaded.destination_path, "媒体/千与千寻.mkv")

                # 3. Terminal completion clears progress and publishes the
                #    Result without corrupting the row.
                coordinator.complete_direct_item(
                    reloaded,
                    status=TaskItemStatus.SUCCESS,
                    operation="COPY",
                    target_path="媒体/千与千寻.mkv",
                    destination_storage_id="目标存储",
                    completed_operations=("COPY",),
                )
                terminal = repository.get_item(transfer.item_id)
                self.assertIsNotNone(terminal)
                assert terminal is not None
                self.assertEqual(terminal.status, TaskItemStatus.SUCCESS)
                self.assertIsNone(terminal.progress)
                result = repository.list_results(task.task_id)[0]
                self.assertEqual(result.completed_operations, ("COPY",))
                self.assertEqual(result.destination_storage_id, "目标存储")

            # 4. A fresh (non-upgraded) database declares ``progress`` before
            #    the occurrence columns and loads the same values.
            with tempfile.TemporaryDirectory() as fresh_directory:
                fresh_database = Path(fresh_directory, "fresh.sqlite3")
                with SQLiteTaskRepository(fresh_database) as fresh:
                    with sqlite3.connect(fresh_database) as connection:
                        columns = [
                            row[1]
                            for row in connection.execute(
                                "PRAGMA table_info(task_items)"
                            ).fetchall()
                        ]
                    self.assertLess(
                        columns.index("progress"), columns.index("source_occurrence_id")
                    )
                    self.assertEqual(fresh.schema_version, SCHEMA_VERSION)

    def test_all_task_item_inserts_name_their_columns(self) -> None:
        """No task_items write may depend on the physical column order again."""

        import inspect

        from mediaflow.infrastructure import sqlite_runtime

        source = inspect.getsource(sqlite_runtime)
        self.assertNotIn(
            "INSERT INTO task_items VALUES",
            source,
            "a positional task_items INSERT depends on the physical column order; "
            "every insert must name its columns (see _TASK_ITEM_COLUMNS)",
        )
        self.assertIn("_TASK_ITEM_UPSERT", source)
        self.assertIn("_TASK_ITEM_INSERT", source)


if __name__ == "__main__":
    unittest.main()
