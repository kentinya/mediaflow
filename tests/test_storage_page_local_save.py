from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
    ConfigurationVersionConflict,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageCapabilities, StorageEntry, StorageEntryType
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request

SAVE_ROUTE = "/api/v1/storages"
INVENTORY_ROUTE = "/api/v1/operations/storage-management/inventory"

# Sentinel credential values.  They are injected only to prove that no response,
# audit record, validation error or log ever carries a secret value: the Storage
# contract accepts deployment-owned environment-variable *names*, never values.
SECRET_SENTINELS = {
    "SMB_USER": "sentinel-smb-user-value",
    "SMB_PASS": "sentinel-smb-password-value",
    "OPENLIST_TOKEN": "sentinel-openlist-token-value",
    "AWS_ACCESS_KEY_ID": "sentinel-access-key-value",
    "AWS_SECRET_ACCESS_KEY": "sentinel-secret-key-value",
    "R2_ACCESS_KEY_ID": "sentinel-r2-access-key-value",
    "R2_SECRET_ACCESS_KEY": "sentinel-r2-secret-key-value",
}


class ZeroMutationStorage:
    """Provider-neutral fake that proves Save only ever performs reads."""

    def __init__(self, storage_id: str) -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = False
        self.capabilities = StorageCapabilities()
        self.mutations: list[str] = []
        self.read_calls: list[str] = []
        # When set, the root read is denied: the same unavailable-mount /
        # permission shape a real provider failure produces.
        self.fail = False

    def _read(self, operation: str, path: str) -> None:
        if self.fail:
            raise PermissionError(f"{self.storage_id} read denied")
        self.read_calls.append(f"{operation}:{path}")

    def stat(self, path: str) -> StorageEntry:
        self._read("stat", path)
        return StorageEntry(path, path, StorageEntryType.DIRECTORY, 0, datetime.now(UTC))

    def list(self, path: str):
        self._read("list", path)
        return ()

    def exists(self, path: str) -> bool:
        self._read("exists", path)
        return True

    def write(self, *args, **kwargs):
        self.mutations.append("write")
        raise AssertionError("Storage Save must not write Storage")

    def create_directory(self, *args, **kwargs):
        self.mutations.append("create_directory")
        raise AssertionError("Storage Save must not create Storage directories")

    def move(self, *args, **kwargs):
        self.mutations.append("move")
        raise AssertionError("Storage Save must not move Storage files")

    def copy(self, *args, **kwargs):
        self.mutations.append("copy")
        raise AssertionError("Storage Save must not copy Storage files")

    def delete(self, *args, **kwargs):
        self.mutations.append("delete")
        raise AssertionError("Storage Save must not delete Storage files")

    def hard_link(self, *args, **kwargs):
        self.mutations.append("hard_link")
        raise AssertionError("Storage Save must not hard-link Storage files")

    def soft_link(self, *args, **kwargs):
        self.mutations.append("soft_link")
        raise AssertionError("Storage Save must not soft-link Storage files")


def add_body(**overrides) -> dict:
    body = {
        "storageId": "local-new",
        "name": "Local New",
        "type": "local",
        "rootPath": "/media/storage-save",
        "readOnly": False,
        "enabled": True,
        "options": {},
    }
    body.update(overrides)
    return body


def edit_body(active: dict, storage_id: str, **overrides) -> dict:
    body = {
        "storageId": storage_id,
        "name": "Edited Storage",
        "type": "local",
        "rootPath": "/media/storage-save",
        "readOnly": False,
        "enabled": True,
        "options": {},
        "expectedRevisionId": active["revisionId"],
        "expectedVersion": active["revisionSequence"],
        "expectedDigest": active["digest"],
    }
    body.update(overrides)
    return body


def app_body(**overrides) -> dict:
    """One application-level candidate (canonical ``id`` field naming)."""

    body = {
        "id": "app-storage",
        "name": "App Storage",
        "type": "local",
        "rootPath": "",
        "readOnly": False,
        "enabled": True,
        "options": {},
    }
    body.update(overrides)
    return body


class StoragePageLocalSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "source" / "incoming").mkdir(parents=True)
        (self.root / "target" / "Movies").mkdir(parents=True)
        self.environment = patch.dict(os.environ, SECRET_SENTINELS, clear=False)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.directory.cleanup)

        document = example_document()
        document["persistence"]["databasePath"] = str(self.root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(self.root / "source")
        document["storages"][1]["rootPath"] = str(self.root / "target")
        document["resourceLibraries"][0]["storagePath"] = "incoming"
        document["mediaLibraries"][0]["rootPath"] = "Movies"

        self.configuration_repository = SQLiteConfigurationRepository(
            self.root / "configuration.sqlite3"
        )
        self.addCleanup(self.configuration_repository.close)
        self.configuration = ManagedConfigurationService(
            self.configuration_repository,
            bootstrap_database_path=str(self.root / "configuration.sqlite3"),
        )
        # The Active baseline is created with real Local Storage so its
        # evidence is current; per-test mutation probes are registered on the
        # application service/API afterwards.
        self.objects = ConfigurationObjectService(
            self.configuration,
            storage_browser_cursor_secret="storage-save-test-secret",
        )
        draft = self.configuration.import_draft(document, actor="operator")
        validated = self.configuration.validate(draft.revision_id, actor="operator")
        self._evidence_gates(validated)
        self.active = self.objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        self.source = ZeroMutationStorage("source-storage")
        self.target = ZeroMutationStorage("media-target")
        self.adapters = {"source-storage": self.source, "media-target": self.target}
        (self.root / "six-local").mkdir()
        for storage_id in (
            "smb-six",
            "openlist-six",
            "s3-six",
            "r2-six",
            "s3c-six",
            "smb-preserve",
            "smb-switch",
            "smb-prefill",
            "openlist-audit",
        ):
            self.adapters[storage_id] = ZeroMutationStorage(storage_id)
        self.objects._storage_adapters.update(self.adapters)
        self.runtime_repository = SQLiteTaskRepository(str(self.root / "runtime.sqlite3"))
        self.addCleanup(self.runtime_repository.close)
        self.admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
        self.viewer = ResolvedApiPrincipal(
            "viewer", "viewer-token", frozenset({ApiPermission.READ})
        )
        self.api = MediaFlowApi(
            self.runtime_repository,
            None,
            principals=(self.admin, self.viewer),
            configuration_service=self.configuration,
            storage_adapters=self.adapters,
            storage_browser_cursor_secret="storage-save-test-secret",
        )

    def tearDown(self) -> None:
        self.objects._setup_check_executor.shutdown(wait=True)

    def _evidence_gates(self, revision) -> None:
        for storage_id in ("source-storage", "media-target"):
            evidence = self.objects.storage_check(
                revision.revision_id,
                storage_id=storage_id,
                expected_version=revision.version,
                expected_digest=revision.digest,
                actor="operator",
            )
            if evidence.status is not ConfigurationStorageCheckStatus.PASSED:
                raise AssertionError(f"initial Storage check failed: {storage_id}")
        strategy = self.objects.recognition_strategy_test(
            revision.revision_id,
            expected_version=revision.version,
            expected_digest=revision.digest,
            actor="operator",
            resource_library_id="source",
            synthetic_path="Example.Movie.2024.1080p.mkv",
        )
        if strategy.status is not ConfigurationStrategyTestStatus.COMPLETED:
            raise AssertionError("initial strategy test failed")
        destination = self.objects.destination_precheck(
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

    # ------------------------------------------------------------------
    # Helpers

    def add_body(self, **overrides) -> dict:
        active = self.configuration.active()
        return add_body(
            **{
                "rootPath": str(self.root / "source"),
                "expectedRevisionId": active.revision_id,
                "expectedVersion": active.revision_sequence,
                "expectedDigest": active.digest,
                **overrides,
            }
        )

    def active_identity(self) -> dict:
        status, inventory = request(self.api, INVENTORY_ROUTE)
        self.assertEqual(status, 200, inventory)
        self.assertTrue(inventory["available"], inventory)
        return inventory["active"]

    def form_identity(self, storage_id: str) -> dict:
        """The exact Active identity the operator's opened Add/Edit form binds to."""

        status, projection = request(self.api, f"{SAVE_ROUTE}/{storage_id}/edit")
        self.assertEqual(status, 200, projection)
        return projection["active"]

    def storage_of(self, storage_id: str) -> dict | None:
        document = self.configuration.active().document
        return next(
            (item for item in document["storages"] if item.get("id") == storage_id),
            None,
        )

    def assert_no_secret_values(self, payload) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, default=str)
        for value in SECRET_SENTINELS.values():
            self.assertNotIn(value, encoded)

    def object_change_actions(self) -> list[str]:
        actions: list[str] = []
        for revision in self.configuration_repository.list_revisions():
            for audit in self.configuration_repository.list_revision_audits(revision.revision_id):
                change = audit.safe_after().get("objectChange")
                if isinstance(change, dict) and isinstance(change.get("action"), str):
                    actions.append(change["action"])
        return actions

    def _management_only_api(self) -> MediaFlowApi:
        """One isolated management-only bootstrap API with no Active runtime."""

        root = Path(tempfile.mkdtemp())
        repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        task_repository = SQLiteTaskRepository(str(root / "runtime.sqlite3"))
        bootstrap = {"persistence": {"databasePath": str(root / "runtime.sqlite3")}}
        self.addCleanup(task_repository.close)
        self.addCleanup(repository.close)
        service = ManagedConfigurationService(
            repository,
            bootstrap_database_path=str(root / "runtime.sqlite3"),
            bootstrap_document=bootstrap,
            management_only=True,
        )
        return MediaFlowApi(
            task_repository,
            None,
            principals=(self.admin,),
            configuration_service=service,
            bootstrap_document=bootstrap,
            management_only=True,
        )

    # ------------------------------------------------------------------
    # Edit projection

    def test_edit_projection_is_typed_secret_free_and_bound_to_active(self) -> None:
        status, projection = request(self.api, f"{SAVE_ROUTE}/source-storage/edit")
        self.assertEqual(status, 200, projection)
        storage = projection["storage"]
        self.assertEqual(storage["id"], "source-storage")
        self.assertEqual(storage["type"], "local")
        self.assertEqual(storage["rootPath"], str(self.root / "source"))
        self.assertEqual(storage["options"], {})
        self.assertEqual(storage["secretReadiness"], [])
        self.assertFalse(storage["readOnly"])
        self.assertTrue(storage["enabled"])
        self.assertEqual(projection["sideEffects"], "none")
        managed = self.configuration.active()
        self.assertEqual(projection["active"]["revisionId"], managed.revision_id)
        self.assertEqual(projection["active"]["revisionSequence"], managed.revision_sequence)
        self.assertEqual(projection["active"]["digest"], managed.digest)
        self.assertNotIn("notes", storage)
        self.assert_no_secret_values(projection)
        # A prefill read performs zero Storage access and zero mutation.
        self.assertEqual(self.source.mutations, [])
        self.assertEqual(self.source.read_calls, [])
        self.assertEqual(self.target.mutations, [])

        missing = request(self.api, f"{SAVE_ROUTE}/does-not-exist/edit")
        self.assertEqual(missing[0], 404, missing[1])
        self.assertEqual(missing[1]["error"]["code"], "storage_not_found")

    def test_remote_edit_projection_exposes_references_without_values(self) -> None:
        status, created = request(
            self.api,
            SAVE_ROUTE,
            method="POST",
            body=self.add_body(
                storageId="smb-prefill",
                name="SMB Prefill",
                type="smb",
                rootPath="media",
                options={
                    "host": "nas.local",
                    "share": "media",
                    "usernameEnv": "SMB_USER",
                    "passwordEnv": "SMB_PASS",
                    "domain": "WORKGROUP",
                },
            ),
        )
        self.assertEqual(status, 200, created)
        status, projection = request(self.api, f"{SAVE_ROUTE}/smb-prefill/edit")
        self.assertEqual(status, 200, projection)
        storage = projection["storage"]
        self.assertEqual(storage["type"], "smb")
        # Reference names and deployment readiness cross the boundary; values do not.
        self.assertEqual(storage["options"]["passwordEnv"], "SMB_PASS")
        readiness = {entry["field"]: entry for entry in storage["secretReadiness"]}
        self.assertEqual(readiness["passwordEnv"]["env"], "SMB_PASS")
        self.assertEqual(readiness["passwordEnv"]["state"], "SET")
        self.assert_no_secret_values(projection)

    def test_setup_state_survives_add_as_actionable_error_not_false_success(self) -> None:
        api = self._management_only_api()
        status, document = request(
            api,
            SAVE_ROUTE,
            method="POST",
            body=self.add_body(
                storageId="setup-storage",
                name="Setup Storage",
                rootPath="/tmp/setup-storage",
            ),
        )
        self.assertEqual(status, 503, document)
        self.assertEqual(document["error"]["code"], "configuration_unavailable")
        self.assertEqual(document["error"]["details"]["durableState"], "no_active_configuration")
        self.assertEqual(document["error"]["details"]["candidateState"], "not_saved")
        self.assertIn("activate", document["error"]["details"]["nextAction"])
        status, projection = request(api, f"{SAVE_ROUTE}/setup-storage/edit")
        self.assertEqual(status, 503, projection)
        self.assertEqual(projection["error"]["code"], "configuration_unavailable")

    # ------------------------------------------------------------------
    # Add / Edit for every supported provider type

    def _provider_cases(self) -> list[tuple[dict, dict]]:
        cases: list[tuple[dict, dict]] = []
        for storage_id, name, storage_type, root_path, options, edited_options in (
            (
                "local-six",
                "Local Six",
                "local",
                str(self.root / "six-local"),
                {},
                {},
            ),
            (
                "smb-six",
                "SMB Six",
                "smb",
                "media",
                {
                    "host": "nas.local",
                    "share": "media",
                    "usernameEnv": "SMB_USER",
                    "passwordEnv": "SMB_PASS",
                },
                {"domain": "WORKGROUP"},
            ),
            (
                "openlist-six",
                "OpenList Six",
                "openlist",
                "media",
                {"tokenEnv": "OPENLIST_TOKEN", "baseUrl": "https://openlist.example.local"},
                {"maxRetries": 4},
            ),
            (
                "s3-six",
                "S3 Six",
                "s3",
                "media",
                {
                    "bucket": "media-bucket",
                    "region": "us-east-1",
                    "accessKeyEnv": "AWS_ACCESS_KEY_ID",
                    "secretKeyEnv": "AWS_SECRET_ACCESS_KEY",
                },
                {"maxConcurrency": 8},
            ),
            (
                "r2-six",
                "R2 Six",
                "r2",
                "media",
                {
                    "bucket": "r2-bucket",
                    "endpoint": "https://account.r2.cloudflarestorage.com",
                    "accessKeyEnv": "R2_ACCESS_KEY_ID",
                    "secretKeyEnv": "R2_SECRET_ACCESS_KEY",
                },
                {"forcePathStyle": True},
            ),
            (
                "s3c-six",
                "S3 Compatible Six",
                "s3-compatible",
                "media",
                {
                    "bucket": "compatible-bucket",
                    "endpoint": "https://objects.example.local",
                    "accessKeyEnv": "AWS_ACCESS_KEY_ID",
                    "secretKeyEnv": "AWS_SECRET_ACCESS_KEY",
                },
                {"pageSize": 500},
            ),
        ):
            add = self.add_body(
                storageId=storage_id,
                name=name,
                type=storage_type,
                rootPath=root_path,
                options=dict(options),
            )
            edit = edit_body(
                {"revisionId": "", "revisionSequence": 0, "digest": ""},
                storage_id,
                name=f"{name} Edited",
                type=storage_type,
                rootPath=root_path,
                options={**options, **edited_options},
            )
            cases.append((add, edit))
        return cases

    def test_all_six_provider_types_add_then_edit_to_checked_active(self) -> None:
        for add, template in self._provider_cases():
            with self.subTest(storage=add["storageId"]):
                previous_revision = self.configuration.active().revision_id
                active = self.configuration.active()
                add.update(
                    expectedRevisionId=active.revision_id,
                    expectedVersion=active.revision_sequence,
                    expectedDigest=active.digest,
                )
                status, created = request(self.api, SAVE_ROUTE, method="POST", body=add)
                self.assertEqual(status, 200, created)
                self.assertEqual(created["storage"]["id"], add["storageId"])
                self.assertEqual(created["storage"]["type"], add["type"])
                self.assertEqual(created["storage"]["name"], add["name"])
                self.assertEqual(created["active"]["status"], "active")
                self.assertNotEqual(self.configuration.active().revision_id, previous_revision)
                self.assert_no_secret_values(created)
                persisted = self.storage_of(add["storageId"])
                self.assertIsNotNone(persisted)

                # The form re-opens from the newly published Active object.
                status, projection = request(self.api, f"{SAVE_ROUTE}/{add['storageId']}/edit")
                self.assertEqual(status, 200, projection)
                active = projection["active"]
                self.assertEqual(active["revisionId"], self.configuration.active().revision_id)
                edit = {
                    **template,
                    "expectedRevisionId": active["revisionId"],
                    "expectedVersion": active["revisionSequence"],
                    "expectedDigest": active["digest"],
                }
                status, updated = request(
                    self.api,
                    f"{SAVE_ROUTE}/{add['storageId']}",
                    method="PUT",
                    body=edit,
                )
                self.assertEqual(status, 200, updated)
                self.assertEqual(updated["storage"]["name"], edit["name"])
                self.assert_no_secret_values(updated)
                persisted = self.storage_of(add["storageId"])
                self.assertEqual(persisted["name"], edit["name"])

        # The refreshed inventory is served from the same Active authority.
        status, inventory = request(self.api, INVENTORY_ROUTE)
        self.assertEqual(status, 200, inventory)
        ids = {item["id"] for item in inventory["items"]}
        for add, _template in self._provider_cases():
            self.assertIn(add["storageId"], ids)
        # Provider-specific defaults persisted through the typed field path.
        self.assertEqual(self.storage_of("smb-six")["options"]["port"], 445)
        self.assertEqual(self.storage_of("openlist-six")["options"]["maxRetries"], 4)
        self.assertEqual(self.storage_of("s3-six")["options"]["maxConcurrency"], 8)
        self.assertIs(self.storage_of("r2-six")["options"]["forcePathStyle"], True)
        self.assertEqual(self.storage_of("s3c-six")["options"]["pageSize"], 500)
        # Nothing mutated Storage and no workflow work was created.
        self.assertEqual(self.source.mutations, [])
        self.assertEqual(self.target.mutations, [])
        connection = sqlite3.connect(self.root / "runtime.sqlite3")
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM automation_jobs").fetchone()[0],
                0,
            )
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 0)
        finally:
            connection.close()

    def test_edit_preserves_unexposed_options_and_rejects_id_change(self) -> None:
        status, created = request(
            self.api,
            SAVE_ROUTE,
            method="POST",
            body=self.add_body(
                storageId="smb-preserve",
                name="SMB Preserve",
                type="smb",
                rootPath="media",
                options={
                    "host": "nas.local",
                    "share": "media",
                    "usernameEnv": "SMB_USER",
                    "passwordEnv": "SMB_PASS",
                    "domain": "WORKGROUP",
                },
            ),
        )
        self.assertEqual(status, 200, created)
        active = self.form_identity("smb-preserve")
        # The focused form submits only the fields it exposes; every other
        # supported option must survive the edit untouched.
        status, edited = request(
            self.api,
            f"{SAVE_ROUTE}/smb-preserve",
            method="PUT",
            body=edit_body(
                active,
                "smb-preserve",
                name="SMB Preserve Renamed",
                type="smb",
                rootPath="media",
                options={"host": "nas2.local", "share": "media"},
            ),
        )
        self.assertEqual(status, 200, edited)
        options = self.storage_of("smb-preserve")["options"]
        self.assertEqual(options["host"], "nas2.local")
        self.assertEqual(options["domain"], "WORKGROUP")
        self.assertEqual(options["usernameEnv"], "SMB_USER")
        self.assertEqual(options["passwordEnv"], "SMB_PASS")
        self.assertEqual(options["port"], 445)
        self.assert_no_secret_values(edited)

        # An explicit null clears an optional value.
        status, cleared = request(
            self.api,
            f"{SAVE_ROUTE}/smb-preserve",
            method="PUT",
            body=edit_body(
                self.form_identity("smb-preserve"),
                "smb-preserve",
                name="SMB Preserve Renamed",
                type="smb",
                rootPath="media",
                options={"host": "nas2.local", "share": "media", "domain": None},
            ),
        )
        self.assertEqual(status, 200, cleared)
        self.assertNotIn("domain", self.storage_of("smb-preserve")["options"])

        # An ID change is rejected rather than re-identifying the object.
        status, rejected = request(
            self.api,
            f"{SAVE_ROUTE}/smb-preserve",
            method="PUT",
            body=edit_body(
                self.form_identity("smb-preserve"),
                "smb-preserve",
                storageId="smb-reidentified",
                name="Renamed Identity",
                type="smb",
                rootPath="media",
            ),
        )
        self.assertEqual(status, 400, rejected)
        self.assertEqual(rejected["error"]["code"], "invalid_request")
        self.assertIsNotNone(self.storage_of("smb-preserve"))
        self.assertIsNone(self.storage_of("smb-reidentified"))

        # A PUT addressed at a Storage that does not exist cannot create one.
        status, rejected = request(
            self.api,
            f"{SAVE_ROUTE}/smb-never-existed",
            method="PUT",
            body=edit_body(
                self.form_identity("smb-preserve"),
                "smb-never-existed",
                name="Ghost",
                type="smb",
                rootPath="media",
                options={
                    "host": "nas.local",
                    "share": "media",
                    "usernameEnv": "SMB_USER",
                    "passwordEnv": "SMB_PASS",
                },
            ),
        )
        self.assertEqual(status, 404, rejected)
        self.assertEqual(rejected["error"]["code"], "storage_not_found")
        self.assertIsNone(self.storage_of("smb-never-existed"))

    def test_edit_provider_change_drops_unsupported_options(self) -> None:
        status, created = request(
            self.api,
            SAVE_ROUTE,
            method="POST",
            body=self.add_body(
                storageId="smb-switch",
                name="SMB Switch",
                type="smb",
                rootPath="media",
                options={
                    "host": "nas.local",
                    "share": "media",
                    "usernameEnv": "SMB_USER",
                    "passwordEnv": "SMB_PASS",
                },
            ),
        )
        self.assertEqual(status, 200, created)
        status, edited = request(
            self.api,
            f"{SAVE_ROUTE}/smb-switch",
            method="PUT",
            body=edit_body(
                self.form_identity("smb-switch"),
                "smb-switch",
                name="Now Local",
                type="local",
                rootPath=str(self.root / "source"),
                options={},
            ),
        )
        self.assertEqual(status, 200, edited)
        persisted = self.storage_of("smb-switch")
        self.assertEqual(persisted["type"], "local")
        self.assertEqual(persisted["options"], {})
        self.assertEqual(persisted["rootPath"], str(self.root / "source"))

    # ------------------------------------------------------------------
    # Concurrency, duplicates and invalid input

    def test_stale_writer_and_duplicate_id_preserve_prior_active(self) -> None:
        stale_active = self.form_identity("source-storage")
        status, first = request(
            self.api,
            f"{SAVE_ROUTE}/source-storage",
            method="PUT",
            body=edit_body(
                stale_active,
                "source-storage",
                name="Renamed Once",
                type="local",
                rootPath=str(self.root / "source"),
            ),
        )
        self.assertEqual(status, 200, first)
        published_name = self.storage_of("source-storage")["name"]
        self.assertEqual(published_name, "Renamed Once")
        winner_revision = self.configuration.active().revision_id

        # The same captured Active can never publish a second successor.
        status, stale = request(
            self.api,
            f"{SAVE_ROUTE}/source-storage",
            method="PUT",
            body=edit_body(
                stale_active,
                "source-storage",
                name="Renamed Twice",
                type="local",
                rootPath=str(self.root / "source"),
            ),
        )
        self.assertEqual(status, 409, stale)
        self.assertEqual(stale["error"]["code"], "configuration_version_conflict")
        self.assertEqual(stale["error"]["details"]["candidateState"], "not_published")
        self.assertEqual(self.storage_of("source-storage")["name"], published_name)
        self.assertEqual(self.configuration.active().revision_id, winner_revision)

        # Duplicate identity on Add is rejected before any successor work.
        status, duplicate = request(
            self.api,
            SAVE_ROUTE,
            method="POST",
            body=self.add_body(
                storageId="source-storage",
                name="Duplicate",
                rootPath=str(self.root / "duplicate"),
            ),
        )
        self.assertEqual(status, 409, duplicate)
        self.assertEqual(duplicate["error"]["code"], "storage_duplicate")
        self.assertEqual(self.configuration.active().revision_id, winner_revision)
        self.assertIsNone(self.storage_of("duplicate"))

    def test_invalid_provider_fields_never_publish_a_successor(self) -> None:
        winner = self.configuration.active().revision_id
        smb_options = {
            "host": "nas.local",
            "share": "media",
            "usernameEnv": "SMB_USER",
            "passwordEnv": "SMB_PASS",
        }
        cases: list[tuple[dict, str]] = [
            ({**self.add_body(rootPath=str(self.root / "rel")), "extra": True}, "extra field"),
            (
                self.add_body(
                    storageId="notes-storage",
                    rootPath=str(self.root / "noted"),
                    notes="not supported",
                ),
                "notes field",
            ),
            (self.add_body(rootPath="relative/path"), "local root must be absolute"),
            (self.add_body(rootPath="/"), "host root is unsupported"),
            (self.add_body(expectedVersion=True), "boolean is not a revision"),
            (self.add_body(storageId="Bad_ID"), "identifier shape"),
            (self.add_body(storageId="local/../escape"), "identifier traversal"),
            (self.add_body(name=""), "empty name"),
            (self.add_body(readOnly="yes"), "readOnly type"),
            (self.add_body(enabled=None), "enabled type"),
            (self.add_body(options=None), "options type"),
            (self.add_body(options={"host": "nas.local"}), "unsupported local option"),
            (
                self.add_body(type="quantum-drive", rootPath="media", options={}),
                "unsupported provider type",
            ),
            (
                self.add_body(type="smb", rootPath="media", options={**smb_options, "host": ""}),
                "missing SMB host",
            ),
            (
                self.add_body(
                    type="smb",
                    rootPath="media",
                    options={**smb_options, "port": 70000},
                ),
                "port out of range",
            ),
            (
                self.add_body(
                    type="smb",
                    rootPath="media",
                    options={**smb_options, "password": "sentinel-never-allowed"},
                ),
                "literal secret value",
            ),
            (
                self.add_body(
                    type="smb",
                    rootPath="/absolute/on/smb",
                    options=smb_options,
                ),
                "remote root must be relative",
            ),
            (
                self.add_body(
                    type="r2",
                    rootPath="media",
                    options={
                        "bucket": "r2-bucket",
                        "accessKeyEnv": "R2_ACCESS_KEY_ID",
                        "secretKeyEnv": "R2_SECRET_ACCESS_KEY",
                    },
                ),
                "missing R2 endpoint",
            ),
            (
                self.add_body(
                    type="s3-compatible",
                    rootPath="media",
                    options={
                        "bucket": "compatible-bucket",
                        "endpoint": "objects.example.local",
                        "accessKeyEnv": "AWS_ACCESS_KEY_ID",
                        "secretKeyEnv": "AWS_SECRET_ACCESS_KEY",
                    },
                ),
                "endpoint must be absolute",
            ),
        ]
        for body, label in cases:
            with self.subTest(case=label):
                status, document = request(self.api, SAVE_ROUTE, method="POST", body=body)
                self.assertEqual(status, 400, (label, document))
                self.assertEqual(document["error"]["code"], "invalid_request")
                self.assertEqual(self.configuration.active().revision_id, winner)
                self.assertNotIn("sentinel-never-allowed", json.dumps(document, ensure_ascii=False))
        # Nothing was added by any rejected candidate.
        self.assertIsNone(self.storage_of("local-new"))
        self.assertIsNone(self.storage_of("notes-storage"))

    def test_failed_read_only_evidence_preserves_prior_active(self) -> None:
        # Only this scenario lets real Storage I/O decide the outcome: the API's
        # own checked-publication service drops the fake adapter so the successor
        # read-only check attempts the (missing) Local root.
        self.api._configuration_objects._storage_adapters["source-storage"] = None
        winner = self.configuration.active().revision_id
        status, failure = request(
            self.api,
            f"{SAVE_ROUTE}/source-storage",
            method="PUT",
            body=edit_body(
                self.form_identity("source-storage"),
                "source-storage",
                name="Missing Mount",
                type="local",
                rootPath=str(self.root / "does-not-exist"),
            ),
        )
        self.assertEqual(status, 409, failure)
        self.assertEqual(failure["error"]["code"], "storage_storage_check_failed")
        self.assertEqual(failure["error"]["details"]["durableState"], "active_preserved")
        self.assertEqual(failure["error"]["details"]["failureCategory"], "not_found")
        self.assertEqual(failure["error"]["details"]["affectedStorageId"], "source-storage")
        self.assertEqual(failure["error"]["details"]["affectedStorageName"], "Missing Mount")
        self.assertIn(
            "make the configured root available",
            failure["error"]["details"]["nextAction"],
        )
        self.assertEqual(self.configuration.active().revision_id, winner)
        self.assertEqual(self.storage_of("source-storage")["rootPath"], str(self.root / "source"))
        self.assertEqual(self.source.mutations, [])
        self.assertEqual(self.target.mutations, [])

        self.api._configuration_objects._storage_adapters["source-storage"] = self.source
        status, saved = request(
            self.api,
            f"{SAVE_ROUTE}/source-storage",
            method="PUT",
            body=edit_body(
                self.form_identity("source-storage"),
                "source-storage",
                name="Recovered Source",
                type="local",
                rootPath=str(self.root / "source"),
            ),
        )
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["storage"]["name"], "Recovered Source")

    # ------------------------------------------------------------------
    # Authority, audit, evidence retention and application boundary

    def test_save_is_backend_authoritative_and_records_redacted_audit(self) -> None:
        status, denied = request(
            self.api,
            SAVE_ROUTE,
            method="POST",
            token="viewer-token",
            body=self.add_body(rootPath=str(self.root / "viewer-attempt")),
        )
        self.assertEqual(status, 403, denied)
        self.assertIsNone(self.storage_of("viewer-attempt"))
        status, denied = request(
            self.api, f"{SAVE_ROUTE}/source-storage", method="PUT", token="viewer-token"
        )
        self.assertEqual(status, 403, denied)
        # A viewer may read the edit projection but not publish through it.
        status, projection = request(
            self.api, f"{SAVE_ROUTE}/source-storage/edit", token="viewer-token"
        )
        self.assertEqual(status, 200, projection)

        status, created = request(
            self.api,
            SAVE_ROUTE,
            method="POST",
            body=self.add_body(
                storageId="openlist-audit",
                name="OpenList Audit",
                type="openlist",
                rootPath="media",
                options={
                    "tokenEnv": "OPENLIST_TOKEN",
                    "baseUrl": "https://openlist.example.local",
                },
            ),
        )
        self.assertEqual(status, 200, created)
        self.assertIn("storage_save", self.object_change_actions())

        status, edited = request(
            self.api,
            f"{SAVE_ROUTE}/openlist-audit",
            method="PUT",
            body=edit_body(
                self.form_identity("openlist-audit"),
                "openlist-audit",
                name="OpenList Audit Edited",
                type="openlist",
                rootPath="media",
                options={
                    "tokenEnv": "OPENLIST_TOKEN",
                    "baseUrl": "https://openlist.example.local",
                    "pageSize": 50,
                },
            ),
        )
        self.assertEqual(status, 200, edited)
        self.assertIn("storage_edit", self.object_change_actions())

        # No secret value in the response, the persisted Active document or the
        # configuration audits.
        self.assert_no_secret_values(created)
        self.assert_no_secret_values(edited)
        self.assert_no_secret_values(self.configuration.active().document)
        audits = self.configuration_repository.list_revision_audits(
            self.configuration.active().revision_id
        )
        self.assertTrue(audits)
        for audit in audits:
            self.assert_no_secret_values(audit.safe_before())
            self.assert_no_secret_values(audit.safe_after())

        # Security audit route evidence is templated, never raw.
        records = self.runtime_repository.list_security_audit(limit=200)
        self.assertTrue(records)
        routes = {record.route for record in records}
        self.assertIn(SAVE_ROUTE, routes)
        self.assertIn("/api/v1/storages/{id}", routes)
        self.assertIn("/api/v1/storages/{id}/edit", routes)
        self.assertFalse(any("openlist-audit" in route for route in routes))

        # The refreshed Active is consumed by the existing browse authority.
        status, browse = request(self.api, "/api/v1/resource-libraries/source/files")
        self.assertEqual(status, 200, browse)
        self.assertEqual(self.source.mutations, [])

    def test_checked_activation_retains_offline_strategy_and_destination_gates(self) -> None:
        status, created = request(
            self.api,
            SAVE_ROUTE,
            method="POST",
            body=self.add_body(rootPath=str(self.root / "source"), name="Gated Local"),
        )
        self.assertEqual(status, 200, created)
        revision = self.configuration.active()
        detail = self.objects.revision_detail(revision.revision_id)
        strategy = detail["recognitionStrategyTest"]
        self.assertIsNotNone(strategy)
        self.assertEqual(strategy["status"], "completed")
        # The strategy evidence binds to this exact successor and is current,
        # proving the offline calculation ran for the published document.
        self.assertEqual(strategy["revisionId"], revision.revision_id)
        self.assertFalse(strategy["stale"])
        precheck = detail["destinationPrecheck"]
        self.assertIsNotNone(precheck)
        self.assertEqual(precheck["status"], "completed")
        self.assertEqual(precheck["revisionId"], revision.revision_id)
        self.assertFalse(precheck["stale"])
        checks = {item["storageId"]: item for item in detail["storageChecks"]}
        self.assertEqual(checks["source-storage"]["status"], "passed")
        self.assertEqual(checks["media-target"]["status"], "passed")
        self.assertFalse(checks["source-storage"]["stale"])
        # Those gates are read-only calculations: no media work exists.
        connection = sqlite3.connect(self.root / "runtime.sqlite3")
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 0)
        finally:
            connection.close()

    def test_disabling_a_referenced_storage_is_blocked_by_full_validation(self) -> None:
        """Disabling cannot leave an enabled library bound to a disabled Storage.

        The bound destination Storage is the edit target, so full successor
        validation plus its own read-only check reject the change and the
        previous Active keeps both the enabled Storage and the enabled library.
        """

        winner = self.configuration.active().revision_id
        status, response = request(
            self.api,
            f"{SAVE_ROUTE}/media-target",
            method="PUT",
            body=edit_body(
                self.form_identity("media-target"),
                "media-target",
                name="Disabled target",
                rootPath=str(self.root / "target"),
                enabled=False,
            ),
        )
        self.assertEqual(status, 409, response)
        self.assertEqual(response["error"]["code"], "storage_storage_check_failed")
        self.assertIn("disabled", str(response["error"]["details"]["nextAction"]))
        self.assertEqual(self.configuration.active().revision_id, winner)
        self.assertIsNot(self.storage_of("media-target").get("enabled"), False)
        self.assertEqual(self.target.mutations, [])

    def test_unavailable_secret_reference_fails_closed_with_recovery(self) -> None:
        """A missing deployment-owned credential blocks publication safely.

        The bound destination Storage is switched to SMB referencing an
        environment variable the deployment never injected: the read-only check
        fails as `missing_secret` before any adapter or provider call, the
        previous Active and Storage contents stay exactly as they were, and the
        projection never leaks the reference value.
        """

        winner = self.configuration.active().revision_id
        status, response = request(
            self.api,
            f"{SAVE_ROUTE}/media-target",
            method="PUT",
            body=edit_body(
                self.form_identity("media-target"),
                "media-target",
                name="Missing Credential Target",
                type="smb",
                rootPath="media",
                options={
                    "host": "nas.invalid",
                    "share": "media",
                    "usernameEnv": "SMB_USER",
                    "passwordEnv": "MF_ABSENT_PASSWORD_REFERENCE",
                },
            ),
        )
        self.assertEqual(status, 409, response)
        self.assertEqual(response["error"]["code"], "storage_storage_check_failed")
        self.assertEqual(response["error"]["details"]["durableState"], "active_preserved")
        self.assertIn("missing_secret", str(response["error"]["details"]["nextAction"]))
        # The prior Active is untouched: the destination remains the Local root.
        self.assertEqual(self.configuration.active().revision_id, winner)
        persisted = self.storage_of("media-target")
        self.assertEqual(persisted["type"], "local")
        self.assertEqual(persisted["rootPath"], str(self.root / "target"))
        # The rejected candidate was never presented as configured.
        self.assertNotIn(
            "MF_ABSENT_PASSWORD_REFERENCE",
            json.dumps(self.configuration.active().document),
        )
        self.assertEqual(self.target.mutations, [])
        for entry in response["error"].values():
            self.assertNotIn("hunter", json.dumps(entry, default=str))

    def test_evidence_persistence_and_runtime_failures_keep_active_and_retry(self) -> None:
        """Every failed admission preserves the prior Active and mutates nothing."""

        api_objects = self.api._configuration_objects
        # A failed read-only Storage check for the exact successor. Only a
        # Enabled Storage being saved also requires a root check, so this journey
        # edits the bound destination Storage and denies its root read.
        self.target.fail = True
        status, response = request(
            self.api,
            f"{SAVE_ROUTE}/media-target",
            method="PUT",
            body=edit_body(
                self.form_identity("media-target"),
                "media-target",
                name="Bound Destination",
                rootPath=str(self.root / "target"),
            ),
        )
        self.assertEqual(status, 409, response)
        self.assertEqual(response["error"]["code"], "storage_storage_check_failed")
        self.assertEqual(response["error"]["details"]["durableState"], "active_preserved")
        self.assertEqual(self.configuration.active().revision_id, self.active.revision_id)
        self.target.fail = False

        # A failed offline Recognition Strategy Test.
        failed_strategy = SimpleNamespace(
            status=ConfigurationStrategyTestStatus.FAILED, result=None
        )
        with patch.object(api_objects, "recognition_strategy_test", return_value=failed_strategy):
            status, response = request(
                self.api, SAVE_ROUTE, method="POST", body=self.add_body(storageId="strategy-fail")
            )
        self.assertEqual(status, 409, response)
        self.assertEqual(response["error"]["code"], "storage_strategy_test_failed")
        self.assertEqual(self.configuration.active().revision_id, self.active.revision_id)

        # A failed read-only destination precheck.
        failed_destination = SimpleNamespace(
            status=ConfigurationDestinationPrecheckStatus.FAILED, result=None
        )
        with patch.object(api_objects, "destination_precheck", return_value=failed_destination):
            status, response = request(
                self.api,
                SAVE_ROUTE,
                method="POST",
                body=self.add_body(storageId="destination-fail"),
            )
        self.assertEqual(status, 409, response)
        self.assertEqual(response["error"]["code"], "storage_destination_check_failed")
        self.assertEqual(self.configuration.active().revision_id, self.active.revision_id)

        # A successor-create persistence failure.
        with patch.object(
            self.configuration_repository,
            "create_revision_with_audit",
            side_effect=RuntimeError("simulated successor persistence failure"),
        ):
            status, response = request(
                self.api, SAVE_ROUTE, method="POST", body=self.add_body(storageId="create-failure")
            )
        self.assertEqual(status, 503, response)
        self.assertEqual(response["error"]["code"], "storage_persistence_failed")
        self.assertEqual(response["error"]["details"]["durableState"], "active_preserved")

        # A validation lifecycle failure.
        with patch.object(
            self.configuration, "validate", side_effect=RuntimeError("simulated validation failure")
        ):
            status, response = request(
                self.api,
                SAVE_ROUTE,
                method="POST",
                body=self.add_body(storageId="validate-failure"),
            )
        self.assertEqual(status, 503, response)
        self.assertEqual(response["error"]["code"], "storage_persistence_failed")

        # A candidate that never reaches VALIDATED is a 422, not a silent save.
        with patch.object(self.configuration, "validate", return_value=self.active):
            status, response = request(
                self.api, SAVE_ROUTE, method="POST", body=self.add_body(storageId="invalid-status")
            )
        self.assertEqual(status, 422, response)
        self.assertEqual(response["error"]["code"], "storage_validation_failed")

        # A runtime-binding failure after a successful activation attempt.
        with patch.object(
            api_objects,
            "activate_checked",
            side_effect=RuntimeError("simulated activation persistence failure"),
        ):
            status, response = request(
                self.api,
                SAVE_ROUTE,
                method="POST",
                body=self.add_body(storageId="activation-failure"),
            )
        self.assertEqual(status, 503, response)
        self.assertEqual(response["error"]["code"], "storage_persistence_failed")
        self.assertEqual(self.configuration.active().revision_id, self.active.revision_id)

        # The process runtime binding stays the previous usable Active.
        self.assertEqual(self.api._runtime_binding.snapshot_id, self.active.revision_id)
        # None of the failed admissions mutated Storage or created workflow work.
        self.assertEqual(self.source.mutations, [])
        self.assertEqual(self.target.mutations, [])
        for storage_id in (
            "create-failure",
            "validate-failure",
            "invalid-status",
            "activation-failure",
        ):
            self.assertIsNone(self.storage_of(storage_id))

    def test_runtime_binding_preparation_failure_is_reported_without_publication(self) -> None:
        # Warm the process binding from the current Active first, so the only
        # remaining `_build_runtime_binding` call is the successor publication
        # step inside Save itself (the same boundary the runtime-binding
        # failure must be reported at).
        warm_status, _inventory = request(self.api, INVENTORY_ROUTE)
        self.assertEqual(warm_status, 200)
        self.assertIsNotNone(self.api._runtime_binding.files_browser)
        with patch.object(
            self.api,
            "_build_runtime_binding",
            side_effect=RuntimeError("simulated runtime failure"),
        ):
            status, response = request(
                self.api, SAVE_ROUTE, method="POST", body=self.add_body(storageId="runtime-failure")
            )
        self.assertEqual(status, 503, response)
        self.assertEqual(response["error"]["code"], "storage_runtime_failed")
        self.assertEqual(response["error"]["details"]["durableState"], "active_preserved")
        # The Active pointer never moved, the process keeps serving the
        # previous binding, and the candidate is not presented as published.
        self.assertEqual(self.configuration.active().revision_id, self.active.revision_id)
        self.assertEqual(self.api._runtime_binding.snapshot_id, self.active.revision_id)
        self.assertIsNone(self.storage_of("runtime-failure"))

    def test_partial_management_authority_cannot_publish_a_successor(self) -> None:
        # Both management AND activation authority are required: a principal
        # holding only one of them is refused before any successor is created.
        for index, permissions in enumerate(
            (
                frozenset({ApiPermission.READ, ApiPermission.MANAGE_CONFIGURATION}),
                frozenset({ApiPermission.READ, ApiPermission.ACTIVATE_CONFIGURATION}),
            )
        ):
            principal = ResolvedApiPrincipal(
                f"limited-{index}", f"limited-token-{index}", permissions
            )
            limited_api = MediaFlowApi(
                self.runtime_repository,
                None,
                principals=(principal, self.admin),
                configuration_service=self.configuration,
                storage_adapters=self.adapters,
                storage_browser_cursor_secret="storage-save-test-secret",
            )
            status, response = request(
                limited_api,
                SAVE_ROUTE,
                method="POST",
                token=f"limited-token-{index}",
                body=self.add_body(
                    storageId=f"limited-{index}", rootPath=str(self.root / "source")
                ),
            )
            self.assertEqual(status, 403, response)
            self.assertEqual(response["error"]["code"], "forbidden")
            self.assertIsNone(self.storage_of(f"limited-{index}"))
            status, response = request(
                limited_api,
                f"{SAVE_ROUTE}/media-target",
                method="PUT",
                token=f"limited-token-{index}",
                body=edit_body(
                    self.form_identity("media-target"),
                    "media-target",
                    storageId="media-target",
                    rootPath=str(self.root / "target"),
                ),
            )
            self.assertEqual(status, 403, response)
        self.assertEqual(self.configuration.active().revision_id, self.active.revision_id)

    def test_known_failure_then_explicit_retry_publishes_once(self) -> None:
        self.source.fail = True
        status, response = request(
            self.api, SAVE_ROUTE, method="POST", body=self.add_body(storageId="retry-storage")
        )
        self.assertEqual(status, 409, response)
        self.assertEqual(self.configuration.active().revision_id, self.active.revision_id)

        # The operator repairs the named condition and submits explicitly again.
        self.source.fail = False
        status, response = request(
            self.api, SAVE_ROUTE, method="POST", body=self.add_body(storageId="retry-storage")
        )
        self.assertEqual(status, 200, response)
        self.assertIsNotNone(self.storage_of("retry-storage"))
        self.assertNotEqual(self.configuration.active().revision_id, self.active.revision_id)
        # The refreshed list and the browse authority both consume the successor.
        _status, inventory = request(self.api, INVENTORY_ROUTE)
        self.assertIn("retry-storage", {item["id"] for item in inventory["items"]})
        self.assertEqual(self.source.mutations, [])
        self.assertEqual(self.target.mutations, [])

    def test_lifecycle_publications_use_sequence_for_followup_read_check(self) -> None:
        active = self.active_identity()
        command_identity = {
            "expectedRevisionId": active["revisionId"],
            "expectedVersion": active["revisionSequence"],
            "expectedDigest": self.configuration.active().digest,
        }
        status, copied = request(
            self.api,
            f"{SAVE_ROUTE}/source-storage/copy",
            method="POST",
            body={
                **command_identity,
                "newStorageId": "lifecycle-copy",
                "name": "Lifecycle Copy",
            },
        )
        self.assertEqual(status, 200, copied)
        self.assertIsNotNone(self.storage_of("lifecycle-copy"))

        for action, enabled in (("disable", False), ("enable", True)):
            current = self.configuration.active()
            status, changed = request(
                self.api,
                f"{SAVE_ROUTE}/lifecycle-copy/{action}",
                method="POST",
                body={
                    "enabled": enabled,
                    "expectedRevisionId": current.revision_id,
                    "expectedVersion": current.revision_sequence,
                    "expectedDigest": current.digest,
                },
            )
            self.assertEqual(status, 200, changed)
            self.assertEqual(self.storage_of("lifecycle-copy")["enabled"], enabled)

        current = self.configuration.active()
        status, removed = request(
            self.api,
            f"{SAVE_ROUTE}/lifecycle-copy",
            method="DELETE",
            body={
                "expectedRevisionId": current.revision_id,
                "expectedVersion": current.revision_sequence,
                "expectedDigest": current.digest,
            },
        )
        self.assertEqual(status, 200, removed)
        self.assertIsNone(self.storage_of("lifecycle-copy"))

        active = self.active_identity()
        self.assertNotEqual(active["revisionSequence"], active["version"])
        status, evidence = request(
            self.api,
            "/api/v1/operations/storage-management/storage/source-storage/check",
            method="POST",
            body={
                "expectedRevisionId": active["revisionId"],
                "expectedVersion": active["revisionSequence"],
            },
        )
        self.assertEqual(status, 200, evidence)
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(self.source.mutations, [])
        self.assertEqual(self.target.mutations, [])

    def test_remove_rejects_authority_captured_before_concurrent_edit(self) -> None:
        status, created = request(
            self.api,
            SAVE_ROUTE,
            method="POST",
            body=self.add_body(storageId="stale-remove", name="Spare Original"),
        )
        self.assertEqual(status, 200, created)
        stale = self.configuration.active()

        status, edited = request(
            self.api,
            f"{SAVE_ROUTE}/stale-remove",
            method="PUT",
            body=edit_body(
                self.form_identity("stale-remove"),
                "stale-remove",
                name="Spare Changed After Decision",
                rootPath=str(self.root / "source"),
            ),
        )
        self.assertEqual(status, 200, edited)

        status, rejected = request(
            self.api,
            f"{SAVE_ROUTE}/stale-remove",
            method="DELETE",
            body={
                "expectedRevisionId": stale.revision_id,
                "expectedVersion": stale.revision_sequence,
                "expectedDigest": stale.digest,
            },
        )
        self.assertEqual(status, 409, rejected)
        self.assertEqual(rejected["error"]["code"], "storage_remove_stale")
        self.assertEqual(self.storage_of("stale-remove")["name"], "Spare Changed After Decision")
        self.assertEqual(self.source.mutations, [])
        self.assertEqual(self.target.mutations, [])

    def test_add_captures_open_time_authority_and_rejects_stale_or_missing_identity(self):
        reads_before = list(self.source.read_calls)
        status, authority = request(self.api, SAVE_ROUTE)
        self.assertEqual(status, 200, authority)
        self.assertEqual(authority["active"]["revisionId"], self.active.revision_id)
        self.assertEqual(self.source.read_calls, reads_before)
        stale = self.add_body(storageId="stale-add")
        winner = self.add_body(storageId="winner")
        status, result = request(self.api, SAVE_ROUTE, method="POST", body=winner)
        self.assertEqual(status, 200, result)
        active = self.configuration.active()
        count = len(self.configuration_repository.list_revisions())
        status, rejected = request(self.api, SAVE_ROUTE, method="POST", body=stale)
        self.assertEqual(status, 409, rejected)
        self.assertEqual(rejected["error"]["code"], "configuration_version_conflict")
        self.assertEqual(len(self.configuration_repository.list_revisions()), count)
        self.assertEqual(self.configuration.active().revision_id, active.revision_id)
        del stale["expectedDigest"]
        status, rejected = request(self.api, SAVE_ROUTE, method="POST", body=stale)
        self.assertEqual(status, 400, rejected)
        with self.assertRaises(ConfigurationVersionConflict):
            self.objects.save_storage(
                app_body(rootPath=str(self.root / "source")), actor="operator"
            )

    def test_unreferenced_add_requires_read_check_and_preserves_physical_contents(self):
        marker = self.root / "source" / "keep.mkv"
        marker.write_bytes(b"unchanged media")
        cases = [
            self.add_body(rootPath=str(self.root / "missing-mount")),
            self.add_body(
                type="smb",
                rootPath="media",
                options={
                    "host": "nas.invalid",
                    "share": "media",
                    "usernameEnv": "SMB_USER",
                    "passwordEnv": "MF_MISSING_STORAGE_SECRET",
                },
            ),
        ]
        for candidate in cases:
            with self.subTest(provider=candidate["type"]):
                status, rejected = request(self.api, SAVE_ROUTE, method="POST", body=candidate)
                self.assertEqual(status, 409, rejected)
                self.assertEqual(rejected["error"]["code"], "storage_storage_check_failed")
                self.assertEqual(self.configuration.active().revision_id, self.active.revision_id)
                self.assertEqual(marker.read_bytes(), b"unchanged media")
                self.assertIsNone(self.storage_of(candidate["storageId"]))
        self.assertFalse((self.root / "missing-mount").exists())

    def test_edit_rejects_null_unsupported_option(self):
        status, rejected = request(
            self.api,
            f"{SAVE_ROUTE}/source-storage",
            method="PUT",
            body=edit_body(
                self.form_identity("source-storage"),
                "source-storage",
                rootPath=str(self.root / "source"),
                options={"password": None},
            ),
        )
        self.assertEqual(status, 400, rejected)
        self.assertEqual(self.configuration.active().revision_id, self.active.revision_id)

    def test_storage_save_command_is_stale_safe_at_application_boundary(self) -> None:
        stale_revision = self.configuration.active()
        saved = self.objects.save_storage(
            app_body(
                id="app-boundary",
                name="App Boundary",
                rootPath=str(self.root / "source"),
            ),
            actor="operator",
            expected_revision_id=stale_revision.revision_id,
            expected_version=stale_revision.revision_sequence,
            expected_digest=stale_revision.digest,
        )
        self.assertEqual(saved.revision_id, self.configuration.active().revision_id)
        with self.assertRaises(ConfigurationVersionConflict):
            self.objects.save_storage(
                app_body(
                    id="app-boundary",
                    name="App Boundary Stale",
                    rootPath=str(self.root / "source"),
                ),
                actor="operator",
                edit=True,
                expected_revision_id=stale_revision.revision_id,
                expected_version=stale_revision.revision_sequence,
                expected_digest=stale_revision.digest,
            )
        self.assertEqual(self.storage_of("app-boundary")["name"], "App Boundary")
        with self.assertRaises(ValueError):
            self.objects.save_storage({"id": "x", "name": "X"}, actor="operator")
        with self.assertRaises(ValueError):
            self.objects.save_storage(
                app_body(notes="Storage has no notes field"), actor="operator"
            )


if __name__ == "__main__":
    unittest.main()
