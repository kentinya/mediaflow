from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.automation import AutomationJobService
from mediaflow.domain.automation import AutomationJobStatus, job_control_version
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi


def principal(name: str, token: str, permissions) -> ResolvedApiPrincipal:
    return ResolvedApiPrincipal(name, token, frozenset(permissions))


def request(api, method: str, path: str, *, token: str, query: str = "", body: bytes = b""):
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(body),
    }
    response = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(response)


class OperatorJobCancellationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.viewer = principal("viewer", "viewer-token", {ApiPermission.READ})
        self.operator = principal(
            "operator",
            "operator-token",
            {ApiPermission.READ, ApiPermission.CANCEL_JOB},
        )
        self.api = MediaFlowApi(self.repository, None, principals=(self.viewer, self.operator))

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_pending_and_running_cancellation_reuse_existing_service(self) -> None:
        service = AutomationJobService(self.repository)
        running = service.submit("scan")
        pending = service.submit("preview")
        self.repository.claim_next_job(datetime.now(UTC))

        status, denied = request(
            self.api,
            "POST",
            f"/api/v1/jobs/{pending.job_id}/cancel",
            token="viewer-token",
        )
        self.assertEqual(status, 403)
        self.assertEqual(denied["error"]["code"], "forbidden")

        status, cancelled = request(
            self.api,
            "POST",
            f"/api/v1/jobs/{pending.job_id}/cancel",
            token="operator-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(cancelled["status"], "cancelled")
        status, requested = request(
            self.api,
            "POST",
            f"/api/v1/jobs/{running.job_id}/cancel",
            token="operator-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(requested["status"], "running")
        self.assertTrue(requested["cancellation_requested"])
        audit_routes = [item.route for item in self.repository.list_security_audit()]
        self.assertIn("/api/v1/jobs/{id}/cancel", audit_routes)
        self.assertNotIn(pending.job_id, json.dumps(audit_routes))
        self.assertNotIn(running.job_id, json.dumps(audit_routes))

    def test_cancel_contract_rejects_method_query_body_and_bad_path(self) -> None:
        job = AutomationJobService(self.repository).submit("scan")
        path = f"/api/v1/jobs/{job.job_id}/cancel"
        self.assertEqual(request(self.api, "GET", path, token="operator-token")[0], 405)
        self.assertEqual(
            request(self.api, "POST", path, token="operator-token", query="execute=true")[0],
            400,
        )
        self.assertEqual(
            request(self.api, "POST", path, token="operator-token", body=b"{}")[0], 400
        )
        self.assertEqual(request(self.api, "POST", path + "/extra", token="operator-token")[0], 404)
        self.assertEqual(self.repository.get_job(job.job_id).status.value, "pending")

    def test_terminal_commit_cannot_overwrite_an_accepted_running_cancellation(self) -> None:
        """The exact cancel-versus-completion boundary B demonstrated.

        A claimed running Job's cancellation is durably accepted first; the
        already-in-flight workflow then submits itself as COMPLETED through
        ``complete_claimed_job``.  The accepted request must win: the row
        becomes cancelled, stays cancelled and keeps the request flag, so a
        late completion can never be reported as success.
        """

        service = AutomationJobService(self.repository)
        service.submit("scan")
        claimed = self.repository.claim_next_job(datetime.now(UTC))
        assert claimed is not None
        self.repository.request_job_cancellation(
            claimed.job_id,
            datetime.now(UTC),
            expected_version=job_control_version(claimed),
        )
        running = self.repository.get_job(claimed.job_id)
        self.assertEqual(running.status, AutomationJobStatus.RUNNING)
        self.assertTrue(running.cancellation_requested)
        finished = replace(
            claimed,
            status=AutomationJobStatus.COMPLETED,
            completed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            task_id="task-completed",
        )
        self.assertTrue(self.repository.complete_claimed_job(finished))
        persisted = self.repository.get_job(claimed.job_id)
        self.assertEqual(persisted.status, AutomationJobStatus.CANCELLED)
        self.assertTrue(persisted.cancellation_requested)
        self.assertEqual(persisted.task_id, "task-completed")
        self.assertIsNone(persisted.claim_token)

    def test_terminal_commit_folds_an_accepted_cancellation_across_two_connections(self) -> None:
        """The exact interleaving B demonstrated, across real connections.

        One connection owns the Worker's terminal commit; a second connection
        over the same database durably accepts the cancellation while the
        Worker is between reading the row and writing its terminal outcome.
        The fold must happen inside the single terminal UPDATE statement
        itself, so no read-then-write seam exists to lose the request: the
        row becomes ``cancelled`` with the request flag kept, and the terminal
        commit is still reported as accepted.
        """

        worker = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        try:
            service = AutomationJobService(self.repository)
            service.submit("scan")
            claimed = worker.claim_next_job(datetime.now(UTC))
            assert claimed is not None
            # The second connection durably accepts the cancellation for the
            # exact state the Worker last observed.
            self.repository.request_job_cancellation(
                claimed.job_id,
                datetime.now(UTC),
                expected_version=job_control_version(claimed),
            )
            accepted = self.repository.get_job(claimed.job_id)
            self.assertEqual(accepted.status, AutomationJobStatus.RUNNING)
            self.assertTrue(accepted.cancellation_requested)
            # The Worker's own connection then submits the already-in-flight
            # workflow as COMPLETED, exactly as B's paused interleaving did.
            finished = replace(
                claimed,
                status=AutomationJobStatus.COMPLETED,
                completed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                task_id="task-completed",
            )
            self.assertTrue(worker.complete_claimed_job(finished))
            persisted = worker.get_job(claimed.job_id)
            self.assertEqual(persisted.status, AutomationJobStatus.CANCELLED)
            self.assertTrue(persisted.cancellation_requested)
            self.assertEqual(persisted.task_id, "task-completed")
            self.assertIsNone(persisted.claim_token)
            # The other connection sees the same durable folded outcome.
            self.assertEqual(
                self.repository.get_job(claimed.job_id).status, AutomationJobStatus.CANCELLED
            )
        finally:
            worker.close()

    def test_failed_terminal_commit_also_cannot_overwrite_an_accepted_cancellation(self) -> None:
        service = AutomationJobService(self.repository)
        service.submit("preview")
        claimed = self.repository.claim_next_job(datetime.now(UTC))
        assert claimed is not None
        self.repository.request_job_cancellation(
            claimed.job_id,
            datetime.now(UTC),
            expected_version=job_control_version(claimed),
        )
        failed = replace(
            claimed,
            status=AutomationJobStatus.FAILED,
            completed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            task_id="task-failed",
            error="workflow failed (RuntimeError)",
            failure_category="workflow_failed",
            failure_durable_state="the run failed at a bounded boundary",
            failure_retry_safe=False,
            failure_next_action="inspect the linked Task",
        )
        self.assertTrue(self.repository.complete_claimed_job(failed))
        persisted = self.repository.get_job(claimed.job_id)
        self.assertEqual(persisted.status, AutomationJobStatus.CANCELLED)
        self.assertTrue(persisted.cancellation_requested)
        # The workflow's own failure evidence stays truthful; only the status
        # and the accepted request flag are fenced.
        self.assertEqual(persisted.error, "workflow failed (RuntimeError)")
        self.assertEqual(persisted.failure_category, "workflow_failed")

    def test_ui_is_two_step_terminal_safe_and_does_not_add_execution_controls(self) -> None:
        script = APP_JS.decode()
        self.assertIn("data.status === 'pending' || data.status === 'running'", script)
        self.assertIn("Request cancellation", script)
        self.assertIn("Confirm cancellation", script)
        self.assertIn("Keep job", script)
        self.assertIn("() => confirmation.remove()", script)
        self.assertIn("{method: 'POST'}", script)
        self.assertNotIn("window.confirm", script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("/api/v1/tasks/${encodeURIComponent(id)}/resume", script)
        # The job detail and cancellation journey must never request execution or
        # name overwrite authority; the guided OrganizePolicy configuration section
        # and the explicit Queue Job Organize review (validated separately) may.
        cancellation = "".join(
            _js_function_body(script, name)
            for name in ("showJob", "confirmJobCancellation", "cancelJob")
        )
        self.assertNotIn("execute", cancellation.casefold())
        self.assertNotIn("overwrite", cancellation.casefold())
        self.assertNotIn("overwrite:", script)


def _js_function_body(script: str, name: str) -> str:
    """Return one JS function body from the served asset by brace matching."""

    opening = script.index("{", script.index(f"function {name}("))
    depth = 0
    for index in range(opening, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[opening + 1 : index]
    raise AssertionError("JavaScript block has an unbalanced body")


if __name__ == "__main__":
    unittest.main()
