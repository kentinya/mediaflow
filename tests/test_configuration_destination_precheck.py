from __future__ import annotations

import copy
import sqlite3
import tempfile
import time
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.organizer import OrganizePlanner
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ConfigurationVersionConflict,
)
from mediaflow.domain.naming import NamingResult
from mediaflow.domain.organizer import ConflictStrategy
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageError, StorageErrorCode
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


class ManagedDestinationPrecheckTests(unittest.TestCase):
    @staticmethod
    def _document(root: Path) -> dict:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source-private")
        document["storages"][1]["rootPath"] = str(root / "target-private")
        return document

    @staticmethod
    def _sample() -> dict[str, object]:
        return {
            "title": "The Matrix",
            "mediaType": "movie",
            "year": 1999,
            "genres": ["Action"],
            "extension": "mkv",
        }

    @staticmethod
    def _tree_snapshot(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
        values = []
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            values.append(
                (
                    relative,
                    "directory" if path.is_dir() else "file",
                    None if path.is_dir() else path.read_bytes(),
                )
            )
        return tuple(values)

    def _open(self, root: Path, document: dict | None = None):
        repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        managed = ManagedConfigurationService(repository)
        objects = ConfigurationObjectService(managed)
        draft = managed.import_draft(document or self._document(root), actor="operator")
        return repository, managed, objects, draft

    def _run(self, objects, draft, sample=None):
        return objects.destination_precheck(
            draft.revision_id,
            expected_version=draft.version,
            expected_digest=draft.digest,
            actor="operator",
            recognition_type="C",
            sample=sample or self._sample(),
        )

    def _assert_revision_and_other_evidence_unchanged(self, repository, managed, revision) -> None:
        current = managed.require(revision.revision_id)
        self.assertEqual((current.version, current.digest), (revision.version, revision.digest))
        self.assertEqual(current.document, revision.document)
        self.assertIsNone(repository.get_naming_preview(revision.revision_id))
        self.assertIsNone(repository.get_classification_preview(revision.revision_id))
        self.assertIsNone(repository.get_organize_authority(revision.revision_id))
        self.assertIsNone(repository.get_destination_preview(revision.revision_id))
        self.assertIsNone(repository.get_local_setup_check(revision.revision_id))

    def test_success_partial_ancestor_c_identity_and_three_read_only_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target-private"
            (target / "Movies" / "Action").mkdir(parents=True)
            (root / "source-private").mkdir()
            before = self._tree_snapshot(target)
            repository, managed, objects, draft = self._open(root)
            try:
                evidence = self._run(objects, draft)
                result = evidence.result
                self.assertEqual(evidence.status.value, "completed")
                self.assertEqual(result["recognitionType"], "C")
                self.assertEqual(result["destinationStorageId"], "media-target")
                self.assertEqual(result["destinationStorageType"], "local")
                self.assertEqual(result["storageSupport"], "local_only")
                self.assertEqual(result["mediaLibraryId"], "movies")
                self.assertEqual(result["mediaLibraryRootPath"], "Movies")
                self.assertTrue(result["destinationRootExists"])
                self.assertTrue(result["destinationRootIsDirectory"])
                self.assertEqual(result["deepestExistingAncestor"], "Movies/Action")
                self.assertEqual(
                    result["directoriesToCreate"],
                    ["Movies/Action/The Matrix (1999) [tmdbid-synthetic]"],
                )
                self.assertFalse(result["targetExists"])
                self.assertEqual(result["conflictProjection"]["projectedOutcome"], "ready")
                self.assertEqual(result["requiredStorageCapabilities"], ["can_move"])
                self.assertIn("can_move", result["destinationStorageCapabilities"])
                self.assertEqual(result["missingStorageCapabilities"], [])
                self.assertEqual(result["verdict"], "ready")
                self.assertTrue(result["probeOperations"])
                self.assertEqual(set(result["guardMutationCalls"].values()), {0})
                self.assertEqual(evidence.document()["pathScope"], "storage_relative")
                self.assertEqual(evidence.document()["sideEffects"], "none")
                self.assertTrue(evidence.document()["retrySafe"])
                self.assertEqual(self._tree_snapshot(target), before)
                self.assertNotIn(str(root), repr(evidence.document()))
                self._assert_revision_and_other_evidence_unchanged(repository, managed, draft)
            finally:
                repository.close()

            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                second = managed.import_draft(self._document(root), actor="operator")

                def mutate(_planner, **kwargs):
                    kwargs["target_storage"].create_directory("forbidden")

                with patch.object(OrganizePlanner, "plan", mutate):
                    violation = self._run(objects, second)
                self.assertEqual(violation.failure_category, "read_only_violation")
                self.assertFalse(violation.document()["retrySafe"])
                self.assertIn("do not activate", violation.next_action)
                self.assertEqual(self._tree_snapshot(target), before)

    def test_conflict_projection_uses_production_resolver_for_every_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_root = root / "target-private"
            (target_root / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            relative = Path("Movies/Action/The Matrix (1999) [tmdbid-synthetic]")
            filename = "The Matrix (1999).mkv"
            (target_root / relative).mkdir(parents=True)
            (target_root / relative / filename).write_bytes(b"existing")
            (target_root / relative / "The Matrix (1999) (1).mkv").write_bytes(b"candidate")
            before = self._tree_snapshot(target_root)
            for strategy, expected in (
                (ConflictStrategy.SKIP, "skip"),
                (ConflictStrategy.RENAME, "rename"),
                (ConflictStrategy.OVERWRITE, "overwrite_requires_confirmation"),
                (ConflictStrategy.MANUAL, "manual_confirmation_required"),
            ):
                with self.subTest(strategy=strategy):
                    document = self._document(root)
                    policy = document["organizePolicies"][0]
                    policy["conflictStrategy"] = strategy.value
                    policy["overwrite"] = strategy is ConflictStrategy.OVERWRITE
                    repository, _, objects, draft = self._open(root, document)
                    try:
                        evidence = self._run(objects, draft)
                        projection = evidence.result["conflictProjection"]
                        self.assertEqual(projection["projectedOutcome"], expected)
                        self.assertIn("DESTINATION_EXISTS", projection["plannerConflicts"])
                        if strategy is ConflictStrategy.RENAME:
                            self.assertTrue(
                                projection["proposedRelativeDestination"].endswith(
                                    "The Matrix (1999) (2).mkv"
                                )
                            )
                        if strategy is ConflictStrategy.OVERWRITE:
                            self.assertIn(
                                "can_delete", evidence.result["requiredStorageCapabilities"]
                            )
                        self.assertEqual(evidence.result["authorityGranted"], "none")
                        self.assertEqual(self._tree_snapshot(target_root), before)
                    finally:
                        repository.close()

    def test_capability_gap_hardlink_cleanup_and_declared_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            document = self._document(root)
            document["organizePolicies"][0]["operation"] = "HARD_LINK"
            with patch.object(LocalStorage, "_can_hard_link", return_value=False):
                repository, _, objects, draft = self._open(root, document)
                try:
                    evidence = self._run(objects, draft)
                    self.assertEqual(evidence.result["verdict"], "capability_gap")
                    self.assertEqual(
                        evidence.result["missingStorageCapabilities"], ["can_hard_link"]
                    )
                    self.assertEqual(evidence.result["requiredByOperation"], "hard_link")
                    self.assertEqual(
                        evidence.result["fallback"],
                        "none; an unsupported capability is a failure",
                    )
                    self.assertTrue(evidence.result["destinationRootExists"])
                finally:
                    repository.close()

            readonly = self._document(root)
            readonly["storages"][1]["readOnly"] = True
            repository, _, objects, draft = self._open(root, readonly)
            try:
                evidence = self._run(objects, draft)
                self.assertEqual(evidence.result["verdict"], "capability_gap")
                self.assertEqual(evidence.result["destinationStorageCapabilities"], [])
                self.assertIn("can_move", evidence.result["missingStorageCapabilities"])
            finally:
                repository.close()

            cleanup = self._document(root)
            cleanup["organizePolicies"][0]["sourceDirectoryCleanup"]["mode"] = "empty"
            repository, _, objects, draft = self._open(root, cleanup)
            try:
                evidence = self._run(objects, draft)
                self.assertIn("can_delete", evidence.result["requiredStorageCapabilities"])
            finally:
                repository.close()

    def test_bounded_failure_categories_and_no_unsupported_adapter_construction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source-private").mkdir()
            variants = []
            remote = self._document(root)
            remote["storages"][1]["type"] = "s3"
            variants.append(("unsupported_storage_type", remote))
            missing = self._document(root)
            (root / "target-private").mkdir()
            variants.append(("missing_destination_root", missing))
            for category, document in variants:
                with self.subTest(category=category):
                    repository, managed, objects, draft = self._open(root, document)
                    try:
                        with (
                            patch.object(
                                RuntimeConfiguration,
                                "create_storages",
                                side_effect=AssertionError("unsupported adapter constructed"),
                            )
                            if category == "unsupported_storage_type"
                            else nullcontext()
                        ):
                            evidence = self._run(objects, draft)
                        self.assertEqual(evidence.failure_category, category)
                        self.assertLessEqual(len(evidence.message), 384)
                        self._assert_revision_and_other_evidence_unchanged(
                            repository, managed, draft
                        )
                    finally:
                        repository.close()

            target = root / "target-private"
            (target / "Movies").write_bytes(b"not-directory")
            repository, managed, objects, draft = self._open(root)
            try:
                evidence = self._run(objects, draft)
                self.assertEqual(evidence.failure_category, "destination_root_not_directory")
                self._assert_revision_and_other_evidence_unchanged(repository, managed, draft)
            finally:
                repository.close()

    def test_storage_error_depth_composition_capacity_and_timeout_categories(self) -> None:
        error_cases = (
            (StorageErrorCode.PERMISSION_DENIED, "permission_denied"),
            (StorageErrorCode.CONNECTION_FAILED, "unavailable"),
            (StorageErrorCode.TIMEOUT, "timeout"),
            (StorageErrorCode.INVALID_PATH, "invalid_path"),
        )
        for code, expected in error_cases:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "target-private" / "Movies").mkdir(parents=True)
                (root / "source-private").mkdir()
                repository, _, objects, draft = self._open(root)
                try:
                    with patch.object(
                        LocalStorage,
                        "exists",
                        side_effect=StorageError(code, "Exists", "Movies", "secret-value"),
                    ):
                        evidence = self._run(objects, draft)
                    self.assertEqual(evidence.failure_category, expected)
                    self.assertNotIn("secret-value", evidence.message)
                finally:
                    repository.close()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            repository, _, objects, draft = self._open(root)
            try:
                naming = NamingResult(
                    "deep",
                    "movie.mkv",
                    "A",
                    "C",
                    directory_segments=tuple(["deep"] * 65),
                )
                with patch(
                    "mediaflow.application.configuration_objects.NamingPreviewService.preview",
                    return_value=naming,
                ):
                    evidence = self._run(objects, draft)
                self.assertEqual(evidence.failure_category, "invalid_path")
            finally:
                repository.close()

    def test_all_composition_failure_categories_precede_storage_construction(self) -> None:
        variants = []
        missing = example_document()
        variants.append((missing, "missing", "missing_type_policy"))
        duplicate = example_document()
        duplicate["recognitionTypePolicies"].append(
            {**copy.deepcopy(duplicate["recognitionTypePolicies"][2]), "id": "type-C-copy"}
        )
        variants.append((duplicate, "C", "duplicate_type_policy"))
        disabled = example_document()
        disabled["recognitionTypes"][2]["enabled"] = False
        variants.append((disabled, "C", "recognition_type_disabled"))
        disabled_policy = example_document()
        next(value for value in disabled_policy["metadataPolicies"] if value["id"] == "C")[
            "enabled"
        ] = False
        variants.append((disabled_policy, "C", "policy_disabled"))
        dangling = example_document()
        dangling["recognitionTypePolicies"][2]["namingPolicy"] = "absent"
        variants.append((dangling, "C", "invalid_policy_reference"))
        unresolved = example_document()
        next(
            value
            for value in unresolved["classificationPolicies"][0]["rules"]
            if value["id"] == "action-movie"
        )["result"]["mediaLibraryId"] = "absent"
        variants.append((unresolved, "C", "unresolved_media_library"))
        unsafe = example_document()
        unsafe["mediaLibraries"][0]["rootPath"] = "../Movies"
        variants.append((unsafe, "C", "unsafe_destination"))

        for document, requested, expected in variants:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
                document["storages"][0]["rootPath"] = str(root / "source-private")
                document["storages"][1]["rootPath"] = str(root / "target-private")
                repository, managed, objects, draft = self._open(root, document)
                try:
                    with patch.object(
                        RuntimeConfiguration,
                        "create_storages",
                        side_effect=AssertionError("composition failure constructed Storage"),
                    ):
                        evidence = objects.destination_precheck(
                            draft.revision_id,
                            expected_version=draft.version,
                            expected_digest=draft.digest,
                            actor="operator",
                            recognition_type=requested,
                            sample=self._sample(),
                        )
                    self.assertEqual(evidence.failure_category, expected)
                    self.assertLessEqual(len(evidence.message), 384)
                    self._assert_revision_and_other_evidence_unchanged(repository, managed, draft)
                finally:
                    repository.close()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            bad = self._document(root)
            bad["recognitionTypePolicies"][2]["namingPolicy"] = "absent"
            repository, _, objects, draft = self._open(root, bad)
            try:
                with patch.object(
                    RuntimeConfiguration,
                    "create_storages",
                    side_effect=AssertionError("composition failure constructed Storage"),
                ):
                    evidence = self._run(objects, draft)
                self.assertEqual(evidence.failure_category, "invalid_policy_reference")
            finally:
                repository.close()

            repository, _, objects, draft = self._open(root)
            try:
                self.assertTrue(objects._acquire_setup_check())
                occupied = self._run(objects, draft)
                self.assertEqual(occupied.failure_category, "capacity_unavailable")
                self.assertIsNone(repository.get_destination_precheck(draft.revision_id))
                objects._release_setup_check()
            finally:
                repository.close()

            repository = SQLiteConfigurationRepository(root / "timeout.sqlite3")
            managed = ManagedConfigurationService(repository)
            objects = ConfigurationObjectService(managed, setup_check_timeout_seconds=0.01)
            document = self._document(root)
            document["persistence"]["databasePath"] = str(root / "timeout.sqlite3")
            draft = managed.import_draft(document, actor="operator")
            original = objects._run_destination_precheck

            def delayed(*args, **kwargs):
                time.sleep(0.05)
                return original(*args, **kwargs)

            try:
                with patch.object(objects, "_run_destination_precheck", side_effect=delayed):
                    evidence = self._run(objects, draft)
                self.assertEqual(evidence.failure_category, "timeout")
            finally:
                repository.close()

    def test_invalid_exact_revision_api_and_marker_nine_eight_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            (root / "source-private" / "Media").mkdir()
            database = root / "configuration.sqlite3"
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(database) as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(document, actor="operator")
                objects.naming_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample=self._sample(),
                )
                objects.classification_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample=self._sample(),
                )
                objects.organize_authority(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                )
                objects.destination_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    sample=self._sample(),
                )
                evidence = self._run(objects, draft)
                stored = evidence.document()
                draft = managed.validate(draft.revision_id, actor="operator")
                setup = objects.local_check(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    resource_library_id=document["resourceLibraries"][0]["id"],
                    media_library_id="movies",
                )
                self.assertEqual(setup.status.value, "passed")
                other_evidence = (
                    repository.get_naming_preview(draft.revision_id).document(),
                    repository.get_classification_preview(draft.revision_id).document(),
                    repository.get_organize_authority(draft.revision_id).document(),
                    repository.get_destination_preview(draft.revision_id).document(),
                    repository.get_local_setup_check(draft.revision_id).document(),
                )
                revision_document = copy.deepcopy(draft.document)
                for sample in ([], {"unknown": True}, {"path": "x.mkv", "title": "x"}):
                    with self.subTest(sample=sample), self.assertRaises(ValueError):
                        objects.destination_precheck(
                            draft.revision_id,
                            expected_version=draft.version,
                            expected_digest=draft.digest,
                            actor="operator",
                            recognition_type="C",
                            sample=sample,
                        )
                    self.assertEqual(
                        repository.get_destination_precheck(draft.revision_id).document(), stored
                    )
                    self.assertEqual(
                        (
                            repository.get_naming_preview(draft.revision_id).document(),
                            repository.get_classification_preview(draft.revision_id).document(),
                            repository.get_organize_authority(draft.revision_id).document(),
                            repository.get_destination_preview(draft.revision_id).document(),
                            repository.get_local_setup_check(draft.revision_id).document(),
                        ),
                        other_evidence,
                    )
                    self.assertEqual(managed.require(draft.revision_id).document, revision_document)
                changed = copy.deepcopy(draft.document["namingPolicies"][0])
                changed["description"] = "changed"
                edited = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.NAMING_POLICY,
                    object_id="A",
                    value=changed,
                    expected_version=draft.version,
                    actor="operator",
                )
                self.assertTrue(
                    objects.revision_detail(edited.revision_id)["destinationPrecheck"]["stale"]
                )
                with self.assertRaises(ConfigurationVersionConflict):
                    objects.destination_precheck(
                        edited.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        recognition_type="C",
                        sample=self._sample(),
                    )
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=managed,
                    bootstrap_document=document,
                )
                endpoint = (
                    f"/api/v1/configuration/revisions/{edited.revision_id}/destination-precheck"
                )
                status, response = request(
                    api,
                    endpoint,
                    method="POST",
                    body={
                        "expectedVersion": edited.version,
                        "expectedDigest": edited.digest,
                        "recognitionType": "C",
                        "sample": self._sample(),
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(response["sideEffects"], "none")
                status, response = request(
                    api,
                    endpoint,
                    method="POST",
                    body={
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                        "recognitionType": "C",
                        "sample": self._sample(),
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(response["error"]["code"], "configuration_version_conflict")
                status, response = request(
                    api,
                    endpoint,
                    method="POST",
                    body={
                        "expectedVersion": edited.version,
                        "expectedDigest": edited.digest,
                        "recognitionType": "C",
                        "sample": [],
                    },
                )
                self.assertEqual((status, response["error"]["code"]), (400, "invalid_request"))
                status, response = request(
                    api,
                    endpoint,
                    method="POST",
                    body={
                        "expectedVersion": edited.version,
                        "expectedDigest": edited.digest,
                        "recognitionType": "C" * 65,
                        "sample": self._sample(),
                    },
                )
                self.assertEqual((status, response["error"]["code"]), (400, "invalid_request"))
                status, response = request(
                    api,
                    endpoint,
                    method="POST",
                    body={
                        "expectedVersion": edited.version,
                        "expectedDigest": edited.digest,
                        "recognitionType": "C",
                        "sample": {"path": "x.mkv", "title": "x"},
                    },
                )
                self.assertEqual((status, response["error"]["code"]), (400, "invalid_request"))
                unavailable = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                )
                status, _ = request(
                    unavailable,
                    endpoint,
                    method="POST",
                    body={
                        "expectedVersion": edited.version,
                        "expectedDigest": edited.digest,
                        "recognitionType": "C",
                        "sample": self._sample(),
                    },
                )
                self.assertEqual(status, 503)

                active_draft = managed.import_draft(document, actor="operator")
                validated = managed.validate(active_draft.revision_id, actor="operator")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="operator",
                )
                with self.assertRaises(ConfigurationVersionConflict):
                    objects.destination_precheck(
                        active.revision_id,
                        expected_version=active.version,
                        expected_digest=active.digest,
                        actor="operator",
                        recognition_type="C",
                        sample=self._sample(),
                    )
                self.assertIsNone(repository.get_destination_precheck(active.revision_id))

            with sqlite3.connect(database) as connection:
                connection.execute("DROP INDEX managed_destination_prechecks_status")
                connection.execute("DROP TABLE managed_destination_prechecks")
                connection.execute(
                    "UPDATE schema_version SET version=9 WHERE component='configuration_management'"
                )
            with SQLiteConfigurationRepository(database) as repository:
                self.assertIsNone(repository.get_destination_precheck(draft.revision_id))
                self.assertIsNotNone(repository.get_revision(draft.revision_id))
                self.assertIsNotNone(repository.get_naming_preview(draft.revision_id))
                self.assertIsNotNone(repository.get_classification_preview(draft.revision_id))
                self.assertIsNotNone(repository.get_organize_authority(draft.revision_id))
                self.assertIsNotNone(repository.get_destination_preview(draft.revision_id))
                self.assertIsNotNone(repository.get_local_setup_check(draft.revision_id))
                self.assertEqual(CONFIGURATION_SCHEMA_VERSION, 10)
            with sqlite3.connect(database) as connection:
                connection.execute("DROP INDEX managed_destination_prechecks_status")
                connection.execute("DROP TABLE managed_destination_prechecks")
                connection.execute("DROP INDEX managed_destination_previews_status")
                connection.execute("DROP TABLE managed_destination_previews")
                connection.execute(
                    "UPDATE schema_version SET version=8 WHERE component='configuration_management'"
                )
            with SQLiteConfigurationRepository(database) as repository:
                self.assertIsNone(repository.get_destination_precheck(draft.revision_id))
                self.assertIsNone(repository.get_destination_preview(draft.revision_id))
                self.assertIsNotNone(repository.get_revision(draft.revision_id))
                self.assertIsNotNone(repository.get_naming_preview(draft.revision_id))
                self.assertIsNotNone(repository.get_classification_preview(draft.revision_id))
                self.assertIsNotNone(repository.get_organize_authority(draft.revision_id))
                self.assertIsNotNone(repository.get_local_setup_check(draft.revision_id))
                self.assertEqual(RUNTIME_SCHEMA_VERSION, 22)


if __name__ == "__main__":
    unittest.main()
