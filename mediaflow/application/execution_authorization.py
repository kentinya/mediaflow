from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
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


class ExecutionAuthorizationService:
    def __init__(
        self,
        repository: ExecutionAuthorizationRepository,
        *,
        maximum_ttl_seconds: int = 900,
        maximum_active_jobs: int = 100,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> None:
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

    def submit_organize(self, token: str, *, limit: int) -> AutomationJob:
        if not token:
            raise ValueError("execution authorization token is required")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("remote organize limit must be a positive integer")
        now = self._clock()
        job = AutomationJob(
            str(uuid4()),
            AutomationCommand.ORGANIZE,
            AutomationJobStatus.PENDING,
            now,
            now,
            limit=limit,
            execute_authorized=True,
        )
        self._repository.consume_execution_authorization(
            self.digest(token),
            job,
            now,
            ExecutionAuthorizationAudit(
                str(uuid4()), "resolved-by-digest", "consumed", now, job_id=job.job_id
            ),
            self._maximum_active_jobs,
        )
        return job

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
