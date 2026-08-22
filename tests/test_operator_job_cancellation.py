from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.automation import AutomationJobService
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
        self.assertNotIn("execute: true", script)
        self.assertNotIn("overwrite", script.casefold())


if __name__ == "__main__":
    unittest.main()
