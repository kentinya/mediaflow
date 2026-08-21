from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "pending"
    SCANNING = "scanning"
    PARSING = "parsing"
    RECOGNIZING = "recognizing"
    FETCHING_METADATA = "fetching_metadata"
    PLANNING = "planning"
    WAITING_CONFIRM = "waiting_confirm"
    ORGANIZING = "organizing"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Task:
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class ScanTask:
    task_id: str
    resource_library_id: str
    mode: str
    status: TaskStatus = TaskStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: dict[str, int] = field(default_factory=dict)
    errors: tuple[object, ...] = field(default_factory=tuple)
