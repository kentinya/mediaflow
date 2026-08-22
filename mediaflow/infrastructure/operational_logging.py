from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.logging import (
    Logger,
    LogLevel,
    OperationalLogRecord,
    OperationalLogRepository,
)

_SAFE_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_EVENTS = {
    "scan started": "scan.started",
    "scan completed": "scan.completed",
    "scan failed": "scan.failed",
    "library scan started": "library_scan.started",
    "library scan completed": "library_scan.completed",
    "media parsed and recognized": "workflow.recognized",
    "metadata naming and classification completed": "workflow.strategy_completed",
    "organize plan processed": "workflow.plan_processed",
    "media workflow failed": "workflow.failed",
    "organize execution result": "organizer.execution_result",
}


class SQLiteOperationalLogger(Logger):
    def __init__(
        self,
        repository: OperationalLogRepository,
        component: str,
        minimum_level: LogLevel = LogLevel.INFO,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not _SAFE_ID.fullmatch(component):
            raise ValueError("operational log component is invalid")
        self._repository = repository
        self._component = component
        self._minimum_level = LogLevel(minimum_level)
        self._clock = clock

    def log(self, level: LogLevel, message: str, **context: object) -> None:
        resolved = LogLevel(level)
        event = _EVENTS.get(message)
        if resolved < self._minimum_level or event is None:
            return
        status = context.get("status", context.get("execution_status"))
        try:
            self._repository.append_operational_log(
                OperationalLogRecord(
                    uuid4().hex,
                    self._clock(),
                    resolved,
                    self._component,
                    event,
                    task_id=_safe(context.get("task_id")),
                    job_id=_safe(context.get("job_id")),
                    plan_id=_safe(context.get("plan_id")),
                    status=_safe(status),
                )
            )
        except Exception:
            # Observability is never allowed to change workflow or execution authority.
            return


def _safe(value: object) -> str | None:
    return value if isinstance(value, str) and _SAFE_ID.fullmatch(value) else None
