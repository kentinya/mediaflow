"""Resident Processing-Worker pickup for admitted exact manual executions.

The Web/API boundary only *admits* a reviewed manual Organize execution: it
consumes the server-held one-shot authority, commits the durable execution,
Task scope and Storage fences, and returns promptly.  This module is the only
place that turns an admitted execution into ``OrganizerExecutor`` work, and it
does so under the existing resident Worker loop.

Lease semantics are deliberately conservative:

* only an ``admitted`` execution can be claimed, so an execution that may have
  crossed the mutation boundary is never handed to a second Worker;
* the running boundary is published by a guarded, claim-token-bound update
  immediately before ``OrganizerExecutor`` is invoked;
* a Worker that fails to start an execution records one truthful pre-mutation
  failure instead of leaving it silently claimable forever, and never replays
  a mutation that may already have happened.
"""

from __future__ import annotations

import secrets
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from mediaflow.domain.manual_execution import (
    ManualExecution,
    ManualExecutionError,
    ManualExecutionStatus,
)

DEFAULT_LEASE_SECONDS = 300.0
_TERMINAL_EXECUTION_STATUSES = frozenset(
    {
        ManualExecutionStatus.COMPLETED,
        ManualExecutionStatus.PARTIAL_SUCCESS,
        ManualExecutionStatus.FAILED,
        ManualExecutionStatus.CANCELLED,
    }
)


class ManualOrganizeExecutionWorker:
    """Claim and run admitted manual Organize executions for one Worker."""

    def __init__(
        self,
        execution_service,
        *,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        clock: Callable[[], datetime] | None = None,
        worker_id: str | None = None,
        notice: Callable[[str], None] | None = None,
    ) -> None:
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int | float)
            or not 0 < float(lease_seconds) <= 86_400
        ):
            raise ValueError("manual organize worker lease must be between 1 second and 1 day")
        self._service = execution_service
        self._lease_seconds = float(lease_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._worker_id = worker_id or f"manual-organize-{secrets.token_hex(6)}"
        self._notice = notice or (lambda line: sys.stderr.write(line))

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def lease_seconds(self) -> float:
        return self._lease_seconds

    def run_next(self) -> ManualExecution | None:
        """Claim and run at most one admitted execution.

        Returns the durable execution after the run, or ``None`` when there is
        no admitted work to claim.  A claim that cannot be started is closed
        with one recorded pre-mutation failure; it is never silently returned
        to the claimable queue.
        """

        repository = getattr(self._service, "repository", None)
        if repository is None:
            raise ManualExecutionError(
                "manual organize execution repository is unavailable",
                code="execution_unavailable",
                status=503,
            )
        claim_token = secrets.token_urlsafe(32)
        claimed = repository.claim_next_manual_execution(
            self._clock(),
            worker_id=self._worker_id,
            claim_token=claim_token,
            lease_seconds=self._lease_seconds,
        )
        if claimed is None:
            return None
        try:
            return self._service.run_admitted(
                claimed.execution_id,
                worker_id=self._worker_id,
                claim_token=claim_token,
                heartbeat=lambda: self._heartbeat(claimed.execution_id, claim_token),
                lease_seconds=self._lease_seconds,
            )
        except Exception as error:
            self._notice(self._bounded_notice(claimed.execution_id, error))
            self._close_unstarted(claimed.execution_id, error)
            return None

    def _heartbeat(self, execution_id: str, claim_token: str) -> bool:
        return bool(
            self._service.repository.heartbeat_manual_execution_claim(
                execution_id, claim_token, self._clock(), self._lease_seconds
            )
        )

    def _close_unstarted(self, execution_id: str, error: BaseException) -> None:
        """Make sure a claimed execution that never started is not silently claimable."""

        closer = getattr(self._service, "fail_unstarted_execution", None)
        if not callable(closer):
            return
        try:
            current = self._service.get(execution_id)
        except Exception:
            return
        if current.status in _TERMINAL_EXECUTION_STATUSES:
            return
        try:
            closer(execution_id, error)
        except Exception:
            return

    def _bounded_notice(self, execution_id: str, error: BaseException) -> str:
        code = getattr(error, "code", None)
        if not isinstance(code, str) or not code.strip():
            code = "manual_execution_unavailable"
        bounded = "".join(
            character for character in code if character.isalnum() or character in "_-"
        )
        return (
            f"manual organize execution {execution_id} could not be started by this Worker "
            f"({bounded[:48]}); its durable state is preserved\n"
        )
