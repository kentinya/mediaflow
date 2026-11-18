from __future__ import annotations

from mediaflow.domain.manual_ignore import (
    ManualIgnoreDecision,
    ManualIgnoreRepository,
    ManualReviewKind,
)


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
        admission = self._admission()
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

    def _admission(self):
        from mediaflow.application.recovery_admission import RecoveryAdmissionService

        return self._recovery_admission or RecoveryAdmissionService(self._repository)

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

        admission = self._admission()
        decisions: list[ManualIgnoreDecision] = []
        for candidate in candidates:
            checkpoint = admission.checkpoint_service.get(
                candidate.item.item_id, task_id=candidate.item.task_id
            )
            request = admission.admit(
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

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if value is not None else ""
        return normalized or None
