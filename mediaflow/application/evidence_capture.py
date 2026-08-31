"""Build bounded, immutable pipeline evidence from existing transient results."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from mediaflow.domain.media_evidence import (
    EVIDENCE_SECTION_NAMES,
    EvidenceSection,
    PipelineEvidence,
)
from mediaflow.domain.organizer import (
    ExecutionResult,
    OrganizePlan,
    PlanOperation,
)
from mediaflow.domain.recognition import RecognitionStatus

_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|password|passwd|secret|token|authorization|cookie)"
    r"(\s*[=:]\s*)[^\s,;\"']+"
)
_MAX_TEXT = 4096
_MAX_ITEM_TEXT = 256
_MAX_ERROR = 1000
_MAX_ITEMS = 64
_MAX_SCORE_COMPONENTS = 16


def build_pipeline_evidence(
    task,
    item,
    *,
    strategy=None,
    plan: OrganizePlan | None = None,
    execution: ExecutionResult | None = None,
    error: str | Exception | None = None,
    outcome: str | None = None,
    storages: Mapping[str, Any] | None = None,
    captured_at: datetime | None = None,
) -> PipelineEvidence:
    """Capture one immutable evidence record for a TaskItem attempt.

    The builder is intentionally read-only: it inspects only in-memory results,
    the pinned Task identity, and declared Storage capability properties.  It never
    calls Storage, constructs Providers, or performs any mutation.
    """

    timestamp = captured_at or datetime.now(UTC)
    evidence_id = f"{item.item_id}:{item.attempts}"
    if outcome is None:
        outcome = _default_outcome(strategy, plan, execution, error)
    sections = {
        "parse": _parse_section(strategy),
        "recognition": _recognition_section(strategy),
        "metadata": _metadata_section(strategy),
        "policies": _policies_section(strategy),
        "naming": _naming_section(strategy),
        "classification": _classification_section(strategy),
        "plan": _plan_section(plan),
        "operation": _operation_section(execution),
        "capabilities": _capability_section(plan, storages),
    }
    warnings = _collect_warnings(sections)
    truncated = any(section.truncated for section in sections.values())
    return PipelineEvidence(
        evidence_id=evidence_id,
        task_id=task.task_id,
        item_id=item.item_id,
        attempts=item.attempts,
        source_storage_id=item.storage_id,
        source_path=item.source_path,
        captured_at=timestamp,
        configuration_snapshot_id=getattr(task, "configuration_snapshot_id", None),
        configuration_snapshot_digest=getattr(task, "configuration_snapshot_digest", None),
        outcome=outcome,
        sections=sections,
        warnings=warnings,
        error=_safe_error(error),
        truncated=truncated,
    )


def _default_outcome(strategy, plan, execution, error) -> str:
    if execution is not None:
        return execution.status.value.lower()
    if error:
        return "failed"
    if plan is not None and (plan.conflicts or plan.status.value in {"conflict", "invalid"}):
        return "waiting_confirm"
    if strategy is not None:
        if strategy.recognition.status is RecognitionStatus.UNRECOGNIZED:
            return "waiting_recognition"
        metadata = strategy.metadata
        if metadata is not None:
            if metadata.status.value in {"need_confirm", "ambiguous"}:
                return "waiting_metadata"
            if metadata.status.value == "not_found":
                return "waiting_metadata_correction"
        if (
            strategy.classification is not None
            and strategy.classification.status.value == "unclassified"
        ):
            return "waiting_classification"
        if plan is not None and plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}:
            return "skipped"
    return "processing"


def _parse_section(strategy) -> EvidenceSection:
    if strategy is None:
        return _legacy_section()
    parsed = strategy.parsed
    value = {
        "titleCandidate": _bounded(parsed.title_candidate),
        "year": parsed.year,
        "season": parsed.season,
        "episode": parsed.episode,
        "episodes": _bounded_items(parsed.episodes),
        "resolutionTag": _bounded(parsed.resolution_tag),
        "sourceTag": _bounded(parsed.source_tag),
        "videoCodecTag": _bounded(parsed.video_codec_tag),
        "audioTag": _bounded(parsed.audio_tag),
        "hdrTag": _bounded(parsed.hdr_tag),
        "versionTag": _bounded(parsed.version_tag),
        "releaseGroup": _bounded(parsed.release_group),
        "extension": _bounded(parsed.extension),
        "nfoMediaType": (
            _bounded(parsed.nfo_media_type.value) if parsed.nfo_media_type is not None else None
        ),
        "nfoPath": _bounded(parsed.nfo_path, _MAX_ITEM_TEXT),
        "languageTags": _bounded_items(parsed.language_tags),
    }
    items = [
        {
            "field": _bounded(evidence.field),
            "value": _bounded(evidence.value, _MAX_ITEM_TEXT),
            "source": _bounded(evidence.source.value),
            "confidence": _bounded(evidence.confidence.value),
        }
        for evidence in _bounded_tuple(parsed.evidence)
    ]
    warnings = [
        f"{_bounded(warning.code.value, 128)}: {_bounded(warning.message, _MAX_ITEM_TEXT)}"
        for warning in _bounded_tuple(parsed.warnings)
    ]
    return EvidenceSection(
        True,
        value,
        tuple(items),
        tuple(warnings),
        truncated=_was_truncated((parsed.evidence, parsed.warnings)),
    )


def _recognition_section(strategy) -> EvidenceSection:
    if strategy is None:
        return _legacy_section()
    recognition = strategy.recognition
    value = {
        "status": _bounded(recognition.status.value),
        "recognitionTypeId": _bounded(recognition.recognition_type_id),
        "ruleId": _bounded(recognition.rule_id),
        "confidence": recognition.confidence,
        "score": recognition.score,
        "matchedRules": [
            {
                "ruleId": _bounded(rule.rule_id),
                "recognitionTypeId": _bounded(rule.recognition_type_id),
                "priority": rule.priority,
                "score": rule.score,
            }
            for rule in _bounded_tuple(recognition.matched_rules)
        ],
        "alternatives": [
            {
                "recognitionTypeId": _bounded(item.recognition_type_id),
                "score": item.score,
                "priority": item.priority,
            }
            for item in _bounded_tuple(recognition.alternatives)
        ],
    }
    items = [
        {
            "ruleId": _bounded(item.rule_id),
            "field": _bounded(item.field),
            "operator": _bounded(item.operator),
            "expected": _bounded(item.expected, _MAX_ITEM_TEXT),
            "actual": _bounded(item.actual, _MAX_ITEM_TEXT),
        }
        for item in _bounded_tuple(recognition.evidence)
    ]
    reasons = [
        f"{_bounded(reason.code, 128)}: {_bounded(reason.message, _MAX_ITEM_TEXT)}"
        for reason in _bounded_tuple(recognition.reasons)
    ]
    warnings = tuple(
        _bounded(item, _MAX_ITEM_TEXT) for item in _bounded_tuple(recognition.warnings)
    )
    truncated = _was_truncated(
        (
            recognition.matched_rules,
            recognition.alternatives,
            recognition.evidence,
            recognition.reasons,
            recognition.warnings,
        )
    )
    return EvidenceSection(
        True,
        value,
        tuple(items),
        tuple(reasons) + warnings,
        truncated,
    )


def _metadata_section(strategy) -> EvidenceSection:
    if strategy is None:
        return _legacy_section()
    metadata = strategy.metadata
    if metadata is None:
        return EvidenceSection(
            False,
            {"recognitionTypeId": _bounded(strategy.recognition.recognition_type_id)},
            unavailable_reason="metadata stage was not reached",
        )
    identity = metadata.identity
    match = metadata.match
    value = {
        "status": _bounded(metadata.status.value),
        "recognitionTypeId": _bounded(metadata.recognition_type_id),
        "query": _bounded(metadata.query, _MAX_ITEM_TEXT),
        "provider": _bounded(identity.provider if identity else None),
        "providerId": _bounded(identity.provider_id if identity else None),
        "mediaType": _bounded(identity.media_type.value if identity else None),
        "title": _bounded(identity.title if identity else None, _MAX_ITEM_TEXT),
        "originalTitle": _bounded(identity.original_title if identity else None, _MAX_ITEM_TEXT),
        "year": identity.year if identity else None,
        "season": identity.season if identity else None,
        "episode": identity.episode if identity else None,
        "episodes": _bounded_items(identity.episodes if identity else ()),
        "confidence": identity.confidence if identity else None,
        "matchedBy": _bounded(identity.matched_by if identity else None),
        "matchStatus": _bounded(match.status.value) if match else None,
        "matchReasons": _bounded_items(match.reasons if match else ()),
        "matchWarnings": _bounded_items(match.warnings if match else ()),
        "candidateCount": len(match.candidate_scores) if match else 0,
    }
    items: list[dict[str, Any]] = []
    if match is not None:
        best = match.best_candidate
        if best is not None:
            best_score = next(
                (
                    score
                    for score in _bounded_tuple(match.candidate_scores)
                    if score.candidate.provider == best.provider
                    and score.candidate.provider_id == best.provider_id
                ),
                None,
            )
            value["bestCandidate"] = {
                "provider": _bounded(best.provider),
                "providerId": _bounded(best.provider_id),
                "mediaType": _bounded(best.media_type.value),
                "title": _bounded(best.title, _MAX_ITEM_TEXT),
                "originalTitle": _bounded(best.original_title, _MAX_ITEM_TEXT),
                "year": best.year,
                "score": best.score,
                "matchedLocalTitle": _bounded(
                    getattr(best_score, "matched_local_title", None), _MAX_ITEM_TEXT
                ),
                "matchedProviderTitle": _bounded(
                    getattr(best_score, "matched_provider_title", None), _MAX_ITEM_TEXT
                ),
                "matchedTitleSource": _bounded(
                    getattr(best_score, "matched_title_source", None), 128
                ),
            }
        for score in _bounded_tuple(match.candidate_scores):
            candidate = score.candidate
            components = [
                {
                    "name": _bounded(component.name, 128),
                    "score": component.score,
                    "reason": _bounded(component.reason, _MAX_ITEM_TEXT),
                }
                for component in _bounded_tuple(getattr(score, "components", ()))[
                    :_MAX_SCORE_COMPONENTS
                ]
            ]
            items.append(
                {
                    "provider": _bounded(candidate.provider),
                    "providerId": _bounded(candidate.provider_id),
                    "mediaType": _bounded(candidate.media_type.value),
                    "title": _bounded(candidate.title, _MAX_ITEM_TEXT),
                    "originalTitle": _bounded(candidate.original_title, _MAX_ITEM_TEXT),
                    "year": candidate.year,
                    "score": score.total_score,
                    "exactTitle": score.exact_title,
                    "exactYear": score.exact_year,
                    "matchedLocalTitle": _bounded(
                        getattr(score, "matched_local_title", None), _MAX_ITEM_TEXT
                    ),
                    "matchedProviderTitle": _bounded(
                        getattr(score, "matched_provider_title", None), _MAX_ITEM_TEXT
                    ),
                    "matchedTitleSource": _bounded(
                        getattr(score, "matched_title_source", None), 128
                    ),
                    "scoreComponents": components,
                }
            )
    return EvidenceSection(
        True,
        value,
        tuple(items),
        tuple(_bounded(item, _MAX_ITEM_TEXT) for item in _bounded_tuple(value["matchReasons"])),
        truncated=(
            _was_truncated((match.candidate_scores if match else (),))
            or any(
                len(getattr(score, "components", ())) > _MAX_SCORE_COMPONENTS
                for score in _bounded_tuple(match.candidate_scores if match else ())
            )
        ),
    )


def _policies_section(strategy) -> EvidenceSection:
    if strategy is None:
        return _legacy_section()
    policy = strategy.policy
    if policy is None:
        return EvidenceSection(
            False,
            unavailable_reason="RecognitionTypePolicy was not resolved",
        )
    return EvidenceSection(
        True,
        {
            "recognitionTypeId": _bounded(policy.recognition_type_id),
            "recognitionTypePolicyId": _bounded(policy.type_policy_id),
            "metadataPolicyId": _bounded(policy.metadata_policy_id),
            "namingPolicyId": _bounded(policy.naming_policy_id),
            "classificationPolicyId": _bounded(policy.classification_policy_id),
            "organizePolicyId": _bounded(policy.organize_policy_id),
        },
    )


def _naming_section(strategy) -> EvidenceSection:
    if strategy is None:
        return _legacy_section()
    naming = strategy.naming
    if naming is None:
        reason = strategy.naming_error or "naming stage was not reached"
        return EvidenceSection(False, unavailable_reason=_bounded(reason, _MAX_ITEM_TEXT))
    return EvidenceSection(
        True,
        {
            "policyId": _bounded(naming.policy_id),
            "recognitionTypeId": _bounded(naming.recognition_type_id),
            "mediaType": _bounded(naming.media_type.value) if naming.media_type else None,
            "directory": _bounded(naming.directory, _MAX_ITEM_TEXT),
            "filename": _bounded(naming.filename, _MAX_ITEM_TEXT),
            "directorySegments": _bounded_items(naming.directory_segments),
            "sanitizationChanges": _bounded_items(naming.sanitization_changes),
            "renderedVariables": [
                [_bounded(key, 128), _bounded(value, _MAX_ITEM_TEXT)]
                for key, value in _bounded_tuple(naming.rendered_variables)
            ],
        },
        warnings=tuple(_bounded(item, _MAX_ITEM_TEXT) for item in _bounded_tuple(naming.warnings)),
        truncated=_was_truncated(
            (
                naming.directory_segments,
                naming.sanitization_changes,
                naming.rendered_variables,
                naming.warnings,
            )
        ),
    )


def _classification_section(strategy) -> EvidenceSection:
    if strategy is None:
        return _legacy_section()
    classification = strategy.classification
    if classification is None:
        reason = strategy.classification_error or "classification stage was not reached"
        return EvidenceSection(False, unavailable_reason=_bounded(reason, _MAX_ITEM_TEXT))
    return EvidenceSection(
        True,
        {
            "policyId": _bounded(classification.policy_id),
            "recognitionTypeId": _bounded(classification.recognition_type_id),
            "status": _bounded(classification.status.value),
            "mediaLibraryId": _bounded(classification.media_library_id),
            "relativePath": _bounded(classification.relative_path, _MAX_ITEM_TEXT),
            "matchedRuleId": _bounded(classification.matched_rule_id),
            "matchedRuleName": _bounded(classification.matched_rule_name, _MAX_ITEM_TEXT),
            "library": _bounded(classification.library),
            "category": _bounded(classification.category),
            "subcategory": _bounded(classification.subcategory),
            "confidence": classification.confidence,
            "matchEvidence": _bounded_items(classification.evidence),
        },
        warnings=tuple(
            _bounded(item, _MAX_ITEM_TEXT) for item in _bounded_tuple(classification.warnings)
        ),
        truncated=_was_truncated((classification.evidence, classification.warnings)),
    )


def _plan_section(plan: OrganizePlan | None) -> EvidenceSection:
    if plan is None:
        return EvidenceSection(
            False,
            unavailable_reason="organize plan was not reached",
        )
    duplicate = plan.duplicate_comparison
    value: dict[str, Any] = {
        "planId": _bounded(plan.plan_id),
        "sourceStorageId": _bounded(plan.source_storage_id),
        "targetStorageId": _bounded(plan.target_storage_id),
        "target": _bounded(plan.target, _MAX_ITEM_TEXT),
        "relativeDestination": _bounded(plan.relative_destination, _MAX_ITEM_TEXT),
        "operation": _bounded(plan.operation.value),
        "status": _bounded(plan.status.value),
        "mediaLibraryRoot": _bounded(plan.media_library_root, _MAX_ITEM_TEXT),
        "overwriteAuthorized": plan.overwrite_authorized,
        "warnings": _bounded_items(plan.warnings),
        "conflicts": [
            {
                "type": _bounded(conflict.type.value),
                "source": _bounded(conflict.source, _MAX_ITEM_TEXT),
                "destination": _bounded(conflict.destination, _MAX_ITEM_TEXT),
                "details": _bounded(conflict.details, _MAX_ITEM_TEXT),
            }
            for conflict in _bounded_tuple(plan.conflicts)
        ],
        "attachments": [
            {
                "type": _bounded(attachment.attachment_type.value),
                "operation": _bounded(attachment.operation.value),
                "suffix": _bounded(attachment.suffix, 128),
            }
            for attachment in _bounded_tuple(plan.attachment_plans)
        ],
        "duplicateDetection": (
            {
                "status": _bounded(duplicate.status.value),
                "mode": _bounded(duplicate.mode.value),
                "reason": _bounded(duplicate.reason, _MAX_ITEM_TEXT),
            }
            if duplicate is not None
            else None
        ),
    }
    return EvidenceSection(
        True,
        value,
        tuple(value["conflicts"]) + tuple(value["attachments"]),
        warnings=tuple(_bounded(item, _MAX_ITEM_TEXT) for item in _bounded_tuple(plan.warnings)),
        truncated=_was_truncated((plan.conflicts, plan.attachment_plans, plan.warnings)),
    )


def _operation_section(execution: ExecutionResult | None) -> EvidenceSection:
    if execution is None:
        return EvidenceSection(
            False,
            unavailable_reason="no executor operation was produced",
        )
    return EvidenceSection(
        True,
        {
            "status": _bounded(execution.status.value),
            "operation": _bounded(execution.operation.value),
            "destination": _bounded(
                execution.resolved_destination or execution.destination, _MAX_ITEM_TEXT
            ),
            "planId": _bounded(execution.plan_id),
            "createdDirectories": _bounded_items(execution.created_directories),
            "completedOperations": _bounded_items(execution.completed_operations),
            "effectCertainty": _bounded(execution.effect_certainty.value),
            "uncertainEffects": _bounded_items(execution.uncertain_effects),
            "cleanupStatus": _bounded(execution.cleanup_status.value),
            "rollbackStatus": _bounded(execution.rollback_status.value),
            "errors": _bounded_items(execution.errors),
        },
        warnings=tuple(
            _bounded(item, _MAX_ITEM_TEXT) for item in _bounded_tuple(execution.warnings)
        ),
        truncated=_was_truncated(
            (
                execution.created_directories,
                execution.completed_operations,
                execution.uncertain_effects,
                execution.errors,
                execution.warnings,
            )
        ),
    )


def _capability_section(
    plan: OrganizePlan | None, storages: Mapping[str, Any] | None
) -> EvidenceSection:
    if plan is None or storages is None:
        return EvidenceSection(
            False,
            {
                "required": [],
                "declared": [],
                "missing": [],
                "verdict": "not_determined",
                "operation": _bounded(plan.operation.value) if plan else None,
            },
            unavailable_reason=(
                "capability verdict was not captured"
                if plan is None
                else "declared Storage capabilities were not supplied"
            ),
        )
    required = _required_capabilities(plan)
    declared: list[str] = []
    source = storages.get(plan.source_storage_id)
    target = storages.get(plan.target_storage_id)
    for capability in required:
        storage = source if capability == "can_delete" else target
        if storage is not None and getattr(storage.capabilities, capability, False):
            declared.append(capability)
    missing = [capability for capability in required if capability not in declared]
    verdict = "capability_gap" if missing else "ok" if required else "not_applicable"
    return EvidenceSection(
        True,
        {
            "required": required,
            "declared": declared,
            "missing": missing,
            "verdict": verdict,
            "operation": _bounded(plan.operation.value),
            "sourceStorageId": _bounded(plan.source_storage_id),
            "targetStorageId": _bounded(plan.target_storage_id),
        },
    )


def _required_capabilities(plan: OrganizePlan) -> list[str]:
    operation = plan.operation
    if operation in {PlanOperation.NOOP, PlanOperation.SKIP}:
        return []
    if operation is PlanOperation.MOVE:
        if plan.source_storage_id == plan.target_storage_id:
            return ["can_move"]
        return ["can_copy", "can_delete"]
    if operation is PlanOperation.COPY:
        return ["can_copy"]
    if operation is PlanOperation.LINK:
        if plan.source_storage_id != plan.target_storage_id:
            return []
        if getattr(plan, "link_operation", None) is not None:
            return [
                "can_soft_link" if plan.link_operation.value == "soft_link" else "can_hard_link"
            ]
        return ["can_hard_link"]
    return []


def _legacy_section(reason: str = "legacy evidence was not captured") -> EvidenceSection:
    return EvidenceSection(False, unavailable_reason=reason)


def _collect_warnings(sections: Mapping[str, EvidenceSection]) -> tuple[str, ...]:
    warnings: list[str] = []
    for name in EVIDENCE_SECTION_NAMES:
        section = sections.get(name)
        if section is None:
            continue
        if not section.available:
            warnings.append(f"{name}: {section.unavailable_reason or 'unavailable'}")
        if section.truncated:
            warnings.append(f"{name}: evidence truncated")
        warnings.extend(section.warnings)
    return tuple(warnings[:_MAX_ITEMS])


def _bounded(value: Any, limit: int = _MAX_TEXT) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:limit]


def _bounded_items(values: Any, limit: int = _MAX_ITEMS) -> list[str]:
    if values is None:
        return []
    return [_bounded(item, _MAX_ITEM_TEXT) or "" for item in list(values)[:limit]]


def _bounded_tuple(values: Any) -> tuple[Any, ...]:
    return tuple(list(values)[:_MAX_ITEMS])


def _was_truncated(values: Any) -> bool:
    return any(len(tuple(value)) > _MAX_ITEMS for value in values if value is not None)


def _safe_error(error: str | Exception | None) -> str | None:
    if error is None:
        return None
    text = str(error)[:_MAX_ERROR]
    text = _SECRET_PATTERN.sub(r"\1\2[redacted]", text)
    return text
