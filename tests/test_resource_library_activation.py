from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
    ConfigurationVersionConflict,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageCapabilities, StorageEntry, StorageEntryType
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request


class ReadOnlyStorage:
    """A provider-neutral fake that proves Save only performs reads."""

    def __init__(self, storage_id: str) -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = True
        self.fail = False
        self.mutations: list[str] = []
        self.capabilities = StorageCapabilities()

    def stat(self, path: str) -> StorageEntry:
        if self.fail:
            raise PermissionError(f"{self.storage_id} read denied")
        return StorageEntry(path, path, StorageEntryType.DIRECTORY, 0, datetime.now(UTC))

    def list(self, path: str):
        if self.fail:
            raise PermissionError(f"{self.storage_id} read denied")
        return ()

    def exists(self, path: str) -> bool:
        if self.fail:
            raise PermissionError(f"{self.storage_id} read denied")
        return True

    def write(self, *args, **kwargs):
        self.mutations.append("write")
        raise AssertionError("ResourceLibrary Save must not write Storage")

    def create_directory(self, *args, **kwargs):
        self.mutations.append("create_directory")
        raise AssertionError("ResourceLibrary Save must not create Storage directories")

    def move(self, *args, **kwargs):
        self.mutations.append("move")
        raise AssertionError("ResourceLibrary Save must not move Storage files")

    def copy(self, *args, **kwargs):
        self.mutations.append("copy")
        raise AssertionError("ResourceLibrary Save must not copy Storage files")

    def delete(self, *args, **kwargs):
        self.mutations.append("delete")
        raise AssertionError("ResourceLibrary Save must not delete Storage files")

    def hard_link(self, *args, **kwargs):
        self.mutations.append("hard_link")
        raise AssertionError("ResourceLibrary Save must not hard-link Storage files")

    def soft_link(self, *args, **kwargs):
        self.mutations.append("soft_link")
        raise AssertionError("ResourceLibrary Save must not soft-link Storage files")


class ResourceLibraryActivationTests(unittest.TestCase):
    def _document(self, root: Path) -> dict[str, object]:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        document["resourceLibraries"][0]["storagePath"] = "incoming"
        document["mediaLibraries"][0]["rootPath"] = "Movies"
        return document

    @staticmethod
    def _evidence_gates(
        objects: ConfigurationObjectService,
        revision,
        *,
        include_strategy: bool = True,
    ) -> None:
        for storage_id in ("source-storage", "media-target"):
            evidence = objects.storage_check(
                revision.revision_id,
                storage_id=storage_id,
                expected_version=revision.version,
                expected_digest=revision.digest,
                actor="operator",
            )
            if evidence.status is not ConfigurationStorageCheckStatus.PASSED:
                raise AssertionError(f"initial Storage check failed: {storage_id}")
        if include_strategy:
            strategy = objects.recognition_strategy_test(
                revision.revision_id,
                expected_version=revision.version,
                expected_digest=revision.digest,
                actor="operator",
                resource_library_id="source",
                synthetic_path="Example.Movie.2024.1080p.mkv",
            )
            if strategy.status is not ConfigurationStrategyTestStatus.COMPLETED:
                raise AssertionError("initial strategy test failed")
        destination = objects.destination_precheck(
            revision.revision_id,
            expected_version=revision.version,
            expected_digest=revision.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        if destination.status is not ConfigurationDestinationPrecheckStatus.COMPLETED:
            raise AssertionError("initial destination precheck failed")

    def _active_api(
        self,
        root: Path,
        *,
        storage_adapters=None,
        resource_enabled: bool = True,
        include_disabled_storage: bool = False,
    ):
        document = self._document(root)
        document["resourceLibraries"][0]["enabled"] = resource_enabled
        if include_disabled_storage:
            document["storages"].append(
                {
                    "id": "disabled-storage",
                    "name": "Disabled Storage",
                    "type": "local",
                    "rootPath": str(root / "disabled"),
                    "readOnly": False,
                    "enabled": False,
                    "options": {},
                }
            )
        (root / "source" / "incoming").mkdir(parents=True)
        (root / "target" / "Movies").mkdir(parents=True)
        configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(root / "configuration.sqlite3"),
        )
        objects = ConfigurationObjectService(
            service,
            storage_adapters=storage_adapters,
            storage_browser_cursor_secret="resource-library-test-secret",
        )
        draft = service.import_draft(document, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        self._evidence_gates(objects, validated, include_strategy=resource_enabled)
        active = objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        runtime_repository = SQLiteTaskRepository(root / "runtime.sqlite3")
        self.addCleanup(runtime_repository.close)
        principal = ResolvedApiPrincipal(
            "admin",
            "admin-token",
            frozenset(ApiPermission),
        )
        api = MediaFlowApi(
            runtime_repository,
            None,
            principals=(principal,),
            configuration_service=service,
            bootstrap_document=document,
            storage_adapters=storage_adapters,
            storage_browser_cursor_secret="resource-library-test-secret",
        )
        return configuration_repository, service, objects, active, runtime_repository, api

    @staticmethod
    def _save_body(**overrides):
        body = {
            "resourceLibraryId": "new-library",
            "name": "New Library",
            "enabled": True,
            "storageId": "source-storage",
            "storagePath": "incoming/new",
        }
        body.update(overrides)
        return body

    def test_edit_preserves_unexposed_fields_and_stale_writer_cannot_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, _active, _runtime, api = self._active_api(root)
            before = service.active().document["resourceLibraries"][0]
            status, projection = request(api, "/api/v1/resource-libraries/source/edit")
            self.assertEqual(status, 200, projection)
            expected = projection["active"]
            self.assertEqual(
                [item["id"] for item in projection["storages"]],
                ["source-storage", "media-target"],
            )
            body = {
                "resourceLibraryId": "source",
                "name": "Edited Source",
                "enabled": True,
                "storageId": "source-storage",
                "storagePath": "incoming",
                "expectedRevisionId": expected["revisionId"],
                "expectedVersion": expected["version"],
                "expectedDigest": expected["digest"],
            }
            status, edited = request(
                api, "/api/v1/resource-libraries/source", method="PUT", body=body
            )
            self.assertEqual(status, 200, edited)
            after = service.active().document["resourceLibraries"][0]
            self.assertEqual(after["name"], "Edited Source")
            self.assertEqual(after.get("extensions"), before.get("extensions"))
            stale_status, stale = request(
                api,
                "/api/v1/resource-libraries/source",
                method="PUT",
                body={**body, "name": "Stale overwrite"},
            )
            self.assertEqual(stale_status, 409, stale)
            self.assertEqual(stale["error"]["code"], "configuration_version_conflict")
            self.assertEqual(
                service.active().document["resourceLibraries"][0]["name"], "Edited Source"
            )

    def test_edit_projection_uses_revision_sequence_after_multiple_activations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, _active, _runtime, api = self._active_api(root)
            for library_id in ("second", "third"):
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(resourceLibraryId=library_id),
                )
                self.assertEqual(status, 200, response)
            active = service.active()
            self.assertNotEqual(active.version, active.revision_sequence)
            status, projection = request(api, "/api/v1/resource-libraries/source/edit")
            self.assertEqual(status, 200, projection)
            self.assertEqual(projection["active"]["revisionSequence"], active.revision_sequence)
            self.assertTrue(all(item["enabled"] for item in projection["storages"]))
            status, edited = request(
                api,
                "/api/v1/resource-libraries/source",
                method="PUT",
                body={
                    "resourceLibraryId": "source",
                    "name": "Sequence-safe Source",
                    "enabled": True,
                    "storageId": "source-storage",
                    "storagePath": "incoming",
                    "expectedRevisionId": projection["active"]["revisionId"],
                    "expectedVersion": projection["active"]["revisionSequence"],
                    "expectedDigest": projection["active"]["digest"],
                },
            )
            self.assertEqual(status, 200, edited)
            self.assertEqual(edited["resourceLibrary"]["name"], "Sequence-safe Source")

    def test_success_publishes_one_new_active_runtime_without_storage_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ReadOnlyStorage("source-storage")
            target = ReadOnlyStorage("media-target")
            values = self._active_api(
                root,
                storage_adapters={"source-storage": source, "media-target": target},
            )
            configuration_repository, service, _objects, active, _runtime_repository, api = values
            status, response = request(
                api,
                "/api/v1/resource-libraries",
                method="POST",
                body=self._save_body(),
            )
            self.assertEqual(status, 200)
            self.assertEqual(response["resourceLibrary"]["id"], "new-library")
            self.assertEqual(response["active"]["status"], "active")
            self.assertNotEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(
                service.active().document["resourceLibraries"][-1]["id"],
                "new-library",
            )
            browse_status, browse = request(
                api,
                "/api/v1/resource-libraries/new-library/files",
                token="admin-token",
            )
            self.assertEqual(browse_status, 200)
            self.assertEqual(browse["resourceLibrary"]["id"], "new-library")
            self.assertEqual(source.mutations, [])
            self.assertEqual(target.mutations, [])
            audits = configuration_repository.list_revision_audits(service.active().revision_id)
            self.assertTrue(
                any(
                    audit.safe_after().get("objectChange", {}).get("action")
                    == "files_resource_library_save"
                    for audit in audits
                )
            )

    def test_invalid_duplicate_and_unavailable_storage_keep_old_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = self._active_api(root)
            _repository, service, _objects, active, _runtime_repository, api = values
            for body, expected_code in (
                ({**self._save_body(), "unexpected": True}, "invalid_request"),
                ({**self._save_body(), "storagePath": "../escape"}, "invalid_request"),
                ({**self._save_body(), "name": None}, "invalid_request"),
                ({**self._save_body(), "enabled": "true"}, "invalid_request"),
                ({**self._save_body(), "name": "x" * 121}, "invalid_request"),
                ({**self._save_body(), "storageId": "x" * 65}, "invalid_request"),
                ({**self._save_body(), "storagePath": "x" * 4097}, "invalid_request"),
                (
                    {**self._save_body(), "resourceLibraryId": "source"},
                    "resource_library_duplicate",
                ),
                (
                    {**self._save_body(), "storageId": "missing-storage"},
                    "resource_library_storage_unavailable",
                ),
            ):
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=body,
                )
                self.assertIn(status, {400, 409})
                self.assertEqual(response["error"]["code"], expected_code)
                self.assertEqual(service.active().revision_id, active.revision_id)

    def test_missing_active_reports_no_active_without_claiming_old_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
            self.addCleanup(configuration_repository.close)
            document = self._document(root)
            service = ManagedConfigurationService(
                configuration_repository,
                bootstrap_database_path=str(root / "configuration.sqlite3"),
            )
            runtime_repository = SQLiteTaskRepository(root / "runtime.sqlite3")
            self.addCleanup(runtime_repository.close)
            principal = ResolvedApiPrincipal(
                "admin",
                "admin-token",
                frozenset(ApiPermission),
            )
            api = MediaFlowApi(
                runtime_repository,
                None,
                principals=(principal,),
                configuration_service=service,
                bootstrap_document=document,
                management_only=True,
            )

            status, response = request(
                api,
                "/api/v1/resource-libraries",
                method="POST",
                body=self._save_body(),
            )

            self.assertEqual(status, 503)
            self.assertEqual(response["error"]["code"], "configuration_unavailable")
            details = response["error"]["details"]
            self.assertEqual(details["reason"], "active_missing")
            self.assertEqual(details["durableState"], "no_active_configuration")
            self.assertEqual(details["candidateState"], "not_saved")
            self.assertEqual(details["sideEffects"], "none")
            self.assertIsNone(service.active())
            self.assertEqual(configuration_repository.list_revisions(), ())

    def test_corrupt_active_reports_unavailable_without_claiming_old_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = self._active_api(root)
            repository, service, _objects, active, _runtime_repository, api = values
            corrupt_document = dict(active.document)
            corrupt_document["resourceLibraries"] = list(corrupt_document["resourceLibraries"]) + [
                {"id": "corrupt-candidate"}
            ]
            with repository._connection:
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                    (json.dumps(corrupt_document), active.revision_id),
                )

            status, response = request(
                api,
                "/api/v1/resource-libraries",
                method="POST",
                body=self._save_body(),
            )

            self.assertEqual(status, 503)
            self.assertEqual(response["error"]["code"], "configuration_unavailable")
            details = response["error"]["details"]
            self.assertEqual(details["reason"], "digest_corrupt")
            self.assertEqual(details["durableState"], "managed_active_unavailable")
            self.assertEqual(details["candidateState"], "not_saved")
            self.assertEqual(
                [item["id"] for item in service.active().document["resourceLibraries"]],
                ["source", "corrupt-candidate"],
            )

    def test_unreadable_active_reports_unavailable_without_saving_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = self._active_api(root)
            repository, service, _objects, active, _runtime_repository, api = values
            with repository._connection:
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                    ("{not-json", active.revision_id),
                )

            status, response = request(
                api,
                "/api/v1/resource-libraries",
                method="POST",
                body=self._save_body(),
            )

            self.assertEqual(status, 503)
            self.assertEqual(response["error"]["code"], "configuration_unavailable")
            details = response["error"]["details"]
            self.assertEqual(details["reason"], "active_unreadable")
            self.assertEqual(details["durableState"], "managed_active_unavailable")
            self.assertEqual(details["candidateState"], "not_saved")
            with self.assertRaises(RuntimeSnapshotUnavailable):
                service.active()

    def test_disabled_storage_is_rejected_before_read_only_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = self._active_api(root, include_disabled_storage=True)
            _repository, service, _objects, active, _runtime_repository, api = values

            status, response = request(
                api,
                "/api/v1/resource-libraries",
                method="POST",
                body=self._save_body(storageId="disabled-storage"),
            )

            self.assertEqual(status, 409)
            self.assertEqual(response["error"]["code"], "resource_library_storage_unavailable")
            self.assertEqual(response["error"]["details"]["durableState"], "active_preserved")
            self.assertEqual(service.active().revision_id, active.revision_id)

    def test_failed_read_only_check_and_runtime_binding_preserve_old_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ReadOnlyStorage("source-storage")
            target = ReadOnlyStorage("media-target")
            values = self._active_api(
                root,
                storage_adapters={"source-storage": source, "media-target": target},
            )
            _repository, service, _objects, active, _runtime_repository, api = values
            source.fail = True
            status, response = request(
                api,
                "/api/v1/resource-libraries",
                method="POST",
                body=self._save_body(),
            )
            self.assertEqual(status, 409)
            self.assertEqual(response["error"]["code"], "resource_library_storage_check_failed")
            self.assertEqual(service.active().revision_id, active.revision_id)
            self.assertIn("active_preserved", response["error"]["details"]["durableState"])
            self.assertEqual(source.mutations, [])
            source.fail = False
            with patch.object(
                api,
                "_build_runtime_binding",
                side_effect=RuntimeError("simulated runtime publication failure"),
            ):
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(resourceLibraryId="runtime-failure"),
                )
            self.assertEqual(status, 503)
            self.assertEqual(response["error"]["code"], "resource_library_runtime_failed")
            self.assertEqual(service.active().revision_id, active.revision_id)

    def test_disabled_resource_library_is_saved_but_not_browseable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = self._active_api(root, resource_enabled=False)
            _repository, service, _objects, active, _runtime_repository, api = values
            status, response = request(
                api,
                "/api/v1/resource-libraries",
                method="POST",
                body=self._save_body(enabled=False),
            )
            self.assertEqual(status, 200)
            self.assertFalse(response["resourceLibrary"]["enabled"])
            self.assertNotEqual(service.active().revision_id, active.revision_id)
            saved = next(
                item
                for item in service.active().document["resourceLibraries"]
                if item["id"] == "new-library"
            )
            self.assertFalse(saved["enabled"])
            browse_status, browse = request(
                api,
                "/api/v1/resource-libraries/new-library/files",
                token="admin-token",
            )
            self.assertIn(browse_status, {403, 404, 409})
            self.assertNotEqual(browse.get("resourceLibrary", {}).get("id"), "new-library")

    def test_concurrent_active_replacement_wins_without_candidate_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = self._active_api(root)
            _repository, service, objects, active, _runtime_repository, api = values

            def competing_winner(_revision) -> object:
                competitor = service.create_successor_draft(actor="competitor")
                validated = service.validate(competitor.revision_id, actor="competitor")
                self._evidence_gates(objects, validated)
                winner = objects.activate_checked(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="competitor",
                )
                return winner

            with patch.object(
                api,
                "_prepare_runtime_binding_for_revision",
                side_effect=competing_winner,
            ):
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(resourceLibraryId="race-library"),
                )
            self.assertEqual(status, 409)
            self.assertEqual(response["error"]["code"], "configuration_conflict")
            self.assertEqual(
                response["error"]["details"]["durableState"], "active_winner_preserved"
            )
            self.assertEqual(response["error"]["details"]["candidateState"], "not_published")
            winner = service.active()
            self.assertNotEqual(winner.revision_id, active.revision_id)
            self.assertEqual(api._runtime_binding.snapshot_id, winner.revision_id)
            self.assertNotIn(
                "race-library",
                [item["id"] for item in winner.document["resourceLibraries"]],
            )

    def test_successor_create_conflict_refreshes_the_winning_runtime_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = self._active_api(root)
            _repository, service, objects, active, _runtime_repository, api = values
            winner_holder = []

            def competing_version_conflict(*_args, **_kwargs) -> object:
                competitor = service.create_successor_draft(actor="competitor")
                validated = service.validate(competitor.revision_id, actor="competitor")
                self._evidence_gates(objects, validated)
                winner = objects.activate_checked(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="competitor",
                )
                winner_holder.append(winner)
                raise ConfigurationVersionConflict(
                    "Active changed while creating the successor Draft",
                    revision_id=active.revision_id,
                    current_version=winner.version,
                    current_digest=winner.digest,
                    durable_state="active_winner_preserved",
                )

            with patch.object(
                api._configuration_objects,
                "save_resource_library",
                side_effect=competing_version_conflict,
            ):
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(resourceLibraryId="version-race-library"),
                )
            self.assertEqual(status, 409)
            self.assertEqual(response["error"]["code"], "configuration_version_conflict")
            self.assertEqual(
                response["error"]["details"]["durableState"], "active_winner_preserved"
            )
            self.assertEqual(response["error"]["details"]["candidateState"], "not_published")
            self.assertEqual(service.active().revision_id, winner_holder[0].revision_id)
            self.assertNotEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(api._runtime_binding.snapshot_id, winner_holder[0].revision_id)
            self.assertNotIn(
                "version-race-library",
                [item["id"] for item in service.active().document["resourceLibraries"]],
            )

    def test_missing_required_permission_is_rejected_before_candidate_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configuration_repository, service, _objects, active, runtime_repository, _api = (
                self._active_api(root)
            )
            for index, permissions in enumerate(
                (
                    frozenset({ApiPermission.READ, ApiPermission.MANAGE_CONFIGURATION}),
                    frozenset({ApiPermission.READ, ApiPermission.ACTIVATE_CONFIGURATION}),
                )
            ):
                principal = ResolvedApiPrincipal(
                    f"limited-{index}",
                    f"limited-token-{index}",
                    permissions,
                )
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=self._document(root),
                )
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(),
                    token=f"limited-token-{index}",
                )
                self.assertEqual(status, 403)
                self.assertEqual(response["error"]["code"], "forbidden")
                self.assertEqual(service.active().revision_id, active.revision_id)
                self.assertEqual(
                    len(service.active().document["resourceLibraries"]),
                    1,
                )

    def test_persistence_validation_and_activation_failures_keep_active_and_can_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ReadOnlyStorage("source-storage")
            target = ReadOnlyStorage("media-target")
            values = self._active_api(
                root,
                storage_adapters={"source-storage": source, "media-target": target},
            )
            repository, service, _objects, active, _runtime_repository, api = values

            with patch.object(
                repository,
                "create_revision_with_audit",
                side_effect=RuntimeError("simulated successor persistence failure"),
            ):
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(resourceLibraryId="create-failure"),
                )
            self.assertEqual(status, 503)
            self.assertEqual(response["error"]["code"], "resource_library_persistence_failed")
            self.assertEqual(response["error"]["details"]["durableState"], "active_preserved")
            self.assertEqual(service.active().revision_id, active.revision_id)

            with patch.object(
                service,
                "validate",
                side_effect=RuntimeError("simulated validation lifecycle failure"),
            ):
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(resourceLibraryId="validate-failure"),
                )
            self.assertEqual(status, 503)
            self.assertEqual(response["error"]["code"], "resource_library_persistence_failed")
            self.assertEqual(service.active().revision_id, active.revision_id)

            with patch.object(service, "validate", return_value=active):
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(resourceLibraryId="invalid-status"),
                )
            self.assertEqual(status, 422)
            self.assertEqual(response["error"]["code"], "resource_library_validation_failed")
            self.assertEqual(service.active().revision_id, active.revision_id)

            with patch.object(
                repository,
                "activate_revision",
                side_effect=RuntimeError("simulated activation persistence failure"),
            ):
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(resourceLibraryId="activation-failure"),
                )
            self.assertEqual(status, 503)
            self.assertEqual(response["error"]["code"], "resource_library_persistence_failed")
            self.assertEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(source.mutations, [])
            self.assertEqual(target.mutations, [])

    def test_real_check_failure_then_explicit_retry_succeeds_without_auto_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ReadOnlyStorage("source-storage")
            target = ReadOnlyStorage("media-target")
            values = self._active_api(
                root,
                storage_adapters={"source-storage": source, "media-target": target},
            )
            _repository, service, _objects, active, _runtime_repository, api = values
            source.fail = True
            status, response = request(
                api,
                "/api/v1/resource-libraries",
                method="POST",
                body=self._save_body(resourceLibraryId="retry-library"),
            )
            self.assertEqual(status, 409)
            self.assertEqual(response["error"]["code"], "resource_library_storage_check_failed")
            self.assertEqual(service.active().revision_id, active.revision_id)

            source.fail = False
            status, response = request(
                api,
                "/api/v1/resource-libraries",
                method="POST",
                body=self._save_body(resourceLibraryId="retry-library"),
            )
            self.assertEqual(status, 200)
            self.assertEqual(response["resourceLibrary"]["id"], "retry-library")
            self.assertNotEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(source.mutations, [])
            self.assertEqual(target.mutations, [])

    def test_save_creates_no_work_provider_requests_or_organizer_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ReadOnlyStorage("source-storage")
            target = ReadOnlyStorage("media-target")
            values = self._active_api(
                root,
                storage_adapters={"source-storage": source, "media-target": target},
            )
            _repository, service, objects, active, runtime_repository, api = values
            connection = runtime_repository._connection
            before_counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("tasks", "automation_jobs")
            }
            provider_factory = patch.object(
                objects,
                "_metadata_provider_registry_factory",
                side_effect=AssertionError("Save must not request Metadata"),
            )
            task_create = patch.object(
                runtime_repository,
                "create_task",
                side_effect=AssertionError("Save must not create a Task"),
            )
            job_create = patch.object(
                runtime_repository,
                "create_job",
                side_effect=AssertionError("Save must not create a Job"),
            )
            organizer_execute = patch(
                "mediaflow.application.organizer.OrganizerExecutor.execute",
                side_effect=AssertionError("Save must not invoke OrganizerExecutor"),
            )
            scanner = patch(
                "mediaflow.application.library_pipeline.ResourceLibraryScanner.scan_all",
                side_effect=AssertionError("Save must not invoke Scan"),
            )
            with provider_factory, task_create, job_create, organizer_execute, scanner:
                status, response = request(
                    api,
                    "/api/v1/resource-libraries",
                    method="POST",
                    body=self._save_body(resourceLibraryId="side-effect-free"),
                )

            self.assertEqual(status, 200)
            self.assertEqual(response["sideEffects"], "configuration_only")
            self.assertNotEqual(service.active().revision_id, active.revision_id)
            after_counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("tasks", "automation_jobs")
            }
            self.assertEqual(after_counts, before_counts)
            self.assertEqual(source.mutations, [])
            self.assertEqual(target.mutations, [])


if __name__ == "__main__":
    unittest.main()
