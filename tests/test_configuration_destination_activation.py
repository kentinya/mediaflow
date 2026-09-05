from __future__ import annotations

import copy
import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application import configuration_objects as configuration_objects_module
from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
    DestinationPrecheckEvidence,
    RecognitionStrategyTestEvidence,
    StorageSetupCheckEvidence,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageCapabilities, StorageEntry, StorageEntryType
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_configuration_management import (
    CONFIGURATION_SCHEMA_VERSION,
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION as RUNTIME_SCHEMA_VERSION
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request


class RemoteDestinationFake:
    """Fake remote adapter proving the setup evidence path stays read-only."""

    def __init__(self, storage_id: str = "media-target", *, read_only: bool = False):
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = read_only
        self.capabilities = (
            StorageCapabilities()
            if read_only
            else StorageCapabilities(can_move=True, can_copy=True, can_delete=True)
        )
        self.existing_directories = {"Movies"}
        self.mutations: list[str] = []

    def exists(self, path: str) -> bool:
        return path == "" or path in self.existing_directories

    def stat(self, path: str) -> StorageEntry:
        if path == "" or path in self.existing_directories:
            return StorageEntry(path, path, StorageEntryType.DIRECTORY, 0, datetime.now(UTC))
        raise FileNotFoundError(path)

    def list(self, path: str):
        return ()

    def write(self, *args, **kwargs):
        self.mutations.append("write")
        raise AssertionError("setup evidence must not write")

    def create_directory(self, path):
        self.mutations.append("create_directory")
        raise AssertionError("setup evidence must not create directories")

    def move(self, *args, **kwargs):
        self.mutations.append("move")
        raise AssertionError("setup evidence must not move")

    def copy(self, *args, **kwargs):
        self.mutations.append("copy")
        raise AssertionError("setup evidence must not copy")

    def delete(self, path):
        self.mutations.append("delete")
        raise AssertionError("setup evidence must not delete")

    def hard_link(self, *args, **kwargs):
        self.mutations.append("hard_link")
        raise AssertionError("setup evidence must not hard-link")

    def soft_link(self, *args, **kwargs):
        self.mutations.append("soft_link")
        raise AssertionError("setup evidence must not soft-link")


class DestinationPrecheckActivationTests(unittest.TestCase):
    @staticmethod
    def _document(root: Path) -> dict:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        return document

    @staticmethod
    def _validated(managed: ManagedConfigurationService, document: dict):
        draft = managed.import_draft(document, actor="operator")
        validated = managed.validate(draft.revision_id, actor="operator")
        if validated.status.value != "validated":
            raise AssertionError("test document did not validate")
        return validated

    @staticmethod
    def _save_strategy_test(repository, revision) -> None:
        now = datetime.now(UTC)
        repository.save_recognition_strategy_test(
            RecognitionStrategyTestEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationStrategyTestStatus.COMPLETED,
                now,
                "operator",
                "source",
                "Example.Movie.2024.mkv",
                {"outcome": "matched"},
            )
        )

    @staticmethod
    def _save_storage_check(
        repository,
        revision,
        storage_id: str,
        *,
        storage_type: str = "local",
        status: ConfigurationStorageCheckStatus = ConfigurationStorageCheckStatus.PASSED,
        version: int | None = None,
        digest: str | None = None,
        failure_category: str | None = None,
        secret_readiness: tuple[dict[str, str], ...] = (),
    ) -> StorageSetupCheckEvidence:
        failed = status is ConfigurationStorageCheckStatus.FAILED
        evidence = StorageSetupCheckEvidence(
            revision.revision_id,
            revision.version if version is None else version,
            revision.digest if digest is None else digest,
            status,
            datetime.now(UTC),
            "operator",
            storage_id,
            storage_type,
            False,
            {key: False for key in StorageSetupCheckEvidence.CAPABILITY_FIELDS},
            secret_readiness=secret_readiness,
            failure_category=failure_category if failed else None,
            message="bounded Storage check failure" if failed else None,
            next_action=(
                "correct the Storage, rerun its read-only check, then activate checked"
                if failed
                else None
            ),
        )
        return repository.save_storage_setup_check(evidence)

    @classmethod
    def _save_storage_checks(cls, repository, revision) -> None:
        storages = {
            str(item.get("id")): item
            for item in revision.document.get("storages", [])
            if isinstance(item, dict)
        }
        referenced: list[str] = []
        for section in ("resourceLibraries", "mediaLibraries"):
            for library in revision.document.get(section, []) or []:
                storage_id = str(library.get("storageId", ""))
                if storage_id and storage_id not in referenced:
                    referenced.append(storage_id)
        for storage_id in referenced:
            storage = storages.get(storage_id, {})
            if storage.get("enabled", True) is False:
                continue
            cls._save_storage_check(
                repository,
                revision,
                storage_id,
                storage_type=str(storage.get("type", "local")).lower() or "local",
                secret_readiness=tuple(
                    dict(entry)
                    for entry in ConfigurationObjectService._storage_secret_readiness(
                        str(storage.get("type", "local")).lower() or "local",
                        ConfigurationObjectService._storage_options(storage),
                    )
                ),
            )

    @classmethod
    def _save_existing_gates(cls, repository, revision) -> None:
        cls._save_storage_checks(repository, revision)
        cls._save_strategy_test(repository, revision)

    @staticmethod
    def _save_precheck(
        repository,
        revision,
        *,
        status: ConfigurationDestinationPrecheckStatus = (
            ConfigurationDestinationPrecheckStatus.COMPLETED
        ),
        verdict: str = "ready",
        failure_category: str | None = None,
        next_action: str | None = None,
    ) -> DestinationPrecheckEvidence:
        evidence = DestinationPrecheckEvidence(
            revision.revision_id,
            revision.version,
            revision.digest,
            status,
            datetime.now(UTC),
            "operator",
            "C",
            {"mode": "synthetic"},
            {"verdict": verdict}
            if status is ConfigurationDestinationPrecheckStatus.COMPLETED
            else None,
            failure_category,
            "bounded destination precheck result",
            next_action,
        )
        return repository.save_destination_precheck(evidence)

    @staticmethod
    def _assert_runtime_empty(database: Path) -> None:
        with sqlite3.connect(database) as connection:
            for table in (
                "tasks",
                "task_items",
                "task_results",
                "conflict_confirmations",
                "metadata_corrections",
                "recognition_reviews",
                "metadata_reviews",
                "classification_reviews",
                "automation_jobs",
                "execution_authorizations",
            ):
                count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if count != 0:
                    raise AssertionError(f"activation created a row in {table}")

    @staticmethod
    def _run_remote_precheck(objects, revision, fake):
        def fake_create(_self, external=None, storage_ids=None):
            return {"media-target": fake}

        with patch.object(RuntimeConfiguration, "create_storages", fake_create):
            return objects.destination_precheck(
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

    def test_checked_activation_requires_current_per_storage_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                revision = self._validated(managed, self._document(root))
                self._save_storage_check(repository, revision, "media-target")
                with self.assertRaisesRegex(
                    ConfigurationActivationConflict,
                    "read-only Storage check for 'source-storage' is required",
                ):
                    objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                self.assertIsNone(managed.active())
                self._save_storage_check(repository, revision, "source-storage", digest="0" * 64)
                with self.assertRaisesRegex(
                    ConfigurationActivationConflict,
                    "check for 'source-storage' is stale",
                ):
                    objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                self.assertIsNone(managed.active())
                self._save_storage_check(repository, revision, "source-storage")
                self._save_storage_check(
                    repository,
                    revision,
                    "media-target",
                    status=ConfigurationStorageCheckStatus.FAILED,
                    failure_category="not_found",
                )
                with self.assertRaisesRegex(
                    ConfigurationActivationConflict,
                    "'media-target' failed with category not_found",
                ):
                    objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                self.assertIsNone(managed.active())
                self._save_storage_check(repository, revision, "media-target")
                self._save_strategy_test(repository, revision)
                self._save_precheck(repository, revision)
                activated = objects.activate_checked(
                    revision.revision_id,
                    expected_version=revision.version,
                    actor="operator",
                )
                self.assertEqual(activated.status.value, "active")

    def test_provider_neutral_storage_checks_and_remote_destination_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            document = self._document(root)
            document["storages"][1] = {
                "id": "media-target",
                "name": "Remote media",
                "type": "openlist",
                "rootPath": "remote-media",
                "baseUrl": "http://127.0.0.1:1",
                "tokenEnv": "MEDIAFLOW_TEST_OPENLIST_TOKEN",
                "enabled": True,
            }
            runtime_database = root / "runtime.sqlite3"
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(runtime_database) as runtime_repository,
            ):
                managed = ManagedConfigurationService(repository)
                fake = RemoteDestinationFake()
                objects = ConfigurationObjectService(
                    managed,
                    storage_adapters={
                        "source-storage": LocalStorage("source-storage", root / "source"),
                        "media-target": fake,
                    },
                )
                revision = self._validated(managed, document)
                with patch.dict(os.environ, {"MEDIAFLOW_TEST_OPENLIST_TOKEN": "test-token"}):
                    for storage_id, storage_type in (
                        ("source-storage", "local"),
                        ("media-target", "openlist"),
                    ):
                        evidence = objects.storage_check(
                            revision.revision_id,
                            storage_id=storage_id,
                            expected_version=revision.version,
                            expected_digest=revision.digest,
                            actor="operator",
                        )
                        self.assertEqual(
                            evidence.status,
                            ConfigurationStorageCheckStatus.PASSED,
                        )
                    destination_evidence = self._run_remote_precheck(objects, revision, fake)
                    self.assertEqual(destination_evidence.status.value, "completed")
                    self.assertEqual(destination_evidence.result["verdict"], "ready")
                    self.assertEqual(fake.mutations, [])
                    self._save_strategy_test(repository, revision)
                    activated = objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                self.assertEqual(activated.status.value, "active")
                self._assert_runtime_empty(runtime_database)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=managed,
                    bootstrap_document=document,
                )
                status, created = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body={"command": "preview"},
                )
                self.assertEqual(status, 202)
                stored = runtime_repository.get_job(created["job_id"])
                self.assertIsNotNone(stored)
                self.assertEqual(stored.configuration_revision_id, activated.revision_id)
                self.assertEqual(stored.configuration_revision_digest, activated.digest)

    def test_set_to_unset_credential_readiness_blocks_checked_activation_through_api(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            document = self._document(root)
            document["storages"][1] = {
                "id": "media-target",
                "name": "Remote media",
                "type": "openlist",
                "rootPath": "remote-media",
                "baseUrl": "http://127.0.0.1:1",
                "tokenEnv": "MEDIAFLOW_TEST_OPENLIST_TOKEN",
                "enabled": True,
            }
            runtime_database = root / "runtime.sqlite3"
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(runtime_database) as runtime_repository,
            ):
                managed = ManagedConfigurationService(repository)
                fake = RemoteDestinationFake()
                adapters = {
                    "source-storage": LocalStorage("source-storage", root / "source"),
                    "media-target": fake,
                }
                objects = ConfigurationObjectService(managed, storage_adapters=adapters)

                def run_evidence_gates(revision) -> None:
                    with patch.dict(
                        os.environ,
                        {"MEDIAFLOW_TEST_OPENLIST_TOKEN": "unit-token"},
                    ):
                        for storage_id in ("source-storage", "media-target"):
                            evidence = objects.storage_check(
                                revision.revision_id,
                                storage_id=storage_id,
                                expected_version=revision.version,
                                expected_digest=revision.digest,
                                actor="operator",
                            )
                            self.assertEqual(
                                evidence.status,
                                ConfigurationStorageCheckStatus.PASSED,
                            )
                        destination = self._run_remote_precheck(objects, revision, fake)
                        self.assertEqual(destination.result["verdict"], "ready")
                        self._save_strategy_test(repository, revision)
                        self._save_precheck(repository, revision)

                first = self._validated(managed, document)
                run_evidence_gates(first)
                with patch.dict(
                    os.environ,
                    {"MEDIAFLOW_TEST_OPENLIST_TOKEN": "unit-token"},
                ):
                    activated = objects.activate_checked(
                        first.revision_id,
                        expected_version=first.version,
                        actor="operator",
                    )
                self.assertEqual(activated.status.value, "active")
                self.assertEqual(activated.revision_id, managed.active().revision_id)

                second = self._validated(managed, document)
                run_evidence_gates(second)
                principal = ResolvedApiPrincipal(
                    "admin",
                    "admin-token",
                    frozenset(ApiPermission),
                )
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=managed,
                    storage_adapters=adapters,
                    bootstrap_document=document,
                )
                evidence_before = repository.get_storage_setup_check(
                    second.revision_id, "media-target"
                )
                endpoint = f"/api/v1/configuration/revisions/{second.revision_id}/activate"
                with patch.dict(
                    os.environ,
                    {"MEDIAFLOW_TEST_OPENLIST_TOKEN": ""},
                ):
                    status, blocked = request(
                        api,
                        endpoint,
                        method="POST",
                        body={"expectedVersion": second.version, "checked": True},
                    )
                self.assertEqual(status, 409)
                self.assertEqual(blocked["error"]["code"], "configuration_conflict")
                self.assertIn("media-target", blocked["error"]["message"])
                self.assertIn("secret readiness", blocked["error"]["message"])
                self.assertIn("unchanged", blocked["error"]["message"])
                self.assertIn("rerun", blocked["error"]["details"]["nextAction"])
                self.assertLessEqual(len(blocked["error"]["message"]), 384)
                self.assertNotIn("unit-token", repr(blocked))
                self.assertEqual(managed.active().revision_id, activated.revision_id)
                self.assertEqual(managed.require(second.revision_id).status.value, "validated")
                self.assertEqual(
                    repository.get_storage_setup_check(second.revision_id, "media-target"),
                    evidence_before,
                )
                self.assertEqual(fake.mutations, [])

    def _assert_activation_module_namespace_is_hardened(self, namespace) -> None:
        for name in (
            "OrganizerExecutor",
            "MetadataProviderRegistry",
            "OrganizePlanner",
        ):
            self.assertNotIn(name, namespace)

    def test_missing_stale_failed_and_capability_gap_refuse_without_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                first = self._validated(managed, document)
                previous_active = managed.activate(
                    first.revision_id, expected_version=first.version, actor="operator"
                )
                candidate = self._validated(managed, document)
                self._save_existing_gates(repository, candidate)
                before_audits = repository.list_revision_audits(candidate.revision_id)
                local_before = repository.get_local_setup_check(candidate.revision_id)
                strategy_before = repository.get_recognition_strategy_test(candidate.revision_id)

                with self.assertRaises(ConfigurationActivationConflict) as caught:
                    objects.activate_checked(
                        candidate.revision_id,
                        expected_version=candidate.version,
                        actor="operator",
                    )
                self.assertIn("current read-only destination precheck", str(caught.exception))
                self.assertIn(
                    "run the read-only destination precheck", caught.exception.next_action
                )
                self.assertEqual(managed.active().revision_id, previous_active.revision_id)
                self.assertEqual(managed.require(candidate.revision_id).status.value, "validated")
                self.assertEqual(
                    repository.get_local_setup_check(candidate.revision_id), local_before
                )
                self.assertEqual(
                    repository.get_recognition_strategy_test(candidate.revision_id), strategy_before
                )
                self.assertEqual(
                    repository.list_revision_audits(candidate.revision_id), before_audits
                )

                self._save_precheck(repository, candidate)
                changed_document = copy.deepcopy(candidate.document)
                changed_document["namingPolicies"][0]["description"] = "changed"
                edited = managed.edit_draft(
                    candidate.revision_id,
                    changed_document,
                    expected_version=candidate.version,
                    actor="operator",
                )
                revalidated = managed.validate(edited.revision_id, actor="operator")
                self._save_existing_gates(repository, revalidated)
                stale = repository.get_destination_precheck(revalidated.revision_id)
                with self.assertRaisesRegex(
                    ConfigurationActivationConflict, "Destination precheck is stale"
                ) as caught:
                    objects.activate_checked(
                        revalidated.revision_id,
                        expected_version=revalidated.version,
                        actor="operator",
                    )
                self.assertIn("reload this revision", caught.exception.next_action)
                self.assertEqual(
                    repository.get_destination_precheck(revalidated.revision_id), stale
                )
                self.assertEqual(managed.active().revision_id, previous_active.revision_id)

        for status, verdict, category, expected in (
            (
                ConfigurationDestinationPrecheckStatus.FAILED,
                "ready",
                "permission_denied",
                "permission_denied",
            ),
            (
                ConfigurationDestinationPrecheckStatus.FAILED,
                "ready",
                "duplicate_destination",
                "duplicate_destination",
            ),
            (
                ConfigurationDestinationPrecheckStatus.FAILED,
                "ready",
                "multiple_destination_storages",
                "multiple_destination_storages",
            ),
            (
                ConfigurationDestinationPrecheckStatus.COMPLETED,
                "capability_gap",
                None,
                "capability_gap",
            ),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    managed = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(managed)
                    revision = self._validated(managed, self._document(root))
                    self._save_existing_gates(repository, revision)
                    evidence = self._save_precheck(
                        repository,
                        revision,
                        status=status,
                        verdict=verdict,
                        failure_category=category,
                        next_action="correct the destination and rerun the precheck",
                    )
                    with self.assertRaisesRegex(
                        ConfigurationActivationConflict, expected
                    ) as caught:
                        objects.activate_checked(
                            revision.revision_id,
                            expected_version=revision.version,
                            actor="operator",
                        )
                    expected_action = (
                        evidence.next_action
                        if status is ConfigurationDestinationPrecheckStatus.FAILED
                        else (
                            "change the configured operation or destination Storage, "
                            "then rerun the precheck"
                        )
                    )
                    self.assertEqual(caught.exception.next_action, expected_action)
                    self.assertIsNone(managed.active())
                    self.assertEqual(
                        repository.get_destination_precheck(revision.revision_id), evidence
                    )

    def test_previous_build_evidence_without_multi_sample_keys_still_activates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                revision = self._validated(managed, self._document(root))
                self._save_existing_gates(repository, revision)
                evidence = self._save_precheck(repository, revision)
                self.assertNotIn("sampleCount", evidence.result)
                self.assertNotIn("items", evidence.result)
                self.assertNotIn("collisions", evidence.result)
                activated = objects.activate_checked(
                    revision.revision_id,
                    expected_version=revision.version,
                    actor="operator",
                )
                self.assertEqual(activated.status.value, "active")

    def test_current_completed_outcomes_activate_and_remote_requires_precheck(self) -> None:
        for verdict in (
            "ready",
            "skip",
            "rename",
            "overwrite_requires_confirmation",
            "manual_confirmation_required",
        ):
            with self.subTest(verdict=verdict), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    managed = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(managed)
                    revision = self._validated(managed, self._document(root))
                    self._save_existing_gates(repository, revision)
                    self._save_precheck(repository, revision, verdict=verdict)
                    activated = objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                    self.assertEqual(activated.status.value, "active")

        for mode in ("remote_only", "no_media_library"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = self._document(root)
                if mode == "remote_only":
                    document["storages"].append(
                        {
                            "id": "remote",
                            "name": "Remote",
                            "type": "openlist",
                            "rootPath": "/",
                            "baseUrl": "https://example.invalid",
                            "tokenEnv": "OPENLIST_TOKEN",
                        }
                    )
                    document["mediaLibraries"] = [
                        {
                            "id": "remote-media",
                            "name": "Remote",
                            "storageId": "remote",
                            "rootPath": "Media",
                        }
                    ]
                    for policy in document["classificationPolicies"]:
                        for rule in policy["rules"]:
                            rule["result"]["mediaLibraryId"] = "remote-media"
                else:
                    document["mediaLibraries"] = []
                    for policy in document["classificationPolicies"]:
                        policy["rules"] = []
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    managed = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(managed)
                    revision = self._validated(managed, document)
                    if mode == "remote_only":
                        with patch.dict(os.environ, {"OPENLIST_TOKEN": "unit-token"}):
                            self._save_existing_gates(repository, revision)
                            with self.assertRaisesRegex(
                                ConfigurationActivationConflict,
                                "current read-only destination precheck",
                            ):
                                objects.activate_checked(
                                    revision.revision_id,
                                    expected_version=revision.version,
                                    actor="operator",
                                )
                            self.assertIsNone(managed.active())
                            self._save_precheck(repository, revision)
                    else:
                        self._save_existing_gates(repository, revision)
                        objects.require_current_destination_precheck(revision)
                    with patch.dict(os.environ, {"OPENLIST_TOKEN": "unit-token"}):
                        activated = objects.activate_checked(
                            revision.revision_id,
                            expected_version=revision.version,
                            actor="operator",
                        )
                    self.assertEqual(activated.status.value, "active")
                    if mode == "remote_only":
                        self.assertIsNotNone(
                            repository.get_destination_precheck(revision.revision_id)
                        )
                    else:
                        self.assertIsNone(repository.get_destination_precheck(revision.revision_id))

    def test_omitted_media_libraries_is_not_applicable_for_checked_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                revision = self._validated(managed, self._document(root))
                self._save_existing_gates(repository, revision)
                missing_section = replace(
                    revision,
                    document={
                        key: value
                        for key, value in revision.document.items()
                        if key != "mediaLibraries"
                    },
                )
                objects.require_current_destination_precheck(missing_section)
                with (
                    patch.object(managed, "require", return_value=missing_section),
                    patch.object(managed, "activate", return_value=revision) as activate,
                ):
                    activated = objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                self.assertIs(activated, revision)
                activate.assert_called_once_with(
                    revision.revision_id,
                    expected_version=revision.version,
                    actor="operator",
                )

    def test_activation_module_namespace_stays_free_of_construction_classes(self) -> None:
        namespace = vars(configuration_objects_module)
        self._assert_activation_module_namespace_is_hardened(namespace)
        self.assertIs(
            configuration_objects_module.MetadataProviderRegistry,
            MetadataProviderRegistry,
        )
        with patch(
            "mediaflow.application.metadata.MetadataProviderRegistry",
            side_effect=AssertionError("activation constructed Provider"),
        ) as definition_site:
            self.assertIs(
                configuration_objects_module.MetadataProviderRegistry,
                definition_site,
            )
            self.assertNotIn("MetadataProviderRegistry", vars(configuration_objects_module))

        probe = dict(namespace)
        exec("from mediaflow.application.organizer import OrganizerExecutor", probe)
        with self.assertRaisesRegex(AssertionError, "OrganizerExecutor"):
            self._assert_activation_module_namespace_is_hardened(probe)

    def test_requirement_order_unchecked_activation_and_zero_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_database = root / "runtime.sqlite3"
            with SQLiteTaskRepository(runtime_database):
                pass
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                revision = self._validated(managed, self._document(root))
                with self.assertRaisesRegex(
                    ConfigurationActivationConflict, "read-only Storage check"
                ):
                    objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                self._save_storage_checks(repository, revision)
                with self.assertRaisesRegex(
                    ConfigurationActivationConflict, "completed Recognition Strategy Test"
                ):
                    objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                self._save_strategy_test(repository, revision)
                unchecked = managed.activate(
                    revision.revision_id,
                    expected_version=revision.version,
                    actor="operator",
                )
                self.assertEqual(unchecked.status.value, "active")

            with SQLiteConfigurationRepository(root / "second.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                document = self._document(root)
                document["persistence"]["databasePath"] = str(root / "second.sqlite3")
                revision = self._validated(managed, document)
                self._save_storage_checks(repository, revision)
                self._save_strategy_test(repository, revision)
                with (
                    patch(
                        "mediaflow.application.configuration_objects.MetadataProviderRegistry",
                        side_effect=AssertionError("activation constructed Provider"),
                    ),
                    patch(
                        "mediaflow.application.organizer.OrganizerExecutor",
                        side_effect=AssertionError("activation constructed Executor"),
                    ),
                    patch(
                        "mediaflow.application.organizer.OrganizePlanner.plan",
                        side_effect=AssertionError("activation constructed Planner"),
                    ),
                    patch.object(
                        RuntimeConfiguration,
                        "create_storages",
                        side_effect=AssertionError("activation constructed Storage"),
                    ),
                ):
                    with self.assertRaisesRegex(
                        ConfigurationActivationConflict, "destination precheck"
                    ):
                        objects.activate_checked(
                            revision.revision_id,
                            expected_version=revision.version,
                            actor="operator",
                        )
                    self._save_precheck(repository, revision)
                    activated = objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                self.assertEqual(activated.status.value, "active")
                self._assert_runtime_empty(runtime_database)
                self.assertEqual(CONFIGURATION_SCHEMA_VERSION, 10)
                self.assertEqual(RUNTIME_SCHEMA_VERSION, 33)

    def test_api_blocked_and_satisfied_use_existing_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                managed = ManagedConfigurationService(repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                limited = ResolvedApiPrincipal(
                    "manager",
                    "manager-token",
                    frozenset({ApiPermission.MANAGE_CONFIGURATION}),
                )
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal, limited),
                    configuration_service=managed,
                    bootstrap_document=document,
                )
                revision = self._validated(managed, document)
                self._save_existing_gates(repository, revision)
                endpoint = f"/api/v1/configuration/revisions/{revision.revision_id}/activate"
                for checked in (False, True):
                    denied_status, denied = request(
                        api,
                        endpoint,
                        method="POST",
                        token="manager-token",
                        body={"expectedVersion": revision.version, "checked": checked},
                    )
                    self.assertEqual(denied_status, 403)
                    self.assertEqual(denied["error"]["code"], "forbidden")
                status, blocked = request(
                    api,
                    endpoint,
                    method="POST",
                    body={"expectedVersion": revision.version, "checked": True},
                )
                self.assertEqual(status, 409)
                self.assertEqual(blocked["error"]["code"], "configuration_conflict")
                self.assertIn("current read-only destination precheck", blocked["error"]["message"])
                self.assertIn(
                    "run the read-only destination precheck",
                    blocked["error"]["details"]["nextAction"],
                )
                self.assertLessEqual(len(blocked["error"]["message"]), 384)
                self.assertNotIn(str(root), repr(blocked))
                self._assert_runtime_empty(root / "runtime.sqlite3")
                self._save_precheck(repository, revision)
                status, active = request(
                    api,
                    endpoint,
                    method="POST",
                    body={"expectedVersion": revision.version, "checked": True},
                )
                self.assertEqual(status, 200)
                self.assertEqual(active["status"], "active")
                self.assertEqual(set(active), set(revision.summary()))
                self._assert_runtime_empty(root / "runtime.sqlite3")


if __name__ == "__main__":
    unittest.main()
