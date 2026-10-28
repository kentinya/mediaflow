"""Task46.5: real checked publication, normal Scheduler and live intent boundaries."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime, timedelta

from mediaflow.application.automation import IntervalScheduler
from mediaflow.application.automation_execution_intent import activation_evidence, resolve_principal
from mediaflow.application.unattended_execution import UnattendedExecutionBoundaryError
from mediaflow.domain.automation import AutomationTaskDefinition, SchedulerConfigurationSnapshot
from mediaflow.domain.configuration_management import AutomationDefinitionSaveError
from tests import test_v2_automation_lifecycle as lifecycle


class ExecutionIntentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = lifecycle.AutomationLifecycleApiTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        status, body = f.request(
            "POST",
            lifecycle.BASE,
            {**f.authority(), "object": lifecycle._definition(enabled=False)},
        )
        self.assertEqual(200, status, body)

    def enable(self):
        f = self.fixture
        status, body = f.request("POST", lifecycle.BASE + "/nightly/enable", f.authority())
        self.assertEqual(200, status, body)
        active = f.managed.active()
        definition = AutomationTaskDefinition.from_document(
            active.document["automationTaskDefinitions"][0]
        )
        return active, definition

    def scheduler(self, active, definition):
        f = self.fixture
        snapshot = SchedulerConfigurationSnapshot(
            active.revision_id,
            active.digest,
            (),
            100,
            (definition,),
            active.version,
            ("source",),
            ("source",),
        )
        return IntervalScheduler(
            f.runtime,
            (),
            configuration_snapshot_resolver=lambda: snapshot,
            execution_authority=f.api._unattended_grants,
        )

    def publish(self, document, actor="admin"):
        f = self.fixture
        draft = f.managed.import_draft(document, actor=actor)
        validated = f.managed.validate(draft.revision_id, actor=actor)
        self.assertEqual("validated", validated.status.value, validated.validation_errors)
        return f.managed.activate(
            validated.revision_id, expected_version=validated.version, actor=actor
        )

    def test_checked_enable_supplies_scoped_principal_without_grants_or_immediate_work(self):
        active, definition = self.enable()
        f = self.fixture
        self.assertEqual((), f.runtime.list_jobs())
        self.assertEqual((), f.runtime.list_tasks())
        self.assertEqual((), f.runtime.list_unattended_execution_grants())
        (job,) = self.scheduler(active, definition).tick(datetime.now(UTC))
        principal = resolve_principal(f.managed, job, definition)
        self.assertEqual("admin", principal.principal_id)
        self.assertFalse(principal.trusted_local)
        self.assertIsNone(f.api._unattended_grants.authorize(job, definition).grant)
        audit = activation_evidence(f.managed.repository, active)
        self.assertEqual(
            "admin", audit.after["automationExecutionIntents"]["nightly"]["principalId"]
        )

    def test_disable_and_removal_stop_unperformed_scheduled_effects_on_pinned_work(self):
        active, definition = self.enable()
        f = self.fixture
        (job,) = self.scheduler(active, definition).tick(datetime.now(UTC))
        status, body = f.request("POST", lifecycle.BASE + "/nightly/disable", f.authority())
        self.assertEqual(200, status, body)
        with self.assertRaises(UnattendedExecutionBoundaryError):
            f.api._unattended_grants.assert_live(job, definition)
        status, body = f.request("DELETE", lifecycle.BASE + "/nightly", f.authority())
        self.assertEqual(200, status, body)
        with self.assertRaises(UnattendedExecutionBoundaryError):
            f.api._unattended_grants.assert_live(job, definition)
        self.assertEqual((), f.runtime.list_tasks())
        self.assertEqual(active.revision_id, job.configuration_snapshot_id)

    def test_live_permission_loss_stops_next_effect_and_next_due_admission(self):
        active, definition = self.enable()
        f = self.fixture
        now = datetime.now(UTC)
        (job,) = self.scheduler(active, definition).tick(now)
        document = copy.deepcopy(active.document)
        document["api"]["principals"][0]["roles"] = ["viewer"]
        successor = self.publish(document)
        # Unrelated role publication retains the original principal, never launders it.
        self.assertEqual("admin", resolve_principal(f.managed, job, definition).principal_id)
        with self.assertRaises(UnattendedExecutionBoundaryError):
            f.api._unattended_grants.assert_live(job, definition)
        self.assertEqual((), self.scheduler(successor, definition).tick(now + timedelta(hours=2)))
        self.assertEqual(1, len(f.runtime.list_jobs()))

    def test_generic_activation_cannot_expand_enabled_scope_without_execution_permission(self):
        active, _ = self.enable()
        f = self.fixture
        document = copy.deepcopy(active.document)
        document["automationTaskDefinitions"][0]["itemLimit"] = 20
        with self.assertRaises(AutomationDefinitionSaveError) as error:
            self.publish(document, actor="viewer")
        self.assertEqual(403, error.exception.status)
        self.assertEqual(active.revision_id, f.managed.active().revision_id)
        self.assertEqual((), f.runtime.list_jobs())

    def test_unrelated_publication_retains_exact_intent_without_reauthorizing_scope(self):
        active, definition = self.enable()
        f = self.fixture
        document = copy.deepcopy(active.document)
        document["automation"]["workerPollSeconds"] = 2
        published = self.publish(document, actor="viewer")
        (job,) = self.scheduler(published, definition).tick(datetime.now(UTC))
        self.assertEqual("admin", resolve_principal(f.managed, job, definition).principal_id)

    def test_exact_publication_reconciliation_is_principal_and_candidate_bound(self):
        f = self.fixture
        observed = f.managed.active()
        candidate = lifecycle._definition(name="Updated", enabled=False)
        status, saved = f.request(
            "PUT", lifecycle.BASE + "/nightly", {**f.authority(), "object": candidate}
        )
        self.assertEqual(200, status, saved)
        body = {
            "action": "edit",
            "object": candidate,
            "expectedRevisionId": observed.revision_id,
            "expectedVersion": observed.revision_sequence or observed.version,
            "expectedDigest": observed.digest,
        }
        status, result = f.request("POST", lifecycle.BASE + "/nightly/publication-intent", body)
        self.assertEqual(200, status, result)
        self.assertEqual("published", result["state"])
        self.assertEqual(
            saved["active"]["revisionId"], result["publication"]["active"]["revisionId"]
        )
        status, other = f.request(
            "POST",
            lifecycle.BASE + "/nightly/publication-intent",
            body,
            token=lifecycle.VIEWER_TOKEN,
        )
        self.assertEqual(200, status, other)
        self.assertEqual("unknown", other["state"])
        status, changed = f.request(
            "POST",
            lifecycle.BASE + "/nightly/publication-intent",
            {**body, "object": {**candidate, "name": "Other"}},
        )
        self.assertEqual("unknown", changed["state"])
        self.assertEqual((), f.runtime.list_jobs())

    def test_local_publication_uses_local_identity_instead_of_actor_text(self):
        import os

        from mediaflow.application.configuration_snapshot import ManagedConfigurationService

        f = self.fixture
        local = ManagedConfigurationService(
            f.repository, bootstrap_database_path=str(f.root / "runtime.sqlite3")
        )
        document = copy.deepcopy(local.active().document)
        document["automationTaskDefinitions"][0]["enabled"] = True
        draft = local.import_draft(document, actor="forged-remote-admin")
        validated = local.validate(draft.revision_id, actor="forged-remote-admin")
        published = local.activate(
            validated.revision_id, expected_version=validated.version, actor="forged-remote-admin"
        )
        intent = activation_evidence(f.repository, published).after["automationExecutionIntents"][
            "nightly"
        ]
        self.assertEqual(f"local:{os.getuid()}", intent["principalId"])
        self.assertTrue(intent["trustedLocal"])

    def test_corrupt_or_missing_publication_evidence_fails_closed(self):
        active, definition = self.enable()
        f = self.fixture
        (job,) = self.scheduler(active, definition).tick(datetime.now(UTC))
        from unittest.mock import patch

        with patch.object(f.managed.repository, "list_audits", side_effect=OSError("unavailable")):
            with self.assertRaises(Exception):
                f.api._unattended_grants.authorize(job, definition)
        self.assertEqual((), f.runtime.list_tasks())

    def test_reenable_does_not_resurrect_pre_disable_job(self):
        active, definition = self.enable()
        f = self.fixture
        (old_job,) = self.scheduler(active, definition).tick(datetime.now(UTC))
        status, body = f.request("POST", lifecycle.BASE + "/nightly/disable", f.authority())
        self.assertEqual(200, status, body)
        successor, enabled = self.enable()
        with self.assertRaises(UnattendedExecutionBoundaryError) as failure:
            f.api._unattended_grants.assert_live(old_job, definition)
        self.assertEqual("scheduled_intent_stopped", failure.exception.category)
        # The normal next due owns a fresh intent; it is not an old-job retry.
        (new_job,) = self.scheduler(successor, enabled).tick(datetime.now(UTC) + timedelta(hours=2))
        f.api._unattended_grants.assert_live(new_job, enabled)
        self.assertNotEqual(old_job.job_id, new_job.job_id)

    def test_enabled_successor_keeps_legitimate_admitted_pin(self):
        active, definition = self.enable()
        f = self.fixture
        (job,) = self.scheduler(active, definition).tick(datetime.now(UTC))
        document = copy.deepcopy(active.document)
        document["automationTaskDefinitions"][0]["name"] = "Changed presentation"
        self.publish(document)
        f.api._unattended_grants.assert_live(job, definition)
        self.assertEqual(active.revision_id, job.configuration_snapshot_id)

    def test_revoked_historical_grant_does_not_gate_checked_enabled_work(self):
        from tests.test_automation_definition_execution import (
            SNAPSHOT_DIGEST,
            SNAPSHOT_ID,
            _grant_service,
        )

        active, definition = self.enable()
        f = self.fixture
        (job,) = self.scheduler(active, definition).tick(datetime.now(UTC))
        historical = _grant_service(f.runtime, definition)
        grant = historical.grant(
            definition,
            configuration_snapshot_id=SNAPSHOT_ID,
            configuration_snapshot_digest=SNAPSHOT_DIGEST,
            configuration_snapshot_version=1,
            actor="admin",
            confirmation=True,
        )
        historical.revoke(grant.grant_id, actor="admin", reason="retained history")
        self.assertIsNone(f.api._unattended_grants.authorize(job, definition).grant)
        f.api._unattended_grants.assert_live(job, definition)

    def test_unreferenced_storage_publication_does_not_create_execution_intent(self):
        active, definition = self.enable()
        f = self.fixture
        document = copy.deepcopy(active.document)
        document["storages"].append(
            {
                "id": "unrelated",
                "name": "Unrelated",
                "type": "local",
                "rootPath": str(f.root / "unrelated"),
                "enabled": True,
            }
        )
        successor = self.publish(document, actor="viewer")
        (job,) = self.scheduler(successor, definition).tick(datetime.now(UTC))
        self.assertEqual("admin", resolve_principal(f.managed, job, definition).principal_id)

    def test_pre_amendment_enabled_publication_uses_actual_legacy_actor_without_toggle(self):
        import json

        active, definition = self.enable()
        f = self.fixture
        audit = activation_evidence(f.repository, active)
        # Temporary supported legacy audit fixture: before Task46.5 this field
        # did not exist. Retain the original real actor and immutable revision.
        legacy_after = dict(audit.after)
        legacy_after.pop("automationExecutionIntents")
        with f.repository._connection:
            f.repository._connection.execute(
                "UPDATE configuration_change_audits SET after_json=? WHERE audit_id=?",
                (json.dumps(legacy_after), audit.audit_id),
            )
        (job,) = self.scheduler(active, definition).tick(datetime.now(UTC))
        self.assertEqual("admin", resolve_principal(f.managed, job, definition).principal_id)
        f.api._unattended_grants.assert_live(job, definition)
        self.assertEqual((), f.runtime.list_unattended_execution_grants())

    def test_resident_permission_reader_uses_current_managed_database_without_environment_locator(
        self,
    ):
        from mediaflow.domain.security import ApiPermission
        from mediaflow.final_cli import (
            _ConfiguredPermissionAuthority,
            _current_automation_configuration,
        )

        fixture = lifecycle.SameFileRemovalAuthorityTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        reader = _ConfiguredPermissionAuthority(
            lambda: _current_automation_configuration(fixture.database)
        )
        self.assertTrue(reader.has_permission("admin", ApiPermission.GRANT_UNATTENDED_EXECUTION))
        document = copy.deepcopy(fixture.managed.active().document)
        document["api"]["principals"][0]["roles"] = ["viewer"]
        draft = fixture.managed.import_draft(document, actor="admin")
        validated = fixture.managed.validate(draft.revision_id, actor="admin")
        fixture.managed.activate(
            validated.revision_id, expected_version=validated.version, actor="admin"
        )
        self.assertFalse(reader.has_permission("admin", ApiPermission.GRANT_UNATTENDED_EXECUTION))
