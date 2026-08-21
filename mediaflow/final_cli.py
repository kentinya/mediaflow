from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import TextIO

from mediaflow.application.library_pipeline import ResourceLibraryScanner
from mediaflow.application.media_organizer import MediaOrganizerBatchResult, MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import strategy_runner_from_configuration
from mediaflow.cli import render_strategy_result
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    load_runtime_configuration,
)
from mediaflow.infrastructure.tmdb import TMDBClient, TMDBConfig, TMDBProvider


def final_main(argv: list[str], *, stdout: TextIO, stderr: TextIO) -> int:
    parser = argparse.ArgumentParser(prog="mediaflow")
    parser.add_argument("--config", help="runtime JSON configuration")
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="configuration operations")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("validate", help="validate configuration without processing media")
    analyze = commands.add_parser("analyze", help="analyze one file without planning execution")
    analyze.add_argument("path")
    analyze.add_argument("--offline", action="store_true")
    scan = commands.add_parser("scan", help="scan all configured ResourceLibraries read-only")
    scan.add_argument("--limit", type=int)
    preview = commands.add_parser("preview", help="run the complete workflow as DryRun")
    preview.add_argument("path", nargs="?")
    preview.add_argument("--limit", type=int)
    organize = commands.add_parser("organize", help="organize one file or a directory")
    organize.add_argument("path", nargs="?")
    organize.add_argument("--limit", type=int)
    organize.add_argument("--execute", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        configuration = _configuration(arguments.config)
        if arguments.command == "config":
            strategy = configuration.strategy
            stdout.write(
                "Configuration valid\n"
                f"Recognition rules: {len(strategy.recognition_rules)}\n"
                f"Recognition type policies: {len(strategy.recognition_type_policies)}\n"
                f"Metadata policies: {len(strategy.metadata_policies)}\n"
                f"Naming policies: {len(strategy.naming_policies)}\n"
                f"Classification policies: {len(strategy.classification_policies)}\n"
                f"Organize policies: {len(strategy.organize_policies)}\n"
            )
            return 0
        storages = configuration.create_storages()
        if arguments.command == "scan":
            discovered = []
            batch = ResourceLibraryScanner(
                StorageScanner(storages, InMemoryFileIndexRepository()),
                configuration.resource_libraries,
                storages,
            ).scan_all(
                limit=arguments.limit,
                on_discovered=lambda library, file: discovered.append(
                    (library.library_id, file.storage_id, file.path)
                ),
            )
            stdout.write(render_scan(batch.results, discovered))
            return 1 if any(result.errors for result in batch.results) else 0
        library = display_root = None
        if arguments.path:
            library, display_root = _resource_library(configuration, arguments.path)
        token = os.environ.get("TMDB_ACCESS_TOKEN") or os.environ.get("TMDB_TOKEN")
        providers = None
        if not (arguments.command == "analyze" and arguments.offline):
            if not token:
                raise ValueError("metadata workflow requires TMDB_ACCESS_TOKEN")
            providers = MetadataProviderRegistry((TMDBProvider(TMDBClient(TMDBConfig(token))),))
        strategy = strategy_runner_from_configuration(configuration.strategy, providers)
        if arguments.command == "analyze":
            assert library is not None
            result = strategy.run_path(
                str(Path(arguments.path).resolve(strict=False)),
                live_metadata=not arguments.offline,
                resource_library_id=library.library_id,
                storage_id=library.storage_id,
            )
            stdout.write(render_strategy_result(result))
            return 0
        service = MediaOrganizerService(
            strategy,
            StorageScanner(storages, InMemoryFileIndexRepository()),
            storages,
            {item.library_id: item for item in configuration.media_libraries},
            configuration.strategy.recognition_type_policies,
            JsonLinesOperationHistoryRepository(configuration.history_path),
            source_display_roots=dict(configuration.resource_display_roots),
        )
        execute = arguments.command == "organize" and arguments.execute
        if arguments.path is None:
            summary = service.process_all_libraries(
                configuration.resource_libraries,
                execute=execute,
                limit=arguments.limit,
                progress=lambda done, total, source: stdout.write(
                    f"PROGRESS {done}/{total or '?'} {source}\n"
                ),
            )
        else:
            assert library is not None and display_root is not None
            path = Path(arguments.path).resolve(strict=False)
            if path.is_dir():
                summary = service.process_library(
                    library,
                    execute=execute,
                    limit=arguments.limit,
                    progress=lambda done, total, source: stdout.write(
                        f"PROGRESS {done}/{total or '?'} {source}\n"
                    ),
                )
            else:
                storage_path = path.relative_to(Path(display_root).resolve(strict=False)).as_posix()
                storage_path = _storage_path(library.root_path, storage_path)
                item = service.process_file(
                    path.as_posix(),
                    resource_library=library,
                    storage_path=storage_path,
                    execute=execute,
                )
                summary = MediaOrganizerBatchResult((item,))
        stdout.write(render_summary(summary, execute=execute))
        return 1 if summary.failed else 0
    except (OSError, ValueError, LookupError, RuntimeError) as error:
        stderr.write(f"mediaflow error: {error}\n")
        return 2


def render_summary(summary: MediaOrganizerBatchResult, *, execute: bool) -> str:
    lines = ["", "SUMMARY", "", f"Mode: {'EXECUTE' if execute else 'DRY_RUN'}"]
    for item in summary.items:
        status = (
            item.execution.status.value if item.execution else "FAILED" if item.error else "SKIPPED"
        )
        detail = item.error or (
            "; ".join(item.execution.errors) if item.execution and item.execution.errors else ""
        )
        lines.append(f"{status} | {item.source} | {detail}")
    lines.extend(
        (
            "",
            f"Total: {summary.total}",
            f"Matched: {summary.matched}",
            f"Conflicts: {summary.conflicts}",
            f"Moved: {summary.moved}",
            f"Failed: {summary.failed}",
            "",
        )
    )
    return "\n".join(lines)


def render_scan(results, discovered) -> str:
    lines = ["", "SCAN", ""]
    by_library = {result.resource_library_id: result for result in results}
    for library_id, result in by_library.items():
        lines.extend(
            (
                f"ResourceLibrary: {library_id}",
                f"Status: {result.status.value}",
                f"Found: {sum(1 for item in discovered if item[0] == library_id)}",
                f"Errors: {len(result.errors)}",
                "",
            )
        )
    lines.append(f"Total: {len(discovered)}")
    lines.extend(f"{storage_id}:{path}" for _, storage_id, path in discovered)
    lines.append("")
    return "\n".join(lines)


def _configuration(path: str | None) -> RuntimeConfiguration:
    configured = path or os.environ.get("MEDIAFLOW_CONFIG")
    if not configured:
        raise ValueError("--config or MEDIAFLOW_CONFIG is required")
    return load_runtime_configuration(json.loads(Path(configured).read_text(encoding="utf-8")))


def _resource_library(configuration: RuntimeConfiguration, path: str) -> tuple[object, str]:
    candidate = Path(path).resolve(strict=False)
    roots = []
    libraries = {item.library_id: item for item in configuration.resource_libraries}
    for library_id, value in configuration.resource_display_roots:
        root = Path(value).resolve(strict=False)
        if candidate == root or root in candidate.parents:
            roots.append((len(root.parts), library_id, root.as_posix()))
    if not roots:
        raise ValueError("path is not inside a configured ResourceLibrary")
    _, library_id, root = max(roots)
    return libraries[library_id], root


def _storage_path(library_root: str, relative_to_display_root: str) -> str:
    return "/".join(
        value.strip("/") for value in (library_root, relative_to_display_root) if value.strip("/")
    )
