from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mediaflow.domain.automation import AutomationCommand
from mediaflow.domain.execution_authorization import (
    ExecutionAuthorization,
    ExecutionAuthorizationAudit,
    ExecutionAuthorizationRepository,
    ExecutionAuthorizationStatus,
)


@dataclass(frozen=True)
class IssuedExecutionAuthorization:
    authorization: ExecutionAuthorization
    token: str


@dataclass(frozen=True)
class ScheduledOrganizeSubmission:
    """The durable Task one consumed remote ticket admitted.

    The Task is the run's only identity: it is queued in the shared scheduling
    kernel with its own pin, limit and principal, and the resident Task engine
    owns its whole machine life.  No Job row exists for it.
    """

    task: object
    state: object
    authorization: ExecutionAuthorization


class ExecutionAuthorizationService:
    def __init__(
        self,
        repository: ExecutionAuthorizationRepository,
        *,
        maximum_ttl_seconds: int = 900,
        maximum_active_jobs: int = 100,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
    ) -> None:
        if (configuration_snapshot_id is None) != (configuration_snapshot_digest is None):
            raise ValueError("Job configuration snapshot ID and digest must be provided together")
        if maximum_ttl_seconds < 1:
            raise ValueError("maximum execution authorization TTL must be positive")
        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or maximum_active_jobs < 1
            or maximum_active_jobs > 10_000
        ):
            raise ValueError("maximum active Jobs must be between 1 and 10000")
        self._repository = repository
        self._maximum_ttl_seconds = maximum_ttl_seconds
        self._maximum_active_jobs = maximum_active_jobs
        self._clock = clock
        self._token_factory = token_factory
        self._configuration_snapshot_id = configuration_snapshot_id
        self._configuration_snapshot_digest = configuration_snapshot_digest

    def bind_configuration_snapshot(self, snapshot_id: str | None, digest: str | None) -> None:
        if (snapshot_id is None) != (digest is None):
            raise ValueError("Job configuration snapshot ID and digest must be provided together")
        self._configuration_snapshot_id = snapshot_id
        self._configuration_snapshot_digest = digest

    def issue(
        self,
        *,
        ttl_seconds: int,
        max_items: int,
        actor: str | None = None,
        note: str | None = None,
    ) -> IssuedExecutionAuthorization:
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
            raise ValueError("execution authorization TTL must be an integer")
        if ttl_seconds < 1 or ttl_seconds > self._maximum_ttl_seconds:
            raise ValueError(
                f"execution authorization TTL must be between 1 and "
                f"{self._maximum_ttl_seconds} seconds"
            )
        if isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 1:
            raise ValueError("execution authorization max items must be a positive integer")
        now = self._clock()
        token = self._token_factory()
        if not token:
            raise ValueError("execution authorization token generator returned an empty token")
        value = ExecutionAuthorization(
            str(uuid4()),
            self.digest(token),
            ExecutionAuthorizationStatus.ACTIVE,
            now,
            now + timedelta(seconds=ttl_seconds),
            max_items,
            actor,
            note,
        )
        self._repository.create_execution_authorization(
            value,
            ExecutionAuthorizationAudit(
                str(uuid4()), value.authorization_id, "issued", now, actor=actor
            ),
        )
        return IssuedExecutionAuthorization(value, token)

    def submit_organize(self, token: str, *, limit: int) -> ScheduledOrganizeSubmission:
        """Consume one remote ticket into one admitted organizing Task.

        Slice 47 RO-2: the remote organize submission is the same shared Task
        work every other entrance runs.  The exact ticket validation, the shared
        Task scheduling capacity and the Task/queue/audit commit are one atomic
        transaction; no Job row is written and no second queue exists.  The
        returned submission names the durable Task identity and its queued
        scheduling state so the caller can read the run back by that identity.
        """

        from mediaflow.application.task_scheduling import build_scheduled_task_admission
        from mediaflow.domain.automation import AutomationQueueFull
        from mediaflow.domain.task_persistence import RunDisplayContext
        from mediaflow.domain.task_scheduling import TaskQueueFull, TaskTrigger

        if not token:
            raise ValueError("execution authorization token is required")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("remote organize limit must be a positive integer")
        now = self._clock()
        task, state = build_scheduled_task_admission(
            AutomationCommand.ORGANIZE.value,
            execute_authorized=True,
            trigger=TaskTrigger.MANUAL,
            principal="remote-execution",
            item_limit=limit,
            configuration_snapshot_id=self._configuration_snapshot_id,
            configuration_snapshot_digest=self._configuration_snapshot_digest,
            require_configuration_snapshot=self._configuration_snapshot_id is not None,
            now=now,
        )
        display = RunDisplayContext(
            source_scope=None,
            origin_kind="remote-organize",
        )
        try:
            authorization = self._repository.consume_execution_authorization_task(
                self.digest(token),
                task,
                state,
                now,
                ExecutionAuthorizationAudit(
                    str(uuid4()), "resolved-by-digest", "consumed", now, task_id=task.task_id
                ),
                self._maximum_active_jobs,
                display=display,
            )
        except TaskQueueFull as error:
            # The shared queue-full boundary keeps its established transport
            # error type; nothing was written and no authority was consumed.
            raise AutomationQueueFull(str(error)) from error
        return ScheduledOrganizeSubmission(
            task=task,
            state=state,
            authorization=authorization,
        )

    def list(self) -> tuple[ExecutionAuthorization, ...]:
        self._repository.expire_execution_authorizations(self._clock())
        return self._repository.list_execution_authorizations()

    def get(self, authorization_id: str) -> ExecutionAuthorization | None:
        self._repository.expire_execution_authorizations(self._clock())
        return self._repository.get_execution_authorization(authorization_id)

    def revoke(self, authorization_id: str, *, actor: str | None = None):
        now = self._clock()
        return self._repository.revoke_execution_authorization(
            authorization_id,
            now,
            ExecutionAuthorizationAudit(
                str(uuid4()), authorization_id, "revoked", now, actor=actor
            ),
        )

    @staticmethod
    def digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
