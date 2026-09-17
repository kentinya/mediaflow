"""Resident Processing-Worker pickup for admitted Files Copy/Move transfers.

The Web/API boundary only *admits* a confirmed bounded transfer: it persists
the queued Task, the bounded per-item transfer authority and the claimable
transfer row in one atomic admission, and returns the durable operator
projection before the first Storage mutation.  This module is the only place
that turns an admitted transfer into ``OrganizerExecutor`` work, and it does
so under the same resident Worker ownership model as the admitted manual
Organize executions:

* only a non-terminal transfer whose previous lease (if any) expired can be
  claimed, so a transfer that may have crossed the mutation boundary is never
  handed to two live Workers;
* the running boundary is published by a guarded, claim-token-bound update
  immediately before the first OrganizerExecutor call;
* a Worker that fails to start a claimed transfer records one truthful
  durable failure instead of leaving it silently claimable forever, and
  never replays a mutation that may already have happened.
"""

from __future__ import annotations

import secrets
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from mediaflow.domain.task_persistence import FilesTransferStatus

DEFAULT_TRANSFER_LEASE_SECONDS = 300.0
_TRANSFER_TERMINAL_STATUSES = frozenset(status for status in FilesTransferStatus if status.terminal)


class FilesTransferWorker:
    """Claim and run admitted bounded Files transfers for one Worker."""

    def __init__(
        self,
        transfer_service,
        repository,
        *,
        lease_seconds: float = DEFAULT_TRANSFER_LEASE_SECONDS,
        clock: Callable[[], datetime] | None = None,
        worker_id: str | None = None,
        notice: Callable[[str], None] | None = None,
    ) -> None:
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int | float)
            or not 0 < float(lease_seconds) <= 86_400
        ):
            raise ValueError("files transfer worker lease must be between 1 second and 1 day")
        self._service = transfer_service
        self._repository = repository
        self._lease_seconds = float(lease_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._worker_id = worker_id or f"files-transfer-{secrets.token_hex(6)}"
        self._notice = notice or (lambda line: sys.stderr.write(line))

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def lease_seconds(self) -> float:
        return self._lease_seconds

    def run_next(self) -> object | None:
        """Claim and run at most one admitted transfer.

        Returns the durable transfer after the run, or ``None`` when there is
        no claimable work.  A claimed transfer that cannot be started is
        closed with one recorded pre-mutation failure; it is never silently
        returned to the claimable queue.
        """

        claim_token = secrets.token_urlsafe(32)
        claimed = self._repository.claim_next_files_transfer(
            self._clock(),
            worker_id=self._worker_id,
            claim_token=claim_token,
            lease_seconds=self._lease_seconds,
        )
        if claimed is None:
            return None
        try:
            return self._service.run_claimed_transfer(
                claimed,
                claim_token=claim_token,
                heartbeat=lambda: self._heartbeat(claimed.transfer_id, claim_token),
                lease_seconds=self._lease_seconds,
            )
        except Exception as error:
            self._notice(self._bounded_notice(claimed.transfer_id, error))
            self._close_unstarted(claimed.transfer_id, claim_token, error)
            return None

    def _heartbeat(self, transfer_id: str, claim_token: str) -> bool:
        return bool(
            self._repository.heartbeat_files_transfer_claim(
                transfer_id, claim_token, self._clock(), self._lease_seconds
            )
        )

    def _close_unstarted(self, transfer_id: str, claim_token: str, error: BaseException) -> None:
        """Make sure a claimed transfer that never started is not claimable forever.

        The claim owner closes its own lease with a truthful bounded failure.
        A replacement Worker may later take over an expired claim, but that
        continuation proceeds only from the persisted known-safe checkpoints —
        never by replaying a completed or uncertain mutation.
        """

        closer = getattr(self._repository, "finish_files_transfer", None)
        if not callable(closer):
            return
        try:
            current = self._repository.get_files_transfer(transfer_id)
        except Exception:
            return
        if current is None or current.status in _TRANSFER_TERMINAL_STATUSES:
            return
        from dataclasses import replace

        terminal = replace(
            current,
            status=FilesTransferStatus.FAILED,
            error=f"files_transfer_worker_failed_{type(error).__name__}",
            next_action=(
                "inspect the recorded per-item outcomes and submit a fresh transfer "
                "for the remaining entries"
            ),
            completed_at=self._clock(),
        )
        try:
            closer(terminal, claim_token=claim_token, now=self._clock())
        except Exception:
            return

    def _bounded_notice(self, transfer_id: str, error: BaseException) -> str:
        code = getattr(error, "code", None)
        if not isinstance(code, str) or not code.strip():
            code = "files_transfer_unavailable"
        bounded = "".join(
            character for character in code if character.isalnum() or character in "_-"
        )
        return (
            f"files transfer {transfer_id} could not be started by this Worker "
            f"({bounded[:48]}); its durable state is preserved\n"
        )
