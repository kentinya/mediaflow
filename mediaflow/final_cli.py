from __future__ import annotations

import argparse
import io
import json
import os
import signal
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TextIO
from zoneinfo import ZoneInfo

from mediaflow.application.automation import (
    AutomationCancelled,
    AutomationJobService,
    AutomationWorker,
    IntervalScheduler,
)
from mediaflow.application.conflict_resolution import ConfirmationService
from mediaflow.application.library_pipeline import ResourceLibraryScanner
from mediaflow.application.media_organizer import MediaOrganizerBatchResult, MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import strategy_runner_from_configuration
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.cli import render_strategy_result
from mediaflow.domain.automation import CronSchedule
from mediaflow.domain.notification import NotificationDeliveryStatus
from mediaflow.domain.organizer import ConflictStrategy
from mediaflow.domain.task_persistence import (
    ConfirmationStatus,
    PersistentTask,
    PersistentTaskItem,
    TaskItemStatus,
)
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    load_runtime_configuration,
)
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.tmdb import TMDBClient, TMDBConfig, TMDBProvider


def final_main(
    argv: list[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
    cancellation_check: Callable[[], bool] | None = None,
) -> int:
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
    tasks = commands.add_parser("tasks", help="persistent task operations")
    task_commands = tasks.add_subparsers(dest="task_command", required=True)
    task_list = task_commands.add_parser("list")
    task_list.add_argument("--limit", type=int, default=20)
    task_show = task_commands.add_parser("show")
    task_show.add_argument("task_id")
    for name in ("resume", "retry-failed"):
        task_retry = task_commands.add_parser(name)
        task_retry.add_argument("task_id")
        task_retry.add_argument("--execute", action="store_true")
    confirmations = commands.add_parser("confirmations", help="persistent conflict decisions")
    confirmation_commands = confirmations.add_subparsers(dest="confirmation_command", required=True)
    confirmation_list = confirmation_commands.add_parser("list")
    confirmation_list.add_argument("--all", action="store_true")
    confirmation_show = confirmation_commands.add_parser("show")
    confirmation_show.add_argument("confirmation_id")
    confirmation_resolve = confirmation_commands.add_parser("resolve")
    confirmation_resolve.add_argument("confirmation_id")
    confirmation_resolve.add_argument(
        "--strategy", required=True, choices=[item.value for item in ConflictStrategy]
    )
    confirmation_resolve.add_argument("--confirm-overwrite", action="store_true")
    confirmation_resolve.add_argument("--actor")
    confirmation_resolve.add_argument("--note")
    storage_command = commands.add_parser("storage", help="Storage configuration and preflight")
    storage_commands = storage_command.add_subparsers(dest="storage_command", required=True)
    storage_commands.add_parser("list", help="list configured Storages without connecting")
    storage_check = storage_commands.add_parser("check", help="run read-only Storage preflight")
    storage_check.add_argument("storage_id", nargs="?")
    jobs = commands.add_parser("jobs", help="persistent DryRun background jobs")
    job_commands = jobs.add_subparsers(dest="job_command", required=True)
    job_list = job_commands.add_parser("list")
    job_list.add_argument("--limit", type=int, default=20)
    job_show = job_commands.add_parser("show")
    job_show.add_argument("job_id")
    job_submit = job_commands.add_parser("submit")
    job_submit.add_argument("workflow", choices=("scan", "preview"))
    job_submit.add_argument("--limit", type=int)
    job_cancel = job_commands.add_parser("cancel")
    job_cancel.add_argument("job_id")
    job_stale = job_commands.add_parser("stale")
    job_stale.add_argument("--age-seconds", type=float, required=True)
    job_requeue = job_commands.add_parser("requeue")
    job_requeue.add_argument("job_id")
    job_requeue.add_argument("--age-seconds", type=float, required=True)
    worker = commands.add_parser("worker", help="run persistent DryRun jobs")
    worker_commands = worker.add_subparsers(dest="worker_command", required=True)
    worker_commands.add_parser("run-next")
    worker_run = worker_commands.add_parser("run")
    worker_run.add_argument("--poll-seconds", type=float)
    scheduler = commands.add_parser("scheduler", help="persistent interval schedules")
    scheduler_commands = scheduler.add_subparsers(dest="scheduler_command", required=True)
    scheduler_commands.add_parser("list")
    scheduler_commands.add_parser("tick")
    scheduler_audit = scheduler_commands.add_parser("audit")
    scheduler_audit.add_argument("schedule_id", nargs="?")
    scheduler_audit.add_argument("--limit", type=int, default=100)
    scheduler_run = scheduler_commands.add_parser("run")
    scheduler_run.add_argument("--poll-seconds", type=float)
    notifications = commands.add_parser("notifications", help="notification outbox operations")
    notification_commands = notifications.add_subparsers(dest="notification_command", required=True)
    notification_list = notification_commands.add_parser("list")
    notification_list.add_argument(
        "--status", choices=[item.value for item in NotificationDeliveryStatus]
    )
    notification_list.add_argument("--limit", type=int, default=100)
    notification_requeue = notification_commands.add_parser("requeue")
    notification_requeue.add_argument("delivery_id")
    notification_stale = notification_commands.add_parser("stale")
    notification_stale.add_argument("--age-seconds", type=float, required=True)
    notification_stale.add_argument("--limit", type=int, default=100)
    notification_worker = commands.add_parser(
        "notification-worker", help="deliver signed webhook notifications"
    )
    notification_worker_commands = notification_worker.add_subparsers(
        dest="notification_worker_command", required=True
    )
    notification_worker_commands.add_parser("run-next")
    notification_worker_run = notification_worker_commands.add_parser("run")
    notification_worker_run.add_argument("--poll-seconds", type=float)
    api = commands.add_parser("api", help="development REST API")
    api_commands = api.add_subparsers(dest="api_command", required=True)
    api_serve = api_commands.add_parser("serve")
    api_serve.add_argument("--host", default="127.0.0.1")
    api_serve.add_argument("--port", type=int, default=8787)
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
                f"Webhooks: {len(configuration.webhooks)}\n"
            )
            return 0
        if arguments.command == "notifications":
            if arguments.notification_command in {"list", "stale"} and arguments.limit < 1:
                raise ValueError("notification limit must be positive")
            with SQLiteTaskRepository(configuration.database_path) as repository:
                if arguments.notification_command == "list":
                    status = (
                        NotificationDeliveryStatus(arguments.status) if arguments.status else None
                    )
                    stdout.write(
                        render_notifications(
                            repository.list_deliveries(status=status, limit=arguments.limit)
                        )
                    )
                elif arguments.notification_command == "requeue":
                    stdout.write(
                        render_notification(
                            repository.requeue_dead_letter(arguments.delivery_id, datetime.now(UTC))
                        )
                    )
                else:
                    if arguments.age_seconds <= 0:
                        raise ValueError("notification stale age must be positive")
                    cutoff = datetime.now(UTC) - timedelta(seconds=arguments.age_seconds)
                    stdout.write(
                        render_notifications(
                            repository.list_stale_deliveries(cutoff, limit=arguments.limit)
                        )
                    )
            return 0
        if arguments.command == "notification-worker":
            from mediaflow.infrastructure.webhook import UrllibWebhookTransport

            with SQLiteTaskRepository(configuration.database_path) as repository:
                delivery_worker = NotificationWorker(
                    repository,
                    configuration.resolve_webhook_targets(),
                    UrllibWebhookTransport(),
                    delivery_lease_seconds=configuration.notification_delivery_lease_seconds,
                )
                if arguments.notification_worker_command == "run-next":
                    delivery = delivery_worker.run_next()
                    if delivery is None:
                        stdout.write("No due notification deliveries\n")
                        return 0
                    stdout.write(render_notification(delivery))
                    return 0 if delivery.status.value in {"delivered", "retry"} else 1
                poll = arguments.poll_seconds or configuration.notification_poll_seconds
                processed = _run_resident(
                    lambda stop: delivery_worker.run(
                        stop, poll_seconds=poll, sleep=lambda seconds: _wait(stop, seconds)
                    )
                )
                stdout.write(f"Notification worker stopped; processed={processed}\n")
            return 0
        if arguments.command == "tasks" and arguments.task_command in {"list", "show"}:
            with SQLiteTaskRepository(configuration.database_path) as repository:
                if arguments.task_command == "list":
                    stdout.write(render_tasks(repository.list_tasks(limit=arguments.limit)))
                else:
                    task = repository.get_task(arguments.task_id)
                    if task is None:
                        raise LookupError(f"task {arguments.task_id!r} was not found")
                    stdout.write(render_task(task, repository.list_items(task.task_id)))
            return 0
        if arguments.command == "confirmations":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                service = ConfirmationService(repository)
                if arguments.confirmation_command == "list":
                    values = repository.list_confirmations(
                        status=None if arguments.all else ConfirmationStatus.PENDING
                    )
                    stdout.write(render_confirmations(values))
                elif arguments.confirmation_command == "show":
                    value = repository.get_confirmation(arguments.confirmation_id)
                    if value is None:
                        raise LookupError(
                            f"confirmation {arguments.confirmation_id!r} was not found"
                        )
                    stdout.write(
                        render_confirmation(
                            value,
                            repository.list_confirmation_audit(value.confirmation_id),
                        )
                    )
                else:
                    value = service.resolve(
                        arguments.confirmation_id,
                        ConflictStrategy(arguments.strategy),
                        confirm_overwrite=arguments.confirm_overwrite,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    item = repository.get_item(value.item_id)
                    if item is not None:
                        from dataclasses import replace

                        repository.upsert_item(
                            replace(
                                item,
                                status=(
                                    TaskItemStatus.SKIPPED
                                    if value.selected_strategy == ConflictStrategy.SKIP.value
                                    else TaskItemStatus.PENDING
                                ),
                                stage="conflict_resolved",
                                updated_at=datetime.now(UTC),
                            )
                        )
                    stdout.write(render_confirmation(value, ()))
            return 0
        if arguments.command == "storage":
            if arguments.storage_command == "list":
                stdout.write(render_storage_definitions(configuration.storage_definitions))
                return 0
            selected = (
                [arguments.storage_id]
                if arguments.storage_id
                else [item.storage_id for item in configuration.storage_definitions]
            )
            known = {item.storage_id for item in configuration.storage_definitions}
            unknown = set(selected) - known
            if unknown:
                raise ValueError(f"unknown Storage {sorted(unknown)[0]!r}")
            failures = 0
            lines = ["", "STORAGE CHECK", ""]
            for storage_id in selected:
                storage = None
                try:
                    storage = configuration.create_storages(storage_ids={storage_id})[storage_id]
                    _read_only_storage_check(storage)
                    lines.append(f"PASS | {storage_id} | read-only preflight succeeded")
                except Exception as error:
                    failures += 1
                    lines.append(f"FAIL | {storage_id} | {_safe_preflight_error(error)}")
                finally:
                    close = getattr(storage, "close", None)
                    if callable(close):
                        try:
                            close()
                        except Exception:
                            pass
            lines.extend(("", f"Total: {len(selected)}", f"Failed: {failures}", ""))
            stdout.write("\n".join(lines))
            return 1 if failures else 0
        if arguments.command == "jobs":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                service = AutomationJobService(repository)
                if arguments.job_command == "list":
                    stdout.write(render_jobs(repository.list_jobs(limit=arguments.limit)))
                elif arguments.job_command == "show":
                    job = repository.get_job(arguments.job_id)
                    if job is None:
                        raise LookupError(f"automation job {arguments.job_id!r} was not found")
                    stdout.write(render_job(job))
                elif arguments.job_command == "submit":
                    job = service.submit(arguments.workflow, limit=arguments.limit)
                    stdout.write(render_job(job))
                elif arguments.job_command == "cancel":
                    stdout.write(render_job(service.cancel(arguments.job_id)))
                elif arguments.job_command == "stale":
                    stdout.write(render_jobs(service.stale(age_seconds=arguments.age_seconds)))
                else:
                    stdout.write(
                        render_job(
                            service.requeue_stale(
                                arguments.job_id, age_seconds=arguments.age_seconds
                            )
                        )
                    )
            return 0
        if arguments.command == "worker":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                worker_service = AutomationWorker(
                    repository,
                    lambda job, cancelled: _run_queued_workflow(job, arguments.config, cancelled),
                    NotificationPublisher(repository, configuration.webhooks),
                )
                if arguments.worker_command == "run-next":
                    job = worker_service.run_next()
                    if job is None:
                        stdout.write("No pending automation jobs\n")
                        return 0
                    stdout.write(render_job(job))
                    return 0 if job.status.value in {"completed", "cancelled"} else 1
                poll = arguments.poll_seconds or configuration.worker_poll_seconds
                processed = _run_resident(
                    lambda stop: worker_service.run(
                        stop, poll_seconds=poll, sleep=lambda seconds: _wait(stop, seconds)
                    )
                )
                stdout.write(f"Worker stopped; processed={processed}\n")
                return 0
        if arguments.command == "scheduler":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                scheduler_service = IntervalScheduler(
                    repository,
                    configuration.automation_schedules,
                    NotificationPublisher(repository, configuration.webhooks),
                )
                if arguments.scheduler_command == "list":
                    stdout.write(
                        render_schedules(
                            configuration.automation_schedules,
                            repository.list_schedule_states(),
                        )
                    )
                    return 0
                if arguments.scheduler_command == "tick":
                    queued = scheduler_service.tick()
                    stdout.write(render_jobs(queued))
                    return 0
                if arguments.scheduler_command == "audit":
                    known = {item.schedule_id for item in configuration.automation_schedules}
                    if arguments.schedule_id and arguments.schedule_id not in known:
                        raise LookupError(f"schedule {arguments.schedule_id!r} was not found")
                    if arguments.limit < 1:
                        raise ValueError("schedule audit limit must be positive")
                    stdout.write(
                        render_schedule_audit(
                            repository.list_schedule_audit(
                                arguments.schedule_id, limit=arguments.limit
                            ),
                            configuration.automation_schedules,
                        )
                    )
                    return 0
                poll = arguments.poll_seconds or configuration.scheduler_poll_seconds
                emitted = _run_resident(
                    lambda stop: scheduler_service.run(
                        stop, poll_seconds=poll, sleep=lambda seconds: _wait(stop, seconds)
                    )
                )
                stdout.write(f"Scheduler stopped; emitted={emitted}\n")
                return 0
        if arguments.command == "api":
            if not configuration.api_token_env:
                raise ValueError("API tokenEnv is not configured")
            token = os.environ.get(configuration.api_token_env)
            if not token:
                raise ValueError(f"API requires environment variable {configuration.api_token_env}")
            if not 1 <= arguments.port <= 65535:
                raise ValueError("API port must be between 1 and 65535")
            from wsgiref.simple_server import make_server

            from mediaflow.interfaces.service_api import MediaFlowApi

            with SQLiteTaskRepository(configuration.database_path) as repository:
                app = MediaFlowApi(repository, token, configuration.automation_schedules)
                stdout.write(f"MediaFlow API listening on {arguments.host}:{arguments.port}\n")
                stdout.flush()
                with make_server(arguments.host, arguments.port, app) as server:
                    server.serve_forever()
            return 0

        storages = configuration.create_storages()
        if arguments.command == "scan":
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("scan", execute_authorized=False)
                discovered = []

                def on_discovered(library, file) -> None:
                    discovered.append((library.library_id, file.storage_id, file.path))
                    coordinator.record_discovered(
                        task.task_id,
                        file.storage_id,
                        library.library_id,
                        file.path,
                        f"{file.storage_id}:{file.path}",
                    )

                batch = ResourceLibraryScanner(
                    StorageScanner(storages, file_index),
                    configuration.resource_libraries,
                    storages,
                ).scan_all(
                    limit=arguments.limit,
                    on_discovered=on_discovered,
                    cancellation_check=cancellation_check,
                )
                errors = tuple(error for result in batch.results for error in result.errors)
                cancelled = bool(cancellation_check and cancellation_check())
                if cancelled:
                    coordinator.cancel(task.task_id)
                else:
                    coordinator.finish(task.task_id, MediaOrganizerBatchResult((), errors))
                stdout.write(f"Task ID: {task.task_id}\n")
                stdout.write(render_scan(batch.results, discovered))
                return 130 if cancelled else 1 if errors else 0
        library = display_root = None
        if getattr(arguments, "path", None):
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
        with (
            SQLiteTaskRepository(configuration.database_path) as repository,
            SQLiteFileIndexRepository(configuration.database_path) as file_index,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            retry_items: tuple[PersistentTaskItem, ...] | None = None
            if arguments.command == "tasks":
                original = coordinator.require(arguments.task_id)
                if arguments.execute and not original.execute_authorized:
                    raise ValueError(
                        "original task was not execute-authorized; retry cannot enable execute"
                    )
                retry_items = coordinator.retryable_items(
                    original.task_id,
                    failed_only=arguments.task_command == "retry-failed",
                )
                repository.reclaim_task_locks(original.task_id)
                execute = bool(arguments.execute and original.execute_authorized)
                task = coordinator.create(
                    f"{arguments.task_command}:{original.task_id}",
                    execute_authorized=execute,
                )
            else:
                execute = arguments.command == "organize" and arguments.execute
                task = coordinator.create(arguments.command, execute_authorized=execute)
            service = MediaOrganizerService(
                strategy,
                StorageScanner(storages, file_index),
                storages,
                {item.library_id: item for item in configuration.media_libraries},
                configuration.strategy.recognition_type_policies,
                JsonLinesOperationHistoryRepository(configuration.history_path),
                source_display_roots=dict(configuration.resource_display_roots),
                task_coordinator=coordinator,
                task_id=task.task_id,
                conflict_decisions={
                    (value.source_storage_id, value.source_path): value
                    for value in repository.list_confirmations(status=ConfirmationStatus.RESOLVED)
                }
                if retry_items is not None
                else {},
            )
            if retry_items is not None:
                libraries = {item.library_id: item for item in configuration.resource_libraries}
                retried = []
                for stored in retry_items:
                    resource = libraries.get(stored.resource_library_id)
                    if resource is None:
                        raise ValueError(
                            f"task item references missing ResourceLibrary "
                            f"{stored.resource_library_id!r}"
                        )
                    retried.append(
                        service.process_file(
                            stored.source_display,
                            resource_library=resource,
                            storage_path=stored.source_path,
                            execute=execute,
                        )
                    )
                summary = MediaOrganizerBatchResult(tuple(retried))
            elif arguments.path is None:
                summary = service.process_all_libraries(
                    configuration.resource_libraries,
                    execute=execute,
                    limit=arguments.limit,
                    progress=lambda done, total, source: stdout.write(
                        f"PROGRESS {done}/{total or '?'} {source}\n"
                    ),
                    cancellation_check=cancellation_check,
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
                        cancellation_check=cancellation_check,
                    )
                else:
                    storage_path = path.relative_to(
                        Path(display_root).resolve(strict=False)
                    ).as_posix()
                    storage_path = _storage_path(library.root_path, storage_path)
                    item = service.process_file(
                        path.as_posix(),
                        resource_library=library,
                        storage_path=storage_path,
                        execute=execute,
                    )
                    summary = MediaOrganizerBatchResult((item,))
            cancelled = bool(cancellation_check and cancellation_check())
            if cancelled:
                coordinator.cancel(task.task_id)
            else:
                coordinator.finish(task.task_id, summary)
            stdout.write(f"Task ID: {task.task_id}\n")
            stdout.write(render_summary(summary, execute=execute))
            return 130 if cancelled else 1 if summary.failed else 0
    except (OSError, ValueError, LookupError, RuntimeError) as error:
        stderr.write(f"mediaflow error: {error}\n")
        return 2


def render_summary(summary: MediaOrganizerBatchResult, *, execute: bool) -> str:
    lines = ["", "SUMMARY", "", f"Mode: {'EXECUTE' if execute else 'DRY_RUN'}"]
    for item in summary.items:
        status = (
            item.execution.status.value
            if item.execution
            else "FAILED"
            if item.error
            else "NEED_CONFIRM"
            if item.plan and item.plan.conflicts
            else "SKIPPED"
        )
        details = []
        if item.plan and item.plan.attachment_plans:
            details.append(f"attachments={len(item.plan.attachment_plans)}")
        if item.error:
            details.append(item.error)
        elif item.execution and item.execution.errors:
            details.append("; ".join(item.execution.errors))
        detail = " | ".join(details)
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


def render_tasks(tasks: tuple[PersistentTask, ...]) -> str:
    lines = ["", "TASKS", ""]
    for task in tasks:
        lines.append(
            f"{task.task_id} | {task.command} | {task.status.value} | "
            f"total={task.total_items} completed={task.completed_items} failed={task.failed_items}"
        )
    lines.extend(("", f"Total: {len(tasks)}", ""))
    return "\n".join(lines)


def render_task(task: PersistentTask, items: tuple[PersistentTaskItem, ...]) -> str:
    lines = [
        "",
        "TASK",
        "",
        f"ID: {task.task_id}",
        f"Command: {task.command}",
        f"Status: {task.status.value}",
        f"Execute authorized: {'YES' if task.execute_authorized else 'NO'}",
        f"Created: {task.created_at.isoformat()}",
        "",
        "ITEMS",
        "",
    ]
    for item in items:
        detail = item.error or item.destination_path or ""
        lines.append(
            f"{item.status.value} | {item.storage_id}:{item.source_path} | "
            f"attempts={item.attempts} | {detail}"
        )
    lines.extend(("", f"Total: {len(items)}", ""))
    return "\n".join(lines)


def render_confirmations(values) -> str:
    lines = ["", "CONFIRMATIONS", ""]
    for value in values:
        lines.append(
            f"{value.confirmation_id} | {value.status.value} | {value.conflict_type} | "
            f"{value.source_storage_id}:{value.source_path} -> "
            f"{value.destination_storage_id}:{value.destination_path}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_confirmation(value, audit) -> str:
    lines = [
        "",
        "CONFIRMATION",
        "",
        f"ID: {value.confirmation_id}",
        f"Status: {value.status.value}",
        f"Conflict: {value.conflict_type}",
        f"Configured strategy: {value.configured_strategy}",
        f"Selected strategy: {value.selected_strategy or '-'}",
        f"Source: {value.source_storage_id}:{value.source_path}",
        f"Destination: {value.destination_storage_id}:{value.destination_path}",
        f"Overwrite authorized: {'YES' if value.overwrite_authorized else 'NO'}",
        "",
        "AUDIT",
        "",
    ]
    lines.extend(
        f"{entry.decided_at.isoformat()} | {entry.strategy} | {entry.actor or '-'}"
        for entry in audit
    )
    lines.append("")
    return "\n".join(lines)


def render_storage_definitions(definitions) -> str:
    lines = ["", "STORAGES", ""]
    for value in definitions:
        capabilities = _declared_capabilities(value.storage_type, value.read_only)
        lines.append(
            f"{value.storage_id} | {value.storage_type} | root={value.root_path or '/'} | "
            f"readOnly={'YES' if value.read_only else 'NO'} | {capabilities}"
        )
    lines.extend(("", f"Total: {len(definitions)}", ""))
    return "\n".join(lines)


def render_jobs(values) -> str:
    lines = ["", "AUTOMATION JOBS", ""]
    for value in values:
        lines.append(
            f"{value.job_id} | {value.command.value} | {value.status.value} | "
            f"limit={value.limit or '-'} | task={value.task_id or '-'} | "
            f"schedule={value.schedule_id or '-'}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_job(value) -> str:
    return "\n".join(
        (
            "",
            "AUTOMATION JOB",
            "",
            f"ID: {value.job_id}",
            f"Command: {value.command.value}",
            f"Status: {value.status.value}",
            f"Limit: {value.limit or '-'}",
            f"Task ID: {value.task_id or '-'}",
            f"Error: {value.error or '-'}",
            f"Cancellation requested: {'YES' if value.cancellation_requested else 'NO'}",
            f"Schedule ID: {value.schedule_id or '-'}",
            "",
        )
    )


def render_notifications(values) -> str:
    lines = ["", "NOTIFICATION DELIVERIES", ""]
    for value in values:
        lines.append(
            f"{value.delivery_id} | {value.event_type.value} | {value.webhook_id} | "
            f"{value.status.value} | attempts={value.attempts} | "
            f"updated={value.updated_at.isoformat()} | failure={value.failure_category or '-'}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_notification(value) -> str:
    return render_notifications((value,))


def _run_queued_workflow(
    job, configured_path: str | None, cancellation_check: Callable[[], bool]
) -> str | None:
    args = []
    resolved = configured_path or os.environ.get("MEDIAFLOW_CONFIG")
    if resolved:
        args.extend(("--config", resolved))
    args.append(job.command.value)
    if job.limit is not None:
        args.extend(("--limit", str(job.limit)))
    output, errors = io.StringIO(), io.StringIO()
    code = final_main(args, stdout=output, stderr=errors, cancellation_check=cancellation_check)
    task_id = None
    for line in output.getvalue().splitlines():
        if line.startswith("Task ID: "):
            task_id = line.removeprefix("Task ID: ").strip()
            break
    if code == 130:
        raise AutomationCancelled(task_id)
    if code:
        raise RuntimeError("queued workflow returned a failure status")
    return task_id


def render_schedules(definitions, states) -> str:
    state_by_id = {item.schedule_id: item for item in states}
    lines = ["", "INTERVAL SCHEDULES", ""]
    for value in definitions:
        state = state_by_id.get(value.schedule_id)
        timing = (
            f"cron={value.expression} | timezone={value.timezone}"
            if isinstance(value, CronSchedule)
            else f"interval={value.interval_seconds:g}s"
        )
        local_next = (
            state.next_run_at.astimezone(ZoneInfo(value.timezone)).isoformat()
            if state and isinstance(value, CronSchedule)
            else "-"
        )
        lines.append(
            f"{value.schedule_id} | {value.command.value} | "
            f"enabled={'YES' if value.enabled else 'NO'} | {timing} | "
            f"limit={value.limit or '-'} | nextUtc="
            f"{state.next_run_at.isoformat() if state else '-'} | nextLocal={local_next}"
        )
    lines.extend(("", f"Total: {len(definitions)}", ""))
    return "\n".join(lines)


def render_schedule_audit(values, definitions=()) -> str:
    definitions_by_id = {item.schedule_id: item for item in definitions}
    lines = ["", "SCHEDULE AUDIT", ""]
    for value in values:
        definition = definitions_by_id.get(value.schedule_id)
        local = (
            value.occurrence_at.astimezone(ZoneInfo(definition.timezone)).isoformat()
            if isinstance(definition, CronSchedule)
            else "-"
        )
        lines.append(
            f"{value.emitted_at.isoformat()} | {value.schedule_id} | "
            f"occurrenceUtc={value.occurrence_at.isoformat()} | occurrenceLocal={local} | "
            f"job={value.job_id} | "
            f"command={value.command.value} | next={value.next_run_at.isoformat()}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def _run_resident(run: Callable[[Callable[[], bool]], int]) -> int:
    stopped = threading.Event()
    previous = {}

    def request_stop(_signum, _frame) -> None:
        stopped.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, request_stop)
    try:
        return run(stopped.is_set)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _wait(stop: Callable[[], bool], seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while not stop():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        threading.Event().wait(min(remaining, 0.25))


def _declared_capabilities(storage_type: str, read_only: bool) -> str:
    if read_only:
        return "move=NO copy=NO delete=NO hardLink=NO softLink=NO"
    links = storage_type == "local"
    return (
        "move=YES copy=YES delete=YES "
        f"hardLink={'YES' if links else 'NO'} softLink={'YES' if links else 'NO'}"
    )


def _read_only_storage_check(storage) -> None:
    health = getattr(storage, "health_check", None)
    if callable(health):
        health()
    else:
        connect = getattr(storage, "connect", None)
        if callable(connect):
            connect()
        storage.list("")


def _safe_preflight_error(error: Exception) -> str:
    from mediaflow.domain.storage import StorageError

    if isinstance(error, StorageError):
        return f"{error.code.value}: {error}"
    if isinstance(error, (ValueError, RuntimeError, OSError)):
        return str(error)
    return type(error).__name__


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
