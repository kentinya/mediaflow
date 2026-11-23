"""Fixed resident-service entry for API, Worker, Scheduler and Notification Worker.

The four production services start from the deployment database locator alone.
This entry owns no general command dispatch: it accepts exactly one service
name, performs the same read-only preflight and shared runtime lease as the
deployment boundary, and then runs the existing service assembly.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import signal
import sys
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from typing import TextIO

from mediaflow.application.accounts import AccountService
from mediaflow.application.automation import (
    AutomationConfigurationUnavailable,
    AutomationFailureEvidence,
    IntervalScheduler,
    ResidentProcessingWorker,
)
from mediaflow.application.automation_definition_execution import (
    DefinitionScopedExecutionService,
)
from mediaflow.application.automation_execution_authority import AutomationExecutionAuthority
from mediaflow.application.configuration_snapshot import (
    ManagedConfigurationService,
)
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.notification import (
    NotificationPublisher,
    NotificationWorker,
)
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.resident_services import ResidentServiceService
from mediaflow.application.strategy_test import strategy_runner_from_configuration
from mediaflow.container_entrypoint import container_preflight_errors, load_environment_file
from mediaflow.domain.automation import SchedulerConfigurationSnapshot
from mediaflow.domain.automation_settings import engine_values_from_document
from mediaflow.domain.configuration_input import reject_retired_configuration_input
from mediaflow.domain.configuration_management import (
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.resident_services import ResidentServiceWaiting
from mediaflow.domain.security import ApiPermission
from mediaflow.domain.task_persistence import (
    FILES_DELETE_TASK_COMMAND,
    FILES_TRANSFER_TASK_COMMAND,
    direct_command_task_command,
)
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.metadata_provider_bootstrap import (
    LazyMetadataProviderRegistryFactory,
    metadata_provider_registry_from_environment,
)
from mediaflow.infrastructure.operational_logging import SQLiteOperationalLogger
from mediaflow.infrastructure.runtime_configuration import (
    ManagementBootstrapConfiguration,
    RuntimeConfiguration,
    load_managed_runtime_configuration,
    load_management_bootstrap,
)
from mediaflow.infrastructure.runtime_lease import (
    RuntimeDatabaseLease,
    RuntimeLeaseMode,
    RuntimeLeaseUnavailable,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.runtime_support import (
    ResidentConfigurationUnavailable,
)
from mediaflow.runtime_support import (
    attach_task_terminal_notifications as _attach_task_terminal_notifications,
)
from mediaflow.runtime_support import (
    bootstrap_database_path as _bootstrap_database_path,
)
from mediaflow.runtime_support import (
    configuration_document as _configuration_document,
)
from mediaflow.runtime_support import (
    current_runtime_configuration as _current_runtime_configuration,
)
from mediaflow.runtime_support import (
    managed_snapshot_reference as _managed_snapshot_reference,
)
from mediaflow.runtime_support import (
    resident_failure_reason as _resident_failure_reason,
)
from mediaflow.runtime_support import (
    resolve_configuration as _configuration,
)
from mediaflow.runtime_support import (
    resolve_resident_configuration as _resolve_resident_configuration,
)


class _ConfiguredPermissionAuthority:
    """Current execution permission from the database account, or legacy config.

    A real account is always authoritative.  The JSON-configuration fallback
    exists only for focused compatibility tests that still pass principal
    definitions directly; a fresh deployment has no such definitions, so an
    unknown or revoked account is denied.
    """

    def __init__(
        self,
        configuration_provider: Callable[[], object],
        account_service: AccountService | None = None,
    ) -> None:
        self._configuration_provider = configuration_provider
        self._account_service = account_service

    def has_permission(self, principal_id: str, permission: str | ApiPermission) -> bool:
        if self._account_service is not None:
            repository = self._account_service._repository
            account = repository.get_account(principal_id)
            if account is not None:
                return self._account_service.has_permission(principal_id, permission)
            # Once the instance has durable accounts, a missing/unknown
            # principal is denied.  The JSON fallback is only for focused
            # compatibility tests that never created an account.
            if repository.count_accounts() > 0:
                return False
        configuration = self._configuration_provider()
        definitions = tuple(getattr(configuration, "api_principals", ()))
        expected = permission.value if isinstance(permission, ApiPermission) else str(permission)
        for definition in definitions:
            if definition.principal_id != principal_id:
                continue
            return bool(
                definition.enabled
                and any(
                    item == permission or getattr(item, "value", str(item)) == expected
                    for item in definition.permissions
                )
            )
        return False


def _definition_scoped_service(
    task_repository,
    configuration: RuntimeConfiguration,
    configured_path: str | None,
) -> DefinitionScopedExecutionService:
    """Build the one automatic definition pipeline for a Task repository.

    Shared by the legacy Job handoff and the Task-kernel automatic runner so a
    Scheduler/Run once Task and a legacy queued Job execute through the exact
    same application engine, authorities and factories.
    """

    operational_logger = (
        SQLiteOperationalLogger(
            task_repository,
            "workflow",
            configuration.operational_logging_minimum_level,
        )
        if configuration.operational_logging_enabled
        else None
    )
    return DefinitionScopedExecutionService(
        task_repository,
        configuration,
        storage_factory=configuration.create_storages,
        provider_factory=metadata_provider_registry_from_environment,
        strategy_factory=strategy_runner_from_configuration,
        history_factory=JsonLinesOperationHistoryRepository,
        execution_authority=AutomationExecutionAuthority(
            task_repository,
            permission_authority=_ConfiguredPermissionAuthority(
                lambda: _configuration(configured_path),
                AccountService(task_repository),
            ),
            publication_principal_resolver=lambda job, definition: (
                _definition_publication_principal(configuration.database_path, job, definition)
            ),
            live_intent_checker=lambda job, definition: _schedule_intent_continuity(
                configuration.database_path, job, definition
            ),
            live_definition_resolver=lambda definition_id: _live_automation_definition(
                configuration.database_path, definition_id
            ),
        ),
        logger=operational_logger,
    )


def _scheduler_execution_authority(configuration, repository):
    """Build the live definition authority the Scheduler checks before admission."""

    return AutomationExecutionAuthority(
        repository,
        permission_authority=_ConfiguredPermissionAuthority(
            lambda: _current_automation_configuration(configuration.database_path),
            AccountService(repository),
        ),
        publication_principal_resolver=lambda task, definition: _definition_publication_principal(
            configuration.database_path, task, definition
        ),
        live_intent_checker=lambda task, definition: _schedule_intent_continuity(
            configuration.database_path, task, definition
        ),
        live_definition_resolver=lambda definition_id: _live_automation_definition(
            configuration.database_path, definition_id
        ),
    )


@contextmanager
def _automatic_continuation_context(repository, configured_path: str | None):
    """Open the zero-mutation continuation-analysis boundary for one pass.

    The continuation reuses the existing intent/Preview analysis machinery
    under the Task's admitted pin, so the automatic Task's saved decision
    produces the same durable plan summary a Files Task owns — without faking
    a Files submission and without a second engine.  The checkpoint service
    carries the same managed snapshot validator the confirmation path reads,
    so the summary's durable version fence is the one fence everywhere.
    """

    from mediaflow.application.automatic_task_continuation import (
        AutomaticTaskContinuationService,
    )
    from mediaflow.application.manual_organize import ManualOrganizeIntentService
    from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
    from mediaflow.application.processing_checkpoint import ProcessingCheckpointService

    bootstrap_document = _configuration_document(configured_path)
    database_path = _bootstrap_database_path(bootstrap_document)
    with SQLiteConfigurationRepository(database_path) as configuration_repository:
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=database_path,
            bootstrap_document=bootstrap_document,
        )
        intents = ManualOrganizeIntentService(
            repository,
            configuration_service,
            storage_factory=lambda runtime, ids: runtime.create_storages(storage_ids=set(ids)),
        )
        previews = ManualOrganizePreviewService(
            repository,
            intents,
            configuration_service=configuration_service,
            metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                metadata_provider_registry_from_environment
            ),
            storage_factory=lambda runtime, ids: runtime.create_storages(storage_ids=set(ids)),
        )
        yield AutomaticTaskContinuationService(
            repository,
            intent_service=intents,
            preview_service=previews,
            checkpoint_service=ProcessingCheckpointService(
                repository,
                snapshot_validator=configuration_service.validate_runtime_snapshot,
            ),
        )


def _task_configuration_unavailable(
    error: RuntimeSnapshotUnavailable,
) -> AutomationConfigurationUnavailable:
    """Keep a corrupt admitted pin an actionable Task failure.

    The Task engine reports the durable failure; this conversion preserves the
    bounded category/effect/next-action vocabulary the Automation record and the
    operator's recovery surface already understand.  No Task, Provider, Storage
    or media effect is created here.
    """

    allowed_categories = {
        "active_missing",
        "active_unreadable",
        "digest_corrupt",
        "job_snapshot_incomplete",
        "job_snapshot_missing",
        "runtime_invalid",
        "schema_unsupported",
        "snapshot_digest_mismatch",
        "snapshot_missing",
        "snapshot_not_published",
        "snapshot_unreadable",
        "task_snapshot_incomplete",
        "task_snapshot_missing",
    }
    category = error.reason if error.reason in allowed_categories else "configuration_unavailable"
    return AutomationConfigurationUnavailable(
        AutomationFailureEvidence(
            category,
            "saved_configuration_unavailable",
            "none",
            False,
            "restore the saved published revision, or explicitly create new work under "
            "the current Active configuration",
        )
    )


def _pinned_task_configuration(configured_path: str | None, task):
    """Resolve one admitted Task's exact pin with actionable failure evidence."""

    try:
        return _configuration(
            configured_path,
            snapshot_id=task.configuration_snapshot_id,
            snapshot_digest=task.configuration_snapshot_digest,
        )
    except RuntimeSnapshotUnavailable as error:
        raise _task_configuration_unavailable(error) from error
    except (OSError, ValueError, LookupError) as error:
        raise AutomationConfigurationUnavailable(
            AutomationFailureEvidence(
                "snapshot_unreadable",
                "saved_configuration_unavailable",
                "none",
                False,
                "restore the saved published revision, or explicitly create new work under "
                "the current Active configuration",
            )
        ) from error


def _automatic_task_runner(repository, configured_path, scheduling_service):
    """Build the resident runner for one adopted Scheduler/Run once Task.

    It reconstructs the exact definition intent from the Task's admitted pin and
    its durable display origin, then runs the *same* definition-scoped pipeline
    the legacy Job handoff uses — under the Task's live claim fence and with the
    existing publication/authority continuity checks intact.  No Job row is
    written, no CLI text is parsed and no second engine is invoked.

    A Task that already owns durable TaskItems is a *continuation*: its saved
    four-type decision re-entered the same Task's zero-mutation analysis, so
    this runner advances that analysis instead of re-running the initial
    automatic intent.
    """

    def run(task, claim, clock=None, heartbeat=None) -> None:
        from mediaflow.domain.task_scheduling import TaskTrigger

        display = repository.get_run_display_context(task.task_id)
        if repository.list_items(task.task_id):
            # A continuation pass: the Task's own saved decisions re-entered its
            # zero-mutation analysis.  The pinned runtime is reconstructed from
            # the Task's admitted pin inside the continuation boundary.
            with _automatic_continuation_context(repository, configured_path) as continuation:
                continuation.run_pass(
                    task,
                    scheduling_service,
                    claim,
                    clock=clock,
                    heartbeat=heartbeat,
                )
            return
        if display is not None and display.origin_kind == "remote-organize":
            configuration = _pinned_task_configuration(configured_path, task)

            def direct_cancelled() -> bool:
                current = scheduling_service.state(task.task_id)
                return current is not None and current.control_request is not None

            service = _definition_scoped_service(repository, configuration, configured_path)
            service.run_direct_organize(
                task,
                scheduling_service,
                claim,
                cancellation_check=direct_cancelled,
                clock=clock,
                heartbeat=heartbeat,
            )
            return
        definition_id = display.origin_definition_id if display is not None else None
        if not isinstance(definition_id, str) or not definition_id.strip():
            raise RuntimeError("automatic Task has no durable definition origin")
        configuration = _pinned_task_configuration(configured_path, task)
        definition = next(
            (
                value
                for value in getattr(configuration, "automation_task_definitions", ())
                if getattr(value, "definition_id", getattr(value, "id", None)) == definition_id
            ),
            None,
        )
        if definition is None:
            raise RuntimeError("pinned Automation Task Definition is unavailable")
        state = scheduling_service.state(task.task_id)
        trigger = state.admission_trigger if state is not None else None
        run_once = trigger is TaskTrigger.RUN_ONCE

        def task_cancelled() -> bool:
            current = scheduling_service.state(task.task_id)
            return current is not None and current.control_request is not None

        service = _definition_scoped_service(repository, configuration, configured_path)
        service.run(
            task,
            scheduling_service,
            claim,
            run_once=run_once,
            cancellation_check=task_cancelled,
            clock=clock,
            heartbeat=heartbeat,
        )

    return run


def _definition_publication_principal(database_path, job, definition):
    from mediaflow.application.automation_execution_intent import resolve_principal

    with SQLiteConfigurationRepository(database_path) as repository:
        return resolve_principal(ManagedConfigurationService(repository), job, definition)


def _live_automation_definition(database_path, definition_id):
    from mediaflow.application.automation_execution_intent import live_definition

    with SQLiteConfigurationRepository(database_path) as repository:
        return live_definition(ManagedConfigurationService(repository), definition_id)


def _schedule_intent_continuity(database_path, job, definition):
    from mediaflow.application.automation_execution_intent import assert_schedule_continuity

    with SQLiteConfigurationRepository(database_path) as repository:
        assert_schedule_continuity(ManagedConfigurationService(repository), job, definition)


def _current_automation_configuration(database_path):
    """Read current permissions from the same managed authority as the Job queue."""
    with SQLiteConfigurationRepository(database_path) as repository:
        managed = ManagedConfigurationService(repository)
        active = managed.active()
        if active is None:
            raise RuntimeError("current Active is unavailable")
        managed.verify_integrity(active)
        return load_managed_runtime_configuration(
            active.document, bootstrap_database_path=str(database_path)
        )


def _resident_infrastructure_defaults() -> tuple[float, float, float]:
    """Bounded polling defaults used before any Active configuration exists.

    These are *infrastructure* settings, not business objects: a resident
    service needs a heartbeat cadence and a poll cadence to stay alive and stay
    observable during first setup, long before an operator has configured
    anything.  They are intentionally conservative, so the absence of Active
    changes only how often a resident process re-reads the current Active and
    never what it is allowed to do.
    """

    return (300.0, 5.0, 5.0)


def _current_managed_runtime_configuration(
    configured_path: str | None,
) -> RuntimeConfiguration | None:
    """Return the current **managed** Active runtime, or ``None``.

    This is the stricter resolution used by boundaries that must pin their work
    to published authority — the Scheduler's occurrence emission and the
    Notification Worker's target resolution.  A legacy JSON bootstrap has no
    snapshot identity, so it yields ``None`` here and those boundaries wait,
    which is correct: a resident process must never issue unpinned work in a
    deployment that has adopted managed configuration authority.
    """

    try:
        configuration = _configuration(configured_path)
    except Exception:
        return None
    if not getattr(configuration, "configuration_snapshot_id", None):
        return None
    return configuration


def _scheduler_waiting_reason(configuration: RuntimeConfiguration | None) -> tuple[str, str]:
    """Map a missing or unusable Active onto one bounded Scheduler waiting state."""

    if configuration is None:
        return (
            ResidentServiceWaiting.UNCONFIGURED.value,
            "no valid Active configuration is published; no schedule was issued",
        )
    if not configuration.automation_task_definitions:
        return (
            ResidentServiceWaiting.UNCONFIGURED.value,
            "the Active configuration declares no Automation Task Definition",
        )
    return (ResidentServiceWaiting.NONE.value, "")


def _resident_published_cadence_resolver(
    configured_path: str | None, field: str
) -> Callable[[], tuple[str, int | None, str, float] | None]:
    """Resolve the current publication identity plus one consumed poll cadence.

    Only managed Active authority is used, so a JSON compatibility bootstrap
    never becomes a published target for these engine settings.  The resolver is
    called at each safe loop boundary, which is what makes adoption independent
    of process start time and of work arriving.
    """

    def resolve() -> tuple[str, int | None, str, float] | None:
        try:
            document = _configuration_document(configured_path)
            database_path = _bootstrap_database_path(document)
            with SQLiteConfigurationRepository(database_path) as repository:
                active = repository.get_active_revision()
        except Exception:
            # A transient database/configuration fault yields no candidate: the
            # loop keeps the last known-good cadence rather than installing one
            # it cannot attribute to a publication.
            return None
        if active is None:
            return None
        values = engine_values_from_document(active.document)
        if values is None:
            return None
        cadence = values.worker_poll_seconds if field == "worker" else values.scheduler_poll_seconds
        return (
            active.revision_id,
            active.revision_sequence or active.version,
            active.digest,
            float(cadence),
        )

    return resolve


def _resident_snapshot_reference(path: str | None) -> tuple[str, str] | None:
    try:
        return _managed_snapshot_reference(path)
    except Exception:
        return None


def _run_worker(
    configuration,
    configured_path: str | None,
    *,
    stdout: TextIO,
) -> int:
    """Run the resident MediaFlow Worker from deployment-owned authority alone.

    The Worker already supported management-only bootstrap; this adds the two
    things the empty-setup boundary needs on top of it:

    * a **durable resident registration** that makes "the real Worker process is
      running" observable independently of the command families it happens to
      be serving right now, so an API/Compose readiness answer is not inferred
      from a static configuration file; and
    * a **bounded waiting reason** whenever the Worker is alive but has nothing
      lawful to consume, which is the normal state before first activation and
      again whenever the current Active is unusable.

    The existing per-command consumers are preserved untouched: queued Jobs
    still load their own pinned revision after the claim boundary, admitted
    manual Organize executions and both library-kind transfers still
    reconstruct their own immutable pin. Invalid pins are handled by those
    consumers' existing durable failure and recovery rules before mutation.
    """

    from mediaflow.application.resident_runtime import (
        ResidentLoop,
        build_resident_runtime,
        register_resident_process,
        resident_cadence_adoption,
        resident_instance_id,
    )

    _, default_poll, _ = _resident_infrastructure_defaults()
    runtime = build_resident_runtime(configuration.database_path)
    worker_snapshot = _resident_snapshot_reference(configured_path)
    instance_id = resident_instance_id("worker")
    resident_id = worker_snapshot[0] if worker_snapshot is not None else None

    with SQLiteTaskRepository(configuration.database_path) as repository:
        _attach_task_terminal_notifications(repository, configured_path)

        def pending_snapshot() -> tuple[str | None, str | None]:
            # Select a pending pin before registering; the repository still claims
            # only the exact registered pin, and the handler validates publication,
            # digest, schema and current execution authority before any effect.
            # A Task-admitted run owns its pin, so an older queued Task is just as
            # legitimate as a legacy Job and must not be hidden behind today's
            # (possibly unhealthy) Active revision.
            from mediaflow.domain.task_scheduling import TaskQueueState

            with repository._lock:
                row = repository._connection.execute(
                    "SELECT tasks.configuration_snapshot_id, "
                    "tasks.configuration_snapshot_digest "
                    "FROM task_scheduling JOIN tasks "
                    "ON tasks.task_id=task_scheduling.task_id "
                    "WHERE task_scheduling.queue_state IN (?, ?) "
                    "AND tasks.status='pending' "
                    "ORDER BY COALESCE(task_scheduling.queue_eligible_at, "
                    "task_scheduling.created_at), task_scheduling.created_at, "
                    "task_scheduling.task_id LIMIT 1",
                    (TaskQueueState.QUEUED.value, TaskQueueState.CLAIMED.value),
                ).fetchone()
            if row is not None:
                return row["configuration_snapshot_id"], row["configuration_snapshot_digest"]
            try:
                return _managed_snapshot_reference(configured_path) or (None, None)
            except Exception:
                # Current Active does not authorize previously admitted transfers;
                # their independent consumers reconstruct their own durable pins.
                return (None, None)

        with _media_discovery_service_context(
            configuration, configured_path, repository
        ) as discovery_service:
            with _manual_organize_service_context(
                configuration, configured_path, repository
            ) as execution_service:
                with _files_transfer_worker_context(
                    configuration, configured_path, repository
                ) as files_transfer_worker:
                    register_resident_process(
                        runtime,
                        "worker",
                        instance_id,
                        heartbeat_interval_seconds=5.0,
                        snapshot_id=resident_id,
                    )
                    # The resident Worker records its own presence through the same
                    # heartbeat the resident registry reads, so a slow provider call
                    # or a long claim never makes the deployment look stopped.
                    worker_service = ResidentProcessingWorker(
                        repository,
                        configuration_snapshot_resolver=pending_snapshot,
                        runtime_schema_version=SCHEMA_VERSION,
                        files_transfer_worker=files_transfer_worker,
                    )
                    from mediaflow.application.manual_task_engine import (
                        ManualTaskEngineWorker,
                    )
                    from mediaflow.application.task_scheduling import TaskSchedulingService

                    def current_scheduling_capacity() -> int:
                        # The resident Worker re-resolves the published allowance
                        # for each admission/re-entry, so a new System Settings
                        # value applies to new work without a restart.
                        resolved = _resolve_resident_configuration(configured_path)
                        return getattr(
                            resolved or configuration,
                            "automation_maximum_active_jobs",
                            100,
                        )

                    scheduling_service = TaskSchedulingService(
                        repository,
                        capacity=current_scheduling_capacity,
                        locks=repository,
                    )
                    manual_task_worker = ManualTaskEngineWorker(
                        repository,
                        scheduling_service,
                        discovery_service,
                        execution_service,
                        worker_id=worker_service.worker_id,
                    )
                    manual_task_worker.set_automatic_runner(
                        _automatic_task_runner(repository, configured_path, scheduling_service)
                    )
                    worker_service.set_manual_task_worker(manual_task_worker)
                    poll = getattr(configuration, "worker_poll_seconds", default_poll)
                    # Engine settings adoption: the Worker consumes
                    # ``automation.workerPollSeconds`` from the current Active.
                    cadence_resolver, cadence_reporter = resident_cadence_adoption(
                        runtime,
                        "worker",
                        instance_id,
                        field_path="automation.workerPollSeconds",
                        published_resolver=_resident_published_cadence_resolver(
                            configured_path, "worker"
                        ),
                    )
                    cadence_adoption = {
                        "cadence_resolver": cadence_resolver,
                        "adoption_reporter": cadence_reporter,
                    }
                    original_heartbeat = worker_service.heartbeat

                    def heartbeat(now=None) -> bool:
                        kept = original_heartbeat(now)
                        _resident_worker_heartbeat(runtime, instance_id)
                        return kept

                    worker_service.heartbeat = heartbeat
                    files_transfer_worker.set_worker_heartbeat(heartbeat)
                    # Every other runner sharing this loop keeps the same
                    # wrapped liveness evidence (processing-Worker row plus
                    # resident-presence row) fresh across its own long
                    # claim, exactly like the Files transfer consumer.
                    manual_task_worker.set_worker_heartbeat(heartbeat)

                    def step(loop: ResidentLoop) -> int:
                        # A fresh consumer owns no registration row yet, so a
                        # heartbeat can only fail before the first lawful
                        # registration.  Register through the same snapshot
                        # resolver/supported-command boundary first; otherwise a
                        # newly started Worker would wait forever and never
                        # reach the consumer that claims admitted work.
                        if not worker_service.registered:
                            worker_service.ensure_registration()
                        if not worker_service.heartbeat():
                            raise RuntimeError("worker registration unavailable")
                        worked = worker_service.run_next() is not None
                        if worked:
                            loop.clear_waiting()
                        else:
                            current = _resolve_resident_configuration(configured_path)
                            if current is None:
                                loop.note(
                                    "unconfigured",
                                    "waiting for published business configuration",
                                )
                            else:
                                loop.clear_waiting()
                        return int(worked)

                    loop = ResidentLoop(
                        runtime,
                        "worker",
                        instance_id,
                        heartbeat_interval_seconds=5.0,
                        poll_seconds=poll,
                        stdout=stdout,
                        step=step,
                        describe=_resident_failure_reason,
                        **cadence_adoption,
                    )
                    try:
                        processed = _run_resident(
                            lambda stop: loop.run(stop, lambda seconds: _wait(stop, seconds))
                        )
                    finally:
                        try:
                            worker_service.stop()
                        except Exception:
                            pass
                    stdout.write(f"Worker stopped; processed={processed}\n")
                    return 0


def _resident_worker_heartbeat(runtime, instance_id) -> None:
    """Refresh the resident presence row, tolerating a transient database fault."""

    try:
        runtime.service.heartbeat(instance_id)
    except Exception:
        return


def _run_scheduler(
    configuration,
    configured_path: str | None,
    *,
    stdout: TextIO,
) -> int:
    """Run the resident Scheduler from deployment-owned authority alone.

    The Scheduler owns exactly one job: decide whether an eligible occurrence
    is due *right now* and, if so, issue it pinned to the current valid Active
    snapshot.  Everything else is configuration state, so this process needs no
    business configuration at all to start.

    Its correctness properties are preserved rather than reimplemented:
    ``IntervalScheduler`` remains the single authority for occurrence identity,
    idempotency, scope, capacity and duplicate protection, and the existing
    configuration-resolver seam is what lets it re-read the current Active on
    every tick instead of binding to whatever existed at startup.
    """

    from mediaflow.application.resident_runtime import (
        ResidentLoop,
        build_resident_runtime,
        register_resident_process,
        resident_cadence_adoption,
        resident_instance_id,
    )

    heartbeat_seconds, default_poll, _ = _resident_infrastructure_defaults()
    runtime = build_resident_runtime(configuration.database_path)
    snapshot = _resident_snapshot_reference(configured_path)
    instance_id = resident_instance_id("scheduler")

    current = _current_runtime_configuration(configured_path)
    poll = current.scheduler_poll_seconds if current is not None else default_poll
    maximum_active_jobs = current.automation_maximum_active_jobs if current is not None else 100

    with SQLiteTaskRepository(configuration.database_path) as repository:

        def build_service(resolved: RuntimeConfiguration | None) -> IntervalScheduler:
            """Build one scheduler bound to the exact configuration it admits from.

            When no valid Active exists the scheduler still runs, but with no
            definitions and no snapshot identity.  That makes "emit nothing"
            the only reachable outcome, which is precisely the required
            behaviour when Active is absent or unusable.
            """

            from mediaflow.application.task_scheduling import TaskSchedulingService

            return IntervalScheduler(
                repository,
                # Notification targets are resolved by the resident Notification
                # Worker at its own claim boundary.  The Scheduler only writes
                # deterministic durable deliveries for enabled Webhooks, so an
                # unavailable secret must never stop it emitting a due
                # occurrence.
                NotificationPublisher(
                    repository, getattr(resolved, "webhooks", ()) if resolved else ()
                ),
                execution_authority=_scheduler_execution_authority(
                    resolved or configuration, repository
                ),
                maximum_active_jobs=(
                    getattr(resolved, "automation_maximum_active_jobs", maximum_active_jobs)
                    if resolved
                    else maximum_active_jobs
                ),
                scheduling_service=TaskSchedulingService(
                    repository,
                    capacity=(
                        getattr(resolved, "automation_maximum_active_jobs", maximum_active_jobs)
                        if resolved
                        else maximum_active_jobs
                    ),
                    locks=repository,
                ),
                configuration_snapshot_id=(
                    getattr(resolved, "configuration_snapshot_id", None) if resolved else None
                ),
                configuration_snapshot_digest=(
                    getattr(resolved, "configuration_snapshot_digest", None) if resolved else None
                ),
                automation_task_definitions=(
                    getattr(resolved, "automation_task_definitions", ()) if resolved else ()
                ),
                configuration_snapshot_version=(
                    getattr(resolved, "configuration_snapshot_version", None) if resolved else None
                ),
                configuration_snapshot_resolver=lambda: _scheduler_snapshot_from_runtime(resolved),
            )

        register_resident_process(
            runtime,
            "scheduler",
            instance_id,
            heartbeat_interval_seconds=5.0,
            snapshot_id=snapshot[0] if snapshot is not None else None,
        )

        def step(loop: ResidentLoop) -> int:
            """Re-resolve the current Active, then tick under that exact identity.

            Re-resolving per tick is what makes a running Scheduler adopt an
            eligible publication with no restart, and what keeps it from reusing
            stale definitions while Active is unavailable: a failed resolution
            yields no definitions and no pin, so no occurrence is issued or
            advanced.
            """

            resolved = _resolve_resident_configuration(configured_path)
            reason, detail = _scheduler_waiting_reason(resolved)
            loop.note(reason, detail)
            if resolved is None:
                return 0
            return len(build_service(resolved).tick())

        # Engine settings adoption: the Scheduler consumes
        # ``automation.schedulerPollSeconds`` as its due-check cadence.  Schedule
        # resolution stays separate — a poll change never alters a definition's
        # interval, Cron expression or timezone.
        cadence_resolver, cadence_reporter = resident_cadence_adoption(
            runtime,
            "scheduler",
            instance_id,
            field_path="automation.schedulerPollSeconds",
            published_resolver=_resident_published_cadence_resolver(configured_path, "scheduler"),
        )
        loop = ResidentLoop(
            runtime,
            "scheduler",
            instance_id,
            heartbeat_interval_seconds=5.0,
            poll_seconds=poll,
            stdout=stdout,
            step=step,
            describe=_resident_failure_reason,
            cadence_resolver=cadence_resolver,
            adoption_reporter=cadence_reporter,
        )
        emitted = _run_resident(lambda stop: loop.run(stop, lambda seconds: _wait(stop, seconds)))
        stdout.write(f"Scheduler stopped; emitted={emitted}\n")
        return 0


def _run_notification_worker(
    configuration,
    configured_path: str | None,
    *,
    stdout: TextIO,
) -> int:
    """Run the resident Notification Worker from deployment-owned authority.

    The worker resolves its delivery configuration at every claim, so it can
    start before any Webhook exists and adopt a later valid publication without
    a restart, while still refusing to claim a delivery whose durable target it
    cannot lawfully deliver to.
    """

    from mediaflow.application.resident_runtime import (
        ResidentLoop,
        build_resident_runtime,
        register_resident_process,
        resident_instance_id,
    )
    from mediaflow.infrastructure.webhook import UrllibWebhookTransport

    _, default_poll, _ = _resident_infrastructure_defaults()
    runtime = build_resident_runtime(configuration.database_path)
    snapshot = _resident_snapshot_reference(configured_path)
    instance_id = resident_instance_id("notification-worker")

    current = _current_runtime_configuration(configured_path)
    poll = current.notification_poll_seconds if current is not None else default_poll
    lease = (
        current.notification_delivery_lease_seconds
        if current is not None
        else _resident_infrastructure_defaults()[0]
    )

    def resolve_targets() -> dict:
        """Resolve the current valid deliverable targets, or fail closed.

        A missing secret is deliberately a resolution failure rather than a
        silently skipped target: a delivery must never be claimed against a
        target whose signing secret is absent, because the request could not be
        signed and reporting success afterwards would be false.
        """

        resolved = _resolve_resident_configuration(configured_path)
        if resolved is None:
            return {}
        try:
            return resolved.resolve_webhook_targets()
        except ValueError as error:
            raise ResidentConfigurationUnavailable("secret_unavailable") from error

    with SQLiteTaskRepository(configuration.database_path) as repository:
        delivery_worker = NotificationWorker(
            repository,
            resolve_targets,
            UrllibWebhookTransport(),
            delivery_lease_seconds=lease,
        )
        register_resident_process(
            runtime,
            "notification-worker",
            instance_id,
            heartbeat_interval_seconds=5.0,
            snapshot_id=snapshot[0] if snapshot is not None else None,
        )

        def step(loop: ResidentLoop) -> int:
            try:
                targets = delivery_worker.resolve_targets()
            except ResidentConfigurationUnavailable as error:
                loop.note(error.reason, str(error))
                return 0
            if not targets:
                loop.note(
                    ResidentServiceWaiting.UNCONFIGURED.value,
                    "the Active configuration declares no enabled Webhook target",
                )
                return 0
            loop.clear_waiting()
            return 0 if delivery_worker.run_next() is None else 1

        loop = ResidentLoop(
            runtime,
            "notification-worker",
            instance_id,
            heartbeat_interval_seconds=5.0,
            poll_seconds=poll,
            stdout=stdout,
            step=step,
            describe=_resident_failure_reason,
        )
        processed = _run_resident(lambda stop: loop.run(stop, lambda seconds: _wait(stop, seconds)))
        stdout.write(f"Notification worker stopped; processed={processed}\n")
        return 0


def _api_resident_heartbeat(runtime, instance_id: str):
    """Keep the API's own resident registration fresh while it serves.

    The API has no work loop, so it refreshes its heartbeat on a timer in a
    daemon thread.  A heartbeat fault is swallowed on purpose: the API must stay
    reachable for configuration recovery even when the shared database is
    briefly unhappy, and a later beat repairs the state.  Killing the API would
    achieve nothing and lose the recovery surface entirely.
    """

    class _Heartbeat:
        def __init__(self) -> None:
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, daemon=True)

        def _run(self) -> None:
            while not self._stop.wait(5.0):
                try:
                    runtime.service.heartbeat(instance_id)
                except Exception:
                    continue

        def start(self):
            self._thread.start()
            return self

        def stop(self) -> None:
            self._stop.set()
            self._thread.join(timeout=6.0)

    return _Heartbeat()


_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


def _valid_api_host(host: str) -> bool:
    if (
        not host
        or len(host) > 253
        or host != host.strip()
        or any(value in host for value in "/\\\x00")
    ):
        return False
    if host.casefold() == "localhost":
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        labels = host[:-1].split(".") if host.endswith(".") else host.split(".")
        return bool(labels) and all(_HOST_LABEL.fullmatch(label) for label in labels)


def _api_endpoint() -> tuple[str, int, int]:
    host = os.environ.get("MEDIAFLOW_API_HOST", "0.0.0.0")
    if not _valid_api_host(host):
        raise ValueError("MEDIAFLOW_API_HOST must be a valid hostname or IP address")

    def bounded(name: str, default: int, minimum: int, maximum: int) -> int:
        raw = os.environ.get(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError as error:
            raise ValueError(f"{name} must be an integer") from error
        if isinstance(value, bool) or not minimum <= value <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
        return value

    return (
        host,
        bounded("MEDIAFLOW_API_PORT", 8080, 1, 65535),
        bounded("MEDIAFLOW_API_THREADS", 4, 1, 64),
    )


def _serve_api(
    configuration, configured_path: str | None, *, stdout: TextIO, stderr: TextIO
) -> None:
    """Serve the shared WSGI application through the production Waitress adapter."""

    host, port, threads = _api_endpoint()
    stderr.write(
        "WARNING: production WSGI serves HTTP without TLS; bind the container port "
        "to a trusted LAN or HTTPS reverse proxy\n"
    )
    from mediaflow.production_wsgi import serve as run_server

    bootstrap_document = _configuration_document(configured_path)
    from mediaflow.infrastructure.configuration_snapshot import (
        build_configuration_snapshot,
    )
    from mediaflow.interfaces.service_api import MediaFlowApi

    management_only = isinstance(configuration, ManagementBootstrapConfiguration)
    # The API registers its own durable presence for the same reason the other
    # three services do: "the process is running" must be an observed fact, not
    # an inference from a static configuration file.
    from mediaflow.application.resident_runtime import (
        build_resident_runtime,
        register_resident_process,
        resident_instance_id,
    )

    runtime = build_resident_runtime(configuration.database_path)
    active_reference = _managed_snapshot_reference(configured_path)
    instance_id = resident_instance_id("api")
    with (
        SQLiteTaskRepository(configuration.database_path) as repository,
        SQLiteConfigurationRepository(configuration.database_path) as configuration_repository,
    ):
        register_resident_process(
            runtime,
            "api",
            instance_id,
            heartbeat_interval_seconds=5.0,
            snapshot_id=active_reference[0] if active_reference is not None else None,
        )
        resident_services = ResidentServiceService(
            repository, runtime_schema_version=SCHEMA_VERSION
        )
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=configuration.database_path,
            bootstrap_document=bootstrap_document,
            management_only=management_only,
        )
        app = MediaFlowApi(
            repository,
            account_service=AccountService(repository),
            maximum_active_jobs=getattr(configuration, "automation_maximum_active_jobs", 100),
            system_status=(
                None if management_only else build_configuration_snapshot(configuration)
            ),
            metadata_policies=getattr(
                getattr(configuration, "strategy", None), "metadata_policies", ()
            ),
            configuration_service=configuration_service,
            configuration_snapshot_id=getattr(configuration, "configuration_snapshot_id", None),
            configuration_snapshot_digest=getattr(
                configuration, "configuration_snapshot_digest", None
            ),
            bootstrap_document=bootstrap_document,
            management_only=management_only,
            metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                metadata_provider_registry_from_environment
            ),
            resident_services=resident_services,
        )
        stdout.write(f"MediaFlow production API listening on {host}:{port}\n")
        stdout.flush()
        heartbeat = _api_resident_heartbeat(runtime, instance_id)
        heartbeat.start()
        try:
            run_server(app, host=host, port=port, threads=threads)
        finally:
            heartbeat.stop()
            runtime.service.stop(instance_id)


@contextmanager
def _manual_organize_service_context(configuration, configured_path: str | None, repository):
    """Yield the Task engine's admitted-manual-Organize application service.

    The service reconstructs the reviewed Preview, the pinned runtime snapshot
    and the required Storage adapters from durable state, so it never shares
    in-memory authority with the API request that admitted the work.  Every
    runtime resource it opens is closed with the surrounding Worker lifetime.
    """

    bootstrap_document = _configuration_document(configured_path)
    management_only = isinstance(configuration, ManagementBootstrapConfiguration)
    with SQLiteConfigurationRepository(configuration.database_path) as configuration_repository:
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=configuration.database_path,
            bootstrap_document=bootstrap_document,
            management_only=management_only,
        )
        intents = ManualOrganizeIntentService(repository, configuration_service)
        previews = ManualOrganizePreviewService(
            repository,
            intents,
            configuration_service=configuration_service,
            metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                metadata_provider_registry_from_environment
            ),
        )
        execution = ManualOrganizeExecutionService(
            repository,
            previews,
            intents,
            checkpoint_service=ProcessingCheckpointService(repository),
        )
        yield execution


@contextmanager
def _media_discovery_service_context(configuration, configured_path: str | None, repository):
    """Yield the Task engine's admitted bounded-discovery application service.

    The service reconstructs the pinned Active revision, the runtime snapshot and
    the configured Storage adapters from durable state, so it never shares
    in-memory authority with the API request that admitted the discovery.  The
    admitting request performs zero Storage enumeration; this Worker context is
    the only place a discovery becomes bounded Storage observations, and it
    remains metadata-only with zero mutation.
    """

    from mediaflow.application.media_discovery import MediaDiscoveryService

    bootstrap_document = _configuration_document(configured_path)
    management_only = isinstance(configuration, ManagementBootstrapConfiguration)
    with SQLiteConfigurationRepository(configuration.database_path) as configuration_repository:
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=configuration.database_path,
            bootstrap_document=bootstrap_document,
            management_only=management_only,
        )
        intents = ManualOrganizeIntentService(repository, configuration_service)
        previews = ManualOrganizePreviewService(
            repository,
            intents,
            configuration_service=configuration_service,
            metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                metadata_provider_registry_from_environment
            ),
        )
        discovery = MediaDiscoveryService(
            repository,
            intents,
            configuration_service=configuration_service,
            preview_service=previews,
        )
        yield discovery


@contextmanager
def _files_transfer_worker_context(configuration, configured_path: str | None, repository):
    """Yield the resident Worker's admitted Files Copy/Move transfer runner.

    The runner reconstructs the pinned Active revision, the runtime snapshot
    and the configured Storage adapters from durable state, so it never shares
    in-memory authority with the API request that admitted the transfer.  The
    admitting request performs zero Storage mutation; this Worker context is
    the only place an admitted transfer becomes ``OrganizerExecutor`` work.
    """

    from mediaflow.application.direct_file_commands import DirectFileCommandService
    from mediaflow.application.direct_file_transfers import DirectFileTransferService
    from mediaflow.application.files_transfer_worker import FilesTransferWorker
    from mediaflow.domain.direct_files import LibraryKind

    def reconstruct(revision_id: str, revision_digest: str, *, media_library: bool = False):
        """Rebuild the exact persisted revision a claimed transfer pinned.

        A resident Worker may outlive an activation, so it must execute each
        claimed transfer under that transfer's own immutable revision rather
        than under whatever Active snapshot the process started with.  A
        revision this process cannot lawfully reconstruct returns ``None`` and
        leaves the transfer claimable instead of consuming it as a failure.

        ``media_library`` selects the library kind of the rebuilt runtime: one
        kind's reconstructor never returns a service of the other kind, so the
        persisted kind of a claimed transfer is always honored.
        """

        with SQLiteConfigurationRepository(configuration.database_path) as pinned_repository:
            pinned = pinned_repository.get_revision(revision_id)
        if pinned is None:
            return None

        if pinned.status is ManagedConfigurationStatus.DRAFT:
            return None
        if revision_digest and pinned.digest != revision_digest:
            return None
        try:
            pinned_runtime = _configuration(
                configured_path,
                snapshot_id=pinned.revision_id,
                snapshot_digest=pinned.digest,
            )
        except Exception:
            return None
        published = replace(
            pinned,
            status=ManagedConfigurationStatus.ACTIVE,
            activated_at=pinned.activated_at or datetime.now(UTC),
        )
        return DirectFileCommandService(
            active_revision=published,
            runtime_configuration=pinned_runtime,
            task_repository=repository,
            storage_adapters=None,
            revision_rebuilder=reconstruct,
            library_kind=(LibraryKind.MEDIA if media_library else LibraryKind.RESOURCE),
        )

    resource_command = direct_command_task_command(FILES_TRANSFER_TASK_COMMAND, media_library=False)
    media_command = direct_command_task_command(FILES_TRANSFER_TASK_COMMAND, media_library=True)
    resource_delete_command = direct_command_task_command(
        FILES_DELETE_TASK_COMMAND, media_library=False
    )
    media_delete_command = direct_command_task_command(
        FILES_DELETE_TASK_COMMAND, media_library=True
    )

    def service_for(command: str, transfer):
        """Build one attempt boundary from the claimed transfer's durable pin."""

        media_library = command in {media_command, media_delete_command}
        if command not in {
            resource_command,
            media_command,
            resource_delete_command,
            media_delete_command,
        }:
            return None
        direct = reconstruct(
            transfer.configuration_snapshot_id,
            transfer.configuration_snapshot_digest,
            media_library=media_library,
        )
        if direct is None:
            return None
        return DirectFileTransferService(direct_files=direct)

    # The resident consumer exists before the first Active configuration and
    # throughout later Active outages.  It opens no provider here: each claim
    # is reconstructed from its own immutable revision/digest after ownership
    # has been acquired, and all Storage adapters remain attempt-scoped.
    yield FilesTransferWorker(
        None,
        repository,
        service_factory=service_for,
        supported_commands=(
            resource_command,
            media_command,
            resource_delete_command,
            media_delete_command,
        ),
    )


class _NullFilesTransferWorker:
    """A no-op transfer runner for Workers without an Active configuration."""

    @staticmethod
    def run_next():
        return None


def _run_resident(run: Callable[[Callable[[], bool]], int]) -> int:
    stopped = threading.Event()
    previous = {}

    def request_stop(_signum, _frame) -> None:
        stopped.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, request_stop)
    try:
        return run(stopped.is_set)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _wait(stop: Callable[[], bool], seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while not stop():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        threading.Event().wait(min(remaining, 0.25))


def _managed_scheduler_configuration(
    path: str | None,
) -> SchedulerConfigurationSnapshot | None:
    """Resolve schedule definitions and pin from one current runtime revision.

    ``None`` means "no managed Active exists to admit from", which is the normal
    pre-activation state.  The Scheduler treats that as an empty definition set
    and emits nothing, rather than reusing whatever the JSON bootstrap happened
    to contain.
    """

    # The resolver seam is the *managed* one: a resident Scheduler pins every
    # occurrence it issues to published authority, and a legacy JSON bootstrap
    # has no identity to pin to.  It therefore yields no snapshot here, which
    # makes the resident path fail closed while the one-shot commands below
    # still support the pre-activation compatibility runtime.
    configuration = _current_managed_runtime_configuration(path)
    return _scheduler_snapshot_from_runtime(configuration)


def _scheduler_snapshot_from_runtime(configuration) -> SchedulerConfigurationSnapshot | None:
    """Pin occurrence and notification publication to the same resolved runtime."""

    if configuration is None or not getattr(configuration, "configuration_snapshot_id", None):
        return None
    return SchedulerConfigurationSnapshot(
        configuration.configuration_snapshot_id,
        configuration.configuration_snapshot_digest or "",
        configuration.automation_maximum_active_jobs,
        configuration.automation_task_definitions,
        configuration.configuration_snapshot_version,
        tuple(item.library_id for item in configuration.resource_libraries),
        tuple(item.library_id for item in configuration.resource_libraries if item.enabled),
    )


SERVICE_NAMES = ("api", "worker", "scheduler", "notification-worker")


def _service_runner(
    service: str,
    configuration,
    configured_path: str,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    if service == "api":
        _serve_api(configuration, configured_path, stdout=stdout, stderr=stderr)
        return 0
    if service == "worker":
        return _run_worker(configuration, configured_path, stdout=stdout)
    if service == "scheduler":
        return _run_scheduler(configuration, configured_path, stdout=stdout)
    return _run_notification_worker(configuration, configured_path, stdout=stdout)


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    parser = argparse.ArgumentParser(
        prog="python -m mediaflow.resident_entry",
        description=__doc__,
    )
    parser.add_argument("service", choices=SERVICE_NAMES)
    arguments = parser.parse_args(argv)

    env_file = os.environ.get("MEDIAFLOW_ENV_FILE")
    if env_file:
        try:
            os.environ.update(load_environment_file(env_file))
        except ValueError as error:
            error_output.write(f"mediaflow service error: {error}\n")
            return 1
    configured_path = os.environ.get("MEDIAFLOW_CONFIG", "/config/mediaflow.json")
    data_dir = os.environ.get("MEDIAFLOW_DATA_DIR", "/data")
    errors = container_preflight_errors(
        configured_path,
        data_dir,
        service=arguments.service,
    )
    if errors:
        error_output.write("MediaFlow container preflight failed:\n")
        for error in errors:
            error_output.write(f"- {error}\n")
        return 1
    try:
        document = _configuration_document(configured_path)
        reject_retired_configuration_input(document)
        database_path = _bootstrap_database_path(document)
    except (OSError, ValueError, RuntimeError) as error:
        error_output.write(f"mediaflow service error: {error}\n")
        return 2
    # The shared lease precedes every repository: resolving the API's Active
    # opens the configuration repository, which creates tables and markers on
    # an empty file.  An offline recovery holds the exclusive lease of an empty
    # destination, so a service started meanwhile must leave that target empty.
    try:
        lease = RuntimeDatabaseLease(database_path, RuntimeLeaseMode.SHARED).acquire(
            create_parent=True
        )
    except RuntimeLeaseUnavailable:
        error_output.write(
            "mediaflow service error: the runtime database is in use; an offline recovery or "
            f"another MediaFlow process holds the maintenance lease. Finish it, then start the "
            f"{arguments.service} service again. No database file was created or modified.\n"
        )
        return 2
    except (OSError, ValueError, RuntimeError) as error:
        error_output.write(f"mediaflow service error: {error}\n")
        return 2
    try:
        from mediaflow.infrastructure.sqlite_applicability import (
            DatabaseApplicabilityError,
            assert_supported_database,
        )
        from mediaflow.infrastructure.sqlite_configuration_schema import (
            CONFIGURATION_SCHEMA_VERSION,
        )

        # The same read-only applicability decision every repository repeats on
        # its own connection, run before any runtime store is opened so an
        # unsupported previous store (for example configuration schema 11 from
        # an earlier build) is refused without creating tables or markers.
        assert_supported_database(
            database_path,
            current_runtime_version=SCHEMA_VERSION,
            current_configuration_version=CONFIGURATION_SCHEMA_VERSION,
        )
    except DatabaseApplicabilityError as error:
        error_output.write(f"mediaflow service error: {error}\n")
        return 2
    except (OSError, ValueError, RuntimeError) as error:
        error_output.write(f"mediaflow service error: {error}\n")
        return 2
    try:
        if arguments.service == "api":
            try:
                configuration = _configuration(configured_path)
            except RuntimeSnapshotUnavailable:
                configuration = load_management_bootstrap(document)
        else:
            configuration = load_management_bootstrap(document)
        return _service_runner(
            arguments.service,
            configuration,
            configured_path,
            stdout=output,
            stderr=error_output,
        )
    except (OSError, ValueError, LookupError, RuntimeError) as error:
        error_output.write(f"mediaflow service error: {error}\n")
        return 2
    finally:
        lease.close()


if __name__ == "__main__":
    raise SystemExit(main())
