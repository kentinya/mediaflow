from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.media_organizer import MediaOrganizerItemResult
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.domain.organizer import (
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
    OrganizePlan,
    PlanOperation,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskItem,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def request(api, method: str, path: str, *, token: str | None = "viewer-token"):
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


def request_with_query(api, path: str, query: str):
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": "Bearer viewer-token",
        "wsgi.input": io.BytesIO(),
    }
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


class ProcessingCheckpointTests(unittest.TestCase):
    @staticmethod
    def _item(task_id: str, item_id: str, status: TaskItemStatus, stage: str) -> PersistentTaskItem:
        return PersistentTaskItem(
            item_id,
            task_id,
            "source",
            "resources",
            f"folder/{item_id}.mkv",
            f"source/{item_id}.mkv",
            status,
            stage,
            1,
            NOW,
            NOW,
        )

    @staticmethod
    def _result(
        task_id: str,
        item_id: str,
        result_id: str,
        status: str,
        *,
        certainty: str = "unknown",
        completed: tuple[str, ...] = (),
        uncertain: tuple[str, ...] = (),
    ) -> PersistentResultRecord:
        return PersistentResultRecord(
            result_id,
            task_id,
            item_id,
            "source",
            f"folder/{item_id}.mkv",
            "target",
            f"Movies/{item_id}.mkv",
            "C",
            "tmdb",
            "123",
            "metadata-c",
            "naming-a",
            "classification-a",
            "organize-move",
            "MOVE",
            status,
            NOW,
            title="Example",
            completed_operations=completed,
            effect_certainty=certainty,
            uncertain_effects=uncertain,
        )

    def test_all_persisted_statuses_and_production_stages_are_projectable(self) -> None:
        cases = (
            (TaskItemStatus.PENDING, "pipeline", "queued"),
            (TaskItemStatus.PROCESSING, "strategy", "recognition"),
            (TaskItemStatus.DRY_RUN, "completed", "completed"),
            (TaskItemStatus.SUCCESS, "completed", "completed"),
            (TaskItemStatus.PARTIAL, "failed", "failed"),
            (TaskItemStatus.FAILED, "lock", "failed"),
            (TaskItemStatus.SKIPPED, "scanned", "completed"),
            (TaskItemStatus.CANCELLED, "cancelled", "cancelled"),
            (TaskItemStatus.WAITING_CONFIRM, "waiting_confirm", "waiting_confirm"),
            (TaskItemStatus.WAITING_RECOGNITION, "waiting_recognition", "waiting_recognition"),
            (TaskItemStatus.WAITING_METADATA, "waiting_metadata", "waiting_metadata"),
            (
                TaskItemStatus.WAITING_METADATA_CORRECTION,
                "waiting_metadata_correction",
                "waiting_metadata_correction",
            ),
            (
                TaskItemStatus.WAITING_CLASSIFICATION,
                "waiting_classification",
                "waiting_classification",
            ),
            (TaskItemStatus.PAUSED, "paused", "paused"),
            (TaskItemStatus.IGNORED, "ignored_by_operator", "ignored"),
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "preview", execute_authorized=False
                )
                for index, (status, raw_stage, expected_stage) in enumerate(cases):
                    item = self._item(task.task_id, f"item-{index}", status, raw_stage)
                    repository.upsert_item(item)
                    checkpoint = ProcessingCheckpointService(repository).get(item.item_id)
                    self.assertEqual(checkpoint.stage.value, expected_stage)
                    self.assertNotIn("retry", checkpoint.permitted_action_ids)
                    self.assertIsNotNone(checkpoint.refusal_reason or checkpoint.blocker)

    def test_partial_and_legacy_results_never_offer_automatic_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "organize", execute_authorized=True
                )
                partial = self._item(task.task_id, "partial", TaskItemStatus.PARTIAL, "failed")
                repository.upsert_item(partial)
                repository.append_result(
                    self._result(
                        task.task_id,
                        partial.item_id,
                        "partial-result",
                        "partial",
                        certainty="attempted_unverified",
                        completed=("MOVE",),
                        uncertain=("target_state",),
                    )
                )
                checkpoint = ProcessingCheckpointService(repository).get(partial.item_id)
                self.assertEqual(checkpoint.effect_certainty.value, "attempted_unverified")
                self.assertEqual(checkpoint.completed_operations, ("MOVE",))
                self.assertEqual(checkpoint.uncertain_effects, ("target_state",))
                self.assertEqual(checkpoint.retry_safety.value, "unknown")
                self.assertEqual(checkpoint.permitted_action_ids, ("investigate",))
                self.assertIn("replay_refused", checkpoint.refusal_reason)

                legacy = self._item(task.task_id, "legacy", TaskItemStatus.FAILED, "failed")
                repository.upsert_item(legacy)
                repository.append_result(
                    self._result(
                        task.task_id,
                        legacy.item_id,
                        "legacy-result",
                        "failed",
                        completed=("MOVE",),
                    )
                )
                legacy_checkpoint = ProcessingCheckpointService(repository).get(legacy.item_id)
                self.assertEqual(legacy_checkpoint.effect_certainty.value, "unknown")
                self.assertNotIn("retry", legacy_checkpoint.permitted_action_ids)

    def test_completion_path_persists_explicit_effect_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("organize", execute_authorized=True)
                item = self._item(task.task_id, "new", TaskItemStatus.PROCESSING, "pipeline")
                repository.upsert_item(item)
                execution = ExecutionResult(
                    ExecutionStatus.SUCCESS,
                    PlanOperation.MOVE,
                    item.source_path,
                    "Movies/new.mkv",
                    completed_operations=("MOVE",),
                    effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
                )
                coordinator.complete_item(
                    item, MediaOrganizerItemResult(item.source_path, execution=execution)
                )
                result = repository.list_results_for_item(item.item_id)[0]
                self.assertEqual(result.effect_certainty, "verified_complete")
                checkpoint = ProcessingCheckpointService(repository).get(item.item_id)
                self.assertEqual(checkpoint.effect_certainty.value, "verified_complete")

    def test_mutate_then_raise_is_unverified_and_never_retry_safe(self) -> None:
        class MutateThenRaiseStorage:
            storage_id = "source"

            def __init__(self) -> None:
                self.target_exists = False

            def exists(self, path: str) -> bool:
                return path in {"folder/uncertain.mkv", "Movies"} or (
                    path == "Movies/uncertain.mkv" and self.target_exists
                )

            @staticmethod
            def stat(path: str):
                return type("Entry", (), {"size": 5})()

            def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
                self.target_exists = True
                raise OSError("response lost after target mutation")

        storage = MutateThenRaiseStorage()
        plan = OrganizePlan(
            "source",
            "source",
            "folder/uncertain.mkv",
            "Movies/uncertain.mkv",
            "C",
            "naming-a",
            "classification-a",
            "organize-copy",
            operation=PlanOperation.COPY,
        )
        execution = OrganizerExecutor().execute(plan, {"source": storage}, execute=True)
        self.assertTrue(storage.target_exists)
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertEqual(
            execution.effect_certainty,
            ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
        )
        self.assertEqual(execution.uncertain_effects, ("mutation_outcome",))

        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create(
                    "organize",
                    execute_authorized=True,
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest="digest-1",
                )
                item = self._item(
                    task.task_id,
                    "uncertain",
                    TaskItemStatus.PROCESSING,
                    "pipeline",
                )
                repository.upsert_item(item)
                coordinator.complete_item(
                    item,
                    MediaOrganizerItemResult(
                        item.source_path,
                        plan=plan,
                        execution=execution,
                    ),
                )
                checkpoint = ProcessingCheckpointService(
                    repository,
                    snapshot_validator=lambda _snapshot_id, _digest: None,
                ).get(item.item_id)
                self.assertEqual(checkpoint.effect_certainty.value, "attempted_unverified")
                self.assertEqual(checkpoint.uncertain_effects, ("mutation_outcome",))
                self.assertEqual(checkpoint.retry_safety.value, "unknown")
                self.assertEqual(checkpoint.permitted_action_ids, ("investigate",))
                self.assertNotIn("retry", checkpoint.permitted_action_ids)

    def test_all_five_blocker_kinds_link_to_existing_resolution_surfaces(self) -> None:
        cases = (
            (
                TaskItemStatus.WAITING_RECOGNITION,
                "recognition_reviews",
                "recognition-1",
                "review_id",
            ),
            (TaskItemStatus.WAITING_METADATA, "metadata_reviews", "metadata-1", "review_id"),
            (
                TaskItemStatus.WAITING_METADATA_CORRECTION,
                "metadata_corrections",
                "correction-1",
                "review_id",
            ),
            (
                TaskItemStatus.WAITING_CLASSIFICATION,
                "classification_reviews",
                "classification-1",
                "review_id",
            ),
            (
                TaskItemStatus.WAITING_CONFIRM,
                "conflict_confirmations",
                "conflict-1",
                "confirmation_id",
            ),
        )
        expected = {
            "recognition_reviews": "recognition",
            "metadata_reviews": "metadata",
            "metadata_corrections": "metadata_correction",
            "classification_reviews": "classification",
            "conflict_confirmations": "conflict",
        }
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "preview", execute_authorized=False
                )
                for index, (status, table, identifier, _identifier_column) in enumerate(cases):
                    item = self._item(task.task_id, f"blocked-{index}", status, status.value)
                    repository.upsert_item(item)
                    now = (NOW + timedelta(seconds=index)).isoformat()
                    if table == "recognition_reviews":
                        repository._connection.execute(
                            "INSERT INTO recognition_reviews VALUES ("
                            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                identifier,
                                task.task_id,
                                item.item_id,
                                "source",
                                item.source_path,
                                "pending",
                                now,
                                now,
                                None,
                                None,
                                None,
                            ),
                        )
                    elif table == "metadata_reviews":
                        repository._connection.execute(
                            "INSERT INTO metadata_reviews VALUES ("
                            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                identifier,
                                task.task_id,
                                item.item_id,
                                "source",
                                item.source_path,
                                "C",
                                "metadata-c",
                                "query",
                                "ambiguous",
                                "pending",
                                now,
                                now,
                                None,
                                None,
                                None,
                                None,
                                None,
                                None,
                            ),
                        )
                    elif table == "metadata_corrections":
                        repository._connection.execute(
                            "INSERT INTO metadata_corrections VALUES ("
                            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                identifier,
                                task.task_id,
                                item.item_id,
                                "source",
                                item.source_path,
                                "C",
                                "metadata-c",
                                "123",
                                "query",
                                None,
                                "movie",
                                "not_found",
                                "pending",
                                now,
                                now,
                                None,
                                None,
                                None,
                                None,
                                None,
                                None,
                            ),
                        )
                    elif table == "classification_reviews":
                        repository._connection.execute(
                            "INSERT INTO classification_reviews VALUES ("
                            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                identifier,
                                task.task_id,
                                item.item_id,
                                "source",
                                item.source_path,
                                "C",
                                "classification-a",
                                "tmdb",
                                "123",
                                "movie",
                                "Example",
                                2020,
                                "pending",
                                now,
                                now,
                                None,
                                None,
                                None,
                                None,
                                None,
                                None,
                            ),
                        )
                    else:
                        repository._connection.execute(
                            "INSERT INTO conflict_confirmations VALUES ("
                            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                identifier,
                                task.task_id,
                                item.item_id,
                                "plan",
                                "DESTINATION_EXISTS",
                                "source",
                                item.source_path,
                                "target",
                                "Movies/example.mkv",
                                "manual",
                                "pending",
                                now,
                                now,
                                None,
                                None,
                                0,
                                None,
                                None,
                            ),
                        )
                    repository._connection.commit()
                    checkpoint = ProcessingCheckpointService(repository).get(item.item_id)
                    blocker = checkpoint.blocker
                    self.assertIsNotNone(blocker)
                    self.assertEqual(blocker.kind, expected[table])
                    self.assertEqual(blocker.blocker_id, identifier)
                    self.assertIn(identifier, blocker.resolution_path)

    def test_checkpoint_digest_is_stable_changes_and_survives_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "preview", execute_authorized=False
                )
                item = self._item(task.task_id, "stable", TaskItemStatus.FAILED, "failed")
                repository.upsert_item(item)
                service = ProcessingCheckpointService(repository)
                first = service.get(item.item_id).checkpoint_version
                self.assertEqual(first, service.get(item.item_id).checkpoint_version)
                repository.upsert_item(
                    replace(item, attempts=2, updated_at=NOW + timedelta(minutes=1))
                )
                changed = service.get(item.item_id).checkpoint_version
                self.assertNotEqual(first, changed)
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(
                    changed,
                    ProcessingCheckpointService(reopened).get(item.item_id).checkpoint_version,
                )

    def test_pre_checkpoint_result_rows_migrate_to_unknown_effect_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_version VALUES ('runtime', 22);
                CREATE TABLE task_results (
                    result_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, item_id TEXT NOT NULL,
                    source_storage_id TEXT NOT NULL, source_path TEXT NOT NULL,
                    destination_storage_id TEXT, destination_path TEXT, recognition_type TEXT,
                    provider TEXT, provider_id TEXT, metadata_policy_id TEXT,
                    naming_policy_id TEXT, classification_policy_id TEXT,
                    organize_policy_id TEXT, operation TEXT, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, title TEXT, error TEXT
                );
                INSERT INTO task_results VALUES (
                    'legacy-result', 'legacy-task', 'legacy-item', 'source', 'movie.mkv',
                    'target', 'Movies/movie.mkv', 'C', 'tmdb', '123', 'metadata-c',
                    'naming-a', 'classification-a', 'organize-move', 'MOVE', 'failed',
                    '2026-08-30T12:00:00+00:00', 'Movie', 'old error with no inference'
                );
                """
            )
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, 24)
                result = repository.list_results_for_item("legacy-item")[0]
                self.assertEqual(result.effect_certainty, "unknown")
                self.assertEqual(result.uncertain_effects, ())

    def test_pinned_snapshot_is_reported_and_missing_snapshot_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "preview",
                    execute_authorized=False,
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest="digest-1",
                )
                item = self._item(task.task_id, "pinned", TaskItemStatus.FAILED, "failed")
                repository.upsert_item(item)

                def unavailable(revision_id: str, digest: str) -> None:
                    raise RuntimeSnapshotUnavailable(
                        "snapshot unavailable",
                        revision_id=revision_id,
                        digest=digest,
                        reason="snapshot_missing",
                    )

                checkpoint = ProcessingCheckpointService(
                    repository, snapshot_validator=unavailable
                ).get(item.item_id)
                self.assertEqual(checkpoint.configuration.snapshot_id, "revision-1")
                self.assertEqual(checkpoint.configuration.snapshot_digest, "digest-1")
                self.assertFalse(checkpoint.configuration.resolvable)
                self.assertEqual(checkpoint.configuration.reason, "snapshot_missing")
                self.assertNotIn("retry", checkpoint.permitted_action_ids)

    def test_api_permissions_task_mismatch_and_summary_share_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "preview", execute_authorized=False
                )
                item = self._item(task.task_id, "api-item", TaskItemStatus.FAILED, "failed")
                repository.upsert_item(item)
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                )
                status, full = request(
                    api, "GET", f"/api/v1/tasks/{task.task_id}/items/{item.item_id}"
                )
                self.assertEqual(status, 200)
                status, detail = request(api, "GET", f"/api/v1/tasks/{task.task_id}")
                self.assertEqual(status, 200)
                blocker = full["blocker"] or {}
                self.assertEqual(
                    detail["items"][0]["checkpoint"],
                    {
                        "status": full["status"],
                        "stage": full["stage"],
                        "raw_stage": full["raw_stage"],
                        "blocker_kind": blocker.get("kind"),
                        "blocker_id": blocker.get("id"),
                        "effect_certainty": full["effects"]["certainty"],
                        "retry_safety": full["retry_safety"],
                        "permitted_action_ids": [item["action_id"] for item in full["actions"]],
                        "refusal_reason": full["refusal_reason"],
                        "checkpoint_version": full["checkpoint_version"],
                        "recovery_request": None,
                    },
                )
                self.assertEqual(
                    request(api, "GET", f"/api/v1/tasks/wrong/items/{item.item_id}")[0], 404
                )
                self.assertEqual(
                    request(api, "GET", f"/api/v1/tasks/{task.task_id}/items/missing")[0], 404
                )
                self.assertEqual(
                    request(
                        api, "GET", f"/api/v1/tasks/{task.task_id}/items/{item.item_id}", token=None
                    )[0],
                    401,
                )
                self.assertEqual(
                    request_with_query(
                        api, f"/api/v1/tasks/{task.task_id}/items/{item.item_id}", "unexpected=1"
                    )[0],
                    400,
                )

    def test_read_projection_is_zero_mutation_and_operator_web_is_api_driven(self) -> None:
        class SpyRepository:
            def __init__(self, context):
                self.context = context
                self.calls = 0

            def get_processing_checkpoint_context(self, item_id, **kwargs):
                self.calls += 1
                return self.context

        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "preview", execute_authorized=False
                )
                item = self._item(task.task_id, "spy", TaskItemStatus.SUCCESS, "completed")
                repository.upsert_item(item)
                context = repository.get_processing_checkpoint_context(item.item_id)
                spy = SpyRepository(context)
                checkpoint = ProcessingCheckpointService(spy).get(item.item_id)
                self.assertEqual(spy.calls, 1)
                self.assertEqual(checkpoint.permitted_action_ids, ())
                self.assertIn("Task item checkpoint", APP_JS.decode())
                self.assertIn("/api/v1/tasks/${encodeURIComponent(taskId)}/items/", APP_JS.decode())
                self.assertIn("Effect certainty", APP_JS.decode())
                self.assertIn("Retry safety", APP_JS.decode())


if __name__ == "__main__":
    unittest.main()
