"""Removed Scan inputs fail as ordinary unsupported inputs before runtime work."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from mediaflow.application.automation import AutomationJobService, AutomationWorker
from mediaflow.application.scope_continuation import ScopeContinuationService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import AutomationJob, AutomationJobStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentTaskStatus
from mediaflow.final_cli import _run_queued_workflow, final_main
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


def request(api, path, *, token, method="GET", body=None):
    raw = json.dumps(body).encode() if body is not None else b""
    statuses = []
    payload = b"".join(
        api(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "QUERY_STRING": "",
                "CONTENT_LENGTH": str(len(raw)),
                "REMOTE_ADDR": "127.0.0.1",
                "HTTP_AUTHORIZATION": f"Bearer {token}",
                "wsgi.input": io.BytesIO(raw),
            },
            lambda status, headers: statuses.append(status),
        )
    )
    return int(statuses[0].split()[0]), json.loads(payload)


class StandaloneScanRetirementTests(unittest.TestCase):
    def test_legacy_job_refused_without_creating_work(self):
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                with self.assertRaisesRegex(ValueError, "unsupported|must be preview"):
                    AutomationJobService(repository).submit("scan")
                self.assertEqual((), repository.list_jobs())
                self.assertEqual((), repository.list_tasks())

    def test_removed_scan_routes_are_ordinary_not_found(self):
        operator = ResolvedApiPrincipal(
            "operator",
            "operator-token",
            frozenset(
                {
                    ApiPermission.READ,
                    ApiPermission.SUBMIT_DRY_RUN,
                }
            ),
        )
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, None, principals=(operator, viewer))
                for path in (
                    "/api/v1/scans",
                    "/api/v1/manual-scan",
                    "/api/v1/manual-scans",
                    "/api/v1/operations/scans",
                ):
                    with self.subTest(path=path):
                        status, value = request(
                            api, path, token="viewer-token", method="POST", body={}
                        )
                        self.assertEqual(404, status, value)
                self.assertEqual((), repository.list_jobs())
                self.assertEqual((), repository.list_tasks())

    def test_removed_scan_history_and_cancel_routes_are_ordinary_not_found(self):
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, "operator-token")
                with patch.object(
                    api, "_refresh_configuration_binding", side_effect=AssertionError
                ):
                    for prefix in ("scans", "manual-scan", "manual-scans", "operations/scans"):
                        for suffix, method in (("/old", "GET"), ("/old/cancel", "POST")):
                            status, value = request(
                                api,
                                f"/api/v1/{prefix}{suffix}",
                                token="operator-token",
                                method=method,
                            )
                            self.assertEqual(404, status, value)
                self.assertEqual((), repository.list_tasks())
                self.assertEqual((), repository.list_jobs())

    def test_scan_dispatch_rejects_before_handler_even_with_forged_definition(self):
        for definition_id in (None, "forged"):
            with (
                self.subTest(definition_id=definition_id),
                tempfile.TemporaryDirectory() as directory,
            ):
                with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                    now = datetime.now(UTC)
                    job = AutomationJob(
                        "retired",
                        "scan",
                        AutomationJobStatus.PENDING,
                        now,
                        now,
                        definition_id=definition_id,
                    )
                    repository.create_job(job)
                    handler = Mock(side_effect=AssertionError("discovery called"))
                    finished = AutomationWorker(repository, handler).run_next()
                    self.assertEqual(AutomationJobStatus.FAILED, finished.status)
                    self.assertEqual("unsupported_workflow", finished.failure_category)
                    self.assertIsNone(finished.task_id)
                    handler.assert_not_called()
                    self.assertEqual((), repository.list_tasks())
                    with patch("mediaflow.final_cli._configuration", side_effect=AssertionError):
                        with self.assertRaisesRegex(ValueError, "unsupported|must be preview"):
                            _run_queued_workflow(job, None, lambda: False, repository=repository)

    def test_unsupported_dispatch_refuses_before_configuration(self):
        now = datetime.now(UTC)
        invalid = AutomationJob(
            "unsupported", "scan-unbounded", AutomationJobStatus.PENDING, now, now
        )
        with patch("mediaflow.final_cli._configuration", side_effect=AssertionError("runtime")):
            with self.assertRaisesRegex(ValueError, "unsupported workflow"):
                _run_queued_workflow(invalid, None, lambda: False)

    def test_fresh_schema_omits_only_dedicated_scan_tables_and_preserves_shared_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "preview",
                    execute_authorized=False,
                    configuration_snapshot_id="saved-pin",
                    configuration_snapshot_digest="a" * 64,
                )
                names = {
                    row[0]
                    for row in repository._connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertNotIn("manual_scan_tasks", names)
                self.assertNotIn("manual_scan_items", names)
                self.assertTrue({"tasks", "task_results", "manual_executions"}.issubset(names))
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.get_task(task.task_id), task)

    def test_paused_scan_cannot_admit_continuation_or_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                original = coordinator.create("scan", execute_authorized=False)
                paused = replace(original, status=PersistentTaskStatus.PAUSED)
                repository.update_task(paused)
                with self.assertRaisesRegex(ValueError, "no supported"):
                    ScopeContinuationService(repository).submit(
                        paused.task_id,
                        expected_version=None,
                        actor="operator",
                        maximum_active_jobs=10,
                    )
                with self.assertRaisesRegex(ValueError, "unsupported|must be preview"):
                    coordinator.retryable_items(paused.task_id, failed_only=False)
                self.assertEqual((), repository.list_jobs())
                self.assertEqual(paused, repository.get_task(paused.task_id))

    def test_cli_removed_scan_inputs_are_argparse_errors_before_any_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / "invalid.json"
            invalid.write_text("{broken")
            bootstrap = root / "bootstrap.json"
            bootstrap.write_text(
                json.dumps({"persistence": {"databasePath": str(root / "runtime.sqlite3")}})
            )
            for config in (None, root / "missing.json", invalid, bootstrap):
                for command in (
                    ["scan"],
                    ["scan", "--limit", "3", "--path", "/unused"],
                    ["scan", "--help"],
                    ["jobs", "submit", "scan"],
                    ["jobs", "submit", "scan", "--limit", "3"],
                ):
                    args = (["--config", str(config)] if config else []) + command
                    with self.subTest(args=args), ExitStack() as stack:
                        guards = [
                            stack.enter_context(
                                patch(
                                    "mediaflow.final_cli." + name,
                                    side_effect=AssertionError(name + " called"),
                                )
                            )
                            for name in (
                                "_configuration",
                                "SQLiteTaskRepository",
                                "SQLiteFileIndexRepository",
                                "SQLiteConfigurationRepository",
                                "RuntimeDatabaseLease",
                                "metadata_provider_registry_from_environment",
                                "strategy_runner_from_configuration",
                            )
                        ]
                        errors = io.StringIO()
                        stack.enter_context(redirect_stderr(errors))
                        with self.assertRaises(SystemExit) as raised:
                            final_main(args, stdout=io.StringIO(), stderr=io.StringIO())
                        self.assertEqual(2, raised.exception.code)
                        self.assertIn("invalid choice", errors.getvalue())
                        self.assertNotIn("retired", errors.getvalue())
                        self.assertNotIn("新建整理", errors.getvalue())
                        for guard in guards:
                            guard.assert_not_called()
            self.assertEqual({"invalid.json", "bootstrap.json"}, {p.name for p in root.iterdir()})

    def test_cli_help_only_advertises_supported_commands(self):
        for args in (["--help"], ["jobs", "submit", "--help"]):
            out = io.StringIO()
            with redirect_stdout(out), self.assertRaises(SystemExit) as raised:
                final_main(args, stdout=io.StringIO(), stderr=io.StringIO())
            self.assertEqual(0, raised.exception.code)
            self.assertNotIn("scan", out.getvalue().lower())
            self.assertIn("preview", out.getvalue())


if __name__ == "__main__":
    unittest.main()
