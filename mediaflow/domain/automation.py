from __future__ import annotations

import copy
import math
import posixpath
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mediaflow.domain.cron import CronExpression


class AutomationCommand(StrEnum):
    SCAN = "scan"
    PREVIEW = "preview"
    ORGANIZE = "organize"
    FILE_METADATA_CORRECTION = "file-metadata-correction"
    RECOVERY_CONTINUATION = "recovery-continuation"


class AutomationTaskRunMode(StrEnum):
    """The bounded work intent owned by a managed Automation Task Definition.

    These values intentionally describe the amount of work the definition may
    request.  They do not select a Provider, policy, destination, or transfer
    operation; those decisions remain in the normal media pipeline.
    """

    SCAN_ONLY = "scan-only"
    SCAN_AND_PLAN = "scan-and-plan"
    AUTOMATIC_ORGANIZATION = "automatic-organization"

    @classmethod
    def parse(cls, value: object) -> AutomationTaskRunMode:
        if not isinstance(value, str) or not value.strip() or len(value) > 64:
            raise ValueError("Automation Task Definition mode must be bounded text")
        aliases = {
            "scan": cls.SCAN_ONLY,
            "scan_only": cls.SCAN_ONLY,
            "scanonly": cls.SCAN_ONLY,
            "scanOnly": cls.SCAN_ONLY,
            "scan-only": cls.SCAN_ONLY,
            "preview": cls.SCAN_AND_PLAN,
            "scan_and_plan": cls.SCAN_AND_PLAN,
            "scanandplan": cls.SCAN_AND_PLAN,
            "scanAndPlan": cls.SCAN_AND_PLAN,
            "scan-and-plan": cls.SCAN_AND_PLAN,
            "organize": cls.AUTOMATIC_ORGANIZATION,
            "automatic_organization": cls.AUTOMATIC_ORGANIZATION,
            "automaticorganization": cls.AUTOMATIC_ORGANIZATION,
            "automaticOrganization": cls.AUTOMATIC_ORGANIZATION,
            "automatic-organization": cls.AUTOMATIC_ORGANIZATION,
        }
        try:
            return aliases[value.strip().lower()]
        except KeyError as error:
            raise ValueError(
                "Automation Task Definition mode must be scan-only, scan-and-plan, "
                "or automatic-organization"
            ) from error


# Short aliases make the domain contract discoverable to application adapters
# while keeping one canonical enum type.
AutomationRunMode = AutomationTaskRunMode
AutomationTaskDefinitionMode = AutomationTaskRunMode


@dataclass(frozen=True)
class AutomationTaskDefinition:
    """A reusable, managed source/schedule/run-intent definition.

    This object is deliberately independent from :class:`ScheduleDefinition`:
    legacy schedules remain scan/preview-only and are consumed by the existing
    Scheduler.  The managed definition is parsed and persisted in this Task;
    later work may connect it to occurrence admission.
    """

    definition_id: str
    name: str
    resource_library_id: str
    source_scope: str | None = None
    mode: AutomationTaskRunMode = AutomationTaskRunMode.SCAN_ONLY
    interval_seconds: float | None = None
    cron: str | None = None
    timezone: str | None = None
    item_limit: int = 100
    enabled: bool = False

    MAX_ID_LENGTH = 64
    MAX_NAME_LENGTH = 120
    MAX_SCOPE_LENGTH = 1024
    MAX_TIMEZONE_LENGTH = 64
    MAX_ITEM_LIMIT = 10_000
    MAX_INTERVAL_SECONDS = 31_536_000.0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.definition_id, str)
            or not self.definition_id.strip()
            or len(self.definition_id) > self.MAX_ID_LENGTH
            or any(character in self.definition_id for character in "/\\\x00")
        ):
            raise ValueError("Automation Task Definition id must be bounded and safe")
        if (
            not isinstance(self.name, str)
            or not self.name.strip()
            or len(self.name) > self.MAX_NAME_LENGTH
            or "\x00" in self.name
        ):
            raise ValueError("Automation Task Definition name must be bounded and non-empty")
        if (
            not isinstance(self.resource_library_id, str)
            or not self.resource_library_id.strip()
            or len(self.resource_library_id) > self.MAX_ID_LENGTH
            or "\x00" in self.resource_library_id
        ):
            raise ValueError("Automation Task Definition ResourceLibrary reference is invalid")
        if not isinstance(self.mode, AutomationTaskRunMode):
            object.__setattr__(self, "mode", AutomationTaskRunMode.parse(self.mode))
        normalized_scope = self.normalize_scope(self.source_scope)
        object.__setattr__(self, "source_scope", normalized_scope)
        if not isinstance(self.enabled, bool):
            raise ValueError("Automation Task Definition enabled must be boolean")
        if (
            isinstance(self.item_limit, bool)
            or not isinstance(self.item_limit, int)
            or not 1 <= self.item_limit <= self.MAX_ITEM_LIMIT
        ):
            raise ValueError("Automation Task Definition itemLimit must be between 1 and 10000")
        has_interval = self.interval_seconds is not None
        has_cron = self.cron is not None
        if has_interval == has_cron:
            raise ValueError(
                "Automation Task Definition requires exactly one of intervalSeconds or cron"
            )
        if has_interval:
            if self.timezone is not None:
                raise ValueError("interval Automation Task Definition must not configure timezone")
            if (
                isinstance(self.interval_seconds, bool)
                or not isinstance(self.interval_seconds, (int, float))
                or not math.isfinite(float(self.interval_seconds))
                or not 0 < float(self.interval_seconds) <= self.MAX_INTERVAL_SECONDS
            ):
                raise ValueError(
                    "Automation Task Definition intervalSeconds must be positive and bounded"
                )
            object.__setattr__(self, "interval_seconds", float(self.interval_seconds))
        else:
            if not isinstance(self.cron, str) or not self.cron.strip():
                raise ValueError("Automation Task Definition cron must be non-empty text")
            if not isinstance(self.timezone, str) or not self.timezone.strip():
                raise ValueError("Cron Automation Task Definition timezone is required")
            if len(self.timezone) > self.MAX_TIMEZONE_LENGTH or "\x00" in self.timezone:
                raise ValueError("Automation Task Definition timezone is bounded")
            try:
                expression = CronExpression.parse(self.cron)
                timezone = ZoneInfo(self.timezone)
                # This also proves the expression has a bounded future occurrence
                # and keeps invalid DST/timezone combinations out of Active data.
                expression.next_after(datetime.now().astimezone(), timezone)
            except (ValueError, ZoneInfoNotFoundError) as error:
                raise ValueError(
                    "Automation Task Definition cron or timezone is invalid"
                ) from error

    @staticmethod
    def normalize_scope(value: object) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str) or len(value) > AutomationTaskDefinition.MAX_SCOPE_LENGTH:
            raise ValueError("Automation Task Definition sourceScope must be bounded text")
        if (
            "\x00" in value
            or value.startswith(("/", "\\"))
            or "\\" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
        ):
            raise ValueError(
                "Automation Task Definition sourceScope must be a safe Storage-relative path"
            )
        normalized = posixpath.normpath(value)
        if normalized in {"", ".", ".."} or normalized.startswith("../"):
            raise ValueError(
                "Automation Task Definition sourceScope must be a safe Storage-relative path"
            )
        return normalized

    @classmethod
    def from_document(
        cls,
        value: Mapping[str, object],
        *,
        resource_libraries: Iterable[object] | Mapping[str, object] | None = None,
    ) -> AutomationTaskDefinition:
        if not isinstance(value, Mapping):
            raise ValueError("Automation Task Definition must be an object")
        allowed = {
            "id",
            "name",
            "enabled",
            "resourceLibraryId",
            "sourceScope",
            "mode",
            "runMode",
            "intervalSeconds",
            "cron",
            "timezone",
            "itemLimit",
            "limit",
            "schedule",
        }
        unknown = set(value).difference(allowed)
        if unknown:
            raise ValueError(
                f"automationTaskDefinitions contains unsupported field {sorted(unknown)[0]!r}"
            )
        schedule = value.get("schedule")
        schedule_values: dict[str, object] = {}
        if "schedule" in value:
            if not isinstance(schedule, Mapping):
                raise ValueError("Automation Task Definition schedule must be an object")
            schedule_values = dict(schedule)
            if set(schedule_values).difference({"intervalSeconds", "cron", "timezone"}):
                raise ValueError("Automation Task Definition schedule contains unsupported field")
            if any(field in value for field in ("intervalSeconds", "cron", "timezone")):
                raise ValueError("Automation Task Definition schedule must not be duplicated")
        merged = {**schedule_values, **value}
        mode_value = merged.get("mode")
        if "mode" in value and "runMode" in value:
            raise ValueError("Automation Task Definition may specify only mode")
        if mode_value is None:
            mode_value = merged.get("runMode")
        if mode_value is None:
            raise ValueError("Automation Task Definition mode is required")
        limit = merged.get("itemLimit", merged.get("limit", 100))
        if "itemLimit" in merged and "limit" in merged:
            raise ValueError("Automation Task Definition may specify only itemLimit")
        interval = merged.get("intervalSeconds")
        cron = merged.get("cron")
        timezone = merged.get("timezone")
        definition = cls(
            merged.get("id", ""),
            merged.get("name", ""),
            merged.get("resourceLibraryId", ""),
            merged.get("sourceScope"),
            AutomationTaskRunMode.parse(mode_value),
            interval,
            cron,
            timezone,
            limit,
            merged.get("enabled", False),
        )
        if resource_libraries is not None:
            if isinstance(resource_libraries, Mapping):
                candidate = resource_libraries.get(definition.resource_library_id)
                values = (candidate,) if candidate is not None else ()
            else:
                values = tuple(resource_libraries)
            reference = next(
                (
                    item
                    for item in values
                    if getattr(item, "library_id", getattr(item, "id", None))
                    == definition.resource_library_id
                    or (
                        isinstance(item, Mapping)
                        and item.get("id") == definition.resource_library_id
                    )
                ),
                None,
            )
            if reference is None:
                raise ValueError(
                    "Automation Task Definition references unknown ResourceLibrary "
                    f"{definition.resource_library_id!r}"
                )
            enabled = (
                reference.get("enabled", True)
                if isinstance(reference, Mapping)
                else getattr(reference, "enabled", True)
            )
            if enabled is not True:
                raise ValueError("Automation Task Definition ResourceLibrary must be enabled")
        return definition

    @property
    def id(self) -> str:
        return self.definition_id

    @property
    def run_mode(self) -> AutomationTaskRunMode:
        return self.mode

    @property
    def source_sub_scope(self) -> str | None:
        return self.source_scope

    @property
    def limit(self) -> int:
        return self.item_limit

    @property
    def schedule_type(self) -> str:
        return "interval" if self.interval_seconds is not None else "cron"

    @property
    def schedule(self) -> dict[str, object]:
        return {
            key: value
            for key, value in {
                "intervalSeconds": self.interval_seconds,
                "cron": self.cron,
                "timezone": self.timezone,
            }.items()
            if value is not None
        }

    def document(self) -> dict[str, object]:
        result: dict[str, object] = {
            "id": self.definition_id,
            "name": self.name,
            "enabled": self.enabled,
            "resourceLibraryId": self.resource_library_id,
            "mode": self.mode.value,
            "itemLimit": self.item_limit,
        }
        if self.source_scope is not None:
            result["sourceScope"] = self.source_scope
        if self.interval_seconds is not None:
            result["intervalSeconds"] = self.interval_seconds
        else:
            result["cron"] = self.cron
            result["timezone"] = self.timezone
        return copy.deepcopy(result)

    to_document = document
    as_document = document


parse_automation_task_definition = AutomationTaskDefinition.from_document


class AutomationJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutomationQueueFull(RuntimeError):
    pass


class AutomationClaimLost(RuntimeError):
    pass


@dataclass(frozen=True)
class AutomationFailureEvidence:
    """Bounded operator-facing evidence for a trusted pre-work failure."""

    category: str
    durable_state: str
    side_effects: str
    retry_safe: bool
    next_action: str

    def __post_init__(self) -> None:
        for label, value, maximum in (
            ("category", self.category, 64),
            ("durable state", self.durable_state, 128),
            ("side effects", self.side_effects, 64),
            ("next action", self.next_action, 512),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"automation failure {label} must be bounded and non-empty")
        if not isinstance(self.retry_safe, bool):
            raise ValueError("automation failure retry safety must be boolean")


@dataclass(frozen=True)
class AutomationJob:
    job_id: str
    command: AutomationCommand
    status: AutomationJobStatus
    created_at: datetime
    updated_at: datetime
    limit: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    task_id: str | None = None
    error: str | None = None
    cancellation_requested: bool = False
    schedule_id: str | None = None
    execute_authorized: bool = False
    claim_token: str | None = None
    configuration_snapshot_id: str | None = None
    configuration_snapshot_digest: str | None = None
    failure_category: str | None = None
    failure_durable_state: str | None = None
    failure_side_effects: str | None = None
    failure_retry_safe: bool | None = None
    failure_next_action: str | None = None


@dataclass(frozen=True)
class IntervalSchedule:
    schedule_id: str
    command: AutomationCommand
    interval_seconds: float
    limit: int | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.schedule_id:
            raise ValueError("schedule ID must be non-empty")
        if not isinstance(self.command, AutomationCommand):
            object.__setattr__(self, "command", AutomationCommand(self.command))
        if self.command not in {AutomationCommand.SCAN, AutomationCommand.PREVIEW}:
            raise ValueError("schedule command must be scan or preview")
        if self.interval_seconds <= 0:
            raise ValueError("schedule interval must be positive")
        if self.limit is not None and self.limit < 1:
            raise ValueError("schedule limit must be positive")


@dataclass(frozen=True)
class CronSchedule:
    schedule_id: str
    command: AutomationCommand
    expression: str
    timezone: str
    limit: int | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        from datetime import UTC, datetime
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        from mediaflow.domain.cron import CronExpression

        if not self.schedule_id:
            raise ValueError("schedule ID must be non-empty")
        if not isinstance(self.command, AutomationCommand):
            object.__setattr__(self, "command", AutomationCommand(self.command))
        if self.command not in {AutomationCommand.SCAN, AutomationCommand.PREVIEW}:
            raise ValueError("schedule command must be scan or preview")
        expression = CronExpression.parse(self.expression)
        try:
            timezone = ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"unknown schedule timezone {self.timezone!r}") from error
        expression.next_after(datetime.now(UTC), timezone)
        if self.limit is not None and self.limit < 1:
            raise ValueError("schedule limit must be positive")


ScheduleDefinition = IntervalSchedule | CronSchedule


@dataclass(frozen=True)
class SchedulerConfigurationSnapshot:
    """The schedule inputs and identity loaded from one runtime revision."""

    snapshot_id: str
    snapshot_digest: str
    schedules: tuple[ScheduleDefinition, ...]
    maximum_active_jobs: int

    def __post_init__(self) -> None:
        if not self.snapshot_id or not self.snapshot_digest:
            raise ValueError("scheduler configuration snapshot identity is required")
        if isinstance(self.maximum_active_jobs, bool) or not isinstance(
            self.maximum_active_jobs, int
        ):
            raise ValueError("scheduler maximum active Jobs must be an integer")
        if not 1 <= self.maximum_active_jobs <= 10_000:
            raise ValueError("scheduler maximum active Jobs must be between 1 and 10000")


@dataclass(frozen=True)
class ScheduleState:
    schedule_id: str
    next_run_at: datetime
    updated_at: datetime
    last_job_id: str | None = None


@dataclass(frozen=True)
class ScheduleAuditRecord:
    audit_id: str
    schedule_id: str
    occurrence_at: datetime
    emitted_at: datetime
    job_id: str
    command: AutomationCommand
    next_run_at: datetime


class AutomationJobRepository(Protocol):
    def create_job(self, job: AutomationJob) -> None: ...
    def admit_job(self, job: AutomationJob, maximum_active_jobs: int) -> bool: ...
    def get_job(self, job_id: str) -> AutomationJob | None: ...
    def list_jobs(
        self,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[AutomationJob, ...]: ...
    def claim_next_job(self, now: datetime) -> AutomationJob | None: ...
    def update_job(self, job: AutomationJob) -> None: ...
    def request_job_cancellation(self, job_id: str, now: datetime) -> AutomationJob: ...
    def job_cancellation_requested(self, job_id: str) -> bool: ...
    def heartbeat_job(self, job_id: str, claim_token: str, now: datetime) -> bool: ...
    def complete_claimed_job(self, job: AutomationJob) -> bool: ...
    def list_stale_running_jobs(
        self, before: datetime, *, limit: int = 100
    ) -> tuple[AutomationJob, ...]: ...
    def requeue_stale_job(self, job_id: str, before: datetime, now: datetime) -> AutomationJob: ...
    def get_schedule_state(self, schedule_id: str) -> ScheduleState | None: ...
    def initialize_schedule_state(
        self, schedule_id: str, next_run_at: datetime, now: datetime
    ) -> ScheduleState: ...
    def enqueue_due_schedule(
        self,
        schedule_id: str,
        job: AutomationJob,
        occurrence_at: datetime,
        next_run_at: datetime,
        now: datetime,
        maximum_active_jobs: int,
    ) -> bool: ...
    def list_schedule_states(self) -> tuple[ScheduleState, ...]: ...
    def list_schedule_audit(
        self,
        schedule_id: str | None = None,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[ScheduleAuditRecord, ...]: ...
