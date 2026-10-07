"""Task 43.1 — native V2 Automation definition lifecycle over the real API.

These tests drive the real ``MediaFlowApi`` against a real managed configuration
runtime and prove the focused publication surface:

* one checked Save/lifecycle command per intended change, with backend
  permissions, optimistic concurrency and durable readback;
* published/enabled/granted/ready stay distinct, and a new/copied definition
  starts disabled with no authority;
* removal revokes future unattended authority and retains history;
* direct POST cannot bypass an unavailable UI action, and 401/403 fail closed;
* reads and schedule preview are zero-side-effect.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.unattended_execution import UnattendedExecutionGrantService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

BASE = "/api/v1/operations/automation/definitions"
ADMIN_TOKEN = "automation-lifecycle-admin"
VIEWER_TOKEN = "automation-lifecycle-viewer"
MANAGER_TOKEN = "automation-lifecycle-manager"

_DIGEST_KEYS = (
    "definitionFingerprint",
    "definitionCurrentFingerprint",
    "sourceFingerprint",
    "planFingerprint",
)
_FORBIDDEN_SUBSTRINGS = ("Bearer ", "apiKey", "authorization:", "executionPlan")


def _assert_operator_document_clean(document: object) -> None:
    text = json.dumps(document, ensure_ascii=False)
    lowered = text.lower()
    for key in _DIGEST_KEYS:
        assert f'"{key}"' not in text, f"operator document leaked {key}"
    for substring in _FORBIDDEN_SUBSTRINGS:
        assert substring.lower() not in lowered, f"operator document leaked {substring}"
    if isinstance(document, dict):
        for value in document.values():
            _assert_operator_document_clean(value)
    elif isinstance(document, list):
        for value in document:
            _assert_operator_document_clean(value)


def _document(root: Path) -> dict:
    value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    value["storages"][0]["rootPath"] = str(root / "source")
    value["storages"][1]["rootPath"] = str(root / "target")
    return value


def _definition(definition_id: str = "nightly", **overrides) -> dict:
    value = {
        "id": definition_id,
        "name": f"Automation {definition_id}",
        "resourceLibraryId": "source",
        "mode": "scan-only",
        "intervalSeconds": 3600,
        "itemLimit": 10,
    }
    value.update(overrides)
    return value


class AutomationLifecycleApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "source").mkdir(parents=True)
        (self.root / "target").mkdir(parents=True)
        self.environment = patch.dict(
            os.environ,
            {"TMDB_ACCESS_TOKEN": "sentinel-tmdb", "OPENLIST_TOKEN": "sentinel-openlist"},
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

        self.repository = SQLiteConfigurationRepository(self.root / "configuration.sqlite3")
        self.addCleanup(self.repository.close)
        self.runtime = SQLiteTaskRepository(str(self.root / "runtime.sqlite3"))
        self.addCleanup(self.runtime.close)
        self.document = _document(self.root)
        self.managed = ManagedConfigurationService(
            self.repository,
            bootstrap_database_path=str(self.root / "runtime.sqlite3"),
        )
        self.objects = ConfigurationObjectService(
            self.managed,
            metadata_provider_registry_factory=self._forbidden_provider_factory,
        )
        self.grants = UnattendedExecutionGrantService(self.runtime, permission_authority=None)
        draft = self.managed.import_draft(self.document, actor="tester")
        validated = self.managed.validate(draft.revision_id, actor="tester")
        self.managed.activate(
            validated.revision_id, expected_version=validated.version, actor="tester"
        )
        self.api = MediaFlowApi(
            self.runtime,
            None,
            principals=(
                ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                ResolvedApiPrincipal("viewer", VIEWER_TOKEN, frozenset({ApiPermission.READ})),
                ResolvedApiPrincipal(
                    "manager",
                    MANAGER_TOKEN,
                    frozenset({ApiPermission.READ, ApiPermission.MANAGE_CONFIGURATION}),
                ),
            ),
            configuration_service=self.managed,
            bootstrap_document=self.document,
        )

    def _forbidden_provider_factory(self, provider_ids):
        raise AssertionError("Automation definition commands must not construct a Provider")

    def request(
        self,
        method: str,
        path: str,
        body: object | None = None,
        *,
        token: str = ADMIN_TOKEN,
        query: str = "",
    ):
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_LENGTH": str(len(payload)),
            "wsgi.input": io.BytesIO(payload),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        result = b"".join(self.api(environ, lambda status, _headers: statuses.append(status)))
        return int(statuses[0].split()[0]), (json.loads(result) if result else {})

    def authority(self) -> dict:
        active = self.managed.active()
        assert active is not None
        return {
            "expectedRevisionId": active.revision_id,
            "expectedVersion": active.revision_sequence or active.version,
            "expectedDigest": active.digest,
        }

    def ids(self) -> list[str]:
        active = self.managed.active()
        assert active is not None
        return [item["id"] for item in active.document.get("automationTaskDefinitions", [])]

    # -- reads -----------------------------------------------------------

    def test_form_authority_is_bounded_and_secret_free(self) -> None:
        status, body = self.request("GET", BASE)
        self.assertEqual(status, 200)
        _assert_operator_document_clean(body)
        self.assertEqual(body["active"]["revisionId"], self.managed.active().revision_id)
        self.assertIn("resourceLibraryId", body["fields"])
        self.assertEqual(body["resourceLibraries"][0]["id"], "source")
        self.assertIn("scan-only", body["enums"]["modes"])
        self.assertEqual(body["actions"]["remove"], True)

    def test_edit_and_removal_projections_are_read_only(self) -> None:
        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        revisions_before = len(self.repository.list_revisions())
        status, body = self.request("GET", f"{BASE}/nightly")
        self.assertEqual(status, 200)
        self.assertEqual(body["definition"]["id"], "nightly")
        self.assertEqual(body["definitionState"], "active")
        status, impact = self.request("GET", f"{BASE}/nightly/removal-impact")
        self.assertEqual(status, 200)
        self.assertEqual(impact["definition"]["id"], "nightly")
        self.assertEqual(impact["unattendedAuthority"]["status"], "none")
        self.assertEqual(len(self.repository.list_revisions()), revisions_before)

    def test_schedule_preview_is_zero_mutation(self) -> None:
        revisions_before = len(self.repository.list_revisions())
        jobs_before = len(self.runtime.list_jobs())
        status, body = self.request(
            "POST",
            f"{BASE}/schedule-preview",
            {
                "candidate": _definition(
                    "nightly", intervalSeconds=None, cron="0 8 * * *", timezone="UTC"
                ),
                "objectId": "nightly",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["scheduleType"], "cron")
        self.assertTrue(body["zeroMutation"])
        self.assertEqual(len(body["upcoming"]), 5)
        self.assertEqual(len(self.repository.list_revisions()), revisions_before)
        self.assertEqual(len(self.runtime.list_jobs()), jobs_before)
        self.assertEqual(self.ids(), [])

    # -- commands --------------------------------------------------------

    def test_create_edit_toggle_copy_and_remove_publish_exactly(self) -> None:
        status, created = self.request("POST", BASE, {**self.authority(), "object": _definition()})
        self.assertEqual(status, 200)
        self.assertEqual(created["action"], "create")
        self.assertEqual(created["definition"]["id"], "nightly")
        self.assertIs(created["definition"]["enabled"], False)
        _assert_operator_document_clean(created)

        status, edited = self.request(
            "PUT",
            f"{BASE}/nightly",
            {**self.authority(), "object": {"id": "nightly", "name": "Renamed"}},
        )
        self.assertEqual(status, 200)
        self.assertEqual(edited["definition"]["name"], "Renamed")
        # Unexposed fields survive the focused edit.
        self.assertEqual(edited["definition"]["itemLimit"], 10)

        status, enabled = self.request("POST", f"{BASE}/nightly/enable", self.authority())
        self.assertEqual(status, 200)
        self.assertIs(enabled["definition"]["enabled"], True)
        self.assertEqual(len(self.runtime.list_jobs()), 0)

        status, copied = self.request("POST", f"{BASE}/nightly/copy", self.authority())
        self.assertEqual(status, 200)
        self.assertEqual(copied["definition"]["id"], "nightly-copy")
        self.assertIs(copied["definition"]["enabled"], False)

        status, disabled = self.request("POST", f"{BASE}/nightly/disable", self.authority())
        self.assertEqual(status, 200)
        self.assertIs(disabled["definition"]["enabled"], False)

        status, removed = self.request("DELETE", f"{BASE}/nightly-copy", self.authority())
        self.assertEqual(status, 200)
        self.assertEqual(removed["action"], "remove")
        self.assertIsNone(removed["definition"])
        self.assertEqual(removed["removed"]["id"], "nightly-copy")
        self.assertEqual(self.ids(), ["nightly"])

    def test_removal_revokes_live_authority_and_retains_history(self) -> None:
        from datetime import UTC, datetime

        from mediaflow.domain.unattended_execution import (
            UnattendedExecutionGrant,
            UnattendedExecutionGrantAudit,
            UnattendedExecutionGrantStatus,
        )

        self.request(
            "POST",
            BASE,
            {
                **self.authority(),
                "object": _definition(mode="automatic-organization"),
            },
        )
        active = self.managed.active()
        stored = active.document["automationTaskDefinitions"][0]
        from mediaflow.domain.automation import AutomationTaskDefinition

        domain = AutomationTaskDefinition.from_document(stored)
        grant = UnattendedExecutionGrant(
            "grant-nightly",
            "nightly",
            domain.resource_library_id,
            domain.source_scope,
            domain.run_mode,
            domain.item_limit,
            UnattendedExecutionGrantStatus.ACTIVE,
            "admin",
            datetime.now(UTC),
            domain.definition_fingerprint,
            active.revision_id,
            active.digest,
            active.version,
        )
        self.runtime.create_unattended_execution_grant(
            grant,
            UnattendedExecutionGrantAudit(
                "grant-audit", grant.grant_id, "granted", datetime.now(UTC), "admin", {}
            ),
        )
        self.assertEqual(self.grants.get_for_definition("nightly").status.value, "active")
        status, _body = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)
        self.assertEqual(self.ids(), [])
        revoked = self.grants.get_for_definition("nightly")
        self.assertIsNotNone(revoked)
        self.assertEqual(revoked.status.value, "revoked")
        # The audit survives: removal is not history deletion.
        self.assertTrue(
            any(
                item.action == "revoked"
                for item in self.grants.list_audit("grant-nightly", limit=10)
            )
        )

    def test_retained_history_is_readable_after_removal(self) -> None:
        """P1-3 regression: removed-definition history stays readable through
        the operator detail and occurrence routes after removal."""

        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        # The definition must first be published, then removed.
        status, removed = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)
        self.assertEqual(self.ids(), [])

        status, detail = self.request(
            "GET", "/api/v1/operations/automation/task-definitions/nightly"
        )
        self.assertEqual(status, 200)
        self.assertEqual(detail["definition"]["definitionState"], "historical")
        self.assertEqual(detail["definition"]["historicalState"], "removed")
        self.assertEqual(detail["definition"]["name"], "Automation nightly")

        status, occurrences = self.request(
            "GET", "/api/v1/operations/automation/task-definitions/nightly/occurrences"
        )
        self.assertEqual(status, 200)
        self.assertEqual(occurrences["definitionId"], "nightly")
        self.assertEqual(occurrences["historicalState"], "removed")

        # The V1 detail and grant surfaces also resolve the removed history.
        status, legacy = self.request("GET", "/api/v1/automation/task-definitions/nightly")
        self.assertEqual(status, 200)
        self.assertEqual(legacy["definition"]["definitionState"], "historical")

        status, grant_state = self.request(
            "GET", "/api/v1/automation/task-definitions/nightly/grant"
        )
        self.assertEqual(status, 200)
        self.assertEqual(grant_state["historicalState"], "removed")

    def test_retained_history_is_read_only(self) -> None:
        """A removed definition must not be grantable or previewable."""

        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        status, _removed = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)
        status, _body = self.request(
            "POST", "/api/v1/automation/task-definitions/nightly/grant", {}
        )
        self.assertEqual(status, 404)

    def test_fractional_interval_round_trips(self) -> None:
        """P1-4 regression: the backend supports fractional interval seconds;
        the API accepts and returns the exact value."""

        status, created = self.request(
            "POST",
            BASE,
            {**self.authority(), "object": _definition("sub-second", intervalSeconds=1.5)},
        )
        self.assertEqual(status, 200)
        self.assertEqual(created["definition"]["intervalSeconds"], 1.5)
        status, edited = self.request("GET", f"{BASE}/sub-second")
        self.assertEqual(status, 200)
        self.assertEqual(edited["definition"]["intervalSeconds"], 1.5)
        self.assertIsNone(edited["definition"].get("cron"))

    def test_clearing_scope_publishes_the_cleared_value(self) -> None:
        """P1-4 regression: an explicit scope clear publishes the cleared
        scope instead of silently keeping the previously stored value."""

        self.request(
            "POST",
            BASE,
            {**self.authority(), "object": _definition(sourceScope="incoming")},
        )
        status, edited = self.request(
            "PUT",
            f"{BASE}/nightly",
            {
                **self.authority(),
                "object": {
                    "id": "nightly",
                    "name": "Automation nightly",
                    "sourceScope": "",
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertIsNone(edited["definition"].get("sourceScope"))

    def test_copy_intent_reconciliation(self) -> None:
        """P1-5 regression: the copy-intent read resolves the committed copy
        identity from durable evidence, with zero side effects."""

        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        revisions_before = len(self.repository.list_revisions())
        status, copied = self.request("POST", f"{BASE}/nightly/copy", self.authority())
        self.assertEqual(status, 200)
        status, intent = self.request("GET", f"{BASE}/nightly/copy-intent")
        self.assertEqual(status, 200)
        self.assertTrue(intent["committed"])
        self.assertEqual(intent["committedDefinitionId"], copied["definition"]["id"])
        # The reconciliation read creates nothing.
        self.assertEqual(len(self.repository.list_revisions()), revisions_before + 1)
        # An unknown-submission outcome without publication evidence.
        status, empty_intent = self.request("GET", f"{BASE}/ghost/copy-intent")
        self.assertEqual(status, 200)
        self.assertFalse(empty_intent["committed"])

    def test_stale_authority_conflicts_without_publishing(self) -> None:
        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        stale = self.authority()
        self.request(
            "PUT",
            f"{BASE}/nightly",
            {**self.authority(), "object": {"id": "nightly", "name": "Second"}},
        )
        status, body = self.request(
            "PUT",
            f"{BASE}/nightly",
            {**stale, "object": {"id": "nightly", "name": "Stale"}},
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "configuration_version_conflict")
        self.assertEqual(
            self.managed.active().document["automationTaskDefinitions"][0]["name"], "Second"
        )

    def test_invalid_input_and_unknown_fields_fail_closed(self) -> None:
        for candidate, expected in (
            ({**_definition("a"), "sourceScope": "../escape"}, 400),
            ({**_definition("b"), "itemLimit": 10_001}, 400),
            ({**_definition("c"), "runMode": "scan-only"}, 400),
            ({**_definition("d", enabled=True)}, 409),
            ({**_definition("e"), "resourceLibraryId": "missing"}, 409),
        ):
            with self.subTest(id=candidate.get("id")):
                status, body = self.request("POST", BASE, {**self.authority(), "object": candidate})
                self.assertEqual(status, expected)
                self.assertIn("error", body)
        self.assertEqual(self.ids(), [])

    def test_missing_definition_reads_and_commands_report_not_found(self) -> None:
        for method, path, body in (
            ("GET", f"{BASE}/ghost", None),
            ("GET", f"{BASE}/ghost/removal-impact", None),
            ("POST", f"{BASE}/ghost/enable", self.authority()),
            ("DELETE", f"{BASE}/ghost", self.authority()),
        ):
            with self.subTest(path=path, method=method):
                status, body = self.request(method, path, body)
                self.assertEqual(status, 404)
                self.assertEqual(body["error"]["code"], "automation_definition_not_found")

    def test_unknown_route_is_not_found(self) -> None:
        status, _body = self.request("GET", f"{BASE}/nightly/unknown")
        self.assertEqual(status, 404)

    # -- permissions and compatibility ------------------------------------

    def test_permissions_are_enforced_per_command(self) -> None:
        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        status, _ = self.request("GET", BASE, token=VIEWER_TOKEN)
        self.assertEqual(status, 200)
        for method, path, body in (
            ("POST", BASE, {**self.authority(), "object": _definition("other")}),
            ("PUT", f"{BASE}/nightly", {**self.authority(), "object": {"id": "nightly"}}),
            ("POST", f"{BASE}/nightly/enable", self.authority()),
            ("DELETE", f"{BASE}/nightly", self.authority()),
        ):
            with self.subTest(path=path, method=method):
                status, body = self.request(method, path, body, token=VIEWER_TOKEN)
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "forbidden")
        # A principal with management but not activation permission cannot publish.
        status, body = self.request(
            "POST", BASE, {**self.authority(), "object": _definition("other")}, token=MANAGER_TOKEN
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.ids(), ["nightly"])

    def test_existing_v1_surfaces_remain_compatible(self) -> None:
        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        status, legacy = self.request("GET", "/api/v1/automation/task-definitions")
        self.assertEqual(status, 200)
        self.assertIn("configuration", legacy)
        self.assertEqual(legacy["items"][0]["id"], "nightly")
        status, operations = self.request("GET", "/api/v1/operations/automation/task-definitions")
        self.assertEqual(status, 200)
        self.assertEqual(operations["items"][0]["id"], "nightly")
        _assert_operator_document_clean(operations)

    def test_no_active_configuration_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            (root / "target").mkdir()
            repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
            self.addCleanup(repository.close)
            runtime = SQLiteTaskRepository(str(root / "runtime.sqlite3"))
            self.addCleanup(runtime.close)
            managed = ManagedConfigurationService(
                repository, bootstrap_database_path=str(root / "runtime.sqlite3")
            )
            api = MediaFlowApi(
                runtime,
                None,
                principals=(ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),),
                configuration_service=managed,
                bootstrap_document=_document(root),
            )
            statuses: list[str] = []
            environ = {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": BASE,
                "QUERY_STRING": "",
                "CONTENT_LENGTH": "0",
                "wsgi.input": io.BytesIO(b""),
                "REMOTE_ADDR": "127.0.0.1",
                "HTTP_AUTHORIZATION": f"Bearer {ADMIN_TOKEN}",
            }
            result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
            self.assertEqual(int(statuses[0].split()[0]), 503)
            body = json.loads(result)
            self.assertEqual(body["error"]["code"], "configuration_unavailable")
            self.assertEqual(body["error"]["details"]["reason"], "active_missing")


if __name__ == "__main__":
    unittest.main()
