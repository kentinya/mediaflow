"""The shared read contracts of the unified Operations run inventory.

One "run" is one bounded operator-visible unit of admitted work.  The
inventory joins three durable families through their *explicit* persisted
relationships only:

- an Automation Job (the admission record) and, when it has one, its linked
  Task through ``automation_jobs.task_id``;
- a standalone Task (created by a producer that admits its own Task, e.g. a
  an exact manual organize execution);
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


#: The historical status facet an operator used to treat as attention.  Task
#: Center attention is now the exact union of the four business problem types
#: (see :data:`RECOVERY_PROBLEM_TYPES`), never a status or a technical failure,
#: so this set is retained only as documentation of the status vocabulary.
ATTENTION_RUN_STATUSES = frozenset(
    {
        OperationsRunStatus.PENDING,
        OperationsRunStatus.WAITING,
        OperationsRunStatus.PAUSED,
        OperationsRunStatus.PARTIAL_SUCCESS,
        OperationsRunStatus.FAILED,
    }
)


class OperationsRunView(StrEnum):
    """The eight sibling task-center views (Slice46 RO-4).

    The first four are lifecycle partitions of the whole authorized
    organizing population; the last four are overlapping cross-Task recovery
    lists that group one Task per current *business* problem type.  They share
    one horizontal navigation row and one authoritative query, but each is an
    independent deep-linkable list.  A former fifth ``failure`` view is gone:
    technical failures are read-only history in All/Ended.
    """

    ALL = "all"
    RUNNING = "running"
    ATTENTION = "attention"
    ENDED = "ended"
    RECOGNITION = "recognition"
    METADATA = "metadata"
    CLASSIFICATION = "classification"
    CONFLICT = "conflict"


#: The four lifecycle views; the remaining views are recovery types.
RUN_VIEW_LIFECYCLE = frozenset(
    {
        OperationsRunView.ALL,
        OperationsRunView.RUNNING,
        OperationsRunView.ATTENTION,
        OperationsRunView.ENDED,
    }
)

#: The four cross-Task recovery problem types, in display order.  Exactly the
#: business problems a human must decide; technical failures are not a type.
RECOVERY_PROBLEM_TYPES: tuple[str, ...] = (
    "recognition",
    "metadata",
    "classification",
    "conflict",
)

#: A view's recovery problem type, or ``None`` for a lifecycle view.
RUN_VIEW_PROBLEM_TYPE: Mapping[str, str | None] = MappingProxyType(
    {
        OperationsRunView.ALL.value: None,
        OperationsRunView.RUNNING.value: None,
        OperationsRunView.ATTENTION.value: None,
        OperationsRunView.ENDED.value: None,
        OperationsRunView.RECOGNITION.value: "recognition",
        OperationsRunView.METADATA.value: "metadata",
        OperationsRunView.CLASSIFICATION.value: "classification",
        OperationsRunView.CONFLICT.value: "conflict",
    }
)

#: Chinese business labels for the eight views.
RUN_VIEW_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "all": "全部任务",
        "running": "进行中",
        "attention": "需要处理",
        "ended": "已结束",
        "recognition": "识别恢复",
        "metadata": "元数据恢复",
        "classification": "分类恢复",
        "conflict": "冲突处理",
    }
)

#: Chinese business labels for the four recovery problem types.
RECOVERY_PROBLEM_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "recognition": "识别问题",
        "metadata": "元数据问题",
        "classification": "分类问题",
        "conflict": "冲突问题",
    }
)

# -- Task Center population: admitted organizing work only (RO-4) -----------
#
# One shared, testable membership rule decides which durable rows the Task
# Center may ever list, count, filter or page.  It is deliberately *not* a
# display-text guess: it names the supported organizing command families plus
# the persisted admission/lineage relations the real producers write, so an
# explicitly admitted Files organizing Task stays included while it is still
# discovering/analyzing/waiting for its first confirmation, and a
# preparation-only analysis/preview or an ordinary file command is not.

#: Task command families of admitted organizing work and its legal recovery/
#: continuation successors.  ``manual_organize`` is the Files-first admission.
ORGANIZING_TASK_COMMAND_FAMILIES: tuple[str, ...] = (
    "organize",
    "manual_organize",
    "retry",
    "retry-failed",
    "recovery-continuation",
    "metadata-correction-continuation",
    "scope-continuation",
)

#: Job command families of admitted organizing work.  A scheduled/Run-once
#: occurrence, an analysis continuation and a remaining-scope continuation all
#: remain part of the same admitted organizing journey.  A metadata-correction
#: continuation Job records the shared ``AutomationCommand`` value
#: ``file-metadata-correction``; the Task it produces records
#: ``metadata-correction-continuation:<id>``.
ORGANIZING_JOB_COMMAND_FAMILIES: tuple[str, ...] = (
    "organize",
    "recovery-continuation",
    "file-metadata-correction",
    "scope-continuation",
)

#: Command families that a Task admission itself proves: a Files admission
#: (``manual_organize``) and an explicit organize execution intent (``organize``)
#: both persist ``execute_authorized=True`` inside the admitting transaction.
ORGANIZING_TASK_SEED_TASK_FAMILIES: tuple[str, ...] = (
    "organize",
    "manual_organize",
)

#: Command families of an explicit retry of one named organizing Task.  The
#: persisted command identity names the exact predecessor Task, so it proves a
#: legal continuation of that work instead of guessing from a label.
ORGANIZING_RETRY_TASK_FAMILIES: tuple[str, ...] = ("retry", "retry-failed")

#: The durable relations that prove a Task continues an admitted organizing
#: work.  Only persisted identity equality may establish this.
ORGANIZING_TASK_LINEAGE_RELATIONS: tuple[tuple[str, str], ...] = (
    ("recovery_continuations", "new_task_id"),
    ("scope_continuations", "new_task_id"),
    ("metadata_correction_continuations", "new_task_id"),
)


def organizing_task_command_family(command: object) -> str | None:
    """The organizing command family of one durable Task/Job command.

    A derived ``<kind>:<identity>`` continuation and the MediaLibrary ``media_``
    prefix are stripped exactly like :func:`known_command_label`, so a
    MediaLibrary-owned command is never read as organizing work by accident.
    """

    if not isinstance(command, str) or not command:
        return None
    if command.startswith(MEDIA_LIBRARY_TASK_COMMAND_PREFIX):
        return None
    return command.split(":", 1)[0]


def is_organizing_task_command(command: object) -> bool:
    """Whether a durable Task *command family* is organizing work.

    This is only the command half of the membership rule.  Whether one concrete
    Task really is admitted organizing work additionally needs its persisted
    admission (Files admission, execute-authorized execution intent) or a legal
    lineage relation; see the SQL population expression, which is the single
    authority every center read uses.  A standalone ``organize`` DryRun shares
    this family but is analysis-only work.
    """

    return organizing_task_command_family(command) in ORGANIZING_TASK_COMMAND_FAMILIES


def is_organizing_job_command(command: object) -> bool:
    """Whether a durable Job command belongs to admitted organizing work."""

    return organizing_task_command_family(command) in ORGANIZING_JOB_COMMAND_FAMILIES


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
    standalone Task producer such as an exact manual organize
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

#: The command label of the bounded discovery stage itself.  It lives next to
#: the family map (not inside it) because a discovery is not a Task command
#: family: the run inventory unions it in as its own run kind, so its label is
#: applied directly rather than derived from a persisted command string.
DISCOVERY_COMMAND_LABEL = "整理发现"

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
    #: Live read-only progress over the exact TaskItem population. The stage
    #: is a small public bucket, never an arbitrary internal stage string.
    processed_items: int | None = None
    current_stage: str | None = None
    pause_requested: bool = False
    #: The current, real operator-attention facet: exactly the union of the
    #: four business problem types a human must still decide.  A plain status
    #: name, a technical failure, a plain queue admission and an initial manual
    #: confirmation are never attention.
    attention: bool = False
    #: The four recovery problem types this Task currently has outstanding
    #: (recognition/metadata/classification/conflict).  A Task may carry several
    #: at once; each is derived from the same durable review / saved-decision /
    #: continuation evidence its own list and file read use.  Empty means the
    #: Task currently has no outstanding business problem.
    problem_types: tuple[str, ...] = ()
    #: Distinct affected primary files for each current problem type on this
    #: exact Task. Attachment steps remain grouped under their primary file.
    problem_file_counts: tuple[tuple[str, int], ...] = ()
    #: Why this run is in attention: its current four-type problem evidence.
    #: ``"task_problem"`` is the only published reason; ``None`` means the run
    #: is not in attention at all.
    attention_reason: str | None = None
    #: Bounded, secret-free *factual* failure evidence of a Job that failed
    #: before any Task existed.  It is read-only history in All/Ended and the
    #: shared administrative recovery boundary; it is deliberately NOT an
    #: attention type, a center pending count or a recovery entry.
    attention_failure_category: str | None = None
    attention_failure_next_action: str | None = None
    configuration_snapshot_id: str | None = None
    worker_id: str | None = None
    #: The durable *manual definition origin* recorded with the admission, or
    #: ``None`` for an ordinary Files/CLI run.  It is immutable admission
    #: evidence: reads never derive it from today's Active configuration, and it
    #: lets Automation history and Operations reach the same Run-once execution
    #: without a dummy Job or a second queue.
    origin_definition_id: str | None = None
    origin_definition_name: str | None = None
    origin_kind: str | None = None
    #: The exact execution window the durable admission recorded.  A Job row
    #: publishes its own ``started_at``/``completed_at``; a Task row publishes
    #: the Task's.  Both stay ``None`` while the stage has not been reached, so
    #: a pending row never borrows ``created_at``/``updated_at`` as a fake
    #: execution start or end.
    execution_started_at: datetime | None = None
    execution_finished_at: datetime | None = None
    #: Durable item evidence behind the published outcome: how many primary
    #: items the exact linked Task persisted as ``success``, and how many of
    #: those still carry an uncertain latest Result effect.  A completed queue
    #: or preparation row with no proven successful item is *not* organizing
    #: success, and a skipped item is not an organized item.
    organization_success_items: int = 0
    uncertain_success_items: int = 0
    #: The admitted item bound the producer persisted with the run, or ``None``
    #: when this run carries no bound at all (a discovery, a legacy row, a
    #: pre-Task failure).  It is the durable admission value, never today's
    #: definition limit, so a historical run keeps the exact bound it ran with.
    admitted_item_bound: int | None = None
    #: Whether this run is only *Completed* because an exact persisted recovery
    #: really finished every necessary item.  The original Task/Result rows keep
    #: their historical failed/partial facts; this facet only lets the operator-
    #: facing projection say "已完成（恢复成功）" instead of pretending the first
    #: attempt always succeeded.  It is never true for a run that still carries a
    #: four-type problem, an unsettled/uncertain effect or a sibling failure
    #: without its own verified follow-up.
    recovered_completion: bool = False

    @property
    def organized_successfully(self) -> bool:
        """Whether this run's durable evidence proves successful organization.

        Only a terminal ``completed`` aggregate whose Task persisted at least
        one genuinely successful primary item, with no success item left
        uncertain, qualifies.  A no-work completion, a preparation/admission
        row, a skipped-only run and a terminal-uncertain effect are all
        excluded, so a Job or queue completion can never be relabelled as
        successful organization.
        """

        return (
            self.status is OperationsRunStatus.COMPLETED
            and self.organization_success_items > 0
            and self.uncertain_success_items == 0
        )

    @property
    def no_work_completion(self) -> bool:
        """Whether this run terminally completed without organizing any item."""

        return (
            self.status is OperationsRunStatus.COMPLETED
            and self.organization_success_items == 0
            and self.uncertain_success_items == 0
        )

    @property
    def reached_item_bound(self) -> bool:
        """Whether the durable admitted item population reached its own bound.

        Only an admitted bound plus an exactly equal durable primary-item
        population proves this.  A run without a bound (a bounded discovery, a
        legacy row, a pre-Task admission) and a primary population below or
        above its admitted bound all publish ``False``: reaching a bound is a
        fact about this admission, never a claim that the source scope was
        exhausted.
        """

        if self.admitted_item_bound is None or self.total_items is None:
            return False
        return self.total_items >= self.admitted_item_bound > 0


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
