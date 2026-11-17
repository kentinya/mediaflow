"""Read-only same-Task recovery eligibility.

A recovery preparation is admitted while its exact source is still undecided,
but its discovery, freeze and analysis happen later.  The operator can
legitimately confirm and execute an earlier preparation in between, so every
publication boundary re-asks this one module whether the original Task still
holds an undecided source under the same immutable pin.

The current recovery continues the *same* Task: the admitted items, their
Results and the confirmed summary are all bound to that Task identity.  Nothing
here mutates Storage, grants authority or walks a cross-Task ancestry.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    """Every decided item identity and decided source of one Task.

    A decided outcome reaches the Task through either row shape, and both are
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


def is_continuable_task_command(command: object) -> bool:
    """Whether one durable Task command has a supported remaining-scope boundary."""

    return isinstance(command, str) and command in CONTINUABLE_TASK_COMMANDS


def remaining_scope(
    repository,
    task: PersistentTask,
) -> tuple[tuple[PersistentTaskItem, ...], frozenset[tuple[str, str]], int | None]:
    """The exact remaining admitted scope of one same-Task recovery source.

    Returns ``(remaining_items, already_recorded_sources, remaining_limit)``.

    * ``already_recorded_sources`` is every recorded item's
      ``(storage_id, source_path)`` so a preparation can never re-record or
      re-process a source this Task already owns;
    * ``remaining_items`` are the still-undecided items of this Task;
    * ``remaining_limit`` is the Task's originally admitted ``item_limit`` minus
      every distinct source it already recorded, so recovery never broadens the
      admitted budget.

    An outcome is resolved **per source**, not only per item identity: a later
    attempt of the same Task records its own item and Result, so matching on
    ``item_id`` alone would leave an earlier item undecided after the same
    source was really completed.  The recorded history itself is never
    rewritten: this is a read-time projection over the existing Task/Result
    rows.
    """

    items = tuple(repository.list_items(task.task_id))
    results = tuple(repository.list_results(task.task_id))
    decided_items, decided_observations = _decided_source_observations(items, results)
    remaining = tuple(
        item
        for item in items
        if item.status in _REMAINING_ITEM_STATUSES
        and item.item_id not in decided_items
        and not any(observation.is_the_same_file_as(item) for observation in decided_observations)
    )
    already_recorded = frozenset((item.storage_id, item.source_path) for item in items)
    if task.item_limit is None:
        remaining_limit = None
    else:
        # A recorded item occupies a unit of the originally admitted budget.
        # A re-observation of an *already admitted* source is the same unit of
        # work, not a new one, so the budget is counted over distinct sources.
        recorded_units = len({(item.storage_id, item.source_path) for item in items})
        remaining_limit = max(0, task.item_limit - recorded_units)
    return remaining, already_recorded, remaining_limit


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

        ``eligible`` is only a statement about the whole Task: it says the
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
    ``Task.updated_at`` — the deciding evidence is recorded on that same Task's
    own items, Results and confirmed summary.

    The revalidation reads only durable evidence:

    * the source Task must still be a paused, continuable admission with the
      same immutable pin that was admitted;
    * the Task must still hold at least one undecided source (a completed,
      ignored or uncertain attempt retires it);
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
