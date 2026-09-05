import copy
import dataclasses
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.configuration_snapshot import build_configuration_snapshot
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime.now(UTC)


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def request(api, method: str = "GET", query: str = "", token: str = "viewer-token"):
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": "/api/v1/jobs/stale",
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
        "wsgi.input": io.BytesIO(),
    }
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


class StaleJobVisibilityTests(unittest.TestCase):
    def test_configuration_default_custom_validation_and_snapshot(self) -> None:
        source = example_document()
        source["automation"].pop("staleJobAgeSeconds")
        self.assertEqual(
            load_runtime_configuration(copy.deepcopy(source)).automation_stale_job_age_seconds, 3600
        )
        for value in (60, 7200, 604_800):
            candidate = copy.deepcopy(source)
            candidate["automation"]["staleJobAgeSeconds"] = value
            runtime = load_runtime_configuration(candidate)
            self.assertEqual(runtime.automation_stale_job_age_seconds, value)
            self.assertEqual(
                build_configuration_snapshot(runtime).as_document()["system"][
                    "stale_job_age_seconds"
                ],
                value,
            )
        for value in (True, "3600", 59, 604_801):
            candidate = copy.deepcopy(source)
            candidate["automation"]["staleJobAgeSeconds"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "between 60"):
                load_runtime_configuration(candidate)

    def test_repository_query_is_bounded_ordered_and_filters_status_and_age(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                repository.create_job(self._job("old-b", NOW - timedelta(hours=3)))
                repository.create_job(self._job("old-a", NOW - timedelta(hours=3)))
                repository.create_job(self._job("new", NOW - timedelta(minutes=5)))
                repository.create_job(
                    self._job("failed", NOW - timedelta(hours=4), AutomationJobStatus.FAILED)
                )
                values = repository.list_stale_running_jobs(NOW - timedelta(hours=1), limit=1)
                self.assertEqual([item.job_id for item in values], ["old-a"])
                for limit in (True, 0, 101):
                    with self.subTest(limit=limit), self.assertRaises(ValueError):
                        repository.list_stale_running_jobs(NOW, limit=limit)

    def test_api_is_bounded_allowlisted_redacted_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                repository.create_job(
                    self._job(
                        "execute-job",
                        NOW - timedelta(hours=2),
                        error="token=secret /private/source.mkv",
                        execute_authorized=True,
                    )
                )
                api = self._api(repository)
                status, document = request(api, query="limit=1")
                self.assertEqual(status, 200)
                self.assertEqual(document["threshold_seconds"], 3600)
                item = document["items"][0]
                self.assertEqual(item["job_id"], "execute-job")
                self.assertTrue(item["execute_authorized"])
                self.assertEqual(
                    set(item),
                    {
                        "job_id",
                        "command",
                        "status",
                        "created_at",
                        "updated_at",
                        "started_at",
                        "task_id",
                        "cancellation_requested",
                        "schedule_id",
                        "execute_authorized",
                        "operationalCondition",
                    },
                )
                self.assertEqual(item["operationalCondition"]["condition"], "no_worker")
                self.assertTrue(item["operationalCondition"]["retrySafe"])
                self.assertTrue(item["operationalCondition"]["nextAction"])
                self.assertNotIn("secret", json.dumps(document))
                self.assertEqual(repository.list_security_audit()[0].route, "/api/v1/jobs/stale")

    def test_api_auth_method_and_strict_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = self._api(repository)
                self.assertEqual(request(api, token="")[0], 401)
                self.assertEqual(request(api, method="POST")[0], 405)
                for query in ("limit=0", "limit=101", "limit=x", "limit=1&limit=2", "age=1"):
                    with self.subTest(query=query):
                        self.assertEqual(request(api, query=query)[0], 400)

    def test_operator_ui_is_explicit_read_only_and_warns_about_authority(self) -> None:
        script = APP_JS.decode()
        self.assertIn("Show stale running jobs", script)
        self.assertIn("/api/v1/jobs/stale?limit=100", script)
        self.assertIn("Age is an observation, not proof that a worker died", script)
        self.assertIn("MUTATION_AUTHORIZED \\u2014 MANUAL RECOVERY ONLY", script)
        self.assertIn("system.stale_job_age_seconds", script)
        stale_section = script[script.index("async function renderStaleJobs") :]
        stale_section = stale_section[: stale_section.index("function showDryRunJobForm")]
        self.assertIn("Owner", stale_section)
        self.assertIn("Next action", stale_section)
        self.assertIn("operationalCondition", stale_section)
        for forbidden in ("requeue", "cancel", "retry", "execute"):
            self.assertNotIn(f"actionButton('{forbidden}", stale_section.lower())

    def test_running_job_projects_worker_ownership_and_last_alive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                # Register worker
                repository.register_worker(
                    worker_id="w-123",
                    label="worker-node-1",
                    heartbeat_interval_seconds=3600.0,
                    supported_commands=("scan",),
                    configuration_snapshot_id="cfg-1",
                    configuration_snapshot_digest="sha256:test",
                    runtime_schema_version=33,
                    now=NOW,
                )
                # Create running job owned by w-123
                job = dataclasses.replace(
                    self._job("running-job", NOW, AutomationJobStatus.RUNNING),
                    worker_id="w-123",
                )
                repository.create_job(job)
                # Query via API
                api = self._api(repository)
                statuses: list[str] = []
                environ = {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/api/v1/jobs/running-job",
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer viewer-token",
                    "wsgi.input": io.BytesIO(),
                }
                body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
                self.assertEqual(int(statuses[0].split()[0]), 200)
                doc = json.loads(body)
                self.assertEqual(doc["workerId"], "w-123")
                self.assertEqual(doc["ownerLastHeartbeatAt"], NOW.isoformat())
                self.assertEqual(doc["ownerStatus"], "live")
                self.assertNotIn("operationalCondition", doc)
                # No secrets or claim token exposed
                self.assertNotIn("claim_token", doc)
                self.assertNotIn("claimToken", doc)

    def test_stale_job_projects_worker_owner_condition_and_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                repository.register_worker(
                    worker_id="stale-owner",
                    label="stale-owner",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan",),
                    configuration_snapshot_id="cfg-1",
                    configuration_snapshot_digest="sha256:test",
                    runtime_schema_version=33,
                    now=NOW - timedelta(hours=3),
                )
                job = dataclasses.replace(
                    self._job("stale-owner-job", NOW - timedelta(hours=2)),
                    worker_id="stale-owner",
                )
                repository.create_job(job)
                api = self._api(repository)
                status, document = request(api, query="limit=10")
                self.assertEqual(status, 200)
                item = next(
                    value for value in document["items"] if value["job_id"] == "stale-owner-job"
                )
                self.assertEqual(item["workerId"], "stale-owner")
                self.assertEqual(item["ownerStatus"], "stale")
                condition = item["operationalCondition"]
                self.assertEqual(condition["condition"], "stale_worker")
                self.assertEqual(condition["stage"], "running")
                self.assertEqual(condition["sideEffects"], "none")
                self.assertTrue(condition["retrySafe"])
                self.assertTrue(condition["nextAction"])

    def test_pending_job_with_no_worker_projects_operational_condition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                # No worker registered
                job = self._job(
                    "pending-job", NOW - timedelta(minutes=10), AutomationJobStatus.PENDING
                )
                repository.create_job(job)
                api = self._api(repository)
                statuses: list[str] = []
                environ = {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/api/v1/jobs/pending-job",
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer viewer-token",
                    "wsgi.input": io.BytesIO(),
                }
                body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
                self.assertEqual(int(statuses[0].split()[0]), 200)
                doc = json.loads(body)
                condition = doc.get("operationalCondition")
                self.assertIsNotNone(condition)
                self.assertEqual(condition["condition"], "no_worker")
                self.assertEqual(condition["sideEffects"], "none")
                self.assertTrue(condition["retrySafe"])

    @staticmethod
    def _api(repository):
        principal = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        return MediaFlowApi(repository, None, principals=(principal,), stale_job_age_seconds=3600)

    @staticmethod
    def _job(
        job_id: str,
        updated_at: datetime,
        status: AutomationJobStatus = AutomationJobStatus.RUNNING,
        *,
        error: str | None = None,
        execute_authorized: bool = False,
    ) -> AutomationJob:
        return AutomationJob(
            job_id,
            AutomationCommand.ORGANIZE if execute_authorized else AutomationCommand.SCAN,
            status,
            updated_at - timedelta(minutes=1),
            updated_at,
            started_at=updated_at - timedelta(minutes=1),
            error=error,
            execute_authorized=execute_authorized,
        )


if __name__ == "__main__":
    unittest.main()
