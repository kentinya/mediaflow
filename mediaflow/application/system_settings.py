from __future__ import annotations

import re
from typing import Any

from mediaflow.application.configuration_snapshot import (
    ManagedConfigurationService,
    _reject_literal_secrets,
)
from mediaflow.domain.configuration_management import (
    ConfigurationVersionConflict,
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.system_settings import (
    SystemSettings,
    SystemSettingsBoundary,
    SystemSettingsEdit,
    apply_settings_edits,
    validate_settings_edit,
)


class SystemSettingsService:
    """Read and edit System Settings through the managed Draft authority.

    Settings are projected from managed configuration revisions.  Reads return the
    Active snapshot when available, falling back to the current Draft.  Edits
    create or update a successor Draft through the existing revision service.
    """

    _SECRET_PATTERNS = re.compile(
        r"(?:token|password|secret|access_key|secret_key|session_token|"
        r"authorization|username|cookie|api_key|apikey|accesskey|secretkey)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        configuration_service: ManagedConfigurationService,
    ) -> None:
        self._config = configuration_service

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_active(self) -> SystemSettings:
        """Read System Settings from the Active revision, or fail closed."""

        active = self._config.active()
        if active is None:
            if self._config.has_managed_activation():
                marker = self._config.last_known_active() or {}
                raise RuntimeSnapshotUnavailable(
                    "managed Active configuration is unavailable",
                    revision_id=marker.get("revisionId"),
                    version=marker.get("revisionSequence", marker.get("version")),
                    digest=marker.get("digest"),
                    reason="active_missing",
                )
            raise RuntimeSnapshotUnavailable(
                "no Active configuration exists; system settings are not available",
                reason="active_missing",
            )
        self._config.verify_integrity(active)
        bootstrap_db = self._config.bootstrap_database_path
        return SystemSettings.from_document(
            active.document,
            revision_id=active.revision_id,
            revision_version=active.revision_sequence or active.version,
            revision_digest=active.digest,
            is_active=True,
            bootstrap_database_path=bootstrap_db,
        )

    def read_draft_or_active(self, revision_id: str | None = None) -> SystemSettings:
        """Read System Settings from the Active revision or a specific Draft."""

        if revision_id is None:
            return self.read_active()
        # Check if this is the Active revision.
        active = self._config.active()
        if active is not None and active.revision_id == revision_id:
            self._config.verify_integrity(active)
            return SystemSettings.from_document(
                active.document,
                revision_id=active.revision_id,
                revision_version=active.revision_sequence or active.version,
                revision_digest=active.digest,
                is_active=True,
                bootstrap_database_path=self._config.bootstrap_database_path,
            )
        return self.read_draft(revision_id)

    def read_draft(self, revision_id: str) -> SystemSettings:
        """Read System Settings from a specific Draft revision."""

        revision = self._config.require(revision_id)
        if revision.status not in {
            ManagedConfigurationStatus.DRAFT,
            ManagedConfigurationStatus.VALIDATED,
        }:
            raise RuntimeSnapshotUnavailable(
                "settings can only be read from a Draft or Validated revision",
                revision_id=revision.revision_id,
                reason="revision_not_editable",
            )
        bootstrap_db = self._config.bootstrap_database_path
        return SystemSettings.from_document(
            revision.document,
            revision_id=revision.revision_id,
            revision_version=revision.revision_sequence or revision.version,
            revision_digest=revision.digest,
            is_active=False,
            bootstrap_database_path=bootstrap_db,
        )

    def read_from_document(self, document: dict[str, Any]) -> SystemSettings:
        """Project System Settings from a raw document (for preview/testing)."""

        bootstrap_db = self._config.bootstrap_database_path
        return SystemSettings.from_document(
            document,
            revision_id=None,
            revision_version=None,
            revision_digest=None,
            is_active=False,
            bootstrap_database_path=bootstrap_db,
        )

    # ------------------------------------------------------------------
    # Edit — create successor Draft and apply settings
    # ------------------------------------------------------------------

    def edit(
        self,
        *,
        edits: tuple[SystemSettingsEdit, ...],
        actor: str,
        expected_active_revision_id: str | None = None,
        expected_active_version: int | None = None,
        expected_active_digest: str | None = None,
    ) -> SystemSettings:
        """Create a successor Draft, apply settings edits, and return the new Draft.

        This does NOT activate the Draft.  The caller (or operator) must validate
        and activate the Draft separately.  Edits that target bootstrap-immutable
        fields are rejected before any Draft is created.
        """

        bootstrap_db = self._config.bootstrap_database_path
        validation_errors = validate_settings_edit(edits, bootstrap_db)
        if validation_errors:
            raise SystemSettingsValidationError(validation_errors)

        # Determine the source document: prefer Active, fall back to bootstrap.
        try:
            self._config.current_document({})
        except RuntimeSnapshotUnavailable as error:
            raise RuntimeSnapshotUnavailable(
                "cannot create settings Draft: no Active or bootstrap configuration available",
                reason=error.args[0] if error.args else "unavailable",
            ) from error

        # Create successor Draft from current Active.
        try:
            successor = self._config.create_successor_draft(
                actor=actor,
                expected_active_revision_id=expected_active_revision_id,
                expected_active_version=expected_active_version,
                expected_active_digest=expected_active_digest,
            )
        except RuntimeSnapshotUnavailable:
            raise RuntimeSnapshotUnavailable(
                "cannot create settings Draft: Active configuration is unavailable",
                reason="active_missing",
            )
        except ConfigurationVersionConflict:
            raise

        # Apply validated settings edits to the successor Draft document.
        edited_doc = apply_settings_edits(dict(successor.document), edits)
        _reject_literal_secrets(edited_doc)

        # Update the Draft with the edited settings.
        edited = self._config.edit_draft(
            successor.revision_id,
            edited_doc,
            expected_version=successor.version,
            actor=actor,
            audit_context={
                "kind": "system_settings",
                "objectId": "system_settings",
                "action": "settings_edit",
                "edits": [{"field": e.field_path, "type": type(e.value).__name__} for e in edits],
            },
        )

        bootstrap_db = self._config.bootstrap_database_path
        return SystemSettings.from_document(
            edited.document,
            revision_id=edited.revision_id,
            revision_version=edited.revision_sequence or edited.version,
            revision_digest=edited.digest,
            is_active=False,
            bootstrap_database_path=bootstrap_db,
        )

    def edit_draft(
        self,
        revision_id: str,
        *,
        edits: tuple[SystemSettingsEdit, ...],
        expected_version: int,
        actor: str,
    ) -> SystemSettings:
        """Apply settings edits to an existing Draft revision.

        The Draft must not be Active or Superseded.  Optimistic concurrency
        is enforced via ``expectedVersion``.
        """

        bootstrap_db = self._config.bootstrap_database_path
        validation_errors = validate_settings_edit(edits, bootstrap_db)
        if validation_errors:
            raise SystemSettingsValidationError(validation_errors)

        # Load the current revision and verify it's editable.
        current = self._config.require(revision_id)
        if current.status in {
            ManagedConfigurationStatus.ACTIVE,
            ManagedConfigurationStatus.SUPERSEDED,
        }:
            raise RuntimeSnapshotUnavailable(
                "published configuration is immutable; create a successor Draft instead",
                revision_id=revision_id,
                reason="revision_immutable",
            )
        if current.version != expected_version:
            raise ConfigurationVersionConflict(
                "configuration Draft is stale; refresh it before editing",
                revision_id=current.revision_id,
                current_version=current.version,
                current_digest=current.digest,
            )

        edited_doc = apply_settings_edits(dict(current.document), edits)
        _reject_literal_secrets(edited_doc)

        edited = self._config.edit_draft(
            revision_id,
            edited_doc,
            expected_version=expected_version,
            actor=actor,
            audit_context={
                "kind": "system_settings",
                "objectId": "system_settings",
                "action": "settings_edit",
                "edits": [{"field": e.field_path, "type": type(e.value).__name__} for e in edits],
            },
        )

        bootstrap_db = self._config.bootstrap_database_path
        return SystemSettings.from_document(
            edited.document,
            revision_id=edited.revision_id,
            revision_version=edited.revision_sequence or edited.version,
            revision_digest=edited.digest,
            is_active=False,
            bootstrap_database_path=bootstrap_db,
        )

    # ------------------------------------------------------------------
    # Consumption evidence
    # ------------------------------------------------------------------

    def consumption_evidence(self) -> dict[str, Any]:
        """Return the exact Active snapshot identity consumed by runtime."""

        active = self._config.active()
        if active is None:
            return {
                "consumed": False,
                "reason": "no_active",
                "nextAction": "activate a configuration revision to consume settings",
            }
        try:
            self._config.verify_integrity(active)
        except RuntimeSnapshotUnavailable as error:
            return {
                "consumed": False,
                "reason": "active_corrupt",
                "message": str(error),
                "nextAction": "inspect configuration status and stage a recovery Draft",
            }
        settings = SystemSettings.from_document(
            active.document,
            revision_id=active.revision_id,
            revision_version=active.revision_sequence or active.version,
            revision_digest=active.digest,
            is_active=True,
            bootstrap_database_path=self._config.bootstrap_database_path,
        )
        return {
            "consumed": True,
            "revisionId": active.revision_id,
            "revisionVersion": active.revision_sequence or active.version,
            "digest": active.digest,
            "settingsSections": sorted(settings.field_boundaries.keys()),
            "bootstrapDatabasePath": settings.bootstrap_database_path,
            "restartRequiredFields": sorted(
                k
                for k, v in settings.field_boundaries.items()
                if v == SystemSettingsBoundary.RESTART_REQUIRED
            ),
            "hotConsumedFields": sorted(
                k
                for k, v in settings.field_boundaries.items()
                if v == SystemSettingsBoundary.HOT_CONSUMED
            ),
        }


class SystemSettingsValidationError(ValueError):
    """Raised when one or more settings edits fail validation."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__(
            f"{len(errors)} settings validation error(s): "
            + "; ".join(e.get("code", "error") for e in errors)
        )
        self.errors = errors
