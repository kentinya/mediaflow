from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.automation import IntervalScheduler
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import (
    AutomationTaskDefinition,
    AutomationTaskRunMode,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.configuration_integrity import (
    MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
    canonical_document_digest,
)
from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationObjectKind,
    ConfigurationVersionConflict,
    ManagedConfigurationRevision,
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
    _task_snapshot_identity,
    final_main,
)
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


class _SnapshotTMDBProvider:
    """A synthetic Provider so a real shared analysis needs no external service."""

    provider_id = "tmdb"
    capabilities = ProviderCapabilities(can_search_movie=True)

    def __init__(self, *_args, **_kwargs):
        pass

    def search_movie(self, query, _policy=None, **_kwargs):
        title = str(getattr(query, "title_candidate", ""))
        provider_id = "beta" if "Beta" in title else "alpha"
        name = "Beta Movie" if provider_id == "beta" else "Alpha Movie"
        return (
            MediaCandidate(
                "tmdb",
                provider_id,
                MediaType.MOVIE,
                name,
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
        )

    def get_movie(self, provider_id, _policy=None, **_kwargs):
        name = "Beta Movie" if provider_id == "beta" else "Alpha Movie"
        return MediaIdentity(
            "tmdb",
            provider_id,
            MediaType.MOVIE,
            name,
            year=2024,
            genres=("Animation",),
            countries=("JP",),
        )


def _snapshot_provider_registry(_requested):
    from mediaflow.application.metadata import MetadataProviderRegistry

    return MetadataProviderRegistry((_SnapshotTMDBProvider(),))


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


def set_local_roots(document, root):
    import os

    os.environ.setdefault("TMDB_ACCESS_TOKEN", "test-token")
    source = root / "source"
    target = root / "target"
    source.mkdir(parents=True, exist_ok=True)
    (target / "Movies").mkdir(parents=True, exist_ok=True)
    document["storages"][0]["rootPath"] = str(source)
    document["storages"][1]["rootPath"] = str(target)
    document["resourceLibraries"][0]["storagePath"] = ""
    document["resourceLibraries"][0]["displayRootPath"] = str(source)
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    document["recognitionRules"][0]["condition"] = {
        "field": "resource_library_id",
        "operator": "equals",
        "value": "source",
    }
    return document


def publish_document(api, document, *, expected=None, replace=False, token="admin-token"):
    body = {"document": document}
    if expected is not None:
        body.update(
            {
                "expectedActiveRevisionId": expected.revision_id,
                "expectedActiveVersion": expected.revision_sequence or expected.version,
                "expectedActiveDigest": expected.digest,
            }
        )
    if replace:
        body["replaceActive"] = True
    return request(
        api,
        "/api/configuration/publish",
        method="POST",
        body=json.dumps(body).encode(),
        token=token,
    )


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


def submit_organize_job(api, *, limit=None):
    """Admit one real organizing Task through the current Task kernel.

    The retired remote ticket boundary is gone; this helper uses the same
    non-interactive kernel admission the supported CLI/Scheduler entrances use,
    under the API's current configuration pin, then reads the Task back through
    the ordinary ``GET /api/tasks/{id}`` projection.
    """
    from datetime import UTC, datetime

    from mediaflow.application.task_scheduling import build_scheduled_task_admission
    from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
    from mediaflow.domain.task_persistence import RunDisplayContext
    from mediaflow.domain.task_scheduling import TaskQueueFull, TaskTrigger

    limit = 1 if limit is None else limit
    try:
        api._refresh_configuration_binding()
        binding = api._runtime_binding
    except RuntimeSnapshotUnavailable as error:
        return 503, {
            "error": {
                "code": "configuration_unavailable",
                "details": {
                    "reason": getattr(error, "reason", None),
                    "revisionId": getattr(error, "revision_id", None),
                    "version": getattr(error, "version", None),
                    "digest": getattr(error, "digest", None),
                    "durableState": "managed_active_unavailable",
                    "sideEffects": "none",
                    "retrySafe": True,
                },
            }
        }
    except Exception:
        return 503, {"error": {"code": "configuration_unavailable"}}
    if binding.snapshot_id is None:
        return 503, {"error": {"code": "configuration_unavailable"}}
    task, state = build_scheduled_task_admission(
        "organize",
        execute_authorized=True,
        trigger=TaskTrigger.MANUAL,
        principal="tester",
        item_limit=limit,
        configuration_snapshot_id=binding.snapshot_id,
        configuration_snapshot_digest=binding.snapshot_digest,
        require_configuration_snapshot=True,
        now=datetime.now(UTC),
    )
    try:
        api._repository.admit_scheduled_task(
            task,
            state,
            capacity=binding.maximum_active_jobs,
            display=RunDisplayContext(source_scope=None, origin_kind="remote-organize"),
        )
    except TaskQueueFull:
        return 409, {"error": {"code": "queue_full"}}
    return request(api, f"/api/tasks/{task.task_id}")


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

    def test_accepted_draft_with_historical_webhook_validates_and_activates(self) -> None:
        """A Draft accepted before this version keeps its exact bytes.

        The previous version stored the notification Webhook under
        ``notifications`` with the then-current event names.  An upgraded
        instance validates and activates that same durable revision without
        rejecting the deployment-produced bytes or rewriting its ID, digest,
        document or lifecycle evidence.
        """

        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "runtime.sqlite3")
            document = example_document()
            webhook = document.pop("webhooks")[0]
            webhook["events"] = ["job.completed", "job.failed", "schedule.emitted"]
            document["notifications"]["webhooks"] = [webhook]
            document["persistence"]["databasePath"] = database
            now = datetime.now(UTC)
            with SQLiteConfigurationRepository(
                Path(directory) / "configuration.sqlite3"
            ) as repository:
                accepted = repository.create_revision(
                    ManagedConfigurationRevision(
                        "previous-version-draft",
                        1,
                        ManagedConfigurationStatus.DRAFT,
                        MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
                        canonical_document_digest(document),
                        document,
                        now,
                        now,
                    )
                )
                service = ManagedConfigurationService(repository)
                validated = service.validate(accepted.revision_id, actor="tester")
                self.assertEqual(validated.status, ManagedConfigurationStatus.VALIDATED)
                self.assertEqual(validated.validation_errors, ())
                self.assertEqual(validated.document, document)
                self.assertEqual(validated.digest, accepted.digest)
                active = service.activate(
                    accepted.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                self.assertEqual(active.status, ManagedConfigurationStatus.ACTIVE)
                self.assertEqual(active.document, document)
                self.assertEqual(active.digest, accepted.digest)
                self.assertEqual(repository.get_active_revision().revision_id, accepted.revision_id)
                self.assertEqual(
                    [item.action for item in repository.list_revision_audits(accepted.revision_id)],
                    ["activate", "validate"],
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

    def test_tasks_pin_the_snapshot_at_submission_boundary(self) -> None:
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
                from mediaflow.application.task_scheduling import TaskSchedulingService
                from mediaflow.domain.task_scheduling import TaskTrigger

                old_task = (
                    TaskSchedulingService(runtime_repository, capacity=10)
                    .admit(
                        "organize",
                        execute_authorized=True,
                        trigger=TaskTrigger.MANUAL,
                        principal="tester",
                        configuration_snapshot_id=first_active.revision_id,
                        configuration_snapshot_digest=first_active.digest,
                        require_configuration_snapshot=True,
                    )
                    .task
                )
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
                new_task = (
                    TaskSchedulingService(runtime_repository, capacity=10)
                    .admit(
                        "organize",
                        execute_authorized=True,
                        trigger=TaskTrigger.MANUAL,
                        principal="tester",
                        configuration_snapshot_id=second_active.revision_id,
                        configuration_snapshot_digest=second_active.digest,
                        require_configuration_snapshot=True,
                    )
                    .task
                )
                self.assertEqual(old_task.configuration_snapshot_id, first_active.revision_id)
                self.assertEqual(old_task.configuration_snapshot_digest, first_active.digest)
                self.assertEqual(new_task.configuration_snapshot_id, second_active.revision_id)
                self.assertEqual(new_task.configuration_snapshot_digest, second_active.digest)

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
                accepted = [submit_organize_job(api) for _ in range(2)]
                self.assertEqual([item[0] for item in accepted], [200, 200])
                self.assertTrue(
                    all(
                        item[1]["configuration_snapshot_id"] == second.revision_id
                        for item in accepted
                    )
                )
                from mediaflow.application.task_scheduling import TaskSchedulingService
                from mediaflow.domain.task_scheduling import TaskControl

                scheduling = TaskSchedulingService(task_repository, capacity=2)
                for _, item in accepted:
                    scheduling.request_control(
                        item["task_id"], TaskControl.CANCEL, now=datetime.now(UTC)
                    )

                restricted = json.loads(json.dumps(expanded))
                restricted["historyPath"] = str(root / "restricted.jsonl")
                restricted["automation"]["maximumActiveJobs"] = 1
                third = activate_document(service, restricted)
                first_under_third = submit_organize_job(api)
                rejected = submit_organize_job(api)
                self.assertEqual(first_under_third[0], 200)
                self.assertEqual(
                    first_under_third[1]["configuration_snapshot_id"], third.revision_id
                )
                self.assertEqual(rejected[0], 409)
                self.assertEqual(rejected[1]["error"]["code"], "queue_full")

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
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    maximum_active_jobs=2,
                    configuration_service=service,
                    configuration_snapshot_id=first.revision_id,
                    configuration_snapshot_digest=first.digest,
                    bootstrap_document=document,
                )
                existing = submit_organize_job(api)
                self.assertEqual(existing[0], 200)
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
                    outcomes.append(submit_organize_job(api))

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
                self.assertIn(status, {200, 409})
                if status == 200:
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
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, value = request(api, "/api/system/status")
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
            document = set_local_roots(example_document(), Path(directory))
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
                    principals=(admin, viewer),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, body = request(api, "/api/configuration", token="viewer-token")
                self.assertEqual(status, 200)
                self.assertEqual(body["authority"], "MANAGEMENT_BOOTSTRAP")
                status, active_body = publish_document(api, document)
                self.assertEqual(status, 200)
                self.assertTrue(active_body["published"])
                self.assertEqual(active_body["status"], "active")
                revision_id = active_body["revisionId"]
                job_status, job_body = submit_organize_job(api)
                self.assertEqual(job_status, 200)
                self.assertEqual(job_body["configuration_snapshot_id"], revision_id)
                status, denied = publish_document(api, document, token="viewer-token")
                self.assertEqual(status, 403)
                self.assertEqual(denied["error"]["code"], "forbidden")
                for retired in (
                    ("/api/configuration/drafts", "POST"),
                    (f"/api/configuration/revisions/{revision_id}/activate", "POST"),
                    (f"/api/configuration/revisions/{revision_id}/validate", "POST"),
                ):
                    status, body = request(api, retired[0], method=retired[1], body=b"{}")
                    self.assertEqual(status, 404)
                    self.assertEqual(body["error"]["code"], "not_found")

    def test_api_document_submission_reconciles_without_a_second_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = set_local_roots(example_document(), Path(directory))
            document["persistence"]["databasePath"] = str(Path(directory) / "runtime.sqlite3")
            with (
                SQLiteConfigurationRepository(
                    Path(directory) / "runtime.sqlite3"
                ) as configuration_repository,
                SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(configuration_repository)
                admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                api = MediaFlowApi(
                    runtime_repository,
                    principals=(admin,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, first = publish_document(api, document)
                self.assertEqual(status, 200)
                current = service.active()
                submission_id = "document-publish-submission-1"
                status, published = request(
                    api,
                    "/api/configuration/publish",
                    method="POST",
                    body=json.dumps(
                        {
                            "document": current.document,
                            "expectedActiveRevisionId": current.revision_id,
                            "expectedActiveVersion": current.revision_sequence or current.version,
                            "expectedActiveDigest": current.digest,
                            "submissionId": submission_id,
                        }
                    ).encode(),
                )
                self.assertEqual(status, 200, published)
                self.assertEqual(published["submissionId"], submission_id)
                before = len(service.repository.list_revisions(limit=100))
                status, reconciled = request(
                    api,
                    "/api/system/settings/reconcile",
                    query=f"submissionId={submission_id}",
                )
                self.assertEqual(status, 200, reconciled)
                self.assertEqual(reconciled["state"], "COMMITTED")
                self.assertEqual(reconciled["committedRevisionId"], published["revisionId"])
                self.assertEqual(reconciled["sideEffects"], "none")
                self.assertEqual(len(service.repository.list_revisions(limit=100)), before)
                self.assertEqual(service.active().revision_id, published["revisionId"])

                # A refused command with a lost transport also has a terminal
                # answer for its own identity; absence alone is never proof.
                refused_submission = "document-publish-refused-1"
                status, refused = request(
                    api,
                    "/api/configuration/publish",
                    method="POST",
                    body=json.dumps(
                        {
                            "document": current.document,
                            "expectedActiveRevisionId": current.revision_id,
                            "expectedActiveVersion": (current.revision_sequence or current.version)
                            + 99,
                            "submissionId": refused_submission,
                        }
                    ).encode(),
                )
                self.assertEqual(status, 409, refused)
                status, reconciled = request(
                    api,
                    "/api/system/settings/reconcile",
                    query=f"submissionId={refused_submission}",
                )
                self.assertEqual(status, 200, reconciled)
                self.assertEqual(reconciled["state"], "NOT_COMMITTED")
                self.assertFalse(reconciled["committed"])
                self.assertEqual(reconciled["sideEffects"], "none")
                self.assertEqual(service.active().revision_id, published["revisionId"])

    def test_api_invalid_candidate_is_rejected_then_corrected_publish_pins_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = set_local_roots(example_document(), Path(directory))
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
                    principals=(admin,),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, refused = publish_document(api, invalid)
                self.assertIn(status, {400, 422})
                self.assertNotEqual(refused["error"]["code"], "ok")
                self.assertIsNone(service.active())
                self.assertEqual(configuration_repository.list_revisions(), ())

                status, active = publish_document(api, document)
                self.assertEqual(status, 200)
                self.assertEqual(active["status"], "active")
                self.assertTrue(active["published"])
                revision_id = active["revisionId"]
                status, job = submit_organize_job(api)
                self.assertEqual(status, 200)
                self.assertEqual(job["configuration_snapshot_id"], revision_id)
                self.assertEqual(job["configuration_snapshot_digest"], active["digest"])
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        for revision in configuration_repository.list_revisions()
                    )
                )

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

    def test_paged_command_audits_use_the_ledger_sequence_as_a_real_cursor(self) -> None:
        """The targeted reader pages by the ledger's own monotonic sequence.

        This is the exact root cause B named: reconciliation pages the durable
        audit trail and needs a *usable* cursor on the real domain object, so
        the reader must return the stored sequence and page strictly downward
        without repeating or skipping a row. The stored ``occurred_at`` values
        are deliberately made to disagree with insertion order, so a page
        ordered by wall-clock time would drop rows while a sequence-ordered
        cursor still walks the whole trail.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = example_document()
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                revisions = [service.import_draft(document, actor="tester") for _ in range(6)]
                # Invert wall-clock order relative to insertion order, keeping
                # the monotonically increasing sequences untouched.
                rows = repository._connection.execute(
                    "SELECT sequence FROM configuration_change_audits "
                    "WHERE action='draft_import' ORDER BY sequence"
                ).fetchall()
                sequences_in_order = [int(row["sequence"]) for row in rows]
                self.assertEqual(len(sequences_in_order), len(revisions))
                for position, sequence in enumerate(sequences_in_order):
                    repository._connection.execute(
                        "UPDATE configuration_change_audits SET occurred_at=? WHERE sequence=?",
                        (
                            datetime(2020, 1, 1, tzinfo=UTC)
                            .replace(second=len(sequences_in_order) - position)
                            .isoformat(),
                            sequence,
                        ),
                    )
                repository._connection.commit()
                # Every row carries the real stored cursor, newest-first.
                page = repository.list_command_audits_before(
                    ("draft_import",),
                    before_sequence=repository.latest_command_audit_sequence() + 1,
                    limit=3,
                )
                self.assertEqual(len(page), 3)
                sequences = [audit.sequence for audit in page]
                self.assertTrue(all(isinstance(item, int) for item in sequences))
                self.assertEqual(sequences, sorted(sequences, reverse=True))
                # The newest sequence is the one anchored highest, independent
                # of the inverted wall-clock values.
                self.assertEqual(sequences[0], max(sequences_in_order))
                # Paging strictly below the previous page's lowest sequence
                # reaches the remaining rows with no gap and no repeat.
                rest: list = []
                marker = min(sequences)
                while True:
                    following = repository.list_command_audits_before(
                        ("draft_import",), before_sequence=marker, limit=3
                    )
                    if not following:
                        break
                    rest.extend(following)
                    marker = min(
                        audit.sequence for audit in following if audit.sequence is not None
                    )
                collected = [audit.audit_id for audit in page] + [audit.audit_id for audit in rest]
                self.assertEqual(len(collected), len(set(collected)))
                self.assertEqual(
                    set(collected),
                    {
                        audit.audit_id
                        for audit in repository.list_command_audits_before(
                            ("draft_import",),
                            before_sequence=repository.latest_command_audit_sequence() + 1,
                            limit=500,
                        )
                    },
                )
                self.assertEqual(len(collected), len(revisions))

    def test_missing_active_keeps_configuration_recovery_available_but_blocks_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = set_local_roots(example_document(), root)
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
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, body = request(api, "/api/configuration")
                self.assertEqual(status, 200)
                self.assertEqual(body["health"], "UNAVAILABLE")
                status, readiness = request(api, "/api/management/readiness")
                self.assertEqual(status, 200)
                self.assertEqual(readiness["health"], "UNAVAILABLE")
                self.assertTrue(readiness["recoveryRequired"])
                self.assertIsNone(readiness["active"])
                self.assertEqual(
                    readiness["lastKnownActive"]["revisionId"],
                    active.revision_id,
                )
                self.assertEqual(readiness["lastKnownActive"]["digest"], active.digest)
                replacement = json.loads(json.dumps(document))
                replacement["historyPath"] = str(root / "replacement.jsonl")
                status, job = submit_organize_job(api)
                self.assertEqual(status, 503)
                self.assertEqual(job["error"]["code"], "configuration_unavailable")
                self.assertEqual(
                    job["error"]["details"]["durableState"], "managed_active_unavailable"
                )
                self.assertEqual(job["error"]["details"]["sideEffects"], "none")
                self.assertTrue(job["error"]["details"]["retrySafe"])
                status, replacement_active = publish_document(api, replacement, replace=True)
                self.assertEqual(status, 200)
                self.assertEqual(replacement_active["status"], "active")
                self.assertTrue(replacement_active["published"])
                self.assertEqual(service.active().revision_id, replacement_active["revisionId"])
                status, recovered_job = submit_organize_job(api)
                self.assertEqual(status, 200)
                self.assertEqual(
                    recovered_job["configuration_snapshot_id"],
                    replacement_active["revisionId"],
                )

    def test_runtime_invalid_active_repeated_job_requests_remain_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = set_local_roots(example_document(), root)
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
                    status, body = submit_organize_job(api)
                    self.assertEqual(status, 503)
                    self.assertEqual(body["error"]["code"], "configuration_unavailable")
                    self.assertEqual(body["error"]["details"]["revisionId"], active.revision_id)
                    self.assertEqual(body["error"]["details"]["digest"], digest)
                    self.assertEqual(
                        body["error"]["details"]["durableState"], "managed_active_unavailable"
                    )
                    self.assertEqual(body["error"]["details"]["sideEffects"], "none")
                    self.assertTrue(body["error"]["details"]["retrySafe"])
                self.assertEqual(task_repository.list_tasks(), ())
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
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=str(runtime),
                    ),
                    bootstrap_document=document,
                )
                status, details = request(api, "/api/configuration")
                self.assertEqual(status, 200)
                self.assertEqual(details["health"], "UNAVAILABLE")
                status, body = submit_organize_job(api)
                self.assertEqual(status, 503)
                self.assertEqual(body["error"]["details"]["reason"], "schema_unsupported")
                self.assertEqual(task_repository.list_tasks(), ())

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
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=str(runtime),
                    ),
                    bootstrap_document=document,
                )
                status, details = request(api, "/api/configuration")
                self.assertEqual(status, 200)
                self.assertEqual(details["health"], "UNAVAILABLE")
                status, body = submit_organize_job(api)
                self.assertEqual(status, 503)
                self.assertEqual(body["error"]["details"]["reason"], "digest_corrupt")
                self.assertEqual(task_repository.list_tasks(), ())

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
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=str(runtime),
                    ),
                    bootstrap_document=document,
                )
                status, body = submit_organize_job(api)
                self.assertEqual(status, 503)
                self.assertEqual(body["error"]["details"]["reason"], "runtime_invalid")
                self.assertEqual(task_repository.list_tasks(), ())

    def test_api_stale_publish_returns_structured_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = set_local_roots(example_document(), root)
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            with (
                SQLiteConfigurationRepository(root / "runtime.sqlite3") as configuration_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=document["persistence"]["databasePath"],
                )
                api = MediaFlowApi(
                    runtime_repository,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document=document,
                )
                status, first = publish_document(api, document)
                self.assertEqual(status, 200)
                first_active = service.require(first["revisionId"])
                status, second = publish_document(
                    api,
                    {**document, "historyPath": str(root / "first-history.jsonl")},
                    expected=first_active,
                )
                self.assertEqual(status, 200)
                second_active = service.require(second["revisionId"])
                status, conflict = publish_document(
                    api,
                    {**document, "historyPath": str(root / "stale.jsonl")},
                    expected=first_active,
                )
                self.assertEqual(status, 409)
                self.assertEqual(conflict["error"]["code"], "configuration_version_conflict")
                self.assertEqual(
                    conflict["error"]["details"]["revisionId"], second_active.revision_id
                )
                self.assertEqual(conflict["error"]["details"]["durableState"], "active_preserved")
                self.assertEqual(service.active().revision_id, second_active.revision_id)
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        for revision in configuration_repository.list_revisions()
                    )
                )

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
                self.configuration_result = request(self.app, "/api/configuration")
                self.job_result = submit_organize_job(self.app)
                replacement = json.loads(self.replacement_document)
                self.activation_result = publish_document(self.app, replacement, replace=True)
                self.assertions.append(self.activation_result)
                self.replacement_job_result = submit_organize_job(self.app)
                self.second_replacement_job_result = submit_organize_job(self.app)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.sqlite3"
            document = set_local_roots(example_document(), root)
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
                        "api": {
                            "principals": [
                                {
                                    "id": "admin",
                                    "tokenEnv": "MEDIAFLOW_API_TOKEN",
                                    "roles": ["admin"],
                                }
                            ]
                        },
                        "staleWorkflowContent": {"invalid": True},
                    }
                ),
                encoding="utf-8",
            )
            server = Server()
            replacement_document = json.loads(json.dumps(document))
            replacement_document.pop("api", None)
            replacement_document["automation"]["maximumActiveJobs"] = 2
            server.replacement_document = json.dumps(replacement_document)
            server.assertions = []

            def make_server(host, port, app):
                server.app = app
                return server

            with (
                patch.dict("os.environ", {"MEDIAFLOW_API_TOKEN": "admin-token"}, clear=True),
                patch("wsgiref.simple_server.make_server", side_effect=make_server),
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
            self.assertEqual(server.assertions[0][0], 200, server.assertions[0][1])
            self.assertEqual(server.activation_result[0], 200, server.activation_result[1])
            self.assertEqual(server.activation_result[1]["status"], "active")
            self.assertTrue(server.activation_result[1]["published"])
            self.assertEqual(server.replacement_job_result[0], 200)
            self.assertEqual(server.second_replacement_job_result[0], 200)
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
            lifecycle = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def serve_forever(self):
                status, refused = publish_document(self.app, self.invalid_document)
                self.lifecycle.append((status, "rejected"))
                if refused.get("error", {}).get("code") == "ok":
                    raise AssertionError(refused)
                status, active = publish_document(self.app, self.document)
                if status != 200 or "revisionId" not in active:
                    raise AssertionError((status, active))
                self.lifecycle.append((status, active.get("status")))
                self.active_result = (status, active)
                self.detail_result = request(
                    self.app,
                    f"/api/configuration/revisions/{active['revisionId']}",
                )
                self.job_result = submit_organize_job(self.app)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            (source_root / "电影").mkdir(parents=True)
            target_root.mkdir()
            (target_root / "Movies").mkdir()
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
                    [(400, "rejected"), (200, "active")],
                )
                self.assertEqual(server.detail_result[0], 200)
                self.assertEqual(server.detail_result[1]["status"], "active")
                self.assertEqual(server.active_result[0], 200, server.active_result[1])
                self.assertTrue(server.active_result[1]["published"])
                self.assertEqual(server.job_result[0], 200, server.job_result[1])
                task_id = server.job_result[1]["task_id"]
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
                task = repository.get_task(task_id)
                self.assertIsNotNone(task)
                self.assertEqual(task.status.value, "completed")
                self.assertEqual(task.configuration_snapshot_id, active_id)
                self.assertEqual(task.configuration_snapshot_digest, active_digest)
                results = repository.list_results(task.task_id)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].task_id, task.task_id)
                self.assertEqual(results[0].item_id, repository.list_items(task.task_id)[0].item_id)
                self.assertEqual(results[0].status, "success")

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
                # First setup activates the empty baseline; enabled automation is
                # introduced by a later successor under the current principal.
                baseline_document = json.loads(json.dumps(document))
                baseline_document["automationTaskDefinitions"] = []
                activate_document(managed, baseline_document, actor="local-admin")
                # Publish as the real configured remote principal so the
                # Worker proves the publisher's current permission instead of
                # mistaking a trusted local publication for that proof.
                managed.bind_automation_publication_authority(
                    _ConfiguredPermissionAuthority(lambda: _configuration(str(config)))
                )
                active = activate_document(managed, document, actor="local-admin")
            pinned = _configuration(
                str(config),
                snapshot_id=active.revision_id,
                snapshot_digest=active.digest,
            )
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
                    automation_task_definitions=pinned.automation_task_definitions,
                    configuration_snapshot_id=pinned.configuration_snapshot_id,
                    configuration_snapshot_digest=pinned.configuration_snapshot_digest,
                    configuration_snapshot_version=pinned.configuration_snapshot_version,
                ).tick(now)
                self.assertEqual(len(emitted), 1)

                original_execute = OrganizerExecutor.execute
                effect_calls = []

                def execute_and_disable(executor, plan, storages, **kwargs):
                    result = original_execute(executor, plan, storages, **kwargs)
                    if result.status.value.lower() == "success":
                        effect_calls.append(plan.plan_id)
                        if len(effect_calls) == 1:
                            disable_current_principal()
                    return result

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
                    output, error = io.StringIO(), io.StringIO()
                    status = final_main(
                        ["--config", str(config), "worker", "run-next"],
                        stdout=output,
                        stderr=error,
                    )
                self.assertEqual(status, 0, (output.getvalue(), error.getvalue()))
                task = repository.get_task(emitted[0].task_id)
                # Slice 48 RO-1: the file failure stays on its item; the
                # flow completed.
                self.assertEqual(task.status, PersistentTaskStatus.COMPLETED)
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
                # A settled Task is never replayed by a later Worker pass.
                output, error = io.StringIO(), io.StringIO()
                status = final_main(
                    ["--config", str(config), "worker", "run-next"],
                    stdout=output,
                    stderr=error,
                )
                self.assertEqual(status, 0)
                self.assertIn("No pending work", output.getvalue())
                self.assertEqual(len(effect_calls), 1)

    def test_checked_local_setup_organize_keeps_original_pin_after_second_activation(
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
                status, active = publish_document(self.app, document)
                if status != 200 or active["status"] != "active":
                    raise AssertionError((status, active))
                return active, active

            def serve_forever(self):
                self.first_check, self.first_active = self.checked_activate(self.first_document)
                status, self.first_job = submit_organize_job(self.app)
                if status != 200:
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
                task_id = self.first_job["task_id"]
                status, self.task_detail = request(
                    self.app,
                    f"/api/tasks/{task_id}",
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
                "Movies/Movies/Anime/Example Movie (2024) [tmdbid-4242]/Example Movie (2024).mkv"
            )
            second_destination = (
                "Movies/Movies/Later Active Only/Example Movie (2024) [tmdbid-4242]/"
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
                self.assertEqual(server.first_check["digest"], first_digest)
                self.assertEqual(server.second_check["revisionId"], second_id)
                self.assertEqual(server.first_job["configuration_snapshot_id"], first_id)
                self.assertEqual(server.first_job["configuration_snapshot_digest"], first_digest)
                self.assertEqual(
                    first_document["classificationPolicies"][0]["rules"][0]["result"]["path"],
                    ["Movies", "Anime"],
                )
                self.assertEqual(
                    second_document["classificationPolicies"][0]["rules"][0]["result"]["path"],
                    ["Later Active Only"],
                )

                with SQLiteTaskRepository(runtime) as repository:
                    stored_task = repository.get_task(server.task_detail["task_id"])
                self.assertIsNotNone(stored_task)
                self.assertEqual(stored_task.status.value, "completed")
                self.assertEqual(stored_task.configuration_snapshot_id, first_id)
                self.assertEqual(stored_task.configuration_snapshot_digest, first_digest)
                self.assertTrue(stored_task.execute_authorized)
                self.assertEqual(server.task_detail["configuration_snapshot_id"], first_id)
                self.assertTrue(server.task_detail["execute_authorized"])
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
                self.assertEqual(result["status"], "success")
                self.assertEqual(result["recognition_type"], "A")
                self.assertEqual(result["title"], "Example Movie")
                self.assertEqual(result["classification_policy_id"], "A")
                self.assertEqual(result["destination_path"], first_destination)
                self.assertNotEqual(result["destination_path"], second_destination)
                self.assertEqual(result["task_id"], stored_task.task_id)
                self.assertEqual(
                    result["item_id"],
                    server.task_detail["items"][0]["item_id"],
                )

            # The organized file landed at the pin the Job was admitted under,
            # not at the newer Active revision.
            self.assertNotEqual(
                (directory_state(source_root), directory_state(target_root)),
                before,
            )
            with SQLiteConfigurationRepository(runtime) as configuration_repository:
                current = configuration_repository.get_active_revision()
                self.assertIsNotNone(current)
                self.assertEqual(current.revision_id, second_id)

    def test_worker_claim_bootstrap_uses_locator_before_any_task_is_claimed(self) -> None:
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
            self.assertIn("No pending work", output.getvalue())

    def test_worker_reports_actionable_saved_revision_failures_without_media_io(self) -> None:
        cases = {
            "missing": "snapshot_missing",
            "digest-corrupt": "digest_corrupt",
            "payload-unreadable": "snapshot_unreadable",
            "schema-unsupported": "schema_unsupported",
            # A Task's admitted pin cannot be repinned to an altered payload:
            # the changed revision is refused as a pin digest mismatch even
            # though its own payload/hash pair is internally consistent.
            "runtime-invalid": "snapshot_digest_mismatch",
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
                    from mediaflow.application.task_scheduling import TaskSchedulingService
                    from mediaflow.domain.task_persistence import RunDisplayContext
                    from mediaflow.domain.task_scheduling import TaskTrigger

                    queued = (
                        TaskSchedulingService(task_repository, capacity=10)
                        .admit(
                            "organize",
                            execute_authorized=True,
                            trigger=TaskTrigger.MANUAL,
                            principal="remote-execution",
                            scope_path="Media",
                            configuration_snapshot_id=first.revision_id,
                            configuration_snapshot_digest=first.digest,
                            require_configuration_snapshot=True,
                            display=RunDisplayContext(
                                source_scope="Media", origin_kind="direct-organize"
                            ),
                        )
                        .task
                    )
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
                            # The admitted Task's pin and the stored revision
                            # keep the same digest; the payload itself is what
                            # fails runtime validation.
                            expected_pin_digest = first.digest
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
                    finished = task_repository.get_task(queued.task_id)
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
                    self.assertIsNotNone(finished.error)
                    self.assertIn(expected_category, finished.error)
                    self.assertIn("saved_configuration_unavailable", finished.error)
                    self.assertIn("restore", finished.error)
                    self.assertEqual(task_repository.list_items(queued.task_id), ())
                    self.assertEqual(task_repository.list_results(queued.task_id), ())
                    api = MediaFlowApi(
                        task_repository,
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
                    api_status, api_task = request(
                        api,
                        f"/api/tasks/{queued.task_id}",
                    )
                    self.assertEqual(api_status, 200, api_task)
                    failure = api_task["failure"]
                    self.assertEqual(failure["category"], expected_category)
                    self.assertEqual(api_task["status"], "failed")

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
                current = [("first", "a" * 64)]
                definition = AutomationTaskDefinition(
                    "test",
                    "Test",
                    "library",
                    None,
                    AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                    1,
                    None,
                    None,
                    5,
                    True,
                )
                scheduler = IntervalScheduler(
                    repository,
                    automation_task_definitions=(definition,),
                    configuration_snapshot_resolver=lambda: current[0],
                )
                first = scheduler.tick(datetime.now(UTC))
                self.assertEqual(first[0].configuration_snapshot_id, "first")
                current[0] = ("second", "b" * 64)
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
                definition = AutomationTaskDefinition(
                    "test",
                    "Test",
                    "library",
                    None,
                    AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                    60,
                    None,
                    None,
                    5,
                    True,
                )
                current = [
                    SchedulerConfigurationSnapshot("revision-a", "a" * 64, 10, (definition,))
                ]

                def resolve():
                    if current[0] is None:
                        raise RuntimeError("unavailable snapshot")
                    return current[0]

                scheduler = IntervalScheduler(
                    repository,
                    automation_task_definitions=(definition,),
                    configuration_snapshot_resolver=resolve,
                )
                now = datetime.now(UTC)
                emitted = scheduler.tick(now)
                self.assertEqual(len(emitted), 1)
                state_before = repository.get_automation_definition_due_state("test")
                self.assertIsNotNone(state_before)
                # A definition-backed scheduler has known definitions to record
                # the blocked reason on, so the tick fails closed without
                # raising and without emitting.
                current[0] = None
                self.assertEqual(scheduler.tick(now + timedelta(seconds=61)), ())
                self.assertEqual(
                    [item.task_id for item in repository.list_tasks()],
                    [emitted[0].task_id],
                )
                self.assertEqual(
                    repository.get_automation_definition_due_state("test").next_run_at,
                    state_before.next_run_at,
                )
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
                    "organize", execute_authorized=False
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
                        "organize",
                        execute_authorized=False,
                        require_configuration_snapshot=True,
                    )
                with self.assertRaisesRegex(ValueError, "provided together"):
                    coordinator.create(
                        "organize",
                        execute_authorized=False,
                        configuration_snapshot_id="revision-a",
                    )
            finally:
                repository.close()


if __name__ == "__main__":
    unittest.main()
