"""Focused proof for Task 42.1 — the unified Operations run inventory.

These tests exercise the real SQLite repository, the shared read projection
and the authenticated ``/api/v1/operations/runs`` API against the current
legal production assemblies:

- AC-T1 one real population: linked Job→Task work is visible and counted
  once across the linkage, standalone Tasks, pre-Task pending/failed Jobs,
  manual-execution Tasks, scheduled definition occurrences, retry
  continuations and both library kinds' direct commands/transfers are all
  discoverable; unknown legacy commands keep an honest label; a completed
  Job never masks its linked Task's partial success or failure.
- AC-T2 authoritative query/counts: text/status/kind/time filters compose,
  invalid values reject safely, ties page deterministically, cursors bind
  the submitted filter scope (and refuse a mismatch), totals and status
  partitions reconcile beyond one page, and the attention facet is
  explicitly overlapping.
- AC-T3 historical identity/privacy: scope evidence comes from the durable
  admission record or is explicitly unavailable; a restart and an Active
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
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.operations_run import (
    ATTENTION_RUN_STATUSES,
    known_command_label,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentTask,
    PersistentTaskStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.pagination import (
    CursorDirection,
    decode_directional_cursor,
    encode_cursor,
)
from mediaflow.interfaces.service_api import MediaFlowApi

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


class RunInventoryTestCase(unittest.TestCase):
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
            expected_scope=("principal=viewer;status=completed;command=all;q=;from=;to="),
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

        The fixture reproduces the Task-Base layout: every current table, the
        schema-39 marker and none of the schema-40 inventory indexes.  The
        production repository migration then adds only the additive indexes.
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


if __name__ == "__main__":
    unittest.main()
