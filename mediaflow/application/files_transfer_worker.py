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

One Worker may serve both library kinds (Slice 38 RO-6/RO-7).  Each admitted
transfer is claimed through the same durable queue, and the claimed Task's own
command selects the kind-pinned service that executes and resolves it: a media
transfer is never executed by the ResourceLibrary boundary (or the reverse),
even when the two libraries carry the same configured ID.
"""

from __future__ import annotations

import secrets
import sys
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from mediaflow.domain.task_persistence import (
    FILES_TRANSFER_TASK_COMMAND,
    FilesTransferStatus,
    direct_command_task_command,
)

DEFAULT_TRANSFER_LEASE_SECONDS = 300.0
_TRANSFER_TERMINAL_STATUSES = frozenset(status for status in FilesTransferStatus if status.terminal)


def _default_services(transfer_service) -> dict[str, object]:
    """The command→service map of one Worker's transfer boundaries.

    A caller that passes a single service (the pre-existing ResourceLibrary-only
    construction) keeps exactly that behavior, while a Worker composed with a
    media-kind twin serves both kinds and always dispatches by the claimed
    Task's own durable command.
    """

    if transfer_service is None:
        return {}
    mapping: dict[str, object] = {}
    if isinstance(transfer_service, dict):
        for command, service in transfer_service.items():
            if isinstance(command, str) and service is not None:
                mapping[command] = service
        return mapping
    command = getattr(transfer_service, "task_command", None)
    if not isinstance(command, str) or not command:
        command = FILES_TRANSFER_TASK_COMMAND
    mapping[command] = transfer_service
    return mapping


def transfer_services(
    resource_transfers=None, media_transfers=None, *, fallback=None
) -> dict[str, object]:
    """The command→service dispatch map for one resident Worker.

    Both kind-pinned boundaries share one durable claim queue, so the Worker
    needs one entry per kind: the claimed Task's command decides which service
    may lawfully execute it.
    """

    services: dict[str, object] = {}
    if resource_transfers is not None:
        services[FILES_TRANSFER_TASK_COMMAND] = resource_transfers
    if media_transfers is not None:
        services[direct_command_task_command(FILES_TRANSFER_TASK_COMMAND, media_library=True)] = (
            media_transfers
        )
    if not services and fallback is not None:
        services = _default_services(fallback)
    return services


class FilesTransferWorker:
    """Claim and run admitted bounded Files transfers for one Worker."""

    def __init__(
        self,
        transfer_service=None,
        repository=None,
        *,
        media_transfer_service=None,
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
        services = _default_services(transfer_service)
        if media_transfer_service is not None:
            services[
                direct_command_task_command(FILES_TRANSFER_TASK_COMMAND, media_library=True)
            ] = media_transfer_service
        self._services = services
        #: The pre-existing single-service attribute, retained so a Worker that
        #: serves exactly one kind keeps its historical behavior and any caller
        #: inspecting it sees the boundary it was built with.
        self._service = next(iter(services.values()), None)
        self._repository = repository
        self._lease_seconds = float(lease_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._worker_id = worker_id or f"files-transfer-{secrets.token_hex(6)}"
        self._notice = notice or (lambda line: sys.stderr.write(line))

    def service_for(self, command: str | None):
        """The one kind-pinned service that may execute a claimed Task command."""

        if not isinstance(command, str) or not command:
            return None
        return self._services.get(command)

    @property
    def commands(self) -> tuple[str, ...]:
        """The durable Task commands this Worker can lawfully execute."""

        return tuple(sorted(self._services))

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
        service = self._service_for_transfer(claimed)
        keeper = self._start_lease_keeper(claimed.transfer_id, claim_token)
        try:
            if service is None:
                # No configured boundary of this Worker may lawfully execute the
                # claimed transfer's kind.  It is returned to the claimable queue
                # with bounded readiness evidence instead of being consumed as a
                # business failure: an eligible Worker continues it later.
                self._release_incompatible(claimed.transfer_id, claim_token)
                return None
            return service.run_claimed_transfer(
                claimed,
                claim_token=claim_token,
                heartbeat=lambda: self._heartbeat(claimed.transfer_id, claim_token),
                lease_seconds=self._lease_seconds,
            )
        except Exception as error:
            self._notice(self._bounded_notice(claimed.transfer_id, error))
            self._close_unstarted(claimed.transfer_id, claim_token, error, service=service)
            return None
        finally:
            keeper.stop()

    def _service_for_transfer(self, transfer):
        """The one kind-pinned service that may execute a claimed transfer.

        The durable Task command is the authority: it records which kind of
        configured library owns the work, so a claimed media transfer reaches
        only the media boundary and a claimed resource transfer only the
        resource one — never whichever service happens to be built first.
        """

        task = None
        task_id = getattr(transfer, "task_id", None)
        reader = getattr(self._repository, "get_task", None)
        if isinstance(task_id, str) and callable(reader):
            task = reader(task_id)
        if task is None:
            # A transfer whose Task row cannot be read has no lawful execution
            # boundary here: fall back to the single configured service only
            # when this Worker serves exactly one kind, otherwise fail closed.
            return self._service if len(self._services) == 1 else None
        return self.service_for(getattr(task, "command", None))

    def _release_incompatible(self, transfer_id: str, claim_token: str) -> None:
        """Return one claimed transfer this Worker cannot execute to the queue."""

        requeue = getattr(self._repository, "release_files_transfer_claim", None)
        if not callable(requeue):
            return
        try:
            requeue(
                transfer_id,
                claim_token=claim_token,
                now=self._clock(),
                error="files_transfer_worker_kind_unavailable",
                next_action=(
                    "wait for a Worker configured with this transfer's library kind, "
                    "or inspect the Active configuration"
                ),
            )
        except Exception:
            return

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

    def _close_unstarted(
        self,
        transfer_id: str,
        claim_token: str,
        error: BaseException,
        *,
        service=None,
    ) -> None:
        """Make sure a claimed transfer that never started is not claimable forever.

        The claim owner closes its own lease with a truthful bounded failure,
        converging the transfer row, the Task, every unfinished item and the
        bounded Result evidence together, so a failed start never leaves a
        permanently running projection.  A replacement Worker may later take
        over an expired claim, but that continuation proceeds only from the
        persisted known-safe checkpoints — never by replaying a completed or
        uncertain mutation.

        The convergence runs through the exact kind-pinned service that was
        about to execute the transfer, so a failed start of media work is
        converged by its own boundary rather than the other kind's.
        """

        boundary = service if service is not None else self._service
        converge = getattr(boundary, "converge_worker_failure", None)
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
