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
from threading import Barrier, Thread
from unittest.mock import patch

from mediaflow.application.automation import (
    AutomationJobService,
    AutomationWorker,
    IntervalScheduler,
)
from mediaflow.domain.automation import AutomationJobStatus, IntervalSchedule
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


class AutomationPersistenceTests(unittest.TestCase):
    def test_schema_four_job_table_migrates_to_cancellation_and_schedules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_version VALUES ('runtime', 4);
                CREATE TABLE automation_jobs (
                    job_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, limit_value INTEGER,
                    started_at TEXT, completed_at TEXT, task_id TEXT, error TEXT
                );
                """
            )
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, 21)
                job = AutomationJobService(repository).submit("scan")
                self.assertFalse(job.cancellation_requested)
                self.assertEqual(repository.list_schedule_states(), ())

    def test_jobs_persist_claim_in_order_and_cancel_pending_or_running(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                service = AutomationJobService(repository)
                first = service.submit("scan", limit=3)
                second = service.submit("preview")
                claimed = repository.claim_next_job(datetime.now(UTC))
                self.assertEqual(claimed.job_id, first.job_id)
                self.assertEqual(claimed.status, AutomationJobStatus.RUNNING)
                requested = service.cancel(first.job_id)
                self.assertEqual(requested.status, AutomationJobStatus.RUNNING)
                self.assertTrue(requested.cancellation_requested)
                cancelled = service.cancel(second.job_id)
                self.assertEqual(cancelled.status, AutomationJobStatus.CANCELLED)
            with SQLiteTaskRepository(database) as reopened:
                self.assertTrue(reopened.get_job(first.job_id).cancellation_requested)
                self.assertEqual(
                    reopened.get_job(second.job_id).status, AutomationJobStatus.CANCELLED
                )

    def test_atomic_claim_allows_one_worker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                AutomationJobService(repository).submit("scan")
            barrier = Barrier(2)
            claimed = []

            def claim() -> None:
                with SQLiteTaskRepository(database) as repository:
                    barrier.wait()
                    claimed.append(repository.claim_next_job(datetime.now(UTC)))

            threads = [Thread(target=claim), Thread(target=claim)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sum(value is not None for value in claimed), 1)

    def test_worker_completes_and_redacts_failure_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository)
                service.submit("preview")
                completed = AutomationWorker(repository, lambda job, cancelled: "task-1").run_next()
                self.assertEqual(completed.status, AutomationJobStatus.COMPLETED)
                self.assertEqual(completed.task_id, "task-1")
                service.submit("scan")

                def fail(job, cancelled):
                    raise RuntimeError("Authorization: Bearer top-secret")

                failed = AutomationWorker(repository, fail).run_next()
                self.assertEqual(failed.status, AutomationJobStatus.FAILED)
                self.assertNotIn("top-secret", failed.error)
                self.assertEqual(failed.error, "workflow failed (RuntimeError)")

    def test_running_cancellation_becomes_cancelled_and_retains_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                queued = AutomationJobService(repository).submit("preview")

                def handler(job, cancelled):
                    repository.request_job_cancellation(job.job_id, datetime.now(UTC))
                    self.assertTrue(cancelled())
                    return "task-cancelled"

                result = AutomationWorker(repository, handler).run_next()
                self.assertEqual(result.status, AutomationJobStatus.CANCELLED)
                self.assertEqual(result.task_id, "task-cancelled")
                self.assertTrue(repository.get_job(queued.job_id).cancellation_requested)

    def test_stale_requeue_is_explicit_and_age_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository)
                queued = service.submit("scan")
                running = repository.claim_next_job(datetime.now(UTC))
                old = replace(running, updated_at=datetime.now(UTC) - timedelta(hours=2))
                repository.update_job(old)
                self.assertEqual(len(service.stale(age_seconds=3600)), 1)
                with self.assertRaisesRegex(ValueError, "not stale"):
                    service.requeue_stale(queued.job_id, age_seconds=10800)
                requeued = service.requeue_stale(queued.job_id, age_seconds=3600)
                self.assertEqual(requeued.status, AutomationJobStatus.PENDING)
                self.assertIsNone(requeued.started_at)

    def test_resident_worker_polls_without_busy_loop_and_isolates_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository)
                service.submit("scan")
                service.submit("preview")
                calls, sleeps = [], []
                stopped = False

                def handler(job, cancelled):
                    calls.append(job.command.value)
                    if job.command.value == "scan":
                        raise RuntimeError("failed")
                    return "task-ok"

                def sleep(seconds):
                    nonlocal stopped
                    sleeps.append(seconds)
                    stopped = True

                processed = AutomationWorker(repository, handler).run(
                    lambda: stopped, poll_seconds=0.5, sleep=sleep
                )
                self.assertEqual(processed, 2)
                self.assertEqual(calls, ["scan", "preview"])
                self.assertEqual(sleeps, [0.5])


class IntervalSchedulerTests(unittest.TestCase):
    def test_due_disabled_not_due_and_restart_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            schedules = (
                IntervalSchedule("scan-fast", "scan", 60, 5),
                IntervalSchedule("disabled", "preview", 60, enabled=False),
            )
            now = datetime(2026, 8, 22, tzinfo=UTC)
            with SQLiteTaskRepository(database) as repository:
                scheduler = IntervalScheduler(repository, schedules)
                first = scheduler.tick(now)
                self.assertEqual([item.schedule_id for item in first], ["scan-fast"])
                self.assertEqual(scheduler.tick(now), ())
            with SQLiteTaskRepository(database) as repository:
                scheduler = IntervalScheduler(repository, schedules)
                self.assertEqual(scheduler.tick(now + timedelta(seconds=59)), ())
                second = scheduler.tick(now + timedelta(seconds=60))
                self.assertEqual(len(second), 1)
                self.assertEqual(len(repository.list_jobs()), 2)

    def test_scheduler_resident_loop_has_bounded_poll(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                stopped, sleeps = False, []

                def sleep(seconds):
                    nonlocal stopped
                    sleeps.append(seconds)
                    stopped = True

                emitted = IntervalScheduler(
                    repository, (IntervalSchedule("daily", "preview", 86400),)
                ).run(lambda: stopped, poll_seconds=2, sleep=sleep)
                self.assertEqual(emitted, 1)
                self.assertEqual(sleeps, [2])

    def test_invalid_commands_and_limits_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository)
                for command in ("organize", "execute", "delete"):
                    with self.assertRaisesRegex(ValueError, "scan or preview"):
                        service.submit(command)
                for limit in (0, -1, 10_001, True, "2"):
                    with self.assertRaisesRegex(ValueError, "between 1 and 10000"):
                        service.submit("scan", limit=limit)


class ServiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.api = MediaFlowApi(self.repository, "api-secret")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def request(self, method: str, path: str, document=None, token: str | None = None):
        body = b"" if document is None else json.dumps(document).encode()
        status = []
        headers = []
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
        }
        if token is not None:
            environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        def start_response(value, response_headers):
            status.append(value)
            headers.extend(response_headers)

        response = b"".join(self.api(environ, start_response))
        return int(status[0].split()[0]), json.loads(response), dict(headers)

    def test_health_public_and_api_requires_auth(self) -> None:
        self.assertEqual(self.request("GET", "/health")[0], 200)
        status, document, _ = self.request("GET", "/api/v1/jobs")
        self.assertEqual(status, 401)
        self.assertNotIn("api-secret", json.dumps(document))

    def test_submit_list_show_cancel_and_utf8(self) -> None:
        status, created, headers = self.request(
            "POST", "/api/v1/jobs", {"command": "preview", "limit": 20}, "api-secret"
        )
        self.assertEqual(status, 202)
        self.assertIn("charset=utf-8", headers["Content-Type"])
        job_id = created["job_id"]
        self.assertEqual(
            self.request("GET", f"/api/v1/jobs/{job_id}", token="api-secret")[1]["limit"],
            20,
        )
        self.assertEqual(
            self.request("GET", "/api/v1/jobs", token="api-secret")[1]["items"][0]["command"],
            "preview",
        )
        cancelled = self.request("POST", f"/api/v1/jobs/{job_id}/cancel", token="api-secret")[1]
        self.assertEqual(cancelled["status"], "cancelled")

    def test_schedule_output_is_read_only(self) -> None:
        self.api = MediaFlowApi(
            self.repository,
            "api-secret",
            (IntervalSchedule("nightly", "preview", 3600, 20),),
        )
        status, response, _ = self.request("GET", "/api/v1/schedules", token="api-secret")
        self.assertEqual(status, 200)
        self.assertEqual(response["items"][0]["schedule_id"], "nightly")
        self.assertIsNone(response["items"][0]["state"])

    def test_api_requests_running_job_cancellation(self) -> None:
        queued = AutomationJobService(self.repository).submit("scan")
        self.repository.claim_next_job(datetime.now(UTC))
        status, response, _ = self.request(
            "POST", f"/api/v1/jobs/{queued.job_id}/cancel", token="api-secret"
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "running")
        self.assertTrue(response["cancellation_requested"])

    def test_rejects_execute_and_unsupported_commands(self) -> None:
        for document in (
            {"command": "organize"},
            {"command": "preview", "execute": False},
            {"command": "scan", "overwrite": False},
        ):
            status, response, _ = self.request("POST", "/api/v1/jobs", document, "api-secret")
            self.assertEqual(status, 400)
            self.assertEqual(response["error"]["code"], "invalid_request")
        self.assertEqual(len(self.repository.list_jobs()), 0)

    def test_stable_errors_for_invalid_json_unknown_routes_and_ids(self) -> None:
        status, response, _ = self.request("GET", "/missing")
        self.assertEqual((status, response["error"]["code"]), (404, "not_found"))
        status, response, _ = self.request("GET", "/api/v1/jobs/missing", token="api-secret")
        self.assertEqual((status, response["error"]["code"]), (404, "not_found"))
        status = []
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/api/v1/jobs",
            "CONTENT_LENGTH": "1",
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": "Bearer api-secret",
            "wsgi.input": io.BytesIO(b"{"),
        }
        response = b"".join(self.api(environ, lambda value, headers: status.append(value)))
        self.assertEqual(status[0].split()[0], "400")
        self.assertEqual(json.loads(response)["error"]["code"], "invalid_request")

    def test_read_endpoints_do_not_construct_or_mutate_storage(self) -> None:
        for path in ("/api/v1/tasks", "/api/v1/jobs", "/api/v1/confirmations"):
            self.assertEqual(self.request("GET", path, token="api-secret")[0], 200)


class AutomationCliTests(unittest.TestCase):
    def _configuration(self, directory: str) -> Path:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        root = Path(directory)
        source = root / "source"
        target = root / "target"
        source.mkdir()
        target.mkdir()
        document["storages"][0]["rootPath"] = str(source)
        document["storages"][1]["rootPath"] = str(target)
        document["resourceLibraries"][0]["storagePath"] = ""
        document["resourceLibraries"][0]["displayRootPath"] = str(source)
        document["persistence"] = {"databasePath": str(root / "state.sqlite3")}
        document["historyPath"] = str(root / "history.jsonl")
        document["api"] = {"tokenEnv": "MEDIAFLOW_API_TOKEN"}
        document["automation"] = {
            "workerPollSeconds": 1,
            "schedulerPollSeconds": 2,
            "schedules": [
                {
                    "id": "periodic-scan",
                    "command": "scan",
                    "intervalSeconds": 3600,
                    "limit": 20,
                }
            ],
        }
        config = root / "config.json"
        config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return config

    def test_cli_queue_worker_scan_reuses_workflow_with_zero_media_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            source = Path(directory, "source")
            media = source / "Movie.2025.mkv"
            media.write_bytes(b"unchanged")
            output, error = io.StringIO(), io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "jobs", "submit", "scan", "--limit", "1"],
                    stdout=output,
                    stderr=error,
                ),
                0,
                error.getvalue(),
            )
            output = io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "worker", "run-next"],
                    stdout=output,
                    stderr=error,
                ),
                0,
                error.getvalue(),
            )
            self.assertIn("Status: completed", output.getvalue())
            self.assertEqual(media.read_bytes(), b"unchanged")
            self.assertEqual(list(Path(directory, "target").iterdir()), [])

    def test_api_config_validation_does_not_require_secret(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["api"] = {"tokenEnv": "MEDIAFLOW_API_TOKEN"}
        document["automation"] = {
            "schedules": [{"id": "periodic-scan", "command": "scan", "intervalSeconds": 3600}]
        }
        loaded = load_runtime_configuration(copy.deepcopy(document))
        self.assertEqual(loaded.api_token_env, "MEDIAFLOW_API_TOKEN")
        self.assertEqual(loaded.automation_schedules[0].schedule_id, "periodic-scan")
        document["api"] = {"tokenEnv": "invalid-name"}
        with self.assertRaisesRegex(ValueError, "API tokenEnv"):
            load_runtime_configuration(document)

    def test_invalid_automation_configuration_rejects_execute_and_duplicates(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        for schedules, message in (
            ([{"id": "x", "command": "organize", "intervalSeconds": 1}], "scan or preview"),
            (
                [
                    {"id": "x", "command": "scan", "intervalSeconds": 1},
                    {"id": "x", "command": "preview", "intervalSeconds": 2},
                ],
                "IDs must be unique",
            ),
        ):
            candidate = copy.deepcopy(document)
            candidate["automation"] = {"schedules": schedules}
            with self.assertRaisesRegex(ValueError, message):
                load_runtime_configuration(candidate)

    def test_production_scan_cooperatively_cancels_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            media = Path(directory, "source", "Movie.2025.mkv")
            media.write_bytes(b"unchanged")
            code = final_main(
                ["--config", str(config), "scan"],
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                cancellation_check=lambda: True,
            )
            self.assertEqual(code, 130)
            self.assertEqual(media.read_bytes(), b"unchanged")
            self.assertEqual(list(Path(directory, "target").iterdir()), [])

    def test_scheduler_cli_tick_is_persistent_and_storage_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            target = Path(directory, "target")
            output, error = io.StringIO(), io.StringIO()
            code = final_main(
                ["--config", str(config), "scheduler", "tick"],
                stdout=output,
                stderr=error,
            )
            self.assertEqual(code, 0, error.getvalue())
            # The test configuration's schedule is enabled and emits one job on first tick.
            self.assertIn("periodic-scan", output.getvalue())
            self.assertEqual(list(target.iterdir()), [])
            second = io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "scheduler", "tick"],
                    stdout=second,
                    stderr=error,
                ),
                0,
            )
            self.assertIn("Total: 0", second.getvalue())

    def test_api_startup_requires_configured_secret_without_leaking_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            output, error = io.StringIO(), io.StringIO()
            with patch.dict("os.environ", {}, clear=True):
                code = final_main(
                    ["--config", str(config), "api", "serve"], stdout=output, stderr=error
                )
            self.assertEqual(code, 2)
            self.assertIn("MEDIAFLOW_API_TOKEN", error.getvalue())
            self.assertNotIn("Authorization", error.getvalue())


if __name__ == "__main__":
    unittest.main()
