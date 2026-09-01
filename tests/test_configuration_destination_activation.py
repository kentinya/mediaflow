from __future__ import annotations

import copy
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
    ConfigurationSetupCheckStatus,
    ConfigurationStrategyTestStatus,
    DestinationPrecheckEvidence,
    LocalSetupCheckEvidence,
    RecognitionStrategyTestEvidence,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_configuration_management import (
    CONFIGURATION_SCHEMA_VERSION,
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION as RUNTIME_SCHEMA_VERSION
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document, request


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
    def _save_existing_gates(repository, revision) -> None:
        now = datetime.now(UTC)
        repository.save_local_setup_check(
            LocalSetupCheckEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationSetupCheckStatus.PASSED,
                now,
                "operator",
            )
        )
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
                self.assertIn("current Local destination precheck", str(caught.exception))
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
                    ConfigurationActivationConflict, "destination precheck is stale"
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

    def test_current_completed_outcomes_activate_and_non_local_is_not_applicable(self) -> None:
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
                    self._save_existing_gates(repository, revision)
                    objects.require_current_destination_precheck(revision)
                    activated = objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                    self.assertEqual(activated.status.value, "active")
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
                    ConfigurationActivationConflict, "successful Local setup check"
                ):
                    objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
                now = datetime.now(UTC)
                repository.save_local_setup_check(
                    LocalSetupCheckEvidence(
                        revision.revision_id,
                        revision.version,
                        revision.digest,
                        ConfigurationSetupCheckStatus.PASSED,
                        now,
                        "operator",
                    )
                )
                with self.assertRaisesRegex(
                    ConfigurationActivationConflict, "completed Recognition Strategy Test"
                ):
                    objects.activate_checked(
                        revision.revision_id,
                        expected_version=revision.version,
                        actor="operator",
                    )
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
                self._save_existing_gates(repository, revision)
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
                self.assertEqual(RUNTIME_SCHEMA_VERSION, 28)

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
                self.assertIn("current Local destination precheck", blocked["error"]["message"])
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
