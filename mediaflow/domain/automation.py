from __future__ import annotations

from collections.abc import Mapping
import copy
import hashlib
import json
import math
import posixpath
import re
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

    This object remains independent from :class:`ScheduleDefinition`: legacy
    schedules stay scan/preview-only while the managed Scheduler consumes this
    definition through its separate due-occurrence admission boundary.
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

    @property
    def definition_fingerprint(self) -> str:
        """The stable identity of this exact definition content."""

        encoded = json.dumps(
            self.document(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

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


class WorkerStatus(StrEnum):
    LIVE = "live"
    STALE = "stale"
    STOPPED = "stopped"


class WorkerReadiness(StrEnum):
    READY = "ready"
    NO_WORKER = "no_worker"
    STALE_WORKER = "stale_worker"
    SNAPSHOT_MISMATCH = "snapshot_mismatch"


_WORKER_SECRET_PATTERN = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)\s*[:=]\s*\S+)"
)
_WORKER_ENDPOINT_PATTERN = re.compile(r"(?i)(?:https?|s3|file|smb|tcp|udp)://[^\s]+")
_WORKER_PATH_PATTERN = re.compile(
    r"(?<![\w])(?:/[a-zA-Z0-9_.~-]+(?:/[a-zA-Z0-9_.~+-]+)+|[A-Za-z]:[\\/][^\s]+)"
)
_WORKER_ENV_PATTERN = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*|\$\{[A-Za-z_][A-Za-z0-9_]*\}")


def validate_worker_label(label: str) -> str:
    if not isinstance(label, str) or not label.strip():
        raise ValueError("worker label must be a non-empty string")
    normalized = label.strip()
    if len(normalized) > 256:
        raise ValueError("worker label must not exceed 256 characters")
    if _WORKER_SECRET_PATTERN.search(normalized):
        raise ValueError("worker label must not contain secrets, tokens, or credentials")
    if _WORKER_ENDPOINT_PATTERN.search(normalized):
        raise ValueError("worker label must not contain URLs or endpoints")
    if _WORKER_PATH_PATTERN.search(normalized) or normalized.startswith(("/", "\\")):
        raise ValueError("worker label must not contain filesystem paths")
    if _WORKER_ENV_PATTERN.search(normalized):
        raise ValueError("worker label must not contain environment variable references")
    return normalized


@dataclass(frozen=True)
class ProcessingWorker:
    """A durable processing-Worker registration record."""
    worker_id: str
    label: str
    registered_at: datetime
    heartbeat_interval_seconds: float
    supported_commands: tuple[str, ...]
    configuration_snapshot_id: str | None
    configuration_snapshot_digest: str | None
    runtime_schema_version: int
    last_heartbeat_at: datetime
    status: WorkerStatus

    def __post_init__(self) -> None:
        for label_, value, maximum in (
            ("Worker ID", self.worker_id, 128),
            ("label", self.label, 256),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label_} must be a non-empty string")
            if isinstance(maximum, int) and len(value) > maximum:
                raise ValueError(f"{label_} must not exceed {maximum} characters")
        validate_worker_label(self.label)
        if isinstance(self.heartbeat_interval_seconds, bool) or not isinstance(
            self.heartbeat_interval_seconds, (int, float)
        ) or self.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat interval must be a positive number")
        if isinstance(self.runtime_schema_version, bool) or not isinstance(
            self.runtime_schema_version, int
        ) or self.runtime_schema_version < 0:
            raise ValueError("runtime schema version must be a non-negative integer")
        if not isinstance(self.supported_commands, tuple) or not all(
            isinstance(c, str) and c.strip() for c in self.supported_commands
        ):
            raise ValueError("supported commands must be a tuple of non-empty strings")

class ProcessingWorkerRepository(Protocol):
    """Persistence contract for processing-Worker registration."""

    def register_worker(
        self,
        worker_id: str,
        label: str,
        heartbeat_interval_seconds: float,
        supported_commands: tuple[str, ...],
        configuration_snapshot_id: str | None,
        configuration_snapshot_digest: str | None,
        runtime_schema_version: int,
        now: datetime,
    ) -> ProcessingWorker: ...

    def heartbeat_worker(
        self,
        worker_id: str,
        now: datetime,
    ) -> bool: ...

    def stop_worker(
        self,
        worker_id: str,
        now: datetime,
    ) -> ProcessingWorker: ...

    def list_workers(self) -> tuple[ProcessingWorker, ...]: ...

    def get_worker(self, worker_id: str) -> ProcessingWorker | None: ...


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
class AutomationDefinitionDueState:
    """Durable, bounded state for one managed definition's next occurrence."""

    definition_id: str
    next_run_at: datetime
    updated_at: datetime
    last_occurrence_at: datetime | None = None
    last_job_id: str | None = None
    last_outcome: str | None = None
    last_reason: str | None = None
    last_next_action: str | None = None
    definition_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.definition_id, str)
            or not self.definition_id.strip()
            or len(self.definition_id) > 128
            or "\x00" in self.definition_id
        ):
            raise ValueError("automation definition due-state ID is invalid")
        for label, value in (
            ("next run", self.next_run_at),
            ("updated", self.updated_at),
            ("last occurrence", self.last_occurrence_at),
        ):
            if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
                raise ValueError(f"automation definition due-state {label} must include a timezone")
        for label, value, maximum in (
            ("last Job ID", self.last_job_id, 128),
            ("last outcome", self.last_outcome, 64),
            ("last reason", self.last_reason, 256),
            ("last next action", self.last_next_action, 512),
        ):
            if value is not None and (
                not isinstance(value, str) or len(value) > maximum or "\x00" in value
            ):
                raise ValueError(f"automation definition due-state {label} is invalid")
        if self.definition_fingerprint is not None and not _is_sha256(self.definition_fingerprint):
            raise ValueError("automation definition due-state fingerprint is invalid")


@dataclass(frozen=True)
class AutomationDefinitionOccurrence:
    """One emitted managed-definition occurrence and its immutable pins."""

    occurrence_id: str
    definition_id: str
    occurrence_at: datetime
    emitted_at: datetime
    job_id: str
    definition_fingerprint: str
    definition_version: int
    configuration_revision_id: str
    configuration_revision_version: int
    configuration_revision_digest: str
    run_mode: AutomationTaskRunMode
    resource_library_id: str
    source_scope: str | None
    item_limit: int
    outcome: str = "emitted"
    reason: str | None = None
    next_action: str | None = None
    # The occurrence keeps its stable Job identity as the durable link.  The
    # Worker fills these read-back fields from the linked Job after Task
    # creation/terminal completion; keeping them optional preserves older
    # occurrence rows and scheduler emission semantics.
    task_id: str | None = None
    failure_category: str | None = None

    def __post_init__(self) -> None:
        for label, value, maximum in (
            ("occurrence ID", self.occurrence_id, 192),
            ("definition ID", self.definition_id, 128),
            ("Job ID", self.job_id, 128),
            ("configuration revision ID", self.configuration_revision_id, 128),
            ("ResourceLibrary ID", self.resource_library_id, 128),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > maximum
                or "\x00" in value
            ):
                raise ValueError(f"automation occurrence {label} is invalid")
        for label, value in (("occurrence", self.occurrence_at), ("emitted", self.emitted_at)):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError(f"automation occurrence {label} time must include a timezone")
        if not _is_sha256(self.definition_fingerprint):
            raise ValueError("automation occurrence definition fingerprint is invalid")
        if not _is_sha256(self.configuration_revision_digest):
            raise ValueError("automation occurrence configuration digest is invalid")
        for label, value in (
            ("definition version", self.definition_version),
            ("configuration revision version", self.configuration_revision_version),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"automation occurrence {label} must be positive")
        if not isinstance(self.run_mode, AutomationTaskRunMode):
            object.__setattr__(self, "run_mode", AutomationTaskRunMode.parse(self.run_mode))
        normalized_scope = AutomationTaskDefinition.normalize_scope(self.source_scope)
        object.__setattr__(self, "source_scope", normalized_scope)
        if (
            isinstance(self.item_limit, bool)
            or not isinstance(self.item_limit, int)
            or not 1 <= self.item_limit <= AutomationTaskDefinition.MAX_ITEM_LIMIT
        ):
            raise ValueError("automation occurrence item limit is invalid")
        for label, value, maximum in (
            ("outcome", self.outcome, 64),
            ("reason", self.reason, 256),
            ("next action", self.next_action, 512),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > maximum
            ):
                raise ValueError(f"automation occurrence {label} is invalid")
        for label, value, maximum in (
            ("Task ID", self.task_id, 128),
            ("failure category", self.failure_category, 64),
        ):
            if value is not None and (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > maximum
                or "\x00" in value
            ):
                raise ValueError(f"automation occurrence {label} is invalid")

    def document(self) -> dict[str, object]:
        return {
            "occurrenceId": self.occurrence_id,
            "definitionId": self.definition_id,
            "occurrenceAt": self.occurrence_at.isoformat(),
            "emittedAt": self.emitted_at.isoformat(),
            "jobId": self.job_id,
            "definitionFingerprint": self.definition_fingerprint,
            "definitionVersion": self.definition_version,
            "configurationRevisionId": self.configuration_revision_id,
            "configurationRevisionVersion": self.configuration_revision_version,
            "configurationRevisionDigest": self.configuration_revision_digest,
            "runMode": self.run_mode.value,
            "resourceLibraryId": self.resource_library_id,
            "sourceScope": self.source_scope,
            "itemLimit": self.item_limit,
            "outcome": self.outcome,
            "reason": self.reason,
            "nextAction": self.next_action,
            "taskId": self.task_id,
            "failureCategory": self.failure_category,
        }

    to_document = document
    as_document = document


# Descriptive aliases keep the persistence/application adapter vocabulary
# discoverable without creating parallel contracts.
AutomationDueState = AutomationDefinitionDueState
AutomationDefinitionOccurrenceRecord = AutomationDefinitionOccurrence


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


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
    worker_id: str | None = None
    configuration_snapshot_id: str | None = None
    configuration_snapshot_digest: str | None = None
    failure_category: str | None = None
    failure_durable_state: str | None = None
    failure_side_effects: str | None = None
    failure_retry_safe: bool | None = None
    failure_next_action: str | None = None
    # These fields are populated only for managed Automation Task Definition
    # occurrences.  Legacy jobs deliberately remain unpinned.
    definition_id: str | None = None
    definition_fingerprint: str | None = None
    definition_version: int | None = None
    occurrence_at: datetime | None = None
    run_mode: AutomationTaskRunMode | None = None
    resource_library_id: str | None = None
    source_scope: str | None = None
    configuration_snapshot_version: int | None = None

    @property
    def automation_definition_id(self) -> str | None:
        return self.definition_id

    @property
    def automation_definition_fingerprint(self) -> str | None:
        return self.definition_fingerprint

    @property
    def automation_definition_version(self) -> int | None:
        return self.definition_version

    @property
    def definition_pinned(self) -> bool:
        return self.definition_id is not None

    @property
    def configuration_revision_id(self) -> str | None:
        return self.configuration_snapshot_id

    @property
    def configuration_revision_digest(self) -> str | None:
        return self.configuration_snapshot_digest

    @property
    def configuration_revision_version(self) -> int | None:
        return self.configuration_snapshot_version


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
    automation_task_definitions: tuple[AutomationTaskDefinition, ...] = ()
    configuration_snapshot_version: int | None = None
    resource_library_ids: tuple[str, ...] = ()
    enabled_resource_library_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.snapshot_id or not self.snapshot_digest:
            raise ValueError("scheduler configuration snapshot identity is required")
        if isinstance(self.maximum_active_jobs, bool) or not isinstance(
            self.maximum_active_jobs, int
        ):
            raise ValueError("scheduler maximum active Jobs must be an integer")
        if not 1 <= self.maximum_active_jobs <= 10_000:
            raise ValueError("scheduler maximum active Jobs must be between 1 and 10000")
        if self.configuration_snapshot_version is not None and (
            isinstance(self.configuration_snapshot_version, bool)
            or not isinstance(self.configuration_snapshot_version, int)
            or self.configuration_snapshot_version < 1
        ):
            raise ValueError("scheduler configuration snapshot version must be positive")


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
    def get_automation_definition_due_state(
        self, definition_id: str
    ) -> AutomationDefinitionDueState | None: ...
    def initialize_automation_definition_due_state(
        self,
        definition_id: str,
        next_run_at: datetime,
        now: datetime,
        *,
        definition_fingerprint: str | None = None,
    ) -> AutomationDefinitionDueState: ...
    def reset_automation_definition_due_state(
        self,
        definition_id: str,
        next_run_at: datetime,
        now: datetime,
        *,
        definition_fingerprint: str,
    ) -> AutomationDefinitionDueState: ...
    def record_automation_definition_failure(
        self,
        definition_id: str,
        *,
        outcome: str,
        reason: str,
        next_action: str,
        now: datetime,
        expected_next_run_at: datetime | None = None,
    ) -> AutomationDefinitionDueState | None: ...
    def enqueue_due_automation_definition(
        self,
        definition_id: str,
        job: AutomationJob,
        occurrence: AutomationDefinitionOccurrence,
        next_run_at: datetime,
        now: datetime,
        maximum_active_jobs: int,
    ) -> bool: ...
    def get_latest_automation_definition_occurrence(
        self, definition_id: str
    ) -> AutomationDefinitionOccurrence | None: ...
    def list_automation_definition_occurrences(
        self,
        definition_id: str,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[AutomationDefinitionOccurrence, ...]: ...
    def list_latest_automation_definition_occurrences(
        self, definition_ids: Iterable[str]
    ) -> tuple[AutomationDefinitionOccurrence, ...]: ...
    def list_automation_definition_due_states(
        self,
        *,
        limit: int | None = None,
        definition_ids: Iterable[str] | None = None,
    ) -> tuple[AutomationDefinitionDueState, ...]: ...
