"""Rules-workspace typed object commands (Slice 41, Task 41.2).

This module owns the narrow command and projection boundary the V2 organizing-rules
workspace needs for the five independently creatable foundations of the rule graph —
RecognitionType, MetadataPolicy, NamingPolicy, ClassificationPolicy and OrganizePolicy.

It deliberately composes the existing authorities instead of duplicating them:

* object normalization and whole-document validation stay in
  :class:`ConfigurationObjectService` / :class:`ManagedConfigurationService`, so a V2
  Save can never accept, reject or normalize a field differently from V1, the API,
  the CLI or the runtime;
* the applicable Slice 40 exact-successor read-only evidence gates stay the shared
  ``_checked_successor_evidence`` plus ``activate_checked`` admission gates;
* publication is one checked atomic activation of the exact validated successor, so a
  known failure keeps the previous Active authoritative and an unknown outcome stays a
  state-verification problem rather than an automatic replay.

Every command is composed from one captured immutable Active snapshot and guarded by
the submitted observed Active identity (revision id, sequence and digest verified
server-side).  Reads never create a Draft, Provider call, Task/Job, schedule
occurrence, notification or Storage mutation, and no projection returns a secret
value: provider and Storage credentials are only ever referenced by their
deployment-owned environment variable names.
"""

from __future__ import annotations

import copy
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.naming import SUPPORTED_VARIABLES
from mediaflow.domain.classification import ClassificationError
from mediaflow.domain.configuration_management import (
    ConfigurationActivationConflict,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationReferenceEvidence,
    ConfigurationVersionConflict,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    ResourceLibrarySaveError,
    RulesWorkspaceSaveError,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.duplicates import HashMode
from mediaflow.domain.metadata import (
    METADATA_POLICY_CONFIGURATION_FIELDS,
    MediaQueryType,
    MediaType,
)
from mediaflow.domain.naming import (
    MissingVariableStrategy,
    NamingError,
    NamingMediaTypeMode,
)
from mediaflow.domain.organizer import (
    ConflictStrategy,
    DirectoryCleanupMode,
    OrganizeOperationType,
)
from mediaflow.domain.recognition import ConditionField, ConditionOperator, LogicalOperator
from mediaflow.infrastructure.metadata_provider_bootstrap import (
    SUPPORTED_METADATA_PROVIDER_IDS,
    metadata_provider_secret_env_fields,
)

MAX_RULES_OBJECT_ID_LENGTH = 64
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+ -]{0,63}$")


@dataclass(frozen=True)
class _FamilySpec:
    """One rules-workspace family and the exact authority it exposes.

    ``form_fields`` is the allowlisted typed-form surface, ``kind``/``section`` bind it
    to the existing managed-object authority, and ``supports_enabled`` reflects the real
    domain (OrganizePolicy has no enable state, so the workspace never invents one).
    """

    family: str
    kind: ConfigurationObjectKind
    section: str
    label: str
    form_fields: frozenset[str]
    supports_enabled: bool


RULE_FAMILIES: tuple[str, ...] = (
    "recognitionRules",
    "typeBindings",
    "recognitionTypes",
    "metadataPolicies",
    "namingPolicies",
    "classificationPolicies",
    "organizePolicies",
)

_FAMILY_SPECS: dict[str, _FamilySpec] = {
    "recognitionRules": _FamilySpec(
        family="recognitionRules",
        kind=ConfigurationObjectKind.RECOGNITION_RULE,
        section="recognitionRules",
        label="RecognitionRule",
        form_fields=frozenset(
            {
                "id",
                "name",
                "description",
                "condition",
                "outputRecognitionType",
                "enabled",
                "priority",
                "score",
                "stopOnMatch",
            }
        ),
        supports_enabled=True,
    ),
    "typeBindings": _FamilySpec(
        family="typeBindings",
        kind=ConfigurationObjectKind.RECOGNITION_TYPE_POLICY,
        section="recognitionTypePolicies",
        label="RecognitionTypePolicy",
        form_fields=frozenset(
            {
                "id",
                "name",
                "recognitionType",
                "metadataPolicy",
                "namingPolicy",
                "classificationPolicy",
                "organizePolicy",
                "enabled",
                "priority",
            }
        ),
        supports_enabled=True,
    ),
    "recognitionTypes": _FamilySpec(
        family="recognitionTypes",
        kind=ConfigurationObjectKind.RECOGNITION_TYPE,
        section="recognitionTypes",
        label="RecognitionType",
        form_fields=frozenset({"id", "name", "description", "enabled"}),
        supports_enabled=True,
    ),
    "metadataPolicies": _FamilySpec(
        family="metadataPolicies",
        kind=ConfigurationObjectKind.METADATA_POLICY,
        section="metadataPolicies",
        label="MetadataPolicy",
        form_fields=METADATA_POLICY_CONFIGURATION_FIELDS,
        supports_enabled=True,
    ),
    "namingPolicies": _FamilySpec(
        family="namingPolicies",
        kind=ConfigurationObjectKind.NAMING_POLICY,
        section="namingPolicies",
        label="NamingPolicy",
        form_fields=ConfigurationObjectService._NAMING_POLICY_FIELDS,
        supports_enabled=True,
    ),
    "classificationPolicies": _FamilySpec(
        family="classificationPolicies",
        kind=ConfigurationObjectKind.CLASSIFICATION_POLICY,
        section="classificationPolicies",
        label="ClassificationPolicy",
        form_fields=ConfigurationObjectService._CLASSIFICATION_POLICY_FIELDS,
        supports_enabled=True,
    ),
    "organizePolicies": _FamilySpec(
        family="organizePolicies",
        kind=ConfigurationObjectKind.ORGANIZE_POLICY,
        section="organizePolicies",
        label="OrganizePolicy",
        form_fields=ConfigurationObjectService._ORGANIZE_POLICY_FIELDS,
        supports_enabled=False,
    ),
}

_NAMING_TEMPLATE_FIELDS = (
    "directoryTemplate",
    "filenameTemplate",
    "seriesDirectoryTemplate",
    "seasonDirectoryTemplate",
    "episodeFilenameTemplate",
    "multiEpisodeFileTemplate",
)

# Display defaults for a fresh create form.  They mirror the values `_normalize` and
# the domain models already apply when a field is omitted, so the workspace shows the
# real backend default instead of an invented one.
_FORM_DEFAULTS: dict[str, dict[str, object]] = {
    "recognitionRules": {
        "name": "",
        "description": "",
        "condition": {"operator": "always", "children": []},
        "outputRecognitionType": "",
        "enabled": True,
        "priority": 0,
        "score": 1,
        "stopOnMatch": False,
    },
    "typeBindings": {
        "name": "",
        "recognitionType": "",
        "metadataPolicy": "",
        "namingPolicy": "",
        "classificationPolicy": "",
        "organizePolicy": "",
        "enabled": True,
        "priority": 0,
    },
    "recognitionTypes": {"name": "", "description": "", "enabled": True},
    "metadataPolicies": {
        "providerId": "tmdb",
        "mediaType": MediaType.MOVIE.value,
        "mediaQueryType": MediaQueryType.AUTO.value,
        "language": "zh-CN",
        "region": None,
        "automaticThreshold": 90,
        "confirmationThreshold": 70,
        "minimumScoreGap": 5,
        "timeout": 10,
        "retryCount": 2,
        "maxCandidates": 20,
        "maxSearchPages": 2,
        "maxProviderRequests": 6,
        "maxCandidateEnrichments": 2,
        "enabled": True,
    },
    "namingPolicies": {
        "name": "",
        "description": "",
        "enabled": True,
        "mediaTypeMode": NamingMediaTypeMode.AUTO.value,
        "missingVariableStrategy": MissingVariableStrategy.OMIT_TOKEN.value,
        "maxComponentLength": 200,
        "directoryTemplate": "{title} ({year})",
        "filenameTemplate": "{title} ({year}).{ext}",
        "seriesDirectoryTemplate": "{title} ({year})",
        "seasonDirectoryTemplate": "Season {season:02}",
        "episodeFilenameTemplate": "{title} - S{season:02}E{episode:02} - {episode_title}.{ext}",
        "multiEpisodeFileTemplate": "{title} - S{season:02}{episodes}.{ext}",
    },
    "classificationPolicies": {
        "name": "",
        "description": "",
        "enabled": True,
        "priority": 0,
        "rules": [],
    },
    "organizePolicies": {
        "operation": OrganizeOperationType.MOVE.value,
        "conflictStrategy": ConflictStrategy.MANUAL.value,
        "overwrite": False,
        "attachments": {
            "enabled": False,
            "subtitles": True,
            "nfo": True,
            "artwork": True,
            "trailers": True,
            "otherSameStem": False,
        },
        "duplicateDetection": {
            "mode": HashMode.NONE.value,
            "fastSampleBytes": 1_048_576,
            "fullMaxFileSize": 1_099_511_627_776,
            "chunkSize": 1_048_576,
        },
        "rollback": {"enabled": False, "cleanupCreatedDirectories": True},
        "sourceDirectoryCleanup": {
            "mode": DirectoryCleanupMode.NONE.value,
            "maxParentDirectories": 1,
            "ignorePatterns": [],
            "maxEntries": 100,
        },
    },
}

_CLASSIFICATION_CONDITION_FIELDS = (
    "mediaType",
    "mediaTypes",
    "genres",
    "countries",
    "languages",
    "yearMin",
    "yearMax",
    "canonicalYear",
    "keywords",
)


def _bounded(value: object, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:maximum]


class RulesWorkspaceCommandService:
    """One Save-and-activate command per intended rules-object change."""

    def __init__(self, objects: ConfigurationObjectService) -> None:
        self._objects = objects
        self._managed: ManagedConfigurationService = objects._managed

    # ------------------------------------------------------------------
    # Zero-mutation candidate previews
    # ------------------------------------------------------------------

    def preview_naming(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        policy_id: str,
        sample: Mapping[str, object],
    ):
        """Run the production naming engine against the exact inspected revision."""
        return self._objects.naming_preview(
            revision_id,
            expected_version=expected_version,
            expected_digest=expected_digest,
            actor=actor,
            policy_id=policy_id,
            sample=sample,
        )

    def preview_classification(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        policy_id: str,
        sample: Mapping[str, object],
    ):
        """Run the production classification engine without Storage access."""
        return self._objects.classification_preview(
            revision_id,
            expected_version=expected_version,
            expected_digest=expected_digest,
            actor=actor,
            policy_id=policy_id,
            sample=sample,
        )

    def explain_organize(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        recognition_type: str,
    ):
        """Explain declared organize authority; never issue execution authority."""
        return self._objects.organize_authority(
            revision_id,
            expected_version=expected_version,
            expected_digest=expected_digest,
            actor=actor,
            recognition_type=recognition_type,
        )

    def preview_strategy(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        resource_library_id: str,
        synthetic_path: str,
        live_metadata: bool = False,
    ):
        """Run the bounded strategy test through the shared application authority."""
        return self._objects.recognition_strategy_test(
            revision_id,
            expected_version=expected_version,
            expected_digest=expected_digest,
            actor=actor,
            resource_library_id=resource_library_id,
            synthetic_path=synthetic_path,
            live_metadata=live_metadata,
        )

    # ------------------------------------------------------------------
    # Reads (zero configuration, Provider, Task/Job or Storage side effects)
    # ------------------------------------------------------------------

    def authority(self) -> dict[str, object]:
        """Return the exact Active identity a page binds its next Save to."""

        active = self._require_active_read("authority")
        return {"active": active.summary(), "sideEffects": "none"}

    def form_authority(self) -> dict[str, object]:
        """Return the bounded typed-form authority derived from the actual domain.

        The projection answers "which fields, values and references exist here" from
        the same domain enums, field allowlists, configured MediaLibraries and supported
        Metadata Providers the backend already uses.  It never invents a provider,
        variable, condition, operation or fallback, and secret readiness reports only
        whether a deployment-owned environment variable name is SET or UNSET.
        """

        active = self._require_active_read("form authority")
        media_libraries = [
            {
                "id": _bounded(item.get("id"), MAX_RULES_OBJECT_ID_LENGTH),
                "name": _bounded(item.get("name"), 120),
                "enabled": item.get("enabled", True) is not False,
                "storageId": _bounded(item.get("storageId"), MAX_RULES_OBJECT_ID_LENGTH),
            }
            for item in self._objects._canonical_objects(active.document, "mediaLibraries")
        ]
        providers = [
            {
                "providerId": provider_id,
                "secretReadiness": [
                    {
                        "field": field,
                        "state": "SET" if os.environ.get(field) else "UNSET",
                    }
                    for field in metadata_provider_secret_env_fields(provider_id)
                ],
            }
            for provider_id in sorted(SUPPORTED_METADATA_PROVIDER_IDS)
        ]
        catalogs = {
            family: [
                {
                    "id": str(item.get("id")),
                    "name": _bounded(item.get("name"), 120) or str(item.get("id")),
                    "enabled": item.get("enabled", True) is not False,
                }
                for item in self._objects._canonical_objects(active.document, section)
            ]
            for family, section in (
                ("recognitionTypes", "recognitionTypes"),
                ("metadataPolicies", "metadataPolicies"),
                ("namingPolicies", "namingPolicies"),
                ("classificationPolicies", "classificationPolicies"),
                ("organizePolicies", "organizePolicies"),
            )
        }
        families = []
        for family in RULE_FAMILIES:
            spec = _FAMILY_SPECS[family]
            families.append(
                {
                    "family": family,
                    "kind": spec.kind.value,
                    "label": spec.label,
                    "fields": sorted(spec.form_fields),
                    "supportsEnabled": spec.supports_enabled,
                    "defaults": copy.deepcopy(_FORM_DEFAULTS[family]),
                    "actions": {
                        "create": True,
                        "edit": True,
                        "copy": True,
                        "toggle": spec.supports_enabled,
                        "remove": True,
                    },
                }
            )
        return {
            "active": active.summary(),
            "sideEffects": "none",
            "families": families,
            "mediaLibraries": media_libraries,
            "metadataProviders": providers,
            "catalogs": catalogs,
            "enums": {
                "mediaTypes": [item.value for item in MediaType],
                "mediaQueryTypes": [item.value for item in MediaQueryType],
                "namingMediaTypeModes": [item.value for item in NamingMediaTypeMode],
                "missingVariableStrategies": [item.value for item in MissingVariableStrategy],
                "namingTemplates": list(_NAMING_TEMPLATE_FIELDS),
                "namingVariables": list(SUPPORTED_VARIABLES),
                "numericNamingVariables": ["year", "season", "episode"],
                "classificationConditions": list(_CLASSIFICATION_CONDITION_FIELDS),
                "organizeOperations": [
                    OrganizeOperationType.MOVE.value,
                    OrganizeOperationType.COPY.value,
                    OrganizeOperationType.HARD_LINK.value,
                    OrganizeOperationType.SOFT_LINK.value,
                ],
                "conflictStrategies": [item.value for item in ConflictStrategy],
                "cleanupModes": [item.value for item in DirectoryCleanupMode],
                "hashModes": [item.value for item in HashMode],
                "conditionFields": [item.value for item in ConditionField],
                "conditionOperators": [item.value for item in ConditionOperator],
                "logicalOperators": [item.value for item in LogicalOperator],
            },
            "limits": {
                "objectId": MAX_RULES_OBJECT_ID_LENGTH,
                "name": 120,
                "description": 1000,
                "maxComponentLength": {"minimum": 8, "maximum": 255},
                "classificationRules": {"minimum": 1, "maximum": 128},
                "classificationRuleConditions": 64,
            },
        }

    def edit_projection(self, family: str, object_id: str) -> dict[str, object]:
        """Typed edit prefill for one exact Active object, with its reference impact."""

        active, spec, stored = self._active_object(family, object_id, "edit")
        return {
            "family": family,
            "object": self._form_projection(spec, stored),
            "references": self._impact(spec, stored, active),
            "active": active.summary(),
            "sideEffects": "none",
        }

    def copy_projection(self, family: str, object_id: str) -> dict[str, object]:
        """One new-ID copy candidate prefill computed from the backend field authority.

        The copy keeps the source's typed field values, receives a fresh stable ID and a
        bounded name, and defaults to disabled for the kinds that actually support an
        enabled state (OrganizePolicy has none, so none is invented).  Nothing is
        persisted here: the operator's single `保存` publishes the candidate.
        """

        active, spec, stored = self._active_object(family, object_id, "copy")
        values = self._form_projection(spec, stored)
        section_values = self._objects._canonical_objects(active.document, spec.section)
        candidate_id = self._allocate_copy_id(str(stored["id"]), section_values)
        values["id"] = candidate_id
        source_name = str(stored.get("name") or stored["id"])
        # Only a family whose domain actually owns a name receives the copied label;
        # OrganizePolicy has no name field, so none is invented for it.
        if "name" in spec.form_fields:
            values["name"] = f"{source_name[:115]} copy"
        if spec.supports_enabled:
            values["enabled"] = False
        return {
            "family": family,
            "object": values,
            "source": {"id": str(stored["id"]), "name": source_name},
            "active": active.summary(),
            "sideEffects": "none",
            "nextAction": (
                f"review the copied {spec.label} fields and save to publish it as Active"
            ),
        }

    def removal_impact(self, family: str, object_id: str) -> dict[str, object]:
        """Bounded reference impact that decides whether a removal is safe."""

        active, spec, stored = self._active_object(family, object_id, "removal impact")
        return {
            "family": family,
            "object": {"id": str(stored["id"]), "name": _bounded(stored.get("name"), 120)},
            "references": self._impact(spec, stored, active),
            "active": active.summary(),
            "sideEffects": "none",
        }

    # ------------------------------------------------------------------
    # Commands (one explicit intent publishes one exact Active successor)
    # ------------------------------------------------------------------

    def save_object(
        self,
        family: str,
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

        ``object_id`` carries the route's explicit intent: a create has none and its
        candidate ID is new, while an edit is the already-opened object whose ID stays
        immutable.  Inferring that from the body would let one filled-in form silently
        change an object's identity or overwrite an unrelated Active row.
        """

        spec = self._spec(family, "save")
        if not isinstance(candidate, Mapping):
            raise self._invalid(spec, "compose", f"The {spec.label} candidate must be an object")
        return self._publish(
            spec,
            candidate,
            object_id=object_id,
            actor=actor,
            expected_revision_id=expected_revision_id,
            expected_version=expected_version,
            expected_digest=expected_digest,
            before_publish=before_publish,
            audit_action="rules_edit" if object_id is not None else "rules_create",
        )

    def set_enabled(
        self,
        family: str,
        object_id: str,
        *,
        enabled: bool,
        actor: str,
        expected_revision_id: str,
        expected_version: int,
        expected_digest: str,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
    ) -> ManagedConfigurationRevision:
        """Publish one explicit enabled-state successor for an exact Active object."""

        spec = self._spec(family, "state change")
        if not isinstance(enabled, bool):
            raise self._invalid(spec, "compose", f"{spec.label} enabled must be boolean")
        if not spec.supports_enabled:
            raise RulesWorkspaceSaveError(
                "rules_operation_unsupported",
                f"{spec.label} does not support enable/disable in the domain model",
                status=400,
                object_kind=spec.family,
                object_id=object_id,
                stage="compose",
                durable_state="active_unchanged",
                side_effects="none",
                next_action=(
                    "edit the policy settings instead; an enable state that the domain does "
                    "not have is never invented for convenience"
                ),
            )
        active, _spec, stored = self._command_target(
            spec,
            object_id,
            expected_revision_id=expected_revision_id,
            expected_version=expected_version,
            expected_digest=expected_digest,
            action="enable" if enabled else "disable",
        )
        value = self._form_projection(spec, stored)
        value["enabled"] = enabled
        return self._publish(
            spec,
            value,
            object_id=object_id,
            actor=actor,
            expected_revision_id=active.revision_id,
            expected_version=active.revision_sequence or active.version,
            expected_digest=active.digest,
            before_publish=before_publish,
            audit_action="rules_enable" if enabled else "rules_disable",
            audit_metadata={"surface": "rules", "family": spec.family, "enabled": enabled},
        )

    def remove_object(
        self,
        family: str,
        object_id: str,
        *,
        actor: str,
        expected_revision_id: str,
        expected_version: int,
        expected_digest: str,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None = None,
    ) -> ManagedConfigurationRevision:
        """Remove one unreferenced object through the same checked publication path."""

        spec = self._spec(family, "removal")
        active, _spec, _stored = self._command_target(
            spec,
            object_id,
            expected_revision_id=expected_revision_id,
            expected_version=expected_version,
            expected_digest=expected_digest,
            action="remove",
        )
        evidence = self._reference_evidence(spec, object_id, active)
        if evidence.total:
            raise RulesWorkspaceSaveError(
                "rules_object_referenced",
                (
                    f"{spec.label} {object_id!r} is referenced by {evidence.total} "
                    "configuration object(s); removal is reference-protected"
                ),
                status=409,
                object_kind=spec.family,
                object_id=object_id,
                stage="reference",
                durable_state="active_unchanged",
                side_effects="none",
                next_action=(
                    "repoint or remove the listed dependents first, then retry the removal"
                ),
                reference_items=tuple(
                    {
                        **item.document(),
                        "label": self._dependent_label(active, item.section, item.object_id),
                    }
                    for item in evidence.items
                ),
            )
        return self._publish(
            spec,
            None,
            object_id=object_id,
            actor=actor,
            expected_revision_id=active.revision_id,
            expected_version=active.revision_sequence or active.version,
            expected_digest=active.digest,
            before_publish=before_publish,
            audit_action="rules_remove",
            audit_metadata={"surface": "rules", "family": spec.family, "removed": object_id},
        )

    # ------------------------------------------------------------------
    # Shared publication core
    # ------------------------------------------------------------------

    def _publish(
        self,
        spec: _FamilySpec,
        candidate: Mapping[str, object] | None,
        *,
        object_id: str | None,
        actor: str,
        expected_revision_id: str,
        expected_version: int,
        expected_digest: str,
        before_publish: Callable[[ManagedConfigurationRevision], object] | None,
        audit_action: str,
        audit_metadata: Mapping[str, object] | None = None,
    ) -> ManagedConfigurationRevision:
        delete = candidate is None
        if not delete and object_id is not None:
            submitted_id = candidate.get("id") if isinstance(candidate, Mapping) else None
            if submitted_id != object_id:
                raise RulesWorkspaceSaveError(
                    "rules_id_immutable",
                    f"{spec.label} ID cannot change during update",
                    status=400,
                    object_kind=spec.family,
                    object_id=object_id,
                    stage="compose",
                    durable_state="active_unchanged",
                    side_effects="none",
                    next_action="keep the object ID and correct the editable fields instead",
                )

        active = self._capture_active(spec, "save")
        self._assert_current_authority(
            spec, active, expected_revision_id, expected_version, expected_digest
        )
        section_values = self._objects._canonical_objects(active.document, spec.section)
        current = {str(item["id"]): item for item in section_values}

        if delete:
            assert object_id is not None
            if object_id not in current:
                raise self._not_found(spec, object_id, "compose")
            composed: Mapping[str, object] | None = None
        else:
            assert candidate is not None
            stored = current.get(object_id) if object_id is not None else None
            if object_id is not None and stored is None:
                raise self._not_found(spec, str(object_id), "compose")
            submitted_id = candidate.get("id")
            if object_id is None and isinstance(submitted_id, str) and submitted_id in current:
                raise RulesWorkspaceSaveError(
                    "rules_duplicate",
                    f"{spec.label} ID {submitted_id!r} already exists in the current Active",
                    status=409,
                    object_kind=spec.family,
                    object_id=submitted_id,
                    stage="compose",
                    durable_state="active_preserved",
                    side_effects="none",
                    next_action="choose a different ID, or edit the existing object",
                )
            # Compose only the focused change: unexposed fields survive from the exact
            # Active object, so a typed Save never silently rewrites or drops state the
            # form does not render.
            merged = copy.deepcopy(stored) if stored is not None else {}
            for field in spec.form_fields:
                if field in candidate:
                    merged[field] = copy.deepcopy(candidate[field])
            unknown = set(candidate).difference(spec.form_fields)
            if unknown:
                raise self._invalid(
                    spec,
                    "compose",
                    f"{spec.label} candidate contains unsupported field {sorted(unknown)[0]!r}",
                )
            self._validate_form_fields(spec, merged)
            composed = self._normalize_or_reject(spec, merged)
            self._validate_references(spec, composed, active.document, object_id)

        try:
            draft = self._managed.create_successor_draft(
                actor=actor,
                expected_active_revision_id=active.revision_id,
                expected_active_version=active.revision_sequence or active.version,
                expected_active_digest=active.digest,
                verified_active=active,
            )
        except (ConfigurationVersionConflict, RuntimeSnapshotUnavailable):
            raise
        except Exception as error:
            raise RulesWorkspaceSaveError(
                "rules_persistence_failed",
                (
                    "the successor configuration could not be created; the previous Active "
                    "remains in use"
                ),
                status=503,
                object_kind=spec.family,
                object_id=object_id,
                stage="persist",
                durable_state="active_preserved",
                next_action="check configuration persistence health, then retry",
            ) from error

        try:
            edited = self._objects.mutate(
                draft.revision_id,
                spec.kind,
                object_id=object_id,
                value=composed,
                expected_version=draft.version,
                actor=actor,
                delete=delete,
                audit_action=audit_action,
                audit_metadata={
                    **(audit_metadata or {}),
                    "candidate": None if composed is None else copy.deepcopy(dict(composed)),
                },
            )
        except (ConfigurationVersionConflict, ConfigurationActivationConflict):
            raise
        except ConfigurationObjectReferenced as error:
            raise RulesWorkspaceSaveError(
                "rules_object_referenced",
                str(error),
                status=409,
                object_kind=spec.family,
                object_id=object_id,
                stage="reference",
                durable_state="active_unchanged",
                side_effects="none",
                next_action=(
                    "repoint or remove the listed dependents first, then retry the removal"
                ),
                reference_items=tuple(
                    item.document()
                    for item in (
                        error.reference_evidence.items
                        if error.reference_evidence is not None
                        else ()
                    )
                ),
            ) from error
        except Exception as error:
            raise RulesWorkspaceSaveError(
                "rules_persistence_failed",
                (
                    "the configuration candidate could not be persisted; the previous Active "
                    "remains in use"
                ),
                status=503,
                revision_id=draft.revision_id,
                object_kind=spec.family,
                object_id=object_id,
                stage="persist",
                durable_state="active_preserved",
                next_action="check configuration persistence health, then retry",
            ) from error

        try:
            validated = self._managed.validate(edited.revision_id, actor=actor)
        except (ConfigurationVersionConflict, ConfigurationActivationConflict):
            raise
        except Exception as error:
            raise RulesWorkspaceSaveError(
                "rules_persistence_failed",
                (
                    "the successor configuration could not be validated; the previous Active "
                    "remains in use"
                ),
                status=503,
                revision_id=edited.revision_id,
                object_kind=spec.family,
                object_id=object_id,
                stage="validate",
                durable_state="active_preserved",
                next_action="check configuration persistence health, then retry",
            ) from error
        if validated.status is not ManagedConfigurationStatus.VALIDATED:
            raise RulesWorkspaceSaveError(
                "rules_validation_failed",
                (
                    "the successor configuration failed complete whole-document validation; "
                    "the previous Active remains in use"
                ),
                status=422,
                revision_id=validated.revision_id,
                object_kind=spec.family,
                object_id=object_id,
                stage="validate",
                durable_state="active_preserved",
                next_action=self._validation_next_action(validated),
            )

        self._objects._checked_successor_evidence(validated, actor=actor, code_prefix="rules")

        try:
            return self._objects.activate_checked(
                validated.revision_id,
                expected_version=validated.version,
                actor=actor,
                before_publish=before_publish,
            )
        except RulesWorkspaceSaveError:
            raise
        except ResourceLibrarySaveError:
            raise
        except ConfigurationActivationConflict as error:
            if error.current_revision_id is not None:
                raise
            raise RulesWorkspaceSaveError(
                "rules_evidence_failed",
                (
                    "checked activation admission failed; the previous Active remains in use "
                    "and the candidate was not published"
                ),
                revision_id=validated.revision_id,
                object_kind=spec.family,
                object_id=object_id,
                stage="activate",
                durable_state="active_preserved",
                next_action=(
                    error.next_action or "refresh the current Active configuration and retry Save"
                ),
            ) from error
        except ConfigurationVersionConflict:
            raise
        except Exception as error:
            raise RulesWorkspaceSaveError(
                "rules_persistence_failed",
                ("the successor could not be published; the previous Active remains in use"),
                status=503,
                revision_id=validated.revision_id,
                object_kind=spec.family,
                object_id=object_id,
                stage="activate",
                durable_state="active_preserved",
                next_action="check configuration persistence health, then retry Save",
            ) from error

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _spec(self, family: str, action: str) -> _FamilySpec:
        spec = _FAMILY_SPECS.get(family) if isinstance(family, str) else None
        if spec is None:
            raise RulesWorkspaceSaveError(
                "rules_family_unsupported",
                f"{family!r} is not a rules-workspace object family",
                status=400,
                object_kind=family if isinstance(family, str) else None,
                stage="compose",
                durable_state="active_unchanged",
                side_effects="none",
                next_action=(
                    f"choose one of {', '.join(RULE_FAMILIES)}; type bindings and recognition "
                    "rules are edited on their own surfaces"
                ),
            )
        return spec

    def _capture_active(self, spec: _FamilySpec, action: str) -> ManagedConfigurationRevision:
        active = self._managed.active()
        if active is None:
            # Reuse the managed service's fail-closed missing/marker distinction.
            self._managed.create_successor_draft(actor="system")
            raise RuntimeSnapshotUnavailable(
                f"no Active configuration exists; {spec.label} {action} is unavailable",
                reason="active_missing",
            )
        self._managed.verify_integrity(active)
        return active

    def _require_active_read(self, surface: str) -> ManagedConfigurationRevision:
        active = self._managed.active()
        if active is None:
            raise RuntimeSnapshotUnavailable(
                f"no Active configuration exists; rules {surface} is unavailable",
                reason="active_missing",
            )
        self._managed.verify_integrity(active)
        return active

    def _assert_current_authority(
        self,
        spec: _FamilySpec,
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
            raise self._invalid(
                spec,
                "authority",
                (
                    f"{spec.label} Save requires the observed Active revision identity "
                    "(expectedRevisionId, expectedVersion and expectedDigest)"
                ),
            )
        if (
            active.revision_id != expected_revision_id
            or (active.revision_sequence or active.version) != expected_version
            or active.digest != expected_digest
        ):
            raise ConfigurationVersionConflict(
                (
                    f"the {spec.label} Save is stale; the Active configuration changed after "
                    "this form was opened"
                ),
                revision_id=active.revision_id,
                current_version=active.revision_sequence or active.version,
                current_digest=active.digest,
                durable_state="active_preserved",
                next_action=(
                    "refresh the Active rules inventory, review the current object, and save "
                    "the intended change again"
                ),
            )

    def _command_target(
        self,
        spec: _FamilySpec,
        object_id: str,
        *,
        expected_revision_id: str,
        expected_version: int,
        expected_digest: str,
        action: str,
    ) -> tuple[ManagedConfigurationRevision, _FamilySpec, dict[str, object]]:
        self._identifier(spec, object_id, action)
        active = self._capture_active(spec, action)
        self._assert_current_authority(
            spec, active, expected_revision_id, expected_version, expected_digest
        )
        for item in self._objects._canonical_objects(active.document, spec.section):
            if str(item.get("id")) == object_id:
                return active, spec, item
        raise self._not_found(spec, object_id, action)

    def _active_object(
        self, family: str, object_id: str, action: str
    ) -> tuple[ManagedConfigurationRevision, _FamilySpec, dict[str, object]]:
        spec = self._spec(family, action)
        self._identifier(spec, object_id, action)
        active = self._require_active_read(f"{spec.label} {action}")
        stored = self._stored_object(active, spec, object_id)
        return active, spec, stored

    @staticmethod
    def _identifier(spec: _FamilySpec, object_id: object, action: str) -> None:
        if (
            not isinstance(object_id, str)
            or not object_id
            or len(object_id) > MAX_RULES_OBJECT_ID_LENGTH
            or not _SAFE_IDENTIFIER.fullmatch(object_id)
        ):
            raise RulesWorkspaceSaveError(
                "rules_invalid_request",
                f"{spec.label} ID is not a safe bounded identifier",
                status=400,
                object_kind=spec.family,
                stage=action,
                durable_state="active_unchanged",
                side_effects="none",
                next_action="refresh the Active rules inventory and choose an existing object",
            )

    def _stored_object(
        self, active: ManagedConfigurationRevision, spec: _FamilySpec, object_id: str
    ) -> dict[str, object]:
        for item in self._objects._canonical_objects(active.document, spec.section):
            if str(item.get("id")) == object_id:
                return item
        raise LookupError(f"{spec.section} {object_id!r} was not found in the Active configuration")

    def _form_projection(
        self, spec: _FamilySpec, stored: Mapping[str, object]
    ) -> dict[str, object]:
        """Project one stored object into exactly the typed form fields it owns."""

        values: dict[str, object] = {}
        for field in spec.form_fields:
            if field in stored:
                values[field] = copy.deepcopy(stored[field])
        if "id" not in values:
            values["id"] = stored.get("id")
        if spec.supports_enabled:
            values.setdefault("enabled", True)
        return values

    def _normalize_or_reject(
        self, spec: _FamilySpec, value: Mapping[str, object]
    ) -> dict[str, object]:
        """Reuse the shared managed-object normalizer; report its reason, never a raw stack."""

        try:
            return self._objects._normalize(spec.kind, value)
        except (NamingError, ClassificationError, ValueError) as error:
            message = self._objects._bounded_utf8(str(error), 384) or "invalid value"
            raise RulesWorkspaceSaveError(
                "rules_invalid_field",
                f"{spec.label} field is invalid: {message}",
                status=400,
                object_kind=spec.family,
                object_id=_bounded(value.get("id"), MAX_RULES_OBJECT_ID_LENGTH),
                stage="compose",
                durable_state="active_unchanged",
                side_effects="none",
                next_action=f"correct the reported {spec.label} field, then save again",
            ) from error

    def _validate_form_fields(self, spec: _FamilySpec, value: Mapping[str, object]) -> None:
        """Cheap structural guards that keep a malformed body from reaching normalization."""

        for field in ("description", "name", "providerId"):
            raw = value.get(field)
            if isinstance(raw, str) and len(raw) > 4096:
                raise self._invalid(
                    spec, "compose", f"{spec.label} {field} is too long", object_id=value.get("id")
                )
        templates = value.get("directoryTemplate")
        if isinstance(templates, str) and len(templates) > 4096:
            raise self._invalid(
                spec, "compose", f"{spec.label} template is too long", object_id=value.get("id")
            )
        rules = value.get("rules")
        if isinstance(rules, list) and len(rules) > 128:
            raise self._invalid(
                spec,
                "compose",
                f"{spec.label} rules must not exceed 128 entries",
                object_id=value.get("id"),
            )

    def _validate_references(
        self,
        spec: _FamilySpec,
        value: Mapping[str, object],
        document: Mapping[str, object],
        object_id: str | None,
    ) -> None:
        """Reject declared references this deployment cannot honor.

        A MetadataPolicy may only point at a Provider this service can construct, and
        every ClassificationPolicy rule must name an enabled configured MediaLibrary:
        both are real runtime authorities, so accepting a dangling reference would let a
        published Active configuration silently under-deliver downstream.
        """

        if spec.family == "recognitionRules":
            output = str(value.get("outputRecognitionType") or "")
            types = {
                str(item.get("id")): item
                for item in self._objects._canonical_objects(document, "recognitionTypes")
            }
            target = types.get(output)
            if target is None or target.get("enabled", True) is False:
                raise RulesWorkspaceSaveError(
                    "rules_reference_unavailable",
                    f"RecognitionRule output RecognitionType {output!r} is missing or disabled",
                    status=409,
                    object_kind=spec.family,
                    object_id=_bounded(value.get("id"), MAX_RULES_OBJECT_ID_LENGTH),
                    stage="reference",
                    durable_state="active_preserved",
                    side_effects="none",
                    next_action="choose an enabled RecognitionType, then save again",
                )
            return
        if spec.family == "typeBindings":
            refs = {
                "recognitionType": "recognitionTypes",
                "metadataPolicy": "metadataPolicies",
                "namingPolicy": "namingPolicies",
                "classificationPolicy": "classificationPolicies",
                "organizePolicy": "organizePolicies",
            }
            for field, section in refs.items():
                catalog = {
                    str(item.get("id")): item
                    for item in self._objects._canonical_objects(document, section)
                }
                target = catalog.get(str(value.get(field)))
                if target is None or (
                    section != "organizePolicies" and target.get("enabled", True) is False
                ):
                    raise RulesWorkspaceSaveError(
                        "rules_reference_unavailable",
                        f"RecognitionTypePolicy {field} references a missing or disabled object",
                        status=409,
                        object_kind=spec.family,
                        object_id=_bounded(value.get("id"), MAX_RULES_OBJECT_ID_LENGTH),
                        stage="reference",
                        durable_state="active_preserved",
                        side_effects="none",
                        next_action=f"choose an enabled {field} reference, then save again",
                    )
            if value.get("enabled", True) is not False:
                for item in self._objects._canonical_objects(document, "recognitionTypePolicies"):
                    if (
                        str(item.get("id")) != str(value.get("id"))
                        and item.get("enabled", True) is not False
                        and str(item.get("recognitionType")) == str(value.get("recognitionType"))
                    ):
                        raise RulesWorkspaceSaveError(
                            "rules_duplicate_enabled_binding",
                            "only one enabled RecognitionTypePolicy may bind each RecognitionType",
                            status=409,
                            object_kind=spec.family,
                            object_id=_bounded(value.get("id"), MAX_RULES_OBJECT_ID_LENGTH),
                            stage="reference",
                            durable_state="active_preserved",
                            side_effects="none",
                            next_action="disable or edit the existing binding, then save again",
                        )
            return
        if spec.family == "metadataPolicies":
            provider_id = str(value.get("providerId") or "")
            if provider_id not in SUPPORTED_METADATA_PROVIDER_IDS:
                raise RulesWorkspaceSaveError(
                    "rules_reference_unavailable",
                    (
                        f"Metadata Provider {provider_id!r} is not configured by this service; "
                        "supported providers: " + ", ".join(sorted(SUPPORTED_METADATA_PROVIDER_IDS))
                    ),
                    status=409,
                    object_kind=spec.family,
                    object_id=_bounded(value.get("id"), MAX_RULES_OBJECT_ID_LENGTH),
                    stage="reference",
                    durable_state="active_preserved",
                    side_effects="none",
                    next_action=(
                        "choose a configured provider, or deploy the Provider the policy needs, "
                        "then save again"
                    ),
                )
            secret_fields = metadata_provider_secret_env_fields(provider_id)
            if secret_fields and not any(os.environ.get(field) for field in secret_fields):
                raise RulesWorkspaceSaveError(
                    "rules_provider_secret_unavailable",
                    (f"Metadata Provider {provider_id!r} has no configured deployment credential"),
                    status=409,
                    object_kind=spec.family,
                    object_id=_bounded(value.get("id"), MAX_RULES_OBJECT_ID_LENGTH),
                    stage="reference",
                    durable_state="active_preserved",
                    side_effects="none",
                    next_action=(
                        "set one approved Provider credential environment variable, then "
                        "refresh readiness and save again"
                    ),
                )
            return
        if spec.family != "classificationPolicies":
            return
        libraries = {
            str(item.get("id")): item
            for item in self._objects._canonical_objects(document, "mediaLibraries")
        }
        rules = value.get("rules")
        if not isinstance(rules, list):
            return
        for index, rule in enumerate(rules):
            if not isinstance(rule, Mapping):
                continue
            result = rule.get("result")
            result = result if isinstance(result, Mapping) else rule
            library_id = result.get("mediaLibraryId")
            if not isinstance(library_id, str) or not library_id:
                continue
            library = libraries.get(library_id)
            if library is None:
                raise RulesWorkspaceSaveError(
                    "rules_reference_unavailable",
                    (
                        f"classification rules[{index}] references MediaLibrary {library_id!r} "
                        "which is not configured in the current Active configuration"
                    ),
                    status=409,
                    object_kind=spec.family,
                    object_id=_bounded(value.get("id"), MAX_RULES_OBJECT_ID_LENGTH),
                    stage="reference",
                    durable_state="active_preserved",
                    side_effects="none",
                    next_action=(
                        "add or correct the MediaLibrary in the media destination settings, "
                        "or repoint the rule, then save again"
                    ),
                )
            if library.get("enabled", True) is False:
                raise RulesWorkspaceSaveError(
                    "rules_reference_disabled",
                    (
                        f"classification rules[{index}] references disabled MediaLibrary "
                        f"{library_id!r}; a destination rule cannot resolve to it"
                    ),
                    status=409,
                    object_kind=spec.family,
                    object_id=_bounded(value.get("id"), MAX_RULES_OBJECT_ID_LENGTH),
                    stage="reference",
                    durable_state="active_preserved",
                    side_effects="none",
                    next_action=(
                        f"enable MediaLibrary {library_id!r} or repoint the rule to an enabled "
                        "library, then save again"
                    ),
                )
        return

    def _validation_next_action(self, validated: ManagedConfigurationRevision) -> str:
        errors = validated.validation_errors
        if not errors:
            return "correct the blocking configuration, then save again"
        first = self._objects._bounded_utf8(str(errors[0]), 240)
        return f"correct the reported configuration error ({first}), then save again"

    def _reference_evidence(
        self, spec: _FamilySpec, object_id: str, active: ManagedConfigurationRevision
    ) -> ConfigurationReferenceEvidence:
        return self._objects._references_for(spec.kind, object_id, active.document)

    def _impact(
        self, spec: _FamilySpec, stored: Mapping[str, object], active: ManagedConfigurationRevision
    ) -> dict[str, object]:
        object_id = str(stored.get("id"))
        evidence = self._reference_evidence(spec, object_id, active)
        items = [item.document() for item in evidence.items]
        for item in items:
            item["label"] = self._dependent_label(active, str(item["section"]), str(item["id"]))
        return {
            "total": evidence.total,
            "items": items,
            "truncated": evidence.truncated,
            "removalBlocked": bool(evidence.total),
        }

    def _dependent_label(
        self, active: ManagedConfigurationRevision, section: str, item_id: str
    ) -> str:
        try:
            candidates = self._objects._canonical_objects(active.document, section)
        except (ValueError, KeyError):
            candidates = []
        for item in candidates:
            if str(item.get("id")) == item_id:
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()[:120]
        return item_id[:120]

    def _allocate_copy_id(self, source_id: str, section_values: list[dict[str, object]]) -> str:
        existing = {str(item.get("id")) for item in section_values}
        base = f"{source_id}-copy"
        if len(base) > MAX_RULES_OBJECT_ID_LENGTH:
            base = f"{source_id[: MAX_RULES_OBJECT_ID_LENGTH - 5]}-copy"
        candidate = base
        if candidate in existing:
            for index in range(2, 101):
                suffix = f"-{index}"
                candidate = f"{base[: MAX_RULES_OBJECT_ID_LENGTH - len(suffix)]}{suffix}"
                if candidate not in existing:
                    break
            else:
                raise RulesWorkspaceSaveError(
                    "rules_duplicate",
                    f"could not allocate a unique copied {base!r} ID",
                    status=409,
                    stage="compose",
                    durable_state="active_unchanged",
                    side_effects="none",
                    next_action="remove an unused copy or create the object explicitly",
                )
        return candidate

    def _invalid(
        self,
        spec: _FamilySpec,
        stage: str,
        message: str,
        *,
        object_id: object = None,
    ) -> RulesWorkspaceSaveError:
        return RulesWorkspaceSaveError(
            "rules_invalid_request",
            message,
            status=400,
            object_kind=spec.family,
            object_id=_bounded(object_id, MAX_RULES_OBJECT_ID_LENGTH)
            if isinstance(object_id, str)
            else None,
            stage=stage,
            durable_state="active_unchanged",
            side_effects="none",
            next_action=f"correct the reported {spec.label} input, then retry",
        )

    def _not_found(self, spec: _FamilySpec, object_id: str, stage: str) -> RulesWorkspaceSaveError:
        return RulesWorkspaceSaveError(
            "rules_object_not_found",
            f"{spec.label} {object_id!r} is not present in the current Active configuration",
            status=404,
            object_kind=spec.family,
            object_id=object_id,
            stage=stage,
            durable_state="active_unchanged",
            side_effects="none",
            next_action="refresh the Active rules inventory and choose an existing object",
        )
