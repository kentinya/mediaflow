"""Resident-service registration, heartbeat and infrastructure readiness.

Every resident MediaFlow process (API, Worker, Scheduler, Notification Worker)
registers itself here on startup and refreshes a heartbeat.  That makes
"the real process is running" an observable fact rather than an inference from
the presence of a static configuration file.

The application boundary is deliberately read-only apart from a process's own
heartbeat: it never loads an Active configuration, never opens a Storage or
Provider, never admits work and never migrates schema.  A Compose healthcheck
and the authenticated status API therefore share one truthful implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from mediaflow.domain.resident_services import (
    RESIDENT_SERVICES,
    ResidentServiceReadiness,
    ResidentServiceRegistration,
    ResidentServiceStatus,
    ResidentServiceWaitState,
    evaluate_resident_service_status,
    resident_stale_threshold_seconds,
    validate_resident_service_name,
)

# Bounded, operator-facing recovery text.  These are deliberately written as
# actions rather than protocol detail: the Slice forbids exposing raw
# exceptions, tokens or implementation identifiers to the operator.
_NEXT_ACTIONS: dict[str, str] = {
    ResidentServiceReadiness.READY.value: "none",
    ResidentServiceReadiness.NO_SERVICE.value: (
        "start the resident service; durable work and configuration are preserved"
    ),
    ResidentServiceReadiness.STALE_SERVICE.value: (
        "restart the resident service; durable work and configuration are preserved"
    ),
    ResidentServiceReadiness.SCHEMA_MISMATCH.value: (
        "upgrade the deployment to a compatible MediaFlow version, then restart the service"
    ),
}

_DURABLE_STATES: dict[str, str] = {
    ResidentServiceReadiness.READY.value: "the resident service is registered and heartbeating",
    ResidentServiceReadiness.NO_SERVICE.value: (
        "no resident service has ever registered for this deployment"
    ),
    ResidentServiceReadiness.STALE_SERVICE.value: (
        "a resident service registered previously and its heartbeat is now stale"
    ),
    ResidentServiceReadiness.SCHEMA_MISMATCH.value: (
        "the registered resident service reports a runtime schema that differs from "
        "this application"
    ),
}


class ResidentServiceRepository(Protocol):
    """Persistence contract for resident-service heartbeat rows."""

    def register_resident_service(
        self,
        service: str,
        instance_id: str,
        heartbeat_interval_seconds: float,
        runtime_schema_version: int,
        configuration_snapshot_id: str | None,
        now: datetime,
    ) -> ResidentServiceRegistration: ...

    def heartbeat_resident_service(self, instance_id: str, now: datetime) -> bool: ...

    def stop_resident_service(self, instance_id: str, now: datetime) -> None: ...

    def get_resident_service(
        self, service: str, instance_id: str
    ) -> ResidentServiceRegistration | None: ...

    def list_resident_services(self) -> tuple[ResidentServiceRegistration, ...]: ...

    def set_resident_service_wait_state(
        self,
        service: str,
        instance_id: str,
        waiting_reason: str | None,
        waiting_detail: str,
        now: datetime,
    ) -> None: ...

    def get_resident_service_wait_state(
        self, service: str, instance_id: str
    ) -> ResidentServiceWaitState | None: ...


class ResidentServiceService:
    """Register resident processes and report infrastructure readiness."""

    def __init__(
        self,
        repository: ResidentServiceRepository,
        *,
        runtime_schema_version: int = 0,
    ) -> None:
        self._repository = repository
        self._runtime_schema_version = int(runtime_schema_version)

    def register(
        self,
        service: str,
        instance_id: str,
        *,
        heartbeat_interval_seconds: float = 5.0,
        configuration_snapshot_id: str | None = None,
        now: datetime | None = None,
    ) -> ResidentServiceRegistration:
        """Register or refresh this process's own durable presence."""

        return self._repository.register_resident_service(
            service,
            instance_id,
            heartbeat_interval_seconds,
            self._runtime_schema_version,
            configuration_snapshot_id,
            now or datetime.now(UTC),
        )

    def heartbeat(self, instance_id: str, now: datetime | None = None) -> bool:
        """Refresh this process's own heartbeat; never revives a stopped row."""

        return self._repository.heartbeat_resident_service(instance_id, now or datetime.now(UTC))

    def stop(self, instance_id: str, now: datetime | None = None) -> None:
        """Mark this process's row stopped so readiness fails closed promptly."""

        try:
            self._repository.stop_resident_service(instance_id, now or datetime.now(UTC))
        except LookupError:
            # A process that was never registered has nothing to retire, and a
            # shutdown path must never raise over an absent row.
            return

    def record_wait_state(
        self,
        service: str,
        instance_id: str,
        *,
        waiting_reason: str | None,
        waiting_detail: str = "",
        now: datetime | None = None,
    ) -> None:
        """Record the bounded reason this live process is currently idle.

        The reason is a description for the operator, never a gate: recording
        ``unconfigured`` keeps the service infrastructure-ready.
        """

        self._repository.set_resident_service_wait_state(
            service,
            instance_id,
            waiting_reason,
            waiting_detail,
            now or datetime.now(UTC),
        )

    def get(self, service: str, instance_id: str) -> ResidentServiceRegistration | None:
        return self._repository.get_resident_service(
            validate_resident_service_name(service), instance_id
        )

    def list(self, now: datetime | None = None) -> tuple[ResidentServiceRegistration, ...]:
        return self._repository.list_resident_services()

    def wait_state(self, service: str, instance_id: str) -> ResidentServiceWaitState | None:
        return self._repository.get_resident_service_wait_state(
            validate_resident_service_name(service), instance_id
        )

    def evaluate_readiness(
        self,
        service: str,
        now: datetime | None = None,
        *,
        instance_id: str | None = None,
    ) -> dict[str, object]:
        """Bounded, side-effect-free infrastructure readiness for one service.

        When ``instance_id`` is supplied the answer describes exactly that
        resident process, which is what a container-local Compose healthcheck
        needs.  Without it the answer describes the deployment as a whole: one
        live, schema-compatible process is enough.
        """

        validate_resident_service_name(service)
        current_now = now or datetime.now(UTC)
        registrations = self._repository.list_resident_services()
        if instance_id is not None:
            scoped = [item for item in registrations if item.instance_id == instance_id]
        else:
            scoped = [item for item in registrations if item.service == service]
        derived = [(item, evaluate_resident_service_status(item, current_now)) for item in scoped]
        live = [(item, status) for item, status in derived if status is ResidentServiceStatus.LIVE]
        stale = [
            (item, status) for item, status in derived if status is ResidentServiceStatus.STALE
        ]
        stopped = [
            (item, status) for item, status in derived if status is ResidentServiceStatus.STOPPED
        ]
        schema_matched = [
            item for item, _ in live if item.runtime_schema_version == self._runtime_schema_version
        ]
        database_schema = getattr(self._repository, "schema_version", self._runtime_schema_version)
        if database_schema != self._runtime_schema_version:
            condition = ResidentServiceReadiness.SCHEMA_MISMATCH.value
        elif schema_matched:
            condition = ResidentServiceReadiness.READY.value
        elif live:
            condition = ResidentServiceReadiness.SCHEMA_MISMATCH.value
        elif stale:
            condition = ResidentServiceReadiness.STALE_SERVICE.value
        elif stopped:
            condition = ResidentServiceReadiness.NO_SERVICE.value
        else:
            condition = ResidentServiceReadiness.NO_SERVICE.value
        ready = condition == ResidentServiceReadiness.READY.value
        return {
            "service": service,
            "ready": ready,
            "condition": condition,
            "category": None if ready else condition,
            "durableState": _DURABLE_STATES[condition],
            "sideEffects": "none",
            "retrySafe": True,
            "nextAction": _NEXT_ACTIONS[condition],
            "asOf": current_now.isoformat(),
            "liveServices": len(live),
            "staleServices": len(stale),
            "stoppedServices": len(stopped),
            "totalServices": len(derived),
            "expectedSchemaVersion": self._runtime_schema_version,
            "staleThresholdSeconds": (
                resident_stale_threshold_seconds(schema_matched[0].heartbeat_interval_seconds)
                if schema_matched
                else None
            ),
        }

    def deployment_readiness(self, now: datetime | None = None) -> dict[str, object]:
        """Readiness for every resident service this deployment declares.

        The projection is intentionally small: it names the service, whether the
        real process is infrastructure-ready, and — for the services that can
        wait for configuration — whether it is currently idle and why.  It never
        evaluates business work readiness, which depends on the Active
        configuration and belongs to the configuration/operations projections.
        """

        current_now = now or datetime.now(UTC)
        registrations = self._repository.list_resident_services()
        services: dict[str, object] = {}
        for service in RESIDENT_SERVICES:
            readiness = self.evaluate_readiness(service, current_now)
            live = [
                item
                for item in registrations
                if item.service == service
                and evaluate_resident_service_status(item, current_now)
                is ResidentServiceStatus.LIVE
            ]
            waiting = None
            for item in live:
                state = self._repository.get_resident_service_wait_state(service, item.instance_id)
                if state is not None and state.is_waiting:
                    waiting = state
                    break
            services[service] = {
                **readiness,
                "waiting": waiting is not None,
                "waitingReason": waiting.waiting_reason if waiting is not None else None,
                "waitingDetail": waiting.waiting_detail if waiting is not None else "",
                # Only a bounded, non-secret observation.  Process identity stays
                # out of the operator projection; it is available to the
                # instance-scoped healthcheck that owns that same process.
                "instanceCount": len(live),
            }
        return {
            "sideEffects": "none",
            "asOf": current_now.isoformat(),
            "services": services,
            "infrastructureReady": all(bool(item["ready"]) for item in services.values()),
        }
