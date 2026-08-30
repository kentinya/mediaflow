from __future__ import annotations

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.task_retry import TaskRetryRequestService
from mediaflow.domain.task_retry import TaskRetryRequestDecision


class FileReplanRequestService:
    def __init__(
        self,
        file_catalog: FileCatalogService,
        task_retry: TaskRetryRequestService | None = None,
        recovery_admission=None,
    ) -> None:
        self._file_catalog = file_catalog
        self._task_retry = task_retry
        self._recovery_admission = recovery_admission

    def request(
        self,
        file_id: str,
        *,
        actor: str,
        note: str | None = None,
        expected_checkpoint_version: str | None = None,
    ) -> TaskRetryRequestDecision:
        detail = self._file_catalog.detail(file_id)
        if detail.latest_result is None:
            raise ValueError("file has no latest TaskResult")
        if self._recovery_admission is not None:
            checkpoint = self._recovery_admission.checkpoint_service.get(
                detail.latest_result.item_id
            )
            request = self._recovery_admission.admit(
                checkpoint.task_id,
                detail.latest_result.item_id,
                action_id="retry",
                expected_checkpoint_version=(
                    expected_checkpoint_version or checkpoint.checkpoint_version
                ),
                actor=actor,
                note=note,
            )
            return TaskRetryRequestDecision(
                request.request_id,
                request.task_id,
                request.item_id,
                request.requested_at,
                request.actor,
                request.note,
            )
        if self._task_retry is None:
            raise RuntimeError("recovery admission service is unavailable")
        return self._task_retry.request_item(
            detail.latest_result.item_id,
            actor=actor,
            note=note,
            expected_checkpoint_version=expected_checkpoint_version,
        )
