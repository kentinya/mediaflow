"""V2 Web-native manual Organize journey: admission, Worker execution, outcomes.

This module drives the real ``MediaFlowApi`` over a real managed runtime, real
``LocalStorage`` roots, scanner-produced FileIndex records, the real manual
intent/Preview/execution services and the real admitted-execution Worker.  It
proves the Slice 33 manual Organize journey end to end:

``GET  /api/v1/operations/manual-actions``
``POST /api/v1/operations/organize/intents``
``GET  /api/v1/operations/organize/intents/{intentId}``
``POST /api/v1/operations/organize/intents/{intentId}/items/{itemId}/choice``
``POST /api/v1/operations/organize/intents/{intentId}/previews``
``GET  /api/v1/operations/organize/previews/{previewId}``
``POST /api/v1/operations/organize/previews/{previewId}/execute``
``GET  /api/v1/operations/organize/executions/{executionId}``

Every assertion is about durable behavior: no Storage mutation happens before
admission, only the Processing Worker executes admitted work, exactly one
execution exists per reviewed selection, a source that changed after admission
fails without mutation and nothing is replayed automatically.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import copyfile
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from mediaflow.application.automation import ProcessingWorkerService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_organize_worker import ManualOrganizeExecutionWorker
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.manual_execution import (
    MANUAL_EXECUTION_PERMISSION,
    ManualExecutionStatus,
)
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.organizer import (
    ConflictStrategy,
    OrganizeOperationType,
    RollbackPolicy,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import ConfirmationStatus, ConflictConfirmation
from mediaflow.infrastructure.configuration_snapshot import build_configuration_snapshot
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    StorageDefinition,
    with_managed_snapshot,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document
from tests.test_manual_organize_preview import manual_snapshot

SNAPSHOT_ID = "active-1"
SNAPSHOT_DIGEST = "a" * 64
NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
OPERATOR_TOKEN = "operator-token"
OPERATOR_2_TOKEN = "operator-two-token"
VIEWER_TOKEN = "viewer-token"
MANAGER_TOKEN = "manager-token"

_FORBIDDEN_DOCUMENT_SUBSTRINGS = (
    "Bearer ",
    "fingerprint",
    "digest",
    "occurrenceId",
    "executionPlan",
    "/tmp/",
    "smb://",
    "http://",
    "https://",
    "one-time",
)


class RecordingStorage:
    """LocalStorage passthrough that records every mutating call.

    The journey must prove that the read-only stages never mutate Storage and
    that the Worker path goes through ``OrganizerExecutor``.
    """

    def __init__(self, storage, *, can_hard_link: bool | None = None) -> None:
        self._storage = storage
        self._can_hard_link = can_hard_link
        self.mutations: list[str] = []

    @property
    def storage_id(self):
        return self._storage.storage_id

    @property
    def name(self):
        return self._storage.name

    @property
    def read_only(self):
        return self._storage.read_only

    @property
    def capabilities(self):
        capabilities = self._storage.capabilities
        if self._can_hard_link is None:
            return capabilities
        return replace(capabilities, can_hard_link=self._can_hard_link)

    def __getattr__(self, name):
        return getattr(self._storage, name)

    def _record(self, operation: str, method, *args, **kwargs):
        self.mutations.append(operation)
        return method(*args, **kwargs)

    def write(self, *args, **kwargs):
        return self._record("write", self._storage.write, *args, **kwargs)

    def create_directory(self, *args, **kwargs):
        return self._record("create_directory", self._storage.create_directory, *args, **kwargs)

    def move(self, *args, **kwargs):
        return self._record("move", self._storage.move, *args, **kwargs)

    def copy(self, *args, **kwargs):
        return self._record("copy", self._storage.copy, *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._record("delete", self._storage.delete, *args, **kwargs)

    def hard_link(self, *args, **kwargs):
        return self._record("hard_link", self._storage.hard_link, *args, **kwargs)

    def soft_link(self, *args, **kwargs):
        return self._record("soft_link", self._storage.soft_link, *args, **kwargs)


class _JourneyFixtureMixin:
    """Shared full-journey fixture used by both regression suites."""

    maxDiff = None

    # --- fixture -----------------------------------------------------------

    @contextmanager
    def journey(
        self,
        *,
        names: tuple[str, ...] = ("One.2001.mkv",),
        target_files: tuple[str, ...] = (),
        operation: OrganizeOperationType = OrganizeOperationType.MOVE,
        conflict_strategy: ConflictStrategy = ConflictStrategy.MANUAL,
        target_hard_link: bool | None = None,
        register_worker: bool = True,
    ):
        with self._journey_environment(
            names=names,
            target_files=target_files,
            operation=operation,
            conflict_strategy=conflict_strategy,
            target_hard_link=target_hard_link,
            register_worker=register_worker,
        ) as value:
            try:
                yield value
            finally:
                value.repository.close()

    @contextmanager
    def _journey_environment(
        self,
        *,
        names,
        target_files,
        operation,
        conflict_strategy,
        target_hard_link,
        register_worker,
    ):
        """Build the whole journey graph; the caller owns the repository."""

        with (
            tempfile.TemporaryDirectory() as source_directory,
            tempfile.TemporaryDirectory() as target_directory,
            tempfile.TemporaryDirectory() as runtime_directory,
        ):
            source_root = Path(source_directory)
            target_root = Path(target_directory)
            candidates = []
            for position, name in enumerate(names, start=1):
                path = Path(name)
                (source_root / path).parent.mkdir(parents=True, exist_ok=True)
                (source_root / path).write_bytes((name.encode() + b"x" * 200)[:123])
                candidates.append(
                    MediaCandidate(
                        "tmdb",
                        str(100 + position),
                        MediaType.MOVIE,
                        path.stem.split(".", 1)[0],
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    )
                )
            for name in target_files:
                target_path = target_root / Path(name)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(b"existing-destination")

            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            library = ResourceLibrary("library", "Library", "source", "", exclude_rules=())

            def scan_clock() -> datetime:
                return datetime.now(UTC) + timedelta(hours=2)

            index = InMemoryFileIndexRepository()
            scan = StorageScanner({"source": source_storage}, index, clock=scan_clock).scan(library)
            self.assertEqual("completed", scan.status.value)

            strategy = development_strategy_configuration()
            type_policies = list(strategy.recognition_type_policies)
            c_index = next(
                position
                for position, value in enumerate(type_policies)
                if value.recognition_type_id == "C"
            )
            c_policy = type_policies[c_index]
            type_policies[c_index] = replace(
                c_policy,
                organize_policy=replace(
                    c_policy.organize_policy,
                    operation=operation,
                    conflict_strategy=conflict_strategy,
                    rollback=RollbackPolicy(False, True),
                ),
            )
            strategy = replace(strategy, recognition_type_policies=tuple(type_policies))

            configuration = RuntimeConfiguration(
                strategy,
                (
                    StorageDefinition("source", "local", str(source_root), "Source"),
                    StorageDefinition("target", "local", str(target_root), "Target"),
                ),
                (library,),
                (),
                (MediaLibrary("movies", "Movies", "target", "Movies"),),
                str(Path(runtime_directory, "history.jsonl")),
                str(Path(runtime_directory, "runtime.sqlite3")),
            )
            configuration = with_managed_snapshot(
                configuration, snapshot_id=SNAPSHOT_ID, digest=SNAPSHOT_DIGEST
            )
            provider = SyntheticMetadataProvider(tuple(candidates))
            source = RecordingStorage(source_storage)
            target = RecordingStorage(target_storage, can_hard_link=target_hard_link)
            repository = SQLiteTaskRepository(Path(runtime_directory, "runtime.sqlite3"))
            catalog = FileCatalogService(
                index,
                ("library",),
                ("source",),
                task_repository=repository,
            )
            intents = ManualOrganizeIntentService(
                repository,
                catalog,
                configuration_resolver=manual_snapshot,
                runtime_resolver=lambda snapshot_id, digest: configuration,
                storage_factory=lambda runtime, ids: runtime.create_storages(
                    external={"source": source, "target": target}, storage_ids=ids
                ),
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                catalog,
                configuration=configuration,
                file_index=index,
                providers=MetadataProviderRegistry((provider,)),
                storages={"source": source, "target": target},
            )
            execution = ManualOrganizeExecutionService(
                repository,
                previews,
                intents,
                checkpoint_service=ProcessingCheckpointService(repository),
                storages={"source": source, "target": target},
            )
            worker = ManualOrganizeExecutionWorker(
                execution, worker_id="worker-1", notice=lambda line: None
            )
            worker_service = ProcessingWorkerService(repository)
            if register_worker:
                worker_service.register_worker(
                    "worker-1",
                    "worker one",
                    10.0,
                    ("scan", "preview", "organize"),
                    configuration_snapshot_id=SNAPSHOT_ID,
                    configuration_snapshot_digest=SNAPSHOT_DIGEST,
                    runtime_schema_version=SCHEMA_VERSION,
                )
            api = MediaFlowApi(
                repository,
                None,
                principals=(
                    ResolvedApiPrincipal(
                        "operator",
                        OPERATOR_TOKEN,
                        frozenset(
                            {
                                ApiPermission.READ,
                                ApiPermission.SUBMIT_DRY_RUN,
                                ApiPermission.MANAGE_MANUAL_ORGANIZE,
                                ApiPermission.EXECUTE_MANUAL_ORGANIZE,
                            }
                        ),
                    ),
                    ResolvedApiPrincipal("viewer", VIEWER_TOKEN, frozenset({ApiPermission.READ})),
                    ResolvedApiPrincipal(
                        "manager",
                        MANAGER_TOKEN,
                        frozenset({ApiPermission.READ, ApiPermission.MANAGE_MANUAL_ORGANIZE}),
                    ),
                    ResolvedApiPrincipal(
                        "operator-two",
                        OPERATOR_2_TOKEN,
                        frozenset(
                            {
                                ApiPermission.READ,
                                ApiPermission.SUBMIT_DRY_RUN,
                                ApiPermission.MANAGE_MANUAL_ORGANIZE,
                                ApiPermission.EXECUTE_MANUAL_ORGANIZE,
                            }
                        ),
                    ),
                ),
                system_status=build_configuration_snapshot(configuration),
                file_catalog=catalog,
                file_index=index,
                configuration_snapshot_id=SNAPSHOT_ID,
                configuration_snapshot_digest=SNAPSHOT_DIGEST,
                manual_intent_service=intents,
                manual_preview_service=previews,
                manual_execution_service=execution,
                worker_service=worker_service,
            )
            file_ids = tuple(record.file_id for record in index.list_by_resource_library("library"))
            value = SimpleNamespace(
                api=api,
                repository=repository,
                intents=intents,
                previews=previews,
                execution=execution,
                worker=worker,
                worker_service=worker_service,
                configuration=configuration,
                index=index,
                catalog=catalog,
                source=source,
                target=target,
                source_root=source_root,
                target_root=target_root,
                runtime_path=Path(runtime_directory, "runtime.sqlite3"),
                file_ids=file_ids,
                file_id=file_ids[0] if file_ids else None,
            )
            yield value

    # --- shared API helpers -------------------------------------------------

    def _request(
        self,
        value,
        path: str,
        method: str = "GET",
        body: dict | None = None,
        *,
        token: str = OPERATOR_TOKEN,
    ) -> tuple[int, dict]:
        statuses: list[str] = []
        raw = json.dumps(body).encode() if body is not None else b""
        path_info, _, query_string = path.partition("?")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(raw)),
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": io.BytesIO(raw),
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        response = b"".join(value.api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(response)

    def _create_reviewed_intent(self, value):
        """Create one file-scoped intent and pin the RecognitionType C choices."""

        status, intent = self._request(
            value,
            "/api/v1/operations/organize/intents",
            "POST",
            {
                "scopeKind": "file",
                "fileId": value.file_id,
                "resourceLibraryId": "library",
            },
        )
        self.assertEqual(201, status, intent)
        item = intent["items"][0]
        status, intent = self._request(
            value,
            f"/api/v1/operations/organize/intents/{intent['intentId']}"
            f"/items/{item['itemId']}/choice",
            "POST",
            {
                "expectedVersion": intent["version"],
                "expectedItemVersion": item["version"],
                "recognitionTypeId": "C",
                "namingPolicyId": "A",
                "classificationPolicyId": "A",
                "organizePolicyId": "A",
            },
        )
        self.assertEqual(200, status, intent)
        self.assertEqual("C", intent["items"][0]["choice"]["recognitionTypeId"])
        return intent

    def _create_preview(self, value, intent):
        status, preview = self._request(
            value,
            f"/api/v1/operations/organize/intents/{intent['intentId']}/previews",
            "POST",
            {"expectedVersion": intent["version"]},
        )
        self.assertEqual(201, status, preview)
        return preview

    def _execute(self, value, preview, intent, *, token=OPERATOR_TOKEN, **overrides):
        body = {
            "confirmation": True,
            "itemIds": [item["itemId"] for item in preview["items"]],
            "expectedIntentVersion": intent["version"],
        }
        body.update(overrides)
        return self._request(
            value,
            f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
            "POST",
            body,
            token=token,
        )

    def _assert_secret_free(self, document: object, label: str) -> None:
        encoded = json.dumps(document)
        for forbidden in _FORBIDDEN_DOCUMENT_SUBSTRINGS:
            self.assertNotIn(forbidden, encoded, f"{label} leaked {forbidden!r}")
        self.assertNotIn("authorizationId", encoded, label)


class V2ManualOrganizeJourneyTests(_JourneyFixtureMixin, unittest.TestCase):
    # --- the journey -------------------------------------------------------

    def test_web_journey_admits_one_execution_and_the_worker_completes_it(self) -> None:
        with self.journey() as value:
            status, matrix = self._request(
                value,
                "/api/v1/operations/manual-actions"
                f"?scopeKind=file&fileId={value.file_id}&resourceLibraryId=library",
            )
            self.assertEqual(200, status)
            organize = matrix["actions"]["organize"]
            self.assertTrue(organize["available"], organize)
            self.assertEqual("/api/v1/operations/organize/intents", organize["path"])

            intent = self._create_reviewed_intent(value)
            self.assertEqual("organize", intent["journey"])
            self.assertTrue(intent["zeroMutation"])
            self.assertEqual("open", intent["status"])
            self.assertTrue(intent["actions"]["preview"]["available"], intent["actions"])
            self.assertTrue(intent["options"]["recognitionTypes"])
            self._assert_secret_free(intent, "intent")

            status, detail = self._request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}",
            )
            self.assertEqual(200, status)
            self.assertEqual(intent["version"], detail["version"])

            preview = self._create_preview(value, intent)
            self.assertEqual("previewed", preview["status"])
            self.assertTrue(preview["current"])
            self.assertTrue(preview["zeroMutation"])
            self.assertEqual([intent["items"][0]["itemId"]], preview["executionCandidateItemIds"])
            # RecognitionType C keeps its identity even though policies A/A are used.
            self.assertEqual("C", preview["items"][0]["plan"]["recognitionType"])
            self.assertTrue(preview["actions"]["execute"]["available"], preview["actions"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self._assert_secret_free(preview, "preview")

            status, execution = self._execute(value, preview, intent)
            self.assertEqual(202, status, execution)
            self.assertEqual("organize", execution["journey"])
            self.assertEqual("admitted", execution["status"])
            self.assertEqual("admitted", execution["durableState"])
            self.assertTrue(execution["taskId"])
            # Admission alone mutates nothing; the API request never runs the executor.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertTrue((value.source_root / "One.2001.mkv").exists())
            self._assert_secret_free(execution, "execution admission")

            # A repeated submission of the same reviewed work is the same execution.
            status, repeated = self._execute(value, preview, intent)
            self.assertIn(status, (200, 202), repeated)
            self.assertEqual(execution["executionId"], repeated["executionId"])
            self.assertEqual(
                1, len(value.repository.list_manual_executions_for_preview(preview["previewId"]))
            )

            completed = value.worker.run_next()
            self.assertIsNotNone(completed)
            self.assertEqual(ManualExecutionStatus.COMPLETED, completed.status)
            self.assertEqual(["delete"], value.source.mutations)
            self.assertTrue(value.target.mutations)
            self.assertFalse((value.source_root / "One.2001.mkv").exists())
            moved = list(value.target_root.rglob("*.mkv"))
            self.assertEqual(1, len(moved))
            self.assertTrue(moved[0].name.startswith("One (2001)"))

            status, outcome = self._request(
                value,
                f"/api/v1/operations/organize/executions/{execution['executionId']}",
            )
            self.assertEqual(200, status)
            self.assertEqual("completed", outcome["status"])
            self.assertEqual("completed", outcome["durableState"])
            self.assertEqual(1, outcome["knownEffects"]["verifiedItemCount"])
            item = outcome["items"][0]
            self.assertEqual("success", item["status"])
            self.assertEqual("verified_complete", item["effectCertainty"])
            self.assertTrue(item["resultId"])
            self.assertTrue(item["taskItemId"])
            self.assertFalse(outcome["actions"]["recovery"]["available"])
            self._assert_secret_free(outcome, "execution outcome")

            # No pending work remains and nothing is replayed.
            self.assertIsNone(value.worker.run_next())
            self.assertEqual(0, len(value.repository.list_jobs()))

    def test_choice_edits_are_optimistic_and_invalidate_prior_previews(self) -> None:
        with self.journey() as value:
            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            item = intent["items"][0]

            # A stale intent/item version is rejected atomically with no change.
            status, error = self._request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}"
                f"/items/{item['itemId']}/choice",
                "POST",
                {
                    "expectedVersion": 1,
                    "expectedItemVersion": 1,
                    "recognitionTypeId": "C",
                },
            )
            self.assertEqual(409, status)
            self.assertEqual("manual_intent_conflict", error["error"]["code"])
            self._assert_secret_free(error, "stale choice error")

            # A cross-intent item identity fails closed.
            status, error = self._request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}"
                "/items/unknown-item/choice",
                "POST",
                {"expectedVersion": intent["version"], "recognitionTypeId": "C"},
            )
            self.assertEqual(404, status)
            self.assertEqual("item_not_found", error["error"]["code"])

            # A real edit advances the item and intent versions and marks the
            # earlier Preview as no longer current evidence.
            status, edited = self._request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}"
                f"/items/{item['itemId']}/choice",
                "POST",
                {
                    "expectedVersion": intent["version"],
                    "expectedItemVersion": item["version"],
                    "recognitionTypeId": "A",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
            )
            self.assertEqual(200, status, edited)
            self.assertTrue(edited["previewRequired"])
            self.assertEqual("A", edited["items"][0]["choice"]["recognitionTypeId"])

            status, stale_preview = self._request(
                value,
                f"/api/v1/operations/organize/previews/{preview['previewId']}",
            )
            self.assertEqual(200, status)
            self.assertFalse(stale_preview["actions"]["execute"]["available"])
            status, error = self._execute(value, preview, intent)
            self.assertIn(status, (400, 409))
            self.assertEqual([], value.source.mutations)
            self.assertEqual(
                (), value.repository.list_manual_executions_for_preview(preview["previewId"])
            )

    def test_viewer_and_manager_without_execute_permission_render_no_control(self) -> None:
        with self.journey() as value:
            status, matrix = self._request(
                value,
                "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=library",
                token=VIEWER_TOKEN,
            )
            self.assertEqual(200, status)
            self.assertFalse(matrix["actions"]["organize"]["available"])
            self.assertIn("manage_manual_organize", matrix["actions"]["organize"]["reason"])
            # A viewer cannot even create the durable intent.
            status, error = self._request(
                value,
                "/api/v1/operations/organize/intents",
                "POST",
                {
                    "scopeKind": "file",
                    "fileId": value.file_id,
                    "resourceLibraryId": "library",
                },
                token=VIEWER_TOKEN,
            )
            self.assertEqual(403, status)

            # A manager may review and Preview but can never execute.
            status, matrix = self._request(
                value,
                "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=library",
                token=MANAGER_TOKEN,
            )
            self.assertEqual(200, status)
            self.assertFalse(matrix["actions"]["organize"]["available"])
            self.assertIn("execute_manual_organize", matrix["actions"]["organize"]["reason"])
            status, error = self._request(
                value,
                "/api/v1/operations/organize/intents",
                "POST",
                {
                    "scopeKind": "file",
                    "fileId": value.file_id,
                    "resourceLibraryId": "library",
                },
                token=MANAGER_TOKEN,
            )
            self.assertEqual(201, status)
            item = error["items"][0]
            status, error = self._request(
                value,
                f"/api/v1/operations/organize/intents/{error['intentId']}"
                f"/items/{item['itemId']}/choice",
                "POST",
                {
                    "expectedVersion": 1,
                    "expectedItemVersion": 1,
                    "recognitionTypeId": "C",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
                token=MANAGER_TOKEN,
            )
            self.assertEqual(200, status)
            status, preview = self._request(
                value,
                f"/api/v1/operations/organize/intents/{error['intentId']}/previews",
                "POST",
                {"expectedVersion": error["version"]},
                token=MANAGER_TOKEN,
            )
            self.assertEqual(201, status, preview)
            self.assertFalse(preview["actions"]["execute"]["available"])
            status, error = self._request(
                value,
                f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
                "POST",
                {
                    "confirmation": True,
                    "itemIds": [item["itemId"]],
                    "expectedIntentVersion": preview["intentVersion"],
                },
                token=MANAGER_TOKEN,
            )
            self.assertEqual(403, status)
            self.assertEqual(
                0, len(value.repository.list_manual_executions_for_preview(preview["previewId"]))
            )

    def test_malformed_authority_fields_are_rejected_before_any_durable_state(self) -> None:
        with self.journey() as value:
            for body in (
                {
                    "scopeKind": "file",
                    "fileId": value.file_id,
                    "resourceLibraryId": "library",
                    "sourceFingerprint": "0" * 64,
                },
                {
                    "scopeKind": "file",
                    "fileId": value.file_id,
                    "resourceLibraryId": "library",
                    "snapshotDigest": "0" * 64,
                },
                {
                    "scopeKind": "resourceLibrary",
                    "resourceLibraryId": "library",
                },
            ):
                status, error = self._request(
                    value, "/api/v1/operations/organize/intents", "POST", body
                )
                self.assertEqual(400, status, error)
            self.assertEqual((), value.repository.list_manual_intents())

            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            item_ids = [item["itemId"] for item in preview["items"]]
            for body in (
                {"itemIds": item_ids, "expectedIntentVersion": intent["version"]},
                {
                    "confirmation": True,
                    "expectedIntentVersion": intent["version"],
                },
                {"confirmation": True, "itemIds": item_ids},
                {
                    "confirmation": True,
                    "itemIds": item_ids,
                    "expectedIntentVersion": intent["version"],
                    "authorizationId": "browser-supplied",
                },
                {
                    "confirmation": True,
                    "itemIds": item_ids,
                    "expectedIntentVersion": intent["version"],
                    "allowOverwrite": "yes",
                },
            ):
                status, error = self._request(
                    value,
                    f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
                    "POST",
                    body,
                )
                self.assertEqual(400, status, error)
            self.assertEqual(
                0, len(value.repository.list_manual_executions_for_preview(preview["previewId"]))
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_worker_claim_is_single_owner_and_never_replays_started_work(self) -> None:
        with self.journey() as value:
            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            status, execution = self._execute(value, preview, intent)
            self.assertEqual(202, status, execution)
            execution_id = execution["executionId"]

            # Another Worker cannot steal a live claim.
            reader = value.repository
            self.assertIsNotNone(
                reader.claim_next_manual_execution(
                    datetime.now(UTC),
                    worker_id="worker-2",
                    claim_token="token-two",
                    lease_seconds=60.0,
                )
            )
            self.assertIsNone(
                reader.claim_next_manual_execution(
                    datetime.now(UTC),
                    worker_id="worker-3",
                    claim_token="token-three",
                    lease_seconds=60.0,
                )
            )
            self.assertIsNone(value.worker.run_next())
            self.assertEqual([], value.source.mutations)

            # Once the running boundary is published the execution is never
            # claimable again, even after a Worker restart.
            self.assertTrue(
                reader.begin_manual_execution(execution_id, "token-two", datetime.now(UTC))
            )
            self.assertIsNone(
                reader.claim_next_manual_execution(
                    datetime.now(UTC) + timedelta(days=1),
                    worker_id="worker-3",
                    claim_token="token-three",
                    lease_seconds=60.0,
                )
            )
            self.assertIsNone(value.worker.run_next())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_worker_uses_preview_storage_identity_without_file_index_relookup(self) -> None:
        with self.journey() as value:
            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)

            with (
                patch.object(
                    value.index,
                    "find_by_file_id",
                    side_effect=AssertionError("execution must not resolve through FileIndex"),
                ),
                patch.object(
                    value.index,
                    "list_by_resource_library",
                    side_effect=AssertionError("execution must not list FileIndex"),
                ),
            ):
                status, execution = self._execute(value, preview, intent)
                self.assertEqual(202, status, execution)
                completed = value.worker.run_next()

            self.assertIsNotNone(completed)
            self.assertEqual(ManualExecutionStatus.COMPLETED, completed.status)
            self.assertIn("delete", value.source.mutations)
            self.assertIn("write", value.target.mutations)

    def test_pre_mutation_source_change_fails_the_item_without_mutation(self) -> None:
        with self.journey() as value:
            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            status, execution = self._execute(value, preview, intent)
            self.assertEqual(202, status, execution)

            # The reviewed source is replaced after admission.
            source_file = value.source_root / "One.2001.mkv"
            source_file.write_bytes(b"replaced-and-different" * 10)
            completed = value.worker.run_next()
            self.assertIsNotNone(completed)
            self.assertEqual(ManualExecutionStatus.FAILED, completed.status)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            item = completed.items[0]
            self.assertEqual("none", item.effect_certainty)
            self.assertEqual("failed", item.status.value)

            status, outcome = self._request(
                value,
                f"/api/v1/operations/organize/executions/{execution['executionId']}",
            )
            self.assertEqual(200, status)
            self.assertEqual("failed", outcome["status"])
            self.assertEqual(0, outcome["knownEffects"]["verifiedItemCount"])
            self.assertEqual(1, outcome["knownEffects"]["failedWithoutEffectCount"])
            self.assertIn("never", outcome["knownEffects"]["statement"])
            self.assertTrue(outcome["actions"]["recovery"]["available"])
            self._assert_secret_free(outcome, "rejected execution")

    def test_execute_action_withholds_itself_when_the_worker_is_unavailable(self) -> None:
        with self.journey(register_worker=False) as value:
            status, matrix = self._request(
                value,
                "/api/v1/operations/manual-actions"
                f"?scopeKind=file&fileId={value.file_id}&resourceLibraryId=library",
            )
            self.assertEqual(200, status)
            self.assertFalse(matrix["actions"]["organize"]["available"])
            self.assertIn("worker", matrix["actions"]["organize"]["reason"].lower())

            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            self.assertFalse(preview["actions"]["execute"]["available"])
            self.assertFalse(preview["worker"]["ready"])

    def test_recognition_type_c_is_preserved_in_the_executed_result(self) -> None:
        with self.journey() as value:
            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            status, execution = self._execute(value, preview, intent)
            self.assertEqual(202, status, execution)
            completed = value.worker.run_next()
            self.assertIsNotNone(completed)
            results = value.repository.list_results(completed.task_id)
            self.assertEqual(1, len(results))
            self.assertEqual("C", results[0].recognition_type)
            self.assertEqual("A", results[0].naming_policy_id)
            self.assertEqual("A", results[0].classification_policy_id)

    def test_overwrite_requires_explicit_separate_authority(self) -> None:
        with self.journey(
            names=("One.2001.mkv",),
            conflict_strategy=ConflictStrategy.OVERWRITE,
        ) as value:
            intent = self._create_reviewed_intent(value)
            first = self._create_preview(value, intent)
            raw = value.previews.get_readonly(first["previewId"])
            destination = raw.items[0].plan["destination"]["path"]
            collision = value.target_root / destination
            collision.parent.mkdir(parents=True, exist_ok=True)
            collision.write_bytes(b"existing-destination")

            # The un-resolved collision blocks the exact plan; it is not offered
            # as executable work and no authority broadens it.
            blocked = self._create_preview(value, intent)
            self.assertEqual([], blocked["executionCandidateItemIds"])
            self.assertFalse(blocked["actions"]["execute"]["available"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # A recorded explicit overwrite decision makes the fresh exact plan
            # executable, but the destructive effect still needs its own
            # separate confirmation before any mutation.
            raw = value.previews.get_readonly(blocked["previewId"])
            plan = raw.items[0].plan
            value.repository.create_confirmation(
                ConflictConfirmation(
                    str(uuid4()),
                    "conflict-task",
                    "conflict-item",
                    plan["planId"],
                    "DESTINATION_EXISTS",
                    "source",
                    plan["source"]["path"],
                    "target",
                    destination,
                    "overwrite",
                    ConfirmationStatus.RESOLVED,
                    NOW,
                    NOW,
                    selected_strategy="overwrite",
                    overwrite_authorized=True,
                    actor="operator",
                )
            )
            fresh = self._create_preview(value, intent)
            implications = fresh["items"][0]["plan"]["destructiveImplications"]
            self.assertTrue(implications["overwriteRequired"], implications)
            self.assertTrue(fresh["actions"]["execute"]["available"], fresh["actions"])

            # Without the explicit overwrite authority the exact work is refused
            # and nothing is admitted or mutated.
            status, error = self._execute(value, fresh, intent)
            self.assertEqual(409, status, error)
            self.assertEqual("overwrite_authority_required", error["error"]["code"], error)
            self.assertEqual(
                0, len(value.repository.list_manual_executions_for_preview(fresh["previewId"]))
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual(b"existing-destination", collision.read_bytes())

            status, execution = self._execute(value, fresh, intent, allowOverwrite=True)
            self.assertEqual(202, status, execution)
            self.assertTrue(execution["allowOverwrite"])
            completed = value.worker.run_next()
            self.assertIsNotNone(completed)
            self.assertEqual(ManualExecutionStatus.COMPLETED, completed.status)
            self.assertIn("delete", value.source.mutations)
            self.assertEqual(123, collision.stat().st_size)

    def test_link_operation_never_falls_back_to_copy_or_move(self) -> None:
        with self.journey(
            operation=OrganizeOperationType.HARD_LINK,
            target_hard_link=False,
        ) as value:
            intent = self._create_reviewed_intent(value)
            preview = self._create_preview(value, intent)
            capabilities = preview["items"][0]["plan"]["capabilities"]
            self.assertEqual("capability_gap", capabilities["verdict"], capabilities)
            self.assertTrue(capabilities["missing"], capabilities)
            self.assertEqual([], preview["executionCandidateItemIds"])
            self.assertFalse(preview["actions"]["execute"]["available"], preview["actions"])
            status, error = self._execute(value, preview, intent)
            self.assertGreaterEqual(status, 400)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual(
                (), value.repository.list_manual_executions_for_preview(preview["previewId"])
            )

    def test_v1_manual_routes_and_documents_remain_compatible(self) -> None:
        with self.journey() as value:
            status, body = self._request(
                value,
                f"/api/v1/files/{value.file_id}/manual-organize",
                "POST",
            )
            self.assertEqual(201, status, body)
            self.assertIn("intentId", body)
            status, preview = self._request(
                value,
                f"/api/v1/manual-intents/{body['intentId']}/preview",
                "POST",
                {"expectedVersion": body["version"]},
            )
            self.assertEqual(201, status, preview)
            status, dashboard = self._request(value, "/api/v1/dashboard")
            self.assertEqual(200, status)


class _ExactAdmissionMixin:
    """Shared reviewed-intent fixture for exact admission regressions."""

    def _reviewed_multi_item(self, value, names):
        """One ResourceLibrary-scoped intent over several reviewed files."""

        body = {
            "scopeKind": "resourceLibrary",
            "resourceLibraryId": "library",
            "itemIds": list(value.file_ids),
        }
        self.assertEqual(len(names), len(value.file_ids))
        status, intent = self._request(value, "/api/v1/operations/organize/intents", "POST", body)
        self.assertEqual(201, status, intent)
        self.assertEqual(len(names), len(intent["items"]))
        for item in intent["items"]:
            status, intent = self._request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}"
                f"/items/{item['itemId']}/choice",
                "POST",
                {
                    "expectedVersion": intent["version"],
                    "expectedItemVersion": item["version"],
                    "recognitionTypeId": "C",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
            )
            self.assertEqual(200, status, intent)
        return intent


class ExactAdmissionResolutionTests(_JourneyFixtureMixin, _ExactAdmissionMixin, unittest.TestCase):
    """Idempotent/concurrent admission resolves only exactly equivalent work.

    A repeated submission may only be folded into the existing durable
    execution when the principal, permission, intent/configuration binding,
    destructive authority and the *exact* selected item set all match.  A
    narrower, overlapping, differently authorized or different-principal
    request must fail with its own reason and never return unrelated work.
    """

    def _executions(self, value, preview_id):
        return value.repository.list_manual_executions_for_preview(preview_id)

    def test_exact_repeat_resolves_across_the_full_preview_bound(self) -> None:
        """An exact repeat resolves even past the newest few durable executions."""

        # MAX_ITEMS + 1 disjoint one-item admissions push the oldest execution
        # out of any bounded "newest few" read.
        names = tuple(f"Show{index}.2001.mkv" for index in range(1, 12))
        with self.journey(names=names) as value:
            self.assertGreater(len(value.file_ids), 10)
            intent = self._reviewed_multi_item(value, names)
            preview = self._create_preview(value, intent)
            self.assertEqual(len(names), len(preview["items"]))

            admitted_ids = []
            for item in preview["items"]:
                status, execution = self._execute(
                    value,
                    preview,
                    intent,
                    itemIds=[item["itemId"]],
                )
                self.assertEqual(202, status, execution)
                admitted_ids.append(execution["executionId"])
            self.assertEqual(len(set(admitted_ids)), len(admitted_ids))
            self.assertEqual(len(names), len(self._executions(value, preview["previewId"])))

            # The exact repeat of the *oldest* admission is the same reviewed
            # submission and must resolve to it, not be refused as a duplicate.
            oldest = admitted_ids[0]
            status, repeated = self._execute(
                value,
                preview,
                intent,
                itemIds=[preview["items"][0]["itemId"]],
            )
            self.assertIn(status, (200, 202), repeated)
            self.assertEqual(oldest, repeated["executionId"])
            self.assertEqual(len(names), len(self._executions(value, preview["previewId"])))

            # The repeat consumed only its own one-shot authority; no sibling
            # item was admitted a second time and nothing was mutated yet.
            for other in preview["items"][1:]:
                executions = [
                    candidate
                    for candidate in self._executions(value, preview["previewId"])
                    if other["itemId"] in candidate.selected_item_ids
                ]
                self.assertEqual(1, len(executions))
            self.assertEqual([], value.source.mutations)

            # Every disjoint execution still runs exactly once.
            for _ in range(len(names)):
                completed = value.worker.run_next()
                self.assertIsNotNone(completed)
            self.assertIsNone(value.worker.run_next())
            self.assertEqual(len(names), len(list(value.target_root.rglob("*.mkv"))))

    def test_repeated_same_submission_is_one_exact_execution(self) -> None:
        with self.journey(names=("One.2001.mkv", "Two.2002.mkv")) as value:
            intent = self._reviewed_multi_item(value, ("One", "Two"))
            preview = self._create_preview(value, intent)
            self.assertEqual(2, len(preview["items"]))

            status, first = self._execute(value, preview, intent)
            self.assertEqual(202, status, first)
            self.assertTrue(first["executionId"])
            status, repeated = self._execute(value, preview, intent)
            self.assertIn(status, (200, 202), repeated)
            self.assertEqual(first["executionId"], repeated["executionId"])
            self.assertEqual(1, len(self._executions(value, preview["previewId"])))

            # The Worker consumes the reviewed sources exactly once.
            completed = value.worker.run_next()
            self.assertEqual(ManualExecutionStatus.COMPLETED, completed.status)
            self.assertEqual(2, len(list(value.target_root.rglob("*.mkv"))))

            # After completion the reviewed sources no longer exist, so a
            # further submission is refused during revalidation and can never
            # admit a second execution for the same reviewed work.
            status, error = self._execute(value, preview, intent)
            self.assertGreaterEqual(status, 400, error)
            self.assertEqual(1, len(self._executions(value, preview["previewId"])))
            self.assertIsNone(value.worker.run_next())

    def test_narrower_selection_never_resolves_to_a_broader_execution(self) -> None:
        with self.journey(names=("One.2001.mkv", "Two.2002.mkv")) as value:
            intent = self._reviewed_multi_item(value, ("One", "Two"))
            preview = self._create_preview(value, intent)
            status, admitted = self._execute(value, preview, intent)
            self.assertEqual(202, status, admitted)
            self.assertEqual(2, len(admitted["selectedItemIds"]))

            # A subset of the reviewed selection is a different submission.
            status, error = self._execute(
                value,
                preview,
                intent,
                itemIds=[admitted["selectedItemIds"][0]],
            )
            self.assertEqual(409, status, error)
            self.assertIn(error["error"]["code"], {"duplicate_execution", "concurrent_execution"})
            self.assertEqual(1, len(self._executions(value, preview["previewId"])))
            self.assertEqual([], value.source.mutations)

    def test_overlapping_selection_never_resolves_to_an_unrelated_execution(self) -> None:
        with self.journey(names=("One.2001.mkv", "Two.2002.mkv")) as value:
            intent = self._reviewed_multi_item(value, ("One", "Two"))
            preview = self._create_preview(value, intent)
            status, admitted = self._execute(
                value, preview, intent, itemIds=[preview["items"][0]["itemId"]]
            )
            self.assertEqual(202, status, admitted)

            # Adding an unadmitted sibling overlaps, but is not equivalent.
            status, error = self._execute(value, preview, intent)
            self.assertEqual(409, status, error)
            self.assertEqual(1, len(self._executions(value, preview["previewId"])))
            self.assertEqual([], value.source.mutations)

    def test_different_principal_never_resolves_to_another_operator_execution(self) -> None:
        with self.journey(names=("One.2001.mkv", "Two.2002.mkv")) as value:
            intent = self._reviewed_multi_item(value, ("One", "Two"))
            preview = self._create_preview(value, intent)
            status, admitted = self._execute(value, preview, intent)
            self.assertEqual(202, status, admitted)
            self.assertEqual("operator", admitted["actor"])

            # The same reviewed work submitted by another principal is not this
            # operator's submission and must fail without returning it.
            status, error = self._execute(value, preview, intent, token=OPERATOR_2_TOKEN)
            self.assertEqual(409, status, error)
            self.assertEqual(1, len(self._executions(value, preview["previewId"])))
            self.assertEqual([], value.source.mutations)

    def test_differently_authorized_destructive_binding_never_resolves(self) -> None:
        with self.journey(names=("One.2001.mkv",)) as value:
            intent = self._reviewed_multi_item(value, ("One",))
            preview = self._create_preview(value, intent)
            status, admitted = self._execute(value, preview, intent)
            self.assertEqual(202, status, admitted)
            execution = self._executions(value, preview["previewId"])[0]
            self.assertFalse(execution.allow_overwrite)

            # A submission that carries broader destructive authority than the
            # reviewed plan is refused before admission, so it can never be
            # folded into the previously admitted, non-destructive execution.
            status, error = self._execute(value, preview, intent, allowOverwrite=True)
            self.assertEqual(409, status, error)
            self.assertEqual("scope_changed", error["error"]["code"], error)
            self.assertEqual(1, len(self._executions(value, preview["previewId"])))
            self.assertEqual([], value.source.mutations)

            # The persisted destructive binding stays narrow, so an exactly
            # repeated narrow submission still resolves to the same execution
            # while any broadened one cannot.
            status, repeated = self._execute(value, preview, intent)
            self.assertIn(status, (200, 202), repeated)
            self.assertEqual(admitted["executionId"], repeated["executionId"])
            self.assertEqual(1, len(self._executions(value, preview["previewId"])))

    def test_permission_binding_is_proved_from_the_persisted_authority(self) -> None:
        with self.journey(names=("One.2001.mkv",)) as value:
            intent = self._reviewed_multi_item(value, ("One",))
            preview = self._create_preview(value, intent)
            status, admitted = self._execute(value, preview, intent)
            self.assertEqual(202, status, admitted)
            existing = self._executions(value, preview["previewId"])[0]
            stored = value.repository.get_manual_execution_authorization(existing.authorization_id)
            self.assertEqual(MANUAL_EXECUTION_PERMISSION, stored.permission)
            self.assertEqual(existing.authorization_id, stored.authorization_id)
            self.assertEqual(stored.execution_id, existing.execution_id)
            # An execution without its persisted authority can never resolve.
            self.assertIsNone(
                value.execution._execution_authorization_for_replay(
                    replace(existing, authorization_id="missing")
                )
            )


class SchemaAndRestartRecoveryTests(_JourneyFixtureMixin, unittest.TestCase):
    """Copied-fixture migration proof and real repository/service reopen proof.

    The Worker-claim schema this Task added is additive, so an existing
    schema-33 database must migrate forward in one atomic step and preserve
    every already-admitted manual execution, while a newer schema and a failing
    migration are both refused without leaving a half-applied database.
    """

    _CLAIM_COLUMNS = (
        "worker_id",
        "claim_token",
        "claimed_at",
        "claim_expires_at",
        "attempts",
    )

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection

    def _downgraded_33_copy(self, source_path: Path, target_path: Path) -> None:
        """Copy a live runtime database and revert it to its schema-33 shape."""

        copyfile(source_path, target_path)
        connection = self._connect(target_path)
        try:
            for column in self._CLAIM_COLUMNS:
                connection.execute(f"ALTER TABLE manual_executions DROP COLUMN {column}")
            connection.execute(
                "UPDATE schema_version SET version=? WHERE component='runtime'", (33,)
            )
            connection.commit()
        finally:
            connection.close()

    def _admitted_execution(self, value) -> SimpleNamespace:
        intent = self._create_reviewed_intent(value)
        preview = self._create_preview(value, intent)
        status, execution = self._execute(value, preview, intent)
        self.assertEqual(202, status, execution)
        return SimpleNamespace(intent=intent, preview=preview, execution=execution, value=value)

    def test_schema_33_fixture_migrates_forward_with_existing_executions(self) -> None:
        with self.journey() as value:
            admitted = self._admitted_execution(value)
            execution_id = admitted.execution["executionId"]
            value.repository.close()

            with tempfile.TemporaryDirectory() as copy_directory:
                copy_path = Path(copy_directory, "schema33.sqlite3")
                self._downgraded_33_copy(value.runtime_path, copy_path)

                # The copied fixture really is the older schema.
                connection = self._connect(copy_path)
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(manual_executions)")
                }
                self.assertEqual(
                    33,
                    connection.execute(
                        "SELECT version FROM schema_version WHERE component='runtime'"
                    ).fetchone()[0],
                )
                self.assertFalse(columns & set(self._CLAIM_COLUMNS))
                connection.close()

                # Reopening migrates forward in place and preserves the work.
                repository = SQLiteTaskRepository(copy_path)
                try:
                    self.assertEqual(SCHEMA_VERSION, repository.schema_version)
                    migrated = repository.get_manual_execution(execution_id)
                    self.assertIsNotNone(migrated)
                    self.assertEqual(ManualExecutionStatus.ADMITTED, migrated.status)
                    claim = repository.manual_execution_claim(execution_id)
                    self.assertIsNotNone(claim)
                    self.assertIsNone(claim["claimToken"])
                    self.assertEqual(0, claim["attempts"])
                finally:
                    repository.close()

    def test_newer_schema_is_rejected_without_touching_the_database(self) -> None:
        with self.journey() as value:
            value.repository.close()
            connection = self._connect(value.runtime_path)
            connection.execute(
                "UPDATE schema_version SET version=? WHERE component='runtime'",
                (SCHEMA_VERSION + 1,),
            )
            connection.commit()
            before = value.runtime_path.read_bytes()
            connection.close()

            with self.assertRaises(ValueError) as context:
                SQLiteTaskRepository(value.runtime_path)
            self.assertIn("newer", str(context.exception))

            connection = self._connect(value.runtime_path)
            self.assertEqual(
                SCHEMA_VERSION + 1,
                connection.execute(
                    "SELECT version FROM schema_version WHERE component='runtime'"
                ).fetchone()[0],
            )
            connection.close()
            # The refusal is a pure read: nothing was migrated or rewritten.
            self.assertEqual(before, value.runtime_path.read_bytes())

    def test_failing_migration_is_atomic_and_leaves_the_older_schema(self) -> None:
        with self.journey() as value:
            value.repository.close()
            connection = self._connect(value.runtime_path)
            # The schema_version table itself refuses the newer version, so the
            # migration fails midway: after some columns were already altered
            # but before the version bump could commit.
            connection.execute("DROP TABLE schema_version")
            connection.execute(
                "CREATE TABLE schema_version ("
                "component TEXT PRIMARY KEY, version INTEGER NOT NULL "
                "CHECK (version <= 33))"
            )
            connection.execute("INSERT INTO schema_version VALUES ('runtime', 33)")
            for column in self._CLAIM_COLUMNS:
                connection.execute(f"ALTER TABLE manual_executions DROP COLUMN {column}")
            connection.commit()
            connection.close()

            with self.assertRaises(sqlite3.IntegrityError):
                SQLiteTaskRepository(value.runtime_path)

            connection = self._connect(value.runtime_path)
            self.assertEqual(
                33,
                connection.execute(
                    "SELECT version FROM schema_version WHERE component='runtime'"
                ).fetchone()[0],
            )
            # No partially applied migration survives the failure.
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(manual_executions)")
            }
            self.assertFalse(columns & set(self._CLAIM_COLUMNS))
            connection.close()

            # Once the obstacle is repaired, the same database migrates fully.
            connection = self._connect(value.runtime_path)
            connection.execute("DROP TABLE schema_version")
            connection.execute(
                "CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            connection.execute("INSERT INTO schema_version VALUES ('runtime', 33)")
            connection.commit()
            connection.close()
            repository = SQLiteTaskRepository(value.runtime_path)
            try:
                self.assertEqual(SCHEMA_VERSION, repository.schema_version)
                columns = {
                    row["name"]
                    for row in repository._connection.execute(
                        "PRAGMA table_info(manual_executions)"
                    )
                }
                self.assertTrue(columns & set(self._CLAIM_COLUMNS))
            finally:
                repository.close()

    def test_reopened_repository_and_service_reconstruct_and_run_admitted_work(self) -> None:
        with self.journey() as value:
            admitted = self._admitted_execution(value)
            execution_id = admitted.execution["executionId"]
            intent_id = admitted.intent["intentId"]
            # The API process dies before the Worker could claim anything.
            value.repository.close()
            self.assertEqual([], value.source.mutations)

            # A real reopen over the same database file reconstructs the exact
            # admitted work and hands it to the resident Worker exactly once.
            repository = SQLiteTaskRepository(value.runtime_path)
            try:
                # Every service is rebuilt on the reopened repository, exactly
                # as an API/Worker process restart would do.
                catalog = FileCatalogService(
                    value.index,
                    ("library",),
                    ("source",),
                    task_repository=repository,
                )
                intents = ManualOrganizeIntentService(
                    repository,
                    catalog,
                    configuration_resolver=manual_snapshot,
                )
                previews = ManualOrganizePreviewService(
                    repository,
                    intents,
                    catalog,
                    configuration=value.configuration,
                    file_index=value.index,
                    providers=MetadataProviderRegistry((SyntheticMetadataProvider(()),)),
                    storages={"source": value.source, "target": value.target},
                )
                execution = ManualOrganizeExecutionService(
                    repository,
                    previews,
                    intents,
                    checkpoint_service=ProcessingCheckpointService(repository),
                    storages={"source": value.source, "target": value.target},
                )
                reopened = execution.get(execution_id)
                self.assertIsNotNone(reopened)
                self.assertEqual(ManualExecutionStatus.ADMITTED, reopened.status)
                self.assertEqual(intent_id, reopened.intent_id)

                worker = ManualOrganizeExecutionWorker(
                    execution, worker_id="restarted-worker", notice=lambda line: None
                )
                completed = worker.run_next()
                self.assertIsNotNone(completed)
                self.assertEqual(ManualExecutionStatus.COMPLETED, completed.status)
                self.assertEqual(execution_id, completed.execution_id)
                self.assertEqual(["delete"], value.source.mutations)
                self.assertTrue(list(value.target_root.rglob("*.mkv")))

                # Nothing is left to claim and nothing is replayed.
                self.assertIsNone(worker.run_next())
                self.assertIsNone(
                    repository.claim_next_manual_execution(
                        datetime.now(UTC),
                        worker_id="second-worker",
                        claim_token="second-token",
                        lease_seconds=60.0,
                    )
                )
            finally:
                repository.close()

    def test_started_work_is_never_reclaimed_or_replayed_after_a_restart(self) -> None:
        with self.journey() as value:
            admitted = self._admitted_execution(value)
            execution_id = admitted.execution["executionId"]
            value.repository.close()
            self.assertEqual([], value.source.mutations)

            repository = SQLiteTaskRepository(value.runtime_path)
            try:
                # The lease is taken and the running mutation boundary is
                # published; the process then dies mid-execution, so whether
                # any mutation happened is genuinely uncertain.
                claimed = repository.claim_next_manual_execution(
                    datetime.now(UTC),
                    worker_id="crashed-worker",
                    claim_token="crashed-token",
                    lease_seconds=60.0,
                )
                self.assertIsNotNone(claimed)
                self.assertEqual(execution_id, claimed.execution_id)
                self.assertTrue(
                    repository.begin_manual_execution(
                        execution_id, "crashed-token", datetime.now(UTC)
                    )
                )
            finally:
                repository.close()

            # A restarted Worker must never reclaim or replay this execution,
            # even long after the original lease expired.
            repository = SQLiteTaskRepository(value.runtime_path)
            try:
                self.assertIsNone(
                    repository.claim_next_manual_execution(
                        datetime.now(UTC) + timedelta(days=1),
                        worker_id="restarted-worker",
                        claim_token="restarted-token",
                        lease_seconds=60.0,
                    )
                )
                execution = repository.get_manual_execution(execution_id)
                self.assertEqual(ManualExecutionStatus.RUNNING, execution.status)
                # The per-item running boundary is published only immediately
                # before its own mutation, so the surviving item evidence is
                # still admitted with unknown certainty: nothing may be replayed.
                self.assertEqual("admitted", execution.items[0].status.value)
                self.assertEqual("unknown", execution.items[0].effect_certainty)
            finally:
                repository.close()
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)


class FilesAdmissionJourneyTests(unittest.TestCase):
    """Files-originated live-Storage admission, exact identity and reconciliation.

    The whole journey runs on one real runtime database shared by the Task
    repository and the durable FileIndex, so exact-occurrence reconciliation is
    exercised against the same persistence boundary production uses.
    """

    SOURCE_NAMES = ("Movies/One.2001.mkv", "Movies/Two.2002.mkv")

    @contextmanager
    def journey(self, *, names: tuple[str, ...] = SOURCE_NAMES, with_symlink: bool = False):
        with (
            tempfile.TemporaryDirectory() as source_directory,
            tempfile.TemporaryDirectory() as target_directory,
            tempfile.TemporaryDirectory() as runtime_directory,
        ):
            source_root = Path(source_directory)
            target_root = Path(target_directory)
            candidates = []
            for position, name in enumerate(names, start=1):
                path = Path(name)
                (source_root / path).parent.mkdir(parents=True, exist_ok=True)
                (source_root / path).write_bytes((name.encode() + b"x" * 200)[:123])
                candidates.append(
                    MediaCandidate(
                        "tmdb",
                        str(200 + position),
                        MediaType.MOVIE,
                        path.stem.split(".", 1)[0],
                        year=2000 + position,
                        genres=("Animation",),
                        countries=("JP",),
                    )
                )
            if with_symlink:
                os.symlink(
                    str(source_root / "Movies" / "One.2001.mkv"),
                    str(source_root / "Movies" / "linked.mkv"),
                )
            runtime_path = Path(runtime_directory, "runtime.sqlite3")
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            library = ResourceLibrary("library", "Library", "source", "", exclude_rules=())
            index = SQLiteFileIndexRepository(runtime_path)
            scan = StorageScanner(
                {"source": source_storage},
                index,
                clock=lambda: datetime.now(UTC) + timedelta(hours=2),
            ).scan(library)
            self.assertEqual("completed", scan.status.value)
            configuration = RuntimeConfiguration(
                development_strategy_configuration(),
                (
                    StorageDefinition("source", "local", str(source_root), "Source"),
                    StorageDefinition("target", "local", str(target_root), "Target"),
                ),
                (library,),
                (),
                (MediaLibrary("movies", "Movies", "target", "Movies"),),
                str(Path(runtime_directory, "history.jsonl")),
                str(runtime_path),
            )
            configuration = with_managed_snapshot(
                configuration, snapshot_id=SNAPSHOT_ID, digest=SNAPSHOT_DIGEST
            )
            provider = SyntheticMetadataProvider(tuple(candidates))
            repository = SQLiteTaskRepository(runtime_path)
            source = RecordingStorage(source_storage)
            target = RecordingStorage(target_storage)
            catalog = FileCatalogService(
                index,
                ("library",),
                ("source",),
                task_repository=repository,
            )
            intents = ManualOrganizeIntentService(
                repository,
                catalog,
                configuration_resolver=manual_snapshot,
                runtime_resolver=lambda snapshot_id, digest: configuration,
                storage_factory=lambda runtime, ids: runtime.create_storages(
                    external={"source": source, "target": target}, storage_ids=ids
                ),
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                catalog,
                configuration=configuration,
                file_index=index,
                providers=MetadataProviderRegistry((provider,)),
                storages={"source": source, "target": target},
            )
            execution = ManualOrganizeExecutionService(
                repository,
                previews,
                intents,
                checkpoint_service=ProcessingCheckpointService(repository),
                storages={"source": source, "target": target},
            )
            worker = ManualOrganizeExecutionWorker(
                execution, worker_id="worker-1", notice=lambda line: None
            )
            worker_service = ProcessingWorkerService(repository)
            worker_service.register_worker(
                "worker-1",
                "worker one",
                10.0,
                ("scan", "preview", "organize"),
                configuration_snapshot_id=SNAPSHOT_ID,
                configuration_snapshot_digest=SNAPSHOT_DIGEST,
                runtime_schema_version=SCHEMA_VERSION,
            )
            api = MediaFlowApi(
                repository,
                None,
                principals=(
                    ResolvedApiPrincipal(
                        "operator",
                        OPERATOR_TOKEN,
                        frozenset(
                            {
                                ApiPermission.READ,
                                ApiPermission.MANAGE_MANUAL_ORGANIZE,
                                ApiPermission.EXECUTE_MANUAL_ORGANIZE,
                            }
                        ),
                    ),
                    ResolvedApiPrincipal(
                        "viewer",
                        VIEWER_TOKEN,
                        frozenset({ApiPermission.READ}),
                    ),
                ),
                system_status=build_configuration_snapshot(configuration),
                file_catalog=catalog,
                file_index=index,
                configuration_snapshot_id=SNAPSHOT_ID,
                configuration_snapshot_digest=SNAPSHOT_DIGEST,
                manual_intent_service=intents,
                manual_preview_service=previews,
                manual_execution_service=execution,
                worker_service=worker_service,
            )
            try:
                yield SimpleNamespace(
                    api=api,
                    repository=repository,
                    intents=intents,
                    previews=previews,
                    execution=execution,
                    worker=worker,
                    configuration=configuration,
                    index=index,
                    catalog=catalog,
                    source=source,
                    target=target,
                    source_root=source_root,
                    target_root=target_root,
                )
            finally:
                index.close()
                repository.close()

    @staticmethod
    def request(
        value,
        path: str,
        method: str = "GET",
        body: dict | None = None,
        *,
        token: str = OPERATOR_TOKEN,
    ) -> tuple[int, dict]:
        statuses: list[str] = []
        raw = json.dumps(body).encode() if body is not None else b""
        path_info, _, query_string = path.partition("?")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(raw)),
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": io.BytesIO(raw),
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        response = b"".join(value.api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(response)

    def admit(self, value, paths, *, token: str = OPERATOR_TOKEN):
        return self.request(
            value,
            "/api/v1/resource-libraries/library/files/organize",
            "POST",
            {"paths": list(paths)},
            token=token,
        )

    def test_files_admission_creates_one_ordered_multi_file_intent_from_live_storage(self) -> None:
        with self.journey() as value:
            status, intent = self.admit(value, ["Movies/Two.2002.mkv", "Movies/One.2001.mkv"])
            self.assertEqual(201, status, intent)
            self.assertEqual("organize", intent["journey"])
            self.assertTrue(intent["zeroMutation"])
            self.assertEqual("open", intent["status"])
            self.assertEqual(
                ["Two.2002.mkv", "One.2001.mkv"],
                [Path(item["source"]["path"]).name for item in intent["items"]],
            )
            first = value.index.find_by_path("source", "library", "Movies/One.2001.mkv")
            self.assertIsNotNone(first)
            # The intent carries the server-derived identity of the live source.
            stored = value.repository.get_manual_intent(intent["intentId"])
            identities = {item.source.path: item.source for item in stored.items}
            self.assertEqual(
                first.occurrence_id,
                identities["Movies/One.2001.mkv"].occurrence_id,
            )
            self.assertEqual(first.fingerprint, identities["Movies/One.2001.mkv"].fingerprint)
            # Admission is zero Storage mutation, creates no Task and no Preview.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual((), value.repository.list_tasks())
            self.assertIsNone(value.repository.get_manual_execution("does-not-exist"))
            # The operator document never publishes fingerprints, occurrence IDs
            # or configuration digests.
            encoded = json.dumps(intent)
            for forbidden in ("fingerprint", "occurrenceId", SNAPSHOT_DIGEST):
                self.assertNotIn(forbidden, encoded)

    def test_files_admission_fails_closed_for_ineligible_and_malformed_selections(self) -> None:
        with self.journey(with_symlink=True) as value:
            cases = (
                (["Movies"], 409, "source_not_file"),
                (["Movies/linked.mkv"], 409, "source_symlink"),
                (["Movies/Missing.mkv"], 404, "source_missing"),
                (["../escape.mkv"], 400, "invalid_path"),
                (["/etc/passwd"], 400, "invalid_path"),
                (["Movies/One.2001.mkv", "Movies/One.2001.mkv"], 400, "duplicate_source"),
                ([], 400, "selection_empty"),
                (
                    [f"Movies/Bulk.{index:03d}.mkv" for index in range(101)],
                    400,
                    "selection_over_limit",
                ),
            )
            for paths, expected_status, expected_code in cases:
                status, document = self.admit(value, paths)
                self.assertEqual(expected_status, status, (paths, document))
                self.assertEqual(expected_code, document["error"]["code"], paths)
                self.assertEqual(
                    "rejected_without_mutation", document["error"]["details"]["durableState"]
                )
            # Nothing was admitted, mutated or scheduled by a rejected selection.
            self.assertEqual((), value.repository.list_tasks())
            self.assertEqual((), value.repository.list_manual_intents())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_files_admission_requires_manage_permission(self) -> None:
        with self.journey() as value:
            status, document = self.admit(value, ["Movies/One.2001.mkv"], token=VIEWER_TOKEN)
            self.assertEqual(403, status, document)
            self.assertEqual((), value.repository.list_manual_intents())
            self.assertEqual([], value.source.mutations)

    def test_files_admission_rejects_a_non_current_active_selection(self) -> None:
        with self.journey() as value:
            # A source that disappeared after the Files listing was rendered
            # fails without admitting an intent.
            (value.source_root / "Movies" / "One.2001.mkv").unlink()
            status, document = self.admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(404, status, document)
            self.assertEqual("source_missing", document["error"]["code"])
            self.assertEqual((), value.repository.list_manual_intents())

    def test_files_journey_executes_and_reconciles_the_exact_live_occurrence(self) -> None:
        with self.journey() as value:
            status, intent = self.admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(201, status, intent)
            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}/previews",
                "POST",
                {"expectedVersion": intent["version"]},
            )
            self.assertEqual(201, status, preview)
            status, execution = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
                "POST",
                {
                    "confirmation": True,
                    "itemIds": [item["itemId"] for item in preview["items"]],
                    "expectedIntentVersion": intent["version"],
                },
            )
            self.assertEqual(202, status, execution)
            self.assertEqual([], value.source.mutations)
            completed = value.worker.run_next()
            self.assertIsNotNone(completed)
            self.assertIsNone(value.worker.run_next())

            records = {
                name: value.index.find_by_path("source", "library", name)
                for name in ("Movies/One.2001.mkv", "Movies/Two.2002.mkv")
            }
            task = value.repository.get_task(execution["taskId"])
            self.assertIsNotNone(task)
            items = value.repository.list_items(execution["taskId"])
            self.assertEqual(2, len(items))
            for item in items:
                record = records[item.source_path]
                self.assertEqual(record.occurrence_id, item.source_occurrence_id)
                self.assertEqual(record.fingerprint, item.source_fingerprint)
                self.assertEqual("verified", item.source_fingerprint_state)
                results = value.repository.list_results_for_item(item.item_id)
                self.assertEqual(1, len(results))
                self.assertEqual(record.occurrence_id, results[0].source_occurrence_id)
                self.assertEqual(record.fingerprint, results[0].source_fingerprint)
                self.assertEqual("verified", results[0].source_fingerprint_state)
            # The durable Result reconciled the exact FileIndex occurrence it executed.
            for name, record in records.items():
                current = value.index.find_by_path("source", "library", name)
                self.assertEqual(record.occurrence_id, current.occurrence_id)
                self.assertNotEqual("unknown", current.processing_disposition.value, name)
                self.assertIsNotNone(current.processing_result_id)

            status, document = self.request(
                value,
                f"/api/v1/operations/organize/executions/{execution['executionId']}",
            )
            self.assertEqual(200, status, document)
            reconciliation = {
                item["itemId"]: item["fileIndexReconciliation"] for item in document["items"]
            }
            self.assertEqual(2, len(reconciliation))
            for state in reconciliation.values():
                self.assertEqual("synchronized", state["state"])
                self.assertFalse(state["action"]["available"])
            encoded = json.dumps(document)
            for forbidden in ("fingerprint", "occurrenceId", "executionPlan"):
                self.assertNotIn(forbidden, encoded)

    def test_same_path_replacement_never_receives_the_older_occurrence_result(self) -> None:
        with self.journey(names=("Movies/One.2001.mkv",)) as value:
            status, intent = self.admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(201, status, intent)
            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}/previews",
                "POST",
                {"expectedVersion": intent["version"]},
            )
            self.assertEqual(201, status, preview)
            status, execution = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
                "POST",
                {
                    "confirmation": True,
                    "itemIds": [item["itemId"] for item in preview["items"]],
                    "expectedIntentVersion": intent["version"],
                },
            )
            self.assertEqual(202, status, execution)
            self.assertIsNotNone(value.worker.run_next())

            original = value.index.find_by_path("source", "library", "Movies/One.2001.mkv")
            self.assertNotEqual("unknown", original.processing_disposition.value)

            # A different file now occupies the same live path.  A routine
            # rescan records a new occurrence; the older Result must never bind
            # to it.
            (value.source_root / "Movies" / "One.2001.mkv").write_bytes(b"replacement" * 40)
            scan = StorageScanner(
                {"source": LocalStorage("source", value.source_root)},
                value.index,
                clock=lambda: datetime.now(UTC) + timedelta(hours=4),
            ).scan(ResourceLibrary("library", "Library", "source", "", exclude_rules=()))
            self.assertEqual("completed", scan.status.value)
            replacement = value.index.find_by_path("source", "library", "Movies/One.2001.mkv")
            self.assertNotEqual(original.occurrence_id, replacement.occurrence_id)
            self.assertEqual("unknown", replacement.processing_disposition.value)
            self.assertIsNone(replacement.processing_result_id)

            status, document = self.request(
                value,
                f"/api/v1/operations/organize/executions/{execution['executionId']}",
            )
            self.assertEqual(200, status, document)
            item = document["items"][0]
            self.assertEqual("no_matching_occurrence", item["fileIndexReconciliation"]["state"])
            self.assertTrue(item["fileIndexReconciliation"]["action"]["available"])

            # The bounded reconciliation action re-applies the durable Result
            # only to a matching current occurrence; the replacement keeps its
            # own untouched disposition and no mutation is replayed.
            status, result = self.request(
                value,
                f"/api/v1/operations/organize/executions/{execution['executionId']}"
                "/file-index-reconciliation",
                "POST",
                {"itemId": item["itemId"]},
            )
            self.assertEqual(200, status, result)
            self.assertEqual("no_matching_occurrence", result["fileIndexReconciliation"]["state"])
            self.assertEqual("organize_effect_unchanged", result["durableState"])
            after = value.index.find_by_path("source", "library", "Movies/One.2001.mkv")
            self.assertEqual("unknown", after.processing_disposition.value)
            self.assertIsNone(after.processing_result_id)

    def save_choice(self, value, intent, item, body, *, token: str = OPERATOR_TOKEN):
        return self.request(
            value,
            f"/api/v1/operations/organize/intents/{intent['intentId']}"
            f"/items/{item['itemId']}/choice",
            "POST",
            {"expectedVersion": intent["version"], **body},
            token=token,
        )

    def test_files_source_saves_choice_without_a_file_index_row(self) -> None:
        """A live Files selection saves a valid Choice with no FileIndex row.

        This is the recorded P1: the Files admission derives its source
        identity from live Storage, so Save Choice must validate against that
        same pinned Storage authority instead of demanding a FileIndex row.
        """

        with self.journey(names=("Movies/One.2001.mkv",)) as value:
            status, intent = self.admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(201, status, intent)
            item = intent["items"][0]
            # The admitted intent really carries the live-Storage authority,
            # not a FileIndex-derived identity.
            stored = value.repository.get_manual_intent(intent["intentId"])
            self.assertTrue(stored.items[0].source.is_storage_source)
            # Remove every FileIndex row: the Files selection is still the
            # current live Storage source and must keep its authority.
            value.index.close()
            value.index = InMemoryFileIndexRepository()

            status, updated = self.save_choice(
                value,
                intent,
                item,
                {
                    "recognitionTypeId": "C",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
            )
            self.assertEqual(200, status, updated)
            self.assertEqual("C", updated["items"][0]["choice"]["recognitionTypeId"])
            # Save Choice is zero Storage mutation.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_files_source_choice_rejections_preserve_durable_state(self) -> None:
        """Missing and replaced Files sources reject with no durable change."""

        with self.journey(names=("Movies/One.2001.mkv",)) as value:
            status, intent = self.admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(201, status, intent)
            item = intent["items"][0]
            stored_before = value.repository.get_manual_intent(intent["intentId"])
            version_before = (stored_before.version, stored_before.items[0].version)

            # A source that disappeared before Save Choice is source_missing.
            (value.source_root / "Movies" / "One.2001.mkv").unlink()
            status, document = self.save_choice(value, intent, item, {"recognitionTypeId": "C"})
            self.assertEqual(404, status, document)
            self.assertEqual("source_missing", document["error"]["code"])
            self.assertEqual("none", document["error"]["details"]["sideEffects"])
            after = value.repository.get_manual_intent(intent["intentId"])
            self.assertEqual(version_before, (after.version, after.items[0].version))
            self.assertEqual("open", after.status.value)

            # A replaced source (same path, different content) is source_stale.
            (value.source_root / "Movies" / "One.2001.mkv").write_bytes(b"replacement" * 40)
            status, document = self.save_choice(value, intent, item, {"recognitionTypeId": "C"})
            self.assertEqual(409, status, document)
            self.assertEqual("source_stale", document["error"]["code"])
            after = value.repository.get_manual_intent(intent["intentId"])
            self.assertEqual(version_before, (after.version, after.items[0].version))
            self.assertEqual("open", after.status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            # The rejection never leaks internal identity implementation detail.
            self.assertNotIn("fingerprint", json.dumps(document))
            self.assertNotIn("occurrenceId", json.dumps(document))

    def test_file_index_intent_keeps_its_scoped_file_index_validation(self) -> None:
        """The legacy FileIndex-originated path keeps its existing behavior."""

        with self.journey(names=("Movies/One.2001.mkv",)) as value:
            record = value.index.find_by_path("source", "library", "Movies/One.2001.mkv")
            status, intent = self.request(
                value,
                "/api/v1/operations/organize/intents",
                "POST",
                {
                    "scopeKind": "file",
                    "fileId": record.file_id,
                    "resourceLibraryId": "library",
                },
            )
            self.assertEqual(201, status, intent)
            item = intent["items"][0]
            stored = value.repository.get_manual_intent(intent["intentId"])
            self.assertFalse(stored.items[0].source.is_storage_source)
            version_before = (stored.version, stored.items[0].version)

            # The FileIndex-originated path still requires its scoped FileIndex
            # occurrence: with every row gone it fails closed as source_missing.
            empty_index = InMemoryFileIndexRepository()
            value.index.close()
            value.index = empty_index
            value.catalog._repository = empty_index
            status, document = self.save_choice(value, intent, item, {"recognitionTypeId": "C"})
            self.assertEqual(404, status, document)
            self.assertEqual("source_missing", document["error"]["code"])
            after = value.repository.get_manual_intent(intent["intentId"])
            self.assertEqual(version_before, (after.version, after.items[0].version))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_files_source_choice_is_optimistic_and_keeps_preview_invalidation(self) -> None:
        """Optimistic versions and prior-Preview invalidation stay unchanged."""

        with self.journey(names=("Movies/One.2001.mkv",)) as value:
            status, intent = self.admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(201, status, intent)
            item = intent["items"][0]
            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}/previews",
                "POST",
                {"expectedVersion": intent["version"]},
            )
            self.assertEqual(201, status, preview)
            self.assertTrue(preview["current"])

            # A stale expected version is refused without a durable change.
            stored_before = value.repository.get_manual_intent(intent["intentId"])
            status, document = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}"
                f"/items/{item['itemId']}/choice",
                "POST",
                {"expectedVersion": intent["version"] + 5, "recognitionTypeId": "C"},
            )
            self.assertEqual(409, status, document)
            after = value.repository.get_manual_intent(intent["intentId"])
            self.assertEqual(
                (stored_before.version, stored_before.items[0].version),
                (after.version, after.items[0].version),
            )

            # A valid Files choice edit still invalidates the prior Preview.
            status, updated = self.save_choice(value, intent, item, {"recognitionTypeId": "C"})
            self.assertEqual(200, status, updated)
            self.assertEqual("C", updated["items"][0]["choice"]["recognitionTypeId"])
            status, refreshed = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview['previewId']}",
            )
            self.assertEqual(200, status, refreshed)
            self.assertFalse(refreshed["current"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)


class DefaultAssemblySaveChoiceTests(unittest.TestCase):
    """Files Save Choice through the automatic ``MediaFlowApi`` composition.

    This is the recorded P1 regression: the default API assembly supplies only
    ``configuration_service`` and ``storage_factory`` to
    ``ManualOrganizeIntentService`` — no explicit ``runtime_resolver`` — so the
    service must validate a Files-originated source against the managed
    pinned-runtime resolver it builds internally.  These tests never inject a
    ``runtime_resolver`` and drive the real managed Active lifecycle
    (import → validate → activate) over a real SQLite configuration
    repository, real ``LocalStorage`` roots and a real runtime database.
    """

    OPERATOR = ResolvedApiPrincipal(
        "operator",
        OPERATOR_TOKEN,
        frozenset({ApiPermission.READ, ApiPermission.MANAGE_MANUAL_ORGANIZE}),
    )

    @contextmanager
    def journey(self):
        with (
            tempfile.TemporaryDirectory() as source_directory,
            tempfile.TemporaryDirectory() as target_directory,
            tempfile.TemporaryDirectory() as runtime_directory,
        ):
            root = Path(runtime_directory)
            source_root = Path(source_directory)
            target_root = Path(target_directory)
            media = source_root / "Media"
            (media / "Movies").mkdir(parents=True)
            (media / "Movies" / "One.2001.mkv").write_bytes(b"one" * 41)
            (target_root / "Movies").mkdir(parents=True)

            configuration_path = root / "configuration.sqlite3"
            configuration_repository = SQLiteConfigurationRepository(configuration_path)
            service = ManagedConfigurationService(
                configuration_repository,
                bootstrap_database_path=str(configuration_path),
            )
            document = example_document()
            document["persistence"]["databasePath"] = str(configuration_path)
            document["storages"][0]["rootPath"] = str(source_root)
            document["storages"][1]["rootPath"] = str(target_root)
            draft = service.import_draft(document, actor="operator")
            validated = service.validate(draft.revision_id, actor="operator")
            active = service.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor="operator",
            )

            runtime_path = root / "runtime.sqlite3"
            repository = SQLiteTaskRepository(runtime_path)
            index = SQLiteFileIndexRepository(runtime_path)
            catalog = FileCatalogService(
                index,
                ("source",),
                ("source-storage",),
                task_repository=repository,
            )
            api = MediaFlowApi(
                repository,
                None,
                principals=(self.OPERATOR,),
                configuration_service=service,
                file_catalog=catalog,
                file_index=index,
            )
            try:
                yield SimpleNamespace(
                    api=api,
                    repository=repository,
                    index=index,
                    catalog=catalog,
                    service=service,
                    configuration_repository=configuration_repository,
                    active=active,
                    source_root=source_root,
                    media=media,
                )
            finally:
                index.close()
                repository.close()
                configuration_repository.close()

    @staticmethod
    def request(value, path, *, method="GET", body=None):
        raw = json.dumps(body).encode() if body is not None else b""
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(raw)),
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": io.BytesIO(raw),
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {OPERATOR_TOKEN}",
        }
        response = b"".join(value.api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(response)

    def admit(self, value, paths):
        return self.request(
            value,
            "/api/v1/resource-libraries/source/files/organize",
            method="POST",
            body={"paths": list(paths)},
        )

    def test_default_assembly_saves_files_choice_against_managed_runtime(self) -> None:
        """A valid Files-originated choice persists without an injected resolver."""

        with self.journey() as value:
            status, intent = self.admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(201, status, intent)
            item = intent["items"][0]
            stored = value.repository.get_manual_intent(intent["intentId"])
            self.assertTrue(stored.items[0].source.is_storage_source)
            # The Files authority is live Storage: no FileIndex row exists.
            self.assertEqual((), value.index.list_by_resource_library("source"))
            versions_before = (stored.version, stored.items[0].version)
            audits_before = value.repository.list_manual_intent_audit(intent["intentId"])

            status, updated = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}"
                f"/items/{item['itemId']}/choice",
                method="POST",
                body={
                    "expectedVersion": intent["version"],
                    "expectedItemVersion": item["version"],
                    "recognitionTypeId": "C",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
            )
            self.assertEqual(200, status, updated)
            choice = updated["items"][0]["choice"]
            self.assertEqual("C", choice["recognitionTypeId"])
            self.assertEqual("A", choice["namingPolicyId"])
            self.assertEqual("A", choice["classificationPolicyId"])
            self.assertEqual("A", choice["organizePolicyId"])

            # The choice persisted exactly once and each version moved once.
            persisted = value.repository.get_manual_intent(intent["intentId"])
            self.assertEqual("C", persisted.items[0].choice.recognition_type_id)
            self.assertEqual(versions_before[0] + 1, persisted.version)
            self.assertEqual(versions_before[1] + 1, persisted.items[0].version)
            audits_after = value.repository.list_manual_intent_audit(intent["intentId"])
            self.assertEqual(len(audits_before) + 1, len(audits_after))
            self.assertEqual("choice_updated", audits_after[-1].action)
            # Save Choice performs zero Storage mutation.
            self.assertEqual((), value.repository.list_tasks())

    def test_default_assembly_fails_closed_when_source_or_runtime_unavailable(self) -> None:
        """Unavailable runtime/source evidence rejects without durable change."""

        with self.journey() as value:
            status, intent = self.admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(201, status, intent)
            item = intent["items"][0]
            choice_path = (
                f"/api/v1/operations/organize/intents/{intent['intentId']}"
                f"/items/{item['itemId']}/choice"
            )
            body = {"expectedVersion": intent["version"], "recognitionTypeId": "C"}

            default_choice = value.repository.get_manual_intent(
                intent["intentId"]
            ).items[0].choice

            def unchanged():
                persisted = value.repository.get_manual_intent(intent["intentId"])
                self.assertEqual(intent["version"], persisted.version)
                self.assertEqual(item["version"], persisted.items[0].version)
                self.assertEqual(default_choice, persisted.items[0].choice)
                self.assertEqual("open", persisted.status.value)
                self.assertEqual(
                    1, len(value.repository.list_manual_intent_audit(intent["intentId"]))
                )

            # A source that disappeared before Save Choice fails closed.
            (value.media / "Movies" / "One.2001.mkv").unlink()
            status, document = self.request(value, choice_path, method="POST", body=body)
            self.assertEqual(404, status, document)
            self.assertEqual("source_missing", document["error"]["code"])
            unchanged()

            # A replaced source (same path, different content) is source_stale.
            (value.media / "Movies" / "One.2001.mkv").write_bytes(b"replacement" * 40)
            status, document = self.request(value, choice_path, method="POST", body=body)
            self.assertEqual(409, status, document)
            self.assertEqual("source_stale", document["error"]["code"])
            unchanged()

            # A pinned snapshot the managed authority no longer publishes fails
            # closed instead of falling back to the current configuration.
            value.configuration_repository._connection.execute(
                "UPDATE managed_configuration_revisions SET status = ? WHERE revision_id = ?",
                ("archived", value.active.revision_id),
            )
            status, document = self.request(value, choice_path, method="POST", body=body)
            self.assertEqual(503, status, document)
            self.assertEqual("configuration_unavailable", document["error"]["code"])
            details = document["error"]["details"]
            self.assertEqual("managed_active_unavailable", details["durableState"])
            self.assertEqual("none", details["sideEffects"])
            unchanged()

    def test_save_choice_uses_intent_pinned_snapshot_after_active_replacement(self) -> None:
        """A successor Active revision must not invalidate a pinned intent.

        Regression for the reviewed FIX REQUIRED: the intent is created under
        Active revision A; a successor revision that disables the
        ResourceLibrary is then activated.  Save Choice must still validate the
        source against the intent-pinned revision A (published superseded
        snapshot, unchanged live Storage) and persist exactly once, not fail
        with ``source_cross_authority`` from the successor revision.
        """

        with self.journey() as value:
            status, intent = self.admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(201, status, intent)
            item = intent["items"][0]
            pinned_revision_id = value.active.revision_id
            stored = value.repository.get_manual_intent(intent["intentId"])
            self.assertEqual(pinned_revision_id, stored.snapshot_id)
            versions_before = (stored.version, stored.items[0].version)
            audits_before = value.repository.list_manual_intent_audit(intent["intentId"])

            # Activate a successor revision that disables the ResourceLibrary.
            successor_document = example_document()
            successor_document["persistence"]["databasePath"] = str(
                value.configuration_repository.database_path
            )
            successor_document["storages"][0]["rootPath"] = str(value.source_root)
            successor_document["storages"][1]["rootPath"] = str(value.media.parent / "target")
            successor_document["resourceLibraries"][0]["enabled"] = False
            draft = value.service.import_draft(successor_document, actor="operator")
            validated = value.service.validate(draft.revision_id, actor="operator")
            successor = value.service.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor="operator",
            )
            self.assertNotEqual(pinned_revision_id, successor.revision_id)
            # Revision A is now superseded but still published and intact.
            self.assertEqual(
                "superseded", value.service.require(pinned_revision_id).status.value
            )

            status, updated = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent['intentId']}"
                f"/items/{item['itemId']}/choice",
                method="POST",
                body={
                    "expectedVersion": intent["version"],
                    "expectedItemVersion": item["version"],
                    "recognitionTypeId": "C",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
            )
            self.assertEqual(200, status, updated)
            self.assertEqual("C", updated["items"][0]["choice"]["recognitionTypeId"])

            persisted = value.repository.get_manual_intent(intent["intentId"])
            self.assertEqual("C", persisted.items[0].choice.recognition_type_id)
            # Still pinned to revision A, persisted exactly once.
            self.assertEqual(pinned_revision_id, persisted.snapshot_id)
            self.assertEqual(versions_before[0] + 1, persisted.version)
            self.assertEqual(versions_before[1] + 1, persisted.items[0].version)
            audits_after = value.repository.list_manual_intent_audit(intent["intentId"])
            self.assertEqual(len(audits_before) + 1, len(audits_after))
            self.assertEqual("choice_updated", audits_after[-1].action)
            self.assertEqual((), value.repository.list_tasks())


if __name__ == "__main__":
    unittest.main()
