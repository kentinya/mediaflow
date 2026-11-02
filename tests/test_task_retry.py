"""The retired standalone CLI retry entrances stay retired with zero effects.

Slice 47 RO-6 retired ``tasks retry-request`` and, with it, the independent
``tasks retry-failed`` entrance: new organizing starts from Files/``organize``
and an existing Task's own four-type continuation.  The old commands must fail
at argument parsing like any unrecognized command: no database, no Storage, no
Provider, no recovery request, no pending rewrite and no execution.
"""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration


class TaskRetryEntranceRetirementTests(unittest.TestCase):
    def test_help_no_longer_lists_a_retry_command(self) -> None:
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            with self.assertRaises(SystemExit):
                final_main(["tasks", "--help"], stdout=output, stderr=error)
        self.assertIn("ignore-pending", output.getvalue())
        self.assertIn("cancel", output.getvalue())
        self.assertNotIn("retry-failed", output.getvalue())
        self.assertNotIn("retry-request", output.getvalue())
        self.assertNotIn("retry-failed", error.getvalue())
        self.assertNotIn("retry-request", error.getvalue())

    def test_retired_commands_fail_at_parsing_with_zero_effects(self) -> None:
        for command in ("retry-failed", "retry-request", "retry"):
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    # A configuration document that would fail any real runtime
                    # load: reaching it at all would mean the parser did not
                    # stop first.
                    config_path = root / "strategy.json"
                    config_path.write_text(json.dumps({"version": 1}), encoding="utf-8")
                    database = root / "runtime.sqlite3"
                    output, error = io.StringIO(), io.StringIO()
                    with (
                        redirect_stderr(error),
                        patch.object(
                            RuntimeConfiguration,
                            "create_storages",
                            side_effect=AssertionError("retired retry command constructed Storage"),
                        ),
                    ):
                        with self.assertRaises(SystemExit) as exited:
                            final_main(
                                [
                                    "--config",
                                    str(config_path),
                                    "tasks",
                                    command,
                                    "task-id",
                                    *(
                                        ["--actor", "operator"]
                                        if command == "retry-request"
                                        else []
                                    ),
                                ],
                                stdout=output,
                                stderr=error,
                            )
                    self.assertEqual(2, exited.exception.code)
                    self.assertIn("invalid choice", error.getvalue())
                    self.assertEqual("", output.getvalue())
                    # Parsing stopped before any runtime construction: no
                    # database was created, so no Task, item, request, audit or
                    # queue row exists.
                    self.assertFalse(database.exists())
                    if database.exists():  # pragma: no cover - defensive only
                        with sqlite3.connect(database) as connection:
                            self.assertEqual(
                                (),
                                connection.execute("SELECT * FROM task_retry_audit").fetchall(),
                            )
                            self.assertEqual(
                                (), connection.execute("SELECT * FROM tasks").fetchall()
                            )


if __name__ == "__main__":
    unittest.main()
