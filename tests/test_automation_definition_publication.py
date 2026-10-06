"""Task 43.1 — focused Automation Task Definition publication.

These tests prove the vertical the native V2 Automation workspace depends on:

* one checked Save or lifecycle command publishes exactly one intended Active
  successor through the shared managed normalization, whole-document validation
  and checked atomic activation boundaries;
* the successor changes only the selected definition, so sibling definitions and
  unrelated configuration never ride along;
* a new/copied definition starts disabled with no unattended authority, enabling
  starts no work and disabling neither cancels admitted work nor revokes a grant;
* removal revokes applicable future unattended authority before publishing and
  retains grants, audits and occurrence history;
* reads and schedule calculation create no Draft, call no Provider, start no work
  and mutate no Storage.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.automation_workspace_commands import (
    AUTOMATION_DEFINITION_SECTION,
    AutomationWorkspaceCommandService,
)
from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.unattended_execution import UnattendedExecutionGrantService
from mediaflow.domain.configuration_management import (
    AutomationDefinitionSaveError,
    ConfigurationVersionConflict,
)
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

ADMIN = "operator"


class RecordingStorage:
    """Provider-neutral fake that fails loudly on any mutation."""

    def __init__(self, storage_id: str) -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = False
        self.mutations: list[str] = []
        self.reads: list[str] = []

    def stat(self, path: str):
        self.reads.append(f"stat:{path}")
        raise AssertionError("Automation definition commands must not read Storage")

    def list(self, path: str):
        self.reads.append(f"list:{path}")
        raise AssertionError("Automation definition commands must not list Storage")

    def _refuse(self, operation: str):
        self.mutations.append(operation)
        raise AssertionError(f"Automation definition commands must not {operation} Storage")

    def write(self, *args, **kwargs):
        self._refuse("write")

    def create_directory(self, *args, **kwargs):
        self._refuse("create_directory")

    def move(self, *args, **kwargs):
        self._refuse("move")

    def copy(self, *args, **kwargs):
        self._refuse("copy")

    def delete(self, *args, **kwargs):
        self._refuse("delete")

    def hard_link(self, *args, **kwargs):
        self._refuse("hard_link")

    def soft_link(self, *args, **kwargs):
        self._refuse("soft_link")


class MutationAuditRepository(SQLiteConfigurationRepository):
    """Counts activation writes so a test can prove nothing published."""

    def __init__(self, path) -> None:
        super().__init__(path)
        self.activations = 0

    def activate_revision(self, revision_id, expected_version, audit):
        self.activations += 1
        return super().activate_revision(revision_id, expected_version, audit)


def example_document(root: Path) -> dict:
    value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    value["storages"][0]["rootPath"] = str(root / "source")
    value["storages"][1]["rootPath"] = str(root / "target")
    return value


def definition(definition_id: str, **overrides) -> dict:
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


class AutomationPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "source").mkdir(parents=True)
        (self.root / "target").mkdir(parents=True)
        self.environment = patch.dict(
            os.environ,
            {"TMDB_ACCESS_TOKEN": "sentinel-tmdb-value", "OPENLIST_TOKEN": "sentinel-openlist"},
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

        self.repository = MutationAuditRepository(self.root / "configuration.sqlite3")
        self.addCleanup(self.repository.close)
        self.runtime = SQLiteTaskRepository(str(self.root / "runtime.sqlite3"))
        self.addCleanup(self.runtime.close)
        self.managed = ManagedConfigurationService(
            self.repository,
            bootstrap_database_path=str(self.root / "runtime.sqlite3"),
        )
        self.provider_calls: list[str] = []
        self.objects = ConfigurationObjectService(
            self.managed,
            metadata_provider_registry_factory=self._forbidden_provider_factory,
            storage_browser_cursor_secret="automation-publication-test-secret",
        )
        self.adapters = {
            "source-storage": RecordingStorage("source-storage"),
            "media-target": RecordingStorage("media-target"),
        }
        self.objects._storage_adapters.update(self.adapters)
        self.grants = UnattendedExecutionGrantService(
            self.runtime,
            permission_authority=None,
        )
        self.commands = AutomationWorkspaceCommandService(
            self.objects, unattended_grants=self.grants
        )

        document = example_document(self.root)
        draft = self.managed.import_draft(document, actor="bootstrap")
        validated = self.managed.validate(draft.revision_id, actor="bootstrap")
        # The focused publication path composes the successor from the exact
        # Active and relies on the confinement proof instead of re-running the
        # page-local Storage evidence gates, so the baseline publishes through
        # the same plain atomic activation boundary.
        self.managed.activate(
            validated.revision_id, expected_version=validated.version, actor="bootstrap"
        )
        self.activations_at_baseline = self.repository.activations

    def _forbidden_provider_factory(self, provider_ids):
        self.provider_calls.extend(provider_ids)
        raise AssertionError("Automation definition commands must not construct a Provider")

    def authority(self) -> dict[str, object]:
        active = self.managed.active()
        assert active is not None
        return {
            "expected_revision_id": active.revision_id,
            "expected_version": active.revision_sequence or active.version,
            "expected_digest": active.digest,
        }

    def definitions(self) -> list[dict]:
        active = self.managed.active()
        assert active is not None
        return copy.deepcopy(active.document.get(AUTOMATION_DEFINITION_SECTION, []))

    def ids(self) -> list[str]:
        return [item["id"] for item in self.definitions()]

    def assert_active_unchanged(self, before) -> None:
        after = self.managed.active()
        assert before is not None and after is not None
        self.assertEqual(
            (before.revision_id, before.version, before.digest),
            (after.revision_id, after.version, after.digest),
        )

    def save(self, value: dict, *, object_id: str | None = None, **overrides):
        kwargs = self.authority()
        kwargs.update(overrides)
        return self.commands.save_object(value, actor=ADMIN, object_id=object_id, **kwargs)

    # -- create / edit --------------------------------------------------

    def test_create_publishes_one_focused_disabled_successor(self) -> None:
        before = self.managed.active()
        revision = self.save(definition("nightly"))
        self.assertEqual(revision.status.value, "active")
        self.assertEqual(self.ids(), ["nightly"])
        stored = self.definitions()[0]
        self.assertIs(stored["enabled"], False)
        self.assertEqual(stored["mode"], "scan-only")
        # The previously reviewed configuration semantics are unchanged.
        self.assertEqual(
            revision.document["resourceLibraries"], before.document["resourceLibraries"]
        )
        self.assertEqual(revision.document["storages"], before.document["storages"])
        self.assertEqual(self.repository.activations, self.activations_at_baseline + 1)
        self.assertEqual(self.provider_calls, [])
        self.assertEqual(self.adapters["source-storage"].mutations, [])

    def test_create_rejects_an_enabled_candidate_without_publishing(self) -> None:
        before = self.managed.active()
        with self.assertRaises(AutomationDefinitionSaveError) as caught:
            self.save(definition("nightly", enabled=True))
        self.assertEqual(caught.exception.code, "automation_definition_enable_requires_command")
        self.assert_active_unchanged(before)
        self.assertEqual(self.repository.activations, self.activations_at_baseline)

    def test_create_rejects_a_duplicate_id(self) -> None:
        self.save(definition("nightly"))
        before = self.managed.active()
        with self.assertRaises(AutomationDefinitionSaveError) as caught:
            self.save(definition("nightly", name="Hijack"))
        self.assertEqual(caught.exception.code, "automation_definition_duplicate")
        self.assert_active_unchanged(before)
        self.assertEqual(self.definitions()[0]["name"], "Automation nightly")

    def test_edit_preserves_unsubmitted_fields_and_is_id_immutable(self) -> None:
        self.save(definition("nightly", sourceScope="incoming"))
        revision = self.save({"id": "nightly", "name": "Renamed"}, object_id="nightly")
        stored = next(
            item
            for item in revision.document[AUTOMATION_DEFINITION_SECTION]
            if item["id"] == "nightly"
        )
        self.assertEqual(stored["name"], "Renamed")
        # Fields the focused form did not submit survive the merge.
        self.assertEqual(stored["sourceScope"], "incoming")
        self.assertEqual(stored["intervalSeconds"], 3600)
        self.assertEqual(stored["itemLimit"], 10)

        before = self.managed.active()
        with self.assertRaises(AutomationDefinitionSaveError) as caught:
            self.save({"id": "other", "name": "Forged"}, object_id="nightly")
        self.assertEqual(caught.exception.code, "automation_definition_id_immutable")
        self.assert_active_unchanged(before)

    def test_schedule_switch_keeps_exactly_one_canonical_form(self) -> None:
        self.save(definition("nightly"))
        revision = self.save(
            {
                "id": "nightly",
                "cron": "0 8 * * *",
                "timezone": "UTC",
                "intervalSeconds": None,
            },
            object_id="nightly",
        )
        stored = revision.document[AUTOMATION_DEFINITION_SECTION][0]
        self.assertNotIn("intervalSeconds", stored)
        self.assertEqual(stored["cron"], "0 8 * * *")
        self.assertEqual(stored["timezone"], "UTC")

        revision = self.save(
            {"id": "nightly", "intervalSeconds": 120, "cron": None, "timezone": None},
            object_id="nightly",
        )
        stored = revision.document[AUTOMATION_DEFINITION_SECTION][0]
        self.assertEqual(stored["intervalSeconds"], 120.0)
        self.assertNotIn("cron", stored)
        self.assertNotIn("timezone", stored)

    def test_unsafe_scope_bounds_and_references_fail_before_publication(self) -> None:
        before = self.managed.active()
        for candidate, code in (
            (definition("a", sourceScope="../escape"), "automation_definition_invalid_field"),
            (definition("b", sourceScope="/absolute"), "automation_definition_invalid_field"),
            (definition("c", itemLimit=10_001), "automation_definition_invalid_field"),
            (definition("d", itemLimit=0), "automation_definition_invalid_field"),
            (definition("e", intervalSeconds=0), "automation_definition_invalid_field"),
            (
                definition("f", intervalSeconds=None, cron="not a cron", timezone="UTC"),
                "automation_definition_invalid_field",
            ),
            (
                definition("g", intervalSeconds=None, cron="0 8 * * *", timezone="Nowhere/Nope"),
                "automation_definition_invalid_field",
            ),
            (
                definition("h", resourceLibraryId="missing"),
                "automation_definition_resource_unavailable",
            ),
            (
                {**definition("i"), "runMode": "scan-only"},
                "automation_definition_invalid_request",
            ),
        ):
            with self.subTest(id=candidate.get("id")):
                with self.assertRaises(AutomationDefinitionSaveError) as caught:
                    self.save(candidate)
                self.assertEqual(caught.exception.code, code)
        self.assert_active_unchanged(before)
        self.assertEqual(self.repository.activations, self.activations_at_baseline)

    def test_disabled_resource_library_reference_is_rejected(self) -> None:
        active = self.managed.active()
        document = copy.deepcopy(active.document)
        document["resourceLibraries"][0]["enabled"] = False
        draft = self.managed.import_draft(document, actor="tester")
        validated = self.managed.validate(draft.revision_id, actor="tester")
        self.managed.activate(
            validated.revision_id, expected_version=validated.version, actor="tester"
        )
        before = self.managed.active()
        with self.assertRaises(AutomationDefinitionSaveError) as caught:
            self.save(definition("nightly"))
        self.assertEqual(caught.exception.code, "automation_definition_resource_disabled")
        self.assert_active_unchanged(before)

    def test_stale_authority_is_rejected_without_publishing(self) -> None:
        self.save(definition("nightly"))
        stale = self.authority()
        self.save({"id": "nightly", "name": "Second"}, object_id="nightly")
        with self.assertRaises(ConfigurationVersionConflict):
            self.commands.save_object(
                {"id": "nightly", "name": "Stale"},
                actor=ADMIN,
                object_id="nightly",
                **stale,
            )

    # -- independent states ---------------------------------------------

    def test_enable_and_disable_publish_without_creating_work_or_authority(self) -> None:
        self.save(definition("nightly"))
        jobs_before = len(self.runtime.list_jobs())
        enabled = self.commands.set_enabled(
            "nightly", enabled=True, actor=ADMIN, **self.authority()
        )
        stored = enabled.document[AUTOMATION_DEFINITION_SECTION][0]
        self.assertIs(stored["enabled"], True)
        self.assertEqual(len(self.runtime.list_jobs()), jobs_before)
        self.assertIsNone(self.grants.get_for_definition("nightly"))

        disabled = self.commands.set_enabled(
            "nightly", enabled=False, actor=ADMIN, **self.authority()
        )
        self.assertIs(disabled.document[AUTOMATION_DEFINITION_SECTION][0]["enabled"], False)
        self.assertEqual(len(self.runtime.list_jobs()), jobs_before)

    def test_copy_starts_disabled_with_a_new_identity_and_no_authority(self) -> None:
        self.save(definition("nightly"))
        self.commands.set_enabled("nightly", enabled=True, actor=ADMIN, **self.authority())
        revision = self.commands.copy_object("nightly", actor=ADMIN, **self.authority())
        copied = revision.document[AUTOMATION_DEFINITION_SECTION][-1]
        self.assertEqual(copied["id"], "nightly-copy")
        self.assertIs(copied["enabled"], False)
        self.assertEqual(copied["resourceLibraryId"], "source")
        self.assertIsNone(self.grants.get_for_definition("nightly-copy"))

    def test_recreating_a_removed_id_does_not_revive_authority(self) -> None:
        self.save(definition("nightly"))
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.assertEqual(self.ids(), [])
        self.save(definition("nightly", name="Recreated"))
        # A recreated definition starts disabled and has no grant of its own.
        self.assertIs(self.definitions()[0]["enabled"], False)
        self.assertIsNone(self.grants.get_for_definition("nightly"))

    # -- removal ---------------------------------------------------------

    def test_removal_revokes_future_authority_and_retains_history(self) -> None:
        self.save(definition("nightly", mode="automatic-organization"))
        self.commands.set_enabled("nightly", enabled=True, actor=ADMIN, **self.authority())
        grant = self._seed_active_grant("nightly")
        self.assertEqual(grant.status.value, "active")

        revision = self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.assertEqual(
            [item["id"] for item in revision.document.get(AUTOMATION_DEFINITION_SECTION, [])],
            [],
        )
        revoked = self.grants.get_for_definition("nightly")
        self.assertIsNotNone(revoked)
        self.assertEqual(revoked.status.value, "revoked")
        # The grant and its audit survive the removal: removal is not deletion.
        self.assertEqual(self.grants.get(grant.grant_id).status.value, "revoked")
        self.assertTrue(
            any(
                item.action == "revoked"
                for item in self.grants.list_audit(grant.grant_id, limit=10)
            )
        )

    def test_removal_preserves_siblings_and_unrelated_configuration(self) -> None:
        self.save(definition("first"))
        self.save(definition("second"))
        before = self.managed.active()
        revision = self.commands.remove_object("first", actor=ADMIN, **self.authority())
        self.assertEqual(
            [item["id"] for item in revision.document[AUTOMATION_DEFINITION_SECTION]],
            ["second"],
        )
        self.assertEqual(
            revision.document["resourceLibraries"], before.document["resourceLibraries"]
        )
        self.assertEqual(revision.document["storages"], before.document["storages"])

    def test_removal_reports_truthfully_when_authority_state_is_unavailable(self) -> None:
        self.save(definition("nightly", mode="automatic-organization"))
        self.commands.set_enabled("nightly", enabled=True, actor=ADMIN, **self.authority())

        class _FailingGrants:
            def get_for_definition(self, definition_id):
                raise RuntimeError("simulated grant persistence failure")

        commands = AutomationWorkspaceCommandService(
            self.objects, unattended_grants=_FailingGrants()
        )
        before = self.managed.active()
        with self.assertRaises(AutomationDefinitionSaveError) as caught:
            commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.assertEqual(caught.exception.code, "automation_definition_authority_unavailable")
        self.assert_active_unchanged(before)
        self.assertEqual(self.ids(), ["nightly"])

    def test_missing_definition_reads_and_commands_report_not_found(self) -> None:
        before = self.managed.active()
        for operation in (
            lambda: self.commands.edit_projection("ghost"),
            lambda: self.commands.copy_projection("ghost"),
            lambda: self.commands.removal_impact("ghost"),
            lambda: self.commands.remove_object("ghost", actor=ADMIN, **self.authority()),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(AutomationDefinitionSaveError) as caught:
                    operation()
                self.assertEqual(caught.exception.code, "automation_definition_not_found")
                self.assertEqual(caught.exception.status, 404)
        self.assert_active_unchanged(before)

    # -- reads -----------------------------------------------------------

    def test_reads_and_schedule_preview_create_nothing(self) -> None:
        self.save(definition("nightly"))
        revisions_before = len(self.repository.list_revisions())
        jobs_before = len(self.runtime.list_jobs())
        authority = self.commands.authority()
        self.assertEqual(authority["active"]["revisionId"], self.managed.active().revision_id)
        form = self.commands.form_authority()
        self.assertTrue(form["actions"]["create"])
        self.assertIn("resourceLibraryId", form["fields"])
        self.assertEqual(form["resourceLibraries"][0]["id"], "source")
        projection = self.commands.edit_projection("nightly")
        self.assertEqual(projection["definition"]["id"], "nightly")
        candidate = self.commands.copy_projection("nightly")
        self.assertIs(candidate["definition"]["enabled"], False)
        impact = self.commands.removal_impact("nightly")
        self.assertEqual(impact["unattendedAuthority"]["status"], "none")

        preview = self.commands.schedule_preview(
            {
                "id": "nightly",
                "name": "Nightly",
                "resourceLibraryId": "source",
                "mode": "scan-only",
                "cron": "0 8 * * *",
                "timezone": "UTC",
            },
            object_id="nightly",
        )
        self.assertEqual(preview["scheduleType"], "cron")
        self.assertTrue(preview["zeroMutation"])
        self.assertEqual(len(preview["upcoming"]), 5)
        self.assertEqual(len(self.repository.list_revisions()), revisions_before)
        self.assertEqual(len(self.runtime.list_jobs()), jobs_before)
        self.assertEqual(self.repository.activations, self.activations_at_baseline + 1)
        self.assertEqual(self.adapters["source-storage"].reads, [])

    def test_historical_definition_resolves_after_removal(self) -> None:
        self.save(definition("nightly", name="Before removal"))
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        historical = self.commands.historical_definition("nightly")
        self.assertIsNotNone(historical)
        self.assertEqual(historical["definition"]["name"], "Before removal")
        self.assertNotEqual(historical["revisionStatus"], "active")
        # A definition that never existed has no historical evidence.
        self.assertIsNone(self.commands.historical_definition("never-existed"))

    def test_interval_preview_notes_relative_times_without_side_effects(self) -> None:
        self.save(definition("nightly"))
        preview = self.commands.schedule_preview(
            {
                "id": "nightly",
                "name": "Nightly",
                "resourceLibraryId": "source",
                "mode": "scan-only",
                "intervalSeconds": 60,
            },
            object_id="nightly",
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
        self.assertEqual(preview["scheduleType"], "interval")
        expected = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=60)
        self.assertEqual(preview["upcoming"][0]["at"], expected.isoformat())
        self.assertTrue(preview["notes"])

    # -- boundary --------------------------------------------------------

    def test_focused_successor_keeps_sibling_and_other_sections_identical(self) -> None:
        self.save(definition("first"))
        self.save(definition("second"))
        before = self.managed.active()
        revision = self.save({"id": "first", "name": "Renamed"}, object_id="first")
        siblings_before = {
            item["id"]: item
            for item in before.document[AUTOMATION_DEFINITION_SECTION]
            if item["id"] != "first"
        }
        siblings_after = {
            item["id"]: item
            for item in revision.document[AUTOMATION_DEFINITION_SECTION]
            if item["id"] != "first"
        }
        self.assertEqual(siblings_after, siblings_before)
        for section in set(before.document) - {AUTOMATION_DEFINITION_SECTION}:
            self.assertEqual(revision.document[section], before.document[section], section)

    def test_no_active_configuration_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            (root / "target").mkdir()
            repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
            self.addCleanup(repository.close)
            managed = ManagedConfigurationService(
                repository, bootstrap_database_path=str(root / "runtime.sqlite3")
            )
            objects = ConfigurationObjectService(managed)
            commands = AutomationWorkspaceCommandService(objects)
            with self.assertRaises(Exception) as caught:
                commands.form_authority()
            self.assertEqual(getattr(caught.exception, "reason", None), "active_missing")

    def _definition_value(self, definition_id: str):
        from mediaflow.domain.automation import AutomationTaskDefinition

        stored = next(item for item in self.definitions() if item["id"] == definition_id)
        return AutomationTaskDefinition.from_document(stored)

    def _seed_active_grant(self, definition_id: str):
        """Persist one real active unattended grant through the durable repository.

        The grant admission path requires a persisted exact Preview, which is a
        separate journey; removal only has to durably revoke whatever live
        authority exists, so the durable row is seeded directly here.
        """

        from mediaflow.domain.unattended_execution import (
            UnattendedExecutionGrant,
            UnattendedExecutionGrantAudit,
            UnattendedExecutionGrantStatus,
        )

        active = self.managed.active()
        definition = self._definition_value(definition_id)
        grant = UnattendedExecutionGrant(
            "grant-nightly",
            definition_id,
            definition.resource_library_id,
            definition.source_scope,
            definition.run_mode,
            definition.item_limit,
            UnattendedExecutionGrantStatus.ACTIVE,
            "admin",
            datetime.now(UTC),
            definition.definition_fingerprint,
            active.revision_id,
            active.digest,
            active.version,
        )
        audit = UnattendedExecutionGrantAudit(
            "grant-audit-nightly",
            grant.grant_id,
            "granted",
            datetime.now(UTC),
            "admin",
            {"definitionId": definition_id},
        )
        self.runtime.create_unattended_execution_grant(grant, audit)
        return grant


if __name__ == "__main__":
    unittest.main()
