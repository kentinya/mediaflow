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
from zoneinfo import ZoneInfo

from mediaflow.application.automation import IntervalScheduler
from mediaflow.domain.automation import CronSchedule
from mediaflow.domain.cron import CronExpression
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


class CronExpressionTests(unittest.TestCase):
    def test_lists_ranges_steps_and_bounds(self) -> None:
        expression = CronExpression.parse("*/15 1,3 1-5/2 1,12 0-6/2")
        self.assertEqual(expression.minutes.values, frozenset({0, 15, 30, 45}))
        self.assertEqual(expression.hours.values, frozenset({1, 3}))
        self.assertEqual(expression.days.values, frozenset({1, 3, 5}))
        self.assertEqual(expression.months.values, frozenset({1, 12}))
        self.assertEqual(expression.weekdays.values, frozenset({0, 2, 4, 6}))

    def test_invalid_expression_matrix(self) -> None:
        values = (
            "* * * *",
            "* * * * * *",
            "@daily",
            "60 * * * *",
            "* 24 * * *",
            "* * 0 * *",
            "* * * 13 *",
            "* * * * 7",
            "*/0 * * * *",
            "5/2 * * * *",
            "5-1 * * * *",
            "1,,2 * * * *",
            "MON * * * *",
        )
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                CronExpression.parse(value)

    def test_day_of_month_and_weekday_use_cron_or_semantics(self) -> None:
        expression = CronExpression.parse("0 0 13 * 1")
        timezone = ZoneInfo("UTC")
        # Monday the 6th matches weekday even though it is not the 13th.
        self.assertEqual(
            expression.next_at_or_after(datetime(2025, 1, 6, tzinfo=UTC), timezone),
            datetime(2025, 1, 6, tzinfo=UTC),
        )
        # The 13th matches day-of-month (and happens to be Monday here as well).
        self.assertEqual(
            expression.next_after(datetime(2025, 1, 6, tzinfo=UTC), timezone),
            datetime(2025, 1, 13, tzinfo=UTC),
        )

    def test_timezone_year_month_and_leap_day(self) -> None:
        shanghai = CronExpression.parse("0 8 * * *")
        self.assertEqual(
            shanghai.next_at_or_after(
                datetime(2026, 8, 22, 0, 0, tzinfo=UTC), ZoneInfo("Asia/Shanghai")
            ),
            datetime(2026, 8, 22, 0, 0, tzinfo=UTC),
        )
        leap = CronExpression.parse("0 0 29 2 *")
        self.assertEqual(
            leap.next_after(datetime(2025, 3, 1, tzinfo=UTC), ZoneInfo("UTC")),
            datetime(2028, 2, 29, tzinfo=UTC),
        )

    def test_dst_nonexistent_is_skipped_and_ambiguous_fires_once(self) -> None:
        timezone = ZoneInfo("America/New_York")
        nonexistent = CronExpression.parse("30 2 * * *")
        self.assertEqual(
            nonexistent.next_after(datetime(2024, 3, 10, 6, 0, tzinfo=UTC), timezone),
            datetime(2024, 3, 11, 6, 30, tzinfo=UTC),
        )
        ambiguous = CronExpression.parse("30 1 * * *")
        first = ambiguous.next_after(datetime(2024, 11, 3, 4, 0, tzinfo=UTC), timezone)
        self.assertEqual(first, datetime(2024, 11, 3, 5, 30, tzinfo=UTC))
        self.assertEqual(
            ambiguous.next_after(first, timezone), datetime(2024, 11, 4, 6, 30, tzinfo=UTC)
        )


class CronSchedulerTests(unittest.TestCase):
    def test_schema_five_migrates_to_immutable_schedule_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_version VALUES ('runtime', 5);
                CREATE TABLE automation_schedules (
                    schedule_id TEXT PRIMARY KEY, next_run_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, last_job_id TEXT
                );
                """
            )
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                self.assertEqual(repository.list_schedule_audit(), ())

    def test_current_future_missed_and_audit(self) -> None:
        schedule = CronSchedule("morning", "preview", "0 8 * * *", "Asia/Shanghai", 20)
        now = datetime(2026, 8, 22, 0, 0, 30, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                scheduler = IntervalScheduler(repository, (schedule,))
                first = scheduler.tick(now)
                self.assertEqual(len(first), 1)
                audit = repository.list_schedule_audit("morning")
                self.assertEqual(len(audit), 1)
                self.assertEqual(audit[0].occurrence_at, now.replace(second=0))
                self.assertEqual(audit[0].job_id, first[0].job_id)
                self.assertEqual(scheduler.tick(now), ())
                # Several missed days coalesce into one emitted job.
                later = now + timedelta(days=3, minutes=1)
                self.assertEqual(len(scheduler.tick(later)), 1)
                self.assertEqual(len(repository.list_schedule_audit("morning")), 2)
                self.assertEqual(len(repository.list_jobs()), 2)

    def test_concurrent_ticks_emit_one_job_and_one_audit(self) -> None:
        schedule = CronSchedule("midnight", "scan", "0 0 * * *", "UTC")
        now = datetime(2026, 8, 22, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database):
                pass
            barrier = Barrier(2)
            results = []

            def tick() -> None:
                with SQLiteTaskRepository(database) as repository:
                    barrier.wait()
                    results.append(IntervalScheduler(repository, (schedule,)).tick(now))

            threads = [Thread(target=tick), Thread(target=tick)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(sum(len(value) for value in results), 1)
                self.assertEqual(len(repository.list_jobs()), 1)
                self.assertEqual(len(repository.list_schedule_audit()), 1)

    def test_audit_filter_limit_and_api(self) -> None:
        schedules = (
            CronSchedule("one", "scan", "* * * * *", "UTC"),
            CronSchedule("two", "preview", "* * * * *", "UTC"),
        )
        now = datetime(2026, 8, 22, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                IntervalScheduler(repository, schedules).tick(now)
                self.assertEqual(len(repository.list_schedule_audit(limit=1)), 1)
                self.assertEqual(len(repository.list_schedule_audit("one")), 1)
                api = MediaFlowApi(repository, "secret", schedules)
                status = []
                environ = {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/api/v1/schedules/one/audit",
                    "CONTENT_LENGTH": "0",
                    "HTTP_AUTHORIZATION": "Bearer secret",
                    "wsgi.input": io.BytesIO(),
                }
                body = b"".join(api(environ, lambda value, headers: status.append(value)))
                self.assertEqual(status[0].split()[0], "200")
                self.assertEqual(json.loads(body)["items"][0]["schedule_id"], "one")

    def test_runtime_configuration_and_cli_audit_are_storage_free(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["automation"] = {
            "schedules": [
                {
                    "id": "cn-morning",
                    "command": "scan",
                    "cron": "0 8 * * *",
                    "timezone": "Asia/Shanghai",
                }
            ]
        }
        loaded = load_runtime_configuration(copy.deepcopy(document))
        self.assertIsInstance(loaded.automation_schedules[0], CronSchedule)
        with tempfile.TemporaryDirectory() as directory:
            document["persistence"] = {"databasePath": str(Path(directory, "runtime.sqlite3"))}
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "scheduler", "tick"],
                    stdout=output,
                    stderr=error,
                ),
                0,
                error.getvalue(),
            )
            audit = io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "scheduler", "audit", "cn-morning"],
                    stdout=audit,
                    stderr=error,
                ),
                0,
            )
            self.assertIn("SCHEDULE AUDIT", audit.getvalue())

    def test_invalid_cron_schedule_configuration(self) -> None:
        base = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        invalid = (
            {"id": "x", "command": "scan", "cron": "* * * * *"},
            {
                "id": "x",
                "command": "scan",
                "cron": "* * * * *",
                "timezone": "Missing/Zone",
            },
            {
                "id": "x",
                "command": "scan",
                "cron": "* * * * *",
                "timezone": "UTC",
                "intervalSeconds": 60,
            },
        )
        for schedule in invalid:
            document = copy.deepcopy(base)
            document["automation"] = {"schedules": [schedule]}
            with self.subTest(schedule=schedule), self.assertRaises(ValueError):
                load_runtime_configuration(document)


if __name__ == "__main__":
    unittest.main()
