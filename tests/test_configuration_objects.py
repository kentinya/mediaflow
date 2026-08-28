from __future__ import annotations

import copy
import io
import json
import socket
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event, current_thread
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.read_only_storage import (
    ReadOnlyStorageGuard,
    ReadOnlyStorageMutationError,
)
from mediaflow.domain.configuration_management import (
    CONFIGURATION_SETUP_CHECK_PATH_LIMIT,
    CONFIGURATION_STRATEGY_RESULT_LIMIT,
    ConfigurationActivationConflict,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationSetupCheckStatus,
    ConfigurationVersionConflict,
)
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaIdentity,
    MediaType,
    MetadataError,
    MetadataErrorCode,
    ProviderCapabilities,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.metadata_provider_bootstrap import (
    LazyMetadataProviderRegistryFactory,
    MetadataProviderBootstrapError,
    metadata_provider_registry_from_environment,
)
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


class FakeLiveMetadataProvider:
    provider_id = "tmdb"
    capabilities = ProviderCapabilities(can_search_movie=True)

    def __init__(
        self,
        candidates=(),
        *,
        error=None,
        details_error=None,
        details_barrier: Barrier | None = None,
        search_barrier: Barrier | None = None,
    ) -> None:
        self.candidates = tuple(candidates)
        self.error = error
        self.details_error = details_error
        self.details_barrier = details_barrier
        self.search_barrier = search_barrier
        self.searches = 0
        self.details = 0
        self.search_queries: list[object] = []
        self.detail_ids: list[str] = []

    def search_movie(self, query, policy=None, *, force_refresh=False):
        self.searches += 1
        self.search_queries.append(query)
        if self.search_barrier is not None:
            self.search_barrier.wait(timeout=5)
        if self.error:
            raise self.error
        return self.candidates

    def get_movie(self, provider_id, policy=None, *, force_refresh=False):
        self.details += 1
        self.detail_ids.append(provider_id)
        if self.details_barrier is not None:
            self.details_barrier.wait(timeout=5)
        if self.details_error:
            raise self.details_error
        candidate = next(item for item in self.candidates if item.provider_id == provider_id)
        return MediaIdentity(
            self.provider_id,
            provider_id,
            MediaType.MOVIE,
            candidate.title,
            candidate.original_title,
            candidate.year,
        )


class LazyMetadataProviderRegistryFactoryTests(unittest.TestCase):
    def test_sequential_and_concurrent_first_use_publish_one_registry(self) -> None:
        provider = FakeLiveMetadataProvider()
        calls = []
        release = Event()

        def builder(provider_ids):
            calls.append(tuple(provider_ids))
            release.wait(1)
            return MetadataProviderRegistry((provider,))

        factory = LazyMetadataProviderRegistryFactory(builder)
        self.assertIsNotNone(factory(()))
        self.assertEqual(calls, [])
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(factory, ("tmdb",)) for _ in range(8)]
            release.set()
            registries = [future.result(timeout=2) for future in futures]
        self.assertEqual(calls, [("tmdb",)])
        self.assertTrue(all(registry is registries[0] for registry in registries))
        self.assertIs(factory(("tmdb",)), registries[0])

    def test_unsupported_id_fails_closed_after_initialization(self) -> None:
        provider = FakeLiveMetadataProvider()
        factory = LazyMetadataProviderRegistryFactory(
            lambda _ids: MetadataProviderRegistry((provider,))
        )
        factory(("tmdb",))
        with self.assertRaises(MetadataProviderBootstrapError) as caught:
            factory(("unknown",))
        self.assertEqual(caught.exception.category, "provider_not_configured")

    def test_failed_initialization_is_not_cached(self) -> None:
        provider = FakeLiveMetadataProvider()
        calls = 0

        def builder(_ids):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise MetadataProviderBootstrapError("missing_credential", "missing", "retry")
            return MetadataProviderRegistry((provider,))

        factory = LazyMetadataProviderRegistryFactory(builder)
        with self.assertRaises(MetadataProviderBootstrapError):
            factory(("tmdb",))
        self.assertIs(factory(("tmdb",)).resolve("tmdb"), provider)
        self.assertEqual(calls, 2)


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def request(
    api,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = "admin-token",
):
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


class ConfigurationObjectJourneyTests(unittest.TestCase):
    def _document(self, root: Path) -> dict:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        document["resourceLibraries"][0]["storagePath"] = "incoming"
        document["mediaLibraries"][0]["rootPath"] = "Movies"
        return document

    @staticmethod
    def _strategy_test(objects, revision):
        return objects.recognition_strategy_test(
            revision.revision_id,
            expected_version=revision.version,
            expected_digest=revision.digest,
            actor="tester",
            resource_library_id="source",
            synthetic_path="Example.Movie.2024.1080p.mkv",
        )

    @staticmethod
    def _destination_precheck(objects, revision):
        return objects.destination_precheck(
            revision.revision_id,
            expected_version=revision.version,
            expected_digest=revision.digest,
            actor="tester",
            recognition_type="C",
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )

    def test_revision_detail_uses_one_captured_revision_for_all_projections(self) -> None:
        document_v1 = {
            "storages": [{"id": "source", "type": "local", "rootPath": "/source"}],
            "resourceLibraries": [],
            "mediaLibraries": [],
            "recognitionRules": [],
            "recognitionTypes": [],
            "recognitionTypePolicies": [],
            "metadataPolicies": [],
            "classificationPolicies": [],
        }
        document_v2 = copy.deepcopy(document_v1)
        document_v2["resourceLibraries"] = [
            {"id": "new-resource", "storageId": "source", "storagePath": "incoming"}
        ]
        document_v2["recognitionRules"] = [
            {
                "id": "new-rule",
                "condition": {"field": "resourceLibraryId", "value": "new-resource"},
            }
        ]
        setup_evidence = SimpleNamespace(
            revision_version=1,
            revision_digest="digest-v1",
            document=lambda: {"status": "passed"},
        )
        revision_v1 = SimpleNamespace(
            revision_id="revision",
            version=1,
            digest="digest-v1",
            document=document_v1,
            summary=lambda: {
                "revisionId": "revision",
                "version": 1,
                "digest": "digest-v1",
            },
        )
        revision_v2 = SimpleNamespace(
            revision_id="revision",
            version=2,
            digest="digest-v2",
            document=document_v2,
            summary=lambda: {
                "revisionId": "revision",
                "version": 2,
                "digest": "digest-v2",
            },
        )

        class SequentialManaged:
            repository = SimpleNamespace(
                get_local_setup_check=lambda _revision_id: setup_evidence,
                get_recognition_strategy_test=lambda _revision_id: None,
            )

            def __init__(self) -> None:
                self.reads = 0

            def require(self, _revision_id: str):
                self.reads += 1
                return revision_v1 if self.reads == 1 else revision_v2

        managed = SequentialManaged()
        objects = ConfigurationObjectService(managed)
        detail = objects.revision_detail("revision")
        self.assertEqual(managed.reads, 1)
        self.assertEqual(
            (detail["revisionId"], detail["version"], detail["digest"]),
            ("revision", 1, "digest-v1"),
        )
        self.assertEqual(len(detail["objects"]["resourceLibraries"]), 0)
        self.assertEqual(detail["references"]["storage:source"]["total"], 0)
        self.assertFalse(detail["localSetupCheck"]["stale"])
        managed.reads = 0
        self.assertEqual(objects.references("revision")["storage:source"]["total"], 0)
        self.assertEqual(managed.reads, 1)

    def test_guided_objects_preserve_document_and_block_referenced_deletes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                changed = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.STORAGE,
                    object_id=None,
                    value={
                        "id": "local-extra",
                        "name": "Extra",
                        "type": "local",
                        "rootPath": str(root / "extra"),
                    },
                    expected_version=draft.version,
                    actor="tester",
                )
                self.assertEqual(changed.status.value, "draft")
                self.assertEqual(
                    len(changed.document["metadataPolicies"]), len(document["metadataPolicies"])
                )
                with self.assertRaises(ConfigurationObjectReferenced):
                    objects.mutate(
                        changed.revision_id,
                        ConfigurationObjectKind.STORAGE,
                        object_id="source-storage",
                        value=None,
                        expected_version=changed.version,
                        actor="tester",
                        delete=True,
                    )
                detail = objects.revision_detail(changed.revision_id)
                self.assertEqual(detail["objects"]["storages"][-1]["id"], "local-extra")

    def test_remote_storage_is_preserved_redacted_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            document["storages"].append(
                {
                    "id": "remote",
                    "name": "Remote",
                    "type": "openlist",
                    "rootPath": "/",
                    "options": {"baseUrl": "https://example.invalid", "tokenEnv": "OPENLIST_TOKEN"},
                }
            )
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                detail = objects.revision_detail(draft.revision_id)
                remote = next(
                    item for item in detail["objects"]["storages"] if item["id"] == "remote"
                )
                self.assertTrue(remote["readOnly"])
                self.assertEqual(remote["editability"], "json_import_only")
                self.assertEqual(remote["options"]["tokenEnv"], "OPENLIST_TOKEN")

    def test_guided_local_create_and_update_preserve_host_absolute_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                draft = service.import_draft(document, actor="tester")
                first_root = str(root / "first root")
                status, created = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/objects/storages",
                    method="POST",
                    body={
                        "expectedVersion": draft.version,
                        "object": {
                            "id": "guided-local",
                            "name": "Guided Local",
                            "type": "local",
                            "rootPath": first_root,
                            "readOnly": True,
                        },
                    },
                )
                self.assertEqual(status, 200)
                second_root = str(root / "second root")
                target_path = (
                    f"/api/v1/configuration/revisions/{draft.revision_id}"
                    "/objects/storages/guided-local"
                )
                status, updated = request(
                    api,
                    target_path,
                    method="PUT",
                    body={
                        "expectedVersion": created["version"],
                        "object": {
                            "id": "guided-local",
                            "name": "Guided Local",
                            "type": "local",
                            "rootPath": second_root,
                            "readOnly": True,
                        },
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(updated["version"], created["version"] + 1)
                status, guided = request(
                    api, f"/api/v1/configuration/revisions/{draft.revision_id}/objects"
                )
                self.assertEqual(status, 200)
                stored = next(
                    item for item in guided["objects"]["storages"] if item["id"] == "guided-local"
                )
                self.assertEqual(stored["rootPath"], second_root)

    def test_invalid_guided_local_root_is_atomic_and_same_object_can_recover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                draft = service.import_draft(document, actor="tester")
                target_path = (
                    f"/api/v1/configuration/revisions/{draft.revision_id}"
                    "/objects/storages/source-storage"
                )
                before = service.require(draft.revision_id)
                before_audits = len(config_repository.list_revision_audits(draft.revision_id))
                invalid_roots = (
                    "",
                    None,
                    17,
                    "bad\x00root",
                    "relative/media",
                    "../escape",
                    f"{root}/safe/../escape",
                )
                for invalid_root in invalid_roots:
                    with self.subTest(root=repr(invalid_root)):
                        status, response = request(
                            api,
                            target_path,
                            method="PUT",
                            body={
                                "expectedVersion": draft.version,
                                "object": {
                                    "id": "source-storage",
                                    "name": "Source",
                                    "type": "local",
                                    "rootPath": invalid_root,
                                    "readOnly": True,
                                },
                            },
                        )
                        self.assertEqual(status, 400)
                        self.assertEqual(response["error"]["code"], "invalid_request")
                        self.assertIn("rootPath", response["error"]["message"])
                        self.assertIn("host-absolute", response["error"]["message"])
                        current = service.require(draft.revision_id)
                        self.assertEqual(current.version, before.version)
                        self.assertEqual(current.digest, before.digest)
                        self.assertEqual(current.document, before.document)
                        self.assertEqual(
                            len(config_repository.list_revision_audits(draft.revision_id)),
                            before_audits,
                        )

                corrected_root = str(root / "corrected source")
                status, saved = request(
                    api,
                    target_path,
                    method="PUT",
                    body={
                        "expectedVersion": draft.version,
                        "object": {
                            "id": "source-storage",
                            "name": "Source",
                            "type": "local",
                            "rootPath": corrected_root,
                            "readOnly": True,
                        },
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(saved["version"], draft.version + 1)
                current = service.require(draft.revision_id)
                source = next(
                    item for item in current.document["storages"] if item["id"] == "source-storage"
                )
                self.assertEqual(source["rootPath"], corrected_root)
                object_audits = [
                    audit.safe_after().get("objectChange", {})
                    for audit in config_repository.list_revision_audits(draft.revision_id)
                    if audit.safe_after().get("objectChange", {}).get("objectId")
                    == "source-storage"
                ]
                self.assertEqual(len(object_audits), 1)
                self.assertEqual(object_audits[0]["action"], "guided_update")

    def test_guided_local_root_validation_constructs_no_storage_or_filesystem_io(self) -> None:
        absolute_root = str(Path(tempfile.gettempdir()) / "mediaflow-root-validation")
        traversal_root = str(Path(tempfile.gettempdir()) / "media" / ".." / "escape")
        for root in ("relative/media", traversal_root, absolute_root):
            with self.subTest(root=root):
                with (
                    patch(
                        "mediaflow.application.configuration_objects.load_runtime_configuration",
                        side_effect=AssertionError("runtime/Storage construction is forbidden"),
                    ),
                    patch(
                        "mediaflow.application.configuration_objects.load_managed_runtime_configuration",
                        side_effect=AssertionError("runtime/Storage construction is forbidden"),
                    ),
                    patch("os.stat", side_effect=AssertionError("filesystem stat is forbidden")),
                    patch("os.listdir", side_effect=AssertionError("filesystem list is forbidden")),
                    patch(
                        "os.makedirs", side_effect=AssertionError("filesystem mkdir is forbidden")
                    ),
                    patch(
                        "pathlib.Path.resolve",
                        side_effect=AssertionError("path resolve is forbidden"),
                    ),
                ):
                    value = {
                        "id": "local",
                        "name": "Local",
                        "type": "local",
                        "rootPath": root,
                        "readOnly": True,
                    }
                    if root == absolute_root:
                        self.assertEqual(
                            ConfigurationObjectService._normalize(
                                ConfigurationObjectKind.STORAGE, value
                            )["rootPath"],
                            root,
                        )
                    else:
                        with self.assertRaisesRegex(ValueError, "host-absolute"):
                            ConfigurationObjectService._normalize(
                                ConfigurationObjectKind.STORAGE, value
                            )

    def test_local_setup_check_is_read_only_and_exact_revision_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "incoming").mkdir(parents=True)
            (root / "target" / "Movies").mkdir(parents=True)
            document = self._document(root)
            before = {
                root / "source",
                root / "source" / "incoming",
                root / "target",
                root / "target" / "Movies",
            }
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                evidence = objects.local_check(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="source",
                    media_library_id="movies",
                )
                self.assertEqual(evidence.status, ConfigurationSetupCheckStatus.PASSED)
                self.assertEqual(evidence.source_path, "incoming")
                self.assertEqual(evidence.destination_path, "Movies")
                self.assertEqual(repository.get_local_setup_check(validated.revision_id), evidence)
                self.assertEqual(before, {path for path in root.rglob("*") if path.is_dir()})
                self.assertIsNone(service.active())
                self._strategy_test(objects, validated)
                self._destination_precheck(objects, validated)
                activated = objects.activate_checked(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                self.assertEqual(activated.status.value, "active")

    def test_recognition_crud_strategy_evidence_and_c_identity_journey(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "incoming").mkdir(parents=True)
            (root / "target" / "Movies").mkdir(parents=True)
            document = self._document(root)
            before = sorted(
                (path.relative_to(root).as_posix(), path.is_dir()) for path in root.rglob("*")
            )
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")

                created = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.RECOGNITION_TYPE,
                    object_id=None,
                    value={"id": "D", "name": "Temporary", "enabled": True},
                    expected_version=draft.version,
                    actor="tester",
                )
                deleted = objects.mutate(
                    created.revision_id,
                    ConfigurationObjectKind.RECOGNITION_TYPE,
                    object_id="D",
                    value=None,
                    expected_version=created.version,
                    actor="tester",
                    delete=True,
                )
                with self.assertRaises(ConfigurationObjectReferenced):
                    objects.mutate(
                        deleted.revision_id,
                        ConfigurationObjectKind.RECOGNITION_TYPE,
                        object_id="C",
                        value=None,
                        expected_version=deleted.version,
                        actor="tester",
                        delete=True,
                    )
                special = next(
                    item
                    for item in deleted.document["recognitionRules"]
                    if item["id"] == "special-library"
                )
                special = copy.deepcopy(special)
                special["priority"] = 321
                edited = objects.mutate(
                    deleted.revision_id,
                    ConfigurationObjectKind.RECOGNITION_RULE,
                    object_id="special-library",
                    value=special,
                    expected_version=deleted.version,
                    actor="tester",
                )
                with self.assertRaises(ValueError):
                    objects.mutate(
                        edited.revision_id,
                        ConfigurationObjectKind.RECOGNITION_RULE,
                        object_id=None,
                        value={
                            "id": "unsafe",
                            "name": "Unsafe",
                            "condition": {
                                "field": "path",
                                "operator": "regex",
                                "value": "(a+)+$",
                            },
                            "outputRecognitionType": "C",
                        },
                        expected_version=edited.version,
                        actor="tester",
                    )
                validated = service.validate(edited.revision_id, actor="tester")
                objects.local_check(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="source",
                    media_library_id="movies",
                )
                failed = objects.recognition_strategy_test(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="missing",
                    synthetic_path="/C/Special.Movie.2024.mkv",
                )
                self.assertEqual(failed.status.value, "failed")
                self.assertEqual(failed.failure_category, "invalid_configuration")
                self.assertEqual(failed.document()["sideEffects"], "none")
                self.assertTrue(failed.document()["retrySafe"])
                with self.assertRaises(ConfigurationActivationConflict):
                    objects.activate_checked(
                        validated.revision_id,
                        expected_version=validated.version,
                        actor="tester",
                    )
                with patch(
                    "mediaflow.infrastructure.runtime_configuration."
                    "RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("Strategy Test must not construct Storage"),
                ):
                    evidence = objects.recognition_strategy_test(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        synthetic_path="/C/Special.Movie.2024.mkv",
                    )
                self.assertEqual(evidence.status.value, "completed")
                recognition = evidence.result["recognition"]
                self.assertEqual(recognition["recognitionType"], "C")
                self.assertEqual(recognition["matchedRules"][0]["priority"], 321)
                self.assertEqual(evidence.result["policy"]["recognitionType"], "C")
                self.assertEqual(evidence.result["policy"]["metadataPolicy"], "C")
                self.assertEqual(evidence.result["policy"]["namingPolicy"], "A")
                self.assertEqual(evidence.result["policy"]["classificationPolicy"], "A")
                self.assertEqual(evidence.result["effectiveMetadataPolicy"]["id"], "C")
                self.assertTrue(evidence.result["recognitionTypePreserved"])
                self.assertEqual(
                    repository.get_recognition_strategy_test(validated.revision_id), evidence
                )
                detail = objects.revision_detail(validated.revision_id)
                self.assertFalse(detail["recognitionStrategyTest"]["stale"])
                type_c = next(
                    item for item in validated.document["recognitionTypes"] if item["id"] == "C"
                )
                changed_type = copy.deepcopy(type_c)
                changed_type["description"] = "Reviewed special type"
                changed = objects.mutate(
                    validated.revision_id,
                    ConfigurationObjectKind.RECOGNITION_TYPE,
                    object_id="C",
                    value=changed_type,
                    expected_version=validated.version,
                    actor="tester",
                )
                stale_detail = objects.revision_detail(changed.revision_id)
                self.assertTrue(stale_detail["recognitionStrategyTest"]["stale"])
                self.assertTrue(stale_detail["localSetupCheck"]["stale"])
                revalidated = service.validate(changed.revision_id, actor="tester")
                objects.local_check(
                    revalidated.revision_id,
                    expected_version=revalidated.version,
                    expected_digest=revalidated.digest,
                    actor="tester",
                    resource_library_id="source",
                    media_library_id="movies",
                )
                objects.recognition_strategy_test(
                    revalidated.revision_id,
                    expected_version=revalidated.version,
                    expected_digest=revalidated.digest,
                    actor="tester",
                    resource_library_id="source",
                    synthetic_path="/C/Special.Movie.2024.mkv",
                )
                self._destination_precheck(objects, revalidated)
                activated = objects.activate_checked(
                    revalidated.revision_id,
                    expected_version=revalidated.version,
                    actor="tester",
                )
                self.assertEqual(activated.status.value, "active")
            after = sorted(
                (path.relative_to(root).as_posix(), path.is_dir())
                for path in root.rglob("*")
                if path.name != "configuration.sqlite3"
                and not path.name.startswith("configuration.sqlite3-")
            )
            self.assertEqual([item for item in before if item[0] != "configuration.sqlite3"], after)

    def test_managed_live_metadata_uses_exact_policy_and_explains_later_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider(
                (
                    MediaCandidate("tmdb", "wrong", MediaType.MOVIE, "Unrelated", year=2024),
                    MediaCandidate(
                        "tmdb",
                        "correct",
                        MediaType.MOVIE,
                        "Example Movie",
                        year=2024,
                        translated_titles=("示例电影",),
                    ),
                )
            )
            factory_calls = []

            def factory(provider_ids):
                factory_calls.append(provider_ids)
                return MetadataProviderRegistry((provider,))

            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(
                    service, metadata_provider_registry_factory=factory
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with patch(
                    "mediaflow.infrastructure.runtime_configuration."
                    "RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("live Strategy Test must not construct Storage"),
                ):
                    evidence = objects.recognition_strategy_test(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        synthetic_path="/电影/Example.Movie.2024.mkv",
                        live_metadata=True,
                    )
                self.assertEqual(evidence.status.value, "completed")
                self.assertEqual(factory_calls, [("tmdb",)])
                self.assertEqual(provider.searches, 1)
                self.assertEqual(evidence.result["mode"], "live")
                self.assertEqual(evidence.result["effectiveMetadataPolicy"]["providerId"], "tmdb")
                self.assertEqual(evidence.result["metadata"]["status"], "matched")
                self.assertEqual(evidence.result["metadata"]["identity"]["providerId"], "correct")
                candidates = evidence.result["metadata"]["match"]["candidates"]
                self.assertEqual([item["providerId"] for item in candidates], ["correct", "wrong"])
                self.assertEqual(candidates[0]["matchedTitleSource"], "title")
                self.assertIn("canonical year", candidates[0]["components"][1]["reason"])
                self.assertEqual(
                    repository.get_recognition_strategy_test(validated.revision_id), evidence
                )

    def test_offline_strategy_test_never_constructs_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)

            def forbidden_factory(_provider_ids):
                raise AssertionError("offline test must not construct a Provider")

            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(
                    service, metadata_provider_registry_factory=forbidden_factory
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                evidence = self._strategy_test(objects, validated)
                self.assertEqual(evidence.status.value, "completed")
                self.assertEqual(evidence.result["mode"], "offline")
                self.assertIsNone(evidence.result["metadata"])

    def test_live_provider_failures_are_categorized_and_secret_free(self) -> None:
        cases = (
            (MetadataErrorCode.AUTHENTICATION_FAILED, "authentication_failed"),
            (MetadataErrorCode.RATE_LIMITED, "rate_limited"),
            (MetadataErrorCode.TIMEOUT, "timeout"),
            (MetadataErrorCode.CONNECTION_FAILED, "provider_unavailable"),
            (MetadataErrorCode.MALFORMED_RESPONSE, "malformed_response"),
        )
        for code, category in cases:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = self._document(root)
                secret = "secret-token-in-provider-error"
                provider = FakeLiveMetadataProvider(
                    error=MetadataError(code, f"provider failed Authorization: Bearer {secret}")
                )
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    service = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(
                        service,
                        metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                            (provider,)
                        ),
                    )
                    draft = service.import_draft(document, actor="tester")
                    validated = service.validate(draft.revision_id, actor="tester")
                    evidence = objects.recognition_strategy_test(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        synthetic_path="/电影/Example.Movie.2024.mkv",
                        live_metadata=True,
                    )
                    self.assertEqual(evidence.status.value, "failed")
                    self.assertEqual(evidence.failure_category, category)
                    self.assertEqual(evidence.result["metadata"]["status"], "provider_error")
                    self.assertNotIn(secret, json.dumps(evidence.document()))
                    self.assertEqual(evidence.document()["sideEffects"], "none")

    def test_live_c_recognition_remains_c(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider(
                (MediaCandidate("tmdb", "c-id", MediaType.MOVIE, "Special Movie", year=2024),)
            )
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(
                    service,
                    metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                        (provider,)
                    ),
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                evidence = objects.recognition_strategy_test(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="source",
                    synthetic_path="/C/Special.Movie.2024.mkv",
                    live_metadata=True,
                )
                self.assertEqual(evidence.result["recognition"]["recognitionType"], "C")
                self.assertEqual(evidence.result["policy"]["metadataPolicy"], "C")
                self.assertEqual(evidence.result["policy"]["namingPolicy"], "A")
                self.assertTrue(evidence.result["recognitionTypePreserved"])

    def test_live_localized_title_and_canonical_year_evidence_are_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "858024",
                        MediaType.MOVIE,
                        "Hamnet",
                        original_title="Hamnet",
                        year=2025,
                        translated_titles=("哈姆奈特",),
                        regional_release_date="2026-01-01",
                    ),
                )
            )
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(
                    service,
                    metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                        (provider,)
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                evidence = objects.recognition_strategy_test(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="source",
                    synthetic_path="/电影/哈姆奈特.2025.mkv",
                    live_metadata=True,
                )
                candidate = evidence.result["metadata"]["match"]["candidates"][0]
                self.assertEqual(candidate["matchedProviderTitle"], "哈姆奈特")
                self.assertEqual(candidate["matchedTitleSource"], "translation")
                self.assertEqual(candidate["canonicalYear"], 2025)
                self.assertEqual(candidate["regionalYear"], 2026)
                self.assertIn("exact translation match", candidate["components"][0]["reason"])

    def test_live_candidate_media_outcomes_remain_distinct(self) -> None:
        cases = (
            (
                "need_confirm",
                (MediaCandidate("tmdb", "candidate", MediaType.MOVIE, "Example", year=2024),),
                {},
            ),
            (
                "ambiguous",
                tuple(
                    MediaCandidate("tmdb", str(index), MediaType.MOVIE, "Example Movie", year=2024)
                    for index in range(12)
                ),
                {},
            ),
            (
                "not_found",
                (MediaCandidate("tmdb", "wrong", MediaType.MOVIE, "Unrelated", year=2024),),
                {},
            ),
        )
        for expected, candidates, policy_changes in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = self._document(root)
                policy = next(item for item in document["metadataPolicies"] if item["id"] == "A")
                policy.update(policy_changes)
                provider = FakeLiveMetadataProvider(candidates)
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    service = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(
                        service,
                        metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                            (provider,)
                        ),
                    )
                    validated = service.validate(
                        service.import_draft(document, actor="tester").revision_id,
                        actor="tester",
                    )
                    evidence = objects.recognition_strategy_test(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        synthetic_path="/电影/Example.Movie.2024.mkv",
                        live_metadata=True,
                    )
                    self.assertEqual(evidence.status.value, "completed")
                    self.assertEqual(evidence.failure_category, expected)
                    self.assertEqual(evidence.result["metadata"]["status"], expected)
                    self.assertLessEqual(len(evidence.result["metadata"]["match"]["candidates"]), 5)
                    self.assertTrue(evidence.next_action)

    def test_live_missing_credential_or_provider_fails_with_recovery(self) -> None:
        with self.assertRaises(MetadataProviderBootstrapError) as missing:
            metadata_provider_registry_from_environment(("tmdb",), environ={})
        self.assertEqual(missing.exception.category, "missing_credential")
        with self.assertRaises(MetadataProviderBootstrapError) as unsupported:
            metadata_provider_registry_from_environment(("unknown",), environ={})
        self.assertEqual(unsupported.exception.category, "provider_not_configured")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(
                    service,
                    metadata_provider_registry_factory=lambda ids: (
                        metadata_provider_registry_from_environment(ids, environ={})
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                evidence = objects.recognition_strategy_test(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="source",
                    synthetic_path="/电影/Example.Movie.2024.mkv",
                    live_metadata=True,
                )
                self.assertEqual(evidence.failure_category, "missing_credential")
                self.assertEqual(evidence.result["mode"], "live")
                self.assertIn("TMDB_ACCESS_TOKEN", evidence.next_action)

    def test_api_get_and_offline_are_lazy_while_repeated_live_reuses_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Example Movie", year=2024),)
            )
            builder_calls = []

            def builder(provider_ids):
                builder_calls.append(tuple(provider_ids))
                return MetadataProviderRegistry((provider,))

            lazy_factory = LazyMetadataProviderRegistryFactory(builder)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=lazy_factory,
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                endpoint = (
                    f"/api/v1/configuration/revisions/{validated.revision_id}/"
                    "recognition-strategy-test"
                )
                status, _detail = request(
                    api,
                    f"/api/v1/configuration/revisions/{validated.revision_id}/objects",
                )
                self.assertEqual(status, 200)
                base_body = {
                    "expectedVersion": validated.version,
                    "expectedDigest": validated.digest,
                    "resourceLibraryId": "source",
                    "syntheticPath": "/电影/Example.Movie.2024.mkv",
                }
                status, offline = request(api, endpoint, method="POST", body=base_body)
                self.assertEqual(status, 200)
                self.assertEqual(offline["result"]["mode"], "offline")
                self.assertEqual(builder_calls, [])
                for _ in range(2):
                    status, live = request(
                        api,
                        endpoint,
                        method="POST",
                        body={**base_body, "liveMetadata": True},
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(live["result"]["metadata"]["status"], "matched")
                self.assertEqual(builder_calls, [("tmdb",)])

    def test_four_byte_unicode_ambiguous_evidence_is_bounded_persisted_and_reloaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            title = "😀" * 300
            provider = FakeLiveMetadataProvider(
                tuple(
                    MediaCandidate("tmdb", str(index), MediaType.MOVIE, title, year=2024)
                    for index in range(12)
                )
            )
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                        lambda _ids: MetadataProviderRegistry((provider,))
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                status, evidence = request(
                    api,
                    f"/api/v1/configuration/revisions/{validated.revision_id}/"
                    "recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": f"/电影/{title}.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(evidence["status"], "completed")
                self.assertEqual(evidence["failureCategory"], "ambiguous")
                metadata = evidence["result"]["metadata"]
                self.assertEqual(metadata["status"], "ambiguous")
                self.assertTrue(metadata["truncated"])
                self.assertTrue(metadata["match"]["truncated"])
                self.assertEqual(metadata["match"]["candidateTotal"], 12)
                self.assertLess(metadata["match"]["candidateProjected"], 12)
                encoded = json.dumps(
                    evidence["result"], ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
                self.assertLessEqual(len(encoded), CONFIGURATION_STRATEGY_RESULT_LIMIT)

                status, detail = request(
                    api,
                    f"/api/v1/configuration/revisions/{validated.revision_id}/objects",
                )
                self.assertEqual(status, 200)
                reloaded = detail["recognitionStrategyTest"]
                self.assertEqual(reloaded["failureCategory"], "ambiguous")
                self.assertEqual(reloaded["result"]["metadata"], metadata)

    def test_api_corrects_live_not_found_by_query_and_persists_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider()
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                        (provider,)
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                status, not_found = request(
                    api,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/C/Wrong.Title.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(not_found["failureCategory"], "not_found")
                provider.candidates = (
                    MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct Title", year=2024),
                )
                with patch(
                    "mediaflow.infrastructure.runtime_configuration."
                    "RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("Metadata correction must not construct Storage"),
                ):
                    status, corrected = request(
                        api,
                        f"{base}/recognition-strategy-test/metadata-correction",
                        method="POST",
                        body={
                            "expectedVersion": validated.version,
                            "expectedDigest": validated.digest,
                            "expectedTestedAt": not_found["testedAt"],
                            "query": "  Correct Title  ",
                            "year": 2024,
                            "mediaType": "movie",
                        },
                    )
                self.assertEqual(status, 200)
                self.assertEqual(corrected["status"], "completed")
                metadata = corrected["result"]["metadata"]
                self.assertEqual(metadata["status"], "matched")
                self.assertEqual(metadata["identity"]["providerId"], "42")
                self.assertEqual(
                    metadata["correction"],
                    {
                        "mode": "query",
                        "sourceOutcome": "not_found",
                        "mediaType": "movie",
                        "provider": "tmdb",
                        "query": "Correct Title",
                        "year": 2024,
                    },
                )
                self.assertEqual(corrected["result"]["recognition"]["recognitionType"], "C")
                self.assertEqual(corrected["result"]["policy"]["metadataPolicy"], "C")
                self.assertTrue(corrected["result"]["recognitionTypePreserved"])
                self.assertEqual(provider.search_queries[-1].title_candidate, "Correct Title")
                self.assertEqual(
                    repository.get_recognition_strategy_test(validated.revision_id).document(),
                    corrected,
                )

    def test_api_direct_id_correction_uses_details_without_repeated_search(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider()
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                        (provider,)
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                _status, not_found = request(
                    api,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/C/Wrong.Title.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                searches_before = provider.searches
                provider.candidates = (
                    MediaCandidate(
                        "tmdb", "direct-42", MediaType.MOVIE, "Correct Title", year=2024
                    ),
                )
                status, corrected = request(
                    api,
                    f"{base}/recognition-strategy-test/metadata-correction",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "expectedTestedAt": not_found["testedAt"],
                        "providerId": "direct-42",
                        "mediaType": "movie",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(provider.searches, searches_before)
                self.assertEqual(provider.detail_ids, ["direct-42"])
                metadata = corrected["result"]["metadata"]
                self.assertEqual(metadata["identity"]["matchedBy"], "manual_provider_id")
                self.assertEqual(metadata["correction"]["mode"], "direct_provider_id")
                self.assertEqual(metadata["correction"]["providerId"], "direct-42")
                self.assertEqual(corrected["result"]["recognition"]["recognitionType"], "C")

    def test_metadata_correction_rejects_invalid_or_stale_input_without_provider_access(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider()
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                        (provider,)
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                _status, evidence = request(
                    api,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/C/Wrong.Title.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                original = repository.get_recognition_strategy_test(validated.revision_id)
                calls = provider.searches + provider.details
                common = {
                    "expectedVersion": validated.version,
                    "expectedDigest": validated.digest,
                    "expectedTestedAt": evidence["testedAt"],
                    "mediaType": "movie",
                }
                for body, expected_status in (
                    ({**common, "query": "Title", "providerId": "42"}, 400),
                    ({**common, "query": "Title", "provider": "other"}, 400),
                    ({**common, "query": "Title", "year": 1800}, 400),
                    ({**common, "providerId": "bad/id"}, 400),
                    ({**common, "query": "Title", "expectedTestedAt": "stale"}, 409),
                ):
                    with self.subTest(body=body):
                        status, _result = request(
                            api,
                            f"{base}/recognition-strategy-test/metadata-correction",
                            method="POST",
                            body=body,
                        )
                        self.assertEqual(status, expected_status)
                self.assertEqual(provider.searches + provider.details, calls)
                self.assertEqual(
                    repository.get_recognition_strategy_test(validated.revision_id), original
                )

    def test_metadata_correction_rejects_offline_matched_and_draft_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider()
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                        (provider,)
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"

                def run_test(live):
                    return request(
                        api,
                        f"{base}/recognition-strategy-test",
                        method="POST",
                        body={
                            "expectedVersion": validated.version,
                            "expectedDigest": validated.digest,
                            "resourceLibraryId": "source",
                            "syntheticPath": "/C/Exact.2024.mkv",
                            "liveMetadata": live,
                        },
                    )[1]

                def correct(evidence):
                    return request(
                        api,
                        f"{base}/recognition-strategy-test/metadata-correction",
                        method="POST",
                        body={
                            "expectedVersion": validated.version,
                            "expectedDigest": validated.digest,
                            "expectedTestedAt": evidence["testedAt"],
                            "query": "Exact",
                            "mediaType": "movie",
                        },
                    )

                offline = run_test(False)
                self.assertEqual(correct(offline)[0], 400)
                self.assertEqual(provider.searches + provider.details, 0)
                provider.candidates = (
                    MediaCandidate("tmdb", "42", MediaType.MOVIE, "Exact", year=2024),
                )
                matched = run_test(True)
                self.assertEqual(matched["result"]["metadata"]["status"], "matched")
                calls = provider.searches + provider.details
                self.assertEqual(correct(matched)[0], 400)
                self.assertEqual(provider.searches + provider.details, calls)
                changed = copy.deepcopy(validated.document)
                changed["recognitionTypes"][0]["description"] = "Draft"
                service.edit_draft(
                    validated.revision_id,
                    changed,
                    expected_version=validated.version,
                    actor="editor",
                )
                self.assertEqual(correct(matched)[0], 409)
                self.assertEqual(provider.searches + provider.details, calls)

    def test_corrected_candidates_reuse_existing_confirmation_without_second_search(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider()
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                        (provider,)
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                _status, not_found = request(
                    api,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/C/Wrong.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                provider.candidates = tuple(
                    MediaCandidate("tmdb", str(index), MediaType.MOVIE, "Correct", year=2024)
                    for index in (1, 2)
                )
                _status, corrected = request(
                    api,
                    f"{base}/recognition-strategy-test/metadata-correction",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "expectedTestedAt": not_found["testedAt"],
                        "query": "Correct",
                        "mediaType": "movie",
                    },
                )
                self.assertIn(
                    corrected["result"]["metadata"]["status"], {"need_confirm", "ambiguous"}
                )
                searches = provider.searches
                status, selected = request(
                    api,
                    f"{base}/recognition-strategy-test/candidate-selection",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "expectedTestedAt": corrected["testedAt"],
                        "candidateRank": 1,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(provider.searches, searches)
                self.assertEqual(
                    selected["result"]["metadata"]["candidateSelection"]["providerId"], "1"
                )
                self.assertEqual(
                    selected["result"]["metadata"]["correction"],
                    corrected["result"]["metadata"]["correction"],
                )

    def test_metadata_correction_provider_failures_persist_bounded_context(self) -> None:
        cases = (
            (MetadataErrorCode.INVALID_REQUEST, "invalid_provider_request"),
            (MetadataErrorCode.NOT_FOUND, "provider_id_not_found"),
            (MetadataErrorCode.TIMEOUT, "timeout"),
            (MetadataErrorCode.RATE_LIMITED, "rate_limited"),
            (MetadataErrorCode.AUTHENTICATION_FAILED, "authentication_failed"),
            (MetadataErrorCode.MALFORMED_RESPONSE, "malformed_response"),
        )
        for error_code, expected_category in cases:
            with self.subTest(error_code=error_code):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    document = self._document(root)
                    provider = FakeLiveMetadataProvider()
                    with (
                        SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                        SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
                    ):
                        service = ManagedConfigurationService(repository)
                        api = MediaFlowApi(
                            runtime_repository,
                            None,
                            principals=(
                                ResolvedApiPrincipal(
                                    "admin", "admin-token", frozenset(ApiPermission)
                                ),
                            ),
                            configuration_service=service,
                            bootstrap_document=document,
                            metadata_provider_registry_factory=lambda _ids: (
                                MetadataProviderRegistry((provider,))
                            ),
                        )
                        validated = service.validate(
                            service.import_draft(document, actor="tester").revision_id,
                            actor="tester",
                        )
                        base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                        _status, not_found = request(
                            api,
                            f"{base}/recognition-strategy-test",
                            method="POST",
                            body={
                                "expectedVersion": validated.version,
                                "expectedDigest": validated.digest,
                                "resourceLibraryId": "source",
                                "syntheticPath": "/C/Wrong.2024.mkv",
                                "liveMetadata": True,
                            },
                        )
                        secret = "provider-secret-must-not-leak"
                        provider_failure = MetadataError(error_code, f"failure with {secret}")
                        direct = error_code in {
                            MetadataErrorCode.INVALID_REQUEST,
                            MetadataErrorCode.NOT_FOUND,
                        }
                        if direct:
                            provider.details_error = provider_failure
                        else:
                            provider.error = provider_failure
                        correction = (
                            {"providerId": "bad-direct-id"} if direct else {"query": "Corrected"}
                        )
                        status, failed = request(
                            api,
                            f"{base}/recognition-strategy-test/metadata-correction",
                            method="POST",
                            body={
                                "expectedVersion": validated.version,
                                "expectedDigest": validated.digest,
                                "expectedTestedAt": not_found["testedAt"],
                                "mediaType": "movie",
                                **correction,
                            },
                        )
                        self.assertEqual(status, 200)
                        self.assertEqual(failed["status"], "failed")
                        self.assertEqual(failed["failureCategory"], expected_category)
                        context = failed["result"]["metadata"]["correction"]
                        self.assertEqual(
                            context["providerId"] if direct else context["query"],
                            "bad-direct-id" if direct else "Corrected",
                        )
                        self.assertEqual(failed["sideEffects"], "none")
                        self.assertTrue(failed["retrySafe"])
                        self.assertIn("rerun", failed["nextAction"])
                        self.assertNotIn(secret, json.dumps(failed))
                        calls_before_recovery = provider.searches + provider.details
                        if direct:
                            provider.details_error = None
                            provider.candidates = (
                                MediaCandidate(
                                    "tmdb",
                                    "bad-direct-id",
                                    MediaType.MOVIE,
                                    "Recovered",
                                    year=2024,
                                ),
                            )
                        else:
                            provider.error = None
                            provider.candidates = (
                                MediaCandidate(
                                    "tmdb", "recovered", MediaType.MOVIE, "Corrected", year=2024
                                ),
                            )
                        recovery_status, recovered = request(
                            api,
                            f"{base}/recognition-strategy-test/metadata-correction",
                            method="POST",
                            body={
                                "expectedVersion": validated.version,
                                "expectedDigest": validated.digest,
                                "expectedTestedAt": failed["testedAt"],
                                "mediaType": "movie",
                                **correction,
                            },
                        )
                        self.assertEqual(recovery_status, 200)
                        self.assertEqual(recovered["status"], "completed")
                        self.assertNotEqual(recovered["testedAt"], failed["testedAt"])
                        self.assertEqual(
                            recovered["result"]["metadata"]["correction"]["sourceOutcome"],
                            "not_found",
                        )
                        self.assertGreater(
                            provider.searches + provider.details, calls_before_recovery
                        )

    def test_concurrent_metadata_corrections_have_one_durable_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            configuration_path = root / "configuration.sqlite3"
            with (
                SQLiteConfigurationRepository(configuration_path) as repository_one,
                SQLiteConfigurationRepository(configuration_path) as repository_two,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                managed_one = ManagedConfigurationService(repository_one)
                managed_two = ManagedConfigurationService(repository_two)
                provider = FakeLiveMetadataProvider()

                def make_api(managed):
                    return MediaFlowApi(
                        runtime_repository,
                        None,
                        principals=(
                            ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                        ),
                        configuration_service=managed,
                        bootstrap_document=document,
                        metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                            (provider,)
                        ),
                    )

                api_one = make_api(managed_one)
                api_two = make_api(managed_two)
                validated = managed_one.validate(
                    managed_one.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                _status, not_found = request(
                    api_one,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/C/Wrong.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                provider.candidates = (
                    MediaCandidate("tmdb", "42", MediaType.MOVIE, "Winner", year=2024),
                )
                provider.search_barrier = Barrier(2)

                def correct(api, query):
                    return request(
                        api,
                        f"{base}/recognition-strategy-test/metadata-correction",
                        method="POST",
                        body={
                            "expectedVersion": validated.version,
                            "expectedDigest": validated.digest,
                            "expectedTestedAt": not_found["testedAt"],
                            "query": query,
                            "mediaType": "movie",
                        },
                    )

                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = (
                        executor.submit(correct, api_one, "Winner"),
                        executor.submit(correct, api_two, "Winner alternate"),
                    )
                    outcomes = tuple(future.result(timeout=10) for future in futures)
                self.assertEqual(sorted(status for status, _value in outcomes), [200, 409])
                winner = next(value for status, value in outcomes if status == 200)
                loser = next(value for status, value in outcomes if status == 409)
                self.assertEqual(loser["error"]["code"], "configuration_version_conflict")
                self.assertEqual(
                    loser["error"]["details"]["durableState"],
                    "current_strategy_evidence_preserved",
                )
                self.assertEqual(loser["error"]["details"]["sideEffects"], "none")
                self.assertIn("reload", loser["error"]["details"]["nextAction"])
                stored = repository_one.get_recognition_strategy_test(validated.revision_id)
                self.assertEqual(stored.document(), winner)
                self.assertIn(
                    stored.result["metadata"]["correction"]["query"],
                    {"Winner", "Winner alternate"},
                )
                self.assertEqual(provider.searches, 3)

    def test_metadata_correction_rejects_in_flight_revision_edit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            configuration_path = root / "configuration.sqlite3"
            with (
                SQLiteConfigurationRepository(configuration_path) as repository_one,
                SQLiteConfigurationRepository(configuration_path) as repository_two,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                managed_one = ManagedConfigurationService(repository_one)
                managed_two = ManagedConfigurationService(repository_two)
                provider = FakeLiveMetadataProvider()
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=managed_one,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                        (provider,)
                    ),
                )
                validated = managed_one.validate(
                    managed_one.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                _status, not_found = request(
                    api,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/C/Wrong.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                original = repository_one.get_recognition_strategy_test(validated.revision_id)
                provider.candidates = (
                    MediaCandidate("tmdb", "42", MediaType.MOVIE, "Winner", year=2024),
                )
                provider.search_barrier = Barrier(2)

                def correct():
                    return request(
                        api,
                        f"{base}/recognition-strategy-test/metadata-correction",
                        method="POST",
                        body={
                            "expectedVersion": validated.version,
                            "expectedDigest": validated.digest,
                            "expectedTestedAt": not_found["testedAt"],
                            "query": "Winner",
                            "mediaType": "movie",
                        },
                    )

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(correct)
                    for _ in range(500):
                        if provider.searches == 2:
                            break
                        time.sleep(0.002)
                    self.assertEqual(provider.searches, 2)
                    changed = copy.deepcopy(validated.document)
                    changed["recognitionTypes"][0]["description"] = "edited during correction"
                    edited = managed_two.edit_draft(
                        validated.revision_id,
                        changed,
                        expected_version=validated.version,
                        actor="editor",
                    )
                    provider.search_barrier.wait(timeout=5)
                    status, conflict = future.result(timeout=10)
                self.assertEqual(status, 409)
                self.assertEqual(
                    conflict["error"]["details"]["durableState"],
                    "current_draft_and_strategy_evidence_preserved",
                )
                self.assertEqual(conflict["error"]["details"]["sideEffects"], "none")
                self.assertIn("reload", conflict["error"]["details"]["nextAction"])
                self.assertEqual(repository_one.get_revision(validated.revision_id), edited)
                self.assertEqual(
                    repository_one.get_recognition_strategy_test(validated.revision_id), original
                )

    def test_api_confirms_only_persisted_candidate_and_preserves_c(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider(
                (
                    MediaCandidate("tmdb", "10", MediaType.MOVIE, "Special Movie", year=2024),
                    MediaCandidate("tmdb", "20", MediaType.MOVIE, "Special Movie", year=2024),
                )
            )
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                        lambda _ids: MetadataProviderRegistry((provider,))
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                status, ambiguous = request(
                    api,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/C/Special.Movie.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(ambiguous["failureCategory"], "ambiguous")
                self.assertEqual(provider.searches, 1)
                selection_body = {
                    "expectedVersion": validated.version,
                    "expectedDigest": validated.digest,
                    "expectedTestedAt": ambiguous["testedAt"],
                    "candidateRank": 2,
                }
                status, _forbidden = request(
                    api,
                    f"{base}/recognition-strategy-test/candidate-selection",
                    method="POST",
                    body=selection_body,
                    token="viewer-token",
                )
                self.assertEqual(status, 403)
                self.assertEqual(provider.details, 0)
                with patch(
                    "mediaflow.infrastructure.runtime_configuration."
                    "RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("candidate confirmation must not construct Storage"),
                ):
                    status, selected = request(
                        api,
                        f"{base}/recognition-strategy-test/candidate-selection",
                        method="POST",
                        body=selection_body,
                    )
                self.assertEqual(status, 200)
                self.assertEqual(selected["status"], "completed")
                self.assertEqual(selected["actor"], "admin")
                self.assertEqual(selected["result"]["metadata"]["status"], "matched")
                self.assertEqual(selected["result"]["metadata"]["identity"]["providerId"], "20")
                self.assertEqual(
                    selected["result"]["metadata"]["identity"]["matchedBy"],
                    "manual_provider_id",
                )
                self.assertEqual(
                    selected["result"]["metadata"]["candidateSelection"],
                    {
                        "rank": 2,
                        "sourceOutcome": "ambiguous",
                        "provider": "tmdb",
                        "providerId": "20",
                        "mediaType": "movie",
                    },
                )
                self.assertEqual(selected["result"]["recognition"]["recognitionType"], "C")
                self.assertEqual(selected["result"]["policy"]["metadataPolicy"], "C")
                self.assertTrue(selected["result"]["recognitionTypePreserved"])
                self.assertEqual(selected["sideEffects"], "none")
                self.assertEqual(provider.searches, 1)
                self.assertEqual(provider.details, 1)
                status, detail = request(api, f"{base}/objects")
                self.assertEqual(status, 200)
                reloaded = detail["recognitionStrategyTest"]
                self.assertFalse(reloaded["stale"])
                for key, value in selected.items():
                    self.assertEqual(reloaded[key], value)

    def test_candidate_confirmation_rejects_stale_rank_and_wrong_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider(
                tuple(
                    MediaCandidate("tmdb", str(index), MediaType.MOVIE, "Example Movie", year=2024)
                    for index in (1, 2)
                )
            )
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                        lambda _ids: MetadataProviderRegistry((provider,))
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                status, ambiguous = request(
                    api,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/电影/Example.Movie.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                self.assertEqual(status, 200)
                body = {
                    "expectedVersion": validated.version,
                    "expectedDigest": validated.digest,
                    "expectedTestedAt": ambiguous["testedAt"],
                    "candidateRank": 1,
                }
                for changes, expected_status in (
                    ({"expectedTestedAt": "2000-01-01T00:00:00+00:00"}, 409),
                    ({"candidateRank": 5}, 400),
                    ({"providerId": "injected"}, 400),
                ):
                    with self.subTest(changes=changes):
                        status, _error = request(
                            api,
                            f"{base}/recognition-strategy-test/candidate-selection",
                            method="POST",
                            body={**body, **changes},
                        )
                        self.assertEqual(status, expected_status)
                self.assertEqual(provider.details, 0)

                provider.candidates = (
                    MediaCandidate("tmdb", "matched", MediaType.MOVIE, "Example Movie", year=2024),
                )
                status, matched = request(
                    api,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/电影/Example.Movie.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                self.assertEqual(status, 200)
                status, _error = request(
                    api,
                    f"{base}/recognition-strategy-test/candidate-selection",
                    method="POST",
                    body={**body, "expectedTestedAt": matched["testedAt"]},
                )
                self.assertEqual(status, 400)
                self.assertEqual(provider.details, 1)

    def test_concurrent_candidate_confirmation_has_one_durable_winner(self) -> None:
        for details_error in (
            None,
            MetadataError(MetadataErrorCode.TIMEOUT, "candidate details timed out"),
        ):
            with self.subTest(provider_failure=details_error is not None):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    document = self._document(root)
                    provider = FakeLiveMetadataProvider(
                        (
                            MediaCandidate(
                                "tmdb", "10", MediaType.MOVIE, "Special Movie", year=2024
                            ),
                            MediaCandidate(
                                "tmdb", "20", MediaType.MOVIE, "Special Movie", year=2024
                            ),
                        ),
                        details_error=details_error,
                        details_barrier=Barrier(2),
                    )
                    configuration_path = root / "configuration.sqlite3"
                    with (
                        SQLiteConfigurationRepository(configuration_path) as repository_one,
                        SQLiteConfigurationRepository(configuration_path) as repository_two,
                        SQLiteTaskRepository(root / "runtime-one.sqlite3") as runtime_one,
                        SQLiteTaskRepository(root / "runtime-two.sqlite3") as runtime_two,
                    ):
                        managed_one = ManagedConfigurationService(repository_one)
                        managed_two = ManagedConfigurationService(repository_two)
                        registry = MetadataProviderRegistry((provider,))
                        api_one = MediaFlowApi(
                            runtime_one,
                            None,
                            principals=(
                                ResolvedApiPrincipal(
                                    "operator-one", "token-one", frozenset(ApiPermission)
                                ),
                            ),
                            configuration_service=managed_one,
                            bootstrap_document=document,
                            metadata_provider_registry_factory=lambda _ids: registry,
                        )
                        api_two = MediaFlowApi(
                            runtime_two,
                            None,
                            principals=(
                                ResolvedApiPrincipal(
                                    "operator-two", "token-two", frozenset(ApiPermission)
                                ),
                            ),
                            configuration_service=managed_two,
                            bootstrap_document=document,
                            metadata_provider_registry_factory=lambda _ids: registry,
                        )
                        validated = managed_one.validate(
                            managed_one.import_draft(document, actor="tester").revision_id,
                            actor="tester",
                        )
                        base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                        status, ambiguous = request(
                            api_one,
                            f"{base}/recognition-strategy-test",
                            method="POST",
                            token="token-one",
                            body={
                                "expectedVersion": validated.version,
                                "expectedDigest": validated.digest,
                                "resourceLibraryId": "source",
                                "syntheticPath": "/C/Special.Movie.2024.mkv",
                                "liveMetadata": True,
                            },
                        )
                        self.assertEqual(status, 200)
                        self.assertEqual(ambiguous["failureCategory"], "ambiguous")

                        def confirm(api, token, rank):
                            return request(
                                api,
                                f"{base}/recognition-strategy-test/candidate-selection",
                                method="POST",
                                token=token,
                                body={
                                    "expectedVersion": validated.version,
                                    "expectedDigest": validated.digest,
                                    "expectedTestedAt": ambiguous["testedAt"],
                                    "candidateRank": rank,
                                },
                            )

                        with (
                            patch(
                                "mediaflow.infrastructure.runtime_configuration."
                                "RuntimeConfiguration.create_storages",
                                side_effect=AssertionError(
                                    "candidate confirmation must not construct Storage"
                                ),
                            ),
                            ThreadPoolExecutor(max_workers=2) as executor,
                        ):
                            futures = (
                                executor.submit(confirm, api_one, "token-one", 1),
                                executor.submit(confirm, api_two, "token-two", 2),
                            )
                            outcomes = tuple(future.result(timeout=10) for future in futures)

                        self.assertEqual(sorted(status for status, _value in outcomes), [200, 409])
                        winner = next(value for status, value in outcomes if status == 200)
                        loser = next(value for status, value in outcomes if status == 409)
                        self.assertEqual(loser["error"]["code"], "configuration_version_conflict")
                        self.assertIn("reload", loser["error"]["message"])
                        self.assertEqual(loser["error"]["details"]["sideEffects"], "none")
                        self.assertEqual(
                            loser["error"]["details"]["durableState"],
                            "current_strategy_evidence_preserved",
                        )
                        self.assertIn("reload", loser["error"]["details"]["nextAction"])

                        stored = repository_one.get_recognition_strategy_test(validated.revision_id)
                        self.assertIsNotNone(stored)
                        self.assertEqual(stored.document(), winner)
                        selection = stored.result["metadata"]["candidateSelection"]
                        self.assertEqual(stored.actor, winner["actor"])
                        self.assertEqual(
                            selection["providerId"], "10" if selection["rank"] == 1 else "20"
                        )
                        if details_error is None:
                            self.assertEqual(stored.status.value, "completed")
                            self.assertEqual(
                                stored.result["metadata"]["identity"]["providerId"],
                                selection["providerId"],
                            )
                        else:
                            self.assertEqual(stored.status.value, "failed")
                            self.assertEqual(stored.failure_category, "timeout")
                        self.assertEqual(stored.result["recognition"]["recognitionType"], "C")
                        self.assertEqual(stored.result["policy"]["metadataPolicy"], "C")
                        self.assertTrue(stored.result["recognitionTypePreserved"])
                        self.assertEqual(provider.searches, 1)
                        self.assertEqual(provider.details, 2)

                        replay_status, replay = confirm(api_one, "token-one", 1)
                        self.assertEqual(replay_status, 409)
                        self.assertIn("reload", replay["error"]["message"])
                        self.assertEqual(
                            repository_one.get_recognition_strategy_test(
                                validated.revision_id
                            ).document(),
                            winner,
                        )

    def test_candidate_confirmation_rejects_in_flight_revision_edit(self) -> None:
        for details_error in (
            None,
            MetadataError(MetadataErrorCode.TIMEOUT, "candidate details timed out"),
        ):
            with self.subTest(provider_failure=details_error is not None):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    document = self._document(root)
                    release_details = Barrier(2)
                    provider = FakeLiveMetadataProvider(
                        (
                            MediaCandidate(
                                "tmdb", "10", MediaType.MOVIE, "Special Movie", year=2024
                            ),
                            MediaCandidate(
                                "tmdb", "20", MediaType.MOVIE, "Special Movie", year=2024
                            ),
                        ),
                        details_error=details_error,
                        details_barrier=release_details,
                    )
                    configuration_path = root / "configuration.sqlite3"
                    with (
                        SQLiteConfigurationRepository(configuration_path) as repository_one,
                        SQLiteConfigurationRepository(configuration_path) as repository_two,
                        SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
                    ):
                        managed_one = ManagedConfigurationService(repository_one)
                        managed_two = ManagedConfigurationService(repository_two)
                        api = MediaFlowApi(
                            runtime_repository,
                            None,
                            principals=(
                                ResolvedApiPrincipal(
                                    "operator", "operator-token", frozenset(ApiPermission)
                                ),
                            ),
                            configuration_service=managed_one,
                            bootstrap_document=document,
                            metadata_provider_registry_factory=lambda _ids: (
                                MetadataProviderRegistry((provider,))
                            ),
                        )
                        validated = managed_one.validate(
                            managed_one.import_draft(document, actor="tester").revision_id,
                            actor="tester",
                        )
                        base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                        status, ambiguous = request(
                            api,
                            f"{base}/recognition-strategy-test",
                            method="POST",
                            token="operator-token",
                            body={
                                "expectedVersion": validated.version,
                                "expectedDigest": validated.digest,
                                "resourceLibraryId": "source",
                                "syntheticPath": "/C/Special.Movie.2024.mkv",
                                "liveMetadata": True,
                            },
                        )
                        self.assertEqual(status, 200)
                        self.assertEqual(ambiguous["failureCategory"], "ambiguous")
                        original_evidence = repository_one.get_recognition_strategy_test(
                            validated.revision_id
                        )
                        self.assertIsNotNone(original_evidence)

                        def confirm():
                            return request(
                                api,
                                f"{base}/recognition-strategy-test/candidate-selection",
                                method="POST",
                                token="operator-token",
                                body={
                                    "expectedVersion": validated.version,
                                    "expectedDigest": validated.digest,
                                    "expectedTestedAt": ambiguous["testedAt"],
                                    "candidateRank": 1,
                                },
                            )

                        with (
                            patch(
                                "mediaflow.infrastructure.runtime_configuration."
                                "RuntimeConfiguration.create_storages",
                                side_effect=AssertionError(
                                    "candidate confirmation must not construct Storage"
                                ),
                            ),
                            ThreadPoolExecutor(max_workers=1) as executor,
                        ):
                            future = executor.submit(confirm)
                            for _ in range(500):
                                if provider.details == 1:
                                    break
                                time.sleep(0.002)
                            self.assertEqual(provider.details, 1)
                            changed_document = copy.deepcopy(validated.document)
                            changed_document["recognitionTypes"][0]["description"] = (
                                "edited during candidate lookup"
                            )
                            edited = managed_two.edit_draft(
                                validated.revision_id,
                                changed_document,
                                expected_version=validated.version,
                                actor="editor",
                            )
                            release_details.wait(timeout=5)
                            conflict_status, conflict = future.result(timeout=10)

                        self.assertEqual(conflict_status, 409)
                        self.assertEqual(
                            conflict["error"]["code"], "configuration_version_conflict"
                        )
                        self.assertEqual(
                            conflict["error"]["details"]["durableState"],
                            "current_draft_and_strategy_evidence_preserved",
                        )
                        self.assertEqual(conflict["error"]["details"]["sideEffects"], "none")
                        self.assertTrue(conflict["error"]["details"]["retrySafe"])
                        next_action = conflict["error"]["details"]["nextAction"]
                        self.assertIn("reload", next_action)
                        self.assertIn("validate", next_action)
                        self.assertIn("rerun", next_action)

                        current = repository_one.get_revision(validated.revision_id)
                        self.assertIsNotNone(current)
                        self.assertEqual(current.version, edited.version)
                        self.assertEqual(current.status.value, "draft")
                        self.assertEqual(
                            repository_one.get_recognition_strategy_test(validated.revision_id),
                            original_evidence,
                        )
                        self.assertEqual(provider.searches, 1)
                        self.assertEqual(provider.details, 1)

    def test_candidate_confirmation_provider_failure_persists_selection_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            secret = "selection-provider-secret"
            provider = FakeLiveMetadataProvider(
                tuple(
                    MediaCandidate("tmdb", str(index), MediaType.MOVIE, "Example Movie", year=2024)
                    for index in (1, 2)
                ),
                details_error=MetadataError(
                    MetadataErrorCode.TIMEOUT, f"timed out with Bearer {secret}"
                ),
            )
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                        lambda _ids: MetadataProviderRegistry((provider,))
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                base = f"/api/v1/configuration/revisions/{validated.revision_id}"
                status, ambiguous = request(
                    api,
                    f"{base}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/电影/Example.Movie.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                self.assertEqual(status, 200)
                status, failed = request(
                    api,
                    f"{base}/recognition-strategy-test/candidate-selection",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "expectedTestedAt": ambiguous["testedAt"],
                        "candidateRank": 1,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(failed["status"], "failed")
                self.assertEqual(failed["failureCategory"], "timeout")
                self.assertEqual(
                    failed["result"]["metadata"]["candidateSelection"]["providerId"], "1"
                )
                self.assertIn("explicitly rerun", failed["nextAction"])
                self.assertNotIn(secret, json.dumps(failed))
                self.assertEqual(failed["sideEffects"], "none")

    def test_live_metadata_api_uses_injected_provider_and_persists_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            provider = FakeLiveMetadataProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Example Movie", year=2024),)
            )
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=lambda _ids: MetadataProviderRegistry(
                        (provider,)
                    ),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                status, evidence = request(
                    api,
                    f"/api/v1/configuration/revisions/{validated.revision_id}/"
                    "recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated.version,
                        "expectedDigest": validated.digest,
                        "resourceLibraryId": "source",
                        "syntheticPath": "/电影/Example.Movie.2024.mkv",
                        "liveMetadata": True,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(evidence["result"]["mode"], "live")
                self.assertEqual(evidence["result"]["metadata"]["identity"]["providerId"], "42")
                status, detail = request(
                    api,
                    f"/api/v1/configuration/revisions/{validated.revision_id}/objects",
                )
                self.assertEqual(status, 200)
                reloaded = detail["recognitionStrategyTest"]
                self.assertFalse(reloaded["stale"])
                for key, value in evidence.items():
                    self.assertEqual(reloaded[key], value)
                self.assertEqual(provider.searches, 1)

    def test_strategy_test_api_projects_matched_ambiguous_unrecognized_and_failed_evidence(
        self,
    ) -> None:
        always = {"operator": "always", "children": []}
        cases = (
            (
                "matched",
                [
                    {
                        "id": "a-primary",
                        "name": "A primary",
                        "condition": always,
                        "outputRecognitionType": "A",
                        "priority": 200,
                        "score": 70,
                    },
                    {
                        "id": "a-secondary",
                        "name": "A secondary",
                        "condition": always,
                        "outputRecognitionType": "A",
                        "priority": 100,
                        "score": 20,
                    },
                ],
                "source",
                "matched",
                2,
                1,
                "review the matched rules and policy resolution",
                (),
            ),
            (
                "ambiguous",
                [
                    {
                        "id": "a-tie",
                        "name": "A tie",
                        "condition": always,
                        "outputRecognitionType": "A",
                        "priority": 100,
                        "score": 50,
                    },
                    {
                        "id": "b-tie",
                        "name": "B tie",
                        "condition": always,
                        "outputRecognitionType": "B",
                        "priority": 100,
                        "score": 50,
                    },
                ],
                "source",
                "ambiguous",
                2,
                2,
                "correct rule priorities or conditions",
                ("manual recognition is required",),
            ),
            (
                "unrecognized",
                [
                    {
                        "id": "never",
                        "name": "Never matches",
                        "condition": {
                            "field": "path",
                            "operator": "contains",
                            "value": "/never/",
                        },
                        "outputRecognitionType": "A",
                        "priority": 100,
                        "score": 100,
                    }
                ],
                "source",
                "unrecognized",
                0,
                0,
                "correct the selected ResourceLibrary context or RecognitionRules",
                (),
            ),
            (
                "failed",
                None,
                "missing",
                None,
                0,
                0,
                "correct and validate the Draft",
                (),
            ),
        )
        for (
            label,
            rules,
            library_id,
            outcome,
            matched_count,
            alternative_count,
            next_action,
            expected_warnings,
        ) in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = self._document(root)
                if rules is not None:
                    document["recognitionRules"] = copy.deepcopy(rules)
                with (
                    SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                    SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
                ):
                    service = ManagedConfigurationService(repository)
                    api = MediaFlowApi(
                        runtime_repository,
                        None,
                        principals=(
                            ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                        ),
                        configuration_service=service,
                        bootstrap_document=document,
                    )
                    draft = service.import_draft(document, actor="tester")
                    validated = service.validate(draft.revision_id, actor="tester")
                    with patch(
                        "mediaflow.infrastructure.runtime_configuration."
                        "RuntimeConfiguration.create_storages",
                        side_effect=AssertionError("Strategy Test must not construct Storage"),
                    ):
                        status, evidence = request(
                            api,
                            f"/api/v1/configuration/revisions/{validated.revision_id}/"
                            "recognition-strategy-test",
                            method="POST",
                            body={
                                "expectedVersion": validated.version,
                                "expectedDigest": validated.digest,
                                "resourceLibraryId": library_id,
                                "syntheticPath": "Example.Movie.2024.mkv",
                            },
                        )
                    self.assertEqual(status, 200)
                    status, detail = request(
                        api,
                        f"/api/v1/configuration/revisions/{validated.revision_id}/objects",
                    )
                    self.assertEqual(status, 200)
                    reloaded = detail["recognitionStrategyTest"]
                    self.assertFalse(reloaded["stale"])
                    for key, value in evidence.items():
                        self.assertEqual(reloaded[key], value)
                    self.assertEqual(evidence["sideEffects"], "none")
                    self.assertTrue(evidence["retrySafe"])
                    self.assertIn(next_action, evidence["nextAction"])
                    if outcome is None:
                        self.assertEqual(evidence["status"], "failed")
                        self.assertEqual(evidence["failureCategory"], "invalid_configuration")
                        self.assertIsNone(evidence["result"])
                        continue
                    self.assertEqual(evidence["status"], "completed")
                    recognition = evidence["result"]["recognition"]
                    self.assertEqual(recognition["status"], outcome)
                    self.assertEqual(len(recognition["matchedRules"]), matched_count)
                    self.assertEqual(len(recognition["alternatives"]), alternative_count)
                    self.assertEqual(tuple(recognition["warnings"]), expected_warnings)
                    if outcome == "matched":
                        self.assertEqual(evidence["result"]["effectiveMetadataPolicy"]["id"], "A")
                    else:
                        self.assertIsNone(evidence["result"]["effectiveMetadataPolicy"])
                    for item in recognition["matchedRules"]:
                        self.assertEqual(
                            set(item), {"ruleId", "recognitionType", "priority", "score"}
                        )
                    for item in recognition["alternatives"]:
                        self.assertEqual(set(item), {"recognitionType", "priority", "score"})

    def test_metadata_policy_crud_reference_and_exact_offline_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                current = service.import_draft(document, actor="tester")
                policy_a = next(
                    item for item in current.document["metadataPolicies"] if item["id"] == "A"
                )
                updated_policy = {
                    **policy_a,
                    "name": "Managed movie metadata",
                    "mediaQueryType": "movie",
                    "language": "ja-JP",
                    "region": "JP",
                    "automaticThreshold": 93,
                    "confirmationThreshold": 73,
                    "minimumScoreGap": 7,
                    "timeout": 12,
                    "retryCount": 3,
                    "maxCandidates": 17,
                    "maxSearchPages": 3,
                    "maxProviderRequests": 8,
                    "maxCandidateEnrichments": 4,
                    "enabled": True,
                }
                current = objects.mutate(
                    current.revision_id,
                    ConfigurationObjectKind.METADATA_POLICY,
                    object_id="A",
                    value=updated_policy,
                    expected_version=current.version,
                    actor="tester",
                )
                detail = objects.revision_detail(current.revision_id)
                stored = next(
                    item for item in detail["objects"]["metadataPolicies"] if item["id"] == "A"
                )
                self.assertEqual(stored, updated_policy)
                references = detail["references"]["metadata_policy:A"]
                self.assertGreaterEqual(references["total"], 1)
                self.assertTrue(
                    any(item["field"] == "metadataPolicy" for item in references["items"])
                )
                with self.assertRaises(ConfigurationObjectReferenced):
                    objects.mutate(
                        current.revision_id,
                        ConfigurationObjectKind.METADATA_POLICY,
                        object_id="A",
                        value=None,
                        expected_version=current.version,
                        actor="tester",
                        delete=True,
                    )

                current = objects.mutate(
                    current.revision_id,
                    ConfigurationObjectKind.METADATA_POLICY,
                    object_id=None,
                    value={"id": "temporary", "providerId": "tmdb", "enabled": False},
                    expected_version=current.version,
                    actor="tester",
                )
                current = objects.mutate(
                    current.revision_id,
                    ConfigurationObjectKind.METADATA_POLICY,
                    object_id="temporary",
                    value=None,
                    expected_version=current.version,
                    actor="tester",
                    delete=True,
                )
                validated = service.validate(current.revision_id, actor="tester")
                with (
                    patch(
                        "mediaflow.infrastructure.runtime_configuration."
                        "RuntimeConfiguration.create_storages",
                        side_effect=AssertionError(
                            "offline Strategy Test must not construct Storage"
                        ),
                    ),
                    patch(
                        "mediaflow.application.strategy_test.MetadataProviderRegistry",
                        side_effect=AssertionError(
                            "offline Strategy Test must not construct a Provider registry"
                        ),
                    ),
                    patch.object(
                        socket,
                        "create_connection",
                        side_effect=AssertionError(
                            "offline Strategy Test must not access the network"
                        ),
                    ),
                ):
                    evidence = objects.recognition_strategy_test(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        synthetic_path="/电影/Example.Movie.2024.mkv",
                    )
                effective = evidence.result["effectiveMetadataPolicy"]
                self.assertEqual(
                    {
                        key: effective[key]
                        for key in (
                            "id",
                            "providerId",
                            "mediaQueryType",
                            "language",
                            "region",
                            "automaticThreshold",
                            "confirmationThreshold",
                            "minimumScoreGap",
                            "timeout",
                            "maxCandidates",
                            "maxSearchPages",
                            "maxProviderRequests",
                            "maxCandidateEnrichments",
                            "enabled",
                        )
                    },
                    {
                        "id": "A",
                        "providerId": "tmdb",
                        "mediaQueryType": "movie",
                        "language": "ja-JP",
                        "region": "JP",
                        "automaticThreshold": 93.0,
                        "confirmationThreshold": 73.0,
                        "minimumScoreGap": 7.0,
                        "timeout": 12.0,
                        "maxCandidates": 17,
                        "maxSearchPages": 3,
                        "maxProviderRequests": 8,
                        "maxCandidateEnrichments": 4,
                        "enabled": True,
                    },
                )
                self.assertEqual(effective["retry"]["count"], 3)

                changed_policy = copy.deepcopy(updated_policy)
                changed_policy.update(
                    {"language": "ko-KR", "region": "KR", "maxProviderRequests": 9}
                )
                changed = objects.mutate(
                    validated.revision_id,
                    ConfigurationObjectKind.METADATA_POLICY,
                    object_id="A",
                    value=changed_policy,
                    expected_version=validated.version,
                    actor="tester",
                )
                self.assertTrue(
                    objects.revision_detail(changed.revision_id)["recognitionStrategyTest"]["stale"]
                )
                revalidated = service.validate(changed.revision_id, actor="tester")
                rerun = objects.recognition_strategy_test(
                    revalidated.revision_id,
                    expected_version=revalidated.version,
                    expected_digest=revalidated.digest,
                    actor="tester",
                    resource_library_id="source",
                    synthetic_path="/电影/Example.Movie.2024.mkv",
                )
                self.assertEqual(rerun.result["effectiveMetadataPolicy"]["language"], "ko-KR")
                self.assertEqual(rerun.result["effectiveMetadataPolicy"]["region"], "KR")
                self.assertEqual(rerun.result["effectiveMetadataPolicy"]["maxProviderRequests"], 9)

    def test_metadata_policy_validation_rejects_unknown_secret_and_invalid_semantics(self) -> None:
        base = {"id": "A", "providerId": "tmdb"}
        invalid = (
            {**base, "accessToken": "secret"},
            {**base, "language": "not_a_locale"},
            {**base, "region": "CHINA"},
            {**base, "mediaQueryType": "film"},
            {**base, "automaticThreshold": 50, "confirmationThreshold": 60},
            {**base, "timeout": 0},
            {**base, "retryCount": 11},
            {**base, "maxCandidates": 0},
            {**base, "maxProviderRequests": 101},
            {**base, "maxCandidateEnrichments": -1},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                ConfigurationObjectService._normalize(
                    ConfigurationObjectKind.METADATA_POLICY, value
                )

    def test_whole_document_validation_rejects_invalid_or_disabled_metadata_policy(self) -> None:
        cases = (
            ("unknown", {"accessToken": "literal-secret"}, "unsupported field"),
            ("locale", {"language": "not_a_locale"}, "language"),
            ("timeout", {"timeout": 0}, "limits"),
            ("disabled", {"enabled": False}, "disabled MetadataPolicy"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                for label, changes, expected in cases:
                    with self.subTest(label=label):
                        document = self._document(root)
                        document["metadataPolicies"][0].update(changes)
                        draft = service.import_draft(document, actor="tester")
                        result = service.validate(draft.revision_id, actor="tester")
                        self.assertEqual(result.status.value, "draft")
                        self.assertTrue(result.validation_errors)
                        self.assertIn(expected, result.validation_errors[0])

    def test_authenticated_api_exposes_metadata_policy_crud(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                draft = service.import_draft(document, actor="tester")
                collection = (
                    f"/api/v1/configuration/revisions/{draft.revision_id}/objects/metadataPolicies"
                )
                status, created = request(
                    api,
                    collection,
                    method="POST",
                    body={
                        "expectedVersion": draft.version,
                        "object": {
                            "id": "api-policy",
                            "name": "API policy",
                            "providerId": "tmdb",
                            "mediaQueryType": "movie",
                            "language": "zh-CN",
                            "region": "CN",
                            "enabled": True,
                        },
                    },
                )
                self.assertEqual(status, 200)
                status, updated = request(
                    api,
                    f"{collection}/api-policy",
                    method="PUT",
                    body={
                        "expectedVersion": created["version"],
                        "object": {
                            "id": "api-policy",
                            "name": "API policy",
                            "providerId": "tmdb",
                            "mediaQueryType": "movie",
                            "language": "ja-JP",
                            "region": "JP",
                            "enabled": False,
                        },
                    },
                )
                self.assertEqual(status, 200)
                status, detail = request(
                    api, f"/api/v1/configuration/revisions/{draft.revision_id}/objects"
                )
                self.assertEqual(status, 200)
                stored = next(
                    item
                    for item in detail["objects"]["metadataPolicies"]
                    if item["id"] == "api-policy"
                )
                self.assertEqual((stored["language"], stored["enabled"]), ("ja-JP", False))
                status, deleted = request(
                    api,
                    f"{collection}/api-policy",
                    method="DELETE",
                    body={"expectedVersion": updated["version"]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(deleted["version"], updated["version"] + 1)

    def test_recognition_object_crud_preserves_reference_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                current = service.import_draft(self._document(root), actor="tester")
                current = objects.mutate(
                    current.revision_id,
                    ConfigurationObjectKind.RECOGNITION_TYPE,
                    object_id=None,
                    value={"id": "D", "name": "Documentary", "enabled": True},
                    expected_version=current.version,
                    actor="tester",
                )
                current = objects.mutate(
                    current.revision_id,
                    ConfigurationObjectKind.RECOGNITION_RULE,
                    object_id=None,
                    value={
                        "id": "type-d-rule",
                        "name": "Documentary catch-all",
                        "condition": {"operator": "always", "children": []},
                        "outputRecognitionType": "D",
                        "priority": -100,
                        "score": 1,
                    },
                    expected_version=current.version,
                    actor="tester",
                )
                current = objects.mutate(
                    current.revision_id,
                    ConfigurationObjectKind.RECOGNITION_TYPE_POLICY,
                    object_id=None,
                    value={
                        "id": "type-D",
                        "name": "Documentary policy",
                        "recognitionType": "D",
                        "metadataPolicy": "A",
                        "namingPolicy": "A",
                        "classificationPolicy": "A",
                        "organizePolicy": "A",
                        "priority": 10,
                    },
                    expected_version=current.version,
                    actor="tester",
                )
                with self.assertRaises(ConfigurationObjectReferenced) as blocked:
                    objects.mutate(
                        current.revision_id,
                        ConfigurationObjectKind.RECOGNITION_TYPE,
                        object_id="D",
                        value=None,
                        expected_version=current.version,
                        actor="tester",
                        delete=True,
                    )
                self.assertEqual(blocked.exception.reference_count, 2)
                policy = next(
                    item
                    for item in current.document["recognitionTypePolicies"]
                    if item["id"] == "type-D"
                )
                policy = copy.deepcopy(policy)
                policy["priority"] = 11
                current = objects.mutate(
                    current.revision_id,
                    ConfigurationObjectKind.RECOGNITION_TYPE_POLICY,
                    object_id="type-D",
                    value=policy,
                    expected_version=current.version,
                    actor="tester",
                )
                for kind, object_id in (
                    (ConfigurationObjectKind.RECOGNITION_TYPE_POLICY, "type-D"),
                    (ConfigurationObjectKind.RECOGNITION_RULE, "type-d-rule"),
                    (ConfigurationObjectKind.RECOGNITION_TYPE, "D"),
                ):
                    current = objects.mutate(
                        current.revision_id,
                        kind,
                        object_id=object_id,
                        value=None,
                        expected_version=current.version,
                        actor="tester",
                        delete=True,
                    )
                validated = service.validate(current.revision_id, actor="tester")
                self.assertEqual(validated.status.value, "validated")

    def test_local_setup_check_calls_only_read_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            calls: list[str] = []

            class ProbeStorage:
                def exists(self, path):
                    calls.append(f"exists:{path}")
                    return True

                def stat(self, path):
                    calls.append(f"stat:{path}")
                    return SimpleNamespace(is_directory=True)

                def __getattr__(self, name):
                    if name in {
                        "write",
                        "create_directory",
                        "move",
                        "copy",
                        "delete",
                        "hard_link",
                        "soft_link",
                    }:

                        def forbidden(*args, **kwargs):
                            raise AssertionError(f"forbidden Storage operation: {name}")

                        return forbidden
                    raise AttributeError(name)

            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with (
                    patch(
                        "mediaflow.application.configuration_objects.load_runtime_configuration",
                        return_value=SimpleNamespace(
                            create_storages=lambda **kwargs: {
                                "source-storage": ProbeStorage(),
                                "media-target": ProbeStorage(),
                            }
                        ),
                    ),
                    patch.object(
                        ConfigurationObjectService,
                        "_check_path",
                        wraps=ConfigurationObjectService._check_path,
                    ) as checked_path,
                ):
                    evidence = objects.local_check(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        media_library_id="movies",
                    )
                self.assertEqual(evidence.status, ConfigurationSetupCheckStatus.PASSED)
                self.assertEqual(
                    calls, ["exists:incoming", "stat:incoming", "exists:Movies", "stat:Movies"]
                )
                self.assertEqual(
                    evidence.operations,
                    (
                        "runtime.load",
                        "storage.construct",
                        "source.exists",
                        "source.stat",
                        "destination.exists",
                        "destination.stat",
                    ),
                )
                self.assertEqual(evidence.document()["sideEffects"], "none")
                self.assertTrue(evidence.document()["retrySafe"])
                self.assertEqual(len(checked_path.call_args_list), 2)
                self.assertTrue(
                    all(
                        isinstance(call.args[0], ReadOnlyStorageGuard)
                        for call in checked_path.call_args_list
                    )
                )

    def test_setup_check_overall_deadline_covers_every_blocking_stage(self) -> None:
        for blocked_stage in ("loader", "constructor", "exists", "stat"):
            with (
                self.subTest(blocked_stage=blocked_stage),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                document = self._document(root)
                blocked = Event()
                release = Event()
                thread_names: list[str] = []
                blocked_once = False

                def wait_if_selected(stage: str) -> None:
                    nonlocal blocked_once
                    thread_names.append(current_thread().name)
                    if blocked_stage == stage and not blocked_once:
                        blocked_once = True
                        blocked.set()
                        if not release.wait(2):
                            raise AssertionError("test did not release setup-check worker")

                class ProbeStorage:
                    def exists(self, path):
                        wait_if_selected("exists")
                        return True

                    def stat(self, path):
                        wait_if_selected("stat")
                        return SimpleNamespace(is_directory=True)

                class ProbeRuntime:
                    def create_storages(self, **kwargs):
                        wait_if_selected("constructor")
                        return {
                            "source-storage": ProbeStorage(),
                            "media-target": ProbeStorage(),
                        }

                def load_runtime(_document):
                    wait_if_selected("loader")
                    return ProbeRuntime()

                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    service = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(service, setup_check_timeout_seconds=0.03)
                    draft = service.import_draft(document, actor="tester")
                    validated = service.validate(draft.revision_id, actor="tester")
                    with patch(
                        "mediaflow.application.configuration_objects.load_runtime_configuration",
                        side_effect=load_runtime,
                    ):
                        started = time.monotonic()
                        evidence = objects.local_check(
                            validated.revision_id,
                            expected_version=validated.version,
                            expected_digest=validated.digest,
                            actor="tester",
                            resource_library_id="source",
                            media_library_id="movies",
                        )
                        elapsed = time.monotonic() - started
                        self.assertTrue(blocked.wait(0.2))
                        self.assertLess(elapsed, 0.3)
                        self.assertEqual(evidence.status, ConfigurationSetupCheckStatus.FAILED)
                        self.assertEqual(evidence.failure_category, "timeout")
                        expected_operations = {
                            "loader": (),
                            "constructor": ("runtime.load",),
                            "exists": ("runtime.load", "storage.construct"),
                            "stat": (
                                "runtime.load",
                                "storage.construct",
                                "source.exists",
                            ),
                        }
                        self.assertEqual(evidence.operations, expected_operations[blocked_stage])
                        self.assertEqual(evidence.document()["sideEffects"], "none")
                        self.assertTrue(evidence.document()["retrySafe"])
                        self.assertEqual(objects.setup_checks_in_flight, 1)
                        persisted = repository.get_local_setup_check(validated.revision_id)
                        self.assertEqual(persisted, evidence)
                        with self.assertRaises(ConfigurationActivationConflict):
                            objects.activate_checked(
                                validated.revision_id,
                                expected_version=validated.version,
                                actor="tester",
                            )
                        self.assertIsNone(service.active())
                        release.set()
                        deadline = time.monotonic() + 1
                        while objects.setup_checks_in_flight and time.monotonic() < deadline:
                            time.sleep(0.005)
                        self.assertEqual(objects.setup_checks_in_flight, 0)
                        self.assertEqual(
                            repository.get_local_setup_check(validated.revision_id), evidence
                        )
                self.assertTrue(thread_names)
                self.assertTrue(
                    all(name.startswith("mediaflow-setup-check") for name in thread_names)
                )

    def test_timed_out_check_holds_capacity_until_exit_then_explicit_retry_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            blocked = Event()
            release = Event()
            loader_calls = 0

            class ProbeStorage:
                def exists(self, path):
                    return True

                def stat(self, path):
                    return SimpleNamespace(is_directory=True)

            runtime = SimpleNamespace(
                create_storages=lambda **kwargs: {
                    "source-storage": ProbeStorage(),
                    "media-target": ProbeStorage(),
                }
            )

            def load_runtime(_document):
                nonlocal loader_calls
                loader_calls += 1
                if loader_calls == 1:
                    blocked.set()
                    if not release.wait(2):
                        raise AssertionError("test did not release setup-check worker")
                return runtime

            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service, setup_check_timeout_seconds=0.03)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with patch(
                    "mediaflow.application.configuration_objects.load_runtime_configuration",
                    side_effect=load_runtime,
                ):
                    timed_out = objects.local_check(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        media_library_id="movies",
                    )
                    self.assertTrue(blocked.is_set())
                    self.assertEqual(timed_out.failure_category, "timeout")
                    self.assertEqual(objects.setup_checks_in_flight, 1)
                    started = time.monotonic()
                    saturated = objects.local_check(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        media_library_id="movies",
                    )
                    # Capacity rejection must be independent of the blocked worker's
                    # overall deadline. Keep enough scheduler margin for slower CI.
                    self.assertLess(time.monotonic() - started, 0.2)
                    self.assertEqual(saturated.failure_category, "capacity_unavailable")
                    self.assertEqual(loader_calls, 1)
                    self.assertEqual(objects.setup_checks_in_flight, 1)
                    release.set()
                    deadline = time.monotonic() + 1
                    while objects.setup_checks_in_flight and time.monotonic() < deadline:
                        time.sleep(0.005)
                    self.assertEqual(objects.setup_checks_in_flight, 0)
                    self.assertEqual(
                        repository.get_local_setup_check(validated.revision_id), timed_out
                    )
                    recovered = objects.local_check(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        media_library_id="movies",
                    )
                    self.assertEqual(recovered.status, ConfigurationSetupCheckStatus.PASSED)
                    self.assertEqual(loader_calls, 2)
                    self.assertEqual(objects.setup_checks_in_flight, 0)
                    self.assertEqual(
                        repository.get_local_setup_check(validated.revision_id), recovered
                    )

    def test_setup_check_read_only_guard_rejects_every_mutation(self) -> None:
        underlying_mutations: list[str] = []

        class ProbeStorage:
            def __getattr__(self, name):
                def mutation(*args, **kwargs):
                    underlying_mutations.append(name)

                return mutation

        guard = ReadOnlyStorageGuard(ProbeStorage())
        operations = (
            lambda: guard.write("file", b"data"),
            lambda: guard.create_directory("directory"),
            lambda: guard.move("source", "target"),
            lambda: guard.copy("source", "target"),
            lambda: guard.delete("file"),
            lambda: guard.hard_link("source", "target"),
            lambda: guard.soft_link("source", "target"),
        )
        for operation in operations:
            with self.assertRaises(ReadOnlyStorageMutationError):
                operation()
        self.assertEqual(underlying_mutations, [])
        self.assertEqual(guard.mutation_calls, {name: 1 for name in guard.mutation_calls})

    def test_stale_setup_check_identity_fails_before_capacity_or_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service, setup_check_timeout_seconds=0.03)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with patch(
                    "mediaflow.application.configuration_objects.load_runtime_configuration",
                    side_effect=AssertionError("stale identity must not construct Runtime"),
                ):
                    with self.assertRaises(ConfigurationVersionConflict):
                        objects.local_check(
                            validated.revision_id,
                            expected_version=validated.version - 1,
                            expected_digest=validated.digest,
                            actor="tester",
                        )
                self.assertEqual(objects.setup_checks_in_flight, 0)

    def test_api_setup_check_timeout_returns_actionable_read_only_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            blocked = Event()
            release = Event()

            def blocked_loader(_document):
                blocked.set()
                if not release.wait(2):
                    raise AssertionError("test did not release setup-check worker")
                raise AssertionError("late worker result must be ignored")

            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                objects = ConfigurationObjectService(service, setup_check_timeout_seconds=0.03)
                api._configuration_objects = objects
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with patch(
                    "mediaflow.application.configuration_objects.load_runtime_configuration",
                    side_effect=blocked_loader,
                ):
                    status, response = request(
                        api,
                        f"/api/v1/configuration/revisions/{validated.revision_id}/local-setup-check",
                        method="POST",
                        body={
                            "expectedVersion": validated.version,
                            "expectedDigest": validated.digest,
                            "resourceLibraryId": "source",
                            "mediaLibraryId": "movies",
                        },
                    )
                    self.assertEqual(status, 200)
                    self.assertTrue(blocked.is_set())
                    self.assertEqual(response["status"], "failed")
                    self.assertEqual(response["failureCategory"], "timeout")
                    self.assertEqual(response["sideEffects"], "none")
                    self.assertTrue(response["retrySafe"])
                    self.assertIn("wait for the in-flight check", response["nextAction"])
                    self.assertNotIn("admin-token", json.dumps(response))
                    self.assertIsNone(service.active())
                    release.set()
                    deadline = time.monotonic() + 1
                    while objects.setup_checks_in_flight and time.monotonic() < deadline:
                        time.sleep(0.005)
                    self.assertEqual(objects.setup_checks_in_flight, 0)

    def test_unrepresentable_setup_path_is_persisted_and_explicit_correction_recovers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            document["resourceLibraries"][0]["storagePath"] = "x" * (
                CONFIGURATION_SETUP_CHECK_PATH_LIMIT + 1
            )
            probe_calls: list[str] = []

            class ProbeStorage:
                def exists(self, path):
                    probe_calls.append(f"exists:{path}")
                    return True

                def stat(self, path):
                    probe_calls.append(f"stat:{path}")
                    return SimpleNamespace(is_directory=True)

            runtime = SimpleNamespace(
                create_storages=lambda **kwargs: {
                    "source-storage": ProbeStorage(),
                    "media-target": ProbeStorage(),
                }
            )
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with patch(
                    "mediaflow.application.configuration_objects.load_runtime_configuration",
                    return_value=runtime,
                ):
                    failed = objects.local_check(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        media_library_id="movies",
                    )
                self.assertEqual(failed.status, ConfigurationSetupCheckStatus.FAILED)
                self.assertEqual(failed.failure_category, "invalid_path")
                self.assertIsNone(failed.source_path)
                self.assertEqual(probe_calls, [])
                self.assertEqual(objects.setup_checks_in_flight, 0)
                self.assertEqual(repository.get_local_setup_check(validated.revision_id), failed)
                self.assertEqual(failed.revision_version, validated.version)
                self.assertEqual(failed.revision_digest, validated.digest)
                self.assertEqual(failed.document()["sideEffects"], "none")
                self.assertTrue(failed.document()["retrySafe"])
                self.assertIsNone(service.active())

                corrected = objects.mutate(
                    validated.revision_id,
                    ConfigurationObjectKind.RESOURCE_LIBRARY,
                    object_id="source",
                    value={
                        **validated.document["resourceLibraries"][0],
                        "storagePath": "incoming",
                    },
                    expected_version=validated.version,
                    actor="tester",
                )
                revalidated = service.validate(corrected.revision_id, actor="tester")
                with patch(
                    "mediaflow.application.configuration_objects.load_runtime_configuration",
                    return_value=runtime,
                ):
                    recovered = objects.local_check(
                        revalidated.revision_id,
                        expected_version=revalidated.version,
                        expected_digest=revalidated.digest,
                        actor="tester",
                        resource_library_id="source",
                        media_library_id="movies",
                    )
                self.assertEqual(recovered.status, ConfigurationSetupCheckStatus.PASSED)
                self.assertEqual(recovered.revision_id, failed.revision_id)
                self.assertGreater(recovered.revision_version, failed.revision_version)
                self.assertNotEqual(recovered.revision_digest, failed.revision_digest)
                self.assertEqual(repository.get_local_setup_check(recovered.revision_id), recovered)
                self.assertEqual(
                    probe_calls,
                    ["exists:incoming", "stat:incoming", "exists:Movies", "stat:Movies"],
                )

    def test_unexpected_worker_failure_is_redacted_persisted_and_releases_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "incoming").mkdir(parents=True)
            (root / "target" / "Movies").mkdir(parents=True)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with patch.object(
                    objects,
                    "_run_local_check",
                    side_effect=RuntimeError("SECRET-WORKER-DETAIL"),
                ):
                    failed = objects.local_check(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        media_library_id="movies",
                    )
                deadline = time.monotonic() + 1
                while objects.setup_checks_in_flight and time.monotonic() < deadline:
                    time.sleep(0.005)
                self.assertEqual(objects.setup_checks_in_flight, 0)
                self.assertEqual(failed.failure_category, "unavailable")
                self.assertNotIn("SECRET-WORKER-DETAIL", json.dumps(failed.document()))
                self.assertEqual(repository.get_local_setup_check(validated.revision_id), failed)
                self.assertIsNone(service.active())
                recovered = objects.local_check(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="source",
                    media_library_id="movies",
                )
                self.assertEqual(recovered.status, ConfigurationSetupCheckStatus.PASSED)

    def test_setup_evidence_persistence_failure_does_not_strand_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "incoming").mkdir(parents=True)
            (root / "target" / "Movies").mkdir(parents=True)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with (
                    patch.object(
                        repository,
                        "save_local_setup_check",
                        side_effect=RuntimeError("persistence unavailable"),
                    ),
                    self.assertRaisesRegex(RuntimeError, "persistence unavailable"),
                ):
                    objects.local_check(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        media_library_id="movies",
                    )
                deadline = time.monotonic() + 1
                while objects.setup_checks_in_flight and time.monotonic() < deadline:
                    time.sleep(0.005)
                self.assertEqual(objects.setup_checks_in_flight, 0)
                recovered = objects.local_check(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="source",
                    media_library_id="movies",
                )
                self.assertEqual(recovered.status, ConfigurationSetupCheckStatus.PASSED)

    def test_api_unrepresentable_setup_path_returns_actionable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            document["resourceLibraries"][0]["storagePath"] = "private-" + "x" * (
                CONFIGURATION_SETUP_CHECK_PATH_LIMIT
            )
            probe_calls: list[str] = []

            class ProbeStorage:
                def exists(self, path):
                    probe_calls.append("exists")
                    return True

                def stat(self, path):
                    probe_calls.append("stat")
                    return SimpleNamespace(is_directory=True)

            runtime = SimpleNamespace(
                create_storages=lambda **kwargs: {
                    "source-storage": ProbeStorage(),
                    "media-target": ProbeStorage(),
                }
            )
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with patch(
                    "mediaflow.application.configuration_objects.load_runtime_configuration",
                    return_value=runtime,
                ):
                    status, response = request(
                        api,
                        f"/api/v1/configuration/revisions/{validated.revision_id}/local-setup-check",
                        method="POST",
                        body={
                            "expectedVersion": validated.version,
                            "expectedDigest": validated.digest,
                            "resourceLibraryId": "source",
                            "mediaLibraryId": "movies",
                        },
                    )
                self.assertEqual(status, 200)
                self.assertEqual(response["status"], "failed")
                self.assertEqual(response["failureCategory"], "invalid_path")
                self.assertEqual(response["revisionId"], validated.revision_id)
                self.assertEqual(response["revisionVersion"], validated.version)
                self.assertEqual(response["revisionDigest"], validated.digest)
                self.assertEqual(response["sideEffects"], "none")
                self.assertTrue(response["retrySafe"])
                self.assertIn("correct the Draft", response["nextAction"])
                self.assertNotIn("private-", json.dumps(response))
                self.assertEqual(probe_calls, [])
                self.assertEqual(api._configuration_objects.setup_checks_in_flight, 0)
                self.assertIsNone(service.active())
                self.assertIsNotNone(config_repository.get_local_setup_check(validated.revision_id))

    def test_persisted_setup_evidence_survives_api_reload_edit_and_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configuration_path = root / "configuration.sqlite3"
            runtime_path = root / "runtime.sqlite3"
            document = self._document(root)
            document["resourceLibraries"][0]["storagePath"] = "x" * (
                CONFIGURATION_SETUP_CHECK_PATH_LIMIT + 1
            )

            class ProbeStorage:
                def exists(self, path):
                    return True

                def stat(self, path):
                    return SimpleNamespace(is_directory=True)

            runtime = SimpleNamespace(
                create_storages=lambda **kwargs: {
                    "source-storage": ProbeStorage(),
                    "media-target": ProbeStorage(),
                }
            )
            with SQLiteConfigurationRepository(configuration_path) as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                with patch(
                    "mediaflow.application.configuration_objects.load_runtime_configuration",
                    return_value=runtime,
                ):
                    failed = objects.local_check(
                        validated.revision_id,
                        expected_version=validated.version,
                        expected_digest=validated.digest,
                        actor="tester",
                        resource_library_id="source",
                        media_library_id="movies",
                    )
                revision_id = validated.revision_id
                failed_version = validated.version
                failed_digest = validated.digest
                self.assertEqual(failed.failure_category, "invalid_path")

            with (
                SQLiteConfigurationRepository(configuration_path) as repository,
                SQLiteTaskRepository(runtime_path) as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                detail_path = f"/api/v1/configuration/revisions/{revision_id}/objects"
                status, reloaded = request(api, detail_path)
                self.assertEqual(status, 200)
                evidence = reloaded["localSetupCheck"]
                self.assertEqual(evidence["status"], "failed")
                self.assertFalse(evidence["stale"])
                self.assertEqual(evidence["revisionId"], revision_id)
                self.assertEqual(evidence["revisionVersion"], failed_version)
                self.assertEqual(evidence["revisionDigest"], failed_digest)
                self.assertEqual(evidence["failureCategory"], "invalid_path")
                self.assertTrue(evidence["message"])
                self.assertEqual(evidence["operations"], ["runtime.load", "storage.construct"])
                self.assertIsInstance(evidence["durationMs"], int)
                self.assertEqual(evidence["sideEffects"], "none")
                self.assertTrue(evidence["retrySafe"])
                self.assertTrue(evidence["nextAction"])

                resource = dict(reloaded["objects"]["resourceLibraries"][0])
                resource["storagePath"] = "incoming"
                status, edited = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/"
                    "resourceLibraries/source",
                    method="PUT",
                    body={"object": resource, "expectedVersion": failed_version},
                )
                self.assertEqual(status, 200)
                self.assertEqual(edited["status"], "draft")
                status, draft_detail = request(api, detail_path)
                self.assertEqual(status, 200)
                self.assertTrue(draft_detail["localSetupCheck"]["stale"])

                status, revalidated = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/validate",
                    method="POST",
                    body={},
                )
                self.assertEqual(status, 200)
                self.assertEqual(revalidated["status"], "validated")
                status, validated_detail = request(api, detail_path)
                self.assertEqual(status, 200)
                self.assertTrue(validated_detail["localSetupCheck"]["stale"])

                current = service.require(revision_id)
                with patch(
                    "mediaflow.application.configuration_objects.load_runtime_configuration",
                    return_value=runtime,
                ):
                    status, passed = request(
                        api,
                        f"/api/v1/configuration/revisions/{revision_id}/local-setup-check",
                        method="POST",
                        body={
                            "expectedVersion": current.version,
                            "expectedDigest": current.digest,
                            "resourceLibraryId": "source",
                            "mediaLibraryId": "movies",
                        },
                    )
                self.assertEqual(status, 200)
                self.assertEqual(passed["status"], "passed")
                status, passed_detail = request(api, detail_path)
                self.assertEqual(status, 200)
                self.assertFalse(passed_detail["localSetupCheck"]["stale"])
                self.assertEqual(passed_detail["localSetupCheck"]["revisionId"], revision_id)
                self.assertEqual(
                    passed_detail["localSetupCheck"]["revisionVersion"], current.version
                )
                self.assertEqual(passed_detail["localSetupCheck"]["revisionDigest"], current.digest)
                self.assertIsNone(service.active())

    def test_missing_local_root_is_actionable_and_does_not_activate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                evidence = objects.local_check(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="source",
                    media_library_id="movies",
                )
                self.assertEqual(evidence.status, ConfigurationSetupCheckStatus.FAILED)
                self.assertEqual(evidence.failure_category, "missing_path")
                with self.assertRaises(Exception):
                    objects.activate_checked(
                        validated.revision_id,
                        expected_version=validated.version,
                        actor="tester",
                    )
                self.assertIsNone(service.active())

    def test_setup_evidence_becomes_stale_after_guided_edit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "incoming").mkdir(parents=True)
            (root / "target" / "Movies").mkdir(parents=True)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                objects.local_check(
                    validated.revision_id,
                    expected_version=validated.version,
                    expected_digest=validated.digest,
                    actor="tester",
                    resource_library_id="source",
                    media_library_id="movies",
                )
                changed_document = dict(validated.document)
                changed_document["mediaLibraries"] = [
                    {
                        "id": "movies",
                        "name": "Movies changed",
                        "storageId": "media-target",
                        "rootPath": "Movies",
                        "enabled": True,
                    },
                    changed_document["mediaLibraries"][1],
                ]
                edited = service.edit_draft(
                    validated.revision_id,
                    changed_document,
                    expected_version=validated.version,
                    actor="tester",
                )
                detail = objects.revision_detail(edited.revision_id)
                self.assertTrue(detail["localSetupCheck"]["stale"])
                with self.assertRaises(ConfigurationActivationConflict):
                    objects.activate_checked(
                        edited.revision_id,
                        expected_version=edited.version,
                        actor="tester",
                    )

    def test_concurrent_guided_edits_have_one_winner_and_one_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")

                def edit(name: str):
                    try:
                        return objects.mutate(
                            draft.revision_id,
                            ConfigurationObjectKind.MEDIA_LIBRARY,
                            object_id="movies",
                            value={
                                "id": "movies",
                                "name": name,
                                "storageId": "media-target",
                                "rootPath": "Movies",
                                "enabled": True,
                            },
                            expected_version=draft.version,
                            actor=name,
                        )
                    except Exception as error:  # one optimistic writer must lose
                        return error

                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(edit, ("winner-a", "winner-b")))
                self.assertEqual(sum(not isinstance(result, Exception) for result in results), 1)
                self.assertEqual(sum(isinstance(result, Exception) for result in results), 1)

    def test_large_sections_update_create_delete_without_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            document["storages"] = [
                {
                    "id": f"storage-{index:03d}",
                    "name": f"Storage {index}",
                    "type": "local",
                    "rootPath": str(root / f"storage-{index:03d}"),
                    "readOnly": True,
                }
                for index in range(257)
            ]
            document["resourceLibraries"] = [
                {
                    "id": f"resource-{index:03d}",
                    "name": f"Resource {index}",
                    "storageId": "storage-000",
                    "storagePath": f"incoming/{index:03d}",
                    "enabled": True,
                }
                for index in range(257)
            ]
            document["mediaLibraries"] = [
                {
                    "id": f"media-{index:03d}",
                    "name": f"Media {index}",
                    "storageId": "storage-000",
                    "rootPath": f"Movies/{index:03d}",
                    "enabled": True,
                }
                for index in range(257)
            ]
            original_sections = {
                section: copy.deepcopy(document[section])
                for section in ("storages", "resourceLibraries", "mediaLibraries")
            }
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                revision = service.import_draft(document, actor="tester")
                for kind, section in (
                    (ConfigurationObjectKind.STORAGE, "storages"),
                    (ConfigurationObjectKind.RESOURCE_LIBRARY, "resourceLibraries"),
                    (ConfigurationObjectKind.MEDIA_LIBRARY, "mediaLibraries"),
                ):
                    for index in (0, 128, 256):
                        value = copy.deepcopy(revision.document[section][index])
                        value["name"] = f"Edited {kind.value} {index}"
                        revision = objects.mutate(
                            revision.revision_id,
                            kind,
                            object_id=value["id"],
                            value=value,
                            expected_version=revision.version,
                            actor="tester",
                        )
                    values = revision.document[section]
                    self.assertEqual(len(values), 257)
                    self.assertEqual(
                        [item["id"] for item in values],
                        [item["id"] for item in original_sections[section]],
                    )
                    for index, item in enumerate(values):
                        expected = original_sections[section][index]
                        if index in {0, 128, 256}:
                            self.assertTrue(item["name"].startswith("Edited "))
                        else:
                            self.assertEqual(item, expected)
                created = objects.mutate(
                    revision.revision_id,
                    ConfigurationObjectKind.MEDIA_LIBRARY,
                    object_id=None,
                    value={
                        "id": "media-created",
                        "name": "Created",
                        "storageId": "storage-000",
                        "rootPath": "Movies/created",
                        "enabled": True,
                    },
                    expected_version=revision.version,
                    actor="tester",
                )
                self.assertEqual(len(created.document["mediaLibraries"]), 258)
                deleted = objects.mutate(
                    created.revision_id,
                    ConfigurationObjectKind.MEDIA_LIBRARY,
                    object_id="media-created",
                    value=None,
                    expected_version=created.version,
                    actor="tester",
                    delete=True,
                )
                self.assertEqual(len(deleted.document["mediaLibraries"]), 257)
                for section in document:
                    if section not in {"storages", "resourceLibraries", "mediaLibraries"}:
                        self.assertEqual(deleted.document[section], document[section])

    def test_malformed_or_duplicate_canonical_entries_fail_without_persistence(self) -> None:
        cases = {
            "missing-section": lambda document: document.pop("mediaLibraries"),
            "non-array": lambda document: document.__setitem__("mediaLibraries", {}),
            "non-object": lambda document: document["mediaLibraries"].append("invalid"),
            "missing-id": lambda document: document["mediaLibraries"].append(
                {"name": "missing", "storageId": "media-target", "rootPath": "x"}
            ),
            "invalid-id": lambda document: document["mediaLibraries"].append(
                {
                    "id": "../escape",
                    "name": "unsafe",
                    "storageId": "media-target",
                    "rootPath": "x",
                }
            ),
            "duplicate-id": lambda document: document["mediaLibraries"].append(
                copy.deepcopy(document["mediaLibraries"][0])
            ),
        }
        for label, mutate_document in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = self._document(root)
                mutate_document(document)
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    service = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(service)
                    revision = service.import_draft(document, actor="tester")
                    before_version = revision.version
                    before_digest = revision.digest
                    before_document = copy.deepcopy(revision.document)
                    before_audits = len(repository.list_revision_audits(revision.revision_id))
                    with self.assertRaises(ValueError):
                        objects.mutate(
                            revision.revision_id,
                            ConfigurationObjectKind.MEDIA_LIBRARY,
                            object_id="movies",
                            value={
                                "id": "movies",
                                "name": "Changed",
                                "storageId": "media-target",
                                "rootPath": "Movies",
                                "enabled": True,
                            },
                            expected_version=revision.version,
                            actor="tester",
                        )
                    current = service.require(revision.revision_id)
                    self.assertEqual(current.version, before_version)
                    self.assertEqual(current.digest, before_digest)
                    self.assertEqual(current.document, before_document)
                    self.assertEqual(
                        len(repository.list_revision_audits(revision.revision_id)), before_audits
                    )

    def test_remote_storage_after_former_limit_survives_guided_edit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            document["storages"].extend(
                {
                    "id": f"local-{index:03d}",
                    "name": f"Local {index}",
                    "type": "local",
                    "rootPath": str(root / f"local-{index:03d}"),
                    "readOnly": True,
                }
                for index in range(255)
            )
            remote = {
                "id": "remote-after-256",
                "name": "Remote",
                "type": "openlist",
                "rootPath": "/",
                "options": {
                    "baseUrl": "https://example.invalid",
                    "tokenEnv": "OPENLIST_TOKEN",
                },
            }
            document["storages"].append(remote)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                revision = service.import_draft(document, actor="tester")
                changed = objects.mutate(
                    revision.revision_id,
                    ConfigurationObjectKind.STORAGE,
                    object_id="source-storage",
                    value={
                        "id": "source-storage",
                        "name": "Source changed",
                        "type": "local",
                        "rootPath": str(root / "source"),
                        "readOnly": True,
                    },
                    expected_version=revision.version,
                    actor="tester",
                )
                self.assertEqual(changed.document["storages"][-1], remote)
                displayed = objects.revision_detail(changed.revision_id)["objects"]["storages"][-1]
                self.assertEqual(displayed["options"]["tokenEnv"], "OPENLIST_TOKEN")
                self.assertTrue(displayed["readOnly"])

    def test_references_after_former_limit_block_each_delete(self) -> None:
        cases = (
            (
                "storage",
                ConfigurationObjectKind.STORAGE,
                "resourceLibraries",
                "target-storage",
            ),
            (
                "media",
                ConfigurationObjectKind.MEDIA_LIBRARY,
                "classificationPolicies",
                "target-media",
            ),
            (
                "resource",
                ConfigurationObjectKind.RESOURCE_LIBRARY,
                "recognitionRules",
                "target-resource",
            ),
        )
        for label, kind, section, target_id in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = self._document(root)
                if label == "storage":
                    document["storages"].append(
                        {
                            "id": target_id,
                            "name": "Target",
                            "type": "local",
                            "rootPath": str(root / "target-storage"),
                            "readOnly": True,
                        }
                    )
                    document["resourceLibraries"] = [
                        {
                            "id": f"resource-{index:03d}",
                            "name": f"Resource {index}",
                            "storageId": "source-storage" if index < 256 else target_id,
                            "storagePath": "incoming",
                            "enabled": True,
                        }
                        for index in range(257)
                    ]
                elif label == "media":
                    document["mediaLibraries"].append(
                        {
                            "id": target_id,
                            "name": "Target",
                            "storageId": "media-target",
                            "rootPath": "Target",
                            "enabled": True,
                        }
                    )
                    document["classificationPolicies"] = [
                        {
                            "id": f"classification-{index:03d}",
                            "rules": (
                                [{"id": "target-rule", "result": {"mediaLibraryId": target_id}}]
                                if index == 256
                                else []
                            ),
                        }
                        for index in range(257)
                    ]
                else:
                    document["resourceLibraries"].append(
                        {
                            "id": target_id,
                            "name": "Target",
                            "storageId": "source-storage",
                            "storagePath": "incoming",
                            "enabled": True,
                        }
                    )
                    document["recognitionRules"] = [
                        {
                            "id": f"recognition-{index:03d}",
                            "priority": 1,
                            "condition": (
                                {"field": "resourceLibraryId", "value": target_id}
                                if index == 256
                                else {"field": "resourceLibraryId", "value": "source"}
                            ),
                            "outputRecognitionType": "A",
                        }
                        for index in range(257)
                    ]
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    service = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(service)
                    revision = service.import_draft(document, actor="tester")
                    with self.assertRaises(ConfigurationObjectReferenced) as context:
                        objects.mutate(
                            revision.revision_id,
                            kind,
                            object_id=target_id,
                            value=None,
                            expected_version=revision.version,
                            actor="tester",
                            delete=True,
                        )
                    error = context.exception
                    self.assertEqual(error.reference_count, 1)
                    self.assertFalse(error.references_truncated)
                    expected_label = {
                        "storage": "resource-256",
                        "media": "classification-256",
                        "resource": "recognition-256",
                    }[label]
                    self.assertIn(expected_label, error.references[0])
                    evidence = objects.references(revision.revision_id)[f"{kind.value}:{target_id}"]
                    self.assertEqual(evidence["total"], 1)
                    self.assertEqual(evidence["items"][0]["id"], expected_label)
                    self.assertFalse(evidence["truncated"])

    def test_referenced_delete_reports_exact_count_and_truncated_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            target_id = "reference-target"
            document["storages"].append(
                {
                    "id": target_id,
                    "name": "Target",
                    "type": "local",
                    "rootPath": str(root / "reference-target"),
                    "readOnly": True,
                }
            )
            document["resourceLibraries"] = [
                {
                    "id": f"reference-{index:03d}",
                    "name": f"Reference {index}",
                    "storageId": target_id,
                    "storagePath": "incoming",
                    "enabled": True,
                }
                for index in range(257)
            ]
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                revision = service.import_draft(document, actor="tester")
                before = service.require(revision.revision_id)
                before_audits = len(repository.list_revision_audits(revision.revision_id))
                with self.assertRaises(ConfigurationObjectReferenced) as context:
                    objects.mutate(
                        revision.revision_id,
                        ConfigurationObjectKind.STORAGE,
                        object_id=target_id,
                        value=None,
                        expected_version=revision.version,
                        actor="tester",
                        delete=True,
                    )
                error = context.exception
                self.assertEqual(error.reference_count, 257)
                self.assertEqual(len(error.references), 32)
                self.assertTrue(error.references_truncated)
                after = service.require(revision.revision_id)
                self.assertEqual(after.version, before.version)
                self.assertEqual(after.digest, before.digest)
                self.assertEqual(after.document, before.document)
                self.assertEqual(
                    len(repository.list_revision_audits(revision.revision_id)), before_audits
                )

    def test_revision_detail_returns_bounded_structured_reference_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            target_id = "reference-target"
            document["storages"].append(
                {
                    "id": target_id,
                    "name": "Target",
                    "type": "local",
                    "rootPath": str(root / "reference-target"),
                    "readOnly": True,
                }
            )
            document["resourceLibraries"] = [
                {
                    "id": f"reference-{index:03d}",
                    "name": f"Reference {index}",
                    "storageId": target_id,
                    "storagePath": "incoming",
                    "enabled": True,
                }
                for index in range(40)
            ]
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                evidence = objects.revision_detail(draft.revision_id)["references"][
                    f"storage:{target_id}"
                ]
                self.assertEqual(evidence["total"], 40)
                self.assertEqual(len(evidence["items"]), 32)
                self.assertTrue(evidence["truncated"])
                self.assertEqual(
                    evidence["items"][0],
                    {
                        "section": "resourceLibraries",
                        "id": "reference-000",
                        "field": "storageId",
                    },
                )
                self.assertEqual(evidence["items"][-1]["id"], "reference-031")

    def test_revision_detail_reference_counts_are_exact_at_boundaries(self) -> None:
        for count in (0, 1, 32, 33, 257):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = self._document(root)
                target_id = "reference-target"
                document["storages"].append(
                    {
                        "id": target_id,
                        "name": "Target",
                        "type": "local",
                        "rootPath": str(root / "reference-target"),
                        "readOnly": True,
                    }
                )
                document["resourceLibraries"] = [
                    {
                        "id": f"reference-{index:03d}",
                        "name": f"Reference {index}",
                        "storageId": target_id,
                        "storagePath": "incoming",
                        "enabled": True,
                    }
                    for index in range(count)
                ]
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    service = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(service)
                    draft = service.import_draft(document, actor="tester")
                    evidence = objects.revision_detail(draft.revision_id)["references"][
                        f"storage:{target_id}"
                    ]
                    self.assertEqual(evidence["total"], count)
                    self.assertLessEqual(len(evidence["items"]), 32)
                    self.assertEqual(evidence["truncated"], count > 32)

    def test_malformed_storage_and_recognition_references_fail_closed(self) -> None:
        cases = (
            (
                "resource-storage-missing",
                ConfigurationObjectKind.STORAGE,
                "source-storage",
                lambda document: document["resourceLibraries"].__setitem__(
                    0,
                    {
                        key: value
                        for key, value in document["resourceLibraries"][0].items()
                        if key != "storageId"
                    },
                ),
            ),
            (
                "resource-storage-non-string",
                ConfigurationObjectKind.STORAGE,
                "source-storage",
                lambda document: document["resourceLibraries"].__setitem__(
                    0, {**document["resourceLibraries"][0], "storageId": 7}
                ),
            ),
            (
                "resource-storage-empty",
                ConfigurationObjectKind.STORAGE,
                "source-storage",
                lambda document: document["resourceLibraries"].__setitem__(
                    0, {**document["resourceLibraries"][0], "storageId": ""}
                ),
            ),
            (
                "media-storage-missing",
                ConfigurationObjectKind.STORAGE,
                "media-target",
                lambda document: document["mediaLibraries"].__setitem__(
                    0,
                    {
                        key: value
                        for key, value in document["mediaLibraries"][0].items()
                        if key != "storageId"
                    },
                ),
            ),
            (
                "media-storage-non-string",
                ConfigurationObjectKind.STORAGE,
                "media-target",
                lambda document: document["mediaLibraries"].__setitem__(
                    0, {**document["mediaLibraries"][0], "storageId": 7}
                ),
            ),
            (
                "media-storage-empty",
                ConfigurationObjectKind.STORAGE,
                "media-target",
                lambda document: document["mediaLibraries"].__setitem__(
                    0, {**document["mediaLibraries"][0], "storageId": ""}
                ),
            ),
            (
                "resource-condition-missing",
                ConfigurationObjectKind.RESOURCE_LIBRARY,
                "source",
                lambda document: document["recognitionRules"].__setitem__(
                    0,
                    {
                        key: value
                        for key, value in document["recognitionRules"][0].items()
                        if key != "condition"
                    },
                ),
            ),
            (
                "resource-condition-non-object",
                ConfigurationObjectKind.RESOURCE_LIBRARY,
                "source",
                lambda document: document["recognitionRules"].__setitem__(
                    0, {**document["recognitionRules"][0], "condition": []}
                ),
            ),
        )
        for label, kind, object_id, corrupt in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = self._document(root)
                corrupt(document)
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    service = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(service)
                    draft = service.import_draft(document, actor="tester")
                    with self.assertRaises(ValueError):
                        objects.mutate(
                            draft.revision_id,
                            kind,
                            object_id=object_id,
                            value=None,
                            expected_version=draft.version,
                            actor="tester",
                            delete=True,
                        )
                    current = service.require(draft.revision_id)
                    self.assertEqual(current.version, draft.version)
                    self.assertEqual(current.document, draft.document)

    def test_malformed_reference_shapes_fail_closed_without_mutation(self) -> None:
        cases = (
            ("rules must be an array", {"rules": {"bad": {"mediaLibraryId": "target-media"}}}),
            ("rule must be an object", {"rules": ["bad"]}),
            ("result must be an object", {"rules": [{"result": "bad"}]}),
        )
        for label, malformed in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = self._document(root)
                document["mediaLibraries"].append(
                    {
                        "id": "target-media",
                        "name": "Target",
                        "storageId": "media-target",
                        "rootPath": "Target",
                        "enabled": True,
                    }
                )
                document["classificationPolicies"] = [{"id": "broken", **malformed}]
                with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                    service = ManagedConfigurationService(repository)
                    objects = ConfigurationObjectService(service)
                    draft = service.import_draft(document, actor="tester")
                    with self.assertRaises(ValueError) as context:
                        objects.mutate(
                            draft.revision_id,
                            ConfigurationObjectKind.MEDIA_LIBRARY,
                            object_id="target-media",
                            value=None,
                            expected_version=draft.version,
                            actor="tester",
                            delete=True,
                        )
                    self.assertIn("classificationPolicies[0]", str(context.exception))
                    current = service.require(draft.revision_id)
                    self.assertEqual(current.version, draft.version)
                    self.assertEqual(current.digest, draft.digest)
                    self.assertEqual(current.document, draft.document)

    def test_malformed_guided_references_leave_raw_draft_recovery_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            target_id = "unreferenced-media"
            document["mediaLibraries"].append(
                {
                    "id": target_id,
                    "name": "Unreferenced",
                    "storageId": "media-target",
                    "rootPath": "Unreferenced",
                    "enabled": True,
                }
            )
            document["classificationPolicies"] = [
                {
                    "id": "broken",
                    "rules": {"mediaLibraryId": target_id},
                }
            ]
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                draft = service.import_draft(document, actor="tester")
                target_path = (
                    f"/api/v1/configuration/revisions/{draft.revision_id}"
                    f"/objects/mediaLibraries/{target_id}"
                )
                before = service.require(draft.revision_id)
                before_audits = len(config_repository.list_revision_audits(draft.revision_id))
                status, guided_error = request(
                    api,
                    target_path,
                    method="DELETE",
                    body={"expectedVersion": draft.version},
                )
                self.assertEqual(status, 400)
                self.assertEqual(guided_error["error"]["code"], "invalid_request")
                self.assertIn("classificationPolicies[0].rules", guided_error["error"]["message"])
                after_failure = service.require(draft.revision_id)
                self.assertEqual(after_failure.version, before.version)
                self.assertEqual(after_failure.digest, before.digest)
                self.assertEqual(after_failure.document, before.document)
                self.assertEqual(
                    len(config_repository.list_revision_audits(draft.revision_id)), before_audits
                )
                status, raw = request(api, f"/api/v1/configuration/revisions/{draft.revision_id}")
                self.assertEqual(status, 200)
                self.assertEqual(raw["document"], document)
                corrected = copy.deepcopy(document)
                corrected["classificationPolicies"] = [
                    {
                        "id": "fixed",
                        "rules": [],
                    }
                ]
                status, saved = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}",
                    method="PUT",
                    body={"document": corrected, "expectedVersion": draft.version},
                )
                self.assertEqual(status, 200)
                self.assertEqual(saved["version"], draft.version + 1)
                status, guided = request(
                    api, f"/api/v1/configuration/revisions/{draft.revision_id}/objects"
                )
                self.assertEqual(status, 200)
                self.assertIn(
                    target_id,
                    [item["id"] for item in guided["objects"]["mediaLibraries"]],
                )
                status, deleted = request(
                    api,
                    target_path,
                    method="DELETE",
                    body={"expectedVersion": saved["version"]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(deleted["version"], saved["version"] + 1)
                current = service.require(draft.revision_id)
                self.assertNotIn(
                    target_id,
                    [item["id"] for item in current.document["mediaLibraries"]],
                )
                audits = config_repository.list_revision_audits(draft.revision_id)
                self.assertEqual(
                    sum(
                        audit.safe_after().get("objectChange", {}).get("action") == "guided_delete"
                        and audit.safe_after().get("objectChange", {}).get("objectId") == target_id
                        for audit in audits
                    ),
                    1,
                )

    def test_api_reference_conflict_contains_shared_structured_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            target_id = "reference-target"
            document["storages"].append(
                {
                    "id": target_id,
                    "name": "Target",
                    "type": "local",
                    "rootPath": str(root / "reference-target"),
                    "readOnly": True,
                }
            )
            document["resourceLibraries"] = [
                {
                    "id": f"reference-{index:03d}",
                    "name": f"Reference {index}",
                    "storageId": target_id,
                    "storagePath": "incoming",
                    "enabled": True,
                }
                for index in range(257)
            ]
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                draft = service.import_draft(document, actor="tester")
                before = service.require(draft.revision_id)
                before_audits = len(config_repository.list_revision_audits(draft.revision_id))
                status, response = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/objects/storages/{target_id}",
                    method="DELETE",
                    body={"expectedVersion": draft.version},
                )
                self.assertEqual(status, 409)
                evidence = response["error"]["details"]["referenceEvidence"]
                self.assertEqual(evidence["total"], 257)
                self.assertEqual(len(evidence["items"]), 32)
                self.assertTrue(evidence["truncated"])
                self.assertEqual(evidence["items"][0]["section"], "resourceLibraries")
                after = service.require(draft.revision_id)
                self.assertEqual(after.version, before.version)
                self.assertEqual(after.digest, before.digest)
                self.assertEqual(after.document, before.document)
                self.assertEqual(
                    len(config_repository.list_revision_audits(draft.revision_id)), before_audits
                )

    def test_api_stale_conflict_and_reference_conflict_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            document["storages"].append(
                {
                    "id": "reference-target",
                    "name": "Target",
                    "type": "local",
                    "rootPath": str(root / "reference-target"),
                    "readOnly": True,
                }
            )
            document["resourceLibraries"] = [
                {
                    "id": f"reference-{index:03d}",
                    "name": f"Reference {index}",
                    "storageId": "reference-target",
                    "storagePath": "incoming",
                    "enabled": True,
                }
                for index in range(40)
            ]
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, draft = request(
                    api, "/api/v1/configuration/drafts", method="POST", body={"document": document}
                )
                self.assertEqual(status, 201)
                status, conflict = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/objects/storages/reference-target",
                    method="DELETE",
                    body={"expectedVersion": draft["version"]},
                )
                self.assertEqual(status, 409)
                details = conflict["error"]["details"]
                self.assertEqual(details["referenceCount"], 40)
                self.assertTrue(details["referencesTruncated"])
                status, first = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/objects/storages",
                    method="POST",
                    body={
                        "expectedVersion": draft["version"],
                        "object": {
                            "id": "extra",
                            "name": "Extra",
                            "type": "local",
                            "rootPath": str(root / "extra"),
                            "readOnly": True,
                        },
                    },
                )
                self.assertEqual(status, 200)
                status, stale = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/objects/storages",
                    method="POST",
                    body={
                        "expectedVersion": draft["version"],
                        "object": {
                            "id": "another",
                            "name": "Another",
                            "type": "local",
                            "rootPath": str(root / "another"),
                            "readOnly": True,
                        },
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(stale["error"]["code"], "configuration_version_conflict")
                self.assertEqual(
                    len(config_repository.list_revision_audits(draft["revisionId"])), 2
                )

    def test_api_malformed_section_returns_400_without_partial_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            document["mediaLibraries"].append("invalid")
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                draft = service.import_draft(document, actor="tester")
                status, response = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/objects/mediaLibraries/movies",
                    method="PUT",
                    body={
                        "expectedVersion": draft.version,
                        "object": {
                            "id": "movies",
                            "name": "Changed",
                            "storageId": "media-target",
                            "rootPath": "Movies",
                            "enabled": True,
                        },
                    },
                )
                self.assertEqual(status, 400)
                self.assertEqual(response["error"]["code"], "invalid_request")
                current = service.require(draft.revision_id)
                self.assertEqual(current.version, draft.version)
                self.assertEqual(current.digest, draft.digest)
                self.assertEqual(current.document, draft.document)
                self.assertEqual(len(config_repository.list_revision_audits(draft.revision_id)), 1)

    def test_raw_and_guided_edits_share_one_revision_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(service)
                draft = service.import_draft(document, actor="tester")
                raw_document = copy.deepcopy(draft.document)
                raw_document["mediaLibraries"][0]["name"] = "Raw first"
                raw = service.edit_draft(
                    draft.revision_id,
                    raw_document,
                    expected_version=draft.version,
                    actor="tester",
                )
                guided = objects.mutate(
                    raw.revision_id,
                    ConfigurationObjectKind.MEDIA_LIBRARY,
                    object_id="movies",
                    value={
                        "id": "movies",
                        "name": "Guided after raw",
                        "storageId": "media-target",
                        "rootPath": "Movies",
                        "enabled": True,
                    },
                    expected_version=raw.version,
                    actor="tester",
                )
                self.assertEqual(
                    (draft.revision_id, raw.version, guided.version),
                    (guided.revision_id, 2, 3),
                )
                self.assertNotEqual(raw.digest, guided.digest)

                second = service.import_draft(document, actor="tester")
                guided_first = objects.mutate(
                    second.revision_id,
                    ConfigurationObjectKind.MEDIA_LIBRARY,
                    object_id="movies",
                    value={
                        "id": "movies",
                        "name": "Guided first",
                        "storageId": "media-target",
                        "rootPath": "Movies",
                        "enabled": True,
                    },
                    expected_version=second.version,
                    actor="tester",
                )
                raw_after_guided = copy.deepcopy(guided_first.document)
                raw_after_guided["mediaLibraries"][0]["name"] = "Raw after guided"
                raw_final = service.edit_draft(
                    guided_first.revision_id,
                    raw_after_guided,
                    expected_version=guided_first.version,
                    actor="tester",
                )
                self.assertEqual(
                    (second.revision_id, guided_first.version, raw_final.version),
                    (raw_final.revision_id, 2, 3),
                )
                self.assertEqual(
                    raw_final.document["mediaLibraries"][0]["name"], "Raw after guided"
                )

    def test_api_large_guided_update_returns_complete_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            document["mediaLibraries"] = [
                {
                    "id": f"media-{index:03d}",
                    "name": f"Media {index}",
                    "storageId": "media-target",
                    "rootPath": f"Movies/{index:03d}",
                    "enabled": True,
                }
                for index in range(257)
            ]
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                draft = service.import_draft(document, actor="tester")
                target = copy.deepcopy(document["mediaLibraries"][256])
                target["name"] = "Last changed"
                status, changed = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/objects/mediaLibraries/{target['id']}",
                    method="PUT",
                    body={"expectedVersion": draft.version, "object": target},
                )
                self.assertEqual(status, 200)
                status, detail = request(
                    api, f"/api/v1/configuration/revisions/{draft.revision_id}/objects"
                )
                self.assertEqual(status, 200)
                values = detail["objects"]["mediaLibraries"]
                self.assertEqual(len(values), 257)
                self.assertEqual(values[0]["id"], "media-000")
                self.assertEqual(values[-1]["id"], "media-256")
                self.assertEqual(values[-1]["name"], "Last changed")
                self.assertEqual(changed["version"], draft.version + 1)

    def test_concurrent_api_guided_edits_have_one_winner_and_one_audited_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, draft = request(
                    api, "/api/v1/configuration/drafts", method="POST", body={"document": document}
                )
                self.assertEqual(status, 201)
                body = {
                    "expectedVersion": draft["version"],
                    "object": {
                        "id": "movies",
                        "name": "Concurrent",
                        "storageId": "media-target",
                        "rootPath": "Movies",
                        "enabled": True,
                    },
                }

                def edit() -> tuple[int, dict]:
                    return request(
                        api,
                        f"/api/v1/configuration/revisions/{draft['revisionId']}/objects/mediaLibraries/movies",
                        method="PUT",
                        body=body,
                    )

                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(lambda _index: edit(), (0, 1)))
                self.assertEqual(sum(status == 200 for status, _ in results), 1)
                self.assertEqual(sum(status == 409 for status, _ in results), 1)
                loser = next(value for status, value in results if status == 409)
                self.assertEqual(loser["error"]["code"], "configuration_version_conflict")
                audits = config_repository.list_revision_audits(draft["revisionId"])
                self.assertEqual(sum(audit.action == "draft_edit" for audit in audits), 1)

    def test_api_guided_objects_check_and_checked_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "incoming").mkdir(parents=True)
            (root / "target" / "Movies").mkdir(parents=True)
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(config_repository)
                principal = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(principal,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, draft = request(
                    api, "/api/v1/configuration/drafts", method="POST", body={"document": document}
                )
                self.assertEqual(status, 201)
                revision_id = draft["revisionId"]
                status, detail = request(
                    api, f"/api/v1/configuration/revisions/{revision_id}/objects"
                )
                self.assertEqual(status, 200)
                self.assertEqual(detail["objects"]["resourceLibraries"][0]["id"], "source")
                status, created = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages",
                    method="POST",
                    body={
                        "expectedVersion": draft["version"],
                        "object": {
                            "id": "extra",
                            "name": "Extra",
                            "type": "local",
                            "rootPath": str(root / "target"),
                            "readOnly": True,
                        },
                    },
                )
                self.assertEqual(status, 200)
                status, updated = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/extra",
                    method="PUT",
                    body={
                        "expectedVersion": created["version"],
                        "object": {
                            "id": "extra",
                            "name": "Extra updated",
                            "type": "local",
                            "rootPath": str(root / "target"),
                            "readOnly": True,
                        },
                    },
                )
                self.assertEqual(status, 200)
                status, deleted = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/extra",
                    method="DELETE",
                    body={"expectedVersion": updated["version"]},
                )
                self.assertEqual(status, 200)
                status, validated = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/validate",
                    method="POST",
                    body={},
                )
                self.assertEqual(status, 200)
                status, evidence = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/local-setup-check",
                    method="POST",
                    body={
                        "expectedVersion": validated["version"],
                        "expectedDigest": validated["digest"],
                        "resourceLibraryId": "source",
                        "mediaLibraryId": "movies",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(evidence["status"], "passed")
                status, active = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/recognition-strategy-test",
                    method="POST",
                    body={
                        "expectedVersion": validated["version"],
                        "expectedDigest": validated["digest"],
                        "resourceLibraryId": "source",
                        "syntheticPath": "Example.Movie.2024.1080p.mkv",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(active["status"], "completed")
                status, precheck = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/destination-precheck",
                    method="POST",
                    body={
                        "expectedVersion": validated["version"],
                        "expectedDigest": validated["digest"],
                        "recognitionType": "C",
                        "sample": {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(precheck["status"], "completed")
                status, active = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/activate",
                    method="POST",
                    body={"expectedVersion": validated["version"], "checked": True},
                )
                self.assertEqual(status, 200)
                self.assertEqual(active["status"], "active")
                status, job = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body={"command": "preview"},
                )
                self.assertEqual(status, 202)
                self.assertEqual(job["configuration_snapshot_id"], revision_id)
                self.assertEqual(job["configuration_snapshot_digest"], active["digest"])


if __name__ == "__main__":
    unittest.main()
