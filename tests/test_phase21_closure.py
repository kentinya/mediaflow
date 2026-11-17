from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from mediaflow.final_cli import final_main


class Phase21ClosureTests(unittest.TestCase):
    def test_top_level_cli_exposes_current_commands_without_retired_review_queues(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            final_main(["--help"], stdout=io.StringIO(), stderr=io.StringIO())
        help_text = output.getvalue()
        for command in ("batch", "files", "tasks"):
            with self.subTest(command=command):
                self.assertIn(command, help_text)
        for retired in (
            "metadata-reviews",
            "metadata-corrections",
            "recognition-reviews",
            "classification-reviews",
            "confirmations",
        ):
            with self.subTest(command=retired):
                self.assertNotIn(retired, help_text)


if __name__ == "__main__":
    unittest.main()
