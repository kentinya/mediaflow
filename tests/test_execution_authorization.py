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

from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.domain.automation import CronSchedule, IntervalSchedule
from mediaflow.domain.execution_authorization import ExecutionAuthorizationStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
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
        "PATH_INFO": "/api/v1/tasks",
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
        # A schedule can only ever declare the supported organize command; the
        # retired DryRun/Preview command is not a schedule command.
        with self.assertRaises(ValueError):
            IntervalSchedule("unsafe", "preview", 60)
        with self.assertRaises(ValueError):
            CronSchedule("unsafe", "preview", "* * * * *", "UTC")
        # Organize is the one accepted schedule command.
        self.assertEqual(IntervalSchedule("ok", "organize", 60).command.value, "organize")

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

    def test_consume_is_single_use_limit_bounded_and_admits_authorized_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                authorizer = service(repository)
                issued = authorizer.issue(ttl_seconds=60, max_items=2)
                with self.assertRaisesRegex(ValueError, "exceeds"):
                    authorizer.submit_organize(issued.token, limit=3)
                submission = authorizer.submit_organize(issued.token, limit=2)
                task = submission.task
                self.assertEqual(task.command, "organize")
                self.assertTrue(task.execute_authorized)
                self.assertEqual(repository.get_task(task.task_id), task)
                state = repository.get_task_scheduling(task.task_id)
                self.assertIsNotNone(state)
                self.assertEqual(state.queue_state.value, "queued")
                self.assertEqual(state.admission_principal, "remote-execution")
                self.assertEqual(1, len(repository.list_tasks()))
                with self.assertRaisesRegex(ValueError, "consumed"):
                    authorizer.submit_organize(issued.token, limit=1)
                stored = repository.get_execution_authorization(
                    issued.authorization.authorization_id
                )
                self.assertEqual(stored.status, ExecutionAuthorizationStatus.CONSUMED)
                # The legacy column keeps its name and carries the substantive
                # Task identity, exactly like the occurrence link.
                self.assertEqual(stored.consumed_task_id, task.task_id)
                audit = repository.list_execution_authorization_audit(stored.authorization_id)
                self.assertEqual(
                    [item.task_id for item in audit if item.action == "consumed"], [task.task_id]
                )

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

    def test_concurrent_token_consumption_admits_one_task(self) -> None:
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
                self.assertEqual(len(()), 0)
                self.assertEqual(len(repository.list_tasks()), 1)

    def test_api_requires_feature_bearer_separate_header_and_execute_true(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                issued = service(repository, clock=lambda: datetime.now(UTC)).issue(
                    ttl_seconds=60, max_items=2
                )
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
                # Only a refused request leaves the one-shot authority
                # unconsumed, so the accepted case runs last.
                for document, token in (
                    ({"command": "organize", "execute": True, "limit": 1}, None),
                    ({"command": "organize", "limit": 1}, issued.token),
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
                self.assertTrue(result["executeAuthorized"])
                self.assertTrue(result["taskId"])
                self.assertEqual(result["executionMethod"], "task_engine")
                self.assertNotIn(issued.token, json.dumps(result))
                # The admitted run is one shared Task: no Job row exists and the
                # queued Task is the only durable identity.
                self.assertEqual(1, len(repository.list_tasks()))
                self.assertIsNotNone(repository.get_task(result["taskId"]))

    def test_api_ticket_admits_one_queued_authorized_task_without_a_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.mkv").write_bytes(b"media")
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                issued = service(repository, clock=lambda: datetime.now(UTC)).issue(
                    ttl_seconds=60, max_items=1
                )
                api = MediaFlowApi(repository, "api-secret", remote_execution_enabled=True)
                status, submitted = request(
                    api,
                    {"command": "organize", "execute": True, "limit": 1},
                    execution_token=issued.token,
                )
                self.assertEqual(status, 202)
                task_id = submitted["taskId"]
                task = repository.get_task(task_id)
                self.assertIsNotNone(task)
                self.assertTrue(task.execute_authorized)
                self.assertIsNone(task.scope_path)
                self.assertEqual(task.item_limit, 1)
                state = repository.get_task_scheduling(task_id)
                self.assertEqual(state.queue_state.value, "queued")
                self.assertEqual(state.admission_trigger.value, "manual")
                self.assertEqual(1, len(repository.list_tasks()))
                # The whole-library scope is the Task's own admitted shape; the
                # resident engine owns its execution, so nothing ran here.
                self.assertFalse((root / "target").exists())
                self.assertTrue((root / "source.mkv").exists())

    def test_cli_organize_execute_admits_and_executes_one_kernel_task(self) -> None:
        """Task47.3: the direct CLI execute entrance is one shared Task run.

        The admitted Task — not a parallel generic coordinator row — carries the
        run: the shared kernel admission, the claim-fenced publication, the
        settled aggregate and the honest exit code.  No Job row exists and the
        analysis-only command keeps its own zero-mutation shape.
        """

        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            source_root.mkdir()
            target_root.mkdir()
            (source_root / "Movies").mkdir()
            media = source_root / "Movies" / "One.2001.mkv"
            media.write_bytes(b"m" * 512)
            document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
            document["historyPath"] = str(root / "history.jsonl")
            document["storages"] = [
                {
                    "id": "source",
                    "name": "Source",
                    "type": "local",
                    "rootPath": str(source_root),
                    "enabled": True,
                },
                {
                    "id": "target",
                    "name": "Target",
                    "type": "local",
                    "rootPath": str(target_root),
                    "enabled": True,
                },
            ]
            document["resourceLibraries"] = [
                {
                    "id": "library",
                    "name": "Library",
                    "storageId": "source",
                    "storagePath": "",
                    "enabled": True,
                    "extensions": ["mkv", "mp4"],
                }
            ]
            document["mediaLibraries"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "storageId": "target",
                    "rootPath": "Organized/Movies",
                    "enabled": True,
                },
                {
                    "id": "tv",
                    "name": "TV",
                    "storageId": "target",
                    "rootPath": "Organized/TV",
                    "enabled": True,
                },
            ]
            document["automationTaskDefinitions"] = []
            document["recognitionRules"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "priority": 100,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {
                        "field": "extension",
                        "operator": "in",
                        "value": ["mkv", "mp4"],
                    },
                    "outputRecognitionType": "A",
                }
            ]
            config = root / "config.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            from mediaflow.application.metadata import MetadataProviderRegistry
            from mediaflow.application.strategy_test import SyntheticMetadataProvider
            from mediaflow.domain.metadata import MediaCandidate, MediaType

            provider = MetadataProviderRegistry(
                (
                    SyntheticMetadataProvider(
                        (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
                    ),
                )
            )
            # A real older queued Run once already holds the shared queue.  The
            # direct CLI must claim its *own* newly admitted Task atomically, not
            # take the oldest Task and then reject its identity.
            from mediaflow.application.task_scheduling import (
                TaskSchedulingService,
                build_scheduled_task_admission,
            )
            from mediaflow.domain.task_scheduling import TaskTrigger

            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                scheduling = TaskSchedulingService(repository, capacity=100)
                older_task, older_state = build_scheduled_task_admission(
                    "organize",
                    execute_authorized=True,
                    trigger=TaskTrigger.RUN_ONCE,
                    principal="automation-scheduler",
                    request_id="pre-existing-run-once",
                    now=datetime.now(UTC),
                )
                repository.admit_scheduled_task(
                    older_task, older_state, capacity=scheduling.capacity
                )

            output, errors = io.StringIO(), io.StringIO()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                return_value=provider,
            ):
                code = final_main(
                    ["--config", str(config), "organize", "--execute", "--limit", "5"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(0, code, errors.getvalue())
            self.assertIn("Task ID:", output.getvalue())
            self.assertFalse(media.exists())
            organized = list((target_root / "Organized" / "Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                self.assertEqual(2, len(repository.list_tasks()))
                tasks = repository.list_tasks()
                self.assertEqual(2, len(tasks), tasks)
                task = next(value for value in tasks if value.task_id != older_task.task_id)
                self.assertEqual("organize", task.command)
                self.assertTrue(task.execute_authorized)
                self.assertEqual("completed", task.status.value)
                state = repository.get_task_scheduling(task.task_id)
                self.assertIsNotNone(state)
                self.assertEqual(state.queue_state.value, "settled")
                self.assertEqual(state.admission_trigger.value, "manual")
                (item,) = repository.list_items(task.task_id)
                self.assertEqual("success", item.status.value)
                self.assertEqual(1, len(repository.list_results(task.task_id)))

                # The older Run once is untouched: still queued, never claimed by
                # the CLI, no fabricated processing or result, and no second
                # owner left behind in the shared queue.
                older = repository.get_task(older_task.task_id)
                self.assertEqual("pending", older.status.value)
                older_queue = repository.get_task_scheduling(older_task.task_id)
                self.assertEqual("queued", older_queue.queue_state.value)
                self.assertIsNone(older_queue.claim_token)
                self.assertIsNone(older_queue.claim_worker_id)
                self.assertEqual((), repository.list_items(older_task.task_id))
                self.assertEqual((), repository.list_results(older_task.task_id))
                # The transient CLI Worker identity was stopped with the run.
                workers = repository.list_workers()
                self.assertTrue(workers, workers)
                self.assertTrue(
                    all(worker.status.value == "stopped" for worker in workers), workers
                )

    def test_direct_cli_never_steals_a_task_already_owned_by_a_resident_worker(self) -> None:
        from mediaflow.application.task_scheduling import (
            TaskSchedulingService,
            build_scheduled_task_admission,
        )
        from mediaflow.domain.task_scheduling import TaskTrigger, TaskWorkerRejected
        from mediaflow.final_cli import _drive_direct_organize_claim

        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                now = datetime.now(UTC)
                scheduling = TaskSchedulingService(repository, capacity=2)
                task, state = build_scheduled_task_admission(
                    "organize",
                    execute_authorized=True,
                    trigger=TaskTrigger.MANUAL,
                    principal="cli",
                    now=now,
                )
                repository.admit_scheduled_task(task, state, capacity=scheduling.capacity)
                repository.register_worker(
                    "resident-worker",
                    "resident",
                    5.0,
                    ("organize",),
                    None,
                    None,
                    SCHEMA_VERSION,
                    now,
                )
                owned = scheduling.claim(
                    task.task_id,
                    worker_id="resident-worker",
                    now=now + timedelta(seconds=1),
                    lease_seconds=900,
                )
                self.assertIsNotNone(owned)
                with self.assertRaisesRegex(TaskWorkerRejected, "already owned"):
                    _drive_direct_organize_claim(repository, scheduling, task)
                # This process took nothing and left no live temporary Worker.
                current = repository.get_task_scheduling(task.task_id)
                self.assertEqual("resident-worker", current.claim_worker_id)
                self.assertEqual(owned.claim_token, current.claim_token)
                temporary = [
                    worker
                    for worker in repository.list_workers()
                    if worker.worker_id.startswith("direct-organize-")
                ]
                self.assertTrue(temporary, temporary)
                self.assertTrue(all(worker.status.value == "stopped" for worker in temporary))

    def test_cli_organize_without_execute_keeps_analysis_only_shape(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            source_root.mkdir()
            target_root.mkdir()
            (source_root / "Movies").mkdir()
            media = source_root / "Movies" / "One.2001.mkv"
            media.write_bytes(b"m" * 512)
            document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
            document["historyPath"] = str(root / "history.jsonl")
            document["storages"] = [
                {
                    "id": "source",
                    "name": "Source",
                    "type": "local",
                    "rootPath": str(source_root),
                    "enabled": True,
                },
                {
                    "id": "target",
                    "name": "Target",
                    "type": "local",
                    "rootPath": str(target_root),
                    "enabled": True,
                },
            ]
            document["resourceLibraries"] = [
                {
                    "id": "library",
                    "name": "Library",
                    "storageId": "source",
                    "storagePath": "",
                    "enabled": True,
                    "extensions": ["mkv", "mp4"],
                }
            ]
            document["mediaLibraries"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "storageId": "target",
                    "rootPath": "Organized/Movies",
                    "enabled": True,
                },
                {
                    "id": "tv",
                    "name": "TV",
                    "storageId": "target",
                    "rootPath": "Organized/TV",
                    "enabled": True,
                },
            ]
            document["automationTaskDefinitions"] = []
            document["recognitionRules"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "priority": 100,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {
                        "field": "extension",
                        "operator": "in",
                        "value": ["mkv", "mp4"],
                    },
                    "outputRecognitionType": "A",
                }
            ]
            config = root / "config.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            from mediaflow.application.metadata import MetadataProviderRegistry
            from mediaflow.application.strategy_test import SyntheticMetadataProvider
            from mediaflow.domain.metadata import MediaCandidate, MediaType

            provider = MetadataProviderRegistry(
                (
                    SyntheticMetadataProvider(
                        (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
                    ),
                )
            )
            output, errors = io.StringIO(), io.StringIO()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                return_value=provider,
            ):
                code = final_main(
                    ["--config", str(config), "organize", "--limit", "5"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(0, code, errors.getvalue())
            self.assertTrue(media.exists())
            self.assertEqual([], list((target_root / "Organized").rglob("*.mkv")))
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                self.assertEqual(1, len(repository.list_tasks()))
                tasks = repository.list_tasks()
                self.assertEqual(1, len(tasks), tasks)
                task = tasks[0]
                self.assertFalse(task.execute_authorized)
                # The analysis-only run stays outside the organizing execution
                # queue: no kernel scheduling row claims it.
                self.assertIsNone(repository.get_task_scheduling(task.task_id))
                (item,) = repository.list_items(task.task_id)
                self.assertEqual("dry_run", item.status.value)

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


if __name__ == "__main__":
    unittest.main()
