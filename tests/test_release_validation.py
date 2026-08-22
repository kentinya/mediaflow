from __future__ import annotations

import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

from scripts.wheel_smoke_test import inspect_wheel


class ReleaseValidationTests(unittest.TestCase):
    def test_ci_is_read_only_bounded_offline_and_covers_declared_versions(self) -> None:
        workflow = Path(".github/workflows/quality.yml").read_text(encoding="utf-8")
        for version in ("3.11", "3.12", "3.13"):
            self.assertIn(f'"{version}"', workflow)
        for command in (
            "ruff format --check .",
            "ruff check .",
            "python -m unittest discover -s tests",
            "python -m compileall -q mediaflow tests scripts",
            "python -m pip check",
            "config/strategy.example.json config validate",
            "config/mediaflow.phase13.2.example.json config validate",
            "scripts/wheel_smoke_test.py",
        ):
            self.assertIn(command, workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("timeout-minutes:", workflow)
        for forbidden in ("pull_request_target", "secrets.", "organize --execute", "twine upload"):
            self.assertNotIn(forbidden, workflow)

    def test_project_metadata_matches_ci_support_and_entry_points(self) -> None:
        with Path("pyproject.toml").open("rb") as stream:
            document = tomllib.load(stream)
        project = document["project"]
        self.assertEqual(project["requires-python"], ">=3.11,<3.14")
        self.assertEqual(project["scripts"]["mediaflow"], "mediaflow.cli:main")
        self.assertEqual(project["scripts"]["strategy-test"], "mediaflow.cli:main")
        self.assertEqual(
            document["tool"]["setuptools"]["packages"]["find"]["include"], ["mediaflow*"]
        )

    def test_wheel_inspection_rejects_user_and_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = root / "valid.whl"
            with zipfile.ZipFile(valid, "w") as archive:
                for name in (
                    "mediaflow/cli.py",
                    "mediaflow/final_cli.py",
                    "mediaflow/infrastructure/sqlite_backup.py",
                    "mediaflow/infrastructure/upgrade_preflight.py",
                ):
                    archive.writestr(name, "")
            inspect_wheel(valid)
            for unsafe in ("config/alist.json", "runtime.sqlite3", "tests/test_secret.py"):
                candidate = root / f"{Path(unsafe).name}.whl"
                with zipfile.ZipFile(candidate, "w") as archive:
                    for name in (
                        "mediaflow/cli.py",
                        "mediaflow/final_cli.py",
                        "mediaflow/infrastructure/sqlite_backup.py",
                        "mediaflow/infrastructure/upgrade_preflight.py",
                        unsafe,
                    ):
                        archive.writestr(name, "")
                with self.subTest(unsafe=unsafe), self.assertRaisesRegex(ValueError, "forbidden"):
                    inspect_wheel(candidate)


if __name__ == "__main__":
    unittest.main()
