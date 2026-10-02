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
    TaskItemStatus,
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


# -- Selected-run detail: progress, items and operation records (RO-3) -------

#: The mutually exclusive primary-item dispositions of one task's durable
#: population.  Every persisted ``TaskItemStatus`` maps to exactly one of
#: these, so a known total always reconciles: the disposition counts sum to
#: the known item total.  They are an attention-style *partition of items*,
#: never a claim about Storage success — see the accounting basis text the
#: progress document publishes.
RUN_DISPOSITIONS = (
    "pending",
    "active",
    "waiting",
    "success",
    "skipped",
    "failed_partial",
    "ignored",
    "cancelled",
)

#: Chinese business labels for the dispositions above (published, never
#: invented at read time from raw status strings).
RUN_DISPOSITION_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "pending": "待处理",
        "active": "进行中",
        "waiting": "等待中",
        "success": "成功",
        "skipped": "跳过",
        "failed_partial": "失败或部分",
        "ignored": "已忽略",
        "cancelled": "已取消",
    }
)

_ITEM_DISPOSITION: Mapping[str, str] = MappingProxyType(
    {
        TaskItemStatus.PENDING.value: "pending",
        TaskItemStatus.PROCESSING.value: "active",
        # A completed dry-run item is a completed *analysis* item.  It counts
        # as success only against the analysis accounting basis the progress
        # document publishes; analysis completion is never labelled organize
        # or Storage success.
        TaskItemStatus.DRY_RUN.value: "success",
        TaskItemStatus.SUCCESS.value: "success",
        TaskItemStatus.SKIPPED.value: "skipped",
        TaskItemStatus.PARTIAL.value: "failed_partial",
        TaskItemStatus.FAILED.value: "failed_partial",
        TaskItemStatus.CANCELLED.value: "cancelled",
        TaskItemStatus.IGNORED.value: "ignored",
        TaskItemStatus.PAUSED.value: "waiting",
        TaskItemStatus.WAITING_CONFIRM.value: "waiting",
        TaskItemStatus.WAITING_RECOGNITION.value: "waiting",
        TaskItemStatus.WAITING_METADATA.value: "waiting",
        TaskItemStatus.WAITING_METADATA_CORRECTION.value: "waiting",
        TaskItemStatus.WAITING_CLASSIFICATION.value: "waiting",
    }
)


def item_disposition(status: object) -> str:
    """Map one persisted item status to its mutually exclusive disposition.

    An unknown/legacy status is ``failed_partial`` — never silently dropped
    into success, and never omitted from the partition, so the reported
    disposition counts keep reconciling with the known total even for a row
    written by an older or external producer.
    """

    value = getattr(status, "value", status)
    if isinstance(value, str):
        return _ITEM_DISPOSITION.get(value, "failed_partial")
    return "failed_partial"


_RAW_DISPOSITION_STATUSES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "pending": (TaskItemStatus.PENDING.value,),
        "active": (TaskItemStatus.PROCESSING.value,),
        "waiting": (
            TaskItemStatus.PAUSED.value,
            TaskItemStatus.WAITING_CONFIRM.value,
            TaskItemStatus.WAITING_RECOGNITION.value,
            TaskItemStatus.WAITING_METADATA.value,
            TaskItemStatus.WAITING_METADATA_CORRECTION.value,
            TaskItemStatus.WAITING_CLASSIFICATION.value,
        ),
        # ``dry_run`` belongs to success only against the analysis accounting
        # basis (see ``item_disposition``); the raw statuses stay the single
        # expansion point so the filtered count and the filtered page always
        # run against the same predicate.
        "success": (TaskItemStatus.DRY_RUN.value, TaskItemStatus.SUCCESS.value),
        "skipped": (TaskItemStatus.SKIPPED.value,),
        "failed_partial": (TaskItemStatus.PARTIAL.value, TaskItemStatus.FAILED.value),
        "ignored": (TaskItemStatus.IGNORED.value,),
        "cancelled": (TaskItemStatus.CANCELLED.value,),
    }
)


def statuses_for_disposition(disposition: str) -> tuple[str, ...]:
    """Expand one submitted disposition into its exact raw item statuses."""

    try:
        return _RAW_DISPOSITION_STATUSES[disposition]
    except (KeyError, TypeError) as error:
        raise ValueError("run disposition filter is invalid") from error


def disposition_partition(
    status_counts: Mapping[str, int],
) -> tuple[dict[str, int], int]:
    """Partition raw status counts into the mutually exclusive dispositions.

    Returns the disposition counts (all keys always present, zero-filled)
    and the grand total they reconcile to.
    """

    counts = {key: 0 for key in RUN_DISPOSITIONS}
    total = 0
    for status, value in status_counts.items():
        numeric = int(value)
        if numeric <= 0:
            continue
        counts[item_disposition(status)] += numeric
        total += numeric
    return counts, total


@dataclass(frozen=True)
class OperationsRunProgress:
    """One snapshot of a run's durable progress accounting (AC-T2).

    Read entirely inside one repository read transaction together with the
    run row it belongs to, so the aggregate state and the progress facts a
    panel presents together always share one read basis.

    ``known_total`` is ``None`` when discovery totals are genuinely unknown
    (a scan still discovering, or a task that has not admitted any item
    yet): the caller must publish the progress as *indeterminate* instead of
    inventing a total or a percentage.  ``dispositions`` partitions the
    primary item population; ``uncertain_success`` counts items whose status
    says success while their latest durable Result still declares uncertain
    effects — those are never presented as success.  ``effect_counts``
    summarizes the latest Result effect certainty per item (a non-exclusive
    facet), ``scan_errors`` counts scan-level errors kept separate from
    primary items, and ``attachment_steps`` counts attachment operations
    kept separate from primary items.
    """

    available: bool
    unavailable_reason: str | None = None
    known_total: int | None = None
    indeterminate: bool = False
    dispositions: Mapping[str, int] = MappingProxyType({})
    uncertain_success: int = 0
    attachment_steps: int = 0
    effect_counts: Mapping[str, int] = MappingProxyType({})
    results_total: int = 0
    results_complete: bool = True
    scan_errors: int | None = None
    scan_discovery_complete: bool | None = None
    scan_progress: Mapping[str, int] = MappingProxyType({})
    primary_unit: str = "task_items"
    #: Whether this Task's durable admission authorized Storage execution —
    #: the basis for distinguishing analysis completion from organize
    #: success.  Read together with the counts in the same snapshot.
    execute_authorized: bool = False


@dataclass(frozen=True)
class OperationsRunItemWindow:
    """One item page plus population totals from one read snapshot."""

    page: tuple[object, ...]
    total: int
    matching_total: int
    dispositions: Mapping[str, int]
    uncertain_success: int
    has_next: bool
    has_previous: bool


#: The durable operation-record kinds of the ``操作记录`` stream.  Each row
#: is joined to the run only through exact persisted IDs (task_id, job_id,
#: item_id, plan_id) — never through text matching.
RUN_RECORD_KINDS = ("result", "evidence", "log", "audit")

RUN_RECORD_KIND_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "result": "执行结果",
        "evidence": "分析与计划",
        "log": "运行日志",
        "audit": "控制与恢复",
    }
)


@dataclass(frozen=True)
class OperationsRunRecord:
    """One exactly-linked operation record of a run.

    ``record_id`` is globally unique across kinds (``<kind>:<primary key>``)
    and is the cursor tiebreak, so mixed-kind paging stays deterministic.
    ``item_id`` is set when the record belongs to one exact TaskItem.
    ``source`` carries the durable row the projector needs for ``kind``.
    """

    kind: str
    record_id: str
    occurred_at: datetime
    item_id: str | None
    source: object


@dataclass(frozen=True)
class OperationsRunRecordWindow:
    """One record page plus kind totals from one read snapshot."""

    page: tuple[OperationsRunRecord, ...]
    matching_total: int
    kind_counts: Mapping[str, int]
    has_next: bool
    has_previous: bool
