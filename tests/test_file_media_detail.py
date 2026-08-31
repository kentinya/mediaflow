from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.evidence_capture import build_pipeline_evidence
from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.media_organizer import MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import (
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskItem,
    TaskItemStatus,
)
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_file_catalog import file_record

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


def api_request(api, path: str, *, token="viewer-token", method="GET", body=None, query=""):
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if body is not None:
        raw = json.dumps(body).encode("utf-8")
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(body)


class FileMediaDetailTests(unittest.TestCase):
    def _database(self, directory: str) -> Path:
        return Path(directory, "runtime.sqlite3")

    def test_legacy_detail_marks_unavailable_and_never_reconstructs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                repository.upsert_item(
                    PersistentTaskItem(
                        item.item_id,
                        task.task_id,
                        "source",
                        "movies",
                        "Movies/A.mkv",
                        "Movies/A.mkv",
                        TaskItemStatus.DRY_RUN,
                        "completed",
                        item.attempts,
                        item.created_at,
                        NOW,
                        plan_id="plan-1",
                    )
                )
                repository.append_result(
                    PersistentResultRecord(
                        "result-1",
                        task.task_id,
                        item.item_id,
                        "source",
                        "Movies/A.mkv",
                        "target",
                        "Movies/A.mkv",
                        "C",
                        "tmdb",
                        "129",
                        "C",
                        "A",
                        "A",
                        "A",
                        "move",
                        "dry_run",
                        NOW,
                        title="Movie A",
                    )
                )
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("movies",),
                    ("source",),
                    task_repository=repository,
                )
                detail = service.detail("one")
                self.assertEqual(detail.evidence, ())
                self.assertEqual(detail.truncated["evidence"], False)
                self.assertEqual(len(detail.items), 1)
                self.assertEqual(detail.items[0].status, "dry_run")
                self.assertEqual(len(detail.results), 1)
                self.assertEqual(detail.actions, ())

    def test_real_dryrun_capture_persists_type_c_and_downstream_policy_a(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
            tempfile.TemporaryDirectory() as state_root,
        ):
            source_path = Path(source_root, "Movie.2024.mkv")
            source_path.write_bytes(b"movie")
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            storages = {"source": source_storage, "target": target_storage}
            configuration = development_strategy_configuration()
            provider = SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "Movie",
                        year=2024,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            )
            database = Path(state_root, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create(
                    "preview",
                    execute_authorized=False,
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest="digest-1",
                )
                service = MediaOrganizerService(
                    strategy_runner_from_configuration(
                        configuration, MetadataProviderRegistry((provider,))
                    ),
                    None,
                    storages,
                    {"movies": MediaLibrary("movies", "Movies", "target", "Movies")},
                    configuration.recognition_type_policies,
                    JsonLinesOperationHistoryRepository(Path(state_root, "history.jsonl")),
                    source_display_roots={"movies": source_root},
                    task_coordinator=coordinator,
                    task_id=task.task_id,
                )
                library = ResourceLibrary("special", "Special", "source", "")
                processed = service.process_file(
                    source_path.as_posix(),
                    resource_library=library,
                    storage_path=source_path.name,
                )
                self.assertIsNotNone(processed.evidence)
                self.assertEqual(processed.execution.status.value, "DRY_RUN")
                evidence = repository.list_evidence_for_item(processed.evidence.item_id)
                self.assertEqual(len(evidence), 1)
                record = evidence[0]
                self.assertEqual(record.outcome, "dry_run")
                self.assertEqual(record.section("policies").value["recognitionTypeId"], "C")
                self.assertEqual(record.section("policies").value["namingPolicyId"], "A")
                self.assertEqual(record.section("policies").value["classificationPolicyId"], "A")
                self.assertEqual(record.section("policies").value["organizePolicyId"], "A")
                self.assertEqual(record.section("recognition").value["recognitionTypeId"], "C")
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "special", source_path.name),))
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("special",),
                    ("source",),
                    task_repository=repository,
                )
                detail = service.detail("one")
                self.assertEqual(len(detail.evidence), 1)
                policies = detail.evidence[0].section("policies").value
                self.assertEqual(policies["recognitionTypeId"], "C")
                self.assertEqual(policies["namingPolicyId"], "A")
                self.assertEqual(policies["classificationPolicyId"], "A")
                self.assertEqual(policies["organizePolicyId"], "A")

    def test_waiting_evidence_and_reload_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                evidence = build_pipeline_evidence(task, item, outcome="waiting_recognition")
                repository.append_evidence(evidence)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as reopened:
                values = reopened.list_evidence_for_item(item.item_id)
                self.assertEqual(len(values), 1)
                self.assertEqual(values[0].outcome, "waiting_recognition")
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as reopened,
            ):
                service = FileCatalogService(
                    index,
                    ("movies",),
                    ("source",),
                    task_repository=reopened,
                )
                detail = service.detail("one")
                self.assertEqual(detail.evidence[0].outcome, "waiting_recognition")
                self.assertEqual(detail.evidence[0].document(), values[0].document())

    def test_detail_reads_create_no_provider_storage_queue_or_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                repository.append_evidence(
                    build_pipeline_evidence(task, item, outcome="processing")
                )
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("movies",),
                    ("source",),
                    task_repository=repository,
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    file_catalog=service,
                )
                with (
                    patch(
                        "mediaflow.application.metadata.MetadataIdentificationService",
                        side_effect=AssertionError("detail must not construct providers"),
                    ),
                    patch.object(
                        LocalStorage,
                        "read",
                        side_effect=AssertionError("detail must not read Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "list",
                        side_effect=AssertionError("detail must not list Storage"),
                    ),
                ):
                    status, document = api_request(api, "/api/v1/files/one")
                self.assertEqual(status, 200)
                self.assertEqual(document["evidence"][0]["outcome"], "processing")
                self.assertEqual(repository.list_security_audit(), ())
                self.assertIn("Captured pipeline evidence", APP_JS.decode())
                self.assertIn("/api/v1/files/by-source", APP_JS.decode())
                self.assertIn("renderFileMediaSections", APP_JS.decode())

    def test_rbac_denies_read_and_read_only_cannot_invoke_write_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                repository.append_evidence(
                    build_pipeline_evidence(task, item, outcome="failed", error="failed")
                )
                repository.upsert_item(
                    PersistentTaskItem(
                        item.item_id,
                        task.task_id,
                        "source",
                        "movies",
                        "Movies/A.mkv",
                        "Movies/A.mkv",
                        TaskItemStatus.FAILED,
                        "failed",
                        item.attempts,
                        item.created_at,
                        NOW,
                        error="failed",
                    )
                )
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("movies",),
                    ("source",),
                    task_repository=repository,
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    file_catalog=service,
                )
                status, _ = api_request(api, "/api/v1/files/one", token=None)
                self.assertEqual(status, 401)
                status, document = api_request(api, "/api/v1/files/one/re-plan", method="POST")
                self.assertEqual(status, 403)
                self.assertEqual(document["error"]["code"], "forbidden")

    def test_by_source_resolves_unique_and_explains_missing_or_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert(
                    (
                        file_record("one", "source", "movies", "Movies/A.mkv"),
                        file_record("two", "source", "archive", "Movies/A.mkv"),
                    )
                )
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("movies", "archive"),
                    ("source",),
                    task_repository=repository,
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    file_catalog=service,
                )
                status, document = api_request(api, "/api/v1/files/by-source", query="")
                self.assertEqual(status, 400)
                status, document = api_request(
                    api,
                    "/api/v1/files/by-source",
                    query="storageId=source&path=Movies%2FA.mkv",
                )
                self.assertEqual(status, 200)
                self.assertFalse(document["available"])
                self.assertIn("ambiguous", document["unavailableReason"])
                status, document = api_request(
                    api,
                    "/api/v1/files/by-source",
                    query="storageId=source&path=Movies%2FA.mkv&resourceLibrary=movies",
                )
                self.assertEqual(status, 200)
                self.assertTrue(document["available"])
                self.assertEqual(document["fileId"], "one")
                status, document = api_request(
                    api,
                    "/api/v1/files/by-source",
                    query="storageId=source&path=Missing.mkv&resourceLibrary=movies",
                )
                self.assertEqual(status, 200)
                self.assertFalse(document["available"])
                self.assertIn("no current indexed", document["unavailableReason"])

    def test_complete_item_evidence_write_rolls_back_result_and_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                completed = PersistentTaskItem(
                    item.item_id,
                    task.task_id,
                    "source",
                    "movies",
                    "Movies/A.mkv",
                    "Movies/A.mkv",
                    TaskItemStatus.SUCCESS,
                    "completed",
                    item.attempts,
                    item.created_at,
                    NOW,
                )
                result = PersistentResultRecord(
                    "result-1",
                    task.task_id,
                    item.item_id,
                    "source",
                    "Movies/A.mkv",
                    "target",
                    "Movies/A.mkv",
                    "C",
                    "tmdb",
                    "129",
                    "C",
                    "A",
                    "A",
                    "A",
                    "move",
                    "success",
                    NOW,
                )
                evidence = build_pipeline_evidence(task, item, outcome="success")
                with patch.object(
                    SQLiteTaskRepository,
                    "_evidence_values",
                    side_effect=RuntimeError("evidence persistence failed"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "evidence persistence failed"):
                        repository.complete_item_with_evidence(completed, result, evidence)
                persisted = repository.get_item(item.item_id)
                self.assertIsNotNone(persisted)
                self.assertEqual(persisted.status, TaskItemStatus.PROCESSING)
                self.assertEqual(repository.list_results_for_item(item.item_id), ())
                self.assertEqual(repository.list_evidence_for_item(item.item_id), ())

    def test_old_schema_26_migrates_without_losing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.record_discovered(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                repository.append_result(
                    PersistentResultRecord(
                        "legacy-result",
                        task.task_id,
                        item.item_id,
                        "source",
                        "Movies/A.mkv",
                        None,
                        None,
                        "C",
                        "tmdb",
                        "129",
                        "C",
                        "A",
                        "A",
                        "A",
                        "move",
                        "dry_run",
                        NOW,
                    )
                )
            connection = sqlite3.connect(database)
            connection.execute("UPDATE schema_version SET version=26 WHERE component='runtime'")
            connection.execute("DROP TABLE pipeline_evidence")
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.schema_version, SCHEMA_VERSION)
                self.assertEqual(reopened.list_items(task.task_id)[0].item_id, item.item_id)
                self.assertEqual(reopened.list_results(task.task_id)[0].result_id, "legacy-result")
                self.assertEqual(reopened.list_evidence_for_item(item.item_id), ())


if __name__ == "__main__":
    unittest.main()
