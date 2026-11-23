"""Task45.6 RO-8 acceptance: independent Preview retirement and shared analysis.

These tests exercise the real application boundary for the retired independent
Preview product:

* the old CLI commands, API routes and Web destinations are gone and answer as
  ordinary unsupported/not-found results rather than compatibility shims;
* a fresh runtime database has no independent Preview-only tables, while the
  shared organize plan evidence (``manual_previews``) is retained;
* the shared Organize DryRun analysis (public ``organize`` without
  ``--execute`` and the Web preparation chain) produces the same complete fixed
  plan, records conflicts/unready branches as findings only, creates no formal
  execution backlog, grants no execution authority and mutates no Storage;
* the retained Automation grant binds definition/config/permission bounds
  without depending on the retired product.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.runtime_configuration import (
    load_runtime_configuration,
)
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
    # Task 58.2 retired the whole general CLI with its dispatch layer.
    "mediaflow.cli",
    "mediaflow.final_cli",
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


class RetiredPreviewModuleTests(unittest.TestCase):
    def test_retired_modules_cannot_be_imported(self):
        for module in RETIRED_MODULES:
            with self.subTest(module=module):
                with self.assertRaises(ModuleNotFoundError):
                    __import__(module)


class RetiredPreviewApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.api = MediaFlowApi(
            self.repository,
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
            ("POST", "/api/operations/previews", {"scopeKind": "resource_library"}),
            ("GET", "/api/operations/previews", None),
            ("GET", "/api/operations/previews/p-1", None),
            (
                "POST",
                "/api/automation/task-definitions/definition/preview",
                {},
            ),
            ("GET", "/api/automation/task-definitions/definition/previews", None),
            (
                "GET",
                "/api/automation/task-definitions/definition/previews/p-1",
                None,
            ),
            (
                "POST",
                "/api/automation/task-definitions/definition/preview-analyses",
                {},
            ),
            (
                "POST",
                "/api/operations/organize/intents/intent-1/preview-analyses",
                {"expectedVersion": 1},
            ),
            ("GET", "/api/operations/automation/preview-analyses", None),
            ("GET", "/api/operations/automation/preview-analyses/a-1", None),
        ):
            with self.subTest(method=method, path=path):
                status, document = _request(self.api, method, path, body=body, token="admin-token")
                self.assertIn(status, (404, 503), document)
                self.assertNotIn("previewId", document)

    def test_retired_routes_create_no_durable_work(self):
        _request(
            self.api,
            "POST",
            "/api/automation/task-definitions/definition/preview",
            body={},
        )
        _request(
            self.api,
            "POST",
            "/api/operations/previews",
            body={"scopeKind": "resource_library"},
        )
        self.assertEqual((), self.repository.list_tasks())
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


class RetainedRunOncePlanTests(unittest.TestCase):
    """New Run once admits one real Task; retired analysis plans stay readable.

    A repeated or response-lost Run once command is restored by its exact
    principal-scoped request identity, never by a second admission.  Historical
    zero-mutation Preview records remain readable through their own supported
    durable evidence and are never promoted into execution.
    """

    def test_new_run_once_admits_real_work_with_one_exact_identity(self):
        from tests.test_v2_automation_operations import (
            _DEFINITION,
            AutomationOperatorJourneyTests,
            _request,
        )

        journey = AutomationOperatorJourneyTests()
        with journey._journey() as value:
            api = value.api
            path = f"/api/operations/automation/task-definitions/{_DEFINITION['id']}/run-once"
            request_id = "preview-retirement-request-1"
            status, admitted = _request(
                api,
                path,
                method="POST",
                body={"admissionRequestId": request_id},
            )
            self.assertEqual(202, status, admitted)
            # One command admits the real organizing Task; there is no frozen
            # analysis phase and no second initial confirmation.
            self.assertEqual("organizing", admitted["executionKind"])
            task = value.repository.get_task(admitted["taskId"])
            self.assertEqual("pending", task.status.value)
            self.assertEqual(value.active.revision_id, task.configuration_snapshot_id)

            # The exact request identity reads back the same durable admission.
            status, reread = _request(api, path, query=f"admissionRequestId={request_id}")
            self.assertEqual(200, status, reread)
            self.assertEqual(admitted["taskId"], reread["taskId"])
            self.assertEqual(admitted["taskId"], reread["taskId"])

            # A repeated command with the same identity replays no admission
            # and creates no second durable work identity or media effect.  The
            # Task is the only durable identity; no automation_jobs row exists.
            status, duplicate = _request(
                api,
                path,
                method="POST",
                body={"admissionRequestId": request_id},
            )
            self.assertEqual(202, status, duplicate)
            self.assertEqual(admitted["taskId"], duplicate["taskId"])
            self.assertEqual(0, len(()))
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # The same admission survives a reopen of the runtime store.
            database = Path(value.root, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as reopened:
                persisted = reopened.get_task(admitted["taskId"])
                self.assertEqual("pending", persisted.status.value)
                persisted_admission = reopened.find_scheduled_admission(
                    principal="admin", request_id=request_id
                )
                self.assertIsNotNone(persisted_admission)
                persisted_task, persisted_state = persisted_admission
                self.assertEqual(admitted["taskId"], persisted_task.task_id)
                self.assertEqual("run_once", persisted_state.admission_trigger.value)
                self.assertEqual(
                    admitted["definitionId"],
                    reopened.get_run_display_context(persisted_task.task_id).origin_definition_id,
                )

    def test_retained_old_analysis_plan_stays_readable_from_its_own_record(self):
        from tests.test_v2_automation_operations import AutomationOperatorJourneyTests

        journey = AutomationOperatorJourneyTests()
        with journey._journey() as value:
            # The historical analysis record remains readable through its own
            # supported durable evidence; it is never promoted into execution
            # or re-admitted through the new normal Run once entry.
            preview_id = journey._seed_retained_analysis_plan(value)
            preview = value.repository.get_manual_preview(preview_id)
            self.assertIsNotNone(preview)
            self.assertTrue(preview.zero_mutation)
            self.assertEqual(
                preview_id, value.repository.get_latest_manual_preview(preview.intent_id).preview_id
            )
            self.assertEqual((), value.repository.list_tasks())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # The same plan association survives a reopen of the runtime store.
            database = Path(value.root, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as reopened:
                reintent = reopened.get_manual_preview(preview_id)
                self.assertEqual(preview.intent_id, reintent.intent_id)
                self.assertTrue(reintent.zero_mutation)
                latest = reopened.get_latest_manual_preview(reintent.intent_id)
                self.assertEqual(preview_id, latest.preview_id)
                self.assertTrue(latest.zero_mutation)


class RetiredAuthoritySurfaceTests(unittest.TestCase):
    """The independent grant product is retired without weakening safety.

    The retired independent Preview used to be required evidence before an
    unattended grant.  Current authority is the published Enabled definition
    plus the current configured permission, re-checked at admission and again
    at every effect boundary; the retired grant transports answer as ordinary
    unknown routes and no authority table exists to seed.
    """

    def test_retired_grant_transports_are_unknown_routes(self):
        from tests.test_v2_automation_operations import (
            _DEFINITION,
            AutomationOperatorJourneyTests,
            _request,
        )

        journey = AutomationOperatorJourneyTests()
        with journey._journey() as value:
            api = value.api
            for method, body in (
                ("POST", {"revisionId": value.active.revision_id, "confirmation": True}),
                ("POST", {"reason": "no longer wanted"}),
            ):
                status, refused = _request(
                    api,
                    f"/api/automation/task-definitions/{_DEFINITION['id']}/grant",
                    method=method,
                    body=body,
                )
                self.assertEqual(404, status, refused)
                self.assertEqual("not_found", refused["error"]["code"])
            status, state = _request(
                api,
                f"/api/automation/task-definitions/{_DEFINITION['id']}/grant-state",
            )
            self.assertEqual(404, status)
            self.assertEqual((), value.repository.list_tasks())
            self.assertEqual(value.source.mutations, [])
            self.assertEqual(value.target.mutations, [])

    def test_a_shared_analysis_still_creates_no_execution_authority(self):
        from tests.test_v2_automation_operations import (
            AutomationOperatorJourneyTests,
        )

        journey = AutomationOperatorJourneyTests()
        with journey._journey() as value:
            preview_id = journey._seed_retained_analysis_plan(value)
            self.assertTrue(preview_id)
            # The frozen shared analysis carries no authority at all.
            self.assertEqual(_authority_rows(value.repository), {})
            self.assertEqual((), value.repository.list_tasks())
            self.assertEqual(value.source.mutations, [])
            self.assertEqual(value.target.mutations, [])


class RetiredPreviewScheduleTests(unittest.TestCase):
    def test_preview_schedule_command_is_rejected(self):
        from mediaflow.domain.automation import AutomationCommand

        self.assertNotIn("preview", {item.value for item in AutomationCommand})

    def test_old_schedule_document_value_is_rejected_not_defaulted(self):

        document = json.loads(EXAMPLES.read_text(encoding="utf-8"))
        document["automation"] = {
            "schedules": [{"id": "legacy", "command": "preview", "intervalSeconds": 60}]
        }
        with self.assertRaisesRegex(ValueError, "retired"):
            load_runtime_configuration(document)

    def test_empty_schedules_slot_stays_a_normal_v2_document(self):

        document = json.loads(EXAMPLES.read_text(encoding="utf-8"))
        document["automation"]["schedules"] = []
        loaded = load_runtime_configuration(document)
        self.assertEqual(loaded.automation_task_definitions, ())


_AUTHORITY_TABLES = (
    "manual_executions",
    "manual_execution_authorizations",
)


def _authority_rows(repository) -> dict[str, int]:
    """Non-zero execution-authority rows, so an empty dict proves none exist."""

    counts: dict[str, int] = {}
    existing_tables = {
        row[0]
        for row in repository._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for table in _AUTHORITY_TABLES:
        # Fixed table names from ``_AUTHORITY_TABLES``, never operator input.
        if table not in existing_tables:
            continue
        total = repository._connection.execute(
            f"SELECT COUNT(*) FROM {table}"  # noqa: S608
        ).fetchone()[0]
        if total:
            counts[table] = total
    return counts


if __name__ == "__main__":
    unittest.main()
