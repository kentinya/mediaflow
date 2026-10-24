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
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

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


class _RuntimePreparationFailure(Exception):
    """Marker: the successor's runtime binding could not be constructed."""


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
        """

        normalized = normalize_engine_setting_edits(payload)
        identity = normalize_submission_id(submission_id)
        target = self._published_target(required=True)
        assert target is not None  # narrow type for the reader
        current_values = target.values.as_field_map()
        if all(current_values[path] == normalized[path] for path in ENGINE_FIELD_PATHS):
            # An unchanged Save must not admit work, manufacture a publication or
            # fabricate adoption evidence.  It reports the exact unchanged target.
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
          revision this request edited;
        * that revision's own activation evidence decides whether *it* published;
        * the persisted ``validation_failed`` audit decides a terminal rejection.

        A submission whose own evidence cannot be located or read completely is
        reported as ``unresolved`` — that state keeps the resubmission block in
        place, because an absent audit while publication is still possible is not
        permission to submit again.
        """

        normalized = normalize_engine_setting_edits(payload)
        identity = normalize_submission_id(submission_id)
        target = self._published_target(required=False)
        current = target.values.as_field_map() if target is not None else {}
        matches_current = bool(current) and all(
            current.get(path) == normalized[path] for path in ENGINE_FIELD_PATHS
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
                "submittedValues": {path: normalized[path] for path in ENGINE_FIELD_PATHS},
                "currentValues": current,
                "evidence": None,
                "target": target.as_document() if target is not None else None,
                "nextAction": (
                    "this submission identity is unavailable, so its outcome cannot be proven; "
                    "inspect the published target and publish deliberately again only if it does "
                    "not carry your values"
                ),
            }
        evidence = self._submission_evidence(actor, identity, normalized)
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
            "submittedValues": {path: normalized[path] for path in ENGINE_FIELD_PATHS},
            "currentValues": current,
            "evidence": evidence or None,
            "target": target.as_document() if target is not None else None,
            "nextAction": next_action,
        }

    def _submission_evidence(
        self, actor: str, identity: str, normalized: Mapping[str, Any]
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
                    page = targeted(("draft_edit",), before_sequence=marker, limit=200)
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
                audits = list(recent(("draft_edit",), limit=500))
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
            candidate = change.get("candidate")
            if not isinstance(candidate, dict):
                continue
            if not all(candidate.get(path) == normalized[path] for path in ENGINE_FIELD_PATHS):
                # The same identity submitted different values: the durable
                # records contradict each other, so nothing is certified.
                return {
                    "state": EngineSubmissionState.UNRESOLVED.value,
                    "evidenceComplete": complete,
                    "identityMatched": True,
                    "auditId": audit.audit_id,
                    "revisionId": audit.object_id,
                    "occurredAt": audit.occurred_at.isoformat(),
                    "durableState": "submission_values_contradict_evidence",
                }
            return self._revision_submission_state(audit, complete)
        return {
            "state": EngineSubmissionState.UNRESOLVED.value,
            "evidenceComplete": complete,
            "identityMatched": False,
        }

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
        registrations, evidence = self._resident_state()
        for service, field_path in CONSUMER_POLLING_FIELDS.items():
            service_registrations = tuple(item for item in registrations if item.service == service)
            service_evidence = tuple(item for item in evidence if item.service == service)
            projections[service] = evaluate_consumer_adoption(
                service=service,
                field_path=field_path,
                target=target,
                registrations=service_registrations,
                evidence=service_evidence,
                now=now,
                expected_schema_version=self._schema_version(),
                stale_threshold_seconds=self._stale_threshold(service_registrations),
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

    def _resident_state(
        self,
    ) -> tuple[tuple[ConsumerRegistrationState, ...], tuple[ResidentSettingsEvidence, ...]]:
        repository = self._residents
        if repository is None:
            return ((), ())
        try:
            rows = repository.list_resident_services()
        except Exception:
            return ((), ())
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
        reader = getattr(repository, "list_resident_settings_adoption", None)
        if callable(reader):
            for service in RELEVANT_CONSUMERS:
                try:
                    evidence.extend(reader(service=service, limit=ADOPTION_EVIDENCE_LIMIT))
                except Exception:
                    continue
        return (tuple(registrations), tuple(evidence))

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
            "status": ConsumerAdoptionStatus.UNAVAILABLE.value,
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
