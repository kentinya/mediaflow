from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.dashboard import DashboardService
from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.file_index import FileIndexRecord
from mediaflow.domain.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
)
from mediaflow.domain.scanner import FileChange, FileScanStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    ConfirmationStatus,
    ConflictConfirmation,
    PersistentTask,
    PersistentTaskStatus,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def request(api, *, token: str | None = "viewer-token", query: str = ""):
    statuses = []
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/api/v1/dashboard",
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(body)


class DashboardTests(unittest.TestCase):
    def test_empty_database_does_not_create_file_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                snapshot = DashboardService(
                    repository, resource_library_count=0, media_library_count=0
                ).snapshot()
                self.assertEqual(snapshot.files.total, 0)
                self.assertEqual(snapshot.tasks.total, 0)
                self.assertEqual(snapshot.jobs.total, 0)
            connection = sqlite3.connect(database)
            try:
                self.assertIsNone(
                    connection.execute(
                        "SELECT name FROM sqlite_master WHERE name='file_index'"
                    ).fetchone()
                )
            finally:
                connection.close()

    def test_aggregate_counts_and_redacted_bounded_recent_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert(
                    (
                        self._file("ready", FileScanStatus.READY),
                        self._file("missing", FileScanStatus.MISSING),
                        self._file("error", FileScanStatus.ERROR),
                    )
                )
            with SQLiteTaskRepository(database) as repository:
                repository.create_task(self._task("task-failed", PersistentTaskStatus.FAILED))
                repository.create_task(self._task("task-running", PersistentTaskStatus.RUNNING))
                repository.create_job(self._job("job-failed", AutomationJobStatus.FAILED, 2))
                repository.create_job(self._job("job-pending", AutomationJobStatus.PENDING, 1))
                repository.create_confirmation(self._confirmation())
                repository.create_delivery(self._delivery())
                snapshot = DashboardService(
                    repository, resource_library_count=2, media_library_count=3
                ).snapshot(recent_limit=2)

            self.assertEqual((snapshot.resource_libraries, snapshot.media_libraries), (2, 3))
            self.assertEqual(snapshot.files.total, 3)
            self.assertEqual(snapshot.files.ready, 1)
            self.assertEqual(snapshot.files.missing, 1)
            self.assertEqual(snapshot.files.errors, 1)
            self.assertEqual(snapshot.tasks.running, 1)
            self.assertEqual(snapshot.tasks.failed, 1)
            self.assertEqual(snapshot.jobs.pending, 1)
            self.assertEqual(snapshot.jobs.failed, 1)
            self.assertEqual(snapshot.pending_confirmations, 1)
            self.assertEqual(snapshot.dead_letter_notifications, 1)
            self.assertEqual(len(snapshot.recent_failures), 2)
            serialized = repr(snapshot)
            self.assertNotIn("super-secret", serialized)
            self.assertNotIn("/private/media", serialized)
            self.assertNotIn("webhook-body", serialized)
            self.assertEqual(
                [item.identifier for item in snapshot.recent_failures],
                ["delivery-dead", "job-failed"],
            )

    def test_large_index_uses_aggregate_query_not_repository_enumeration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert(
                    tuple(self._file(str(value), FileScanStatus.READY) for value in range(600))
                )
            with (
                patch.object(
                    SQLiteFileIndexRepository,
                    "list_by_resource_library",
                    side_effect=AssertionError("dashboard must not enumerate FileIndex"),
                ),
                SQLiteTaskRepository(database) as repository,
            ):
                snapshot = DashboardService(
                    repository, resource_library_count=1, media_library_count=1
                ).snapshot()
            self.assertEqual(snapshot.files.total, 600)
            self.assertEqual(snapshot.files.ready, 600)

    def test_cli_and_api_are_read_only_bounded_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            configuration = json.loads(Path("config/strategy.example.json").read_text())
            configuration["persistence"] = {"databasePath": str(database)}
            config_path = Path(directory, "config.json")
            config_path.write_text(json.dumps(configuration), encoding="utf-8")
            output = io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("dashboard constructed Storage"),
            ):
                self.assertEqual(
                    final_main(
                        ["--config", str(config_path), "dashboard", "--recent-limit", "5"],
                        stdout=output,
                        stderr=io.StringIO(),
                    ),
                    0,
                )
            self.assertIn("DASHBOARD", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                viewer = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                auditor = ResolvedApiPrincipal(
                    "auditor",
                    "auditor-token",
                    frozenset({ApiPermission.READ, ApiPermission.READ_SECURITY_AUDIT}),
                )
                admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(viewer, auditor, admin),
                    dashboard_resource_library_count=2,
                    dashboard_media_library_count=3,
                )
                self.assertEqual(request(api, token=None)[0], 401)
                status, document = request(api, query="recentLimit=5")
                self.assertEqual(status, 200)
                self.assertEqual(document["resource_libraries"], 2)
                self.assertEqual(document["media_libraries"], 3)
                self.assertEqual(request(api, token="auditor-token")[0], 200)
                self.assertEqual(request(api, token="admin-token")[0], 200)
                self.assertEqual(request(api, query="recentLimit=0")[0], 400)
                self.assertEqual(request(api, query="secret=token-value")[0], 400)
                audit = repository.list_security_audit(limit=20)
                self.assertTrue(any(item.route == "/api/v1/dashboard" for item in audit))
                self.assertNotIn("secret", repr(audit))
                self.assertNotIn("token-value", repr(audit))

    @staticmethod
    def _file(identifier: str, status: FileScanStatus) -> FileIndexRecord:
        return FileIndexRecord(
            identifier,
            "storage",
            "library",
            f"movies/{identifier}.mkv",
            f"{identifier}.mkv",
            "mkv",
            1,
            NOW,
            NOW,
            NOW,
            NOW,
            status,
            FileChange.NEW,
            NOW,
            NOW,
        )

    @staticmethod
    def _task(identifier: str, status: PersistentTaskStatus) -> PersistentTask:
        return PersistentTask(
            identifier,
            "preview",
            status,
            False,
            NOW,
            NOW,
            error="super-secret /private/media" if status is PersistentTaskStatus.FAILED else None,
        )

    @staticmethod
    def _job(identifier: str, status: AutomationJobStatus, minutes: int) -> AutomationJob:
        occurred = NOW + timedelta(minutes=minutes)
        return AutomationJob(
            identifier,
            AutomationCommand.PREVIEW,
            status,
            occurred,
            occurred,
            error="super-secret /private/media" if status is AutomationJobStatus.FAILED else None,
        )

    @staticmethod
    def _confirmation() -> ConflictConfirmation:
        return ConflictConfirmation(
            "confirmation",
            "task-failed",
            "item",
            "plan",
            "destination_exists",
            "source",
            "private/movie.mkv",
            "target",
            "Movies/movie.mkv",
            "manual",
            ConfirmationStatus.PENDING,
            NOW,
            NOW,
        )

    @staticmethod
    def _delivery() -> NotificationDelivery:
        occurred = NOW + timedelta(minutes=3)
        return NotificationDelivery(
            "delivery-dead",
            "webhook",
            "event",
            NotificationEventType.JOB_FAILED,
            "webhook-body super-secret",
            NotificationDeliveryStatus.DEAD_LETTER,
            1,
            occurred,
            occurred,
            occurred,
            failure_category="super-secret /private/media",
        )
