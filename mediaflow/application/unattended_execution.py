"""Application authority for persistent scheduled organization grants."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.automation import AutomationTaskDefinition, AutomationTaskRunMode
from mediaflow.domain.manual_organize_preview import (
    ManualOrganizePreview,
    ManualPreviewItemStatus,
    ManualPreviewStatus,
)
from mediaflow.domain.manual_safety import redact_evidence_text, redact_evidence_value
from mediaflow.domain.security import ApiPermission
from mediaflow.domain.unattended_execution import (
    MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH,
    MAX_UNATTENDED_GRANT_REASON_LENGTH,
    CurrentPermissionAuthority,
    UnattendedExecutionGrant,
    UnattendedExecutionGrantAudit,
    UnattendedExecutionGrantRepository,
    UnattendedExecutionGrantStatus,
)


class UnattendedExecutionGrantError(ValueError):
    """Bounded, operator-actionable grant or authority error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "unattended_execution_grant_rejected",
        status: int = 409,
        durable_state: str = "no media mutation occurred",
        retry_safe: bool = True,
        next_action: str = "inspect the grant state and explicitly correct the stated condition",
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.durable_state = _bounded(durable_state, 256, "durable state")
        self.retry_safe = retry_safe
        self.next_action = _bounded(next_action, 512, "next action")
        self.details = dict(details or {})


class UnattendedExecutionBoundaryError(RuntimeError):
    """A live grant disappeared or changed at one per-item mutation boundary."""

    def __init__(
        self,
        *,
        category: str,
        reason: str,
        next_action: str,
        retry_safe: bool = True,
    ) -> None:
        self.category = _bounded(category, 96, "grant boundary category")
        self.reason = _bounded(reason, 256, "grant boundary reason")
        self.next_action = _bounded(next_action, 512, "grant boundary next action")
        self.retry_safe = retry_safe
        self.durable_state = "completed sibling effects are preserved; this item was not mutated"
        super().__init__(self.safe_message)

    @property
    def safe_message(self) -> str:
        return redact_evidence_text(
            f"{self.category}: {self.reason}; next action: {self.next_action}",
            limit=1000,
        )


@dataclass(frozen=True)
class UnattendedExecutionAuthority:
    """The exact grant admitted for one claimed occurrence."""

    grant: UnattendedExecutionGrant
    definition_changed_since_grant: bool = False


class UnattendedExecutionGrantService:
    """Grant/revoke and live authority checks over one repository boundary."""

    _MAX_DEFINITION_IDS_PER_READ = 100

    def __init__(
        self,
        repository: UnattendedExecutionGrantRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], str] = lambda: str(uuid4()),
        discovery_service=None,
        preview_service=None,
        permission_authority: CurrentPermissionAuthority | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._id_factory = id_factory
        self._discovery_service = discovery_service
        self._preview_service = preview_service
        self._permission_authority = permission_authority

    @property
    def repository(self):
        return self._repository

    def grant(
        self,
        definition,
        *,
        configuration_snapshot_id: str,
        configuration_snapshot_digest: str,
        configuration_snapshot_version: int,
        actor: str | None = None,
        principal=None,
        max_items_per_run: int | None = None,
        max_items: int | None = None,
        confirmation: bool = False,
        confirmed: bool | None = None,
        reason: str | None = None,
        storage_id: str | None = None,
    ) -> UnattendedExecutionGrant:
        self._require_permission(principal)
        try:
            actor = _actor(actor, principal)
        except (TypeError, ValueError) as error:
            raise self._invalid("granting principal is invalid") from error
        if self._permission_authority is not None:
            self._assert_current_permission(actor, boundary=False)
        if confirmed is not None:
            if confirmation and confirmation != confirmed:
                raise self._invalid("grant confirmation was specified twice")
            confirmation = confirmed
        if confirmation is not True:
            raise self._invalid(
                "explicit grant confirmation is required",
                next_action="review the exact definition bounds and confirm unattended execution",
            )
        try:
            definition = _definition(definition)
        except (TypeError, ValueError) as error:
            raise self._invalid("Automation Task Definition is invalid") from error
        if definition.mode is not AutomationTaskRunMode.AUTOMATIC_ORGANIZATION:
            raise self._invalid(
                "unattended execution grants require automatic-organization mode",
                next_action="change the definition to automatic-organization and activate it",
            )
        if max_items is not None:
            if max_items_per_run is not None and max_items != max_items_per_run:
                raise self._invalid("maxItemsPerRun was specified twice")
            max_items_per_run = max_items
        if max_items_per_run is None:
            max_items_per_run = definition.item_limit
        if (
            isinstance(max_items_per_run, bool)
            or not isinstance(max_items_per_run, int)
            or not 1 <= max_items_per_run <= definition.item_limit
        ):
            raise self._invalid(
                f"grant maxItemsPerRun must be between 1 and {definition.item_limit}",
                next_action="choose a workload bound no greater than the definition item limit",
            )
        try:
            snapshot_id = _bounded(configuration_snapshot_id, 128, "configuration snapshot ID")
            snapshot_digest = _sha(configuration_snapshot_digest, "configuration snapshot digest")
            snapshot_version = _version(
                configuration_snapshot_version, "configuration snapshot version"
            )
            reason = _reason(reason)
        except (TypeError, ValueError) as error:
            raise self._invalid("grant configuration evidence is invalid") from error
        # An unattended grant authorizes real, repeated media mutation.  It may
        # only be admitted over a real, persisted zero-mutation analysis of the
        # exact published definition scope and bounds: the definition-bound Run
        # once's frozen manifest with its linked exact organize Preview.  Without
        # that shared analysis there is no evidence the exact bounds, source
        # scope, configuration pin and workload bound were ever analyzed, so the
        # grant is refused before any grant row, audit or media effect.
        self._require_shared_analysis(
            definition,
            configuration_snapshot_id=snapshot_id,
            configuration_snapshot_digest=snapshot_digest,
            configuration_snapshot_version=snapshot_version,
            max_items_per_run=max_items_per_run,
            storage_id=storage_id,
        )
        now = self._clock()
        value = UnattendedExecutionGrant(
            self._id_factory(),
            definition.definition_id,
            definition.resource_library_id,
            definition.source_scope,
            definition.mode,
            max_items_per_run,
            UnattendedExecutionGrantStatus.ACTIVE,
            actor,
            now,
            definition.definition_fingerprint,
            snapshot_id,
            snapshot_digest,
            snapshot_version,
            reason=reason,
        )
        existing = self._latest_for_definition(definition.definition_id)
        if existing is not None and existing.status is UnattendedExecutionGrantStatus.ACTIVE:
            if _grant_binding(existing) == _grant_binding(value):
                return existing
            raise UnattendedExecutionGrantError(
                "an active unattended grant already exists for different exact bounds",
                code="unattended_execution_grant_already_active",
                next_action="revoke the existing grant, review the new bounds, and grant again",
                details={"grantId": existing.grant_id, "definitionId": definition.definition_id},
            )
        audit = UnattendedExecutionGrantAudit(
            self._id_factory(),
            value.grant_id,
            "granted",
            now,
            actor,
            {
                "definitionId": value.definition_id,
                "resourceLibraryId": value.resource_library_id,
                "sourceScope": value.source_scope,
                "runMode": value.run_mode.value,
                "maxItemsPerRun": value.max_items_per_run,
                "configurationSnapshotId": value.configuration_snapshot_id,
                "configurationSnapshotDigest": value.configuration_snapshot_digest,
                "configurationSnapshotVersion": value.configuration_snapshot_version,
            },
        )
        creator = getattr(self._repository, "create_unattended_execution_grant", None)
        if not callable(creator):
            creator = getattr(self._repository, "create_unattended_grant")
        try:
            creator(value, audit)
        except Exception as error:
            # A concurrent process may have committed an active grant after
            # the read above.  Surface that race as the same bounded conflict
            # rather than leaking a database integrity error.
            concurrent = self._get_active(definition.definition_id)
            if concurrent is not None:
                if _grant_binding(concurrent) == _grant_binding(value):
                    return concurrent
                raise UnattendedExecutionGrantError(
                    "an active unattended grant already exists for different exact bounds",
                    code="unattended_execution_grant_already_active",
                    next_action="revoke the existing grant, review the new bounds, and grant again",
                    details={
                        "grantId": concurrent.grant_id,
                        "definitionId": definition.definition_id,
                    },
                ) from error
            raise
        return value

    def revoke(
        self,
        grant_id: str | None = None,
        *,
        definition_id: str | None = None,
        actor: str | None = None,
        principal=None,
        reason: str | None = None,
    ) -> UnattendedExecutionGrant:
        self._require_permission(principal)
        try:
            actor = _actor(actor, principal)
        except (TypeError, ValueError) as error:
            raise self._invalid("revoking principal is invalid") from error
        if (grant_id is None) == (definition_id is None):
            raise self._invalid("provide exactly one grantId or definitionId")
        if definition_id is not None:
            try:
                definition_id = _bounded(definition_id, 128, "definition ID")
            except (TypeError, ValueError) as error:
                raise self._invalid("definition ID is invalid") from error
            current = self._latest_for_definition(definition_id)
        else:
            try:
                grant_id = _bounded(grant_id, 128, "grant ID")
            except (TypeError, ValueError) as error:
                raise self._invalid("grant ID is invalid") from error
            current = self._get(grant_id)
        if current is None:
            raise LookupError(
                f"unattended execution grant {grant_id or definition_id!r} was not found"
            )
        if current.status is UnattendedExecutionGrantStatus.REVOKED:
            return current
        now = self._clock()
        try:
            reason = _reason(reason)
        except (TypeError, ValueError) as error:
            raise self._invalid("revoke reason is invalid") from error
        audit = UnattendedExecutionGrantAudit(
            self._id_factory(),
            current.grant_id,
            "revoked",
            now,
            actor,
            {"reason": reason} if reason is not None else {},
        )
        revoker = getattr(self._repository, "revoke_unattended_execution_grant", None)
        if not callable(revoker):
            revoker = getattr(self._repository, "revoke_unattended_grant")
        return revoker(
            current.grant_id,
            now,
            audit,
            revoking_principal=actor,
            reason=reason,
        )

    def get(self, grant_id: str) -> UnattendedExecutionGrant | None:
        return self._get(_bounded(grant_id, 128, "grant ID"))

    def get_for_definition(self, definition_id: str) -> UnattendedExecutionGrant | None:
        return self._current_for_definition(_bounded(definition_id, 128, "definition ID"))

    def list(
        self,
        *,
        definition_id: str | None = None,
        limit: int = 100,
    ) -> tuple[UnattendedExecutionGrant, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("unattended execution grant limit must be between 1 and 100")
        ids = None
        if definition_id is not None:
            ids = (_bounded(definition_id, 128, "definition ID"),)
        return self._list(definition_ids=ids, limit=limit)

    def list_audit(self, grant_id: str, *, limit: int = 100):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("unattended execution grant audit limit must be between 1 and 100")
        getter = getattr(self._repository, "list_unattended_execution_grant_audit", None)
        if not callable(getter):
            getter = getattr(self._repository, "list_unattended_grant_audit", None)
        if not callable(getter):
            return ()
        return getter(_bounded(grant_id, 128, "grant ID"), limit=limit)

    def authorize(self, job, definition) -> UnattendedExecutionAuthority:
        definition = _definition(definition)
        grant = self._get_active(definition.definition_id)
        if grant is None:
            latest = self._latest_for_definition(definition.definition_id)
            if latest is not None and latest.status is UnattendedExecutionGrantStatus.REVOKED:
                raise UnattendedExecutionGrantError(
                    "unattended execution grant is revoked",
                    code="unattended_execution_grant_revoked",
                    next_action=(
                        "review completed history and explicitly grant the exact bounds again"
                    ),
                )
            raise UnattendedExecutionGrantError(
                "automatic organization has no active unattended execution grant; "
                "no Task was created",
                code="unattended_execution_authority_missing",
                durable_state="no Task, adapter, Provider request, or media effect was created",
                next_action=(
                    "review the exact definition bounds and explicitly grant unattended execution"
                ),
                details={"definitionId": definition.definition_id},
            )
        self._assert_match(grant, job, definition)
        self._assert_current_permission(grant.granting_principal, boundary=False)
        return UnattendedExecutionAuthority(
            grant,
            _definition_changed_since_grant(grant, definition),
        )

    def assert_live(self, job, definition) -> UnattendedExecutionGrant:
        """Re-read and validate the grant at one mutation boundary."""

        definition = _definition(definition)
        grant = self._get_active(definition.definition_id)
        try:
            if grant is None:
                raise UnattendedExecutionGrantError(
                    "unattended execution grant is no longer active",
                    code="unattended_execution_grant_revoked",
                    next_action=(
                        "inspect the completed siblings and explicitly grant the exact bounds again"
                    ),
                )
            self._assert_match(grant, job, definition)
            self._assert_current_permission(grant.granting_principal, boundary=True)
        except UnattendedExecutionGrantError as error:
            raise UnattendedExecutionBoundaryError(
                category=error.code,
                reason=str(error),
                next_action=error.next_action,
                retry_safe=error.retry_safe,
            ) from error
        return grant

    def _assert_current_permission(self, principal_id: str, *, boundary: bool) -> None:
        if self._permission_authority is None:
            # Lightweight direct callers from the pre-managed runtime do not
            # have a configured authority to consult. Production API/Worker
            # composition always injects one and therefore fails closed.
            return
        try:
            allowed = self._permission_authority.has_permission(
                principal_id, ApiPermission.GRANT_UNATTENDED_EXECUTION
            )
        except Exception:
            error = UnattendedExecutionGrantError(
                "current configured principal permission authority could not be read",
                code="unattended_permission_authority_unavailable",
                status=503,
                durable_state=(
                    "no Task, adapter, Provider request, Storage probe, or media effect was created"
                ),
                next_action=(
                    "restore the current permission authority, then explicitly resume the "
                    "occurrence"
                ),
            )
            if not boundary:
                raise error from error
            raise UnattendedExecutionBoundaryError(
                category="unattended_permission_authority_unavailable",
                reason="current configured principal permission authority could not be read",
                next_action=(
                    "restore the current permission authority, then explicitly resume the "
                    "occurrence"
                ),
            ) from error
        if allowed is not True:
            error = UnattendedExecutionGrantError(
                "the granting principal no longer has grant_unattended_execution permission",
                code="unattended_permission_invalid",
                durable_state=(
                    "no Task, adapter, Provider request, Storage probe, or media effect was created"
                ),
                next_action="restore that principal permission or explicitly create a new grant",
            )
            if not boundary:
                raise error
            raise UnattendedExecutionBoundaryError(
                category="unattended_permission_invalid",
                reason="the granting principal no longer has grant_unattended_execution permission",
                next_action="restore that principal permission or explicitly create a new grant",
            ) from error

    def project_eligibility(
        self,
        definition,
        *,
        configuration_snapshot_id: str,
        configuration_snapshot_digest: str,
        configuration_snapshot_version: int,
        storage_id: str | None,
        max_items_per_run: int | None = None,
        principal_id: str | None = None,
    ) -> dict[str, object]:
        """Project the exact, shared admission decision for API and Web.

        This is deliberately a read-only projection.  It performs the same
        bounded Preview and current-authority checks as grant admission while
        never writing a grant, audit row, Task, or Storage effect.
        """

        try:
            definition = _definition(definition)
            if definition.mode is not AutomationTaskRunMode.AUTOMATIC_ORGANIZATION:
                raise self._invalid(
                    "unattended execution grants require automatic-organization mode",
                    next_action="change the definition to automatic-organization and activate it",
                )
            if max_items_per_run is None:
                max_items_per_run = definition.item_limit
            if (
                isinstance(max_items_per_run, bool)
                or not isinstance(max_items_per_run, int)
                or not 1 <= max_items_per_run <= definition.item_limit
            ):
                raise self._invalid(
                    f"grant maxItemsPerRun must be between 1 and {definition.item_limit}",
                    next_action="choose a workload bound no greater than the definition item limit",
                )
            for label, value, maximum in (
                ("configuration snapshot id", configuration_snapshot_id, 128),
                ("configuration snapshot digest", configuration_snapshot_digest, 64),
            ):
                if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                    raise self._invalid(f"{label} is invalid")
            _version(configuration_snapshot_version, "configuration snapshot version")
            if (
                principal_id is None
                or not isinstance(principal_id, str)
                or not principal_id.strip()
            ):
                raise UnattendedExecutionGrantError(
                    "a current granting principal is required for eligibility",
                    code="unattended_permission_invalid",
                    status=403,
                    durable_state="no grant or media mutation occurred",
                    next_action=(
                        "authenticate as an enabled principal with "
                        "grant_unattended_execution permission"
                    ),
                )
            if self._permission_authority is None:
                raise UnattendedExecutionGrantError(
                    "current configured principal permission authority could not be read",
                    code="unattended_permission_authority_unavailable",
                    status=503,
                    durable_state="no grant or media mutation occurred",
                    next_action="restore the current permission authority, then reload eligibility",
                )
            self._assert_current_permission(principal_id, boundary=False)
            # The same shared analysis requirement the durable grant enforces:
            # an unattended grant may only be admitted over a real, persisted
            # zero-mutation analysis of the exact definition scope and bounds.  A
            # stale or mismatched analysis is refused here exactly as at grant,
            # but only after the current authority is proven valid.
            analysis_error = self._validate_shared_analysis(
                definition,
                configuration_snapshot_id=configuration_snapshot_id,
                configuration_snapshot_digest=configuration_snapshot_digest,
                configuration_snapshot_version=configuration_snapshot_version,
                max_items_per_run=max_items_per_run,
                storage_id=storage_id,
            )
            if analysis_error is not None:
                raise analysis_error
        except UnattendedExecutionGrantError as error:
            return self._eligibility_failure(error)
        return {
            "eligible": True,
            "status": "eligible",
            "maxItemsPerRun": max_items_per_run,
            "currentPermission": {
                "principalId": principal_id,
                "status": "valid",
                "allowed": True,
            },
            "explanation": (
                "the exact definition bounds and current granting-principal permission "
                "satisfy the persisted grant bounds"
            ),
            "durableState": "no grant or media mutation has been created",
            "retrySafe": True,
            "nextAction": "review the exact bounds and explicitly confirm the unattended grant",
            "error": None,
        }

    @staticmethod
    def _eligibility_failure(error: UnattendedExecutionGrantError) -> dict[str, object]:
        details = redact_evidence_value(dict(error.details))
        return {
            "eligible": False,
            "status": "ineligible",
            "currentPermission": None,
            "explanation": redact_evidence_text(str(error), limit=512),
            "durableState": error.durable_state,
            "retrySafe": error.retry_safe,
            "nextAction": error.next_action,
            "error": {
                "code": error.code,
                "status": error.status,
                "message": redact_evidence_text(str(error), limit=512),
                "durableState": error.durable_state,
                "retrySafe": error.retry_safe,
                "nextAction": error.next_action,
                "details": details,
            },
        }

    def project(
        self,
        definition,
        *,
        configuration: Mapping[str, object] | None = None,
        grant: UnattendedExecutionGrant | None = None,
    ) -> dict[str, object]:
        definition = _definition(definition)
        grant = grant if grant is not None else self.get_for_definition(definition.definition_id)
        if grant is None:
            return {
                "status": "none",
                "active": False,
                "grantId": None,
                "definitionId": definition.definition_id,
                "definitionChangedSinceGrant": False,
                "nextAction": (
                    "review the exact definition bounds and explicitly grant unattended execution"
                ),
            }
        changed = _definition_changed_since_grant(grant, definition) or (
            configuration is not None
            and (
                configuration.get("revisionId") != grant.configuration_snapshot_id
                or configuration.get("digest") != grant.configuration_snapshot_digest
                or configuration.get("version") not in {None, grant.configuration_snapshot_version}
            )
        )
        if grant.status is UnattendedExecutionGrantStatus.REVOKED:
            next_action = (
                "review the exact definition bounds and explicitly grant unattended execution again"
            )
        elif changed:
            next_action = (
                "the definition changed since grant; review the new bounds and "
                "explicitly grant again"
            )
        else:
            next_action = (
                "inspect the next occurrence or revoke this grant before changing its exact bounds"
            )
        value = grant.document()
        value.update(
            {
                "definitionChangedSinceGrant": changed,
                "nextAction": next_action,
                "definitionCurrentFingerprint": definition.definition_fingerprint,
                "currentPermission": self._permission_projection(grant),
            }
        )
        return value

    def _permission_projection(self, grant) -> dict[str, object]:
        if self._permission_authority is None:
            return {
                "principalId": grant.granting_principal,
                "status": "unavailable",
                "allowed": False,
            }
        try:
            allowed = self._permission_authority.has_permission(
                grant.granting_principal, ApiPermission.GRANT_UNATTENDED_EXECUTION
            )
        except Exception:
            return {
                "principalId": grant.granting_principal,
                "status": "unavailable",
                "allowed": False,
            }
        return {
            "principalId": grant.granting_principal,
            "status": "valid" if allowed is True else "invalid",
            "allowed": allowed is True,
        }

    def project_many(
        self,
        definitions: Iterable,
        *,
        configuration: Mapping[str, object] | None = None,
    ) -> dict[str, dict[str, object]]:
        values = tuple(definitions)
        ids = tuple(_definition(value).definition_id for value in values)
        grants = {}
        unique_ids = tuple(dict.fromkeys(ids))
        for offset in range(0, len(unique_ids), self._MAX_DEFINITION_IDS_PER_READ):
            chunk = unique_ids[offset : offset + self._MAX_DEFINITION_IDS_PER_READ]
            for value in self._list(
                definition_ids=chunk,
                limit=self._MAX_DEFINITION_IDS_PER_READ,
            ):
                current = grants.get(value.definition_id)
                if _prefer_grant(value, current):
                    grants[value.definition_id] = value
        return {
            definition_id: self.project(
                definition,
                configuration=configuration,
                grant=grants.get(definition_id),
            )
            for definition, definition_id in zip(values, ids, strict=True)
        }

    def _assert_match(self, grant, job, definition) -> None:
        if grant.status is not UnattendedExecutionGrantStatus.ACTIVE:
            raise UnattendedExecutionGrantError(
                "unattended execution grant is revoked",
                code="unattended_execution_grant_revoked",
                next_action="review completed history and explicitly grant the exact bounds again",
            )
        if getattr(job, "definition_id", None) != grant.definition_id:
            raise self._mismatch(
                "definition identity", "unattended_execution_grant_definition_mismatch"
            )
        if getattr(job, "resource_library_id", None) != grant.resource_library_id:
            raise self._mismatch("ResourceLibrary", "unattended_execution_grant_resource_mismatch")
        try:
            job_scope = AutomationTaskDefinition.normalize_scope(getattr(job, "source_scope", None))
        except (TypeError, ValueError):
            job_scope = object()
        if job_scope != grant.source_scope or definition.source_scope != grant.source_scope:
            raise self._mismatch("source scope", "unattended_execution_grant_scope_mismatch")
        if (
            getattr(job, "run_mode", None) != grant.run_mode
            or definition.mode is not grant.run_mode
        ):
            raise self._mismatch("run mode", "unattended_execution_grant_mode_mismatch")
        limit = getattr(job, "limit", None)
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > grant.max_items_per_run
        ):
            raise UnattendedExecutionGrantError(
                "occurrence workload exceeds the unattended execution grant",
                code="unattended_execution_grant_limit_exceeded",
                next_action=(
                    "lower the occurrence bound or explicitly grant a larger bound after review"
                ),
            )
        if _definition_changed_since_grant(grant, definition):
            raise UnattendedExecutionGrantError(
                "definition changed since the unattended execution grant",
                code="unattended_execution_grant_definition_changed",
                next_action=(
                    "review the changed definition and explicitly grant its exact bounds again"
                ),
            )
        if getattr(job, "configuration_snapshot_id", None) != grant.configuration_snapshot_id:
            raise self._mismatch(
                "configuration snapshot", "unattended_execution_grant_snapshot_mismatch"
            )
        if (
            getattr(job, "configuration_snapshot_digest", None)
            != grant.configuration_snapshot_digest
        ):
            raise self._mismatch(
                "configuration snapshot digest", "unattended_execution_grant_snapshot_mismatch"
            )
        job_version = getattr(job, "configuration_snapshot_version", None)
        if job_version != grant.configuration_snapshot_version:
            raise self._mismatch(
                "configuration snapshot version", "unattended_execution_grant_snapshot_mismatch"
            )

    @staticmethod
    def _mismatch(label: str, code: str) -> UnattendedExecutionGrantError:
        return UnattendedExecutionGrantError(
            f"unattended execution grant {label} does not match the claimed occurrence",
            code=code,
            next_action=(
                "inspect the pinned occurrence and explicitly grant the exact current bounds"
            ),
        )

    def _require_shared_analysis(
        self,
        definition,
        *,
        configuration_snapshot_id: str,
        configuration_snapshot_digest: str,
        configuration_snapshot_version: int,
        max_items_per_run: int,
        storage_id: str | None,
    ) -> None:
        """Refuse a grant with no valid shared analysis of the exact bounds.

        The independent Preview product is retired.  Its authorization-precedent
        role is now carried by the shared zero-mutation organize analysis that the
        definition-bound Run once produces: a frozen manifest with its linked
        exact plan Preview.  A grant may only be admitted over that persisted,
        current, zero-mutation analysis, so the exact definition identity, scope
        bounds and configuration pin are provably analyzed before any repeated
        media mutation authority is granted.
        """
        error = self._validate_shared_analysis(
            definition,
            configuration_snapshot_id=configuration_snapshot_id,
            configuration_snapshot_digest=configuration_snapshot_digest,
            configuration_snapshot_version=configuration_snapshot_version,
            max_items_per_run=max_items_per_run,
            storage_id=storage_id,
        )
        if error is not None:
            raise error

    def _validate_shared_analysis(
        self,
        definition,
        *,
        configuration_snapshot_id: str,
        configuration_snapshot_digest: str,
        configuration_snapshot_version: int,
        max_items_per_run: int,
        storage_id: str | None,
    ) -> UnattendedExecutionGrantError | None:
        """Return one bounded refusal, or ``None`` if the shared analysis is valid.

        Used by both the read-only eligibility projection and the durable grant
        admission so they refuse for exactly the same reasons.
        """
        if self._discovery_service is None or self._preview_service is None:
            return UnattendedExecutionGrantError(
                "the shared unattended-grant analysis service is unavailable",
                code="unattended_execution_analysis_unavailable",
                status=503,
                durable_state="no grant or media mutation occurred",
                next_action=(
                    "restore the shared discovery and organize-analysis services, then "
                    "run a fresh analysis before granting"
                ),
            )
        resolved = self._discovery_service.latest_definition_analysis(
            definition.definition_id,
            snapshot_id=configuration_snapshot_id,
            snapshot_digest=configuration_snapshot_digest,
        )
        if resolved is None:
            return UnattendedExecutionGrantError(
                "an unattended grant requires a shared zero-mutation analysis of the exact "
                "definition scope; none has been performed for the current configuration",
                code="unattended_execution_analysis_required",
                durable_state="no grant or media mutation occurred",
                next_action=(
                    "open the definition and run a fresh analysis (Run once), inspect its "
                    "findings and unblocked items, then explicitly confirm the grant"
                ),
                details={"definitionId": definition.definition_id},
            )
        discovery = resolved
        origin = discovery.definition_origin
        if origin is None:
            return UnattendedExecutionGrantError(
                "the shared analysis is not a definition-bound Run once",
                code="unattended_execution_analysis_mismatch",
                durable_state="no grant or media mutation occurred",
                next_action="run a fresh definition-scoped analysis, then grant again",
                details={"discoveryId": discovery.discovery_id},
            )
        mismatches = []
        expected = (
            ("definition identity", origin.definition_id, definition.definition_id),
            (
                "definition fingerprint",
                origin.definition_fingerprint,
                definition.definition_fingerprint,
            ),
            (
                "configuration revision",
                origin.configuration_revision_id,
                configuration_snapshot_id,
            ),
            (
                "configuration digest",
                origin.configuration_revision_digest,
                configuration_snapshot_digest,
            ),
            (
                "configuration version",
                origin.configuration_revision_version,
                configuration_snapshot_version,
            ),
            ("ResourceLibrary", origin.resource_library_id, definition.resource_library_id),
            ("source scope", origin.source_scope, definition.source_scope),
            ("run mode", origin.run_mode, definition.mode.value),
            ("Storage", discovery.storage_id, storage_id),
        )
        mismatches.extend(label for label, actual, wanted in expected if actual != wanted)
        if origin.effective_primary_limit < max_items_per_run:
            mismatches.append("workload bound")
        if mismatches:
            return UnattendedExecutionGrantError(
                "the shared analysis does not match the exact grant bounds: "
                + ", ".join(mismatches),
                code="unattended_execution_analysis_mismatch",
                durable_state="no grant or media mutation occurred",
                next_action="run a fresh analysis for the current exact definition and grant bound",
                details={"discoveryId": discovery.discovery_id, "mismatches": mismatches[:8]},
            )
        # The exact Preview is linked to the frozen manifest through the durable
        # intent identity; resolve it from the latest read-only analysis of that
        # intent rather than a discovery.preview_id column (which stays None).
        try:
            preview = self._preview_service.latest_readonly(discovery.intent_id)
        except Exception as error:
            if isinstance(error, UnattendedExecutionGrantError):
                return error
            return UnattendedExecutionGrantError(
                "the shared analysis Preview is missing or unavailable",
                code="unattended_execution_analysis_unavailable",
                status=503,
                durable_state="no grant or media mutation occurred",
                next_action="run a fresh analysis, then grant again",
                details={"intentId": discovery.intent_id},
            )
        if preview.current is not True or preview.zero_mutation is not True:
            return UnattendedExecutionGrantError(
                "the shared analysis is stale or does not prove zero mutation",
                code="unattended_execution_analysis_stale",
                durable_state="no grant or media mutation occurred",
                next_action="run a fresh exact zero-mutation analysis, then grant again",
                details={"previewId": preview.preview_id},
            )
        if preview.status is not ManualPreviewStatus.PREVIEWED:
            return UnattendedExecutionGrantError(
                "the shared analysis is not an acceptable completed analysis",
                code="unattended_execution_analysis_ineligible",
                durable_state="no grant or media mutation occurred",
                next_action="resolve the analysis blockers and run a fresh analysis",
                details={"previewId": preview.preview_id, "status": preview.status.value},
            )
        invalid = self._invalid_analysis_items(preview)
        if invalid:
            return UnattendedExecutionGrantError(
                "the shared analysis contains blocked or failed executable items",
                code="unattended_execution_analysis_item_blocked",
                durable_state="no grant or media mutation occurred",
                next_action="resolve each blocked or failed analysis item and run a fresh analysis",
                details={"previewId": preview.preview_id, "itemStatuses": invalid[:16]},
            )
        return None

    @staticmethod
    def _invalid_analysis_items(preview: ManualOrganizePreview) -> list[str]:
        """The statuses of analysis items that may not back an unattended grant."""

        blocked = {
            ManualPreviewItemStatus.BLOCKED,
            ManualPreviewItemStatus.FAILED,
            ManualPreviewItemStatus.STALE,
            ManualPreviewItemStatus.UNAVAILABLE,
            ManualPreviewItemStatus.TRUNCATED,
            ManualPreviewItemStatus.CANCELLED,
        }
        invalid = []
        for item in preview.items:
            if item.status in blocked:
                invalid.append(item.status.value)
        return invalid

    def _require_permission(self, principal) -> None:
        if principal is None:
            return
        permissions = getattr(principal, "permissions", principal)
        if (
            ApiPermission.GRANT_UNATTENDED_EXECUTION not in permissions
            and str(ApiPermission.GRANT_UNATTENDED_EXECUTION.value) not in permissions
        ):
            raise UnattendedExecutionGrantError(
                "principal lacks grant_unattended_execution permission",
                code="forbidden",
                status=403,
                durable_state="no grant or media effect was created",
                next_action="use an authorized principal to grant or revoke unattended execution",
            )

    def _get(self, grant_id):
        getter = getattr(self._repository, "get_unattended_execution_grant", None)
        if not callable(getter):
            getter = getattr(self._repository, "get_unattended_grant", None)
        if not callable(getter):
            return None
        try:
            return getter(grant_id)
        except UnattendedExecutionGrantError:
            raise
        except Exception as error:
            raise self._state_unavailable() from error

    def _get_active(self, definition_id):
        getter = getattr(self._repository, "get_active_unattended_execution_grant", None)
        if not callable(getter):
            getter = getattr(self._repository, "get_active_unattended_grant", None)
        if not callable(getter):
            return None
        try:
            return getter(definition_id)
        except UnattendedExecutionGrantError:
            raise
        except Exception as error:
            raise self._state_unavailable() from error

    def _latest_for_definition(self, definition_id):
        getter = getattr(self._repository, "get_latest_unattended_execution_grant", None)
        if callable(getter):
            try:
                return getter(definition_id)
            except UnattendedExecutionGrantError:
                raise
            except Exception as error:
                raise self._state_unavailable() from error
        values = self._list(definition_ids=(definition_id,), limit=1)
        return values[0] if values else None

    def _current_for_definition(self, definition_id):
        active = self._get_active(definition_id)
        return active if active is not None else self._latest_for_definition(definition_id)

    def _list(self, *, definition_ids=None, limit=100):
        getter = getattr(self._repository, "list_unattended_execution_grants", None)
        if not callable(getter):
            getter = getattr(self._repository, "list_unattended_grants", None)
        if not callable(getter):
            return ()
        try:
            return tuple(getter(definition_ids=definition_ids, limit=limit))
        except UnattendedExecutionGrantError:
            raise
        except Exception as error:
            raise self._state_unavailable() from error

    @staticmethod
    def _state_unavailable() -> UnattendedExecutionGrantError:
        return UnattendedExecutionGrantError(
            "unattended execution grant state is unavailable",
            code="unattended_execution_grant_state_unavailable",
            status=503,
            durable_state="grant state could not be read; no execution authority was granted",
            next_action=(
                "reload the Automation view and retry; do not treat unavailable grant state "
                "as no grant"
            ),
        )

    @staticmethod
    def _invalid(message: str, *, next_action: str = "inspect the grant request and correct it"):
        return UnattendedExecutionGrantError(
            message,
            code="unattended_execution_grant_invalid",
            status=400,
            next_action=next_action,
        )


def _definition(value):
    if isinstance(value, AutomationTaskDefinition):
        return value
    if isinstance(value, Mapping):
        return AutomationTaskDefinition.from_document(value)
    raise ValueError("Automation Task Definition is invalid")


def _actor(actor, principal) -> str:
    if actor is not None and not isinstance(actor, str):
        raise ValueError("unattended execution granting principal is invalid")
    value = actor or getattr(principal, "principal_id", None)
    if not isinstance(value, str):
        raise ValueError("unattended execution granting principal is invalid")
    return _bounded(
        redact_evidence_text(value, limit=MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH),
        MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH,
        "granting principal",
    )


def _reason(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("unattended execution reason is invalid")
    return _bounded(
        redact_evidence_text(value, limit=MAX_UNATTENDED_GRANT_REASON_LENGTH),
        MAX_UNATTENDED_GRANT_REASON_LENGTH,
        "grant reason",
    )


def _bounded(value: object, maximum: int, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"unattended execution {label} is invalid")
    return value.strip()


def _sha(value: object, label: str) -> str:
    result = _bounded(value, 64, label)
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise ValueError(f"unattended execution {label} is invalid")
    return result


def _version(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"unattended execution {label} is invalid")
    return value


def _grant_binding(value: UnattendedExecutionGrant) -> tuple[object, ...]:
    return (
        value.definition_id,
        value.resource_library_id,
        value.source_scope,
        value.run_mode,
        value.max_items_per_run,
        value.definition_fingerprint,
        value.configuration_snapshot_id,
        value.configuration_snapshot_digest,
        value.configuration_snapshot_version,
    )


def _prefer_grant(
    candidate: UnattendedExecutionGrant,
    current: UnattendedExecutionGrant | None,
) -> bool:
    """Select the same current grant semantics as the single-definition path."""

    if current is None:
        return True
    if candidate.active != current.active:
        return candidate.active
    return (candidate.granted_at, candidate.grant_id) > (
        current.granted_at,
        current.grant_id,
    )


def _definition_changed_since_grant(
    grant: UnattendedExecutionGrant, definition: AutomationTaskDefinition
) -> bool:
    """Treat enable/disable as scheduling state, not a grant-bound edit.

    Definition fingerprints intentionally include ``enabled`` because the
    Scheduler pins the complete definition document.  The grant itself is
    independent of scheduling, however: disabling a definition must not make
    its durable grant look stale, and re-enabling the same definition must be
    able to reuse that grant.  Comparing the opposite enabled value lets us
    recognize that one permitted toggle without weakening any other fingerprint
    or bound-tuple check.
    """

    current = definition.definition_fingerprint
    if grant.definition_fingerprint == current:
        return False
    try:
        toggled = replace(definition, enabled=not definition.enabled)
    except (TypeError, ValueError):
        return True
    return grant.definition_fingerprint != toggled.definition_fingerprint


__all__ = [
    "UnattendedExecutionAuthority",
    "UnattendedExecutionBoundaryError",
    "UnattendedExecutionGrantError",
    "UnattendedExecutionGrantService",
]
