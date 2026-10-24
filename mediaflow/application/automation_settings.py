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
    CONFIG_RECHECK_SECONDS,
    CONSUMER_POLLING_FIELDS,
    ENGINE_FIELD_PATHS,
    ENGINE_FIELD_SPECS,
    NON_ADOPTED_STATUSES,
    ConsumerAdoptionStatus,
    ConsumerRegistrationState,
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

SETTINGS_PUBLICATION_ACTION = "automation_engine_settings_publish"


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
    ) -> dict[str, object]:
        """Publish exactly these four fields from the checked Active.

        The command is deliberately narrow: it validates the submitted values,
        creates a successor Draft from the observed Active, applies only the four
        fields, validates the whole candidate, prepares the runtime binding, and
        lets the existing activation boundary publish it atomically.  A no-op
        submission publishes nothing and reports the unchanged target.
        """

        normalized = normalize_engine_setting_edits(payload)
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
        published = self._activate(validated, actor=actor)
        return {
            "published": True,
            "unchanged": False,
            "sideEffects": "configuration_only",
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
        self, validated: ManagedConfigurationRevision, *, actor: str
    ) -> ManagedConfigurationRevision:
        try:
            return self._config.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor=actor,
            )
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
        submitted_revision_id: str | None = None,
    ) -> dict[str, object]:
        """Read back whether one focused submission actually published.

        Comparing four equal values alone proves nothing: the current Active may
        already have carried them.  A submission is only reported as committed
        when durable audit evidence for this actor's focused edit records the
        candidate *and* the current Active still carries it.
        """

        normalized = normalize_engine_setting_edits(payload)
        target = self._published_target(required=False)
        current = target.values.as_field_map() if target is not None else {}
        matches = bool(current) and all(
            current.get(path) == normalized[path] for path in ENGINE_FIELD_PATHS
        )
        evidence = self._focused_edit_evidence(actor, normalized)
        committed = bool(matches and evidence)
        if committed:
            next_action = "the submission is published; no further retry is needed"
        elif evidence and not matches:
            next_action = (
                "a matching submission was recorded but the current Active does not carry it; "
                "refresh the published values before deciding"
            )
        else:
            next_action = "no matching durable submission was observed; publish deliberately again"
        return {
            "sideEffects": "none",
            "submittedValues": {path: normalized[path] for path in ENGINE_FIELD_PATHS},
            "currentValues": current,
            "committed": committed,
            "evidence": evidence,
            "target": target.as_document() if target is not None else None,
            "nextAction": next_action,
        }

    def _focused_edit_evidence(
        self, actor: str, normalized: Mapping[str, Any]
    ) -> dict[str, object] | None:
        repository = self._config.repository
        reader = getattr(repository, "list_recent_command_audits", None)
        if not callable(reader):
            return None
        try:
            audits = reader(("draft_edit",), limit=200)
        except Exception:
            return None
        for audit in audits:
            if audit.actor != actor:
                continue
            change = audit.after.get("objectChange")
            if not isinstance(change, dict):
                continue
            if change.get("objectId") != "automation_engine_settings":
                continue
            candidate = change.get("candidate")
            if not isinstance(candidate, dict):
                continue
            if all(candidate.get(path) == normalized[path] for path in ENGINE_FIELD_PATHS):
                return {
                    "auditId": audit.audit_id,
                    "revisionId": audit.object_id,
                    "occurredAt": audit.occurred_at.isoformat(),
                }
        return None

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
