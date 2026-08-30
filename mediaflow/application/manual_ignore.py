from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.manual_ignore import (
    ManualIgnoreBatchRequest,
    ManualIgnoreDecision,
    ManualIgnoreRepository,
    ManualReviewKind,
)
from mediaflow.domain.metadata_correction import MetadataCorrectionStatus
from mediaflow.domain.metadata_review import MetadataReviewStatus
from mediaflow.domain.recognition_review import RecognitionReviewStatus
from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus


class ManualIgnoreService:
    MAX_ACTOR = 200
    MAX_NOTE = 500
    MAX_BATCH_SIZE = 100

    def __init__(
        self,
        repository: ManualIgnoreRepository,
        *,
        recovery_admission=None,
        snapshot_validator=None,
    ) -> None:
        self._repository = repository
        if recovery_admission is None and snapshot_validator is not None:
            from mediaflow.application.recovery_admission import RecoveryAdmissionService

            recovery_admission = RecoveryAdmissionService(
                repository, snapshot_validator=snapshot_validator
            )
        self._recovery_admission = recovery_admission

    def ignore(
        self,
        task_id: str,
        item_id: str,
        *,
        actor: str,
        note: str | None = None,
        expected_checkpoint_version: str | None = None,
    ) -> ManualIgnoreDecision:
        from mediaflow.application.recovery_admission import RecoveryAdmissionService

        admission = self._recovery_admission or RecoveryAdmissionService(self._repository)
        expected = expected_checkpoint_version
        if expected is None:
            expected = admission.checkpoint_service.get(item_id, task_id=task_id).checkpoint_version
        request = admission.admit(
            task_id,
            item_id,
            action_id="ignore",
            expected_checkpoint_version=expected,
            actor=actor,
            note=note,
        )
        review_kind = ManualReviewKind(request.review_kind or "recognition")
        return ManualIgnoreDecision(
            request.request_id,
            request.task_id,
            request.item_id,
            review_kind,
            request.review_id or "",
            request.requested_at,
            request.actor,
            request.note,
        )

    def _legacy_ignore(
        self,
        task_id: str,
        item_id: str,
        *,
        actor: str,
        note: str | None = None,
    ) -> ManualIgnoreDecision:
        normalized_actor = self._text(actor, self.MAX_ACTOR)
        if not normalized_actor:
            raise ValueError("ignore actor is required")
        item = self._repository.get_item(item_id)
        if item is None or item.task_id != task_id:
            raise LookupError("TaskItem was not found in the specified Task")
        review_kind, review = self._pending_review(item)
        now = datetime.now(UTC)
        decision = ManualIgnoreDecision(
            str(uuid4()),
            task_id,
            item_id,
            review_kind,
            review.review_id,
            now,
            normalized_actor,
            self._text(note, self.MAX_NOTE),
        )
        ignored = replace(
            item,
            status=TaskItemStatus.IGNORED,
            stage="ignored_by_operator",
            updated_at=now,
        )
        self._repository.ignore_waiting_item(decision, ignored)
        return decision

    def ignore_pending(
        self,
        *,
        actor: str,
        note: str | None = None,
        limit: int = 100,
        task_id: str | None = None,
    ) -> tuple[ManualIgnoreDecision, ...]:
        normalized_actor = self._text(actor, self.MAX_ACTOR)
        if not normalized_actor:
            raise ValueError("ignore actor is required")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= self.MAX_BATCH_SIZE
        ):
            raise ValueError(f"ignore batch limit must be between 1 and {self.MAX_BATCH_SIZE}")
        candidates = self._repository.list_ignorable_waiting_items(limit=limit, task_id=task_id)
        if not candidates:
            raise ValueError("no pending manual review items were selected")

        if self._recovery_admission is not None:
            decisions: list[ManualIgnoreDecision] = []
            for candidate in candidates:
                checkpoint = self._recovery_admission.checkpoint_service.get(
                    candidate.item.item_id, task_id=candidate.item.task_id
                )
                request = self._recovery_admission.admit(
                    candidate.item.task_id,
                    candidate.item.item_id,
                    action_id="ignore",
                    expected_checkpoint_version=checkpoint.checkpoint_version,
                    actor=normalized_actor,
                    note=note,
                )
                decisions.append(
                    ManualIgnoreDecision(
                        request.request_id,
                        request.task_id,
                        request.item_id,
                        ManualReviewKind(request.review_kind or candidate.review_kind.value),
                        request.review_id or candidate.review_id,
                        request.requested_at,
                        request.actor,
                        request.note,
                    )
                )
            return tuple(decisions)

        now = datetime.now(UTC)
        normalized_note = self._text(note, self.MAX_NOTE)
        requests: list[ManualIgnoreBatchRequest] = []
        for candidate in candidates:
            decision = ManualIgnoreDecision(
                str(uuid4()),
                candidate.item.task_id,
                candidate.item.item_id,
                candidate.review_kind,
                candidate.review_id,
                now,
                normalized_actor,
                normalized_note,
            )
            ignored = replace(
                candidate.item,
                status=TaskItemStatus.IGNORED,
                stage="ignored_by_operator",
                updated_at=now,
            )
            requests.append(ManualIgnoreBatchRequest(decision, ignored))

        self._repository.ignore_waiting_items(tuple(requests))
        return tuple(request.decision for request in requests)

    def _pending_review(self, item: PersistentTaskItem):
        mappings = {
            TaskItemStatus.WAITING_RECOGNITION: (
                ManualReviewKind.RECOGNITION,
                self._repository.get_recognition_review_for_item,
                RecognitionReviewStatus.PENDING,
            ),
            TaskItemStatus.WAITING_METADATA: (
                ManualReviewKind.METADATA,
                self._repository.get_metadata_review_for_item,
                MetadataReviewStatus.PENDING,
            ),
            TaskItemStatus.WAITING_METADATA_CORRECTION: (
                ManualReviewKind.METADATA_CORRECTION,
                self._repository.get_metadata_correction_for_item,
                MetadataCorrectionStatus.PENDING,
            ),
        }
        selected = mappings.get(item.status)
        if selected is None:
            raise ValueError("TaskItem is not in a supported manual-review waiting state")
        kind, getter, pending = selected
        review = getter(item.item_id)
        if review is None or review.status is not pending:
            raise ValueError("TaskItem has no matching pending manual review")
        return kind, review

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if value is not None else ""
        return normalized or None
