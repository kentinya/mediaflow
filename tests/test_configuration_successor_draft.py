"""Retired configuration-draft contract and its direct publication replacement.

The former Draft API, successor route and draft lifecycle no longer exist. These
regressions keep the negative boundary explicit and prove that the surviving
object commands publish one checked Active snapshot without leaving a Draft or
Validated revision behind.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request


class RetiredDraftAndDirectPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repository = SQLiteConfigurationRepository(self.root / "configuration.sqlite3")
        self.task_repository = SQLiteTaskRepository(self.root / "runtime.sqlite3")
        self.service = ManagedConfigurationService(self.repository)
        self.document = example_document()
        self.document["persistence"]["databasePath"] = str(self.root / "configuration.sqlite3")
        (self.root / "source" / "incoming").mkdir(parents=True)
        (self.root / "target" / "Movies").mkdir(parents=True)
        self.document["storages"][0]["rootPath"] = str(self.root / "source")
        self.document["storages"][1]["rootPath"] = str(self.root / "target")
        self.document["resourceLibraries"][0]["storagePath"] = "incoming"
        self.document["mediaLibraries"][0]["rootPath"] = "Movies"
        self.api = MediaFlowApi(
            self.task_repository,
            principals=(
                ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ResolvedApiPrincipal("readonly", "readonly-token", frozenset({ApiPermission.READ})),
            ),
            configuration_service=self.service,
            bootstrap_document=self.document,
        )
        status, self.active = request(
            self.api,
            "/api/configuration/publish",
            method="POST",
            body={"document": self.document},
        )
        self.assertEqual(status, 200, self.active)

    def tearDown(self) -> None:
        self.repository.close()
        self.task_repository.close()
        self.temp_dir.cleanup()

    def _no_unpublished_revision(self) -> None:
        self.assertFalse(
            any(
                revision.status.value in {"draft", "validated"}
                for revision in self.repository.list_revisions()
            )
        )

    def test_retired_draft_entries_are_unknown_and_leave_active_unchanged(self) -> None:
        before = self.service.active()
        entries = (
            ("/api/configuration/drafts", {}),
            ("/api/configuration/drafts/successor", {}),
            (f"/api/configuration/revisions/{before.revision_id}/successor", {}),
            (f"/api/configuration/revisions/{before.revision_id}/validate", {}),
            (f"/api/configuration/revisions/{before.revision_id}/activate", {}),
            ("/api/configuration/drafts/import", {"document": self.document}),
        )
        for path, body in entries:
            status, response = request(
                self.api, path, method="POST", body=body, token="admin-token"
            )
            self.assertEqual(status, 404, (path, response))
            self.assertEqual(response["error"]["code"], "not_found")
        self.assertEqual(self.service.active().revision_id, before.revision_id)
        self._no_unpublished_revision()

    def test_direct_object_commands_publish_one_checked_active_snapshot(self) -> None:
        active = self.service.active()
        status, created = request(
            self.api,
            f"/api/configuration/revisions/{active.revision_id}/objects/storages",
            method="POST",
            body={
                "expectedVersion": active.version,
                "object": {
                    "id": "extra",
                    "name": "Extra",
                    "type": "local",
                    "rootPath": str(self.root / "target"),
                    "readOnly": True,
                },
            },
            token="admin-token",
        )
        self.assertEqual(status, 200, created)
        self.assertEqual(created["status"], "active")
        self.assertNotEqual(created["revisionId"], active.revision_id)
        self.assertEqual(self.service.active().revision_id, created["revisionId"])
        self.assertEqual(self.service.require(active.revision_id).status.value, "superseded")
        self._no_unpublished_revision()

        status, disabled = request(
            self.api,
            f"/api/configuration/revisions/{created['revisionId']}/objects/storages/extra/disable",
            method="POST",
            body={"expectedVersion": created["version"]},
            token="admin-token",
        )
        self.assertEqual(status, 200, disabled)
        self.assertFalse(disabled["storage"]["enabled"])
        self._no_unpublished_revision()

    def test_stale_version_is_refused_without_publication(self) -> None:
        active = self.service.active()
        status, response = request(
            self.api,
            f"/api/configuration/revisions/{active.revision_id}/objects/storages",
            method="POST",
            body={
                "expectedVersion": active.version - 1,
                "object": {
                    "id": "stale",
                    "name": "Stale",
                    "type": "local",
                    "rootPath": str(self.root / "target"),
                    "readOnly": True,
                },
            },
            token="admin-token",
        )
        self.assertEqual(status, 409)
        self.assertEqual(response["error"]["code"], "configuration_version_conflict")
        self.assertEqual(self.service.active().revision_id, active.revision_id)
        self._no_unpublished_revision()

    def test_read_only_principal_cannot_publish_objects(self) -> None:
        active = self.service.active()
        status, response = request(
            self.api,
            f"/api/configuration/revisions/{active.revision_id}/objects/storages",
            method="POST",
            body={
                "expectedVersion": active.version,
                "object": {
                    "id": "denied",
                    "name": "Denied",
                    "type": "local",
                    "rootPath": str(self.root / "target"),
                    "readOnly": True,
                },
            },
            token="readonly-token",
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.service.active().revision_id, active.revision_id)
        self._no_unpublished_revision()


if __name__ == "__main__":
    unittest.main()
