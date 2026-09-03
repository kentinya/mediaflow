from __future__ import annotations

import os
import posixpath
import re
import urllib.parse
from dataclasses import dataclass, replace
from typing import Any

from mediaflow.application.strategy_test import (
    StrategyTestConfiguration,
    strategy_runner_from_configuration,
)
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationTaskDefinition,
    CronSchedule,
    IntervalSchedule,
    ScheduleDefinition,
)
from mediaflow.domain.library import DEFAULT_MEDIA_EXTENSIONS, MediaLibrary, ResourceLibrary
from mediaflow.domain.logging import LogLevel
from mediaflow.domain.notification import NotificationEventType, WebhookDefinition
from mediaflow.domain.security import (
    ApiCredentialStatus,
    ApiPrincipalDefinition,
    ApiRole,
    ResolvedApiPrincipal,
)
from mediaflow.domain.storage import Storage
from mediaflow.domain.workflow_retry import WorkflowRetryPolicy
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.openlist_storage import OpenListStorage, OpenListStorageConfig
from mediaflow.infrastructure.s3_storage import S3Provider, S3Storage, S3StorageConfig
from mediaflow.infrastructure.smb_storage import SMBStorage, SMBStorageConfig
from mediaflow.infrastructure.strategy_user_configuration import load_strategy_configuration


@dataclass(frozen=True)
class StorageDefinition:
    storage_id: str
    storage_type: str
    root_path: str
    name: str
    read_only: bool = False
    options: dict[str, Any] | None = None


@dataclass(frozen=True)
class RuntimeConfiguration:
    strategy: StrategyTestConfiguration
    storage_definitions: tuple[StorageDefinition, ...]
    resource_libraries: tuple[ResourceLibrary, ...]
    resource_display_roots: tuple[tuple[str, str], ...]
    media_libraries: tuple[MediaLibrary, ...]
    history_path: str
    database_path: str
    api_token_env: str | None = None
    automation_schedules: tuple[ScheduleDefinition, ...] = ()
    worker_poll_seconds: float = 2.0
    scheduler_poll_seconds: float = 5.0
    webhooks: tuple[WebhookDefinition, ...] = ()
    notification_poll_seconds: float = 5.0
    notification_delivery_lease_seconds: float = 300.0
    remote_execution_enabled: bool = False
    remote_execution_maximum_ttl_seconds: int = 900
    api_principals: tuple[ApiPrincipalDefinition, ...] = ()
    operational_logging_enabled: bool = False
    operational_logging_minimum_level: LogLevel = LogLevel.INFO
    operational_logging_retention_days: int = 30
    operational_logging_maximum_records: int = 10_000
    automation_maximum_active_jobs: int = 100
    automation_stale_job_age_seconds: int = 3600
    workflow_retry_policy: WorkflowRetryPolicy = WorkflowRetryPolicy()
    # Configuration authority is explicit so a managed Active snapshot can never
    # be mistaken for the JSON compatibility bootstrap.
    configuration_authority: str = "JSON_BOOTSTRAP"
    configuration_snapshot_id: str | None = None
    configuration_snapshot_digest: str | None = None
    configuration_snapshot_version: int | None = None
    automation_task_definitions: tuple[AutomationTaskDefinition, ...] = ()

    def create_storages(
        self,
        external: dict[str, Storage] | None = None,
        storage_ids: set[str] | None = None,
    ) -> dict[str, Storage]:
        storages = dict(external or {})
        for value in self.storage_definitions:
            if storage_ids is not None and value.storage_id not in storage_ids:
                continue
            if value.storage_id in storages:
                continue
            storages[value.storage_id] = create_storage_from_definition(value)
        return storages

    def resolve_webhook_targets(self) -> dict[str, tuple[WebhookDefinition, str]]:
        targets = {}
        for definition in self.webhooks:
            if not definition.enabled:
                continue
            secret = os.environ.get(definition.secret_env)
            if not secret:
                raise ValueError(
                    f"Webhook {definition.webhook_id!r} requires environment variable "
                    f"{definition.secret_env}"
                )
            targets[definition.webhook_id] = (definition, secret)
        return targets

    def resolve_api_principals(self) -> tuple[ResolvedApiPrincipal, ...]:
        definitions = self.api_principals
        if not definitions and self.api_token_env:
            definitions = (
                ApiPrincipalDefinition("legacy-admin", self.api_token_env, (ApiRole.ADMIN,)),
            )
        resolved = []
        for definition in definitions:
            if not definition.enabled:
                continue
            token = os.environ.get(definition.token_env)
            if not token:
                raise ValueError(
                    f"API principal {definition.principal_id!r} requires environment variable "
                    f"{definition.token_env}"
                )
            resolved.append(
                ResolvedApiPrincipal(definition.principal_id, token, definition.permissions)
            )
        if not resolved:
            raise ValueError("API requires at least one enabled configured principal")
        return tuple(resolved)

    def api_credential_statuses(self) -> tuple[ApiCredentialStatus, ...]:
        definitions = self.api_principals
        if not definitions and self.api_token_env:
            definitions = (
                ApiPrincipalDefinition("legacy-admin", self.api_token_env, (ApiRole.ADMIN,)),
            )
        return tuple(
            ApiCredentialStatus(
                definition.principal_id,
                definition.token_env,
                definition.roles,
                definition.enabled,
                bool(os.environ.get(definition.token_env)),
            )
            for definition in definitions
        )


@dataclass(frozen=True)
class ManagementBootstrapConfiguration:
    """Minimal recovery authority loaded without workflow configuration.

    This boundary contains only the immutable runtime database locator and the
    environment-owned API credential definitions.  It deliberately has no
    Storage, strategy, library, schedule, or provider content.
    """

    database_path: str
    api_token_env: str | None = None
    api_principals: tuple[ApiPrincipalDefinition, ...] = ()

    def resolve_api_principals(self) -> tuple[ResolvedApiPrincipal, ...]:
        definitions = self.api_principals
        if not definitions and self.api_token_env:
            definitions = (
                ApiPrincipalDefinition("legacy-admin", self.api_token_env, (ApiRole.ADMIN,)),
            )
        resolved = []
        for definition in definitions:
            if not definition.enabled:
                continue
            token = os.environ.get(definition.token_env)
            if not token:
                raise ValueError(
                    f"API principal {definition.principal_id!r} requires environment "
                    f"variable {definition.token_env}"
                )
            resolved.append(
                ResolvedApiPrincipal(definition.principal_id, token, definition.permissions)
            )
        if not resolved:
            raise ValueError("API requires at least one enabled configured principal")
        return tuple(resolved)

    def api_credential_statuses(self) -> tuple[ApiCredentialStatus, ...]:
        definitions = self.api_principals
        if not definitions and self.api_token_env:
            definitions = (
                ApiPrincipalDefinition("legacy-admin", self.api_token_env, (ApiRole.ADMIN,)),
            )
        return tuple(
            ApiCredentialStatus(
                definition.principal_id,
                definition.token_env,
                definition.roles,
                definition.enabled,
                bool(os.environ.get(definition.token_env)),
            )
            for definition in definitions
        )


def load_management_bootstrap(document: Any) -> ManagementBootstrapConfiguration:
    """Load only the locator and management credential boundary.

    This function intentionally does not call the complete runtime loader.  It
    is used only to keep authenticated configuration recovery reachable while a
    managed Active workflow snapshot is unavailable.
    """

    if not isinstance(document, dict):
        raise ValueError("configuration bootstrap must be a JSON object")
    persistence = document.get("persistence", {})
    if not isinstance(persistence, dict):
        raise ValueError("configuration bootstrap persistence must be an object")
    database_path = persistence.get("databasePath", ".mediaflow/mediaflow.sqlite3")
    if not isinstance(database_path, str) or not database_path.strip() or "\x00" in database_path:
        raise ValueError("configuration bootstrap databasePath is invalid")
    api = document.get("api", {})
    if not isinstance(api, dict):
        raise ValueError("configuration bootstrap api must be an object")
    api_token_env = api.get("tokenEnv")
    if api_token_env is not None and (
        not isinstance(api_token_env, str) or not _ENV_NAME.fullmatch(api_token_env)
    ):
        raise ValueError("API tokenEnv must be a valid environment variable name")
    raw_principals = api.get("principals", [])
    if not isinstance(raw_principals, list) or not all(
        isinstance(item, dict) for item in raw_principals
    ):
        raise ValueError("API principals must be an array of objects")
    if api_token_env is not None and raw_principals:
        raise ValueError("API tokenEnv cannot be combined with principals")
    principals = tuple(_api_principal(item) for item in raw_principals)
    if len(principals) > 64:
        raise ValueError("API supports at most 64 principals")
    principal_ids = [item.principal_id for item in principals]
    token_envs = [item.token_env for item in principals]
    if len(principal_ids) != len(set(principal_ids)):
        raise ValueError("API principal IDs must be unique")
    if len(token_envs) != len(set(token_envs)):
        raise ValueError("API principal tokenEnv names must be unique")
    return ManagementBootstrapConfiguration(
        database_path,
        api_token_env,
        principals,
    )


def is_minimal_management_bootstrap(document: Any) -> bool:
    """Return whether a document contains only the fresh-setup authority.

    The recovery loader intentionally accepts extra stale workflow content so a
    previously managed installation can still expose configuration recovery.
    Fresh setup needs a stricter boundary: workflow sections must not silently
    become part of the management-only bootstrap or be mistaken for a usable
    runtime.
    """

    if not isinstance(document, dict):
        return False
    if set(document).difference({"version", "persistence", "api"}):
        return False
    if "version" in document and (
        isinstance(document["version"], bool) or document["version"] != 1
    ):
        return False
    persistence = document.get("persistence")
    if (
        not isinstance(persistence, dict)
        or "databasePath" not in persistence
        or set(persistence).difference({"databasePath"})
    ):
        return False
    api = document.get("api")
    if (
        not isinstance(api, dict)
        or not ({"tokenEnv", "principals"} & set(api))
        or set(api).difference({"tokenEnv", "principals"})
    ):
        return False
    return True


def load_minimal_management_bootstrap(document: Any) -> ManagementBootstrapConfiguration:
    """Load the strict bootstrap allowed for first-time setup."""

    if not is_minimal_management_bootstrap(document):
        raise ValueError(
            "minimal management bootstrap may contain only version, persistence.databasePath, "
            "and environment-reference API principal configuration"
        )
    return load_management_bootstrap(document)


def load_runtime_configuration(document: Any) -> RuntimeConfiguration:
    if not isinstance(document, dict):
        raise ValueError("runtime configuration must be a JSON object")
    loaded = load_strategy_configuration(document, require_complete=True)
    storage_definitions = tuple(_storage(item) for item in _objects(document, "storages"))
    for definition in storage_definitions:
        _validate_storage_definition(definition)
    storage_ids = {item.storage_id for item in storage_definitions}
    resources = []
    display_roots = []
    for item in _objects(document, "resourceLibraries"):
        storage_id = _required(item, "storageId")
        _reference(storage_id, storage_ids, "ResourceLibrary Storage")
        display_root = item.get("displayRootPath", item.get("rootPath"))
        storage_path = item.get("storagePath", "")
        if not isinstance(storage_path, str):
            raise ValueError("ResourceLibrary storagePath must be a string")
        normalized_storage_path = posixpath.normpath(storage_path) if storage_path else ""
        if (
            storage_path.startswith(("/", "\\"))
            or "\\" in storage_path
            or "\x00" in storage_path
            or (storage_path and any(part in {"", ".", ".."} for part in storage_path.split("/")))
            or normalized_storage_path in {".", ".."}
            or normalized_storage_path.startswith("../")
        ):
            raise ValueError("ResourceLibrary storagePath must be a safe Storage-relative path")
        resources.append(
            ResourceLibrary(
                _required(item, "id"),
                str(item.get("name") or item["id"]),
                storage_id,
                normalized_storage_path,
                enabled=bool(item.get("enabled", True)),
                file_extensions=tuple(item.get("extensions", ())) or DEFAULT_MEDIA_EXTENSIONS,
                max_depth=item.get("maxDepth"),
            )
        )
        if display_root is not None:
            if not isinstance(display_root, str) or not display_root.strip():
                raise ValueError(
                    "ResourceLibrary displayRootPath must be a non-empty string when configured"
                )
            display_roots.append((_required(item, "id"), display_root))
    media_libraries = tuple(
        _media_library(item, storage_ids) for item in _objects(document, "mediaLibraries")
    )
    media_ids = {item.library_id for item in media_libraries}
    if len(media_ids) != len(media_libraries):
        raise ValueError("mediaLibraries IDs must be unique")
    for policy in loaded.strategy.classification_policies:
        for rule in policy.rules:
            if rule.media_library_id not in media_ids:
                raise ValueError(
                    f"ClassificationRule {rule.rule_id!r} references unknown "
                    f"MediaLibrary {rule.media_library_id!r}"
                )
    # Constructing the application registries validates templates, duplicate IDs,
    # recognition outputs, and every RecognitionTypePolicy reference up front.
    strategy_runner_from_configuration(loaded.strategy)
    _validate_strategy_references(loaded.strategy)
    history_path = str(document.get("historyPath", ".mediaflow/history.jsonl"))
    persistence = document.get("persistence", {})
    if not isinstance(persistence, dict):
        raise ValueError("runtime configuration 'persistence' must be an object")
    database_path = persistence.get("databasePath", ".mediaflow/mediaflow.sqlite3")
    if not isinstance(database_path, str) or not database_path.strip() or "\x00" in database_path:
        raise ValueError("persistence databasePath must be a non-empty path string")
    api = document.get("api", {})
    if not isinstance(api, dict):
        raise ValueError("runtime configuration 'api' must be an object")
    api_token_env = api.get("tokenEnv")
    if api_token_env is not None and (
        not isinstance(api_token_env, str) or not _ENV_NAME.fullmatch(api_token_env)
    ):
        raise ValueError("API tokenEnv must be a valid environment variable name")
    raw_principals = api.get("principals", [])
    if not isinstance(raw_principals, list) or not all(
        isinstance(item, dict) for item in raw_principals
    ):
        raise ValueError("API principals must be an array of objects")
    if api_token_env is not None and raw_principals:
        raise ValueError("API tokenEnv cannot be combined with principals")
    api_principals = tuple(_api_principal(item) for item in raw_principals)
    if len(api_principals) > 64:
        raise ValueError("API supports at most 64 principals")
    principal_ids = [item.principal_id for item in api_principals]
    token_envs = [item.token_env for item in api_principals]
    if len(principal_ids) != len(set(principal_ids)):
        raise ValueError("API principal IDs must be unique")
    if len(token_envs) != len(set(token_envs)):
        raise ValueError("API principal tokenEnv names must be unique")
    remote_execution = api.get("remoteExecution", {})
    if not isinstance(remote_execution, dict):
        raise ValueError("API remoteExecution must be an object")
    forbidden_remote_fields = {"token", "secret", "tokenEnv", "executionToken"}.intersection(
        remote_execution
    )
    if forbidden_remote_fields:
        raise ValueError(
            f"API remoteExecution field {sorted(forbidden_remote_fields)[0]!r} is forbidden"
        )
    remote_execution_enabled = remote_execution.get("enabled", False)
    if not isinstance(remote_execution_enabled, bool):
        raise ValueError("API remoteExecution enabled must be boolean")
    maximum_ttl = remote_execution.get("maximumTtlSeconds", 900)
    if isinstance(maximum_ttl, bool) or not isinstance(maximum_ttl, int) or maximum_ttl < 1:
        raise ValueError("API remoteExecution maximumTtlSeconds must be a positive integer")
    automation = document.get("automation", {})
    if not isinstance(automation, dict):
        raise ValueError("runtime configuration 'automation' must be an object")
    allowed_automation = {
        "workerPollSeconds",
        "schedulerPollSeconds",
        "maximumActiveJobs",
        "staleJobAgeSeconds",
        "schedules",
        "taskDefinitions",
    }
    if unknown := set(automation).difference(allowed_automation):
        raise ValueError(f"unknown automation field {sorted(unknown)[0]!r}")
    maximum_active_jobs = automation.get("maximumActiveJobs", 100)
    if (
        isinstance(maximum_active_jobs, bool)
        or not isinstance(maximum_active_jobs, int)
        or maximum_active_jobs < 1
        or maximum_active_jobs > 10_000
    ):
        raise ValueError("automation maximumActiveJobs must be between 1 and 10000")
    stale_job_age_seconds = automation.get("staleJobAgeSeconds", 3600)
    if (
        isinstance(stale_job_age_seconds, bool)
        or not isinstance(stale_job_age_seconds, int)
        or stale_job_age_seconds < 60
        or stale_job_age_seconds > 604_800
    ):
        raise ValueError("automation staleJobAgeSeconds must be between 60 and 604800")
    worker_poll = _positive_number(automation.get("workerPollSeconds", 2), "workerPollSeconds")
    scheduler_poll = _positive_number(
        automation.get("schedulerPollSeconds", 5), "schedulerPollSeconds"
    )
    raw_schedules = automation.get("schedules", [])
    if not isinstance(raw_schedules, list) or not all(
        isinstance(item, dict) for item in raw_schedules
    ):
        raise ValueError("automation schedules must be an array of objects")
    schedules = tuple(_schedule(item) for item in raw_schedules)
    schedule_ids = [item.schedule_id for item in schedules]
    if len(schedule_ids) != len(set(schedule_ids)):
        raise ValueError("automation schedule IDs must be unique")
    root_definitions = document.get("automationTaskDefinitions")
    root_definitions_present = "automationTaskDefinitions" in document
    nested_definitions = automation.get("taskDefinitions", [])
    if root_definitions_present and "taskDefinitions" in automation:
        raise ValueError(
            "runtime configuration cannot define both automationTaskDefinitions and "
            "automation.taskDefinitions"
        )
    raw_definitions = root_definitions if root_definitions_present else nested_definitions
    if not isinstance(raw_definitions, list) or not all(
        isinstance(item, dict) for item in raw_definitions
    ):
        raise ValueError("automation taskDefinitions must be an array of objects")
    automation_task_definitions = tuple(
        AutomationTaskDefinition.from_document(item, resource_libraries=resources)
        for item in raw_definitions
    )
    definition_ids = [item.definition_id for item in automation_task_definitions]
    if len(definition_ids) != len(set(definition_ids)):
        raise ValueError("automation task definition IDs must be unique")
    notifications = document.get("notifications", {})
    if not isinstance(notifications, dict):
        raise ValueError("runtime configuration 'notifications' must be an object")
    notification_poll = _positive_number(
        notifications.get("pollSeconds", 5), "notification pollSeconds"
    )
    notification_lease = _positive_number(
        notifications.get("deliveryLeaseSeconds", 300),
        "notification deliveryLeaseSeconds",
    )
    raw_webhooks = notifications.get("webhooks", [])
    if not isinstance(raw_webhooks, list) or not all(
        isinstance(item, dict) for item in raw_webhooks
    ):
        raise ValueError("notification webhooks must be an array of objects")
    webhooks = tuple(_webhook(item) for item in raw_webhooks)
    webhook_ids = [item.webhook_id for item in webhooks]
    if len(webhook_ids) != len(set(webhook_ids)):
        raise ValueError("notification Webhook IDs must be unique")
    logging = document.get("operationalLogging", {})
    if not isinstance(logging, dict):
        raise ValueError("operationalLogging must be an object")
    allowed_logging = {"enabled", "minimumLevel", "retentionDays", "maximumRecords"}
    if unknown := set(logging).difference(allowed_logging):
        raise ValueError(f"unknown operationalLogging field {sorted(unknown)[0]!r}")
    logging_enabled = logging.get("enabled", False)
    if not isinstance(logging_enabled, bool):
        raise ValueError("operationalLogging enabled must be boolean")
    try:
        logging_level = LogLevel[str(logging.get("minimumLevel", "INFO")).upper()]
    except KeyError as error:
        raise ValueError("operationalLogging minimumLevel is invalid") from error
    retention_days = logging.get("retentionDays", 30)
    maximum_records = logging.get("maximumRecords", 10_000)
    for value, name, maximum in (
        (retention_days, "retentionDays", 3650),
        (maximum_records, "maximumRecords", 1_000_000),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
            raise ValueError(f"operationalLogging {name} must be between 1 and {maximum}")
    retry = _workflow_retry(document.get("workflowRetry", {}))
    return RuntimeConfiguration(
        loaded.strategy,
        storage_definitions,
        tuple(resources),
        tuple(display_roots),
        media_libraries,
        history_path,
        database_path,
        api_token_env,
        schedules,
        worker_poll,
        scheduler_poll,
        webhooks,
        notification_poll,
        notification_lease,
        remote_execution_enabled,
        maximum_ttl,
        api_principals,
        logging_enabled,
        logging_level,
        retention_days,
        maximum_records,
        maximum_active_jobs,
        stale_job_age_seconds,
        retry,
        automation_task_definitions=automation_task_definitions,
    )


def load_managed_runtime_configuration(
    document: Any,
    *,
    bootstrap_database_path: str,
) -> RuntimeConfiguration:
    """Load a managed document and enforce immutable bootstrap locators.

    This is the single validator shared by configuration activation, API
    refresh, CLI runtime resolution, and resident producers.  It performs
    normalization/reference validation only; it never constructs Storage or
    Provider adapters.
    """

    if not isinstance(bootstrap_database_path, str) or not bootstrap_database_path.strip():
        raise ValueError("bootstrap databasePath is required")
    resolved = load_runtime_configuration(document)
    if resolved.database_path != bootstrap_database_path:
        raise ValueError(
            "managed configuration cannot change immutable persistence.databasePath; "
            f"expected {bootstrap_database_path!r}"
        )
    return resolved


def with_managed_snapshot(
    configuration: RuntimeConfiguration,
    *,
    snapshot_id: str,
    digest: str,
    version: int | None = None,
) -> RuntimeConfiguration:
    """Attach the immutable Active identity consumed by new work."""
    if not snapshot_id or not digest:
        raise ValueError("managed configuration snapshot identity is required")
    return replace(
        configuration,
        configuration_authority="MANAGED",
        configuration_snapshot_id=snapshot_id,
        configuration_snapshot_digest=digest,
        configuration_snapshot_version=version,
    )


def _workflow_retry(value: object) -> WorkflowRetryPolicy:
    if not isinstance(value, dict):
        raise ValueError("workflowRetry must be an object")
    allowed = {
        "enabled",
        "maxAttempts",
        "baseDelaySeconds",
        "maxDelaySeconds",
        "jitterRatio",
    }
    if unknown := set(value).difference(allowed):
        raise ValueError(f"unknown workflowRetry field {sorted(unknown)[0]!r}")
    enabled = value.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("workflowRetry enabled must be boolean")
    numeric = {
        "max_attempts": value.get("maxAttempts", 3),
        "base_delay_seconds": value.get("baseDelaySeconds", 1.0),
        "max_delay_seconds": value.get("maxDelaySeconds", 30.0),
        "jitter_ratio": value.get("jitterRatio", 0.0),
    }
    for name, item in numeric.items():
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"workflowRetry {name} must be numeric")
    if not isinstance(numeric["max_attempts"], int):
        raise ValueError("workflowRetry maxAttempts must be an integer")
    return WorkflowRetryPolicy(enabled=enabled, **numeric)


def _api_principal(value: dict) -> ApiPrincipalDefinition:
    principal_id = _required(value, "id")
    token_env = _required(value, "tokenEnv")
    if not _ENV_NAME.fullmatch(token_env):
        raise ValueError("API principal tokenEnv must be a valid environment variable name")
    forbidden = {"token", "secret", "password", "authorization"}.intersection(value)
    if forbidden:
        raise ValueError(f"API principal field {sorted(forbidden)[0]!r} is forbidden")
    raw_roles = value.get("roles")
    if not isinstance(raw_roles, list) or not raw_roles:
        raise ValueError("API principal roles must be a non-empty array")
    try:
        roles = tuple(ApiRole(item) for item in raw_roles)
    except (TypeError, ValueError) as error:
        raise ValueError("API principal contains an unknown role") from error
    if len(roles) != len(set(roles)):
        raise ValueError("API principal roles must be unique")
    enabled = value.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("API principal enabled must be boolean")
    return ApiPrincipalDefinition(principal_id, token_env, roles, enabled)


def _storage(value: dict) -> StorageDefinition:
    storage_type = _required(value, "type").lower()
    root = value.get("rootPath", "")
    if not isinstance(root, str) or "\x00" in root:
        raise ValueError("Storage rootPath must be a string without NUL")
    if storage_type == "local" and not root.strip():
        raise ValueError("Local Storage rootPath must be non-empty")
    read_only = value.get("readOnly", False)
    if not isinstance(read_only, bool):
        raise ValueError("Storage readOnly must be boolean")
    raw_options = value.get("options")
    if raw_options is None:
        # Preserve the legacy JSON bootstrap spelling where provider fields live
        # directly on the Storage object.
        options = dict(value)
    elif isinstance(raw_options, dict):
        options = dict(raw_options)
        # A mixed document can be loaded during the migration from the legacy
        # spelling.  Canonical managed objects win when both spellings exist.
        for key, item in value.items():
            if key not in {"id", "type", "name", "rootPath", "readOnly", "enabled", "options"}:
                options.setdefault(key, item)
    else:
        raise ValueError("Storage options must be an object")
    return StorageDefinition(
        _required(value, "id"),
        storage_type,
        root,
        str(value.get("name") or value["id"]),
        read_only,
        options,
    )


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _env_name(options: dict[str, Any], key: str, *, required: bool = True) -> str | None:
    value = options.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not _ENV_NAME.fullmatch(value):
        raise ValueError(f"Storage {key} must be a valid environment variable name")
    return value


def _secret(definition: StorageDefinition, key: str) -> str:
    options = definition.options or {}
    name = _env_name(options, key)
    assert name is not None
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Storage {definition.storage_id!r} requires environment variable {name}")
    return value


def _validate_storage_definition(value: StorageDefinition) -> None:
    options = value.options or {}
    if value.storage_type == "local":
        return
    if value.storage_type == "openlist":
        _reject_literal_secrets(options, {"token"})
        _env_name(options, "tokenEnv")
        OpenListStorageConfig(
            value.storage_id,
            value.name,
            str(options.get("baseUrl", "")),
            "validation-placeholder",
            value.root_path,
            value.read_only,
            float(options.get("connectTimeout", 10)),
            float(options.get("requestTimeout", 60)),
            int(options.get("maxConcurrency", 4)),
            int(options.get("maxRetries", 2)),
            int(options.get("pageSize", 100)),
        )
        return
    if value.storage_type == "smb":
        _reject_literal_secrets(options, {"username", "password"})
        _validate_remote_root(value.root_path)
        _env_name(options, "usernameEnv")
        _env_name(options, "passwordEnv")
        SMBStorageConfig(
            value.storage_id,
            value.name,
            str(options.get("host", "")),
            str(options.get("share", "")),
            "validation-user",
            "validation-password",
            str(options["domain"]) if options.get("domain") is not None else None,
            value.root_path,
            int(options.get("port", 445)),
            value.read_only,
            float(options.get("connectTimeout", 30)),
            float(options.get("operationTimeout", 60)),
            int(options.get("maxConcurrency", 4)),
        )
        return
    if value.storage_type in {"s3", "r2", "s3-compatible"}:
        _reject_literal_secrets(options, {"accessKey", "secretKey", "sessionToken"})
        _validate_remote_root(value.root_path)
        _env_name(options, "accessKeyEnv")
        _env_name(options, "secretKeyEnv")
        _env_name(options, "sessionTokenEnv", required=False)
        provider = {
            "s3": S3Provider.AWS_S3,
            "r2": S3Provider.CLOUDFLARE_R2,
            "s3-compatible": S3Provider.S3_COMPATIBLE,
        }[value.storage_type]
        force_path_style = options.get("forcePathStyle", False)
        if not isinstance(force_path_style, bool):
            raise ValueError("Storage forcePathStyle must be boolean")
        S3StorageConfig(
            value.storage_id,
            value.name,
            provider,
            str(options.get("bucket", "")),
            "validation-access-key",
            "validation-secret-key",
            str(options["endpoint"]) if options.get("endpoint") else None,
            str(options["region"]) if options.get("region") else None,
            "validation-session" if options.get("sessionTokenEnv") else None,
            value.root_path,
            value.read_only,
            float(options.get("connectTimeout", 10)),
            float(options.get("requestTimeout", 60)),
            int(options.get("maxConcurrency", 4)),
            int(options.get("multipartThreshold", 64 * 1024 * 1024)),
            int(options.get("multipartPartSize", 16 * 1024 * 1024)),
            force_path_style,
            int(options.get("maxRetries", 2)),
            int(options.get("pageSize", 1000)),
        )
        return
    raise ValueError(f"unsupported Storage type {value.storage_type!r}")


def load_storage_definition(value: object) -> StorageDefinition:
    """Parse and validate one Storage without loading the full runtime graph.

    Managed setup checks intentionally need this narrow compatibility boundary:
    a first Draft may contain one Storage before its ResourceLibrary, policies or
    other runtime sections exist.  The function performs configuration-only
    validation and never resolves a credential or opens an adapter.
    """

    if not isinstance(value, dict):
        raise ValueError("Storage definition must be an object")
    definition = _storage(value)
    _validate_storage_definition(definition)
    return definition


def create_storage_from_definition(definition: StorageDefinition) -> Storage:
    """Construct one configured Storage adapter at the infrastructure boundary."""

    if not isinstance(definition, StorageDefinition):
        raise ValueError("Storage definition is required")
    _validate_storage_definition(definition)
    options = definition.options or {}
    if definition.storage_type == "local":
        return LocalStorage(
            definition.storage_id,
            definition.root_path,
            name=definition.name,
            read_only=definition.read_only,
        )
    if definition.storage_type == "openlist":
        token = _secret(definition, "tokenEnv")
        return OpenListStorage(
            OpenListStorageConfig(
                definition.storage_id,
                definition.name,
                str(options.get("baseUrl", "")),
                token,
                definition.root_path,
                definition.read_only,
                float(options.get("connectTimeout", 10)),
                float(options.get("requestTimeout", 60)),
                int(options.get("maxConcurrency", 4)),
                int(options.get("maxRetries", 2)),
                int(options.get("pageSize", 100)),
            )
        )
    if definition.storage_type == "smb":
        return SMBStorage(
            SMBStorageConfig(
                definition.storage_id,
                definition.name,
                str(options.get("host", "")),
                str(options.get("share", "")),
                _secret(definition, "usernameEnv"),
                _secret(definition, "passwordEnv"),
                str(options["domain"]) if options.get("domain") is not None else None,
                definition.root_path,
                int(options.get("port", 445)),
                definition.read_only,
                float(options.get("connectTimeout", 30)),
                float(options.get("operationTimeout", 60)),
                int(options.get("maxConcurrency", 4)),
            )
        )
    if definition.storage_type in {"s3", "r2", "s3-compatible"}:
        provider = {
            "s3": S3Provider.AWS_S3,
            "r2": S3Provider.CLOUDFLARE_R2,
            "s3-compatible": S3Provider.S3_COMPATIBLE,
        }[definition.storage_type]
        session_token = (
            _secret(definition, "sessionTokenEnv")
            if options.get("sessionTokenEnv") is not None
            else None
        )
        return S3Storage(
            S3StorageConfig(
                definition.storage_id,
                definition.name,
                provider,
                str(options.get("bucket", "")),
                _secret(definition, "accessKeyEnv"),
                _secret(definition, "secretKeyEnv"),
                str(options["endpoint"]) if options.get("endpoint") else None,
                str(options["region"]) if options.get("region") else None,
                session_token,
                definition.root_path,
                definition.read_only,
                float(options.get("connectTimeout", 10)),
                float(options.get("requestTimeout", 60)),
                int(options.get("maxConcurrency", 4)),
                int(options.get("multipartThreshold", 64 * 1024 * 1024)),
                int(options.get("multipartPartSize", 16 * 1024 * 1024)),
                bool(options.get("forcePathStyle", False)),
                int(options.get("maxRetries", 2)),
                int(options.get("pageSize", 1000)),
            )
        )
    raise ValueError(
        f"Storage {definition.storage_id!r} type {definition.storage_type!r} requires an "
        "injected configured adapter"
    )


def _reject_literal_secrets(options: dict[str, Any], fields: set[str]) -> None:
    configured = fields.intersection(options)
    if configured:
        raise ValueError(
            f"literal Storage secret field {sorted(configured)[0]!r} is forbidden; use Env fields"
        )


def _validate_remote_root(value: str) -> None:
    normalized = posixpath.normpath(value or ".")
    if (
        value.startswith(("/", "\\"))
        or "\\" in value
        or "\x00" in value
        or normalized == ".."
        or normalized.startswith("../")
    ):
        raise ValueError("remote Storage rootPath must be a safe relative path")


def _media_library(value: dict, storage_ids: set[str]) -> MediaLibrary:
    storage_id = _required(value, "storageId")
    _reference(storage_id, storage_ids, "MediaLibrary Storage")
    root_path = _required(value, "rootPath")
    normalized = posixpath.normpath(root_path)
    if (
        root_path.startswith(("/", "\\"))
        or "\\" in root_path
        or normalized in {".", ".."}
        or normalized.startswith("../")
    ):
        raise ValueError("MediaLibrary rootPath must be a safe Storage-relative path")
    return MediaLibrary(
        _required(value, "id"),
        str(value.get("name") or value["id"]),
        storage_id,
        normalized,
        bool(value.get("enabled", True)),
    )


def _objects(document: dict, key: str) -> list[dict]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"runtime configuration {key!r} must be an array of objects")
    return value


def _required(document: dict, key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"runtime configuration {key!r} must be a non-empty string")
    return value


def _positive_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"automation {label} must be a positive number")
    return float(value)


def _schedule(value: dict) -> IntervalSchedule | CronSchedule:
    command_value = _required(value, "command")
    try:
        command = AutomationCommand(command_value)
    except ValueError as error:
        raise ValueError("automation schedule command must be scan or preview") from error
    if command not in {AutomationCommand.SCAN, AutomationCommand.PREVIEW}:
        raise ValueError("automation schedule command must be scan or preview")
    limit = value.get("limit")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError("automation schedule limit must be a positive integer")
    enabled = value.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("automation schedule enabled must be boolean")
    has_interval = "intervalSeconds" in value
    has_cron = "cron" in value
    if has_interval == has_cron:
        raise ValueError("automation schedule requires exactly one of intervalSeconds or cron")
    if has_interval:
        if "timezone" in value:
            raise ValueError("interval schedule must not configure timezone")
        return IntervalSchedule(
            _required(value, "id"),
            command,
            _positive_number(value.get("intervalSeconds"), "schedule intervalSeconds"),
            limit,
            enabled,
        )
    return CronSchedule(
        _required(value, "id"),
        command,
        _required(value, "cron"),
        _required(value, "timezone"),
        limit,
        enabled,
    )


def _webhook(value: dict) -> WebhookDefinition:
    webhook_id = _required(value, "id")
    url = _required(value, "url")
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError(
            f"Webhook {webhook_id!r} URL must be HTTPS without credentials or fragment"
        )
    secret_env = _required(value, "secretEnv")
    if not _ENV_NAME.fullmatch(secret_env):
        raise ValueError("Webhook secretEnv must be a valid environment variable name")
    raw_events = value.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("Webhook events must be a non-empty array")
    try:
        events = tuple(NotificationEventType(item) for item in raw_events)
    except (TypeError, ValueError) as error:
        raise ValueError("Webhook contains an unsupported event") from error
    if len(events) != len(set(events)):
        raise ValueError("Webhook events must be unique")
    enabled = value.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("Webhook enabled must be boolean")
    timeout = _positive_number(value.get("timeoutSeconds", 10), "Webhook timeoutSeconds")
    max_attempts = value.get("maxAttempts", 5)
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("Webhook maxAttempts must be a positive integer")
    base_retry = _positive_number(value.get("baseRetrySeconds", 5), "Webhook baseRetrySeconds")
    max_retry = _positive_number(value.get("maxRetrySeconds", 300), "Webhook maxRetrySeconds")
    if max_retry < base_retry:
        raise ValueError("Webhook maxRetrySeconds must be at least baseRetrySeconds")
    forbidden = {"secret", "token", "authorization", "execute"}.intersection(value)
    if forbidden:
        raise ValueError(f"Webhook field {sorted(forbidden)[0]!r} is forbidden")
    return WebhookDefinition(
        webhook_id,
        url,
        secret_env,
        events,
        enabled,
        timeout,
        max_attempts,
        base_retry,
        max_retry,
    )


def _reference(value: str, available: set[str], label: str) -> None:
    if value not in available:
        raise ValueError(f"{label} references unknown Storage {value!r}")


def _validate_strategy_references(strategy: StrategyTestConfiguration) -> None:
    type_ids = {item.type_id for item in strategy.recognition_types}
    metadata_by_id = {item.policy_id: item for item in strategy.metadata_policies}
    catalogs = {
        "MetadataPolicy": {item.policy_id for item in strategy.metadata_policies},
        "NamingPolicy": {item.policy_id for item in strategy.naming_policies},
        "ClassificationPolicy": {item.policy_id for item in strategy.classification_policies},
        "OrganizePolicy": {item.policy_id for item in strategy.organize_policies},
    }
    policy_ids = [item.policy_id for item in strategy.recognition_type_policies]
    if len(policy_ids) != len(set(policy_ids)):
        raise ValueError("recognitionTypePolicies IDs must be unique")
    for rule in strategy.recognition_rules:
        if rule.output_recognition_type_id not in type_ids:
            raise ValueError(
                f"RecognitionRule {rule.rule_id!r} references unknown RecognitionType "
                f"{rule.output_recognition_type_id!r}"
            )
    for policy in strategy.recognition_type_policies:
        referenced_metadata = metadata_by_id.get(policy.metadata_policy_id)
        if referenced_metadata is not None and not referenced_metadata.enabled:
            raise ValueError(
                f"RecognitionTypePolicy {policy.policy_id!r} references disabled "
                f"MetadataPolicy {policy.metadata_policy_id!r}"
            )
        references = (
            ("MetadataPolicy", policy.metadata_policy_id),
            ("NamingPolicy", policy.naming_policy_id),
            ("ClassificationPolicy", policy.classification_policy_id),
            ("OrganizePolicy", policy.organize_policy_id),
        )
        for label, value in references:
            if value not in catalogs[label]:
                raise ValueError(
                    f"RecognitionTypePolicy {policy.policy_id!r} references unknown "
                    f"{label} {value!r}"
                )
