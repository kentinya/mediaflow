"""Selected-run detail, progress and operation evidence (Task 42.2).

Covers AC-T1–AC-T5 and AC-T7 through the real SQLite repository, the
application projections and the authenticated API on temporary databases:

- exact durable run/Task identity before and after Job→Task linkage,
- task-kind-specific progress whose mutually exclusive dispositions
  reconcile to the known total (and go honestly indeterminate when the
  discovery total is unknown),
- server-side item/record filters whose cursors are bound to the exact
  run/task, the submitted filters and the reading principal,
- one item's durable checkpoint/Result/plan/log evidence with exact links,
- the run-scoped truthful result package export through the existing
  export authority, and
- zero workflow/Storage side effects for every read.

Every test uses temporary SQLite and fake/local dependencies; no production
credential, Provider, Storage service or user media is ever required.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from datetime import timedelta
from pathlib import Path

from mediaflow.domain.automation import AutomationJobStatus
from mediaflow.domain.library import ScanMode
from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.domain.manual_scan import ManualScanScopeKind, ManualScanTask
from mediaflow.domain.media_evidence import EvidenceSection, PipelineEvidence
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.pagination import (
    CursorDirection,
    decode_directional_cursor,
    encode_cursor,
)
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_package_exchange import example_document, setup_api
from tests.test_operations_run_inventory import (
    NOW,
    OPERATOR,
    VIEWER,
    job,
    request,
    task,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TASK_BASE_SHA = "cf7099a478a203f3f29ac57ef5b8acc295aadaa9"

ADMIN = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
SILENT = ResolvedApiPrincipal("silent", "silent-token", frozenset())


def _item(
    task_id: str,
    item_id: str,
    status: TaskItemStatus,
    *,
    created_rank: int = 0,
    plan_id: str | None = None,
    library: str = "movies",
    stage: str = "organize",
    error: str | None = None,
) -> PersistentTaskItem:
    occurred = NOW + timedelta(minutes=created_rank)
    return PersistentTaskItem(
        item_id=item_id,
        task_id=task_id,
        storage_id="src",
        resource_library_id=library,
        source_path=f"src/{item_id}.mkv",
        source_display=f"src/{item_id}.mkv",
        status=status,
        stage=stage,
        attempts=1,
        created_at=occurred,
        updated_at=occurred,
        plan_id=plan_id,
        destination_storage_id="dst" if status is TaskItemStatus.SUCCESS else None,
        destination_path=f"Movies/{item_id}.mkv" if status is TaskItemStatus.SUCCESS else None,
        error=error,
    )


def _result(
    task_id: str,
    item_id: str,
    *,
    result_id: str | None = None,
    created_rank: int = 1,
    effect_certainty: str = "verified_complete",
    uncertain_effects: tuple[str, ...] = (),
    attachment_count: int = 0,
    operation: str = "MOVE",
    status: str = "success",
    error: str | None = None,
    recognition_type: str = "C",
    naming_policy_id: str = "A",
    classification_policy_id: str = "A",
) -> PersistentResultRecord:
    occurred = NOW + timedelta(minutes=created_rank)
    return PersistentResultRecord(
        result_id=result_id or f"result-{uuid.uuid4().hex[:12]}",
        task_id=task_id,
        item_id=item_id,
        source_storage_id="src",
        source_path=f"src/{item_id}.mkv",
        destination_storage_id="dst",
        destination_path=f"Movies/{item_id}.mkv",
        recognition_type=recognition_type,
        provider="tmdb",
        provider_id="101",
        metadata_policy_id="C",
        naming_policy_id=naming_policy_id,
        classification_policy_id=classification_policy_id,
        organize_policy_id="A",
        operation=operation,
        status=status,
        created_at=occurred,
        title="Sample Title",
        error=error,
        attachment_count=attachment_count,
        effect_certainty=effect_certainty,
        uncertain_effects=uncertain_effects,
    )


def _scan(
    task_id: str,
    *,
    status: PersistentTaskStatus = PersistentTaskStatus.RUNNING,
    reconciliation_complete: bool = False,
    errors: tuple[dict[str, object], ...] = (),
    progress: dict[str, int] | None = None,
) -> ManualScanTask:
    return ManualScanTask(
        task_id=task_id,
        scope_kind=ManualScanScopeKind.RESOURCE_LIBRARY,
        resource_library_id="source",
        mode=ScanMode.FULL,
        status=status,
        configuration_snapshot_id="snap-a",
        configuration_snapshot_digest="digest-a",
        created_at=NOW,
        updated_at=NOW,
        reconciliation_complete=reconciliation_complete,
        errors=errors,
        progress=progress or {},
    )


class _RunDetailApiTestCase(unittest.TestCase):
    """One real SQLite repository behind the authenticated run-detail API."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name, "runtime.sqlite3")
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        self.api = MediaFlowApi(self.repository, None, principals=(VIEWER, OPERATOR, ADMIN))
        self.silent_api = MediaFlowApi(self.repository, None, principals=(SILENT,))

    # -- helpers ------------------------------------------------------------

    def get(
        self,
        path: str,
        *,
        query: str = "",
        token: str = "viewer-token",
        api: MediaFlowApi | None = None,
    ) -> tuple[int, dict, list[str]]:
        return request(api or self.api, "GET", path, token=token, query=query)

    def raw(self) -> sqlite3.Connection:
        """A raw writer connection for fixture rows the object API cannot express."""

        connection = sqlite3.connect(str(self.database))
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        return connection

    def overview(self, run_id: str, **kwargs) -> tuple[int, dict]:
        code, body, _ = self.get(f"/api/v1/operations/runs/{run_id}", **kwargs)
        return code, body

    def seed_run(
        self,
        *,
        command: str = "organize",
        execute_authorized: bool = True,
        status: PersistentTaskStatus = PersistentTaskStatus.COMPLETED,
        total_items: int | None = None,
        linked_job: bool = False,
        library: str = "movies",
    ) -> tuple[str, str]:
        """Create one Task (+ optional linked Job) and return (run_id, task_id)."""

        task_id = f"task-{uuid.uuid4().hex[:10]}"
        record = dataclasses.replace(
            task(
                task_id,
                command=command,
                status=status,
                execute_authorized=execute_authorized,
            ),
            total_items=(
                total_items
                if total_items is not None
                else (0 if status is not PersistentTaskStatus.COMPLETED else 2)
            ),
        )
        if library != "movies":
            record = dataclasses.replace(record, scope_path=f"src/{library}")
        self.repository.create_task(record)
        run_id = task_id
        if linked_job:
            job_id = f"job-{uuid.uuid4().hex[:10]}"
            self.repository.create_job(job(job_id, task_id=task_id))
            run_id = job_id
        return run_id, task_id


class RunDetailJourneyTests(_RunDetailApiTestCase):
    """AC-T1: exact native detail for pre-Task, linked, standalone and both kinds."""

    def test_selected_run_detail_for_job_linked_task(self) -> None:
        run_id, task_id = self.seed_run(linked_job=True, status=PersistentTaskStatus.RUNNING)
        self.repository.upsert_item(
            _item(task_id, "item-1", TaskItemStatus.SUCCESS, created_rank=1)
        )
        self.repository.append_result(_result(task_id, "item-1"))

        # The run anchor is the Job; its detail names the exact linked Task.
        code, overview = self.overview(run_id)
        self.assertEqual(code, 200)
        self.assertEqual(overview["run_id"], run_id)
        self.assertEqual(overview["task_id"], task_id)
        self.assertIsNotNone(overview["progress"])
        self.assertTrue(overview["progress"]["available"])
        self.assertEqual(overview["sideEffects"], "none")

        # A supported Task detail identity resolves to the same run through
        # the persisted Job→Task link — never a manual or textual join.
        code, by_task = self.overview(task_id)
        self.assertEqual(code, 200)
        self.assertEqual(by_task["run_id"], run_id)
        self.assertEqual(by_task, overview)

        for segment in ("items", "records"):
            code, page, _ = self.get(f"/api/v1/operations/runs/{task_id}/{segment}")
            self.assertEqual(code, 200)
            self.assertEqual(page["run_id"], run_id)
            self.assertEqual(page["task_id"], task_id)

    def test_pre_task_admission_has_truthful_queue_state_and_unavailability(self) -> None:
        run_id = f"job-{uuid.uuid4().hex[:10]}"
        self.repository.create_job(job(run_id, status=AutomationJobStatus.PENDING))
        # A job-linked operational log exists even before the Task does.
        self.repository.append_operational_log(
            OperationalLogRecord(
                "log-pre-task",
                NOW,
                LogLevel.INFO,
                "workflow",
                "scan.started",
                job_id=run_id,
                status="pending",
            )
        )

        code, overview = self.overview(run_id)
        self.assertEqual(code, 200)
        self.assertIsNone(overview["task_id"])
        self.assertFalse(overview["progress"]["available"])
        self.assertIn("no linked Task", overview["progress"]["reason"])

        code, items, _ = self.get(f"/api/v1/operations/runs/{run_id}/items")
        self.assertEqual(code, 200)
        self.assertIsNone(items["task_id"])
        self.assertEqual(items["items"], [])
        self.assertFalse(items["truncated"])
        self.assertIn("no linked Task", items["unavailable"])
        self.assertEqual(items["sideEffects"], "none")

        # Records stay honest: only exactly job-linked evidence appears.
        code, records, _ = self.get(f"/api/v1/operations/runs/{run_id}/records")
        self.assertEqual(code, 200)
        self.assertEqual(records["matching_total"], 1)
        self.assertEqual(records["kind_counts"]["log"], 1)
        self.assertEqual(records["kind_counts"]["result"], 0)
        self.assertEqual(records["records"][0]["record_id"], "log:log-pre-task")

    def test_standalone_task_and_both_library_kinds_remain_inspectable(self) -> None:
        resource_run, resource_task = self.seed_run(command="preview")
        media_run, media_task = self.seed_run(
            command="media_organize:collection-1", library="media-collection"
        )
        self.repository.upsert_item(
            _item(resource_task, "r-item", TaskItemStatus.DRY_RUN, library="movies")
        )
        self.repository.upsert_item(
            _item(media_task, "m-item", TaskItemStatus.SUCCESS, library="media:collection")
        )

        code, resource = self.overview(resource_run)
        self.assertEqual(code, 200)
        self.assertEqual(resource["run_kind"], "task")
        self.assertEqual(resource["library_kind"], "resource")

        code, media = self.overview(media_run)
        self.assertEqual(code, 200)
        self.assertEqual(media["run_kind"], "task")
        self.assertEqual(media["library_kind"], "media")

        for run_id, item_id in ((resource_run, "r-item"), (media_run, "m-item")):
            code, page, _ = self.get(f"/api/v1/operations/runs/{run_id}/items")
            self.assertEqual(code, 200)
            self.assertEqual([row["item_id"] for row in page["items"]], [item_id])
            code, evidence, _ = self.get(f"/api/v1/operations/runs/{run_id}/items/{item_id}")
            self.assertEqual(code, 200)
            self.assertEqual(evidence["item"]["item_id"], item_id)

    def test_missing_and_disallowed_reads_stay_distinct(self) -> None:
        run_id, task_id = self.seed_run()
        unknown = "no-such-run"
        for path in (
            f"/api/v1/operations/runs/{unknown}",
            f"/api/v1/operations/runs/{unknown}/items",
            f"/api/v1/operations/runs/{unknown}/records",
            f"/api/v1/operations/runs/{unknown}/items/item-x",
        ):
            with self.subTest(path=path):
                code, body, _ = self.get(path)
                self.assertEqual(code, 404)
                self.assertEqual(body["error"]["code"], "not_found")

        # This runtime has no package-exchange service wired, so export is a
        # distinct, actionable 503 rather than a fabricated empty download.
        code, body, _ = self.get(f"/api/v1/operations/runs/{unknown}/export")
        self.assertEqual(code, 503)
        self.assertEqual(body["error"]["code"], "service_unavailable")

        # Write verbs are refused on every detail route.
        code, body, _ = request(self.api, "POST", f"/api/v1/operations/runs/{run_id}/items")
        self.assertEqual(code, 405)
        self.assertEqual(body["error"]["code"], "method_not_allowed")

        # Authentication and authorization stay backend-authoritative.
        for path in (
            f"/api/v1/operations/runs/{run_id}",
            f"/api/v1/operations/runs/{run_id}/items",
            f"/api/v1/operations/runs/{run_id}/records",
            f"/api/v1/operations/runs/{run_id}/items/item-x",
            f"/api/v1/operations/runs/{run_id}/export",
        ):
            with self.subTest(path=path, auth="anonymous"):
                code, body, _ = self.get(path, token="denied-token")
                self.assertEqual(code, 401)
            with self.subTest(path=path, auth="no-permissions"):
                code, body, _ = self.get(path, token="silent-token", api=self.silent_api)
                self.assertEqual(code, 403)
                self.assertEqual(body["error"]["code"], "forbidden")

    def test_existing_compatibility_detail_routes_still_answer(self) -> None:
        run_id, task_id = self.seed_run()
        self.repository.upsert_item(_item(task_id, "item-1", TaskItemStatus.SUCCESS))
        self.repository.append_result(_result(task_id, "item-1"))

        code, legacy, _ = self.get(f"/api/v1/tasks/{task_id}")
        self.assertEqual(code, 200)
        self.assertEqual(legacy["task_id"], task_id)
        self.assertEqual(len(legacy["items"]), 1)

        code, alias, _ = self.get(f"/api/v1/operations/tasks/{task_id}")
        self.assertEqual(code, 200)
        self.assertEqual(alias["task_id"], task_id)

        code, logs, _ = self.get("/api/v1/logs")
        self.assertEqual(code, 200)
        self.assertIn("items", logs)

        code, page, _ = self.get("/api/v1/operations/runs")
        self.assertEqual(code, 200)
        self.assertEqual(page["total"], 1)


class RunProgressAccountingTests(_RunDetailApiTestCase):
    """AC-T2: durable, reconcilable, task-kind-specific progress."""

    def test_progress_partition_reconciles_beyond_one_page(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.PARTIAL_SUCCESS, total_items=9)
        statuses = [
            TaskItemStatus.SUCCESS,
            TaskItemStatus.SUCCESS,
            TaskItemStatus.DRY_RUN,
            TaskItemStatus.FAILED,
            TaskItemStatus.PARTIAL,
            TaskItemStatus.SKIPPED,
            TaskItemStatus.IGNORED,
            TaskItemStatus.CANCELLED,
            TaskItemStatus.WAITING_CONFIRM,
        ]
        for index, status in enumerate(statuses):
            self.repository.upsert_item(_item(task_id, f"item-{index}", status, created_rank=index))

        code, overview = self.overview(run_id)
        self.assertEqual(code, 200)
        progress = overview["progress"]
        self.assertTrue(progress["available"])
        self.assertFalse(progress["indeterminate"])
        self.assertEqual(progress["known_total"], 9)
        self.assertEqual(sum(progress["dispositions"].values()), 9)
        self.assertEqual(progress["dispositions"]["success"], 3)
        self.assertEqual(progress["dispositions"]["failed_partial"], 2)
        self.assertEqual(progress["dispositions"]["waiting"], 1)
        self.assertEqual(progress["confirmed_success"], 3)
        self.assertEqual(progress["uncertain_success"], 0)
        # Processed counts everything that left pending/active — waiting and
        # terminal dispositions are processed states, so this is not a
        # success percentage.
        self.assertEqual(progress["processed"], 9)
        self.assertIn("success_means", progress)
        self.assertEqual(progress["sideEffects"], "none")

        # Beyond one page the same totals hold: the first item page is a
        # window, not the population.
        code, page, _ = self.get(f"/api/v1/operations/runs/{run_id}/items", query="limit=3")
        self.assertEqual(code, 200)
        self.assertEqual(len(page["items"]), 3)
        self.assertEqual(page["total"], 9)
        self.assertEqual(page["matching_total"], 9)
        self.assertEqual(sum(page["dispositions"].values()), 9)

    def test_uncertain_effect_success_is_never_claimed_as_success(self) -> None:
        run_id, task_id = self.seed_run(execute_authorized=True, total_items=3)
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))
        self.repository.upsert_item(_item(task_id, "item-1", TaskItemStatus.SUCCESS))
        self.repository.upsert_item(_item(task_id, "item-2", TaskItemStatus.SUCCESS))
        self.repository.append_result(
            _result(
                task_id,
                "item-0",
                effect_certainty="attempted_unverified",
                uncertain_effects=("mutation_outcome",),
            )
        )
        self.repository.append_result(
            _result(task_id, "item-1", effect_certainty="verified_complete")
        )

        code, overview = self.overview(run_id)
        self.assertEqual(code, 200)
        progress = overview["progress"]
        self.assertEqual(progress["dispositions"]["success"], 3)
        self.assertEqual(progress["uncertain_success"], 1)
        self.assertEqual(progress["confirmed_success"], 2)
        self.assertEqual(progress["effect_counts"].get("attempted_unverified"), 1)
        self.assertEqual(progress["effect_counts"].get("verified_complete"), 1)
        self.assertTrue(progress["results_complete"])

        # The latest Result decides: a verified follow-up clears the
        # uncertain annotation without rewriting history.
        self.repository.append_result(
            _result(task_id, "item-0", effect_certainty="verified_complete", created_rank=5)
        )
        code, overview = self.overview(run_id)
        progress = overview["progress"]
        self.assertEqual(progress["uncertain_success"], 0)
        self.assertEqual(progress["confirmed_success"], 3)

    def test_analysis_completion_is_not_organize_success(self) -> None:
        run_id, task_id = self.seed_run(command="preview", execute_authorized=False, total_items=1)
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.DRY_RUN))
        code, overview = self.overview(run_id)
        progress = overview["progress"]
        self.assertEqual(progress["kind"], "analysis")
        self.assertIn("不是整理成功", progress["success_means"])
        self.assertIn("零变更", progress["basis"])

        run_id, task_id = self.seed_run(command="organize", execute_authorized=True, total_items=1)
        self.repository.upsert_item(_item(task_id, "item-1", TaskItemStatus.SUCCESS))
        code, overview = self.overview(run_id)
        progress = overview["progress"]
        self.assertEqual(progress["kind"], "organize")
        self.assertIn("存储操作", progress["success_means"])

    def test_unknown_discovery_total_is_indeterminate(self) -> None:
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        record = dataclasses.replace(
            task(task_id, command="scan", status=PersistentTaskStatus.RUNNING),
            total_items=0,
        )
        self.repository.create_manual_scan(record, _scan(task_id, reconciliation_complete=False))
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))

        code, overview = self.overview(task_id)
        self.assertEqual(code, 200)
        progress = overview["progress"]
        self.assertTrue(progress["available"])
        self.assertTrue(progress["indeterminate"])
        self.assertIsNone(progress["known_total"])
        self.assertIsNone(progress["processed"])
        self.assertFalse(progress["scan_discovery_complete"])
        self.assertEqual(progress["kind"], "scan")
        # The already-known dispositions remain visible without a denominator.
        self.assertEqual(progress["dispositions"]["success"], 1)
        self.assertEqual(sum(progress["dispositions"].values()), 1)

        # Once discovery reconciles, the total becomes known and reconciles.
        connection = self.raw()
        connection.execute(
            "UPDATE manual_scan_tasks SET reconciliation_complete=1 WHERE task_id=?",
            (task_id,),
        )
        connection.commit()
        code, overview = self.overview(task_id)
        progress = overview["progress"]
        self.assertFalse(progress["indeterminate"])
        self.assertEqual(progress["known_total"], 1)
        self.assertTrue(progress["scan_discovery_complete"])

    def test_scan_errors_and_attachment_steps_stay_separate(self) -> None:
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        record = dataclasses.replace(
            task(task_id, command="scan", status=PersistentTaskStatus.PARTIAL_SUCCESS),
            total_items=1,
        )
        self.repository.create_manual_scan(
            record,
            _scan(
                task_id,
                status=PersistentTaskStatus.PARTIAL_SUCCESS,
                reconciliation_complete=True,
                errors=({"stage": "discovery"}, {"stage": "source"}),
                progress={"files_visited": 12, "candidates": 1},
            ),
        )
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))
        self.repository.append_result(_result(task_id, "item-0", attachment_count=4))

        code, overview = self.overview(task_id)
        progress = overview["progress"]
        self.assertEqual(progress["scan_errors"], 2)
        self.assertEqual(progress["attachment_steps"], 4)
        self.assertEqual(progress["scan_progress"]["files_visited"], 12)
        # Neither leaks into the primary-item partition.
        self.assertEqual(progress["known_total"], 1)
        self.assertEqual(sum(progress["dispositions"].values()), 1)
        self.assertEqual(progress["dispositions"]["success"], 1)

    def test_admitted_not_yet_materialized_items_publish_pending(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=5)
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))
        self.repository.upsert_item(_item(task_id, "item-1", TaskItemStatus.PENDING))

        code, overview = self.overview(run_id)
        progress = overview["progress"]
        self.assertFalse(progress["indeterminate"])
        self.assertEqual(progress["known_total"], 5)
        self.assertEqual(sum(progress["dispositions"].values()), 5)
        self.assertEqual(progress["dispositions"]["pending"], 4)
        self.assertEqual(progress["processed"], 1)

    def test_non_terminal_run_without_any_admission_is_indeterminate(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=0)
        code, overview = self.overview(run_id)
        progress = overview["progress"]
        self.assertTrue(progress["indeterminate"])
        self.assertIsNone(progress["known_total"])
        self.assertIsNone(progress["processed"])
        self.assertEqual(sum(progress["dispositions"].values()), 0)

    def test_accounting_basis_covers_every_current_task_family(self) -> None:
        from mediaflow.application.operations_lifecycle import run_accounting_basis

        expectations = {
            "scan": "scan",
            "preview": "analysis",
            "organize": "organize",
            "manual_organize": "organize",
            "files_transfer": "transfer",
            "files_direct_command": "direct",
            "files_delete": "direct",
            "recovery-continuation": "recovery",
            "retry": "recovery",
            "metadata-correction-continuation": "recovery",
            "media_files_transfer:collection-1": "transfer",
            "some-legacy-unknown-command": "task",
        }
        for command, kind in expectations.items():
            with self.subTest(command=command):
                derived, _unit, basis, success_means = run_accounting_basis(
                    command, execute_authorized=True, scan=False
                )
                self.assertEqual(derived, kind)
                self.assertTrue(basis)
                self.assertTrue(success_means)
        # A dry-run task (no execution authority) reports analysis success.
        derived, *_ = run_accounting_basis("organize", execute_authorized=False, scan=False)
        self.assertEqual(derived, "analysis")

    def test_legacy_unknown_status_still_reconciles(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=2)
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))
        self.repository.upsert_item(_item(task_id, "item-1", TaskItemStatus.FAILED))
        connection = self.raw()
        connection.execute(
            "UPDATE task_items SET status='legacy_unknown_state' WHERE item_id='item-1'"
        )
        connection.commit()

        code, overview = self.overview(run_id)
        progress = overview["progress"]
        # An unknown legacy status counts as failed/partial, never as a
        # silent drop or a fabricated success.
        self.assertEqual(progress["dispositions"]["failed_partial"], 1)
        self.assertEqual(sum(progress["dispositions"].values()), progress["known_total"])


class RunItemsQueryTests(_RunDetailApiTestCase):
    """AC-T3: server-side item filters, population totals, bound cursors."""

    def _seed_items(self, task_id: str, count: int = 12) -> list[str]:
        pattern = [
            TaskItemStatus.SUCCESS,
            TaskItemStatus.FAILED,
            TaskItemStatus.WAITING_METADATA,
            TaskItemStatus.PENDING,
        ]
        ids = []
        for index in range(count):
            item_id = f"item-{index:02d}"
            self.repository.upsert_item(
                _item(task_id, item_id, pattern[index % len(pattern)], created_rank=index)
            )
            ids.append(item_id)
        return ids

    def test_filtered_pages_are_server_side_and_totals_stay_page_independent(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=12)
        self._seed_items(task_id)

        code, first, _ = self.get(f"/api/v1/operations/runs/{run_id}/items", query="limit=5")
        self.assertEqual(code, 200)
        self.assertEqual(len(first["items"]), 5)
        self.assertTrue(first["truncated"])
        self.assertEqual(first["total"], 12)
        self.assertEqual(first["matching_total"], 12)
        self.assertEqual(sum(first["dispositions"].values()), 12)

        # A submitted disposition filter narrows the page but never the
        # reported population counts.
        code, filtered, _ = self.get(
            f"/api/v1/operations/runs/{run_id}/items",
            query="limit=5&status=waiting",
        )
        self.assertEqual(code, 200)
        self.assertEqual(filtered["matching_total"], 3)
        self.assertEqual(len(filtered["items"]), 3)
        self.assertEqual(sum(filtered["dispositions"].values()), 12)
        self.assertEqual(filtered["dispositions"]["waiting"], 3)
        # A successful sibling outside the filter stays visible in the counts.
        self.assertEqual(filtered["dispositions"]["success"], 3)

        # Paging with the filter keeps the same totals on every page.
        cursor = filtered["next_cursor"]
        self.assertIsNone(cursor)  # everything fitted one page
        code, second, _ = self.get(f"/api/v1/operations/runs/{run_id}/items", query="limit=4")
        self.assertEqual(len(second["items"]), 4)
        cursor = second["next_cursor"]
        self.assertIsNotNone(cursor)
        code, next_page, _ = self.get(
            f"/api/v1/operations/runs/{run_id}/items",
            query=f"limit=4&cursor={cursor}",
        )
        self.assertEqual(code, 200)
        self.assertEqual(len(next_page["items"]), 4)
        self.assertEqual(next_page["total"], 12)
        self.assertEqual(sum(next_page["dispositions"].values()), 12)
        second_ids = {row["item_id"] for row in second["items"]}
        next_ids = {row["item_id"] for row in next_page["items"]}
        self.assertFalse(second_ids & next_ids)

        # A previous cursor walks back without dropping siblings.
        previous = next_page["previous_cursor"]
        self.assertIsNotNone(previous)
        code, back, _ = self.get(
            f"/api/v1/operations/runs/{run_id}/items",
            query=f"limit=4&cursor={previous}",
        )
        self.assertEqual(code, 200)
        self.assertEqual(back["total"], 12)

    def test_item_cursors_bind_run_filter_and_principal(self) -> None:
        run_a, task_a = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=4)
        run_b, task_b = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=4)
        for index in range(4):
            self.repository.upsert_item(
                _item(task_a, f"a-{index}", TaskItemStatus.PENDING, created_rank=index)
            )
            self.repository.upsert_item(
                _item(task_b, f"b-{index}", TaskItemStatus.PENDING, created_rank=index)
            )

        code, page, _ = self.get(f"/api/v1/operations/runs/{run_a}/items", query="limit=2")
        self.assertEqual(code, 200)
        cursor = page["next_cursor"]
        self.assertIsNotNone(cursor)

        # The cursor is a scoped cursor: decoding without the exact scope is
        # refused outright.
        with self.assertRaises(ValueError):
            decode_directional_cursor(cursor, "run_items")

        # Cross-run replay is refused.
        code, body, _ = self.get(
            f"/api/v1/operations/runs/{run_b}/items", query=f"limit=2&cursor={cursor}"
        )
        self.assertEqual(code, 400)
        self.assertEqual(body["error"]["code"], "invalid_request")

        # Same run, different filter state is refused.
        code, body, _ = self.get(
            f"/api/v1/operations/runs/{run_a}/items",
            query=f"limit=2&cursor={cursor}&status=waiting",
        )
        self.assertEqual(code, 400)

        # A different reading principal is refused, the same one succeeds.
        code, body, _ = self.get(
            f"/api/v1/operations/runs/{run_a}/items",
            query=f"limit=2&cursor={cursor}",
            token="operator-token",
        )
        self.assertEqual(code, 400)
        code, replay, _ = self.get(
            f"/api/v1/operations/runs/{run_a}/items",
            query=f"limit=2&cursor={cursor}",
        )
        self.assertEqual(code, 200)
        self.assertEqual(len(replay["items"]), 2)

        # Malformed and foreign-kind cursors are refused too.
        code, body, _ = self.get(f"/api/v1/operations/runs/{run_a}/items", query="cursor=%25")
        self.assertEqual(code, 400)
        foreign = encode_cursor(
            "operations_runs", NOW, run_a, CursorDirection.NEXT, scope="principal=viewer"
        )
        code, body, _ = self.get(
            f"/api/v1/operations/runs/{run_a}/items", query=f"cursor={foreign}"
        )
        self.assertEqual(code, 400)

    def test_invalid_item_filters_and_limits_are_rejected(self) -> None:
        run_id, _task_id = self.seed_run()
        for query in (
            "status=bogus",
            "status=waiting&status=failed_partial",
            "limit=0",
            "limit=101",
            "limit=abc",
            "unknown=1",
            "cursor=abc&cursor=def",
        ):
            with self.subTest(query=query):
                code, body, _ = self.get(f"/api/v1/operations/runs/{run_id}/items", query=query)
                self.assertEqual(code, 400)
                self.assertEqual(body["error"]["code"], "invalid_request")

    def test_concurrent_transition_never_fabricates_totals(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=3)
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))
        self.repository.upsert_item(_item(task_id, "item-1", TaskItemStatus.PROCESSING))
        self.repository.upsert_item(_item(task_id, "item-2", TaskItemStatus.PENDING))

        code, page, _ = self.get(f"/api/v1/operations/runs/{run_id}/items", query="limit=2")
        self.assertEqual(page["dispositions"]["active"], 1)

        # A concurrent worker completes the active item between the reads.
        self.repository.upsert_item(_item(task_id, "item-1", TaskItemStatus.SUCCESS))

        cursor = page["next_cursor"]
        self.assertIsNotNone(cursor)
        code, next_page, _ = self.get(
            f"/api/v1/operations/runs/{run_id}/items",
            query=f"limit=2&cursor={cursor}",
        )
        self.assertEqual(code, 200)
        # The successful sibling is still present in the population and the
        # new counts reconcile to the same total.
        self.assertEqual(next_page["total"], 3)
        self.assertEqual(next_page["dispositions"]["success"], 2)
        self.assertEqual(sum(next_page["dispositions"].values()), 3)

    def test_restart_reopens_the_same_durable_item_truth(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=3)
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))
        self.repository.upsert_item(_item(task_id, "item-1", TaskItemStatus.FAILED))
        code, before, _ = self.get(f"/api/v1/operations/runs/{run_id}/items")
        self.assertEqual(code, 200)

        self.repository.close()
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        self.api = MediaFlowApi(self.repository, None, principals=(VIEWER, OPERATOR, ADMIN))

        code, after, _ = self.get(f"/api/v1/operations/runs/{run_id}/items")
        self.assertEqual(code, 200)
        self.assertEqual(after["dispositions"], before["dispositions"])
        self.assertEqual(after["total"], before["total"])


class RunRecordsQueryTests(_RunDetailApiTestCase):
    """AC-T4: exactly-linked operation records, bounded and server-paged."""

    def _seed_evidence(self, task_id: str, item_id: str, evidence_id: str) -> None:
        self.repository.append_evidence(
            PipelineEvidence(
                evidence_id=evidence_id,
                task_id=task_id,
                item_id=item_id,
                attempts=1,
                source_storage_id="src",
                source_path=f"src/{item_id}.mkv",
                captured_at=NOW + timedelta(minutes=2),
                configuration_snapshot_id="snap-a",
                configuration_snapshot_digest="digest-a",
                outcome="planned",
                sections={"plan": EvidenceSection(True, value={"operation": "MOVE"})},
            )
        )

    def test_records_union_uses_only_exact_persisted_links(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=1)
        self.repository.upsert_item(
            _item(task_id, "item-0", TaskItemStatus.FAILED, plan_id="plan-0")
        )
        self.repository.append_result(_result(task_id, "item-0"))
        self._seed_evidence(task_id, "item-0", "evidence-0")
        self.repository.append_operational_log(
            OperationalLogRecord(
                "log-a",
                NOW + timedelta(minutes=3),
                LogLevel.ERROR,
                "workflow",
                "workflow.failed",
                task_id=task_id,
                plan_id="plan-0",
                status="failed",
            )
        )
        connection = self.raw()
        connection.execute(
            "INSERT INTO task_retry_audit VALUES (?, ?, ?, ?, ?, ?)",
            ("retry-audit-0", task_id, "item-0", NOW.isoformat(), "operator", "note"),
        )
        connection.commit()

        # Another task's evidence shares a textually similar identity but must
        # never appear in this run's stream.
        other_task = f"task-{uuid.uuid4().hex[:10]}"
        self.repository.create_task(
            dataclasses.replace(task(other_task, command="preview"), total_items=1)
        )
        self.repository.upsert_item(_item(other_task, "item-0", TaskItemStatus.SUCCESS))
        self.repository.append_result(_result(other_task, "item-0", result_id="result-other"))
        self.repository.append_operational_log(
            OperationalLogRecord(
                "log-other",
                NOW + timedelta(minutes=4),
                LogLevel.INFO,
                "workflow",
                "workflow.failed",
                task_id=other_task,
                status="failed",
            )
        )

        code, records, _ = self.get(f"/api/v1/operations/runs/{run_id}/records")
        self.assertEqual(code, 200)
        self.assertEqual(records["matching_total"], 4)
        self.assertEqual(
            records["kind_counts"],
            {"result": 1, "evidence": 1, "log": 1, "audit": 1},
        )
        record_ids = {row["record_id"] for row in records["records"]}
        result_ids = [value for value in record_ids if value.startswith("result:")]
        self.assertEqual(len(result_ids), 1)
        self.assertNotIn("result-other", result_ids)
        self.assertFalse(any("log-other" in value for value in record_ids))
        log_row = next(r for r in records["records"] if r["kind"] == "log")
        self.assertEqual(log_row["level"], "ERROR")
        self.assertEqual(log_row["event"], "workflow.failed")
        self.assertEqual(log_row["plan_id"], "plan-0")
        audit_row = next(r for r in records["records"] if r["kind"] == "audit")
        self.assertEqual(audit_row["action"], "task_retry")
        self.assertEqual(audit_row["actor"], "operator")

    def test_kind_filter_counts_stay_page_independent_and_bound(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=3)
        for index in range(3):
            self.repository.upsert_item(
                _item(task_id, f"item-{index}", TaskItemStatus.SUCCESS, created_rank=index)
            )
            self.repository.append_result(_result(task_id, f"item-{index}"))
        for index in range(2):
            self.repository.append_operational_log(
                OperationalLogRecord(
                    f"log-{index}",
                    NOW + timedelta(minutes=5 + index),
                    LogLevel.INFO,
                    "workflow",
                    "organizer.execution_result",
                    task_id=task_id,
                    status="success",
                )
            )

        code, all_records, _ = self.get(
            f"/api/v1/operations/runs/{run_id}/records", query="limit=2"
        )
        self.assertEqual(code, 200)
        self.assertEqual(all_records["matching_total"], 5)
        self.assertEqual(all_records["kind_counts"]["result"], 3)
        self.assertEqual(all_records["kind_counts"]["log"], 2)
        self.assertTrue(all_records["truncated"])

        code, logs_only, _ = self.get(f"/api/v1/operations/runs/{run_id}/records", query="kind=log")
        self.assertEqual(code, 200)
        self.assertEqual(logs_only["matching_total"], 2)
        self.assertEqual(len(logs_only["records"]), 2)
        self.assertTrue(all(row["kind"] == "log" for row in logs_only["records"]))
        # The filtered page still reports the whole population's counts.
        self.assertEqual(logs_only["kind_counts"]["result"], 3)

        # A cursor minted under one kind filter is refused under another.
        cursor = all_records["next_cursor"]
        self.assertIsNotNone(cursor)
        code, body, _ = self.get(
            f"/api/v1/operations/runs/{run_id}/records",
            query=f"cursor={cursor}&kind=log",
        )
        self.assertEqual(code, 400)

        # And it is refused for another run or principal.
        other_run, other_task = self.seed_run(status=PersistentTaskStatus.RUNNING)
        code, body, _ = self.get(
            f"/api/v1/operations/runs/{other_run}/records", query=f"cursor={cursor}"
        )
        self.assertEqual(code, 400)
        code, body, _ = self.get(
            f"/api/v1/operations/runs/{run_id}/records",
            query=f"cursor={cursor}",
            token="operator-token",
        )
        self.assertEqual(code, 400)
        with self.assertRaises(ValueError):
            decode_directional_cursor(cursor, "run_records")

    def test_invalid_record_filters_are_rejected(self) -> None:
        run_id, _task_id = self.seed_run()
        for query in ("kind=bogus", "limit=0", "level=INFO", "status=waiting"):
            with self.subTest(query=query):
                code, body, _ = self.get(f"/api/v1/operations/runs/{run_id}/records", query=query)
                self.assertEqual(code, 400)

    def test_result_truth_is_independent_of_log_presence(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=1)
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))
        self.repository.append_result(_result(task_id, "item-0"))

        code, records, _ = self.get(f"/api/v1/operations/runs/{run_id}/records")
        self.assertEqual(code, 200)
        self.assertEqual(records["kind_counts"]["result"], 1)
        self.assertEqual(records["kind_counts"]["log"], 0)

        # The item evidence still presents the durable Result with an empty
        # log list — absent logs never erase a Result.
        code, evidence, _ = self.get(f"/api/v1/operations/runs/{run_id}/items/item-0")
        self.assertEqual(code, 200)
        self.assertEqual(len(evidence["results"]), 1)
        self.assertEqual(evidence["logs"], [])
        self.assertEqual(evidence["results"][0]["recognition_type"], "C")


class RunItemEvidenceTests(_RunDetailApiTestCase):
    """AC-T4: one item's checkpoint/Result/plan/log evidence through exact links."""

    def test_item_evidence_composes_all_durable_sources(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=1)
        self.repository.upsert_item(
            _item(task_id, "item-0", TaskItemStatus.FAILED, plan_id="plan-0")
        )
        self.repository.append_result(
            _result(task_id, "item-0", effect_certainty="attempted_unverified")
        )
        self.repository.append_evidence(
            PipelineEvidence(
                evidence_id="evidence-0",
                task_id=task_id,
                item_id="item-0",
                attempts=1,
                source_storage_id="src",
                source_path="src/item-0.mkv",
                captured_at=NOW + timedelta(minutes=2),
                configuration_snapshot_id="snap-a",
                configuration_snapshot_digest="digest-a",
                outcome="failed",
                sections={"operation": EvidenceSection(True, value={"kind": "MOVE"})},
            )
        )
        self.repository.append_operational_log(
            OperationalLogRecord(
                "log-plan-0",
                NOW + timedelta(minutes=3),
                LogLevel.ERROR,
                "workflow",
                "organizer.execution_result",
                task_id=task_id,
                plan_id="plan-0",
                status="failed",
            )
        )
        # A log for another plan must not attach to this item.
        self.repository.append_operational_log(
            OperationalLogRecord(
                "log-other-plan",
                NOW + timedelta(minutes=3),
                LogLevel.INFO,
                "workflow",
                "organizer.execution_result",
                task_id=task_id,
                plan_id="plan-other",
                status="success",
            )
        )

        code, evidence, _ = self.get(f"/api/v1/operations/runs/{run_id}/items/item-0")
        self.assertEqual(code, 200)
        self.assertEqual(evidence["item"]["item_id"], "item-0")
        self.assertEqual(evidence["item"]["task_id"], task_id)
        self.assertEqual(len(evidence["results"]), 1)
        self.assertEqual(evidence["results"][0]["effect_certainty"], "attempted_unverified")
        self.assertEqual(len(evidence["evidence"]), 1)
        self.assertEqual(evidence["evidence"][0]["outcome"], "failed")
        self.assertEqual([row["record_id"] for row in evidence["logs"]], ["log:log-plan-0"])
        self.assertEqual(evidence["checkpoint"]["item_id"], "item-0")
        self.assertEqual(evidence["sideEffects"], "none")

        serialized = json.dumps(evidence)
        self.assertNotIn("snapshot_digest", serialized)
        self.assertNotIn("configuration_snapshot_digest", serialized)
        self.assertNotIn("digest-a", serialized)
        self.assertNotIn("source_fingerprint", serialized)

    def test_item_evidence_rejects_foreign_and_missing_items(self) -> None:
        run_a, task_a = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=1)
        run_b, task_b = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=1)
        self.repository.upsert_item(_item(task_a, "item-a", TaskItemStatus.SUCCESS))
        self.repository.upsert_item(_item(task_b, "item-b", TaskItemStatus.SUCCESS))

        # Exact-link enforcement: run A cannot read run B's item.
        code, body, _ = self.get(f"/api/v1/operations/runs/{run_a}/items/item-b")
        self.assertEqual(code, 404)
        code, body, _ = self.get(f"/api/v1/operations/runs/{run_a}/items/missing")
        self.assertEqual(code, 404)

        # A pre-Task run has no item evidence at all.
        job_run = f"job-{uuid.uuid4().hex[:10]}"
        self.repository.create_job(job(job_run))
        code, body, _ = self.get(f"/api/v1/operations/runs/{job_run}/items/item-a")
        self.assertEqual(code, 404)

    def test_item_evidence_query_must_be_empty(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.RUNNING, total_items=1)
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))
        code, body, _ = self.get(f"/api/v1/operations/runs/{run_id}/items/item-0", query="limit=1")
        self.assertEqual(code, 400)


class RunExportTests(unittest.TestCase):
    """AC-T5: the run-scoped truthful result package export."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.api, self.service, self.repository, self.revision = setup_api(self.root)
        self.addCleanup(self.repository.close)
        self.silent_api = MediaFlowApi(
            self.repository,
            None,
            principals=(SILENT,),
            configuration_service=self.service,
            configuration_snapshot_id=self.revision.revision_id,
            configuration_snapshot_digest=self.revision.digest,
            bootstrap_document=example_document(self.root),
        )

    def _seed(self, *, result_count: int = 3, hostile: bool = False) -> tuple[str, str]:
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        self.repository.create_task(
            dataclasses.replace(
                task(
                    task_id,
                    command="preview",
                    status=PersistentTaskStatus.COMPLETED,
                    execute_authorized=False,
                ),
                total_items=1,
            )
        )
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.DRY_RUN))
        for index in range(result_count):
            self.repository.append_result(
                _result(
                    task_id,
                    "item-0",
                    result_id=f"result-{index}",
                    created_rank=index,
                    status="dry_run",
                    error=(
                        "Authorization: Bearer secret-token password=hunter2"
                        if hostile and index == 0
                        else None
                    ),
                )
            )
        return task_id, task_id

    def test_run_export_resolves_the_linked_task_and_matches_existing_package(self) -> None:
        task_id, run_id = self._seed(result_count=3)
        code, package, _ = request(
            self.api, "GET", f"/api/v1/operations/runs/{run_id}/export", query="limit=2"
        )
        self.assertEqual(code, 200)
        self.assertEqual(package["packageKind"], "mediaflow.results.v1")
        self.assertEqual(package["source"]["taskId"], task_id)
        self.assertEqual(len(package["results"]), 2)
        self.assertTrue(package["truncated"])
        self.assertEqual(package["warning"][0]["code"], "results_truncated")
        self.assertEqual([row["resultId"] for row in package["results"]], ["result-0", "result-1"])

        # The run-scoped route is the same authority as the legacy route:
        # identical package digest for the same scope and limit.
        code, legacy, _ = request(
            self.api,
            "GET",
            "/api/v1/configuration/packages/export/results",
            query=f"taskId={task_id}&limit=2",
        )
        self.assertEqual(code, 200)
        self.assertEqual(package["packageDigest"], legacy["packageDigest"])

        # Truthful truncation labeling travels with the package.
        code, full, _ = request(
            self.api, "GET", f"/api/v1/operations/runs/{run_id}/export", query="limit=5"
        )
        self.assertEqual(code, 200)
        self.assertFalse(full["truncated"])
        self.assertEqual(full["warning"], [])

    def test_export_of_a_pre_task_run_is_refused_not_empty(self) -> None:
        run_id = f"job-{uuid.uuid4().hex[:10]}"
        self.repository.create_job(job(run_id, status=AutomationJobStatus.PENDING))
        code, body, _ = request(self.api, "GET", f"/api/v1/operations/runs/{run_id}/export")
        self.assertEqual(code, 409)
        self.assertEqual(body["error"]["code"], "task_not_linked")

    def test_export_rejects_unknown_runs_and_invalid_limits(self) -> None:
        task_id, run_id = self._seed(result_count=1)
        code, body, _ = request(self.api, "GET", "/api/v1/operations/runs/missing/export")
        self.assertEqual(code, 404)
        for query in ("limit=0", "limit=501", "limit=abc", "taskId=other"):
            with self.subTest(query=query):
                code, body, _ = request(
                    self.api, "GET", f"/api/v1/operations/runs/{run_id}/export", query=query
                )
                self.assertIn(code, {400, 422})

    def test_export_requires_read_and_creates_no_work(self) -> None:
        task_id, run_id = self._seed(result_count=2)
        before = (
            len(self.repository.list_tasks(limit=100)),
            len(self.repository.list_results(task_id, limit=100)),
        )
        code, body, _ = request(
            self.silent_api,
            "GET",
            f"/api/v1/operations/runs/{run_id}/export",
            token="silent-token",
        )
        self.assertEqual(code, 403)

        code, package, _ = request(self.api, "GET", f"/api/v1/operations/runs/{run_id}/export")
        self.assertEqual(code, 200)
        after = (
            len(self.repository.list_tasks(limit=100)),
            len(self.repository.list_results(task_id, limit=100)),
        )
        self.assertEqual(before, after)

    def test_export_package_is_secret_free_and_digest_truthful(self) -> None:
        task_id, run_id = self._seed(result_count=2, hostile=True)
        code, package, _ = request(self.api, "GET", f"/api/v1/operations/runs/{run_id}/export")
        self.assertEqual(code, 200)
        encoded = json.dumps(package)
        self.assertNotIn("secret-token", encoded)
        self.assertNotIn("hunter2", encoded)
        self.assertIn("[redacted]", encoded)
        from mediaflow.domain.package_exchange import canonical_digest

        self.assertEqual(
            package["packageDigest"],
            canonical_digest({"results": package["results"], "source": package["source"]}),
        )
        # RecognitionType C and its A Naming/Classification policies survive
        # the export unchanged (C stays C).
        self.assertEqual(package["results"][0]["recognitionType"], "C")
        self.assertEqual(package["results"][0]["namingPolicyId"], "A")
        self.assertEqual(package["results"][0]["classificationPolicyId"], "A")


class RunDetailReadSafetyTests(_RunDetailApiTestCase):
    """AC-T7: reads admit no work, redact joined paths and keep compatibility."""

    def _seed_full_run(self) -> tuple[str, str]:
        run_id, task_id = self.seed_run(
            command="organize",
            execute_authorized=True,
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            total_items=2,
            linked_job=True,
        )
        self.repository.upsert_item(
            _item(task_id, "item-0", TaskItemStatus.SUCCESS, plan_id="plan-0")
        )
        self.repository.upsert_item(
            _item(task_id, "item-1", TaskItemStatus.FAILED, plan_id="plan-1")
        )
        self.repository.append_result(
            _result(
                task_id,
                "item-0",
                error="Authorization: Bearer leaked-token",
            )
        )
        self.repository.append_operational_log(
            OperationalLogRecord(
                "log-0",
                NOW + timedelta(minutes=2),
                LogLevel.INFO,
                "workflow",
                "organizer.execution_result",
                task_id=task_id,
                plan_id="plan-0",
                status="success",
            )
        )
        return run_id, task_id

    def _workflow_counts(self) -> dict[str, int]:
        connection = self.raw()
        tables = (
            "tasks",
            "task_items",
            "task_results",
            "automation_jobs",
            "operations_run_display",
            "pipeline_evidence",
            "operational_logs",
            "recovery_requests",
            "file_locks",
        )
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }

    def test_every_detail_read_is_side_effect_free(self) -> None:
        run_id, task_id = self._seed_full_run()
        before = self._workflow_counts()
        reads = [
            (f"/api/v1/operations/runs/{run_id}", ""),
            (f"/api/v1/operations/runs/{run_id}/items", ""),
            (f"/api/v1/operations/runs/{run_id}/items", "status=waiting"),
            (f"/api/v1/operations/runs/{run_id}/records", ""),
            (f"/api/v1/operations/runs/{run_id}/records", "kind=result"),
            (f"/api/v1/operations/runs/{run_id}/items/item-0", ""),
            (f"/api/v1/operations/runs/{task_id}", ""),
            (f"/api/v1/tasks/{task_id}", ""),
            ("/api/v1/logs", ""),
        ]
        for path, query in reads:
            with self.subTest(path=path, query=query):
                code, body, _ = self.get(path, query=query)
                self.assertEqual(code, 200)
                serialized = json.dumps(body)
                self.assertNotIn("leaked-token", serialized)
                if "operations/runs" in path:
                    # The bounded V2 run detail surfaces publish no
                    # configuration digest, no occurrence fingerprint and no
                    # raw error text.  (The V1 compatibility detail keeps its
                    # pre-existing document contract; it is not this Task's
                    # projection.)
                    self.assertEqual(body["sideEffects"], "none")
                    self.assertNotIn("snapshot_digest", serialized)
                    self.assertNotIn("fingerprint", serialized)
        after = self._workflow_counts()
        self.assertEqual(before, after)
        # Reading never acquires an execution lock.
        self.assertEqual(before["file_locks"], 0)

    def test_detail_reads_are_redacted_even_for_hostile_rows(self) -> None:
        run_id, task_id = self.seed_run(status=PersistentTaskStatus.FAILED, total_items=1)
        self.repository.upsert_item(
            _item(
                task_id,
                "item-0",
                TaskItemStatus.FAILED,
                error="password=hunter2 at /etc/secret/path",
            )
        )
        code, page, _ = self.get(f"/api/v1/operations/runs/{run_id}/items")
        self.assertEqual(code, 200)
        serialized = json.dumps(page)
        self.assertNotIn("hunter2", serialized)
        code, overview = self.overview(run_id)
        self.assertNotIn("hunter2", json.dumps(overview))

    def test_recognition_type_c_identity_survives_every_detail_read(self) -> None:
        run_id, task_id = self.seed_run(command="organize", execute_authorized=True, total_items=1)
        self.repository.upsert_item(_item(task_id, "item-0", TaskItemStatus.SUCCESS))
        self.repository.append_result(
            _result(
                task_id,
                "item-0",
                recognition_type="C",
                naming_policy_id="A",
                classification_policy_id="A",
            )
        )

        code, records, _ = self.get(f"/api/v1/operations/runs/{run_id}/records")
        result_row = next(row for row in records["records"] if row["kind"] == "result")
        self.assertEqual(result_row["result"]["recognition_type"], "C")
        self.assertEqual(result_row["result"]["naming_policy_id"], "A")
        self.assertEqual(result_row["result"]["classification_policy_id"], "A")

        code, evidence, _ = self.get(f"/api/v1/operations/runs/{run_id}/items/item-0")
        self.assertEqual(evidence["results"][0]["recognition_type"], "C")
        self.assertEqual(evidence["results"][0]["naming_policy_id"], "A")
        self.assertEqual(evidence["results"][0]["classification_policy_id"], "A")

    def test_audit_evidence_never_publishes_run_identifiers(self) -> None:
        run_id, task_id = self._seed_full_run()
        for path in (
            f"/api/v1/operations/runs/{run_id}",
            f"/api/v1/operations/runs/{run_id}/items",
            f"/api/v1/operations/runs/{run_id}/records",
            f"/api/v1/operations/runs/{run_id}/items/item-0",
        ):
            self.get(path)
        connection = self.raw()
        routes = [
            row[0]
            for row in connection.execute(
                "SELECT route FROM security_audit WHERE route LIKE '%runs%'"
            ).fetchall()
        ]
        self.assertTrue(routes)
        for route in routes:
            self.assertNotIn(run_id, route)
            self.assertNotIn(task_id, route)
            self.assertNotIn("item-0", route)


class RunDetailSchemaUpgradeTests(unittest.TestCase):
    """Additive Task-Base schema upgrade for the read journey."""

    def test_task_base_database_upgrades_in_place_with_truth_intact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_source = root / "task-base"
            base_source.mkdir()
            archive = subprocess.run(
                ["git", "archive", TASK_BASE_SHA],
                check=True,
                capture_output=True,
                cwd=REPOSITORY_ROOT,
            )
            subprocess.run(
                ["tar", "-x", "-C", str(base_source)],
                input=archive.stdout,
                check=True,
            )
            database = root / "runtime.sqlite3"
            # Create a genuine Task-Base (schema-41) database with the Base's
            # own code: pinned configuration, durable item and Result.
            script = (
                "import sys\n"
                "from datetime import UTC, datetime\n"
                "from mediaflow.infrastructure.sqlite_runtime import (\n"
                "    SQLiteTaskRepository, SCHEMA_VERSION,\n"
                ")\n"
                "from mediaflow.domain.task_persistence import (\n"
                "    PersistentTask, PersistentTaskStatus, PersistentTaskItem,\n"
                "    TaskItemStatus, PersistentResultRecord,\n"
                ")\n"
                f"assert SCHEMA_VERSION == {SCHEMA_VERSION - 1}, SCHEMA_VERSION\n"
                "NOW = datetime(2026, 1, 1, tzinfo=UTC)\n"
                "with SQLiteTaskRepository(sys.argv[1]) as repository:\n"
                "    repository.create_task(PersistentTask(\n"
                "        'base-task', 'organize', PersistentTaskStatus.COMPLETED, True,\n"
                "        NOW, NOW, NOW, NOW, 1, 1, 0, None, False, 'src/movies', None,\n"
                "        'snap-base', 'digest-base'))\n"
                "    repository.upsert_item(PersistentTaskItem(\n"
                "        'base-item', 'base-task', 'src', 'movies', 'src/one.mkv',\n"
                "        'src/one.mkv', TaskItemStatus.SUCCESS, 'organize', 1, NOW, NOW))\n"
                "    repository.append_result(PersistentResultRecord(\n"
                "        'base-result', 'base-task', 'base-item', 'src', 'src/one.mkv',\n"
                "        'dst', 'Movies/one.mkv', 'C', 'tmdb', '1', 'C', 'A', 'A', 'A',\n"
                "        'MOVE', 'success', NOW, title='Base'))\n"
                "print('base-schema-ready')\n"
            )
            completed = subprocess.run(
                [sys.executable, "-c", script, str(database)],
                cwd=base_source,
                env={**os.environ, "PYTHONPATH": str(base_source)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("base-schema-ready", completed.stdout)

            # The current code upgrades the Task-Base database in place.
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                task_record = repository.get_task("base-task")
                self.assertIsNotNone(task_record)
                assert task_record is not None
                self.assertEqual(task_record.configuration_snapshot_id, "snap-base")
                self.assertEqual(task_record.configuration_snapshot_digest, "digest-base")
                self.assertTrue(task_record.execute_authorized)
                self.assertEqual(task_record.status, PersistentTaskStatus.COMPLETED)
                items = repository.list_items("base-task")
                self.assertEqual([value.item_id for value in items], ["base-item"])
                results = repository.list_results("base-task")
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].recognition_type, "C")
                connection = repository._connection
                indexes = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='index'"
                    ).fetchall()
                }
                for expected in (
                    "task_items_task_created",
                    "task_results_task_created",
                    "operational_logs_task_time",
                    "operational_logs_plan_time",
                    "conflict_confirmations_task_created",
                ):
                    self.assertIn(expected, indexes)

                # The new detail reads work on the upgraded legacy data.
                overview, progress = repository.operations_run_with_progress("base-task")
                self.assertEqual(overview.run_id, "base-task")
                self.assertTrue(progress.available)
                self.assertEqual(progress.known_total, 1)
                self.assertEqual(progress.dispositions["success"], 1)
                window = repository.operations_run_items_window("base-task")
                self.assertEqual(window.total, 1)
                records = repository.operations_run_records_window("base-task", None)
                self.assertEqual(records.kind_counts["result"], 1)

            # A database newer than this code still fails closed.
            connection = sqlite3.connect(str(database))
            connection.execute(
                "UPDATE schema_version SET version=? WHERE component='runtime'",
                (SCHEMA_VERSION + 1,),
            )
            connection.commit()
            connection.close()
            with self.assertRaises(ValueError):
                SQLiteTaskRepository(database)


if __name__ == "__main__":
    unittest.main()
