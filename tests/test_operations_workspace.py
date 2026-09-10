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
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.automation import AutomationJobService
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
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


if __name__ == "__main__":
    unittest.main()
