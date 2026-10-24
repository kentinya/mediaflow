"""Focused Automation engine settings and truthful consumer-adoption evidence.

Two truths are kept apart here on purpose:

* the **published target** — the exact four Automation engine values in the
  immutable Active configuration, identified by revision id/version/digest; and
* the **adopted values** — what each relevant live resident process actually
  installed in its own loop after adopting a publication at a safe boundary.

Only a *published target* can be read from the managed configuration store, and
only a *consumer report* can prove adoption.  A snapshot the API happens to hold
in memory therefore certifies the API's own binding and nothing about another
process's cadence, which is why the two are projected through different fields
with different freshness rules.

The module is pure: it validates, normalizes and evaluates.  It never loads a
configuration, writes a report, admits work, opens Storage or calls a Provider.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AutomationEngineField(StrEnum):
    """The four engine settings one focused checked Save owns."""

    MAXIMUM_ACTIVE_JOBS = "automation.maximumActiveJobs"
    STALE_JOB_AGE_SECONDS = "automation.staleJobAgeSeconds"
    WORKER_POLL_SECONDS = "automation.workerPollSeconds"
    SCHEDULER_POLL_SECONDS = "automation.schedulerPollSeconds"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(item.value for item in cls)


ENGINE_FIELD_PATHS: tuple[str, ...] = AutomationEngineField.values()

#: Which resident service actually consumes which polling field.  A field that
#: no resident process consumes is never asserted as adopted by one, and a
#: consumer never claims a field outside its own role.
CONSUMER_POLLING_FIELDS: dict[str, str] = {
    "worker": AutomationEngineField.WORKER_POLL_SECONDS.value,
    "scheduler": AutomationEngineField.SCHEDULER_POLL_SECONDS.value,
}

#: The two admission/capacity fields are consumed by whichever boundary admits
#: or observes Jobs.  They are reported as *engine* settings with an API-local
#: basis, never as a resident process's adopted cadence.
CAPACITY_FIELD_PATHS: tuple[str, ...] = (
    AutomationEngineField.MAXIMUM_ACTIVE_JOBS.value,
    AutomationEngineField.STALE_JOB_AGE_SECONDS.value,
)

#: An explicit, deployment-owned poll override retains precedence over the
#: published value.  It is never silently overwritten by a Web Save.
OVERRIDE_SOURCE_CLI = "cli"
OVERRIDE_SOURCE_DEPLOYMENT = "deployment"
_OVERRIDE_SOURCES = frozenset({OVERRIDE_SOURCE_CLI, OVERRIDE_SOURCE_DEPLOYMENT})

#: Documented internal recheck bound for the resident loops' idle wait.  It is
#: independent of the configured poll value and of work arriving, so a
#: previously long wait still observes a new publication promptly.  The bound
#: gates the *configuration recheck* only: the business poll (claim/due check)
#: keeps the cadence this process selected, so a recheck never turns into an
#: early tick/emission.
CONFIG_RECHECK_SECONDS = 5.0

#: How often an owning resident consumer refreshes its own adoption report even
#: though nothing changed.  Readback expires a report as stale when it is older
#: than ``max(3 * heartbeat interval, 10s)``, so a bounded refresh keeps a live,
#: unchanged consumer distinct from a dead one.  It is a reporting cadence on the
#: existing bounded wake, never an extra business poll.
ADOPTION_REPORT_REFRESH_SECONDS = 5.0

MAX_ENGINE_EFFECTIVE_REPORT_FIELDS = 4


@dataclass(frozen=True)
class EngineFieldSpec:
    """One bounded, operator-explainable engine field."""

    field_path: str
    label: str
    unit: str
    value_type: str  # "integer" | "number"
    minimum: float | None
    maximum: float | None
    meaning: str
    not_meaning: str
    #: The resident service that must adopt this field, if any.
    consumer: str | None = None


ENGINE_FIELD_SPECS: dict[str, EngineFieldSpec] = {
    AutomationEngineField.MAXIMUM_ACTIVE_JOBS.value: EngineFieldSpec(
        AutomationEngineField.MAXIMUM_ACTIVE_JOBS.value,
        "并行任务上限",
        "个任务",
        "integer",
        1,
        10_000,
        "共享准入池中同时处于等待与运行状态的 Job 数量上限。",
        "不是 Worker/线程数,也不是同时整理的媒体文件数。降低上限只阻止新的超额准入,"
        "已准入的工作保留。",
    ),
    AutomationEngineField.STALE_JOB_AGE_SECONDS.value: EngineFieldSpec(
        AutomationEngineField.STALE_JOB_AGE_SECONDS.value,
        "任务失效判定时间",
        "秒",
        "integer",
        60,
        604_800,
        "运行中的 Job 多久没有持久化更新就被观察为失效。",
        "不是总运行时长上限,不授权取消、重排或重放任何 Job。",
    ),
    AutomationEngineField.WORKER_POLL_SECONDS.value: EngineFieldSpec(
        AutomationEngineField.WORKER_POLL_SECONDS.value,
        "Worker 轮询间隔",
        "秒",
        "number",
        None,
        None,
        "常驻 Worker 进程实际检查待处理工作的间隔。",
        "独立于心跳/租约,也独立于单个 Job 的处理流水线配置。",
        consumer="worker",
    ),
    AutomationEngineField.SCHEDULER_POLL_SECONDS.value: EngineFieldSpec(
        AutomationEngineField.SCHEDULER_POLL_SECONDS.value,
        "调度器轮询间隔",
        "秒",
        "number",
        None,
        None,
        "常驻 Scheduler 进程实际检查到期任务定义的间隔。",
        "独立于每个定义的间隔/Cron/时区;它不改变任何计划时间。",
        consumer="scheduler",
    ),
}


class AutomationEngineSettingsError(ValueError):
    """One bounded, secret-free rejection of a focused settings submission."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str | None = None,
        next_action: str = "correct the reported value and save again",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.next_action = next_action

    def as_detail(self) -> dict[str, str]:
        detail = {"code": self.code, "message": self.message, "nextAction": self.next_action}
        if self.field is not None:
            detail["field"] = self.field
        return detail


@dataclass(frozen=True)
class ResidentCadence:
    """The cadence a resident consumer should install at its next safe boundary.

    ``override_source`` is set when the deployment/CLI owns the cadence, in
    which case the published value is *reported as overridden*, never as adopted.
    """

    service: str
    field_path: str
    poll_seconds: float
    published_revision_id: str
    published_revision_version: int | None
    published_revision_digest: str
    override_source: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.poll_seconds, bool) or not isinstance(self.poll_seconds, (int, float)):
            raise ValueError("resident cadence must be numeric")
        if not math.isfinite(float(self.poll_seconds)) or self.poll_seconds <= 0:
            raise ValueError("resident cadence must be a finite positive number")
        normalize_override_source(self.override_source)


@dataclass(frozen=True)
class AutomationEngineValues:
    """The four typed engine values of one configuration document."""

    maximum_active_jobs: int
    stale_job_age_seconds: int
    worker_poll_seconds: float
    scheduler_poll_seconds: float

    def as_field_map(self) -> dict[str, float | int]:
        return {
            AutomationEngineField.MAXIMUM_ACTIVE_JOBS.value: self.maximum_active_jobs,
            AutomationEngineField.STALE_JOB_AGE_SECONDS.value: self.stale_job_age_seconds,
            AutomationEngineField.WORKER_POLL_SECONDS.value: self.worker_poll_seconds,
            AutomationEngineField.SCHEDULER_POLL_SECONDS.value: self.scheduler_poll_seconds,
        }

    def field_value(self, field_path: str) -> float | int | None:
        return self.as_field_map().get(field_path)


def engine_values_from_document(document: object) -> AutomationEngineValues | None:
    """Read the four engine values from a runtime/managed document.

    ``None`` is returned when the section is absent or malformed, so a caller
    can distinguish "not published" from "published as 0".
    """

    if not isinstance(document, Mapping):
        return None
    automation = document.get("automation")
    if not isinstance(automation, Mapping):
        return None
    maximum = automation.get("maximumActiveJobs")
    stale = automation.get("staleJobAgeSeconds")
    worker_poll = automation.get("workerPollSeconds")
    scheduler_poll = automation.get("schedulerPollSeconds")
    if (
        isinstance(maximum, bool)
        or not isinstance(maximum, int)
        or isinstance(stale, bool)
        or not isinstance(stale, int)
        or isinstance(worker_poll, bool)
        or not isinstance(worker_poll, (int, float))
        or isinstance(scheduler_poll, bool)
        or not isinstance(scheduler_poll, (int, float))
    ):
        return None
    if not (math.isfinite(float(worker_poll)) and math.isfinite(float(scheduler_poll))):
        return None
    return AutomationEngineValues(
        maximum_active_jobs=int(maximum),
        stale_job_age_seconds=int(stale),
        worker_poll_seconds=float(worker_poll),
        scheduler_poll_seconds=float(scheduler_poll),
    )


def normalize_engine_setting_edits(payload: object) -> dict[str, float | int]:
    """Strictly normalize one focused four-field submission.

    The submitted document must be a flat ``{fieldPath: value}`` (or ``settings``
    wrapper) map naming exactly the four supported fields.  Unknown, missing,
    out-of-scope, boolean, fractional-integer and non-finite values are rejected
    before any Draft is created, so a browser can never narrow the publication to
    a partially validated subset or smuggle an unrelated setting into a save.
    """

    if not isinstance(payload, Mapping):
        raise AutomationEngineSettingsError(
            "settings_payload_invalid",
            "the settings submission must be a JSON object",
            next_action="submit the four Automation engine fields as an object",
        )
    raw = payload.get("settings", payload)
    if not isinstance(raw, Mapping):
        raise AutomationEngineSettingsError(
            "settings_payload_invalid",
            "the settings values must be a JSON object",
            next_action="submit the four Automation engine fields as an object",
        )
    unsupported = sorted(str(key) for key in raw if key not in ENGINE_FIELD_SPECS)
    if unsupported:
        raise AutomationEngineSettingsError(
            "settings_field_unsupported",
            "this form only publishes the four Automation engine settings",
            field=unsupported[0][:120],
            next_action=(
                "edit only maximumActiveJobs, staleJobAgeSeconds, workerPollSeconds and "
                "schedulerPollSeconds; other settings keep their own configuration journey"
            ),
        )
    missing = [path for path in ENGINE_FIELD_PATHS if path not in raw]
    if missing:
        raise AutomationEngineSettingsError(
            "settings_field_missing",
            "every one of the four Automation engine settings is required",
            field=missing[0],
            next_action="read the current published values, then submit all four fields",
        )
    normalized: dict[str, float | int] = {}
    for path in ENGINE_FIELD_PATHS:
        normalized[path] = _normalize_field(path, raw[path])
    return normalized


def _normalize_field(field_path: str, value: object) -> float | int:
    spec = ENGINE_FIELD_SPECS[field_path]
    if isinstance(value, bool):
        raise AutomationEngineSettingsError(
            "settings_boolean_not_number",
            f"{field_path} must be a number, not a boolean",
            field=field_path,
            next_action="enter a numeric value",
        )
    if isinstance(value, str) or not isinstance(value, (int, float)):
        raise AutomationEngineSettingsError(
            "settings_invalid_type",
            f"{field_path} must be a number",
            field=field_path,
            next_action="enter a numeric value",
        )
    numeric = float(value)
    if not math.isfinite(numeric):
        raise AutomationEngineSettingsError(
            "settings_not_finite",
            f"{field_path} must be a finite number",
            field=field_path,
            next_action="enter a finite numeric value",
        )
    if spec.value_type == "integer":
        if numeric != int(numeric):
            raise AutomationEngineSettingsError(
                "settings_fractional_integer",
                f"{field_path} must be a whole number",
                field=field_path,
                next_action="enter a whole number of seconds/jobs",
            )
        integer = int(numeric)
        if spec.minimum is not None and integer < spec.minimum:
            raise AutomationEngineSettingsError(
                "settings_out_of_range",
                f"{field_path} must be between {int(spec.minimum)} and {int(spec.maximum or 0)}",
                field=field_path,
                next_action=f"enter a value between {int(spec.minimum)} and "
                f"{int(spec.maximum or 0)}",
            )
        if spec.maximum is not None and integer > spec.maximum:
            raise AutomationEngineSettingsError(
                "settings_out_of_range",
                f"{field_path} must be between {int(spec.minimum or 0)} and {int(spec.maximum)}",
                field=field_path,
                next_action=f"enter a value between {int(spec.minimum or 0)} and "
                f"{int(spec.maximum)}",
            )
        return integer
    if numeric <= 0:
        raise AutomationEngineSettingsError(
            "settings_out_of_range",
            f"{field_path} must be a positive number of seconds",
            field=field_path,
            next_action="enter a positive number of seconds",
        )
    return numeric


@dataclass(frozen=True)
class PublishedEngineTarget:
    """The exact published Active identity and its four engine values."""

    revision_id: str
    revision_version: int | None
    digest: str
    values: AutomationEngineValues

    def as_document(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "revisionVersion": self.revision_version,
            "digest": self.digest,
            "values": self.values.as_field_map(),
        }


class ConsumerAdoptionStatus(StrEnum):
    """Truthful adoption state of one field for one live consumer."""

    ADOPTED = "adopted"
    PENDING = "pending"
    OVERRIDE = "override"
    STALE = "stale"
    STOPPED = "stopped"
    STOPPED_UNREPORTED = "stopped_unreported"
    UNREPORTED = "unreported"
    UNAVAILABLE = "unavailable"
    SCHEMA_INCOMPATIBLE = "schema_incompatible"


#: Statuses that cannot contribute to a collective adoption claim.
NON_ADOPTED_STATUSES: frozenset[str] = frozenset(
    item.value for item in ConsumerAdoptionStatus if item is not ConsumerAdoptionStatus.ADOPTED
)


class EngineSubmissionState(StrEnum):
    """Durable outcome of one identified focused settings submission.

    The four states are deliberately distinct, because collapsing them into one
    boolean is what lets a failed Draft or an older equal submission certify a
    request that never published.
    """

    #: The submission's own revision is the current Active.
    COMMITTED = "committed"
    #: The submission published, and a later publication has replaced it.
    SUPERSEDED = "superseded"
    #: The submission's own revision terminally failed; it cannot publish.
    NOT_COMMITTED = "not_committed"
    #: No terminal durable outcome can be proven for this exact submission.
    UNRESOLVED = "unresolved"


#: States in which the submission certainly published.
COMMITTED_SUBMISSION_STATES: frozenset[str] = frozenset(
    {EngineSubmissionState.COMMITTED.value, EngineSubmissionState.SUPERSEDED.value}
)


def normalize_override_source(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value in _OVERRIDE_SOURCES:
        return value
    return None


@dataclass(frozen=True)
class ResidentSettingsEvidence:
    """One consumer's own report that it adopted a published cadence.

    ``effective_values`` holds only the fields this consumer actually installed,
    and ``published_revision_id``/``digest`` name the publication it adopted.  A
    later publication therefore cannot be mistaken for an older adoption.
    """

    service: str
    instance_id: str
    published_revision_id: str
    published_revision_version: int | None
    published_revision_digest: str
    applied_fields: tuple[str, ...]
    effective_values: Mapping[str, float]
    override_source: str | None
    reported_at: datetime

    def __post_init__(self) -> None:
        if not self.service or not self.instance_id:
            raise ValueError("resident settings evidence needs a service and instance")
        if not self.published_revision_id or not self.published_revision_digest:
            raise ValueError("resident settings evidence needs a published identity")
        if len(self.applied_fields) > MAX_ENGINE_EFFECTIVE_REPORT_FIELDS:
            raise ValueError("resident settings evidence reports too many fields")
        for value in self.effective_values.values():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("resident settings evidence values must be numbers")
            if not math.isfinite(float(value)):
                raise ValueError("resident settings evidence values must be finite")
        normalize_override_source(self.override_source)
        if self.reported_at.tzinfo is None:
            raise ValueError("resident settings evidence time must include a timezone")

    def as_document(self) -> dict[str, object]:
        return {
            "service": self.service,
            "appliedFields": sorted(self.applied_fields),
            "effectiveValues": {
                field: float(value) for field, value in sorted(self.effective_values.items())
            },
            "publishedRevisionId": self.published_revision_id,
            "publishedRevisionVersion": self.published_revision_version,
            "publishedRevisionDigest": self.published_revision_digest,
            "overrideSource": self.override_source,
            "reportedAt": self.reported_at.isoformat(),
        }


@dataclass(frozen=True)
class ConsumerRegistrationState:
    """The minimum liveness/schema facts an adoption answer needs."""

    service: str
    instance_id: str
    status: str  # "live" | "stale" | "stopped"
    runtime_schema_version: int
    heartbeat_interval_seconds: float


def evaluate_consumer_adoption(
    *,
    service: str,
    field_path: str,
    target: PublishedEngineTarget | None,
    registrations: tuple[ConsumerRegistrationState, ...],
    evidence: tuple[ResidentSettingsEvidence, ...],
    now: datetime,
    expected_schema_version: int,
    stale_threshold_seconds: float,
) -> dict[str, object]:
    """One truthful per-consumer adoption answer for one polling field.

    Every live instance of the consumer is projected separately: a deployment is
    never reported as collectively adopted because one instance (or the API's own
    binding) reported a value.  Unreported, stale, stopped, schema-incompatible
    and overridden instances each keep their own explicit state and next action.
    """

    target_value = target.values.field_value(field_path) if target is not None else None
    instances: list[dict[str, object]] = []
    for registration in sorted(registrations, key=lambda item: item.instance_id):
        report = next(
            (item for item in evidence if item.instance_id == registration.instance_id),
            None,
        )
        instances.append(
            _evaluate_instance(
                registration=registration,
                report=report,
                target=target,
                target_value=target_value,
                field_path=field_path,
                now=now,
                expected_schema_version=expected_schema_version,
                stale_threshold_seconds=stale_threshold_seconds,
            )
        )
    adopted = bool(instances) and all(
        item["status"] == ConsumerAdoptionStatus.ADOPTED.value for item in instances
    )
    return {
        "service": service,
        "field": field_path,
        "publishedValue": target_value,
        "adopted": adopted,
        "instanceCount": len(instances),
        "instances": instances,
    }


def _evaluate_instance(
    *,
    registration: ConsumerRegistrationState,
    report: ResidentSettingsEvidence | None,
    target: PublishedEngineTarget | None,
    target_value: float | int | None,
    field_path: str,
    now: datetime,
    expected_schema_version: int,
    stale_threshold_seconds: float,
) -> dict[str, object]:
    base: dict[str, object] = {
        "instanceId": registration.instance_id,
        "liveness": registration.status,
        "publishedRevisionId": target.revision_id if target is not None else None,
        "reportedRevisionId": report.published_revision_id if report is not None else None,
        "reportedAt": report.reported_at.isoformat() if report is not None else None,
        "appliedFields": sorted(report.applied_fields) if report is not None else [],
        "effectiveValue": (report.effective_values.get(field_path) if report is not None else None),
        "overrideSource": normalize_override_source(report.override_source)
        if report is not None
        else None,
    }
    if registration.runtime_schema_version != expected_schema_version:
        return {
            **base,
            "status": ConsumerAdoptionStatus.SCHEMA_INCOMPATIBLE.value,
            "durableState": "consumer_schema_incompatible",
            "nextAction": (
                "upgrade this consumer to the same MediaFlow version as the API, then restart it"
            ),
        }
    if registration.status == "stopped":
        return {
            **base,
            "status": ConsumerAdoptionStatus.STOPPED.value,
            "durableState": "consumer_stopped",
            "nextAction": "start this service; published settings and admitted work are preserved",
        }
    if registration.status == "stale":
        return {
            **base,
            "status": ConsumerAdoptionStatus.STALE.value,
            "durableState": "consumer_heartbeat_stale",
            "nextAction": "restart this service; its heartbeat is no longer fresh",
        }
    if report is None or field_path not in report.applied_fields:
        return {
            **base,
            "status": ConsumerAdoptionStatus.UNREPORTED.value,
            "durableState": "adoption_not_reported",
            "nextAction": (
                "no adoption report exists for this running process yet; it adopts the published "
                "value at its next safe loop boundary without a restart"
            ),
        }
    age = (now - report.reported_at).total_seconds()
    if age > stale_threshold_seconds:
        return {
            **base,
            "status": ConsumerAdoptionStatus.STALE.value,
            "durableState": "adoption_report_stale",
            "reportAgeSeconds": round(age, 3),
            "nextAction": (
                "this process has not refreshed its adoption report; check that it is still "
                "running and reaching the shared database"
            ),
        }
    if report.override_source is not None:
        return {
            **base,
            "status": ConsumerAdoptionStatus.OVERRIDE.value,
            "durableState": "explicit_poll_override",
            "nextAction": (
                "this process is started with an explicit poll override, which keeps precedence "
                "over the published value; remove the override from the deployment/CLI to adopt "
                "the published cadence"
            ),
        }
    if target is None:
        return {
            **base,
            "status": ConsumerAdoptionStatus.UNAVAILABLE.value,
            "durableState": "no_published_target",
            "nextAction": "publish the settings once a valid Active configuration exists",
        }
    if report.published_revision_digest != target.digest:
        return {
            **base,
            "status": ConsumerAdoptionStatus.PENDING.value,
            "durableState": "consumer_on_older_publication",
            "nextAction": (
                "this process adopted an older publication; it adopts the current one at its "
                "next safe loop boundary"
            ),
        }
    reported_value = report.effective_values.get(field_path)
    if (
        reported_value is None
        or target_value is None
        or float(reported_value) != float(target_value)
    ):
        return {
            **base,
            "status": ConsumerAdoptionStatus.PENDING.value,
            "durableState": "consumer_value_mismatch",
            "nextAction": (
                "the reported cadence does not match the published value yet; refresh after the "
                "next loop boundary"
            ),
        }
    return {
        **base,
        "status": ConsumerAdoptionStatus.ADOPTED.value,
        "durableState": "adopted_current_publication",
        "nextAction": "none",
    }


def adoption_summary(projections: tuple[Mapping[str, object], ...]) -> dict[str, object]:
    """Aggregate per-consumer answers without ever inventing success."""

    total = len(projections)
    adopted = sum(1 for item in projections if item.get("adopted") is True)
    return {
        "consumers": total,
        "adoptedConsumers": adopted,
        "allAdopted": total > 0 and adopted == total,
    }
