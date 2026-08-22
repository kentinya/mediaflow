from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import (
    CaseRunSummary,
    DirectoryStrategySummary,
    ReadOnlyStrategyStorage,
    StrategyConfigurationError,
    StrategyDirectoryRunner,
    StrategyTestResult,
    StrategyTestRunner,
    strategy_runner_from_configuration,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.strategy_configuration import (
    development_strategy_configuration,
    smoke_strategy_configuration,
)
from mediaflow.infrastructure.strategy_user_configuration import (
    LoadedStrategyConfiguration,
    ResourceLibraryBinding,
    load_strategy_configuration,
)
from mediaflow.infrastructure.tmdb import TMDBClient, TMDBConfig, TMDBProvider


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    runner_factory: Callable[[bool], StrategyTestRunner] | None = None,
) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    production_commands = {
        "analyze",
        "scan",
        "preview",
        "organize",
        "config",
        "tasks",
        "confirmations",
        "storage",
        "jobs",
        "worker",
        "api",
        "scheduler",
        "notifications",
        "notification-worker",
        "execution-authorizations",
        "security-audit",
        "dashboard",
    }
    if Path(sys.argv[0]).name == "mediaflow" or production_commands.intersection(effective_argv):
        from mediaflow.final_cli import final_main

        return final_main(effective_argv, stdout=stdout, stderr=stderr)
    parser = argparse.ArgumentParser(
        prog="strategy-test", description="Inspect MediaFlow strategy decisions"
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--offline", action="store_true", help="run parser, recognition, and policy resolution only"
    )
    modes.add_argument(
        "--live-metadata", action="store_true", help="also query the configured TMDB provider"
    )
    modes.add_argument("--cases", metavar="FILE", help="run a JSON strategy regression case file")
    parser.add_argument("--directory", metavar="PATH", help="scan a local directory read-only")
    parser.add_argument(
        "--show-naming", action="store_true", help="preview configured naming after metadata"
    )
    parser.add_argument(
        "--show-classification",
        action="store_true",
        help="preview configured classification after metadata",
    )
    parser.add_argument(
        "--show-plan", action="store_true", help="preview an OrganizePlan without execution"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="explicitly execute the generated plan (single local file only)",
    )
    parser.add_argument(
        "--execution-root",
        metavar="PATH",
        help="existing local destination Storage root required by --execute",
    )
    parser.add_argument("--config", metavar="FILE", help="user strategy configuration JSON file")
    parser.add_argument(
        "--resource-library-id",
        "--resource-library",
        dest="resource_library_id",
        metavar="ID",
        help="ResourceLibrary ID for a single path or an explicit directory override",
    )
    parser.add_argument(
        "--limit", type=int, help="maximum media files to inspect in directory mode"
    )
    parser.add_argument(
        "path", nargs="?", help="synthetic or real media path; the file need not exist"
    )
    arguments = parser.parse_args(effective_argv)
    if not arguments.cases and not arguments.path and not arguments.directory:
        parser.error("a path, --directory PATH, or --cases FILE is required")
    if arguments.directory and (arguments.path or arguments.cases):
        parser.error("--directory cannot be combined with a path or --cases")
    if arguments.limit is not None and not arguments.directory:
        parser.error("--limit requires --directory")
    if arguments.limit is not None and arguments.limit < 1:
        parser.error("--limit must be positive")
    if arguments.execute and not arguments.show_plan:
        parser.error("--execute requires --show-plan")
    if arguments.execute and (arguments.directory or arguments.cases):
        parser.error("--execute currently supports one explicit file only")
    if arguments.execution_root and not arguments.show_plan:
        parser.error("--execution-root requires --show-plan")
    try:
        configured_path = arguments.config or os.environ.get("MEDIAFLOW_STRATEGY_CONFIG")
        loaded = None
        if runner_factory:
            factory = runner_factory
        else:
            loaded = _load_cli_configuration(configured_path, cases=bool(arguments.cases))

            def factory(live: bool) -> StrategyTestRunner:
                return _runner_for_configuration(loaded.strategy, live)

        if arguments.cases:
            document = json.loads(Path(arguments.cases).read_text(encoding="utf-8"))
            summary = factory(False).run_cases(document, show_naming=arguments.show_naming)
            stdout.write(render_case_summary(summary))
            return 0 if summary.failed == 0 else 1
        if arguments.directory:
            summary = _run_directory(
                arguments.directory,
                factory(arguments.live_metadata),
                live_metadata=arguments.live_metadata,
                limit=arguments.limit,
                show_naming=arguments.show_naming,
                show_classification=arguments.show_classification,
                show_plan=arguments.show_plan,
                resource_library_id=_resolve_resource_library_id(
                    arguments.directory,
                    arguments.resource_library_id,
                    loaded.resource_libraries if loaded else (),
                    fallback="strategy-directory",
                ),
            )
            stdout.write(render_directory_summary(summary))
            return 0 if summary.errors == 0 else 1
        result = factory(arguments.live_metadata).run_path(
            arguments.path,
            live_metadata=arguments.live_metadata,
            show_naming=arguments.show_naming,
            show_classification=arguments.show_classification,
            show_plan=arguments.show_plan,
            resource_library_id=_resolve_resource_library_id(
                arguments.path,
                arguments.resource_library_id,
                loaded.resource_libraries if loaded else (),
                fallback="strategy-test",
            ),
        )
        execution_root = arguments.execution_root or os.environ.get("MEDIAFLOW_EXECUTION_ROOT")
        if arguments.execute or (arguments.show_plan and execution_root):
            result = _execute_local_result(
                result,
                arguments.path,
                execution_root,
                loaded.resource_libraries if loaded else (),
                execute=arguments.execute,
            )
        stdout.write(render_strategy_result(result))
        execution_failed = bool(
            result.execution and result.execution.status.value in {"FAILED", "PARTIAL"}
        )
        return (
            1
            if result.naming_error
            or result.classification_error
            or result.plan_error
            or execution_failed
            else 0
        )
    except StrategyConfigurationError as error:
        stderr.write(f"ConfigurationError: {_redact(str(error))}\n")
        return 2
    except (OSError, ValueError, RuntimeError, LookupError) as error:
        stderr.write(f"strategy-test error: {_redact(str(error))}\n")
        return 2


def _load_cli_configuration(path: str | None, *, cases: bool) -> LoadedStrategyConfiguration:
    base = development_strategy_configuration(
        language=os.environ.get("TMDB_LANGUAGE"), region=os.environ.get("TMDB_REGION")
    )
    if path:
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            return load_strategy_configuration(document, base=base)
        except (OSError, ValueError) as error:
            raise StrategyConfigurationError(
                f"cannot load strategy configuration {path!r}: {error}"
            ) from error
    if cases:
        return LoadedStrategyConfiguration(smoke_strategy_configuration(), ())
    return LoadedStrategyConfiguration(base, ())


def _runner_for_configuration(configuration, live: bool) -> StrategyTestRunner:
    if not live:
        return strategy_runner_from_configuration(configuration)
    token = os.environ.get("TMDB_ACCESS_TOKEN") or os.environ.get("TMDB_TOKEN")
    if not token:
        raise RuntimeError("live metadata requires TMDB_ACCESS_TOKEN")
    provider = TMDBProvider(TMDBClient(TMDBConfig(token)))
    return strategy_runner_from_configuration(configuration, MetadataProviderRegistry((provider,)))


def _configured_runner(live: bool) -> StrategyTestRunner:
    """Backward-compatible developer runner used by existing callers."""
    return _runner_for_configuration(development_strategy_configuration(), live)


def _resolve_resource_library_id(
    path: str,
    explicit: str | None,
    bindings: tuple[ResourceLibraryBinding, ...],
    *,
    fallback: str,
) -> str:
    if explicit:
        return explicit
    candidate = Path(path).expanduser().resolve(strict=False)
    matches = []
    for binding in bindings:
        if binding.root_path is None:
            continue
        root = Path(binding.root_path).expanduser().resolve(strict=False)
        if candidate == root or root in candidate.parents:
            matches.append((len(root.parts), binding.library_id))
    if not matches:
        return fallback
    matches.sort(reverse=True)
    return matches[0][1]


def _run_directory(
    path: str,
    strategy: StrategyTestRunner,
    *,
    live_metadata: bool,
    limit: int | None,
    show_naming: bool,
    show_classification: bool,
    show_plan: bool,
    resource_library_id: str,
) -> DirectoryStrategySummary:
    storage = LocalStorage("strategy-directory", path, read_only=True)
    guard = ReadOnlyStrategyStorage(storage)
    library = ResourceLibrary(
        resource_library_id,
        "Strategy Test Directory",
        guard.storage_id,
        "",
    )
    scanner = StorageScanner({guard.storage_id: guard}, InMemoryFileIndexRepository())
    return StrategyDirectoryRunner(scanner, library, strategy, guard).run(
        live_metadata=live_metadata,
        limit=limit,
        show_naming=show_naming,
        show_classification=show_classification,
        show_plan=show_plan,
    )


def _execute_local_result(
    result: StrategyTestResult,
    path: str,
    execution_root: str | None,
    bindings: tuple[ResourceLibraryBinding, ...],
    *,
    execute: bool,
) -> StrategyTestResult:
    if result.organize_plan is None:
        raise StrategyConfigurationError("--execute requires a successfully generated OrganizePlan")
    if not execution_root:
        raise StrategyConfigurationError(
            "--execute requires --execution-root or MEDIAFLOW_EXECUTION_ROOT"
        )
    source_path = Path(path).expanduser().resolve(strict=False)
    source_root = source_path.parent
    matching_roots = []
    for binding in bindings:
        if binding.root_path is None:
            continue
        root = Path(binding.root_path).expanduser().resolve(strict=False)
        if source_path == root or root in source_path.parents:
            matching_roots.append(root)
    if matching_roots:
        source_root = max(matching_roots, key=lambda item: len(item.parts))
    destination_root = Path(execution_root).expanduser().resolve(strict=True)
    resolved_destination = destination_root.joinpath(*result.organize_plan.target.split("/"))
    if not execute:
        execution = OrganizerExecutor().execute(
            result.organize_plan,
            {},
            resolved_destination=resolved_destination.as_posix(),
        )
        return replace(result, execution=execution)
    source_storage = LocalStorage("strategy-execute-source", source_root)
    if source_root == destination_root:
        target_storage = source_storage
    else:
        target_storage = LocalStorage("strategy-execute-target", destination_root)
    execution = OrganizerExecutor().execute(
        result.organize_plan,
        {
            result.organize_plan.source_storage_id: source_storage,
            result.organize_plan.target_storage_id: target_storage,
        },
        execute=True,
        source_storage_path=source_path.relative_to(source_root).as_posix(),
        destination_storage_path=result.organize_plan.target,
        resolved_destination=resolved_destination.as_posix(),
    )
    return replace(result, execution=execution)


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
            f"Library: {_value(classification.library if classification else None)}",
            f"Category: {_value(classification.category if classification else None)}",
            f"Subcategory: {_value(classification.subcategory if classification else None)}",
            f"Path: {_value(classification.relative_path if classification else None)}",
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


def render_case_summary(summary: CaseRunSummary) -> str:
    lines = [
        "Strategy Cases",
        f"Total: {summary.total}",
        f"Passed: {summary.passed}",
        f"Failed: {summary.failed}",
        f"Skipped: {summary.skipped}",
    ]
    for item in summary.cases:
        lines.append(f"{'PASS' if item.passed else 'FAIL'} {item.name}")
        if not item.passed:
            matched_rules = [rule.rule_id for rule in item.strategy.recognition.matched_rules]
            evidence = [evidence.field for evidence in item.strategy.recognition.evidence]
            lines.extend(
                [
                    f"  Expected: {json.dumps(item.expected, ensure_ascii=False, sort_keys=True)}",
                    f"  Actual: {json.dumps(item.actual, ensure_ascii=False, sort_keys=True)}",
                    f"  Matched rules: {matched_rules}",
                    f"  Recognition evidence: {evidence}",
                ]
            )
    return "\n".join(lines) + "\n"


def render_directory_summary(summary: DirectoryStrategySummary) -> str:
    if summary.show_classification:
        return _render_classification_directory_summary(summary)
    if summary.show_naming:
        return _render_naming_directory_summary(summary)
    lines = [
        "Strategy Directory",
        "status | RecognitionType | parsed title/year | metadata result/confidence",
    ]
    for item in summary.items:
        if item.error or item.strategy is None:
            lines.append(f"error | - | {item.path} | {_redact(item.error or 'unknown error')}")
            continue
        result = item.strategy
        metadata = result.metadata
        identity = metadata.identity if metadata else None
        confidence = identity.confidence if identity else None
        status = metadata.status.value if metadata else result.recognition.status.value
        lines.append(
            " | ".join(
                (
                    status,
                    _value(result.recognition.recognition_type_id),
                    f"{result.parsed.title_candidate}/{_value(result.parsed.year)}",
                    f"{metadata.status.value if metadata else 'offline'}/{_value(confidence)}",
                )
            )
        )
    for error in summary.scan_errors:
        lines.append(f"error | - | {error.path} | {error.operation}/{error.storage_error.value}")
    lines.extend(
        [
            "",
            f"Total: {summary.total}",
            f"Matched: {summary.matched}",
            f"NeedConfirm: {summary.need_confirm}",
            f"Ambiguous: {summary.ambiguous}",
            f"NotFound: {summary.not_found}",
            f"Unrecognized: {summary.unrecognized}",
            f"Errors: {summary.errors}",
            "Storage mutations: "
            + ", ".join(f"{name}={count}" for name, count in summary.mutation_calls.items()),
        ]
    )
    return "\n".join(lines) + "\n"


def _render_naming_directory_summary(summary: DirectoryStrategySummary) -> str:
    lines = [
        "Naming Preview Directory",
        "status | RecognitionType | title | year | directory | filename / warning",
    ]
    for item in summary.items:
        if item.error or item.strategy is None:
            lines.append(
                f"ERROR | - | {item.path} | - | - | {_redact(item.error or 'unknown error')}"
            )
            continue
        result = item.strategy
        metadata = result.metadata
        identity = metadata.identity if metadata else None
        if result.naming_error:
            status, detail = "ERROR", _redact(result.naming_error)
        elif result.naming:
            status = "WARN" if result.naming.warnings else "PASS"
            detail = result.naming.filename
        elif metadata and metadata.status.value in {"need_confirm", "not_found"}:
            status, detail = "WARN", f"metadata {metadata.status.value}"
        else:
            status, detail = "WARN", "naming unavailable: MediaIdentity required"
        directory = result.naming.directory if result.naming else "-"
        lines.append(
            " | ".join(
                (
                    status,
                    _value(result.recognition.recognition_type_id),
                    identity.title if identity else result.parsed.title_candidate,
                    _value(identity.year if identity else result.parsed.year),
                    directory,
                    detail,
                )
            )
        )
    for error in summary.scan_errors:
        lines.append(
            f"ERROR | - | {error.path} | - | - | {error.operation}/{error.storage_error.value}"
        )
    lines.extend(
        [
            "",
            f"Total: {summary.total}",
            f"Naming OK: {summary.naming_ok}",
            f"Warnings: {summary.naming_warnings}",
            f"Metadata NeedConfirm: {summary.metadata_need_confirm}",
            f"Metadata NotFound: {summary.metadata_not_found}",
            f"Naming Errors: {summary.naming_errors}",
            f"Other Errors: {summary.other_errors}",
            "Classification executions: 0",
            "Organizer executions: 0",
            "Storage mutations: "
            + ", ".join(f"{name}={count}" for name, count in summary.mutation_calls.items()),
        ]
    )
    return "\n".join(lines) + "\n"


def _render_classification_directory_summary(summary: DirectoryStrategySummary) -> str:
    lines = [
        "Classification Preview Directory",
        "status | RecognitionType | title | library | category | rule",
    ]
    executions = 0
    for item in summary.items:
        if item.error or item.strategy is None:
            lines.append(f"ERROR | - | {item.path} | - | - | {_redact(item.error or 'unknown')}")
            continue
        result = item.strategy
        identity = result.metadata.identity if result.metadata else None
        classification = result.classification
        if result.classification_error:
            status, detail = "ERROR", _redact(result.classification_error)
        elif classification:
            executions += 1
            status, detail = (
                classification.status.value.upper(),
                _value(classification.matched_rule_id),
            )
        else:
            status, detail = "UNAVAILABLE", "MediaIdentity required"
        lines.append(
            " | ".join(
                (
                    status,
                    _value(result.recognition.recognition_type_id),
                    identity.title if identity else result.parsed.title_candidate,
                    _value(classification.library if classification else None),
                    _value(classification.category if classification else None),
                    detail,
                )
            )
        )
    lines.extend(
        [
            "",
            f"Total: {summary.total}",
            f"Errors: {summary.errors}",
            f"Classification executions: {executions}",
            "Organizer executions: 0",
            "Storage mutations: "
            + ", ".join(f"{name}={count}" for name, count in summary.mutation_calls.items()),
        ]
    )
    return "\n".join(lines) + "\n"


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
