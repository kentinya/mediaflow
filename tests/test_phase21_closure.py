from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from mediaflow.final_cli import final_main
from mediaflow.interfaces.operator_ui import APP_JS


class Phase21ClosureTests(unittest.TestCase):
    def test_top_level_cli_exposes_phase21_commands(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            final_main(["--help"], stdout=io.StringIO(), stderr=io.StringIO())
        help_text = output.getvalue()
        for command in (
            "batch",
            "files",
            "tasks",
            "metadata-reviews",
            "metadata-corrections",
            "recognition-reviews",
        ):
            with self.subTest(command=command):
                self.assertIn(command, help_text)

    def test_operator_ui_files_actions_are_read_only(self) -> None:
        script = APP_JS.decode()
        self.assertIn("/api/v1/files?", script)
        self.assertIn("showDetail('files'", script)
        self.assertNotIn("/api/v1/files/${encodeURIComponent(id)}/resolve", script)
        self.assertNotIn("/api/v1/files/${encodeURIComponent(id)}/execute", script)
        self.assertNotIn("innerHTML", script)


if __name__ == "__main__":
    unittest.main()
