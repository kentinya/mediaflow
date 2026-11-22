from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mediaflow.domain.cron import CronExpression
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from tests.resident_entry_fixtures import run_resident_step


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


class SchedulerDefinitionBoundaryTests(unittest.TestCase):
    """The Scheduler consumes Automation Task Definitions only.

    The retired ``automation.schedules`` product neither parses into runtime
    configuration nor advertises CLI surfaces; a system-generated empty slot in
    a normal V2 document stays readable with no scheduling semantics.
    """

    def _definition_document(self) -> dict:
        return {
            "id": "cn-morning",
            "name": "Morning organize",
            "resourceLibraryId": "source",
            "mode": "automatic-organization",
            "cron": "0 8 * * *",
            "timezone": "Asia/Shanghai",
            "enabled": False,
        }

    def _base_document(self) -> dict:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["automation"] = {}
        document["automationTaskDefinitions"] = [self._definition_document()]
        return document

    def test_scheduler_tick_runs_definition_only_configuration(self) -> None:
        document = self._base_document()
        with tempfile.TemporaryDirectory() as directory:
            document["persistence"] = {"databasePath": str(Path(directory, "runtime.sqlite3"))}
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            status, output = run_resident_step("scheduler", config)
            self.assertEqual(status, 0, output)

    def test_scheduler_list_and_audit_are_not_registered(self) -> None:
        import contextlib

        with tempfile.TemporaryDirectory() as directory:
            document = self._base_document()
            document["persistence"] = {"databasePath": str(Path(directory, "runtime.sqlite3"))}
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            for arguments in (
                ["--config", str(config), "scheduler", "list"],
                ["--config", str(config), "scheduler", "audit", "cn-morning"],
            ):
                output, error = io.StringIO(), io.StringIO()
                with contextlib.redirect_stderr(io.StringIO()) as parser_error:
                    with self.assertRaises(SystemExit):
                        final_main(arguments, stdout=output, stderr=error)
                self.assertIn("invalid choice", parser_error.getvalue())

    def test_empty_schedules_slot_stays_readable_without_semantics(self) -> None:
        document = self._base_document()
        document["automation"] = {"schedules": []}
        loaded = load_runtime_configuration(copy.deepcopy(document))
        self.assertEqual(loaded.automation_task_definitions[0].definition_id, "cn-morning")
        self.assertEqual(
            getattr(loaded, "automation_schedules", None),
            None,
            "the retired schedules product keeps no runtime projection",
        )

    def test_retired_schedule_definitions_reject_through_normal_validation(self) -> None:
        invalid = (
            {"id": "x", "command": "organize", "cron": "* * * * *"},
            {
                "id": "x",
                "command": "organize",
                "cron": "* * * * *",
                "timezone": "UTC",
                "intervalSeconds": 60,
            },
            {"id": "x", "command": "organize", "intervalSeconds": 60},
        )
        for schedule in invalid:
            document = self._base_document()
            document["automation"] = {"schedules": [schedule]}
            with self.subTest(schedule=schedule), self.assertRaises(ValueError):
                load_runtime_configuration(document)

    def test_non_list_schedules_value_rejects(self) -> None:
        document = self._base_document()
        document["automation"] = {"schedules": "organize-daily"}
        with self.assertRaises(ValueError):
            load_runtime_configuration(document)


if __name__ == "__main__":
    unittest.main()
