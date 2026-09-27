"""Durable resident-service identity, heartbeat and waiting state.

Slice 40 separates three truths that the previous release conflated:

* **process liveness** — the container/command is running at all;
* **infrastructure readiness** — the shared durable database is compatible and
  the real resident process registered and is still heartbeating;
* **work readiness** — whether a particular capability can actually run work
  right now, which additionally depends on the current Active configuration.

This module owns only the durable infrastructure boundary.  It never loads an
Active configuration, constructs a Storage or Provider, admits work or performs
any mutation other than recording this process's own heartbeat.  That keeps it
safe to call from a Compose healthcheck and from the authenticated status API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from mediaflow.domain.automation import (
    validate_worker_id,
    worker_stale_threshold_seconds,
)

# The three resident services plus the API, which registers only its own
# liveness.  Keep this bounded and explicit: an unknown service name is a
# programming error, never a silently accepted value.
RESIDENT_SERVICES: tuple[str, ...] = ("api", "worker", "scheduler", "notification-worker")

# The infrastructure role of a resident service.  ``api`` and ``worker`` are
# always expected to be *up*; ``scheduler`` and ``notification-worker`` are also
# always expected to be *up* but are separately reported as *waiting* for
# business configuration.  The two states are deliberately independent so a
# correctly-waiting Scheduler is never reported as an infrastructure failure.
RESIDENT_SERVICE_LABELS: dict[str, str] = {
    "api": "API",
    "worker": "Worker",
    "scheduler": "Scheduler",
    "notification-worker": "Notification Worker",
}

MAX_RESIDENT_SERVICE_DETAIL_LENGTH = 200


class ResidentServiceName(StrEnum):
    API = "api"
    WORKER = "worker"
    SCHEDULER = "scheduler"
    NOTIFICATION_WORKER = "notification-worker"


class ResidentServiceStatus(StrEnum):
    """Derived status of one registered resident process."""

    LIVE = "live"
    STALE = "stale"
    STOPPED = "stopped"


class ResidentServiceReadiness(StrEnum):
    """Infrastructure readiness condition for one resident service."""

    READY = "ready"
    NO_SERVICE = "no_service"
    STALE_SERVICE = "stale_service"
    SCHEMA_MISMATCH = "schema_mismatch"


class ResidentServiceWaiting(StrEnum):
    """Why a live resident process is not doing work right now.

    These values are stable machine-readable reasons.  They never carry a
    secret, a raw exception or a private filesystem path: the callers pass
    already-bounded text and this module truncates defensively.
    """

    NONE = "none"
    UNCONFIGURED = "unconfigured"
    CONFIGURATION_UNAVAILABLE = "configuration_unavailable"
    SECRET_UNAVAILABLE = "secret_unavailable"
    DATABASE_UNAVAILABLE = "database_unavailable"
    SCHEMA_UNSUPPORTED = "schema_unsupported"


_RESIDENT_WAITING_VALUES = frozenset(item.value for item in ResidentServiceWaiting)
_RESIDENT_SERVICE_VALUES = frozenset(item.value for item in ResidentServiceName)


def validate_resident_service_name(service: str) -> str:
    """Return the bounded service name, or fail closed on an unknown one."""

    if not isinstance(service, str) or service not in _RESIDENT_SERVICE_VALUES:
        raise ValueError(
            f"resident service must be one of {', '.join(sorted(_RESIDENT_SERVICE_VALUES))}"
        )
    return service


def validate_resident_waiting_reason(reason: str | None) -> str | None:
    """Return a stable waiting reason, rejecting unbounded operator text."""

    if reason is None:
        return None
    if not isinstance(reason, str) or reason not in _RESIDENT_WAITING_VALUES:
        raise ValueError("resident service waiting reason must be a bounded known value")
    return reason


def bounded_resident_detail(value: object) -> str:
    """Bound an operator-facing detail without exposing secrets or long text.

    Only the exception *category* reaches a status projection.  A raw message
    may contain an endpoint, a private path or a credential, so the value is
    truncated rather than passed through.
    """

    if value is None:
        return ""
    if isinstance(value, BaseException):
        text = type(value).__name__
    else:
        text = str(value)
    text = " ".join(text.split())
    if len(text) > MAX_RESIDENT_SERVICE_DETAIL_LENGTH:
        return text[: MAX_RESIDENT_SERVICE_DETAIL_LENGTH - 1] + "…"
    return text


@dataclass(frozen=True)
class ResidentServiceRegistration:
    """One durable resident-process registration and heartbeat row.

    ``configuration_snapshot_id`` records which Active identity the process was
    bound to at registration time.  It is informational: a resident service must
    stay live and re-read the current Active at each admission boundary, so a
    newer Active never makes this row "wrong" — it only explains what the
    process last observed.  ``None`` means the process has not yet observed any
    valid Active, which is the normal first-setup state.
    """

    service: str
    instance_id: str
    registered_at: datetime
    last_heartbeat_at: datetime
    heartbeat_interval_seconds: float
    runtime_schema_version: int
    configuration_snapshot_id: str | None
    status: ResidentServiceStatus

    def __post_init__(self) -> None:
        validate_resident_service_name(self.service)
        validate_worker_id(self.instance_id)
        if (
            isinstance(self.heartbeat_interval_seconds, bool)
            or not isinstance(self.heartbeat_interval_seconds, (int, float))
            or self.heartbeat_interval_seconds <= 0
        ):
            raise ValueError("resident service heartbeat interval must be positive")
        if (
            isinstance(self.runtime_schema_version, bool)
            or not isinstance(self.runtime_schema_version, int)
            or self.runtime_schema_version < 0
        ):
            raise ValueError("runtime schema version must be a non-negative integer")
        if self.configuration_snapshot_id is not None:
            validate_worker_id(self.configuration_snapshot_id)


@dataclass(frozen=True)
class ResidentServiceWaitState:
    """The latest durable reason a live resident process is not doing work.

    The waiting state is a *description*, not a readiness gate: infrastructure
    readiness is derived only from the heartbeat, so a correctly-waiting service
    is still infrastructure-ready.  It is updated in place by the process that
    owns the row, so an operator sees the current bounded reason after a
    configuration fault is repaired.
    """

    service: str
    waiting_reason: str | None
    waiting_detail: str
    updated_at: datetime

    def __post_init__(self) -> None:
        validate_resident_service_name(self.service)
        validate_resident_waiting_reason(self.waiting_reason)

    @property
    def is_waiting(self) -> bool:
        return self.waiting_reason not in (None, ResidentServiceWaiting.NONE.value)


def resident_stale_threshold_seconds(heartbeat_interval_seconds: float) -> float:
    """Reuse the proven processing-Worker staleness policy."""

    return worker_stale_threshold_seconds(heartbeat_interval_seconds)


def evaluate_resident_service_status(
    registration: ResidentServiceRegistration,
    now: datetime,
) -> ResidentServiceStatus:
    """Derive live/stale for one registration without writing anything."""

    if registration.status is ResidentServiceStatus.STOPPED:
        return ResidentServiceStatus.STOPPED
    threshold = resident_stale_threshold_seconds(registration.heartbeat_interval_seconds)
    if (now - registration.last_heartbeat_at).total_seconds() > threshold:
        return ResidentServiceStatus.STALE
    return ResidentServiceStatus.LIVE
