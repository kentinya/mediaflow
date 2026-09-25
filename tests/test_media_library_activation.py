from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageCapabilities, StorageEntry, StorageEntryType
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request


def _media_removal_confirmation(preview: dict) -> dict[str, object]:
    """The exact previewed Active revision identity bound to one confirmation."""

    active = preview["active"]
    return {
        "expectedRevisionId": active["revisionId"],
        "expectedVersion": active["version"],
        "expectedDigest": active["digest"],
        "expectedLibraryId": preview["mediaLibrary"]["id"],
    }


class ReadOnlyStorage:
    """A provider-neutral fake that proves the journey only performs reads."""

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
        raise AssertionError("MediaLibrary journey must not write Storage")

    def create_directory(self, *args, **kwargs):
        self.mutations.append("create_directory")
        raise AssertionError("MediaLibrary journey must not create Storage directories")

    def move(self, *args, **kwargs):
        self.mutations.append("move")
        raise AssertionError("MediaLibrary journey must not move Storage files")

    def copy(self, *args, **kwargs):
        self.mutations.append("copy")
        raise AssertionError("MediaLibrary journey must not copy Storage files")

    def delete(self, *args, **kwargs):
        self.mutations.append("delete")
        raise AssertionError("MediaLibrary journey must not delete Storage files")

    def hard_link(self, *args, **kwargs):
        self.mutations.append("hard_link")
        raise AssertionError("MediaLibrary journey must not hard-link Storage files")

    def soft_link(self, *args, **kwargs):
        self.mutations.append("soft_link")
        raise AssertionError("MediaLibrary journey must not soft-link Storage files")


# @@BODY@@


class MediaLibraryActivationTests(unittest.TestCase):
    def _document(self, root: Path) -> dict[str, object]:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        document["resourceLibraries"][0]["storagePath"] = "incoming"
        document["mediaLibraries"][0]["rootPath"] = "Movies"
        return document

    @staticmethod
    def _tree_bytes(base: Path) -> dict[str, bytes]:
        snapshot: dict[str, bytes] = {}
        for path in sorted(base.rglob("*")):
            relative = str(path.relative_to(base))
            snapshot[relative] = path.read_bytes() if path.is_file() else b"<dir>"
        return snapshot

    @staticmethod
    def _save_body(**overrides):
        body = {
            "mediaLibraryId": "archive",
            "name": "Archive Library",
            "enabled": True,
            "storageId": "media-target",
            "rootPath": "Archive",
        }
        body.update(overrides)
        return body

    # @@GATES@@

    @staticmethod
    def _evidence_gates(
        objects: ConfigurationObjectService,
        revision,
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

    # @@ACTIVE@@

    def _active_api(
        self,
        root: Path,
        *,
        storage_adapters=None,
        include_disabled_storage: bool = False,
    ):
        document = self._document(root)
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
            storage_browser_cursor_secret="media-library-test-secret",
        )
        draft = service.import_draft(document, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        self._evidence_gates(objects, validated)
        active = objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        # @@ACTIVE2@@
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
            storage_browser_cursor_secret="media-library-test-secret",
        )
        return configuration_repository, service, objects, active, runtime_repository, api

    def _save_media_library(self, api, media_library_id: str, *, enabled: bool = True):
        status, body = request(
            api,
            "/api/v1/media-libraries",
            method="POST",
            body=self._save_body(mediaLibraryId=media_library_id, enabled=enabled),
        )
        self.assertEqual(status, 200, body)
        return body

    # @@SAVE_TESTS@@

    def test_edit_projection_updates_by_immutable_id_and_rejects_stale_writer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, _active, _runtime, api = self._active_api(root)
            status, projection = request(api, "/api/v1/media-libraries/movies/edit")
            self.assertEqual(status, 200, projection)
            expected = projection["active"]
            self.assertEqual(
                [item["id"] for item in projection["storages"]],
                ["source-storage", "media-target"],
            )
            body = {
                "mediaLibraryId": "movies",
                "name": "Edited Movies",
                "enabled": True,
                "storageId": "media-target",
                "rootPath": "Movies",
                "expectedRevisionId": expected["revisionId"],
                "expectedVersion": expected["version"],
                "expectedDigest": expected["digest"],
            }
            status, edited = request(api, "/api/v1/media-libraries/movies", method="PUT", body=body)
            self.assertEqual(status, 200, edited)
            self.assertEqual(edited["mediaLibrary"]["name"], "Edited Movies")
            self.assertEqual(service.active().document["mediaLibraries"][0]["id"], "movies")
            stale_status, stale = request(
                api,
                "/api/v1/media-libraries/movies",
                method="PUT",
                body={**body, "name": "Stale overwrite"},
            )
            self.assertEqual(stale_status, 409, stale)
            self.assertEqual(stale["error"]["code"], "configuration_version_conflict")
            self.assertEqual(
                service.active().document["mediaLibraries"][0]["name"], "Edited Movies"
            )

    def test_edit_projection_uses_revision_sequence_after_multiple_activations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, _active, _runtime, api = self._active_api(root)
            for library_id in ("archive", "vault"):
                self._save_media_library(api, library_id)
            active = service.active()
            self.assertNotEqual(active.version, active.revision_sequence)
            status, projection = request(api, "/api/v1/media-libraries/movies/edit")
            self.assertEqual(status, 200, projection)
            self.assertEqual(projection["active"]["revisionSequence"], active.revision_sequence)
            self.assertTrue(all(item["enabled"] for item in projection["storages"]))
            status, edited = request(
                api,
                "/api/v1/media-libraries/movies",
                method="PUT",
                body={
                    "mediaLibraryId": "movies",
                    "name": "Sequence-safe Movies",
                    "enabled": True,
                    "storageId": "media-target",
                    "rootPath": "Movies",
                    "expectedRevisionId": projection["active"]["revisionId"],
                    "expectedVersion": projection["active"]["revisionSequence"],
                    "expectedDigest": projection["active"]["digest"],
                },
            )
            self.assertEqual(status, 200, edited)
            self.assertEqual(edited["mediaLibrary"]["name"], "Sequence-safe Movies")

    def test_success_publishes_one_new_active_without_storage_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ReadOnlyStorage("source-storage")
            target = ReadOnlyStorage("media-target")
            values = self._active_api(
                root,
                storage_adapters={"source-storage": source, "media-target": target},
            )
            configuration_repository, service, _objects, active, _runtime, api = values
            status, response = request(
                api,
                "/api/v1/media-libraries",
                method="POST",
                body=self._save_body(),
            )
            self.assertEqual(status, 200, response)
            self.assertEqual(response["mediaLibrary"]["id"], "archive")
            self.assertEqual(response["mediaLibrary"]["storageId"], "media-target")
            self.assertEqual(response["active"]["status"], "active")
            self.assertEqual(response["sideEffects"], "configuration_only")
            # The durable configuration block names the exact published Active so
            # the frontend can fail a split-identity document closed.
            self.assertEqual(response["configuration"]["authority"], "MANAGED")
            self.assertEqual(
                response["configuration"]["revisionId"], response["active"]["revisionId"]
            )
            self.assertEqual(response["configuration"]["version"], response["active"]["version"])
            self.assertEqual(response["configuration"]["digest"], response["active"]["digest"])
            self.assertNotEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(
                service.active().document["mediaLibraries"][-1]["id"],
                "archive",
            )
            browse_status, browse = request(
                api,
                "/api/v1/media-libraries/archive/files",
                token="admin-token",
            )
            self.assertEqual(browse_status, 200, browse)
            self.assertEqual(browse["mediaLibrary"]["id"], "archive")
            self.assertEqual(source.mutations, [])
            self.assertEqual(target.mutations, [])
            audits = configuration_repository.list_revision_audits(service.active().revision_id)
            self.assertTrue(
                any(
                    audit.safe_after().get("objectChange", {}).get("action") == "media_library_save"
                    for audit in audits
                )
            )

    # @@SAVE_TESTS2@@

    def test_invalid_duplicate_and_unavailable_storage_keep_old_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, active, _runtime, api = self._active_api(root)
            for body, expected_code in (
                ({**self._save_body(), "unexpected": True}, "invalid_request"),
                ({**self._save_body(), "name": None}, "invalid_request"),
                ({**self._save_body(), "enabled": "true"}, "invalid_request"),
                ({**self._save_body(), "name": "x" * 121}, "invalid_request"),
                ({**self._save_body(), "storageId": "x" * 65}, "invalid_request"),
                ({**self._save_body(), "storageId": "bad/slash"}, "invalid_request"),
                ({**self._save_body(), "rootPath": "x" * 4097}, "invalid_request"),
                (
                    {**self._save_body(), "mediaLibraryId": "movies"},
                    "media_library_duplicate",
                ),
                (
                    {**self._save_body(), "storageId": "missing-storage"},
                    "media_library_storage_unavailable",
                ),
            ):
                status, response = request(
                    api,
                    "/api/v1/media-libraries",
                    method="POST",
                    body=body,
                )
                self.assertIn(status, {400, 409}, response)
                self.assertEqual(response["error"]["code"], expected_code)
                self.assertEqual(service.active().revision_id, active.revision_id)

    def test_missing_active_reports_no_active(self) -> None:
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
            principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
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
                "/api/v1/media-libraries",
                method="POST",
                body=self._save_body(),
            )
            self.assertEqual(status, 503, response)
            self.assertEqual(response["error"]["code"], "configuration_unavailable")
            details = response["error"]["details"]
            self.assertEqual(details["reason"], "active_missing")
            self.assertEqual(details["durableState"], "no_active_configuration")
            self.assertEqual(details["candidateState"], "not_saved")
            self.assertIsNone(service.active())

    # @@SAVE_TESTS3@@

    def test_disabled_storage_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, active, _runtime, api = self._active_api(
                root, include_disabled_storage=True
            )
            status, response = request(
                api,
                "/api/v1/media-libraries",
                method="POST",
                body=self._save_body(storageId="disabled-storage"),
            )
            self.assertEqual(status, 409, response)
            self.assertEqual(response["error"]["code"], "media_library_storage_unavailable")
            self.assertEqual(response["error"]["details"]["durableState"], "active_preserved")
            self.assertEqual(service.active().revision_id, active.revision_id)

    def test_disabled_media_library_is_saved_but_not_browseable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, active, _runtime, api = self._active_api(root)
            status, response = request(
                api,
                "/api/v1/media-libraries",
                method="POST",
                body=self._save_body(enabled=False),
            )
            self.assertEqual(status, 200, response)
            self.assertFalse(response["mediaLibrary"]["enabled"])
            self.assertNotEqual(service.active().revision_id, active.revision_id)
            saved = next(
                item
                for item in service.active().document["mediaLibraries"]
                if item["id"] == "archive"
            )
            self.assertFalse(saved["enabled"])
            browse_status, browse = request(
                api,
                "/api/v1/media-libraries/archive/files",
                token="admin-token",
            )
            self.assertIn(browse_status, {403, 404, 409})
            self.assertNotEqual(browse.get("mediaLibrary", {}).get("id"), "archive")

    def test_missing_required_permission_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, active, runtime_repository, _api = self._active_api(
                root
            )
            for index, permissions in enumerate(
                (
                    frozenset({ApiPermission.READ, ApiPermission.MANAGE_CONFIGURATION}),
                    frozenset({ApiPermission.READ, ApiPermission.ACTIVATE_CONFIGURATION}),
                )
            ):
                principal = ResolvedApiPrincipal(
                    f"limited-{index}", f"limited-token-{index}", permissions
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
                    "/api/v1/media-libraries",
                    method="POST",
                    body=self._save_body(),
                    token=f"limited-token-{index}",
                )
                self.assertEqual(status, 403, response)
                self.assertEqual(response["error"]["code"], "forbidden")
                self.assertEqual(service.active().revision_id, active.revision_id)
                self.assertEqual(len(service.active().document["mediaLibraries"]), 2)

    # @@SAVE_TESTS4@@

    def test_concurrent_active_replacement_wins_without_candidate_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, objects, active, _runtime, api = self._active_api(root)

            def competing_winner(_revision) -> object:
                competitor = service.create_successor_draft(actor="competitor")
                validated = service.validate(competitor.revision_id, actor="competitor")
                self._evidence_gates(objects, validated)
                return objects.activate_checked(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="competitor",
                )

            with patch.object(
                api,
                "_prepare_runtime_binding_for_revision",
                side_effect=competing_winner,
            ):
                status, response = request(
                    api,
                    "/api/v1/media-libraries",
                    method="POST",
                    body=self._save_body(mediaLibraryId="race-library"),
                )
            self.assertEqual(status, 409, response)
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
                [item["id"] for item in winner.document["mediaLibraries"]],
            )

    def test_runtime_binding_failure_preserves_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ReadOnlyStorage("source-storage")
            target = ReadOnlyStorage("media-target")
            values = self._active_api(
                root,
                storage_adapters={"source-storage": source, "media-target": target},
            )
            _repository, service, _objects, _active, _runtime, api = values
            # Warm the process binding against a known Active exactly as any
            # prior successful configuration change would.  The Save handler's
            # initial refresh then reuses this cached binding, so the injected
            # failure surfaces at successor preparation (before_publish) rather
            # than at an unrelated cold-cache rebuild.
            self._save_media_library(api, "warmup")
            warm_active = service.active()
            with patch.object(
                api,
                "_build_runtime_binding",
                side_effect=RuntimeError("simulated runtime publication failure"),
            ):
                status, response = request(
                    api,
                    "/api/v1/media-libraries",
                    method="POST",
                    body=self._save_body(mediaLibraryId="runtime-failure"),
                )
            self.assertEqual(status, 503, response)
            # Runtime-binding preparation is a Save-shared mechanism, so the
            # failure carries the shared runtime-binding code, matching the
            # ResourceLibrary Save contract for the identical failure.
            self.assertEqual(response["error"]["code"], "resource_library_runtime_failed")
            # The previous Active is preserved; the failing successor never
            # publishes and never appears in the Active document.
            self.assertEqual(service.active().revision_id, warm_active.revision_id)
            self.assertNotIn(
                "runtime-failure",
                [item["id"] for item in service.active().document["mediaLibraries"]],
            )
            self.assertEqual(source.mutations, [])
            self.assertEqual(target.mutations, [])

    # @@SAVE_TESTS5@@

    def test_persistence_validation_and_activation_failures_keep_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ReadOnlyStorage("source-storage")
            target = ReadOnlyStorage("media-target")
            values = self._active_api(
                root,
                storage_adapters={"source-storage": source, "media-target": target},
            )
            repository, service, _objects, active, _runtime, api = values

            with patch.object(
                repository,
                "create_revision_with_audit",
                side_effect=RuntimeError("simulated successor persistence failure"),
            ):
                status, response = request(
                    api,
                    "/api/v1/media-libraries",
                    method="POST",
                    body=self._save_body(mediaLibraryId="create-failure"),
                )
            self.assertEqual(status, 503, response)
            self.assertEqual(response["error"]["code"], "media_library_persistence_failed")
            self.assertEqual(response["error"]["details"]["durableState"], "active_preserved")
            self.assertEqual(service.active().revision_id, active.revision_id)

            with patch.object(
                service,
                "validate",
                side_effect=RuntimeError("simulated validation lifecycle failure"),
            ):
                status, response = request(
                    api,
                    "/api/v1/media-libraries",
                    method="POST",
                    body=self._save_body(mediaLibraryId="validate-failure"),
                )
            self.assertEqual(status, 503, response)
            self.assertEqual(response["error"]["code"], "media_library_persistence_failed")
            self.assertEqual(service.active().revision_id, active.revision_id)

            with patch.object(service, "validate", return_value=active):
                status, response = request(
                    api,
                    "/api/v1/media-libraries",
                    method="POST",
                    body=self._save_body(mediaLibraryId="invalid-status"),
                )
            self.assertEqual(status, 422, response)
            self.assertEqual(response["error"]["code"], "media_library_validation_failed")
            self.assertEqual(service.active().revision_id, active.revision_id)

            with patch.object(
                repository,
                "activate_revision",
                side_effect=RuntimeError("simulated activation persistence failure"),
            ):
                status, response = request(
                    api,
                    "/api/v1/media-libraries",
                    method="POST",
                    body=self._save_body(mediaLibraryId="activation-failure"),
                )
            self.assertEqual(status, 503, response)
            self.assertEqual(response["error"]["code"], "media_library_persistence_failed")
            self.assertEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(source.mutations, [])
            self.assertEqual(target.mutations, [])

    # @@SAVE_TESTS6@@

    def test_save_creates_no_work_or_organizer_execution(self) -> None:
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
                    "/api/v1/media-libraries",
                    method="POST",
                    body=self._save_body(mediaLibraryId="side-effect-free"),
                )
            self.assertEqual(status, 200, response)
            self.assertEqual(response["sideEffects"], "configuration_only")
            self.assertNotEqual(service.active().revision_id, active.revision_id)
            after_counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("tasks", "automation_jobs")
            }
            self.assertEqual(after_counts, before_counts)
            self.assertEqual(source.mutations, [])
            self.assertEqual(target.mutations, [])

    # @@REMOVAL_TESTS@@

    def test_removal_preview_reports_references_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, _service, _objects, _active, _runtime, api = self._active_api(root)
            status, body = request(
                api,
                "/api/v1/media-libraries/movies/removal-preview",
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(body["mediaLibrary"]["id"], "movies")
            self.assertEqual(body["storage"]["id"], "media-target")
            self.assertGreaterEqual(body["references"]["total"], 1)
            self.assertEqual(body["sideEffects"], "none")

    def test_referenced_library_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, active, _runtime, api = self._active_api(root)
            status, preview = request(
                api,
                "/api/v1/media-libraries/movies/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            status, body = request(
                api,
                "/api/v1/media-libraries/movies",
                method="DELETE",
                body=_media_removal_confirmation(preview),
            )
            self.assertEqual(status, 409, body)
            self.assertEqual(body["error"]["code"], "configuration_object_referenced")
            self.assertGreaterEqual(body["error"]["details"]["referenceCount"], 1)
            self.assertEqual(service.active().revision_id, active.revision_id)
            self.assertIn(
                "movies",
                [item["id"] for item in service.active().document["mediaLibraries"]],
            )

    def test_unreferenced_removal_publishes_successor_and_keeps_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, _active, _runtime, api = self._active_api(root)
            self._save_media_library(api, "archive")
            archive_root = root / "target" / "Archive"
            (archive_root / "nested").mkdir(parents=True)
            (archive_root / "movie.mkv").write_bytes(b"\x00mkv-bytes")
            (archive_root / "nested" / "deep.txt").write_text("deep", encoding="utf-8")
            before = self._tree_bytes(root / "target")
            status, preview = request(
                api,
                "/api/v1/media-libraries/archive/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            status, body = request(
                api,
                "/api/v1/media-libraries/archive",
                method="DELETE",
                body=_media_removal_confirmation(preview),
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(body["removed"]["id"], "archive")
            self.assertEqual(body["sideEffects"], "configuration_only")
            self.assertEqual(self._tree_bytes(root / "target"), before)
            self.assertNotIn(
                "archive",
                [item["id"] for item in service.active().document["mediaLibraries"]],
            )

    # @@REMOVAL_TESTS2@@

    def test_removal_never_invokes_organizer_or_storage_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ReadOnlyStorage("source-storage")
            target = ReadOnlyStorage("media-target")
            values = self._active_api(
                root,
                storage_adapters={"source-storage": source, "media-target": target},
            )
            _repository, _service, _objects, _active, _runtime, api = values
            with patch.object(OrganizerExecutor, "execute") as execute:
                self._save_media_library(api, "archive")
                status, preview = request(
                    api,
                    "/api/v1/media-libraries/archive/removal-preview",
                )
                self.assertEqual(status, 200, preview)
                status, body = request(
                    api,
                    "/api/v1/media-libraries/archive",
                    method="DELETE",
                    body=_media_removal_confirmation(preview),
                )
                self.assertEqual(status, 200, body)
                execute.assert_not_called()
            self.assertEqual(source.mutations, [])
            self.assertEqual(target.mutations, [])

    def test_removal_requires_configuration_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, _active, runtime_repository, api = self._active_api(
                root
            )
            viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
            viewer_api = MediaFlowApi(
                runtime_repository,
                None,
                principals=(viewer,),
                configuration_service=service,
                bootstrap_document=self._document(root),
            )
            status, preview = request(
                viewer_api,
                "/api/v1/media-libraries/movies/removal-preview",
                token="viewer-token",
            )
            self.assertEqual(status, 200, preview)
            status, body = request(
                viewer_api,
                "/api/v1/media-libraries/movies",
                method="DELETE",
                token="viewer-token",
                body=_media_removal_confirmation(preview),
            )
            self.assertEqual(status, 403, body)
            self.assertEqual(body["error"]["code"], "forbidden")

    def test_missing_library_removal_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, _service, _objects, _active, _runtime, api = self._active_api(root)
            status, preview = request(
                api,
                "/api/v1/media-libraries/movies/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            confirmation = _media_removal_confirmation(preview)
            confirmation["expectedLibraryId"] = "does-not-exist"
            status, body = request(
                api,
                "/api/v1/media-libraries/does-not-exist",
                method="DELETE",
                body=confirmation,
            )
            self.assertEqual(status, 404, body)
            self.assertEqual(body["error"]["code"], "media_library_not_found")

    # @@REMOVAL_TESTS3@@

    def test_stale_active_revision_refuses_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, _active, _runtime, api = self._active_api(root)
            self._save_media_library(api, "archive")
            _status, preview = request(
                api,
                "/api/v1/media-libraries/archive/removal-preview",
            )
            stale_confirmation = _media_removal_confirmation(preview)
            # The Active revision advances after the operator previewed.
            self._save_media_library(api, "vault")
            status, body = request(
                api,
                "/api/v1/media-libraries/archive",
                method="DELETE",
                body=stale_confirmation,
            )
            self.assertEqual(status, 409, body)
            self.assertEqual(body["error"]["code"], "media_library_removal_stale")
            self.assertEqual(body["error"]["details"]["durableState"], "active_preserved")
            self.assertIn(
                "archive",
                [item["id"] for item in service.active().document["mediaLibraries"]],
            )

    def test_mismatched_library_identity_refuses_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, _active, _runtime, api = self._active_api(root)
            self._save_media_library(api, "archive")
            _status, preview = request(
                api,
                "/api/v1/media-libraries/archive/removal-preview",
            )
            confirmation = _media_removal_confirmation(preview)
            confirmation["expectedLibraryId"] = "movies"
            status, body = request(
                api,
                "/api/v1/media-libraries/archive",
                method="DELETE",
                body=confirmation,
            )
            self.assertEqual(status, 409, body)
            self.assertEqual(body["error"]["code"], "media_library_removal_stale")
            self.assertIn(
                "archive",
                [item["id"] for item in service.active().document["mediaLibraries"]],
            )

    def test_disabled_library_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, service, _objects, _active, _runtime, api = self._active_api(root)
            self._save_media_library(api, "archive", enabled=False)
            status, preview = request(
                api,
                "/api/v1/media-libraries/archive/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            self.assertEqual(preview["mediaLibrary"]["enabled"], False)
            status, body = request(
                api,
                "/api/v1/media-libraries/archive",
                method="DELETE",
                body=_media_removal_confirmation(preview),
            )
            self.assertEqual(status, 409, body)
            self.assertEqual(body["error"]["code"], "media_library_disabled")
            self.assertEqual(body["error"]["details"]["durableState"], "active_preserved")
            self.assertIn(
                "archive",
                [item["id"] for item in service.active().document["mediaLibraries"]],
            )


if __name__ == "__main__":
    unittest.main()
