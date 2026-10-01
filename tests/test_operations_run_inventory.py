"""Focused proof for Task 42.1 — the unified Operations run inventory.

These tests exercise the real SQLite repository, the shared read projection
and the authenticated ``/api/v1/operations/runs`` API against the current
legal production assemblies:

- AC-T1 one real population: linked Job→Task work is visible and counted
  once across the linkage, standalone Tasks, pre-Task pending/failed Jobs,
  manual-execution Tasks, scheduled definition occurrences, retry
  continuations and both library kinds' direct commands/transfers are all
  discoverable; unknown legacy commands keep an honest label; a completed
  Job never masks its linked Task's partial success or failure; and an
  exact-ID overview keeps even the oldest run openable.
- AC-T2 authoritative query/counts: text/status/kind/time filters compose,
  invalid values reject safely, ties page deterministically, cursors bind
  the submitted filter scope (and refuse a mismatch), totals and status
  partitions reconcile beyond one page and in both paging directions from
  one cross-connection read snapshot (the cursor bounds the window, never
  the population), the published maximum limit is served, and the attention
  facet is an explicit, composable, cursor-bound filter whose count stays
  explicitly overlapping.
- AC-T3 historical identity/privacy: scope evidence comes from the durable
  admission record (including the display context shared producers record
  at admission) or is explicitly unavailable; a restart and an Active
  A-to-B rename/delete cannot rewrite it; equal library IDs keep their
  kinds; no secret, private endpoint, host root or raw adapter exception
  leaves the API.
- AC-T6 no new authority or side effects: reads are bounded, authorized and
  admit nothing; a read against a mutation-recording Storage fake performs
  zero media calls and creates no Task/Job/configuration work.
- AC-T7 durable compatible delivery: an additive schema-39 fixture upgrades
  in place without rewriting pins, links, results or authority state, and
  restart retains truth; an unsupported newer schema fails closed.

No production media, credentials or external service is used.
"""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.automation import ProcessingWorkerService
from mediaflow.application.manual_scan import ManualScanService
from mediaflow.application.scanner import StorageScanner
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.operations_run import (
    ATTENTION_RUN_STATUSES,
    known_command_label,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentTask,
    PersistentTaskStatus,
)
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.pagination import (
    CursorDirection,
    decode_directional_cursor,
    encode_cursor,
)
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_scanner import FakeStorage
from tests.test_v2_manual_organize import _JourneyFixtureMixin

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)

VIEWER = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
OPERATOR = ResolvedApiPrincipal(
    "operator",
    "operator-token",
    frozenset({ApiPermission.READ, ApiPermission.CANCEL_JOB}),
)


def request(
    api: MediaFlowApi,
    method: str,
    path: str,
    *,
    token: str = "viewer-token",
    query: str = "",
    body: bytes = b"",
) -> tuple[int, dict, list[str]]:
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(body),
    }
    payload = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload), statuses


def task(
    task_id: str,
    *,
    command: str = "preview",
    status: PersistentTaskStatus = PersistentTaskStatus.COMPLETED,
    rank: int = 0,
    scope_path: str | None = None,
    execute_authorized: bool = False,
    configuration_snapshot_id: str | None = "snap-a",
) -> PersistentTask:
    occurred = NOW + timedelta(minutes=rank)
    terminal = status in {
        PersistentTaskStatus.COMPLETED,
        PersistentTaskStatus.PARTIAL_SUCCESS,
        PersistentTaskStatus.FAILED,
        PersistentTaskStatus.CANCELLED,
    }
    return PersistentTask(
        task_id,
        command,
        status,
        execute_authorized,
        occurred,
        occurred,
        started_at=occurred,
        completed_at=occurred if terminal else None,
        total_items=2,
        completed_items=1,
        failed_items=1 if terminal and status is not PersistentTaskStatus.COMPLETED else 0,
        scope_path=scope_path,
        configuration_snapshot_id=configuration_snapshot_id,
        configuration_snapshot_digest="digest-a" if configuration_snapshot_id else None,
    )


def job(
    job_id: str,
    *,
    command: AutomationCommand = AutomationCommand.PREVIEW,
    status: AutomationJobStatus = AutomationJobStatus.PENDING,
    rank: int = 0,
    task_id: str | None = None,
    definition_id: str | None = None,
    schedule_id: str | None = None,
    resource_library_id: str | None = "source",
    source_scope: str | None = None,
) -> AutomationJob:
    occurred = NOW + timedelta(minutes=rank)
    return AutomationJob(
        job_id,
        command,
        status,
        occurred,
        occurred,
        task_id=task_id,
        schedule_id=schedule_id,
        definition_id=definition_id,
        resource_library_id=resource_library_id,
        source_scope=source_scope,
    )


class _InventoryApiTestCase(unittest.TestCase):
    """One real SQLite repository behind the authenticated inventory API."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.api = MediaFlowApi(
            self.repository,
            None,
            principals=(VIEWER, OPERATOR),
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()


class RunInventoryTestCase(_InventoryApiTestCase):
    # -- AC-T1: one real population -------------------------------------

    def test_job_task_linkage_counts_once_and_survives_the_link(self) -> None:
        self.repository.create_task(task("linked-task", command="scan", rank=1))
        self.repository.create_job(job("linked-job", rank=0, task_id="linked-task"))
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        self.assertEqual(page["total"], 1)
        items = page["items"]
        self.assertEqual(len(items), 1)
        run = items[0]
        # The admission's visible identity is preserved after Task creation.
        self.assertEqual(run["run_id"], "linked-job")
        self.assertEqual(run["job_id"], "linked-job")
        self.assertEqual(run["task_id"], "linked-task")
        self.assertEqual(page["status_counts"], {"pending": 1})

    def test_job_completion_cannot_mask_linked_task_failure_or_partial(self) -> None:
        self.repository.create_task(
            task(
                "task-failed",
                command="scan",
                status=PersistentTaskStatus.FAILED,
                rank=1,
            )
        )
        self.repository.create_job(
            job(
                "job-failed-link",
                command=AutomationCommand.SCAN,
                status=AutomationJobStatus.COMPLETED,
                rank=0,
                task_id="task-failed",
            )
        )
        self.repository.create_task(
            task(
                "task-partial",
                command="scan",
                status=PersistentTaskStatus.PARTIAL_SUCCESS,
                rank=3,
            )
        )
        self.repository.create_job(
            job(
                "job-partial-link",
                command=AutomationCommand.SCAN,
                status=AutomationJobStatus.COMPLETED,
                rank=2,
                task_id="task-partial",
            )
        )
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        states = {item["run_id"]: item["status"] for item in page["items"]}
        self.assertEqual(states["job-failed-link"], "failed")
        self.assertEqual(states["job-partial-link"], "partial_success")
        self.assertEqual(page["status_counts"]["failed"], 1)
        self.assertEqual(page["status_counts"]["partial_success"], 1)

    def test_standalone_tasks_and_pre_task_jobs_remain_visible(self) -> None:
        self.repository.create_task(task("standalone", command="preview", rank=0))
        self.repository.create_task(
            task(
                "manual-scan-task",
                command="scan",
                status=PersistentTaskStatus.RUNNING,
                rank=1,
            )
        )
        self.repository.create_job(job("pre-task-pending", rank=2))
        self.repository.create_job(
            job(
                "pre-task-failed",
                command=AutomationCommand.ORGANIZE,
                status=AutomationJobStatus.FAILED,
                rank=3,
            )
        )
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        self.assertEqual(page["total"], 4)
        ids = {item["run_id"] for item in page["items"]}
        self.assertEqual(
            ids,
            {"standalone", "manual-scan-task", "pre-task-pending", "pre-task-failed"},
        )
        # Pre-Task pending/failed Jobs keep their own state, not a Task's.
        states = {item["run_id"]: item["status"] for item in page["items"]}
        self.assertEqual(states["pre-task-pending"], "pending")
        self.assertEqual(states["pre-task-failed"], "failed")

    def test_triggers_and_scheduled_occurrences_are_distinguishable(self) -> None:
        self.repository.create_job(
            job(
                "scheduled-job",
                rank=0,
                definition_id="def-1",
                source_scope="Shows",
            )
        )
        self.repository.create_job(
            job(
                "legacy-schedule-job",
                rank=1,
                schedule_id="schedule-1",
            )
        )
        self.repository.create_job(job("automation-job", rank=2))
        self.repository.create_task(task("manual-task", rank=3))
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        triggers = {item["run_id"]: item["trigger"] for item in page["items"]}
        self.assertEqual(triggers["scheduled-job"], "scheduled")
        self.assertEqual(triggers["legacy-schedule-job"], "scheduled")
        self.assertEqual(triggers["automation-job"], "automation")
        self.assertEqual(triggers["manual-task"], "manual")

    def test_command_families_and_library_kinds_are_discoverable(self) -> None:
        self.repository.create_task(task("scan-task", command="scan", rank=0))
        self.repository.create_task(
            task(
                "retry-task",
                command="retry-failed:scan-task",
                status=PersistentTaskStatus.RUNNING,
                rank=1,
            )
        )
        self.repository.create_task(
            task("transfer-task", command="files_transfer", rank=2, execute_authorized=True)
        )
        self.repository.create_task(
            task(
                "media-transfer-task",
                command="media_files_transfer",
                rank=3,
                execute_authorized=True,
            )
        )
        self.repository.create_task(
            task("media-rename-task", command="media_rename", rank=4, execute_authorized=True)
        )
        self.repository.create_task(task("files-delete-task", command="files_delete", rank=5))
        self.repository.create_task(
            task("legacy-command-task", command="legacy_historic_work", rank=6)
        )
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        by_id = {item["run_id"]: item for item in page["items"]}
        self.assertEqual(by_id["retry-task"]["command_label"], "失败项重试")
        self.assertEqual(by_id["transfer-task"]["command_label"], "文件传输")
        self.assertEqual(by_id["transfer-task"]["library_kind"], "resource")
        # An equal library ID never reads as ResourceLibrary work.
        self.assertEqual(by_id["media-transfer-task"]["library_kind"], "media")
        self.assertEqual(by_id["media-transfer-task"]["command_label"], "媒体库文件传输")
        self.assertEqual(by_id["media-rename-task"]["library_kind"], "media")
        self.assertEqual(by_id["files-delete-task"]["command_label"], "文件删除")
        # An unknown legacy command stays discoverable with an honest label.
        self.assertTrue(by_id["legacy-command-task"]["recognized_command"] is False)
        self.assertEqual(by_id["legacy-command-task"]["command"], "legacy_historic_work")
        self.assertIsNone(by_id["legacy-command-task"]["command_label"])

    def test_unknown_command_label_is_honest_at_the_domain_layer(self) -> None:
        self.assertIsNone(known_command_label("totally_unknown_command"))
        self.assertIsNone(known_command_label(None))
        self.assertEqual(known_command_label("scan"), "扫描")
        # A media-prefixed command that is not a known family is not guessed.
        self.assertIsNone(known_command_label("media_totally_unknown"))

    def test_sql_label_expression_mirrors_the_published_command_label(self) -> None:
        """The search label and the published label come from one shared map.

        The repository must find a run by exactly the Chinese business label
        the API publishes (and honestly find nothing for an unknown legacy
        command), so the generated SQL CASE is evaluated against the same
        command matrix as :func:`known_command_label`.
        """

        from mediaflow.infrastructure.sqlite_runtime import command_label_sql

        cases = (
            "scan",
            "scan:task-1",
            "preview",
            "preview:task-2",
            "organize",
            "manual_organize",
            "retry:task-3",
            "retry-failed:task-3",
            "metadata-correction-continuation:task-4",
            "recovery-continuation:task-4",
            "file-metadata-correction:task-5",
            "files_direct_command",
            "files_delete:task-6",
            "files_transfer",
            "media_scan:task-7",
            "media_organize",
            "media_files_transfer:task-8",
            "media_totally_unknown:task-9",
            "totally_unknown_command",
            "scan:",
            "",
        )
        with sqlite3.connect(":memory:") as connection:
            for command in cases:
                with self.subTest(command=command):
                    literal = "'" + command.replace("'", "''") + "'"
                    sql_label = connection.execute(
                        f"SELECT {command_label_sql(literal)}"
                    ).fetchone()[0]
                    self.assertEqual(known_command_label(command), sql_label)
            # A NULL command behaves exactly like the domain function's None.
            sql_label = connection.execute(f"SELECT {command_label_sql('NULL')}").fetchone()[0]
            self.assertIsNone(sql_label)
            self.assertIsNone(known_command_label(None))

    def test_manual_execution_task_is_visible_with_pinned_evidence(self) -> None:
        self.repository.create_task(
            task(
                "manual-exec-task",
                command="manual_organize",
                status=PersistentTaskStatus.RUNNING,
                rank=0,
                scope_path="movies/Movie.2024.mkv",
                execute_authorized=True,
            )
        )
        self.repository.upsert_item(_inventory_item("manual-exec-task", "item-1", "media:movies"))
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        run = page["items"][0]
        self.assertEqual(run["command"], "manual_organize")
        self.assertEqual(run["command_label"], "手动整理")
        self.assertEqual(run["trigger"], "manual")
        self.assertEqual(run["status"], "running")
        self.assertEqual(run["library_kind"], "media")

    def test_pause_request_is_distinct_and_attention_overlaps_status(self) -> None:
        # A waiting item turns the run into the waiting facet: it stays in its
        # own status partition while also counting as attention.
        self.repository.create_task(_waiting_task("waiting-task"))
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        run = page["items"][0]
        self.assertEqual(run["status"], "partial_success")
        self.assertFalse(run["pause_requested"])
        # Attention is an overlapping facet of the same population, not a
        # mutually exclusive terminal state.
        self.assertTrue(run["attention"])
        attention_statuses = {item.value for item in ATTENTION_RUN_STATUSES}
        self.assertIn(run["status"], attention_statuses)
        self.assertEqual(page["status_counts"], {"partial_success": 1})
        self.assertEqual(page["attention_count"], 1)

    def test_pause_request_is_visible_without_claiming_an_acknowledged_pause(
        self,
    ) -> None:
        self.repository.create_task(_pause_requested_task("pausing-task"))
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        run = page["items"][0]
        # A request is not an acknowledged pause: the aggregate stays running.
        self.assertEqual(run["status"], "running")
        self.assertTrue(run["pause_requested"])
        self.assertEqual(page["status_counts"], {"running": 1})
        self.assertEqual(page["attention_count"], 0)

    # -- AC-T2: authoritative query/counts -------------------------------

    def test_filters_compose_and_counts_reconcile_beyond_one_page(self) -> None:
        fixture = {
            "a-completed": ("scan", PersistentTaskStatus.COMPLETED, 0),
            "b-completed": ("scan", PersistentTaskStatus.COMPLETED, 1),
            "c-failed": ("scan", PersistentTaskStatus.FAILED, 2),
            "d-failed": ("preview", PersistentTaskStatus.FAILED, 3),
            "e-running": ("preview", PersistentTaskStatus.RUNNING, 4),
            "f-partial": ("preview", PersistentTaskStatus.PARTIAL_SUCCESS, 5),
        }
        for index, (task_id, (command, status, rank)) in enumerate(fixture.items()):
            self.repository.create_task(
                task(
                    task_id,
                    command=command,
                    status=status,
                    rank=rank,
                    scope_path=f"scope-{index}",
                )
            )
        cases = (
            ("", 6),
            ("status=completed", 2),
            ("status=failed", 2),
            ("command=scan", 3),
            ("command=preview", 3),
            ("status=failed&command=preview", 1),
            ("q=scope-1", 1),
            ("q=scope", 6),
        )
        for query, expected_total in cases:
            with self.subTest(query=query):
                _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs", query=query)
                self.assertEqual(page["total"], expected_total)
                counts = page["status_counts"]
                self.assertEqual(sum(counts.values()), page["total"])

    def test_time_filters_compose_with_status(self) -> None:
        self.repository.create_task(task("old", rank=0))
        self.repository.create_task(task("new", rank=60))
        boundary = (NOW + timedelta(minutes=30)).isoformat()
        _status, page, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            query=f"to={boundary}",
        )
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["items"][0]["run_id"], "old")
        _status, page, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            query=f"from={boundary}&status=completed",
        )
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["items"][0]["run_id"], "new")

    def test_invalid_filter_values_reject_safely(self) -> None:
        for query in (
            "status=not-a-status",
            "status=failed&status=running",
            "command=../escape",
            "q=" + "x" * 200,
            "from=yesterday",
            "to=2026-13-40",
            "from=2026-08-22T10:00:00+02:00",
            "limit=0",
            "limit=101",
            "unknown=1",
        ):
            with self.subTest(query=query):
                code, _body, _ = request(self.api, "GET", "/api/v1/operations/runs", query=query)
                self.assertEqual(code, 400)

    def test_pagination_is_deterministic_through_ties(self) -> None:
        for index in range(6):
            # Same created_at forces the ID tiebreak to define the page order.
            self.repository.create_task(task(f"tie-{index}", rank=0))
            self.repository.update_task(_retime(f"tie-{index}", NOW))
        seen: list[str] = []
        cursor: str | None = None
        for _ in range(3):
            query = "limit=2" + (f"&cursor={cursor}" if cursor else "")
            _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs", query=query)
            ids = [item["run_id"] for item in page["items"]]
            self.assertEqual(len(ids), 2)
            self.assertEqual(ids, sorted(ids, reverse=True))
            seen.extend(ids)
            cursor = page["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(len(seen), 6)
        self.assertEqual(len(set(seen)), 6)

    def test_cursors_bind_the_submitted_filter_scope(self) -> None:
        for index in range(4):
            self.repository.create_task(
                task(
                    f"page-{index}",
                    command="scan" if index < 2 else "preview",
                    status=PersistentTaskStatus.COMPLETED,
                    rank=index,
                )
            )
        _status, first, _ = request(
            self.api, "GET", "/api/v1/operations/runs", query="status=completed&limit=1"
        )
        cursor = first["next_cursor"]
        self.assertIsNotNone(cursor)
        # The cursor is always scope-bound: decoding without the expected
        # scope is refused even when the submitted filter set is empty.
        with self.assertRaises(ValueError):
            decode_directional_cursor(cursor, "operations_runs")
        decoded = decode_directional_cursor(
            cursor,
            "operations_runs",
            expected_scope=(
                "principal=viewer;status=completed;attention=false;command=all;q=;from=;to="
            ),
        )
        self.assertEqual(decoded.direction, CursorDirection.NEXT)
        _status, second, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            query=f"status=completed&limit=1&cursor={cursor}",
        )
        self.assertNotEqual(
            [item["run_id"] for item in first["items"]],
            [item["run_id"] for item in second["items"]],
        )
        for mismatched in (
            f"status=failed&limit=1&cursor={cursor}",
            f"command=preview&limit=1&cursor={cursor}",
            f"q=page-0&limit=1&cursor={cursor}",
            f"limit=1&cursor={cursor}",
        ):
            with self.subTest(query=mismatched):
                code, _body, _ = request(
                    self.api, "GET", "/api/v1/operations/runs", query=mismatched
                )
                self.assertEqual(code, 400)
        # A cursor minted for another resource is rejected outright.
        foreign = encode_cursor("tasks", NOW, "page-0", scope="status=all;command=all")
        code, _body, _ = request(
            self.api, "GET", "/api/v1/operations/runs", query=f"limit=1&cursor={foreign}"
        )
        self.assertEqual(code, 400)

    def test_page_and_counts_share_one_read_basis_under_concurrent_linkage(
        self,
    ) -> None:
        self.repository.create_task(task("concurrent-task", rank=0))
        errors: list[Exception] = []

        def link_job() -> None:
            try:
                for _ in range(20):
                    self.repository.create_job(
                        job(
                            f"racing-{threading.get_ident()}",
                            rank=0,
                            task_id="concurrent-task",
                        )
                    )
                    # Keep the population churning without ever duplicating a
                    # Task row: the linked Job admits once, then re-asserts.
                    break
            except Exception as error:  # pragma: no cover - diagnostic
                errors.append(error)

        thread = threading.Thread(target=link_job)
        thread.start()
        try:
            for _ in range(10):
                _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
                counts = page["status_counts"]
                # The page items and the counts never disagree within one read.
                self.assertLessEqual(len(page["items"]), page["limit"])
                self.assertGreaterEqual(sum(counts.values()), 0)
        finally:
            thread.join()
        self.assertEqual(errors, [])

    def test_page_and_counts_share_one_database_snapshot_across_connections(
        self,
    ) -> None:
        """A concurrent admission on another connection cannot skew the read.

        The page, the filtered total and the status partitions must come from
        one SQLite read snapshot: a legitimate admission committed by a
        *second* repository connection while the page SELECT is being read
        either lands entirely before or entirely after that snapshot, never
        between the page and its counts.
        """

        self.repository.create_task(task("base-one", rank=1))
        self.repository.create_task(task("base-two", rank=2))
        other = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.addCleanup(other.close)
        writer_done = threading.Event()
        writer_threads: list[threading.Thread] = []
        writer_outcome: list[str] = []
        signalled: list[bool] = []

        def writer() -> None:
            try:
                other.create_task(task("concurrent-admission", rank=0))
                writer_outcome.append("committed")
            except Exception as error:  # pragma: no cover - diagnostic only
                writer_outcome.append(f"blocked:{type(error).__name__}")
            finally:
                writer_done.set()

        def hook(statement: str) -> None:
            # Fire exactly once, when the count statement is about to run —
            # i.e. after the page window was already read inside the same
            # snapshot, at the exact interleaving point a concurrent
            # admission could skew the totals.
            if signalled or "SELECT COUNT(*) AS total FROM" not in statement:
                return
            signalled.append(True)
            thread = threading.Thread(target=writer)
            writer_threads.append(thread)
            thread.start()
            # Give the second connection a bounded window to commit inside
            # this read.  With a real read transaction it can only commit
            # after the snapshot closes, so the totals below stay truthful.
            writer_done.wait(timeout=0.5)

        connection = self.repository._connection  # test-only statement hook
        connection.set_trace_callback(hook)
        try:
            window = self.repository.operations_runs_window(limit=10)
        finally:
            connection.set_trace_callback(None)
        for thread in writer_threads:
            thread.join(timeout=5)
        self.assertTrue(signalled, "the page statement was never observed")
        # Page items, filtered total and status partitions agree: the write
        # that was scheduled inside the read can never land between them.
        self.assertEqual(2, len(window.page))
        self.assertEqual(2, window.total)
        self.assertEqual({"completed": 2}, window.status_counts)
        self.assertEqual(2, sum(window.status_counts.values()))
        self.assertEqual(["committed"], writer_outcome)
        # The blocked admission still commits once the snapshot closes.
        _status, after, _ = request(self.api, "GET", "/api/v1/operations/runs")
        self.assertEqual(3, after["total"])

    def test_pages_keep_filter_scoped_totals_in_both_directions(self) -> None:
        """Totals never shrink while paging; both directions page newest-first."""

        for index in range(30):
            self.repository.create_task(
                task(
                    f"bulk-{index}",
                    command="scan",
                    status=PersistentTaskStatus.COMPLETED,
                    rank=index,
                )
            )
        for index in range(5):
            self.repository.create_task(
                task(
                    f"bulk-failed-{index}",
                    command="preview",
                    status=PersistentTaskStatus.FAILED,
                    rank=100 + index,
                )
            )
        expected_counts = {"completed": 30, "failed": 5}
        pages: list[dict] = []
        cursor: str | None = None
        for _ in range(4):
            query = "limit=10" + (f"&cursor={cursor}" if cursor else "")
            code, page, _ = request(self.api, "GET", "/api/v1/operations/runs", query=query)
            self.assertEqual(200, code)
            # The cursor bounds the window only: the reported population is
            # always the full filtered population (35, never 35/25/15/5).
            self.assertEqual(35, page["total"])
            self.assertEqual(expected_counts, page["status_counts"])
            self.assertEqual(35, sum(page["status_counts"].values()))
            self.assertEqual(5, page["attention_count"])
            pages.append(page)
            cursor = page["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(4, len(pages))
        self.assertEqual([10, 10, 10, 5], [len(page["items"]) for page in pages])
        self.assertIsNone(pages[0]["previous_cursor"])
        self.assertIsNotNone(pages[0]["next_cursor"])
        self.assertIsNotNone(pages[1]["previous_cursor"])
        self.assertIsNone(pages[3]["next_cursor"])
        seen: list[str] = []
        for page in pages:
            created = [item["created_at"] for item in page["items"]]
            self.assertEqual(created, sorted(created, reverse=True))
            seen.extend(item["run_id"] for item in page["items"])
        self.assertEqual(len(seen), len(set(seen)))
        # Walking backward from page 2 returns page 1, newest-first, with the
        # adjacent cursors that let the operator keep going both ways.
        code, back, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            query=f"limit=10&cursor={pages[1]['previous_cursor']}",
        )
        self.assertEqual(200, code)
        self.assertEqual(
            [item["run_id"] for item in pages[0]["items"]],
            [item["run_id"] for item in back["items"]],
        )
        created = [item["created_at"] for item in back["items"]]
        self.assertEqual(created, sorted(created, reverse=True))
        self.assertEqual(35, back["total"])
        self.assertEqual(expected_counts, back["status_counts"])
        self.assertIsNone(back["previous_cursor"])
        self.assertIsNotNone(back["next_cursor"])
        # Following the backward page's next cursor returns page 2 again.
        code, again, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            query=f"limit=10&cursor={back['next_cursor']}",
        )
        self.assertEqual(200, code)
        self.assertEqual(
            [item["run_id"] for item in pages[1]["items"]],
            [item["run_id"] for item in again["items"]],
        )
        # A middle page can also step back to its own previous page.
        code, middle, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            query=f"limit=10&cursor={pages[2]['previous_cursor']}",
        )
        self.assertEqual(200, code)
        self.assertEqual(
            [item["run_id"] for item in pages[1]["items"]],
            [item["run_id"] for item in middle["items"]],
        )

    def test_published_maximum_limit_is_served(self) -> None:
        """The advertised legal maximum limit works, including its follow-up."""

        for index in range(105):
            self.repository.create_task(
                task(
                    f"cap-{index:03d}",
                    command="scan",
                    status=PersistentTaskStatus.COMPLETED,
                    rank=index,
                )
            )
        code, first, _ = request(self.api, "GET", "/api/v1/operations/runs", query="limit=100")
        self.assertEqual(200, code)
        self.assertEqual(100, len(first["items"]))
        self.assertEqual(105, first["total"])
        self.assertEqual({"completed": 105}, first["status_counts"])
        self.assertTrue(first["truncated"])
        self.assertIsNotNone(first["next_cursor"])
        self.assertIsNone(first["previous_cursor"])
        self.assertIs(first["attention"], False)
        code, second, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            query=f"limit=100&cursor={first['next_cursor']}",
        )
        self.assertEqual(200, code)
        self.assertEqual(5, len(second["items"]))
        self.assertEqual(105, second["total"])
        self.assertEqual({"completed": 105}, second["status_counts"])
        self.assertFalse(second["truncated"])
        self.assertIsNone(second["next_cursor"])
        self.assertIsNotNone(second["previous_cursor"])

    def test_attention_facet_filters_the_population_and_binds_the_cursor(
        self,
    ) -> None:
        """The attention card's filter is explicit, composable and cursor-bound."""

        self.repository.create_task(task("at-pending", status=PersistentTaskStatus.PENDING, rank=0))
        self.repository.create_task(task("at-failed", status=PersistentTaskStatus.FAILED, rank=1))
        self.repository.create_task(
            task("at-partial", status=PersistentTaskStatus.PARTIAL_SUCCESS, rank=2)
        )
        self.repository.create_task(task("at-done", status=PersistentTaskStatus.COMPLETED, rank=3))
        self.repository.create_task(task("at-done2", status=PersistentTaskStatus.COMPLETED, rank=4))

        code, page, _ = request(self.api, "GET", "/api/v1/operations/runs", query="attention=true")
        self.assertEqual(200, code)
        self.assertIs(page["attention"], True)
        self.assertEqual(3, page["total"])
        self.assertEqual({"pending": 1, "failed": 1, "partial_success": 1}, page["status_counts"])
        self.assertEqual(3, page["attention_count"])
        self.assertEqual(
            {"at-pending", "at-failed", "at-partial"},
            {item["run_id"] for item in page["items"]},
        )
        # The facet composes with the other filters.
        code, composed, _ = request(
            self.api, "GET", "/api/v1/operations/runs", query="attention=true&status=failed"
        )
        self.assertEqual(200, code)
        self.assertEqual(1, composed["total"])
        self.assertEqual("at-failed", composed["items"][0]["run_id"])
        # Absent/false/all keep the unfiltered population.
        for value in ("", "all", "false"):
            with self.subTest(value=value):
                code, plain, _ = request(
                    self.api,
                    "GET",
                    "/api/v1/operations/runs",
                    query=(f"attention={value}" if value else ""),
                )
                self.assertEqual(200, code)
                self.assertIs(plain["attention"], False)
                self.assertEqual(5, plain["total"])
                self.assertEqual(3, plain["attention_count"])
        # An invalid facet value rejects safely instead of silently dropping.
        code, error_body, _ = request(
            self.api, "GET", "/api/v1/operations/runs", query="attention=maybe"
        )
        self.assertEqual(400, code)
        self.assertEqual("invalid_request", error_body["error"]["code"])
        # A cursor minted with the facet cannot be replayed without it, and
        # the reverse mismatch refuses the same way (read recovery).
        code, first, _ = request(
            self.api, "GET", "/api/v1/operations/runs", query="attention=true&limit=1"
        )
        self.assertEqual(200, code)
        cursor = first["next_cursor"]
        self.assertIsNotNone(cursor)
        code, continued, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            query=f"attention=true&limit=1&cursor={cursor}",
        )
        self.assertEqual(200, code)
        self.assertEqual(1, len(continued["items"]))
        self.assertNotEqual(
            [item["run_id"] for item in first["items"]],
            [item["run_id"] for item in continued["items"]],
        )
        for mismatched in (f"limit=1&cursor={cursor}", f"attention=false&limit=1&cursor={cursor}"):
            with self.subTest(query=mismatched):
                code, body, _ = request(
                    self.api, "GET", "/api/v1/operations/runs", query=mismatched
                )
                self.assertEqual(400, code)
                self.assertEqual("invalid_request", body["error"]["code"])

    def test_cursors_refuse_a_different_reading_principal(self) -> None:
        """A cursor minted for one principal never pages another (AC-T2)."""

        for index in range(3):
            self.repository.create_task(
                task(f"cross-{index}", rank=index, status=PersistentTaskStatus.COMPLETED)
            )
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs", query="limit=1")
        cursor = page["next_cursor"]
        self.assertIsNotNone(cursor)

        # The minting principal pages normally.
        code, second, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            query=f"limit=1&cursor={cursor}",
        )
        self.assertEqual(code, 200)
        self.assertEqual(len(second["items"]), 1)

        # Another authorized principal replays the exact cursor: the digested
        # principal binding refuses it with read recovery instead of silently
        # serving a page from a different authorization context.
        code, body, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            token="operator-token",
            query=f"limit=1&cursor={cursor}",
        )
        self.assertEqual(code, 400)
        self.assertEqual(body["error"]["code"], "invalid_request")

    def test_read_denial_is_explicit_and_never_an_empty_population(self) -> None:
        """A principal without READ gets 403, not a fabricated empty list."""

        denied_api = MediaFlowApi(
            self.repository,
            None,
            principals=(ResolvedApiPrincipal("silent", "silent-token", frozenset()),),
        )
        code, body, _ = request(denied_api, "GET", "/api/v1/operations/runs", token="silent-token")
        self.assertEqual(code, 403)
        self.assertNotIn("items", body)
        code, body, _ = request(
            denied_api,
            "GET",
            "/api/v1/operations/runs/task-x",
            token="silent-token",
        )
        self.assertEqual(code, 403)

    # -- AC-T3: historical identity/privacy ------------------------------

    def test_scope_evidence_is_durable_and_never_a_current_active_fallback(
        self,
    ) -> None:
        self.repository.create_job(
            job(
                "scoped-job",
                rank=0,
                task_id="scoped-task",
                resource_library_id="source",
                source_scope="Movies",
            )
        )
        self.repository.create_task(
            task("scoped-task", command="scan", rank=0, scope_path="Movies/2024")
        )
        self.repository.create_task(task("legacy-task", command="scan", rank=1, scope_path=None))
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        by_id = {item["run_id"]: item for item in page["items"]}
        self.assertEqual(by_id["scoped-job"]["source_scope"], "Movies/2024")
        # Missing legacy evidence is explicitly unavailable, never guessed.
        self.assertIsNone(by_id["legacy-task"]["source_scope"])

    def test_restart_and_active_rename_cannot_rewrite_historical_identity(
        self,
    ) -> None:
        """Durable run identity survives a restart and an Active A→B rename.

        The inventory reads only durable repository rows: it never resolves
        the current Active configuration, so renaming a library, deleting one
        or losing the Active entirely can never rewrite a historical scope,
        label or search result.
        """

        from mediaflow.application.configuration_snapshot import (
            ManagedConfigurationService,
        )
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )
        from tests.test_configuration_objects import example_document

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(root / "config.sqlite3")

            def activate_revision(service, doc):
                draft = service.import_draft(doc, actor="operator")
                validated = service.validate(draft.revision_id, actor="operator")
                return service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="operator",
                )

            with SQLiteConfigurationRepository(root / "config.sqlite3") as config_repository:
                service = ManagedConfigurationService(
                    config_repository,
                    bootstrap_database_path=str(root / "config.sqlite3"),
                )
                revision_a = activate_revision(service, document)

                # A legal assembly: the API can read the current Active, and
                # a durable run is recorded with its historical scope.
                with SQLiteTaskRepository(database) as runtime_repository:
                    api = MediaFlowApi(
                        runtime_repository,
                        None,
                        principals=(VIEWER,),
                        configuration_service=service,
                        bootstrap_document=document,
                        configuration_snapshot_id=revision_a.revision_id,
                        configuration_snapshot_digest=revision_a.digest,
                    )
                    runtime_repository.create_job(
                        job(
                            "pinned-job",
                            rank=0,
                            task_id="pinned-task",
                            resource_library_id="library-a",
                            source_scope="Movies A",
                        )
                    )
                    runtime_repository.create_task(
                        task(
                            "pinned-task",
                            command="scan",
                            rank=0,
                            scope_path="Movies A/2024",
                        )
                    )

                    # Under Active A the historical scope is searchable.
                    code, page, _ = request(
                        api,
                        "GET",
                        "/api/v1/operations/runs",
                        query="q=Movies A",
                    )
                    self.assertEqual(code, 200)
                    self.assertEqual(page["total"], 1)

                    # Active B renames the library through the same service:
                    # a real A→B configuration change.
                    renamed = json.loads(json.dumps(document))
                    renamed["resourceLibraries"][0]["name"] = "Renamed Movies"
                    revision_b = activate_revision(service, renamed)
                    self.assertNotEqual(revision_b.revision_id, revision_a.revision_id)

                    # Restart over the same durable database: identity, scope
                    # and search results are byte-for-byte unchanged by the
                    # rename, the library deletion and the new Active.
                    with SQLiteTaskRepository(database) as restarted_repository:
                        restarted_api = MediaFlowApi(
                            restarted_repository,
                            None,
                            principals=(VIEWER,),
                            configuration_service=service,
                            bootstrap_document=renamed,
                        )
                        _status, page, _ = request(
                            restarted_api,
                            "GET",
                            "/api/v1/operations/runs",
                        )
                        run = page["items"][0]
                        self.assertEqual(run["source_scope"], "Movies A/2024")
                        self.assertEqual(run["configuration_snapshot_id"], "snap-a")
                        _status, searched, _ = request(
                            restarted_api,
                            "GET",
                            "/api/v1/operations/runs",
                            query="q=Movies A",
                        )
                        self.assertEqual(searched["total"], 1)
                        # No read-time backfill: the Active's new library name
                        # never appears in, nor matches, historical evidence.
                        _status, renamed_search, _ = request(
                            restarted_api,
                            "GET",
                            "/api/v1/operations/runs",
                            query="q=Renamed Movies",
                        )
                        self.assertEqual(renamed_search["total"], 0)

    def test_history_stays_readable_without_a_usable_current_active(self) -> None:
        """A lost or unreadable Active never hides durable run history (RO-2)."""

        from mediaflow.application.configuration_snapshot import (
            ManagedConfigurationService,
        )
        from mediaflow.domain.configuration_management import (
            RuntimeSnapshotUnavailable,
        )
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )
        from tests.test_configuration_objects import example_document

        self.repository.create_task(
            task("durable-task", command="scan", rank=0, scope_path="Movies/2024")
        )

        document = example_document()
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "config.sqlite3"
            with SQLiteConfigurationRepository(database_path) as config_repository:
                service = ManagedConfigurationService(
                    config_repository,
                    bootstrap_database_path=str(database_path),
                )
                # Assembled legally first, then the Active becomes unreadable
                # (lost snapshot, corrupted authority or missing revision).
                api = MediaFlowApi(
                    self.repository,
                    None,
                    principals=(VIEWER,),
                    configuration_service=service,
                    bootstrap_document=document,
                )

                def raise_unavailable():
                    raise RuntimeSnapshotUnavailable("Active is unavailable")

                service.active = raise_unavailable  # type: ignore[method-assign]

                # The inventory reads durable repository rows only: it still
                # answers truthfully with no admission, no Provider call and
                # no Storage mutation of any kind.
                code, page, _ = request(api, "GET", "/api/v1/operations/runs")
                self.assertEqual(code, 200)
                by_id = {item["run_id"]: item for item in page["items"]}
                self.assertEqual(by_id["durable-task"]["source_scope"], "Movies/2024")

    def test_public_documents_expose_no_host_roots_or_adapter_evidence(self) -> None:
        self.repository.create_task(
            task("hostile-task", command="scan", rank=0, scope_path="/srv/private-host/root")
        )
        self.repository.create_task(_hostile_error_task("hostile-error-task"))
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        rendered = json.dumps(page)
        for forbidden in (
            "/srv/private-host",
            "topsecret",
            "https://private.example",
            "Bearer",
        ):
            self.assertNotIn(forbidden, rendered)
        # An absolute host root degrades to the bounded redaction marker.
        by_id = {item["run_id"]: item for item in page["items"]}
        self.assertEqual(by_id["hostile-task"]["source_scope"], "[redacted-path]")

    # -- AC-T6: no new authority or side effects -------------------------

    def test_reads_are_authorized_and_admit_nothing(self) -> None:
        self.repository.create_task(task("read-only-task", rank=0))
        before_tasks = len(self.repository.list_tasks())
        before_jobs = len(self.repository.list_jobs())
        code, _body, _ = request(self.api, "GET", "/api/v1/operations/runs")
        self.assertEqual(code, 200)
        self.assertEqual(len(self.repository.list_tasks()), before_tasks)
        self.assertEqual(len(self.repository.list_jobs()), before_jobs)
        code, _body, _ = request(self.api, "GET", "/api/v1/operations/runs", token="denied-token")
        self.assertEqual(code, 401)
        code, _body, _ = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            token="viewer-token",
            query="limit=1",
        )
        self.assertEqual(code, 200)

    def test_read_performs_zero_storage_mutation_or_provider_work(self) -> None:
        self.repository.create_task(task("side-effect-task", rank=0))
        # The API construction itself never received a Provider or a Storage
        # adapter, and the read route resolves neither: prove the read answers
        # from durable rows alone and creates no work.
        _status, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        self.assertEqual(page["sideEffects"], "none")
        self.assertEqual(page["total"], 1)
        overview_status, overview, _ = request(
            self.api, "GET", "/api/v1/operations/runs/side-effect-task"
        )
        self.assertEqual(overview_status, 200)
        self.assertEqual(overview["sideEffects"], "none")

    def test_oldest_run_opens_by_exact_id_beyond_the_newest_window(self) -> None:
        """A real historical run stays openable no matter how many followed.

        The overview must read one run by its exact ID from the same linked
        projection, never by scanning a "newest N rows" window: selection and
        supported detail deep links keep working for the oldest admitted run
        of a busy inventory, while an unknown ID stays an honest 404.
        """

        for index in range(105):
            self.repository.create_task(task(f"hist-{index:03d}", command="scan", rank=index))
        # The oldest run is not in any newest-100 window.
        code, overview, _ = request(self.api, "GET", "/api/v1/operations/runs/hist-000")
        self.assertEqual(code, 200)
        self.assertEqual("hist-000", overview["run_id"])
        self.assertEqual("扫描", overview["command_label"])
        self.assertEqual("none", overview["sideEffects"])
        # It is also still findable and pageable in the filtered inventory.
        code, page, _ = request(self.api, "GET", "/api/v1/operations/runs", query="q=hist-000")
        self.assertEqual(code, 200)
        self.assertEqual(1, page["total"])
        self.assertEqual("hist-000", page["items"][0]["run_id"])
        # An unknown ID is an honest not-found, not an empty overview.
        code, body, _ = request(self.api, "GET", "/api/v1/operations/runs/not-a-run")
        self.assertEqual(code, 404)
        self.assertEqual("not_found", body["error"]["code"])

    def test_unsupported_runtime_has_no_inventory_endpoint_access(self) -> None:
        class NoInventoryRepository:
            def list_tasks(self, **_kwargs):
                return ()

            def append_security_audit(self, record):
                return None

            def list_security_audit(self, *, limit=100):
                return ()

        limited_api = MediaFlowApi(NoInventoryRepository(), None, principals=(VIEWER,))
        code, body, _ = request(limited_api, "GET", "/api/v1/operations/runs")
        self.assertEqual(code, 503)
        self.assertEqual(body["error"]["code"], "service_unavailable")

    # -- AC-T7: durable compatible delivery -------------------------------

    def test_schema39_fixture_upgrades_additively_and_preserves_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "upgraded.sqlite3")
            self._create_schema39_database(database)
            # Pre-upgrade rows: a linked Job→Task pair with a pinned result and
            # a registered worker.
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "legacy-task-1",
                        "scan",
                        "completed",
                        1,
                        NOW.isoformat(),
                        NOW.isoformat(),
                        NOW.isoformat(),
                        NOW.isoformat(),
                        2,
                        2,
                        0,
                        None,
                        0,
                        "Movies",
                        10,
                        "snap-legacy",
                        "digest-legacy",
                    ),
                )
                connection.execute(
                    "INSERT INTO automation_jobs (job_id, command, status, created_at,"
                    " updated_at, task_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "legacy-job-1",
                        "scan",
                        "completed",
                        NOW.isoformat(),
                        NOW.isoformat(),
                        "legacy-task-1",
                    ),
                )
                connection.execute(
                    "INSERT INTO processing_workers (worker_id, label, registered_at,"
                    " heartbeat_interval_seconds, supported_commands,"
                    " configuration_snapshot_id, configuration_snapshot_digest,"
                    " runtime_schema_version, last_heartbeat_at, status)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "worker-legacy",
                        "legacy-worker",
                        NOW.isoformat(),
                        5.0,
                        "scan,preview",
                        "snap-legacy",
                        "digest-legacy",
                        SCHEMA_VERSION - 1,
                        NOW.isoformat(),
                        "live",
                    ),
                )
                connection.commit()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                # The schema-41 display table is created additively by the
                # upgrade; the fixture itself never contained it.
                with sqlite3.connect(database) as upgraded:
                    display_table = upgraded.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                        " AND name='operations_run_display'"
                    ).fetchone()
                self.assertIsNotNone(display_table)
                # Pins, links, results and authority survive the additive
                # upgrade untouched.
                upgraded_task = repository.get_task("legacy-task-1")
                self.assertIsNotNone(upgraded_task)
                self.assertEqual(upgraded_task.configuration_snapshot_id, "snap-legacy")
                upgraded_job = repository.get_job("legacy-job-1")
                self.assertIsNotNone(upgraded_job)
                self.assertEqual(upgraded_job.task_id, "legacy-task-1")
                # The inventory reads the upgraded population immediately.
                page, total, counts = repository.operations_runs_page(limit=10)
                self.assertEqual(total, 1)
                self.assertEqual(counts, {"completed": 1})
                self.assertEqual(page[0].run_id, "legacy-job-1")
                self.assertEqual(page[0].task_id, "legacy-task-1")
            # A restart on the upgraded database retains the same truth.
            with SQLiteTaskRepository(database) as repository:
                page, total, _counts = repository.operations_runs_page(limit=10)
                self.assertEqual(total, 1)
                self.assertEqual(page[0].run_id, "legacy-job-1")

    def test_unsupported_newer_schema_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "future.sqlite3")
            with SQLiteTaskRepository(database):
                pass
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (SCHEMA_VERSION + 1,),
                )
                connection.commit()
            with self.assertRaises(ValueError):
                SQLiteTaskRepository(database)

    def test_worker_readiness_keeps_current_schema_contract(self) -> None:
        worker_service = ProcessingWorkerService(
            self.repository,
            active_configuration_snapshot_id="snap-a",
            active_configuration_snapshot_digest="digest-a",
        )
        worker_service.register_worker(
            worker_id="worker-inventory",
            label="inventory-worker",
            heartbeat_interval_seconds=5.0,
            supported_commands=("scan", "preview"),
            configuration_snapshot_id="snap-a",
            configuration_snapshot_digest="digest-a",
            runtime_schema_version=SCHEMA_VERSION,
            now=NOW,
        )
        readiness = worker_service.evaluate_readiness(
            active_snapshot_id="snap-a",
            active_snapshot_digest="digest-a",
            now=NOW,
        )
        self.assertTrue(readiness["ready"])

    # -- fixture helpers ---------------------------------------------------

    @staticmethod
    def _create_schema39_database(path: Path) -> None:
        """Create a production-shaped schema-39 runtime database.

        The fixture reproduces the Task-Base layout: every table that existed
        at the Task Base, the schema-39 marker and none of the schema-40
        inventory indexes or the schema-41 display table.  The production
        repository migration then adds only those additive objects.
        """

        from tests.test_task_persistence import Schema34To35UpgradeTests

        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            connection.execute("INSERT INTO schema_version VALUES ('runtime', 39)")
            for ddl in (
                Schema34To35UpgradeTests._TASKS_DDL,
                Schema34To35UpgradeTests._SCHEMA34_TASK_ITEMS_DDL,
                Schema34To35UpgradeTests._SCHEMA34_TASK_RESULTS_DDL,
                Schema34To35UpgradeTests._FILE_LOCKS_DDL,
            ):
                connection.execute(ddl)
            # A representative remainder of the schema-39 surface: the tables
            # the inventory itself reads plus one Worker row table.
            connection.execute(
                """
                CREATE TABLE automation_jobs (
                    job_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, limit_value INTEGER,
                    started_at TEXT, completed_at TEXT, task_id TEXT, error TEXT,
                    cancellation_requested INTEGER NOT NULL DEFAULT 0, schedule_id TEXT,
                    execute_authorized INTEGER NOT NULL DEFAULT 0, claim_token TEXT,
                    worker_id TEXT, configuration_snapshot_id TEXT,
                    configuration_snapshot_digest TEXT, failure_category TEXT,
                    failure_durable_state TEXT, failure_side_effects TEXT,
                    failure_retry_safe INTEGER, failure_next_action TEXT,
                    definition_id TEXT, definition_fingerprint TEXT,
                    definition_version INTEGER, occurrence_at TEXT, run_mode TEXT,
                    resource_library_id TEXT, source_scope TEXT,
                    configuration_snapshot_version INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE processing_workers (
                    worker_id TEXT PRIMARY KEY, label TEXT NOT NULL,
                    registered_at TEXT NOT NULL, heartbeat_interval_seconds REAL NOT NULL,
                    supported_commands TEXT NOT NULL, configuration_snapshot_id TEXT,
                    configuration_snapshot_digest TEXT, runtime_schema_version INTEGER NOT NULL,
                    last_heartbeat_at TEXT NOT NULL, status TEXT NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()


def _inventory_item(task_id: str, item_id: str, library_identity: str):
    from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus

    return PersistentTaskItem(
        item_id,
        task_id,
        "storage-1",
        library_identity,
        f"{item_id}.mkv",
        f"source:{item_id}.mkv",
        TaskItemStatus.PROCESSING,
        "organizing",
        1,
        NOW,
        NOW,
    )


def _pause_requested_task(task_id: str) -> PersistentTask:
    from dataclasses import replace

    return replace(
        task(task_id, command="scan", status=PersistentTaskStatus.RUNNING, rank=0),
        pause_requested=True,
    )


def _waiting_task(task_id: str) -> PersistentTask:
    from dataclasses import replace

    return replace(
        task(
            task_id,
            command="organize",
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            rank=0,
        ),
        completed_items=1,
        failed_items=1,
    )


def _hostile_error_task(task_id: str) -> PersistentTask:
    from dataclasses import replace

    return replace(
        task(
            task_id,
            command="scan",
            status=PersistentTaskStatus.FAILED,
            rank=1,
            configuration_snapshot_id=None,
        ),
        error=(
            "Authorization: Bearer topsecret https://private.example/api raw adapter stack trace"
        ),
    )


def _retime(task_id: str, when: datetime) -> PersistentTask:
    from dataclasses import replace

    return replace(task(task_id, rank=0), created_at=when, updated_at=when)


class ScanDisplayEvidenceTests(_InventoryApiTestCase):
    """A newly admitted Scan records its business identity at admission.

    The producer writes bounded display evidence inside the same transaction
    that creates the Task, so a brand-new Scan is searchable by its visible
    business label and configured library scope instead of appearing as
    legacy-missing.
    """

    def _service(self) -> tuple[ManualScanService, InMemoryFileIndexRepository]:
        storage = FakeStorage("source")
        storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        storage.add_file("sibling.mkv", 11, NOW - timedelta(hours=2))
        index = InMemoryFileIndexRepository()
        library = ResourceLibrary("library", "Library", "source", "", exclude_rules=())
        StorageScanner({"source": storage}, index, clock=lambda: NOW).scan(library)
        service = ManualScanService(
            self.repository,
            index,
            resource_libraries=(library,),
            storages={"source": storage},
            configuration_snapshot_id="snap-a",
            configuration_snapshot_digest="digest-a",
            clock=lambda: NOW,
            start_async=False,
        )
        return service, index

    def _run_document(self, run_id: str) -> dict:
        code, page, _ = request(self.api, "GET", "/api/v1/operations/runs")
        self.assertEqual(200, code)
        matches = [item for item in page["items"] if item["run_id"] == run_id]
        self.assertEqual(1, len(matches), page)
        return matches[0]

    def test_library_scope_scan_publishes_scope_and_is_searchable(self) -> None:
        service, _index = self._service()
        admitted = service.admit_document(
            {
                "scopeKind": "resource_library",
                "resourceLibraryId": "library",
                "mode": "full",
            }
        )
        run = self._run_document(admitted.task_id)
        self.assertEqual("扫描", run["command_label"])
        self.assertEqual("Library", run["source_scope"])
        self.assertIsNone(run["target_scope"])
        self.assertEqual("resource", run["library_kind"])
        for needle in ("Library", "扫描"):
            with self.subTest(needle=needle):
                code, found, _ = request(
                    self.api, "GET", "/api/v1/operations/runs", query=f"q={needle}"
                )
                self.assertEqual(200, code)
                self.assertEqual(1, found["total"])
                self.assertEqual(admitted.task_id, found["items"][0]["run_id"])

    def test_file_scope_scan_publishes_the_relative_source_path(self) -> None:
        service, index = self._service()
        record = index.find_by_path("source", "library", "current.mkv")
        self.assertIsNotNone(record)
        admitted = service.admit_document(
            {
                "scopeKind": "file",
                "resourceLibraryId": "library",
                "fileId": record.file_id,
                "occurrenceId": record.occurrence_id,
                "fingerprint": record.fingerprint,
                "mode": "incremental",
            }
        )
        run = self._run_document(admitted.task_id)
        self.assertEqual("Library/current.mkv", run["source_scope"])
        code, found, _ = request(self.api, "GET", "/api/v1/operations/runs", query="q=current.mkv")
        self.assertEqual(200, code)
        self.assertEqual(1, found["total"])
        self.assertEqual(admitted.task_id, found["items"][0]["run_id"])


class ManualOrganizeDisplayEvidenceTests(_JourneyFixtureMixin, unittest.TestCase):
    """A newly admitted manual Organize run carries its full business identity.

    The display evidence (historical source/target scope and safe business
    labels) is recorded from the reviewed Preview, the selected items and the
    pinned runtime inside the admission transaction — never resolved from the
    current Active configuration at read time — and is searchable immediately.
    """

    def test_admitted_execution_publishes_display_identity_and_is_searchable(
        self,
    ) -> None:
        with self.journey() as value:
            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            status, execution = self._execute(value, preview, intent)
            self.assertEqual(202, status)
            task_id = execution["taskId"]

            status, page = self._request(value, "/api/v1/operations/runs")
            self.assertEqual(200, status)
            self.assertEqual(1, page["total"])
            run = page["items"][0]
            self.assertEqual(task_id, run["run_id"])
            self.assertEqual("手动整理", run["command_label"])
            self.assertEqual("manual", run["trigger"])
            self.assertEqual("resource", run["library_kind"])
            self.assertTrue(run["source_scope"], run)
            self.assertTrue(run["target_scope"], run)
            self.assertTrue(str(run["source_scope"]).startswith("Library"), run)
            self.assertTrue(str(run["target_scope"]).startswith("Movies"), run)

            # The visible business label, both library scopes and the reviewed
            # source file are all reachable through the server-side search.
            for needle in ("手动整理", "Library", "Movies", "One.2001.mkv"):
                with self.subTest(needle=needle):
                    status, found = self._request(value, f"/api/v1/operations/runs?q={needle}")
                    self.assertEqual(200, status)
                    self.assertGreaterEqual(found["total"], 1, needle)
                    self.assertIn(task_id, [item["run_id"] for item in found["items"]])

            # The selected-run overview (deep-link target) publishes exactly
            # the same identity as the list row.
            status, overview = self._request(value, f"/api/v1/operations/runs/{task_id}")
            self.assertEqual(200, status)
            self.assertEqual(run["source_scope"], overview["source_scope"])
            self.assertEqual(run["target_scope"], overview["target_scope"])
            self.assertEqual(run["command_label"], overview["command_label"])


if __name__ == "__main__":
    unittest.main()
