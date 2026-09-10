"""Focused proof for the Task 33.1 Operations workspace backend contract.

These tests exercise the authoritative Python API rather than the Playwright
fake: bounded Task/Job status and command filtering with filter-bound cursors,
the backend-computed lifecycle projection for an exact principal and state,
cooperative pause/cancel admission with optimistic and duplicate rejection,
normalized audit routes, durable preservation of successful siblings, and the
zero-mutation guarantee of every Operations read.
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.automation import AutomationJobService
from mediaflow.application.media_organizer import (
    MediaOrganizerBatchResult,
    MediaOrganizerItemResult,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.manual_scan import (
    ManualScanScopeKind,
    ManualScanTask,
    ScanMode,
)
from mediaflow.domain.organizer import (
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
    PlanOperation,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.final_cli import _task_was_cancelled
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
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
AUDITOR = ResolvedApiPrincipal("auditor", "auditor-token", frozenset({ApiPermission.READ}))


def request(
    api: MediaFlowApi,
    method: str,
    path: str,
    *,
    token: str = "operator-token",
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


def control_body(version: str) -> bytes:
    return json.dumps({"expectedUpdatedAt": version}).encode()


class OperationsWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.api = MediaFlowApi(
            self.repository,
            None,
            principals=(VIEWER, OPERATOR, AUDITOR),
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    # -- fixtures ---------------------------------------------------------

    @staticmethod
    def task(
        task_id: str,
        *,
        command: str = "preview",
        status: PersistentTaskStatus = PersistentTaskStatus.COMPLETED,
        rank: int = 0,
        pause_requested: bool = False,
        execute_authorized: bool = False,
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
            failed_items=1 if terminal else 0,
            pause_requested=pause_requested,
            configuration_snapshot_id="snap-1",
            configuration_snapshot_digest="digest-1",
        )

    @staticmethod
    def job(
        job_id: str,
        *,
        command: AutomationCommand = AutomationCommand.PREVIEW,
        status: AutomationJobStatus = AutomationJobStatus.PENDING,
        rank: int = 0,
        task_id: str | None = None,
    ) -> AutomationJob:
        occurred = NOW + timedelta(minutes=rank)
        return AutomationJob(
            job_id,
            command,
            status,
            occurred,
            occurred,
            started_at=occurred if status is not AutomationJobStatus.PENDING else None,
            completed_at=(
                occurred
                if status
                in {
                    AutomationJobStatus.COMPLETED,
                    AutomationJobStatus.FAILED,
                    AutomationJobStatus.CANCELLED,
                }
                else None
            ),
            task_id=task_id,
        )

    @staticmethod
    def item(task_id: str, item_id: str, status: TaskItemStatus) -> PersistentTaskItem:
        return PersistentTaskItem(
            item_id,
            task_id,
            "source",
            "movies",
            f"{item_id}.mkv",
            f"source:{item_id}.mkv",
            status,
            "completed",
            1,
            NOW,
            NOW,
        )

    @staticmethod
    def result(
        task_id: str,
        item_id: str,
        *,
        certainty: str = "verified_complete",
        uncertain: tuple[str, ...] = (),
    ) -> PersistentResultRecord:
        return PersistentResultRecord(
            f"{item_id}:1",
            task_id,
            item_id,
            "source",
            f"{item_id}.mkv",
            "target",
            f"Movies/{item_id}.mkv",
            "A",
            "tmdb",
            "1",
            "A",
            "A",
            "A",
            "A",
            "MOVE",
            "success",
            NOW,
            title="Movie",
            effect_certainty=certainty,
            uncertain_effects=uncertain,
        )

    def audit_routes(self) -> list[str]:
        return [item.route for item in self.repository.list_security_audit(limit=200)]

    def state_counts(self) -> tuple[int, int]:
        return (
            len(self.repository.list_tasks()),
            len(self.repository.list_jobs()),
        )

    # -- collection filtering --------------------------------------------

    def test_task_and_job_collections_apply_status_and_command_filters(self) -> None:
        self.repository.create_task(self.task("task-a", command="preview", rank=0))
        self.repository.create_task(
            self.task(
                "task-b",
                command="organize",
                status=PersistentTaskStatus.FAILED,
                rank=1,
            )
        )
        self.repository.create_task(
            self.task(
                "task-c",
                command="retry-failed:task-b",
                status=PersistentTaskStatus.RUNNING,
                rank=2,
            )
        )
        for rank, (command, status) in enumerate(
            (
                (AutomationCommand.SCAN, AutomationJobStatus.PENDING),
                (AutomationCommand.PREVIEW, AutomationJobStatus.COMPLETED),
            )
        ):
            self.repository.create_job(
                self.job(f"job-{rank}", command=command, status=status, rank=rank)
            )

        status, page, _ = request(self.api, "GET", "/api/v1/tasks", query="status=failed")
        self.assertEqual(status, 200)
        self.assertEqual([item["task_id"] for item in page["items"]], ["task-b"])
        self.assertEqual(page["status"], "failed")

        status, page, _ = request(self.api, "GET", "/api/v1/tasks", query="command=retry-failed")
        self.assertEqual(status, 200)
        # A derived continuation belongs to its command family.
        self.assertEqual([item["task_id"] for item in page["items"]], ["task-c"])

        status, page, _ = request(self.api, "GET", "/api/v1/jobs", query="command=scan")
        self.assertEqual(status, 200)
        self.assertEqual([item["job_id"] for item in page["items"]], ["job-0"])
        self.assertEqual(page["command"], "scan")

        status, page, _ = request(
            self.api, "GET", "/api/v1/jobs", query="status=completed&command=preview"
        )
        self.assertEqual(status, 200)
        self.assertEqual([item["job_id"] for item in page["items"]], ["job-1"])

        for path, query in (
            ("/api/v1/tasks", "status=unknown"),
            ("/api/v1/tasks", "command=../escape"),
            ("/api/v1/tasks", "status=failed&status=running"),
            ("/api/v1/jobs", "status=unknown"),
            ("/api/v1/jobs", "command=not-a-command"),
            ("/api/v1/jobs", "command=scan&command=preview"),
        ):
            with self.subTest(path=path, query=query):
                code, _, _ = request(self.api, "GET", path, query=query)
                self.assertEqual(code, 400)

    def test_collection_cursors_bind_the_submitted_filters(self) -> None:
        for rank in range(4):
            self.repository.create_task(
                self.task(
                    f"task-{rank}",
                    command="preview" if rank % 2 == 0 else "organize",
                    status=(
                        PersistentTaskStatus.COMPLETED if rank < 2 else PersistentTaskStatus.FAILED
                    ),
                    rank=rank,
                )
            )
        status, first, _ = request(
            self.api, "GET", "/api/v1/tasks", query="status=completed&limit=1"
        )
        self.assertEqual(status, 200)
        cursor = first["next_cursor"]
        self.assertIsNotNone(cursor)
        decoded = decode_directional_cursor(
            cursor, "tasks", expected_scope="status=completed;command=all"
        )
        self.assertEqual(decoded.direction, CursorDirection.NEXT)

        status, second, _ = request(
            self.api,
            "GET",
            "/api/v1/tasks",
            query=f"status=completed&limit=1&cursor={cursor}",
        )
        self.assertEqual(status, 200)
        self.assertNotEqual(
            [item["task_id"] for item in first["items"]],
            [item["task_id"] for item in second["items"]],
        )

        for mismatched in (
            f"status=failed&limit=1&cursor={cursor}",
            f"command=preview&limit=1&cursor={cursor}",
            f"limit=1&cursor={cursor}",
        ):
            with self.subTest(query=mismatched):
                code, _, _ = request(self.api, "GET", "/api/v1/tasks", query=mismatched)
                self.assertEqual(code, 400)

        # A cursor minted for another kind is rejected outright.
        foreign = encode_cursor("jobs", NOW, "job-0", scope="status=all;command=all")
        code, _, _ = request(self.api, "GET", "/api/v1/tasks", query=f"limit=1&cursor={foreign}")
        self.assertEqual(code, 400)

    # -- lifecycle projection ---------------------------------------------

    def test_projection_is_computed_per_principal_and_exact_state(self) -> None:
        self.repository.create_task(
            self.task("task-run", status=PersistentTaskStatus.RUNNING, rank=0)
        )
        self.repository.create_task(self.task("task-done", rank=1))

        status, detail, _ = request(self.api, "GET", "/api/v1/tasks/task-run", token="viewer-token")
        self.assertEqual(status, 200)
        lifecycle = detail["lifecycle"]
        self.assertFalse(lifecycle["permitted"])
        self.assertEqual(lifecycle["state"], "running")
        self.assertTrue(lifecycle["actions"])
        self.assertFalse(any(item["available"] for item in lifecycle["actions"]))
        for item in lifecycle["actions"]:
            self.assertIsNotNone(item["unavailableReason"])

        status, detail, _ = request(
            self.api, "GET", "/api/v1/tasks/task-run", token="operator-token"
        )
        self.assertEqual(status, 200)
        lifecycle = detail["lifecycle"]
        self.assertTrue(lifecycle["permitted"])
        available = {item["action"] for item in lifecycle["actions"] if item["available"]}
        self.assertEqual(available, {"cancel", "pause"})
        self.assertEqual(
            lifecycle["version"], self.repository.get_task("task-run").updated_at.isoformat()
        )

        status, detail, _ = request(
            self.api, "GET", "/api/v1/tasks/task-done", token="operator-token"
        )
        self.assertEqual(status, 200)
        lifecycle = detail["lifecycle"]
        self.assertTrue(lifecycle["terminal"])
        self.assertFalse(any(item["available"] for item in lifecycle["actions"]))

    def test_resume_is_withheld_with_an_actionable_reason(self) -> None:
        self.repository.create_task(
            self.task("task-paused", status=PersistentTaskStatus.PAUSED, rank=0)
        )
        status, detail, _ = request(
            self.api, "GET", "/api/v1/tasks/task-paused", token="operator-token"
        )
        self.assertEqual(status, 200)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertFalse(resume["available"])
        self.assertIn("operator CLI workflow", resume["unavailableReason"])
        self.assertIn("tasks resume", resume["nextAction"])

        task = self.repository.get_task("task-paused")
        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-paused/resume",
            body=control_body(task.updated_at.isoformat()),
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["details"]["reason"], "resume_unavailable")
        self.assertEqual(self.repository.get_task("task-paused").status.value, "paused")

    def test_task_detail_projection_reports_recorded_effect_certainty(self) -> None:
        self.repository.create_task(
            self.task("task-effects", status=PersistentTaskStatus.PARTIAL_SUCCESS, rank=0)
        )
        self.repository.append_result(
            self.result(
                "task-effects", "item-a", certainty="attempted_unverified", uncertain=("move",)
            )
        )
        status, detail, _ = request(
            self.api, "GET", "/api/v1/tasks/task-effects", token="operator-token"
        )
        self.assertEqual(status, 200)
        lifecycle = detail["lifecycle"]
        self.assertEqual(lifecycle["effectCertainty"], "uncertain")
        self.assertEqual(lifecycle["uncertainResults"], 1)
        self.assertIn("unverified Storage effect", lifecycle["knownEffects"])
        # An uncertain mutation is never advertised as repeatable.
        self.assertFalse(any(item["retrySafe"] for item in lifecycle["actions"]))

    # -- cooperative control ----------------------------------------------

    def test_pause_is_durable_and_rejects_stale_duplicate_and_terminal_use(self) -> None:
        self.repository.create_task(
            self.task("task-run", status=PersistentTaskStatus.RUNNING, rank=0)
        )
        task = self.repository.get_task("task-run")
        version = task.updated_at.isoformat()

        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-run/pause",
            body=control_body(version),
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["task"]["pause_requested"])
        self.assertEqual(body["task"]["status"], "running")
        self.assertTrue(body["lifecycle"]["pauseRequested"])

        # The Task is still running: the pause is a durable request, not an
        # instant interruption.
        self.assertEqual(self.repository.get_task("task-run").status, PersistentTaskStatus.RUNNING)

        # A duplicate submission against the now-stale version is refused.
        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-run/pause",
            body=control_body(version),
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["details"]["reason"], "stale_task_state")

        # A fresh read shows the pending request and no longer offers pause.
        current = self.repository.get_task("task-run")
        status, detail, _ = request(
            self.api, "GET", "/api/v1/tasks/task-run", token="operator-token"
        )
        pause = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "pause")
        self.assertFalse(pause["available"])
        self.assertIn("already stored", pause["unavailableReason"])
        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-run/pause",
            body=control_body(current.updated_at.isoformat()),
        )
        self.assertEqual(status, 409)

        self.repository.create_task(self.task("task-done", rank=1))
        done = self.repository.get_task("task-done")
        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-done/pause",
            body=control_body(done.updated_at.isoformat()),
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["details"]["reason"], "pause_unavailable")

    def test_cancel_is_general_terminal_safe_and_permission_checked(self) -> None:
        self.repository.create_task(
            self.task("task-preview", status=PersistentTaskStatus.RUNNING, rank=0)
        )
        self.repository.upsert_item(self.item("task-preview", "item-done", TaskItemStatus.SUCCESS))
        self.repository.upsert_item(
            self.item("task-preview", "item-open", TaskItemStatus.PROCESSING)
        )
        task = self.repository.get_task("task-preview")
        version = task.updated_at.isoformat()

        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-preview/cancel",
            token="viewer-token",
            body=control_body(version),
        )
        self.assertEqual(status, 403)
        self.assertEqual(
            self.repository.get_task("task-preview").status,
            PersistentTaskStatus.RUNNING,
        )

        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-preview/cancel",
            body=control_body(version),
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["task"]["status"], "cancelled")
        # A completed sibling stays terminal; only the open item is cancelled.
        self.assertEqual(self.repository.get_item("item-done").status, TaskItemStatus.SUCCESS)
        self.assertEqual(self.repository.get_item("item-open").status, TaskItemStatus.CANCELLED)

        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-preview/cancel",
            body=control_body(version),
        )
        self.assertEqual(status, 409)
        self.assertEqual(
            self.repository.get_task("task-preview").status,
            PersistentTaskStatus.CANCELLED,
        )

        # An empty body keeps the pre-existing cancellation contract working.
        self.repository.create_task(
            self.task("task-legacy", status=PersistentTaskStatus.RUNNING, rank=1)
        )
        status, body, _ = request(self.api, "POST", "/api/v1/tasks/task-legacy/cancel")
        self.assertEqual(status, 200)
        self.assertEqual(body["task"]["status"], "cancelled")

        self.repository.create_task(
            self.task("task-bad", status=PersistentTaskStatus.RUNNING, rank=2)
        )
        for bad_body in (b"{}", b'{"expectedUpdatedAt": ""}', b'{"other": "x"}'):
            with self.subTest(body=bad_body):
                code, _, _ = request(
                    self.api, "POST", "/api/v1/tasks/task-bad/cancel", body=bad_body
                )
                self.assertEqual(code, 400)
        self.assertEqual(self.repository.get_task("task-bad").status, PersistentTaskStatus.RUNNING)

    def test_job_cancel_fences_version_and_state(self) -> None:
        service = AutomationJobService(self.repository)
        pending = service.submit("scan")
        self.repository.create_job(
            self.job(
                "job-done",
                command=AutomationCommand.PREVIEW,
                status=AutomationJobStatus.COMPLETED,
                rank=5,
                task_id="task-a",
            )
        )
        stale_version = pending.updated_at.isoformat()
        self.repository.claim_next_job(datetime.now(UTC))
        running = self.repository.get_job(pending.job_id)

        status, body, _ = request(
            self.api,
            "POST",
            f"/api/v1/jobs/{pending.job_id}/cancel",
            body=control_body(stale_version),
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["details"]["reason"], "stale_job_state")

        status, body, _ = request(
            self.api,
            "POST",
            f"/api/v1/jobs/{pending.job_id}/cancel",
            body=control_body(running.updated_at.isoformat()),
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["cancellation_requested"])
        self.assertFalse(
            body["lifecycle"]["actions"][0]["available"],
        )

        done = self.repository.get_job("job-done")
        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/jobs/job-done/cancel",
            body=control_body(done.updated_at.isoformat()),
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["details"]["reason"], "cancel_unavailable")

        status, body, _ = request(self.api, "GET", "/api/v1/jobs/job-done", token="viewer-token")
        self.assertEqual(status, 200)
        self.assertFalse(body["lifecycle"]["permitted"])
        self.assertFalse(any(item["available"] for item in body["lifecycle"]["actions"]))

    def test_lifecycle_attempts_are_audited_through_normalized_routes(self) -> None:
        self.repository.create_task(
            self.task("task-run", status=PersistentTaskStatus.RUNNING, rank=0)
        )
        task = self.repository.get_task("task-run")
        request(
            self.api,
            "POST",
            "/api/v1/tasks/task-run/pause",
            body=control_body(task.updated_at.isoformat()),
        )
        request(self.api, "POST", "/api/v1/tasks/task-run/cancel")
        request(
            self.api,
            "POST",
            "/api/v1/tasks/task-run/pause",
            token="viewer-token",
            body=control_body(task.updated_at.isoformat()),
        )
        routes = self.audit_routes()
        self.assertIn("/api/v1/tasks/{id}/pause", routes)
        self.assertIn("/api/v1/tasks/{id}/cancel", routes)
        serialized = json.dumps(routes)
        self.assertNotIn("task-run", serialized)
        outcomes = {
            (item.route, item.outcome, item.http_status)
            for item in self.repository.list_security_audit(limit=200)
        }
        self.assertIn(("/api/v1/tasks/{id}/pause", "denied", 403), outcomes)

    def test_operations_reads_create_no_work_and_only_normalized_audit(self) -> None:
        self.repository.create_task(self.task("task-a", rank=0))
        self.repository.create_job(self.job("job-a", rank=0))
        before = self.state_counts()
        audit_before = len(self.repository.list_security_audit(limit=500))

        reads = (
            ("/api/v1/tasks", ""),
            ("/api/v1/tasks", "status=completed&command=preview&limit=1"),
            ("/api/v1/tasks/task-a", ""),
            ("/api/v1/jobs", "status=pending"),
            ("/api/v1/jobs/job-a", ""),
            ("/api/v1/workers", ""),
            ("/api/v1/workers/readiness", ""),
        )
        for path, query in reads:
            status, _, _ = request(self.api, "GET", path, query=query)
            self.assertEqual(status, 200)

        self.assertEqual(self.state_counts(), before)
        audit_after = self.repository.list_security_audit(limit=500)
        added = {item.route for item in audit_after}
        self.assertLessEqual(len(audit_after) - audit_before, len(reads))
        self.assertNotIn("task-a", json.dumps(sorted(added)))
        self.assertNotIn("job-a", json.dumps(sorted(added)))

    def test_lifecycle_routes_reject_unknown_objects_and_queries(self) -> None:
        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/missing/pause",
            body=control_body(NOW.isoformat()),
        )
        self.assertEqual(status, 404)

        self.repository.create_task(
            self.task("task-run", status=PersistentTaskStatus.RUNNING, rank=0)
        )
        task = self.repository.get_task("task-run")
        status, _, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-run/pause",
            query="force=true",
            body=control_body(task.updated_at.isoformat()),
        )
        self.assertEqual(status, 400)
        status, _, _ = request(self.api, "GET", "/api/v1/tasks/task-run/pause")
        self.assertEqual(status, 404)


class OperationsControlFencingTests(unittest.TestCase):
    """Deterministic proof for atomic controls and real handler cooperation.

    Every accepted transition is one compare-and-set over the exact durable
    state the operator read; an accepted cancellation is observed by the owning
    execution path at its own item boundary, never by releasing confinement for
    work that is still in flight, and never overwritten by a later completion.
    """

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.api = MediaFlowApi(
            self.repository,
            None,
            principals=(VIEWER, OPERATOR, AUDITOR),
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def running_task(self, task_id: str, *, command: str = "preview", execute: bool = False):
        task = PersistentTask(
            task_id,
            command,
            PersistentTaskStatus.RUNNING,
            execute,
            NOW,
            NOW,
            started_at=NOW,
        )
        self.repository.create_task(task)
        return task

    def concurrent_control(self, path: str, version: str) -> list[int]:
        """Submit the identical control from two threads behind one barrier."""

        barrier = threading.Barrier(2)
        statuses: list[int] = []
        lock = threading.Lock()

        def submit() -> None:
            barrier.wait(5)
            code, _, _ = request(self.api, "POST", path, body=control_body(version))
            with lock:
                statuses.append(code)

        threads = [threading.Thread(target=submit) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        return sorted(statuses)

    def test_concurrent_pause_submissions_admit_exactly_one(self) -> None:
        self.running_task("task-pause")
        version = self.repository.get_task("task-pause").updated_at.isoformat()

        self.assertEqual(
            self.concurrent_control("/api/v1/tasks/task-pause/pause", version),
            [200, 409],
        )
        task = self.repository.get_task("task-pause")
        self.assertTrue(task.pause_requested)
        self.assertEqual(task.status, PersistentTaskStatus.RUNNING)

        # A further submission against the now-current version is refused for the
        # durable reason instead of storing the request twice.
        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/task-pause/pause",
            body=control_body(task.updated_at.isoformat()),
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["details"]["reason"], "already_requested")

    def test_concurrent_cancel_submissions_admit_exactly_one(self) -> None:
        self.running_task("task-cancel", execute=True)
        version = self.repository.get_task("task-cancel").updated_at.isoformat()

        self.assertEqual(
            self.concurrent_control("/api/v1/tasks/task-cancel/cancel", version),
            [200, 409],
        )
        task = self.repository.get_task("task-cancel")
        self.assertEqual(task.status, PersistentTaskStatus.CANCELLED)

    def test_concurrent_job_cancel_submissions_admit_exactly_one(self) -> None:
        job = AutomationJobService(self.repository).submit("scan")
        version = job.updated_at.isoformat()

        self.assertEqual(
            self.concurrent_control(f"/api/v1/jobs/{job.job_id}/cancel", version),
            [200, 409],
        )
        persisted = self.repository.get_job(job.job_id)
        self.assertTrue(persisted.cancellation_requested)

    def test_accepted_cancel_keeps_the_in_flight_lock_and_is_never_overwritten(self) -> None:
        task = self.running_task("task-live", command="organize", execute=True)
        coordinator = PersistentTaskCoordinator(self.repository, self.repository)
        in_flight = coordinator.begin_item(
            task.task_id, "source", "movies", "movie.mkv", "source:movie.mkv"
        )
        # A second lock of the same Task belongs to no in-flight item.
        self.assertTrue(self.repository.acquire("source", "queued.mkv", task.task_id, NOW))
        version = self.repository.get_task(task.task_id).updated_at.isoformat()

        status, body, _ = request(
            self.api,
            "POST",
            f"/api/v1/tasks/{task.task_id}/cancel",
            body=control_body(version),
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["task"]["status"], "cancelled")
        self.assertTrue(body["task"]["execute_authorized"])
        # The in-flight source lock is preserved; the idle one is released.
        self.assertTrue(self.repository.lock_owned("source", "movie.mkv", task.task_id))
        self.assertFalse(self.repository.lock_owned("source", "queued.mkv", task.task_id))
        self.assertEqual(
            self.repository.get_item(in_flight.item_id).status,
            TaskItemStatus.CANCELLED,
        )

        # The owning handler observes the durable cancellation at its item
        # boundary and records the outcome of the item it was already running.
        self.assertTrue(coordinator.cancellation_observed(task.task_id))
        execution = ExecutionResult(
            ExecutionStatus.SUCCESS,
            PlanOperation.MOVE,
            "movie.mkv",
            "Movies/movie.mkv",
            completed_operations=("MOVE",),
            effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
        )
        coordinator.complete_item(
            in_flight,
            MediaOrganizerItemResult("movie.mkv", execution=execution),
        )
        self.assertFalse(self.repository.lock_owned("source", "movie.mkv", task.task_id))
        self.assertEqual(self.repository.get_item(in_flight.item_id).status, TaskItemStatus.SUCCESS)

        # A later completion can never resurrect the durable cancellation.
        finished = coordinator.finish(task.task_id, MediaOrganizerBatchResult(()))
        self.assertEqual(finished.status, PersistentTaskStatus.CANCELLED)
        self.assertEqual(finished.completed_at.isoformat(), body["task"]["completed_at"])
        self.assertEqual(
            self.repository.get_task(task.task_id).status,
            PersistentTaskStatus.CANCELLED,
        )

    def test_pause_is_withheld_for_a_manual_scan_task(self) -> None:
        task = PersistentTask(
            "scan-task",
            "scan",
            PersistentTaskStatus.RUNNING,
            False,
            NOW,
            NOW,
            started_at=NOW,
            configuration_snapshot_id="snap-1",
            configuration_snapshot_digest="digest-1",
        )
        # The manual Scan service owns the Task row and its discovery scope row
        # in one transaction.
        self.repository.create_manual_scan(
            task,
            ManualScanTask(
                task.task_id,
                ManualScanScopeKind.RESOURCE_LIBRARY,
                "movies",
                ScanMode.FULL,
                PersistentTaskStatus.RUNNING,
                "snap-1",
                "digest-1",
                NOW,
                NOW,
            ),
        )

        status, detail, _ = request(self.api, "GET", "/api/v1/tasks/scan-task")
        self.assertEqual(status, 200)
        lifecycle = detail["lifecycle"]
        self.assertEqual(lifecycle["executionPath"], "manual_scan")
        pause = next(item for item in lifecycle["actions"] if item["action"] == "pause")
        self.assertFalse(pause["available"])
        self.assertIn("never acknowledges a Task pause request", pause["unavailableReason"])
        # The manual Scan service observes its own cooperative cancellation.
        cancel = next(item for item in lifecycle["actions"] if item["action"] == "cancel")
        self.assertTrue(cancel["available"])

        status, body, _ = request(
            self.api,
            "POST",
            "/api/v1/tasks/scan-task/pause",
            body=control_body(task.updated_at.isoformat()),
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["details"]["reason"], "pause_unavailable")
        persisted = self.repository.get_task("scan-task")
        self.assertFalse(persisted.pause_requested)
        self.assertEqual(persisted.status, PersistentTaskStatus.RUNNING)

    def test_synchronously_executed_manual_organize_task_exposes_no_control(self) -> None:
        task = self.running_task("manual-run", command="manual_organize", execute=True)
        self.repository.acquire("source", "movie.mkv", task.task_id, NOW)

        status, detail, _ = request(self.api, "GET", "/api/v1/tasks/manual-run")
        self.assertEqual(status, 200)
        lifecycle = detail["lifecycle"]
        self.assertEqual(lifecycle["executionPath"], "synchronous_manual_organize")
        self.assertFalse(any(item["available"] for item in lifecycle["actions"]))

        for action in ("pause", "cancel"):
            with self.subTest(action=action):
                status, body, _ = request(
                    self.api,
                    "POST",
                    f"/api/v1/tasks/manual-run/{action}",
                    body=control_body(task.updated_at.isoformat()),
                )
                self.assertEqual(status, 409)
                self.assertEqual(body["error"]["details"]["reason"], f"{action}_unavailable")
        persisted = self.repository.get_task("manual-run")
        self.assertEqual(persisted.status, PersistentTaskStatus.RUNNING)
        self.assertTrue(persisted.execute_authorized)
        self.assertTrue(self.repository.lock_owned("source", "movie.mkv", "manual-run"))

    def test_hostile_historical_record_never_reaches_the_operations_projection(self) -> None:
        hostile_error = "Authorization: Bearer topsecret /home/alice/private.mkv"
        fingerprint = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        task = PersistentTask(
            "task-hostile",
            "preview",
            PersistentTaskStatus.FAILED,
            False,
            NOW,
            NOW,
            started_at=NOW,
            completed_at=NOW,
            total_items=1,
            completed_items=0,
            failed_items=1,
            error=hostile_error,
            configuration_snapshot_id="rev-1",
            configuration_snapshot_digest=fingerprint,
        )
        self.repository.create_task(task)
        self.repository.upsert_item(
            PersistentTaskItem(
                "item-hostile",
                task.task_id,
                "source",
                "movies",
                "movie.mkv",
                "/srv/media/private.mkv",
                TaskItemStatus.FAILED,
                "failed",
                1,
                NOW,
                NOW,
                error=hostile_error,
                source_occurrence_id="occurrence-1",
                source_fingerprint="fingerprint-value",
                source_fingerprint_state="verified",
            )
        )
        self.repository.append_result(
            PersistentResultRecord(
                "item-hostile:1",
                task.task_id,
                "item-hostile",
                "source",
                "movie.mkv",
                None,
                None,
                "A",
                "tmdb",
                "1",
                "A",
                "A",
                "A",
                "A",
                "MOVE",
                "failed",
                NOW,
                error=hostile_error,
                source_occurrence_id="occurrence-1",
                source_fingerprint="fingerprint-value",
                source_fingerprint_state="verified",
            )
        )
        self.repository.create_job(
            AutomationJob(
                "job-hostile",
                AutomationCommand.PREVIEW,
                AutomationJobStatus.FAILED,
                NOW,
                NOW,
                started_at=NOW,
                completed_at=NOW,
                error=hostile_error,
                failure_category="workflow_failed",
                failure_durable_state=hostile_error,
                failure_side_effects="none",
                failure_retry_safe=False,
                failure_next_action=hostile_error,
                definition_fingerprint="fingerprint-value",
                source_scope="/srv/media/private",
                configuration_snapshot_id="rev-1",
                configuration_snapshot_digest=fingerprint,
            )
        )
        # A syntactically valid durable failure envelope whose structured
        # fields smuggle a credential and an absolute host path: the envelope
        # must be published only after the same bounded scrubbing as every
        # other evidence branch.
        envelope = "mediaflow-failure-v1:" + json.dumps(
            {
                "category": "storage_failure",
                "message": "Authorization: Bearer topsecret",
                "durableState": "effects were recorded under /home/alice/private.mkv",
                "sideEffects": "Authorization: Bearer topsecret",
                "retrySafe": False,
                "nextAction": "inspect /home/alice/private.mkv",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.repository.create_job(
            AutomationJob(
                "job-envelope",
                AutomationCommand.PREVIEW,
                AutomationJobStatus.FAILED,
                NOW,
                NOW,
                started_at=NOW,
                completed_at=NOW,
                error=envelope,
            )
        )
        # A second item and result whose persisted identity columns hold
        # absolute host paths instead of Storage-relative identities: the
        # projection must fail closed rather than publish them.
        self.repository.upsert_item(
            PersistentTaskItem(
                "item-path",
                task.task_id,
                "source",
                "movies",
                "/home/alice/private.mkv",
                "/srv/media/display.mkv",
                TaskItemStatus.FAILED,
                "failed",
                1,
                NOW,
                NOW,
                destination_path="/home/alice/dest/private.mkv",
            )
        )
        self.repository.append_result(
            PersistentResultRecord(
                "item-path:1",
                task.task_id,
                "item-path",
                "source",
                "/home/alice/private.mkv",
                "destination",
                "/home/alice/dest/private.mkv",
                "A",
                "tmdb",
                "1",
                "A",
                "A",
                "A",
                "A",
                "MOVE",
                "failed",
                NOW,
            )
        )

        forbidden = ("topsecret", "/home/alice", "/srv/media", "fingerprint-value", fingerprint)
        operations_reads = (
            ("/api/v1/operations/tasks", ""),
            (f"/api/v1/operations/tasks/{task.task_id}", ""),
            ("/api/v1/operations/jobs", ""),
            ("/api/v1/operations/jobs/job-hostile", ""),
            ("/api/v1/operations/jobs/job-envelope", ""),
        )
        for path, query in operations_reads:
            with self.subTest(path=path):
                status, document, _ = request(self.api, "GET", path, query=query)
                self.assertEqual(status, 200)
                serialized = json.dumps(document)
                for value in forbidden:
                    self.assertNotIn(value, serialized)
                self.assertNotIn("configuration_snapshot_digest", serialized)
                self.assertNotIn('"error"', serialized)

        status, detail, _ = request(self.api, "GET", f"/api/v1/operations/tasks/{task.task_id}")
        self.assertEqual(status, 200)
        # Bounded failure evidence is still present for the operator.
        self.assertIn("failure", detail)
        self.assertIn("category", detail["failure"])
        self.assertIn("nextAction", detail["failure"])
        self.assertIn("failure", detail["items"][0])
        self.assertIn("failure", detail["results"][0])
        # The immutable revision identity stays visible as the pin evidence.
        self.assertEqual(detail["items"][0]["source_path"], "movie.mkv")
        self.assertEqual(detail["configuration_snapshot_id"], "rev-1")
        # A persisted identity column that is not a provably Storage-relative
        # identity fails closed to the redaction marker.
        hostile_items = {item["item_id"]: item for item in detail["items"]}
        self.assertEqual(hostile_items["item-path"]["source_path"], "[redacted-path]")
        self.assertEqual(hostile_items["item-path"]["destination_path"], "[redacted-path]")
        self.assertIn("failure", detail["results"][1])
        hostile_results = {result["item_id"]: result for result in detail["results"]}
        self.assertEqual(hostile_results["item-path"]["source_path"], "[redacted-path]")
        self.assertEqual(hostile_results["item-path"]["destination_path"], "[redacted-path]")
        # The decoded envelope is still published as bounded failure evidence,
        # with its credential and host-path content replaced.
        status, envelope_document, _ = request(
            self.api, "GET", "/api/v1/operations/jobs/job-envelope"
        )
        self.assertEqual(status, 200)
        self.assertEqual(envelope_document["failure"]["category"], "storage_failure")
        self.assertIn("[redacted]", envelope_document["failure"]["message"])
        self.assertIn("[redacted-path]", envelope_document["failure"]["durableState"])

        # The pre-existing compatibility document keeps its historical fields.
        # It keeps the configured display root the V1 operator UI renders and the
        # pinned configuration digest a pre-existing pin test asserts, but a
        # hostile durable error is normalized there too, so no Task/Job read
        # echoes a credential or the raw record.
        status, legacy, _ = request(self.api, "GET", f"/api/v1/tasks/{task.task_id}")
        self.assertEqual(status, 200)
        legacy_serialized = json.dumps(legacy)
        self.assertNotIn("topsecret", legacy_serialized)
        self.assertNotIn("/home/alice", legacy_serialized)
        self.assertEqual(
            legacy["items"][0]["error"],
            "scheduled organization failed at a bounded workflow boundary",
        )
        self.assertEqual(legacy["configuration_snapshot_id"], "rev-1")

    def test_operations_reads_create_no_work_and_no_fingerprint(self) -> None:
        task = self.running_task("task-read")
        self.repository.create_job(
            AutomationJob(
                "job-read",
                AutomationCommand.PREVIEW,
                AutomationJobStatus.PENDING,
                NOW,
                NOW,
            )
        )
        before = (len(self.repository.list_tasks()), len(self.repository.list_jobs()))
        reads = (
            "/api/v1/operations/tasks",
            f"/api/v1/operations/tasks/{task.task_id}",
            "/api/v1/operations/jobs",
            "/api/v1/operations/jobs/job-read",
            "/api/v1/operations/workers",
            "/api/v1/operations/workers/readiness",
        )
        for path in reads:
            with self.subTest(path=path):
                status, document, _ = request(self.api, "GET", path)
                self.assertEqual(status, 200)
                serialized = json.dumps(document)
                self.assertNotIn("digest", serialized)
                self.assertNotIn("fingerprint", serialized)
        self.assertEqual(
            (len(self.repository.list_tasks()), len(self.repository.list_jobs())), before
        )
        routes = self.audit_routes()
        self.assertIn("/api/v1/operations/tasks", routes)
        self.assertIn("/api/v1/operations/tasks/{id}", routes)
        self.assertIn("/api/v1/operations/workers/readiness", routes)
        self.assertNotIn(task.task_id, json.dumps(routes))

    def test_worker_reports_a_web_cancelled_task_as_a_cancelled_job(self) -> None:
        task = self.running_task("task-worker", command="scan")
        version = self.repository.get_task(task.task_id).updated_at.isoformat()
        status, _, _ = request(
            self.api,
            "POST",
            f"/api/v1/tasks/{task.task_id}/cancel",
            body=control_body(version),
        )
        self.assertEqual(status, 200)

        # The queued-workflow wrapper refuses to report a Job as completed once
        # the durable Task carries an operator-accepted cancellation, and the
        # definition-scoped runner uses the same coordinator observation.
        self.assertTrue(_task_was_cancelled(self.repository, task.task_id))
        self.assertTrue(
            PersistentTaskCoordinator(self.repository, self.repository).cancellation_observed(
                task.task_id
            )
        )

    def audit_routes(self) -> list[str]:
        return [item.route for item in self.repository.list_security_audit(limit=400)]


if __name__ == "__main__":
    unittest.main()
