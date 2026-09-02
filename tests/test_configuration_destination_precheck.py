from __future__ import annotations

import copy
import sqlite3
import tempfile
import time
import unittest
from contextlib import nullcontext
from dataclasses import replace
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
from mediaflow.domain.organizer import Conflict, ConflictStrategy, ConflictType, PlanStatus
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

    def _assert_runtime_authority_empty(self, database: Path) -> None:
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
                with self.subTest(table=table):
                    count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    self.assertEqual(count, 0)

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
                self.assertEqual(
                    result["relativeDestination"],
                    "Action/The Matrix (1999) [tmdbid-synthetic]/The Matrix (1999).mkv",
                )
                self.assertEqual(
                    result["destinationPath"],
                    "Movies/Action/The Matrix (1999) [tmdbid-synthetic]/The Matrix (1999).mkv",
                )
                self.assertTrue(result["destinationPath"].startswith("Movies/"))
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

    def test_multiple_samples_success_most_severe_verdict_and_distinct_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_root = root / "target-private"
            (target_root / "Movies").mkdir(parents=True)
            existing = (
                target_root
                / "Movies"
                / "Action"
                / "The Matrix (1999) [tmdbid-synthetic]"
                / "The Matrix (1999).mkv"
            )
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"existing")
            (root / "source-private").mkdir()
            before = self._tree_snapshot(target_root)
            repository, _, objects, draft = self._open(root)
            try:
                evidence = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Your Name",
                            "mediaType": "movie",
                            "year": 2016,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Spirited Away",
                            "mediaType": "movie",
                            "year": 2001,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                    ],
                )
                result = evidence.result
                self.assertEqual(evidence.status.value, "completed")
                self.assertEqual(result["recognitionType"], "C")
                self.assertEqual(result["sampleCount"], 3)
                self.assertEqual(result["verdict"], "manual_confirmation_required")
                self.assertEqual(result["collisions"], [])
                self.assertEqual([row["index"] for row in result["items"]], [0, 1, 2])
                self.assertEqual(
                    [row["projectedOutcome"] for row in result["items"]],
                    ["manual_confirmation_required", "ready", "ready"],
                )
                destinations = [row["destinationPath"] for row in result["items"]]
                self.assertEqual(len(set(destinations)), 3)
                self.assertTrue(result["items"][0]["targetExists"])
                self.assertIn("DESTINATION_EXISTS", result["items"][0]["plannerConflicts"])
                self.assertFalse(result["items"][1]["targetExists"])
                self.assertEqual(result["authorityGranted"], "none")
                self.assertEqual(set(result["guardMutationCalls"].values()), {0})
                self.assertEqual(self._tree_snapshot(target_root), before)
            finally:
                repository.close()

    def test_multi_sample_verdict_is_most_severe_not_first_or_last_sample(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_root = root / "target-private"
            (target_root / "Movies").mkdir(parents=True)
            severe = (
                target_root
                / "Movies"
                / "Anime"
                / "Your Name (2016) [tmdbid-synthetic]"
                / "Your Name (2016).mkv"
            )
            severe.parent.mkdir(parents=True)
            severe.write_bytes(b"existing")
            (root / "source-private").mkdir()
            before = self._tree_snapshot(target_root)
            repository, _, objects, draft = self._open(root)
            try:
                evidence = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Your Name",
                            "mediaType": "movie",
                            "year": 2016,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Spirited Away",
                            "mediaType": "movie",
                            "year": 2001,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                    ],
                )
                result = evidence.result
                self.assertEqual(evidence.status.value, "completed")
                self.assertIsNone(evidence.failure_category)
                self.assertEqual(result["sampleCount"], 3)
                self.assertEqual(result["collisions"], [])
                outcomes = [row["projectedOutcome"] for row in result["items"]]
                self.assertEqual(
                    outcomes,
                    ["ready", "manual_confirmation_required", "ready"],
                )
                self.assertEqual(result["verdict"], "manual_confirmation_required")
                self.assertNotEqual(result["verdict"], outcomes[0])
                self.assertNotEqual(result["verdict"], outcomes[-1])
                destinations = [row["destinationPath"] for row in result["items"]]
                self.assertEqual(len(set(destinations)), 3)
                self.assertIn("DESTINATION_EXISTS", result["items"][1]["plannerConflicts"])
                self.assertEqual(result["authorityGranted"], "none")
                self.assertEqual(set(result["guardMutationCalls"].values()), {0})
                self.assertEqual(self._tree_snapshot(target_root), before)
            finally:
                repository.close()

    def test_multi_sample_top_level_keys_describe_the_first_sample(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_root = root / "target-private"
            (target_root / "Movies").mkdir(parents=True)
            severe = (
                target_root
                / "Movies"
                / "Anime"
                / "Your Name (2016) [tmdbid-synthetic]"
                / "Your Name (2016).mkv"
            )
            severe.parent.mkdir(parents=True)
            severe.write_bytes(b"existing")
            (root / "source-private").mkdir()
            before = self._tree_snapshot(target_root)
            repository, _, objects, draft = self._open(root)
            try:
                evidence = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Your Name",
                            "mediaType": "movie",
                            "year": 2016,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Spirited Away",
                            "mediaType": "movie",
                            "year": 2001,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                    ],
                )
                result = evidence.result
                first = result["items"][0]
                self.assertEqual(result["destinationPath"], first["destinationPath"])
                self.assertEqual(
                    result["conflictProjection"]["projectedOutcome"],
                    first["projectedOutcome"],
                )
                self.assertEqual(result["targetExists"], first["targetExists"])
                self.assertEqual(first["projectedOutcome"], "ready")
                self.assertNotEqual(result["verdict"], first["projectedOutcome"])
                self.assertEqual(result["authorityGranted"], "none")
                self.assertEqual(set(result["guardMutationCalls"].values()), {0})
                self.assertEqual(self._tree_snapshot(target_root), before)
            finally:
                repository.close()

    def test_cross_sample_collision_is_duplicate_destination_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_root = root / "target-private"
            (target_root / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            before = self._tree_snapshot(target_root)
            repository, _, objects, draft = self._open(root)
            try:
                sample = self._sample()
                evidence = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[sample, copy.deepcopy(sample)],
                )
                self.assertEqual(evidence.status.value, "failed")
                self.assertEqual(evidence.failure_category, "duplicate_destination")
                result = evidence.result
                self.assertEqual(result["sampleCount"], 2)
                self.assertEqual(len(result["items"]), 2)
                self.assertEqual(
                    result["items"][0]["destinationPath"],
                    result["items"][1]["destinationPath"],
                )
                self.assertIn("TARGET_COLLISION", result["items"][1]["plannerConflicts"])
                self.assertEqual(
                    result["collisions"],
                    [
                        {
                            "destinationPath": result["items"][0]["destinationPath"],
                            "itemIndexes": [0, 1],
                        }
                    ],
                )
                self.assertIn("distinguishing naming variable", evidence.next_action)
                self.assertNotIn(str(root), repr(evidence.document()))
                self.assertEqual(set(result["guardMutationCalls"].values()), {0})
                self.assertEqual(self._tree_snapshot(target_root), before)
            finally:
                repository.close()

    def test_per_sample_isolation_when_middle_sample_fails_composition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            repository, _, objects, draft = self._open(root)
            try:
                evidence = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Unroutable",
                            "mediaType": "tv",
                            "year": 2020,
                            "genres": ["Action"],
                        },
                        {
                            "title": "Your Name",
                            "mediaType": "movie",
                            "year": 2016,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                    ],
                )
                self.assertEqual(evidence.status.value, "failed")
                self.assertEqual(evidence.failure_category, "invalid_rule")
                result = evidence.result
                self.assertEqual(result["sampleCount"], 3)
                self.assertEqual([row["index"] for row in result["items"]], [0, 1, 2])
                self.assertIsNone(result["items"][1]["destinationPath"])
                self.assertEqual(result["items"][1]["failureCategory"], "invalid_rule")
                self.assertIn("ClassificationPolicy", result["items"][1]["message"])
                self.assertIsNone(result["items"][0]["failureCategory"])
                self.assertIsNone(result["items"][2]["failureCategory"])
                self.assertTrue(result["items"][0]["destinationPath"].startswith("Movies/Action/"))
                self.assertTrue(result["items"][2]["destinationPath"].startswith("Movies/Anime/"))
                self.assertEqual(result["items"][0]["projectedOutcome"], "ready")
                self.assertEqual(result["items"][2]["projectedOutcome"], "ready")
            finally:
                repository.close()

    def test_destination_precheck_multi_sample_independent_failures_keep_their_own_message(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            repository, _, objects, draft = self._open(root)
            try:
                evidence = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Show",
                            "mediaType": "tv",
                            "year": 2020,
                            "genres": ["Action"],
                        },
                        {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                    ],
                )
                result = evidence.result
                failing = [row for row in result["items"] if row["failureCategory"] is not None]
                self.assertEqual([row["index"] for row in failing], [0, 1])
                self.assertEqual(failing[0]["failureCategory"], "invalid_input")
                self.assertEqual(failing[1]["failureCategory"], "invalid_rule")
                self.assertIsNotNone(failing[0]["message"])
                self.assertIsNotNone(failing[1]["message"])
                self.assertNotEqual(failing[0]["message"], failing[1]["message"])
                self.assertEqual(evidence.failure_category, failing[0]["failureCategory"])
                self.assertEqual(evidence.message, failing[0]["message"])
                self.assertNotEqual(failing[1]["message"], evidence.message)
                self.assertNotEqual(failing[1]["message"], evidence.next_action)
            finally:
                repository.close()

    def test_destination_precheck_per_sample_rows_carry_their_own_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            document = self._document(root)
            document["mediaLibraries"][1]["rootPath"] = "TV Missing"
            document["classificationPolicies"][0]["rules"].insert(
                0,
                {
                    "id": "missing-root-movie",
                    "priority": 300,
                    "conditions": {"mediaType": ["movie"], "genres": ["Drama"]},
                    "result": {
                        "mediaLibraryId": "tv",
                        "library": "TV Shows",
                        "path": ["Drama"],
                    },
                },
            )
            fixture_root_paths = [
                str(value["rootPath"])
                for value in [*document["storages"], *document["mediaLibraries"]]
            ]
            repository, _, objects, draft = self._open(root, document)
            try:
                evidence = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Missing Root",
                            "mediaType": "movie",
                            "year": 2024,
                            "genres": ["Drama"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Your Name",
                            "mediaType": "movie",
                            "year": 2016,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                    ],
                )
                self.assertEqual(evidence.status.value, "failed")
                result = evidence.result
                self.assertEqual(result["collisions"], [])
                items = sorted(result["items"], key=lambda row: row["index"])
                failing = [row for row in items if row["failureCategory"] is not None]
                self.assertEqual([row["index"] for row in failing], [0, 1])
                self.assertIsNone(items[2]["nextAction"])
                self.assertTrue(all(isinstance(row["nextAction"], str) for row in failing))
                self.assertNotEqual(failing[0]["nextAction"], failing[1]["nextAction"])
                for row in failing:
                    self.assertEqual(
                        row["nextAction"],
                        ConfigurationObjectService._destination_sample_next_action(
                            row["failureCategory"]
                        ),
                    )
                    self.assertFalse(Path(row["nextAction"]).is_absolute())
                    for fixture_root_path in fixture_root_paths:
                        self.assertNotIn(fixture_root_path, row["nextAction"])
                    self.assertNotIn("/", row["nextAction"])
                    self.assertNotIn("\\", row["nextAction"])
                    self.assertNotIn("://", row["nextAction"])
                mapped_categories = {
                    "missing_destination_root",
                    "destination_root_not_directory",
                    "read_only_violation",
                    "permission_denied",
                    "unavailable",
                    "timeout",
                }
                self.assertNotIn(failing[0]["failureCategory"], mapped_categories)
                self.assertEqual(
                    failing[0]["nextAction"],
                    "correct the destination or conflict policy, then rerun precheck",
                )
                self.assertEqual(failing[1]["failureCategory"], "missing_destination_root")
                self.assertEqual(evidence.next_action, failing[0]["nextAction"])
            finally:
                repository.close()

    def test_destination_sample_next_action_sentences_are_bounded_unchanged_constants(
        self,
    ) -> None:
        expected = {
            "missing_destination_root": (
                "create the root out of band or correct MediaLibrary.rootPath, then rerun"
            ),
            "destination_root_not_directory": (
                "correct MediaLibrary.rootPath, then rerun destination precheck"
            ),
            "read_only_violation": (
                "do not activate; inspect the destination-precheck implementation"
            ),
            "permission_denied": (
                "correct availability, permissions or path, then rerun destination precheck"
            ),
            "unavailable": ("inspect service health and configuration, then rerun precheck"),
            "timeout": ("wait for the in-flight check to finish, fix availability, then rerun"),
        }
        for category, sentence in expected.items():
            with self.subTest(category=category):
                self.assertEqual(
                    ConfigurationObjectService._destination_sample_next_action(category),
                    sentence,
                )
                self.assertTrue(sentence.isascii())
                self.assertGreater(len(sentence), 0)
                self.assertLessEqual(len(sentence.encode("utf-8")), 500)
                self.assertNotIn("/", sentence)
                self.assertNotIn("\\", sentence)
                self.assertNotIn("://", sentence)
        self.assertEqual(
            ConfigurationObjectService._destination_sample_next_action("invalid_input"),
            "correct the destination or conflict policy, then rerun precheck",
        )

    def test_multiple_destination_storages_is_bounded_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "target-private-2" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            document = self._document(root)
            document["storages"].append(
                {
                    "id": "media-target-2",
                    "name": "Target 2",
                    "type": "local",
                    "rootPath": str(root / "target-private-2"),
                    "readOnly": False,
                }
            )
            document["mediaLibraries"].append(
                {
                    "id": "movies2",
                    "name": "Movies 2",
                    "storageId": "media-target-2",
                    "rootPath": "Movies",
                    "enabled": True,
                }
            )
            for rule in document["classificationPolicies"][0]["rules"]:
                if rule["id"] == "japanese-animation":
                    rule["result"]["mediaLibraryId"] = "movies2"
                    rule["result"]["path"] = ["Anime"]
            repository, _, objects, draft = self._open(root, document)
            try:
                evidence = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Your Name",
                            "mediaType": "movie",
                            "year": 2016,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                    ],
                )
                self.assertEqual(evidence.status.value, "failed")
                self.assertEqual(evidence.failure_category, "multiple_destination_storages")
                self.assertIn("media-target:local", evidence.message)
                self.assertIn("media-target-2:local", evidence.message)
                self.assertNotIn(str(root / "target-private-2"), repr(evidence.document()))
                self.assertIn("one destination Storage", evidence.next_action)
                result = evidence.result
                self.assertEqual(result["sampleCount"], 2)
                self.assertEqual(len(result["items"]), 2)
                self.assertEqual(result["collisions"], [])
                self.assertIsNone(result["items"][0]["projectedOutcome"])
                self.assertIsNone(result["items"][0]["nextAction"])
                self.assertIsNone(result["items"][1]["nextAction"])
                self.assertIsNone(result["items"][0]["message"])
                self.assertIsNone(result["items"][0]["targetExists"])
                self.assertIsNone(result["items"][0]["proposedRelativeDestination"])
                self.assertIsNone(result["items"][0]["failureCategory"])
                self.assertEqual(result["items"][0]["plannerConflicts"], [])
            finally:
                repository.close()

    def test_single_sample_result_gains_sample_count_items_and_empty_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies" / "Action").mkdir(parents=True)
            (root / "source-private").mkdir()
            repository, _, objects, draft = self._open(root)
            try:
                evidence = self._run(objects, draft)
                result = evidence.result
                self.assertEqual(evidence.status.value, "completed")
                self.assertEqual(result["sampleCount"], 1)
                self.assertEqual(result["collisions"], [])
                self.assertEqual(len(result["items"]), 1)
                row = result["items"][0]
                self.assertEqual(row["index"], 0)
                self.assertEqual(row["relativeDestination"], result["relativeDestination"])
                self.assertEqual(row["destinationPath"], result["destinationPath"])
                self.assertEqual(
                    row["projectedOutcome"],
                    result["conflictProjection"]["projectedOutcome"],
                )
                self.assertIsNone(row["failureCategory"])
                self.assertIsNone(row["nextAction"])
                self.assertEqual(result["verdict"], "ready")
            finally:
                repository.close()

    def test_destination_precheck_rows_share_one_key_shape_across_branches(self) -> None:
        expected = (
            "index",
            "relativeDestination",
            "destinationPath",
            "targetExists",
            "plannerConflicts",
            "projectedOutcome",
            "proposedRelativeDestination",
            "failureCategory",
            "message",
            "nextAction",
        )
        rows = []

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies" / "Action").mkdir(parents=True)
            (root / "source-private").mkdir()
            repository, _, objects, draft = self._open(root)
            try:
                single = self._run(objects, draft)
                rows.extend(single.result["items"])
            finally:
                repository.close()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            document = self._document(root)
            document["mediaLibraries"][1]["rootPath"] = "TV Missing"
            document["classificationPolicies"][0]["rules"].insert(
                0,
                {
                    "id": "missing-root-movie",
                    "priority": 300,
                    "conditions": {"mediaType": ["movie"], "genres": ["Drama"]},
                    "result": {
                        "mediaLibraryId": "tv",
                        "library": "TV Shows",
                        "path": ["Drama"],
                    },
                },
            )
            repository, _, objects, draft = self._open(root, document)
            try:
                mixed = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Missing Root",
                            "mediaType": "movie",
                            "year": 2024,
                            "genres": ["Drama"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Your Name",
                            "mediaType": "movie",
                            "year": 2016,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                    ],
                )
                rows.extend(mixed.result["items"])
            finally:
                repository.close()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "target-private-2" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            document = self._document(root)
            document["storages"].append(
                {
                    "id": "media-target-2",
                    "name": "Target 2",
                    "type": "local",
                    "rootPath": str(root / "target-private-2"),
                    "readOnly": False,
                }
            )
            document["mediaLibraries"].append(
                {
                    "id": "movies2",
                    "name": "Movies 2",
                    "storageId": "media-target-2",
                    "rootPath": "Movies",
                    "enabled": True,
                }
            )
            for rule in document["classificationPolicies"][0]["rules"]:
                if rule["id"] == "japanese-animation":
                    rule["result"]["mediaLibraryId"] = "movies2"
                    rule["result"]["path"] = ["Anime"]
            repository, _, objects, draft = self._open(root, document)
            try:
                multiple_storage = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Your Name",
                            "mediaType": "movie",
                            "year": 2016,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                    ],
                )
                rows.extend(multiple_storage.result["items"])
            finally:
                repository.close()

        self.assertGreaterEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(tuple(row.keys()), expected)
        self.assertTrue(
            any(
                row["failureCategory"] is not None and isinstance(row["nextAction"], str)
                for row in rows
            )
        )
        self.assertTrue(
            any(row["failureCategory"] is None and row["nextAction"] is None for row in rows)
        )
        self.assertEqual(single.status.value, "completed")
        self.assertEqual(
            multiple_storage.failure_category,
            "multiple_destination_storages",
        )

    def test_multi_sample_all_ready_verdict_is_ready_not_inflated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_root = root / "target-private"
            (target_root / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            before = self._tree_snapshot(target_root)
            repository, _, objects, draft = self._open(root)
            try:
                evidence = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    samples=[
                        {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "genres": ["Action"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Your Name",
                            "mediaType": "movie",
                            "year": 2016,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                        {
                            "title": "Spirited Away",
                            "mediaType": "movie",
                            "year": 2001,
                            "genres": ["Animation"],
                            "countries": ["JP"],
                            "extension": "mkv",
                        },
                    ],
                )
                result = evidence.result
                self.assertEqual(evidence.status.value, "completed")
                self.assertEqual(result["verdict"], "ready")
                self.assertEqual(result["sampleCount"], 3)
                self.assertEqual(result["collisions"], [])
                self.assertEqual([row["index"] for row in result["items"]], [0, 1, 2])
                self.assertEqual(
                    [row["projectedOutcome"] for row in result["items"]],
                    ["ready", "ready", "ready"],
                )
                for row in result["items"]:
                    self.assertIsNone(row["failureCategory"])
                    self.assertIsNone(row["message"])
                    self.assertIsNone(row["nextAction"])
                    self.assertFalse(row["targetExists"])
                destinations = [row["destinationPath"] for row in result["items"]]
                self.assertEqual(len(set(destinations)), 3)
                self.assertEqual(result["authorityGranted"], "none")
                self.assertEqual(set(result["guardMutationCalls"].values()), {0})
                self.assertEqual(self._tree_snapshot(target_root), before)
            finally:
                repository.close()

    def test_multi_sample_capability_gap_overrides_ready_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_root = root / "target-private"
            (target_root / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            before = self._tree_snapshot(target_root)
            document = self._document(root)
            document["organizePolicies"][0]["operation"] = "HARD_LINK"
            with patch.object(LocalStorage, "_can_hard_link", return_value=False):
                repository, _, objects, draft = self._open(root, document)
                try:
                    evidence = objects.destination_precheck(
                        draft.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        recognition_type="C",
                        samples=[
                            {
                                "title": "The Matrix",
                                "mediaType": "movie",
                                "year": 1999,
                                "genres": ["Action"],
                                "extension": "mkv",
                            },
                            {
                                "title": "Your Name",
                                "mediaType": "movie",
                                "year": 2016,
                                "genres": ["Animation"],
                                "countries": ["JP"],
                                "extension": "mkv",
                            },
                        ],
                    )
                    result = evidence.result
                    self.assertEqual(evidence.status.value, "completed")
                    self.assertEqual(result["verdict"], "capability_gap")
                    self.assertEqual(result["missingStorageCapabilities"], ["can_hard_link"])
                    self.assertEqual(result["requiredByOperation"], "hard_link")
                    self.assertEqual(result["sampleCount"], 2)
                    self.assertEqual(result["collisions"], [])
                    for row in result["items"]:
                        self.assertEqual(row["projectedOutcome"], "ready")
                        self.assertIsNone(row["failureCategory"])
                    self.assertEqual(result["authorityGranted"], "none")
                    self.assertEqual(set(result["guardMutationCalls"].values()), {0})
                    self.assertEqual(self._tree_snapshot(target_root), before)
                finally:
                    repository.close()

    def test_capability_gap_hardlink_cleanup_and_declared_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            before = self._tree_snapshot(root / "target-private")
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
                    self.assertEqual(evidence.result["deepestExistingAncestor"], "Movies")
                    self.assertEqual(
                        evidence.result["directoriesToCreate"],
                        [
                            "Movies/Action",
                            "Movies/Action/The Matrix (1999) [tmdbid-synthetic]",
                        ],
                    )
                    self.assertFalse(evidence.result["targetExists"])
                    self.assertEqual(set(evidence.result["guardMutationCalls"].values()), {0})
                    self.assertEqual(evidence.result["authorityGranted"], "none")
                    self.assertEqual(self._tree_snapshot(root / "target-private"), before)
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

    def test_constructs_no_provider_executor_or_runtime_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target-private"
            (target / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            runtime_database = root / "runtime.sqlite3"
            with SQLiteTaskRepository(runtime_database):
                pass
            before = self._tree_snapshot(target)

            for expected_failure in (None, "permission_denied"):
                with self.subTest(expected_failure=expected_failure):
                    repository, managed, objects, draft = self._open(root)
                    try:
                        storage_failure = (
                            patch.object(
                                LocalStorage,
                                "exists",
                                side_effect=StorageError(
                                    StorageErrorCode.PERMISSION_DENIED,
                                    "Exists",
                                    "Movies",
                                    "redacted",
                                ),
                            )
                            if expected_failure
                            else nullcontext()
                        )
                        with (
                            patch(
                                "mediaflow.application.configuration_objects.MetadataProviderRegistry",
                                side_effect=AssertionError(
                                    "destination precheck constructed Provider"
                                ),
                            ),
                            patch(
                                "mediaflow.application.organizer.OrganizerExecutor",
                                side_effect=AssertionError(
                                    "destination precheck constructed Executor"
                                ),
                            ),
                            storage_failure,
                        ):
                            evidence = self._run(objects, draft)
                        if expected_failure is None:
                            self.assertEqual(evidence.status.value, "completed")
                            self.assertEqual(evidence.result["authorityGranted"], "none")
                            self.assertEqual(
                                set(evidence.result["guardMutationCalls"].values()), {0}
                            )
                        else:
                            self.assertEqual(evidence.failure_category, expected_failure)
                        self._assert_runtime_authority_empty(runtime_database)
                        self.assertIsNone(repository.get_organize_authority(draft.revision_id))
                        self.assertEqual(self._tree_snapshot(target), before)
                        self._assert_revision_and_other_evidence_unchanged(
                            repository, managed, draft
                        )
                    finally:
                        repository.close()

    def test_multiple_samples_zero_mutation_and_no_construction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target-private"
            (target / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            runtime_database = root / "runtime.sqlite3"
            with SQLiteTaskRepository(runtime_database):
                pass
            before = self._tree_snapshot(target)
            first = {
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            }
            second = {
                "title": "Your Name",
                "mediaType": "movie",
                "year": 2016,
                "genres": ["Animation"],
                "countries": ["JP"],
                "extension": "mkv",
            }
            for collision in (False, True):
                with self.subTest(collision=collision):
                    repository, managed, objects, draft = self._open(root)
                    try:
                        samples = [first, copy.deepcopy(first) if collision else second]
                        with (
                            patch(
                                "mediaflow.application.configuration_objects.MetadataProviderRegistry",
                                side_effect=AssertionError(
                                    "destination precheck constructed Provider"
                                ),
                            ),
                            patch(
                                "mediaflow.application.organizer.OrganizerExecutor",
                                side_effect=AssertionError(
                                    "destination precheck constructed Executor"
                                ),
                            ),
                        ):
                            evidence = objects.destination_precheck(
                                draft.revision_id,
                                expected_version=draft.version,
                                expected_digest=draft.digest,
                                actor="operator",
                                recognition_type="C",
                                samples=samples,
                            )
                        if collision:
                            self.assertEqual(evidence.failure_category, "duplicate_destination")
                        else:
                            self.assertEqual(evidence.status.value, "completed")
                        self.assertEqual(set(evidence.result["guardMutationCalls"].values()), {0})
                        self.assertEqual(evidence.result["authorityGranted"], "none")
                        self._assert_runtime_authority_empty(runtime_database)
                        self.assertIsNone(repository.get_organize_authority(draft.revision_id))
                        self.assertEqual(self._tree_snapshot(target), before)
                        self._assert_revision_and_other_evidence_unchanged(
                            repository, managed, draft
                        )
                    finally:
                        repository.close()

    def test_api_rejects_invalid_sample_shapes_without_writing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target-private" / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            database = root / "configuration.sqlite3"
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(database) as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(document, actor="operator")
                previous = objects.destination_precheck(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    recognition_type="C",
                    sample=self._sample(),
                )
                with self.assertRaises(ValueError):
                    objects.destination_precheck(
                        draft.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        recognition_type="C",
                        samples=[self._sample()] * 9,
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
                    f"/api/v1/configuration/revisions/{draft.revision_id}/destination-precheck"
                )
                invalid_bodies = (
                    {
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                        "recognitionType": "C",
                        "samples": [self._sample()] * 9,
                    },
                    {
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                        "recognitionType": "C",
                        "samples": [],
                    },
                    {
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                        "recognitionType": "C",
                        "samples": "not-a-list",
                    },
                    {
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                        "recognitionType": "C",
                        "sample": self._sample(),
                        "samples": [self._sample()],
                    },
                    {
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                        "recognitionType": "C",
                    },
                    {
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                        "recognitionType": "C",
                        "samples": [self._sample(), "not-an-object"],
                    },
                )
                for body in invalid_bodies:
                    with self.subTest(body=body):
                        status, response = request(api, endpoint, method="POST", body=body)
                        self.assertEqual(status, 400)
                        self.assertEqual(response["error"]["code"], "invalid_request")
                        self.assertEqual(
                            repository.get_destination_precheck(draft.revision_id), previous
                        )

    def test_defensive_invalid_plan_is_unsafe_destination_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target-private"
            (target / "Movies").mkdir(parents=True)
            (root / "source-private").mkdir()
            before = self._tree_snapshot(target)
            repository, managed, objects, draft = self._open(root)
            original_plan = OrganizePlanner.plan

            def invalid_plan(planner, **kwargs):
                plan = original_plan(planner, **kwargs)
                return replace(
                    plan,
                    status=PlanStatus.INVALID,
                    conflicts=(
                        Conflict(
                            ConflictType.INVALID_DESTINATION,
                            plan.source,
                            plan.target,
                            "defensive invalid destination",
                        ),
                    ),
                )

            try:
                with (
                    patch.object(OrganizePlanner, "plan", invalid_plan),
                    patch(
                        "mediaflow.application.configuration_objects.ConflictResolver.apply_configured",
                        side_effect=AssertionError(
                            "invalid destination reached conflict resolution"
                        ),
                    ),
                ):
                    evidence = self._run(objects, draft)
                self.assertEqual(evidence.status.value, "failed")
                self.assertEqual(evidence.failure_category, "unsafe_destination")
                self.assertIsNone(evidence.result)
                self.assertEqual(evidence.document()["status"], "failed")
                self.assertIsNone(evidence.document()["result"])
                self.assertEqual(self._tree_snapshot(target), before)
                self._assert_revision_and_other_evidence_unchanged(repository, managed, draft)
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
                self.assertEqual(RUNTIME_SCHEMA_VERSION, 31)


if __name__ == "__main__":
    unittest.main()
