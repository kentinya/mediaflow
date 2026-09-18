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
import threading
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

        A lease-keeper keeps the claim live for the whole invocation — including
        while a provider call is blocked — so one long SMB/OpenList/S3 mutation
        can never outlive its only ownership signal and be taken over in
        parallel.  A takeover therefore becomes possible only after this
        process genuinely stopped (or this invocation ended), which is exactly
        when a replacement Worker may safely continue from the persisted
        checkpoints.
        """

        claim_token = secrets.token_urlsafe(32)
        claimed = self._repository.claim_next_files_transfer(
            self._clock(),
            worker_id=self._worker_id,
            claim_token=claim_token,
            lease_seconds=self._lease_seconds,
        )
        if claimed is None:
            # No ordinary work is claimable.  One transfer may still hold an
            # expired in-flight mutation: the ordinary query deliberately never
            # hands that over, so it is reached only through this explicit
            # resolution claim, which converges the recorded boundary without
            # ever invoking the interrupted operation again.
            claimed = self._claim_expired_mutation(claim_token)
            if claimed is None:
                return None
        keeper = self._start_lease_keeper(claimed.transfer_id, claim_token)
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
        finally:
            keeper.stop()

    def _claim_expired_mutation(self, claim_token: str):
        claim = getattr(self._repository, "claim_expired_files_transfer_mutation", None)
        if not callable(claim):
            return None
        return claim(
            self._clock(),
            worker_id=self._worker_id,
            claim_token=claim_token,
            lease_seconds=self._lease_seconds,
        )

    def _start_lease_keeper(self, transfer_id: str, claim_token: str):
        """Keep one claim's lease live for the whole invocation.

        The keeper heartbeats at a fraction of the lease interval in its own
        thread, so a blocked or slow provider mutation cannot let the lease
        expire while this Worker still owns it.  A transient heartbeat fault —
        a ``False`` CAS result, a SQLite error or any other exception — is
        retried (bounded) instead of silently killing the keeper, and every
        fault is reported through the Worker's bounded notice.  Liveness support
        is nevertheless not the data-integrity fence: the durable
        ``mutation_in_flight`` boundary keeps an entered operation
        non-replayable even if the keeper can no longer renew the lease.
        """

        interval = max(0.05, self._lease_seconds / 3.0)
        heartbeat = self._heartbeat
        notice = self._notice

        class _LeaseKeeper:
            def __init__(self) -> None:
                self._stop = threading.Event()
                self.faults = 0
                self._thread = threading.Thread(target=self._run, daemon=True)

            def _run(self) -> None:
                consecutive_faults = 0
                while not self._stop.wait(interval):
                    try:
                        renewed = heartbeat(transfer_id, claim_token)
                    except Exception:
                        renewed = False
                    if renewed:
                        consecutive_faults = 0
                        continue
                    consecutive_faults += 1
                    self.faults = consecutive_faults
                    if consecutive_faults == 1:
                        notice(
                            f"files transfer {transfer_id} lease heartbeat faulted; "
                            "retrying while the claim token still owns the row\n"
                        )
                    if consecutive_faults >= self._maximum_faults:
                        # A persistent ownership-signal failure ends the liveness
                        # support only; the in-flight boundary it may have left
                        # behind is resolved without replay by the next Worker.
                        notice(
                            f"files transfer {transfer_id} lease heartbeat keeps failing; "
                            "the in-flight boundary stays non-replayable\n"
                        )
                        return

            _maximum_faults = 8

            def start(self):
                self._thread.start()
                return self

            def stop(self) -> None:
                self._stop.set()
                self._thread.join(timeout=interval + 1.0)

        return _LeaseKeeper().start()

    def _heartbeat(self, transfer_id: str, claim_token: str) -> bool:
        return bool(
            self._repository.heartbeat_files_transfer_claim(
                transfer_id, claim_token, self._clock(), self._lease_seconds
            )
        )

    def _close_unstarted(self, transfer_id: str, claim_token: str, error: BaseException) -> None:
        """Make sure a claimed transfer that never started is not claimable forever.

        The claim owner closes its own lease with a truthful bounded failure,
        converging the transfer row, the Task, every unfinished item and the
        bounded Result evidence together, so a failed start never leaves a
        permanently running projection.  A replacement Worker may later take
        over an expired claim, but that continuation proceeds only from the
        persisted known-safe checkpoints — never by replaying a completed or
        uncertain mutation.
        """

        converge = getattr(self._service, "converge_worker_failure", None)
        if callable(converge):
            try:
                # A truthful convergence (or an already-terminal row) is the
                # whole outcome; only a convergence that could not run at all
                # falls through to the narrow terminal-publish fallback.
                if converge(transfer_id, claim_token, error):
                    return
            except Exception:
                pass
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
