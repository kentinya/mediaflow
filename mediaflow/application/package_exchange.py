from __future__ import annotations

import copy
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.configuration_management import (
    ConfigurationVersionConflict,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.package_exchange import (
    CONFIGURATION_PACKAGE_KIND,
    CONFIGURATION_PACKAGE_SCHEMA_VERSION,
    MAX_RESULT_EXPORT_LIMIT,
    REDACTION_EVIDENCE_LIMIT,
    RESULT_PACKAGE_KIND,
    RESULT_PACKAGE_SCHEMA_VERSION,
    PackageExchangeError,
    build_configuration_package,
    canonical_digest,
    package_redaction_sweep,
    redact_result_rows,
    result_redaction_entries,
    validate_configuration_package,
)
from mediaflow.domain.security import SecurityAuditRecord


class PackageExchangeService:
    """Shared export/import behavior for RO-4 package exchange.

    The service only reads durable configuration/revision and Task/Result
    repositories. It never reads media, contacts Providers/Storage, starts
    workflow work, mutates Storage or changes Active. Configuration import
    delegates Draft creation/editing to the managed revision authority.
    """

    def __init__(
        self,
        configuration_service,
        task_repository=None,
        *,
        audit_repository=None,
        clock=None,
    ) -> None:
        self._configuration = configuration_service
        self._task_repository = task_repository
        self._audit_repository = task_repository if audit_repository is None else audit_repository
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def configuration_service(self):
        return self._configuration

    @property
    def task_repository(self):
        return self._task_repository

    def status_document(self) -> dict[str, object]:
        if self._configuration is None:
            raise PackageExchangeError(
                "configuration package exchange is unavailable",
                code="service_unavailable",
                status=503,
                durable_state="no_package_state_changed",
                next_action="restore the managed configuration service, then retry",
            )
        try:
            active = self._configuration.active()
            revisions = self._configuration.repository.list_revisions(limit=500)
        except RuntimeSnapshotUnavailable as error:
            raise PackageExchangeError(
                "managed Active configuration is unavailable for package exchange",
                code="configuration_unavailable",
                status=503,
                durable_state="managed_active_unavailable",
                next_action="inspect configuration status and restore a valid Active revision",
                details={
                    "reason": getattr(error, "reason", "active_missing"),
                    "revisionId": getattr(error, "revision_id", None),
                    "digest": getattr(error, "digest", None),
                },
            ) from error
        current_draft = next(
            (
                revision
                for revision in revisions
                if revision.status
                in {ManagedConfigurationStatus.DRAFT, ManagedConfigurationStatus.VALIDATED}
            ),
            None,
        )
        return {
            "exchangeAvailable": True,
            "packageKinds": {
                "configuration": CONFIGURATION_PACKAGE_KIND,
                "results": RESULT_PACKAGE_KIND,
            },
            "configurationPackageSchemaVersion": CONFIGURATION_PACKAGE_SCHEMA_VERSION,
            "resultPackageSchemaVersion": RESULT_PACKAGE_SCHEMA_VERSION,
            "packageVersion": 1,
            "currentActive": active.summary() if active is not None else None,
            "currentDraft": current_draft.summary() if current_draft is not None else None,
            "supportedRevisionStatuses": [
                status.value
                for status in (
                    ManagedConfigurationStatus.DRAFT,
                    ManagedConfigurationStatus.VALIDATED,
                    ManagedConfigurationStatus.ACTIVE,
                    ManagedConfigurationStatus.SUPERSEDED,
                )
            ],
            "resultExport": {
                "scope": "task",
                "ordering": "created_at_asc,result_id_asc",
                "limitMaximum": MAX_RESULT_EXPORT_LIMIT,
                "source": "durable_task_result_repository",
            },
            "importBehavior": {
                "createsNewDraft": True,
                "updatesExactDraft": "explicit recovery identity required",
                "neverActivates": True,
                "sideEffects": "none",
                "currentDraftOverwrite": "forbidden_without_exact_identity",
            },
            "nextAction": (
                "export the Active or an explicit revision as a Draft/recovery package, "
                "or import a supported package after confirming current Active identity"
            ),
        }

    def export_configuration(
        self,
        *,
        actor: str,
        revision_id: str | None = None,
    ) -> dict[str, object]:
        if self._configuration is None:
            raise PackageExchangeError(
                "configuration package exchange is unavailable",
                code="service_unavailable",
                status=503,
                durable_state="no_package_state_changed",
                next_action="restore the managed configuration service, then retry",
            )
        now = self._clock()
        if revision_id:
            try:
                revision = self._configuration.require(revision_id)
            except LookupError as error:
                raise PackageExchangeError(
                    "configuration revision was not found for package export",
                    code="revision_not_found",
                    status=404,
                    durable_state="no_package_state_changed",
                    next_action="refresh configuration status and select an existing revision",
                ) from error
        else:
            try:
                revision = self._configuration.active()
            except RuntimeSnapshotUnavailable as error:
                raise PackageExchangeError(
                    "managed Active configuration is unavailable for export",
                    code="configuration_unavailable",
                    status=503,
                    durable_state="managed_active_unavailable",
                    next_action="restore or activate a valid managed configuration revision",
                    details={
                        "revisionId": getattr(error, "revision_id", None),
                        "digest": getattr(error, "digest", None),
                    },
                ) from error
            if revision is None:
                raise PackageExchangeError(
                    "no Active configuration exists; export an explicit managed revision",
                    code="active_missing",
                    status=503,
                    durable_state="no_active_configuration",
                    next_action="activate a managed configuration revision before package export",
                )
        self._configuration.verify_integrity(revision)
        try:
            active = self._configuration.active()
        except RuntimeSnapshotUnavailable as error:
            raise PackageExchangeError(
                "current Active configuration is unavailable while exporting",
                code="configuration_unavailable",
                status=503,
                durable_state="managed_active_unavailable",
                next_action="restore a valid Active revision, then retry package export",
            ) from error
        package = build_configuration_package(revision, active, generated_at=now)
        package = package_redaction_sweep(package)
        self._audit(
            actor=actor,
            action="configuration_package_export",
            outcome="allowed",
            route="/api/v1/configuration/packages/export/configuration",
            status=200,
            revision_id=revision.revision_id,
        )
        return package

    def export_results(
        self,
        *,
        actor: str,
        task_id: str,
        limit: int = 100,
    ) -> dict[str, object]:
        repository = self._task_repository
        if repository is None:
            raise PackageExchangeError(
                "result package export is unavailable",
                code="service_unavailable",
                status=503,
                durable_state="no_package_state_changed",
                next_action="restore the durable Task/Result repository, then retry",
            )
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise PackageExchangeError(
                f"result export limit must be between 1 and {MAX_RESULT_EXPORT_LIMIT}",
                code="invalid_limit",
                status=422,
                durable_state="no_package_state_changed",
                next_action="retry with a bounded result limit",
            )
        try:
            task = repository.get_task(task_id)
        except Exception as error:
            raise PackageExchangeError(
                "Task/Result repository could not read the requested Task",
                code="result_repository_unavailable",
                status=503,
                durable_state="no_package_state_changed",
                retry_safe=True,
                next_action="check the durable repository and retry result export",
            ) from error
        if task is None:
            raise PackageExchangeError(
                "task was not found for result package export",
                code="task_not_found",
                status=404,
                durable_state="no_package_state_changed",
                next_action="refresh the Task list and choose an existing Task ID",
            )
        try:
            fetched = repository.list_results(task_id, limit=limit + 1)
        except Exception as error:
            raise PackageExchangeError(
                "Task/Result repository could not read results",
                code="result_repository_unavailable",
                status=503,
                durable_state="no_package_state_changed",
                retry_safe=True,
                next_action="check the durable repository and retry result export",
            ) from error
        truncated = len(fetched) > limit
        values = fetched[:limit]
        rows = redact_result_rows(values)
        redaction_entries = result_redaction_entries(values)
        package = {
            "packageKind": RESULT_PACKAGE_KIND,
            "packageSchemaVersion": RESULT_PACKAGE_SCHEMA_VERSION,
            "packageVersion": 1,
            "generatedAt": self._clock().isoformat(),
            "producer": {"id": "mediaflow"},
            "source": {
                "scope": "task",
                "taskId": task_id,
                "taskCommand": task.command,
                "ordering": "created_at_asc,result_id_asc",
                "limit": limit,
            },
            "redaction": {
                "scope": "persisted_task_result_projection",
                "entryCount": len(redaction_entries),
                "entries": redaction_entries,
            },
            "results": rows,
            "truncated": truncated,
            "warning": (
                [
                    {
                        "code": "results_truncated",
                        "message": (
                            "the requested result scope exceeds this package limit; "
                            "export again with a larger bounded limit or a narrower scope"
                        ),
                    }
                ]
                if truncated
                else []
            ),
        }
        # Run the final secret-free projection before computing the digest so
        # packageDigest covers exactly the results/source returned to the
        # caller. A secret-shaped Task command is redacted by this sweep, so
        # record that change in the bounded redaction evidence as well.
        package = package_redaction_sweep(package)
        if package["source"]["taskCommand"] != task.command:
            entries = [
                *package["redaction"]["entries"],
                {"field": "source.taskCommand", "kind": "redacted_text"},
            ][:REDACTION_EVIDENCE_LIMIT]
            package["redaction"] = {
                "scope": package["redaction"]["scope"],
                "entryCount": len(entries),
                "entries": entries,
            }
        package["packageDigest"] = canonical_digest(
            {"results": package["results"], "source": package["source"]}
        )
        self._audit(
            actor=actor,
            action="result_package_export",
            outcome="allowed",
            route="/api/v1/configuration/packages/export/results",
            status=200,
            revision_id=None,
            task_id=task_id,
        )
        return package

    def import_configuration(
        self,
        package_value: object,
        *,
        actor: str,
        recovery: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if self._configuration is None:
            raise PackageExchangeError(
                "configuration package import is unavailable",
                code="service_unavailable",
                status=503,
                durable_state="no_configuration_changed",
                next_action="restore the managed configuration service, then retry",
            )
        parsed = validate_configuration_package(package_value)
        try:
            active = self._configuration.active()
        except RuntimeSnapshotUnavailable as error:
            raise PackageExchangeError(
                "managed Active configuration is unavailable; import is fail-closed",
                code="configuration_unavailable",
                status=503,
                durable_state="managed_active_unavailable_no_draft_change",
                next_action="restore a valid Active revision, then retry package import",
                details={
                    "revisionId": getattr(error, "revision_id", None),
                    "digest": getattr(error, "digest", None),
                },
            ) from error
        if active is None:
            raise PackageExchangeError(
                "no Active configuration exists; package import is fail-closed",
                code="active_missing",
                status=503,
                durable_state="no_active_configuration_no_draft_change",
                next_action="activate a managed configuration revision before package import",
            )
        self._configuration.verify_integrity(active)
        currentness = parsed["currentness"]
        if (
            currentness.get("currentActiveRevisionId") != active.revision_id
            or currentness.get("currentActiveDigest") != active.digest
        ):
            current_draft = self._current_draft()
            raise PackageExchangeError(
                "configuration package was exported from a different Active revision",
                code="package_stale",
                status=409,
                durable_state="active_preserved_no_draft_change",
                next_action=(
                    "export the current Active revision, or create a successor Draft from "
                    "the current Active and reapply the desired change"
                ),
                details={
                    "currentActive": active.summary(),
                    "currentDraft": current_draft.summary() if current_draft else None,
                    "packageActive": {
                        "revisionId": currentness.get("currentActiveRevisionId"),
                        "digest": currentness.get("currentActiveDigest"),
                    },
                },
            )
        recovery = recovery or {}
        if not isinstance(recovery, dict):
            raise PackageExchangeError(
                "package import recovery authority must be an object",
                code="invalid_authority",
                status=422,
                durable_state="no_configuration_changed",
                next_action="repeat the import with the exact current Draft identity",
            )
        current_draft = self._current_draft()
        document = copy.deepcopy(parsed["document"])
        if current_draft is not None:
            expected_id = recovery.get("expectedRevisionId")
            expected_version = recovery.get("expectedVersion")
            expected_digest = recovery.get("expectedDigest")
            replace_draft = recovery.get("replaceDraft") is True
            if (
                not replace_draft
                or expected_id != current_draft.revision_id
                or not isinstance(expected_version, int)
                or expected_version != current_draft.version
                or expected_digest != current_draft.digest
            ):
                raise PackageExchangeError(
                    "configuration import cannot silently overwrite the current Draft",
                    code="package_import_draft_conflict",
                    status=409,
                    durable_state="current_draft_preserved_active_unchanged",
                    next_action=(
                        "open the current Draft, or repeat import with replaceDraft=true and "
                        "the exact current Draft revision/version/digest"
                    ),
                    details={
                        "currentActive": active.summary(),
                        "currentDraft": current_draft.summary(),
                    },
                )
            try:
                updated = self._configuration.edit_draft(
                    current_draft.revision_id,
                    document,
                    expected_version=current_draft.version,
                    actor=actor,
                )
            except ConfigurationVersionConflict as error:
                refreshed = self._current_draft()
                raise PackageExchangeError(
                    "configuration Draft changed before package import could update it",
                    code="package_import_draft_conflict",
                    status=409,
                    durable_state="current_draft_preserved_active_unchanged",
                    next_action="refresh the Draft and repeat the exact recovery identity",
                    details={
                        "currentActive": active.summary(),
                        "currentDraft": refreshed.summary() if refreshed else None,
                    },
                ) from error
            except (ValueError, RuntimeError) as error:
                raise PackageExchangeError(
                    "package import was rejected by managed configuration rules",
                    code="package_import_validation_failed",
                    status=422,
                    durable_state="current_draft_preserved_active_unchanged",
                    next_action="correct the configuration package and retry",
                    details={"error": str(error)[:500]},
                ) from error
            result: dict[str, object] = {
                "imported": True,
                "action": "updated",
                "revision": updated.summary(),
                "sideEffects": "draft_only",
                "retrySafe": True,
                "nextAction": (
                    "open the updated Draft, run validation, then use checked activation"
                ),
            }
        else:
            if recovery:
                raise PackageExchangeError(
                    "recovery authority was supplied but no current Draft exists",
                    code="no_current_draft",
                    status=409,
                    durable_state="active_preserved_no_draft_created",
                    next_action="repeat the import without recovery authority",
                    details={"currentActive": active.summary()},
                )
            try:
                created = self._configuration.import_draft(
                    document,
                    actor=actor,
                    source="package_import",
                )
            except (ValueError, RuntimeError) as error:
                raise PackageExchangeError(
                    "package import was rejected by managed configuration rules",
                    code="package_import_validation_failed",
                    status=422,
                    durable_state="no_configuration_changed",
                    next_action="correct the configuration package and retry",
                    details={"error": str(error)[:500]},
                ) from error
            result = {
                "imported": True,
                "action": "created",
                "revision": created.summary(),
                "sideEffects": "draft_only",
                "retrySafe": True,
                "nextAction": (
                    "open the imported Draft/recovery candidate, run validation, "
                    "then use checked activation"
                ),
            }
        result["currentActive"] = active.summary()
        result["currentDraft"] = (
            result["revision"] if isinstance(result["revision"], dict) else None
        )
        self._audit(
            actor=actor,
            action="configuration_package_import",
            outcome="allowed",
            route="/api/v1/configuration/packages",
            status=201 if result["action"] == "created" else 200,
            revision_id=str(result["revision"].get("revisionId")),
        )
        return result

    def _current_draft(self) -> ManagedConfigurationRevision | None:
        revisions = self._configuration.repository.list_revisions(limit=500)
        return next(
            (
                revision
                for revision in revisions
                if revision.status
                in {ManagedConfigurationStatus.DRAFT, ManagedConfigurationStatus.VALIDATED}
            ),
            None,
        )

    def _audit(
        self,
        *,
        actor: str,
        action: str,
        outcome: str,
        route: str,
        status: int,
        revision_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        repository = getattr(self._audit_repository, "append_security_audit", None)
        if not callable(repository):
            return
        route_value = route
        if revision_id:
            route_value = f"{route}?revisionId={revision_id}"
        if task_id:
            route_value = f"{route}?taskId={task_id}"
        try:
            repository(
                SecurityAuditRecord(
                    str(uuid4()),
                    self._clock(),
                    actor,
                    "GET" if outcome == "allowed" else "POST",
                    route_value[:500],
                    action,
                    outcome,
                    status,
                    str(uuid4()),
                    None,
                )
            )
        except Exception:
            # The API transport also records request audits.  A best-effort
            # application audit must never echo secret-bearing package data.
            return
