from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from mediaflow.domain.task_persistence import PersistentTaskItem


@dataclass(frozen=True)
class TaskRetryRequestDecision:
    decision_id: str
    task_id: str
    item_id: str
    decided_at: datetime
    actor: str
    note: str | None = None


@dataclass(frozen=True)
class TaskRetryBatchRequest:
    decision: TaskRetryRequestDecision
    item: PersistentTaskItem


class TaskRetryRepository(Protocol):
    def get_item(self, item_id: str) -> PersistentTaskItem | None: ...
    def list_failed_items(
        self, *, limit: int = 100, task_id: str | None = None
    ) -> tuple[PersistentTaskItem, ...]: ...
    def request_task_retries(self, requests: tuple[TaskRetryBatchRequest, ...]) -> None: ...
    def list_task_retry_audit(self, item_id: str) -> tuple[TaskRetryRequestDecision, ...]: ...
