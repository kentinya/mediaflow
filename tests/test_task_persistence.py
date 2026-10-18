from __future__ import annotations

import copy
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from mediaflow.application.task_runtime import PersistentTaskCoordinator, TaskLockError
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
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

    def test_unknown_scan_command_creates_no_persistent_task_or_file_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "absent.json"
            errors = io.StringIO()
            with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
                final_main(
                    ["--config", str(config), "scan"],
                    stdout=io.StringIO(),
                    stderr=errors,
                )
            self.assertEqual(2, raised.exception.code)
            self.assertIn("invalid choice", errors.getvalue())
            self.assertEqual([], list(root.iterdir()))


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


class Schema36To37UpgradeTests(unittest.TestCase):
    """The real 36 -> 37 files_transfers upgrade preserves the claim fence.

    Schema 37 adds the durable in-flight mutation columns to
    ``files_transfers``.  A database upgraded in place must accept the same
    named-column inserts and loads as a freshly created one, and the new
    columns must default to no in-flight mutation.
    """

    _SCHEMA36_FILES_TRANSFERS_DDL = """
        CREATE TABLE files_transfers (
            transfer_id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL, authority_json TEXT NOT NULL,
            configuration_snapshot_id TEXT NOT NULL,
            configuration_snapshot_digest TEXT NOT NULL,
            worker_id TEXT, claim_token TEXT, claimed_at TEXT, claim_expires_at TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            error TEXT, next_action TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(task_id)
        )
    """

    @staticmethod
    def _create_schema36_database(path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            connection.execute("INSERT INTO schema_version VALUES ('runtime', 36)")
            connection.execute(
                """CREATE TABLE tasks (
                    task_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    execute_authorized INTEGER NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                    total_items INTEGER NOT NULL, completed_items INTEGER NOT NULL,
                    failed_items INTEGER NOT NULL, error TEXT,
                    pause_requested INTEGER NOT NULL DEFAULT 0,
                    scope_path TEXT, item_limit INTEGER,
                    configuration_snapshot_id TEXT, configuration_snapshot_digest TEXT
                )"""
            )
            connection.execute(Schema36To37UpgradeTests._SCHEMA36_FILES_TRANSFERS_DDL)
            connection.commit()
        finally:
            connection.close()

    def test_upgraded_files_transfers_gains_the_in_flight_fence_columns(self) -> None:
        from mediaflow.domain.task_persistence import (
            FilesTransferStatus,
            PersistentFilesTransfer,
            PersistentTask,
        )

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "upgraded.sqlite3")
            self._create_schema36_database(database)
            now = datetime.now(UTC)
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                with sqlite3.connect(database) as connection:
                    columns = [
                        row[1]
                        for row in connection.execute(
                            "PRAGMA table_info(files_transfers)"
                        ).fetchall()
                    ]
                self.assertIn("mutation_state", columns)
                self.assertIn("in_flight_item_id", columns)
                self.assertIn("in_flight_entry_path", columns)
                self.assertIn("in_flight_action", columns)

                task = PersistentTask(
                    "task-upgrade",
                    "files_transfer",
                    PersistentTaskStatus.PENDING,
                    True,
                    now,
                    now,
                )
                transfer = PersistentFilesTransfer(
                    transfer_id="task-upgrade",
                    task_id="task-upgrade",
                    status=FilesTransferStatus.ADMITTED,
                    authority_json="{}",
                    configuration_snapshot_id="rev",
                    configuration_snapshot_digest="digest",
                    created_at=now,
                    updated_at=now,
                )
                repository.admit_files_transfer(task, (), transfer)
                loaded = repository.require_files_transfer("task-upgrade")
                self.assertIsNone(loaded.mutation_state)
                self.assertIsNone(loaded.in_flight_entry_path)

                claim_token = "token-upgrade"
                self.assertIsNotNone(
                    repository.claim_next_files_transfer(
                        now,
                        worker_id="worker",
                        claim_token=claim_token,
                        lease_seconds=3600.0,
                    )
                )
                self.assertTrue(
                    repository.begin_files_transfer_mutation(
                        "task-upgrade",
                        claim_token,
                        now,
                        item_id="item-1",
                        entry_path="a.mkv",
                        action="copy",
                    )
                )
                opened = repository.require_files_transfer("task-upgrade")
                self.assertEqual(opened.mutation_state, "mutation_in_flight")
                self.assertEqual(opened.in_flight_entry_path, "a.mkv")
                # An in-flight transfer is never handed out by the ordinary
                # claim query, even after its lease elapses.
                self.assertIsNone(
                    repository.claim_next_files_transfer(
                        now + timedelta(hours=2),
                        worker_id="worker-2",
                        claim_token="token-2",
                        lease_seconds=3600.0,
                    )
                )
                resolved = repository.claim_expired_files_transfer_mutation(
                    now + timedelta(hours=2),
                    worker_id="worker-2",
                    claim_token="token-2",
                    lease_seconds=3600.0,
                )
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved.transfer_id, "task-upgrade")


class Schema37To38UpgradeTests(unittest.TestCase):
    """The real 37 -> 38 file_locks upgrade preserves an existing lock row.

    Schema 38 adds the durable owner generation to ``file_locks``.  An upgraded
    database must accept the same named-column inserts and loads as a fresh one,
    an existing lock row must survive with a conservative legacy identity that is
    still Task-level releasable but never matches a generation release, and a
    newly acquired generation must be exactly releasable without weakening the
    normalized-path uniqueness across Tasks.
    """

    _SCHEMA37_FILE_LOCKS_DDL = """
        CREATE TABLE file_locks (
            storage_id TEXT NOT NULL, path TEXT NOT NULL, task_id TEXT NOT NULL,
            acquired_at TEXT NOT NULL, PRIMARY KEY(storage_id, path)
        )
    """

    @staticmethod
    def _create_schema37_database(path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            connection.execute("INSERT INTO schema_version VALUES ('runtime', 37)")
            connection.execute(
                """CREATE TABLE tasks (
                    task_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    execute_authorized INTEGER NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                    total_items INTEGER NOT NULL, completed_items INTEGER NOT NULL,
                    failed_items INTEGER NOT NULL, error TEXT,
                    pause_requested INTEGER NOT NULL DEFAULT 0,
                    scope_path TEXT, item_limit INTEGER,
                    configuration_snapshot_id TEXT, configuration_snapshot_digest TEXT
                )"""
            )
            connection.execute(Schema37To38UpgradeTests._SCHEMA37_FILE_LOCKS_DDL)
            # A pre-existing lock row exactly as schema 37 could have written it.
            connection.execute(
                "INSERT INTO file_locks VALUES (?, ?, ?, ?)",
                ("source", "Media/movie.mkv", "task-existing", "2026-09-01T00:00:00+00:00"),
            )
            connection.commit()
        finally:
            connection.close()

    def test_upgraded_file_locks_gains_a_conservative_owner_generation(self) -> None:
        from mediaflow.infrastructure.sqlite_runtime import LEGACY_LOCK_OWNER_TOKEN

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "upgraded.sqlite3")
            self._create_schema37_database(database)
            now = datetime.now(UTC)
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                with sqlite3.connect(database) as connection:
                    columns = [
                        row[1]
                        for row in connection.execute("PRAGMA table_info(file_locks)").fetchall()
                    ]
                self.assertIn("owner_token", columns)
                # The existing row survived with the conservative legacy identity
                # rather than becoming unlocked or broadly releasable.
                with sqlite3.connect(database) as connection:
                    row = connection.execute(
                        "SELECT task_id, owner_token FROM file_locks WHERE storage_id=? AND path=?",
                        ("source", "Media/movie.mkv"),
                    ).fetchone()
                self.assertEqual(row[0], "task-existing")
                self.assertEqual(row[1], LEGACY_LOCK_OWNER_TOKEN)
                # It is still exactly releasable at Task level, and a
                # generation-carrying release never matches it.
                self.assertTrue(repository.lock_owned("source", "Media/movie.mkv", "task-existing"))
                self.assertFalse(
                    repository.release(
                        "source",
                        "Media/movie.mkv",
                        "task-existing",
                        owner_token="not-the-generation",
                    )
                )
                self.assertTrue(repository.lock_owned("source", "Media/movie.mkv", "task-existing"))
                self.assertTrue(repository.release("source", "Media/movie.mkv", "task-existing"))
                self.assertFalse(
                    repository.lock_owned("source", "Media/movie.mkv", "task-existing")
                )

                # A new acquisition carries a fresh generation.  Normalized-path
                # uniqueness across Tasks is preserved, and only the exact
                # generation may release the row.
                self.assertTrue(
                    repository.acquire(
                        "source",
                        "Media/other.mkv",
                        "task-a",
                        now,
                        owner_token="generation-a",
                    )
                )
                self.assertFalse(
                    repository.acquire(
                        "source",
                        "Media//other.mkv",
                        "task-b",
                        now,
                        owner_token="generation-b",
                    )
                )
                self.assertTrue(
                    repository.lock_owned(
                        "source", "Media/other.mkv", "task-a", owner_token="generation-a"
                    )
                )
                self.assertFalse(
                    repository.release(
                        "source",
                        "Media/other.mkv",
                        "task-a",
                        owner_token="generation-b",
                    )
                )
                self.assertTrue(
                    repository.lock_owned(
                        "source", "Media/other.mkv", "task-a", owner_token="generation-a"
                    )
                )
                self.assertTrue(
                    repository.release(
                        "source",
                        "Media/other.mkv",
                        "task-a",
                        owner_token="generation-a",
                    )
                )
                self.assertFalse(
                    repository.lock_owned(
                        "source", "Media/other.mkv", "task-a", owner_token="generation-a"
                    )
                )

    def test_fresh_and_upgraded_file_locks_load_the_same_values(self) -> None:
        """A fresh schema-38 table and an upgraded one behave identically."""

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "upgraded.sqlite3")
            self._create_schema37_database(database)
            now = datetime.now(UTC)
            with SQLiteTaskRepository(database) as upgraded:
                self.assertTrue(
                    upgraded.acquire("source", "a.mkv", "task-a", now, owner_token="token-a")
                )
                self.assertTrue(
                    upgraded.lock_owned("source", "a.mkv", "task-a", owner_token="token-a")
                )
                with sqlite3.connect(database) as connection:
                    upgraded_row = connection.execute(
                        "SELECT storage_id, path, task_id, owner_token FROM file_locks "
                        "WHERE path=?",
                        ("a.mkv",),
                    ).fetchone()
            with tempfile.TemporaryDirectory() as fresh_directory:
                fresh_database = Path(fresh_directory, "fresh.sqlite3")
                with SQLiteTaskRepository(fresh_database) as fresh:
                    self.assertTrue(
                        fresh.acquire("source", "a.mkv", "task-a", now, owner_token="token-a")
                    )
                    with sqlite3.connect(fresh_database) as connection:
                        fresh_row = connection.execute(
                            "SELECT storage_id, path, task_id, owner_token FROM file_locks "
                            "WHERE path=?",
                            ("a.mkv",),
                        ).fetchone()
            self.assertEqual(upgraded_row, fresh_row)
            self.assertEqual(upgraded_row[3], "token-a")


class Schema42To44UpgradeTests(unittest.TestCase):
    """The real 42 -> 44 continuation/recovery upgrade preserves durable facts.

    Schema 43 adds the durable queued continuation boundary and schema 44 adds
    the nullable origin Task on manual Previews. The fixture is a genuine
    schema-42 runtime database — every real table and column as schema 42
    shipped, with both additions absent and the marker set to 42 — so the
    upgrade is proven against the production shape rather than a hand-written
    subset.

    The upgrade must leave every durable fact the continuation depends on
    intact: the immutable pin, the recorded per-item outcome, the persisted
    one-shot authority and the original Result.  A pre-existing Task must never
    be handed a fabricated continuation.
    """

    #: The exact objects schemas 43 and 44 add. The fixture removes them to
    #: reproduce a real schema-42 database; production migrations re-add them.
    _SCHEMA42_OBJECTS = (
        "DROP INDEX IF EXISTS one_active_scope_continuation",
        "DROP INDEX IF EXISTS scope_continuations_source_created",
        "DROP TABLE IF EXISTS scope_continuations",
        "DROP INDEX IF EXISTS manual_previews_recovery_source",
        "ALTER TABLE manual_previews DROP COLUMN recovery_source_task_id",
    )

    @staticmethod
    def _create_schema42_database(path: Path) -> None:
        """Reproduce a production-shaped schema-42 database with real rows."""

        with SQLiteTaskRepository(path) as repository:
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create(
                "preview",
                execute_authorized=True,
                scope_path="Media",
                item_limit=10,
                configuration_snapshot_id="snap-base",
                configuration_snapshot_digest="digest-base",
                require_configuration_snapshot=True,
            )
            coordinator.record_discovered(
                task.task_id, "source", "source", "Media/one.mkv", "source:Media/one.mkv"
            )
            repository.upsert_item(
                replace(
                    repository.list_items(task.task_id)[0],
                    status=TaskItemStatus.SUCCESS,
                    stage="completed",
                )
            )
            repository.append_result(
                PersistentResultRecord(
                    "base-result",
                    task.task_id,
                    repository.list_items(task.task_id)[0].item_id,
                    "source",
                    "Media/one.mkv",
                    "target",
                    "Movies/one.mkv",
                    "C",
                    "tmdb",
                    "1",
                    "C",
                    "A",
                    "A",
                    "A",
                    "MOVE",
                    "success",
                    datetime(2026, 9, 1, tzinfo=UTC),
                    title="Base",
                )
            )
            repository.request_task_pause(task.task_id, datetime(2026, 9, 1, tzinfo=UTC))
            coordinator.acknowledge_pause(task.task_id)
        # Remove exactly the schema-43/44 additions and rewind the marker: the
        # result is a real schema-42 database that still holds every durable row.
        with sqlite3.connect(path) as connection:
            for statement in Schema42To44UpgradeTests._SCHEMA42_OBJECTS:
                connection.execute(statement)
            connection.execute("UPDATE schema_version SET version=42 WHERE component='runtime'")
            connection.commit()

    def test_schema42_upgrades_additively_and_preserves_the_paused_scope(self) -> None:
        from mediaflow.application.scope_continuation import remaining_scope

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "upgraded.sqlite3")
            self._create_schema42_database(database)
            # The fixture really is a schema-42 database without either new feature.
            with sqlite3.connect(database) as connection:
                marker = connection.execute(
                    "SELECT version FROM schema_version WHERE component='runtime'"
                ).fetchone()[0]
                objects = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE name LIKE '%scope_continuation%'"
                    ).fetchall()
                }
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(manual_previews)")
                }
            self.assertEqual(marker, 42)
            self.assertEqual(objects, set())
            self.assertNotIn("recovery_source_task_id", columns)

            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                self.assertEqual(SCHEMA_VERSION, 47)
                # Every pre-existing durable fact survived the additive upgrade.
                task = repository.get_task("base-task") or next(
                    item
                    for item in repository.list_tasks(limit=10)
                    if item.status is PersistentTaskStatus.PAUSED
                )
                self.assertIs(task.status, PersistentTaskStatus.PAUSED)
                self.assertTrue(task.execute_authorized)
                self.assertEqual(task.configuration_snapshot_id, "snap-base")
                self.assertEqual(task.configuration_snapshot_digest, "digest-base")
                self.assertEqual(task.scope_path, "Media")
                self.assertEqual(task.item_limit, 10)
                items = repository.list_items(task.task_id)
                self.assertEqual(len(items), 1)
                self.assertIs(items[0].status, TaskItemStatus.SUCCESS)
                results = repository.list_results(task.task_id)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].recognition_type, "C")
                self.assertEqual(results[0].status, "success")

                # The new boundary exists and is empty: an upgraded legacy Task
                # is never handed a fabricated continuation, and the remaining
                # scope is read from the preserved rows alone.
                self.assertEqual(repository.list_scope_continuations(task.task_id), ())
                self.assertIsNone(repository.get_scope_continuation_for_source_task(task.task_id))
                self.assertEqual(repository.list_scope_recovery_links(task.task_id), ())
                remaining, already_recorded, remaining_limit = remaining_scope(repository, task)
                self.assertEqual(remaining, ())
                self.assertEqual(already_recorded, {("source", "Media/one.mkv")})
                self.assertEqual(remaining_limit, 9)

            # The upgrade is idempotent: reopening changes nothing.
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.schema_version, SCHEMA_VERSION)
                self.assertEqual(len(reopened.list_items(task.task_id)), 1)
                self.assertEqual(len(reopened.list_results(task.task_id)), 1)

            # A database newer than this code still fails closed.
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (SCHEMA_VERSION + 1,),
                )
                connection.commit()
            with self.assertRaises(ValueError):
                SQLiteTaskRepository(database)

    def test_upgraded_scope_continuations_matches_a_freshly_created_one(self) -> None:
        """The migrated table accepts and loads exactly like a fresh one."""

        from mediaflow.domain.automation import (
            AutomationCommand,
            AutomationJob,
            AutomationJobStatus,
        )
        from mediaflow.domain.scope_continuation import (
            CONTINUATION_BOUNDARY,
            ScopeContinuation,
            ScopeContinuationStatus,
        )

        with tempfile.TemporaryDirectory() as directory:
            upgraded = Path(directory, "upgraded.sqlite3")
            fresh = Path(directory, "fresh.sqlite3")
            self._create_schema42_database(upgraded)
            # The same genuine population, but never rewound: a fresh schema-44 DB.
            self._create_schema42_database(fresh)
            with SQLiteTaskRepository(fresh):
                pass
            now = datetime(2026, 10, 4, tzinfo=UTC)

            def admit(database: Path) -> tuple[object, ...]:
                with SQLiteTaskRepository(database) as repository:
                    task = next(
                        item
                        for item in repository.list_tasks(limit=10)
                        if item.status is PersistentTaskStatus.PAUSED
                    )
                    job = AutomationJob(
                        "job-cont",
                        AutomationCommand.SCOPE_CONTINUATION,
                        AutomationJobStatus.PENDING,
                        now,
                        now,
                        limit=task.item_limit,
                        configuration_snapshot_id=task.configuration_snapshot_id,
                        configuration_snapshot_digest=task.configuration_snapshot_digest,
                    )
                    continuation = ScopeContinuation(
                        "cont-1",
                        task.task_id,
                        task.command,
                        task.scope_path,
                        task.item_limit,
                        task.configuration_snapshot_id or "",
                        task.configuration_snapshot_digest or "",
                        CONTINUATION_BOUNDARY,
                        ScopeContinuationStatus.QUEUED,
                        now,
                        now,
                        "operator",
                        "job-cont",
                    )
                    admitted, created = repository.admit_scope_continuation(
                        job, continuation, maximum_active_jobs=10
                    )
                    self.assertTrue(created)
                    stored = repository.get_scope_continuation_for_job("job-cont")
                    self.assertEqual(stored, admitted)
                    # The Task identity is generated per fixture, so it is
                    # normalized out: every other bounded field must match.
                    return tuple(
                        (key, value)
                        for key, value in stored.document().items()
                        if key != "source_task_id"
                    )

            self.assertEqual(admit(upgraded), admit(fresh))


class Schema44To45DiscoveryUpgradeTests(unittest.TestCase):
    """The additive 44 -> 45 discovery upgrade preserves prior durable facts.

    This is a bounded schema-shape fixture: it creates a current-schema
    database, removes exactly the schema-45 discovery objects and rewinds the
    marker, so the additive DDL is exercised over a database that still holds
    real admitted manual work.  It deliberately does not claim to be a
    rehearsal against a prior committed application build; that genuine
    prior-artifact rehearsal is the schema-38 -> 45 Docker upgrade smoke
    (``scripts/docker_upgrade_recovery_smoke_test.py``), which seeds historical
    manual intents/Previews/admitted/completed/partial/uncertain executions
    through the old image's own code and verifies them after the upgrade.
    """

    _SCHEMA44_OBJECTS = (
        "DROP INDEX IF EXISTS media_discovery_observations_discovery",
        "DROP TABLE IF EXISTS media_discovery_observations",
        "DROP INDEX IF EXISTS media_discoveries_status_created",
        "DROP INDEX IF EXISTS media_discoveries_actor_created",
        "DROP TABLE IF EXISTS media_discoveries",
    )

    @staticmethod
    def _create_schema44_database(path: Path) -> None:
        with SQLiteTaskRepository(path) as repository:
            repository.create_manual_intent_with_audit(
                _manual_intent("intent-base"),
                _manual_items("intent-base"),
                _manual_audit("intent-base"),
            )
            connection = repository._connection
            for statement in Schema44To45DiscoveryUpgradeTests._SCHEMA44_OBJECTS:
                connection.execute(statement)
            connection.execute("INSERT OR REPLACE INTO schema_version VALUES ('runtime', ?)", (44,))
            connection.commit()

    def test_schema44_upgrades_additively_and_keeps_the_admitted_intent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "schema-44.sqlite3")
            self._create_schema44_database(database)
            with sqlite3.connect(database) as connection:
                marker = connection.execute(
                    "SELECT version FROM schema_version WHERE component='runtime'"
                ).fetchone()[0]
                objects = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name LIKE 'media_discover%'"
                    ).fetchall()
                }
            self.assertEqual(marker, 44)
            self.assertEqual(objects, set())

            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                self.assertEqual(SCHEMA_VERSION, 47)
                # The pre-existing admitted intent survived the additive upgrade.
                intent = repository.get_manual_intent("intent-base")
                self.assertIsNotNone(intent)
                self.assertEqual(1, len(intent.items))
                # The new discovery boundary is present and empty.
                self.assertEqual((), repository.list_media_discoveries())
                tables = {
                    row["name"]
                    for row in repository._connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name LIKE 'media_discover%'"
                    ).fetchall()
                }
                self.assertEqual({"media_discoveries", "media_discovery_observations"}, tables)
                columns = {
                    row[1]
                    for row in repository._connection.execute(
                        "PRAGMA table_info(media_discovery_observations)"
                    ).fetchall()
                }
                self.assertIn("stable_since", columns)
                # The new boundary really persists work after the upgrade: a
                # discovery round-trips through the same repository, and the
                # pre-existing admitted manual intent still reads back.
                self._assert_discovery_round_trip(repository)

    def test_schema45_upgrades_additively_with_durable_wait_and_admission_identity(
        self,
    ) -> None:
        """A schema-45 database gains the two additive discovery columns.

        The real prior implementation (schema 45) had neither the durable
        stability re-observation deadline nor the persisted admission identity.
        Reopening must add both without changing the schema marker, without
        touching an existing row's identity, and without making legacy open work
        unreadable: a legacy row simply keeps no due time (immediately
        claimable) and no admission signature (not reconcilable by signature).
        """

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "schema-45.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                connection = repository._connection
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(media_discoveries)").fetchall()
                }
                self.assertIn("next_observation_at", columns)
                self.assertIn("admission_signature", columns)
                self.assertIn("admission_request_id", columns)
                # Simulate the real prior schema by dropping the three additive
                # columns, exactly as a schema-45 database created before these
                # corrections would have looked.
                connection.execute("DROP INDEX IF EXISTS media_discoveries_admission")
                connection.execute("DROP INDEX IF EXISTS media_discoveries_request")
                connection.execute("ALTER TABLE media_discoveries DROP COLUMN next_observation_at")
                connection.execute("ALTER TABLE media_discoveries DROP COLUMN admission_signature")
                connection.execute("ALTER TABLE media_discoveries DROP COLUMN admission_request_id")
                connection.execute(
                    "INSERT OR REPLACE INTO schema_version VALUES ('runtime', ?)", (45,)
                )
                connection.commit()
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    45,
                    connection.execute(
                        "SELECT version FROM schema_version WHERE component='runtime'"
                    ).fetchone()[0],
                )
                prior_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(media_discoveries)").fetchall()
                }
            self.assertNotIn("next_observation_at", prior_columns)
            self.assertNotIn("admission_signature", prior_columns)
            self.assertNotIn("admission_request_id", prior_columns)

            with SQLiteTaskRepository(database) as repository:
                # The additive upgrade did not need a version bump: the marker
                # stays exactly where the prior implementation left it.
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                columns = {
                    row[1]
                    for row in repository._connection.execute(
                        "PRAGMA table_info(media_discoveries)"
                    ).fetchall()
                }
                self.assertIn("next_observation_at", columns)
                self.assertIn("admission_signature", columns)
                self.assertIn("admission_request_id", columns)
                indexes = {
                    row["name"]
                    for row in repository._connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='index' "
                        "AND name LIKE 'media_discoveries%'"
                    ).fetchall()
                }
                self.assertIn("media_discoveries_admission", indexes)
                self.assertIn("media_discoveries_request", indexes)
                # A prior-schema admission stays readable and is simply not
                # reconcilable by client request identity: the honest unknown
                # outcome stands instead of a guessed navigation.
                self.assertIsNone(
                    repository.find_media_discovery_by_request_id(
                        actor="operator",
                        admission_request_id="00000000-0000-4000-8000-000000000000",
                    )
                )
                # The durable identity lookup is usable after the upgrade.
                self.assertIsNone(
                    repository.find_open_media_discovery(
                        actor="operator",
                        resource_library_id="library",
                        storage_id="storage",
                        snapshot_id="snap",
                        snapshot_digest="digest",
                        scope_signature="[]",
                    )
                )

    @staticmethod
    def _assert_discovery_round_trip(repository) -> None:
        from mediaflow.domain.media_discovery import (
            DiscoveryBudgets,
            DiscoveryCounters,
            DiscoveryEntryKind,
            DiscoveryIncompleteReason,
            DiscoveryProgress,
            DiscoveryScopeEntry,
            DiscoveryStatus,
            MediaDiscovery,
        )

        now = datetime(2026, 10, 4, tzinfo=UTC)
        discovery = MediaDiscovery(
            "discovery-round-trip",
            "operator",
            "library-base",
            "storage-base",
            "snap-base",
            "digest-base",
            DiscoveryStatus.COMPLETED,
            1,
            DiscoveryBudgets(),
            DiscoveryProgress(
                "completed",
                (DiscoveryScopeEntry("Movies", DiscoveryEntryKind.DIRECTORY),),
                DiscoveryCounters(),
                DiscoveryIncompleteReason.NONE,
                (),
                (),
            ),
            now,
            now,
            admission_request_id="11111111-1111-4111-8111-111111111111",
        )
        repository.create_media_discovery(discovery)
        stored = repository.get_media_discovery("discovery-round-trip")
        assert stored is not None
        assert stored.resource_library_id == "library-base"
        assert stored.storage_id == "storage-base"
        assert stored.progress.scope_entries[0].path == "Movies"
        # The client request identity survives the durable round trip and is
        # readable by the actor-bound proof lookup a lost response needs.
        assert stored.admission_request_id == "11111111-1111-4111-8111-111111111111"
        found = repository.find_media_discovery_by_request_id(
            actor="operator",
            admission_request_id="11111111-1111-4111-8111-111111111111",
        )
        assert found is not None and found.discovery_id == "discovery-round-trip"
        # A different actor can never recover another principal's admission.
        assert (
            repository.find_media_discovery_by_request_id(
                actor="intruder",
                admission_request_id="11111111-1111-4111-8111-111111111111",
            )
            is None
        )


class ManualRecoveryPreparationPersistenceTests(unittest.TestCase):
    def test_preparation_round_trips_and_supersedes_without_authority(self) -> None:
        """A prepared summary persists, supersedes and never invents authority."""

        from mediaflow.domain.manual_recovery import (
            ManualRecoveryPreparation,
            ManualRecoveryPreparationStatus,
        )

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "preparations.sqlite3")
            now = datetime(2026, 10, 17, tzinfo=UTC)
            with SQLiteTaskRepository(database) as repository:
                repository.create_manual_intent_with_audit(
                    _manual_intent("intent-1"),
                    _manual_items("intent-1"),
                    _manual_audit("intent-1"),
                )
                task_id, item_id = self._source_task_and_item(repository)
                preparation = ManualRecoveryPreparation(
                    "prep-1",
                    task_id,
                    item_id,
                    "continuation-1",
                    "analysis-task-1",
                    "analysis-result-1",
                    "intent-1",
                    "preview-1",
                    1,
                    "b" * 64,
                    "c" * 64,
                    "snap-1",
                    "digest-1",
                    "operator",
                    ManualRecoveryPreparationStatus.PREPARED,
                    now,
                    now,
                )
                repository.create_manual_recovery_preparation(preparation)
                stored = repository.get_manual_recovery_preparation("prep-1")
                assert stored is not None
                assert stored.authorization_id is None
                assert stored.execution_id is None
                assert stored.intent_version == 1
                assert stored.status is ManualRecoveryPreparationStatus.PREPARED
                assert repository.get_current_manual_recovery_preparation(task_id, item_id)
                assert repository.list_manual_recovery_preparations(task_id, item_id)

                # A prepared summary must not claim execution authority.
                with self.assertRaises(ValueError):
                    repository.create_manual_recovery_preparation(
                        replace(preparation, preparation_id="prep-bad", authorization_id="a")
                    )

                superseded = repository.supersede_manual_recovery_preparation("prep-1", now=now)
                assert superseded.status is ManualRecoveryPreparationStatus.SUPERSEDED
                assert repository.get_current_manual_recovery_preparation(task_id, item_id) is None

            # Reopening preserves the exact record; the historical row is intact.
            with SQLiteTaskRepository(database) as reopened:
                stored = reopened.get_manual_recovery_preparation("prep-1")
                assert stored is not None
                assert stored.status is ManualRecoveryPreparationStatus.SUPERSEDED
                assert stored.authorization_id is None

    def _source_task_and_item(self, repository):
        from mediaflow.application.task_runtime import PersistentTaskCoordinator
        from mediaflow.domain.task_persistence import TaskItemStatus

        coordinator = PersistentTaskCoordinator(repository, repository)
        task = coordinator.create(
            "manual_organize",
            execute_authorized=False,
            item_limit=1,
            configuration_snapshot_id="snap-1",
            configuration_snapshot_digest="digest-1",
            require_configuration_snapshot=True,
        )
        item = coordinator.begin_item(
            task.task_id, "source", "source", "Media/One.2001.mkv", "Media/One.2001.mkv"
        )
        repository.upsert_item(replace(item, status=TaskItemStatus.FAILED, stage="failed"))
        repository.release(item.storage_id, item.source_path, item.task_id)
        return task.task_id, item.item_id


class Schema45ToManualRecoveryPreparationUpgradeTests(unittest.TestCase):
    """The additive preparation table appears without touching prior facts."""

    def test_reopening_adds_the_preparation_table_and_preserves_prior_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "schema-preparation.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                repository.create_manual_intent_with_audit(
                    _manual_intent("intent-base"),
                    _manual_items("intent-base"),
                    _manual_audit("intent-base"),
                )
                connection = repository._connection
                connection.execute("DROP INDEX IF EXISTS manual_recovery_preparations_source")
                connection.execute("DROP TABLE IF EXISTS manual_recovery_preparations")
                connection.commit()
            with sqlite3.connect(database) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name LIKE 'manual_recovery_preparation%'"
                    ).fetchall()
                }
            self.assertEqual(tables, set())

            with SQLiteTaskRepository(database) as repository:
                tables = {
                    row[0]
                    for row in repository._connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name LIKE 'manual_recovery_preparation%'"
                    ).fetchall()
                }
                self.assertIn("manual_recovery_preparations", tables)
                # The pre-existing admitted intent is unchanged and has no
                # fabricated summary.
                intent = repository.get_manual_intent("intent-base")
                assert intent is not None
                self.assertEqual(intent.intent_id, "intent-base")
                self.assertEqual(repository.list_manual_recovery_preparations("task", "item"), ())


def _manual_intent(intent_id: str):
    from mediaflow.domain.manual_organize import (
        ManualConfigurationSnapshot,
        ManualIntentStatus,
        ManualOrganizeIntent,
    )

    now = datetime(2026, 10, 4, tzinfo=UTC)
    return ManualOrganizeIntent(
        intent_id,
        "operator",
        "snap-base",
        "digest-base",
        ManualIntentStatus.OPEN,
        1,
        now,
        now,
        _manual_items(intent_id),
        ManualConfigurationSnapshot("snap-base", "digest-base", (), (), (), (), ()),
        "continue to an exact zero-mutation Preview",
        None,
        (),
    )


def _manual_items(intent_id: str):
    from mediaflow.domain.manual_organize import (
        ManualChoice,
        ManualIntentItem,
        ManualIntentItemStatus,
        ManualSourceIdentity,
    )

    now = datetime(2026, 10, 4, tzinfo=UTC)
    source = ManualSourceIdentity(
        source_id="occ-base",
        storage_id="storage-base",
        resource_library_id="library-base",
        path="Movies/One.2001.mkv",
        filename="One.2001.mkv",
        extension="mkv",
        size=512,
        modified_at=now,
        observed_at=now,
        stable_since=None,
        occurrence_id="occ-base",
        fingerprint="a" * 64,
        fingerprint_algorithm="storage-entry-sha256",
        fingerprint_evidence={"source": "storage_entry"},
        occurrence_state="verified",
    )
    return (
        ManualIntentItem(
            "item-base",
            intent_id,
            0,
            source,
            ManualChoice("A", None, "A", "A", "A"),
            ManualIntentItemStatus.READY,
            None,
            1,
            now,
            now,
        ),
    )


def _manual_audit(intent_id: str):
    from mediaflow.domain.manual_organize import ManualIntentAudit

    now = datetime(2026, 10, 4, tzinfo=UTC)
    return ManualIntentAudit(
        "audit-base", intent_id, None, "operator", "created_from_storage_source", {}, {}, now
    )


if __name__ == "__main__":
    unittest.main()
