"""The one read-only interpretation of durable direct-file work.

Ordinary Files/MediaLibrary maintenance (Create Folder/Text, Rename, bounded
text Save, Copy, Move, Delete) is persisted as Task/TaskItem/Result rows plus,
for the transfer families, an in-flight per-entry progress snapshot.  Two
surfaces read that evidence: the transfer/Delete operator projections and the
per-library local status read.  They must never grow two interpretations of the
same rows — an operator who reads a paused folder Move on the page and in the
transfer dialog has to see the same moved children, the same per-entry status
and the same effect certainty.

This module therefore owns that interpretation and nothing else:

* the disposition of one item (queued/running/paused/terminal) from its durable
  status and its newest Result;
* its bounded per-entry outcomes — the created destination directory, each
  moved file with its completed executor checkpoints, each skipped or refused
  child — taken from the recorded progress snapshot while the item is still
  unfinished and from the Result annotations once it is terminal;
* whether the recorded evidence proves a real mutation at all; and
* the aggregate effect certainty of a set of such signals, where "no change"
  may only be claimed when the durable evidence proves it.

It performs no Storage, Provider, configuration or Task mutation, admits no
work and resolves no library.  Callers own their own authority checks.
"""

from __future__ import annotations

import json

from mediaflow.domain.organizer import ExecutionEffectCertainty
from mediaflow.domain.task_persistence import TaskItemStatus

__all__ = [
    "effect_certainty_of",
    "has_completed_mutation",
    "item_effect_signal",
    "item_known_mutation",
    "ITEM_TASK_INVERSE",
    "ITEM_TASK_STATUS",
    "progress_payload",
    "projection_effect",
    "projection_item_outcomes",
    "projection_item_status",
    "PROJECTION_EFFECT",
    "aggregate_effect_certainty",
    "EffectCertaintyFold",
    "TERMINAL_RESULT_STATUSES",
]

#: Result statuses that describe a real, already-decided outcome.
TERMINAL_RESULT_STATUSES = frozenset({"SUCCESS", "SKIPPED", "PARTIAL", "FAILED", "DRY_RUN"})

#: Result annotations that describe an entry's aggregate state rather than a
#: completed executor mutation.
_ANNOTATION_MARKERS = frozenset({"entry", "entry_error", "skip_conflict"})

#: The canonical aggregate status of one item, and its inverse projection for a
#: terminal TaskItem that has no Result record (a legacy or externally written
#: row): the projection still names a truthful state instead of fabricating
#: success.  ``UNCERTAIN`` is its own canonical outcome even though it is stored
#: as the ``PARTIAL`` item status.
ITEM_TASK_STATUS = {
    "SUCCESS": TaskItemStatus.SUCCESS,
    "SKIPPED": TaskItemStatus.SKIPPED,
    "PARTIAL": TaskItemStatus.PARTIAL,
    "UNCERTAIN": TaskItemStatus.PARTIAL,
    "FAILED": TaskItemStatus.FAILED,
}

ITEM_TASK_INVERSE = {
    TaskItemStatus.SUCCESS: "SUCCESS",
    TaskItemStatus.SKIPPED: "SKIPPED",
    TaskItemStatus.PARTIAL: "PARTIAL",
    TaskItemStatus.FAILED: "FAILED",
}

#: The durable projection's effect vocabulary for one item.  Items still
#: queued, running or paused are reported as in progress — never as
#: transferred.
PROJECTION_EFFECT = {
    "SUCCESS": "transferred",
    "SKIPPED": "skipped",
    "PARTIAL": "partial",
    "UNCERTAIN": "uncertain",
    "FAILED": "retained",
    "CANCELLED": "retained",
    "RUNNING": "in_progress",
    "QUEUED": "in_progress",
    "PAUSED": "in_progress",
}

#: Item statuses that no longer change without a new admission.
_SETTLED_ITEM_STATUSES = frozenset(
    {
        TaskItemStatus.SUCCESS,
        TaskItemStatus.PARTIAL,
        TaskItemStatus.FAILED,
        TaskItemStatus.SKIPPED,
        TaskItemStatus.IGNORED,
        TaskItemStatus.CANCELLED,
    }
)

_UNFINISHED_ITEM_STATUSES = frozenset(
    {
        TaskItemStatus.PENDING,
        TaskItemStatus.PROCESSING,
        TaskItemStatus.PAUSED,
        TaskItemStatus.WAITING_CONFIRM,
        TaskItemStatus.WAITING_RECOGNITION,
        TaskItemStatus.WAITING_METADATA,
        TaskItemStatus.WAITING_METADATA_CORRECTION,
        TaskItemStatus.WAITING_CLASSIFICATION,
    }
)

#: The bounded per-entry outcome surface of one operation read.
MAX_PROJECTION_EVENTS = 64


def progress_payload(item) -> dict[str, object] | None:
    """The parsed bounded progress snapshot of one transfer item, if any."""

    raw = getattr(item, "progress", None)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def has_completed_mutation(operations) -> bool:
    """Whether a Result's bounded annotations contain a real completed mutation."""

    return any(
        str(operation).partition(":")[0] not in _ANNOTATION_MARKERS for operation in operations
    )


def projection_item_status(item, record) -> str:
    """The truthful projection status of one direct-file item."""

    if item.status is TaskItemStatus.PENDING:
        return "QUEUED"
    if item.status is TaskItemStatus.PROCESSING:
        return "RUNNING"
    if item.status is TaskItemStatus.PAUSED:
        return "PAUSED"
    if item.status is TaskItemStatus.CANCELLED:
        return "CANCELLED"
    if record is not None:
        record_status = str(record.status).upper()
        if record_status in {"PARTIAL", "SKIPPED", "FAILED", "SUCCESS"}:
            return record_status
    return ITEM_TASK_INVERSE.get(item.status, "FAILED")


def projection_effect(status: str) -> str:
    """The one effect word of one projected item/entry status."""

    return PROJECTION_EFFECT.get(status, "in_progress")


def projection_item_outcomes(
    item,
    payload: dict[str, object] | None,
    record,
    outcome_status: str,
) -> tuple[list[dict[str, object]], bool]:
    """The durable per-entry outcomes of one direct-file item.

    A started item's recorded per-entry progress is the source of truth while
    it stays unfinished; a finished item's Result annotations (completed
    executor checkpoints plus the retained skipped-child evidence) reproduce
    the same per-entry truth after the progress marker was consumed.
    """

    outcomes: list[dict[str, object]] = []
    if payload is not None and item.status in _UNFINISHED_ITEM_STATUSES:
        for entry in payload.get("entries") or ():
            if not isinstance(entry, dict):
                continue
            outcome: dict[str, object] = {
                "path": str(entry.get("path", "")),
                "destination": str(entry.get("destination", "")),
                "status": str(entry.get("status", "")),
                "checkpoints": [],
            }
            if entry.get("errorCategory"):
                outcome["errorCategory"] = str(entry.get("errorCategory"))
            outcomes.append(outcome)
        return outcomes, bool(payload.get("truncated"))
    if record is None:
        return outcomes, False
    destination = item.destination_path or ""
    if not record.completed_operations:
        # A refused/failed item records no executor checkpoint: its single
        # truthful outcome is the item's own durable failure evidence.
        outcomes.append(
            {
                "path": item.source_display,
                "destination": destination,
                "status": outcome_status,
                "checkpoints": [],
                **({"errorCategory": record.error} if record.error else {}),
            }
        )
        return outcomes, False
    # The Result annotations group into one outcome per entry path, keeping
    # each compound checkpoint order (copy_written, destination_verified,
    # source_deleted), the exact per-entry status and the skipped-child
    # evidence beside the entry it belongs to.
    grouped: dict[str, dict[str, object]] = {}

    def entry_for(path: str) -> dict[str, object]:
        return grouped.setdefault(
            path,
            {
                "path": path,
                "destination": destination,
                "status": outcome_status,
                "checkpoints": [],
            },
        )

    for annotation in record.completed_operations:
        name, separator, rest = str(annotation).partition(":")
        if not separator or not rest:
            entry_for(item.source_display)["checkpoints"].append(name)
            continue
        if name == "entry":
            status, _, path = rest.partition(":")
            if path:
                entry_for(path)["status"] = status or outcome_status
            continue
        if name == "entry_error":
            category, _, path = rest.partition(":")
            if path:
                entry_for(path)["errorCategory"] = category
            continue
        if name == "skip_conflict":
            entry = entry_for(rest)
            entry["status"] = "SKIPPED"
            entry["errorCategory"] = "target_exists"
            continue
        entry_for(rest)["checkpoints"].append(name)
    outcomes.extend(grouped.values())
    return outcomes, False


def item_known_mutation(item, record) -> tuple[bool, bool]:
    """Whether one item already recorded a known mutation, and its certainty.

    The durable per-entry progress of a started item is the authoritative
    known-effect evidence after an unexpected failure: an entry marked
    ``UNCERTAIN`` (or an item already carrying the uncertain marker) means the
    effect cannot be proven and must be investigation-only; any other recorded
    non-skipped entry means a mutation may already have happened.
    """

    if getattr(item, "error", None) == "mutation_outcome":
        return True, True
    if record is not None:
        certainty = getattr(record, "effect_certainty", None)
        if certainty == ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value:
            return True, True
        if certainty == ExecutionEffectCertainty.VERIFIED_COMPLETE.value:
            return True, False
    payload = progress_payload(item)
    if payload is None:
        return False, False
    statuses = {
        str(value.get("status", ""))
        for value in payload.get("entries") or ()
        if isinstance(value, dict)
    }
    if "UNCERTAIN" in statuses:
        return True, True
    completed = payload.get("completedEntries")
    if statuses & {"SUCCESS", "PARTIAL"} or (isinstance(completed, int) and completed > 0):
        return True, False
    return False, False


def effect_certainty_of(record) -> str:
    """The closed certainty name of one durable Result, or ``unknown``."""

    certainty = getattr(record, "effect_certainty", None) if record is not None else None
    if certainty == ExecutionEffectCertainty.VERIFIED_COMPLETE.value:
        return "verified_complete"
    if certainty == ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value:
        return "uncertain"
    if certainty == ExecutionEffectCertainty.NONE.value:
        return "none"
    return "unknown"


def item_effect_signal(item, record) -> dict[str, object]:
    """One item's projected status, net effect and effect certainty.

    An unfinished item that already recorded a verified child mutation is
    ``partial``: some of its work is provably done and the rest is not, which is
    neither "no change" nor a finished success.  An unfinished item with no
    recorded evidence stays ``unknown`` — never ``none``.
    """

    status = projection_item_status(item, record)
    known_mutation, uncertain = item_known_mutation(item, record)
    certainty = effect_certainty_of(record)
    if certainty == "uncertain":
        uncertain = True
        # A refused/partial mutation whose net effect could not be verified is
        # *uncertain*, never a settled failure: the Delete/transfer projections
        # say the same thing, and the operator must not read it as
        # "nothing happened".
        if status in {"FAILED", "PARTIAL"}:
            status = "UNCERTAIN"
    if item.status in _UNFINISHED_ITEM_STATUSES and certainty in {"unknown", "none"}:
        certainty = "partial" if known_mutation else "unknown"
    # An unfinished item that already recorded a real mutation reports that
    # partial effect: its remaining work is still in progress, but the operator
    # must not read the whole item as untouched.
    effect = "partial" if certainty == "partial" else projection_effect(status)
    return {
        "status": status,
        "effect": effect,
        "effectCertainty": certainty,
        "knownMutation": known_mutation,
        "uncertain": uncertain,
        "settled": item.status in _SETTLED_ITEM_STATUSES,
    }


class EffectCertaintyFold:
    """The streaming fold of one whole operation's item effect signals.

    An operation-level fact (its recorded effect, its durable state and its safe
    next action) describes *every* admitted item, not the page of items that
    happens to be delivered to the operator.  This fold therefore accepts the
    signals one item at a time, so a caller can read a large operation in bounded
    batches and still publish one page-independent truth; loading more items can
    never change what the operation is said to have done.

    Precedence is intentional and identical to ``aggregate_effect_certainty``.
    """

    __slots__ = (
        "count",
        "_any_failed",
        "_any_known_mutation",
        "_any_uncertain",
        "_every_settled_none",
        "_every_verified",
    )

    def __init__(self) -> None:
        self.count = 0
        self._any_uncertain = False
        self._every_verified = True
        self._any_known_mutation = False
        self._every_settled_none = True
        self._any_failed = False

    def add(self, signal) -> None:
        self.count += 1
        certainty = signal["effectCertainty"]
        if signal["uncertain"] or certainty == "uncertain":
            self._any_uncertain = True
        if certainty != "verified_complete":
            self._every_verified = False
        if signal["knownMutation"]:
            self._any_known_mutation = True
        if not (signal["settled"] and certainty == "none"):
            self._every_settled_none = False
        if signal["status"] in {"FAILED", "PARTIAL", "UNCERTAIN"}:
            self._any_failed = True

    @property
    def any_uncertain(self) -> bool:
        """Whether any admitted item's effect cannot be proven."""

        return self._any_uncertain

    @property
    def any_failed(self) -> bool:
        """Whether any admitted item settled failed/partial/uncertain."""

        return self._any_failed

    @property
    def certainty(self) -> str:
        """The truthful aggregate certainty of every folded item."""

        if self.count == 0:
            return "unknown"
        if self._any_uncertain:
            return "uncertain"
        if self._every_verified:
            return "verified_complete"
        if self._any_known_mutation:
            return "partial"
        if self._every_settled_none:
            return "none"
        return "unknown"


def aggregate_effect_certainty(signals) -> str:
    """The truthful aggregate certainty of one operation's item signals.

    Precedence is intentional.  Any unprovable effect dominates.  A mix of
    provable changes and anything else is ``partial`` — a known successful
    sibling must never be averaged away by a refused one.  ``none`` means the
    durable evidence proves that no item changed anything (every item settled
    with a recorded "no effect"), and ``unknown`` is reserved for admitted work
    that records no provable effect yet.  In particular an unfinished item
    without recorded checkpoints is ``unknown``, never ``none``.

    This is the list form of :class:`EffectCertaintyFold`; both must stay in one
    place so a paged read and a whole-operation read cannot disagree.
    """

    fold = EffectCertaintyFold()
    for entry in signals:
        fold.add(entry)
    return fold.certainty
