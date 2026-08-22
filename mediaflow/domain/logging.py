from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Protocol


class LogLevel(IntEnum):
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40


class Logger(Protocol):
    def log(self, level: LogLevel, message: str, **context: object) -> None: ...


@dataclass(frozen=True)
class OperationalLogRecord:
    log_id: str
    occurred_at: datetime
    level: LogLevel
    component: str
    event: str
    task_id: str | None = None
    job_id: str | None = None
    plan_id: str | None = None
    status: str | None = None


class OperationalLogRepository(Protocol):
    def append_operational_log(self, value: OperationalLogRecord) -> None: ...
    def list_operational_logs(
        self, *, limit: int, minimum_level: LogLevel | None = None
    ) -> tuple[OperationalLogRecord, ...]: ...
    def prune_operational_logs(self, *, before: datetime, maximum_records: int) -> int: ...
