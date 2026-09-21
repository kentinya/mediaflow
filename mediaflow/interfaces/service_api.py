from __future__ import annotations

import copy
import hmac
import json
import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from urllib.parse import parse_qs, quote
from uuid import uuid4

from mediaflow.application.automation import AutomationJobService, ProcessingWorkerService
from mediaflow.application.automation_definition_occurrence import (
    AutomationDefinitionOccurrenceService,
)
from mediaflow.application.automation_task_definition_preview import (
    AutomationTaskDefinitionPreviewService,
)
from mediaflow.application.classification_review import ClassificationReviewService
from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.conflict_resolution import ConfirmationService
from mediaflow.application.dashboard import DashboardService
from mediaflow.application.direct_file_commands import (
    DirectFileCommandService,
    DirectFileError,
)
from mediaflow.application.direct_file_transfers import (
    DirectFileTransferError,
    DirectFileTransferService,
)
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.application.file_catalog import FileCatalogFilter, FileCatalogService
from mediaflow.application.file_index_lifecycle import FileIndexLifecycleService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_recovery_continuation import (
    ManualRecoveryContinuationService,
)
from mediaflow.application.manual_scan import ManualScanError, ManualScanService
from mediaflow.application.metadata_correction_continuation import (
    FileMetadataCorrectionContinuationService,
    MetadataCorrectionContinuationConflict,
)
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.notification_delivery import (
    DELIVERY_LEASE_DEFAULT_SECONDS,
    NotificationDeliveryService,
)
from mediaflow.application.operations_lifecycle import (
    OperationsLifecycleConflict,
    TaskExecutionPath,
    TaskLifecycleService,
    bounded_failure_document,
    bounded_identity_path,
    job_lifecycle_document,
    job_operator_document,
    manual_action_matrix_operator_document,
    manual_execution_operator_document,
    manual_intent_operator_document,
    manual_preview_operator_document,
    manual_scan_operator_document,
    manual_step_error_document,
    require_cancellable,
    task_item_operator_document,
    task_lifecycle_document,
    task_operator_document,
    task_result_operator_document,
)
from mediaflow.application.package_exchange import PackageExchangeService
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.recovery_batch import RecoveryBatchContinuationService
from mediaflow.application.recovery_continuation import RecoveryContinuationService
from mediaflow.application.storage_browser import (
    RuntimeFilesBrowserService,
    StorageBrowserError,
)
from mediaflow.application.system_settings import (
    SystemSettingsService,
    SystemSettingsValidationError,
)
from mediaflow.application.unattended_execution import (
    UnattendedExecutionGrantError,
    UnattendedExecutionGrantService,
)
from mediaflow.application.webhook_test import WebhookTestService, webhook_events_supported
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJobControlConflict,
    AutomationJobStatus,
    AutomationQueueFull,
    AutomationTaskDefinition,
    WorkerReadiness,
    WorkerStatus,
)
from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationFirstDraftConflict,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationVersionConflict,
    ManagedConfigurationStatus,
    ResourceLibrarySaveError,
    RuntimeConfigurationNotConfigured,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.direct_files import (
    MAX_DELETE_PATHS,
    MAX_TRANSFER_PATHS,
    DirectFileOperation,
)
from mediaflow.domain.failure import failure_document
from mediaflow.domain.file_lifecycle import (
    FileIndexLifecycleError,
    OccurrenceState,
    ProcessingDisposition,
)
from mediaflow.domain.library import ScanMode
from mediaflow.domain.logging import LogLevel
from mediaflow.domain.manual_execution import ManualExecutionError, ManualExecutionStatus
from mediaflow.domain.manual_organize import (
    ManualIntentError,
)
from mediaflow.domain.manual_organize_preview import (
    MAX_MANUAL_PREVIEW_ITEMS,
    ManualPreviewError,
)
from mediaflow.domain.manual_safety import redact_manual_text, redact_manual_value
from mediaflow.domain.metadata_correction import (
    MetadataCorrectionContinuation,
    MetadataCorrectionContinuationStatus,
)
from mediaflow.domain.notification import (
    NotificationDeliveryConflict,
    NotificationDeliveryStatus,
)
from mediaflow.domain.organizer import ConflictStrategy
from mediaflow.domain.package_exchange import (
    MAX_CONFIGURATION_PACKAGE_BYTES,
    PackageExchangeError,
)
from mediaflow.domain.recovery import RecoveryAdmissionError, RecoveryAdmissionReason
from mediaflow.domain.recovery_continuation import (
    RecoveryContinuationError,
    RecoveryContinuationReason,
)
from mediaflow.domain.scanner import FileScanStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal, SecurityAuditRecord
from mediaflow.domain.system_settings import (
    SystemSettingsEdit,
)
from mediaflow.domain.task_persistence import (
    FILES_TRANSFER_TASK_COMMAND,
    ConfirmationStatus,
    PersistentTaskStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION
from mediaflow.infrastructure.webhook import UrllibWebhookTransport
from mediaflow.interfaces.operator_ui import ASSETS as OPERATOR_UI_ASSETS
from mediaflow.interfaces.pagination import (
    CursorDirection,
    DecodedCursor,
    decode_directional_cursor,
    encode_cursor,
)
from mediaflow.interfaces.v2_ui import V2_UI_PREFIX, v2_ui_asset

# A submitted Task command filter is a bounded work-kind token; the repository
# matches it against the exact command and its own ``<kind>:<identity>``
# continuation family.
_TASK_COMMAND_FILTER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")

# Historical Task/Job/TaskItem/Result keys that must never leave the API: claim
# and fence evidence, internal scope hints and fingerprint values.  The V2
# Operations projection uses an explicit allowlist on top of this filter.
_HIDDEN_DOCUMENT_FIELDS = frozenset(
    {
        "claim_token",
        "scope_path",
        "source_scope",
        "definition_fingerprint",
        "source_fingerprint",
        "source_occurrence_id",
        # The exact file-lock owner generation is an execution fence, not an
        # operator value: it must never appear in a Files/Operations document.
        "lock_owner_token",
    }
)


def _collection_scope(status: str | None, command: str | None) -> str:
    """Deterministic cursor scope binding the submitted collection filters."""

    return f"status={status or 'all'};command={command or 'all'}"


class ApiPermissionDenied(RuntimeError):
    pass


class _CurrentConfiguredPermissionAuthority:
    """Resolve principal permissions from the current managed configuration."""

    def __init__(self, fallback, configuration_service=None) -> None:
        self._fallback = tuple(fallback)
        self._configuration_service = configuration_service

    def has_permission(self, principal_id: str, permission: str | ApiPermission) -> bool:
        principals = self._current_principals()
        expected = permission.value if isinstance(permission, ApiPermission) else str(permission)
        for principal in principals:
            if principal.principal_id != principal_id:
                continue
            if getattr(principal, "enabled", True) is not True:
                return False
            permissions = getattr(principal, "permissions", ())
            return any(
                item == permission or getattr(item, "value", str(item)) == expected
                for item in permissions
            )
        return False

    def _current_principals(self):
        if self._configuration_service is None:
            return self._fallback
        active = self._configuration_service.active()
        if active is None:
            raise RuntimeError("managed Active configuration is unavailable")
        from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration

        runtime = load_runtime_configuration(active.document)
        definitions = runtime.api_principals
        if not definitions and runtime.api_token_env:
            from mediaflow.domain.security import ApiPrincipalDefinition, ApiRole

            definitions = (
                ApiPrincipalDefinition("legacy-admin", runtime.api_token_env, (ApiRole.ADMIN,)),
            )
        return definitions


@dataclass(frozen=True)
class _ApiRuntimeBinding:
    """One immutable set of config-derived API behavior and its snapshot pin."""

    snapshot_id: str | None
    snapshot_digest: str | None
    jobs: AutomationJobService
    maximum_active_jobs: int
    execution_authorizations: ExecutionAuthorizationService
    remote_execution_enabled: bool
    stale_job_age_seconds: int
    system_status: object | None
    schedules: tuple
    metadata_policies: tuple
    dashboard: DashboardService
    files_browser: RuntimeFilesBrowserService | None = None
    direct_files: DirectFileCommandService | None = None
    direct_transfers: DirectFileTransferService | None = None
    manual_scans: ManualScanService | None = None
    runtime_settings: dict[str, object] | None = None


class MediaFlowApi:
    """Small WSGI transport over persistence and queue application boundaries."""

    #: Deterministic combined page limit for the Operations Automation list:
    #: Active and Draft-only definitions share one bounded page that matches
    #: the frontend normalizer contract (more than 100 items fails closed).
    AUTOMATION_DEFINITIONS_PAGE_LIMIT = 100

    #: Deterministic combined page limit for the Operations Notification list:
    #: Active and Draft-only Webhook definitions share one bounded page that
    #: matches the frontend normalizer contract (more than 100 items fails
    #: closed).
    NOTIFICATION_DEFINITIONS_PAGE_LIMIT = 100

    def __init__(
        self,
        repository,
        bearer_token: str | None,
        schedules=(),
        *,
        principals: tuple[ResolvedApiPrincipal, ...] = (),
        dashboard_resource_library_count: int = 0,
        dashboard_media_library_count: int = 0,
        remote_execution_enabled: bool = False,
        remote_execution_maximum_ttl_seconds: int = 900,
        maximum_active_jobs: int | None = None,
        stale_job_age_seconds: int = 3600,
        system_status=None,
        file_catalog: FileCatalogService | None = None,
        file_index=None,
        file_index_lifecycle: FileIndexLifecycleService | None = None,
        metadata_policies=(),
        configuration_service: ManagedConfigurationService | None = None,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        bootstrap_document: object | None = None,
        metadata_provider_registry_factory=None,
        storage_adapters=None,
        storage_browser_cursor_secret: bytes | str | None = None,
        recovery_snapshot_validator: Callable[[str, str], None] | None = None,
        manual_intent_service: ManualOrganizeIntentService | None = None,
        manual_preview_service: ManualOrganizePreviewService | None = None,
        manual_execution_service: ManualOrganizeExecutionService | None = None,
        manual_recovery_service: ManualRecoveryContinuationService | None = None,
        manual_scan_service: ManualScanService | None = None,
        automation_preview_service: AutomationTaskDefinitionPreviewService | None = None,
        management_only: bool = False,
        worker_service: ProcessingWorkerService | None = None,
        webhook_transport: object | None = None,
    ) -> None:
        if bearer_token and principals:
            raise ValueError("legacy bearer token cannot be combined with API principals")
        if bearer_token:
            principals = (
                ResolvedApiPrincipal("legacy-admin", bearer_token, frozenset(ApiPermission)),
            )
        if not principals:
            raise ValueError("at least one API principal must be configured")
        self._repository = repository
        self._principals = principals
        if (
            isinstance(stale_job_age_seconds, bool)
            or not isinstance(stale_job_age_seconds, int)
            or stale_job_age_seconds < 60
            or stale_job_age_seconds > 604_800
        ):
            raise ValueError("stale Job age must be between 60 and 604800 seconds")
        self._file_catalog = file_catalog
        self._file_index = file_index
        self._file_lifecycle = file_index_lifecycle
        if self._file_lifecycle is None and self._file_catalog is not None:
            self._file_lifecycle = FileIndexLifecycleService(
                self._file_catalog,
                file_index=self._file_index,
                task_repository=repository,
            )
        self._storage_adapters = dict(storage_adapters or {})
        self._storage_browser_cursor_secret = storage_browser_cursor_secret
        self._configuration_service = configuration_service
        self._manual_scans_override = manual_scan_service
        self._maximum_active_jobs_override = maximum_active_jobs
        self._manual_intents = manual_intent_service
        if self._manual_intents is None and self._file_catalog is not None:
            self._manual_intents = ManualOrganizeIntentService(
                repository,
                self._file_catalog,
                configuration_service,
                storage_factory=lambda runtime, ids: runtime.create_storages(
                    external=self._storage_adapters, storage_ids=ids
                ),
            )
        self._manual_previews = manual_preview_service
        if self._manual_previews is None and self._manual_intents is not None:
            self._manual_previews = ManualOrganizePreviewService(
                repository,
                self._manual_intents,
                self._file_catalog,
                file_index=self._file_index,
                configuration_service=configuration_service,
                metadata_provider_registry_factory=metadata_provider_registry_factory,
            )
        self._configuration_objects = (
            ConfigurationObjectService(
                configuration_service,
                metadata_provider_registry_factory=metadata_provider_registry_factory,
                storage_adapters=storage_adapters,
                storage_browser_cursor_secret=storage_browser_cursor_secret,
            )
            if configuration_service is not None
            else None
        )
        self._system_settings = (
            SystemSettingsService(
                configuration_service,
                runtime_snapshot_provider=lambda: self._runtime_settings_evidence(),
            )
            if configuration_service is not None
            else None
        )
        self._package_exchange = (
            PackageExchangeService(configuration_service, self._repository)
            if configuration_service is not None
            else None
        )
        self._webhook_tests = (
            WebhookTestService(
                configuration_service,
                webhook_transport if webhook_transport is not None else UrllibWebhookTransport(),
                audit_repository=self._repository,
            )
            if configuration_service is not None
            else None
        )
        self._notification_deliveries = NotificationDeliveryService(
            self._repository,
            audit_repository=self._repository,
        )
        self._bootstrap_document = bootstrap_document
        from mediaflow.infrastructure.runtime_configuration import (
            is_minimal_management_bootstrap,
        )

        self._management_only = bool(
            management_only
            or getattr(configuration_service, "management_only", False)
            or (
                bootstrap_document is not None
                and is_minimal_management_bootstrap(bootstrap_document)
            )
        )
        self._configuration_snapshot_id = configuration_snapshot_id
        self._configuration_snapshot_digest = configuration_snapshot_digest
        snapshot_validator = (
            configuration_service.validate_runtime_snapshot
            if configuration_service is not None
            else recovery_snapshot_validator
        )
        self._checkpoint_service = ProcessingCheckpointService(
            repository,
            snapshot_validator=snapshot_validator,
        )
        if self._file_catalog is not None:
            self._file_catalog.attach_checkpoint_service(self._checkpoint_service)
        self._manual_execution = manual_execution_service
        if self._manual_execution is None and self._manual_previews is not None:
            self._manual_execution = ManualOrganizeExecutionService(
                repository,
                self._manual_previews,
                self._manual_intents,
                checkpoint_service=self._checkpoint_service,
            )
        self._manual_recovery = manual_recovery_service
        if (
            self._manual_recovery is None
            and self._manual_intents is not None
            and self._manual_previews is not None
            and self._manual_execution is not None
        ):
            self._manual_recovery = ManualRecoveryContinuationService(
                repository,
                intent_service=self._manual_intents,
                preview_service=self._manual_previews,
                execution_service=self._manual_execution,
                checkpoint_service=self._checkpoint_service,
            )
        self._automation_previews = automation_preview_service
        if self._automation_previews is None and configuration_service is not None:
            self._automation_previews = AutomationTaskDefinitionPreviewService(
                repository,
                configuration_service,
                metadata_provider_registry_factory=metadata_provider_registry_factory,
                file_index=file_index,
            )
        self._unattended_grants = UnattendedExecutionGrantService(
            repository,
            preview_service=self._automation_previews,
            permission_authority=_CurrentConfiguredPermissionAuthority(
                self._principals, configuration_service
            ),
        )
        self._automation_occurrences = AutomationDefinitionOccurrenceService(repository)
        self._automation_occurrences.attach_unattended_grant_service(self._unattended_grants)
        self._automation_occurrences.attach_checkpoint_service(self._checkpoint_service)
        self._recovery_admission = RecoveryAdmissionService(
            repository,
            snapshot_validator=snapshot_validator,
            checkpoint_service=self._checkpoint_service,
        )
        self._recovery_continuation = RecoveryContinuationService(
            repository,
            snapshot_validator=snapshot_validator,
            checkpoint_service=self._checkpoint_service,
        )
        self._recovery_batch = RecoveryBatchContinuationService(
            repository,
            continuation_service=self._recovery_continuation,
            admission_service=self._recovery_admission,
        )
        self._worker_service = worker_service
        if self._worker_service is None:
            try:
                has_worker = hasattr(repository, "register_worker")
            except AssertionError:
                has_worker = False
            if has_worker:
                self._worker_service = ProcessingWorkerService(
                    repository,
                    active_configuration_snapshot_id=configuration_snapshot_id,
                    active_configuration_snapshot_digest=configuration_snapshot_digest,
                )
        self._runtime_binding_lock = threading.RLock()
        self._runtime_binding = self._build_runtime_binding(
            snapshot_id=configuration_snapshot_id,
            snapshot_digest=configuration_snapshot_digest,
            maximum_active_jobs=100 if maximum_active_jobs is None else maximum_active_jobs,
            remote_execution_enabled=remote_execution_enabled,
            remote_execution_maximum_ttl_seconds=remote_execution_maximum_ttl_seconds,
            stale_job_age_seconds=stale_job_age_seconds,
            system_status=system_status,
            schedules=tuple(schedules),
            metadata_policies=tuple(metadata_policies),
            resource_library_count=dashboard_resource_library_count,
            media_library_count=dashboard_media_library_count,
        )

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        request_id = str(uuid4())
        try:
            if path == "/health" and method == "GET":
                return self._response(
                    start_response,
                    200,
                    {"status": "ok", "processAlive": True},
                )
            if path in OPERATOR_UI_ASSETS:
                if method != "GET":
                    return self._error(start_response, 405, "method_not_allowed", "GET required")
                content_type, body = OPERATOR_UI_ASSETS[path]
                return self._static_response(start_response, content_type, body)
            if path == V2_UI_PREFIX or path.startswith(V2_UI_PREFIX + "/"):
                if method != "GET":
                    return self._error(start_response, 405, "method_not_allowed", "GET required")
                v2_asset = v2_ui_asset(path)
                if v2_asset is None:
                    return self._error(start_response, 404, "not_found", "route was not found")
                content_type, body = v2_asset
                return self._static_response(start_response, content_type, body)
            if not path.startswith("/api/v1"):
                return self._error(start_response, 404, "not_found", "route was not found")
            principal = self._authenticate(environ)
            if principal is None:
                self._audit(environ, request_id, None, method, path, "authenticate", "denied", 401)
                return self._error(start_response, 401, "unauthorized", "bearer token required")
            if not self._suppress_file_detail_audit(path, method, principal):
                self._audit(environ, request_id, principal, method, path, "request", "started", 0)
            statuses = []

            def capture(status, headers):
                statuses.append(int(status.split()[0]))
                return start_response(status, headers)

            result = self._dispatch(method, path, environ, capture, principal)
            status = statuses[0] if statuses else 500
            self._safe_audit(
                environ,
                request_id,
                principal,
                method,
                path,
                "request",
                "allowed" if status < 400 else "denied",
                status,
            )
            return result
        except ApiPermissionDenied as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "permission",
                "denied",
                403,
            )
            return self._error(start_response, 403, "forbidden", str(error))
        except UnattendedExecutionGrantError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "unattended-execution-grant",
                "denied" if error.status < 500 else "error",
                error.status,
            )
            details = {
                "durableState": error.durable_state,
                "sideEffects": "none",
                "retrySafe": error.retry_safe,
                "nextAction": error.next_action,
                **error.details,
            }
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details=details,
            )
        except RecoveryAdmissionError as error:
            reason = error.reason
            status = (
                404
                if reason
                in {
                    RecoveryAdmissionReason.UNKNOWN_ITEM,
                    RecoveryAdmissionReason.ITEM_TASK_MISMATCH,
                }
                else 503
                if reason is RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE
                else 403
                if reason is RecoveryAdmissionReason.INSUFFICIENT_AUTHORITY
                else 400
                if reason
                in {
                    RecoveryAdmissionReason.INVALID_INPUT,
                    RecoveryAdmissionReason.INVALID_ACTION,
                    RecoveryAdmissionReason.INVALID_VERSION,
                }
                else 409
            )
            not_found = reason in {
                RecoveryAdmissionReason.UNKNOWN_ITEM,
                RecoveryAdmissionReason.ITEM_TASK_MISMATCH,
            }
            details: dict[str, object] = {"sideEffects": "none"}
            if not not_found:
                details["reason"] = reason.value
            if error.current_checkpoint_version and not not_found:
                details["currentCheckpointVersion"] = error.current_checkpoint_version
            if error.existing_request is not None and not not_found:
                details["existingRequest"] = error.existing_request.document()
                details["nextAction"] = error.existing_request.next_action
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "recovery-admission",
                "denied",
                status,
            )
            return self._error(
                start_response,
                status,
                "not_found" if not_found else "recovery_admission_rejected",
                "TaskItem was not found" if not_found else "recovery request was not admitted",
                details=details,
            )
        except RecoveryContinuationError as error:
            reason = error.reason
            status = (
                404
                if reason
                in {
                    RecoveryContinuationReason.UNKNOWN_ITEM,
                    RecoveryContinuationReason.ITEM_TASK_MISMATCH,
                }
                else 503
                if reason is RecoveryContinuationReason.SNAPSHOT_UNAVAILABLE
                else 403
                if reason is RecoveryContinuationReason.INSUFFICIENT_AUTHORITY
                else 400
                if reason
                in {
                    RecoveryContinuationReason.INVALID_INPUT,
                    RecoveryContinuationReason.INVALID_VERSION,
                }
                else 409
            )
            not_found = reason in {
                RecoveryContinuationReason.UNKNOWN_ITEM,
                RecoveryContinuationReason.ITEM_TASK_MISMATCH,
            }
            details: dict[str, object] = {"sideEffects": "none"}
            if not not_found:
                details["reason"] = reason.value
            if error.current_checkpoint_version and not not_found:
                details["currentCheckpointVersion"] = error.current_checkpoint_version
            if error.existing_continuation is not None and not not_found:
                details["existingContinuation"] = error.existing_continuation.document()
                details["nextAction"] = error.existing_continuation.next_action()
            if reason is RecoveryContinuationReason.SNAPSHOT_UNAVAILABLE:
                code = "configuration_unavailable"
                message = "saved configuration snapshot is unavailable"
            else:
                code = "not_found" if not_found else "recovery_continuation_rejected"
                message = (
                    "TaskItem was not found"
                    if not_found
                    else "recovery continuation was not admitted"
                )
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "recovery-continuation",
                "denied",
                status,
            )
            return self._error(
                start_response,
                status,
                code,
                message,
                details=details,
            )
        except AutomationQueueFull as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "request",
                "denied",
                409,
            )
            return self._error(
                start_response,
                409,
                "queue_full",
                str(error),
                details={
                    "durableState": "no new Job or continuation queued",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "wait for active Jobs to finish or cancel one, then resubmit the "
                        "same request and correction identity"
                    ),
                },
            )
        except MetadataCorrectionContinuationConflict as error:
            continuation = error.continuation
            details = {
                "durableState": (
                    "current_continuation_preserved_source_unchanged"
                    if continuation is not None
                    else "correction_preserved_source_unchanged"
                ),
                "sideEffects": "none",
                "retrySafe": True,
                "nextAction": (
                    "open the current linked continuation/Task"
                    if continuation is not None
                    else "refresh the File detail and use the current correction identity"
                ),
            }
            if continuation is not None:
                details["continuationId"] = continuation.continuation_id
                details["jobId"] = continuation.job_id
                details["status"] = continuation.status.value
                details["taskId"] = continuation.new_task_id
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "metadata-correction-continuation",
                "conflict",
                409,
            )
            return self._error(
                start_response,
                409,
                "continuation_conflict",
                str(error),
                details=details,
            )
        except DirectFileError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "files-direct-command",
                "conflict" if error.status < 500 else "error",
                error.status,
            )
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details=error.details,
            )
        except ResourceLibrarySaveError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "resource-library-save",
                "conflict" if error.status < 500 else "error",
                error.status,
            )
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details=error.details,
            )
        except ConfigurationActivationConflict as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "configuration",
                "conflict",
                409,
            )
            is_resource_library_save = path == "/api/v1/resource-libraries" and method == "POST"
            details = {
                key: value
                for key, value in {
                    "revisionId": error.revision_id,
                    "currentRevisionId": error.current_revision_id,
                    "currentVersion": error.current_version,
                    "currentDigest": error.current_digest,
                    "durableState": (
                        "active_winner_preserved"
                        if is_resource_library_save and error.current_revision_id
                        else (
                            "draft_preserved_active_unchanged"
                            if error.current_revision_id
                            else "draft_preserved"
                        )
                    ),
                    "candidateState": ("not_published" if is_resource_library_save else None),
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        error.next_action
                        or "refresh the current Active/Draft, review the diff, and revalidate"
                    ),
                }.items()
                if value is not None
            }
            return self._error(
                start_response,
                409,
                "configuration_conflict",
                str(error),
                details=details,
            )
        except ConfigurationFirstDraftConflict as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "configuration-first-draft",
                "conflict",
                409,
            )
            existing = error.revision.summary() if error.revision is not None else None
            details = {
                key: value
                for key, value in {
                    "revisionId": error.revision_id,
                    "version": error.version,
                    "digest": error.digest,
                    "existingRevision": existing,
                    "durableState": error.durable_state,
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": error.next_action,
                    "resumeAction": (
                        {
                            "method": "GET",
                            "path": (f"/api/v1/configuration/revisions/{error.revision_id}"),
                        }
                        if error.revision_id
                        else None
                    ),
                }.items()
                if value is not None
            }
            return self._error(
                start_response,
                409,
                "configuration_first_draft_conflict",
                str(error),
                details=details,
            )
        except ConfigurationVersionConflict as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "configuration",
                "conflict",
                409,
            )
            is_resource_library_save = path == "/api/v1/resource-libraries" and method == "POST"
            details = {
                key: value
                for key, value in {
                    "revisionId": error.revision_id,
                    "currentVersion": error.current_version,
                    "currentDigest": error.current_digest,
                    "durableState": (
                        "active_winner_preserved"
                        if is_resource_library_save and error.current_version is not None
                        else error.durable_state or "draft_preserved"
                    ),
                    "candidateState": ("not_published" if is_resource_library_save else None),
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": error.next_action
                    or "refresh the Draft, review the current version, and edit again",
                }.items()
                if value is not None
            }
            return self._error(
                start_response,
                409,
                "configuration_version_conflict",
                str(error),
                details=details,
            )
        except NotificationDeliveryConflict as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "notification-recovery",
                "denied",
                409,
            )
            details: dict[str, object] = {
                "deliveryId": (error.delivery.delivery_id if error.delivery is not None else None),
                "action": error.action,
                "durableState": "delivery_preserved_no_change",
                "sideEffects": "none",
                "retrySafe": True,
                "nextAction": (
                    "reload the delivery and inspect its current durable state before "
                    "choosing a recovery action"
                ),
            }
            if error.delivery is not None:
                details["delivery"] = self._notification_deliveries.delivery_document(
                    error.delivery,
                    now=datetime.now(UTC),
                    lease_seconds=self._notification_delivery_lease_seconds(),
                )
            return self._error(
                start_response,
                409,
                "notification_delivery_conflict",
                str(error),
                details=details,
            )
        except RuntimeConfigurationNotConfigured as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "runtime-admission",
                "denied",
                503,
            )
            is_resource_library_save = path == "/api/v1/resource-libraries" and method == "POST"
            return self._error(
                start_response,
                503,
                "runtime_not_configured",
                str(error),
                details={
                    "managementReady": True,
                    "setupRequired": True,
                    "runtimeConfigured": False,
                    "workflowAvailable": False,
                    "durableState": (
                        "no_active_configuration"
                        if is_resource_library_save
                        else "no_workflow_work_created"
                    ),
                    "candidateState": "not_saved" if is_resource_library_save else None,
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "create or resume the first setup Draft, complete guided setup, "
                        "validate it, and activate it"
                    ),
                },
            )
        except SystemSettingsValidationError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "system-settings",
                "validation_failed",
                422,
            )
            return self._error(
                start_response,
                422,
                "system_settings_invalid",
                str(error),
                details={
                    "errors": error.errors,
                    "durableState": "draft_preserved_or_not_created",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": "correct invalid settings values and submit again",
                },
            )
        except ConfigurationObjectReferenced as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "configuration",
                "conflict",
                409,
            )
            return self._error(
                start_response,
                409,
                "configuration_object_referenced",
                str(error),
                details={
                    "objectKind": error.kind.value,
                    "objectId": error.object_id,
                    "referenceCount": error.reference_count,
                    "references": list(error.references),
                    "referenceItems": [item.document() for item in error.reference_items],
                    "referenceEvidence": (
                        error.reference_evidence.document()
                        if error.reference_evidence is not None
                        else {
                            "total": error.reference_count,
                            "items": [{"label": label} for label in error.references],
                            "truncated": error.references_truncated,
                        }
                    ),
                    "referencesTruncated": error.references_truncated,
                    "durableState": "draft_preserved",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": "update the references or cancel deletion",
                },
            )
        except RuntimeSnapshotUnavailable as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "configuration",
                "error",
                503,
            )
            is_resource_library_save = path == "/api/v1/resource-libraries" and method == "POST"
            active_unavailable_state = (
                "no_active_configuration"
                if is_resource_library_save and error.reason == "active_missing"
                else "managed_active_unavailable"
            )
            next_action = (
                (
                    "activate a valid managed configuration, then retry Save"
                    if error.reason == "active_missing"
                    else "repair or replace the unavailable Active configuration, then retry Save"
                )
                if is_resource_library_save
                else "inspect configuration status and stage a replacement Draft"
            )
            details = {
                key: value
                for key, value in {
                    "revisionId": error.revision_id,
                    "version": error.version,
                    "digest": error.digest,
                    "reason": error.reason,
                    "durableState": active_unavailable_state,
                    "candidateState": "not_saved" if is_resource_library_save else None,
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": next_action,
                }.items()
                if value is not None
            }
            return self._error(
                start_response,
                503,
                "configuration_unavailable",
                str(error),
                details=details,
            )
        except PackageExchangeError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "package-exchange",
                "denied" if error.status < 500 else "error",
                error.status,
            )
            return self._error(
                start_response,
                error.status,
                error.code,
                error.message,
                details=error.document(),
            )
        except ManualIntentError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "manual-intent",
                "conflict" if error.status == 409 else "denied" if error.status < 500 else "error",
                error.status,
            )
            details = {"sideEffects": "none", **error.details}
            if error.next_action:
                details.setdefault("nextAction", error.next_action)
            return self._error(
                start_response, error.status, error.code, str(error), details=details
            )
        except ManualScanError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "manual-scan",
                "conflict" if error.status == 409 else "denied" if error.status < 500 else "error",
                error.status,
            )
            details = {
                "durableState": error.durable_state,
                "sideEffects": "none",
                "retrySafe": error.retry_safe,
                "nextAction": error.next_action,
                **error.details,
            }
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details=details,
            )
        except StorageBrowserError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "storage-browser",
                "denied" if error.status < 500 else "error",
                error.status,
            )
            return self._error(
                start_response,
                error.status,
                error.code,
                error.message,
                details=error.details,
            )
        except FileIndexLifecycleError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "file-index-reprocess",
                "conflict" if error.status < 500 else "error",
                error.status,
            )
            details = {
                "durableState": error.durable_state,
                "sideEffects": "none",
                "retrySafe": error.retry_safe,
                "nextAction": error.next_action,
                **error.details,
            }
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details=details,
            )
        except LookupError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "request",
                "error",
                404,
            )
            return self._error(start_response, 404, "not_found", str(error))
        except OperationsLifecycleConflict as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "operations-lifecycle",
                "conflict",
                409,
            )
            return self._error(
                start_response,
                409,
                "lifecycle_conflict",
                str(error),
                details=error.document(),
            )
        except AutomationJobControlConflict as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "operations-lifecycle",
                "conflict",
                409,
            )
            return self._error(
                start_response,
                409,
                "lifecycle_conflict",
                str(error),
                details=error.document(),
            )
        except (ValueError, json.JSONDecodeError) as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "request",
                "denied",
                400,
            )
            return self._error(
                start_response,
                400,
                "invalid_request",
                redact_manual_text(error),
            )
        except Exception:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "request",
                "error",
                500,
            )
            return self._error(
                start_response, 500, "internal_error", "request failed (details redacted)"
            )

    @property
    def _system_status(self):
        """Compatibility diagnostic backed by the current atomic binding."""

        return self._runtime_binding.system_status

    def _dispatch(
        self,
        method: str,
        path: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        parts = [part for part in path.split("/") if part]
        operations_projection = False
        if (
            len(parts) >= 4
            and parts[:3] == ["api", "v1", "operations"]
            and parts[3] in {"tasks", "jobs", "workers"}
        ):
            # The V2 Operations workspace reads one explicit bounded operator
            # projection.  The pre-existing /api/v1/tasks, /api/v1/jobs and
            # /api/v1/workers compatibility documents keep their historical
            # fields for existing clients; this alias never publishes a raw
            # durable error, a fingerprint value or a configured display root.
            operations_projection = True
            parts = ["api", "v1", *parts[3:]]
        if len(parts) >= 3 and parts[:3] == ["api", "v1", "file-index"]:
            # ``/file-index`` remains the explicit V1/background catalog contract.
            # UI-V2 Files uses ResourceLibrary-scoped live Storage routes instead.
            parts[2] = "files"
        if (
            len(parts) >= 3
            and parts[:2] == ["api", "v1"]
            and parts[2]
            in {
                "manual-organize",
                "manual-organize-intents",
            }
        ):
            # Keep the public route aliases on the same application semantics.
            parts[2] = "manual-intents"
        if (
            len(parts) >= 3
            and parts[:2] == ["api", "v1"]
            and parts[2] in {"manual-scans", "manual-scan"}
        ):
            # The versioned ``scans`` route is canonical; these aliases keep older operator
            # links on the same bounded application behavior.
            parts[2] = "scans"
        if (
            len(parts) >= 3
            and parts[:2] == ["api", "v1"]
            and parts[2] in {"previews", "current-source-previews"}
        ):
            # Current-source Preview is the same persisted manual Preview
            # projection.  Keep concise API aliases on one application path.
            parts[2] = "manual-previews"
        configuration_route = parts[:3] == ["api", "v1", "configuration"]
        automation_definition_route = parts[:4] == [
            "api",
            "v1",
            "automation",
            "task-definitions",
        ]
        management_readiness_route = parts == ["api", "v1", "management", "readiness"]
        task_read_route = parts[:3] == ["api", "v1", "tasks"] and method == "GET"
        worker_route = parts[:3] == ["api", "v1", "workers"]
        resource_library_save_route = (
            parts == ["api", "v1", "resource-libraries"] and method == "POST"
        )
        if (
            self._is_management_only_setup()
            and self._is_workflow_producing_route(method, parts)
            and not resource_library_save_route
        ):
            raise RuntimeConfigurationNotConfigured()
        binding = self._runtime_binding
        if (
            not configuration_route
            and not management_readiness_route
            and not automation_definition_route
            and not task_read_route
            and not worker_route
        ):
            binding = self._refresh_configuration_binding()
        # --- V2 Manual Scan/Preview operations routes (bounded, server-bound) ---
        if parts == ["api", "v1", "operations", "manual-actions"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            return self._manual_action_matrix(start_response, environ, principal, binding)
        if parts == ["api", "v1", "operations", "scans"] and method == "POST":
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            self._require_empty_query(environ, "server-bound manual Scan")
            if binding.manual_scans is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Scan service is unavailable",
                    details={
                        "durableState": "no_task_created",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore a valid Active runtime and Task repository, then retry"
                        ),
                    },
                )
            scan = binding.manual_scans.admit_current_document(
                self._document(environ), actor=principal.principal_id
            )
            return self._response(
                start_response,
                202,
                manual_scan_operator_document(
                    {
                        **scan.document(),
                        "taskId": scan.task_id,
                        "scopeKind": scan.scope_kind.value,
                        "scopeId": scan.scope_id,
                        "resourceLibraryId": scan.resource_library_id,
                        "fileId": scan.file_id,
                        "storageId": scan.storage_id,
                        "sourcePath": scan.source_path,
                        "sourceOccurrenceId": scan.source_occurrence_id,
                        "sourceFingerprint": scan.source_fingerprint,
                    },
                    cancel_permitted=ApiPermission.CANCEL_JOB in principal.permissions,
                ),
            )
        if (
            len(parts) == 5
            and parts[:4] == ["api", "v1", "operations", "scans"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if binding.manual_scans is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Scan service is unavailable",
                )
            try:
                limit, cursor = self._manual_scan_detail_page(environ)
            except ValueError:
                # A Scan detail cursor is read-only continuation state. If a
                # browser resumes with an expired or malformed cursor, safely
                # restart this collection at page one while continuing to
                # reject unsupported query fields and invalid page limits.
                values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
                if (
                    set(values).issubset({"itemLimit", "itemCursor"})
                    and len(values.get("itemCursor", [])) == 1
                ):
                    limit = self._parse_bounded_limit(
                        values.get("itemLimit", ["100"])[0], "manual Scan item"
                    )
                    cursor = None
                else:
                    raise
            after = cursor.position if cursor and cursor.direction is CursorDirection.NEXT else None
            before = (
                cursor.position if cursor and cursor.direction is CursorDirection.PREVIOUS else None
            )
            value = binding.manual_scans.detail_document(
                parts[4], limit=limit, after=after, before=before
            )
            items = value.get("items", [])
            has_previous = bool(value.pop("_has_previous_items", False))
            has_next = bool(value.pop("_has_next_items", False))
            value["itemLimit"] = value.pop("item_limit", limit)
            value["itemsTruncated"] = bool(value.pop("items_truncated", False)) or has_next
            value["nextItemCursor"] = self._manual_scan_cursor(
                items, direction=CursorDirection.NEXT
            )
            value["previousItemCursor"] = self._manual_scan_cursor(
                items, direction=CursorDirection.PREVIOUS
            )
            if not has_previous:
                value["previousItemCursor"] = None
            if not has_next:
                value["nextItemCursor"] = None
            return self._response(
                start_response,
                200,
                manual_scan_operator_document(
                    value,
                    cancel_permitted=ApiPermission.CANCEL_JOB in principal.permissions,
                ),
            )
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "operations", "scans"]
            and parts[5] == "cancel"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.CANCEL_JOB)
            self._require_empty_query(environ, "server-bound Scan cancellation")
            self._require_empty_body(environ, "server-bound Scan cancellation")
            if binding.manual_scans is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Scan service is unavailable",
                )
            scan = binding.manual_scans.cancel(parts[4])
            return self._response(
                start_response,
                200,
                manual_scan_operator_document(
                    scan.document(),
                    cancel_permitted=ApiPermission.CANCEL_JOB in principal.permissions,
                ),
            )
        if parts == ["api", "v1", "operations", "previews"] and method == "POST":
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_previews is None or not callable(
                getattr(self._manual_previews, "create_current_from_storage", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "current-source Preview service is unavailable",
                )
            self._require_empty_query(environ, "server-bound current-source Preview")
            document = self._document(environ)
            allowed = {
                "scopeKind",
                "scope",
                "resourceLibraryId",
                "relativePath",
                "path",
                "snapshotId",
                "snapshotDigest",
            }
            if set(document).difference(allowed):
                raise ValueError(
                    "server-bound Preview accepts only ResourceLibrary source identity fields"
                )
            raw_kind = document.get("scopeKind", document.get("scope"))
            if raw_kind == "resourceLibrary":
                raw_kind = "resource_library"
            if raw_kind not in {"file", "resource_library"}:
                raise ValueError("server-bound Preview scope must be file or resource_library")
            relative_path = document.get("relativePath", document.get("path"))
            if raw_kind == "file" and (
                not isinstance(relative_path, str) or not relative_path.strip()
            ):
                raise ValueError("server-bound file Preview requires relativePath")
            if raw_kind == "resource_library" and relative_path not in (None, ""):
                raise ValueError("ResourceLibrary Preview cannot include relativePath")
            for name in ("snapshotId", "snapshotDigest"):
                if name in document and (
                    not isinstance(document[name], str) or not document[name].strip()
                ):
                    raise ValueError(f"server-bound Preview {name} must be a non-empty string")
            preview = self._manual_previews.create_current_from_storage(
                scope_kind=raw_kind,
                resource_library_id=document.get("resourceLibraryId"),
                relative_path=relative_path,
                snapshot_id=document.get("snapshotId"),
                snapshot_digest=document.get("snapshotDigest"),
                actor=principal.principal_id,
            )
            return self._response(
                start_response,
                201,
                manual_preview_operator_document(self._manual_preview_document(preview)),
            )
        if parts == ["api", "v1", "operations", "previews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._manual_previews is None or not callable(
                getattr(self._manual_previews, "list_current", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "current-source Preview service is unavailable",
                )
            values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(values).difference(
                {
                    "scopeKind",
                    "scopeId",
                    "resourceLibraryId",
                    "limit",
                }
            ) or any(len(value) != 1 for value in values.values()):
                raise ValueError("server-bound Preview list query contains unsupported fields")
            limit = self._parse_bounded_limit(values.get("limit", ["100"])[0], "Preview")
            scope_kind = values.get("scopeKind", [None])[0]
            scope_id = values.get("scopeId", [None])[0]
            resource_library_id = values.get("resourceLibraryId", [None])[0]
            if scope_kind == "resourceLibrary":
                scope_kind = "resource_library"
            if resource_library_id is not None and scope_id is not None:
                if scope_kind not in (None, "resource_library"):
                    raise ValueError("server-bound Preview list scope_kind is invalid")
                scope_kind = "resource_library"
                scope_id = resource_library_id
            elif resource_library_id is not None:
                scope_kind = "resource_library"
                scope_id = resource_library_id
            if not scope_kind or not scope_id:
                raise ValueError("server-bound Preview list requires scopeKind and scopeId")
            items = self._manual_previews.list_current(scope_kind, scope_id, limit=limit)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        manual_preview_operator_document(self._manual_preview_document(value))
                        for value in items
                    ],
                    "limit": limit,
                    "total": len(items),
                    "scopeKind": "resourceLibrary"
                    if scope_kind == "resource_library"
                    else scope_kind,
                    "scopeId": scope_id,
                },
            )
        if (
            len(parts) == 5
            and parts[:4] == ["api", "v1", "operations", "previews"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._manual_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "current-source Preview service is unavailable",
                )
            try:
                preview = self._manual_previews.get_readonly(parts[4])
            except ManualPreviewError as error:
                if error.status == 404:
                    return self._error(
                        start_response,
                        404,
                        "preview_not_found",
                        "manual Preview was not found",
                        details={"nextAction": error.next_action},
                    )
                return self._error(
                    start_response,
                    error.status,
                    error.code,
                    str(error),
                    details={"sideEffects": "none", **error.details},
                )
            return self._response(
                start_response,
                200,
                manual_preview_operator_document(self._manual_preview_document(preview)),
            )
        # --- V2 Operations: manual Organize intent, exact Preview, one Execute action ---
        if parts == ["api", "v1", "operations", "organize", "intents"] and method == "POST":
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                    details={
                        "durableState": "no_intent_created",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore a valid Active runtime and Task repository, then retry the "
                            "same bounded selection"
                        ),
                    },
                )
            self._require_empty_query(environ, "operations organize intent")
            document = self._document(environ)
            allowed = {"scopeKind", "scope", "resourceLibraryId", "fileId", "itemIds"}
            if set(document).difference(allowed):
                raise ValueError(
                    "operations organize intent accepts only bounded scope identity fields"
                )
            raw_kind = document.get("scopeKind", document.get("scope"))
            if raw_kind == "resourceLibrary":
                raw_kind = "resource_library"
            if raw_kind not in {"file", "resource_library"}:
                raise ValueError(
                    "operations organize intent scope must be file or resource_library"
                )
            resource_library_id = document.get("resourceLibraryId")
            if not isinstance(resource_library_id, str) or not resource_library_id.strip():
                raise ValueError("operations organize intent requires resourceLibraryId")
            if raw_kind == "file":
                file_id = document.get("fileId")
                if not isinstance(file_id, str) or not file_id.strip():
                    raise ValueError("operations organize intent file scope requires fileId")
                selected: list[object] = [file_id]
            else:
                if document.get("fileId") is not None:
                    raise ValueError(
                        "operations organize intent library scope cannot include fileId"
                    )
                raw_items = document.get("itemIds")
                if not isinstance(raw_items, list) or not raw_items:
                    raise ValueError(
                        "operations organize intent requires itemIds for a library scope"
                    )
                if len(raw_items) > self._manual_intents.MAX_ITEMS:
                    raise ValueError(
                        "operations organize intent selection is over the supported item limit"
                    )
                selected = list(raw_items)
            self._require_organize_selection(selected, resource_library_id)
            try:
                intent = self._manual_intents.create(selected, actor=principal.principal_id)
            except ManualIntentError as error:
                return self._manual_step_error(start_response, error)
            return self._response(
                start_response, 201, self._organize_intent_document(intent, principal)
            )
        if (
            len(parts) == 6
            and parts[:5] == ["api", "v1", "operations", "organize", "intents"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                )
            self._require_empty_query(environ, "operations organize intent detail")
            try:
                intent = self._manual_intents.get(parts[5])
            except ManualIntentError as error:
                return self._manual_step_error(start_response, error)
            return self._response(
                start_response, 200, self._organize_intent_document(intent, principal)
            )
        if (
            len(parts) == 9
            and parts[:5] == ["api", "v1", "operations", "organize", "intents"]
            and parts[6] == "items"
            and parts[8] == "choice"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                )
            self._require_empty_query(environ, "operations organize choice")
            document = self._document(environ)
            allowed = {
                "expectedVersion",
                "expectedItemVersion",
                "recognitionTypeId",
                "metadata",
                "namingPolicyId",
                "classificationPolicyId",
                "organizePolicyId",
            }
            if set(document).difference(allowed) or "expectedVersion" not in document:
                raise ValueError(
                    "operations organize choice requires expectedVersion and bounded choice fields"
                )
            expected_version = document["expectedVersion"]
            if (
                isinstance(expected_version, bool)
                or not isinstance(expected_version, int)
                or expected_version < 1
            ):
                raise ValueError(
                    "operations organize choice expectedVersion must be a positive integer"
                )
            expected_item_version = document.get("expectedItemVersion")
            if expected_item_version is not None and (
                isinstance(expected_item_version, bool)
                or not isinstance(expected_item_version, int)
                or expected_item_version < 1
            ):
                raise ValueError(
                    "operations organize choice expectedItemVersion must be a positive integer"
                )
            patch = {
                name: document[name]
                for name in (
                    "recognitionTypeId",
                    "metadata",
                    "namingPolicyId",
                    "classificationPolicyId",
                    "organizePolicyId",
                )
                if name in document
            }
            if not patch:
                raise ValueError("operations organize choice requires at least one choice field")
            try:
                intent = self._manual_intents.update_choice(
                    parts[5],
                    parts[7],
                    patch,
                    expected_version=expected_version,
                    actor=principal.principal_id,
                    expected_item_version=expected_item_version,
                )
            except ManualIntentError as error:
                return self._manual_step_error(start_response, error)
            operator_document = self._organize_intent_document(intent, principal)
            operator_document["previewRequired"] = True
            return self._response(start_response, 200, operator_document)
        if (
            len(parts) == 7
            and parts[:5] == ["api", "v1", "operations", "organize", "intents"]
            and parts[6] == "previews"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_previews is None or not callable(
                getattr(self._manual_previews, "create", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Preview service is unavailable",
                    details={
                        "durableState": "no_preview_created",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore a valid Active runtime and Preview services, then retry"
                        ),
                    },
                )
            self._require_empty_query(environ, "operations organize preview")
            document = self._document(environ)
            if set(document) != {"expectedVersion"}:
                raise ValueError(
                    "operations organize Preview requires only the current intent version"
                )
            expected_version = document["expectedVersion"]
            if (
                isinstance(expected_version, bool)
                or not isinstance(expected_version, int)
                or expected_version < 1
            ):
                raise ValueError(
                    "operations organize Preview expectedVersion must be a positive integer"
                )
            try:
                preview = self._manual_previews.create(
                    parts[5],
                    None,
                    expected_version=expected_version,
                    actor=principal.principal_id,
                )
            except ManualPreviewError as error:
                return self._manual_step_error(start_response, error)
            return self._response(
                start_response, 201, self._organize_preview_document(preview, principal)
            )
        if (
            len(parts) == 6
            and parts[:5] == ["api", "v1", "operations", "organize", "previews"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._manual_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Preview service is unavailable",
                )
            self._require_empty_query(environ, "operations organize Preview detail")
            try:
                preview = self._manual_previews.get_readonly(parts[5])
            except ManualPreviewError as error:
                return self._manual_step_error(start_response, error)
            return self._response(
                start_response, 200, self._organize_preview_document(preview, principal)
            )
        if (
            len(parts) == 7
            and parts[:5] == ["api", "v1", "operations", "organize", "previews"]
            and parts[6] == "execute"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            self._require_manual_execution(principal)
            if self._manual_execution is None or not callable(
                getattr(self._manual_execution, "begin_web_execution", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual organize execution service is unavailable",
                    details={
                        "durableState": "no_execution_admitted",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore the Active runtime, Task repository and admitted execution "
                            "boundary, then request a fresh Preview"
                        ),
                    },
                )
            self._require_empty_query(environ, "operations organize execute")
            document = self._document(environ)
            allowed = {
                "confirmation",
                "itemIds",
                "expectedIntentVersion",
                "allowOverwrite",
                "allowSourceCleanup",
            }
            if set(document).difference(allowed):
                raise ValueError(
                    "operations organize execute accepts only bounded reviewed selection fields"
                )
            if document.get("confirmation") is not True:
                raise ValueError("operations organize execute requires one explicit confirmation")
            item_ids = document.get("itemIds")
            if not isinstance(item_ids, list) or not item_ids:
                raise ValueError("operations organize execute requires a selected itemIds array")
            if len(item_ids) > self._manual_execution.MAX_ITEMS:
                raise ValueError(
                    "operations organize execute selection is over the supported item limit"
                )
            expected_version = document.get("expectedIntentVersion")
            if (
                isinstance(expected_version, bool)
                or not isinstance(expected_version, int)
                or expected_version < 1
            ):
                raise ValueError(
                    "operations organize execute expectedIntentVersion must be a positive integer"
                )
            for name in ("allowOverwrite", "allowSourceCleanup"):
                if name in document and not isinstance(document[name], bool):
                    raise ValueError(f"operations organize execute {name} must be boolean")
            try:
                execution = self._manual_execution.begin_web_execution(
                    parts[5],
                    item_ids,
                    expected_intent_version=expected_version,
                    actor=principal.principal_id,
                    confirmation=True,
                    allow_overwrite=document.get("allowOverwrite", False),
                    allow_source_cleanup=document.get("allowSourceCleanup", False),
                )
            except ManualExecutionError as error:
                return self._manual_step_error(start_response, error)
            return self._response(
                start_response,
                202 if execution.status is ManualExecutionStatus.ADMITTED else 200,
                self._organize_execution_document(execution),
            )
        if parts == ["api", "v1", "operations", "organize", "executions"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._manual_execution is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual organize execution service is unavailable",
                )
            values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(values).difference({"previewId", "intentId", "limit"}) or any(
                len(value) != 1 for value in values.values()
            ):
                raise ValueError(
                    "operations organize execution list query contains unsupported fields"
                )
            limit = self._parse_bounded_limit(values.get("limit", ["50"])[0], "execution")
            preview_id = values.get("previewId", [None])[0]
            intent_id = values.get("intentId", [None])[0]
            reader = None
            relation = None
            if preview_id:
                reader = getattr(self._manual_execution, "list_for_preview", None)
                relation = preview_id
            elif intent_id:
                reader = getattr(self._manual_execution, "list_for_intent", None)
                relation = intent_id
            if reader is None or relation is None:
                raise ValueError(
                    "operations organize execution list requires previewId or intentId"
                )
            try:
                executions = reader(relation, limit=limit)
            except TypeError:
                executions = reader(relation)
            documents = [
                self._organize_execution_document(value) for value in tuple(executions)[:limit]
            ]
            return self._response(
                start_response,
                200,
                {
                    "journey": "organize",
                    "items": documents,
                    "limit": limit,
                    "total": len(documents),
                    "truncated": len(tuple(executions)) > len(documents),
                },
            )
        if (
            len(parts) == 6
            and parts[:5] == ["api", "v1", "operations", "organize", "executions"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._manual_execution is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual organize execution service is unavailable",
                )
            self._require_empty_query(environ, "operations organize execution detail")
            try:
                execution = self._manual_execution.get(parts[5])
            except ManualExecutionError as error:
                return self._manual_step_error(start_response, error)
            return self._response(start_response, 200, self._organize_execution_document(execution))
        if (
            len(parts) == 7
            and parts[:5] == ["api", "v1", "operations", "organize", "executions"]
            and parts[6] == "file-index-reconciliation"
            and method == "POST"
        ):
            # Display-only recovery for one reconciliation miss: the durable
            # Result is re-applied to a current exact FileIndex occurrence.
            # This never calls Storage and never replays the Organize mutation.
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_execution is None or not callable(
                getattr(self._manual_execution, "reconcile_file_index", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual organize FileIndex reconciliation is unavailable",
                    details={
                        "durableState": "organize_effect_unchanged",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore the manual Organize execution service, then repeat the "
                            "bounded reconciliation; no Organize mutation is replayed"
                        ),
                    },
                )
            self._require_empty_query(environ, "operations organize FileIndex reconciliation")
            document = self._document(environ)
            if set(document) != {"itemId"} or not isinstance(document["itemId"], str):
                raise ValueError(
                    "operations organize FileIndex reconciliation requires only itemId"
                )
            try:
                return self._response(
                    start_response,
                    200,
                    self._manual_execution.reconcile_file_index(
                        parts[5],
                        item_id=document["itemId"],
                        actor=principal.principal_id,
                    ),
                )
            except ManualExecutionError as error:
                return self._manual_step_error(start_response, error)
        if parts == ["api", "v1", "automation", "task-definitions"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._configuration_service is None or self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            active = self._automation_revision(environ)
            if active is None:
                return self._response(
                    start_response,
                    200,
                    {"configuration": None, "items": [], "total": 0, "truncated": False},
                )
            detail = self._configuration_objects.revision_detail(active.revision_id)
            all_items = detail["objects"].get("automationTaskDefinitions", [])
            items = self._automation_occurrences.project_definitions(
                all_items[:100],
                configuration=active.summary(),
            )
            return self._response(
                start_response,
                200,
                {
                    "configuration": active.summary(),
                    "items": items,
                    "total": len(all_items),
                    "truncated": len(all_items) > len(items),
                },
            )
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] in {"grant", "grant-state"}
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "unattended execution grant state")
            active, _raw, definition = self._automation_definition_context(environ, parts[4])
            persisted = self._unattended_grants.get_for_definition(definition.definition_id)
            grant = self._unattended_grants.project(
                definition,
                configuration=active.summary(),
                grant=persisted,
            )
            eligibility = self._automation_grant_eligibility(
                active, definition, principal, persisted=persisted
            )
            return self._response(
                start_response,
                200,
                {
                    "definitionId": parts[4],
                    "configuration": active.summary(),
                    "grant": grant,
                    "unattendedExecutionGrant": grant,
                    "grantEligibility": eligibility,
                    "previewEligibility": eligibility,
                },
            )
        if (
            len(parts) == 7
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "grant"
            and parts[6] == "audit"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            _active, _raw, _definition = self._automation_definition_context(environ, parts[4])
            grant = self._unattended_grants.get_for_definition(parts[4])
            if grant is None:
                raise LookupError(
                    f"unattended execution grant for definition {parts[4]!r} was not found"
                )
            query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(query).difference({"limit"}) or any(len(value) != 1 for value in query.values()):
                raise ValueError("unattended execution grant audit query accepts one limit field")
            limit = self._parse_bounded_limit(
                query.get("limit", ["100"])[0], "unattended execution grant audit"
            )
            return self._response(
                start_response,
                200,
                {
                    "definitionId": parts[4],
                    "grantId": grant.grant_id,
                    "items": [
                        item.document()
                        for item in self._unattended_grants.list_audit(grant.grant_id, limit=limit)
                    ],
                    "limit": limit,
                },
            )
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "grant"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.GRANT_UNATTENDED_EXECUTION)
            self._require_empty_query(environ, "unattended execution grant")
            document = self._document(environ)
            allowed = {
                "revisionId",
                "expectedVersion",
                "confirmation",
                "confirmed",
                "maxItemsPerRun",
                "maxItems",
                "reason",
                "previewId",
            }
            if set(document).difference(allowed):
                raise ValueError("unattended execution grant fields are invalid")
            active, raw, definition = self._automation_definition_context(environ, parts[4])
            self._validate_grant_revision_binding(document, active)
            resource = next(
                (
                    value
                    for value in active.document.get("resourceLibraries", [])
                    if value.get("id") == definition.resource_library_id
                ),
                None,
            )
            if resource is None:
                raise UnattendedExecutionGrantError(
                    "the definition ResourceLibrary is unavailable",
                    code="unattended_execution_resource_unavailable",
                    status=409,
                    next_action="repair the ResourceLibrary reference and run a fresh Preview",
                )
            grant = self._unattended_grants.grant(
                definition,
                configuration_snapshot_id=active.revision_id,
                configuration_snapshot_digest=active.digest,
                configuration_snapshot_version=active.version,
                actor=principal.principal_id,
                principal=principal,
                max_items_per_run=document.get("maxItemsPerRun"),
                max_items=document.get("maxItems"),
                confirmation=document.get("confirmation", False),
                confirmed=document.get("confirmed"),
                reason=document.get("reason"),
                preview_id=document.get("previewId"),
                storage_id=resource.get("storageId"),
            )
            eligibility = self._unattended_grants.project_eligibility(
                definition,
                configuration_snapshot_id=active.revision_id,
                configuration_snapshot_digest=active.digest,
                configuration_snapshot_version=active.version,
                preview_id=grant.preview_id,
                storage_id=resource.get("storageId"),
                max_items_per_run=grant.max_items_per_run,
                principal_id=grant.granting_principal,
            )
            return self._response(
                start_response,
                201,
                {
                    "configuration": active.summary(),
                    "definition": raw,
                    "grant": self._unattended_grants.project(
                        definition,
                        configuration=active.summary(),
                        grant=grant,
                    ),
                    "unattendedExecutionGrant": self._unattended_grants.project(
                        definition,
                        configuration=active.summary(),
                        grant=grant,
                    ),
                    "grantEligibility": eligibility,
                    "previewEligibility": eligibility,
                },
            )
        if (
            (
                len(parts) == 6
                and parts[:4] == ["api", "v1", "automation", "task-definitions"]
                and parts[5] == "revoke"
            )
            or (
                len(parts) == 7
                and parts[:4] == ["api", "v1", "automation", "task-definitions"]
                and parts[5:7] == ["grant", "revoke"]
            )
            or (
                len(parts) == 6
                and parts[:4] == ["api", "v1", "automation", "task-definitions"]
                and parts[5] == "grant"
                and method == "DELETE"
            )
        ) and method in {"POST", "DELETE"}:
            self._require(principal, ApiPermission.GRANT_UNATTENDED_EXECUTION)
            self._require_empty_query(environ, "unattended execution revoke")
            if method == "DELETE":
                self._require_empty_body(environ, "unattended execution revoke")
            document = {} if method == "DELETE" else self._document(environ)
            if set(document).difference({"grantId", "reason"}):
                raise ValueError("unattended execution revoke fields are invalid")
            _active, _raw, _definition = self._automation_definition_context(environ, parts[4])
            grant_id = document.get("grantId")
            if grant_id is not None:
                if not isinstance(grant_id, str) or not grant_id.strip():
                    raise ValueError("unattended execution grantId must be a non-empty string")
                current = self._unattended_grants.get(grant_id)
                if current is None or current.definition_id != parts[4]:
                    raise LookupError(
                        f"unattended execution grant for definition {parts[4]!r} was not found"
                    )
                grant = self._unattended_grants.revoke(
                    grant_id,
                    actor=principal.principal_id,
                    principal=principal,
                    reason=document.get("reason"),
                )
            else:
                grant = self._unattended_grants.revoke(
                    definition_id=parts[4],
                    actor=principal.principal_id,
                    principal=principal,
                    reason=document.get("reason"),
                )
            return self._response(
                start_response,
                200,
                {
                    "definitionId": parts[4],
                    "grant": grant.document(),
                    "unattendedExecutionGrant": self._unattended_grants.project(
                        _definition,
                        configuration=_active.summary(),
                        grant=grant,
                    ),
                },
            )
        if (
            len(parts) == 5
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_service is None or self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            active = self._automation_revision(environ)
            if active is None:
                raise LookupError(f"automationTaskDefinitions {parts[4]!r} was not found")
            detail = self._configuration_objects.revision_detail(active.revision_id)
            item = next(
                (
                    candidate
                    for candidate in detail["objects"].get("automationTaskDefinitions", [])
                    if candidate.get("id") == parts[4]
                ),
                None,
            )
            if item is None:
                raise LookupError(f"automationTaskDefinitions {parts[4]!r} was not found")
            item = self._automation_occurrences.project_definition(
                item,
                configuration=active.summary(),
            )
            return self._response(
                start_response,
                200,
                {"configuration": active.summary(), "definition": item},
            )
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "occurrences"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_service is None or self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            active = self._automation_revision({**environ, "QUERY_STRING": ""})
            if active is None:
                raise LookupError(f"automationTaskDefinitions {parts[4]!r} was not found")
            detail = self._configuration_objects.revision_detail(active.revision_id)
            definition = next(
                (
                    candidate
                    for candidate in detail["objects"].get("automationTaskDefinitions", [])
                    if candidate.get("id") == parts[4]
                ),
                None,
            )
            if definition is None:
                raise LookupError(f"automationTaskDefinitions {parts[4]!r} was not found")
            limit, cursor = self._scoped_page_query(
                environ,
                "automation_definition_occurrences",
                parts[4],
                "automation occurrence",
            )
            values = self._list_page(
                lambda **kwargs: self._automation_occurrences.list(parts[4], **kwargs),
                limit,
                cursor,
            )
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "definitionId": parts[4],
                    "configuration": active.summary(),
                    "items": self._automation_occurrences.project_occurrences(page),
                    "limit": limit,
                    "truncated": has_next,
                    "previous_cursor": self._page_cursor(
                        "automation_definition_occurrences",
                        page,
                        has_previous,
                        CursorDirection.PREVIOUS,
                        scope=parts[4],
                    ),
                    "next_cursor": self._page_cursor(
                        "automation_definition_occurrences",
                        page,
                        has_next,
                        CursorDirection.NEXT,
                        scope=parts[4],
                    ),
                },
            )
        if parts == ["api", "v1", "automation", "task-definitions"] and method == "POST":
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document).difference({"revisionId", "expectedVersion", "object", "definition"}):
                raise ValueError("Automation Task Definition create fields are invalid")
            revision_id = document.get("revisionId")
            expected = document.get("expectedVersion")
            if not isinstance(revision_id, str) or not revision_id:
                raise ValueError("Automation Task Definition revisionId is required")
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if "object" in document and "definition" in document:
                raise ValueError("Automation Task Definition may specify only object")
            value = document.get("object", document.get("definition"))
            if not isinstance(value, dict):
                raise ValueError("Automation Task Definition must be an object")
            revision = self._configuration_objects.mutate(
                revision_id,
                ConfigurationObjectKind.SCHEDULE,
                object_id=None,
                value=value,
                expected_version=expected,
                actor=principal.principal_id,
            )
            values = revision.document.get("automationTaskDefinitions", [])
            response = revision.summary()
            response["configurationRevisionId"] = revision.revision_id
            response["automationTaskDefinition"] = values[-1] if values else None
            if isinstance(value.get("id"), str):
                self._invalidate_automation_previews(
                    value["id"],
                    "the pinned Automation Task Definition was created or replaced",
                )
            return self._response(start_response, 200, response)
        if (
            len(parts) == 5
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and method == "PUT"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document).difference({"revisionId", "expectedVersion", "object", "definition"}):
                raise ValueError("Automation Task Definition update fields are invalid")
            revision_id = document.get("revisionId")
            expected = document.get("expectedVersion")
            if not isinstance(revision_id, str) or not revision_id:
                raise ValueError("Automation Task Definition revisionId is required")
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if "object" in document and "definition" in document:
                raise ValueError("Automation Task Definition may specify only object")
            value = document.get("object", document.get("definition"))
            if not isinstance(value, dict):
                raise ValueError("Automation Task Definition must be an object")
            revision = self._configuration_objects.mutate(
                revision_id,
                ConfigurationObjectKind.SCHEDULE,
                object_id=parts[4],
                value=value,
                expected_version=expected,
                actor=principal.principal_id,
            )
            definition = next(
                (
                    item
                    for item in revision.document.get("automationTaskDefinitions", [])
                    if item.get("id") == parts[4]
                ),
                None,
            )
            response = revision.summary()
            response["configurationRevisionId"] = revision.revision_id
            response["automationTaskDefinition"] = definition
            self._invalidate_automation_previews(
                parts[4],
                "the pinned Automation Task Definition was edited",
            )
            return self._response(start_response, 200, response)
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] in {"copy", "enable", "disable"}
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            revision_id = document.get("revisionId")
            expected = document.get("expectedVersion")
            if not isinstance(revision_id, str) or not revision_id:
                raise ValueError("Automation Task Definition revisionId is required")
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            action = parts[5]
            if action == "copy":
                allowed = {"revisionId", "expectedVersion", "newId", "id", "newName", "name"}
                if set(document).difference(allowed):
                    raise ValueError("Automation Task Definition copy fields are invalid")
                new_id = document.get("newId", document.get("id"))
                new_name = document.get("newName", document.get("name"))
                if new_id is not None and not isinstance(new_id, str):
                    raise ValueError("Automation Task Definition copied id must be a string")
                if new_name is not None and not isinstance(new_name, str):
                    raise ValueError("Automation Task Definition copied name must be a string")
                revision = self._configuration_objects.copy_definition(
                    revision_id,
                    object_id=parts[4],
                    new_object_id=new_id,
                    new_name=new_name,
                    expected_version=expected,
                    actor=principal.principal_id,
                )
            else:
                if set(document) != {"revisionId", "expectedVersion"}:
                    raise ValueError(
                        "Automation Task Definition enable/disable requires revisionId "
                        "and expectedVersion"
                    )
                revision = self._configuration_objects.set_definition_enabled(
                    revision_id,
                    object_id=parts[4],
                    enabled=action == "enable",
                    expected_version=expected,
                    actor=principal.principal_id,
                )
            definitions = revision.document.get("automationTaskDefinitions", [])
            target_id = parts[4] if action != "copy" else None
            definition = (
                next((item for item in definitions if item.get("id") == target_id), None)
                if target_id is not None
                else (definitions[-1] if definitions else None)
            )
            response = revision.summary()
            response["configurationRevisionId"] = revision.revision_id
            response["automationTaskDefinition"] = definition
            self._invalidate_automation_previews(
                parts[4],
                f"the pinned Automation Task Definition was {action}",
            )
            return self._response(start_response, 200, response)
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "preview"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            if self._automation_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "automation Preview service is unavailable",
                )
            document = self._document(environ)
            if set(document).difference({"revisionId"}):
                raise ValueError("automation Preview accepts only an optional revisionId")
            revision_id = document.get("revisionId")
            if revision_id is not None and (
                not isinstance(revision_id, str) or not revision_id.strip()
            ):
                raise ValueError("automation Preview revisionId must be a non-empty string")
            preview = self._automation_previews.create(
                parts[4],
                revision_id=revision_id,
                actor=principal.principal_id,
            )
            return self._response(
                start_response,
                201,
                self._automation_preview_document(preview),
            )
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "previews"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._automation_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "automation Preview service is unavailable",
                )
            query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(query).difference({"limit"}) or any(len(value) != 1 for value in query.values()):
                raise ValueError("automation Preview list query accepts one limit field")
            limit = self._parse_bounded_limit(query.get("limit", ["100"])[0], "automation Preview")
            values = self._automation_previews.list_readonly(parts[4], limit=limit)
            return self._response(
                start_response,
                200,
                {
                    "definitionId": parts[4],
                    "items": [self._automation_preview_document(value) for value in values],
                    "total": len(values),
                    "truncated": False,
                },
            )
        if (
            len(parts) == 7
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "previews"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._automation_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "automation Preview service is unavailable",
                )
            preview = self._automation_previews.get_readonly(parts[6])
            return self._response(
                start_response,
                200,
                self._automation_preview_document(preview),
            )
        if (
            len(parts) == 8
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "previews"
            and parts[7] == "items"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._automation_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "automation Preview service is unavailable",
                )
            query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(query).difference({"limit", "after"}) or any(
                len(value) != 1 for value in query.values()
            ):
                raise ValueError("automation Preview item query accepts limit and after once")
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError as error:
                raise ValueError("automation Preview item limit must be an integer") from error
            if limit < 1 or limit > 500:
                raise ValueError("automation Preview item limit must be between 1 and 500")
            after_value = query.get("after", [None])[0]
            if after_value is not None:
                try:
                    after = int(after_value)
                except ValueError as error:
                    raise ValueError("automation Preview item cursor must be an integer") from error
            else:
                after = None
            items, total, next_after = self._automation_previews.items(
                parts[6], limit=limit, after=after
            )
            return self._response(
                start_response,
                200,
                {
                    "previewId": parts[6],
                    "items": [item.document() for item in items],
                    "total": total,
                    "nextAfter": next_after,
                },
            )
        if parts[:5] == [
            "api",
            "v1",
            "operations",
            "automation",
            "task-definitions",
        ] and method in {"GET", "POST"}:
            return self._automation_operations_projection(
                parts, method, environ, start_response, principal
            )
        if parts[:4] == ["api", "v1", "operations", "notifications"] and method in {
            "GET",
            "POST",
        }:
            return self._notification_operations_projection(
                parts, method, environ, start_response, principal
            )
        if parts == ["api", "v1", "management", "readiness"]:
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require_empty_query(environ, "management readiness")
            self._require(principal, ApiPermission.READ)
            return self._response(
                start_response,
                200,
                self._management_readiness_document(principal),
            )
        if parts == ["api", "v1", "workers", "readiness"]:
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require_empty_query(environ, "worker readiness")
            self._require(principal, ApiPermission.READ)
            if self._worker_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "processing worker service is unavailable",
                )
            return self._response(
                start_response,
                200,
                self._worker_readiness_document(principal, bounded=operations_projection),
            )
        if parts == ["api", "v1", "workers"]:
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            limit = self._parse_bounded_limit(
                parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True).get(
                    "limit", ["50"]
                )[0],
                "worker",
            )
            self._require(principal, ApiPermission.READ)
            if self._worker_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "processing worker service is unavailable",
                )
            return self._response(
                start_response,
                200,
                self._workers_document(principal, limit=limit, bounded=operations_projection),
            )
        if parts == ["api", "v1", "configuration", "status"]:
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require_empty_query(environ, "configuration status")
            self._require(principal, ApiPermission.READ)
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            return self._response(
                start_response,
                200,
                self._configuration_status_document(principal),
            )
        if parts == ["api", "v1", "configuration", "drafts", "first"]:
            if method != "POST":
                return self._error(start_response, 405, "method_not_allowed", "POST required")
            self._require_empty_query(environ, "first setup Draft")
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._optional_document(environ)
            if set(document):
                raise ValueError("first setup Draft does not accept configuration fields")
            revision = self._configuration_service.create_first_draft(
                self._bootstrap_document,
                actor=principal.principal_id,
            )
            response = revision.summary()
            response["created"] = True
            response["nextAction"] = (
                "open the setup Draft and complete guided setup before validation and activation"
            )
            return self._response(start_response, 201, response)
        if parts == ["api", "v1", "configuration", "drafts", "successor"]:
            if method != "POST":
                return self._error(start_response, 405, "method_not_allowed", "POST required")
            self._require_empty_query(environ, "successor Draft")
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            allowed = {"expectedActiveRevisionId", "expectedActiveVersion", "expectedActiveDigest"}
            if set(document).difference(allowed):
                raise ValueError(
                    "successor Draft accepts optional expectedActiveRevisionId, "
                    "expectedActiveVersion, and expectedActiveDigest only"
                )
            expected_revision_id = document.get("expectedActiveRevisionId")
            if expected_revision_id is not None and not isinstance(expected_revision_id, str):
                raise ValueError("expectedActiveRevisionId must be a string")
            expected_version = document.get("expectedActiveVersion")
            if expected_version is not None and (
                isinstance(expected_version, bool) or not isinstance(expected_version, int)
            ):
                raise ValueError("expectedActiveVersion must be an integer")
            expected_digest = document.get("expectedActiveDigest")
            if expected_digest is not None and not isinstance(expected_digest, str):
                raise ValueError("expectedActiveDigest must be a string")
            revision = self._configuration_service.create_successor_draft(
                actor=principal.principal_id,
                expected_active_revision_id=expected_revision_id,
                expected_active_version=expected_version,
                expected_active_digest=expected_digest,
            )
            response = revision.summary()
            response["created"] = True
            response["nextAction"] = (
                "open the successor Draft, edit configuration objects, validate, and activate"
            )
            return self._response(start_response, 201, response)
        if parts == ["api", "v1", "configuration"]:
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require(principal, ApiPermission.READ)
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            return self._response(
                start_response, 200, self._configuration_status_document(principal)
            )
        if parts[:4] == ["api", "v1", "configuration", "packages"]:
            if self._package_exchange is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "configuration package exchange service is unavailable",
                    details={
                        "durableState": "no_package_state_changed",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": ("restore the managed configuration service, then retry"),
                    },
                )
            if parts == ["api", "v1", "configuration", "packages"]:
                if method == "GET":
                    self._require_empty_query(environ, "package exchange status")
                    self._require(principal, ApiPermission.READ)
                    return self._response(
                        start_response,
                        200,
                        self._package_exchange.status_document(),
                    )
                if method == "POST":
                    self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
                    package_value, recovery = self._package_import_request(environ)
                    result = self._package_exchange.import_configuration(
                        package_value,
                        actor=principal.principal_id,
                        recovery=recovery,
                    )
                    return self._response(
                        start_response,
                        201 if result.get("action") == "created" else 200,
                        result,
                    )
                return self._error(
                    start_response, 405, "method_not_allowed", "GET or POST required"
                )
            if len(parts) == 6 and parts[4:6] == ["export", "configuration"] and method == "GET":
                self._require(principal, ApiPermission.READ)
                values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
                if set(values).difference({"revisionId"}) or any(
                    len(value) != 1 for value in values.values()
                ):
                    raise ValueError("configuration package export accepts one optional revisionId")
                revision_id = values.get("revisionId", [None])[0]
                if revision_id is not None and (
                    not isinstance(revision_id, str) or not revision_id.strip()
                ):
                    raise ValueError("configuration package revisionId must be non-empty")
                package = self._package_exchange.export_configuration(
                    actor=principal.principal_id,
                    revision_id=revision_id,
                )
                return self._response(start_response, 200, package)
            if len(parts) == 6 and parts[4:6] == ["export", "results"] and method == "GET":
                self._require(principal, ApiPermission.READ)
                values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
                if set(values).difference({"taskId", "limit"}) or any(
                    len(value) != 1 for value in values.values()
                ):
                    raise ValueError("result package export accepts taskId and one limit field")
                task_id = values.get("taskId", [None])[0]
                if not isinstance(task_id, str) or not task_id.strip():
                    raise ValueError("result package export requires a non-empty taskId")
                try:
                    limit = int(values.get("limit", ["100"])[0])
                except ValueError as error:
                    raise ValueError("result package limit must be an integer") from error
                package = self._package_exchange.export_results(
                    actor=principal.principal_id,
                    task_id=task_id,
                    limit=limit,
                )
                return self._response(start_response, 200, package)
            return self._error(start_response, 404, "not_found", "package route was not found")
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            return self._response(
                start_response,
                200,
                self._configuration_service.detail(parts[4]),
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "naming-preview"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) != {"expectedVersion", "expectedDigest", "policyId", "sample"}:
                raise ValueError(
                    "naming preview requires expectedVersion, expectedDigest, policyId, and sample"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            if not isinstance(document["policyId"], str):
                raise ValueError("NamingPolicy ID is required")
            if not isinstance(document["sample"], dict):
                raise ValueError("naming preview sample must be an object")
            evidence = self._configuration_objects.naming_preview(
                parts[4],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                actor=principal.principal_id,
                policy_id=document["policyId"],
                sample=document["sample"],
            )
            return self._response(start_response, 200, evidence.document())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "destination-precheck"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) not in (
                {
                    "expectedVersion",
                    "expectedDigest",
                    "recognitionType",
                    "sample",
                },
                {
                    "expectedVersion",
                    "expectedDigest",
                    "recognitionType",
                    "samples",
                },
            ):
                raise ValueError(
                    "destination precheck requires expectedVersion, expectedDigest, "
                    "recognitionType, and exactly one of sample or samples"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            if not isinstance(document["recognitionType"], str):
                raise ValueError("destination precheck RecognitionType is required")
            if "sample" in document:
                if not isinstance(document["sample"], dict):
                    raise ValueError("destination precheck sample must be an object")
                evidence = self._configuration_objects.destination_precheck(
                    parts[4],
                    expected_version=expected,
                    expected_digest=document["expectedDigest"],
                    actor=principal.principal_id,
                    recognition_type=document["recognitionType"],
                    sample=document["sample"],
                )
            else:
                raw_samples = document["samples"]
                if not isinstance(raw_samples, list):
                    raise ValueError("destination precheck samples must be an array")
                if not 1 <= len(raw_samples) <= 8:
                    raise ValueError("destination precheck accepts one to eight samples")
                if any(not isinstance(value, dict) for value in raw_samples):
                    raise ValueError("destination precheck sample must be an object")
                evidence = self._configuration_objects.destination_precheck(
                    parts[4],
                    expected_version=expected,
                    expected_digest=document["expectedDigest"],
                    actor=principal.principal_id,
                    recognition_type=document["recognitionType"],
                    samples=raw_samples,
                )
            return self._response(start_response, 200, evidence.document())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "classification-preview"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) != {"expectedVersion", "expectedDigest", "policyId", "sample"}:
                raise ValueError(
                    "classification preview requires expectedVersion, expectedDigest, "
                    "policyId, and sample"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            if not isinstance(document["policyId"], str):
                raise ValueError("ClassificationPolicy ID is required")
            if not isinstance(document["sample"], dict):
                raise ValueError("classification preview sample must be an object")
            evidence = self._configuration_objects.classification_preview(
                parts[4],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                actor=principal.principal_id,
                policy_id=document["policyId"],
                sample=document["sample"],
            )
            return self._response(start_response, 200, evidence.document())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "organize-authority"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) != {"expectedVersion", "expectedDigest", "recognitionType"}:
                raise ValueError(
                    "organize authority requires expectedVersion, expectedDigest, and "
                    "recognitionType"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            if not isinstance(document["recognitionType"], str):
                raise ValueError("organize authority RecognitionType is required")
            evidence = self._configuration_objects.organize_authority(
                parts[4],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                actor=principal.principal_id,
                recognition_type=document["recognitionType"],
            )
            return self._response(start_response, 200, evidence.document())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "destination-preview"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) != {
                "expectedVersion",
                "expectedDigest",
                "recognitionType",
                "sample",
            }:
                raise ValueError(
                    "destination preview requires expectedVersion, expectedDigest, "
                    "recognitionType, and sample"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            if not isinstance(document["recognitionType"], str):
                raise ValueError("destination preview RecognitionType is required")
            if not isinstance(document["sample"], dict):
                raise ValueError("destination preview sample must be an object")
            evidence = self._configuration_objects.destination_preview(
                parts[4],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                actor=principal.principal_id,
                recognition_type=document["recognitionType"],
                sample=document["sample"],
            )
            return self._response(start_response, 200, evidence.document())
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5:] == ["recognition-strategy-test", "metadata-correction"]
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            required = {"expectedVersion", "expectedDigest", "expectedTestedAt", "mediaType"}
            allowed = required | {"query", "year", "providerId"}
            if not required.issubset(document) or set(document).difference(allowed):
                raise ValueError(
                    "Metadata correction requires expectedVersion, expectedDigest, "
                    "expectedTestedAt, mediaType, and exactly one query or providerId"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            evidence = self._configuration_objects.recognition_strategy_correct_metadata(
                parts[4],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                expected_tested_at=document["expectedTestedAt"],
                media_type=document["mediaType"],
                query=document.get("query"),
                year=document.get("year"),
                provider_id=document.get("providerId"),
                actor=principal.principal_id,
            )
            return self._response(start_response, 200, evidence.document())
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5:] == ["recognition-strategy-test", "candidate-selection"]
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            required = {
                "expectedVersion",
                "expectedDigest",
                "expectedTestedAt",
                "candidateRank",
            }
            if set(document) != required:
                raise ValueError(
                    "candidate confirmation requires expectedVersion, expectedDigest, "
                    "expectedTestedAt, and candidateRank"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            evidence = self._configuration_objects.recognition_strategy_select_candidate(
                parts[4],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                expected_tested_at=document["expectedTestedAt"],
                candidate_rank=document["candidateRank"],
                actor=principal.principal_id,
            )
            return self._response(start_response, 200, evidence.document())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "objects"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            return self._response(
                start_response,
                200,
                self._configuration_objects.revision_detail(parts[4]),
            )
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "objects"
            and parts[6] == "storages"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            detail = self._configuration_objects.revision_detail(parts[4])
            items = detail["objects"]["storages"]
            return self._response(
                start_response,
                200,
                {
                    **detail,
                    "items": items,
                    "total": len(items),
                },
            )
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "objects"
            and parts[6] == "storages"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            detail = self._configuration_objects.revision_detail(parts[4])
            storage = next(
                (item for item in detail["objects"]["storages"] if item.get("id") == parts[7]),
                None,
            )
            if storage is None:
                raise LookupError(f"storages {parts[7]!r} was not found")
            return self._response(
                start_response,
                200,
                {**detail, "storage": storage},
            )
        if (
            len(parts) == 9
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5:7] == ["objects", "storages"]
            and parts[8] == "check"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) != {"expectedVersion", "expectedDigest"}:
                raise ValueError("Storage check requires expectedVersion and expectedDigest")
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            evidence = self._configuration_objects.storage_check(
                parts[4],
                storage_id=parts[7],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                actor=principal.principal_id,
            )
            response = self._configuration_objects.storage_check_evidence(parts[4], parts[7])
            return self._response(start_response, 200, response or evidence.document())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "storage-check"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) != {"storageId", "expectedVersion", "expectedDigest"}:
                raise ValueError(
                    "Storage check requires storageId, expectedVersion and expectedDigest"
                )
            storage_id = document["storageId"]
            if not isinstance(storage_id, str) or not storage_id.strip():
                raise ValueError("Storage check storageId is required")
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            evidence = self._configuration_objects.storage_check(
                parts[4],
                storage_id=storage_id,
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                actor=principal.principal_id,
            )
            response = self._configuration_objects.storage_check_evidence(parts[4], storage_id)
            return self._response(start_response, 200, response or evidence.document())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "storage-checks"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            detail = self._configuration_objects.revision_detail(parts[4])
            items = detail.get("storageChecks", [])
            return self._response(
                start_response,
                200,
                {**detail, "items": items, "total": len(items)},
            )
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "storage-checks"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            evidence = self._configuration_objects.storage_check_evidence(parts[4], parts[6])
            if evidence is None:
                raise LookupError(f"Storage check evidence for {parts[6]!r} was not found")
            detail = self._configuration_objects.revision_detail(parts[4])
            return self._response(
                start_response,
                200,
                {**detail, "storageCheck": evidence},
            )
        if (
            len(parts) == 9
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5:7] == ["objects", "storages"]
            and parts[8] == "check"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            evidence = self._configuration_objects.storage_check_evidence(parts[4], parts[7])
            if evidence is None:
                raise LookupError(f"Storage check evidence for {parts[7]!r} was not found")
            return self._response(start_response, 200, evidence)
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "storage-browser"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            query = self._storage_browser_query(environ)
            return self._response(
                start_response,
                200,
                self._configuration_objects.browse_storage(parts[4], **query),
            )
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5:7] == ["storage-browser", "select"]
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            required = {
                "storageId",
                "path",
                "target",
                "libraryId",
                "field",
                "expectedVersion",
                "expectedDigest",
            }
            if set(document) != required:
                raise ValueError(
                    "Storage directory selection requires storageId, path, target, libraryId, "
                    "field, expectedVersion and expectedDigest"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str) or not document["expectedDigest"]:
                raise ValueError("configuration expectedDigest is required")
            for field in ("storageId", "path", "target", "libraryId", "field"):
                if not isinstance(document[field], str):
                    raise ValueError(f"Storage directory selection {field} must be text")
            result = self._configuration_objects.select_storage_directory(
                parts[4],
                storage_id=document["storageId"],
                path=document["path"],
                target=document["target"],
                library_id=document["libraryId"],
                field=document["field"],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                actor=principal.principal_id,
            )
            return self._response(start_response, 200, result)
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "objects"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            kind = self._configuration_object_kind(parts[6])
            document = self._document(environ)
            if set(document) != {"object", "expectedVersion"}:
                raise ValueError(
                    "configuration object mutation requires object and expectedVersion"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            value = document["object"]
            if not isinstance(value, dict):
                raise ValueError("configuration object must be an object")
            if kind is ConfigurationObjectKind.STORAGE:
                # The inspect response is safe to round-trip through edit.  These
                # two fields are projection metadata, not persisted Storage input.
                value = {
                    key: item
                    for key, item in value.items()
                    if key not in {"editability", "secretReadiness"}
                }
            elif kind is ConfigurationObjectKind.WEBHOOK_DEFINITION:
                # Readiness and structural-validity are projection metadata that
                # reflect the current process environment; they are never input.
                value = {
                    key: item
                    for key, item in value.items()
                    if key
                    not in {
                        "secretReadiness",
                        "structuralValid",
                        "validationError",
                    }
                }
            revision = self._configuration_objects.mutate(
                parts[4],
                kind,
                object_id=None,
                value=value,
                expected_version=expected,
                actor=principal.principal_id,
            )
            response = revision.summary()
            if kind is ConfigurationObjectKind.STORAGE:
                storages = self._configuration_objects.revision_detail(revision.revision_id)[
                    "objects"
                ]["storages"]
                response["storage"] = next(
                    (item for item in storages if item.get("id") == value.get("id")),
                    None,
                )
            elif kind is ConfigurationObjectKind.SCHEDULE:
                values = revision.document.get("automationTaskDefinitions", [])
                if values:
                    response["automationTaskDefinition"] = values[-1]
                if isinstance(value.get("id"), str):
                    self._invalidate_automation_previews(
                        value["id"],
                        "the pinned Automation Task Definition was created or replaced",
                    )
            elif kind is ConfigurationObjectKind.WEBHOOK_DEFINITION:
                values = revision.document.get("webhooks", [])
                if values:
                    response["webhook"] = values[-1]
            return self._response(start_response, 200, response)
        if (
            len(parts) == 9
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "objects"
            and parts[8] in {"copy", "enable", "disable"}
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            kind = self._configuration_object_kind(parts[6])
            document = self._document(environ)
            expected = document.get("expectedVersion")
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            action = parts[8]
            label = parts[6][:-1] if parts[6].endswith("s") else parts[6]
            if action == "copy":
                allowed = {"expectedVersion", "newId", "id", "newName", "name"}
                if set(document).difference(allowed):
                    raise ValueError(f"{label} copy fields are invalid")
                new_id = document.get("newId", document.get("id"))
                new_name = document.get("newName", document.get("name"))
                if new_id is not None and not isinstance(new_id, str):
                    raise ValueError(f"{label} copied id must be a string")
                if new_name is not None and not isinstance(new_name, str):
                    raise ValueError(f"{label} copied name must be a string")
                revision = self._configuration_objects.copy_object(
                    parts[4],
                    kind,
                    object_id=parts[7],
                    new_object_id=new_id,
                    new_name=new_name,
                    expected_version=expected,
                    actor=principal.principal_id,
                )
            else:
                if set(document) != {"expectedVersion"}:
                    raise ValueError(f"{label} enable/disable requires expectedVersion")
                revision = self._configuration_objects.set_object_enabled(
                    parts[4],
                    kind,
                    object_id=parts[7],
                    enabled=action == "enable",
                    expected_version=expected,
                    actor=principal.principal_id,
                )
            response = revision.summary()
            section = ConfigurationObjectService._SECTIONS.get(kind, parts[6])
            items = revision.document.get(section) if section in revision.document else None
            updated = None
            if items:
                updated = (
                    items[-1]
                    if action == "copy"
                    else next((item for item in items if item.get("id") == parts[7]), None)
                )
            if kind is ConfigurationObjectKind.STORAGE:
                response["storage"] = updated
            elif kind is ConfigurationObjectKind.SCHEDULE:
                if updated is not None:
                    response["automationTaskDefinition"] = updated
                self._invalidate_automation_previews(
                    parts[7],
                    f"the pinned Automation Task Definition was {action}",
                )
            elif updated is not None:
                response["object"] = updated
            return self._response(start_response, 200, response)
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "objects"
            and method == "PUT"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            kind = self._configuration_object_kind(parts[6])
            document = self._document(environ)
            if set(document) != {"object", "expectedVersion"}:
                raise ValueError("configuration object update requires object and expectedVersion")
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            value = document["object"]
            if not isinstance(value, dict):
                raise ValueError("configuration object must be an object")
            if kind is ConfigurationObjectKind.STORAGE:
                value = {
                    key: item
                    for key, item in value.items()
                    if key not in {"editability", "secretReadiness"}
                }
            elif kind is ConfigurationObjectKind.WEBHOOK_DEFINITION:
                value = {
                    key: item
                    for key, item in value.items()
                    if key
                    not in {
                        "secretReadiness",
                        "structuralValid",
                        "validationError",
                    }
                }
            revision = self._configuration_objects.mutate(
                parts[4],
                kind,
                object_id=parts[7],
                value=value,
                expected_version=expected,
                actor=principal.principal_id,
            )
            response = revision.summary()
            if kind is ConfigurationObjectKind.STORAGE:
                storages = self._configuration_objects.revision_detail(revision.revision_id)[
                    "objects"
                ]["storages"]
                response["storage"] = next(
                    (item for item in storages if item.get("id") == parts[7]),
                    None,
                )
            elif kind is ConfigurationObjectKind.SCHEDULE:
                response["automationTaskDefinition"] = next(
                    (
                        item
                        for item in revision.document.get("automationTaskDefinitions", [])
                        if item.get("id") == parts[7]
                    ),
                    None,
                )
                self._invalidate_automation_previews(
                    parts[7],
                    "the pinned Automation Task Definition was edited",
                )
            elif kind is ConfigurationObjectKind.WEBHOOK_DEFINITION:
                response["webhook"] = next(
                    (
                        item
                        for item in revision.document.get("webhooks", [])
                        if item.get("id") == parts[7]
                    ),
                    None,
                )
            return self._response(start_response, 200, response)
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "objects"
            and method == "DELETE"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            kind = self._configuration_object_kind(parts[6])
            document = self._document(environ)
            if set(document) != {"expectedVersion"}:
                raise ValueError("configuration object deletion requires expectedVersion")
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            revision = self._configuration_objects.mutate(
                parts[4],
                kind,
                object_id=parts[7],
                value=None,
                expected_version=expected,
                actor=principal.principal_id,
                delete=True,
            )
            return self._response(start_response, 200, revision.summary())
        if (
            len(parts) == 9
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5:7] == ["objects", "webhooks"]
            and parts[8] == "test"
            and method == "POST"
        ):
            # Explicit bounded Webhook test against the exact managed revision.
            # It sends one signed request, never enqueues a delivery, never
            # retries and never mutates configuration, Storage or media work.
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._webhook_tests is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed Webhook test service is unavailable",
                )
            document = self._document(environ)
            if set(document) != {"expectedVersion", "expectedDigest"}:
                raise ValueError("Webhook test requires expectedVersion and expectedDigest")
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("Webhook test expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("Webhook test expectedDigest is required")
            result = self._webhook_tests.test(
                parts[4],
                parts[7],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                actor=principal.principal_id,
            )
            return self._response(start_response, 200, result)
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "local-setup-check"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            allowed = {"expectedVersion", "expectedDigest", "resourceLibraryId", "mediaLibraryId"}
            if set(document).difference(allowed):
                raise ValueError("Local setup check contains unsupported fields")
            expected = document.get("expectedVersion")
            digest = document.get("expectedDigest")
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(digest, str):
                raise ValueError("configuration expectedDigest is required")
            evidence = self._configuration_objects.local_check(
                parts[4],
                expected_version=expected,
                expected_digest=digest,
                actor=principal.principal_id,
                resource_library_id=document.get("resourceLibraryId"),
                media_library_id=document.get("mediaLibraryId"),
            )
            return self._response(start_response, 200, evidence.document())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "recognition-strategy-test"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            required = {
                "expectedVersion",
                "expectedDigest",
                "resourceLibraryId",
                "syntheticPath",
            }
            allowed = required | {"liveMetadata"}
            if not required.issubset(document) or set(document).difference(allowed):
                raise ValueError(
                    "Recognition Strategy Test requires expectedVersion, expectedDigest, "
                    "resourceLibraryId, syntheticPath, and optional liveMetadata"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["expectedDigest"], str):
                raise ValueError("configuration expectedDigest is required")
            live_metadata = document.get("liveMetadata", False)
            if not isinstance(live_metadata, bool):
                raise ValueError("Recognition Strategy Test liveMetadata must be a boolean")
            evidence = self._configuration_objects.recognition_strategy_test(
                parts[4],
                expected_version=expected,
                expected_digest=document["expectedDigest"],
                actor=principal.principal_id,
                resource_library_id=document["resourceLibraryId"],
                synthetic_path=document["syntheticPath"],
                live_metadata=live_metadata,
            )
            return self._response(start_response, 200, evidence.document())
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and method == "PUT"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) != {"document", "expectedVersion"}:
                raise ValueError("configuration Draft edit requires document and expectedVersion")
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            if not isinstance(document["document"], dict):
                raise ValueError("configuration Draft document must be an object")
            revision = self._configuration_service.edit_draft(
                parts[4],
                document["document"],
                expected_version=expected,
                actor=principal.principal_id,
            )
            return self._response(start_response, 200, revision.summary())
        if parts == ["api", "v1", "configuration", "drafts"] and method == "POST":
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) == {"source"} and document.get("source") in {
                "current",
                "active",
                "successor",
            }:
                draft_document = self._configuration_service.current_document(
                    self._bootstrap_document
                )
            elif set(document) == {"document"} and isinstance(document["document"], dict):
                draft_document = document["document"]
            else:
                raise ValueError("configuration Draft import requires a document object")
            revision = self._configuration_service.import_draft(
                draft_document, actor=principal.principal_id, source="api"
            )
            return self._response(start_response, 201, revision.summary())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] in {"validate", "activate"}
            and method == "POST"
        ):
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if parts[5] == "validate":
                self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
                if document:
                    raise ValueError("configuration validation does not accept request fields")
                revision = self._configuration_service.validate(
                    parts[4], actor=principal.principal_id
                )
                return self._response(start_response, 200, revision.summary())
            self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
            allowed = {"expectedVersion", "checked"}
            if set(document).difference(allowed) or "expectedVersion" not in document:
                raise ValueError(
                    "configuration activation requires expectedVersion and optional checked"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            checked = document.get("checked", False)
            if not isinstance(checked, bool):
                raise ValueError("configuration activation checked must be boolean")
            if checked:
                if self._configuration_objects is None:
                    return self._error(
                        start_response,
                        503,
                        "service_unavailable",
                        "managed configuration object service is unavailable",
                    )
                revision = self._configuration_objects.activate_checked(
                    parts[4], expected_version=expected, actor=principal.principal_id
                )
            else:
                revision = self._configuration_service.activate(
                    parts[4], expected_version=expected, actor=principal.principal_id
                )
            self._refresh_configuration_binding()
            return self._response(start_response, 200, revision.summary())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "successor"
            and method == "POST"
        ):
            self._require_empty_query(environ, "successor Draft")
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._optional_document(environ)
            allowed = {"expectedActiveRevisionId", "expectedActiveVersion", "expectedActiveDigest"}
            if set(document).difference(allowed):
                raise ValueError(
                    "successor Draft from a specific revision accepts optional "
                    "expectedActiveRevisionId, expectedActiveVersion, and expectedActiveDigest only"
                )
            if (
                "expectedActiveRevisionId" in document
                and document["expectedActiveRevisionId"] != parts[4]
            ):
                raise ValueError(
                    "expectedActiveRevisionId in request body does not match revision ID in URL"
                )
            expected_version = document.get("expectedActiveVersion")
            if expected_version is not None and (
                isinstance(expected_version, bool) or not isinstance(expected_version, int)
            ):
                raise ValueError("expectedActiveVersion must be an integer")
            expected_digest = document.get("expectedActiveDigest")
            if expected_digest is not None and not isinstance(expected_digest, str):
                raise ValueError("expectedActiveDigest must be a string")
            revision = self._configuration_service.create_successor_draft(
                actor=principal.principal_id,
                expected_active_revision_id=parts[4],
                expected_active_version=expected_version,
                expected_active_digest=expected_digest,
            )
            response = revision.summary()
            response["created"] = True
            response["nextAction"] = (
                "open the successor Draft, edit configuration objects, validate, and activate"
            )
            return self._response(start_response, 201, response)
        if parts == ["api", "v1", "resource-libraries"] and method == "POST":
            self._require_empty_query(environ, "Files ResourceLibrary Save")
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration object service is unavailable",
                )
            document = self._document(environ)
            allowed = {"resourceLibraryId", "name", "enabled", "storageId", "storagePath"}
            if set(document) != allowed:
                raise ValueError(
                    "ResourceLibrary Save requires only resourceLibraryId, name, enabled, "
                    "storageId, and storagePath"
                )
            candidate = {
                "id": document["resourceLibraryId"],
                "name": document["name"],
                "enabled": document["enabled"],
                "storageId": document["storageId"],
                "storagePath": document["storagePath"],
            }
            prepared: list[_ApiRuntimeBinding] = []
            with self._runtime_binding_lock:
                # Pin the process to the same save-time Active before any
                # successor work begins.  A failed Save must leave a usable
                # old binding, while a competing winner can be refreshed
                # explicitly below if publication loses the race.
                self._refresh_configuration_binding_locked()

                def before_publish(revision) -> None:
                    prepared.append(self._prepare_runtime_binding_for_revision(revision))

                try:
                    revision = self._configuration_objects.save_resource_library(
                        candidate,
                        actor=principal.principal_id,
                        before_publish=before_publish,
                    )
                except (ConfigurationActivationConflict, ConfigurationVersionConflict):
                    # The repository has authoritative concurrency fencing;
                    # if another Active won, make this process consume that
                    # winner before returning the stale/conflict result.  The
                    # successor-create path reports the same race as a version
                    # conflict, while the publish path reports activation
                    # conflict.
                    self._refresh_configuration_binding_locked()
                    raise
                if len(prepared) != 1:
                    raise ResourceLibrarySaveError(
                        "resource_library_runtime_failed",
                        "the successor runtime binding was not prepared; the previous Active "
                        "remains in use",
                        status=503,
                        revision_id=revision.revision_id,
                        durable_state="active_preserved",
                        next_action="refresh the current Active configuration and retry Save",
                    )
                self._publish_runtime_binding(prepared[0])
            resource = next(
                item
                for item in self._configuration_objects._canonical_objects(
                    revision.document, "resourceLibraries"
                )
                if item.get("id") == candidate["id"]
            )
            return self._response(
                start_response,
                200,
                {
                    "resourceLibrary": {
                        "id": resource["id"],
                        "name": resource["name"],
                        "storageId": resource["storageId"],
                        "storagePath": resource.get("storagePath", ""),
                        "enabled": resource["enabled"],
                    },
                    "active": revision.summary(),
                    "configuration": {
                        "authority": "MANAGED",
                        "revisionId": revision.revision_id,
                        "version": revision.version,
                        "digest": revision.digest,
                    },
                    "sideEffects": "configuration_only",
                    "nextAction": (
                        "refresh the Active ResourceLibrary list and browse the selected library"
                        if resource["enabled"]
                        else "refresh the Active ResourceLibrary list; this disabled library "
                        "is not browseable"
                    ),
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "removal-preview"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration object service is unavailable",
                )
            self._require_empty_query(environ, "ResourceLibrary removal preview")
            document = self._configuration_objects.resource_library_removal_evidence(parts[3])
            return self._response(start_response, 200, document)
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and method == "DELETE"
        ):
            self._require_empty_query(environ, "ResourceLibrary removal")
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration object service is unavailable",
                )
            # The removal confirmation must carry the exact Active revision
            # identity the operator previewed; the backend rejects stale,
            # mismatched, missing or disabled selections before any successor
            # work begins.
            confirmation = self._document(environ)
            required_confirmation = {
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
                "expectedLibraryId",
            }
            if set(confirmation) != required_confirmation:
                raise ValueError(
                    "ResourceLibrary removal requires the previewed Active revision "
                    "evidence and the selected library identity"
                )
            prepared: list[_ApiRuntimeBinding] = []
            with self._runtime_binding_lock:
                # Pin the process to the removal-time Active before any
                # successor work begins; a failed removal must leave a usable
                # old binding, and a competing winner is refreshed explicitly.
                self._refresh_configuration_binding_locked()

                def before_publish(revision) -> None:
                    prepared.append(self._prepare_runtime_binding_for_revision(revision))

                try:
                    revision = self._configuration_objects.remove_resource_library(
                        parts[3],
                        actor=principal.principal_id,
                        expected_revision_id=confirmation["expectedRevisionId"],
                        expected_version=confirmation["expectedVersion"],
                        expected_digest=confirmation["expectedDigest"],
                        expected_library_id=confirmation["expectedLibraryId"],
                        before_publish=before_publish,
                    )
                except (ConfigurationActivationConflict, ConfigurationVersionConflict):
                    self._refresh_configuration_binding_locked()
                    raise
                if len(prepared) != 1:
                    raise ResourceLibrarySaveError(
                        "resource_library_runtime_failed",
                        "the successor runtime binding was not prepared; the previous Active "
                        "remains in use",
                        status=503,
                        revision_id=revision.revision_id,
                        durable_state="active_preserved",
                        next_action="refresh the current Active configuration and retry removal",
                    )
                self._publish_runtime_binding(prepared[0])
            return self._response(
                start_response,
                200,
                {
                    "removed": {"id": parts[3]},
                    "active": revision.summary(),
                    "configuration": {
                        "authority": "MANAGED",
                        "revisionId": revision.revision_id,
                        "version": revision.version,
                        "digest": revision.digest,
                    },
                    "sideEffects": "configuration_only",
                    "nextAction": (
                        "refresh the Active ResourceLibrary list and select another enabled library"
                    ),
                },
            )
        if parts == ["api", "v1", "system", "status"]:
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require_empty_query(environ, "system status")
            self._require(principal, ApiPermission.READ)
            if binding.system_status is None:
                if self._management_only and self._configuration_service is not None:
                    from mediaflow.infrastructure.configuration_snapshot import (
                        build_management_configuration_snapshot,
                    )

                    return self._response(
                        start_response,
                        200,
                        build_management_configuration_snapshot(
                            self._configuration_service.status_document()
                        ).as_document(),
                    )
                return self._error(
                    start_response, 503, "service_unavailable", "system status is unavailable"
                )
            return self._response(start_response, 200, binding.system_status.as_document())
        # GET /api/v1/system/settings
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "system"]
            and parts[3] == "settings"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._system_settings is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "system settings service is unavailable",
                )
            query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            revision_id = query.get("revisionId", [None])[0]
            try:
                settings = self._system_settings.read_draft_or_active(revision_id)
            except RuntimeSnapshotUnavailable as error:
                return self._error(
                    start_response,
                    503,
                    "system_settings_unavailable",
                    str(error),
                    details={
                        "durableState": "system_settings_not_available",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": "activate a managed configuration to access system settings",
                    },
                )
            projection = settings.as_projection()
            projection["authority"] = (
                "MANAGED"
                if settings.is_active
                else ("MANAGEMENT_BOOTSTRAP" if self._management_only else "MANAGED")
            )
            # Include consumption evidence.
            evidence = self._system_settings.consumption_evidence()
            projection["consumption"] = evidence
            return self._response(start_response, 200, projection)

        # PUT /api/v1/system/settings
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "system"]
            and parts[3] == "settings"
            and method == "PUT"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._system_settings is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "system settings service is unavailable",
                )
            document = self._document(environ)
            expected_version = document.get("expectedVersion")
            if expected_version is not None and (
                isinstance(expected_version, bool) or not isinstance(expected_version, int)
            ):
                raise ValueError("expectedVersion must be an integer")
            edits = self._extract_system_settings_edits(document)
            if expected_version is not None:
                # Edit an existing Draft by revision ID.
                revision_id = document.get("revisionId")
                if not isinstance(revision_id, str) or not revision_id:
                    raise ValueError("revisionId is required when expectedVersion is provided")
                updated = self._system_settings.edit_draft(
                    revision_id,
                    edits=edits,
                    expected_version=expected_version,
                    actor=principal.principal_id,
                )
                status_code = 200
            else:
                # Create successor Draft from Active and apply edits.
                updated = self._system_settings.edit(
                    edits=edits,
                    actor=principal.principal_id,
                    expected_active_revision_id=document.get("expectedActiveRevisionId"),
                    expected_active_version=(
                        int(document["expectedActiveVersion"])
                        if document.get("expectedActiveVersion") is not None
                        else None
                    ),
                    expected_active_digest=document.get("expectedActiveDigest"),
                )
                status_code = 201
            response = updated.as_projection()
            response["authority"] = "MANAGED"
            response["created"] = expected_version is None
            response["consumption"] = self._system_settings.consumption_evidence()
            return self._response(start_response, status_code, response)

        # GET /api/v1/configuration/revisions/<revision_id>/settings
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "settings"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._system_settings is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "system settings service is unavailable",
                )
            revision_id = parts[4]
            try:
                settings = self._system_settings.read_draft_or_active(revision_id)
            except RuntimeSnapshotUnavailable as error:
                return self._error(
                    start_response,
                    404 if "not found" in str(error).lower() else 503,
                    "system_settings_unavailable",
                    str(error),
                    details={
                        "durableState": "revision_not_available",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": "check the revision ID and try again",
                    },
                )
            projection = settings.as_projection()
            projection["authority"] = "MANAGED"
            projection["consumption"] = self._system_settings.consumption_evidence()
            return self._response(start_response, 200, projection)

        # PUT /api/v1/configuration/revisions/<revision_id>/settings
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "settings"
            and method == "PUT"
        ):
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._system_settings is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "system settings service is unavailable",
                )
            document = self._document(environ)
            expected_version = document.get("expectedVersion")
            if isinstance(expected_version, bool) or not isinstance(expected_version, int):
                raise ValueError("expectedVersion must be an integer")
            edits = self._extract_system_settings_edits(document)
            updated = self._system_settings.edit_draft(
                parts[4],
                edits=edits,
                expected_version=expected_version,
                actor=principal.principal_id,
            )
            response = updated.as_projection()
            response["authority"] = "MANAGED"
            response["consumption"] = self._system_settings.consumption_evidence()
            return self._response(start_response, 200, response)

        if parts == ["api", "v1", "scans"] and method == "POST":
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            self._require_empty_query(environ, "manual Scan")
            if binding.manual_scans is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Scan service is unavailable",
                    details={
                        "durableState": "no_task_created",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore a valid Active runtime and Task repository, then retry"
                        ),
                    },
                )
            scan = binding.manual_scans.admit_document(
                self._document(environ), actor=principal.principal_id
            )
            return self._response(
                start_response,
                202,
                {
                    **scan.document(),
                    "task_id": scan.task_id,
                    "scope_kind": scan.scope_kind.value,
                    "resource_library_id": scan.resource_library_id,
                    "file_id": scan.file_id,
                    "source_occurrence_id": scan.source_occurrence_id,
                    "source_fingerprint": scan.source_fingerprint,
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "scans"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if binding.manual_scans is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Scan service is unavailable",
                )
            limit, cursor = self._manual_scan_detail_page(environ)
            after = cursor.position if cursor and cursor.direction is CursorDirection.NEXT else None
            before = (
                cursor.position if cursor and cursor.direction is CursorDirection.PREVIOUS else None
            )
            value = binding.manual_scans.detail_document(
                parts[3], limit=limit, after=after, before=before
            )
            items = value.get("items", [])
            has_previous = bool(value.pop("_has_previous_items", False))
            has_next = bool(value.pop("_has_next_items", False))
            value["previous_item_cursor"] = None
            value["next_item_cursor"] = None
            # The manual Scan service already bounds item pages.  Cursor links use the same
            # signed task-item cursor contract as the generic Task detail surface.
            if has_previous:
                value["previous_item_cursor"] = self._manual_scan_cursor(
                    items, direction=CursorDirection.PREVIOUS
                )
            if has_next:
                value["next_item_cursor"] = self._manual_scan_cursor(
                    items, direction=CursorDirection.NEXT
                )
            return self._response(start_response, 200, value)
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "scans"]
            and parts[4] == "cancel"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.CANCEL_JOB)
            self._require_empty_query(environ, "manual Scan cancellation")
            self._require_empty_body(environ, "manual Scan cancellation")
            if binding.manual_scans is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Scan service is unavailable",
                )
            scan = binding.manual_scans.cancel(parts[3])
            return self._response(start_response, 200, scan.document())
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if binding.files_browser is None:
                return self._files_browser_unavailable(start_response)
            query = self._resource_library_files_query(environ, parts[3])
            return self._response(
                start_response,
                200,
                binding.files_browser.browse_resource_library(**query),
            )
        if parts == ["api", "v1", "resource-libraries", "files"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if binding.files_browser is None:
                return self._files_browser_unavailable(start_response)
            self._require_empty_query(environ, "ResourceLibrary Files list")
            return self._response(
                start_response, 200, binding.files_browser.list_resource_libraries()
            )
        if (
            parts == ["api", "v1", "storage", "files"] or parts == ["api", "v1", "files", "browse"]
        ) and method == "GET":
            self._require(principal, ApiPermission.READ)
            if binding.files_browser is None:
                return self._files_browser_unavailable(start_response)
            query = self._runtime_files_query(environ)
            return self._response(
                start_response,
                200,
                binding.files_browser.browse(**query),
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "text"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if binding.direct_files is None:
                return self._files_browser_unavailable(start_response)
            path = self._files_direct_text_query(environ)
            document = binding.direct_files.read_text(resource_library_id=parts[3], path=path)
            return self._response(
                start_response,
                200,
                {
                    "resourceLibraryId": document.resource_library_id,
                    "path": document.path,
                    "content": document.content,
                    "evidence": document.evidence.document(),
                    "sideEffects": "none",
                    "retrySafe": True,
                },
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "delete-impact"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if binding.direct_files is None:
                return self._files_browser_unavailable(start_response)
            paths = self._files_delete_impact_query(environ)
            document = binding.direct_files.delete_impact(resource_library_id=parts[3], paths=paths)
            response = document.document()
            response["sideEffects"] = "none"
            response["retrySafe"] = True
            response["nextAction"] = (
                "confirm this exact impact to run the bounded Delete"
                if document.entries
                else "the selection is empty; refresh the directory and retry"
            )
            return self._response(start_response, 200, response)
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "rename-evidence"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if binding.direct_files is None:
                return self._files_browser_unavailable(start_response)
            path = self._files_direct_rename_evidence_query(environ)
            evidence = binding.direct_files.rename_evidence(resource_library_id=parts[3], path=path)
            response = evidence.document()
            response["sideEffects"] = "none"
            response["retrySafe"] = True
            response["nextAction"] = (
                "submit the Rename with this exact evidence, or refresh the directory "
                "if the entry changed in the meantime"
            )
            return self._response(start_response, 200, response)
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "transfer-impact"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if binding.direct_transfers is None:
                return self._files_browser_unavailable(start_response)
            query = self._files_transfer_impact_query(environ)
            impact = binding.direct_transfers.transfer_impact(
                resource_library_id=parts[3],
                paths=query["paths"],
                destination_resource_library_id=query["destination"],
                destination_directory=query["destination_path"],
                operation=query["operation"],
                conflict_mode=query["conflict_mode"],
            )
            return self._response(start_response, 200, impact.document())
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "transfers"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.EXECUTE_MANUAL_ORGANIZE)
            if binding.direct_transfers is None:
                return self._files_browser_unavailable(start_response)
            self._require_empty_query(environ, "Files transfer")
            document = self._document(environ)
            required = {
                "operation",
                "paths",
                "destinationResourceLibraryId",
                "destinationDirectory",
                "conflictMode",
                "manifestDigest",
            }
            if not isinstance(document, dict) or set(document) != required:
                raise ValueError(
                    "a Files transfer requires only operation, paths, "
                    "destinationResourceLibraryId, destinationDirectory, conflictMode, "
                    "and manifestDigest"
                )
            if not isinstance(document["paths"], list):
                raise ValueError("Files transfer paths must be an array")
            result = binding.direct_transfers.submit_transfer(
                resource_library_id=parts[3],
                paths=document["paths"],
                destination_resource_library_id=document["destinationResourceLibraryId"],
                destination_directory=document["destinationDirectory"],
                operation=document["operation"],
                conflict_mode=document["conflictMode"],
                manifest_digest=document["manifestDigest"],
            )
            # 202: the transfer is durably admitted and queued for the resident
            # Worker; the response carries the durable operator projection and
            # no Storage mutation has happened on this request's stack.
            return self._response(start_response, 202, result)
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "transfers"
            and method == "GET"
        ):
            # The bounded durable projection of one admitted transfer.  The Web
            # polls this read to follow queued/running/paused progress with the
            # backend-advertised lifecycle actions; it never needs a raw
            # execution token and never learns claim/lease internals.
            self._require(principal, ApiPermission.READ)
            if binding.direct_transfers is None:
                return self._files_browser_unavailable(start_response)
            self._require_empty_query(environ, "Files transfer status")
            try:
                projection = binding.direct_transfers.transfer_projection(parts[6])
            except DirectFileTransferError as error:
                if error.category == "not_found":
                    raise LookupError(f"task {parts[6]!r} was not found") from None
                raise
            return self._response(start_response, 200, projection)
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "organize"
            and method == "POST"
        ):
            # Files submits only the enabled ResourceLibrary identity and
            # normalized ResourceLibrary-relative paths.  The backend pins the
            # Active snapshot, derives every immutable SourceIdentity from live
            # Storage, and admits the one durable manual intent through the
            # existing application boundary; no Preview, Task or Storage
            # mutation is created here.
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            self._require_empty_query(environ, "Files organize admission")
            if self._manual_previews is None or not callable(
                getattr(self._manual_previews, "admit_storage_paths", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual organize admission is unavailable",
                    details={
                        "durableState": "no_intent_created",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore a valid Active runtime and manual Organize services, "
                            "then resubmit the same bounded selection"
                        ),
                    },
                )
            document = self._document(environ)
            if not isinstance(document, dict) or set(document) != {"paths"}:
                raise ValueError("Files organize admission accepts only bounded relative paths")
            if not isinstance(document["paths"], list):
                raise ValueError("Files organize admission paths must be an array")
            try:
                intent = self._manual_previews.admit_storage_paths(
                    resource_library_id=parts[3],
                    relative_paths=document["paths"],
                    actor=principal.principal_id,
                )
            except ManualPreviewError as error:
                return self._manual_step_error(start_response, error)
            except ManualIntentError as error:
                return self._manual_step_error(start_response, error)
            return self._response(
                start_response, 201, self._organize_intent_document(intent, principal)
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "commands"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.EXECUTE_MANUAL_ORGANIZE)
            if binding.direct_files is None:
                return self._files_browser_unavailable(start_response)
            self._require_empty_query(environ, "Files direct command")
            document = self._document(environ)
            if not isinstance(document, dict) or "operation" not in document:
                raise ValueError("a Files direct command requires an operation")
            operation = document["operation"]
            resource_library_id = parts[3]
            if operation == DirectFileOperation.CREATE_DIRECTORY.value:
                required = {"operation", "parentPath", "name"}
                if set(document) != required:
                    raise ValueError("Create Folder requires only operation, parentPath, and name")
                result = binding.direct_files.create_directory(
                    resource_library_id=resource_library_id,
                    parent_path=document["parentPath"],
                    name=document["name"],
                )
            elif operation == DirectFileOperation.CREATE_TEXT.value:
                required = {"operation", "parentPath", "name", "content"}
                if set(document) != required:
                    raise ValueError(
                        "Create Text File requires only operation, parentPath, name, and content"
                    )
                result = binding.direct_files.create_text(
                    resource_library_id=resource_library_id,
                    parent_path=document["parentPath"],
                    name=document["name"],
                    content=document["content"],
                )
            elif operation == DirectFileOperation.RENAME.value:
                required = {"operation", "path", "name", "expected"}
                if set(document) != required:
                    raise ValueError("Rename requires only operation, path, name, and expected")
                result = binding.direct_files.rename(
                    resource_library_id=resource_library_id,
                    path=document["path"],
                    name=document["name"],
                    expected=document["expected"],
                )
            elif operation == DirectFileOperation.SAVE_TEXT.value:
                required = {"operation", "path", "content", "expected"}
                if set(document) != required:
                    raise ValueError(
                        "Text Save requires only operation, path, content, and expected"
                    )
                result = binding.direct_files.save_text(
                    resource_library_id=resource_library_id,
                    path=document["path"],
                    content=document["content"],
                    expected=document["expected"],
                )
            elif operation == DirectFileOperation.DELETE.value:
                required = {"operation", "paths", "confirmationDigest"}
                if set(document) != required:
                    raise ValueError(
                        "Delete requires only operation, paths, and confirmationDigest"
                    )
                result = binding.direct_files.execute_delete(
                    resource_library_id=resource_library_id,
                    paths=document["paths"],
                    confirmation_digest=document["confirmationDigest"],
                )
            else:
                raise ValueError("the Files direct command operation is not supported")
            return self._response(start_response, 200, result)
        if parts == ["api", "v1", "files", "stats"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._file_catalog is None:
                return self._error(
                    start_response, 503, "service_unavailable", "file catalog is unavailable"
                )
            resource_library_id, storage_id = self._file_stats_query(environ)
            stats = self._file_catalog.stats(
                resource_library_id=resource_library_id, storage_id=storage_id
            )
            return self._response(
                start_response,
                200,
                {
                    "surface": "file_index",
                    "fileIndexSurface": "/api/v1/file-index",
                    "filesSurface": "/api/v1/storage/files",
                    "total": stats.total,
                    "byStatus": {
                        status.value: stats.by_status.get(status, 0) for status in FileScanStatus
                    },
                },
            )
        if parts == ["api", "v1", "files"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._file_catalog is None:
                return self._error(
                    start_response, 503, "service_unavailable", "file catalog is unavailable"
                )
            filters = self._file_catalog_query(environ)
            values = (
                self._file_lifecycle.list(filters)
                if self._file_lifecycle is not None
                else self._file_catalog.list(filters)
            )
            return self._response(
                start_response,
                200,
                {
                    "surface": "file_index",
                    "fileIndexSurface": "/api/v1/file-index",
                    "filesSurface": "/api/v1/storage/files",
                    "items": [self._file_catalog_value(item) for item in values],
                    "limit": filters.limit,
                },
            )
        if parts == ["api", "v1", "files", "by-source"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._file_catalog is None:
                return self._error(
                    start_response, 503, "service_unavailable", "file catalog is unavailable"
                )
            storage_id, path, resource_library_id = self._file_by_source_query(environ)
            record, unavailable_reason = self._file_catalog.resolve_by_source(
                storage_id,
                path,
                resource_library_id=resource_library_id,
            )
            if record is None:
                reason_code = "ambiguous" if unavailable_reason == "ambiguous" else "missing"
                return self._response(
                    start_response,
                    200,
                    {
                        "surface": "file_index",
                        "fileIndexSurface": "/api/v1/file-index",
                        "filesSurface": "/api/v1/storage/files",
                        "available": False,
                        "fileId": None,
                        "reason": reason_code,
                        "unavailableReason": (
                            "the source link is ambiguous; scope it by ResourceLibrary and reload"
                            if reason_code == "ambiguous"
                            else "no current indexed FileIndex record matches this source link"
                        ),
                    },
                )
            return self._response(
                start_response,
                200,
                {
                    "surface": "file_index",
                    "fileIndexSurface": "/api/v1/file-index",
                    "filesSurface": "/api/v1/storage/files",
                    "available": True,
                    "fileId": record.file_id,
                    "reason": None,
                    "resourceLibraryId": record.resource_library_id,
                    "detailUrl": f"/api/v1/files/{record.file_id}",
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "files"]
            and parts[4] == "previews"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._manual_previews is None or not callable(
                getattr(self._manual_previews, "list_current", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "current-source Preview service is unavailable",
                )
            values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(values).difference({"resourceLibrary", "resourceLibraryId", "limit"}) or any(
                len(value) != 1 for value in values.values()
            ):
                raise ValueError("file Preview list query accepts one ResourceLibrary and limit")
            resource_library_alias = values.get("resourceLibrary", [None])[0]
            resource_library_canonical = values.get("resourceLibraryId", [None])[0]
            if (
                resource_library_alias is not None
                and resource_library_canonical is not None
                and resource_library_alias != resource_library_canonical
            ):
                raise ValueError("file Preview list ResourceLibrary fields disagree")
            resource_library_id = resource_library_alias or resource_library_canonical
            if not resource_library_id:
                raise ValueError("file Preview list requires resourceLibrary")
            limit = self._parse_bounded_limit(values.get("limit", ["100"])[0], "Preview")
            previews = self._manual_previews.list_current("file", parts[3], limit=limit)
            if any(
                any(value.source.resource_library_id != resource_library_id for value in item.items)
                for item in previews
            ):
                raise ValueError("file Preview list ResourceLibrary does not match the source")
            return self._response(
                start_response,
                200,
                {
                    "items": [self._manual_preview_document(value) for value in previews],
                    "limit": limit,
                    "total": len(previews),
                    "scopeKind": "file",
                    "scopeId": parts[3],
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "previews"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._manual_previews is None or not callable(
                getattr(self._manual_previews, "list_current", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "current-source Preview service is unavailable",
                )
            values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(values).difference({"limit"}) or any(
                len(value) != 1 for value in values.values()
            ):
                raise ValueError("ResourceLibrary Preview list query accepts limit once")
            limit = self._parse_bounded_limit(values.get("limit", ["100"])[0], "Preview")
            previews = self._manual_previews.list_current("resource_library", parts[3], limit=limit)
            return self._response(
                start_response,
                200,
                {
                    "items": [self._manual_preview_document(value) for value in previews],
                    "limit": limit,
                    "total": len(previews),
                    "scopeKind": "resourceLibrary",
                    "scopeId": parts[3],
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "files"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._file_catalog is None:
                return self._error(
                    start_response, 503, "service_unavailable", "file catalog is unavailable"
                )
            resource_library_id = self._file_resource_query(environ)
            detail = self._file_catalog.detail(parts[3], resource_library_id=resource_library_id)
            return self._response(
                start_response,
                200,
                self._file_catalog_detail_value(detail),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "files"]
            and parts[4] == "reprocess"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            if self._file_lifecycle is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "FileIndex lifecycle service is unavailable",
                )
            self._require_empty_query(environ, "FileIndex Reprocess")
            document = self._document(environ)
            if set(document) != {"occurrenceId", "fingerprint"}:
                raise ValueError(
                    "FileIndex Reprocess requires only the current occurrenceId and fingerprint"
                )
            occurrence_id = document["occurrenceId"]
            fingerprint = document["fingerprint"]
            if (
                not isinstance(occurrence_id, str)
                or not occurrence_id.strip()
                or not isinstance(fingerprint, str)
                or not fingerprint.strip()
            ):
                raise ValueError("FileIndex Reprocess occurrenceId and fingerprint are required")
            request = self._file_lifecycle.admit_reprocess(
                parts[3],
                occurrence_id,
                fingerprint,
                actor=principal.principal_id,
            )
            return self._response(
                start_response,
                202,
                {
                    "surface": "file_index",
                    "fileId": request.file_id,
                    "requestId": request.request_id,
                    "occurrenceId": request.occurrence_id,
                    "fingerprint": request.fingerprint,
                    "status": request.status,
                    "actor": request.actor,
                    "requestedAt": request.requested_at.isoformat(),
                    "sideEffects": "none",
                    "taskCreated": False,
                    "providerRequested": False,
                    "nextAction": request.next_action,
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "files"]
            and parts[4] == "preview"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_previews is None or not callable(
                getattr(self._manual_previews, "create_current", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "current-source Preview service is unavailable",
                )
            self._require_empty_query(environ, "current-source Preview")
            request = self._current_preview_request(
                self._document(environ), route_scope_kind="file", route_scope_id=parts[3]
            )
            preview = self._manual_previews.create_current(
                **request,
                actor=principal.principal_id,
            )
            return self._response(start_response, 201, self._manual_preview_document(preview))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] in {"preview", "previews"}
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_previews is None or not callable(
                getattr(self._manual_previews, "create_current", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "current-source Preview service is unavailable",
                )
            self._require_empty_query(environ, "ResourceLibrary Preview")
            request = self._current_preview_request(
                self._document(environ),
                route_scope_kind="resource_library",
                route_scope_id=parts[3],
            )
            preview = self._manual_previews.create_current(
                **request,
                actor=principal.principal_id,
            )
            return self._response(start_response, 201, self._manual_preview_document(preview))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "files"]
            and parts[4] == "continue-dry-run"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            if self._file_catalog is None:
                return self._error(
                    start_response, 503, "service_unavailable", "file catalog is unavailable"
                )
            self._require_empty_query(environ, "file action")
            document = self._document(environ)
            allowed = {"reviewId", "expectedCorrectionVersion"}
            if set(document).difference(allowed):
                raise ValueError(f"file {parts[4]} request fields are invalid")
            if set(document) != allowed:
                raise ValueError(
                    "file continuation requires reviewId and expectedCorrectionVersion"
                )
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            submission = FileMetadataCorrectionContinuationService(
                self._file_catalog,
                self._repository,
                snapshot_validator=(self._configuration_service.validate_runtime_snapshot),
            ).submit(
                parts[3],
                document["reviewId"],
                expected_correction_version=document["expectedCorrectionVersion"],
                actor=principal.principal_id,
                maximum_active_jobs=binding.maximum_active_jobs,
            )
            continuation = submission.continuation
            return self._response(
                start_response,
                202,
                {
                    "continuationId": continuation.continuation_id,
                    "jobId": continuation.job_id,
                    "taskId": continuation.new_task_id,
                    "resultId": continuation.new_result_id,
                    "status": continuation.status.value,
                    "executionMode": "dry_run",
                    "sourceTaskId": continuation.source_task_id,
                    "sourceItemId": continuation.source_item_id,
                    "configurationSnapshotId": continuation.configuration_snapshot_id,
                    "configurationSnapshotDigest": continuation.configuration_snapshot_digest,
                    "correctionVersion": continuation.correction_version,
                    "sideEffects": "none",
                    "nextAction": (
                        "run or wait for the Worker, then inspect the linked Task/Result"
                    ),
                },
            )
        if parts == ["api", "v1", "manual-intents"] and method == "POST":
            # Manual intent admission is analysis/selection work, not execution.
            # It uses the existing operator DryRun permission and never creates
            # a Task, Plan, Provider request or execution authority.
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                )
            self._require_empty_query(environ, "manual intent creation")
            document = self._document(environ)
            if set(document) != {"fileIds"}:
                raise ValueError("manual intent creation requires only fileIds")
            file_ids = document["fileIds"]
            if not isinstance(file_ids, list):
                raise ValueError("manual intent fileIds must be an array")
            intent = self._manual_intents.create(file_ids, actor=principal.principal_id)
            return self._response(
                start_response,
                201,
                self._manual_intent_document(intent),
            )
        if parts == ["api", "v1", "manual-previews"] and method == "POST":
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_previews is None or not callable(
                getattr(self._manual_previews, "create_current", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "current-source Preview service is unavailable",
                )
            self._require_empty_query(environ, "current-source Preview")
            request = self._current_preview_request(self._document(environ))
            preview = self._manual_previews.create_current(
                **request,
                actor=principal.principal_id,
            )
            return self._response(start_response, 201, self._manual_preview_document(preview))
        if parts == ["api", "v1", "manual-previews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._manual_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "current-source Preview service is unavailable",
                )
            values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(values).difference(
                {
                    "scopeKind",
                    "scopeId",
                    "fileId",
                    "resourceLibrary",
                    "resourceLibraryId",
                    "intentId",
                    "limit",
                }
            ) or any(len(value) != 1 for value in values.values()):
                raise ValueError("current-source Preview list query contains unsupported fields")
            limit = self._parse_bounded_limit(values.get("limit", ["100"])[0], "Preview")
            intent_id = values.get("intentId", [None])[0]
            file_id = values.get("fileId", [None])[0]
            resource_library_id = values.get("resourceLibraryId", [None])[0]
            resource_library_alias = values.get("resourceLibrary", [None])[0]
            if (
                resource_library_id is not None
                and resource_library_alias is not None
                and resource_library_id != resource_library_alias
            ):
                raise ValueError("Preview list ResourceLibrary fields disagree")
            resource_library_id = resource_library_id or resource_library_alias
            scope_kind = values.get("scopeKind", [None])[0]
            scope_id = values.get("scopeId", [None])[0]
            if scope_kind == "resourceLibrary":
                scope_kind = "resource_library"
            if intent_id is not None:
                if any(
                    value is not None
                    for value in (file_id, resource_library_id, scope_kind, scope_id)
                ):
                    raise ValueError("Preview list intentId cannot be combined with a source scope")
                items = self._manual_previews.list_readonly(intent_id, limit=limit)
            else:
                if file_id is not None and resource_library_id is not None:
                    raise ValueError("Preview list cannot combine fileId and resourceLibraryId")
                if file_id is not None:
                    if resource_library_id is None:
                        raise ValueError("file Preview list requires resourceLibraryId")
                    if scope_kind not in (None, "file"):
                        raise ValueError("file Preview list scopeKind must be file")
                    if scope_id not in (None, file_id):
                        raise ValueError("file Preview list scopeId disagrees with fileId")
                    scope_kind, scope_id = "file", file_id
                elif resource_library_id is not None:
                    if scope_kind not in (None, "resource_library"):
                        raise ValueError("ResourceLibrary Preview list scopeKind is invalid")
                    if scope_id not in (None, resource_library_id):
                        raise ValueError("ResourceLibrary Preview list scopeId disagrees")
                    scope_kind, scope_id = "resource_library", resource_library_id
                elif scope_kind is not None or scope_id is not None:
                    if scope_kind not in {"file", "resource_library"} or not scope_id:
                        raise ValueError(
                            "Preview list scope requires a valid scopeKind and scopeId"
                        )
                    if scope_kind == "file":
                        file_id, scope_id = scope_id, scope_id
                    else:
                        resource_library_id, scope_id = scope_id, scope_id
                else:
                    raise ValueError("Preview list requires intentId or a bounded source scope")
                items = self._manual_previews.list_current(scope_kind, scope_id, limit=limit)
            return self._response(
                start_response,
                200,
                {
                    "items": [self._manual_preview_document(value) for value in items],
                    "limit": limit,
                    "total": len(items),
                    "scopeKind": "resourceLibrary"
                    if scope_kind == "resource_library"
                    else scope_kind,
                    "scopeId": scope_id,
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "files"]
            and parts[4] in {"manual-organize", "manual-intent"}
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                )
            self._require_empty_query(environ, "single-file manual intent creation")
            if environ.get("CONTENT_LENGTH", "0") not in ("", "0", 0, None):
                document = self._document(environ)
                if document:
                    raise ValueError("single-file manual intent accepts an empty request body")
            intent = self._manual_intents.create([parts[3]], actor=principal.principal_id)
            return self._response(start_response, 201, self._manual_intent_document(intent))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-intents"]
            and parts[4] == "preview"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Preview service is unavailable",
                )
            self._require_empty_query(environ, "manual Preview")
            document = self._document(environ)
            allowed = {
                "expectedVersion",
                "expectedItemVersions",
                "itemIds",
                "snapshotId",
                "snapshotDigest",
            }
            if set(document).difference(allowed) or "expectedVersion" not in document:
                raise ValueError(
                    "manual Preview requires expectedVersion and only bounded selection fields"
                )
            expected_version = document["expectedVersion"]
            if (
                isinstance(expected_version, bool)
                or not isinstance(expected_version, int)
                or expected_version < 1
            ):
                raise ValueError("manual Preview expectedVersion must be a positive integer")
            item_ids = document.get("itemIds")
            if item_ids is not None and not isinstance(item_ids, list):
                raise ValueError("manual Preview itemIds must be an array")
            expected_item_versions = document.get("expectedItemVersions")
            if expected_item_versions is not None and not isinstance(
                expected_item_versions, (dict, list)
            ):
                raise ValueError("manual Preview expectedItemVersions must be an object or array")
            for name in ("snapshotId", "snapshotDigest"):
                if name in document and (
                    not isinstance(document[name], str) or not document[name].strip()
                ):
                    raise ValueError(f"manual Preview {name} must be a non-empty string")
            preview = self._manual_previews.create(
                parts[3],
                item_ids,
                expected_version=expected_version,
                expected_item_versions=expected_item_versions,
                snapshot_id=document.get("snapshotId"),
                snapshot_digest=document.get("snapshotDigest"),
                actor=principal.principal_id,
            )
            return self._response(start_response, 201, self._manual_preview_document(preview))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-intents"]
            and parts[4] == "previews"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._manual_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Preview service is unavailable",
                )
            values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(values).difference({"limit"}) or any(
                len(value) != 1 for value in values.values()
            ):
                raise ValueError("manual Preview query accepts limit once")
            limit = self._parse_bounded_limit(values.get("limit", ["100"])[0], "manual Preview")
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._manual_preview_document(value)
                        for value in self._manual_previews.list_readonly(parts[3], limit=limit)
                    ],
                    "limit": limit,
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-intents"]
            and parts[4] == "preview"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._manual_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Preview service is unavailable",
                )
            self._require_empty_query(environ, "current manual Preview")
            return self._response(
                start_response,
                200,
                self._manual_preview_document(self._manual_previews.latest_readonly(parts[3])),
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "manual-previews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._manual_previews is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual Preview service is unavailable",
                )
            self._require_empty_query(environ, "manual Preview detail")
            return self._response(
                start_response,
                200,
                self._manual_preview_document(self._manual_previews.get_readonly(parts[3])),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-previews"]
            and parts[4] == "authorize"
            and method == "POST"
        ):
            self._require_manual_execution(principal)
            if self._manual_execution is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual execution service is unavailable",
                )
            self._require_empty_query(environ, "manual execution authorization")
            document = self._document(environ)
            allowed = {
                "expectedVersion",
                "expectedItemVersions",
                "itemIds",
                "snapshotId",
                "snapshotDigest",
                "confirmation",
                "allowOverwrite",
                "allowSourceCleanup",
                "ttlSeconds",
                "note",
            }
            if set(document).difference(allowed):
                raise ValueError("manual execution authorization fields are invalid")
            required = {"expectedVersion", "expectedItemVersions", "itemIds", "confirmation"}
            if not required.issubset(document):
                raise ValueError(
                    "manual execution authorization requires expected versions, itemIds, "
                    "and confirmation"
                )
            expected_version = document["expectedVersion"]
            if (
                isinstance(expected_version, bool)
                or not isinstance(expected_version, int)
                or expected_version < 1
            ):
                raise ValueError("manual execution expectedVersion must be a positive integer")
            item_ids = document["itemIds"]
            if not isinstance(item_ids, list):
                raise ValueError("manual execution itemIds must be an array")
            expected_item_versions = document["expectedItemVersions"]
            if not isinstance(expected_item_versions, (dict, list)):
                raise ValueError("manual execution expectedItemVersions must be an object or array")
            for name in ("snapshotId", "snapshotDigest"):
                if name in document and (
                    not isinstance(document[name], str) or not document[name].strip()
                ):
                    raise ValueError(f"manual execution {name} must be a non-empty string")
            if "confirmation" not in document or document["confirmation"] is not True:
                raise ValueError("manual execution authorization requires confirmation=true")
            authorization = self._manual_execution.authorize(
                parts[3],
                item_ids,
                expected_intent_version=expected_version,
                expected_item_versions=expected_item_versions,
                snapshot_id=document.get("snapshotId"),
                snapshot_digest=document.get("snapshotDigest"),
                actor=principal.principal_id,
                permission=ApiPermission.EXECUTE_MANUAL_ORGANIZE.value,
                confirmation=document["confirmation"],
                allow_overwrite=document.get("allowOverwrite", False),
                allow_source_cleanup=document.get("allowSourceCleanup", False),
                ttl_seconds=document.get("ttlSeconds"),
                note=document.get("note"),
            )
            return self._response(
                start_response,
                201,
                self._manual_execution.authorization_document(authorization.authorization_id),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-execution-authorizations"]
            and parts[4] in {"execute", "consume"}
            and method == "POST"
        ):
            self._require_manual_execution(principal)
            if self._manual_execution is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual execution service is unavailable",
                )
            self._require_empty_query(environ, "manual execution")
            document = self._document(environ)
            if set(document) != {"confirmation"} or document["confirmation"] is not True:
                raise ValueError("manual execution requires only confirmation=true")
            execution = self._manual_execution.execute(
                parts[3],
                actor=principal.principal_id,
                permission=ApiPermission.EXECUTE_MANUAL_ORGANIZE.value,
                confirmation=document["confirmation"],
            )
            return self._response(
                start_response,
                200,
                self._manual_execution.document(execution.execution_id),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-previews"]
            and parts[4] == "execute"
            and method == "POST"
        ):
            self._require_manual_execution(principal)
            if self._manual_execution is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual execution service is unavailable",
                )
            self._require_empty_query(environ, "manual execution")
            document = self._document(environ)
            if set(document) != {"authorizationId", "confirmation"}:
                raise ValueError(
                    "manual Preview execution requires authorizationId and confirmation"
                )
            if (
                not isinstance(document["authorizationId"], str)
                or not document["authorizationId"].strip()
                or document["confirmation"] is not True
            ):
                raise ValueError("manual Preview execution requires confirmation=true")
            authorization = self._manual_execution.get_authorization(document["authorizationId"])
            if authorization.preview_id != parts[3]:
                raise ValueError("manual execution authorization does not belong to this Preview")
            execution = self._manual_execution.execute(
                authorization.authorization_id,
                actor=principal.principal_id,
                permission=ApiPermission.EXECUTE_MANUAL_ORGANIZE.value,
                confirmation=document["confirmation"],
            )
            return self._response(
                start_response,
                200,
                self._manual_execution.document(execution.execution_id),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-executions"]
            and parts[4] == "reconcile"
            and method == "POST"
        ):
            self._require_manual_execution(principal)
            if self._manual_execution is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual execution service is unavailable",
                )
            self._require_empty_query(environ, "manual execution reconciliation")
            document = self._document(environ)
            if set(document) != {"confirmation"} or document["confirmation"] is not True:
                raise ValueError("manual execution reconciliation requires confirmation=true")
            execution = self._manual_execution.reconcile(
                parts[3],
                actor=principal.principal_id,
                permission=ApiPermission.EXECUTE_MANUAL_ORGANIZE.value,
                confirmation=document["confirmation"],
            )
            return self._response(
                start_response,
                200,
                self._manual_execution.document(execution.execution_id),
            )
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "manual-execution-authorizations"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if self._manual_execution is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual execution service is unavailable",
                )
            self._require_empty_query(environ, "manual execution authorization detail")
            return self._response(
                start_response,
                200,
                self._manual_execution.authorization_document(parts[3]),
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "manual-executions"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._manual_execution is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual execution service is unavailable",
                )
            self._require_empty_query(environ, "manual execution detail")
            return self._response(
                start_response,
                200,
                self._manual_execution.document(parts[3]),
            )
        if parts == ["api", "v1", "manual-intents"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                )
            values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(values).difference({"limit"}) or any(
                len(value) != 1 for value in values.values()
            ):
                raise ValueError("manual intent query accepts limit once")
            limit = self._parse_bounded_limit(values.get("limit", ["100"])[0], "manual intent")
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._manual_intent_document(item, include_audit=False)
                        for item in self._manual_intents.list(limit=limit)
                    ],
                    "limit": limit,
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "manual-intents"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                )
            self._require_empty_query(environ, "manual intent detail")
            return self._response(
                start_response,
                200,
                self._manual_intent_document(self._manual_intents.get(parts[3])),
            )
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "manual-intents"]
            and parts[4] == "items"
            and parts[6] == "choice"
            and method == "PUT"
        ):
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                )
            self._require_empty_query(environ, "manual intent choice")
            document = self._document(environ)
            allowed = {
                "expectedVersion",
                "expectedItemVersion",
                "snapshotId",
                "snapshotDigest",
                "recognitionTypeId",
                "metadata",
                "metadataIdentity",
                "namingPolicyId",
                "classificationPolicyId",
                "organizePolicyId",
            }
            if set(document).difference(allowed):
                raise ValueError("manual intent choice fields are invalid")
            if "expectedVersion" not in document:
                raise ValueError("manual intent choice requires expectedVersion")
            if "metadata" in document and "metadataIdentity" in document:
                raise ValueError(
                    "manual intent choice accepts metadata or metadataIdentity, not both"
                )
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int) or expected < 1:
                raise ValueError("manual intent expectedVersion must be a positive integer")
            expected_item = document.get("expectedItemVersion")
            if expected_item is not None and (
                isinstance(expected_item, bool)
                or not isinstance(expected_item, int)
                or expected_item < 1
            ):
                raise ValueError("manual intent expectedItemVersion must be a positive integer")
            patch = {
                key: document[key]
                for key in (
                    "recognitionTypeId",
                    "metadata",
                    "namingPolicyId",
                    "classificationPolicyId",
                    "organizePolicyId",
                )
                if key in document
            }
            if "metadataIdentity" in document:
                patch["metadata"] = document["metadataIdentity"]
            if not patch:
                raise ValueError("manual intent choice requires at least one normalized choice")
            intent = self._manual_intents.update_choice(
                parts[3],
                parts[5],
                patch,
                expected_version=expected,
                expected_item_version=expected_item,
                snapshot_id=document.get("snapshotId"),
                snapshot_digest=document.get("snapshotDigest"),
                actor=principal.principal_id,
            )
            return self._response(start_response, 200, self._manual_intent_document(intent))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-intents"]
            and parts[4] == "cancel"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                )
            self._require_empty_query(environ, "manual intent cancellation")
            document = self._document(environ)
            if set(document) != {"expectedVersion"}:
                raise ValueError("manual intent cancellation requires only expectedVersion")
            expected = document["expectedVersion"]
            if isinstance(expected, bool) or not isinstance(expected, int) or expected < 1:
                raise ValueError("manual intent expectedVersion must be a positive integer")
            intent = self._manual_intents.cancel(
                parts[3], expected_version=expected, actor=principal.principal_id
            )
            return self._response(start_response, 200, self._manual_intent_document(intent))
        if parts == ["api", "v1", "security-audit"] and method == "GET":
            self._require(principal, ApiPermission.READ_SECURITY_AUDIT)
            return self._response(
                start_response,
                200,
                {"items": [self._value(item) for item in self._repository.list_security_audit()]},
            )
        if parts == ["api", "v1", "dashboard"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            return self._response(
                start_response,
                200,
                self._value(
                    binding.dashboard.snapshot(recent_limit=self._dashboard_limit(environ))
                ),
            )
        if parts == ["api", "v1", "metadata-reviews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            limit = self._metadata_review_limit(environ)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._value(item)
                        for item in self._repository.list_metadata_reviews(limit=limit)
                    ]
                },
            )
        if parts == ["api", "v1", "recognition-reviews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            limit = self._recognition_review_limit(environ)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._value(item)
                        for item in self._repository.list_recognition_reviews(limit=limit)
                    ]
                },
            )
        if parts == ["api", "v1", "metadata-corrections"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            limit = self._metadata_correction_limit(environ)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._value(item)
                        for item in self._repository.list_metadata_corrections(limit=limit)
                    ]
                },
            )
        if parts == ["api", "v1", "classification-reviews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            limit = self._classification_review_limit(environ)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._value(item)
                        for item in self._repository.list_classification_reviews(limit=limit)
                    ]
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "metadata-reviews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            review = self._repository.get_metadata_review(parts[3])
            if review is None:
                raise LookupError(f"metadata review {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                {
                    **self._value(review),
                    "candidates": [
                        self._value(item)
                        for item in self._repository.list_metadata_review_candidates(parts[3])
                    ],
                    "audit": [
                        self._metadata_review_audit_value(item)
                        for item in self._repository.list_metadata_review_audit(parts[3])
                    ],
                },
            )
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "recognition-reviews"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            review = self._repository.get_recognition_review(parts[3])
            if review is None:
                raise LookupError(f"recognition review {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                {
                    **self._value(review),
                    "choices": [
                        self._value(item)
                        for item in self._repository.list_recognition_review_choices(parts[3])
                    ],
                    "audit": [
                        self._value(item)
                        for item in self._repository.list_recognition_review_audit(parts[3])
                    ],
                },
            )
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "metadata-corrections"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            review = self._repository.get_metadata_correction(parts[3])
            if review is None:
                raise LookupError(f"metadata correction {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                {
                    **self._value(review),
                    "audit": [
                        self._metadata_correction_audit_value(item)
                        for item in self._repository.list_metadata_correction_audit(parts[3])
                    ],
                },
            )
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "classification-reviews"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            review = self._repository.get_classification_review(parts[3])
            if review is None:
                raise LookupError(f"classification review {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                {
                    **self._value(review),
                    "choices": [
                        self._value(item)
                        for item in self._repository.list_classification_review_choices(parts[3])
                    ],
                    "audit": [
                        self._classification_review_audit_value(item)
                        for item in self._repository.list_classification_review_audit(parts[3])
                    ],
                },
            )
        if method == "GET":
            self._require(principal, ApiPermission.READ)
        if parts == ["api", "v1", "tasks"] and method == "GET":
            task_status, task_command, limit, cursor = self._task_collection_query(environ)
            scope = _collection_scope(task_status.value if task_status else None, task_command)
            values = self._list_page(
                lambda **kwargs: self._repository.list_tasks(
                    status=task_status.value if task_status else None,
                    command=task_command,
                    **kwargs,
                ),
                limit,
                cursor,
            )
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._task_document(item, bounded=operations_projection) for item in page
                    ],
                    "limit": limit,
                    "status": task_status.value if task_status else None,
                    "command": task_command,
                    "truncated": has_next,
                    "previous_cursor": self._page_cursor(
                        "tasks",
                        page,
                        has_previous,
                        CursorDirection.PREVIOUS,
                        scope=scope,
                    ),
                    "next_cursor": self._page_cursor(
                        "tasks", page, has_next, CursorDirection.NEXT, scope=scope
                    ),
                },
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "task checkpoint")
            checkpoint = self._checkpoint_service.get(parts[5], task_id=parts[3])
            value = checkpoint.document()
            if self._manual_execution is not None:
                value["manualExecutionDiscovery"] = self._manual_execution.discovery_for_task_item(
                    parts[3], parts[5]
                )
            if self._manual_recovery is not None:
                value["manualRecoveryLink"] = self._manual_recovery.discovery_for_source_item(
                    parts[3], parts[5]
                )
            return self._response(start_response, 200, value)
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6] == "recovery"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            self._require_empty_query(environ, "task item recovery")
            document = self._document(environ)
            allowed = {"actionId", "expectedCheckpointVersion", "note"}
            if set(document).difference(allowed):
                raise ValueError("task item recovery request fields are invalid")
            if "actionId" not in document or "expectedCheckpointVersion" not in document:
                raise ValueError(
                    "task item recovery requires actionId and expectedCheckpointVersion"
                )
            action_id = document["actionId"]
            expected = document["expectedCheckpointVersion"]
            if not isinstance(action_id, str) or not action_id.strip():
                raise ValueError("recovery actionId is required")
            if not isinstance(expected, str) or not expected.strip():
                raise ValueError("expectedCheckpointVersion is required")
            if (
                "note" in document
                and document["note"] is not None
                and not isinstance(document["note"], str)
            ):
                raise ValueError("recovery note must be a string")
            request = self._recovery_admission.admit(
                parts[3],
                parts[5],
                action_id=action_id,
                expected_checkpoint_version=expected,
                actor=principal.principal_id,
                note=document.get("note"),
            )
            value = request.document()
            return self._response(
                start_response,
                200,
                {
                    "request": value,
                    "requestId": request.request_id,
                    "taskId": request.task_id,
                    "itemId": request.item_id,
                    "actionId": request.action_id,
                    "status": request.status.value,
                    "checkpointVersion": request.checkpoint_version,
                    "nextAction": request.next_action,
                    "sideEffects": "none",
                },
            )
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6:8] == ["recovery", "continue"]
            and method == "POST"
        ):
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            self._require_empty_query(environ, "task item recovery continuation")
            document = self._document(environ)
            allowed = {"expectedCheckpointVersion"}
            if set(document).difference(allowed):
                raise ValueError("task item recovery continuation request fields are invalid")
            if set(document) != allowed:
                raise ValueError(
                    "task item recovery continuation requires expectedCheckpointVersion"
                )
            expected = document["expectedCheckpointVersion"]
            if not isinstance(expected, str) or not expected.strip():
                raise ValueError("expectedCheckpointVersion is required")
            binding = self._runtime_binding
            submission = self._recovery_continuation.submit(
                parts[3],
                parts[5],
                expected_checkpoint_version=expected,
                actor=principal.principal_id,
                maximum_active_jobs=binding.maximum_active_jobs,
            )
            continuation = submission.continuation
            return self._response(
                start_response,
                202,
                {
                    **continuation.document(),
                    "executionMode": "dry_run",
                    "sideEffects": "none",
                },
            )
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6:8] == ["recovery", "authorize-organize"]
            and method == "POST"
        ):
            self._require_manual_execution(principal)
            if self._manual_recovery is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual recovery continuation service is unavailable",
                )
            self._require_empty_query(environ, "manual recovery continuation authorization")
            document = self._document(environ)
            allowed = {
                "expectedCheckpointVersion",
                "confirmation",
                "allowOverwrite",
                "allowSourceCleanup",
                "ttlSeconds",
                "note",
            }
            if set(document).difference(allowed):
                raise ValueError("manual recovery continuation fields are invalid")
            expected = document.get("expectedCheckpointVersion")
            if not isinstance(expected, str) or not expected.strip():
                raise ValueError("expectedCheckpointVersion is required")
            if document.get("confirmation") is not True:
                raise ValueError(
                    "manual recovery continuation authorization requires confirmation=true"
                )
            if (
                "note" in document
                and document["note"] is not None
                and not isinstance(document["note"], str)
            ):
                raise ValueError("manual recovery continuation note must be a string")
            link = self._manual_recovery.authorize_continued(
                parts[3],
                parts[5],
                expected_checkpoint_version=expected,
                actor=principal.principal_id,
                permission=ApiPermission.EXECUTE_MANUAL_ORGANIZE.value,
                confirmation=document["confirmation"],
                allow_overwrite=bool(document.get("allowOverwrite", False)),
                allow_source_cleanup=bool(document.get("allowSourceCleanup", False)),
                ttl_seconds=document.get("ttlSeconds"),
                note=document.get("note"),
            )
            return self._response(
                start_response,
                201,
                {
                    **link.document(),
                    "sourceTaskId": parts[3],
                    "sourceItemId": parts[5],
                    "sideEffects": "none",
                    "executionMode": "not_authorized_yet",
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-recovery-links"]
            and parts[4] == "execute"
            and method == "POST"
        ):
            self._require_manual_execution(principal)
            if self._manual_recovery is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual recovery continuation service is unavailable",
                )
            self._require_empty_query(environ, "manual recovery continuation execution")
            document = self._document(environ)
            if set(document) != {"confirmation"} or document["confirmation"] is not True:
                raise ValueError(
                    "manual recovery continuation execution requires confirmation=true"
                )
            link = self._manual_recovery.execute_continued(
                parts[3],
                actor=principal.principal_id,
                permission=ApiPermission.EXECUTE_MANUAL_ORGANIZE.value,
                confirmation=document["confirmation"],
            )
            return self._response(
                start_response,
                200,
                link.document(),
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4:6] == ["recovery", "continue-batch"]
            and method == "POST"
        ):
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            self._require_empty_query(environ, "task batch recovery continuation")
            document = self._document(environ)
            if set(document) != {"items"}:
                raise ValueError("task batch recovery continuation requires only items")
            if not isinstance(document["items"], list):
                raise ValueError("task batch recovery items must be a list")
            binding = self._runtime_binding
            batch = self._recovery_batch.submit(
                parts[3],
                document["items"],
                actor=principal.principal_id,
                maximum_active_jobs=binding.maximum_active_jobs,
            )
            return self._response(
                start_response,
                202,
                {
                    **batch.document(),
                    "executionMode": "dry_run",
                    "sideEffects": "none",
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "recovery-batches"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "recovery batch")
            return self._response(
                start_response,
                200,
                self._repository.get_recovery_batch(parts[3]).document(),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "recovery-batches"]
            and parts[4] == "resume"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            self._require_empty_query(environ, "recovery batch resume")
            self._require_empty_body(environ, "recovery batch resume")
            binding = self._runtime_binding
            batch = self._recovery_batch.resume(
                parts[3],
                actor=principal.principal_id,
                maximum_active_jobs=binding.maximum_active_jobs,
            )
            return self._response(
                start_response,
                202,
                {
                    **batch.document(),
                    "executionMode": "dry_run",
                    "sideEffects": "none",
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] in {"cancel", "pause", "resume"}
            and method == "POST"
        ):
            # Cooperative Task lifecycle control.  The advertised action, the
            # exact current version and the permission check all come from the
            # same backend projection the V2 client renders; a rejected or
            # stale control performs no Provider/Storage work and is never
            # replayed automatically.
            self._require(principal, ApiPermission.CANCEL_JOB)
            self._require_empty_query(environ, f"Task {parts[4]}")
            action = parts[4]
            expected_version = self._control_version(environ, f"Task {parts[4]} control")
            service = TaskLifecycleService(self._repository)
            if action == "resume":
                task = service.require(parts[3])
                service.require_version(task, expected_version)
                if task.command == FILES_TRANSFER_TASK_COMMAND and (
                    binding.direct_transfers is not None
                ):
                    # The one Task kind with a persisted, bounded continuation
                    # authority: the resume request only re-queues the durable
                    # authority — the resident Worker later claims it and
                    # continues from each item's recorded known-safe
                    # checkpoint, never by replaying an uncertain mutation.
                    requeued = binding.direct_transfers.requeue_transfer(task.task_id)
                    return self._response(start_response, 202, requeued)
                # No durable queued continuation of one exact paused scope
                # exists today, so the transition is refused with the same
                # actionable reason the projection states.
                raise OperationsLifecycleConflict(
                    "resume_unavailable",
                    "pausing is cooperative, but resuming one exact paused Task scope is not "
                    "available through this API",
                    durable_state="the Task keeps its paused state and its recorded item outcomes",
                    next_action=(
                        "continue the paused Task from the operator terminal "
                        "(mediaflow tasks resume <task-id>), or leave it paused"
                    ),
                )
            if action == "pause":
                task = service.pause(parts[3], expected_version=expected_version)
            else:
                task = self._cancel_task(service, parts[3], expected_version, binding)
            lifecycle = self._task_lifecycle(
                service, task, principal, results=service.results(task.task_id)
            )
            return self._response(
                start_response,
                200,
                {
                    "action": action,
                    "taskId": task.task_id,
                    "task": task_operator_document(task),
                    "lifecycle": lifecycle,
                    "durableOutcome": next(
                        (
                            item["durableOutcome"]
                            for item in lifecycle["actions"]
                            if item["action"] == action
                        ),
                        None,
                    ),
                    "sideEffects": "none",
                    "retrySafe": False,
                    "nextAction": lifecycle["nextAction"],
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "tasks"] and method == "GET":
            item_limit, result_limit, item_cursor, result_cursor = self._task_detail_page(environ)
            task = self._repository.get_task(parts[3])
            if task is None:
                raise LookupError(f"task {parts[3]!r} was not found")
            items = self._list_page(
                lambda **kwargs: self._repository.list_items(task.task_id, **kwargs),
                item_limit,
                item_cursor,
            )
            results = self._list_page(
                lambda **kwargs: self._repository.list_results(task.task_id, **kwargs),
                result_limit,
                result_cursor,
            )
            item_page, has_previous_items, has_next_items = self._page_window(
                items, item_limit, item_cursor
            )
            result_page, has_previous_results, has_next_results = self._page_window(
                results, result_limit, result_cursor
            )
            checkpoint_items = []
            for item in item_page:
                checkpoint_items.append(
                    self._task_item_document(
                        item,
                        bounded=operations_projection,
                        checkpoint=self._checkpoint_service.summary(
                            item.item_id, task_id=task.task_id
                        ),
                    )
                )
            manual_discovery = (
                self._manual_execution.discovery_for_task(task.task_id)
                if self._manual_execution is not None
                else None
            )
            manual_scan = None
            if binding is not None and binding.manual_scans is not None:
                try:
                    scan_after = (
                        item_cursor.position
                        if item_cursor and item_cursor.direction is CursorDirection.NEXT
                        else None
                    )
                    scan_before = (
                        item_cursor.position
                        if item_cursor and item_cursor.direction is CursorDirection.PREVIOUS
                        else None
                    )
                    manual_scan = binding.manual_scans.detail_document(
                        task.task_id,
                        limit=item_limit,
                        after=scan_after,
                        before=scan_before,
                    )
                    manual_scan.pop("_has_previous_items", None)
                    manual_scan.pop("_has_next_items", None)
                    if operations_projection:
                        manual_scan = manual_scan_operator_document(
                            manual_scan,
                            cancel_permitted=ApiPermission.CANCEL_JOB in principal.permissions,
                        )
                except ManualScanError as error:
                    if error.code != "task_not_found":
                        raise
            return self._response(
                start_response,
                200,
                {
                    **self._task_document(task, bounded=operations_projection),
                    "items": checkpoint_items,
                    "results": [
                        self._task_result_document(item, bounded=operations_projection)
                        for item in result_page
                    ],
                    "manualExecutionDiscovery": manual_discovery,
                    "manualScan": manual_scan,
                    "recovery_batches": [
                        batch.document()
                        for batch in (
                            self._repository.list_recovery_batches(task.task_id)
                            if callable(getattr(self._repository, "list_recovery_batches", None))
                            else ()
                        )
                    ],
                    "item_limit": item_limit,
                    "result_limit": result_limit,
                    "items_truncated": has_next_items,
                    "results_truncated": has_next_results,
                    "previous_item_cursor": self._page_cursor(
                        "task_items", item_page, has_previous_items, CursorDirection.PREVIOUS
                    ),
                    "previous_result_cursor": self._page_cursor(
                        "task_results",
                        result_page,
                        has_previous_results,
                        CursorDirection.PREVIOUS,
                    ),
                    "next_item_cursor": self._page_cursor(
                        "task_items", item_page, has_next_items, CursorDirection.NEXT
                    ),
                    "next_result_cursor": self._page_cursor(
                        "task_results", result_page, has_next_results, CursorDirection.NEXT
                    ),
                    "lifecycle": redact_manual_value(
                        self._task_lifecycle(
                            TaskLifecycleService(self._repository),
                            task,
                            principal,
                            results=tuple(result_page),
                            # Effect certainty is claimed only from a view that
                            # provably holds every durable Result.
                            results_complete=result_cursor is None and not has_next_results,
                        )
                    ),
                },
            )
        if parts == ["api", "v1", "confirmations"] and method == "GET":
            status, limit = self._confirmation_query(environ)
            values = self._repository.list_confirmations(status=status, limit=limit)
            return self._response(
                start_response,
                200,
                {"items": [self._confirmation_value(item) for item in values]},
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "confirmations"] and method == "GET":
            value = self._repository.get_confirmation(parts[3])
            if value is None:
                raise LookupError(f"confirmation {parts[3]!r} was not found")
            return self._response(start_response, 200, self._confirmation_value(value))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "metadata-reviews"]
            and parts[4] == "resolve"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.RESOLVE_METADATA_REVIEW)
            document = self._document(environ)
            if set(document) != {"candidateRank"}:
                raise ValueError("metadata review resolution requires only candidateRank")
            candidate_rank = document["candidateRank"]
            if isinstance(candidate_rank, bool) or not isinstance(candidate_rank, int):
                raise ValueError("candidateRank must be an integer")
            value = MetadataReviewService(self._repository).resolve(
                parts[3], candidate_rank, actor=principal.principal_id
            )
            return self._response(start_response, 200, self._value(value))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "classification-reviews"]
            and parts[4] == "resolve"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.RESOLVE_CLASSIFICATION_REVIEW)
            document = self._document(environ)
            if set(document) != {"choiceRank"}:
                raise ValueError("classification review resolution requires only choiceRank")
            choice_rank = document["choiceRank"]
            if isinstance(choice_rank, bool) or not isinstance(choice_rank, int):
                raise ValueError("choiceRank must be an integer")
            value = ClassificationReviewService(self._repository).resolve(
                parts[3], choice_rank, actor=principal.principal_id
            )
            return self._response(start_response, 200, self._value(value))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "confirmations"]
            and parts[4] == "audit"
            and method == "GET"
        ):
            value = self._repository.get_confirmation(parts[3])
            if value is None:
                raise LookupError(f"confirmation {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._confirmation_audit_value(item)
                        for item in self._repository.list_confirmation_audit(parts[3])
                    ]
                },
            )
        if parts == ["api", "v1", "schedules"] and method == "GET":
            self._require_empty_query(environ, "schedule")
            states = {item.schedule_id: item for item in self._repository.list_schedule_states()}
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        {
                            **self._value(item),
                            "state": self._value(states.get(item.schedule_id)),
                        }
                        for item in binding.schedules
                    ]
                },
            )
        if parts == ["api", "v1", "notifications"] and method == "GET":
            limit, delivery_status, cursor = self._notification_query(environ)
            scope = delivery_status.value if delivery_status else "all"
            values = self._list_page(
                lambda **kwargs: self._repository.list_deliveries(status=delivery_status, **kwargs),
                limit,
                cursor,
            )
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "limit": limit,
                    "status": delivery_status.value if delivery_status else None,
                    "previous_cursor": self._page_cursor(
                        "notification_deliveries",
                        page,
                        has_previous,
                        CursorDirection.PREVIOUS,
                        scope=scope,
                    ),
                    "next_cursor": self._page_cursor(
                        "notification_deliveries",
                        page,
                        has_next,
                        CursorDirection.NEXT,
                        scope=scope,
                    ),
                    "items": [
                        {
                            "deliveryId": item.delivery_id,
                            "webhookId": item.webhook_id,
                            "eventId": item.event_id,
                            "eventType": item.event_type.value,
                            "status": item.status.value,
                            "attempts": item.attempts,
                            "nextAttemptAt": item.next_attempt_at.isoformat(),
                            "createdAt": item.created_at.isoformat(),
                            "updatedAt": item.updated_at.isoformat(),
                            "deliveredAt": (
                                item.delivered_at.isoformat() if item.delivered_at else None
                            ),
                            "failureCategory": item.failure_category,
                            "responseStatus": item.response_status,
                        }
                        for item in page
                    ],
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "notifications"] and method == "GET":
            # One bounded delivery detail projection.  The application service
            # derives lease/staleness, known effects, retry safety and the
            # explicitly available recovery actions; viewing never mutates.
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "notification delivery detail")
            return self._response(
                start_response,
                200,
                self._notification_deliveries.detail(
                    parts[3],
                    lease_seconds=self._notification_delivery_lease_seconds(),
                ),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "notifications"]
            and parts[4] in {"requeue", "resolve-stale"}
            and method == "POST"
        ):
            # Explicit delivery recovery actions (dead-letter requeue and
            # expired-lease stale recovery).  Both are optimistic-concurrency
            # state transitions scoped to the exact delivery identity; they
            # never create a second row, never touch siblings and never mutate
            # Webhook definitions, configuration, Storage or media work.
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            self._require_empty_query(environ, "notification delivery recovery")
            document = self._document(environ)
            if set(document) != {"expectedStatus", "expectedUpdatedAt"}:
                raise ValueError("delivery recovery requires expectedStatus and expectedUpdatedAt")
            if parts[4] == "requeue":
                result = self._notification_deliveries.requeue_dead_letter(
                    parts[3],
                    expected_status=document["expectedStatus"],
                    expected_updated_at=document["expectedUpdatedAt"],
                    lease_seconds=self._notification_delivery_lease_seconds(),
                    actor=principal.principal_id,
                )
            else:
                result = self._notification_deliveries.resolve_stale(
                    parts[3],
                    expected_status=document["expectedStatus"],
                    expected_updated_at=document["expectedUpdatedAt"],
                    lease_seconds=self._notification_delivery_lease_seconds(),
                    actor=principal.principal_id,
                )
            return self._response(start_response, 200, result)
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "schedules"]
            and parts[4] == "audit"
            and method == "GET"
        ):
            known = {item.schedule_id for item in binding.schedules}
            if parts[3] not in known:
                raise LookupError(f"schedule {parts[3]!r} was not found")
            limit, cursor = self._scoped_page_query(
                environ, "schedule_audit", parts[3], "schedule audit"
            )
            values = self._list_page(
                lambda **kwargs: self._repository.list_schedule_audit(parts[3], **kwargs),
                limit,
                cursor,
            )
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "items": [self._value(item) for item in page],
                    "limit": limit,
                    "previous_cursor": self._page_cursor(
                        "schedule_audit",
                        page,
                        has_previous,
                        CursorDirection.PREVIOUS,
                        scope=parts[3],
                    ),
                    "next_cursor": self._page_cursor(
                        "schedule_audit",
                        page,
                        has_next,
                        CursorDirection.NEXT,
                        scope=parts[3],
                    ),
                },
            )
        if parts == ["api", "v1", "logs"] and method == "GET":
            limit, minimum_level, cursor = self._log_query(environ)
            scope = minimum_level.name if minimum_level else "all"
            values = self._list_page(
                lambda **kwargs: self._repository.list_operational_logs(
                    minimum_level=minimum_level, **kwargs
                ),
                limit,
                cursor,
            )
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        {
                            "log_id": item.log_id,
                            "occurred_at": item.occurred_at.isoformat(),
                            "level": item.level.name,
                            "component": item.component,
                            "event": item.event,
                            "task_id": item.task_id,
                            "job_id": item.job_id,
                            "plan_id": item.plan_id,
                            "status": item.status,
                        }
                        for item in page
                    ],
                    "limit": limit,
                    "level": minimum_level.name if minimum_level else None,
                    "previous_cursor": self._page_cursor(
                        "operational_logs",
                        page,
                        has_previous,
                        CursorDirection.PREVIOUS,
                        scope=scope,
                    ),
                    "next_cursor": self._page_cursor(
                        "operational_logs", page, has_next, CursorDirection.NEXT, scope=scope
                    ),
                },
            )
        if parts == ["api", "v1", "jobs", "stale"]:
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require(principal, ApiPermission.READ)
            limit = self._stale_job_limit(environ)
            return self._response(
                start_response,
                200,
                {
                    "threshold_seconds": binding.stale_job_age_seconds,
                    "items": [
                        self._stale_job_value(item)
                        for item in binding.jobs.stale(
                            age_seconds=binding.stale_job_age_seconds, limit=limit
                        )
                    ],
                },
            )
        if parts == ["api", "v1", "jobs"]:
            if method == "GET":
                job_status, job_command, limit, cursor = self._job_collection_query(environ)
                scope = (
                    f"status={job_status.value if job_status else 'all'};"
                    f"command={job_command.value if job_command else 'all'}"
                )
                values = self._list_page(
                    lambda **kwargs: self._repository.list_jobs(
                        status=job_status.value if job_status else None,
                        command=job_command.value if job_command else None,
                        **kwargs,
                    ),
                    limit,
                    cursor,
                )
                page, has_previous, has_next = self._page_window(values, limit, cursor)
                return self._response(
                    start_response,
                    200,
                    {
                        "items": [
                            self._job_document(item, principal, bounded=operations_projection)
                            for item in page
                        ],
                        "limit": limit,
                        "status": job_status.value if job_status else None,
                        "command": job_command.value if job_command else None,
                        "truncated": has_next,
                        "previous_cursor": self._page_cursor(
                            "jobs",
                            page,
                            has_previous,
                            CursorDirection.PREVIOUS,
                            scope=scope,
                        ),
                        "next_cursor": self._page_cursor(
                            "jobs", page, has_next, CursorDirection.NEXT, scope=scope
                        ),
                    },
                )
            if method == "POST":
                self._require_empty_query(environ, "job submission")
                document = self._document(environ)
                forbidden = {
                    "overwrite",
                    "delete",
                    "executionToken",
                    "authorization",
                }.intersection(document)
                if forbidden:
                    raise ValueError(f"unsupported service field {sorted(forbidden)[0]!r}")
                command = document.get("command", "")
                if command == "organize":
                    self._require(principal, ApiPermission.REMOTE_EXECUTE)
                    if not binding.remote_execution_enabled:
                        raise ValueError("remote execution is disabled")
                    if document.get("execute") is not True:
                        raise ValueError("remote organize requires execute=true")
                    unsupported = set(document).difference({"command", "execute", "limit"})
                    if unsupported:
                        raise ValueError(
                            f"unsupported remote organize field {sorted(unsupported)[0]!r}"
                        )
                    token = str(environ.get("HTTP_X_MEDIAFLOW_EXECUTION_TOKEN", ""))
                    job = binding.execution_authorizations.submit_organize(
                        token, limit=document.get("limit")
                    )
                else:
                    self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
                    unsupported = set(document).difference({"command", "limit"})
                    if unsupported:
                        raise ValueError(f"unsupported DryRun job field {sorted(unsupported)[0]!r}")
                    job = binding.jobs.submit(command, limit=document.get("limit"))
                return self._response(start_response, 202, self._job_document(job, principal))
        if len(parts) == 4 and parts[:3] == ["api", "v1", "jobs"] and method == "GET":
            job = self._repository.get_job(parts[3])
            if job is None:
                raise LookupError(f"automation job {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                self._job_document(job, principal, bounded=operations_projection),
            )
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "cancel":
            if method != "POST":
                return self._error(start_response, 405, "method_not_allowed", "POST required")
            self._require(principal, ApiPermission.CANCEL_JOB)
            self._require_empty_query(environ, "job cancellation")
            expected_version = self._control_version(environ, "job cancellation")
            # The durable transition itself binds the cancellable state, the
            # unset request flag and the version the operator read in one atomic
            # compare-and-set, so a concurrent or repeated control is refused
            # instead of being admitted twice.
            return self._response(
                start_response,
                200,
                self._job_document(
                    binding.jobs.cancel(parts[3], expected_version=expected_version),
                    principal,
                    bounded=True,
                ),
            )
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "requeue-stale":
            if method != "POST":
                return self._error(start_response, 405, "method_not_allowed", "POST required")
            self._require(principal, ApiPermission.CANCEL_JOB)
            self._require_empty_query(environ, "stale Job requeue")
            self._require_empty_body(environ, "stale Job requeue")
            job = self._repository.get_job(parts[3])
            if job is None:
                raise LookupError(f"automation job {parts[3]!r} was not found")
            if job.command is not AutomationCommand.FILE_METADATA_CORRECTION:
                raise ValueError(
                    "stale requeue is only available for a File correction continuation"
                )
            return self._response(
                start_response,
                200,
                self._job_document(
                    binding.jobs.requeue_stale(
                        parts[3],
                        age_seconds=binding.stale_job_age_seconds,
                    ),
                    principal,
                ),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "confirmations"]
            and parts[4] == "resolve"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.RESOLVE_CONFIRMATION)
            document = self._document(environ)
            unsupported = set(document).difference({"strategy"})
            if unsupported:
                raise ValueError(f"unsupported confirmation field {sorted(unsupported)[0]!r}")
            try:
                strategy = ConflictStrategy(document.get("strategy", ""))
            except ValueError as error:
                raise ValueError("remote confirmation strategy must be skip or rename") from error
            if strategy not in {ConflictStrategy.SKIP, ConflictStrategy.RENAME}:
                raise ValueError("remote confirmation strategy must be skip or rename")
            value = ConfirmationService(self._repository).resolve(
                parts[3], strategy, actor=principal.principal_id
            )
            return self._response(start_response, 200, self._confirmation_value(value))
        return self._error(start_response, 404, "not_found", "route was not found")

    def _authenticate(self, environ: dict) -> ResolvedApiPrincipal | None:
        header = str(environ.get("HTTP_AUTHORIZATION", ""))
        prefix = "Bearer "
        candidate = header[len(prefix) :] if header.startswith(prefix) else ""
        valid = (
            len(header) <= 4096
            and 1 <= len(candidate) <= 2048
            and not any(character.isspace() for character in candidate)
        )
        presented = candidate if valid else ""
        matched = None
        for principal in self._principals:
            if hmac.compare_digest(presented, principal.token):
                matched = principal
        return matched

    @staticmethod
    def _stream_response(
        start_response: Callable,
        status: int,
        headers: list[tuple[str, str]],
        body: Iterable[bytes],
    ) -> Iterable[bytes]:
        """Commit one bounded streaming response body.

        The headers are fixed before the first byte is produced (admission
        already ran with zero mutation), so the body generator is the only
        thing that runs after ``start_response``.  WSGI servers with chunked
        transfer encoding carry the archive case without a Content-Length.
        """

        start_response(f"{status} OK", headers)
        return body

    @staticmethod
    def _rfc5987(value: str) -> str:
        return quote(value, safe="")

    def _static_response(
        self, start_response: Callable, content_type: str, body: bytes
    ) -> list[bytes]:
        start_response(
            "200 OK",
            [
                ("Content-Type", content_type),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                (
                    "Content-Security-Policy",
                    "default-src 'self'; connect-src 'self'; "
                    "script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; "
                    "frame-ancestors 'none'; form-action 'none'",
                ),
                ("X-Content-Type-Options", "nosniff"),
                ("Referrer-Policy", "no-referrer"),
                ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
            ],
        )
        return [body]

    @staticmethod
    def _require(principal: ResolvedApiPrincipal, permission: ApiPermission) -> None:
        if permission not in principal.permissions:
            raise ApiPermissionDenied(f"principal lacks {permission.value} permission")

    def _configuration_status_document(
        self,
        principal: ResolvedApiPrincipal,
    ) -> dict[str, object]:
        if self._configuration_service is None:
            return {
                "authority": None,
                "managementReady": False,
                "setupRequired": False,
                "runtimeConfigured": False,
                "runtimeReady": False,
                "workflowAvailable": False,
                "unavailableReason": "managed configuration service is unavailable",
                "canManageConfiguration": False,
                "canActivateConfiguration": False,
            }
        status = self._configuration_service.status_document()
        status["canManageConfiguration"] = (
            ApiPermission.MANAGE_CONFIGURATION in principal.permissions
        )
        status["canActivateConfiguration"] = (
            ApiPermission.ACTIVATE_CONFIGURATION in principal.permissions
        )
        return status

    def _management_readiness_document(
        self,
        principal: ResolvedApiPrincipal,
    ) -> dict[str, object]:
        status = self._configuration_status_document(principal)
        return {
            "processAlive": True,
            "managementReady": status.get("managementReady", False),
            "setupRequired": status.get("setupRequired", False),
            "runtimeConfigured": status.get("runtimeConfigured", False),
            "runtimeReady": status.get("runtimeReady", False),
            "workflowAvailable": status.get("workflowAvailable", False),
            "authority": status.get("authority"),
            "active": status.get("active"),
            "lastKnownActive": status.get("lastKnownActive"),
            "managedActivation": status.get("managedActivation", False),
            "setupDraft": status.get("setupDraft"),
            "recoveryRequired": status.get("recoveryRequired", False),
            "health": status.get("health"),
            "unavailableReason": status.get("unavailableReason"),
            "nextAction": status.get("nextAction"),
            "canManageConfiguration": status.get("canManageConfiguration", False),
            "canActivateConfiguration": status.get("canActivateConfiguration", False),
        }

    def _worker_readiness_document(
        self,
        principal: ResolvedApiPrincipal,
        *,
        bounded: bool = False,
    ) -> dict[str, object]:
        """Worker readiness document (GET /api/v1/workers/readiness).

        The bounded Operations projection keeps the readiness identity and the
        Operator-facing next action but not the Active snapshot digest, which is
        a fingerprint value.
        """
        self._require(principal, ApiPermission.READ)
        self._refresh_configuration_binding()
        active_snapshot_id = self._runtime_binding.snapshot_id
        active_snapshot_digest = self._runtime_binding.snapshot_digest
        if self._worker_service is None:
            document: dict[str, object] = {
                "ready": False,
                "condition": WorkerReadiness.NO_WORKER.value,
                "category": WorkerReadiness.NO_WORKER.value,
                "durableState": "processing worker service is unavailable",
                "sideEffects": "none",
                "retrySafe": True,
                "nextAction": "contact system administrator",
                "activeWorkersCount": 0,
                "activeSnapshotId": active_snapshot_id,
            }
            if not bounded:
                document["activeSnapshotDigest"] = active_snapshot_digest
            return document
        readiness = self._worker_service.evaluate_readiness(
            active_snapshot_id=active_snapshot_id,
            active_snapshot_digest=active_snapshot_digest,
        )
        document = {
            "ready": readiness.get("ready", False),
            "condition": readiness.get("condition", WorkerReadiness.NO_WORKER.value),
            "category": readiness.get("condition", None) if not readiness.get("ready") else None,
            "durableState": readiness.get("durableState", ""),
            "sideEffects": readiness.get("sideEffects", "none"),
            "retrySafe": readiness.get("retrySafe", True),
            "nextAction": readiness.get("nextAction", ""),
            "activeWorkersCount": readiness.get("liveWorkers", 0),
            "activeSnapshotId": active_snapshot_id,
            "expectedRuntimeSchemaVersion": readiness.get("expectedSchemaVersion"),
        }
        if not bounded:
            document["activeSnapshotDigest"] = active_snapshot_digest
        return redact_manual_value(document)

    def _workers_document(
        self,
        principal: ResolvedApiPrincipal,
        limit: int = 50,
        *,
        bounded: bool = False,
    ) -> dict[str, object]:
        """Workers list document (GET /api/v1/workers)."""
        self._require(principal, ApiPermission.READ)
        if self._worker_service is None:
            return {
                "workers": [],
                "count": 0,
            }
        workers = self._worker_service.list_workers()
        # Apply limit to the list (repository list_workers returns all, we slice)
        limited_workers = workers[:limit]
        return {
            "workers": [
                self._worker_document(worker, bounded=bounded) for worker in limited_workers
            ],
            "count": len(workers),
        }

    @staticmethod
    def _worker_document(worker, *, bounded: bool = False) -> dict[str, object]:
        document: dict[str, object] = {
            "worker_id": worker.worker_id,
            "label": worker.label,
            "registered_at": worker.registered_at.isoformat(),
            "last_heartbeat_at": worker.last_heartbeat_at.isoformat(),
            "heartbeat_interval_seconds": worker.heartbeat_interval_seconds,
            "supported_commands": list(worker.supported_commands),
            "configuration_snapshot_id": worker.configuration_snapshot_id,
            "runtime_schema_version": worker.runtime_schema_version,
            "status": worker.status.value,
        }
        if not bounded:
            # The digest is a fingerprint value and stays out of the Operations
            # projection only; the administrative compatibility document keeps it.
            document["configuration_snapshot_digest"] = worker.configuration_snapshot_digest
        return redact_manual_value(document)

    @staticmethod
    def _require_manual_execution(principal: ResolvedApiPrincipal) -> None:
        if ApiPermission.EXECUTE_MANUAL_ORGANIZE not in principal.permissions:
            raise ApiPermissionDenied("principal lacks execute_manual_organize permission")

    def _prepare_runtime_binding_for_revision(self, revision):
        """Build a candidate runtime binding before publishing its Active pointer."""

        if self._configuration_service is None:
            return self._runtime_binding
        from mediaflow.infrastructure.configuration_snapshot import build_configuration_snapshot
        from mediaflow.infrastructure.runtime_configuration import (
            load_managed_runtime_configuration,
            with_managed_snapshot,
        )

        try:
            self._configuration_service.verify_integrity(revision)
            runtime = with_managed_snapshot(
                load_managed_runtime_configuration(
                    revision.document,
                    bootstrap_database_path=(
                        self._configuration_service.bootstrap_database_path
                        or getattr(
                            getattr(self._configuration_service, "_repository", None),
                            "database_path",
                            "",
                        )
                    ),
                ),
                snapshot_id=revision.revision_id,
                digest=revision.digest,
                version=revision.version,
            )
            system_status = build_configuration_snapshot(runtime)
            maximum_active_jobs = (
                self._maximum_active_jobs_override
                if self._maximum_active_jobs_override is not None
                else runtime.automation_maximum_active_jobs
            )
            # The repository will assign the persisted ACTIVE status after this
            # callback.  RuntimeFilesBrowserService still needs the exact
            # immutable identity and an Active lifecycle marker during preflight.
            runtime_revision = replace(
                revision,
                status=ManagedConfigurationStatus.ACTIVE,
                activated_at=revision.activated_at or datetime.now(UTC),
            )
            return self._build_runtime_binding(
                snapshot_id=revision.revision_id,
                snapshot_digest=revision.digest,
                maximum_active_jobs=maximum_active_jobs,
                remote_execution_enabled=runtime.remote_execution_enabled,
                remote_execution_maximum_ttl_seconds=(runtime.remote_execution_maximum_ttl_seconds),
                stale_job_age_seconds=runtime.automation_stale_job_age_seconds,
                system_status=system_status,
                schedules=runtime.automation_schedules,
                metadata_policies=runtime.strategy.metadata_policies,
                resource_library_count=sum(item.enabled for item in runtime.resource_libraries),
                media_library_count=sum(item.enabled for item in runtime.media_libraries),
                runtime_revision=runtime_revision,
                runtime_configuration=runtime,
            )
        except ResourceLibrarySaveError:
            raise
        except Exception as error:
            raise ResourceLibrarySaveError(
                "resource_library_runtime_failed",
                "the successor configuration could not be bound to the runtime; the previous "
                "Active remains in use",
                status=503,
                revision_id=getattr(revision, "revision_id", None),
                durable_state="active_preserved",
                side_effects=(
                    "successor_draft_and_read_only_evidence_retained; Active pointer unchanged"
                ),
                next_action="correct the runtime configuration, refresh, and retry Save",
            ) from error

    def _publish_runtime_binding(self, binding: _ApiRuntimeBinding) -> None:
        self._runtime_binding = binding
        # Compatibility diagnostics only; request behavior uses the single
        # immutable binding above rather than these individual attributes.
        self._configuration_snapshot_id = binding.snapshot_id
        self._configuration_snapshot_digest = binding.snapshot_digest

    def _refresh_configuration_binding(self) -> _ApiRuntimeBinding:
        with self._runtime_binding_lock:
            return self._refresh_configuration_binding_locked()

    def _runtime_settings_evidence(self) -> dict[str, object] | None:
        binding = getattr(self, "_runtime_binding", None)
        return binding.runtime_settings if binding is not None else None

    def _is_management_only_setup(self) -> bool:
        if not self._management_only:
            return False
        if self._configuration_service is None:
            return True
        try:
            if self._configuration_service.active() is not None:
                return False
            return not self._configuration_service.has_managed_activation()
        except RuntimeSnapshotUnavailable:
            # A prior managed installation is a recovery/unavailable state;
            # the normal binding refresh will return that more specific error.
            return False

    @staticmethod
    def _is_workflow_producing_route(method: str, parts: list[str]) -> bool:
        if method in {"GET", "HEAD", "OPTIONS"}:
            return False
        if parts[:3] == ["api", "v1", "configuration"]:
            return False
        if parts[:3] == ["api", "v1", "system"]:
            return False
        if parts == ["api", "v1", "management", "readiness"]:
            return False
        if len(parts) == 5 and parts[:3] == ["api", "v1", "files"] and parts[4] == "reprocess":
            # Reprocess is an auditable admission marker only; it creates no workflow work.
            return False
        if tuple(parts[:3]) in {
            ("api", "v1", "jobs"),
            ("api", "v1", "tasks"),
            ("api", "v1", "scans"),
            ("api", "v1", "manual-intents"),
            ("api", "v1", "manual-previews"),
            ("api", "v1", "manual-executions"),
            ("api", "v1", "manual-execution-authorizations"),
            ("api", "v1", "manual-recovery-links"),
            ("api", "v1", "resource-libraries"),
            ("api", "v1", "automation"),
            ("api", "v1", "schedules"),
            ("api", "v1", "files"),
            ("api", "v1", "recovery"),
            ("api", "v1", "recovery-batches"),
            ("api", "v1", "confirmations"),
            ("api", "v1", "recognition-reviews"),
            ("api", "v1", "metadata-corrections"),
            ("api", "v1", "classification-reviews"),
        }:
            return True
        return False

    def _refresh_configuration_binding_locked(self) -> _ApiRuntimeBinding:
        if self._configuration_service is None:
            return self._runtime_binding
        active = self._configuration_service.active()
        if active is None and self._configuration_service.has_managed_activation():
            marker = self._configuration_service.last_known_active()
            raise RuntimeSnapshotUnavailable(
                "managed Active configuration is unavailable; runtime is fail-closed",
                revision_id=marker.get("revisionId") if marker else None,
                version=(marker.get("revisionSequence", marker.get("version")) if marker else None),
                digest=marker.get("digest") if marker else None,
                reason="active_missing",
            )
        runtime = None
        refreshed_status = None
        if active is not None:
            self._configuration_service.verify_integrity(active)
            from mediaflow.infrastructure.configuration_snapshot import build_configuration_snapshot
            from mediaflow.infrastructure.runtime_configuration import (
                load_managed_runtime_configuration,
                with_managed_snapshot,
            )

            try:
                runtime = with_managed_snapshot(
                    load_managed_runtime_configuration(
                        active.document,
                        bootstrap_database_path=(
                            self._configuration_service.bootstrap_database_path
                            or getattr(
                                getattr(self._configuration_service, "_repository", None),
                                "database_path",
                                "",
                            )
                        ),
                    ),
                    snapshot_id=active.revision_id,
                    digest=active.digest,
                    version=active.version,
                )
                refreshed_status = build_configuration_snapshot(runtime)
            except Exception as error:
                raise RuntimeSnapshotUnavailable(
                    f"managed Active configuration {active.revision_id!r} is unavailable: "
                    f"{type(error).__name__}",
                    revision_id=active.revision_id,
                    version=active.revision_sequence,
                    digest=active.digest,
                    reason="runtime_invalid",
                ) from error
        snapshot_id = active.revision_id if active else None
        digest = active.digest if active else None
        current = self._runtime_binding
        if (
            snapshot_id == current.snapshot_id
            and digest == current.snapshot_digest
            and (
                runtime is None
                or (
                    current.files_browser is not None
                    and (self._file_index is None or current.manual_scans is not None)
                )
            )
        ):
            return current
        if runtime is None or refreshed_status is None:
            return current
        if snapshot_id != current.snapshot_id:
            self._maximum_active_jobs_override = None
        # Construct every config-derived behavior before publishing one pointer.
        # A request captures this immutable binding and cannot combine a new pin
        # with admission or execute settings retained from the previous Active.
        candidate = self._build_runtime_binding(
            snapshot_id=snapshot_id,
            snapshot_digest=digest,
            maximum_active_jobs=(
                self._maximum_active_jobs_override
                if self._maximum_active_jobs_override is not None
                else runtime.automation_maximum_active_jobs
            ),
            remote_execution_enabled=runtime.remote_execution_enabled,
            remote_execution_maximum_ttl_seconds=(runtime.remote_execution_maximum_ttl_seconds),
            stale_job_age_seconds=runtime.automation_stale_job_age_seconds,
            system_status=refreshed_status,
            schedules=runtime.automation_schedules,
            metadata_policies=runtime.strategy.metadata_policies,
            resource_library_count=sum(item.enabled for item in runtime.resource_libraries),
            media_library_count=sum(item.enabled for item in runtime.media_libraries),
            runtime_revision=active,
            runtime_configuration=runtime,
        )
        self._runtime_binding = candidate
        # Compatibility diagnostics only; request behavior uses the single
        # immutable binding above rather than these individual attributes.
        self._configuration_snapshot_id = snapshot_id
        self._configuration_snapshot_digest = digest
        return candidate

    def _build_runtime_binding(
        self,
        *,
        snapshot_id: str | None,
        snapshot_digest: str | None,
        maximum_active_jobs: int,
        remote_execution_enabled: bool,
        remote_execution_maximum_ttl_seconds: int,
        stale_job_age_seconds: int,
        system_status,
        schedules: tuple,
        metadata_policies: tuple,
        resource_library_count: int,
        media_library_count: int,
        runtime_revision=None,
        runtime_configuration=None,
    ) -> _ApiRuntimeBinding:
        files_browser = None
        direct_files = None
        direct_transfers = None
        if runtime_revision is not None and runtime_configuration is not None:
            files_browser = RuntimeFilesBrowserService(
                self._configuration_service,
                active_revision=runtime_revision,
                runtime_configuration=runtime_configuration,
                file_index=self._file_index,
                storage_adapters=self._storage_adapters,
                cursor_secret=self._storage_browser_cursor_secret,
            )
            direct_files = DirectFileCommandService(
                active_revision=runtime_revision,
                runtime_configuration=runtime_configuration,
                task_repository=self._repository,
                storage_adapters=self._storage_adapters,
            )
            direct_transfers = DirectFileTransferService(direct_files=direct_files)
        manual_scans = self._manual_scans_override
        if (
            manual_scans is None
            and runtime_configuration is not None
            and self._file_index is not None
        ):
            manual_scans = ManualScanService(
                self._repository,
                self._file_index,
                runtime_configuration=runtime_configuration,
                storage_factory=lambda storage_ids=None, configuration=runtime_configuration: (
                    configuration.create_storages(
                        external=self._storage_adapters, storage_ids=storage_ids
                    )
                ),
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=snapshot_digest,
            )
        runtime_settings = None
        if runtime_configuration is not None:
            retry = runtime_configuration.workflow_retry_policy
            runtime_settings = {
                "snapshotId": snapshot_id,
                "digest": snapshot_digest,
                "settings": {
                    "automation.workerPollSeconds": runtime_configuration.worker_poll_seconds,
                    "automation.schedulerPollSeconds": (
                        runtime_configuration.scheduler_poll_seconds
                    ),
                    "automation.maximumActiveJobs": (
                        runtime_configuration.automation_maximum_active_jobs
                    ),
                    "automation.staleJobAgeSeconds": (
                        runtime_configuration.automation_stale_job_age_seconds
                    ),
                    "operationalLogging.enabled": runtime_configuration.operational_logging_enabled,
                    "operationalLogging.minimumLevel": (
                        runtime_configuration.operational_logging_minimum_level.name
                    ),
                    "operationalLogging.retentionDays": (
                        runtime_configuration.operational_logging_retention_days
                    ),
                    "operationalLogging.maximumRecords": (
                        runtime_configuration.operational_logging_maximum_records
                    ),
                    "workflowRetry.enabled": retry.enabled,
                    "workflowRetry.maxAttempts": retry.max_attempts,
                    "workflowRetry.baseDelaySeconds": retry.base_delay_seconds,
                    "workflowRetry.maxDelaySeconds": retry.max_delay_seconds,
                    "workflowRetry.jitterRatio": retry.jitter_ratio,
                    "notifications.pollSeconds": runtime_configuration.notification_poll_seconds,
                    "notifications.deliveryLeaseSeconds": (
                        runtime_configuration.notification_delivery_lease_seconds
                    ),
                    "api.remoteExecution.enabled": runtime_configuration.remote_execution_enabled,
                    "api.remoteExecution.maximumTtlSeconds": (
                        runtime_configuration.remote_execution_maximum_ttl_seconds
                    ),
                },
            }
        return _ApiRuntimeBinding(
            snapshot_id,
            snapshot_digest,
            AutomationJobService(
                self._repository,
                maximum_active_jobs=maximum_active_jobs,
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=snapshot_digest,
            ),
            maximum_active_jobs,
            ExecutionAuthorizationService(
                self._repository,
                maximum_ttl_seconds=remote_execution_maximum_ttl_seconds,
                maximum_active_jobs=maximum_active_jobs,
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=snapshot_digest,
            ),
            remote_execution_enabled,
            stale_job_age_seconds,
            system_status,
            tuple(schedules),
            tuple(metadata_policies),
            DashboardService(
                self._repository,
                resource_library_count=resource_library_count,
                media_library_count=media_library_count,
            ),
            files_browser,
            direct_files,
            direct_transfers,
            manual_scans,
            runtime_settings,
        )

    def _audit(
        self,
        environ,
        request_id,
        principal,
        method,
        path,
        action,
        outcome,
        status,
    ) -> None:
        source_parts = str(environ.get("REMOTE_ADDR", "")).split()
        source = source_parts[0][:128] if source_parts else None
        self._repository.append_security_audit(
            SecurityAuditRecord(
                str(uuid4()),
                datetime.now(UTC),
                principal.principal_id if principal else None,
                method[:16],
                self._audit_route(path),
                action,
                outcome,
                status,
                request_id,
                source,
            )
        )

    @staticmethod
    def _audit_route(path: str) -> str:
        parts = [part for part in path.split("/") if part]
        if (
            len(parts) >= 4
            and parts[:3] == ["api", "v1", "operations"]
            and parts[3] in {"tasks", "jobs", "workers"}
        ):
            # The V2 Operations read alias names its own bounded projection
            # without publishing an object identifier in audit evidence.
            kind = parts[3]
            if len(parts) == 4:
                return f"/api/v1/operations/{kind}"
            if len(parts) == 5:
                if kind == "workers" and parts[4] == "readiness":
                    return "/api/v1/operations/workers/readiness"
                return f"/api/v1/operations/{kind}/{{id}}"
            return "/api/v1/<unmatched>"
        exact = {
            ("api", "v1", "tasks"),
            ("api", "v1", "scans"),
            ("api", "v1", "confirmations"),
            ("api", "v1", "schedules"),
            ("api", "v1", "notifications"),
            ("api", "v1", "logs"),
            ("api", "v1", "jobs"),
            ("api", "v1", "jobs", "stale"),
            ("api", "v1", "resource-libraries"),
            ("api", "v1", "security-audit"),
            ("api", "v1", "dashboard"),
            ("api", "v1", "system", "status"),
            ("api", "v1", "configuration", "packages"),
            ("api", "v1", "configuration", "packages", "export", "configuration"),
            ("api", "v1", "configuration", "packages", "export", "results"),
            ("api", "v1", "metadata-reviews"),
            ("api", "v1", "classification-reviews"),
            ("api", "v1", "recognition-reviews"),
            ("api", "v1", "metadata-corrections"),
            ("api", "v1", "recovery-batches"),
            ("api", "v1", "automation", "task-definitions"),
            ("api", "v1", "file-index"),
            ("api", "v1", "files"),
            ("api", "v1", "storage", "files"),
        }
        key = tuple(parts)
        if key in exact:
            return "/" + "/".join(parts)
        if len(parts) == 4 and parts[:3] in (
            ["api", "v1", "tasks"],
            ["api", "v1", "jobs"],
            ["api", "v1", "scans"],
        ):
            return f"/api/v1/{parts[2]}/{{id}}"
        if len(parts) == 5 and parts[:4] == ["api", "v1", "automation", "task-definitions"]:
            return "/api/v1/automation/task-definitions/{id}"
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "occurrences"
        ):
            return "/api/v1/automation/task-definitions/{id}/occurrences"
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] in {"grant", "grant-state", "revoke"}
        ):
            return f"/api/v1/automation/task-definitions/{{id}}/{parts[5]}"
        if (
            len(parts) == 7
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "grant"
            and parts[6] in {"audit", "revoke"}
        ):
            return "/api/v1/automation/task-definitions/{id}/grant/" + parts[6]
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "preview"
        ):
            return "/api/v1/automation/task-definitions/{id}/preview"
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "previews"
        ):
            return "/api/v1/automation/task-definitions/{id}/previews"
        if (
            len(parts) >= 7
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] == "previews"
        ):
            return "/api/v1/automation/task-definitions/{id}/previews/{previewId}"
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "automation", "task-definitions"]
            and parts[5] in {"copy", "enable", "disable"}
        ):
            return f"/api/v1/automation/task-definitions/{{id}}/{parts[5]}"
        if len(parts) >= 5 and parts[:4] == ["api", "v1", "operations", "notifications"]:
            # The V2 Notification projections name their own bounded operator
            # surface without publishing Webhook identifiers, delivery
            # identifiers, endpoints or secret references in audit evidence.
            if len(parts) == 5 and parts[4] == "webhooks":
                return "/api/v1/operations/notifications/webhooks"
            if parts[4] == "webhooks" and len(parts) == 6:
                return "/api/v1/operations/notifications/webhooks/{id}"
            if (
                parts[4] == "webhooks"
                and len(parts) == 7
                and parts[6] in {"draft", "test", "activate-draft"}
            ):
                return f"/api/v1/operations/notifications/webhooks/{{id}}/{parts[6]}"
            if parts[4] == "deliveries" and len(parts) == 6:
                return "/api/v1/operations/notifications/deliveries/{id}"
            return "/api/v1/<unmatched>"
        if len(parts) == 6 and parts[:3] == ["api", "v1", "tasks"] and parts[4] == "items":
            return "/api/v1/tasks/{task_id}/items/{item_id}"
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4:6] == ["recovery", "continue-batch"]
        ):
            return "/api/v1/tasks/{task_id}/recovery/continue-batch"
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6] == "recovery"
        ):
            return "/api/v1/tasks/{task_id}/items/{item_id}/recovery"
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6:8] == ["recovery", "continue"]
        ):
            return "/api/v1/tasks/{task_id}/items/{item_id}/recovery/continue"
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6:8] == ["recovery", "authorize-organize"]
        ):
            return "/api/v1/tasks/{task_id}/items/{item_id}/recovery/authorize-organize"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "recovery-batches"]:
            return "/api/v1/recovery-batches/{id}"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "recovery-batches"]
            and parts[4] == "resume"
        ):
            return "/api/v1/recovery-batches/{id}/resume"
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "cancel":
            return "/api/v1/jobs/{id}/cancel"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] in {"cancel", "pause", "resume"}
        ):
            return f"/api/v1/tasks/{{id}}/{parts[4]}"
        if len(parts) == 5 and parts[:3] == ["api", "v1", "scans"] and parts[4] == "cancel":
            return "/api/v1/scans/{id}/cancel"
        if len(parts) == 5 and parts[:3] == ["api", "v1", "schedules"] and parts[4] == "audit":
            return "/api/v1/schedules/{id}/audit"
        if (
            len(parts) == 5
            and parts[:3]
            in (
                ["api", "v1", "files"],
                ["api", "v1", "file-index"],
                ["api", "v1", "resource-libraries"],
            )
            and parts[4] in {"preview", "previews"}
        ):
            return f"/api/v1/{parts[2]}/{{id}}/{parts[4]}"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "resource-libraries"]:
            return "/api/v1/resource-libraries/{id}"
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5]
            in {
                "text",
                "delete-impact",
                "rename-evidence",
                "transfer-impact",
                "commands",
                "organize",
                "transfers",
            }
        ):
            return f"/api/v1/resource-libraries/{{id}}/files/{parts[5]}"
        if (
            len(parts) == 5
            and parts[:3] in (["api", "v1", "files"], ["api", "v1", "file-index"])
            and parts[4] == "reprocess"
        ):
            return f"/api/v1/{parts[2]}/{{id}}/reprocess"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "confirmations"]:
            return "/api/v1/confirmations/{id}"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "metadata-reviews"]:
            return "/api/v1/metadata-reviews/{id}"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "classification-reviews"]:
            return "/api/v1/classification-reviews/{id}"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "recognition-reviews"]:
            return "/api/v1/recognition-reviews/{id}"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "metadata-corrections"]:
            return "/api/v1/metadata-corrections/{id}"
        if len(parts) == 4 and parts[:3] in (
            ["api", "v1", "manual-previews"],
            ["api", "v1", "manual-execution-authorizations"],
            ["api", "v1", "manual-executions"],
        ):
            return f"/api/v1/{parts[2]}/{{id}}"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-previews"]
            and parts[4] in {"authorize", "execute"}
        ):
            return f"/api/v1/manual-previews/{{id}}/{parts[4]}"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-execution-authorizations"]
            and parts[4] in {"execute", "consume"}
        ):
            return f"/api/v1/manual-execution-authorizations/{{id}}/{parts[4]}"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-executions"]
            and parts[4] == "reconcile"
        ):
            return "/api/v1/manual-executions/{id}/reconcile"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-recovery-links"]
            and parts[4] == "execute"
        ):
            return "/api/v1/manual-recovery-links/{id}/execute"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "metadata-reviews"]
            and parts[4] == "resolve"
        ):
            return "/api/v1/metadata-reviews/{id}/resolve"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "classification-reviews"]
            and parts[4] == "resolve"
        ):
            return "/api/v1/classification-reviews/{id}/resolve"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "confirmations"]
            and parts[4]
            in {
                "audit",
                "resolve",
            }
        ):
            return f"/api/v1/confirmations/{{id}}/{parts[4]}"
        return "/api/v1/<unmatched>"

    @staticmethod
    def _dashboard_limit(environ: dict) -> int:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        unknown = set(values).difference({"recentLimit"})
        if unknown:
            raise ValueError("dashboard query contains an unsupported field")
        raw = values.get("recentLimit", ["10"])
        if len(raw) != 1:
            raise ValueError("dashboard recentLimit must be specified once")
        try:
            return int(raw[0])
        except ValueError as error:
            raise ValueError("dashboard recentLimit must be an integer") from error

    @staticmethod
    def _confirmation_query(
        environ: dict,
    ) -> tuple[ConfirmationStatus | None, int]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        unknown = set(values).difference({"status", "limit"})
        if unknown:
            raise ValueError("confirmation query contains an unsupported field")
        if any(len(value) != 1 for value in values.values()):
            raise ValueError("confirmation query fields must be specified once")
        raw_status = values.get("status", ["pending"])[0]
        if raw_status == "all":
            status = None
        else:
            try:
                status = ConfirmationStatus(raw_status)
            except ValueError as error:
                raise ValueError("confirmation status must be pending, resolved, or all") from error
        try:
            limit = int(values.get("limit", ["100"])[0])
        except ValueError as error:
            raise ValueError("confirmation limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError("confirmation limit must be between 1 and 100")
        return status, limit

    @staticmethod
    def _metadata_review_limit(environ: dict) -> int:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit"}) or any(len(value) != 1 for value in values.values()):
            raise ValueError("metadata review query accepts one limit field")
        try:
            limit = int(values.get("limit", ["100"])[0])
        except ValueError as error:
            raise ValueError("metadata review limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError("metadata review limit must be between 1 and 100")
        return limit

    @staticmethod
    def _classification_review_limit(environ: dict) -> int:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit"}) or any(len(value) != 1 for value in values.values()):
            raise ValueError("classification review query accepts one limit field")
        try:
            limit = int(values.get("limit", ["100"])[0])
        except ValueError as error:
            raise ValueError("classification review limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError("classification review limit must be between 1 and 100")
        return limit

    @staticmethod
    def _recognition_review_limit(environ: dict) -> int:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit"}) or any(len(value) != 1 for value in values.values()):
            raise ValueError("recognition review query accepts one limit field")
        try:
            limit = int(values.get("limit", ["100"])[0])
        except ValueError as error:
            raise ValueError("recognition review limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError("recognition review limit must be between 1 and 100")
        return limit

    @staticmethod
    def _metadata_correction_limit(environ: dict) -> int:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit"}) or any(len(value) != 1 for value in values.values()):
            raise ValueError("metadata correction query accepts one limit field")
        try:
            limit = int(values.get("limit", ["100"])[0])
        except ValueError as error:
            raise ValueError("metadata correction limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError("metadata correction limit must be between 1 and 100")
        return limit

    @staticmethod
    def _stale_job_limit(environ: dict) -> int:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit"}) or any(len(value) != 1 for value in values.values()):
            raise ValueError("stale job query accepts one limit field")
        return MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], "stale job")

    def _stale_job_value(self, value) -> dict:
        document = {
            "job_id": value.job_id,
            "command": value.command.value,
            "status": value.status.value,
            "created_at": value.created_at.isoformat(),
            "updated_at": value.updated_at.isoformat(),
            "started_at": value.started_at.isoformat() if value.started_at else None,
            "task_id": value.task_id,
            "cancellation_requested": value.cancellation_requested,
            "schedule_id": value.schedule_id,
            "execute_authorized": value.execute_authorized,
        }
        document.update(self._worker_owner_evidence(value.worker_id))
        return document

    @staticmethod
    def _require_empty_query(environ: dict, resource: str) -> None:
        if str(environ.get("QUERY_STRING", "")):
            raise ValueError(f"{resource} query does not accept fields")

    @staticmethod
    def _require_empty_body(environ: dict, resource: str) -> None:
        raw_length = str(environ.get("CONTENT_LENGTH", "")).strip()
        if not raw_length:
            return
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if length != 0:
            raise ValueError(f"{resource} body must be empty")

    @staticmethod
    def _control_version(environ: dict, resource: str) -> str | None:
        """Read the optional optimistic-concurrency body of a lifecycle control.

        An empty body keeps the pre-existing cancellation contract working.
        When a body is supplied it must carry exactly the version the operator
        read, so a control submitted against a state that has already changed is
        rejected before any durable transition.
        """

        raw_length = str(environ.get("CONTENT_LENGTH", "")).strip()
        if not raw_length:
            return None
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if length == 0:
            return None
        document = MediaFlowApi._document(environ)
        if set(document) != {"expectedUpdatedAt"}:
            raise ValueError(f"{resource} accepts only expectedUpdatedAt")
        expected = document["expectedUpdatedAt"]
        if (
            not isinstance(expected, str)
            or not expected.strip()
            or len(expected) > 128
            or not expected.isascii()
        ):
            raise ValueError("expectedUpdatedAt must be the version read by the operator")
        return expected

    def _task_lifecycle(
        self,
        service: TaskLifecycleService,
        task,
        principal: ResolvedApiPrincipal,
        *,
        results=(),
        results_complete: bool = True,
    ) -> dict[str, object]:
        """Project the lifecycle controls for one exact Task and principal."""

        return redact_manual_value(
            task_lifecycle_document(
                task,
                tuple(results),
                permissions=principal.permissions,
                execution=service.execution_context(task),
                results_complete=results_complete,
            )
        )

    @classmethod
    def _compatibility_document(cls, value) -> dict[str, object]:
        """Keep the historical document keys without the forbidden values.

        Existing clients may read these documents, so the historical field names
        are preserved.  Internal claim/fence, scope and fingerprint values never
        belong in an operator document, and a raw durable error is replaced by
        the normalized failure message plus the bounded failure evidence: a
        legacy or externally written row must never echo a credential, a private
        path or raw adapter text through this API.
        """

        document = {
            key: item
            for key, item in cls._value(value).items()
            if key not in _HIDDEN_DOCUMENT_FIELDS
        }
        raw_error = getattr(value, "error", None)
        failure = bounded_failure_document(raw_error)
        if "error" in document:
            document["error"] = None if failure is None else failure["message"]
        if failure is not None:
            document["failure"] = failure
        for key in (
            "failure_category",
            "failure_durable_state",
            "failure_side_effects",
            "failure_next_action",
        ):
            if key in document and isinstance(document[key], str):
                # Structured failure evidence is app-authored and bounded, but a
                # legacy or externally written row must not smuggle a credential
                # through it either.
                document[key] = redact_manual_text(document[key], limit=512) or None
        return document

    @classmethod
    def _task_document(cls, task, *, bounded: bool) -> dict[str, object]:
        return task_operator_document(task) if bounded else cls._compatibility_document(task)

    @classmethod
    def _task_item_document(
        cls, item, *, bounded: bool, checkpoint: dict[str, object] | None = None
    ) -> dict[str, object]:
        if bounded:
            return task_item_operator_document(item, checkpoint=checkpoint)
        document = cls._compatibility_document(item)
        for key in ("source_path", "destination_path"):
            if key in document:
                # A persisted identity column that is not a provably
                # Storage-relative identity fails closed in the compatibility
                # read too; the V1 operator UI renders source_display, not this.
                document[key] = bounded_identity_path(document[key])
        if checkpoint is not None:
            document["checkpoint"] = checkpoint
        return document

    @classmethod
    def _task_result_document(cls, result, *, bounded: bool) -> dict[str, object]:
        if bounded:
            return task_result_operator_document(result)
        document = cls._compatibility_document(result)
        for key in ("source_path", "destination_path"):
            if key in document:
                document[key] = bounded_identity_path(document[key])
        return document

    def _cancel_task(
        self,
        service: TaskLifecycleService,
        task_id: str,
        expected_version: str | None,
        binding,
    ):
        """Cancel one Task through the execution path that really observes it."""

        task = service.require(task_id)
        require_cancellable(task)
        context = service.execution_context(task)
        if context.path is TaskExecutionPath.MANUAL_SCAN:
            # The manual Scan service owns the cooperative cancellation: claim it
            # atomically for the observed version, then let the service mark its
            # own bounded state and cancel any in-process token.
            service.claim_manual_scan_cancellation(task_id, expected_version=expected_version)
            if binding is not None and binding.manual_scans is not None:
                try:
                    binding.manual_scans.cancel(task_id)
                except ManualScanError as error:
                    if error.code != "task_not_found":
                        raise
            return service.require(task_id)
        return service.cancel(task_id, expected_version=expected_version)

    @staticmethod
    def _scoped_page_query(
        environ: dict, kind: str, scope: str, resource: str
    ) -> tuple[int, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "cursor"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError(f"{resource} query accepts limit and cursor once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], resource)
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(raw_cursor[0], kind, expected_scope=scope)
            if raw_cursor
            else None
        )
        return limit, cursor

    def _notification_delivery_lease_seconds(self) -> float:
        """Return the signed delivery lease window used for staleness evidence.

        Prefer the lease actually consumed by the Notification Worker from the
        current managed Active runtime configuration; fall back to the shared
        domain default when no Active runtime snapshot is available to this
        surface (for example the management-only harness).
        """

        settings = getattr(self._runtime_binding, "runtime_settings", None)
        if isinstance(settings, dict):
            value = settings.get("settings", {}).get("notifications.deliveryLeaseSeconds")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return DELIVERY_LEASE_DEFAULT_SECONDS

    @staticmethod
    def _notification_query(
        environ: dict,
    ) -> tuple[int, NotificationDeliveryStatus | None, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "status", "cursor"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError("notification query accepts limit, status, and cursor once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], "notification")
        raw_status = values.get("status")
        if raw_status is None or raw_status[0] == "all":
            status = None
        else:
            try:
                status = NotificationDeliveryStatus(raw_status[0])
            except ValueError as error:
                raise ValueError("notification status is invalid") from error
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(
                raw_cursor[0],
                "notification_deliveries",
                expected_scope=status.value if status else "all",
            )
            if raw_cursor
            else None
        )
        return limit, status, cursor

    @staticmethod
    def _log_query(environ: dict) -> tuple[int, LogLevel | None, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "level", "cursor"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError("log query accepts limit, level, and cursor once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], "log")
        raw_level = values.get("level", ["all"])[0]
        if raw_level == "all":
            level = None
        else:
            try:
                level = LogLevel[raw_level]
            except KeyError as error:
                raise ValueError("log level is invalid") from error
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(
                raw_cursor[0],
                "operational_logs",
                expected_scope=level.name if level else "all",
            )
            if raw_cursor
            else None
        )
        return limit, level, cursor

    @staticmethod
    def _collection_page(environ: dict, resource: str) -> tuple[int, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "cursor"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError(f"{resource} query accepts limit and cursor once")
        limit = MediaFlowApi._parse_bounded_limit(
            values.get("limit", ["100"])[0], resource.rstrip("s")
        )
        raw_cursor = values.get("cursor")
        return limit, decode_directional_cursor(raw_cursor[0], resource) if raw_cursor else None

    @staticmethod
    def _task_collection_query(
        environ: dict,
    ) -> tuple[PersistentTaskStatus | None, str | None, int, DecodedCursor | None]:
        """Bounded Task collection filter state plus its filter-bound cursor.

        The submitted filters are part of the cursor scope, so a cursor minted
        for one filter state is rejected as soon as the submitted status or
        command differs, and a cursor minted without filters is rejected when
        filters are submitted.
        """

        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "cursor", "status", "command"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError("task query accepts limit, cursor, status, and command once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], "task")
        raw_status = values.get("status", ["all"])[0]
        if raw_status in {"", "all"}:
            status = None
        else:
            try:
                status = PersistentTaskStatus(raw_status)
            except ValueError as error:
                raise ValueError("task status is invalid") from error
        raw_command = values.get("command", [""])[0]
        command = None if raw_command in {"", "all"} else raw_command
        if command is not None and not _TASK_COMMAND_FILTER.fullmatch(command):
            raise ValueError("task command filter is invalid")
        scope = _collection_scope(status.value if status else None, command)
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(
                raw_cursor[0],
                "tasks",
                expected_scope=scope,
                # Without a submitted filter the collection keeps the
                # pre-existing unfiltered cursor contract.
                scope_optional=status is None and command is None,
            )
            if raw_cursor
            else None
        )
        return status, command, limit, cursor

    @staticmethod
    def _job_collection_query(
        environ: dict,
    ) -> tuple[AutomationJobStatus | None, AutomationCommand | None, int, DecodedCursor | None]:
        """Bounded Job collection filter state plus its filter-bound cursor."""

        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "cursor", "status", "command"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError("job query accepts limit, cursor, status, and command once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], "job")
        raw_status = values.get("status", ["all"])[0]
        if raw_status in {"", "all"}:
            status = None
        else:
            try:
                status = AutomationJobStatus(raw_status)
            except ValueError as error:
                raise ValueError("job status is invalid") from error
        raw_command = values.get("command", [""])[0]
        if raw_command in {"", "all"}:
            command = None
        else:
            try:
                command = AutomationCommand(raw_command)
            except ValueError as error:
                raise ValueError("job command is invalid") from error
        scope = _collection_scope(
            status.value if status else None, command.value if command else None
        )
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(
                raw_cursor[0],
                "jobs",
                expected_scope=scope,
                scope_optional=status is None and command is None,
            )
            if raw_cursor
            else None
        )
        return status, command, limit, cursor

    @staticmethod
    def _task_detail_page(
        environ: dict,
    ) -> tuple[int, int, DecodedCursor | None, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"itemLimit", "resultLimit", "itemCursor", "resultCursor"}
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError("task detail query fields must be supported and specified once")
        raw_item_cursor = values.get("itemCursor")
        raw_result_cursor = values.get("resultCursor")
        return (
            MediaFlowApi._parse_bounded_limit(values.get("itemLimit", ["100"])[0], "task item"),
            MediaFlowApi._parse_bounded_limit(values.get("resultLimit", ["100"])[0], "task result"),
            decode_directional_cursor(raw_item_cursor[0], "task_items")
            if raw_item_cursor
            else None,
            decode_directional_cursor(raw_result_cursor[0], "task_results")
            if raw_result_cursor
            else None,
        )

    @staticmethod
    def _manual_scan_detail_page(
        environ: dict,
    ) -> tuple[int, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"itemLimit", "itemCursor"}
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError("manual Scan detail query accepts itemLimit and itemCursor")
        raw_cursor = values.get("itemCursor")
        return (
            MediaFlowApi._parse_bounded_limit(
                values.get("itemLimit", ["100"])[0], "manual Scan item"
            ),
            decode_directional_cursor(raw_cursor[0], "task_items") if raw_cursor else None,
        )

    @staticmethod
    def _manual_scan_cursor(items, *, direction: CursorDirection) -> str | None:
        if not items:
            return None
        item = items[0] if direction is CursorDirection.PREVIOUS else items[-1]
        if not isinstance(item, dict):
            return None
        raw_timestamp = item.get("createdAt")
        record_id = item.get("itemId")
        if not isinstance(raw_timestamp, str) or not isinstance(record_id, str):
            return None
        return encode_cursor(
            "task_items",
            datetime.fromisoformat(raw_timestamp),
            record_id,
            direction,
        )

    def _manual_action_matrix(
        self,
        start_response: Callable,
        environ: dict,
        principal: ResolvedApiPrincipal,
        binding: _ApiRuntimeBinding,
    ):
        """Action matrix projection for the V2 Manual Scan/Preview surfaces.

        The matrix is authoritative for the exact authenticated principal, the
        exact current source/scope and runtime readiness.  It is also the
        bounded discovery surface for the ResourceLibrary choices the operator
        may select: a request without an exact scope reports
        ``selectionRequired`` and offers no actionable submission.
        """

        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"scopeKind", "scope", "fileId", "resourceLibraryId"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError("manual action matrix query contains unsupported fields")
        raw_kind = values.get("scopeKind", values.get("scope", [None]))[0]
        file_id = values.get("fileId", [None])[0]
        resource_library_id = values.get("resourceLibraryId", [None])[0]
        if raw_kind == "resourceLibrary":
            raw_kind = "resource_library"
        if (
            raw_kind is None
            and isinstance(resource_library_id, str)
            and resource_library_id.strip()
        ):
            raw_kind = "resource_library"
        if raw_kind is not None and raw_kind not in {"file", "resource_library"}:
            raise ValueError("manual action matrix scopeKind must be file or resource_library")
        if raw_kind is None and file_id is not None:
            raise ValueError("manual action matrix file scope requires scopeKind=file")
        if raw_kind == "file" and not isinstance(resource_library_id, str):
            raise ValueError("manual action matrix resourceLibraryId is required for file scope")

        can_scan = ApiPermission.SUBMIT_DRY_RUN in principal.permissions
        can_preview = ApiPermission.MANAGE_MANUAL_ORGANIZE in principal.permissions
        can_execute = ApiPermission.EXECUTE_MANUAL_ORGANIZE in principal.permissions
        configuration_snapshot_id = getattr(binding, "snapshot_id", None)
        # Determine runtime readiness: the binding has a snapshot_id when a
        # configuration has been activated and loaded.
        runtime_ready = bool(configuration_snapshot_id)
        scan_service_ready = callable(getattr(binding.manual_scans, "admit_current_document", None))
        preview_service_ready = callable(
            getattr(self._manual_previews, "create_current_from_index", None)
        )
        intent_service_ready = callable(getattr(self._manual_intents, "create", None))
        preview_intent_ready = callable(getattr(self._manual_previews, "create", None))
        execution_service_ready = callable(
            getattr(self._manual_execution, "begin_web_execution", None)
        )
        organize_worker = (
            self._organize_worker_evidence()
            if execution_service_ready
            else {
                "ready": False,
                "condition": "execution_service_unavailable",
                "durableState": "the admitted manual execution boundary is unavailable",
                "nextAction": "restore the admitted execution services, then refresh",
            }
        )
        scan_available = can_scan and runtime_ready and scan_service_ready
        preview_available = can_preview and runtime_ready and preview_service_ready
        organize_available = (
            can_execute
            and can_preview
            and runtime_ready
            and intent_service_ready
            and preview_intent_ready
            and execution_service_ready
            and bool(organize_worker["ready"])
        )
        scan_reason = (
            None
            if scan_available
            else (
                "the connected API principal does not hold the submit_dry_run permission "
                "required for Scan"
                if not can_scan
                else "the Active runtime is unavailable for Scan"
                if not runtime_ready
                else "the manual Scan service is unavailable"
                if not scan_service_ready
                else "Scan is unavailable"
            )
        )
        preview_reason = (
            None
            if preview_available
            else (
                "the connected API principal does not hold the manage_manual_organize "
                "permission required for Preview"
                if not can_preview
                else "the Active runtime is unavailable for Preview"
                if not runtime_ready
                else "the current-source Preview service is unavailable"
                if not preview_service_ready
                else "Preview is unavailable"
            )
        )
        organize_reason = (
            None
            if organize_available
            else (
                "the connected API principal does not hold the manage_manual_organize "
                "permission required to build a manual intent"
                if not can_preview
                else "the connected API principal does not hold the execute_manual_organize "
                "permission required for Organize"
                if not can_execute
                else "the Active runtime is unavailable for Organize"
                if not runtime_ready
                else "the manual intent, Preview or execution service is unavailable"
                if not (intent_service_ready and preview_intent_ready and execution_service_ready)
                else str(
                    organize_worker.get("durableState")
                    or "the resident Processing Worker cannot claim admitted work"
                )
                if not organize_worker["ready"]
                else "Organize is unavailable"
            )
        )
        # Resolve the ResourceLibrary choices from the system_status snapshot.
        sys_doc = {}
        system_status = getattr(binding, "system_status", None)
        if system_status is not None and callable(getattr(system_status, "as_document", None)):
            sys_doc = system_status.as_document()
        raw_rls = (
            sys_doc.get("resource_libraries", {}).get("items", [])
            if isinstance(sys_doc.get("resource_libraries"), dict)
            else []
        )
        rl_map: dict[str, dict] = {}
        for rl in raw_rls:
            if isinstance(rl, dict) and isinstance(rl.get("id"), str):
                rl_map[rl["id"]] = rl
        resource_libraries = [
            {
                "resourceLibraryId": rl["id"],
                "storageId": rl.get("storage_id"),
                "scanMode": rl.get("scan_mode"),
                "enabled": bool(rl.get("enabled", False)),
                "reason": (
                    None
                    if rl.get("enabled", False)
                    else "this ResourceLibrary is disabled in the Active configuration"
                ),
            }
            for rl in list(rl_map.values())[:100]
        ]
        source: dict[str, object] = {}
        selection_required = raw_kind is None
        if raw_kind is None:
            scan_available = False
            preview_available = False
            organize_available = False
            scan_reason = "select an exact ResourceLibrary scope before submitting a Scan"
            preview_reason = "select an exact ResourceLibrary scope before running a Preview"
            organize_reason = "select an exact scope before organizing"
        elif raw_kind == "file":
            if not isinstance(file_id, str) or not file_id.strip():
                raise ValueError("manual action matrix fileId is required for file scope")
            # Check ResourceLibrary availability.
            rl_info = rl_map.get(resource_library_id)
            if rl_info is None or not rl_info.get("enabled", False):
                scan_available = False
                preview_available = False
                organize_available = False
                scan_reason = "the configured ResourceLibrary is not available"
                preview_reason = "the configured ResourceLibrary is not available"
                organize_reason = "the configured ResourceLibrary is not available"
            else:
                # Resolve the FileIndex record.
                file_index = self._file_index
                lister = (
                    getattr(file_index, "list_by_resource_library", None) if file_index else None
                )
                record = None
                if callable(lister):
                    for candidate in lister(resource_library_id):
                        if getattr(candidate, "file_id", None) == file_id:
                            record = candidate
                            break
                if record is None:
                    scan_available = False
                    preview_available = False
                    organize_available = False
                    scan_reason = "the current FileIndex source was not found"
                    preview_reason = "the current FileIndex source was not found"
                    organize_reason = "the current FileIndex source was not found"
                elif (
                    getattr(record, "occurrence_state", None) != OccurrenceState.VERIFIED
                    or getattr(record, "scan_status", None) != FileScanStatus.READY
                    or not getattr(record, "occurrence_id", None)
                    or not getattr(record, "fingerprint", None)
                ):
                    scan_available = False
                    preview_available = False
                    organize_available = False
                    scan_reason = "the FileIndex source is not a verified ready current occurrence"
                    preview_reason = (
                        "the FileIndex source is not a verified ready current occurrence"
                    )
                    organize_reason = (
                        "the FileIndex source is not a verified ready current occurrence"
                    )
                else:
                    source = {
                        "fileId": file_id,
                        "resourceLibraryId": resource_library_id,
                        "storageId": getattr(record, "storage_id", None),
                        "path": bounded_identity_path(getattr(record, "path", None)),
                        "filename": getattr(record, "filename", None),
                        "sizeBytes": getattr(record, "size", None),
                        "occurrenceState": getattr(
                            getattr(record, "occurrence_state", None),
                            "value",
                            getattr(record, "occurrence_state", None),
                        ),
                        "scanStatus": getattr(
                            getattr(record, "scan_status", None),
                            "value",
                            getattr(record, "scan_status", None),
                        ),
                    }
        else:
            if file_id is not None:
                raise ValueError("manual action matrix file scope is required for resource_library")
            if not isinstance(resource_library_id, str) or not resource_library_id.strip():
                # Bounded discovery: the operator has not selected an exact
                # ResourceLibrary yet, so nothing is actionable.
                selection_required = True
                scan_available = False
                preview_available = False
                organize_available = False
                scan_reason = "select an exact ResourceLibrary scope before submitting a Scan"
                preview_reason = "select an exact ResourceLibrary scope before running a Preview"
                organize_reason = "select an exact ResourceLibrary scope before organizing"
            else:
                rl_info = rl_map.get(resource_library_id)
                if rl_info is None or not rl_info.get("enabled", False):
                    scan_available = False
                    preview_available = False
                    organize_available = False
                    scan_reason = "the configured ResourceLibrary is not available"
                    preview_reason = "the configured ResourceLibrary is not available"
                    organize_reason = "the configured ResourceLibrary is not available"
                else:
                    source = {
                        "resourceLibraryId": resource_library_id,
                        "storageId": rl_info.get("storage_id"),
                    }
        scope_id = file_id if raw_kind == "file" else resource_library_id
        return self._response(
            start_response,
            200,
            manual_action_matrix_operator_document(
                {
                    "scopeKind": "resourceLibrary" if raw_kind == "resource_library" else raw_kind,
                    "scopeId": scope_id if isinstance(scope_id, str) and scope_id else None,
                    "fileId": file_id if raw_kind == "file" else None,
                    "resourceLibraryId": resource_library_id,
                    "selectionRequired": bool(selection_required),
                    "source": source if source else None,
                    "resourceLibraries": resource_libraries,
                    "runtime": {
                        "ready": runtime_ready,
                        "condition": (
                            "configuration_active" if runtime_ready else "configuration_unavailable"
                        ),
                        "nextAction": (
                            None if runtime_ready else "restore or activate a valid Active runtime"
                        ),
                    },
                    "actions": {
                        "scan": {
                            "available": scan_available,
                            "reason": scan_reason,
                            "method": "POST",
                            "path": "/api/v1/operations/scans",
                            "nextAction": (
                                "submit a bounded Scan" if scan_available else scan_reason
                            ),
                            "modes": [mode.value for mode in ScanMode],
                        },
                        "preview": {
                            "available": preview_available,
                            "reason": preview_reason,
                            "method": "POST",
                            "path": "/api/v1/operations/previews",
                            "nextAction": (
                                "run a zero-mutation Preview"
                                if preview_available
                                else preview_reason
                            ),
                            "modes": [],
                        },
                        "organize": {
                            "available": organize_available,
                            "reason": organize_reason,
                            "method": "POST",
                            "path": "/api/v1/operations/organize/intents",
                            "nextAction": (
                                "create a durable manual intent, then request an exact Preview"
                                if organize_available
                                else organize_reason
                            ),
                            "modes": [],
                        },
                    },
                    "limits": {
                        "previewMaxItems": MAX_MANUAL_PREVIEW_ITEMS if can_preview else 0,
                    },
                }
            ),
        )

    @staticmethod
    def _list_page(list_values: Callable, limit: int, cursor: DecodedCursor | None):
        if cursor is None:
            return list_values(limit=limit + 1)
        boundary = (
            {"after": cursor.position}
            if cursor.direction is CursorDirection.NEXT
            else {"before": cursor.position}
        )
        return list_values(limit=limit + 1, **boundary)

    @staticmethod
    def _page_window(values, limit: int, cursor: DecodedCursor | None):
        if cursor is not None and cursor.direction is CursorDirection.PREVIOUS:
            page = values[-limit:]
            return page, len(values) > limit, bool(page)
        page = values[:limit]
        return page, bool(cursor and page), len(values) > limit

    @staticmethod
    def _page_cursor(
        kind: str,
        page: tuple | list,
        available: bool,
        direction: CursorDirection,
        *,
        scope: str | None = None,
    ) -> str | None:
        if not available or not page:
            return None
        record = page[0] if direction is CursorDirection.PREVIOUS else page[-1]
        attribute = {
            "tasks": "task_id",
            "jobs": "job_id",
            "task_items": "item_id",
            "task_results": "result_id",
            "notification_deliveries": "delivery_id",
            "schedule_audit": "audit_id",
            "automation_definition_occurrences": "occurrence_id",
            "operational_logs": "log_id",
        }[kind]
        identifier = getattr(record, attribute)
        timestamp = (
            record.emitted_at
            if kind in {"schedule_audit", "automation_definition_occurrences"}
            else record.occurred_at
            if kind == "operational_logs"
            else record.created_at
        )
        return encode_cursor(kind, timestamp, identifier, direction, scope=scope)

    @staticmethod
    def _parse_bounded_limit(raw: str, resource: str) -> int:
        try:
            limit = int(raw)
        except ValueError as error:
            raise ValueError(f"{resource} limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError(f"{resource} limit must be between 1 and 100")
        return limit

    @classmethod
    def _storage_browser_query(cls, environ: dict) -> dict[str, object]:
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"storageId", "path", "limit", "cursor", "expectedVersion", "expectedDigest"}
        if set(query).difference(allowed) or any(len(value) != 1 for value in query.values()):
            raise ValueError("Storage browser query contains unsupported or repeated fields")
        storage_id = query.get("storageId", [""])[0]
        if not storage_id:
            raise ValueError("Storage browser storageId is required")
        path = query.get("path", [""])[0]
        limit = cls._parse_bounded_limit(query.get("limit", ["50"])[0], "Storage browser")
        cursor = query.get("cursor", [None])[0]
        if cursor == "":
            raise ValueError("Storage browser cursor must not be empty")
        has_version = "expectedVersion" in query
        has_digest = "expectedDigest" in query
        if has_version != has_digest:
            raise ValueError("Storage browser expectedVersion and expectedDigest must be paired")
        expected_version = None
        expected_digest = None
        if has_version:
            try:
                expected_version = int(query["expectedVersion"][0])
            except ValueError as error:
                raise ValueError("Storage browser expectedVersion must be an integer") from error
            expected_digest = query["expectedDigest"][0]
            if not expected_digest:
                raise ValueError("Storage browser expectedDigest is required")
        return {
            "storage_id": storage_id,
            "path": path,
            "limit": limit,
            "cursor": cursor,
            "expected_version": expected_version,
            "expected_digest": expected_digest,
        }

    @staticmethod
    def _files_browser_unavailable(start_response: Callable):
        return MediaFlowApi._error(
            start_response,
            503,
            "configuration_unavailable",
            "managed Active runtime is unavailable for Files browsing",
            details={
                "authority": "MANAGED",
                "runtimeReady": False,
                "durableState": "managed_active_unavailable",
                "sideEffects": "none",
                "retrySafe": True,
                "nextAction": (
                    "inspect configuration status and restore or activate a valid Active runtime"
                ),
            },
        )

    @classmethod
    def _resource_library_files_query(
        cls, environ: dict, resource_library_id: str
    ) -> dict[str, object]:
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"path", "limit", "cursor"}
        if set(query).difference(allowed) or any(len(value) != 1 for value in query.values()):
            raise ValueError("ResourceLibrary Files query contains unsupported or repeated fields")
        if not resource_library_id:
            raise ValueError("ResourceLibrary Files route requires resourceLibraryId")
        cursor = query.get("cursor", [None])[0]
        if cursor == "":
            raise ValueError("ResourceLibrary Files cursor must not be empty")
        return {
            "resource_library_id": resource_library_id,
            "path": query.get("path", [""])[0],
            "limit": cls._parse_bounded_limit(query.get("limit", ["50"])[0], "Files"),
            "cursor": cursor,
        }

    @classmethod
    def _files_direct_text_query(cls, environ: dict) -> str:
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"path"}
        if set(query).difference(allowed) or any(len(value) != 1 for value in query.values()):
            raise ValueError("Files text query contains unsupported or repeated fields")
        path = query.get("path", [None])[0]
        if not isinstance(path, str) or not path:
            raise ValueError("Files text query requires a ResourceLibrary-relative path")
        return path

    @classmethod
    def _files_delete_impact_query(cls, environ: dict) -> list[str]:
        """The bounded multi-selection Delete impact query.

        ``path`` is the one deliberately repeatable field: the Web encodes a
        bounded selection as repeated ``?path=a&path=b`` values.  Every other
        field must appear exactly once, blank values are rejected, and the
        selection bound is enforced here so a valid multi-selection is not
        collapsed into a generic request error while unknown keys, empty values
        or an excessive selection still fail closed and actionably.
        """

        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(query).difference({"path"}):
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "the Delete impact query contains an unsupported field",
                status=400,
                next_action="request the impact summary with only bounded path values",
            )
        paths = query.get("path", [])
        if not paths:
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "the Delete impact query requires at least one selected path",
                status=400,
                next_action="select one or more files or directories and retry",
            )
        if any(not isinstance(path, str) or path == "" for path in paths):
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "the Delete impact query contains an empty path value",
                status=400,
                next_action="remove the empty selection and retry",
            )
        if len(paths) > MAX_DELETE_PATHS:
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "the Delete selection exceeds the bounded multi-selection limit",
                status=400,
                next_action=f"select at most {MAX_DELETE_PATHS} items per Delete command",
            )
        return paths

    @classmethod
    def _files_transfer_impact_query(cls, environ: dict) -> dict[str, object]:
        """The bounded zero-mutation Copy/Move impact query.

        ``path`` is the one deliberately repeatable field.  The destination
        ResourceLibrary, destination directory, operation and explicit conflict
        choice each appear exactly once; an unknown key, a blank value or an
        excessive selection fails closed with an actionable stable error.
        """

        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"path", "to", "toPath", "operation", "conflict"}
        if set(query).difference(allowed):
            raise DirectFileError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer impact query contains an unsupported field",
                status=400,
                next_action="request the transfer impact with only supported fields",
            )
        if any(len(value) != 1 for key, value in query.items() if key != "path"):
            raise DirectFileError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer impact query repeats a single-valued field",
                status=400,
                next_action="send each transfer field exactly once",
            )
        paths = query.get("path", [])
        if not paths or any(not isinstance(path, str) or path == "" for path in paths):
            raise DirectFileError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer impact query requires bounded non-empty source paths",
                status=400,
                next_action="select one or more files or directories and retry",
            )
        if len(paths) > MAX_TRANSFER_PATHS:
            raise DirectFileError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer selection exceeds the bounded multi-selection limit",
                status=400,
                next_action=f"transfer at most {MAX_TRANSFER_PATHS} items per command",
            )
        destination = query.get("to", [""])[0]
        if not isinstance(destination, str) or not destination:
            raise DirectFileError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer impact query requires a destination ResourceLibrary",
                status=400,
                next_action="choose an enabled destination ResourceLibrary and retry",
            )
        return {
            "paths": paths,
            "destination": destination,
            "destination_path": query.get("toPath", [""])[0],
            "operation": query.get("operation", [""])[0],
            "conflict_mode": query.get("conflict", [None])[0],
        }

    @classmethod
    def _files_direct_rename_evidence_query(cls, environ: dict) -> str:
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"path"}
        if set(query).difference(allowed) or any(len(value) != 1 for value in query.values()):
            raise ValueError("Files Rename evidence query contains unsupported or repeated fields")
        path = query.get("path", [None])[0]
        if not isinstance(path, str) or not path:
            raise ValueError("Files Rename evidence requires one ResourceLibrary-relative path")
        return path

    @classmethod
    def _runtime_files_query(cls, environ: dict) -> dict[str, object]:
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"storageId", "resourceLibrary", "path", "limit", "cursor"}
        if set(query).difference(allowed) or any(len(value) != 1 for value in query.values()):
            raise ValueError("Files query contains unsupported or repeated fields")
        storage_id = query.get("storageId", [""])[0]
        if not storage_id:
            raise ValueError("Files storageId is required")
        cursor = query.get("cursor", [None])[0]
        if cursor == "":
            raise ValueError("Files cursor must not be empty")
        return {
            "storage_id": storage_id,
            "resource_library_id": query.get("resourceLibrary", [None])[0],
            "path": query.get("path", [""])[0],
            "limit": cls._parse_bounded_limit(query.get("limit", ["50"])[0], "Files"),
            "cursor": cursor,
        }

    @classmethod
    def _current_preview_request(
        cls,
        document: dict,
        *,
        route_scope_kind: str | None = None,
        route_scope_id: str | None = None,
    ) -> dict[str, object]:
        """Validate the narrow current-source Preview admission contract."""

        if not isinstance(document, dict):
            raise ValueError("current-source Preview request must be an object")
        if route_scope_kind == "file":
            allowed = {
                "fileId",
                "resourceLibraryId",
                "occurrenceId",
                "sourceOccurrenceId",
                "fingerprint",
                "sourceFingerprint",
                "snapshotId",
                "snapshotDigest",
            }
            kind = "file"
            file_id = route_scope_id
        elif route_scope_kind == "resource_library":
            allowed = {"resourceLibraryId", "snapshotId", "snapshotDigest"}
            kind = "resource_library"
            file_id = None
        else:
            allowed = {
                "scope",
                "scopeKind",
                "resourceLibraryId",
                "fileId",
                "occurrenceId",
                "sourceOccurrenceId",
                "fingerprint",
                "sourceFingerprint",
                "snapshotId",
                "snapshotDigest",
            }
            raw_kind = document.get("scopeKind")
            raw_scope = document.get("scope")
            scope_id = None
            if isinstance(raw_scope, dict):
                if set(raw_scope).difference({"kind", "id"}):
                    raise ValueError("current-source Preview scope object is invalid")
                if raw_kind is not None:
                    raise ValueError("current-source Preview scope fields disagree")
                raw_kind = raw_scope.get("kind")
                scope_id = raw_scope.get("id")
            elif raw_scope is not None:
                if raw_kind is not None and cls._preview_scope_kind(
                    raw_kind
                ) != cls._preview_scope_kind(raw_scope):
                    raise ValueError("current-source Preview scope fields disagree")
                if raw_kind is None:
                    raw_kind = raw_scope
            if raw_kind is not None:
                raw_kind = cls._preview_scope_kind(raw_kind)
            kind = raw_kind
            file_id = document.get("fileId")
            resource_library_id = document.get("resourceLibraryId")
            if scope_id is not None:
                if not isinstance(scope_id, str) or not scope_id.strip():
                    raise ValueError("current-source Preview scope ID is invalid")
                if kind == "file":
                    if file_id is not None and file_id != scope_id:
                        raise ValueError("current-source Preview scope and fileId disagree")
                    file_id = scope_id
                elif kind == "resource_library":
                    if resource_library_id is not None and resource_library_id != scope_id:
                        raise ValueError(
                            "current-source Preview scope and resourceLibraryId disagree"
                        )
                    resource_library_id = scope_id
        if set(document).difference(allowed):
            raise ValueError(
                "current-source Preview accepts only bounded FileIndex identity and snapshot fields"
            )
        if not isinstance(kind, str) or kind not in {"file", "resource_library"}:
            raise ValueError("current-source Preview scope must be file or resource_library")

        if route_scope_kind is not None:
            resource_library_id = document.get("resourceLibraryId")
        if route_scope_id is not None and route_scope_kind == "resource_library":
            if resource_library_id is not None and resource_library_id != route_scope_id:
                raise ValueError("ResourceLibrary Preview route and body scope disagree")
            resource_library_id = route_scope_id
        if not isinstance(resource_library_id, str) or not resource_library_id.strip():
            raise ValueError("current-source Preview requires resourceLibraryId")
        if route_scope_kind == "file" and not isinstance(file_id, str):
            raise ValueError("current-source Preview file route is invalid")
        if (
            route_scope_kind == "file"
            and document.get("fileId") is not None
            and document["fileId"] != file_id
        ):
            raise ValueError("current-source Preview file route and body fileId disagree")
        if kind == "file" and not isinstance(file_id, str):
            raise ValueError("current-source Preview file scope requires fileId")
        if kind == "resource_library" and document.get("fileId") is not None:
            raise ValueError("ResourceLibrary Preview cannot contain fileId")

        occurrence_id = cls._same_request_alias(
            document, "occurrenceId", "sourceOccurrenceId", "occurrence ID"
        )
        fingerprint = cls._same_request_alias(
            document, "fingerprint", "sourceFingerprint", "source fingerprint"
        )
        if kind == "file":
            if not isinstance(occurrence_id, str) or not occurrence_id.strip():
                raise ValueError("current-source Preview requires occurrenceId")
            if not isinstance(fingerprint, str) or not fingerprint.strip():
                raise ValueError("current-source Preview requires fingerprint")
        elif occurrence_id is not None or fingerprint is not None:
            raise ValueError("ResourceLibrary Preview cannot contain source occurrence fields")
        has_snapshot_id = "snapshotId" in document
        has_snapshot_digest = "snapshotDigest" in document
        if has_snapshot_id != has_snapshot_digest:
            raise ValueError("current-source Preview snapshotId and snapshotDigest must be paired")
        if has_snapshot_id and (
            not isinstance(document["snapshotId"], str)
            or not document["snapshotId"].strip()
            or not isinstance(document["snapshotDigest"], str)
            or not document["snapshotDigest"].strip()
        ):
            raise ValueError("current-source Preview snapshot identity is invalid")
        return {
            "scope_kind": kind,
            "file_id": file_id,
            "resource_library_id": resource_library_id,
            "occurrence_id": occurrence_id,
            "fingerprint": fingerprint,
            "snapshot_id": document.get("snapshotId"),
            "snapshot_digest": document.get("snapshotDigest"),
        }

    @staticmethod
    def _preview_scope_kind(value: object) -> object:
        if value == "resourceLibrary":
            return "resource_library"
        return value

    @staticmethod
    def _same_request_alias(document: dict, first: str, second: str, label: str) -> str | None:
        first_value = document.get(first)
        second_value = document.get(second)
        if first_value is not None and second_value is not None and first_value != second_value:
            raise ValueError(f"current-source Preview {label} fields disagree")
        return first_value if first_value is not None else second_value

    @classmethod
    def _confirmation_value(cls, value) -> dict:
        document = cls._value(value)
        document.pop("note", None)
        return document

    @classmethod
    def _confirmation_audit_value(cls, value) -> dict:
        document = cls._value(value)
        document.pop("note", None)
        return document

    @classmethod
    def _metadata_review_audit_value(cls, value) -> dict:
        document = cls._value(value)
        document.pop("note", None)
        return document

    @classmethod
    def _metadata_correction_audit_value(cls, value) -> dict:
        document = cls._value(value)
        document.pop("note", None)
        return document

    @classmethod
    def _classification_review_audit_value(cls, value) -> dict:
        document = cls._value(value)
        document.pop("note", None)
        return document

    def _safe_audit(self, *args) -> None:
        try:
            if len(args) >= 6 and self._suppress_file_detail_audit(args[4], args[3], args[2]):
                return
            self._audit(*args)
        except Exception:
            pass

    @staticmethod
    def _suppress_file_detail_audit(path: str, method: str, principal) -> bool:
        """Read-only journey projections must not create durable audit mutations."""

        if method != "GET" or principal is None:
            return False
        if ApiPermission.READ not in getattr(principal, "permissions", ()):
            return False
        parts = [part for part in str(path).split("/") if part]
        if parts in (
            ["api", "v1", "management", "readiness"],
            ["api", "v1", "workers", "readiness"],
            ["api", "v1", "workers"],
        ):
            return True
        if parts[:3] == ["api", "v1", "manual-intents"] or (
            len(parts) >= 3
            and parts[:2] == ["api", "v1"]
            and parts[2] in {"manual-organize", "manual-organize-intents"}
        ):
            return True
        if parts[:3] == ["api", "v1", "manual-previews"]:
            return True
        if (
            len(parts) == 5
            and parts[:3] in (["api", "v1", "files"], ["api", "v1", "file-index"])
            and parts[4] == "previews"
        ):
            return True
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "previews"
        ):
            return True
        if tuple(parts[:3]) in {
            ("api", "v1", "manual-execution-authorizations"),
            ("api", "v1", "manual-executions"),
        }:
            return True
        if parts[:3] == ["api", "v1", "tasks"]:
            return True
        if parts[:3] == ["api", "v1", "scans"]:
            return True
        if parts[:4] == ["api", "v1", "automation", "task-definitions"] and (
            len(parts) in {4, 5}
            or (len(parts) == 6 and parts[5] in {"occurrences", "grant", "grant-state"})
            or (len(parts) == 7 and parts[5:7] == ["grant", "audit"])
        ):
            return True
        return (
            (
                parts[:3] in (["api", "v1", "files"], ["api", "v1", "file-index"])
                and (len(parts) == 4 or parts == ["api", "v1", parts[2], "by-source"])
            )
            or parts == ["api", "v1", "storage", "files"]
            or (
                len(parts) == 5
                and parts[:3] == ["api", "v1", "resource-libraries"]
                and parts[4] == "files"
            )
            or (
                len(parts) == 6
                and parts[:3] == ["api", "v1", "resource-libraries"]
                and parts[4] == "files"
                and parts[5] in {"text", "delete-impact"}
            )
        )

    @staticmethod
    def _document(environ: dict) -> dict:
        raw_length = environ.get("CONTENT_LENGTH", "0") or "0"
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if length < 0 or length > 16_384:
            raise ValueError("request body exceeds 16384 bytes")
        raw = environ["wsgi.input"].read(length)
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("request JSON must be an object")
        return value

    @staticmethod
    def _package_import_request(
        environ: dict,
    ) -> tuple[object, dict[str, object] | None]:
        raw_length = environ.get("CONTENT_LENGTH", "0") or "0"
        try:
            length = int(raw_length)
        except ValueError as error:
            raise PackageExchangeError(
                "package import Content-Length is invalid",
                code="invalid_request",
                status=400,
                durable_state="no_configuration_changed",
                next_action="resend the package with a valid Content-Length",
            ) from error
        if length <= 0 or length > MAX_CONFIGURATION_PACKAGE_BYTES:
            raise PackageExchangeError(
                "package import body exceeds the bounded package size",
                code="package_too_large",
                status=413,
                durable_state="no_configuration_changed",
                next_action="import a supported bounded configuration package",
            )
        raw = environ["wsgi.input"].read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PackageExchangeError(
                "package import body is not valid JSON",
                code="invalid_schema",
                status=422,
                durable_state="no_configuration_changed",
                next_action="import an unmodified JSON configuration package",
            ) from error
        if not isinstance(value, dict):
            raise PackageExchangeError(
                "package import body must be a JSON object",
                code="invalid_schema",
                status=422,
                durable_state="no_configuration_changed",
                next_action="import an unmodified JSON configuration package",
            )
        if "package" in value:
            allowed = {"package", "recovery"}
            if set(value).difference(allowed):
                raise PackageExchangeError(
                    "package import request contains unsupported fields",
                    code="invalid_request",
                    status=422,
                    durable_state="no_configuration_changed",
                    next_action="send only the package and optional recovery authority",
                )
            package_value = value["package"]
            recovery = value.get("recovery")
        else:
            package_value = value
            recovery = None
        if not isinstance(package_value, dict):
            raise PackageExchangeError(
                "configuration package must be an object",
                code="invalid_schema",
                status=422,
                durable_state="no_configuration_changed",
                next_action="import a supported configuration package",
            )
        if recovery is not None and not isinstance(recovery, dict):
            raise PackageExchangeError(
                "package import recovery authority must be an object",
                code="invalid_request",
                status=422,
                durable_state="no_configuration_changed",
                next_action="omit recovery or supply the exact current Draft identity",
            )
        return package_value, recovery

    @staticmethod
    def _optional_document(environ: dict) -> dict:
        raw_length = environ.get("CONTENT_LENGTH", "0") or "0"
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if length == 0:
            return {}
        return MediaFlowApi._document(environ)

    @staticmethod
    def _configuration_object_kind(value: str) -> ConfigurationObjectKind:
        mapping = {
            "storages": ConfigurationObjectKind.STORAGE,
            "resourceLibraries": ConfigurationObjectKind.RESOURCE_LIBRARY,
            "mediaLibraries": ConfigurationObjectKind.MEDIA_LIBRARY,
            "recognitionTypes": ConfigurationObjectKind.RECOGNITION_TYPE,
            "recognitionRules": ConfigurationObjectKind.RECOGNITION_RULE,
            "recognitionTypePolicies": ConfigurationObjectKind.RECOGNITION_TYPE_POLICY,
            "metadataPolicies": ConfigurationObjectKind.METADATA_POLICY,
            "namingPolicies": ConfigurationObjectKind.NAMING_POLICY,
            "classificationPolicies": ConfigurationObjectKind.CLASSIFICATION_POLICY,
            "organizePolicies": ConfigurationObjectKind.ORGANIZE_POLICY,
            "automationTaskDefinitions": ConfigurationObjectKind.SCHEDULE,
            "webhooks": ConfigurationObjectKind.WEBHOOK_DEFINITION,
        }
        try:
            return mapping[value]
        except KeyError as error:
            raise ValueError("unsupported guided configuration object kind") from error

    @staticmethod
    def _extract_system_settings_edits(
        document: dict[str, object],
    ) -> tuple[SystemSettingsEdit, ...]:
        if not isinstance(document, dict):
            raise ValueError("request body must be a JSON object")

        if "edits" in document:
            raw_edits = document["edits"]
            if not isinstance(raw_edits, list) or not raw_edits:
                raise ValueError("'edits' must be a non-empty array of objects")
            edits = []
            for item in raw_edits:
                if not isinstance(item, dict):
                    raise ValueError("each edit must be an object")
                field_path = item.get("fieldPath") or item.get("field")
                if not isinstance(field_path, str) or not field_path:
                    raise ValueError("edit fieldPath is required")
                edits.append(SystemSettingsEdit(field_path, item.get("value")))
            return tuple(edits)

        raw_settings = document.get("settings") if "settings" in document else document
        if not isinstance(raw_settings, dict):
            raise ValueError("'settings' must be an object")

        meta_keys = {
            "expectedVersion",
            "expectedActiveVersion",
            "expectedActiveRevisionId",
            "expectedActiveDigest",
            "revisionId",
            "fromActive",
            "settings",
        }

        edits = []

        def _flatten(d: dict[str, object], prefix: str = "") -> None:
            for key, val in d.items():
                if prefix == "" and key in meta_keys:
                    continue
                path = f"{prefix}.{key}" if prefix else key
                if isinstance(val, dict):
                    _flatten(val, path)
                else:
                    edits.append(SystemSettingsEdit(path, val))

        _flatten(raw_settings)
        if not edits:
            raise ValueError("at least one system setting edit is required")
        return tuple(edits)

    def _automation_revision(self, environ: dict):
        """Resolve one explicit managed revision for Automation inspection."""

        if self._configuration_service is None:
            return None
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"revisionId"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError("Automation Task Definition query accepts one revisionId")
        revision_id = values.get("revisionId", [None])[0]
        if revision_id:
            return self._configuration_service.require(revision_id)
        # Without an explicit revision selector this surface is the runtime
        # Automation view, so only the immutable Active snapshot may be
        # presented. A latest Draft/Validated revision is not an Active
        # authority and must not be labelled or consumed as one.
        return self._configuration_service.active()

    def _automation_definition_context(self, environ: dict, definition_id: str):
        """Return the immutable Active revision, raw definition, and validated domain value."""

        if self._configuration_service is None or self._configuration_objects is None:
            raise UnattendedExecutionGrantError(
                "managed configuration service is unavailable",
                code="service_unavailable",
                status=503,
                durable_state="no grant or media effect was created",
                next_action="restore the managed configuration service, then retry",
            )
        active = self._automation_revision({**environ, "QUERY_STRING": ""})
        if active is None:
            raise LookupError(f"automationTaskDefinitions {definition_id!r} was not found")
        detail = self._configuration_objects.revision_detail(active.revision_id)
        raw = next(
            (
                candidate
                for candidate in detail["objects"].get("automationTaskDefinitions", [])
                if candidate.get("id") == definition_id
            ),
            None,
        )
        if raw is None:
            raise LookupError(f"automationTaskDefinitions {definition_id!r} was not found")
        objects = detail["objects"]
        resources = objects.get("resourceLibraries")
        definition = AutomationTaskDefinition.from_document(
            raw,
            **({"resource_libraries": resources} if resources is not None else {}),
        )
        return active, raw, definition

    def _automation_definition_resolution(self, definition_id: str, start_response: Callable):
        """Resolve a definition from the Active revision, then the open Draft.

        Returns ``(active, raw, definition, draft, in_active)``. Newly created
        or copied definitions exist only inside an open successor Draft until
        activation, so Draft-only resolution keeps them reachable and editable
        without presenting them as Active. Returns the bounded 503 response
        when the configuration or Draft read fails (callers must return it
        unchanged); a definition found in neither source raises ``LookupError``
        exactly as the Active-only context did.
        """

        if self._configuration_service is None or self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        try:
            active = self._configuration_service.active()
            draft = self._configuration_service.latest_open_draft_containing(
                "automationTaskDefinitions", definition_id
            )
            raw = None
            definition = None
            detail = None
            if active is not None:
                detail = self._configuration_objects.revision_detail(active.revision_id)
                raw = next(
                    (
                        candidate
                        for candidate in detail["objects"].get("automationTaskDefinitions", [])
                        if isinstance(candidate, dict) and candidate.get("id") == definition_id
                    ),
                    None,
                )
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        in_active = raw is not None
        if raw is not None:
            resources = detail["objects"].get("resourceLibraries")
            definition = AutomationTaskDefinition.from_document(
                raw,
                **({"resource_libraries": resources} if resources is not None else {}),
            )
        if raw is None and draft is not None and active is not None:
            section = (
                draft.document.get("automationTaskDefinitions", [])
                if isinstance(draft.document, dict)
                else []
            )
            raw = next(
                (
                    item
                    for item in section
                    if isinstance(item, dict) and item.get("id") == definition_id
                ),
                None,
            )
        if raw is None:
            raise LookupError(f"automationTaskDefinitions {definition_id!r} was not found")
        return active, raw, definition, draft, in_active

    @staticmethod
    def _validate_grant_revision_binding(document: dict, active) -> None:
        revision_id = document.get("revisionId")
        if revision_id is not None and revision_id != active.revision_id:
            raise UnattendedExecutionGrantError(
                "grant request revision does not match the current Active configuration",
                code="unattended_execution_grant_snapshot_mismatch",
                next_action=(
                    "refresh the current Active configuration and review the exact bounds again"
                ),
            )
        expected = document.get("expectedVersion")
        if expected is not None and (
            isinstance(expected, bool)
            or not isinstance(expected, int)
            or expected != active.version
        ):
            raise UnattendedExecutionGrantError(
                "grant request configuration version is stale",
                code="unattended_execution_grant_snapshot_mismatch",
                next_action=(
                    "refresh the current Active configuration and review the exact bounds again"
                ),
            )

    @staticmethod
    def _file_stats_query(environ: dict) -> tuple[str | None, str | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"resourceLibrary", "storage"}
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError("file stats query accepts resourceLibrary and storage once")
        return values.get("resourceLibrary", [None])[0], values.get("storage", [None])[0]

    @staticmethod
    def _file_resource_query(environ: dict) -> str | None:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"resourceLibrary"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError("file detail query accepts resourceLibrary once")
        return values.get("resourceLibrary", [None])[0]

    @staticmethod
    def _file_by_source_query(environ: dict) -> tuple[str, str, str | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"storageId", "path", "resourceLibrary"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError(
                "file by-source query accepts storageId, path, and resourceLibrary once"
            )
        storage_id = values.get("storageId", [None])[0]
        path = values.get("path", [None])[0]
        if not storage_id or not path:
            raise ValueError("file by-source query requires storageId and path")
        return storage_id, path, values.get("resourceLibrary", [None])[0]

    @staticmethod
    def _file_catalog_query(environ: dict) -> FileCatalogFilter:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {
            "resourceLibrary",
            "storage",
            "scanStatus",
            "query",
            "limit",
            "after",
            "before",
            "cursorFileId",
            "recognitionType",
            "provider",
            "providerId",
            "title",
            "taskId",
            "year",
            "processingDisposition",
        }
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError("file catalog query fields must be supported and specified once")
        if "cursorFileId" in values and "after" not in values and "before" not in values:
            raise ValueError("file cursor requires after/before and cursorFileId")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], "file")
        scan_status = FileScanStatus(values["scanStatus"][0]) if "scanStatus" in values else None
        processing_disposition = (
            ProcessingDisposition(values["processingDisposition"][0])
            if "processingDisposition" in values
            else None
        )
        after = (
            MediaFlowApi._file_cursor(values.get("after"), values.get("cursorFileId"))
            if "after" in values
            else None
        )
        before = (
            MediaFlowApi._file_cursor(values.get("before"), values.get("cursorFileId"))
            if "before" in values
            else None
        )
        year = int(values["year"][0]) if "year" in values else None
        return FileCatalogFilter(
            resource_library_id=values.get("resourceLibrary", [None])[0],
            storage_id=values.get("storage", [None])[0],
            scan_status=scan_status,
            query=values.get("query", [None])[0],
            limit=limit,
            after=after,
            before=before,
            recognition_type=values.get("recognitionType", [None])[0],
            provider=values.get("provider", [None])[0],
            provider_id=values.get("providerId", [None])[0],
            title=values.get("title", [None])[0],
            task_id=values.get("taskId", [None])[0],
            year=year,
            processing_disposition=processing_disposition,
        )

    @staticmethod
    def _file_cursor(timestamp_values, file_id_values):
        timestamp = timestamp_values[0] if timestamp_values else None
        file_id = file_id_values[0] if file_id_values else None
        if timestamp is None and file_id is None:
            return None
        if timestamp is None or file_id is None:
            raise ValueError("file cursor requires after/before and cursorFileId")
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError as error:
            raise ValueError("file cursor timestamp must be ISO-8601") from error
        return parsed, file_id

    @staticmethod
    def _file_catalog_value(record) -> dict:
        disposition = getattr(record.processing_disposition, "value", record.processing_disposition)
        occurrence_state = getattr(record.occurrence_state, "value", record.occurrence_state)
        reprocess_eligible = bool(
            record.scan_status is FileScanStatus.READY
            and occurrence_state == "verified"
            and record.fingerprint
            and record.processing_result_id
            and disposition not in {"unknown", "unverified", "reprocess_requested"}
            and record.processing_retry_safety == "safe"
        )
        return {
            "fileId": record.file_id,
            "storageId": record.storage_id,
            "resourceLibraryId": record.resource_library_id,
            "path": record.path,
            "filename": record.filename,
            "extension": record.extension,
            "size": record.size,
            "modifiedAt": record.modified_at.isoformat(),
            "stableSince": record.stable_since.isoformat() if record.stable_since else None,
            "scanStatus": record.scan_status.value,
            "change": record.change.value,
            "firstSeenAt": record.first_seen_at.isoformat(),
            "lastSeenAt": record.last_seen_at.isoformat(),
            "missingSince": record.missing_since.isoformat() if record.missing_since else None,
            "lastScanId": record.last_scan_id,
            "updatedAt": record.updated_at.isoformat(),
            "discovery": {
                "status": record.scan_status.value,
                "change": record.change.value,
                "stableSince": record.stable_since.isoformat() if record.stable_since else None,
                "lastSeenAt": record.last_seen_at.isoformat(),
                "missingSince": record.missing_since.isoformat() if record.missing_since else None,
                "lastScanId": record.last_scan_id,
            },
            "processingDisposition": disposition,
            "processing": {
                "disposition": disposition,
                "resultId": record.processing_result_id,
                "effectCertainty": record.processing_effect_certainty,
                "retrySafety": record.processing_retry_safety,
                "nextAction": record.processing_next_action,
                "updatedAt": (
                    record.processing_updated_at.isoformat()
                    if record.processing_updated_at
                    else None
                ),
            },
            "priorResultRelevance": {
                "currentResultId": record.processing_result_id,
                "current": bool(
                    record.processing_result_id
                    and occurrence_state == "verified"
                    and disposition not in {"unknown", "unverified"}
                ),
                "historicalOnly": occurrence_state != "verified",
            },
            "currentOccurrence": {
                "occurrenceId": record.occurrence_id,
                "fingerprint": record.fingerprint,
                "fingerprintAlgorithm": record.fingerprint_algorithm,
                "fingerprintEvidence": dict(record.fingerprint_evidence or {}),
                "state": occurrence_state,
                "current": True,
            },
            "reprocess": {
                "eligible": reprocess_eligible,
                "reason": (
                    "explicit Reprocess is available for this current occurrence"
                    if reprocess_eligible
                    else (
                        "inspect the current disposition and occurrence before requesting Reprocess"
                    )
                ),
            },
        }

    def _manual_intent_document(self, intent, *, include_audit: bool = True) -> dict:
        document = intent.document(include_audit=include_audit)
        if self._manual_execution is not None:
            document["manualExecutionDiscovery"] = self._manual_execution.discovery_for_intent(
                intent.intent_id
            )
        return redact_manual_value(document)

    def _manual_preview_document(self, preview) -> dict:
        document = preview.document()
        if self._manual_execution is not None:
            document["manualExecutionDiscovery"] = self._manual_execution.discovery_for_preview(
                preview.preview_id
            )
        return redact_manual_value(document)

    # --- V2 manual Organize journey projections ----------------------------

    def _manual_step_error(self, start_response: Callable, error) -> list[bytes]:
        """One bounded, secret-free failure for a manual Organize step."""

        document = manual_step_error_document(error)
        status = int(document.pop("status", 409))
        return self._error(
            start_response,
            status,
            str(document.pop("code", "manual_organize_rejected")),
            str(document.pop("message", "the exact manual Organize step was rejected")),
            details=document,
        )

    def _require_organize_selection(self, item_ids: list, resource_library_id: str) -> None:
        """Resolve every selected FileIndex identity in its exact current scope.

        The browser submits only FileIndex identities it already rendered; the
        backend resolves each one through the current catalog inside the chosen
        ResourceLibrary, so a stale, foreign or fabricated identity can never
        become a durable manual intent.
        """

        catalog_reader = getattr(self._file_catalog, "show", None) if self._file_catalog else None
        index_reader = (
            getattr(self._file_index, "list_by_resource_library", None)
            if self._file_index is not None
            else None
        )
        seen: set[str] = set()
        for raw in item_ids:
            if not isinstance(raw, str) or not raw.strip() or len(raw) > 512:
                raise ValueError(
                    "operations organize selection contains an invalid FileIndex identity"
                )
            file_id = raw.strip()
            if file_id in seen:
                raise ValueError(
                    "operations organize selection contains a duplicate FileIndex identity"
                )
            seen.add(file_id)
            record = None
            if callable(catalog_reader):
                try:
                    record = catalog_reader(file_id, resource_library_id=resource_library_id)
                except LookupError:
                    record = None
                except Exception as error:
                    raise ValueError(
                        "the selected FileIndex scope could not be resolved from the current "
                        "catalog"
                    ) from error
            if record is None and callable(index_reader):
                for candidate in index_reader(resource_library_id):
                    if getattr(candidate, "file_id", None) == file_id:
                        record = candidate
                        break
            if record is None:
                raise ValueError(
                    "a selected FileIndex record is not current in the chosen ResourceLibrary"
                )

    def _organize_worker_evidence(self) -> dict[str, object]:
        """Backend-authoritative Worker evidence for the admitted execution queue."""

        if self._worker_service is None:
            return {
                "ready": False,
                "condition": "worker_service_unavailable",
                "durableState": "the Processing Worker service is unavailable",
                "nextAction": ("restore the resident Processing Worker, then refresh this journey"),
            }
        readiness = self._worker_service.evaluate_manual_organize_readiness(
            runtime_schema_version=SCHEMA_VERSION
        )
        return {
            "ready": bool(readiness.get("ready")),
            "condition": readiness.get("condition"),
            "durableState": readiness.get("durableState"),
            "nextAction": readiness.get("nextAction"),
        }

    def _organize_intent_document(self, intent, principal: ResolvedApiPrincipal) -> dict:
        document = manual_intent_operator_document(intent.document(include_audit=False))
        document["journey"] = "organize"
        intent_id = document.get("intentId")
        items = [item for item in document.get("items") or [] if isinstance(item, dict)]
        open_intent = document.get("status") == "open"
        ready_items = [item for item in items if item.get("status") == "ready"]
        manage_permitted = ApiPermission.MANAGE_MANUAL_ORGANIZE in principal.permissions
        execute_permitted = ApiPermission.EXECUTE_MANUAL_ORGANIZE in principal.permissions
        choice_reason = self._organize_unavailable_reason(
            manage_permitted,
            ApiPermission.MANAGE_MANUAL_ORGANIZE,
            "the connected API principal cannot edit this manual intent",
        ) or (
            None
            if open_intent and items
            else "this manual intent is closed and no longer accepts a choice edit"
        )
        preview_reason = self._organize_unavailable_reason(
            manage_permitted,
            ApiPermission.MANAGE_MANUAL_ORGANIZE,
            "the connected API principal cannot create an exact Preview for this intent",
        ) or (
            None
            if open_intent and ready_items and len(ready_items) == len(items)
            else "every intent item must be current and ready before a zero-mutation Preview"
        )
        document["actions"] = {
            "choice": {
                "available": choice_reason is None,
                "reason": choice_reason,
                "method": "POST",
                "path": (
                    f"/api/v1/operations/organize/intents/{intent_id}/items/{{itemId}}/choice"
                    if isinstance(intent_id, str) and intent_id
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": (
                    "a durable optimistic choice revision is stored and every earlier Preview "
                    "of this intent becomes historical evidence"
                ),
                "nextAction": (
                    "edit one item choice with its current intent and item versions"
                    if choice_reason is None
                    else "reopen this intent from current Files if its choices must change"
                ),
            },
            "preview": {
                "available": preview_reason is None,
                "reason": preview_reason,
                "method": "POST",
                "path": (
                    f"/api/v1/operations/organize/intents/{intent_id}/previews"
                    if isinstance(intent_id, str) and intent_id
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": "a durable zero-mutation Preview revision is stored",
                "nextAction": (
                    "create a fresh exact Preview of the reviewed choices"
                    if preview_reason is None
                    else "reload the current intent and repair the blocked item evidence"
                ),
            },
            "execute": {
                "available": False,
                "reason": (
                    "exact execution is only offered from a current, complete Preview"
                    if execute_permitted
                    else "the connected API principal does not hold the "
                    "execute_manual_organize permission"
                ),
                "method": None,
                "path": None,
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "create a fresh exact Preview after the last choice change",
            },
        }
        document["limits"] = {"intentMaxItems": self._organize_intent_limit()}
        return document

    def _organize_preview_document(self, preview, principal: ResolvedApiPrincipal) -> dict:
        document = manual_preview_operator_document(preview.document())
        document["journey"] = "organize"
        preview_id = document.get("previewId")
        items = [item for item in document.get("items") or [] if isinstance(item, dict)]
        executable = [
            item
            for item in items
            if item.get("current") is True
            and item.get("truncated") is False
            and item.get("status") == "previewed"
            and item.get("executionState") == "ready_for_explicit_authorization"
        ]
        blocked = len(items) - len(executable)
        manage_permitted = ApiPermission.MANAGE_MANUAL_ORGANIZE in principal.permissions
        execute_permitted = ApiPermission.EXECUTE_MANUAL_ORGANIZE in principal.permissions
        worker = self._organize_worker_evidence()
        reason: str | None = None
        if not manage_permitted or not execute_permitted:
            reason = (
                "the connected API principal does not hold the permissions required to "
                "execute reviewed manual work"
            )
        elif not document.get("current"):
            reason = "this Preview is historical evidence and can no longer be executed"
        elif document.get("truncated"):
            reason = "this Preview is truncated and cannot authorize exact work"
        elif not executable:
            reason = "no Preview item is current, complete and executable"
        elif not worker["ready"]:
            reason = str(
                worker.get("durableState")
                or "the resident Processing Worker cannot claim admitted work"
            )
        document["executionCandidateItemIds"] = [item.get("itemId") for item in executable]
        document["blockedItemCount"] = blocked
        document["worker"] = worker
        document["actions"] = {
            "execute": {
                "available": reason is None,
                "reason": reason,
                "method": "POST",
                "path": (
                    f"/api/v1/operations/organize/previews/{preview_id}/execute"
                    if isinstance(preview_id, str) and preview_id
                    else None
                ),
                "requiresConfirmation": True,
                "sideEffects": "reported_per_item",
                "durableOutcome": (
                    "one durable admitted execution and its Processing Worker outcome are "
                    "stored; only OrganizerExecutor may then mutate Storage"
                ),
                "nextAction": (
                    "confirm one Execute action for the selected exact items"
                    if reason is None
                    else str(
                        worker.get("nextAction")
                        if not worker["ready"]
                        else "request a fresh Preview after repairing the blocked items"
                    )
                ),
            },
            "intent": {
                "available": isinstance(document.get("intentId"), str),
                "reason": None,
                "method": "GET",
                "path": (
                    f"/api/v1/operations/organize/intents/{document.get('intentId')}"
                    if isinstance(document.get("intentId"), str)
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "reopen the durable intent to change a choice",
            },
        }
        return document

    def _organize_execution_document(self, execution) -> dict:
        document_reader = (
            getattr(self._manual_execution, "document", None)
            if self._manual_execution is not None
            else None
        )
        if callable(document_reader):
            source = document_reader(execution.execution_id)
        else:
            source = execution.document()
        document = manual_execution_operator_document(source)
        document["journey"] = "organize"
        execution_id = document.get("executionId")
        status = document.get("status")
        if status == "admitted":
            next_action = (
                "the reviewed work is durably admitted and waits for the resident Processing "
                "Worker to claim it"
            )
            durable_state = "admitted"
        elif status == "running":
            next_action = (
                "the resident Processing Worker owns this exact execution; refresh to read "
                "each independent item outcome"
            )
            durable_state = "running"
        elif status == "completed":
            next_action = "inspect the verified per-item Results; no replay is required"
            durable_state = "completed"
        elif status == "partial_success":
            next_action = (
                "inspect each failed item and use Review & Recovery; uncertain effects are "
                "never replayed automatically"
            )
            durable_state = "partially_completed"
        elif status == "cancelled":
            next_action = "this execution was cancelled; inspect the preserved item outcomes"
            durable_state = "cancelled"
        else:
            next_action = (
                "inspect each failed item, repair the cause and request a fresh Preview; "
                "uncertain effects are never replayed automatically"
            )
            durable_state = "terminal_failure"
        document["durableState"] = durable_state
        document["nextAction"] = next_action
        document["actions"] = {
            "detail": {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": (
                    f"/api/v1/operations/organize/executions/{execution_id}"
                    if isinstance(execution_id, str) and execution_id
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": next_action,
            },
            "task": {
                "available": isinstance(document.get("taskId"), str),
                "reason": None,
                "method": "GET",
                "path": (
                    f"/api/v1/operations/tasks/{document.get('taskId')}"
                    if isinstance(document.get("taskId"), str)
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "inspect the durable Task and its per-item Results",
            },
            "recovery": {
                "available": status in {"partial_success", "failed"},
                "reason": (
                    None
                    if status in {"partial_success", "failed"}
                    else "recovery is only offered for an execution with a failed item"
                ),
                "method": None,
                "path": None,
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": (
                    "open Review & Recovery to inspect the failed item; MediaFlow never "
                    "replays an uncertain mutation automatically"
                ),
            },
        }
        return document

    def _organize_unavailable_reason(
        self, permitted: bool, permission: ApiPermission, message: str
    ) -> str | None:
        if permitted:
            return None
        return f"{message} (required permission: {permission.value})"

    def _organize_intent_limit(self) -> int:
        limit = getattr(self._manual_intents, "MAX_ITEMS", None)
        return limit if isinstance(limit, int) else 0

    def _automation_preview_document(self, preview, *, item_limit: int = 100) -> dict:
        document = redact_manual_value(preview.document())
        items = document.pop("items", [])
        document["items"] = items[:item_limit]
        document["itemTotal"] = len(items)
        document["itemsTruncated"] = len(items) > item_limit
        return document

    def _invalidate_automation_previews(self, definition_id: str, reason: str) -> None:
        if self._automation_previews is None:
            return
        self._automation_previews.invalidate(definition_id, reason)

    _AUTOMATION_OPERATOR_DENIED_KEYS = frozenset(
        {
            "plan",
            "planFingerprint",
            "sourceFingerprint",
            "definitionFingerprint",
            "definitionCurrentFingerprint",
            "configurationRevisionDigest",
            "configurationSnapshotDigest",
            "digest",
        }
    )

    @classmethod
    def _strip_automation_operator_evidence(
        cls, value: object, *, drop_definition_version: bool = False
    ) -> object:
        """Rebuild operator evidence without digests, fingerprints or raw plans.

        The V2 Automation journey consumes bounded operator projections. The
        revision digests, definition fingerprints, source fingerprints and
        organize plans that the managed-configuration and automation services
        publish are server-side binding evidence; they stay on the existing
        surfaces and never enter these documents.
        """

        if isinstance(value, dict):
            return {
                key: cls._strip_automation_operator_evidence(
                    item, drop_definition_version=drop_definition_version
                )
                for key, item in value.items()
                if key not in cls._AUTOMATION_OPERATOR_DENIED_KEYS
                and not (drop_definition_version and key == "definitionVersion")
            }
        if isinstance(value, list):
            return [
                cls._strip_automation_operator_evidence(
                    item, drop_definition_version=drop_definition_version
                )
                for item in value
            ]
        return value

    @staticmethod
    def _automation_active_configuration(active) -> dict | None:
        """The exact immutable Active identity, without its digest evidence."""

        if active is None:
            return None
        return {
            "revisionId": active.revision_id,
            "version": active.version,
            "revisionSequence": active.revision_sequence,
            "status": active.status.value,
        }

    def _automation_draft_state(self, draft, *, empty_reason: str) -> dict:
        """Bounded open-Draft evidence for one definition or for the list."""

        if draft is None:
            return {
                "present": False,
                "reason": empty_reason,
                "revisionId": None,
                "revisionVersion": None,
                "revisionStatus": None,
                "baseActiveRevisionId": None,
                "updatedAt": None,
                "validatedAt": None,
                "validationErrors": [],
            }
        return {
            "present": True,
            "reason": None,
            "revisionId": draft.revision_id,
            "revisionVersion": draft.version,
            "revisionStatus": draft.status.value,
            "baseActiveRevisionId": draft.base_active_revision_id,
            "updatedAt": draft.updated_at.isoformat(),
            "validatedAt": draft.validated_at.isoformat() if draft.validated_at else None,
            "validationErrors": list(draft.validation_errors),
        }

    @staticmethod
    def _automation_resource_library_options(objects: object) -> list[dict]:
        """Bounded ResourceLibrary options for the definition form."""

        values = objects.get("resourceLibraries") if isinstance(objects, dict) else None
        options: list[dict] = []
        for value in values or []:
            if not isinstance(value, dict) or not isinstance(value.get("id"), str):
                continue
            options.append(
                {
                    "id": value["id"],
                    "name": value.get("name") if isinstance(value.get("name"), str) else None,
                    "enabled": value.get("enabled") is True,
                }
            )
        return options[:100]

    def _automation_definition_actions(
        self,
        definition_id: str,
        principal: ResolvedApiPrincipal,
        *,
        active,
        draft_present: bool,
        in_active: bool = True,
    ) -> dict:
        """Backend-authoritative action metadata for one definition document.

        A Draft-only definition (newly created or copied) is editable but not
        yet consumed by runtime, so Active-definition actions such as Preview
        or unattended authority are unavailable until its Draft is activated.
        """

        permissions = principal.permissions
        manage = ApiPermission.MANAGE_CONFIGURATION in permissions
        grant_permitted = ApiPermission.GRANT_UNATTENDED_EXECUTION in permissions
        dry_run = ApiPermission.SUBMIT_DRY_RUN in permissions
        active_revision_id = active.revision_id if active is not None else None
        not_active_reason = (
            "this definition exists only inside an open successor Draft; "
            "activate the Draft to make it the Active definition"
        )
        return {
            "detail": {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": (f"/api/v1/operations/automation/task-definitions/{definition_id}"),
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": ("inspect the durable definition, schedule and occurrence state"),
            },
            "occurrences": {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": (
                    f"/api/v1/operations/automation/task-definitions/{definition_id}/occurrences"
                ),
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "inspect the bounded occurrence history and its linked work",
            },
            "preview": {
                "available": dry_run and in_active,
                "reason": (
                    not_active_reason
                    if not in_active
                    else self._organize_unavailable_reason(
                        dry_run,
                        ApiPermission.SUBMIT_DRY_RUN,
                        "the connected API principal cannot run a zero-mutation Automation Preview",
                    )
                ),
                "method": "POST",
                "path": f"/api/v1/automation/task-definitions/{definition_id}/preview",
                "sideEffects": "none",
                "durableOutcome": (
                    "a durable zero-mutation Preview of the exact Active definition is stored"
                ),
                "nextAction": (
                    "create the exact Preview after reviewing the current schedule and scope"
                ),
            },
            "grantState": {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": f"/api/v1/automation/task-definitions/{definition_id}/grant-state",
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "read the current unattended grant state and its eligibility",
            },
            "grant": {
                "available": grant_permitted and in_active,
                "reason": (
                    not_active_reason
                    if not in_active
                    else self._organize_unavailable_reason(
                        grant_permitted,
                        ApiPermission.GRANT_UNATTENDED_EXECUTION,
                        "the connected API principal cannot grant unattended execution authority",
                    )
                ),
                "method": "POST",
                "path": f"/api/v1/automation/task-definitions/{definition_id}/grant",
                "requiresConfirmation": True,
                "sideEffects": "none",
                "durableOutcome": (
                    "a persistent scoped unattended execution grant is stored and audited"
                ),
                "nextAction": (
                    "run a fresh exact Preview, review its eligibility and explicitly "
                    "confirm the unattended grant"
                ),
            },
            "revoke": {
                "available": grant_permitted and in_active,
                "reason": (
                    not_active_reason
                    if not in_active
                    else self._organize_unavailable_reason(
                        grant_permitted,
                        ApiPermission.GRANT_UNATTENDED_EXECUTION,
                        "the connected API principal cannot revoke unattended execution authority",
                    )
                ),
                "method": "POST",
                "path": f"/api/v1/automation/task-definitions/{definition_id}/revoke",
                "sideEffects": "none",
                "durableOutcome": (
                    "the grant is revoked; future unattended mutation is prevented without "
                    "rewriting completed effects"
                ),
                "nextAction": "revoke the grant when its exact bounds are no longer wanted",
            },
            "copy": {
                "available": manage and draft_present,
                "reason": (
                    self._organize_unavailable_reason(
                        manage,
                        ApiPermission.MANAGE_CONFIGURATION,
                        "the connected API principal cannot copy Automation Task Definitions",
                    )
                    if not manage
                    else (
                        None
                        if draft_present
                        else "an open successor Draft is required to copy this definition"
                    )
                ),
                "method": "POST",
                "path": f"/api/v1/automation/task-definitions/{definition_id}/copy",
                "sideEffects": "none",
                "durableOutcome": ("a copied definition is stored inside the open successor Draft"),
                "nextAction": (
                    "create or open a successor Draft, then copy the definition inside it"
                ),
            },
            "draftCreate": {
                "available": manage and active is not None,
                "reason": (
                    self._organize_unavailable_reason(
                        manage,
                        ApiPermission.MANAGE_CONFIGURATION,
                        "the connected API principal cannot create a successor Draft",
                    )
                    if not manage
                    else (
                        None
                        if active is not None
                        else "no Active configuration exists; managed "
                        "configuration setup owns the first Draft"
                    )
                ),
                "method": "POST",
                "path": (
                    f"/api/v1/configuration/revisions/{active_revision_id}/successor"
                    if active_revision_id is not None
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": (
                    "a successor Draft seeded from the immutable Active configuration is stored"
                ),
                "nextAction": (
                    "create or open the successor Draft, edit the definition, then validate "
                    "and explicitly activate"
                ),
            },
        }

    def _automation_definition_operator_document(
        self,
        document: dict,
        *,
        principal: ResolvedApiPrincipal,
        active=None,
        draft=None,
        eligibility: dict | None = None,
        in_active: bool = True,
    ) -> dict:
        """Bounded, digest-free V2 operator projection for one definition."""

        definition_id = str(document.get("id", ""))
        operator = self._strip_automation_operator_evidence(document)
        operator["definitionState"] = "active" if in_active else "draft-only"
        operator["activeConfiguration"] = self._automation_active_configuration(active)
        draft_state = self._automation_draft_state(
            draft,
            empty_reason=(
                "no open successor Draft contains this definition; create one to edit it"
            ),
        )
        operator["draftState"] = draft_state
        operator["actions"] = self._automation_definition_actions(
            definition_id,
            principal,
            active=active,
            draft_present=bool(draft_state["present"]),
            in_active=in_active,
        )
        if eligibility is not None:
            operator["grantEligibility"] = self._strip_automation_operator_evidence(eligibility)
        return operator

    def _automation_occurrence_operator_document(self, document: dict) -> dict:
        """Bounded occurrence projection with exact linked-work transports."""

        operator = self._strip_automation_operator_evidence(document)
        actions: dict[str, object] = {}
        task_id = operator.get("taskId")
        if isinstance(task_id, str) and task_id:
            actions["task"] = {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": f"/api/v1/operations/tasks/{task_id}",
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "inspect the durable Task and its per-item Results",
            }
        job_id = operator.get("jobId")
        if isinstance(job_id, str) and job_id:
            actions["job"] = {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": f"/api/v1/operations/jobs/{job_id}",
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "inspect the durable admission Job",
            }
        operator["actions"] = actions
        return operator

    def _automation_preview_operator_document(
        self,
        preview,
        *,
        principal: ResolvedApiPrincipal,
        eligibility: dict | None = None,
    ) -> dict:
        """Bounded, digest-free V2 operator projection for one exact Preview."""

        document = self._automation_preview_document(preview)
        operator = self._strip_automation_operator_evidence(document, drop_definition_version=True)
        definition_id = str(operator.get("definitionId", ""))
        preview_id = str(operator.get("previewId", ""))
        grant_permitted = ApiPermission.GRANT_UNATTENDED_EXECUTION in principal.permissions
        preview_ready = operator.get("current") is True and operator.get("zeroMutation") is True
        operator["actions"] = {
            "detail": {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": (
                    f"/api/v1/operations/automation/task-definitions/{definition_id}"
                    f"/previews/{preview_id}"
                ),
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "inspect the exact Preview evidence and its items",
            },
            "items": {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": (
                    f"/api/v1/operations/automation/task-definitions/{definition_id}"
                    f"/previews/{preview_id}/items"
                ),
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "page the bounded Preview item evidence",
            },
            "definition": {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": (f"/api/v1/operations/automation/task-definitions/{definition_id}"),
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "reopen the durable definition behind this Preview",
            },
            "grantState": {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": f"/api/v1/automation/task-definitions/{definition_id}/grant-state",
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "read the current unattended grant state and its eligibility",
            },
            "grant": {
                "available": grant_permitted and preview_ready,
                "reason": (
                    None
                    if grant_permitted and preview_ready
                    else (
                        self._organize_unavailable_reason(
                            grant_permitted,
                            ApiPermission.GRANT_UNATTENDED_EXECUTION,
                            "the connected API principal cannot grant unattended "
                            "execution authority",
                        )
                        if not grant_permitted
                        else (
                            "this Preview is historical, truncated or incomplete and "
                            "cannot support unattended authority; run a fresh exact Preview"
                        )
                    )
                ),
                "method": "POST",
                "path": f"/api/v1/automation/task-definitions/{definition_id}/grant",
                "requiresConfirmation": True,
                "sideEffects": "none",
                "durableOutcome": (
                    "a persistent scoped unattended execution grant bound to this exact "
                    "Preview is stored and audited"
                ),
                "nextAction": (
                    "review the grant eligibility and explicitly confirm the unattended grant"
                ),
            },
        }
        if eligibility is not None:
            operator["grantEligibility"] = self._strip_automation_operator_evidence(eligibility)
        return operator

    def _automation_grant_eligibility(
        self,
        active,
        definition,
        principal: ResolvedApiPrincipal,
        *,
        persisted=None,
    ) -> dict:
        """The shared read-only unattended-grant admission decision."""

        resource = next(
            (
                value
                for value in active.document.get("resourceLibraries", [])
                if value.get("id") == definition.resource_library_id
            ),
            None,
        )
        candidate_preview_id = None
        if persisted is not None and persisted.status.value == "active":
            candidate_preview_id = persisted.preview_id
        elif self._automation_previews is not None:
            try:
                candidate_preview_id = self._automation_previews.latest_readonly(
                    definition.definition_id
                ).preview_id
            except Exception:
                candidate_preview_id = None
        return self._unattended_grants.project_eligibility(
            definition,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
            configuration_snapshot_version=active.version,
            preview_id=candidate_preview_id,
            storage_id=resource.get("storageId") if resource is not None else None,
            max_items_per_run=(
                persisted.max_items_per_run
                if persisted is not None and persisted.status.value == "active"
                else definition.item_limit
            ),
            principal_id=(
                persisted.granting_principal
                if persisted is not None and persisted.status.value == "active"
                else principal.principal_id
            ),
        )

    def _automation_operations_projection(
        self,
        parts: list[str],
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """Dispatch the bounded V2 Automation operator projections.

        The read documents are the exact, digest-free evidence the Web journey
        consumes. The raw managed-configuration and automation documents stay
        on the existing /api/v1/automation and /api/v1/configuration surfaces.
        The one mutation here is the automation-scoped checked activation: it
        composes the existing read-only Storage/strategy/destination checks
        server-side so the browser never handles a revision digest.
        """

        if len(parts) == 7 and parts[6] == "activate-draft" and method == "POST":
            return self._automation_definition_activate_checked_draft(
                parts[5], environ, start_response, principal
            )
        if method != "GET":
            return self._error(start_response, 405, "method_not_allowed", "GET required")
        self._require(principal, ApiPermission.READ)
        if self._configuration_service is None or self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        if len(parts) == 5:
            self._require_empty_query(environ, "operations automation definitions")
            return self._automation_definitions_operator_page(environ, start_response, principal)
        if len(parts) == 6:
            self._require_empty_query(environ, "operations automation definition")
            return self._automation_definition_operator_detail(parts[5], start_response, principal)
        if len(parts) == 7 and parts[6] == "draft":
            self._require_empty_query(environ, "operations automation definition draft")
            return self._automation_definition_operator_draft(parts[5], start_response, principal)
        if len(parts) == 7 and parts[6] == "occurrences":
            return self._automation_definition_operator_occurrences(
                parts[5], environ, start_response, principal
            )
        if len(parts) == 8 and parts[6] == "previews":
            self._require_empty_query(environ, "operations automation Preview")
            return self._automation_definition_operator_preview(
                parts[5], parts[7], start_response, principal
            )
        if len(parts) == 9 and parts[6] == "previews" and parts[8] == "items":
            return self._automation_definition_operator_preview_items(
                parts[5], parts[7], environ, start_response
            )
        return self._error(start_response, 404, "not_found", "route was not found")

    def _automation_definitions_operator_page(
        self, environ: dict, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        active = self._configuration_service.active()
        if active is None:
            manage = ApiPermission.MANAGE_CONFIGURATION in principal.permissions
            return self._response(
                start_response,
                200,
                {
                    "activeConfiguration": None,
                    "items": [],
                    "total": 0,
                    "truncated": False,
                    "draftState": self._automation_draft_state(
                        None,
                        empty_reason=(
                            "no Active configuration exists; managed configuration "
                            "setup owns the first Draft"
                        ),
                    ),
                    "resourceLibraryOptions": [],
                    "actions": {
                        "create": {
                            "available": False,
                            "reason": (
                                self._organize_unavailable_reason(
                                    manage,
                                    ApiPermission.MANAGE_CONFIGURATION,
                                    "the connected API principal cannot create "
                                    "Automation Task Definitions",
                                )
                                if not manage
                                else "no Active configuration exists; managed "
                                "configuration setup owns the first Draft"
                            ),
                            "method": "POST",
                            "path": "/api/v1/automation/task-definitions",
                            "sideEffects": "none",
                            "durableOutcome": (
                                "the bounded definition is stored inside the open successor Draft"
                            ),
                            "nextAction": (
                                "complete managed configuration setup, then create "
                                "definitions inside a successor Draft"
                            ),
                        },
                        "createDraft": {
                            "available": False,
                            "reason": (
                                self._organize_unavailable_reason(
                                    manage,
                                    ApiPermission.MANAGE_CONFIGURATION,
                                    "the connected API principal cannot create a successor Draft",
                                )
                                if not manage
                                else "no Active configuration exists; managed "
                                "configuration setup owns the first Draft"
                            ),
                            "method": "POST",
                            "path": None,
                            "sideEffects": "none",
                            "durableOutcome": (
                                "a successor Draft seeded from the immutable Active "
                                "configuration is stored"
                            ),
                            "nextAction": (
                                "complete managed configuration setup before staging "
                                "a successor Draft"
                            ),
                        },
                    },
                },
            )
        detail = self._configuration_objects.revision_detail(active.revision_id)
        all_items = detail["objects"].get("automationTaskDefinitions", [])
        try:
            drafts = self._configuration_service.open_draft_revisions()
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        active_ids = {
            str(candidate.get("id"))
            for candidate in all_items
            if isinstance(candidate, dict) and isinstance(candidate.get("id"), str)
        }
        draft_by_id: dict[str, object] = {}
        draft_only: list[tuple[object, dict]] = []
        seen_draft_only: set[str] = set()
        draft_only_total = 0
        # One deterministic combined page limit for Active and Draft-only
        # definitions: the Active document order fills the page first and
        # draft-only definitions take the remaining capacity. The frontend
        # normalizer fails closed on any page above this limit, so the merged
        # response must never exceed it; dropped definitions stay counted in
        # the truthful total and the truncated flag.
        active_page = all_items[: self.AUTOMATION_DEFINITIONS_PAGE_LIMIT]
        draft_capacity = self.AUTOMATION_DEFINITIONS_PAGE_LIMIT - len(active_page)
        for draft in drafts:
            document = draft.document if isinstance(draft.document, dict) else {}
            section = document.get("automationTaskDefinitions")
            if not isinstance(section, list):
                continue
            for candidate in section:
                if not (isinstance(candidate, dict) and isinstance(candidate.get("id"), str)):
                    continue
                if candidate["id"] not in draft_by_id:
                    draft_by_id[candidate["id"]] = draft
                if candidate["id"] in active_ids or candidate["id"] in seen_draft_only:
                    continue
                seen_draft_only.add(candidate["id"])
                draft_only_total += 1
                if len(draft_only) >= draft_capacity:
                    continue
                draft_only.append((draft, candidate))
        projected = self._automation_occurrences.project_definitions(
            active_page,
            configuration=active.summary(),
        )
        items = [
            self._automation_definition_operator_document(
                value,
                principal=principal,
                active=active,
                draft=draft_by_id.get(str(value.get("id", ""))),
            )
            for value in projected
        ]
        # Newly created or copied definitions live only inside an open Draft
        # until activation; listing them as draft-only keeps the create/copy
        # journey reachable without presenting a Draft as Active.
        for draft, candidate in draft_only:
            items.append(
                self._automation_definition_operator_document(
                    self._automation_occurrences.project_definition(
                        candidate,
                        configuration=active.summary(),
                    ),
                    principal=principal,
                    active=active,
                    draft=draft,
                    in_active=False,
                )
            )
        manage = ApiPermission.MANAGE_CONFIGURATION in principal.permissions
        return self._response(
            start_response,
            200,
            {
                "activeConfiguration": self._automation_active_configuration(active),
                "items": items,
                "total": len(all_items) + draft_only_total,
                "truncated": (
                    len(all_items) > len(active_page) or draft_only_total > len(draft_only)
                ),
                "draftState": self._automation_draft_state(
                    drafts[0] if drafts else None,
                    empty_reason=(
                        "no open successor Draft exists; create one to add or edit definitions"
                    ),
                ),
                "resourceLibraryOptions": self._automation_resource_library_options(
                    detail["objects"]
                ),
                "actions": {
                    "create": {
                        "available": manage,
                        "reason": self._organize_unavailable_reason(
                            manage,
                            ApiPermission.MANAGE_CONFIGURATION,
                            "the connected API principal cannot create Automation Task Definitions",
                        ),
                        "method": "POST",
                        "path": "/api/v1/automation/task-definitions",
                        "sideEffects": "none",
                        "durableOutcome": (
                            "the bounded definition is stored inside the open successor Draft"
                        ),
                        "nextAction": (
                            "start or open a successor Draft, then create the definition inside it"
                        ),
                    },
                    "createDraft": {
                        "available": manage,
                        "reason": self._organize_unavailable_reason(
                            manage,
                            ApiPermission.MANAGE_CONFIGURATION,
                            "the connected API principal cannot create a successor Draft",
                        ),
                        "method": "POST",
                        "path": (f"/api/v1/configuration/revisions/{active.revision_id}/successor"),
                        "sideEffects": "none",
                        "durableOutcome": (
                            "a successor Draft seeded from the immutable Active "
                            "configuration is stored"
                        ),
                        "nextAction": (
                            "create or open the successor Draft, then add or edit "
                            "definitions inside it"
                        ),
                    },
                },
            },
        )

    def _automation_definition_operator_detail(
        self, definition_id: str, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        resolution = self._automation_definition_resolution(definition_id, start_response)
        if not isinstance(resolution, tuple):
            return resolution
        active, raw, definition, draft, in_active = resolution
        projected = self._automation_occurrences.project_definition(
            raw,
            configuration=active.summary(),
        )
        eligibility = None
        if in_active and definition is not None:
            persisted = self._unattended_grants.get_for_definition(definition.definition_id)
            eligibility = self._automation_grant_eligibility(
                active, definition, principal, persisted=persisted
            )
        return self._response(
            start_response,
            200,
            {
                "definition": self._automation_definition_operator_document(
                    projected,
                    principal=principal,
                    active=active,
                    draft=draft,
                    eligibility=eligibility,
                    in_active=in_active,
                ),
                "activeConfiguration": self._automation_active_configuration(active),
            },
        )

    def _automation_definition_operator_draft(
        self, definition_id: str, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        resolution = self._automation_definition_resolution(definition_id, start_response)
        if not isinstance(resolution, tuple):
            return resolution
        active, _raw, _definition, draft, _in_active = resolution
        draft_definition = None
        if draft is not None:
            section = (
                draft.document.get("automationTaskDefinitions", [])
                if isinstance(draft.document, dict)
                else []
            )
            draft_definition = next(
                (
                    item
                    for item in section
                    if isinstance(item, dict) and item.get("id") == definition_id
                ),
                None,
            )
        # Edits are stored inside the open Draft, so the authoritative form
        # options come from that exact Draft document when one is open.
        if draft is not None and isinstance(draft.document, dict):
            options_source = {"resourceLibraries": draft.document.get("resourceLibraries")}
        elif active is not None:
            options_source = self._configuration_objects.revision_detail(active.revision_id)[
                "objects"
            ]
        else:
            options_source = {}
        permissions = principal.permissions
        manage = ApiPermission.MANAGE_CONFIGURATION in permissions
        activate_permitted = ApiPermission.ACTIVATE_CONFIGURATION in permissions
        draft_revision_id = draft.revision_id if draft is not None else None
        return self._response(
            start_response,
            200,
            {
                "definitionId": definition_id,
                "activeConfiguration": self._automation_active_configuration(active),
                "draft": (
                    None
                    if draft is None or draft_definition is None
                    else {
                        "revisionId": draft.revision_id,
                        "revisionVersion": draft.version,
                        "revisionStatus": draft.status.value,
                        "baseActiveRevisionId": draft.base_active_revision_id,
                        "updatedAt": draft.updated_at.isoformat(),
                        "validatedAt": (
                            draft.validated_at.isoformat() if draft.validated_at else None
                        ),
                        "validationErrors": list(draft.validation_errors),
                        "definition": self._strip_automation_operator_evidence(draft_definition),
                    }
                ),
                "resourceLibraryOptions": self._automation_resource_library_options(options_source),
                "actions": {
                    "createDraft": {
                        "available": manage,
                        "reason": self._organize_unavailable_reason(
                            manage,
                            ApiPermission.MANAGE_CONFIGURATION,
                            "the connected API principal cannot create a successor Draft",
                        ),
                        "method": "POST",
                        "path": (f"/api/v1/configuration/revisions/{active.revision_id}/successor"),
                        "sideEffects": "none",
                        "durableOutcome": (
                            "a successor Draft seeded from the immutable Active "
                            "configuration is stored"
                        ),
                        "nextAction": (
                            "create the successor Draft, then edit this definition inside it"
                        ),
                    },
                    "save": {
                        "available": manage and draft is not None,
                        "reason": (
                            self._organize_unavailable_reason(
                                manage,
                                ApiPermission.MANAGE_CONFIGURATION,
                                "the connected API principal cannot edit Automation "
                                "Task Definitions",
                            )
                            if not manage
                            else (
                                None
                                if draft is not None
                                else "an open successor Draft is required to edit this definition"
                            )
                        ),
                        "method": "PUT",
                        "path": (
                            f"/api/v1/configuration/revisions/{draft_revision_id}/objects/"
                            f"automationTaskDefinitions/{definition_id}"
                            if draft_revision_id is not None
                            else None
                        ),
                        "sideEffects": "none",
                        "durableOutcome": (
                            "the bounded definition form is stored in the open successor "
                            "Draft at a new optimistic revision version"
                        ),
                        "nextAction": (
                            "save the bounded form, then validate and explicitly activate"
                        ),
                    },
                    "validate": {
                        "available": manage and draft is not None,
                        "reason": (
                            self._organize_unavailable_reason(
                                manage,
                                ApiPermission.MANAGE_CONFIGURATION,
                                "the connected API principal cannot validate configuration",
                            )
                            if not manage
                            else (
                                None
                                if draft is not None
                                else "an open successor Draft is required before validation"
                            )
                        ),
                        "method": "POST",
                        "path": (
                            f"/api/v1/configuration/revisions/{draft_revision_id}/validate"
                            if draft_revision_id is not None
                            else None
                        ),
                        "sideEffects": "none",
                        "durableOutcome": (
                            "the open Draft is validated without any runtime or Storage effect"
                        ),
                        "nextAction": "validate the Draft, then review the validation evidence",
                    },
                    "activate": {
                        "available": activate_permitted and draft is not None,
                        "reason": (
                            self._organize_unavailable_reason(
                                activate_permitted,
                                ApiPermission.ACTIVATE_CONFIGURATION,
                                "the connected API principal cannot activate configuration",
                            )
                            if not activate_permitted
                            else (
                                None
                                if draft is not None
                                else "an open successor Draft is required before activation"
                            )
                        ),
                        "method": "POST",
                        "path": (
                            f"/api/v1/operations/automation/task-definitions/{definition_id}"
                            "/activate-draft"
                            if draft_revision_id is not None
                            else None
                        ),
                        "requiresConfirmation": True,
                        "sideEffects": "none",
                        "durableOutcome": (
                            "the exact Draft becomes the immutable Active configuration after "
                            "the exact-revision binding and Automation-only boundary checks; "
                            "no Scan, Job, Task or occurrence is started"
                        ),
                        "nextAction": ("confirm one explicit activation of the validated Draft"),
                    },
                },
            },
        )

    def _automation_definition_operator_occurrences(
        self,
        definition_id: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ) -> None:
        resolution = self._automation_definition_resolution(definition_id, start_response)
        if not isinstance(resolution, tuple):
            return resolution
        active, _raw, _definition, _draft, _in_active = resolution
        limit, cursor = self._scoped_page_query(
            environ,
            "automation_definition_occurrences",
            definition_id,
            "automation occurrence",
        )
        values = self._list_page(
            lambda **kwargs: self._automation_occurrences.list(definition_id, **kwargs),
            limit,
            cursor,
        )
        page, has_previous, has_next = self._page_window(values, limit, cursor)
        return self._response(
            start_response,
            200,
            {
                "definitionId": definition_id,
                "activeConfiguration": self._automation_active_configuration(active),
                "items": [
                    self._automation_occurrence_operator_document(item)
                    for item in self._automation_occurrences.project_occurrences(page)
                ],
                "limit": limit,
                "truncated": has_next,
                "previous_cursor": self._page_cursor(
                    "automation_definition_occurrences",
                    page,
                    has_previous,
                    CursorDirection.PREVIOUS,
                    scope=definition_id,
                ),
                "next_cursor": self._page_cursor(
                    "automation_definition_occurrences",
                    page,
                    has_next,
                    CursorDirection.NEXT,
                    scope=definition_id,
                ),
            },
        )

    def _automation_definition_operator_preview(
        self,
        definition_id: str,
        preview_id: str,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ) -> None:
        if self._automation_previews is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "automation Preview service is unavailable",
            )
        preview = self._automation_previews.get_readonly(preview_id)
        if preview.definition_id != definition_id:
            raise LookupError(
                f"automation Preview {preview_id!r} does not belong to definition {definition_id!r}"
            )
        eligibility = None
        if self._configuration_service is not None and self._configuration_objects is not None:
            active, _raw, definition = self._automation_definition_context(
                environ={}, definition_id=definition_id
            )
            persisted = self._unattended_grants.get_for_definition(definition.definition_id)
            eligibility = self._automation_grant_eligibility(
                active, definition, principal, persisted=persisted
            )
        return self._response(
            start_response,
            200,
            self._automation_preview_operator_document(
                preview, principal=principal, eligibility=eligibility
            ),
        )

    def _automation_definition_activate_checked_draft(
        self,
        definition_id: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ) -> None:
        """Checked-activate the exact open successor Draft that owns this definition.

        The browser supplies the Draft's exact advertised revision identity and
        optimistic version — never a digest. The action is bound to that exact
        Draft revision, the Active base is pinned, and the Draft's changes are
        compared with the Active document so a revision that touches anything
        outside the Automation Task Definition boundary is rejected before any
        activation, and so the section changes only at the reviewed
        definition's exact identity — a sibling definition can never be added,
        removed or modified while riding along. Because the confinement
        comparison proves every other section and every other definition is
        byte-identical to the live Active configuration, the published
        configuration carries no new Storage, strategy or destination
        semantics. No Scan, Job, Task or occurrence is started by activation,
        and a Draft-only definition (newly created or copied) is activatable
        exactly like an edited Active definition.
        """

        if self._configuration_service is None or self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
        self._require_empty_query(environ, "operations automation draft activation")
        document = self._document(environ)
        if set(document) != {"expectedRevisionId", "expectedVersion"}:
            raise ValueError(
                "automation draft activation requires expectedRevisionId and expectedVersion only"
            )
        expected_revision_id = document["expectedRevisionId"]
        if not isinstance(expected_revision_id, str) or not expected_revision_id.strip():
            raise ValueError(
                "automation draft activation expectedRevisionId must be a non-empty string"
            )
        expected = document["expectedVersion"]
        if isinstance(expected, bool) or not isinstance(expected, int):
            raise ValueError("automation draft activation expectedVersion must be an integer")
        active = self._configuration_service.active()
        try:
            draft = self._configuration_service.latest_open_draft_containing(
                "automationTaskDefinitions", definition_id
            )
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        if active is None:
            raise UnattendedExecutionGrantError(
                "no Active configuration exists; managed configuration setup owns the first Draft",
                code="automation_active_missing",
                status=409,
                durable_state="no configuration was activated",
                next_action="complete managed configuration setup, then stage a successor Draft",
            )
        if draft is None:
            raise UnattendedExecutionGrantError(
                "no open successor Draft contains this definition",
                code="automation_draft_required",
                status=409,
                durable_state="active configuration preserved",
                next_action="create a successor Draft, edit the definition, then activate",
            )
        if draft.revision_id != expected_revision_id:
            raise ConfigurationVersionConflict(
                "the submitted Draft identity does not match the current open successor "
                "Draft; reload the Draft",
                revision_id=draft.revision_id,
                current_version=draft.version,
                durable_state="draft_preserved",
                next_action="reload the Draft document, then activate the exact advertised "
                "Draft revision again",
            )
        if draft.version != expected:
            raise ConfigurationVersionConflict(
                "the successor Draft changed before activation; reload the Draft",
                revision_id=draft.revision_id,
                current_version=draft.version,
                durable_state="draft_preserved",
                next_action="reload the Draft, then activate the current version again",
            )
        if draft.base_active_revision_id != active.revision_id:
            raise ConfigurationVersionConflict(
                "the Active configuration changed after this Draft was created; "
                "stage a fresh successor Draft",
                revision_id=draft.revision_id,
                current_version=draft.version,
                durable_state="draft_preserved",
                next_action="create a fresh successor Draft from the current Active "
                "configuration, then edit, validate and activate it",
            )
        changed = self._automation_draft_changed_sections(draft.document, active.document)
        if changed - {"automationTaskDefinitions"}:
            raise UnattendedExecutionGrantError(
                "this Draft changes configuration outside the Automation Task Definition boundary",
                code="automation_activation_out_of_scope",
                status=409,
                durable_state="active configuration preserved",
                next_action=(
                    "remove the unrelated configuration changes from the Draft, or use the "
                    "managed configuration activation journey with explicit review"
                ),
            )
        self._require_automation_definition_only_change(
            active.document, draft.document, definition_id
        )
        # The exact-revision binding, Active-base pin and Automation-only
        # confinement above prove every non-Automation section and every other
        # Automation definition is byte-identical to the live Active
        # configuration, so no new Storage, strategy or destination semantics
        # are published by this activation. The managed activation revalidates
        # the exact revision digest, optimistic version and document loader
        # atomically before publishing.
        activated = self._configuration_service.activate(
            draft.revision_id,
            expected_version=draft.version,
            actor=principal.principal_id,
        )
        self._refresh_configuration_binding()
        active_after = self._configuration_service.active()
        definition_after = next(
            (
                item
                for item in activated.document.get("automationTaskDefinitions", [])
                if isinstance(item, dict) and item.get("id") == definition_id
            ),
            None,
        )
        return self._response(
            start_response,
            200,
            {
                "activatedRevisionId": activated.revision_id,
                "activatedVersion": activated.version,
                "revisionSequence": activated.revision_sequence,
                "activeConfiguration": self._automation_active_configuration(active_after),
                "definition": (
                    self._strip_automation_operator_evidence(definition_after)
                    if definition_after is not None
                    else None
                ),
            },
        )

    def _require_automation_definition_only_change(
        self,
        active_document: object,
        draft_document: object,
        definition_id: str,
    ) -> None:
        """Fail closed unless the Draft's only Automation change is this definition.

        The section-level confinement proves no other configuration section
        changed; this comparison proves the ``automationTaskDefinitions``
        section changed only at the reviewed definition's exact identity. Every
        other definition must be present in both documents and byte-identical,
        so a sibling definition cannot be added, removed or modified while
        riding along with the reviewed activation — including the create/copy
        case, where the new or copied definition must be the sole Automation
        change. Malformed sections fail closed: an unverifiable boundary is
        never activated.
        """

        active_definitions = self._automation_definition_identity_map(active_document)
        draft_definitions = self._automation_definition_identity_map(draft_document)
        if active_definitions is None or draft_definitions is None:
            raise UnattendedExecutionGrantError(
                "the Automation Task Definition section is malformed; activation "
                "cannot verify its exact boundary",
                code="automation_activation_out_of_scope",
                status=409,
                durable_state="active configuration preserved",
                next_action=(
                    "create a fresh successor Draft from the current Active "
                    "configuration, then edit, validate and activate it"
                ),
            )
        unexpected = sorted(
            candidate_id
            for candidate_id in set(active_definitions) | set(draft_definitions)
            if candidate_id != definition_id
            and (
                candidate_id not in active_definitions
                or candidate_id not in draft_definitions
                or draft_definitions[candidate_id] != active_definitions[candidate_id]
            )
        )
        if unexpected:
            raise UnattendedExecutionGrantError(
                "this Draft changes other Automation Task Definitions beyond the "
                "reviewed definition",
                code="automation_activation_definition_scope",
                status=409,
                durable_state="active configuration preserved",
                next_action=(
                    "remove the other definition changes from this Draft, then edit, "
                    "validate and activate one definition per Draft"
                ),
            )

    @staticmethod
    def _automation_definition_identity_map(document: object) -> dict[str, object] | None:
        """Definition id → entry map for the automationTaskDefinitions section.

        Returns ``None`` when the section is missing or any entry is malformed
        (not an object, a non-string id, or a duplicated id), so the caller can
        fail closed instead of activating an unverifiable boundary.
        """

        if not isinstance(document, dict):
            return None
        section = document.get("automationTaskDefinitions")
        if not isinstance(section, list):
            return None
        definitions: dict[str, object] = {}
        for entry in section:
            if not (isinstance(entry, dict) and isinstance(entry.get("id"), str)):
                return None
            entry_id = entry["id"]
            if entry_id in definitions:
                return None
            definitions[entry_id] = entry
        return definitions

    @staticmethod
    def _automation_draft_changed_sections(
        draft_document: object, active_document: object
    ) -> set[str]:
        """Top-level configuration sections the Draft changes versus Active.

        A successor Draft is seeded as an exact copy of the Active document,
        so any differing top-level section is a Draft change. Comparing whole
        sections keeps the boundary exact without interpreting nested object
        semantics.
        """

        draft = draft_document if isinstance(draft_document, dict) else {}
        base = active_document if isinstance(active_document, dict) else {}
        return {
            key
            for key in set(draft) | set(base)
            if key not in draft or key not in base or draft[key] != base[key]
        }

    def _automation_definition_operator_preview_items(
        self,
        definition_id: str,
        preview_id: str,
        environ: dict,
        start_response: Callable,
    ) -> None:
        if self._automation_previews is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "automation Preview service is unavailable",
            )
        preview = self._automation_previews.get_readonly(preview_id)
        if preview.definition_id != definition_id:
            raise LookupError(
                f"automation Preview {preview_id!r} does not belong to definition {definition_id!r}"
            )
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(query).difference({"limit", "after"}) or any(
            len(value) != 1 for value in query.values()
        ):
            raise ValueError("automation Preview item query accepts limit and after once")
        try:
            limit = int(query.get("limit", ["100"])[0])
        except ValueError as error:
            raise ValueError("automation Preview item limit must be an integer") from error
        if limit < 1 or limit > 500:
            raise ValueError("automation Preview item limit must be between 1 and 500")
        after_value = query.get("after", [None])[0]
        if after_value is not None:
            try:
                after = int(after_value)
            except ValueError as error:
                raise ValueError("automation Preview item cursor must be an integer") from error
        else:
            after = None
        items, total, next_after = self._automation_previews.items(
            preview_id, limit=limit, after=after
        )
        return self._response(
            start_response,
            200,
            {
                "previewId": preview_id,
                "items": [
                    self._strip_automation_operator_evidence(
                        item.document(), drop_definition_version=True
                    )
                    for item in items
                ],
                "total": total,
                "nextAfter": next_after,
            },
        )

    # ------------------------------------------------------------------
    # V2 Notification operations projections (bounded, digest-free)

    def _notification_operations_projection(
        self,
        parts: list[str],
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """Dispatch the bounded V2 Notification operator projections.

        The read documents are the exact, digest-free Webhook evidence the Web
        journey consumes; the raw managed-configuration documents stay on the
        existing /api/v1/configuration surfaces. The two mutations here are
        the digest-free exact-revision Webhook test and the Webhook-object-
        scoped checked activation: the browser submits only the advertised
        revision identity and optimistic version, while the configuration
        digest and the resolved secret remain server-side. Delivery reads
        compose the existing NotificationDeliveryService authority and add
        only permission-aware recovery action metadata.
        """

        if parts[4] == "deliveries":
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            if len(parts) != 6:
                return self._error(start_response, 404, "not_found", "route was not found")
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "operations notification delivery detail")
            return self._notification_delivery_operator_detail(parts[5], start_response, principal)
        if parts[4] != "webhooks" or len(parts) > 7:
            return self._error(start_response, 404, "not_found", "route was not found")
        if len(parts) == 7 and method == "POST" and parts[6] == "test":
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            return self._notification_webhook_operator_test(
                parts[5], environ, start_response, principal
            )
        if len(parts) == 7 and method == "POST" and parts[6] == "activate-draft":
            return self._notification_webhook_activate_checked_draft(
                parts[5], environ, start_response, principal
            )
        if method != "GET":
            return self._error(start_response, 405, "method_not_allowed", "GET required")
        self._require(principal, ApiPermission.READ)
        if self._configuration_service is None or self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        if len(parts) == 5:
            self._require_empty_query(environ, "operations notification definitions")
            return self._notification_webhooks_operator_page(environ, start_response, principal)
        if len(parts) == 6:
            self._require_empty_query(environ, "operations notification definition")
            return self._notification_webhook_operator_detail(parts[5], start_response, principal)
        if len(parts) == 7 and parts[6] == "draft":
            self._require_empty_query(environ, "operations notification definition draft")
            return self._notification_webhook_operator_draft(parts[5], start_response, principal)
        return self._error(start_response, 404, "not_found", "route was not found")

    def _notification_webhook_resolution(self, webhook_id: str, start_response: Callable):
        """Resolve a Webhook definition from the Active revision, then the open Draft.

        Returns ``(active, draft, raw, in_active)`` where ``raw`` is the
        bounded projected definition (secret-readiness metadata, redacted
        endpoint) from the exact revision that contains it. Newly created or
        copied definitions exist only inside an open successor Draft until
        activation, so Draft-only resolution keeps them reachable and editable
        without presenting them as Active. Returns the bounded 503 response
        when the configuration or Draft read fails (callers must return it
        unchanged); a definition found in neither source raises ``LookupError``
        exactly as the Automation resolution does.
        """

        if self._configuration_service is None or self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        try:
            active = self._configuration_service.active()
            draft = self._configuration_service.latest_open_draft_containing("webhooks", webhook_id)
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        raw = None
        in_active = False
        if active is not None:
            projected = self._configuration_objects.revision_detail(active.revision_id)[
                "objects"
            ].get("webhooks", [])
            raw = next(
                (
                    item
                    for item in projected
                    if isinstance(item, dict) and item.get("id") == webhook_id
                ),
                None,
            )
            in_active = raw is not None
        if raw is None and draft is not None:
            projected = self._configuration_objects.revision_detail(draft.revision_id)[
                "objects"
            ].get("webhooks", [])
            raw = next(
                (
                    item
                    for item in projected
                    if isinstance(item, dict) and item.get("id") == webhook_id
                ),
                None,
            )
        if raw is None:
            raise LookupError(f"webhooks {webhook_id!r} was not found")
        return active, draft, raw, in_active

    def _notification_webhook_actions(
        self,
        webhook_id: str,
        principal: ResolvedApiPrincipal,
        *,
        active,
        draft,
    ) -> dict:
        """Backend-authoritative action metadata for one Webhook document.

        Draft-bound definition mutations compose the existing managed
        configuration object routes; the test and checked activation are the
        bounded operations transports owned by this projection. A Draft-only
        definition is editable and activatable exactly like an edited Active
        definition, but it is never presented as runtime truth.
        """

        permissions = principal.permissions
        manage = ApiPermission.MANAGE_CONFIGURATION in permissions
        activate_permitted = ApiPermission.ACTIVATE_CONFIGURATION in permissions
        active_revision_id = active.revision_id if active is not None else None
        draft_revision_id = draft.revision_id if draft is not None else None
        no_draft_reason = "an open successor Draft is required to edit this Webhook definition"
        manage_reason = "the connected API principal cannot manage Webhook Definitions"
        return {
            "detail": {
                "available": True,
                "reason": None,
                "method": "GET",
                "path": f"/api/v1/operations/notifications/webhooks/{webhook_id}",
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": "inspect the exact bounded Webhook definition state",
            },
            "test": {
                "available": manage,
                "reason": self._organize_unavailable_reason(
                    manage,
                    ApiPermission.MANAGE_CONFIGURATION,
                    manage_reason,
                ),
                "method": "POST",
                "path": f"/api/v1/operations/notifications/webhooks/{webhook_id}/test",
                "sideEffects": "one_signed_test_request",
                "durableOutcome": (
                    "no durable change; only the bounded test outcome category is returned"
                ),
                "nextAction": (
                    "test the exact displayed revision after reviewing its endpoint and "
                    "secret readiness"
                ),
            },
            "edit": {
                "available": manage and draft is not None,
                "reason": (
                    self._organize_unavailable_reason(
                        manage,
                        ApiPermission.MANAGE_CONFIGURATION,
                        manage_reason,
                    )
                    if not manage
                    else (None if draft is not None else no_draft_reason)
                ),
                "method": "PUT",
                "path": (
                    f"/api/v1/configuration/revisions/{draft_revision_id}/objects/"
                    f"webhooks/{webhook_id}"
                    if draft_revision_id is not None
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": (
                    "the bounded definition form is stored in the open successor Draft at "
                    "a new optimistic revision version"
                ),
                "nextAction": "save the bounded form, then validate and explicitly activate",
            },
            "copy": {
                "available": manage and draft is not None,
                "reason": (
                    self._organize_unavailable_reason(
                        manage,
                        ApiPermission.MANAGE_CONFIGURATION,
                        manage_reason,
                    )
                    if not manage
                    else (None if draft is not None else no_draft_reason)
                ),
                "method": "POST",
                "path": (
                    f"/api/v1/configuration/revisions/{draft_revision_id}/objects/"
                    f"webhooks/{webhook_id}/copy"
                    if draft_revision_id is not None
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": (
                    "a copied, disabled Webhook definition is stored inside the open "
                    "successor Draft"
                ),
                "nextAction": "open the copied definition, edit it, then validate and activate",
            },
            "enable": {
                "available": manage and draft is not None,
                "reason": (
                    self._organize_unavailable_reason(
                        manage,
                        ApiPermission.MANAGE_CONFIGURATION,
                        manage_reason,
                    )
                    if not manage
                    else (None if draft is not None else no_draft_reason)
                ),
                "method": "POST",
                "path": (
                    f"/api/v1/configuration/revisions/{draft_revision_id}/objects/"
                    f"webhooks/{webhook_id}/enable"
                    if draft_revision_id is not None
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": (
                    "the definition is enabled inside the open successor Draft only"
                ),
                "nextAction": "review the Draft, validate it, then explicitly activate",
            },
            "disable": {
                "available": manage and draft is not None,
                "reason": (
                    self._organize_unavailable_reason(
                        manage,
                        ApiPermission.MANAGE_CONFIGURATION,
                        manage_reason,
                    )
                    if not manage
                    else (None if draft is not None else no_draft_reason)
                ),
                "method": "POST",
                "path": (
                    f"/api/v1/configuration/revisions/{draft_revision_id}/objects/"
                    f"webhooks/{webhook_id}/disable"
                    if draft_revision_id is not None
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": (
                    "the definition is disabled inside the open successor Draft only"
                ),
                "nextAction": "review the Draft, validate it, then explicitly activate",
            },
            "draftCreate": {
                "available": manage and active is not None,
                "reason": (
                    self._organize_unavailable_reason(
                        manage,
                        ApiPermission.MANAGE_CONFIGURATION,
                        manage_reason,
                    )
                    if not manage
                    else (
                        None
                        if active is not None
                        else "no Active configuration exists; managed "
                        "configuration setup owns the first Draft"
                    )
                ),
                "method": "POST",
                "path": (
                    f"/api/v1/configuration/revisions/{active_revision_id}/successor"
                    if active_revision_id is not None
                    else None
                ),
                "sideEffects": "none",
                "durableOutcome": (
                    "a successor Draft seeded from the immutable Active configuration is stored"
                ),
                "nextAction": (
                    "create or open the successor Draft, then add or edit Webhook "
                    "definitions inside it"
                ),
            },
            "activate": {
                "available": activate_permitted and draft is not None,
                "reason": (
                    self._organize_unavailable_reason(
                        activate_permitted,
                        ApiPermission.ACTIVATE_CONFIGURATION,
                        "the connected API principal cannot activate configuration",
                    )
                    if not activate_permitted
                    else (None if draft is not None else no_draft_reason)
                ),
                "method": "POST",
                "path": (
                    f"/api/v1/operations/notifications/webhooks/{webhook_id}/activate-draft"
                    if draft_revision_id is not None
                    else None
                ),
                "requiresConfirmation": True,
                "sideEffects": "none",
                "durableOutcome": (
                    "the exact reviewed Webhook-only Draft change becomes the immutable "
                    "Active configuration; no delivery is created"
                ),
                "nextAction": (
                    "activate the reviewed Draft after validating it; the resulting Active "
                    "identity is reported without a digest"
                ),
            },
        }

    def _notification_webhook_operator_document(
        self,
        raw: dict,
        *,
        principal: ResolvedApiPrincipal,
        active,
        draft,
        in_active: bool = True,
    ) -> dict:
        """Bounded, digest-free V2 operator projection for one Webhook definition."""

        webhook_id = str(raw.get("id", ""))
        operator = dict(raw)
        operator["definitionState"] = "active" if in_active else "draft-only"
        operator["activeConfiguration"] = self._automation_active_configuration(active)
        operator["draftState"] = self._automation_draft_state(
            draft,
            empty_reason=(
                "no open successor Draft contains this Webhook definition; create one to edit it"
            ),
        )
        operator["actions"] = self._notification_webhook_actions(
            webhook_id, principal, active=active, draft=draft
        )
        return operator

    def _notification_webhooks_operator_page(
        self, environ: dict, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        active = self._configuration_service.active()
        if active is None:
            manage = ApiPermission.MANAGE_CONFIGURATION in principal.permissions
            return self._response(
                start_response,
                200,
                {
                    "activeConfiguration": None,
                    "items": [],
                    "total": 0,
                    "truncated": False,
                    "draftState": self._automation_draft_state(
                        None,
                        empty_reason=(
                            "no Active configuration exists; managed configuration "
                            "setup owns the first Draft"
                        ),
                    ),
                    "supportedEvents": list(webhook_events_supported()),
                    "actions": {
                        "create": {
                            "available": False,
                            "reason": (
                                self._organize_unavailable_reason(
                                    manage,
                                    ApiPermission.MANAGE_CONFIGURATION,
                                    "the connected API principal cannot create Webhook Definitions",
                                )
                                if not manage
                                else "no Active configuration exists; managed "
                                "configuration setup owns the first Draft"
                            ),
                            "method": "POST",
                            "path": None,
                            "sideEffects": "none",
                            "durableOutcome": (
                                "the bounded Webhook definition is stored inside the open "
                                "successor Draft"
                            ),
                            "nextAction": (
                                "complete managed configuration setup, then create Webhook "
                                "definitions inside a successor Draft"
                            ),
                        },
                        "createDraft": {
                            "available": False,
                            "reason": (
                                self._organize_unavailable_reason(
                                    manage,
                                    ApiPermission.MANAGE_CONFIGURATION,
                                    "the connected API principal cannot create a successor Draft",
                                )
                                if not manage
                                else "no Active configuration exists; managed "
                                "configuration setup owns the first Draft"
                            ),
                            "method": "POST",
                            "path": None,
                            "sideEffects": "none",
                            "durableOutcome": (
                                "a successor Draft seeded from the immutable Active "
                                "configuration is stored"
                            ),
                            "nextAction": (
                                "complete managed configuration setup before staging "
                                "a successor Draft"
                            ),
                        },
                    },
                },
            )
        detail = self._configuration_objects.revision_detail(active.revision_id)
        all_items = detail["objects"].get("webhooks", [])
        try:
            drafts = self._configuration_service.open_draft_revisions()
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        active_ids = {
            str(candidate.get("id"))
            for candidate in all_items
            if isinstance(candidate, dict) and isinstance(candidate.get("id"), str)
        }
        draft_by_id: dict[str, object] = {}
        draft_only: list[tuple[object, dict]] = []
        seen_draft_only: set[str] = set()
        draft_only_total = 0
        # One deterministic combined page limit for Active and Draft-only
        # definitions: the Active document order fills the page first and
        # draft-only definitions take the remaining capacity. The frontend
        # normalizer fails closed on any page above this limit, so the merged
        # response must never exceed it; dropped definitions stay counted in
        # the truthful total and the truncated flag.
        active_page = all_items[: self.NOTIFICATION_DEFINITIONS_PAGE_LIMIT]
        draft_capacity = self.NOTIFICATION_DEFINITIONS_PAGE_LIMIT - len(active_page)
        for draft in drafts:
            for candidate in ConfigurationObjectService._webhooks_projection(draft.document):
                if not (isinstance(candidate, dict) and isinstance(candidate.get("id"), str)):
                    continue
                if candidate["id"] not in draft_by_id:
                    draft_by_id[candidate["id"]] = draft
                if candidate["id"] in active_ids or candidate["id"] in seen_draft_only:
                    continue
                seen_draft_only.add(candidate["id"])
                draft_only_total += 1
                if len(draft_only) >= draft_capacity:
                    continue
                draft_only.append((draft, candidate))
        items = [
            self._notification_webhook_operator_document(
                value,
                principal=principal,
                active=active,
                draft=draft_by_id.get(str(value.get("id", ""))),
            )
            for value in active_page
            if isinstance(value, dict)
        ]
        # Newly created or copied definitions live only inside an open Draft
        # until activation; listing them as draft-only keeps the create/copy
        # journey reachable without presenting a Draft as Active.
        for draft, candidate in draft_only:
            items.append(
                self._notification_webhook_operator_document(
                    candidate,
                    principal=principal,
                    active=active,
                    draft=draft,
                    in_active=False,
                )
            )
        manage = ApiPermission.MANAGE_CONFIGURATION in principal.permissions
        draft_revision_id = drafts[0].revision_id if drafts else None
        return self._response(
            start_response,
            200,
            {
                "activeConfiguration": self._automation_active_configuration(active),
                "items": items,
                "total": len(all_items) + draft_only_total,
                "truncated": (
                    len(all_items) > len(active_page) or draft_only_total > len(draft_only)
                ),
                "draftState": self._automation_draft_state(
                    drafts[0] if drafts else None,
                    empty_reason=(
                        "no open successor Draft exists; create one to add or edit "
                        "Webhook definitions"
                    ),
                ),
                "supportedEvents": list(webhook_events_supported()),
                "actions": {
                    "create": {
                        "available": manage and draft_revision_id is not None,
                        "reason": (
                            self._organize_unavailable_reason(
                                manage,
                                ApiPermission.MANAGE_CONFIGURATION,
                                "the connected API principal cannot create Webhook Definitions",
                            )
                            if not manage
                            else (
                                None
                                if draft_revision_id is not None
                                else "an open successor Draft is required to add a "
                                "Webhook definition"
                            )
                        ),
                        "method": "POST",
                        "path": (
                            f"/api/v1/configuration/revisions/{draft_revision_id}/objects/webhooks"
                            if draft_revision_id is not None
                            else None
                        ),
                        "sideEffects": "none",
                        "durableOutcome": (
                            "the bounded Webhook definition is stored inside the open "
                            "successor Draft"
                        ),
                        "nextAction": (
                            "start or open a successor Draft, then create the definition inside it"
                        ),
                    },
                    "createDraft": {
                        "available": manage,
                        "reason": self._organize_unavailable_reason(
                            manage,
                            ApiPermission.MANAGE_CONFIGURATION,
                            "the connected API principal cannot create a successor Draft",
                        ),
                        "method": "POST",
                        "path": f"/api/v1/configuration/revisions/{active.revision_id}/successor",
                        "sideEffects": "none",
                        "durableOutcome": (
                            "a successor Draft seeded from the immutable Active "
                            "configuration is stored"
                        ),
                        "nextAction": (
                            "create or open the successor Draft, then add or edit "
                            "Webhook definitions inside it"
                        ),
                    },
                },
            },
        )

    def _notification_webhook_operator_detail(
        self, webhook_id: str, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        resolution = self._notification_webhook_resolution(webhook_id, start_response)
        if not isinstance(resolution, tuple):
            return resolution
        active, draft, raw, in_active = resolution
        return self._response(
            start_response,
            200,
            {
                "webhook": self._notification_webhook_operator_document(
                    raw,
                    principal=principal,
                    active=active,
                    draft=draft,
                    in_active=in_active,
                ),
                "activeConfiguration": self._automation_active_configuration(active),
            },
        )

    def _notification_webhook_operator_draft(
        self, webhook_id: str, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        resolution = self._notification_webhook_resolution(webhook_id, start_response)
        if not isinstance(resolution, tuple):
            return resolution
        active, draft, raw, in_active = resolution
        draft_webhook = None
        if draft is not None:
            projected = ConfigurationObjectService._webhooks_projection(draft.document)
            draft_webhook = next(
                (
                    item
                    for item in projected
                    if isinstance(item, dict) and item.get("id") == webhook_id
                ),
                None,
            )
        permissions = principal.permissions
        manage = ApiPermission.MANAGE_CONFIGURATION in permissions
        activate_permitted = ApiPermission.ACTIVATE_CONFIGURATION in permissions
        draft_revision_id = draft.revision_id if draft is not None else None
        active_revision_id = active.revision_id if active is not None else None
        no_draft_reason = "an open successor Draft is required to edit this Webhook definition"
        manage_reason = "the connected API principal cannot manage Webhook Definitions"
        return self._response(
            start_response,
            200,
            {
                "webhookId": webhook_id,
                "activeConfiguration": self._automation_active_configuration(active),
                "webhook": raw if in_active else None,
                "draft": (
                    None
                    if draft is None or draft_webhook is None
                    else {
                        "revisionId": draft.revision_id,
                        "revisionVersion": draft.version,
                        "revisionStatus": draft.status.value,
                        "baseActiveRevisionId": draft.base_active_revision_id,
                        "updatedAt": draft.updated_at.isoformat(),
                        "validatedAt": (
                            draft.validated_at.isoformat() if draft.validated_at else None
                        ),
                        "validationErrors": list(draft.validation_errors),
                        "webhook": draft_webhook,
                    }
                ),
                "supportedEvents": list(webhook_events_supported()),
                "actions": {
                    "createDraft": {
                        "available": manage and active is not None,
                        "reason": (
                            self._organize_unavailable_reason(
                                manage,
                                ApiPermission.MANAGE_CONFIGURATION,
                                manage_reason,
                            )
                            if not manage
                            else (
                                None
                                if active is not None
                                else "no Active configuration exists; managed "
                                "configuration setup owns the first Draft"
                            )
                        ),
                        "method": "POST",
                        "path": (
                            f"/api/v1/configuration/revisions/{active_revision_id}/successor"
                            if active_revision_id is not None
                            else None
                        ),
                        "sideEffects": "none",
                        "durableOutcome": (
                            "a successor Draft seeded from the immutable Active "
                            "configuration is stored"
                        ),
                        "nextAction": (
                            "create the successor Draft, then edit this Webhook definition "
                            "inside it"
                        ),
                    },
                    "save": {
                        "available": manage and draft is not None,
                        "reason": (
                            self._organize_unavailable_reason(
                                manage,
                                ApiPermission.MANAGE_CONFIGURATION,
                                manage_reason,
                            )
                            if not manage
                            else (None if draft is not None else no_draft_reason)
                        ),
                        "method": "PUT",
                        "path": (
                            f"/api/v1/configuration/revisions/{draft_revision_id}/objects/"
                            f"webhooks/{webhook_id}"
                            if draft_revision_id is not None
                            else None
                        ),
                        "sideEffects": "none",
                        "durableOutcome": (
                            "the bounded definition form is stored in the open successor "
                            "Draft at a new optimistic revision version"
                        ),
                        "nextAction": (
                            "save the bounded form, then validate and explicitly activate"
                        ),
                    },
                    "validate": {
                        "available": manage and draft is not None,
                        "reason": (
                            self._organize_unavailable_reason(
                                manage,
                                ApiPermission.MANAGE_CONFIGURATION,
                                "the connected API principal cannot validate configuration",
                            )
                            if not manage
                            else (None if draft is not None else no_draft_reason)
                        ),
                        "method": "POST",
                        "path": (
                            f"/api/v1/configuration/revisions/{draft_revision_id}/validate"
                            if draft_revision_id is not None
                            else None
                        ),
                        "sideEffects": "none",
                        "durableOutcome": (
                            "the open Draft is validated without any runtime or Storage effect"
                        ),
                        "nextAction": "validate the Draft, then review the validation evidence",
                    },
                    "activate": {
                        "available": activate_permitted and draft is not None,
                        "reason": (
                            self._organize_unavailable_reason(
                                activate_permitted,
                                ApiPermission.ACTIVATE_CONFIGURATION,
                                "the connected API principal cannot activate configuration",
                            )
                            if not activate_permitted
                            else (None if draft is not None else no_draft_reason)
                        ),
                        "method": "POST",
                        "path": (
                            f"/api/v1/operations/notifications/webhooks/{webhook_id}/activate-draft"
                            if draft_revision_id is not None
                            else None
                        ),
                        "requiresConfirmation": True,
                        "sideEffects": "none",
                        "durableOutcome": (
                            "the exact reviewed Webhook-only Draft change becomes the "
                            "immutable Active configuration; no delivery is created"
                        ),
                        "nextAction": (
                            "activate the reviewed Draft after validating it; the resulting "
                            "Active identity is reported without a digest"
                        ),
                    },
                    "test": {
                        "available": manage,
                        "reason": (
                            self._organize_unavailable_reason(
                                manage,
                                ApiPermission.MANAGE_CONFIGURATION,
                                manage_reason,
                            )
                        ),
                        "method": "POST",
                        "path": f"/api/v1/operations/notifications/webhooks/{webhook_id}/test",
                        "sideEffects": "one_signed_test_request",
                        "durableOutcome": (
                            "no durable change; only the bounded test outcome category is returned"
                        ),
                        "nextAction": (
                            "test the exact displayed revision after reviewing its endpoint "
                            "and secret readiness"
                        ),
                    },
                },
            },
        )

    def _notification_webhook_operator_test(
        self,
        webhook_id: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ) -> None:
        """Run the explicit signed Webhook test bound to one exact revision.

        The browser submits only the advertised revision identity and
        optimistic version. The configuration digest is resolved server-side
        from the exact revision and handed to the existing signed-test
        service, so the browser neither receives nor submits a digest, and
        the resolved secret never leaves the process.
        """

        if self._webhook_tests is None or self._configuration_service is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed Webhook test service is unavailable",
            )
        self._require_empty_query(environ, "operations notification Webhook test")
        document = self._document(environ)
        if set(document) != {"expectedRevisionId", "expectedVersion"}:
            raise ValueError("Webhook test requires expectedRevisionId and expectedVersion only")
        expected_revision_id = document["expectedRevisionId"]
        if not isinstance(expected_revision_id, str) or not expected_revision_id.strip():
            raise ValueError("Webhook test expectedRevisionId must be a non-empty string")
        expected = document["expectedVersion"]
        if isinstance(expected, bool) or not isinstance(expected, int):
            raise ValueError("Webhook test expectedVersion must be an integer")
        revision = self._configuration_service.require(expected_revision_id)
        if revision.version != expected:
            return self._error(
                start_response,
                409,
                "configuration_version_conflict",
                "the selected Webhook revision is stale; reload before testing",
                details={
                    "revisionId": revision.revision_id,
                    "currentVersion": revision.version,
                    "durableState": "no test request was sent",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "reload the Webhook definition, then test the exact current revision again"
                    ),
                },
            )
        # A valid historical revision with a matching version is still not the
        # displayed revision: only the exact currently advertised Active
        # revision (for a definition it contains) or the eligible open
        # successor Draft may be tested, and the rejection happens before any
        # transport invocation.
        resolution = self._notification_webhook_resolution(webhook_id, start_response)
        if not isinstance(resolution, tuple):
            return resolution
        active, draft, _raw, in_active = resolution
        advertised = set()
        if active is not None and in_active:
            advertised.add(active.revision_id)
        if draft is not None:
            advertised.add(draft.revision_id)
        if expected_revision_id not in advertised:
            return self._error(
                start_response,
                409,
                "configuration_version_conflict",
                (
                    "the selected revision is not the currently advertised Active revision "
                    "or the open successor Draft for this Webhook definition; no test "
                    "request was sent"
                ),
                details={
                    "durableState": "no test request was sent",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "reload the Webhook definition, then test the exact advertised "
                        "revision again"
                    ),
                },
            )
        result = self._webhook_tests.test(
            expected_revision_id,
            webhook_id,
            expected_version=expected,
            expected_digest=revision.digest,
            actor=principal.principal_id,
        )
        # The digest is server-side binding evidence for the existing managed
        # surfaces; the bounded operator outcome never carries it.
        revision_evidence = dict(result.get("revision") or {})
        revision_evidence.pop("digest", None)
        result["revision"] = revision_evidence
        return self._response(start_response, 200, result)

    def _notification_delivery_operator_detail(
        self, delivery_id: str, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        """Bounded delivery detail with permission-aware recovery actions.

        The durable document comes from the shared NotificationDeliveryService
        authority; this projection only adds backend-authoritative action
        metadata so the Web journey can hide recovery controls with a truthful
        reason when the connected principal lacks the recovery permission.
        """

        detail = self._notification_deliveries.detail(
            delivery_id,
            lease_seconds=self._notification_delivery_lease_seconds(),
        )
        manage = ApiPermission.MANAGE_CONFIGURATION in principal.permissions
        available = set(detail.get("recovery", {}).get("availableActions") or [])
        actions: dict[str, object] = {}
        if "requeue-dead-letter" in available:
            actions["requeue"] = {
                "available": manage,
                "reason": (
                    None
                    if manage
                    else self._organize_unavailable_reason(
                        manage,
                        ApiPermission.MANAGE_CONFIGURATION,
                        "the connected API principal cannot recover notification deliveries",
                    )
                ),
                "method": "POST",
                "path": f"/api/v1/notifications/{delivery_id}/requeue",
                "requiresConfirmation": True,
                "sideEffects": "delivery_queue_state_only",
                "durableOutcome": (
                    "the dead-letter delivery returns to pending with the same identity; "
                    "attempts are reset"
                ),
                "nextAction": (
                    "confirm the requeue, then refresh this delivery to watch the worker reclaim it"
                ),
            }
        if "resolve-stale" in available:
            actions["resolveStale"] = {
                "available": manage,
                "reason": (
                    None
                    if manage
                    else self._organize_unavailable_reason(
                        manage,
                        ApiPermission.MANAGE_CONFIGURATION,
                        "the connected API principal cannot recover notification deliveries",
                    )
                ),
                "method": "POST",
                "path": f"/api/v1/notifications/{delivery_id}/resolve-stale",
                "requiresConfirmation": True,
                "sideEffects": "delivery_queue_state_only",
                "durableOutcome": (
                    "the expired-lease delivery returns to pending with the same identity "
                    "and attempts"
                ),
                "nextAction": (
                    "confirm the stale resolution, then refresh this delivery to watch the "
                    "worker reclaim it"
                ),
            }
        detail["actions"] = actions
        return self._response(start_response, 200, detail)

    def _notification_webhook_activate_checked_draft(
        self,
        webhook_id: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ) -> None:
        """Checked-activate the exact open successor Draft that owns this Webhook.

        The browser supplies the Draft's exact advertised revision identity and
        optimistic version — never a digest. The action is bound to that exact
        Draft revision, the Active base is pinned, and the Draft's changes are
        compared with the Active document so a revision that touches anything
        outside the Webhook Definition boundary is rejected before any
        activation, and so the ``webhooks`` section changes only at the
        reviewed definition's exact identity — a sibling definition can never
        be added, removed or modified while riding along. Because the
        confinement comparison proves every other section and every other
        definition is identical to the live Active configuration, the published
        configuration carries no new Storage, strategy or destination
        semantics. No delivery is created by activation, and a Draft-only
        definition (newly created or copied) is activatable exactly like an
        edited Active definition.
        """

        if self._configuration_service is None or self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
        self._require_empty_query(environ, "operations notification draft activation")
        document = self._document(environ)
        if set(document) != {"expectedRevisionId", "expectedVersion"}:
            raise ValueError(
                "notification draft activation requires expectedRevisionId and expectedVersion only"
            )
        expected_revision_id = document["expectedRevisionId"]
        if not isinstance(expected_revision_id, str) or not expected_revision_id.strip():
            raise ValueError(
                "notification draft activation expectedRevisionId must be a non-empty string"
            )
        expected = document["expectedVersion"]
        if isinstance(expected, bool) or not isinstance(expected, int):
            raise ValueError("notification draft activation expectedVersion must be an integer")
        active = self._configuration_service.active()
        try:
            draft = self._configuration_service.latest_open_draft_containing("webhooks", webhook_id)
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        if active is None:
            raise UnattendedExecutionGrantError(
                "no Active configuration exists; managed configuration setup owns the first Draft",
                code="notification_active_missing",
                status=409,
                durable_state="no configuration was activated",
                next_action="complete managed configuration setup, then stage a successor Draft",
            )
        if draft is None:
            raise UnattendedExecutionGrantError(
                "no open successor Draft contains this Webhook definition",
                code="notification_draft_required",
                status=409,
                durable_state="active configuration preserved",
                next_action="create a successor Draft, edit the definition, then activate",
            )
        if draft.revision_id != expected_revision_id:
            raise ConfigurationVersionConflict(
                "the submitted Draft identity does not match the current open successor "
                "Draft; reload the Draft",
                revision_id=draft.revision_id,
                current_version=draft.version,
                durable_state="draft_preserved",
                next_action=(
                    "reload the Draft document, then activate the exact advertised "
                    "Draft revision again"
                ),
            )
        if draft.version != expected:
            raise ConfigurationVersionConflict(
                "the successor Draft changed before activation; reload the Draft",
                revision_id=draft.revision_id,
                current_version=draft.version,
                durable_state="draft_preserved",
                next_action="reload the Draft, then activate the current version again",
            )
        if draft.base_active_revision_id != active.revision_id:
            raise ConfigurationVersionConflict(
                "the Active configuration changed after this Draft was created; "
                "stage a fresh successor Draft",
                revision_id=draft.revision_id,
                current_version=draft.version,
                durable_state="draft_preserved",
                next_action=(
                    "create a fresh successor Draft from the current Active "
                    "configuration, then edit, validate and activate it"
                ),
            )
        changed = self._notification_draft_changed_sections(draft.document, active.document)
        if changed - {"webhooks"}:
            raise UnattendedExecutionGrantError(
                "this Draft changes configuration outside the Webhook Definition boundary",
                code="notification_activation_out_of_scope",
                status=409,
                durable_state="active configuration preserved",
                next_action=(
                    "remove the unrelated configuration changes from the Draft, or use the "
                    "managed configuration activation journey with explicit review"
                ),
            )
        self._require_webhook_only_change(active.document, draft.document, webhook_id)
        # The exact-revision binding, Active-base pin and Webhook-only
        # confinement above prove every non-Webhook section and every other
        # Webhook definition is identical to the live Active configuration, so
        # no new Storage, strategy or destination semantics are published by
        # this activation. The managed activation revalidates the exact
        # revision digest, optimistic version and document loader atomically
        # before publishing.
        activated = self._configuration_service.activate(
            draft.revision_id,
            expected_version=draft.version,
            actor=principal.principal_id,
        )
        self._refresh_configuration_binding()
        active_after = self._configuration_service.active()
        webhook_after = next(
            (
                item
                for item in ConfigurationObjectService._webhooks_projection(activated.document)
                if isinstance(item, dict) and item.get("id") == webhook_id
            ),
            None,
        )
        return self._response(
            start_response,
            200,
            {
                "activatedRevisionId": activated.revision_id,
                "activatedVersion": activated.version,
                "revisionSequence": activated.revision_sequence,
                # Echo of the exact reviewed Draft identity the activation was
                # bound to, so the Web client can verify the success document
                # against the submitted mutation.
                "publishedFromRevisionId": draft.revision_id,
                "publishedFromVersion": draft.version,
                "activeConfiguration": self._automation_active_configuration(active_after),
                "webhook": webhook_after,
            },
        )

    @staticmethod
    def _notification_webhook_canonical_document(document: object) -> dict:
        """Copy of one document with the legacy nested Webhook spelling normalized.

        The managed Webhook edit path moves ``notifications.webhooks`` to the
        root ``webhooks`` section, so the confinement comparison must treat
        that spelling migration as the same boundary, not as an unrelated
        configuration change.
        """

        value = copy.deepcopy(document) if isinstance(document, dict) else {}
        if "webhooks" not in value:
            notifications = value.get("notifications")
            if isinstance(notifications, dict) and isinstance(notifications.get("webhooks"), list):
                value["webhooks"] = copy.deepcopy(notifications["webhooks"])
                nested = dict(notifications)
                nested.pop("webhooks", None)
                value["notifications"] = nested
        return value

    @classmethod
    def _notification_draft_changed_sections(
        cls, draft_document: object, active_document: object
    ) -> set[str]:
        """Top-level configuration sections the Draft changes versus Active.

        Both documents are first normalized to the canonical root ``webhooks``
        spelling so a managed Webhook edit inside a legacy-spelled Active
        document is confined to the Webhook boundary instead of being read as
        an unrelated configuration change.
        """

        return MediaFlowApi._automation_draft_changed_sections(
            cls._notification_webhook_canonical_document(draft_document),
            cls._notification_webhook_canonical_document(active_document),
        )

    @staticmethod
    def _webhook_identity_map(document: object) -> dict[str, object] | None:
        """Effective Webhook id → entry map for either section spelling.

        Returns ``None`` when the effective section is malformed (not a list,
        an entry that is not an object, a non-string id, or a duplicated id),
        so the caller can fail closed instead of activating an unverifiable
        boundary.
        """

        if not isinstance(document, dict):
            return None
        section = document.get("webhooks")
        if not isinstance(section, list):
            notifications = document.get("notifications")
            if isinstance(notifications, dict) and isinstance(notifications.get("webhooks"), list):
                section = notifications["webhooks"]
            else:
                section = []
        definitions: dict[str, object] = {}
        for entry in section:
            if not (isinstance(entry, dict) and isinstance(entry.get("id"), str)):
                return None
            entry_id = entry["id"]
            if entry_id in definitions:
                return None
            definitions[entry_id] = entry
        return definitions

    def _require_webhook_only_change(
        self,
        active_document: object,
        draft_document: object,
        webhook_id: str,
    ) -> None:
        """Fail closed unless the Draft's only Webhook change is this definition.

        The section-level confinement proves no other configuration section
        changed; this comparison proves the effective ``webhooks`` section
        changed only at the reviewed definition's exact identity. Every other
        definition must be present in both documents and identical, so a
        sibling definition cannot be added, removed or modified while riding
        along with the reviewed activation — including the create/copy case,
        where the new or copied definition must be the sole Webhook change.
        Malformed sections fail closed: an unverifiable boundary is never
        activated.
        """

        active_definitions = self._webhook_identity_map(active_document)
        draft_definitions = self._webhook_identity_map(draft_document)
        if active_definitions is None or draft_definitions is None:
            raise UnattendedExecutionGrantError(
                "the Webhook definition section is malformed; activation "
                "cannot verify its exact boundary",
                code="notification_activation_out_of_scope",
                status=409,
                durable_state="active configuration preserved",
                next_action=(
                    "create a fresh successor Draft from the current Active "
                    "configuration, then edit, validate and activate it"
                ),
            )
        unexpected = sorted(
            candidate_id
            for candidate_id in set(active_definitions) | set(draft_definitions)
            if candidate_id != webhook_id
            and (
                candidate_id not in active_definitions
                or candidate_id not in draft_definitions
                or draft_definitions[candidate_id] != active_definitions[candidate_id]
            )
        )
        if unexpected:
            raise UnattendedExecutionGrantError(
                "this Draft changes other Webhook Definitions beyond the reviewed definition",
                code="notification_activation_definition_scope",
                status=409,
                durable_state="active configuration preserved",
                next_action=(
                    "remove the other definition changes from this Draft, then edit, "
                    "validate and activate one definition per Draft"
                ),
            )

    def _file_catalog_detail_value(self, detail) -> dict:
        projection = (
            self._file_lifecycle.project(detail) if self._file_lifecycle is not None else None
        )
        document = self._file_catalog_value(detail.record)
        document["surface"] = "file_index"
        document["filesSurface"] = "/api/v1/storage/files"
        if projection is not None:
            document["currentOccurrence"] = {
                **document["currentOccurrence"],
                "history": [value.document() for value in projection.occurrence_history],
            }
            document["occurrenceHistory"] = [
                value.document() for value in projection.occurrence_history
            ]
            document["reprocess"] = {
                "eligible": projection.reprocess_eligible,
                "reason": projection.reprocess_reason,
                "required": {
                    "occurrenceId": detail.record.occurrence_id,
                    "fingerprint": detail.record.fingerprint,
                },
            }
            document["priorResultRelevance"] = [
                {
                    "resultId": result.result_id,
                    "relevance": relation,
                    "current": relation == "current",
                }
                for result, relation in projection.result_relevance
            ]
            document["reprocessRequests"] = [
                value.document() for value in projection.reprocess_requests
            ]
        if self._manual_execution is not None:
            document["manualExecutionDiscovery"] = self._manual_execution.discovery_for_source(
                detail.record.storage_id,
                detail.record.path,
            )
        related_reviews = [
            {
                "kind": item.kind,
                "reviewId": item.review_id,
                "status": item.status,
                "taskId": item.task_id,
                "itemId": item.item_id,
            }
            for item in detail.related_reviews
        ]
        if self._file_catalog is not None:
            continuation_service = FileMetadataCorrectionContinuationService(
                self._file_catalog,
                self._repository,
            )
            for value in related_reviews:
                if value["kind"] != "metadata_correction":
                    continue
                get_continuation = getattr(
                    self._repository,
                    "get_metadata_correction_continuation_for_review",
                    None,
                )
                continuation = (
                    get_continuation(value["reviewId"]) if callable(get_continuation) else None
                )
                try:
                    context = continuation_service.context(detail.record.file_id, value["reviewId"])
                except (LookupError, ValueError):
                    # A queued/running/failed continuation must remain visible even
                    # if source linkage became stale after admission. Projection is
                    # read-only; retry stays disabled until the linkage is repaired.
                    if continuation is None:
                        continue
                    value["correctionVersion"] = continuation.correction_version
                    value["configurationSnapshotId"] = continuation.configuration_snapshot_id
                    value["configurationSnapshotDigest"] = (
                        continuation.configuration_snapshot_digest
                    )
                    value["canContinue"] = False
                    value["continuation"] = self._metadata_correction_continuation_value(
                        continuation,
                        next_action=(
                            "repair the linked File/Task/TaskItem, then reload before retrying"
                        ),
                    )
                    continue
                value["correctionVersion"] = context.correction_version
                value["configurationSnapshotId"] = context.configuration_snapshot_id
                value["configurationSnapshotDigest"] = context.configuration_snapshot_digest
                value["canContinue"] = context.current is None or context.current.status in {
                    MetadataCorrectionContinuationStatus.FAILED,
                    MetadataCorrectionContinuationStatus.CANCELLED,
                }
                if context.current is not None:
                    get_job = getattr(self._repository, "get_job", None)
                    job = get_job(context.current.job_id) if callable(get_job) else None
                    stale = (
                        context.current.status is MetadataCorrectionContinuationStatus.RUNNING
                        and job is not None
                        and job.status.value == "running"
                        and datetime.now(UTC) - job.updated_at
                        >= timedelta(seconds=self._runtime_binding.stale_job_age_seconds)
                    )
                    value["continuation"] = self._metadata_correction_continuation_value(
                        context.current,
                        display_status="stale" if stale else None,
                        job=job,
                    )
                    if stale:
                        value["nextAction"] = (
                            "inspect the stale Job and explicitly requeue it, then reload this File"
                        )
        document["relatedReviews"] = related_reviews
        document["evidence"] = [self._pipeline_evidence_value(value) for value in detail.evidence]
        document["evidenceAvailability"] = "available" if detail.evidence else "unavailable"
        document["items"] = []
        for value in detail.items:
            item_document = self._file_detail_item_value(value)
            if (
                detail.record.occurrence_id is None
                or detail.record.occurrence_state.value == "legacy"
                or value.source_occurrence_id is None
            ):
                item_document["relevance"] = "unverified_legacy"
                item_document["current"] = False
            elif value.source_occurrence_id == detail.record.occurrence_id:
                if (
                    value.source_fingerprint_state == "verified"
                    and value.source_fingerprint == detail.record.fingerprint
                ):
                    item_document["relevance"] = "current"
                    item_document["current"] = True
                else:
                    item_document["relevance"] = "historical_fingerprint_mismatch"
                    item_document["current"] = False
            else:
                item_document["relevance"] = "historical_different_occurrence"
                item_document["current"] = False
            document["items"].append(item_document)
        relation_by_result = (
            {result.result_id: relation for result, relation in projection.result_relevance}
            if projection is not None
            else {}
        )
        document["results"] = [
            self._file_result_value(value, relevance=relation_by_result.get(value.result_id))
            for value in detail.results
        ]
        document["currentActions"] = [
            {
                "actionId": value.action_id,
                "label": value.label,
                "confirmationRequired": value.confirmation_required,
                "requiredAuthority": value.required_authority,
                "resolutionSurface": value.resolution_surface,
                "admissible": value.admissible,
                "taskId": value.task_id,
                "itemId": value.item_id,
            }
            for value in detail.actions
        ]
        document["truncated"] = dict(detail.truncated)
        latest_result = (
            projection.current_result if projection is not None else detail.latest_result
        )
        if latest_result is None:
            document["latestResult"] = None
            return document
        document["latestResult"] = self._file_result_value(
            latest_result,
            include_source=False,
            latest=True,
            relevance=(
                "current"
                if projection is not None
                and latest_result.source_occurrence_id == detail.record.occurrence_id
                and latest_result.source_fingerprint == detail.record.fingerprint
                else "unverified_legacy"
                if projection is not None
                else None
            ),
        )
        return document

    @staticmethod
    def _pipeline_evidence_value(evidence) -> dict:
        return evidence.document()

    @staticmethod
    def _file_detail_item_value(item) -> dict:
        return {
            "taskId": item.task_id,
            "itemId": item.item_id,
            "status": item.status,
            "stage": item.stage,
            "updatedAt": item.updated_at.isoformat(),
            "sourceStorageId": item.source_storage_id,
            "resourceLibraryId": item.resource_library_id,
            "sourcePath": item.source_path,
            "sourceOccurrenceId": item.source_occurrence_id,
            "sourceFingerprint": item.source_fingerprint,
            "sourceFingerprintState": item.source_fingerprint_state,
            "checkpoint": item.checkpoint,
        }

    @staticmethod
    def _file_result_value(
        result,
        *,
        include_source: bool = True,
        latest: bool = False,
        relevance: str | None = None,
    ) -> dict:
        document = {
            "resultId": result.result_id,
            "taskId": result.task_id,
            "itemId": result.item_id,
            "status": result.status,
            "recognitionType": result.recognition_type,
            "provider": result.provider,
            "providerId": result.provider_id,
            "title": result.title,
            "metadataPolicyId": result.metadata_policy_id,
            "namingPolicyId": result.naming_policy_id,
            "classificationPolicyId": result.classification_policy_id,
            "organizePolicyId": result.organize_policy_id,
            "operation": result.operation,
            "destinationStorageId": result.destination_storage_id,
            "destinationPath": result.destination_path,
            "createdAt": result.created_at.isoformat(),
            "retryAttempts": result.retry_attempts,
            "cleanupStatus": result.cleanup_status,
            "error": result.error,
            "sourceOccurrenceId": result.source_occurrence_id,
            "sourceFingerprint": result.source_fingerprint,
            "sourceFingerprintState": result.source_fingerprint_state,
        }
        explanation = failure_document(result.error)
        if explanation is not None:
            document["failureExplanation"] = explanation
        if include_source:
            document["sourceStorageId"] = result.source_storage_id
            document["sourcePath"] = result.source_path
        if not latest:
            document["effectCertainty"] = result.effect_certainty
            document["uncertainEffects"] = list(result.uncertain_effects)
            document["completedOperations"] = list(result.completed_operations)
            document["attachmentCount"] = result.attachment_count
        if relevance is not None:
            document["relevance"] = relevance
            document["current"] = relevance == "current"
        return redact_manual_value(document)

    @classmethod
    def _metadata_correction_continuation_value(
        cls,
        continuation: MetadataCorrectionContinuation,
        *,
        display_status: str | None = None,
        next_action: str | None = None,
        job=None,
    ) -> dict:
        status = display_status or continuation.status.value
        return {
            "continuationId": continuation.continuation_id,
            "jobId": continuation.job_id,
            "taskId": continuation.new_task_id,
            "resultId": continuation.new_result_id,
            "status": status,
            "executionMode": "dry_run",
            "sourceTaskId": continuation.source_task_id,
            "sourceItemId": continuation.source_item_id,
            "configurationSnapshotId": continuation.configuration_snapshot_id,
            "configurationSnapshotDigest": continuation.configuration_snapshot_digest,
            "correctionVersion": continuation.correction_version,
            "failureCategory": getattr(job, "failure_category", None),
            "snapshotUnavailable": getattr(job, "failure_category", None)
            in {
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
            },
            "error": continuation.error,
            "recovery": continuation.recovery,
            "nextAction": next_action or cls._metadata_correction_continuation_next_action(status),
            "createdAt": continuation.created_at.isoformat(),
            "updatedAt": continuation.updated_at.isoformat(),
        }

    @staticmethod
    def _metadata_correction_continuation_next_action(status: str) -> str:
        return {
            "queued": "wait for the Worker, then inspect the linked DryRun Task/Result",
            "running": "wait for the Worker, then inspect the linked DryRun Task/Result",
            "stale": "inspect and explicitly requeue the stale Job, then reload this File",
            "completed": "inspect the linked DryRun Task/Result; the source remains unchanged",
            "failed": (
                "inspect the failure, repair the stated condition, then retry this correction"
            ),
            "cancelled": "refresh the File detail and explicitly continue this correction again",
        }.get(status, "inspect the linked continuation state")

    @classmethod
    def _value(cls, value):
        if hasattr(value, "__dataclass_fields__"):
            document = {
                key: cls._value(item)
                for key, item in asdict(value).items()
                if key not in {"claim_token", "scope_path"}
            }
            explanation = failure_document(document.get("error"))
            if explanation is not None:
                document["failureExplanation"] = explanation
            return document
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, tuple):
            return [cls._value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._value(item) for key, item in value.items()}
        return value

    @staticmethod
    def _response(start_response: Callable, status: int, document: dict) -> list[bytes]:
        body = json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")
        labels = {
            200: "OK",
            201: "Created",
            202: "Accepted",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            409: "Conflict",
            413: "Payload Too Large",
            422: "Unprocessable Entity",
            500: "Internal Server Error",
            503: "Service Unavailable",
        }
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("X-Frame-Options", "DENY"),
        ]
        if status == 401:
            headers.append(("WWW-Authenticate", 'Bearer realm="mediaflow"'))
        start_response(f"{status} {labels[status]}", headers)
        return [body]

    def _job_document(
        self, job, principal: ResolvedApiPrincipal, *, bounded: bool = False
    ) -> dict[str, object]:
        """Project one Job with its worker evidence and lifecycle projection.

        The bounded Operations projection is an explicit operator allowlist.
        The pre-existing compatibility document keeps its historical keys for
        existing clients while the claim/fence, scope, fingerprint and raw error
        values stay out of every document.  Either way the response carries the
        bounded worker ownership evidence (workerId, ownerLastHeartbeatAt) for a
        RUNNING Job and the operational condition (no-worker / stale-worker) for
        a PENDING or stale RUNNING Job with a bounded recovery next action.
        """
        document = job_operator_document(job) if bounded else self._compatibility_document(job)
        status_value = document.get("status")
        if status_value == "running":
            worker_id = getattr(job, "worker_id", None)
            if worker_id:
                document["workerId"] = worker_id
            document.update(self._worker_owner_evidence(worker_id))
        elif status_value == "pending":
            if self._worker_service is not None:
                readiness = self._worker_service.evaluate_readiness(
                    active_snapshot_id=self._runtime_binding.snapshot_id,
                    active_snapshot_digest=self._runtime_binding.snapshot_digest,
                )
                if not readiness.get("ready"):
                    document["operationalCondition"] = {
                        "condition": readiness.get("condition"),
                        "stage": "pending",
                        "durableState": readiness.get("durableState"),
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": readiness.get("nextAction"),
                    }
        document["lifecycle"] = redact_manual_value(
            job_lifecycle_document(job, permissions=principal.permissions)
        )
        return document

    def _worker_owner_evidence(self, worker_id: str | None) -> dict[str, object]:
        """Bound worker ownership and recovery evidence for one running Job."""

        if self._worker_service is None:
            return {}
        if worker_id:
            worker = self._worker_service.evaluate_worker(worker_id)
            evidence: dict[str, object] = {
                "workerId": worker_id,
                "ownerStatus": worker.status.value if worker is not None else None,
                "ownerLastHeartbeatAt": (
                    worker.last_heartbeat_at.isoformat() if worker is not None else None
                ),
            }
            condition = self._worker_unusable_condition(worker)
            if condition is not None:
                evidence["operationalCondition"] = condition
            return evidence
        readiness = self._worker_service.evaluate_readiness(
            active_snapshot_id=self._runtime_binding.snapshot_id,
            active_snapshot_digest=self._runtime_binding.snapshot_digest,
        )
        if readiness.get("ready"):
            return {}
        return {
            "operationalCondition": {
                "condition": readiness.get("condition"),
                "stage": "running",
                "durableState": readiness.get("durableState"),
                "sideEffects": "none",
                "retrySafe": True,
                "nextAction": readiness.get("nextAction"),
            }
        }

    @staticmethod
    def _worker_unusable_condition(worker) -> dict[str, object] | None:
        if worker is None:
            return {
                "condition": WorkerReadiness.NO_WORKER.value,
                "stage": "running",
                "durableState": "the owning processing worker is no longer registered",
                "sideEffects": "none",
                "retrySafe": True,
                "nextAction": (
                    "restart a resident worker with the active configuration, then inspect "
                    "or explicitly requeue the Job"
                ),
            }
        if worker.status is WorkerStatus.LIVE:
            return None
        durable_state = (
            "the owning processing worker is stopped"
            if worker.status is WorkerStatus.STOPPED
            else "the owning processing worker has a stale heartbeat"
        )
        return {
            "condition": WorkerReadiness.STALE_WORKER.value,
            "stage": "running",
            "durableState": durable_state,
            "sideEffects": "none",
            "retrySafe": True,
            "nextAction": (
                "restart the resident worker, then inspect or explicitly requeue the stale Job"
            ),
        }

    @classmethod
    def _error(
        cls,
        start_response: Callable,
        status: int,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ):
        error = {"code": code, "message": redact_manual_text(message)}
        if details:
            error["details"] = redact_manual_value(details)
        return cls._response(start_response, status, {"error": error})
