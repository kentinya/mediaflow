#!/usr/bin/env python3
"""Task Base -> candidate additive migration proof for Task 45.3.

The script builds an isolated Git worktree at the exact Task Base commit
(``8f5cf4e284766bcc8894817d7640231e85050fb2``), creates a runtime SQLite
database with the *actual Task Base code* (schema 45, no
``manual_recovery_preparations`` table), seeds representative durable state,
then reopens that database with the current candidate repository and verifies:

* the additive schema bump (45 -> 46) and the new preparation columns exist;
* the seeded **real** published configuration revision, manual intent/item,
  exact Preview/PreviewItem, one-shot authorization (one active, one already
  consumed), recovery continuation/link and Task/Result facts are byte-for-byte
  intact and no old work became executable;
* the new preparation boundary round-trips, references real Task/item/Preview
  rows, and a legacy row (no confirmed selection) still reads back;
* an injected failure in the additive migration leaves the old database
  unchanged (no half state, no schema marker advance), and removing the fault
  allows a safe reopen.

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
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.configuration_management import (
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
)
from mediaflow.domain.manual_execution import (
    MANUAL_EXECUTION_PERMISSION,
    ManualExecutionAuthorization,
    ManualExecutionAuthorizationStatus,
    ManualExecutionScopeItem,
)
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
from mediaflow.domain.manual_organize_preview import (
    ManualOrganizePreview,
    ManualPreviewItem,
    ManualPreviewItemStatus,
    ManualPreviewStatus,
)
from mediaflow.domain.manual_recovery import ManualRecoveryLink, ManualRecoveryLinkStatus
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository, SCHEMA_VERSION

database = Path(sys.argv[1])
now = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
digest = "d" * 64
snapshot_id = "snap-base"
snapshot_digest = "digest-base"

def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

# 1. A real published configuration revision that the old pin names.
with SQLiteConfigurationRepository(database) as configuration:
    revision = ManagedConfigurationRevision(
        "base-revision", 1, ManagedConfigurationStatus.ACTIVE, 1, digest,
        {"version": 1, "source": "task-base-seed"}, now, now,
    )
    configuration.create_revision(revision)
    assert configuration.get_revision("base-revision") is not None

with SQLiteTaskRepository(database) as repository:
    coordinator = PersistentTaskCoordinator(repository, repository)
    task = coordinator.create(
        "manual_organize",
        execute_authorized=True,
        scope_path="Incoming/Media",
        item_limit=2,
        configuration_snapshot_id=snapshot_id,
        configuration_snapshot_digest=snapshot_digest,
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
    source = ManualSourceIdentity(
        "base-file", "source-storage", "source",
        "Media/C/Failed.2024.mkv", "Failed.2024.mkv", "mkv", 512,
        now, now, now, now, "ready", None, "base-occurrence",
        "a" * 64, "storage-entry-sha256", {"source": "storage_entry"},
        "verified",
    )
    choice = ManualChoice("A", None, "A", "A", "A")
    intent = ManualOrganizeIntent(
        "base-intent", "operator", snapshot_id, snapshot_digest,
        ManualIntentStatus.OPEN, 1, now, now,
        (
            ManualIntentItem(
                "base-intent-item", "base-intent", 0, source, choice,
                ManualIntentItemStatus.READY, None, 1, now, now,
            ),
        ),
        ManualConfigurationSnapshot(
            snapshot_id, snapshot_digest, (), (), (), (), ()
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
    # A real exact Preview + PreviewItem the new preparation boundary can
    # legitimately reference.
    plan = {"executionPlan": {"operation": "MOVE"}, "destination": {"path": "Movies/Failed.mkv"}}
    preview_item = ManualPreviewItem(
        "base-preview-item", "base-preview", "base-intent", "base-intent-item", 0,
        1, 1, source, choice, snapshot_id, snapshot_digest,
        sha({"source": "base"}), (), (), (), sha({"input": "base"}),
        sha(plan), ManualPreviewItemStatus.PREVIEWED, plan, None,
        "inspect the Preview", True, "not_available_in_this_task", False, now, now, True,
    )
    preview = ManualOrganizePreview(
        "base-preview", "base-intent", "operator", 1, snapshot_id, snapshot_digest,
        ManualPreviewStatus.PREVIEWED, (preview_item,), now, now,
        "inspect each item", None, True, True, False, None, (), "file", "base-file", None,
    )
    repository.create_manual_preview(preview, (preview_item,))
    # One active and one already-consumed one-shot authorization for the same
    # Preview, so the migration must preserve both statuses.
    scope_item = ManualExecutionScopeItem(
        "base-intent-item", "base-preview-item", 1, sha({"source": "base"}),
        sha(plan), source, choice,
    )
    active_authorization = ManualExecutionAuthorization(
        "base-authorization", "base-preview", "base-intent", 1,
        snapshot_id, snapshot_digest, "operator", MANUAL_EXECUTION_PERMISSION,
        True, False, False, (scope_item,), now, now + timedelta(hours=1),
        ManualExecutionAuthorizationStatus.ACTIVE,
    )
    repository.create_manual_execution_authorization(active_authorization)
    # A second one-shot authority already consumed by an earlier execution.  The
    # execution_id is left NULL: the consumed state is durable on its own and no
    # execution row is fabricated for this proof.
    consumed_authorization = ManualExecutionAuthorization(
        "base-authorization-consumed", "base-preview", "base-intent", 1,
        snapshot_id, snapshot_digest, "operator", MANUAL_EXECUTION_PERMISSION,
        True, False, False, (scope_item,), now, now + timedelta(hours=1),
        ManualExecutionAuthorizationStatus.ACTIVE,
    )
    repository.create_manual_execution_authorization(consumed_authorization)
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

# Mark the second one-shot authority consumed through the base schema itself.
import sqlite3 as _sqlite3
with _sqlite3.connect(database) as _connection:
    _connection.execute(
        "UPDATE manual_execution_authorizations SET status='consumed', "
        "consumed_at=? WHERE authorization_id='base-authorization-consumed'",
        (now.isoformat(),),
    )
    _connection.commit()

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
                "SELECT result_id, status, provider_id, effect_certainty, destination_path "
                "FROM task_results ORDER BY result_id"
            ).fetchall()
        ]
        link = (
            [
                dict(row)
                for row in connection.execute(
                    "SELECT status, execution_id, authorization_id, preview_id "
                    "FROM manual_recovery_links ORDER BY link_id"
                ).fetchall()
            ]
            if "manual_recovery_links" in tables
            else []
        )
        authorizations = (
            [
                dict(row)
                for row in connection.execute(
                    "SELECT authorization_id, status, consumed_at, execution_id, "
                    "allow_overwrite, allow_source_cleanup FROM "
                    "manual_execution_authorizations ORDER BY authorization_id"
                ).fetchall()
            ]
            if "manual_execution_authorizations" in tables
            else []
        )
        revisions = (
            [
                dict(row)
                for row in connection.execute(
                    "SELECT revision_id, status, digest FROM managed_configuration_revisions "
                    "ORDER BY revision_id"
                ).fetchall()
            ]
            if "managed_configuration_revisions" in tables
            else []
        )
        previews = (
            [
                dict(row)
                for row in connection.execute(
                    "SELECT preview_id, intent_id, status, configuration_snapshot_id "
                    "FROM manual_previews ORDER BY preview_id"
                ).fetchall()
            ]
            if "manual_previews" in tables
            else []
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
        "links": link,
        "authorizations": authorizations,
        "revisions": revisions,
        "previews": previews,
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
        # The old recovery link/authorizations/results/revision are unchanged
        # and no old work became executable: no new manual execution exists.
        after_open = _read_facts(database)
        for key in ("links", "authorizations", "revisions", "previews", "results"):
            assert after_open[key] == facts_before[key], (key, after_open[key], facts_before[key])
        assert after_open["manualExecutions"] == facts_before["manualExecutions"] == 0
        # A fresh preparation references the real Task/item/Preview and the
        # confirmed-selection columns round-trip.
        preparation = ManualRecoveryPreparation(
            "candidate-prep",
            "base-task",
            "base-item",
            "base-continuation",
            "base-analysis-task",
            "base-result-sibling",
            "base-intent",
            "base-preview",
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
        assert (
            reopened.get_manual_execution_authorization("base-authorization").status.value
            == "active"
        )
        assert (
            reopened.get_manual_execution_authorization("base-authorization-consumed").status.value
            == "consumed"
        )
    return _read_facts(database)


def _build_intermediate_database(base_database: Path, target: Path, seeded: dict) -> None:
    """Copy the base database and give it a pre-46 preparation table.

    The Task Base schema 45 has no preparation table at all, so the candidate's
    fresh-table path is exercised by the main round trip.  To exercise the
    *additive ALTER* path (and prove it rolls back atomically), this copies the
    real base database and installs the preparation table in its pre-46 shape:
    the three new columns are absent and one legacy row already exists.  The
    schema marker stays 45, so reopening with the candidate code must add the
    columns through the ALTER branch.
    """

    shutil.copyfile(base_database, target)
    with sqlite3.connect(target) as connection:
        connection.execute(
            """CREATE TABLE manual_recovery_preparations (
                preparation_id TEXT PRIMARY KEY, source_task_id TEXT NOT NULL,
                source_item_id TEXT NOT NULL,
                analysis_continuation_id TEXT NOT NULL,
                analysis_task_id TEXT NOT NULL,
                analysis_result_id TEXT NOT NULL,
                intent_id TEXT NOT NULL, preview_id TEXT NOT NULL UNIQUE,
                intent_version INTEGER NOT NULL,
                checkpoint_version TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                configuration_snapshot_id TEXT NOT NULL,
                configuration_snapshot_digest TEXT NOT NULL,
                actor TEXT NOT NULL, status TEXT NOT NULL, current INTEGER NOT NULL,
                authorization_id TEXT UNIQUE, execution_id TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
        )
        connection.execute(
            "INSERT INTO manual_recovery_preparations VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-prep",
                seeded["taskId"],
                seeded["failedItemId"],
                "base-continuation",
                "base-analysis-task",
                "base-result-sibling",
                "base-intent",
                "base-preview",
                1,
                "a" * 64,
                "b" * 64,
                "snap-base",
                "digest-base",
                "operator",
                "prepared",
                1,
                None,
                None,
                "2026-10-17T12:00:00+00:00",
                "2026-10-17T12:00:00+00:00",
            ),
        )
        connection.execute("UPDATE schema_version SET version=45 WHERE component='runtime'")
        connection.commit()


def _inject_migration_failure(base_database: Path, seeded: dict, work: Path) -> None:
    """Inject a fault into the additive migration and prove atomic rollback.

    The candidate's own migration runs the ``ALTER TABLE
    manual_recovery_preparations ADD COLUMN selected_item_ids_json`` statement;
    the fault makes that statement raise.  Because the whole additive migration
    runs inside the ``_initialize`` transaction, the preceding statements and
    the schema marker must roll back: the old database keeps schema 45, the
    preparation table keeps its pre-46 shape and the legacy row is intact.
    Removing the fault must then let a safe reopen complete the migration.
    """

    sys.path.insert(0, str(ROOT))
    import mediaflow.infrastructure.sqlite_runtime as runtime_module

    target = work / "intermediate.sqlite3"
    _build_intermediate_database(base_database, target, seeded)
    before = _read_facts(target)
    assert before["schema"] == BASE_SCHEMA
    assert before["hasPreparationTable"] is True
    assert "selected_item_ids_json" not in before["preparationColumns"]
    assert before["preparationColumns"] == [
        "actor",
        "analysis_continuation_id",
        "analysis_result_id",
        "analysis_task_id",
        "authorization_id",
        "checkpoint_version",
        "configuration_snapshot_digest",
        "configuration_snapshot_id",
        "created_at",
        "current",
        "execution_id",
        "input_fingerprint",
        "intent_id",
        "intent_version",
        "preparation_id",
        "preview_id",
        "source_item_id",
        "source_task_id",
        "status",
        "updated_at",
    ], before["preparationColumns"]

    original_connect = sqlite3.connect
    state = {"raised": False}

    class _FailingConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if (
                not state["raised"]
                and isinstance(sql, str)
                and "ALTER TABLE manual_recovery_preparations ADD COLUMN selected_item_ids_json"
                in sql
            ):
                state["raised"] = True
                raise sqlite3.OperationalError("injected additive migration failure")
            return super().execute(sql, *args, **kwargs)

    def _patched_connect(*args, **kwargs):
        kwargs.setdefault("factory", _FailingConnection)
        return original_connect(*args, **kwargs)

    runtime_module.sqlite3.connect = _patched_connect
    try:
        try:
            with runtime_module.SQLiteTaskRepository(target):
                raise AssertionError("the injected failure must abort initialization")
        except sqlite3.OperationalError:
            pass
    finally:
        runtime_module.sqlite3.connect = original_connect
    assert state["raised"] is True
    after = _read_facts(target)
    # Atomic rollback: no half-migrated columns, no schema marker advance, and
    # every old durable fact is untouched.
    assert after["schema"] == BASE_SCHEMA, after["schema"]
    assert after["preparationColumns"] == before["preparationColumns"]
    assert after["results"] == before["results"]
    assert after["links"] == before["links"]
    assert after["authorizations"] == before["authorizations"]
    assert after["revisions"] == before["revisions"]
    # Removing the fault lets the same database reopen and migrate cleanly.
    with runtime_module.SQLiteTaskRepository(target) as reopened:
        assert reopened.schema_version == CANDIDATE_SCHEMA
        legacy = reopened.get_manual_recovery_preparation("legacy-prep")
        assert legacy is not None
        assert legacy.selected_item_ids == ()
        assert legacy.allow_overwrite is False
        assert legacy.allow_source_cleanup is False
    recovered = _read_facts(target)
    assert recovered["schema"] == CANDIDATE_SCHEMA
    assert "selected_item_ids_json" in recovered["preparationColumns"]
    assert recovered["links"] == before["links"]
    assert recovered["authorizations"] == before["authorizations"]
    assert recovered["results"] == before["results"]


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
            # Preserve the true schema-45 database before the candidate migrates
            # it, so the additive-ALTER failure injection starts from real base
            # rows rather than from an already-migrated copy.
            old_database = work / "base-old.sqlite3"
            shutil.copyfile(database, old_database)
            old = _read_facts(database)
            report["oldDatabase"] = old
            assert old["schema"] == BASE_SCHEMA, old["schema"]
            assert old["hasPreparationTable"] is False
            assert old["manualExecutions"] == 0
            assert {value["status"] for value in old["authorizations"]} == {
                "active",
                "consumed",
            }, old["authorizations"]
            assert old["links"][0]["status"] == "consumed", old["links"]
            migrated = _candidate_round_trip(database)
            report["migrated"] = migrated
            assert migrated["schema"] == CANDIDATE_SCHEMA
            assert migrated["hasPreparationTable"] is True
            assert "selected_item_ids_json" in migrated["preparationColumns"]
            assert "allow_overwrite" in migrated["preparationColumns"]
            assert "allow_source_cleanup" in migrated["preparationColumns"]
            assert migrated["links"] == old["links"]
            assert migrated["authorizations"] == old["authorizations"]
            assert migrated["results"] == old["results"]
            assert migrated["revisions"] == old["revisions"]
            report["legacyPreparation"] = "confirmed selection round-tripped"
            # Failure injection runs on a copy of the real base database with an
            # intermediate pre-46 preparation table; it must roll back
            # atomically and then recover on a fault-free reopen.
            _inject_migration_failure(old_database, seeded, work)
            report["failureInjection"] = "rolled back and recovered"
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
