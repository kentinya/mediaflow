from __future__ import annotations

import re
from collections.abc import Callable
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
        *,
        runtime_snapshot_provider: Callable[[], dict[str, Any] | None] | None = None,
    ) -> None:
        self._config = configuration_service
        self._runtime_snapshot_provider = runtime_snapshot_provider

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
            draft_version=active.version,
            is_active=True,
            bootstrap_database_path=bootstrap_db,
        )

    def read_draft_or_active(self, revision_id: str | None = None) -> SystemSettings:
        """Read System Settings from the current or a historical published revision.

        A historical published revision may be inspected by its exact ID; an
        editable draft is never a settings authority.
        """

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
                draft_version=active.version,
                is_active=True,
                bootstrap_database_path=self._config.bootstrap_database_path,
            )
        return self.read_draft(revision_id)

    def read_draft(self, revision_id: str) -> SystemSettings:
        """Read System Settings from one published revision.

        The historical method name is retained for internal callers; editable
        draft revisions are never a settings authority and are refused.
        """

        revision = self._config.require(revision_id)
        if revision.status not in {
            ManagedConfigurationStatus.ACTIVE,
            ManagedConfigurationStatus.SUPERSEDED,
        }:
            raise RuntimeSnapshotUnavailable(
                "settings can only be read from a published revision",
                revision_id=revision.revision_id,
                reason="revision_not_published",
            )
        bootstrap_db = self._config.bootstrap_database_path
        return SystemSettings.from_document(
            revision.document,
            revision_id=revision.revision_id,
            revision_version=revision.revision_sequence or revision.version,
            revision_digest=revision.digest,
            draft_version=revision.version,
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
            draft_version=edited.version,
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
            draft_version=edited.version,
            is_active=False,
            bootstrap_database_path=bootstrap_db,
        )

    def publish(
        self,
        *,
        edits: tuple[SystemSettingsEdit, ...],
        actor: str,
        expected_active_revision_id: str | None = None,
        expected_active_version: int | None = None,
        expected_active_digest: str | None = None,
        submission_id: str | None = None,
        before_publish: Callable[[object], object] | None = None,
    ) -> SystemSettings:
        """Apply settings edits and atomically publish the exact successor.

        The previous Active remains authoritative on any validation, permission,
        evidence or persistence failure.  No editable draft survives the call.
        """

        validation_errors = validate_settings_edit(edits, self._config.bootstrap_database_path)
        if validation_errors:
            raise SystemSettingsValidationError(validation_errors)
        active = self._config.active()
        if active is None:
            if self._config.has_managed_activation():
                raise RuntimeSnapshotUnavailable(
                    "managed Active configuration is unavailable",
                    reason="active_missing",
                )
            raise RuntimeSnapshotUnavailable(
                "no Active configuration exists; initialize configuration first",
                reason="active_missing",
            )
        self._config.verify_integrity(active)
        current_version = active.revision_sequence or active.version
        if (
            expected_active_revision_id is not None
            and expected_active_revision_id != active.revision_id
        ):
            raise ConfigurationVersionConflict(
                "Active revision changed; reload Settings before applying changes",
                revision_id=active.revision_id,
                current_version=current_version,
                current_digest=active.digest,
                durable_state="active_preserved",
                next_action="reload the current Active settings, then apply the intended changes",
            )
        if expected_active_version is not None and expected_active_version != current_version:
            raise ConfigurationVersionConflict(
                "Active version changed; reload Settings before applying changes",
                revision_id=active.revision_id,
                current_version=current_version,
                current_digest=active.digest,
                durable_state="active_preserved",
                next_action="reload the current Active settings, then apply the intended changes",
            )
        if expected_active_digest is not None and expected_active_digest != active.digest:
            raise ConfigurationVersionConflict(
                "Active digest changed; reload Settings before applying changes",
                revision_id=active.revision_id,
                current_version=current_version,
                current_digest=active.digest,
                durable_state="active_preserved",
                next_action="reload the current Active settings, then apply the intended changes",
            )
        candidate = apply_settings_edits(dict(active.document), edits)
        _reject_literal_secrets(candidate)
        context = {
            "kind": "system_settings",
            "objectId": "system_settings",
            "action": "settings_apply",
            "submissionId": submission_id,
            "edits": [
                {"field": edit.field_path, "type": type(edit.value).__name__} for edit in edits
            ],
        }
        try:
            published = self._config.publish_document(
                candidate,
                actor=actor,
                expected_active_revision_id=active.revision_id,
                expected_active_version=current_version,
                expected_active_digest=active.digest,
                audit_context=context,
                before_publish=before_publish,
            )
        except Exception as error:
            self._record_outcome(
                actor=actor,
                submission_id=submission_id,
                outcome="not_committed",
                stage="publish",
                next_action="correct the reported condition, then apply the settings again",
                extra={"code": type(error).__name__},
            )
            raise
        return SystemSettings.from_document(
            published.document,
            revision_id=published.revision_id,
            revision_version=published.revision_sequence or published.version,
            revision_digest=published.digest,
            draft_version=published.version,
            is_active=True,
            bootstrap_database_path=self._config.bootstrap_database_path,
        )

    def record_submission_outcome(
        self,
        *,
        actor: str,
        submission_id: str | None,
        stage: str,
        next_action: str,
        kind: str = "system_settings",
        object_id: str = "system_settings",
        action: str = "settings_apply",
        extra: dict[str, object] | None = None,
    ) -> None:
        """Persist a bounded not-committed answer for another managed publish entry.

        Settings, whole-document publication and portable-package import share
        one reconciliation read. When their command refuses before publishing,
        this exact submission must still have a terminal durable answer so a
        lost transport cannot leave the operator permanently blocked.
        """

        self._record_outcome(
            actor=actor,
            submission_id=submission_id,
            outcome="not_committed",
            stage=stage,
            next_action=next_action,
            kind=kind,
            object_id=object_id,
            action=action,
            extra=extra,
        )

    def _record_outcome(
        self,
        *,
        actor: str,
        submission_id: str | None,
        outcome: str,
        stage: str,
        next_action: str,
        kind: str = "system_settings",
        object_id: str = "system_settings",
        action: str = "settings_apply",
        extra: dict[str, object] | None = None,
    ) -> None:
        if not isinstance(submission_id, str) or not submission_id.strip():
            return
        record = getattr(self._config.repository, "record_configuration_audit", None)
        if not callable(record):
            return
        from uuid import uuid4

        from mediaflow.domain.configuration_management import (
            ConfigurationChangeAudit,
            ConfigurationObjectKind,
        )

        try:
            record(
                ConfigurationChangeAudit(
                    str(uuid4()),
                    ConfigurationObjectKind.SYSTEM_SETTINGS,
                    submission_id,
                    "settings_outcome",
                    {},
                    {
                        "objectChange": {
                            "kind": kind,
                            "objectId": object_id,
                            "action": action,
                            "submissionId": submission_id,
                            "outcome": outcome,
                            "stage": stage,
                            "nextAction": next_action,
                            **dict(extra or {}),
                        }
                    },
                    self._config._clock(),
                    actor,
                )
            )
        except Exception:
            return

    def reconcile(
        self,
        *,
        actor: str,
        submission_id: str | None,
    ) -> dict[str, object]:
        """Resolve one identified settings publication without writing.

        The exact actor/submission pair is required; equal current values from
        another writer can never prove that this request published.
        """

        current: dict[str, object] | None = None
        try:
            current = self.read_active().as_projection()
        except Exception:
            current = None
        if not isinstance(submission_id, str) or not submission_id.strip():
            return {
                "state": "UNRESOLVED",
                "committed": False,
                "submissionId": None,
                "current": current,
                "nextAction": (
                    "this request identity is unavailable, so its outcome cannot be proven; "
                    "inspect the current Active settings before applying again"
                ),
                "sideEffects": "none",
            }
        repository = self._config.repository
        latest = getattr(repository, "latest_command_audit_sequence", None)
        before = getattr(repository, "list_command_audits_before", None)
        audits: list[object] = []
        complete = False
        if callable(latest) and callable(before):
            marker = int(latest()) + 1
            try:
                while True:
                    page = before(
                        ("activate", "settings_outcome"), before_sequence=marker, limit=200
                    )
                    audits.extend(page)
                    if len(page) < 200:
                        complete = True
                        break
                    sequences = [int(item.sequence) for item in page if item.sequence is not None]
                    if not sequences:
                        break
                    marker = min(sequences)
            except Exception:
                audits = []
                complete = False
        for audit in audits:
            if audit.actor != actor:
                continue
            change = audit.after.get("objectChange")
            if not isinstance(change, dict):
                continue
            if change.get("submissionId") != submission_id:
                continue
            if audit.action == "settings_outcome":
                return {
                    "state": "NOT_COMMITTED",
                    "committed": False,
                    "submissionId": submission_id,
                    "failureStage": change.get("stage"),
                    "current": current,
                    "nextAction": str(change.get("nextAction") or ""),
                    "sideEffects": "none",
                    "evidenceComplete": complete,
                }
            revision = None
            try:
                revision = self._config.require(str(audit.object_id))
            except Exception:
                revision = None
            if revision is not None and revision.status.value in {"active", "superseded"}:
                return {
                    "state": "COMMITTED" if revision.status.value == "active" else "SUPERSEDED",
                    "committed": True,
                    "submissionId": submission_id,
                    "committedRevisionId": revision.revision_id,
                    "committedRevisionVersion": revision.revision_sequence or revision.version,
                    "current": current,
                    "nextAction": (
                        "this exact submission published and is the current Active settings"
                        if revision.status.value == "active"
                        else "this exact submission published; a later publication is current"
                    ),
                    "sideEffects": "none",
                    "evidenceComplete": complete,
                }
        return {
            "state": "UNRESOLVED",
            "committed": False,
            "submissionId": submission_id,
            "current": current,
            "nextAction": (
                "no terminal durable outcome can be proven for this exact submission; "
                "do not apply again until the current Active and its audit evidence are readable"
            ),
            "sideEffects": "none",
            "evidenceComplete": complete,
        }

    # ------------------------------------------------------------------
    # Consumption evidence
    # ------------------------------------------------------------------

    def consumption_evidence(self) -> dict[str, Any]:
        """Return the exact Active snapshot identity and values consumed by runtime."""

        active = self._config.active()
        if active is None:
            return {
                "consumed": False,
                "reason": "no_active",
                "nextAction": "initialize and publish a configuration revision to consume settings",
            }
        try:
            self._config.verify_integrity(active)
        except RuntimeSnapshotUnavailable as error:
            return {
                "consumed": False,
                "reason": "active_corrupt",
                "message": str(error),
                "nextAction": "inspect configuration status and publish an explicit replacement",
            }
        settings = SystemSettings.from_document(
            active.document,
            revision_id=active.revision_id,
            revision_version=active.revision_sequence or active.version,
            revision_digest=active.digest,
            draft_version=active.version,
            is_active=True,
            bootstrap_database_path=self._config.bootstrap_database_path,
        )
        runtime_snapshot = (
            self._runtime_snapshot_provider() if self._runtime_snapshot_provider else None
        )
        if runtime_snapshot is None:
            return {
                "consumed": False,
                "reason": "runtime_binding_unavailable",
                "revisionId": active.revision_id,
                "revisionVersion": active.revision_sequence or active.version,
                "digest": active.digest,
                "nextAction": "restore the Active runtime binding and refresh readiness",
            }
        if (
            runtime_snapshot.get("snapshotId") != active.revision_id
            or runtime_snapshot.get("digest") != active.digest
        ):
            return {
                "consumed": False,
                "reason": "runtime_snapshot_mismatch",
                "revisionId": active.revision_id,
                "revisionVersion": active.revision_sequence or active.version,
                "digest": active.digest,
                "runtimeSnapshotId": runtime_snapshot.get("snapshotId"),
                "runtimeSnapshotDigest": runtime_snapshot.get("digest"),
                "nextAction": "refresh the runtime binding before treating settings as consumed",
            }
        runtime_values = runtime_snapshot.get("settings") or {}
        expected_values = {
            field_path: settings.as_projection()["settings"][field_path]
            for field_path, boundary in settings.field_boundaries.items()
            if boundary == SystemSettingsBoundary.HOT_CONSUMED
        }
        mismatches = sorted(
            field_path
            for field_path, expected in expected_values.items()
            if runtime_values.get(field_path) != expected
        )
        if mismatches:
            return {
                "consumed": False,
                "reason": "runtime_settings_mismatch",
                "revisionId": active.revision_id,
                "revisionVersion": active.revision_sequence or active.version,
                "digest": active.digest,
                "mismatchedFields": mismatches,
                "nextAction": "reload the exact Active snapshot before reporting readiness",
            }
        return {
            "consumed": True,
            "revisionId": active.revision_id,
            "revisionVersion": active.revision_sequence or active.version,
            "digest": active.digest,
            "runtimeSnapshotId": runtime_snapshot["snapshotId"],
            "runtimeSnapshotDigest": runtime_snapshot["digest"],
            "consumedFields": sorted(expected_values),
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
