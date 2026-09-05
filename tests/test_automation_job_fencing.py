from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.automation import AutomationJobService, AutomationWorker
from mediaflow.domain.automation import AutomationClaimLost, AutomationJobStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import render_job
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


class RecordingNotifications:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


class AutomationJobFencingTests(unittest.TestCase):
    def test_schema_thirteen_migrates_claim_token_and_fresh_schema_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory, "legacy.sqlite3")
            connection = sqlite3.connect(legacy)
            connection.executescript(
                """
                CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_version VALUES ('runtime', 13);
                CREATE TABLE automation_jobs (
                    job_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, limit_value INTEGER,
                    started_at TEXT, completed_at TEXT, task_id TEXT, error TEXT,
                    cancellation_requested INTEGER NOT NULL DEFAULT 0, schedule_id TEXT,
                    execute_authorized INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            connection.close()
            with SQLiteTaskRepository(legacy) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                columns = {
                    row["name"]
                    for row in repository._connection.execute(
                        "PRAGMA table_info(automation_jobs)"
                    ).fetchall()
                }
                self.assertIn("claim_token", columns)
            with SQLiteTaskRepository(Path(directory, "fresh.sqlite3")) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_claim_heartbeat_cancellation_and_terminal_completion_are_fenced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                queued = AutomationJobService(repository).submit("preview")
                claimed = repository.claim_next_job(NOW)
                self.assertEqual(claimed.job_id, queued.job_id)
                self.assertTrue(claimed.claim_token)
                heartbeat_at = NOW + timedelta(seconds=30)
                self.assertFalse(
                    repository.heartbeat_job(claimed.job_id, claimed.claim_token, heartbeat_at)
                )
                self.assertEqual(repository.get_job(claimed.job_id).updated_at, heartbeat_at)
                with self.assertRaises(AutomationClaimLost):
                    repository.heartbeat_job(claimed.job_id, "wrong-token", NOW)
                repository.request_job_cancellation(claimed.job_id, NOW + timedelta(seconds=31))
                self.assertTrue(
                    repository.heartbeat_job(
                        claimed.job_id, claimed.claim_token, NOW + timedelta(seconds=32)
                    )
                )
                terminal = replace(
                    claimed,
                    status=AutomationJobStatus.CANCELLED,
                    cancellation_requested=True,
                    updated_at=NOW + timedelta(seconds=33),
                    completed_at=NOW + timedelta(seconds=33),
                )
                self.assertFalse(
                    repository.complete_claimed_job(replace(terminal, claim_token="bad"))
                )
                self.assertTrue(repository.complete_claimed_job(terminal))
                persisted = repository.get_job(claimed.job_id)
                self.assertEqual(persisted.status, AutomationJobStatus.CANCELLED)
                self.assertIsNone(persisted.claim_token)

    def test_requeue_clears_token_new_claim_is_unique_and_old_worker_cannot_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository)
                service.submit("scan")
                first = repository.claim_next_job(NOW - timedelta(hours=2))
                first_token = first.claim_token
                requeued = service.requeue_stale(first.job_id, age_seconds=3600)
                self.assertEqual(requeued.status, AutomationJobStatus.PENDING)
                self.assertIsNone(requeued.claim_token)
                second = repository.claim_next_job(NOW)
                self.assertNotEqual(second.claim_token, first_token)
                stale_completion = replace(
                    first,
                    status=AutomationJobStatus.COMPLETED,
                    updated_at=NOW,
                    completed_at=NOW,
                )
                self.assertFalse(repository.complete_claimed_job(stale_completion))
                persisted = repository.get_job(first.job_id)
                self.assertEqual(persisted.status, AutomationJobStatus.RUNNING)
                self.assertEqual(persisted.claim_token, second.claim_token)

    def test_worker_losing_claim_does_not_publish_or_overwrite_new_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                first = AutomationJobService(repository).submit("preview")
                notifications = RecordingNotifications()

                def handler(job, cancelled):
                    aged = replace(job, updated_at=NOW - timedelta(hours=2))
                    repository.update_job(aged)
                    service.requeue_stale(job.job_id, age_seconds=3600)
                    repository.claim_next_job(NOW)
                    return "stale-task"

                service = AutomationJobService(repository)
                with self.assertRaises(AutomationClaimLost):
                    AutomationWorker(repository, handler, notifications).run_next()

                self.assertEqual(notifications.events, [])
                persisted = repository.get_job(first.job_id)
                self.assertEqual(persisted.status, AutomationJobStatus.RUNNING)
                self.assertNotEqual(persisted.claim_token, first.claim_token)

    def test_worker_a_aging_requeue_and_worker_b_completion_preserves_b_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository)
                service.submit("preview")
                repository.register_worker(
                    worker_id="worker-a",
                    label="worker-a",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan", "preview"),
                    configuration_snapshot_id=None,
                    configuration_snapshot_digest=None,
                    runtime_schema_version=33,
                    now=NOW - timedelta(hours=3),
                )
                # Worker-a heartbeats immediately before claiming so the claim-time
                # lease check admits it; it then goes quiet so its Job can age.
                repository.heartbeat_worker("worker-a", NOW - timedelta(hours=2))
                repository.register_worker(
                    worker_id="worker-b",
                    label="worker-b",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan", "preview"),
                    configuration_snapshot_id=None,
                    configuration_snapshot_digest=None,
                    runtime_schema_version=33,
                    now=NOW,
                )
                first_claimed = repository.claim_next_job(
                    NOW - timedelta(hours=2), worker_id="worker-a"
                )
                first_token = first_claimed.claim_token
                requeued = service.requeue_stale(first_claimed.job_id, age_seconds=3600)
                self.assertEqual(requeued.status, AutomationJobStatus.PENDING)
                self.assertIsNone(requeued.worker_id)
                self.assertIsNone(requeued.claim_token)
                second_claimed = repository.claim_next_job(NOW, worker_id="worker-b")
                self.assertNotEqual(second_claimed.claim_token, first_token)
                self.assertEqual(second_claimed.worker_id, "worker-b")
                finished = replace(
                    second_claimed,
                    status=AutomationJobStatus.COMPLETED,
                    updated_at=NOW,
                    completed_at=NOW,
                    task_id="task-b",
                )
                self.assertTrue(repository.complete_claimed_job(finished))
                stale_attempt = replace(
                    first_claimed,
                    status=AutomationJobStatus.COMPLETED,
                    updated_at=NOW,
                    completed_at=NOW,
                    task_id="task-a",
                )
                self.assertFalse(repository.complete_claimed_job(stale_attempt))
                persisted = repository.get_job(first_claimed.job_id)
                self.assertEqual(persisted.status, AutomationJobStatus.COMPLETED)
                self.assertEqual(persisted.task_id, "task-b")
                self.assertEqual(persisted.worker_id, "worker-b")
                self.assertIsNone(persisted.claim_token)

    def test_mismatched_owner_cannot_complete_even_with_matching_claim_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                AutomationJobService(repository).submit("preview")
                repository.register_worker(
                    worker_id="worker-a",
                    label="worker-a",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan", "preview"),
                    configuration_snapshot_id=None,
                    configuration_snapshot_digest=None,
                    runtime_schema_version=33,
                    now=NOW,
                )
                claimed = repository.claim_next_job(NOW, worker_id="worker-a")
                assert claimed is not None and claimed.worker_id == "worker-a"
                # Same claim token but a different owner must not commit.
                tampered = replace(
                    claimed,
                    worker_id="worker-b",
                    status=AutomationJobStatus.COMPLETED,
                    updated_at=NOW + timedelta(seconds=5),
                    completed_at=NOW + timedelta(seconds=5),
                )
                self.assertFalse(repository.complete_claimed_job(tampered))
                persisted = repository.get_job(claimed.job_id)
                self.assertEqual(persisted.status, AutomationJobStatus.RUNNING)
                self.assertEqual(persisted.worker_id, "worker-a")
                self.assertEqual(persisted.claim_token, claimed.claim_token)

    def test_incompatible_or_stale_worker_cannot_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                AutomationJobService(repository).submit("preview")
                repository.register_worker(
                    worker_id="worker-stale",
                    label="worker-stale",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan",),
                    configuration_snapshot_id=None,
                    configuration_snapshot_digest=None,
                    runtime_schema_version=33,
                    now=NOW - timedelta(hours=2),
                )
                with self.assertRaises(AutomationClaimLost):
                    repository.claim_next_job(NOW, worker_id="worker-stale")
                repository.register_worker(
                    worker_id="worker-schema",
                    label="worker-schema",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan",),
                    configuration_snapshot_id=None,
                    configuration_snapshot_digest=None,
                    runtime_schema_version=99,
                    now=NOW,
                )
                with self.assertRaises(AutomationClaimLost):
                    repository.claim_next_job(NOW, worker_id="worker-schema")
                # A live worker bound to a different snapshot cannot claim a pinned Job.
                AutomationJobService(
                    repository,
                    configuration_snapshot_id="cfg-a",
                    configuration_snapshot_digest="digest-a",
                ).submit("preview")
                repository.register_worker(
                    worker_id="worker-other-snapshot",
                    label="worker-other-snapshot",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan",),
                    configuration_snapshot_id="cfg-b",
                    configuration_snapshot_digest="digest-b",
                    runtime_schema_version=33,
                    now=NOW,
                )
                self.assertIsNone(repository.claim_next_job(NOW, worker_id="worker-other-snapshot"))
                # The matching snapshot worker is admitted.
                repository.register_worker(
                    worker_id="worker-matching",
                    label="worker-matching",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan",),
                    configuration_snapshot_id="cfg-a",
                    configuration_snapshot_digest="digest-a",
                    runtime_schema_version=33,
                    now=NOW,
                )
                claimed = repository.claim_next_job(NOW, worker_id="worker-matching")
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed.worker_id, "worker-matching")

    def test_success_clears_token_and_cli_notification_output_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                AutomationJobService(repository).submit("preview")
                notifications = RecordingNotifications()
                observed_tokens = []

                def handler(job, cancelled):
                    observed_tokens.append(job.claim_token)
                    self.assertFalse(cancelled())
                    return "task-safe"

                result = AutomationWorker(repository, handler, notifications).run_next()
                self.assertEqual(result.status, AutomationJobStatus.COMPLETED)
                self.assertIsNone(result.claim_token)
                self.assertEqual(len(notifications.events), 1)
                token = observed_tokens[0]
                self.assertTrue(token)
                self.assertNotIn(token, render_job(result))
                self.assertNotIn(token, json.dumps(notifications.events[0].data))
                self.assertNotIn("claim", json.dumps(notifications.events[0].data).lower())

    def test_heartbeat_refresh_controls_stale_age_and_token_is_api_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                AutomationJobService(repository).submit("scan")
                claimed = repository.claim_next_job(NOW - timedelta(hours=2))
                self.assertEqual(
                    len(repository.list_stale_running_jobs(NOW - timedelta(hours=1))), 1
                )
                repository.heartbeat_job(claimed.job_id, claimed.claim_token, NOW)
                self.assertEqual(repository.list_stale_running_jobs(NOW - timedelta(hours=1)), ())
                principal = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                api = MediaFlowApi(repository, None, principals=(principal,))
                status, body = self._request(api, f"/api/v1/jobs/{claimed.job_id}")
                self.assertEqual(status, 200)
                rendered = json.dumps(body)
                self.assertNotIn("claim_token", rendered)
                self.assertNotIn(claimed.claim_token, rendered)

    @staticmethod
    def _request(api, path: str):
        statuses = []
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "CONTENT_LENGTH": "0",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer viewer-token",
            "wsgi.input": io.BytesIO(),
        }
        body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(body)


if __name__ == "__main__":
    unittest.main()
