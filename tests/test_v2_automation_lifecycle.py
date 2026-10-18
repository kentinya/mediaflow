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

import copy
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
        "mode": "automatic-organization",
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
        # The only retained mode is advertised; removed modes are absent.
        self.assertEqual(body["enums"]["modes"], ["automatic-organization"])
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

    def test_retained_history_survives_publications_beyond_every_former_window(
        self,
    ) -> None:
        """P1 regression: retained history is not a bounded recent window.

        The exact production shape B reproduced: a published, enabled and
        emitted definition is removed; hundreds of ordinary authenticated
        focused publications of another definition then succeed; every
        retained-history route must still resolve the removed definition from
        its durable publication evidence with ``definitionState: historical``
        and ``historicalState: removed`` — never 404, never a substituted
        identity, and never an unpublished Draft candidate.

        The same assertion is then repeated after a runtime/API reopen, because
        the evidence is durable and must not depend on process state.
        """

        routes = (
            "/api/v1/operations/automation/task-definitions/nightly",
            "/api/v1/operations/automation/task-definitions/nightly/occurrences",
            "/api/v1/automation/task-definitions/nightly",
            "/api/v1/automation/task-definitions/nightly/grant",
        )

        def assert_historical() -> None:
            status, detail = self.request("GET", routes[0])
            self.assertEqual(status, 200, detail)
            self.assertEqual(detail["definition"]["definitionState"], "historical")
            self.assertEqual(detail["definition"]["historicalState"], "removed")
            self.assertEqual(detail["definition"]["name"], "Retained historical name")
            self.assertEqual(detail["definition"]["id"], "nightly")
            self.assertEqual(detail["definition"]["mode"], "automatic-organization")
            self.assertEqual(detail["definition"]["sourceScope"], "incoming/series")
            self.assertEqual(detail["definition"]["itemLimit"], 23)
            status, occurrences = self.request("GET", routes[1])
            self.assertEqual(status, 200, occurrences)
            self.assertEqual(occurrences["historicalState"], "removed")
            status, legacy = self.request("GET", routes[2])
            self.assertEqual(status, 200, legacy)
            self.assertEqual(legacy["definition"]["definitionState"], "historical")
            self.assertEqual(legacy["definition"]["historicalState"], "removed")
            status, grant_state = self.request("GET", routes[3])
            self.assertEqual(status, 200, grant_state)
            self.assertEqual(grant_state["historicalState"], "removed")

        status, _created = self.request(
            "POST",
            BASE,
            {
                **self.authority(),
                "object": _definition(
                    name="Retained historical name",
                    mode="automatic-organization",
                    sourceScope="incoming/series",
                    itemLimit=23,
                ),
            },
        )
        self.assertEqual(status, 200)
        status, _enabled = self.request("POST", f"{BASE}/nightly/enable", self.authority())
        self.assertEqual(status, 200)
        status, _other = self.request(
            "POST", BASE, {**self.authority(), "object": _definition("publisher")}
        )
        self.assertEqual(status, 200)
        status, _removed = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)
        assert_historical()

        # 505 ordinary authenticated focused publications, far beyond the
        # former 200-revision, 500-activation and 200-ever-published windows.
        for index in range(505):
            status, _body = self.request(
                "PUT",
                f"{BASE}/publisher",
                {
                    **self.authority(),
                    "object": {"id": "publisher", "name": f"Ordinary publication {index}"},
                },
            )
            self.assertEqual(status, 200)
        assert_historical()

        # A runtime/API reopen must not change the durable answer.
        reopened = MediaFlowApi(
            self.runtime,
            None,
            principals=(
                ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                ResolvedApiPrincipal("viewer", VIEWER_TOKEN, frozenset({ApiPermission.READ})),
            ),
            configuration_service=self.managed,
            bootstrap_document=self.document,
        )
        original = self.api
        self.api = reopened
        try:
            assert_historical()
        finally:
            self.api = original

    def test_retained_history_is_unavailable_not_absent_when_evidence_cannot_be_read(
        self,
    ) -> None:
        """P1 regression: an incomplete evidence read is 503, never a false 404.

        When the durable activation ledger cannot be walked and no occurrence
        pin exists, absence from the unreadable evidence must not be presented
        as "this definition has no history": the route reports the actionable
        configuration-unavailable state instead of a 404 that would let an
        unpublished Draft candidate be substituted.
        """

        self.request("POST", BASE, {**self.authority(), "object": _definition(name="Removed name")})
        status, _removed = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)

        repository = self.api._configuration_service.repository
        real_before = repository.list_command_audits_before
        real_latest = repository.latest_command_audit_sequence

        def failing_before(*args, **kwargs):
            raise RuntimeError("simulated truncating activation read failure")

        def failing_latest():
            raise RuntimeError("simulated truncating activation read failure")

        repository.list_command_audits_before = failing_before
        repository.latest_command_audit_sequence = failing_latest
        try:
            status, body = self.request(
                "GET", "/api/v1/operations/automation/task-definitions/nightly"
            )
            self.assertEqual(status, 503, body)
            self.assertNotIn("definition", body)
            status, _legacy = self.request("GET", "/api/v1/automation/task-definitions/nightly")
            self.assertEqual(status, 503)
            # The V1 grant surface must fail closed identically rather than
            # resolve a substituted identity from unreadable evidence.
            status, _grant = self.request(
                "GET", "/api/v1/automation/task-definitions/nightly/grant"
            )
            self.assertEqual(status, 503)
        finally:
            repository.list_command_audits_before = real_before
            repository.latest_command_audit_sequence = real_latest

        # The real readers resolve the same route truthfully.
        status, detail = self.request(
            "GET", "/api/v1/operations/automation/task-definitions/nightly"
        )
        self.assertEqual(status, 200)
        self.assertEqual(detail["definition"]["definitionState"], "historical")

    def test_open_draft_is_not_substituted_when_publication_evidence_is_unreadable(
        self,
    ) -> None:
        """P1 regression: an unreadable evidence read must not release the Draft.

        This is the dangerous shape: the definition is removed, a compatible
        open successor Draft still carries an unpublished candidate for the same
        ID, and the publication evidence cannot be read. Reporting "never
        published" would silently substitute the Draft candidate for the
        removed definition's real published history, so the route must instead
        report the actionable unavailable state.
        """

        self.request(
            "POST",
            BASE,
            {**self.authority(), "object": _definition(name="Published historical name")},
        )
        active = self.managed.active()
        assert active is not None
        draft = self.managed.create_successor_draft(
            actor="tester",
            expected_active_revision_id=active.revision_id,
            expected_active_version=active.revision_sequence or active.version,
            expected_active_digest=active.digest,
            verified_active=active,
        )
        document = copy.deepcopy(draft.document)
        document["automationTaskDefinitions"][0]["name"] = "NEVER PUBLISHED draft name"
        self.managed.edit_draft(
            draft.revision_id,
            document,
            expected_version=draft.version,
            actor="tester",
        )
        status, _removed = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)

        repository = self.api._configuration_service.repository
        real_before = repository.list_command_audits_before
        real_latest = repository.latest_command_audit_sequence

        def failing_before(*args, **kwargs):
            raise RuntimeError("simulated truncating activation read failure")

        def failing_latest():
            raise RuntimeError("simulated truncating activation read failure")

        repository.list_command_audits_before = failing_before
        repository.latest_command_audit_sequence = failing_latest
        try:
            status, body = self.request(
                "GET", "/api/v1/operations/automation/task-definitions/nightly"
            )
            self.assertEqual(status, 503, body)
            # The Draft candidate was never substituted for the real history.
            self.assertNotIn("NEVER PUBLISHED draft name", json.dumps(body))
        finally:
            repository.list_command_audits_before = real_before
            repository.latest_command_audit_sequence = real_latest

        # With the real readers the published history wins over the Draft.
        status, detail = self.request(
            "GET", "/api/v1/operations/automation/task-definitions/nightly"
        )
        self.assertEqual(status, 200)
        self.assertEqual(detail["definition"]["definitionState"], "historical")
        self.assertEqual(detail["definition"]["name"], "Published historical name")
        self.assertNotEqual(detail["definition"]["name"], "NEVER PUBLISHED draft name")

    def test_retained_history_never_substitutes_an_open_draft_beyond_the_window(
        self,
    ) -> None:
        """P1 regression: published history is never replaced by a Draft candidate.

        A removed definition with a compatible open successor Draft whose
        candidate carries a different name must keep resolving the *published*
        configuration its runs used — and must keep doing so after hundreds of
        ordinary publications push its evidence far outside every former
        window. Substituting the unpublished Draft candidate would present
        configuration that was never Active as the removed run's history.
        """

        self.request(
            "POST",
            BASE,
            {**self.authority(), "object": _definition(name="Published historical name")},
        )
        # An open successor Draft with an unpublished name for the same ID.
        active = self.managed.active()
        assert active is not None
        draft = self.managed.create_successor_draft(
            actor="tester",
            expected_active_revision_id=active.revision_id,
            expected_active_version=active.revision_sequence or active.version,
            expected_active_digest=active.digest,
            verified_active=active,
        )
        document = copy.deepcopy(draft.document)
        definitions = document["automationTaskDefinitions"]
        definitions[0]["name"] = "NEVER PUBLISHED draft name"
        self.managed.edit_draft(
            draft.revision_id,
            document,
            expected_version=draft.version,
            actor="tester",
        )
        status, _removed = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)
        self.request("POST", BASE, {**self.authority(), "object": _definition("publisher")})
        for index in range(300):
            status, _body = self.request(
                "PUT",
                f"{BASE}/publisher",
                {
                    **self.authority(),
                    "object": {"id": "publisher", "name": f"Ordinary publication {index}"},
                },
            )
            self.assertEqual(status, 200)

        status, detail = self.request(
            "GET", "/api/v1/operations/automation/task-definitions/nightly"
        )
        self.assertEqual(status, 200, detail)
        self.assertEqual(detail["definition"]["definitionState"], "historical")
        self.assertEqual(detail["definition"]["historicalState"], "removed")
        self.assertEqual(detail["definition"]["name"], "Published historical name")
        self.assertNotEqual(detail["definition"]["name"], "NEVER PUBLISHED draft name")

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

    def test_retained_history_ignores_an_unpublished_draft(self) -> None:
        """P1 regression: a compatible open successor Draft is never
        substituted for the removed definition's published history. The
        published name/scope/mode the run used is what the retained-history
        read returns, and the Draft stays available for explicit correction
        through its own route."""

        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        active = self.managed.active()
        # A real open successor Draft with an unpublished name.
        draft = self.managed.create_successor_draft(
            actor="tester",
            expected_active_revision_id=active.revision_id,
            expected_active_version=active.revision_sequence or active.version,
            expected_active_digest=active.digest,
            verified_active=active,
        )
        document = json.loads(json.dumps(draft.document))
        document["automationTaskDefinitions"][0]["name"] = "NEVER PUBLISHED draft name"
        self.managed.edit_draft(
            draft.revision_id,
            document,
            expected_version=draft.version,
            actor="tester",
        )
        status, _removed = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)

        status, detail = self.request(
            "GET", "/api/v1/operations/automation/task-definitions/nightly"
        )
        self.assertEqual(status, 200)
        self.assertEqual(detail["definition"]["definitionState"], "historical")
        self.assertEqual(detail["definition"]["historicalState"], "removed")
        # The published configuration — never the Draft candidate.
        self.assertEqual(detail["definition"]["name"], "Automation nightly")
        self.assertNotEqual(detail["definition"]["name"], "NEVER PUBLISHED draft name")

        # The V2 typed edit projection also resolves the published history.
        status, projection = self.request("GET", f"{BASE}/nightly")
        self.assertEqual(status, 200)
        self.assertEqual(projection["definitionState"], "historical")
        self.assertEqual(projection["definition"]["name"], "Automation nightly")

        # The V1 detail surface agrees.
        status, legacy = self.request("GET", "/api/v1/automation/task-definitions/nightly")
        self.assertEqual(status, 200)
        self.assertEqual(legacy["definition"]["name"], "Automation nightly")

    def _publish_remove_and_retain_draft(self, draft_name: str) -> str:
        """Publish, remove, and retain a same-ID unpublished Draft candidate.

        Returns the exact published revision ID that the caller may corrupt.
        """

        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        active = self.managed.active()
        assert active is not None
        published_revision_id = active.revision_id
        draft = self.managed.create_successor_draft(
            actor="tester",
            expected_active_revision_id=active.revision_id,
            expected_active_version=active.revision_sequence or active.version,
            expected_active_digest=active.digest,
            verified_active=active,
        )
        document = json.loads(json.dumps(draft.document))
        document["automationTaskDefinitions"][0]["name"] = draft_name
        self.managed.edit_draft(
            draft.revision_id,
            document,
            expected_version=draft.version,
            actor="tester",
        )
        status, _removed = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)
        return published_revision_id

    def _corrupt_published_section(self, revision_id: str, section: object) -> None:
        """Corrupt one published revision's section, keeping ID/digest/audit."""

        import sqlite3

        revision = self.repository.get_revision(revision_id)
        assert revision is not None
        payload = copy.deepcopy(revision.document)
        payload["automationTaskDefinitions"] = section
        connection = sqlite3.connect(str(self.root / "configuration.sqlite3"))
        try:
            connection.execute(
                "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                (json.dumps(payload), revision_id),
            )
            connection.commit()
        finally:
            connection.close()

    def test_corrupt_published_history_is_unavailable_on_every_route(self) -> None:
        """P1 regression: a corrupt published revision is never false absence.

        B reproduced this against the real API: remove a definition, retain a
        same-ID unpublished Draft, then corrupt only the superseded published
        revision's definition section while keeping its revision ID, stored
        digest and positive activation audit. Every affected route must answer
        the actionable unavailable state — never the Draft name, a false 404 or
        older-context substitution — and must keep doing so after a runtime/API
        reopen.
        """

        revision_id = self._publish_remove_and_retain_draft("NEVER PUBLISHED B draft")
        routes = (
            "/api/v1/operations/automation/task-definitions/nightly",
            "/api/v1/automation/task-definitions/nightly",
            "/api/v1/automation/task-definitions/nightly/grant",
            "/api/v1/operations/automation/task-definitions/nightly/occurrences",
            f"{BASE}/nightly",
            f"{BASE}/nightly/copy-candidate",
            f"{BASE}/nightly/removal-impact",
        )

        # Before corruption the affected routes resolve the real history.
        status, detail = self.request("GET", routes[0])
        self.assertEqual(status, 200)
        self.assertEqual(detail["definition"]["definitionState"], "historical")
        self.assertEqual(detail["definition"]["name"], "Automation nightly")

        self._corrupt_published_section(revision_id, "corrupt section")

        def assert_unavailable() -> None:
            for route in routes:
                with self.subTest(route=route):
                    status, body = self.request("GET", route)
                    self.assertEqual(status, 503, body)
                    self.assertEqual(body["error"]["code"], "configuration_unavailable")
                    self.assertEqual(
                        body["error"]["details"]["reason"], "historical_evidence_unavailable"
                    )
                    # The unpublished Draft candidate was never substituted,
                    # and no route claims a false absence.
                    self.assertNotIn("NEVER PUBLISHED B draft", json.dumps(body))
                    self.assertNotIn("not_found", json.dumps(body))

        assert_unavailable()

        # A runtime/API reopen must not change the durable answer.
        reopened = MediaFlowApi(
            self.runtime,
            None,
            principals=(
                ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                ResolvedApiPrincipal("viewer", VIEWER_TOKEN, frozenset({ApiPermission.READ})),
            ),
            configuration_service=self.managed,
            bootstrap_document=self.document,
        )
        original = self.api
        self.api = reopened
        try:
            assert_unavailable()
        finally:
            self.api = original

        # A definition with genuinely no published evidence is still a real
        # 404, and the Draft itself stays inspectable through its own route.
        status, _absent = self.request(
            "GET", "/api/v1/operations/automation/task-definitions/ghost"
        )
        self.assertEqual(status, 404)

    def test_corrupt_published_history_does_not_release_the_draft_via_api(self) -> None:
        """P1 regression: the corrupt read must not label the Draft draft-only.

        This is the exact B reproducer shape: the V2 detail/lifecycle routes
        returned 200 with the never-published Draft name and ``draft-only``.
        They must instead report unavailable evidence for the same-ID Draft.
        """

        revision_id = self._publish_remove_and_retain_draft("NEVER PUBLISHED B draft")
        self._corrupt_published_section(revision_id, "corrupt section")

        for route in (
            "/api/v1/operations/automation/task-definitions/nightly",
            f"{BASE}/nightly",
        ):
            with self.subTest(route=route):
                status, body = self.request("GET", route)
                self.assertEqual(status, 503, body)
                self.assertNotIn("draft-only", json.dumps(body))
                self.assertNotIn("NEVER PUBLISHED B draft", json.dumps(body))

        # The Draft is still stored for explicit correction; it was simply
        # never presented as the removed definition's published history.
        draft = self.managed.latest_open_draft_containing("automationTaskDefinitions", "nightly")
        self.assertIsNotNone(draft)

    def test_corrupt_published_history_without_a_draft_is_still_unavailable(self) -> None:
        """P1 regression: corrupt evidence is unavailable, never a false 404.

        Without any same-ID Draft candidate the corrupt published revision used
        to exhaust the ledger and report the definition as absent, which the V1
        detail and grant routes turned into a 404. Corrupt published evidence is
        unavailability, so those routes must answer 503 with the actionable
        reason rather than claiming the removed definition never existed.
        """

        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        active = self.managed.active()
        assert active is not None
        revision_id = active.revision_id
        status, _removed = self.request("DELETE", f"{BASE}/nightly", self.authority())
        self.assertEqual(status, 200)
        self._corrupt_published_section(revision_id, "corrupt section")

        for route in (
            "/api/v1/automation/task-definitions/nightly",
            "/api/v1/automation/task-definitions/nightly/grant",
            "/api/v1/automation/task-definitions/nightly/occurrences",
            "/api/v1/operations/automation/task-definitions/nightly",
            f"{BASE}/nightly",
        ):
            with self.subTest(route=route):
                status, body = self.request("GET", route)
                self.assertEqual(status, 503, body)
                self.assertEqual(body["error"]["code"], "configuration_unavailable")
                self.assertEqual(
                    body["error"]["details"]["reason"], "historical_evidence_unavailable"
                )
                # A false absence is explicitly not claimed.
                self.assertNotEqual(body["error"]["code"], "not_found")

        # A definition that genuinely never existed is still a real 404.
        status, _absent = self.request("GET", "/api/v1/automation/task-definitions/never-published")
        self.assertEqual(status, 404)

    def test_copy_intent_binds_to_the_submitted_intent(self) -> None:
        """P1 regression: copy-intent reconciliation is bound to the exact
        submitted intent. A later submission's committed copy is never named
        as an earlier intent's result, and a fence no observed command was
        submitted against resolves no committed outcome."""

        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        first_fence = self.authority()
        status, first = self.request("POST", f"{BASE}/nightly/copy", self.authority())
        self.assertEqual(status, 200)
        first_copy_id = first["definition"]["id"]
        status, second = self.request("POST", f"{BASE}/nightly/copy", self.authority())
        self.assertEqual(status, 200)
        second_copy_id = second["definition"]["id"]
        self.assertNotEqual(first_copy_id, second_copy_id)

        # The unfenced read resolves the newest source-matching command.
        status, unfenced = self.request("GET", f"{BASE}/nightly/copy-intent")
        self.assertEqual(status, 200)
        self.assertTrue(unfenced["committed"])
        self.assertEqual(unfenced["committedDefinitionId"], second_copy_id)

        # The read bound to the FIRST intent's fence resolves that submission.
        status, fenced = self.request(
            "GET",
            f"{BASE}/nightly/copy-intent",
            query=(
                f"expectedRevisionId={first_fence['expectedRevisionId']}"
                f"&expectedVersion={first_fence['expectedVersion']}"
                f"&expectedDigest={first_fence['expectedDigest']}"
            ),
        )
        self.assertEqual(status, 200)
        self.assertTrue(fenced["committed"])
        self.assertEqual(fenced["committedDefinitionId"], first_copy_id)

        # A fence no observed command was submitted against resolves nothing.
        status, empty = self.request(
            "GET",
            f"{BASE}/nightly/copy-intent",
            query=(
                "expectedRevisionId=no-such-revision&expectedVersion=1&expectedDigest=" + "f" * 64
            ),
        )
        self.assertEqual(status, 200)
        self.assertFalse(empty["committed"])

    def test_copy_intent_resolves_a_committed_copy_beyond_the_recent_audit_window(
        self,
    ) -> None:
        """P1 regression (fix loop 4): a real cursor, not a bigger window.

        A Copy commits durably through the real API. Another definition then
        receives enough ordinary authenticated focused edits to push the
        original command past a full scan page, so a reader that stopped at its
        first page — or that re-anchored on a cursor the domain object never
        carried — would report `committed: false`/`observedCommands: 0` and
        release a duplicate Copy, exactly as B reproduced. The submitted fence
        must still resolve the original committed identity, the publication
        proof must come from that command revision's own activation authority,
        and the read must report its evidence as complete.
        """

        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        # The intent's fence is the authority the Copy is submitted against,
        # captured before the command advances the Active revision.
        fence = self.authority()
        status, published = self.request("POST", f"{BASE}/nightly/copy", self.authority())
        self.assertEqual(status, 200)
        copy_id = published["definition"]["id"]
        # An unrelated definition then receives more focused edits than one
        # full scan page, so the copy's command row is only reachable by
        # paging with a real durable cursor.
        self.request("POST", BASE, {**self.authority(), "object": _definition("other")})
        for index in range(210):
            status, _body = self.request(
                "PUT",
                f"{BASE}/other",
                {**self.authority(), "object": {"id": "other", "name": f"Edit {index}"}},
            )
            self.assertEqual(status, 200)
        status, intent = self.request(
            "GET",
            f"{BASE}/nightly/copy-intent",
            query=(
                f"expectedRevisionId={fence['expectedRevisionId']}"
                f"&expectedVersion={fence['expectedVersion']}"
                f"&expectedDigest={fence['expectedDigest']}"
            ),
        )
        self.assertEqual(status, 200)
        self.assertTrue(intent["evidenceComplete"])
        self.assertTrue(intent["committed"])
        self.assertEqual(intent["committedDefinitionId"], copy_id)
        self.assertIsNotNone(intent["lastObserved"])
        self.assertTrue(intent["lastObserved"]["published"])
        self.assertEqual(intent["lastObserved"]["candidateId"], copy_id)
        self.assertTrue(intent["sourcePresent"])
        # The published copy is still readable, so no second copy was needed.
        status, detail = self.request("GET", f"{BASE}/{copy_id}")
        self.assertEqual(status, 200)

    def test_copy_intent_never_releases_a_duplicate_when_evidence_is_incomplete(self) -> None:
        """P1 regression (fix loop 4): an incomplete read is unknown, not unpublished.

        When the durable audit readers cannot complete, the read observes zero
        commands. That absence must never be presented as a proven
        non-publication that releases a second Copy; the response must mark the
        evidence incomplete and keep the operator on the reconciliation path.
        """

        self.request("POST", BASE, {**self.authority(), "object": _definition()})
        repository = self.api._configuration_service.repository
        real_before = repository.list_command_audits_before
        real_latest = repository.latest_command_audit_sequence

        def failing_before(*args, **kwargs):
            raise RuntimeError("simulated truncating audit read failure")

        def failing_latest():
            raise RuntimeError("simulated truncating audit read failure")

        repository.list_command_audits_before = failing_before
        repository.latest_command_audit_sequence = failing_latest
        try:
            status, intent = self.request("GET", f"{BASE}/nightly/copy-intent")
        finally:
            repository.list_command_audits_before = real_before
            repository.latest_command_audit_sequence = real_latest
        self.assertEqual(status, 200)
        self.assertFalse(intent["committed"])
        self.assertIsNone(intent["committedDefinitionId"])
        self.assertEqual(intent["observedCommands"], 0)
        self.assertFalse(intent["evidenceComplete"])
        self.assertIn("unknown", intent["nextAction"].lower())
        # With the real readers the same read is complete and honest.
        status, healthy = self.request("GET", f"{BASE}/nightly/copy-intent")
        self.assertEqual(status, 200)
        self.assertTrue(healthy["evidenceComplete"])

    def test_removal_persistence_failure_reports_preserved_authority(self) -> None:
        """P1 regression: a known failed removal inside the real publication
        boundary preserves the live grant and reports the durable truth.

        A second real SQLite writer holds ``BEGIN IMMEDIATE`` between the
        runtime preparation and the activation — ordinary production write
        contention — so the removal's activation fails with a database lock.
        The removal must not leave the definition Active with its grant
        revoked: the prior live authority is durably restored and reported."""

        from datetime import UTC, datetime

        from mediaflow.domain.automation import AutomationTaskDefinition
        from mediaflow.domain.unattended_execution import (
            UnattendedExecutionGrant,
            UnattendedExecutionGrantAudit,
            UnattendedExecutionGrantStatus,
        )

        self.request(
            "POST",
            BASE,
            {**self.authority(), "object": _definition(mode="automatic-organization")},
        )
        active = self.managed.active()
        stored = active.document["automationTaskDefinitions"][0]
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
        # One ordinary production writer holds the configuration write lock
        # between runtime preparation and activation.
        holder: list = []

        def contention(_successor):
            import sqlite3
            import time

            time.sleep(0.05)
            connection = sqlite3.connect(str(self.root / "configuration.sqlite3"), timeout=0.05)
            connection.execute("BEGIN IMMEDIATE")
            holder.append(connection)

        import mediaflow.application.automation_workspace_commands as workspace_module

        original_remove = workspace_module.AutomationWorkspaceCommandService.remove_object

        def remove_with_contention(self_service, definition_id, **kwargs):
            kwargs["before_publish"] = contention
            return original_remove(self_service, definition_id, **kwargs)

        try:
            with patch.object(
                workspace_module.AutomationWorkspaceCommandService,
                "remove_object",
                remove_with_contention,
            ):
                status, body = self.request("DELETE", f"{BASE}/nightly", self.authority())
        finally:
            for connection in holder:
                try:
                    connection.rollback()
                    connection.close()
                except Exception:
                    pass
        self.assertEqual(status, 503)
        error = body["error"]
        self.assertEqual(error["code"], "automation_definition_removal_not_published")
        self.assertIn(
            error["details"]["durableState"],
            {"active_preserved", "commit_state_unknown"},
        )
        # The definition is still published and its authority is live: the
        # failed removal did not break the admitted work.
        self.assertEqual(self.ids(), ["nightly"])
        self.assertEqual(self.grants.get_for_definition("nightly").status.value, "active")

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
            # The legacy ``runMode`` alias is not a typed-form field.
            ({**_definition("c"), "runMode": "unsupported-mode"}, 400),
            # Each removed mode spelling is refused as a submitted value.
            ({**_definition("c1"), "mode": "unsupported-mode"}, 400),
            ({**_definition("c2"), "mode": "unsupported-mode"}, 400),
            ({**_definition("c3"), "mode": "scan"}, 400),
            ({**_definition("c4"), "mode": "preview"}, 400),
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


class SameFileRemovalAuthorityTests(unittest.TestCase):
    """The production database arrangement: one shared SQLite file.

    Configuration and runtime/grant state live in the same database file in
    production, so any foreign writer holding that file's write lock blocks
    every write — including a compensating grant write. These tests drive the
    real API and the real Worker assembly on that exact arrangement.
    """

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

        self.database = self.root / "mediaflow.sqlite3"
        self.repository = SQLiteConfigurationRepository(self.database)
        self.addCleanup(self.repository.close)
        self.runtime = SQLiteTaskRepository(str(self.database))
        self.addCleanup(self.runtime.close)
        self.document = _document(self.root)
        # The exact production arrangement: one database file for the managed
        # configuration authority AND the runtime/grant state, so the bootstrap
        # locator must resolve to the same file the repositories open.
        self.document["persistence"]["databasePath"] = str(self.database)
        self.managed = ManagedConfigurationService(
            self.repository,
            bootstrap_database_path=str(self.database),
        )
        self.objects = ConfigurationObjectService(
            self.managed,
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
            principals=(ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),),
            configuration_service=self.managed,
            bootstrap_document=self.document,
        )

    def request(self, method: str, path: str, body: object | None = None):
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(payload)),
            "wsgi.input": io.BytesIO(payload),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": f"Bearer {ADMIN_TOKEN}",
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

    def _seed_active_grant(self, definition_id: str) -> None:
        from datetime import UTC, datetime

        from mediaflow.domain.automation import AutomationTaskDefinition
        from mediaflow.domain.unattended_execution import (
            UnattendedExecutionGrant,
            UnattendedExecutionGrantAudit,
            UnattendedExecutionGrantStatus,
        )

        active = self.managed.active()
        stored = active.document["automationTaskDefinitions"][0]
        domain = AutomationTaskDefinition.from_document(stored)
        grant = UnattendedExecutionGrant(
            f"grant-{definition_id}",
            definition_id,
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
                f"grant-{definition_id}-audit",
                grant.grant_id,
                "granted",
                datetime.now(UTC),
                "admin",
                {},
            ),
        )

    def test_known_failed_removal_preserves_the_live_grant_on_the_shared_file(self) -> None:
        """P1 regression: a foreign writer's write lock on the SAME SQLite file
        that holds both configuration and grants cannot revoke the live
        authority of a known failed removal.

        The review reproduced this with the production arrangement: real exact
        Preview, confirmed grant, real Scheduler admission, then a second
        SQLite writer holding ``BEGIN IMMEDIATE`` between runtime preparation
        and activation. The prior compensation design wrote its restore into
        the same locked database and the admitted Job failed in the real
        Worker with ``unattended_execution_grant_revoked``. The corrected
        removal revokes only AFTER a proven publication, so a failed
        activation never touches authority at all: the definition stays
        published, the grant stays active, and the admitted Job's authority
        still authorizes.
        """

        from mediaflow.domain.automation import AutomationTaskRunMode

        status, _created = self.request(
            "POST",
            BASE,
            {
                **self.authority(),
                "object": _definition(mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION.value),
            },
        )
        self.assertEqual(status, 200)
        status, _enabled = self.request("POST", f"{BASE}/nightly/enable", self.authority())
        self.assertEqual(status, 200)
        self._seed_active_grant("nightly")

        # One ordinary production writer holds the ONE production database's
        # write lock — the same file holds configuration, grants and Jobs —
        # between runtime preparation and the activation transaction.
        holder: list = []

        def contention(_successor):
            import sqlite3
            import time

            time.sleep(0.05)
            connection = sqlite3.connect(str(self.database), timeout=0.05)
            connection.execute("BEGIN IMMEDIATE")
            holder.append(connection)

        import mediaflow.interfaces.service_api as service_api_module

        original_remove = service_api_module.AutomationWorkspaceCommandService.remove_object

        def remove_with_contention(workspace, definition_id, **kwargs):
            kwargs["before_publish"] = contention
            return original_remove(workspace, definition_id, **kwargs)

        try:
            with patch.object(
                service_api_module.AutomationWorkspaceCommandService,
                "remove_object",
                remove_with_contention,
            ):
                status, body = self.request("DELETE", f"{BASE}/nightly", self.authority())
        finally:
            for connection in holder:
                try:
                    connection.rollback()
                    connection.close()
                except Exception:
                    pass
        self.assertEqual(status, 503)
        error = body["error"]
        self.assertEqual(error["code"], "automation_definition_removal_not_published")
        self.assertIn(
            error["details"]["durableState"],
            {"active_preserved", "commit_state_unknown"},
        )
        # The definition is still published...
        self.assertEqual(self.ids(), ["nightly"])
        # ...and its live authority survived the failed removal untouched.
        self.assertEqual(self.grants.get_for_definition("nightly").status.value, "active")
        # The admitted Job's authority still authorizes against the live grant
        # through the grant service's own match/snapshot boundary.
        from types import SimpleNamespace

        from mediaflow.domain.automation import AutomationTaskDefinition

        active_now = self.managed.active()
        assert active_now is not None
        stored = active_now.document["automationTaskDefinitions"][0]
        job = SimpleNamespace(
            definition_id=stored["id"],
            resource_library_id=stored["resourceLibraryId"],
            source_scope=stored.get("sourceScope"),
            run_mode=stored["mode"],
            limit=stored["itemLimit"],
            configuration_snapshot_id=active_now.revision_id,
            configuration_snapshot_digest=active_now.digest,
            configuration_snapshot_version=active_now.version,
        )
        grant = self.grants._get_active("nightly")
        self.assertIsNotNone(grant)
        self.assertEqual(grant.status.value, "active")
        self.grants._assert_match(grant, job, AutomationTaskDefinition.from_document(stored))


if __name__ == "__main__":
    unittest.main()
