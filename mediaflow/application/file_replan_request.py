from __future__ import annotations

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.task_retry import TaskRetryRequestService
from mediaflow.domain.task_retry import TaskRetryRequestDecision


class FileReplanRequestService:
    def __init__(
        self,
        file_catalog: FileCatalogService,
        task_retry: TaskRetryRequestService,
    ) -> None:
        self._file_catalog = file_catalog
        self._task_retry = task_retry

    def request(
        self,
        file_id: str,
        *,
        actor: str,
        note: str | None = None,
    ) -> TaskRetryRequestDecision:
        detail = self._file_catalog.detail(file_id)
        if detail.latest_result is None:
            raise ValueError("file has no latest TaskResult")
        return self._task_retry.request_item(
            detail.latest_result.item_id,
            actor=actor,
            note=note,
        )
