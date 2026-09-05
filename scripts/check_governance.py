#!/usr/bin/env python3
"""Validate the committed Slice/Task/Roadmap governance state.

This check is intentionally read-only. It never stages, edits, resets, restores,
cleans, checks out, or stashes repository content.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
NO_ACTIVE_TASK = "NO ACTIVE IMPLEMENTATION TASK"
ACTIVE_TASK_STATUSES = {"PLANNED", "IN PROGRESS", "FIX REQUIRED", "READY FOR B REVIEW"}
SLICE_STATUSES = {"ACTIVE", "FIX REQUIRED", "READY FOR A REVIEW", "PASS / CLOSED"}


@dataclass(frozen=True)
class SliceState:
    slice_id: int
    status: str
    base_sha: str
    implementation_head: str


@dataclass(frozen=True)
class TaskState:
    active: bool
    status: str | None
    parent_slice: int | None
    task_base: str | None


@dataclass(frozen=True)
class RoadmapRow:
    slice_id: int
    status: str


def _first_match(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        raise ValueError(f"{label} is missing")
    return match.group(1).strip()


def parse_slice(text: str) -> SliceState:
    slice_id = int(_first_match(r"^Slice ID:\s*(\d+)\s*$", text, "Slice ID"))
    status = _first_match(r"^Status:\s*([^\n]+)$", text, "Slice status")
    base_sha = _first_match(r"^Base SHA:\s*([^\n]+)$", text, "Slice Base SHA")
    implementation_head = _first_match(
        r"^Implementation Head:\s*([^\n]+)$", text, "Slice Implementation Head"
    )
    if status not in SLICE_STATUSES:
        raise ValueError(f"unsupported Slice status: {status}")
    return SliceState(slice_id, status, base_sha, implementation_head)


def parse_task(text: str) -> TaskState:
    if text.lstrip().startswith("# NO ACTIVE IMPLEMENTATION TASK"):
        return TaskState(False, None, None, None)
    status = _first_match(r"^Status:\s*([^\n]+)$", text, "Task status")
    parent_match = re.search(r"^Parent Slice:\s*(\d+)\s*$", text, flags=re.MULTILINE)
    base_match = re.search(r"^Task Base:\s*([^\n]+)$", text, flags=re.MULTILINE)
    if parent_match is None:
        raise ValueError("Task Parent Slice is missing")
    if base_match is None:
        raise ValueError("Task Base SHA is missing")
    if status not in ACTIVE_TASK_STATUSES:
        raise ValueError(f"unsupported active Task status: {status}")
    return TaskState(True, status, int(parent_match.group(1)), base_match.group(1).strip())


def parse_roadmap(text: str) -> dict[int, RoadmapRow]:
    rows: dict[int, RoadmapRow] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        fields = [field.strip() for field in line.split("|")]
        if len(fields) < 4:
            continue
        match = re.match(r"^(\d+)(?:\.\d+)?\s+—", fields[1])
        if match is None:
            continue
        rows[int(match.group(1))] = RoadmapRow(int(match.group(1)), fields[3])
    if not rows:
        raise ValueError("Roadmap has no Slice rows")
    return rows


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _head_file(repo: Path, path: str) -> str:
    return _run_git(repo, "show", f"HEAD:{path}")


def _require_commit(repo: Path, sha: str, label: str) -> None:
    if not COMMIT_RE.fullmatch(sha):
        raise ValueError(f"{label} is not a full commit SHA: {sha}")
    _run_git(repo, "cat-file", "-e", f"{sha}^{{commit}}")


def _require_ancestor(repo: Path, ancestor: str, descendant: str, label: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"{label} {ancestor} is not an ancestor of {descendant}")


def _require_slice_lineage(repo: Path, slice_state: SliceState, head_sha: str) -> None:
    _require_commit(repo, slice_state.base_sha, "Slice Base SHA")
    _require_ancestor(repo, slice_state.base_sha, head_sha, "Slice Base SHA")
    if slice_state.implementation_head == "NOT SET":
        return
    _require_commit(repo, slice_state.implementation_head, "Slice Implementation Head")
    _require_ancestor(
        repo,
        slice_state.base_sha,
        slice_state.implementation_head,
        "Slice Base SHA",
    )


def _require_current_row(rows: dict[int, RoadmapRow], slice_state: SliceState) -> RoadmapRow:
    row = rows.get(slice_state.slice_id)
    if row is None:
        raise ValueError(f"Roadmap has no row for Slice {slice_state.slice_id}")
    return row


def _check_no_active_task(
    repo: Path,
    slice_state: SliceState,
    roadmap: dict[int, RoadmapRow],
) -> None:
    row = _require_current_row(roadmap, slice_state)
    if slice_state.status == "FIX REQUIRED":
        raise ValueError("Slice FIX REQUIRED cannot have NO ACTIVE IMPLEMENTATION TASK")
    if slice_state.status == "ACTIVE":
        if row.status != "ACTIVE":
            raise ValueError(f"Roadmap Slice {slice_state.slice_id} must be ACTIVE")
        return
    if slice_state.status == "READY FOR A REVIEW":
        if row.status not in {"PLANNED", "ACTIVE"}:
            raise ValueError(
                f"Roadmap Slice {slice_state.slice_id} has incompatible status {row.status}"
            )
        return
    if row.status != "PASS / CLOSED":
        raise ValueError(f"Roadmap Slice {slice_state.slice_id} must be PASS / CLOSED")
    open_rows = [row for row in roadmap.values() if row.slice_id > slice_state.slice_id]
    next_open = next(
        (
            row
            for row in sorted(open_rows, key=lambda item: item.slice_id)
            if row.status != "PASS / CLOSED"
        ),
        None,
    )
    if next_open is not None and next_open.status != "PLANNED":
        raise ValueError(f"next open Slice {next_open.slice_id} must be PLANNED")


def check_repository(repo: Path) -> None:
    repo = repo.resolve()
    head_sha = _run_git(repo, "rev-parse", "HEAD").strip()
    committed_slice_text = _head_file(repo, "SLICE.md")
    committed_roadmap_text = _head_file(repo, "docs/roadmap.md")
    working_slice_text = (repo / "SLICE.md").read_text(encoding="utf-8")
    working_task_text = (repo / "TASK.md").read_text(encoding="utf-8")

    # A Slice Contract must be checkpointed before any Task planning or execution.
    if working_slice_text != committed_slice_text:
        raise ValueError(
            "SLICE.md differs from HEAD; checkpoint the Slice Contract before planning or "
            "executing a Task"
        )

    slice_state = parse_slice(committed_slice_text)
    task_state = parse_task(working_task_text)
    roadmap = parse_roadmap(committed_roadmap_text)
    _require_slice_lineage(repo, slice_state, head_sha)

    if not task_state.active:
        _check_no_active_task(repo, slice_state, roadmap)
        return

    if slice_state.status != "ACTIVE":
        raise ValueError(
            f"active Task requires committed HEAD Slice {slice_state.slice_id} to be ACTIVE"
        )
    if task_state.parent_slice != slice_state.slice_id:
        raise ValueError(
            f"Task Parent Slice {task_state.parent_slice} does not match Slice "
            f"{slice_state.slice_id}"
        )
    row = _require_current_row(roadmap, slice_state)
    if row.status != "ACTIVE":
        raise ValueError(f"Roadmap Slice {slice_state.slice_id} must be ACTIVE")
    assert task_state.task_base is not None
    _require_commit(repo, task_state.task_base, "Task Base SHA")
    _require_ancestor(repo, task_state.task_base, head_sha, "Task Base SHA")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository root")
    args = parser.parse_args(argv)
    try:
        check_repository(args.repo)
    except (OSError, ValueError) as error:
        print(f"governance check failed: {error}", file=sys.stderr)
        return 1
    print("governance check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
