from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.automation import (
    AutomationJobService,
    AutomationWorker,
    IntervalScheduler,
)
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.application.unattended_execution import UnattendedExecutionGrantService
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJobStatus,
    IntervalSchedule,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.automation_task_definition_preview import (
    AutomationTaskDefinitionPreview,
    AutomationTaskDefinitionPreviewStatus,
)
from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationObjectKind,
    ConfigurationVersionConflict,
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaIdentity,
    MediaType,
    ProviderCapabilities,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.final_cli import (
    _configuration,
    _ConfiguredPermissionAuthority,
    _PersistedPreviewReader,
    _run_queued_workflow,
    _task_snapshot_identity,
    final_main,
)
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def request(
    api,
    path,
    *,
    method="GET",
    body=b"",
    token="admin-token",
    headers=None,
    query="",
):
    statuses = []
    environment = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
    }
    environment.update(headers or {})
    payload = b"".join(api(environment, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


def request_raw(api, path, *, method="GET", token="admin-token"):
    statuses = []
    headers = []
    environment = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
    }

    def start_response(status, response_headers):
        statuses.append(status)
        headers.extend(response_headers)

    payload = b"".join(api(environment, start_response))
    return int(statuses[0].split()[0]), dict(headers), payload


def activate_document(service, document, *, actor="tester"):
    draft = service.import_draft(document, actor=actor)
    validated = service.validate(draft.revision_id, actor=actor)
    return service.activate(
        validated.revision_id,
        expected_version=validated.version,
        actor=actor,
    )


class ManagedConfigurationSnapshotTests(unittest.TestCase):
    def test_draft_validate_activate_and_edit_invalidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = example_document()
            document["persistence"]["databasePath"] = str(Path(directory) / "runtime.sqlite3")
            with SQLiteConfigurationRepository(
                Path(directory) / "configuration.sqlite3"
            ) as repository:
                service = ManagedConfigurationService(repository)
                draft = service.import_draft(document, actor="tester")
                self.assertEqual(draft.status, ManagedConfigurationStatus.DRAFT)
                validated = service.validate(draft.revision_id, actor="tester")
                self.assertEqual(validated.status, ManagedConfigurationStatus.VALIDATED)
                edited = dict(document)
                edited["historyPath"] = str(Path(directory) / "history.jsonl")
                changed = service.edit_draft(
                    draft.revision_id,
                    edited,
                    expected_version=validated.version,
                    actor="tester",
                )
                self.assertEqual(changed.status, ManagedConfigurationStatus.DRAFT)
                self.assertEqual(changed.version, validated.version + 1)
                self.assertIsNone(changed.validated_at)
                with self.assertRaises(ConfigurationActivationConflict):
                    service.activate(
                        changed.revision_id,
                        expected_version=changed.version,
                        actor="tester",
                    )

    def test_activation_replaces_active_atomically_and_stale_activation_preserves_old(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = example_document()
            document["persistence"]["databasePath"] = str(Path(directory) / "runtime.sqlite3")
            with SQLiteConfigurationRepository(
                Path(directory) / "configuration.sqlite3"
            ) as repository:
                service = ManagedConfigurationService(repository)
                first = service.validate(
                    service.import_draft(document, actor="tester").revision_id, actor="tester"
                )
                active = service.activate(
                    first.revision_id, expected_version=first.version, actor="tester"
                )
                second_doc = json.loads(json.dumps(document))
                second_doc["historyPath"] = str(Path(directory) / "other-history.jsonl")
                second = service.validate(
                    service.import_draft(second_doc, actor="tester").revision_id,
                    actor="tester",
                )
                with self.assertRaises(ConfigurationActivationConflict):
                    service.activate(
                        second.revision_id, expected_version=second.version + 1, actor="tester"
                    )
                self.assertEqual(repository.get_active_revision().revision_id, active.revision_id)
                current = service.activate(
                    second.revision_id, expected_version=second.version, actor="tester"
                )
                self.assertEqual(current.status, ManagedConfigurationStatus.ACTIVE)
                self.assertEqual(repository.get_active_revision().revision_id, second.revision_id)
                self.assertEqual(len(repository.list_revision_audits(second.revision_id)), 3)

    def test_activation_rejects_a_validated_draft_created_before_new_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = example_document()
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            second_document = json.loads(json.dumps(document))
            second_document["historyPath"] = str(root / "second-history.jsonl")
            with SQLiteConfigurationRepository(root / "runtime.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                first_draft = service.import_draft(document, actor="tester")
                second_draft = service.import_draft(second_document, actor="tester")
                first = service.validate(first_draft.revision_id, actor="tester")
                service.activate(first.revision_id, expected_version=first.version, actor="tester")
                second = service.validate(second_draft.revision_id, actor="tester")
                with self.assertRaises(ConfigurationActivationConflict):
                    service.activate(
                        second.revision_id,
                        expected_version=second.version,
                        actor="tester",
                    )
                self.assertEqual(repository.get_active_revision().revision_id, first.revision_id)

    def test_activation_persistence_failure_rolls_back_to_previous_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = example_document()
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            with SQLiteConfigurationRepository(root / "runtime.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                first = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                active = service.activate(
                    first.revision_id, expected_version=first.version, actor="tester"
                )
                second_document = json.loads(json.dumps(document))
                second_document["historyPath"] = str(root / "second-history.jsonl")
                second = service.validate(
                    service.import_draft(second_document, actor="tester").revision_id,
                    actor="tester",
                )
                with patch.object(
                    repository,
                    "_insert_audit",
                    side_effect=RuntimeError("simulated persistence failure"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "simulated persistence failure"):
                        service.activate(
                            second.revision_id,
                            expected_version=second.version,
                            actor="tester",
                        )
                self.assertEqual(repository.get_active_revision().revision_id, active.revision_id)
                self.assertEqual(
                    repository.get_revision(second.revision_id).status,
                    ManagedConfigurationStatus.VALIDATED,
                )

    def test_jobs_pin_the_snapshot_at_submission_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = example_document()
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            with (
                SQLiteConfigurationRepository(root / "runtime.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(repository)
                first = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                first_active = service.activate(
                    first.revision_id,
                    expected_version=first.version,
                    actor="tester",
                )
                old_job = AutomationJobService(
                    runtime_repository,
                    configuration_snapshot_id=first_active.revision_id,
                    configuration_snapshot_digest=first_active.digest,
                ).submit("preview")
                second_document = json.loads(json.dumps(document))
                second_document["historyPath"] = str(root / "second-history.jsonl")
                second = service.validate(
                    service.import_draft(second_document, actor="tester").revision_id,
                    actor="tester",
                )
                second_active = service.activate(
                    second.revision_id,
                    expected_version=second.version,
                    actor="tester",
                )
                new_job = AutomationJobService(
                    runtime_repository,
                    configuration_snapshot_id=second_active.revision_id,
                    configuration_snapshot_digest=second_active.digest,
                ).submit("preview")
                self.assertEqual(old_job.configuration_snapshot_id, first_active.revision_id)
                self.assertEqual(new_job.configuration_snapshot_id, second_active.revision_id)

    def test_api_activation_atomically_refreshes_admission_and_snapshot_pin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            first_document = example_document()
            first_document["persistence"]["databasePath"] = str(runtime)
            first_document["automation"]["maximumActiveJobs"] = 1
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(runtime),
                )
                first = activate_document(service, first_document)
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    maximum_active_jobs=1,
                    configuration_service=service,
                    configuration_snapshot_id=first.revision_id,
                    configuration_snapshot_digest=first.digest,
                    bootstrap_document=first_document,
                )

                expanded = json.loads(json.dumps(first_document))
                expanded["historyPath"] = str(root / "expanded.jsonl")
                expanded["automation"]["maximumActiveJobs"] = 2
                second = activate_document(service, expanded)
                accepted = [
                    request(
                        api,
                        "/api/v1/jobs",
                        method="POST",
                        body=json.dumps({"command": "preview"}).encode(),
                    )
                    for _ in range(2)
                ]
                self.assertEqual([item[0] for item in accepted], [202, 202])
                self.assertTrue(
                    all(
                        item[1]["configuration_snapshot_id"] == second.revision_id
                        for item in accepted
                    )
                )
                for _, item in accepted:
                    task_repository.request_job_cancellation(item["job_id"], datetime.now(UTC))

                restricted = json.loads(json.dumps(expanded))
                restricted["historyPath"] = str(root / "restricted.jsonl")
                restricted["automation"]["maximumActiveJobs"] = 1
                third = activate_document(service, restricted)
                first_under_third = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                rejected = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.assertEqual(first_under_third[0], 202)
                self.assertEqual(
                    first_under_third[1]["configuration_snapshot_id"], third.revision_id
                )
                self.assertEqual(rejected[0], 409)
                self.assertEqual(rejected[1]["error"]["code"], "queue_full")

    def test_api_activation_applies_remote_execute_gate_before_token_consumption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            document["api"]["remoteExecution"] = {
                "enabled": True,
                "maximumTtlSeconds": 120,
            }
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(runtime),
                )
                first = activate_document(service, document)
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    remote_execution_enabled=True,
                    remote_execution_maximum_ttl_seconds=120,
                    configuration_service=service,
                    configuration_snapshot_id=first.revision_id,
                    configuration_snapshot_digest=first.digest,
                    bootstrap_document=document,
                )
                issued = ExecutionAuthorizationService(task_repository).issue(
                    ttl_seconds=60,
                    max_items=1,
                    actor="tester",
                )

                disabled = json.loads(json.dumps(document))
                disabled["historyPath"] = str(root / "disabled.jsonl")
                disabled["api"]["remoteExecution"]["enabled"] = False
                activate_document(service, disabled)
                denied = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "organize", "execute": True, "limit": 1}).encode(),
                    headers={"HTTP_X_MEDIAFLOW_EXECUTION_TOKEN": issued.token},
                )
                self.assertEqual(denied[0], 400)
                self.assertIn("disabled", denied[1]["error"]["message"])
                self.assertEqual(
                    task_repository.get_execution_authorization(
                        issued.authorization.authorization_id
                    ).status.value,
                    "active",
                )
                self.assertEqual(task_repository.list_jobs(), ())

                enabled = json.loads(json.dumps(disabled))
                enabled["historyPath"] = str(root / "enabled.jsonl")
                enabled["api"]["remoteExecution"]["enabled"] = True
                current = activate_document(service, enabled)
                accepted = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "organize", "execute": True, "limit": 1}).encode(),
                    headers={"HTTP_X_MEDIAFLOW_EXECUTION_TOKEN": issued.token},
                )
                self.assertEqual(accepted[0], 202, accepted[1])
                self.assertTrue(accepted[1]["execute_authorized"])
                self.assertEqual(accepted[1]["configuration_snapshot_id"], current.revision_id)
                self.assertEqual(accepted[1]["configuration_snapshot_digest"], current.digest)

    def test_concurrent_activation_and_submission_never_mix_pin_and_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            document["automation"]["maximumActiveJobs"] = 2
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(runtime),
                )
                first = activate_document(service, document)
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    maximum_active_jobs=2,
                    configuration_service=service,
                    configuration_snapshot_id=first.revision_id,
                    configuration_snapshot_digest=first.digest,
                    bootstrap_document=document,
                )
                existing = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.assertEqual(existing[0], 202)
                restricted = json.loads(json.dumps(document))
                restricted["historyPath"] = str(root / "restricted.jsonl")
                restricted["automation"]["maximumActiveJobs"] = 1
                draft = service.import_draft(restricted, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                barrier = threading.Barrier(2)
                outcomes = []
                activation_errors = []

                def activate() -> None:
                    try:
                        barrier.wait()
                        service.activate(
                            validated.revision_id,
                            expected_version=validated.version,
                            actor="activator",
                        )
                    except Exception as error:  # pragma: no cover - asserted below
                        activation_errors.append(error)

                def submit() -> None:
                    barrier.wait()
                    outcomes.append(
                        request(
                            api,
                            "/api/v1/jobs",
                            method="POST",
                            body=json.dumps({"command": "preview"}).encode(),
                        )
                    )

                threads = [threading.Thread(target=activate), threading.Thread(target=submit)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                self.assertEqual(activation_errors, [])
                self.assertEqual(
                    configuration_repository.get_active_revision().revision_id,
                    validated.revision_id,
                )
                self.assertEqual(len(outcomes), 1)
                status, value = outcomes[0]
                self.assertIn(status, {202, 409})
                if status == 202:
                    self.assertEqual(value["configuration_snapshot_id"], first.revision_id)
                else:
                    self.assertEqual(value["error"]["code"], "queue_full")

    def test_concurrent_imports_have_unique_sequences_and_atomic_audits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            barrier = threading.Barrier(6)
            revisions = []
            errors = []

            def import_one(index: int) -> None:
                try:
                    document = example_document()
                    document["persistence"]["databasePath"] = str(database)
                    document["historyPath"] = str(Path(directory) / f"history-{index}.jsonl")
                    with SQLiteConfigurationRepository(database) as repository:
                        barrier.wait()
                        revision = ManagedConfigurationService(repository).import_draft(
                            document,
                            actor=f"importer-{index}",
                        )
                        revisions.append(revision)
                except Exception as error:  # pragma: no cover - asserted below
                    errors.append(error)

            threads = [threading.Thread(target=import_one, args=(index,)) for index in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(revisions), 6)
            sequences = sorted(item.revision_sequence for item in revisions)
            self.assertEqual(sequences, list(range(1, 7)))
            with SQLiteConfigurationRepository(database) as repository:
                for revision in revisions:
                    audits = repository.list_revision_audits(revision.revision_id)
                    self.assertEqual(len(audits), 1)
                    self.assertEqual(audits[0].action, "draft_import")

    def test_concurrent_edits_have_one_winner_and_one_atomic_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(database)
            with SQLiteConfigurationRepository(database) as repository:
                draft = ManagedConfigurationService(repository).import_draft(
                    document, actor="creator"
                )
            barrier = threading.Barrier(2)
            successes = []
            conflicts = []

            def edit(name: str) -> None:
                changed = json.loads(json.dumps(document))
                changed["historyPath"] = str(Path(directory) / f"{name}.jsonl")
                try:
                    with SQLiteConfigurationRepository(database) as repository:
                        barrier.wait()
                        successes.append(
                            ManagedConfigurationService(repository).edit_draft(
                                draft.revision_id,
                                changed,
                                expected_version=draft.version,
                                actor=name,
                            )
                        )
                except ConfigurationVersionConflict as error:
                    conflicts.append(error)

            threads = [threading.Thread(target=edit, args=(name,)) for name in ("one", "two")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(successes), 1)
            self.assertEqual(len(conflicts), 1)
            with SQLiteConfigurationRepository(database) as repository:
                stored = repository.get_revision(draft.revision_id)
                self.assertIsNotNone(stored)
                self.assertEqual(stored.version, 2)
                self.assertEqual(stored.digest, successes[0].digest)
                self.assertEqual(stored.document, successes[0].document)
                audits = repository.list_revision_audits(draft.revision_id)
                self.assertEqual([item.action for item in audits], ["draft_edit", "draft_import"])

    def test_concurrent_activations_have_exactly_one_active_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(database)
            with SQLiteConfigurationRepository(database) as repository:
                service = ManagedConfigurationService(repository)
                first = activate_document(service, document)
                candidates = []
                for name in ("one", "two"):
                    changed = json.loads(json.dumps(document))
                    changed["historyPath"] = str(Path(directory) / f"{name}.jsonl")
                    draft = service.import_draft(changed, actor=name)
                    candidates.append(service.validate(draft.revision_id, actor=name))
            barrier = threading.Barrier(2)
            winners = []
            conflicts = []

            def activate(candidate) -> None:
                try:
                    with SQLiteConfigurationRepository(database) as repository:
                        barrier.wait()
                        winners.append(
                            ManagedConfigurationService(repository).activate(
                                candidate.revision_id,
                                expected_version=candidate.version,
                                actor=f"activate-{candidate.revision_id}",
                            )
                        )
                except ConfigurationActivationConflict as error:
                    conflicts.append(error)

            threads = [threading.Thread(target=activate, args=(item,)) for item in candidates]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(winners), 1)
            self.assertEqual(len(conflicts), 1)
            with SQLiteConfigurationRepository(database) as repository:
                active = repository.get_active_revision()
                self.assertIsNotNone(active)
                self.assertEqual(active.revision_id, winners[0].revision_id)
                self.assertNotEqual(active.revision_id, first.revision_id)
                loser = next(item for item in candidates if item.revision_id != active.revision_id)
                stored_loser = repository.get_revision(loser.revision_id)
                self.assertIsNotNone(stored_loser)
                self.assertEqual(stored_loser.status, ManagedConfigurationStatus.VALIDATED)
                self.assertEqual(
                    [item.action for item in repository.list_revision_audits(active.revision_id)],
                    ["activate", "validate", "draft_import"],
                )
                self.assertEqual(
                    [item.action for item in repository.list_revision_audits(loser.revision_id)],
                    ["validate", "draft_import"],
                )

    def test_invalid_and_secret_documents_never_become_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteConfigurationRepository(
                Path(directory) / "configuration.sqlite3"
            ) as repository:
                service = ManagedConfigurationService(repository)
                invalid = example_document()
                invalid["recognitionTypePolicies"][0]["metadataPolicy"] = "missing"
                draft = service.import_draft(invalid, actor="tester")
                result = service.validate(draft.revision_id, actor="tester")
                self.assertEqual(result.status, ManagedConfigurationStatus.DRAFT)
                self.assertTrue(result.validation_errors)
                self.assertIsNone(repository.get_active_revision())
                with self.assertRaises(ValueError):
                    service.import_draft({"storages": [{"password": "plaintext"}]}, actor="tester")

    def test_lifecycle_audit_evidence_is_bounded_and_contains_no_environment_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(database)
            document["operatorNotes"] = "x" * 500_000
            secret = "literal-secret-that-must-not-appear"
            with (
                patch.dict("os.environ", {"TMDB_ACCESS_TOKEN": secret}, clear=False),
                SQLiteConfigurationRepository(database) as repository,
            ):
                revision = ManagedConfigurationService(repository).import_draft(
                    document,
                    actor="bounded-auditor",
                )
                audits = repository.list_revision_audits(revision.revision_id)
                self.assertEqual(len(audits), 1)
                encoded = json.dumps(
                    {
                        "before": audits[0].safe_before(),
                        "after": audits[0].safe_after(),
                    },
                    sort_keys=True,
                ).encode()
                self.assertLessEqual(len(encoded), 128 * 1024)
                self.assertNotIn(secret.encode(), encoded)

    def test_configuration_lifecycle_and_api_refresh_construct_no_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = example_document()
            runtime = Path(directory) / "runtime.sqlite3"
            document["persistence"]["databasePath"] = str(runtime)
            with (
                SQLiteConfigurationRepository(runtime) as repository,
                SQLiteTaskRepository(runtime) as task_repository,
                patch(
                    "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("configuration lifecycle constructed Storage"),
                ),
                patch(
                    "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                    side_effect=AssertionError("configuration lifecycle constructed Provider"),
                ),
            ):
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                draft = service.import_draft(document, actor="tester")
                changed = json.loads(json.dumps(document))
                changed["historyPath"] = str(Path(directory) / "changed.jsonl")
                edited = service.edit_draft(
                    draft.revision_id,
                    changed,
                    expected_version=draft.version,
                    actor="tester",
                )
                result = service.validate(edited.revision_id, actor="tester")
                self.assertTrue(service.detail(result.revision_id)["diff"])
                self.assertEqual(result.status, ManagedConfigurationStatus.VALIDATED)
                active = service.activate(
                    result.revision_id,
                    expected_version=result.version,
                    actor="tester",
                )
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, value = request(api, "/api/v1/system/status")
                self.assertEqual(status, 200, value)
                self.assertEqual(
                    value["system"]["configuration_snapshot_id"],
                    active.revision_id,
                )

    def test_missing_active_revision_fails_closed_after_managed_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            config = root / "bootstrap.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(repository)
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                service.activate(
                    validated.revision_id, expected_version=validated.version, actor="tester"
                )
            connection = sqlite3.connect(runtime)
            try:
                connection.execute(
                    "DELETE FROM managed_configuration_revisions WHERE status='active'"
                )
                connection.commit()
            finally:
                connection.close()
            with self.assertRaises(RuntimeSnapshotUnavailable):
                _configuration(str(config))

    def test_api_configuration_lifecycle_and_rbac(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = example_document()
            document["persistence"]["databasePath"] = str(Path(directory) / "runtime.sqlite3")
            with (
                SQLiteConfigurationRepository(
                    Path(directory) / "runtime.sqlite3"
                ) as configuration_repository,
                SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(configuration_repository)
                admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                viewer = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(admin, viewer),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, body = request(api, "/api/v1/configuration", token="viewer-token")
                self.assertEqual(status, 200)
                self.assertEqual(body["authority"], "JSON_BOOTSTRAP")
                payload = json.dumps({"source": "current"}).encode()
                status, draft_body = request(
                    api, "/api/v1/configuration/drafts", method="POST", body=payload
                )
                self.assertEqual(status, 201)
                revision_id = draft_body["revisionId"]
                status, _ = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/validate",
                    method="POST",
                    body=b"{}",
                )
                self.assertEqual(status, 200)
                status, active_body = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/activate",
                    method="POST",
                    body=json.dumps({"expectedVersion": 1}).encode(),
                )
                self.assertEqual(status, 200)
                self.assertEqual(active_body["status"], "active")
                job_status, job_body = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.assertEqual(job_status, 202)
                self.assertEqual(job_body["configuration_snapshot_id"], revision_id)
                status, _ = request(
                    api,
                    "/api/v1/configuration/drafts",
                    method="POST",
                    body=payload,
                    token="viewer-token",
                )
                self.assertEqual(status, 403)

    def test_api_draft_correction_validate_activate_and_job_pin_journey(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = example_document()
            document["persistence"]["databasePath"] = str(Path(directory) / "runtime.sqlite3")
            invalid = json.loads(json.dumps(document))
            invalid["recognitionTypePolicies"][0]["metadataPolicy"] = "missing"
            with (
                SQLiteConfigurationRepository(
                    Path(directory) / "runtime.sqlite3"
                ) as configuration_repository,
                SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=document["persistence"]["databasePath"],
                )
                admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(admin,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, draft = request(
                    api,
                    "/api/v1/configuration/drafts",
                    method="POST",
                    body=json.dumps({"document": invalid}).encode(),
                )
                self.assertEqual(status, 201)
                revision_id = draft["revisionId"]
                status, validated = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/validate",
                    method="POST",
                    body=b"{}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(validated["status"], "draft")
                status, edited = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}",
                    method="PUT",
                    body=json.dumps(
                        {"document": document, "expectedVersion": validated["version"]}
                    ).encode(),
                )
                self.assertEqual(status, 200)
                status, validated = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/validate",
                    method="POST",
                    body=b"{}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(validated["status"], "validated")
                status, active = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/activate",
                    method="POST",
                    body=json.dumps({"expectedVersion": validated["version"]}).encode(),
                )
                self.assertEqual(status, 200)
                self.assertEqual(active["status"], "active")
                status, job = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.assertEqual(status, 202)
                self.assertEqual(job["configuration_snapshot_id"], revision_id)
                self.assertEqual(job["configuration_snapshot_digest"], active["digest"])

    def test_runtime_locator_is_rejected_during_validation_and_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                invalid = json.loads(json.dumps(document))
                invalid["persistence"]["databasePath"] = str(root / "other.sqlite3")
                draft = service.import_draft(invalid, actor="tester")
                result = service.validate(draft.revision_id, actor="tester")
                self.assertEqual(result.status, ManagedConfigurationStatus.DRAFT)
                self.assertTrue(any("databasePath" in item for item in result.validation_errors))
                with self.assertRaises(ConfigurationActivationConflict):
                    service.activate(
                        result.revision_id,
                        expected_version=result.version,
                        actor="tester",
                    )
                self.assertIsNone(repository.get_active_revision())

    def test_tampered_validated_payload_cannot_be_activated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                validated = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                    (json.dumps({"tampered": True}), validated.revision_id),
                )
                repository._connection.commit()
                with self.assertRaises(ConfigurationActivationConflict):
                    service.activate(
                        validated.revision_id,
                        expected_version=validated.version,
                        actor="tester",
                    )
                self.assertIsNone(repository.get_active_revision())

    def test_import_validate_edit_audit_failures_roll_back_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = example_document()
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                with patch.object(repository, "_insert_audit", side_effect=RuntimeError("audit")):
                    with self.assertRaisesRegex(RuntimeError, "audit"):
                        service.import_draft(document, actor="tester")
                self.assertEqual(repository.list_revisions(), ())

                draft = service.import_draft(document, actor="tester")
                with patch.object(repository, "_insert_audit", side_effect=RuntimeError("audit")):
                    with self.assertRaisesRegex(RuntimeError, "audit"):
                        service.validate(draft.revision_id, actor="tester")
                self.assertEqual(
                    repository.get_revision(draft.revision_id).status,
                    ManagedConfigurationStatus.DRAFT,
                )

                validated = service.validate(draft.revision_id, actor="tester")
                with patch.object(repository, "_insert_audit", side_effect=RuntimeError("audit")):
                    with self.assertRaisesRegex(RuntimeError, "audit"):
                        service.edit_draft(
                            draft.revision_id,
                            {**document, "historyPath": str(root / "history.jsonl")},
                            expected_version=validated.version,
                            actor="tester",
                        )
                current = repository.get_revision(draft.revision_id)
                self.assertEqual(current.status, ManagedConfigurationStatus.VALIDATED)
                self.assertEqual(current.version, validated.version)

    def test_revision_sequence_is_stable_and_distinct_from_edit_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = example_document()
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                first = service.import_draft(document, actor="tester")
                second = service.import_draft(document, actor="tester")
                self.assertNotEqual(first.revision_sequence, second.revision_sequence)
                edited = service.edit_draft(
                    first.revision_id,
                    {**document, "historyPath": str(root / "history.jsonl")},
                    expected_version=first.version,
                    actor="tester",
                )
                self.assertEqual(edited.revision_sequence, first.revision_sequence)
                self.assertEqual(edited.version, first.version + 1)
                self.assertEqual(
                    len(
                        repository.list_audits(
                            ConfigurationObjectKind.SYSTEM_SETTINGS, first.revision_id
                        )
                    ),
                    2,
                )

    def test_missing_active_keeps_configuration_recovery_available_but_blocks_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                active = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                service.activate(
                    active.revision_id, expected_version=active.version, actor="tester"
                )
                repository._connection.execute(
                    "DELETE FROM managed_configuration_revisions WHERE status='active'"
                )
                repository._connection.commit()
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(runtime),
                )
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, body = request(api, "/api/v1/configuration")
                self.assertEqual(status, 200)
                self.assertEqual(body["health"], "UNAVAILABLE")
                replacement = json.loads(json.dumps(document))
                replacement["historyPath"] = str(root / "replacement.jsonl")
                status, draft = request(
                    api,
                    "/api/v1/configuration/drafts",
                    method="POST",
                    body=json.dumps({"document": replacement}).encode(),
                )
                self.assertEqual(status, 201)
                status, job = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.assertEqual(status, 503)
                self.assertEqual(job["error"]["code"], "configuration_unavailable")
                self.assertEqual(
                    job["error"]["details"]["durableState"], "managed_active_unavailable"
                )
                self.assertEqual(job["error"]["details"]["sideEffects"], "none")
                self.assertTrue(job["error"]["details"]["retrySafe"])
                self.assertEqual(draft["status"], "draft")

    def test_runtime_invalid_active_repeated_job_requests_remain_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                active = service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                broken = json.loads(json.dumps(document))
                broken["recognitionTypePolicies"][0]["metadataPolicy"] = "missing-policy"
                payload = json.dumps(
                    broken,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=?, digest=? "
                    "WHERE revision_id=?",
                    (payload, digest, active.revision_id),
                )
                repository._connection.commit()
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=str(runtime),
                    ),
                    bootstrap_document=document,
                )
                for _ in range(3):
                    status, body = request(
                        api,
                        "/api/v1/jobs",
                        method="POST",
                        body=json.dumps({"command": "preview"}).encode(),
                    )
                    self.assertEqual(status, 503)
                    self.assertEqual(body["error"]["code"], "configuration_unavailable")
                    self.assertEqual(body["error"]["details"]["revisionId"], active.revision_id)
                    self.assertEqual(body["error"]["details"]["digest"], digest)
                    self.assertEqual(
                        body["error"]["details"]["durableState"], "managed_active_unavailable"
                    )
                    self.assertEqual(body["error"]["details"]["sideEffects"], "none")
                    self.assertTrue(body["error"]["details"]["retrySafe"])
                self.assertEqual(task_repository.list_jobs(), ())
                self.assertEqual(
                    api._configuration_snapshot_id,
                    None,
                    "a rejected Active must not be cached as the API runtime identity",
                )

    def test_schema_unsupported_active_is_reported_and_stays_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                active = service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET schema_version=? "
                    "WHERE revision_id=?",
                    (999, active.revision_id),
                )
                repository._connection.commit()
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=str(runtime),
                    ),
                    bootstrap_document=document,
                )
                status, details = request(api, "/api/v1/configuration")
                self.assertEqual(status, 200)
                self.assertEqual(details["health"], "UNAVAILABLE")
                status, body = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.assertEqual(status, 503)
                self.assertEqual(body["error"]["details"]["reason"], "schema_unsupported")
                self.assertEqual(task_repository.list_jobs(), ())

    def test_digest_corrupt_active_is_reported_and_stays_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                active = service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                tampered = {**document, "historyPath": str(root / "tampered.jsonl")}
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                    (json.dumps(tampered), active.revision_id),
                )
                repository._connection.commit()
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=str(runtime),
                    ),
                    bootstrap_document=document,
                )
                status, details = request(api, "/api/v1/configuration")
                self.assertEqual(status, 200)
                self.assertEqual(details["health"], "UNAVAILABLE")
                status, body = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.assertEqual(status, 503)
                self.assertEqual(body["error"]["details"]["reason"], "digest_corrupt")
                self.assertEqual(task_repository.list_jobs(), ())

    def test_active_bootstrap_locator_change_is_runtime_invalid_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                active = service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                changed = json.loads(json.dumps(document))
                changed["persistence"]["databasePath"] = str(root / "other.sqlite3")
                payload = json.dumps(
                    changed,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=?, digest=? "
                    "WHERE revision_id=?",
                    (payload, digest, active.revision_id),
                )
                repository._connection.commit()
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=str(runtime),
                    ),
                    bootstrap_document=document,
                )
                status, body = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.assertEqual(status, 503)
                self.assertEqual(body["error"]["details"]["reason"], "runtime_invalid")
                self.assertEqual(task_repository.list_jobs(), ())

    def test_api_stale_draft_edit_returns_structured_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = example_document()
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            with (
                SQLiteConfigurationRepository(root / "runtime.sqlite3") as configuration_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=document["persistence"]["databasePath"],
                    ),
                    bootstrap_document=document,
                )
                status, draft = request(
                    api,
                    "/api/v1/configuration/drafts",
                    method="POST",
                    body=json.dumps({"document": document}).encode(),
                )
                self.assertEqual(status, 201)
                edit_document = {**document, "historyPath": str(root / "first-history.jsonl")}
                status, edited = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}",
                    method="PUT",
                    body=json.dumps(
                        {"document": edit_document, "expectedVersion": draft["version"]}
                    ).encode(),
                )
                self.assertEqual(status, 200)
                status, conflict = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}",
                    method="PUT",
                    body=json.dumps(
                        {
                            "document": {**document, "historyPath": str(root / "stale.jsonl")},
                            "expectedVersion": draft["version"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(conflict["error"]["code"], "configuration_version_conflict")
                self.assertEqual(conflict["error"]["details"]["revisionId"], draft["revisionId"])
                self.assertEqual(conflict["error"]["details"]["currentVersion"], edited["version"])
                self.assertEqual(conflict["error"]["details"]["durableState"], "draft_preserved")
                self.assertEqual(conflict["error"]["details"]["sideEffects"], "none")
                self.assertTrue(conflict["error"]["details"]["retrySafe"])
                self.assertIn("refresh", conflict["error"]["details"]["nextAction"])

    def test_scheduler_resolves_schedule_content_and_pin_from_one_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteTaskRepository(Path(directory) / "runtime.sqlite3")
            try:
                first_schedule = IntervalSchedule("first", AutomationCommand.SCAN, 60)
                second_schedule = IntervalSchedule("first", AutomationCommand.PREVIEW, 30)
                current = [
                    SchedulerConfigurationSnapshot(
                        "first-revision",
                        "first-digest",
                        (first_schedule,),
                        10,
                    )
                ]
                scheduler = IntervalScheduler(
                    repository,
                    (first_schedule,),
                    configuration_snapshot_resolver=lambda: current[0],
                )
                now = datetime.now(UTC)
                first = scheduler.tick(now)
                self.assertEqual(len(first), 1)
                self.assertEqual(first[0].schedule_id, "first")
                self.assertEqual(first[0].configuration_snapshot_id, "first-revision")

                current[0] = SchedulerConfigurationSnapshot(
                    "second-revision",
                    "second-digest",
                    (second_schedule,),
                    20,
                )
                second = scheduler.tick(now + timedelta(seconds=61))
                self.assertEqual(len(second), 1)
                self.assertEqual(second[0].schedule_id, "first")
                self.assertEqual(second[0].command, AutomationCommand.PREVIEW)
                self.assertEqual(second[0].configuration_snapshot_id, "second-revision")
                self.assertEqual(second[0].configuration_snapshot_digest, "second-digest")
            finally:
                repository.close()

    def test_api_views_and_job_pin_refresh_from_the_same_active_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(runtime),
                )
                first = activate_document(service, document)
                api = MediaFlowApi(
                    task_repository,
                    None,
                    tuple(),
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    configuration_snapshot_id=first.revision_id,
                    configuration_snapshot_digest=first.digest,
                    bootstrap_document=document,
                )
                changed = json.loads(json.dumps(document))
                changed["historyPath"] = str(root / "changed.jsonl")
                changed["automation"]["maximumActiveJobs"] = 7
                changed["automation"]["staleJobAgeSeconds"] = 7200
                changed["automation"]["schedules"] = [
                    {
                        "id": "replacement-preview",
                        "command": "preview",
                        "intervalSeconds": 30,
                        "limit": 3,
                        "enabled": True,
                    }
                ]
                changed["metadataPolicies"][0]["language"] = "ja-JP"
                active = activate_document(service, changed)

                status, system = request(api, "/api/v1/system/status")
                self.assertEqual(status, 200)
                self.assertEqual(system["system"]["configuration_snapshot_id"], active.revision_id)
                self.assertEqual(system["system"]["maximum_active_jobs"], 7)
                status, schedules = request(api, "/api/v1/schedules")
                self.assertEqual(status, 200)
                self.assertEqual(
                    [item["schedule_id"] for item in schedules["items"]],
                    ["replacement-preview"],
                )
                status, stale = request(
                    api,
                    "/api/v1/jobs/stale",
                    headers={"QUERY_STRING": "limit=1"},
                )
                self.assertEqual(status, 200)
                self.assertEqual(stale["threshold_seconds"], 7200)
                status, job = request(
                    api,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.assertEqual(status, 202)
                self.assertEqual(job["configuration_snapshot_id"], active.revision_id)
                self.assertEqual(api._runtime_binding.metadata_policies[0].language, "ja-JP")

    def test_actual_operator_ui_assets_expose_configuration_and_failure_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteTaskRepository(Path(directory) / "runtime.sqlite3")
            try:
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                )
                status, headers, page = request_raw(api, "/ui/")
                self.assertEqual(status, 200)
                self.assertIn("text/html", headers["Content-Type"])
                self.assertIn(b"Configuration", page)
                status, headers, script = request_raw(api, "/ui/app.js")
                self.assertEqual(status, 200)
                self.assertIn("javascript", headers["Content-Type"])
                self.assertIn(b"/api/v1/configuration", script)
                self.assertIn(b"failure_category", script)
                self.assertIn(b"failure_next_action", script)
                self.assertNotIn(b"Authorization: Bearer", page + script)
            finally:
                repository.close()

    def test_api_recovery_starts_from_locator_when_workflow_bootstrap_is_broken(self) -> None:
        class Server:
            app = None
            configuration_result = None
            job_result = None
            replacement_job_result = None
            second_replacement_job_result = None
            activation_result = None

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def serve_forever(self):
                self.configuration_result = request(self.app, "/api/v1/configuration")
                self.job_result = request(
                    self.app,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                replacement = json.loads(self.replacement_document)
                status, draft = request(
                    self.app,
                    "/api/v1/configuration/drafts",
                    method="POST",
                    body=json.dumps({"document": replacement}).encode(),
                )
                self.assertions.append((status, draft))
                status, validated = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/validate",
                    method="POST",
                    body=b"{}",
                )
                self.assertions.append((status, validated))
                self.activation_result = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/activate",
                    method="POST",
                    body=json.dumps({"expectedVersion": validated["version"]}).encode(),
                )
                self.replacement_job_result = request(
                    self.app,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                self.second_replacement_job_result = request(
                    self.app,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                active = service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                broken = json.loads(json.dumps(document))
                broken["recognitionTypePolicies"][0]["metadataPolicy"] = "missing-policy"
                payload = json.dumps(
                    broken,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=?, digest=? "
                    "WHERE revision_id=?",
                    (payload, digest, active.revision_id),
                )
                repository._connection.commit()

            bootstrap = root / "bootstrap.json"
            bootstrap.write_text(
                json.dumps(
                    {
                        "persistence": {"databasePath": str(runtime)},
                        "api": {"tokenEnv": "MEDIAFLOW_API_TOKEN"},
                        "staleWorkflowContent": {"invalid": True},
                    }
                ),
                encoding="utf-8",
            )
            server = Server()
            replacement_document = json.loads(json.dumps(document))
            replacement_document["automation"]["maximumActiveJobs"] = 2
            server.replacement_document = json.dumps(replacement_document)
            server.assertions = []

            def make_server(host, port, app):
                server.app = app
                return server

            with (
                patch.dict("os.environ", {"MEDIAFLOW_API_TOKEN": "admin-token"}, clear=True),
                patch("wsgiref.simple_server.make_server", side_effect=make_server),
                patch(
                    "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("recovery API must not construct Storage"),
                ),
                patch(
                    "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                    side_effect=AssertionError("recovery API must not construct Provider"),
                ),
            ):
                output, error = io.StringIO(), io.StringIO()
                status = final_main(
                    ["--config", str(bootstrap), "api", "serve"],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(status, 0, error.getvalue())
            self.assertIsNotNone(server.app)
            status, body = server.configuration_result
            self.assertEqual(status, 200, body)
            self.assertEqual(body["health"], "UNAVAILABLE")
            status, body = server.job_result
            self.assertEqual(status, 503, body)
            self.assertEqual(body["error"]["code"], "configuration_unavailable")
            self.assertEqual(server.assertions[0][0], 201)
            self.assertEqual(server.assertions[1][0], 200)
            self.assertEqual(server.activation_result[0], 200, server.activation_result[1])
            self.assertEqual(server.activation_result[1]["status"], "active")
            self.assertEqual(server.replacement_job_result[0], 202)
            self.assertEqual(server.second_replacement_job_result[0], 202)
            self.assertEqual(
                server.replacement_job_result[1]["configuration_snapshot_id"],
                server.activation_result[1]["revisionId"],
            )

    def test_web_job_worker_task_and_result_share_one_snapshot_pin(self) -> None:
        class FakeTMDBProvider:
            provider_id = "tmdb"
            capabilities = ProviderCapabilities(can_search_movie=True)

            def __init__(self, *_args, **_kwargs):
                pass

            def search_movie(self, _query, _policy=None, **_kwargs):
                return (
                    MediaCandidate(
                        "tmdb",
                        "4242",
                        MediaType.MOVIE,
                        "Example Movie",
                        year=2024,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )

            def get_movie(self, provider_id, _policy=None, **_kwargs):
                return MediaIdentity(
                    "tmdb",
                    provider_id,
                    MediaType.MOVIE,
                    "Example Movie",
                    year=2024,
                    genres=("Animation",),
                    countries=("JP",),
                )

        class Server:
            app = None
            job_result = None
            active_result = None
            detail_result = None
            ui_result = None
            script_result = None
            lifecycle = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def serve_forever(self):
                self.ui_result = request_raw(self.app, "/ui/")
                self.script_result = request_raw(self.app, "/ui/app.js")
                status, draft = request(
                    self.app,
                    "/api/v1/configuration/drafts",
                    method="POST",
                    body=json.dumps({"document": self.invalid_document}).encode(),
                )
                self.lifecycle.append((status, draft["status"]))
                status, validated = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/validate",
                    method="POST",
                    body=b"{}",
                )
                self.lifecycle.append((status, validated["status"]))
                status, edited = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}",
                    method="PUT",
                    body=json.dumps(
                        {
                            "document": self.document,
                            "expectedVersion": validated["version"],
                        }
                    ).encode(),
                )
                self.lifecycle.append((status, edited["status"]))
                self.detail_result = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}",
                )
                status, validated = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/validate",
                    method="POST",
                    body=b"{}",
                )
                self.lifecycle.append((status, validated["status"]))
                self.active_result = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/activate",
                    method="POST",
                    body=json.dumps({"expectedVersion": validated["version"]}).encode(),
                )
                self.job_result = request(
                    self.app,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            (source_root / "电影").mkdir(parents=True)
            target_root.mkdir()
            (source_root / "电影" / "Example.Movie.2024.mkv").write_bytes(b"movie")
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["storages"][0]["rootPath"] = str(source_root)
            document["storages"][1]["rootPath"] = str(target_root)
            document["resourceLibraries"][0]["storagePath"] = ""
            document["resourceLibraries"][0]["displayRootPath"] = str(source_root)
            document["recognitionRules"][0]["condition"] = {
                "field": "resource_library_id",
                "operator": "equals",
                "value": "source",
            }
            document["persistence"]["databasePath"] = str(runtime)
            config = root / "bootstrap.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            invalid = json.loads(json.dumps(document))
            invalid["recognitionTypePolicies"][0]["metadataPolicy"] = "missing-policy"

            server = Server()
            server.document = document
            server.invalid_document = invalid

            def make_server(_host, _port, app):
                server.app = app
                return server

            with (
                patch.dict(
                    "os.environ",
                    {"TMDB_ACCESS_TOKEN": "test-token", "MEDIAFLOW_API_TOKEN": "admin-token"},
                    clear=True,
                ),
                patch("wsgiref.simple_server.make_server", side_effect=make_server),
                patch(
                    "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                    FakeTMDBProvider,
                ),
                patch(
                    "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBClient",
                    return_value=object(),
                ),
            ):
                output, error = io.StringIO(), io.StringIO()
                api_status = final_main(
                    ["--config", str(config), "api", "serve"],
                    stdout=output,
                    stderr=error,
                )
                self.assertEqual(api_status, 0, error.getvalue())
                self.assertEqual(
                    server.lifecycle,
                    [(201, "draft"), (200, "draft"), (200, "draft"), (200, "validated")],
                )
                self.assertEqual(server.ui_result[0], 200)
                self.assertEqual(server.script_result[0], 200)
                self.assertEqual(server.detail_result[0], 200)
                self.assertIn("changedSections", server.detail_result[1]["diff"])
                self.assertIn(
                    "recognitionTypePolicies",
                    server.detail_result[1]["diff"]["changedSections"],
                )
                self.assertEqual(server.active_result[0], 200, server.active_result[1])
                self.assertEqual(server.job_result[0], 202, server.job_result[1])
                job_id = server.job_result[1]["job_id"]
                active_id = server.active_result[1]["revisionId"]
                active_digest = server.active_result[1]["digest"]

                worker_output, worker_error = io.StringIO(), io.StringIO()
                worker_status = final_main(
                    ["--config", str(config), "worker", "run-next"],
                    stdout=worker_output,
                    stderr=worker_error,
                )
                self.assertEqual(worker_status, 0, worker_error.getvalue())

            with SQLiteTaskRepository(runtime) as repository:
                job = repository.get_job(job_id)
                self.assertIsNotNone(job)
                self.assertEqual(job.status.value, "completed")
                self.assertEqual(job.configuration_snapshot_id, active_id)
                self.assertEqual(job.configuration_snapshot_digest, active_digest)
                self.assertIsNotNone(job.task_id)
                task = repository.get_task(job.task_id)
                self.assertIsNotNone(task)
                self.assertEqual(task.configuration_snapshot_id, active_id)
                self.assertEqual(task.configuration_snapshot_digest, active_digest)
                results = repository.list_results(task.task_id)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].task_id, task.task_id)
                self.assertEqual(results[0].item_id, repository.list_items(task.task_id)[0].item_id)
                self.assertEqual(results[0].status, "dry_run")

    def test_worker_rechecks_current_principal_between_real_effect_boundaries(self) -> None:
        class FakeTMDBProvider:
            provider_id = "tmdb"
            capabilities = ProviderCapabilities(can_search_movie=True)

            def __init__(self, *_args, **_kwargs):
                pass

            def search_movie(self, query, _policy=None, **_kwargs):
                title = str(getattr(query, "title_candidate", ""))
                if "Beta" in title:
                    return (
                        MediaCandidate(
                            "tmdb",
                            "beta",
                            MediaType.MOVIE,
                            "Beta Movie",
                            year=2024,
                            genres=("Animation",),
                            countries=("JP",),
                        ),
                    )
                return (
                    MediaCandidate(
                        "tmdb",
                        "alpha",
                        MediaType.MOVIE,
                        "Alpha Movie",
                        year=2024,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )

            def get_movie(self, provider_id, _policy=None, **_kwargs):
                title = "Beta Movie" if provider_id == "beta" else "Alpha Movie"
                return MediaIdentity(
                    "tmdb",
                    provider_id,
                    MediaType.MOVIE,
                    title,
                    year=2024,
                    genres=("Animation",),
                    countries=("JP",),
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            incoming = source_root / "Media" / "incoming"
            incoming.mkdir(parents=True)
            target_root.mkdir()
            alpha = incoming / "Alpha.Movie.2024.mkv"
            beta = incoming / "Beta.Movie.2024.mkv"
            alpha.write_bytes(b"alpha")
            beta.write_bytes(b"beta")
            document = example_document()
            document["storages"] = [
                {
                    "id": "source-storage",
                    "name": "Source",
                    "type": "local",
                    "rootPath": str(source_root),
                },
                {
                    "id": "media-target",
                    "name": "Target",
                    "type": "local",
                    "rootPath": str(target_root),
                },
            ]
            document["resourceLibraries"][0]["displayRootPath"] = str(source_root / "Media")
            document["resourceLibraries"][0]["storagePath"] = "Media"
            document["resourceLibraries"][0]["enabled"] = True
            document["recognitionRules"][0]["condition"] = {
                "field": "resource_library_id",
                "operator": "equals",
                "value": "source",
            }
            document["automationTaskDefinitions"] = [
                {
                    "id": "automatic",
                    "name": "Automatic",
                    "resourceLibraryId": "source",
                    "sourceScope": "incoming",
                    "mode": "automatic-organization",
                    "intervalSeconds": 60,
                    "itemLimit": 2,
                    "enabled": True,
                }
            ]
            runtime = root / "runtime.sqlite3"
            document["persistence"]["databasePath"] = str(runtime)
            document["historyPath"] = str(root / "history.jsonl")
            config = root / "bootstrap.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            disabled_document = json.loads(json.dumps(document))
            disabled_document["api"]["principals"][0]["enabled"] = False

            with SQLiteConfigurationRepository(runtime) as configuration_repository:
                managed = ManagedConfigurationService(
                    configuration_repository, bootstrap_database_path=str(runtime)
                )
                active = activate_document(managed, document)
            pinned = _configuration(
                str(config),
                snapshot_id=active.revision_id,
                snapshot_digest=active.digest,
            )
            definition = pinned.automation_task_definitions[0]
            now = datetime.now(UTC)

            def disable_current_principal() -> None:
                with SQLiteConfigurationRepository(runtime) as configuration_repository:
                    activate_document(
                        ManagedConfigurationService(
                            configuration_repository, bootstrap_database_path=str(runtime)
                        ),
                        disabled_document,
                    )

            def restore_current_principal() -> None:
                with SQLiteConfigurationRepository(runtime) as configuration_repository:
                    activate_document(
                        ManagedConfigurationService(
                            configuration_repository, bootstrap_database_path=str(runtime)
                        ),
                        document,
                    )

            with SQLiteTaskRepository(runtime) as repository:
                emitted = IntervalScheduler(
                    repository,
                    pinned.automation_schedules,
                    automation_task_definitions=pinned.automation_task_definitions,
                    configuration_snapshot_id=pinned.configuration_snapshot_id,
                    configuration_snapshot_digest=pinned.configuration_snapshot_digest,
                    configuration_snapshot_version=pinned.configuration_snapshot_version,
                ).tick(now)
                self.assertEqual(len(emitted), 1)
                preview = AutomationTaskDefinitionPreview(
                    "preview-production",
                    definition.definition_id,
                    definition.definition_fingerprint,
                    pinned.configuration_snapshot_id,
                    pinned.configuration_snapshot_version,
                    pinned.configuration_snapshot_digest,
                    "active",
                    definition.resource_library_id,
                    pinned.resource_libraries[0].storage_id,
                    definition.source_scope,
                    definition.mode.value,
                    definition.item_limit,
                    {
                        "discovered": 0,
                        "selected": 0,
                        "permitted": 0,
                        "excludedIgnored": 0,
                        "unstable": 0,
                        "truncatedByLimit": 0,
                    },
                    AutomationTaskDefinitionPreviewStatus.PREVIEWED,
                    (),
                    "local-admin",
                    now,
                    now,
                )
                repository.create_automation_task_definition_preview(preview)
                grant_service = UnattendedExecutionGrantService(
                    repository,
                    preview_service=_PersistedPreviewReader(repository),
                    permission_authority=_ConfiguredPermissionAuthority(
                        lambda: _configuration(str(config))
                    ),
                )
                grant = grant_service.grant(
                    definition,
                    configuration_snapshot_id=pinned.configuration_snapshot_id,
                    configuration_snapshot_digest=pinned.configuration_snapshot_digest,
                    configuration_snapshot_version=pinned.configuration_snapshot_version,
                    actor="local-admin",
                    confirmation=True,
                    preview_id=preview.preview_id,
                    storage_id=pinned.resource_libraries[0].storage_id,
                )
                self.assertEqual(grant.preview_id, preview.preview_id)

                original_execute = OrganizerExecutor.execute
                effect_calls = []

                def execute_and_disable(executor, plan, storages, **kwargs):
                    result = original_execute(executor, plan, storages, **kwargs)
                    if result.status.value.lower() == "success":
                        effect_calls.append(plan.plan_id)
                        if len(effect_calls) == 1:
                            disable_current_principal()
                    return result

                worker = AutomationWorker(
                    repository,
                    lambda job, cancelled: _run_queued_workflow(
                        job, str(config), cancelled, repository=repository
                    ),
                )
                original_configuration = _configuration
                configuration_calls = []

                def fail_current_authority(path, **kwargs):
                    configuration_calls.append(True)
                    if len(configuration_calls) == 1:
                        return original_configuration(path, **kwargs)
                    raise RuntimeError("current permission authority unavailable")

                with patch(
                    "mediaflow.final_cli._configuration", side_effect=fail_current_authority
                ):
                    authority_failed = worker.run_next()
                self.assertIsNotNone(authority_failed)
                self.assertEqual(authority_failed.status.value, "failed")
                self.assertIsNone(authority_failed.task_id)
                self.assertEqual(
                    authority_failed.failure_category,
                    "unattended_permission_authority_unavailable",
                )
                occurrence = repository.get_latest_automation_definition_occurrence(
                    definition.definition_id
                )
                self.assertEqual(occurrence.outcome, "failed")
                self.assertIn("no Task", occurrence.reason)
                self.assertTrue(occurrence.next_action)
                self.assertEqual(repository.list_tasks(), ())
                self.assertTrue(
                    repository.admit_job(
                        replace(
                            emitted[0],
                            job_id="production-effect-job",
                            status=AutomationJobStatus.PENDING,
                            created_at=now,
                            updated_at=now,
                            started_at=None,
                            completed_at=None,
                            task_id=None,
                            error=None,
                            claim_token=None,
                            failure_category=None,
                            failure_durable_state=None,
                            failure_side_effects=None,
                            failure_retry_safe=None,
                            failure_next_action=None,
                        ),
                        100,
                    )
                )
                with (
                    patch.object(OrganizerExecutor, "execute", execute_and_disable),
                    patch.dict("os.environ", {"TMDB_ACCESS_TOKEN": "test-token"}, clear=False),
                    patch(
                        "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                        FakeTMDBProvider,
                    ),
                    patch(
                        "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBClient",
                        return_value=object(),
                    ),
                ):
                    finished = worker.run_next()
                self.assertIsNotNone(finished)
                self.assertEqual(finished.status.value, "completed")
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                items = {
                    Path(item.source_path).name: item
                    for item in repository.list_items(task.task_id)
                }
                self.assertEqual(items[alpha.name].status, TaskItemStatus.SUCCESS)
                self.assertEqual(items[beta.name].status, TaskItemStatus.FAILED)
                self.assertIn("unattended_authority", items[beta.name].error)
                results = repository.list_results(task.task_id)
                self.assertEqual([result.status for result in results], ["success", "failed"])
                checkpoints = ProcessingCheckpointService(
                    repository,
                    snapshot_validator=managed.validate_runtime_snapshot,
                )
                alpha_checkpoint = checkpoints.get(items[alpha.name].item_id)
                beta_checkpoint = checkpoints.get(items[beta.name].item_id)
                self.assertEqual(alpha_checkpoint.latest_result.status, "success")
                self.assertEqual(beta_checkpoint.error_category.value, "unattended_authority")
                self.assertEqual(beta_checkpoint.permitted_action_ids, ("investigate",))
                self.assertEqual(len(effect_calls), 1)
                self.assertFalse(alpha.exists())
                self.assertTrue(beta.exists())
                self.assertTrue(
                    any("Alpha Movie" in path.name for path in target_root.rglob("*.mkv"))
                )
                self.assertFalse(
                    any("Beta Movie" in path.name for path in target_root.rglob("*.mkv"))
                )
                restore_current_principal()
                self.assertIsNone(worker.run_next())

    def test_checked_local_setup_preview_keeps_original_pin_after_second_activation(
        self,
    ) -> None:
        class FakeTMDBProvider:
            provider_id = "tmdb"
            capabilities = ProviderCapabilities(can_search_movie=True)

            def __init__(self, *_args, **_kwargs):
                pass

            def search_movie(self, _query, _policy=None, **_kwargs):
                return (
                    MediaCandidate(
                        "tmdb",
                        "4242",
                        MediaType.MOVIE,
                        "Example Movie",
                        year=2024,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )

            def get_movie(self, provider_id, _policy=None, **_kwargs):
                return MediaIdentity(
                    "tmdb",
                    provider_id,
                    MediaType.MOVIE,
                    "Example Movie",
                    year=2024,
                    genres=("Animation",),
                    countries=("JP",),
                )

        class Server:
            app = None
            first_active = None
            first_check = None
            first_job = None
            second_active = None
            second_check = None
            job_detail = None
            task_detail = None

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def checked_activate(self, document):
                status, draft = request(
                    self.app,
                    "/api/v1/configuration/drafts",
                    method="POST",
                    body=json.dumps({"document": document}).encode(),
                )
                if status != 201:
                    raise AssertionError((status, draft))
                revision_id = draft["revisionId"]
                status, validated = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{revision_id}/validate",
                    method="POST",
                    body=b"{}",
                )
                if status != 200 or validated["status"] != "validated":
                    raise AssertionError((status, validated))
                status, evidence = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{revision_id}/local-setup-check",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedVersion": validated["version"],
                            "expectedDigest": validated["digest"],
                            "resourceLibraryId": "source",
                            "mediaLibraryId": "movies",
                        }
                    ).encode(),
                )
                if status != 200 or evidence["status"] != "passed":
                    raise AssertionError((status, evidence))
                for storage_id in ("source-storage", "media-target"):
                    status, storage_evidence = request(
                        self.app,
                        f"/api/v1/configuration/revisions/{revision_id}/storage-check",
                        method="POST",
                        body=json.dumps(
                            {
                                "storageId": storage_id,
                                "expectedVersion": validated["version"],
                                "expectedDigest": validated["digest"],
                            }
                        ).encode(),
                    )
                    if status != 200 or storage_evidence["status"] != "passed":
                        raise AssertionError((status, storage_evidence))
                status, strategy_evidence = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{revision_id}/recognition-strategy-test",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedVersion": validated["version"],
                            "expectedDigest": validated["digest"],
                            "resourceLibraryId": "source",
                            "syntheticPath": "/电影/Example.Movie.2024.mkv",
                        }
                    ).encode(),
                )
                if status != 200 or strategy_evidence["status"] != "completed":
                    raise AssertionError((status, strategy_evidence))
                status, destination_evidence = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{revision_id}/destination-precheck",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedVersion": validated["version"],
                            "expectedDigest": validated["digest"],
                            "recognitionType": "C",
                            "sample": {
                                "title": "Example Movie",
                                "mediaType": "movie",
                                "year": 2024,
                                "genres": ["Animation"],
                                "countries": ["JP"],
                                "extension": "mkv",
                            },
                        }
                    ).encode(),
                )
                if status != 200 or destination_evidence["status"] != "completed":
                    raise AssertionError((status, destination_evidence))
                status, active = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{revision_id}/activate",
                    method="POST",
                    body=json.dumps(
                        {"expectedVersion": validated["version"], "checked": True}
                    ).encode(),
                )
                if status != 200 or active["status"] != "active":
                    raise AssertionError((status, active))
                return evidence, active

            def serve_forever(self):
                self.first_check, self.first_active = self.checked_activate(self.first_document)
                status, self.first_job = request(
                    self.app,
                    "/api/v1/jobs",
                    method="POST",
                    body=json.dumps({"command": "preview"}).encode(),
                )
                if status != 202:
                    raise AssertionError((status, self.first_job))
                self.second_check, self.second_active = self.checked_activate(self.second_document)
                worker_output, worker_error = io.StringIO(), io.StringIO()
                with patch(
                    "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBClient",
                    return_value=object(),
                ):
                    worker_status = final_main(
                        ["--config", str(self.config), "worker", "run-next"],
                        stdout=worker_output,
                        stderr=worker_error,
                    )
                if worker_status != 0:
                    raise AssertionError(
                        (worker_status, worker_output.getvalue(), worker_error.getvalue())
                    )
                job_id = self.first_job["job_id"]
                status, self.job_detail = request(self.app, f"/api/v1/jobs/{job_id}")
                if status != 200:
                    raise AssertionError((status, self.job_detail))
                status, self.task_detail = request(
                    self.app,
                    f"/api/v1/tasks/{self.job_detail['task_id']}",
                    query="itemLimit=100&resultLimit=100",
                )
                if status != 200:
                    raise AssertionError((status, self.task_detail))

        def directory_state(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
            return tuple(
                (
                    path.relative_to(root).as_posix(),
                    "directory" if path.is_dir() else "file",
                    None if path.is_dir() else path.read_bytes(),
                )
                for path in sorted(root.rglob("*"))
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            (source_root / "电影").mkdir(parents=True)
            (target_root / "Movies").mkdir(parents=True)
            (source_root / "电影" / "Example.Movie.2024.mkv").write_bytes(b"movie")
            runtime = root / "runtime.sqlite3"
            first_document = example_document()
            first_document["storages"][0]["rootPath"] = str(source_root)
            first_document["storages"][1]["rootPath"] = str(target_root)
            first_document["resourceLibraries"][0]["storagePath"] = ""
            first_document["resourceLibraries"][0]["displayRootPath"] = str(source_root)
            first_document["mediaLibraries"][0]["rootPath"] = "Movies"
            first_document["recognitionRules"][0]["condition"] = {
                "field": "resource_library_id",
                "operator": "equals",
                "value": "source",
            }
            first_document["persistence"]["databasePath"] = str(runtime)
            second_document = json.loads(json.dumps(first_document))
            second_document["classificationPolicies"][0]["rules"][0]["result"]["path"] = [
                "Later Active Only"
            ]
            first_destination = (
                "Movies/Anime/Example Movie (2024) [tmdbid-4242]/Example Movie (2024).mkv"
            )
            second_destination = (
                "Movies/Later Active Only/Example Movie (2024) [tmdbid-4242]/"
                "Example Movie (2024).mkv"
            )
            config = root / "bootstrap.json"
            config.write_text(json.dumps(first_document), encoding="utf-8")
            server = Server()
            server.first_document = first_document
            server.second_document = second_document
            server.config = str(config)

            def make_server(_host, _port, app):
                server.app = app
                return server

            before = (directory_state(source_root), directory_state(target_root))
            with (
                patch.dict(
                    "os.environ",
                    {"TMDB_ACCESS_TOKEN": "test-token", "MEDIAFLOW_API_TOKEN": "admin-token"},
                    clear=True,
                ),
                patch("wsgiref.simple_server.make_server", side_effect=make_server),
                patch(
                    "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                    FakeTMDBProvider,
                ),
            ):
                output, error = io.StringIO(), io.StringIO()
                api_status = final_main(
                    ["--config", str(config), "api", "serve"],
                    stdout=output,
                    stderr=error,
                )
                self.assertEqual(api_status, 0, error.getvalue())
                first_id = server.first_active["revisionId"]
                first_digest = server.first_active["digest"]
                second_id = server.second_active["revisionId"]
                self.assertNotEqual(first_id, second_id)
                self.assertEqual(server.first_check["revisionId"], first_id)
                self.assertEqual(server.first_check["revisionDigest"], first_digest)
                self.assertEqual(server.second_check["revisionId"], second_id)
                self.assertEqual(server.first_job["configuration_snapshot_id"], first_id)
                self.assertEqual(server.first_job["configuration_snapshot_digest"], first_digest)
                self.assertEqual(
                    first_document["classificationPolicies"][0]["rules"][0]["result"]["path"],
                    ["Anime"],
                )
                self.assertEqual(
                    second_document["classificationPolicies"][0]["rules"][0]["result"]["path"],
                    ["Later Active Only"],
                )

                self.assertEqual(server.job_detail["status"], "completed")
                self.assertEqual(server.job_detail["configuration_snapshot_id"], first_id)
                self.assertEqual(server.job_detail["configuration_snapshot_digest"], first_digest)
                self.assertFalse(server.job_detail["execute_authorized"])
                self.assertEqual(server.task_detail["configuration_snapshot_id"], first_id)
                self.assertEqual(server.task_detail["configuration_snapshot_digest"], first_digest)
                self.assertFalse(server.task_detail["execute_authorized"])
                self.assertEqual(len(server.task_detail["items"]), 1)
                self.assertEqual(
                    server.task_detail["items"][0]["destination_path"],
                    first_destination,
                )
                self.assertNotEqual(
                    server.task_detail["items"][0]["destination_path"],
                    second_destination,
                )
                self.assertEqual(
                    len(server.task_detail["results"]),
                    1,
                    repr(server.task_detail),
                )
                result = server.task_detail["results"][0]
                self.assertEqual(result["status"], "dry_run")
                self.assertEqual(result["recognition_type"], "A")
                self.assertEqual(result["title"], "Example Movie")
                self.assertEqual(result["classification_policy_id"], "A")
                self.assertEqual(result["destination_path"], first_destination)
                self.assertNotEqual(result["destination_path"], second_destination)
                self.assertEqual(result["task_id"], server.job_detail["task_id"])
                self.assertEqual(
                    result["item_id"],
                    server.task_detail["items"][0]["item_id"],
                )

            self.assertEqual(
                (directory_state(source_root), directory_state(target_root)),
                before,
            )
            with SQLiteConfigurationRepository(runtime) as configuration_repository:
                current = configuration_repository.get_active_revision()
                self.assertIsNotNone(current)
                self.assertEqual(current.revision_id, second_id)

    def test_worker_continues_pinned_scan_when_current_active_is_unhealthy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            source_root.mkdir()
            target_root.mkdir()
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["storages"][0]["rootPath"] = str(source_root)
            document["storages"][1]["rootPath"] = str(target_root)
            document["resourceLibraries"][0]["storagePath"] = ""
            document["resourceLibraries"][0]["displayRootPath"] = str(source_root)
            document["persistence"]["databasePath"] = str(runtime)
            config = root / "bootstrap.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(runtime),
                )
                first_draft = service.import_draft(document, actor="tester")
                first_validated = service.validate(first_draft.revision_id, actor="tester")
                first = service.activate(
                    first_validated.revision_id,
                    expected_version=first_validated.version,
                    actor="tester",
                )
                from mediaflow.application.automation import AutomationJobService

                old_job = AutomationJobService(
                    task_repository,
                    configuration_snapshot_id=first.revision_id,
                    configuration_snapshot_digest=first.digest,
                ).submit("scan")
                second_document = json.loads(json.dumps(document))
                second_document["historyPath"] = str(root / "second-history.jsonl")
                second_draft = service.import_draft(second_document, actor="tester")
                second_validated = service.validate(second_draft.revision_id, actor="tester")
                second = service.activate(
                    second_validated.revision_id,
                    expected_version=second_validated.version,
                    actor="tester",
                )
                broken = json.loads(json.dumps(second_document))
                broken["recognitionTypePolicies"][0]["metadataPolicy"] = "missing-policy"
                payload = json.dumps(
                    broken,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                configuration_repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=?, digest=? "
                    "WHERE revision_id=?",
                    (payload, digest, second.revision_id),
                )
                configuration_repository._connection.commit()

            output, error = io.StringIO(), io.StringIO()
            status = final_main(
                ["--config", str(config), "worker", "run-next"],
                stdout=output,
                stderr=error,
            )
            self.assertEqual(status, 0, error.getvalue())
            with SQLiteTaskRepository(runtime) as repository:
                completed_job = repository.get_job(old_job.job_id)
                self.assertIsNotNone(completed_job)
                self.assertEqual(completed_job.status.value, "completed")
                self.assertIsNotNone(completed_job.task_id)
                task = repository.get_task(completed_job.task_id)
                self.assertIsNotNone(task)
                self.assertEqual(task.configuration_snapshot_id, first.revision_id)
                self.assertEqual(task.configuration_snapshot_digest, first.digest)

    def test_worker_claim_bootstrap_uses_locator_before_any_job_is_claimed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            config = root / "bootstrap.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            with (
                patch(
                    "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("worker bootstrap must not construct Storage"),
                ),
                patch(
                    "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                    side_effect=AssertionError("worker bootstrap must not construct Provider"),
                ),
            ):
                output, error = io.StringIO(), io.StringIO()
                status = final_main(
                    ["--config", str(config), "worker", "run-next"],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(status, 0, error.getvalue())
            self.assertIn("No pending automation jobs", output.getvalue())

    def test_worker_rejects_legacy_unpinned_job_after_managed_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            config = root / "bootstrap.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(runtime),
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                legacy = AutomationJobService(task_repository).submit("preview")
                worker = AutomationWorker(
                    task_repository,
                    lambda job, cancelled: _run_queued_workflow(job, str(config), cancelled),
                )
                finished = worker.run_next()
                self.assertIsNotNone(finished)
                self.assertEqual(finished.status.value, "failed")
                self.assertEqual(finished.job_id, legacy.job_id)
                self.assertEqual(
                    finished.error,
                    "saved configuration snapshot is unavailable",
                )
                self.assertEqual(finished.failure_category, "job_snapshot_missing")
                self.assertEqual(
                    finished.failure_durable_state,
                    "saved_configuration_unavailable",
                )
                self.assertEqual(finished.failure_side_effects, "none")
                self.assertFalse(finished.failure_retry_safe)
                self.assertIn("restore", finished.failure_next_action or "")
                self.assertEqual(task_repository.list_tasks(), ())

    def test_worker_reports_actionable_saved_revision_failures_without_media_io(self) -> None:
        cases = {
            "missing": "snapshot_missing",
            "digest-corrupt": "digest_corrupt",
            "payload-unreadable": "snapshot_unreadable",
            "schema-unsupported": "schema_unsupported",
            "runtime-invalid": "runtime_invalid",
        }
        for mutation, expected_category in cases.items():
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                runtime = root / "runtime.sqlite3"
                document = example_document()
                document["persistence"]["databasePath"] = str(runtime)
                config = root / "bootstrap.json"
                config.write_text(json.dumps(document), encoding="utf-8")
                with (
                    SQLiteConfigurationRepository(runtime) as configuration_repository,
                    SQLiteTaskRepository(runtime) as task_repository,
                ):
                    service = ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=str(runtime),
                    )
                    first = activate_document(service, document)
                    queued = AutomationJobService(
                        task_repository,
                        configuration_snapshot_id=first.revision_id,
                        configuration_snapshot_digest=first.digest,
                    ).submit("preview")
                    expected_pin_digest = first.digest
                    changed = json.loads(json.dumps(document))
                    changed["historyPath"] = str(root / "current.jsonl")
                    current = activate_document(service, changed)
                    self.assertNotEqual(first.revision_id, current.revision_id)

                    if mutation == "missing":
                        configuration_repository._connection.execute(
                            "DELETE FROM managed_configuration_revisions WHERE revision_id=?",
                            (first.revision_id,),
                        )
                    elif mutation == "schema-unsupported":
                        configuration_repository._connection.execute(
                            "UPDATE managed_configuration_revisions SET schema_version=99 "
                            "WHERE revision_id=?",
                            (first.revision_id,),
                        )
                    elif mutation == "payload-unreadable":
                        configuration_repository._connection.execute(
                            "UPDATE managed_configuration_revisions SET payload=? "
                            "WHERE revision_id=?",
                            ("{not-json", first.revision_id),
                        )
                    else:
                        damaged = json.loads(json.dumps(document))
                        if mutation == "runtime-invalid":
                            damaged["recognitionTypePolicies"][0]["metadataPolicy"] = (
                                "missing-policy"
                            )
                        else:
                            damaged["historyPath"] = str(root / "tampered.jsonl")
                        payload = json.dumps(
                            damaged,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                            allow_nan=False,
                        )
                        digest = (
                            hashlib.sha256(payload.encode("utf-8")).hexdigest()
                            if mutation == "runtime-invalid"
                            else first.digest
                        )
                        configuration_repository._connection.execute(
                            "UPDATE managed_configuration_revisions SET payload=?, digest=? "
                            "WHERE revision_id=?",
                            (payload, digest, first.revision_id),
                        )
                        if mutation == "runtime-invalid":
                            configuration_repository._connection.execute(
                                "UPDATE automation_jobs SET configuration_snapshot_digest=? "
                                "WHERE job_id=?",
                                (digest, queued.job_id),
                            )
                            expected_pin_digest = digest
                    configuration_repository._connection.commit()

                with (
                    patch(
                        "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                        side_effect=AssertionError("failed snapshot must not construct Storage"),
                    ),
                    patch(
                        "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                        side_effect=AssertionError("failed snapshot must not construct Provider"),
                    ),
                ):
                    output, error = io.StringIO(), io.StringIO()
                    status = final_main(
                        ["--config", str(config), "worker", "run-next"],
                        stdout=output,
                        stderr=error,
                    )
                self.assertEqual(status, 1)
                self.assertNotIn("test-token", output.getvalue() + error.getvalue())
                with (
                    SQLiteConfigurationRepository(runtime) as configuration_repository,
                    SQLiteTaskRepository(runtime) as task_repository,
                ):
                    finished = task_repository.get_job(queued.job_id)
                    self.assertIsNotNone(finished)
                    self.assertEqual(finished.status.value, "failed")
                    self.assertEqual(
                        finished.configuration_snapshot_id,
                        first.revision_id,
                    )
                    self.assertEqual(
                        finished.configuration_snapshot_digest,
                        expected_pin_digest,
                    )
                    self.assertEqual(finished.failure_category, expected_category)
                    self.assertEqual(
                        finished.failure_durable_state,
                        "saved_configuration_unavailable",
                    )
                    self.assertEqual(finished.failure_side_effects, "none")
                    self.assertFalse(finished.failure_retry_safe)
                    self.assertIn("restore", finished.failure_next_action or "")
                    self.assertEqual(task_repository.list_tasks(), ())
                    api = MediaFlowApi(
                        task_repository,
                        None,
                        principals=(
                            ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                        ),
                        configuration_service=ManagedConfigurationService(
                            configuration_repository,
                            bootstrap_database_path=str(runtime),
                        ),
                        configuration_snapshot_id=current.revision_id,
                        configuration_snapshot_digest=current.digest,
                        bootstrap_document=document,
                    )
                    api_status, api_job = request(
                        api,
                        f"/api/v1/jobs/{queued.job_id}",
                    )
                    self.assertEqual(api_status, 200, api_job)
                    self.assertEqual(api_job["failure_category"], expected_category)
                    self.assertEqual(
                        api_job["failure_durable_state"],
                        "saved_configuration_unavailable",
                    )
                    self.assertEqual(api_job["failure_side_effects"], "none")
                    self.assertFalse(api_job["failure_retry_safe"])
                    self.assertIn("restore", api_job["failure_next_action"])

    def test_unreadable_active_reports_identity_and_allows_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                active = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                service.activate(
                    active.revision_id, expected_version=active.version, actor="tester"
                )
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=? WHERE status='active'",
                    ("{malformed",),
                )
                repository._connection.commit()
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                status = service.status_document()
                self.assertEqual(status["health"], "UNAVAILABLE")
                self.assertEqual(status["lastKnownActive"]["revisionId"], active.revision_id)

    def test_digest_corrupt_active_can_be_replaced_after_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                active = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                service.activate(
                    active.revision_id, expected_version=active.version, actor="tester"
                )
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=? WHERE status='active'",
                    (json.dumps({"corrupt": True}),),
                )
                repository._connection.commit()

            replacement = json.loads(json.dumps(document))
            replacement["historyPath"] = str(root / "replacement.jsonl")
            with SQLiteConfigurationRepository(runtime) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(runtime),
                )
                draft = service.import_draft(replacement, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                published = service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                self.assertEqual(published.status, ManagedConfigurationStatus.ACTIVE)
                self.assertEqual(repository.get_active_revision().revision_id, draft.revision_id)

    def test_scheduler_resolves_snapshot_at_each_emission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteTaskRepository(Path(directory) / "runtime.sqlite3")
            try:
                current = [("first", "digest-first")]
                schedule = IntervalSchedule("test", AutomationCommand.SCAN, 1)
                scheduler = IntervalScheduler(
                    repository,
                    (schedule,),
                    configuration_snapshot_resolver=lambda: current[0],
                )
                first = scheduler.tick()
                self.assertEqual(first[0].configuration_snapshot_id, "first")
                current[0] = ("second", "digest-second")
                second = scheduler.tick(
                    first[0].created_at.replace(microsecond=0) + timedelta(seconds=2)
                )
                self.assertEqual(second[0].configuration_snapshot_id, "second")
            finally:
                repository.close()

    def test_scheduler_reload_failure_emits_nothing_and_preserves_due_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteTaskRepository(Path(directory) / "runtime.sqlite3")
            try:
                schedule = IntervalSchedule("test", AutomationCommand.SCAN, 60)
                current = [
                    SchedulerConfigurationSnapshot("revision-a", "digest-a", (schedule,), 10)
                ]

                def resolve():
                    if current[0] is None:
                        raise RuntimeError("unavailable snapshot")
                    return current[0]

                scheduler = IntervalScheduler(
                    repository,
                    (schedule,),
                    configuration_snapshot_resolver=resolve,
                )
                now = datetime.now(UTC)
                emitted = scheduler.tick(now)
                self.assertEqual(len(emitted), 1)
                state_before = repository.get_schedule_state("test")
                self.assertIsNotNone(state_before)
                current[0] = None
                with self.assertRaises(RuntimeError):
                    scheduler.tick(now + timedelta(seconds=61))
                self.assertEqual(repository.list_jobs(), (emitted[0],))
                self.assertEqual(repository.get_schedule_state("test"), state_before)
            finally:
                repository.close()

    def test_legacy_unpinned_task_is_rejected_after_managed_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            config = root / "config.json"
            document = example_document()
            document["persistence"]["databasePath"] = str(runtime)
            config.write_text(json.dumps(document), encoding="utf-8")
            with (
                SQLiteConfigurationRepository(runtime) as configuration_repository,
                SQLiteTaskRepository(runtime) as task_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(runtime),
                )
                active = service.validate(
                    service.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                service.activate(
                    active.revision_id, expected_version=active.version, actor="tester"
                )
                from mediaflow.application.task_runtime import PersistentTaskCoordinator

                task = PersistentTaskCoordinator(task_repository, task_repository).create(
                    "preview", execute_authorized=False
                )
                with self.assertRaises(RuntimeSnapshotUnavailable):
                    _task_snapshot_identity(str(config), task.task_id)

    def test_managed_task_creation_requires_an_atomic_snapshot_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteTaskRepository(Path(directory) / "runtime.sqlite3")
            try:
                coordinator = PersistentTaskCoordinator(repository, repository)
                with self.assertRaisesRegex(ValueError, "snapshot pin"):
                    coordinator.create(
                        "preview",
                        execute_authorized=False,
                        require_configuration_snapshot=True,
                    )
                with self.assertRaisesRegex(ValueError, "provided together"):
                    coordinator.create(
                        "preview",
                        execute_authorized=False,
                        configuration_snapshot_id="revision-a",
                    )
            finally:
                repository.close()


if __name__ == "__main__":
    unittest.main()
