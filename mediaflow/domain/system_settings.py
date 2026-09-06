from __future__ import annotations

import copy
import posixpath
import re
import zoneinfo
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mediaflow.domain.logging import LogLevel

# Fields that can never be changed after first activation.
BOOTSTRAP_IMMUTABLE_FIELDS: frozenset[str] = frozenset(
    {
        "persistence.databasePath",
    }
)

# Fields that require a restart/deployment to take effect.
RESTART_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "historyPath",
        "cachePath",
        "logPath",
        "exportPath",
    }
)

# Fields consumed immediately by running runtime components.
HOT_CONSUMED_FIELDS: frozenset[str] = frozenset(
    {
        "locale",
        "timezone",
        "automation.workerPollSeconds",
        "automation.schedulerPollSeconds",
        "automation.maximumActiveJobs",
        "automation.staleJobAgeSeconds",
        "operationalLogging.enabled",
        "operationalLogging.minimumLevel",
        "operationalLogging.retentionDays",
        "operationalLogging.maximumRecords",
        "workflowRetry.enabled",
        "workflowRetry.maxAttempts",
        "workflowRetry.baseDelaySeconds",
        "workflowRetry.maxDelaySeconds",
        "workflowRetry.jitterRatio",
        "notifications.pollSeconds",
        "notifications.deliveryLeaseSeconds",
        "api.remoteExecution.enabled",
        "api.remoteExecution.maximumTtlSeconds",
    }
)


class SystemSettingsBoundary(StrEnum):
    BOOTSTRAP_IMMUTABLE = "bootstrap_immutable"
    RESTART_REQUIRED = "restart_required"
    HOT_CONSUMED = "hot_consumed"


@dataclass(frozen=True)
class SystemSettingsField:
    """Metadata for one editable system setting."""

    field_path: str
    label: str
    section: str
    boundary: SystemSettingsBoundary
    value_type: str  # "string" | "boolean" | "integer" | "number" | "enum"
    required: bool = False


# Canonical index of editable system settings.
SYSTEM_SETTINGS_FIELDS: tuple[SystemSettingsField, ...] = tuple(
    sorted(
        [
            # Database
            SystemSettingsField(
                "persistence.databasePath",
                "Database location",
                "Database",
                SystemSettingsBoundary.BOOTSTRAP_IMMUTABLE,
                "string",
                required=True,
            ),
            SystemSettingsField(
                "historyPath",
                "History file path",
                "Database",
                SystemSettingsBoundary.RESTART_REQUIRED,
                "string",
            ),
            SystemSettingsField(
                "cachePath",
                "Cache directory path",
                "Database",
                SystemSettingsBoundary.RESTART_REQUIRED,
                "string",
            ),
            SystemSettingsField(
                "logPath",
                "Log directory path",
                "Database",
                SystemSettingsBoundary.RESTART_REQUIRED,
                "string",
            ),
            SystemSettingsField(
                "exportPath",
                "Export directory path",
                "Database",
                SystemSettingsBoundary.RESTART_REQUIRED,
                "string",
            ),
            # Localization
            SystemSettingsField(
                "locale",
                "System locale",
                "Localization",
                SystemSettingsBoundary.RESTART_REQUIRED,
                "string",
            ),
            SystemSettingsField(
                "timezone",
                "System timezone",
                "Localization",
                SystemSettingsBoundary.RESTART_REQUIRED,
                "string",
            ),
            # Automation
            SystemSettingsField(
                "automation.workerPollSeconds",
                "Worker poll interval (seconds)",
                "Automation",
                SystemSettingsBoundary.HOT_CONSUMED,
                "number",
            ),
            SystemSettingsField(
                "automation.schedulerPollSeconds",
                "Scheduler poll interval (seconds)",
                "Automation",
                SystemSettingsBoundary.HOT_CONSUMED,
                "number",
            ),
            SystemSettingsField(
                "automation.maximumActiveJobs",
                "Maximum active jobs",
                "Automation",
                SystemSettingsBoundary.HOT_CONSUMED,
                "integer",
            ),
            SystemSettingsField(
                "automation.staleJobAgeSeconds",
                "Stale job age (seconds)",
                "Automation",
                SystemSettingsBoundary.HOT_CONSUMED,
                "integer",
            ),
            # Operational logging
            SystemSettingsField(
                "operationalLogging.enabled",
                "Operational logging enabled",
                "Logging",
                SystemSettingsBoundary.HOT_CONSUMED,
                "boolean",
            ),
            SystemSettingsField(
                "operationalLogging.minimumLevel",
                "Operational logging level",
                "Logging",
                SystemSettingsBoundary.HOT_CONSUMED,
                "enum",
            ),
            SystemSettingsField(
                "operationalLogging.retentionDays",
                "Log retention (days)",
                "Logging",
                SystemSettingsBoundary.HOT_CONSUMED,
                "integer",
            ),
            SystemSettingsField(
                "operationalLogging.maximumRecords",
                "Maximum log records",
                "Logging",
                SystemSettingsBoundary.HOT_CONSUMED,
                "integer",
            ),
            # Workflow retry
            SystemSettingsField(
                "workflowRetry.enabled",
                "Workflow retry enabled",
                "Workflow",
                SystemSettingsBoundary.HOT_CONSUMED,
                "boolean",
            ),
            SystemSettingsField(
                "workflowRetry.maxAttempts",
                "Maximum retry attempts",
                "Workflow",
                SystemSettingsBoundary.HOT_CONSUMED,
                "integer",
            ),
            SystemSettingsField(
                "workflowRetry.baseDelaySeconds",
                "Base retry delay (seconds)",
                "Workflow",
                SystemSettingsBoundary.HOT_CONSUMED,
                "number",
            ),
            SystemSettingsField(
                "workflowRetry.maxDelaySeconds",
                "Maximum retry delay (seconds)",
                "Workflow",
                SystemSettingsBoundary.HOT_CONSUMED,
                "number",
            ),
            SystemSettingsField(
                "workflowRetry.jitterRatio",
                "Retry jitter ratio",
                "Workflow",
                SystemSettingsBoundary.HOT_CONSUMED,
                "number",
            ),
            # Notifications
            SystemSettingsField(
                "notifications.pollSeconds",
                "Notification poll interval (seconds)",
                "Notifications",
                SystemSettingsBoundary.HOT_CONSUMED,
                "number",
            ),
            SystemSettingsField(
                "notifications.deliveryLeaseSeconds",
                "Delivery lease duration (seconds)",
                "Notifications",
                SystemSettingsBoundary.HOT_CONSUMED,
                "integer",
            ),
            # API remote execution
            SystemSettingsField(
                "api.remoteExecution.enabled",
                "Remote execution enabled",
                "API",
                SystemSettingsBoundary.HOT_CONSUMED,
                "boolean",
            ),
            SystemSettingsField(
                "api.remoteExecution.maximumTtlSeconds",
                "Remote execution maximum TTL (seconds)",
                "API",
                SystemSettingsBoundary.HOT_CONSUMED,
                "integer",
            ),
        ],
        key=lambda f: f.field_path,
    )
)

FIELD_INDEX: dict[str, SystemSettingsField] = {f.field_path: f for f in SYSTEM_SETTINGS_FIELDS}
_LOCALE_REGEX = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


@dataclass(frozen=True)
class SystemSettings:
    """Canonical typed system settings projection.

    Values are read from the managed configuration document.
    """

    # Identity
    revision_id: str | None
    revision_version: int | None
    revision_digest: str | None
    is_active: bool

    # Database & storage paths
    database_path: str | None
    history_path: str | None
    cache_path: str | None = None
    log_path: str | None = None
    export_path: str | None = None

    # Localization
    locale: str | None = None
    timezone: str | None = None

    # Automation
    worker_poll_seconds: float | None = None
    scheduler_poll_seconds: float | None = None
    maximum_active_jobs: int | None = None
    stale_job_age_seconds: int | None = None

    # Operational logging
    operational_logging_enabled: bool | None = None
    operational_logging_minimum_level: LogLevel | None = None
    operational_logging_retention_days: int | None = None
    operational_logging_maximum_records: int | None = None

    # Workflow retry
    workflow_retry_enabled: bool | None = None
    workflow_retry_max_attempts: int | None = None
    workflow_retry_base_delay_seconds: float | None = None
    workflow_retry_max_delay_seconds: float | None = None
    workflow_retry_jitter_ratio: float | None = None

    # Notifications
    notification_poll_seconds: float | None = None
    notification_delivery_lease_seconds: float | None = None

    # API
    api_remote_execution_enabled: bool | None = None
    api_remote_execution_maximum_ttl_seconds: int | None = None

    # Bootstrap / active identity
    bootstrap_database_path: str | None = None

    # Field-level boundaries
    field_boundaries: dict[str, SystemSettingsBoundary] = field(default_factory=dict)

    @classmethod
    def from_document(
        cls,
        document: dict[str, Any],
        revision_id: str | None = None,
        revision_version: int | None = None,
        revision_digest: str | None = None,
        is_active: bool = False,
        bootstrap_database_path: str | None = None,
    ) -> SystemSettings:
        """Project a typed SystemSettings from a managed configuration document."""

        persistence = document.get("persistence", {})
        automation = document.get("automation", {})
        logging_cfg = document.get("operationalLogging", {})
        retry_cfg = document.get("workflowRetry", {})
        notifications = document.get("notifications", {})
        api_cfg = document.get("api", {})
        remote_exec = api_cfg.get("remoteExecution", {})

        boundaries: dict[str, SystemSettingsBoundary] = {
            f.field_path: f.boundary for f in SYSTEM_SETTINGS_FIELDS
        }

        level_raw = logging_cfg.get("minimumLevel", "INFO")
        try:
            level = LogLevel[str(level_raw).upper()]
        except (KeyError, AttributeError):
            level = None

        return cls(
            revision_id=revision_id,
            revision_version=revision_version,
            revision_digest=revision_digest,
            is_active=is_active,
            database_path=persistence.get("databasePath"),
            history_path=document.get("historyPath"),
            cache_path=document.get("cachePath"),
            log_path=document.get("logPath"),
            export_path=document.get("exportPath"),
            locale=document.get("locale"),
            timezone=document.get("timezone"),
            worker_poll_seconds=_float_or_none(automation.get("workerPollSeconds")),
            scheduler_poll_seconds=_float_or_none(automation.get("schedulerPollSeconds")),
            maximum_active_jobs=_int_or_none(automation.get("maximumActiveJobs")),
            stale_job_age_seconds=_int_or_none(automation.get("staleJobAgeSeconds")),
            operational_logging_enabled=_bool_or_none(logging_cfg.get("enabled")),
            operational_logging_minimum_level=level,
            operational_logging_retention_days=_int_or_none(logging_cfg.get("retentionDays")),
            operational_logging_maximum_records=_int_or_none(logging_cfg.get("maximumRecords")),
            workflow_retry_enabled=_bool_or_none(retry_cfg.get("enabled")),
            workflow_retry_max_attempts=_int_or_none(retry_cfg.get("maxAttempts")),
            workflow_retry_base_delay_seconds=_float_or_none(retry_cfg.get("baseDelaySeconds")),
            workflow_retry_max_delay_seconds=_float_or_none(retry_cfg.get("maxDelaySeconds")),
            workflow_retry_jitter_ratio=_float_or_none(retry_cfg.get("jitterRatio")),
            notification_poll_seconds=_float_or_none(notifications.get("pollSeconds")),
            notification_delivery_lease_seconds=_int_or_none(
                notifications.get("deliveryLeaseSeconds")
            ),
            api_remote_execution_enabled=_bool_or_none(remote_exec.get("enabled")),
            api_remote_execution_maximum_ttl_seconds=_int_or_none(
                remote_exec.get("maximumTtlSeconds")
            ),
            bootstrap_database_path=bootstrap_database_path,
            field_boundaries=boundaries,
        )

    def as_projection(self) -> dict[str, Any]:
        """Return the secret-free settings projection suitable for API responses."""

        result: dict[str, Any] = {
            "revisionId": self.revision_id,
            "revisionVersion": self.revision_version,
            "revisionDigest": self.revision_digest,
            "isActive": self.is_active,
            "sections": {},
            "settings": {},
        }
        sections: dict[str, dict[str, Any]] = {}
        flat_settings: dict[str, Any] = {}

        for f in SYSTEM_SETTINGS_FIELDS:
            value = self._field_value(f.field_path)
            formatted = self._format_value(f, value) if value is not None else None
            flat_settings[f.field_path] = formatted
            if f.section not in sections:
                sections[f.section] = {}
            sections[f.section][f.field_path] = {
                "label": f.label,
                "value": formatted,
                "boundary": f.boundary.value,
                "fieldPath": f.field_path,
                "valueType": f.value_type,
                "required": f.required,
            }

        result["sections"] = sections
        result["settings"] = flat_settings
        if self.bootstrap_database_path:
            result["bootstrapDatabasePath"] = self.bootstrap_database_path
        return result

    def _field_value(self, field_path: str) -> Any:
        mapping = {
            "persistence.databasePath": self.database_path,
            "historyPath": self.history_path,
            "cachePath": self.cache_path,
            "logPath": self.log_path,
            "exportPath": self.export_path,
            "locale": self.locale,
            "timezone": self.timezone,
            "automation.workerPollSeconds": self.worker_poll_seconds,
            "automation.schedulerPollSeconds": self.scheduler_poll_seconds,
            "automation.maximumActiveJobs": self.maximum_active_jobs,
            "automation.staleJobAgeSeconds": self.stale_job_age_seconds,
            "operationalLogging.enabled": self.operational_logging_enabled,
            "operationalLogging.minimumLevel": (
                self.operational_logging_minimum_level.name
                if self.operational_logging_minimum_level is not None
                else None
            ),
            "operationalLogging.retentionDays": self.operational_logging_retention_days,
            "operationalLogging.maximumRecords": self.operational_logging_maximum_records,
            "workflowRetry.enabled": self.workflow_retry_enabled,
            "workflowRetry.maxAttempts": self.workflow_retry_max_attempts,
            "workflowRetry.baseDelaySeconds": self.workflow_retry_base_delay_seconds,
            "workflowRetry.maxDelaySeconds": self.workflow_retry_max_delay_seconds,
            "workflowRetry.jitterRatio": self.workflow_retry_jitter_ratio,
            "notifications.pollSeconds": self.notification_poll_seconds,
            "notifications.deliveryLeaseSeconds": self.notification_delivery_lease_seconds,
            "api.remoteExecution.enabled": self.api_remote_execution_enabled,
            "api.remoteExecution.maximumTtlSeconds": self.api_remote_execution_maximum_ttl_seconds,
        }
        return mapping.get(field_path)

    @staticmethod
    def _format_value(field: SystemSettingsField, value: Any) -> Any:
        if value is None:
            return None
        if field.value_type == "boolean":
            return bool(value)
        if field.value_type == "integer":
            return int(value)
        if field.value_type == "number":
            return float(value)
        return str(value)


@dataclass(frozen=True)
class SystemSettingsEdit:
    """One field edit in a settings update request."""

    field_path: str
    value: Any


def validate_settings_edit(
    edits: tuple[SystemSettingsEdit, ...],
    bootstrap_database_path: str | None,
) -> list[dict[str, str]]:
    """Validate a batch of settings edits.

    Returns a list of error objects. Empty list means all edits are valid.
    """
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    edits_by_path: dict[str, Any] = {}

    for edit in edits:
        if edit.field_path in seen:
            errors.append(
                {
                    "code": "duplicate_field",
                    "message": f"field {edit.field_path!r} is specified more than once",
                    "field": edit.field_path,
                    "nextAction": "send each field at most once",
                }
            )
            continue
        seen.add(edit.field_path)
        edits_by_path[edit.field_path] = edit.value

        field = FIELD_INDEX.get(edit.field_path)
        if field is None:
            errors.append(
                {
                    "code": "unknown_field",
                    "message": f"unknown system setting {edit.field_path!r}",
                    "field": edit.field_path,
                    "nextAction": "check the supported fields list",
                }
            )
            continue

        if field.boundary is SystemSettingsBoundary.BOOTSTRAP_IMMUTABLE:
            errors.append(
                {
                    "code": "field_immutable",
                    "message": f"{edit.field_path!r} is bootstrap-owned and cannot be changed",
                    "field": edit.field_path,
                    "boundary": "bootstrap_immutable",
                    "nextAction": (
                        "this field is determined at first setup and requires a fresh "
                        "installation to change"
                    ),
                }
            )
            continue

        err = _validate_field_value(field, edit.value, bootstrap_database_path)
        if err:
            errors.append(err)

    # Cross-field validation: workflowRetry maxDelaySeconds >= baseDelaySeconds
    if (
        "workflowRetry.baseDelaySeconds" in edits_by_path
        and "workflowRetry.maxDelaySeconds" in edits_by_path
    ):
        base = edits_by_path["workflowRetry.baseDelaySeconds"]
        max_d = edits_by_path["workflowRetry.maxDelaySeconds"]
        if (
            isinstance(base, (int, float))
            and isinstance(max_d, (int, float))
            and not isinstance(base, bool)
            and not isinstance(max_d, bool)
        ):
            if max_d < base:
                errors.append(
                    {
                        "code": "invalid_range",
                        "message": (
                            "workflowRetry.maxDelaySeconds must be at least baseDelaySeconds"
                        ),
                        "field": "workflowRetry.maxDelaySeconds",
                        "nextAction": "set maxDelaySeconds >= baseDelaySeconds",
                    }
                )

    return errors


def _validate_field_value(
    field: SystemSettingsField,
    value: Any,
    bootstrap_database_path: str | None,
) -> dict[str, str] | None:
    """Return an error dict or None."""

    if field.value_type == "boolean":
        if not isinstance(value, bool):
            return {
                "code": "invalid_type",
                "message": f"{field.field_path!r} must be a boolean",
                "field": field.field_path,
                "nextAction": "send true or false",
            }
        return None

    if field.value_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return {
                "code": "invalid_type",
                "message": f"{field.field_path!r} must be an integer",
                "field": field.field_path,
                "nextAction": "send an integer value",
            }
        return _validate_integer_bounds(field.field_path, value)

    if field.value_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return {
                "code": "invalid_type",
                "message": f"{field.field_path!r} must be a number",
                "field": field.field_path,
                "nextAction": "send a numeric value",
            }
        return _validate_number_bounds(field.field_path, float(value))

    if field.value_type == "enum":
        if not isinstance(value, str):
            return {
                "code": "invalid_type",
                "message": f"{field.field_path!r} must be a string",
                "field": field.field_path,
                "nextAction": "send a valid string value",
            }
        if field.field_path == "operationalLogging.minimumLevel":
            try:
                LogLevel[value.upper()]
            except (KeyError, AttributeError):
                valid = [e.name for e in LogLevel]
                return {
                    "code": "invalid_enum",
                    "message": f"invalid log level {value!r}",
                    "field": field.field_path,
                    "nextAction": f"use one of: {', '.join(valid)}",
                }
        return None

    if field.value_type == "string":
        if not isinstance(value, str):
            return {
                "code": "invalid_type",
                "message": f"{field.field_path!r} must be a string",
                "field": field.field_path,
                "nextAction": "send a string value",
            }
        if field.field_path == "locale":
            return _validate_locale(value)
        if field.field_path == "timezone":
            return _validate_timezone(value)
        if field.field_path in {
            "historyPath",
            "cachePath",
            "logPath",
            "exportPath",
            "persistence.databasePath",
        }:
            return _validate_path(field.field_path, value, bootstrap_database_path)
        return None

    return None


def _validate_integer_bounds(field_path: str, value: int) -> dict[str, str] | None:
    bounds = {
        "automation.maximumActiveJobs": (1, 10_000),
        "automation.staleJobAgeSeconds": (60, 604_800),
        "operationalLogging.retentionDays": (1, 3_650),
        "operationalLogging.maximumRecords": (1, 1_000_000),
        "workflowRetry.maxAttempts": (1, 100),
        "notifications.deliveryLeaseSeconds": (1, 86_400),
        "api.remoteExecution.maximumTtlSeconds": (1, 86_400),
    }
    if field_path in bounds:
        low, high = bounds[field_path]
        if value < low or value > high:
            return {
                "code": "invalid_range",
                "message": f"{field_path} must be between {low} and {high}",
                "field": field_path,
                "nextAction": f"provide a value between {low} and {high}",
            }
    return None


def _validate_number_bounds(field_path: str, value: float) -> dict[str, str] | None:
    if field_path in {
        "automation.workerPollSeconds",
        "automation.schedulerPollSeconds",
        "notifications.pollSeconds",
        "workflowRetry.baseDelaySeconds",
        "workflowRetry.maxDelaySeconds",
    }:
        if value <= 0:
            return {
                "code": "invalid_range",
                "message": f"{field_path} must be a positive number",
                "field": field_path,
                "nextAction": "provide a positive numeric value",
            }
    if field_path == "workflowRetry.jitterRatio":
        if value < 0.0 or value > 1.0:
            return {
                "code": "invalid_range",
                "message": "workflowRetry.jitterRatio must be between 0.0 and 1.0",
                "field": field_path,
                "nextAction": "provide a ratio between 0.0 and 1.0",
            }
    return None


def _validate_locale(value: str) -> dict[str, str] | None:
    stripped = value.strip()
    if not stripped:
        return {
            "code": "invalid_locale",
            "message": "locale must be a non-empty string",
            "field": "locale",
            "nextAction": "provide a valid locale tag such as 'en-US' or 'zh-CN'",
        }
    if len(stripped) > 35 or not _LOCALE_REGEX.fullmatch(stripped):
        return {
            "code": "invalid_locale",
            "message": f"invalid locale format {value!r}",
            "field": "locale",
            "nextAction": "provide a standard BCP 47 locale such as 'en-US' or 'zh-CN'",
        }
    return None


def _validate_timezone(value: str) -> dict[str, str] | None:
    stripped = value.strip()
    if not stripped:
        return {
            "code": "invalid_timezone",
            "message": "timezone must be a non-empty string",
            "field": "timezone",
            "nextAction": "provide a valid IANA timezone such as 'UTC' or 'Asia/Shanghai'",
        }
    if len(stripped) > 128 or "\x00" in stripped:
        return {
            "code": "invalid_timezone",
            "message": "timezone string exceeds maximum length or contains invalid characters",
            "field": "timezone",
            "nextAction": "provide a valid bounded IANA timezone identifier",
        }
    try:
        zoneinfo.ZoneInfo(stripped)
    except Exception:
        return {
            "code": "invalid_timezone",
            "message": f"unknown timezone {value!r}",
            "field": "timezone",
            "nextAction": "provide a recognized IANA timezone such as 'UTC' or 'Asia/Shanghai'",
        }
    return None


def _validate_path(
    field_path: str,
    value: str,
    bootstrap_database_path: str | None,
) -> dict[str, str] | None:
    if not isinstance(value, str) or not value.strip():
        return {
            "code": "invalid_value",
            "message": f"{field_path!r} must be a non-empty string",
            "field": field_path,
            "nextAction": "provide a valid path string",
        }
    if "\x00" in value:
        return {
            "code": "invalid_value",
            "message": f"{field_path!r} contains a NUL character",
            "field": field_path,
            "nextAction": "provide a valid path without NUL",
        }
    normalized = posixpath.normpath(value)
    if (
        value.startswith(("/", "\\"))
        or "\\" in value
        or normalized in {".", ".."}
        or normalized.startswith("../")
    ):
        return {
            "code": "unsafe_path",
            "message": f"{field_path!r} must be a safe relative path without traversal",
            "field": field_path,
            "nextAction": "use a safe relative path like '.mediaflow/history.jsonl'",
        }
    return None


def apply_settings_edits(
    document: dict[str, Any],
    edits: tuple[SystemSettingsEdit, ...],
) -> dict[str, Any]:
    """Apply validated settings edits to a configuration document, returning a new copy."""

    result = copy.deepcopy(document)
    for edit in edits:
        _set_nested(result, edit.field_path, edit.value)
    return result


def _set_nested(root: dict[str, Any], path: str, value: Any) -> None:
    """Set a dotted path in a nested dict, creating intermediate dicts as needed."""
    parts = path.split(".", 1)
    if len(parts) == 1:
        root[path] = value
        return
    section, rest = parts
    if section not in root or not isinstance(root[section], dict):
        root[section] = {}
    _set_nested(root[section], rest, value)


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None or not isinstance(value, bool):
        return None
    return value
