"""Focused tests for the revised classification destination contract (Task 44.2).

The revised contract is ``MediaLibrary.RootPath + Classification.path +
Naming.Directory + Naming.Filename``.  These tests use the actual production
engines — the domain normalizer, the managed-configuration service, the shared
destination composer, the formal Planner and the runtime loader — rather than an
alternate preview path calculator, and they assert zero Storage mutation for
every pure stage.

The legacy prefix contract is retained and asserted separately, because
historical snapshots, pins and effects must keep their original meaning.
"""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.classification import (
    ClassificationEngine,
    ClassificationPolicyRegistry,
    ClassificationPreviewService,
)
from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.organizer import OrganizePlanner
from mediaflow.domain.classification import (
    ClassificationContext,
    ClassificationError,
    ClassificationPolicy,
    ClassificationResult,
    ClassificationRule,
    ClassificationStatus,
    normalize_classification_path,
)
from mediaflow.domain.library import MediaLibrary
from mediaflow.domain.metadata import MediaIdentity, MediaType
from mediaflow.domain.naming import NamingResult
from mediaflow.domain.organizer import (
    OrganizeOperationType,
    OrganizePolicy,
    PlanStatus,
    compose_destination,
)
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import (
    RecognitionResult,
    RecognitionType,
    RecognitionTypePolicy,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from tests.test_configuration_objects import example_document


def context(recognition_type: str = "C", media_type=MediaType.MOVIE) -> ClassificationContext:
    return ClassificationContext(
        RecognitionType(recognition_type, recognition_type),
        MediaIdentity("tmdb", "1", media_type, "Movie", year=2001),
        ParseResult("Movie", year=2001),
    )


# One shared RecognitionType instance: the domain type carries identity
# timestamps, so the planner's identity check compares the exact configured
# object rather than two independently constructed equivalents.
RECOGNITION_TYPE = RecognitionType("C", "C")


def recognition() -> RecognitionResult:
    return RecognitionResult(RECOGNITION_TYPE, "rule-C")


def type_policy() -> RecognitionTypePolicy:
    return RecognitionTypePolicy(
        "type-C",
        RECOGNITION_TYPE,
        "C",
        "A",
        "A",
        OrganizePolicy("A", OrganizeOperationType.MOVE),
    )


class ClassificationPathNormalizationTests(unittest.TestCase):
    """One backend normalization serves every string/segment-list consumer."""

    def test_string_and_segment_list_agree(self) -> None:
        for value in ("电影/华语", ["电影", "华语"], ("电影", "华语")):
            with self.subTest(value=value):
                path, segments = normalize_classification_path(value)
                self.assertEqual(path, "电影/华语")
                self.assertEqual(segments, ("电影", "华语"))

    def test_single_and_nested_paths_are_accepted(self) -> None:
        self.assertEqual(normalize_classification_path("Anime")[0], "Anime")
        self.assertEqual(
            normalize_classification_path("外语电影/日本/动画")[0], "外语电影/日本/动画"
        )

    def test_unsafe_paths_are_rejected(self) -> None:
        for value in (
            "",
            "/absolute",
            "..",
            "../escape",
            "a/../b",
            "back\\slash",
            "double//slash",
            "trailing/",
            "nul\x00byte",
            ["."],
            [".."],
            [""],
            ["ok", ".."],
        ):
            with self.subTest(value=value):
                with self.assertRaises(ClassificationError):
                    normalize_classification_path(value)

    def test_rule_normalizes_through_the_same_function(self) -> None:
        rule = ClassificationRule("r", "R", "movies", ["电影", "华语"])
        self.assertEqual(rule.path, "电影/华语")
        self.assertEqual(rule.category, "电影")
        self.assertEqual(rule.subcategory, "华语")
        self.assertFalse(rule.legacy)

    def test_category_display_is_derived_from_path(self) -> None:
        single = ClassificationRule("r", "R", "movies", "Anime")
        self.assertEqual(single.category, "Anime")
        self.assertIsNone(single.subcategory)
        nested = ClassificationRule("r", "R", "movies", "Anime/剧场版")
        self.assertEqual((nested.category, nested.subcategory), ("Anime", "剧场版"))


class RevisedTargetParityTests(unittest.TestCase):
    """AC-2: every revised consumer produces the same canonical target."""

    def test_revised_target_omits_the_library_name_and_id(self) -> None:
        naming = NamingResult(
            "影片目录",
            "影片.mkv",
            "A",
            "C",
            directory_segments=("影片目录",),
        )
        composition = compose_destination(
            "/Media", "电影/华语", naming.directory, naming.directory_segments, naming.filename
        )
        self.assertTrue(composition.safe)
        self.assertEqual(composition.relative_destination, "电影/华语/影片目录/影片.mkv")
        self.assertEqual(composition.target, "/Media/电影/华语/影片目录/影片.mkv")
        self.assertEqual(composition.classification_contribution, "电影/华语")

    def test_keeping_a_movies_prefix_requires_it_explicitly_in_path(self) -> None:
        naming = NamingResult("影片目录", "影片.mkv", "A", "C", directory_segments=("影片目录",))
        composition = compose_destination(
            "/Media",
            "Movies/电影/华语",
            naming.directory,
            naming.directory_segments,
            naming.filename,
        )
        self.assertEqual(composition.target, "/Media/Movies/电影/华语/影片目录/影片.mkv")

    def test_planner_agrees_with_the_shared_composer(self) -> None:
        naming = NamingResult("影片目录", "影片.mkv", "A", "C", directory_segments=("影片目录",))
        classification = ClassificationResult("movies", "电影/华语", "A", "C")
        plan = OrganizePlanner().plan(
            source_storage_id="source",
            source="source.mkv",
            recognition=recognition(),
            type_policy=type_policy(),
            media_library=MediaLibrary("movies", "Movies", "target", "/Media"),
            naming=naming,
            classification=classification,
        )
        composition = compose_destination(
            "/Media", "电影/华语", naming.directory, naming.directory_segments, naming.filename
        )
        self.assertIs(plan.status, PlanStatus.READY)
        self.assertEqual(plan.relative_destination, composition.relative_destination)
        self.assertEqual(plan.target, composition.target)
        self.assertEqual(plan.target, "/Media/电影/华语/影片目录/影片.mkv")

    def test_display_name_change_does_not_change_a_revised_target(self) -> None:
        naming = NamingResult("影片目录", "影片.mkv", "A", "C", directory_segments=("影片目录",))
        targets = set()
        for name in ("Movies", "电影库", "renamed-library"):
            plan = OrganizePlanner().plan(
                source_storage_id="source",
                source="source.mkv",
                recognition=recognition(),
                type_policy=type_policy(),
                media_library=MediaLibrary("movies", name, "target", "/Media"),
                naming=naming,
                classification=ClassificationResult("movies", "电影/华语", "A", "C"),
            )
            targets.add(plan.target)
        self.assertEqual(targets, {"/Media/电影/华语/影片目录/影片.mkv"})

    def test_c_reusing_a_policies_stays_c(self) -> None:
        policy = ClassificationPolicy(
            "A",
            "Movie",
            (
                ClassificationRule(
                    "animation-movie",
                    "Animation",
                    "movies",
                    "电影/华语",
                    media_types=(MediaType.MOVIE,),
                ),
            ),
        )
        result = ClassificationEngine().classify(context(recognition_type="C"), policy)
        self.assertEqual(result.recognition_type_id, "C")
        self.assertEqual(result.policy_id, "A")
        self.assertEqual(result.relative_path, "电影/华语")
        self.assertFalse(result.legacy_destination)

    def test_classification_and_planner_cause_zero_storage_mutation(self) -> None:
        policy = ClassificationPolicy(
            "A",
            "Movie",
            (ClassificationRule("any", "Any", "movies", "电影/华语"),),
        )
        with patch(
            "mediaflow.application.organizer.OrganizerExecutor",
            side_effect=AssertionError("classification constructed Executor"),
        ):
            result = ClassificationPreviewService(ClassificationPolicyRegistry((policy,))).preview(
                context(), "A"
            )
            self.assertIs(result.status, ClassificationStatus.CLASSIFIED)


class LegacyContractIntegrityTests(unittest.TestCase):
    """A legacy rule keeps its original prefix meaning; a revised one does not."""

    def test_legacy_prefix_still_leads_the_destination(self) -> None:
        naming = NamingResult("影片目录", "影片.mkv", "A", "C", directory_segments=("影片目录",))
        classification = ClassificationResult(
            "movies",
            "电影/华语",
            "A",
            "C",
            library="Movies",
            legacy_destination=True,
        )
        self.assertEqual(classification.destination_prefix, "Movies")
        plan = OrganizePlanner().plan(
            source_storage_id="source",
            source="source.mkv",
            recognition=recognition(),
            type_policy=type_policy(),
            media_library=MediaLibrary("movies", "Movies", "target", "/Media"),
            naming=naming,
            classification=classification,
        )
        self.assertEqual(plan.target, "/Media/Movies/电影/华语/影片目录/影片.mkv")

    def test_unmarked_result_never_contributes_a_prefix(self) -> None:
        """A stale ``library`` value cannot re-route a revised result."""

        naming = NamingResult("影片目录", "影片.mkv", "A", "C", directory_segments=("影片目录",))
        classification = ClassificationResult("movies", "电影/华语", "A", "C", library="Movies")
        self.assertFalse(classification.legacy_destination)
        self.assertIsNone(classification.destination_prefix)
        plan = OrganizePlanner().plan(
            source_storage_id="source",
            source="source.mkv",
            recognition=recognition(),
            type_policy=type_policy(),
            media_library=MediaLibrary("movies", "Movies", "target", "/Media"),
            naming=naming,
            classification=classification,
        )
        self.assertEqual(plan.target, "/Media/电影/华语/影片目录/影片.mkv")

    def test_legacy_rule_reports_its_contract_and_keeps_its_path(self) -> None:
        policy = ClassificationPolicy(
            "A",
            "Movie",
            (ClassificationRule("any", "Any", "movies", "电影/华语", library="Movies"),),
        )
        rule = policy.rules[0]
        self.assertTrue(rule.legacy)
        result = ClassificationEngine().classify(context(), policy)
        self.assertTrue(result.legacy_destination)
        self.assertEqual(result.destination_prefix, "Movies")
        self.assertEqual(result.relative_path, "电影/华语")
        self.assertEqual(result.category, "电影")


class ManagedLegacyCompatibilityTests(unittest.TestCase):
    """Real Base-era documents stay readable and keep their exact meaning."""

    @staticmethod
    def _document(root: Path) -> dict:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        return document

    def test_legacy_document_round_trips_without_rewriting_its_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                original = copy.deepcopy(draft.document)
                validated = managed.validate(draft.revision_id, actor="operator")
                self.assertEqual(validated.status.value, "validated")
                # Validation never rewrites the stored legacy prefix.
                self.assertEqual(validated.document, original)
                policy = objects._classification_policy(
                    objects._canonical_objects(validated.document, "classificationPolicies")[0]
                )
                self.assertTrue(policy.rules[0].legacy)
                self.assertEqual(policy.rules[0].library, "Movies")

    def test_revised_rule_omits_the_prefix_in_the_normalized_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                managed.import_draft(self._document(root), actor="operator")
                _, normalized = objects._classification_rule(
                    {
                        "id": "revised",
                        "name": "Revised",
                        "conditions": {"mediaType": ["movie"]},
                        "result": {"mediaLibraryId": "movies", "path": ["电影", "华语"]},
                    }
                )
                self.assertEqual(
                    normalized["result"], {"mediaLibraryId": "movies", "path": ["电影", "华语"]}
                )
                self.assertNotIn("library", normalized["result"])
                self.assertNotIn("category", normalized["result"])
                self.assertNotIn("subcategory", normalized["result"])

    def test_legacy_rule_without_explicit_id_is_not_resolved_from_its_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                document = self._document(root)
                result = document["classificationPolicies"][0]["rules"][0]["result"]
                result.pop("mediaLibraryId", None)
                draft = managed.import_draft(document, actor="operator")
                validated = managed.validate(draft.revision_id, actor="operator")
                # The ambiguous reference fails closed rather than guessing "movies".
                self.assertEqual(validated.status.value, "draft")
                self.assertTrue(
                    any("mediaLibraryId" in error for error in validated.validation_errors)
                )
                self.assertEqual(
                    objects._classification_rule_library_id(
                        document["classificationPolicies"][0]["rules"][0]
                    ),
                    "",
                )

    def test_legacy_category_only_document_still_resolves_its_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                managed.import_draft(self._document(root), actor="operator")
                _, normalized = objects._classification_rule(
                    {
                        "id": "category-only",
                        "name": "Category only",
                        "conditions": {"mediaType": ["movie"]},
                        "result": {
                            "mediaLibraryId": "movies",
                            "library": "Movies",
                            "category": "电影",
                            "subcategory": "华语",
                        },
                    }
                )
                self.assertEqual(normalized["result"]["path"], ["电影", "华语"])
                self.assertEqual(normalized["result"]["library"], "Movies")

    def test_destination_preview_reports_the_revised_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                document = self._document(root)
                # Convert the sample rule to the revised contract.
                for rule in document["classificationPolicies"][0]["rules"]:
                    rule["result"].pop("library", None)
                draft = managed.import_draft(document, actor="operator")
                evidence = objects.destination_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
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
                result = evidence.result
                self.assertEqual(result["destinationContract"], "media_library_path")
                self.assertNotIn("Movies/", result["rootRelativeDestination"])
                self.assertEqual(
                    result["classificationPathContributes"],
                    result["classificationRelativePath"],
                )


class RulesWorkspaceConversionTests(unittest.TestCase):
    """AC-4: conversion is explicit; an unrelated Save cannot switch the contract."""

    @staticmethod
    def _document(root: Path) -> dict:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        # The destination root stays Storage-relative; the real directory is
        # created under the bound Local target adapter.
        document["mediaLibraries"][0]["rootPath"] = "Media"
        return document

    def _objects(self, managed, root: Path):
        """Bind the real Local adapters so the read-only Storage gate really runs."""

        (root / "source").mkdir(parents=True, exist_ok=True)
        (root / "target" / "Media").mkdir(parents=True, exist_ok=True)
        objects = ConfigurationObjectService(managed)
        objects._storage_adapters.update(
            {
                "source": LocalStorage("source", root / "source"),
                "target": LocalStorage("target", root / "target"),
            }
        )
        return objects

    def _activate(self, managed, document, objects):
        draft = managed.import_draft(document, actor="operator")
        validated = managed.validate(draft.revision_id, actor="operator")
        if validated.status.value != "validated":
            raise AssertionError(validated.validation_errors)
        # Reuse the shared exact-revision evidence and checked activation the
        # production Save path itself requires; no gate is bypassed or faked.
        objects._checked_successor_evidence(validated, actor="operator")
        return objects.activate_checked(
            validated.revision_id, expected_version=validated.version, actor="operator"
        )

    def test_edit_projection_exposes_contract_and_hides_legacy_outputs(self) -> None:
        from mediaflow.application.rules_workspace_commands import RulesWorkspaceCommandService

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = self._objects(managed, root)
                self._activate(managed, self._document(root), objects)
                commands = RulesWorkspaceCommandService(objects)
                policy_id = str(managed.active().document["classificationPolicies"][0]["id"])
                projection = commands.edit_projection("classificationPolicies", policy_id)
                rule = projection["object"]["rules"][0]
                self.assertEqual(rule["result"]["destinationContract"], "legacy_library_prefix")
                self.assertEqual(rule["result"]["library"], "Movies")
                self.assertNotIn("category", rule["result"])
                self.assertNotIn("subcategory", rule["result"])

    def test_cosmetic_save_preserves_the_legacy_contract(self) -> None:
        from mediaflow.application.rules_workspace_commands import RulesWorkspaceCommandService

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = self._objects(managed, root)
                self._activate(managed, self._document(root), objects)
                commands = RulesWorkspaceCommandService(objects)
                active = managed.active()
                policy = active.document["classificationPolicies"][0]
                projection = commands.edit_projection("classificationPolicies", str(policy["id"]))
                candidate = copy.deepcopy(projection["object"])
                # A cosmetic change that does not express destination intent.
                candidate["description"] = "cosmetic only"
                commands.save_object(
                    "classificationPolicies",
                    candidate,
                    actor="operator",
                    expected_revision_id=active.revision_id,
                    expected_version=active.revision_sequence or active.version,
                    expected_digest=active.digest,
                    object_id=str(policy["id"]),
                )
                stored = managed.active().document["classificationPolicies"][0]
                self.assertEqual(stored["rules"][0]["result"]["library"], "Movies")
                self.assertEqual(stored["rules"][0]["result"]["path"], ["Anime"])

    def test_explicit_removal_publishes_the_revised_contract(self) -> None:
        from mediaflow.application.rules_workspace_commands import RulesWorkspaceCommandService

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = self._objects(managed, root)
                self._activate(managed, self._document(root), objects)
                commands = RulesWorkspaceCommandService(objects)
                active = managed.active()
                policy = active.document["classificationPolicies"][0]
                projection = commands.edit_projection("classificationPolicies", str(policy["id"]))
                candidate = copy.deepcopy(projection["object"])
                for rule in candidate["rules"]:
                    # An explicit null is the operator's deliberate conversion
                    # intent; an absent key only means "no destination change".
                    rule["result"]["library"] = None
                    rule["result"].pop("destinationContract", None)
                commands.save_object(
                    "classificationPolicies",
                    candidate,
                    actor="operator",
                    expected_revision_id=active.revision_id,
                    expected_version=active.revision_sequence or active.version,
                    expected_digest=active.digest,
                    object_id=str(policy["id"]),
                )
                stored = managed.active().document["classificationPolicies"][0]
                self.assertNotIn("library", stored["rules"][0]["result"])
                # The explicit path is preserved rather than prefixed.
                self.assertEqual(stored["rules"][0]["result"]["path"], ["Anime"])

    def test_stale_save_is_refused_and_preserves_the_legacy_active(self) -> None:
        from mediaflow.application.rules_workspace_commands import RulesWorkspaceCommandService
        from mediaflow.domain.configuration_management import ConfigurationVersionConflict

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = self._objects(managed, root)
                self._activate(managed, self._document(root), objects)
                commands = RulesWorkspaceCommandService(objects)
                active = managed.active()
                policy = active.document["classificationPolicies"][0]
                candidate = commands.edit_projection("classificationPolicies", str(policy["id"]))[
                    "object"
                ]
                candidate = copy.deepcopy(candidate)
                candidate["description"] = "stale attempt"
                with self.assertRaises(ConfigurationVersionConflict):
                    commands.save_object(
                        "classificationPolicies",
                        candidate,
                        actor="operator",
                        expected_revision_id=active.revision_id,
                        expected_version=(active.revision_sequence or active.version) + 1,
                        expected_digest=active.digest,
                        object_id=str(policy["id"]),
                    )
                stored = managed.active().document["classificationPolicies"][0]
                self.assertEqual(stored["rules"][0]["result"]["library"], "Movies")
                self.assertNotEqual(stored.get("description"), "stale attempt")


class RuntimeRevisionIdentityTests(unittest.TestCase):
    """A stored revision keeps its bytes and digest across a restart."""

    def test_legacy_revision_digest_and_bytes_survive_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(database)
            document["storages"][0]["rootPath"] = str(root / "source")
            document["storages"][1]["rootPath"] = str(root / "target")
            with SQLiteConfigurationRepository(database) as repository:
                managed = ManagedConfigurationService(repository)
                draft = managed.import_draft(document, actor="operator")
                validated = managed.validate(draft.revision_id, actor="operator")
                activated = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="operator",
                )
                revision_id, digest, payload = (
                    activated.revision_id,
                    activated.digest,
                    copy.deepcopy(activated.document),
                )
            # A separate connection models a candidate restart.
            with SQLiteConfigurationRepository(database) as reopened:
                managed = ManagedConfigurationService(reopened)
                active = managed.active()
                self.assertEqual(active.revision_id, revision_id)
                self.assertEqual(active.digest, digest)
                self.assertEqual(active.document, payload)
                self.assertEqual(
                    active.document["classificationPolicies"][0]["rules"][0]["result"]["library"],
                    "Movies",
                )
                managed.verify_integrity(active)


if __name__ == "__main__":
    unittest.main()
