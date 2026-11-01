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
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from mediaflow.domain.organizer import ExecutionEffectCertainty
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)

CONTINUABLE_TASK_COMMANDS = frozenset({"preview", "organize"})


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
_NO_REMAINING_SCOPE_NEXT_ACTION = (
    "inspect the linked continuation run and its independent per-item results, or start "
    "a new bounded run from 操作与任务"
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
#:
#: The comparison is case-folded because two real producers write the same
#: disposition with different case: the workflow pipeline stores the
#: ``TaskItemStatus`` value (``success``/``skipped``) while the manual-Organize
#: executor stores the organizer's own ``ExecutionStatus`` value
#: (``SUCCESS``/``SKIPPED``).  Reading only the lowercase form would silently
#: treat a really successful recovery Result as undecided.
_TERMINAL_RESULT_STATUSES = frozenset(
    {
        TaskItemStatus.SUCCESS.value,
        TaskItemStatus.DRY_RUN.value,
        TaskItemStatus.SKIPPED.value,
        TaskItemStatus.IGNORED.value,
    }
)

#: Any effect the executor never verified is never replayed automatically:
#: MediaFlow cannot prove the interrupted mutation did not happen, so it stays
#: investigation-only.  ``unknown`` is the executor's own value for an
#: invocation that may have crossed the mutation boundary.
_UNCERTAIN_EFFECT_CERTAINTIES = frozenset(
    {"attempted_unverified", ExecutionEffectCertainty.UNKNOWN.value}
)


def _result_is_decided(result: PersistentResultRecord) -> bool:
    """Whether one recorded Result already proves a decided outcome.

    Both a terminal disposition and an unverified effect are decided: the first
    has nothing left to do, the second may only ever be investigated.  A Result
    whose primary operation was verified complete is decided even when its
    status is ``PARTIAL``: the remaining warnings belong to independent
    attachments, which are never resolved by replaying the primary.

    The comparison is case-folded because two real producers write the same
    disposition with different case — the workflow pipeline stores the
    ``TaskItemStatus`` value (``success``/``skipped``) while the manual-Organize
    executor stores the organizer's own ``ExecutionStatus`` value
    (``SUCCESS``/``SKIPPED``).  Matching only the lowercase spelling would
    silently treat a really successful recovery Result as undecided and allow
    the same source to be executed again.
    """

    status = result.status.strip().lower() if isinstance(result.status, str) else ""
    certainty = (
        result.effect_certainty.strip().lower() if isinstance(result.effect_certainty, str) else ""
    )
    return (
        status in _TERMINAL_RESULT_STATUSES
        or certainty in _UNCERTAIN_EFFECT_CERTAINTIES
        or bool(result.primary_completed)
    )


@dataclass(frozen=True)
class _SourceObservation:
    """One bounded source observation that already carries a decided outcome."""

    storage_id: str
    path: str
    fingerprint: str | None

    def is_the_same_file_as(self, item: PersistentTaskItem) -> bool:
        """Whether this decided observation provably names this item's source.

        Storage and the exact relative path always have to match.  When both
        sides carry a verified fingerprint the two are additionally required to
        be equal, so a file *replaced* at the same path keeps its own undecided
        state instead of inheriting the previous file's outcome.  A legacy or
        externally written row without any fingerprint evidence cannot be
        compared, so it is conservatively treated as the same source: refusing a
        duplicate mutation is always preferable to silently repeating one, and
        the item keeps its own recorded history either way.
        """

        if self.storage_id != item.storage_id or self.path != item.source_path:
            return False
        if not self.fingerprint or not item.source_fingerprint:
            return True
        return self.fingerprint == item.source_fingerprint


def _decided_source_observations(
    items: tuple[PersistentTaskItem, ...],
    results: tuple[PersistentResultRecord, ...],
) -> tuple[set[str], tuple[_SourceObservation, ...]]:
    """Every decided item identity and decided source of one recorded chain.

    A decided outcome reaches the chain through either row shape, and both are
    real:

    * a Result is the authoritative record of an executed item, and its
      ``item_id`` names the attempt that actually ran;
    * an explicit operator decision (ignore) and a read-only completion rewrite
      only the TaskItem, so no Result exists for them.

    Reading both keeps an ignored or dry-run attempt from being forgotten while
    still letting a Result retire an ancestor attempt of the same source.
    """

    decided_items: set[str] = set()
    observations: list[_SourceObservation] = []
    for result in results:
        if not _result_is_decided(result):
            continue
        decided_items.add(result.item_id)
        if isinstance(result.source_storage_id, str) and isinstance(result.source_path, str):
            if result.source_storage_id and result.source_path:
                observations.append(
                    _SourceObservation(
                        result.source_storage_id,
                        result.source_path,
                        result.source_fingerprint or None,
                    )
                )
    for item in items:
        if item.status in _REMAINING_ITEM_STATUSES or item.status.value.startswith("waiting"):
            continue
        decided_items.add(item.item_id)
        observations.append(
            _SourceObservation(
                item.storage_id,
                item.source_path,
                item.source_fingerprint or None,
            )
        )
    return decided_items, tuple(observations)


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
class RecoveryScopePlan:
    """The exact scope one remaining-scope *recovery preparation* may observe.

    ``unrecorded_budget`` decides the observable shape of the preparation:

    * ``0`` means the original admission is fully recorded, so the only work that
      can legitimately still be reviewed is the recorded-but-undecided set
      itself.  The preparation then observes exactly those sources, so a file
      that appeared in the directory afterwards can neither borrow the undecided
      unit nor silently replace or widen the reviewed scope;
    * a positive value (or ``None`` for an unlimited admission) leaves real
      discovery budget, so the preparation walks the admitted directory and the
      existing budget/stability rules apply exactly as an ordinary admission.
    """

    undecided_items: tuple[PersistentTaskItem, ...]
    replay_excluded: frozenset[tuple[str, str]]
    new_source_budget: int | None
    unrecorded_budget: int | None


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

    An outcome is resolved **per source**, not only per item identity: a later
    attempt of the chain (an exact-Preview recovery execution, a queued
    continuation Task) records its own item and Result under its own item ID,
    so matching on ``item_id`` alone would leave the ancestor item undecided
    after the same source was really completed.  A decided outcome therefore
    retires every chain item that provably names the same source: the same
    Storage, the same ResourceLibrary and the same exact relative path, and —
    when both sides recorded verified occurrence evidence — the same
    fingerprint.  A replaced file at the same path keeps its own undecided
    state because its fingerprint differs, and a success recorded for a
    different Storage/library/path never retires this source.  The recorded
    history itself is never rewritten: this is a read-time projection over the
    existing Task/Result rows.
    """

    chain = continuation_chain(repository, task)
    root = chain[0]
    items = tuple(item for value in chain for item in repository.list_items(value.task_id))
    results = tuple(result for value in chain for result in repository.list_results(value.task_id))
    decided_items, decided_observations = _decided_source_observations(items, results)
    remaining = tuple(
        item
        for item in items
        if item.status in _REMAINING_ITEM_STATUSES
        and item.item_id not in decided_items
        and not any(observation.is_the_same_file_as(item) for observation in decided_observations)
    )
    already_recorded = frozenset((item.storage_id, item.source_path) for item in items)
    if root.item_limit is None:
        remaining_limit = None
    else:
        # A recorded item occupies a unit of the originally admitted budget.
        # A re-observation of an *already admitted* source (a recovery
        # execution, a continued attempt) is the same unit of work, not a new
        # one, so the budget is counted over distinct sources: an extra attempt
        # must neither shrink nor widen what the operator originally admitted.
        recorded_units = len({(item.storage_id, item.source_path) for item in items})
        remaining_limit = max(0, root.item_limit - recorded_units)
    return remaining, already_recorded, remaining_limit


def recovery_scope(
    repository,
    task: PersistentTask,
) -> tuple[tuple[PersistentTaskItem, ...], frozenset[tuple[str, str]], int | None]:
    """The exact ``(undecided, replay_excluded, new_source_budget)`` triple.

    This stays the compact public shape both the admission and its existing
    callers read.  :func:`recovery_scope_plan` is the same computation plus the
    extra ``unrecorded_budget`` fact that decides the observable shape of a
    preparation, so the two can never disagree.
    """

    plan = recovery_scope_plan(repository, task)
    return plan.undecided_items, plan.replay_excluded, plan.new_source_budget


def recovery_scope_plan(
    repository,
    task: PersistentTask,
) -> RecoveryScopePlan:
    """The exact scope a remaining-scope *recovery preparation* may still offer.

    The two recorded sets are kept deliberately distinct:

    * ``undecided_items`` are the chain's still-undecided items.  They are part
      of the recovery scope: the operator explicitly asked to review exactly
      what is left, and a pending/processing/failed/paused item has no decided
      outcome yet, so refusing or silently skipping it would lose the remaining
      work;
    * ``replay_excluded`` are the recorded sources whose outcome is already
      decided: a successful/dry-run sibling, an explicit ignore, or an uncertain
      effect that must only ever be investigated.  They are never observed,
      re-offered or replayed;
    * ``new_source_budget`` is the number of *further* sources the walk may still
      discover.  Undecided items already occupy their unit of the original
      admitted budget (they are recorded items), so they are not deducted twice;
      the budget is never enlarged beyond the original admission;
    * ``unrecorded_budget`` is the part of the original admission no recorded
      item occupies.  It is ``0`` exactly when the admission is fully recorded,
      which is what makes the preparation observe the undecided set itself
      instead of re-walking a directory that now advertises further sources.

    A chain whose recorded items consumed the whole original budget still keeps
    its undecided items recoverable; only a chain with neither an undecided item
    nor any remaining budget has truly nothing left to prepare.
    """

    remaining, already_recorded, remaining_limit = remaining_scope(repository, task)
    # The undecided set is reduced to one entry per exact source.  A later
    # attempt of the chain records its own item for the same source, so the
    # reviewed/observed scope is the set of distinct undecided *sources*, not
    # one observation row per attempt; otherwise the same file could be offered
    # (and executed) once per earlier attempt.
    undecided_items: list[PersistentTaskItem] = []
    seen_sources: set[tuple[str, str]] = set()
    for item in remaining:
        source = (item.storage_id, item.source_path)
        if source in seen_sources:
            continue
        seen_sources.add(source)
        undecided_items.append(item)
    undecided = frozenset(seen_sources)
    replay_excluded = already_recorded - undecided
    if remaining_limit is None:
        new_source_budget = None
    else:
        # The undecided sources are already inside the original admission, so
        # they stay admissible on top of the still-unrecorded budget.  The
        # still-unrecorded part is measured over distinct sources as well, so an
        # extra attempt of an already admitted source never enlarges the
        # operator's original admission.
        new_source_budget = remaining_limit + len(undecided_items)
    return RecoveryScopePlan(
        tuple(undecided_items),
        replay_excluded,
        new_source_budget,
        remaining_limit,
    )


class RecoveryPreparationState(StrEnum):
    """Whether an admitted recovery preparation may still offer its scope."""

    ELIGIBLE = "eligible"
    STALE = "stale"


@dataclass(frozen=True)
class RecoveryPreparationEligibility:
    """The exact live qualification of one already-admitted preparation.

    ``state`` is ``ELIGIBLE`` while the preparation may still observe and
    publish its scope.  ``STALE`` is a terminal, explainable outcome: the
    original paused admission, its immutable pin or the classification of the
    remaining sources changed after admission, so the preparation may no longer
    publish a summary, authorize or execute.  ``code``/``message``/``next_action``
    are bounded, secret-free operator text; nothing here mutates media.
    """

    state: RecoveryPreparationState
    #: ``False`` for an ordinary Files/definition admission: the recovery
    #: contract does not govern it at all, so every source stays offerable.
    applies: bool = True
    code: str | None = None
    message: str | None = None
    next_action: str | None = None
    undecided_sources: frozenset[tuple[str, str]] = frozenset()
    decided_sources: frozenset[tuple[str, str]] = frozenset()
    #: Whether the original admission still holds unrecorded discovery budget,
    #: i.e. whether a source that no attempt has recorded yet may legitimately
    #: be observed by this preparation.
    allow_new_sources: bool = False

    @property
    def eligible(self) -> bool:
        return self.state is RecoveryPreparationState.ELIGIBLE

    def may_offer(self, storage_id: str, path: str) -> bool:
        """Whether one observed source may still appear in this preparation.

        A recorded-but-undecided source is the preparation's actual remaining
        work.  A source the chain already decided (success, ignore, unknown
        effect, or a verified primary with attachment warnings) may never be
        re-offered, even though it was still undecided when this preparation was
        admitted.  A source no attempt has recorded is only legitimate while the
        original admission really has unrecorded discovery budget left.
        """

        if not self.applies:
            return True
        source = (storage_id, path)
        if source in self.undecided_sources:
            return True
        if source in self.decided_sources:
            return False
        return self.allow_new_sources

    def check_sources(self, sources) -> tuple[bool, ...]:
        """Whether each exact observed source may still be offered or executed.

        ``eligible`` is only a statement about the *whole* chain: it says the
        preparation still has work somewhere.  It is deliberately **not** a
        licence for every individual source, because a mixed scope stays
        eligible while one sibling is still undecided even though another was
        decided by an earlier attempt.  A boundary that is about to publish,
        authorize, admit or execute an exact source set must therefore ask this
        per-source verdict instead of trusting the chain-level ``eligible``
        flag, which would let the decided sibling through on the strength of an
        unrelated legal one.

        ``sources`` is an iterable of ``(storage_id, path)`` pairs.  The
        returned tuple carries one verdict per input in the same order, so a
        caller can keep the legal siblings and refuse only the sources this
        chain already decided.  An ordinary (non-recovery) admission is never
        governed and every source stays legal; a stale preparation refuses
        every source.
        """

        values = tuple((storage_id, path) for storage_id, path in sources)
        if not self.applies:
            return tuple(True for _ in values)
        if not self.eligible:
            return tuple(False for _ in values)
        return tuple(self.may_offer(storage_id, path) for storage_id, path in values)

    def refused_sources(self, sources) -> tuple[tuple[str, str], ...]:
        """The exact subset of ``sources`` this preparation may no longer offer.

        A read-only projection of :meth:`check_sources` for boundaries that
        need to name which selected source was retired (for a bounded refusal
        detail or for trimming a frozen manifest).
        """

        values = tuple((storage_id, path) for storage_id, path in sources)
        return tuple(
            source
            for source, allowed in zip(values, self.check_sources(values), strict=True)
            if not allowed
        )


def recovery_preparation_eligibility(
    repository,
    *,
    recovery_source_task_id: str | None,
    snapshot_id: str | None = None,
    snapshot_digest: str | None = None,
) -> RecoveryPreparationEligibility:
    """Revalidate one already-admitted recovery preparation against live truth.

    A preparation is admitted while its exact source is still undecided, but its
    discovery, freeze and analysis happen later, in the resident Worker, and the
    operator can legitimately confirm and execute an *earlier* preparation in
    between.  Persisting the admission is therefore not a licence to publish a
    summary much later: every publication boundary (and the execution admission
    itself) re-asks this one function instead of comparing the original
    ``Task.updated_at`` — the deciding evidence lives in a *descendant* Task and
    changes while the original Task row does not.

    The revalidation reads only durable evidence:

    * the source Task must still be a paused, continuable admission with the
      same immutable pin that was admitted;
    * the whole explicit continuation chain must still hold at least one
      undecided source (a completed, ignored or uncertain attempt retires it);
    * wherever the caller supplies its own pin, that pin must equal the source
      Task's pin, so a preparation can never observe one revision and publish a
      summary bound to another.

    A repository that cannot answer the chain reads as ineligible: refusing a
    duplicate mutation is always preferable to replaying one.
    """

    if not isinstance(recovery_source_task_id, str) or not recovery_source_task_id.strip():
        # Not a recovery preparation: an ordinary Files/definition admission is
        # untouched by the recovery contract.
        return RecoveryPreparationEligibility(RecoveryPreparationState.ELIGIBLE, applies=False)
    reader = getattr(repository, "get_task", None)
    task = reader(recovery_source_task_id) if callable(reader) else None
    if task is None:
        return RecoveryPreparationEligibility(
            RecoveryPreparationState.STALE,
            code="recovery_source_unavailable",
            message="the run this preparation belongs to no longer exists",
            next_action=(
                "the original paused run is unavailable, so its remaining scope cannot be "
                "reviewed; start a new bounded run from 操作与任务"
            ),
        )
    if task.status is not PersistentTaskStatus.PAUSED:
        return RecoveryPreparationEligibility(
            RecoveryPreparationState.STALE,
            code="recovery_source_not_paused",
            message=(
                "the run this preparation belongs to is no longer paused; it is "
                f"{task.status.value}"
            ),
            next_action=("review the run's recorded per-item outcomes, or start a new bounded run"),
        )
    if (
        not is_continuable_task_command(task.command)
        or not task.configuration_snapshot_id
        or not task.configuration_snapshot_digest
    ):
        return RecoveryPreparationEligibility(
            RecoveryPreparationState.STALE,
            code="recovery_pin_unavailable",
            message=(
                "the run's original admitted scope or immutable configuration pin is no longer "
                "available"
            ),
            next_action="start a new bounded run under the current Active configuration",
        )
    if snapshot_id is not None and snapshot_id != task.configuration_snapshot_id:
        return RecoveryPreparationEligibility(
            RecoveryPreparationState.STALE,
            code="recovery_pin_mismatch",
            message=(
                "this preparation was admitted under a different configuration revision than "
                "the run it belongs to"
            ),
            next_action="open the run again and request a fresh plan summary under its own pin",
        )
    if snapshot_digest is not None and snapshot_digest != task.configuration_snapshot_digest:
        return RecoveryPreparationEligibility(
            RecoveryPreparationState.STALE,
            code="recovery_pin_mismatch",
            message=(
                "this preparation's configuration digest no longer matches the run it belongs to"
            ),
            next_action="open the run again and request a fresh plan summary under its own pin",
        )
    try:
        plan = recovery_scope_plan(repository, task)
    except Exception:
        return RecoveryPreparationEligibility(
            RecoveryPreparationState.STALE,
            code="recovery_scope_unresolved",
            message="the run's recorded remaining scope can no longer be resolved",
            next_action=(
                "inspecting the run's recorded per-item outcomes is the only safe next step"
            ),
        )
    undecided = frozenset((item.storage_id, item.source_path) for item in plan.undecided_items)
    decided = frozenset(plan.replay_excluded)
    allow_new = plan.new_source_budget != 0
    if not undecided and not allow_new:
        return RecoveryPreparationEligibility(
            RecoveryPreparationState.STALE,
            code="recovery_scope_decided",
            message=(
                "every source this preparation was admitted for now has a decided outcome, so "
                "nothing remains to review or confirm"
            ),
            next_action=(
                "open the run and review its recorded per-item outcomes; a decided or uncertain "
                "effect is never repeated"
            ),
        )
    return RecoveryPreparationEligibility(
        RecoveryPreparationState.ELIGIBLE,
        undecided_sources=undecided,
        decided_sources=decided,
        allow_new_sources=allow_new,
    )
