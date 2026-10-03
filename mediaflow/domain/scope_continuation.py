"""Durable queued continuation of one safely paused Task's remaining scope.

A scope continuation turns one durably paused, supported asynchronous operator
workflow into bounded queued work: the operator's Web Continue request only
*admits* the continuation (a queued Job plus one explicit continuation row) and
returns promptly.  The resident Worker later claims that Job under the existing
claim/lease/schema fences, rebuilds the original Task's immutable configuration
pin and continues **only** the exact remaining admitted scope.

Three properties are structural rather than conventional:

* the continuation never re-executes a terminal outcome — a successful,
  dry-run, skipped, ignored, waiting or uncertain-effect item is excluded by
  construction, so no completed effect and no unknown mutation is ever replayed;
* the continuation never invents scope — the original Task's command,
  ``scope_path``, ``item_limit`` and configuration pin are copied verbatim, and
  the remaining item budget is the original limit minus the already-recorded
  items;
* a persisted ``execute_authorized`` boolean is never authority.  A continuation
  that would mutate media requires a *live* durable mutation authority that is
  revalidated at admission and again at every mutation boundary; when that
  authority cannot be proven the continuation is refused with the native exact
  Preview/explicit-intent next action instead of silently downgrading or
  replaying the original admission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.automation import AutomationJob

#: The durable Task commands whose remaining admitted scope can be continued
#: through the existing processing pipeline by the resident Worker.  The manual
#: Scan service observes no pause request at all, the synchronous Web manual
#: Organize and the in-request Files commands/Delete are not Worker-owned
#: asynchronous work, and the analysis/recovery continuation families have no
#: remaining-scope contract of their own.  Those paths keep their Pause
#: capability and explain their real reason instead.
CONTINUABLE_TASK_COMMANDS = frozenset({"scan", "preview", "organize"})

#: The single supported continuation boundary.  It names the exact durable
#: evidence the Worker revalidates before any adapter is constructed.
CONTINUATION_BOUNDARY = "paused_remaining_admitted_scope"


class ScopeContinuationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def active(self) -> bool:
        return self in {self.QUEUED, self.RUNNING}


class ScopeContinuationReason(StrEnum):
    """The closed set of bounded, operator-facing continuation refusals."""

    TASK_NOT_FOUND = "task_not_found"
    TASK_NOT_PAUSED = "task_not_paused"
    STALE_TASK_STATE = "stale_task_state"
    COMMAND_NOT_CONTINUABLE = "command_not_continuable"
    SNAPSHOT_UNAVAILABLE = "snapshot_unavailable"
    AUTHORITY_REQUIRED = "authority_required"
    CONTINUATION_EXISTS = "continuation_exists"
    QUEUE_FULL = "queue_full"
    INVALID_INPUT = "invalid_input"
    INSUFFICIENT_PERMISSION = "insufficient_permission"


class ScopeContinuationError(ValueError):
    """A bounded, secret-free refusal from the continuation submission.

    ``next_action`` is the operator-facing recovery step.  It never contains a
    token, a raw identifier the operator would have to paste, or an absolute
    host path.
    """

    def __init__(
        self,
        reason: ScopeContinuationReason,
        message: str,
        *,
        durable_state: str = "the Task keeps its paused state and its recorded item outcomes",
        next_action: str,
        retry_safe: bool = False,
        current_version: str | None = None,
        existing_continuation: ScopeContinuation | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = ScopeContinuationReason(reason)
        self.durable_state = durable_state
        self.next_action = next_action
        self.retry_safe = retry_safe
        self.current_version = current_version
        self.existing_continuation = existing_continuation

    def document(self) -> dict[str, object]:
        return {
            "reason": self.reason.value,
            "durableState": self.durable_state,
            "sideEffects": "none",
            "retrySafe": self.retry_safe,
            "nextAction": self.next_action,
            **({"currentVersion": self.current_version} if self.current_version else {}),
        }


@dataclass(frozen=True)
class ScopeContinuation:
    """One durable, Worker-executed continuation of a paused Task's scope."""

    continuation_id: str
    source_task_id: str
    command: str
    scope_path: str | None
    item_limit: int | None
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    boundary: str
    status: ScopeContinuationStatus
    created_at: datetime
    updated_at: datetime
    actor: str
    job_id: str
    new_task_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    recovery: str | None = None
    authority_statement: str = (
        "bounded remaining-scope continuation: no scope expansion; no replay of a "
        "terminal, ignored or uncertain effect; no repin; no mutation without a live "
        "durable authority revalidated at admission and at every mutation boundary"
    )

    @property
    def active(self) -> bool:
        return self.status.active

    def next_action(self) -> str:
        """One concrete, secret-free next step for the operator."""

        if self.status is ScopeContinuationStatus.COMPLETED:
            return "inspect the linked continuation run and its independent per-item results"
        if self.status is ScopeContinuationStatus.FAILED:
            return (
                self.recovery
                or "inspect the linked continuation run, repair the stated condition, then "
                "continue the remaining scope again"
            )
        if self.status is ScopeContinuationStatus.CANCELLED:
            return (
                "refresh the Task; the original paused scope is unchanged and can be "
                "continued again"
            )
        return (
            "the resident Worker will claim this continuation; follow the linked continuation run"
        )

    def document(self) -> dict[str, object]:
        """Return a bounded transport-safe representation."""

        return {
            "continuation_id": self.continuation_id,
            "source_task_id": self.source_task_id,
            "command": self.command,
            "scope_path": self.scope_path,
            "item_limit": self.item_limit,
            "configuration_snapshot_id": self.configuration_snapshot_id,
            "configuration_snapshot_digest": self.configuration_snapshot_digest,
            "boundary": self.boundary,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "actor": self.actor,
            "job_id": self.job_id,
            "new_task_id": self.new_task_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "recovery": self.recovery,
            "next_action": self.next_action(),
            "authority_statement": self.authority_statement,
        }


class ScopeContinuationRepository(Protocol):
    def get_scope_continuation_for_job(self, job_id: str) -> ScopeContinuation | None: ...
    def get_scope_continuation_for_source_task(self, task_id: str) -> ScopeContinuation | None: ...
    def list_scope_continuations(
        self, task_id: str, *, limit: int = 32
    ) -> tuple[ScopeContinuation, ...]: ...
    def admit_scope_continuation(
        self,
        job: AutomationJob,
        continuation: ScopeContinuation,
        *,
        maximum_active_jobs: int,
    ) -> tuple[ScopeContinuation, bool]: ...
    def mark_scope_continuation_running(self, job_id: str) -> ScopeContinuation: ...
    def bind_scope_continuation_task(self, job_id: str, task_id: str) -> ScopeContinuation: ...
    def complete_scope_continuation(
        self,
        job_id: str,
        *,
        new_task_id: str | None = None,
        success: bool,
        error: str | None = None,
        recovery: str | None = None,
    ) -> ScopeContinuation: ...
    def fail_queued_scope_continuation(
        self, job_id: str, *, error: str, recovery: str | None = None
    ) -> ScopeContinuation: ...
    def cancel_scope_continuation(self, job_id: str) -> ScopeContinuation: ...


__all__ = [
    "CONTINUABLE_TASK_COMMANDS",
    "CONTINUATION_BOUNDARY",
    "ScopeContinuation",
    "ScopeContinuationError",
    "ScopeContinuationReason",
    "ScopeContinuationRepository",
    "ScopeContinuationStatus",
]
