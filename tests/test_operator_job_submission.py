from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi


def principal(name: str, token: str, permissions) -> ResolvedApiPrincipal:
    return ResolvedApiPrincipal(name, token, frozenset(permissions))


def request(
    api,
    document,
    *,
    token: str = "operator-token",
    query: str = "",
    raw_body: bytes | None = None,
):
    body = json.dumps(document).encode() if raw_body is None else raw_body
    statuses = []
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/v1/jobs",
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(body),
    }
    response = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(response)


class OperatorJobSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        viewer = principal("viewer", "viewer-token", {ApiPermission.READ})
        operator = principal(
            "operator",
            "operator-token",
            {ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN},
        )
        self.api = MediaFlowApi(self.repository, None, principals=(viewer, operator))

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_scan_preview_optional_bounded_limit_and_rbac(self) -> None:
        status, denied = request(self.api, {"command": "scan"}, token="viewer-token")
        self.assertEqual(status, 403)
        self.assertEqual(denied["error"]["code"], "forbidden")
        for document in (
            {"command": "scan"},
            {"command": "preview", "limit": 1},
            {"command": "scan", "limit": 10_000},
        ):
            with self.subTest(document=document):
                status, created = request(self.api, document)
                self.assertEqual(status, 202)
                self.assertEqual(created["command"], document["command"])
                self.assertEqual(created["limit"], document.get("limit"))
                self.assertFalse(created["execute_authorized"])
        self.assertEqual(len(self.repository.list_jobs()), 3)
        routes = [item.route for item in self.repository.list_security_audit()]
        self.assertIn("/api/v1/jobs", routes)
        self.assertNotIn("preview", json.dumps(routes))
        self.assertNotIn("10000", json.dumps(routes))

    def test_invalid_documents_and_query_create_zero_jobs(self) -> None:
        invalid = [
            {},
            {"command": "organize"},
            {"command": "preview", "execute": False},
            {"command": "scan", "limit": True},
            {"command": "scan", "limit": 0},
            {"command": "scan", "limit": -1},
            {"command": "scan", "limit": 10_001},
            {"command": "scan", "path": "/private"},
            {"command": "scan", "task": "task-1"},
            {"command": "scan", "actor": "admin"},
            {"command": "scan", "policy": "A"},
            {"command": "scan", "storage": "source"},
            {"command": "scan", "schedule": "nightly"},
            {"command": "scan", "overwrite": False},
            {"command": "scan", "delete": False},
        ]
        for document in invalid:
            with self.subTest(document=document):
                expected = 403 if document.get("command") == "organize" else 400
                self.assertEqual(request(self.api, document)[0], expected)
        self.assertEqual(request(self.api, {"command": "scan"}, query="limit=1")[0], 400)
        self.assertEqual(request(self.api, None, raw_body=b"{")[0], 400)
        self.assertEqual(self.repository.list_jobs(), ())

    def test_ui_has_three_steps_and_only_dryrun_request_shape(self) -> None:
        script = APP_JS.decode()
        self.assertIn("Queue DryRun job", script)
        self.assertIn("['scan', 'preview']", script)
        self.assertIn("Review DryRun job", script)
        self.assertIn("Confirm queueing", script)
        self.assertIn("Back without queueing", script)
        self.assertIn("Keep jobs unchanged", script)
        self.assertIn("Object.freeze", script)
        self.assertIn("['Authority', 'DRY_RUN']", script)
        self.assertIn("['Storage mutation', 'NONE']", script)
        self.assertIn("limit.max = '10000'", script)
        self.assertIn("body: JSON.stringify(payload)", script)
        self.assertIn("await renderObservability('jobs'); await showJob(created.job_id)", script)
        self.assertNotIn("window.confirm", script)
        self.assertNotIn("HTTP_X_MEDIAFLOW_EXECUTION_TOKEN", script)
        self.assertNotIn("execute: true", script)
        self.assertNotIn("'organize'", script)
        self.assertNotIn("overwrite", script.casefold())


if __name__ == "__main__":
    unittest.main()
