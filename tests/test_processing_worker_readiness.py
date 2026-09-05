from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.automation import (
    ProcessingWorkerService,
    evaluate_pending_job_operational_condition,
)
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
    WorkerReadiness,
    WorkerStatus,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


def _example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def _request(
    api,
    method: str = "GET",
    path: str = "/api/v1/workers",
    query: str = "",
    token: str = "viewer-token",
):
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
        "wsgi.input": io.BytesIO(),
    }
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


def _job(
    job_id: str,
    updated_at: datetime,
    status: AutomationJobStatus = AutomationJobStatus.PENDING,
    execute_authorized: bool = False,
) -> AutomationJob:
    return AutomationJob(
        job_id=job_id,
        command=AutomationCommand.ORGANIZE if execute_authorized else AutomationCommand.SCAN,
        status=status,
        created_at=updated_at - timedelta(minutes=1),
        updated_at=updated_at,
        started_at=updated_at - timedelta(minutes=1),
        execute_authorized=execute_authorized,
    )


class TestProcessingWorkerReadiness(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.service = ProcessingWorkerService(self.repository)
        self.api = MediaFlowApi(self.repository, "api-secret")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    # AC1: Durable registration
    def test_register_worker_is_durable_and_idempotent(self) -> None:
        worker_id = "worker-1"
        registered = self.service.register_worker(
            worker_id=worker_id,
            label="resident-worker",
            heartbeat_interval_seconds=2.0,
            supported_commands=("scan", "process"),
            configuration_snapshot_id="cfg-1",
            configuration_snapshot_digest="digest-1",
            runtime_schema_version=33,
            now=datetime.now(UTC),
        )
        self.assertEqual(registered.worker_id, worker_id)
        self.assertEqual(registered.label, "resident-worker")
        self.assertEqual(registered.heartbeat_interval_seconds, 2.0)
        self.assertEqual(registered.supported_commands, ("scan", "process"))
        self.assertEqual(registered.status, WorkerStatus.LIVE)
        self.assertEqual(registered.runtime_schema_version, 33)
        self.assertEqual(registered.configuration_snapshot_id, "cfg-1")
        self.assertEqual(registered.configuration_snapshot_digest, "digest-1")
        self.assertEqual(registered.registered_at, registered.last_heartbeat_at)

        # Idempotent re-registration: same worker_id, same record
        reregistered = self.service.register_worker(
            worker_id=worker_id,
            label="resident-worker",
            heartbeat_interval_seconds=2.0,
            supported_commands=("scan", "process"),
            configuration_snapshot_id="cfg-1",
            configuration_snapshot_digest="digest-1",
            runtime_schema_version=33,
            now=datetime.now(UTC),
        )
        # registered_at is preserved on re-registration; last_heartbeat_at is updated
        self.assertEqual(registered.registered_at, reregistered.registered_at)
        self.assertEqual(registered.worker_id, reregistered.worker_id)
        self.assertEqual(registered.label, reregistered.label)
        self.assertGreaterEqual(reregistered.last_heartbeat_at, registered.last_heartbeat_at)
        self.assertEqual(len(self.service.list_workers()), 1)

    def test_register_worker_rejects_path_or_url_label(self) -> None:
        for bad in ("/etc/passwd", "C:\\\\secrets", "https://x/token"):
            with self.subTest(label=bad):
                with self.assertRaises(ValueError):
                    self.service.register_worker(
                        worker_id="w",
                        label=bad,
                        heartbeat_interval_seconds=1.0,
                        supported_commands=("scan",),
                        now=datetime.now(UTC),
                    )

    def test_cli_worker_registration_binds_current_active_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = _example_document()
            document["persistence"]["databasePath"] = str(runtime)
            config = root / "bootstrap.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteConfigurationRepository(runtime) as configuration_repository:
                configuration_service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(runtime),
                )
                draft = configuration_service.import_draft(document, actor="worker-test")
                validated = configuration_service.validate(draft.revision_id, actor="worker-test")
                active = configuration_service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="worker-test",
                )

            output, errors = io.StringIO(), io.StringIO()
            status = final_main(
                ["--config", str(config), "worker", "run-next"],
                stdout=output,
                stderr=errors,
            )
            self.assertEqual(status, 0, errors.getvalue())
            with SQLiteTaskRepository(runtime) as repository:
                workers = repository.list_workers()
                self.assertEqual(len(workers), 1)
                self.assertEqual(workers[0].configuration_snapshot_id, active.revision_id)
                self.assertEqual(workers[0].configuration_snapshot_digest, active.digest)
                self.assertEqual(workers[0].runtime_schema_version, 33)

    # AC2: Liveness and readiness
    def test_heartbeat_progression_and_stale_evaluation(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        self.service.register_worker(
            worker_id="worker-2",
            label="heartbeat-worker",
            heartbeat_interval_seconds=5.0,
            supported_commands=("scan",),
            now=start,
        )
        # Heartbeat at t+1
        self.service.heartbeat_worker("worker-2", now=start + timedelta(seconds=1))
        # At t+10 (just under 3x threshold of 15s), worker is still live
        workers = self.service.list_workers(now=start + timedelta(seconds=10))
        self.assertEqual(workers[0].status, WorkerStatus.LIVE)
        # At t+20 (beyond 3x threshold), worker becomes stale
        workers = self.service.list_workers(now=start + timedelta(seconds=20))
        self.assertEqual(workers[0].status, WorkerStatus.STALE)
        # Clean stop
        stopped = self.service.stop_worker("worker-2", now=start + timedelta(seconds=21))
        self.assertEqual(stopped.status, WorkerStatus.STOPPED)
        # Stopped workers stay stopped regardless of clock progression
        workers = self.service.list_workers(now=start + timedelta(hours=1))
        self.assertEqual(workers[0].status, WorkerStatus.STOPPED)

    def test_readiness_is_fail_closed_for_snapshot_mismatch(self) -> None:
        self.service.register_worker(
            worker_id="worker-2b",
            label="snapshot-worker",
            heartbeat_interval_seconds=1.0,
            supported_commands=("scan",),
            configuration_snapshot_id="stale-cfg",
            configuration_snapshot_digest="stale-digest",
            now=datetime.now(UTC),
        )
        readiness = self.service.evaluate_readiness(
            now=datetime.now(UTC),
            active_snapshot_id="active-cfg",
            active_snapshot_digest="active-digest",
        )
        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["condition"], WorkerReadiness.SNAPSHOT_MISMATCH.value)
        self.assertEqual(readiness["sideEffects"], "none")
        self.assertTrue(readiness["retrySafe"])

    # AC3: Separate from API health
    def test_health_payload_unchanged_when_no_live_worker(self) -> None:
        # No live worker; /health must still report alive
        status, document = _request(self.api, "GET", "/health", token="")
        self.assertEqual(status, 200)
        self.assertEqual(document.get("status"), "ok")
        self.assertTrue(document.get("processAlive"))

    def test_management_readiness_payload_unchanged_when_no_live_worker(self) -> None:
        # No live worker; /api/v1/management/readiness must still report ready
        status, document = _request(
            self.api, "GET", "/api/v1/management/readiness", token="api-secret"
        )
        self.assertEqual(status, 200)
        # Management readiness is configuration-readiness, not worker-readiness.
        # With no live worker, the management readiness payload must still not include
        # a worker-readiness field.
        self.assertNotIn("workerReadiness", document)
        self.assertNotIn("workers", document)

    # AC4: Queued work is explained
    def test_pending_job_operational_condition_when_no_worker(self) -> None:
        # No worker registered
        readiness = self.service.evaluate_readiness(now=datetime.now(UTC))
        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["condition"], WorkerReadiness.NO_WORKER.value)
        # Operational condition for a pending job waiting beyond the threshold
        condition = evaluate_pending_job_operational_condition(readiness)
        self.assertIsNotNone(condition)
        self.assertEqual(condition["condition"], WorkerReadiness.NO_WORKER.value)
        self.assertEqual(condition["stage"], "pending")
        self.assertEqual(condition["sideEffects"], "none")
        self.assertTrue(condition["retrySafe"])
        self.assertEqual(
            condition["nextAction"], "start a resident worker with the active configuration"
        )

    def test_pending_job_no_operational_condition_with_live_worker(self) -> None:
        # Live usable worker -> no operational condition projected for pending job
        self.service.register_worker(
            worker_id="worker-3",
            label="live-worker",
            heartbeat_interval_seconds=5.0,
            supported_commands=("scan",),
            now=datetime.now(UTC),
        )
        readiness = self.service.evaluate_readiness(now=datetime.now(UTC))
        self.assertTrue(readiness["ready"])
        condition = evaluate_pending_job_operational_condition(readiness)
        self.assertIsNone(condition)

    # AC7: API never supervises a Worker
    def test_api_exposes_no_worker_mutation_methods(self) -> None:
        for forbidden in (
            "register_worker",
            "heartbeat_worker",
            "start_worker",
            "stop_worker",
            "supervise_worker",
        ):
            with self.subTest(method=forbidden):
                self.assertFalse(
                    hasattr(self.api, forbidden),
                    f"API must not expose {forbidden}",
                )

    def test_api_request_path_does_not_start_subprocess_or_thread(self) -> None:
        # Issue a read-only API request; capture subprocess and thread invocations.
        import subprocess
        import threading

        original_popen = subprocess.Popen
        original_thread_init = threading.Thread.__init__
        popen_calls: list[tuple] = []
        thread_calls: list[tuple] = []

        def tracking_popen(*args, **kwargs):
            popen_calls.append((args, kwargs))
            return original_popen(*args, **kwargs)

        def tracking_thread_init(self, *args, **kwargs):
            thread_calls.append((args, kwargs))
            return original_thread_init(self, *args, **kwargs)

        with (
            patch.object(subprocess, "Popen", tracking_popen),
            patch.object(threading.Thread, "__init__", tracking_thread_init),
        ):
            status, _ = _request(self.api, "GET", "/api/v1/workers", token="api-secret")

        self.assertEqual(status, 200)
        self.assertEqual(popen_calls, [], "API request must not spawn subprocesses")
        self.assertEqual(thread_calls, [], "API request must not spawn threads")

    def test_api_request_for_workers_is_read_only(self) -> None:
        # POST/PUT/DELETE on /api/v1/workers must be rejected with 405
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            with self.subTest(method=method):
                status, _ = _request(self.api, method, "/api/v1/workers", token="api-secret")
                self.assertEqual(status, 405)


if __name__ == "__main__":
    unittest.main()
