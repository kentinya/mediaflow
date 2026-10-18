"""Build bounded, immutable pipeline evidence from existing transient results."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from mediaflow.domain.manual_safety import contains_manual_secret, redact_evidence_text
from mediaflow.domain.media_evidence import (
    EVIDENCE_SECTION_NAMES,
    EXECUTION_IDENTITY_BYTE_LIMIT,
    EXECUTION_IDENTITY_ITEM_LIMIT,
    EXECUTION_IDENTITY_SIZE_LIMIT_REASON,
    EXECUTION_IDENTITY_TEXT_LIMIT,
    EvidenceSection,
    PipelineEvidence,
)
from mediaflow.domain.organizer import (
    ExecutionResult,
    OrganizePlan,
    OrganizePolicy,
    PlanOperation,
)
from mediaflow.domain.recognition import RecognitionStatus

_MAX_TEXT = 4096
_MAX_ITEM_TEXT = 256
_MAX_ERROR = 1000
_MAX_ITEMS = 64
_MAX_SCORE_COMPONENTS = 16

PREVIEW_CONFLICT_NEXT_ACTION = (
    "this analysis-only finding is not execution authority; run the explicit real "
    "Organize journey under fresh one-shot authority and current-state revalidation "
    "when organization is desired"
)


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
    organize_policy: OrganizePolicy | None = None,
    conflict_finding: bool = False,
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
        "plan": _plan_section(
            plan,
            organize_policy=organize_policy,
            conflict_finding=conflict_finding,
        ),
        "operation": _operation_section(execution),
        "capabilities": _capability_section(plan, storages),
    }
    warnings = _collect_warnings(sections)
    truncated = any(section.truncated for section in sections.values())
    identity = (
        strategy.metadata.identity
        if strategy is not None and strategy.metadata is not None
        else None
    )
    execution_identity, identity_unavailable_reason = _execution_identity_document(identity)
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
        execution_identity=execution_identity,
        execution_identity_unavailable_reason=identity_unavailable_reason,
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
        "episodes": _bounded_numbers(identity.episodes if identity else ()),
        "episodeTitle": _bounded(identity.episode_title if identity else None, _MAX_ITEM_TEXT),
        "episodeMetadata": _bounded_episode_metadata(identity.episode_metadata if identity else ()),
        # The classification-relevant identity facets are persisted so a
        # completed re-analysis can be reused for a same-page summary without a
        # second Provider lookup while still classifying identically.
        "genres": _bounded_items(identity.genres if identity else ()),
        "countries": _bounded_items(identity.countries if identity else ()),
        "languages": _bounded_items(identity.languages if identity else ()),
        "keywords": _bounded_items(identity.keywords if identity else ()),
        "alternativeTitles": _bounded_items(identity.alternative_titles if identity else ()),
        "translatedTitles": _bounded_items(identity.translated_titles if identity else ()),
        "releaseDate": _bounded(identity.release_date if identity else None, _MAX_ITEM_TEXT),
        "canonicalReleaseDate": _bounded(
            identity.canonical_release_date if identity else None, _MAX_ITEM_TEXT
        ),
        "regionalReleaseDate": _bounded(
            identity.regional_release_date if identity else None, _MAX_ITEM_TEXT
        ),
        "externalIds": _bounded_external_ids(identity.external_ids if identity else ()),
        "posterPath": _bounded(identity.poster_path if identity else None, _MAX_ITEM_TEXT),
        "backdropPath": _bounded(identity.backdrop_path if identity else None, _MAX_ITEM_TEXT),
        "confidence": identity.confidence if identity else None,
        "matchedBy": _bounded(identity.matched_by if identity else None),
        "identityRecognitionTypeId": _bounded(identity.recognition_type_id if identity else None),
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
            _was_truncated(
                (
                    identity.episodes if identity else (),
                    identity.episode_metadata if identity else (),
                    identity.genres if identity else (),
                    identity.countries if identity else (),
                    identity.languages if identity else (),
                    identity.keywords if identity else (),
                    identity.alternative_titles if identity else (),
                    identity.translated_titles if identity else (),
                    identity.external_ids if identity else (),
                    match.candidate_scores if match else (),
                )
            )
            or any(
                len(getattr(score, "components", ())) > _MAX_SCORE_COMPONENTS
                for score in _bounded_tuple(match.candidate_scores if match else ())
            )
        ),
    )


class _ExecutionIdentityTooLarge(ValueError):
    """The normalized identity exceeded an explicit persistence size bound."""


def _execution_identity_document(identity: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Capture a bounded normalized identity separate from display evidence.

    Values outside this snapshot's explicit size/type limits are not clipped:
    they make the identity unavailable for deterministic plan reuse instead.
    This avoids treating a display projection as a complete provider identity.
    """

    if identity is None:
        return None, None

    def exact_text(value: Any, *, optional: bool = False) -> str | None:
        if value is None and optional:
            return None
        if not isinstance(value, str) or (not optional and not value):
            raise ValueError("identity text is missing")
        if len(value) > EXECUTION_IDENTITY_TEXT_LIMIT:
            raise _ExecutionIdentityTooLarge
        if contains_manual_secret(value):
            raise ValueError("identity text is outside the safe persistence bound")
        return value

    def exact_texts(values: Any) -> list[str]:
        if not isinstance(values, (list, tuple)):
            raise ValueError("identity list is outside the safe persistence bound")
        if len(values) > EXECUTION_IDENTITY_ITEM_LIMIT:
            raise _ExecutionIdentityTooLarge
        result = []
        for value in values:
            normalized = exact_text(value)
            assert normalized is not None
            result.append(normalized)
        return result

    try:
        external_ids = []
        if not isinstance(identity.external_ids, (list, tuple)):
            return None, None
        if len(identity.external_ids) > EXECUTION_IDENTITY_ITEM_LIMIT:
            raise _ExecutionIdentityTooLarge
        for provider, provider_id in identity.external_ids:
            external_ids.append(
                {
                    "provider": exact_text(provider),
                    "providerId": exact_text(provider_id),
                }
            )

        episodes = list(identity.episodes)
        if len(episodes) > EXECUTION_IDENTITY_ITEM_LIMIT:
            raise _ExecutionIdentityTooLarge
        if any(not isinstance(value, int) or isinstance(value, bool) for value in episodes):
            return None, None

        episode_metadata = []
        if not isinstance(identity.episode_metadata, (list, tuple)):
            return None, None
        if len(identity.episode_metadata) > EXECUTION_IDENTITY_ITEM_LIMIT:
            raise _ExecutionIdentityTooLarge
        for episode in identity.episode_metadata:
            if not isinstance(episode.episode, int) or isinstance(episode.episode, bool):
                return None, None
            episode_metadata.append(
                {
                    "episode": episode.episode,
                    "title": exact_text(episode.title),
                    "airDate": exact_text(episode.air_date, optional=True),
                    "overview": exact_text(episode.overview, optional=True),
                }
            )

        confidence = identity.confidence
        if confidence is not None and (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not math.isfinite(confidence)
        ):
            return None, None
        document = {
            "version": 1,
            "provider": exact_text(identity.provider),
            "providerId": exact_text(identity.provider_id),
            "mediaType": exact_text(identity.media_type.value),
            "title": exact_text(identity.title),
            "originalTitle": exact_text(identity.original_title, optional=True),
            "year": identity.year,
            "season": identity.season,
            "episode": identity.episode,
            "episodes": episodes,
            "episodeTitle": exact_text(identity.episode_title, optional=True),
            "episodeMetadata": episode_metadata,
            "genres": exact_texts(identity.genres),
            "countries": exact_texts(identity.countries),
            "languages": exact_texts(identity.languages),
            "keywords": exact_texts(identity.keywords),
            "alternativeTitles": exact_texts(identity.alternative_titles),
            "translatedTitles": exact_texts(identity.translated_titles),
            "releaseDate": exact_text(identity.release_date, optional=True),
            "canonicalReleaseDate": exact_text(identity.canonical_release_date, optional=True),
            "regionalReleaseDate": exact_text(identity.regional_release_date, optional=True),
            "overview": exact_text(identity.overview, optional=True),
            "externalIds": external_ids,
            "posterPath": exact_text(identity.poster_path, optional=True),
            "backdropPath": exact_text(identity.backdrop_path, optional=True),
            "confidence": confidence,
            "matchedBy": exact_text(identity.matched_by, optional=True),
            "recognitionTypeId": exact_text(identity.recognition_type_id, optional=True),
        }
        encoded = json.dumps(
            document, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        if len(encoded) > EXECUTION_IDENTITY_BYTE_LIMIT:
            return None, EXECUTION_IDENTITY_SIZE_LIMIT_REASON
        # The standard evidence redactor must leave this execution snapshot
        # byte-for-byte intact or it is not safe to reuse.
        if redact_evidence_text(encoded.decode("utf-8")) != encoded.decode("utf-8"):
            return None, None
        return document, None
    except _ExecutionIdentityTooLarge:
        return None, EXECUTION_IDENTITY_SIZE_LIMIT_REASON
    except (AttributeError, TypeError, ValueError):
        return None, None


def _bounded_episode_metadata(values: Any) -> list[dict[str, Any]]:
    if values is None:
        return []
    return [
        {
            "episode": getattr(item, "episode", None),
            "title": _bounded(getattr(item, "title", None), _MAX_ITEM_TEXT),
            "airDate": _bounded(getattr(item, "air_date", None), _MAX_ITEM_TEXT),
            "overview": _bounded(getattr(item, "overview", None), _MAX_TEXT),
        }
        for item in list(values)[:_MAX_ITEMS]
    ]


def _bounded_external_ids(values: Any) -> list[dict[str, str]]:
    if values is None:
        return []
    result = []
    for item in list(values)[:_MAX_ITEMS]:
        try:
            provider, provider_id = item
        except (TypeError, ValueError):
            continue
        if isinstance(provider, str) and isinstance(provider_id, str):
            result.append(
                {
                    "provider": _bounded(provider, 128) or "",
                    "providerId": _bounded(provider_id, _MAX_ITEM_TEXT) or "",
                }
            )
    return result


def _bounded_numbers(values: Any, limit: int = _MAX_ITEMS) -> list[int]:
    if values is None:
        return []
    return [
        item
        for item in list(values)[:limit]
        if isinstance(item, int) and not isinstance(item, bool)
    ]


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
            "destinationContract": (
                "legacy_library_prefix"
                if classification.legacy_destination
                else "media_library_path"
            ),
            "confidence": classification.confidence,
            "matchEvidence": _bounded_items(classification.evidence),
        },
        warnings=tuple(
            _bounded(item, _MAX_ITEM_TEXT) for item in _bounded_tuple(classification.warnings)
        ),
        truncated=_was_truncated((classification.evidence, classification.warnings)),
    )


def _plan_section(
    plan: OrganizePlan | None,
    *,
    organize_policy: OrganizePolicy | None = None,
    conflict_finding: bool = False,
) -> EvidenceSection:
    if plan is None:
        return EvidenceSection(
            False,
            unavailable_reason="organize plan was not reached",
        )
    duplicate = plan.duplicate_comparison
    if organize_policy is not None:
        policy_value = {
            "policyId": _bounded(organize_policy.policy_id),
            "configuredConflictStrategy": _bounded(organize_policy.conflict_strategy.value),
        }
    else:
        policy_value = None
    next_action = PREVIEW_CONFLICT_NEXT_ACTION if conflict_finding and plan.conflicts else None
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
        "configuredPolicy": policy_value,
        "nextAction": next_action,
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
    return redact_evidence_text(value, limit=limit)


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
    return redact_evidence_text(error, limit=_MAX_ERROR)
