from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.operational_logging import SQLiteOperationalLogger
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

NOW = datetime(2026, 8, 22, 12, tzinfo=UTC)


class OperationalLoggingTests(unittest.TestCase):
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
                encoded = repr(values)
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
