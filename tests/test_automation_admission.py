from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

from mediaflow.application.automation import (
    AutomationJobService,
    AutomationQueueFull,
    IntervalScheduler,
)
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.domain.automation import AutomationJobStatus, IntervalSchedule
from mediaflow.domain.execution_authorization import ExecutionAuthorizationStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.configuration_snapshot import build_configuration_snapshot
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi


def example_document():
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def api_request(api, document):
    body = json.dumps(document).encode()
    statuses = []
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/v1/jobs",
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": "Bearer operator-token",
        "wsgi.input": io.BytesIO(body),
    }
    response = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(response)


class AutomationAdmissionTests(unittest.TestCase):
    def test_configuration_default_custom_boundaries_and_snapshot(self) -> None:
        source = example_document()
        source["automation"].pop("maximumActiveJobs")
        self.assertEqual(
            load_runtime_configuration(copy.deepcopy(source)).automation_maximum_active_jobs, 100
        )
        for value in (1, 10_000):
            candidate = copy.deepcopy(source)
            candidate["automation"]["maximumActiveJobs"] = value
            runtime = load_runtime_configuration(candidate)
            self.assertEqual(runtime.automation_maximum_active_jobs, value)
            snapshot = build_configuration_snapshot(runtime).as_document()
            self.assertEqual(snapshot["system"]["maximum_active_jobs"], value)
            rendered = json.dumps(snapshot)
            self.assertNotIn("automation_jobs", rendered)
            self.assertNotIn("pending_jobs", rendered)
        for value in (True, "2", 0, -1, 10_001):
            candidate = copy.deepcopy(source)
            candidate["automation"]["maximumActiveJobs"] = value
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "between 1 and 10000"),
            ):
                load_runtime_configuration(candidate)
        unknown = copy.deepcopy(source)
        unknown["automation"]["forceAdmission"] = True
        with self.assertRaisesRegex(ValueError, "unknown automation field"):
            load_runtime_configuration(unknown)

    def test_active_statuses_consume_and_terminal_statuses_release_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository, maximum_active_jobs=1)
                pending = service.submit("scan")
                with self.assertRaises(AutomationQueueFull):
                    service.submit("preview")
                repository.claim_next_job(datetime.now(UTC))
                with self.assertRaises(AutomationQueueFull):
                    service.submit("preview")
                for status in (
                    AutomationJobStatus.COMPLETED,
                    AutomationJobStatus.FAILED,
                    AutomationJobStatus.CANCELLED,
                ):
                    running = repository.get_job(pending.job_id)
                    repository.update_job(
                        type(running)(
                            **{
                                **running.__dict__,
                                "status": status,
                                "updated_at": datetime.now(UTC),
                            }
                        )
                    )
                    replacement = service.submit("preview")
                    self.assertEqual(replacement.status, AutomationJobStatus.PENDING)
                    pending = replacement
                    repository.claim_next_job(datetime.now(UTC))

    def test_concurrent_connections_never_exceed_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database):
                pass
            barrier = Barrier(2)

            def submit():
                with SQLiteTaskRepository(database) as repository:
                    barrier.wait()
                    try:
                        return (
                            AutomationJobService(repository, maximum_active_jobs=1)
                            .submit("scan")
                            .job_id
                        )
                    except AutomationQueueFull:
                        return None

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: submit(), range(2)))
            self.assertEqual(sum(value is not None for value in results), 1)
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(len(repository.list_jobs()), 1)

    def test_scheduler_full_retries_without_state_or_audit_advance(self) -> None:
        now = datetime(2026, 8, 22, 12, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                filler = AutomationJobService(repository, maximum_active_jobs=1).submit("scan")
                scheduler = IntervalScheduler(
                    repository,
                    (IntervalSchedule("hourly", "preview", 3600),),
                    maximum_active_jobs=1,
                )
                self.assertEqual(scheduler.tick(now), ())
                before = repository.get_schedule_state("hourly")
                self.assertIsNone(before.last_job_id)
                self.assertEqual(repository.list_schedule_audit("hourly"), ())
                AutomationJobService(repository).cancel(filler.job_id)
                emitted = scheduler.tick(now)
                self.assertEqual(len(emitted), 1)
                self.assertEqual(len(repository.list_schedule_audit("hourly")), 1)

    def test_remote_ticket_survives_full_queue_then_consumes_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                filler = AutomationJobService(repository, maximum_active_jobs=1).submit("scan")
                authorizations = ExecutionAuthorizationService(
                    repository, maximum_active_jobs=1, token_factory=lambda: "one-time-token"
                )
                issued = authorizations.issue(ttl_seconds=60, max_items=1)
                with self.assertRaises(AutomationQueueFull):
                    authorizations.submit_organize("one-time-token", limit=1)
                unchanged = authorizations.get(issued.authorization.authorization_id)
                self.assertEqual(unchanged.status, ExecutionAuthorizationStatus.ACTIVE)
                self.assertIsNone(unchanged.consumed_job_id)
                AutomationJobService(repository).cancel(filler.job_id)
                job = authorizations.submit_organize("one-time-token", limit=1)
                self.assertTrue(job.execute_authorized)
                consumed = authorizations.get(issued.authorization.authorization_id)
                self.assertEqual(consumed.status, ExecutionAuthorizationStatus.CONSUMED)
                with self.assertRaisesRegex(ValueError, "consumed"):
                    authorizations.submit_organize("one-time-token", limit=1)

    def test_api_returns_queue_full_without_optimistic_ui_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                principal = ResolvedApiPrincipal(
                    "operator",
                    "operator-token",
                    frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
                )
                api = MediaFlowApi(repository, None, principals=(principal,), maximum_active_jobs=1)
                self.assertEqual(api_request(api, {"command": "scan"})[0], 202)
                status, document = api_request(api, {"command": "preview"})
                self.assertEqual(status, 409)
                self.assertEqual(document["error"]["code"], "queue_full")
                self.assertEqual(len(repository.list_jobs()), 1)
        script = APP_JS.decode()
        self.assertIn("catch (error) { message(error.message, true); }", script)
        for forbidden in ("Force queue", "Purge queue", "Bypass limit"):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
