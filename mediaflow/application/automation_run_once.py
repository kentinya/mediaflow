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
    discovery_manifest_incomplete,
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
        analysis_service=None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._discovery = discovery_service
        self._intents = intent_service
        self._previews = preview_service
        # Optional durable exact-analysis admission.  When present, freezing a
        # Run-once manifest hands its exact Preview work to the resident Worker
        # instead of running the whole walk and Provider batch inline in the
        # HTTP request.
        self._analyses = analysis_service
        self._clock = clock

    @property
    def discovery(self):
        return self._discovery

    def bind_analysis_service(self, analysis_service) -> None:
        """Attach the durable exact-analysis admission used by ``finalize``.

        The API constructs the exact-Preview and analysis services after this
        service, so the binding is explicit rather than a construction-order
        dependency.  Until it is bound, ``finalize`` produces the exact Preview
        inline as before.
        """

        self._analyses = analysis_service

    # ------------------------------------------------------------------
    # Admission (prompt; no Storage walk in the HTTP request)
    # ------------------------------------------------------------------

    def admit(
        self,
        definition_id: str,
        *,
        actor: str,
        admission_request_id: str | None = None,
        expected_definition_fingerprint: str | None = None,
        expected_revision_id: str | None = None,
        expected_revision_version: int | None = None,
        expected_revision_digest: str | None = None,
    ) -> MediaDiscovery:
        """Admit the durable discovery for one published definition.

        The response is prompt: the actual source walk happens in the resident
        Processing Worker, so a large analysis never blocks the HTTP request.

        The optional observed definition/configuration fence binds the new
        admission to the exact published state the operator reviewed; a
        changed definition or repinned Active refuses the stale request.
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
            expected_definition_fingerprint=expected_definition_fingerprint,
            expected_revision_id=expected_revision_id,
            expected_revision_version=expected_revision_version,
            expected_revision_digest=expected_revision_digest,
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
        refusal = discovery_manifest_incomplete(discovery.progress)
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
            "frozen": discovery.frozen,
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
        # The frozen state is advertised only after the durable freeze actually
        # happened: a completed walk that has not been frozen yet is ready to
        # freeze, not already frozen.
        if discovery.frozen and discovery.intent_id is not None:
            return "frozen"
        if discovery.status is DiscoveryStatus.PARTIAL_SUCCESS:
            # A partial walk is an incomplete manifest for a definition-derived
            # Run once; it is refused above rather than advertised as ready.
            return "refused"
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
        # Finalize (and therefore any Preview or execution) is refused for any
        # walk that did not prove a complete manifest: a budget/safety-limited
        # walk recorded a truncated prefix, and a read failure recorded a
        # partial subset.  Neither may become an executable Automation prefix.
        finalizable = (
            terminal and refusal is None and bool(discovery.sources) and not discovery.frozen
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
                    "manual Preview is stored"
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
                    "narrow the definition sourceScope or correct the unreadable source, "
                    "publish it, then start Run once again"
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
                "narrow the definition sourceScope or correct the unreadable source so a "
                "complete manifest is proved, publish it, then start Run once again"
            )
        if discovery.frozen and discovery.intent_id is not None:
            return (
                "review the exact zero-mutation manual Preview of the frozen manifest, then "
                "separately confirm execution"
            )
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
    ) -> tuple[MediaDiscovery, object | None, object | None]:
        """Freeze the complete manifest and admit its exact zero-mutation Preview.

        Freezing reuses the existing discovery finalize, which hands the frozen
        source list to the existing manual intent admission.  The exact Preview
        over that intent is then admitted through the durable analysis service
        when one is configured, so a large frozen manifest never blocks the HTTP
        request; the resident Worker runs the walk and Provider batch and links
        the resulting exact Preview.  Either way no execution authority is
        created: the operator still has to confirm execution separately.

        Returns ``(frozen, preview, analysis)``.  ``preview`` is the completed
        Preview when one could be produced inline (no durable analysis service),
        and ``analysis`` is the durable admission when the work was deferred.
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
        intent_version = self._intent_version(frozen.intent_id)
        if self._analyses is not None:
            # Defer the expensive exact analysis to the resident Worker.  The
            # frozen manifest and its intent are already durable, so the
            # operator reads a durable analysis identity immediately and the
            # separate one-shot execution intent is still required afterwards.
            analysis = self._analyses.admit_manual(
                frozen.intent_id,
                actor=actor,
                expected_version=intent_version,
            )
            return frozen, None, analysis
        preview = self._previews.create(
            frozen.intent_id,
            actor=actor,
            expected_version=intent_version,
        )
        return frozen, preview, None

    def _intent_version(self, intent_id: str) -> int:
        intent = self._intents.get(intent_id)
        return int(getattr(intent, "version", 1))

    def _assert_complete(self, discovery: MediaDiscovery) -> None:
        # A definition-derived Run once must prove a *complete* manifest of the
        # saved definition scope.  The strict rule includes an ordinary read
        # failure: an unreadable subtree or an unobservable named file leaves
        # the recorded sources a partial subset, so freezing it would advertise
        # a truncated Automation prefix as executable work.
        refusal = discovery_manifest_incomplete(discovery.progress)
        if refusal is not None:
            raise AutomationRunOnceError(
                "this Run once did not prove a complete manifest of the definition scope, so "
                "its findings cannot be executed",
                code=(
                    "discovery_overflow"
                    if refusal in BUDGET_LIMITED_REASONS
                    else "discovery_incomplete_manifest"
                ),
                next_action=(
                    "narrow the definition sourceScope or correct the unreadable source, "
                    "publish it, then start a fresh Run once and discover again"
                ),
                details={
                    "incompleteReason": refusal.value,
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
    definition recording a removed mode is not runnable at all.  A ceiling
    above the manual primary bound is legal: the effective manifest bound is
    ``min(ceiling, bound)`` and is enforced against the actual discovered
    manifest, so a scope smaller than the bound still runs once completely.
    """

    if not isinstance(definition, AutomationTaskDefinition):
        try:
            definition = AutomationTaskDefinition.from_document(definition)
        except (TypeError, ValueError):
            return False, "the definition configuration is invalid and cannot be run once"
    mode = definition.mode
    if not isinstance(mode, AutomationTaskRunMode) or not mode.is_runnable:
        return False, "the definition records a removed Automation mode and cannot be run once"
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
