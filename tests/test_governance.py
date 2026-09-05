from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_governance.py"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def write(repo: Path, name: str, content: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def slice_document(slice_id: int, status: str, base_sha: str) -> str:
    return f"""# Slice {slice_id} — Test Slice

```text
Slice ID: {slice_id}
Owner: A
Status: {status}
Base SHA: {base_sha}
Implementation Head: NOT SET
```
"""


def roadmap_document(slice_id: int, status: str, next_status: str = "PLANNED") -> str:
    next_id = slice_id + 1
    return f"""# Roadmap

| Slice | Goal | Status | Depends On |
|---|---|---|---|
| {slice_id} — Test Slice | test | {status} | base |
| {next_id} — Next Slice | test | {next_status} | {slice_id} |
"""


def task_document(parent_slice: int, status: str, task_base: str) -> str:
    return f"""# Task {parent_slice}.1 — Test Task

```text
Task ID: {parent_slice}.1
Parent Slice: {parent_slice}
Status: {status}
Task Base: {task_base}
```
"""


def init_repo(slice_id: int = 27, slice_status: str = "ACTIVE") -> tuple[Path, str]:
    repo = Path(tempfile.mkdtemp(prefix="mediaflow-governance-"))
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Governance Test")
    write(repo, "README.md", "test\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-qm", "base")
    base_sha = git(repo, "rev-parse", "HEAD")
    write(repo, "SLICE.md", slice_document(slice_id, slice_status, base_sha))
    write(repo, "docs/roadmap.md", roadmap_document(slice_id, slice_status))
    write(repo, "TASK.md", "# NO ACTIVE IMPLEMENTATION TASK\n")
    git(repo, "add", "SLICE.md", "docs/roadmap.md", "TASK.md")
    git(repo, "commit", "-qm", "activate slice")
    return repo, base_sha


def run_check(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo)],
        check=False,
        capture_output=True,
        text=True,
    )


class GovernanceCheckTests(unittest.TestCase):
    def test_current_repository_passes_no_active_closed_slice_state(self) -> None:
        result = run_check(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_base_can_precede_contract_checkpoint(self) -> None:
        repo, base_sha = init_repo()
        result = run_check(repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(base_sha, git(repo, "rev-parse", "HEAD"))

    def test_uncheckpointed_working_tree_slice_is_rejected(self) -> None:
        repo, base_sha = init_repo(slice_id=27, slice_status="PASS / CLOSED")
        write(repo, "SLICE.md", slice_document(28, "ACTIVE", base_sha))
        write(repo, "TASK.md", task_document(28, "PLANNED", base_sha))
        result = run_check(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SLICE.md differs from HEAD", result.stderr)

    def test_active_task_requires_matching_parent_and_active_roadmap(self) -> None:
        repo, base_sha = init_repo()
        write(repo, "TASK.md", task_document(26, "PLANNED", base_sha))
        result = run_check(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Parent Slice", result.stderr)

        write(repo, "TASK.md", task_document(27, "PLANNED", base_sha))
        write(repo, "docs/roadmap.md", roadmap_document(27, "PLANNED"))
        git(repo, "add", "docs/roadmap.md")
        git(repo, "commit", "-qm", "bad roadmap")
        result = run_check(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Roadmap Slice 27 must be ACTIVE", result.stderr)


if __name__ == "__main__":
    unittest.main()
