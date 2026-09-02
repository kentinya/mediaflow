from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationVersionConflict,
)
from mediaflow.domain.recognition import PolicyResolutionErrorCode
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_configuration_management import (
    CONFIGURATION_SCHEMA_VERSION,
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION as RUNTIME_SCHEMA_VERSION
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request


def policy(policy_id: str = "managed") -> dict[str, object]:
    return {
        "id": policy_id,
        "operation": "MOVE",
        "conflictStrategy": "manual",
        "overwrite": False,
        "duplicateDetection": {
            "mode": "none",
            "fastSampleBytes": 1_048_576,
            "fullMaxFileSize": 1_099_511_627_776,
            "chunkSize": 1_048_576,
        },
        "rollback": {"enabled": False, "cleanupCreatedDirectories": True},
        "sourceDirectoryCleanup": {
            "mode": "none",
            "maxParentDirectories": 1,
            "ignorePatterns": [],
            "maxEntries": 100,
        },
        "attachments": {
            "enabled": False,
            "subtitles": True,
            "nfo": True,
            "artwork": True,
            "trailers": True,
            "otherSameStem": False,
        },
    }


def invalid_policies() -> tuple[tuple[str, dict[str, object], str], ...]:
    cases: list[tuple[str, dict[str, object], str]] = []

    def add(label: str, change, message: str) -> None:
        candidate = policy(f"invalid-{label}")
        change(candidate)
        cases.append((label, candidate, message))

    add("top-field", lambda value: value.update({"unknown": True}), "unsupported field")
    add(
        "sub-field",
        lambda value: value["duplicateDetection"].update({"unknown": 1}),
        "unknown duplicateDetection field",
    )
    add("unsupported", lambda value: value.update({"operation": "teleport"}), "unsupported")
    add("delete", lambda value: value.update({"operation": "delete"}), "Move, Copy")
    add(
        "create-directory",
        lambda value: value.update({"operation": "create_directory"}),
        "Move, Copy",
    )
    add(
        "overwrite-conflict",
        lambda value: value.update({"overwrite": True, "conflictStrategy": "rename"}),
        "conflicts",
    )
    add(
        "fast-sample",
        lambda value: value["duplicateDetection"].update({"fastSampleBytes": 0}),
        "fast Hash sample",
    )
    add(
        "chunk-size",
        lambda value: value["duplicateDetection"].update({"chunkSize": 0}),
        "Hash chunk size",
    )
    add(
        "full-size",
        lambda value: value["duplicateDetection"].update({"fullMaxFileSize": 0}),
        "full Hash maximum",
    )
    add(
        "parents",
        lambda value: value["sourceDirectoryCleanup"].update({"maxParentDirectories": 0}),
        "maximum parent directories",
    )
    add(
        "entries",
        lambda value: value["sourceDirectoryCleanup"].update({"maxEntries": 0}),
        "maximum entries",
    )
    add(
        "unsafe-ignore",
        lambda value: value.update(
            {
                "sourceDirectoryCleanup": {
                    "mode": "ignorable",
                    "ignorePatterns": ["*"],
                }
            }
        ),
        "ignore pattern is unsafe",
    )
    add(
        "misplaced-ignore",
        lambda value: value["sourceDirectoryCleanup"].update(
            {"mode": "none", "ignorePatterns": [".DS_Store"]}
        ),
        "require ignorable mode",
    )
    add("non-object", lambda value: value.update({"rollback": "yes"}), "must be an object")
    add(
        "attachment-boolean",
        lambda value: value["attachments"].update({"enabled": "yes"}),
        "must be boolean",
    )
    return tuple(cases)


class ManagedOrganizePolicyJourneyTests(unittest.TestCase):
    @staticmethod
    def _document(root: Path) -> dict:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        return document

    def test_crud_audit_reference_block_and_delete_after_repoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                evidence = objects.references(draft.revision_id)["organize_policy:A"]
                self.assertGreaterEqual(evidence["total"], 1)
                self.assertIn(
                    {
                        "section": "recognitionTypePolicies",
                        "id": "type-C",
                        "field": "organizePolicy",
                    },
                    evidence["items"],
                )
                unchanged = copy.deepcopy(draft.document)
                with self.assertRaises(ConfigurationObjectReferenced) as blocked:
                    objects.mutate(
                        draft.revision_id,
                        ConfigurationObjectKind.ORGANIZE_POLICY,
                        object_id="A",
                        value=None,
                        expected_version=draft.version,
                        actor="operator",
                        delete=True,
                    )
                self.assertEqual(blocked.exception.reference_items[0].field, "organizePolicy")
                self.assertEqual(managed.require(draft.revision_id).document, unchanged)

                created = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.ORGANIZE_POLICY,
                    object_id=None,
                    value=policy(),
                    expected_version=draft.version,
                    actor="operator",
                )
                updated_policy = policy()
                updated_policy["operation"] = "COPY"
                updated = objects.mutate(
                    created.revision_id,
                    ConfigurationObjectKind.ORGANIZE_POLICY,
                    object_id="managed",
                    value=updated_policy,
                    expected_version=created.version,
                    actor="operator",
                )
                copied = objects.mutate(
                    updated.revision_id,
                    ConfigurationObjectKind.ORGANIZE_POLICY,
                    object_id=None,
                    value=policy("managed-copy"),
                    expected_version=updated.version,
                    actor="operator",
                )
                deleted = objects.mutate(
                    copied.revision_id,
                    ConfigurationObjectKind.ORGANIZE_POLICY,
                    object_id="managed-copy",
                    value=None,
                    expected_version=copied.version,
                    actor="operator",
                    delete=True,
                )
                self.assertEqual(deleted.version, draft.version + 4)
                self.assertEqual(
                    next(
                        item
                        for item in deleted.document["organizePolicies"]
                        if item["id"] == "managed"
                    )["operation"],
                    "copy",
                )
                actions = [
                    item.safe_after().get("objectChange", {}).get("action")
                    for item in repository.list_revision_audits(draft.revision_id)
                    if item.safe_after().get("objectChange", {}).get("objectId")
                    in {"managed", "managed-copy"}
                ]
                self.assertCountEqual(
                    actions, ["guided_create", "guided_update", "guided_create", "guided_delete"]
                )

                current = deleted
                for mapping in tuple(current.document["recognitionTypePolicies"]):
                    if mapping["organizePolicy"] != "A":
                        continue
                    replacement = copy.deepcopy(mapping)
                    replacement["organizePolicy"] = "B"
                    current = objects.mutate(
                        current.revision_id,
                        ConfigurationObjectKind.RECOGNITION_TYPE_POLICY,
                        object_id=mapping["id"],
                        value=replacement,
                        expected_version=current.version,
                        actor="operator",
                    )
                current = objects.mutate(
                    current.revision_id,
                    ConfigurationObjectKind.ORGANIZE_POLICY,
                    object_id="A",
                    value=None,
                    expected_version=current.version,
                    actor="operator",
                    delete=True,
                )
                self.assertNotIn("A", [item["id"] for item in current.document["organizePolicies"]])

    def test_invalid_service_inputs_leave_revision_and_evidence_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                original = copy.deepcopy(draft.document)
                for label, candidate, expected_message in invalid_policies():
                    with self.subTest(label=label), self.assertRaises(ValueError) as caught:
                        objects.mutate(
                            draft.revision_id,
                            ConfigurationObjectKind.ORGANIZE_POLICY,
                            object_id=None,
                            value=candidate,
                            expected_version=draft.version,
                            actor="operator",
                        )
                    self.assertIn(expected_message, str(caught.exception))
                    self.assertLessEqual(len(str(caught.exception)), 500)
                    current = managed.require(draft.revision_id)
                    self.assertEqual(
                        (current.version, current.digest), (draft.version, draft.digest)
                    )
                    self.assertEqual(current.document, original)
                    self.assertIsNone(repository.get_organize_authority(draft.revision_id))

    def test_normalization_is_semantically_neutral_for_every_example_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                original = {
                    item.policy_id: item
                    for item in load_runtime_configuration(
                        draft.document
                    ).strategy.organize_policies
                }
                current = draft
                for item in tuple(draft.document["organizePolicies"]):
                    current = objects.mutate(
                        current.revision_id,
                        ConfigurationObjectKind.ORGANIZE_POLICY,
                        object_id=item["id"],
                        value=item,
                        expected_version=current.version,
                        actor="operator",
                    )
                normalized = {
                    item.policy_id: item
                    for item in load_runtime_configuration(
                        current.document
                    ).strategy.organize_policies
                }
                self.assertEqual(normalized, original)

    def test_authority_resolution_failures_stale_and_zero_side_effects(self) -> None:
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
                        side_effect=AssertionError("authority constructed Storage"),
                    ),
                    patch(
                        "mediaflow.application.configuration_objects.MetadataProviderRegistry",
                        side_effect=AssertionError("authority constructed Provider"),
                    ),
                    patch(
                        "mediaflow.application.organizer.OrganizePlanner",
                        side_effect=AssertionError("authority constructed Planner"),
                    ),
                    patch(
                        "mediaflow.application.organizer.OrganizerExecutor",
                        side_effect=AssertionError("authority constructed Executor"),
                    ),
                ):
                    evidence = objects.organize_authority(
                        draft.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        recognition_type="C",
                    )
                result = evidence.result
                self.assertEqual(result["recognitionType"], "C")
                self.assertEqual(result["recognitionTypePolicyId"], "type-C")
                self.assertEqual(result["organizePolicyId"], "A")
                self.assertEqual(result["operation"], "move")
                self.assertEqual(result["conflictStrategy"], "manual")
                self.assertFalse(result["overwriteAuthorized"])
                self.assertFalse(result["deleteAuthorized"])
                self.assertEqual(result["requiredStorageCapabilities"], ["can_move"])
                self.assertEqual(result["fallback"], "none; unsupported capability is a failure")
                self.assertEqual(evidence.document()["sideEffects"], "none")
                self.assertEqual(managed.require(draft.revision_id).document, original)

                changed_policy = copy.deepcopy(draft.document["organizePolicies"][0])
                changed_policy["conflictStrategy"] = "overwrite"
                changed_policy["overwrite"] = True
                changed_policy["sourceDirectoryCleanup"] = {
                    "mode": "ignorable",
                    "maxParentDirectories": 2,
                    "ignorePatterns": [".DS_Store"],
                    "maxEntries": 20,
                }
                changed = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.ORGANIZE_POLICY,
                    object_id="A",
                    value=changed_policy,
                    expected_version=draft.version,
                    actor="operator",
                )
                destructive = objects.organize_authority(
                    changed.revision_id,
                    expected_version=changed.version,
                    expected_digest=changed.digest,
                    actor="operator",
                    recognition_type="C",
                )
                self.assertTrue(destructive.result["overwriteAuthorized"])
                self.assertTrue(destructive.result["deleteAuthorized"])
                self.assertEqual(
                    destructive.result["requiredStorageCapabilities"], ["can_move", "can_delete"]
                )
                self.assertTrue(any("overwrite" in item for item in destructive.result["warnings"]))
                self.assertTrue(
                    any("sourceDirectoryCleanup" in item for item in destructive.result["warnings"])
                )
                preserved = destructive.document()

                changed_again = copy.deepcopy(changed_policy)
                changed_again["operation"] = "HARDLINK"
                edited = objects.mutate(
                    changed.revision_id,
                    ConfigurationObjectKind.ORGANIZE_POLICY,
                    object_id="A",
                    value=changed_again,
                    expected_version=changed.version,
                    actor="operator",
                )
                self.assertTrue(
                    objects.revision_detail(edited.revision_id)["organizeAuthority"]["stale"]
                )
                with self.assertRaises(ConfigurationVersionConflict) as conflict:
                    objects.organize_authority(
                        edited.revision_id,
                        expected_version=changed.version,
                        expected_digest=changed.digest,
                        actor="operator",
                        recognition_type="C",
                    )
                self.assertEqual(conflict.exception.current_version, edited.version)
                self.assertEqual(
                    repository.get_organize_authority(edited.revision_id).document(), preserved
                )
                hard_link = objects.organize_authority(
                    edited.revision_id,
                    expected_version=edited.version,
                    expected_digest=edited.digest,
                    actor="operator",
                    recognition_type="C",
                )
                self.assertIn("can_hard_link", hard_link.result["requiredStorageCapabilities"])
                self.assertTrue(any("no fallback" in item for item in hard_link.result["warnings"]))

    def test_policy_resolution_error_categories_are_persisted(self) -> None:
        variants = []
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
        disabled_type = example_document()
        disabled_type["recognitionTypes"][2]["enabled"] = False
        variants.append(
            (
                "disabled-type",
                disabled_type,
                "C",
                PolicyResolutionErrorCode.RECOGNITION_TYPE_DISABLED,
            )
        )
        disabled_policy = example_document()
        next(item for item in disabled_policy["metadataPolicies"] if item["id"] == "C")[
            "enabled"
        ] = False
        variants.append(
            ("disabled-policy", disabled_policy, "C", PolicyResolutionErrorCode.POLICY_DISABLED)
        )
        dangling = example_document()
        dangling["recognitionTypePolicies"][2]["organizePolicy"] = "absent"
        variants.append(
            ("dangling", dangling, "C", PolicyResolutionErrorCode.INVALID_POLICY_REFERENCE)
        )

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
                        evidence = objects.organize_authority(
                            draft.revision_id,
                            expected_version=draft.version,
                            expected_digest=draft.digest,
                            actor="operator",
                            recognition_type=requested,
                        )
                        self.assertEqual(evidence.status.value, "failed")
                        self.assertEqual(evidence.failure_category, category.value)
                        self.assertLessEqual(len(evidence.message), 500)
                        self.assertEqual(
                            repository.get_organize_authority(draft.revision_id).document(),
                            evidence.document(),
                        )

    def test_authenticated_api_rejections_success_and_stale_share_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                managed = ManagedConfigurationService(repository)
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=managed,
                    bootstrap_document=document,
                )
                draft = managed.import_draft(document, actor="operator")
                collection = (
                    f"/api/v1/configuration/revisions/{draft.revision_id}/objects/organizePolicies"
                )
                for label, candidate, expected_message in invalid_policies():
                    with self.subTest(label=label):
                        status, response = request(
                            api,
                            collection,
                            method="POST",
                            body={"expectedVersion": draft.version, "object": candidate},
                        )
                        self.assertEqual(status, 400)
                        self.assertEqual(response["error"]["code"], "invalid_request")
                        self.assertIn(expected_message, response["error"]["message"])
                        self.assertLessEqual(len(response["error"]["message"]), 500)
                        self.assertEqual(managed.require(draft.revision_id).version, draft.version)
                        self.assertIsNone(repository.get_organize_authority(draft.revision_id))
                status, evidence = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/organize-authority",
                    method="POST",
                    body={
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                        "recognitionType": "C",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(evidence["result"]["recognitionType"], "C")
                stored = repository.get_organize_authority(draft.revision_id).document()
                status, stale = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/organize-authority",
                    method="POST",
                    body={
                        "expectedVersion": draft.version + 1,
                        "expectedDigest": draft.digest,
                        "recognitionType": "C",
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(stale["error"]["code"], "configuration_version_conflict")
                self.assertEqual(
                    repository.get_organize_authority(draft.revision_id).document(), stored
                )

    def test_optional_section_marker_seven_upgrade_and_active_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            document = self._document(root)
            with SQLiteConfigurationRepository(database) as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(document, actor="operator")
                naming = objects.naming_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample={"title": "Example", "mediaType": "movie", "year": 2024},
                )
                classification = objects.classification_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample={"title": "Example", "mediaType": "movie"},
                )
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "UPDATE schema_version SET version=7 WHERE component='configuration_management'"
                )
            with SQLiteConfigurationRepository(database) as repository:
                self.assertEqual(
                    repository.get_naming_preview(draft.revision_id).document(), naming.document()
                )
                self.assertEqual(
                    repository.get_classification_preview(draft.revision_id).document(),
                    classification.document(),
                )
                with sqlite3.connect(database) as connection:
                    marker = connection.execute(
                        "SELECT version FROM schema_version "
                        "WHERE component='configuration_management'"
                    ).fetchone()[0]
                self.assertEqual(marker, CONFIGURATION_SCHEMA_VERSION)
                self.assertEqual(RUNTIME_SCHEMA_VERSION, 29)

                optional = copy.deepcopy(document)
                optional.pop("organizePolicies")
                optional_draft = ManagedConfigurationService(repository).import_draft(
                    optional, actor="operator"
                )
                detail = ConfigurationObjectService(
                    ManagedConfigurationService(repository)
                ).revision_detail(optional_draft.revision_id)
                self.assertEqual(detail["objects"]["organizePolicies"], [])
                self.assertNotIn("organize_policy:A", detail["references"])

                active_draft = ManagedConfigurationService(repository).import_draft(
                    document, actor="operator"
                )
                validated = ManagedConfigurationService(repository).validate(
                    active_draft.revision_id, actor="operator"
                )
                active = ManagedConfigurationService(repository).activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="operator",
                )
                with self.assertRaises(ConfigurationVersionConflict):
                    ConfigurationObjectService(
                        ManagedConfigurationService(repository)
                    ).organize_authority(
                        active.revision_id,
                        expected_version=active.version,
                        expected_digest=active.digest,
                        actor="operator",
                        recognition_type="C",
                    )
                self.assertIsNone(repository.get_organize_authority(active.revision_id))


if __name__ == "__main__":
    unittest.main()
