"""Focused Automation engine settings publication and consumer readback (RO-6).

This is the application boundary the native `自动化 → 全局设置` form and the
System Settings Automation section both submit to.  It reuses the existing
authorities instead of adding a second settings store:

* validation and normalization of the four fields happen in
  :mod:`mediaflow.domain.automation_settings`, before any Draft exists;
* the successor Draft is seeded from the *observed immutable Active*, never from
  an unrelated open Draft, and every other field/object is preserved
  byte-identically;
* whole-candidate validation, prepare-before-publish and atomic activation stay
  in :class:`ManagedConfigurationService`, so this command cannot accept, publish
  or race differently from any other managed publication;
* adoption is a separate truth: it is read from each resident process's own
  durable report, never inferred from the API binding.

Reads create no Draft, admit no work, grant no authority, call no Provider and
mutate no Storage.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from mediaflow.application.configuration_snapshot import (
    ManagedConfigurationService,
    _reject_literal_secrets,
)
from mediaflow.domain.automation_settings import (
    CAPACITY_FIELD_PATHS,
    COMMITTED_SUBMISSION_STATES,
    CONFIG_RECHECK_SECONDS,
    CONSUMER_POLLING_FIELDS,
    ENGINE_FIELD_PATHS,
    ENGINE_FIELD_SPECS,
    NON_ADOPTED_STATUSES,
    AutomationEngineSettingsError,
    ConsumerAdoptionStatus,
    ConsumerRegistrationState,
    EngineSubmissionState,
    PublishedEngineTarget,
    ResidentSettingsEvidence,
    adoption_summary,
    engine_values_from_document,
    evaluate_consumer_adoption,
    normalize_engine_setting_edits,
    normalize_override_source,
)
from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationVersionConflict,
    ManagedConfigurationRevision,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.resident_services import (
    ResidentServiceRegistration,
    resident_stale_threshold_seconds,
)

#: The two resident consumers whose cadence this form can observe.
RELEVANT_CONSUMERS: tuple[str, ...] = ("worker", "scheduler")

#: Per-instance evidence rows read per service.  This is a *page* size for one
#: bounded read, not a window on "who is live": liveness comes from the
#: registration rows, so an instance whose report is older than the bound still
#: appears — as unreported — instead of disappearing from the answer.
ADOPTION_EVIDENCE_LIMIT = 100

#: One submission identity is a client-generated, non-secret token.  It is
#: bounded and opaque so it can be recorded in durable audit evidence and read
#: back after a reload without ever becoming an authority.
SUBMISSION_ID_MAX_LENGTH = 64


def normalize_submission_id(value: object) -> str | None:
    """Return a bounded opaque submission identity, or ``None`` when unusable.

    The identity is deliberately required to look like a random token rather
    than free text: it is persisted in bounded audit evidence and echoed to the
    operator for reconciliation, so it must not be able to carry a secret, a
    path or a bearer credential.
    """

    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed or len(trimmed) > SUBMISSION_ID_MAX_LENGTH:
        return None
    if not all(character.isalnum() or character in "-_.:" for character in trimmed):
        return None
    return trimmed


SETTINGS_PUBLICATION_ACTION = "automation_engine_settings_publish"

#: Durable, bounded terminal-outcome records for one identified focused Save.
#:
#: A submission can terminate *without* ever owning a revision: a four-field
#: input rejection happens before normalisation succeeds, a stale refusal happens
#: before a Draft exists, a no-op publishes nothing, and a persist/validate/
#: prepare/activate fault leaves the successor unpublished.  Without a durable
#: record of those terminations a lost response would leave the operator with a
#: permanently blocked form: the request cannot be re-sent safely and the exact
#: submission could never be proven either way.  The record is scoped to the same
#: submission identity and actor as the publication trail, so it can only ever
#: resolve that one request.
SUBMISSION_OUTCOME_ACTION = "automation_settings_outcome"
SUBMISSION_OUTCOME_INPUT_REJECTED = "input_rejected"
SUBMISSION_OUTCOME_STALE = "stale_refused"
SUBMISSION_OUTCOME_UNCHANGED = "unchanged_no_publication"
SUBMISSION_OUTCOME_VALIDATION_FAILED = "validation_failed"
SUBMISSION_OUTCOME_PREPARE_FAILED = "runtime_prepare_failed"
SUBMISSION_OUTCOME_ACTIVATE_FAILED = "activation_failed"
SUBMISSION_OUTCOME_PERSIST_FAILED = "persist_failed"

#: The terminal outcome a bounded focused-publication failure proves.
#:
#: The mapping is by the error's own code rather than only its stage, because the
#: ``compose`` stage covers both a stale identity and an out-of-scope candidate,
#: and those two must not be reported to the operator as the same condition.
SUBMISSION_OUTCOME_BY_CODE: dict[str, str] = {
    "automation_settings_stale": SUBMISSION_OUTCOME_STALE,
    "automation_settings_out_of_scope": SUBMISSION_OUTCOME_STALE,
    "automation_settings_persistence_failed": SUBMISSION_OUTCOME_PERSIST_FAILED,
    "automation_settings_validation_failed": SUBMISSION_OUTCOME_VALIDATION_FAILED,
    "automation_settings_runtime_failed": SUBMISSION_OUTCOME_PREPARE_FAILED,
    "automation_settings_activation_failed": SUBMISSION_OUTCOME_ACTIVATE_FAILED,
}

#: Stage fallback for an unexpected bounded error with no mapped code.
SUBMISSION_OUTCOME_BY_STAGE: dict[str, str] = {
    "persist": SUBMISSION_OUTCOME_PERSIST_FAILED,
    "validate": SUBMISSION_OUTCOME_VALIDATION_FAILED,
    "prepare": SUBMISSION_OUTCOME_PREPARE_FAILED,
    "activate": SUBMISSION_OUTCOME_ACTIVATE_FAILED,
}

#: Which audit actions one submission's durable trail can consist of.
SUBMISSION_TRAIL_ACTIONS: tuple[str, ...] = ("draft_edit", SUBMISSION_OUTCOME_ACTION)

#: The recorded outcomes that prove this submission will never publish.
TERMINAL_NON_PUBLICATION_OUTCOMES: frozenset[str] = frozenset(
    {
        SUBMISSION_OUTCOME_INPUT_REJECTED,
        SUBMISSION_OUTCOME_STALE,
        SUBMISSION_OUTCOME_UNCHANGED,
        SUBMISSION_OUTCOME_VALIDATION_FAILED,
        SUBMISSION_OUTCOME_PREPARE_FAILED,
        SUBMISSION_OUTCOME_ACTIVATE_FAILED,
        SUBMISSION_OUTCOME_PERSIST_FAILED,
    }
)

#: The bounded durable-state code each terminal outcome reports.
TERMINAL_NON_PUBLICATION_STATES: dict[str, str] = {
    SUBMISSION_OUTCOME_INPUT_REJECTED: "submission_input_rejected",
    SUBMISSION_OUTCOME_STALE: "submission_refused_stale",
    SUBMISSION_OUTCOME_UNCHANGED: "submission_no_publication_needed",
    SUBMISSION_OUTCOME_VALIDATION_FAILED: "submission_validation_failed",
    SUBMISSION_OUTCOME_PREPARE_FAILED: "submission_prepare_failed",
    SUBMISSION_OUTCOME_ACTIVATE_FAILED: "submission_activation_failed",
    SUBMISSION_OUTCOME_PERSIST_FAILED: "submission_persist_failed",
}

#: The bounded durable-state codes that prove a settled, correctable ending.
TERMINAL_NON_PUBLICATION_STATE_VALUES: frozenset[str] = frozenset(
    TERMINAL_NON_PUBLICATION_STATES.values()
)


class _RuntimePreparationFailure(Exception):
    """Marker: the successor's runtime binding could not be constructed."""


@dataclass(frozen=True)
class _ResidentReadState:
    """One bounded resident read: every retained row plus what could be read.

    ``evidence_read_failures`` names the services whose adoption-report page could
    not be read, so an unreadable read is reported as unproven rather than as a
    population that simply has no report yet.
    """

    registrations: tuple[ConsumerRegistrationState, ...]
    evidence: tuple[ResidentSettingsEvidence, ...]
    registration_read_failed: bool = False
    evidence_read_failures: frozenset[str] = frozenset()


class AutomationSettingsPublicationError(RuntimeError):
    """One bounded, secret-free failure of a focused settings publication."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 409,
        stage: str = "activate",
        durable_state: str = "active_preserved",
        side_effects: str = "none",
        revision_id: str | None = None,
        next_action: str = "refresh the current Active settings and review before saving again",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.stage = stage
        self.durable_state = durable_state
        self.side_effects = side_effects
        self.revision_id = revision_id
        self.next_action = next_action

    @property
    def details(self) -> dict[str, object]:
        details: dict[str, object] = {
            "stage": self.stage,
            "durableState": self.durable_state,
            "sideEffects": self.side_effects,
            "retrySafe": True,
            "nextAction": self.next_action,
        }
        if self.revision_id is not None:
            details["revisionId"] = self.revision_id
        return details


class AutomationSettingsService:
    """Read the four-field projection and publish one checked successor."""

    def __init__(
        self,
        configuration_service: ManagedConfigurationService,
        *,
        resident_repository=None,
        expected_schema_version: int | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = configuration_service
        self._residents = resident_repository
        self._expected_schema_version = expected_schema_version
        self._clock = clock or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Read (zero configuration, Provider, Task/Job or Storage effects)
    # ------------------------------------------------------------------

    def read(self) -> dict[str, object]:
        """The published target, the four field metadata and consumer adoption."""

        target = self._published_target(required=False)
        now = self._clock()
        consumers = (
            self._consumer_projections(target, now) if target is not None else _unavailable()
        )
        document: dict[str, object] = {
            "sideEffects": "none",
            "asOf": now.isoformat(),
            "configRecheckSeconds": CONFIG_RECHECK_SECONDS,
            "fields": [_field_projection(path) for path in ENGINE_FIELD_PATHS],
            "target": target.as_document() if target is not None else None,
            "consumers": consumers,
            # The collective claim covers only the resident *cadence* consumers:
            # the API-local capacity evidence is a different basis and must not
            # gate (or inflate) a polling-adoption statement.
            "adoption": adoption_summary(
                tuple(value for key, value in consumers.items() if key in RELEVANT_CONSUMERS)
            ),
        }
        if target is None:
            document["unavailable"] = self._unavailable_document()
        return document

    def _unavailable_document(self) -> dict[str, object]:
        active = None
        try:
            active = self._config.active()
        except Exception:
            active = None
        if active is None and self._config.has_managed_activation():
            return {
                "reason": "active_missing",
                "durableState": "managed_active_unavailable",
                "nextAction": (
                    "inspect configuration status and stage a recovery Draft; no new unsafe "
                    "admission or emission happens until a valid Active exists"
                ),
            }
        return {
            "reason": "active_missing",
            "durableState": "no_active_configuration",
            "nextAction": (
                "complete first setup, validate the Draft and activate it, then publish these "
                "engine settings"
            ),
        }

    def _published_target(self, *, required: bool) -> PublishedEngineTarget | None:
        try:
            active = self._config.active()
        except Exception as error:
            if required:
                raise AutomationSettingsPublicationError(
                    "automation_settings_unavailable",
                    "the managed Active configuration is unavailable",
                    status=503,
                    stage="read",
                    durable_state="managed_active_unavailable",
                    next_action=(
                        "restore the Active configuration and refresh settings before saving"
                    ),
                ) from error
            return None
        if active is None:
            if required:
                raise AutomationSettingsPublicationError(
                    "automation_settings_unavailable",
                    "no Active configuration exists; engine settings cannot be published",
                    status=409,
                    stage="read",
                    durable_state="no_active_configuration",
                    next_action=(
                        "complete first setup and activate a configuration before publishing "
                        "engine settings"
                    ),
                )
            return None
        self._config.verify_integrity(active)
        values = engine_values_from_document(active.document)
        if values is None:
            if required:
                raise AutomationSettingsPublicationError(
                    "automation_settings_invalid",
                    "the Active configuration does not carry readable Automation engine settings",
                    status=409,
                    stage="read",
                    durable_state="active_preserved",
                    next_action=(
                        "correct the Automation engine settings in the managed configuration, "
                        "then save again"
                    ),
                )
            return None
        return PublishedEngineTarget(
            revision_id=active.revision_id,
            revision_version=active.revision_sequence or active.version,
            digest=active.digest,
            values=values,
        )

    # ------------------------------------------------------------------
    # Checked Save
    # ------------------------------------------------------------------

    def save(
        self,
        payload: object,
        *,
        actor: str,
        expected_revision_id: str | None = None,
        expected_version: int | None = None,
        expected_digest: str | None = None,
        submission_id: str | None = None,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
    ) -> dict[str, object]:
        """Publish exactly these four fields from the checked Active.

        The command is deliberately narrow: it validates the submitted values,
        creates a successor Draft from the observed Active, applies only the four
        fields, validates the whole candidate, prepares the runtime binding and
        only then lets the existing activation boundary publish it atomically.  A
        preparation failure therefore cannot leave the persisted Active ahead of
        the process binding.  A no-op submission publishes nothing and reports
        the unchanged target.

        A request refused by the four-field *input* validation still terminates,
        and it terminates without ever owning a revision.  Its bounded content
        fingerprint is recorded before the refusal is returned, so a lost
        rejection response can be reconciled by the exact same identity without
        requiring that payload to pass publication validation again.  The refusal
        semantics themselves are unchanged: nothing is published, no Draft is
        created and no work is admitted.
        """

        identity = normalize_submission_id(submission_id)
        try:
            normalized = normalize_engine_setting_edits(payload)
        except AutomationEngineSettingsError as error:
            self._record_input_rejection(
                actor=actor, identity=identity, request=payload, error=error
            )
            raise
        target = self._published_target(required=True)
        assert target is not None  # narrow type for the reader
        current_values = target.values.as_field_map()
        if all(current_values[path] == normalized[path] for path in ENGINE_FIELD_PATHS):
            # An unchanged Save must not admit work, manufacture a publication or
            # fabricate adoption evidence.  It reports the exact unchanged target.
            #
            # It is still a *terminal, durable* outcome for this request: it wrote
            # nothing, so a reconciliation that arrives after a lost response must
            # be able to clear the resubmission block deliberately instead of
            # staying unresolved forever.
            self._record_submission_outcome(
                actor=actor,
                identity=identity,
                outcome=SUBMISSION_OUTCOME_UNCHANGED,
                normalized=normalized,
                target=target,
                stage="unchanged",
                next_action="none; the submitted values already match the published target",
            )
            return {
                "published": False,
                "unchanged": True,
                "sideEffects": "none",
                "submissionId": identity,
                "target": target.as_document(),
                "nextAction": "none; the submitted values already match the published target",
            }
        if (
            (expected_revision_id is not None and expected_revision_id != target.revision_id)
            or (expected_version is not None and expected_version != target.revision_version)
            or (expected_digest is not None and expected_digest != target.digest)
        ):
            # The refusal is proven before any Draft exists, so there is no
            # revision whose own evidence could ever resolve it.  The terminal
            # outcome is therefore recorded against this exact submission
            # identity here; otherwise a lost refusal response would leave the
            # operator with a permanently blocked form and no way back.
            self._record_submission_outcome(
                actor=actor,
                identity=identity,
                outcome=SUBMISSION_OUTCOME_STALE,
                normalized=normalized,
                target=target,
                stage="compose",
                next_action=(
                    "refresh the current published values, review the difference and save again"
                ),
                extra={
                    "expectedRevisionId": expected_revision_id,
                    "expectedDigest": expected_digest,
                    "currentRevisionId": target.revision_id,
                    "currentDigest": target.digest,
                },
            )
            raise AutomationSettingsPublicationError(
                "automation_settings_stale",
                "the published settings changed since this form was read; nothing was published",
                stage="compose",
                durable_state="active_preserved",
                next_action=(
                    "refresh the current published values, review the difference and save again"
                ),
            )

        before = {path: current_values[path] for path in ENGINE_FIELD_PATHS}
        try:
            return self._compose_validate_publish(
                normalized=normalized,
                identity=identity,
                actor=actor,
                target=target,
                before=before,
                before_publish=before_publish,
            )
        except AutomationSettingsPublicationError as error:
            # Every bounded failure of this exact submission is durably terminal:
            # it wrote nothing, or it left an unpublished revision behind.  The
            # record is what lets a lost failure response be reconciled into a
            # correctable state instead of a permanently blocked form.
            self._record_submission_outcome(
                actor=actor,
                identity=identity,
                outcome=SUBMISSION_OUTCOME_BY_CODE.get(
                    error.code,
                    SUBMISSION_OUTCOME_BY_STAGE.get(error.stage, SUBMISSION_OUTCOME_PERSIST_FAILED),
                ),
                normalized=normalized,
                target=target,
                stage=error.stage,
                next_action=error.next_action,
                extra={
                    "code": error.code,
                    "revisionId": error.revision_id,
                    "durableState": error.durable_state,
                },
            )
            raise
        except (ConfigurationVersionConflict, ConfigurationActivationConflict):
            # A concurrent writer won: this submission provably did not publish.
            self._record_submission_outcome(
                actor=actor,
                identity=identity,
                outcome=SUBMISSION_OUTCOME_STALE,
                normalized=normalized,
                target=target,
                stage="compose",
                next_action=(
                    "refresh the current published values, review the difference and save again"
                ),
            )
            raise

    def _compose_validate_publish(
        self,
        *,
        normalized: dict[str, float | int],
        identity: str | None,
        actor: str,
        target: PublishedEngineTarget,
        before: dict[str, float | int],
        before_publish: Callable[[ManagedConfigurationRevision], object] | None,
    ) -> dict[str, object]:
        """Compose, validate and publish one focused successor.

        Splitting this out of :meth:`save` keeps the terminal-outcome recording
        in one place for every bounded failure stage while the success path stays
        the single shared checked publication.
        """

        try:
            draft = self._config.create_successor_draft(
                actor=actor,
                expected_active_revision_id=target.revision_id,
                expected_active_version=target.revision_version,
                expected_active_digest=target.digest,
            )
        except (ConfigurationVersionConflict, RuntimeSnapshotUnavailable):
            raise
        except Exception as error:
            raise AutomationSettingsPublicationError(
                "automation_settings_persistence_failed",
                "the settings successor could not be created; the previous Active remains in use",
                status=503,
                stage="persist",
                durable_state="active_preserved",
                next_action="check configuration persistence health, then save again",
            ) from error

        document = copy.deepcopy(dict(draft.document))
        automation = document.get("automation")
        if not isinstance(automation, dict):
            automation = {}
            document["automation"] = automation
        for path in ENGINE_FIELD_PATHS:
            automation[path.split(".", 1)[1]] = normalized[path]
        _reject_literal_secrets(document)
        try:
            edited = self._config.edit_draft(
                draft.revision_id,
                document,
                expected_version=draft.version,
                actor=actor,
                audit_context={
                    "kind": "system_settings",
                    "objectId": "automation_engine_settings",
                    "action": "focused_edit",
                    "routeObjectId": None,
                    "sourceObjectId": None,
                    "publishedFromRevisionId": target.revision_id,
                    # The submission identity is the reconciliation fence: only
                    # this request's own revision may certify it, so an older
                    # equal submission or a failed Draft never does.
                    "submissionId": identity,
                    "before": before,
                    "candidate": {path: normalized[path] for path in ENGINE_FIELD_PATHS},
                },
            )
        except Exception as error:
            raise AutomationSettingsPublicationError(
                "automation_settings_persistence_failed",
                "the settings successor could not be edited; the previous Active remains in use",
                status=503,
                stage="persist",
                durable_state="active_preserved",
                revision_id=draft.revision_id,
                next_action="check configuration persistence health, then save again",
            ) from error

        self._assert_focused_change(target, edited)
        validated = self._validate(edited)
        published = self._activate(
            validated, actor=actor, before_publish=before_publish, submission_id=identity
        )
        return {
            "published": True,
            "unchanged": False,
            "sideEffects": "configuration_only",
            "submissionId": identity,
            "revisionId": published.revision_id,
            "revisionVersion": (published.revision_sequence or published.version),
            "digest": published.digest,
            "publishedValues": {path: normalized[path] for path in ENGINE_FIELD_PATHS},
            "previousValues": before,
            "nextAction": (
                "the published target is authoritative; each live consumer adopts it at its "
                "next safe loop boundary and reports its own adopted values independently"
            ),
        }

    def _assert_focused_change(
        self,
        target: PublishedEngineTarget,
        edited: ManagedConfigurationRevision,
    ) -> None:
        """Fail closed unless only the four engine fields changed."""

        active = self._config.active()
        if active is None or active.revision_id != target.revision_id:
            raise AutomationSettingsPublicationError(
                "automation_settings_stale",
                "the published settings changed while this save was composing; "
                "nothing was published",
                stage="compose",
                durable_state="active_preserved",
                next_action="refresh the published values and save again",
            )
        before_document = copy.deepcopy(dict(active.document))
        after_document = copy.deepcopy(dict(edited.document))
        before_automation = before_document.get("automation")
        after_automation = after_document.get("automation")
        if isinstance(before_automation, dict) and isinstance(after_automation, dict):
            for path in ENGINE_FIELD_PATHS:
                key = path.split(".", 1)[1]
                before_automation[key] = after_automation.get(key)
        if _canonical(before_document) != _canonical(after_document):
            raise AutomationSettingsPublicationError(
                "automation_settings_out_of_scope",
                "the successor changes configuration outside the four engine settings; "
                "nothing was published",
                stage="compose",
                durable_state="active_preserved",
                next_action=(
                    "save only the four Automation engine settings; other settings keep their "
                    "own configuration journey"
                ),
            )

    def _validate(self, edited: ManagedConfigurationRevision) -> ManagedConfigurationRevision:
        try:
            validated = self._config.validate(edited.revision_id, actor="automation-settings")
        except Exception as error:
            raise AutomationSettingsPublicationError(
                "automation_settings_validation_failed",
                "the settings successor could not be validated; the previous Active remains in use",
                status=503,
                stage="validate",
                durable_state="active_preserved",
                revision_id=edited.revision_id,
                next_action="check configuration persistence health, then save again",
            ) from error
        if validated.status.value != "validated":
            first = str(validated.validation_errors[0]) if validated.validation_errors else ""
            raise AutomationSettingsPublicationError(
                "automation_settings_validation_failed",
                "the whole candidate configuration failed validation; the previous Active "
                "remains in use",
                status=422,
                stage="validate",
                durable_state="active_preserved",
                revision_id=validated.revision_id,
                next_action=(
                    f"correct the blocking configuration ({first[:240]}), then save again"
                    if first
                    else "correct the blocking configuration, then save again"
                ),
            )
        return validated

    def _activate(
        self,
        validated: ManagedConfigurationRevision,
        *,
        actor: str,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
        submission_id: str | None = None,
    ) -> ManagedConfigurationRevision:
        """Publish the validated successor *after* the caller prepared runtime.

        ``before_publish`` runs while the previous Active pointer is still
        authoritative, exactly like every other checked Save.  A preparation
        fault therefore raises before publication and leaves both the persisted
        Active and the process binding untouched.
        """

        failure: list[BaseException] = []

        def prepare(revision: ManagedConfigurationRevision) -> object:
            try:
                return before_publish(revision) if before_publish is not None else None
            except BaseException as error:  # noqa: BLE001 - re-raised as a marker below
                failure.append(error)
                raise _RuntimePreparationFailure from error

        try:
            return self._config.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor=actor,
                before_publish=prepare if before_publish is not None else None,
            )
        except _RuntimePreparationFailure as error:
            # The runtime binding could not be constructed for the successor, so
            # the pointer was never advanced: Active and the process binding are
            # both unchanged and the operator gets a bounded preparation stage.
            raise AutomationSettingsPublicationError(
                "automation_settings_runtime_failed",
                "the successor configuration could not be bound to the runtime; the previous "
                "Active remains in use",
                status=503,
                stage="prepare",
                durable_state="active_preserved",
                side_effects=(
                    "successor_draft_and_read_only_evidence_retained; Active pointer unchanged"
                ),
                revision_id=validated.revision_id,
                next_action=(
                    "correct the runtime configuration, refresh the published values and save again"
                ),
            ) from (failure[0] if failure else error)
        except Exception as error:
            from mediaflow.domain.configuration_management import (
                ConfigurationActivationConflict,
            )

            if isinstance(error, (ConfigurationVersionConflict, ConfigurationActivationConflict)):
                raise
            raise AutomationSettingsPublicationError(
                "automation_settings_activation_failed",
                "the settings successor could not be published; the previous Active remains in use",
                status=503,
                stage="activate",
                durable_state="active_preserved",
                revision_id=validated.revision_id,
                next_action="check configuration persistence health, then save again",
            ) from error

    def _record_input_rejection(
        self,
        *,
        actor: str,
        identity: str | None,
        request: object,
        error: AutomationEngineSettingsError,
    ) -> None:
        """Persist the terminal refusal of a submission that never normalised.

        The exact four values cannot be persisted here: they may be booleans,
        strings, fractional integers, non-finite numbers or an out-of-scope key,
        and copying them would either fail the bounded-ledger contract or store
        arbitrary operator input.  What is durable instead is a bounded,
        secret-free *content fingerprint* of the request plus the rejection code
        and field.  That is enough to prove that this actor's exact request ended
        here — a different payload for the same identity contradicts the record
        and stays unresolved — while keeping strict validation and never letting
        reconciliation re-publish the rejected values.
        """

        if identity is None:
            return
        fingerprint = submission_request_fingerprint(request)
        if fingerprint is None:
            return
        self._record_submission_outcome(
            actor=actor,
            identity=identity,
            outcome=SUBMISSION_OUTCOME_INPUT_REJECTED,
            normalized=None,
            target=None,
            stage="normalize",
            next_action=(
                f"correct the reported value ({error.code})"
                + (f" for {error.field}" if error.field else "")
                + ", then save deliberately again"
            ),
            extra={
                "requestFingerprint": fingerprint,
                "code": error.code,
                "field": error.field,
                "message": error.message[:240],
            },
        )

    def _record_submission_outcome(
        self,
        *,
        actor: str,
        identity: str | None,
        outcome: str,
        normalized: Mapping[str, Any] | None,
        target: PublishedEngineTarget | None,
        stage: str,
        next_action: str,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """Persist the terminal, non-publication outcome of one submission.

        This is *evidence about this request*, not a setting and not authority:
        it carries only the submission identity, the four values that were
        submitted, the stage that ended the request and a bounded next action.
        It is written best-effort — a failure to record it must never change the
        answer the operator receives — and it can only ever resolve the one
        actor/submission pair it names, so a later equal publication by another
        writer still cannot certify this request.

        A submission with no identity cannot be fenced, so nothing is recorded:
        such a request must stay unresolved rather than become resumable.
        """

        if identity is None:
            return
        repository = self._config.repository
        record = getattr(repository, "record_configuration_audit", None)
        if not callable(record):
            return
        try:
            from mediaflow.domain.configuration_management import (
                ConfigurationChangeAudit,
                ConfigurationObjectKind,
            )

            after: dict[str, object] = {
                "objectChange": {
                    "kind": "system_settings",
                    "objectId": "automation_engine_settings",
                    "action": "focused_edit",
                    "submissionId": identity,
                    "outcome": outcome,
                    "stage": stage,
                    **(
                        {"candidate": {path: normalized[path] for path in ENGINE_FIELD_PATHS}}
                        if normalized is not None
                        else {}
                    ),
                    "publishedRevisionId": (target.revision_id if target is not None else None),
                    "publishedRevisionDigest": (target.digest if target is not None else None),
                    "nextAction": next_action,
                    **(dict(extra) if extra is not None else {}),
                }
            }
            record(
                ConfigurationChangeAudit(
                    str(uuid4()),
                    ConfigurationObjectKind.SYSTEM_SETTINGS,
                    identity,
                    SUBMISSION_OUTCOME_ACTION,
                    {},
                    after,
                    self._clock(),
                    actor,
                )
            )
        except Exception:
            # The bounded failure answer is already determined; losing the
            # reconciliation record must not turn it into a different error.  An
            # unrecorded terminal outcome stays unresolved, which is the safe
            # direction (it keeps the resubmission block in place).
            return

    # ------------------------------------------------------------------
    # Reconciliation of an unknown submission
    # ------------------------------------------------------------------

    def reconcile(
        self,
        payload: object,
        *,
        actor: str,
        submission_id: str | None = None,
    ) -> dict[str, object]:
        """Resolve one *identified* focused submission from durable evidence.

        Four equal values prove nothing: the current Active may already have
        carried them, and an older equal submission or a failed Draft is not a
        publication of this request.  The reconciliation therefore follows this
        request's own durable trail:

        * the ``draft_edit`` audit that carries this submission identity names the
          revision this request edited, and that revision's own status decides
          whether *it* published;
        * a persisted terminal-outcome record proves a termination that never
          owned a revision at all (a four-field input refusal, a stale refusal
          before any Draft, a no-op, or a persist/validate/prepare/activate
          fault).

        A submission whose own evidence cannot be located or read completely is
        reported as ``unresolved`` — that state keeps the resubmission block in
        place, because an absent audit while publication is still possible is not
        permission to submit again.

        Looking the outcome up is deliberately *separate* from publishing: a
        request refused by four-field input validation (for example the text
        ``3.5`` for an integer field) is precisely the request whose outcome the
        operator most needs proven, so this read must identify it without
        requiring its payload to pass publication validation again.  Strict
        validation is preserved everywhere a value could be published.
        """

        identity = normalize_submission_id(submission_id)
        # The bounded content evidence of the submitted request is computed from
        # the *raw* payload, so it distinguishes `3.5`, `"3.5"`, `true`, a missing
        # field and an out-of-scope key exactly as the request carried them.
        fingerprint = submission_request_fingerprint(payload)
        try:
            normalized: dict[str, float | int] | None = normalize_engine_setting_edits(payload)
            rejection: AutomationEngineSettingsError | None = None
        except AutomationEngineSettingsError as error:
            normalized = None
            rejection = error
        target = self._published_target(required=False)
        current = target.values.as_field_map() if target is not None else {}
        matches_current = (
            normalized is not None
            and bool(current)
            and all(current.get(path) == normalized[path] for path in ENGINE_FIELD_PATHS)
        )
        submitted_values = (
            {path: normalized[path] for path in ENGINE_FIELD_PATHS}
            if normalized is not None
            else None
        )
        if identity is None:
            # Without the submission identity this read can only describe the
            # current publication.  It is never reported as this request's
            # outcome, so the caller must not treat it as a resubmission licence.
            return {
                "sideEffects": "none",
                "submissionId": None,
                "state": EngineSubmissionState.UNRESOLVED.value,
                "committed": False,
                "committedRevisionId": None,
                "currentValuesMatchSubmission": matches_current,
                "submittedValues": submitted_values,
                "currentValues": current,
                "evidence": None,
                "target": target.as_document() if target is not None else None,
                "nextAction": (
                    "this submission identity is unavailable, so its outcome cannot be proven; "
                    "inspect the published target and publish deliberately again only if it does "
                    "not carry your values"
                ),
            }
        evidence = self._submission_evidence(
            actor, identity, normalized=normalized, fingerprint=fingerprint
        )
        state = evidence.pop("state")
        committed = state in COMMITTED_SUBMISSION_STATES
        if state == EngineSubmissionState.COMMITTED.value:
            next_action = (
                "this exact submission is the current published target; no further retry is needed"
            )
        elif state == EngineSubmissionState.SUPERSEDED.value:
            next_action = (
                "this exact submission published and a later publication has replaced it; "
                "review the current target before saving your values again"
            )
        elif state == EngineSubmissionState.NOT_COMMITTED.value:
            terminal = evidence.get("durableState")
            if terminal == TERMINAL_NON_PUBLICATION_STATES[SUBMISSION_OUTCOME_INPUT_REJECTED]:
                rejected_field = evidence.get("field")
                next_action = (
                    "this exact submission was refused before publication"
                    + (f" ({rejected_field})" if isinstance(rejected_field, str) else "")
                    + "; correct that value and save deliberately again"
                )
            elif terminal in TERMINAL_NON_PUBLICATION_STATE_VALUES:
                next_action = (
                    "this exact submission is settled and did not change the published settings; "
                    "review the current values and save your corrected values deliberately"
                )
            else:
                next_action = (
                    "this exact submission terminated without publishing; correct the reported "
                    "condition and save deliberately again"
                )
        else:
            next_action = (
                "no terminal durable outcome can be proven for this exact submission; do not "
                "resubmit until the published target and its audit evidence are readable"
            )
        return {
            "sideEffects": "none",
            "submissionId": identity,
            "state": state,
            "committed": committed,
            # True only for the committed/superseded distinction: a superseded
            # submission published but is not what runtime consumes today.
            "currentValuesMatchSubmission": matches_current,
            "committedRevisionId": evidence.get("revisionId") if committed else None,
            "submittedValues": submitted_values,
            "currentValues": current,
            "evidence": evidence or None,
            "rejection": _rejection_detail(rejection, evidence),
            "target": target.as_document() if target is not None else None,
            "nextAction": next_action,
        }

    def _submission_evidence(
        self,
        actor: str,
        identity: str,
        *,
        normalized: Mapping[str, Any] | None,
        fingerprint: str | None,
    ) -> dict[str, object]:
        """Walk this submission's own durable trail, newest first.

        The walk is targeted at the audit ledger through its monotonic
        ``sequence`` cursor rather than a bounded recent window, so a submission
        made long before later activity is still located.  Only an audit that
        carries *this* submission identity for *this* actor counts; a `draft_edit`
        with equal values but another (or no) identity is a different request and
        can never certify this one.
        """

        repository = self._config.repository
        targeted = getattr(repository, "list_command_audits_before", None)
        latest = getattr(repository, "latest_command_audit_sequence", None)
        recent = getattr(repository, "list_recent_command_audits", None)
        audits: list[Any] = []
        complete = False
        if callable(targeted) and callable(latest):
            marker = None
            try:
                marker = int(latest()) + 1
                while True:
                    page = targeted(SUBMISSION_TRAIL_ACTIONS, before_sequence=marker, limit=200)
                    audits.extend(page)
                    if len(page) < 200:
                        complete = True
                        break
                    sequences = [
                        int(item.sequence) for item in page if getattr(item, "sequence", None)
                    ]
                    if not sequences:
                        break
                    next_marker = min(sequences)
                    if next_marker >= marker:
                        break
                    marker = next_marker
            except Exception:
                audits = []
                complete = False
        elif callable(recent):
            try:
                audits = list(recent(SUBMISSION_TRAIL_ACTIONS, limit=500))
            except Exception:
                audits = []
        if not audits:
            # Nothing durable names this submission.  If the ledger read was
            # incomplete, publication may still be in flight or recorded later,
            # so this stays unresolved; only a complete walk with no evidence at
            # all is the same unresolved answer for a different reason, and the
            # next action states it.
            return {
                "state": EngineSubmissionState.UNRESOLVED.value,
                "evidenceComplete": complete,
                "identityMatched": False,
            }
        matched: list[tuple[Any, Mapping[str, Any]]] = []
        for audit in audits:
            if audit.actor != actor:
                continue
            change = audit.after.get("objectChange")
            if not isinstance(change, dict):
                continue
            if change.get("objectId") != "automation_engine_settings":
                continue
            if change.get("submissionId") != identity:
                continue
            if audit.action == SUBMISSION_OUTCOME_ACTION:
                # A terminal-outcome record proves the content it recorded.  An
                # input refusal can only record a fingerprint (the values were
                # never normalised), while every other outcome records the
                # normalised four values.
                recorded_fingerprint = change.get("requestFingerprint")
                if isinstance(recorded_fingerprint, str):
                    if recorded_fingerprint != fingerprint:
                        return self._contradiction(audit, complete)
                    matched.append((audit, change))
                    continue
                candidate = change.get("candidate")
                if not isinstance(candidate, dict) or normalized is None:
                    # The durable record names different (or unusable) values than
                    # the request being reconciled: nothing is certified.
                    return self._contradiction(audit, complete)
                if not all(candidate.get(path) == normalized[path] for path in ENGINE_FIELD_PATHS):
                    return self._contradiction(audit, complete)
                matched.append((audit, change))
                continue
            candidate = change.get("candidate")
            if not isinstance(candidate, dict) or normalized is None:
                return self._contradiction(audit, complete)
            if not all(candidate.get(path) == normalized[path] for path in ENGINE_FIELD_PATHS):
                # The same identity submitted different values: the durable
                # records contradict each other, so nothing is certified.
                return self._contradiction(audit, complete)
            matched.append((audit, change))
        if not matched:
            return {
                "state": EngineSubmissionState.UNRESOLVED.value,
                "evidenceComplete": complete,
                "identityMatched": False,
            }
        # Positive publication evidence always wins over a later terminal record:
        # a submission that published must never be reported as "not committed"
        # merely because a subsequent statement about the same identity exists.
        for audit, _change in matched:
            if audit.action != SUBMISSION_OUTCOME_ACTION:
                state = self._revision_submission_state(audit, complete)
                if state.get("state") in COMMITTED_SUBMISSION_STATES:
                    return state
        audit, change = matched[0]
        if audit.action == SUBMISSION_OUTCOME_ACTION:
            return self._terminal_outcome_state(audit, change, complete)
        return self._revision_submission_state(audit, complete)

    @staticmethod
    def _contradiction(audit: Any, complete: bool) -> dict[str, object]:
        """One identity's durable evidence disagrees with the request."""

        return {
            "state": EngineSubmissionState.UNRESOLVED.value,
            "evidenceComplete": complete,
            "identityMatched": True,
            "auditId": audit.audit_id,
            "revisionId": audit.object_id,
            "occurredAt": audit.occurred_at.isoformat(),
            "durableState": "submission_values_contradict_evidence",
        }

    @staticmethod
    def _terminal_outcome_state(
        audit: Any, change: Mapping[str, Any], complete: bool
    ) -> dict[str, object]:
        """One submission's recorded terminal non-publication.

        The record is authoritative only for the exact actor/submission pair the
        walk already matched, and it states that this request ended without
        publishing.  It is therefore a *correctable* outcome: the page can clear
        the resubmission block and let the operator review the current values and
        save deliberately.
        """

        outcome = str(change.get("outcome") or "")
        if outcome not in TERMINAL_NON_PUBLICATION_OUTCOMES:
            return {
                "state": EngineSubmissionState.UNRESOLVED.value,
                "evidenceComplete": complete,
                "identityMatched": True,
                "auditId": audit.audit_id,
                "occurredAt": audit.occurred_at.isoformat(),
                "durableState": "submission_outcome_unknown",
            }
        stage = str(change.get("stage") or "")
        evidence: dict[str, object] = {
            "state": EngineSubmissionState.NOT_COMMITTED.value,
            "evidenceComplete": complete,
            "identityMatched": True,
            "auditId": audit.audit_id,
            "occurredAt": audit.occurred_at.isoformat(),
            "submissionOutcome": outcome,
            "failureStage": stage or None,
            "durableState": TERMINAL_NON_PUBLICATION_STATES[outcome],
            "nextAction": str(change.get("nextAction") or "") or None,
            "targetRevisionId": change.get("publishedRevisionId"),
        }
        for key in ("field", "message", "code"):
            value = change.get(key)
            if isinstance(value, str) and value:
                evidence[key] = value[:240]
        revision_id = change.get("revisionId")
        if isinstance(revision_id, str) and revision_id:
            # A persist/validate/prepare/activate fault may leave an unpublished
            # successor behind; naming it keeps the evidence diagnosable without
            # ever presenting that revision as a publication.
            evidence["revisionId"] = revision_id
        code = change.get("code")
        if isinstance(code, str) and code:
            evidence["failureCode"] = code
        return evidence

    def _revision_submission_state(self, audit: Any, complete: bool) -> dict[str, object]:
        """Decide one submission's outcome from its own revision's evidence."""

        revision_id = str(audit.object_id)
        evidence: dict[str, object] = {
            "auditId": audit.audit_id,
            "revisionId": revision_id,
            "occurredAt": audit.occurred_at.isoformat(),
            "evidenceComplete": complete,
            "identityMatched": True,
        }
        try:
            revision = self._config.require(revision_id)
        except LookupError:
            # The audit names a revision durable authority no longer holds: its
            # outcome cannot be proven, so this stays unresolved.
            evidence["durableState"] = "submission_revision_unreadable"
            return {**evidence, "state": EngineSubmissionState.UNRESOLVED.value}
        except Exception:
            evidence["durableState"] = "submission_revision_unreadable"
            return {**evidence, "state": EngineSubmissionState.UNRESOLVED.value}
        evidence["revisionStatus"] = revision.status.value
        if revision.status.value == "active":
            return {**evidence, "state": EngineSubmissionState.COMMITTED.value}
        if revision.status.value == "superseded":
            # Published, but a later immutable Active replaced it.  The
            # revision is still readable evidence that this exact submission did
            # publish, so it is not a rejection.
            return {**evidence, "state": EngineSubmissionState.SUPERSEDED.value}
        if revision.status.value == "draft" and revision.validation_errors:
            # A terminal validation rejection: this revision cannot publish, and
            # a later equal publication by another writer is not this request's
            # success.
            evidence["durableState"] = "submission_validation_failed"
            evidence["validationErrors"] = [
                str(item)[:240] for item in revision.validation_errors[:3]
            ]
            return {**evidence, "state": EngineSubmissionState.NOT_COMMITTED.value}
        evidence["durableState"] = "submission_revision_unpublished"
        return {**evidence, "state": EngineSubmissionState.UNRESOLVED.value}

    # ------------------------------------------------------------------
    # Consumer adoption readback
    # ------------------------------------------------------------------

    def _consumer_projections(
        self, target: PublishedEngineTarget, now: datetime
    ) -> dict[str, dict[str, object]]:
        projections: dict[str, dict[str, object]] = {}
        state = self._resident_state()
        for service, field_path in CONSUMER_POLLING_FIELDS.items():
            service_registrations = tuple(
                item for item in state.registrations if item.service == service
            )
            service_evidence = tuple(item for item in state.evidence if item.service == service)
            projections[service] = evaluate_consumer_adoption(
                service=service,
                field_path=field_path,
                target=target,
                registrations=service_registrations,
                evidence=service_evidence,
                now=now,
                expected_schema_version=self._schema_version(),
                # Freshness is a property of the whole population this read
                # observed, so the threshold comes from every registration of
                # the service — including a stopped or stale one whose own
                # heartbeat interval is still the deployment's real interval.
                stale_threshold_seconds=self._stale_threshold(service_registrations),
                registration_read_failed=state.registration_read_failed,
                evidence_read_failed=service in state.evidence_read_failures,
            )
        # Surface API-local evidence for the two capacity/observation fields so
        # the page never presents them as a resident process's cadence.
        projections["api"] = {
            "service": "api",
            "field": CAPACITY_FIELD_PATHS[0],
            "fields": list(CAPACITY_FIELD_PATHS),
            "publishedValues": {
                path: target.values.field_value(path) for path in CAPACITY_FIELD_PATHS
            },
            "adopted": False,
            "basis": "api_local",
            "instanceCount": 0,
            "instances": [],
            "explanation": (
                "容量与失效判定由准入/观察边界各自读取当前 Active,不是常驻进程轮询值;"
                "本页只显示发布目标,不声称某个进程已采用。"
            ),
        }
        return projections

    def _resident_state(self) -> _ResidentReadState:
        """Every retained registration/report row plus its liveness *now*.

        The registration lifecycle is the membership authority: registrations are
        never filtered or deleted here.  Each row gets its freshness derived at
        this read's timestamp, so the current population is exactly the live
        subset.  A read failure is recorded instead of being flattened into an
        empty population, because "nobody is registered" and "this read could not
        answer" are different operator situations.
        """

        repository = self._residents
        if repository is None:
            return _ResidentReadState((), (), registration_read_failed=True)
        try:
            rows = repository.list_resident_services()
        except Exception:
            return _ResidentReadState((), (), registration_read_failed=True)
        registrations: list[ConsumerRegistrationState] = []
        for row in rows:
            if not isinstance(row, ResidentServiceRegistration):
                continue
            if row.service not in RELEVANT_CONSUMERS:
                continue
            registrations.append(
                ConsumerRegistrationState(
                    service=row.service,
                    instance_id=row.instance_id,
                    status=self._liveness(row),
                    runtime_schema_version=row.runtime_schema_version,
                    heartbeat_interval_seconds=row.heartbeat_interval_seconds,
                )
            )
        evidence: list[ResidentSettingsEvidence] = []
        failures: set[str] = set()
        reader = getattr(repository, "list_resident_settings_adoption", None)
        if callable(reader):
            for service in RELEVANT_CONSUMERS:
                try:
                    evidence.extend(reader(service=service, limit=ADOPTION_EVIDENCE_LIMIT))
                except Exception:
                    # One unreadable evidence page is unproven adoption for that
                    # service, never silently "no report exists".
                    failures.add(service)
        return _ResidentReadState(
            tuple(registrations),
            tuple(evidence),
            evidence_read_failures=frozenset(failures),
        )

    def _liveness(self, row: ResidentServiceRegistration) -> str:
        from mediaflow.domain.resident_services import (
            ResidentServiceStatus,
            evaluate_resident_service_status,
        )

        status = evaluate_resident_service_status(row, self._clock())
        if status is ResidentServiceStatus.LIVE:
            return "live"
        if status is ResidentServiceStatus.STOPPED:
            return "stopped"
        return "stale"

    def _schema_version(self) -> int:
        if self._expected_schema_version is not None:
            return int(self._expected_schema_version)
        repository = self._residents
        schema = getattr(repository, "schema_version", None)
        if isinstance(schema, int) and not isinstance(schema, bool):
            return schema
        return 0

    @staticmethod
    def _stale_threshold(registrations: tuple[ConsumerRegistrationState, ...]) -> float:
        intervals = [
            item.heartbeat_interval_seconds
            for item in registrations
            if item.heartbeat_interval_seconds > 0
        ]
        if not intervals:
            return resident_stale_threshold_seconds(5.0)
        return resident_stale_threshold_seconds(min(intervals))


def _unavailable() -> dict[str, dict[str, object]]:
    """No published target: an honest, non-zero, non-success projection."""

    return {
        service: {
            "service": service,
            "field": field_path,
            "publishedValue": None,
            "adopted": False,
            "instanceCount": 0,
            "instances": [],
            # No publication exists, so nothing about a consumer can be proved;
            # its retained history is still not silently dropped.
            "historyCount": 0,
            "history": [],
            "status": ConsumerAdoptionStatus.UNAVAILABLE.value,
            "durableState": "no_published_target",
            "nextAction": "publish a valid Active configuration before reading adoption",
        }
        for service, field_path in CONSUMER_POLLING_FIELDS.items()
    } | {
        "api": {
            "service": "api",
            "field": CAPACITY_FIELD_PATHS[0],
            "fields": list(CAPACITY_FIELD_PATHS),
            "publishedValues": {path: None for path in CAPACITY_FIELD_PATHS},
            "adopted": False,
            "basis": "api_local",
            "instanceCount": 0,
            "instances": [],
            "status": ConsumerAdoptionStatus.UNAVAILABLE.value,
        }
    }


def _field_projection(field_path: str) -> dict[str, object]:
    spec = ENGINE_FIELD_SPECS[field_path]
    return {
        "fieldPath": spec.field_path,
        "label": spec.label,
        "unit": spec.unit,
        "valueType": spec.value_type,
        "minimum": spec.minimum,
        "maximum": spec.maximum,
        "meaning": spec.meaning,
        "notMeaning": spec.not_meaning,
        "consumer": spec.consumer,
        "integer": spec.value_type == "integer",
    }


def _rejection_detail(
    rejection: AutomationEngineSettingsError | None, evidence: Mapping[str, Any]
) -> dict[str, str] | None:
    """The readable field error for a refused submission, if one is proven.

    The local normalisation failure is preferred because it is the same code the
    Save returned.  A caller that sends different (already corrected) content can
    still be told what the *durable* record rejected, because the record is
    authoritative for that exact submission.
    """

    if rejection is not None:
        return rejection.as_detail()
    if evidence.get("submissionOutcome") != SUBMISSION_OUTCOME_INPUT_REJECTED:
        return None
    detail: dict[str, str] = {}
    code = evidence.get("failureCode")
    if isinstance(code, str) and code:
        detail["code"] = code
    field = evidence.get("field")
    if isinstance(field, str) and field:
        detail["field"] = field
    message = evidence.get("message")
    if isinstance(message, str) and message:
        detail["message"] = message
    next_action = evidence.get("nextAction")
    if isinstance(next_action, str) and next_action:
        detail["nextAction"] = next_action
    return detail or None


def submission_request_fingerprint(request: object) -> str | None:
    """A bounded, secret-free fingerprint of one submitted settings request.

    Reconciliation needs to prove that the durable record belongs to the *same
    content* the operator submitted.  The published request is normalised before
    it is stored, but a request refused by input validation never is — `3.5`,
    `"3.5"`, `true`, `None`, a missing field and an out-of-scope key must still be
    distinguishable from each other and from an accepted submission.

    The fingerprint is therefore taken over a canonical encoding of the raw
    request, restricted to the bounded four-field surface so an oversized or
    hostile payload cannot be persisted through the audit ledger.  Arbitrary
    values are never copied into durable evidence or into the response: only this
    digest and the bounded rejection code/field are kept.
    """

    if not isinstance(request, Mapping):
        return None
    raw = request.get("settings", request)
    if not isinstance(raw, Mapping):
        return None
    if len(raw) > 16:
        return None
    encoded: dict[str, str] = {}
    for original_key, value in raw.items():
        key = str(original_key)
        if len(key) > 128:
            return None
        try:
            encoded[key] = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=True,
                default=repr,
            )
        except (TypeError, ValueError):
            encoded[key] = "<unencodable>"
        if len(encoded[key]) > 256:
            return None
    payload = json.dumps(encoded, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(payload.encode("utf-8")) > 8 * 1024:
        return None
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical(document: object) -> str:
    import json

    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "ADOPTION_EVIDENCE_LIMIT",
    "AutomationSettingsPublicationError",
    "AutomationSettingsService",
    "NON_ADOPTED_STATUSES",
    "RELEVANT_CONSUMERS",
    "SETTINGS_PUBLICATION_ACTION",
    "normalize_override_source",
]
