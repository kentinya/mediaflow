from __future__ import annotations

import hmac
import json
import threading
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from urllib.parse import parse_qs
from uuid import uuid4

from mediaflow.application.automation import AutomationJobService
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
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.application.file_catalog import FileCatalogFilter, FileCatalogService
from mediaflow.application.file_metadata_correction import FileMetadataCorrectionService
from mediaflow.application.file_recognition_request import FileRecognitionRequestService
from mediaflow.application.file_replan_request import FileReplanRequestService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.metadata_correction_continuation import (
    FileMetadataCorrectionContinuationService,
    MetadataCorrectionContinuationConflict,
)
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.recognition_retry import RecognitionRetryService
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.recovery_batch import RecoveryBatchContinuationService
from mediaflow.application.recovery_continuation import RecoveryContinuationService
from mediaflow.application.unattended_execution import (
    UnattendedExecutionGrantError,
    UnattendedExecutionGrantService,
)
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationQueueFull,
    AutomationTaskDefinition,
)
from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationFirstDraftConflict,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationVersionConflict,
    RuntimeConfigurationNotConfigured,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.failure import failure_document
from mediaflow.domain.logging import LogLevel
from mediaflow.domain.manual_organize import (
    ManualIntentError,
)
from mediaflow.domain.manual_safety import redact_manual_text, redact_manual_value
from mediaflow.domain.metadata_correction import (
    MetadataCorrectionContinuation,
    MetadataCorrectionContinuationStatus,
)
from mediaflow.domain.notification import NotificationDeliveryStatus
from mediaflow.domain.organizer import ConflictStrategy
from mediaflow.domain.recovery import RecoveryAdmissionError, RecoveryAdmissionReason
from mediaflow.domain.recovery_continuation import (
    RecoveryContinuationError,
    RecoveryContinuationReason,
)
from mediaflow.domain.scanner import FileScanStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal, SecurityAuditRecord
from mediaflow.domain.task_persistence import ConfirmationStatus
from mediaflow.interfaces.operator_ui import ASSETS as OPERATOR_UI_ASSETS
from mediaflow.interfaces.pagination import (
    CursorDirection,
    DecodedCursor,
    decode_directional_cursor,
    encode_cursor,
)


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


class MediaFlowApi:
    """Small WSGI transport over persistence and queue application boundaries."""

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
        maximum_active_jobs: int = 100,
        stale_job_age_seconds: int = 3600,
        system_status=None,
        file_catalog: FileCatalogService | None = None,
        file_index=None,
        metadata_policies=(),
        configuration_service: ManagedConfigurationService | None = None,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        bootstrap_document: object | None = None,
        metadata_provider_registry_factory=None,
        recovery_snapshot_validator: Callable[[str, str], None] | None = None,
        manual_intent_service: ManualOrganizeIntentService | None = None,
        manual_preview_service: ManualOrganizePreviewService | None = None,
        manual_execution_service: ManualOrganizeExecutionService | None = None,
        automation_preview_service: AutomationTaskDefinitionPreviewService | None = None,
        management_only: bool = False,
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
        self._configuration_service = configuration_service
        self._manual_intents = manual_intent_service
        if self._manual_intents is None and self._file_catalog is not None:
            self._manual_intents = ManualOrganizeIntentService(
                repository,
                self._file_catalog,
                configuration_service,
            )
        self._manual_previews = manual_preview_service
        if self._manual_previews is None and self._manual_intents is not None:
            self._manual_previews = ManualOrganizePreviewService(
                repository,
                self._manual_intents,
                self._file_catalog,
                configuration_service=configuration_service,
                metadata_provider_registry_factory=metadata_provider_registry_factory,
            )
        self._configuration_objects = (
            ConfigurationObjectService(
                configuration_service,
                metadata_provider_registry_factory=metadata_provider_registry_factory,
            )
            if configuration_service is not None
            else None
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
        self._runtime_binding_lock = threading.RLock()
        self._runtime_binding = self._build_runtime_binding(
            snapshot_id=configuration_snapshot_id,
            snapshot_digest=configuration_snapshot_digest,
            maximum_active_jobs=maximum_active_jobs,
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
            details = {
                key: value
                for key, value in {
                    "revisionId": error.revision_id,
                    "currentRevisionId": error.current_revision_id,
                    "currentVersion": error.current_version,
                    "currentDigest": error.current_digest,
                    "durableState": (
                        "draft_preserved_active_unchanged"
                        if error.current_revision_id
                        else "draft_preserved"
                    ),
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
            details = {
                key: value
                for key, value in {
                    "revisionId": error.revision_id,
                    "currentVersion": error.current_version,
                    "currentDigest": error.current_digest,
                    "durableState": error.durable_state or "draft_preserved",
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
                    "durableState": "no_workflow_work_created",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "create or resume the first setup Draft, complete guided setup, "
                        "validate it, and activate it"
                    ),
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
            details = {
                key: value
                for key, value in {
                    "revisionId": error.revision_id,
                    "version": error.version,
                    "digest": error.digest,
                    "reason": error.reason,
                    "durableState": "managed_active_unavailable",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": "inspect configuration status and stage a replacement Draft",
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
        configuration_route = parts[:3] == ["api", "v1", "configuration"]
        automation_definition_route = parts[:4] == [
            "api",
            "v1",
            "automation",
            "task-definitions",
        ]
        management_readiness_route = parts == ["api", "v1", "management", "readiness"]
        task_read_route = parts[:3] == ["api", "v1", "tasks"] and method == "GET"
        if self._is_management_only_setup() and self._is_workflow_producing_route(method, parts):
            raise RuntimeConfigurationNotConfigured()
        binding = self._runtime_binding
        if (
            not configuration_route
            and not management_readiness_route
            and not automation_definition_route
            and not task_read_route
        ):
            binding = self._refresh_configuration_binding()
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
            eligibility = self._unattended_grants.project_eligibility(
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
            return self._response(start_response, 200, response)
        if (
            len(parts) == 9
            and parts[:3] == ["api", "v1", "configuration"]
            and parts[3] == "revisions"
            and parts[5] == "objects"
            and parts[6] in {"automationTaskDefinitions", "storages"}
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
            document = self._document(environ)
            expected = document.get("expectedVersion")
            if isinstance(expected, bool) or not isinstance(expected, int):
                raise ValueError("configuration expectedVersion must be an integer")
            action = parts[8]
            is_storage = parts[6] == "storages"
            label = "Storage" if is_storage else "Automation Task Definition"
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
                if is_storage:
                    revision = self._configuration_objects.copy_storage(
                        parts[4],
                        object_id=parts[7],
                        new_object_id=new_id,
                        new_name=new_name,
                        expected_version=expected,
                        actor=principal.principal_id,
                    )
                else:
                    revision = self._configuration_objects.copy_definition(
                        parts[4],
                        object_id=parts[7],
                        new_object_id=new_id,
                        new_name=new_name,
                        expected_version=expected,
                        actor=principal.principal_id,
                    )
            else:
                if set(document) != {"expectedVersion"}:
                    raise ValueError(f"{label} enable/disable requires expectedVersion")
                if is_storage:
                    revision = self._configuration_objects.set_storage_enabled(
                        parts[4],
                        object_id=parts[7],
                        enabled=action == "enable",
                        expected_version=expected,
                        actor=principal.principal_id,
                    )
                else:
                    revision = self._configuration_objects.set_definition_enabled(
                        parts[4],
                        object_id=parts[7],
                        enabled=action == "enable",
                        expected_version=expected,
                        actor=principal.principal_id,
                    )
            if is_storage:
                storages = self._configuration_objects.revision_detail(revision.revision_id)[
                    "objects"
                ]["storages"]
                storage = (
                    storages[-1]
                    if action == "copy" and storages
                    else next((item for item in storages if item.get("id") == parts[7]), None)
                )
                response = revision.summary()
                if storage is not None:
                    response["storage"] = storage
                return self._response(start_response, 200, response)
            definitions = revision.document.get("automationTaskDefinitions", [])
            if action == "copy":
                definition = definitions[-1] if definitions else None
            else:
                definition = next(
                    (item for item in definitions if item.get("id") == parts[7]),
                    None,
                )
            response = revision.summary()
            if definition is not None:
                response["automationTaskDefinition"] = definition
            self._invalidate_automation_previews(
                parts[7],
                f"the pinned Automation Task Definition was {action}",
            )
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
            if set(document) == {"source"} and document.get("source") == "current":
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
            values = self._file_catalog.list(filters)
            return self._response(
                start_response,
                200,
                {
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
                return self._response(
                    start_response,
                    200,
                    {
                        "available": False,
                        "fileId": None,
                        "unavailableReason": (
                            "the source link is ambiguous; scope it by ResourceLibrary and reload"
                            if unavailable_reason == "ambiguous"
                            else "no current indexed FileIndex record matches this source link"
                        ),
                    },
                )
            return self._response(
                start_response,
                200,
                {
                    "available": True,
                    "fileId": record.file_id,
                    "resourceLibraryId": record.resource_library_id,
                    "detailUrl": f"/api/v1/files/{record.file_id}",
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
            and parts[4] in {"re-recognize", "re-plan", "re-match", "continue-dry-run"}
            and method == "POST"
        ):
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            if self._file_catalog is None:
                return self._error(
                    start_response, 503, "service_unavailable", "file catalog is unavailable"
                )
            self._require_empty_query(environ, "file action")
            document = self._document(environ)
            if parts[4] == "continue-dry-run":
                allowed = {"reviewId", "expectedCorrectionVersion"}
            elif parts[4] == "re-match":
                allowed = {"query", "year", "mediaType", "providerId", "note"}
            else:
                allowed = {"note"}
            if set(document).difference(allowed):
                raise ValueError(f"file {parts[4]} request fields are invalid")
            note = document.get("note")
            if parts[4] == "continue-dry-run":
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
            if parts[4] == "re-recognize":
                decision = FileRecognitionRequestService(
                    self._file_catalog,
                    RecognitionRetryService(self._repository),
                ).request(parts[3], actor=principal.principal_id, note=note)
                value = self._value(decision)
            elif parts[4] == "re-match":
                if document.get("mediaType") not in {"movie", "tv"}:
                    raise ValueError("file re-match mediaType must be movie or tv")
                review = FileMetadataCorrectionService(
                    self._file_catalog,
                    MetadataCorrectionService(
                        self._repository,
                        binding.metadata_policies,
                    ),
                ).resolve(
                    parts[3],
                    query=document.get("query"),
                    year=document.get("year"),
                    media_type=document["mediaType"],
                    provider_id=document.get("providerId"),
                    actor=principal.principal_id,
                    note=note,
                )
                value = self._value(review)
            else:
                decision = FileReplanRequestService(
                    self._file_catalog,
                    recovery_admission=self._recovery_admission,
                ).request(parts[3], actor=principal.principal_id, note=note)
                value = self._value(decision)
            return self._response(start_response, 200, value)
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
            limit, cursor = self._collection_page(environ, "tasks")
            values = self._list_page(self._repository.list_tasks, limit, cursor)
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "items": [self._value(item) for item in page],
                    "limit": limit,
                    "truncated": has_next,
                    "previous_cursor": self._page_cursor(
                        "tasks", page, has_previous, CursorDirection.PREVIOUS
                    ),
                    "next_cursor": self._page_cursor("tasks", page, has_next, CursorDirection.NEXT),
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
                value = self._value(item)
                value["checkpoint"] = self._checkpoint_service.summary(
                    item.item_id, task_id=task.task_id
                )
                checkpoint_items.append(value)
            manual_discovery = (
                self._manual_execution.discovery_for_task(task.task_id)
                if self._manual_execution is not None
                else None
            )
            return self._response(
                start_response,
                200,
                {
                    **self._value(task),
                    "items": checkpoint_items,
                    "results": [self._value(item) for item in result_page],
                    "manualExecutionDiscovery": manual_discovery,
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
                limit, cursor = self._collection_page(environ, "jobs")
                values = self._list_page(self._repository.list_jobs, limit, cursor)
                page, has_previous, has_next = self._page_window(values, limit, cursor)
                return self._response(
                    start_response,
                    200,
                    {
                        "items": [self._value(item) for item in page],
                        "limit": limit,
                        "truncated": has_next,
                        "previous_cursor": self._page_cursor(
                            "jobs", page, has_previous, CursorDirection.PREVIOUS
                        ),
                        "next_cursor": self._page_cursor(
                            "jobs", page, has_next, CursorDirection.NEXT
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
                return self._response(start_response, 202, self._value(job))
        if len(parts) == 4 and parts[:3] == ["api", "v1", "jobs"] and method == "GET":
            job = self._repository.get_job(parts[3])
            if job is None:
                raise LookupError(f"automation job {parts[3]!r} was not found")
            return self._response(start_response, 200, self._value(job))
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "cancel":
            if method != "POST":
                return self._error(start_response, 405, "method_not_allowed", "POST required")
            self._require(principal, ApiPermission.CANCEL_JOB)
            self._require_empty_query(environ, "job cancellation")
            self._require_empty_body(environ, "job cancellation")
            return self._response(start_response, 200, self._value(binding.jobs.cancel(parts[3])))
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
                self._value(
                    binding.jobs.requeue_stale(
                        parts[3],
                        age_seconds=binding.stale_job_age_seconds,
                    )
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
    def _static_response(start_response: Callable, content_type: str, body: bytes):
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
            "setupDraft": status.get("setupDraft"),
            "recoveryRequired": status.get("recoveryRequired", False),
            "health": status.get("health"),
            "unavailableReason": status.get("unavailableReason"),
            "nextAction": status.get("nextAction"),
            "canManageConfiguration": status.get("canManageConfiguration", False),
            "canActivateConfiguration": status.get("canActivateConfiguration", False),
        }

    @staticmethod
    def _require_manual_execution(principal: ResolvedApiPrincipal) -> None:
        if ApiPermission.EXECUTE_MANUAL_ORGANIZE not in principal.permissions:
            raise ApiPermissionDenied("principal lacks execute_manual_organize permission")

    def _refresh_configuration_binding(self) -> _ApiRuntimeBinding:
        with self._runtime_binding_lock:
            return self._refresh_configuration_binding_locked()

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
        if parts == ["api", "v1", "management", "readiness"]:
            return False
        if tuple(parts[:3]) in {
            ("api", "v1", "jobs"),
            ("api", "v1", "tasks"),
            ("api", "v1", "manual-intents"),
            ("api", "v1", "manual-previews"),
            ("api", "v1", "manual-executions"),
            ("api", "v1", "manual-execution-authorizations"),
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
        if snapshot_id == current.snapshot_id and digest == current.snapshot_digest:
            return current
        if runtime is None or refreshed_status is None:
            return current

        # Construct every config-derived behavior before publishing one pointer.
        # A request captures this immutable binding and cannot combine a new pin
        # with admission or execute settings retained from the previous Active.
        candidate = self._build_runtime_binding(
            snapshot_id=snapshot_id,
            snapshot_digest=digest,
            maximum_active_jobs=runtime.automation_maximum_active_jobs,
            remote_execution_enabled=runtime.remote_execution_enabled,
            remote_execution_maximum_ttl_seconds=(runtime.remote_execution_maximum_ttl_seconds),
            stale_job_age_seconds=runtime.automation_stale_job_age_seconds,
            system_status=refreshed_status,
            schedules=runtime.automation_schedules,
            metadata_policies=runtime.strategy.metadata_policies,
            resource_library_count=sum(item.enabled for item in runtime.resource_libraries),
            media_library_count=sum(item.enabled for item in runtime.media_libraries),
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
    ) -> _ApiRuntimeBinding:
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
        exact = {
            ("api", "v1", "tasks"),
            ("api", "v1", "confirmations"),
            ("api", "v1", "schedules"),
            ("api", "v1", "notifications"),
            ("api", "v1", "logs"),
            ("api", "v1", "jobs"),
            ("api", "v1", "jobs", "stale"),
            ("api", "v1", "security-audit"),
            ("api", "v1", "dashboard"),
            ("api", "v1", "system", "status"),
            ("api", "v1", "metadata-reviews"),
            ("api", "v1", "classification-reviews"),
            ("api", "v1", "recognition-reviews"),
            ("api", "v1", "metadata-corrections"),
            ("api", "v1", "recovery-batches"),
            ("api", "v1", "automation", "task-definitions"),
        }
        key = tuple(parts)
        if key in exact:
            return "/" + "/".join(parts)
        if len(parts) == 4 and parts[:3] in (
            ["api", "v1", "tasks"],
            ["api", "v1", "jobs"],
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
        if len(parts) == 5 and parts[:3] == ["api", "v1", "schedules"] and parts[4] == "audit":
            return "/api/v1/schedules/{id}/audit"
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

    @staticmethod
    def _stale_job_value(value) -> dict:
        return {
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
        if parts[:3] == ["api", "v1", "manual-intents"] or (
            len(parts) >= 3
            and parts[:2] == ["api", "v1"]
            and parts[2] in {"manual-organize", "manual-organize-intents"}
        ):
            return True
        if parts[:3] == ["api", "v1", "manual-previews"]:
            return True
        if tuple(parts[:3]) in {
            ("api", "v1", "manual-execution-authorizations"),
            ("api", "v1", "manual-executions"),
        }:
            return True
        if parts[:3] == ["api", "v1", "tasks"]:
            return True
        if parts[:4] == ["api", "v1", "automation", "task-definitions"] and (
            len(parts) in {4, 5}
            or (len(parts) == 6 and parts[5] in {"occurrences", "grant", "grant-state"})
            or (len(parts) == 7 and parts[5:7] == ["grant", "audit"])
        ):
            return True
        return parts[:3] == ["api", "v1", "files"] and (
            len(parts) == 4 or parts == ["api", "v1", "files", "by-source"]
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
        }
        try:
            return mapping[value]
        except KeyError as error:
            raise ValueError("unsupported guided configuration object kind") from error

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
        }
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError("file catalog query fields must be supported and specified once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], "file")
        scan_status = FileScanStatus(values["scanStatus"][0]) if "scanStatus" in values else None
        after = MediaFlowApi._file_cursor(values.get("after"), values.get("cursorFileId"))
        before = MediaFlowApi._file_cursor(values.get("before"), values.get("cursorFileId"))
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

    def _file_catalog_detail_value(self, detail) -> dict:
        document = self._file_catalog_value(detail.record)
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
        document["items"] = [self._file_detail_item_value(value) for value in detail.items]
        document["results"] = [self._file_result_value(value) for value in detail.results]
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
        if detail.latest_result is None:
            document["latestResult"] = None
            return document
        document["latestResult"] = self._file_result_value(
            detail.latest_result, include_source=False, latest=True
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
            "checkpoint": item.checkpoint,
        }

    @staticmethod
    def _file_result_value(result, *, include_source: bool = True, latest: bool = False) -> dict:
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
