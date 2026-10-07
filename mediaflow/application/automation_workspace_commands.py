"""Focused Automation Task Definition publication (Slice 43, Task 43.1).

This module owns the narrow command and projection boundary the native V2
Automation workspace needs to maintain one Automation Task Definition without
orchestrating Draft/Validate/Activate as separate operator steps.

It deliberately composes the existing authorities instead of duplicating them:

* normalization, reference checks, whole-document validation, audit and
  optimistic concurrency stay in :class:`ConfigurationObjectService` /
  :class:`ManagedConfigurationService`, so a V2 Save can never accept, reject or
  normalize a field differently from V1, the API, the CLI or the runtime;
* publication is one checked atomic activation of an exact focused successor
  composed from the observed immutable Active.  The successor changes only the
  selected definition — every other configuration section and every sibling
  definition stays byte-identical — so publication cannot carry unrelated Draft
  edits, and the previously reviewed Storage/strategy/destination semantics of
  the Active snapshot are preserved unchanged;
* removal durably revokes applicable future unattended authority *before* the
  removal successor is published, so no window exists in which the definition is
  gone while its scheduled mutation authority is still live.  A revocation that
  precedes a failed publication is fail-closed and reported truthfully; grants,
  audits, occurrences, Jobs/Tasks/Results and admitted pins are never erased.

Reads (form opening, projections, schedule calculation) create no Draft, call no
Provider, start no scan/Job/Task/occurrence and mutate no Storage, and no
projection returns a secret value.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.domain.automation import AutomationTaskDefinition, AutomationTaskRunMode
from mediaflow.domain.configuration_management import (
    AutomationDefinitionSaveError,
    ConfigurationActivationConflict,
    ConfigurationObjectKind,
    ConfigurationVersionConflict,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.cron import CronExpression

MAX_DEFINITION_ID_LENGTH = 64
MAX_DEFINITION_NAME_LENGTH = 120
MAX_DEFINITION_SCOPE_LENGTH = AutomationTaskDefinition.MAX_SCOPE_LENGTH
MAX_DEFINITION_TIMEZONE_LENGTH = AutomationTaskDefinition.MAX_TIMEZONE_LENGTH
MAX_DEFINITION_ITEM_LIMIT = AutomationTaskDefinition.MAX_ITEM_LIMIT
MAX_DEFINITION_INTERVAL_SECONDS = AutomationTaskDefinition.MAX_INTERVAL_SECONDS
UPCOMING_RUN_LIMIT = 5
HISTORICAL_REVISION_SCAN_LIMIT = 200

#: Rows read per page when walking a definition's durable command trail. This
#: is a *page* size, not a window on the answer: the walk continues with a real
#: monotonic cursor until a short page proves the trail ended, so the bound
#: limits one query, never the amount of evidence that can be reconciled. It is
#: deliberately no larger than the smallest reader bound the repository offers,
#: so an incomplete read is always detectable rather than silently mistaken for
#: the end of the trail.
COMMAND_TRAIL_PAGE_SIZE = 200

AUTOMATION_DEFINITION_SECTION = "automationTaskDefinitions"

#: The exact typed-form surface one focused Automation definition command owns.
#: Aliases the legacy whole-document surface tolerates (``runMode``, ``limit``,
#: ``schedule``) are intentionally absent: the typed form owns canonical fields
#: only, so a browser request can never publish a second spelling of the same
#: concept.
AUTOMATION_DEFINITION_FORM_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "name",
        "enabled",
        "resourceLibraryId",
        "sourceScope",
        "mode",
        "itemLimit",
        "intervalSeconds",
        "cron",
        "timezone",
    }
)

#: Display defaults that mirror the real domain defaults for an omitted field.
AUTOMATION_DEFINITION_FORM_DEFAULTS: dict[str, object] = {
    "name": "",
    "enabled": False,
    "resourceLibraryId": "",
    "sourceScope": None,
    "mode": AutomationTaskRunMode.SCAN_ONLY.value,
    "itemLimit": 100,
    "intervalSeconds": 3600.0,
    "cron": None,
    "timezone": None,
}

_SAFE_DEFINITION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,63}$")


@dataclass(frozen=True)
class _DefinitionCommandAudit:
    """One durable Automation definition command's bounded audit evidence.

    ``revision_id`` is the Draft revision the command was edited into (the
    audit row's own ``object_id``); its publication is proven separately from
    that revision's activation evidence, never from today's Active pointer.
    """

    audit_id: str
    revision_id: str
    action: str
    occurred_at: str
    context: dict[str, object]


@dataclass(frozen=True)
class _DefinitionCommandEvidence:
    """The result of reading one definition's durable command trail.

    ``complete`` is the truthfulness gate: it is ``True`` only when the whole
    trail was walked to its end *and* every located command's publication proof
    was readable.  An incomplete read can never be reported as "no command was
    ever submitted", because absence of evidence is not evidence of absence.
    """

    commands: tuple[_DefinitionCommandAudit, ...]
    complete: bool


@dataclass(frozen=True)
class _PublicationProof:
    """Whether one command's own revision provably published its candidate.

    ``revision_id`` names the publishing revision when publication is proven.
    ``available`` is ``False`` when the durable proof could not be read at all
    (a repository failure); the outcome is then *unknown*, and must never be
    presented as a proven non-publication.
    """

    revision_id: str | None
    available: bool

    @property
    def published(self) -> bool:
        return self.revision_id is not None


def _bounded(value: object, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:maximum]


class AutomationWorkspaceCommandService:
    """One checked Save or lifecycle command per intended definition change."""

    def __init__(self, objects: ConfigurationObjectService, *, unattended_grants=None) -> None:
        self._objects = objects
        self._managed = objects._managed
        self._repository = objects._repository
        self._unattended_grants = unattended_grants
        # Bound by the API layer: a zero-argument reader that returns the
        # definition's newest durable occurrence (or None).  It is used only
        # for read-only historical resolution, never for authority.
        self._occurrence_store = None

    def bind_occurrence_store(self, reader) -> None:
        """Bind the durable-occurrence reader used for historical resolution."""

        self._occurrence_store = reader

    # ------------------------------------------------------------------
    # Reads (zero configuration, Provider, Task/Job or Storage side effects)
    # ------------------------------------------------------------------

    def authority(self) -> dict[str, object]:
        """The exact Active identity a page binds its next Save to."""

        active = self._require_active_read("authority")
        return {"active": self._safe_active(active), "sideEffects": "none"}

    def form_authority(self) -> dict[str, object]:
        """The bounded typed-form authority derived from the actual domain.

        The projection answers "which fields, references and bounds exist here"
        from the same domain constants, configured ResourceLibraries and run
        modes the backend already uses.  It never invents a mode or schedule
        form, and it starts no work.
        """

        active = self._require_active_read("form authority")
        resource_libraries = [
            {
                "id": _bounded(item.get("id"), MAX_DEFINITION_ID_LENGTH),
                "name": _bounded(item.get("name"), MAX_DEFINITION_NAME_LENGTH),
                "enabled": item.get("enabled", True) is not False,
                "storageId": _bounded(item.get("storageId"), MAX_DEFINITION_ID_LENGTH),
                "storagePath": _bounded(item.get("storagePath"), MAX_DEFINITION_SCOPE_LENGTH),
            }
            for item in self._objects._canonical_objects(active.document, "resourceLibraries")
        ]
        return {
            "active": self._safe_active(active),
            "sideEffects": "none",
            "fields": sorted(AUTOMATION_DEFINITION_FORM_FIELDS),
            "defaults": copy.deepcopy(AUTOMATION_DEFINITION_FORM_DEFAULTS),
            "resourceLibraries": resource_libraries,
            "enums": {
                "modes": [item.value for item in AutomationTaskRunMode],
                "scheduleTypes": ["interval", "cron"],
            },
            "limits": {
                "id": MAX_DEFINITION_ID_LENGTH,
                "name": MAX_DEFINITION_NAME_LENGTH,
                "sourceScope": MAX_DEFINITION_SCOPE_LENGTH,
                "timezone": MAX_DEFINITION_TIMEZONE_LENGTH,
                "itemLimit": {"minimum": 1, "maximum": MAX_DEFINITION_ITEM_LIMIT},
                "intervalSeconds": {
                    # The domain accepts any finite value greater than zero:
                    # fractional seconds such as 1.5 are supported values, so
                    # the bound is an exclusive minimum, not an integer floor.
                    "minimum": 0,
                    "exclusiveMinimum": True,
                    "maximum": MAX_DEFINITION_INTERVAL_SECONDS,
                },
            },
            "actions": {
                "create": True,
                "edit": True,
                "copy": True,
                "toggle": True,
                "remove": True,
            },
        }

    def edit_projection(self, definition_id: str) -> dict[str, object]:
        """Typed edit prefill for one exact published definition."""

        self._identifier(definition_id, "edit")
        active = self._require_active_read("definition edit")
        stored, definition_state = self._resolve_source(active, definition_id, "edit")
        return {
            "definition": self._form_projection(stored),
            "active": self._safe_active(active),
            "definitionState": definition_state,
            "sideEffects": "none",
        }

    def copy_projection(self, definition_id: str) -> dict[str, object]:
        """One new-ID copy candidate computed from the backend field authority.

        The copy keeps the source's typed field values, receives a fresh stable
        ID and starts disabled so it can never inherit the source's schedule
        authority.  Nothing is persisted here: the operator's single `保存`
        publishes the candidate.
        """

        self._identifier(definition_id, "copy")
        active = self._require_active_read("definition copy")
        stored, definition_state = self._resolve_source(active, definition_id, "copy")
        values = self._form_projection(stored)
        values["id"] = self._allocate_copy_id(definition_id, self._active_ids(active))
        values["name"] = f"{str(stored.get('name') or definition_id)[:115]} copy"
        values["enabled"] = False
        return {
            "definition": values,
            "source": {"id": definition_id, "name": _bounded(stored.get("name"), 120)},
            "sourceState": definition_state,
            "active": self._safe_active(active),
            "sideEffects": "none",
            "nextAction": (
                "review the copied definition fields and save to publish it as a new, "
                "disabled Active definition without authority"
            ),
        }

    def removal_impact(self, definition_id: str) -> dict[str, object]:
        """Bounded evidence that decides whether a removal is safe and complete."""

        self._identifier(definition_id, "removal impact")
        active = self._require_active_read("definition removal impact")
        stored, definition_state = self._resolve_source(active, definition_id, "removal impact")
        evidence = self._objects._references_for(
            ConfigurationObjectKind.SCHEDULE, definition_id, active.document
        )
        return {
            "definition": {
                "id": str(stored.get("id")),
                "name": _bounded(stored.get("name"), MAX_DEFINITION_NAME_LENGTH),
                "enabled": stored.get("enabled", False) is True,
                "resourceLibraryId": _bounded(stored.get("resourceLibraryId"), 128),
                "mode": stored.get("mode"),
            },
            "definitionState": definition_state,
            "references": {
                "total": evidence.total,
                "items": [item.document() for item in evidence.items],
                "truncated": evidence.truncated,
            },
            "unattendedAuthority": self._authority_projection(definition_id),
            "active": self._safe_active(active),
            "sideEffects": "none",
            "nextAction": (
                "confirm the removal to stop future scheduling and revoke future unattended "
                "mutation authority while retaining grants, audits and run history"
            ),
        }

    def copy_intent(
        self,
        definition_id: str,
        *,
        expected_revision_id: str | None = None,
        expected_version: int | None = None,
        expected_digest: str | None = None,
    ) -> dict[str, object]:
        """Reconcile one submitted-but-unconfirmed Copy command from durable truth.

        A Copy whose HTTP response was lost is an unknown publication outcome,
        not a rejection.  This read resolves the exact outcome from durable
        evidence instead of letting the browser allocate another copy.

        The reconciliation is bound to the *submitted intent*: the caller
        supplies the observed Active identity the lost Copy was submitted
        against (when it is known), and only a command whose recorded
        ``publishedFromRevisionId`` matches that fence can be reported as its
        committed result.  Without a fence the read reports the newest observed
        command for this source but never silently names another, later
        submission's copy as this one's outcome.

        The evidence scan is *targeted, not bounded by recent activity*: the
        durable command trail is walked to its end from a real, monotonic ledger
        cursor, so a Copy submitted long before later activity is still located,
        and each observed command's publication is proven from *that exact
        revision's* own durable activation authority rather than from a recent
        global activation window.  Absence from any bounded recent scan is
        therefore never reported as "genuinely unpublished", and a trail or proof
        that cannot be read completely is reported as an unknown outcome that
        keeps the resubmission block in place.  The read creates nothing and
        starts no work.
        """

        self._identifier(definition_id, "copy intent")
        active = self._require_active_read("copy intent")
        if expected_revision_id is not None:
            # The submitted intent's fence identifies the authority the lost
            # Copy was submitted against; it is intentionally the historical
            # snapshot, not today's Active, so only its shape is validated and
            # it is never compared against the current revision.
            if (
                not isinstance(expected_revision_id, str)
                or not expected_revision_id
                or not isinstance(expected_digest, str)
                or not expected_digest
                or isinstance(expected_version, bool)
                or not isinstance(expected_version, int)
            ):
                raise AutomationDefinitionSaveError(
                    "automation_definition_invalid_request",
                    "the copy-intent reconciliation requires the observed Active revision "
                    "identity (expectedRevisionId, expectedVersion and expectedDigest)",
                    status=400,
                    stage="copy intent",
                    durable_state="active_unchanged",
                    side_effects="none",
                    next_action="reload the Active Automation inventory and reconcile again",
                )
        published_ids = self._active_ids(active)
        trail = self._definition_command_evidence(definition_id)
        evidence: dict[str, object] | None = None
        committed_id: str | None = None
        observed_commands = 0
        unresolved_proof = False
        for command in trail.commands:
            change = command.context
            command_action = command.action
            candidate = change.get("after") or change.get("candidate")
            if not isinstance(candidate, dict):
                continue
            candidate_id = str(candidate.get("id") or "")
            if not candidate_id or candidate_id == definition_id:
                continue
            observed_commands += 1
            # Bind the evidence to the submitted intent: a command is only
            # this read's outcome when it was submitted against the exact
            # authority the caller observed (or when no fence was
            # supplied).  A later submission's copy is a different intent
            # and is never named as this one's result.
            command_fence = str(change.get("publishedFromRevisionId") or "")
            if expected_revision_id is not None and command_fence != expected_revision_id:
                continue
            proof = self._candidate_publication(command.revision_id, candidate_id)
            if not proof.available:
                # The command is located but its own revision's publication
                # proof could not be read from durable authority.  That is an
                # unknown outcome, never a proven rejection: the block must
                # hold so no second copy can be allocated for this intent.
                unresolved_proof = True
                if evidence is None:
                    evidence = {
                        "auditId": command.audit_id[:64],
                        "action": command_action,
                        "occurredAt": command.occurred_at,
                        "candidateId": candidate_id,
                        "published": False,
                    }
                if expected_revision_id is not None:
                    break
                continue
            if proof.published:
                committed_id = candidate_id
                evidence = {
                    "auditId": command.audit_id[:64],
                    "action": command_action,
                    "occurredAt": command.occurred_at,
                    "candidateId": candidate_id,
                    "published": True,
                    "publishedRevisionId": proof.revision_id,
                }
                if expected_revision_id is None:
                    break
            elif evidence is None:
                # The command is located but its candidate's publication
                # cannot be proven from durable evidence: that is an unknown
                # outcome, never a proven rejection.
                evidence = {
                    "auditId": command.audit_id[:64],
                    "action": command_action,
                    "occurredAt": command.occurred_at,
                    "candidateId": candidate_id,
                    "published": False,
                }
            if expected_revision_id is not None:
                break
        # Completeness is the truthfulness gate the page binds to: only a trail
        # walked to its end whose every relevant proof was readable may be
        # presented as a proven non-publication.
        evidence_complete = trail.complete and not unresolved_proof
        if committed_id is not None:
            next_action = (
                f"the copy of {definition_id!r} committed durably as {committed_id!r}; "
                "reload the current authority instead of submitting another copy"
            )
        elif not evidence_complete:
            next_action = (
                "the submitted copy outcome is unknown: the durable command evidence could "
                "not be read completely, so reconcile the current Active Automation inventory "
                "and do not submit another copy for this intent"
            )
        elif observed_commands > 0 and evidence is not None:
            next_action = (
                "the submitted copy command's publication could not be proven from "
                "durable evidence; reconcile the current Active Automation inventory "
                "and resubmit the copy deliberately"
            )
        elif observed_commands > 0:
            next_action = (
                "no submitted copy command was observed in durable evidence; the "
                "outcome is genuinely unpublished"
            )
        else:
            next_action = "no pending copy command was observed for this definition"
        return {
            "definitionId": definition_id,
            "sourcePresent": definition_id in published_ids,
            "committed": committed_id is not None,
            "committedDefinitionId": committed_id,
            "lastObserved": evidence,
            "observedCommands": observed_commands,
            "evidenceComplete": evidence_complete,
            "active": self._safe_active(active),
            "sideEffects": "none",
            "nextAction": next_action,
        }

    def _definition_command_evidence(self, definition_id: str) -> _DefinitionCommandEvidence:
        """The definition's durable create/copy command audits, newest first.

        The walk is targeted at the durable command trail rather than a global
        recent window, so a committed intent submitted long before later
        activity is still located.  Paging uses the ledger's own monotonic
        ``sequence`` as a real cursor: the first page starts just above the
        newest persisted sequence and each following page anchors strictly
        below the previous page's lowest sequence, so pages can neither repeat
        nor skip a row.  The walk stops when a page comes back short, which is
        the only condition that proves the trail was read to its end.

        ``complete`` reports that proof honestly.  A repository double that
        offers only the bounded recent reader still reconciles the commands it
        can see, but its read is never presented as a complete trail — an
        incomplete read must not be mistaken for "no command was ever
        submitted".
        """

        commands: list[_DefinitionCommandAudit] = []

        def accept(audit: object) -> None:
            change = audit.after.get("objectChange")
            if not isinstance(change, dict):
                return
            if str(change.get("kind")) != "schedule":
                return
            # The persisted audit action is the managed lifecycle action
            # (``draft_edit``); the command identity lives in the
            # objectChange context.
            command_action = str(change.get("action"))
            if command_action not in {"copy", "create"}:
                return
            # Copy commands carry their source explicitly; create commands
            # have no source identity at all, so they only reconcile for a
            # read naming the candidate itself.
            source_id = change.get("sourceObjectId") or change.get("routeObjectId")
            candidate = change.get("after") or change.get("candidate")
            if source_id is None and command_action == "create":
                if not (
                    isinstance(candidate, dict) and str(candidate.get("id") or "") == definition_id
                ):
                    return
            elif source_id is None:
                return
            if str(source_id) != definition_id and command_action == "copy":
                return
            commands.append(
                _DefinitionCommandAudit(
                    audit_id=str(audit.audit_id),
                    revision_id=str(audit.object_id),
                    action=command_action,
                    occurred_at=audit.occurred_at.isoformat(),
                    context=change,
                )
            )

        repository = self._managed.repository
        targeted = getattr(repository, "list_command_audits_before", None)
        latest = getattr(repository, "latest_command_audit_sequence", None)
        recent = getattr(repository, "list_recent_command_audits", None)
        page_size = COMMAND_TRAIL_PAGE_SIZE
        complete = False
        if callable(targeted) and callable(latest):
            try:
                marker = int(latest()) + 1
                while True:
                    page = targeted(("draft_edit",), before_sequence=marker, limit=page_size)
                    for audit in page:
                        accept(audit)
                    if len(page) < page_size:
                        # A short page is the end of the trail: the walk is
                        # complete and absence from it is real evidence.
                        complete = True
                        break
                    sequences = [
                        int(audit.sequence)
                        for audit in page
                        if getattr(audit, "sequence", None) is not None
                    ]
                    if not sequences:
                        # A full page with no usable cursor cannot be paged
                        # safely; report the read as incomplete rather than
                        # risk skipping evidence.
                        break
                    next_marker = min(sequences)
                    if next_marker >= marker:
                        break
                    marker = next_marker
            except Exception:
                commands = []
                complete = False
        elif callable(recent):
            try:
                audits = recent(("draft_edit",), limit=200)
            except Exception:
                audits = ()
            for audit in audits:
                accept(audit)
        seen: set[str] = set()
        deduplicated: list[_DefinitionCommandAudit] = []
        for command in commands:
            if command.audit_id in seen:
                continue
            seen.add(command.audit_id)
            deduplicated.append(command)
        return _DefinitionCommandEvidence(tuple(deduplicated), complete)

    def _candidate_publication(
        self, command_revision_id: str, candidate_id: str
    ) -> _PublicationProof:
        """Whether one command's own revision provably published its candidate.

        The command's Draft edit audit row carries the revision it was edited
        into (``object_id``).  Publication is proven from *that exact
        revision's* durable activation authority — its own ``activate`` audit
        read through the per-revision reader — instead of from a bounded window
        of recent global activations, so a revision published long ago is
        proven just as reliably as a fresh one and no activation window can
        limit the answer.

        The activated document must also still contain the candidate.  The
        Active pointer may have moved on since; the historical revision still
        proves the publication.  ``available`` is ``False`` when the durable
        proof could not be read at all, which the caller reports as an unknown
        outcome rather than a proven non-publication.
        """

        try:
            revision = self._repository.get_revision(command_revision_id)
        except Exception:
            return _PublicationProof(None, False)
        if revision is None:
            # The command names a revision that durable authority no longer
            # holds: the proof is unavailable, not disproven.
            return _PublicationProof(None, False)
        try:
            values = self._objects._automation_definition_objects(revision.document)
        except (ValueError, KeyError):
            return _PublicationProof(None, False)
        if not any(str(item.get("id")) == candidate_id for item in values):
            # The revision is readable and provably does not contain this
            # candidate, so this command did not publish it. That is a real
            # negative answer, not unavailable evidence.
            return _PublicationProof(None, True)
        reader = getattr(self._repository, "list_revision_audits", None)
        if not callable(reader):
            return _PublicationProof(None, False)
        try:
            audits = reader(command_revision_id, limit=500)
        except Exception:
            return _PublicationProof(None, False)
        if len(audits) >= 500:
            # The per-revision trail may be truncated, so the absence of an
            # activation audit cannot be proven: fail closed to unknown.
            return _PublicationProof(None, False)
        for audit in audits:
            if audit.action != "activate":
                continue
            if str(audit.object_id) != str(revision.revision_id):
                continue
            return _PublicationProof(str(revision.revision_id), True)
        return _PublicationProof(None, True)

    def schedule_preview(
        self,
        candidate: Mapping[str, object],
        *,
        object_id: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, object]:
        """Zero-mutation upcoming-run calculation through the Scheduler's own rules.

        The candidate is normalized and reference-checked against the exact
        current Active document, but no Draft, due state, occurrence, Job or Task
        is created: the operator can preview upcoming times and invalid/DST
        behavior before committing to a Save.
        """

        active = self._require_active_read("schedule preview")
        composed = self._compose(candidate, active, object_id)
        normalized = self._normalize_or_reject(composed, object_id)
        self._validate_reference(normalized, active.document, object_id)
        definition = AutomationTaskDefinition.from_document(normalized)
        reference = now or datetime.now(UTC)
        upcoming, notes = self._upcoming_runs(definition, reference)
        return {
            "scheduleType": definition.schedule_type,
            "timezone": definition.timezone,
            "intervalSeconds": definition.interval_seconds,
            "cron": definition.cron,
            "upcoming": upcoming,
            "notes": notes,
            "enabled": definition.enabled,
            "zeroMutation": True,
            "sideEffects": "none",
            "nextAction": "review the upcoming times, then save the definition to publish it",
        }

    def historical_definition(
        self, definition_id: str, *, occurrence: object = None
    ) -> dict[str, object] | None:
        """The published revision a retained occurrence pins, or its newest evidence.

        A removed definition's retained history resolves from durable evidence,
        never from an open Draft: an unpublished Draft candidate is exactly the
        thing that was never published, so its name/scope/mode must not be
        substituted for what the removed run actually used.

        With an ``occurrence`` (the durable emitted row), the newest
        non-Active revision whose digest and revision identity match the
        occurrence's pinned configuration is returned — the publication that
        actually emitted the run. Without one, the newest non-Active revision
        that still contains the definition and is backed by published
        activation evidence is used; a definition without published evidence
        has no retained history here.
        """

        occurrence_row = getattr(occurrence, "document", lambda: None)() if occurrence else None
        if not isinstance(occurrence_row, dict):
            occurrence_row = None
        pinned_revision_id = (
            str(occurrence_row.get("configurationRevisionId")) if occurrence_row else None
        )
        pinned_revision_version = (
            occurrence_row.get("configurationRevisionVersion") if occurrence_row else None
        )
        pinned_revision_digest = (
            str(occurrence_row.get("configurationRevisionDigest")) if occurrence_row else None
        )
        pinned_fingerprint = (
            str(occurrence_row.get("definitionFingerprint")) if occurrence_row else None
        )
        try:
            revisions = self._repository.list_revisions(limit=HISTORICAL_REVISION_SCAN_LIMIT)
        except Exception:
            return None
        published_revision_ids = self._published_revision_ids()
        exact = None
        best = None
        for revision in revisions:
            if revision.status is ManagedConfigurationStatus.ACTIVE:
                continue
            # An open Draft/Validated revision that was never published must
            # never be presented as a removed definition's history: its
            # candidate was never Active and the removed run's occurrence
            # cannot name it.  Only revisions with durable activation
            # evidence are historical run context; a definition without any
            # such evidence has no retained history here.
            if str(revision.revision_id) not in published_revision_ids:
                continue
            try:
                values = self._objects._automation_definition_objects(revision.document)
            except (ValueError, KeyError):
                continue
            item = next((entry for entry in values if str(entry.get("id")) == definition_id), None)
            if item is None:
                continue
            candidate = {
                "definition": copy.deepcopy(item),
                "revision": self._safe_active(revision),
                "revisionStatus": revision.status.value,
            }
            if pinned_revision_id is not None and str(revision.revision_id) == pinned_revision_id:
                exact = candidate
                break
            if (
                pinned_revision_digest is not None
                and str(revision.digest) == pinned_revision_digest
                and pinned_revision_version is not None
                and str(revision.version) == str(pinned_revision_version)
            ):
                exact = candidate
                break
            if (
                pinned_fingerprint is not None
                and self._definition_fingerprint(item) == pinned_fingerprint
            ):
                # The published revision whose definition content matches the
                # occurrence's recorded fingerprint is the exact run context.
                exact = exact or candidate
            if best is None:
                best = candidate
        if exact is not None:
            return exact
        return best

    @staticmethod
    def _definition_fingerprint(item: dict[str, object]) -> str | None:
        """The exact definition identity fingerprint, when the domain can compute it."""

        try:
            return AutomationTaskDefinition.from_document(item).definition_fingerprint
        except (TypeError, ValueError, KeyError):
            return None

    def _published_revision_ids(self) -> set[str]:
        """Revision identities with durable activation evidence.

        The activation audit is the publication proof: an ``activate`` audit row
        names exactly the revision that was once Active. Draft/Validated
        revisions without activation evidence are never historical run context.
        """

        repository = self._managed.repository
        reader = getattr(repository, "list_recent_command_audits", None)
        if not callable(reader):
            return set()
        try:
            audits = reader(("activate",), limit=500)
        except Exception:
            return set()
        published: set[str] = set()
        for audit in audits:
            revision_id = audit.after.get("revisionId")
            if isinstance(revision_id, str) and revision_id:
                published.add(revision_id)
        return published

    # ------------------------------------------------------------------
    # Commands (one explicit intent publishes one exact Active successor)
    # ------------------------------------------------------------------

    def save_object(
        self,
        candidate: Mapping[str, object],
        *,
        actor: str,
        expected_revision_id: str,
        expected_version: int,
        expected_digest: str,
        object_id: str | None = None,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
    ) -> ManagedConfigurationRevision:
        """Validate and atomically activate one focused create/edit successor.

        ``object_id`` carries the route's explicit intent: a create has none and
        its candidate ID must be new, while an edit is the already-opened
        definition whose ID stays immutable.  Inferring that from the body would
        let one filled-in form silently change a definition's identity or
        overwrite an unrelated Active row.
        """

        if not isinstance(candidate, Mapping):
            raise self._invalid(
                "the Automation Task Definition candidate must be an object", object_id, "compose"
            )
        if object_id is not None:
            self._identifier(object_id, "save")
            submitted_id = candidate.get("id")
            if submitted_id is not None and submitted_id != object_id:
                raise AutomationDefinitionSaveError(
                    "automation_definition_id_immutable",
                    "the Automation Task Definition ID is immutable; an edit may only address "
                    "the definition it opened",
                    status=400,
                    definition_id=object_id,
                    stage="compose",
                    durable_state="active_unchanged",
                    side_effects="none",
                    next_action="keep the definition ID and correct the editable fields instead",
                )

        active = self._capture_active("save")
        self._assert_current_authority(
            active, expected_revision_id, expected_version, expected_digest
        )
        published = self._active_ids(active)
        editing_published = object_id is not None and object_id in published
        if object_id is None:
            new_id = candidate.get("id")
            if not isinstance(new_id, str):
                raise self._invalid(
                    "a new Automation Task Definition requires an id", None, "compose"
                )
            self._identifier(new_id, "save")
            if new_id in published:
                raise AutomationDefinitionSaveError(
                    "automation_definition_duplicate",
                    f"Automation Task Definition {new_id!r} already exists in the current "
                    "Active configuration",
                    status=409,
                    definition_id=new_id,
                    stage="compose",
                    durable_state="active_unchanged",
                    side_effects="none",
                    next_action="choose a different ID, or edit the existing definition",
                )
        elif not editing_published:
            # A Draft-only candidate is corrected and published by the same one
            # Save.  The old Draft is left exactly as it was: its unrelated edits
            # neither ride along nor disappear.
            self._resolve_source(active, object_id, "save")

        composed = self._compose(candidate, active, object_id)
        normalized = self._normalize_or_reject(composed, object_id)
        if not editing_published and normalized.get("enabled") is True:
            raise AutomationDefinitionSaveError(
                "automation_definition_enable_requires_command",
                "a new Automation Task Definition starts disabled; enable it with the separate "
                "explicit enable command after it is published",
                status=409,
                definition_id=str(normalized.get("id")),
                stage="compose",
                durable_state="active_unchanged",
                side_effects="none",
                next_action="save the definition as disabled, then enable it deliberately",
            )
        self._validate_reference(normalized, active.document, object_id)

        return self._publish(
            active,
            normalized,
            object_id=object_id if editing_published else None,
            actor=actor,
            audit_action="edit" if editing_published else "create",
            before_publish=before_publish,
        )

    def set_enabled(
        self,
        definition_id: str,
        *,
        enabled: bool,
        actor: str,
        expected_revision_id: str,
        expected_version: int,
        expected_digest: str,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
    ) -> ManagedConfigurationRevision:
        """Publish one explicit enabled-state successor for an exact Active definition.

        Enabling only makes the definition eligible for future Scheduler
        evaluation: it starts no scan, Job, Task, occurrence or grant, and it
        neither cancels admitted work nor revokes an existing grant.
        """

        if not isinstance(enabled, bool):
            raise self._invalid(
                "Automation Task Definition enabled must be boolean", definition_id, "compose"
            )
        self._identifier(definition_id, "state change")
        active = self._capture_active("state change")
        self._assert_current_authority(
            active, expected_revision_id, expected_version, expected_digest
        )
        stored = self._active_definition(active, definition_id, "state change")
        value = self._form_projection(stored)
        value["enabled"] = enabled
        normalized = self._normalize_or_reject(value, definition_id)
        self._validate_reference(normalized, active.document, definition_id)
        return self._publish(
            active,
            normalized,
            object_id=definition_id,
            actor=actor,
            audit_action="enable" if enabled else "disable",
            before_publish=before_publish,
        )

    def copy_object(
        self,
        definition_id: str,
        *,
        actor: str,
        expected_revision_id: str,
        expected_version: int,
        expected_digest: str,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
    ) -> ManagedConfigurationRevision:
        """Publish one new, disabled copy with a fresh identity and no authority."""

        self._identifier(definition_id, "copy")
        active = self._capture_active("copy")
        self._assert_current_authority(
            active, expected_revision_id, expected_version, expected_digest
        )
        stored, _state = self._resolve_source(active, definition_id, "copy")
        values = self._form_projection(stored)
        values["id"] = self._allocate_copy_id(definition_id, self._active_ids(active))
        values["name"] = f"{str(stored.get('name') or definition_id)[:115]} copy"
        values["enabled"] = False
        normalized = self._normalize_or_reject(values, None)
        self._validate_reference(normalized, active.document, None)
        return self._publish(
            active,
            normalized,
            object_id=None,
            actor=actor,
            audit_action="copy",
            source_id=definition_id,
            before_publish=before_publish,
        )

    def remove_object(
        self,
        definition_id: str,
        *,
        actor: str,
        expected_revision_id: str,
        expected_version: int,
        expected_digest: str,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
        reason: str | None = None,
    ) -> ManagedConfigurationRevision:
        """Remove one definition and durably revoke its future unattended authority.

        Ordering is deliberate and fault-tolerant at the exact production
        persistence boundary, where configuration and runtime/grant state live
        in the *same* SQLite file and any foreign writer can hold the write
        lock:

        1. the removal successor is persisted and validated *before* any
           authority is touched, so a persistence/validation failure is a pure
           configuration failure whose prior Active and live authority are
           untouched;
        2. the successor is then atomically activated.  A known rejected or
           known failed activation is a known failed removal: the Active
           pointer swap is one SQLite transaction that did not commit, so the
           definition and its live authority are preserved by construction and
           the bounded error reports the live authority read after the fact;
        3. only a *proven successful* publication is followed by the durable
           revocation of applicable future unattended authority, so a known
           failed removal can never leave the definition Active while its
           authority was already revoked.  A revocation that cannot prove the
           revoked state is reported truthfully on the already-published
           removal instead of being hidden.

        Grants, audits, occurrences, Jobs/Tasks/Results and admitted pins are
        never erased.  A genuinely ambiguous activation commit — where the
        repository raised but the durable pointer state cannot be read back as
        either the prior Active or the attempted successor — is reported as
        unknown with the live authority truth attached; the operator
        reconciles deliberately, nothing replays automatically.
        """

        self._identifier(definition_id, "removal")
        active = self._capture_active("removal")
        self._assert_current_authority(
            active, expected_revision_id, expected_version, expected_digest
        )
        stored = self._active_definition(active, definition_id, "removal")

        draft = self._successor(active)
        try:
            edited = self._objects.mutate(
                draft.revision_id,
                ConfigurationObjectKind.SCHEDULE,
                object_id=definition_id,
                value=None,
                expected_version=draft.version,
                actor=actor,
                delete=True,
                allow_automation_definition_delete=True,
                audit_action="remove",
                audit_metadata={
                    "surface": "automation",
                    "removed": {
                        "id": stored.get("id"),
                        "name": stored.get("name"),
                        "resourceLibraryId": stored.get("resourceLibraryId"),
                        "sourceScope": stored.get("sourceScope"),
                        "mode": stored.get("mode"),
                    },
                    "routeObjectId": definition_id,
                    "publishedFromRevisionId": active.revision_id,
                },
            )
        except (ConfigurationVersionConflict, ConfigurationActivationConflict, ValueError):
            raise
        except Exception as error:
            # This failure happened inside the shared managed-authority Draft
            # edit — before any activation and before any authority is touched.
            # The Active definition and its live unattended authority are
            # exactly as they were, so the bounded recovery document reports
            # that durable truth instead of leaving an admitted Job's authority
            # silently revoked.
            raise AutomationDefinitionSaveError(
                "automation_definition_persistence_failed",
                "the removal successor could not be persisted; the Active definition and its "
                "live unattended authority are unchanged",
                status=503,
                definition_id=definition_id,
                stage="persist",
                revision_id=draft.revision_id,
                durable_state="active_preserved",
                side_effects="none",
                retry_safe=True,
                authority_state=self._live_authority_status(definition_id),
                next_action=(
                    "resolve the configuration persistence failure (for example a write "
                    "lock held by another writer), then confirm the removal again"
                ),
            ) from error

        validated = self._validate(edited, definition_id)
        self._assert_focused_change(active.document, validated.document, definition_id)

        # Fail-closed authority preflight: the removal must never publish when
        # the definition's live unattended authority cannot be read, because
        # publication is followed by the durable revocation and an unreadable
        # grant state can never be treated as no authority. This is a read
        # only; the revocation itself happens after the publication is proven.
        self._assert_authority_readable(definition_id)

        try:
            published = self._managed.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor=actor,
                before_publish=before_publish,
            )
        except ConfigurationVersionConflict:
            # A known rejected activation: the concurrent writer won and the
            # Active is exactly what the winner left, live authority untouched.
            raise
        except ConfigurationActivationConflict as error:
            # A known rejected activation: the Active pointer never moved, so
            # the definition and its live authority are preserved by
            # construction.  No revocation has happened on this path, so no
            # compensating grant write is needed or attempted.
            live_authority = self._authority_state_now(definition_id)
            raise AutomationDefinitionSaveError(
                "automation_definition_removal_not_published",
                "the removal successor could not be published; the Active definition is "
                "preserved with its previous live authority untouched",
                status=409,
                definition_id=definition_id,
                stage="activate",
                revision_id=validated.revision_id,
                durable_state="active_preserved",
                side_effects="configuration_only",
                retry_safe=True,
                authority_state=live_authority,
                next_action=(
                    "refresh the current Active configuration; the definition is still "
                    f"published and its future unattended authority is {live_authority}. "
                    "Re-grant deliberately if it must remain live"
                ),
            ) from error
        except Exception as error:
            # A persistence/concurrency failure inside the activation boundary
            # (a foreign writer's write lock, a failed commit, a storage fault)
            # is a known failure of this removal, not a rejection to reason
            # about.  No authority was touched on this path: the failed
            # activation transaction leaves the prior Active in place, so the
            # definition's live authority survives exactly as it was.  The
            # durable pointer state is read back and reported truthfully;
            # `commit_state_unknown` is reserved for the genuinely ambiguous
            # case where the pointer already matches the attempted successor.
            live_authority = self._authority_state_now(definition_id)
            active_after = self._safe_active_summary()
            unconflicted = (
                active_after is not None and active_after.get("revisionId") != validated.revision_id
            )
            raise AutomationDefinitionSaveError(
                "automation_definition_removal_not_published",
                (
                    "the removal successor could not be published; the Active definition is "
                    "preserved with its previous live authority untouched"
                    if unconflicted
                    else "the removal publication state is uncertain; the Active configuration "
                    "read back matches the attempted successor, so verify the durable "
                    "inventory before acting again"
                ),
                status=503,
                definition_id=definition_id,
                stage="activate",
                revision_id=validated.revision_id,
                durable_state=("active_preserved" if unconflicted else "commit_state_unknown"),
                side_effects="configuration_only",
                retry_safe=unconflicted,
                authority_state=live_authority,
                next_action=(
                    (
                        "resolve the configuration persistence failure, then confirm the "
                        "removal again; the definition is still published and its future "
                        f"unattended authority is {live_authority}"
                    )
                    if unconflicted
                    else (
                        "read the Active Automation inventory and the definition's grant "
                        "state; reconcile the uncertain publication deliberately before any "
                        "further removal command"
                    )
                ),
            ) from error

        # The removal successor is durably published.  Only now — after the
        # publication is proven — is the definition's future unattended
        # authority durably revoked, so a known failed removal can never leave
        # the definition Active while its authority was already revoked (the
        # exact production failure the same-file configuration/runtime
        # assembly exposed).  A residual applicable grant that a concurrent
        # operator legitimately re-granted in the serialized window between
        # publication and this revocation is revoked here; a revocation that
        # cannot prove the revoked state is re-read live and reported
        # truthfully on the already-published removal instead of being hidden.
        residual = self._revoke_future_authority(
            definition_id,
            actor=actor,
            reason=reason or "the Automation Task Definition was removed",
            allow_unavailable=True,
        )
        if str(residual.get("state")) not in {"revoked", "already_revoked", "none"}:
            live = self._live_authority_status(definition_id)
            raise AutomationDefinitionSaveError(
                "automation_definition_removal_authority_live",
                (
                    "the removal successor was published but live future unattended authority "
                    "could not be revoked; verify and revoke it deliberately"
                    if live == "active"
                    else (
                        "the removal successor was published and no live unattended authority "
                        "is currently readable; the revocation could not be proven, so "
                        "verify the grant state and revoke it deliberately"
                    )
                ),
                status=200,
                definition_id=definition_id,
                stage="authority",
                revision_id=published.revision_id,
                durable_state="successor_published",
                side_effects="configuration_only",
                retry_safe=False,
                authority_state=live,
                next_action=(
                    "inspect the definition's unattended grant state and revoke it "
                    "deliberately; scheduled emission already stopped because the "
                    "definition is no longer published"
                ),
            )
        return published

    def _safe_active_summary(self) -> dict[str, object] | None:
        try:
            current = self._managed.active()
        except Exception:
            return None
        return self._safe_active(current) if current is not None else None

    def _authority_state_now(self, definition_id: str) -> str:
        """The definition's live unattended-authority state read at this moment."""

        return self._live_authority_status(definition_id)

    # ------------------------------------------------------------------
    # Shared publication core
    # ------------------------------------------------------------------

    def _publish(
        self,
        active: ManagedConfigurationRevision,
        normalized: Mapping[str, object],
        *,
        object_id: str | None,
        actor: str,
        audit_action: str,
        source_id: str | None = None,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None,
    ) -> ManagedConfigurationRevision:
        definition_id = str(normalized.get("id"))
        draft = self._successor(active)
        try:
            edited = self._objects.mutate(
                draft.revision_id,
                ConfigurationObjectKind.SCHEDULE,
                object_id=object_id,
                value=normalized,
                expected_version=draft.version,
                actor=actor,
                audit_action=audit_action,
                audit_metadata={
                    "surface": "automation",
                    "candidate": copy.deepcopy(dict(normalized)),
                    # The audit context is the reconciliation evidence a lost
                    # response needs: the command's route intent, the exact
                    # candidate it submitted, the source it derived from (for
                    # copy commands the route target), and the Active identity
                    # it was published from.
                    "routeObjectId": object_id,
                    "sourceObjectId": (
                        str(source_id) if audit_action == "copy" and source_id else None
                    ),
                    "publishedFromRevisionId": active.revision_id,
                },
            )
        except (ConfigurationVersionConflict, ConfigurationActivationConflict, ValueError):
            raise
        except Exception as error:
            raise self._persistence_failed(definition_id, draft.revision_id) from error

        validated = self._validate(edited, definition_id)
        self._assert_focused_change(active.document, validated.document, definition_id)

        try:
            return self._managed.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor=actor,
                before_publish=before_publish,
            )
        except (ConfigurationVersionConflict, ConfigurationActivationConflict):
            raise
        except AutomationDefinitionSaveError:
            raise
        except Exception as error:
            raise AutomationDefinitionSaveError(
                "automation_definition_activation_failed",
                "the successor could not be published; the previous Active remains in use",
                status=503,
                definition_id=definition_id,
                stage="activate",
                revision_id=validated.revision_id,
                durable_state="active_preserved",
                side_effects="configuration_only",
                next_action="check configuration persistence health, then retry",
            ) from error

    def _successor(self, active: ManagedConfigurationRevision) -> ManagedConfigurationRevision:
        try:
            return self._managed.create_successor_draft(
                actor="automation",
                expected_active_revision_id=active.revision_id,
                expected_active_version=active.revision_sequence or active.version,
                expected_active_digest=active.digest,
                verified_active=active,
            )
        except (ConfigurationVersionConflict, RuntimeSnapshotUnavailable):
            raise
        except Exception as error:
            raise AutomationDefinitionSaveError(
                "automation_definition_persistence_failed",
                "the successor configuration could not be created; the previous Active remains "
                "in use",
                status=503,
                stage="persist",
                durable_state="active_preserved",
                next_action="check configuration persistence health, then retry",
            ) from error

    def _validate(
        self, edited: ManagedConfigurationRevision, definition_id: str
    ) -> ManagedConfigurationRevision:
        try:
            validated = self._managed.validate(edited.revision_id, actor="automation")
        except (ConfigurationVersionConflict, ConfigurationActivationConflict):
            raise
        except Exception as error:
            raise AutomationDefinitionSaveError(
                "automation_definition_persistence_failed",
                "the successor configuration could not be validated; the previous Active "
                "remains in use",
                status=503,
                definition_id=definition_id,
                stage="validate",
                revision_id=edited.revision_id,
                durable_state="active_preserved",
                next_action="check configuration persistence health, then retry",
            ) from error
        if validated.status is not ManagedConfigurationStatus.VALIDATED:
            errors = list(validated.validation_errors)
            first = self._objects._bounded_utf8(str(errors[0]), 240) if errors else None
            raise AutomationDefinitionSaveError(
                "automation_definition_validation_failed",
                "the successor configuration failed complete whole-document validation; the "
                "previous Active remains in use",
                status=422,
                definition_id=definition_id,
                stage="validate",
                revision_id=validated.revision_id,
                durable_state="active_preserved",
                next_action=(
                    f"correct the reported configuration error ({first}), then save again"
                    if first
                    else "correct the blocking configuration, then save again"
                ),
            )
        return validated

    def _assert_focused_change(
        self,
        active_document: object,
        successor_document: object,
        definition_id: str,
    ) -> None:
        """Fail closed unless the successor changes only the selected definition.

        Composition already builds the successor from the exact observed Active,
        so this is a defensive proof: every other top-level section and every
        sibling definition must be byte-identical, otherwise publication is
        refused instead of silently carrying an unrelated change.
        """

        active = active_document if isinstance(active_document, dict) else {}
        successor = successor_document if isinstance(successor_document, dict) else {}
        changed = {
            key for key in set(active) | set(successor) if active.get(key) != successor.get(key)
        }
        if changed - {AUTOMATION_DEFINITION_SECTION}:
            raise AutomationDefinitionSaveError(
                "automation_definition_out_of_scope",
                "the successor changes configuration outside the Automation Task Definition "
                "boundary; nothing was published",
                status=409,
                definition_id=definition_id,
                stage="compose",
                durable_state="active_preserved",
                side_effects="none",
                next_action=(
                    "save one definition per command; unrelated configuration changes keep "
                    "their own managed publication journey"
                ),
            )
        active_map = self._definition_map(active)
        successor_map = self._definition_map(successor)
        if active_map is None or successor_map is None:
            raise AutomationDefinitionSaveError(
                "automation_definition_out_of_scope",
                "the Automation Task Definition section is malformed; the publication boundary "
                "cannot be verified",
                status=409,
                definition_id=definition_id,
                stage="compose",
                durable_state="active_preserved",
                side_effects="none",
                next_action="restore a valid Automation Task Definition section, then save again",
            )
        unexpected = sorted(
            candidate_id
            for candidate_id in set(active_map) | set(successor_map)
            if candidate_id != definition_id
            and active_map.get(candidate_id) != successor_map.get(candidate_id)
        )
        if unexpected:
            raise AutomationDefinitionSaveError(
                "automation_definition_sibling_scope",
                "the successor changes other Automation Task Definitions beyond the selected "
                "definition; nothing was published",
                status=409,
                definition_id=definition_id,
                stage="compose",
                durable_state="active_preserved",
                side_effects="none",
                next_action="publish one definition per command",
            )

    # ------------------------------------------------------------------
    # Composition and validation helpers
    # ------------------------------------------------------------------

    def _compose(
        self,
        candidate: Mapping[str, object],
        active: ManagedConfigurationRevision,
        object_id: str | None,
    ) -> dict[str, object]:
        """Merge one typed candidate over the exact stored definition.

        Only the fields the typed form owns are replaced: every other stored
        field survives, so a focused Save never silently drops state the form
        does not render.
        """

        unknown = set(candidate).difference(AUTOMATION_DEFINITION_FORM_FIELDS)
        if unknown:
            raise self._invalid(
                "Automation Task Definition candidate contains unsupported field "
                f"{sorted(unknown)[0]!r}",
                object_id,
                "compose",
            )
        stored: Mapping[str, object] | None = None
        if object_id is not None:
            stored = self._stored_definition(active, object_id)
        merged: dict[str, object] = copy.deepcopy(dict(stored)) if stored is not None else {}
        for field in AUTOMATION_DEFINITION_FORM_FIELDS:
            if field in candidate:
                merged[field] = copy.deepcopy(candidate[field])
        if object_id is not None:
            merged["id"] = object_id
        self._compose_schedule(merged, candidate)
        return merged

    @staticmethod
    def _compose_schedule(merged: dict[str, object], candidate: Mapping[str, object]) -> None:
        """Keep exactly one canonical schedule form in the composed definition.

        The typed form always submits its schedule selection, so switching
        between interval and Cron clears the other form instead of leaving a
        contradictory pair that the domain would reject with a confusing error.
        An edit that submits neither form keeps the stored schedule.
        """

        cron = candidate.get("cron") if "cron" in candidate else None
        interval = candidate.get("intervalSeconds") if "intervalSeconds" in candidate else None
        if "cron" in candidate and isinstance(cron, str) and cron.strip():
            merged.pop("intervalSeconds", None)
            return
        if "intervalSeconds" in candidate and interval is not None:
            merged.pop("cron", None)
            merged.pop("timezone", None)
            return
        if merged.get("intervalSeconds") is not None and merged.get("cron") is not None:
            # A contradictory pair can only arrive from legacy stored data;
            # keep the canonical interval form rather than publishing both.
            merged.pop("cron", None)
            merged.pop("timezone", None)

    def _normalize_or_reject(
        self, value: Mapping[str, object], object_id: str | None
    ) -> dict[str, object]:
        try:
            return self._objects._normalize(ConfigurationObjectKind.SCHEDULE, value)
        except ValueError as error:
            message = self._objects._bounded_utf8(str(error), 384) or "invalid value"
            raise AutomationDefinitionSaveError(
                "automation_definition_invalid_field",
                f"Automation Task Definition field is invalid: {message}",
                status=400,
                definition_id=(
                    object_id
                    if isinstance(object_id, str)
                    else _bounded(value.get("id"), MAX_DEFINITION_ID_LENGTH)
                ),
                stage="compose",
                durable_state="active_unchanged",
                side_effects="none",
                next_action=(
                    "correct the reported Automation Task Definition field, then save again"
                ),
            ) from error

    def _validate_reference(
        self,
        value: Mapping[str, object],
        document: Mapping[str, object],
        object_id: str | None,
    ) -> None:
        resources = {
            str(item.get("id")): item
            for item in self._objects._canonical_objects(document, "resourceLibraries")
        }
        reference = str(value.get("resourceLibraryId") or "")
        target = resources.get(reference)
        definition_id = object_id or _bounded(value.get("id"), MAX_DEFINITION_ID_LENGTH)
        if target is None:
            raise AutomationDefinitionSaveError(
                "automation_definition_resource_unavailable",
                f"the selected ResourceLibrary {reference!r} is not configured in the current "
                "Active configuration",
                status=409,
                definition_id=definition_id,
                stage="reference",
                durable_state="active_preserved",
                side_effects="none",
                next_action="choose an enabled configured ResourceLibrary, then save again",
            )
        if target.get("enabled", True) is False:
            raise AutomationDefinitionSaveError(
                "automation_definition_resource_disabled",
                f"the selected ResourceLibrary {reference!r} is disabled in the current Active "
                "configuration",
                status=409,
                definition_id=definition_id,
                stage="reference",
                durable_state="active_preserved",
                side_effects="none",
                next_action="enable the ResourceLibrary, then refresh and save again",
            )

    # ------------------------------------------------------------------
    # Authority revocation
    # ------------------------------------------------------------------

    def _authority_projection(self, definition_id: str) -> dict[str, object]:
        if self._unattended_grants is None:
            return {"status": "unavailable", "active": False, "grantId": None}
        try:
            grant = self._unattended_grants.get_for_definition(definition_id)
        except Exception:
            return {"status": "unavailable", "active": False, "grantId": None}
        if grant is None:
            return {"status": "none", "active": False, "grantId": None}
        return {
            "status": grant.status.value,
            "active": grant.status.value == "active",
            "grantId": grant.grant_id,
            "maxItemsPerRun": grant.max_items_per_run,
            "previewId": grant.preview_id,
        }

    def _live_authority_status(self, definition_id: str) -> str:
        """The definition's live unattended-authority status right now.

        ``get_for_definition`` falls back to the newest grant row of any
        status, so a previously revoked grant reads ``revoked`` even when no
        authority is live.  Removal reconciliation must report the *live*
        state: a revoked/absent grant means no live authority; only an ACTIVE
        grant is live future mutation authority.
        """

        projection = self._authority_projection(definition_id)
        if projection.get("active") is True:
            return "active"
        return "none"

    def _assert_authority_readable(self, definition_id: str) -> None:
        """Fail closed when the definition's unattended authority cannot be read.

        The removal publishes first and revokes afterwards, so an unreadable
        grant state can never be silently treated as "no authority": the
        pre-publication preflight refuses to publish until the grant boundary
        can answer. It is a read only and changes nothing.
        """

        if self._unattended_grants is None:
            return
        try:
            self._unattended_grants.get_for_definition(definition_id)
        except Exception as error:
            raise AutomationDefinitionSaveError(
                "automation_definition_authority_unavailable",
                "the definition's unattended authority state could not be read, so the removal "
                "was not attempted; the Active definition remains in use",
                status=503,
                definition_id=definition_id,
                stage="authority",
                durable_state="active_preserved",
                side_effects="none",
                authority_state="unavailable",
                next_action=(
                    "restore unattended grant state availability, then confirm the removal again"
                ),
            ) from error

    def _revoke_future_authority(
        self,
        definition_id: str,
        *,
        actor: str,
        reason: str | None,
        allow_unavailable: bool = False,
    ) -> dict[str, object]:
        """Durably revoke the definition's future unattended mutation authority.

        With ``allow_unavailable`` the two availability-failure codes are
        returned as bounded states instead of aborting the command: a removal
        that already published must report its authority proof truthfully on
        the published outcome rather than pretending the publication itself
        failed.  A grant whose state cannot be read is never treated as no
        authority.
        """

        if self._unattended_grants is None:
            return {"state": "unavailable", "grantId": None}
        try:
            current = self._unattended_grants.get_for_definition(definition_id)
        except Exception as error:
            if allow_unavailable:
                return {"state": "unavailable", "grantId": None}
            raise AutomationDefinitionSaveError(
                "automation_definition_authority_unavailable",
                "the definition's unattended authority state could not be read, so the removal "
                "was not attempted; the Active definition remains in use",
                status=503,
                definition_id=definition_id,
                stage="authority",
                durable_state="active_preserved",
                side_effects="none",
                authority_state="unavailable",
                next_action=(
                    "restore unattended grant state availability, then confirm the removal again"
                ),
            ) from error
        if current is None:
            return {"state": "none", "grantId": None}
        if current.status.value == "revoked":
            return {"state": "already_revoked", "grantId": current.grant_id}
        try:
            revoked = self._unattended_grants.revoke(
                definition_id=definition_id,
                actor=actor,
                reason=reason or "the Automation Task Definition was removed",
            )
        except Exception as error:
            if allow_unavailable:
                return {"state": "unavailable", "grantId": None}
            raise AutomationDefinitionSaveError(
                "automation_definition_authority_revoke_failed",
                "future unattended authority could not be revoked, so the removal was not "
                "published; the Active definition remains in use",
                status=503,
                definition_id=definition_id,
                stage="authority",
                durable_state="active_preserved",
                side_effects="none",
                authority_state="unchanged",
                next_action="restore unattended grant persistence, then confirm the removal again",
            ) from error
        return {"state": revoked.status.value, "grantId": revoked.grant_id}

    # ------------------------------------------------------------------
    # Lookup and bounded helpers
    # ------------------------------------------------------------------

    def _capture_active(self, action: str) -> ManagedConfigurationRevision:
        active = self._managed.active()
        if active is None:
            self._managed.create_successor_draft(actor="automation")
            raise RuntimeSnapshotUnavailable(
                f"no Active configuration exists; Automation definition {action} is unavailable",
                reason="active_missing",
            )
        self._managed.verify_integrity(active)
        return active

    def _require_active_read(self, surface: str) -> ManagedConfigurationRevision:
        active = self._managed.active()
        if active is None:
            reason = "active_missing"
            try:
                if self._managed.has_managed_activation():
                    reason = "managed_active_unavailable"
            except Exception:
                reason = "managed_active_unavailable"
            raise RuntimeSnapshotUnavailable(
                f"no usable Active configuration exists; Automation {surface} is unavailable",
                reason=reason,
            )
        self._managed.verify_integrity(active)
        return active

    @staticmethod
    def _safe_active(revision) -> dict[str, object]:
        """The exact Active identity a page binds its next command to.

        The digest is included because it is the optimistic fence the focused
        command submits back; it is an identity, not secret evidence, and the
        browser already receives it on the equivalent rules-workspace surface.
        """

        return {
            "revisionId": revision.revision_id,
            "version": revision.version,
            "revisionSequence": revision.revision_sequence or revision.version,
            "status": revision.status.value,
            "digest": revision.digest,
        }

    def _assert_current_authority(
        self,
        active: ManagedConfigurationRevision,
        expected_revision_id: object,
        expected_version: object,
        expected_digest: object,
    ) -> None:
        if (
            not isinstance(expected_revision_id, str)
            or not expected_revision_id
            or not isinstance(expected_digest, str)
            or not expected_digest
            or isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
        ):
            raise AutomationDefinitionSaveError(
                "automation_definition_invalid_request",
                "the Automation Task Definition command requires the observed Active revision "
                "identity (expectedRevisionId, expectedVersion and expectedDigest)",
                status=400,
                stage="authority",
                durable_state="active_unchanged",
                side_effects="none",
                next_action="reload the Active Automation inventory and submit again",
            )
        if (
            active.revision_id != expected_revision_id
            or (active.revision_sequence or active.version) != expected_version
            or active.digest != expected_digest
        ):
            raise ConfigurationVersionConflict(
                "the Automation definition command is stale; the Active configuration changed "
                "after this form was opened",
                revision_id=active.revision_id,
                current_version=active.revision_sequence or active.version,
                current_digest=active.digest,
                durable_state="active_preserved",
                next_action=(
                    "refresh the Active Automation inventory, review the current definition, "
                    "and submit the intended change again"
                ),
            )

    def _identifier(self, object_id: object, action: str) -> str:
        if (
            not isinstance(object_id, str)
            or not object_id
            or len(object_id) > MAX_DEFINITION_ID_LENGTH
            or not _SAFE_DEFINITION_ID.fullmatch(object_id)
        ):
            raise AutomationDefinitionSaveError(
                "automation_definition_invalid_request",
                "the Automation Task Definition ID is not a safe bounded identifier",
                status=400,
                stage=action,
                durable_state="active_unchanged",
                side_effects="none",
                next_action=(
                    "refresh the Active Automation inventory and choose an existing definition"
                ),
            )
        return object_id

    def _active_ids(self, active: ManagedConfigurationRevision) -> set[str]:
        return {
            str(item.get("id"))
            for item in self._objects._automation_definition_objects(active.document)
        }

    def _active_definition(
        self, active: ManagedConfigurationRevision, definition_id: str, action: str
    ) -> dict[str, object]:
        stored = self._stored_definition(active, definition_id)
        if stored is None or definition_id not in self._active_ids(active):
            raise AutomationDefinitionSaveError(
                "automation_definition_not_found",
                f"Automation Task Definition {definition_id!r} is not present in the current "
                "Active configuration",
                status=404,
                definition_id=definition_id,
                stage=action,
                durable_state="active_unchanged",
                side_effects="none",
                next_action=(
                    "refresh the Active Automation inventory and choose an existing definition"
                ),
            )
        return stored

    def _stored_definition(
        self, active: ManagedConfigurationRevision, definition_id: str
    ) -> dict[str, object] | None:
        for item in self._objects._automation_definition_objects(active.document):
            if str(item.get("id")) == definition_id:
                return item
        # A definition that was once published and is no longer Active is a
        # removed definition: its retained history is the *published*
        # configuration its runs used — an open successor Draft's candidate
        # was never published and must never be substituted for it.  A
        # definition that exists only inside an open Draft (a fresh
        # create/copy candidate) has no published evidence and resolves
        # draft-only for explicit correction.
        if self._definition_was_published(definition_id):
            historical = self.historical_definition(
                definition_id,
                occurrence=self._latest_occurrence(definition_id),
            )
            if historical is not None:
                return historical.get("definition")
        return self._open_draft_definition(definition_id)

    def _latest_occurrence(self, definition_id: str):
        """The definition's newest durable occurrence, when a store is bound.

        The application service itself has no runtime-occurrence dependency;
        the API layer binds one through ``bind_occurrence_store`` so the
        historical resolution can pin the exact published revision the run
        used.  Without a bound store the published-evidence scan still
        resolves the newest published revision containing the definition.
        """

        reader = getattr(self, "_occurrence_store", None)
        if reader is None:
            return None
        try:
            return reader(definition_id)
        except Exception:
            return None

    def _open_draft_definition(self, definition_id: str) -> dict[str, object] | None:
        try:
            draft = self._managed.latest_open_draft_containing(
                AUTOMATION_DEFINITION_SECTION, definition_id
            )
        except Exception:
            return None
        if draft is None:
            return None
        try:
            values = self._objects._automation_definition_objects(draft.document)
        except (ValueError, KeyError):
            return None
        for item in values:
            if str(item.get("id")) == definition_id:
                return item
        return None

    def _resolve_source(
        self, active: ManagedConfigurationRevision, definition_id: str, action: str
    ) -> tuple[dict[str, object], str]:
        stored = self._stored_definition(active, definition_id)
        if stored is None:
            raise AutomationDefinitionSaveError(
                "automation_definition_not_found",
                f"Automation Task Definition {definition_id!r} is not present in the current "
                "Active configuration or an open successor Draft",
                status=404,
                definition_id=definition_id,
                stage=action,
                durable_state="active_unchanged",
                side_effects="none",
                next_action=(
                    "refresh the Active Automation inventory and choose an existing definition"
                ),
            )
        if definition_id in self._active_ids(active):
            return stored, "active"
        if self._definition_was_published(definition_id):
            # A removed definition resolves from its durable published
            # history: labelled historical, never Active/Draft authority.
            return stored, "historical"
        return stored, "draft-only"

    def definition_was_published(self, definition_id: str) -> bool:
        """Whether durable activation evidence ever published this definition.

        The API layer uses this to keep its resolution order truthful: a
        definition that was once published and is no longer Active is a
        removed definition whose retained history resolves from published
        evidence, while a definition that exists only inside an open Draft is
        still a draft-only candidate for explicit correction.
        """

        return self._definition_was_published(definition_id)

    def _definition_was_published(self, definition_id: str) -> bool:
        """Whether durable activation evidence ever published this definition."""

        repository = self._managed.repository
        reader = getattr(repository, "list_recent_command_audits", None)
        if not callable(reader):
            return False
        try:
            audits = reader(("activate",), limit=200)
        except Exception:
            return False
        for audit in audits:
            definitions = audit.after.get("automationTaskDefinitions")
            if not isinstance(definitions, dict):
                continue
            items = definitions.get("items")
            if not isinstance(items, list):
                continue
            if any(
                isinstance(item, dict) and str(item.get("id")) == definition_id for item in items
            ):
                return True
        return False

    @staticmethod
    def _form_projection(stored: Mapping[str, object]) -> dict[str, object]:
        values: dict[str, object] = {}
        for field in AUTOMATION_DEFINITION_FORM_FIELDS:
            if field in stored:
                values[field] = copy.deepcopy(stored[field])
        values.setdefault("id", stored.get("id"))
        values.setdefault("enabled", False)
        return values

    def _allocate_copy_id(self, source_id: str, existing: set[str]) -> str:
        base = f"{source_id}-copy"
        if len(base) > MAX_DEFINITION_ID_LENGTH:
            base = f"{source_id[: MAX_DEFINITION_ID_LENGTH - 5]}-copy"
        candidate = base
        if candidate in existing:
            for index in range(2, 101):
                suffix = f"-{index}"
                candidate = f"{base[: MAX_DEFINITION_ID_LENGTH - len(suffix)]}{suffix}"
                if candidate not in existing:
                    break
            else:
                raise AutomationDefinitionSaveError(
                    "automation_definition_duplicate",
                    f"could not allocate a unique copied ID for {source_id!r}",
                    status=409,
                    definition_id=source_id,
                    stage="compose",
                    durable_state="active_unchanged",
                    side_effects="none",
                    next_action="remove an unused copy or create the definition explicitly",
                )
        return candidate

    @staticmethod
    def _definition_map(document: object) -> dict[str, object] | None:
        """Definition-id map for one document, or ``None`` when it is malformed.

        An absent section is a legal empty population (an instance that has never
        published a definition), while a present non-array or a malformed entry is
        unverifiable evidence the caller must fail closed on.
        """

        if not isinstance(document, dict):
            return None
        if AUTOMATION_DEFINITION_SECTION not in document:
            return {}
        section = document.get(AUTOMATION_DEFINITION_SECTION)
        if not isinstance(section, list):
            return None
        values: dict[str, object] = {}
        for entry in section:
            if not (isinstance(entry, dict) and isinstance(entry.get("id"), str)):
                return None
            entry_id = entry["id"]
            if entry_id in values:
                return None
            values[entry_id] = entry
        return values

    def _upcoming_runs(
        self, definition: AutomationTaskDefinition, now: datetime
    ) -> tuple[list[dict[str, object]], list[str]]:
        notes: list[str] = []
        upcoming: list[dict[str, object]] = []
        if definition.interval_seconds is not None:
            current = now
            for _ in range(UPCOMING_RUN_LIMIT):
                current = current + timedelta(seconds=float(definition.interval_seconds))
                upcoming.append({"at": current.isoformat(), "timezone": None})
            notes.append(
                "interval schedules repeat from the moment the Scheduler first evaluates the "
                "definition; the times below are relative to this preview"
            )
            return upcoming, notes
        try:
            timezone = ZoneInfo(str(definition.timezone))
        except (ZoneInfoNotFoundError, ValueError):
            notes.append("the configured timezone could not be resolved")
            return upcoming, notes
        try:
            expression = CronExpression.parse(str(definition.cron))
            current = expression.next_at_or_after(now, timezone)
            for _ in range(UPCOMING_RUN_LIMIT):
                upcoming.append(
                    {
                        "at": current.isoformat(),
                        "timezone": str(definition.timezone),
                        "local": current.astimezone(timezone).isoformat(),
                    }
                )
                current = expression.next_after(current, timezone)
        except (ValueError, ZoneInfoNotFoundError) as error:
            notes.append(self._objects._bounded_utf8(str(error), 240) or "invalid Cron schedule")
        return upcoming, notes

    def _persistence_failed(
        self, definition_id: str | None, revision_id: str
    ) -> AutomationDefinitionSaveError:
        return AutomationDefinitionSaveError(
            "automation_definition_persistence_failed",
            "the Automation Task Definition candidate could not be persisted; the previous "
            "Active remains in use",
            status=503,
            definition_id=definition_id,
            stage="persist",
            revision_id=revision_id,
            durable_state="active_preserved",
            next_action="check configuration persistence health, then retry",
        )

    def _invalid(
        self, message: str, object_id: object, stage: str
    ) -> AutomationDefinitionSaveError:
        return AutomationDefinitionSaveError(
            "automation_definition_invalid_request",
            message,
            status=400,
            definition_id=(
                _bounded(object_id, MAX_DEFINITION_ID_LENGTH)
                if isinstance(object_id, str)
                else None
            ),
            stage=stage,
            durable_state="active_unchanged",
            side_effects="none",
            next_action="correct the reported Automation Task Definition input, then retry",
        )


__all__ = [
    "AUTOMATION_DEFINITION_FORM_DEFAULTS",
    "AUTOMATION_DEFINITION_FORM_FIELDS",
    "AUTOMATION_DEFINITION_SECTION",
    "AutomationWorkspaceCommandService",
    "MAX_DEFINITION_ID_LENGTH",
]
