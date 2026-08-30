from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.domain.recognition_review import RecognitionReviewStatus
from mediaflow.domain.recovery import RecoveryAdmissionError, RecoveryAdmissionReason
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentResultRecord, TaskItemStatus
from mediaflow.infrastructure.metadata_provider_bootstrap import LazyMetadataProviderRegistryFactory
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
SNAPSHOT_ID = "revision-23"
SNAPSHOT_DIGEST = "a" * 64


def api_request(
    api,
    method: str,
    path: str,
    *,
    body=None,
    token="operator-token",
    query="",
):
    statuses: list[str] = []
    raw = b"" if body is None else json.dumps(body).encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(raw),
    }
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    payload = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


class RecoveryAdmissionTests(unittest.TestCase):
    @staticmethod
    def _validator(snapshot_id: str, digest: str) -> None:
        if snapshot_id != SNAPSHOT_ID or digest != SNAPSHOT_DIGEST:
            raise RuntimeSnapshotUnavailable(
                "snapshot unavailable",
                revision_id=snapshot_id,
                digest=digest,
                reason="snapshot_missing",
            )

    @staticmethod
    def _task(
        repository,
        *,
        pinned=True,
        snapshot_id=SNAPSHOT_ID,
        snapshot_digest=SNAPSHOT_DIGEST,
    ):
        coordinator = PersistentTaskCoordinator(repository, repository)
        kwargs = {
            "configuration_snapshot_id": snapshot_id,
            "configuration_snapshot_digest": snapshot_digest,
        }
        if not pinned:
            kwargs = {}
        return coordinator, coordinator.create("organize", execute_authorized=False, **kwargs)

    @staticmethod
    def _failed_item(
        repository,
        task,
        item_id="item-1",
        *,
        status=TaskItemStatus.FAILED,
        certainty="none",
        error="original failure",
        source_path="folder/movie.mkv",
    ):
        coordinator = PersistentTaskCoordinator(repository, repository)
        if source_path == "folder/movie.mkv":
            source_path = f"folder/{item_id}.mkv"
        item = coordinator.begin_item(
            task.task_id,
            "source",
            "resources",
            source_path,
            source_path,
        )
        item = replace(item, status=status, stage="failed", error=error)
        repository.upsert_item(item)
        result = PersistentResultRecord(
            f"result-{item.item_id}",
            task.task_id,
            item.item_id,
            "source",
            source_path,
            "target",
            "Movies/movie.mkv",
            "C",
            "tmdb",
            "123",
            "metadata-c",
            "naming-a",
            "classification-a",
            "organize-move",
            "MOVE",
            status.value,
            NOW,
            title="Movie",
            error="result failure",
            completed_operations=("MOVE",) if certainty == "attempted_unverified" else (),
            effect_certainty=certainty,
            uncertain_effects=("mutation_outcome",) if certainty == "attempted_unverified" else (),
        )
        repository.append_result(result)
        return item, result

    def _gate(self, repository):
        return RecoveryAdmissionService(
            repository,
            snapshot_validator=self._validator,
        )

    def test_retry_admission_is_version_bound_audited_and_preserves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator, task = self._task(repository)
                item, result = self._failed_item(repository, task)
                gate = self._gate(repository)
                checkpoint = gate.checkpoint_service.get(item.item_id, task_id=task.task_id)
                self.assertEqual(checkpoint.permitted_action_ids, ("retry",))
                admitted = gate.admit(
                    task.task_id,
                    item.item_id,
                    action_id="retry",
                    expected_checkpoint_version=checkpoint.checkpoint_version,
                    actor="operator",
                    note=" retry the safe analysis ",
                )
                self.assertEqual(admitted.checkpoint_version, checkpoint.checkpoint_version)
                self.assertEqual(admitted.configuration_snapshot_id, SNAPSHOT_ID)
                self.assertEqual(admitted.configuration_snapshot_digest, SNAPSHOT_DIGEST)
                self.assertEqual(admitted.source_storage_id, "source")
                self.assertEqual(admitted.source_path, "folder/item-1.mkv")
                self.assertEqual(admitted.note, "retry the safe analysis")
                self.assertIn("no execute", admitted.authority_statement)
                self.assertIn("no overwrite", admitted.authority_statement)
                self.assertIn("no delete", admitted.authority_statement)
                self.assertIn("no source-cleanup", admitted.authority_statement)
                self.assertIn("no rollback", admitted.authority_statement)

                stored_item = repository.get_item(item.item_id)
                self.assertEqual(stored_item.status, TaskItemStatus.PENDING)
                self.assertEqual(stored_item.stage, "task_retry_requested")
                self.assertEqual(stored_item.error, item.error)
                self.assertEqual(repository.list_results_for_item(item.item_id)[0], result)
                retry_audit = repository.list_task_retry_audit(item.item_id)
                self.assertEqual(len(retry_audit), 1)
                self.assertEqual(retry_audit[0].decision_id, admitted.request_id)
                requests = repository.list_recovery_requests(item.item_id)
                self.assertEqual(requests, (admitted,))
                current = ProcessingCheckpointService(
                    repository,
                    snapshot_validator=self._validator,
                ).get(item.item_id)
                self.assertEqual(current.active_recovery_request.request_id, admitted.request_id)
                self.assertIn("recovery_request", [value.kind for value in current.audits])
                self.assertEqual(current.latest_result.effect_certainty.value, "none")
                self.assertEqual(current.latest_result.recognition_type, "C")
                self.assertEqual(current.latest_result.naming_policy_id, "naming-a")
                self.assertEqual(current.latest_result.classification_policy_id, "classification-a")
                self.assertEqual(
                    coordinator.retryable_items(task.task_id, failed_only=False)[0].item_id,
                    item.item_id,
                )

    def test_partial_and_terminal_items_cannot_be_replayed(self) -> None:
        cases = (
            (TaskItemStatus.PARTIAL, "none"),
            (TaskItemStatus.PARTIAL, "attempted_unverified"),
            (TaskItemStatus.PARTIAL, "unknown"),
            (TaskItemStatus.SUCCESS, "verified_complete"),
            (TaskItemStatus.DRY_RUN, "none"),
            (TaskItemStatus.SKIPPED, "unknown"),
            (TaskItemStatus.IGNORED, "unknown"),
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task = self._task(repository)
                gate = self._gate(repository)
                for index, (status, certainty) in enumerate(cases):
                    with self.subTest(status=status, certainty=certainty):
                        item, _ = self._failed_item(
                            repository,
                            task,
                            item_id=f"item-{index}",
                            status=status,
                            certainty=certainty,
                        )
                        checkpoint = gate.checkpoint_service.get(item.item_id)
                        self.assertNotIn("retry", checkpoint.permitted_action_ids)
                        with self.assertRaises(RecoveryAdmissionError) as raised:
                            gate.admit(
                                task.task_id,
                                item.item_id,
                                action_id="retry",
                                expected_checkpoint_version=checkpoint.checkpoint_version,
                                actor="operator",
                            )
                        self.assertIn(
                            raised.exception.reason,
                            {
                                RecoveryAdmissionReason.INVALID_ACTION,
                                RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                            },
                        )
                        self.assertEqual(repository.get_item(item.item_id).status, status)
                        self.assertEqual(repository.list_recovery_requests(item.item_id), ())

    def test_stale_version_and_duplicate_return_bounded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task = self._task(repository)
                item, _ = self._failed_item(repository, task)
                gate = self._gate(repository)
                first_checkpoint = gate.checkpoint_service.get(item.item_id)
                repository.upsert_item(
                    replace(item, attempts=2, error="new failure", updated_at=NOW)
                )
                with self.assertRaises(RecoveryAdmissionError) as raised:
                    gate.admit(
                        task.task_id,
                        item.item_id,
                        action_id="retry",
                        expected_checkpoint_version=first_checkpoint.checkpoint_version,
                        actor="operator",
                    )
                self.assertEqual(raised.exception.reason, RecoveryAdmissionReason.STALE_CHECKPOINT)
                self.assertEqual(repository.list_recovery_requests(item.item_id), ())
                current = gate.checkpoint_service.get(item.item_id)
                admitted = gate.admit(
                    task.task_id,
                    item.item_id,
                    action_id="retry",
                    expected_checkpoint_version=current.checkpoint_version,
                    actor="operator",
                )
                with self.assertRaises(RecoveryAdmissionError) as duplicate:
                    gate.admit(
                        task.task_id,
                        item.item_id,
                        action_id="retry",
                        expected_checkpoint_version=admitted.checkpoint_version,
                        actor="operator-2",
                    )
                self.assertEqual(
                    duplicate.exception.reason,
                    RecoveryAdmissionReason.DUPLICATE_ACTIVE_REQUEST,
                )
                self.assertEqual(duplicate.exception.existing_request, admitted)
                self.assertEqual(len(repository.list_task_retry_audit(item.item_id)), 1)

                with self.assertRaises(RecoveryAdmissionError) as mismatch:
                    gate.admit(
                        "different-task",
                        item.item_id,
                        action_id="retry",
                        expected_checkpoint_version=admitted.checkpoint_version,
                        actor="operator-3",
                    )
                self.assertEqual(
                    mismatch.exception.reason,
                    RecoveryAdmissionReason.ITEM_TASK_MISMATCH,
                )

    def test_missing_and_unresolvable_snapshots_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, unpinned = self._task(repository, pinned=False)
                item, _ = self._failed_item(repository, unpinned, item_id="unpinned")
                gate = RecoveryAdmissionService(repository)
                checkpoint = gate.checkpoint_service.get(item.item_id)
                with self.assertRaises(RecoveryAdmissionError) as missing:
                    gate.admit(
                        unpinned.task_id,
                        item.item_id,
                        action_id="retry",
                        expected_checkpoint_version=checkpoint.checkpoint_version,
                        actor="operator",
                    )
                self.assertEqual(
                    missing.exception.reason,
                    RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE,
                )

                _, task = self._task(repository)
                item, _ = self._failed_item(repository, task, item_id="unreadable")

                def unavailable(_snapshot_id, _digest):
                    raise RuntimeSnapshotUnavailable(
                        "private exception text must not escape",
                        reason="snapshot_missing",
                    )

                gate = RecoveryAdmissionService(repository, snapshot_validator=unavailable)
                checkpoint = gate.checkpoint_service.get(item.item_id)
                with self.assertRaises(RecoveryAdmissionError) as unreadable:
                    gate.admit(
                        task.task_id,
                        item.item_id,
                        action_id="retry",
                        expected_checkpoint_version=checkpoint.checkpoint_version,
                        actor="operator",
                    )
                self.assertEqual(
                    unreadable.exception.reason,
                    RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE,
                )
                self.assertEqual(repository.list_recovery_requests(item.item_id), ())

    def test_ignore_requires_pending_review_and_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, task = self._task(repository)
                coordinator = PersistentTaskCoordinator(repository, repository)
                item = coordinator.begin_item(
                    task.task_id, "source", "resources", "folder/review.mkv", "folder/review.mkv"
                )
                item = replace(
                    item,
                    status=TaskItemStatus.WAITING_RECOGNITION,
                    stage="waiting_recognition",
                    error="recognition needs operator",
                )
                repository.upsert_item(item)
                now = NOW.isoformat()
                repository._connection.execute(
                    "INSERT INTO recognition_reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "recognition-review",
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
                repository._connection.commit()
                gate = self._gate(repository)
                checkpoint = gate.checkpoint_service.get(item.item_id)
                self.assertEqual(
                    checkpoint.permitted_action_ids,
                    ("resolve_recognition", "ignore"),
                )
                self.assertTrue(
                    next(
                        value for value in checkpoint.actions if value.action_id == "ignore"
                    ).admissible
                )
                admitted = gate.admit(
                    task.task_id,
                    item.item_id,
                    action_id="ignore",
                    expected_checkpoint_version=checkpoint.checkpoint_version,
                    actor="operator",
                    note="ignore this review",
                )
                self.assertEqual(admitted.review_kind, "recognition")
                self.assertEqual(admitted.review_id, "recognition-review")
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.IGNORED)
                self.assertEqual(repository.get_item(item.item_id).error, item.error)
                self.assertEqual(
                    repository.get_recognition_review("recognition-review").status,
                    RecognitionReviewStatus.IGNORED,
                )
                self.assertEqual(
                    repository.list_manual_ignore_audit(item.item_id)[0].decision_id,
                    admitted.request_id,
                )
                self.assertEqual(
                    gate.checkpoint_service.get(item.item_id).active_recovery_request,
                    admitted,
                )

                _, no_review_task = self._task(repository)
                no_review_item = coordinator.begin_item(
                    no_review_task.task_id,
                    "source",
                    "resources",
                    "folder/no-review.mkv",
                    "no-review",
                )
                no_review_item = replace(
                    no_review_item,
                    status=TaskItemStatus.WAITING_RECOGNITION,
                    stage="waiting_recognition",
                )
                repository.upsert_item(no_review_item)
                no_review_checkpoint = gate.checkpoint_service.get(no_review_item.item_id)
                self.assertNotIn("ignore", no_review_checkpoint.permitted_action_ids)
                with self.assertRaises(RecoveryAdmissionError):
                    gate.admit(
                        no_review_task.task_id,
                        no_review_item.item_id,
                        action_id="ignore",
                        expected_checkpoint_version=no_review_checkpoint.checkpoint_version,
                        actor="operator",
                    )

    def test_atomic_insert_failure_rolls_back_item_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, task = self._task(repository)
                item, _ = self._failed_item(repository, task)
                repository._connection.execute(
                    """CREATE TRIGGER reject_recovery BEFORE INSERT ON recovery_requests
                    BEGIN SELECT RAISE(ABORT, 'injected failure'); END"""
                )
                repository._connection.commit()
                gate = self._gate(repository)
                checkpoint = gate.checkpoint_service.get(item.item_id)
                with self.assertRaises(sqlite3.IntegrityError):
                    gate.admit(
                        task.task_id,
                        item.item_id,
                        action_id="retry",
                        expected_checkpoint_version=checkpoint.checkpoint_version,
                        actor="operator",
                    )
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.FAILED)
                self.assertEqual(repository.get_item(item.item_id).error, item.error)
                self.assertEqual(repository.list_task_retry_audit(item.item_id), ())
                self.assertEqual(repository.list_recovery_requests(item.item_id), ())

    def test_api_recovery_route_is_authenticated_and_uses_same_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task = self._task(repository)
                item, _ = self._failed_item(repository, task)
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "operator",
                            "operator-token",
                            frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
                        ),
                        ResolvedApiPrincipal(
                            "viewer",
                            "viewer-token",
                            frozenset({ApiPermission.READ}),
                        ),
                    ),
                    recovery_snapshot_validator=self._validator,
                )
                checkpoint_status, checkpoint = api_request(
                    api,
                    "GET",
                    f"/api/v1/tasks/{task.task_id}/items/{item.item_id}",
                )
                self.assertEqual(checkpoint_status, 200)
                status, payload = api_request(
                    api,
                    "POST",
                    f"/api/v1/tasks/{task.task_id}/items/{item.item_id}/recovery",
                    body={
                        "actionId": "retry",
                        "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    payload["request"]["checkpoint_version"],
                    checkpoint["checkpoint_version"],
                )
                self.assertEqual(payload["sideEffects"], "none")
                status, after = api_request(
                    api,
                    "GET",
                    f"/api/v1/tasks/{task.task_id}/items/{item.item_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(after["recovery_request"]["request_id"], payload["requestId"])
                status, denied = api_request(
                    api,
                    "POST",
                    f"/api/v1/tasks/{task.task_id}/items/{item.item_id}/recovery",
                    body={
                        "actionId": "retry",
                        "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                    },
                    token="viewer-token",
                )
                self.assertEqual(status, 403)
                self.assertEqual(denied["error"]["code"], "forbidden")

    def test_api_recovery_route_maps_refusals_and_bounds_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task = self._task(repository)
                item, _ = self._failed_item(repository, task, item_id="api-base")
                _, other_task = self._task(repository)
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "operator",
                            "operator-token",
                            frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
                        ),
                        ResolvedApiPrincipal(
                            "viewer",
                            "viewer-token",
                            frozenset({ApiPermission.READ}),
                        ),
                    ),
                    recovery_snapshot_validator=self._validator,
                )

                def route(task_id: str, item_id: str) -> str:
                    return f"/api/v1/tasks/{task_id}/items/{item_id}/recovery"

                def checkpoint(task_id: str, item_id: str) -> dict[str, object]:
                    status, payload = api_request(
                        api,
                        "GET",
                        f"/api/v1/tasks/{task_id}/items/{item_id}",
                    )
                    self.assertEqual(status, 200)
                    return payload

                def post(
                    task_id: str,
                    item_id: str,
                    body: dict[str, object],
                    *,
                    token="operator-token",
                    query="",
                ) -> tuple[int, dict[str, object]]:
                    return api_request(
                        api,
                        "POST",
                        route(task_id, item_id),
                        body=body,
                        token=token,
                        query=query,
                    )

                def assert_not_found(payload: dict[str, object]) -> None:
                    self.assertEqual(payload["error"]["code"], "not_found")
                    details = payload["error"].get("details", {})
                    self.assertNotIn("reason", details)

                base = checkpoint(task.task_id, item.item_id)
                valid_body = {
                    "actionId": "retry",
                    "expectedCheckpointVersion": base["checkpoint_version"],
                }

                status, payload = post(
                    task.task_id,
                    item.item_id,
                    valid_body,
                    token=None,
                )
                self.assertEqual(status, 401)
                self.assertEqual(payload["error"]["code"], "unauthorized")

                status, payload = post("missing-task", item.item_id, valid_body)
                self.assertEqual(status, 404)
                assert_not_found(payload)

                status, payload = post(task.task_id, "missing-item", valid_body)
                self.assertEqual(status, 404)
                assert_not_found(payload)

                status, payload = post(other_task.task_id, item.item_id, valid_body)
                self.assertEqual(status, 404)
                assert_not_found(payload)

                refused, _ = self._failed_item(
                    repository,
                    task,
                    item_id="api-refused",
                    status=TaskItemStatus.PARTIAL,
                    certainty="attempted_unverified",
                )
                refused_checkpoint = checkpoint(task.task_id, refused.item_id)
                status, payload = post(
                    task.task_id,
                    refused.item_id,
                    {
                        "actionId": "investigate",
                        "expectedCheckpointVersion": refused_checkpoint["checkpoint_version"],
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(
                    payload["error"]["details"]["reason"],
                    RecoveryAdmissionReason.ACTION_NOT_PERMITTED.value,
                )
                self.assertEqual(payload["error"]["details"]["sideEffects"], "none")
                self.assertEqual(repository.list_recovery_requests(refused.item_id), ())

                stale, _ = self._failed_item(repository, task, item_id="api-stale")
                stale_checkpoint = checkpoint(task.task_id, stale.item_id)
                repository.upsert_item(
                    replace(stale, attempts=2, error="new failure", updated_at=NOW)
                )
                current_stale = checkpoint(task.task_id, stale.item_id)
                status, payload = post(
                    task.task_id,
                    stale.item_id,
                    {
                        "actionId": "retry",
                        "expectedCheckpointVersion": stale_checkpoint["checkpoint_version"],
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(
                    payload["error"]["details"]["reason"],
                    RecoveryAdmissionReason.STALE_CHECKPOINT.value,
                )
                self.assertEqual(
                    payload["error"]["details"]["currentCheckpointVersion"],
                    current_stale["checkpoint_version"],
                )
                self.assertEqual(repository.list_recovery_requests(stale.item_id), ())

                duplicate, _ = self._failed_item(repository, task, item_id="api-duplicate")
                duplicate_checkpoint = checkpoint(task.task_id, duplicate.item_id)
                duplicate_body = {
                    "actionId": "retry",
                    "expectedCheckpointVersion": duplicate_checkpoint["checkpoint_version"],
                }
                status, first = post(task.task_id, duplicate.item_id, duplicate_body)
                self.assertEqual(status, 200)
                status, payload = post(task.task_id, duplicate.item_id, duplicate_body)
                self.assertEqual(status, 409)
                details = payload["error"]["details"]
                self.assertEqual(
                    details["reason"],
                    RecoveryAdmissionReason.DUPLICATE_ACTIVE_REQUEST.value,
                )
                self.assertEqual(details["existingRequest"]["request_id"], first["requestId"])
                self.assertEqual(details["nextAction"], first["nextAction"])
                self.assertEqual(len(repository.list_task_retry_audit(duplicate.item_id)), 1)
                self.assertEqual(len(repository.list_recovery_requests(duplicate.item_id)), 1)

                _, unavailable_task = self._task(
                    repository,
                    snapshot_id="missing-revision",
                    snapshot_digest="b" * 64,
                )
                unavailable, _ = self._failed_item(
                    repository, unavailable_task, item_id="api-unavailable"
                )
                unavailable_checkpoint = checkpoint(unavailable_task.task_id, unavailable.item_id)
                self.assertFalse(unavailable_checkpoint["configuration"]["resolvable"])
                status, payload = post(
                    unavailable_task.task_id,
                    unavailable.item_id,
                    {
                        "actionId": "retry",
                        "expectedCheckpointVersion": unavailable_checkpoint["checkpoint_version"],
                    },
                )
                self.assertEqual(status, 503)
                self.assertEqual(
                    payload["error"]["details"]["reason"],
                    RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE.value,
                )
                self.assertEqual(repository.list_recovery_requests(unavailable.item_id), ())

                unknown_action, _ = self._failed_item(repository, task, item_id="api-unknown")
                unknown_checkpoint = checkpoint(task.task_id, unknown_action.item_id)
                status, payload = post(
                    task.task_id,
                    unknown_action.item_id,
                    {
                        "actionId": "not-a-real-action",
                        "expectedCheckpointVersion": unknown_checkpoint["checkpoint_version"],
                    },
                )
                self.assertEqual(status, 400)
                self.assertEqual(
                    payload["error"]["details"]["reason"],
                    RecoveryAdmissionReason.INVALID_ACTION.value,
                )

                malformed, _ = self._failed_item(repository, task, item_id="api-malformed")
                status, payload = post(
                    task.task_id,
                    malformed.item_id,
                    {"actionId": "retry", "expectedCheckpointVersion": "bad"},
                )
                self.assertEqual(status, 400)
                self.assertEqual(
                    payload["error"]["details"]["reason"],
                    RecoveryAdmissionReason.INVALID_VERSION.value,
                )

                overlong, _ = self._failed_item(repository, task, item_id="api-overlong")
                overlong_checkpoint = checkpoint(task.task_id, overlong.item_id)
                status, payload = post(
                    task.task_id,
                    overlong.item_id,
                    {
                        "actionId": "retry",
                        "expectedCheckpointVersion": overlong_checkpoint["checkpoint_version"],
                        "note": "x" * 501,
                    },
                )
                self.assertEqual(status, 400)
                self.assertEqual(
                    payload["error"]["details"]["reason"],
                    RecoveryAdmissionReason.INVALID_INPUT.value,
                )

                unexpected_field, _ = self._failed_item(
                    repository, task, item_id="api-unexpected-field"
                )
                unexpected_checkpoint = checkpoint(task.task_id, unexpected_field.item_id)
                status, payload = post(
                    task.task_id,
                    unexpected_field.item_id,
                    {
                        "actionId": "retry",
                        "expectedCheckpointVersion": unexpected_checkpoint["checkpoint_version"],
                        "actor": "should-not-be-accepted",
                    },
                )
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], "invalid_request")
                self.assertEqual(repository.list_recovery_requests(unexpected_field.item_id), ())

                unexpected_query, _ = self._failed_item(
                    repository, task, item_id="api-unexpected-query"
                )
                unexpected_query_checkpoint = checkpoint(task.task_id, unexpected_query.item_id)
                status, payload = post(
                    task.task_id,
                    unexpected_query.item_id,
                    {
                        "actionId": "retry",
                        "expectedCheckpointVersion": unexpected_query_checkpoint[
                            "checkpoint_version"
                        ],
                    },
                    query="unexpected=1",
                )
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], "invalid_request")
                self.assertEqual(repository.list_recovery_requests(unexpected_query.item_id), ())

                permission, _ = self._failed_item(repository, task, item_id="api-permission")
                permission_checkpoint = checkpoint(task.task_id, permission.item_id)
                status, payload = post(
                    task.task_id,
                    permission.item_id,
                    {
                        "actionId": "retry",
                        "expectedCheckpointVersion": permission_checkpoint["checkpoint_version"],
                    },
                    token="viewer-token",
                )
                self.assertEqual(status, 403)
                self.assertEqual(payload["error"]["code"], "forbidden")
                self.assertEqual(repository.list_recovery_requests(permission.item_id), ())

                audit = repository.list_security_audit(limit=1000)
                self.assertTrue(
                    any(
                        value.route == "/api/v1/tasks/{task_id}/items/{item_id}/recovery"
                        and value.action == "recovery-admission"
                        and value.outcome == "denied"
                        and value.http_status == 409
                        for value in audit
                    )
                )

    def test_recovery_admission_falsifies_storage_provider_and_durable_side_effects(self) -> None:
        class RecordingValidator:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def __call__(self, snapshot_id: str, digest: str) -> None:
                self.calls.append((snapshot_id, digest))
                if snapshot_id != SNAPSHOT_ID or digest != SNAPSHOT_DIGEST:
                    raise RuntimeSnapshotUnavailable(
                        "snapshot unavailable",
                        revision_id=snapshot_id,
                        digest=digest,
                        reason="snapshot_missing",
                    )

        def lock_rows(repository):
            rows = repository._connection.execute(
                "SELECT storage_id, path, task_id, acquired_at FROM file_locks "
                "ORDER BY storage_id, path, task_id"
            ).fetchall()
            return tuple(tuple(row) for row in rows)

        def tree_snapshot(root: Path) -> tuple[tuple[str, int, int], ...]:
            if not root.is_dir():
                return ()
            rows: list[tuple[str, int, int]] = []
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    stat = path.stat()
                    rows.append((str(path.relative_to(root)), stat.st_size, stat.st_mtime_ns))
            return tuple(rows)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            destination_root = root / "destination"
            source_file = source_root / "folder" / "zero-mutation.mkv"
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(b"fake media payload")
            destination_root.mkdir()
            source_before = tree_snapshot(source_root)
            destination_before = tree_snapshot(destination_root)

            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                _, task = self._task(repository)
                item, _ = self._failed_item(repository, task, item_id="zero-mutation")
                validator = RecordingValidator()
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "operator",
                            "operator-token",
                            frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
                        ),
                    ),
                    recovery_snapshot_validator=validator,
                )
                task_before = repository.get_task(task.task_id)
                tasks_before = repository.list_tasks()
                jobs_before = repository.list_jobs()
                results_before = repository.list_results(task.task_id)
                locks_before = lock_rows(repository)

                checkpoint_status, checkpoint = api_request(
                    api,
                    "GET",
                    f"/api/v1/tasks/{task.task_id}/items/{item.item_id}",
                )
                self.assertEqual(checkpoint_status, 200)
                with (
                    patch.object(
                        RuntimeConfiguration,
                        "create_storages",
                        side_effect=AssertionError("recovery admission constructed Storage"),
                    ),
                    patch.object(
                        LazyMetadataProviderRegistryFactory,
                        "__call__",
                        side_effect=AssertionError(
                            "recovery admission constructed metadata Provider"
                        ),
                    ),
                ):
                    status, payload = api_request(
                        api,
                        "POST",
                        f"/api/v1/tasks/{task.task_id}/items/{item.item_id}/recovery",
                        body={
                            "actionId": "retry",
                            "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                        },
                    )
                self.assertEqual(status, 200)
                self.assertEqual(payload["sideEffects"], "none")
                self.assertTrue(validator.calls)
                self.assertEqual(tree_snapshot(source_root), source_before)
                self.assertEqual(tree_snapshot(destination_root), destination_before)
                self.assertEqual(repository.get_task(task.task_id), task_before)
                self.assertEqual(repository.list_tasks(), tasks_before)
                self.assertEqual(repository.list_jobs(), jobs_before)
                self.assertEqual(repository.list_results(task.task_id), results_before)
                self.assertEqual(lock_rows(repository), locks_before)
                self.assertEqual(len(repository.list_results(task.task_id)), len(results_before))

    def test_recovery_table_migrates_forward_without_rewriting_existing_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator, task = self._task(repository)
                item, _ = self._failed_item(repository, task)
                repository._connection.execute("DROP INDEX one_active_recovery_request")
                repository._connection.execute("DROP INDEX recovery_requests_item_requested")
                repository._connection.execute("DROP TABLE recovery_requests")
                repository._connection.execute(
                    "UPDATE schema_version SET version=23 WHERE component='runtime'"
                )
                repository._connection.commit()
                self.assertEqual(repository.get_item(item.item_id).error, "original failure")
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.schema_version, SCHEMA_VERSION)
                tables = reopened._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='recovery_requests'"
                ).fetchall()
                self.assertEqual(len(tables), 1)
                self.assertEqual(reopened.get_item(item.item_id).error, "original failure")
                self.assertEqual(reopened.list_recovery_requests(item.item_id), ())

    def test_audit_note_redacts_obvious_secret_and_private_path_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, task = self._task(repository)
                item, _ = self._failed_item(repository, task)
                gate = self._gate(repository)
                checkpoint = gate.checkpoint_service.get(item.item_id)
                admitted = gate.admit(
                    task.task_id,
                    item.item_id,
                    action_id="retry",
                    expected_checkpoint_version=checkpoint.checkpoint_version,
                    actor="operator",
                    note="token=do-not-persist see https://private.example/home /home/user/media",
                )
                self.assertEqual(admitted.note, "[redacted] see [redacted] [redacted]")
                self.assertNotIn(
                    "do-not-persist", repr(repository.list_recovery_requests(item.item_id))
                )
                self.assertNotIn("private.example", repr(admitted.document()))

    def test_source_scope_must_remain_storage_relative(self) -> None:
        unsafe_paths = (
            "/home/user/media/movie.mkv",
            "C:/Users/user/media/movie.mkv",
            "https://private.example/media/movie.mkv",
            "~/media/movie.mkv",
        )
        for source_path in unsafe_paths:
            with self.subTest(source_path=source_path), tempfile.TemporaryDirectory() as directory:
                with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                    _, task = self._task(repository)
                    item, _ = self._failed_item(repository, task, source_path=source_path)
                    gate = self._gate(repository)
                    checkpoint = gate.checkpoint_service.get(item.item_id)
                    with self.assertRaises(RecoveryAdmissionError) as raised:
                        gate.admit(
                            task.task_id,
                            item.item_id,
                            action_id="retry",
                            expected_checkpoint_version=checkpoint.checkpoint_version,
                            actor="operator",
                        )
                    self.assertEqual(raised.exception.reason, RecoveryAdmissionReason.INVALID_INPUT)
                    self.assertEqual(repository.list_recovery_requests(item.item_id), ())


if __name__ == "__main__":
    unittest.main()
