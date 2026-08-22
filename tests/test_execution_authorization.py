from __future__ import annotations

import copy
import io
import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import patch

from mediaflow.application.automation import AutomationJobService, AutomationWorker
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.automation import AutomationCommand, CronSchedule, IntervalSchedule
from mediaflow.domain.execution_authorization import ExecutionAuthorizationStatus
from mediaflow.domain.organizer import ExecutionStatus, OrganizePlan, PlanOperation
from mediaflow.final_cli import _run_queued_workflow, final_main
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 22, 12, tzinfo=UTC)


def service(repository, clock=None, token="one-time-secret"):
    return ExecutionAuthorizationService(
        repository,
        maximum_ttl_seconds=900,
        clock=clock or (lambda: NOW),
        token_factory=lambda: token,
    )


def request(api, document, *, execution_token=None):
    body = json.dumps(document).encode()
    status = []
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/v1/jobs",
        "CONTENT_LENGTH": str(len(body)),
        "HTTP_AUTHORIZATION": "Bearer api-secret",
        "wsgi.input": io.BytesIO(body),
    }
    if execution_token is not None:
        environ["HTTP_X_MEDIAFLOW_EXECUTION_TOKEN"] = execution_token
    result = b"".join(api(environ, lambda value, headers: status.append(value)))
    return int(status[0].split()[0]), json.loads(result)


class ExecutionAuthorizationTests(unittest.TestCase):
    def test_runtime_feature_gate_defaults_disabled_and_validates_ttl(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["api"].pop("remoteExecution", None)
        self.assertFalse(
            load_runtime_configuration(copy.deepcopy(document)).remote_execution_enabled
        )
        document["api"]["remoteExecution"] = {
            "enabled": True,
            "maximumTtlSeconds": 120,
        }
        loaded = load_runtime_configuration(copy.deepcopy(document))
        self.assertTrue(loaded.remote_execution_enabled)
        self.assertEqual(loaded.remote_execution_maximum_ttl_seconds, 120)
        for value in (0, True, "60"):
            invalid = copy.deepcopy(document)
            invalid["api"]["remoteExecution"]["maximumTtlSeconds"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_runtime_configuration(invalid)
        literal = copy.deepcopy(document)
        literal["api"]["remoteExecution"]["token"] = "must-not-be-configured"
        with self.assertRaises(ValueError):
            load_runtime_configuration(literal)

    def test_schedules_cannot_gain_execute_authority(self) -> None:
        with self.assertRaisesRegex(ValueError, "scan or preview"):
            IntervalSchedule("unsafe", "organize", 60)
        with self.assertRaisesRegex(ValueError, "scan or preview"):
            CronSchedule("unsafe", "organize", "* * * * *", "UTC")

    def test_issue_persists_digest_only_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                issued = service(repository).issue(
                    ttl_seconds=60, max_items=2, actor="local-admin", note="manual approval"
                )
                stored = repository.get_execution_authorization(
                    issued.authorization.authorization_id
                )
                self.assertEqual(issued.token, "one-time-secret")
                self.assertNotEqual(stored.token_digest, issued.token)
                self.assertEqual(
                    stored.token_digest,
                    ExecutionAuthorizationService.digest("one-time-secret"),
                )
                audit = repository.list_execution_authorization_audit(stored.authorization_id)
                self.assertEqual([item.action for item in audit], ["issued"])
            connection = sqlite3.connect(database)
            raw = connection.execute(
                "SELECT token_digest FROM execution_authorizations"
            ).fetchone()[0]
            connection.close()
            self.assertNotIn("one-time-secret", raw)

    def test_consume_is_single_use_limit_bounded_and_creates_authorized_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                authorizer = service(repository)
                issued = authorizer.issue(ttl_seconds=60, max_items=2)
                with self.assertRaisesRegex(ValueError, "exceeds"):
                    authorizer.submit_organize(issued.token, limit=3)
                job = authorizer.submit_organize(issued.token, limit=2)
                self.assertEqual(job.command, AutomationCommand.ORGANIZE)
                self.assertTrue(job.execute_authorized)
                self.assertEqual(repository.get_job(job.job_id), job)
                with self.assertRaisesRegex(ValueError, "consumed"):
                    authorizer.submit_organize(issued.token, limit=1)
                stored = repository.get_execution_authorization(
                    issued.authorization.authorization_id
                )
                self.assertEqual(stored.status, ExecutionAuthorizationStatus.CONSUMED)
                self.assertEqual(stored.consumed_job_id, job.job_id)

    def test_expired_revoked_invalid_and_validation(self) -> None:
        clock = [NOW]
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                authorizer = service(repository, clock=lambda: clock[0])
                expired = authorizer.issue(ttl_seconds=1, max_items=1)
                clock[0] += timedelta(seconds=2)
                self.assertEqual(authorizer.list()[0].status, ExecutionAuthorizationStatus.EXPIRED)
                with self.assertRaisesRegex(ValueError, "expired"):
                    authorizer.submit_organize(expired.token, limit=1)
                self.assertEqual(
                    repository.get_execution_authorization(
                        expired.authorization.authorization_id
                    ).status,
                    ExecutionAuthorizationStatus.EXPIRED,
                )
                clock[0] = NOW
                active = service(repository, clock=lambda: clock[0], token="second").issue(
                    ttl_seconds=30, max_items=1
                )
                authorizer.revoke(active.authorization.authorization_id)
                with self.assertRaisesRegex(ValueError, "revoked"):
                    authorizer.submit_organize("second", limit=1)
                with self.assertRaisesRegex(ValueError, "invalid"):
                    authorizer.submit_organize("unknown", limit=1)
                for ttl, items in ((0, 1), (901, 1), (1, 0)):
                    with self.subTest(ttl=ttl, items=items), self.assertRaises(ValueError):
                        authorizer.issue(ttl_seconds=ttl, max_items=items)

    def test_concurrent_token_consumption_creates_one_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                service(repository).issue(ttl_seconds=60, max_items=1)
            barrier = Barrier(2)
            results = []

            def consume() -> None:
                with SQLiteTaskRepository(database) as repository:
                    barrier.wait()
                    try:
                        results.append(
                            service(repository).submit_organize("one-time-secret", limit=1)
                        )
                    except ValueError:
                        results.append(None)

            threads = [Thread(target=consume), Thread(target=consume)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(sum(item is not None for item in results), 1)
                self.assertEqual(len(repository.list_jobs()), 1)

    def test_api_requires_feature_bearer_separate_header_and_execute_true(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                issued = service(repository).issue(ttl_seconds=60, max_items=2)
                disabled = MediaFlowApi(repository, "api-secret")
                self.assertEqual(
                    request(
                        disabled,
                        {"command": "organize", "execute": True, "limit": 1},
                        execution_token=issued.token,
                    )[0],
                    400,
                )
                api = MediaFlowApi(repository, "api-secret", remote_execution_enabled=True)
                for document, token in (
                    ({"command": "organize", "execute": True, "limit": 1}, None),
                    ({"command": "organize", "limit": 1}, issued.token),
                    ({"command": "preview", "execute": True, "limit": 1}, issued.token),
                    (
                        {
                            "command": "organize",
                            "execute": True,
                            "limit": 1,
                            "executionToken": issued.token,
                        },
                        issued.token,
                    ),
                ):
                    with self.subTest(document=document):
                        self.assertEqual(request(api, document, execution_token=token)[0], 400)
                status, result = request(
                    api,
                    {"command": "organize", "execute": True, "limit": 1},
                    execution_token=issued.token,
                )
                self.assertEqual(status, 202)
                self.assertTrue(result["execute_authorized"])
                self.assertNotIn(issued.token, json.dumps(result))

    def test_worker_adds_execute_only_for_persisted_authorized_organize(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                issued = service(repository).issue(ttl_seconds=60, max_items=1)
                job = service(repository).submit_organize(issued.token, limit=1)
                calls = []

                def fake_main(args, **kwargs):
                    calls.append(args)
                    kwargs["stdout"].write("Task ID: task-execute\n")
                    return 0

                with patch("mediaflow.final_cli.final_main", side_effect=fake_main):
                    task_id = _run_queued_workflow(job, None, lambda: False)
                self.assertEqual(task_id, "task-execute")
                self.assertIn("--execute", calls[0])
                preview = AutomationJobService(repository).submit("preview", limit=1)
                calls.clear()
                with patch("mediaflow.final_cli.final_main", side_effect=fake_main):
                    _run_queued_workflow(preview, None, lambda: False)
                self.assertNotIn("--execute", calls[0])

    def test_api_job_worker_executes_existing_local_storage_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.mkv").write_bytes(b"media")
            storage = LocalStorage("local", root)
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                issued = service(repository).issue(ttl_seconds=60, max_items=1)
                api = MediaFlowApi(repository, "api-secret", remote_execution_enabled=True)
                status, submitted = request(
                    api,
                    {"command": "organize", "execute": True, "limit": 1},
                    execution_token=issued.token,
                )
                self.assertEqual(status, 202)

                def execute(job, cancelled):
                    self.assertTrue(job.execute_authorized)
                    plan = OrganizePlan(
                        "local",
                        "local",
                        "source.mkv",
                        "target/movie.mkv",
                        "A",
                        "A",
                        "A",
                        "A",
                        operation=PlanOperation.MOVE,
                    )
                    result = OrganizerExecutor().execute(
                        plan, {"local": storage}, execute=job.execute_authorized
                    )
                    self.assertEqual(result.status, ExecutionStatus.SUCCESS)
                    return "task-real-execute"

                completed = AutomationWorker(repository, execute).run_next()
                self.assertEqual(completed.job_id, submitted["job_id"])
                self.assertEqual(completed.status.value, "completed")
                self.assertFalse((root / "source.mkv").exists())
                self.assertEqual((root / "target" / "movie.mkv").read_bytes(), b"media")

    def test_cli_issues_token_once_and_lists_without_token_or_digest(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            document["api"]["remoteExecution"]["enabled"] = True
            document["persistence"] = {"databasePath": str(Path(directory, "runtime.sqlite3"))}
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document), encoding="utf-8")
            issued, errors = io.StringIO(), io.StringIO()
            self.assertEqual(
                final_main(
                    [
                        "--config",
                        str(config),
                        "execution-authorizations",
                        "issue",
                        "--ttl-seconds",
                        "60",
                        "--max-items",
                        "2",
                    ],
                    stdout=issued,
                    stderr=errors,
                ),
                0,
                errors.getvalue(),
            )
            self.assertIn("Token shown once: YES", issued.getvalue())
            listing = io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "execution-authorizations", "list"],
                    stdout=listing,
                    stderr=errors,
                ),
                0,
            )
            token = issued.getvalue().split("Token: ", 1)[1].splitlines()[0]
            self.assertNotIn(token, listing.getvalue())
            self.assertNotIn(ExecutionAuthorizationService.digest(token), listing.getvalue())

    def test_schema_seven_migrates_job_authority_and_authorization_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            connection = sqlite3.connect(database)
            connection.executescript(
                "CREATE TABLE schema_version "
                "(component TEXT PRIMARY KEY, version INTEGER NOT NULL);"
                "INSERT INTO schema_version VALUES ('runtime', 7);"
                "CREATE TABLE automation_jobs ("
                "job_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,"
                "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, limit_value INTEGER,"
                "started_at TEXT, completed_at TEXT, task_id TEXT, error TEXT,"
                "cancellation_requested INTEGER NOT NULL DEFAULT 0, schedule_id TEXT);"
            )
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, 8)
                job = AutomationJobService(repository).submit("scan")
                self.assertFalse(job.execute_authorized)


if __name__ == "__main__":
    unittest.main()
