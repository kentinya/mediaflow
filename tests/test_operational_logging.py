from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.operational_logging import SQLiteOperationalLogger
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS, INDEX_HTML
from mediaflow.interfaces.pagination import decode_cursor
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 22, 12, tzinfo=UTC)


def request(api, query=""):
    statuses = []
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/api/v1/logs",
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": "Bearer viewer-token",
        "wsgi.input": io.BytesIO(),
    }
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


class OperationalLoggingTests(unittest.TestCase):
    def test_api_pages_logs_both_directions_and_binds_level(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                for rank in range(5):
                    repository.append_operational_log(
                        OperationalLogRecord(
                            f"log-{rank}",
                            NOW,
                            LogLevel.ERROR,
                            "worker",
                            "scan.failed",
                            task_id=f"task-{rank}",
                            status="failed",
                        )
                    )
                principal = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                api = MediaFlowApi(repository, None, principals=(principal,))
                _, first = request(api, "limit=2&level=ERROR")
                _, middle = request(api, f"limit=2&level=ERROR&cursor={first['next_cursor']}")
                _, last = request(api, f"limit=2&level=ERROR&cursor={middle['next_cursor']}")
                self.assertIsNone(first["previous_cursor"])
                self.assertIsNone(last["next_cursor"])
                position = decode_cursor(
                    last["previous_cursor"], "operational_logs", expected_scope="ERROR"
                )
                with patch.object(
                    repository, "list_operational_logs", wraps=repository.list_operational_logs
                ) as logs:
                    _, back = request(api, f"limit=2&level=ERROR&cursor={last['previous_cursor']}")
                logs.assert_called_once_with(minimum_level=LogLevel.ERROR, limit=3, before=position)
                self.assertEqual(back["items"], middle["items"])
                _, beginning = request(api, f"limit=2&level=ERROR&cursor={back['previous_cursor']}")
                self.assertEqual(beginning["items"], first["items"])
                self.assertEqual(
                    request(api, f"limit=2&level=all&cursor={first['next_cursor']}")[0], 400
                )
                allowed = {
                    "log_id",
                    "occurred_at",
                    "level",
                    "component",
                    "event",
                    "task_id",
                    "job_id",
                    "plan_id",
                    "status",
                }
                self.assertEqual(set(first["items"][0]), allowed)
                _, one = request(api, "limit=1&level=ERROR")
                self.assertEqual(len(one["items"]), 1)
                self.assertNotIn("level=ERROR", repr(repository.list_security_audit(limit=100)))
                for query in (
                    "limit=0",
                    "level=nope",
                    "cursor=%25",
                    "level=all&level=INFO",
                    "path=/private",
                ):
                    with self.subTest(query=query):
                        self.assertEqual(request(api, query)[0], 400)

    def test_operator_ui_log_view_is_read_only(self) -> None:
        html, script = INDEX_HTML.decode(), APP_JS.decode()
        self.assertIn('data-view="logs"', html)
        self.assertIn("/api/v1/logs?limit=100&level=", script)
        self.assertIn("Refresh logs", script)
        self.assertIn("renderLogs(level, data.previous_cursor)", script)
        self.assertIn("renderLogs(level, data.next_cursor)", script)
        self.assertNotIn("logs/prune", script)
        self.assertNotIn("innerHTML", script)

    def test_persistence_failure_never_escapes_logger(self) -> None:
        class FailingRepository:
            def append_operational_log(self, value) -> None:
                raise RuntimeError("database unavailable")

        logger = SQLiteOperationalLogger(FailingRepository(), "workflow")
        logger.log(LogLevel.ERROR, "media workflow failed", source="/private/movie.mkv")

    def test_logger_persists_only_fixed_events_and_safe_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                logger = SQLiteOperationalLogger(
                    repository, "workflow", LogLevel.INFO, clock=lambda: NOW
                )
                logger.log(LogLevel.DEBUG, "scan started", task_id="task-low")
                logger.log(
                    LogLevel.ERROR,
                    "media workflow failed",
                    task_id="task-1",
                    plan_id="plan-1",
                    status="failed",
                    source="/private/movie.mkv",
                    error="token=secret",
                    title="Secret Movie",
                    provider_id="123",
                )
                logger.log(LogLevel.ERROR, "secret arbitrary message", task_id="task-2")
                values = repository.list_operational_logs(limit=10)
                self.assertEqual(len(values), 1)
                self.assertEqual(values[0].event, "workflow.failed")
                self.assertEqual(values[0].task_id, "task-1")
                encoded = "\n".join(
                    " ".join(
                        (
                            value.event,
                            value.task_id or "",
                            value.job_id or "",
                            value.plan_id or "",
                            value.status or "",
                        )
                    )
                    for value in values
                )
                for forbidden in ("private", "movie.mkv", "secret", "Secret Movie", "123"):
                    self.assertNotIn(forbidden, encoded)

    def test_repository_order_filter_retention_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                for rank, level in enumerate((LogLevel.INFO, LogLevel.ERROR, LogLevel.WARN)):
                    repository.append_operational_log(
                        OperationalLogRecord(
                            f"log-{rank}",
                            NOW + timedelta(days=rank),
                            level,
                            "worker",
                            "scan.completed",
                        )
                    )
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                self.assertEqual(
                    [item.log_id for item in repository.list_operational_logs(limit=2)],
                    ["log-2", "log-1"],
                )
                self.assertEqual(
                    [
                        item.log_id
                        for item in repository.list_operational_logs(
                            limit=10, minimum_level=LogLevel.ERROR
                        )
                    ],
                    ["log-1"],
                )
                removed = repository.prune_operational_logs(
                    before=NOW + timedelta(hours=1), maximum_records=1
                )
                self.assertEqual(removed, 2)
                self.assertEqual(repository.list_operational_logs(limit=10)[0].log_id, "log-2")
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.list_operational_logs(limit=10)[0].log_id, "log-2")

    def test_configuration_and_local_cli_are_bounded(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        self.assertFalse(
            load_runtime_configuration(copy.deepcopy(document)).operational_logging_enabled
        )
        document["operationalLogging"] = {
            "enabled": True,
            "minimumLevel": "WARN",
            "retentionDays": 7,
            "maximumRecords": 50,
        }
        loaded = load_runtime_configuration(copy.deepcopy(document))
        self.assertEqual(loaded.operational_logging_minimum_level, LogLevel.WARN)
        for field, value in (
            ("enabled", 1),
            ("minimumLevel", "NOPE"),
            ("retentionDays", 0),
            ("maximumRecords", True),
        ):
            invalid = copy.deepcopy(document)
            invalid["operationalLogging"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                load_runtime_configuration(invalid)
        with tempfile.TemporaryDirectory() as directory:
            document["persistence"] = {"databasePath": str(Path(directory, "runtime.sqlite3"))}
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(document["persistence"]["databasePath"]) as repository:
                repository.append_operational_log(
                    OperationalLogRecord("safe-log", NOW, LogLevel.ERROR, "worker", "scan.failed")
                )
            output, error = io.StringIO(), io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "logs", "list", "--limit", "1"],
                    stdout=output,
                    stderr=error,
                ),
                0,
                error.getvalue(),
            )
            self.assertIn("scan.failed", output.getvalue())
            output = io.StringIO()
            self.assertEqual(
                final_main(["--config", str(config), "logs", "prune"], stdout=output, stderr=error),
                0,
            )
            self.assertIn("rows removed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
