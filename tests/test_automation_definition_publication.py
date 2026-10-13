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
from dataclasses import replace
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
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
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


def _occurrence(
    definition_id: str,
    *,
    revision_id: str,
    version: int,
    digest: str,
    fingerprint: str | None,
    occurrence_id: str = "occurrence-nightly",
):
    """One durable occurrence row pinning an exact published revision."""

    from mediaflow.domain.automation import AutomationDefinitionOccurrence, AutomationTaskRunMode

    return AutomationDefinitionOccurrence(
        occurrence_id,
        definition_id,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
        "job-nightly",
        fingerprint,
        1,
        revision_id,
        version,
        digest,
        AutomationTaskRunMode.SCAN_ONLY,
        "source",
        None,
        10,
        "emitted",
        "scheduled",
        "no operator action is required",
        "task-nightly",
        None,
    )


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

    def test_concurrent_save_wins_and_removal_preserves_authority(self) -> None:
        """A legitimate concurrent focused Save between revocation and publication
        must not leave the definition Active with its grant already revoked.

        The review reproduced exactly this interleaving at the ``before_publish``
        seam: the revocation committed, then the concurrent Save published, then
        the removal activation failed — and the error construction itself raised
        ``TypeError`` for unsupported kwargs. The corrected ordering reads the
        live authority state back and reports it bounded without an unhandled
        exception, and the grant stays active.
        """

        self.save(definition("nightly", mode="automatic-organization"))
        self.commands.set_enabled("nightly", enabled=True, actor=ADMIN, **self.authority())
        self._seed_active_grant("nightly")
        active_before = self.managed.active()
        assert active_before is not None

        def concurrent_save(_successor):
            """One legitimate concurrent focused Save, interleaved in the seam."""
            import time

            time.sleep(0.05)
            self.save(definition("other", name="Sibling"))
            return None

        authority = self.authority()
        authority["before_publish"] = concurrent_save
        with self.assertRaises(AutomationDefinitionSaveError) as caught:
            self.commands.remove_object("nightly", actor=ADMIN, **authority)
        self.assertEqual(caught.exception.code, "automation_definition_removal_not_published")
        self.assertEqual(caught.exception.status, 409)
        # No unhandled TypeError: the bounded recovery document is complete.
        self.assertIn("authorityState", caught.exception.details)
        # The definition is still published and its authority is still live.
        self.assertEqual(self.ids(), ["nightly", "other"])
        current = self.grants.get_for_definition("nightly")
        self.assertIsNotNone(current)
        self.assertEqual(current.status.value, "active")
        self.assertEqual(caught.exception.details["authorityState"], "active")

    def test_concurrent_regrant_between_revocation_and_publication_is_fenced(self) -> None:
        """A legitimate confirmed regrant interleaved before publication cannot
        leave live authority on a removed definition.

        The review reproduced this with the real API: revoke -> regrant (201) ->
        removal publish succeeded with the latest grant still ``active``. The
        corrected removal re-verifies applicable authority at publication time
        and revokes any residual grant, so a successful removal never leaves
        live authority behind.
        """

        self.save(definition("nightly", mode="automatic-organization"))
        self.commands.set_enabled("nightly", enabled=True, actor=ADMIN, **self.authority())

        def concurrent_regrant(_successor):
            import time

            time.sleep(0.05)
            # The removal has already revoked the original grant inside this
            # seam. A legitimate confirmed regrant then goes live, exactly as
            # the real API reproduction did (grant -> 201).
            self._seed_active_grant("nightly", grant_id="grant-nightly-regrant")
            return None

        authority = self.authority()
        authority["before_publish"] = concurrent_regrant
        revision = self.commands.remove_object("nightly", actor=ADMIN, **authority)
        self.assertEqual(
            [item["id"] for item in revision.document.get(AUTOMATION_DEFINITION_SECTION, [])],
            [],
        )
        final = self.grants.get_for_definition("nightly")
        self.assertIsNotNone(final)
        self.assertEqual(final.status.value, "revoked")

    def test_removal_reports_truthfully_when_residual_revoke_fails(self) -> None:
        """A published removal whose residual re-revoke fails reports its
        durable state instead of silently claiming full revocation."""

        self.save(definition("nightly", mode="automatic-organization"))
        self.commands.set_enabled("nightly", enabled=True, actor=ADMIN, **self.authority())
        self._seed_active_grant("nightly")

        class _RegrantingGrants:
            """Restores live authority after the removal's residual proof.

            The reordered removal reads the grant boundary twice: the
            fail-closed pre-publication preflight and the post-publication
            residual revocation. This wrapper hooks ``get_for_definition`` for
            that second boundary: it persists one fresh ACTIVE grant row first,
            exactly like a legitimate concurrent regrant that won against the
            residual revocation. The removal must then report its durable
            state instead of claiming full revocation.
            """

            def __init__(self, inner, definition, runtime) -> None:
                self._inner = inner
                self._definition = definition
                self._runtime = runtime
                self._reads = 0

            def get_for_definition(self, definition_id):
                # The reordered removal reads the current grant twice: the
                # fail-closed pre-publication preflight and the residual
                # re-revoke lookup. On the second read a legitimate concurrent
                # regrant has just gone live: re-grant live authority right
                # before the read, so the residual revocation races against a
                # real active grant.
                self._reads += 1
                if self._reads == 2:
                    # Second read = the removal's residual re-revoke lookup:
                    # the grant was active at the preflight, the publication
                    # succeeded, and now the residual proof reads it. Re-grant
                    # live authority before the service reads.
                    from datetime import UTC, datetime

                    from mediaflow.domain.unattended_execution import (
                        UnattendedExecutionGrant,
                        UnattendedExecutionGrantAudit,
                        UnattendedExecutionGrantStatus,
                    )

                    grant = UnattendedExecutionGrant(
                        "grant-nightly-residual",
                        definition_id,
                        self._definition.resource_library_id,
                        self._definition.source_scope,
                        self._definition.run_mode,
                        self._definition.item_limit,
                        UnattendedExecutionGrantStatus.ACTIVE,
                        "regranted",
                        datetime.now(UTC),
                        self._definition.definition_fingerprint,
                        "revision-regrant",
                        "d" * 64,
                        1,
                    )
                    audit = UnattendedExecutionGrantAudit(
                        "grant-nightly-residual-audit",
                        grant.grant_id,
                        "granted",
                        datetime.now(UTC),
                        "regranted",
                        {},
                    )
                    self._runtime.create_unattended_execution_grant(grant, audit)
                return self._inner.get_for_definition(definition_id)

            def revoke(self, **kwargs):
                if self._reads >= 2:
                    # The residual revocation loses its persistence race
                    # against the re-grant: the durable revoke write fails.
                    raise RuntimeError("simulated residual revocation persistence failure")
                return self._inner.revoke(**kwargs)

        wrapper = _RegrantingGrants(self.grants, self._definition_value("nightly"), self.runtime)
        commands = AutomationWorkspaceCommandService(self.objects, unattended_grants=wrapper)
        with self.assertRaises(AutomationDefinitionSaveError) as caught:
            commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.assertEqual(caught.exception.code, "automation_definition_removal_authority_live")
        self.assertEqual(caught.exception.details["durableState"], "successor_published")
        self.assertEqual(self.ids(), [])

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

    def test_historical_definition_survives_more_publications_than_every_window(
        self,
    ) -> None:
        """P1 regression: retained history is not a bounded recent window.

        The removed definition's publication proof is durable and exact, so
        hundreds of later ordinary focused publications of another definition —
        far beyond every former bounded revision/activation scan (200 revisions,
        500 activation audits, 200 ever-published audits) — must not hide it.
        Absence from a window is not absence from durable history.

        No occurrence pin exists here, so this exercises the cursor-walked
        activation ledger: the walk must page past the 500-audit mark rather
        than stop at a bounded first page.
        """

        self.save(definition("nightly", name="Published historical name"))
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.save(definition("publisher", name="Ordinary publisher"))
        # 520 ordinary focused publications: past the former 200-revision and
        # 200/500-activation windows that used to lose the removed definition.
        for index in range(520):
            self.save(
                {"id": "publisher", "name": f"Ordinary publication {index}"},
                object_id="publisher",
            )
        historical = self.commands.historical_definition("nightly")
        self.assertIsNotNone(historical)
        self.assertEqual(historical["definition"]["name"], "Published historical name")
        self.assertEqual(historical["definition"]["id"], "nightly")
        self.assertNotEqual(historical["revisionStatus"], "active")
        # The published-versus-Draft distinction still holds at this distance.
        self.assertIsNone(self.commands.historical_definition("never-existed"))

    def test_historical_definition_uses_the_exact_occurrence_pin_beyond_the_window(
        self,
    ) -> None:
        """P1 regression: an occurrence pin resolves its exact published revision.

        The retained occurrence records the revision identity its run consumed.
        Even when the activation ledger cannot be walked at all *and* the
        pinned revision is far outside any bounded recent revision window, the
        exact pin still resolves the historical name the run used.
        """

        self.save(
            definition(
                "nightly",
                name="Published historical name",
                mode="scan-and-plan",
                sourceScope="incoming/season-01",
                itemLimit=17,
            )
        )
        active = self.managed.active()
        assert active is not None
        occurrence = _occurrence(
            "nightly",
            revision_id=active.revision_id,
            version=active.version,
            digest=active.digest,
            fingerprint=self._definition_value("nightly").definition_fingerprint,
        )
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.save(definition("publisher"))
        # Push the pinned revision far outside any bounded revision window.
        for index in range(300):
            self.save(
                {"id": "publisher", "name": f"Ordinary publication {index}"},
                object_id="publisher",
            )
        # Hide the ledger entirely: only the exact occurrence pin can resolve
        # the history, proving it depends on no window and no ledger scan.
        with (
            patch.object(type(self.repository), "list_command_audits_before", None),
            patch.object(type(self.repository), "latest_command_audit_sequence", None),
        ):
            historical = self.commands.historical_definition("nightly", occurrence=occurrence)
        self.assertIsNotNone(historical)
        self.assertEqual(historical["definition"]["name"], "Published historical name")
        self.assertEqual(historical["definition"]["mode"], "scan-and-plan")
        self.assertEqual(historical["definition"]["sourceScope"], "incoming/season-01")
        self.assertEqual(historical["definition"]["itemLimit"], 17)
        self.assertEqual(historical["revision"]["revisionId"], active.revision_id)
        self.assertEqual(historical["revision"]["version"], active.version)

    def test_historical_definition_does_not_fallback_from_a_contradictory_occurrence_pin(
        self,
    ) -> None:
        """A corrupt exact pin is unavailable, never replaced by older history.

        The occurrence claims the removal revision as the context for
        ``nightly``, but that revision does not contain ``nightly``. The older
        activation does contain it, yet using that older snapshot would silently
        misrepresent which published configuration the occurrence consumed.
        """

        self.save(definition("nightly", name="Published historical name"))
        published_definition = self._definition_value("nightly")
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        pinned_revision = self.managed.active()
        assert pinned_revision is not None
        # Supersede the pinned revision so the history resolver takes its
        # retained-history path, while preserving its exact ID/version/digest.
        self.save(definition("publisher"))
        occurrence = _occurrence(
            "nightly",
            revision_id=pinned_revision.revision_id,
            version=pinned_revision.version,
            digest=pinned_revision.digest,
            fingerprint=published_definition.definition_fingerprint,
        )

        with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
            self.commands.historical_definition("nightly", occurrence=occurrence)
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")

    def test_historical_definition_reports_unavailable_instead_of_absent_evidence(
        self,
    ) -> None:
        """P1 regression: an incomplete read is unavailability, never a 404.

        When the durable activation ledger cannot be walked, the historical read
        must raise the bounded unavailable state rather than returning ``None``,
        which the API would otherwise turn into a false 404 and a substituted
        Draft candidate.
        """

        self.save(definition("nightly", name="Published historical name"))
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())

        def failing_before(*args, **kwargs):
            raise RuntimeError("simulated truncating activation read failure")

        def failing_latest():
            raise RuntimeError("simulated truncating activation read failure")

        with (
            patch.object(type(self.repository), "list_command_audits_before", failing_before),
            patch.object(type(self.repository), "latest_command_audit_sequence", failing_latest),
        ):
            with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
                self.commands.historical_definition("nightly")
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")
        # The real readers resolve the same read truthfully.
        self.assertIsNotNone(self.commands.historical_definition("nightly"))

    def test_historical_definition_rejects_activation_rows_without_cursor_evidence(
        self,
    ) -> None:
        """A short page with a missing sequence cannot prove the ledger ended."""

        self.save(definition("nightly", name="Published historical name"))
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        real_reader = self.repository.list_command_audits_before

        def missing_sequence(_repository, actions, *, before_sequence, limit=50):
            page = real_reader(
                actions,
                before_sequence=before_sequence,
                limit=limit,
            )
            if not page:
                return page
            return (replace(page[0], sequence=None), *page[1:])

        with patch.object(type(self.repository), "list_command_audits_before", missing_sequence):
            with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
                self.commands.historical_definition("nightly")
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")

    def test_published_state_resolves_beyond_the_window_without_substituting_a_draft(
        self,
    ) -> None:
        """P1 regression: the published-versus-Draft distinction is window-free.

        A removed definition stays labelled historical and a Draft-only
        candidate stays draft-only even after hundreds of later publications,
        and an incomplete evidence read raises rather than releasing the Draft.
        """

        self.save(definition("nightly", name="Published historical name"))
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.save(definition("publisher"))
        for index in range(250):
            self.save(
                {"id": "publisher", "name": f"Ordinary publication {index}"},
                object_id="publisher",
            )
        active = self.managed.active()
        assert active is not None
        self.assertTrue(self.commands.definition_was_published("nightly"))
        self.assertFalse(self.commands.definition_was_published("publisher-draft-only"))
        # A Draft-only candidate created through the real Draft authority is
        # still reported unpublished at this distance.
        draft = self.managed.create_successor_draft(
            actor="tester",
            expected_active_revision_id=active.revision_id,
            expected_active_version=active.revision_sequence or active.version,
            expected_active_digest=active.digest,
            verified_active=active,
        )
        document = copy.deepcopy(draft.document)
        document[AUTOMATION_DEFINITION_SECTION].append(definition("draft-only-candidate"))
        self.managed.edit_draft(
            draft.revision_id,
            document,
            expected_version=draft.version,
            actor="tester",
        )
        self.assertFalse(self.commands.definition_was_published("draft-only-candidate"))

    def _publish_remove_and_keep_open_draft(self, draft_name: str) -> str:
        """Publish, remove, and retain a same-ID unpublished Draft candidate.

        Returns the exact published revision ID that is about to be corrupted.
        """

        self.save(definition("nightly", name="Published historical name"))
        published = self.managed.active()
        assert published is not None
        draft = self.managed.create_successor_draft(
            actor="tester",
            expected_active_revision_id=published.revision_id,
            expected_active_version=published.revision_sequence or published.version,
            expected_active_digest=published.digest,
            verified_active=published,
        )
        document = copy.deepcopy(draft.document)
        document[AUTOMATION_DEFINITION_SECTION][0]["name"] = draft_name
        self.managed.edit_draft(
            draft.revision_id,
            document,
            expected_version=draft.version,
            actor="tester",
        )
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        return published.revision_id

    def _corrupt_published_section(self, revision_id: str, section: object) -> None:
        """Corrupt one superseded published revision's definition section.

        Only the persisted payload is rewritten; the revision ID, its stored
        digest and its positive activation audit stay exactly as durable
        authority recorded them, which is the contradictory evidence B
        reproduced.
        """

        import sqlite3

        revision = self.repository.get_revision(revision_id)
        assert revision is not None
        payload = copy.deepcopy(revision.document)
        payload[AUTOMATION_DEFINITION_SECTION] = section
        connection = sqlite3.connect(str(self.root / "configuration.sqlite3"))
        try:
            connection.execute(
                "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                (json.dumps(payload), revision_id),
            )
            connection.commit()
        finally:
            connection.close()

    def test_corrupt_published_section_is_unavailable_not_absent_or_draft(self) -> None:
        """P1 regression: corrupt published evidence is never a false absence.

        B reproduced this with real managed publication: remove a definition,
        retain a same-ID unpublished Draft, then corrupt only the superseded
        published revision's definition section while keeping its revision ID,
        stored digest and positive activation audit. The corrupt section is
        unreadable evidence, so the resolved state must be the actionable
        unavailable one — never the unpublished Draft candidate, older context
        or a proven absence.
        """

        revision_id = self._publish_remove_and_keep_open_draft("NEVER PUBLISHED B draft")
        # Intact evidence still resolves the real published history.
        historical = self.commands.historical_definition("nightly")
        self.assertIsNotNone(historical)
        self.assertEqual(historical["definition"]["name"], "Published historical name")
        self.assertEqual(self.commands.edit_projection("nightly")["definitionState"], "historical")
        self.assertTrue(self.commands.definition_was_published("nightly"))

        self._corrupt_published_section(revision_id, "corrupt section")

        for operation in (
            lambda: self.commands.historical_definition("nightly"),
            lambda: self.commands.edit_projection("nightly"),
            lambda: self.commands.copy_projection("nightly"),
            lambda: self.commands.removal_impact("nightly"),
            lambda: self.commands.definition_was_published("nightly"),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
                    operation()
                self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")
        # A definition that genuinely never existed still resolves nothing: the
        # corrupt revision is not a blanket failure for unrelated reads.
        self.assertFalse(self.commands.definition_was_published("never-published"))

    def test_corrupt_occurrence_pinned_revision_is_unavailable(self) -> None:
        """P1 regression: a corrupt exact pin is unavailability, never absence.

        A retained occurrence pins the exact published revision its run
        consumed. When that pinned revision's definition section is
        structurally corrupt, the read must report unavailable evidence instead
        of falling back to older context, releasing the unpublished Draft or
        claiming the definition was never published.
        """

        self.save(
            definition(
                "nightly",
                name="Published historical name",
                mode="scan-and-plan",
                sourceScope="incoming/season-01",
                itemLimit=17,
            )
        )
        active = self.managed.active()
        assert active is not None
        occurrence = _occurrence(
            "nightly",
            revision_id=active.revision_id,
            version=active.version,
            digest=active.digest,
            fingerprint=self._definition_value("nightly").definition_fingerprint,
        )
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.save(definition("publisher"))
        self._corrupt_published_section(active.revision_id, "corrupt section")

        with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
            self.commands.historical_definition("nightly", occurrence=occurrence)
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")

    def test_corrupt_published_section_never_releases_the_open_draft(self) -> None:
        """P1 regression: corrupt published evidence must not release the Draft.

        The dangerous shape is a removed definition whose only readable
        same-ID candidate is an unpublished Draft. If the corrupt published
        revision were treated as absence, ``_stored_definition_state`` would
        resolve that Draft as ``draft-only`` and present never-published
        configuration as the removed run's context.
        """

        self._publish_remove_and_keep_open_draft("NEVER PUBLISHED B draft")
        published = self.repository.list_revisions(limit=50)
        superseded = [
            revision
            for revision in published
            if revision.status is ManagedConfigurationStatus.SUPERSEDED
        ]
        assert superseded, "the published revision must still be retained"
        # Corrupt every superseded revision's section: no older revision may be
        # silently substituted for the newest published evidence either.
        for revision in superseded:
            self._corrupt_published_section(revision.revision_id, "corrupt section")

        with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
            self.commands.edit_projection("nightly")
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")
        # The same-ID Draft is still stored, but it is never presented.
        draft = self.managed.latest_open_draft_containing(AUTOMATION_DEFINITION_SECTION, "nightly")
        self.assertIsNotNone(draft)

    def test_published_digest_mismatch_is_unavailable_not_absent(self) -> None:
        """P1 regression: a digest-mismatched revision is unreadable evidence.

        Rewriting the payload while leaving the stored digest untouched makes
        the revision internally contradictory. That is unavailability, not
        proof the definition was never published, and must not be skipped in
        favour of an unpublished Draft or an older revision.
        """

        revision_id = self._publish_remove_and_keep_open_draft("NEVER PUBLISHED B draft")
        import sqlite3

        revision = self.repository.get_revision(revision_id)
        assert revision is not None
        payload = copy.deepcopy(revision.document)
        payload[AUTOMATION_DEFINITION_SECTION][0]["name"] = "Tampered published name"
        connection = sqlite3.connect(str(self.root / "configuration.sqlite3"))
        try:
            connection.execute(
                "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                (json.dumps(payload), revision_id),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
            self.commands.historical_definition("nightly")
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")
        with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
            self.commands.definition_was_published("nightly")
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")

    def test_published_invalid_document_digest_is_unavailable_not_absent(self) -> None:
        """P1 regression: an invalid stored document digest is unreadable evidence.

        The other direction of the same contradiction is a persisted digest
        that is not the SHA-256 of its payload. The revision cannot be consumed
        as published evidence, so the read is unavailable rather than a false
        absence that would release the unpublished Draft.
        """

        revision_id = self._publish_remove_and_keep_open_draft("NEVER PUBLISHED B draft")
        import sqlite3

        connection = sqlite3.connect(str(self.root / "configuration.sqlite3"))
        try:
            connection.execute(
                "UPDATE managed_configuration_revisions SET digest=? WHERE revision_id=?",
                ("f" * 64, revision_id),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
            self.commands.historical_definition("nightly")
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")
        with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
            self.commands.edit_projection("nightly")
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")

    def test_activation_naming_an_unreadable_revision_is_unavailable(self) -> None:
        """P1 regression: audit/revision contradiction is unreadable evidence.

        The activation audit positively names the definition, but the verified
        published document no longer carries it. The two durable records
        contradict each other, so the read is unavailable and must not resolve
        a different, older revision as if it were the removed run's context.
        """

        self.save(definition("nightly", name="Published historical name"))
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.save(definition("publisher"))
        for revision in self.repository.list_revisions(limit=50):
            if revision.status is not ManagedConfigurationStatus.SUPERSEDED:
                continue
            if not any(
                str(item.get("id")) == "nightly"
                for item in self.objects._automation_definition_objects(revision.document)
            ):
                continue
            # Keep the section structurally valid but remove the definition it
            # positively activated: the activation evidence now contradicts the
            # verified document rather than proving a different publication.
            self._corrupt_published_section(revision.revision_id, [definition("other")])

        with self.assertRaises(RuntimeSnapshotUnavailable) as caught:
            self.commands.historical_definition("nightly")
        self.assertEqual(caught.exception.reason, "historical_evidence_unavailable")

    def test_intact_and_absent_history_remain_distinct_after_corruption(self) -> None:
        """P1 regression: unavailable, intact and genuinely absent stay distinct.

        Corrupting one removed definition's published evidence must not turn
        another definition's intact retained history, or a genuinely absent
        definition, into an unavailable read.
        """

        self.save(definition("nightly", name="Published historical name"))
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.save(definition("retained", name="Retained historical name"))
        self.commands.remove_object("retained", actor=ADMIN, **self.authority())
        retained_revision = next(
            revision
            for revision in self.repository.list_revisions(limit=50)
            if revision.status is ManagedConfigurationStatus.SUPERSEDED
            and any(
                str(item.get("id")) == "retained"
                for item in self.objects._automation_definition_objects(revision.document)
            )
        )
        nightly_revision = next(
            revision
            for revision in self.repository.list_revisions(limit=50)
            if revision.status is ManagedConfigurationStatus.SUPERSEDED
            and any(
                str(item.get("id")) == "nightly"
                for item in self.objects._automation_definition_objects(revision.document)
            )
        )
        self._corrupt_published_section(nightly_revision.revision_id, "corrupt section")

        with self.assertRaises(RuntimeSnapshotUnavailable):
            self.commands.historical_definition("nightly")
        # The unrelated definition's intact history is unaffected.
        intact = self.commands.historical_definition("retained")
        self.assertIsNotNone(intact)
        self.assertEqual(intact["definition"]["name"], "Retained historical name")
        self.assertEqual(intact["revision"]["revisionId"], retained_revision.revision_id)
        # A definition with no activation evidence at all is still a true absence.
        self.assertIsNone(self.commands.historical_definition("never-published"))
        self.assertFalse(self.commands.definition_was_published("never-published"))
        # Genuine Draft-only recovery is also unaffected: a fresh candidate that
        # was never published still resolves draft-only for explicit correction.
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
        document[AUTOMATION_DEFINITION_SECTION].append(definition("draft-only-candidate"))
        self.managed.edit_draft(
            draft.revision_id,
            document,
            expected_version=draft.version,
            actor="tester",
        )
        state = self.commands.edit_projection("draft-only-candidate")
        self.assertEqual(state["definitionState"], "draft-only")
        self.assertEqual(state["definition"]["id"], "draft-only-candidate")

    def test_copy_intent_resolves_committed_copy_from_durable_evidence(self) -> None:
        """P1-5 regression: a Copy whose response was lost must reconcile.

        After the copy command commits durably, ``copy_intent`` reads the
        persisted command audit and reports the exact committed identity
        instead of letting the browser allocate another copy.
        """

        self.save(definition("nightly"))
        revision = self.commands.copy_object("nightly", actor=ADMIN, **self.authority())
        copied_id = revision.document[AUTOMATION_DEFINITION_SECTION][-1]["id"]
        intent = self.commands.copy_intent("nightly")
        self.assertTrue(intent["committed"])
        self.assertEqual(intent["committedDefinitionId"], copied_id)
        self.assertIsNotNone(intent["lastObserved"])
        self.assertTrue(intent["lastObserved"]["published"])
        self.assertEqual(intent["lastObserved"]["candidateId"], copied_id)
        self.assertIsNotNone(intent["active"])

    def test_copy_intent_reports_unknown_outcome_without_publication_evidence(self) -> None:
        """A copy command that never published (validation failed) is unknown,
        not committed: the read says deliberate resubmission is possible."""

        self.save(definition("nightly"))
        with self.assertRaises(AutomationDefinitionSaveError):
            self.save(definition("copy-attempt", resourceLibraryId="missing"))
        intent = self.commands.copy_intent("nightly")
        self.assertFalse(intent["committed"])
        self.assertIsNone(intent["committedDefinitionId"])
        self.assertEqual(intent["observedCommands"], 0)

    def test_copy_intent_read_is_zero_side_effect(self) -> None:
        self.save(definition("nightly"))
        revisions_before = len(self.repository.list_revisions())
        jobs_before = len(self.runtime.list_jobs())
        self.commands.copy_intent("nightly")
        self.assertEqual(len(self.repository.list_revisions()), revisions_before)
        self.assertEqual(len(self.runtime.list_jobs()), jobs_before)

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

    def test_removal_persistence_failure_preserves_authority(self) -> None:
        """P1 regression: a persistence/concurrency failure inside the removal
        publication boundary is a known failed removal — the Active definition
        and its live unattended authority are preserved and reported, so an
        already-admitted Job is not failed by the removal command itself.

        The review reproduced this with a real second SQLite writer holding
        ``BEGIN IMMEDIATE`` between runtime preparation and activation: the
        prior removal implementation let ``OperationalError: database is
        locked`` escape after its revocation had already committed, so the
        definition stayed Active but its grant was revoked and the admitted
        Job then failed in the real Worker with
        ``unattended_execution_grant_revoked``. The corrected removal revokes
        only after a *proven* publication, so a failed activation never
        touches authority at all — no compensation write is needed or
        attempted, and the lock on the shared database can never strand a
        revoked grant behind an Active definition.
        """

        self.save(definition("nightly", mode="automatic-organization"))
        self.commands.set_enabled("nightly", enabled=True, actor=ADMIN, **self.authority())
        self._seed_active_grant("nightly")
        admitted = self._definition_value("nightly")
        writer: list = []

        def contention(_successor):
            """One ordinary production writer holds the write lock meanwhile."""

            import sqlite3
            import time

            time.sleep(0.05)
            # The SAME SQLite file the fixture's configuration and runtime
            # repositories share is not possible here — this fixture keeps
            # them separate, and the same-file production arrangement is
            # proven by tests.test_v2_automation_lifecycle.
            # SameFileRemovalAuthorityTests. This test proves the application
            # ordering itself: the activation fails and no grant write was
            # attempted through the grant boundary at all.
            connection = sqlite3.connect(str(self.root / "configuration.sqlite3"), timeout=0.05)
            connection.execute("BEGIN IMMEDIATE")
            writer.append(connection)

        authority = self.authority()
        authority["before_publish"] = contention
        try:
            with self.assertRaises(AutomationDefinitionSaveError) as caught:
                self.commands.remove_object("nightly", actor=ADMIN, **authority)
        finally:
            for connection in writer:
                try:
                    connection.rollback()
                    connection.close()
                except Exception:
                    pass
        self.assertEqual(caught.exception.code, "automation_definition_removal_not_published")
        self.assertIn(
            caught.exception.details["durableState"],
            {"active_preserved", "commit_state_unknown"},
        )
        # The definition is still published...
        self.assertEqual(self.ids(), ["nightly"])
        # ...and its live authority survived the failed removal, so the
        # already-admitted Job is not failed by this command.
        current = self.grants.get_for_definition("nightly")
        self.assertIsNotNone(current)
        self.assertEqual(current.status.value, "active")
        # The live authority state is reported in the recovery document.
        self.assertIn(
            caught.exception.details.get("authorityState"),
            {"active", "none", "unavailable"},
        )
        # The admitted definition still authorizes against the live grant: a
        # job carrying its identity, bounds, scope and the granted snapshot
        # authorizes without the worker refusing revoked authority the failed
        # removal would have left behind.  (The grant in this fixture has no
        # Preview linkage, so only the grant's own match/snapshot bounds are
        # asserted here — the exact-Preview admission journey is covered by
        # the dedicated Preview/grant suites.)
        from types import SimpleNamespace

        active_now = self.managed.active()
        assert active_now is not None
        job = SimpleNamespace(
            definition_id=admitted.definition_id,
            resource_library_id=admitted.resource_library_id,
            source_scope=admitted.source_scope,
            run_mode=admitted.run_mode,
            limit=admitted.item_limit,
            configuration_snapshot_id=active_now.revision_id,
            configuration_snapshot_digest=active_now.digest,
            configuration_snapshot_version=active_now.version,
        )
        grant = self.grants._get_active(admitted.definition_id)
        self.assertIsNotNone(grant)
        self.assertEqual(grant.status.value, "active")
        self.grants._assert_match(grant, job, admitted)

    def test_removal_persistence_failure_before_revocation_preserves_authority(self) -> None:
        """A Draft-edit persistence failure precedes any revocation: the live
        authority is untouched and the bounded error reports that truth."""

        self.save(definition("nightly", mode="automatic-organization"))
        self.commands.set_enabled("nightly", enabled=True, actor=ADMIN, **self.authority())
        self._seed_active_grant("nightly")

        def failing_mutate(*args, **kwargs):
            raise RuntimeError("simulated configuration store failure")

        with patch.object(self.commands._objects, "mutate", failing_mutate):
            with self.assertRaises(AutomationDefinitionSaveError) as caught:
                self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        self.assertEqual(caught.exception.code, "automation_definition_persistence_failed")
        self.assertEqual(caught.exception.details["durableState"], "active_preserved")
        self.assertEqual(self.ids(), ["nightly"])
        self.assertEqual(self.grants.get_for_definition("nightly").status.value, "active")

    def test_historical_definition_never_substitutes_an_open_draft(self) -> None:
        """P1 regression: retained history resolves from published evidence.

        Publish and enable a definition, emit a real occurrence, and keep a
        compatible open successor Draft with a different name. After removal
        the retained history is the *published* configuration the run used —
        never the unpublished Draft candidate, today's configuration or
        another definition.
        """

        self.save(definition("nightly", name="Published historical name"))
        self.commands.set_enabled("nightly", enabled=True, actor=ADMIN, **self.authority())
        # An open successor Draft with an unpublished name, derived from the
        # same Active through the normal managed authority.
        active = self.managed.active()
        draft = self.managed.create_successor_draft(
            actor="tester",
            expected_active_revision_id=active.revision_id,
            expected_active_version=active.revision_sequence or active.version,
            expected_active_digest=active.digest,
            verified_active=active,
        )
        document = copy.deepcopy(draft.document)
        definitions = document[AUTOMATION_DEFINITION_SECTION]
        definitions[0]["name"] = "NEVER PUBLISHED draft name"
        self.managed.edit_draft(
            draft.revision_id,
            document,
            expected_version=draft.version,
            actor="tester",
        )
        self.commands.remove_object("nightly", actor=ADMIN, **self.authority())
        historical = self.commands.historical_definition("nightly")
        self.assertIsNotNone(historical)
        self.assertEqual(historical["definition"]["name"], "Published historical name")
        self.assertNotEqual(historical["definition"]["name"], "NEVER PUBLISHED draft name")
        self.assertEqual(historical["definition"]["id"], "nightly")

    def test_copy_intent_binds_to_the_submitted_intent(self) -> None:
        """P1 regression: a committed Copy's reconciliation resolves that exact
        submission, never a later submission's copy, and the read is bound to
        the authority the intent was submitted against."""

        self.save(definition("nightly"))
        # The first Copy is submitted against the observed Active; its fence
        # identity is captured before the command publishes.
        first_fence = self.authority()
        first = self.commands.copy_object("nightly", actor=ADMIN, **self.authority())
        first_copy_id = first.document[AUTOMATION_DEFINITION_SECTION][-1]["id"]
        # A second legitimate submission commits another copy afterwards.
        second = self.commands.copy_object("nightly", actor=ADMIN, **self.authority())
        second_copy_id = second.document[AUTOMATION_DEFINITION_SECTION][-1]["id"]
        self.assertNotEqual(first_copy_id, second_copy_id)
        # The unfenced read resolves the newest source-matching command.
        unfenced = self.commands.copy_intent("nightly")
        self.assertTrue(unfenced["committed"])
        self.assertEqual(unfenced["committedDefinitionId"], second_copy_id)
        # The fenced read bound to the FIRST intent's observed authority
        # resolves that exact submission, never a later submission's copy.
        fenced_first = self.commands.copy_intent("nightly", **first_fence)
        self.assertTrue(fenced_first["committed"])
        self.assertEqual(fenced_first["committedDefinitionId"], first_copy_id)
        # A fence from an authority that no observed command was submitted
        # against reports no committed outcome for that intent.
        stale_fence = self.commands.copy_intent(
            "nightly",
            expected_revision_id="revision-that-never-hosted-a-copy",
            expected_version=1,
            expected_digest="f" * 64,
        )
        self.assertFalse(stale_fence["committed"])
        self.assertIsNone(stale_fence["committedDefinitionId"])

    def test_copy_intent_resolves_a_committed_copy_beyond_the_recent_audit_window(self) -> None:
        """P1 regression: absence from a bounded recent scan is not proof.

        A Copy commits durably; hundreds of ordinary supported focused edits
        then push the original command far outside any recent global audit
        window. The reconciliation must still locate the submitted command
        through the targeted durable audit trail and prove its candidate's
        publication from that revision's activation evidence — and, symmetric
        to that, it must never report "no copy was published" merely because
        the command is outside a bounded window.
        """

        self.save(definition("nightly"))
        published = self.commands.copy_object("nightly", actor=ADMIN, **self.authority())
        copy_id = published.document[AUTOMATION_DEFINITION_SECTION][-1]["id"]
        # 300 ordinary supported focused edits, far beyond any recent window.
        for index in range(300):
            self.save({"id": "nightly", "name": f"Edit {index}"}, object_id="nightly")
        intent = self.commands.copy_intent("nightly")
        self.assertTrue(intent["committed"])
        self.assertEqual(intent["committedDefinitionId"], copy_id)
        self.assertIsNotNone(intent["lastObserved"])
        self.assertTrue(intent["lastObserved"]["published"])
        self.assertEqual(intent["lastObserved"]["candidateId"], copy_id)
        self.assertTrue(intent["lastObserved"].get("publishedRevisionId"))
        self.assertTrue(intent["sourcePresent"])

    def test_copy_intent_keeps_an_unknown_outcome_when_publication_cannot_be_proven(self) -> None:
        """A located command whose publication cannot be proven stays unknown.

        A copy command is audited (its Draft edit exists) but the durable
        activation evidence for its own recorded revision does not name an
        activation — the honest report is an unknown outcome, never "genuinely
        unpublished", so the operator reconciles against the durable inventory
        instead of blindly resubmitting a second copy.
        """

        self.save(definition("nightly"))
        # Record a real copy command, then hide its revision's own activation
        # evidence from the reconciliation reads only (the publication boundary
        # itself is untouched): the located command's candidate can then not be
        # proven published from durable evidence.
        real_revision_audits = self.repository.list_revision_audits

        def activation_hidden(_repository, revision_id, *, limit=50):
            return tuple(
                audit
                for audit in real_revision_audits(revision_id, limit=limit)
                if audit.action != "activate"
            )

        self.commands.copy_object("nightly", actor=ADMIN, **self.authority())
        with patch.object(type(self.repository), "list_revision_audits", activation_hidden):
            intent = self.commands.copy_intent("nightly")
        # The command is located and observed...
        self.assertEqual(intent["observedCommands"], 1)
        self.assertIsNotNone(intent["lastObserved"])
        self.assertFalse(intent["lastObserved"]["published"])
        # ...but the outcome stays unknown: no committed identity is named and
        # the next action directs the operator to reconcile, not to blindly
        # treat the copy as never published.
        self.assertFalse(intent["committed"])
        self.assertIsNone(intent["committedDefinitionId"])
        self.assertIn("reconcile", intent["nextAction"].lower())

    def test_copy_intent_reports_incomplete_evidence_as_unknown_and_blocks_release(self) -> None:
        """A truncated/incomplete durable read is unknown, never "unpublished".

        P1 (fix loop 4) regression: the release action must depend on a
        *complete* evidence read. When the durable audit readers fail (a
        truncated or unavailable read), the reconciliation must not claim that
        no command was ever submitted — even though it observed zero commands —
        because absence of evidence is not evidence of absence. A duplicate
        copy must therefore stay blocked.
        """

        self.save(definition("nightly"))

        def failing_before(*args, **kwargs):
            raise RuntimeError("simulated truncating audit read failure")

        def failing_latest():
            raise RuntimeError("simulated truncating audit read failure")

        with (
            patch.object(type(self.repository), "list_command_audits_before", failing_before),
            patch.object(type(self.repository), "latest_command_audit_sequence", failing_latest),
        ):
            intent = self.commands.copy_intent("nightly")
        # Nothing was disproven, so nothing may be presented as proven
        # non-publication: the evidence read is explicitly incomplete and the
        # duplicate-copy block must hold.
        self.assertFalse(intent["committed"])
        self.assertIsNone(intent["committedDefinitionId"])
        self.assertEqual(intent["observedCommands"], 0)
        self.assertFalse(intent["evidenceComplete"])
        self.assertIn("unknown", intent["nextAction"].lower())

    def test_copy_intent_never_releases_a_committed_copy_outside_a_window_reader(self) -> None:
        """A window-only reader must not release a copy it cannot see.

        P1 (fix loop 4) regression, the exact production shape B reproduced:
        a Copy commits durably, then ordinary focused edits push its command
        row outside a *bounded* reader's window. The bounded reader observes
        zero commands — which used to read as "genuinely unpublished" and
        released a second Copy. The read must instead report the evidence as
        incomplete so the block holds and no duplicate is allocated.
        """

        self.save(definition("nightly"))
        published = self.commands.copy_object("nightly", actor=ADMIN, **self.authority())
        copy_id = published.document[AUTOMATION_DEFINITION_SECTION][-1]["id"]
        # Push the copy's command row beyond a 200-row window with ordinary
        # supported focused edits.
        for index in range(205):
            self.save({"id": "nightly", "name": f"Edit {index}"}, object_id="nightly")
        with (
            patch.object(type(self.repository), "list_command_audits_before", None),
            patch.object(type(self.repository), "latest_command_audit_sequence", None),
        ):
            intent = self.commands.copy_intent("nightly")
        # The bounded reader cannot see the committed command...
        self.assertEqual(intent["observedCommands"], 0)
        # ...so the outcome must stay unknown instead of claiming a proven
        # non-publication that would release a duplicate Copy.
        self.assertFalse(intent["evidenceComplete"])
        self.assertFalse(intent["committed"])
        self.assertIsNone(intent["committedDefinitionId"])
        self.assertIn("unknown", intent["nextAction"].lower())
        # The real paging reader still resolves the original committed identity.
        resolved = self.commands.copy_intent("nightly")
        self.assertTrue(resolved["evidenceComplete"])
        self.assertTrue(resolved["committed"])
        self.assertEqual(resolved["committedDefinitionId"], copy_id)

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

    def _seed_active_grant(self, definition_id: str, *, grant_id: str = "grant-nightly"):
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
            grant_id,
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
            f"{grant_id}-audit",
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
