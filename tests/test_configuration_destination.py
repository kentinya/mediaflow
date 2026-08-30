from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.organizer import OrganizePlanner
from mediaflow.domain.classification import ClassificationResult, ClassificationStatus
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ConfigurationVersionConflict,
)
from mediaflow.domain.library import MediaLibrary
from mediaflow.domain.naming import NamingError, NamingErrorCode, NamingResult
from mediaflow.domain.organizer import (
    ConflictType,
    OrganizeOperationType,
    OrganizePolicy,
    PlanStatus,
    compose_destination,
)
from mediaflow.domain.recognition import (
    PolicyResolutionErrorCode,
    RecognitionResult,
    RecognitionType,
    RecognitionTypePolicy,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import (
    CONFIGURATION_SCHEMA_VERSION,
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION as RUNTIME_SCHEMA_VERSION
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request


class DestinationCompositionParityTests(unittest.TestCase):
    def test_shared_composition_matches_real_planner_for_safe_and_unsafe_inputs(self) -> None:
        cases = (
            ("safe", "Movies", "Action", ("Movie (2001)",), "Movie (2001).mkv"),
            ("absolute-root", "/media/Movies/", "Action", ("Movie",), "Movie.mkv"),
            ("unsafe-root", "../Movies", "Action", ("Movie",), "Movie.mkv"),
            ("classification-traversal", "Movies", "../Action", ("Movie",), "Movie.mkv"),
            ("classification-absolute", "Movies", "/Action", ("Movie",), "Movie.mkv"),
            ("directory-traversal", "Movies", "Action", ("..",), "Movie.mkv"),
            ("filename-separator", "Movies", "Action", ("Movie",), "bad/name.mkv"),
            ("filename-traversal", "Movies", "Action", ("Movie",), ".."),
        )
        for label, root, relative, segments, filename in cases:
            with self.subTest(label=label):
                recognition_type = RecognitionType("C", "C")
                type_policy = RecognitionTypePolicy(
                    "type-C",
                    recognition_type,
                    "C",
                    "A",
                    "A",
                    OrganizePolicy("A", OrganizeOperationType.MOVE),
                )
                naming = NamingResult(
                    "/".join(segments),
                    filename,
                    "A",
                    "C",
                    directory_segments=segments,
                )
                classification = ClassificationResult("movies", relative, "A", "C")
                composition = compose_destination(
                    root, relative, naming.directory, segments, filename
                )
                plan = OrganizePlanner().plan(
                    source_storage_id="source",
                    source="source.mkv",
                    recognition=RecognitionResult(recognition_type, "rule-C"),
                    type_policy=type_policy,
                    media_library=MediaLibrary("movies", "Movies", "target", root),
                    naming=naming,
                    classification=classification,
                )
                self.assertEqual(composition.safe, plan.status is not PlanStatus.INVALID)
                if composition.safe:
                    self.assertEqual(plan.media_library_root, root)
                    self.assertEqual(plan.relative_destination, composition.relative_destination)
                    self.assertEqual(plan.target, composition.target)
                else:
                    self.assertEqual(plan.status, PlanStatus.INVALID)
                    self.assertEqual(plan.target, "")
                    self.assertEqual(plan.conflicts[0].type, ConflictType.INVALID_DESTINATION)


class ManagedDestinationPreviewJourneyTests(unittest.TestCase):
    @staticmethod
    def _document(root: Path) -> dict:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "private-source")
        document["storages"][1]["rootPath"] = str(root / "private-target")
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

    def _assert_failed_preview_preserved_other_state(
        self,
        repository: SQLiteConfigurationRepository,
        managed: ManagedConfigurationService,
        revision,
    ) -> None:
        current = managed.require(revision.revision_id)
        self.assertEqual((current.version, current.digest), (revision.version, revision.digest))
        self.assertEqual(current.document, revision.document)
        self.assertIsNone(repository.get_naming_preview(revision.revision_id))
        self.assertIsNone(repository.get_classification_preview(revision.revision_id))
        self.assertIsNone(repository.get_organize_authority(revision.revision_id))

    def test_synthetic_and_path_success_preserve_c_identity_and_zero_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                original = copy.deepcopy(draft.document)
                with (
                    patch(
                        "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                        side_effect=AssertionError("destination preview constructed Storage"),
                    ),
                    patch(
                        "mediaflow.application.configuration_objects.MetadataProviderRegistry",
                        side_effect=AssertionError("destination preview constructed Provider"),
                    ),
                    patch(
                        "mediaflow.application.organizer.OrganizePlanner",
                        side_effect=AssertionError("destination preview constructed Planner"),
                    ),
                    patch(
                        "mediaflow.application.organizer.OrganizerExecutor",
                        side_effect=AssertionError("destination preview constructed Executor"),
                    ),
                ):
                    synthetic = objects.destination_preview(
                        draft.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        recognition_type="C",
                        sample=self._sample(),
                    )
                    path_mode = objects.destination_preview(
                        draft.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        recognition_type="C",
                        sample={"path": "The.Matrix.1999.1080p.mkv"},
                    )
                result = synthetic.result
                self.assertEqual(result["recognitionType"], "C")
                self.assertEqual(result["recognitionTypePolicyId"], "type-C")
                self.assertEqual(result["namingPolicyId"], "A")
                self.assertEqual(result["classificationPolicyId"], "A")
                self.assertEqual(result["mediaLibraryId"], "movies")
                self.assertEqual(result["mediaLibraryRootPath"], "Movies")
                self.assertEqual(result["classificationRelativePath"], "Action")
                self.assertEqual(result["classificationRuleId"], "action-movie")
                self.assertEqual(
                    result["rootRelativeDestination"],
                    "Action/The Matrix (1999) [tmdbid-synthetic]/The Matrix (1999).mkv",
                )
                self.assertEqual(
                    result["composedStorageRelativeDestination"],
                    "Movies/Action/The Matrix (1999) [tmdbid-synthetic]/The Matrix (1999).mkv",
                )
                recognition_type = RecognitionType("C", "C")
                plan = OrganizePlanner().plan(
                    source_storage_id="source",
                    source="source.mkv",
                    recognition=RecognitionResult(recognition_type, "rule-C"),
                    type_policy=RecognitionTypePolicy(
                        "type-C",
                        recognition_type,
                        "C",
                        "A",
                        "A",
                        OrganizePolicy("A", OrganizeOperationType.MOVE),
                    ),
                    media_library=MediaLibrary("movies", "Movies", "target", "Movies"),
                    naming=NamingResult(
                        "/".join(result["namingDirectorySegments"]),
                        result["namingFilename"],
                        "A",
                        "C",
                        directory_segments=tuple(result["namingDirectorySegments"]),
                    ),
                    classification=ClassificationResult(
                        "movies",
                        result["classificationRelativePath"],
                        "A",
                        "C",
                    ),
                )
                self.assertEqual(plan.target, result["composedStorageRelativeDestination"])
                self.assertEqual(synthetic.document()["pathScope"], "storage_relative")
                self.assertEqual(synthetic.document()["sideEffects"], "none")
                self.assertTrue(synthetic.document()["retrySafe"])
                self.assertEqual(path_mode.status.value, "completed")
                self.assertEqual(path_mode.input["mode"], "path")
                self.assertNotIn(str(root), repr(synthetic.document()))
                self.assertNotIn(str(root), repr(path_mode.document()))
                current = managed.require(draft.revision_id)
                self.assertEqual((current.version, current.digest), (draft.version, draft.digest))
                self.assertEqual(current.document, original)

    def test_invalid_samples_preserve_all_existing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                naming = objects.naming_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample=self._sample(),
                ).document()
                classification = objects.classification_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample=self._sample(),
                ).document()
                authority = objects.organize_authority(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                ).document()
                original = copy.deepcopy(draft.document)
                for label, sample in (
                    ("non-object", []),
                    ("unknown", {"title": "Example", "unknown": True}),
                    ("mixed-path", {"path": "Example.mkv", "title": "Example"}),
                ):
                    with self.subTest(label=label), self.assertRaises(ValueError):
                        objects.destination_preview(
                            draft.revision_id,
                            expected_version=draft.version,
                            expected_digest=draft.digest,
                            actor="operator",
                            recognition_type="C",
                            sample=sample,
                        )
                    self.assertIsNone(repository.get_destination_preview(draft.revision_id))
                    self.assertEqual(
                        repository.get_naming_preview(draft.revision_id).document(), naming
                    )
                    self.assertEqual(
                        repository.get_classification_preview(draft.revision_id).document(),
                        classification,
                    )
                    self.assertEqual(
                        repository.get_organize_authority(draft.revision_id).document(), authority
                    )
                    self.assertEqual(managed.require(draft.revision_id).document, original)

    def test_resolution_engine_unresolved_and_unsafe_failures_are_bounded(self) -> None:
        variants: list[tuple[str, dict, str, str]] = []
        missing = example_document()
        variants.append(
            ("missing", missing, "missing", PolicyResolutionErrorCode.MISSING_TYPE_POLICY)
        )
        duplicate = example_document()
        duplicate["recognitionTypePolicies"].append(
            {**copy.deepcopy(duplicate["recognitionTypePolicies"][2]), "id": "type-C-copy"}
        )
        variants.append(
            ("duplicate", duplicate, "C", PolicyResolutionErrorCode.DUPLICATE_TYPE_POLICY)
        )
        disabled = example_document()
        disabled["recognitionTypes"][2]["enabled"] = False
        variants.append(
            ("disabled", disabled, "C", PolicyResolutionErrorCode.RECOGNITION_TYPE_DISABLED)
        )
        disabled_policy = example_document()
        next(item for item in disabled_policy["metadataPolicies"] if item["id"] == "C")[
            "enabled"
        ] = False
        variants.append(
            ("disabled-policy", disabled_policy, "C", PolicyResolutionErrorCode.POLICY_DISABLED)
        )
        dangling = example_document()
        dangling["recognitionTypePolicies"][2]["namingPolicy"] = "absent"
        variants.append(
            ("dangling", dangling, "C", PolicyResolutionErrorCode.INVALID_POLICY_REFERENCE)
        )
        unresolved = example_document()
        next(
            rule
            for rule in unresolved["classificationPolicies"][0]["rules"]
            if rule["id"] == "action-movie"
        )["result"]["mediaLibraryId"] = "absent"
        variants.append(("unresolved", unresolved, "C", "unresolved_media_library"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                for label, document, requested, category in variants:
                    with self.subTest(label=label):
                        document["persistence"]["databasePath"] = str(
                            root / "configuration.sqlite3"
                        )
                        draft = managed.import_draft(document, actor="operator")
                        evidence = objects.destination_preview(
                            draft.revision_id,
                            expected_version=draft.version,
                            expected_digest=draft.digest,
                            actor="operator",
                            recognition_type=requested,
                            sample=self._sample(),
                        )
                        expected = (
                            category.value
                            if isinstance(category, PolicyResolutionErrorCode)
                            else category
                        )
                        self.assertEqual(evidence.status.value, "failed")
                        self.assertEqual(evidence.failure_category, expected)
                        self.assertLessEqual(len(evidence.message), 384)
                        self.assertNotIn("secret-value", evidence.message)
                        self._assert_failed_preview_preserved_other_state(
                            repository, managed, draft
                        )

                classification_failure = managed.import_draft(
                    self._document(root), actor="operator"
                )
                failed = objects.destination_preview(
                    classification_failure.revision_id,
                    expected_version=classification_failure.version,
                    expected_digest=classification_failure.digest,
                    actor="operator",
                    recognition_type="C",
                    sample={"title": "Example", "mediaType": "tv", "extension": "mkv"},
                )
                self.assertEqual(failed.failure_category, "invalid_rule")
                self.assertIn("ClassificationPolicy 'A'", failed.message)
                self._assert_failed_preview_preserved_other_state(
                    repository, managed, classification_failure
                )

                naming_document = self._document(root)
                naming_document["namingPolicies"][0]["directoryTemplate"] = "{episode_title}"
                naming_document["namingPolicies"][0]["missingVariableStrategy"] = "error"
                naming_failure = managed.import_draft(naming_document, actor="operator")
                failed = objects.destination_preview(
                    naming_failure.revision_id,
                    expected_version=naming_failure.version,
                    expected_digest=naming_failure.digest,
                    actor="operator",
                    recognition_type="C",
                    sample=self._sample(),
                )
                self.assertEqual(failed.failure_category, "missing_variable")
                self.assertIn("NamingPolicy 'A'", failed.message)
                self._assert_failed_preview_preserved_other_state(
                    repository, managed, naming_failure
                )

                redacted_failure = managed.import_draft(self._document(root), actor="operator")
                with patch(
                    "mediaflow.application.configuration_objects.NamingPreviewService.preview",
                    side_effect=NamingError(
                        NamingErrorCode.INTERNAL_ERROR, "secret-value from raw exception"
                    ),
                ):
                    failed = objects.destination_preview(
                        redacted_failure.revision_id,
                        expected_version=redacted_failure.version,
                        expected_digest=redacted_failure.digest,
                        actor="operator",
                        recognition_type="C",
                        sample=self._sample(),
                    )
                self.assertEqual(failed.failure_category, "internal_error")
                self.assertNotIn("secret-value", failed.message)
                self._assert_failed_preview_preserved_other_state(
                    repository, managed, redacted_failure
                )

                unsafe_cases = (
                    ("mediaLibrary.rootPath", None, None, "../Movies"),
                    ("classification.relativePath", "../Action", None, None),
                    ("naming.directorySegments[0]", None, ("..",), None),
                    ("naming.filename", None, None, None),
                )
                for contribution, relative, segments, unsafe_root in unsafe_cases:
                    classification_result = ClassificationResult(
                        "movies",
                        relative or "Action",
                        "A",
                        "C",
                        ClassificationStatus.CLASSIFIED,
                        "action-movie",
                    )
                    naming_result = NamingResult(
                        (
                            "Movie"
                            if contribution == "naming.directorySegments[0]"
                            else "/".join(segments or ("Movie",))
                        ),
                        "bad/name.mkv" if contribution == "naming.filename" else "Movie.mkv",
                        "A",
                        "C",
                        directory_segments=segments or ("Movie",),
                    )
                    document = self._document(root)
                    if unsafe_root is not None:
                        document["mediaLibraries"][0]["rootPath"] = unsafe_root
                    candidate = managed.import_draft(document, actor="operator")
                    with (
                        patch(
                            "mediaflow.application.configuration_objects.NamingPreviewService.preview",
                            return_value=naming_result,
                        ),
                        patch(
                            "mediaflow.application.configuration_objects.ClassificationPreviewService.preview",
                            return_value=classification_result,
                        ),
                    ):
                        evidence = objects.destination_preview(
                            candidate.revision_id,
                            expected_version=candidate.version,
                            expected_digest=candidate.digest,
                            actor="operator",
                            recognition_type="C",
                            sample=self._sample(),
                        )
                    self.assertEqual(evidence.failure_category, "unsafe_destination")
                    self.assertIn(contribution, evidence.message)
                    self._assert_failed_preview_preserved_other_state(
                        repository, managed, candidate
                    )

    def test_optional_media_and_organize_sections_load_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                for section in ("mediaLibraries", "organizePolicies"):
                    with self.subTest(section=section):
                        document = self._document(root)
                        document.pop(section)
                        draft = managed.import_draft(document, actor="operator")
                        self.assertEqual(
                            objects.revision_detail(draft.revision_id)["objects"][section], []
                        )

    def test_stale_active_api_and_marker_eight_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(database) as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(document, actor="operator")
                naming = objects.naming_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample=self._sample(),
                ).document()
                classification = objects.classification_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample=self._sample(),
                ).document()
                authority = objects.organize_authority(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                ).document()
                destination = objects.destination_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    sample=self._sample(),
                )
                changed_policy = copy.deepcopy(draft.document["namingPolicies"][0])
                changed_policy["description"] = "changed"
                edited = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.NAMING_POLICY,
                    object_id="A",
                    value=changed_policy,
                    expected_version=draft.version,
                    actor="operator",
                )
                self.assertTrue(
                    objects.revision_detail(edited.revision_id)["destinationPreview"]["stale"]
                )
                with self.assertRaises(ConfigurationVersionConflict):
                    objects.destination_preview(
                        edited.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        recognition_type="C",
                        sample=self._sample(),
                    )
                self.assertEqual(
                    repository.get_destination_preview(draft.revision_id).document(),
                    destination.document(),
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
                    f"/api/v1/configuration/revisions/{edited.revision_id}/destination-preview"
                )
                status, response = request(
                    api,
                    endpoint,
                    method="POST",
                    body={
                        "expectedVersion": edited.version,
                        "expectedDigest": edited.digest,
                        "recognitionType": "C",
                        "sample": {"path": "Example.mkv", "title": "Example"},
                    },
                )
                self.assertEqual(status, 400)
                self.assertEqual(response["error"]["code"], "invalid_request")
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
                self.assertEqual(status, 400)
                self.assertEqual(response["error"]["code"], "invalid_request")
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
                self.assertEqual(response["pathScope"], "storage_relative")
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

                unavailable = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                )
                status, response = request(
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
                self.assertEqual(response["error"]["code"], "service_unavailable")

                validated = managed.validate(edited.revision_id, actor="operator")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="operator",
                )
                with self.assertRaises(ConfigurationVersionConflict):
                    objects.destination_preview(
                        active.revision_id,
                        expected_version=active.version,
                        expected_digest=active.digest,
                        actor="operator",
                        recognition_type="C",
                        sample=self._sample(),
                    )
            with sqlite3.connect(database) as connection:
                connection.execute("DROP INDEX managed_destination_previews_status")
                connection.execute("DROP TABLE managed_destination_previews")
                connection.execute(
                    "UPDATE schema_version SET version=8 WHERE component='configuration_management'"
                )
            with SQLiteConfigurationRepository(database) as repository:
                self.assertIsNone(repository.get_destination_preview(draft.revision_id))
                self.assertEqual(
                    repository.get_revision(draft.revision_id).document, active.document
                )
                self.assertEqual(
                    repository.get_naming_preview(draft.revision_id).document(), naming
                )
                self.assertEqual(
                    repository.get_classification_preview(draft.revision_id).document(),
                    classification,
                )
                self.assertEqual(
                    repository.get_organize_authority(draft.revision_id).document(), authority
                )
                with sqlite3.connect(database) as connection:
                    marker = connection.execute(
                        "SELECT version FROM schema_version "
                        "WHERE component='configuration_management'"
                    ).fetchone()[0]
                self.assertEqual(marker, CONFIGURATION_SCHEMA_VERSION)
                self.assertEqual(RUNTIME_SCHEMA_VERSION, 26)


if __name__ == "__main__":
    unittest.main()
