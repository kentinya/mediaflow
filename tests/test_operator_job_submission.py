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


class RetiredDryRunJobSubmissionTests(unittest.TestCase):
    """The legacy Download/DryRun Job submission command is retired.

    Only the explicit one-shot Organize authority may admit a Job.  An ordinary
    principal with ``SUBMIT_DRY_RUN`` must get an ordinary permission refusal,
    and no Job may be created by any refused request.
    """

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

    def test_retired_job_commands_are_ordinary_refusals_without_admission(self) -> None:
        status, denied = request(self.api, {"command": "organize"}, token="viewer-token")
        self.assertEqual(status, 403)
        self.assertEqual(denied["error"]["code"], "forbidden")
        for document in (
            {"command": "preview"},
            {"command": "scan"},
            {"command": "organize"},
            {"command": "organize", "limit": 1},
        ):
            with self.subTest(document=document):
                status, body = request(self.api, document)
                self.assertIn(status, (400, 403), body)
                self.assertNotIn("job_id", body)
        self.assertEqual(self.repository.list_jobs(), ())
        routes = [item.route for item in self.repository.list_security_audit()]
        self.assertIn("/api/v1/jobs", routes)

    def test_invalid_documents_and_query_create_zero_jobs(self) -> None:
        invalid = [
            {},
            {"command": "preview"},
            {"command": "scan"},
            {"command": "organize"},
            {"command": "organize", "execute": False},
            {"command": "organize", "limit": True},
            {"command": "organize", "limit": 0},
            {"command": "organize", "limit": -1},
            {"command": "organize", "limit": 10_001},
            {"command": "organize", "path": "/private"},
            {"command": "organize", "task": "task-1"},
            {"command": "organize", "actor": "admin"},
            {"command": "organize", "policy": "A"},
            {"command": "organize", "storage": "source"},
            {"command": "organize", "schedule": "nightly"},
            {"command": "organize", "overwrite": False},
            {"command": "organize", "delete": False},
        ]
        for document in invalid:
            with self.subTest(document=document):
                self.assertIn(request(self.api, document)[0], (400, 403))
        self.assertIn(request(self.api, {"command": "organize"}, query="limit=1")[0], (400, 403))
        self.assertEqual(request(self.api, None, raw_body=b"{")[0], 400)
        self.assertEqual(self.repository.list_jobs(), ())

    def test_ui_has_one_queue_job_surface_with_organize_review(self) -> None:
        script = APP_JS.decode()
        self.assertIn("Queue Job", script)
        self.assertNotIn("Queue DryRun job", script)
        self.assertNotIn("['preview', 'organize']", script)
        self.assertIn("['organize']", script)
        self.assertIn("Review Job", script)
        self.assertNotIn("Review DryRun job", script)
        self.assertIn("Confirm Organize", script)
        self.assertIn("Back without queueing", script)
        self.assertIn("Keep jobs unchanged", script)
        self.assertIn("Object.freeze", script)
        self.assertIn("['Authority', 'REMOTE_EXECUTE (one-shot)']", script)
        self.assertIn("['Storage mutation', 'POSSIBLE']", script)
        self.assertIn("execute: true", script)
        self.assertIn("limit.max = '10000'", script)
        self.assertIn("body: JSON.stringify(payload)", script)
        self.assertIn("await renderObservability('jobs'); await showJob(created.job_id)", script)
        self.assertNotIn("window.confirm", script)
        self.assertNotIn("HTTP_X_MEDIAFLOW_EXECUTION_TOKEN", script)
        # The Queue Job submission journey must never request overwrite authority or
        # carry an execution token; the guided OrganizePolicy configuration section
        # legitimately displays overwrite read-only.
        submission = "".join(
            _js_function_body(script, name)
            for name in ("showQueueJobForm", "reviewQueueJob", "submitQueueJob")
        )
        self.assertNotIn("overwrite", submission.casefold())
        self.assertNotIn("delete", submission.casefold())
        self.assertNotIn("overwrite:", script)
        self.assertNotIn("preview", submission.casefold())


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
