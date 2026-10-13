"""Definition-bound Run once: automatic discovery, freeze and exact Preview.

A published ``automatic-organization`` definition already identifies its
ResourceLibrary and safe source sub-scope.  Run once therefore needs no file
picker and no hand-selected subset: this service derives the complete admitted
scope from the saved definition, admits the existing durable bounded discovery,
and — once the resident Worker has frozen a *complete* manifest — creates the
existing manual intent and exact zero-mutation Preview that the ordinary
separate one-shot execution intent then consumes.

Safety invariants preserved here:

* the whole stage is metadata-only and creates **no** mutation authority; only
  the existing exact Preview plus an explicit separate execution confirmation
  can ever reach ``OrganizerExecutor``;
* the effective manifest bound is the smaller of the definition ceiling and the
  existing manual/discovery primary bound, and an over-bound or incomplete walk
  refuses execution instead of freezing a first-N prefix;
* Run once never enables a schedule, never creates/revives/consumes an
  unattended grant, and never advances or resets definition due state;
* a disabled published schedule is runnable once; a Draft-only or removed
  definition is not.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from mediaflow.domain.automation import AutomationTaskDefinition, AutomationTaskRunMode
from mediaflow.domain.media_discovery import (
    BUDGET_LIMITED_REASONS,
    DiscoveryError,
    DiscoveryIncompleteReason,
    DiscoveryStatus,
    MediaDiscovery,
    discovery_material_refusal,
    effective_primary_limit,
)

#: Bounded operator-facing phases of one definition-bound Run once.
RUN_ONCE_PHASES = (
    "discovering",
    "analyzing",
    "ready",
    "refused",
    "no_work",
    "failed",
)


class AutomationRunOnceError(DiscoveryError):
    """A bounded, operator-correctable Run-once refusal."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "run_once_rejected",
        status: int = 409,
        next_action: str = "review the definition bounds and start Run once again",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status=status,
            next_action=next_action,
            details=details,
        )


class AutomationRunOnceService:
    """Drive one definition-bound Run once through the existing authorities."""

    def __init__(
        self,
        discovery_service,
        intent_service,
        preview_service,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._discovery = discovery_service
        self._intents = intent_service
        self._previews = preview_service
        self._clock = clock

    @property
    def discovery(self):
        return self._discovery

    # ------------------------------------------------------------------
    # Admission (prompt; no Storage walk in the HTTP request)
    # ------------------------------------------------------------------

    def admit(
        self,
        definition_id: str,
        *,
        actor: str,
        admission_request_id: str | None = None,
    ) -> MediaDiscovery:
        """Admit the durable discovery for one published definition.

        The response is prompt: the actual source walk happens in the resident
        Processing Worker, so a large analysis never blocks the HTTP request.
        """

        if self._discovery is None:
            raise AutomationRunOnceError(
                "definition Run once is unavailable",
                code="run_once_unavailable",
                status=503,
                next_action="restore the bounded discovery service and start Run once again",
            )
        return self._discovery.admit_definition_run_once(
            definition_id=definition_id,
            actor=actor,
            admission_request_id=admission_request_id,
        )

    # ------------------------------------------------------------------
    # Readback
    # ------------------------------------------------------------------

    def get(self, discovery_id: str) -> MediaDiscovery:
        return self._discovery.get(discovery_id)

    def list(self, *, actor: str | None = None, limit: int = 100) -> tuple[MediaDiscovery, ...]:
        return self._discovery.list(actor=actor, limit=limit)

    def document(self, discovery: MediaDiscovery) -> dict[str, object]:
        """The bounded Run-once projection of one definition-bound discovery."""

        origin = discovery.definition_origin
        if origin is None:
            raise AutomationRunOnceError(
                "the requested discovery is not a definition-bound Run once",
                code="not_a_run_once",
                status=404,
                next_action="open the definition and start Run once",
            )
        refusal = discovery_material_refusal(discovery.progress)
        phase = self._phase(discovery, refusal)
        document: dict[str, object] = {
            "journey": "automation-run-once",
            "discoveryId": discovery.discovery_id,
            "definitionId": origin.definition_id,
            "definitionName": origin.definition_name,
            "definitionFingerprint": origin.definition_fingerprint,
            "definitionOrigin": origin.document(),
            "resourceLibraryId": discovery.resource_library_id,
            "sourceScope": origin.source_scope,
            "runMode": origin.run_mode,
            "definitionItemLimit": origin.definition_item_limit,
            "effectivePrimaryLimit": origin.effective_primary_limit,
            "phase": phase,
            "status": discovery.status.value,
            "version": discovery.version,
            "progress": discovery.progress.document(),
            "counts": discovery.progress.counters.document(),
            "primarySourceCount": len(discovery.sources),
            "intentId": discovery.intent_id,
            "frozenAt": discovery.frozen_at.isoformat() if discovery.frozen_at else None,
            "zeroMutation": True,
            "sideEffects": "none",
            "admissionRequestId": discovery.admission_request_id,
            "nextAction": self._next_action(discovery, refusal),
            "actions": self._actions(discovery, refusal),
        }
        if refusal is not None:
            document["refusalReason"] = refusal.value
        if discovery.progress.incomplete_reason is not DiscoveryIncompleteReason.NONE:
            document["incompleteReason"] = discovery.progress.incomplete_reason.value
        if discovery.error:
            document["error"] = discovery.error
        return document

    def _phase(
        self,
        discovery: MediaDiscovery,
        refusal: DiscoveryIncompleteReason | None,
    ) -> str:
        if discovery.status in {DiscoveryStatus.QUEUED, DiscoveryStatus.RUNNING}:
            return "discovering"
        if discovery.status is DiscoveryStatus.WAITING_STABILITY:
            return "analyzing"
        if discovery.status is DiscoveryStatus.PAUSED:
            return "analyzing"
        if refusal is not None:
            return "refused"
        if discovery.status is DiscoveryStatus.PARTIAL_SUCCESS:
            # A partial walk without a material refusal is an ordinary read
            # failure: the reviewed subset keeps its explicit-review path.
            return "analyzing" if not discovery.sources else "ready"
        if discovery.status is DiscoveryStatus.COMPLETED:
            return "ready" if discovery.sources else "no_work"
        if discovery.status is DiscoveryStatus.CANCELLED:
            return "failed"
        return "failed"

    def _actions(
        self,
        discovery: MediaDiscovery,
        refusal: DiscoveryIncompleteReason | None,
    ) -> dict[str, object]:
        terminal = discovery.status in {
            DiscoveryStatus.COMPLETED,
            DiscoveryStatus.PARTIAL_SUCCESS,
        }
        # Finalize (and therefore any Preview or execution) is refused for a
        # budget/safety-limited walk: the recorded sources are a truncated
        # prefix, never a complete manifest.
        finalizable = (
            terminal
            and refusal is None
            and discovery.progress.incomplete_reason not in BUDGET_LIMITED_REASONS
            and bool(discovery.sources)
            and not discovery.frozen
        )
        pause = discovery.status in {DiscoveryStatus.QUEUED, DiscoveryStatus.RUNNING}
        cancel = discovery.status in {
            DiscoveryStatus.QUEUED,
            DiscoveryStatus.RUNNING,
            DiscoveryStatus.WAITING_STABILITY,
            DiscoveryStatus.PAUSED,
        }
        resume = discovery.status is DiscoveryStatus.PAUSED
        return {
            "pause": {"available": pause, "method": "POST", "sideEffects": "none"},
            "cancel": {"available": cancel, "method": "POST", "sideEffects": "none"},
            "resume": {"available": resume, "method": "POST", "sideEffects": "none"},
            "finalize": {
                "available": finalizable,
                "method": "POST",
                "sideEffects": "none",
                "durableOutcome": (
                    "the complete bounded manifest is frozen and an exact zero-mutation "
                    "Preview is stored"
                ),
                "nextAction": (
                    "review the exact Preview of the frozen manifest, then separately "
                    "confirm execution"
                ),
            },
            "narrowScope": {
                "available": refusal is not None,
                "sideEffects": "none",
                "nextAction": (
                    "narrow the definition sourceScope or lower its itemLimit, publish it, "
                    "then start Run once again"
                ),
            },
            "preview": {
                "available": discovery.frozen and discovery.intent_id is not None,
                "method": "GET",
                "sideEffects": "none",
                "nextAction": "open the frozen manifest's exact Preview",
            },
        }

    def _next_action(
        self,
        discovery: MediaDiscovery,
        refusal: DiscoveryIncompleteReason | None,
    ) -> str:
        if refusal is not None:
            return (
                "narrow the definition sourceScope or lower its itemLimit so a complete "
                "manifest fits the bound, publish it, then start Run once again"
            )
        if discovery.frozen and discovery.intent_id is not None:
            return "review the exact zero-mutation Preview, then separately confirm execution"
        if discovery.status is DiscoveryStatus.WAITING_STABILITY:
            return (
                "wait for the configured stability interval, then let the resident Worker "
                "continue the same Run once"
            )
        if discovery.status is DiscoveryStatus.PAUSED:
            return "continue the Run once to resume the same bounded scope"
        if discovery.status is DiscoveryStatus.CANCELLED:
            return "start a new Run once from the published definition"
        if discovery.status is DiscoveryStatus.FAILED:
            return "repair the stated source or configuration condition, then start Run once again"
        if discovery.status is DiscoveryStatus.COMPLETED and not discovery.sources:
            return "the definition scope currently contains no eligible source; no work was started"
        if discovery.status in {DiscoveryStatus.QUEUED, DiscoveryStatus.RUNNING}:
            return "wait for the resident Processing Worker to finish the bounded discovery"
        return "finalize the completed discovery to review its exact Preview"

    # ------------------------------------------------------------------
    # Freeze and exact Preview
    # ------------------------------------------------------------------

    def finalize(
        self, discovery_id: str, *, actor: str, expected_version: int
    ) -> tuple[MediaDiscovery, object]:
        """Freeze the complete manifest and create its exact zero-mutation Preview.

        Freezing reuses the existing discovery finalize (which hands the frozen
        source list to the existing manual intent admission) and then runs the
        existing exact Preview over that intent.  No execution authority is
        created: the operator still has to confirm execution separately.
        """

        discovery = self._discovery.get(discovery_id)
        origin = discovery.definition_origin
        if origin is None:
            raise AutomationRunOnceError(
                "the requested discovery is not a definition-bound Run once",
                code="not_a_run_once",
                status=404,
                next_action="open the definition and start Run once",
            )
        self._assert_complete(discovery)
        frozen = self._discovery.finalize(
            discovery_id, actor=actor, expected_version=expected_version
        )
        if frozen.intent_id is None:
            raise AutomationRunOnceError(
                "the frozen Run-once manifest has no linked reviewable intent",
                code="run_once_finalize_incomplete",
                status=503,
                next_action="inspect the discovery state, then finalize it again",
            )
        preview = self._previews.create(
            frozen.intent_id,
            actor=actor,
            expected_version=self._intent_version(frozen.intent_id),
        )
        return frozen, preview

    def _intent_version(self, intent_id: str) -> int:
        intent = self._intents.get(intent_id)
        return int(getattr(intent, "version", 1))

    def _assert_complete(self, discovery: MediaDiscovery) -> None:
        refusal = discovery_material_refusal(discovery.progress)
        if refusal is not None or (discovery.progress.incomplete_reason in BUDGET_LIMITED_REASONS):
            reason = (refusal or discovery.progress.incomplete_reason).value
            raise AutomationRunOnceError(
                "this Run once stopped at a budget or safety limit, so its findings are an "
                "incomplete subset and cannot be executed",
                code="discovery_overflow",
                next_action=(
                    "narrow the definition sourceScope or lower its itemLimit, publish it, "
                    "then start a fresh Run once"
                ),
                details={
                    "incompleteReason": reason,
                    "definitionItemLimit": (
                        discovery.definition_origin.definition_item_limit
                        if discovery.definition_origin
                        else None
                    ),
                    "effectivePrimaryLimit": (
                        discovery.definition_origin.effective_primary_limit
                        if discovery.definition_origin
                        else None
                    ),
                },
            )
        if discovery.status not in {
            DiscoveryStatus.COMPLETED,
            DiscoveryStatus.PARTIAL_SUCCESS,
        }:
            raise AutomationRunOnceError(
                "the Run-once discovery has not finished its bounded walk yet",
                code="discovery_not_complete",
                status=409,
                next_action=(
                    "wait for the resident Processing Worker to finish, then review the "
                    "exact Preview"
                ),
                details={"status": discovery.status.value},
            )
        if not discovery.sources:
            raise AutomationRunOnceError(
                "the definition scope currently contains no eligible source; no work was started",
                code="selection_empty",
                status=409,
                next_action=(
                    "narrow the definition sourceScope or correct the configured filters, "
                    "publish it, then start Run once again"
                ),
            )

    # ------------------------------------------------------------------
    # Historical context
    # ------------------------------------------------------------------

    @staticmethod
    def definition_context(discovery: MediaDiscovery) -> dict[str, object] | None:
        """The immutable definition context of one Run once, for history reads."""

        origin = discovery.definition_origin
        if origin is None:
            return None
        return {
            "definitionId": origin.definition_id,
            "definitionName": origin.definition_name,
            "definitionFingerprint": origin.definition_fingerprint,
            "configurationRevisionId": origin.configuration_revision_id,
            "configurationRevisionVersion": origin.configuration_revision_version,
            "resourceLibraryId": origin.resource_library_id,
            "sourceScope": origin.source_scope,
            "runMode": origin.run_mode,
            "definitionItemLimit": origin.definition_item_limit,
            "effectivePrimaryLimit": origin.effective_primary_limit,
        }


def definition_run_once_available(definition) -> tuple[bool, str | None]:
    """Whether one published definition may be run once, with its reason.

    A disabled schedule is explicitly runnable: only the *schedule* is off.  A
    definition recording a removed mode is not runnable at all.
    """

    if not isinstance(definition, AutomationTaskDefinition):
        try:
            definition = AutomationTaskDefinition.from_document(definition)
        except (TypeError, ValueError):
            return False, "the definition configuration is invalid and cannot be run once"
    mode = definition.mode
    if not isinstance(mode, AutomationTaskRunMode) or not mode.is_runnable:
        return False, "the definition records a removed Automation mode and cannot be run once"
    bound = effective_primary_limit(definition.item_limit)
    if definition.item_limit > bound:
        return (
            False,
            f"the definition item ceiling exceeds the bounded manifest limit of {bound}; "
            "narrow the scope or lower the limit, publish, then run once",
        )
    return True, None


def origin_summary(discovery: MediaDiscovery) -> Mapping[str, object] | None:
    """A bounded, secret-free origin summary for list projections."""

    origin = discovery.definition_origin
    if origin is None:
        return None
    return {
        "kind": "definition-run-once",
        "definitionId": origin.definition_id,
        "definitionName": origin.definition_name,
        "sourceScope": origin.source_scope,
        "runMode": origin.run_mode,
    }


__all__ = [
    "AutomationRunOnceError",
    "AutomationRunOnceService",
    "RUN_ONCE_PHASES",
    "definition_run_once_available",
    "origin_summary",
]
