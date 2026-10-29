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


def standalone_task_document(status: str, task_base: str) -> str:
    return f"""# Task PATCH-1 — Standalone bug

```text
Task ID: PATCH-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
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

    def test_planned_slice_without_an_active_task_is_valid(self) -> None:
        repo, _base_sha = init_repo(slice_status="PLANNED")
        result = run_check(repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_planned_slice_cannot_authorize_any_active_task_status(self) -> None:
        repo, base_sha = init_repo(slice_status="PLANNED")
        for status in ("PLANNED", "IN PROGRESS", "FIX REQUIRED", "READY FOR B REVIEW"):
            with self.subTest(status=status):
                write(repo, "TASK.md", task_document(27, status, base_sha))
                result = run_check(repo)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ACTIVE or FIX REQUIRED", result.stderr)

    def test_planned_slice_requires_a_planned_roadmap_row(self) -> None:
        repo, _base_sha = init_repo(slice_status="PLANNED")
        write(repo, "docs/roadmap.md", roadmap_document(27, "ACTIVE"))
        git(repo, "add", "docs/roadmap.md")
        git(repo, "commit", "-qm", "mismatched planned roadmap")
        result = run_check(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Roadmap Slice 27 must be PLANNED", result.stderr)

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

    def test_fix_required_slice_allows_one_matching_active_correction_task(self) -> None:
        repo, _base_sha = init_repo()
        task_base = git(repo, "rev-parse", "HEAD")
        write(repo, "SLICE.md", slice_document(27, "FIX REQUIRED", task_base))
        git(repo, "add", "SLICE.md")
        git(repo, "commit", "-qm", "record A fix-required review")
        write(repo, "TASK.md", task_document(27, "PLANNED", task_base))

        result = run_check(repo)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fix_required_slice_still_requires_an_active_correction_task(self) -> None:
        repo, _base_sha = init_repo()
        task_base = git(repo, "rev-parse", "HEAD")
        write(repo, "SLICE.md", slice_document(27, "FIX REQUIRED", task_base))
        git(repo, "add", "SLICE.md")
        git(repo, "commit", "-qm", "record A fix-required review")

        result = run_check(repo)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FIX REQUIRED cannot have NO ACTIVE IMPLEMENTATION TASK", result.stderr)

    def test_standalone_bug_lifecycle_preserves_closed_or_planned_slice(self) -> None:
        for slice_status in ("PASS / CLOSED", "PLANNED"):
            repo, base_sha = init_repo(slice_status=slice_status)
            before_slice = (repo / "SLICE.md").read_bytes()
            before_roadmap = (repo / "docs/roadmap.md").read_bytes()
            for status in ("PLANNED", "IN PROGRESS", "FIX REQUIRED", "READY FOR B REVIEW"):
                with self.subTest(slice_status=slice_status, task_status=status):
                    write(repo, "TASK.md", standalone_task_document(status, base_sha))
                    before_status = git(repo, "status", "--porcelain")
                    result = run_check(repo)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual((repo / "SLICE.md").read_bytes(), before_slice)
                    self.assertEqual((repo / "docs/roadmap.md").read_bytes(), before_roadmap)
                    self.assertEqual(git(repo, "status", "--porcelain"), before_status)

    def test_standalone_bug_pass_returns_to_no_active_task(self) -> None:
        repo, base_sha = init_repo(slice_status="PASS / CLOSED")
        write(repo, "TASK.md", standalone_task_document("READY FOR B REVIEW", base_sha))
        self.assertEqual(run_check(repo).returncode, 0)
        write(repo, "TASK.md", "# NO ACTIVE IMPLEMENTATION TASK\n\nB reviewed PATCH-1: PASS.\n")
        result = run_check(repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_standalone_bug_requires_explicit_type_and_no_parent(self) -> None:
        repo, base_sha = init_repo(slice_status="PASS / CLOSED")
        document = standalone_task_document("PLANNED", base_sha)
        for invalid in (
            document.replace("Task Type: STANDALONE MINOR BUG\n", ""),
            document.replace("Parent Slice: NONE", "Parent Slice: 27"),
            document.replace("Parent Slice: NONE\n", ""),
            document.replace("Task Type: STANDALONE MINOR BUG", "Task Type: UNKNOWN"),
        ):
            with self.subTest(document=invalid):
                write(repo, "TASK.md", invalid)
                result = run_check(repo)
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, "Task (Type|Parent Slice)")

    def test_standalone_bug_cannot_silently_displace_unclosed_slice(self) -> None:
        for status in ("ACTIVE", "FIX REQUIRED", "READY FOR A REVIEW"):
            with self.subTest(slice_status=status):
                repo, base_sha = init_repo(slice_status=status)
                write(repo, "TASK.md", standalone_task_document("PLANNED", base_sha))
                result = run_check(repo)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "standalone minor bug cannot replace an unclosed Slice", result.stderr
                )

    def test_standalone_bug_does_not_bypass_contract_checkpoint(self) -> None:
        repo, base_sha = init_repo(slice_status="PASS / CLOSED")
        write(repo, "TASK.md", standalone_task_document("PLANNED", base_sha))
        write(repo, "SLICE.md", slice_document(27, "ACTIVE", base_sha))
        result = run_check(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SLICE.md differs from HEAD", result.stderr)

    def test_standalone_bug_still_requires_consistent_roadmap(self) -> None:
        for status in ("PASS / CLOSED", "PLANNED"):
            with self.subTest(slice_status=status):
                repo, base_sha = init_repo(slice_status=status)
                write(repo, "TASK.md", standalone_task_document("PLANNED", base_sha))
                write(repo, "docs/roadmap.md", roadmap_document(27, "ACTIVE"))
                git(repo, "add", "docs/roadmap.md")
                git(repo, "commit", "-qm", "mismatched retained roadmap")
                result = run_check(repo)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"Roadmap Slice 27 must be {status}", result.stderr)

    def test_standalone_bug_does_not_hide_a_later_active_slice(self) -> None:
        repo, base_sha = init_repo(slice_status="PASS / CLOSED")
        write(repo, "TASK.md", standalone_task_document("PLANNED", base_sha))
        write(repo, "docs/roadmap.md", roadmap_document(27, "PASS / CLOSED", next_status="ACTIVE"))
        git(repo, "add", "docs/roadmap.md")
        git(repo, "commit", "-qm", "another active slice")
        result = run_check(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("next open Slice 28 must be PLANNED", result.stderr)

    def test_task_bases_must_be_full_existing_ancestor_commits_for_both_types(self) -> None:
        for standalone in (False, True):
            repo, base_sha = init_repo(slice_status="PASS / CLOSED" if standalone else "ACTIVE")
            unrelated = git(
                repo, "commit-tree", git(repo, "rev-parse", "HEAD^{tree}"), "-m", "root"
            )
            for invalid in (base_sha[:8], "0" * 40, unrelated):
                with self.subTest(standalone=standalone, task_base=invalid):
                    document = (
                        standalone_task_document("PLANNED", invalid)
                        if standalone
                        else task_document(27, "PLANNED", invalid)
                    )
                    write(repo, "TASK.md", document)
                    result = run_check(repo)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertRegex(result.stderr, "Task Base SHA|cat-file")

    def test_standalone_bug_rejects_unknown_status_and_missing_base(self) -> None:
        repo, base_sha = init_repo(slice_status="PASS / CLOSED")
        for invalid in (
            standalone_task_document("UNKNOWN", base_sha),
            standalone_task_document("PLANNED", base_sha).replace(f"Task Base: {base_sha}\n", ""),
        ):
            with self.subTest(document=invalid):
                write(repo, "TASK.md", invalid)
                result = run_check(repo)
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, "Task status|Task Base SHA")

    def test_explicit_slice_type_keeps_the_existing_parent_contract(self) -> None:
        repo, base_sha = init_repo()
        document = task_document(27, "PLANNED", base_sha).replace(
            "Task ID: 27.1", "Task ID: 27.1\nTask Type: SLICE"
        )
        write(repo, "TASK.md", document)
        result = run_check(repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        write(repo, "TASK.md", document.replace("Parent Slice: 27", "Parent Slice: NONE"))
        result = run_check(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Task Parent Slice", result.stderr)

    def test_closed_slice_still_cannot_authorize_a_slice_task(self) -> None:
        repo, base_sha = init_repo(slice_status="PASS / CLOSED")
        document = task_document(27, "PLANNED", base_sha)
        for declaration in ("", "Task Type: SLICE\n"):
            with self.subTest(declaration=declaration):
                write(
                    repo,
                    "TASK.md",
                    document.replace("Status: PLANNED", declaration + "Status: PLANNED"),
                )
                result = run_check(repo)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ACTIVE or FIX REQUIRED", result.stderr)


if __name__ == "__main__":
    unittest.main()
