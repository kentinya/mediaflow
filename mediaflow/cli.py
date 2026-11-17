from __future__ import annotations

import os
import re
import sys
from typing import TextIO

from mediaflow.application.strategy_test import StrategyTestResult


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """The installed ``mediaflow`` console entry point.

    The former standalone ``strategy-test`` argument parser, embedded smoke
    strategy and local execution runner are retired.  Every installed command
    is dispatched to the one current application CLI; the shared analysis
    engine remains reachable through ``analyze`` and the rules workspace.
    """

    from mediaflow.final_cli import final_main

    return final_main(list(sys.argv[1:] if argv is None else argv), stdout=stdout, stderr=stderr)


def render_strategy_result(result: StrategyTestResult) -> str:
    parsed, recognition, policy, metadata = (
        result.parsed,
        result.recognition,
        result.policy,
        result.metadata,
    )
    parser_evidence = [
        f"{item.field}={item.value} ({item.source.value})" for item in parsed.evidence
    ]
    recognition_evidence = [
        f"{item.field} {item.operator} {item.expected}" for item in recognition.evidence
    ]
    metadata_provider = result.metadata_policy.provider_id if result.metadata_policy else None
    query_type = result.metadata_policy.query_type.value if result.metadata_policy else None
    query_language = result.metadata_policy.language if result.metadata_policy else None
    query_region = result.metadata_policy.region if result.metadata_policy else None
    identity = metadata.identity if metadata else None
    match = metadata.match if metadata else None
    confidence = identity.confidence if identity else match.score if match else None
    naming_segments = list(result.naming.directory_segments) if result.naming else []
    naming_variables = dict(result.naming.rendered_variables) if result.naming else {}
    naming_changes = list(result.naming.sanitization_changes) if result.naming else []
    classification = result.classification
    plan = result.organize_plan
    execution = result.execution
    executed = bool(execution and execution.status.value != "DRY_RUN")
    mutation_text = "explicit execution mode" if executed else "0"
    resolved_execution_destination = execution.resolved_destination if execution else None
    lines = [
        "=" * 50,
        "Strategy Test",
        "=" * 50,
        "INPUT",
        f"Path: {result.path}",
        "",
        "-" * 50,
        "PARSER",
        "-" * 50,
        f"titleCandidate: {parsed.title_candidate}",
        f"year: {_value(parsed.year)}",
        f"season: {_value(parsed.season)}",
        f"episode: {_value(parsed.episode)}",
        f"episodes: {list(parsed.episodes)}",
        f"resolution: {_value(parsed.resolution_tag)}",
        f"source: {_value(parsed.source_tag)}",
        f"videoCodec: {_value(parsed.video_codec_tag)}",
        f"audio: {_value(parsed.audio_codec_tag)} {_value(parsed.audio_channels_tag)}",
        f"hdr: {list(parsed.hdr_tags)}",
        f"version: {list(parsed.version_tags)}",
        f"releaseGroup: {_value(parsed.release_group)}",
        f"Parser warnings: {[warning.code.value for warning in parsed.warnings]}",
        f"Parser evidence: {parser_evidence}",
        "",
        "-" * 50,
        "RECOGNITION",
        "-" * 50,
        f"Recognition status: {recognition.status.value}",
        f"RecognitionType: {_value(recognition.recognition_type_id)}",
        f"Matched rules: {[item.rule_id for item in recognition.matched_rules]}",
        f"Rule priorities: {[item.priority for item in recognition.matched_rules]}",
        f"Score: {recognition.score}",
        f"Evidence: {recognition_evidence}",
        f"Warnings: {list(recognition.warnings)}",
        "",
        "-" * 50,
        "RECOGNITION TYPE POLICY",
        "-" * 50,
        f"RecognitionType: {_value(policy.recognition_type_id if policy else None)}",
        f"MetadataPolicy: {_value(policy.metadata_policy_id if policy else None)}",
        f"NamingPolicy: {_value(policy.naming_policy_id if policy else None)}",
        f"ClassificationPolicy: {_value(policy.classification_policy_id if policy else None)}",
        f"OrganizePolicy: {_value(policy.organize_policy_id if policy else None)}",
        f"RecognitionType preserved: {'YES' if result.recognition_type_preserved else 'NO'}",
        "",
        "-" * 50,
        "METADATA",
        "-" * 50,
        f"Provider: {_value(metadata_provider)}",
        f"Query type: {_value(query_type)}",
        f"TMDB query language: {_value(query_language)}",
        f"TMDB query region: {_value(query_region)}",
        f"Query: {parsed.title_candidate}",
        f"Year: {_value(parsed.year)}",
        "Cache hit/miss: provider-managed / not exposed",
        "",
        "-" * 50,
        "CANDIDATES",
        "-" * 50,
    ]
    lines.extend(_render_candidates(match))
    lines.extend(
        [
            "",
            "-" * 50,
            "MATCH RESULT",
            "-" * 50,
            f"Status: {_value(metadata.status.value if metadata else 'offline')}",
            f"Confidence: {_value(confidence)}",
            f"Selected provider: {_value(identity.provider if identity else None)}",
            f"Selected provider ID: {_value(identity.provider_id if identity else None)}",
            f"Selected title: {_value(identity.title if identity else None)}",
            f"Selected year: {_value(identity.year if identity else None)}",
            f"Selected genres: {list(identity.genres) if identity else []}",
            f"Selected countries: {list(identity.countries) if identity else []}",
            "",
            "-" * 50,
            "NAMING PREVIEW",
            "-" * 50,
            f"RecognitionType: {_value(recognition.recognition_type_id)}",
            f"NamingPolicy: {_value(policy.naming_policy_id if policy else None)}",
            f"Status: {_naming_status(result)}",
            f"Directory segments: {naming_segments}",
            f"Filename: {_value(result.naming.filename if result.naming else None)}",
            f"Rendered variables: {naming_variables}",
            f"Sanitization changes: {naming_changes}",
            f"Warnings: {_naming_warnings(result)}",
            f"RecognitionType preserved: {'YES' if result.recognition_type_preserved else 'NO'}",
            "",
            "-" * 50,
            "CLASSIFICATION PREVIEW",
            "-" * 50,
            f"RecognitionType: {_value(recognition.recognition_type_id)}",
            f"ClassificationPolicy: {_value(policy.classification_policy_id if policy else None)}",
            f"Status: {_classification_status(result)}",
            f"Matched Rule: {_value(classification.matched_rule_id if classification else None)}",
            f"MediaLibrary: {_value(classification.media_library_id if classification else None)}",
            f"Path: {_value(classification.relative_path if classification else None)}",
            f"Category: {_value(classification.category if classification else None)}",
            f"Destination contract: {_destination_contract(classification)}",
            f"Confidence: {_value(classification.confidence if classification else None)}",
            f"Evidence: {list(classification.evidence) if classification else []}",
            f"Warnings: {_classification_warnings(result)}",
            f"RecognitionType preserved: {'YES' if result.recognition_type_preserved else 'NO'}",
            "",
            "-" * 50,
            "ORGANIZE PLAN",
            "-" * 50,
            f"Status: {_plan_status(result)}",
            f"Operation: {_value(plan.operation.value if plan else None)}",
            f"Source: {_value(plan.source if plan else result.path)}",
            f"Destination: {_value(plan.destination if plan else None)}",
            f"Conflicts: {_plan_conflicts(result)}",
            f"Execution: {'EXECUTED' if executed else 'NOT EXECUTED'}",
            f"Storage mutation: {mutation_text}",
            "",
            "-" * 50,
            "EXECUTION RESULT",
            "-" * 50,
            f"Mode: {'EXECUTE' if executed else 'DRY_RUN'}",
            f"Operation: {_value(execution.operation.value if execution else None)}",
            f"Status: {_value(execution.status.value if execution else None)}",
            f"Source: {_value(execution.source if execution else None)}",
            f"Destination: {_value(execution.destination if execution else None)}",
            f"Resolved destination: {_value(resolved_execution_destination)}",
            f"Created directories: {list(execution.created_directories) if execution else []}",
            f"Completed operations: {list(execution.completed_operations) if execution else []}",
            f"Warnings: {list(execution.warnings) if execution else []}",
            f"Errors: {list(execution.errors) if execution else []}",
            f"Duration: {_value(execution.duration if execution else None)}",
            "",
            "-" * 50,
            "SAFETY",
            "-" * 50,
            f"Classification execution calls: {1 if classification else 0}",
            f"OrganizerExecutor calls: {1 if execution else 0}",
            f"Organizer execution calls: {1 if executed else 0}",
            f"Storage mutations: {mutation_text}",
            "",
            "-" * 50,
            "FINAL",
            "-" * 50,
            f"RecognitionType: {_value(recognition.recognition_type_id)}",
            f"MediaIdentity: {_value(identity.title if identity else None)}",
            f"MetadataPolicy: {_value(policy.metadata_policy_id if policy else None)}",
            f"NamingPolicy: {_value(policy.naming_policy_id if policy else None)}",
            f"ClassificationPolicy: {_value(policy.classification_policy_id if policy else None)}",
            f"OrganizePolicy: {_value(policy.organize_policy_id if policy else None)}",
            f"Storage mutations: {mutation_text}",
            "=" * 50,
            "",
        ]
    )
    return "\n".join(lines)


def _render_candidates(match) -> list[str]:
    if match is None or not match.candidate_scores:
        return ["No candidate scores (offline or no results)."]
    lines = []
    for scored in match.candidate_scores:
        candidate = scored.candidate
        lines.extend(
            [
                f"Provider ID: {candidate.provider_id}",
                f"Title: {candidate.title}",
                f"Original title: {_value(candidate.original_title)}",
                f"Matched provider title: {_value(scored.matched_provider_title)}",
                f"Matched title source: {_value(scored.matched_title_source)}",
                f"Year: {_value(candidate.year)}",
                f"Canonical year: {_value(candidate.canonical_year)}",
                f"Regional year: {_value(candidate.regional_year)}",
                f"Total score: {scored.total_score}",
                "Score breakdown:",
                *[
                    f"- {component.name}: {component.score:.3f} — {component.reason}"
                    for component in scored.components
                ],
                f"Reasons / warnings: {list(match.reasons + match.warnings)}",
                "",
            ]
        )
    return lines


def _naming_status(result: StrategyTestResult) -> str:
    if not result.naming_requested:
        return "not requested"
    if result.naming_error:
        return f"error: {_redact(result.naming_error)}"
    if result.naming:
        return "warning" if result.naming.warnings else "ok"
    return "unavailable: MediaIdentity required"


def _naming_warnings(result: StrategyTestResult) -> list[str]:
    if result.naming:
        return list(result.naming.warnings)
    if result.naming_requested and not result.naming_error:
        return ["MediaIdentity unavailable; naming was not executed"]
    return []


def _classification_status(result: StrategyTestResult) -> str:
    if not result.classification_requested:
        return "not requested"
    if result.classification_error:
        return f"error: {_redact(result.classification_error)}"
    if result.classification:
        return result.classification.status.value
    return "unavailable: MediaIdentity required"


def _destination_contract(classification) -> str:
    """Name the destination contract this result actually resolves under.

    A legacy result still composes its original prefix; a revised result does
    not.  Reporting the fact avoids implying that a historical target and a
    newly published target are interchangeable.
    """

    if classification is None:
        return "unavailable"
    if classification.legacy_destination:
        return "LEGACY prefix + path"
    return "MediaLibrary root + path"


def _classification_warnings(result: StrategyTestResult) -> list[str]:
    if result.classification:
        return list(result.classification.warnings)
    if result.classification_requested and not result.classification_error:
        return ["MediaIdentity unavailable; classification was not executed"]
    return []


def _plan_status(result: StrategyTestResult) -> str:
    if not result.plan_requested:
        return "not requested"
    if result.plan_error:
        return f"error: {_redact(result.plan_error)}"
    if result.organize_plan:
        return result.organize_plan.status.value
    return "not generated (metadata, naming, or classification unavailable)"


def _plan_conflicts(result: StrategyTestResult) -> list[str]:
    if not result.organize_plan:
        return []
    return [
        f"{conflict.type.value}: {conflict.details}" for conflict in result.organize_plan.conflicts
    ]


def _value(value) -> str:
    return "-" if value is None else str(value)


def _redact(message: str) -> str:
    for name in ("TMDB_ACCESS_TOKEN", "TMDB_TOKEN"):
        if secret := os.environ.get(name):
            message = message.replace(secret, "***")
    return re.sub(r"(?i)(authorization\s*:\s*bearer\s+)\S+", r"\1***", message)


if __name__ == "__main__":
    raise SystemExit(main())
