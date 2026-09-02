"""Read-only projections for managed Automation Task Definition occurrences."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping

from mediaflow.domain.automation import AutomationTaskDefinition

_UNSET = object()


class AutomationDefinitionOccurrenceService:
    """Share bounded occurrence state between API and Operator Web adapters.

    The service only reads the runtime repository.  It never resolves a
    Storage/Provider adapter and never performs scheduler admission.
    """

    def __init__(self, repository) -> None:
        self._repository = repository

    def due_state(self, definition_id: str):
        getter = getattr(self._repository, "get_automation_definition_due_state", None)
        return getter(definition_id) if callable(getter) else None

    def latest(self, definition_id: str):
        getter = getattr(self._repository, "get_latest_automation_definition_occurrence", None)
        return getter(definition_id) if callable(getter) else None

    def list(self, definition_id: str, *, limit: int, after=None, before=None):
        getter = getattr(self._repository, "list_automation_definition_occurrences", None)
        if not callable(getter):
            return ()
        return getter(definition_id, limit=limit, after=after, before=before)

    def project_definitions(
        self,
        definitions,
        *,
        configuration: Mapping[str, object] | None = None,
    ) -> list[dict[str, object]]:
        """Project a bounded definition page with bulk state lookups.

        SQLite supplies one bounded due-state query and one bounded latest-row
        query for the page.  Small test doubles without those optional bulk
        methods retain the single-definition fallback.
        """

        values = list(definitions)
        ids = [
            str(item.get("id") if isinstance(item, Mapping) else getattr(item, "definition_id", ""))
            for item in values
        ]
        states = {}
        list_states = getattr(self._repository, "list_automation_definition_due_states", None)
        if callable(list_states):
            try:
                states = {
                    item.definition_id: item
                    for item in list_states(definition_ids=tuple(ids), limit=max(len(ids), 1))
                }
            except TypeError:
                # Compatibility doubles from before the bulk repository seam
                # can still serve a bounded page through the single-row path.
                states = {}
        latest_values = {}
        list_latest = getattr(
            self._repository,
            "list_latest_automation_definition_occurrences",
            None,
        )
        if callable(list_latest):
            try:
                latest_values = {item.definition_id: item for item in list_latest(tuple(ids))}
            except TypeError:
                latest_values = {}
        return [
            self.project_definition(
                item,
                configuration=configuration,
                _state=states.get(definition_id),
                _latest=latest_values.get(definition_id),
            )
            for item, definition_id in zip(values, ids, strict=True)
        ]

    def project_definition(
        self,
        definition,
        *,
        configuration: Mapping[str, object] | None = None,
        _state=_UNSET,
        _latest=_UNSET,
    ) -> dict[str, object]:
        """Add current due/last-occurrence state to a safe definition document."""

        document = (
            definition.document()
            if callable(getattr(definition, "document", None))
            else dict(definition)
            if isinstance(definition, Mapping)
            else {}
        )
        if not isinstance(document, dict):
            document = dict(document)
        document = copy.deepcopy(document)
        definition_id = str(document.get("id", getattr(definition, "definition_id", "")))
        encoded = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        definition_fingerprint = getattr(definition, "definition_fingerprint", None)
        if not isinstance(definition_fingerprint, str) or len(definition_fingerprint) != 64:
            try:
                definition_fingerprint = AutomationTaskDefinition.from_document(
                    document
                ).definition_fingerprint
            except (TypeError, ValueError):
                definition_fingerprint = hashlib.sha256(encoded).hexdigest()
        state = self.due_state(definition_id) if _state is _UNSET else _state
        latest = self.latest(definition_id) if _latest is _UNSET else _latest
        occurrence = self._state_document(state)
        occurrence["enabled"] = bool(document.get("enabled", False))
        latest_document = latest.document() if latest is not None else None
        occurrence["definitionFingerprint"] = definition_fingerprint
        occurrence["lastOccurrence"] = latest_document
        if latest is not None:
            occurrence.update(
                {
                    "lastConfigurationRevisionId": latest.configuration_revision_id,
                    "lastConfigurationRevisionVersion": latest.configuration_revision_version,
                    "lastConfigurationRevisionDigest": latest.configuration_revision_digest,
                    "lastRunMode": latest.run_mode.value,
                    "lastResourceLibraryId": latest.resource_library_id,
                    "lastSourceScope": latest.source_scope,
                    "lastItemLimit": latest.item_limit,
                }
            )
        document["occurrence"] = occurrence
        document["occurrenceState"] = occurrence
        document["definitionFingerprint"] = definition_fingerprint
        document["lastOccurrence"] = latest_document
        document["nextRunAt"] = occurrence["nextRunAt"]
        document["lastOccurrenceAt"] = occurrence["lastOccurrenceAt"]
        document["lastJobId"] = occurrence["lastJobId"]
        document["lastOutcome"] = occurrence["lastOutcome"]
        document["lastReason"] = occurrence["lastReason"]
        document["nextAction"] = occurrence["nextAction"]
        if configuration is not None:
            document["activeConfiguration"] = {
                key: configuration.get(key)
                for key in ("revisionId", "version", "revisionSequence", "digest")
                if configuration.get(key) is not None
            }
        return document

    @staticmethod
    def _state_document(state) -> dict[str, object]:
        if state is None:
            return {
                "enabled": None,
                "nextRunAt": None,
                "lastOccurrenceAt": None,
                "lastJobId": None,
                "lastOutcome": None,
                "lastReason": None,
                "nextAction": None,
            }
        return {
            "enabled": None,
            "nextRunAt": state.next_run_at.isoformat(),
            "lastOccurrenceAt": (
                state.last_occurrence_at.isoformat() if state.last_occurrence_at else None
            ),
            "lastJobId": state.last_job_id,
            "lastOutcome": state.last_outcome,
            "lastReason": state.last_reason,
            "nextAction": state.last_next_action,
        }


# Compatibility names for adapters/tests that use the shorter projection term.
AutomationOccurrenceProjectionService = AutomationDefinitionOccurrenceService
AutomationDefinitionOccurrenceProjection = AutomationDefinitionOccurrenceService


__all__ = [
    "AutomationDefinitionOccurrenceService",
    "AutomationOccurrenceProjectionService",
    "AutomationDefinitionOccurrenceProjection",
]
