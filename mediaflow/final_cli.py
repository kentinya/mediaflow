from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import secrets
import signal
import threading
import time
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from mediaflow.application.automation import (
    AutomationConfigurationUnavailable,
    AutomationFailureEvidence,
    IntervalScheduler,
    ResidentProcessingWorker,
)
from mediaflow.application.automation_definition_execution import (
    DefinitionScopedExecutionService,
)
from mediaflow.application.automation_execution_authority import AutomationExecutionAuthority
from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import (
    MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
    ManagedConfigurationService,
)
from mediaflow.application.manual_ignore import ManualIgnoreService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.media_organizer import (
    IncompleteOrganizingScope,
    MediaOrganizerBatchResult,
    MediaOrganizerService,
    incomplete_scope_failure,
)
from mediaflow.application.notification import (
    NotificationPublisher,
    NotificationWorker,
    task_terminal_observer,
)
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.resident_services import ResidentServiceService
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.storage_browser import StorageBrowserError
from mediaflow.application.strategy_test import strategy_runner_from_configuration
from mediaflow.application.task_flow_settlement import (
    TaskFlowSettlementInputs,
    settle_task_flow,
)
from mediaflow.application.task_runtime import KernelTaskCoordinator, PersistentTaskCoordinator
from mediaflow.cli import render_strategy_result
from mediaflow.domain.automation import SchedulerConfigurationSnapshot
from mediaflow.domain.automation_settings import engine_values_from_document
from mediaflow.domain.configuration_input import reject_retired_configuration_input
from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.domain.failure import decode_failure_explanation
from mediaflow.domain.logging import LogLevel
from mediaflow.domain.notification import NotificationDeliveryStatus
from mediaflow.domain.resident_services import ResidentServiceWaiting
from mediaflow.domain.security import ApiPermission
from mediaflow.domain.task_persistence import (
    FILES_DELETE_TASK_COMMAND,
    FILES_TRANSFER_TASK_COMMAND,
    SETTLED_ITEM_STATUSES,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
    direct_command_task_command,
    task_item_counts,
)
from mediaflow.domain.task_scheduling import TaskControl
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.metadata_provider_bootstrap import (
    LazyMetadataProviderRegistryFactory,
    metadata_provider_registry_from_environment,
)
from mediaflow.infrastructure.operational_logging import SQLiteOperationalLogger
from mediaflow.infrastructure.runtime_configuration import (
    ManagementBootstrapConfiguration,
    RuntimeConfiguration,
    is_minimal_management_bootstrap,
    load_managed_runtime_configuration,
    load_management_bootstrap,
    load_runtime_configuration,
    with_managed_snapshot,
)
from mediaflow.infrastructure.runtime_lease import RuntimeDatabaseLease, RuntimeLeaseMode
from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_restore import SQLiteRestoreService
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository


def final_main(
    argv: list[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
    cancellation_check: Callable[[], bool] | None = None,
    _resolved_configuration: RuntimeConfiguration | None = None,
    _task_observer: Callable[[str], None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="mediaflow")
    parser.add_argument("--config", help="runtime JSON configuration")
    parser.add_argument("--configuration-snapshot-id", help=argparse.SUPPRESS)
    parser.add_argument("--configuration-snapshot-digest", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="configuration operations")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("validate", help="validate configuration without processing media")
    config_commands.add_parser("status", help="show JSON bootstrap/managed Active authority")
    initialize = config_commands.add_parser(
        "initialize", help="publish an empty managed configuration"
    )
    initialize.add_argument("--actor", default="local-cli")
    publish = config_commands.add_parser(
        "publish", help="check and publish one complete configuration document"
    )
    publish.add_argument("--file", help="JSON file; defaults to the current Active document")
    publish.add_argument("--actor", default="local-cli")
    publish.add_argument(
        "--replace-active",
        action="store_true",
        help="explicitly replace an unavailable managed Active from --file",
    )
    analyze = commands.add_parser("analyze", help="analyze one file without planning execution")
    analyze.add_argument("path")
    analyze.add_argument("--offline", action="store_true")
    organize = commands.add_parser("organize", help="organize one file or a directory")
    organize.add_argument("path", nargs="?")
    organize.add_argument("--limit", type=int)
    organize.add_argument("--execute", action="store_true")
    batch = commands.add_parser("batch", help="explicit all-ResourceLibrary batch operations")
    batch_commands = batch.add_subparsers(dest="batch_command", required=True)
    batch_organize = batch_commands.add_parser("organize")
    batch_organize.add_argument("--limit", type=int)
    batch_organize.add_argument("--execute", action="store_true")
    tasks = commands.add_parser("tasks", help="persistent task operations")
    task_commands = tasks.add_subparsers(dest="task_command", required=True)
    task_list = task_commands.add_parser("list")
    task_list.add_argument("--limit", type=int, default=20)
    task_show = task_commands.add_parser("show")
    task_show.add_argument("task_id")
    task_show_item = task_commands.add_parser("show-item")
    task_show_item.add_argument("task_id")
    task_show_item.add_argument("item_id")
    task_ignore = task_commands.add_parser("ignore-item")
    task_ignore.add_argument("task_id")
    task_ignore.add_argument("item_id")
    task_ignore.add_argument("--actor", required=True)
    task_ignore.add_argument("--note")
    task_ignore_pending = task_commands.add_parser("ignore-pending")
    task_ignore_pending.add_argument("--actor", required=True)
    task_ignore_pending.add_argument("--note")
    task_ignore_pending.add_argument("--limit", type=int, default=100)
    task_ignore_pending.add_argument("--task-id")
    task_cancel = task_commands.add_parser("cancel")
    task_cancel.add_argument("task_id")
    # ``retry-request`` and the independent ``retry-failed`` entrance are
    # absent from the command surface: new organizing starts from Files/CLI
    # organize and an existing Task's own four-type continuation; there is no
    # separate failure-retry command and no alias that would recreate one.
    storage_command = commands.add_parser("storage", help="Storage configuration and preflight")
    storage_commands = storage_command.add_subparsers(dest="storage_command", required=True)
    storage_commands.add_parser("list", help="list configured Storages without connecting")
    storage_check = storage_commands.add_parser("check", help="run read-only Storage preflight")
    storage_check.add_argument("storage_id", nargs="?")
    files = commands.add_parser(
        "files",
        help="read the live directory of one Active ResourceLibrary or MediaLibrary",
    )
    file_commands = files.add_subparsers(dest="file_command", required=True)
    file_list = file_commands.add_parser(
        "list",
        help="list one live library directory (read-only; nothing is recorded)",
    )
    library_scope = file_list.add_mutually_exclusive_group(required=True)
    library_scope.add_argument(
        "--resource-library",
        metavar="ID",
        help="ResourceLibrary ID to read the current live directory from",
    )
    library_scope.add_argument(
        "--media-library",
        metavar="ID",
        help="MediaLibrary ID to read the current live directory from",
    )
    file_list.add_argument(
        "--path",
        default="",
        help="library-relative directory (default: the library root)",
    )
    file_list.add_argument("--limit", type=int, default=100)
    file_list.add_argument("--cursor")
    worker = commands.add_parser("worker", help="run resident Task and file work")
    worker_commands = worker.add_subparsers(dest="worker_command", required=True)
    worker_commands.add_parser("run-next")
    worker_run = worker_commands.add_parser("run")
    worker_run.add_argument("--poll-seconds", type=float)
    scheduler = commands.add_parser("scheduler", help="Automation Task Definition scheduler")
    scheduler_commands = scheduler.add_subparsers(dest="scheduler_command", required=True)
    scheduler_commands.add_parser("tick")
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
    security_audit = commands.add_parser("security-audit", help="local API security audit")
    security_audit_commands = security_audit.add_subparsers(
        dest="security_audit_command", required=True
    )
    security_audit_list = security_audit_commands.add_parser("list")
    security_audit_list.add_argument("--limit", type=int, default=100)
    logs = commands.add_parser("logs", help="local redacted operational logs")
    log_commands = logs.add_subparsers(dest="log_command", required=True)
    log_list = log_commands.add_parser("list")
    log_list.add_argument("--limit", type=int, default=100)
    log_list.add_argument("--level", choices=[item.name for item in LogLevel])
    log_commands.add_parser("prune")
    database = commands.add_parser("database", help="runtime database protection")
    database_commands = database.add_subparsers(dest="database_command", required=True)
    database_backup = database_commands.add_parser("backup")
    database_backup.add_argument("--output", required=True)
    database_verify = database_commands.add_parser("verify")
    database_verify.add_argument("path")
    database_restore = database_commands.add_parser("restore")
    database_restore.add_argument("backup")
    database_restore.add_argument("--confirm-empty-destination", action="store_true")
    api = commands.add_parser("api", help="development REST API")
    api_commands = api.add_subparsers(dest="api_command", required=True)
    api_token = api_commands.add_parser("token", help="cryptographic bearer token operations")
    api_token_commands = api_token.add_subparsers(dest="api_token_command", required=True)
    api_token_generate = api_token_commands.add_parser("generate")
    api_token_generate.add_argument("--bytes", type=int, default=32, dest="token_bytes")
    api_credentials = api_commands.add_parser("credentials", help="redacted credential status")
    api_credential_commands = api_credentials.add_subparsers(
        dest="api_credential_command", required=True
    )
    api_credential_commands.add_parser("check")
    api_serve = api_commands.add_parser("serve")
    api_serve.add_argument("--host", default="127.0.0.1")
    api_serve.add_argument("--port", type=int, default=8787)
    api_serve.add_argument("--allow-insecure-remote-http", action="store_true")
    api_production = api_commands.add_parser(
        "serve-production", help="serve with the production WSGI adapter (Waitress)"
    )
    api_production.add_argument("--host", default="0.0.0.0")
    api_production.add_argument("--port", type=int, default=8080)
    api_production.add_argument("--threads", type=int, default=4)
    arguments, unsupported_arguments = parser.parse_known_args(argv)
    if unsupported_arguments:
        parser.error("unrecognized arguments: " + " ".join(unsupported_arguments))
    if arguments.command == "batch":
        arguments.command = arguments.batch_command
        arguments.path = None
    runtime_lease: RuntimeDatabaseLease | None = None
    direct_organize_worker_id: str | None = None
    try:
        if arguments.command == "api" and arguments.api_command == "token":
            if not 32 <= arguments.token_bytes <= 128:
                raise ValueError("API token bytes must be between 32 and 128")
            stdout.write(f"{secrets.token_urlsafe(arguments.token_bytes)}\n")
            return 0
        # A resumed/retried workflow must resolve the snapshot pinned to the
        # original Task before loading the runtime strategy.  Otherwise a
        # process restart after activation could silently run the old Task
        # against the new Active configuration.  The standalone retry-failed
        # entrance was retired (Slice 47 RO-6); a four-type continuation
        # resolves its own pinned snapshot inside its admitting service.
        snapshot_id = arguments.configuration_snapshot_id
        snapshot_digest = arguments.configuration_snapshot_digest

        # Database backup/restore are intentionally bootstrap-only.  Resolving
        # managed workflow configuration for them would open the configured
        # runtime database before the command's own read-only/atomic safety
        # checks run.
        configuration_management_command = (
            arguments.command == "config"
            and arguments.config_command
            in {
                "status",
                "initialize",
                "publish",
            }
        )
        management_bootstrap_database_path = None
        if configuration_management_command:
            # Recovery commands need only the immutable locator.  Do not make
            # status/import/validate depend on the rest of a broken runtime
            # document; the service performs the candidate validation later.
            management_bootstrap_database_path = _bootstrap_database_path(
                _configuration_document(arguments.config)
            )
        managed_command = (
            arguments.command != "database"
            and not configuration_management_command
            and not (arguments.command == "config" and arguments.config_command == "validate")
        )
        if _resolved_configuration is not None:
            configuration = _resolved_configuration
        elif arguments.command == "files":
            # ``files list`` is a strictly read-only library read.  It resolves
            # the exact Active revision itself through a ``mode=ro`` connection
            # and must never create, migrate or write-lock the runtime database,
            # so it bootstraps only the immutable locator here.
            configuration = load_management_bootstrap(_configuration_document(arguments.config))
        elif arguments.command in {"worker", "scheduler", "notification-worker"} or (
            arguments.command == "api" and arguments.api_command == "credentials"
        ):
            # Resident services bootstrap from deployment-owned authority alone.
            # The immutable locator is enough to open the durable database, run
            # the heartbeat and claim a bounded unit of already-pinned work.  It
            # deliberately does not resolve the current Active workflow, because
            # "no Active yet" is the normal first-setup state for a resident
            # service, not a startup error.  Each service resolves the exact
            # current — or its own admitted pin — at the boundary where it
            # actually needs business configuration, which is what lets a
            # running process adopt a later publication without restarting.
            #
            # ``api credentials check`` is the preflight the operator runs
            # before the first startup or after correcting a database path.  It
            # reports deployment-owned token names from the bootstrap alone and
            # must not open, initialize or validate the configured database;
            # otherwise an unsupported file would hide the SET/UNSET diagnosis
            # and a first start would create the store just to read environment
            # variables.
            configuration = load_management_bootstrap(_configuration_document(arguments.config))
        else:
            try:
                configuration = (
                    None
                    if configuration_management_command
                    else _configuration(
                        arguments.config,
                        use_managed=managed_command,
                        snapshot_id=snapshot_id,
                        snapshot_digest=snapshot_digest,
                    )
                )
            except RuntimeSnapshotUnavailable:
                # API management must remain available without trusting stale
                # workflow JSON.  It uses only the immutable locator and
                # environment-owned management credentials when Active is
                # unavailable; workflow content is not used for recovery.
                if arguments.command == "api":
                    configuration = load_management_bootstrap(
                        _configuration_document(arguments.config)
                    )
                else:
                    raise
        if (
            arguments.command == "database"
            and arguments.database_command == "restore"
            and not arguments.confirm_empty_destination
        ):
            raise ValueError("restore requires --confirm-empty-destination")
        lease_mode = _runtime_lease_mode(arguments)
        if lease_mode is not None:
            runtime_lease = RuntimeDatabaseLease(configuration.database_path, lease_mode).acquire(
                create_parent=lease_mode is RuntimeLeaseMode.SHARED
            )
        if arguments.command == "api" and arguments.api_command == "credentials":
            statuses = configuration.api_credential_statuses()
            stdout.write(render_api_credentials(statuses))
            return (
                0
                if statuses and all(not item.enabled or item.configured for item in statuses)
                else 1
            )
        if arguments.command == "config":
            bootstrap_document = _configuration_document(arguments.config)
            managed_config_command = arguments.config_command in {
                "status",
                "initialize",
                "publish",
            }
            if managed_config_command:
                database_path = management_bootstrap_database_path
                if database_path is None:
                    raise RuntimeError("configuration management bootstrap locator is unavailable")
                with SQLiteConfigurationRepository(database_path) as repository:
                    service = ManagedConfigurationService(
                        repository,
                        bootstrap_database_path=database_path,
                        bootstrap_document=bootstrap_document,
                        management_only=is_minimal_management_bootstrap(bootstrap_document),
                    )
                    if arguments.config_command == "status":
                        stdout.write(
                            json.dumps(service.status_document(), ensure_ascii=False, indent=2)
                            + "\n"
                        )
                        return 0
                    objects = ConfigurationObjectService(service)
                    if arguments.config_command == "initialize":
                        if service.status_document().get("managedActivation") is True:
                            raise ValueError(
                                "managed configuration already exists; initialize is closed"
                            )
                        from mediaflow.application.configuration_snapshot import (
                            build_first_setup_starter_document,
                        )
                        from mediaflow.infrastructure.runtime_configuration import (
                            load_minimal_management_bootstrap,
                        )

                        document = build_first_setup_starter_document(
                            load_minimal_management_bootstrap(bootstrap_document)
                        )
                        revision = objects.publish_document(document, actor=arguments.actor)
                        stdout.write(
                            json.dumps(
                                {**revision.summary(), "initialized": True},
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n"
                        )
                        return 0
                    if arguments.config_command == "publish":
                        if arguments.replace_active and not arguments.file:
                            raise ValueError(
                                "--replace-active requires --file with the complete "
                                "replacement document"
                            )
                        try:
                            active = service.active()
                        except RuntimeSnapshotUnavailable:
                            if not arguments.replace_active:
                                raise
                            active = None
                        if arguments.file:
                            document = json.loads(Path(arguments.file).read_text(encoding="utf-8"))
                        else:
                            if active is None:
                                raise ValueError(
                                    "no Active configuration exists; use `config initialize` "
                                    "or supply --file"
                                )
                            document = service.current_document(bootstrap_document)
                        revision = objects.publish_document(
                            document,
                            actor=arguments.actor,
                            expected_active_revision_id=(
                                active.revision_id if active is not None else None
                            ),
                            expected_active_version=(
                                (active.revision_sequence or active.version)
                                if active is not None
                                else None
                            ),
                            expected_active_digest=(active.digest if active is not None else None),
                            replace_active=arguments.replace_active,
                        )
                        stdout.write(
                            json.dumps(
                                {**revision.summary(), "published": True},
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n"
                        )
                        return 0
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
        if arguments.command == "logs":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                if arguments.log_command == "list":
                    values = repository.list_operational_logs(
                        limit=arguments.limit,
                        minimum_level=LogLevel[arguments.level] if arguments.level else None,
                    )
                    stdout.write(render_operational_logs(values))
                else:
                    removed = repository.prune_operational_logs(
                        before=datetime.now(UTC)
                        - timedelta(days=configuration.operational_logging_retention_days),
                        maximum_records=configuration.operational_logging_maximum_records,
                    )
                    stdout.write(f"Operational log rows removed: {removed}\n")
            return 0
        if arguments.command == "database":
            if arguments.database_command == "restore":
                result = SQLiteRestoreService(
                    arguments.backup, configuration.database_path
                ).restore(confirmed_empty_destination=arguments.confirm_empty_destination)
                stdout.write(render_database_restore(result))
            else:
                service = SQLiteBackupService(configuration.database_path)
                result = (
                    service.backup(arguments.output)
                    if arguments.database_command == "backup"
                    else service.verify(arguments.path)
                )
                stdout.write(render_database_backup(result, arguments.database_command))
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
            return _run_notification_worker(
                configuration,
                arguments,
                arguments.config,
                stdout=stdout,
            )
        if arguments.command == "security-audit":
            if arguments.limit < 1 or arguments.limit > 1000:
                raise ValueError("security audit limit must be between 1 and 1000")
            with SQLiteTaskRepository(configuration.database_path) as repository:
                stdout.write(
                    render_security_audit(repository.list_security_audit(limit=arguments.limit))
                )
            return 0
        if arguments.command == "tasks" and arguments.task_command in {
            "list",
            "show",
            "show-item",
            "ignore-item",
            "ignore-pending",
            "cancel",
        }:
            with ExitStack() as stack:
                repository = stack.enter_context(SQLiteTaskRepository(configuration.database_path))
                _attach_task_terminal_notifications(repository, arguments.config)
                recovery_admission = None
                if arguments.task_command in {"ignore-item", "ignore-pending"}:
                    configuration_repository = stack.enter_context(
                        SQLiteConfigurationRepository(configuration.database_path)
                    )
                    managed_service = ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=configuration.database_path,
                    )
                    recovery_admission = RecoveryAdmissionService(
                        repository,
                        snapshot_validator=managed_service.validate_runtime_snapshot,
                    )
                if arguments.task_command == "list":
                    stdout.write(render_tasks(repository.list_tasks(limit=arguments.limit)))
                elif arguments.task_command == "show":
                    task = repository.get_task(arguments.task_id)
                    if task is None:
                        raise LookupError(f"task {arguments.task_id!r} was not found")
                    stdout.write(render_task(task, repository.list_items(task.task_id)))
                elif arguments.task_command == "show-item":
                    checkpoint_service = ProcessingCheckpointService(
                        repository, snapshot_validator=None
                    )
                    checkpoint = checkpoint_service.get(
                        arguments.item_id, task_id=arguments.task_id
                    )
                    stdout.write(render_recovery_checkpoint(checkpoint))
                elif arguments.task_command == "cancel":
                    from mediaflow.application.operations_lifecycle import (
                        TaskLifecycleService,
                    )

                    task = repository.get_task(arguments.task_id)
                    if task is None:
                        raise LookupError(f"task {arguments.task_id!r} was not found")
                    cancelled = TaskLifecycleService(repository).cancel(
                        task.task_id,
                        expected_version=task.updated_at.isoformat(),
                    )
                    stdout.write(
                        f"Task ID: {cancelled.task_id}\nStatus: {cancelled.status.value}\n"
                    )
                elif arguments.task_command == "ignore-pending":
                    decisions = ManualIgnoreService(
                        repository, recovery_admission=recovery_admission
                    ).ignore_pending(
                        actor=arguments.actor,
                        note=arguments.note,
                        limit=arguments.limit,
                        task_id=arguments.task_id,
                    )
                    stdout.write(render_manual_ignore_batch(decisions))
                else:
                    decision = ManualIgnoreService(
                        repository, recovery_admission=recovery_admission
                    ).ignore(
                        arguments.task_id,
                        arguments.item_id,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    task = repository.get_task(arguments.task_id)
                    stdout.write(
                        render_manual_ignore(
                            decision,
                            task,
                            repository.list_items(arguments.task_id),
                        )
                    )
            return 0
        if arguments.command == "files":
            # ``files list`` reads one exact Active library directory through the
            # same application browser the Web Files and MediaLibrary pages use.
            # It is strictly read-only: it opens no Task/Result repository, creates
            # or upgrades no database, records no directory entry and grants no
            # execution authority.
            if arguments.file_command != "list":
                raise ValueError(
                    f"unsupported files command {arguments.file_command!r}; "
                    "use 'files list' to read one live library directory"
                )
            stdout.write(_render_live_library_directory(configuration, arguments))
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
        if arguments.command == "worker":
            return _run_worker(
                configuration,
                arguments,
                arguments.config,
                stdout=stdout,
            )
        if arguments.command == "scheduler":
            return _run_scheduler(
                configuration,
                arguments,
                arguments.config,
                stdout=stdout,
            )
        if arguments.command == "api":
            _serve_api(configuration, arguments, stdout=stdout, stderr=stderr)
            return 0

        storages = configuration.create_storages()
        library = display_root = None
        if getattr(arguments, "path", None):
            library, display_root = _resource_library(configuration, arguments.path)
        providers = None
        if not (arguments.command == "analyze" and arguments.offline):
            providers = metadata_provider_registry_from_environment(("tmdb",))
        strategy = strategy_runner_from_configuration(
            configuration.strategy, providers, storages=storages
        )
        if arguments.command == "analyze":
            assert library is not None and display_root is not None
            result = strategy.run_path(
                str(Path(arguments.path).resolve(strict=False)),
                live_metadata=not arguments.offline,
                resource_library_id=library.library_id,
                storage_id=library.storage_id,
                storage_path=_storage_path(
                    library.root_path,
                    str(
                        Path(arguments.path)
                        .resolve(strict=False)
                        .relative_to(Path(display_root).resolve(strict=False))
                    ),
                ),
            )
            stdout.write(render_strategy_result(result))
            return 0
        with SQLiteTaskRepository(configuration.database_path) as repository:
            _attach_task_terminal_notifications(repository, arguments.config)
            operational_logger = (
                SQLiteOperationalLogger(
                    repository,
                    "workflow",
                    configuration.operational_logging_minimum_level,
                )
                if configuration.operational_logging_enabled
                else None
            )
            coordinator = PersistentTaskCoordinator(repository, repository)
            kernel_context = None
            # The independent ``tasks retry-failed`` entrance was retired (Slice
            # 47 RO-6): new organizing starts from Files/``organize`` and an
            # existing Task's own four-type continuation.  What remains here is
            # the ordinary direct organize workflow (analysis by default, an
            # explicitly authorized kernel execution with ``--execute``).
            execute = arguments.command == "organize" and arguments.execute
            if execute:
                # RO-2: a direct CLI organize execution is the same shared
                # Task work every other entrance runs.  The Task is admitted
                # through the scheduling kernel — capacity, pin, claim fence
                # and results included — and this process drives its own
                # execution under the live claim instead of a parallel
                # generic executor.
                task, scheduling = _admit_direct_organize_task(
                    repository,
                    configuration,
                    path=arguments.path,
                    limit=arguments.limit,
                )
                claim, direct_organize_worker_id = _drive_direct_organize_claim(
                    repository, scheduling, task
                )
                kernel_context = (scheduling, claim)
                coordinator = KernelTaskCoordinator(
                    repository,
                    repository,
                    scheduling,
                    claim,
                    heartbeat=lambda: (
                        scheduling.heartbeat(
                            claim,
                            now=datetime.now(UTC),
                            lease_seconds=900.0,
                        )
                        is not None
                    ),
                )
            else:
                task = coordinator.create(
                    arguments.command,
                    execute_authorized=execute,
                    scope_path=arguments.path,
                    item_limit=arguments.limit,
                    configuration_snapshot_id=configuration.configuration_snapshot_id,
                    configuration_snapshot_digest=configuration.configuration_snapshot_digest,
                    require_configuration_snapshot=(
                        configuration.configuration_authority == "MANAGED"
                    ),
                )
            if _task_observer is not None:
                # The durable Task identity is handed to the application caller
                # structurally.  Rendered CLI text remains the operator output
                # and is never parsed back into an identity.
                _task_observer(task.task_id)

            def workflow_stop() -> bool:
                return bool(
                    (cancellation_check and cancellation_check())
                    or coordinator.cancellation_observed(task.task_id)
                )

            # Not executing is the shared zero-mutation analysis: it records the
            # complete plan, attachments, conflicts and unready findings without
            # creating a formal execution backlog (WAITING_CONFIRM, review or
            # ConflictConfirmation) and without any execution authority.  A real
            # execute/recovery run keeps its original blocker responsibilities.
            analysis_only = not execute
            service = MediaOrganizerService(
                strategy,
                StorageScanner(storages, logger=operational_logger),
                storages,
                {item.library_id: item for item in configuration.media_libraries},
                configuration.strategy.recognition_type_policies,
                JsonLinesOperationHistoryRepository(configuration.history_path),
                executor=OrganizerExecutor(operational_logger),
                source_display_roots=dict(configuration.resource_display_roots),
                logger=operational_logger,
                task_coordinator=coordinator,
                task_id=task.task_id,
                conflict_decisions={},
                metadata_selections={},
                metadata_corrections={},
                classification_selections={},
                recognition_selections={},
                retry_policy=configuration.workflow_retry_policy,
                retry_cancellation_check=workflow_stop,
                analysis_only=analysis_only,
                # B46.3-05: only a run that may really consume a source asks the
                # shared durable ownership boundary.  A zero-mutation analysis
                # (``execute`` false) creates no organizing work, gains no
                # execution authority and mutates nothing, so it must stay
                # readable even while another work owns the file.
                enforce_source_ownership=execute,
            )
            # The CLI's own source scope must be read completely before any
            # file is processed: a root or subtree that cannot be enumerated
            # makes the admitted scope unproved, so the run settles as a Task
            # flow failure instead of executing a readable prefix or reporting
            # a healthy empty completion.  An explicit --limit keeps its
            # existing subset semantics; only unreadable/overflowed discovery
            # is a scope failure here.
            scope_failure = None
            try:
                if arguments.path is None:
                    summary = service.process_all_libraries(
                        configuration.resource_libraries,
                        execute=execute,
                        limit=arguments.limit,
                        progress=lambda done, total, source: stdout.write(
                            f"PROGRESS {done}/{total or '?'} {source}\n"
                        ),
                        cancellation_check=workflow_stop,
                        require_readable_scope=True,
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
                            cancellation_check=workflow_stop,
                            require_readable_scope=True,
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
            except IncompleteOrganizingScope as error:
                scope_failure = error
                summary = MediaOrganizerBatchResult((), error.errors, False)
            cancelled = bool(cancellation_check and cancellation_check())
            if kernel_context is not None:
                scheduling, claim = kernel_context
                state = scheduling.state(task.task_id)
                if cancelled and (state is None or state.control_request is None):
                    scheduling.request_control(task.task_id, TaskControl.CANCEL)
                    state = scheduling.state(task.task_id)
                if state is not None and state.control_request is not None:
                    # The operator's accepted control owns the outcome at this
                    # safe boundary: finished items keep their recorded results,
                    # the unfinished tail settles with the control.  This CLI
                    # pass has returned, so a recorded unknown outcome is
                    # history rather than a call still in flight; the shared
                    # kernel still refuses a missing Result or machine sibling.
                    scheduling.acknowledge_control(
                        claim,
                        now=datetime.now(UTC),
                        close_recorded_unknown_boundary=True,
                    )
                else:
                    _settle_direct_organize(
                        repository,
                        scheduling,
                        claim,
                        task,
                        batch=summary,
                        scope_failure=scope_failure,
                    )
            elif cancelled:
                coordinator.cancel(task.task_id)
            elif coordinator.cancellation_observed(task.task_id):
                # A durable cooperative cancellation already owns this Task
                # outcome; a late finish must not overwrite it.
                pass
            else:
                coordinator.finish(task.task_id, summary)
            stdout.write(f"Task ID: {task.task_id}\n")
            stdout.write(render_summary(summary, execute=execute, analysis_only=analysis_only))
            return 130 if cancelled else 1 if summary.failed else 0
    except (OSError, ValueError, LookupError, RuntimeError) as error:
        stderr.write(f"mediaflow error: {error}\n")
        return 2
    finally:
        if direct_organize_worker_id is not None:
            # The synchronous CLI only borrowed a transient Worker identity to
            # own its claimed Task.  Settle it with the run so no live temporary
            # Worker record survives a success or a bounded failure.
            try:
                with SQLiteTaskRepository(configuration.database_path) as cleanup_repository:
                    cleanup_repository.stop_worker(direct_organize_worker_id, datetime.now(UTC))
            except Exception:  # noqa: BLE001 - cleanup never masks the run's real result
                pass
        if runtime_lease is not None:
            runtime_lease.close()


def _runtime_lease_mode(arguments: argparse.Namespace) -> RuntimeLeaseMode | None:
    if arguments.command in {"config", "storage"}:
        return None
    if arguments.command == "api" and arguments.api_command in {"token", "credentials"}:
        return None
    if arguments.command == "database" and arguments.database_command == "restore":
        return RuntimeLeaseMode.EXCLUSIVE
    return RuntimeLeaseMode.SHARED


def render_summary(
    summary: MediaOrganizerBatchResult, *, execute: bool, analysis_only: bool = False
) -> str:
    lines = ["", "SUMMARY", "", f"Mode: {'EXECUTE' if execute else 'DRY_RUN'}"]
    for item in summary.items:
        if item.execution is not None:
            status = item.execution.status.value
        elif item.error:
            status = "FAILED"
        elif analysis_only:
            # The analysis ran to completion and recorded its finding: no
            # operator confirmation item exists for it, so the summary must not
            # claim NEED_CONFIRM/SKIPPED.
            status = "ANALYSIS"
        elif item.plan and item.plan.conflicts:
            status = "NEED_CONFIRM"
        else:
            status = "SKIPPED"
        details = []
        if item.plan and item.plan.attachment_plans:
            details.append(f"attachments={len(item.plan.attachment_plans)}")
        if item.plan and item.plan.conflicts:
            details.append(
                "findings=" + ",".join(sorted({value.type.value for value in item.plan.conflicts}))
            )
        if analysis_only and item.evidence is not None:
            details.append(f"outcome={item.evidence.outcome}")
            plan_section = item.evidence.section("plan")
            if plan_section.available and isinstance(plan_section.value, dict):
                next_action = plan_section.value.get("nextAction")
                if isinstance(next_action, str) and next_action:
                    details.append(f"next={next_action}")
            elif plan_section.unavailable_reason:
                details.append(f"next={plan_section.unavailable_reason}")
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


def render_tasks(tasks: tuple[PersistentTask, ...]) -> str:
    lines = ["", "TASKS", ""]
    for task in tasks:
        lines.append(
            f"{task.task_id} | {task.command} | {task.status.value} | "
            f"total={task.total_items} completed={task.completed_items} "
            f"failed={task.failed_items} | "
            f"snapshot={task.configuration_snapshot_id or '-'}"
        )
    lines.extend(("", f"Total: {len(tasks)}", ""))
    return "\n".join(lines)


def _active_runtime_for_browsing(active, database_path: str):
    """Resolve the exact Active revision into a runtime configuration for browsing.

    Only configuration is resolved: no Storage adapter is constructed here, and
    the database locator comes from the immutable bootstrap document, so this can
    never upgrade or create the store it just read.
    """

    from mediaflow.infrastructure.runtime_configuration import (
        load_managed_runtime_configuration,
        with_managed_snapshot,
    )

    runtime = load_managed_runtime_configuration(
        active.document, bootstrap_database_path=database_path
    )
    return with_managed_snapshot(
        runtime,
        snapshot_id=active.revision_id,
        digest=active.digest,
        version=active.revision_sequence,
    )


def _live_list_limit(value: object) -> int:
    if value is None:
        return 100
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise ValueError("files list --limit must be between 1 and 100")
    return value


def render_live_library_directory(document) -> str:
    """Render one bounded live library directory listing."""

    library_kind = str(document.get("libraryKind"))
    library_label = "ResourceLibrary" if library_kind == "resourceLibrary" else "MediaLibrary"
    library = document.get(
        "resourceLibrary" if library_kind == "resourceLibrary" else "mediaLibrary"
    )
    library = library if isinstance(library, dict) else {}
    entries = document.get("entries") or ()
    lines = [
        "",
        "LIVE DIRECTORY",
        "",
        f"Library kind: {library_label}",
        f"Library: {library.get('name') or '-'} ({library.get('id') or '-'})",
        f"Storage: {document.get('storageName') or '-'} ({document.get('storageId') or '-'})",
        f"Directory: {document.get('path') or '/'}",
        f"Revision: {document.get('revisionId') or '-'}",
        "",
        "NAME | TYPE | SIZE | MODIFIED",
        "",
    ]
    for entry in entries:
        lines.append(
            f"{entry.get('name')} | {entry.get('type')} | {entry.get('size')} | "
            f"{entry.get('modifiedAt')}"
        )
    if not entries:
        lines.append("None")
    lines.extend(
        (
            "",
            f"Returned: {len(entries)}",
            f"Limit: {document.get('limit')}",
            f"More available: {'yes' if document.get('hasNext') else 'no'}",
            f"Next cursor: {document.get('nextCursor') or '-'}",
            "Total: unknown (only the requested directory is read)",
            f"Side effects: {document.get('sideEffects', 'none')}",
            "",
        )
    )
    return "\n".join(lines)


def _render_live_library_directory(configuration, arguments) -> str:
    """Read one live library directory and render it for the operator.

    This is the CLI twin of the Web Files/MediaLibrary pages: it resolves the
    exact Active revision, binds the requested library and Storage, and lists the
    requested directory through the shared application browser.  It records
    nothing, creates no database, calls no Provider and mutates no media.
    """

    try:
        document = _live_library_directory_document(configuration, arguments)
    except StorageBrowserError as error:
        return "\n".join(
            (
                "",
                "LIVE DIRECTORY",
                "",
                f"Status: {error.code}",
                f"Reason: {error.message}",
                f"Durable state: {error.durable_state}",
                f"Side effects: {error.details['sideEffects']}",
                f"Repeatable: {'yes' if error.retry_safe else 'no'}",
                f"Next action: {error.next_action}",
                "",
            )
        )
    return render_live_library_directory(document)


def _live_library_directory_document(configuration, arguments) -> dict[str, object]:
    from mediaflow.application.storage_browser import RuntimeFilesBrowserService
    from mediaflow.domain.configuration_management import (
        STORAGE_BROWSER_CURSOR_KEY_NAME,
    )
    from mediaflow.infrastructure.internal_key_store import (
        InternalKeyUnavailable,
        read_internal_key_read_only,
    )
    from mediaflow.infrastructure.read_only_active_configuration import (
        ReadOnlyActiveRevisionSource,
        active_revision_failure_document,
        read_active_revision_read_only,
    )

    bootstrap_document = _configuration_document(arguments.config)
    database_path = _bootstrap_database_path(bootstrap_document)
    try:
        active = read_active_revision_read_only(database_path)
    except RuntimeSnapshotUnavailable as error:
        raise StorageBrowserError(
            f"files_list_{getattr(error, 'reason', 'active_unavailable')}",
            getattr(error, "reason", "active_unavailable"),
            str(error),
            status=409,
            next_action=str(
                active_revision_failure_document(error).get(
                    "nextAction",
                    "complete first setup in the Web Settings page and activate a revision",
                )
            ),
            durable_state="no configuration was created, changed or upgraded",
        ) from error
    if active is None:
        raise StorageBrowserError(
            "files_list_no_active",
            "no_active",
            "no Active configuration revision is published yet",
            status=409,
            next_action="complete first setup in the Web Settings page and activate a revision",
            durable_state="no configuration was created, changed or upgraded",
        )
    # Cursor continuation must stay verifiable across CLI/API processes, so the
    # authentication key is the one persisted in the managed store.  Reading it
    # here stays strictly read-only: a store that has not been initialized with
    # the key is refused explicitly instead of minting a one-off process key.
    try:
        cursor_key = read_internal_key_read_only(database_path, STORAGE_BROWSER_CURSOR_KEY_NAME)
    except InternalKeyUnavailable as error:
        raise StorageBrowserError(
            "files_list_internal_key_unavailable",
            getattr(error, "reason", "internal_key_unavailable"),
            str(error),
            status=409,
            next_action=(
                "complete supported initialization (for example the Web Settings or "
                "resident service startup) so the internal cursor key exists, then retry"
            ),
            durable_state="no configuration was created, changed or upgraded",
        ) from error
    if cursor_key is None:
        raise StorageBrowserError(
            "files_list_internal_key_unavailable",
            "internal_key_unavailable",
            "the internal cursor-authentication key has not been initialized in this store",
            status=409,
            next_action=(
                "complete supported initialization (for example the Web Settings or "
                "resident service startup) so the internal cursor key exists, then retry"
            ),
            durable_state="no configuration was created, changed or upgraded",
        )
    browser = RuntimeFilesBrowserService(
        ReadOnlyActiveRevisionSource(active),
        active_revision=active,
        runtime_configuration=_active_runtime_for_browsing(active, database_path),
        cursor_secret=cursor_key,
    )
    limit = _live_list_limit(arguments.limit)
    if arguments.resource_library is not None:
        document = browser.browse_resource_library(
            resource_library_id=arguments.resource_library,
            path=arguments.path,
            limit=limit,
            cursor=arguments.cursor,
        )
        document["libraryKind"] = "resourceLibrary"
    else:
        document = browser.browse_media_library(
            media_library_id=arguments.media_library,
            path=arguments.path,
            limit=limit,
            cursor=arguments.cursor,
        )
        document["libraryKind"] = "mediaLibrary"
    return document


def render_task(task: PersistentTask, items: tuple[PersistentTaskItem, ...]) -> str:
    lines = [
        "",
        "TASK",
        "",
        f"ID: {task.task_id}",
        f"Command: {task.command}",
        f"Status: {task.status.value}",
        f"Execute authorized: {'YES' if task.execute_authorized else 'NO'}",
        f"Configuration snapshot: {task.configuration_snapshot_id or '-'}",
        f"Configuration digest: {task.configuration_snapshot_digest or '-'}",
        f"Created: {task.created_at.isoformat()}",
        f"Ignored items: {sum(item.status is TaskItemStatus.IGNORED for item in items)}",
        "",
        "ITEMS",
        "",
    ]
    for item in items:
        detail = item.error or item.destination_path or ""
        # A persisted bounded failure is stored as a versioned envelope.  Decode
        # it so the operator reads the category, reason and next action instead
        # of an opaque token.
        explanation = decode_failure_explanation(item.error)
        if explanation is not None:
            detail = (
                f"{explanation.category}: {explanation.message} | Next: {explanation.next_action}"
            )
        lines.append(
            f"{item.status.value} | {item.storage_id}:{item.source_path} | "
            f"attempts={item.attempts} | {detail}"
        )
    lines.extend(("", f"Total: {len(items)}", ""))
    return "\n".join(lines)


def render_recovery_checkpoint(checkpoint) -> str:
    lines = [
        "",
        "TASK ITEM RECOVERY CHECKPOINT",
        "",
        f"Task: {checkpoint.task_id}",
        f"Item: {checkpoint.item_id}",
        f"Status: {checkpoint.status}",
        f"Stage: {checkpoint.stage.value}",
        f"Effect certainty: {checkpoint.effect_certainty.value}",
        f"Retry safety: {checkpoint.retry_safety.value}",
        f"Checkpoint version: {checkpoint.checkpoint_version}",
        f"Permitted actions: {', '.join(checkpoint.permitted_action_ids) or '-'}",
    ]
    request = checkpoint.active_recovery_request
    if request is not None:
        lines.extend(
            (
                "",
                "ADMITTED RECOVERY REQUEST",
                "",
                f"Request: {request.request_id}",
                f"Action: {request.action_id}",
                f"Actor: {request.actor}",
                f"Requested: {request.requested_at.isoformat()}",
                f"Bound checkpoint: {request.checkpoint_version}",
                f"Source: {request.source_storage_id}:{request.source_path}",
                f"Snapshot: {request.configuration_snapshot_id}",
                f"Next action: {request.next_action}",
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_manual_ignore(decision, task, items) -> str:
    return "\n".join(
        (
            "",
            "MANUAL IGNORE",
            "",
            f"Decision: {decision.decision_id}",
            f"Task: {decision.task_id}",
            f"Item: {decision.item_id}",
            f"Review kind: {decision.review_kind.value}",
            f"Review: {decision.review_id}",
            f"Actor: {decision.actor}",
            "Media mutation: 0",
            render_task(task, items),
        )
    )


def render_manual_ignore_batch(decisions) -> str:
    lines = [
        "",
        "BATCH MANUAL IGNORE",
        "",
        f"Ignored: {len(decisions)}",
        "Media mutation: 0",
        "",
        "DECISIONS",
        "",
    ]
    lines.extend(
        f"{item.decision_id} | {item.review_kind.value} | {item.task_id} | "
        f"{item.item_id} | {item.review_id} | {item.actor}"
        for item in decisions
    )
    lines.extend(("", f"Total: {len(decisions)}", ""))
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


def render_operational_logs(values) -> str:
    lines = ["", "OPERATIONAL LOGS", ""]
    for value in values:
        identifiers = ",".join(
            item for item in (value.task_id, value.plan_id, value.status) if item is not None
        )
        lines.append(
            f"{value.occurred_at.isoformat()} | {value.level.name} | {value.component} | "
            f"{value.event} | {identifiers or '-'}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_database_backup(value, operation: str) -> str:
    return "\n".join(
        (
            "",
            f"DATABASE {operation.upper()}",
            "",
            f"Path: {value.destination}",
            f"Schema: {value.schema_version}",
            f"Size: {value.size_bytes}",
            f"SHA-256: {value.sha256}",
            f"Checked: {value.created_at.isoformat()}",
            "",
        )
    )


def render_database_restore(value) -> str:
    return "\n".join(
        (
            "",
            "DATABASE RESTORE",
            "",
            "Status: RESTORED",
            f"Destination: {value.destination}",
            f"Schema: {value.schema_version}",
            f"Migration required: {'YES' if value.migration_required else 'NO'}",
            f"Size: {value.size_bytes}",
            f"SHA-256: {value.sha256}",
            f"Completed: {value.completed_at.isoformat()}",
            "",
        )
    )


def render_notification(value) -> str:
    return render_notifications((value,))


def render_security_audit(values) -> str:
    lines = ["", "SECURITY AUDIT", ""]
    lines.extend(
        f"{item.occurred_at.isoformat()} | {item.principal_id or '-'} | "
        f"{item.method} {item.route} | {item.action} | {item.outcome} | "
        f"status={item.http_status} | request={item.request_id}"
        for item in values
    )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


class _ConfiguredPermissionAuthority:
    """Read current configured principal roles without resolving credentials."""

    def __init__(self, configuration_provider: Callable[[], object]) -> None:
        self._configuration_provider = configuration_provider

    def has_permission(self, principal_id: str, permission: str | ApiPermission) -> bool:
        configuration = self._configuration_provider()
        definitions = tuple(getattr(configuration, "api_principals", ()))
        expected = permission.value if isinstance(permission, ApiPermission) else str(permission)
        for definition in definitions:
            if definition.principal_id != principal_id:
                continue
            return bool(
                definition.enabled
                and any(
                    item == permission or getattr(item, "value", str(item)) == expected
                    for item in definition.permissions
                )
            )
        return False


def _definition_scoped_service(
    task_repository,
    configuration: RuntimeConfiguration,
    configured_path: str | None,
) -> DefinitionScopedExecutionService:
    """Build the one automatic definition pipeline for a Task repository.

    Shared by the legacy Job handoff and the Task-kernel automatic runner so a
    Scheduler/Run once Task and a legacy queued Job execute through the exact
    same application engine, authorities and factories.
    """

    operational_logger = (
        SQLiteOperationalLogger(
            task_repository,
            "workflow",
            configuration.operational_logging_minimum_level,
        )
        if configuration.operational_logging_enabled
        else None
    )
    return DefinitionScopedExecutionService(
        task_repository,
        configuration,
        storage_factory=configuration.create_storages,
        provider_factory=metadata_provider_registry_from_environment,
        strategy_factory=strategy_runner_from_configuration,
        history_factory=JsonLinesOperationHistoryRepository,
        execution_authority=AutomationExecutionAuthority(
            task_repository,
            permission_authority=_ConfiguredPermissionAuthority(
                lambda: _configuration(configured_path)
            ),
            publication_principal_resolver=lambda job, definition: (
                _definition_publication_principal(configuration.database_path, job, definition)
            ),
            live_intent_checker=lambda job, definition: _schedule_intent_continuity(
                configuration.database_path, job, definition
            ),
            live_definition_resolver=lambda definition_id: _live_automation_definition(
                configuration.database_path, definition_id
            ),
        ),
        logger=operational_logger,
    )


def _scheduler_execution_authority(configuration, repository):
    """Build the live definition authority the Scheduler checks before admission."""

    return AutomationExecutionAuthority(
        repository,
        permission_authority=_ConfiguredPermissionAuthority(
            lambda: _current_automation_configuration(configuration.database_path)
        ),
        publication_principal_resolver=lambda task, definition: _definition_publication_principal(
            configuration.database_path, task, definition
        ),
        live_intent_checker=lambda task, definition: _schedule_intent_continuity(
            configuration.database_path, task, definition
        ),
        live_definition_resolver=lambda definition_id: _live_automation_definition(
            configuration.database_path, definition_id
        ),
    )


@contextmanager
def _automatic_continuation_context(repository, configured_path: str | None):
    """Open the zero-mutation continuation-analysis boundary for one pass.

    The continuation reuses the existing intent/Preview analysis machinery
    under the Task's admitted pin, so the automatic Task's saved decision
    produces the same durable plan summary a Files Task owns — without faking
    a Files submission and without a second engine.  The checkpoint service
    carries the same managed snapshot validator the confirmation path reads,
    so the summary's durable version fence is the one fence everywhere.
    """

    from mediaflow.application.automatic_task_continuation import (
        AutomaticTaskContinuationService,
    )
    from mediaflow.application.manual_organize import ManualOrganizeIntentService
    from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
    from mediaflow.application.processing_checkpoint import ProcessingCheckpointService

    bootstrap_document = _configuration_document(configured_path)
    database_path = _bootstrap_database_path(bootstrap_document)
    with SQLiteConfigurationRepository(database_path) as configuration_repository:
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=database_path,
            bootstrap_document=bootstrap_document,
        )
        intents = ManualOrganizeIntentService(
            repository,
            configuration_service,
            storage_factory=lambda runtime, ids: runtime.create_storages(storage_ids=set(ids)),
        )
        previews = ManualOrganizePreviewService(
            repository,
            intents,
            configuration_service=configuration_service,
            metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                metadata_provider_registry_from_environment
            ),
            storage_factory=lambda runtime, ids: runtime.create_storages(storage_ids=set(ids)),
        )
        yield AutomaticTaskContinuationService(
            repository,
            intent_service=intents,
            preview_service=previews,
            checkpoint_service=ProcessingCheckpointService(
                repository,
                snapshot_validator=configuration_service.validate_runtime_snapshot,
            ),
        )


def _admit_direct_organize_task(repository, configuration, *, path, limit):
    """Admit one direct CLI organize execution through the shared Task kernel.

    The admitted Task — not a parallel generic coordinator row — is the durable
    subject of the run: the same shared capacity, pin, claim fence and results
    every other organizing entrance uses.  Admission is atomic and
    capacity-checked; a full queue refuses the run before any work starts
    instead of queueing it invisibly.
    """

    from mediaflow.application.task_scheduling import (
        TaskSchedulingService,
        build_scheduled_task_admission,
    )
    from mediaflow.domain.task_persistence import RunDisplayContext
    from mediaflow.domain.task_scheduling import TaskQueueFull, TaskTrigger

    scheduling = TaskSchedulingService(
        repository,
        capacity=getattr(configuration, "automation_maximum_active_jobs", 100),
        locks=repository,
    )
    task, state = build_scheduled_task_admission(
        "organize",
        execute_authorized=True,
        trigger=TaskTrigger.MANUAL,
        principal="cli",
        scope_path=path,
        item_limit=limit,
        configuration_snapshot_id=configuration.configuration_snapshot_id,
        configuration_snapshot_digest=configuration.configuration_snapshot_digest,
        require_configuration_snapshot=(configuration.configuration_authority == "MANAGED"),
        now=datetime.now(UTC),
    )
    display = RunDisplayContext(
        source_scope=path,
        origin_kind="direct-organize",
    )
    try:
        admitted = repository.admit_scheduled_task(
            task,
            state,
            capacity=scheduling.capacity,
            display=display,
        )
    except TaskQueueFull as error:
        raise ValueError(
            "the shared organizing queue is full; no organize run was started"
        ) from error
    if admitted.duplicate:
        task, state = admitted.task, admitted.state
    return task, scheduling


def _drive_direct_organize_claim(
    repository, scheduling, task, *, lease_seconds=900.0, commands=("organize",)
):
    """Claim the admitted direct organize Task for this process' own execution.

    The claim is the same kernel boundary a resident Worker holds, so the
    synchronous CLI run publishes every item and Result under the live fence
    and can never write over a successor.  A bounded transient Worker
    registration carries the claim eligibility; it is stopped with the Task's
    own settlement.
    """

    from mediaflow.domain.task_scheduling import TaskWorkerRejected
    from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

    worker_id = f"direct-organize-{uuid4().hex[:12]}"
    repository.register_worker(
        worker_id,
        worker_id,
        lease_seconds,
        commands,
        None,
        None,
        SCHEMA_VERSION,
        datetime.now(UTC),
    )
    try:
        claim = scheduling.claim(
            task.task_id,
            worker_id=worker_id,
            now=datetime.now(UTC),
            lease_seconds=lease_seconds,
        )
    except BaseException:
        _stop_direct_organize_worker(repository, worker_id)
        raise
    if claim is None:
        _stop_direct_organize_worker(repository, worker_id)
        state = scheduling.state(task.task_id)
        owner = getattr(state, "claim_worker_id", None)
        if isinstance(owner, str) and owner and owner != worker_id:
            raise TaskWorkerRejected(
                f"the admitted organize Task {task.task_id} is already owned by Worker "
                f"{owner!r}; this process did not take or duplicate that work — inspect the "
                "Task's shared execution and result instead"
            )
        raise TaskWorkerRejected(
            f"the admitted organize Task {task.task_id} is not claimable in this run; "
            "inspect its queue state and pinned configuration"
        )
    try:
        claim = scheduling.begin_work(claim, now=datetime.now(UTC))
    except BaseException:
        # The claim is ours but the running boundary could not be published
        # (for example an already accepted control).  Settle that existing
        # control, or hand the claim back without changing operator intent;
        # never leave an owner that never runs.
        try:
            state = scheduling.state(task.task_id)
            if state is not None and state.control_request is not None:
                scheduling.acknowledge_control(claim, now=datetime.now(UTC))
            else:
                from mediaflow.domain.task_scheduling import TaskMachineStage

                scheduling.yield_claim(
                    claim,
                    task=claim.task,
                    stage=TaskMachineStage.DISCOVERY,
                    now=datetime.now(UTC),
                )
        except Exception:  # noqa: BLE001 - preserve the original failure
            pass
        _stop_direct_organize_worker(repository, worker_id)
        raise
    return claim, worker_id


def _stop_direct_organize_worker(repository, worker_id: str) -> None:
    """Best-effort cleanup of the CLI's transient Worker registration."""

    try:
        repository.stop_worker(worker_id, datetime.now(UTC))
    except Exception:  # noqa: BLE001 - cleanup never masks the run's real result
        pass


def _settle_direct_organize(repository, scheduling, claim, task, *, batch, scope_failure):
    """Settle one directly driven organize Task under its live claim.

    The flow outcome is the shared settlement rule over the facts this pass
    actually observed: the pass returned, a discovery failure may have left the
    admitted scope unproved, and durable items may still be waiting for the
    operator or real machine work.  File outcomes never become the flow status.
    An unproved source scope is a bounded Task flow failure — never a healthy
    empty completion — while a source still waiting for the operator returns the
    Task to human waiting with zero slots.
    """

    from mediaflow.domain.task_scheduling import TaskMachineStage

    now = datetime.now(UTC)
    items = repository.list_items(task.task_id)
    total, completed, failed = task_item_counts(items)
    waiting_statuses = {
        TaskItemStatus.WAITING_CONFIRM,
        TaskItemStatus.WAITING_RECOGNITION,
        TaskItemStatus.WAITING_METADATA,
        TaskItemStatus.WAITING_METADATA_CORRECTION,
        TaskItemStatus.WAITING_CLASSIFICATION,
    }
    waiting = tuple(item for item in items if item.status in waiting_statuses)
    machine = tuple(
        item
        for item in items
        if item.status not in SETTLED_ITEM_STATUSES and item.status not in waiting_statuses
    )
    failure = scope_failure.explanation() if scope_failure is not None else None
    if failure is None and batch.scan_errors:
        failure = incomplete_scope_failure(errors=batch.scan_errors)
    decision = settle_task_flow(
        TaskFlowSettlementInputs(
            ended_this_round=True,
            machine_work_remaining=bool(machine),
            human_decision_pending=bool(waiting),
            live_local_call=False,
            scope_proven_complete=failure is None,
            orchestration_error=failure,
            acknowledged_cancellation=False,
        )
    )
    updated = replace(
        task,
        updated_at=now,
        total_items=total,
        completed_items=completed,
        failed_items=failed,
        error=failure.encode() if failure is not None else None,
    )
    if decision.status is PersistentTaskStatus.FAILED:
        # The pass never proved the admitted scope; no file was processed and
        # the reason is durable, bounded and secret-free.  Release the slot
        # under the live owner fence like every other terminal settlement.
        failed_task = replace(updated, status=PersistentTaskStatus.FAILED, completed_at=now)
        scheduling.settle(
            claim,
            task=failed_task,
            items=items,
            now=now,
            close_recorded_unknown_boundary=True,
        )
        return
    if machine:
        # A still-processing sibling is genuine machine work; keep the slot and
        # let the next claim finish it instead of settling under a terminal
        # outcome this run does not own.
        running = replace(updated, status=PersistentTaskStatus.RUNNING, completed_at=None)
        scheduling.publish_task(claim, running, now=now)
        scheduling.yield_claim(
            claim,
            task=running,
            stage=TaskMachineStage.EXECUTION,
            now=now,
        )
        return
    if waiting:
        scheduling.publish_task(claim, updated, now=now)
        # Every source of this direct pass already recorded its own outcome or
        # is waiting for the operator; the process is done making calls, so a
        # recorded unknown effect no longer holds the shared slot.
        scheduling.defer_to_human(
            claim,
            task=updated,
            items=(),
            now=now,
            close_recorded_unknown_boundary=True,
        )
        return
    settled = replace(
        updated,
        status=PersistentTaskStatus.COMPLETED,
        completed_at=now,
    )
    # The direct CLI pass has returned and every durable item is terminal.  A
    # recorded unknown effect remains factual history; releasing its slot does
    # not rewrite the Result, its completed steps or the source protection.
    scheduling.settle(
        claim,
        task=settled,
        items=items,
        now=now,
        close_recorded_unknown_boundary=True,
    )


def _task_configuration_unavailable(
    error: RuntimeSnapshotUnavailable,
) -> AutomationConfigurationUnavailable:
    """Keep a corrupt admitted pin an actionable Task failure.

    The Task engine reports the durable failure; this conversion preserves the
    bounded category/effect/next-action vocabulary the Automation record and the
    operator's recovery surface already understand.  No Task, Provider, Storage
    or media effect is created here.
    """

    allowed_categories = {
        "active_missing",
        "active_unreadable",
        "digest_corrupt",
        "job_snapshot_incomplete",
        "job_snapshot_missing",
        "runtime_invalid",
        "schema_unsupported",
        "snapshot_digest_mismatch",
        "snapshot_missing",
        "snapshot_not_published",
        "snapshot_unreadable",
        "task_snapshot_incomplete",
        "task_snapshot_missing",
    }
    category = error.reason if error.reason in allowed_categories else "configuration_unavailable"
    return AutomationConfigurationUnavailable(
        AutomationFailureEvidence(
            category,
            "saved_configuration_unavailable",
            "none",
            False,
            "restore the saved published revision, or explicitly create new work under "
            "the current Active configuration",
        )
    )


def _pinned_task_configuration(configured_path: str | None, task):
    """Resolve one admitted Task's exact pin with actionable failure evidence."""

    try:
        return _configuration(
            configured_path,
            snapshot_id=task.configuration_snapshot_id,
            snapshot_digest=task.configuration_snapshot_digest,
        )
    except RuntimeSnapshotUnavailable as error:
        raise _task_configuration_unavailable(error) from error
    except (OSError, ValueError, LookupError) as error:
        raise AutomationConfigurationUnavailable(
            AutomationFailureEvidence(
                "snapshot_unreadable",
                "saved_configuration_unavailable",
                "none",
                False,
                "restore the saved published revision, or explicitly create new work under "
                "the current Active configuration",
            )
        ) from error


def _automatic_task_runner(repository, configured_path, scheduling_service):
    """Build the resident runner for one adopted Scheduler/Run once Task.

    It reconstructs the exact definition intent from the Task's admitted pin and
    its durable display origin, then runs the *same* definition-scoped pipeline
    the legacy Job handoff uses — under the Task's live claim fence and with the
    existing publication/authority continuity checks intact.  No Job row is
    written, no CLI text is parsed and no second engine is invoked.

    A Task that already owns durable TaskItems is a *continuation*: its saved
    four-type decision re-entered the same Task's zero-mutation analysis, so
    this runner advances that analysis instead of re-running the initial
    automatic intent.
    """

    def run(task, claim, clock=None, heartbeat=None) -> None:
        from mediaflow.domain.task_scheduling import TaskTrigger

        display = repository.get_run_display_context(task.task_id)
        if repository.list_items(task.task_id):
            # A continuation pass: the Task's own saved decisions re-entered its
            # zero-mutation analysis.  The pinned runtime is reconstructed from
            # the Task's admitted pin inside the continuation boundary.
            with _automatic_continuation_context(repository, configured_path) as continuation:
                continuation.run_pass(
                    task,
                    scheduling_service,
                    claim,
                    clock=clock,
                    heartbeat=heartbeat,
                )
            return
        if display is not None and display.origin_kind in {"remote-organize", "direct-organize"}:
            configuration = _pinned_task_configuration(configured_path, task)

            def direct_cancelled() -> bool:
                current = scheduling_service.state(task.task_id)
                return current is not None and current.control_request is not None

            service = _definition_scoped_service(repository, configuration, configured_path)
            service.run_direct_organize(
                task,
                scheduling_service,
                claim,
                cancellation_check=direct_cancelled,
                clock=clock,
                heartbeat=heartbeat,
            )
            return
        definition_id = display.origin_definition_id if display is not None else None
        if not isinstance(definition_id, str) or not definition_id.strip():
            raise RuntimeError("automatic Task has no durable definition origin")
        configuration = _pinned_task_configuration(configured_path, task)
        definition = next(
            (
                value
                for value in getattr(configuration, "automation_task_definitions", ())
                if getattr(value, "definition_id", getattr(value, "id", None)) == definition_id
            ),
            None,
        )
        if definition is None:
            raise RuntimeError("pinned Automation Task Definition is unavailable")
        state = scheduling_service.state(task.task_id)
        trigger = state.admission_trigger if state is not None else None
        run_once = trigger is TaskTrigger.RUN_ONCE

        def task_cancelled() -> bool:
            current = scheduling_service.state(task.task_id)
            return current is not None and current.control_request is not None

        service = _definition_scoped_service(repository, configuration, configured_path)
        service.run(
            task,
            scheduling_service,
            claim,
            run_once=run_once,
            cancellation_check=task_cancelled,
            clock=clock,
            heartbeat=heartbeat,
        )

    return run


def _definition_publication_principal(database_path, job, definition):
    from mediaflow.application.automation_execution_intent import resolve_principal

    with SQLiteConfigurationRepository(database_path) as repository:
        return resolve_principal(ManagedConfigurationService(repository), job, definition)


def _live_automation_definition(database_path, definition_id):
    from mediaflow.application.automation_execution_intent import live_definition

    with SQLiteConfigurationRepository(database_path) as repository:
        return live_definition(ManagedConfigurationService(repository), definition_id)


def _schedule_intent_continuity(database_path, job, definition):
    from mediaflow.application.automation_execution_intent import assert_schedule_continuity

    with SQLiteConfigurationRepository(database_path) as repository:
        assert_schedule_continuity(ManagedConfigurationService(repository), job, definition)


def _current_automation_configuration(database_path):
    """Read current permissions from the same managed authority as the Job queue."""
    with SQLiteConfigurationRepository(database_path) as repository:
        managed = ManagedConfigurationService(repository)
        active = managed.active()
        if active is None:
            raise RuntimeError("current Active is unavailable")
        managed.verify_integrity(active)
        return load_managed_runtime_configuration(
            active.document, bootstrap_database_path=str(database_path)
        )


def _resident_infrastructure_defaults() -> tuple[float, float, float]:
    """Bounded polling defaults used before any Active configuration exists.

    These are *infrastructure* settings, not business objects: a resident
    service needs a heartbeat cadence and a poll cadence to stay alive and stay
    observable during first setup, long before an operator has configured
    anything.  They are intentionally conservative, so the absence of Active
    changes only how often a resident process re-reads the current Active and
    never what it is allowed to do.
    """

    return (300.0, 5.0, 5.0)


class ResidentConfigurationUnavailable(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__("resident configuration is unavailable; restore the named prerequisite")
        self.reason = reason


def _resolve_resident_configuration(configured_path: str | None) -> RuntimeConfiguration | None:
    import sqlite3

    try:
        configuration = _configuration(configured_path)
    except sqlite3.Error as error:
        raise ResidentConfigurationUnavailable("database_unavailable") from error
    except RuntimeSnapshotUnavailable as error:
        reason = (
            "schema_unsupported"
            if error.reason == "schema_unsupported"
            else "configuration_unavailable"
        )
        raise ResidentConfigurationUnavailable(reason) from error
    except Exception as error:
        raise ResidentConfigurationUnavailable("configuration_unavailable") from error
    if isinstance(configuration, ManagementBootstrapConfiguration):
        return None
    return configuration


def _current_runtime_configuration(configured_path: str | None) -> RuntimeConfiguration | None:
    try:
        return _resolve_resident_configuration(configured_path)
    except ResidentConfigurationUnavailable:
        return None


def _resident_failure_reason(error: BaseException) -> tuple[str, str]:
    if isinstance(error, ResidentConfigurationUnavailable):
        return error.reason, str(error)
    return (
        "configuration_unavailable",
        "service work is blocked; inspect configuration and durable work",
    )


def _current_managed_runtime_configuration(
    configured_path: str | None,
) -> RuntimeConfiguration | None:
    """Return the current **managed** Active runtime, or ``None``.

    This is the stricter resolution used by boundaries that must pin their work
    to published authority — the Scheduler's occurrence emission and the
    Notification Worker's target resolution.  A legacy JSON bootstrap has no
    snapshot identity, so it yields ``None`` here and those boundaries wait,
    which is correct: a resident process must never issue unpinned work in a
    deployment that has adopted managed configuration authority.
    """

    try:
        configuration = _configuration(configured_path)
    except Exception:
        return None
    if not getattr(configuration, "configuration_snapshot_id", None):
        return None
    return configuration


def _scheduler_waiting_reason(configuration: RuntimeConfiguration | None) -> tuple[str, str]:
    """Map a missing or unusable Active onto one bounded Scheduler waiting state."""

    if configuration is None:
        return (
            ResidentServiceWaiting.UNCONFIGURED.value,
            "no valid Active configuration is published; no schedule was issued",
        )
    if not configuration.automation_task_definitions:
        return (
            ResidentServiceWaiting.UNCONFIGURED.value,
            "the Active configuration declares no Automation Task Definition",
        )
    return (ResidentServiceWaiting.NONE.value, "")


def _resident_published_cadence_resolver(
    configured_path: str | None, field: str
) -> Callable[[], tuple[str, int | None, str, float] | None]:
    """Resolve the current publication identity plus one consumed poll cadence.

    Only managed Active authority is used, so a JSON compatibility bootstrap
    never becomes a published target for these engine settings.  The resolver is
    called at each safe loop boundary, which is what makes adoption independent
    of process start time and of work arriving.
    """

    def resolve() -> tuple[str, int | None, str, float] | None:
        try:
            document = _configuration_document(configured_path)
            database_path = _bootstrap_database_path(document)
            with SQLiteConfigurationRepository(database_path) as repository:
                active = repository.get_active_revision()
        except Exception:
            # A transient database/configuration fault yields no candidate: the
            # loop keeps the last known-good cadence rather than installing one
            # it cannot attribute to a publication.
            return None
        if active is None:
            return None
        values = engine_values_from_document(active.document)
        if values is None:
            return None
        cadence = values.worker_poll_seconds if field == "worker" else values.scheduler_poll_seconds
        return (
            active.revision_id,
            active.revision_sequence or active.version,
            active.digest,
            float(cadence),
        )

    return resolve


def _resident_snapshot_reference(path: str | None) -> tuple[str, str] | None:
    try:
        return _managed_snapshot_reference(path)
    except Exception:
        return None


def _run_worker(
    configuration,
    arguments,
    configured_path: str | None,
    *,
    stdout: TextIO,
) -> int:
    """Run the resident MediaFlow Worker from deployment-owned authority alone.

    The Worker already supported management-only bootstrap; this adds the two
    things the empty-setup boundary needs on top of it:

    * a **durable resident registration** that makes "the real Worker process is
      running" observable independently of the command families it happens to
      be serving right now, so an API/Compose readiness answer is not inferred
      from a static configuration file; and
    * a **bounded waiting reason** whenever the Worker is alive but has nothing
      lawful to consume, which is the normal state before first activation and
      again whenever the current Active is unusable.

    The existing per-command consumers are preserved untouched: queued Jobs
    still load their own pinned revision after the claim boundary, admitted
    manual Organize executions and both library-kind transfers still
    reconstruct their own immutable pin. Invalid pins are handled by those
    consumers' existing durable failure and recovery rules before mutation.
    """

    from mediaflow.application.resident_runtime import (
        ResidentLoop,
        build_resident_runtime,
        register_resident_process,
        resident_cadence_adoption,
        resident_instance_id,
    )

    _, default_poll, _ = _resident_infrastructure_defaults()
    runtime = build_resident_runtime(configuration.database_path)
    worker_snapshot = _resident_snapshot_reference(configured_path)
    instance_id = resident_instance_id("worker")
    resident_id = worker_snapshot[0] if worker_snapshot is not None else None

    with SQLiteTaskRepository(configuration.database_path) as repository:
        _attach_task_terminal_notifications(repository, configured_path)

        def pending_snapshot() -> tuple[str | None, str | None]:
            # Select a pending pin before registering; the repository still claims
            # only the exact registered pin, and the handler validates publication,
            # digest, schema and current execution authority before any effect.
            # A Task-admitted run owns its pin, so an older queued Task is just as
            # legitimate as a legacy Job and must not be hidden behind today's
            # (possibly unhealthy) Active revision.
            from mediaflow.domain.task_scheduling import TaskQueueState

            with repository._lock:
                row = repository._connection.execute(
                    "SELECT tasks.configuration_snapshot_id, "
                    "tasks.configuration_snapshot_digest "
                    "FROM task_scheduling JOIN tasks "
                    "ON tasks.task_id=task_scheduling.task_id "
                    "WHERE task_scheduling.queue_state IN (?, ?) "
                    "AND tasks.status='pending' "
                    "ORDER BY COALESCE(task_scheduling.queue_eligible_at, "
                    "task_scheduling.created_at), task_scheduling.created_at, "
                    "task_scheduling.task_id LIMIT 1",
                    (TaskQueueState.QUEUED.value, TaskQueueState.CLAIMED.value),
                ).fetchone()
            if row is not None:
                return row["configuration_snapshot_id"], row["configuration_snapshot_digest"]
            try:
                return _managed_snapshot_reference(configured_path) or (None, None)
            except Exception:
                # Current Active does not authorize previously admitted transfers;
                # their independent consumers reconstruct their own durable pins.
                return (None, None)

        with _media_discovery_service_context(
            configuration, configured_path, repository
        ) as discovery_service:
            with _manual_organize_service_context(
                configuration, configured_path, repository
            ) as execution_service:
                with _files_transfer_worker_context(
                    configuration, configured_path, repository
                ) as files_transfer_worker:
                    register_resident_process(
                        runtime,
                        "worker",
                        instance_id,
                        heartbeat_interval_seconds=5.0,
                        snapshot_id=resident_id,
                    )
                    # The resident Worker records its own presence through the same
                    # heartbeat the resident registry reads, so a slow provider call
                    # or a long claim never makes the deployment look stopped.
                    worker_service = ResidentProcessingWorker(
                        repository,
                        configuration_snapshot_resolver=pending_snapshot,
                        runtime_schema_version=SCHEMA_VERSION,
                        files_transfer_worker=files_transfer_worker,
                    )
                    from mediaflow.application.manual_task_engine import (
                        ManualTaskEngineWorker,
                    )
                    from mediaflow.application.task_scheduling import TaskSchedulingService

                    def current_scheduling_capacity() -> int:
                        # The resident Worker re-resolves the published allowance
                        # for each admission/re-entry, so a new System Settings
                        # value applies to new work without a restart.
                        resolved = _resolve_resident_configuration(configured_path)
                        return getattr(
                            resolved or configuration,
                            "automation_maximum_active_jobs",
                            100,
                        )

                    scheduling_service = TaskSchedulingService(
                        repository,
                        capacity=current_scheduling_capacity,
                        locks=repository,
                    )
                    manual_task_worker = ManualTaskEngineWorker(
                        repository,
                        scheduling_service,
                        discovery_service,
                        execution_service,
                        worker_id=worker_service.worker_id,
                    )
                    manual_task_worker.set_automatic_runner(
                        _automatic_task_runner(repository, configured_path, scheduling_service)
                    )
                    worker_service.set_manual_task_worker(manual_task_worker)
                    if arguments.worker_command == "run-next":
                        result = worker_service.run_next()
                        if result is None:
                            stdout.write("No pending work\n")
                            return 0
                        if hasattr(result, "task_id") and hasattr(result, "status"):
                            status = getattr(result.status, "value", str(result.status))
                            stdout.write(f"Task ID: {result.task_id}\nStatus: {status}\n")
                            return 0 if status in {"completed", "cancelled"} else 1
                        stdout.write("No pending work\n")
                        return 0
                    poll = getattr(arguments, "poll_seconds", None) or getattr(
                        configuration, "worker_poll_seconds", default_poll
                    )
                    # Engine settings adoption: the Worker consumes
                    # ``automation.workerPollSeconds``.  An explicit
                    # ``--poll-seconds`` retains precedence and is reported as an
                    # override, never as adoption of the published value.
                    cadence_resolver, cadence_reporter = resident_cadence_adoption(
                        runtime,
                        "worker",
                        instance_id,
                        field_path="automation.workerPollSeconds",
                        published_resolver=_resident_published_cadence_resolver(
                            configured_path, "worker"
                        ),
                        override_poll_seconds=getattr(arguments, "poll_seconds", None),
                        override_source="cli",
                    )
                    cadence_adoption = {
                        "cadence_resolver": cadence_resolver,
                        "adoption_reporter": cadence_reporter,
                    }
                    original_heartbeat = worker_service.heartbeat

                    def heartbeat(now=None) -> bool:
                        kept = original_heartbeat(now)
                        _resident_worker_heartbeat(runtime, instance_id)
                        return kept

                    worker_service.heartbeat = heartbeat
                    files_transfer_worker.set_worker_heartbeat(heartbeat)
                    # Every other runner sharing this loop keeps the same
                    # wrapped liveness evidence (processing-Worker row plus
                    # resident-presence row) fresh across its own long
                    # claim, exactly like the Files transfer consumer.
                    manual_task_worker.set_worker_heartbeat(heartbeat)

                    def step(loop: ResidentLoop) -> int:
                        # A fresh consumer owns no registration row yet, so a
                        # heartbeat can only fail before the first lawful
                        # registration.  Register through the same snapshot
                        # resolver/supported-command boundary first; otherwise a
                        # newly started Worker would wait forever and never
                        # reach the consumer that claims admitted work.
                        if not worker_service.registered:
                            worker_service.ensure_registration()
                        if not worker_service.heartbeat():
                            raise RuntimeError("worker registration unavailable")
                        worked = worker_service.run_next() is not None
                        if worked:
                            loop.clear_waiting()
                        else:
                            current = _resolve_resident_configuration(configured_path)
                            if current is None:
                                loop.note(
                                    "unconfigured",
                                    "waiting for published business configuration",
                                )
                            else:
                                loop.clear_waiting()
                        return int(worked)

                    loop = ResidentLoop(
                        runtime,
                        "worker",
                        instance_id,
                        heartbeat_interval_seconds=5.0,
                        poll_seconds=poll,
                        stdout=stdout,
                        step=step,
                        describe=_resident_failure_reason,
                        **cadence_adoption,
                    )
                    try:
                        processed = _run_resident(
                            lambda stop: loop.run(stop, lambda seconds: _wait(stop, seconds))
                        )
                    finally:
                        try:
                            worker_service.stop()
                        except Exception:
                            pass
                    stdout.write(f"Worker stopped; processed={processed}\n")
                    return 0


def _resident_worker_heartbeat(runtime, instance_id) -> None:
    """Refresh the resident presence row, tolerating a transient database fault."""

    try:
        runtime.service.heartbeat(instance_id)
    except Exception:
        return


def _worker_notification_publisher(
    repository, configured_path: str | None
) -> NotificationPublisher:
    """Publish settled Task outcomes to the current Active Webhooks.

    The target set is resolved per publication rather than at process start, so
    a Task that settles after a later publication notifies the Webhooks that are
    actually configured then.  Only the durable outbox write happens here; an
    unavailable configuration or a missing secret never fails the Task, and the
    resident Notification Worker remains responsible for signed delivery.
    """

    def webhooks():
        resolved = _current_runtime_configuration(configured_path)
        return getattr(resolved, "webhooks", ()) if resolved else ()

    return NotificationPublisher(repository, webhooks)


def _attach_task_terminal_notifications(repository, configured_path: str | None) -> None:
    """Publish one terminal Task event at its durable result boundary.

    A Task's terminal outcome is committed by the scheduling kernel, so this
    post-commit observer is the same place for Worker, direct CLI and API
    settlements.  A repository without the seam (a focused unit test double)
    simply publishes nothing.
    """

    attach = getattr(repository, "add_task_terminal_observer", None)
    if not callable(attach):
        return
    attach(task_terminal_observer(_worker_notification_publisher(repository, configured_path)))


def _run_scheduler(
    configuration,
    arguments,
    configured_path: str | None,
    *,
    stdout: TextIO,
) -> int:
    """Run the resident Scheduler from deployment-owned authority alone.

    The Scheduler owns exactly one job: decide whether an eligible occurrence
    is due *right now* and, if so, issue it pinned to the current valid Active
    snapshot.  Everything else is configuration state, so this process needs no
    business configuration at all to start.

    Its correctness properties are preserved rather than reimplemented:
    ``IntervalScheduler`` remains the single authority for occurrence identity,
    idempotency, scope, capacity and duplicate protection, and the existing
    configuration-resolver seam is what lets it re-read the current Active on
    every tick instead of binding to whatever existed at startup.
    """

    from mediaflow.application.resident_runtime import (
        ResidentLoop,
        build_resident_runtime,
        register_resident_process,
        resident_cadence_adoption,
        resident_instance_id,
    )

    heartbeat_seconds, default_poll, _ = _resident_infrastructure_defaults()
    runtime = build_resident_runtime(configuration.database_path)
    snapshot = _resident_snapshot_reference(configured_path)
    instance_id = resident_instance_id("scheduler")

    current = _current_runtime_configuration(configured_path)
    # Only the resident ``run`` loop accepts a poll override; the one-shot
    # inspection commands always use the configured (or bounded default) cadence.
    poll = getattr(arguments, "poll_seconds", None) or (
        current.scheduler_poll_seconds if current is not None else default_poll
    )
    maximum_active_jobs = current.automation_maximum_active_jobs if current is not None else 100

    with SQLiteTaskRepository(configuration.database_path) as repository:

        def build_service(resolved: RuntimeConfiguration | None) -> IntervalScheduler:
            """Build one scheduler bound to the exact configuration it admits from.

            When no valid Active exists the scheduler still runs, but with no
            definitions and no snapshot identity.  That makes "emit nothing"
            the only reachable outcome, which is precisely the required
            behaviour when Active is absent or unusable.
            """

            from mediaflow.application.task_scheduling import TaskSchedulingService

            return IntervalScheduler(
                repository,
                # Notification targets are resolved by the resident Notification
                # Worker at its own claim boundary.  The Scheduler only writes
                # deterministic durable deliveries for enabled Webhooks, so an
                # unavailable secret must never stop it emitting a due
                # occurrence.
                NotificationPublisher(
                    repository, getattr(resolved, "webhooks", ()) if resolved else ()
                ),
                execution_authority=_scheduler_execution_authority(
                    resolved or configuration, repository
                ),
                maximum_active_jobs=(
                    getattr(resolved, "automation_maximum_active_jobs", maximum_active_jobs)
                    if resolved
                    else maximum_active_jobs
                ),
                scheduling_service=TaskSchedulingService(
                    repository,
                    capacity=(
                        getattr(resolved, "automation_maximum_active_jobs", maximum_active_jobs)
                        if resolved
                        else maximum_active_jobs
                    ),
                    locks=repository,
                ),
                configuration_snapshot_id=(
                    getattr(resolved, "configuration_snapshot_id", None) if resolved else None
                ),
                configuration_snapshot_digest=(
                    getattr(resolved, "configuration_snapshot_digest", None) if resolved else None
                ),
                automation_task_definitions=(
                    getattr(resolved, "automation_task_definitions", ()) if resolved else ()
                ),
                configuration_snapshot_version=(
                    getattr(resolved, "configuration_snapshot_version", None) if resolved else None
                ),
                configuration_snapshot_resolver=lambda: _scheduler_snapshot_from_runtime(resolved),
            )

        register_resident_process(
            runtime,
            "scheduler",
            instance_id,
            heartbeat_interval_seconds=5.0,
            snapshot_id=snapshot[0] if snapshot is not None else None,
        )
        if arguments.scheduler_command == "tick":
            stdout.write(render_tasks(tuple(build_service(current).tick())))
            return 0

        def step(loop: ResidentLoop) -> int:
            """Re-resolve the current Active, then tick under that exact identity.

            Re-resolving per tick is what makes a running Scheduler adopt an
            eligible publication with no restart, and what keeps it from reusing
            stale definitions while Active is unavailable: a failed resolution
            yields no definitions and no pin, so no occurrence is issued or
            advanced.
            """

            resolved = _resolve_resident_configuration(configured_path)
            reason, detail = _scheduler_waiting_reason(resolved)
            loop.note(reason, detail)
            if resolved is None:
                return 0
            return len(build_service(resolved).tick())

        # Engine settings adoption: the Scheduler consumes
        # ``automation.schedulerPollSeconds`` as its due-check cadence.  Schedule
        # resolution stays separate — a poll change never alters a definition's
        # interval, Cron expression or timezone.
        cadence_resolver, cadence_reporter = resident_cadence_adoption(
            runtime,
            "scheduler",
            instance_id,
            field_path="automation.schedulerPollSeconds",
            published_resolver=_resident_published_cadence_resolver(configured_path, "scheduler"),
            override_poll_seconds=getattr(arguments, "poll_seconds", None),
            override_source="cli",
        )
        loop = ResidentLoop(
            runtime,
            "scheduler",
            instance_id,
            heartbeat_interval_seconds=5.0,
            poll_seconds=poll,
            stdout=stdout,
            step=step,
            describe=_resident_failure_reason,
            cadence_resolver=cadence_resolver,
            adoption_reporter=cadence_reporter,
        )
        emitted = _run_resident(lambda stop: loop.run(stop, lambda seconds: _wait(stop, seconds)))
        stdout.write(f"Scheduler stopped; emitted={emitted}\n")
        return 0


def _run_notification_worker(
    configuration,
    arguments,
    configured_path: str | None,
    *,
    stdout: TextIO,
) -> int:
    """Run the resident Notification Worker from deployment-owned authority.

    The worker resolves its delivery configuration at every claim, so it can
    start before any Webhook exists and adopt a later valid publication without
    a restart, while still refusing to claim a delivery whose durable target it
    cannot lawfully deliver to.
    """

    from mediaflow.application.resident_runtime import (
        ResidentLoop,
        build_resident_runtime,
        register_resident_process,
        resident_instance_id,
    )
    from mediaflow.infrastructure.webhook import UrllibWebhookTransport

    _, default_poll, _ = _resident_infrastructure_defaults()
    runtime = build_resident_runtime(configuration.database_path)
    snapshot = _resident_snapshot_reference(configured_path)
    instance_id = resident_instance_id("notification-worker")

    current = _current_runtime_configuration(configured_path)
    # Only the resident ``run`` loop accepts a poll override; ``run-next`` always
    # uses the configured (or bounded default) cadence.
    poll = getattr(arguments, "poll_seconds", None) or (
        current.notification_poll_seconds if current is not None else default_poll
    )
    lease = (
        current.notification_delivery_lease_seconds
        if current is not None
        else _resident_infrastructure_defaults()[0]
    )

    def resolve_targets() -> dict:
        """Resolve the current valid deliverable targets, or fail closed.

        A missing secret is deliberately a resolution failure rather than a
        silently skipped target: a delivery must never be claimed against a
        target whose signing secret is absent, because the request could not be
        signed and reporting success afterwards would be false.
        """

        resolved = _resolve_resident_configuration(configured_path)
        if resolved is None:
            return {}
        try:
            return resolved.resolve_webhook_targets()
        except ValueError as error:
            raise ResidentConfigurationUnavailable("secret_unavailable") from error

    with SQLiteTaskRepository(configuration.database_path) as repository:
        delivery_worker = NotificationWorker(
            repository,
            resolve_targets,
            UrllibWebhookTransport(),
            delivery_lease_seconds=lease,
        )
        register_resident_process(
            runtime,
            "notification-worker",
            instance_id,
            heartbeat_interval_seconds=5.0,
            snapshot_id=snapshot[0] if snapshot is not None else None,
        )
        if arguments.notification_worker_command == "run-next":
            try:
                delivery = delivery_worker.run_next()
            except ResidentConfigurationUnavailable as error:
                # Waiting is a normal resident outcome, not a failed run: the
                # durable delivery is untouched and stays claimable.
                stdout.write(f"Notification worker is waiting: {error}\n")
                return 0
            if delivery is None:
                stdout.write("Notification worker waiting: no due deliverable notifications\n")
                return 0
            stdout.write(render_notification(delivery))
            return 0 if delivery.status.value in {"delivered", "retry"} else 1

        def step(loop: ResidentLoop) -> int:
            try:
                targets = delivery_worker.resolve_targets()
            except ResidentConfigurationUnavailable as error:
                loop.note(error.reason, str(error))
                return 0
            if not targets:
                loop.note(
                    ResidentServiceWaiting.UNCONFIGURED.value,
                    "the Active configuration declares no enabled Webhook target",
                )
                return 0
            loop.clear_waiting()
            return 0 if delivery_worker.run_next() is None else 1

        loop = ResidentLoop(
            runtime,
            "notification-worker",
            instance_id,
            heartbeat_interval_seconds=5.0,
            poll_seconds=poll,
            stdout=stdout,
            step=step,
            describe=_resident_failure_reason,
        )
        processed = _run_resident(lambda stop: loop.run(stop, lambda seconds: _wait(stop, seconds)))
        stdout.write(f"Notification worker stopped; processed={processed}\n")
        return 0


def _api_resident_heartbeat(runtime, instance_id: str):
    """Keep the API's own resident registration fresh while it serves.

    The API has no work loop, so it refreshes its heartbeat on a timer in a
    daemon thread.  A heartbeat fault is swallowed on purpose: the API must stay
    reachable for configuration recovery even when the shared database is
    briefly unhappy, and a later beat repairs the state.  Killing the API would
    achieve nothing and lose the recovery surface entirely.
    """

    class _Heartbeat:
        def __init__(self) -> None:
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, daemon=True)

        def _run(self) -> None:
            while not self._stop.wait(5.0):
                try:
                    runtime.service.heartbeat(instance_id)
                except Exception:
                    continue

        def start(self):
            self._thread.start()
            return self

        def stop(self) -> None:
            self._stop.set()
            self._thread.join(timeout=6.0)

    return _Heartbeat()


def _serve_api(configuration, arguments, *, stdout: TextIO, stderr: TextIO) -> None:
    """Build and serve the shared WSGI application.

    ``api serve`` remains the standard-library development/trusted-loopback
    listener.  ``api serve-production`` deliberately selects the declared
    Waitress adapter and is the command used by the Compose API service.
    """

    production = getattr(arguments, "api_command", None) == "serve-production"
    _validate_api_bind_host(arguments.host)
    if not 1 <= arguments.port <= 65535:
        raise ValueError("API port must be between 1 and 65535")
    if production:
        if (
            isinstance(arguments.threads, bool)
            or not isinstance(arguments.threads, int)
            or not 1 <= arguments.threads <= 64
        ):
            raise ValueError("production WSGI threads must be between 1 and 64")
        stderr.write(
            "WARNING: production WSGI serves HTTP without TLS; bind the container port "
            "to a trusted LAN or HTTPS reverse proxy\n"
        )
        from mediaflow.production_wsgi import serve as run_server
    else:
        loopback = _validate_api_bind_host(arguments.host)
        if not loopback and not arguments.allow_insecure_remote_http:
            raise ValueError(
                "non-loopback API bind requires --allow-insecure-remote-http; "
                "the development server does not provide TLS"
            )
        if not loopback:
            stderr.write(
                "WARNING: serving authenticated traffic over unencrypted non-loopback HTTP; "
                "use a trusted TLS reverse proxy\n"
            )
        from wsgiref.simple_server import make_server

    principals = configuration.resolve_api_principals()
    bootstrap_document = _configuration_document(arguments.config)
    from mediaflow.infrastructure.configuration_snapshot import (
        build_configuration_snapshot,
    )
    from mediaflow.interfaces.service_api import MediaFlowApi

    management_only = isinstance(configuration, ManagementBootstrapConfiguration)
    # The API registers its own durable presence for the same reason the other
    # three services do: "the process is running" must be an observed fact, not
    # an inference from a static configuration file.  This changes nothing
    # about the API's request behavior — it is the only thing it writes outside
    # its existing request handling, and it never supervises a subprocess.
    from mediaflow.application.resident_runtime import (
        build_resident_runtime,
        register_resident_process,
        resident_instance_id,
    )

    runtime = build_resident_runtime(configuration.database_path)
    active_reference = _managed_snapshot_reference(arguments.config)
    instance_id = resident_instance_id("api")
    with (
        SQLiteTaskRepository(configuration.database_path) as repository,
        SQLiteConfigurationRepository(configuration.database_path) as configuration_repository,
    ):
        register_resident_process(
            runtime,
            "api",
            instance_id,
            heartbeat_interval_seconds=5.0,
            snapshot_id=active_reference[0] if active_reference is not None else None,
        )
        resident_services = ResidentServiceService(
            repository, runtime_schema_version=SCHEMA_VERSION
        )
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=configuration.database_path,
            bootstrap_document=bootstrap_document,
            management_only=management_only,
        )
        app = MediaFlowApi(
            repository,
            principals=principals,
            maximum_active_jobs=getattr(configuration, "automation_maximum_active_jobs", 100),
            system_status=(
                None if management_only else build_configuration_snapshot(configuration)
            ),
            metadata_policies=getattr(
                getattr(configuration, "strategy", None), "metadata_policies", ()
            ),
            configuration_service=configuration_service,
            configuration_snapshot_id=getattr(configuration, "configuration_snapshot_id", None),
            configuration_snapshot_digest=getattr(
                configuration, "configuration_snapshot_digest", None
            ),
            bootstrap_document=bootstrap_document,
            management_only=management_only,
            metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                metadata_provider_registry_from_environment
            ),
            resident_services=resident_services,
        )
        stdout.write(
            f"MediaFlow {'production ' if production else ''}API listening on "
            f"{arguments.host}:{arguments.port}\n"
        )
        stdout.flush()
        heartbeat = _api_resident_heartbeat(runtime, instance_id)
        heartbeat.start()
        try:
            if production:
                run_server(
                    app,
                    host=arguments.host,
                    port=arguments.port,
                    threads=arguments.threads,
                )
            else:
                with make_server(arguments.host, arguments.port, app) as server:
                    server.serve_forever()
        finally:
            heartbeat.stop()
            runtime.service.stop(instance_id)


@contextmanager
def _manual_organize_service_context(configuration, configured_path: str | None, repository):
    """Yield the Task engine's admitted-manual-Organize application service.

    The service reconstructs the reviewed Preview, the pinned runtime snapshot
    and the required Storage adapters from durable state, so it never shares
    in-memory authority with the API request that admitted the work.  Every
    runtime resource it opens is closed with the surrounding Worker lifetime.
    """

    bootstrap_document = _configuration_document(configured_path)
    management_only = isinstance(configuration, ManagementBootstrapConfiguration)
    with SQLiteConfigurationRepository(configuration.database_path) as configuration_repository:
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=configuration.database_path,
            bootstrap_document=bootstrap_document,
            management_only=management_only,
        )
        intents = ManualOrganizeIntentService(repository, configuration_service)
        previews = ManualOrganizePreviewService(
            repository,
            intents,
            configuration_service=configuration_service,
            metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                metadata_provider_registry_from_environment
            ),
        )
        execution = ManualOrganizeExecutionService(
            repository,
            previews,
            intents,
            checkpoint_service=ProcessingCheckpointService(repository),
        )
        yield execution


@contextmanager
def _media_discovery_service_context(configuration, configured_path: str | None, repository):
    """Yield the Task engine's admitted bounded-discovery application service.

    The service reconstructs the pinned Active revision, the runtime snapshot and
    the configured Storage adapters from durable state, so it never shares
    in-memory authority with the API request that admitted the discovery.  The
    admitting request performs zero Storage enumeration; this Worker context is
    the only place a discovery becomes bounded Storage observations, and it
    remains metadata-only with zero mutation.
    """

    from mediaflow.application.media_discovery import MediaDiscoveryService

    bootstrap_document = _configuration_document(configured_path)
    management_only = isinstance(configuration, ManagementBootstrapConfiguration)
    with SQLiteConfigurationRepository(configuration.database_path) as configuration_repository:
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=configuration.database_path,
            bootstrap_document=bootstrap_document,
            management_only=management_only,
        )
        intents = ManualOrganizeIntentService(repository, configuration_service)
        previews = ManualOrganizePreviewService(
            repository,
            intents,
            configuration_service=configuration_service,
            metadata_provider_registry_factory=LazyMetadataProviderRegistryFactory(
                metadata_provider_registry_from_environment
            ),
        )
        discovery = MediaDiscoveryService(
            repository,
            intents,
            configuration_service=configuration_service,
            preview_service=previews,
        )
        yield discovery


@contextmanager
def _files_transfer_worker_context(configuration, configured_path: str | None, repository):
    """Yield the resident Worker's admitted Files Copy/Move transfer runner.

    The runner reconstructs the pinned Active revision, the runtime snapshot
    and the configured Storage adapters from durable state, so it never shares
    in-memory authority with the API request that admitted the transfer.  The
    admitting request performs zero Storage mutation; this Worker context is
    the only place an admitted transfer becomes ``OrganizerExecutor`` work.
    """

    from mediaflow.application.direct_file_commands import DirectFileCommandService
    from mediaflow.application.direct_file_transfers import DirectFileTransferService
    from mediaflow.application.files_transfer_worker import FilesTransferWorker
    from mediaflow.domain.direct_files import LibraryKind

    def reconstruct(revision_id: str, revision_digest: str, *, media_library: bool = False):
        """Rebuild the exact persisted revision a claimed transfer pinned.

        A resident Worker may outlive an activation, so it must execute each
        claimed transfer under that transfer's own immutable revision rather
        than under whatever Active snapshot the process started with.  A
        revision this process cannot lawfully reconstruct returns ``None`` and
        leaves the transfer claimable instead of consuming it as a failure.

        ``media_library`` selects the library kind of the rebuilt runtime: one
        kind's reconstructor never returns a service of the other kind, so the
        persisted kind of a claimed transfer is always honored.
        """

        with SQLiteConfigurationRepository(configuration.database_path) as pinned_repository:
            pinned = pinned_repository.get_revision(revision_id)
        if pinned is None:
            return None
        from mediaflow.domain.configuration_management import ManagedConfigurationStatus

        if pinned.status is ManagedConfigurationStatus.DRAFT:
            return None
        if revision_digest and pinned.digest != revision_digest:
            return None
        try:
            pinned_runtime = _configuration(
                configured_path,
                snapshot_id=pinned.revision_id,
                snapshot_digest=pinned.digest,
            )
        except Exception:
            return None
        published = replace(
            pinned,
            status=ManagedConfigurationStatus.ACTIVE,
            activated_at=pinned.activated_at or datetime.now(UTC),
        )
        return DirectFileCommandService(
            active_revision=published,
            runtime_configuration=pinned_runtime,
            task_repository=repository,
            storage_adapters=None,
            revision_rebuilder=reconstruct,
            library_kind=(LibraryKind.MEDIA if media_library else LibraryKind.RESOURCE),
        )

    resource_command = direct_command_task_command(FILES_TRANSFER_TASK_COMMAND, media_library=False)
    media_command = direct_command_task_command(FILES_TRANSFER_TASK_COMMAND, media_library=True)
    resource_delete_command = direct_command_task_command(
        FILES_DELETE_TASK_COMMAND, media_library=False
    )
    media_delete_command = direct_command_task_command(
        FILES_DELETE_TASK_COMMAND, media_library=True
    )

    def service_for(command: str, transfer):
        """Build one attempt boundary from the claimed transfer's durable pin."""

        media_library = command in {media_command, media_delete_command}
        if command not in {
            resource_command,
            media_command,
            resource_delete_command,
            media_delete_command,
        }:
            return None
        direct = reconstruct(
            transfer.configuration_snapshot_id,
            transfer.configuration_snapshot_digest,
            media_library=media_library,
        )
        if direct is None:
            return None
        return DirectFileTransferService(direct_files=direct)

    # The resident consumer exists before the first Active configuration and
    # throughout later Active outages.  It opens no provider here: each claim
    # is reconstructed from its own immutable revision/digest after ownership
    # has been acquired, and all Storage adapters remain attempt-scoped.
    yield FilesTransferWorker(
        None,
        repository,
        service_factory=service_for,
        supported_commands=(
            resource_command,
            media_command,
            resource_delete_command,
            media_delete_command,
        ),
    )


class _NullFilesTransferWorker:
    """A no-op transfer runner for Workers without an Active configuration."""

    @staticmethod
    def run_next():
        return None


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


def _configuration_document(path: str | None) -> object:
    configured = path or os.environ.get("MEDIAFLOW_CONFIG")
    if not configured:
        raise ValueError("--config or MEDIAFLOW_CONFIG is required")
    try:
        return json.loads(Path(configured).read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"configuration file could not be read: {error}") from error


def _configuration(
    path: str | None,
    *,
    use_managed: bool = True,
    snapshot_id: str | None = None,
    snapshot_digest: str | None = None,
) -> RuntimeConfiguration:
    raw_document = _configuration_document(path)
    if not use_managed:
        reject_retired_configuration_input(raw_document)
        return load_runtime_configuration(raw_document)
    bootstrap_database_path = _bootstrap_database_path(raw_document)
    try:
        with SQLiteConfigurationRepository(bootstrap_database_path) as repository:
            active = (
                repository.get_revision(snapshot_id)
                if snapshot_id
                else repository.get_active_revision()
            )
    except RuntimeSnapshotUnavailable:
        raise
    except Exception as error:
        if not snapshot_id:
            raise
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {snapshot_id!r} is unreadable",
            revision_id=snapshot_id,
            digest=snapshot_digest,
            reason="snapshot_unreadable",
        ) from error
    if active is None:
        if snapshot_id:
            raise RuntimeSnapshotUnavailable(
                f"managed configuration snapshot {snapshot_id!r} is unavailable",
                revision_id=snapshot_id,
                digest=snapshot_digest,
                reason="snapshot_missing",
            )
        with SQLiteConfigurationRepository(bootstrap_database_path) as repository:
            if repository.has_managed_activation():
                marker = repository.last_known_active()
                raise RuntimeSnapshotUnavailable(
                    "managed Active configuration is unavailable; "
                    "restore the last published snapshot or stage a new Draft",
                    revision_id=marker.get("revisionId") if marker else None,
                    version=marker.get("revisionSequence") if marker else None,
                    digest=marker.get("digest") if marker else None,
                    reason="active_missing",
                )
        raise RuntimeSnapshotUnavailable(
            "no managed Active configuration exists; create and activate the first setup Draft",
            reason="active_missing",
        )
    if active.schema_version != MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION:
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {active.revision_id!r} schema is unsupported",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="schema_unsupported",
        )
    if snapshot_id and active.status.value not in {"active", "superseded"}:
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {snapshot_id!r} is not a published revision",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="snapshot_not_published",
        )
    if snapshot_digest and active.digest != snapshot_digest:
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {active.revision_id!r} digest does not match the Job",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="snapshot_digest_mismatch",
        )
    canonical = json.dumps(
        active.document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != active.digest:
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {active.revision_id!r} digest is corrupt",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="digest_corrupt",
        )
    try:
        resolved = load_managed_runtime_configuration(
            active.document,
            bootstrap_database_path=bootstrap_database_path,
        )
    except Exception as error:
        raise RuntimeSnapshotUnavailable(
            f"managed Active configuration {active.revision_id!r} is unavailable: "
            f"{type(error).__name__}",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="runtime_invalid",
        ) from error
    return with_managed_snapshot(
        resolved,
        snapshot_id=active.revision_id,
        digest=active.digest,
        version=active.version,
    )


def _bootstrap_database_path(document: object) -> str:
    """Read only the bootstrap DB locator before managed authority is known.

    Once an Active revision exists, the rest of the JSON document is not trusted
    for workflow resolution. This small bootstrap field is needed solely to find
    the managed revision store and is never treated as active strategy content.
    """
    if not isinstance(document, dict):
        raise RuntimeSnapshotUnavailable("configuration bootstrap is not a JSON object")
    persistence = document.get("persistence")
    if not isinstance(persistence, dict):
        raise RuntimeSnapshotUnavailable("configuration bootstrap persistence is unavailable")
    value = persistence.get("databasePath", ".mediaflow/mediaflow.sqlite3")
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise RuntimeSnapshotUnavailable("configuration bootstrap databasePath is invalid")
    return value


def _task_snapshot_identity(path: str | None, task_id: str) -> tuple[str, str] | None:
    """Read a persisted Task's configuration pin before workflow bootstrap.

    A bounded read-only utility: it does not resolve strategy content or
    construct Storage/Provider objects; it only preserves the immutable
    identity already recorded at the Task boundary. Legacy Tasks without a pin
    fail closed once managed authority has been activated; before activation
    they remain bootstrap work.  The standalone retry-failed entrance that
    used to call this was retired (Slice 47 RO-6); a four-type continuation
    resolves its own pinned snapshot inside its admitting service.
    """
    try:
        document = _configuration_document(path)
        database_path = _bootstrap_database_path(document)
        with SQLiteTaskRepository(database_path) as repository:
            task = repository.get_task(task_id)
        if task is not None and not task.configuration_snapshot_id:
            with SQLiteConfigurationRepository(database_path) as configuration_repository:
                if configuration_repository.has_managed_activation():
                    raise RuntimeSnapshotUnavailable(
                        "legacy Task has no managed configuration snapshot pin; "
                        "recreate the Task under the current Active configuration"
                    )
    except RuntimeSnapshotUnavailable:
        raise
    except (OSError, ValueError, RuntimeError):
        return None
    if task is None or not task.configuration_snapshot_id:
        return None
    return task.configuration_snapshot_id, task.configuration_snapshot_digest or ""


def _managed_snapshot_identity(path: str | None) -> tuple[str, str] | None:
    """Resolve the current managed identity for long-lived Job producers."""

    document = _configuration_document(path)
    database_path = _bootstrap_database_path(document)
    with SQLiteConfigurationRepository(database_path) as repository:
        active = repository.get_active_revision()
        if active is None:
            if repository.has_managed_activation():
                raise RuntimeSnapshotUnavailable(
                    "managed Active configuration is unavailable; scheduler is fail-closed",
                    reason="active_missing",
                )
            return None
        if active.schema_version != MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION:
            raise RuntimeSnapshotUnavailable(
                f"managed Active configuration {active.revision_id!r} schema is unsupported",
                revision_id=active.revision_id,
                version=active.revision_sequence,
                digest=active.digest,
                reason="schema_unsupported",
            )
        if (
            hashlib.sha256(
                json.dumps(
                    active.document,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
            != active.digest
        ):
            raise RuntimeSnapshotUnavailable(
                f"managed Active configuration {active.revision_id!r} digest is corrupt",
                revision_id=active.revision_id,
                version=active.revision_sequence,
                digest=active.digest,
                reason="digest_corrupt",
            )
        try:
            load_managed_runtime_configuration(
                active.document,
                bootstrap_database_path=database_path,
            )
        except Exception as error:
            raise RuntimeSnapshotUnavailable(
                f"managed Active configuration {active.revision_id!r} is unavailable: "
                f"{type(error).__name__}: {str(error)[:400]}",
                revision_id=active.revision_id,
                version=active.revision_sequence,
                digest=active.digest,
                reason="runtime_invalid",
            ) from error
        return active.revision_id, active.digest


def _managed_snapshot_reference(path: str | None) -> tuple[str, str] | None:
    """Read the current managed identity without validating its workflow document.

    A Worker must bind its registration to the persisted Active identity, but it
    must still be able to finish an already pinned Job when a newer Active
    document is unhealthy.  The claimed Job remains responsible for loading
    and validating the exact snapshot it consumes.
    """

    document = _configuration_document(path)
    database_path = _bootstrap_database_path(document)
    with SQLiteConfigurationRepository(database_path) as repository:
        active = repository.get_active_revision()
        if active is None:
            return None
        return active.revision_id, active.digest


def _managed_scheduler_configuration(
    path: str | None,
) -> SchedulerConfigurationSnapshot | None:
    """Resolve schedule definitions and pin from one current runtime revision.

    ``None`` means "no managed Active exists to admit from", which is the normal
    pre-activation state.  The Scheduler treats that as an empty definition set
    and emits nothing, rather than reusing whatever the JSON bootstrap happened
    to contain.
    """

    # The resolver seam is the *managed* one: a resident Scheduler pins every
    # occurrence it issues to published authority, and a legacy JSON bootstrap
    # has no identity to pin to.  It therefore yields no snapshot here, which
    # makes the resident path fail closed while the one-shot commands below
    # still support the pre-activation compatibility runtime.
    configuration = _current_managed_runtime_configuration(path)
    return _scheduler_snapshot_from_runtime(configuration)


def _scheduler_snapshot_from_runtime(configuration) -> SchedulerConfigurationSnapshot | None:
    """Pin occurrence and notification publication to the same resolved runtime."""

    if configuration is None or not getattr(configuration, "configuration_snapshot_id", None):
        return None
    return SchedulerConfigurationSnapshot(
        configuration.configuration_snapshot_id,
        configuration.configuration_snapshot_digest or "",
        configuration.automation_maximum_active_jobs,
        configuration.automation_task_definitions,
        configuration.configuration_snapshot_version,
        tuple(item.library_id for item in configuration.resource_libraries),
        tuple(item.library_id for item in configuration.resource_libraries if item.enabled),
    )


_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


def _validate_api_bind_host(host: str) -> bool:
    if (
        not host
        or len(host) > 253
        or host != host.strip()
        or any(value in host for value in "/\\\x00")
    ):
        raise ValueError("API host must be a valid hostname or IP address")
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        labels = host[:-1].split(".") if host.endswith(".") else host.split(".")
        if not labels or any(not _HOST_LABEL.fullmatch(label) for label in labels):
            raise ValueError("API host must be a valid hostname or IP address") from None
        return False


def render_api_credentials(values) -> str:
    lines = ["API CREDENTIALS", ""]
    if not values:
        return "\n".join(lines + ["No API principals configured", ""])
    for value in values:
        lines.append(
            " | ".join(
                (
                    value.principal_id,
                    ",".join(role.value for role in value.roles),
                    value.token_env,
                    "ENABLED" if value.enabled else "DISABLED",
                    "SET" if value.configured else "UNSET",
                )
            )
        )
    return "\n".join(lines + [""])


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
