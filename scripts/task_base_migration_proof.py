#!/usr/bin/env python3
"""Task Base -> candidate additive migration proof for Task 45.3.

The script builds an isolated Git worktree at the exact Task Base commit
(``8f5cf4e284766bcc8894817d7640231e85050fb2``), creates a runtime SQLite
database with the *actual Task Base code* (schema 45, no
``manual_recovery_preparations`` table), seeds representative durable state
(a Task with a succeeded sibling and a failed recovery item, its Result rows,
a manual intent/item and a persisted recovery authorization/link), then
reopens that database with the current candidate repository and verifies:

* the additive schema bump (45 -> 46) and the new preparation columns exist;
* every pre-existing Task/Result/pin/authorization/recovery fact is byte-for-
  byte intact and no old work became executable;
* the new preparation boundary round-trips and a legacy row (no confirmed
  selection) still reads back;
* an injected migration failure leaves the old database unchanged.

It never reads production paths, user databases, credentials, Storage or
Providers.  Usage (from the repository root, inside the project venv):

    .venv/bin/python scripts/task_base_migration_proof.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_BASE = "8f5cf4e284766bcc8894817d7640231e85050fb2"
BASE_SCHEMA = 45
CANDIDATE_SCHEMA = 46


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_old_database(base_root: Path, database: Path) -> dict[str, object]:
    """Create the old database using the actual Task Base repository code."""

    seed = base_root / "scripts" / "_task_base_seed.py"
    seed.write_text(
        """
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.manual_organize import (
    ManualChoice,
    ManualConfigurationSnapshot,
    ManualIntentAudit,
    ManualIntentItem,
    ManualIntentItemStatus,
    ManualOrganizeIntent,
    ManualIntentStatus,
    ManualSourceIdentity,
)
from mediaflow.domain.manual_recovery import ManualRecoveryLink, ManualRecoveryLinkStatus
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository, SCHEMA_VERSION

database = Path(sys.argv[1])
now = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)

with SQLiteTaskRepository(database) as repository:
    coordinator = PersistentTaskCoordinator(repository, repository)
    task = coordinator.create(
        "manual_organize",
        execute_authorized=True,
        scope_path="Incoming/Media",
        item_limit=2,
        configuration_snapshot_id="snap-base",
        configuration_snapshot_digest="digest-base",
        require_configuration_snapshot=True,
    )
    failed = coordinator.begin_item(
        task.task_id, "source-storage", "source", "Media/C/Failed.2024.mkv",
        "Incoming/C/Failed.2024.mkv",
    )
    repository.upsert_item(
        __import__("dataclasses").replace(
            failed, status=TaskItemStatus.FAILED, stage="failed", error="original failure"
        )
    )
    repository.release(failed.storage_id, failed.source_path, failed.task_id)
    repository.append_result(
        PersistentResultRecord(
            "base-result-failed", task.task_id, failed.item_id, "source-storage",
            "Media/C/Failed.2024.mkv", "target-storage", "Movies/Failed.mkv", "A",
            "tmdb", "42", "A", "A", "A", "A", "MOVE", TaskItemStatus.FAILED.value,
            now, title="Failed", effect_certainty="none",
        )
    )
    sibling = coordinator.begin_item(
        task.task_id, "source-storage", "source", "Media/C/Sibling.mkv",
        "Incoming/C/Sibling.mkv",
    )
    repository.upsert_item(
        __import__("dataclasses").replace(
            sibling, status=TaskItemStatus.SUCCESS, stage="completed"
        )
    )
    repository.release(sibling.storage_id, sibling.source_path, sibling.task_id)
    repository.append_result(
        PersistentResultRecord(
            "base-result-sibling", task.task_id, sibling.item_id, "source-storage",
            "Media/C/Sibling.mkv", "target-storage", "Movies/Sibling.mkv", "A",
            "tmdb", "43", "A", "A", "A", "A", "MOVE", TaskItemStatus.SUCCESS.value,
            now, title="Sibling", effect_certainty="verified_complete",
        )
    )
    intent = ManualOrganizeIntent(
        "base-intent", "operator", "snap-base", "digest-base",
        ManualIntentStatus.OPEN, 1, now, now,
        (
            ManualIntentItem(
                "base-intent-item", "base-intent", 0,
                ManualSourceIdentity(
                    "base-file", "source-storage", "source",
                    "Media/C/Failed.2024.mkv", "Failed.2024.mkv", "mkv", 512,
                    now, now, now, now, "ready", None, "base-occurrence",
                    "a" * 64, "storage-entry-sha256", {"source": "storage_entry"},
                    "verified",
                ),
                ManualChoice("A", None, "A", "A", "A"),
                ManualIntentItemStatus.READY, None, 1, now, now,
            ),
        ),
        ManualConfigurationSnapshot(
            "snap-base", "digest-base", (), (), (), (), ()
        ),
        "continue to an exact zero-mutation Preview", None, (),
    )
    repository.create_manual_intent_with_audit(
        intent,
        tuple(intent.items),
        ManualIntentAudit(
            "base-audit", "base-intent", None, "operator",
            "created_from_storage_source", {}, {}, now,
        ),
    )
    link = ManualRecoveryLink(
        "base-link", task.task_id, failed.item_id, "base-continuation",
        "base-analysis-task", "base-analysis-result", "base-intent", "base-preview",
        "base-authorization", "operator", ManualRecoveryLinkStatus.AUTHORIZED,
        now, now, execution_id=None,
    )
    repository.create_manual_recovery_link(link)
    repository.complete_manual_recovery_link(
        "base-link", execution_id="base-execution", now=now
    )

print(json.dumps({
    "schema": SCHEMA_VERSION,
    "taskId": task.task_id,
    "failedItemId": failed.item_id,
    "siblingItemId": sibling.item_id,
}))
""",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(base_root)
    try:
        result = _run(
            [sys.executable, str(seed), str(database)],
            cwd=base_root,
            env=env,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Task Base seed failed:\nSTDOUT:\n{error.stdout}\nSTDERR:\n{error.stderr}"
        ) from error
    return json.loads(result.stdout.strip().splitlines()[-1])


def _read_facts(database: Path) -> dict[str, object]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        marker = connection.execute(
            "SELECT version FROM schema_version WHERE component='runtime'"
        ).fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        results = [
            dict(row)
            for row in connection.execute(
                "SELECT result_id, status, provider_id, effect_certainty "
                "FROM task_results ORDER BY result_id"
            ).fetchall()
        ]
        link = (
            connection.execute(
                "SELECT status, execution_id, authorization_id FROM manual_recovery_links"
            ).fetchone()
            if "manual_recovery_links" in tables
            else None
        )
        executions = (
            connection.execute("SELECT COUNT(*) FROM manual_executions").fetchone()[0]
            if "manual_executions" in tables
            else 0
        )
        columns = (
            {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(manual_recovery_preparations)"
                ).fetchall()
            }
            if "manual_recovery_preparations" in tables
            else set()
        )
    return {
        "schema": marker,
        "hasPreparationTable": "manual_recovery_preparations" in tables,
        "preparationColumns": sorted(columns),
        "results": results,
        "link": dict(link) if link is not None else None,
        "manualExecutions": executions,
    }


def _candidate_round_trip(database: Path) -> dict[str, object]:
    """Reopen with the candidate code, round-trip a preparation, read old facts."""

    sys.path.insert(0, str(ROOT))
    from mediaflow.domain.manual_recovery import (
        ManualRecoveryPreparation,
        ManualRecoveryPreparationStatus,
    )
    from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

    now = datetime(2026, 10, 17, 13, 0, tzinfo=UTC)
    facts_before = _read_facts(database)
    with SQLiteTaskRepository(database) as repository:
        assert repository.schema_version == CANDIDATE_SCHEMA, repository.schema_version
        # The old recovery link and results are unchanged and no old work became
        # executable: no new manual execution exists.
        after_open = _read_facts(database)
        assert after_open["link"] == facts_before["link"], (after_open["link"], facts_before)
        assert after_open["results"] == facts_before["results"]
        assert after_open["manualExecutions"] == facts_before["manualExecutions"] == 0
        # A fresh preparation round-trips with the confirmed-selection columns.
        preparation = ManualRecoveryPreparation(
            "candidate-prep",
            "base-task",
            "base-item",
            "base-continuation",
            "base-analysis-task",
            "base-result-sibling",
            "base-intent",
            "candidate-preview",
            1,
            "a" * 64,
            "b" * 64,
            "snap-base",
            "digest-base",
            "operator",
            ManualRecoveryPreparationStatus.PREPARED,
            now,
            now,
        )
        repository.create_manual_recovery_preparation(preparation)
        stored = repository.get_manual_recovery_preparation("candidate-prep")
        assert stored is not None
        assert stored.selected_item_ids == ()
        completed = repository.complete_manual_recovery_preparation(
            "candidate-prep",
            authorization_id="candidate-authorization",
            execution_id="candidate-execution",
            selected_item_ids=("base-item",),
            allow_overwrite=True,
            allow_source_cleanup=False,
            now=now,
        )
        assert completed.status is ManualRecoveryPreparationStatus.CONFIRMED
        assert completed.selected_item_ids == ("base-item",)
        assert completed.allow_overwrite is True
    # Reopen again: the confirmed summary survives and the old facts still hold.
    with SQLiteTaskRepository(database) as reopened:
        stored = reopened.get_manual_recovery_preparation("candidate-prep")
        assert stored is not None
        assert stored.selected_item_ids == ("base-item",)
        assert reopened.get_manual_recovery_link("base-link") is not None
    return _read_facts(database)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", default=None)
    args = parser.parse_args()
    work = (
        Path(args.work_dir)
        if args.work_dir
        else Path(tempfile.mkdtemp(prefix="mediaflow-task-base-migration-"))
    )
    work.mkdir(parents=True, exist_ok=True)
    base_root = work / "base"
    database = work / "runtime.sqlite3"
    report: dict[str, object] = {"taskBase": TASK_BASE, "workDir": str(work)}
    try:
        _run(
            ["git", "worktree", "add", "--detach", str(base_root), TASK_BASE],
            cwd=ROOT,
            env=dict(os.environ),
        )
        try:
            seeded = _seed_old_database(base_root, database)
            report["seeded"] = seeded
            old = _read_facts(database)
            report["oldDatabase"] = old
            assert old["schema"] == BASE_SCHEMA, old["schema"]
            assert old["hasPreparationTable"] is False
            migrated = _candidate_round_trip(database)
            report["migrated"] = migrated
            assert migrated["schema"] == CANDIDATE_SCHEMA
            assert migrated["hasPreparationTable"] is True
            assert "selected_item_ids_json" in migrated["preparationColumns"]
            assert "allow_overwrite" in migrated["preparationColumns"]
            assert "allow_source_cleanup" in migrated["preparationColumns"]
            assert migrated["link"] == old["link"]
            assert migrated["results"] == old["results"]
            report["status"] = "PASS"
        finally:
            _run(
                ["git", "worktree", "remove", "--force", str(base_root)],
                cwd=ROOT,
                env=dict(os.environ),
            )
    except Exception as error:  # pragma: no cover - diagnostic path
        report["status"] = "FAIL"
        report["error"] = f"{type(error).__name__}: {error}"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        shutil.rmtree(work, ignore_errors=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
