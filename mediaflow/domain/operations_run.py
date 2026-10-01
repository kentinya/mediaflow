"""The shared read contracts of the unified Operations run inventory.

One "run" is one bounded operator-visible unit of admitted work.  The
inventory joins three durable families through their *explicit* persisted
relationships only:

- an Automation Job (the admission record) and, when it has one, its linked
  Task through ``automation_jobs.task_id``;
- a standalone Task (created by a producer that admits its own Task, e.g. a
  manual Scan or an exact manual organize execution);
- a Files transfer Task whose separate ``files_transfers`` row is the Worker
  claim authority.

The projection is a read boundary, never a new lifecycle or execution
authority: it derives one honest aggregate state and bounded display evidence
from rows that already exist and never mutates them.  Links are never
inferred from filenames, creation-time proximity, labels or a command prefix
alone — only a persisted ID equality (``job.task_id == task.task_id``) joins
an admission to its Task, and an unknown legacy command keeps an honest
bounded label instead of disappearing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from mediaflow.domain.automation import AutomationJob, AutomationJobStatus
from mediaflow.domain.direct_files import LibraryKind
from mediaflow.domain.task_persistence import (
    FILES_DELETE_TASK_COMMAND,
    FILES_DIRECT_COMMAND_TASK,
    FILES_TRANSFER_TASK_COMMAND,
    MEDIA_LIBRARY_TASK_COMMAND_PREFIX,
    PersistentTask,
    PersistentTaskStatus,
)


class OperationsRunStatus(StrEnum):
    """One honest aggregate state of a run, derived from actual evidence."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING = "waiting"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class OperationsRunTrigger(StrEnum):
    """What admitted the run, from its durable record alone."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    AUTOMATION = "automation"
    UNKNOWN = "unknown"


#: The bounded attention facet: an overlapping (not mutually exclusive) set of
#: runs an operator should look at.  A run can be in attention and still be
#: counted in its own status partition.
ATTENTION_RUN_STATUSES = frozenset(
    {
        OperationsRunStatus.PENDING,
        OperationsRunStatus.WAITING,
        OperationsRunStatus.PAUSED,
        OperationsRunStatus.PARTIAL_SUCCESS,
        OperationsRunStatus.FAILED,
    }
)


def derive_run_status(
    job: AutomationJob | None,
    task: PersistentTask | None,
) -> OperationsRunStatus:
    """Aggregate status from actual queue/processing evidence.

    Rules, in order of authority:

    - A paused Task stays paused; a completed Job can never mask its linked
      Task's partial success or failure.
    - A live (non-terminal) Job/Task publishes its own state.
    - Terminal evidence prefers the linked Task (the per-item truth) over the
      Job admission outcome.
    - No evidence at all is ``unknown``, never an optimistic success.
    """

    task_status = _task_run_status(task) if task is not None else None
    job_status = _job_run_status(job) if job is not None else None
    if task_status is not None and task_status is OperationsRunStatus.PAUSED:
        return OperationsRunStatus.PAUSED
    if task_status is not None and task_status not in _TERMINAL_RUN_STATUSES:
        return task_status
    if job_status is not None and job_status not in _TERMINAL_RUN_STATUSES:
        return job_status
    if task_status is not None:
        return task_status
    if job_status is not None:
        return job_status
    return OperationsRunStatus.UNKNOWN


_TERMINAL_RUN_STATUSES = frozenset(
    {
        OperationsRunStatus.COMPLETED,
        OperationsRunStatus.PARTIAL_SUCCESS,
        OperationsRunStatus.FAILED,
        OperationsRunStatus.CANCELLED,
    }
)


def _task_run_status(task: PersistentTask) -> OperationsRunStatus | None:
    try:
        status = PersistentTaskStatus(task.status)
    except ValueError:
        return OperationsRunStatus.UNKNOWN
    return _PERSISTENT_TASK_RUN_STATUS.get(status, OperationsRunStatus.UNKNOWN)


def _job_run_status(job: AutomationJob) -> OperationsRunStatus | None:
    try:
        status = AutomationJobStatus(job.status)
    except ValueError:
        return OperationsRunStatus.UNKNOWN
    return _JOB_RUN_STATUS.get(status, OperationsRunStatus.UNKNOWN)


_PERSISTENT_TASK_RUN_STATUS = {
    PersistentTaskStatus.PENDING: OperationsRunStatus.PENDING,
    PersistentTaskStatus.RUNNING: OperationsRunStatus.RUNNING,
    PersistentTaskStatus.PAUSED: OperationsRunStatus.PAUSED,
    PersistentTaskStatus.COMPLETED: OperationsRunStatus.COMPLETED,
    PersistentTaskStatus.PARTIAL_SUCCESS: OperationsRunStatus.PARTIAL_SUCCESS,
    PersistentTaskStatus.FAILED: OperationsRunStatus.FAILED,
    PersistentTaskStatus.CANCELLED: OperationsRunStatus.CANCELLED,
}

_JOB_RUN_STATUS = {
    AutomationJobStatus.PENDING: OperationsRunStatus.PENDING,
    AutomationJobStatus.RUNNING: OperationsRunStatus.RUNNING,
    AutomationJobStatus.COMPLETED: OperationsRunStatus.COMPLETED,
    AutomationJobStatus.FAILED: OperationsRunStatus.FAILED,
    AutomationJobStatus.CANCELLED: OperationsRunStatus.CANCELLED,
}


def derive_run_trigger(job: AutomationJob | None) -> OperationsRunTrigger:
    """The admission trigger from the durable Job record alone.

    A managed definition occurrence is scheduled work; a legacy schedule
    reference is scheduled as well; any other Job came from the Automation
    submission surface; a run with no Job at all was admitted manually (a
    standalone Task producer such as a manual Scan, an exact manual organize
    execution or a bounded Files command/transfer).  No guesswork beyond the
    persisted record.
    """

    if job is None:
        return OperationsRunTrigger.MANUAL
    if job.definition_id:
        return OperationsRunTrigger.SCHEDULED
    if job.schedule_id:
        return OperationsRunTrigger.SCHEDULED
    return OperationsRunTrigger.AUTOMATION


def known_command_label(command: str | None) -> str | None:
    """The bounded Chinese business label of a known command family.

    An unknown legacy command returns ``None``: the caller labels it honestly
    as an unrecognized record instead of guessing a business meaning from a
    string.  A derived ``<kind>:<identity>`` continuation shares its family's
    label.  A MediaLibrary-owned direct command keeps its own kind in the
    label so equal library IDs can never read as ResourceLibrary work.
    """

    if not isinstance(command, str) or not command:
        return None
    # A derived ``<kind>:<identity>`` continuation shares its family's label.
    if command.startswith(MEDIA_LIBRARY_TASK_COMMAND_PREFIX):
        base = command[len(MEDIA_LIBRARY_TASK_COMMAND_PREFIX) :].split(":", 1)[0]
        media_label = _COMMAND_LABELS.get(base)
        return None if media_label is None else f"媒体库{media_label}"
    return _COMMAND_LABELS.get(command.split(":", 1)[0])


_COMMAND_LABELS = {
    "scan": "扫描",
    "preview": "预览",
    "organize": "整理",
    "manual_organize": "手动整理",
    "retry": "重试",
    "retry-failed": "失败项重试",
    "metadata-correction-continuation": "元数据修正",
    "recovery-continuation": "恢复继续",
    "file-metadata-correction": "文件元数据修正",
    FILES_DIRECT_COMMAND_TASK: "文件维护",
    FILES_DELETE_TASK_COMMAND: "文件删除",
    FILES_TRANSFER_TASK_COMMAND: "文件传输",
}

#: Public read-only view of the bounded business labels above.  The SQL run
#: inventory projects the exact same family→label mapping (see
#: :func:`mediaflow.infrastructure.sqlite_runtime.command_label_sql`), so a
#: repository search for a visible business label and the published
#: ``command_label`` can never disagree.
COMMAND_LABELS: Mapping[str, str] = MappingProxyType(_COMMAND_LABELS)


@dataclass(frozen=True)
class OperationsRunOverview:
    """One row of the unified run inventory.

    Every field is bounded, secret-free display evidence.  ``source_scope``
    is the historical admission scope exactly as it was recorded (or ``None``
    when the legacy row carries no evidence — never a current-Active
    fallback).  ``recognized_command`` is False for an unknown legacy
    command, so the operator sees an honest label rather than a guessed one.
    """

    run_kind: str
    run_id: str
    command: str | None
    command_label: str | None
    recognized_command: bool
    status: OperationsRunStatus
    trigger: OperationsRunTrigger
    created_at: datetime
    updated_at: datetime
    job_id: str | None = None
    task_id: str | None = None
    schedule_id: str | None = None
    definition_id: str | None = None
    source_scope: str | None = None
    target_scope: str | None = None
    library_kind: LibraryKind | None = None
    total_items: int | None = None
    completed_items: int | None = None
    failed_items: int | None = None
    pause_requested: bool = False
    attention: bool = False
    configuration_snapshot_id: str | None = None
    worker_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attention", self.status in ATTENTION_RUN_STATUSES)
