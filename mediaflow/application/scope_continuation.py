"""Application boundary for durable queued continuation of a paused Task scope.

Two responsibilities live here and nowhere else:

* :class:`ScopeContinuationService` is the **admission** boundary the HTTP
  control uses.  It revalidates the exact durable Task state, the live source
  and configuration pin, the applicable execution authority and the queue
  capacity, then records one queued continuation Job plus its continuation row.
  It performs **zero** Storage work, constructs no Storage/Provider adapter and
  never executes media.
* :class:`ScopeContinuationWorkerService` is the **Worker** boundary.  The
  resident Worker claims the queued Job under the existing claim/lease/schema
  fences and then revalidates the same durable evidence before any adapter is
  built, so a continuation that lost its source, capability, permission or
  authority is refused with a truthful reason instead of mutating anything.

Neither service shells out to the CLI and neither runs a long continuation
inside an HTTP request.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.scope_continuation import (
    CONTINUABLE_TASK_COMMANDS,
    CONTINUATION_BOUNDARY,
    ScopeContinuation,
    ScopeContinuationError,
    ScopeContinuationReason,
    ScopeContinuationStatus,
)
from mediaflow.domain.task_persistence import (
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}")

#: The operator-facing next action when the exact remaining work cannot proceed
#: without fresh explicit authority.  It names the native journey the Contract
#: promises (exact Preview plus explicit execution intent) rather than the CLI.
_NATIVE_AUTHORITY_NEXT_ACTION = (
    "open the run's exact Preview, review the remaining scope, and authorize execution "
    "again from 操作与任务; MediaFlow never reissues consumed or revoked execution authority"
)
_AUTHORITY_REASON = (
    "continuing this remaining scope would mutate media, but the original execution authority "
    "was one-shot, expired or revoked; a stored execute flag is not authority"
)
_SNAPSHOT_REASON = (
    "the Task's immutable configuration pin cannot be resolved, so the exact original scope "
    "cannot be reproduced"
)
_SNAPSHOT_NEXT_ACTION = (
    "restore the pinned published configuration revision, or start a new bounded run under "
    "the current Active configuration"
)
_LINEAGE_REASON = "the recorded continuation history no longer proves the original paused scope"
_LINEAGE_NEXT_ACTION = (
    "inspect the linked continuation run and its configuration history; start a new bounded run "
    "if the original scope cannot be restored"
)

#: The item dispositions that still hold remaining admitted work.  This mirrors
#: the operator CLI's proven continuation eligibility exactly
#: (``retryable_items(failed_only=False)``): pending, processing, failed,
#: partial, cancelled and paused items are all still undecided work, while a
#: waiting item is owned by its own decision journey, an ignored item is an
#: explicit operator decision and a dry-run/successful sibling is already
#: decided.
_REMAINING_ITEM_STATUSES = frozenset(
    {
        TaskItemStatus.PENDING,
        TaskItemStatus.PROCESSING,
        TaskItemStatus.FAILED,
        TaskItemStatus.PARTIAL,
        TaskItemStatus.CANCELLED,
        TaskItemStatus.PAUSED,
    }
)

#: The recorded Result outcomes that prove an item's durable outcome is already
#: decided.  Even when a later transition rewrote the item status, an item with
#: one of these Results is never replayed: a successful/dry-run/skipped sibling
#: has a completed effect and an ignored item is an explicit operator decision.
_TERMINAL_RESULT_STATUSES = frozenset(
    {
        TaskItemStatus.SUCCESS.value,
        TaskItemStatus.DRY_RUN.value,
        TaskItemStatus.SKIPPED.value,
        TaskItemStatus.IGNORED.value,
    }
)

#: An item whose executor recorded an unverified effect is never replayed
#: automatically: MediaFlow cannot prove the interrupted mutation did not
#: happen, so it stays investigation-only.
_UNCERTAIN_EFFECT_CERTAINTY = "attempted_unverified"

#: The statuses that mean a Task of a continuation chain has stopped producing
#: work: a terminal Task cannot own remaining scope, so the deepest Task of the
#: chain is the last known owner.
_CHAIN_TERMINAL_STATUSES = frozenset(
    {
        PersistentTaskStatus.COMPLETED,
        PersistentTaskStatus.PARTIAL_SUCCESS,
        PersistentTaskStatus.FAILED,
        PersistentTaskStatus.CANCELLED,
    }
)

#: A hard bound on how many linked Tasks one chain walk will follow, so a
#: corrupted or externally written link row can never make a read unbounded.
_MAX_CHAIN_TASKS = 64


@dataclass(frozen=True)
class ScopeContinuationSubmission:
    continuation: ScopeContinuation
    job: AutomationJob
    created: bool


@dataclass(frozen=True)
class PreparedScopeContinuation:
    continuation: ScopeContinuation
    source_task: PersistentTask
    remaining_items: tuple[PersistentTaskItem, ...]
    already_recorded: frozenset[tuple[str, str]]
    remaining_limit: int | None


def is_continuable_task_command(command: object) -> bool:
    """Whether one durable Task command has a supported remaining-scope boundary."""

    return isinstance(command, str) and command in CONTINUABLE_TASK_COMMANDS


def continuation_origin(repository, task: PersistentTask) -> PersistentTask:
    """Resolve a continuation Task's root only through exact persisted links.

    Each queued continuation copies its source Task's command, scope, item
    limit and immutable configuration pin. Rechecking those values on every
    parent edge makes the root Job's Definition occurrence usable after any
    number of pauses without inferring ancestry from a path, label or timestamp.
    A malformed, cyclic, incomplete or overlong chain is refused.
    """

    reader = getattr(repository, "get_scope_continuation_for_new_task", None)
    if not callable(reader):
        return task

    current = task
    visited = {task.task_id}
    for _ in range(_MAX_CHAIN_TASKS):
        link = reader(current.task_id)
        if link is None:
            return current
        if getattr(link, "new_task_id", None) != current.task_id:
            raise ValueError("continuation ancestry does not identify its child Task")
        parent_id = getattr(link, "source_task_id", None)
        if not isinstance(parent_id, str) or not parent_id or parent_id in visited:
            raise ValueError("continuation ancestry is cyclic or incomplete")
        parent = repository.get_task(parent_id)
        if parent is None:
            raise ValueError("continuation ancestry source Task is unavailable")
        expected = (
            parent.task_id,
            parent.command,
            parent.scope_path,
            parent.item_limit,
            parent.configuration_snapshot_id,
            parent.configuration_snapshot_digest,
        )
        recorded = (
            getattr(link, "source_task_id", None),
            getattr(link, "command", None),
            getattr(link, "scope_path", None),
            getattr(link, "item_limit", None),
            getattr(link, "configuration_snapshot_id", None),
            getattr(link, "configuration_snapshot_digest", None),
        )
        child = (
            current.task_id,
            current.command,
            current.scope_path,
            current.item_limit,
            current.configuration_snapshot_id,
            current.configuration_snapshot_digest,
        )
        if recorded != expected or child[1:] != expected[1:]:
            raise ValueError("continuation ancestry changed its original command, scope or pin")
        visited.add(parent_id)
        current = parent
    raise ValueError("continuation ancestry exceeds the supported chain depth")


def definition_occurrence_authority(repository, definitions, grants):
    """A checker proving a mutation-authorized Task keeps live reusable authority.

    Only a managed Automation Task Definition occurrence owns a reusable,
    revocable mutation authority in this runtime: its definition-bound
    unattended grant.  The checker resolves the occurrence's own Job and the
    definition from the *same* saved configuration revision the occurrence was
    admitted under, then re-reads the grant through the production
    ``UnattendedExecutionGrantService`` — exactly the check the Worker repeats at
    every mutation boundary.  The advertised control, the admission and the real
    execution boundary therefore cannot disagree.

    Any other mutation-authorized Task (for example a consumed one-shot remote
    organize) has no reusable authority left, so the checker returns ``False``
    and the caller fails closed instead of continuing under a stored boolean.
    """

    saved_definitions = tuple(definitions or ())

    def check(task: PersistentTask) -> bool:
        job_reader = getattr(repository, "get_job_for_task", None)
        if not callable(job_reader) or grants is None:
            return False
        try:
            origin = continuation_origin(repository, task)
        except Exception:
            return False
        job = job_reader(origin.task_id)
        definition_id = getattr(job, "definition_id", None)
        if not isinstance(definition_id, str) or not definition_id:
            return False
        definition = next(
            (
                value
                for value in saved_definitions
                if getattr(value, "definition_id", getattr(value, "id", None)) == definition_id
            ),
            None,
        )
        if definition is None:
            return False
        try:
            grants.assert_live(job, definition)
        except Exception:
            # A revoked, expired, mismatched or unverifiable grant is never
            # authority: the continuation must stop with zero new mutation.
            return False
        return True

    return check


def continuation_obstacle(
    repository,
    task: PersistentTask,
    snapshot_validator: Callable[[str, str], None] | None,
    mutation_authority: Callable[[PersistentTask], bool] | None = None,
    *,
    exclude_job_id: str | None = None,
) -> tuple[ScopeContinuationReason | None, str | None, str | None]:
    """Why one continuable Task cannot be continued now.

    Returns ``(reason, bounded_message, next_action)``, or ``(None, None,
    None)`` when the Task's exact remaining scope may be queued.  The lifecycle
    projection, the admission boundary and the resident Worker all call this, so
    the advertised control and the real submission can never disagree about
    whether Continue would be accepted.

    The decision is made over the whole recorded continuation chain, not one
    Task in isolation:

    * an already-active continuation of the same source owns the remaining
      scope, so submitting again would duplicate it (``exclude_job_id`` lets the
      Worker exclude the very continuation it is revalidating);
    * a later Task of the chain that is still non-terminal (a continuation that
      paused again) owns the remaining scope, so the original run must not
      continue it a second time;
    * a chain whose recorded items already consumed the originally admitted
      item budget has no remaining scope left to queue.
    """

    if task.status is not PersistentTaskStatus.PAUSED:
        return (
            ScopeContinuationReason.TASK_NOT_PAUSED,
            f"only a durably paused Task has a remaining scope to continue; this Task is "
            f"{task.status.value}",
            "refresh the Task and continue it only while it is durably paused",
        )
    if not task.configuration_snapshot_id or not task.configuration_snapshot_digest:
        return (
            ScopeContinuationReason.SNAPSHOT_UNAVAILABLE,
            "this Task has no immutable configuration pin, so its exact original scope "
            "cannot be reproduced",
            "start a new bounded run under the current Active configuration, or inspect "
            "the Task's recorded per-item evidence",
        )
    if snapshot_validator is None:
        return (
            ScopeContinuationReason.SNAPSHOT_UNAVAILABLE,
            _SNAPSHOT_REASON,
            _SNAPSHOT_NEXT_ACTION,
        )
    try:
        snapshot_validator(task.configuration_snapshot_id, task.configuration_snapshot_digest)
    except Exception:
        return (
            ScopeContinuationReason.SNAPSHOT_UNAVAILABLE,
            _SNAPSHOT_REASON,
            _SNAPSHOT_NEXT_ACTION,
        )
    try:
        continuation_origin(repository, task)
    except Exception:
        return (
            ScopeContinuationReason.SNAPSHOT_UNAVAILABLE,
            _LINEAGE_REASON,
            _LINEAGE_NEXT_ACTION,
        )
    active = _active_continuation(repository, task.task_id, exclude_job_id=exclude_job_id)
    if active is not None:
        return (
            ScopeContinuationReason.CONTINUATION_EXISTS,
            "this Task already has an active queued continuation that owns its remaining scope",
            "follow the linked continuation run instead of submitting the remaining scope again",
        )
    try:
        _remaining, _recorded, remaining_limit = remaining_scope(repository, task)
    except Exception:
        remaining_limit = None
    if remaining_limit == 0:
        return (
            ScopeContinuationReason.NO_REMAINING_SCOPE,
            "every unit of this Task's originally admitted item budget is already recorded, so "
            "no remaining scope exists to continue",
            "inspect the linked continuation run and its independent per-item results, or start "
            "a new bounded run from 操作与任务",
        )
    owner = chain_owner(repository, task)
    if owner.task_id != task.task_id:
        return (
            ScopeContinuationReason.CONTINUATION_OWNED_ELSEWHERE,
            "a later run of this continuation chain owns the remaining scope; continuing this "
            "run would queue the same remaining work twice",
            "open the linked continuation run and continue its remaining scope there",
        )
    if task.execute_authorized:
        # A persisted execute flag is a record of the original admission, never
        # a reusable credential.  The live authority must be proven again here,
        # by the same check the Worker repeats at every mutation boundary.
        proven = False
        if mutation_authority is not None:
            try:
                proven = bool(mutation_authority(task))
            except Exception:
                proven = False
        if not proven:
            return (
                ScopeContinuationReason.AUTHORITY_REQUIRED,
                _AUTHORITY_REASON,
                _NATIVE_AUTHORITY_NEXT_ACTION,
            )
    return None, None, None


def _active_continuation(repository, task_id: str, *, exclude_job_id: str | None):
    """The active continuation of one source Task, or ``None``.

    The Worker revalidating the continuation it already claimed excludes that
    exact Job, so it never refuses itself.
    """

    reader = getattr(repository, "get_scope_continuation_for_source_task", None)
    if not callable(reader):
        return None
    try:
        existing = reader(task_id)
    except Exception:
        return None
    if existing is None or not existing.active:
        return None
    if exclude_job_id is not None and existing.job_id == exclude_job_id:
        return None
    return existing


def continuation_chain(repository, task: PersistentTask) -> tuple[PersistentTask, ...]:
    """The whole recorded continuation chain that owns one Task's admitted scope.

    The chain is resolved only through explicit durable queued-continuation
    links and exact-Preview recovery links — never by filename, label or
    creation-time proximity. The root (the originally admitted Task) comes
    first and every descendant follows in link order, so the original item
    budget and every recorded item can be read together.
    """

    root = task
    ancestors = {task.task_id}
    link_reader = getattr(repository, "get_scope_continuation_for_new_task", None)
    recovery_reader = getattr(repository, "get_scope_recovery_for_new_task", None)
    if callable(link_reader) or callable(recovery_reader):
        for _ in range(_MAX_CHAIN_TASKS):
            link = None
            for reader in (link_reader, recovery_reader):
                if not callable(reader):
                    continue
                try:
                    link = reader(root.task_id)
                except Exception:
                    link = None
                if link is not None:
                    break
            parent_id = getattr(link, "source_task_id", None) if link is not None else None
            if not isinstance(parent_id, str) or not parent_id or parent_id in ancestors:
                break
            parent = repository.get_task(parent_id)
            if parent is None:
                break
            ancestors.add(parent_id)
            root = parent
    chain: list[PersistentTask] = [root]
    # The forward walk tracks its own visited set: an ancestor recorded while
    # walking up must not make the descendant that produced it look visited.
    seen = {root.task_id}
    pending: list[PersistentTask] = [root]
    lister = getattr(repository, "list_scope_continuations", None)
    recovery_lister = getattr(repository, "list_scope_recovery_links", None)
    if callable(lister) or callable(recovery_lister):
        while pending and len(chain) < _MAX_CHAIN_TASKS:
            current = pending.pop(0)
            links = []
            for reader in (lister, recovery_lister):
                if not callable(reader):
                    continue
                try:
                    links.extend(reader(current.task_id))
                except Exception:
                    continue
            links.sort(
                key=lambda value: getattr(value, "created_at", datetime.min.replace(tzinfo=UTC))
            )
            for link in links:
                child_id = getattr(link, "new_task_id", None)
                if not isinstance(child_id, str) or not child_id or child_id in seen:
                    continue
                child = repository.get_task(child_id)
                if child is None:
                    continue
                seen.add(child_id)
                chain.append(child)
                pending.append(child)
    return tuple(chain)


def chain_owner(repository, task: PersistentTask) -> PersistentTask:
    """The chain Task that currently owns the remaining scope.

    A later non-terminal Task of the chain (a continuation that paused or is
    still running) owns the remaining scope: it carries its own recorded items,
    pin and remaining budget, so the earlier run must not queue that scope a
    second time.  When every later Task is terminal, the deepest Task is the
    last known owner and the caller applies the remaining-budget decision.
    """

    chain = continuation_chain(repository, task)
    for value in reversed(chain):
        if value.status not in _CHAIN_TERMINAL_STATUSES:
            return value
    return chain[-1]


def remaining_scope(
    repository,
    task: PersistentTask,
) -> tuple[tuple[PersistentTaskItem, ...], frozenset[tuple[str, str]], int | None]:
    """The exact remaining admitted scope of one paused Task.

    Returns ``(remaining_items, already_recorded_sources, remaining_limit)``.

    The computation spans the whole recorded continuation chain, so a finished
    or still-paused descendant can never make the original run look unfinished:

    * ``already_recorded_sources`` is **every** recorded item's
      ``(storage_id, source_path)`` across the chain — including the terminal
      ones — so the continuation's discovery walk can never re-record or
      re-process a source any attempt of the chain already owns;
    * ``remaining_items`` are the still-undecided items of the chain;
    * ``remaining_limit`` is the **root** Task's originally admitted
      ``item_limit`` minus every item the chain already recorded, so discovery
      and continuation never broaden the admitted budget.
    """

    chain = continuation_chain(repository, task)
    root = chain[0]
    items = tuple(item for value in chain for item in repository.list_items(value.task_id))
    results = tuple(result for value in chain for result in repository.list_results(value.task_id))
    terminal = {
        result.item_id
        for result in results
        if result.status in _TERMINAL_RESULT_STATUSES
        or result.effect_certainty == _UNCERTAIN_EFFECT_CERTAINTY
    }
    remaining = tuple(
        item
        for item in items
        if item.status in _REMAINING_ITEM_STATUSES and item.item_id not in terminal
    )
    already_recorded = frozenset((item.storage_id, item.source_path) for item in items)
    remaining_limit = max(0, root.item_limit - len(items)) if root.item_limit is not None else None
    return remaining, already_recorded, remaining_limit


class ScopeContinuationService:
    """Shared API/Web admission of exactly one paused-scope continuation."""

    MAX_ACTOR = 200
    MAX_VERSION = 128

    def __init__(
        self,
        repository,
        *,
        snapshot_validator: Callable[[str, str], None] | None = None,
        mutation_authority: Callable[[PersistentTask], bool] | None = None,
    ) -> None:
        self._repository = repository
        self._snapshot_validator = snapshot_validator
        self._mutation_authority = mutation_authority

    @property
    def repository(self):
        return self._repository

    def obstacle(
        self, task: PersistentTask
    ) -> tuple[ScopeContinuationReason | None, str | None, str | None]:
        """The exact decision this boundary would apply to one Task.

        The API and the lifecycle projection call this so a recovery surface is
        offered for exactly the refusal the admission would really return, using
        the same validator and live-authority checker rather than a re-derived
        approximation.
        """

        return continuation_obstacle(
            self._repository, task, self._snapshot_validator, self._mutation_authority
        )

    def submit(
        self,
        task_id: str,
        *,
        expected_version: str | None,
        actor: str,
        maximum_active_jobs: int,
        mutation_authority: Callable[[PersistentTask], bool] | None = None,
    ) -> ScopeContinuationSubmission:
        """Admit one bounded queued continuation of the exact remaining scope."""

        task_id = self._required_id(task_id, "Task ID")
        actor = self._actor(actor)
        if expected_version is not None:
            expected_version = self._bounded(expected_version, self.MAX_VERSION, "Task version")
        self._require_capacity(maximum_active_jobs)

        task = self._repository.get_task(task_id)
        if task is None:
            raise ScopeContinuationError(
                ScopeContinuationReason.TASK_NOT_FOUND,
                "the Task was not found",
                durable_state="no Task exists under this identity",
                next_action="refresh the run inventory and select the exact run again",
            )
        if expected_version is not None and expected_version != task.updated_at.isoformat():
            raise ScopeContinuationError(
                ScopeContinuationReason.STALE_TASK_STATE,
                "the Task changed after the submitted state was read",
                durable_state="the submitted Task version is no longer the durable version",
                next_action=(
                    "reload the Task, review its current state, and continue again deliberately"
                ),
                retry_safe=True,
                current_version=task.updated_at.isoformat(),
            )
        if task.status is not PersistentTaskStatus.PAUSED:
            raise ScopeContinuationError(
                ScopeContinuationReason.TASK_NOT_PAUSED,
                f"only a durably paused Task has a remaining scope to continue; this Task is "
                f"{task.status.value}",
                durable_state=f"the Task remains {task.status.value}",
                next_action="refresh the Task and continue it only while it is durably paused",
                current_version=task.updated_at.isoformat(),
            )
        if not is_continuable_task_command(task.command):
            raise ScopeContinuationError(
                ScopeContinuationReason.COMMAND_NOT_CONTINUABLE,
                "this Task kind has no supported durable queued continuation of its exact "
                "remaining scope",
                durable_state=(
                    "the Task keeps its paused state and its independently recorded item outcomes"
                ),
                next_action=(
                    "use the run's own native evidence and controls; this Task kind is not "
                    "continued through the queued Worker boundary"
                ),
            )
        reason, message, next_action = continuation_obstacle(
            self._repository,
            task,
            self._snapshot_validator,
            mutation_authority if mutation_authority is not None else self._mutation_authority,
        )
        if reason is not None:
            existing = (
                self._repository.get_scope_continuation_for_source_task(task_id)
                if reason is ScopeContinuationReason.CONTINUATION_EXISTS
                else None
            )
            raise ScopeContinuationError(
                reason,
                message or "the Task cannot be continued in its current state",
                durable_state=(
                    "the existing continuation owns the remaining scope and will be claimed by "
                    "the resident Worker"
                    if existing is not None
                    else "the Task keeps its paused state, its recorded item outcomes and its "
                    "completed effects; no further mutation was attempted"
                ),
                next_action=next_action or "refresh the Task and review its current state",
                current_version=task.updated_at.isoformat(),
                existing_continuation=existing,
            )

        now = datetime.now(UTC)
        job = AutomationJob(
            str(uuid4()),
            AutomationCommand.SCOPE_CONTINUATION,
            AutomationJobStatus.PENDING,
            now,
            now,
            limit=task.item_limit,
            execute_authorized=False,
            configuration_snapshot_id=task.configuration_snapshot_id,
            configuration_snapshot_digest=task.configuration_snapshot_digest,
        )
        continuation = ScopeContinuation(
            str(uuid4()),
            task.task_id,
            task.command,
            task.scope_path,
            task.item_limit,
            task.configuration_snapshot_id or "",
            task.configuration_snapshot_digest or "",
            CONTINUATION_BOUNDARY,
            ScopeContinuationStatus.QUEUED,
            now,
            now,
            actor,
            job.job_id,
        )
        admitted, created = self._repository.admit_scope_continuation(
            job, continuation, maximum_active_jobs=maximum_active_jobs
        )
        if not created:
            raise ScopeContinuationError(
                ScopeContinuationReason.CONTINUATION_EXISTS,
                "this Task already has an active queued continuation",
                durable_state=(
                    "the existing continuation owns the remaining scope and will be claimed by "
                    "the resident Worker"
                ),
                next_action="follow the existing continuation run instead of submitting again",
                existing_continuation=admitted,
            )
        return ScopeContinuationSubmission(admitted, job, True)

    def prepare(self, job_id: str) -> PreparedScopeContinuation:
        """Revalidate one claimed continuation before any adapter is constructed."""

        job = self._repository.get_job(job_id)
        if job is None:
            raise LookupError(f"automation Job {job_id!r} was not found")
        continuation = self._repository.get_scope_continuation_for_job(job_id)
        if continuation is None:
            raise LookupError(f"scope continuation for Job {job_id!r} was not found")
        if continuation.status not in {
            ScopeContinuationStatus.QUEUED,
            ScopeContinuationStatus.RUNNING,
        }:
            raise ValueError("scope continuation is not active")
        task = self._repository.get_task(continuation.source_task_id)
        if task is None:
            raise ValueError("scope continuation source Task is unavailable")
        if (
            task.command != continuation.command
            or task.scope_path != continuation.scope_path
            or task.item_limit != continuation.item_limit
            or task.configuration_snapshot_id != continuation.configuration_snapshot_id
            or task.configuration_snapshot_digest != continuation.configuration_snapshot_digest
        ):
            raise ValueError("scope continuation source Task scope or pin changed")
        if not is_continuable_task_command(task.command):
            raise ValueError("scope continuation command is not supported")
        self._require_live_obstacle(task, exclude_job_id=job_id)
        remaining, already_recorded, remaining_limit = remaining_scope(self._repository, task)
        return PreparedScopeContinuation(
            continuation, task, remaining, already_recorded, remaining_limit
        )

    def _require_live_obstacle(
        self, task: PersistentTask, *, exclude_job_id: str | None = None
    ) -> None:
        """Refuse a claimed continuation whose live evidence no longer holds.

        The Worker re-reads the same obstacle the admission boundary and the
        lifecycle projection read, so a continuation whose pinned revision
        became unresolvable, or whose live mutation authority was revoked,
        stops with zero new mutation instead of executing under stale authority.
        The claimed continuation's own Job is excluded, so the Worker never
        refuses itself as a duplicate.
        """

        reason, message, next_action = continuation_obstacle(
            self._repository,
            task,
            self._snapshot_validator,
            self._mutation_authority,
            exclude_job_id=exclude_job_id,
        )
        if reason is not None:
            raise ScopeContinuationError(
                reason,
                message or "the Task can no longer be continued",
                durable_state=(
                    "the Task keeps its paused state, its recorded item outcomes and its "
                    "completed effects; no further mutation was attempted"
                ),
                next_action=next_action or "refresh the Task and review its current state",
            )

    @staticmethod
    def _require_capacity(maximum_active_jobs: int) -> None:
        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or not 1 <= maximum_active_jobs <= 10_000
        ):
            raise ScopeContinuationError(
                ScopeContinuationReason.INVALID_INPUT,
                "maximum active Jobs must be between 1 and 10000",
                next_action="correct the configured queue capacity and retry",
            )

    @staticmethod
    def _required_id(value: str, label: str) -> str:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value.strip()):
            raise ScopeContinuationError(
                ScopeContinuationReason.INVALID_INPUT,
                f"{label} is invalid",
                next_action="reload the run inventory and continue the exact run again",
            )
        return value.strip()

    @staticmethod
    def _bounded(value: str, limit: int, label: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ScopeContinuationError(
                ScopeContinuationReason.INVALID_INPUT,
                f"{label} is invalid",
                next_action="reload the Task and continue it again deliberately",
            )
        return value.strip()

    @classmethod
    def _actor(cls, value: str | None) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ScopeContinuationError(
                ScopeContinuationReason.INSUFFICIENT_PERMISSION,
                "continuation actor is required",
                next_action="authenticate again, then continue the paused Task",
            )
        normalized = " ".join(value.split())
        if len(normalized) > cls.MAX_ACTOR:
            raise ScopeContinuationError(
                ScopeContinuationReason.INVALID_INPUT,
                "continuation actor is too long",
                next_action="authenticate again, then continue the paused Task",
            )
        return normalized


class ScopeContinuationWorkerService:
    """Durable claim/outcome boundary around the existing processing pipeline."""

    def __init__(self, repository) -> None:
        self._repository = repository

    def started(self, job_id: str) -> ScopeContinuation:
        return self._repository.mark_scope_continuation_running(job_id)

    def bind(self, job_id: str, task_id: str) -> ScopeContinuation:
        return self._repository.bind_scope_continuation_task(job_id, task_id)

    def cancelled(self, job_id: str) -> ScopeContinuation:
        return self._repository.cancel_scope_continuation(job_id)

    def finish(self, job_id: str, task_id: str) -> ScopeContinuation:
        """Resolve the continuation from the new Task's own durable outcome.

        The continuation reports success only when the linked Task really
        reached a successful terminal state; a paused, cancelled, failed or
        partial linked Task stays a truthful failure of this continuation, and
        its per-item outcomes remain independently inspectable.
        """

        task = self._repository.get_task(task_id)
        if task is None:
            return self._repository.complete_scope_continuation(
                job_id,
                new_task_id=task_id,
                success=False,
                error="continuation Task was not persisted",
                recovery=(
                    "refresh the run inventory; the original paused scope is unchanged and can "
                    "be continued again"
                ),
            )
        if task.status is PersistentTaskStatus.COMPLETED:
            return self._repository.complete_scope_continuation(
                job_id, new_task_id=task_id, success=True
            )
        if task.status is PersistentTaskStatus.PAUSED:
            error = "the continuation paused again before completing its remaining scope"
            recovery = "refresh the Task and continue its remaining scope again when it is paused"
        elif task.status is PersistentTaskStatus.CANCELLED:
            error = "the continuation was cancelled"
            recovery = (
                "refresh the Task; completed effects are preserved and remaining items keep "
                "their own outcome"
            )
        elif task.status is PersistentTaskStatus.PARTIAL_SUCCESS:
            error = "the continuation completed only part of its remaining scope"
            recovery = (
                "inspect the linked continuation run's per-item outcomes, then continue only "
                "the still-eligible items"
            )
        else:
            error = "the continuation failed before completing its remaining scope"
            recovery = (
                "inspect the linked continuation run, repair the stated condition, then "
                "continue the remaining scope again"
            )
        return self._repository.complete_scope_continuation(
            job_id, new_task_id=task_id, success=False, error=error, recovery=recovery
        )

    def failed(
        self,
        job_id: str,
        *,
        task_id: str | None = None,
        queued: bool = False,
        error: str | None = None,
        recovery: str | None = None,
    ) -> None:
        message = error or "scope continuation failed before Task completion"
        next_action = recovery or (
            "inspect the linked continuation run, repair the stated condition, then continue "
            "the remaining scope again"
        )
        try:
            if queued:
                self._repository.fail_queued_scope_continuation(
                    job_id, error=message, recovery=next_action
                )
            else:
                self._repository.complete_scope_continuation(
                    job_id,
                    new_task_id=task_id,
                    success=False,
                    error=message,
                    recovery=next_action,
                )
        except (LookupError, ValueError):
            pass


__all__ = [
    "PreparedScopeContinuation",
    "ScopeContinuationService",
    "ScopeContinuationSubmission",
    "ScopeContinuationWorkerService",
    "is_continuable_task_command",
    "remaining_scope",
]
