"""Resident-service composition shared by the CLI entry points.

The three resident services (Worker, Scheduler, Notification Worker) must all
survive the same lifecycle:

* they start from deployment-owned database/principal authority alone, before
  any Active configuration exists;
* they stay alive across empty setup, eligible publication and recoverable
  faults;
* they read the *current* Active authority at each admission boundary instead of
  binding to whatever existed at process start.

This module owns that shared composition.  It resolves bounded infrastructure
state — the immutable database locator and the registration/heartbeat rows —
without ever loading business configuration, constructing Storage/Provider
adapters, or admitting work.  Business configuration is resolved by the caller
at the point where it is actually needed, which is what makes "no Active" a
normal, reportable state rather than a startup error.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

from mediaflow.application.resident_services import ResidentServiceService
from mediaflow.domain.resident_services import (
    ResidentServiceReadiness,
    ResidentServiceWaiting,
    bounded_resident_detail,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository


@dataclass(frozen=True)
class ResidentRuntime:
    """The bounded deployment authority one resident process needs to start.

    ``database_path`` is the only deployment-owned locator a resident service
    requires.  No Storage, Provider, strategy or business object is resolved
    here, so this is exactly the same authority the API uses to remain
    reachable for configuration recovery before first activation.
    """

    database_path: str
    service: ResidentServiceService

    def repository(self) -> SQLiteTaskRepository:
        """Open a repository for one bounded unit of resident work."""

        return SQLiteTaskRepository(self.database_path)


def build_resident_runtime(database_path: str) -> ResidentRuntime:
    """Create the shared registration/readiness service over one database."""

    return ResidentRuntime(
        database_path=database_path,
        service=ResidentServiceService(
            SQLiteTaskRepository(database_path), runtime_schema_version=SCHEMA_VERSION
        ),
    )


def resident_instance_id(service: str) -> str:
    """A bounded, non-secret per-process identity for the heartbeat row.

    The identity is only meaningful to the process that wrote it, so a random
    suffix is enough and keeps two replicas of the same service distinguishable
    without exposing host or deployment details.
    """

    return f"{service}-{secrets.token_hex(6)}"


def register_resident_process(
    runtime: ResidentRuntime,
    service: str,
    instance_id: str,
    *,
    heartbeat_interval_seconds: float,
    snapshot_id: str | None = None,
) -> None:
    """Register this process and set its initial (working) waiting state.

    Registering with an explicit "none" waiting reason keeps the projection
    honest: a service that has just started and has not yet observed a reason
    must not appear to be silently failing.  It starts a normal state, not a
    degraded one.
    """

    runtime.service.register(
        service,
        instance_id,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        configuration_snapshot_id=snapshot_id,
    )
    runtime.service.record_wait_state(
        service,
        instance_id,
        waiting_reason=ResidentServiceWaiting.NONE.value,
        waiting_detail="",
    )


def note_resident_waiting(
    runtime: ResidentRuntime,
    service: str,
    instance_id: str,
    *,
    reason: str,
    detail: str = "",
    stdout: TextIO | None = None,
) -> None:
    """Record and optionally surface one bounded waiting transition.

    Repeating an unchanged reason must not spam the resident process log: an
    operator watching the container should see the state change and then a
    steady, quiet wait.  The durable row is always updated; only the console
    line is de-duplicated.
    """

    bounded = bounded_resident_detail(detail)
    previous = runtime.service.wait_state(service, instance_id)
    changed = previous is None or previous.waiting_reason != reason
    runtime.service.record_wait_state(
        service, instance_id, waiting_reason=reason, waiting_detail=bounded
    )
    if changed and stdout is not None:
        stdout.write(f"{service} waiting: {reason}" + (f" ({bounded})" if bounded else "") + "\n")
        stdout.flush()


def resident_health_error(
    runtime: ResidentRuntime,
    service: str,
    instance_id: str | None = None,
) -> str | None:
    """Bounded infrastructure-readiness error for a container-local probe.

    A correctly-waiting service is infrastructure-ready: only a missing,
    stale, stopped or schema-incompatible *process* makes a container
    unhealthy.  Work readiness is reported separately and never gates the
    container.
    """

    readiness = runtime.service.evaluate_readiness(service, instance_id=instance_id)
    if readiness.get("ready"):
        return None
    condition = str(readiness.get("condition", ResidentServiceReadiness.NO_SERVICE.value))[:64]
    return f"resident {service} is not infrastructure-ready ({condition})"


class ResidentLoop:
    """A fault-tolerant resident loop with bounded waiting and heartbeating.

    Two different states have to be treated differently:

    * a **recoverable** runtime fault (the database briefly unavailable, an
      Active that is momentarily unreadable) must keep the process alive,
      record a bounded waiting reason and retry on the next poll;
    * a **configuration** fault is not an exception at all — it is the ordinary
      "there is nothing to do yet" state, recorded the same way.

    Only an *invalid deployment input* is a genuine startup error, and that is
    detected before this loop is ever entered.  Anything that escapes the loop
    body is therefore treated as recoverable by default, because killing a
    resident process never repairs a configuration or a database and always
    loses in-flight progress.
    """

    def __init__(
        self,
        runtime: ResidentRuntime,
        service: str,
        instance_id: str,
        *,
        heartbeat_interval_seconds: float,
        poll_seconds: float,
        stdout: TextIO,
        step: Callable[[ResidentLoop], int],
        describe: Callable[[BaseException], tuple[str, str]] | None = None,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("resident poll interval must be positive")
        self._runtime = runtime
        self._service = service
        self._instance_id = instance_id
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._poll_seconds = poll_seconds
        self._stdout = stdout
        self._step = step
        self._describe = describe
        self._last_heartbeat = 0.0

    def note(self, reason: str, detail: str = "") -> None:
        """Record a bounded waiting state from inside a loop step."""

        note_resident_waiting(
            self._runtime,
            self._service,
            self._instance_id,
            reason=reason,
            detail=detail,
            stdout=self._stdout,
        )

    def clear_waiting(self) -> None:
        """Return to the normal "running, nothing to report" state."""

        note_resident_waiting(
            self._runtime,
            self._service,
            self._instance_id,
            reason=ResidentServiceWaiting.NONE.value,
        )

    def run(self, stop_requested: Callable[[], bool], sleep: Callable[[float], None]) -> int:
        processed = 0
        try:
            while not stop_requested():
                worked = 0
                try:
                    worked = self._step(self)
                except Exception as error:  # noqa: BLE001 - deliberate boundary
                    reason, detail = self._reason_for(error)
                    self.note(reason, detail)
                processed += worked
                self._maybe_heartbeat()
                if not worked:
                    sleep(self._poll_seconds)
        finally:
            self._runtime.service.stop(self._instance_id)
        return processed

    def _reason_for(self, error: BaseException) -> tuple[str, str]:
        if self._describe is not None:
            reason, detail = self._describe(error)
            return reason, detail
        category = type(error).__name__
        return (
            ResidentServiceWaiting.CONFIGURATION_UNAVAILABLE.value,
            f"{category}: this service cannot read its current configuration yet",
        )

    def _maybe_heartbeat(self) -> None:
        """Heartbeat on a wall-clock interval, not on every poll.

        A fast poll must not turn into a write storm against the shared
        database, and a slow poll must still keep the registration fresh.
        """

        import time

        now = time.monotonic()
        if now - self._last_heartbeat < self._heartbeat_interval_seconds:
            return
        self._last_heartbeat = now
        try:
            self._runtime.service.heartbeat(self._instance_id)
        except Exception:
            # A heartbeat fault is reported through the same bounded waiting
            # channel and retried on the next tick; it must never end the loop.
            self.note(ResidentServiceWaiting.DATABASE_UNAVAILABLE.value, "heartbeat failed")
