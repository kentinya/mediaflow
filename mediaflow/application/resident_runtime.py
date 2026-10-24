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

import math
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

from mediaflow.application.resident_services import ResidentServiceService
from mediaflow.domain.automation_settings import (
    ADOPTION_REPORT_REFRESH_SECONDS,
    CONFIG_RECHECK_SECONDS,
    ResidentCadence,
)
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


def resident_cadence_adoption(
    runtime: ResidentRuntime,
    service: str,
    instance_id: str,
    *,
    field_path: str,
    published_resolver: Callable[[], tuple[str, int | None, str, float] | None],
    override_poll_seconds: float | None = None,
    override_source: str | None = None,
    clock: Callable[[], object] | None = None,
) -> tuple[Callable[[], ResidentCadence | None], Callable[[ResidentCadence], object]]:
    """Compose this process's cadence resolver and its own adoption report.

    The resolver reads the *current* published publication identity and the one
    cadence field this service consumes.  The reporter writes the durable row
    only after the loop installed the value, so a report can never precede the
    effect it claims.  An explicit CLI/deployment override keeps precedence and
    is recorded as an override rather than as adoption of the published value.
    """

    from datetime import UTC, datetime

    from mediaflow.domain.automation_settings import ResidentSettingsEvidence

    current_clock = clock or (lambda: datetime.now(UTC))

    def resolve() -> ResidentCadence | None:
        published = published_resolver()
        if published is None:
            return None
        revision_id, revision_version, digest, published_poll = published
        if not revision_id or not digest:
            return None
        if override_poll_seconds is not None:
            return ResidentCadence(
                service=service,
                field_path=field_path,
                poll_seconds=float(override_poll_seconds),
                published_revision_id=revision_id,
                published_revision_version=revision_version,
                published_revision_digest=digest,
                override_source=override_source or "cli",
            )
        return ResidentCadence(
            service=service,
            field_path=field_path,
            poll_seconds=float(published_poll),
            published_revision_id=revision_id,
            published_revision_version=revision_version,
            published_revision_digest=digest,
        )

    def report(cadence: ResidentCadence) -> object:
        return runtime.service.record_settings_adoption(
            ResidentSettingsEvidence(
                service=service,
                instance_id=instance_id,
                published_revision_id=cadence.published_revision_id,
                published_revision_version=cadence.published_revision_version,
                published_revision_digest=cadence.published_revision_digest,
                applied_fields=(cadence.field_path,),
                effective_values={cadence.field_path: float(cadence.poll_seconds)},
                override_source=cadence.override_source,
                reported_at=current_clock(),
            )
        )

    return (resolve, report)


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
        cadence_resolver: Callable[[], ResidentCadence | None] | None = None,
        adoption_reporter: Callable[[ResidentCadence], object] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        if poll_seconds <= 0 or not math.isfinite(float(poll_seconds)):
            raise ValueError("resident poll interval must be a positive finite number")
        self._runtime = runtime
        self._service = service
        self._instance_id = instance_id
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._poll_seconds = float(poll_seconds)
        self._stdout = stdout
        self._step = step
        self._describe = describe
        self._last_heartbeat = 0.0
        # Engine settings adoption is optional so a consumer with no published
        # cadence (the Notification Worker) keeps its existing behaviour and is
        # never asked to report a field it does not consume.
        self._cadence_resolver = cadence_resolver
        self._adoption_reporter = adoption_reporter
        #: The exact cadence this process last installed and acknowledged.
        self._applied_cadence: ResidentCadence | None = None
        #: The most recent resolution, so a transient configuration fault does
        #: not silently reinstall a stale value or lose a valid adoption.
        self._last_resolved_cadence: ResidentCadence | None = None
        #: A bounded, secret-free reason the last adoption attempt failed.
        self._adoption_blocker: tuple[str, str] | None = None
        #: Wall/monotonic clock used for cadence scheduling and report refresh.
        #: It is injectable so a controlled-clock test can prove the wait
        #: deadlines without sleeping in real time.
        self._monotonic = monotonic or time.monotonic
        #: When this process last *successfully* wrote its own adoption report.
        #: ``None`` means nothing has been reported yet, so the first successful
        #: adoption always reports.
        self._last_report_at: float | None = None
        #: How many times a report refresh was attempted but failed.  It is only
        #: diagnostic; the retry itself happens on the next safe boundary.
        self.adoption_report_failures = 0

    @property
    def poll_seconds(self) -> float:
        """The cadence this loop is currently using (the real observable)."""

        return self._poll_seconds

    @property
    def applied_cadence(self) -> ResidentCadence | None:
        return self._applied_cadence

    @property
    def adoption_blocker(self) -> tuple[str, str] | None:
        return self._adoption_blocker

    def effective_poll_deadline(self) -> float:
        """The bounded *configuration/heartbeat* wake interval.

        This is the bound for re-observing configuration, refreshing the
        heartbeat and refreshing this process's own adoption report.  It is not
        the business poll: a wake never claims work, ticks the Scheduler or
        emits an occurrence, so a previously long cadence still observes a new
        publication promptly without turning a recheck into an early poll.
        """

        return min(self._poll_seconds, CONFIG_RECHECK_SECONDS)

    def business_poll_deadline(self) -> float:
        """How long the *business* cadence waits from now.

        The value this process actually selected (published or overridden) is
        preserved here; only the recheck wakes in between are bounded.
        """

        return self._poll_seconds

    def adopt_cadence(self) -> bool:
        """Install the currently published cadence at a safe loop boundary.

        Called before each step and on each bounded recheck wake.  The effective
        cadence is only acknowledged after it is actually installed, and an
        explicitly overridden process keeps its own cadence while reporting the
        override truthfully.

        The report is written by this process only, and only after the cadence
        is installed.  An unchanged cadence is re-reported on a bounded cadence
        so a live consumer never decays into "stale" merely because nothing
        changed, and a failed write is retried at the next safe boundary instead
        of being silently remembered as adopted.
        """

        if self._cadence_resolver is None:
            return False
        try:
            candidate = self._cadence_resolver()
        except Exception:
            # A transient configuration/database fault must not change the
            # cadence in use; the loop keeps the last known-good value and the
            # existing fault path reports the recoverable state.
            self._adoption_blocker = (
                "configuration_unavailable",
                "current engine settings could not be read; the previous cadence stays in use",
            )
            return False
        if candidate is None:
            self._adoption_blocker = (
                "configuration_unavailable",
                "no valid published engine settings exist yet; the infrastructure default "
                "cadence stays in use",
            )
            return False
        self._last_resolved_cadence = candidate
        self._poll_seconds = float(candidate.poll_seconds)
        self._adoption_blocker = None
        previous = self._applied_cadence
        changed = (
            previous is None
            or previous.published_revision_digest != candidate.published_revision_digest
            or previous.poll_seconds != candidate.poll_seconds
            or previous.override_source != candidate.override_source
        )
        if self._adoption_reporter is None:
            self._applied_cadence = candidate
            return True
        now = self._monotonic()
        due = (
            self._last_report_at is None
            or (now - self._last_report_at) >= ADOPTION_REPORT_REFRESH_SECONDS
        )
        if not changed and not due:
            return True
        try:
            self._adoption_reporter(candidate)
        except Exception:
            # Reporting uses the same database as work.  A failed report keeps
            # the loop alive, is retried on the next safe boundary, and does not
            # acknowledge the cadence: the consumer stays visibly unreported
            # rather than claiming an adoption it could not prove.
            self.adoption_report_failures += 1
            return False
        self.adoption_report_failures = 0
        self._applied_cadence = candidate
        self._last_report_at = now
        return True

    def note(self, reason: str, detail: str = "") -> None:
        """Record a bounded waiting state from inside a loop step."""

        try:
            note_resident_waiting(
                self._runtime,
                self._service,
                self._instance_id,
                reason=reason,
                detail=detail,
                stdout=self._stdout,
            )
        except Exception:
            # Reporting uses the same database as work. A failed report must
            # neither terminate the process nor permit the failed step to continue.
            pass

    def clear_waiting(self) -> None:
        """Return to the normal "running, nothing to report" state."""

        self.note(ResidentServiceWaiting.NONE.value)

    def run(self, stop_requested: Callable[[], bool], sleep: Callable[[float], None]) -> int:
        processed = 0
        # Adopt at the very first boundary so a process that started before the
        # first publication picks it up as soon as it exists.
        self.adopt_cadence()
        # The business cadence deadline is kept across bounded configuration
        # wakes: a recheck must never become an early claim/tick/emission.
        next_business_poll = self._monotonic()
        try:
            while not stop_requested():
                now = self._monotonic()
                if now < next_business_poll:
                    # Configuration/heartbeat/report wake only.  No work is
                    # claimed, no schedule is ticked and nothing is emitted, so
                    # the selected business cadence is preserved exactly.
                    self.adopt_cadence()
                    self._maybe_heartbeat()
                    remaining = next_business_poll - self._monotonic()
                    if remaining <= 0:
                        continue
                    # Adopting a *shorter* cadence during the wait shortens the
                    # pending business deadline; a longer one never extends a
                    # wait that was already scheduled.
                    next_business_poll = min(
                        next_business_poll, self._monotonic() + self._poll_seconds
                    )
                    remaining = next_business_poll - self._monotonic()
                    if remaining <= 0:
                        continue
                    sleep(max(0.0, min(self.effective_poll_deadline(), remaining)))
                    continue
                worked = 0
                try:
                    schema = self._runtime.service._repository.schema_version
                    if schema != SCHEMA_VERSION:
                        self.note(
                            "schema_unsupported", "run the explicit upgrade/recovery workflow"
                        )
                    else:
                        # A busy step may have observed a new publication; adopt
                        # only at this boundary, never in the middle of admitted
                        # work, so an in-flight pin is never repinned.
                        self.adopt_cadence()
                        worked = self._step(self)
                except Exception as error:  # noqa: BLE001 - deliberate boundary
                    reason, detail = self._reason_for(error)
                    self.note(reason, detail)
                processed += worked
                self._maybe_heartbeat()
                if worked:
                    # The existing immediate-drain rule: real processed work is
                    # followed by another step without waiting a full cadence.
                    next_business_poll = self._monotonic()
                else:
                    next_business_poll = self._monotonic() + self.business_poll_deadline()
        finally:
            try:
                self._runtime.service.stop(self._instance_id)
            except Exception:
                # During an outage the durable heartbeat expires naturally.
                pass
        return processed

    def _reason_for(self, error: BaseException) -> tuple[str, str]:
        import sqlite3

        if isinstance(error, sqlite3.Error):
            return (
                ResidentServiceWaiting.DATABASE_UNAVAILABLE.value,
                "database unavailable; restore access and this service will retry safely",
            )
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

        now = self._monotonic()
        if now - self._last_heartbeat < self._heartbeat_interval_seconds:
            return
        self._last_heartbeat = now
        try:
            self._runtime.service.heartbeat(self._instance_id)
        except Exception:
            # A heartbeat fault is reported through the same bounded waiting
            # channel and retried on the next tick; it must never end the loop.
            self.note(ResidentServiceWaiting.DATABASE_UNAVAILABLE.value, "heartbeat failed")
