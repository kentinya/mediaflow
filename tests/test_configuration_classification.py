from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.classification import ClassificationError, ClassificationErrorCode
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationVersionConflict,
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


def policy(policy_id: str = "managed") -> dict[str, object]:
    return {
        "id": policy_id,
        "name": "Managed classification",
        "description": "one bounded policy",
        "enabled": True,
        "priority": 10,
        "rules": [
            {
                "id": "action",
                "name": "Action movie",
                "priority": 100,
                "conditions": {"mediaType": ["movie"], "genres": ["Action"]},
                "result": {
                    "mediaLibraryId": "movies",
                    "library": "Movies",
                    "path": ["Action"],
                },
            }
        ],
    }


class ManagedClassificationPolicyJourneyTests(unittest.TestCase):
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
                references = objects.references(draft.revision_id)["classification_policy:A"]
                self.assertGreaterEqual(references["total"], 1)
                self.assertTrue(
                    any(
                        item
                        == {
                            "section": "recognitionTypePolicies",
                            "id": "type-A",
                            "field": "classificationPolicy",
                        }
                        for item in references["items"]
                    )
                )
                unchanged = copy.deepcopy(draft.document)
                with self.assertRaises(ConfigurationObjectReferenced) as blocked:
                    objects.mutate(
                        draft.revision_id,
                        ConfigurationObjectKind.CLASSIFICATION_POLICY,
                        object_id="A",
                        value=None,
                        expected_version=draft.version,
                        actor="operator",
                        delete=True,
                    )
                self.assertEqual(blocked.exception.reference_items[0].field, "classificationPolicy")
                self.assertEqual(managed.require(draft.revision_id).document, unchanged)

                created = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.CLASSIFICATION_POLICY,
                    object_id=None,
                    value=policy(),
                    expected_version=draft.version,
                    actor="operator",
                )
                updated_value = policy()
                updated_value["priority"] = 20
                updated = objects.mutate(
                    created.revision_id,
                    ConfigurationObjectKind.CLASSIFICATION_POLICY,
                    object_id="managed",
                    value=updated_value,
                    expected_version=created.version,
                    actor="operator",
                )
                copied_value = policy("managed-copy")
                copied = objects.mutate(
                    updated.revision_id,
                    ConfigurationObjectKind.CLASSIFICATION_POLICY,
                    object_id=None,
                    value=copied_value,
                    expected_version=updated.version,
                    actor="operator",
                )
                deleted = objects.mutate(
                    copied.revision_id,
                    ConfigurationObjectKind.CLASSIFICATION_POLICY,
                    object_id="managed-copy",
                    value=None,
                    expected_version=copied.version,
                    actor="operator",
                    delete=True,
                )
                self.assertEqual(deleted.version, draft.version + 4)
                self.assertIn(
                    "managed", [item["id"] for item in deleted.document["classificationPolicies"]]
                )
                self.assertNotIn(
                    "managed-copy",
                    [item["id"] for item in deleted.document["classificationPolicies"]],
                )
                object_actions = [
                    item.safe_after().get("objectChange", {}).get("action")
                    for item in repository.list_revision_audits(draft.revision_id)
                    if item.safe_after().get("objectChange", {}).get("objectId")
                    in {"managed", "managed-copy"}
                ]
                self.assertCountEqual(
                    object_actions,
                    ["guided_create", "guided_update", "guided_create", "guided_delete"],
                )
                current = deleted
                for mapping in tuple(current.document["recognitionTypePolicies"]):
                    if mapping["classificationPolicy"] != "A":
                        continue
                    replacement = copy.deepcopy(mapping)
                    replacement["classificationPolicy"] = "B"
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
                    ConfigurationObjectKind.CLASSIFICATION_POLICY,
                    object_id="A",
                    value=None,
                    expected_version=current.version,
                    actor="operator",
                    delete=True,
                )
                self.assertNotIn(
                    "A", [item["id"] for item in current.document["classificationPolicies"]]
                )

    def test_invalid_service_inputs_leave_revision_and_evidence_unchanged(self) -> None:
        cases = (
            ("condition", {"conditions": {"unknown": []}}, ClassificationErrorCode.INVALID_RULE),
            ("result", {"result": {"unknown": "x"}}, ClassificationErrorCode.INVALID_RULE),
            ("absolute", {"result": {"path": "/unsafe"}}, ClassificationErrorCode.UNSAFE_PATH),
            ("traversal", {"result": {"path": [".."]}}, ClassificationErrorCode.UNSAFE_PATH),
            (
                "missing-library",
                {"result": {"mediaLibraryId": ""}},
                ClassificationErrorCode.INVALID_RULE,
            ),
            (
                "oversized-library",
                {"result": {"mediaLibraryId": "x" * 65}},
                ClassificationErrorCode.INVALID_RULE,
            ),
            ("empty-rules", {"rules": []}, ClassificationErrorCode.INVALID_POLICY),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                original = copy.deepcopy(draft.document)
                for label, change, category in cases:
                    candidate = policy(f"invalid-{label}")
                    if "rules" in change:
                        candidate["rules"] = change["rules"]
                    else:
                        rule = candidate["rules"][0]
                        nested = next(iter(change))
                        rule[nested].update(change[nested])
                    with (
                        self.subTest(label=label),
                        self.assertRaises(ClassificationError) as caught,
                    ):
                        objects.mutate(
                            draft.revision_id,
                            ConfigurationObjectKind.CLASSIFICATION_POLICY,
                            object_id=None,
                            value=candidate,
                            expected_version=draft.version,
                            actor="operator",
                        )
                    self.assertEqual(caught.exception.code, category)
                    self.assertLessEqual(len(str(caught.exception)), 500)
                    current = managed.require(draft.revision_id)
                    self.assertEqual(
                        (current.version, current.digest), (draft.version, draft.digest)
                    )
                    self.assertEqual(current.document, original)
                    self.assertIsNone(repository.get_classification_preview(draft.revision_id))

                duplicate = policy("duplicate")
                duplicate["rules"].append(copy.deepcopy(duplicate["rules"][0]))
                with self.assertRaises(ClassificationError) as duplicate_error:
                    objects.mutate(
                        draft.revision_id,
                        ConfigurationObjectKind.CLASSIFICATION_POLICY,
                        object_id=None,
                        value=duplicate,
                        expected_version=draft.version,
                        actor="operator",
                    )
                self.assertEqual(
                    duplicate_error.exception.code, ClassificationErrorCode.INVALID_POLICY
                )
                non_object = policy("non-object")
                non_object["rules"] = ["invalid"]
                with self.assertRaises(ClassificationError) as non_object_error:
                    objects.mutate(
                        draft.revision_id,
                        ConfigurationObjectKind.CLASSIFICATION_POLICY,
                        object_id=None,
                        value=non_object,
                        expected_version=draft.version,
                        actor="operator",
                    )
                self.assertEqual(
                    non_object_error.exception.code, ClassificationErrorCode.INVALID_RULE
                )

    def test_preview_classified_unclassified_unresolved_stale_and_zero_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                original = copy.deepcopy(draft.document)
                sample = {
                    "title": "Mission Impossible",
                    "mediaType": "movie",
                    "recognitionType": "C",
                    "year": 1996,
                    "genres": ["Action"],
                    "countries": ["US"],
                    "languages": ["en"],
                    "keywords": [],
                }
                with (
                    patch(
                        "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                        side_effect=AssertionError("classification preview constructed Storage"),
                    ),
                    patch(
                        "mediaflow.application.configuration_objects.MetadataProviderRegistry",
                        side_effect=AssertionError("classification preview constructed Provider"),
                    ),
                ):
                    invalid_sample = objects.classification_preview(
                        draft.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        policy_id="A",
                        sample={"title": "Example", "unsupported": "value"},
                    )
                    classified = objects.classification_preview(
                        draft.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        policy_id="A",
                        sample=sample,
                    )
                self.assertEqual(invalid_sample.status.value, "failed")
                self.assertEqual(invalid_sample.failure_category, "invalid_input")
                self.assertEqual(invalid_sample.document()["sideEffects"], "none")
                self.assertEqual(classified.result["status"], "classified")
                self.assertEqual(classified.result["recognitionType"], "C")
                self.assertEqual(classified.result["mediaLibraryId"], "movies")
                self.assertTrue(classified.result["mediaLibraryResolved"])
                self.assertEqual(classified.result["relativePath"], "Action")
                self.assertEqual(classified.result["matchedRuleId"], "action-movie")
                self.assertIn("genre=Action", classified.result["matchEvidence"])
                self.assertEqual(managed.require(draft.revision_id).document, original)

                unclassified = objects.classification_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample={"title": "Example", "mediaType": "tv", "recognitionType": "C"},
                )
                self.assertEqual(unclassified.result["status"], "unclassified")
                self.assertIn("adjust", unclassified.next_action)

                unresolved_policy = policy("unresolved")
                unresolved_policy["rules"][0]["result"]["mediaLibraryId"] = "absent"
                changed = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.CLASSIFICATION_POLICY,
                    object_id=None,
                    value=unresolved_policy,
                    expected_version=draft.version,
                    actor="operator",
                )
                unresolved = objects.classification_preview(
                    changed.revision_id,
                    expected_version=changed.version,
                    expected_digest=changed.digest,
                    actor="operator",
                    policy_id="unresolved",
                    sample=sample,
                )
                self.assertFalse(unresolved.result["mediaLibraryResolved"])
                self.assertIn("unresolved_media_library:absent", unresolved.result["warnings"])
                preserved = unresolved.document()
                edited_value = policy("unresolved")
                edited_value["priority"] = 11
                edited = objects.mutate(
                    changed.revision_id,
                    ConfigurationObjectKind.CLASSIFICATION_POLICY,
                    object_id="unresolved",
                    value=edited_value,
                    expected_version=changed.version,
                    actor="operator",
                )
                self.assertTrue(
                    objects.revision_detail(edited.revision_id)["classificationPreview"]["stale"]
                )
                with self.assertRaises(ConfigurationVersionConflict) as conflict:
                    objects.classification_preview(
                        edited.revision_id,
                        expected_version=changed.version,
                        expected_digest=changed.digest,
                        actor="operator",
                        policy_id="unresolved",
                        sample=sample,
                    )
                self.assertEqual(conflict.exception.current_version, edited.version)
                self.assertEqual(
                    repository.get_classification_preview(edited.revision_id).document(), preserved
                )

    def test_authenticated_api_rejections_and_success_share_service(self) -> None:
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
                    f"/api/v1/configuration/revisions/{draft.revision_id}"
                    "/objects/classificationPolicies"
                )
                invalid_values = []
                for label in (
                    "condition",
                    "result",
                    "absolute",
                    "traversal",
                    "duplicate",
                    "missing",
                    "oversized",
                    "non-object",
                    "empty",
                ):
                    candidate = policy(f"invalid-{label}")
                    if label == "condition":
                        candidate["rules"][0]["conditions"]["unknown"] = []
                    elif label == "result":
                        candidate["rules"][0]["result"]["unknown"] = "x"
                    elif label == "absolute":
                        candidate["rules"][0]["result"]["path"] = "/unsafe"
                    elif label == "traversal":
                        candidate["rules"][0]["result"]["path"] = [".."]
                    elif label == "duplicate":
                        candidate["rules"].append(copy.deepcopy(candidate["rules"][0]))
                    elif label == "missing":
                        candidate["rules"][0]["result"]["mediaLibraryId"] = ""
                    elif label == "oversized":
                        candidate["rules"][0]["result"]["mediaLibraryId"] = "x" * 65
                    elif label == "non-object":
                        candidate["rules"] = ["invalid"]
                    else:
                        candidate["rules"] = []
                    invalid_values.append(candidate)
                for candidate in invalid_values:
                    status, response = request(
                        api,
                        collection,
                        method="POST",
                        body={"expectedVersion": draft.version, "object": candidate},
                    )
                    self.assertEqual(status, 400)
                    self.assertEqual(response["error"]["code"], "invalid_request")
                    self.assertLessEqual(len(response["error"]["message"]), 500)
                    self.assertEqual(managed.require(draft.revision_id).version, draft.version)
                    self.assertIsNone(repository.get_classification_preview(draft.revision_id))
                status, created = request(
                    api,
                    collection,
                    method="POST",
                    body={"expectedVersion": draft.version, "object": policy()},
                )
                self.assertEqual(status, 200)
                status, evidence = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/classification-preview",
                    method="POST",
                    body={
                        "expectedVersion": created["version"],
                        "expectedDigest": created["digest"],
                        "policyId": "managed",
                        "sample": {"title": "Example", "mediaType": "movie", "genres": ["Action"]},
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(evidence["result"]["relativePath"], "Action")
                stored = repository.get_classification_preview(draft.revision_id).document()
                status, stale = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/classification-preview",
                    method="POST",
                    body={
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                        "policyId": "managed",
                        "sample": {"title": "Example", "mediaType": "movie"},
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(stale["error"]["code"], "configuration_version_conflict")
                self.assertEqual(stale["error"]["details"]["currentVersion"], created["version"])
                self.assertEqual(stale["error"]["details"]["currentDigest"], created["digest"])
                self.assertEqual(
                    repository.get_classification_preview(draft.revision_id).document(), stored
                )

    def test_optional_section_and_schema_six_upgrade_preserve_naming_evidence(self) -> None:
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
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "UPDATE schema_version SET version=6 WHERE component='configuration_management'"
                )
            with SQLiteConfigurationRepository(database) as repository:
                self.assertEqual(
                    repository.get_naming_preview(draft.revision_id).document(), naming.document()
                )
                with sqlite3.connect(database) as connection:
                    marker = connection.execute(
                        "SELECT version FROM schema_version "
                        "WHERE component='configuration_management'"
                    ).fetchone()[0]
                self.assertEqual(marker, CONFIGURATION_SCHEMA_VERSION)
                self.assertEqual(RUNTIME_SCHEMA_VERSION, 29)

                optional = copy.deepcopy(document)
                optional.pop("classificationPolicies")
                optional_draft = ManagedConfigurationService(repository).import_draft(
                    optional, actor="operator"
                )
                detail = ConfigurationObjectService(
                    ManagedConfigurationService(repository)
                ).revision_detail(optional_draft.revision_id)
                self.assertEqual(detail["objects"]["classificationPolicies"], [])
                self.assertNotIn("classification_policy:A", detail["references"])

    def test_active_revision_refuses_preview_without_writing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                validated = managed.validate(draft.revision_id, actor="operator")
                self.assertEqual(validated.status.value, "validated")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="operator",
                )
                with self.assertRaises(ConfigurationVersionConflict) as refused:
                    objects.classification_preview(
                        active.revision_id,
                        expected_version=active.version,
                        expected_digest=active.digest,
                        actor="operator",
                        policy_id="A",
                        sample={"title": "Example", "mediaType": "movie"},
                    )
                self.assertIn("Draft or Validated", str(refused.exception))
                self.assertIsNone(repository.get_classification_preview(active.revision_id))


if __name__ == "__main__":
    unittest.main()
