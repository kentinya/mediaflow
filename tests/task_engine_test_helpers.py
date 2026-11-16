"""Test-only runners for the current Task kernel.

The retired standalone discovery/execution Worker modules are gone from
production.  These helpers drive the same current application services through
the retained Task scheduling claim, so legacy test fixtures that admitted work
before this Task still exercise real production execution rather than a
reintroduced parallel queue.
"""

from __future__ import annotations

import secrets
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
from mediaflow.application.task_scheduling import TaskSchedulingService
from mediaflow.domain.manual_execution import ManualExecution, ManualExecutionStatus
from mediaflow.domain.media_discovery import (
    DiscoveryError,
)
from mediaflow.domain.task_scheduling import (
    TaskMachineStage,
    TaskQueueState,
    TaskSchedulingState,
    TaskTrigger,
)
from mediaflow.infrastructure.sqlite_runtime import (
    _TASK_SCHEDULING_INSERT,
    SCHEMA_VERSION,
)

_CLAIMABLE_DISCOVERY_STATUSES = frozenset({"queued", "running", "waiting_stability", "analyzing"})


def claim_and_run(
    service,
    *,
    worker_id: str,
    claim_token: str,
    heartbeat=None,
    parent_heartbeat=None,
    analysis_checkpoint=None,
):
    """Claim one explicit discovery ID and advance it through ``run_claimed``."""

    repository = service.repository
    now = service._clock()
    candidates = [
        value
        for value in repository.list_media_discoveries(limit=500)
        if value.status.value in _CLAIMABLE_DISCOVERY_STATUSES
        and (value.next_observation_at is None or value.next_observation_at <= now)
    ]
    if not candidates:
        return None
    discovery = candidates[-1]
    claimed = repository.claim_media_discovery(
        discovery.discovery_id,
        now,
        worker_id=worker_id,
        claim_token=claim_token,
        lease_seconds=300,
    )
    if claimed is None:
        return None
    beat = (lambda _discovery_id: heartbeat(claimed.discovery_id)) if heartbeat else None
    return service.run_claimed(
        claimed.discovery_id,
        worker_id=worker_id,
        claim_token=claim_token,
        heartbeat=beat,
        parent_heartbeat=parent_heartbeat,
        analysis_checkpoint=analysis_checkpoint,
    )


class MediaDiscoveryWorker:
    """Test-only runner that claims one explicit discovery and runs it."""

    def __init__(
        self,
        service,
        *,
        lease_seconds: float = 300.0,
        clock: Callable[[], datetime] | None = None,
        worker_id: str | None = None,
        notice: Callable[[str], None] | None = None,
    ) -> None:
        self._service = service
        self._lease_seconds = lease_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._worker_id = worker_id or f"media-discovery-{secrets.token_hex(6)}"
        self._notice = notice or (lambda line: sys.stderr.write(line))
        self._parent_heartbeat = None

    def set_worker_heartbeat(self, heartbeat):
        self._parent_heartbeat = heartbeat

    @property
    def service(self):
        return self._service

    @property
    def commands(self):
        return ("media_discovery",)

    def run_next(self):
        try:
            return claim_and_run(
                self._service,
                worker_id=self._worker_id,
                claim_token=secrets.token_urlsafe(32),
                parent_heartbeat=self._parent_heartbeat,
            )
        except DiscoveryError as error:
            self._notice(str(getattr(error, "code", "media_discovery_unavailable")))
            return None
        except Exception as error:  # noqa: BLE001 - a test runner never crashes the loop
            self._notice(type(error).__name__)
            return None


class ManualOrganizeExecutionWorker:
    """Test-only runner that registers an admitted execution's Task and runs it.

    A fixture that admitted an execution before Task scheduling existed has a
    real Task row but no scheduling state.  Registering that exact Task once is
    the smallest honest bridge to the current kernel: the engine then owns the
    real claim, the exact execution fence and the actual result publication.
    """

    def __init__(
        self,
        execution_service,
        *,
        repository=None,
        lease_seconds: float = 300.0,
        clock: Callable[[], datetime] | None = None,
        worker_id: str | None = None,
        notice: Callable[[str], None] | None = None,
    ) -> None:
        self._service = execution_service
        self._repository = repository or getattr(execution_service, "_repository", None)
        self._lease_seconds = lease_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._worker_id = worker_id or f"manual-organize-{secrets.token_hex(6)}"
        self._notice = notice or (lambda line: sys.stderr.write(line))
        self._parent_heartbeat = None

    def set_worker_heartbeat(self, heartbeat):
        self._parent_heartbeat = heartbeat

    @property
    def service(self):
        return self._service

    def run_next(self) -> ManualExecution | None:
        repository = self._repository
        if repository is None:
            return None
        row = repository._connection.execute(
            "SELECT execution_id, task_id FROM manual_executions WHERE status=? "
            "ORDER BY created_at, execution_id LIMIT 1",
            (ManualExecutionStatus.ADMITTED.value,),
        ).fetchone()
        if row is None:
            return None
        execution_id = row["execution_id"]
        task_id = row["task_id"]
        now = self._clock()
        if repository.get_task_scheduling(task_id) is None:
            state = TaskSchedulingState(
                task_id,
                TaskQueueState.QUEUED,
                TaskTrigger.MANUAL,
                "legacy-test-fixture",
                None,
                now,
                now,
                machine_stage=TaskMachineStage.EXECUTION,
            )
            with repository._lock, repository._connection:
                repository._connection.execute(
                    _TASK_SCHEDULING_INSERT, repository._scheduling_values(state)
                )
                repository._connection.execute(
                    "UPDATE tasks SET status='pending', updated_at=? WHERE task_id=?",
                    (now.isoformat(), task_id),
                )
        existing_worker = repository.get_worker(self._worker_id)
        if existing_worker is None or "manual_organize" not in existing_worker.supported_commands:
            task = repository.get_task(task_id)
            commands = tuple(
                sorted(
                    {
                        "manual_organize",
                        *(existing_worker.supported_commands if existing_worker else ()),
                    }
                )
            )
            repository.register_worker(
                self._worker_id,
                "task engine test helper",
                10.0,
                commands,
                task.configuration_snapshot_id if task is not None else None,
                task.configuration_snapshot_digest if task is not None else None,
                SCHEMA_VERSION,
                now,
            )
        worker = ManualTaskEngineWorker(
            repository,
            TaskSchedulingService(repository, capacity=1000, locks=repository),
            None,
            self._service,
            clock=self._clock,
            worker_id=self._worker_id,
            notice=self._notice,
            lease_seconds=self._lease_seconds,
        )
        if self._parent_heartbeat is not None:
            worker.set_worker_heartbeat(self._parent_heartbeat)
        worker.run_next()
        after = self._service.get(execution_id)
        return None if after.status is ManualExecutionStatus.ADMITTED else after


def claim_next_discovery(repository, now, *, worker_id, claim_token, lease_seconds):
    """Claim the oldest claimable discovery by its exact durable ID."""

    candidates = [
        value
        for value in repository.list_media_discoveries(limit=500)
        if value.status.value in _CLAIMABLE_DISCOVERY_STATUSES
        and (value.next_observation_at is None or value.next_observation_at <= now)
    ]
    for value in reversed(candidates):
        claimed = repository.claim_media_discovery(
            value.discovery_id,
            now,
            worker_id=worker_id,
            claim_token=claim_token,
            lease_seconds=lease_seconds,
        )
        if claimed is not None:
            return claimed
    return None


def claim_next_execution(repository, now, *, worker_id, claim_token, lease_seconds):
    """Claim the oldest admitted execution by its exact durable ID."""

    rows = repository._connection.execute(
        "SELECT execution_id FROM manual_executions WHERE status=? "
        "ORDER BY created_at, execution_id",
        (ManualExecutionStatus.ADMITTED.value,),
    ).fetchall()
    for row in rows:
        claimed = repository.claim_manual_execution(
            row["execution_id"],
            now,
            worker_id=worker_id,
            claim_token=claim_token,
            lease_seconds=lease_seconds,
        )
        if claimed is not None:
            return claimed
    return None


def admit_organize_task(repository, *, snapshot_id, snapshot_digest, principal="tester", limit=1):
    """Admit one non-interactive organizing Task through the current kernel."""

    from mediaflow.application.task_scheduling import build_scheduled_task_admission
    from mediaflow.domain.task_persistence import RunDisplayContext

    task, state = build_scheduled_task_admission(
        "organize",
        execute_authorized=True,
        trigger=TaskTrigger.MANUAL,
        principal=principal,
        item_limit=limit,
        configuration_snapshot_id=snapshot_id,
        configuration_snapshot_digest=snapshot_digest,
        require_configuration_snapshot=snapshot_id is not None,
        now=datetime.now(UTC),
    )
    repository.admit_scheduled_task(
        task,
        state,
        capacity=1000,
        display=RunDisplayContext(source_scope=None, origin_kind="remote-organize"),
    )
    return task
