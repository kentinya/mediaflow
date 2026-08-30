"""Shared bounded batch recovery continuation service."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.recovery_continuation import RecoveryContinuationService
from mediaflow.domain.automation import AutomationQueueFull
from mediaflow.domain.recovery import RecoveryAdmissionError
from mediaflow.domain.recovery_batch import (
    RecoveryBatch,
    RecoveryBatchItem,
    RecoveryBatchItemStatus,
    RecoveryBatchStatus,
)
from mediaflow.domain.recovery_continuation import RecoveryContinuationError

_REFRESH = "refresh the Task item checkpoint and select it again"
_SENSITIVE_ACTOR = re.compile(
    r"(?ix)(?:bearer\s+\S+|"
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)\s*[:=]\s*\S+)"
)
_PRIVATE_ENDPOINT = re.compile(r"(?i)(?:https?|s3|file)://[^\s]+")
_ABSOLUTE_PATH = re.compile(r"(?<![\w])(?:/[\w.~-]+(?:/[\w. .~+\-]+)*|[A-Za-z]:[\\/][^\s]+)")


class RecoveryBatchContinuationService:
    MAX_BATCH_SIZE = 100
    MAX_ACTOR = 200

    def __init__(self, repository, *, continuation_service=None, admission_service=None):
        self._repository = repository
        self._continuation_service = continuation_service or RecoveryContinuationService(repository)
        self._admission_service = admission_service or RecoveryAdmissionService(repository)

    def submit(
        self,
        task_id: str,
        selections: list[dict[str, str]] | tuple[dict[str, str], ...],
        *,
        actor: str,
        maximum_active_jobs: int,
    ) -> RecoveryBatch:
        task_id = self._required_text(task_id, "Task ID")
        actor = self._actor(actor)
        if not isinstance(selections, (list, tuple)) or not selections:
            raise ValueError("batch recovery selection must not be empty")
        if len(selections) > self.MAX_BATCH_SIZE:
            raise ValueError(
                f"batch recovery selection must not exceed {self.MAX_BATCH_SIZE} items"
            )
        normalized: list[tuple[str, str]] = []
        seen: set[str] = set()
        for value in selections:
            if not isinstance(value, dict):
                raise ValueError("batch recovery selection items must be objects")
            if set(value) != {"itemId", "expectedCheckpointVersion"}:
                raise ValueError(
                    "batch recovery selection items require only itemId and "
                    "expectedCheckpointVersion"
                )
            item_id = self._required_text(value["itemId"], "TaskItem ID")
            version = self._required_text(value["expectedCheckpointVersion"], "checkpoint version")
            if len(version) != 64 or any(char not in "0123456789abcdef" for char in version):
                raise ValueError("checkpoint version must be a lowercase SHA-256 digest")
            if item_id in seen:
                raise ValueError("batch recovery selection contains duplicate TaskItem IDs")
            seen.add(item_id)
            normalized.append((item_id, version))
        normalized.sort()

        task = self._repository.get_task(task_id)
        if task is None:
            raise LookupError(f"task {task_id!r} was not found")
        now = datetime.now(UTC)
        batch_id = str(uuid4())
        initial_items = tuple(
            RecoveryBatchItem(
                str(uuid4()),
                batch_id,
                task_id,
                item_id,
                version,
                RecoveryBatchItemStatus.SELECTED,
                now,
                now,
            )
            for item_id, version in normalized
        )
        initial_items = tuple(replace(item, batch_id=batch_id) for item in initial_items)
        self._repository.create_recovery_batch(
            RecoveryBatch(
                batch_id,
                task_id,
                actor,
                now,
                now,
                RecoveryBatchStatus.QUEUED,
                initial_items,
            )
        )

        self._drive(initial_items, actor, maximum_active_jobs)
        return self._repository.get_recovery_batch(batch_id)

    def resume(self, batch_id: str, *, actor: str, maximum_active_jobs: int) -> RecoveryBatch:
        """Deterministically finish children still durably `selected` after reload.

        A repository/transaction failure while recording one child's outcome must
        never strand the parent. Resume re-drives exactly the children that never
        reached a terminal or waiting outcome; every other child keeps its own
        durable evidence and is not touched or replayed.
        """
        batch_id = self._required_text(batch_id, "recovery batch ID")
        actor = self._actor(actor)
        batch = self._repository.get_recovery_batch(batch_id)
        pending = tuple(
            item for item in batch.items if item.status is RecoveryBatchItemStatus.SELECTED
        )
        if pending:
            self._drive(pending, actor, maximum_active_jobs)
        return self._repository.get_recovery_batch(batch_id)

    def _drive(
        self,
        items: tuple[RecoveryBatchItem, ...],
        actor: str,
        maximum_active_jobs: int,
    ) -> None:
        """Admit each selected child independently of its siblings' fate."""
        for item in items:
            updated = self._admit_item(item, actor, maximum_active_jobs)
            if updated.status is RecoveryBatchItemStatus.QUEUED:
                # Accepted children are linked inside the continuation transaction.
                continue
            try:
                self._repository.update_recovery_batch_item(updated)
            except Exception:
                # This child stays durably `selected` and is reported as resumable;
                # its siblings must still reach their own durable outcome.
                continue

    def _admit_item(self, batch_item: RecoveryBatchItem, actor: str, maximum_active_jobs: int):
        request = None
        try:
            checkpoint = self._continuation_service.checkpoint_service.get(
                batch_item.source_item_id, task_id=batch_item.source_task_id
            )
            # Validate the selected version before following either retry or continue
            if batch_item.checkpoint_version != checkpoint.checkpoint_version:
                # Reject a stale decision before admitting a request or queueing a Job.
                return replace(
                    batch_item,
                    status=RecoveryBatchItemStatus.REFUSED,
                    reason="stale_checkpoint",
                    error=(
                        "the selected checkpoint version is stale; this item was not changed "
                        "and no recovery work was created"
                    ),
                    next_action=_REFRESH,
                    updated_at=datetime.now(UTC),
                )
            if "continue" not in checkpoint.permitted_action_ids:
                if "retry" in checkpoint.permitted_action_ids:
                    request = self._admission_service.admit(
                        batch_item.source_task_id,
                        batch_item.source_item_id,
                        action_id="retry",
                        expected_checkpoint_version=batch_item.checkpoint_version,
                        actor=actor,
                    )
                    checkpoint = self._continuation_service.checkpoint_service.get(
                        batch_item.source_item_id, task_id=batch_item.source_task_id
                    )
                    if request.request_id != checkpoint.active_recovery_request.request_id:
                        raise ValueError("batch recovery request linkage changed")
                else:
                    reason = (
                        "uncertain_effects"
                        if checkpoint.effect_certainty.value in {"attempted_unverified", "unknown"}
                        else "action_not_permitted"
                    )
                    return replace(
                        batch_item,
                        status=RecoveryBatchItemStatus.REFUSED,
                        reason=reason,
                        error="this item has no safe continuation action at its current checkpoint",
                        next_action="inspect the item checkpoint and follow its offered action",
                        updated_at=datetime.now(UTC),
                    )
            submission = self._continuation_service.submit(
                batch_item.source_task_id,
                batch_item.source_item_id,
                expected_checkpoint_version=checkpoint.checkpoint_version,
                actor=actor,
                maximum_active_jobs=maximum_active_jobs,
                batch_item_id=batch_item.batch_item_id,
            )
            continuation = submission.continuation
            return replace(
                batch_item,
                checkpoint_version=checkpoint.checkpoint_version,
                status=RecoveryBatchItemStatus.QUEUED,
                request_id=continuation.request_id,
                continuation_id=continuation.continuation_id,
                job_id=continuation.job_id,
                next_action=continuation.next_action(),
                updated_at=datetime.now(UTC),
            )
        except LookupError:
            return replace(
                batch_item,
                status=RecoveryBatchItemStatus.REFUSED,
                reason="unknown_item",
                error="TaskItem was not found in the requested Task",
                next_action="refresh the Task detail before selecting this item again",
                updated_at=datetime.now(UTC),
            )
        except RecoveryContinuationError as error:
            existing = error.existing_continuation
            status = (
                RecoveryBatchItemStatus.QUEUED
                if existing is not None and existing.status.value == "queued"
                else RecoveryBatchItemStatus.RUNNING
                if existing is not None and existing.status.value == "running"
                else RecoveryBatchItemStatus.WAITING
                if error.reason.value == "snapshot_unavailable"
                else RecoveryBatchItemStatus.REFUSED
            )
            return replace(
                batch_item,
                status=status,
                request_id=(
                    request.request_id
                    if request is not None
                    else existing.request_id
                    if existing
                    else None
                ),
                continuation_id=existing.continuation_id if existing else None,
                job_id=existing.job_id if existing else None,
                reason=error.reason.value,
                error=str(error),
                next_action=(
                    existing.next_action()
                    if existing
                    else "repair the pinned configuration or refresh this item before retrying"
                ),
                updated_at=datetime.now(UTC),
            )
        except RecoveryAdmissionError as error:
            return replace(
                batch_item,
                status=RecoveryBatchItemStatus.REFUSED,
                request_id=(
                    error.existing_request.request_id
                    if error.existing_request is not None
                    else request.request_id
                    if request is not None
                    else None
                ),
                reason=error.reason.value,
                error=str(error),
                next_action=(
                    _REFRESH
                    if error.current_checkpoint_version
                    else "inspect the item checkpoint and follow its offered action"
                ),
                updated_at=datetime.now(UTC),
            )
        except AutomationQueueFull as error:
            return replace(
                batch_item,
                status=RecoveryBatchItemStatus.WAITING,
                request_id=request.request_id if request is not None else None,
                reason="queue_full",
                error=str(error),
                next_action="wait for active Jobs to finish, then continue this item again",
                updated_at=datetime.now(UTC),
            )
        except Exception as error:
            return replace(
                batch_item,
                status=RecoveryBatchItemStatus.WAITING,
                request_id=request.request_id if request is not None else None,
                reason="batch_child_failed",
                error=f"batch child admission failed ({type(error).__name__})",
                next_action="inspect this item's checkpoint and continue it again",
                updated_at=datetime.now(UTC),
            )

    @staticmethod
    def _required_text(value, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} is required")
        return value.strip()

    @staticmethod
    def _actor(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("actor is required")
        normalized = " ".join(value.split())[:200]
        normalized = _SENSITIVE_ACTOR.sub("[redacted]", normalized)
        normalized = _PRIVATE_ENDPOINT.sub("[redacted]", normalized)
        return _ABSOLUTE_PATH.sub("[redacted]", normalized)
