from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationVersionConflict,
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request


class SuccessorDraftLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repository = SQLiteConfigurationRepository(self.root / "configuration.sqlite3")
        self.task_repository = SQLiteTaskRepository(self.root / "runtime.sqlite3")
        self.service = ManagedConfigurationService(self.repository)
        self.objects = ConfigurationObjectService(self.service)
        self.document = example_document()
        self.document["persistence"]["databasePath"] = str(self.root / "configuration.sqlite3")
        self.document["storages"][0]["rootPath"] = str(self.root / "source")
        self.document["storages"][1]["rootPath"] = str(self.root / "target")
        self.document["resourceLibraries"][0]["storagePath"] = "incoming"
        self.document["mediaLibraries"][0]["rootPath"] = "Movies"
        self.document["automationTaskDefinitions"] = [
            {
                "id": "scan-task",
                "name": "Scan task",
                "resourceLibraryId": "source",
                "mode": "scan_only",
                "intervalSeconds": 3600,
                "enabled": True,
            }
        ]
        self.api = MediaFlowApi(
            self.task_repository,
            None,
            principals=(
                ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ResolvedApiPrincipal(
                    "readonly",
                    "readonly-token",
                    frozenset({ApiPermission.READ}),
                ),
            ),
            configuration_service=self.service,
            bootstrap_document=self.document,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.task_repository.close()
        self.temp_dir.cleanup()

    def _activate_initial(self):
        draft = self.service.import_draft(self.document, actor="setup")
        validated = self.service.validate(draft.revision_id, actor="setup")
        return self.service.activate(
            validated.revision_id,
            expected_version=validated.version,
            actor="setup",
        )

    def test_create_successor_draft_fails_closed_without_active(self) -> None:
        with self.assertRaises(RuntimeSnapshotUnavailable) as error:
            self.service.create_successor_draft(actor="tester")
        self.assertEqual(error.exception.reason, "active_missing")

    def test_create_successor_draft_creates_draft_from_active_snapshot(self) -> None:
        active = self._activate_initial()
        successor = self.service.create_successor_draft(actor="operator")
        self.assertEqual(successor.status, ManagedConfigurationStatus.DRAFT)
        self.assertEqual(successor.version, 1)
        self.assertEqual(successor.base_active_revision_id, active.revision_id)
        self.assertEqual(successor.digest, active.digest)
        self.assertNotEqual(successor.revision_id, active.revision_id)
        reloaded_active = self.service.active()
        self.assertEqual(reloaded_active.revision_id, active.revision_id)
        self.assertEqual(reloaded_active.status, ManagedConfigurationStatus.ACTIVE)

    def test_create_successor_draft_validates_expected_active_identity(self) -> None:
        active = self._activate_initial()
        with self.assertRaises(ConfigurationVersionConflict):
            self.service.create_successor_draft(
                actor="operator",
                expected_active_revision_id="wrong-id",
            )
        with self.assertRaises(ConfigurationVersionConflict):
            self.service.create_successor_draft(
                actor="operator",
                expected_active_version=999,
            )
        with self.assertRaises(ConfigurationVersionConflict):
            self.service.create_successor_draft(
                actor="operator",
                expected_active_digest="wrong-digest",
            )
        successor = self.service.create_successor_draft(
            actor="operator",
            expected_active_revision_id=active.revision_id,
            expected_active_version=active.revision_sequence,
            expected_active_digest=active.digest,
        )
        self.assertIsNotNone(successor)

    def test_active_remains_immutable_when_editing_successor(self) -> None:
        active = self._activate_initial()
        original_digest = active.digest
        successor = self.service.create_successor_draft(actor="operator")
        updated = self.objects.set_storage_enabled(
            successor.revision_id,
            object_id="source-storage",
            enabled=False,
            expected_version=successor.version,
            actor="operator",
        )
        self.assertEqual(updated.status, ManagedConfigurationStatus.DRAFT)
        reloaded_active = self.service.active()
        self.assertEqual(reloaded_active.digest, original_digest)
        self.assertEqual(reloaded_active.revision_id, active.revision_id)
        self.assertFalse(updated.document["storages"][0]["enabled"])
        self.assertTrue(reloaded_active.document["storages"][0].get("enabled", True))

    def test_api_successor_draft_journey(self) -> None:
        active = self._activate_initial()
        status, response = request(
            self.api,
            "/api/v1/configuration/drafts/successor",
            method="POST",
            body={},
            token="admin-token",
        )
        self.assertEqual(status, 201)
        self.assertTrue(response.get("created"))
        self.assertEqual(response["status"], "draft")
        self.assertIn("revisionId", response)
        successor_id = response["revisionId"]
        self.assertNotEqual(successor_id, active.revision_id)

    def test_api_successor_draft_from_revision_endpoint(self) -> None:
        active = self._activate_initial()
        status, response = request(
            self.api,
            f"/api/v1/configuration/revisions/{active.revision_id}/successor",
            method="POST",
            body={},
            token="admin-token",
        )
        self.assertEqual(status, 201)
        self.assertTrue(response.get("created"))
        self.assertEqual(response["status"], "draft")

    def test_api_successor_draft_from_revision_rejects_unknown_revision_id(self) -> None:
        active = self._activate_initial()
        before = tuple(revision.revision_id for revision in self.repository.list_revisions())
        status, response = request(
            self.api,
            "/api/v1/configuration/revisions/not-the-active-revision/successor",
            method="POST",
            body={},
            token="admin-token",
        )
        self.assertEqual(status, 409)
        self.assertEqual(response["error"]["code"], "configuration_version_conflict")
        self.assertIn("Active revision does not match", response["error"]["message"])
        details = response["error"]["details"]
        self.assertEqual(details["revisionId"], active.revision_id)
        self.assertEqual(details["durableState"], "active_preserved")
        self.assertEqual(details["sideEffects"], "none")
        self.assertTrue(details["retrySafe"])
        self.assertTrue(details["nextAction"])
        self.assertEqual(
            tuple(revision.revision_id for revision in self.repository.list_revisions()),
            before,
        )
        self.assertEqual(self.service.active().revision_id, active.revision_id)

    def test_api_successor_draft_from_revision_rejects_non_active_revision(self) -> None:
        active = self._activate_initial()
        draft = self.service.import_draft(self.document, actor="operator")
        self.assertEqual(draft.status, ManagedConfigurationStatus.DRAFT)
        self.assertNotEqual(draft.revision_id, active.revision_id)
        before = tuple(revision.revision_id for revision in self.repository.list_revisions())
        status, response = request(
            self.api,
            f"/api/v1/configuration/revisions/{draft.revision_id}/successor",
            method="POST",
            body={},
            token="admin-token",
        )
        self.assertEqual(status, 409)
        self.assertEqual(response["error"]["code"], "configuration_version_conflict")
        self.assertEqual(response["error"]["details"]["revisionId"], active.revision_id)
        self.assertEqual(
            tuple(revision.revision_id for revision in self.repository.list_revisions()),
            before,
        )

    def test_api_successor_draft_from_revision_rejects_superseded_revision(self) -> None:
        first = self._activate_initial()
        successor = self.service.create_successor_draft(actor="operator")
        validated = self.service.validate(successor.revision_id, actor="operator")
        second = self.service.activate(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        self.assertNotEqual(second.revision_id, first.revision_id)
        before = tuple(revision.revision_id for revision in self.repository.list_revisions())
        status, response = request(
            self.api,
            f"/api/v1/configuration/revisions/{first.revision_id}/successor",
            method="POST",
            body={},
            token="admin-token",
        )
        self.assertEqual(status, 409)
        self.assertEqual(response["error"]["code"], "configuration_version_conflict")
        self.assertEqual(response["error"]["details"]["revisionId"], second.revision_id)
        self.assertEqual(
            tuple(revision.revision_id for revision in self.repository.list_revisions()),
            before,
        )

    def test_api_successor_draft_requires_manage_permission(self) -> None:
        self._activate_initial()
        status, _ = request(
            self.api,
            "/api/v1/configuration/drafts/successor",
            method="POST",
            body={},
            token="readonly-token",
        )
        self.assertEqual(status, 403)

    def test_api_successor_draft_rejects_stale_active_identity(self) -> None:
        active = self._activate_initial()
        status, response = request(
            self.api,
            "/api/v1/configuration/drafts/successor",
            method="POST",
            body={"expectedActiveRevisionId": "stale-revision-id"},
            token="admin-token",
        )
        self.assertEqual(status, 409)
        self.assertIn("Active revision does not match", response["error"]["message"])

    def test_api_import_draft_accepts_source_active(self) -> None:
        self._activate_initial()
        status, response = request(
            self.api,
            "/api/v1/configuration/drafts",
            method="POST",
            body={"source": "active"},
            token="admin-token",
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["status"], "draft")

    def test_api_copy_and_toggle_object_lifecycle_for_all_kinds(self) -> None:
        self._activate_initial()
        draft = self.service.create_successor_draft(actor="operator")
        kinds_with_enabled = [
            ("storages", "source-storage"),
            ("resourceLibraries", "source"),
            ("mediaLibraries", "movies"),
            ("recognitionTypes", "A"),
            ("recognitionRules", "movie-library"),
            ("recognitionTypePolicies", "type-A"),
            ("metadataPolicies", "A"),
            ("namingPolicies", "A"),
            ("classificationPolicies", "A"),
            ("automationTaskDefinitions", "scan-task"),
        ]
        current_version = draft.version
        current_rev_id = draft.revision_id
        for section, object_id in kinds_with_enabled:
            with self.subTest(section=section, action="disable"):
                status, response = request(
                    self.api,
                    f"/api/v1/configuration/revisions/{current_rev_id}/objects/{section}/{object_id}/disable",
                    method="POST",
                    body={"expectedVersion": current_version},
                    token="admin-token",
                )
                self.assertEqual(status, 200)
                current_version = response["version"]
            with self.subTest(section=section, action="enable"):
                status, response = request(
                    self.api,
                    f"/api/v1/configuration/revisions/{current_rev_id}/objects/{section}/{object_id}/enable",
                    method="POST",
                    body={"expectedVersion": current_version},
                    token="admin-token",
                )
                self.assertEqual(status, 200)
                current_version = response["version"]
            with self.subTest(section=section, action="copy"):
                status, response = request(
                    self.api,
                    f"/api/v1/configuration/revisions/{current_rev_id}/objects/{section}/{object_id}/copy",
                    method="POST",
                    body={"expectedVersion": current_version},
                    token="admin-token",
                )
                self.assertEqual(status, 200)
                current_version = response["version"]

        # OrganizePolicy supports copy but not enable/disable
        with self.subTest(section="organizePolicies", action="copy"):
            status, response = request(
                self.api,
                f"/api/v1/configuration/revisions/{current_rev_id}/objects/organizePolicies/A/copy",
                method="POST",
                body={"expectedVersion": current_version},
                token="admin-token",
            )
            self.assertEqual(status, 200)
            current_version = response["version"]

        with self.subTest(section="organizePolicies", action="disable_fails"):
            status, response = request(
                self.api,
                f"/api/v1/configuration/revisions/{current_rev_id}/objects/organizePolicies/A/disable",
                method="POST",
                body={"expectedVersion": current_version},
                token="admin-token",
            )
            self.assertEqual(status, 400)

    def test_referenced_object_deletion_is_blocked_and_unreferenced_succeeds(self) -> None:
        self._activate_initial()
        draft = self.service.create_successor_draft(actor="operator")
        # Deleting storage referenced by resourceLibrary must fail
        status, response = request(
            self.api,
            f"/api/v1/configuration/revisions/{draft.revision_id}/objects/storages/source-storage",
            method="DELETE",
            body={"expectedVersion": draft.version},
            token="admin-token",
        )
        self.assertEqual(status, 409)
        self.assertEqual(response["error"]["code"], "configuration_object_referenced")

        # Copying a storage creates an unreferenced copy, which can be deleted
        status, copied = request(
            self.api,
            f"/api/v1/configuration/revisions/{draft.revision_id}/objects/storages/source-storage/copy",
            method="POST",
            body={"expectedVersion": draft.version, "newId": "temp-storage"},
            token="admin-token",
        )
        self.assertEqual(status, 200)
        status, deleted = request(
            self.api,
            f"/api/v1/configuration/revisions/{draft.revision_id}/objects/storages/temp-storage",
            method="DELETE",
            body={"expectedVersion": copied["version"]},
            token="admin-token",
        )
        self.assertEqual(status, 200)


class SuccessorDraftWebUITests(unittest.TestCase):
    def test_successor_draft_button_in_render_configuration(self) -> None:
        with open("mediaflow/interfaces/operator_ui.py", encoding="utf-8") as f:
            script = f.read()
        # renderConfiguration must contain successor-draft action
        self.assertIn("Create successor Draft from Active", script)

    def test_advanced_json_labels_in_operator_ui(self) -> None:
        with open("mediaflow/interfaces/operator_ui.py", encoding="utf-8") as f:
            script = f.read()
        # Revision detail must label whole-document JSON editor as Advanced
        self.assertIn("Advanced: Edit Draft JSON", script)
        # Import/export section must be labelled Advanced
        self.assertIn("Advanced JSON (import/export)", script)

    def test_typed_forms_exist_for_all_object_families(self) -> None:
        with open("mediaflow/interfaces/operator_ui.py", encoding="utf-8") as f:
            script = f.read()
        # guidedObjectFields must be referenced for every kind
        for kind in (
            "storages", "resourceLibraries", "mediaLibraries",
            "recognitionTypes", "recognitionRules", "recognitionTypePolicies",
            "metadataPolicies", "namingPolicies", "classificationPolicies",
            "organizePolicies", "automationTaskDefinitions",
        ):
            with self.subTest(kind=kind):
                self.assertIn(f"guidedObjectFields(kind, item", script)

    def test_render_guided_object_list_has_copy_enable_disable_for_all_applicable_kinds(self) -> None:
        with open("mediaflow/interfaces/operator_ui.py", encoding="utf-8") as f:
            script = f.read()
        # Copy endpoint must be reachable for every kind (organizePolicies has copy too)
        self.assertIn("/objects/${kind}/${encodeURIComponent(item.id)}/copy", script)
        # Enable/disable endpoint must be reachable for kinds that have enabled field
        self.assertIn("/objects/${kind}/${encodeURIComponent(item.id)}/${action}", script)


if __name__ == "__main__":
    unittest.main()
