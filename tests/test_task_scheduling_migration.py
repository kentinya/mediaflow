"""schema 53 → 56 on genuine base-revision databases, and failure atomicity.

The base side of every database in this module is created by the *Task Base
revision itself* (extracted with ``git archive``), never by a shortcut that
rewrites a fresh database's version number.  The candidate then upgrades the same
file, so an upgrade path that only works on a synthetic fixture cannot pass here.

Two failure boundaries are injected on purpose — the additive index creation and
the schema-marker advance — because "the marker is the last durable step" is only
believed if it is broken once and the previous version still works.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.application.task_scheduling import TaskSchedulingService
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.domain.task_scheduling import TaskTrigger
from mediaflow.infrastructure import sqlite_runtime
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

TASK_BASE_SHA = "45d2e951eb00ffdd4cecbaafed50039668e445f0"
BASE_SCHEMA = 53
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)

_BASE_SEED = """
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    RunDisplayContext,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

database = Path(sys.argv[1])
report = Path(sys.argv[2])
now = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
with SQLiteTaskRepository(database) as repository:
    assert repository.schema_version == 53, repository.schema_version
    task = PersistentTask(
        "base-task",
        "organize",
        PersistentTaskStatus.PAUSED,
        True,
        now,
        now,
        started_at=now,
        total_items=2,
        completed_items=1,
        scope_path="媒体/电影",
        item_limit=10,
        configuration_snapshot_id="snapshot-base",
        configuration_snapshot_digest="digest-base",
    )
    repository.create_task(
        task,
        display=RunDisplayContext(
            source_scope="媒体/电影", target_scope="Media", labels=("电影", "基线")
        ),
    )
    repository.upsert_item(
        PersistentTaskItem(
            "base-item-1",
            "base-task",
            "local",
            "library",
            "媒体/电影/A.mkv",
            "媒体/电影/A.mkv",
            TaskItemStatus.SUCCESS,
            "completed",
            1,
            now,
            now,
            plan_id="plan-1",
            destination_storage_id="local",
            destination_path="Media/A/A.mkv",
            execution_status="success",
            source_occurrence_id="occ-1",
            source_fingerprint="fingerprint-1",
            source_fingerprint_state="trusted",
            source_observed_at=now,
            source_storage_path="媒体/电影/A.mkv",
        )
    )
    repository.upsert_item(
        PersistentTaskItem(
            "base-item-2",
            "base-task",
            "local",
            "library",
            "媒体/电影/B.mkv",
            "媒体/电影/B.mkv",
            TaskItemStatus.WAITING_CONFIRM,
            "waiting_confirm",
            1,
            now,
            now,
            plan_id="plan-2",
            destination_storage_id="local",
            destination_path="Media/B/B.mkv",
            source_storage_path="媒体/电影/B.mkv",
        )
    )
    repository.append_result(
        PersistentResultRecord(
            "base-item-1:1",
            "base-task",
            "base-item-1",
            "local",
            "媒体/电影/A.mkv",
            "local",
            "Media/A/A.mkv",
            "C",
            "tmdb",
            "603",
            "metadata-A",
            "naming-A",
            "classification-A",
            "organize-A",
            "move",
            "success",
            now,
            title="矩阵",
            completed_operations=("move",),
            effect_certainty="verified_complete",
            primary_completed=True,
        )
    )
    repository.create_job(
        AutomationJob(
            "base-job-linked",
            AutomationCommand.ORGANIZE,
            AutomationJobStatus.COMPLETED,
            now,
            now,
            task_id="base-task",
            execute_authorized=True,
            configuration_snapshot_id="snapshot-base",
            configuration_snapshot_digest="digest-base",
        )
    )
    repository.create_job(
        AutomationJob(
            "base-job-unlinked",
            AutomationCommand.ORGANIZE,
            AutomationJobStatus.PENDING,
            now,
            now,
        )
    )
    assert repository.acquire(
        "local", "媒体/电影/C.mkv", "base-task", now, owner_token="generation-1"
    )
    report.write_text(json.dumps({"schema": repository.schema_version}))
"""

_READ_WITH_REVISION = """
import json
import sys
from pathlib import Path

from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

database = Path(sys.argv[1])
with SQLiteTaskRepository(database) as repository:
    task = repository.get_task("base-task")
    print(
        json.dumps(
            {
                "schema": repository.schema_version,
                "status": None if task is None else task.status.value,
                "snapshot": None if task is None else task.configuration_snapshot_id,
                "items": len(repository.list_items("base-task")),
                "results": len(repository.list_results("base-task")),
            }
        )
    )
"""


def _git_archive(revision: str, destination: Path) -> Path:
    """Extract one immutable revision, so the base side is genuinely base code."""

    destination.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "archive", revision],
        cwd=str(REPOSITORY_ROOT),
        capture_output=True,
        check=False,
        timeout=300,
    )
    assert archive.returncode == 0, archive.stderr.decode()
    extract = subprocess.run(
        ["tar", "-x", "-C", str(destination)],
        input=archive.stdout,
        capture_output=True,
        check=False,
        timeout=300,
    )
    assert extract.returncode == 0, extract.stderr.decode()
    return destination


def _run(code: str, tree: Path, *arguments: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", code, *arguments],
        cwd=str(tree),
        env={**os.environ, "PYTHONPATH": str(tree)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise AssertionError(f"revision subprocess failed: {result.stderr[-4000:]}")
    return result.stdout


class TaskSchedulingMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._archive = tempfile.TemporaryDirectory()
        cls.base_root = _git_archive(TASK_BASE_SHA, Path(cls._archive.name, "base"))
        cls.candidate_root = Path(cls._archive.name, "candidate")
        shutil.copytree(
            REPOSITORY_ROOT / "mediaflow",
            cls.candidate_root / "mediaflow",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._archive.cleanup()

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = Path(self._directory.name)

    def base_database(self, name: str = "runtime.sqlite3") -> Path:
        """One genuine Task-Base database with representative durable facts."""

        database = self.directory / name
        report = self.directory / "base-report.json"
        _run(_BASE_SEED, self.base_root, str(database), str(report))
        self.assertEqual(json.loads(report.read_text())["schema"], BASE_SCHEMA)
        with sqlite3.connect(database) as connection:
            marker = connection.execute(
                "SELECT version FROM schema_version WHERE component='runtime'"
            ).fetchone()[0]
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='task_scheduling'"
                ).fetchall()
            }
        self.assertEqual(marker, BASE_SCHEMA)
        self.assertEqual(tables, set())
        return database

    def assert_base_facts_intact(self, repository: SQLiteTaskRepository) -> None:
        task = repository.get_task("base-task")
        self.assertIsNotNone(task)
        assert task is not None
        self.assertIs(task.status, PersistentTaskStatus.PAUSED)
        self.assertTrue(task.execute_authorized)
        self.assertEqual(task.scope_path, "媒体/电影")
        self.assertEqual(task.item_limit, 10)
        self.assertEqual(task.configuration_snapshot_id, "snapshot-base")
        self.assertEqual(task.configuration_snapshot_digest, "digest-base")
        self.assertEqual(task.total_items, 2)
        items = {item.item_id: item for item in repository.list_items("base-task")}
        self.assertEqual(set(items), {"base-item-1", "base-item-2"})
        self.assertIs(items["base-item-1"].status, TaskItemStatus.SUCCESS)
        self.assertEqual(items["base-item-1"].destination_path, "Media/A/A.mkv")
        self.assertEqual(items["base-item-1"].source_fingerprint, "fingerprint-1")
        self.assertEqual(items["base-item-1"].source_storage_path, "媒体/电影/A.mkv")
        self.assertIs(items["base-item-2"].status, TaskItemStatus.WAITING_CONFIRM)
        results = repository.list_results("base-task")
        self.assertEqual([value.result_id for value in results], ["base-item-1:1"])
        self.assertEqual(results[0].recognition_type, "C")
        self.assertEqual(results[0].naming_policy_id, "naming-A")
        self.assertEqual(results[0].effect_certainty, "verified_complete")
        linked = repository.get_job("base-job-linked")
        self.assertIsNotNone(linked)
        assert linked is not None
        self.assertEqual(linked.task_id, "base-task")
        self.assertTrue(linked.execute_authorized)
        unlinked = repository.get_job("base-job-unlinked")
        self.assertIsNotNone(unlinked)
        assert unlinked is not None
        self.assertIsNone(unlinked.task_id)
        self.assertEqual(unlinked.status.value, "pending")
        self.assertTrue(
            repository.lock_owned(
                "local", "媒体/电影/C.mkv", "base-task", owner_token="generation-1"
            )
        )
        self.assertEqual(
            repository.library_file_operation_display(("base-task",)),
            {"base-task": ("媒体/电影", "Media")},
        )

    def assert_never_admitted(self, repository: SQLiteTaskRepository, database: Path) -> None:
        """A migrated legacy row is never silently handed to the new kernel."""

        self.assertIsNone(repository.get_task_scheduling("base-task"))
        self.assertEqual(repository.count_scheduled_capacity_use(), 0)
        repository.register_worker(
            "worker-1", "worker one", 5.0, ("organize",), None, None, SCHEMA_VERSION, NOW
        )
        self.assertIsNone(
            repository.claim_next_scheduled_task(
                NOW,
                worker_id="worker-1",
                claim_token="token",
                lease_seconds=30,
            )
        )
        with sqlite3.connect(database) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM task_scheduling").fetchone()[0], 0
            )

    def test_a_genuine_schema53_database_upgrades_and_admits_nothing(self) -> None:
        database = self.base_database()
        with SQLiteTaskRepository(database) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            self.assertEqual(SCHEMA_VERSION, 56)
            self.assert_base_facts_intact(repository)
            self.assert_never_admitted(repository, database)
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

        # The upgrade is idempotent and repeatable.
        with SQLiteTaskRepository(database) as reopened:
            self.assertEqual(reopened.schema_version, SCHEMA_VERSION)
            self.assert_base_facts_intact(reopened)
            self.assertIsNone(reopened.get_task_scheduling("base-task"))

    def test_upgraded_database_still_supports_every_existing_task_writer(self) -> None:
        database = self.base_database()
        with SQLiteTaskRepository(database) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create(
                "organize",
                execute_authorized=True,
                scope_path="Media",
                item_limit=5,
                configuration_snapshot_id="snapshot-new",
                configuration_snapshot_digest="digest-new",
            )
            item = coordinator.begin_item(
                task.task_id, "local", "library", "In/new.mkv", "In/new.mkv"
            )
            self.assertIs(item.status, TaskItemStatus.PROCESSING)
            persisted = repository.get_item(item.item_id)
            self.assertEqual(persisted.source_path, "In/new.mkv")
            coordinator.request_pause(task.task_id)
            paused = coordinator.acknowledge_pause(task.task_id)
            self.assertIs(paused.status, PersistentTaskStatus.PAUSED)
            self.assertIsNone(repository.get_task_scheduling(task.task_id))

    def test_fresh_and_upgraded_databases_share_one_scheduling_layout(self) -> None:
        upgraded_database = self.base_database("upgraded.sqlite3")
        with SQLiteTaskRepository(upgraded_database) as upgraded:
            self.assertEqual(upgraded.schema_version, SCHEMA_VERSION)
        fresh_database = self.directory / "fresh.sqlite3"
        with SQLiteTaskRepository(fresh_database) as fresh:
            self.assertEqual(fresh.schema_version, SCHEMA_VERSION)

        def layout(database: Path) -> tuple[list[tuple], list[str]]:
            with sqlite3.connect(database) as connection:
                columns = connection.execute("PRAGMA table_info(task_scheduling)").fetchall()
                indexes = sorted(
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='index' "
                        "AND tbl_name='task_scheduling' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                )
            return (columns, indexes)

        self.assertEqual(layout(upgraded_database), layout(fresh_database))
        with SQLiteTaskRepository(upgraded_database) as upgraded:
            self.assertEqual(upgraded.schema_version, SCHEMA_VERSION)
        self.assertEqual(
            [row[1] for row in layout(fresh_database)[0]],
            list(sqlite_runtime._TASK_SCHEDULING_COLUMNS),
        )

    def test_a_failed_index_creation_keeps_schema53_and_the_old_code_readable(self) -> None:
        database = self.base_database()
        with patch.object(
            sqlite_runtime,
            "_TASK_SCHEDULING_CAPACITY_INDEX",
            "CREATE INDEX IF NOT EXISTS task_scheduling_capacity "
            "ON task_scheduling(queue_state, no_such_column)",
        ):
            with self.assertRaises(sqlite3.OperationalError):
                SQLiteTaskRepository(database)

        with sqlite3.connect(database) as connection:
            marker = connection.execute(
                "SELECT version FROM schema_version WHERE component='runtime'"
            ).fetchone()[0]
        self.assertEqual(marker, BASE_SCHEMA)
        # The previous code still reads the file exactly as it left it.
        observed = json.loads(_run(_READ_WITH_REVISION, self.base_root, str(database)))
        self.assertEqual(observed["schema"], BASE_SCHEMA)
        self.assertEqual(observed["status"], "paused")
        self.assertEqual(observed["snapshot"], "snapshot-base")
        self.assertEqual(observed["items"], 2)
        self.assertEqual(observed["results"], 1)

        # Without the fault the same file completes the upgrade.
        with SQLiteTaskRepository(database) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            self.assert_base_facts_intact(repository)

    def test_a_failed_schema_marker_advance_repeats_safely(self) -> None:
        database = self.base_database()
        with patch.object(
            SQLiteTaskRepository,
            "_advance_runtime_schema_marker",
            side_effect=RuntimeError("injected marker failure"),
        ):
            with self.assertRaises(RuntimeError):
                SQLiteTaskRepository(database)

        with sqlite3.connect(database) as connection:
            marker = connection.execute(
                "SELECT version FROM schema_version WHERE component='runtime'"
            ).fetchone()[0]
            rows = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("tasks", "task_items", "task_results", "automation_jobs")
            }
        self.assertEqual(marker, BASE_SCHEMA)
        self.assertEqual(
            rows, {"tasks": 1, "task_items": 2, "task_results": 1, "automation_jobs": 2}
        )
        observed = json.loads(_run(_READ_WITH_REVISION, self.base_root, str(database)))
        self.assertEqual(observed["schema"], BASE_SCHEMA)
        self.assertEqual(observed["status"], "paused")

        with SQLiteTaskRepository(database) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            self.assert_base_facts_intact(repository)
            self.assertEqual(repository.count_scheduled_capacity_use(), 0)

    def test_a_database_newer_than_this_code_is_still_refused(self) -> None:
        database = self.base_database()
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE schema_version SET version=? WHERE component='runtime'",
                (SCHEMA_VERSION + 1,),
            )
            connection.commit()
        with self.assertRaises(ValueError):
            SQLiteTaskRepository(database)
        with sqlite3.connect(database) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT version FROM schema_version WHERE component='runtime'"
                ).fetchone()[0],
                SCHEMA_VERSION + 1,
            )


class SchedulingContinuationActorMigrationTests(unittest.TestCase):
    """Schema 56 adds only the operator-continuation actor to scheduling rows."""

    def test_schema55_scheduling_row_gains_the_column_without_rewriting_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            now = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
            with SQLiteTaskRepository(database) as repository:
                service = TaskSchedulingService(repository, capacity=2)
                admission = service.admit(
                    "organize",
                    execute_authorized=True,
                    trigger=TaskTrigger.SCHEDULE,
                    principal="automation-scheduler",
                    request_id="before-schema56",
                    now=now,
                )
            with sqlite3.connect(database) as connection:
                # Recreate the exact pre-56 physical shape: the scheduling facts
                # existed, the continuation actor did not.
                connection.execute("ALTER TABLE task_scheduling DROP COLUMN continuation_actor")
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'", (55,)
                )
                connection.commit()
            with SQLiteTaskRepository(database) as upgraded:
                self.assertEqual(upgraded.schema_version, SCHEMA_VERSION)
                state = upgraded.get_task_scheduling(admission.task.task_id)
                self.assertIsNotNone(state)
                self.assertEqual("automation-scheduler", state.admission_principal)
                self.assertEqual("before-schema56", state.admission_request_id)
                self.assertIsNone(state.continuation_actor)
                task = upgraded.get_task(admission.task.task_id)
                self.assertTrue(task.execute_authorized)
            # The additive migration is idempotent and keeps the same row.
            with SQLiteTaskRepository(database) as reopened:
                state = reopened.get_task_scheduling(admission.task.task_id)
                self.assertEqual("automation-scheduler", state.admission_principal)
                self.assertIsNone(state.continuation_actor)


class ManualExecutionTaskScopeMigrationTests(unittest.TestCase):
    """Schema 55 rebuilds only the legacy one-execution-per-Task constraint."""

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.database = Path(self._directory.name) / "runtime.sqlite3"

    def _legacy_database(self) -> None:
        with sqlite3.connect(self.database) as connection:
            connection.executescript(
                """
                CREATE TABLE schema_version (
                    component TEXT PRIMARY KEY, version INTEGER NOT NULL
                );
                INSERT INTO schema_version VALUES ('runtime', 54);
                CREATE TABLE manual_executions (
                    execution_id TEXT PRIMARY KEY, preview_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL, authorization_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL UNIQUE, actor TEXT NOT NULL,
                    intent_version INTEGER NOT NULL, configuration_snapshot_id TEXT NOT NULL,
                    configuration_snapshot_digest TEXT NOT NULL,
                    selected_item_ids_json TEXT NOT NULL, unselected_item_ids_json TEXT NOT NULL,
                    status TEXT NOT NULL, next_action TEXT NOT NULL, error TEXT,
                    allow_overwrite INTEGER NOT NULL DEFAULT 0,
                    allow_source_cleanup INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT,
                    worker_id TEXT, claim_token TEXT, claimed_at TEXT,
                    claim_expires_at TEXT, attempts INTEGER NOT NULL DEFAULT 0
                );
                INSERT INTO manual_executions (
                    execution_id, preview_id, intent_id, authorization_id, task_id, actor,
                    intent_version, configuration_snapshot_id, configuration_snapshot_digest,
                    selected_item_ids_json, unselected_item_ids_json, status, next_action,
                    created_at, updated_at
                ) VALUES (
                    'exec-legacy', 'preview-legacy', 'intent-legacy', 'auth-legacy',
                    'task-legacy', 'operator', 1, 'snap', 'digest', '[]', '[]',
                    'completed', 'none', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
                );
                """
            )

    def test_the_constraint_is_removed_and_the_row_is_preserved(self) -> None:
        self._legacy_database()
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT execution_id, task_id FROM manual_executions"
                ).fetchall(),
                [("exec-legacy", "task-legacy")],
            )
            # A second execution for the same Task is now legal.
            connection.execute(
                "INSERT INTO manual_executions ("
                "execution_id, preview_id, intent_id, authorization_id, task_id, actor, "
                "intent_version, configuration_snapshot_id, configuration_snapshot_digest, "
                "selected_item_ids_json, unselected_item_ids_json, status, next_action, "
                "created_at, updated_at) VALUES ("
                "'exec-second', 'preview-second', 'intent-second', 'auth-second', "
                "'task-legacy', 'operator', 2, 'snap2', 'digest2', '[]', '[]', "
                "'completed', 'none', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
            )
            connection.commit()
            count = connection.execute(
                "SELECT COUNT(*) FROM manual_executions WHERE task_id='task-legacy'"
            ).fetchone()[0]
            self.assertEqual(count, 2)
        # Idempotent: a second open must not rebuild or lose the preserved rows.
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
        with sqlite3.connect(self.database) as connection:
            unique_on_task = [
                index[1]
                for index in connection.execute("PRAGMA index_list(manual_executions)")
                if index[2]
                and [row[2] for row in connection.execute(f"PRAGMA index_info({index[1]})")]
                == ["task_id"]
            ]
            self.assertEqual(unique_on_task, [])
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM manual_executions").fetchone()[0], 2
            )


if __name__ == "__main__":
    unittest.main()
