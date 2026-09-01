from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationAuthority,
    ConfigurationChangeAudit,
    ConfigurationObjectKind,
    ConfigurationVersionConflict,
    ManagedConfigurationRepository,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
)
from mediaflow.infrastructure.runtime_configuration import (
    load_managed_runtime_configuration,
    load_runtime_configuration,
)

MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION = 1
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

    @property
    def repository(self) -> ManagedConfigurationRepository:
        """Expose the existing persistence boundary to focused app adapters."""

        return self._repository

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
            revisions = self._repository.list_revisions(limit=100)
        except Exception:
            revisions = ()
        return {
            "authority": (
                ConfigurationAuthority.MANAGED.value
                if managed_activation
                else ConfigurationAuthority.JSON_BOOTSTRAP.value
            ),
            "active": active.summary() if active else None,
            "lastKnownActive": self._last_known_active(),
            "health": health if managed_activation else "BOOTSTRAP",
            "runtimeReady": managed_activation and health == "HEALTHY",
            "unavailableReason": unavailable_reason,
            "revisions": [self._revision_summary(item) for item in revisions],
            "managedActivation": managed_activation,
        }

    def detail(self, revision_id: str) -> dict[str, object]:
        revision = self.require(revision_id)
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
        return {
            **revision.summary(),
            "authority": (
                ConfigurationAuthority.MANAGED.value
                if managed_activation
                else ConfigurationAuthority.JSON_BOOTSTRAP.value
            ),
            "health": health if managed_activation else "BOOTSTRAP",
            "runtimeReady": managed_activation and health == "HEALTHY",
            "unavailableReason": unavailable_reason,
            "lastKnownActive": self._last_known_active(),
            "document": _redact_document(revision.document),
            "diff": self._diff(active.document if active else None, revision.document),
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

    def import_draft(
        self,
        document: object,
        *,
        actor: str,
        source: str = "manual",
    ) -> ManagedConfigurationRevision:
        normalized = _canonical_document(document)
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
            before={"authority": "MANAGED" if active else "JSON_BOOTSTRAP"},
        )
        create = getattr(self._repository, "create_revision_with_audit", None)
        if callable(create):
            return create(revision, audit)
        created = self._repository.create_revision(revision)
        self._record_audit(audit)
        return created

    def require(self, revision_id: str) -> ManagedConfigurationRevision:
        revision = self._repository.get_revision(revision_id)
        if revision is None:
            raise LookupError(f"configuration revision {revision_id!r} was not found")
        return revision

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
        _reject_literal_secrets(normalized)
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
            self._loader(copy.deepcopy(revision.document))
        except Exception as error:
            raise ConfigurationActivationConflict(
                f"configuration revision is no longer valid: {_bounded_error(error)}",
                revision_id=revision_id,
            ) from error
        try:
            active = self._repository.get_active_revision()
        except Exception:
            active = None
        activation_after = {
            **_document_evidence(revision, status=ManagedConfigurationStatus.ACTIVE),
            "automationTaskDefinitions": _automation_definition_evidence(revision.document),
        }
        activation_before = (
            {
                **_document_evidence(active),
                "automationTaskDefinitions": _automation_definition_evidence(active.document),
            }
            if active is not None
            else {"authority": "JSON_BOOTSTRAP", "revisionId": None}
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
            return {"changedSections": sorted(candidate), "baseline": "JSON_BOOTSTRAP"}
        changed = sorted(
            key for key in set(active).union(candidate) if active.get(key) != candidate.get(key)
        )
        return {"changedSections": changed, "baseline": "ACTIVE"}


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
    encoded = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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

    return redact(document)  # type: ignore[return-value]


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
