from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NO_ACTIVE_TASK_HEADING = "# NO ACTIVE IMPLEMENTATION TASK"
REQUIRED_RELEASE_QUALITY_COMMANDS = (
    "python3 scripts/check_governance.py",
    "scripts/docker_release_security_smoke_test.py",
    ".venv/bin/ruff format --check .",
    ".venv/bin/ruff check .",
    ".venv/bin/python -m unittest discover -s tests",
    ".venv/bin/python -m compileall -q mediaflow tests scripts",
)


class ReleaseSecurityPolicyTests(unittest.TestCase):
    def assert_release_quality_gate_documentation(self, task: str) -> None:
        """Require execution gates for a real Task, not the canonical no-Task notice."""

        first_nonempty_line = next(
            (line.strip() for line in task.splitlines() if line.strip()),
            "",
        )
        if first_nonempty_line == NO_ACTIVE_TASK_HEADING:
            return
        self.assertNotEqual(first_nonempty_line, "", "TASK.md must declare a lifecycle state")
        for command in REQUIRED_RELEASE_QUALITY_COMMANDS:
            self.assertIn(command, task)

    def test_dockerignore_covers_private_state_and_dockerfile_copies_only_runtime(self) -> None:
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        for required in (
            ".git",
            ".github",
            ".venv",
            "config",
            "config/alist.json",
            "config/strategy.json",
            "config/mediaflow.json",
            "compose.yaml",
            ".env",
            ".env.*",
            ".mediaflow",
            "media",
            "deploy",
            "docs",
            "scripts",
            "Task",
            "tests",
            "*.sqlite",
            "*.sqlite-*",
            "*.sqlite3*",
            "*.db",
            "*.backup",
            "*.bak",
            "*.export",
            "*.log",
            "*.jsonl",
            "*.cache",
            "*.whl",
            "backup",
            "backups",
            "exports",
            "export",
            "logs",
            ".ruff_cache",
            "web/node_modules",
            "web/dist",
            "web/coverage",
            "web/playwright-report",
            "web/test-results",
        ):
            with self.subTest(pattern=required):
                self.assertIn(required, dockerignore)

        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY pyproject.toml ./", dockerfile)
        self.assertIn("COPY mediaflow ./mediaflow", dockerfile)
        self.assertNotIn("COPY . .", dockerfile)

    def test_alist_config_is_ignored_untracked_and_never_committed(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("config/alist.json", gitignore)
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("config/alist.json", dockerignore)

        ignored = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "--no-index", "config/alist.json"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(ignored.returncode, 0, ignored.stderr)
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "config/alist.json"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(tracked.returncode, 0, "config/alist.json must stay untracked")

    def test_compose_source_has_no_literal_secrets_or_unsupported_boundaries(self) -> None:
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertNotIn("MEDIAFLOW_API_TOKEN=", compose)
        self.assertNotIn("Bearer ", compose)
        self.assertNotIn("TMDB_ACCESS_TOKEN=", compose)
        self.assertNotIn("MEDIAFLOW_WEBHOOK_SECRET=", compose)
        self.assertNotIn("docker.sock", compose)
        self.assertNotIn("privileged:", compose)
        self.assertNotIn("network_mode: host", compose)
        self.assertNotIn('source: "/"', compose)
        self.assertNotIn("pid: host", compose)
        for command in (
            '"api", "serve-production", "--host", "0.0.0.0", "--port", "8080"',
            '"worker", "run"',
            '"scheduler", "run"',
            '"notification-worker", "run"',
        ):
            self.assertIn(command, compose)
        self.assertEqual(compose.count("user: "), 1)
        self.assertIn("127.0.0.1", compose)

    def test_release_quality_gate_commands_are_documented_for_task_execution(self) -> None:
        task = (ROOT / "TASK.md").read_text(encoding="utf-8")
        self.assert_release_quality_gate_documentation(task)

    def test_no_active_task_is_legal_without_task_execution_commands(self) -> None:
        self.assert_release_quality_gate_documentation(
            f"{NO_ACTIVE_TASK_HEADING}\n\nNext Action: A SELECTS THE NEXT LARGE SLICE\n"
        )

    def test_active_task_still_requires_every_release_quality_command(self) -> None:
        active_task = "# Task 99.1 — Test fixture\n\n" + "\n".join(
            REQUIRED_RELEASE_QUALITY_COMMANDS
        )
        self.assert_release_quality_gate_documentation(active_task)

        for command in REQUIRED_RELEASE_QUALITY_COMMANDS:
            with self.subTest(missing=command):
                with self.assertRaises(AssertionError):
                    self.assert_release_quality_gate_documentation(
                        active_task.replace(command, "command intentionally absent", 1)
                    )

        with self.assertRaises(AssertionError):
            self.assert_release_quality_gate_documentation(
                "# Task 99.1 — Malformed fixture\n\nNO ACTIVE IMPLEMENTATION TASK\n"
            )


if __name__ == "__main__":
    unittest.main()
