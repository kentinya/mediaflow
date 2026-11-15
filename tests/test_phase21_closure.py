from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from mediaflow.final_cli import final_main


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


if __name__ == "__main__":
    unittest.main()
