"""Resident Processing-Worker pickup for admitted bounded media discoveries.

The API only *admits* a discovery: it validates the exact submitted scope,
resolves the pinned immutable Active revision and returns one durable record
promptly.  This module is the only place that turns an admitted discovery into
Storage observations, and it does so under the existing resident Worker loop.

Safety: discovery is metadata-only and zero mutation, so a claim that expires
can safely be resumed by another Worker without any risk of a media effect.  The
claim is still exclusive so two Workers can never append duplicate findings or
sources for one record.
"""

from __future__ import annotations

import secrets
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from mediaflow.domain.media_discovery import (
    TERMINAL_DISCOVERY_STATUSES,
    DiscoveryError,
    DiscoveryUnavailable,
    MediaDiscovery,
)

DEFAULT_LEASE_SECONDS = 300.0


class MediaDiscoveryWorker:
    """Claim and advance admitted bounded discoveries for one Worker."""

    def __init__(
        self,
        discovery_service,
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
            raise ValueError("media discovery worker lease must be between 1 second and 1 day")
        self._service = discovery_service
        self._lease_seconds = float(lease_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._worker_id = worker_id or f"media-discovery-{secrets.token_hex(6)}"
        self._notice = notice or (lambda line: sys.stderr.write(line))
        # The containing processing-Worker's registration heartbeat, bound by
        # the resident assembly so a long walk keeps the actual hosting
        # process's liveness evidence fresh.  It is a liveness signal only.
        self._parent_heartbeat: Callable[[], bool] | None = None

    def set_worker_heartbeat(self, heartbeat: Callable[[], bool]) -> None:
        """Bind the containing processing-Worker's registration heartbeat.

        Mirrors the Files transfer runner's seam: the resident assembly wires
        its own wrapped heartbeat (registration row plus resident-presence
        row) so a long blocked Storage call cannot make the deployment look
        stale while it is actually working.
        """

        if not callable(heartbeat):
            raise ValueError("media discovery worker heartbeat must be callable")
        self._parent_heartbeat = heartbeat

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def lease_seconds(self) -> float:
        return self._lease_seconds

    @property
    def commands(self) -> tuple[str, ...]:
        """The command family this runner serves, for Worker registration.

        It is advertised alongside the existing ``manual_organize`` family so a
        live Worker's registration truthfully states that it serves the bounded
        discovery boundary too.
        """

        return ("media_discovery",)

    def run_next(self) -> MediaDiscovery | None:
        """Claim and advance at most one admitted discovery.

        Returns the durable discovery after the step, or ``None`` when there is
        no claimable work.  A failure to advance records one truthful bounded
        state instead of leaving the record silently claimable forever.
        """

        repository = getattr(self._service, "repository", None)
        if repository is None:
            raise DiscoveryUnavailable("media discovery repository is unavailable")
        claim_token = secrets.token_urlsafe(32)
        try:
            return self._service.claim_and_run(
                worker_id=self._worker_id,
                claim_token=claim_token,
                heartbeat=self._heartbeat(claim_token),
                parent_heartbeat=self._parent_heartbeat,
            )
        except DiscoveryError as error:
            self._notice(self._bounded_notice(getattr(error, "code", None)))
            return None
        except Exception as error:  # noqa: BLE001 - a Worker must never crash the loop
            self._notice(self._bounded_notice(type(error).__name__))
            return None

    def _heartbeat(self, claim_token: str) -> Callable[[str], bool]:
        def beat(discovery_id: str) -> bool:
            heartbeat = getattr(self._service.repository, "heartbeat_media_discovery_claim", None)
            if not callable(heartbeat):
                return True
            return bool(heartbeat(discovery_id, claim_token, self._clock(), self._lease_seconds))

        return beat

    def _bounded_notice(self, code: object) -> str:
        if not isinstance(code, str) or not code.strip():
            code = "media_discovery_unavailable"
        bounded = "".join(
            character for character in code if character.isalnum() or character in "_-"
        )
        return (
            f"media discovery could not be advanced by this Worker ({bounded[:48]}); "
            "its durable state is preserved\n"
        )


def terminal(discovery: MediaDiscovery | None) -> bool:
    return discovery is not None and discovery.status in TERMINAL_DISCOVERY_STATUSES
