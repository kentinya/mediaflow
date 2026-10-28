from __future__ import annotations

import copy
import hmac
import json
import os
import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from urllib.parse import parse_qs, quote
from uuid import uuid4
from zoneinfo import ZoneInfo

from mediaflow.application.automation import AutomationJobService, ProcessingWorkerService
from mediaflow.application.automation_definition_occurrence import (
    AutomationDefinitionOccurrenceService,
)
from mediaflow.application.automation_run_once import (
    AutomationRunOnceError,
    AutomationRunOnceService,
)
from mediaflow.application.automation_settings import (
    AutomationSettingsPublicationError,
    AutomationSettingsService,
)
from mediaflow.application.automation_workspace_commands import (
    AUTOMATION_DEFINITION_FORM_FIELDS,
    AutomationWorkspaceCommandService,
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
    durable_transfer_read_service,
)
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.application.library_file_operations import (
    LibraryFileOperationError,
    LibraryFileOperationHistoryService,
)
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_recovery_continuation import (
    ManualRecoveryContinuationService,
)
from mediaflow.application.media_discovery import MediaDiscoveryService
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
    TaskLifecycleService,
    bounded_failure_document,
    bounded_identity_path,
    is_files_worker_task_command,
    job_lifecycle_document,
    job_operator_document,
    manual_action_matrix_operator_document,
    manual_execution_operator_document,
    manual_execution_plan_evidence_operator,
    manual_intent_analysis_document,
    manual_intent_latest_plan_document,
    manual_intent_operator_document,
    manual_preview_operator_document,
    manual_step_error_document,
    require_cancellable,
    run_item_evidence_document,
    run_progress_document,
    run_record_document,
    scope_continuation_operator_document,
    scope_recovery_operator_document,
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
from mediaflow.application.resident_services import ResidentServiceService
from mediaflow.application.rules_object_analysis import RulesObjectAnalysisService
from mediaflow.application.rules_workspace_commands import (
    RULE_FAMILIES as RULE_WORKSPACE_FAMILIES,
)
from mediaflow.application.rules_workspace_commands import (
    RulesWorkspaceCommandService,
    rules_family_section,
)
from mediaflow.application.scope_continuation import (
    ScopeContinuationService,
    definition_occurrence_authority,
)
from mediaflow.application.storage_browser import (
    RuntimeFilesBrowserService,
    StorageBrowserError,
)
from mediaflow.application.system_settings import (
    SystemSettingsService,
    SystemSettingsValidationError,
)
from mediaflow.application.task_item_recovery import TaskItemRecoveryError, TaskItemRecoveryService
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
from mediaflow.domain.automation_settings import AutomationEngineSettingsError
from mediaflow.domain.configuration_management import (
    AutomationDefinitionSaveError,
    ConfigurationActivationConflict,
    ConfigurationFirstDraftConflict,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationVersionConflict,
    ManagedConfigurationStatus,
    ResourceLibrarySaveError,
    RulesWorkspaceSaveError,
    RuntimeConfigurationNotConfigured,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.direct_files import (
    MAX_DELETE_PATHS,
    MAX_TRANSFER_PATHS,
    DirectFileOperation,
    LibraryKind,
)
from mediaflow.domain.failure import failure_document
from mediaflow.domain.logging import LogLevel
from mediaflow.domain.manual_execution import ManualExecutionError, ManualExecutionStatus
from mediaflow.domain.manual_organize import (
    MAX_MANUAL_INTENT_ITEMS,
    ManualIntentError,
)
from mediaflow.domain.manual_organize_preview import ManualPreviewError
from mediaflow.domain.manual_safety import redact_manual_text, redact_manual_value
from mediaflow.domain.media_discovery import (
    TERMINAL_DISCOVERY_STATUSES,
    DiscoveryError,
    DiscoveryIncompleteReason,
    DiscoveryStatus,
    discovery_material_refusal,
)
from mediaflow.domain.metadata_correction import (
    MetadataCorrectionContinuation,
)
from mediaflow.domain.notification import (
    NotificationDeliveryConflict,
    NotificationDeliveryStatus,
)
from mediaflow.domain.operations_run import (
    DISCOVERY_COMMAND_LABEL,
    RECOVERY_PROBLEM_TYPES,
    RUN_DISPOSITIONS,
    RUN_RECORD_KINDS,
    OperationsRunRecord,
    OperationsRunStatus,
    OperationsRunTrigger,
    OperationsRunView,
    known_command_label,
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
from mediaflow.domain.scope_continuation import ScopeContinuationError
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal, SecurityAuditRecord
from mediaflow.domain.system_settings import (
    SystemSettingsEdit,
)
from mediaflow.domain.task_persistence import (
    FILES_DELETE_TASK_COMMAND,
    FILES_TRANSFER_TASK_COMMAND,
    ConfirmationStatus,
    PersistentTaskStatus,
    direct_command_task_command,
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
# The bounded Automation definition identity grammar shared by the definition
# reads and the execution-record selector: one URI-safe, length-bounded token.
_AUTOMATION_DEFINITION_FILTER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")

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


class _AutomationInventoryCursorStale(ValueError):
    """A definition page cursor whose exact boundary left the submitted population.

    This is a *recoverable* read condition: the inventory changed under a
    bounded page, so the operator gets an explicit stale-page read with a
    refresh action instead of a silently different page or a generic rejection.
    """


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
    #: The MediaLibrary-owned twin of ``direct_files`` (Slice 38 RO-5/RO-7).  It
    #: is a separate service pinned to the same immutable Active revision but
    #: constructed for the media library kind, so it can only ever resolve an
    #: enabled MediaLibrary and can never be handed a ResourceLibrary ID as
    #: authority (or the reverse).
    direct_media_files: DirectFileCommandService | None = None
    direct_transfers: DirectFileTransferService | None = None
    #: The MediaLibrary-owned twin of ``direct_transfers`` (Slice 38 RO-5/RO-6).
    #: It is a separate transfer service built on the media-kind direct-command
    #: service pinned to the same immutable Active revision, so a media
    #: transfer can only ever resolve MediaLibrary endpoints and one kind's
    #: manifest, evidence or claim can never be exchanged with the other.
    direct_media_transfers: DirectFileTransferService | None = None
    runtime_settings: dict[str, object] | None = None
    #: The saved Automation Task Definitions of this exact Active revision and a
    #: checker that proves one mutation-authorized Task still holds its live
    #: reusable authority.  Both belong to the revision, not to the process, so
    #: a continuation can never be advertised or admitted under another
    #: revision's definitions.
    automation_task_definitions: tuple = ()
    scope_continuation_authority: object | None = None


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

    #: The supported ResourceLibrary include/exclude/stability policy fields the
    #: Files Save/edit surface accepts alongside the five immutable basics.  A
    #: request that omits them preserves the exact existing object, so every
    #: legacy client keeps its current behavior.
    _RESOURCE_LIBRARY_POLICY_KEYS = ("includeRules", "excludeRules", "stability")

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
        media_discovery_service=None,
        automation_run_once_service=None,
        management_only: bool = False,
        worker_service: ProcessingWorkerService | None = None,
        webhook_transport: object | None = None,
        resident_services: ResidentServiceService | None = None,
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
        self._storage_adapters = dict(storage_adapters or {})
        self._configuration_service = configuration_service
        # A cursor minted by one API/CLI process must be verifiable by a later
        # one, so the shared runtime browser and the setup storage picker use
        # the same persisted internal key when no explicit secret is injected
        # (focused tests still inject their own).
        if storage_browser_cursor_secret is None and configuration_service is not None:
            storage_browser_cursor_secret = configuration_service.storage_browser_cursor_key()
        self._storage_browser_cursor_secret = storage_browser_cursor_secret
        self._maximum_active_jobs_override = maximum_active_jobs
        self._manual_intents = manual_intent_service
        if self._manual_intents is None and configuration_service is not None:
            self._manual_intents = ManualOrganizeIntentService(
                repository,
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
                configuration_service=configuration_service,
                metadata_provider_registry_factory=metadata_provider_registry_factory,
            )
        # The RO-6 bounded selected-scope discovery stage shares this API's
        # exact pinned Active revision and Storage adapters, and hands its frozen
        # source list to the same manual intent authority.  It grants no
        # execution permission and performs metadata-only Storage reads.
        self._media_discovery = media_discovery_service
        if self._media_discovery is None and self._manual_intents is not None:
            self._media_discovery = MediaDiscoveryService(
                repository,
                self._manual_intents,
                configuration_service=configuration_service,
                preview_service=self._manual_previews,
                storage_factory=lambda runtime, ids: runtime.create_storages(
                    external=self._storage_adapters, storage_ids=ids
                ),
            )
        # Definition-bound Run once composes the existing bounded discovery, the
        # existing manual intent admission and the existing exact Preview.  It
        # adds no second queue, no dummy Job and no mutation authority: only the
        # separate explicit execution confirmation can reach OrganizerExecutor.
        self._automation_run_once = automation_run_once_service
        if (
            self._automation_run_once is None
            and self._media_discovery is not None
            and self._manual_previews is not None
        ):
            self._automation_run_once = AutomationRunOnceService(
                self._media_discovery,
                self._manual_previews,
                repository=repository,
                configuration_service=configuration_service,
            )
        if self._automation_run_once is not None:
            binder = getattr(self._automation_run_once, "bind_execution_authority", None)
            if callable(binder):
                binder(
                    repository,
                    configuration_service,
                    _CurrentConfiguredPermissionAuthority(self._principals, configuration_service),
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
        # The V2 rules workspace reuses that same application service, so a typed
        # Save cannot diverge from V1/API/CLI normalization, validation, audit,
        # concurrency or checked activation semantics; it only composes the focused
        # object change and delegates publication.
        self._rules_workspace = (
            RulesWorkspaceCommandService(self._configuration_objects)
            if self._configuration_objects is not None
            else None
        )
        # RO-4's object-scoped analysis reuses the exact candidate composition and
        # the production engines through this one shared boundary, so a local test
        # cannot diverge from Save/Preview semantics or become a second authority.
        self._rules_analysis = (
            RulesObjectAnalysisService(self._rules_workspace, self._configuration_objects)
            if self._rules_workspace is not None and self._configuration_objects is not None
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
        # The focused four-field Automation engine settings command and its
        # per-consumer adoption readback.  It composes the same managed
        # publication authority as every other checked Save and reads adoption
        # only from each resident process's own durable report.
        self._automation_settings = (
            AutomationSettingsService(
                configuration_service,
                resident_repository=repository,
                expected_schema_version=SCHEMA_VERSION,
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
            target_resolver=(
                self._notification_recovery_targets if configuration_service else None
            ),
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
        # Resident-service presence is optional so an embedded/WSGI deployment
        # that constructs the API without a durable database still answers the
        # configuration surfaces it always supported.
        self._resident_services = resident_services
        snapshot_validator = (
            configuration_service.validate_runtime_snapshot
            if configuration_service is not None
            else recovery_snapshot_validator
        )
        self._checkpoint_service = ProcessingCheckpointService(
            repository,
            snapshot_validator=snapshot_validator,
        )
        self._task_item_recovery = TaskItemRecoveryService(
            repository,
            checkpoint_service=self._checkpoint_service,
            configuration_service=configuration_service,
            metadata_provider_registry_factory=metadata_provider_registry_factory,
        )
        # The shared admission boundary for a Web "Continue" of one durably
        # paused Task's exact remaining admitted scope.  It performs zero
        # Storage work and revalidates the live pin, the exact durable Task state
        # and the applicable execution authority before queueing anything.
        self._scope_continuations = ScopeContinuationService(
            repository,
            snapshot_validator=snapshot_validator,
            # The live authority checker is resolved per binding below, because
            # the saved definitions it validates against belong to the exact
            # Active revision the request is served under.
            mutation_authority=None,
        )
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
        from mediaflow.application.automation_execution_intent import (
            assert_schedule_continuity,
            live_definition,
            resolve_principal,
        )

        if configuration_service is not None:
            configuration_service.bind_automation_publication_authority(
                _CurrentConfiguredPermissionAuthority(self._principals, configuration_service)
            )
        self._unattended_grants = UnattendedExecutionGrantService(
            repository,
            discovery_service=self._media_discovery,
            preview_service=self._manual_previews,
            permission_authority=_CurrentConfiguredPermissionAuthority(
                self._principals, configuration_service
            ),
            publication_principal_resolver=(
                lambda job, definition: resolve_principal(configuration_service, job, definition)
            )
            if configuration_service is not None
            else None,
            live_intent_checker=(
                lambda job, definition: assert_schedule_continuity(
                    configuration_service, job, definition
                )
            )
            if configuration_service is not None
            else None,
            live_definition_resolver=(
                lambda definition_id: live_definition(configuration_service, definition_id)
            )
            if configuration_service is not None
            else None,
        )
        self._automation_occurrences = AutomationDefinitionOccurrenceService(repository)
        self._automation_occurrences.attach_unattended_grant_service(self._unattended_grants)
        self._automation_occurrences.attach_checkpoint_service(self._checkpoint_service)
        # The V2 Automation workspace reuses the same managed-object authority as
        # V1/API/CLI, so one checked Save cannot diverge from normalization,
        # validation, audit, concurrency or checked activation semantics; it only
        # composes the focused definition change and delegates publication.
        self._automation_workspace = (
            AutomationWorkspaceCommandService(
                self._configuration_objects,
                unattended_grants=self._unattended_grants,
            )
            if self._configuration_objects is not None
            else None
        )
        if self._automation_workspace is not None:
            # The workspace's historical definition resolution reads the
            # definition's newest durable occurrence through this bounded
            # reader so a retained occurrence pins the exact published
            # revision its run used.  It is a read-only dependency.
            self._automation_workspace.bind_occurrence_store(
                lambda definition_id: self._automation_occurrences.latest(definition_id)
            )
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
                    # The API composition root passes the real runtime schema
                    # explicitly so readiness here can never drift from the
                    # database this process actually opened.
                    runtime_schema_version=SCHEMA_VERSION,
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
        except LibraryFileOperationError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "library-file-operations",
                "conflict" if error.status < 500 else "error",
                error.status,
            )
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details={"sideEffects": "none", "retrySafe": error.status >= 500},
            )
        except AutomationSettingsPublicationError as error:
            # Focused engine-settings publication failure: the four-field scope,
            # preserved previous Active and bounded next action stay explicit.
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "automation-engine-settings",
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
        except AutomationEngineSettingsError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "automation-engine-settings",
                "validation_failed",
                422,
            )
            return self._error(
                start_response,
                422,
                error.code,
                str(error),
                details={
                    **error.as_detail(),
                    "durableState": "active_unchanged",
                    "sideEffects": "none",
                    "retrySafe": True,
                },
            )
        except AutomationDefinitionSaveError as error:
            # Handled before the generic page-local Save family because the
            # Automation error adds the affected definition/stage/authority state
            # the operator needs to continue; the bounded details stay secret-free.
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "automation-definition-save",
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
        except RulesWorkspaceSaveError as error:
            # Handled before the generic page-local Save family because the
            # rules-workspace error adds the affected object/stage identity that
            # the operator needs to continue; the bounded details stay secret-free.
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "rules-workspace-save",
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
            is_library_save = self._is_page_local_save(path, method)
            details = {
                key: value
                for key, value in {
                    "revisionId": error.revision_id,
                    "currentRevisionId": error.current_revision_id,
                    "currentVersion": error.current_version,
                    "currentDigest": error.current_digest,
                    "durableState": (
                        "active_winner_preserved"
                        if is_library_save and error.current_revision_id
                        else (
                            "draft_preserved_active_unchanged"
                            if error.current_revision_id
                            else "draft_preserved"
                        )
                    ),
                    "candidateState": ("not_published" if is_library_save else None),
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
            is_library_save = self._is_page_local_save(path, method)
            details = {
                key: value
                for key, value in {
                    "revisionId": error.revision_id,
                    "currentVersion": error.current_version,
                    "currentDigest": error.current_digest,
                    "durableState": (
                        "active_winner_preserved"
                        if is_library_save and error.current_version is not None
                        else error.durable_state or "draft_preserved"
                    ),
                    "candidateState": ("not_published" if is_library_save else None),
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
            is_library_save = self._is_page_local_save(path, method)
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
                        "no_active_configuration" if is_library_save else "no_workflow_work_created"
                    ),
                    "candidateState": "not_saved" if is_library_save else None,
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
            is_library_save = self._is_page_local_save(path, method)
            active_unavailable_state = (
                "no_active_configuration"
                if is_library_save and error.reason == "active_missing"
                else "managed_active_unavailable"
            )
            next_action = (
                (
                    "activate a valid managed configuration, then retry Save"
                    if error.reason == "active_missing"
                    else "repair or replace the unavailable Active configuration, then retry Save"
                )
                if is_library_save
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
                    "candidateState": "not_saved" if is_library_save else None,
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
        except TaskItemRecoveryError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "task-item-recovery",
                "conflict" if error.status == 409 else "error" if error.status >= 500 else "denied",
                error.status,
            )
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details={"sideEffects": "none", "nextAction": error.next_action},
            )
        except _AutomationInventoryCursorStale as error:
            # A bounded page whose exact boundary definition left the submitted
            # population is a recoverable stale read, not a malformed request:
            # the operator gets the truthful condition and a refresh action.
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "request",
                "error",
                409,
            )
            return self._error(
                start_response,
                409,
                "stale_page",
                redact_manual_text(error),
                details={
                    "durableState": "inventory_changed_under_cursor",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "refresh the Automation inventory to read the current page "
                        "boundary; no work, Draft or grant was created"
                    ),
                },
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
            # One bounded, secret-free diagnostic only: the operator-facing JSON
            # error and the durable audit row already carry the request identity
            # and the exact route.  The raw exception chain may contain
            # credential-shaped content, so it is never written to any log or
            # stream (AGENTS logging invariant, REQ-LOG-003).
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
        # Unknown namespaces never resolve Active configuration or adapters.
        supported_roots = {
            "auth",
            "automation",
            "classification-reviews",
            "configuration",
            "confirmations",
            "dashboard",
            "files",
            "jobs",
            "logs",
            "management",
            "manual-execution-authorizations",
            "manual-executions",
            "manual-intents",
            "manual-previews",
            "manual-recovery-links",
            "manual-recovery-preparations",
            "media-libraries",
            "metadata-corrections",
            "metadata-reviews",
            "notifications",
            "operations",
            "recognition-reviews",
            "recovery",
            "recovery-batches",
            "resource-libraries",
            "schedules",
            "security-audit",
            "storage",
            "storages",
            "system",
            "tasks",
            "workers",
        }
        supported_operations = {
            "automation",
            "manual-actions",
            "notifications",
            "organize",
            "rules",
            "runs",
            "storage-management",
        }
        if (
            len(parts) < 3
            or parts[2] not in supported_roots
            or (
                parts[2] == "operations"
                and (len(parts) < 4 or parts[3] not in supported_operations)
            )
        ):
            return self._error(start_response, 404, "not_found", "route was not found")
        job_submission = None
        if parts == ["api", "v1", "jobs"] and method == "POST":
            job_submission = self._document(environ)
            command = job_submission.get("command")
            self._require(
                principal,
                ApiPermission.REMOTE_EXECUTE
                if command == "organize"
                else ApiPermission.SUBMIT_DRY_RUN,
            )
            if command not in {AutomationCommand.ORGANIZE.value}:
                raise ValueError("unsupported job command")
        configuration_route = parts[:3] == ["api", "v1", "configuration"]
        automation_definition_route = parts[:4] == [
            "api",
            "v1",
            "automation",
            "task-definitions",
        ]
        management_readiness_route = parts == ["api", "v1", "management", "readiness"]
        task_read_route = parts[:3] == ["api", "v1", "tasks"] and method == "GET"
        # The unified run inventory reads durable repository rows only: it
        # resolves no configuration, so a missing or unreadable current Active
        # must never hide historical runs.  Like the Task read it shares the
        # same durable basis, it skips the Active refresh entirely instead of
        # failing closed on a route that needs no binding.
        operations_runs_read_route = (
            len(parts) >= 4
            and parts[:3] == ["api", "v1", "operations"]
            and parts[3] == "runs"
            and method == "GET"
        )
        worker_route = parts[:3] == ["api", "v1", "workers"]
        # The originating library's ordinary file-operation history, one exact
        # operation and the deep-link origin resolution are durable reads of
        # already-admitted work: they resolve no configuration, so a missing,
        # unreadable, disabled or removed current Active must never hide them.
        library_file_operation_route = method == "GET" and (
            (
                len(parts) == 5
                and tuple(parts[:3])
                in {
                    ("api", "v1", "resource-libraries"),
                    ("api", "v1", "media-libraries"),
                }
                and parts[4] == "file-operations"
            )
            or (
                len(parts) == 7
                and tuple(parts[:3])
                in {
                    ("api", "v1", "resource-libraries"),
                    ("api", "v1", "media-libraries"),
                }
                and parts[4:6] == ["files", "operations"]
            )
            or (
                len(parts) == 5
                and parts[:3] == ["api", "v1", "files"]
                and parts[3] == "operation-origin"
            )
            or (
                len(parts) == 4
                and tuple(parts[:3])
                in {
                    ("api", "v1", "resource-libraries"),
                    ("api", "v1", "media-libraries"),
                }
                and parts[3] == "operation-origins"
            )
        )
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
            and not operations_runs_read_route
            and not library_file_operation_route
        ):
            # Transfer observation is a durable read of an already-admitted
            # task.  Keep the last published binding so a missing current
            # Active cannot hide valid older pinned progress; admission and
            # other workflow routes still refresh and fail closed normally.
            transfer_observation = (
                method == "GET"
                and len(parts) in {7}
                and parts[4:6] == ["files", "transfers"]
                and tuple(parts[:3])
                in {
                    ("api", "v1", "resource-libraries"),
                    ("api", "v1", "media-libraries"),
                }
            )
            if not transfer_observation:
                binding = self._refresh_configuration_binding()
            else:
                # One progress read converges back to the live binding as soon
                # as a valid Active exists again, and a lost or unreadable
                # Active never turns into a lost durable view: this process
                # keeps its last published binding (or none at all after a
                # restart), and the route below still answers from durable
                # Task state.
                try:
                    binding = self._refresh_configuration_binding()
                except Exception:
                    binding = self._runtime_binding
        # --- V2 Preview operations routes (bounded, server-bound) ---
        if parts == ["api", "v1", "operations", "manual-actions"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            return self._manual_action_matrix(start_response, environ, principal, binding)
        # --- V2 Operations: manual Organize intent, exact Preview, one Execute action ---
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
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6] == "recovery"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "task item recovery detail")
            value = self._task_item_recovery.detail(parts[3], parts[5])
            if self._manual_recovery is not None:
                value["manualRecoveryLink"] = self._manual_recovery.discovery_for_source_item(
                    parts[3], parts[5]
                )
                value["manualRecoveryPreparation"] = (
                    self._manual_recovery.discovery_for_preparation(parts[3], parts[5])
                )
                value["manualRecoveryAvailable"] = self._manual_recovery.supports_source_item(
                    parts[3], parts[5]
                )
                value["manualRecoveryAnalysisReady"] = (
                    self._manual_recovery.analysis_summary_available(parts[3], parts[5])
                )
            else:
                value["manualRecoveryAvailable"] = False
                value["manualRecoveryAnalysisReady"] = False
            return self._response(start_response, 200, redact_manual_value(value))
        if (
            len(parts) == 7
            and parts[:5] == ["api", "v1", "operations", "organize", "intents"]
            and parts[6] == "previews"
            and method == "POST"
        ):
            # The intent-page analysis entry.  The request only records one
            # versioned durable stage on the intent's own organize run; the
            # resident Worker runs the complete zero-mutation analysis and
            # links the exact plan through the same atomic publication as
            # every other run.  A slow Provider never blocks this request, and
            # no execution authority is created here.
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            if self._manual_intents is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual intent service is unavailable",
                )
            self._require_empty_query(environ, "operations organize intent analysis")
            document = self._document(environ)
            if set(document) != {"expectedVersion"}:
                raise ValueError(
                    "operations organize intent analysis requires only the current intent version"
                )
            expected_version = document["expectedVersion"]
            if (
                isinstance(expected_version, bool)
                or not isinstance(expected_version, int)
                or expected_version < 1
            ):
                raise ValueError(
                    "operations organize intent analysis expectedVersion must be a positive integer"
                )
            service = getattr(self, "_media_discovery", None)
            if service is None or not callable(getattr(service, "begin_intent_analysis", None)):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "the durable organize analysis service is unavailable",
                    details={
                        "durableState": "no_analysis_started",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore a valid Active runtime and the bounded organize analysis "
                            "services, then request the summary again"
                        ),
                    },
                )
            try:
                service.begin_intent_analysis(
                    parts[5],
                    actor=principal.principal_id,
                    expected_intent_version=expected_version,
                )
            except DiscoveryError as error:
                return self._discovery_step_error(start_response, error)
            except ManualIntentError as error:
                return self._manual_step_error(start_response, error)
            try:
                intent = self._manual_intents.get(parts[5])
            except ManualIntentError as error:
                return self._manual_step_error(start_response, error)
            operator_document = self._organize_intent_document(intent, principal)
            return self._response(start_response, 201, operator_document)
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
        if (
            len(parts) == 7
            and parts[:5] == ["api", "v1", "operations", "organize", "previews"]
            and parts[6] == "admission"
            and method == "GET"
        ):
            # The exact admission-outcome reconciliation read for one reviewed
            # Preview.  After a transport error, lost response or malformed
            # answer to Execute, the operator may only prove what the durable
            # admission records already say: the submitted selection either is
            # exactly admitted, is contradicted by a non-equivalent durable
            # admission, or has no admitted execution at all.  This GET admits
            # no work, mints or reissues no authority, and never replays an
            # uncertain mutation; only the exact submitted reviewed selection
            # binds the answer, and the reading principal owns that evidence.
            self._require(principal, ApiPermission.READ)
            if self._manual_execution is None or not callable(
                getattr(self._manual_execution, "admission_outcome", None)
            ):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "manual organize admission reconciliation is unavailable",
                    details={
                        "durableState": "admission_unknown",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore the manual Organize execution service, then repeat this "
                            "bounded read; the submitted command is never replayed"
                        ),
                    },
                )
            values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            allowed = {"itemIds", "expectedIntentVersion", "allowOverwrite", "allowSourceCleanup"}
            if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
                raise ValueError(
                    "operations organize admission reconciliation query accepts itemIds, "
                    "expectedIntentVersion, allowOverwrite and allowSourceCleanup once"
                )
            raw_items = values.get("itemIds", [""])[0]
            item_ids = [value for value in raw_items.split(",") if value.strip()]
            if (
                not item_ids
                or len(item_ids) > self._manual_execution.MAX_ITEMS
                or len(set(item_ids)) != len(item_ids)
                or any(len(value.strip()) > 128 for value in item_ids)
            ):
                raise ValueError(
                    "operations organize admission reconciliation requires a bounded itemIds list"
                )
            raw_version = values.get("expectedIntentVersion", [""])[0]
            if not raw_version.isdigit() or int(raw_version) < 1:
                raise ValueError(
                    "operations organize admission reconciliation expectedIntentVersion must be "
                    "a positive integer"
                )
            expected_intent_version = int(raw_version)
            effects: dict[str, bool] = {}
            for name in ("allowOverwrite", "allowSourceCleanup"):
                raw = values.get(name, [""])[0]
                if raw == "":
                    raise ValueError(
                        "operations organize admission reconciliation requires explicit "
                        f"{name} boolean"
                    )
                if raw not in {"true", "false"}:
                    raise ValueError(
                        f"operations organize admission reconciliation {name} must be true or false"
                    )
                effects[name] = raw == "true"
            try:
                document = self._manual_execution.admission_outcome(
                    parts[5],
                    item_ids=item_ids,
                    intent_version=expected_intent_version,
                    actor=principal.principal_id,
                    allow_overwrite=effects["allowOverwrite"],
                    allow_source_cleanup=effects["allowSourceCleanup"],
                )
            except ManualExecutionError as error:
                return self._manual_step_error(start_response, error)
            document["journey"] = "organize"
            return self._response(start_response, 200, document)
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
            len(parts) == 8
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6:8] == ["recovery", "decision"]
            and method == "POST"
        ):
            self._require_empty_query(environ, "task item review decision")
            document = self._document(environ)
            kind = document.get("kind")
            permission = {
                "recognition": ApiPermission.RESOLVE_RECOGNITION_REVIEW,
                "metadata": ApiPermission.RESOLVE_METADATA_REVIEW,
                "metadata_correction": ApiPermission.RESOLVE_METADATA_REVIEW,
                "classification": ApiPermission.RESOLVE_CLASSIFICATION_REVIEW,
                "conflict": ApiPermission.RESOLVE_CONFIRMATION,
            }.get(kind)
            if permission is None:
                raise ValueError("task item decision kind is invalid")
            self._require(principal, permission)
            fields = {
                "recognition": {"kind", "expectedCheckpointVersion", "recognitionTypeId", "note"},
                "metadata": {"kind", "expectedCheckpointVersion", "candidateRank", "note"},
                "metadata_correction": {
                    "kind",
                    "expectedCheckpointVersion",
                    "query",
                    "year",
                    "mediaType",
                    "providerId",
                    "note",
                },
                "classification": {"kind", "expectedCheckpointVersion", "choiceRank", "note"},
                "conflict": {
                    "kind",
                    "expectedCheckpointVersion",
                    "strategy",
                    "confirmOverwrite",
                    "note",
                },
            }[kind]
            if set(document).difference(fields) or not {
                "kind",
                "expectedCheckpointVersion",
            }.issubset(document):
                raise ValueError("task item decision fields are invalid")
            expected = document["expectedCheckpointVersion"]
            if not isinstance(expected, str) or not expected.strip():
                raise ValueError("expectedCheckpointVersion is required")
            decision_fields = {
                "recognitionTypeId": "recognition_type_id",
                "candidateRank": "candidate_rank",
                "choiceRank": "choice_rank",
                "mediaType": "media_type",
                "providerId": "provider_id",
                "confirmOverwrite": "confirm_overwrite",
            }
            decision = {
                decision_fields.get(key, key): value
                for key, value in document.items()
                if key not in {"kind", "expectedCheckpointVersion"}
            }
            result = self._task_item_recovery.resolve(
                parts[3],
                parts[5],
                kind=kind,
                expected_checkpoint_version=expected,
                actor=principal.principal_id,
                decision=decision,
            )
            recovery = self._task_item_recovery.detail(parts[3], parts[5])
            if self._manual_recovery is not None:
                recovery["manualRecoveryLink"] = self._manual_recovery.discovery_for_source_item(
                    parts[3], parts[5]
                )
                recovery["manualRecoveryPreparation"] = (
                    self._manual_recovery.discovery_for_preparation(parts[3], parts[5])
                )
                recovery["manualRecoveryAvailable"] = self._manual_recovery.supports_source_item(
                    parts[3], parts[5]
                )
                recovery["manualRecoveryAnalysisReady"] = (
                    self._manual_recovery.analysis_summary_available(parts[3], parts[5])
                )
            else:
                recovery["manualRecoveryAvailable"] = False
                recovery["manualRecoveryAnalysisReady"] = False
            return self._response(
                start_response,
                200,
                redact_manual_value(
                    {
                        **recovery,
                        "decision_kind": kind,
                        "decision_result": self._value(result),
                    }
                ),
            )
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6:8] == ["recovery", "metadata-search"]
            and method == "POST"
        ):
            self._require(principal, ApiPermission.RESOLVE_METADATA_REVIEW)
            self._require_empty_query(environ, "task item Metadata search")
            document = self._document(environ)
            if set(document) != {"expectedCheckpointVersion", "query", "mediaType"}:
                raise ValueError("task item Metadata search fields are invalid")
            value = self._task_item_recovery.metadata_search(
                parts[3],
                parts[5],
                expected_checkpoint_version=document["expectedCheckpointVersion"],
                query=document["query"],
                media_type=document["mediaType"],
            )
            return self._response(start_response, 200, redact_manual_value(value))
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
        if parts == ["api", "v1", "operations", "organize", "discoveries"] and method == "GET":
            # The bounded operator list of this principal's own admitted
            # discoveries.  It never publishes a claim token, a configuration
            # digest or a raw Storage path.
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "operations organize discoveries")
            service = getattr(self, "_media_discovery", None)
            if service is None:
                return self._discovery_unavailable(start_response)
            values = service.list(actor=principal.principal_id, limit=50)
            return self._response(
                start_response,
                200,
                {
                    "journey": "discovery",
                    "items": [
                        self._discovery_document(value, principal, binding, include_sources=False)
                        for value in values
                    ],
                    "total": len(values),
                    "limit": 50,
                    "sideEffects": "none",
                },
            )
        if (
            len(parts) == 6
            and parts[:5] == ["api", "v1", "operations", "organize", "discoveries"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            # The detail read optionally names the caller's own admission request
            # identity, so a request that converged on this same durable work can
            # read back *its own* admitted/existing/refused result instead of the
            # first request's evidence.
            query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if not query:
                request_id = None
            elif set(query) == {"requestId"} and len(query["requestId"]) == 1:
                request_id = query["requestId"][0]
            else:
                raise ValueError(
                    "operations organize discovery detail accepts only one optional requestId"
                )
            service = getattr(self, "_media_discovery", None)
            if service is None:
                return self._discovery_unavailable(start_response)
            try:
                value = service.get(parts[5])
            except DiscoveryError as error:
                return self._discovery_step_error(start_response, error)
            return self._response(
                start_response,
                200,
                self._discovery_document(value, principal, binding, requested_by=request_id),
            )
        if (
            len(parts) == 7
            and parts[:5] == ["api", "v1", "operations", "organize", "discoveries"]
            and parts[6] in {"pause", "cancel", "resume"}
            and method == "POST"
        ):
            # Cooperative, versioned control.  Pause and cancel only record a
            # request the resident Worker honours at its next safe boundary;
            # they never grant execution authority and never interrupt an
            # in-flight provider call.
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            self._require_empty_query(environ, "operations organize discovery control")
            service = getattr(self, "_media_discovery", None)
            if service is None:
                return self._discovery_unavailable(start_response)
            document = self._document(environ)
            if set(document) != {"expectedVersion"}:
                raise ValueError(
                    "operations organize discovery control requires only expectedVersion"
                )
            action = parts[6]
            try:
                if action == "pause":
                    value = service.request_pause(
                        parts[5],
                        actor=principal.principal_id,
                        expected_version=document["expectedVersion"],
                    )
                elif action == "cancel":
                    value = service.request_cancel(
                        parts[5],
                        actor=principal.principal_id,
                        expected_version=document["expectedVersion"],
                    )
                else:
                    value = service.resume(
                        parts[5],
                        actor=principal.principal_id,
                        expected_version=document["expectedVersion"],
                    )
            except DiscoveryError as error:
                return self._discovery_step_error(start_response, error)
            return self._response(
                start_response, 200, self._discovery_document(value, principal, binding)
            )
        if (
            len(parts) == 7
            and parts[:5] == ["api", "v1", "operations", "organize", "discoveries"]
            and parts[6] == "finalize"
            and method == "POST"
        ):
            # Freeze the durable discovered source list and hand it to the
            # existing manual intent admission.  The resulting intent still
            # requires a separate exact Preview and an explicitly confirmed
            # execution; discovery itself never grants mutation authority.
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            self._require_empty_query(environ, "operations organize discovery finalize")
            service = getattr(self, "_media_discovery", None)
            if service is None:
                return self._discovery_unavailable(start_response)
            document = self._document(environ)
            if set(document) != {"expectedVersion"}:
                raise ValueError(
                    "operations organize discovery finalize requires only expectedVersion"
                )
            try:
                value = service.finalize(
                    parts[5],
                    actor=principal.principal_id,
                    expected_version=document["expectedVersion"],
                )
            except DiscoveryError as error:
                return self._discovery_step_error(start_response, error)
            return self._response(
                start_response, 201, self._discovery_document(value, principal, binding)
            )
        if (
            len(parts) == 7
            and parts[:5] == ["api", "v1", "operations", "organize", "discoveries"]
            and parts[6] == "analyze"
            and method == "POST"
        ):
            # Re-enter the durable analysis stage after an operator correction
            # on the linked intent.  This records one versioned request only;
            # the resident Worker re-runs the complete zero-mutation analysis
            # under the same pinned configuration and links a new exact
            # Preview.  It grants no execution authority.
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            self._require_empty_query(environ, "operations organize discovery analysis")
            service = getattr(self, "_media_discovery", None)
            if service is None:
                return self._discovery_unavailable(start_response)
            document = self._document(environ)
            if set(document) != {"expectedVersion"}:
                raise ValueError(
                    "operations organize discovery analysis requires only expectedVersion"
                )
            try:
                value = service.request_analysis(
                    parts[5],
                    actor=principal.principal_id,
                    expected_version=document["expectedVersion"],
                )
            except DiscoveryError as error:
                return self._discovery_step_error(start_response, error)
            return self._response(
                start_response, 200, self._discovery_document(value, principal, binding)
            )
        if (
            len(parts) == 7
            and parts[:5] == ["api", "v1", "operations", "automation", "task-definitions"]
            and parts[6] == "run-once"
            and method in {"GET", "POST"}
        ):
            # Definition-bound Run once on the V2 operator surface.  The POST
            # admits (or reconciles) one durable discovery derived from the
            # *published definition's own* ResourceLibrary/sub-scope; the GET
            # reads it back.  Neither the browser nor the URL supplies the
            # manifest, so no file picker and no hand-selected subset is
            # involved, and no execution authority is created here.
            return self._automation_run_once_projection(
                parts[5], method, environ, start_response, principal
            )
        if (
            len(parts) == 5
            and parts[:4] == ["api", "v1", "operations", "automation"]
            and parts[4] == "run-once"
            and method == "GET"
        ):
            # The bounded list of this principal's own definition-bound Run
            # once admissions, so a reload or reconnect restores every durable
            # run without re-walking sources.
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "automation Run once list")
            service = getattr(self, "_automation_run_once", None)
            if service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "definition Run once is unavailable",
                )
            values = service.list(actor=principal.principal_id, limit=50)
            items = []
            for value in values:
                if getattr(value, "definition_origin", None) is None and not getattr(
                    value, "run_once", False
                ):
                    continue
                items.append(service.document(value))
            return self._response(
                start_response,
                200,
                {
                    "journey": "automation-run-once",
                    "items": items,
                    "total": len(items),
                    "limit": 50,
                    "sideEffects": "none",
                },
            )
        if (
            len(parts) == 6
            and parts[:4] == ["api", "v1", "operations", "automation"]
            and parts[4] == "run-once"
            and method == "GET"
        ):
            return self._automation_run_once_detail_projection(
                parts[5], None, method, environ, start_response, principal
            )
        if (
            len(parts) == 7
            and parts[:4] == ["api", "v1", "operations", "automation"]
            and parts[4] == "run-once"
            and method == "POST"
            and parts[6] in {"pause", "cancel", "resume", "finalize"}
        ):
            return self._automation_run_once_detail_projection(
                parts[5], parts[6], method, environ, start_response, principal
            )
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
            active, _raw, definition, historical = self._automation_definition_context_historical(
                environ, parts[4]
            )
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
                    "historicalState": "removed" if historical else None,
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
            _active, _raw, _definition, _historical = (
                self._automation_definition_context_historical(environ, parts[4])
            )
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
            # Grant, revocation and focused Automation publication (including
            # removal) share one serialization boundary: a removal revokes
            # authority and publishes inside the same lock, so a concurrent
            # legitimate grant cannot slip live authority in between.
            with self._runtime_binding_lock:
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
                        next_action=(
                            "repair the ResourceLibrary reference and run a fresh Preview"
                        ),
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
                    storage_id=resource.get("storageId"),
                )
                eligibility = self._unattended_grants.project_eligibility(
                    definition,
                    configuration_snapshot_id=active.revision_id,
                    configuration_snapshot_digest=active.digest,
                    configuration_snapshot_version=active.version,
                    storage_id=resource.get("storageId"),
                    max_items_per_run=grant.max_items_per_run,
                    principal_id=grant.granting_principal,
                )
                grant_projection = self._unattended_grants.project(
                    definition,
                    configuration=active.summary(),
                    grant=grant,
                )
                response_document = {
                    "configuration": active.summary(),
                    "definition": raw,
                    "grant": grant_projection,
                    "unattendedExecutionGrant": grant_projection,
                    "grantEligibility": eligibility,
                    "previewEligibility": eligibility,
                }
            return self._response(start_response, 201, response_document)
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
            with self._runtime_binding_lock:
                _active, _raw, _definition, _historical = (
                    self._automation_definition_context_historical(environ, parts[4])
                )
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
                response_document = {
                    "definitionId": parts[4],
                    "grant": grant.document(),
                    "unattendedExecutionGrant": self._unattended_grants.project(
                        _definition,
                        configuration=_active.summary(),
                        grant=grant,
                    ),
                }
            return self._response(start_response, 200, response_document)
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
            historical = False
            if item is None:
                # Retained history: resolve a removed definition from its newest
                # published non-Active revision backed by durable activation
                # evidence (pinned by the retained occurrence when one exists),
                # so the durable detail read stays truthful after removal and
                # restart and never substitutes an unpublished Draft candidate.
                projection = (
                    self._automation_workspace.historical_definition(
                        parts[4],
                        occurrence=self._automation_occurrences.latest(parts[4]),
                    )
                    if self._automation_workspace is not None
                    else None
                )
                if projection is None:
                    raise LookupError(f"automationTaskDefinitions {parts[4]!r} was not found")
                item = projection.get("definition")
                historical = True
            item = self._automation_occurrences.project_definition(
                item,
                configuration=active.summary(),
            )
            if historical:
                item["definitionState"] = "historical"
                item["historicalState"] = "removed"
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
                # Retained history: a removed definition's occurrence history
                # stays readable from durable published evidence, never from an
                # unpublished Draft candidate.
                projection = (
                    self._automation_workspace.historical_definition(
                        parts[4],
                        occurrence=self._automation_occurrences.latest(parts[4]),
                    )
                    if self._automation_workspace is not None
                    else None
                )
                if projection is None:
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
                    "historicalState": "removed" if definition is None else None,
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
            return self._response(start_response, 200, response)
        if parts[:5] in (
            ["api", "v1", "operations", "automation", "task-definitions"],
            ["api", "v1", "operations", "automation", "metrics"],
            ["api", "v1", "operations", "automation", "records"],
        ) and method in {"GET", "POST", "PUT", "DELETE"}:
            return self._automation_operations_projection(
                parts, method, environ, start_response, principal
            )
        if parts[:5] == [
            "api",
            "v1",
            "operations",
            "automation",
            "definitions",
        ] and method in {"GET", "POST", "PUT", "DELETE"}:
            return self._automation_definition_focused_projection(
                parts, method, environ, start_response, principal
            )
        if parts == [
            "api",
            "v1",
            "operations",
            "automation",
            "settings",
        ] and method in {"GET", "PUT"}:
            return self._automation_engine_settings_projection(
                method, environ, start_response, principal
            )
        if parts[:4] == ["api", "v1", "operations", "notifications"] and method in {
            "GET",
            "POST",
        }:
            return self._notification_operations_projection(
                parts, method, environ, start_response, principal
            )
        if parts[:4] == ["api", "v1", "operations", "storage-management"] and method in {
            "GET",
            "POST",
        }:
            return self._storage_operations_projection(
                parts, method, environ, start_response, principal
            )
        if parts[:4] == ["api", "v1", "operations", "runs"]:
            return self._operations_runs_projection(
                parts, method, environ, start_response, principal
            )
        if parts[:4] == ["api", "v1", "operations", "rules"]:
            return self._rules_operations_projection(
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
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "edit"
            and method == "GET"
        ):
            self._require_empty_query(environ, "ResourceLibrary edit projection")
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration object service is unavailable",
                )
            return self._response(
                start_response,
                200,
                self._configuration_objects.resource_library_edit_projection(parts[3]),
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "resource-libraries"] and method == "PUT":
            self._require_empty_query(environ, "ResourceLibrary edit")
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
            policy_keys = set(self._RESOURCE_LIBRARY_POLICY_KEYS)
            allowed = {
                "resourceLibraryId",
                "name",
                "enabled",
                "storageId",
                "storagePath",
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
            } | policy_keys
            required = allowed.difference(policy_keys)
            if (
                not required.issubset(document)
                or set(document).difference(allowed)
                or document["resourceLibraryId"] != parts[3]
            ):
                raise ValueError(
                    "ResourceLibrary edit requires immutable matching ID and Active identity"
                )
            candidate = {
                "id": parts[3],
                "name": document["name"],
                "enabled": document["enabled"],
                "storageId": document["storageId"],
                "storagePath": document["storagePath"],
            }
            for key in policy_keys:
                if key in document:
                    candidate[key] = document[key]
            prepared: list[_ApiRuntimeBinding] = []
            with self._runtime_binding_lock:
                self._refresh_configuration_binding_locked()
                try:
                    revision = self._configuration_objects.save_resource_library(
                        candidate,
                        actor=principal.principal_id,
                        before_publish=lambda rev: prepared.append(
                            self._prepare_runtime_binding_for_revision(rev)
                        ),
                        expected_revision_id=document["expectedRevisionId"],
                        expected_version=document["expectedVersion"],
                        expected_digest=document["expectedDigest"],
                        edit=True,
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
                    )
                self._publish_runtime_binding(prepared[0])
            resource = next(
                item
                for item in self._configuration_objects._canonical_objects(
                    revision.document, "resourceLibraries"
                )
                if item.get("id") == parts[3]
            )
            return self._response(
                start_response,
                200,
                {
                    "resourceLibrary": {
                        key: resource.get(key)
                        for key in ("id", "name", "storageId", "storagePath", "enabled")
                    }
                    | {
                        key: resource.get(key)
                        for key in self._RESOURCE_LIBRARY_POLICY_KEYS
                        if key in resource
                    },
                    "active": revision.summary(),
                    "configuration": {
                        "authority": "MANAGED",
                        "revisionId": revision.revision_id,
                        "version": revision.version,
                        "digest": revision.digest,
                    },
                    "sideEffects": "configuration_only",
                },
            )
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
            policy_keys = set(self._RESOURCE_LIBRARY_POLICY_KEYS)
            required = {
                "resourceLibraryId",
                "name",
                "enabled",
                "storageId",
                "storagePath",
            }
            allowed = required | policy_keys
            if not required.issubset(document) or not set(document).issubset(allowed):
                raise ValueError(
                    "ResourceLibrary Save requires resourceLibraryId, name, enabled, storageId, "
                    "storagePath, and the optional includeRules/excludeRules/stability policy"
                )
            candidate = {
                "id": document["resourceLibraryId"],
                "name": document["name"],
                "enabled": document["enabled"],
                "storageId": document["storageId"],
                "storagePath": document["storagePath"],
            }
            for key in policy_keys:
                if key in document:
                    candidate[key] = document[key]
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
                    }
                    | {
                        key: resource.get(key)
                        for key in self._RESOURCE_LIBRARY_POLICY_KEYS
                        if key in resource
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
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "edit"
            and method == "GET"
        ):
            self._require_empty_query(environ, "MediaLibrary edit projection")
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration object service is unavailable",
                )
            return self._response(
                start_response,
                200,
                self._configuration_objects.media_library_edit_projection(parts[3]),
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "media-libraries"] and method == "PUT":
            self._require_empty_query(environ, "MediaLibrary edit")
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
            allowed = {
                "mediaLibraryId",
                "name",
                "enabled",
                "storageId",
                "rootPath",
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
            }
            if set(document) != allowed or document["mediaLibraryId"] != parts[3]:
                raise ValueError(
                    "MediaLibrary edit requires immutable matching ID and Active identity"
                )
            candidate = {
                "id": parts[3],
                "name": document["name"],
                "enabled": document["enabled"],
                "storageId": document["storageId"],
                "rootPath": document["rootPath"],
            }
            prepared: list[_ApiRuntimeBinding] = []
            with self._runtime_binding_lock:
                self._refresh_configuration_binding_locked()
                try:
                    revision = self._configuration_objects.save_media_library(
                        candidate,
                        actor=principal.principal_id,
                        before_publish=lambda rev: prepared.append(
                            self._prepare_runtime_binding_for_revision(rev)
                        ),
                        expected_revision_id=document["expectedRevisionId"],
                        expected_version=document["expectedVersion"],
                        expected_digest=document["expectedDigest"],
                        edit=True,
                    )
                except (ConfigurationActivationConflict, ConfigurationVersionConflict):
                    self._refresh_configuration_binding_locked()
                    raise
                if len(prepared) != 1:
                    raise ResourceLibrarySaveError(
                        "media_library_runtime_failed",
                        "the successor runtime binding was not prepared; the previous Active "
                        "remains in use",
                        status=503,
                    )
                self._publish_runtime_binding(prepared[0])
            library = next(
                item
                for item in self._configuration_objects._canonical_objects(
                    revision.document, "mediaLibraries"
                )
                if item.get("id") == parts[3]
            )
            return self._response(
                start_response,
                200,
                {
                    "mediaLibrary": {
                        key: library.get(key)
                        for key in ("id", "name", "storageId", "rootPath", "enabled")
                    },
                    "active": revision.summary(),
                    "configuration": {
                        "authority": "MANAGED",
                        "revisionId": revision.revision_id,
                        "version": revision.version,
                        "digest": revision.digest,
                    },
                    "sideEffects": "configuration_only",
                },
            )
        if parts == ["api", "v1", "media-libraries"] and method == "POST":
            self._require_empty_query(environ, "MediaLibrary Save")
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
            allowed = {"mediaLibraryId", "name", "enabled", "storageId", "rootPath"}
            if set(document) != allowed:
                raise ValueError(
                    "MediaLibrary Save requires only mediaLibraryId, name, enabled, "
                    "storageId, and rootPath"
                )
            candidate = {
                "id": document["mediaLibraryId"],
                "name": document["name"],
                "enabled": document["enabled"],
                "storageId": document["storageId"],
                "rootPath": document["rootPath"],
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
                    revision = self._configuration_objects.save_media_library(
                        candidate,
                        actor=principal.principal_id,
                        before_publish=before_publish,
                    )
                except (ConfigurationActivationConflict, ConfigurationVersionConflict):
                    self._refresh_configuration_binding_locked()
                    raise
                if len(prepared) != 1:
                    raise ResourceLibrarySaveError(
                        "media_library_runtime_failed",
                        "the successor runtime binding was not prepared; the previous Active "
                        "remains in use",
                        status=503,
                        revision_id=revision.revision_id,
                        durable_state="active_preserved",
                        next_action="refresh the current Active configuration and retry Save",
                    )
                self._publish_runtime_binding(prepared[0])
            library = next(
                item
                for item in self._configuration_objects._canonical_objects(
                    revision.document, "mediaLibraries"
                )
                if item.get("id") == candidate["id"]
            )
            return self._response(
                start_response,
                200,
                {
                    "mediaLibrary": {
                        "id": library["id"],
                        "name": library["name"],
                        "storageId": library["storageId"],
                        "rootPath": library.get("rootPath", ""),
                        "enabled": library["enabled"],
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
                        "refresh the Active MediaLibrary list and browse the selected library"
                        if library["enabled"]
                        else "refresh the Active MediaLibrary list; this disabled library "
                        "is not browseable"
                    ),
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "media-libraries"]
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
            self._require_empty_query(environ, "MediaLibrary removal preview")
            document = self._configuration_objects.media_library_removal_evidence(parts[3])
            return self._response(start_response, 200, document)
        if len(parts) == 4 and parts[:3] == ["api", "v1", "media-libraries"] and method == "DELETE":
            self._require_empty_query(environ, "MediaLibrary removal")
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
                    "MediaLibrary removal requires the previewed Active revision "
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
                    revision = self._configuration_objects.remove_media_library(
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
                        "media_library_runtime_failed",
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
                        "refresh the Active MediaLibrary list and select another enabled library"
                    ),
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "storages"]
            and parts[4] == "edit"
            and method == "GET"
        ):
            self._require_empty_query(environ, "Storage edit projection")
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration object service is unavailable",
                )
            return self._response(
                start_response,
                200,
                self._configuration_objects.storage_edit_projection(parts[3]),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "storages"]
            and parts[4] in {"copy", "enable", "disable"}
            and method == "POST"
        ):
            self._require_empty_query(environ, "Storage lifecycle command")
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
            required = {"expectedRevisionId", "expectedVersion", "expectedDigest"}
            action = parts[4]
            if action == "copy":
                if set(document) != required | {"newStorageId", "name"}:
                    raise ValueError(
                        "Storage copy requires newStorageId, name and exact Active identity"
                    )

                def command(callback):
                    return self._configuration_objects.copy_storage_checked(
                        parts[3],
                        new_storage_id=document["newStorageId"],
                        new_name=document["name"],
                        actor=principal.principal_id,
                        before_publish=callback,
                        expected_revision_id=document["expectedRevisionId"],
                        expected_version=document["expectedVersion"],
                        expected_digest=document["expectedDigest"],
                    )

                result_id = document["newStorageId"]
            else:
                if set(document) != required | {"enabled"}:
                    raise ValueError(
                        "Storage state change requires enabled and exact Active identity"
                    )

                def command(callback):
                    return self._configuration_objects.set_storage_enabled_checked(
                        parts[3],
                        enabled=document["enabled"],
                        actor=principal.principal_id,
                        before_publish=callback,
                        expected_revision_id=document["expectedRevisionId"],
                        expected_version=document["expectedVersion"],
                        expected_digest=document["expectedDigest"],
                    )

                result_id = parts[3]
            prepared: list[_ApiRuntimeBinding] = []
            with self._runtime_binding_lock:
                self._refresh_configuration_binding_locked()
                revision = command(
                    lambda rev: prepared.append(self._prepare_storage_binding_for_revision(rev))
                )
                if len(prepared) != 1:
                    raise ResourceLibrarySaveError(
                        "storage_runtime_failed",
                        "the successor runtime binding was not prepared; the previous "
                        "Active remains in use",
                        status=503,
                        durable_state="active_preserved",
                        next_action="refresh the current Active configuration and retry",
                    )
                self._publish_runtime_binding(prepared[0])
            return self._storage_save_response(start_response, revision, result_id)
        if len(parts) == 4 and parts[:3] == ["api", "v1", "storages"] and method == "DELETE":
            self._require_empty_query(environ, "Storage removal")
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
            required = {"expectedRevisionId", "expectedVersion", "expectedDigest"}
            if set(document) != required:
                raise ValueError("Storage removal requires the exact Active identity")
            prepared: list[_ApiRuntimeBinding] = []
            with self._runtime_binding_lock:
                self._refresh_configuration_binding_locked()
                revision = self._configuration_objects.remove_storage_checked(
                    parts[3],
                    actor=principal.principal_id,
                    before_publish=lambda rev: prepared.append(
                        self._prepare_storage_binding_for_revision(rev)
                    ),
                    expected_revision_id=document["expectedRevisionId"],
                    expected_version=document["expectedVersion"],
                    expected_digest=document["expectedDigest"],
                )
                if len(prepared) != 1:
                    raise ResourceLibrarySaveError(
                        "storage_runtime_failed",
                        "the successor runtime binding was not prepared; the previous "
                        "Active remains in use",
                        status=503,
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
                    "sideEffects": "configuration_only",
                    "nextAction": (
                        "refresh the Active Storage inventory; physical contents remain unchanged"
                    ),
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "storages"] and method == "PUT":
            self._require_empty_query(environ, "Storage edit")
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
            allowed = {
                "storageId",
                "name",
                "type",
                "rootPath",
                "readOnly",
                "enabled",
                "options",
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
            }
            # The ID is immutable after creation: an Edit may only address the
            # Active Storage it opened, never publish a re-identified object.
            if set(document) != allowed or document["storageId"] != parts[3]:
                raise ValueError("Storage edit requires immutable matching ID and Active identity")
            candidate = {
                "id": parts[3],
                "name": document["name"],
                "type": document["type"],
                "rootPath": document["rootPath"],
                "readOnly": document["readOnly"],
                "enabled": document["enabled"],
                "options": document["options"],
            }
            prepared: list[_ApiRuntimeBinding] = []
            with self._runtime_binding_lock:
                self._refresh_configuration_binding_locked()
                try:
                    revision = self._configuration_objects.save_storage(
                        candidate,
                        actor=principal.principal_id,
                        before_publish=lambda rev: prepared.append(
                            self._prepare_storage_binding_for_revision(rev)
                        ),
                        expected_revision_id=document["expectedRevisionId"],
                        expected_version=document["expectedVersion"],
                        expected_digest=document["expectedDigest"],
                        edit=True,
                    )
                except (ConfigurationActivationConflict, ConfigurationVersionConflict):
                    self._refresh_configuration_binding_locked()
                    raise
                if len(prepared) != 1:
                    raise ResourceLibrarySaveError(
                        "storage_runtime_failed",
                        "the successor runtime binding was not prepared; the previous Active "
                        "remains in use",
                        status=503,
                    )
                self._publish_runtime_binding(prepared[0])
            return self._storage_save_response(start_response, revision, parts[3])
        if parts == ["api", "v1", "storages"] and method == "GET":
            self._require_empty_query(environ, "Storage form authority")
            self._require(principal, ApiPermission.READ)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration object service is unavailable",
                )
            return self._response(
                start_response, 200, self._configuration_objects.storage_form_authority()
            )
        if parts == ["api", "v1", "storages"] and method == "POST":
            self._require_empty_query(environ, "Storage Save")
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
            allowed = {
                "storageId",
                "name",
                "type",
                "rootPath",
                "readOnly",
                "enabled",
                "options",
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
            }
            if set(document) != allowed:
                raise ValueError(
                    "Storage Save requires only storageId, name, type, rootPath, readOnly, "
                    "enabled, options, and exact Active identity"
                )
            candidate = {
                "id": document["storageId"],
                "name": document["name"],
                "type": document["type"],
                "rootPath": document["rootPath"],
                "readOnly": document["readOnly"],
                "enabled": document["enabled"],
                "options": document["options"],
            }
            prepared: list[_ApiRuntimeBinding] = []
            with self._runtime_binding_lock:
                # Pin the process to the same save-time Active before any
                # successor work begins.  A failed Save must leave a usable
                # old binding, while a competing winner can be refreshed
                # explicitly below if publication loses the race.
                self._refresh_configuration_binding_locked()

                def before_publish(revision) -> None:
                    prepared.append(self._prepare_storage_binding_for_revision(revision))

                try:
                    revision = self._configuration_objects.save_storage(
                        candidate,
                        actor=principal.principal_id,
                        before_publish=before_publish,
                        expected_revision_id=document["expectedRevisionId"],
                        expected_version=document["expectedVersion"],
                        expected_digest=document["expectedDigest"],
                    )
                except (ConfigurationActivationConflict, ConfigurationVersionConflict):
                    # The repository has authoritative concurrency fencing;
                    # if another Active won, make this process consume that
                    # winner before returning the stale/conflict result.
                    self._refresh_configuration_binding_locked()
                    raise
                if len(prepared) != 1:
                    raise ResourceLibrarySaveError(
                        "storage_runtime_failed",
                        "the successor runtime binding was not prepared; the previous Active "
                        "remains in use",
                        status=503,
                        revision_id=revision.revision_id,
                        durable_state="active_preserved",
                        next_action="refresh the current Active configuration and retry Save",
                    )
                self._publish_runtime_binding(prepared[0])
            return self._storage_save_response(start_response, revision, candidate["id"])
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
        if parts == ["api", "v1", "media-libraries"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            if binding.files_browser is None:
                return self._files_browser_unavailable(start_response)
            self._require_empty_query(environ, "MediaLibrary list")
            return self._response(start_response, 200, binding.files_browser.list_media_libraries())
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            if binding.files_browser is None:
                return self._files_browser_unavailable(start_response)
            query = self._media_library_files_query(environ, parts[3])
            return self._response(
                start_response,
                200,
                binding.files_browser.browse_media_library(**query),
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
            return self._files_direct_text_read(start_response, binding, parts[3], environ)
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
            and parts[5] == "text"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            return self._files_direct_text_read(
                start_response, binding, parts[3], environ, media_library=True
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "delete-impact"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            return self._files_direct_delete_impact(start_response, binding, parts[3], environ)
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
            and parts[5] == "delete-impact"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            return self._files_direct_delete_impact(
                start_response, binding, parts[3], environ, media_library=True
            )
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4:6] == ["files", "deletes"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "Files Delete status")
            return self._files_direct_delete_status(start_response, binding, parts[3], parts[6])
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4:6] == ["files", "deletes"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "MediaLibrary Delete status")
            return self._files_direct_delete_status(
                start_response, binding, parts[3], parts[6], media_library=True
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "rename-evidence"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            return self._files_direct_rename_evidence(start_response, binding, parts[3], environ)
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
            and parts[5] == "rename-evidence"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            return self._files_direct_rename_evidence(
                start_response, binding, parts[3], environ, media_library=True
            )
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
            transfers = self._durable_transfer_reader(binding, media_library=False)
            if transfers is None:
                return self._files_browser_unavailable(start_response)
            self._require_empty_query(environ, "Files transfer status")
            try:
                projection = transfers.transfer_projection(parts[6])
            except DirectFileTransferError as error:
                if error.category == "not_found":
                    raise LookupError(f"task {parts[6]!r} was not found") from None
                raise
            return self._response(
                start_response,
                200,
                self._with_transfer_worker_readiness(projection, media_library=False),
            )
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
            and parts[5] == "organize-work"
            and method == "GET"
        ):
            # Files' own durable readback of its organizing work for this library.
            # It replaces the removed Task Center discovery section: the operator can
            # reopen several known runs (and a lost admission by its exact request
            # identity) long after they left any recent-N window, without any page
            # visit creating work.  Principal-bound, library-scoped and cursor-paged.
            self._require(principal, ApiPermission.READ)
            service = getattr(self, "_media_discovery", None)
            if service is None:
                return self._discovery_unavailable(start_response)
            query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(query) - {"limit", "before", "requestId"}:
                raise ValueError("Files organize work accepts only limit, before and requestId")
            limit = 25
            if "limit" in query:
                if len(query["limit"]) != 1 or not query["limit"][0].isdigit():
                    raise ValueError("Files organize work limit is invalid")
                limit = int(query["limit"][0])
            boundary = None
            if "before" in query:
                if len(query["before"]) != 1:
                    raise ValueError("Files organize work cursor is invalid")
                cursor_at, _, cursor_id = query["before"][0].partition("|")
                if not cursor_id:
                    raise ValueError("Files organize work cursor is invalid")
                try:
                    boundary = (datetime.fromisoformat(cursor_at), cursor_id)
                except ValueError as error:
                    raise ValueError("Files organize work cursor is invalid") from error
            request_ids = query.get("requestId", [])
            if len(request_ids) > 1:
                raise ValueError("Files organize work accepts only one requestId")
            work = self._files_organize_work(
                principal,
                binding,
                resource_library_id=parts[3],
                limit=limit,
                before=boundary,
                request_id=(request_ids[0] if len(request_ids) == 1 else None),
            )
            return self._response(
                start_response,
                200,
                {
                    "journey": "files-organize-work",
                    "resourceLibraryId": parts[3],
                    "items": work["items"],
                    "total": len(work["items"]),
                    "nextBefore": work["nextBefore"],
                    "sideEffects": "none",
                    "zeroMutation": True,
                },
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "discoveries"
            and method == "POST"
        ):
            # RO-6 folder/mixed-selection discovery admission.  The browser
            # submits only the enabled ResourceLibrary identity and exact
            # ResourceLibrary-relative folder/file paths; the backend resolves
            # real entry types, the pinned immutable Active revision, the
            # Storage adapter and every concrete budget, then returns promptly
            # with one durable discovery record.  This request enumerates no
            # directory, calls no Provider and mutates nothing.
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            self._require_empty_query(environ, "Files discovery admission")
            discovery_service = getattr(self, "_media_discovery", None)
            if discovery_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "bounded folder discovery is unavailable",
                    details={
                        "durableState": "no_discovery_created",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "restore a valid Active runtime and discovery services, then "
                            "resubmit the same bounded selection"
                        ),
                    },
                )
            document = self._document(environ)
            # ``requestId`` is the caller's own identity for this exact
            # admission request.  The backend resolves the immutable Active pin
            # here, at admission time, so a browser that rendered an older pin
            # cannot prove which admission its POST became; the caller's own
            # identifier can, and it is echoed durably for a lost-response
            # readback.  It is optional so an existing client keeps working.
            if not isinstance(document, dict) or set(document) not in (
                {"paths"},
                {"paths", "requestId"},
                {"paths", "autoPrepare"},
                {"paths", "requestId", "autoPrepare"},
            ):
                raise ValueError("Files discovery admission accepts only bounded relative paths")
            if not isinstance(document["paths"], list):
                raise ValueError("Files discovery admission paths must be an array")
            auto_prepare = document.get("autoPrepare", False)
            if not isinstance(auto_prepare, bool):
                raise ValueError("Files discovery autoPrepare flag must be boolean")
            try:
                discovery = discovery_service.admit(
                    resource_library_id=parts[3],
                    relative_paths=document["paths"],
                    actor=principal.principal_id,
                    admission_request_id=document.get("requestId"),
                    auto_prepare=auto_prepare,
                )
            except DiscoveryError as error:
                return self._discovery_step_error(start_response, error)
            return self._response(
                start_response,
                202,
                self._discovery_document(
                    discovery,
                    principal,
                    binding,
                    requested_by=(
                        document.get("requestId")
                        if isinstance(document.get("requestId"), str)
                        else None
                    ),
                ),
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "files"
            and parts[5] == "commands"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.EXECUTE_MANUAL_ORGANIZE)
            return self._files_direct_command(
                start_response, binding, parts[3], environ, media_library=False
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
            and parts[5] == "commands"
            and method == "POST"
        ):
            # The MediaLibrary page reaches the same application behavior through
            # its own library authority: identical permissions, identical request
            # contract, identical admission and execution boundary — and a
            # ResourceLibrary ID supplied here is simply not an enabled
            # MediaLibrary, so it fails closed.
            self._require(principal, ApiPermission.EXECUTE_MANUAL_ORGANIZE)
            return self._files_direct_command(
                start_response, binding, parts[3], environ, media_library=True
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
            and parts[5] == "transfer-impact"
            and method == "GET"
        ):
            # The MediaLibrary transfer impact: the same zero-mutation bounded
            # admission read as the Files surface, resolved entirely from this
            # kind's own Active MediaLibrary authority.  A ResourceLibrary ID
            # named here is simply not an enabled MediaLibrary, so it fails
            # closed; the source or destination can never silently cross kinds.
            self._require(principal, ApiPermission.READ)
            if binding.direct_media_transfers is None:
                return self._files_browser_unavailable(start_response)
            query = self._files_transfer_impact_query(environ)
            impact = binding.direct_media_transfers.transfer_impact(
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
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
            and parts[5] == "transfers"
            and method == "POST"
        ):
            # MediaLibrary transfer admission: identical permissions, request
            # contract and durable admission behavior as the Files transfer —
            # under this kind's own authority.  The admitted Task records the
            # media command name, so it is never claimable or reconstructable
            # as ResourceLibrary work.
            self._require(principal, ApiPermission.EXECUTE_MANUAL_ORGANIZE)
            if binding.direct_media_transfers is None:
                return self._files_browser_unavailable(start_response)
            self._require_empty_query(environ, "MediaLibrary transfer")
            document = self._document(environ)
            required = {
                "operation",
                "paths",
                "destinationMediaLibraryId",
                "destinationDirectory",
                "conflictMode",
                "manifestDigest",
            }
            if not isinstance(document, dict) or set(document) != required:
                raise ValueError(
                    "a MediaLibrary transfer requires only operation, paths, "
                    "destinationMediaLibraryId, destinationDirectory, conflictMode, "
                    "and manifestDigest"
                )
            if not isinstance(document["paths"], list):
                raise ValueError("MediaLibrary transfer paths must be an array")
            result = binding.direct_media_transfers.submit_transfer(
                resource_library_id=parts[3],
                paths=document["paths"],
                destination_resource_library_id=document["destinationMediaLibraryId"],
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
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
            and parts[5] == "transfers"
            and method == "GET"
        ):
            # The bounded durable projection of one admitted media transfer.
            # The media projection is only ever served by the media-kind
            # service, so an equal ResourceLibrary ID cannot read a media
            # transfer (or the reverse).
            self._require(principal, ApiPermission.READ)
            transfers = self._durable_transfer_reader(binding, media_library=True)
            if transfers is None:
                return self._files_browser_unavailable(start_response)
            self._require_empty_query(environ, "MediaLibrary transfer status")
            try:
                projection = transfers.transfer_projection(parts[6])
            except DirectFileTransferError as error:
                if error.category == "not_found":
                    raise LookupError(f"task {parts[6]!r} was not found") from None
                raise
            return self._response(
                start_response,
                200,
                self._with_transfer_worker_readiness(projection, media_library=True),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4] == "file-operations"
            and method == "GET"
        ):
            # The originating library's own ordinary file-operation history.
            # A durable read: it resolves no Active runtime, opens no Storage
            # and creates no work, so a fresh page (or a process restarted
            # during an Active outage) still lists exactly the operations this
            # library admitted.
            self._require(principal, ApiPermission.READ)
            return self._library_file_operations_page(
                start_response,
                environ,
                principal,
                parts[3],
                media_library=False,
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "file-operations"
            and method == "GET"
        ):
            # The MediaLibrary twin of the library-owned history read: the same
            # durable behavior under the media kind's own authority, so an
            # equal ResourceLibrary ID can never supply or read media work.
            self._require(principal, ApiPermission.READ)
            return self._library_file_operations_page(
                start_response,
                environ,
                principal,
                parts[3],
                media_library=True,
            )
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[3] == "operation-origins"
            and method == "GET"
        ):
            # The bounded set of origins this library kind still owns.  It keeps
            # the header entry usable when the current live library list no
            # longer contains a disabled/removed origin.
            self._require(principal, ApiPermission.READ)
            return self._library_file_operation_origins(
                start_response, environ, media_library=False
            )
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[3] == "operation-origins"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            return self._library_file_operation_origins(start_response, environ, media_library=True)
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4:6] == ["files", "operations"]
            and method == "GET"
        ):
            # One ordinary operation of this exact library, rebuilt from its
            # durable Task evidence.  A Task of another library or the other
            # kind is a bounded refusal, never a rebound document.
            self._require(principal, ApiPermission.READ)
            return self._library_file_operation_detail(
                start_response,
                environ,
                principal,
                parts[3],
                parts[6],
                media_library=False,
                binding=binding,
            )
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4:6] == ["files", "operations"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            return self._library_file_operation_detail(
                start_response,
                environ,
                principal,
                parts[3],
                parts[6],
                media_library=True,
                binding=binding,
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "files"]
            and parts[3] == "operation-origin"
            and method == "GET"
        ):
            # Resolve one existing ordinary Task/run deep link to the exact
            # owning library page, or to a bounded non-match.  The read uses
            # durable admitted evidence only and never guesses a library; the
            # originating kind comes from the Task's own persisted command, so
            # both library kinds share this one route.
            self._require(principal, ApiPermission.READ)
            return self._library_file_operation_origin(
                start_response, environ, parts[4], media_library=None
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
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6] == "metadata-correction-continuation"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
            self._require_empty_query(environ, "task item action")
            document = self._document(environ)
            allowed = {"reviewId", "expectedCorrectionVersion"}
            if set(document).difference(allowed):
                raise ValueError(f"task item {parts[6]} request fields are invalid")
            if set(document) != allowed:
                raise ValueError(
                    "Metadata correction continuation requires reviewId and "
                    "expectedCorrectionVersion"
                )
            if self._configuration_service is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            submission = FileMetadataCorrectionContinuationService(
                self._repository,
                snapshot_validator=(self._configuration_service.validate_runtime_snapshot),
            ).submit(
                parts[3],
                parts[5],
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
        if parts == ["api", "v1", "auth", "principal"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "authenticated principal")
            return self._response(
                start_response,
                200,
                {"principal_id": principal.principal_id},
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
                value["manualRecoveryPreparation"] = (
                    self._manual_recovery.discovery_for_preparation(parts[3], parts[5])
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
            len(parts) == 8
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6:8] == ["recovery", "prepare-summary"]
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
            self._require_empty_query(environ, "manual recovery plan summary preparation")
            document = self._document(environ)
            if set(document) != {"expectedCheckpointVersion"}:
                raise ValueError(
                    "manual recovery plan summary preparation requires only "
                    "expectedCheckpointVersion"
                )
            expected = document["expectedCheckpointVersion"]
            if not isinstance(expected, str) or not expected.strip():
                raise ValueError("expectedCheckpointVersion is required")
            preparation = self._manual_recovery.prepare_summary(
                parts[3],
                parts[5],
                expected_checkpoint_version=expected,
                actor=principal.principal_id,
            )
            return self._response(
                start_response,
                201,
                redact_manual_value(
                    {
                        **preparation.document(),
                        "hasExecutionAuthority": False,
                        "sideEffects": "none",
                        "executionMode": "not_authorized_yet",
                    }
                ),
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-recovery-preparations"]
            and parts[4] == "confirm"
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
            self._require_empty_query(environ, "manual recovery plan summary confirmation")
            document = self._document(environ)
            allowed = {"itemIds", "confirmation", "allowOverwrite", "allowSourceCleanup"}
            if set(document).difference(allowed):
                raise ValueError("manual recovery plan summary confirmation fields are invalid")
            if not {"itemIds", "confirmation"}.issubset(document):
                raise ValueError(
                    "manual recovery plan summary confirmation requires itemIds and confirmation"
                )
            if document["confirmation"] is not True:
                raise ValueError(
                    "manual recovery plan summary confirmation requires confirmation=true"
                )
            item_ids = document["itemIds"]
            if not isinstance(item_ids, list) or not item_ids:
                raise ValueError("manual recovery plan summary confirmation requires itemIds")
            execution = self._manual_recovery.confirm_prepared(
                parts[3],
                item_ids=item_ids,
                actor=principal.principal_id,
                permission=ApiPermission.EXECUTE_MANUAL_ORGANIZE.value,
                confirmation=True,
                allow_overwrite=bool(document.get("allowOverwrite", False)),
                allow_source_cleanup=bool(document.get("allowSourceCleanup", False)),
            )
            return self._response(
                start_response,
                202,
                {
                    "executionId": execution.execution_id,
                    "taskId": execution.task_id,
                    "status": execution.status.value,
                    "selectedItemIds": list(execution.selected_item_ids),
                    "nextAction": execution.next_action,
                    "executionPath": "/api/v1/manual-executions/" + execution.execution_id,
                    "sideEffects": "execution_admitted",
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
            if set(document).difference({"items", "batchId"}) or "items" not in document:
                raise ValueError(
                    "task batch recovery continuation requires items and optional batchId"
                )
            if not isinstance(document["items"], list):
                raise ValueError("task batch recovery items must be a list")
            if "batchId" in document and not isinstance(document["batchId"], str):
                raise ValueError("task batch recovery identity must be a UUID")
            binding = self._runtime_binding
            batch = self._recovery_batch.submit(
                parts[3],
                document["items"],
                actor=principal.principal_id,
                maximum_active_jobs=binding.maximum_active_jobs,
                batch_id=document.get("batchId"),
            )
            return self._response(
                start_response,
                202,
                {
                    **self._recovery_batch_document(batch),
                    "executionMode": "dry_run",
                    "sideEffects": "none",
                },
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "recovery-batches"
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "Task recovery batch")
            batch = self._repository.get_recovery_batch(parts[5])
            if batch.source_task_id != parts[3]:
                raise LookupError("Task recovery batch was not found")
            return self._response(start_response, 200, self._recovery_batch_document(batch))
        if len(parts) == 4 and parts[:3] == ["api", "v1", "recovery-batches"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "recovery batch")
            return self._response(
                start_response,
                200,
                self._recovery_batch_document(self._repository.get_recovery_batch(parts[3])),
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
                    **self._recovery_batch_document(batch),
                    "executionMode": "dry_run",
                    "sideEffects": "none",
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "remaining-scope-previews"
            and method == "POST"
        ):
            # The native exact-Preview recovery path for a paused run whose
            # Continue cannot retain live execution authority (RO-5).  It is a
            # Task-scoped sibling of the resume control, so the advertised
            # next action and the real admission can never disagree.
            return self._operations_run_remaining_scope_preview(
                parts[3], environ, start_response, principal
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
            service = TaskLifecycleService(
                self._repository,
                snapshot_validator=self._scope_continuations._snapshot_validator,
                mutation_authority=binding.scope_continuation_authority,
            )
            media_transfer_command = direct_command_task_command(
                FILES_TRANSFER_TASK_COMMAND, media_library=True
            )
            media_delete_command = direct_command_task_command(
                FILES_DELETE_TASK_COMMAND, media_library=True
            )
            if action == "resume":
                task = service.require(parts[3])
                service.require_version(task, expected_version)
                if is_files_worker_task_command(task.command):
                    is_delete = task.command in {
                        FILES_DELETE_TASK_COMMAND,
                        direct_command_task_command(FILES_DELETE_TASK_COMMAND, media_library=True),
                    }
                    is_media = task.command in {media_transfer_command, media_delete_command}
                    transfer_service = (
                        binding.direct_media_transfers if is_media else binding.direct_transfers
                    )
                    if is_delete and transfer_service is None:
                        transfer_service = self._durable_transfer_reader(
                            binding, media_library=is_media
                        )
                    if transfer_service is not None:
                        # The accepted continuation only requeues the persisted
                        # bounded authority. The resident Worker later claims
                        # it and continues from terminal per-item evidence;
                        # uncertain mutation is never replayed.
                        requeued = (
                            transfer_service.requeue_delete(task.task_id)
                            if is_delete
                            else transfer_service.requeue_transfer(task.task_id)
                        )
                        current = service.require(task.task_id)
                        lifecycle = self._task_lifecycle(
                            service,
                            current,
                            principal,
                            results=service.results(current.task_id),
                        )
                        return self._response(
                            start_response,
                            202,
                            {
                                **requeued,
                                "action": action,
                                "task": task_operator_document(current),
                                "lifecycle": lifecycle,
                                "durableOutcome": next(
                                    (
                                        item["durableOutcome"]
                                        for item in lifecycle["actions"]
                                        if item["action"] == action
                                    ),
                                    None,
                                ),
                            },
                        )
                # The shared durable queued continuation of one exact paused
                # Task's remaining admitted scope.  The request performs zero
                # Storage work: it revalidates the exact durable state, the live
                # pin and the applicable execution authority, then queues a
                # bounded continuation Job for the resident Worker.  A Task kind
                # without that boundary is refused with the same actionable
                # reason the projection states.
                try:
                    submission = self._scope_continuations.submit(
                        task.task_id,
                        expected_version=expected_version,
                        actor=principal.principal_id,
                        maximum_active_jobs=binding.maximum_active_jobs,
                        mutation_authority=binding.scope_continuation_authority,
                    )
                except ScopeContinuationError as error:
                    raise OperationsLifecycleConflict(
                        error.reason.value,
                        str(error),
                        durable_state=error.durable_state,
                        next_action=error.next_action,
                        retry_safe=error.retry_safe,
                        current_version=error.current_version,
                    ) from error
                current = service.require(task.task_id)
                lifecycle = self._task_lifecycle(
                    service,
                    current,
                    principal,
                    results=service.results(current.task_id),
                )
                return self._response(
                    start_response,
                    202,
                    {
                        "action": action,
                        "taskId": current.task_id,
                        "task": task_operator_document(current),
                        "lifecycle": lifecycle,
                        "continuation": scope_continuation_operator_document(
                            submission.continuation
                        ),
                        "jobId": submission.job.job_id,
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
                        "nextAction": submission.continuation.next_action(),
                    },
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
                            TaskLifecycleService(
                                self._repository,
                                snapshot_validator=(self._scope_continuations._snapshot_validator),
                                mutation_authority=(
                                    binding.scope_continuation_authority
                                    if binding is not None
                                    else None
                                ),
                            ),
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
                document = job_submission if job_submission is not None else self._document(environ)
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

    def _notification_recovery_targets(self):
        service = self._configuration_service
        active = service.active()
        if active is None:
            return {}
        service.verify_integrity(active)
        runtime = service._load_for_runtime(active.document)
        return {
            item.webhook_id: item
            for item in runtime.webhooks
            if item.enabled and os.environ.get(item.secret_env)
        }

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
        status["commandReadiness"] = self._command_readiness_document(principal, status)
        status["ruleReadiness"] = self._rule_readiness_document()
        return status

    def _rule_readiness_document(
        self,
    ) -> dict[str, object]:
        """Bounded rule-family readiness derived from one exact Active read.

        Settings and the rules workspace must not disagree about what the runtime
        consumes. This projection therefore reuses the
        ``ConfigurationObjectService.active_rule_readiness`` projection — the
        same managed Active revision read, the same reference resolution and the
        same gap derivation, bound to the exact revision identity of that one
        in-memory read. A concurrent activation that lands between this
        projection's Active read and the status document's Active read therefore
        cannot masquerade as one consistent snapshot: the status document
        reports its own identity, the readiness reports the identity it actually
        derived, and the frontend treats a mismatch as "refresh required" while
        showing neither the stale counts nor the gaps as current.

        Nothing is cached, generated, written or resolved in the browser, and no
        secret, raw document or credential value crosses this boundary.
        """

        if self._configuration_objects is None:
            rule_families = self._RULE_INVENTORY_FAMILY_ORDER
            empty_families = {family: 0 for family in rule_families}
            return {
                "available": False,
                "reason": "unavailable",
                "active": None,
                "state": "UNAVAILABLE",
                "gaps": [],
                "counts": empty_families,
                "enabledCounts": dict(empty_families),
            }
        try:
            return self._configuration_objects.active_rule_readiness()
        except Exception:
            rule_families = self._RULE_INVENTORY_FAMILY_ORDER
            empty_families = {family: 0 for family in rule_families}
            return {
                "available": False,
                "reason": "unavailable",
                "active": None,
                "state": "UNAVAILABLE",
                "gaps": [],
                "counts": empty_families,
                "enabledCounts": dict(empty_families),
            }

    @staticmethod
    def _readiness_entry(
        *,
        ready: bool,
        condition: str,
        durable_state: str,
        next_action: str,
        recovery_destination: str,
        authorized: bool = True,
    ) -> dict[str, object]:
        return {
            "ready": ready,
            "condition": condition,
            "durableState": durable_state,
            "nextAction": next_action,
            "recoveryDestination": recovery_destination,
            "authorized": authorized,
            "sideEffects": "none",
        }

    def _command_readiness_document(
        self,
        principal: ResolvedApiPrincipal,
        status: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Bounded command facts for Settings and business-page recovery.

        This projection only reads the managed Active document and in-memory
        service availability. It never constructs a Storage/Provider, checks a
        Webhook, grants authority or starts work.
        """

        status = status or self._configuration_service.status_document()
        required_permissions = {
            "storageConfiguration": frozenset(
                {ApiPermission.MANAGE_CONFIGURATION, ApiPermission.ACTIVATE_CONFIGURATION}
            ),
            "libraryConfiguration": frozenset(
                {ApiPermission.MANAGE_CONFIGURATION, ApiPermission.ACTIVATE_CONFIGURATION}
            ),
            "storageAccess": frozenset({ApiPermission.READ}),
            "libraryBrowse": frozenset({ApiPermission.READ}),
            "directTransfer": frozenset({ApiPermission.EXECUTE_MANUAL_ORGANIZE}),
            "preview": frozenset({ApiPermission.MANAGE_MANUAL_ORGANIZE}),
            "organize": frozenset(
                {ApiPermission.MANAGE_MANUAL_ORGANIZE, ApiPermission.EXECUTE_MANUAL_ORGANIZE}
            ),
            "scheduling": frozenset({ApiPermission.GRANT_UNATTENDED_EXECUTION}),
            "notification": frozenset({ApiPermission.MANAGE_CONFIGURATION}),
        }

        def authorized_for(key: str) -> bool:
            return required_permissions[key].issubset(principal.permissions)

        def unavailable_for(key: str, destination: str, reason: str, next_action: str):
            authorized = authorized_for(key)
            return self._readiness_entry(
                ready=False,
                condition="unauthorized" if not authorized else reason,
                durable_state=(
                    "the connected API principal lacks the permission required for this scope"
                    if not authorized
                    else reason
                ),
                next_action=(
                    "contact an administrator for the required permission"
                    if not authorized
                    else next_action
                ),
                recovery_destination=destination,
                authorized=authorized,
            )

        active = status.get("active")
        if not isinstance(active, dict):
            reason = (
                "no_active_configuration" if status.get("setupRequired") else "active_unavailable"
            )
            next_action = (
                "create and activate the empty baseline in Settings"
                if reason == "no_active_configuration"
                else "repair the Active configuration, then refresh"
            )

            return {
                key: unavailable_for(key, "/ui-v2/configuration", reason, next_action)
                for key in (
                    "storageConfiguration",
                    "libraryConfiguration",
                    "storageAccess",
                    "libraryBrowse",
                    "directTransfer",
                    "preview",
                    "organize",
                    "scheduling",
                    "notification",
                )
            }
        try:
            revision = self._configuration_service.active()
            document = revision.document if revision is not None else None
        except Exception:
            document = None
        if not isinstance(document, dict):
            return {
                key: unavailable_for(
                    key,
                    "/ui-v2/configuration",
                    "active_unavailable",
                    "repair the Active configuration, then refresh",
                )
                for key in (
                    "storageConfiguration",
                    "libraryConfiguration",
                    "storageAccess",
                    "libraryBrowse",
                    "directTransfer",
                    "preview",
                    "organize",
                    "scheduling",
                    "notification",
                )
            }

        storages = [item for item in document.get("storages", []) if isinstance(item, dict)]
        storage_present = bool(storages)
        enabled_storages = {
            item.get("id") for item in storages if item.get("enabled", True) is not False
        }
        resources = [
            item for item in document.get("resourceLibraries", []) if isinstance(item, dict)
        ]
        media = [item for item in document.get("mediaLibraries", []) if isinstance(item, dict)]
        resource_present = bool(resources)
        media_present = bool(media)
        enabled_resources = [
            item
            for item in resources
            if item.get("enabled", True) is not False and item.get("storageId") in enabled_storages
        ]
        enabled_media = [
            item
            for item in media
            if item.get("enabled", True) is not False and item.get("storageId") in enabled_storages
        ]
        processing = all(
            document.get(key)
            for key in (
                "recognitionTypes",
                "recognitionRules",
                "recognitionTypePolicies",
                "metadataPolicies",
                "namingPolicies",
                "classificationPolicies",
                "organizePolicies",
            )
        )
        manage = ApiPermission.MANAGE_CONFIGURATION in principal.permissions
        activate = ApiPermission.ACTIVATE_CONFIGURATION in principal.permissions
        preview = ApiPermission.MANAGE_MANUAL_ORGANIZE in principal.permissions
        execute = ApiPermission.EXECUTE_MANUAL_ORGANIZE in principal.permissions

        def permission(allowed: bool, destination: str, label: str):
            if not allowed:
                return self._readiness_entry(
                    ready=False,
                    condition="unauthorized",
                    durable_state=f"{label} permission denied",
                    next_action="contact an administrator for the required permission",
                    recovery_destination=destination,
                    authorized=False,
                )
            return None

        storage_permission = permission(
            manage and activate, "/ui-v2/storage", "storage configuration"
        )
        library_permission = permission(
            manage and activate, "/ui-v2/resourcelib/files", "library configuration"
        )
        storage_config = storage_permission or self._readiness_entry(
            ready=True,
            condition="ready",
            durable_state="storage configuration is available",
            next_action="add or edit a Storage",
            recovery_destination="/ui-v2/storage",
        )
        library_config = library_permission or self._readiness_entry(
            ready=bool(enabled_storages),
            condition=(
                "ready" if enabled_storages else "disabled" if storage_present else "missing"
            ),
            durable_state="enabled Storage is available"
            if enabled_storages
            else "no enabled Storage",
            next_action="enable a Storage" if storage_present else "add a Storage",
            recovery_destination="/ui-v2/storage",
        )
        storage_access = self._readiness_entry(
            ready=bool(enabled_storages) and authorized_for("storageAccess"),
            condition=(
                "unauthorized"
                if not authorized_for("storageAccess")
                else "admission_ready"
                if enabled_storages
                else "disabled"
                if storage_present
                else "missing"
            ),
            durable_state=(
                "Storage access permission denied"
                if not authorized_for("storageAccess")
                else "enabled Storage is configured; live access is verified by the command"
                if enabled_storages
                else "Storage definitions are disabled"
                if storage_present
                else "no Storage definitions"
            ),
            next_action=(
                "contact an administrator for the required permission"
                if not authorized_for("storageAccess")
                else "enable a Storage"
                if storage_present
                else "add a Storage"
            ),
            recovery_destination="/ui-v2/storage",
            authorized=authorized_for("storageAccess"),
        )
        browse = self._readiness_entry(
            ready=bool(enabled_resources or enabled_media) and authorized_for("libraryBrowse"),
            condition=(
                "unauthorized"
                if not authorized_for("libraryBrowse")
                else "admission_ready"
                if (enabled_resources or enabled_media)
                else "disabled"
                if (resource_present or media_present)
                else "missing"
            ),
            durable_state=(
                "library browse permission denied"
                if not authorized_for("libraryBrowse")
                else "browseable library configured"
                if (enabled_resources or enabled_media)
                else "no enabled library"
            ),
            next_action=(
                "contact an administrator for the required permission"
                if not authorized_for("libraryBrowse")
                else "add a ResourceLibrary or MediaLibrary"
            ),
            recovery_destination="/ui-v2/resourcelib/files",
            authorized=authorized_for("libraryBrowse"),
        )
        transfer = self._readiness_entry(
            ready=bool(enabled_resources or enabled_media) and authorized_for("directTransfer"),
            condition=(
                "unauthorized"
                if not authorized_for("directTransfer")
                else "admission_ready"
                if (enabled_resources or enabled_media)
                else "disabled"
                if (resource_present or media_present)
                else "missing"
            ),
            durable_state=(
                "direct transfer permission denied"
                if not authorized_for("directTransfer")
                else "direct transfer scope available"
                if (enabled_resources or enabled_media)
                else "no transfer scope"
            ),
            next_action=(
                "contact an administrator for the required permission"
                if not authorized_for("directTransfer")
                else "add an enabled library"
            ),
            recovery_destination="/ui-v2/resourcelib/files",
            authorized=authorized_for("directTransfer"),
        )
        organize_permission = permission(
            preview and execute, "/ui-v2/operations/organize/new", "Organize"
        )
        organize = organize_permission or self._readiness_entry(
            ready=bool(enabled_resources and enabled_media and processing),
            condition="ready" if enabled_resources and enabled_media and processing else "missing",
            durable_state="organize chain and source/destination are available"
            if enabled_resources and enabled_media and processing
            else "source, destination or processing chain is not configured",
            next_action="configure the missing source, destination and processing policies",
            recovery_destination="/ui-v2/configuration",
        )
        schedules = (
            document.get("automation", {}).get("schedules", [])
            if isinstance(document.get("automation"), dict)
            else []
        )
        notifications = (
            document.get("notifications", {}).get("webhooks", [])
            if isinstance(document.get("notifications"), dict)
            else []
        )
        schedule_present = bool(schedules)
        schedules = [
            item for item in schedules if isinstance(item, dict) and item.get("enabled", True)
        ]
        notification_present = bool(notifications)
        notifications = [
            item for item in notifications if isinstance(item, dict) and item.get("enabled", True)
        ]
        scheduling = self._readiness_entry(
            ready=bool(schedules) and authorized_for("scheduling"),
            condition=(
                "unauthorized"
                if not authorized_for("scheduling")
                else "ready"
                if schedules
                else "disabled"
                if schedule_present
                else "missing"
            ),
            durable_state=(
                "scheduling permission denied"
                if not authorized_for("scheduling")
                else "enabled schedule definitions are available"
                if schedules
                else "no schedule definitions"
            ),
            next_action=(
                "contact an administrator for the required permission"
                if not authorized_for("scheduling")
                else "enable a schedule"
                if schedule_present
                else "add an enabled schedule"
            ),
            recovery_destination="/ui-v2/operations/automation",
            authorized=authorized_for("scheduling"),
        )
        notification = self._readiness_entry(
            ready=bool(notifications) and authorized_for("notification"),
            condition=(
                "unauthorized"
                if not authorized_for("notification")
                else "ready"
                if notifications
                else "disabled"
                if notification_present
                else "missing"
            ),
            durable_state=(
                "notification configuration permission denied"
                if not authorized_for("notification")
                else "webhook targets are configured"
                if notifications
                else "no webhook targets"
            ),
            next_action=(
                "contact an administrator for the required permission"
                if not authorized_for("notification")
                else "enable a Webhook target"
                if notification_present
                else "add an enabled Webhook target"
            ),
            recovery_destination="/ui-v2/operations/notifications",
            authorized=authorized_for("notification"),
        )
        return {
            "storageConfiguration": storage_config,
            "libraryConfiguration": library_config,
            "storageAccess": storage_access,
            "libraryBrowse": browse,
            "directTransfer": transfer,
            "organize": organize,
            "scheduling": scheduling,
            "notification": notification,
        }

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
            "businessState": status.get("businessState"),
            "capabilities": status.get("capabilities", {}),
            "emptyActive": status.get("emptyActive", False),
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
            "commandReadiness": status.get("commandReadiness", {}),
            # Infrastructure and work readiness are deliberately separate.  A
            # correctly-waiting resident service is infrastructure-ready but has
            # no work, and a fully configured deployment whose Scheduler is
            # down is not infrastructure-ready even though its configuration is
            # valid.  Conflating the two is what made the previous surfaces lie.
            "infrastructure": self._infrastructure_readiness_document(),
        }

    def _infrastructure_readiness_document(self) -> dict[str, object]:
        """Bounded, read-only resident-service presence for this deployment.

        This is deliberately side-effect free: it reads the shared runtime
        database only.  It never loads an Active configuration, opens a Storage
        or Provider, sends a Webhook, admits work or migrates schema, so it is
        safe to call during a configuration outage — which is exactly when an
        operator most needs to know whether the rest of the deployment is
        healthy.
        """

        service = self._resident_services
        if service is None:
            return {
                "available": False,
                "durableState": "resident service presence is unavailable in this deployment",
                "nextAction": "start the API with the configured durable database",
                "infrastructureReady": False,
                "sideEffects": "none",
            }
        try:
            projection = service.deployment_readiness()
        except Exception as error:
            # A shared-database fault during a read must stay a bounded reason,
            # not an exception, because this document is itself the recovery
            # surface.
            return {
                "available": False,
                "durableState": (
                    f"resident service presence could not be read ({type(error).__name__})"
                ),
                "nextAction": "restore database access, then refresh this status",
                "infrastructureReady": False,
                "sideEffects": "none",
            }
        return {
            "available": True,
            "infrastructureReady": bool(projection.get("infrastructureReady")),
            "asOf": projection.get("asOf"),
            "sideEffects": "none",
            "services": projection.get("services", {}),
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
        # Readiness describes the resident process and command consumers.  It
        # must remain observable while current Active is unavailable because
        # already-admitted transfers may still execute their immutable pins.
        active_snapshot_id = self._runtime_binding.snapshot_id
        active_snapshot_digest = self._runtime_binding.snapshot_digest
        if self._configuration_service is not None:
            try:
                active = self._configuration_service.active()
            except Exception:
                active = None
            if active is None:
                active_snapshot_id = None
                active_snapshot_digest = None
            else:
                active_snapshot_id = active.revision_id
                active_snapshot_digest = active.digest
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
                "processAlive": True,
                "baseReadiness": {
                    "ready": False,
                    "registered": False,
                    "liveWorkers": 0,
                    "condition": WorkerReadiness.NO_WORKER.value,
                },
                "currentActiveAvailable": active_snapshot_id is not None,
                "workReadiness": {
                    "resourceFilesTransfer": {
                        "ready": False,
                        "condition": WorkerReadiness.NO_WORKER.value,
                        "durableState": "processing worker service is unavailable",
                        "nextAction": "contact system administrator",
                    },
                    "mediaFilesTransfer": {
                        "ready": False,
                        "condition": WorkerReadiness.NO_WORKER.value,
                        "durableState": "processing worker service is unavailable",
                        "nextAction": "contact system administrator",
                    },
                },
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
            "processAlive": True,
            "baseReadiness": {
                "ready": readiness.get("liveWorkers", 0) > 0
                and readiness.get("condition") != WorkerReadiness.SCHEMA_MISMATCH.value,
                "registered": readiness.get("totalWorkers", 0) > 0,
                "liveWorkers": readiness.get("liveWorkers", 0),
                "condition": readiness.get("condition"),
            },
            "currentActiveAvailable": active_snapshot_id is not None,
        }
        resource_command = direct_command_task_command(
            FILES_TRANSFER_TASK_COMMAND, media_library=False
        )
        media_command = direct_command_task_command(FILES_TRANSFER_TASK_COMMAND, media_library=True)
        document["workReadiness"] = {
            "resourceFilesTransfer": self._worker_service.evaluate_command_readiness(
                (resource_command,), runtime_schema_version=SCHEMA_VERSION
            ),
            "mediaFilesTransfer": self._worker_service.evaluate_command_readiness(
                (media_command,), runtime_schema_version=SCHEMA_VERSION
            ),
        }
        if not bounded:
            document["activeSnapshotDigest"] = active_snapshot_digest
        return redact_manual_value(document)

    def _durable_transfer_reader(self, binding, *, media_library: bool):
        """The transfer-status reader for this request's kind, bound or durable.

        While this process has an Active runtime binding it serves its own
        kind-pinned transfer service, exactly as before.  When it has none —
        the normal API restart during a current-Active outage — the read falls
        back to the bounded durable projection of the admitted Task over this
        process's own Task repository.  The fallback never substitutes another
        process's or snapshot's authority: it resolves no library, opens no
        Storage, mutates nothing, keeps the kind's own Task command filter, and
        does not present a superseded snapshot as current Active.  Admission
        and every other workflow route still require the real binding and keep
        failing closed.
        """

        bound = binding.direct_media_transfers if media_library else binding.direct_transfers
        if bound is not None:
            return bound
        if self._repository is None:
            return None
        return durable_transfer_read_service(self._repository, media_library=media_library)

    def _with_transfer_worker_readiness(
        self, projection: dict[str, object], *, media_library: bool
    ) -> dict[str, object]:
        """Attach bounded command-specific waiting evidence to one transfer."""

        if projection.get("terminal") is True:
            return projection
        command = projection.get("taskCommand")
        if not isinstance(command, str) or not command:
            command = direct_command_task_command(
                FILES_TRANSFER_TASK_COMMAND, media_library=media_library
            )
        if self._worker_service is None:
            readiness: dict[str, object] = {
                "ready": False,
                "condition": WorkerReadiness.NO_WORKER.value,
                "durableState": "processing worker service is unavailable",
                "nextAction": "restore the resident worker service; admitted work is preserved",
            }
        else:
            readiness = self._worker_service.evaluate_command_readiness(
                (command,), runtime_schema_version=SCHEMA_VERSION
            )
        context_blocked = projection.get("durableState") in {
            "files_transfer_snapshot_unavailable",
            "files_transfer_worker_kind_unavailable",
            "files_delete_snapshot_unavailable",
        }
        waiting = context_blocked or not bool(readiness.get("ready"))
        projection["waitingForWorker"] = waiting
        if context_blocked:
            projection["workerCondition"] = "task_context_unavailable"
            projection["workerDurableState"] = (
                "the admitted transfer's pinned configuration cannot currently be reconstructed"
            )
            projection["workerNextAction"] = projection.get("nextAction")
        else:
            projection["workerCondition"] = readiness.get("condition")
            projection["workerDurableState"] = readiness.get("durableState")
            projection["workerNextAction"] = readiness.get("nextAction")
            if waiting:
                projection["nextAction"] = readiness.get("nextAction")
        return projection

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
    def _is_page_local_save(path: str, method: str) -> bool:
        """Whether the request is a page-local checked Save command.

        The Files ResourceLibrary, MediaLibrary and Storage workspace saves
        capture the save-time Active, run the checked admission gates and
        publish one atomic successor, so their conflict/unavailable failures
        report the candidate truthfully (`not_published` / `not_saved`) instead
        of a generic Draft-only state.  The V2 rules-workspace object commands
        are the same class of page-local publication intent, so they report it
        the same way.
        """

        if path in (
            "/api/v1/resource-libraries",
            "/api/v1/media-libraries",
            "/api/v1/storages",
        ):
            return method == "POST"
        if method in {"POST", "PUT", "DELETE"} and path.startswith(
            "/api/v1/operations/rules/objects/"
        ):
            return True
        if path.startswith("/api/v1/operations/automation/definitions"):
            return method in {"POST", "PUT", "DELETE"} and not path.endswith("schedule-preview")
        return method == "PUT" and path.startswith("/api/v1/storages/")

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
        if tuple(parts[:3]) in {
            ("api", "v1", "jobs"),
            ("api", "v1", "tasks"),
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
            and (runtime is None or (current.files_browser is not None))
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
        direct_media_files = None
        direct_transfers = None
        direct_media_transfers = None
        if runtime_revision is not None and runtime_configuration is not None:
            files_browser = RuntimeFilesBrowserService(
                self._configuration_service,
                active_revision=runtime_revision,
                runtime_configuration=runtime_configuration,
                storage_adapters=self._storage_adapters,
                cursor_secret=self._storage_browser_cursor_secret,
            )
            direct_files = DirectFileCommandService(
                active_revision=runtime_revision,
                runtime_configuration=runtime_configuration,
                task_repository=self._repository,
                storage_adapters=self._storage_adapters,
            )
            # A second, media-kind service over the same pinned Active revision:
            # the MediaLibrary Files page gets its own library authority rather
            # than a relabelled ResourceLibrary one, and one service can never
            # resolve the other kind's library.
            direct_media_files = DirectFileCommandService(
                active_revision=runtime_revision,
                runtime_configuration=runtime_configuration,
                task_repository=self._repository,
                storage_adapters=self._storage_adapters,
                library_kind=LibraryKind.MEDIA,
            )
            # Each kind owns its own transfer admission/execution boundary over
            # the same pinned Active revision: the media service resolves only
            # enabled MediaLibraries for both endpoints, and the resource
            # service only enabled ResourceLibraries.  One kind's manifest,
            # evidence or claim can never be exchanged with the other's.
            direct_transfers = DirectFileTransferService(direct_files=direct_files)
            direct_media_transfers = DirectFileTransferService(direct_files=direct_media_files)
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
            direct_media_files,
            direct_transfers,
            direct_media_transfers,
            runtime_settings,
            tuple(getattr(runtime_configuration, "automation_task_definitions", ())),
            (
                definition_occurrence_authority(
                    self._repository,
                    getattr(runtime_configuration, "automation_task_definitions", ()),
                    self._unattended_grants,
                )
                if runtime_configuration is not None
                else None
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
        if len(parts) >= 4 and parts[:3] == ["api", "v1", "operations"] and parts[3] == "runs":
            # The unified run detail reads name their own bounded operator
            # surface without publishing run, Task, Job or item identifiers
            # in audit evidence.
            if len(parts) == 4:
                return "/api/v1/operations/runs"
            if len(parts) == 5:
                return "/api/v1/operations/runs/{id}"
            if len(parts) == 6 and parts[5] in {"items", "records", "export", "problem-items"}:
                return f"/api/v1/operations/runs/{{id}}/{parts[5]}"
            if len(parts) == 7 and parts[5] == "items":
                return "/api/v1/operations/runs/{id}/items/{itemId}"
            return "/api/v1/<unmatched>"
        exact = {
            ("api", "v1", "tasks"),
            ("api", "v1", "confirmations"),
            ("api", "v1", "schedules"),
            ("api", "v1", "notifications"),
            ("api", "v1", "logs"),
            ("api", "v1", "jobs"),
            ("api", "v1", "jobs", "stale"),
            ("api", "v1", "resource-libraries"),
            ("api", "v1", "storages"),
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
            ("api", "v1", "files"),
            ("api", "v1", "storage", "files"),
            ("api", "v1", "media-libraries"),
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
        if len(parts) >= 4 and parts[:4] == ["api", "v1", "operations", "storage-management"]:
            # The V2 Storage management projections name their own bounded
            # operator surface without publishing revision identities or
            # Storage IDs in audit evidence.
            if len(parts) == 5 and parts[4] == "inventory":
                return "/api/v1/operations/storage-management/inventory"
            if len(parts) == 6 and parts[4] == "storage":
                return "/api/v1/operations/storage-management/storage/{id}"
            if len(parts) == 7 and parts[4] == "storage" and parts[6] == "check":
                return "/api/v1/operations/storage-management/storage/{id}/check"
            return "/api/v1/<unmatched>"
        if len(parts) >= 4 and parts[:4] == ["api", "v1", "operations", "rules"]:
            # The rules-workspace surfaces name their own bounded operator route so
            # neither a family-specific object ID nor a revision identity appears in
            # security audit evidence.
            if len(parts) == 5 and parts[4] == "inventory":
                return "/api/v1/operations/rules/inventory"
            if len(parts) == 5 and parts[4] == "form-authority":
                return "/api/v1/operations/rules/form-authority"
            if len(parts) == 6 and parts[4] == "previews":
                return f"/api/v1/operations/rules/previews/{parts[5]}"
            if parts[4] == "objects":
                if len(parts) == 6:
                    return "/api/v1/operations/rules/objects/{family}"
                if len(parts) == 7:
                    return "/api/v1/operations/rules/objects/{family}/{id}"
                if len(parts) == 8 and parts[7] in {"copy", "impact"}:
                    return f"/api/v1/operations/rules/objects/{{family}}/{{id}}/{parts[7]}"
                if len(parts) == 9 and parts[7] == "state" and parts[8] in {"enable", "disable"}:
                    return f"/api/v1/operations/rules/objects/{{family}}/{{id}}/state/{parts[8]}"
            return "/api/v1/<unmatched>"
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6:8] in (["recovery", "decision"], ["recovery", "metadata-search"])
        ):
            return f"/api/v1/tasks/{{task_id}}/items/{{item_id}}/recovery/{parts[7]}"
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "recovery-batches"
        ):
            return "/api/v1/tasks/{task_id}/recovery-batches/{batch_id}"
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
            and parts[6:8] == ["recovery", "prepare-summary"]
        ):
            return "/api/v1/tasks/{task_id}/items/{item_id}/recovery/prepare-summary"
        if (
            len(parts) == 8
            and parts[:3] == ["api", "v1", "tasks"]
            and parts[4] == "items"
            and parts[6:8] == ["recovery", "authorize-organize"]
        ):
            return "/api/v1/tasks/{task_id}/items/{item_id}/recovery/authorize-organize"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "manual-recovery-preparations"]
            and parts[4] == "confirm"
        ):
            return "/api/v1/manual-recovery-preparations/{id}/confirm"
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
        if len(parts) == 5 and parts[:3] == ["api", "v1", "schedules"] and parts[4] == "audit":
            return "/api/v1/schedules/{id}/audit"
        if (
            len(parts) == 5
            and parts[:3]
            in (
                ["api", "v1", "files"],
                ["api", "v1", "resource-libraries"],
            )
            and parts[4] in {"preview", "previews"}
        ):
            return f"/api/v1/{parts[2]}/{{id}}/{parts[4]}"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "resource-libraries"]:
            return "/api/v1/resource-libraries/{id}"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "storages"]:
            # The Storage Add/Edit surface is audited by template so the exact
            # Storage ID never appears in security audit route evidence.
            return "/api/v1/storages/{id}"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "storages"]
            and parts[4] in {"copy", "enable", "disable"}
        ):
            return f"/api/v1/storages/{{id}}/{parts[4]}"
        if len(parts) == 5 and parts[:3] == ["api", "v1", "storages"] and parts[4] == "edit":
            return "/api/v1/storages/{id}/edit"
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "resource-libraries"]
            and parts[4:6] == ["files", "deletes"]
        ):
            return "/api/v1/resource-libraries/{id}/files/deletes/{taskId}"
        if (
            len(parts) == 5
            and tuple(parts[:3])
            in {
                ("api", "v1", "resource-libraries"),
                ("api", "v1", "media-libraries"),
            }
            and parts[4] == "file-operations"
        ):
            # The library-owned ordinary file-operation history names no Task
            # identity in security audit route evidence.
            return f"/api/v1/{parts[2]}/{{id}}/file-operations"
        if (
            len(parts) == 4
            and tuple(parts[:3])
            in {
                ("api", "v1", "resource-libraries"),
                ("api", "v1", "media-libraries"),
            }
            and parts[3] == "operation-origins"
        ):
            # The bounded origin index names no library or Task identity.
            return f"/api/v1/{parts[2]}/operation-origins"
        if (
            len(parts) == 7
            and tuple(parts[:3])
            in {
                ("api", "v1", "resource-libraries"),
                ("api", "v1", "media-libraries"),
            }
            and parts[4:6] == ["files", "operations"]
        ):
            return f"/api/v1/{parts[2]}/{{id}}/files/operations/{{taskId}}"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "files"]
            and parts[3] == "operation-origin"
        ):
            return "/api/v1/files/operation-origin/{taskId}"
        if (
            len(parts) == 7
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4:6] == ["files", "deletes"]
        ):
            return "/api/v1/media-libraries/{id}/files/deletes/{taskId}"
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
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
        ):
            return "/api/v1/media-libraries/{id}/files"
        if (
            len(parts) == 6
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "files"
            and parts[5]
            in {
                "text",
                "delete-impact",
                "rename-evidence",
                "transfer-impact",
                "commands",
                "transfers",
            }
        ):
            # The media command and transfer surfaces are audited under their
            # own path template, never folded into the resource-libraries one.
            return f"/api/v1/media-libraries/{{id}}/files/{parts[5]}"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "media-libraries"]
            and parts[4] == "removal-preview"
        ):
            return "/api/v1/media-libraries/{id}/removal-preview"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "media-libraries"]:
            return "/api/v1/media-libraries/{id}"
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

        can_preview = ApiPermission.MANAGE_MANUAL_ORGANIZE in principal.permissions
        can_execute = ApiPermission.EXECUTE_MANUAL_ORGANIZE in principal.permissions
        configuration_snapshot_id = getattr(binding, "snapshot_id", None)
        # Determine runtime readiness: the binding has a snapshot_id when a
        # configuration has been activated and loaded.
        runtime_ready = bool(configuration_snapshot_id)
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
        organize_available = (
            can_execute
            and can_preview
            and runtime_ready
            and intent_service_ready
            and preview_intent_ready
            and execution_service_ready
            and bool(organize_worker["ready"])
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
            organize_available = False
            organize_reason = "select an exact scope before organizing"
        elif raw_kind == "file":
            if not isinstance(file_id, str) or not file_id.strip():
                raise ValueError("manual action matrix fileId is required for file scope")
            # A single-file admission is made from the live library directory, not
            # from a remembered catalog identity.  This bounded matrix therefore
            # states the exact prerequisite instead of resolving a file ID.
            rl_info = rl_map.get(resource_library_id)
            organize_available = False
            if rl_info is None or not rl_info.get("enabled", False):
                organize_reason = "the configured ResourceLibrary is not available"
            else:
                organize_reason = (
                    "select the live file from the ResourceLibrary directory to organize it"
                )
        else:
            if file_id is not None:
                raise ValueError("manual action matrix file scope is required for resource_library")
            if not isinstance(resource_library_id, str) or not resource_library_id.strip():
                # Bounded discovery: the operator has not selected an exact
                # ResourceLibrary yet, so nothing is actionable.
                selection_required = True
                organize_available = False
                organize_reason = "select an exact ResourceLibrary scope before organizing"
            else:
                rl_info = rl_map.get(resource_library_id)
                if rl_info is None or not rl_info.get("enabled", False):
                    organize_available = False
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
                        "organize": {
                            "available": organize_available,
                            "reason": organize_reason,
                            "method": "POST",
                            "path": (
                                f"/api/v1/resource-libraries/{resource_library_id}"
                                "/files/discoveries"
                                if raw_kind == "resource_library"
                                else ""
                            ),
                            "nextAction": (
                                "select the live files in the library directory, then review the "
                                "prepared summary"
                                if organize_available
                                else organize_reason
                            ),
                            "modes": [],
                        },
                    },
                    "limits": {
                        "organizeMaxItems": MAX_MANUAL_INTENT_ITEMS if can_preview else 0,
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
            "run_items": "item_id",
            "run_problem_items": "item_id",
            "run_records": "record_id",
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
            if kind in {"operational_logs", "run_records"}
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
    def _media_library_files_query(cls, environ: dict, media_library_id: str) -> dict[str, object]:
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"path", "limit", "cursor"}
        if set(query).difference(allowed) or any(len(value) != 1 for value in query.values()):
            raise ValueError("MediaLibrary Files query contains unsupported or repeated fields")
        if not media_library_id:
            raise ValueError("MediaLibrary Files route requires mediaLibraryId")
        cursor = query.get("cursor", [None])[0]
        if cursor == "":
            raise ValueError("MediaLibrary Files cursor must not be empty")
        return {
            "media_library_id": media_library_id,
            "path": query.get("path", [""])[0],
            "limit": cls._parse_bounded_limit(query.get("limit", ["50"])[0], "Files"),
            "cursor": cursor,
        }

    # ------------------------------------------------------------------
    # Shared direct-command transport for both library kinds
    #
    # Slice 38 RO-7: API and Web must use the same application behavior, and the
    # ResourceLibrary and MediaLibrary journeys must do so through *independent*
    # library authority.  One implementation therefore serves both kinds and is
    # given only the kind-selected service; nothing here chooses a library, a
    # Storage, a root or a path — that is the service's job.
    # ------------------------------------------------------------------

    @staticmethod
    def _direct_command_service(binding: _ApiRuntimeBinding, *, media_library: bool):
        """The one kind-pinned service a direct command may use, or ``None``."""

        return binding.direct_media_files if media_library else binding.direct_files

    def _files_direct_text_read(
        self,
        start_response: Callable,
        binding: _ApiRuntimeBinding,
        library_id: str,
        environ: dict,
        *,
        media_library: bool = False,
    ):
        service = self._direct_command_service(binding, media_library=media_library)
        if service is None:
            return self._files_browser_unavailable(start_response)
        path = self._files_direct_text_query(environ)
        document = service.read_text(library_id=library_id, path=path)
        return self._response(
            start_response,
            200,
            {
                **document.document(),
                "sideEffects": "none",
                "retrySafe": True,
            },
        )

    def _files_direct_delete_impact(
        self,
        start_response: Callable,
        binding: _ApiRuntimeBinding,
        library_id: str,
        environ: dict,
        *,
        media_library: bool = False,
    ):
        service = self._direct_command_service(binding, media_library=media_library)
        if service is None:
            return self._files_browser_unavailable(start_response)
        paths = self._files_delete_impact_query(environ)
        document = service.delete_impact(library_id=library_id, paths=paths)
        response = document.document()
        response["sideEffects"] = "none"
        response["retrySafe"] = True
        response["nextAction"] = (
            "confirm this exact impact to run the bounded Delete"
            if document.entries
            else "the selection is empty; refresh the directory and retry"
        )
        return self._response(start_response, 200, response)

    def _files_direct_rename_evidence(
        self,
        start_response: Callable,
        binding: _ApiRuntimeBinding,
        library_id: str,
        environ: dict,
        *,
        media_library: bool = False,
    ):
        service = self._direct_command_service(binding, media_library=media_library)
        if service is None:
            return self._files_browser_unavailable(start_response)
        path = self._files_direct_rename_evidence_query(environ)
        evidence = service.rename_evidence(library_id=library_id, path=path)
        response = evidence.document()
        response["sideEffects"] = "none"
        response["retrySafe"] = True
        response["nextAction"] = (
            "submit the Rename with this exact evidence, or refresh the directory "
            "if the entry changed in the meantime"
        )
        return self._response(start_response, 200, response)

    def _files_direct_command(
        self,
        start_response: Callable,
        binding: _ApiRuntimeBinding,
        library_id: str,
        environ: dict,
        *,
        media_library: bool,
    ):
        service = self._direct_command_service(binding, media_library=media_library)
        if service is None:
            return self._files_browser_unavailable(start_response)
        self._require_empty_query(environ, "Files direct command")
        document = self._document(environ)
        if not isinstance(document, dict) or "operation" not in document:
            raise ValueError("a Files direct command requires an operation")
        operation = document["operation"]
        if operation == DirectFileOperation.CREATE_DIRECTORY.value:
            required = {"operation", "parentPath", "name"}
            if set(document) != required:
                raise ValueError("Create Folder requires only operation, parentPath, and name")
            result = service.create_directory(
                library_id=library_id,
                parent_path=document["parentPath"],
                name=document["name"],
            )
        elif operation == DirectFileOperation.CREATE_TEXT.value:
            required = {"operation", "parentPath", "name", "content"}
            if set(document) != required:
                raise ValueError(
                    "Create Text File requires only operation, parentPath, name, and content"
                )
            result = service.create_text(
                library_id=library_id,
                parent_path=document["parentPath"],
                name=document["name"],
                content=document["content"],
            )
        elif operation == DirectFileOperation.RENAME.value:
            required = {"operation", "path", "name", "expected"}
            if set(document) != required:
                raise ValueError("Rename requires only operation, path, name, and expected")
            result = service.rename(
                library_id=library_id,
                path=document["path"],
                name=document["name"],
                expected=document["expected"],
            )
        elif operation == DirectFileOperation.SAVE_TEXT.value:
            required = {"operation", "path", "content", "expected"}
            if set(document) != required:
                raise ValueError("Text Save requires only operation, path, content, and expected")
            result = service.save_text(
                library_id=library_id,
                path=document["path"],
                content=document["content"],
                expected=document["expected"],
            )
        elif operation == DirectFileOperation.DELETE.value:
            required = {"operation", "paths", "confirmationDigest"}
            if frozenset(document) not in {
                frozenset(required),
                frozenset(required | {"requestId"}),
            }:
                raise ValueError(
                    "Delete requires operation, paths, confirmationDigest, and optional requestId"
                )
            result = service.submit_delete(
                library_id=library_id,
                paths=document["paths"],
                confirmation_digest=document["confirmationDigest"],
                request_id=document.get("requestId"),
            )
            result = self._with_transfer_worker_readiness(result, media_library=media_library)
            return self._response(start_response, 202, result)
        else:
            raise ValueError("the Files direct command operation is not supported")
        return self._response(start_response, 200, result)

    def _files_direct_delete_status(
        self,
        start_response: Callable,
        binding: _ApiRuntimeBinding,
        library_id: str,
        task_id: str,
        *,
        media_library: bool = False,
    ):
        """Read the kind/library-bound durable outcome without Storage access."""

        service = self._durable_transfer_reader(binding, media_library=media_library)
        if service is None:
            return self._files_browser_unavailable(start_response)
        projection = service.delete_projection(task_id, library_id=library_id)
        return self._response(
            start_response,
            200,
            self._with_transfer_worker_readiness(projection, media_library=media_library),
        )

    def _library_file_operation_history(self, *, media_library: bool | None = False):
        """The kind-pinned durable history reader over this process's rows.

        ``media_library=None`` builds a reader whose scope is still decided by the
        exact kind-pinned query, but whose *deep-link resolution* reads the kind
        from the Task's own durable command (see ``resolve``).
        """

        if self._repository is None:
            return None
        return LibraryFileOperationHistoryService(
            self._repository,
            library_kind=(LibraryKind.MEDIA if media_library else LibraryKind.RESOURCE),
        )

    def _library_file_operations_page(
        self,
        start_response: Callable,
        environ: dict,
        principal: ResolvedApiPrincipal,
        library_id: str,
        *,
        media_library: bool,
    ):
        """One bounded page of this library's ordinary file operations.

        The submitted cursor (if any) is bound to the exact library kind/ID it
        was minted for and to the reading principal, so a cursor from another
        kind, library or principal is refused as an invalid cursor instead of
        being re-bound to a different population.
        """

        history = self._library_file_operation_history(media_library=media_library)
        if history is None:
            return self._error(
                start_response,
                503,
                "library_file_operations_unavailable",
                "the durable library file-operation history is unavailable",
                details={
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": "restore database access, then refresh this page",
                },
            )
        scope = (
            f"media={int(media_library)};principal={principal.principal_id};library={library_id}"
        )
        limit, cursor = self._scoped_page_query(
            environ, "library_file_operations", scope, "Library file operations"
        )
        try:
            if cursor is not None and cursor.direction is CursorDirection.PREVIOUS:
                document = history.window(
                    library_id=library_id, limit=limit, before=cursor.position
                )
            else:
                document = history.window(
                    library_id=library_id,
                    limit=limit,
                    after=cursor.position if cursor else None,
                )
        except LibraryFileOperationError as error:
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details={"sideEffects": "none", "retrySafe": True},
            )
        items = document.pop("items") if isinstance(document.get("items"), list) else []
        previous_cursor = None
        next_cursor = None
        if items and document.get("hasPrevious"):
            previous_cursor = encode_cursor(
                "library_file_operations",
                datetime.fromisoformat(str(items[0]["createdAt"])),
                str(items[0]["taskId"]),
                CursorDirection.PREVIOUS,
                scope=scope,
            )
        if items and document.get("hasNext"):
            next_cursor = encode_cursor(
                "library_file_operations",
                datetime.fromisoformat(str(items[-1]["createdAt"])),
                str(items[-1]["taskId"]),
                CursorDirection.NEXT,
                scope=scope,
            )
        return self._response(
            start_response,
            200,
            {
                **document,
                "items": items,
                "previousCursor": previous_cursor,
                "nextCursor": next_cursor,
            },
        )

    def _library_file_operation_detail(
        self,
        start_response: Callable,
        environ: dict,
        principal: ResolvedApiPrincipal,
        library_id: str,
        task_id: str,
        *,
        media_library: bool,
        binding=None,
    ):
        """One exact ordinary operation of this library.

        The document is the durable read plus the backend-computed lifecycle
        projection for this exact Task and principal.  A control therefore
        exists only when the backend advertises it for the current durable
        state; the read itself performs no Storage work, and this route never
        executes the control it advertises.
        """

        history = self._library_file_operation_history(media_library=media_library)
        if history is None:
            return self._error(
                start_response,
                503,
                "library_file_operations_unavailable",
                "the durable library file-operation history is unavailable",
                details={"sideEffects": "none", "retrySafe": True},
            )
        # The per-item page of this exact operation.  Its cursor is bound to the
        # library kind/ID, the Task and the reading principal, so a cursor
        # minted for another operation or another caller is refused as an
        # invalid cursor instead of being re-bound to a different item window.
        scope = (
            f"media={int(media_library)};principal={principal.principal_id};"
            f"library={library_id};task={task_id}"
        )
        limit, cursor = self._scoped_page_query(
            environ, "library_file_operation_items", scope, "Library file operation item"
        )
        if cursor is not None and cursor.direction is CursorDirection.PREVIOUS:
            # An item page only ever publishes a forward continuation, so a
            # previous-direction cursor was not minted for this surface.  It is
            # refused as an invalid cursor instead of being read as a forward
            # position, which would silently re-serve the wrong item window.
            raise ValueError("Library file operation item cursor direction is invalid")
        try:
            document = history.detail(
                library_id=library_id,
                task_id=task_id,
                limit=limit,
                after=cursor.position if cursor is not None else None,
            )
        except LibraryFileOperationError as error:
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details={"sideEffects": "none", "retrySafe": True},
            )
        task = self._repository.get_task(str(document["taskId"]))
        if task is not None:
            service = TaskLifecycleService(
                self._repository,
                snapshot_validator=self._scope_continuations._snapshot_validator,
                mutation_authority=(
                    binding.scope_continuation_authority if binding is not None else None
                ),
            )
            results = service.results(task.task_id)
            document["lifecycle"] = self._task_lifecycle(
                service,
                task,
                principal,
                results=results,
            )
        position = document.pop("nextItemPosition", None)
        next_cursor = None
        if isinstance(position, dict):
            try:
                next_cursor = encode_cursor(
                    "library_file_operation_items",
                    datetime.fromisoformat(str(position["createdAt"])),
                    str(position["itemId"]),
                    CursorDirection.NEXT,
                    scope=scope,
                )
            except (KeyError, TypeError, ValueError):
                next_cursor = None
        return self._response(start_response, 200, {**document, "nextCursor": next_cursor})

    def _library_file_operation_origins(
        self,
        start_response: Callable,
        environ: dict,
        *,
        media_library: bool,
    ):
        """The bounded distinct origins of this kind's ordinary work."""

        history = self._library_file_operation_history(media_library=media_library)
        if history is None:
            return self._error(
                start_response,
                503,
                "library_file_operations_unavailable",
                "the durable library file-operation history is unavailable",
                details={"sideEffects": "none", "retrySafe": True},
            )
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit"}) or any(len(value) != 1 for value in values.values()):
            raise ValueError("Library file operation origins accepts only one limit")
        limit = self._parse_bounded_limit(values.get("limit", ["50"])[0], "origin")
        try:
            document = history.origins(limit=limit)
        except LibraryFileOperationError as error:
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details={"sideEffects": "none", "retrySafe": True},
            )
        return self._response(start_response, 200, document)

    def _library_file_operation_origin(
        self,
        start_response: Callable,
        environ: dict,
        task_id: str,
        *,
        media_library: bool | None,
    ):
        """Resolve one Task deep link to its proven ordinary library origin.

        ``media_library=None`` means the caller submitted no kind: the origin is
        then read from the Task's own durable command, so one shared route serves
        both library kinds and neither can claim the other's work.
        """

        self._require_empty_query(environ, "Library file operation origin")
        history = self._library_file_operation_history(media_library=None)
        if history is None:
            return self._error(
                start_response,
                503,
                "library_file_operations_unavailable",
                "the durable library file-operation history is unavailable",
                details={"sideEffects": "none", "retrySafe": True},
            )
        try:
            document = history.resolve(task_id=task_id)
        except LibraryFileOperationError as error:
            return self._error(
                start_response,
                error.status,
                error.code,
                str(error),
                details={"sideEffects": "none", "retrySafe": True},
            )
        if media_library is not None and document.get("matched") is True:
            expected = "media" if media_library else "resource"
            if document.get("libraryKind") != expected:
                # A caller that submitted its own kind is answered in that kind's
                # terms: a Task of the other kind is a bounded non-match, never a
                # foreign origin.
                document = {
                    "matched": False,
                    "taskId": document["taskId"],
                    "reason": "not_ordinary_file_work",
                    "nextAction": "open the exact Task detail in Operations",
                    "sideEffects": "none",
                }
        return self._response(start_response, 200, document)

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
                "storageFingerprint",
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
                "storageFingerprint",
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
                "current-source Preview accepts only bounded source identity and snapshot fields"
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
        if parts[:4] == ["api", "v1", "automation", "task-definitions"] and (
            len(parts) in {4, 5}
            or (len(parts) == 6 and parts[5] in {"occurrences", "grant", "grant-state"})
            or (len(parts) == 7 and parts[5:7] == ["grant", "audit"])
        ):
            return True
        return (
            parts == ["api", "v1", "storage", "files"]
            or (
                len(parts) == 5
                and parts[:3] == ["api", "v1", "resource-libraries"]
                and parts[4] == "files"
            )
            or parts == ["api", "v1", "media-libraries"]
            or (
                len(parts) == 5
                and parts[:3] == ["api", "v1", "media-libraries"]
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

    def _automation_definition_context_historical(self, environ: dict, definition_id: str):
        """Read context plus durable historical evidence for retained history.

        Resolution order is Active, then the newest published non-Active
        revision backed by durable activation evidence (pinned by the
        definition's latest occurrence when one exists).  An unpublished Draft
        candidate is never substituted: it was never the published
        configuration the removed run used.  Returns
        ``(active, raw, definition, historical)``; grants no authority and
        creates nothing.  Mutating journeys must not use this helper: granting
        or previewing a removed definition stays impossible.
        """

        try:
            active, raw, definition = self._automation_definition_context(environ, definition_id)
            return active, raw, definition, False
        except LookupError:
            pass
        if self._automation_workspace is None:
            raise LookupError(f"automationTaskDefinitions {definition_id!r} was not found")
        historical_projection = self._automation_workspace.historical_definition(
            definition_id, occurrence=self._automation_occurrences.latest(definition_id)
        )
        if historical_projection is None:
            raise LookupError(f"automationTaskDefinitions {definition_id!r} was not found")
        active = self._automation_revision({**environ, "QUERY_STRING": ""})
        raw = historical_projection.get("definition")
        if not isinstance(raw, dict):
            raise LookupError(f"automationTaskDefinitions {definition_id!r} was not found")
        try:
            definition = AutomationTaskDefinition.from_document(raw)
        except (TypeError, ValueError) as error:
            raise LookupError(
                f"automationTaskDefinitions {definition_id!r} was not found"
            ) from error
        return active, raw, definition, True

    def _automation_definition_resolution(self, definition_id: str, start_response: Callable):
        """Resolve a definition from the Active revision, then durable history.

        Returns ``(active, raw, definition, draft, in_active, historical)``.
        Newly created or copied definitions exist only inside an open successor
        Draft until activation, so the Draft document remains available for
        explicit correction through the draft route; it is never presented as
        the Active configuration and — for a removed definition's retained
        history — its unpublished candidate is never substituted as the run's
        historical context.  A removed definition resolves last from the newest
        published non-Active revision backed by durable activation evidence
        (pinned by the retained occurrence when one exists), so retained
        occurrence/history links stay readable after removal and restart —
        always labelled historical and never substituted for today's
        configuration or revived as authority.
        Returns the bounded 503 response when the configuration or Draft read
        fails (callers must return it unchanged); a definition found in no
        source raises ``LookupError`` exactly as the Active-only context did.
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
        historical = False
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
            draft_candidate = next(
                (
                    item
                    for item in section
                    if isinstance(item, dict) and item.get("id") == definition_id
                ),
                None,
            )
            if draft_candidate is not None and not (
                self._automation_workspace is not None
                and self._automation_workspace.definition_was_published(definition_id)
            ):
                # A definition that exists only inside an open Draft is a
                # draft-only candidate for explicit correction.  A definition
                # that was once published and is no longer Active is removed:
                # its retained history resolves from published evidence below
                # and the Draft candidate is never substituted for it.
                raw = draft_candidate
        if raw is None:
            # Last resort: the durable historical evidence.  A removed
            # definition's newest published revision keeps its exact name,
            # scope, mode and schedule readable so retained occurrences and
            # linked results resolve without substituting current
            # configuration or an unpublished Draft candidate.  This is a
            # bounded read-only fallback; it grants no authority and creates
            # nothing.
            historical_projection = (
                self._automation_workspace.historical_definition(
                    definition_id,
                    occurrence=self._automation_occurrences.latest(definition_id),
                )
                if self._automation_workspace is not None
                else None
            )
            if historical_projection is not None:
                raw = historical_projection.get("definition")
                historical = True
                in_active = False
        if raw is None:
            raise LookupError(f"automationTaskDefinitions {definition_id!r} was not found")
        return active, raw, definition, draft, in_active, historical

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

    def _discovery_unavailable(self, start_response: Callable) -> list[bytes]:
        return self._error(
            start_response,
            503,
            "service_unavailable",
            "bounded folder discovery is unavailable",
            details={
                "durableState": "no_discovery_created",
                "sideEffects": "none",
                "retrySafe": True,
                "nextAction": (
                    "restore the discovery service and Processing Worker, then reload the "
                    "Operations task center"
                ),
            },
        )

    def _discovery_step_error(self, start_response: Callable, error) -> list[bytes]:
        """One bounded, secret-free failure for a discovery step."""

        return self._error(
            start_response,
            int(getattr(error, "status", 409) or 409),
            str(getattr(error, "code", "discovery_rejected") or "discovery_rejected"),
            str(error),
            details={
                "nextAction": getattr(error, "next_action", None),
                "durableState": (
                    "rejected_without_mutation"
                    if int(getattr(error, "status", 409) or 409) < 500
                    else "rejection_unconfirmed"
                ),
                "sideEffects": "none",
                "retrySafe": int(getattr(error, "status", 409) or 409) < 500,
                **{
                    key: value
                    for key, value in dict(getattr(error, "details", {}) or {}).items()
                    if key not in {"nextAction", "sideEffects", "retrySafe", "durableState"}
                },
            },
        )

    def _discovery_document(
        self,
        discovery,
        principal,
        binding,
        *,
        include_sources: bool = True,
        requested_by: str | None = None,
    ):
        """The bounded, secret-free operator projection of one discovery.

        It publishes exact relative scopes, progress, counters, bounded findings
        and a native next action.  It never publishes a claim token, a
        configuration digest, a fingerprint, an occurrence ID or a physical
        Storage path.
        """

        progress = discovery.progress
        counters = progress.counters
        incomplete = progress.incomplete_reason
        # The durable, monotonic material refusal is the single authority for
        # the finalize gate: an ordinary read failure in another subtree can
        # never re-enable Finalize for a truncated or unconfined walk.
        material_refusal = discovery_material_refusal(progress)
        terminal = discovery.status in TERMINAL_DISCOVERY_STATUSES
        frozen = discovery.intent_id is not None
        worker = self._discovery_worker_evidence(binding)
        can_manage = ApiPermission.MANAGE_MANUAL_ORGANIZE in principal.permissions
        next_action = self._discovery_next_action(
            discovery, terminal=terminal, frozen=frozen, worker_ready=worker["ready"]
        )
        analysis_available, analysis_refusal, analysis_next_action, analysis_pending = (
            self._media_discovery.analysis_availability(discovery)
            if self._media_discovery is not None
            else (False, "discovery_not_preparation", None, False)
        )
        # The per-request admission outcome: which items of *this* request were
        # admitted, which already belonged to the same durable work, and which of
        # this request's own items were refused.  A converging request is answered
        # with its own evidence, never with the first request's; a read without a
        # request identity falls back to the shared work evidence.
        request_outcome = self._discovery_request_outcome(discovery, requested_by)
        if request_outcome is not None:
            admitted_entries = request_outcome.admitted
            existing_entries = request_outcome.existing
            refused_documents = [item.document() for item in request_outcome.refused]
            selection_scope_count = len(request_outcome.scope)
            echoed_request_id = request_outcome.request_id
        else:
            admitted_entries = progress.scope_entries
            existing_entries = ()
            refused_documents = [item.document() for item in progress.refused_entries]
            selection_scope_count = len(progress.scope_entries)
            echoed_request_id = discovery.admission_request_id
        document: dict[str, object] = {
            "journey": "discovery",
            "discoveryId": discovery.discovery_id,
            "resourceLibraryId": discovery.resource_library_id,
            "storageId": discovery.storage_id,
            "configurationSnapshotId": discovery.snapshot_id,
            "status": discovery.status.value,
            "version": discovery.version,
            "createdAt": discovery.created_at.isoformat(),
            "updatedAt": discovery.updated_at.isoformat(),
            "selection": {
                "scopeCount": selection_scope_count,
                "scopes": [
                    {"path": item.path, "kind": item.kind.value} for item in admitted_entries
                ],
                # Items of the same request that the same durable work already
                # holds.  They are not duplicated execution and are not a refusal
                # either: the operator sees the exact existing work.
                "existing": [
                    {"path": item.path, "kind": item.kind.value} for item in existing_entries
                ],
                "existingCount": len(existing_entries),
                # RO-2/AC-16: the selected items this request refused, with their
                # own bounded reason and next action.  They are durable evidence of
                # this request, never a silent drop, so the operator sees the exact
                # refused item beside the eligible siblings that really became
                # organizing work.
                "refused": refused_documents,
                "refusedCount": len(refused_documents),
            },
            "budgets": discovery.budgets.document(),
            "progress": {
                "phase": progress.phase,
                "visitedEntries": counters.visited_entries,
                "visitedDirectories": counters.visited_directories,
                "pageFetches": counters.page_fetches,
                "primarySources": len(discovery.sources),
                "excludedEntries": counters.excluded_entries,
                "unstableEntries": counters.unstable_entries,
                "errorEntries": counters.error_entries,
                "activeSeconds": round(counters.active_seconds, 3),
                "incomplete": incomplete is not DiscoveryIncompleteReason.NONE,
                "incompleteReason": (
                    None if incomplete is DiscoveryIncompleteReason.NONE else incomplete.value
                ),
                # The durable, monotonic material refusals of this walk.  They
                # survive a later ordinary read failure, a later pass and a
                # restart, so the operator can always see why Finalize stays
                # refused even when the current dominant fact is a read failure.
                "refusalReasons": [item.value for item in progress.refusal_reasons],
                "materialRefusal": (None if material_refusal is None else material_refusal.value),
                "findings": [item.document() for item in progress.findings],
                "reasons": [item.document() for item in progress.reasons],
                "message": progress.message,
            },
            "primarySourceCount": len(discovery.sources),
            # The caller's own admission request identity, echoed so a client
            # that lost the admission response can prove which durable record
            # its request actually became.  It is the client's own value and
            # reveals nothing about the server, the pin or the Storage path.
            "admissionRequestId": echoed_request_id,
            # The exact durable shape of *this* request's result, so a client can
            # read admitted/existing/refused beside the shared progress without
            # merging another request's evidence.
            "request": (None if request_outcome is None else request_outcome.document()),
            # The durable organizing Task this admitted Files selection created, so
            # the operator (and a reload) can open the exact task context instead
            # of inferring one from a recent list.
            "organizeTaskId": discovery.organize_task_id,
            "autoPrepare": discovery.auto_prepare,
            "prepared": discovery.prepared,
            "previewId": discovery.preview_id,
            "recoverySourceTaskId": discovery.recovery_source_task_id,
            "intentId": discovery.intent_id,
            "frozen": frozen,
            "frozenAt": (
                discovery.frozen_at.isoformat() if discovery.frozen_at is not None else None
            ),
            "pauseRequested": discovery.pause_requested,
            "cancelRequested": discovery.cancel_requested,
            # The durable instant at which waiting work may be re-observed.  It
            # is published so the operator can see that a still-waiting
            # discovery is deliberately idle rather than stalled.
            "nextObservationAt": (
                discovery.next_observation_at.isoformat()
                if discovery.next_observation_at is not None
                else None
            ),
            "worker": worker,
            "actions": {
                "pause": {
                    "available": can_manage and not terminal and not discovery.pause_requested,
                    "method": "POST",
                    "path": (
                        f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/pause"
                    ),
                    "requiresVersion": True,
                    "sideEffects": "none",
                },
                "cancel": {
                    "available": can_manage and not terminal and not discovery.cancel_requested,
                    "method": "POST",
                    "path": (
                        f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/cancel"
                    ),
                    "requiresVersion": True,
                    "sideEffects": "none",
                },
                "resume": {
                    # Continue is only offered once the resident Worker has
                    # *acknowledged* the pause at its safe boundary: only then
                    # has the interrupted pass's bounded work been settled and
                    # the claim released.  A pending pause is a real transient
                    # state, so the action is not advertised yet and the
                    # application refuses a premature or stale-client Continue
                    # with the same rule instead of accepting it and stranding
                    # the record.  Cancellation keeps its own terminal path.
                    "available": can_manage
                    and discovery.pause_requested
                    and discovery.status is DiscoveryStatus.PAUSED
                    and not terminal,
                    "method": "POST",
                    "path": (
                        f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/resume"
                    ),
                    "requiresVersion": True,
                    "sideEffects": "none",
                    "pendingReason": (
                        "discovery_pause_pending"
                        if (
                            discovery.pause_requested
                            and discovery.status is not DiscoveryStatus.PAUSED
                            and not terminal
                        )
                        else None
                    ),
                },
                "finalize": {
                    "available": can_manage
                    and not frozen
                    and bool(discovery.sources)
                    and discovery.status
                    in {DiscoveryStatus.COMPLETED, DiscoveryStatus.PARTIAL_SUCCESS}
                    # A budget/safety/cursor/unsafe-entry-limited walk recorded
                    # a truncated or unconfined prefix, never a complete scope:
                    # the backend refuses to freeze it, so the action is not
                    # advertised either.  The refusal is durable and monotonic,
                    # so a later ordinary read failure cannot re-enable it.  An
                    # ordinary read-failure-only subset keeps its explicit-review
                    # path and stays available.
                    and material_refusal is None,
                    "method": "POST",
                    "path": (
                        f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/finalize"
                    ),
                    "requiresVersion": True,
                    "sideEffects": "none",
                    "durableOutcome": (
                        "one immutable deduplicated source list is linked to a durable manual "
                        "intent; a separate exact Preview and confirmed execution are still "
                        "required"
                    ),
                    "refusal": (
                        "discovery_budget_limited" if material_refusal is not None else None
                    ),
                },
                "prepare": {
                    # A full preparation that already linked its read-only plan
                    # summary can re-run the analysis after an operator
                    # correction on its linked intent.  Availability is the
                    # exact same predicate ``request_analysis`` enforces, so an
                    # advertised action can never disagree with the real
                    # admission.  It never grants execution authority.
                    "available": can_manage and analysis_available,
                    "method": "POST",
                    "path": (
                        f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze"
                    ),
                    "requiresVersion": True,
                    "sideEffects": "none",
                    "durableOutcome": (
                        "the resident Worker re-runs the complete zero-mutation analysis "
                        "under the same pinned configuration and links a new exact Preview"
                    ),
                    "reason": analysis_refusal,
                    "nextAction": analysis_next_action,
                    "pendingReason": ("discovery_analysis_pending" if analysis_pending else None),
                },
            },
            "nextAction": next_action,
            "failure": discovery.error,
            "sideEffects": "none",
            "zeroMutation": True,
            "execution": "not_available_from_discovery",
        }
        if include_sources:
            document["sources"] = [
                {
                    "path": str(value.get("path", "")),
                    "filename": str(value.get("filename", "")),
                    "extension": str(value.get("extension", "")),
                    "size": int(value.get("size", 0)),
                    "modifiedAt": value.get("modifiedAt"),
                }
                for value in discovery.sources
            ]
        return document

    def _discovery_request_outcome(self, discovery, requested_by: str | None):
        """One exact request's own resolved admission outcome, if it names one.

        The lookup is principal-bound and identity-bound: a request identity proves
        only the record it actually created, so a caller can never read another
        principal's or another request's per-item result.  ``None`` means no
        per-request evidence was recorded (an automatic admission, or a read without
        an identity), and the shared work evidence is then the honest answer.
        """

        if not requested_by:
            return None
        reader = getattr(self._repository, "find_media_discovery_admission_outcome", None)
        if not callable(reader):
            return None
        try:
            outcome = reader(actor=discovery.actor, admission_request_id=requested_by)
        except Exception:  # noqa: BLE001 - an unprovable outcome is a bounded absence
            return None
        return outcome

    def _files_organize_work(
        self,
        principal: ResolvedApiPrincipal,
        binding,
        *,
        resource_library_id: str,
        limit: int,
        before,
        request_id: str | None,
    ) -> dict[str, object]:
        """This principal's durable Files organizing work for one library.

        ``request_id`` is the lost-admission reconciliation read: it proves the exact
        admission *this* request created.  Without it the caller gets a bounded,
        cursor-paged list of its own work, so Files can reopen several known runs and
        never needs a recent-N guess.  A proved absence is an honest empty answer,
        and nothing in this read creates, resumes or re-submits work.
        """

        service = getattr(self, "_media_discovery", None)
        if service is None:
            return {"items": [], "nextBefore": None}
        reader = getattr(service, "find_by_request_id", None)
        if request_id is not None and callable(reader):
            try:
                found = reader(actor=principal.principal_id, admission_request_id=request_id)
            except DiscoveryError as error:
                raise ValueError(error.code) from error
            if found is None or found.resource_library_id != resource_library_id:
                return {"items": [], "nextBefore": None}
            return {
                "items": [self._files_organize_work_item(found, principal, binding, request_id)],
                "nextBefore": None,
            }
        lister = getattr(service, "list_files_work", None)
        if not callable(lister):
            return {"items": [], "nextBefore": None}
        try:
            values = lister(
                actor=principal.principal_id,
                resource_library_id=resource_library_id,
                limit=limit + 1,
                before=before,
            )
        except DiscoveryError as error:
            raise ValueError(error.code) from error
        page = tuple(values)[:limit]
        next_before = None
        if len(values) > limit and page:
            last = page[-1]
            next_before = f"{last.created_at.isoformat()}|{last.discovery_id}"
        return {
            "items": [
                self._files_organize_work_item(value, principal, binding, None) for value in page
            ],
            "nextBefore": next_before,
        }

    def _files_organize_work_item(
        self,
        discovery,
        principal: ResolvedApiPrincipal,
        binding,
        request_id: str | None,
    ) -> dict[str, object]:
        """One bounded Files work row: identity, stage and next action only.

        Files needs to reopen the exact context, so this publishes the durable
        identities and the real stage, never a claim token, a pin digest, a
        fingerprint or a physical Storage path.
        """

        document = self._discovery_document(
            discovery, principal, binding, include_sources=False, requested_by=request_id
        )
        scope = discovery.progress.scope_entries
        return {
            "discoveryId": discovery.discovery_id,
            "resourceLibraryId": discovery.resource_library_id,
            "organizeTaskId": discovery.organize_task_id,
            "intentId": discovery.intent_id,
            "previewId": discovery.preview_id,
            "status": discovery.status.value,
            "phase": discovery.progress.phase,
            "autoPrepare": discovery.auto_prepare,
            "prepared": discovery.prepared,
            "createdAt": discovery.created_at.isoformat(),
            "updatedAt": discovery.updated_at.isoformat(),
            "version": discovery.version,
            "scopeCount": len(scope),
            "scopes": [{"path": entry.path, "kind": entry.kind.value} for entry in scope[:20]],
            "selection": document["selection"],
            "admissionRequestId": document["admissionRequestId"],
            "nextAction": document["nextAction"],
            "failure": document["failure"],
        }

    def _discovery_worker_evidence(self, binding) -> dict[str, object]:
        """Whether a live resident Worker can actually consume this discovery.

        Process health alone never implies discovery can run: a live,
        schema-compatible Worker that does not advertise the ``media_discovery``
        command family would leave the admitted discovery queued forever.  The
        projection therefore reports the *command-specific* readiness of the
        same WorkerService the discovery Worker registers with, so the operator
        sees the real condition (missing/stale/schema/unsupported command) and
        its own meaningful next action.  Existing manual/transfer readiness is
        unaffected: this answers only the discovery command family.
        """

        service = self._worker_service
        evaluator = getattr(service, "evaluate_command_readiness", None)
        if service is None or not callable(evaluator):
            return {
                "ready": False,
                "condition": "no_worker",
                "durableState": "processing worker service is unavailable",
                "nextAction": "start the resident Processing Worker",
            }
        try:
            readiness = evaluator(("media_discovery",))
        except Exception:
            return {
                "ready": False,
                "condition": "no_worker",
                "durableState": "processing worker readiness could not be read",
                "nextAction": "inspect the resident Processing Worker and retry",
            }
        return {
            "ready": bool(readiness.get("ready")),
            "condition": readiness.get("condition"),
            "durableState": readiness.get("durableState"),
            "nextAction": readiness.get("nextAction"),
        }

    @staticmethod
    def _discovery_next_action(discovery, *, terminal: bool, frozen: bool, worker_ready: bool):
        if discovery.auto_prepare:
            if discovery.preview_id is not None:
                return (
                    "open the linked exact plan summary, review it and explicitly confirm the "
                    "ready subset to organize"
                )
            if discovery.status is DiscoveryStatus.ANALYZING:
                if not worker_ready:
                    return "start or repair the resident Processing Worker so the analysis can run"
                return "the resident Processing Worker is running the complete analysis"
            if discovery.terminal and discovery_material_refusal(discovery.progress) is not None:
                return (
                    "the selected scope exceeded a discovery budget; narrow the scope and start "
                    "a new preparation instead of freezing this incomplete subset"
                )
        if frozen:
            return "open the linked manual intent to review choices and create an exact Preview"
        if discovery.status is DiscoveryStatus.CANCELLED:
            return "start a new bounded discovery from Files if this scope is still wanted"
        if discovery.status is DiscoveryStatus.FAILED:
            return "inspect the recorded failure and start a new bounded discovery"
        if discovery.pause_requested:
            if discovery.status is DiscoveryStatus.PAUSED:
                return "continue the paused discovery to finish the admitted scope"
            # The pause is durable but not yet acknowledged at a safe boundary.
            # State the real transient stage instead of promising a Continue
            # that the backend will refuse until the acknowledgement lands.
            return (
                "the cooperative pause is waiting for the resident Processing Worker to "
                "acknowledge it at its safe boundary; continue the same discovery after "
                "the acknowledgement"
            )
        if discovery.cancel_requested:
            # An accepted cancellation that is not yet terminal is settled by the
            # resident Worker at its next safe boundary.  The readback states the
            # pending acknowledgement truthfully instead of promising more work.
            return (
                "the accepted cancellation is acknowledged by the resident Processing "
                "Worker at its next safe boundary; known findings are preserved and no "
                "execution authority is created"
            )
        if terminal and discovery_material_refusal(discovery.progress) is not None:
            # A budget/safety-limited walk is never an executable subset: the
            # native next action is the honest narrowing action, not finalize.
            return (
                "the selected scope exceeded a discovery budget; narrow the scope and start "
                "a new bounded discovery instead of freezing this incomplete subset"
            )
        if terminal and not discovery.sources:
            return "narrow the selected scope or correct the configured filters, then retry"
        if terminal:
            return "finalize the frozen source list, then review choices and Preview"
        if not worker_ready:
            return "start or repair the resident Processing Worker so discovery can continue"
        return "the resident Processing Worker continues this bounded discovery"

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

    def _organize_intent_analysis(self, intent_id: object, principal: ResolvedApiPrincipal):
        """The bounded durable-analysis projection of the intent's organize run.

        The same-page summary is built by the resident Worker on the intent's
        own durable run, so a reload, return or reconnect shows the real stage
        (observing/analyzing/paused/cancelled/prepared) instead of admitting a
        second inline analysis.  Only identity and stage facts are published;
        the complete plan is read from its own Preview detail route after
        normal authentication.
        """

        service = getattr(self, "_media_discovery", None)
        finder = getattr(service, "discovery_for_intent", None) if service is not None else None
        if not callable(finder) or not isinstance(intent_id, str) or not intent_id:
            return None
        try:
            discovery = finder(intent_id)
        except Exception:  # noqa: BLE001 - an unreadable run is a truthful absence
            return None
        if discovery is None:
            return None
        progress = discovery.progress
        can_manage = ApiPermission.MANAGE_MANUAL_ORGANIZE in principal.permissions
        terminal = discovery.status in TERMINAL_DISCOVERY_STATUSES
        base = f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}"
        return manual_intent_analysis_document(
            {
                "discoveryId": discovery.discovery_id,
                "status": discovery.status.value,
                "phase": progress.phase,
                "version": discovery.version,
                "frozen": discovery.intent_id is not None,
                "prepared": discovery.prepared,
                "previewId": discovery.preview_id,
                "pauseRequested": discovery.pause_requested,
                "cancelRequested": discovery.cancel_requested,
                "message": progress.message,
                "actions": {
                    "pause": {
                        "available": can_manage
                        and not terminal
                        and not discovery.pause_requested
                        and not discovery.cancel_requested,
                        "method": "POST",
                        "path": f"{base}/pause",
                        "requiresVersion": True,
                    },
                    "cancel": {
                        "available": can_manage and not terminal and not discovery.cancel_requested,
                        "method": "POST",
                        "path": f"{base}/cancel",
                        "requiresVersion": True,
                    },
                },
            }
        )

    def _organize_intent_latest_plan(self, intent_id: object) -> dict[str, object] | None:
        """Bounded identity of this intent's latest durable organize plan.

        A same-page plan summary is only ever projected from a durable record,
        so a browser reload, reconnect or restart re-reads the plan this intent
        already produced instead of admitting a second analysis.  The read is
        the bounded, non-publishing ``latest_readonly`` projection: it never
        marks evidence stale merely because the page was opened.  Only identity
        and lifecycle facts are published here; the complete plan is read from
        its own Preview detail route after normal authentication.
        """

        previews = getattr(self, "_manual_previews", None)
        if previews is None or not isinstance(intent_id, str) or not intent_id:
            return None
        latest_readonly = getattr(previews, "latest_readonly", None)
        if not callable(latest_readonly):
            return None
        try:
            preview = latest_readonly(intent_id)
        except ManualPreviewError:
            # No plan exists yet for this intent: the supported next action is
            # the explicit analysis the same page offers.
            return None
        return {
            "previewId": preview.preview_id,
            "status": preview.status.value,
            "current": bool(preview.current),
            "intentVersion": preview.intent_version,
            "createdAt": preview.created_at.isoformat(),
            "updatedAt": preview.updated_at.isoformat(),
            "truncated": bool(preview.truncated),
        }

    def _organize_intent_document(self, intent, principal: ResolvedApiPrincipal) -> dict:
        document = manual_intent_operator_document(intent.document(include_audit=False))
        document["journey"] = "organize"
        intent_id = document.get("intentId")
        # The durable plan association is read-only evidence: the intent page
        # restores the exact plan it already produced after a reload/return
        # without re-analysing, re-authorizing or guessing a recent Task.
        latest_plan = self._organize_intent_latest_plan(intent_id)
        document["latestPlan"] = (
            manual_intent_latest_plan_document(latest_plan) if latest_plan is not None else None
        )
        # The durable analysis stage of this intent's own organize run: the
        # same-page summary request records one versioned stage and the resident
        # Worker links the exact plan here.  A run without a linked intent is
        # still observing, and a paused/cancelled run explains its control
        # instead of re-advertising a superseded summary.
        document["analysis"] = self._organize_intent_analysis(intent_id, principal)
        items = [item for item in document.get("items") or [] if isinstance(item, dict)]
        open_intent = document.get("status") == "open"
        manage_permitted = ApiPermission.MANAGE_MANUAL_ORGANIZE in principal.permissions
        execute_permitted = ApiPermission.EXECUTE_MANUAL_ORGANIZE in principal.permissions
        # The bounded, source-grounded identity options per item.  These are
        # exactly the authorities a save re-validates against, so an ordinary
        # operator can make a legal identity correction without inventing a
        # provider payload or falling back to the standalone intent editor.
        self._attach_allowed_metadata_identities(document, items, intent)
        choice_reason = self._organize_unavailable_reason(
            manage_permitted,
            ApiPermission.MANAGE_MANUAL_ORGANIZE,
            "the connected API principal cannot edit this manual intent",
        ) or (
            None
            if open_intent and items
            else "this manual intent is closed and no longer accepts a choice edit"
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
            "execute": {
                "available": False,
                "reason": (
                    "exact execution is only offered from a current, complete fixed plan"
                    if execute_permitted
                    else "the connected API principal does not hold the "
                    "execute_manual_organize permission"
                ),
                "method": None,
                "path": None,
                "sideEffects": "none",
                "durableOutcome": None,
                "nextAction": ("generate a fresh analysis summary after the last choice change"),
            },
        }
        document["limits"] = {"intentMaxItems": self._organize_intent_limit()}
        return document

    def _recovery_batch_document(self, batch) -> dict:
        """Bound one batch and attach each child's durable same-page summary.

        A batch child that reached a completed linked analysis can be prepared
        into the same non-authorizing plan summary the per-item journey uses.
        The batch projection exposes each child's *current durable* preparation
        (identity, status, ready/not-ready and the linked execution) so the
        operator can aggregate the independent summaries in the task's own
        interface, select exactly the ready subset and confirm only those.  It
        creates nothing, mints no authority and never guesses a summary from a
        child's status; a child with no preparation simply has none.
        """

        document = batch.document()
        recovery = getattr(self, "_manual_recovery", None)
        items = document.get("items")
        if not isinstance(items, list):
            return document
        for child in items:
            if not isinstance(child, dict):
                continue
            source_item_id = child.get("source_item_id")
            if not isinstance(source_item_id, str) or not source_item_id:
                continue
            if recovery is not None:
                try:
                    preparation = recovery.discovery_for_preparation(
                        batch.source_task_id, source_item_id
                    )
                except Exception:
                    preparation = None
                if preparation is not None:
                    child["manualRecoveryPreparation"] = preparation
            try:
                checkpoint = self._checkpoint_service.get(
                    source_item_id, task_id=batch.source_task_id
                )
            except Exception:
                checkpoint = None
            if checkpoint is not None:
                # The current durable checkpoint version lets the batch
                # interface prepare this child's own summary without guessing
                # the version the operator selected before the analysis ran.
                child["currentCheckpointVersion"] = checkpoint.checkpoint_version
                child["recoveryContinuationStatus"] = (
                    checkpoint.recovery_continuation.status.value
                    if checkpoint.recovery_continuation is not None
                    else None
                )
            # The same bounded per-item decision the item page and item panel
            # publish.  A saved batch that contains a technical-history child
            # (created before the center contraction or through the preserved
            # administrative API) cannot offer that child a new four-type
            # summary/confirmation action here.  The management API itself is
            # unchanged.
            child["recoveryKind"] = self._task_item_recovery.recovery_kind(
                source_item_id,
                has_blocker=(checkpoint is not None and checkpoint.blocker is not None),
            )
            if recovery is not None:
                try:
                    child["manualRecoveryAvailable"] = recovery.supports_source_item(
                        batch.source_task_id, source_item_id
                    )
                except Exception:
                    child["manualRecoveryAvailable"] = False
            else:
                child["manualRecoveryAvailable"] = False
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
            reason = "this fixed plan is historical evidence and can no longer be executed"
        elif document.get("truncated"):
            reason = "this fixed plan is truncated and cannot authorize exact work"
        elif not executable:
            reason = "no plan item is current, complete and executable"
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
                "主文件已完成的项无需重放；请按逐附件结果核查或补正，效果未知仅核查。"
                if any(item.get("primaryCompleted") for item in document.get("items", []))
                else "inspect each failed item and use Review & Recovery; uncertain effects are "
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

    def _attach_allowed_metadata_identities(self, document, items, intent) -> None:
        """Publish each intent item's bounded source-grounded identity options.

        The values are read from the same durable authority the choice save
        validates against, so the page can offer a real, legal identity
        correction without exposing a provider payload or widening the choice.
        A read never creates work and never calls a Provider.
        """

        service = self._manual_intents
        lister = getattr(service, "allowed_metadata_identities", None)
        if service is None or not callable(lister):
            return
        raw_items = document.get("items")
        if not isinstance(raw_items, list):
            return
        by_id = {item.item_id: item for item in intent.items}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("itemId")
            model = by_id.get(item_id)
            if model is None:
                continue
            try:
                identities = lister(model, intent)
            except Exception:  # noqa: BLE001 - a read must not fail the document
                identities = ()
            item["allowedMetadataIdentities"] = [
                {
                    "provider": value.get("provider"),
                    "providerId": value.get("providerId"),
                    "mediaType": value.get("mediaType"),
                    "title": value.get("title"),
                    "year": value.get("year"),
                }
                for value in identities
                if isinstance(value, dict)
            ]

    def _organize_unavailable_reason(
        self, permitted: bool, permission: ApiPermission, message: str
    ) -> str | None:
        if permitted:
            return None
        return f"{message} (required permission: {permission.value})"

    def _organize_intent_limit(self) -> int:
        limit = getattr(self._manual_intents, "MAX_ITEMS", None)
        return limit if isinstance(limit, int) else 0

    _AUTOMATION_OPERATOR_DENIED_KEYS = frozenset(
        {
            "plan",
            "planFingerprint",
            "sourceFingerprint",
            "storageFingerprint",
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
        dry_run = ApiPermission.EXECUTE_MANUAL_ORGANIZE in permissions
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
            "runOnce": {
                # Definition-bound Run once.  The backend derives the manifest
                # from the published definition's own ResourceLibrary/sub-scope,
                # so no file picker is involved.  A *disabled* published schedule
                # is explicitly runnable once; a Draft-only definition is not.
                "available": dry_run and in_active,
                "reason": (
                    not_active_reason
                    if not in_active
                    else self._organize_unavailable_reason(
                        dry_run,
                        ApiPermission.EXECUTE_MANUAL_ORGANIZE,
                        "the connected API principal cannot execute an organizing Run once",
                    )
                ),
                "method": "POST",
                "path": f"/api/v1/operations/automation/task-definitions/{definition_id}/run-once",
                "sideEffects": "none",
                "durableOutcome": (
                    "a durable organizing task for the saved scope is admitted and executed "
                    "through the existing Worker after complete scope and plan checks"
                ),
                "nextAction": (
                    "start Run once and inspect progress, independent results and "
                    "recovery in its linked task"
                ),
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

    @staticmethod
    def _automation_operator_execution_state(operator, *, in_active, historical):
        for key in ("unattendedExecutionGrant", "grant", "grantEligibility"):
            operator.pop(key, None)
        for key in ("grantState", "grant", "revoke"):
            operator["actions"].pop(key, None)
        state = "enabled" if operator.get("enabled") is True else "disabled"
        if historical:
            state = "historical"
        elif not in_active:
            state = "draft-only"
        operator["executionReadiness"] = {
            "state": state,
            "explanation": {
                "enabled": "The saved schedule is enabled. Each run still checks current "
                "execution permission, source availability and its actual plans before effects.",
                "disabled": "The saved schedule is disabled; it emits no new scheduled work.",
                "historical": "This definition was removed; retained history is read-only.",
                "draft-only": (
                    "This definition is saved only in a Draft and is not consumed by runtime."
                ),
                "unavailable": "The saved definition cannot currently be consumed safely.",
            }[state],
            "nextAction": (
                "inspect retained results; removed work is never restarted by reading history"
                if historical
                else "review the saved scope and limits in the checked definition editor"
            ),
        }
        return operator

    def _automation_definition_operator_document(
        self,
        document: dict,
        *,
        principal: ResolvedApiPrincipal,
        active=None,
        draft=None,
        eligibility: dict | None = None,
        in_active: bool = True,
        historical: bool = False,
    ) -> dict:
        """Bounded, digest-free V2 operator projection for one definition."""

        definition_id = str(document.get("id", ""))
        operator = self._strip_automation_operator_evidence(document)
        if historical:
            # A removed definition is retained history: truthful labelling,
            # never Active/Draft state, never revived authority.
            operator["definitionState"] = "historical"
            operator["historicalState"] = "removed"
            operator["activeConfiguration"] = self._automation_active_configuration(active)
            operator["draftState"] = self._automation_draft_state(
                None,
                empty_reason=(
                    "this definition was removed; its retained history is read-only and "
                    "no Draft can revive it"
                ),
            )
            operator["actions"] = self._automation_definition_actions(
                definition_id,
                principal,
                active=active,
                draft_present=False,
                in_active=False,
            )
            return self._automation_operator_execution_state(
                operator, in_active=False, historical=True
            )
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
        return self._automation_operator_execution_state(
            operator, in_active=in_active, historical=False
        )

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
        return self._unattended_grants.project_eligibility(
            definition,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
            configuration_snapshot_version=active.version,
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

    # -- Unified Operations run inventory (Slice 42 RO-1/RO-2) ------------

    _RUNS_STATUS_FILTER_VALUES = frozenset(value.value for value in OperationsRunStatus)
    _RUNS_TIME_FILTER = re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|\+00:00)?)?")

    def _operations_runs_projection(
        self,
        parts: list[str],
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """Dispatch the bounded unified run inventory and detail reads.

        The inventory reads one deduplicated population of Jobs and Tasks
        through their explicit persisted relationships.  Every read is
        side-effect-free: no admission, no Provider call, no Storage access
        and no display backfill.  Besides the page and one run's overview,
        the projection serves the selected-run detail reads (RO-3): the
        server-filtered item pages, the exactly-linked operation records,
        one item's durable evidence and the existing task-scoped result
        package export resolved through the run's own durable link.
        """

        if method != "GET":
            return self._error(start_response, 405, "method_not_allowed", "GET required")
        self._require(principal, ApiPermission.READ)
        if len(parts) == 4:
            return self._operations_runs_page(environ, start_response, principal)
        if len(parts) == 5:
            return self._operations_run_overview(parts[4], start_response, principal)
        if len(parts) == 6 and parts[5] == "items":
            return self._operations_run_items(parts[4], environ, start_response, principal)
        if len(parts) == 6 and parts[5] == "records":
            return self._operations_run_records(parts[4], environ, start_response, principal)
        if len(parts) == 6 and parts[5] == "export":
            return self._operations_run_export(parts[4], environ, start_response, principal)
        if len(parts) == 7 and parts[5] == "items":
            return self._operations_run_item_evidence(
                parts[4], parts[6], environ, start_response, principal
            )
        if len(parts) == 6 and parts[5] == "problem-items":
            return self._operations_run_problem_items(parts[4], environ, start_response, principal)
        return self._error(start_response, 404, "not_found", "route was not found")

    @classmethod
    def _operations_runs_query(cls, environ: dict, principal_id: str) -> dict[str, object]:
        """Bounded inventory filter state plus its filter-bound cursor.

        The submitted filters, the cursor kind and the principal identity are
        part of the cursor scope, so a cursor minted for one filter state or
        one principal is refused as soon as either differs: no cross-principal
        or cross-filter cursor replay.
        """

        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {
            "limit",
            "cursor",
            "status",
            "command",
            "q",
            "from",
            "to",
            "attention",
            "view",
            "problem",
            "source",
            "definition",
            "trigger",
        }
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError(
                "operations runs query accepts limit, cursor, status, command, q, from, to, "
                "attention, view, problem, source, definition, and trigger once"
            )
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["50"])[0], "run")
        raw_view = values.get("view", ["all"])[0]
        if raw_view in {"", "all"}:
            view = None
        elif raw_view in {item.value for item in OperationsRunView}:
            view = raw_view
        else:
            # A retired view (the former fifth Failure Recovery page) is a
            # rejected filter, never a silently different population: the old
            # deep link cannot resurrect a failure-recovery list.
            raise ValueError("operations run view filter is invalid")
        raw_problem = values.get("problem", [""])[0]
        if raw_problem in {"", "all"}:
            problem_type = None
        elif raw_problem in set(RECOVERY_PROBLEM_TYPES):
            problem_type = raw_problem
        else:
            # Only the four business problem types are filterable.  A technical
            # failure is read-only history in All/Ended, never a fifth problem
            # filter.
            raise ValueError("operations run problem filter is invalid")
        if view in RECOVERY_PROBLEM_TYPES and problem_type is not None and problem_type != view:
            # A recovery view already owns its problem type; a contradicting
            # explicit problem is a rejected filter, never a silently
            # different population.
            raise ValueError("operations run problem filter contradicts the view")
        raw_status = values.get("status", [""])[0]
        if raw_status in {"", "all"}:
            status = None
        elif raw_status in cls._RUNS_STATUS_FILTER_VALUES:
            status = raw_status
        else:
            raise ValueError("operations run status filter is invalid")
        raw_attention = values.get("attention", [""])[0]
        if raw_attention in {"", "all", "false", "no"}:
            attention = False
        elif raw_attention in {"true", "yes"}:
            attention = True
        else:
            raise ValueError("operations run attention filter is invalid")
        # A recovery view always applies its own problem filter server-side;
        # the standalone `problem` parameter lets the operator narrow a
        # lifecycle view without inventing a client-side filter.
        if view in RECOVERY_PROBLEM_TYPES:
            problem_type = view
        raw_source = values.get("source", [""])[0]
        source = None if raw_source in {"", "all"} else raw_source
        if source is not None and (
            len(source) > 512
            or source != source.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in source)
        ):
            raise ValueError("operations run source filter is invalid")
        raw_command = values.get("command", [""])[0]
        command = None if raw_command in {"", "all"} else raw_command
        if command is not None and not _TASK_COMMAND_FILTER.fullmatch(command):
            raise ValueError("operations run command filter is invalid")
        raw_search = values.get("q", [""])[0].strip()
        if len(raw_search) > 128:
            raise ValueError("operations run search text is too long")
        search = raw_search or None
        # The Automation execution-record selectors bind the admission-written
        # definition identity and the derived trigger.  Both are optional, so
        # the existing Operations list keeps its exact population when neither
        # is submitted.
        raw_definition = values.get("definition", [""])[0]
        definition_id = None if raw_definition in {"", "all"} else raw_definition
        if definition_id is not None and not _AUTOMATION_DEFINITION_FILTER.fullmatch(definition_id):
            raise ValueError("operations run definition filter is invalid")
        raw_trigger = values.get("trigger", [""])[0]
        if raw_trigger in {"", "all"}:
            trigger = None
        elif raw_trigger in {item.value for item in OperationsRunTrigger}:
            trigger = raw_trigger
        else:
            raise ValueError("operations run trigger filter is invalid")
        created_after = cls._run_time_filter(values.get("from", [""])[0], "from")
        created_before = cls._run_time_filter(values.get("to", [""])[0], "to")
        scope = cls._operations_runs_scope(
            principal_id=principal_id,
            status=status,
            command=command,
            search=search,
            created_after=created_after,
            created_before=created_before,
            attention=attention,
            view=view,
            problem_type=problem_type,
            source=source,
            definition_id=definition_id,
            trigger=trigger,
        )
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(
                raw_cursor[0],
                "operations_runs",
                expected_scope=scope,
            )
            if raw_cursor and raw_cursor[0]
            else None
        )
        return {
            "limit": limit,
            "cursor": cursor,
            "status": status,
            "command": command,
            "search": search,
            "attention": attention,
            "view": view,
            "problem": problem_type,
            "source": source,
            "definition_id": definition_id,
            "trigger": trigger,
            "created_after": created_after,
            "created_before": created_before,
            "scope": scope,
        }

    @staticmethod
    def _run_time_filter(raw: str, field: str) -> datetime | None:
        """Parse one bounded creation-time boundary.

        Only UTC ISO-8601 forms are accepted; anything else is a rejected
        filter value rather than an ignored one, so a silent filter mismatch
        can never look like an empty population.
        """

        if raw in {"", "all"}:
            return None
        # parse_qs has already decoded the query string, so a literal "+"
        # arrived as a space; restore the UTC designator before validating.
        raw = raw.replace(" 00:00", "+00:00").replace(" ", "+")
        if not MediaFlowApi._RUNS_TIME_FILTER.fullmatch(raw):
            raise ValueError(f"operations run {field} filter is invalid")
        normalized = raw.replace("Z", "+00:00")
        if "T" not in normalized:
            normalized = normalized.replace("+00:00", "") + "T00:00:00+00:00"
        elif not normalized.endswith("+00:00"):
            normalized += "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as error:
            raise ValueError(f"operations run {field} filter is invalid") from error
        if parsed.utcoffset() != timedelta(0):
            raise ValueError(f"operations run {field} filter must use UTC")
        return parsed

    @staticmethod
    def _operations_runs_scope(
        *,
        principal_id: str,
        status: str | None,
        command: str | None,
        search: str | None,
        created_after: datetime | None,
        created_before: datetime | None,
        attention: bool = False,
        view: str | None = None,
        problem_type: str | None = None,
        source: str | None = None,
        definition_id: str | None = None,
        trigger: str | None = None,
    ) -> str:
        """Deterministic cursor scope binding filters and the reading principal.

        The principal identity is part of the digested scope, so a cursor
        minted by one API principal is refused for another: a cross-principal
        replay recovers as an invalid cursor, never as a silently different
        page.  The digest hides the identity from the cursor payload itself.
        Every submitted population filter — including the overlapping
        attention facet, the selected view and the recovery problem type — is
        bound the same way, so a cursor minted for one filter state is refused
        as soon as any filter differs.
        """

        parts = [
            f"principal={principal_id}",
            f"status={status or 'all'}",
            f"attention={'true' if attention else 'false'}",
            f"view={view or 'all'}",
            f"problem={problem_type or 'all'}",
            f"source={source or 'all'}",
            f"command={command or 'all'}",
            f"q={search or ''}",
            f"from={created_after.isoformat() if created_after else ''}",
            f"to={created_before.isoformat() if created_before else ''}",
        ]
        # The Automation execution-record selectors are appended only when they
        # are actually submitted.  A cursor minted without them therefore never
        # matches a read that submits one, and a cursor minted with a specific
        # definition/trigger never matches any other value — while the existing
        # unfiltered/already-supported scopes keep their exact historical form.
        if definition_id is not None:
            parts.append(f"definition={definition_id}")
        if trigger is not None:
            parts.append(f"trigger={trigger}")
        return ";".join(parts)

    def _operations_runs_page(
        self,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """One bounded inventory page with truthful counts (AC-T2)."""

        query = self._operations_runs_query(environ, principal.principal_id)
        repository = self._repository
        if repository is None or not callable(getattr(repository, "operations_runs_window", None)):
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "unified run inventory is unavailable for this runtime",
            )
        # One repository window call derives the page, the filtered total,
        # the status partitions and the overlapping attention facet from one
        # database read snapshot.  The submitted cursor only bounds the page
        # window — it never narrows the reported population — and both page
        # directions keep one newest-first ordering with honestly derived
        # adjacent-page flags, so an operator can page forward and back
        # through the whole filtered population.
        cursor: DecodedCursor | None = query["cursor"]
        limit: int = query["limit"]
        arguments: dict[str, object] = {
            "limit": limit,
            "status": query["status"],
            "command": query["command"],
            "search": query["search"],
            "created_after": query["created_after"],
            "created_before": query["created_before"],
            "attention": query["attention"],
            "view": query["view"],
            "problem_type": query["problem"],
            "source": query["source"],
            "definition_id": query["definition_id"],
            "trigger": query["trigger"],
        }
        if cursor is not None and cursor.direction is CursorDirection.PREVIOUS:
            window = repository.operations_runs_window(before=cursor.position, **arguments)
        else:
            window = repository.operations_runs_window(
                after=cursor.position if cursor else None, **arguments
            )
        page = window.page
        has_next = bool(window.has_next)
        has_previous = bool(window.has_previous)
        scope: str = query["scope"]
        # The current-problem facet is the exact same derived fact the page
        # rows carry: with the attention facet applied, the page *is* that
        # overlapping population, so the card keeps showing exactly the count
        # it filters to.
        attention_count = window.attention_count
        raw_summary = getattr(window, "summary", None)
        summary = (
            self._public_operations_run_summary(raw_summary)
            if isinstance(raw_summary, dict)
            else {"available": False}
        )
        return self._response(
            start_response,
            200,
            {
                "items": [self._operations_run_document(item) for item in page],
                "limit": limit,
                "status": query["status"],
                "command": query["command"],
                "q": query["search"],
                "attention": bool(query["attention"]),
                "view": query["view"],
                "problem": query["problem"],
                "source": bounded_identity_path(query["source"]),
                "definition": query["definition_id"],
                "trigger": query["trigger"],
                "from": (query["created_after"].isoformat() if query["created_after"] else None),
                "to": (query["created_before"].isoformat() if query["created_before"] else None),
                "total": window.total,
                "truncated": has_next,
                "status_counts": window.status_counts,
                "attention_count": attention_count,
                "summary": summary,
                "population": (
                    "unified job/task run inventory, deduplicated by explicit task linkage"
                ),
                "sideEffects": "none",
                "previous_cursor": self._run_page_cursor(
                    page, has_previous, CursorDirection.PREVIOUS, scope
                ),
                "next_cursor": self._run_page_cursor(page, has_next, CursorDirection.NEXT, scope),
            },
        )

    @staticmethod
    def _operations_run_summary(repository) -> dict[str, object]:
        """The complete-authorized-population summary of the nine views (RO-1).

        Read from one repository read snapshot over the whole authorized
        population, never from the browser's current page, so the summary
        cards and the view counts stay truthful while the operator filters and
        pages.  A repository without the summary read publishes an explicit
        unavailable summary instead of fabricated zeros.
        """

        reader = getattr(repository, "operations_run_summary", None)
        if not callable(reader):
            return {"available": False}
        summary = reader()
        return MediaFlowApi._public_operations_run_summary(summary)

    @staticmethod
    def _public_operations_run_summary(summary: dict[str, object]) -> dict[str, object]:
        """Redact bounded source options before publishing snapshot statistics."""

        summary = dict(summary)
        # The source options are published through the same bounded identity
        # boundary as the run rows: a legacy absolute host/adapter root, a
        # private endpoint or a credential-shaped scope never reaches the
        # public document.  Redacted markers are omitted because they cannot
        # be submitted as a useful exact source filter and could conflate
        # unrelated private locations.
        raw_sources = summary.get("sources")
        if isinstance(raw_sources, list):
            sources: list[dict[str, str]] = []
            redacted = False
            for entry in raw_sources:
                if not isinstance(entry, dict):
                    redacted = True
                    continue
                value = bounded_identity_path(entry.get("value"))
                label = bounded_identity_path(entry.get("label"))
                if value in (None, "[redacted-path]") or label in (None, "[redacted-path]"):
                    redacted = True
                    continue
                sources.append({"value": value, "label": label})
            summary["sources"] = sources
            if redacted:
                summary["sources_truncated"] = True
        return summary

    def _operations_run_overview(
        self, run_id: str, start_response: Callable, principal: ResolvedApiPrincipal
    ):
        """One selected run's bounded overview plus its durable progress.

        The overview row and its progress facts come from one repository read
        snapshot.  A supported Task detail identity also resolves here through
        the exact persisted Job→Task link, so deep-opening either side of the
        linkage reaches the same stable run without a manual join.
        """

        repository = self._repository
        if repository is None or not callable(getattr(repository, "operations_run", None)):
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "unified run inventory is unavailable for this runtime",
            )
        overview, progress = self._operations_run_detail(repository, run_id)
        if overview is None:
            raise LookupError(f"operations run {run_id!r} was not found")
        document = self._operations_run_document(overview)
        document["progress"] = (
            run_progress_document(progress, command=overview.command)
            if progress is not None
            else None
        )
        # The selected run's backend-computed lifecycle controls.  A run that
        # resolves to a linked Task advertises that Task's exact controls; a
        # pre-Task queue admission advertises its Job's controls.  The
        # projection is computed for this exact principal and durable state, so
        # the panel renders only what the backend would really accept, and a run
        # with neither object publishes `null` instead of a guessed control.
        document["lifecycle"] = self._operations_run_lifecycle(overview, principal)
        # The selected run's durable continuation chain.  A paused run whose
        # remaining scope was already continued keeps a native entry to the run
        # that really owns that scope, so the operator never has to guess an
        # internal identifier and never repeats finished work.
        document["continuation"] = self._operations_run_continuation(overview)
        return self._response(start_response, 200, document)

    def _operations_run_continuation(self, overview) -> dict[str, object] | None:
        """The bounded, redacted continuation evidence of one selected run.

        The internal ``scope_path``, the configuration pin and the actor are
        never published: the operator document carries only the bounded
        identifiers the Web needs to follow the linked continuation run, plus
        the run's own truthful next action.
        """

        repository = self._repository
        task_id = getattr(overview, "task_id", None)
        if repository is None or not isinstance(task_id, str) or not task_id:
            return None
        candidates: list[tuple[object, dict[str, object]]] = []
        lister = getattr(repository, "list_scope_continuations", None)
        if callable(lister):
            try:
                values = tuple(lister(task_id, limit=8))
            except Exception:
                values = ()
            for value in values:
                document = scope_continuation_operator_document(value)
                document.update(
                    {
                        "recoveryKind": "queued_continuation",
                        "recoveryPreviewId": None,
                        "executionId": None,
                    }
                )
                document["attemptCount"] = len(values)
                document["truncated"] = len(values) >= 8
                candidates.append((value.created_at, document))

        recovery_lister = getattr(repository, "list_scope_recovery_links", None)
        if callable(recovery_lister):
            try:
                recoveries = tuple(recovery_lister(task_id, limit=8))
            except Exception:
                recoveries = ()
            task_reader = getattr(repository, "get_task", None)
            try:
                source = task_reader(task_id) if callable(task_reader) else None
            except Exception:
                source = None
            for value in recoveries:
                document = scope_recovery_operator_document(value, source)
                document["attemptCount"] = len(recoveries)
                document["truncated"] = len(recoveries) >= 8
                candidates.append((value.created_at, document))
        if not candidates:
            return None
        return max(candidates, key=lambda candidate: candidate[0])[1]

    def _remaining_scope_obstacle(self):
        """The shared continuation obstacle the recovery admission reuses.

        The recovery entry is offered for exactly the refusal the real recovery
        admission boundary would return, so it delegates to that boundary's own
        decision instead of re-deriving the pin, chain ownership or remaining
        scope here.  The decision is asked for the *recovery preparation*
        operation: a fully recorded budget with one still-undecided item has no
        unrecorded discovery budget to hand to the queued Worker, but it does
        have exactly that undecided item to observe and review, so the recovery
        entry must not inherit the queued-continuation budget/authority refusal
        when deciding whether a review is possible at all.
        """

        service = self._scope_continuations

        def obstacle(task):
            reason, message, next_action = service.recovery_obstacle(task)
            return (reason.value if reason is not None else None), message, next_action

        return obstacle

    def _operations_run_remaining_scope_preview(
        self, task_id: str, environ: dict, start_response: Callable, principal: ResolvedApiPrincipal
    ):
        """Admit one durable remaining-scope recovery preparation for a paused run.

        This is the recovery path RO-5 promises when Continue cannot retain live
        execution authority.  It admits a zero-mutation bounded observation of
        the run's *durable* remaining scope under the run's own immutable
        historical pin, runs the complete analysis chain in the resident Worker
        once the configured stability interval is proven, and grants no
        execution authority: the operator still has to make one fresh explicit
        execution intent through the ordinary Execute action.
        """

        self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
        service = getattr(self, "_media_discovery", None)
        if service is None or not callable(getattr(service, "admit_recovery_preparation", None)):
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "the remaining-scope recovery service is unavailable",
                details={
                    "durableState": "no_preparation_created",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "restore a valid Active runtime and the bounded discovery Worker, "
                        "then retry"
                    ),
                },
            )
        self._require_empty_query(environ, "remaining-scope Preview")
        # An empty body is the normal submission; when a body is supplied it may
        # carry only the optimistic version the operator read, exactly like the
        # sibling resume control.
        raw_length = str(environ.get("CONTENT_LENGTH", "")).strip()
        if raw_length and raw_length != "0":
            document = self._document(environ)
            if set(document).difference({"expectedVersion"}):
                raise ValueError("remaining-scope Preview accepts only the paused Task identity")
            expected_version = document.get("expectedVersion")
            if expected_version is not None and (
                not isinstance(expected_version, str)
                or not expected_version.strip()
                or len(expected_version) > 128
            ):
                raise ValueError("remaining-scope Preview expectedVersion is invalid")
            current = repository.get_task(task_id) if (repository := self._repository) else None
            if (
                expected_version is not None
                and current is not None
                and expected_version != current.updated_at.isoformat()
            ):
                return self._error(
                    start_response,
                    409,
                    "lifecycle_conflict",
                    "the paused run changed since it was read; no Preview was created",
                    details={
                        "reason": "stale_task_state",
                        "durableState": "the run keeps its current durable state",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "currentVersion": current.updated_at.isoformat(),
                        "nextAction": "refresh the run and request a fresh plan summary again",
                    },
                )
        repository = self._repository
        task = repository.get_task(task_id) if repository is not None else None
        if task is None:
            return self._error(
                start_response,
                404,
                "not_found",
                "the paused run was not found",
                details={
                    "reason": "task_not_found",
                    "sideEffects": "none",
                    "retrySafe": False,
                    "nextAction": "refresh the run inventory and select the exact run again",
                },
            )
        try:
            discovery = self._media_discovery.admit_recovery_preparation(
                task_id,
                actor=principal.principal_id,
                obstacle=self._remaining_scope_obstacle(),
            )
        except DiscoveryError as error:
            return self._discovery_step_error(start_response, error)
        except ManualPreviewError as error:
            return self._manual_step_error(start_response, error)
        return self._response(
            start_response,
            202,
            self._discovery_document(discovery, principal, self._runtime_binding),
        )

    def _operations_run_lifecycle(self, overview, principal) -> dict[str, object] | None:
        """Backend-computed controls for one selected run, or ``None``."""

        repository = self._repository
        task_id = getattr(overview, "task_id", None)
        if isinstance(task_id, str) and task_id:
            task = repository.get_task(task_id)
            if task is not None:
                # The projection judges the same binding the control endpoint
                # would use, so an advertised Continue and an accepted Continue
                # can never disagree about the live authority.
                binding = self._runtime_binding
                service = TaskLifecycleService(
                    repository,
                    snapshot_validator=self._scope_continuations._snapshot_validator,
                    mutation_authority=(
                        binding.scope_continuation_authority if binding is not None else None
                    ),
                )
                return redact_manual_value(
                    self._task_lifecycle(
                        service,
                        task,
                        principal,
                        results=service.results(task.task_id),
                    )
                )
        job_id = getattr(overview, "job_id", None)
        if isinstance(job_id, str) and job_id:
            reader = getattr(repository, "get_job", None)
            job = reader(job_id) if callable(reader) else None
            if job is not None:
                return redact_manual_value(
                    job_lifecycle_document(job, permissions=principal.permissions)
                )
        return None

    @staticmethod
    def _operations_run_detail(repository, identifier: str):
        """Resolve one supported *Task Center* identity to ``(overview, progress)``.

        The exact run anchor wins; a Job-linked Task ID resolves only through
        the persisted ``automation_jobs.task_id`` link (never a filename,
        label or time proximity).  Task Center's population is admitted
        organizing work only (Slice46 RO-4), so an ordinary file work's Task or
        an unrelated Job published the same ID resolves to *nothing* here: the
        ordinary record keeps its own library-local surface and cannot be
        reached through a center deep link.  When the repository has no combined
        detail read, the plain overview read still answers with
        ``progress=None`` instead of failing a supported deep link.
        """

        membership = getattr(repository, "is_task_center_run", None)
        with_progress = getattr(repository, "operations_run_with_progress", None)

        def read(identity: str):
            if callable(membership) and not membership(identity):
                return None
            return with_progress(identity) if callable(with_progress) else None

        detail = read(identifier) if isinstance(identifier, str) else None
        if detail is None:
            resolver = getattr(repository, "resolve_operations_run_link", None)
            if callable(resolver) and callable(with_progress) and isinstance(identifier, str):
                anchor = resolver(identifier)
                if isinstance(anchor, str) and anchor and anchor != identifier:
                    detail = read(anchor)
            # A Job-linked Task that is not Task Center work may still resolve
            # its anchor through the plain read; but the membership check above
            # already refused it, so nothing is guessed here.
        if detail is not None:
            return detail[0], detail[1]
        if callable(membership) and isinstance(identifier, str) and not membership(identifier):
            return None, None
        return repository.operations_run(identifier), None

    @classmethod
    def _run_items_scope(cls, principal_id: str, overview, disposition: str | None) -> str:
        """Deterministic cursor scope binding principal, run/task and filter."""

        return (
            f"principal={principal_id};run={overview.run_id};"
            f"task={overview.task_id or '-'};status={disposition or 'all'}"
        )

    @classmethod
    def _run_problem_items_scope(cls, principal_id: str, overview, problem: str) -> str:
        """Deterministic cursor scope for one problem-type file list."""

        return (
            f"principal={principal_id};run={overview.run_id};"
            f"task={overview.task_id or '-'};problem={problem}"
        )

    @classmethod
    def _run_problem_items_query(
        cls, environ: dict, principal_id: str, overview
    ) -> tuple[int, str, DecodedCursor | None, str]:
        """Bounded problem-file page state plus its filter-bound cursor."""

        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"limit", "cursor", "problem"}
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError("run problem item query accepts limit, cursor, and problem once")
        limit = MediaFlowApi._parse_bounded_limit(
            values.get("limit", ["20"])[0], "run problem item"
        )
        problem = values.get("problem", [""])[0]
        if problem not in RECOVERY_PROBLEM_TYPES:
            raise ValueError("run problem item type is invalid")
        scope = cls._run_problem_items_scope(principal_id, overview, problem)
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(raw_cursor[0], "run_problem_items", expected_scope=scope)
            if raw_cursor and raw_cursor[0]
            else None
        )
        return limit, problem, cursor, scope

    @classmethod
    def _run_records_scope(cls, principal_id: str, overview, kind: str | None) -> str:
        """Deterministic cursor scope binding principal, run/task/job and kind."""

        return (
            f"principal={principal_id};run={overview.run_id};"
            f"task={overview.task_id or '-'};job={overview.job_id or '-'};"
            f"kind={kind or 'all'}"
        )

    @classmethod
    def _run_items_query(
        cls, environ: dict, principal_id: str, overview
    ) -> tuple[int, str | None, DecodedCursor | None, str]:
        """Bounded item-page state plus its filter-bound cursor (AC-T3).

        The submitted disposition filter, the exact run/task identity and the
        reading principal are part of the cursor scope: a cursor minted for
        another run, another filter state or another principal is refused as
        soon as any of them differs.
        """

        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"limit", "cursor", "status"}
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError("run item query accepts limit, cursor, and status once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["20"])[0], "run item")
        raw_status = values.get("status", [""])[0]
        if raw_status in {"", "all"}:
            disposition = None
        elif raw_status in set(RUN_DISPOSITIONS):
            disposition = raw_status
        else:
            raise ValueError("run item status filter is invalid")
        scope = cls._run_items_scope(principal_id, overview, disposition)
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(raw_cursor[0], "run_items", expected_scope=scope)
            if raw_cursor and raw_cursor[0]
            else None
        )
        return limit, disposition, cursor, scope

    @classmethod
    def _run_records_query(
        cls, environ: dict, principal_id: str, overview
    ) -> tuple[int, str | None, DecodedCursor | None, str]:
        """Bounded record-page state plus its kind-filter-bound cursor."""

        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"limit", "cursor", "kind"}
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError("run record query accepts limit, cursor, and kind once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["20"])[0], "run record")
        raw_kind = values.get("kind", [""])[0]
        if raw_kind in {"", "all"}:
            kind = None
        elif raw_kind in set(RUN_RECORD_KINDS):
            kind = raw_kind
        else:
            raise ValueError("run record kind filter is invalid")
        scope = cls._run_records_scope(principal_id, overview, kind)
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(raw_cursor[0], "run_records", expected_scope=scope)
            if raw_cursor and raw_cursor[0]
            else None
        )
        return limit, kind, cursor, scope

    def _operations_run_items(
        self, run_id: str, environ: dict, start_response: Callable, principal
    ):
        """One bounded item page with page-independent population totals (AC-T3).

        The page, the filtered total and the whole-population disposition
        partition come from one repository read snapshot, so a concurrent
        transition can never fabricate progress or drop a successful sibling,
        and a status filter never hides the full population's counts.
        """

        repository = self._repository
        if repository is None or not callable(
            getattr(repository, "operations_run_items_window", None)
        ):
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "run detail items are unavailable for this runtime",
            )
        overview, progress = self._operations_run_detail(repository, run_id)
        if overview is None:
            raise LookupError(f"operations run {run_id!r} was not found")
        limit, disposition, cursor, scope = self._run_items_query(
            environ, principal.principal_id, overview
        )
        task_id = overview.task_id
        if task_id is None:
            # A pre-Task admission has honest queue/detail state and explicit
            # item unavailability — never a fabricated empty success.
            return self._response(
                start_response,
                200,
                {
                    "run_id": overview.run_id,
                    "task_id": None,
                    "filter": {"status": disposition},
                    "limit": limit,
                    "items": [],
                    "total": 0,
                    "matching_total": 0,
                    "dispositions": {key: 0 for key in RUN_DISPOSITIONS},
                    "uncertain_success": 0,
                    "truncated": False,
                    "previous_cursor": None,
                    "next_cursor": None,
                    "unavailable": (
                        progress.unavailable_reason
                        if progress is not None and progress.unavailable_reason
                        else "this run has no linked Task yet"
                    ),
                    "sideEffects": "none",
                },
            )
        window = repository.operations_run_items_window(
            task_id,
            limit=limit,
            after=cursor.position if cursor and cursor.direction is CursorDirection.NEXT else None,
            before=(
                cursor.position if cursor and cursor.direction is CursorDirection.PREVIOUS else None
            ),
            disposition=disposition,
        )
        items = []
        for item in window.page:
            checkpoint = self._checkpoint_service.get(item.item_id, task_id=task_id)
            document = self._task_item_document(
                item,
                bounded=True,
                checkpoint=checkpoint.summary(),
            )
            # The same bounded per-item decision the item panel and batch
            # document publish.  The center's per-item selection uses it, so a
            # technical failure beside an unrelated business problem never
            # becomes a batch recovery candidate (B46.4-03).
            document["recoveryKind"] = self._task_item_recovery.recovery_kind(
                item.item_id, has_blocker=checkpoint.blocker is not None
            )
            items.append(document)
        return self._response(
            start_response,
            200,
            {
                "run_id": overview.run_id,
                "task_id": task_id,
                "filter": {"status": disposition},
                "limit": limit,
                "items": items,
                "total": window.total,
                "matching_total": window.matching_total,
                "dispositions": dict(window.dispositions),
                "uncertain_success": window.uncertain_success,
                "truncated": window.has_next,
                "previous_cursor": self._page_cursor(
                    "run_items",
                    window.page,
                    window.has_previous,
                    CursorDirection.PREVIOUS,
                    scope=scope,
                ),
                "next_cursor": self._page_cursor(
                    "run_items",
                    window.page,
                    window.has_next,
                    CursorDirection.NEXT,
                    scope=scope,
                ),
                "sideEffects": "none",
            },
        )

    def _operations_run_problem_items(
        self, run_id: str, environ: dict, start_response: Callable, principal
    ):
        """One problem-type-filtered file page of a recovery list entry (RO-3).

        The recovery row leads to the exact Task/type file list, server-
        filtered and server-paged on the same durable predicate the list view
        uses.  A Task with no linked Task (a pre-Task admission) reports honest
        item unavailability instead of an empty success, and a file carrying
        several problems still appears once per type.
        """

        repository = self._repository
        if repository is None or not callable(
            getattr(repository, "operations_run_problem_items_window", None)
        ):
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "run problem items are unavailable for this runtime",
            )
        overview, progress = self._operations_run_detail(repository, run_id)
        if overview is None:
            raise LookupError(f"operations run {run_id!r} was not found")
        limit, problem, cursor, scope = self._run_problem_items_query(
            environ, principal.principal_id, overview
        )
        task_id = overview.task_id
        if task_id is None:
            return self._response(
                start_response,
                200,
                {
                    "run_id": overview.run_id,
                    "task_id": None,
                    "problem": problem,
                    "limit": limit,
                    "items": [],
                    "total": 0,
                    "matching_total": 0,
                    "dispositions": {key: 0 for key in RUN_DISPOSITIONS},
                    "uncertain_success": 0,
                    "truncated": False,
                    "previous_cursor": None,
                    "next_cursor": None,
                    "unavailable": (
                        progress.unavailable_reason
                        if progress is not None and progress.unavailable_reason
                        else "this run has no linked Task yet"
                    ),
                    "sideEffects": "none",
                },
            )
        window = repository.operations_run_problem_items_window(
            task_id,
            problem,
            limit=limit,
            after=cursor.position if cursor and cursor.direction is CursorDirection.NEXT else None,
            before=(
                cursor.position if cursor and cursor.direction is CursorDirection.PREVIOUS else None
            ),
        )
        items = [
            self._task_item_document(
                item,
                bounded=True,
                checkpoint=self._checkpoint_service.summary(item.item_id, task_id=task_id),
            )
            for item in window.page
        ]
        return self._response(
            start_response,
            200,
            {
                "run_id": overview.run_id,
                "task_id": task_id,
                "problem": problem,
                "limit": limit,
                "items": items,
                "total": window.total,
                "matching_total": window.matching_total,
                "dispositions": dict(window.dispositions),
                "uncertain_success": window.uncertain_success,
                "truncated": window.has_next,
                "previous_cursor": self._page_cursor(
                    "run_problem_items",
                    window.page,
                    window.has_previous,
                    CursorDirection.PREVIOUS,
                    scope=scope,
                ),
                "next_cursor": self._page_cursor(
                    "run_problem_items",
                    window.page,
                    window.has_next,
                    CursorDirection.NEXT,
                    scope=scope,
                ),
                "sideEffects": "none",
            },
        )

    def _operations_run_records(
        self, run_id: str, environ: dict, start_response: Callable, principal
    ):
        """One bounded operation-record page from exactly-linked evidence (AC-T4).

        Results, captured plan/analysis evidence, task/job-linked operational
        logs and control/recovery audit rows are joined only through persisted
        IDs and paged on the server; the browser never merges truncated
        collections and the global log collection is never fetched to filter
        client-side.
        """

        repository = self._repository
        if repository is None or not callable(
            getattr(repository, "operations_run_records_window", None)
        ):
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "run operation records are unavailable for this runtime",
            )
        overview, _progress = self._operations_run_detail(repository, run_id)
        if overview is None:
            raise LookupError(f"operations run {run_id!r} was not found")
        limit, kind, cursor, scope = self._run_records_query(
            environ, principal.principal_id, overview
        )
        window = repository.operations_run_records_window(
            overview.task_id,
            overview.job_id,
            kind=kind,
            limit=limit,
            after=cursor.position if cursor and cursor.direction is CursorDirection.NEXT else None,
            before=(
                cursor.position if cursor and cursor.direction is CursorDirection.PREVIOUS else None
            ),
        )
        return self._response(
            start_response,
            200,
            {
                "run_id": overview.run_id,
                "task_id": overview.task_id,
                "job_id": overview.job_id,
                "filter": {"kind": kind},
                "limit": limit,
                "records": [run_record_document(record) for record in window.page],
                "matching_total": window.matching_total,
                "kind_counts": dict(window.kind_counts),
                "truncated": window.has_next,
                "previous_cursor": self._page_cursor(
                    "run_records",
                    window.page,
                    window.has_previous,
                    CursorDirection.PREVIOUS,
                    scope=scope,
                ),
                "next_cursor": self._page_cursor(
                    "run_records",
                    window.page,
                    window.has_next,
                    CursorDirection.NEXT,
                    scope=scope,
                ),
                "sideEffects": "none",
            },
        )

    def _operations_run_item_evidence(
        self, run_id: str, item_id: str, environ: dict, start_response: Callable, principal
    ):
        """One exact item's durable evidence through its persisted links (AC-T4).

        The item must belong to this run's linked Task — an item from another
        run is an honest 404, never a cross-run join.  The document composes
        the persisted checkpoint, Results, captured plan/analysis evidence and
        exactly plan-linked operational logs without re-running any Provider,
        planner or Storage read, and absent logs never erase a Result.
        """

        repository = self._repository
        if repository is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "run item evidence is unavailable for this runtime",
            )
        self._require_empty_query(environ, "run item evidence")
        overview, _progress = self._operations_run_detail(repository, run_id)
        if overview is None:
            raise LookupError(f"operations run {run_id!r} was not found")
        task_id = overview.task_id
        item = repository.get_item(item_id) if task_id is not None else None
        if task_id is None or item is None or item.task_id != task_id:
            raise LookupError(f"run item {item_id!r} was not found")
        checkpoint = self._checkpoint_service.get(item.item_id, task_id=task_id)
        checkpoint_document = checkpoint.document()
        results = repository.list_results_for_item(item.item_id, limit=32)
        evidence_documents = [
            value.document() for value in repository.list_evidence_for_item(item.item_id, limit=16)
        ]
        plan_evidence = None
        execution_reader = getattr(repository, "manual_execution_item_for_task_item", None)
        if callable(execution_reader):
            # The durable reviewed plan joins through the exact persisted
            # (task_id, task_item_id) Manual execution linkage only.  CLI,
            # scheduled and legacy items have no such row, so their plan
            # evidence stays explicitly unavailable.
            execution_document = execution_reader(task_id, item.item_id)
            if isinstance(execution_document, dict):
                plan_evidence = manual_execution_plan_evidence_operator(execution_document)
        logs = []
        plan_id = item.plan_id
        log_reader = getattr(repository, "list_operational_logs_for_plan", None)
        if plan_id and callable(log_reader):
            # A plan ID is deterministic but not run-unique: two attempts at
            # the same source share one plan while being distinct Tasks.
            # Attribution therefore also binds the run's own persisted Task/Job
            # linkage; a log row that carries neither stays unavailable
            # evidence instead of being claimed through its reusable plan ID.
            logs = [
                OperationsRunRecord(
                    kind="log",
                    record_id=f"log:{value.log_id}",
                    occurred_at=value.occurred_at,
                    item_id=None,
                    source={
                        "action": value.event,
                        "state": value.status,
                        "actor": value.component,
                        "ref": int(value.level),
                        "link": value.plan_id,
                    },
                )
                for value in log_reader(
                    plan_id,
                    task_id=task_id,
                    job_id=overview.job_id,
                    limit=20,
                )
            ]
        document = run_item_evidence_document(
            item=item,
            checkpoint_document=checkpoint_document,
            results=results,
            evidence=evidence_documents,
            logs=logs,
            plan_evidence=plan_evidence,
        )
        document["run_id"] = overview.run_id
        document["task_id"] = task_id
        document["item_id"] = item.item_id
        # The evidence panel and the item row must make the same technical-
        # history/four-type decision from the server, never from a label.
        document["recoveryKind"] = self._task_item_recovery.recovery_kind(
            item.item_id, has_blocker=checkpoint.blocker is not None
        )
        return self._response(start_response, 200, redact_manual_value(document))

    def _operations_run_export(
        self, run_id: str, environ: dict, start_response: Callable, principal
    ):
        """Download the eligible linked Task's existing result package (AC-T5).

        The server resolves the exact linked Task through the run's durable
        link and delegates to the existing ``export_results`` authority, so
        package ordering, redaction, limits, digest and truncation stay
        truthful.  A pre-Task run is an explicit refusal — never an empty
        successful download.
        """

        if self._package_exchange is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "result package export is unavailable for this runtime",
            )
        repository = self._repository
        if repository is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "result package export is unavailable for this runtime",
            )
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit"}) or any(len(value) != 1 for value in values.values()):
            raise ValueError("run export accepts one optional limit")
        raw_limit = values.get("limit", ["100"])[0]
        try:
            limit = int(raw_limit)
        except ValueError as error:
            raise ValueError("run export limit must be an integer") from error
        overview, _progress = self._operations_run_detail(repository, run_id)
        if overview is None:
            raise LookupError(f"operations run {run_id!r} was not found")
        if overview.task_id is None:
            raise PackageExchangeError(
                "this run has no linked Task yet, so no eligible result package exists",
                code="task_not_linked",
                status=409,
                durable_state="no_package_state_changed",
                next_action=(
                    "wait until the admission acquires its Task, then export the "
                    "linked Task's result package"
                ),
            )
        package = self._package_exchange.export_results(
            actor=principal.principal_id,
            task_id=overview.task_id,
            limit=limit,
        )
        return self._response(start_response, 200, package)

    @staticmethod
    def _run_page_cursor(
        page: tuple,
        available: bool,
        direction: CursorDirection,
        scope: str,
    ) -> str | None:
        if not available or not page:
            return None
        record = page[0] if direction is CursorDirection.PREVIOUS else page[-1]
        return encode_cursor(
            "operations_runs",
            record.created_at,
            record.run_id,
            direction,
            scope=scope,
        )

    def _operations_run_document(self, overview) -> dict[str, object]:
        """One bounded, secret-free inventory/overview run document.

        The raw scope path is never published: only the bounded relative
        scope identity survives redaction, and an unknown legacy command gets
        an honest ``recognizedCommand: false`` label rather than a guessed
        business meaning.
        """

        command = overview.command
        label = known_command_label(command) if command else None
        if overview.run_kind == "discovery":
            # A bounded discovery carries no Task command family; its bounded
            # business label is the discovery kind label the inventory
            # derives from its own durable record.
            label = DISCOVERY_COMMAND_LABEL
        document: dict[str, object] = {
            "run_kind": overview.run_kind,
            "run_id": overview.run_id,
            "command": command,
            "command_label": label,
            "recognized_command": overview.recognized_command and label is not None,
            "status": overview.status.value,
            "trigger": overview.trigger.value,
            "created_at": overview.created_at.isoformat(),
            "updated_at": overview.updated_at.isoformat(),
            "job_id": overview.job_id,
            "task_id": overview.task_id,
            "schedule_id": overview.schedule_id,
            "definition_id": overview.definition_id,
            "source_scope": bounded_identity_path(overview.source_scope),
            "target_scope": bounded_identity_path(overview.target_scope),
            "library_kind": overview.library_kind.value if overview.library_kind else None,
            "total_items": overview.total_items,
            "completed_items": overview.completed_items,
            "failed_items": overview.failed_items,
            "processed_items": overview.processed_items,
            "current_stage": overview.current_stage,
            "pause_requested": overview.pause_requested,
            "attention": overview.attention,
            "problem_types": list(overview.problem_types),
            "recovered_completion": overview.recovered_completion,
            "problem_file_counts": dict(overview.problem_file_counts),
            "attention_reason": overview.attention_reason,
            "attention_failure_category": overview.attention_failure_category,
            "attention_failure_next_action": overview.attention_failure_next_action,
            "configuration_snapshot_id": overview.configuration_snapshot_id,
            "worker_id": overview.worker_id,
            # The durable *manual* definition origin of a deliberate Run once,
            # or absent for an ordinary Files/CLI run.  It is admission-written
            # immutable evidence, so Automation history and Operations can reach
            # the same durable execution without a dummy Job or a read-time
            # guess from today's Active configuration.
            "manualDefinitionOrigin": (
                {
                    "kind": overview.origin_kind or "definition-run-once",
                    "definitionId": overview.origin_definition_id,
                    "definitionName": overview.origin_definition_name,
                }
                if overview.origin_definition_id
                else None
            ),
            "sideEffects": "none",
        }
        return redact_manual_value(document)

    def _automation_engine_settings_projection(
        self,
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """The focused four-field engine settings read and checked Save.

        This is a distinct contract from the generic managed Settings editor:
        ``GET`` states the published target plus each live consumer's own
        adoption, and ``PUT`` publishes exactly these four fields from the
        checked Active.  The generic ``/api/v1/system/settings`` Draft semantics
        stay unchanged and keep their own validation/activation journey.
        """

        service = getattr(self, "_automation_settings", None)
        if service is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        if method == "GET":
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "automation engine settings")
            document = service.read()
            document["authority"] = "MANAGED"
            document["canManage"] = self._principal_has_permission(
                principal, ApiPermission.MANAGE_CONFIGURATION
            )
            return self._response(start_response, 200, document)
        self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
        document = self._document(environ)
        expected: dict[str, object] = {}
        for key in ("expectedRevisionId", "expectedRevisionVersion", "expectedDigest"):
            value = document.pop(key, None)
            if value is None:
                continue
            if key == "expectedRevisionVersion":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(f"{key} must be an integer")
            elif not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            expected[key] = value
        # The client-generated submission identity names exactly this request, so
        # a lost response is reconciled against *its own* durable evidence rather
        # than against equal values that another writer published.
        submission_id = document.pop("submissionId", None)
        # An unknown submission is reconciled by reading durable evidence, never
        # by re-submitting the mutation automatically.
        if document.pop("reconcile", False) is True:
            payload = document.pop("settings", document)
            result = service.reconcile(
                payload,
                actor=principal.principal_id,
                submission_id=submission_id,
            )
            return self._response(start_response, 200, result)
        prepared: list[_ApiRuntimeBinding] = []
        with self._runtime_binding_lock:
            # Pin this process to the same save-time Active the predecessor was
            # observed from, exactly like every other checked Save.
            self._refresh_configuration_binding_locked()
            try:
                result = service.save(
                    document,
                    actor=principal.principal_id,
                    expected_revision_id=expected.get("expectedRevisionId"),  # type: ignore[arg-type]
                    expected_version=expected.get("expectedRevisionVersion"),  # type: ignore[arg-type]
                    expected_digest=expected.get("expectedDigest"),  # type: ignore[arg-type]
                    submission_id=submission_id,  # type: ignore[arg-type]
                    before_publish=lambda revision: prepared.append(
                        self._prepare_runtime_binding_for_revision(revision)
                    ),
                )
            except (ConfigurationActivationConflict, ConfigurationVersionConflict):
                # The repository fences concurrency authoritatively: consume the
                # winning Active before returning the stale/conflict result.
                self._refresh_configuration_binding_locked()
                raise
            except AutomationSettingsPublicationError as error:
                self._safe_audit(
                    environ,
                    None,
                    principal,
                    method,
                    "/api/v1/operations/automation/settings",
                    "automation-engine-settings",
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
            if result.get("published") is True:
                if len(prepared) != 1:
                    # Publication prepared no binding: this process must not claim
                    # it now serves the new Active.
                    self._refresh_configuration_binding_locked()
                    raise AutomationSettingsPublicationError(
                        "automation_settings_runtime_failed",
                        "the successor runtime binding was not prepared; the previous Active "
                        "remains in use",
                        status=503,
                        stage="prepare",
                        durable_state="active_preserved",
                        side_effects=(
                            "successor_draft_and_read_only_evidence_retained; "
                            "Active pointer unchanged"
                        ),
                        next_action=(
                            "correct the runtime configuration, refresh the published values and "
                            "save again"
                        ),
                    )
                # Publish the newly prepared runtime binding exactly like every
                # other checked Save, so this API process then reads the new Active.
                self._publish_runtime_binding(prepared[0])
        result["sideEffects"] = result.get("sideEffects", "none")
        result["readback"] = service.read()
        return self._response(start_response, 201 if result.get("published") else 200, result)

    @staticmethod
    def _principal_has_permission(
        principal: ResolvedApiPrincipal, permission: ApiPermission
    ) -> bool:
        return permission in getattr(principal, "permissions", frozenset())

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
        if (
            parts
            in (
                ["api", "v1", "operations", "automation", "metrics"],
                ["api", "v1", "operations", "automation", "records"],
            )
            and method == "GET"
        ):
            # The two Automation read-model surfaces need no managed
            # configuration service: a definition inventory without Active
            # configuration and an execution-record history of removed
            # definitions are exactly the states the operator must still be
            # able to read truthfully.
            self._require(principal, ApiPermission.READ)
            if parts[4] == "metrics":
                self._require_empty_query(environ, "automation metrics")
                return self._response(start_response, 200, self._automation_metrics_document())
            return self._automation_records_page(environ, start_response, principal)
        self._require(principal, ApiPermission.READ)
        if self._configuration_service is None or self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        if len(parts) == 5:
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
        return self._error(start_response, 404, "not_found", "route was not found")

    # ------------------------------------------------------------------
    # Automation inventory/records/metrics reads (RO-1/RO-5 read model)
    # ------------------------------------------------------------------

    _AUTOMATION_DEFINITIONS_QUERY_FIELDS = frozenset(
        {
            "limit",
            "cursor",
            "q",
            "enabled",
            "library",
            "sort",
            "direction",
            "state",
        }
    )
    _AUTOMATION_RUNS_QUERY_FIELDS = frozenset(
        {
            "limit",
            "cursor",
            "direction",
            "definition",
            "trigger",
            "status",
            "from",
            "to",
        }
    )
    #: The five admitted-run terminal states that form the success denominator.
    _AUTOMATION_TERMINAL_STATUSES = frozenset(
        {"completed", "partial_success", "failed", "cancelled"}
    )
    #: Bounded Automation inventory orderings; each has one deterministic tie.
    _AUTOMATION_DEFINITION_SORTS = frozenset({"name", "enabled", "nextRun", "latest", "limit"})

    def _automation_now(self) -> datetime:
        """The single evaluation instant the Automation cards are computed at.

        Overridable so a controlled-clock test can assert one exact calendar
        boundary without freezing the process clock; production always reads
        the real current instant.
        """

        return datetime.now(UTC)

    def _automation_system_timezone(self) -> str:
        """The one configured system timezone the metric calendar uses.

        Read from the same Active managed document the rest of the surface
        reads, never from a Cron/browser value.  An unreadable/absent timezone
        is explicitly ``UTC`` with a truthful ``available: False`` marker at
        the metric level, so a card never silently pretends a different zone.
        """

        binding = getattr(self, "_runtime_binding", None)
        configuration = getattr(binding, "runtime_configuration", None)
        timezone = getattr(configuration, "timezone", None)
        if isinstance(timezone, str) and timezone.strip():
            return timezone.strip()
        if self._configuration_service is not None:
            try:
                active = self._configuration_service.active()
            except Exception:
                active = None
            if active is not None and isinstance(active.document, dict):
                candidate = active.document.get("timezone")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        return "UTC"

    @staticmethod
    def _automation_metric_windows(now: datetime, timezone_name: str) -> dict[str, object]:
        """Month-to-date and clamped previous-period windows in one system zone.

        Both windows are derived from the *same* evaluation instant and the
        *same* configured IANA zone, so a DST transition, a leap day or an
        unequal month length cannot make the comparison period longer than the
        elapsed current period.  The windows are returned as absolute UTC
        instants (half-open) together with the exact local boundaries the
        operator can verify.
        """

        try:
            zone = ZoneInfo(timezone_name)
        except Exception:
            zone = ZoneInfo("UTC")
            timezone_name = "UTC"
        local_now = now.astimezone(zone)
        start_local = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_local.month == 12:
            next_start_local = start_local.replace(year=start_local.year + 1, month=1)
        else:
            next_start_local = start_local.replace(month=start_local.month + 1)
        if start_local.month == 1:
            previous_start_local = start_local.replace(year=start_local.year - 1, month=12)
        else:
            previous_start_local = start_local.replace(month=start_local.month - 1)
        # The previous month's comparable elapsed period, clamped to that
        # month's own end: short months and month-length differences never
        # stretch the comparison past a complete previous period.
        elapsed_seconds = (local_now - start_local).total_seconds()
        previous_period_end = previous_start_local + timedelta(seconds=elapsed_seconds)
        if previous_period_end > start_local:
            previous_period_end = start_local
        return {
            "timezone": timezone_name,
            "evaluatedAt": local_now.isoformat(),
            "current": {
                "startLocal": start_local.isoformat(),
                "endLocal": local_now.isoformat(),
                "nextPeriodStartLocal": next_start_local.isoformat(),
                "start": start_local.astimezone(UTC),
                "end": local_now.astimezone(UTC),
            },
            "previous": {
                "startLocal": previous_start_local.isoformat(),
                "endLocal": previous_period_end.astimezone(zone).isoformat(),
                "start": previous_start_local.astimezone(UTC),
                "end": previous_period_end.astimezone(UTC),
            },
        }

    def _automation_metrics_document(self) -> dict[str, object]:
        """The four full-population Automation cards (RO-1 metric contract).

        Every number is read from the shared deduplicated admitted-run
        population in one snapshot, so the cards never derive from the current
        browser page, the list filters or one definition's history.  A missing
        denominator or an unavailable query is published as explicitly
        unavailable/``None`` — never as a fabricated zero or percentage.
        """

        repository = self._repository
        reader = getattr(repository, "automation_run_metrics", None)
        timezone_name = self._automation_system_timezone()
        now = self._automation_now()
        windows = self._automation_metric_windows(now, timezone_name)
        current = windows["current"]
        previous = windows["previous"]
        base: dict[str, object] = {
            "available": False,
            "scope": "full_authorized_population",
            "basis": (
                "each original admitted run counted once by its durable admission "
                "timestamp in the configured system timezone"
            ),
            "timezone": timezone_name,
            "cronTimezoneNote": (
                "Cron definition timezones stay separate from this system calendar"
            ),
            "evaluatedAt": windows["evaluatedAt"],
            "windows": {
                "current": {
                    "start": current["start"].isoformat(),
                    "end": current["end"].isoformat(),
                    "startLocal": current["startLocal"],
                    "endLocal": current["endLocal"],
                    "nextPeriodStartLocal": current["nextPeriodStartLocal"],
                },
                "previous": {
                    "start": previous["start"].isoformat(),
                    "end": previous["end"].isoformat(),
                    "startLocal": previous["startLocal"],
                    "endLocal": previous["endLocal"],
                },
            },
            "sideEffects": "none",
        }
        if repository is None or not callable(reader):
            base["nextAction"] = (
                "restore the runtime database read model, then refresh the Automation cards"
            )
            base["denominatorStatement"] = "unavailable"
            return base
        try:
            values = reader(
                current_start=current["start"],
                current_end=current["end"],
                previous_start=previous["start"],
                previous_end=previous["end"],
            )
        except Exception:
            base["nextAction"] = "inspect the runtime database, then refresh the Automation cards"
            base["denominatorStatement"] = "unavailable"
            return base
        admitted = int(values.get("currentAdmitted", 0))
        previous_admitted = int(values.get("previousAdmitted", 0))
        terminal = int(values.get("currentTerminal", 0))
        completed = int(values.get("currentCompleted", 0))
        no_work = int(values.get("currentNoWork", 0))
        partial = int(values.get("currentPartial", 0))
        failed = int(values.get("currentFailed", 0))
        cancelled = int(values.get("currentCancelled", 0))
        uncertain = int(values.get("currentUncertain", 0))
        active = int(values.get("currentActive", 0))
        base.update(
            {
                "available": True,
                "monthToDateAdmitted": admitted,
                "previousPeriodAdmitted": previous_admitted,
                "comparisonAvailable": previous_admitted > 0,
                "comparisonUnavailableReason": (
                    None if previous_admitted > 0 else "no_comparable_previous_period"
                ),
                "monthToDateTerminal": terminal,
                "monthToDateActive": active,
                "monthToDateNoWork": no_work,
                "monthToDatePartial": partial,
                "monthToDateFailed": failed,
                "monthToDateCancelled": cancelled,
                "monthToDateUncertain": uncertain,
                "denominatorStatement": (
                    f"terminal admitted runs in the current local month ({terminal})"
                    if terminal > 0
                    else "no terminal admitted run in the current local month"
                ),
                "successRate": (completed / terminal if terminal > 0 else None),
                "completedCount": completed,
                "noWorkCount": no_work,
                "noWorkStatement": (
                    "skipped files are not organized files, a completed queue or "
                    "preparation row is not organizing success, a successful no-work "
                    "completion is labelled as such, and a reached item bound does not "
                    "prove scope exhaustion"
                ),
            }
        )
        return base

    def _automation_metric_window_document(self) -> dict[str, object]:
        return self._automation_metrics_document()

    @classmethod
    def _automation_records_query(cls, environ: dict, principal_id: str) -> dict[str, object]:
        """Bounded admitted-run record filters plus their principal-bound cursor.

        Every selector is one of the durable identities the shared run
        population exposes; an unknown or contradictory value is a rejected
        filter, never a silently different population.  A recovery attempt is a
        distinct admission with its own identity, so it appears as its own
        record and never replaces or duplicates the original.
        """

        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference(cls._AUTOMATION_RUNS_QUERY_FIELDS) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError(
                "automation records query accepts limit, cursor, direction, definition, "
                "trigger, status, from, and to once"
            )
        limit = cls._parse_bounded_limit(values.get("limit", ["20"])[0], "automation record")
        raw_direction = values.get("direction", ["next"])[0]
        if raw_direction not in {"next", "previous"}:
            raise ValueError("automation record direction is invalid")
        raw_definition = values.get("definition", [""])[0]
        definition_id = None if raw_definition in {"", "all"} else raw_definition
        if definition_id is not None and not _AUTOMATION_DEFINITION_FILTER.fullmatch(definition_id):
            raise ValueError("automation record definition filter is invalid")
        raw_trigger = values.get("trigger", [""])[0]
        if raw_trigger in {"", "all"}:
            trigger = None
        elif raw_trigger in {item.value for item in OperationsRunTrigger}:
            trigger = raw_trigger
        else:
            raise ValueError("automation record trigger filter is invalid")
        raw_status = values.get("status", [""])[0]
        if raw_status in {"", "all"}:
            status = None
        elif raw_status in cls._RUNS_STATUS_FILTER_VALUES:
            status = raw_status
        else:
            raise ValueError("automation record status filter is invalid")
        created_after = cls._run_time_filter(values.get("from", [""])[0], "from")
        created_before = cls._run_time_filter(values.get("to", [""])[0], "to")
        if created_after is not None and created_before is not None:
            if created_after > created_before:
                raise ValueError("automation record time window is inverted")
        scope = ";".join(
            (
                f"principal={principal_id}",
                "kind=automation-records",
                f"definition={definition_id or 'all'}",
                f"trigger={trigger or 'all'}",
                f"status={status or 'all'}",
                f"from={created_after.isoformat() if created_after else ''}",
                f"to={created_before.isoformat() if created_before else ''}",
            )
        )
        raw_cursor = values.get("cursor", [""])[0]
        cursor = (
            decode_directional_cursor(raw_cursor, "operations_runs", expected_scope=scope)
            if raw_cursor
            else None
        )
        if cursor is not None and cursor.direction.value != raw_direction:
            raise ValueError("automation record direction does not match its cursor")
        return {
            "limit": limit,
            "direction": raw_direction,
            "definition_id": definition_id,
            "trigger": trigger,
            "status": status,
            "created_after": created_after,
            "created_before": created_before,
            "cursor": cursor,
            "scope": scope,
        }

    #: The scheduler diagnostic outcomes that are *not* admitted runs.  They are
    #: durable due-state evidence that the Scheduler blocked or skipped an
    #: emission; they never became a Job, Task or execution.
    _AUTOMATION_BLOCKED_OUTCOMES = frozenset(
        {
            "blocked",
            "disabled",
            "unsupported",
            "failed",
        }
    )

    def _automation_records_page(
        self, environ: dict, start_response: Callable, principal: ResolvedApiPrincipal
    ):
        """One bounded page of admitted Automation runs (RO-5 read model).

        The records read is the *shared* deduplicated run population restricted
        to runs with a durable Automation origin, so a linked Job→Task pair
        stays one identity with one count, a pre-Task failure stays visible and
        a definition that has since been renamed or removed still resolves
        through its admission-written identity.  Every row is read-only: no
        analysis, no admission, no Provider/Storage access and no authority.
        """

        repository = self._repository
        window_reader = getattr(repository, "operations_runs_window", None)
        if repository is None or not callable(window_reader):
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "Automation execution records are unavailable for this runtime",
            )
        query = self._automation_records_query(environ, principal.principal_id)
        # The mandatory original-Automation-admission population predicate: an
        # ordinary Files/CLI run, a standalone manual organize Task, a
        # preparation-only discovery/analysis, a rejected or blocked attempt and
        # a Task Center recovery follow-up are never Automation execution
        # records.  It is applied as a population predicate *before* the page
        # window, the filtered total, the status partitions and the metrics, so
        # no optional definition/trigger filter can accidentally widen it.
        arguments: dict[str, object] = {
            "limit": query["limit"],
            "status": query["status"],
            "created_after": query["created_after"],
            "created_before": query["created_before"],
            "definition_id": query["definition_id"],
            "trigger": query["trigger"],
            "automation_admissions": True,
        }
        cursor = query["cursor"]
        if cursor is not None and cursor.direction is CursorDirection.PREVIOUS:
            window = window_reader(before=cursor.position, **arguments)
        else:
            window = window_reader(after=cursor.position if cursor else None, **arguments)
        page = window.page
        handling = self._automation_handling_evidence(page)
        failure_evidence = self._automation_failure_evidence(page)
        rows = [
            self._automation_record_document(
                item,
                principal,
                handling.get(item.run_id),
                failure_evidence.get(item.task_id) if item.task_id else None,
            )
            for item in page
        ]
        scope = query["scope"]
        return self._response(
            start_response,
            200,
            {
                "items": rows,
                "limit": query["limit"],
                "definition": query["definition_id"],
                "trigger": query["trigger"],
                "status": query["status"],
                "from": (query["created_after"].isoformat() if query["created_after"] else None),
                "to": (query["created_before"].isoformat() if query["created_before"] else None),
                "total": window.total,
                "statusCounts": window.status_counts,
                "truncated": bool(window.has_next),
                "population": ("admitted Automation runs deduplicated by explicit task linkage"),
                "historyBasis": (
                    "definition/name/scope/version from the durable admission, never "
                    "backfilled from the current Active configuration"
                ),
                "sideEffects": "none",
                "previous_cursor": self._run_page_cursor(
                    page, bool(window.has_previous), CursorDirection.PREVIOUS, scope
                ),
                "next_cursor": self._run_page_cursor(
                    page, bool(window.has_next), CursorDirection.NEXT, scope
                ),
            },
        )

    def _automation_handling_evidence(self, page) -> dict[str, dict]:
        """Durable follow-up evidence for one page of original runs.

        The read is batched per page and keyed by the run's own durable Task
        identity, so no unbounded scan happens.  An unavailable read is
        reported explicitly instead of being presented as "no follow-up".
        """

        repository = self._repository
        reader = getattr(repository, "automation_linked_handling", None)
        if not callable(reader):
            return {}
        task_ids = tuple(
            dict.fromkeys(item.task_id for item in page if getattr(item, "task_id", None))
        )
        if not task_ids:
            # Every run on this page is still pre-Task: there is nothing a
            # follow-up could link to, and "unhandled" is the honest state.
            return {}
        unavailable = {
            "state": "unavailable",
            "attempts": 0,
            "latestKind": None,
            "latestStatus": None,
            # An unavailable read proves nothing about coverage, so the counts
            # are explicitly absent-from-zero rather than a fabricated 0/0.
            "affectedItems": None,
            "resolvedItems": None,
            "unresolvedItems": None,
            "nextAction": (
                "the linked follow-up state could not be read; reload this record and, if it "
                "stays unavailable, inspect the exact Task Center run"
            ),
        }
        try:
            by_task = reader(task_ids)
        except Exception:
            # A failed read is never "no follow-up" and never "unhandled": the
            # operator must not be told there is nothing to handle when the
            # evidence simply could not be read.
            return {item.run_id: dict(unavailable) for item in page}
        if not isinstance(by_task, dict):
            return {item.run_id: dict(unavailable) for item in page}
        handling: dict[str, dict] = {}
        for item in page:
            if not item.task_id:
                # A pre-Task run genuinely has nothing a follow-up could link
                # to yet, so "unhandled" is the honest state.
                handling[item.run_id] = {
                    "state": "unhandled",
                    "attempts": 0,
                    "latestKind": None,
                    "latestStatus": None,
                    "affectedItems": 0,
                    "resolvedItems": 0,
                    "unresolvedItems": 0,
                    "nextAction": (
                        "open the exact Task Center run once this admission acquires its Task"
                    ),
                }
                continue
            evidence = by_task.get(item.task_id)
            handling[item.run_id] = evidence if isinstance(evidence, dict) else dict(unavailable)
        return handling

    def _automation_failure_evidence(self, page) -> dict[str, dict]:
        """Batched concrete per-item failure evidence for this page's runs.

        A records read must tell the operator why an affected item failed and
        what is known about its effects, using the durable evidence that already
        exists on the linked Task's failed/partial items and their Results.  The
        read is batched per page and bounded, and an unavailable read stays
        explicitly unavailable rather than being published as "no failure".
        """

        repository = self._repository
        reader = getattr(repository, "automation_record_failure_evidence", None)
        if not callable(reader):
            return {}
        task_ids = tuple(
            dict.fromkeys(item.task_id for item in page if getattr(item, "task_id", None))
        )
        if not task_ids:
            return {}
        try:
            return reader(task_ids)
        except Exception:
            return {}

    def _automation_record_document(
        self,
        overview,
        principal: ResolvedApiPrincipal,
        handling: dict | None = None,
        failure_evidence: dict | None = None,
    ) -> dict[str, object]:
        """One read-only Automation execution record with its exact next action.

        The record reports the *original* durable outcome, its real execution
        window, reached bound, item evidence, stage/reason and known effects,
        plus its separately linked follow-up handling state and the exact legal
        next action.  It never embeds a file-decision form, re-analysis,
        pause/continue/cancel, retry command or recovery execution: after a
        durable formal organizing Task exists, all of that belongs to the exact
        native Task Center run.
        """

        document = self._operations_run_document(overview)
        task_center = (
            {"runId": overview.task_id, "path": f"/api/v1/operations/runs/{overview.task_id}"}
            if overview.task_id
            else None
        )
        job_center = (
            {"jobId": overview.job_id, "path": f"/api/v1/operations/jobs/{overview.job_id}"}
            if overview.job_id
            else None
        )
        route = self._automation_record_route(overview)
        document["recordId"] = overview.run_id
        document["origin"] = (
            {
                "kind": overview.origin_kind,
                "definitionId": overview.origin_definition_id,
                "definitionName": overview.origin_definition_name,
            }
            if overview.origin_definition_id
            else None
        )
        # The real execution window.  A pending/queued row has none, and
        # ``created_at``/``updated_at`` are never relabelled as execution start
        # or end.
        document["executionStartedAt"] = (
            overview.execution_started_at.isoformat()
            if overview.execution_started_at is not None
            else None
        )
        document["executionFinishedAt"] = (
            overview.execution_finished_at.isoformat()
            if overview.execution_finished_at is not None
            else None
        )
        document["historyContext"] = {
            "definitionId": overview.definition_id or overview.origin_definition_id,
            "definitionName": overview.origin_definition_name,
            "sourceScope": document.get("source_scope"),
            "trigger": overview.trigger.value,
            "scheduleId": overview.schedule_id,
            "recoveredFrom": None,
        }
        # The result envelope: the original outcome plus the durable item
        # evidence behind it.  A completed queue/admission row and a no-work
        # completion are explicitly distinguished from organizing success.
        document["result"] = {
            "status": overview.status.value,
            "organized": overview.organized_successfully,
            "noWork": overview.no_work_completion,
            "successItems": overview.organization_success_items,
            "uncertainSuccessItems": overview.uncertain_success_items,
            "reachedItemBound": overview.reached_item_bound,
            "admittedItemBound": overview.admitted_item_bound,
            "statement": self._automation_record_result_statement(overview),
        }
        document["failureStage"] = self._automation_record_failure_stage(overview, failure_evidence)
        document["nextAction"] = route["next_action"]
        # The separately linked follow-up handling state.  It never rewrites the
        # original outcome; a recovery attempt is not a new scheduled trigger and
        # a changed current Task status cannot prove recovery success.
        document["handling"] = handling or {
            # No linked follow-up is a truthful state, not a failed read: a
            # pre-Task admission simply has nothing a repair could attach to yet.
            "state": "unhandled",
            "attempts": 0,
            "latestKind": None,
            "latestStatus": None,
            "affectedItems": 0,
            "resolvedItems": 0,
            "unresolvedItems": 0,
            "nextAction": ("open the exact Task Center run once this admission acquires its Task"),
        }
        document["handoff"] = {
            # Ownership is determined by the durable formal-execution evidence,
            # never by the first media mutation and never by an absent Task
            # link alone.
            "ownership": route["ownership"],
            "formalExecution": route["formal_execution"],
            "durableState": route["durable_state"],
            "explanation": route["explanation"],
            "taskCenter": task_center,
            "job": job_center,
            "definitionSettings": (
                f"/ui-v2/operations/automation/definition/"
                f"{overview.definition_id or overview.origin_definition_id}"
                if (overview.definition_id or overview.origin_definition_id)
                else None
            ),
            "supportedCommand": route["supported_command"],
            "supportedCommandPath": route["supported_command_path"],
            "startAgainAllowed": False,
            "retryExplanation": route["retry_explanation"],
        }
        return document

    @staticmethod
    def _automation_record_result_statement(overview) -> str:
        """One bounded, truthful statement of what this run's result means."""

        if overview.organized_successfully:
            return f"已整理 {overview.organization_success_items} 个条目" + (
                f"（另有 {overview.uncertain_success_items} 个条目效果不确定，不计为成功）"
                if overview.uncertain_success_items
                else ""
            )
        if overview.no_work_completion:
            status = overview.status.value
            if status == "completed":
                return "本次执行已完成，但没有产生已整理的条目（无工作完成）"
            return "本次执行尚未产生已整理的条目"
        if overview.uncertain_success_items:
            return (
                f"有 {overview.uncertain_success_items} 个条目效果不确定，"
                "不会被当作整理成功；请在任务中心核对已知效果"
            )
        if overview.status.value == "partial_success":
            return "部分条目已整理，其余条目有独立结果；请在任务中心查看逐项结果"
        if overview.status.value == "failed":
            return "本次执行失败；已受理的运行和逐项结果仍然保留，请在任务中心查看原因"
        if overview.status.value == "cancelled":
            return "本次执行已取消；已完成的效果保持不变，未执行的部分没有被重放"
        return "本次执行仍在进行或等待，逐项结果会在任务中心更新"

    @staticmethod
    def _automation_record_failure_stage(
        overview, failure_evidence: dict | None = None
    ) -> dict[str, object] | None:
        """The bounded failure stage/reason of one record, or ``None``.

        Two truthful shapes exist:

        - a proven settled **pre-start** failure publishes the structured
          durable category and next action the Job itself recorded;
        - a **formal Task** failure publishes the concrete evidence that already
          exists on its failed/partial items and their Results: the bounded
          failure category/message, the durable stage, the per-item known or
          uncertain effects and the exact safe next action.

        No raw exception text is ever published, and admission completion is
        never a failure stage.  When the linked evidence cannot be read the
        record says so explicitly instead of silently showing no reason.
        """

        # A settled pre-start failure keeps its structured durable repair facts
        # for this explicit administrative handoff, even though Task Center
        # RO-4 does not treat it as a fifth attention type.
        if (
            not overview.task_id
            and overview.attention_failure_category
            and overview.attention_failure_next_action
            and overview.status.value == "failed"
        ):
            return {
                "stage": "before_formal_execution",
                "category": overview.attention_failure_category,
                "nextAction": overview.attention_failure_next_action,
                "statement": ("整理开始前失败：没有创建正式整理任务，也没有产生媒体效果"),
            }
        if overview.status.value not in {"failed", "partial_success"}:
            return None
        if not overview.task_id:
            return None
        items = (failure_evidence or {}).get("items") or []
        # ``bounded_failure_document`` decodes this backend's own envelope and
        # otherwise classifies the persisted value into the same closed set, so
        # a legacy or adapter-written error column never surfaces raw text.
        decoded = [
            (value, bounded_failure_document(value.get("error")) if value.get("error") else None)
            for value in items
            if isinstance(value, dict)
        ]
        explained = [(value, document) for value, document in decoded if document is not None]
        lead = next((document for _value, document in explained if document), None)
        stage_values = [
            str(value["stage"])
            for value, _document in decoded
            if value.get("stage") not in {None, ""}
        ]
        stage = (
            f"{overview.current_stage}_stage"
            if overview.current_stage
            else (f"{stage_values[0]}_stage" if stage_values else "linked_task_stage")
        )
        if not items:
            # The same closed shape as an inspectable failure, with every
            # count explicitly absent-from-zero: a Web consumer must not have to
            # guess which keys a partially-unavailable document carries.
            return {
                "stage": stage,
                "category": None,
                "nextAction": None,
                "statement": (
                    "正式整理任务已经存在，但持久化的逐项失败原因当前不可读；"
                    "请在任务中心核对该运行的条目证据"
                ),
                "unavailable": True,
                "items": [],
                "effects": {"none": 0, "known": 0, "uncertain": 0, "partial": 0},
                "itemsTruncated": False,
            }
        # The effect partition covers the whole durable failed/partial item
        # population (the repository computes it separately from the bounded
        # sample), so a count is never silently the sample size.
        raw_effects = (failure_evidence or {}).get("effects") or {}
        effects = {
            key: int(raw_effects.get(key) or 0) for key in ("none", "known", "uncertain", "partial")
        }
        item_documents = [
            {
                "itemId": value.get("itemId"),
                "status": value.get("status"),
                "stage": value.get("stage"),
                "destination": value.get("destination"),
                "category": (document or {}).get("category"),
                "message": (document or {}).get("message"),
                "durableState": (document or {}).get("durableState"),
                "sideEffects": (document or {}).get("sideEffects"),
                "retrySafe": (document or {}).get("retrySafe"),
                "nextAction": (document or {}).get("nextAction"),
                "effectCertainty": value.get("effectCertainty"),
                # Whether this entry is the durable failed/partial Result (its
                # own status and effect certainty) or the current TaskItem
                # fallback, which exists only because no such Result does.
                "statusSource": value.get("statusSource"),
            }
            for value, document in decoded
        ]
        affected = (failure_evidence or {}).get("failedItems") or 0
        affected += (failure_evidence or {}).get("partialItems") or 0
        affected = affected or len(items)
        statement = (
            f"正式整理任务中有 {affected} 个条目失败或部分完成，原因与已知效果已记录"
            if lead is None
            else f"正式整理任务中有 {affected} 个条目失败或部分完成：{lead['message']}"
        )
        return {
            "stage": stage,
            "category": (lead or {}).get("category"),
            "nextAction": (lead or {}).get("nextAction"),
            "statement": statement,
            "items": item_documents,
            "effects": effects,
            "itemsTruncated": bool((failure_evidence or {}).get("truncated")),
            "unavailable": False,
        }

    @staticmethod
    def _automation_record_route(overview) -> dict[str, object]:
        """Classify one record's recovery ownership from durable evidence only.

        Three disjoint cases are published:

        - ``task_center``: a formal organizing Task exists (including one that
          failed during scanning/recognition/metadata/planning before any
          mutation).  Every execution/recovery command belongs to that Task.
        - ``prestart_repair``: a proven settled pre-start failure with a stable
          failure category and next action, no Task and no claimed/queued work.
          Only the existing supported definition command may be used again, and
          only after the command owner revalidates the current context.
        - ``reconcile``: an ambiguous handoff or unknown effect.  The operator
          must reconcile/investigate before any further command; no start-again
          retry is offered.
        """

        has_task = overview.task_id is not None
        if has_task:
            return {
                "ownership": "task_center",
                "formal_execution": True,
                "durable_state": "formal_execution_exists",
                "explanation": (
                    "a durable organizing Task exists for this run; its plan, per-item "
                    "results and every recovery command belong to that exact Task Center run"
                ),
                "supported_command": None,
                "supported_command_path": None,
                "next_action": {
                    "kind": "task-center-run",
                    "runId": overview.task_id,
                    "statement": ("在一次正式整理任务中选择安全动作，例如重新分析、继续或恢复条目"),
                },
                "retry_explanation": (
                    "Task Center owns recovery for this run; successful or uncertain "
                    "effects are never replayed from Automation"
                ),
            }
        status = overview.status.value
        if status in {"pending", "running", "paused", "waiting"}:
            return {
                "ownership": "reconcile",
                "formal_execution": False,
                "durable_state": "attempt_in_progress",
                "explanation": (
                    "this admission is still queued, claimed or running; it is not a "
                    "settled pre-start failure and no second attempt may be started"
                ),
                "supported_command": None,
                "supported_command_path": None,
                "next_action": {
                    "kind": "wait",
                    "statement": "等待这次执行结束，再重新读取该记录；当前不能再次发起",
                },
                "retry_explanation": (
                    "wait for this attempt to settle; a settled record can then be "
                    "reconciled and, if provably pre-start, re-run deliberately"
                ),
            }
        if (
            status == "failed"
            and not has_task
            and overview.attention_failure_category
            and overview.attention_failure_next_action
        ):
            definition_id = overview.definition_id or overview.origin_definition_id
            command = "run-once" if overview.origin_definition_id else "scheduled-evaluation"
            return {
                "ownership": "prestart_repair",
                "formal_execution": False,
                "durable_state": "settled_before_formal_execution",
                "explanation": (
                    "this admission failed before any formal organizing execution or "
                    "media effect; repair the stated prerequisite, then deliberately "
                    "start a new run from the definition"
                ),
                "supported_command": command,
                "supported_command_path": (
                    f"/ui-v2/operations/automation/definition/{definition_id}"
                    if definition_id
                    else None
                ),
                "definition_settings": definition_id,
                "next_action": {
                    "kind": "repair-prerequisite",
                    "definitionId": definition_id,
                    "category": overview.attention_failure_category,
                    "statement": (
                        overview.attention_failure_next_action
                        or "修复失败阶段指出的前置条件，再显式重新发起一次"
                    ),
                },
                "retry_explanation": (
                    "the existing supported definition command may be used again after "
                    "the prerequisite is repaired and the current scope, pins and "
                    "authority are revalidated; this record stays as the historical fact"
                ),
            }
        return {
            "ownership": "reconcile",
            "formal_execution": False,
            "durable_state": "handoff_uncertain",
            "explanation": (
                "no durable Task proves a formal execution, but the handoff or its "
                "effects cannot be proven absent; investigate before any command"
            ),
            "supported_command": None,
            "supported_command_path": None,
            "next_action": {
                "kind": "investigate",
                "statement": (
                    "先核对这次执行的持久证据（是否有正式任务或已知媒体效果），确认之前不要重试"
                ),
            },
            "retry_explanation": (
                "start-again is refused while the handoff is ambiguous; reconcile the "
                "durable evidence first and preserve this record"
            ),
        }

    def _automation_run_once_projection(
        self,
        definition_id: str,
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """Definition-bound Run once: prompt durable admission and readback.

        The published definition itself supplies the ResourceLibrary, source
        sub-scope and effective bound, so the operator never re-selects files.
        One explicit POST atomically admits the pinned organizing Task/Job and
        returns its durable identity promptly; the resident Processing Worker
        performs discovery, stability, planning and execution.  No separate
        execution authority or second initial confirmation is required.
        """

        service = getattr(self, "_automation_run_once", None)
        if service is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "definition Run once is unavailable",
                details={
                    "durableState": "no_work_started",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": "restore the bounded discovery service and retry Run once",
                },
            )
        if method == "GET":
            # Reconcile one lost Run-once response by the *client's own* request
            # identity.  The request id is generated before the POST, so it
            # identifies the actual admission however the Active pin changed
            # while the response was in flight; it is principal-scoped and never
            # guesses from a latest/list window.
            self._require(principal, ApiPermission.READ)
            query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(query) != {"admissionRequestId"} or len(query["admissionRequestId"]) != 1:
                raise ValueError(
                    "automation Run once reconciliation requires one admissionRequestId"
                )
            request_id = query["admissionRequestId"][0]
            execution = service.find_execution(principal.principal_id, request_id)
            if execution is not None:
                if execution.definition_id != definition_id:
                    return self._error(
                        start_response,
                        404,
                        "run_once_request_not_found",
                        "request not found for this definition",
                    )
                return self._response(start_response, 200, service.document(execution))
            discovery_service = getattr(self, "_media_discovery", None)
            finder = (
                getattr(discovery_service, "find_by_request_id", None)
                if discovery_service is not None
                else None
            )
            if not callable(finder):
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "Run-once request reconciliation is unavailable",
                )
            try:
                discovery = finder(actor=principal.principal_id, admission_request_id=request_id)
            except DiscoveryError as error:
                return self._discovery_step_error(start_response, error)
            if discovery is None or discovery.definition_origin is None:
                # A proved absence is a bounded 404, never a fabricated run.
                return self._error(
                    start_response,
                    404,
                    "run_once_request_not_found",
                    "no Run once was admitted for this request identity",
                    details={
                        "durableState": "unknown",
                        "sideEffects": "none",
                        "retrySafe": True,
                        "nextAction": (
                            "the response was lost before admission was proved; reload the "
                            "definition and start Run once again with a new request identity"
                        ),
                    },
                )
            return self._response(start_response, 200, service.document(discovery))
        if method == "POST":
            self._require(principal, ApiPermission.EXECUTE_MANUAL_ORGANIZE)
            self._require_empty_query(environ, "automation definition Run once")
            document = self._document(environ)
            allowed = {
                "admissionRequestId",
                "expectedDefinitionFingerprint",
                "expectedRevisionId",
                "expectedRevisionVersion",
                "expectedRevisionDigest",
            }
            if set(document).difference(allowed):
                raise ValueError(
                    "automation definition Run once accepts only an optional admissionRequestId "
                    "and the observed definition/configuration fence"
                )
            request_id = document.get("admissionRequestId")
            if request_id is not None and (
                not isinstance(request_id, str) or not request_id.strip()
            ):
                raise ValueError(
                    "automation definition Run once admissionRequestId must be text or null"
                )
            fingerprint = document.get("expectedDefinitionFingerprint")
            if fingerprint is not None and (
                not isinstance(fingerprint, str) or not fingerprint.strip()
            ):
                raise ValueError(
                    "automation definition Run once expectedDefinitionFingerprint must be "
                    "text or null"
                )
            revision_id = document.get("expectedRevisionId")
            if revision_id is not None and (
                not isinstance(revision_id, str) or not revision_id.strip()
            ):
                raise ValueError(
                    "automation definition Run once expectedRevisionId must be text or null"
                )
            revision_version = document.get("expectedRevisionVersion")
            if revision_version is not None and (
                isinstance(revision_version, bool) or not isinstance(revision_version, int)
            ):
                raise ValueError(
                    "automation definition Run once expectedRevisionVersion must be an "
                    "integer or null"
                )
            revision_digest = document.get("expectedRevisionDigest")
            if revision_digest is not None and (
                not isinstance(revision_digest, str) or not revision_digest.strip()
            ):
                raise ValueError(
                    "automation definition Run once expectedRevisionDigest must be text or null"
                )
            try:
                discovery = service.admit_execution(
                    definition_id,
                    actor=principal.principal_id,
                    admission_request_id=request_id,
                    expected_definition_fingerprint=fingerprint,
                    expected_revision_id=revision_id,
                    expected_revision_version=revision_version,
                    expected_revision_digest=revision_digest,
                )
                return self._response(start_response, 202, service.document(discovery))
            except (AutomationRunOnceError, DiscoveryError) as error:
                return self._discovery_step_error(start_response, error)
        self._require(principal, ApiPermission.READ)
        self._require_empty_query(environ, "automation definition Run once detail")
        try:
            discovery = service.get(definition_id)
            return self._response(start_response, 200, service.document(discovery))
        except (AutomationRunOnceError, DiscoveryError) as error:
            return self._discovery_step_error(start_response, error)

    def _automation_run_once_detail_projection(
        self,
        discovery_id: str,
        action: str | None,
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """Read, control or freeze one durable definition-bound Run once.

        The durable identity is the discovery id the admission returned, so a
        reload or reconnect restores the same run without re-walking sources.
        Freezing produces the exact zero-mutation Preview and still creates no
        execution authority.
        """

        service = getattr(self, "_automation_run_once", None)
        if service is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "definition Run once is unavailable",
                details={
                    "durableState": "no_work_started",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": "restore the bounded discovery service and retry Run once",
                },
            )
        discovery_service = getattr(self, "_media_discovery", None)
        if action is None and method == "GET":
            self._require(principal, ApiPermission.READ)
            self._require_empty_query(environ, "automation Run once detail")
            try:
                discovery = service.get(discovery_id)
                return self._response(start_response, 200, service.document(discovery))
            except (AutomationRunOnceError, DiscoveryError) as error:
                return self._discovery_step_error(start_response, error)
        if action in {"pause", "cancel", "resume"} and method == "POST":
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            self._require_empty_query(environ, "automation Run once control")
            if discovery_service is None:
                return self._discovery_unavailable(start_response)
            document = self._document(environ)
            if set(document) != {"expectedVersion"}:
                raise ValueError("automation Run once control requires only expectedVersion")
            try:
                if action == "pause":
                    value = discovery_service.request_pause(
                        discovery_id,
                        actor=principal.principal_id,
                        expected_version=document["expectedVersion"],
                    )
                elif action == "cancel":
                    value = discovery_service.request_cancel(
                        discovery_id,
                        actor=principal.principal_id,
                        expected_version=document["expectedVersion"],
                    )
                else:
                    value = discovery_service.resume(
                        discovery_id,
                        actor=principal.principal_id,
                        expected_version=document["expectedVersion"],
                    )
                return self._response(start_response, 200, service.document(value))
            except (AutomationRunOnceError, DiscoveryError) as error:
                return self._discovery_step_error(start_response, error)
        if action == "finalize" and method == "POST":
            # Freeze the complete bounded manifest and enter the durable shared
            # analysis stage: the resident Worker produces the exact zero-mutation
            # plan on this same run and links it here.  A budget/safety-limited
            # walk is refused here rather than executed as a truncated prefix.
            self._require(principal, ApiPermission.MANAGE_MANUAL_ORGANIZE)
            self._require_empty_query(environ, "automation Run once finalize")
            document = self._document(environ)
            if set(document) != {"expectedVersion"}:
                raise ValueError("automation Run once finalize requires only expectedVersion")
            try:
                frozen, _preview = service.finalize(
                    discovery_id,
                    actor=principal.principal_id,
                    expected_version=document["expectedVersion"],
                )
            except (AutomationRunOnceError, DiscoveryError) as error:
                return self._discovery_step_error(start_response, error)
            payload = service.document(frozen)
            payload["intentId"] = frozen.intent_id
            # The exact plan is durable work of this same run: the response names
            # the analyzing stage and the plain run read (a reload, reconnect or
            # restart) restores the plan identity once the Worker links it.  No
            # plan, analysis identity or execution authority is created inline.
            payload["previewId"] = None
            payload["previewPath"] = None
            payload["analysisId"] = None
            payload["analysisPath"] = None
            return self._response(start_response, 201, payload)
        return self._error(start_response, 404, "not_found", "route was not found")

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

    def _automation_definition_focused_projection(
        self,
        parts: list[str],
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """The native V2 Automation definition lifecycle surface.

        Routes (all under ``/api/v1/operations/automation/definitions``):

        * ``GET  /``                     — form authority (fields/references/bounds)
        * ``POST /``                     — one checked create Save
        * ``POST /schedule-preview``     — zero-mutation upcoming-run calculation
        * ``GET  /{id}``                 — typed edit prefill (published or Draft-only)
        * ``PUT  /{id}``                 — one checked edit Save
        * ``POST /{id}/copy``            — one checked copy publication (disabled, no authority)
        * ``GET  /{id}/copy-candidate``  — read-only copy candidate
        * ``GET  /{id}/copy-intent``     — read-only copy reconciliation evidence
        * ``POST /{id}/enable|disable``  — one checked enabled-state publication
        * ``GET  /{id}/removal-impact``  — read-only removal evidence
        * ``DELETE /{id}``               — one checked removal (revokes future authority first)

        Every command reuses the shared application service, permissions,
        validation, audit and concurrency boundaries.  Nothing here creates a
        scan, Task, Job, schedule occurrence, notification, Provider call or
        Storage mutation.
        """

        if self._automation_workspace is None or self._configuration_service is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        base = ["api", "v1", "operations", "automation", "definitions"]
        if parts[:5] != base:
            return self._error(start_response, 404, "not_found", "route was not found")

        # -- collection ---------------------------------------------------
        if parts == base:
            if method == "GET":
                self._require_empty_query(environ, "automation definition form authority")
                self._require(principal, ApiPermission.READ)
                return self._automation_definition_document(
                    start_response, lambda: self._automation_workspace.form_authority()
                )
            if method == "POST":
                self._require_empty_query(environ, "automation definition create")
                self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
                self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
                document = self._document(environ)
                value, authority = self._automation_command_envelope(document, None)
                return self._automation_definition_publish(
                    start_response,
                    principal,
                    object_id=None,
                    value=value,
                    authority=authority,
                    action="create",
                )
            return self._error(start_response, 405, "method_not_allowed", "GET or POST required")
        if len(parts) == 6 and parts[5] == "schedule-preview":
            if method != "POST":
                return self._error(
                    start_response, 405, "method_not_allowed", "POST required for schedule preview"
                )
            self._require_empty_query(environ, "automation definition schedule preview")
            self._require(principal, ApiPermission.READ)
            document = self._document(environ)
            if set(document) != {"candidate", "objectId"}:
                raise ValueError("automation schedule preview requires candidate and objectId only")
            candidate = document["candidate"]
            if not isinstance(candidate, dict):
                raise ValueError("automation schedule preview candidate must be an object")
            object_id = document["objectId"]
            if object_id is not None and (not isinstance(object_id, str) or not object_id.strip()):
                raise ValueError("automation schedule preview objectId must be text or null")
            return self._automation_definition_document(
                start_response,
                lambda: self._automation_workspace.schedule_preview(candidate, object_id=object_id),
            )

        if len(parts) < 6:
            return self._error(start_response, 404, "not_found", "route was not found")
        definition_id = parts[5]

        if len(parts) == 6:
            if method == "GET":
                self._require_empty_query(environ, "automation definition edit projection")
                self._require(principal, ApiPermission.READ)
                return self._automation_definition_document(
                    start_response,
                    lambda: self._automation_workspace.edit_projection(definition_id),
                )
            if method == "PUT":
                self._require_empty_query(environ, "automation definition edit")
                self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
                self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
                document = self._document(environ)
                value, authority = self._automation_command_envelope(document, definition_id)
                return self._automation_definition_publish(
                    start_response,
                    principal,
                    object_id=definition_id,
                    value=value,
                    authority=authority,
                    action="edit",
                )
            if method == "DELETE":
                self._require_empty_query(environ, "automation definition removal")
                self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
                self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
                document = self._document(environ)
                allowed = {"expectedRevisionId", "expectedVersion", "expectedDigest", "reason"}
                if set(document).difference(allowed):
                    raise ValueError(
                        "automation definition removal accepts the observed Active identity "
                        "and an optional reason only"
                    )
                authority = self._automation_command_envelope(
                    document, definition_id, object=False
                )[1]
                reason = document.get("reason")
                if reason is not None and (not isinstance(reason, str) or len(reason) > 512):
                    raise ValueError("automation definition removal reason must be bounded text")
                return self._automation_definition_publish(
                    start_response,
                    principal,
                    object_id=definition_id,
                    value=None,
                    authority=authority,
                    action="remove",
                    reason=reason,
                )
            return self._error(
                start_response, 405, "method_not_allowed", "GET, PUT or DELETE required"
            )

        if len(parts) == 7 and parts[6] == "publication-intent":
            self._require(principal, ApiPermission.READ)
            if method != "POST":
                return self._error(
                    start_response,
                    405,
                    "method_not_allowed",
                    "POST required for exact reconciliation",
                )
            self._require_empty_query(environ, "publication reconciliation")
            document = self._document(environ)
            if set(document) != {
                "action",
                "object",
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
            }:
                raise ValueError(
                    "publication reconciliation requires the exact command and observed identity"
                )
            return self._automation_definition_document(
                start_response,
                lambda: self._automation_workspace.publication_intent(
                    definition_id,
                    actor=principal.principal_id,
                    action=document["action"],
                    candidate=document["object"],
                    expected_revision_id=document["expectedRevisionId"],
                    expected_version=document["expectedVersion"],
                    expected_digest=document["expectedDigest"],
                ),
            )
        if len(parts) == 7 and parts[6] == "copy-candidate":
            if method != "GET":
                return self._error(
                    start_response, 405, "method_not_allowed", "GET required for a candidate read"
                )
            self._require_empty_query(environ, "automation definition copy candidate")
            self._require(principal, ApiPermission.READ)
            return self._automation_definition_document(
                start_response,
                lambda: self._automation_workspace.copy_projection(definition_id),
            )
        if len(parts) == 7 and parts[6] == "copy-intent":
            if method != "GET":
                return self._error(
                    start_response,
                    405,
                    "method_not_allowed",
                    "GET required for copy-intent reconciliation",
                )
            self._require(principal, ApiPermission.READ)
            # The reconciliation binds to the exact submitted intent: the
            # observed Active identity the lost Copy was submitted against.
            # Without the fence the read still resolves durable evidence, but a
            # later submission's copy is never named as this intent's result.
            query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
            if set(query).difference(
                {"expectedRevisionId", "expectedVersion", "expectedDigest"}
            ) or any(len(value) != 1 for value in query.values()):
                raise ValueError(
                    "automation definition copy intent accepts the observed Active identity "
                    "query fields at most once each"
                )
            expected_revision_id = query.get("expectedRevisionId", [None])[0]
            expected_version = query.get("expectedVersion", [None])[0]
            expected_digest = query.get("expectedDigest", [None])[0]
            if expected_version is not None:
                try:
                    expected_version = int(expected_version)
                except ValueError as error:
                    raise ValueError(
                        "automation definition copy intent expectedVersion must be an integer"
                    ) from error
            return self._automation_definition_document(
                start_response,
                lambda: self._automation_workspace.copy_intent(
                    definition_id,
                    expected_revision_id=expected_revision_id,
                    expected_version=expected_version,
                    expected_digest=expected_digest,
                ),
            )
        if len(parts) == 7 and parts[6] == "run-once":
            # Definition-bound Run once on the focused lifecycle base.  The
            # published definition itself supplies the ResourceLibrary, source
            # sub-scope and effective bound, so no file selection is sent.  One
            # explicit command admits a real organizing Task; the resident
            # Worker performs discovery, planning and execution.
            if method not in {"GET", "POST"}:
                return self._error(
                    start_response, 405, "method_not_allowed", "GET or POST required"
                )
            return self._automation_run_once_projection(
                definition_id, method, environ, start_response, principal
            )
        if (
            len(parts) == 8
            and parts[6] == "run-once"
            and parts[7]
            in {
                "pause",
                "cancel",
                "resume",
                "finalize",
            }
        ):
            if method != "POST":
                return self._error(start_response, 405, "method_not_allowed", "POST required")
            return self._automation_run_once_detail_projection(
                parts[5], parts[7], method, environ, start_response, principal
            )
        if len(parts) == 7 and parts[6] == "removal-impact":
            if method != "GET":
                return self._error(
                    start_response, 405, "method_not_allowed", "GET required for removal evidence"
                )
            self._require_empty_query(environ, "automation definition removal impact")
            self._require(principal, ApiPermission.READ)
            return self._automation_definition_document(
                start_response,
                lambda: self._automation_workspace.removal_impact(definition_id),
            )
        if len(parts) == 7 and parts[6] in {"copy", "enable", "disable"}:
            if method != "POST":
                return self._error(
                    start_response,
                    405,
                    "method_not_allowed",
                    "POST required for a lifecycle command",
                )
            self._require_empty_query(environ, "automation definition lifecycle command")
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
            document = self._document(environ)
            authority = self._automation_command_envelope(document, definition_id, object=False)[1]
            return self._automation_definition_publish(
                start_response,
                principal,
                object_id=definition_id,
                value=None,
                authority=authority,
                action=parts[6],
            )
        return self._error(start_response, 404, "not_found", "route was not found")

    def _automation_definition_document(
        self, start_response: Callable, produce: Callable[[], dict]
    ):
        try:
            return self._response(start_response, 200, produce())
        except LookupError as error:
            return self._error(
                start_response,
                404,
                "not_found",
                str(error),
                details={
                    "durableState": "active_unchanged",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "refresh the Active Automation inventory and choose an existing definition"
                    ),
                },
            )
        except RuntimeSnapshotUnavailable as error:
            return self._error(
                start_response,
                503,
                "configuration_unavailable",
                str(error),
                details={
                    "reason": error.reason,
                    "durableState": (
                        "no_active_configuration"
                        if error.reason == "active_missing"
                        else "managed_active_unavailable"
                    ),
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "complete first setup in Settings and activate a configuration, then "
                        "return to Automation"
                        if error.reason == "active_missing"
                        else "repair or replace the unavailable Active configuration, then refresh"
                    ),
                },
            )

    @staticmethod
    def _automation_command_envelope(
        document: dict,
        object_id: str | None,
        *,
        object: bool = True,
    ) -> tuple[dict | None, tuple[str, int, str]]:
        """Validate the bounded command envelope before it reaches the application.

        Exactly the advertised fields are accepted: the typed definition for a
        Save and the observed Active identity for every command.  A missing or
        extra key is rejected rather than ignored, so a stale or partially-built
        browser request can never publish a different successor than the operator
        reviewed.
        """

        fields = {"expectedRevisionId", "expectedVersion", "expectedDigest"}
        if object:
            fields.add("object")
        if set(document) != fields:
            raise ValueError(
                "automation definition command requires only the typed definition and the "
                "exact Active identity"
            )
        expected_revision_id = document["expectedRevisionId"]
        if not isinstance(expected_revision_id, str) or not expected_revision_id.strip():
            raise ValueError("expectedRevisionId must be a non-empty string")
        expected_digest = document["expectedDigest"]
        if not isinstance(expected_digest, str) or not expected_digest.strip():
            raise ValueError("expectedDigest must be a non-empty string")
        expected_version = document["expectedVersion"]
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise ValueError("expectedVersion must be an integer")
        value = document.get("object") if object else None
        if object and not isinstance(value, dict):
            raise ValueError("automation definition command requires a typed definition")
        if object and set(value).difference(AUTOMATION_DEFINITION_FORM_FIELDS):
            raise ValueError("automation definition command contains an unsupported field")
        if object and object_id is not None:
            submitted = value.get("id")
            if submitted is not None and submitted != object_id:
                raise AutomationDefinitionSaveError(
                    "automation_definition_id_immutable",
                    "the definition ID is immutable; an edit may only address the definition "
                    "it opened",
                    status=400,
                    definition_id=object_id,
                    stage="compose",
                    durable_state="active_unchanged",
                    side_effects="none",
                    next_action="keep the definition ID and correct the editable fields instead",
                )
        return (value if object else None), (
            expected_revision_id,
            expected_version,
            expected_digest,
        )

    def _automation_definition_publish(
        self,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
        *,
        object_id: str | None,
        value: dict | None,
        authority: tuple[str, int, str],
        action: str,
        reason: str | None = None,
    ):
        """Publish one exact focused successor and echo its durable truth."""

        prepared: list[_ApiRuntimeBinding] = []
        before_ids: set[str] = set()
        if action == "copy":
            # A copy allocates its new identity inside the application service, so
            # the published successor is diffed against the observed Active.
            active_before = self._configuration_service.active()
            if active_before is not None:
                before_ids = {
                    str(item.get("id"))
                    for item in self._configuration_objects._automation_definition_objects(
                        active_before.document
                    )
                }
        with self._runtime_binding_lock:
            self._refresh_configuration_binding_locked()
            try:
                if action == "remove":
                    revision = self._automation_workspace.remove_object(
                        str(object_id),
                        actor=principal.principal_id,
                        expected_revision_id=authority[0],
                        expected_version=authority[1],
                        expected_digest=authority[2],
                        before_publish=lambda successor: prepared.append(
                            self._prepare_automation_binding_for_revision(successor)
                        ),
                        reason=reason,
                    )
                elif action in {"enable", "disable"}:
                    revision = self._automation_workspace.set_enabled(
                        str(object_id),
                        enabled=action == "enable",
                        actor=principal.principal_id,
                        expected_revision_id=authority[0],
                        expected_version=authority[1],
                        expected_digest=authority[2],
                        before_publish=lambda successor: prepared.append(
                            self._prepare_automation_binding_for_revision(successor)
                        ),
                    )
                elif action == "copy":
                    revision = self._automation_workspace.copy_object(
                        str(object_id),
                        actor=principal.principal_id,
                        expected_revision_id=authority[0],
                        expected_version=authority[1],
                        expected_digest=authority[2],
                        before_publish=lambda successor: prepared.append(
                            self._prepare_automation_binding_for_revision(successor)
                        ),
                    )
                else:
                    assert value is not None
                    revision = self._automation_workspace.save_object(
                        value,
                        actor=principal.principal_id,
                        expected_revision_id=authority[0],
                        expected_version=authority[1],
                        expected_digest=authority[2],
                        object_id=object_id,
                        before_publish=lambda successor: prepared.append(
                            self._prepare_automation_binding_for_revision(successor)
                        ),
                    )
            except (ConfigurationActivationConflict, ConfigurationVersionConflict):
                # The repository fences concurrency authoritatively: consume the
                # winning Active before returning the stale/conflict result.
                self._refresh_configuration_binding_locked()
                raise
            if len(prepared) != 1:
                raise AutomationDefinitionSaveError(
                    "automation_definition_runtime_failed",
                    "the successor runtime binding was not prepared; the previous Active "
                    "remains in use",
                    status=503,
                    definition_id=object_id,
                    stage="activate",
                    durable_state="active_preserved",
                    next_action="refresh the current Active configuration and retry",
                )
            self._publish_runtime_binding(prepared[0])

        subject_id = object_id
        if subject_id is None and isinstance(value, dict):
            candidate_id = value.get("id")
            if isinstance(candidate_id, str):
                subject_id = candidate_id
        if action == "copy":
            # A copy allocates its new identity inside the application service, so
            # resolve it as the definition the publication added.
            published_ids = [
                str(item.get("id"))
                for item in self._configuration_objects._automation_definition_objects(
                    revision.document
                )
            ]
            added = [item for item in published_ids if item not in before_ids]
            subject_id = added[0] if len(added) == 1 else None
        return self._automation_definition_publish_response(
            start_response, revision, subject_id, action=action
        )

    def _automation_definition_publish_response(
        self,
        start_response: Callable,
        revision,
        subject_id: str | None,
        *,
        action: str,
    ):
        """One bounded publication document so the page can refresh from truth."""

        published = self._configuration_objects._automation_definition_objects(revision.document)
        item = next(
            (value for value in published if str(value.get("id")) == str(subject_id)),
            None,
        )
        if action != "remove" and item is None:
            # Publication succeeded but the intended definition is absent from the
            # new Active: that is a truth the operator must see, never a silent
            # success and never an automatic replay.
            raise AutomationDefinitionSaveError(
                "automation_definition_runtime_failed",
                "the successor was published but does not contain the intended definition; "
                "verify the current Active Automation inventory",
                status=503,
                definition_id=subject_id,
                stage="activate",
                durable_state="successor_published",
                side_effects="configuration_only",
                retry_safe=False,
                next_action="refresh the Active Automation inventory and verify the definitions",
            )
        if action == "remove" and item is not None:
            raise AutomationDefinitionSaveError(
                "automation_definition_runtime_failed",
                "the successor was published but still contains the definition; verify current "
                "Active",
                status=503,
                definition_id=subject_id,
                stage="activate",
                durable_state="successor_published",
                side_effects="configuration_only",
                retry_safe=False,
                next_action="refresh the Active Automation inventory and verify the definitions",
            )
        return self._response(
            start_response,
            200,
            {
                "action": action,
                "definition": item,
                "removed": {"id": subject_id} if action == "remove" else None,
                # The next command fences on the exact successor identity, so the
                # published revision's digest is part of this readback document.
                "active": {
                    "revisionId": revision.revision_id,
                    "version": revision.version,
                    "revisionSequence": revision.revision_sequence or revision.version,
                    "status": revision.status.value,
                    "digest": revision.digest,
                },
                "configuration": {
                    "authority": "MANAGED",
                    "revisionId": revision.revision_id,
                    "version": revision.version,
                    "digest": revision.digest,
                },
                "sideEffects": "configuration_only",
                "nextAction": (
                    "refresh the Active Automation inventory; the published successor is the "
                    "configuration runtime consumes"
                ),
            },
        )

    def _prepare_automation_binding_for_revision(self, revision):
        """Bind the Automation successor to runtime, or fail with its own code."""

        try:
            return self._prepare_runtime_binding_for_revision(revision)
        except ResourceLibrarySaveError as error:
            if error.code != "resource_library_runtime_failed":
                raise
            raise AutomationDefinitionSaveError(
                "automation_definition_runtime_failed",
                str(error),
                status=error.status,
                revision_id=error.revision_id,
                durable_state=error.durable_state,
                side_effects=error.side_effects,
                retry_safe=error.retry_safe,
                next_action=error.next_action,
            ) from error

    #: Bounded upper bound of one Automation inventory read.  The managed
    #: configuration document is itself bounded, so this only protects the read
    #: from a corrupt/unduly large section: it never truncates a supported page.
    _AUTOMATION_INVENTORY_CAP = 10_000

    @classmethod
    def _automation_definitions_query(cls, environ: dict, principal_id: str) -> dict[str, object]:
        """Submitted Automation inventory filters plus their principal-bound cursor.

        The inventory is a bounded, server-side query over **every** authorized
        Active and Draft-only definition: search, enablement/source filters,
        a stable total ordering and a page cursor that is bound to the exact
        filter state and reading principal.  A cursor minted for one filter
        state or principal is therefore refused instead of silently returning a
        different population.
        """

        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference(cls._AUTOMATION_DEFINITIONS_QUERY_FIELDS) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError(
                "automation definitions query accepts limit, cursor, q, enabled, library, "
                "sort, direction, and state once"
            )
        limit = cls._parse_bounded_limit(values.get("limit", ["20"])[0], "automation definition")
        raw_search = values.get("q", [""])[0].strip()
        if len(raw_search) > 128:
            raise ValueError("automation definition search text is too long")
        search = raw_search or None
        raw_enabled = values.get("enabled", [""])[0]
        if raw_enabled in {"", "all"}:
            enabled = None
        elif raw_enabled in {"true", "yes"}:
            enabled = True
        elif raw_enabled in {"false", "no"}:
            enabled = False
        else:
            raise ValueError("automation definition enabled filter is invalid")
        raw_library = values.get("library", [""])[0]
        library = None if raw_library in {"", "all"} else raw_library
        if library is not None and not _AUTOMATION_DEFINITION_FILTER.fullmatch(library):
            raise ValueError("automation definition library filter is invalid")
        raw_state = values.get("state", [""])[0]
        if raw_state in {"", "all"}:
            state = None
        elif raw_state in {"active", "draft-only"}:
            state = raw_state
        else:
            raise ValueError("automation definition state filter is invalid")
        sort = values.get("sort", ["name"])[0]
        if sort not in cls._AUTOMATION_DEFINITION_SORTS:
            raise ValueError("automation definition sort is invalid")
        raw_direction = values.get("direction", [""])[0]
        if raw_direction in {"", "auto"}:
            # The default order visits the most operationally relevant rows
            # first for schedule/result orderings and alphabetical otherwise.
            direction = "desc" if sort in {"nextRun", "latest"} else "asc"
        elif raw_direction in {"asc", "desc"}:
            direction = raw_direction
        else:
            raise ValueError("automation definition direction is invalid")
        scope = ";".join(
            (
                f"principal={principal_id}",
                "kind=automation-definitions",
                f"q={search or ''}",
                f"enabled={'all' if enabled is None else str(enabled).lower()}",
                f"library={library or 'all'}",
                f"state={state or 'all'}",
                f"sort={sort}",
                f"direction={direction}",
            )
        )
        raw_cursor = values.get("cursor", [""])[0]
        cursor = (
            decode_directional_cursor(raw_cursor, "automation_definitions", expected_scope=scope)
            if raw_cursor
            else None
        )
        return {
            "limit": limit,
            "search": search,
            "enabled": enabled,
            "library": library,
            "state": state,
            "sort": sort,
            "direction": direction,
            "cursor": cursor,
            "scope": scope,
        }

    @staticmethod
    def _automation_inventory_sort_key(document: dict, sort: str, latest: dict | None = None):
        """One stable, total ordering key over a projected definition document.

        ``latest`` is the definition's authoritative latest *original admitted*
        run (manual or scheduled) — the same value the row publishes — so the
        ``最近结果`` ordering sorts by the actual latest processing outcome. A
        manual-only history is therefore ordered by its real admission instead
        of by an empty scheduled occurrence, and a never-run or unreadable row
        sorts by the empty key instead of borrowing an unrelated diagnostic.
        The definition identity is the deterministic tie in every ordering.
        """

        body = document
        occurrence = document.get("occurrenceState") or {}
        if sort == "enabled":
            return (1 if body.get("enabled") is True else 0, str(body.get("id", "")))
        if sort == "nextRun":
            return (str(occurrence.get("nextRunAt") or ""), str(body.get("id", "")))
        if sort == "latest":
            admitted_at = ""
            if isinstance(latest, dict) and latest.get("unavailable") is not True:
                value = latest.get("admittedAt")
                if isinstance(value, str):
                    admitted_at = value
            return (admitted_at, str(body.get("id", "")))
        if sort == "limit":
            return (int(body.get("itemLimit") or 0), str(body.get("id", "")))
        return (str(body.get("name", "")).casefold(), str(body.get("id", "")))

    def _automation_definitions_operator_page(
        self, environ: dict, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        query = self._automation_definitions_query(environ, principal.principal_id)
        metrics = self._automation_metrics_document()
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
                    "metrics": {
                        **metrics,
                        "inventory": self._automation_inventory_counts([]),
                    },
                    "inventoryCounts": self._automation_inventory_counts([]),
                    "latestAdmittedRuns": {},
                    "query": self._automation_inventory_query_echo(query),
                    "itemsTruncatedByCap": False,
                    "previous_cursor": None,
                    "next_cursor": None,
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
        active_page = all_items
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
                draft_only.append((draft, candidate))
        projected = self._automation_occurrences.project_definitions(
            active_page,
            configuration=active.summary(),
            include_grants=False,
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
        # The complete authorized inventory is the filter/search/sort basis; the
        # bounded page below is only a window over it, so no definition is
        # hidden behind a hidden prefix and every authorized Draft-only
        # correction stays reachable.
        capped = len(items) > self._AUTOMATION_INVENTORY_CAP
        if capped:
            items = items[: self._AUTOMATION_INVENTORY_CAP]
        # The full-population inventory aggregates are computed from the complete
        # authorized definition population the backend holds, *before* the
        # submitted filters and the page window.  A filtered or paged read
        # therefore never changes the cards, and a Draft-only correction entry is
        # counted separately instead of inflating the published/enabled counts.
        inventory_counts = self._automation_inventory_counts(items)
        # The latest processing outcome/time is the newest *original admitted* run
        # per definition, whether scheduled or manual, so a manual-only history is
        # never hidden behind an empty scheduled-occurrence projection.
        latest_runs = self._automation_latest_runs(items)
        filtered = [item for item in items if self._automation_definition_matches(item, query)]
        ordered = sorted(
            filtered,
            key=lambda item: self._automation_inventory_sort_key(
                item, query["sort"], latest_runs.get(str(item.get("id", "")))
            ),
            reverse=query["direction"] == "desc",
        )
        total = len(ordered)
        cursor = query["cursor"]
        page, has_previous, has_next = self._automation_inventory_window(
            ordered, query["limit"], cursor
        )
        scope = query["scope"]
        manage = ApiPermission.MANAGE_CONFIGURATION in principal.permissions
        return self._response(
            start_response,
            200,
            {
                "activeConfiguration": self._automation_active_configuration(active),
                "items": page,
                "total": total,
                "truncated": has_next or capped,
                "metrics": {**metrics, "inventory": inventory_counts},
                "inventoryCounts": inventory_counts,
                "latestAdmittedRuns": latest_runs,
                "query": self._automation_inventory_query_echo(query),
                "itemsTruncatedByCap": capped,
                "previous_cursor": self._automation_inventory_cursor(
                    page, has_previous, CursorDirection.PREVIOUS, scope, query["sort"]
                ),
                "next_cursor": self._automation_inventory_cursor(
                    page, has_next, CursorDirection.NEXT, scope, query["sort"]
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

    @staticmethod
    def _automation_inventory_counts(items: list[dict]) -> dict[str, object]:
        """Full-population definition aggregates, independent of any filter.

        ``published`` counts only definitions that exist in the exact current
        Active configuration; ``enabled`` counts only published definitions whose
        schedule is enabled; ``draftOnly`` counts correction entries that exist
        solely inside an open Draft.  A Draft-only row is never counted as
        published or enabled, and none of these numbers is derived from a page.
        """

        published = 0
        enabled = 0
        draft_only = 0
        for item in items:
            state = item.get("definitionState")
            if state == "draft-only":
                draft_only += 1
                continue
            published += 1
            document = item.get("document")
            body = document if isinstance(document, dict) else item
            if body.get("enabled") is True:
                enabled += 1
        return {
            "published": published,
            "enabled": enabled,
            "draftOnly": draft_only,
            "total": published + draft_only,
            "basis": "exact_current_active_and_open_drafts",
            "scope": "full_authorized_population",
        }

    def _automation_latest_runs(self, items: list[dict]) -> dict[str, dict[str, object]]:
        """Latest original admitted run per definition, from one durable read.

        The durable read returns the newest *original admitted* run per
        definition whether the Scheduler emitted it or the operator deliberately
        started it once, so a manual-only history reports its real latest
        result.  A successful read that simply holds no run for a definition is
        a legitimate empty history ("no execution yet"), which is a different
        fact from an unreadable history; only a failed/unavailable read is
        published as ``unavailable``.  No scheduled-occurrence diagnostic is
        merged in, so a blocked/disabled emission that never became an admitted
        run can never masquerade as a processing result.
        """

        reader = getattr(self._repository, "automation_latest_admitted_runs", None)
        admitted: dict[str, dict[str, object]] | None = None
        if callable(reader):
            try:
                value = reader()
            except Exception:
                # A failed read stays explicitly unavailable per definition; it
                # is never published as an empty ("no execution yet") history.
                admitted = None
            else:
                admitted = value if isinstance(value, dict) else None
        latest: dict[str, dict[str, object]] = {}
        for item in items:
            definition_id = str(item.get("id", ""))
            if not definition_id:
                continue
            run = admitted.get(definition_id) if admitted is not None else None
            if isinstance(run, dict) and run:
                latest[definition_id] = dict(run)
                continue
            if admitted is None:
                latest[definition_id] = {
                    "definitionId": definition_id,
                    "unavailable": True,
                    "nextAction": (
                        "the durable admitted-run history could not be read; refresh "
                        "to re-read this definition's latest result"
                    ),
                }
        return latest

    @staticmethod
    def _automation_definition_matches(document: dict, query: dict) -> bool:
        """Whether one projected definition document satisfies the submitted filters.

        The predicate is the exact server-side filter basis: the same fields the
        page renders (name, id, source library, scope, schedule text) form the
        search text, and enablement/source/state are the published document
        values.  A Draft-only definition is never matched by an ``active``
        state filter and never contributes to published/enabled counts.
        """

        body = document
        enabled = query["enabled"]
        if enabled is not None and (body.get("enabled") is True) != enabled:
            return False
        library = query["library"]
        if library is not None and body.get("resourceLibraryId") != library:
            return False
        state = query["state"]
        if state is not None and document.get("definitionState") != state:
            return False
        search = query["search"]
        if search is not None:
            haystack = " ".join(
                str(value)
                for value in (
                    body.get("name"),
                    body.get("id"),
                    body.get("resourceLibraryId"),
                    body.get("sourceScope"),
                    body.get("cron"),
                    body.get("timezone"),
                )
                if value is not None
            ).casefold()
            if search.casefold() not in haystack:
                return False
        return True

    #: The documentary cursor timestamp for the id-only Automation inventory.
    #: Definitions carry no admission time, so the durable boundary is the
    #: definition identity itself; the field satisfies the shared directional
    #: cursor format without claiming a timestamp it does not have.
    _AUTOMATION_INVENTORY_CURSOR_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)

    def _automation_inventory_window(self, ordered: list, limit: int, cursor):
        """One page window over the ordered inventory with honest neighbours.

        The cursor names the exact boundary definition it was minted from, so a
        page boundary never shifts because another definition was published:
        the window starts strictly after (or before) that durable identity in
        the freshly ordered population.  A boundary identity that no longer
        exists in the submitted population is reported as a stale cursor for a
        bounded refresh instead of silently returning a different page.
        """

        if cursor is None:
            page = ordered[:limit]
            return page, False, len(ordered) > limit
        ids = [str(item.get("id", "")) for item in ordered]
        if cursor.record_id not in ids:
            raise _AutomationInventoryCursorStale(
                "the definition this page cursor was minted from is no longer in the "
                "submitted population"
            )
        index = ids.index(cursor.record_id)
        if cursor.direction is CursorDirection.PREVIOUS:
            end = index
            start = max(0, end - limit)
            return ordered[start:end], start > 0, bool(ordered[end:])
        start = index + 1
        end = start + limit
        return ordered[start:end], True, len(ordered) > end

    def _automation_inventory_cursor(
        self, page: list, available: bool, direction: CursorDirection, scope: str, sort: str
    ) -> str | None:
        if not available or not page:
            return None
        record = page[0] if direction is CursorDirection.PREVIOUS else page[-1]
        identity = str(record.get("id", ""))
        if not identity:
            return None
        return encode_cursor(
            "automation_definitions",
            self._AUTOMATION_INVENTORY_CURSOR_EPOCH,
            identity,
            direction,
            scope=scope,
        )

    @staticmethod
    def _automation_inventory_query_echo(query: dict) -> dict[str, object]:
        """The exact submitted read basis, echoed for a rebuildable refresh."""

        return {
            "q": query["search"],
            "enabled": query["enabled"],
            "library": query["library"],
            "state": query["state"],
            "sort": query["sort"],
            "direction": query["direction"],
            "limit": query["limit"],
            "scope": "full_authorized_population",
        }

    def _automation_definition_operator_detail(
        self, definition_id: str, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        resolution = self._automation_definition_resolution(definition_id, start_response)
        if not isinstance(resolution, tuple):
            return resolution
        active, raw, definition, draft, in_active, historical = resolution
        projected = self._automation_occurrences.project_definition(
            raw,
            configuration=active.summary(),
            _grant=None,
        )
        operator = self._automation_definition_operator_document(
            projected,
            principal=principal,
            active=active,
            draft=draft,
            in_active=in_active,
            historical=historical,
        )
        return self._response(
            start_response,
            200,
            {
                "definition": operator,
                "activeConfiguration": self._automation_active_configuration(active),
            },
        )

    def _automation_definition_operator_draft(
        self, definition_id: str, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        resolution = self._automation_definition_resolution(definition_id, start_response)
        if not isinstance(resolution, tuple):
            return resolution
        active, _raw, _definition, draft, _in_active, _historical = resolution
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
        active, _raw, _definition, _draft, _in_active, historical = resolution
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
        items = [
            self._automation_occurrence_operator_document(item)
            for item in self._automation_occurrences.project_occurrences(page)
        ]
        # Definition-bound Run once admissions are durable *manual* runs of this
        # same definition.  They are published in the same history next to the
        # scheduled occurrences, distinguished by their explicit trigger, and
        # they are never counted as scheduled occurrences.
        manual_runs = self._automation_run_once_history(definition_id)
        return self._response(
            start_response,
            200,
            {
                "definitionId": definition_id,
                "historicalState": "removed" if historical else None,
                "activeConfiguration": self._automation_active_configuration(active),
                "items": items,
                "manualRuns": manual_runs,
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

    def _automation_run_once_history(self, definition_id: str) -> list[dict[str, object]]:
        """Bounded durable manual Run once entries for one definition's history.

        Each entry is the *actual* admitted manual run, read from its durable
        definition origin.  It is distinguished from a scheduled occurrence by
        its explicit ``manual`` trigger and it never claims a schedule
        occurrence, so the definition's history counts each run once.
        """

        service = getattr(self, "_automation_run_once", None)
        reader = getattr(self._repository, "list_definition_run_once_discoveries", None)
        if service is None or not callable(reader):
            return []
        try:
            values = reader(definition_id, limit=50)
        except Exception:
            return []
        jobs_reader = getattr(self._repository, "list_automation_run_once_jobs", None)
        if callable(jobs_reader):
            values = (*jobs_reader(definition_id=definition_id, limit=50), *values)
        items = []
        for value in values:
            document = service.document(value)
            items.append(
                {
                    "runId": document["discoveryId"],
                    "status": document["status"],
                    "taskId": document.get("taskId"),
                    "kind": document.get("executionKind", "analysis"),
                }
            )
        return items[:50]

    # ------------------------------------------------------------------
    # V2 Rules workspace read projection (bounded, secret-free)

    _RULE_INVENTORY_FAMILY_ORDER = (
        "typeBindings",
        "recognitionTypes",
        "recognitionRules",
        "metadataPolicies",
        "namingPolicies",
        "classificationPolicies",
        "organizePolicies",
    )
    _RULE_INVENTORY_FAMILIES = frozenset(_RULE_INVENTORY_FAMILY_ORDER)

    def _rules_operations_projection(
        self,
        parts: list[str],
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """One authenticated surface for the V2 rules workspace reads and Save.

        The inventory read keeps its existing GET-only contract; the typed object
        commands reuse the same application service, permissions, validation, audit
        and concurrency boundaries as `/api/v1/configuration/*`, V1, the CLI and the
        runtime.  Nothing here creates a scan, Task, Job, schedule occurrence,
        notification, Provider call or Storage mutation.
        """

        if parts[:5] == ["api", "v1", "operations", "rules", "inventory"]:
            if parts != ["api", "v1", "operations", "rules", "inventory"]:
                return self._error(start_response, 404, "not_found", "route was not found")
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require(principal, ApiPermission.READ)
            return self._rules_inventory_operator_page(environ, start_response, principal)
        if self._rules_workspace is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        if parts == ["api", "v1", "operations", "rules", "form-authority"]:
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require_empty_query(environ, "rules form authority")
            self._require(principal, ApiPermission.READ)
            return self._rules_document(
                start_response, lambda: self._rules_workspace.form_authority()
            )
        if len(parts) == 6 and parts[4] == "previews" and method == "POST":
            return self._rules_preview_command(parts, environ, start_response, principal)
        if len(parts) == 6 and parts[4] == "analysis" and method == "POST":
            return self._rules_analysis_command(parts, environ, start_response, principal)
        if parts == ["api", "v1", "operations", "rules", "complete-flow"] and method == "POST":
            return self._rules_complete_flow_command(environ, start_response, principal)
        if len(parts) >= 6 and parts[4] == "objects" and parts[5] in RULE_WORKSPACE_FAMILIES:
            return self._rules_object_command(parts, method, environ, start_response, principal)
        if len(parts) >= 5 and parts[4] == "objects":
            # A typed family the workspace does not author (recognition rules and
            # type bindings stay a later in-Slice unit, and any other configuration
            # kind keeps its existing managed surface).
            return self._error(
                start_response,
                404,
                "not_found",
                "route was not found",
                details={
                    "objectKind": parts[5] if len(parts) > 5 else None,
                    "durableState": "active_unchanged",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "choose one of the typed rule families this workspace edits: "
                        + ", ".join(RULE_WORKSPACE_FAMILIES)
                    ),
                },
            )
        return self._error(start_response, 404, "not_found", "route was not found")

    def _rules_preview_command(
        self,
        parts: list[str],
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """V2 typed, exact-revision preview surface.

        The command envelope is deliberately strict. Preview requests carry the
        inspected revision identity, while the application service owns all
        parsing, provider and policy semantics. No route here creates work or
        grants execution authority.
        """
        self._require_empty_query(environ, "rules preview")
        self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
        kind = parts[5]
        allowed = {
            "strategy": {
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
                "candidate",
                "resourceLibraryId",
                "syntheticPath",
                "liveMetadata",
            },
            "metadata": {
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
                "candidate",
                "policyId",
                "resourceLibraryId",
                "syntheticPath",
                "liveMetadata",
            },
            "naming": {
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
                "candidate",
                "policySelection",
                "sample",
            },
            "classification": {
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
                "candidate",
                "policySelection",
                "sample",
            },
            "organize": {
                "expectedRevisionId",
                "expectedVersion",
                "expectedDigest",
                "candidate",
                "recognitionType",
                "resourceLibraryId",
                "syntheticPath",
                "sample",
            },
        }
        if kind not in allowed:
            return self._error(start_response, 404, "not_found", "preview route was not found")
        document = self._document(environ)
        if set(document) != allowed[kind]:
            raise ValueError(f"rules {kind} preview contains unsupported or missing fields")
        revision_id = document["expectedRevisionId"]
        version = document["expectedVersion"]
        digest = document["expectedDigest"]
        if not isinstance(revision_id, str) or not revision_id.strip():
            raise ValueError("expectedRevisionId must be a non-empty string")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("expectedVersion must be a positive integer")
        if not isinstance(digest, str) or not digest.strip():
            raise ValueError("expectedDigest must be a non-empty string")
        candidate = document["candidate"]
        if not isinstance(candidate, dict) or set(candidate) != {"family", "objectId", "values"}:
            raise ValueError("preview candidate requires family, objectId, and values")
        if not isinstance(candidate["family"], str) or not isinstance(candidate["values"], dict):
            raise ValueError("preview candidate family and values are required")
        if candidate["objectId"] is not None and not isinstance(candidate["objectId"], str):
            raise ValueError("preview candidate objectId must be text or null")
        staged = self._rules_workspace.stage_preview_candidate(
            candidate["family"],
            candidate["values"],
            actor=principal.principal_id,
            expected_revision_id=revision_id,
            expected_version=version,
            expected_digest=digest,
            object_id=candidate["objectId"],
        )
        revision_id = staged.revision_id
        version = staged.version
        digest = staged.digest
        if kind in {"naming", "classification", "organize"} and not isinstance(
            document["sample"], dict
        ):
            raise ValueError("preview sample must be an object")
        policy_selection = None
        if kind in {"naming", "classification"}:
            policy_selection = document["policySelection"]
            if not isinstance(policy_selection, dict):
                raise ValueError("policySelection must be an object")
            mode = policy_selection.get("mode")
            if mode == "direct":
                if (
                    set(policy_selection) != {"mode", "policyId"}
                    or not isinstance(policy_selection.get("policyId"), str)
                    or not policy_selection["policyId"].strip()
                ):
                    raise ValueError("direct policySelection requires policyId")
            elif mode == "binding":
                if (
                    set(policy_selection) != {"mode", "recognitionType"}
                    or not isinstance(policy_selection.get("recognitionType"), str)
                    or not policy_selection["recognitionType"].strip()
                ):
                    raise ValueError("binding policySelection requires recognitionType")
            else:
                raise ValueError("policySelection mode must be direct or binding")
        if kind in {"strategy", "metadata", "organize"}:
            if (
                not isinstance(document["resourceLibraryId"], str)
                or not document["resourceLibraryId"].strip()
            ):
                raise ValueError("resourceLibraryId must be a non-empty string")
            if (
                not isinstance(document["syntheticPath"], str)
                or not document["syntheticPath"].strip()
            ):
                raise ValueError("syntheticPath must be a non-empty string")
            if kind != "organize" and not isinstance(document["liveMetadata"], bool):
                raise ValueError("liveMetadata must be a boolean")
        if kind == "metadata":
            if not isinstance(document["policyId"], str) or not document["policyId"].strip():
                raise ValueError("policyId must be a non-empty string")
            evidence = self._rules_workspace.preview_metadata(
                revision_id,
                expected_version=version,
                expected_digest=digest,
                actor=principal.principal_id,
                policy_id=document["policyId"],
                resource_library_id=document["resourceLibraryId"],
                synthetic_path=document["syntheticPath"],
                live_metadata=document["liveMetadata"],
            )
        elif kind == "strategy":
            evidence = self._rules_workspace.preview_strategy(
                revision_id,
                expected_version=version,
                expected_digest=digest,
                actor=principal.principal_id,
                resource_library_id=document["resourceLibraryId"],
                synthetic_path=document["syntheticPath"],
                live_metadata=document["liveMetadata"],
            )
        elif kind == "naming":
            assert isinstance(policy_selection, dict)
            if policy_selection["mode"] == "binding":
                evidence = self._rules_workspace.preview_naming_for_type(
                    revision_id,
                    expected_version=version,
                    expected_digest=digest,
                    actor=principal.principal_id,
                    recognition_type=policy_selection["recognitionType"],
                    sample=document["sample"],
                )
            else:
                evidence = self._rules_workspace.preview_naming(
                    revision_id,
                    expected_version=version,
                    expected_digest=digest,
                    actor=principal.principal_id,
                    policy_id=policy_selection["policyId"],
                    sample=document["sample"],
                )
        elif kind == "classification":
            assert isinstance(policy_selection, dict)
            if policy_selection["mode"] == "binding":
                evidence = self._rules_workspace.preview_classification_for_type(
                    revision_id,
                    expected_version=version,
                    expected_digest=digest,
                    actor=principal.principal_id,
                    recognition_type=policy_selection["recognitionType"],
                    sample=document["sample"],
                )
            else:
                evidence = self._rules_workspace.preview_classification(
                    revision_id,
                    expected_version=version,
                    expected_digest=digest,
                    actor=principal.principal_id,
                    policy_id=policy_selection["policyId"],
                    sample=document["sample"],
                )
        else:
            evidence = self._rules_workspace.explain_organize(
                revision_id,
                expected_version=version,
                expected_digest=digest,
                actor=principal.principal_id,
                recognition_type=document["recognitionType"],
                resource_library_id=document["resourceLibraryId"],
                synthetic_path=document["syntheticPath"],
                sample=document["sample"],
            )
        response_document = evidence if isinstance(evidence, dict) else evidence.document()
        response_document["candidateState"] = "validated_non_active"
        if kind in {"strategy", "metadata"} and isinstance(response_document.get("result"), dict):
            response_document["result"]["source"] = {
                "resourceLibraryId": document["resourceLibraryId"],
                "syntheticPath": document["syntheticPath"],
            }
        return self._response(start_response, 200, response_document)

    def _rules_analysis_command(
        self,
        parts: list[str],
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """One explicit object-scoped local test of the exact submitted candidate.

        The submitted unsaved object is staged as one non-Active candidate from one
        exact captured Active identity, then analysed by its own family boundary.
        The route creates no executable work, changes no Active revision, mutates no
        Storage and never calls a Provider unless the operator explicitly requested
        the family's live Metadata test.
        """

        self._require_empty_query(environ, "rules object analysis")
        self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
        if self._rules_analysis is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        family = parts[5]
        if family not in RULE_WORKSPACE_FAMILIES:
            return self._error(start_response, 404, "not_found", "preview route was not found")
        allowed = {
            "expectedRevisionId",
            "expectedVersion",
            "expectedDigest",
            "candidate",
            "sample",
            "liveMetadata",
        }
        document = self._document(environ)
        if set(document) != allowed:
            raise ValueError("rules object analysis contains unsupported or missing fields")
        revision_id = document["expectedRevisionId"]
        version = document["expectedVersion"]
        digest = document["expectedDigest"]
        if not isinstance(revision_id, str) or not revision_id.strip():
            raise ValueError("expectedRevisionId must be a non-empty string")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("expectedVersion must be a positive integer")
        if not isinstance(digest, str) or not digest.strip():
            raise ValueError("expectedDigest must be a non-empty string")
        candidate = document["candidate"]
        if not isinstance(candidate, dict) or set(candidate) != {"family", "objectId", "values"}:
            raise ValueError("analysis candidate requires family, objectId, and values")
        if candidate["family"] != family:
            raise ValueError("analysis candidate family must match the requested family")
        if not isinstance(candidate["values"], dict):
            raise ValueError("analysis candidate values are required")
        if candidate["objectId"] is not None and not isinstance(candidate["objectId"], str):
            raise ValueError("analysis candidate objectId must be text or null")
        sample = document["sample"]
        if sample is not None and not isinstance(sample, dict):
            raise ValueError("analysis sample must be an object or null")
        live_metadata = document["liveMetadata"]
        if not isinstance(live_metadata, bool):
            raise ValueError("liveMetadata must be a boolean")
        # A live Provider test is the only analysis that may construct a Provider,
        # and only for the MetadataPolicy family.
        if live_metadata and family != "metadataPolicies":
            raise ValueError("liveMetadata is only available for the MetadataPolicy test")
        staged = self._rules_workspace.stage_analysis_candidate(
            family,
            candidate["values"],
            actor=principal.principal_id,
            expected_revision_id=revision_id,
            expected_version=version,
            expected_digest=digest,
            object_id=candidate["objectId"],
        )
        result = self._rules_analysis.analyze(
            family,
            revision_id=staged.revision_id,
            object_id=candidate["objectId"],
            sample=sample,
            live_metadata=live_metadata,
        )
        response_document = result.document()
        response_document["revisionId"] = staged.revision_id
        response_document["revisionVersion"] = staged.version
        response_document["revisionDigest"] = staged.digest
        response_document["testedAt"] = datetime.now(UTC).isoformat()
        response_document["testedObject"] = {
            "family": family,
            "objectId": candidate["objectId"],
        }
        return self._response(start_response, 200, response_document)

    def _rules_complete_flow_command(
        self,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """The separately labelled complete-flow check from Rules Overview.

        It reuses the complete Python chain and reports truthful missing-stage
        blockers. It never grants execution authority, starts work or mutates
        media; a live Metadata identity stays separately explicit.
        """

        self._require_empty_query(environ, "rules complete flow")
        self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
        if self._rules_analysis is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        allowed = {
            "expectedRevisionId",
            "expectedVersion",
            "expectedDigest",
            "resourceLibraryId",
            "syntheticPath",
            "liveMetadata",
            "syntheticIdentity",
        }
        document = self._document(environ)
        if set(document) != allowed:
            raise ValueError("rules complete flow contains unsupported or missing fields")
        revision_id = document["expectedRevisionId"]
        version = document["expectedVersion"]
        digest = document["expectedDigest"]
        if not isinstance(revision_id, str) or not revision_id.strip():
            raise ValueError("expectedRevisionId must be a non-empty string")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("expectedVersion must be a positive integer")
        if not isinstance(digest, str) or not digest.strip():
            raise ValueError("expectedDigest must be a non-empty string")
        library_id = document["resourceLibraryId"]
        synthetic_path = document["syntheticPath"]
        if not isinstance(library_id, str) or not library_id.strip() or len(library_id) > 128:
            raise ValueError("resourceLibraryId must be a bounded non-empty string")
        if (
            not isinstance(synthetic_path, str)
            or not synthetic_path.strip()
            or len(synthetic_path) > 4096
            or "\x00" in synthetic_path
        ):
            raise ValueError("syntheticPath must be bounded, non-empty, and NUL-free")
        live_metadata = document["liveMetadata"]
        if not isinstance(live_metadata, bool):
            raise ValueError("liveMetadata must be a boolean")
        identity = document["syntheticIdentity"]
        if identity is not None and not isinstance(identity, dict):
            raise ValueError("syntheticIdentity must be an object or null")
        if identity is not None and live_metadata:
            raise ValueError("syntheticIdentity cannot be combined with liveMetadata")
        # The complete-flow entry deliberately analyses the *current Active*
        # configuration graph rather than a staged object candidate: it is the
        # combined processing check, not one object's local test.  It therefore
        # only verifies the observed Active identity and performs no publication.
        active = self._configuration_objects._managed.active()
        if active is None:
            return self._error(
                start_response,
                409,
                "no_active_configuration",
                "no Active configuration exists; complete-flow analysis is unavailable",
                details={
                    "durableState": "active_unchanged",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "publish an Active configuration, then run the complete-flow check"
                    ),
                },
            )
        observed_version = active.revision_sequence or active.version
        if (
            revision_id != active.revision_id
            or version != observed_version
            or digest != active.digest
        ):
            return self._error(
                start_response,
                409,
                "configuration_version_conflict",
                "complete-flow analysis requires the exact current Active; reload before checking",
                details={
                    "currentRevisionId": active.revision_id,
                    "currentVersion": observed_version,
                    "currentDigest": active.digest,
                    "durableState": "active_preserved",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": "reload the Active configuration, then explicitly rerun",
                },
            )
        result = self._rules_analysis.complete_flow(
            revision_id=active.revision_id,
            resource_library_id=library_id,
            synthetic_path=synthetic_path,
            live_metadata=live_metadata,
            synthetic_identity=identity,
        )
        response_document = result.document()
        response_document["revisionId"] = active.revision_id
        response_document["revisionVersion"] = observed_version
        response_document["revisionDigest"] = active.digest
        response_document["testedAt"] = datetime.now(UTC).isoformat()
        response_document["entry"] = "complete_flow_check"
        response_document["executionAuthorityGranted"] = "none"
        return self._response(start_response, 200, response_document)

    def _rules_object_command(
        self,
        parts: list[str],
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        """Typed object reads and the one explicit Save-and-activate command."""

        family = parts[5]
        if len(parts) == 6:
            if method != "POST":
                return self._error(
                    start_response, 405, "method_not_allowed", "POST required for a new object"
                )
            self._require_empty_query(environ, "rules object Save")
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
            document = self._document(environ)
            value, authority = self._rules_command_envelope(document, None)
            return self._rules_publish(
                start_response,
                principal,
                family=family,
                object_id=None,
                value=value,
                authority=authority,
            )
        if len(parts) == 7:
            object_id = parts[6]
            if method == "GET":
                self._require_empty_query(environ, "rules object projection")
                self._require(principal, ApiPermission.READ)
                return self._rules_document(
                    start_response,
                    lambda: self._rules_workspace.edit_projection(family, object_id),
                )
            if method == "PUT":
                self._require_empty_query(environ, "rules object edit")
                self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
                self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
                document = self._document(environ)
                value, authority = self._rules_command_envelope(document, object_id)
                return self._rules_publish(
                    start_response,
                    principal,
                    family=family,
                    object_id=object_id,
                    value=value,
                    authority=authority,
                )
            if method == "DELETE":
                self._require_empty_query(environ, "rules object removal")
                self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
                self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
                document = self._document(environ)
                authority = self._rules_command_envelope(document, object_id, object=False)[1]
                return self._rules_publish(
                    start_response,
                    principal,
                    family=family,
                    object_id=object_id,
                    value=None,
                    authority=authority,
                )
            return self._error(
                start_response,
                405,
                "method_not_allowed",
                "GET, PUT or DELETE required for one rules object",
            )
        if len(parts) == 8 and parts[7] in {"copy", "impact"}:
            if method != "GET":
                return self._error(
                    start_response, 405, "method_not_allowed", "GET required for a candidate read"
                )
            self._require_empty_query(
                environ,
                "rules object copy candidate" if parts[7] == "copy" else "rules object impact",
            )
            self._require(principal, ApiPermission.READ)
            produce = (
                self._rules_workspace.copy_projection
                if parts[7] == "copy"
                else self._rules_workspace.removal_impact
            )
            return self._rules_document(start_response, lambda: produce(family, parts[6]))
        if len(parts) == 9 and parts[7] == "state" and parts[8] in {"enable", "disable"}:
            if method != "POST":
                return self._error(
                    start_response, 405, "method_not_allowed", "POST required for a state change"
                )
            self._require_empty_query(environ, "rules object state change")
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            self._require(principal, ApiPermission.ACTIVATE_CONFIGURATION)
            document = self._document(environ)
            enabled = parts[8] == "enable"
            authority = self._rules_command_envelope(
                document, parts[6], object=False, enabled=enabled
            )[1]
            return self._rules_publish(
                start_response,
                principal,
                family=family,
                object_id=parts[6],
                value=None,
                authority=authority,
                state=enabled,
            )
        return self._error(start_response, 404, "not_found", "route was not found")

    def _rules_document(self, start_response: Callable, produce: Callable[[], dict]):
        try:
            return self._response(start_response, 200, produce())
        except LookupError as error:
            return self._error(
                start_response,
                404,
                "not_found",
                str(error),
                details={
                    "durableState": "active_unchanged",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "refresh the Active rules inventory and choose an existing object"
                    ),
                },
            )
        except RuntimeSnapshotUnavailable as error:
            return self._error(
                start_response,
                503,
                "configuration_unavailable",
                str(error),
                details={
                    "reason": error.reason,
                    "durableState": "no_active_configuration"
                    if error.reason == "active_missing"
                    else "managed_active_unavailable",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "complete first setup in Settings and activate a configuration, then "
                        "return to the rules workspace"
                        if error.reason == "active_missing"
                        else "repair or replace the unavailable Active configuration, then refresh"
                    ),
                },
            )

    @staticmethod
    def _rules_command_envelope(
        document: dict,
        object_id: str | None,
        *,
        object: bool = True,
        enabled: bool | None = None,
    ) -> tuple[dict | None, tuple[str, int, str]]:
        """Validate the bounded command envelope before it reaches the application.

        Exactly the advertised fields are accepted: the typed object for a Save, the
        boolean intent for a state change, and the observed Active identity for every
        command.  A missing or extra key is rejected rather than ignored, so a stale or
        partially-built browser request can never publish a different successor than
        the operator reviewed.
        """

        fields = {"expectedRevisionId", "expectedVersion", "expectedDigest"}
        if object:
            fields.add("object")
        if enabled is not None:
            fields.add("enabled")
        if set(document) != fields:
            raise ValueError(
                "rules object command requires only the typed command fields and the exact "
                "Active identity"
            )
        expected_revision_id = document["expectedRevisionId"]
        if not isinstance(expected_revision_id, str) or not expected_revision_id.strip():
            raise ValueError("expectedRevisionId must be a non-empty string")
        expected_digest = document["expectedDigest"]
        if not isinstance(expected_digest, str) or not expected_digest.strip():
            raise ValueError("expectedDigest must be a non-empty string")
        expected_version = document["expectedVersion"]
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise ValueError("expectedVersion must be an integer")
        if enabled is not None and document["enabled"] is not enabled:
            raise ValueError("rules state change does not match the requested verb")
        value = document.get("object") if object else None
        if object and not isinstance(value, dict):
            raise ValueError("rules object command requires a typed object")
        if object and object_id is not None and value.get("id") != object_id:
            raise RulesWorkspaceSaveError(
                "rules_id_immutable",
                "the object ID is immutable; an edit may only address the object it opened",
                status=400,
                object_id=object_id,
                stage="compose",
                durable_state="active_unchanged",
                side_effects="none",
                next_action="keep the object ID and correct the editable fields instead",
            )
        return (value if object else None), (
            expected_revision_id,
            expected_version,
            expected_digest,
        )

    def _rules_publish(
        self,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
        *,
        family: str,
        object_id: str | None,
        value: dict | None,
        authority: tuple[str, int, str],
        state: bool | None = None,
    ):
        prepared: list[_ApiRuntimeBinding] = []
        with self._runtime_binding_lock:
            # Pin the process to the save-time Active before any successor work so a
            # failed Save leaves a usable old binding and a competing winner can be
            # consumed explicitly below.
            self._refresh_configuration_binding_locked()
            try:
                if state is not None:
                    revision = self._rules_workspace.set_enabled(
                        family,
                        str(object_id),
                        enabled=state,
                        actor=principal.principal_id,
                        expected_revision_id=authority[0],
                        expected_version=authority[1],
                        expected_digest=authority[2],
                        before_publish=lambda successor: prepared.append(
                            self._prepare_rules_binding_for_revision(successor)
                        ),
                    )
                elif value is None:
                    revision = self._rules_workspace.remove_object(
                        family,
                        str(object_id),
                        actor=principal.principal_id,
                        expected_revision_id=authority[0],
                        expected_version=authority[1],
                        expected_digest=authority[2],
                        before_publish=lambda successor: prepared.append(
                            self._prepare_rules_binding_for_revision(successor)
                        ),
                    )
                else:
                    revision = self._rules_workspace.save_object(
                        family,
                        value,
                        actor=principal.principal_id,
                        expected_revision_id=authority[0],
                        expected_version=authority[1],
                        expected_digest=authority[2],
                        object_id=object_id,
                        before_publish=lambda successor: prepared.append(
                            self._prepare_rules_binding_for_revision(successor)
                        ),
                    )
            except (ConfigurationActivationConflict, ConfigurationVersionConflict):
                # The repository fences concurrency authoritatively: consume the
                # winning Active before returning the stale/conflict result.
                self._refresh_configuration_binding_locked()
                raise
            if len(prepared) != 1:
                raise RulesWorkspaceSaveError(
                    "rules_runtime_failed",
                    (
                        "the successor runtime binding was not prepared; the previous Active "
                        "remains in use"
                    ),
                    status=503,
                    object_kind=family,
                    object_id=object_id,
                    stage="activate",
                    durable_state="active_preserved",
                    next_action="refresh the current Active configuration and retry Save",
                )
            self._publish_runtime_binding(prepared[0])
        # A create carries its new identity in the typed object rather than in the
        # route, so the echoed subject is resolved from the published successor itself.
        subject_id = object_id
        if subject_id is None and isinstance(value, dict):
            candidate_id = value.get("id")
            if isinstance(candidate_id, str):
                subject_id = candidate_id
        return self._rules_save_response(
            start_response,
            revision,
            family,
            subject_id,
            action="state" if state is not None else ("remove" if value is None else "save"),
        )

    def _rules_save_response(
        self,
        start_response: Callable,
        revision,
        family: str,
        subject_id: str | None,
        *,
        action: str,
    ):
        """One bounded Save document so the page can refresh from the successor it published."""

        # The response projection resolves the published object through the
        # family's persisted section: the operator-facing `typeBindings` family
        # is stored under `recognitionTypePolicies`, so reading the family name
        # as a section would fail every successful binding Save.
        published = self._configuration_objects._canonical_objects(
            revision.document, rules_family_section(family)
        )
        item = next(
            (value for value in published if str(value.get("id")) == str(subject_id)),
            None,
        )
        if action != "remove" and item is None:
            # Publication succeeded but the intended object is absent from the new
            # Active: that is a truth the operator must see, never a silent success.
            raise RulesWorkspaceSaveError(
                "rules_runtime_failed",
                (
                    "the successor was published but does not contain the intended object; "
                    "verify the current Active rules inventory"
                ),
                status=503,
                object_kind=family,
                object_id=subject_id,
                stage="activate",
                durable_state="successor_published",
                side_effects="configuration_only",
                retry_safe=False,
                next_action="refresh the Active rules inventory and verify the current objects",
            )
        if action == "remove" and item is not None:
            raise RulesWorkspaceSaveError(
                "rules_runtime_failed",
                "the successor was published but still contains the object; verify current Active",
                status=503,
                object_kind=family,
                object_id=subject_id,
                stage="activate",
                durable_state="successor_published",
                side_effects="configuration_only",
                retry_safe=False,
                next_action="refresh the Active rules inventory and verify the current objects",
            )
        return self._response(
            start_response,
            200,
            {
                "family": family,
                "action": action,
                "object": item,
                "removed": {"id": subject_id} if action == "remove" else None,
                "active": revision.summary(),
                "configuration": {
                    "authority": "MANAGED",
                    "revisionId": revision.revision_id,
                    "version": revision.version,
                    "digest": revision.digest,
                },
                "sideEffects": "configuration_only",
                "nextAction": (
                    "refresh the Active rules inventory; the published successor is the "
                    "configuration runtime consumes"
                ),
            },
        )

    def _prepare_rules_binding_for_revision(self, revision):
        """Bind the rules successor to runtime, or fail with its own code."""

        try:
            return self._prepare_runtime_binding_for_revision(revision)
        except ResourceLibrarySaveError as error:
            if error.code != "resource_library_runtime_failed":
                raise
            raise RulesWorkspaceSaveError(
                "rules_runtime_failed",
                str(error),
                status=error.status,
                revision_id=error.revision_id,
                durable_state=error.durable_state,
                side_effects=error.side_effects,
                retry_safe=error.retry_safe,
                next_action=error.next_action,
            ) from error

    def _rules_inventory_operator_page(
        self, environ: dict, start_response: Callable, principal: ResolvedApiPrincipal
    ):
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(query).difference({"family", "q", "enabled"}) or any(
            len(values) != 1 for values in query.values()
        ):
            raise ValueError("Rules inventory query accepts family, q and enabled once")
        family = query.get("family", [None])[0] or None
        if family is not None and family not in self._RULE_INVENTORY_FAMILIES:
            raise ValueError("Rules inventory family is unsupported")
        search = query.get("q", [""])[0]
        if len(search) > 256 or "\0" in search:
            raise ValueError("Rules inventory search must be at most 256 characters")
        enabled_value = query.get("enabled", [None])[0]
        if enabled_value not in {None, "", "true", "false"}:
            raise ValueError("Rules inventory enabled filter must be true or false")
        enabled = None if enabled_value in {None, ""} else enabled_value == "true"
        if self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        try:
            document = self._configuration_objects.active_rules_workspace(
                family=family,
                query=search,
                enabled=enabled,
            )
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "Rules inventory is unavailable",
                details={
                    "durableState": "Active configuration remains unchanged",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": "inspect Settings and refresh after Active is available",
                },
            )
        return self._response(
            start_response,
            200,
            {
                **document,
                # The typed object commands reuse the existing managed-configuration
                # authority; this read only reports whether the connected principal may
                # attempt them, so the page never presents a Save it cannot complete and
                # never decides permissions in the browser.
                "canManage": {
                    ApiPermission.MANAGE_CONFIGURATION,
                    ApiPermission.ACTIVATE_CONFIGURATION,
                }.issubset(principal.permissions),
            },
        )

    # ------------------------------------------------------------------
    # V2 Storage management operations projections (bounded, secret-free)
    #
    # The read documents compose the exact immutable Active snapshot with the
    # existing bounded reference evidence and Storage check documents; the one
    # mutation here is the zero-mutation Connection/Read check bound to the
    # exact Active revision the operator inspected.  The browser submits only
    # the advertised revision identity and optimistic version, while the
    # configuration digest and every secret reference stay server-side.  No
    # route here scans recursively, calls a Metadata Provider, creates
    # Jobs/Tasks, mutates Storage or claims write capability from a read.

    def _storage_operations_projection(
        self,
        parts: list[str],
        method: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        if len(parts) == 3:
            return self._error(start_response, 404, "not_found", "route was not found")
        if parts[3] == "storage-management" and len(parts) == 5 and parts[4] == "inventory":
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require(principal, ApiPermission.READ)
            bounds = self._storage_inventory_query(environ)
            return self._storage_inventory_operator_page(start_response, principal, bounds)
        if parts[3] == "storage-management" and len(parts) == 6 and parts[4] == "storage":
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require_empty_query(environ, "storage management detail")
            self._require(principal, ApiPermission.READ)
            return self._storage_detail_operator_document(parts[5], start_response, principal)
        if (
            parts[3] == "storage-management"
            and len(parts) == 7
            and parts[4] == "storage"
            and parts[6] == "check"
        ):
            if method != "POST":
                return self._error(start_response, 405, "method_not_allowed", "POST required")
            self._require_empty_query(environ, "storage management read check")
            self._require(principal, ApiPermission.MANAGE_CONFIGURATION)
            if self._configuration_objects is None:
                return self._error(
                    start_response,
                    503,
                    "service_unavailable",
                    "managed configuration service is unavailable",
                )
            document = self._document(environ)
            if set(document) != {"expectedRevisionId", "expectedVersion"}:
                raise ValueError(
                    "Storage read check requires expectedRevisionId and expectedVersion"
                )
            expected_revision_id = document["expectedRevisionId"]
            if not isinstance(expected_revision_id, str) or not expected_revision_id.strip():
                raise ValueError("expectedRevisionId must be a non-empty string")
            expected_version = document["expectedVersion"]
            if isinstance(expected_version, bool) or not isinstance(expected_version, int):
                raise ValueError("expectedVersion must be an integer")
            return self._storage_check_operator_document(
                parts[5],
                expected_revision_id,
                expected_version,
                start_response,
                principal,
            )
        return self._error(start_response, 404, "not_found", "route was not found")

    def _prepare_storage_binding_for_revision(self, revision):
        """Bind the Storage Save successor to runtime, or fail with its own code.

        The shared runtime-binding preparation is authoritative; only the
        bounded failure identity differs, so a Storage Save runtime error
        reports `storage_runtime_failed` instead of borrowing the
        ResourceLibrary code family.
        """

        try:
            return self._prepare_runtime_binding_for_revision(revision)
        except ResourceLibrarySaveError as error:
            if error.code != "resource_library_runtime_failed":
                raise
            raise ResourceLibrarySaveError(
                "storage_runtime_failed",
                str(error),
                status=error.status,
                revision_id=error.revision_id,
                durable_state=error.durable_state,
                side_effects=error.side_effects,
                retry_safe=error.retry_safe,
                next_action=error.next_action,
            ) from error

    def _storage_save_response(
        self,
        start_response: Callable,
        revision,
        storage_id: str,
    ) -> list[bytes]:
        """One bounded Add/Edit success document for the Storage workspace.

        It echoes the persisted Storage form projection (provider settings and
        approved secret-reference names only — never a secret value), the new
        immutable Active identity and the configuration-only side effect, so
        the page can refresh its inventory from the exact successor it just
        published.
        """

        storage = next(
            item
            for item in self._configuration_objects._canonical_objects(
                revision.document, "storages"
            )
            if item.get("id") == storage_id
        )
        return self._response(
            start_response,
            200,
            {
                "storage": self._configuration_objects.storage_form_document(storage),
                "active": revision.summary(),
                "configuration": {
                    "authority": "MANAGED",
                    "revisionId": revision.revision_id,
                    "version": revision.version,
                    "digest": revision.digest,
                },
                "sideEffects": "configuration_only",
                "nextAction": (
                    "refresh the Active Storage inventory; the published successor is the "
                    "configuration runtime consumes"
                ),
            },
        )

    _STORAGE_INVENTORY_FAMILIES = ("local", "smb", "openlist", "s3", "other")

    @classmethod
    def _storage_inventory_query(cls, environ: dict) -> dict[str, object]:
        """Parse the bounded Storage inventory search/filter/paging query.

        Only the three advertised operator fields are accepted once each; an
        unsupported, repeated or oversized value is rejected instead of being
        silently ignored, so the Web can never believe it filtered a complete
        inventory when it did not.
        """

        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(query).difference({"q", "family", "limit", "after"}) or any(
            len(value) != 1 for value in query.values()
        ):
            raise ValueError("Storage inventory query accepts q, family, limit and after once")
        search = query.get("q", [""])[0]
        if len(search) > 256 or "\0" in search:
            raise ValueError("Storage inventory search must be at most 256 characters")
        family = query.get("family", [None])[0] or None
        if family is not None and family not in cls._STORAGE_INVENTORY_FAMILIES:
            raise ValueError("Storage inventory family is not a supported provider family")
        limit = cls._parse_bounded_limit(query.get("limit", ["100"])[0], "Storage inventory")
        after = query.get("after", [None])[0]
        if after is not None and (not after or len(after) > 64 or "\0" in after):
            raise ValueError("Storage inventory cursor must be a bounded Storage ID")
        return {"query": search, "family": family, "limit": limit, "after": after}

    def _storage_inventory_operator_page(
        self,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
        bounds: dict[str, object] | None = None,
    ) -> None:
        if self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        selection = bounds or {"query": "", "family": None, "limit": None, "after": None}
        try:
            inventory = self._configuration_objects.active_storage_management(
                query=str(selection.get("query") or ""),
                family=selection.get("family"),
                limit=selection.get("limit"),
                after=selection.get("after"),
            )
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        manage = {
            ApiPermission.MANAGE_CONFIGURATION,
            ApiPermission.ACTIVATE_CONFIGURATION,
        }.issubset(principal.permissions)
        if not inventory.get("available"):
            return self._response(
                start_response,
                200,
                {
                    **inventory,
                    "items": [],
                    "total": 0,
                    "matched": 0,
                    "truncated": False,
                    "returned": 0,
                    "hasMore": False,
                    "nextAfter": None,
                    "families": {},
                    "actions": {
                        "check": {
                            "available": False,
                            "reason": self._storage_unavailable_reason(inventory),
                            "method": "POST",
                            "path": None,
                            "sideEffects": "none",
                            "durableOutcome": None,
                            "nextAction": self._storage_unavailable_next_action(inventory),
                            "requiresConfirmation": False,
                        },
                    },
                    "canManage": manage,
                    "canStartSetup": (ApiPermission.MANAGE_CONFIGURATION in principal.permissions),
                },
            )
        return self._response(
            start_response,
            200,
            {
                **inventory,
                "canStartSetup": (ApiPermission.MANAGE_CONFIGURATION in principal.permissions),
                "actions": {
                    "check": {
                        "available": False,
                        "reason": (
                            "a read check binds to exactly one selected Storage; open its "
                            "detail to run it"
                        ),
                        "method": "POST",
                        "path": None,
                        "sideEffects": "none",
                        "durableOutcome": None,
                        "nextAction": "open one Storage detail, then run its read check",
                        "requiresConfirmation": False,
                    },
                },
                "canManage": manage,
            },
        )

    @staticmethod
    def _storage_unavailable_reason(inventory: dict) -> str:
        return {
            "no_active": "no managed Active configuration exists",
            "unavailable": "the managed Active configuration is unavailable",
            "malformed": "the managed Active configuration is unreadable",
        }.get(str(inventory.get("reason")), "the Storage inventory is unavailable")

    @staticmethod
    def _storage_unavailable_next_action(inventory: dict) -> str:
        reason = str(inventory.get("reason"))
        if reason == "no_active":
            return (
                "complete managed configuration setup, validate the Draft, and "
                "activate it; the setup journey remains the recovery path"
            )
        if reason == "malformed":
            return "inspect configuration status and stage an explicit recovery Draft"
        return "inspect configuration status and refresh after the authority is restored"

    def _storage_detail_operator_document(
        self, storage_id: str, start_response: Callable, principal: ResolvedApiPrincipal
    ) -> None:
        if self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        try:
            detail = self._configuration_objects.active_storage_detail(storage_id)
        except RuntimeSnapshotUnavailable as error:
            return self._error(
                start_response,
                503,
                "configuration_unavailable",
                str(error),
                details={
                    "durableState": "active_pointer_preserved",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "inspect configuration status and refresh after the authority is restored"
                    ),
                },
            )
        except LookupError as error:
            return self._error(start_response, 404, "not_found", str(error))
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        manage = ApiPermission.MANAGE_CONFIGURATION in principal.permissions
        storage = detail["storage"]
        active_identity = detail["activeConfiguration"]
        available = storage.get("enabled", True) is not False and active_identity is not None
        check_reason = None
        if not manage:
            check_reason = (
                "the connected API principal cannot run Storage checks "
                "(required permission: manage_configuration)"
            )
        elif not available:
            check_reason = "the selected Storage is disabled in the current Active configuration"
        document = {
            "storage": storage,
            "references": detail["references"],
            "activeConfiguration": active_identity,
            "actions": {
                "check": {
                    "available": manage and available,
                    "reason": check_reason,
                    "method": "POST",
                    "path": (
                        f"/api/v1/operations/storage-management/storage/{storage_id}/check"
                        if manage and available
                        else None
                    ),
                    "sideEffects": "none",
                    "durableOutcome": (
                        "bounded read-only check evidence is persisted for this exact "
                        "revision; no Storage content changes"
                    ),
                    "nextAction": (
                        "run the read-only check after reviewing the bounded configuration"
                        if manage and available
                        else (check_reason or "this check is unavailable")
                    ),
                    "requiresConfirmation": False,
                },
            },
            "writeCapabilityNote": (
                "a read check proves connection/read access only; write access is "
                "never tested by this diagnostic"
            ),
        }
        return self._response(start_response, 200, document)

    def _storage_check_operator_document(
        self,
        storage_id: str,
        expected_revision_id: str,
        expected_version: int,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ) -> None:
        if self._configuration_service is None or self._configuration_objects is None:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        active = self._configuration_service.active()
        if active is None:
            return self._error(
                start_response,
                503,
                "configuration_unavailable",
                "no managed Active configuration exists",
                details={
                    "durableState": "active_pointer_preserved",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "complete managed configuration setup before running a read check"
                    ),
                },
            )
        if (
            active.revision_id != expected_revision_id
            or (active.revision_sequence or active.version) != expected_version
        ):
            return self._error(
                start_response,
                409,
                "configuration_version_conflict",
                "the Active configuration changed since the inventory was read; "
                "refresh the inventory before retrying",
                details={
                    "durableState": "active_preserved",
                    "candidateState": "not_run",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "refresh the Storage inventory, reopen the detail, then run the check again"
                    ),
                },
            )
        try:
            self._configuration_objects.storage_check(
                active.revision_id,
                storage_id=storage_id,
                expected_version=active.revision_sequence or active.version,
                expected_digest=active.digest,
                actor=principal.principal_id,
            )
        except LookupError as error:
            return self._error(start_response, 404, "not_found", str(error))
        except RuntimeSnapshotUnavailable as error:
            return self._error(
                start_response,
                503,
                "configuration_unavailable",
                str(error),
                details={
                    "durableState": "active_pointer_preserved",
                    "sideEffects": "none",
                    "retrySafe": True,
                    "nextAction": (
                        "inspect configuration status and refresh after the authority is restored"
                    ),
                },
            )
        except Exception:
            return self._error(
                start_response,
                503,
                "service_unavailable",
                "managed configuration service is unavailable",
            )
        response = self._configuration_objects.storage_check_evidence(
            active.revision_id, storage_id
        )
        return self._response(start_response, 200, response or {})

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
            document["primaryCompleted"] = result.primary_completed
            document["attachmentResults"] = list(result.attachment_results)
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
            410: "Gone",
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
