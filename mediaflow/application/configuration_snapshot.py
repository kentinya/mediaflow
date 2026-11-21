from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.configuration_input import reject_retired_configuration_input
from mediaflow.domain.configuration_integrity import (
    MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
    canonical_document_digest,
)
from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationAuthority,
    ConfigurationChangeAudit,
    ConfigurationFirstDraftConflict,
    ConfigurationObjectKind,
    ConfigurationVersionConflict,
    ManagedConfigurationRepository,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
    bind_deployment_authority,
    portable_managed_configuration_document,
)
from mediaflow.domain.notification import (
    redact_webhook_urls,
    unsafe_webhook_url_items,
    webhook_url_items,
)
from mediaflow.infrastructure.runtime_configuration import (
    is_minimal_management_bootstrap,
    load_managed_runtime_configuration,
    load_minimal_management_bootstrap,
    load_runtime_configuration,
    reject_retired_remote_execution_input,
    strip_retired_remote_execution,
)

_BUSINESS_CAPABILITY_SECTIONS = {
    "storage": "storages",
    "resourceLibrary": "resourceLibraries",
    "mediaLibrary": "mediaLibraries",
    "recognition": "recognitionTypes",
    "metadata": "metadataPolicies",
    "naming": "namingPolicies",
    "classification": "classificationPolicies",
    "organize": "organizePolicies",
    "automation": "automationTaskDefinitions",
    "notification": "webhooks",
}


def _business_capability_status(document: object) -> dict[str, object]:
    """Project bounded capability state without exposing configuration values."""

    if not isinstance(document, dict):
        return {"businessState": "UNAVAILABLE", "items": {}}
    items: dict[str, dict[str, object]] = {}
    configured = False
    for capability, section in _BUSINESS_CAPABILITY_SECTIONS.items():
        values = document.get(section, [])
        if capability == "notification" and "webhooks" not in document:
            notifications = document.get("notifications")
            if isinstance(notifications, dict):
                values = notifications.get("webhooks", [])
        count = len(values) if isinstance(values, list) else 0
        configured = configured or count > 0
        items[capability] = {
            "state": "CONFIGURED" if count else "UNCONFIGURED",
            "nextAction": None if count else f"configure {capability}",
        }
    return {
        "businessState": "PARTIALLY_CONFIGURED" if configured else "EMPTY_ACTIVE",
        "items": items,
    }


FIRST_SETUP_STARTER_DOCUMENT_VERSION = 1
FIRST_SETUP_KIND = "first_runtime_setup"
MAX_VALIDATION_ERRORS = 16
_ENV_FIELD = re.compile(r"(?:env|environment)$", re.IGNORECASE)
_SECRET_KEYS = {
    "token",
    "password",
    "secret",
    "access_key",
    "secret_key",
    "session_token",
    "authorization",
    "username",
    "cookie",
    "api_key",
    "apikey",
    "accesskey",
    "secretkey",
    "sessiontoken",
}

_FIRST_SETUP_BLOCKERS = (
    {
        "code": "storage_required",
        "message": "Add at least one Storage before runtime validation.",
        "nextAction": "Add a safe, explicit Storage definition in the guided setup.",
    },
    {
        "code": "resource_library_required",
        "message": "Connect a ResourceLibrary to an enabled Storage.",
        "nextAction": "Add a ResourceLibrary and choose a Storage-relative source path.",
    },
    {
        "code": "media_library_required",
        "message": "Add a destination MediaLibrary with an explicit Storage-relative root.",
        "nextAction": "Add a MediaLibrary after configuring its destination Storage.",
    },
    {
        "code": "recognition_strategy_required",
        "message": "Define RecognitionTypes, rules, and type policies.",
        "nextAction": "Complete the Recognition strategy in the Draft.",
    },
    {
        "code": "metadata_strategy_required",
        "message": "Define a MetadataPolicy with an environment-owned Provider credential.",
        "nextAction": "Add the MetadataPolicy and Provider reference required by recognition.",
    },
    {
        "code": "naming_strategy_required",
        "message": "Define a NamingPolicy for each supported media type.",
        "nextAction": "Add and offline-preview the NamingPolicy templates.",
    },
    {
        "code": "classification_strategy_required",
        "message": "Define ClassificationPolicies and safe destination-relative paths.",
        "nextAction": "Add and offline-preview the ClassificationPolicy rules.",
    },
    {
        "code": "organize_authority_required",
        "message": "Declare explicit non-destructive organize authority and conflict handling.",
        "nextAction": "Add an OrganizePolicy and review its authority explanation.",
    },
    {
        "code": "activation_required",
        "message": "The Draft is not runtime authority until validation and activation succeed.",
        "nextAction": (
            "Validate the complete Draft, run required read-only checks, then activate it."
        ),
    },
)


class ManagedConfigurationService:
    """Stages, validates, and atomically publishes runtime configuration revisions.

    Validation deliberately uses the existing normalized JSON loader. It does not
    construct Storage adapters or metadata Providers, so Draft/Activate are safe
    configuration operations rather than hidden workflow execution.
    """

    def __init__(
        self,
        repository: ManagedConfigurationRepository,
        *,
        loader: Callable[[object], object] = load_runtime_configuration,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        bootstrap_database_path: str | None = None,
        bootstrap_document: object | None = None,
        management_only: bool = False,
    ) -> None:
        self._repository = repository
        self._loader = (
            (
                lambda document: load_managed_runtime_configuration(
                    document,
                    bootstrap_database_path=bootstrap_database_path,
                )
            )
            if bootstrap_database_path is not None and loader is load_runtime_configuration
            else loader
        )
        self._clock = clock
        self._bootstrap_database_path = bootstrap_database_path
        self._bootstrap_document = copy.deepcopy(bootstrap_document)
        self._management_only = bool(
            management_only
            or (
                bootstrap_document is not None
                and is_minimal_management_bootstrap(bootstrap_document)
            )
        )
        # A direct publication composes, validates and checks one candidate
        # entirely in memory.  The exact same revision identity is handed to the
        # single final transaction, so no unpublished revision is ever durable.
        self._transient_revisions: dict[str, ManagedConfigurationRevision] = {}
        self._transient_audit_contexts: dict[str, dict[str, object]] = {}
        self._transient_evidence: dict[str, tuple[object, ...]] = {}

    def bind_automation_publication_authority(self, authority) -> None:
        """Bind the authenticated API's current configured permission reader."""
        self._automation_publication_authority = authority

    @property
    def repository(self) -> ManagedConfigurationRepository:
        """Expose the existing persistence boundary to focused app adapters."""

        return self._repository

    @property
    def management_only(self) -> bool:
        """Whether this service is serving the fresh-setup authority boundary."""

        return self._management_only

    def storage_browser_cursor_key(self) -> bytes | None:
        """Return the persisted internal cursor-authentication key, if any.

        The key is deployment-internal metadata shared by every CLI/API process
        that serves a live library browse, so a continuation cursor minted by
        one process stays verifiable by a later one.  The repository owns its
        create-if-absent generation; this accessor only reads it and never
        writes, so a caller that must stay read-only can still resolve it.
        """

        from mediaflow.domain.configuration_management import (
            STORAGE_BROWSER_CURSOR_KEY_NAME,
        )

        reader = getattr(self._repository, "internal_key", None)
        if reader is None:
            return None
        return reader(STORAGE_BROWSER_CURSOR_KEY_NAME)

    def status_document(self) -> dict[str, object]:
        active = None
        health = "HEALTHY"
        unavailable_reason = None
        try:
            active = self._repository.get_active_revision()
        except Exception as error:
            health = "UNAVAILABLE"
            unavailable_reason = (
                f"managed Active configuration is unreadable ({type(error).__name__})"
            )
        if active is not None:
            try:
                self.verify_integrity(active)
                self._load_for_runtime(active.document)
            except RuntimeSnapshotUnavailable as error:
                health = "UNAVAILABLE"
                unavailable_reason = str(error)
            except Exception as error:
                health = "UNAVAILABLE"
                unavailable_reason = (
                    "managed Active configuration is not runtime-consumable "
                    f"({type(error).__name__})"
                )
        managed_activation = active is not None or self._has_managed_activation()
        if managed_activation and active is None:
            health = "UNAVAILABLE"
            unavailable_reason = "managed Active configuration is missing"
        try:
            revisions = tuple(
                revision
                for revision in self._repository.list_revisions(limit=100)
                if revision.status
                in {
                    ManagedConfigurationStatus.ACTIVE,
                    ManagedConfigurationStatus.SUPERSEDED,
                }
            )
        except Exception:
            revisions = ()
        # Only current and historical published snapshots are configuration
        # revisions.  An unpublished candidate is never a resumable state.
        setup_draft = None
        setup_required = not managed_activation
        if setup_required:
            authority = ConfigurationAuthority.MANAGEMENT_BOOTSTRAP.value
            status_health = "SETUP_REQUIRED"
            runtime_configured = False
        elif managed_activation:
            authority = ConfigurationAuthority.MANAGED.value
            status_health = health
            runtime_configured = active is not None and health == "HEALTHY"
        else:  # pragma: no cover - setup_required covers every no-Active state
            authority = ConfigurationAuthority.MANAGEMENT_BOOTSTRAP.value
            status_health = "SETUP_REQUIRED"
            runtime_configured = False
        runtime_ready = managed_activation and runtime_configured
        capabilities = _business_capability_status(active.document if active is not None else None)
        empty_active = (
            managed_activation
            and runtime_configured
            and capabilities.get("businessState") == "EMPTY_ACTIVE"
        )
        if empty_active:
            next_action = "配置已激活，媒体业务尚未配置；前往 Storage 或资源库配置"
        elif setup_required:
            next_action = "initialize configuration, then configure media capabilities"
        elif managed_activation and not runtime_configured:
            next_action = "inspect configuration status and publish an explicit replacement"
        else:
            next_action = None
        return {
            "authority": authority,
            "active": active.summary() if active else None,
            "lastKnownActive": self._last_known_active(),
            "health": status_health,
            "managementReady": True,
            "setupRequired": setup_required,
            "runtimeConfigured": runtime_configured,
            "runtimeReady": runtime_ready,
            "workflowAvailable": runtime_configured,
            "businessState": capabilities["businessState"],
            "capabilities": capabilities["items"],
            "emptyActive": empty_active,
            "recoveryRequired": managed_activation and not runtime_configured,
            "unavailableReason": unavailable_reason,
            "revisions": [self._revision_summary(item) for item in revisions],
            "managedActivation": managed_activation,
            "setupDraft": setup_draft.summary() if setup_draft is not None else None,
            "setupBlockers": _first_setup_blockers() if setup_required else [],
            "nextAction": next_action,
            "bootstrapMode": "MANAGEMENT_ONLY",
        }

    def detail(self, revision_id: str) -> dict[str, object]:
        revision = self.require(revision_id)
        status = self.status_document()
        active_document = None
        try:
            active_revision = self._repository.get_active_revision()
            active_document = active_revision.document if active_revision is not None else None
        except Exception:
            # Detail remains useful for recovery Drafts even when the old
            # Active payload is unreadable.
            active_document = None
        return {
            **revision.summary(),
            "authority": status["authority"],
            "health": status["health"],
            "managementReady": status["managementReady"],
            "setupRequired": status["setupRequired"],
            "runtimeConfigured": status["runtimeConfigured"],
            "runtimeReady": status["runtimeReady"],
            "workflowAvailable": status["workflowAvailable"],
            "businessState": status["businessState"],
            "capabilities": status["capabilities"],
            "emptyActive": status["emptyActive"],
            "recoveryRequired": status["recoveryRequired"],
            "unavailableReason": status["unavailableReason"],
            "lastKnownActive": status["lastKnownActive"],
            "setupDraft": status["setupDraft"],
            "setupBlockers": status["setupBlockers"],
            "nextAction": status["nextAction"],
            # The shared bounded projection preserves the selected immutable
            # revision identity and every supported managed family while
            # excluding deployment startup authority (database locator and API
            # principal identity); permitted deployment status stays in the
            # separate top-level status fields above.
            "document": _redact_document(
                portable_managed_configuration_document(revision.document)
            ),
            "diff": self._diff(active_document, revision.document),
            "audit": [
                _audit_document(item)
                for item in self._repository.list_revision_audits(revision.revision_id)
            ],
        }

    def _has_managed_activation(self) -> bool:
        marker = getattr(self._repository, "has_managed_activation", None)
        return bool(marker()) if callable(marker) else False

    def _last_known_active(self) -> dict[str, object] | None:
        marker = getattr(self._repository, "last_known_active", None)
        return marker() if callable(marker) else None

    def _load_for_runtime(self, document: object) -> object:
        if self._bootstrap_database_path is None:
            return document
        return self._loader(copy.deepcopy(document))

    def _accepted_baseline(self, revision: ManagedConfigurationRevision) -> object:
        """The already accepted content a stored revision is checked against.

        A persisted revision is immutable and was accepted by this deployment
        when it was imported, edited, or created as the server-owned first
        Draft.  New input is therefore judged at those submission boundaries;
        validating or activating the stored revision compares it with its own
        bytes, which keeps an unchanged historical object (for example the
        empty nested Webhook section of a first setup Draft) readable while a
        changed object still has to use the current spelling.  The baseline
        never supplies values to the revision.
        """

        return revision.document

    def _bind_deployment_authority(self, document: dict[str, object]) -> dict[str, object]:
        """One fail-closed deployment-authority boundary for a submitted document.

        Genuinely omitted authority is supplied from this deployment; supplied
        authority is validated against this deployment's own identity and a
        conflicting or malformed declaration is rejected rather than persisted
        for the next runtime startup.
        """

        return bind_deployment_authority(
            document,
            database_path=self._bootstrap_database_path,
            bootstrap_document=self._bootstrap_document,
        )

    def import_draft(
        self,
        document: object,
        *,
        actor: str,
        source: str = "manual",
    ) -> ManagedConfigurationRevision:
        normalized = _canonical_document(document)
        reject_retired_configuration_input(normalized)
        # Portable exports and displayed JSON omit deployment startup
        # authority; bind whatever was omitted back to this deployment before
        # the Draft is persisted so an imported/recovered document can never
        # carry (or lose) another deployment's database/principal identity.
        normalized = _canonical_document(self._bind_deployment_authority(normalized))
        reject_retired_remote_execution_input(normalized)
        _reject_literal_secrets(normalized)
        now = self._clock()
        try:
            active = self._repository.get_active_revision()
        except Exception:
            # A broken Active must not prevent an administrator from staging
            # an explicit replacement Draft.  It remains unusable authority.
            active = None
        if active is not None:
            try:
                # A syntactically readable but digest/schema-corrupt Active is
                # not a valid optimistic base.  Treat it like a missing
                # authority so an explicitly corrected replacement can be
                # published during recovery.  Runtime-invalid (but intact)
                # snapshots remain a real base and are safely superseded.
                self.verify_integrity(active)
            except RuntimeSnapshotUnavailable:
                active = None
        revision = ManagedConfigurationRevision(
            str(uuid4()),
            1,
            ManagedConfigurationStatus.DRAFT,
            MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
            _digest(normalized),
            normalized,
            now,
            now,
            base_active_revision_id=active.revision_id if active else None,
        )
        audit = self._audit(
            revision,
            "draft_import",
            actor,
            {**_document_evidence(revision), "source": _safe_source(source)},
            before={
                "authority": (
                    "MANAGED" if active else ConfigurationAuthority.MANAGEMENT_BOOTSTRAP.value
                )
            },
        )
        create = getattr(self._repository, "create_revision_with_audit", None)
        if callable(create):
            return create(revision, audit)
        created = self._repository.create_revision(revision)
        self._record_audit(audit)
        return created

    def create_first_draft(
        self,
        bootstrap_document: object | None = None,
        *,
        actor: str,
    ) -> ManagedConfigurationRevision:
        """Create the server-owned first setup Draft before runtime activation.

        Only the strict management bootstrap projection is copied.  The
        repository's first-Draft transaction repeats the authority and
        duplicate checks under ``BEGIN IMMEDIATE`` so concurrent API workers
        cannot create competing setup roots.
        """

        source = self._bootstrap_document if bootstrap_document is None else bootstrap_document
        bootstrap = load_minimal_management_bootstrap(source)
        self._management_only = True
        active = self._repository.get_active_revision()
        if active is not None:
            raise ConfigurationFirstDraftConflict(
                "managed Active configuration already exists; first setup is closed",
                revision=active,
                durable_state="active_configuration_preserved",
                next_action="import a new Draft from the current Active configuration",
            )
        if self._has_managed_activation():
            marker = self._last_known_active() or {}
            raise ConfigurationFirstDraftConflict(
                "managed Active configuration is unavailable; first setup is closed",
                revision_id=marker.get("revisionId"),
                version=marker.get("revisionSequence", marker.get("version")),
                digest=marker.get("digest"),
                durable_state="managed_active_unavailable",
                next_action="inspect configuration status and stage an explicit recovery Draft",
            )
        existing = self._first_setup_draft()
        if existing is not None:
            raise ConfigurationFirstDraftConflict(
                "the first setup Draft already exists",
                revision=existing,
                durable_state="setup_draft_preserved",
                next_action=("reload configuration status and resume the existing setup Draft"),
            )
        document = build_first_setup_starter_document(bootstrap)
        now = self._clock()
        revision = ManagedConfigurationRevision(
            str(uuid4()),
            1,
            ManagedConfigurationStatus.DRAFT,
            MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
            _digest(document),
            document,
            now,
            now,
        )
        audit = self._audit(
            revision,
            "first_draft_create",
            actor,
            {
                "starterVersion": FIRST_SETUP_STARTER_DOCUMENT_VERSION,
                "setupKind": FIRST_SETUP_KIND,
                "revisionId": revision.revision_id,
                "digest": revision.digest,
                "status": revision.status.value,
                "sections": sorted(document),
            },
            before={
                "authority": ConfigurationAuthority.MANAGEMENT_BOOTSTRAP.value,
                "revisionId": None,
            },
        )
        create = getattr(self._repository, "create_first_draft_with_audit", None)
        if callable(create):
            return create(revision, audit)
        # Small in-memory repositories used by focused unit tests may not yet
        # expose the SQLite atomic extension.  They still receive the normal
        # audited lifecycle; production uses the transaction above.
        create = getattr(self._repository, "create_revision_with_audit", None)
        if callable(create):
            return create(revision, audit)
        created = self._repository.create_revision(revision)
        self._record_audit(audit)
        return created

    def create_successor_draft(
        self,
        *,
        actor: str,
        expected_active_revision_id: str | None = None,
        expected_active_version: int | None = None,
        expected_active_digest: str | None = None,
        verified_active: ManagedConfigurationRevision | None = None,
    ) -> ManagedConfigurationRevision:
        """Create a successor Draft seeded by the immutable Active document.

        The Active revision must be readable and verifiable; missing,
        schema-unsupported or digest-corrupt Active fails closed and never
        falls back to a stale JSON bootstrap.  Optimistic checks on
        ``expectedActiveRevisionId`` / ``expectedActiveVersion`` /
        ``expectedActiveDigest`` (when supplied) detect a stale writer
        before a new Draft is published.
        """

        active = verified_active if verified_active is not None else self.active()
        if active is None:
            if self._has_managed_activation():
                marker = self._last_known_active() or {}
                raise RuntimeSnapshotUnavailable(
                    "managed Active configuration is unavailable; cannot create successor Draft",
                    revision_id=marker.get("revisionId"),
                    version=marker.get("revisionSequence", marker.get("version")),
                    digest=marker.get("digest"),
                    reason="managed_active_unavailable",
                )
            raise RuntimeSnapshotUnavailable(
                "no Active configuration exists; create the first setup Draft instead",
                reason="active_missing",
            )
        self.verify_integrity(active)
        current_revision_id = active.revision_id
        current_version = active.revision_sequence or active.version
        current_digest = active.digest
        if expected_active_revision_id and expected_active_revision_id != current_revision_id:
            raise ConfigurationVersionConflict(
                "Active revision does not match expectedActiveRevisionId; "
                "reload before creating successor Draft",
                revision_id=current_revision_id,
                current_version=current_version,
                current_digest=current_digest,
                durable_state="active_preserved",
                next_action="reload configuration status, then create the successor Draft again",
            )
        if expected_active_version is not None and expected_active_version != current_version:
            raise ConfigurationVersionConflict(
                "Active version does not match expectedActiveVersion; "
                "reload before creating successor Draft",
                revision_id=current_revision_id,
                current_version=current_version,
                current_digest=current_digest,
                durable_state="active_preserved",
                next_action="reload configuration status, then create the successor Draft again",
            )
        if expected_active_digest and expected_active_digest != current_digest:
            raise ConfigurationVersionConflict(
                "Active digest does not match expectedActiveDigest; "
                "reload before creating successor Draft",
                revision_id=current_revision_id,
                current_version=current_version,
                current_digest=current_digest,
                durable_state="active_preserved",
                next_action="reload configuration status, then create the successor Draft again",
            )
        # The accepted historical Active stays byte-identical; only the new
        # successor Draft drops the retired ticket setting, so a typed Save
        # never requires rebuilding an otherwise valid configuration.
        normalized = _canonical_document(
            strip_retired_remote_execution(copy.deepcopy(active.document))
        )
        _reject_literal_secrets(normalized)
        now = self._clock()
        revision = ManagedConfigurationRevision(
            str(uuid4()),
            1,
            ManagedConfigurationStatus.DRAFT,
            MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
            _digest(normalized),
            normalized,
            now,
            now,
            base_active_revision_id=current_revision_id,
        )
        audit = self._audit(
            revision,
            "successor_draft_create",
            actor,
            {
                **_document_evidence(revision),
                "source": "active",
                "baseActiveRevisionId": current_revision_id,
                "baseActiveVersion": current_version,
                "baseActiveDigest": current_digest,
            },
            before={
                "authority": ConfigurationAuthority.MANAGED.value,
                "revisionId": current_revision_id,
                "version": current_version,
                "digest": current_digest,
            },
        )
        create = getattr(self._repository, "create_revision_with_audit", None)
        if callable(create):
            return create(revision, audit)
        created = self._repository.create_revision(revision)
        self._record_audit(audit)
        return created

    def publish_document(
        self,
        document: object,
        *,
        actor: str,
        expected_active_revision_id: str | None = None,
        expected_active_version: int | None = None,
        expected_active_digest: str | None = None,
        readiness: Callable[[ManagedConfigurationRevision], object] | None = None,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
        replace_active: bool = False,
        audit_context: dict[str, object] | None = None,
    ) -> ManagedConfigurationRevision:
        """Validate and publish one complete document in a single transaction.

        The candidate and every read-only check exist only for this command.  A
        refusal or a failure discards them with the command; no ``draft`` or
        ``validated`` revision is ever persisted, and the final transaction
        writes only the new Active snapshot, its evidence and its audit.
        """

        normalized = _canonical_document(document)
        normalized = _canonical_document(self._bind_deployment_authority(normalized))
        _reject_literal_secrets(normalized)
        now = self._clock()
        try:
            active = self._repository.get_active_revision()
        except Exception:
            if not replace_active:
                raise
            active = None
        current_revision_id = active.revision_id if active is not None else None
        current_version = (
            (active.revision_sequence or active.version) if active is not None else None
        )
        current_digest = active.digest if active is not None else None
        incoming_api = normalized.get("api")
        incoming_remote = (
            incoming_api.get("remoteExecution") if isinstance(incoming_api, dict) else None
        )
        baseline_api = active.document.get("api") if active is not None else None
        baseline_remote = (
            baseline_api.get("remoteExecution") if isinstance(baseline_api, dict) else None
        )
        if active is None or incoming_remote != baseline_remote:
            reject_retired_remote_execution_input(normalized)
        normalized = _canonical_document(strip_retired_remote_execution(normalized))
        if active is not None:
            self.verify_integrity(active)
            reject_retired_configuration_input(normalized, baseline=active.document)
            _reject_unsafe_webhook_urls(normalized, current=active.document)
        else:
            reject_retired_configuration_input(normalized)
            _reject_unsafe_webhook_urls(normalized, current=None)
        if active is None and self._has_managed_activation() and not replace_active:
            marker = self._last_known_active() or {}
            raise RuntimeSnapshotUnavailable(
                "managed Active configuration is unavailable; explicit replacement is required",
                revision_id=marker.get("revisionId"),
                version=marker.get("revisionSequence", marker.get("version")),
                digest=marker.get("digest"),
                reason="managed_active_unavailable",
            )
        if expected_active_revision_id is not None and (
            expected_active_revision_id != current_revision_id
        ):
            raise ConfigurationVersionConflict(
                "Active revision does not match expectedActiveRevisionId; reload before publishing",
                revision_id=current_revision_id,
                current_version=current_version,
                current_digest=current_digest,
                durable_state="active_preserved",
                next_action="reload configuration status, then apply the change again",
            )
        if expected_active_version is not None and expected_active_version != current_version:
            raise ConfigurationVersionConflict(
                "Active version does not match expectedActiveVersion; reload before publishing",
                revision_id=current_revision_id,
                current_version=current_version,
                current_digest=current_digest,
                durable_state="active_preserved",
                next_action="reload configuration status, then apply the change again",
            )
        if expected_active_digest is not None and expected_active_digest != current_digest:
            raise ConfigurationVersionConflict(
                "Active digest does not match expectedActiveDigest; reload before publishing",
                revision_id=current_revision_id,
                current_version=current_version,
                current_digest=current_digest,
                durable_state="active_preserved",
                next_action="reload configuration status, then apply the change again",
            )
        try:
            self._loader(copy.deepcopy(normalized))
        except Exception as error:
            raise ValueError(
                f"configuration candidate is not runtime-valid: {_bounded_error(error)}"
            ) from error
        revision = ManagedConfigurationRevision(
            str(uuid4()),
            1,
            ManagedConfigurationStatus.VALIDATED,
            MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
            _digest(normalized),
            normalized,
            now,
            now,
            (),
            now,
            base_active_revision_id=current_revision_id,
        )
        self._transient_revisions[revision.revision_id] = revision
        try:
            evidence: tuple[object, ...] = ()
            if readiness is not None:
                collected = readiness(revision)
                if collected is not None:
                    evidence = (
                        tuple(collected) if isinstance(collected, (tuple, list)) else (collected,)
                    )
            if before_publish is not None:
                before_publish(revision)
            if audit_context is not None:
                self._transient_audit_contexts[revision.revision_id] = copy.deepcopy(audit_context)
            return self._publish_prepared(
                revision,
                actor=actor,
                evidence=evidence,
                audit_context=audit_context,
            )
        finally:
            self._drop_transient(revision.revision_id)

    def _publish_prepared(
        self,
        revision: ManagedConfigurationRevision,
        *,
        actor: str,
        evidence: tuple[object, ...],
        audit_context: dict[str, object] | None = None,
        automation_intent_ids: tuple[str, ...] = (),
    ) -> ManagedConfigurationRevision:
        """Atomically publish one already validated in-memory candidate."""

        from mediaflow.application.automation_execution_intent import publication_intents

        previous = self._repository.get_active_revision()
        intents = publication_intents(
            self._repository,
            previous,
            revision,
            actor,
            getattr(self, "_automation_publication_authority", None),
            explicit_ids=automation_intent_ids,
        )
        after = {
            "automationExecutionIntents": intents,
            **_document_evidence(revision, status=ManagedConfigurationStatus.ACTIVE),
            "automationTaskDefinitions": _automation_definition_evidence(revision.document),
        }
        if audit_context is not None:
            after["objectChange"] = copy.deepcopy(audit_context)
        before = (
            {
                **_document_evidence(previous),
                "automationTaskDefinitions": _automation_definition_evidence(previous.document),
            }
            if previous is not None
            else {
                "authority": ConfigurationAuthority.MANAGEMENT_BOOTSTRAP.value,
                "revisionId": None,
            }
        )
        active_revision = ManagedConfigurationRevision(
            revision.revision_id,
            revision.version,
            ManagedConfigurationStatus.ACTIVE,
            revision.schema_version,
            revision.digest,
            revision.document,
            revision.created_at,
            self._clock(),
            (),
            revision.validated_at or self._clock(),
            self._clock(),
            revision.base_active_revision_id,
        )
        audit = self._audit(
            active_revision,
            "activate",
            actor,
            after,
            before=before,
        )
        publish = getattr(self._repository, "publish_revision_with_audit", None)
        if callable(publish):
            return publish(active_revision, audit, evidence)
        # Focused in-memory repositories keep the historical two-step API.  The
        # production SQLite repository always takes the single-transaction path.
        create = getattr(self._repository, "create_revision_with_audit", None)
        if callable(create):
            staged = create(
                ManagedConfigurationRevision(
                    active_revision.revision_id,
                    active_revision.version,
                    ManagedConfigurationStatus.VALIDATED,
                    active_revision.schema_version,
                    active_revision.digest,
                    active_revision.document,
                    active_revision.created_at,
                    active_revision.updated_at,
                    (),
                    active_revision.validated_at,
                    base_active_revision_id=active_revision.base_active_revision_id,
                ),
                audit,
            )
        else:
            staged = self._repository.create_revision(
                ManagedConfigurationRevision(
                    active_revision.revision_id,
                    active_revision.version,
                    ManagedConfigurationStatus.VALIDATED,
                    active_revision.schema_version,
                    active_revision.digest,
                    active_revision.document,
                    active_revision.created_at,
                    active_revision.updated_at,
                    (),
                    active_revision.validated_at,
                    base_active_revision_id=active_revision.base_active_revision_id,
                )
            )
        for item in evidence:
            for name in (
                "save_local_setup_check",
                "save_storage_setup_check",
                "save_recognition_strategy_test",
                "save_destination_precheck",
            ):
                saver = getattr(self._repository, name, None)
                if (
                    callable(saver)
                    and type(item).__name__.lower().find(name.split("save_", 1)[1]) >= 0
                ):
                    saver(item)
                    break
        try:
            return self._repository.activate_revision(staged.revision_id, staged.version, audit)
        except Exception:
            discard = getattr(self._repository, "discard_revision", None)
            if callable(discard):
                discard(
                    staged.revision_id,
                    self._audit(
                        staged,
                        "publish_candidate_discarded",
                        actor,
                        {"revisionId": staged.revision_id, "status": "discarded"},
                        before=_document_evidence(staged),
                    ),
                )
            raise

    def _first_setup_draft(
        self,
        revisions: tuple[ManagedConfigurationRevision, ...] | None = None,
    ) -> ManagedConfigurationRevision | None:
        values = revisions
        if values is None:
            try:
                values = self._repository.list_revisions(limit=100)
            except Exception:
                return None
        for revision in values:
            setup = revision.document.get("setup")
            if (
                isinstance(setup, dict)
                and setup.get("kind") == FIRST_SETUP_KIND
                and revision.status is not ManagedConfigurationStatus.ACTIVE
            ):
                return revision
        return None

    def require(self, revision_id: str) -> ManagedConfigurationRevision:
        transient = self._transient_revisions.get(revision_id)
        if transient is not None:
            return transient
        revision = self._repository.get_revision(revision_id)
        if revision is None:
            raise LookupError(f"configuration revision {revision_id!r} was not found")
        return revision

    def is_transient_revision(self, revision_id: str) -> bool:
        """Whether this exact candidate exists only inside the current command."""

        return revision_id in self._transient_revisions

    def transient_audit_context(self, revision_id: str) -> dict[str, object] | None:
        context = self._transient_audit_contexts.get(revision_id)
        return copy.deepcopy(context) if context is not None else None

    def transient_evidence(self, revision_id: str) -> tuple[object, ...]:
        return self._transient_evidence.get(revision_id, ())

    def record_transient_evidence(
        self, revision_id: str, evidence: object | tuple[object, ...] | list[object]
    ) -> None:
        if revision_id not in self._transient_revisions:
            raise ValueError("evidence can only be collected for a transient candidate")
        values = (evidence,) if not isinstance(evidence, (tuple, list)) else tuple(evidence)
        existing = list(self._transient_evidence.get(revision_id, ()))
        existing.extend(item for item in values if item is not None)
        self._transient_evidence[revision_id] = tuple(existing)

    def release_transient_revision(self, revision_id: str) -> None:
        """Forget one request-scoped candidate after its command has finished.

        Durable ``active``/``superseded`` revisions are never touched. This is
        the explicit release for a preview or object analysis response: the
        revision identity may be returned as part of the check evidence, but
        it must not remain readable as configuration after the request.
        """

        self._drop_transient(revision_id)

    def stage_candidate_document(
        self,
        document: object,
        *,
        version: int = 1,
        base_active_revision_id: str | None,
        actor: str,
    ) -> ManagedConfigurationRevision:
        """Stage one candidate document that was composed from a readable source."""

        normalized = _canonical_document(copy.deepcopy(document))
        _reject_literal_secrets(normalized)
        now = self._clock()
        revision = ManagedConfigurationRevision(
            str(uuid4()),
            version,
            ManagedConfigurationStatus.DRAFT,
            MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
            _digest(normalized),
            normalized,
            now,
            now,
            base_active_revision_id=base_active_revision_id,
        )
        self._transient_revisions[revision.revision_id] = revision
        return revision

    def finalize_source_revision(
        self,
        revision_id: str,
        published: ManagedConfigurationRevision,
        *,
        actor: str,
        audit_context: dict[str, object] | None = None,
    ) -> None:
        """Mark a consumed legacy source row as published history, never a Draft."""

        if revision_id == published.revision_id:
            return
        try:
            source = self._repository.get_revision(revision_id)
        except Exception:
            return
        if source is None or source.status in {
            ManagedConfigurationStatus.ACTIVE,
            ManagedConfigurationStatus.SUPERSEDED,
        }:
            return
        finalized = ManagedConfigurationRevision(
            source.revision_id,
            published.version,
            ManagedConfigurationStatus.SUPERSEDED,
            source.schema_version,
            published.digest,
            copy.deepcopy(published.document),
            source.created_at,
            self._clock(),
            (),
            self._clock(),
            self._clock(),
            published.base_active_revision_id,
            source.revision_sequence,
        )
        after = _document_evidence(finalized)
        if audit_context is not None:
            after["objectChange"] = copy.deepcopy(audit_context)
        audit = self._audit(
            finalized,
            "publish_source_superseded",
            actor,
            after,
            before=_document_evidence(source),
        )
        update = getattr(self._repository, "update_revision_with_audit", None)
        if callable(update):
            try:
                update(finalized, source.version, audit)
            except Exception:
                return

    def _drop_transient(self, revision_id: str) -> None:
        self._transient_revisions.pop(revision_id, None)
        self._transient_audit_contexts.pop(revision_id, None)
        self._transient_evidence.pop(revision_id, None)

    def stage_successor_draft(
        self,
        *,
        actor: str,
        expected_active_revision_id: str | None = None,
        expected_active_version: int | None = None,
        expected_active_digest: str | None = None,
        verified_active: ManagedConfigurationRevision | None = None,
    ) -> ManagedConfigurationRevision:
        """Compose one successor candidate without persisting a Draft.

        Save commands call this instead of ``create_successor_draft``.  The
        returned revision is resolvable by :meth:`require` for validation and
        read-only evidence, but it has no repository row; the final publication
        transaction is the only writer.
        """

        active = verified_active if verified_active is not None else self.active()
        if active is None:
            if self._has_managed_activation():
                marker = self._last_known_active() or {}
                raise RuntimeSnapshotUnavailable(
                    "managed Active configuration is unavailable; cannot compose successor",
                    revision_id=marker.get("revisionId"),
                    version=marker.get("revisionSequence", marker.get("version")),
                    digest=marker.get("digest"),
                    reason="managed_active_unavailable",
                )
            raise RuntimeSnapshotUnavailable(
                "no Active configuration exists; initialize configuration first",
                reason="active_missing",
            )
        self.verify_integrity(active)
        current_revision_id = active.revision_id
        current_version = active.revision_sequence or active.version
        current_digest = active.digest
        if expected_active_revision_id and expected_active_revision_id != current_revision_id:
            raise ConfigurationVersionConflict(
                "Active revision does not match expectedActiveRevisionId; reload before saving",
                revision_id=current_revision_id,
                current_version=current_version,
                current_digest=current_digest,
                durable_state="active_preserved",
                next_action="reload configuration status, then apply the change again",
            )
        if expected_active_version is not None and expected_active_version != current_version:
            raise ConfigurationVersionConflict(
                "Active version does not match expectedActiveVersion; reload before saving",
                revision_id=current_revision_id,
                current_version=current_version,
                current_digest=current_digest,
                durable_state="active_preserved",
                next_action="reload configuration status, then apply the change again",
            )
        if expected_active_digest and expected_active_digest != current_digest:
            raise ConfigurationVersionConflict(
                "Active digest does not match expectedActiveDigest; reload before saving",
                revision_id=current_revision_id,
                current_version=current_version,
                current_digest=current_digest,
                durable_state="active_preserved",
                next_action="reload configuration status, then apply the change again",
            )
        normalized = _canonical_document(
            strip_retired_remote_execution(copy.deepcopy(active.document))
        )
        _reject_literal_secrets(normalized)
        now = self._clock()
        revision = ManagedConfigurationRevision(
            str(uuid4()),
            1,
            ManagedConfigurationStatus.DRAFT,
            MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
            _digest(normalized),
            normalized,
            now,
            now,
            base_active_revision_id=current_revision_id,
        )
        self._transient_revisions[revision.revision_id] = revision
        return revision

    def open_draft_revisions(self, *, limit: int = 100) -> tuple[ManagedConfigurationRevision, ...]:
        """Return newest-first open Draft revisions that an operator may resume.

        Only ``draft`` and ``validated`` revisions are open editing authority.
        The immutable Active revision and superseded history are excluded, so
        an eligible Draft is always one that can still be edited, validated
        and explicitly activated. Repository failures propagate to the caller:
        an unavailable Draft read must never be presented as a legitimate
        empty-Draft state.
        """

        values = self._repository.list_revisions(limit=limit)
        return tuple(
            revision
            for revision in values
            if revision.status
            in (ManagedConfigurationStatus.DRAFT, ManagedConfigurationStatus.VALIDATED)
        )

    def latest_open_draft_containing(
        self, section: str, object_id: str
    ) -> ManagedConfigurationRevision | None:
        """Return the newest open Draft revision whose document contains the object."""

        for revision in self.open_draft_revisions():
            section_items = revision.document.get(section)
            if (
                section == "webhooks"
                and not isinstance(section_items, list)
                and isinstance(revision.document.get("notifications"), dict)
            ):
                # Already-supported configuration documents keep the legacy
                # nested ``notifications.webhooks`` spelling.  A successor Draft
                # copied from such an Active document must still resolve its
                # Webhook definitions for the ordinary edit/test/activation
                # journey; the canonical root section remains preferred.
                section_items = revision.document["notifications"].get("webhooks")
            if isinstance(section_items, list) and any(
                isinstance(item, dict) and item.get("id") == object_id for item in section_items
            ):
                return revision
        return None

    def validate(self, revision_id: str, *, actor: str) -> ManagedConfigurationRevision:
        revision = self.require(revision_id)
        now = self._clock()
        errors: tuple[str, ...] = ()
        if revision.schema_version != MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION:
            errors = (
                "ValueError: unsupported managed configuration schema version "
                f"{revision.schema_version}",
            )
        else:
            try:
                if _digest(revision.document) != revision.digest:
                    raise ValueError("configuration Draft digest does not match its payload")
                reject_retired_remote_execution_input(revision.document)
                reject_retired_configuration_input(
                    revision.document, baseline=self._accepted_baseline(revision)
                )
                self._loader(copy.deepcopy(revision.document))
            except Exception as error:
                errors = (_bounded_error(error),)
        candidate = ManagedConfigurationRevision(
            revision.revision_id,
            revision.version,
            ManagedConfigurationStatus.VALIDATED
            if not errors
            else ManagedConfigurationStatus.DRAFT,
            revision.schema_version,
            revision.digest,
            revision.document,
            revision.created_at,
            now,
            errors,
            now if not errors else None,
            None,
            revision.base_active_revision_id,
        )
        if self.is_transient_revision(revision_id):
            self._transient_revisions[revision_id] = candidate
            return candidate
        after_evidence = {
            **_document_evidence(candidate),
            "automationTaskDefinitions": _automation_definition_evidence(candidate.document),
            "errors": list(errors),
        }
        before_evidence = {
            **_document_evidence(revision),
            "automationTaskDefinitions": _automation_definition_evidence(revision.document),
        }
        audit = self._audit(
            candidate,
            "validate" if not errors else "validation_failed",
            actor,
            after_evidence,
            before=before_evidence,
        )
        update = getattr(self._repository, "update_revision_with_audit", None)
        if callable(update):
            return update(candidate, revision.version, audit)
        result = self._repository.update_revision(candidate, revision.version)
        self._record_audit(audit)
        return result

    def edit_draft(
        self,
        revision_id: str,
        document: object,
        *,
        expected_version: int,
        actor: str,
        audit_context: dict[str, object] | None = None,
    ) -> ManagedConfigurationRevision:
        revision = self.require(revision_id)
        if revision.status in {
            ManagedConfigurationStatus.ACTIVE,
            ManagedConfigurationStatus.SUPERSEDED,
        }:
            raise ConfigurationActivationConflict(
                "published configuration is immutable; import a new Draft to change it",
                revision_id=revision_id,
            )
        if revision.version != expected_version:
            raise ConfigurationVersionConflict(
                "configuration Draft is stale; refresh it before editing",
                revision_id=revision.revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        normalized = _canonical_document(document)
        reject_retired_configuration_input(normalized, baseline=revision.document)
        # The advanced whole-document editor round-trips the bounded portable
        # projection (deployment authority excluded); rebind whatever authority
        # the submitted document omits so validation and runtime loading keep
        # consuming this deployment's own locator and principal identity.
        normalized = _canonical_document(self._bind_deployment_authority(normalized))
        reject_retired_remote_execution_input(normalized)
        _reject_literal_secrets(normalized)
        _reject_unsafe_webhook_urls(normalized, current=revision.document)
        now = self._clock()
        edited = ManagedConfigurationRevision(
            revision.revision_id,
            revision.version + 1,
            ManagedConfigurationStatus.DRAFT,
            MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
            _digest(normalized),
            normalized,
            revision.created_at,
            now,
            base_active_revision_id=revision.base_active_revision_id,
        )
        after_evidence = _document_evidence(edited)
        before_evidence = _document_evidence(revision)
        if audit_context is not None:
            context = copy.deepcopy(audit_context)
            encoded_context = json.dumps(
                context, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            if len(encoded_context.encode("utf-8")) > 16 * 1024:
                raise ValueError("configuration object audit context is too large")
            after_evidence["objectChange"] = context
            before_evidence["objectChange"] = {
                "kind": context.get("kind"),
                "objectId": context.get("objectId"),
                "action": context.get("action"),
                "before": context.get("before"),
                "after": None,
            }
        if self.is_transient_revision(revision_id):
            self._transient_revisions[revision_id] = edited
            if audit_context is not None:
                self._transient_audit_contexts[revision_id] = copy.deepcopy(audit_context)
            return edited
        audit = self._audit(
            edited,
            "draft_edit",
            actor,
            after_evidence,
            before=before_evidence,
        )
        update = getattr(self._repository, "update_revision_with_audit", None)
        if callable(update):
            return update(edited, revision.version, audit)
        result = self._repository.update_revision(edited, revision.version)
        self._record_audit(audit)
        return result

    def activate(
        self,
        revision_id: str,
        *,
        expected_version: int,
        actor: str,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
        automation_intent_ids: tuple[str, ...] = (),
    ) -> ManagedConfigurationRevision:
        revision = self.require(revision_id)
        if revision.status is not ManagedConfigurationStatus.VALIDATED:
            raise ConfigurationActivationConflict(
                "configuration must be successfully Validated before activation",
                revision_id=revision_id,
            )
        if revision.schema_version != MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION:
            raise ConfigurationActivationConflict(
                f"unsupported managed configuration schema version {revision.schema_version}",
                revision_id=revision_id,
            )
        if revision.version != expected_version:
            current = self._safe_active()
            raise ConfigurationActivationConflict(
                "configuration revision version is stale; refresh and validate again",
                revision_id=revision_id,
                current_revision_id=current.revision_id if current else None,
                current_version=current.version if current else None,
                current_digest=current.digest if current else None,
            )
        if _digest(revision.document) != revision.digest:
            raise ConfigurationActivationConflict(
                "validated configuration digest no longer matches its payload; "
                "revalidate the Draft",
                revision_id=revision_id,
            )
        # Re-run the exact loader immediately before publishing. This binds the
        # evidence to the digest and prevents stale validation from being activated.
        try:
            reject_retired_remote_execution_input(revision.document)
            reject_retired_configuration_input(
                revision.document, baseline=self._accepted_baseline(revision)
            )
            self._loader(copy.deepcopy(revision.document))
        except Exception as error:
            raise ConfigurationActivationConflict(
                f"configuration revision is no longer valid: {_bounded_error(error)}",
                revision_id=revision_id,
            ) from error
        if self.is_transient_revision(revision_id):
            try:
                if before_publish is not None:
                    before_publish(revision)
                return self._publish_prepared(
                    ManagedConfigurationRevision(
                        revision.revision_id,
                        revision.version,
                        ManagedConfigurationStatus.ACTIVE,
                        revision.schema_version,
                        revision.digest,
                        revision.document,
                        revision.created_at,
                        revision.updated_at,
                        (),
                        revision.validated_at,
                        self._clock(),
                        revision.base_active_revision_id,
                        revision.revision_sequence,
                    ),
                    actor=actor,
                    evidence=self.transient_evidence(revision_id),
                    audit_context=self.transient_audit_context(revision_id),
                    automation_intent_ids=automation_intent_ids,
                )
            finally:
                self._drop_transient(revision_id)
        from mediaflow.application.automation_execution_intent import publication_intents

        previous = self._repository.get_active_revision()
        intents = publication_intents(
            self._repository,
            previous,
            revision,
            actor,
            getattr(self, "_automation_publication_authority", None),
            explicit_ids=automation_intent_ids,
        )
        if before_publish is not None:
            # Runtime consumers are constructed while the old Active pointer is
            # still authoritative.  A failed preparation therefore cannot leave
            # the persisted pointer ahead of the process binding.
            before_publish(revision)
        try:
            active = self._repository.get_active_revision()
        except Exception:
            active = None
        activation_after = {
            "automationExecutionIntents": intents,
            **_document_evidence(revision, status=ManagedConfigurationStatus.ACTIVE),
            "automationTaskDefinitions": _automation_definition_evidence(revision.document),
        }
        activation_before = (
            {
                **_document_evidence(active),
                "automationTaskDefinitions": _automation_definition_evidence(active.document),
            }
            if active is not None
            else {
                "authority": ConfigurationAuthority.MANAGEMENT_BOOTSTRAP.value,
                "revisionId": None,
            }
        )
        audit = self._audit(
            revision,
            "activate",
            actor,
            activation_after,
            before=activation_before,
        )
        return self._repository.activate_revision(revision_id, expected_version, audit)

    def active(self) -> ManagedConfigurationRevision | None:
        return self._repository.get_active_revision()

    def _safe_active(self) -> ManagedConfigurationRevision | None:
        try:
            return self._repository.get_active_revision()
        except Exception:
            return None

    @property
    def bootstrap_database_path(self) -> str | None:
        return self._bootstrap_database_path

    def has_managed_activation(self) -> bool:
        return self._has_managed_activation()

    def last_known_active(self) -> dict[str, object] | None:
        """Expose the durable authority marker for fail-closed API errors."""

        return self._last_known_active()

    def current_document(self, bootstrap_document: object) -> dict[str, object]:
        """Return the document currently authoritative for a new Draft.

        Before the first activation this is the JSON bootstrap.  Afterwards
        the immutable Active payload is the only source; a missing Active is a
        fail-closed condition rather than permission to fall back silently.
        """
        active = self.active()
        if active is not None:
            self.verify_integrity(active)
            return copy.deepcopy(active.document)
        if self._has_managed_activation():
            raise RuntimeSnapshotUnavailable(
                "managed Active configuration is unavailable; cannot import current configuration"
            )
        if not isinstance(bootstrap_document, dict):
            raise ValueError("current bootstrap configuration is unavailable")
        return copy.deepcopy(bootstrap_document)

    def verify_integrity(self, revision: ManagedConfigurationRevision) -> None:
        if revision.schema_version != MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION:
            raise RuntimeSnapshotUnavailable(
                f"managed configuration snapshot {revision.revision_id!r} schema is unsupported",
                revision_id=revision.revision_id,
                version=revision.revision_sequence,
                digest=revision.digest,
                reason="schema_unsupported",
            )
        if _digest(revision.document) != revision.digest:
            raise RuntimeSnapshotUnavailable(
                f"managed configuration snapshot {revision.revision_id!r} digest is corrupt",
                revision_id=revision.revision_id,
                version=revision.revision_sequence,
                digest=revision.digest,
                reason="digest_corrupt",
            )

    def validate_runtime_snapshot(self, revision_id: str, digest: str) -> None:
        """Validate an immutable saved snapshot without constructing runtime adapters."""

        try:
            revision = self.require(revision_id)
        except LookupError as error:
            raise RuntimeSnapshotUnavailable(
                f"managed configuration snapshot {revision_id!r} is unavailable",
                revision_id=revision_id,
                digest=digest,
                reason="snapshot_missing",
            ) from error
        except Exception as error:
            raise RuntimeSnapshotUnavailable(
                f"managed configuration snapshot {revision_id!r} is unreadable",
                revision_id=revision_id,
                digest=digest,
                reason="snapshot_unreadable",
            ) from error
        if revision.status not in {
            ManagedConfigurationStatus.ACTIVE,
            ManagedConfigurationStatus.SUPERSEDED,
        }:
            raise RuntimeSnapshotUnavailable(
                f"managed configuration snapshot {revision.revision_id!r} is not published",
                revision_id=revision.revision_id,
                version=revision.revision_sequence,
                digest=revision.digest,
                reason="snapshot_not_published",
            )
        self.verify_integrity(revision)
        if digest != revision.digest:
            raise RuntimeSnapshotUnavailable(
                f"saved configuration snapshot {revision.revision_id!r} digest does not match",
                revision_id=revision.revision_id,
                version=revision.revision_sequence,
                digest=digest,
                reason="snapshot_digest_mismatch",
            )
        try:
            self._load_for_runtime(copy.deepcopy(revision.document))
        except RuntimeSnapshotUnavailable:
            raise
        except Exception as error:
            raise RuntimeSnapshotUnavailable(
                f"saved configuration snapshot {revision.revision_id!r} is unavailable: "
                f"{type(error).__name__}",
                revision_id=revision.revision_id,
                version=revision.revision_sequence,
                digest=revision.digest,
                reason="runtime_invalid",
            ) from error

    def _record_audit(self, audit: ConfigurationChangeAudit) -> None:
        record = getattr(self._repository, "record_configuration_audit", None)
        if callable(record):
            record(audit)

    def _audit(
        self,
        revision: ManagedConfigurationRevision,
        action: str,
        actor: str,
        after: dict[str, object],
        *,
        before: dict[str, object] | None = None,
    ) -> ConfigurationChangeAudit:
        normalized_actor = actor.strip() if isinstance(actor, str) else ""
        if not normalized_actor or len(normalized_actor) > 200:
            raise ValueError(
                "configuration actor must be a non-empty string of at most 200 characters"
            )
        return ConfigurationChangeAudit(
            str(uuid4()),
            ConfigurationObjectKind.SYSTEM_SETTINGS,
            revision.revision_id,
            action,
            before or {"revisionId": revision.revision_id, "digest": revision.digest},
            after,
            self._clock(),
            normalized_actor,
        )

    @staticmethod
    def _revision_summary(revision: ManagedConfigurationRevision) -> dict[str, object]:
        return revision.summary()

    @staticmethod
    def _diff(
        active: dict[str, object] | None,
        candidate: dict[str, object],
    ) -> dict[str, object]:
        if active is None:
            return {
                "changedSections": sorted(candidate),
                "baseline": ConfigurationAuthority.MANAGEMENT_BOOTSTRAP.value,
            }
        changed = sorted(
            key for key in set(active).union(candidate) if active.get(key) != candidate.get(key)
        )
        return {"changedSections": changed, "baseline": "ACTIVE"}


def build_first_setup_starter_document(bootstrap) -> dict[str, object]:
    """Build the bounded, inactive document used by a fresh setup Draft."""

    api: dict[str, object] = {}
    if bootstrap.api_principals:
        api["principals"] = [
            {
                "id": item.principal_id,
                "tokenEnv": item.token_env,
                "roles": [role.value for role in item.roles],
                "enabled": item.enabled,
            }
            for item in bootstrap.api_principals
        ]
    return {
        "version": 1,
        "setup": {
            "starterVersion": FIRST_SETUP_STARTER_DOCUMENT_VERSION,
            "kind": FIRST_SETUP_KIND,
            "status": "setup_required",
            "runtimeReady": False,
            "workflowAvailable": False,
            "blockers": _first_setup_blockers(),
            "nextAction": (
                "complete the guided setup, validate the Draft, run required read-only checks, "
                "and activate it"
            ),
        },
        "persistence": {"databasePath": bootstrap.database_path},
        "api": api,
        # Empty sections are intentional.  No fabricated path, endpoint,
        # strategy, or media authority is promoted into a runtime by the starter.
        "storages": [],
        "resourceLibraries": [],
        "mediaLibraries": [],
        "metadataPolicies": [],
        "namingPolicies": [],
        "classificationPolicies": [],
        "organizePolicies": [],
        "recognitionTypes": [],
        "recognitionRules": [],
        "recognitionTypePolicies": [],
        "automationTaskDefinitions": [],
        "webhooks": [],
        "automation": {
            "workerPollSeconds": 2,
            "schedulerPollSeconds": 5,
            "maximumActiveJobs": 100,
        },
        "notifications": {
            "pollSeconds": 5,
            "deliveryLeaseSeconds": 300,
        },
        "operationalLogging": {
            "enabled": False,
            "minimumLevel": "INFO",
            "retentionDays": 30,
            "maximumRecords": 10000,
        },
        "workflowRetry": {
            "enabled": False,
            "maxAttempts": 3,
            "baseDelaySeconds": 1,
            "maxDelaySeconds": 30,
            "jitterRatio": 0.2,
        },
    }


def _first_setup_blockers() -> list[dict[str, str]]:
    return copy.deepcopy(list(_FIRST_SETUP_BLOCKERS))


def _canonical_document(document: object) -> dict[str, object]:
    if not isinstance(document, dict):
        raise ValueError("configuration Draft must be a JSON object")
    try:
        encoded = json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        if len(encoded.encode("utf-8")) > 1024 * 1024:
            raise ValueError("configuration Draft must be at most 1 MiB")
        return json.loads(encoded)
    except (TypeError, ValueError) as error:
        raise ValueError(f"configuration Draft is not valid JSON: {error}") from error


def _digest(document: dict[str, object]) -> str:
    return canonical_document_digest(document)


def _reject_literal_secrets(value: object, path: str = "configuration") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            normalized = re.sub(r"[^a-z0-9]", "", key_text.lower())
            if normalized in {re.sub(r"[^a-z0-9]", "", item) for item in _SECRET_KEYS}:
                if _ENV_FIELD.search(key_text) is None:
                    raise ValueError(f"literal secret field is not allowed at {path}.{key_text}")
            _reject_literal_secrets(child, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_literal_secrets(child, f"{path}[{index}]")


def _reject_unsafe_webhook_urls(
    document: dict[str, object],
    *,
    current: dict[str, object] | None,
) -> None:
    """Reject credential-bearing Webhook URLs before a Draft is persisted.

    ``current`` is the revision being edited, or None for a brand-new import.
    A URL that is unsafe but already persisted unchanged in that exact current
    revision stays correctable (a legacy Draft may be opened and its Webhook
    edited/deleted); any newly introduced or changed unsafe Webhook URL fails
    closed with a bounded message that never echoes the URL or its values.
    """

    current_urls = set(webhook_url_items(current)) if current is not None else set()
    for webhook_id, _url in unsafe_webhook_url_items(document):
        if (webhook_id, _url) in current_urls:
            continue
        message = (
            f"Webhook {webhook_id} URL must not include credentials, a query or a "
            "fragment; correct the endpoint URL before saving"
            if webhook_id
            else (
                "Webhook URL must not include credentials, a query or a fragment; "
                "correct the endpoint URL before saving"
            )
        )
        raise ValueError(message)


def _redact_document(document: dict[str, object]) -> dict[str, object]:
    forbidden = {re.sub(r"[^a-z0-9]", "", item) for item in _SECRET_KEYS}

    def redact(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: "***REDACTED***"
                if re.sub(r"[^a-z0-9]", "", str(key).lower()) in forbidden
                else redact(child)
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [redact(child) for child in value]
        return copy.deepcopy(value)

    safe = redact(document)
    if isinstance(safe, dict):
        # Suppress already-persisted/legacy unsafe Webhook endpoint URLs in the
        # whole-document projection the same way every other projection does.
        redact_webhook_urls(safe)
    return safe  # type: ignore[return-value]


def _audit_document(audit: ConfigurationChangeAudit) -> dict[str, object]:
    return {
        "auditId": audit.audit_id,
        "action": audit.action,
        "actor": audit.actor,
        "occurredAt": audit.occurred_at.isoformat(),
        "before": audit.safe_before(),
        "after": audit.safe_after(),
    }


def _document_evidence(
    revision: ManagedConfigurationRevision | None,
    *,
    status: ManagedConfigurationStatus | None = None,
) -> dict[str, object]:
    """Return bounded, secret-free before/after evidence for lifecycle audit."""

    if revision is None:
        return {"revisionId": None, "status": "NONE"}
    sections: dict[str, str] = {}
    for key, value in sorted(revision.document.items()):
        sections[key] = _digest({key: value})
    return {
        "revisionId": revision.revision_id,
        "revisionSequence": revision.revision_sequence,
        "version": revision.version,
        "status": (status or revision.status).value,
        "digest": revision.digest,
        "sections": sections,
    }


def _automation_definition_evidence(document: dict[str, object]) -> dict[str, object]:
    """Project bounded, secret-free definition fields into lifecycle audits."""

    values = document.get("automationTaskDefinitions")
    if values is None:
        automation = document.get("automation")
        values = automation.get("taskDefinitions") if isinstance(automation, dict) else None
    if not isinstance(values, list):
        return {"total": 0, "items": [], "truncated": False}
    allowed = (
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
    )
    items = [
        {key: _bounded_definition_value(value[key]) for key in allowed if key in value}
        for value in values[:32]
        if isinstance(value, dict)
    ]
    return {"total": len(values), "items": items, "truncated": len(values) > len(items)}


def _bounded_definition_value(value: object) -> object:
    if isinstance(value, str):
        return value[:256]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)[:256]


def _bounded_error(error: Exception) -> str:
    message = str(error).strip() or type(error).__name__
    return f"{type(error).__name__}: {message[:480]}"


def _safe_source(source: str) -> str:
    if not isinstance(source, str):
        return "manual"
    value = source.strip().casefold()
    return value if value in {"manual", "api", "current", "file"} else "manual"


# Compatibility alias for callers that prefer the shorter name.
ConfigurationSnapshotService = ManagedConfigurationService
