from __future__ import annotations

import copy
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
from mediaflow.domain.naming import NamingError, NamingErrorCode
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request


class ManagedNamingPolicyJourneyTests(unittest.TestCase):
    @staticmethod
    def _document(root: Path) -> dict:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        return document

    def test_crud_reference_block_copy_and_exact_revision_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                detail = objects.revision_detail(draft.revision_id)
                self.assertEqual(len(detail["objects"]["namingPolicies"]), 2)
                references = detail["references"]["naming_policy:A"]
                self.assertGreaterEqual(references["total"], 1)
                self.assertTrue(
                    any(item["field"] == "namingPolicy" for item in references["items"])
                )
                with self.assertRaises(ConfigurationObjectReferenced):
                    objects.mutate(
                        draft.revision_id,
                        ConfigurationObjectKind.NAMING_POLICY,
                        object_id="A",
                        value=None,
                        expected_version=draft.version,
                        actor="operator",
                        delete=True,
                    )

                policy = copy.deepcopy(detail["objects"]["namingPolicies"][0])
                policy.update({"id": "A-copy", "name": "Movie naming copy"})
                copied = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.NAMING_POLICY,
                    object_id=None,
                    value=policy,
                    expected_version=draft.version,
                    actor="operator",
                )
                preview = objects.naming_preview(
                    copied.revision_id,
                    expected_version=copied.version,
                    expected_digest=copied.digest,
                    actor="operator",
                    policy_id="A-copy",
                    sample={
                        "title": "Mission: Impossible",
                        "mediaType": "movie",
                        "recognitionType": "C",
                        "provider": "tmdb",
                        "providerId": "954",
                        "year": 1996,
                        "extension": "mkv",
                    },
                )
                self.assertEqual(preview.status.value, "completed")
                self.assertEqual(preview.result["recognitionType"], "C")
                self.assertEqual(preview.result["appliedPolicyId"], "A-copy")
                self.assertEqual(
                    preview.result["directory"], "Mission - Impossible (1996) [tmdbid-954]"
                )
                self.assertEqual(preview.result["filename"], "Mission - Impossible (1996).mkv")
                self.assertIn(
                    "sanitized_character_or_whitespace", preview.result["sanitizationChanges"]
                )

                edited_policy = copy.deepcopy(policy)
                edited_policy["filenameTemplate"] = "{title} ({year}) [v2].{ext}"
                changed = objects.mutate(
                    copied.revision_id,
                    ConfigurationObjectKind.NAMING_POLICY,
                    object_id="A-copy",
                    value=edited_policy,
                    expected_version=copied.version,
                    actor="other-operator",
                )
                stale = objects.revision_detail(changed.revision_id)["namingPreview"]
                self.assertTrue(stale["stale"])
                self.assertEqual(stale["revisionVersion"], copied.version)
                with self.assertRaises(ConfigurationVersionConflict) as conflict:
                    objects.naming_preview(
                        changed.revision_id,
                        expected_version=copied.version,
                        expected_digest=copied.digest,
                        actor="operator",
                        policy_id="A-copy",
                        sample={"title": "Example", "mediaType": "movie"},
                    )
                self.assertEqual(conflict.exception.current_version, changed.version)
                deleted = objects.mutate(
                    changed.revision_id,
                    ConfigurationObjectKind.NAMING_POLICY,
                    object_id="A-copy",
                    value=None,
                    expected_version=changed.version,
                    actor="operator",
                    delete=True,
                )
                self.assertNotIn(
                    "A-copy", [item["id"] for item in deleted.document["namingPolicies"]]
                )

    def test_movie_single_multi_path_and_missing_strategies_use_existing_engine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                cases = (
                    (
                        "movie",
                        "A",
                        {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "provider": "tmdb",
                            "providerId": "603",
                            "extension": "mkv",
                        },
                        ("The Matrix (1999) [tmdbid-603]", "The Matrix (1999).mkv"),
                    ),
                    (
                        "single",
                        "B",
                        {
                            "title": "The Last of Us",
                            "mediaType": "tv",
                            "year": 2023,
                            "season": 1,
                            "episode": 3,
                            "episodeTitle": "Long, Long Time",
                            "extension": "mkv",
                        },
                        (
                            "The Last of Us (2023)/Season 01",
                            "The Last of Us - S01E03 - Long, Long Time.mkv",
                        ),
                    ),
                    (
                        "multi",
                        "B",
                        {
                            "title": "Show",
                            "mediaType": "tv",
                            "season": 1,
                            "episodes": [1, 2, 3],
                            "extension": "mkv",
                        },
                        ("Show/Season 01", "Show - S01E01-E03.mkv"),
                    ),
                    (
                        "path",
                        "B",
                        {"path": "/incoming/Show.S02E04.1080p.WEB-DL.mkv"},
                        ("Show/Season 02", "Show - S02E04.mkv"),
                    ),
                )
                for label, policy_id, sample, expected in cases:
                    with (
                        self.subTest(label=label),
                        patch(
                            "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                            side_effect=AssertionError("naming preview must not construct Storage"),
                        ),
                        patch(
                            "mediaflow.application.configuration_objects.MetadataProviderRegistry",
                            side_effect=AssertionError(
                                "naming preview must not construct Provider"
                            ),
                        ),
                    ):
                        evidence = objects.naming_preview(
                            draft.revision_id,
                            expected_version=draft.version,
                            expected_digest=draft.digest,
                            actor="operator",
                            policy_id=policy_id,
                            sample=sample,
                        )
                    self.assertEqual(evidence.status.value, "completed")
                    self.assertEqual(
                        (evidence.result["directory"], evidence.result["filename"]), expected
                    )
                    self.assertEqual(evidence.document()["sideEffects"], "none")

                error_policy = {
                    "id": "missing-error",
                    "name": "Missing fails",
                    "mediaTypeMode": "tv",
                    "seriesDirectoryTemplate": "{title}",
                    "seasonDirectoryTemplate": "Season {season:02}",
                    "episodeFilenameTemplate": "{title} - {episode_title}.{ext}",
                    "multiEpisodeFileTemplate": "{title} - {episodes}.{ext}",
                    "missingVariableStrategy": "error",
                }
                draft = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.NAMING_POLICY,
                    object_id=None,
                    value=error_policy,
                    expected_version=draft.version,
                    actor="operator",
                )
                failed = objects.naming_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="missing-error",
                    sample={
                        "title": "Show",
                        "mediaType": "tv",
                        "season": 1,
                        "episode": 2,
                        "extension": "mkv",
                    },
                )
                self.assertEqual(failed.status.value, "failed")
                self.assertEqual(failed.failure_category, "missing_variable")
                self.assertIn("correct", failed.next_action)

                for strategy in ("empty", "omit_token"):
                    candidate = copy.deepcopy(error_policy)
                    candidate.update(
                        {"id": f"missing-{strategy}", "missingVariableStrategy": strategy}
                    )
                    draft = objects.mutate(
                        draft.revision_id,
                        ConfigurationObjectKind.NAMING_POLICY,
                        object_id=None,
                        value=candidate,
                        expected_version=draft.version,
                        actor="operator",
                    )
                    evidence = objects.naming_preview(
                        draft.revision_id,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="operator",
                        policy_id=candidate["id"],
                        sample={
                            "title": "Show",
                            "mediaType": "tv",
                            "season": 1,
                            "episode": 2,
                            "extension": "mkv",
                        },
                    )
                    self.assertEqual(evidence.status.value, "completed")
                    self.assertEqual(
                        evidence.result["missingVariableDecisions"][0]["decision"], strategy
                    )

    def test_invalid_templates_are_rejected_without_changing_draft(self) -> None:
        invalid = (
            ("unknown", "{unknown}", NamingErrorCode.UNKNOWN_VARIABLE),
            ("separator", "../{title}", NamingErrorCode.UNSAFE_PATH),
            ("empty", "", NamingErrorCode.INVALID_TEMPLATE),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(self._document(root), actor="operator")
                original_document = copy.deepcopy(draft.document)

                for label, template, expected_code in invalid:
                    with self.subTest(label=label), self.assertRaises(NamingError) as caught:
                        objects.mutate(
                            draft.revision_id,
                            ConfigurationObjectKind.NAMING_POLICY,
                            object_id=None,
                            value={
                                "id": f"bad-{label}",
                                "name": f"Bad {label}",
                                "directoryTemplate": template,
                            },
                            expected_version=draft.version,
                            actor="operator",
                        )
                    self.assertEqual(caught.exception.code, expected_code)
                    self.assertGreater(len(str(caught.exception)), 0)
                    self.assertLessEqual(len(str(caught.exception)), 500)
                    unchanged = managed.require(draft.revision_id)
                    self.assertEqual(unchanged.version, draft.version)
                    self.assertEqual(unchanged.digest, draft.digest)
                    self.assertEqual(unchanged.document, original_document)
                    self.assertIsNone(repository.get_naming_preview(draft.revision_id))

                corrected = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.NAMING_POLICY,
                    object_id=None,
                    value={
                        "id": "corrected-movie",
                        "name": "Corrected movie",
                        "mediaTypeMode": "movie",
                        "directoryTemplate": "{title} ({year})",
                        "filenameTemplate": "{title} ({year}).{ext}",
                    },
                    expected_version=draft.version,
                    actor="operator",
                )
                evidence = objects.naming_preview(
                    corrected.revision_id,
                    expected_version=corrected.version,
                    expected_digest=corrected.digest,
                    actor="operator",
                    policy_id="corrected-movie",
                    sample={
                        "title": "The Matrix",
                        "mediaType": "movie",
                        "year": 1999,
                        "extension": "mkv",
                    },
                )
                self.assertEqual(evidence.status.value, "completed")
                self.assertEqual(evidence.revision_version, corrected.version)
                self.assertEqual(evidence.revision_digest, corrected.digest)
                self.assertEqual(evidence.result["directory"], "The Matrix (1999)")
                self.assertEqual(evidence.result["filename"], "The Matrix (1999).mkv")

    def test_render_failures_are_persisted_with_distinct_recovery_categories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(repository)
                objects = ConfigurationObjectService(managed)
                cases = (
                    ("unknown_variable", {"directoryTemplate": "{unknown}"}),
                    ("unsafe_path", {"directoryTemplate": "../{title}"}),
                    ("invalid_template", {"directoryTemplate": ""}),
                    ("component_too_long", {"directoryTemplate": "x" * 4097}),
                    (
                        "empty_component",
                        {
                            "directoryTemplate": "{episode_title}",
                            "missingVariableStrategy": "empty",
                        },
                    ),
                )
                for expected, changes in cases:
                    with self.subTest(category=expected):
                        document = self._document(root)
                        document["namingPolicies"][0].update(changes)
                        draft = managed.import_draft(document, actor="operator")
                        evidence = objects.naming_preview(
                            draft.revision_id,
                            expected_version=draft.version,
                            expected_digest=draft.digest,
                            actor="operator",
                            policy_id="A",
                            sample={
                                "title": "Example",
                                "mediaType": "movie",
                                "year": 2024,
                                "extension": "mkv",
                            },
                        )
                        self.assertEqual(evidence.status.value, "failed")
                        self.assertEqual(evidence.failure_category, expected)
                        self.assertEqual(evidence.document()["sideEffects"], "none")
                        self.assertTrue(evidence.document()["retrySafe"])
                        self.assertIn("correct", evidence.next_action)

                document = self._document(root)
                document["namingPolicies"][0]["maxComponentLength"] = 40
                draft = managed.import_draft(document, actor="operator")
                truncated = objects.naming_preview(
                    draft.revision_id,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="operator",
                    policy_id="A",
                    sample={
                        "title": "A very long Unicode 电影 title " * 10,
                        "mediaType": "movie",
                        "year": 2024,
                        "providerId": "123",
                        "extension": "mkv",
                    },
                )
                self.assertEqual(truncated.status.value, "completed")
                self.assertIn("component_truncated", truncated.result["warnings"])
                self.assertIn("component_truncated", truncated.result["sanitizationChanges"])

    def test_authenticated_api_and_web_surface_share_the_application_service(self) -> None:
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
                    f"/api/v1/configuration/revisions/{draft.revision_id}/objects/namingPolicies"
                )
                original_document = copy.deepcopy(draft.document)
                for label, template in (
                    ("unknown", "{unknown}"),
                    ("separator", "../{title}"),
                    ("empty", ""),
                ):
                    with self.subTest(api_invalid=label):
                        status, invalid_response = request(
                            api,
                            collection,
                            method="POST",
                            body={
                                "expectedVersion": draft.version,
                                "object": {
                                    "id": f"invalid-{label}",
                                    "name": f"Invalid {label}",
                                    "directoryTemplate": template,
                                },
                            },
                        )
                        self.assertEqual(status, 400)
                        self.assertEqual(invalid_response["error"]["code"], "invalid_request")
                        self.assertGreater(len(invalid_response["error"]["message"]), 0)
                        self.assertLessEqual(len(invalid_response["error"]["message"]), 500)
                        unchanged = managed.require(draft.revision_id)
                        self.assertEqual(unchanged.version, draft.version)
                        self.assertEqual(unchanged.digest, draft.digest)
                        self.assertEqual(unchanged.document, original_document)
                        self.assertIsNone(repository.get_naming_preview(draft.revision_id))
                status, created = request(
                    api,
                    collection,
                    method="POST",
                    body={
                        "expectedVersion": draft.version,
                        "object": {
                            "id": "managed-movie",
                            "name": "Managed movie",
                            "mediaTypeMode": "movie",
                            "directoryTemplate": "{title} ({year})",
                            "filenameTemplate": "{title} ({year}).{ext}",
                            "missingVariableStrategy": "omit_token",
                            "enabled": True,
                        },
                    },
                )
                self.assertEqual(status, 200)
                status, evidence = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/naming-preview",
                    method="POST",
                    body={
                        "expectedVersion": created["version"],
                        "expectedDigest": created["digest"],
                        "policyId": "managed-movie",
                        "sample": {
                            "title": "The Matrix",
                            "mediaType": "movie",
                            "year": 1999,
                            "extension": "mkv",
                        },
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(evidence["status"], "completed")
                status, detail = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/objects",
                )
                self.assertEqual(status, 200)
                self.assertFalse(detail["namingPreview"]["stale"])
                self.assertEqual(
                    detail["namingPreview"]["result"]["filename"], "The Matrix (1999).mkv"
                )


if __name__ == "__main__":
    unittest.main()
