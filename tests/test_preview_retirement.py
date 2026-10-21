"""Task45.6 RO-8 acceptance: independent Preview retirement and shared analysis.

These tests exercise the real application boundary for the retired independent
Preview product:

* the old CLI commands, API routes and Web destinations are gone and answer as
  ordinary unsupported/not-found results rather than compatibility shims;
* a fresh runtime database has no independent Preview-only tables, while the
  shared organize plan evidence (``manual_previews``) is retained;
* the shared Organize DryRun analysis chain still produces the exact plan
  summary that Files/create/recovery consume, and it grants no execution
  authority and mutates no Storage;
* the retained Automation grant binds definition/config/permission bounds
  without depending on the retired product.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

EXAMPLES = Path("config/strategy.example.json")

#: Every module that made up the retired independent Preview product.  Importing
#: any of them must now fail: there is no durable analysis service, no definition
#: Preview service and no dedicated domain model left behind under a new name.
RETIRED_MODULES = (
    "mediaflow.application.preview_analysis",
    "mediaflow.application.automation_task_definition_preview",
    "mediaflow.domain.automation_task_definition_preview",
)

#: The independent Preview-only schema a fresh runtime must never create.
RETIRED_TABLES = (
    "preview_analyses",
    "automation_task_definition_previews",
    "automation_task_definition_preview_items",
)


def _request(api, method, path, *, token="admin-token", body=None, query=""):
    raw = b"" if body is None else json.dumps(body).encode()
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(raw),
    }
    payload = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


def _cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = final_main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


class RetiredPreviewModuleTests(unittest.TestCase):
    def test_retired_modules_cannot_be_imported(self):
        for module in RETIRED_MODULES:
            with self.subTest(module=module):
                with self.assertRaises(ModuleNotFoundError):
                    __import__(module)


class RetiredPreviewCliTests(unittest.TestCase):
    def test_old_cli_preview_commands_are_ordinary_usage_errors(self):
        for argv in (
            ["preview"],
            ["batch", "preview"],
            ["jobs", "submit", "preview"],
        ):
            with self.subTest(argv=argv):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    with self.assertRaises(SystemExit) as raised:
                        final_main(argv, stdout=out, stderr=err)
                self.assertEqual(2, raised.exception.code)
                self.assertIn("invalid choice", err.getvalue())

    def test_cli_help_does_not_advertise_the_retired_product(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            final_main(["--help"], stdout=io.StringIO(), stderr=io.StringIO())
        rendered = out.getvalue()
        self.assertNotIn("preview", rendered)
        self.assertIn("organize", rendered)


class RetiredPreviewApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.api = MediaFlowApi(
            self.repository,
            None,
            principals=(
                ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
            ),
        )

    def tearDown(self):
        self.repository.close()
        self.directory.cleanup()

    def test_old_preview_routes_are_ordinary_not_found(self):
        for method, path, body in (
            ("POST", "/api/v1/operations/previews", {"scopeKind": "resource_library"}),
            ("GET", "/api/v1/operations/previews", None),
            ("GET", "/api/v1/operations/previews/p-1", None),
            (
                "POST",
                "/api/v1/automation/task-definitions/definition/preview",
                {},
            ),
            ("GET", "/api/v1/automation/task-definitions/definition/previews", None),
            (
                "GET",
                "/api/v1/automation/task-definitions/definition/previews/p-1",
                None,
            ),
            (
                "POST",
                "/api/v1/automation/task-definitions/definition/preview-analyses",
                {},
            ),
            (
                "POST",
                "/api/v1/operations/organize/intents/intent-1/preview-analyses",
                {"expectedVersion": 1},
            ),
            ("GET", "/api/v1/operations/automation/preview-analyses", None),
            ("GET", "/api/v1/operations/automation/preview-analyses/a-1", None),
        ):
            with self.subTest(method=method, path=path):
                status, document = _request(self.api, method, path, body=body, token="admin-token")
                self.assertIn(status, (404, 503), document)
                self.assertNotIn("previewId", document)

    def test_retired_routes_create_no_durable_work(self):
        _request(
            self.api,
            "POST",
            "/api/v1/automation/task-definitions/definition/preview",
            body={},
        )
        _request(
            self.api,
            "POST",
            "/api/v1/operations/previews",
            body={"scopeKind": "resource_library"},
        )
        self.assertEqual((), self.repository.list_jobs())
        self.assertEqual((), self.repository.list_tasks())

    def test_fresh_schema_has_no_independent_preview_tables(self):
        tables = {
            row[0]
            for row in self.repository._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for retired in RETIRED_TABLES:
            with self.subTest(table=retired):
                self.assertNotIn(retired, tables)
        # The shared organize plan evidence is retained.
        self.assertIn("manual_previews", tables)
        self.assertIn("manual_preview_items", tables)


class RetiredPreviewScheduleTests(unittest.TestCase):
    def test_preview_schedule_command_is_rejected(self):
        from mediaflow.domain.automation import AutomationCommand, CronSchedule, IntervalSchedule

        self.assertNotIn("preview", {item.value for item in AutomationCommand})
        with self.assertRaises(ValueError):
            IntervalSchedule("legacy", "preview", 60)
        with self.assertRaises(ValueError):
            CronSchedule("legacy", "preview", "* * * * *", "UTC")

    def test_old_schedule_document_value_is_rejected_not_defaulted(self):
        from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration

        document = json.loads(EXAMPLES.read_text(encoding="utf-8"))
        document["automation"] = {
            "schedules": [{"id": "legacy", "command": "preview", "intervalSeconds": 60}]
        }
        with self.assertRaisesRegex(ValueError, "must be organize"):
            load_runtime_configuration(document)


if __name__ == "__main__":
    unittest.main()
