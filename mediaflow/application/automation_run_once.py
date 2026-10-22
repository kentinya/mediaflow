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
    "pausing",
    "paused",
    "ready",
    "refused",
    "no_work",
    "failed",
    "cancelled",
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
        preview_service,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._discovery = discovery_service
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
        plan_id = self._durable_plan_id(discovery)
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
            # The exact durable fixed-plan identity linked to this Run once.  It
            # carries no authority; it lets the same page re-read the plan it
            # already produced after a reload, reconnect or restart.  The
            # inline finalize path writes the plan against the frozen intent, so
            # the association is resolved from that same durable intent rather
            # than from the ``preview_id`` column this path never populates.
            # A paused, pause-pending or cancelled run publishes no plan: the
            # operator's control won the race, so the operator must not be
            # handed a confirmable summary for work that was stopped.
            "previewId": plan_id,
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
        # The operator's own control decides the phase before anything else: a
        # paused or pause-pending run is not "analyzing" and a cancelled run is
        # not a recoverable refusal.  Both must stop advertising the plan they
        # interrupted.
        if discovery.cancel_requested or discovery.status is DiscoveryStatus.CANCELLED:
            return "cancelled"
        if discovery.status is DiscoveryStatus.PAUSED:
            return "paused"
        if discovery.pause_requested:
            # The pause request is durable and the Worker acknowledges it at its
            # next safe boundary; the page states that real transient stage
            # instead of pretending the analysis is still progressing.
            return "pausing"
        if discovery.status in {DiscoveryStatus.QUEUED, DiscoveryStatus.RUNNING}:
            return "discovering"
        if discovery.status is DiscoveryStatus.ANALYZING:
            # The frozen manifest's exact plan is being built by the resident
            # Worker; the run identity, progress and pause/cancel stay live.
            return "analyzing"
        if discovery.status is DiscoveryStatus.WAITING_STABILITY:
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
        # The operator's control owns these actions.  A cancellation request is
        # already a durable terminal settlement, an acknowledged pause is not
        # pausable again, and a pause that is still pending acknowledgement must
        # neither be re-requested nor refused as if it were already settled.
        cancelled = discovery.cancel_requested or discovery.status is DiscoveryStatus.CANCELLED
        paused = discovery.status is DiscoveryStatus.PAUSED
        pause = (
            not cancelled
            and not paused
            and not discovery.pause_requested
            and discovery.status
            in {
                DiscoveryStatus.QUEUED,
                DiscoveryStatus.RUNNING,
                DiscoveryStatus.ANALYZING,
            }
        )
        cancel = not cancelled and discovery.status in {
            DiscoveryStatus.QUEUED,
            DiscoveryStatus.RUNNING,
            DiscoveryStatus.WAITING_STABILITY,
            DiscoveryStatus.PAUSED,
            DiscoveryStatus.ANALYZING,
        }
        # Continue is meaningful only after the Worker acknowledged the pause at
        # a safe boundary; the pending stage is reported through the phase and
        # next action instead of being advertised as an available action.
        resume = paused and discovery.pause_requested
        # The exact plan identity the same page re-reads after a reload.  It is
        # resolved from the durable intent association so the advertised action
        # path is never published as unavailable-with-a-null-route while the
        # plan itself is readable.
        plan_id = self._durable_plan_id(discovery)
        return {
            "pause": {"available": pause, "method": "POST", "sideEffects": "none"},
            "cancel": {"available": cancel, "method": "POST", "sideEffects": "none"},
            "resume": {"available": resume, "method": "POST", "sideEffects": "none"},
            "finalize": {
                "available": finalizable,
                "method": "POST",
                "sideEffects": "none",
                "durableOutcome": (
                    "the complete bounded manifest is frozen and the resident Worker runs the "
                    "exact zero-mutation analysis on this same durable run"
                ),
                "nextAction": (
                    "review the exact plan of the frozen manifest once the Worker links it, "
                    "then separately confirm execution"
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
                # The frozen manifest's complete zero-mutation plan is the shared
                # organize plan of its linked intent.  Its exact durable identity
                # is published so the Run once page can restore the same plan
                # summary after a reload, reconnect or restart instead of
                # re-analysing the manifest.  While the resident Worker is still
                # building the plan the action is available but its route is
                # honestly null; the page shows the durable analysis stage and
                # the plan appears here once it completes.  A paused, pause-
                # pending or cancelled run publishes no plan action at all: the
                # operator's control won, so no confirmable summary is offered.
                "available": (
                    bool(plan_id)
                    or (
                        not cancelled
                        and not paused
                        and not discovery.pause_requested
                        and discovery.frozen
                        and discovery.intent_id is not None
                    )
                ),
                "method": "GET",
                "path": (f"/api/v1/operations/organize/previews/{plan_id}" if plan_id else None),
                "sideEffects": "none",
                "nextAction": (
                    "review the frozen manifest's exact plan summary in this Run once"
                    if plan_id
                    else "wait for the resident Worker to link this run's exact plan"
                ),
            },
        }

    def _durable_plan_id(self, discovery: MediaDiscovery) -> str | None:
        """The exact durable plan this Run once already produced, if any.

        The Run-once finalize freezes the manifest and runs the shared
        zero-mutation analysis over its linked manual intent, so the plan is
        addressed by that intent.  Resolving it here means an ordinary GET — a
        reload, a reconnect or a restart — returns the same plan identity the
        finalize response published, without re-walking sources, re-running the
        analysis or guessing from a recent record.  The read is the bounded,
        non-publishing ``latest_readonly`` projection, so a plain read never
        marks evidence stale and never creates a second plan.  ``None`` simply
        means this Run once has not produced a plan yet.
        """

        if (
            discovery.status is DiscoveryStatus.CANCELLED
            or discovery.cancel_requested
            or discovery.status is DiscoveryStatus.PAUSED
            or discovery.pause_requested
        ):
            # The operator's control decides the run, so the intent's latest
            # read-only plan must never be re-exposed for a stopped run.
            return None
        if discovery.preview_id:
            return discovery.preview_id
        intent_id = discovery.intent_id
        if not intent_id or self._previews is None:
            return None
        latest_readonly = getattr(self._previews, "latest_readonly", None)
        if not callable(latest_readonly):
            return None
        try:
            preview = latest_readonly(intent_id)
        except Exception:  # noqa: BLE001 - an unreadable plan is a truthful absence
            return None
        preview_id = getattr(preview, "preview_id", None)
        return preview_id if isinstance(preview_id, str) and preview_id else None

    def _next_action(
        self,
        discovery: MediaDiscovery,
        refusal: DiscoveryIncompleteReason | None,
    ) -> str:
        if discovery.cancel_requested or discovery.status is DiscoveryStatus.CANCELLED:
            return "start a new Run once from the published definition if the scope is still wanted"
        if discovery.status is DiscoveryStatus.PAUSED:
            return (
                "continue this Run once to resume the same frozen scope and configuration; no "
                "plan was published for the interrupted analysis"
            )
        if discovery.pause_requested:
            return (
                "the cooperative pause is waiting for the resident Processing Worker to "
                "acknowledge it at its safe boundary; continue the same Run once after the "
                "acknowledgement"
            )
        if refusal is not None:
            return (
                "narrow the definition sourceScope or correct the unreadable source so a "
                "complete manifest is proved, publish it, then start Run once again"
            )
        if discovery.status is DiscoveryStatus.ANALYZING:
            return (
                "wait for the resident Worker to finish the zero-mutation analysis; the exact "
                "plan appears on this run and still needs a separate explicit confirmation"
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
    ) -> tuple[MediaDiscovery, object | None]:
        """Freeze the complete manifest and enter its durable shared analysis.

        Freezing reuses the existing discovery finalize, which hands the frozen
        source list to the existing manual intent admission.  The exact plan
        over that intent is then produced by the resident Processing Worker
        through the existing durable analysis stage (one versioned ANALYZING
        publication on this same run record) — never inline inside the HTTP
        request.  No execution authority is created: the operator still has to
        confirm execution separately once the exact plan appears.

        Returns ``(frozen, None)``.  ``preview`` is always ``None`` here; the
        exact plan is read back from the same run's durable association when
        the Worker links it.
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
        if (
            discovery.status is DiscoveryStatus.ANALYZING
            and discovery.frozen
            and discovery.intent_id is not None
        ):
            # A repeated or lost-response request converges on the analysis
            # already queued for this exact frozen intent: one durable run, one
            # linked intent, one analysis stage — never duplicate work.
            return discovery, None
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
        # The shared zero-mutation analysis continues on this same durable run:
        # the resident Worker claims the ANALYZING stage and publishes the exact
        # plan here.  A repeated request after a lost response converges on the
        # already-queued analysis instead of duplicating work.
        analyzing = self._discovery.begin_frozen_analysis(
            discovery_id, actor=actor, expected_version=frozen.version
        )
        return analyzing, None

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
