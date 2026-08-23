from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from mediaflow.final_cli import final_main


class BatchCliTests(unittest.TestCase):
    def test_batch_commands_are_registered(self) -> None:
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            final_main(["batch", "--help"], stdout=io.StringIO(), stderr=error)
        self.assertIn("batch", output.getvalue())
        self.assertIn("preview", output.getvalue())
        self.assertIn("organize", output.getvalue())


if __name__ == "__main__":
    unittest.main()
