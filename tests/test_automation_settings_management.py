"""Task 43.4 — focused Automation engine settings publication (S1–S3, S7).

Every case drives the real WSGI API over a real managed SQLite configuration
store: success, full invalid/boundary input, out-of-scope keys, unrelated-Draft
preservation, two independent writers, preparation failure and principal
isolation.  Assertions also prove the read/validation/save paths admit no work,
call no Provider and mutate no Storage.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.automation_settings import ENGINE_FIELD_PATHS
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ADMIN = ("admin", "admin-token")
WRITER = ("writer", "writer-token")
VIEWER = ("viewer", "viewer-token")
UNICODE_WRITER = ("运营-甲", "unicode-token")

SETTINGS = "/api/v1/operations/automation/settings"


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def request(api, path, *, method="GET", body=b"", token="admin-token", query=""):
    if "?" in path and not query:
        path, query = path.split("?", 1)
    statuses = []
    environment = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
    }
    payload = b"".join(api(environment, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


class SettingsFixture:
    """One isolated managed deployment with a real Active configuration."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.database = str(self.directory / "runtime.sqlite3")
        self.document = example_document()
        self.document["persistence"]["databasePath"] = self.database
        self.config_repository = SQLiteConfigurationRepository(
            self.directory / "configuration.sqlite3"
        )
        self.configuration = ManagedConfigurationService(
            self.config_repository,
            bootstrap_database_path=self.database,
        )
        draft = self.configuration.import_draft(self.document, actor="bootstrap")
        validated = self.configuration.validate(draft.revision_id, actor="bootstrap")
        self.active = self.configuration.activate(
            validated.revision_id, expected_version=validated.version, actor="bootstrap"
        )
        self.repository = SQLiteTaskRepository(self.database)
        self.api = self._api()

    def _api(self) -> MediaFlowApi:
        principals = (
            ResolvedApiPrincipal(*ADMIN, frozenset(ApiPermission)),
            ResolvedApiPrincipal(
                *WRITER, frozenset({ApiPermission.READ, ApiPermission.MANAGE_CONFIGURATION})
            ),
            ResolvedApiPrincipal(*VIEWER, frozenset({ApiPermission.READ})),
            ResolvedApiPrincipal(
                *UNICODE_WRITER,
                frozenset({ApiPermission.READ, ApiPermission.MANAGE_CONFIGURATION}),
            ),
        )
        return MediaFlowApi(
            self.repository,
            None,
            principals=principals,
            configuration_service=self.configuration,
            bootstrap_document=self.document,
        )

    def close(self) -> None:
        self.repository.close()
        self.config_repository.close()

    # -- helpers -------------------------------------------------------

    def values(self) -> dict:
        active = self.configuration.active()
        return dict(active.document["automation"])

    def submit(self, values: dict, *, token="admin-token", **extra):
        body = json.dumps({"settings": values, **extra}).encode("utf-8")
        return request(self.api, SETTINGS, method="PUT", body=body, token=token)

    def full(self, **overrides) -> dict:
        current = self.values()
        values = {
            "automation.maximumActiveJobs": current["maximumActiveJobs"],
            "automation.staleJobAgeSeconds": current["staleJobAgeSeconds"],
            "automation.workerPollSeconds": current["workerPollSeconds"],
            "automation.schedulerPollSeconds": current["schedulerPollSeconds"],
        }
        values.update(overrides)
        return values


class AutomationSettingsReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.fixture = SettingsFixture(self._temporary.name)
        self.addCleanup(self.fixture.close)

    def test_read_reports_the_published_target_and_the_four_fields(self) -> None:
        status, data = request(self.fixture.api, SETTINGS)
        self.assertEqual(status, 200)
        self.assertEqual(data["sideEffects"], "none")
        self.assertEqual(data["authority"], "MANAGED")
        self.assertTrue(data["canManage"])
        self.assertEqual([item["fieldPath"] for item in data["fields"]], list(ENGINE_FIELD_PATHS))
        target = data["target"]
        self.assertEqual(target["revisionId"], self.fixture.active.revision_id)
        self.assertEqual(target["digest"], self.fixture.active.digest)
        self.assertEqual(sorted(target["values"]), sorted(ENGINE_FIELD_PATHS))
        self.assertEqual(target["values"]["automation.maximumActiveJobs"], 100)

    def test_read_never_creates_a_draft_admits_work_or_mutates_storage(self) -> None:
        before_revisions = len(self.fixture.configuration.repository.list_revisions())
        before_jobs = self.fixture.repository.list_jobs()
        for _ in range(3):
            status, _data = request(self.fixture.api, SETTINGS)
            self.assertEqual(status, 200)
        self.assertEqual(
            len(self.fixture.configuration.repository.list_revisions()), before_revisions
        )
        self.assertEqual(self.fixture.repository.list_jobs(), before_jobs)

    def test_read_requires_read_permission(self) -> None:
        status, _data = request(self.fixture.api, SETTINGS, token=None)
        self.assertEqual(status, 401)

    def test_capacity_fields_are_api_local_and_never_gate_cadence_adoption(self) -> None:
        status, data = request(self.fixture.api, SETTINGS)
        self.assertEqual(status, 200)
        # The collective claim is about the two resident *cadence* consumers
        # only; the API-local capacity evidence has its own basis.
        self.assertFalse(data["adoption"]["allAdopted"])
        self.assertEqual(data["adoption"]["consumers"], 2)
        self.assertEqual(data["adoption"]["adoptedConsumers"], 0)
        worker = data["consumers"]["worker"]
        self.assertEqual(worker["instances"], [])
        self.assertFalse(worker["adopted"])
        # The two capacity fields are API-local evidence, never a claim that a
        # resident process consumed them.
        self.assertEqual(data["consumers"]["api"]["basis"], "api_local")
        self.assertFalse(data["consumers"]["api"]["adopted"])


class AutomationSettingsSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.fixture = SettingsFixture(self._temporary.name)
        self.addCleanup(self.fixture.close)

    def test_checked_save_publishes_only_the_four_fields(self) -> None:
        before = self.fixture.configuration.active()
        status, data = self.fixture.submit(
            self.fixture.full(
                **{
                    "automation.maximumActiveJobs": 42,
                    "automation.workerPollSeconds": 1.5,
                }
            )
        )
        self.assertEqual(status, 201, data)
        self.assertTrue(data["published"])
        after = self.fixture.configuration.active()
        self.assertNotEqual(after.revision_id, before.revision_id)
        self.assertEqual(after.document["automation"]["maximumActiveJobs"], 42)
        self.assertEqual(after.document["automation"]["workerPollSeconds"], 1.5)
        # Every other section and object is byte-identical.
        for key in set(before.document) | set(after.document):
            if key == "automation":
                continue
            self.assertEqual(before.document.get(key), after.document.get(key), key)
        self.assertEqual(
            before.document["automation"]["schedules"],
            after.document["automation"]["schedules"],
        )
        # The result exposes the published target and a fresh readback.
        self.assertEqual(data["publishedValues"]["automation.maximumActiveJobs"], 42)
        self.assertEqual(data["previousValues"]["automation.maximumActiveJobs"], 100)
        self.assertEqual(data["readback"]["target"]["revisionId"], after.revision_id)

    def test_noop_save_publishes_nothing_and_fabricates_no_adoption(self) -> None:
        before = self.fixture.configuration.active()
        status, data = self.fixture.submit(self.fixture.full())
        self.assertEqual(status, 200, data)
        self.assertFalse(data["published"])
        self.assertTrue(data["unchanged"])
        self.assertEqual(data["sideEffects"], "none")
        self.assertEqual(self.fixture.configuration.active().revision_id, before.revision_id)
        self.assertFalse(data["readback"]["adoption"]["allAdopted"])

    def test_unrelated_open_draft_is_preserved_and_not_activated(self) -> None:
        # An operator has an unrelated Settings Draft open with a pending edit.
        unrelated = self.fixture.configuration.create_successor_draft(actor="other")
        self.fixture.configuration.edit_draft(
            unrelated.revision_id,
            {**unrelated.document, "locale": "en-GB"},
            expected_version=unrelated.version,
            actor="other",
        )
        preserved = self.fixture.configuration.require(unrelated.revision_id)
        preserved_document = preserved.document
        status, data = self.fixture.submit(self.fixture.full(**{"automation.maximumActiveJobs": 7}))
        self.assertEqual(status, 201, data)
        reloaded = self.fixture.configuration.require(unrelated.revision_id)
        self.assertEqual(reloaded.document, preserved_document)
        self.assertEqual(reloaded.status.value, "draft")
        # The unrelated locale edit stayed in its own Draft and never reached
        # the Active this command published.
        self.assertEqual(reloaded.document["locale"], "en-GB")
        self.assertNotEqual(self.fixture.configuration.active().document.get("locale"), "en-GB")

    def test_out_of_scope_and_unknown_keys_are_rejected_before_publication(self) -> None:
        for extra in (
            {"locale": "en-GB"},
            {"operationalLogging.minimumLevel": "DEBUG"},
            {"automation.maximumActiveJobs.extra": 5},
        ):
            with self.subTest(extra=extra):
                before = self.fixture.configuration.active()
                status, data = self.fixture.submit({**self.fixture.full(), **extra})
                self.assertEqual(status, 422, data)
                self.assertEqual(data["error"]["code"], "settings_field_unsupported")
                self.assertEqual(data["error"]["details"]["sideEffects"], "none")
                self.assertEqual(
                    self.fixture.configuration.active().revision_id, before.revision_id
                )

    def test_missing_field_is_rejected(self) -> None:
        values = self.fixture.full()
        values.pop("automation.workerPollSeconds")
        before = self.fixture.configuration.active()
        status, data = self.fixture.submit(values)
        self.assertEqual(status, 422, data)
        self.assertEqual(data["error"]["code"], "settings_field_missing")
        self.assertEqual(self.fixture.configuration.active().revision_id, before.revision_id)

    def test_invalid_bounds_types_and_non_finite_values_are_rejected(self) -> None:
        cases = {
            "settings_out_of_range": [
                {"automation.maximumActiveJobs": 0},
                {"automation.maximumActiveJobs": 10_001},
                {"automation.staleJobAgeSeconds": 59},
                {"automation.staleJobAgeSeconds": 604_801},
                {"automation.workerPollSeconds": 0},
                {"automation.workerPollSeconds": -3},
                {"automation.schedulerPollSeconds": 0},
            ],
            "settings_fractional_integer": [
                {"automation.maximumActiveJobs": 3.5},
                {"automation.staleJobAgeSeconds": 90.25},
            ],
            "settings_boolean_not_number": [
                {"automation.maximumActiveJobs": True},
                {"automation.workerPollSeconds": False},
            ],
            "settings_invalid_type": [
                {"automation.workerPollSeconds": "2"},
                {"automation.schedulerPollSeconds": None},
            ],
            "settings_not_finite": [
                {"automation.workerPollSeconds": float("inf")},
                {"automation.schedulerPollSeconds": float("nan")},
            ],
        }
        for expected_code, overrides in cases.items():
            for override in overrides:
                for field, value in override.items():
                    with self.subTest(field=field, value=value):
                        before = self.fixture.configuration.active()
                        status, data = self.fixture.submit(self.fixture.full(**{field: value}))
                        self.assertEqual(status, 422, data)
                        self.assertEqual(data["error"]["code"], expected_code)
                        self.assertEqual(data["error"]["details"]["field"], field)
                        self.assertEqual(
                            self.fixture.configuration.active().revision_id,
                            before.revision_id,
                        )

    def test_two_independent_writers_do_not_partially_publish(self) -> None:
        before = self.fixture.configuration.active()
        status, first = self.fixture.submit(
            self.fixture.full(**{"automation.maximumActiveJobs": 11}),
            token="writer-token",
        )
        self.assertEqual(status, 201, first)
        winner = self.fixture.configuration.active()
        # The second writer still holds the stale Active identity it read.
        status, second = self.fixture.submit(
            self.fixture.full(**{"automation.maximumActiveJobs": 12}),
            token="unicode-token",
            expectedRevisionId=before.revision_id,
            expectedRevisionVersion=before.revision_sequence or before.version,
            expectedDigest=before.digest,
        )
        self.assertGreaterEqual(status, 400, second)
        self.assertEqual(self.fixture.configuration.active().revision_id, winner.revision_id)
        self.assertEqual(
            self.fixture.configuration.active().document["automation"]["maximumActiveJobs"], 11
        )

    def test_concurrent_second_save_without_expectation_still_serializes(self) -> None:
        status, first = self.fixture.submit(
            self.fixture.full(**{"automation.maximumActiveJobs": 21})
        )
        self.assertEqual(status, 201, first)
        # A second save re-reads the current Active, so it publishes a real
        # successor rather than silently reusing the first writer's revision.
        status, second = self.fixture.submit(
            self.fixture.full(**{"automation.maximumActiveJobs": 22})
        )
        self.assertEqual(status, 201, second)
        self.assertNotEqual(second["revisionId"], first["revisionId"])
        self.assertEqual(
            self.fixture.configuration.active().document["automation"]["maximumActiveJobs"], 22
        )

    def test_manage_permission_is_required_to_save(self) -> None:
        before = self.fixture.configuration.active()
        status, data = self.fixture.submit(
            self.fixture.full(**{"automation.maximumActiveJobs": 5}), token="viewer-token"
        )
        self.assertEqual(status, 403, data)
        self.assertEqual(self.fixture.configuration.active().revision_id, before.revision_id)

    def test_failed_preparation_preserves_the_previous_active(self) -> None:
        before = self.fixture.configuration.active()
        original_validate = self.fixture.configuration.validate

        def failing_validate(revision_id, *, actor):
            raise RuntimeError("validation store unavailable")

        self.fixture.configuration.validate = failing_validate
        try:
            status, data = self.fixture.submit(
                self.fixture.full(**{"automation.maximumActiveJobs": 31})
            )
        finally:
            self.fixture.configuration.validate = original_validate
        self.assertEqual(status, 503, data)
        self.assertEqual(data["error"]["details"]["durableState"], "active_preserved")
        self.assertEqual(data["error"]["details"]["stage"], "validate")
        active = self.fixture.configuration.active()
        self.assertEqual(active.revision_id, before.revision_id)
        self.assertEqual(active.document["automation"]["maximumActiveJobs"], 100)

    def test_save_has_no_job_task_or_storage_effect(self) -> None:
        before_jobs = self.fixture.repository.list_jobs()
        before_tasks = self.fixture.repository.list_tasks(limit=50)
        status, data = self.fixture.submit(
            self.fixture.full(**{"automation.maximumActiveJobs": 17})
        )
        self.assertEqual(status, 201, data)
        self.assertEqual(data["sideEffects"], "configuration_only")
        self.assertEqual(self.fixture.repository.list_jobs(), before_jobs)
        self.assertEqual(self.fixture.repository.list_tasks(limit=50), before_tasks)

    def test_audit_records_bounded_before_and_after_evidence(self) -> None:
        self.fixture.submit(self.fixture.full(**{"automation.maximumActiveJobs": 61}))
        audits = self.fixture.config_repository.list_recent_command_audits(
            ("draft_edit",), limit=50
        )
        focused = [
            item
            for item in audits
            if isinstance(item.after.get("objectChange"), dict)
            and item.after["objectChange"].get("objectId") == "automation_engine_settings"
        ]
        self.assertTrue(focused)
        change = focused[0].after["objectChange"]
        self.assertEqual(change["candidate"]["automation.maximumActiveJobs"], 61)
        self.assertEqual(change["before"]["automation.maximumActiveJobs"], 100)
        self.assertEqual(focused[0].actor, "admin")


class AutomationSettingsReconcileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.fixture = SettingsFixture(self._temporary.name)
        self.addCleanup(self.fixture.close)

    def test_unknown_submission_reconciles_from_durable_evidence(self) -> None:
        values = self.fixture.full(**{"automation.maximumActiveJobs": 51})
        status, data = self.fixture.submit(values)
        self.assertEqual(status, 201, data)
        # The browser lost the answer; it now reads durable state instead of
        # re-submitting the mutation.
        status, reconciled = request(
            self.fixture.api,
            SETTINGS,
            method="PUT",
            body=json.dumps({"reconcile": True, "settings": values}).encode("utf-8"),
        )
        self.assertEqual(status, 200, reconciled)
        self.assertTrue(reconciled["committed"])
        self.assertEqual(reconciled["sideEffects"], "none")
        self.assertEqual(reconciled["evidence"]["revisionId"], data["revisionId"])

    def test_reconcile_does_not_claim_commit_for_equal_values_without_evidence(self) -> None:
        # A principal that never submitted anything must not be credited with
        # the current Active merely because the values happen to match.
        status, reconciled = request(
            self.fixture.api,
            SETTINGS,
            method="PUT",
            body=json.dumps({"reconcile": True, "settings": self.fixture.full()}).encode("utf-8"),
            token="unicode-token",
        )
        self.assertEqual(status, 200, reconciled)
        self.assertFalse(reconciled["committed"])
        self.assertIn("publish deliberately again", reconciled["nextAction"])

    def test_reconcile_is_principal_scoped(self) -> None:
        values = self.fixture.full(**{"automation.maximumActiveJobs": 52})
        status, _data = self.fixture.submit(values, token="writer-token")
        self.assertEqual(status, 201)
        status, reconciled = request(
            self.fixture.api,
            SETTINGS,
            method="PUT",
            body=json.dumps({"reconcile": True, "settings": values}).encode("utf-8"),
            token="unicode-token",
        )
        self.assertEqual(status, 200, reconciled)
        self.assertFalse(reconciled["committed"])


if __name__ == "__main__":
    unittest.main()
